import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

from click.testing import CliRunner

from vbumper.cli import bump, list_  # imported for their command-registration side effect
from vbumper.cli._grp import root_grp
from vbumper.core.plugins.installer import install_plugins


def _write_config(config_yaml: str) -> None:
    pathlib.Path(".vbump.yaml").write_text(textwrap.dedent(config_yaml))


def _write_version_file(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


class BumpCLITestCase(unittest.TestCase):
    """Base class: installs the plugin registry once per test (idempotent since
    `install_plugins()` resets its own registry) and runs each test in its own temp dir."""

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

    def single_file_config(self, *, include="pkg/version.txt"):
        _write_config(
            f"""\
            version: 3
            discoverers:
              - type: file-regexp
                include: {include}
                version: 'version = "(?P<version>[^"]*)"'
            """
        )


class TestBasicBumps(BumpCLITestCase):
    def setUp(self):
        super().setUp()
        self.single_file_config()
        _write_version_file("pkg/version.txt", 'version = "1.2.3"\n')

    def _read(self) -> str:
        return pathlib.Path("pkg/version.txt").read_text()

    def test_patch(self):
        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.4"\n')

    def test_minor_resets_patch(self):
        result = self.invoke(["minor"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.3.0"\n')

    def test_major_resets_minor_and_patch(self):
        result = self.invoke(["major"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "2.0.0"\n')

    def test_chained_minor_then_rc(self):
        result = self.invoke(["minor", "rc"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.3.0-rc.1"\n')

    def test_set_explicit_version(self):
        result = self.invoke(["set", "9.9.9-beta.2"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "9.9.9-beta.2"\n')

    def test_set_rejects_invalid_version_string(self):
        result = self.invoke(["set", "not-a-version"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(self._read(), 'version = "1.2.3"\n')

    def test_print_outputs_common_version(self):
        result = self.invoke(["print"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.output.strip(), "1.2.3")
        # `print` alone must not write anything back.
        self.assertEqual(self._read(), 'version = "1.2.3"\n')

    def test_dry_run_changes_nothing_on_disk(self):
        result = self.invoke(["-n", "patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Would update", result.output)
        self.assertEqual(self._read(), 'version = "1.2.3"\n')

    def test_nothing_changed_is_reported_and_file_untouched(self):
        result = self.invoke(["set", "1.2.3"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Nothing has changed", result.output)


class TestBuiltinPyProjectDiscovery(BumpCLITestCase):
    """`pyproject-toml` is a zero-configuration built-in in the sense that activating it takes no
    parameters beyond `type:` -- but, like every discoverer, it still has to be listed under
    `discoverers:` to run at all (built-ins are opt-in, not always-on)."""

    def setUp(self):
        super().setUp()
        _write_config(
            """\
            version: 3
            discoverers:
              - type: pyproject-toml
            """
        )
        _write_version_file(
            "pyproject.toml",
            'name = "example"\nversion = "1.2.3"\n',
        )

    def test_patch_bumps_pyproject_toml(self):
        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            pathlib.Path("pyproject.toml").read_text(), 'name = "example"\nversion = "1.2.4"\n'
        )

    def test_extra_configured_discoverer_runs_alongside_the_builtin(self):
        _write_config(
            """\
            version: 3
            discoverers:
              - type: pyproject-toml
              - type: file-regexp
                include: pkg/version.txt
                version: 'version = "(?P<version>[^"]*)"'
            """
        )
        _write_version_file("pkg/version.txt", 'version = "1.2.3"\n')

        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.4"\n')
        self.assertEqual(
            pathlib.Path("pyproject.toml").read_text(), 'name = "example"\nversion = "1.2.4"\n'
        )


class TestBuiltinPackageJsonDiscovery(BumpCLITestCase):
    """Same shape as `TestBuiltinPyProjectDiscovery`, for the `package-json` built-in."""

    def setUp(self):
        super().setUp()
        _write_config(
            """\
            version: 3
            discoverers:
              - type: package-json
            """
        )
        _write_version_file(
            "package.json",
            '{\n  "name": "example",\n  "version": "1.2.3"\n}\n',
        )

    def test_patch_bumps_package_json(self):
        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            pathlib.Path("package.json").read_text(),
            '{\n  "name": "example",\n  "version": "1.2.4"\n}\n',
        )

    def test_both_builtin_discoverers_agree_and_bump_together(self):
        _write_config(
            """\
            version: 3
            discoverers:
              - type: package-json
              - type: pyproject-toml
            """
        )
        _write_version_file("pyproject.toml", 'name = "example"\nversion = "1.2.3"\n')

        result = self.invoke(["minor"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            pathlib.Path("package.json").read_text(),
            '{\n  "name": "example",\n  "version": "1.3.0"\n}\n',
        )
        self.assertEqual(
            pathlib.Path("pyproject.toml").read_text(), 'name = "example"\nversion = "1.3.0"\n'
        )


_INFO_PLIST_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
    ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    '<plist version="1.0">\n'
    "<dict>\n"
)


def _info_plist(version_string: str) -> str:
    return (
        _INFO_PLIST_HEADER + "\t<key>CFBundleShortVersionString</key>\n"
        f"\t<string>{version_string}</string>\n"
        "</dict>\n"
        "</plist>\n"
    )


class TestBuiltinInfoPlistDiscovery(BumpCLITestCase):
    """Same shape as `TestBuiltinPyProjectDiscovery`, for the `info-plist` built-in."""

    def setUp(self):
        super().setUp()
        _write_config(
            """\
            version: 3
            discoverers:
              - type: info-plist
            """
        )
        _write_version_file("Info.plist", _info_plist("1.2.3"))

    def test_patch_bumps_info_plist(self):
        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("Info.plist").read_text(), _info_plist("1.2.4"))

    def test_all_three_builtin_discoverers_agree_and_bump_together(self):
        _write_config(
            """\
            version: 3
            discoverers:
              - type: info-plist
              - type: pyproject-toml
              - type: package-json
            """
        )
        _write_version_file("pyproject.toml", 'name = "example"\nversion = "1.2.3"\n')
        _write_version_file("package.json", '{\n  "name": "example",\n  "version": "1.2.3"\n}\n')

        result = self.invoke(["minor"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("Info.plist").read_text(), _info_plist("1.3.0"))
        self.assertEqual(
            pathlib.Path("pyproject.toml").read_text(), 'name = "example"\nversion = "1.3.0"\n'
        )
        self.assertEqual(
            pathlib.Path("package.json").read_text(),
            '{\n  "name": "example",\n  "version": "1.3.0"\n}\n',
        )


class TestPrereleaseFamily(BumpCLITestCase):
    def setUp(self):
        super().setUp()
        self.single_file_config()

    def _read(self) -> str:
        return pathlib.Path("pkg/version.txt").read_text()

    def test_prerelease_bumps_patch_first_time(self):
        _write_version_file("pkg/version.txt", 'version = "1.2.3"\n')
        result = self.invoke(["prerelease"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.4-rc.1"\n')

    def test_prerelease_uses_custom_token_option(self):
        _write_version_file("pkg/version.txt", 'version = "1.2.3"\n')
        result = self.invoke(["--prerelease-token", "beta", "prerelease"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.4-beta.1"\n')

    def test_rc_advances_existing_rc_serial(self):
        _write_version_file("pkg/version.txt", 'version = "1.2.3-rc.1"\n')
        result = self.invoke(["rc"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.3-rc.2"\n')

    def test_alpha_then_beta_switches_token_and_resets_serial(self):
        _write_version_file("pkg/version.txt", 'version = "1.2.3-alpha.3"\n')
        result = self.invoke(["beta"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.3-beta.1"\n')

    def test_lower_advances_prerelease_when_already_one(self):
        _write_version_file("pkg/version.txt", 'version = "1.2.3-rc.1"\n')
        result = self.invoke(["lower"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.3-rc.2"\n')

    def test_lower_bumps_patch_when_stable(self):
        _write_version_file("pkg/version.txt", 'version = "1.2.3"\n')
        result = self.invoke(["lower"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.4"\n')

    def test_stable_drops_prerelease(self):
        _write_version_file("pkg/version.txt", 'version = "1.2.3-rc.4"\n')
        result = self.invoke(["stable"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._read(), 'version = "1.2.3"\n')


class TestForceOnPrerelease(BumpCLITestCase):
    def setUp(self):
        super().setUp()
        self.single_file_config()
        _write_version_file("pkg/version.txt", 'version = "1.2.3-rc.1"\n')

    def test_patch_refuses_prerelease_without_force(self):
        result = self.invoke(["patch"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.3-rc.1"\n')

    def test_patch_succeeds_with_force_and_clears_prerelease(self):
        result = self.invoke(["-f", "patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.4"\n')


class TestNoVersionedContainer(BumpCLITestCase):
    def setUp(self):
        super().setUp()
        self.single_file_config()
        _write_version_file("pkg/version.txt", 'version = ""\n')

    def test_bump_errors_out(self):
        result = self.invoke(["patch"])
        self.assertNotEqual(result.exit_code, 0)

    def test_set_still_works(self):
        result = self.invoke(["set", "0.1.0"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "0.1.0"\n')


class TestUnversionedContainerIsFilledIn(BumpCLITestCase):
    def setUp(self):
        super().setUp()
        _write_config(
            """\
            version: 3
            discoverers:
              - type: file-regexp
                include: "*.txt"
                version: 'version = "(?P<version>[^"]*)"'
            """
        )
        _write_version_file("a.txt", 'version = "1.0.0"\n')
        _write_version_file("b.txt", 'version = ""\n')

    def test_patch_fills_in_the_unversioned_container_too(self):
        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.1"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "1.0.1"\n')


class TestIncompatibleVersions(BumpCLITestCase):
    def setUp(self):
        super().setUp()
        _write_config(
            """\
            version: 3
            discoverers:
              - type: file-regexp
                include: "*.txt"
                version: 'version = "(?P<version>[^"]*)"'
            """
        )
        _write_version_file("a.txt", 'version = "1.0.0"\n')
        _write_version_file("b.txt", 'version = "not-semver"\n')

    def test_refuses_without_flag(self):
        result = self.invoke(["patch"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "not-semver"\n')

    def test_allow_incompatible_versions_bumps_from_the_valid_one_and_overrides_the_rest(self):
        result = self.invoke(["--allow-incompatible-versions", "patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.1"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "1.0.1"\n')

    def test_skip_unreadable_version_strings_leaves_the_invalid_file_untouched(self):
        result = self.invoke(["--skip-unreadable-version-strings", "patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.1"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "not-semver"\n')


class TestListCommand(BumpCLITestCase):
    def test_list_shows_discovered_containers_without_raising_on_disagreement(self):
        _write_config(
            """\
            version: 3
            discoverers:
              - type: file-regexp
                include: "*.txt"
                version: 'version = "(?P<version>[^"]*)"'
            """
        )
        _write_version_file("a.txt", 'version = "1.0.0"\n')
        _write_version_file("b.txt", 'version = "2.0.0"\n')

        result = self.invoke(["list"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1.0.0", result.output)
        self.assertIn("2.0.0", result.output)
        # `list` never writes anything back.
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "2.0.0"\n')


class TestFlowEngine(BumpCLITestCase):
    """CLI-level exercise of the flow engine, using a real throwaway Git repo and marker-file
    `pre_commands`/`post_commands` in place of real `git` mutating commands, to keep this
    self-contained and independent of the repo's actual branch layout."""

    def setUp(self):
        super().setUp()

        subprocess.run(["git", "init", "-q"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test"], check=True)

        _write_config(
            f"""\
            version: 3
            default_flow: release
            flows:
              release:
                name: Release
                require_on_branch: main
                pre_commands:
                  - - {sys.executable!r}
                    - -c
                    - import pathlib; pathlib.Path('pre.marker').write_text('{{VERSION}}')
                post_commands:
                  - - {sys.executable!r}
                    - -c
                    - import pathlib; pathlib.Path('post.marker').write_text('{{VERSION_TAG}}')
            discoverers:
              - type: file-regexp
                include: pkg/version.txt
                version: 'version = "(?P<version>[^"]*)"'
            """
        )
        _write_version_file("pkg/version.txt", 'version = "1.2.3"\n')
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], check=True)
        subprocess.run(["git", "checkout", "-q", "-b", "main"], check=True)

    def test_flow_runs_pre_and_post_commands_around_write_back(self):
        result = self.invoke(["patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.4"\n')
        self.assertEqual(pathlib.Path("pre.marker").read_text(), "1.2.4")
        self.assertEqual(pathlib.Path("post.marker").read_text(), "v1.2.4")

    def test_no_flow_skips_pre_and_post_commands(self):
        result = self.invoke(["--no-flow", "patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.4"\n')
        self.assertFalse(pathlib.Path("pre.marker").exists())
        self.assertFalse(pathlib.Path("post.marker").exists())

    def test_dry_run_previews_flow_commands_and_runs_nothing(self):
        result = self.invoke(["-n", "patch"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Would execute:", result.output)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.3"\n')
        self.assertFalse(pathlib.Path("pre.marker").exists())
        self.assertFalse(pathlib.Path("post.marker").exists())

    def test_wrong_branch_refuses_before_writing_anything(self):
        subprocess.run(["git", "checkout", "-q", "-b", "other"], check=True)
        result = self.invoke(["patch"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.3"\n')
        self.assertFalse(pathlib.Path("pre.marker").exists())

    def test_dirty_repository_refuses_without_override(self):
        pathlib.Path("pkg/version.txt").write_text('version = "1.2.3"  # dirty\n')
        result = self.invoke(["patch"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(pathlib.Path("pre.marker").exists())

    def test_unknown_flow_name_errors_out(self):
        result = self.invoke(["--flow", "does-not-exist", "patch"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(pathlib.Path("pkg/version.txt").read_text(), 'version = "1.2.3"\n')

    def test_flow_and_no_flow_together_is_a_usage_error(self):
        result = self.invoke(["--flow", "release", "--no-flow", "patch"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("mutually exclusive", result.output)


if __name__ == "__main__":
    unittest.main()
