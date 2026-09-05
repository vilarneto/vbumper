from typing import TYPE_CHECKING, Iterator, Protocol

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol
    from vbumper.core.discoverers.protocols import DiscovererProtocol


class VBumpPluginProtocol(Protocol):
    """A plugin contributes discoverer configuration classes only -- flows are never
    code/plugin-contributed. A named flow comes from exactly two places: a project's own
    `flows:`, or `~/.vbumpconfig.yaml`'s `flows:` (pulled in via `recall:`, see
    `vbumper.config.flow.FlowConfig`)."""

    def iter_config_classes(self) -> Iterator[type[DiscovererConfigProtocol[DiscovererProtocol]]]:
        """Iterate over all discoverer configuration classes that this plugin provides."""
        ...


__all__ = ["VBumpPluginProtocol"]
