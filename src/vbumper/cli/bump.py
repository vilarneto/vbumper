"""The chain-group bump commands: `patch`/`minor`/`major`, `prerelease`/`rc`/`alpha`/`beta`,
`lower`, `stable`, `set`, and `print`.

Each command returns a `Step` closure rather than doing any work itself; `_run_chain` (the
group's `result_callback`) runs every returned step, in the order given on the command line,
against one shared `BumpChainState`, then writes back whatever changed -- unless `print` was
anywhere in the chain, which makes the whole invocation read-only (see `print_`). This mirrors
the legacy CLI's chain-group shape (`@click.group(chain=True)`) while computing a single
aggregate "current version" across all discovered containers instead of bumping each file
independently.
"""

import dataclasses
from typing import TYPE_CHECKING, Callable

import rich_click as click

from ._grp import root_grp

if TYPE_CHECKING:
    from vbumper.core.containers.base import VersionContainer
    from vbumper.core.semver import SemVer

    from .context import GlobalOptions


@dataclasses.dataclass(slots=True)
class BumpChainState:
    containers: list[VersionContainer]
    options: GlobalOptions
    current_version: SemVer | None = None
    resolved: bool = False
    changed: bool = False
    read_only: bool = False


Step = Callable[[BumpChainState], None]


def _resolve_lazily(state: BumpChainState) -> SemVer | None:
    """Resolve the aggregate current version across discovered containers, once, memoized.

    Consulted by every bump-family step and by `print`; `set` never triggers it, since assigning
    an explicit target needs no prior agreement to compute from."""

    if not state.resolved:
        from vbumper.core.resolution import resolve_common_version

        state.current_version = resolve_common_version(
            state.containers,
            allow_incompatible_versions=state.options.allow_incompatible_versions,
            skip_unreadable_version_strings=state.options.skip_unreadable_version_strings,
        )
        state.resolved = True

    return state.current_version


def _require_current_version(state: BumpChainState) -> SemVer:
    from vbumper.core.exceptions import NoBaseVersionError

    version = _resolve_lazily(state)
    if version is None:
        raise NoBaseVersionError(
            "No versioned container was discovered to bump from"
            " (use 'set' to assign an explicit version instead)"
        )

    return version


def _require_stable_bump_allowed(state: BumpChainState, current: SemVer) -> None:
    from vbumper.core.exceptions import VBumpError

    if current.prerelease is not None and not state.options.force:
        raise VBumpError(
            "Refusing to bump major/minor/patch on a prerelease version (use --force to proceed)"
        )


def _bump_prerelease(state: BumpChainState, token: str | None) -> None:
    """Shared by `prerelease`/`rc`/`alpha`/`beta`: a first-time prerelease bump (nothing else has
    changed the version yet this invocation) also bumps the patch first, matching legacy."""

    current = _require_current_version(state)
    if current.prerelease is None and not state.changed:
        current = current.bump_patch()

    state.current_version = current.with_advanced_prerelease(token)
    state.changed = True


@root_grp.command()
def patch() -> Step:
    """Increment the patch version."""

    def step(state: BumpChainState) -> None:
        current = _require_current_version(state)
        _require_stable_bump_allowed(state, current)
        state.current_version = current.bump_patch()
        state.changed = True

    return step


@root_grp.command()
def minor() -> Step:
    """Increment the minor version."""

    def step(state: BumpChainState) -> None:
        current = _require_current_version(state)
        _require_stable_bump_allowed(state, current)
        state.current_version = current.bump_minor()
        state.changed = True

    return step


@root_grp.command()
def major() -> Step:
    """Increment the major version."""

    def step(state: BumpChainState) -> None:
        current = _require_current_version(state)
        _require_stable_bump_allowed(state, current)
        state.current_version = current.bump_major()
        state.changed = True

    return step


@root_grp.command()
def prerelease() -> Step:
    """Move into, or advance, a prerelease sequence, using `--prerelease-token` (default "rc")."""

    def step(state: BumpChainState) -> None:
        _bump_prerelease(state, state.options.prerelease_token)

    return step


@root_grp.command()
def alpha() -> Step:
    """Set the prerelease token to "alpha", or advance its serial if already there."""

    def step(state: BumpChainState) -> None:
        _bump_prerelease(state, "alpha")

    return step


@root_grp.command()
def beta() -> Step:
    """Set the prerelease token to "beta", or advance its serial if already there."""

    def step(state: BumpChainState) -> None:
        _bump_prerelease(state, "beta")

    return step


@root_grp.command()
def rc() -> Step:
    """Set the prerelease token to "rc", or advance its serial if already there."""

    def step(state: BumpChainState) -> None:
        _bump_prerelease(state, "rc")

    return step


@root_grp.command()
def lower() -> Step:
    """Advance the prerelease serial if already a prerelease, otherwise bump the patch."""

    def step(state: BumpChainState) -> None:
        current = _require_current_version(state)
        if current.prerelease is not None:
            state.current_version = current.with_advanced_prerelease(None)
        else:
            state.current_version = current.bump_patch()
        state.changed = True

    return step


@root_grp.command()
def stable() -> Step:
    """Drop any prerelease component, keeping the version stable."""

    def step(state: BumpChainState) -> None:
        current = _require_current_version(state)
        state.current_version = current.without_prerelease()
        state.changed = True

    return step


@root_grp.command("set")
@click.argument("version")
def set_(version: str) -> Step:
    """Set an explicit version string, bypassing any existing agreement across containers."""

    def step(state: BumpChainState) -> None:
        from vbumper.core.exceptions import VBumpError
        from vbumper.core.semver import SemVer

        try:
            parsed = SemVer.parse(version)
        except ValueError as exc:
            raise VBumpError(f"{version!r} is not a valid Semantic Version string") from exc

        state.current_version = parsed
        state.changed = True

    return step


@root_grp.command("print")
def print_() -> Step:
    """Print the single common version, or nothing if no container is versioned.

    `print` anywhere in a chain makes the whole invocation read-only: any bump-family command
    chained alongside it still computes what it would produce (so `prerelease print` prints the
    version a real `prerelease` would move to), but nothing is written back and no Git workflow
    runs, regardless of position in the chain."""

    def step(state: BumpChainState) -> None:
        state.read_only = True
        version = _resolve_lazily(state)
        if version is not None:
            click.echo(str(version))

    return step


@root_grp.result_callback()
def _run_chain(steps: list[Step], **_kwargs: object) -> None:
    from vbumper.core.containers.types import Versioned
    from vbumper.core.exceptions import WriteBackFailure
    from vbumper.core.flows import check_preconditions, resolve_selected_flow, run_commands
    from vbumper.core.resolution import containers_to_update, discover_containers

    from ._describe import describe_status as _describe_status
    from .context import get_cli_context

    callable_steps = [step for step in steps if callable(step)]
    if not callable_steps:
        # No bump-family command was chained (e.g. a bare `list`, or `init` with nothing else) --
        # nothing here needs a config to be loaded or containers discovered. This also matters
        # for `-n init`: in dry-run mode it doesn't write a config file at all, and requiring one
        # to exist just to no-op through this callback would defeat the preview.
        return

    ctx = get_cli_context()
    options = ctx.options
    config = ctx.get_config()
    containers = discover_containers(config, path=options.dir)

    state = BumpChainState(containers=containers, options=options)

    for step in callable_steps:
        step(state)

    if state.read_only:
        # `print` was somewhere in the chain -- report only, via its own step's `click.echo`
        # above. No write-back, no flow preconditions/commands, regardless of what else the
        # chain computed.
        return

    if not state.changed:
        return

    assert state.current_version is not None  # `changed` is only set alongside a real value

    selected_flow = resolve_selected_flow(config, flow=options.flow, no_flow=options.no_flow)
    if selected_flow is not None:
        _, flow_config = selected_flow
        check_preconditions(flow_config, allow_dirty_repository=options.allow_dirty_repository)

    target_containers = containers_to_update(
        containers, skip_unreadable_version_strings=options.skip_unreadable_version_strings
    )
    for container in target_containers:
        container.set_status(
            Versioned(value=state.current_version),
            allow_incompatible_versions=options.allow_incompatible_versions,
        )

    changed_containers = [container for container in target_containers if container.has_changed]
    if not changed_containers and selected_flow is None:
        click.echo("Nothing has changed.", err=True)
        return

    if options.dry_run:
        for container in changed_containers:
            old = _describe_status(container.orig_status)
            click.echo(f"Would update {container.describe()}: {old} -> {state.current_version}")
        if selected_flow is not None:
            _, flow_config = selected_flow
            run_commands(
                flow_config.pre_commands,
                version=state.current_version,
                version_tag_prefix=config.version_tag_prefix,
                variables=flow_config.variables,
                dry_run=True,
            )
            run_commands(
                flow_config.post_commands,
                version=state.current_version,
                version_tag_prefix=config.version_tag_prefix,
                variables=flow_config.variables,
                dry_run=True,
            )
        return

    if not changed_containers:
        click.echo("Nothing has changed.", err=True)

    if selected_flow is not None:
        _, flow_config = selected_flow
        run_commands(
            flow_config.pre_commands,
            version=state.current_version,
            version_tag_prefix=config.version_tag_prefix,
            variables=flow_config.variables,
            dry_run=False,
        )

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
        click.echo(f"Updated {container.describe()}: -> {state.current_version}")

    if selected_flow is not None:
        _, flow_config = selected_flow
        run_commands(
            flow_config.post_commands,
            version=state.current_version,
            version_tag_prefix=config.version_tag_prefix,
            variables=flow_config.variables,
            dry_run=False,
        )


__all__ = ["BumpChainState"]
