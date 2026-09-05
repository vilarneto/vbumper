import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vbumper.config.root import VBumpConfig


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GlobalOptions:
    """The root group's options, shared by every chained subcommand."""

    dir: str = "."
    dry_run: bool = False
    force: bool = False
    allow_incompatible_versions: bool = False
    skip_unreadable_version_strings: bool = False
    prerelease_token: str | None = None
    flow: str | None = None
    no_flow: bool = False
    allow_dirty_repository: bool = False
    no_nested_repo_warnings: bool = False


class CLIContext:
    options: GlobalOptions = GlobalOptions()
    _config: VBumpConfig | None = None

    def get_config(self) -> VBumpConfig:
        from vbumper.config.load import load_config

        if self._config is None:
            self._config = load_config(self.options.dir)

        return self._config


def get_cli_context() -> CLIContext:
    import click

    ctx = click.get_current_context().find_object(CLIContext)
    if ctx is None:
        raise RuntimeError("CLIContext not configured")

    return ctx


def get_config() -> VBumpConfig:
    return get_cli_context().get_config()


def get_options() -> GlobalOptions:
    return get_cli_context().options


__all__ = ["CLIContext", "GlobalOptions", "get_cli_context", "get_config", "get_options"]
