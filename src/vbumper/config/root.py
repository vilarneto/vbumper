from typing import Annotated

import pydantic

from .discoverer import DiscovererEntryConfig
from .flow import FlowConfig, FlowDefinition, FlowKey


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


def resolve_all_flows(
    project_flows: dict[FlowKey, FlowConfig], global_flows: dict[FlowKey, FlowDefinition]
) -> dict[FlowKey, FlowDefinition]:
    """The flows a run should actually have available: a project's own `flows:` entries, each
    resolved against `global_flows` (from `~/.vbumpconfig.yaml`, see
    `vbumper.config.global_config.load_global_config`) when it sets `recall:`.

    An entry with no `recall:` is a full, standalone definition, used as-is. An entry with
    `recall: NAME` adopts the `global_flows[NAME]` definition wholesale, with its own `variables`
    merged key-by-key on top (the entry's entries win on conflict, everything else from the
    recalled definition survives) -- naming an undefined global flow is a `ConfigurationError`,
    not a silent no-op."""

    from vbumper.core.exceptions import ConfigurationError

    resolved: dict[str, FlowDefinition] = {}
    for key, entry in project_flows.items():
        if entry.recall is None:
            resolved[key] = FlowDefinition(**entry.model_dump(exclude={"recall"}))
            continue

        base = global_flows.get(entry.recall)
        if base is None:
            raise ConfigurationError(
                f"flows.{key}: recall: {entry.recall!r} does not match any flow defined in"
                f" ~/.vbumpconfig.yaml (available: {', '.join(sorted(global_flows)) or '(none)'})"
            )
        resolved[key] = base.model_copy(update={"variables": {**base.variables, **entry.variables}})

    return resolved


__all__ = [
    "CONFIG_VERSION",
    "ExcludePatterns",
    "FlowKey",
    "VBumpConfig",
    "default_exclude_patterns",
    "resolve_all_flows",
]
