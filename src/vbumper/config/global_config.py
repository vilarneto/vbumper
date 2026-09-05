"""Loading `~/.vbumpconfig.yaml`: an optional, per-user file holding reusable named flows a
project's own `.vbump.yaml` can pull in by name (see `FlowConfig.recall`) rather than redefining
the same flow in every project.

A single fixed location is checked -- no directory is searched, and no other file name or
location is recognized. A project that doesn't use `recall:` at all is entirely unaffected by
whether this file exists or what it contains.
"""

from pathlib import Path

import pydantic

from .flow import FlowDefinition, FlowKey

#: Schema version marker for this (global) config format, independent of `VBumpConfig`'s own --
#: kept as a distinct constant since the two files could in principle diverge in the future, even
#: though both currently only ever accept `3`.
GLOBAL_CONFIG_VERSION = 3


class GlobalConfig(pydantic.BaseModel):
    """Root of `~/.vbumpconfig.yaml`. Every flow here is a full `FlowDefinition` -- one cannot set
    `recall:` (that field doesn't exist on `FlowDefinition` at all), so a global flow can never
    itself refer to another one."""

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
    """The path to `~/.vbumpconfig.yaml`, or `None` if it doesn't exist. A single fixed location
    -- no search, no alternate file name."""

    candidate = Path.home() / ".vbumpconfig.yaml"
    return candidate if candidate.is_file() else None


def load_global_config() -> GlobalConfig:
    """Load `~/.vbumpconfig.yaml`. A missing file is not an error -- it's treated the same as one
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
            raise  # pragma: no cover -- raise_configuration_error always raises

    raw = raw if raw is not None else {}

    try:
        return GlobalConfig.model_validate(raw)
    except pydantic.ValidationError as exc:
        raise_configuration_error(path, exc)
        raise  # pragma: no cover -- raise_configuration_error always raises


__all__ = [
    "GLOBAL_CONFIG_VERSION",
    "GlobalConfig",
    "find_global_config_path",
    "load_global_config",
]
