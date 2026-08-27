import dataclasses
import unittest

from vbumper.core.containers.types import (
    NO_SEMVER,
    Invalid,
    Mismatched,
    NoSemVer,
    Unversioned,
    Versioned,
    resolve_status,
)
from vbumper.core.semver import SemVer


class TestNoSemVer(unittest.TestCase):
    def test_is_a_singleton_enum_member(self):
        self.assertIs(NO_SEMVER, NoSemVer.NO_SEMVER)
        self.assertIsInstance(NO_SEMVER, NoSemVer)


class TestStatusDataclasses(unittest.TestCase):
    def test_equality_by_value(self):
        v123 = SemVer.parse("1.2.3")
        v123_again = SemVer.parse("1.2.3")
        v124 = SemVer.parse("1.2.4")

        self.assertEqual(Versioned(value=v123), Versioned(value=v123_again))
        self.assertNotEqual(Versioned(value=v123), Versioned(value=v124))
        self.assertEqual(Unversioned(), Unversioned())
        self.assertEqual(Invalid(), Invalid())
        self.assertEqual(Mismatched(copies=[v123, NO_SEMVER]), Mismatched(copies=[v123, NO_SEMVER]))
        self.assertNotEqual(
            Mismatched(copies=[v123, NO_SEMVER]), Mismatched(copies=[NO_SEMVER, v123])
        )

    def test_distinct_status_kinds_are_never_equal(self):
        v123 = SemVer.parse("1.2.3")
        statuses = [Versioned(value=v123), Unversioned(), Invalid(), Mismatched(copies=[v123])]

        for i, a in enumerate(statuses):
            for j, b in enumerate(statuses):
                with self.subTest(a=a, b=b):
                    if i == j:
                        self.assertEqual(a, b)
                    else:
                        self.assertNotEqual(a, b)

    def test_are_frozen(self):
        v123 = SemVer.parse("1.2.3")

        with self.assertRaises(dataclasses.FrozenInstanceError):
            Versioned(value=v123).value = SemVer.parse("2.0.0")

    def test_are_keyword_only(self):
        v123 = SemVer.parse("1.2.3")

        with self.assertRaises(TypeError):
            Versioned(v123)
        with self.assertRaises(TypeError):
            Mismatched([v123])

    def test_are_hashable_for_set_and_dict_use(self):
        v123 = SemVer.parse("1.2.3")

        # A frozen dataclass is hashable by default as long as every field is hashable, which
        # matters for callers that want to dedupe or index statuses.
        self.assertEqual(len({Versioned(value=v123), Versioned(value=v123)}), 1)
        self.assertEqual(len({Unversioned(), Unversioned()}), 1)


class TestResolveStatus(unittest.TestCase):
    def test_all_unversioned_copies_yield_unversioned(self):
        self.assertEqual(resolve_status([NO_SEMVER, NO_SEMVER]), Unversioned())
        self.assertEqual(resolve_status([]), Unversioned())

    def test_any_unparseable_copy_yields_invalid_and_drops_no_raw_string(self):
        v123 = SemVer.parse("1.2.3")

        self.assertEqual(resolve_status([None]), Invalid())
        self.assertEqual(resolve_status([v123, None]), Invalid())
        self.assertEqual(resolve_status([None, NO_SEMVER]), Invalid())
        # Nothing about the invalid copy's raw content leaks into the status.
        self.assertEqual(dataclasses.fields(Invalid()), ())

    def test_single_versioned_copy_yields_versioned(self):
        v123 = SemVer.parse("1.2.3")
        self.assertEqual(resolve_status([v123]), Versioned(value=v123))

    def test_agreeing_versioned_copies_yield_versioned(self):
        v123 = SemVer.parse("1.2.3")
        v123_again = SemVer.parse("1.2.3")
        self.assertEqual(resolve_status([v123, v123_again]), Versioned(value=v123))

    def test_versioned_plus_unversioned_copies_conflate_to_versioned(self):
        v123 = SemVer.parse("1.2.3")
        self.assertEqual(resolve_status([v123, NO_SEMVER, v123]), Versioned(value=v123))
        self.assertEqual(resolve_status([NO_SEMVER, v123]), Versioned(value=v123))

    def test_disagreeing_versioned_copies_yield_mismatched_preserving_all_copies(self):
        v123 = SemVer.parse("1.2.3")
        v200 = SemVer.parse("2.0.0")

        self.assertEqual(resolve_status([v123, v200]), Mismatched(copies=[v123, v200]))
        self.assertEqual(
            resolve_status([v123, NO_SEMVER, v200]),
            Mismatched(copies=[v123, NO_SEMVER, v200]),
        )

    def test_invalid_takes_precedence_over_mismatch(self):
        v123 = SemVer.parse("1.2.3")
        v200 = SemVer.parse("2.0.0")
        self.assertEqual(resolve_status([v123, v200, None]), Invalid())


if __name__ == "__main__":
    unittest.main()
