import os
import pathlib
import subprocess
import tempfile
import unittest

from vbumper.core.containers.types import Unversioned, Versioned
from vbumper.core.exceptions import DiscovererFailure
from vbumper.core.git.gittag import GitTagConfig, GitTagVersionContainer
from vbumper.core.semver import SemVer


class _GitRepoTestCase(unittest.TestCase):
    """Mirrors `tests.test_flows._GitRepoTestCase`, kept local so this module doesn't reach
    into another test module's private helper."""

    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.repo_dir = pathlib.Path(tmp_dir.name)

        previous_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        self.addCleanup(os.chdir, previous_cwd)

        subprocess.run(["git", "init", "-q"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test"], check=True)
        (self.repo_dir / "README.md").write_text("hello\n")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], check=True)

    def tag(self, name: str) -> None:
        subprocess.run(["git", "tag", name], check=True)


def _discover_one(**config_kwargs) -> GitTagVersionContainer:
    config = GitTagConfig.from_config_dict(config_kwargs)
    discoverer = config.create_discoverer()
    (container,) = discoverer.discover()
    return container


class TestDiscover(_GitRepoTestCase):
    def test_no_tags_yields_unversioned(self):
        container = _discover_one()
        self.assertEqual(container.status, Unversioned())

    def test_single_tag_yields_versioned(self):
        self.tag("v1.2.3")
        container = _discover_one()
        self.assertEqual(container.status, Versioned(value=SemVer.parse("1.2.3")))

    def test_highest_of_several_tags_wins(self):
        for name in ("v1.0.0", "v2.0.0", "v1.5.0"):
            self.tag(name)
        container = _discover_one()
        self.assertEqual(container.status, Versioned(value=SemVer.parse("2.0.0")))

    def test_stray_non_matching_tag_is_ignored(self):
        self.tag("v1.0.0")
        self.tag("not-a-release")
        container = _discover_one()
        self.assertEqual(container.status, Versioned(value=SemVer.parse("1.0.0")))

    def test_custom_tag_prefix(self):
        self.tag("release-1.0.0")
        self.tag("v9.9.9")  # must be ignored: doesn't match the configured prefix
        container = _discover_one(tag_prefix="release-")
        self.assertEqual(container.status, Versioned(value=SemVer.parse("1.0.0")))

    def test_malformed_prefixed_tag_is_silently_skipped(self):
        self.tag("v1.0.0")
        self.tag("v2.0")  # missing patch component: not a valid SemVer
        container = _discover_one()
        self.assertEqual(container.status, Versioned(value=SemVer.parse("1.0.0")))

    def test_empty_prefix_skips_non_semver_tags(self):
        self.tag("1.0.0")
        self.tag("not-a-release-at-all")
        container = _discover_one(tag_prefix="")
        self.assertEqual(container.status, Versioned(value=SemVer.parse("1.0.0")))

    def test_tag_coincidentally_starting_with_prefix_is_skipped(self):
        """`startswith(tag_prefix)` alone is too weak a signal: with the default prefix "v",
        a tag like "validated-by-client" matches it exactly as trivially as a real version tag
        would, and its remainder (“alidated-by-client”) just doesn't parse as a SemVer, the
        same as any other unrelated tag."""

        self.tag("v1.0.0")
        self.tag("validated-by-client")
        container = _discover_one()
        self.assertEqual(container.status, Versioned(value=SemVer.parse("1.0.0")))

    def test_not_a_git_repository_raises_discoverer_failure(self):
        os.chdir(tempfile.mkdtemp())
        with self.assertRaises(DiscovererFailure):
            _discover_one()


class TestGitTagVersionContainer(unittest.TestCase):
    def test_is_not_writable(self):
        container = GitTagVersionContainer(status=Unversioned())
        self.assertFalse(container.is_writable)

    def test_describe(self):
        container = GitTagVersionContainer(status=Unversioned())
        self.assertEqual(container.describe(), "Git tags")

    def test_write_raises_not_implemented(self):
        container = GitTagVersionContainer(status=Unversioned())
        with self.assertRaises(NotImplementedError):
            container.write()


class TestGitTagConfig(unittest.TestCase):
    def test_get_type(self):
        self.assertEqual(GitTagConfig.get_type(), "git-tag")

    def test_never_auto_detected(self):
        self.assertEqual(
            list(
                GitTagConfig.iter_auto_detected(
                    dir_root=pathlib.Path("."), path_exclude_patterns=()
                )
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
