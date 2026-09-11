"""Loading `~/.vbumpconfig.yaml`: an optional, per-user file holding reusable named flow
*templates*, so the same flow needn't be redefined by hand in every project.

This file is a template library only: it is never consulted at `bump` time (see
`vbumper.core.flows.resolve_selected_flow`, which looks only at a project's own `flows:`). It is
read solely by `vbump flow add`/`vbump init --flows`, which copy a named template into a
project's own `.vbump.yaml` as a full, standalone flow. A single fixed location is checked, no
directory is searched, and no other file name or location is recognized. A project that has never
run `flow add`/`init --flows` is entirely unaffected by whether this file exists or what it
contains.
"""

from pathlib import Path

import pydantic

from .flow import FlowDefinition, FlowKey

#: Schema version marker for this (global) config format, independent of `VBumpConfig`'s own:
#: kept as a distinct constant since the two files could in principle diverge in the future, even
#: though both currently only ever accept `3`.
GLOBAL_CONFIG_VERSION = 3


class GlobalConfig(pydantic.BaseModel):
    """Root of `~/.vbumpconfig.yaml`. Every flow here is a full, standalone `FlowDefinition`:
    a template `vbump flow add`/`vbump init --flows` can copy into a project, never something a
    project references live."""

    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    version: int = GLOBAL_CONFIG_VERSION
    flows: dict[FlowKey, FlowDefinition] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("version")
    @classmethod
    def _require_current_version(cls, value: int) -> int:
        if value != GLOBAL_CONFIG_VERSION:
            raise ValueError(
                f"Unsupported config version {value!r}; this format requires"
                f" version: {GLOBAL_CONFIG_VERSION}."
            )
        return value

    @classmethod
    def empty(cls) -> "GlobalConfig":
        """What a missing `~/.vbumpconfig.yaml` is treated as: no global flows at all."""

        return cls()


def find_global_config_path() -> Path | None:
    """The path to `~/.vbumpconfig.yaml`, or `None` if it doesn't exist. A single fixed location:
    no search, no alternate file name."""

    candidate = Path.home() / ".vbumpconfig.yaml"
    return candidate if candidate.is_file() else None


def load_global_config() -> GlobalConfig:
    """Load `~/.vbumpconfig.yaml`. A missing file is not an error: it's treated the same as one
    that exists but declares no flows. A present but malformed or wrong-version file is a
    `ConfigurationError`, the same as a project's own `.vbump.yaml`."""

    from ruamel.yaml import YAML, YAMLError

    from vbumper.config.load import raise_configuration_error

    path = find_global_config_path()
    if path is None:
        return GlobalConfig.empty()

    yaml = YAML(typ="safe")
    with path.open("rt", encoding="utf-8") as fd:
        try:
            raw = yaml.load(fd)
        except YAMLError as exc:
            raise_configuration_error(path, exc)
            raise  # pragma: no cover (raise_configuration_error always raises)

    raw = raw if raw is not None else {}

    try:
        return GlobalConfig.model_validate(raw)
    except pydantic.ValidationError as exc:
        raise_configuration_error(path, exc)
        raise  # pragma: no cover (raise_configuration_error always raises)


__all__ = [
    "GLOBAL_CONFIG_VERSION",
    "GlobalConfig",
    "find_global_config_path",
    "load_global_config",
]
