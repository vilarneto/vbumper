"""Plain-text status descriptions shared by the bump-family write-back summary and `sync`.

Kept separate from `list_`'s own `_describe_status` (which uses Rich markup for its table) since
these two callers only ever write plain `click.echo` lines."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vbumper.core.containers.types import VersionStatus


def describe_status(status: VersionStatus) -> str:
    from vbumper.core.containers.types import Invalid, Mismatched, Unversioned, Versioned

    if isinstance(status, Versioned):
        return str(status.value)
    if isinstance(status, Unversioned):
        return "(unversioned)"
    if isinstance(status, Invalid):
        return "(invalid version)"
    if isinstance(status, Mismatched):
        return "(mismatched versions)"

    raise AssertionError(f"Unhandled version status: {status!r}")  # pragma: no cover


__all__ = ["describe_status"]
