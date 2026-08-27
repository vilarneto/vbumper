import os
import pathlib
import tempfile
import textwrap
import unittest

from vbumper.core.containers.types import Invalid, Unversioned, Versioned
from vbumper.core.files.builtins.pythonversion import PythonVersionFileConfig
from vbumper.core.semver import SemVer


def _write(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


class PythonVersionDiscovererTestCase(unittest.TestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        previous_cwd = os.getcwd()
        os.chdir(tmp_dir.name)
        self.addCleanup(os.chdir, previous_cwd)

    def discover(self):
        discoverer = PythonVersionFileConfig().create_discoverer()
        return list(discoverer.discover())

    def test_finds_version_in_init_py(self):
        _write("pkg/__init__.py", '__version__ = "1.2.3"\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))

    def test_finds_version_in_underscore_version_py(self):
        _write("pkg/_version.py", "__version__ = '2.0.0'\n")

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("2.0.0")))

    def test_finds_version_in_version_py(self):
        _write("pkg/version.py", '__version__ = "3.1.4"\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("3.1.4")))

    def test_empty_version_string_is_unversioned(self):
        _write("pkg/__init__.py", '__version__ = ""\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Unversioned())

    def test_unparseable_version_is_invalid(self):
        _write("pkg/__init__.py", '__version__ = "not-a-semver"\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0].status, Invalid)

    def test_ignores_other_python_files(self):
        _write("pkg/other.py", '__version__ = "1.2.3"\n')

        self.assertEqual(self.discover(), [])

    def test_write_back_updates_only_the_version_value(self):
        _write(
            "pkg/__init__.py",
            """\
            \"\"\"Package docstring.\"\"\"

            __version__ = "1.2.3"
            """,
        )

        container = self.discover()[0]
        container.set_status(Versioned(value=SemVer.parse("1.3.0")))
        container.write()

        self.assertEqual(
            pathlib.Path("pkg/__init__.py").read_text(),
            textwrap.dedent(
                """\
                \"\"\"Package docstring.\"\"\"

                __version__ = "1.3.0"
                """
            ),
        )


if __name__ == "__main__":
    unittest.main()
