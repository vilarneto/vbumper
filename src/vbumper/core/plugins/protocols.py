from typing import TYPE_CHECKING, Iterator, Protocol

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol
    from vbumper.core.discoverers.protocols import DiscovererProtocol


class VBumpPluginProtocol(Protocol):
    """A plugin contributes discoverer configuration classes only: flows are never
    code/plugin-contributed. A named flow comes only from a project's own `flows:`;
    `~/.vbumpconfig.yaml`'s `flows:` is a template library `vbump flow add`/`vbump init --flows`
    can copy from beforehand, but a run never resolves against it directly (see
    `vbumper.config.flow.FlowDefinition`)."""

    def iter_config_classes(self) -> Iterator[type[DiscovererConfigProtocol[DiscovererProtocol]]]:
        """Iterate over all discoverer configuration classes that this plugin provides."""
        ...


__all__ = ["VBumpPluginProtocol"]
