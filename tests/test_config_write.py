import pathlib
import tempfile
import unittest

from vbumper.config.flow import FlowDefinition
from vbumper.config.load import load_config_file
from vbumper.config.write import dump_raw, load_raw_for_edit, set_default_flow, set_flow_entry


class TestLoadRawForEdit(unittest.TestCase):
    def test_missing_flows_and_default_flow_load_as_empty_mapping(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbump.yaml"
            path.write_text("version: 3\n")

            raw = load_raw_for_edit(path)

        self.assertEqual(raw["version"], 3)
        self.assertNotIn("flows", raw)


class TestSetFlowEntry(unittest.TestCase):
    def test_creates_flows_section_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbump.yaml"
            path.write_text("version: 3\n")
            raw = load_raw_for_edit(path)

            set_flow_entry(raw, "release", FlowDefinition(name="Release", pre_commands=["echo hi"]))
            dump_raw(raw, path)

            config = load_config_file(path)

        self.assertIn("release", config.flows)
        self.assertEqual(config.flows["release"].name, "Release")
        self.assertEqual(config.flows["release"].pre_commands, ["echo hi"])

    def test_preserves_comments_and_other_content(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbump.yaml"
            path.write_text(
                "# a hand-written comment\n"
                "version: 3\n"
                "flows:\n"
                "  # another comment, on an unrelated flow\n"
                "  other:\n"
                "    name: Other\n"
                "discoverers:\n"
                "  - type: pyproject-toml\n"
            )
            raw = load_raw_for_edit(path)

            set_flow_entry(raw, "release", FlowDefinition(name="Release"))
            dump_raw(raw, path)

            written = path.read_text()
            config = load_config_file(path)

        self.assertIn("# a hand-written comment", written)
        self.assertIn("# another comment, on an unrelated flow", written)
        self.assertEqual(config.flows["other"].name, "Other")
        self.assertEqual(config.flows["release"].name, "Release")
        self.assertEqual(len(config.discoverers), 1)

    def test_overwrites_an_existing_entry_of_the_same_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbump.yaml"
            path.write_text("version: 3\nflows:\n  release:\n    name: Old\n")
            raw = load_raw_for_edit(path)

            set_flow_entry(raw, "release", FlowDefinition(name="New"))
            dump_raw(raw, path)

            config = load_config_file(path)

        self.assertEqual(config.flows["release"].name, "New")

    def test_omits_default_valued_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbump.yaml"
            path.write_text("version: 3\n")
            raw = load_raw_for_edit(path)

            set_flow_entry(raw, "release", FlowDefinition())
            dump_raw(raw, path)

            written = path.read_text()

        self.assertNotIn("pre_commands", written)
        self.assertNotIn("post_commands", written)
        self.assertNotIn("variables", written)


class TestSetDefaultFlow(unittest.TestCase):
    def test_adds_default_flow_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbump.yaml"
            path.write_text("version: 3\nflows:\n  release:\n    name: Release\n")
            raw = load_raw_for_edit(path)

            set_default_flow(raw, "release")
            dump_raw(raw, path)

            config = load_config_file(path)

        self.assertEqual(config.default_flow, "release")

    def test_overwrites_an_existing_default_flow(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = pathlib.Path(tmp_dir) / ".vbump.yaml"
            path.write_text("version: 3\ndefault_flow: old\nflows:\n  new:\n    name: New\n")
            raw = load_raw_for_edit(path)

            set_default_flow(raw, "new")
            dump_raw(raw, path)

            config = load_config_file(path)

        self.assertEqual(config.default_flow, "new")


if __name__ == "__main__":
    unittest.main()
