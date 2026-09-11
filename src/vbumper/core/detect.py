"""Generic auto-detection of built-in discoverer types that need no user-supplied parameters.

Used by `vbump init` to scaffold a starting config, and by `vbump-convert` (a separate,
`vbumper`-dependent project) to fold the same detection into legacy-config migration; see that
project's own docs for why.
"""

import pathlib
from typing import Any


def detect_builtin_discoverers(
    dir_root: pathlib.Path,
) -> list[tuple[str, list[str], dict[str, Any]]]:
    """Return, for every registered discoverer type that (a) needs no user-supplied parameters to
    construct, and (b) actually discovers something under `dir_root`, one or more
    `(type_name, descriptions, extra_fields)` triples describing a `discoverers:` entry to
    scaffold: `descriptions` becomes one `# ...` comment per matched container, and
    `extra_fields` (usually empty) becomes additional `key: value` lines under the entry's own
    `- type: ...`. Order follows plugin registration order, which is deterministic.

    Almost every built-in yields exactly one triple with an empty `extra_fields`, from a single
    zero-config instance (`from_config_dict({})`) covering everything it matched. A config class
    that instead needs one *separate* entry per distinct thing it found (e.g. `xcode-pbxproj`,
    scaffolding one entry per Xcode target rather than one entry for all of them) may define an
    `iter_auto_detected(*, dir_root, path_exclude_patterns) -> Iterator[tuple[list[str], dict]]`
    classmethod instead; when present, it is used in place of the default single-instance path,
    yielding one `(descriptions, extra_fields)` pair per entry to scaffold. This is an optional
    hook a config class may implement, not a required part of `DiscovererConfigProtocol` -- most
    types have no use for it.

    Applies the same built-in `exclude:` defaults (`.venv/`, `node_modules/`, ...) a real run
    would: there's no project-specific `exclude:` to add on top yet, since this scan is what's
    about to produce the config file that could declare one, but skipping the defaults entirely
    would mean dependencies vendored/installed under an excluded directory (a `setup.py` inside
    `.venv/`, say) could get picked up as false positives.

    Every matched container's `describe()` reports a path relative to `dir_root` itself
    (`AbstractFileDiscoverer`'s own `file_path`/`display_path` split -- see
    `vbumper.core.files.discoverer`), regardless of whether `dir_root` was given as an absolute
    path, a relative one, or the default `.`. Without that, an absolute `--dir` would otherwise
    embed the full local filesystem path (username and all) into the scaffolded config's
    comments, a bad default for a file meant to be committed and shared."""

    from vbumper.config.root import default_exclude_patterns
    from vbumper.core.plugins.installer import iter_registered_config_classes

    exclude_patterns = default_exclude_patterns()
    detected: list[tuple[str, list[str], dict[str, Any]]] = []

    for config_cls in iter_registered_config_classes():
        iter_auto_detected = getattr(config_cls, "iter_auto_detected", None)
        if iter_auto_detected is not None:
            for descriptions, extra_fields in iter_auto_detected(
                dir_root=dir_root, path_exclude_patterns=exclude_patterns
            ):
                detected.append((config_cls.get_type(), descriptions, extra_fields))
            continue

        try:
            config_instance = config_cls.from_config_dict({})
        except Exception:
            # Requires parameters this scan can't guess (e.g. `file-regexp`'s `include:`):
            # not an auto-detectable built-in, skip it silently.
            continue

        discoverer = config_instance.create_discoverer(
            path_exclude_patterns=exclude_patterns, dir_root=dir_root
        )
        descriptions = [container.describe() for container in discoverer.discover()]
        if descriptions:
            detected.append((config_cls.get_type(), descriptions, {}))

    return detected


__all__ = ["detect_builtin_discoverers"]
