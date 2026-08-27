import os
import pathlib
import tempfile
import unittest

from vbumper.core.containers.types import Invalid, Mismatched, Unversioned, Versioned
from vbumper.core.files.builtins.pbxproj import PBXProjFileConfig
from vbumper.core.semver import SemVer

_HEADER = "// !$*UTF8*$!\n"


def _write(relative_path: str, contents: str) -> None:
    path = pathlib.Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def _pbxproj(*targets: tuple[str, str, str]) -> str:
    """Assemble a minimal but structurally faithful `project.pbxproj` -- one combined
    `PBXNativeTarget`/`XCConfigurationList`/`XCBuildConfiguration` section holding every target's
    entries, exactly like a real Xcode-generated file (which never repeats a section header),
    from the three fragments each `_target(...)` call returns."""

    targets_body = "".join(fragment[0] for fragment in targets)
    config_lists_body = "".join(fragment[1] for fragment in targets)
    build_configs_body = "".join(fragment[2] for fragment in targets)

    return (
        _HEADER
        + "/* Begin PBXNativeTarget section */\n"
        + targets_body
        + "/* End PBXNativeTarget section */\n"
        + "/* Begin XCConfigurationList section */\n"
        + config_lists_body
        + "/* End XCConfigurationList section */\n"
        + "/* Begin XCBuildConfiguration section */\n"
        + build_configs_body
        + "/* End XCBuildConfiguration section */\n"
    )


def _target(
    target_uuid: str,
    name: str,
    config_list_uuid: str,
    *,
    debug_uuid: str,
    release_uuid: str,
    debug_version: str | None = "1.2.3",
    release_version: str | None = "1.2.3",
) -> tuple[str, str, str]:
    """Return `(target_fragment, config_list_fragment, build_configs_fragment)`, each meant to be
    concatenated with other targets' same-kind fragments into one combined section by
    `_pbxproj`."""

    def _config_block(config_uuid: str, config_name: str, version: str | None) -> str:
        version_line = f"\t\t\t\tMARKETING_VERSION = {version};\n" if version is not None else ""
        return (
            f"\t\t{config_uuid} /* {config_name} */ = {{\n"
            "\t\t\tisa = XCBuildConfiguration;\n"
            "\t\t\tbuildSettings = {\n"
            f"{version_line}"
            '\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";\n'
            "\t\t\t};\n"
            f"\t\t\tname = {config_name};\n"
            "\t\t};\n"
        )

    target_fragment = (
        f"\t\t{target_uuid} /* {name} */ = {{\n"
        "\t\t\tisa = PBXNativeTarget;\n"
        f"\t\t\tbuildConfigurationList = {config_list_uuid} /* Build configuration list */;\n"
        f"\t\t\tname = {name};\n"
        "\t\t};\n"
    )
    config_list_fragment = (
        f"\t\t{config_list_uuid} /* Build configuration list */ = {{\n"
        "\t\t\tisa = XCConfigurationList;\n"
        "\t\t\tbuildConfigurations = (\n"
        f"\t\t\t\t{debug_uuid} /* Debug */,\n"
        f"\t\t\t\t{release_uuid} /* Release */,\n"
        "\t\t\t);\n"
        "\t\t\tdefaultConfigurationName = Release;\n"
        "\t\t};\n"
    )
    build_configs_fragment = _config_block(debug_uuid, "Debug", debug_version) + _config_block(
        release_uuid, "Release", release_version
    )

    return target_fragment, config_list_fragment, build_configs_fragment


class PBXProjDiscovererTestCase(unittest.TestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        previous_cwd = os.getcwd()
        os.chdir(tmp_dir.name)
        self.addCleanup(os.chdir, previous_cwd)

    def discover(self):
        discoverer = PBXProjFileConfig().create_discoverer()
        return list(discoverer.discover())

    def test_finds_one_container_per_target(self):
        content = _pbxproj(
            _target(
                "AAAAAAAAAAAAAAAAAAAAAAAA",
                "App",
                "BBBBBBBBBBBBBBBBBBBBBBBB",
                debug_uuid="CCCCCCCCCCCCCCCCCCCCCCCC",
                release_uuid="DDDDDDDDDDDDDDDDDDDDDDDD",
            )
        )
        _write("App.xcodeproj/project.pbxproj", content)

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))
        self.assertIn("App", containers[0].describe())

    def test_ignores_pbxproj_without_utf8_header(self):
        content = _pbxproj(
            _target(
                "AAAAAAAAAAAAAAAAAAAAAAAA",
                "App",
                "BBBBBBBBBBBBBBBBBBBBBBBB",
                debug_uuid="CCCCCCCCCCCCCCCCCCCCCCCC",
                release_uuid="DDDDDDDDDDDDDDDDDDDDDDDD",
            )
        ).removeprefix(_HEADER)
        _write("App.xcodeproj/project.pbxproj", content)

        self.assertEqual(self.discover(), [])

    def test_two_targets_are_two_independent_containers(self):
        content = _pbxproj(
            _target(
                "A0000000000000000000000A",
                "App",
                "B0000000000000000000000B",
                debug_uuid="C0000000000000000000000C",
                release_uuid="D0000000000000000000000D",
                debug_version="1.0.0",
                release_version="1.0.0",
            ),
            _target(
                "A1111111111111111111111A",
                "AppTests",
                "B1111111111111111111111B",
                debug_uuid="C1111111111111111111111C",
                release_uuid="D1111111111111111111111D",
                debug_version="2.0.0",
                release_version="2.0.0",
            ),
        )
        _write("App.xcodeproj/project.pbxproj", content)

        containers = self.discover()
        self.assertEqual(len(containers), 2)
        statuses = {c.describe(): c.status for c in containers}
        app_status = next(v for k, v in statuses.items() if '"App"' in k)
        tests_status = next(v for k, v in statuses.items() if '"AppTests"' in k)
        self.assertEqual(app_status, Versioned(value=SemVer.parse("1.0.0")))
        self.assertEqual(tests_status, Versioned(value=SemVer.parse("2.0.0")))

    def test_mismatched_copies_within_one_target(self):
        content = _pbxproj(
            _target(
                "AAAAAAAAAAAAAAAAAAAAAAAA",
                "App",
                "BBBBBBBBBBBBBBBBBBBBBBBB",
                debug_uuid="CCCCCCCCCCCCCCCCCCCCCCCC",
                release_uuid="DDDDDDDDDDDDDDDDDDDDDDDD",
                debug_version="1.0.0",
                release_version="1.1.0",
            )
        )
        _write("App.xcodeproj/project.pbxproj", content)

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0].status, Mismatched)

    def test_invalid_version_copy(self):
        content = _pbxproj(
            _target(
                "AAAAAAAAAAAAAAAAAAAAAAAA",
                "App",
                "BBBBBBBBBBBBBBBBBBBBBBBB",
                debug_uuid="CCCCCCCCCCCCCCCCCCCCCCCC",
                release_uuid="DDDDDDDDDDDDDDDDDDDDDDDD",
                debug_version="not-a-semver",
            )
        )
        _write("App.xcodeproj/project.pbxproj", content)

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0].status, Invalid)

    def test_blank_copy_is_unversioned_and_conflated_with_versioned_sibling(self):
        content = _pbxproj(
            _target(
                "AAAAAAAAAAAAAAAAAAAAAAAA",
                "App",
                "BBBBBBBBBBBBBBBBBBBBBBBB",
                debug_uuid="CCCCCCCCCCCCCCCCCCCCCCCC",
                release_uuid="DDDDDDDDDDDDDDDDDDDDDDDD",
                debug_version="",
                release_version="1.2.3",
            )
        )
        _write("App.xcodeproj/project.pbxproj", content)

        containers = self.discover()
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].status, Versioned(value=SemVer.parse("1.2.3")))

    def test_target_with_no_marketing_version_at_all_is_not_a_container(self):
        content = _pbxproj(
            _target(
                "AAAAAAAAAAAAAAAAAAAAAAAA",
                "App",
                "BBBBBBBBBBBBBBBBBBBBBBBB",
                debug_uuid="CCCCCCCCCCCCCCCCCCCCCCCC",
                release_uuid="DDDDDDDDDDDDDDDDDDDDDDDD",
                debug_version=None,
                release_version=None,
            )
        )
        _write("App.xcodeproj/project.pbxproj", content)

        self.assertEqual(self.discover(), [])

    def test_write_back_updates_all_copies_of_the_target(self):
        content = _pbxproj(
            _target(
                "AAAAAAAAAAAAAAAAAAAAAAAA",
                "App",
                "BBBBBBBBBBBBBBBBBBBBBBBB",
                debug_uuid="CCCCCCCCCCCCCCCCCCCCCCCC",
                release_uuid="DDDDDDDDDDDDDDDDDDDDDDDD",
            )
        )
        _write("App.xcodeproj/project.pbxproj", content)

        container = self.discover()[0]
        container.set_status(Versioned(value=SemVer.parse("1.3.0")))
        container.write()

        written = pathlib.Path("App.xcodeproj/project.pbxproj").read_text()
        self.assertEqual(written.count("MARKETING_VERSION = 1.3.0;"), 2)
        self.assertNotIn("1.2.3", written)

    def test_write_back_does_not_clobber_a_sibling_targets_already_written_version(self):
        content = _pbxproj(
            _target(
                "A0000000000000000000000A",
                "App",
                "B0000000000000000000000B",
                debug_uuid="C0000000000000000000000C",
                release_uuid="D0000000000000000000000D",
                debug_version="1.0.0",
                release_version="1.0.0",
            ),
            _target(
                "A1111111111111111111111A",
                "AppTests",
                "B1111111111111111111111B",
                debug_uuid="C1111111111111111111111C",
                release_uuid="D1111111111111111111111D",
                debug_version="1.0.0",
                release_version="1.0.0",
            ),
        )
        _write("App.xcodeproj/project.pbxproj", content)

        containers = self.discover()
        for container in containers:
            container.set_status(Versioned(value=SemVer.parse("2.0.0")))
        for container in containers:
            container.write()

        written = pathlib.Path("App.xcodeproj/project.pbxproj").read_text()
        self.assertEqual(written.count("MARKETING_VERSION = 2.0.0;"), 4)
        self.assertNotIn("1.0.0", written)


if __name__ == "__main__":
    unittest.main()
