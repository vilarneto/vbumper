import unittest

from vbumper.cli.sync import _candidate_pool, _in_scope
from vbumper.core.containers.base import VersionContainer
from vbumper.core.containers.types import NO_SEMVER, Invalid, Mismatched, Unversioned, Versioned
from vbumper.core.semver import SemVer

V100 = SemVer.parse("1.0.0")
V123 = SemVer.parse("1.2.3")
V200 = SemVer.parse("2.0.0")


class FakeContainer(VersionContainer):
    """A minimal in-memory `VersionContainer`, mirroring `test_resolution.py`'s helper."""

    def __init__(self, status, *, name="fake"):
        super().__init__(status=status)
        self.name = name

    def describe(self) -> str:
        return self.name

    def write(self) -> None:
        pass


class TestCandidatePool(unittest.TestCase):
    def test_collects_versioned_values(self):
        containers = [FakeContainer(Versioned(value=V123)), FakeContainer(Versioned(value=V200))]
        pool = _candidate_pool(containers, include_mismatched=False)
        self.assertCountEqual(pool, [V123, V200])

    def test_ignores_unversioned_and_invalid(self):
        containers = [FakeContainer(Unversioned()), FakeContainer(Invalid())]
        self.assertEqual(_candidate_pool(containers, include_mismatched=False), [])

    def test_ignores_mismatched_copies_by_default(self):
        containers = [FakeContainer(Mismatched(copies=[V123, V200]))]
        self.assertEqual(_candidate_pool(containers, include_mismatched=False), [])

    def test_include_mismatched_folds_in_its_semver_copies_only(self):
        containers = [FakeContainer(Mismatched(copies=[V123, V200, NO_SEMVER]))]
        pool = _candidate_pool(containers, include_mismatched=True)
        self.assertCountEqual(pool, [V123, V200])

    def test_max_of_pool_uses_semver_precedence(self):
        containers = [
            FakeContainer(Versioned(value=V100)),
            FakeContainer(Versioned(value=V200)),
            FakeContainer(Versioned(value=V123)),
        ]
        pool = _candidate_pool(containers, include_mismatched=False)
        self.assertEqual(max(pool), V200)


class TestInScope(unittest.TestCase):
    def test_versioned_and_unversioned_always_in_scope(self):
        self.assertTrue(
            _in_scope(
                FakeContainer(Versioned(value=V123)),
                include_mismatched=False,
                fix_invalid=False,
            )
        )
        self.assertTrue(
            _in_scope(FakeContainer(Unversioned()), include_mismatched=False, fix_invalid=False)
        )

    def test_mismatched_gated_by_flag(self):
        container = FakeContainer(Mismatched(copies=[V123, V200]))
        self.assertFalse(_in_scope(container, include_mismatched=False, fix_invalid=False))
        self.assertTrue(_in_scope(container, include_mismatched=True, fix_invalid=False))

    def test_invalid_gated_by_flag(self):
        container = FakeContainer(Invalid())
        self.assertFalse(_in_scope(container, include_mismatched=False, fix_invalid=False))
        self.assertTrue(_in_scope(container, include_mismatched=False, fix_invalid=True))


if __name__ == "__main__":
    unittest.main()
