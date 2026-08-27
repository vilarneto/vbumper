import pathlib
from typing import TYPE_CHECKING, Annotated, Any, Iterable

import pydantic

from ..discoverer import RegularExpressionFileDiscoverer, resolve_discovery_root

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol

#: Matches a top-level `__version__ = "..."` (or single-quoted) assignment, e.g. in a package's
#: `__init__.py`. The quote character is captured via a backreference (group 1) so it's excluded
#: from the `version` group and, like `pyproject.py`, left untouched on write-back -- unlike
#: earlier tooling this project replaces, there's no `eval()`-based unquoting step: since a
#: semver string never contains a quote or backslash, keeping the quotes outside the capture is
#: sufficient and avoids evaluating file contents as code.
_VERSION_PATTERN = r"""(?m)^\s*__version__\s*=\s*(['"])(?P<version>[^'"]*)\1\s*$"""

#: Every one of these filenames is a recognized location for a `__version__` assignment,
#: regardless of which package directory it lives in.
_INCLUDE_PATTERNS = ["__init__.py", "_version.py", "version.py"]


class PythonVersionFileConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[RegularExpressionFileDiscoverer]` structurally (see
    `RegularExpressionFileConfig` for why this can't just inherit the protocol directly).

    A zero-configuration built-in, same spirit as `PyProjectTomlFileConfig`: every
    `__init__.py`, `_version.py`, or `version.py` found in the discovery scope is a
    candidate.
    """

    @classmethod
    def get_type(cls) -> str:
        return "python-version"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> PythonVersionFileConfig:
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
            include_patterns=_INCLUDE_PATTERNS,
            version_pattern=_VERSION_PATTERN,
            path_exclude_patterns=path_exclude_patterns,
        )


__all__ = ["PythonVersionFileConfig"]
