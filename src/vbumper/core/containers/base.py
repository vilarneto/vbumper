import abc

from .types import VersionStatus


class VersionContainer(abc.ABC):
    """The abstract superclass of all version containers that are returned by a discoverer.

    This holds both the original status and the current status and, for writable version
    containers, also the ability to update it."""

    _status: VersionStatus
    _orig_status: VersionStatus

    def __init__(self, *, status: VersionStatus):
        self._status = status
        self._orig_status = status

    @property
    def orig_status(self) -> VersionStatus:
        """The original status extracted from the version container."""
        return self._orig_status

    @property
    def status(self) -> VersionStatus:
        """The status currently attributed to this version container (initially the original
        one)."""
        return self._status

    def set_status(
        self, value: VersionStatus, *, allow_incompatible_versions: bool = False
    ) -> None:
        """Update the status currently attributed to this version container.

        Overriding an `Invalid` or `Mismatched` status requires
        `allow_incompatible_versions=True`; populating an `Unversioned` container, or replacing a
        `Versioned` one, does not.

        This never touches the underlying resource, so write-locking is irrelevant here: a
        write-locked container can still have its in-memory status updated freely, and only fails
        once `write()` is actually attempted."""
        from vbumper.core.exceptions import IncompatibleVersionsError

        from .types import Invalid, Mismatched

        if not allow_incompatible_versions and isinstance(self._status, Invalid | Mismatched):
            raise IncompatibleVersionsError(
                "Cannot override an invalid or mismatched container without"
                " --allow-incompatible-versions"
            )

        self._status = value

    @property
    def has_changed(self) -> bool:
        """Return `True` if the version container has been modified, `False` otherwise."""
        return self._status != self._orig_status

    @abc.abstractmethod
    def describe(self) -> str:
        """Return a textual description of the underlying version container, without the version
        itself."""
        ...

    @abc.abstractmethod
    def write(self) -> None:
        """Update the underlying version container to reflect the current status.

        Whether this container can actually be written is never checked ahead of time — a
        write-locked or otherwise failing container is only discovered here, at write-back time.
        Implementations should let the underlying failure propagate (optionally normalized as a
        `ReadOnlyVersionContainerError`)."""
        ...


__all__ = ["VersionContainer"]
