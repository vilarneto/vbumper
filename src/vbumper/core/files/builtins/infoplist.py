import pathlib
import re
from typing import TYPE_CHECKING, Annotated, Any, Iterable

import pydantic

from ..discoverer import RegularExpressionFileDiscoverer, resolve_discovery_root

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol

#: An `Info.plist` is only recognized once it opens with this *exact* four-line header --
#: mirroring the legacy parser, which folds the header check directly into its content pattern
#: rather than a separate `get_check_patterns()` gate. A file matching the `Info.plist` filename
#: but not this header (a different plist flavor, or a hand-edited/malformed one) is simply not
#: a version container at all.
_HEADER_LINES = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
    ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
    '<plist version="1.0">',
    "<dict>",
]

#: After the header, matches the first `CFBundleShortVersionString` key's `<string>` value,
#: anywhere later in the file (`.*?`, non-greedy, `DOTALL` so it can cross lines).
_VERSION_PATTERN = re.compile(
    "".join(re.escape(line) + r"\n" for line in _HEADER_LINES)
    + r".*?<key>CFBundleShortVersionString</key>\n"
    r"\s*<string>(?P<version>.*?)</string>",
    re.DOTALL,
)


class InfoPlistFileConfig(pydantic.BaseModel):
    """Implements `DiscovererConfigProtocol[RegularExpressionFileDiscoverer]` structurally (see
    `RegularExpressionFileConfig` for why this can't just inherit the protocol directly).

    A zero-configuration built-in, same spirit as `PyProjectTomlFileConfig`: every `Info.plist`
    found in the discovery scope (with the expected header -- see `_VERSION_PATTERN`) is a
    candidate.
    Unlike the legacy parser, XML-escaping/unescaping of the captured value is not applied here:
    a semver string never contains a character (`&`, `<`, `>`, `"`, `'`) that XML would need to
    escape, so the capture is used, and written back, verbatim.
    """

    @classmethod
    def get_type(cls) -> str:
        return "info-plist"

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> InfoPlistFileConfig:
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
            include_patterns=["Info.plist"],
            version_pattern=_VERSION_PATTERN,
            path_exclude_patterns=path_exclude_patterns,
        )


__all__ = ["InfoPlistFileConfig"]
