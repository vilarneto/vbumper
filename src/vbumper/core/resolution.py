"""Aggregation of discovered version containers into a single "current version" for the CLI's
bump-family commands (`patch`/`minor`/`major`/`prerelease`/.../`print`), and the corresponding
write-back target selection.

`set` (an explicit target version) deliberately does not go through `resolve_common_version` --
it needs no existing agreement to compute from. Everything here is CLI-agnostic; `vbumper.cli.bump`
is what actually wires it into the chain group.
"""

import pathlib
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from vbumper.config.root import VBumpConfig
    from vbumper.core.containers.base import VersionContainer
    from vbumper.core.semver import SemVer


def discover_containers(
    config: VBumpConfig, *, path: pathlib.Path | str = "."
) -> list[VersionContainer]:
    """Run every discoverer in `config.discoverers` and collect all containers found, in
    declaration order (then in each discoverer's own discovery order).

    Every discoverer -- built-in types included -- is opt-in: nothing runs unless it's listed
    under `discoverers:` in the loaded config (see `vbumper.config.load.load_config`, which
    requires a config file to exist in the first place). A config with no `discoverers:` entries
    at all is valid but almost certainly not what was intended, so it's flagged with a warning
    rather than silently discovering nothing.

    `path` is the CLI's `--dir`/`-d` value (default `.`), applied uniformly as every
    discoverer's own walk root -- it must name a directory, which scopes the whole run to it.
    See `vbumper.core.files.discoverer.resolve_discovery_root` for exactly how a file-based
    discoverer applies it."""

    import warnings

    if isinstance(path, str):
        path = pathlib.Path(path)

    if not config.discoverers:
        warnings.warn(
            "No discoverers are configured -- nothing will be discovered. Add entries under"
            " 'discoverers:' in .vbump.yaml (see 'vbump init'), or this run is a no-op.",
            stacklevel=2,
        )

    discoverers = [
        entry.resolve().create_discoverer(
            path_exclude_patterns=config.all_exclude_patterns, dir_root=path
        )
        for entry in config.discoverers
    ]
    return [container for discoverer in discoverers for container in discoverer.discover()]


def resolve_common_version(
    containers: Iterable[VersionContainer],
    *,
    allow_incompatible_versions: bool = False,
    skip_unreadable_version_strings: bool = False,
) -> SemVer | None:
    """Compute the single version every discovered container agrees on, or `None` if no
    container is `Versioned` at all (an all-`Unversioned` project, or no containers discovered).

    Raises `IncompatibleVersionsError` (unless `allow_incompatible_versions`) when any container
    is `Invalid`/`Mismatched`, or when two `Versioned` containers disagree. `Unversioned`
    containers never participate in either check, per the "unversioned containers are always
    compatible" rule.

    `skip_unreadable_version_strings` makes `Invalid`/`Mismatched` containers transparent to this
    computation entirely (as if they had not been discovered) rather than requiring the
    incompatibility override -- mirroring the legacy flag of the same name. When
    `allow_incompatible_versions` is set and multiple *valid* `Versioned` containers genuinely
    disagree, there is no principled "correct" base to bump from; this deterministically picks
    the first one encountered (in discovery order) rather than guessing something fancier.
    """

    from vbumper.core.containers.types import Invalid, Mismatched, Versioned
    from vbumper.core.exceptions import IncompatibleVersionsError

    versioned_values: list[SemVer] = []
    has_incompatible = False

    for container in containers:
        status = container.status
        if isinstance(status, Versioned):
            versioned_values.append(status.value)
        elif isinstance(status, Invalid | Mismatched):
            if not skip_unreadable_version_strings:
                has_incompatible = True

    disagree = len({value for value in versioned_values}) > 1

    if (has_incompatible or disagree) and not allow_incompatible_versions:
        raise IncompatibleVersionsError(
            "Discovered version containers do not agree on a single version"
            " (use --allow-incompatible-versions to proceed)"
        )

    if not versioned_values:
        return None

    return versioned_values[0]


def containers_to_update(
    containers: Iterable[VersionContainer], *, skip_unreadable_version_strings: bool = False
) -> list[VersionContainer]:
    """The containers write-back should actually touch: all of them, unless
    `skip_unreadable_version_strings` is set, in which case containers that were `Invalid` or
    `Mismatched` at discovery time are left untouched entirely (consistent with
    `resolve_common_version` treating them as if never discovered)."""

    from vbumper.core.containers.types import Invalid, Mismatched

    containers = list(containers)
    if not skip_unreadable_version_strings:
        return containers

    return [
        container
        for container in containers
        if not isinstance(container.status, Invalid | Mismatched)
    ]


__all__ = ["containers_to_update", "discover_containers", "resolve_common_version"]
