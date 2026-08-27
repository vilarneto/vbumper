import os
import pathlib
import tempfile
import textwrap
import unittest

from vbumper.core.containers.types import Invalid, Unversioned, Versioned
from vbumper.core.files.builtins.setuppy import SetupPyFileConfig
from vbumper.core.semver import SemVer


def _write(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


class SetupPyDiscovererTestCase(unittest.TestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        previous_cwd = os.getcwd()
        os.chdir(tmp_dir.name)
        self.addCleanup(os.chdir, previous_cwd)

    def discover(self):
        discoverer = SetupPyFileConfig().create_discoverer()
        return list(discoverer.discover())

    def test_finds_double_quoted_version(self):
        _write(
            "setup.py",
            """\
            from setuptools import setup

            setup(
                name="example",
                version="1.2.3",
            )
            """,
        )

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))

    def test_finds_single_quoted_version_without_trailing_comma(self):
        _write("setup.py", "version='1.2.3'\n")

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))

    def test_empty_version_string_is_unversioned(self):
        _write("setup.py", 'version="",\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Unversioned())

    def test_unparseable_version_is_invalid(self):
        _write("setup.py", 'version="not-a-semver",\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0].status, Invalid)

    def test_ignores_files_not_named_setup_py(self):
        _write("pyproject.toml", 'version="1.2.3"\n')

        self.assertEqual(self.discover(), [])

    def test_write_back_updates_only_the_version_value(self):
        _write(
            "setup.py",
            """\
            from setuptools import setup

            setup(
                name="example",
                version="1.2.3",
                description="demo",
            )
            """,
        )

        container = self.discover()[0]
        container.set_status(Versioned(value=SemVer.parse("1.3.0")))
        container.write()

        self.assertEqual(
            pathlib.Path("setup.py").read_text(),
            textwrap.dedent(
                """\
                from setuptools import setup

                setup(
                    name="example",
                    version="1.3.0",
                    description="demo",
                )
                """
            ),
        )


if __name__ == "__main__":
    unittest.main()
