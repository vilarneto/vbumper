from typing import TYPE_CHECKING, Any

import pydantic

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol
    from vbumper.core.discoverers.protocols import DiscovererProtocol


class DiscovererEntryConfig(pydantic.BaseModel):
    """One entry of `VBumpConfig.discoverers`: a plugin-discriminated config object.

    `type` selects the discoverer plugin (its registered identifier, e.g. "file-regexp");
    every other key is that plugin's own parameter and is *not* validated here -- it is
    handed, verbatim, to that plugin's own config class (`DiscovererConfigProtocol`) once the
    plugin registry has been populated. Keeping this model's own validation limited to `type`
    lets `VBumpConfig` be parsed and the "all flows behave identically" / "version == 3" shape
    checked before plugins are even installed.
    """

    model_config = pydantic.ConfigDict(frozen=True, extra="allow")

    type: str

    def resolve(self) -> DiscovererConfigProtocol[DiscovererProtocol]:
        """Build the plugin-specific config object this entry describes.

        Requires plugins to already be installed (see `vbumper.core.plugins.installer`).
        """

        from vbumper.core.configs import create_config

        return create_config(self.model_dump())


__all__ = ["DiscovererEntryConfig"]
