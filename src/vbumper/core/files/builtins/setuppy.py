import pathlib
from typing import TYPE_CHECKING, Annotated, Any, Iterable

import pydantic

from ..discoverer import RegularExpressionFileDiscoverer, resolve_discovery_root

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol

#: Matches a `version=...` keyword argument to `setup()`, single- or double-quoted, with an
#: optional trailing comma (as it would appear in a `setup(..., version="1.2.3", ...)` call).
#: The quote character itself is captured via a backreference (group 1) so it's excluded from
#: the `version` group and, like `pyproject.py`, left untouched on write-back.
_VERSION_PATTERN = r"""(?m)^\s*version=(['"])(?P<version>[^'"]*)\1,?\s*$"""


class SetupPyFileConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[RegularExpressionFileDiscoverer]` structurally (see
    `RegularExpressionFileConfig` for why this can't just inherit the protocol directly).

    A zero-configuration built-in, same spirit as `PyProjectTomlFileConfig`: every `setup.py`
    found in the discovery scope is a candidate.
    """

    @classmethod
    def get_type(cls) -> str:
        return "setup-py"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> SetupPyFileConfig:
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
            include_patterns=["setup.py"],
            version_pattern=_VERSION_PATTERN,
            path_exclude_patterns=path_exclude_patterns,
        )


__all__ = ["SetupPyFileConfig"]
