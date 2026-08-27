import os
import pathlib
import tempfile
import textwrap
import unittest

from vbumper.core.containers.types import Invalid, Unversioned, Versioned
from vbumper.core.files.builtins.pyproject import PyProjectTomlFileConfig
from vbumper.core.semver import SemVer


def _write(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


class PyProjectTomlDiscovererTestCase(unittest.TestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        previous_cwd = os.getcwd()
        os.chdir(tmp_dir.name)
        self.addCleanup(os.chdir, previous_cwd)

    def discover(self):
        discoverer = PyProjectTomlFileConfig().create_discoverer()
        return list(discoverer.discover())

    def test_finds_top_level_pyproject_version(self):
        _write(
            "pyproject.toml",
            """\
            [project]
            name = "example"
            version = "1.2.3"
            """,
        )

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))

    def test_finds_nested_pyproject_files(self):
        _write("pyproject.toml", 'version = "1.0.0"\n')
        _write("sub/pkg/pyproject.toml", 'version = "2.0.0"\n')

        containers = self.discover()
        self.assertEqual(len(containers), 2)
        versions = {container.status.value for container in containers}
        self.assertEqual(versions, {SemVer.parse("1.0.0"), SemVer.parse("2.0.0")})

    def test_dynamic_version_yields_no_container(self):
        """`dynamic = ["version"]` means 'no versioning expected here' -- not the same as an
        unversioned container -- so this file must not be discovered at all."""

        _write(
            "pyproject.toml",
            """\
            [project]
            name = "example"
            dynamic = ["version"]
            """,
        )

        self.assertEqual(self.discover(), [])

    def test_empty_version_string_is_unversioned(self):
        _write("pyproject.toml", 'version = ""\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Unversioned())

    def test_unparseable_version_is_invalid(self):
        _write("pyproject.toml", 'version = "not-a-semver"\n')

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0].status, Invalid)

    def test_ignores_files_not_named_pyproject_toml(self):
        _write("setup.py", 'version = "1.2.3"\n')

        self.assertEqual(self.discover(), [])

    def test_write_back_updates_only_the_version_value(self):
        _write(
            "pyproject.toml",
            """\
            [project]
            name = "example"
            version = "1.2.3"
            description = "demo"
            """,
        )

        container = self.discover()[0]
        container.set_status(Versioned(value=SemVer.parse("1.3.0")))
        container.write()

        self.assertEqual(
            pathlib.Path("pyproject.toml").read_text(),
            textwrap.dedent(
                """\
                [project]
                name = "example"
                version = "1.3.0"
                description = "demo"
                """
            ),
        )


if __name__ == "__main__":
    unittest.main()
