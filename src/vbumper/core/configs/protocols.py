import pathlib
from typing import TYPE_CHECKING, Any, Iterable, Protocol, Self

if TYPE_CHECKING:
    from vbumper.core.discoverers.protocols import DiscovererProtocol


class DiscovererConfigProtocol[Discoverer: DiscovererProtocol](Protocol):
    """The protocol for discoverer configuration classes."""

    @classmethod
    def get_type(cls) -> str:
        """Return the string that identifies the related discoverer to be used in configuration
        files.

        Use lowercase letters and hyphens only.
        """
        ...

    @classmethod
    def from_config_dict(cls, data: dict[str, Any]) -> Self: ...

    def create_discoverer(
        self,
        *,
        path_exclude_patterns: Iterable[str] = (),
        dir_root: pathlib.Path | None = None,
    ) -> Discoverer:
        """Return a new Discoverer instance configured according to this config.

        `path_exclude_patterns` are the project-wide `exclude:` gitignore-style patterns from
        `VBumpConfig` -- distinct from any filename-level exclusion the config itself may define.
        `dir_root` is the CLI's `--dir`/`-d` value, resolved to a `Path`, if the run should
        scope discovery to it (see `vbumper.core.files.discoverer.resolve_discovery_root` for
        exactly how a file-based discoverer applies it). Implementations that have no use for
        either (e.g. a discoverer that isn't file-based at all) may ignore them, but must still
        accept them so callers can thread them through uniformly regardless of which discoverer
        type is in play."""
        ...


__all__ = [
    "DiscovererConfigProtocol",
]
