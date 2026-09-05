import unittest
from unittest import mock

from vbumper.config.global_config import GlobalConfig, find_global_config_path, load_global_config
from vbumper.core.exceptions import ConfigurationError


class TestFindGlobalConfigPath(unittest.TestCase):
    def test_missing_file_returns_none(self, tmp_path=None):
        with mock.patch("pathlib.Path.is_file", return_value=False):
            self.assertIsNone(find_global_config_path())

    def test_present_file_returns_its_path(self):
        with mock.patch("pathlib.Path.is_file", return_value=True):
            path = find_global_config_path()
        self.assertEqual(path.name, ".vbumpconfig.yaml")


class TestLoadGlobalConfig(unittest.TestCase):
    def test_missing_file_is_treated_as_no_flows(self):
        with mock.patch("vbumper.config.global_config.find_global_config_path", return_value=None):
            config = load_global_config()

        self.assertEqual(config, GlobalConfig.empty())
        self.assertEqual(config.flows, {})

    def test_valid_file_is_parsed(self, tmp_path=None):
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbumpconfig.yaml"
            path.write_text(
                "version: 3\n"
                "flows:\n"
                "  release:\n"
                "    name: release\n"
                "    pre_commands:\n"
                "      - echo hi\n"
            )
            with mock.patch(
                "vbumper.config.global_config.find_global_config_path", return_value=path
            ):
                config = load_global_config()

        self.assertIn("release", config.flows)
        self.assertEqual(config.flows["release"].pre_commands, ["echo hi"])

    def test_wrong_version_raises_configuration_error(self):
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbumpconfig.yaml"
            path.write_text("version: 1\n")
            with mock.patch(
                "vbumper.config.global_config.find_global_config_path", return_value=path
            ):
                with self.assertRaises(ConfigurationError):
                    load_global_config()

    def test_malformed_yaml_raises_configuration_error(self):
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbumpconfig.yaml"
            path.write_text("flows: [this is not valid: yaml\n")
            with mock.patch(
                "vbumper.config.global_config.find_global_config_path", return_value=path
            ):
                with self.assertRaises(ConfigurationError):
                    load_global_config()

    def test_a_global_flow_may_not_set_recall(self):
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbumpconfig.yaml"
            path.write_text("version: 3\nflows:\n  release:\n    recall: other\n")
            with mock.patch(
                "vbumper.config.global_config.find_global_config_path", return_value=path
            ):
                with self.assertRaises(ConfigurationError):
                    load_global_config()


if __name__ == "__main__":
    unittest.main()
