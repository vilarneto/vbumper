"""The `git-tag` built-in: a discoverer that reads the current version from the highest Git tag
already present in the repository, rather than from any file. See `GitTagConfig`'s docstring for
the `tag_prefix` field, and `GitTagVersionContainer.is_writable` for why this discoverer never
creates a tag itself: that stays the user's own flow's job, via a `post_commands` entry such as
`git tag {VERSION_TAG}`.
"""

import pathlib
from typing import Annotated, Any, Iterable, Iterator

import pydantic

from vbumper.core.containers.base import VersionContainer
from vbumper.core.containers.types import VersionStatus


class GitTagVersionContainer(VersionContainer):
    """The single version container a `GitTagDiscoverer` run ever yields: the highest
    Semantic Version among the repository's tags matching its configured `tag_prefix`, or
    `Unversioned` if none match (including the legitimate “no release yet” case of zero tags).

    Not file-backed (`file_path` stays at the base class's `None` default) and never a
    write-back target (see `is_writable`)."""

    def __init__(self, *, status: VersionStatus):
        super().__init__(status=status)

    @property
    def is_writable(self) -> bool:
        """Always `False`: a Git tag's own existence *is* its version, so there is nothing
        meaningful to “write back” to it. Creating the actual release tag is the flow's own
        job (`post_commands: ["git tag {VERSION_TAG}"]`), which already works today without any
        discoverer-driven write-back, and avoids tagging the wrong commit: write-back happens
        before a flow's `stage_command`/`post_commands` commit, so a discoverer that tagged at
        write-back time would tag the pre-commit parent whenever combined with file-based
        containers in the same run."""
        return False

    def describe(self) -> str:
        return "Git tags"

    def write(self) -> None:
        """Never actually called in normal operation: `is_writable` being `False` means
        `vbumper.core.resolution.containers_to_update` excludes this container from every
        write-back path before `write()` could ever be reached. Raising `NotImplementedError`
        (not a `VBumpError`) signals that reaching this line is a vbumper-internal invariant
        violation, not a normal, user-facing failure such as a write-locked file."""
        raise NotImplementedError(
            "GitTagVersionContainer is not writable; write() must never be called"
            " (is_writable is False)"
        )


class GitTagDiscoverer:
    """Reads the current version from the highest Git tag matching `tag_prefix` already
    present in the repository rooted at `root_dir`. Implements
    `vbumper.core.discoverers.protocols.DiscovererProtocol[GitTagVersionContainer]` directly
    (not `AbstractFileDiscoverer`): there is no file tree to walk, only a single `git tag --list`
    read."""

    _tag_prefix: str
    _root_dir: pathlib.Path

    def __init__(self, *, tag_prefix: str, root_dir: pathlib.Path):
        self._tag_prefix = tag_prefix
        self._root_dir = root_dir

    def discover(self) -> Iterator[GitTagVersionContainer]:
        import subprocess

        from vbumper.core.containers.types import Unversioned, Versioned
        from vbumper.core.exceptions import DiscovererFailure
        from vbumper.core.semver import SemVer

        result = subprocess.run(
            ["git", "tag", "--list", f"{self._tag_prefix}*"],
            capture_output=True,
            text=True,
            cwd=self._root_dir,
        )
        if result.returncode != 0:
            raise DiscovererFailure(
                f"Could not list Git tags ({result.stderr.strip() or 'git tag --list failed'})",
                container_description="Git tags",
            )

        versions: list[SemVer] = []
        for tag in result.stdout.splitlines():
            tag = tag.strip()
            if not tag.startswith(self._tag_prefix):
                continue

            raw = tag[len(self._tag_prefix) :]
            try:
                versions.append(SemVer.parse(raw))
            except ValueError:
                continue

        status = Versioned(value=max(versions)) if versions else Unversioned()
        yield GitTagVersionContainer(status=status)


class GitTagConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[GitTagDiscoverer]` structurally (see
    `vbumper.core.files.config.RegularExpressionFileConfig` for why this can't inherit the
    protocol directly: `Protocol` and `pydantic.BaseModel` use different metaclasses).

    Zero-configuration by default: a bare `type: git-tag` entry reads tags prefixed `v`,
    matching `VBumpConfig.version_tag_prefix`'s own default. `tag_prefix` is deliberately this
    entry's own field rather than derived from `version_tag_prefix`: a `DiscovererEntryConfig`
    only ever resolves against its own dict (see `DiscovererEntryConfig.resolve`), never the
    rest of `VBumpConfig`, so a project using a non-default `version_tag_prefix` together with
    `git-tag` discovery must set the same value in both places by hand: explicit over implicit
    coupling, consistent with how a flow's own `variables:` already work.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    tag_prefix: Annotated[str, pydantic.Field(default="v")]

    @classmethod
    def get_type(cls) -> str:
        return "git-tag"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> "GitTagConfig":
        return cls.model_validate(data)

    def create_discoverer(
        self,
        *,
        path_exclude_patterns: Iterable[str] = (),
        dir_root: pathlib.Path | None = None,
    ) -> GitTagDiscoverer:
        """Not file-based: `path_exclude_patterns` is ignored (there are no files to exclude
        from anything). `dir_root` is still honored, as the working directory `git tag` is run
        from, so `--dir`/`-d` remains the single discovery root even for a Git-native
        discoverer."""

        from vbumper.core.files.discoverer import resolve_discovery_root

        root_dir = resolve_discovery_root(dir_root)
        return GitTagDiscoverer(tag_prefix=self.tag_prefix, root_dir=root_dir)

    @classmethod
    def iter_auto_detected(
        cls, *, dir_root: pathlib.Path, path_exclude_patterns: Iterable[str]
    ) -> Iterator[tuple[list[str], dict[str, Any]]]:
        """Never auto-detected by `vbump init`
        (see `vbumper.core.detect.detect_builtin_discoverers`): a repository's tags are too weak
        a signal that a project actually wants `git-tag` discovery, since any Git repo may
        carry unrelated tags, with or without the default `v` prefix. Also,
        `GitTagDiscoverer.discover()` fails outright when `dir_root` isn't inside a Git
        repository at all, which the generic auto-detection scan has no per-type way to treat
        as “nothing found” rather than a crash. `type: git-tag` must be added to `.vbump.yaml`
        by hand. Returning no candidates here (rather than leaving this hook unset) takes this
        discoverer out of the default `from_config_dict({})` + `discover()` probe entirely."""
        return iter(())


__all__ = ["GitTagConfig", "GitTagDiscoverer", "GitTagVersionContainer"]
