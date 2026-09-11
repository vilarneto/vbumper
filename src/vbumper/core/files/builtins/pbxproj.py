"""Xcode `project.pbxproj` discoverer and container.

A `project.pbxproj` is an old-style ("ASCII") property list, not a format any of the other
built-ins' machinery understands: a single file can declare several independently-versioned
`PBXNativeTarget`s (e.g. an app target and its test target), each carrying its own
`MARKETING_VERSION` copy per build configuration (typically Debug and Release) rather than one
version string per file. `RegularExpressionFileDiscoverer`'s "every match in the file is one
copy of the same container" model has no way to express that grouping, so this module implements
its own narrow extraction instead of writing a general ASCII-plist parser -- it relies on the
fixed indentation Xcode has always generated (a two-tab-indented `<uuid> /* comment */ = {`
opener and two-tab-indented `};` closer per top-level object entry, with every key inside
indented at least one tab deeper) rather than a full grammar.
"""

import pathlib
import re
from typing import TYPE_CHECKING, Annotated, Any, Iterable, Iterator

import pydantic

from vbumper.core.containers.base import VersionContainer
from vbumper.core.containers.types import NO_SEMVER, NoSemVer, Versioned, resolve_status
from vbumper.core.exceptions import ConfigurationError, DiscovererFailure
from vbumper.core.semver import SemVer

from ..container import describe_file_container
from ..discoverer import AbstractFileDiscoverer, resolve_discovery_root

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol

#: Every `project.pbxproj` Xcode has ever generated opens with this exact comment line -- its
#: absence means the file isn't in the ASCII-plist shape this module parses (or isn't a pbxproj
#: at all), so it's simply not a version container, mirroring `info-plist`'s header gate.
_HEADER_LINE = "// !$*UTF8*$!"

#: See the module docstring for the indentation convention this relies on. `body` captures
#: everything between the opening `{` and the matching `};`, with `DOTALL` so it can cross
#: lines; the non-greedy `.*?` stops at the first two-tab-indented `};`, which holds as long as
#: nothing nested inside the entry sits at that same, shallower indentation -- true for every
#: object kind this module reads (their nested collections all indent one tab deeper).
_ENTRY_PATTERN = re.compile(
    r"^\t\t(?P<uuid>[0-9A-F]{24}) /\* (?P<comment>[^\n]*?) \*/ = \{\n"
    r"(?P<body>.*?)\n\t\t\};$",
    re.MULTILINE | re.DOTALL,
)

_NAME_PATTERN = re.compile(r"^\t\t\tname = (?P<name>[^;]+);$", re.MULTILINE)
_BUILD_CONFIGURATION_LIST_PATTERN = re.compile(
    r"^\t\t\tbuildConfigurationList = (?P<uuid>[0-9A-F]{24})", re.MULTILINE
)
_BUILD_CONFIGURATIONS_LIST_PATTERN = re.compile(
    r"buildConfigurations = \((?P<list>.*?)\);", re.DOTALL
)
_UUID_PATTERN = re.compile(r"[0-9A-F]{24}")

#: The value's own span is what every caller actually needs (to read it, or to replace it on
#: write-back) -- `\t+` tolerates whichever depth a given Xcode version indents `buildSettings`
#: entries at, rather than hardcoding a tab count the way `_NAME_PATTERN`/etc. above do for
#: shallower, more stable keys.
_MARKETING_VERSION_PATTERN = re.compile(
    r"^\t+MARKETING_VERSION = (?P<version>[^;\n]*);$", re.MULTILINE
)


def _section_body_span(content: str, section_name: str) -> tuple[int, int] | None:
    begin_marker = f"/* Begin {section_name} section */"
    end_marker = f"/* End {section_name} section */"

    begin = content.find(begin_marker)
    if begin == -1:
        return None

    body_start = begin + len(begin_marker)
    end = content.find(end_marker, body_start)
    if end == -1:
        return None

    return body_start, end


def _iter_entries(content: str, section_name: str) -> Iterator[re.Match[str]]:
    """Yield one `_ENTRY_PATTERN` match per top-level object entry of the named section. Match
    offsets are relative to the whole `content` string (not the section's own substring), since
    callers rely on them being absolute byte spans usable for write-back."""

    span = _section_body_span(content, section_name)
    if span is None:
        return

    start, stop = span
    yield from _ENTRY_PATTERN.finditer(content, start, stop)


def _find_marketing_version_span(content: str, config_uuid: str) -> tuple[int, int] | None:
    """Locate the `(start, end)` byte span of the `MARKETING_VERSION` value inside the
    `XCBuildConfiguration` entry identified by `config_uuid`, re-derived fresh from `content`
    every time it's called. `PBXProjTargetVersionContainer.write` relies on recomputing this
    against the *current* on-disk content rather than reusing a snapshot taken at discovery time
    -- otherwise, writing one target's container would clobber a sibling target's already-written
    change to the same file, since both targets' containers are backed by the same file."""

    for entry in _iter_entries(content, "XCBuildConfiguration"):
        if entry.group("uuid") != config_uuid:
            continue

        version_match = _MARKETING_VERSION_PATTERN.search(entry.group("body"))
        if version_match is None:
            return None

        body_start = entry.start("body")
        return (
            body_start + version_match.start("version"),
            body_start + version_match.end("version"),
        )

    return None


def _coerce_target_names(value: str | list[str]) -> list[str]:
    """Accept a single target name or a list of them; normalize a bare string to a one-element
    list. Deliberately duplicated from the same-shaped `_coerce_patterns` in
    `vbumper.core.files.config` rather than shared -- see that module's `PathspecPatterns` for
    why a plugin-owned discoverer config avoids depending on shared machinery beyond its own
    module."""

    if isinstance(value, str):
        return [value]
    return value


#: A target name or a list of them, restricting `PBXProjDiscoverer` to only the named
#: `PBXNativeTarget`s. Unlike `PathspecPatterns`'s `include:`, omitting this field entirely means
#: "no restriction" (`None`) -- the `min_length=1` enforced where this is used as a field type
#: only rejects an *explicit* empty list, which could never match anything.
TargetNames = Annotated[list[str], pydantic.BeforeValidator(_coerce_target_names)]


def _parse_copy(raw: str) -> SemVer | NoSemVer | None:
    """See `TextFileContentsVersionContainer._parse_copy` for the same convention: empty string
    is unversioned (`NO_SEMVER`), unparseable non-empty is `None` (raw content discarded),
    otherwise the parsed `SemVer`."""

    if raw == "":
        return NO_SEMVER

    try:
        return SemVer.parse(raw)
    except ValueError:
        return None


class PBXProjTargetVersionContainer(VersionContainer):
    """One `PBXNativeTarget` inside a `project.pbxproj` -- a container in its own right, distinct
    from the file it happens to share with any other targets the same project declares (e.g. an
    app target and its test target), since each target's version may independently drift or get
    bumped.

    Internally this may hold more than one copy of the version (one per build configuration --
    typically Debug and Release), which is why its status is derived via `resolve_status` rather
    than a single parsed value, exactly like any other multi-copy container."""

    _file_path: pathlib.Path
    _encoding: str
    _target_name: str
    _config_uuids: list[str]

    def __init__(
        self,
        *,
        file_path: pathlib.Path,
        encoding: str,
        target_name: str,
        config_uuids: list[str],
        content: str,
    ):
        """`config_uuids` are the build-configuration entries belonging to this target that were
        found (by the discoverer) to actually carry a `MARKETING_VERSION` line -- a build
        configuration without the line at all isn't a copy of this container (there is nowhere
        to write a value back to without inventing a new line, which this does not attempt).
        `content` is the file's contents as already read by the discoverer, reused here to parse
        each copy's initial status without a second read."""

        self._file_path = file_path
        self._encoding = encoding
        self._target_name = target_name
        self._config_uuids = config_uuids

        copies: list[SemVer | NoSemVer | None] = []
        for config_uuid in config_uuids:
            span = _find_marketing_version_span(content, config_uuid)
            assert span is not None, "config_uuids must already be filtered to matching spans"
            copies.append(_parse_copy(content[span[0] : span[1]]))

        super().__init__(status=resolve_status(copies))

    @property
    def target_name(self) -> str:
        """The `PBXNativeTarget` name this container was discovered from -- exposed so
        `PBXProjDiscoverer.discover` can check which configured `targets:` names were actually
        matched, without reaching into the private `_target_name`."""

        return self._target_name

    def describe(self) -> str:
        return f'{describe_file_container(self._file_path)} (target "{self._target_name}")'

    def write(self) -> None:
        if not isinstance(self.status, Versioned):
            raise ValueError(
                "Cannot write a version container whose status is not a resolved version"
            )

        new_version = str(self.status.value)
        content = self._file_path.read_text(encoding=self._encoding)

        spans: list[tuple[int, int]] = []
        for config_uuid in self._config_uuids:
            span = _find_marketing_version_span(content, config_uuid)
            if span is None:
                raise DiscovererFailure(
                    f"Could not re-locate MARKETING_VERSION for build configuration"
                    f" {config_uuid!r} on write-back -- the file may have changed since"
                    f" discovery",
                    container_description=self.describe(),
                )
            spans.append(span)

        # Replace back-to-front so that applying one span's replacement never shifts the byte
        # offsets already computed for the spans still to come.
        for start, end in sorted(spans, reverse=True):
            content = content[:start] + new_version + content[end:]

        self._file_path.write_text(content, encoding=self._encoding)


class PBXProjDiscoverer(AbstractFileDiscoverer[PBXProjTargetVersionContainer]):
    """Discovers one `PBXProjTargetVersionContainer` per `PBXNativeTarget` declared in each
    `project.pbxproj` file, using that target's `buildConfigurationList` to gather every build
    configuration's `MARKETING_VERSION` copy as this target's own set of copies. See the module
    docstring for why this can't reuse `RegularExpressionFileDiscoverer`."""

    _encoding: str
    _target_names: frozenset[str] | None

    def __init__(
        self,
        *,
        root_dir: pathlib.Path | str,
        encoding: str = "utf-8",
        include_patterns: Iterable[str] = (),
        path_exclude_patterns: Iterable[str] = (),
        target_names: Iterable[str] | None = None,
    ):
        """`target_names`, if given, restricts discovery to `PBXNativeTarget`s with one of these
        exact names -- `None` (the default) means every target is a candidate, matching this
        built-in's original zero-configuration behavior."""

        super().__init__(
            root_dir=root_dir,
            include_patterns=include_patterns,
            path_exclude_patterns=path_exclude_patterns,
        )
        self._encoding = encoding
        self._target_names = frozenset(target_names) if target_names is not None else None

    def discover(self) -> Iterator[PBXProjTargetVersionContainer]:
        if self._target_names is None:
            yield from super().discover()
            return

        # A configured name that never matches any target across every scanned file is almost
        # certainly a typo/stale reference -- only detectable once the whole walk has completed,
        # so this wraps the inherited walk rather than checking per-file.
        unmatched = set(self._target_names)
        for container in super().discover():
            unmatched.discard(container.target_name)
            yield container

        if unmatched:
            names = ", ".join(sorted(unmatched))
            raise ConfigurationError(
                f"xcode-pbxproj: targets: {names} matched no PBXNativeTarget under the"
                f" discovery root"
            )

    def _discover_from_file(
        self, file_path: pathlib.Path
    ) -> Iterator[PBXProjTargetVersionContainer]:
        with file_path.open("rt", encoding=self._encoding) as file:
            content = file.read()

        if not content.startswith(_HEADER_LINE):
            return

        config_lists: dict[str, list[str]] = {}
        for entry in _iter_entries(content, "XCConfigurationList"):
            list_match = _BUILD_CONFIGURATIONS_LIST_PATTERN.search(entry.group("body"))
            if list_match is None:
                continue
            config_lists[entry.group("uuid")] = _UUID_PATTERN.findall(list_match.group("list"))

        for entry in _iter_entries(content, "PBXNativeTarget"):
            name_match = _NAME_PATTERN.search(entry.group("body"))
            config_list_match = _BUILD_CONFIGURATION_LIST_PATTERN.search(entry.group("body"))
            if name_match is None or config_list_match is None:
                continue

            target_name = name_match.group("name").strip('"')
            if self._target_names is not None and target_name not in self._target_names:
                continue

            config_uuids = [
                config_uuid
                for config_uuid in config_lists.get(config_list_match.group("uuid"), [])
                if _find_marketing_version_span(content, config_uuid) is not None
            ]
            if not config_uuids:
                continue

            yield PBXProjTargetVersionContainer(
                file_path=file_path,
                encoding=self._encoding,
                target_name=target_name,
                config_uuids=config_uuids,
                content=content,
            )


class PBXProjFileConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[PBXProjDiscoverer]` structurally (see
    `RegularExpressionFileConfig` for why this can't just inherit the protocol directly).

    Needs no parameters by default: every `project.pbxproj` found in the discovery scope is a
    candidate, yielding one container per `PBXNativeTarget` it declares (see
    `PBXProjDiscoverer`). `targets:` optionally narrows that down to specific target names."""

    #: A target name or list of names to restrict discovery to; `None` (the default, including
    #: an omitted `targets:` key) means every target is a candidate. An explicit empty list is
    #: rejected (`min_length=1`) rather than silently discovering nothing.
    targets: Annotated[TargetNames, pydantic.Field(min_length=1)] | None = None

    @classmethod
    def get_type(cls) -> str:
        return "xcode-pbxproj"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> PBXProjFileConfig:
        return cls.model_validate(data)

    def create_discoverer(
        self,
        *,
        path_exclude_patterns: Iterable[str] = (),
        dir_root: pathlib.Path | None = None,
    ) -> PBXProjDiscoverer:
        root_dir = resolve_discovery_root(dir_root)
        return PBXProjDiscoverer(
            root_dir=root_dir,
            encoding="utf-8",
            include_patterns=["project.pbxproj"],
            path_exclude_patterns=path_exclude_patterns,
            target_names=self.targets,
        )


__all__ = ["PBXProjFileConfig"]
