import unittest

from vbumper.core.containers.base import VersionContainer
from vbumper.core.containers.types import NO_SEMVER, Invalid, Mismatched, Unversioned, Versioned
from vbumper.core.exceptions import IncompatibleVersionsError
from vbumper.core.resolution import containers_to_update, resolve_common_version
from vbumper.core.semver import SemVer


class FakeContainer(VersionContainer):
    """A minimal in-memory `VersionContainer` for exercising resolution/apply logic without
    touching the filesystem."""

    def __init__(self, status, *, name="fake"):
        super().__init__(status=status)
        self.name = name
        self.write_calls = 0
        self.fail_write = False

    def describe(self) -> str:
        return self.name

    def write(self) -> None:
        self.write_calls += 1
        if self.fail_write:
            raise OSError("boom")


V123 = SemVer.parse("1.2.3")
V200 = SemVer.parse("2.0.0")


class TestResolveCommonVersion(unittest.TestCase):
    def test_no_containers_yields_none(self):
        self.assertIsNone(resolve_common_version([]))

    def test_all_unversioned_yields_none(self):
        containers = [FakeContainer(Unversioned()), FakeContainer(Unversioned())]
        self.assertIsNone(resolve_common_version(containers))

    def test_single_versioned_container_yields_its_version(self):
        containers = [FakeContainer(Versioned(value=V123))]
        self.assertEqual(resolve_common_version(containers), V123)

    def test_versioned_and_unversioned_agree(self):
        containers = [FakeContainer(Versioned(value=V123)), FakeContainer(Unversioned())]
        self.assertEqual(resolve_common_version(containers), V123)

    def test_agreeing_versioned_containers_yield_that_version(self):
        containers = [FakeContainer(Versioned(value=V123)), FakeContainer(Versioned(value=V123))]
        self.assertEqual(resolve_common_version(containers), V123)

    def test_disagreeing_versioned_containers_raise_by_default(self):
        containers = [FakeContainer(Versioned(value=V123)), FakeContainer(Versioned(value=V200))]
        with self.assertRaises(IncompatibleVersionsError):
            resolve_common_version(containers)

    def test_disagreeing_versioned_containers_pick_first_when_allowed(self):
        containers = [FakeContainer(Versioned(value=V200)), FakeContainer(Versioned(value=V123))]
        self.assertEqual(resolve_common_version(containers, allow_incompatible_versions=True), V200)

    def test_invalid_container_raises_by_default(self):
        containers = [FakeContainer(Versioned(value=V123)), FakeContainer(Invalid())]
        with self.assertRaises(IncompatibleVersionsError):
            resolve_common_version(containers)

    def test_invalid_container_ignored_when_allowed(self):
        containers = [FakeContainer(Versioned(value=V123)), FakeContainer(Invalid())]
        self.assertEqual(resolve_common_version(containers, allow_incompatible_versions=True), V123)

    def test_mismatched_container_raises_by_default(self):
        containers = [FakeContainer(Mismatched(copies=[V123, V200]))]
        with self.assertRaises(IncompatibleVersionsError):
            resolve_common_version(containers)

    def test_skip_unreadable_makes_invalid_containers_transparent(self):
        containers = [FakeContainer(Versioned(value=V123)), FakeContainer(Invalid())]
        # No allow_incompatible_versions needed: skip_unreadable_version_strings alone suffices.
        self.assertEqual(
            resolve_common_version(containers, skip_unreadable_version_strings=True), V123
        )

    def test_skip_unreadable_with_only_invalid_containers_yields_none(self):
        containers = [FakeContainer(Invalid()), FakeContainer(Mismatched(copies=[V123, V200]))]
        self.assertIsNone(resolve_common_version(containers, skip_unreadable_version_strings=True))


class TestContainersToUpdate(unittest.TestCase):
    def test_without_skip_flag_returns_everything(self):
        containers = [
            FakeContainer(Versioned(value=V123)),
            FakeContainer(Invalid()),
            FakeContainer(Mismatched(copies=[V123, V200])),
        ]
        self.assertEqual(containers_to_update(containers), containers)

    def test_skip_flag_excludes_invalid_and_mismatched(self):
        versioned = FakeContainer(Versioned(value=V123))
        unversioned = FakeContainer(Unversioned())
        invalid = FakeContainer(Invalid())
        mismatched = FakeContainer(Mismatched(copies=[V123, V200]))

        result = containers_to_update(
            [versioned, unversioned, invalid, mismatched],
            skip_unreadable_version_strings=True,
        )

        self.assertEqual(result, [versioned, unversioned])


class TestFakeContainerSanity(unittest.TestCase):
    """Guards the test double itself, since other suites build on it."""

    def test_set_status_then_write_marks_changed_and_calls_write(self):
        container = FakeContainer(Versioned(value=V123))
        container.set_status(Versioned(value=V200))
        self.assertTrue(container.has_changed)
        container.write()
        self.assertEqual(container.write_calls, 1)

    def test_unversioned_copy_marker_is_distinct_from_a_real_version(self):
        self.assertIsNot(NO_SEMVER, V123)


if __name__ == "__main__":
    unittest.main()
