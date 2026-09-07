"""`vbump init`: scaffold a starting `.vbump.yaml`.

Every discoverer is opt-in (see `vbumper.core.resolution.discover_containers`), so a fresh
project needs an explicit config file before `vbump` finds anything at all. `init` closes that
gap: it writes a `version: 3` config pre-populated with a `- type: ...` entry for each built-in
discoverer type that actually finds something in the target directory, so first-run UX stays
close to what a zero-config scan used to give for free -- but explicit and reviewable rather than
implicit.

Deliberately not a chained `Step`-returning command like the bump family (see `.bump`): it does
its one job (write a file) eagerly in its own callback and returns nothing, so it can't be
meaningfully combined with `patch`/`minor`/etc. in one invocation.
"""

import pathlib

import rich_click as click

from ._grp import root_grp


def _target_config_path(dir_option: str) -> pathlib.Path:
    """`dir_option` must name a directory -- `--dir`/`-d` only ever accepts one."""

    return pathlib.Path(dir_option) / ".vbump.yaml"


def _render_config(detected: list[tuple[str, list[str]]]) -> str:
    from vbumper.config.root import CONFIG_VERSION

    lines = [f"version: {CONFIG_VERSION}", ""]
    if detected:
        lines.append("discoverers:")
        for type_name, descriptions in detected:
            lines.extend(f"  # {description}" for description in descriptions)
            lines.append(f"  - type: {type_name}")
    else:
        lines.append("# No built-in discoverer matched anything under this directory.")
        lines.append("# Add entries here -- see the README's built-in and file-regexp recipes.")
        lines.append("discoverers: []")
    lines.append("")
    return "\n".join(lines)


@root_grp.command()
def init() -> None:
    """Scaffold a starting `.vbump.yaml`, pre-populated with any built-in discoverer types that
    match files already present."""

    from vbumper.config.load import find_config_path
    from vbumper.core.detect import detect_builtin_discoverers

    from .context import get_options

    options = get_options()
    config_path = _target_config_path(options.dir)

    existing = find_config_path(options.dir)
    if existing is not None:
        raise click.UsageError(f"{existing} already exists -- not overwriting it.")

    detected = detect_builtin_discoverers(pathlib.Path(options.dir))
    contents = _render_config(detected)

    if options.dry_run:
        click.echo(f"Would write {config_path}:")
        click.echo(contents)
        return

    config_path.write_text(contents, encoding="utf-8")
    click.echo(f"Wrote {config_path}")
    if detected:
        click.echo("Detected discoverers: " + ", ".join(type_name for type_name, _ in detected))
    else:
        click.echo(
            "No built-in discoverer matched anything here -- edit discoverers: by hand"
            " (see the README)."
        )


__all__ = ["init"]
