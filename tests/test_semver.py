import dataclasses
import itertools
import unittest

from vbumper.core.semver import SemVer, bump_trailing_number


# noinspection PyDataclass,PyTypeChecker,PyStatementEffect
class TestSemVer(unittest.TestCase):
    def test_parse_valid_core_versions(self):
        cases = [
            ("0.0.0", 0, 0, 0, None, None),
            ("1.2.3", 1, 2, 3, None, None),
            ("10.20.30", 10, 20, 30, None, None),
            ("1.0.0-alpha", 1, 0, 0, "alpha", None),
            ("1.0.0-alpha.1", 1, 0, 0, "alpha.1", None),
            ("1.0.0-0.3.7", 1, 0, 0, "0.3.7", None),
            ("1.0.0-x.7.z.92", 1, 0, 0, "x.7.z.92", None),
            ("1.0.0+build", 1, 0, 0, None, "build"),
            ("1.0.0+build.1", 1, 0, 0, None, "build.1"),
            ("1.0.0-alpha+build.1", 1, 0, 0, "alpha", "build.1"),
            ("1.0.0-alpha.1+build.5", 1, 0, 0, "alpha.1", "build.5"),
        ]

        for text, major, minor, patch, prerelease, build in cases:
            with self.subTest(text=text):
                version = SemVer.parse(text)
                self.assertEqual(version.major, major)
                self.assertEqual(version.minor, minor)
                self.assertEqual(version.patch, patch)
                self.assertEqual(version.prerelease, prerelease)
                self.assertEqual(version.build, build)

    def test_str_round_trips_valid_versions(self):
        cases = [
            "0.0.0",
            "1.2.3",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-0.3.7",
            "1.0.0-x.7.z.92",
            "1.0.0+build",
            "1.0.0+build.1",
            "1.0.0-alpha+build.1",
            "1.0.0-alpha.1+build.5",
        ]

        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(str(SemVer.parse(text)), text)

    def test_repr_is_parse_expression(self):
        version = SemVer.parse("1.2.3-alpha.1+build.5")
        self.assertEqual(
            repr(version),
            "SemVer.parse('1.2.3-alpha.1+build.5')",
        )

    def test_constructor_accepts_valid_values(self):
        self.assertEqual(str(SemVer(1, 2, 3)), "1.2.3")
        self.assertEqual(str(SemVer(1, 2, 3, "alpha.1")), "1.2.3-alpha.1")
        self.assertEqual(str(SemVer(1, 2, 3, build="abc.123")), "1.2.3+abc.123")
        self.assertEqual(
            str(SemVer(1, 2, 3, "alpha.1", "abc.123")),
            "1.2.3-alpha.1+abc.123",
        )

    def test_parse_rejects_invalid_versions(self):
        invalid = [
            "",
            "1",
            "1.2",
            "1.2.3.4",
            "v1.2.3",
            "1.2.3v",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "-1.2.3",
            "1.-2.3",
            "1.2.-3",
            "1.2.3-",
            "1.2.3+",
            "1.2.3-alpha..beta",
            "1.2.3-alpha.",
            "1.2.3-.alpha",
            "1.2.3-alpha_1",
            "1.2.3-alpha+",
            "1.2.3+build.",
            "1.2.3+.build",
            "1.2.3+build..1",
            "1.2.3-01",
            "1.2.3-alpha.01",
            "1.2.3-001.alpha",
            "1.2.3-alpha+build_1",
            "1.2.3 alpha",
            " 1.2.3",
            "1.2.3 ",
            "1.2.3\n",
        ]

        for text in invalid:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    SemVer.parse(text)

    def test_constructor_rejects_invalid_values(self):
        invalid_args = [
            (-1, 0, 0, None, None),
            (0, -1, 0, None, None),
            (0, 0, -1, None, None),
            (True, 0, 0, None, None),
            (0, False, 0, None, None),
            (0, 0, True, None, None),
            (1, 2, 3, "", None),
            (1, 2, 3, ".", None),
            (1, 2, 3, "alpha..beta", None),
            (1, 2, 3, "01", None),
            (1, 2, 3, "alpha.01", None),
            (1, 2, 3, "alpha_1", None),
            (1, 2, 3, None, ""),
            (1, 2, 3, None, "."),
            (1, 2, 3, None, "build..1"),
            (1, 2, 3, None, "build_1"),
        ]

        for args in invalid_args:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    SemVer(*args)

    def test_immutable(self):
        version = SemVer.parse("1.2.3")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            version.major = 2

    def test_ordering_semver_spec_example(self):
        ordered = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]

        versions = [SemVer.parse(text) for text in ordered]

        self.assertEqual(sorted(reversed(versions)), versions)

        for lower, higher in itertools.pairwise(versions):
            with self.subTest(lower=lower, higher=higher):
                self.assertLess(lower, higher)
                self.assertLessEqual(lower, higher)
                self.assertGreater(higher, lower)
                self.assertGreaterEqual(higher, lower)

    def test_core_version_ordering(self):
        self.assertLess(SemVer.parse("1.0.0"), SemVer.parse("2.0.0"))
        self.assertLess(SemVer.parse("1.1.0"), SemVer.parse("1.2.0"))
        self.assertLess(SemVer.parse("1.1.1"), SemVer.parse("1.1.2"))

    def test_release_has_higher_precedence_than_prerelease(self):
        self.assertLess(SemVer.parse("1.0.0-alpha"), SemVer.parse("1.0.0"))
        self.assertGreater(SemVer.parse("1.0.0"), SemVer.parse("1.0.0-alpha"))

    def test_numeric_prerelease_identifiers_sort_before_non_numeric(self):
        self.assertLess(SemVer.parse("1.0.0-999"), SemVer.parse("1.0.0-alpha"))
        self.assertLess(SemVer.parse("1.0.0-alpha.9"), SemVer.parse("1.0.0-alpha.x"))

    def test_numeric_prerelease_identifiers_compare_numerically(self):
        self.assertLess(SemVer.parse("1.0.0-alpha.2"), SemVer.parse("1.0.0-alpha.10"))

    def test_longer_prerelease_wins_when_common_prefix_equal(self):
        self.assertLess(SemVer.parse("1.0.0-alpha"), SemVer.parse("1.0.0-alpha.1"))
        self.assertLess(SemVer.parse("1.0.0-alpha.1"), SemVer.parse("1.0.0-alpha.1.1"))

    def test_build_metadata_does_not_affect_equality_or_ordering(self):
        left = SemVer.parse("1.0.0+abc")
        right = SemVer.parse("1.0.0+xyz")

        self.assertEqual(left, right)
        self.assertFalse(left < right)
        self.assertFalse(right < left)
        self.assertEqual(hash(left), hash(right))

    def test_build_metadata_does_not_affect_prerelease_ordering(self):
        left = SemVer.parse("1.0.0-alpha+abc")
        right = SemVer.parse("1.0.0-alpha+xyz")

        self.assertEqual(left, right)
        self.assertFalse(left < right)
        self.assertFalse(right < left)

    def test_is_identical_to_includes_build_metadata(self):
        self.assertTrue(
            SemVer.parse("1.2.3-alpha+abc").is_identical_to(SemVer.parse("1.2.3-alpha+abc"))
        )

        self.assertFalse(
            SemVer.parse("1.2.3-alpha+abc").is_identical_to(SemVer.parse("1.2.3-alpha+xyz"))
        )

    def test_comparison_with_unrelated_type(self):
        version = SemVer.parse("1.2.3")

        self.assertNotEqual(version, "1.2.3")

        with self.assertRaises(TypeError):
            version < "1.2.3"

        with self.assertRaises(TypeError):
            version > "1.2.3"

    def test_copy_without_changes_returns_equal_instance(self):
        version = SemVer.parse("1.2.3-alpha+build.1")
        copied = version.copy()

        self.assertEqual(copied, version)
        self.assertTrue(copied.is_identical_to(version))
        self.assertIsNot(copied, version)

    def test_copy_changes_core_fields(self):
        version = SemVer.parse("1.2.3-alpha+build.1")

        self.assertEqual(
            str(version.copy(major=2, minor=0, patch=0)),
            "2.0.0-alpha+build.1",
        )

    def test_copy_changes_prerelease_and_build(self):
        version = SemVer.parse("1.2.3-alpha+build.1")

        self.assertEqual(
            str(version.copy(prerelease="beta.2", build="build.2")),
            "1.2.3-beta.2+build.2",
        )

    def test_copy_clears_prerelease_and_build(self):
        version = SemVer.parse("1.2.3-alpha+build.1")

        self.assertEqual(
            str(version.copy(clear_prerelease=True)),
            "1.2.3+build.1",
        )

        self.assertEqual(
            str(version.copy(clear_build=True)),
            "1.2.3-alpha",
        )

        self.assertEqual(
            str(version.copy(clear_prerelease=True, clear_build=True)),
            "1.2.3",
        )

    def test_copy_clear_flags_win_over_replacement_values(self):
        version = SemVer.parse("1.2.3-alpha+build.1")

        self.assertEqual(
            str(
                version.copy(
                    prerelease="beta",
                    build="build.2",
                    clear_prerelease=True,
                    clear_build=True,
                )
            ),
            "1.2.3",
        )

    def test_copy_revalidates_new_instance(self):
        version = SemVer.parse("1.2.3")

        with self.assertRaises(ValueError):
            version.copy(major=-1)

        with self.assertRaises(ValueError):
            version.copy(prerelease="01")

        with self.assertRaises(ValueError):
            version.copy(build="bad_build")

    def test_bump_major(self):
        self.assertEqual(str(SemVer.parse("1.2.3-alpha+build.1").bump_major()), "2.0.0")

    def test_bump_minor(self):
        self.assertEqual(str(SemVer.parse("1.2.3-alpha+build.1").bump_minor()), "1.3.0")

    def test_bump_patch(self):
        self.assertEqual(str(SemVer.parse("1.2.3-alpha+build.1").bump_patch()), "1.2.4")

    def test_with_prerelease_clears_build(self):
        version = SemVer.parse("1.2.3+build.1")
        self.assertEqual(str(version.with_prerelease("alpha.1")), "1.2.3-alpha.1")

    def test_without_prerelease(self):
        version = SemVer.parse("1.2.3-alpha.1+build.1")
        self.assertEqual(str(version.without_prerelease()), "1.2.3+build.1")

    def test_with_build(self):
        version = SemVer.parse("1.2.3-alpha.1")
        self.assertEqual(str(version.with_build("build.5")), "1.2.3-alpha.1+build.5")

    def test_without_build(self):
        version = SemVer.parse("1.2.3-alpha.1+build.1")
        self.assertEqual(str(version.without_build()), "1.2.3-alpha.1")

    def test_bump_prerelease_appends_numeric_identifier_when_absent(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-alpha").bump_prerelease()),
            "1.2.3-alpha.1",
        )

        self.assertEqual(
            str(SemVer.parse("1.2.3-alpha.beta").bump_prerelease()),
            "1.2.3-alpha.beta.1",
        )

    def test_bump_prerelease_increments_final_numeric_identifier(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-alpha.1").bump_prerelease()),
            "1.2.3-alpha.2",
        )

        self.assertEqual(
            str(SemVer.parse("1.2.3-rc.9").bump_prerelease()),
            "1.2.3-rc.10",
        )

        self.assertEqual(
            str(SemVer.parse("1.2.3-1").bump_prerelease()),
            "1.2.3-2",
        )

    def test_bump_prerelease_does_not_increment_alphanumeric_suffix(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-beta11").bump_prerelease()),
            "1.2.3-beta11.1",
        )

    def test_bump_prerelease_clears_build(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-alpha.1+build.1").bump_prerelease()),
            "1.2.3-alpha.2",
        )

    def test_bump_prerelease_requires_existing_prerelease(self):
        with self.assertRaises(ValueError):
            SemVer.parse("1.2.3").bump_prerelease()

    def test_bump_trailing_number(self):
        cases = {
            "alpha": "alpha.1",
            "alpha.beta": "alpha.beta.1",
            "alpha.1": "alpha.2",
            "rc.9": "rc.10",
            "1": "2",
            "beta11": "beta11.1",
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(bump_trailing_number(value), expected)

    def test_with_advanced_prerelease_starts_a_fresh_prerelease(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3").with_advanced_prerelease()),
            "1.2.3-rc.1",
        )
        self.assertEqual(
            str(SemVer.parse("1.2.3").with_advanced_prerelease("alpha")),
            "1.2.3-alpha.1",
        )

    def test_with_advanced_prerelease_increments_same_token(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-rc.1").with_advanced_prerelease("rc")),
            "1.2.3-rc.2",
        )
        self.assertEqual(
            str(SemVer.parse("1.2.3-rc.1").with_advanced_prerelease()),
            "1.2.3-rc.2",
        )

    def test_with_advanced_prerelease_switches_token_and_resets_serial(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-alpha.5").with_advanced_prerelease("beta")),
            "1.2.3-beta.1",
        )

    def test_with_advanced_prerelease_appends_serial_when_absent(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-alpha").with_advanced_prerelease("alpha")),
            "1.2.3-alpha.1",
        )
        self.assertEqual(
            str(SemVer.parse("1.2.3-alpha").with_advanced_prerelease()),
            "1.2.3-alpha.1",
        )

    def test_with_advanced_prerelease_clears_build(self):
        self.assertEqual(
            str(SemVer.parse("1.2.3-rc.1+build.1").with_advanced_prerelease("rc")),
            "1.2.3-rc.2",
        )

    def test_instances_are_usable_in_sets_and_dicts_by_precedence(self):
        versions = {
            SemVer.parse("1.0.0+abc"),
            SemVer.parse("1.0.0+xyz"),
            SemVer.parse("1.0.0-alpha"),
        }

        self.assertEqual(len(versions), 2)

        mapping = {
            SemVer.parse("1.0.0+abc"): "first",
            SemVer.parse("1.0.0+xyz"): "second",
        }

        self.assertEqual(len(mapping), 1)
        self.assertEqual(mapping[SemVer.parse("1.0.0+anything")], "second")


if __name__ == "__main__":
    unittest.main()
