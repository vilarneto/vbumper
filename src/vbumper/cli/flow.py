"""`vbump flow add`: copy a named flow template from `~/.vbumpconfig.yaml` into the current
project's own `.vbump.yaml`, as a full, standalone `FlowDefinition`. Once copied, no runtime
dependency on `~/.vbumpconfig.yaml` survives: `vbumper.core.flows.resolve_selected_flow` never
reads it, so a project's `.vbump.yaml` stays self-contained for anyone who clones it.

`flow` cannot be a true nested `click.Group` under `root_grp`: Click categorically refuses to add
a `Group` as a subcommand of a chain-mode group. It also can't simply declare `add`/`NAME` as its
own positional arguments alongside `--update`/`--set`/`--set-default` options: a chain group
parses each subcommand with `allow_interspersed_args=False`, so any option written *after* a
positional argument is mistaken for the start of the next chained command instead. `flow` works
around both restrictions by registering as a single, argument-swallowing `root_grp` command
(`args: tuple[str, ...]`, `type=click.UNPROCESSED`) that dispatches by hand into `add_command`,
an ordinary, independently-parsed `click.Command` invoked via `.main(..., standalone_mode=False)`,
a fresh parse with normal (non-chain) option/argument ordering rules, so
`vbump flow add NAME --set NAME=value` reads exactly as expected. It does its one job (edit a
file) eagerly and returns `None`, the same as `init`/`list`: it is not part of the chained bump
pipeline.
"""

import rich_click as click

from ._grp import root_grp


def _parse_set_option(raw: str) -> tuple[str, str]:
    """Split a `--set NAME=value` argument, rejecting anything not in that shape."""

    name, separator, value = raw.partition("=")
    if not separator or not name:
        raise click.UsageError(f"--set {raw!r} is not in NAME=value form.")
    return name, value


def _validate_variable_name(name: str) -> None:
    from vbumper.config.flow import RESERVED_VARIABLE_NAMES, VARIABLE_NAME_PATTERN

    if name in RESERVED_VARIABLE_NAMES:
        raise click.UsageError(
            f"--set {name}=...: {name} is reserved for vbumper's own placeholders."
        )
    if not VARIABLE_NAME_PATTERN.match(name):
        raise click.UsageError(
            f"--set {name}=...: {name!r} is not a valid variable name"
            " (uppercase letters, digits, underscore, starting with a letter)."
        )


def _add(name: str, *, update: bool, set_: tuple[str, ...], set_default: bool) -> None:
    from vbumper.config.flow import FLOW_KEY_PATTERN, FlowDefinition
    from vbumper.config.global_config import load_global_config
    from vbumper.config.load import find_config_path
    from vbumper.config.write import dump_raw, load_raw_for_edit, set_default_flow, set_flow_entry

    from .context import get_config, get_options

    options = get_options()

    if not FLOW_KEY_PATTERN.match(name):
        raise click.UsageError(
            f"{name!r} is not a valid flow name (lowercase letters, digits, hyphens, starting"
            " with a letter)."
        )

    config_path = find_config_path(options.dir)
    if config_path is None:
        raise click.UsageError(
            f"No .vbump.yaml/.vbump.yml found in {options.dir}; run “vbump init” first."
        )

    global_config = load_global_config()
    template = global_config.flows.get(name)
    if template is None:
        available = ", ".join(sorted(global_config.flows)) or "(none)"
        raise click.UsageError(
            f"No flow {name!r} defined in ~/.vbumpconfig.yaml (available: {available})."
        )

    existing = get_config().flows.get(name)
    if existing is not None and not update:
        raise click.UsageError(
            f"flows.{name} already exists in {config_path}; use --update to refresh it."
        )

    overrides: dict[str, str] = {}
    for raw_set in set_:
        var_name, value = _parse_set_option(raw_set)
        _validate_variable_name(var_name)
        overrides[var_name] = value

    variables = dict(template.variables)
    if update and existing is not None:
        variables.update(existing.variables)
    variables.update(overrides)

    # `model_copy` bypasses validation, so re-validate the merged result explicitly: it's the
    # only field being computed here rather than copied verbatim from an already-valid source.
    merged = FlowDefinition.model_validate(
        {**template.model_dump(exclude={"variables"}), "variables": variables}
    )

    rendered = merged.model_dump(exclude_none=True, exclude_defaults=True)
    if options.dry_run:
        click.echo(f"Would write flows.{name} in {config_path}:")
        click.echo(rendered)
        if set_default:
            click.echo(f"Would set default_flow: {name}")
        return

    raw_doc = load_raw_for_edit(config_path)
    set_flow_entry(raw_doc, name, merged)
    if set_default:
        set_default_flow(raw_doc, name)
    dump_raw(raw_doc, config_path)

    click.echo(f"{'Updated' if existing is not None else 'Added'} flows.{name} in {config_path}")
    if set_default:
        click.echo(f"Set default_flow: {name}")


@click.command("add")
@click.argument("name")
@click.option(
    "--update",
    is_flag=True,
    default=False,
    help="Refresh an already-added flow of this name from the template, preserving its own"
    " `variables` (re)definitions.",
)
@click.option(
    "--set",
    "set_",
    multiple=True,
    metavar="NAME=value",
    help="Override one flow variable in the copy (repeatable).",
)
@click.option(
    "--set-default",
    is_flag=True,
    default=False,
    help="Also set this flow as the project's `default_flow:`.",
)
def add_command(name: str, update: bool, set_: tuple[str, ...], set_default: bool) -> None:
    """Copy NAME from `~/.vbumpconfig.yaml`'s own `flows:` into this project's `.vbump.yaml`, as
    a full, standalone flow."""

    _add(name, update=update, set_=set_, set_default=set_default)


@root_grp.command(
    "flow",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    add_help_option=False,
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def flow(args: tuple[str, ...]) -> None:
    """Manage named Git-workflow `flows:` entries in the current project's `.vbump.yaml`.

    Currently one subcommand: `add NAME` (see `vbump flow add --help`).
    """

    if args and args[0] in ("-h", "--help"):
        click.echo("Usage: vbump flow add NAME [OPTIONS]\n\nSee: vbump flow add --help")
        return

    if not args or args[0] != "add":
        raise click.UsageError("Usage: vbump flow add NAME [OPTIONS] (see --help)")

    add_command.main(
        args=list(args[1:]),
        prog_name="vbump flow add",
        standalone_mode=False,
        parent=click.get_current_context(),
    )


#: Exposed (no leading underscore) so `docs/cli/index.rst` can document it directly via its own
#: `sphinx-click` directive: `flow` itself, being an argument-swallowing dispatcher, would
#: otherwise auto-document as a bare, optionless `[ARGS]...` command with no trace of `--update`/
#: `--set`/`--set-default` (see the module docstring for why `add` can't be a real Click
#: subcommand of `flow` here).
__all__ = ["add_command", "flow"]
