import abc
import pathlib
import re
import warnings
from typing import Iterable, Iterator

import pathspec

from ..discoverers.protocols import DiscovererProtocol
from ..exceptions import ConfigurationError, DiscovererFailure
from .container import (
    JSONFileVersionContainer,
    TextFileContentsVersionContainer,
    describe_file_container,
)


class TooManyMatchesFailure(DiscovererFailure):
    """Raised when a file matches its content pattern more times than this parser type expects
    (`allow_multiple_matches=False`). This is a structural parser-configuration issue, not a
    version disagreement — the latter is represented as a `Mismatched` status instead of raised."""


def _build_pathspec(patterns: Iterable[str] | None) -> pathspec.PathSpec | None:
    """`None` in, `None` out: callers pass `None` to mean "not configured" explicitly, distinct
    from an empty list of patterns (which builds a real, if unhelpful, `PathSpec` that matches
    nothing -- exactly what gitignore semantics would say for zero patterns)."""

    if patterns is None:
        return None
    return pathspec.PathSpec.from_lines("gitignore", list(patterns))


#: A directory holding one of these has its own, independent project configuration -- pruned
#: from every discovery walk the same way a `.vbumpignore` marker prunes a subtree (see
#: `AbstractFileDiscoverer.discover`), but never auto-loaded/merged into the run doing the
#: pruning: a subtree opting into its own rules this way is exactly the "monorepo wanting
#: independently versioned components" case, which is expected to be run as its own separate
#: `vbump -d that/subdir` invocation, not folded into a parent's "every container must agree"
#: check.
_NESTED_CONFIG_FILE_NAMES = (".vbump.yaml", ".vbump.yml")

#: A directory holding one of these marks the root of its own version-control repository --
#: distinct from the run's own root, which is never treated as "nested" even if it happens to
#: carry one of these itself. There is no flag/config to opt back into recursing into such a
#: subtree; see `AbstractFileDiscoverer.discover`.
_VCS_ROOT_MARKER_NAMES = (".git", ".svn", ".hg")


def resolve_discovery_root(dir_root: pathlib.Path | None) -> pathlib.Path:
    """Turn the CLI's `--dir`/`-d` value (default `.`, i.e. `dir_root is None`) into the
    directory `AbstractFileDiscoverer` should walk from. There is no per-discoverer `base_dir`
    to combine it with -- every discoverer entry is scoped by `--dir` uniformly, and narrows
    further only via its own `include:` patterns.

    `dir_root` must name an existing directory (or be `None`, meaning the current directory).
    Raises `ConfigurationError` otherwise -- `--dir`/`-d` only ever accepts a directory; pointing
    it at a single file is not supported."""

    if dir_root is None:
        return pathlib.Path(".")

    if not dir_root.is_dir():
        raise ConfigurationError(f"{dir_root} is not a directory -- --dir/-d requires one")

    return dir_root


class AbstractFileDiscoverer[Container: TextFileContentsVersionContainer](
    DiscovererProtocol[Container], abc.ABC
):
    """A superclass for discoverers that discover version containers from files."""

    _root_dir: pathlib.Path
    _include_spec: pathspec.PathSpec | None
    _path_exclude_spec: pathspec.PathSpec | None

    def __init__(
        self,
        *,
        root_dir: pathlib.Path | str,
        include_patterns: Iterable[str] | None = None,
        path_exclude_patterns: Iterable[str] | None = None,
    ):
        """`include_patterns` are this discoverer's own gitignore-style narrowing of which files
        are candidates (e.g. `["**/*.plist"]`); leave as `None` to consider every file a
        candidate -- an explicit empty list means "match nothing", not "unconfigured".
        `path_exclude_patterns` are the project-wide `exclude:` patterns from `VBumpConfig`
        (already combined with the built-in defaults -- see `VBumpConfig.all_exclude_patterns` --,
        so callers should pass that property, not `exclude` directly), applied uniformly across
        every discoverer and used to prune whole directories during the walk, not just individual
        files."""

        if isinstance(root_dir, str):
            root_dir = pathlib.Path(root_dir)

        self._root_dir = root_dir
        self._include_spec = _build_pathspec(include_patterns)
        self._path_exclude_spec = _build_pathspec(path_exclude_patterns)

    def _is_path_excluded(self, relative_path: pathlib.PurePath, *, is_dir: bool) -> bool:
        if self._path_exclude_spec is None:
            return False

        posix_path = relative_path.as_posix()
        if is_dir:
            posix_path += "/"

        return self._path_exclude_spec.match_file(posix_path)

    def _is_path_included(self, relative_path: pathlib.PurePath) -> bool:
        """This discoverer's own candidate-narrowing, distinct from the project-wide `exclude:`.
        Unlike exclusion, this never prunes directories during the walk -- a directory that
        doesn't itself match `include_patterns` may still contain files below it that do."""

        if self._include_spec is None:
            return True

        return self._include_spec.match_file(relative_path.as_posix())

    def discover(self) -> Iterator[Container]:
        for current_dir, dir_entries, file_entries in self._root_dir.walk():
            relative_dir = current_dir.relative_to(self._root_dir)

            # A `.vbumpignore` flag file in the current directory opts its whole subtree out of
            # discovery, regardless of `exclude:`/`include:` -- its mere presence is the signal
            # (same spirit as a `.gitignore` marker file), so this doesn't even bother reading
            # its contents. Pruned in the same pass as the `exclude:`-driven pruning below,
            # rather than as a separate post-pass over the walk.
            if (current_dir / ".vbumpignore").is_file():
                dir_entries[:] = []
                continue

            # A nested `.vbump.yaml`/`.vbump.yml` below the run's own root means that
            # subdirectory has its own, independent project configuration -- pruned the same
            # way, so it's never forced to agree with this run's discovered versions. (The
            # config file *at* `root_dir` itself, if any, is this run's own -- not nested.)
            if current_dir != self._root_dir:
                nested_config = next(
                    (
                        current_dir / file_name
                        for file_name in _NESTED_CONFIG_FILE_NAMES
                        if (current_dir / file_name).is_file()
                    ),
                    None,
                )
                if nested_config is not None:
                    warnings.warn(
                        f"Skipping {current_dir} for discovery: it has its own"
                        f" {nested_config.name}, so it is treated as an independent project"
                        f" -- run `vbump -d {current_dir}` separately if you want to version it.",
                        stacklevel=2,
                    )
                    dir_entries[:] = []
                    continue

                vcs_marker = next(
                    (
                        marker_name
                        for marker_name in _VCS_ROOT_MARKER_NAMES
                        if (current_dir / marker_name).exists()
                    ),
                    None,
                )
                if vcs_marker is not None:
                    warnings.warn(
                        f"Skipping {current_dir} for discovery: it has its own {vcs_marker},"
                        f" so it is treated as a separate repository nested inside this one --"
                        f" run `vbump -d {current_dir}` separately if you want to version it.",
                        stacklevel=2,
                    )
                    dir_entries[:] = []
                    continue

            # Prune in place (per `Path.walk`'s contract) so excluded directories are never
            # descended into at all, not merely skipped once reached.
            dir_entries[:] = [
                dir_entry
                for dir_entry in dir_entries
                if not self._is_path_excluded(relative_dir / dir_entry, is_dir=True)
            ]

            for file_entry in file_entries:
                relative_file = relative_dir / file_entry
                if self._is_path_excluded(relative_file, is_dir=False):
                    continue
                if not self._is_path_included(relative_file):
                    continue

                yield from self._discover_from_file(current_dir / file_entry)

    @abc.abstractmethod
    def _discover_from_file(
        self, file_path: pathlib.Path
    ) -> Iterator[TextFileContentsVersionContainer]: ...


class RegularExpressionFileDiscoverer(AbstractFileDiscoverer[TextFileContentsVersionContainer]):
    _allow_multiple_matches: bool
    _encoding: str
    _version_pattern: re.Pattern

    def __init__(
        self,
        *,
        root_dir: pathlib.Path | str,
        version_pattern: re.Pattern | str,
        allow_multiple_matches: bool = False,
        encoding: str,
        include_patterns: Iterable[str] | None = None,
        path_exclude_patterns: Iterable[str] | None = None,
    ):
        if isinstance(version_pattern, str):
            version_pattern = re.compile(version_pattern)

        if "version" not in version_pattern.groupindex:
            raise ConfigurationError("Expected version pattern to contain a group named 'version'")

        super().__init__(
            root_dir=root_dir,
            include_patterns=include_patterns,
            path_exclude_patterns=path_exclude_patterns,
        )
        self._allow_multiple_matches = allow_multiple_matches
        self._encoding = encoding
        self._version_pattern = version_pattern

    def _discover_from_file(
        self,
        file_path: pathlib.Path,
    ) -> Iterator[TextFileContentsVersionContainer]:
        with file_path.open("rt", encoding=self._encoding) as file:
            contents = file.read()

        last_pos = 0
        chunks: list[bytes] = []
        version_chunks: list[bytes] = []

        for match in self._version_pattern.finditer(contents):
            if not self._allow_multiple_matches and version_chunks:
                raise TooManyMatchesFailure(
                    "File matches the version pattern more than once",
                    container_description=describe_file_container(file_path),
                )

            chunks.append(contents[last_pos : match.start("version")].encode(self._encoding))
            version_chunks.append(match.group("version").encode(self._encoding))
            last_pos = match.end("version")

        if not version_chunks:
            return

        chunks.append(contents[last_pos:].encode(self._encoding))

        yield TextFileContentsVersionContainer(
            file_path=file_path,
            version_chunks=version_chunks,
            chunks=chunks,
            encoding=self._encoding,
        )


class JSONFileDiscoverer(AbstractFileDiscoverer[JSONFileVersionContainer]):
    """Discovers a version container at a top-level string key of a JSON file (e.g.
    `package.json`'s `"version"`). A file that isn't valid JSON, doesn't parse to a top-level
    object, has no `version_key` at all, or whose value at that key isn't a string, is simply
    not a version container -- nothing is yielded for it, mirroring the legacy NPM parser's
    `data.get("version")` / `isinstance(..., str)` gate (this is *not* the same as `Unversioned`,
    which requires the key to be present with an empty-string value)."""

    _encoding: str
    _version_key: str

    def __init__(
        self,
        *,
        root_dir: pathlib.Path | str,
        encoding: str = "utf-8",
        version_key: str = "version",
        include_patterns: Iterable[str] | None = None,
        path_exclude_patterns: Iterable[str] | None = None,
    ):
        super().__init__(
            root_dir=root_dir,
            include_patterns=include_patterns,
            path_exclude_patterns=path_exclude_patterns,
        )
        self._encoding = encoding
        self._version_key = version_key

    def _discover_from_file(
        self,
        file_path: pathlib.Path,
    ) -> Iterator[JSONFileVersionContainer]:
        import json

        with file_path.open("rt", encoding=self._encoding) as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                return

        if not isinstance(data, dict):
            return

        value = data.get(self._version_key)
        if not isinstance(value, str):
            return

        yield JSONFileVersionContainer(
            file_path=file_path,
            data=data,
            version_key=self._version_key,
            encoding=self._encoding,
        )


__all__ = [
    "AbstractFileDiscoverer",
    "JSONFileDiscoverer",
    "RegularExpressionFileDiscoverer",
    "TooManyMatchesFailure",
    "resolve_discovery_root",
]
