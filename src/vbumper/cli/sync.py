"""`vbump sync`: reconcile every discovered container to the single highest version found.

Deliberately not a chained `Step`-returning command like the bump family (see `.bump`): its
target-selection rules (which containers are even eligible to be touched, gated by its own local
flags) and its interactive confirmation step don't fit the shared `BumpChainState`/write-back
pipeline that `patch`/`minor`/etc. use. Instead it does its one job eagerly in its own callback and
returns nothing, the same shape `init`/`list` already use.

Unlike the bump family, `sync` never requires prior agreement across containers -- disagreement is
exactly the situation it exists to resolve. It takes the highest `SemVer` found among `Versioned`
containers (optionally also looking inside `Mismatched` containers' internal copies) and writes it
over every `Versioned`/`Unversioned` container, plus `Mismatched`/`Invalid` containers if their
respective opt-in flag is given."""

from typing import TYPE_CHECKING

import rich_click as click

from ._grp import root_grp

if TYPE_CHECKING:
    from vbumper.core.containers.base import VersionContainer
    from vbumper.core.semver import SemVer


def _candidate_pool(
    containers: list[VersionContainer], *, include_mismatched: bool
) -> list[SemVer]:
    from vbumper.core.containers.types import Mismatched, Versioned
    from vbumper.core.semver import SemVer

    pool: list[SemVer] = []
    for container in containers:
        status = container.status
        if isinstance(status, Versioned):
            pool.append(status.value)
        elif include_mismatched and isinstance(status, Mismatched):
            pool.extend(copy for copy in status.copies if isinstance(copy, SemVer))
    return pool


def _in_scope(container: VersionContainer, *, include_mismatched: bool, fix_invalid: bool) -> bool:
    from vbumper.core.containers.types import Invalid, Mismatched, Unversioned, Versioned

    status = container.status
    if isinstance(status, Versioned | Unversioned):
        return True
    if isinstance(status, Mismatched):
        return include_mismatched
    if isinstance(status, Invalid):
        return fix_invalid

    raise AssertionError(f"Unhandled version status: {status!r}")  # pragma: no cover


@root_grp.command()
@click.option(
    "--include-mismatched",
    is_flag=True,
    default=False,
    help=(
        "Also consider values found inside mismatched containers when picking the highest"
        " version, and overwrite such containers too."
    ),
)
@click.option(
    "--fix-invalid",
    is_flag=True,
    default=False,
    help="Also overwrite invalid containers with the resulting version.",
)
@click.option(
    "--no-input",
    is_flag=True,
    default=False,
    help="Do not ask for confirmation before writing.",
)
def sync(include_mismatched: bool, fix_invalid: bool, no_input: bool) -> None:
    """Write the highest version found across all discovered containers back over every
    versioned and unversioned container, asking for confirmation first."""

    from vbumper.core.containers.types import Versioned
    from vbumper.core.exceptions import NoBaseVersionError, WriteBackFailure
    from vbumper.core.resolution import discover_containers

    from ._describe import describe_status
    from .context import get_config, get_options

    options = get_options()
    containers = discover_containers(get_config(), path=options.dir)

    pool = _candidate_pool(containers, include_mismatched=include_mismatched)
    if not pool:
        raise NoBaseVersionError(
            "No versioned container was discovered to sync from"
            + (" (try --include-mismatched)" if not include_mismatched else "")
        )
    target_version = max(pool)

    scoped_containers = [
        container
        for container in containers
        if _in_scope(container, include_mismatched=include_mismatched, fix_invalid=fix_invalid)
    ]
    for container in scoped_containers:
        container.set_status(Versioned(value=target_version), allow_incompatible_versions=True)

    changed_containers = [container for container in scoped_containers if container.has_changed]
    if not changed_containers:
        click.echo("Already in sync.")
        return

    for container in changed_containers:
        old = describe_status(container.orig_status)
        click.echo(f"Would update {container.describe()}: {old} -> {target_version}")

    if options.dry_run:
        return

    if not no_input:
        click.confirm("Proceed?", default=False, abort=True)

    written: list[VersionContainer] = []
    for index, container in enumerate(changed_containers):
        try:
            container.write()
        except Exception as exc:
            remaining = changed_containers[index + 1 :]
            raise WriteBackFailure(
                f"Failed writing {container.describe()}: {exc}",
                failed_description=container.describe(),
                written_descriptions=[c.describe() for c in written],
                not_reached_descriptions=[c.describe() for c in remaining],
            ) from exc
        written.append(container)
        click.echo(f"Updated {container.describe()}: -> {target_version}")


__all__ = ["sync"]
