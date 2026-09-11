"""`vbump init`: scaffold a starting `.vbump.yaml`.

Every discoverer is opt-in (see `vbumper.core.resolution.discover_containers`), so a fresh
project needs an explicit config file before `vbump` finds anything at all. `init` closes that
gap: it writes a `version: 3` config pre-populated with a `- type: ...` entry for each built-in
discoverer type that actually finds something in the target directory (occasionally more than
one entry per type; see `vbumper.core.detect.detect_builtin_discoverers`), so first-run UX stays
close to what a zero-config scan used to give for free, but explicit and reviewable rather than
implicit.

Deliberately not a chained `Step`-returning command like the bump family (see `.bump`): it does
its one job (write a file) eagerly in its own callback and returns nothing, so it can't be
meaningfully combined with `patch`/`minor`/etc. in one invocation.
"""

import pathlib
from typing import TYPE_CHECKING, Any

import rich_click as click

from ._grp import root_grp

if TYPE_CHECKING:
    from vbumper.config.flow import FlowDefinition


def _target_config_path(dir_option: str) -> pathlib.Path:
    """`dir_option` must name a directory (`--dir`/`-d` only ever accepts one)."""

    return pathlib.Path(dir_option) / ".vbump.yaml"


def _render_flows_section(flows: "dict[str, FlowDefinition]") -> str:
    """Render a `flows:` block for `flows`, via a plain (non-round-trip) `ruamel.yaml` dump.
    Unlike `discoverers:`'s hand-built lines below, a flow's fields (arbitrary shell commands,
    variable values) can contain YAML-special characters a naive `f"{key}: {value}"` line would
    mangle, so this always goes through a real YAML writer instead."""

    import io

    from ruamel.yaml import YAML

    writer = YAML()
    writer.default_flow_style = False
    writer.indent(mapping=2, sequence=4, offset=2)

    data = {
        "flows": {
            key: flow.model_dump(exclude_none=True, exclude_defaults=True)
            for key, flow in flows.items()
        }
    }
    buffer = io.StringIO()
    writer.dump(data, buffer)
    return buffer.getvalue()


def _render_config(
    detected: list[tuple[str, list[str], dict[str, Any]]], flows: "dict[str, FlowDefinition]"
) -> str:
    import json

    from vbumper.config.root import CONFIG_VERSION, config_header_comment

    lines = [config_header_comment(), f"version: {CONFIG_VERSION}", ""]
    if flows:
        lines.append(_render_flows_section(flows).rstrip("\n"))
        lines.append("")
    if detected:
        lines.append("discoverers:")
        for type_name, descriptions, extra_fields in detected:
            lines.extend(f"  # {description}" for description in descriptions)
            lines.append(f"  - type: {type_name}")
            # `json.dumps` doubles as a safe, always-valid-YAML-flow-scalar renderer here (JSON
            # is a subset of YAML), so a value with special characters (e.g. a target name with a
            # colon or quote in it) can never corrupt the hand-built lines around it.
            for key, value in extra_fields.items():
                lines.append(f"    {key}: {json.dumps(value)}")
    else:
        lines.append("# No built-in discoverer matched anything under this directory.")
        lines.append("# Add entries here (see the README's built-in and file-regexp recipes).")
        lines.append("discoverers: []")
    lines.append("")
    return "\n".join(lines)


def _resolve_requested_flows(raw: str | None) -> "dict[str, FlowDefinition]":
    """Look up each comma-separated name in `raw` against `~/.vbumpconfig.yaml`'s own `flows:`,
    all-or-nothing: an unknown name fails before anything is written, so `init` never leaves a
    half-populated file behind."""

    from vbumper.config.flow import FLOW_KEY_PATTERN
    from vbumper.config.global_config import load_global_config

    if not raw:
        return {}

    names = [name.strip() for name in raw.split(",") if name.strip()]
    for name in names:
        if not FLOW_KEY_PATTERN.match(name):
            raise click.UsageError(
                f"--flows: {name!r} is not a valid flow name (lowercase letters, digits,"
                " hyphens, starting with a letter)."
            )

    global_flows = load_global_config().flows
    unknown = [name for name in names if name not in global_flows]
    if unknown:
        available = ", ".join(sorted(global_flows)) or "(none)"
        raise click.UsageError(
            f"--flows: {', '.join(unknown)} not defined in ~/.vbumpconfig.yaml"
            f" (available: {available})."
        )

    return {name: global_flows[name] for name in names}


@root_grp.command()
@click.option(
    "--flows",
    default=None,
    metavar="NAME[,NAME...]",
    help="Copy these named flows from ~/.vbumpconfig.yaml into the new .vbump.yaml, as full"
    " standalone entries.",
)
def init(flows: str | None) -> None:
    """Scaffold a starting `.vbump.yaml`, pre-populated with any built-in discoverer types that
    match files already present."""

    from vbumper.config.load import find_config_path
    from vbumper.core.detect import detect_builtin_discoverers

    from .context import get_options

    options = get_options()
    config_path = _target_config_path(options.dir)

    existing = find_config_path(options.dir)
    if existing is not None:
        raise click.UsageError(f"{existing} already exists; not overwriting it.")

    requested_flows = _resolve_requested_flows(flows)
    detected = detect_builtin_discoverers(pathlib.Path(options.dir))
    contents = _render_config(detected, requested_flows)

    if options.dry_run:
        click.echo(f"Would write {config_path}:")
        click.echo(contents)
        return

    config_path.write_text(contents, encoding="utf-8")
    click.echo(f"Wrote {config_path}")
    if requested_flows:
        click.echo("Added flows: " + ", ".join(requested_flows))
    if detected:
        click.echo("Detected discoverers: " + ", ".join(type_name for type_name, _, _ in detected))
    else:
        click.echo(
            "No built-in discoverer matched anything here; edit discoverers: by hand"
            " (see the README)."
        )


__all__ = ["init"]
