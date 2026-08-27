from typing import Annotated

import pydantic

from .discoverer import DiscovererEntryConfig
from .flow import FLOW_KEY_PATTERN, FlowConfig


def _coerce_exclude_patterns(value: str | list[str]) -> list[str]:
    """Accept a single gitignore-style pattern or a list of them; normalize to a list."""

    if isinstance(value, str):
        return [value]
    return value


#: A single gitignore-style exclusion pattern, or a list of them -- accepting a bare string
#: avoids `exclude: [pattern]` boilerplate for the common single-pattern case. Matched via
#: `pathspec` (gitignore syntax), against paths relative to the discovery root.
ExcludePatterns = Annotated[
    list[str],
    pydantic.BeforeValidator(_coerce_exclude_patterns),
]


def default_exclude_patterns() -> list[str]:
    """The gitignore-style patterns excluded from discovery by default, regardless of any
    project-specific `exclude:` entries in config.

    `VBumpConfig.exclude` *appends* to this list rather than replacing it (see
    `VBumpConfig.all_exclude_patterns`) -- a project can carve an exception back out of a default
    with gitignore negation (`!some-generated-dir/`), but a bare `exclude:` entry can never
    silently reopen scanning of things like `.git/` or `node_modules/`.

    Grouped and commented by ecosystem for maintainability; entries are deliberately allowed to
    repeat across groups (e.g. `target/` for both Rust and Maven, `build/` for both JS and
    Gradle) since that reads clearer than cross-referencing -- `_dedupe` below collapses
    duplicates, preserving first-seen order.
    """

    patterns = [
        # Version control
        ".git/",
        ".hg/",
        ".svn/",
        # Python
        ".venv/",
        "venv/",
        ".tox/",
        "__pycache__/",
        ".mypy_cache/",
        ".pytest_cache/",
        ".ruff_cache/",
        "*.egg-info/",
        ".eggs/",
        # Node / JavaScript / TypeScript
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        ".nuxt/",
        ".turbo/",
        "coverage/",
        # Rust
        "target/",
        # Java / JVM (Maven, Gradle, Kotlin, Scala)
        "target/",
        ".gradle/",
        "out/",
        "build/",
        # Go
        "vendor/",
        # Xcode / Swift
        "DerivedData/",
        "*.xcworkspace/xcuserdata/",
        "*.xcodeproj/xcuserdata/",
        ".build/",
        # IDEs and editors: JetBrains
        ".idea/",
        "*.iml",
        # IDEs and editors: VS Code / Visual Studio
        ".vscode/",
        ".vs/",
        # Editor swap/backup files: vim, emacs
        "*.swp",
        "*.swo",
        "*~",
        "#*#",
        # OS cruft
        ".DS_Store",
        # Generic build/env noise
        ".env/",
        ".cache/",
        ".parcel-cache/",
    ]
    return _dedupe(patterns)


def _dedupe(patterns: list[str]) -> list[str]:
    """Remove duplicate patterns, preserving first-seen order."""

    return list(dict.fromkeys(patterns))


#: Schema version marker for this (vbumper) config format. Any other value is refused outright.
CONFIG_VERSION = 3

FlowKey = Annotated[str, pydantic.StringConstraints(pattern=FLOW_KEY_PATTERN.pattern)]


class VBumpConfig(pydantic.BaseModel):
    """Root of the vbumper project configuration file (`.vbump.yaml`/`.vbump.yml`).

    Mirrors `vbumper-config.schema.json` -- keep the two in sync when this model changes.
    """

    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    version: Annotated[int, pydantic.Field()] = CONFIG_VERSION
    version_tag_prefix: str = "v"
    default_flow: FlowKey | None = None
    flows: dict[FlowKey, FlowConfig] = pydantic.Field(default_factory=dict)
    discoverers: list[DiscovererEntryConfig] = pydantic.Field(default_factory=list)
    exclude: ExcludePatterns = pydantic.Field(default_factory=list)

    @pydantic.field_validator("version")
    @classmethod
    def _require_current_version(cls, value: int) -> int:
        if value != CONFIG_VERSION:
            raise ValueError(
                f"Unsupported config version {value!r}; this format requires"
                f" version: {CONFIG_VERSION}."
            )
        return value

    @classmethod
    def default(cls) -> VBumpConfig:
        """An empty, otherwise-default config -- the starting point `vbump init` seeds a new
        `.vbump.yaml` from. Not used as a runtime fallback: a project without a config file is a
        configuration error (see `vbumper.config.load.load_config`), not an implicit empty one,
        since discoverers are opt-in and there would be nothing to discover with."""

        return cls()

    @property
    def all_exclude_patterns(self) -> list[str]:
        """The patterns discovery should actually apply: `default_exclude_patterns()` with this
        config's own `exclude:` entries appended. Callers that prune the directory walk (see
        `AbstractFileDiscoverer`) should use this rather than `self.exclude` directly --
        `exclude:` in config is additive, never a replacement for the built-in defaults."""

        return _dedupe([*default_exclude_patterns(), *self.exclude])

    @property
    def all_flows(self) -> dict[str, FlowConfig]:
        """The flows a run should actually have available: every plugin-contributed flow (see
        `vbumper.core.plugins.installer.iter_registered_flows`), with this config's own `flows:`
        entries layered on top by key.

        A project's own entry for a key that doesn't collide with a plugin-contributed flow is a
        full, standalone flow definition, used as-is. A project's own entry for a
        plugin-contributed key instead *tunes* that stock flow rather than replacing it wholesale
        -- see `_merge_flow_override` for exactly which fields that means."""

        from vbumper.core.plugins.installer import iter_registered_flows

        stock_flows = dict(iter_registered_flows())
        merged = dict(stock_flows)
        for key, override in self.flows.items():
            base = stock_flows.get(key)
            merged[key] = override if base is None else _merge_flow_override(key, base, override)
        return merged


#: `FlowConfig` fields a project's own `flows:` entry may not set when overriding a
#: plugin-contributed flow key -- these define what the flow *does*, not data that tunes it, so
#: partially replacing them (append? prepend? replace outright?) has no unambiguous meaning.
#: Customizing them means defining a whole new flow under a different key instead.
_LOCKED_OVERRIDE_FIELDS = frozenset({"pre_commands", "post_commands"})


def _merge_flow_override(key: str, base: FlowConfig, override: FlowConfig) -> FlowConfig:
    """Combine a plugin-contributed flow (`base`) with a project's own `flows:` entry of the same
    key (`override`) into the `FlowConfig` a run should actually use.

    Only fields the project's entry actually set (per `override.model_fields_set` -- distinct from
    a field merely left at its default) take effect; anything unset falls back to `base`.
    `name`/`require_on_branch` are replaced outright when set; `variables` is merged key-by-key
    (the override's entries win on conflict, everything else from `base` survives) rather than
    replaced wholesale, so overriding one variable can't silently drop the rest -- see
    `_LOCKED_OVERRIDE_FIELDS` for the fields this never touches."""

    from vbumper.core.exceptions import ConfigurationError

    locked_fields_used = _LOCKED_OVERRIDE_FIELDS & override.model_fields_set
    if locked_fields_used:
        raise ConfigurationError(
            f"flows.{key}: {', '.join(sorted(locked_fields_used))} cannot be overridden on the"
            f" stock {key!r} flow -- define a new flow under a different key instead"
        )

    fields_set = override.model_fields_set
    return base.model_copy(
        update={
            "name": override.name if "name" in fields_set else base.name,
            "require_on_branch": (
                override.require_on_branch
                if "require_on_branch" in fields_set
                else base.require_on_branch
            ),
            "variables": {**base.variables, **override.variables},
        }
    )


__all__ = [
    "CONFIG_VERSION",
    "ExcludePatterns",
    "FlowKey",
    "VBumpConfig",
    "default_exclude_patterns",
]
