import pathlib
from typing import TYPE_CHECKING, Annotated, Any, Iterable

import pydantic

from ..discoverer import RegularExpressionFileDiscoverer, resolve_discovery_root

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol

#: Matches a PEP 621 `version = "..."` line at the start of a line, e.g. in `[project]`. Only
#: double-quoted values are recognized, mirroring the legacy parser -- `dynamic = ["version"]`
#: (no `version` key at all) simply never matches, which is correct: that spelling means "no
#: versioning expected here", not "unversioned container".
_VERSION_PATTERN = r'(?m)^version\s*=\s*"(?P<version>[^"]*)"\s*$'


class PyProjectTomlFileConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[RegularExpressionFileDiscoverer]` structurally (see
    `RegularExpressionFileConfig` for why this can't just inherit the protocol directly).

    A zero-configuration built-in: every `pyproject.toml` found in the discovery scope is a
    candidate, with no user-facing parameters -- there is exactly one way a
    top-level `version = "..."` key is spelled in a PEP 621 file, so unlike `file-regexp` there
    is nothing else worth exposing here.
    """

    @classmethod
    def get_type(cls) -> str:
        return "pyproject-toml"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> PyProjectTomlFileConfig:
        return cls.model_validate(data)

    def create_discoverer(
        self,
        *,
        path_exclude_patterns: Iterable[str] = (),
        dir_root: pathlib.Path | None = None,
    ) -> RegularExpressionFileDiscoverer:
        root_dir = resolve_discovery_root(dir_root)
        return RegularExpressionFileDiscoverer(
            root_dir=root_dir,
            encoding="utf-8",
            include_patterns=["pyproject.toml"],
            version_pattern=_VERSION_PATTERN,
            path_exclude_patterns=path_exclude_patterns,
        )


__all__ = ["PyProjectTomlFileConfig"]
