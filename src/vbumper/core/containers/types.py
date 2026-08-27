import dataclasses
import enum
from typing import Literal

from vbumper.core.semver import SemVer


class NoSemVer(enum.Enum):
    """Sentinel type for 'this copy has no version string at all' (unversioned), distinct from
    an invalid/unparseable copy."""

    NO_SEMVER = enum.auto()


NO_SEMVER: Literal[NoSemVer.NO_SEMVER] = NoSemVer.NO_SEMVER


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Versioned:
    """A single agreed SemVer across all copies of this container."""

    value: SemVer


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Unversioned:
    """No copy in this container has a version yet (all copies are NO_SEMVER)."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Invalid:
    """At least one copy is an unparseable version string. No raw string is retained."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Mismatched:
    """Two or more copies disagree, or a versioned/invalid mix exists internally."""

    copies: list[SemVer | NoSemVer]


def resolve_status(copies: list[SemVer | NoSemVer | None]) -> VersionStatus:
    """Conflate the per-copy parse results of a multi-copy container into a single
    `VersionStatus`. `None` marks a copy whose raw string failed to parse as a semver; that raw
    string is not retained anywhere (per the "no effort to store invalid raw strings" rule)."""
    if any(copy is None for copy in copies):
        return Invalid()

    versioned = [copy for copy in copies if isinstance(copy, SemVer)]
    if not versioned:
        return Unversioned()

    if all(copy == versioned[0] for copy in versioned):
        return Versioned(value=versioned[0])

    return Mismatched(copies=copies)  # type: ignore[arg-type]  # `None`s excluded above


type VersionStatus = Versioned | Unversioned | Invalid | Mismatched


__all__ = [
    "NO_SEMVER",
    "Invalid",
    "Mismatched",
    "NoSemVer",
    "Unversioned",
    "VersionStatus",
    "Versioned",
    "resolve_status",
]
