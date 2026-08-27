import json
import os
import pathlib
import tempfile
import unittest

from vbumper.core.containers.types import Invalid, Unversioned, Versioned
from vbumper.core.files.builtins.npm import PackageJsonFileConfig
from vbumper.core.semver import SemVer


def _write(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


class PackageJsonDiscovererTestCase(unittest.TestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        previous_cwd = os.getcwd()
        os.chdir(tmp_dir.name)
        self.addCleanup(os.chdir, previous_cwd)

    def discover(self):
        discoverer = PackageJsonFileConfig().create_discoverer()
        return list(discoverer.discover())

    def test_finds_top_level_package_json_version(self):
        _write("package.json", json.dumps({"name": "example", "version": "1.2.3"}))

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))

    def test_finds_nested_package_json_files(self):
        _write("package.json", json.dumps({"version": "1.0.0"}))
        _write("packages/sub/package.json", json.dumps({"version": "2.0.0"}))

        containers = self.discover()
        self.assertEqual(len(containers), 2)
        versions = {container.status.value for container in containers}
        self.assertEqual(versions, {SemVer.parse("1.0.0"), SemVer.parse("2.0.0")})

    def test_missing_version_key_yields_no_container(self):
        _write("package.json", json.dumps({"name": "example"}))

        self.assertEqual(self.discover(), [])

    def test_non_string_version_yields_no_container(self):
        _write("package.json", json.dumps({"name": "example", "version": 123}))

        self.assertEqual(self.discover(), [])

    def test_empty_version_string_is_unversioned(self):
        _write("package.json", json.dumps({"version": ""}))

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Unversioned())

    def test_unparseable_version_is_invalid(self):
        _write("package.json", json.dumps({"version": "not-a-semver"}))

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0].status, Invalid)

    def test_invalid_json_yields_no_container(self):
        _write("package.json", "{not valid json")

        self.assertEqual(self.discover(), [])

    def test_ignores_files_not_named_package_json(self):
        _write("other.json", json.dumps({"version": "1.2.3"}))

        self.assertEqual(self.discover(), [])

    def test_write_back_preserves_other_keys_and_order(self):
        _write(
            "package.json",
            json.dumps(
                {"name": "example", "version": "1.2.3", "dependencies": {"foo": "^1.0.0"}},
                indent=2,
            )
            + "\n",
        )

        container = self.discover()[0]
        container.set_status(Versioned(value=SemVer.parse("1.3.0")))
        container.write()

        written = pathlib.Path("package.json").read_text()
        self.assertEqual(
            written,
            json.dumps(
                {"name": "example", "version": "1.3.0", "dependencies": {"foo": "^1.0.0"}},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        # Written file must still parse back with the same key order.
        self.assertEqual(list(json.loads(written).keys()), ["name", "version", "dependencies"])


if __name__ == "__main__":
    unittest.main()
