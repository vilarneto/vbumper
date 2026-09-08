import os
import pathlib
import tempfile
import textwrap
import unittest
from unittest import mock

from click.testing import CliRunner

from vbumper.cli import bump, init, list_  # imported for their command-registration side effect
from vbumper.cli._grp import root_grp
from vbumper.config.flow import FlowDefinition
from vbumper.config.global_config import GlobalConfig
from vbumper.core.plugins.installer import install_plugins


def _write_version_file(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


class InitCLITestCase(unittest.TestCase):
    """Mirrors `test_cli_bump.BumpCLITestCase`'s temp-dir/plugin-registry setup."""

    def setUp(self):
        install_plugins()
        self.runner = CliRunner()

        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        previous_cwd = os.getcwd()
        os.chdir(tmp_dir.name)
        self.addCleanup(os.chdir, previous_cwd)

    def invoke(self, args):
        return self.runner.invoke(root_grp, args)

    def patch_global_config(self, flows: dict[str, FlowDefinition]):
        patcher = mock.patch(
            "vbumper.config.global_config.load_global_config",
            return_value=GlobalConfig(flows=flows),
        )
        patcher.start()
        self.addCleanup(patcher.stop)


class TestInitScaffold(InitCLITestCase):
    def test_writes_empty_discoverers_when_nothing_matches(self):
        result = self.invoke(["init"])
        self.assertEqual(result.exit_code, 0, result.output)

        contents = pathlib.Path(".vbump.yaml").read_text()
        self.assertIn("version: 3", contents)
        self.assertIn("discoverers: []", contents)

    def test_detects_pyproject_toml(self):
        _write_version_file("pyproject.toml", 'name = "example"\nversion = "1.2.3"\n')

        result = self.invoke(["init"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("pyproject-toml", result.output)

        contents = pathlib.Path(".vbump.yaml").read_text()
        self.assertIn("- type: pyproject-toml", contents)

    def test_detects_multiple_builtins_and_the_config_it_writes_actually_works(self):
        _write_version_file("pyproject.toml", 'name = "example"\nversion = "1.2.3"\n')
        _write_version_file("package.json", '{\n  "name": "example",\n  "version": "1.2.3"\n}\n')

        result = self.invoke(["init"])
        self.assertEqual(result.exit_code, 0, result.output)

        contents = pathlib.Path(".vbump.yaml").read_text()
        self.assertIn("- type: pyproject-toml", contents)
        self.assertIn("- type: package-json", contents)

        # The generated config must itself be usable for a real bump, not just look right.
        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            pathlib.Path("pyproject.toml").read_text(), 'name = "example"\nversion = "1.2.4"\n'
        )
        self.assertEqual(
            pathlib.Path("package.json").read_text(),
            '{\n  "name": "example",\n  "version": "1.2.4"\n}\n',
        )

    def test_does_not_detect_file_regexp_since_it_needs_an_include_pattern(self):
        _write_version_file("Dockerfile", "ARG VERSION=1.2.3\n")

        result = self.invoke(["init"])
        self.assertEqual(result.exit_code, 0, result.output)

        contents = pathlib.Path(".vbump.yaml").read_text()
        self.assertNotIn("- type: file-regexp", contents)
        self.assertIn("discoverers: []", contents)

    def test_refuses_to_overwrite_an_existing_config(self):
        pathlib.Path(".vbump.yaml").write_text("version: 3\ndiscoverers: []\n")

        result = self.invoke(["init"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already exists", str(result.output) + str(result.exception))

    def test_dry_run_does_not_write_anything(self):
        _write_version_file("pyproject.toml", 'name = "example"\nversion = "1.2.3"\n')

        result = self.invoke(["-n", "init"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(pathlib.Path(".vbump.yaml").exists())
        self.assertIn("Would write", result.output)


class TestInitFlows(InitCLITestCase):
    def test_single_flow_is_copied_in(self):
        self.patch_global_config({"release": FlowDefinition(name="Release")})

        result = self.invoke(["init", "--flows=release"])
        self.assertEqual(result.exit_code, 0, result.output)

        from vbumper.config.load import load_config_file

        config = load_config_file(".vbump.yaml")
        self.assertIn("release", config.flows)
        self.assertEqual(config.flows["release"].name, "Release")

    def test_multiple_comma_separated_flows_are_copied_in(self):
        self.patch_global_config(
            {"release": FlowDefinition(name="Release"), "hotfix": FlowDefinition(name="Hotfix")}
        )

        result = self.invoke(["init", "--flows=release,hotfix"])
        self.assertEqual(result.exit_code, 0, result.output)

        from vbumper.config.load import load_config_file

        config = load_config_file(".vbump.yaml")
        self.assertEqual(set(config.flows), {"release", "hotfix"})

    def test_unknown_flow_name_fails_before_writing_anything(self):
        self.patch_global_config({"release": FlowDefinition(name="Release")})

        result = self.invoke(["init", "--flows=missing"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(pathlib.Path(".vbump.yaml").exists())


class TestMissingConfigIsAnError(InitCLITestCase):
    """Every discoverer is opt-in, so a project with no config file at all must fail loudly
    rather than silently discovering nothing."""

    def test_list_without_a_config_file_fails_with_a_pointer_to_init(self):
        result = self.invoke(["list"])
        self.assertNotEqual(result.exit_code, 0)
        message = str(result.output) + str(result.exception)
        self.assertIn("vbump init", message)

    def test_after_init_list_succeeds(self):
        _write_version_file("pyproject.toml", 'name = "example"\nversion = "1.2.3"\n')

        result = self.invoke(["init"])
        self.assertEqual(result.exit_code, 0, result.output)

        result = self.invoke(["list"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1.2.3", result.output)


class TestEmptyDiscoverersWarns(InitCLITestCase):
    def test_empty_discoverers_list_warns_but_does_not_fail(self):
        pathlib.Path(".vbump.yaml").write_text(
            textwrap.dedent(
                """\
                version: 3
                discoverers: []
                """
            )
        )

        with self.assertWarns(UserWarning):
            result = self.invoke(["list"])
        self.assertEqual(result.exit_code, 0, result.output)


__all__ = []
