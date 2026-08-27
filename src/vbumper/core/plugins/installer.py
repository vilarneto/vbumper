from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from vbumper.config.flow import FlowConfig
    from vbumper.core.configs.protocols import DiscovererConfigProtocol
    from vbumper.core.discoverers.protocols import DiscovererProtocol
    from vbumper.core.plugins.protocols import VBumpPluginProtocol

_plugins: list[VBumpPluginProtocol] = []
_config_cls_by_type: dict[str, type[DiscovererConfigProtocol[DiscovererProtocol]]] = {}
_flow_by_key: dict[str, FlowConfig] = {}


def iter_plugins() -> Iterator[VBumpPluginProtocol]:
    """Iterate over available plugins."""
    from importlib.metadata import entry_points

    for entry_point in entry_points(group="vbumper.plugin"):
        cls = entry_point.load()
        yield cls()


def install_plugin(plugin: VBumpPluginProtocol) -> None:
    """Install a plugin."""

    global _plugins

    for config_cls in plugin.iter_config_classes():
        config_type = config_cls.get_type()

        if config_type in _config_cls_by_type:
            raise ValueError(f"Duplicate config type: {config_type}")
        _config_cls_by_type[config_type] = config_cls

    for flow_key, flow_config in plugin.iter_flows():
        if flow_key in _flow_by_key:
            raise ValueError(f"Duplicate flow key: {flow_key}")
        _flow_by_key[flow_key] = flow_config

    _plugins.append(plugin)


def install_plugins() -> None:
    """(Re-)populate the plugin registry from every installed `vbumper.plugin` entry point.

    Resets the registry first, so this is safe to call more than once within a process (e.g.
    once per CLI invocation in a test suite) instead of raising on re-registration."""

    global _plugins, _config_cls_by_type, _flow_by_key

    _plugins = []
    _config_cls_by_type = {}
    _flow_by_key = {}

    for plugin in iter_plugins():
        install_plugin(plugin)


def get_config_cls(config_type: str) -> type[DiscovererConfigProtocol[DiscovererProtocol]]:
    from vbumper.core.exceptions import ConfigurationError

    try:
        return _config_cls_by_type[config_type]
    except KeyError:
        raise ConfigurationError(f"Unknown config type: {config_type}")


def iter_registered_flows() -> Iterator[tuple[str, FlowConfig]]:
    """Iterate over every `(key, FlowConfig)` pair contributed by installed plugins.

    Used by `VBumpConfig.all_flows` to overlay a project's own `flows:` on top of these --
    plugin-contributed flows are defaults a project can override by key, not reserved names."""

    yield from _flow_by_key.items()


def iter_registered_config_classes() -> Iterator[
    type[DiscovererConfigProtocol[DiscovererProtocol]]
]:
    """Iterate over every registered discoverer config class, in registration order.

    Used by `vbump init` to auto-detect which built-in discoverer types apply to a project: a
    type is "auto-detectable" exactly when it can be constructed with no user-supplied
    parameters at all (`from_config_dict({})` succeeds) -- which is precisely the same set of
    types the "universal built-in, no `include:` required" design in the project's config
    documentation calls out (`pyproject-toml`, `package-json`, ...). A type like `file-regexp`
    requires an `include:` pattern to mean anything, so `from_config_dict({})` raises for it and
    it's naturally excluded, with no separate list to keep in sync."""

    yield from _config_cls_by_type.values()


__all__ = [
    "get_config_cls",
    "install_plugins",
    "iter_plugins",
    "iter_registered_config_classes",
    "iter_registered_flows",
]
