import os
import pathlib
import tempfile
import unittest
from unittest import mock

from click.testing import CliRunner

from vbumper.cli import bump, flow, init, list_  # imported for their command-registration effect
from vbumper.cli._grp import root_grp
from vbumper.config.flow import FlowDefinition
from vbumper.config.global_config import GlobalConfig
from vbumper.core.plugins.installer import install_plugins


class FlowAddCLITestCase(unittest.TestCase):
    """Mirrors `test_init.InitCLITestCase`'s temp-dir/plugin-registry setup."""

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


class TestFlowAdd(FlowAddCLITestCase):
    def test_missing_project_config_is_an_error(self):
        self.patch_global_config({"release": FlowDefinition(name="Release")})

        result = self.invoke(["flow", "add", "release"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("vbump init", str(result.output) + str(result.exception))

    def test_no_global_config_is_an_error(self):
        pathlib.Path(".vbump.yaml").write_text("version: 3\n")
        self.patch_global_config({})

        result = self.invoke(["flow", "add", "release"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("release", str(result.output) + str(result.exception))

    def test_happy_path_copies_the_template_and_preserves_comments(self):
        pathlib.Path(".vbump.yaml").write_text("# hand-written note\nversion: 3\ndiscoverers: []\n")
        self.patch_global_config(
            {"release": FlowDefinition(name="Release", pre_commands=["echo hi"])}
        )

        result = self.invoke(["flow", "add", "release"])
        self.assertEqual(result.exit_code, 0, result.output)

        contents = pathlib.Path(".vbump.yaml").read_text()
        self.assertIn("# hand-written note", contents)
        self.assertIn("Release", contents)
        self.assertIn("echo hi", contents)

    def test_collision_without_update_is_an_error_and_file_is_unchanged(self):
        original = "version: 3\nflows:\n  release:\n    name: Old\ndiscoverers: []\n"
        pathlib.Path(".vbump.yaml").write_text(original)
        self.patch_global_config({"release": FlowDefinition(name="New")})

        result = self.invoke(["flow", "add", "release"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--update", str(result.output) + str(result.exception))
        self.assertEqual(pathlib.Path(".vbump.yaml").read_text(), original)

    def test_update_refreshes_definition_but_preserves_local_variables(self):
        pathlib.Path(".vbump.yaml").write_text(
            "version: 3\n"
            "flows:\n"
            "  release:\n"
            "    name: Old\n"
            "    pre_commands: [echo old]\n"
            "    variables:\n"
            "      RELEASE_BRANCH: master\n"
            "discoverers: []\n"
        )
        self.patch_global_config(
            {
                "release": FlowDefinition(
                    name="New",
                    pre_commands=["echo new"],
                    variables={"RELEASE_BRANCH": "main", "DEVELOP_BRANCH": "develop"},
                )
            }
        )

        result = self.invoke(["flow", "add", "release", "--update"])
        self.assertEqual(result.exit_code, 0, result.output)

        from vbumper.config.load import load_config_file

        config = load_config_file(".vbump.yaml")
        flow_def = config.flows["release"]
        self.assertEqual(flow_def.name, "New")
        self.assertEqual(flow_def.pre_commands, ["echo new"])
        # The project's own RELEASE_BRANCH override survives; the template's new DEVELOP_BRANCH
        # is still picked up since the project never redefined it.
        self.assertEqual(
            flow_def.variables, {"RELEASE_BRANCH": "master", "DEVELOP_BRANCH": "develop"}
        )

    def test_set_overrides_a_variable_on_first_add(self):
        pathlib.Path(".vbump.yaml").write_text("version: 3\ndiscoverers: []\n")
        self.patch_global_config({"release": FlowDefinition(variables={"RELEASE_BRANCH": "main"})})

        result = self.invoke(["flow", "add", "release", "--set", "RELEASE_BRANCH=master"])
        self.assertEqual(result.exit_code, 0, result.output)

        from vbumper.config.load import load_config_file

        config = load_config_file(".vbump.yaml")
        self.assertEqual(config.flows["release"].variables, {"RELEASE_BRANCH": "master"})

    def test_set_wins_over_preserved_local_value_on_update(self):
        pathlib.Path(".vbump.yaml").write_text(
            "version: 3\n"
            "flows:\n"
            "  release:\n"
            "    variables:\n"
            "      RELEASE_BRANCH: master\n"
            "discoverers: []\n"
        )
        self.patch_global_config({"release": FlowDefinition(variables={"RELEASE_BRANCH": "main"})})

        result = self.invoke(
            ["flow", "add", "release", "--update", "--set", "RELEASE_BRANCH=trunk"]
        )
        self.assertEqual(result.exit_code, 0, result.output)

        from vbumper.config.load import load_config_file

        config = load_config_file(".vbump.yaml")
        self.assertEqual(config.flows["release"].variables, {"RELEASE_BRANCH": "trunk"})

    def test_set_default_writes_default_flow(self):
        pathlib.Path(".vbump.yaml").write_text("version: 3\ndiscoverers: []\n")
        self.patch_global_config({"release": FlowDefinition(name="Release")})

        result = self.invoke(["flow", "add", "release", "--set-default"])
        self.assertEqual(result.exit_code, 0, result.output)

        from vbumper.config.load import load_config_file

        config = load_config_file(".vbump.yaml")
        self.assertEqual(config.default_flow, "release")

    def test_malformed_set_is_an_error(self):
        pathlib.Path(".vbump.yaml").write_text("version: 3\ndiscoverers: []\n")
        self.patch_global_config({"release": FlowDefinition()})

        result = self.invoke(["flow", "add", "release", "--set", "NOVALUE"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("NAME=value", str(result.output) + str(result.exception))

    def test_reserved_variable_name_in_set_is_an_error(self):
        pathlib.Path(".vbump.yaml").write_text("version: 3\ndiscoverers: []\n")
        self.patch_global_config({"release": FlowDefinition()})

        result = self.invoke(["flow", "add", "release", "--set", "VERSION=1.2.3"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("reserved", str(result.output) + str(result.exception))

    def test_unknown_template_name_is_an_error(self):
        pathlib.Path(".vbump.yaml").write_text("version: 3\ndiscoverers: []\n")
        self.patch_global_config({"other": FlowDefinition()})

        result = self.invoke(["flow", "add", "release"])

        self.assertNotEqual(result.exit_code, 0)
        message = str(result.output) + str(result.exception)
        self.assertIn("release", message)
        self.assertIn("other", message)

    def test_dry_run_does_not_write_anything(self):
        original = "version: 3\ndiscoverers: []\n"
        pathlib.Path(".vbump.yaml").write_text(original)
        self.patch_global_config({"release": FlowDefinition(name="Release")})

        result = self.invoke(["-n", "flow", "add", "release"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path(".vbump.yaml").read_text(), original)
        self.assertIn("Would write", result.output)


if __name__ == "__main__":
    unittest.main()
