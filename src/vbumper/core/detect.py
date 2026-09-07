"""Generic auto-detection of built-in discoverer types that need no user-supplied parameters.

Used by `vbump init` to scaffold a starting config, and by `vbump-convert` (a separate,
`vbumper`-dependent project) to fold the same detection into legacy-config migration -- see that
project's own docs for why.
"""

import pathlib


def detect_builtin_discoverers(dir_root: pathlib.Path) -> list[tuple[str, list[str]]]:
    """Return, for every registered discoverer type that (a) needs no user-supplied parameters to
    construct, and (b) actually discovers something under `dir_root`, a pair of its `type:`
    string and the `describe()` of each container it matched (used to annotate a scaffolded entry
    with what it was matched against). Order follows plugin registration order, which is
    deterministic.

    Applies the same built-in `exclude:` defaults (`.venv/`, `node_modules/`, ...) a real run
    would -- there's no project-specific `exclude:` to add on top yet, since this scan is what's
    about to produce the config file that could declare one, but skipping the defaults entirely
    would mean dependencies vendored/installed under an excluded directory (a `setup.py` inside
    `.venv/`, say) could get picked up as false positives."""

    from vbumper.config.root import default_exclude_patterns
    from vbumper.core.plugins.installer import iter_registered_config_classes

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


__all__ = ["detect_builtin_discoverers"]
