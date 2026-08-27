import os
import pathlib
import tempfile
import unittest

from vbumper.core.containers.types import Invalid, Unversioned, Versioned
from vbumper.core.files.builtins.infoplist import InfoPlistFileConfig
from vbumper.core.semver import SemVer

_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
    ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    '<plist version="1.0">\n'
    "<dict>\n"
)


def _plist(version_string: str, *, header: str = _HEADER) -> str:
    return (
        header + "\t<key>CFBundleShortVersionString</key>\n"
        f"\t<string>{version_string}</string>\n"
        "</dict>\n"
        "</plist>\n"
    )


def _write(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


class InfoPlistDiscovererTestCase(unittest.TestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        previous_cwd = os.getcwd()
        os.chdir(tmp_dir.name)
        self.addCleanup(os.chdir, previous_cwd)

    def discover(self):
        discoverer = InfoPlistFileConfig().create_discoverer()
        return list(discoverer.discover())

    def test_finds_version_in_well_formed_info_plist(self):
        _write("Info.plist", _plist("1.2.3"))

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))

    def test_finds_nested_info_plist_files(self):
        _write("Info.plist", _plist("1.0.0"))
        _write("App/Resources/Info.plist", _plist("2.0.0"))

        containers = self.discover()
        self.assertEqual(len(containers), 2)
        versions = {container.status.value for container in containers}
        self.assertEqual(versions, {SemVer.parse("1.0.0"), SemVer.parse("2.0.0")})

    def test_missing_exact_header_yields_no_container(self):
        # Same key, but not preceded by the exact expected 4-line XML header.
        _write(
            "Info.plist",
            "<?xml version='1.0'?>\n<dict>\n<key>CFBundleShortVersionString</key>\n"
            "<string>1.2.3</string>\n</dict>\n",
        )

        self.assertEqual(self.discover(), [])

    def test_empty_version_string_is_unversioned(self):
        _write("Info.plist", _plist(""))

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Unversioned())

    def test_unparseable_version_is_invalid(self):
        _write("Info.plist", _plist("not-a-semver"))

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0].status, Invalid)

    def test_ignores_files_not_named_info_plist(self):
        _write("Other.plist", _plist("1.2.3"))

        self.assertEqual(self.discover(), [])

    def test_write_back_updates_only_the_version_value(self):
        _write("Info.plist", _plist("1.2.3"))

        container = self.discover()[0]
        container.set_status(Versioned(value=SemVer.parse("1.3.0")))
        container.write()

        self.assertEqual(pathlib.Path("Info.plist").read_text(), _plist("1.3.0"))


if __name__ == "__main__":
    unittest.main()
