from typing import TYPE_CHECKING

from ._grp import root_grp

if TYPE_CHECKING:
    from vbumper.core.containers.types import VersionStatus


def _describe_status(status: VersionStatus) -> str:
    from vbumper.core.containers.types import Invalid, Mismatched, Unversioned, Versioned

    if isinstance(status, Versioned):
        return str(status.value)
    if isinstance(status, Unversioned):
        return "[yellow](unversioned)[/yellow]"
    if isinstance(status, Invalid):
        return "[red](invalid version)[/red]"
    if isinstance(status, Mismatched):
        return "[red](mismatched versions)[/red]"

    raise AssertionError(f"Unhandled version status: {status!r}")  # pragma: no cover


@root_grp.command("list")
def list_():
    """Show every discovered version container and its current version."""

    from rich.console import Console
    from rich.table import Table

    from vbumper.core.resolution import discover_containers

    from .context import get_config, get_options

    containers = discover_containers(get_config(), path=get_options().dir)

    table = Table(box=None, pad_edge=False)
    table.add_column("Container")
    table.add_column("Version")

    for container in containers:
        table.add_row(container.describe(), _describe_status(container.status))

    console = Console()
    if table.row_count == 0:
        console.print("[yellow]No version containers were discovered.[/yellow]")
    else:
        console.print(table)


__all__ = []
