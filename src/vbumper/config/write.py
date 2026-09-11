"""Round-trip editing of an existing `.vbump.yaml`/`.vbump.yml`: injecting or refreshing one
`flows:` entry (and optionally `default_flow:`), while preserving every other comment, blank
line, and key order already in the file.

Used only by `vbump flow add`: the one command that materializes a `~/.vbumpconfig.yaml`
template into an *existing*, already-commented project config. Deliberately separate from
`vbumper.config.load`'s `typ="safe"` validating loader: that one parses a file into plain Python
values for pydantic validation and throws away all formatting; this one keeps the formatting and
is never used to validate anything: `flow add` validates the merged `FlowDefinition` itself
(via `load_config`/`FlowDefinition.model_validate`) before this module is ever touched, so a
failure never leaves a half-edited file (see `set_flow_entry`)."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ruamel.yaml.comments import CommentedMap

    from .flow import FlowDefinition

#: Keys that may precede `default_flow:`/`flows:` in a conventionally-ordered `.vbump.yaml`,
#: checked in this order to decide where a freshly-added key should land (right after the last
#: one of these actually present, or at the very top if none are). Purely cosmetic: the config
#: parses identically regardless of key order.
_PRECEDING_KEYS = ("version", "version_tag_prefix", "default_flow")


def load_raw_for_edit(path: str | Path) -> CommentedMap:
    """Round-trip parse `path` (an existing `.vbump.yaml`/`.vbump.yml`), preserving comments,
    blank lines, and key order for anything `set_flow_entry`/`set_default_flow` don't explicitly
    touch."""

    from ruamel.yaml import YAML, YAMLError

    from .load import raise_configuration_error

    path = Path(path)
    yaml = YAML()
    with path.open("rt", encoding="utf-8") as fd:
        try:
            raw = yaml.load(fd)
        except YAMLError as exc:
            raise_configuration_error(path, exc)
            raise  # pragma: no cover (raise_configuration_error always raises)

    from ruamel.yaml.comments import CommentedMap

    return raw if raw is not None else CommentedMap()


def _insert_after(raw: CommentedMap, key: str, value: object, *, after: tuple[str, ...]) -> None:
    """Insert `key: value` into `raw`, right after the last of `after` that's actually present in
    it, or at the very top if none are."""

    position = 0
    for index, existing_key in enumerate(raw.keys()):
        if existing_key in after:
            position = index + 1
    raw.insert(position, key, value)


def set_flow_entry(raw: CommentedMap, key: str, flow: FlowDefinition) -> None:
    """Insert or overwrite `raw["flows"][key]` with `flow`'s fields, creating a `flows:` mapping
    (positioned after `version`/`version_tag_prefix`/`default_flow`, matching where `vbump init`
    would put it) if the file doesn't have one yet. Every other entry already under `flows:`, and
    everywhere else in `raw`, is left untouched.

    `flow` must already be the fully-resolved, validated definition to write: merging template
    fields, prior local `variables`, and any `--set` overrides is `vbump flow add`'s job, not
    this function's."""

    from ruamel.yaml.comments import CommentedMap

    flows = raw.get("flows")
    if flows is None:
        flows = CommentedMap()
        _insert_after(raw, "flows", flows, after=_PRECEDING_KEYS)

    flows[key] = flow.model_dump(exclude_none=True, exclude_defaults=True)


def set_default_flow(raw: CommentedMap, key: str) -> None:
    """Set `raw["default_flow"]` to `key`, inserting it (positioned after `version`/
    `version_tag_prefix`, before `flows:`) if it isn't already present."""

    if "default_flow" in raw:
        raw["default_flow"] = key
        return

    _insert_after(raw, "default_flow", key, after=("version", "version_tag_prefix"))


def dump_raw(raw: CommentedMap, path: str | Path) -> None:
    """Write `raw` back to `path`, using the same writer settings `vbump-convert` uses for a
    freshly-generated file (2-space mapping indent, 4-space/2-offset sequences, block style)."""

    from ruamel.yaml import YAML

    writer = YAML()
    writer.default_flow_style = False
    writer.indent(mapping=2, sequence=4, offset=2)

    with Path(path).open("wt", encoding="utf-8") as fd:
        writer.dump(raw, fd)


__all__ = [
    "dump_raw",
    "load_raw_for_edit",
    "set_default_flow",
    "set_flow_entry",
]
