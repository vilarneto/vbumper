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
    from vbumper.config.flow import FlowConfig
    from vbumper.config.root import VBumpConfig
    from vbumper.core.semver import SemVer


def resolve_selected_flow(
    config: VBumpConfig, *, flow: str | None, no_flow: bool
) -> tuple[str, FlowConfig] | None:
    """Determine which flow (if any) this run should use, from `--flow`/`--no-flow` and the
    config's `default_flow`. Returns `(key, FlowConfig)`, or `None` if no flow applies.

    `--no-flow` always wins over `--flow`/`default_flow`. An explicit `--flow NAME` (or a
    `default_flow`) that isn't among `config.all_flows` -- plugin-contributed flows plus this
    config's own `flows:` -- is an error; an unset `default_flow` with no `--flow` simply means
    no flow runs (matches the implicit "no flow selected" case).
    """

    from vbumper.core.exceptions import UnknownFlowError

    if no_flow:
        return None

    key = flow if flow is not None else config.default_flow
    if key is None:
        return None

    all_flows = config.all_flows
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
    command: list[str],
    *,
    version: SemVer,
    version_tag_prefix: str,
    variables: dict[str, str] | None = None,
) -> list[str]:
    """Replace the `{VERSION}`/`{VERSION_TAG}` placeholders, plus one `{NAME}` placeholder per
    entry in `variables` (see `substitute_variables`), in each argument of `command`."""

    substitutions = {"{VERSION}": str(version), "{VERSION_TAG}": f"{version_tag_prefix}{version}"}

    def substitute(arg: str) -> str:
        arg = substitute_variables(arg, variables)
        for placeholder, value in substitutions.items():
            arg = arg.replace(placeholder, value)
        return arg

    return [substitute(arg) for arg in command]


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
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
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
            command=["git", "status", "--porcelain"],
            returncode=result.returncode,
        )

    return bool(result.stdout.strip())


def check_preconditions(flow_config: FlowConfig, *, allow_dirty_repository: bool) -> None:
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


def run_commands(
    commands: list[list[str]],
    *,
    version: SemVer,
    version_tag_prefix: str,
    variables: dict[str, str] | None = None,
    dry_run: bool,
) -> None:
    """Run each command in sequence (after placeholder substitution), aborting immediately at the
    first failure -- no rollback of commands already run, consistent with write-back's own
    no-rollback stance on container write failures.

    `--dry-run` prints `Would execute: ...` for each command instead of running it.
    """

    import rich_click as click

    from vbumper.core.exceptions import FlowCommandFailure

    for command in commands:
        argv = substitute_placeholders(
            command,
            version=version,
            version_tag_prefix=version_tag_prefix,
            variables=variables,
        )

        if dry_run:
            click.echo(f"Would execute: {' '.join(argv)}")
            continue

        env = os.environ | {"GIT_MERGE_AUTOEDIT": "no"}
        result = subprocess.run(argv, env=env)
        if result.returncode != 0:
            raise FlowCommandFailure(
                f"Command failed with exit code {result.returncode}: {' '.join(argv)}",
                command=argv,
                returncode=result.returncode,
            )


__all__ = [
    "check_preconditions",
    "current_branch",
    "is_repository_dirty",
    "resolve_selected_flow",
    "run_commands",
    "substitute_placeholders",
    "substitute_variables",
]
