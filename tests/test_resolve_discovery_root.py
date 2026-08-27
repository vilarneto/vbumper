import pathlib
import tempfile
import unittest

from vbumper.core.exceptions import ConfigurationError
from vbumper.core.files.discoverer import resolve_discovery_root


class ResolveDiscoveryRootTestCase(unittest.TestCase):
    def test_none_defaults_to_current_directory(self):
        self.assertEqual(resolve_discovery_root(None), pathlib.Path("."))

    def test_directory_is_returned_as_is(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = pathlib.Path(tmp_dir)
            self.assertEqual(resolve_discovery_root(dir_path), dir_path)

    def test_raises_when_given_a_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pathlib.Path(tmp_dir) / "some_file.txt"
            file_path.write_text("contents")

            with self.assertRaises(ConfigurationError):
                resolve_discovery_root(file_path)

    def test_raises_when_given_a_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = pathlib.Path(tmp_dir) / "does-not-exist"

            with self.assertRaises(ConfigurationError):
                resolve_discovery_root(missing_path)


if __name__ == "__main__":
    unittest.main()
