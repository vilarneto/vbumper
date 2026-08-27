import functools
from typing import Callable

import rich_click as click

from vbumper.core.exceptions import VBumpError


def graceful_shutdown[**P, T](func: Callable[P, T], /) -> Callable[P, T]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            click.secho("Interrupted as per user request.", fg="red", bold=True, err=True)
            raise SystemExit(1) from None
        except VBumpError as exc:
            click.secho(f"Runtime error: {exc}.", fg="red", bold=True, err=True)
            raise SystemExit(1) from None

    return wrapper


def _show_warning_plainly(message, category, filename, lineno, file=None, line=None) -> None:
    """Replaces `warnings`' default `showwarning`, which renders the source file/line the
    `warnings.warn()` call itself sits in -- meaningless, and rather alarming, to a CLI user who
    isn't reading this project's source. Prints just the message instead."""

    click.secho(f"Warning: {message}", fg="yellow", err=True)


@graceful_shutdown
def cli():
    import warnings

    from vbumper.core.plugins.installer import install_plugins

    # imported for their `@root_grp.command` registration side effect
    # noinspection PyUnusedImports
    from . import bump, init, list_, sync
    from ._grp import root_grp

    warnings.showwarning = _show_warning_plainly

    install_plugins()
    root_grp()


__all__ = ["cli"]
