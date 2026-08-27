import pathlib
from typing import TYPE_CHECKING, Annotated, Any, Iterable

import pydantic

from .discoverer import RegularExpressionFileDiscoverer, resolve_discovery_root

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol


def _coerce_patterns(value: str | list[str]) -> list[str]:
    """Accept a single gitignore-style pattern or a list of them; normalize a bare string to a
    one-element list."""

    if isinstance(value, str):
        return [value]
    return value


#: One gitignore-style pattern (matched via `pathspec`'s gitignore syntax, same as
#: `VBumpConfig.exclude`) or a list of them -- always at least one pattern, enforced by the
#: `min_length=1` on the field itself. Deliberately duplicated rather than imported from
#: `vbumper.config.root.ExcludePatterns` -- this class is a plugin-owned discoverer config and
#: should not depend on the top-level application config package.
PathspecPatterns = Annotated[
    list[str],
    pydantic.BeforeValidator(_coerce_patterns),
]


class RegularExpressionFileConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[RegularExpressionFileDiscoverer]` structurally.

    `Protocol` subclasses use a different metaclass than `pydantic.BaseModel`, so this can't
    inherit from `DiscovererConfigProtocol` directly (metaclass conflict) — it satisfies the
    protocol by shape instead, which is all `Protocol` ever requires."""

    allow_multiple_matches: Annotated[bool, pydantic.Field(default=False)]
    encoding: Annotated[str, pydantic.Field(default="utf-8")]
    #: Required: a generic `file-regexp` entry must state at least one gitignore-style pattern
    #: narrowing which files it applies to -- there is no "match every file" default, since an
    #: unbounded content-pattern scan across the whole tree is never what a hand-written config
    #: entry actually wants.
    include: Annotated[PathspecPatterns, pydantic.Field(min_length=1)]
    version_pattern: Annotated[str, pydantic.Field(alias="version")]

    @classmethod
    def get_type(cls) -> str:
        return "file-regexp"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> RegularExpressionFileConfig:
        return cls.model_validate(data)

    def create_discoverer(
        self,
        *,
        path_exclude_patterns: Iterable[str] = (),
        dir_root: pathlib.Path | None = None,
    ) -> RegularExpressionFileDiscoverer:
        """`path_exclude_patterns` are the project-wide `exclude:` gitignore-style patterns from
        `VBumpConfig` (distinct from this entry's own `include`, which narrows candidate files
        down rather than ruling files out) — the caller assembling discoverers from config is
        responsible for threading them through. `dir_root` is the CLI's `--dir`/`-d` value;
        see `resolve_discovery_root` for how it determines the walk's starting point."""

        root_dir = resolve_discovery_root(dir_root)
        return RegularExpressionFileDiscoverer(
            allow_multiple_matches=self.allow_multiple_matches,
            root_dir=root_dir,
            encoding=self.encoding,
            include_patterns=self.include,
            version_pattern=self.version_pattern,
            path_exclude_patterns=path_exclude_patterns,
        )


__all__ = ["RegularExpressionFileConfig"]
