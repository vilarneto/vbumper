from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vbumper.core.configs.protocols import DiscovererConfigProtocol
    from vbumper.core.discoverers.protocols import DiscovererProtocol


def create_config(config_data: dict[str, Any]) -> DiscovererConfigProtocol[DiscovererProtocol]:
    """Create a config instance from a dict.

    The 'type' key determines the actual config class."""

    import pydantic

    from vbumper.core.exceptions import ConfigurationError, format_validation_error
    from vbumper.core.plugins.installer import get_config_cls

    config_data = dict(config_data)
    try:
        config_type = config_data.pop("type")
    except KeyError:
        raise ConfigurationError("Missing 'type' key in config") from None

    config_cls = get_config_cls(config_type)
    try:
        return config_cls.from_config_dict(config_data)
    except pydantic.ValidationError as exc:
        raise ConfigurationError(
            f"discoverers: type {config_type!r}: {format_validation_error(exc)}"
        ) from exc


__all__ = ["create_config"]
