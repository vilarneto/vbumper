from typing import TYPE_CHECKING, Iterator, Protocol

if TYPE_CHECKING:
    from vbumper.core.containers.base import VersionContainer


class DiscovererProtocol[VC: VersionContainer](Protocol):
    """A class that is able to investigate some realm that may contain version containers and yield
    objects that represent the discovered containers."""

    def discover(self) -> Iterator[VC]:
        """Yield all version containers found in the realm."""
        ...


__all__ = [
    "DiscovererProtocol",
]
