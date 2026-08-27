from typing import TYPE_CHECKING, Iterator, Protocol

if TYPE_CHECKING:
    from vbumper.config.flow import FlowConfig
    from vbumper.core.configs.protocols import DiscovererConfigProtocol
    from vbumper.core.discoverers.protocols import DiscovererProtocol


class VBumpPluginProtocol(Protocol):
    def iter_config_classes(self) -> Iterator[type[DiscovererConfigProtocol[DiscovererProtocol]]]:
        """Iterate over all discoverer configuration classes that this plugin provides."""
        ...

    def iter_flows(self) -> Iterator[tuple[str, FlowConfig]]:
        """Iterate over `(key, FlowConfig)` pairs that this plugin contributes.

        These become available for selection (via `--flow`, a project's own `default_flow`, or
        overriding by key under a project's `flows:`) exactly as if they'd been declared in
        config -- see `VBumpConfig.all_flows`. Contributing a flow does not select it: a plugin
        cannot set `default_flow` on a project's behalf."""
        ...


__all__ = ["VBumpPluginProtocol"]
