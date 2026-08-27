import pathlib

from test_cli_bump import BumpCLITestCase, _write_config, _write_version_file

from vbumper.cli import sync  # imported for its command-registration side effect
from vbumper.cli._grp import root_grp


class TestSyncBasic(BumpCLITestCase):
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
        _write_version_file("b.txt", 'version = "2.0.0"\n')

    def test_confirming_yes_writes_the_highest_version(self):
        result = self.runner.invoke(root_grp, ["sync"], input="y\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Proceed?", result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "2.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "2.0.0"\n')

    def test_declining_leaves_files_untouched(self):
        result = self.runner.invoke(root_grp, ["sync"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "2.0.0"\n')

    def test_no_input_skips_the_prompt(self):
        result = self.invoke(["sync", "--no-input"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("Proceed?", result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "2.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "2.0.0"\n')

    def test_dry_run_previews_without_prompting_or_writing(self):
        result = self.invoke(["--dry-run", "sync"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("Proceed?", result.output)
        self.assertIn("Would update", result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "2.0.0"\n')

    def test_already_in_sync_is_a_no_op(self):
        _write_version_file("a.txt", 'version = "2.0.0"\n')
        result = self.invoke(["sync", "--no-input"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Already in sync.", result.output)


class TestSyncUnversioned(BumpCLITestCase):
    def test_populates_unversioned_containers_too(self):
        _write_config(
            """\
            version: 3
            discoverers:
              - type: file-regexp
                include: "*.txt"
                version: 'version = "(?P<version>[^"]*)"'
            """
        )
        _write_version_file("a.txt", 'version = "1.5.0"\n')
        _write_version_file("b.txt", 'version = ""\n')

        result = self.invoke(["sync", "--no-input"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "1.5.0"\n')


class TestSyncInvalid(BumpCLITestCase):
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

    def test_invalid_left_untouched_without_flag(self):
        result = self.invoke(["sync", "--no-input"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "not-semver"\n')

    def test_fix_invalid_overwrites_it(self):
        result = self.invoke(["sync", "--no-input", "--fix-invalid"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(pathlib.Path("a.txt").read_text(), 'version = "1.0.0"\n')
        self.assertEqual(pathlib.Path("b.txt").read_text(), 'version = "1.0.0"\n')


class TestSyncNoBaseVersion(BumpCLITestCase):
    def test_fails_when_nothing_is_versioned(self):
        _write_config(
            """\
            version: 3
            discoverers:
              - type: file-regexp
                include: "*.txt"
                version: 'version = "(?P<version>[^"]*)"'
            """
        )
        _write_version_file("a.txt", 'version = ""\n')

        result = self.invoke(["sync", "--no-input"])
        self.assertNotEqual(result.exit_code, 0)
