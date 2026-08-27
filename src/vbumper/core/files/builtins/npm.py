import pathlib
from typing import TYPE_CHECKING, Annotated, Any, Iterable

import pydantic

from ..discoverer import JSONFileDiscoverer, resolve_discovery_root

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol


class PackageJsonFileConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[JSONFileDiscoverer]` structurally (see
    `RegularExpressionFileConfig` for why this can't just inherit the protocol directly).

    A zero-configuration built-in, same spirit as `PyProjectTomlFileConfig`: every
    `package.json` found in the discovery scope is a candidate, keyed on its top-level
    `"version"` string. Rewritten as a whole file on write-back (`JSONFileVersionContainer`),
    preserving every other key and their order, but not the original file's exact byte-for-byte
    formatting
    (indentation, key order stability aside) -- this mirrors the legacy NPM parser, which also
    fully regenerated the file via `json.dump(..., indent=2)` rather than patching in place.
    """

    @classmethod
    def get_type(cls) -> str:
        return "package-json"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> PackageJsonFileConfig:
        return cls.model_validate(data)

    def create_discoverer(
        self,
        *,
        path_exclude_patterns: Iterable[str] = (),
        dir_root: pathlib.Path | None = None,
    ) -> JSONFileDiscoverer:
        root_dir = resolve_discovery_root(dir_root)
        return JSONFileDiscoverer(
            root_dir=root_dir,
            encoding="utf-8",
            include_patterns=["package.json"],
            version_key="version",
            path_exclude_patterns=path_exclude_patterns,
        )


__all__ = ["PackageJsonFileConfig"]
