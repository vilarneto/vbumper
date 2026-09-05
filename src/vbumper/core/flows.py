"""The Git release-workflow engine: resolving which `FlowConfig` (if any) a run should use, its
preconditions (clean working tree, starting branch), and executing its `pre_commands`/
`post_commands` around write-back.

By design, the engine treats every flow -- built-in or user-defined -- identically: nothing here
branches on a flow's name or key, and every global option (`--dry-run`, `--allow-dirty-repository`,
...) applies uniformly regardless of which flow is selected. `vbumper.cli.bump` is what wires this
into the chain group's `result_callback`.
"""

import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vbumper.config.flow import FlowDefinition
    from vbumper.config.root import VBumpConfig
    from vbumper.core.containers.base import VersionContainer
    from vbumper.core.semver import SemVer


def resolve_selected_flow(
    config: VBumpConfig, *, flow: str | None, no_flow: bool
) -> tuple[str, FlowDefinition] | None:
    """Determine which flow (if any) this run should use, from `--flow`/`--no-flow` and the
    config's `default_flow`. Returns `(key, FlowDefinition)`, or `None` if no flow applies.

    `--no-flow` always wins over `--flow`/`default_flow`. An explicit `--flow NAME` (or a
    `default_flow`) that isn't among the project's own `flows:` (resolved against
    `~/.vbumpconfig.yaml` for any `recall:` entries) is an error; an unset `default_flow` with no
    `--flow` simply means no flow runs (matches the implicit "no flow selected" case).
    """

    from vbumper.config.global_config import load_global_config
    from vbumper.config.root import resolve_all_flows
    from vbumper.core.exceptions import UnknownFlowError

    if no_flow:
        return None

    key = flow if flow is not None else config.default_flow
    if key is None:
        return None

    all_flows = resolve_all_flows(config.flows, load_global_config().flows)
    flow_config = all_flows.get(key)
    if flow_config is None:
        raise UnknownFlowError(
            f"Unknown flow {key!r} (available flows: {', '.join(sorted(all_flows)) or '(none)'})"
        )

    return key, flow_config


def substitute_variables(text: str, variables: dict[str, str] | None) -> str:
    """Replace one `{NAME}` placeholder per entry in `variables` in `text`. A `{NAME}` referenced
    without a matching entry is left as literal, unreplaced text.

    The one substitution rule shared by every placeholder-bearing flow field -- command arguments
    (via `substitute_placeholders`) and `FlowConfig.require_on_branch` (via `check_preconditions`)
    both go through this, so a flow's `variables:` is a single source of truth for a name like
    `{DEVELOP_BRANCH}` wherever it's referenced, not a value that can drift between two independent
    copies."""

    for name, value in (variables or {}).items():
        text = text.replace(f"{{{name}}}", value)
    return text


def substitute_placeholders(
    command: str,
    *,
    version: SemVer,
    version_tag_prefix: str,
    variables: dict[str, str] | None = None,
    changed_file: str | None = None,
) -> str:
    """Replace the `{VERSION}`/`{VERSION_TAG}` placeholders, plus one `{NAME}` placeholder per
    entry in `variables` (see `substitute_variables`), in `command`. Substitution is verbatim --
    no substituted value is quoted or escaped on the command's behalf.

    `changed_file`, when given, additionally substitutes `{CHANGED_FILE}` -- meaningful only for
    `stage_command` (see `run_stage_command`); left as literal, unreplaced text otherwise, the
    same as an unmatched custom `{NAME}` variable."""

    substitutions = {"{VERSION}": str(version), "{VERSION_TAG}": f"{version_tag_prefix}{version}"}
    if changed_file is not None:
        substitutions["{CHANGED_FILE}"] = changed_file

    command = substitute_variables(command, variables)
    for placeholder, value in substitutions.items():
        command = command.replace(placeholder, value)
    return command


def current_branch() -> str:
    """The repository's current branch name, via `git rev-parse --abbrev-ref HEAD`."""

    from vbumper.core.exceptions import FlowCommandFailure

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise FlowCommandFailure(
            "Could not determine the current Git branch"
            f" ({result.stderr.strip() or 'git rev-parse failed'})",
            command="git rev-parse --abbrev-ref HEAD",
            returncode=result.returncode,
        )

    return result.stdout.strip()


def is_repository_dirty() -> bool:
    """Whether the working tree has any uncommitted changes, via `git status --porcelain`."""

    from vbumper.core.exceptions import FlowCommandFailure

    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if result.returncode != 0:
        error = result.stderr.strip() or "git status failed"
        raise FlowCommandFailure(
            f"Could not inspect the Git working tree ({error})",
            command="git status --porcelain",
            returncode=result.returncode,
        )

    return bool(result.stdout.strip())


def check_preconditions(flow_config: FlowDefinition, *, allow_dirty_repository: bool) -> None:
    """Enforce the flow's preconditions: a clean working tree (unless overridden) and, if
    `require_on_branch` is set, that the repository is currently on that branch.

    `require_on_branch` is substituted against the flow's own `variables` (via
    `substitute_variables`) before comparison, the same as any command argument -- so a flow
    written as `require_on_branch: "{DEVELOP_BRANCH}"` never holds a second, independent copy of
    a branch name that could drift out of sync with `variables.DEVELOP_BRANCH`.

    Always enforced, regardless of `--dry-run` -- these are real facts about repository state
    a preview should still surface, not mutating actions dry-run is meant to skip.
    """

    from vbumper.core.exceptions import DirtyRepositoryError, WrongBranchError

    if not allow_dirty_repository and is_repository_dirty():
        raise DirtyRepositoryError(
            "Refusing to run a Git workflow with a dirty working tree"
            " (use --allow-dirty-repository to proceed)"
        )

    if flow_config.require_on_branch is not None:
        required_branch = substitute_variables(flow_config.require_on_branch, flow_config.variables)
        branch = current_branch()
        if branch != required_branch:
            raise WrongBranchError(
                f"This flow requires branch {required_branch!r},"
                f" but the current branch is {branch!r}"
            )


def _execute_or_preview(substituted: str, *, dry_run: bool) -> None:
    """Either print `Would execute: ...` for `substituted` (dry-run), or actually run it through
    the operating system's own command shell, raising `FlowCommandFailure` on a non-zero exit.

    Shared by `run_commands` and `run_stage_command` so both follow identical execution/
    dry-run/failure semantics."""

    import rich_click as click

    from vbumper.core.exceptions import FlowCommandFailure

    if dry_run:
        click.echo(f"Would execute: {substituted}")
        return

    env = os.environ | {"GIT_MERGE_AUTOEDIT": "no"}
    result = subprocess.run(substituted, shell=True, env=env)
    if result.returncode != 0:
        raise FlowCommandFailure(
            f"Command failed with exit code {result.returncode}: {substituted}",
            command=substituted,
            returncode=result.returncode,
        )


def run_commands(
    commands: list[str],
    *,
    version: SemVer,
    version_tag_prefix: str,
    variables: dict[str, str] | None = None,
    dry_run: bool,
) -> None:
    """Run each command in sequence (after placeholder substitution), aborting immediately at the
    first failure -- no rollback of commands already run, consistent with write-back's own
    no-rollback stance on container write failures.

    Each command runs through the operating system's own command shell (`/bin/sh` on Unix-like
    systems, `cmd.exe` on Windows) -- a sequence meant to behave identically on both needs to
    stick to syntax both shells understand, or be split into separate, simpler commands.

    `--dry-run` prints `Would execute: ...` for each command instead of running it.
    """

    for command in commands:
        substituted = substitute_placeholders(
            command,
            version=version,
            version_tag_prefix=version_tag_prefix,
            variables=variables,
        )
        _execute_or_preview(substituted, dry_run=dry_run)


def run_stage_command(
    stage_command: str | None,
    containers: list[VersionContainer],
    *,
    version: SemVer,
    version_tag_prefix: str,
    variables: dict[str, str] | None = None,
    dry_run: bool,
) -> None:
    """Run `stage_command` once per file-backed container in `containers` (in order), with
    `{CHANGED_FILE}` substituted to that container's own `file_path`. A container whose
    `file_path` is `None` (not file-backed) is skipped.

    A no-op if `stage_command` is `None` -- vbumper never stages anything unless a flow opts in
    explicitly, and never touches anything beyond the exact files it just wrote itself. Runs
    strictly after write-back and before `post_commands`; see `vbumper.cli.bump._run_chain`.

    `--dry-run` previews each would-be invocation via `Would execute: ...`, same as
    `run_commands`, without running anything or requiring the containers to have actually been
    written.
    """

    if stage_command is None:
        return

    for container in containers:
        file_path = container.file_path
        if file_path is None:
            continue

        substituted = substitute_placeholders(
            stage_command,
            version=version,
            version_tag_prefix=version_tag_prefix,
            variables=variables,
            changed_file=str(file_path),
        )
        _execute_or_preview(substituted, dry_run=dry_run)


__all__ = [
    "check_preconditions",
    "current_branch",
    "is_repository_dirty",
    "resolve_selected_flow",
    "run_commands",
    "run_stage_command",
    "substitute_placeholders",
    "substitute_variables",
]
