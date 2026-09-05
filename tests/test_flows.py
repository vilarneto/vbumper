import os
import pathlib
import shlex
import subprocess
import tempfile
import unittest

import pydantic

from vbumper.config.flow import FlowConfig
from vbumper.config.root import VBumpConfig
from vbumper.core.exceptions import (
    DirtyRepositoryError,
    FlowCommandFailure,
    UnknownFlowError,
    WrongBranchError,
)
from vbumper.core.flows import (
    check_preconditions,
    current_branch,
    is_repository_dirty,
    resolve_selected_flow,
    run_commands,
    substitute_placeholders,
)
from vbumper.core.semver import SemVer


class TestResolveSelectedFlow(unittest.TestCase):
    """Uses flow keys that don't collide with any real stock flow, so these tests exercise
    `resolve_selected_flow`'s own selection logic in isolation from `all_flows`'s merge behavior
    (covered separately in `test_plugins.TestAllFlowsMerge`)."""

    def setUp(self):
        self.config = VBumpConfig(
            default_flow="flow-a",
            flows={
                "flow-a": FlowConfig(name="main bump"),
                "flow-b": FlowConfig(name="git flow"),
            },
        )

    def test_no_flow_wins_over_default(self):
        self.assertIsNone(resolve_selected_flow(self.config, flow=None, no_flow=True))

    def test_no_flow_wins_over_explicit_flow(self):
        self.assertIsNone(resolve_selected_flow(self.config, flow="flow-b", no_flow=True))

    def test_explicit_flow_overrides_default(self):
        key, flow_config = resolve_selected_flow(self.config, flow="flow-b", no_flow=False)
        self.assertEqual(key, "flow-b")
        self.assertEqual(flow_config.name, "git flow")

    def test_falls_back_to_default_flow(self):
        key, flow_config = resolve_selected_flow(self.config, flow=None, no_flow=False)
        self.assertEqual(key, "flow-a")
        self.assertEqual(flow_config.name, "main bump")

    def test_no_default_flow_and_no_explicit_flow_yields_none(self):
        config = VBumpConfig()
        self.assertIsNone(resolve_selected_flow(config, flow=None, no_flow=False))

    def test_unknown_explicit_flow_raises(self):
        with self.assertRaises(UnknownFlowError):
            resolve_selected_flow(self.config, flow="does-not-exist", no_flow=False)


class TestFlowConfigVariables(unittest.TestCase):
    def test_rejects_version_as_a_variable_name(self):
        with self.assertRaises(pydantic.ValidationError):
            FlowConfig(variables={"VERSION": "1.2.3"})

    def test_rejects_version_tag_as_a_variable_name(self):
        with self.assertRaises(pydantic.ValidationError):
            FlowConfig(variables={"VERSION_TAG": "v1.2.3"})

    def test_accepts_non_reserved_variable_names(self):
        flow = FlowConfig(variables={"RELEASE_BRANCH": "main"})
        self.assertEqual(flow.variables, {"RELEASE_BRANCH": "main"})


class TestSubstitutePlaceholders(unittest.TestCase):
    def test_substitutes_version_and_version_tag(self):
        version = SemVer.parse("1.2.3")
        result = substitute_placeholders(
            "git tag {VERSION_TAG} -m 'release {VERSION}'",
            version=version,
            version_tag_prefix="v",
        )
        self.assertEqual(result, "git tag v1.2.3 -m 'release 1.2.3'")

    def test_leaves_text_without_placeholders_untouched(self):
        version = SemVer.parse("1.0.0")
        result = substitute_placeholders(
            "git checkout main", version=version, version_tag_prefix="v"
        )
        self.assertEqual(result, "git checkout main")

    def test_substitutes_variables_when_given(self):
        version = SemVer.parse("1.0.0")
        result = substitute_placeholders(
            "git checkout {RELEASE_BRANCH} && git merge {DEVELOP_BRANCH}",
            version=version,
            version_tag_prefix="v",
            variables={"RELEASE_BRANCH": "main", "DEVELOP_BRANCH": "develop"},
        )
        self.assertEqual(result, "git checkout main && git merge develop")

    def test_leaves_variable_placeholders_untouched_when_unset(self):
        version = SemVer.parse("1.0.0")
        result = substitute_placeholders(
            "git checkout {RELEASE_BRANCH}", version=version, version_tag_prefix="v"
        )
        self.assertEqual(result, "git checkout {RELEASE_BRANCH}")


class _GitRepoTestCase(unittest.TestCase):
    """Base class for tests needing a real (throwaway) Git repository on disk."""

    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.repo_dir = pathlib.Path(tmp_dir.name)

        previous_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        self.addCleanup(os.chdir, previous_cwd)

        subprocess.run(["git", "init", "-q"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test"], check=True)
        (self.repo_dir / "README.md").write_text("hello\n")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], check=True)


class TestRepositoryIntrospection(_GitRepoTestCase):
    def test_current_branch_reads_head(self):
        branch = current_branch()
        subprocess.run(["git", "checkout", "-q", "-b", "feature"], check=True)
        self.assertEqual(current_branch(), "feature")
        self.assertNotEqual(branch, "feature")

    def test_clean_tree_is_not_dirty(self):
        self.assertFalse(is_repository_dirty())

    def test_uncommitted_change_is_dirty(self):
        (self.repo_dir / "README.md").write_text("changed\n")
        self.assertTrue(is_repository_dirty())


class TestCheckPreconditions(_GitRepoTestCase):
    def test_clean_tree_and_matching_branch_passes(self):
        branch = current_branch()
        check_preconditions(
            FlowConfig(require_on_branch=branch), allow_dirty_repository=False
        )  # no raise

    def test_dirty_tree_raises_without_override(self):
        (self.repo_dir / "README.md").write_text("changed\n")
        with self.assertRaises(DirtyRepositoryError):
            check_preconditions(FlowConfig(), allow_dirty_repository=False)

    def test_dirty_tree_allowed_with_override(self):
        (self.repo_dir / "README.md").write_text("changed\n")
        check_preconditions(FlowConfig(), allow_dirty_repository=True)  # no raise

    def test_wrong_branch_raises(self):
        with self.assertRaises(WrongBranchError):
            check_preconditions(
                FlowConfig(require_on_branch="does-not-exist"), allow_dirty_repository=False
            )

    def test_no_require_on_branch_skips_branch_check(self):
        check_preconditions(FlowConfig(require_on_branch=None), allow_dirty_repository=False)

    def test_require_on_branch_is_substituted_against_variables(self):
        branch = current_branch()
        check_preconditions(
            FlowConfig(require_on_branch="{DEVELOP_BRANCH}", variables={"DEVELOP_BRANCH": branch}),
            allow_dirty_repository=False,
        )  # no raise

    def test_require_on_branch_placeholder_mismatch_raises(self):
        with self.assertRaises(WrongBranchError):
            check_preconditions(
                FlowConfig(
                    require_on_branch="{DEVELOP_BRANCH}",
                    variables={"DEVELOP_BRANCH": "does-not-exist"},
                ),
                allow_dirty_repository=False,
            )


class TestRunCommands(unittest.TestCase):
    def setUp(self):
        self.version = SemVer.parse("1.2.3")

    def test_dry_run_prints_would_execute_and_does_not_run(self):
        import rich_click as click
        from click.testing import CliRunner

        @click.command()
        def _invoke_dry_run():
            run_commands(
                ["some-command-that-does-not-exist {VERSION}"],
                version=self.version,
                version_tag_prefix="v",
                dry_run=True,
            )

        result = CliRunner().invoke(_invoke_dry_run, [])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Would execute: some-command-that-does-not-exist 1.2.3", result.output)

    def test_real_run_executes_and_substitutes_placeholders(self):
        marker = pathlib.Path(tempfile.mktemp())
        self.addCleanup(lambda: marker.unlink(missing_ok=True))

        run_commands(
            [f"echo {{VERSION_TAG}} > {shlex.quote(str(marker))}"],
            version=self.version,
            version_tag_prefix="v",
            dry_run=False,
        )
        self.assertEqual(marker.read_text().strip(), "v1.2.3")

    def test_failing_command_raises_and_stops_the_sequence(self):
        marker = pathlib.Path(tempfile.mktemp())
        self.addCleanup(lambda: marker.unlink(missing_ok=True))

        with self.assertRaises(FlowCommandFailure):
            run_commands(
                ["exit 1", f"touch {shlex.quote(str(marker))}"],
                version=self.version,
                version_tag_prefix="v",
                dry_run=False,
            )
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
