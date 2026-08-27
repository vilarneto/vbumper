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


def _detect_builtin_types(dir_option: str) -> list[tuple[str, list[str]]]:
    """Return, for every registered discoverer type that (a) needs no user-supplied parameters to
    construct, and (b) actually discovers something under `dir_option`, a pair of its `type:`
    string and the `describe()` of each container it matched (used to annotate the scaffolded
    entry with what it was matched against). Order follows plugin registration order, which is
    deterministic.

    Applies the same built-in `exclude:` defaults (`.venv/`, `node_modules/`, ...) a real run
    would -- there's no project-specific `exclude:` to add on top yet, since this scan is what's
    about to produce the config file that could declare one, but skipping the defaults entirely
    would mean dependencies vendored/installed under an excluded directory (a `setup.py` inside
    `.venv/`, say) could get picked up as false positives."""

    from vbumper.config.root import default_exclude_patterns
    from vbumper.core.plugins.installer import iter_registered_config_classes

    dir_root = pathlib.Path(dir_option)
    exclude_patterns = default_exclude_patterns()
    detected: list[tuple[str, list[str]]] = []

    for config_cls in iter_registered_config_classes():
        try:
            config_instance = config_cls.from_config_dict({})
        except Exception:
            # Requires parameters this scan can't guess (e.g. `file-regexp`'s `include:`) --
            # not an auto-detectable built-in, skip it silently.
            continue

        discoverer = config_instance.create_discoverer(
            path_exclude_patterns=exclude_patterns, dir_root=dir_root
        )
        descriptions = [container.describe() for container in discoverer.discover()]
        if descriptions:
            detected.append((config_cls.get_type(), descriptions))

    return detected


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

    from .context import get_options

    options = get_options()
    config_path = _target_config_path(options.dir)

    existing = find_config_path(options.dir)
    if existing is not None:
        raise click.UsageError(f"{existing} already exists -- not overwriting it.")

    detected = _detect_builtin_types(options.dir)
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
