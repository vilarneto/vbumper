import rich_click as click

click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"

#: Shared by every command in the group, not just the root -- lets `-h` work anywhere `--help`
#: does.
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS, cls=click.RichGroup, chain=True)
@click.option(
    "--allow-dirty-repository",
    is_flag=True,
    default=False,
    help="Run a Git workflow even if the working tree has uncommitted changes.",
)
@click.option(
    "--allow-incompatible-versions",
    is_flag=True,
    default=False,
    help="Perform version bumping even if the discovered versions differ.",
)
@click.option(
    "--dry-run", "-n", is_flag=True, default=False, help="Do not actually change any files."
)
@click.option(
    "--flow",
    default=None,
    metavar="NAME",
    help="Run this named Git workflow (default: the config's `default_flow`, if any).",
)
@click.option(
    "--no-flow",
    is_flag=True,
    default=False,
    help="Do not run any Git workflow, even if `default_flow` is configured.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Force major/minor/patch bump even if the current version is a prerelease.",
)
@click.option(
    "--dir",
    "-d",
    "dir_",
    default=".",
    metavar="DIR",
    help="Target directory (default: current directory).",
)
@click.option(
    "--prerelease-token",
    default=None,
    help='String to use for prerelease metadata (default: "rc").',
)
@click.option(
    "--skip-unreadable-version-strings",
    is_flag=True,
    default=False,
    help="Ignore version containers that do not follow semver semantics (default: abort).",
)
@click.version_option(package_name="vbumper")
def root_grp(
    *,
    allow_dirty_repository: bool,
    allow_incompatible_versions: bool,
    dry_run: bool,
    flow: str | None,
    no_flow: bool,
    force: bool,
    dir_: str,
    prerelease_token: str | None,
    skip_unreadable_version_strings: bool,
):
    from .context import CLIContext, GlobalOptions

    if flow is not None and no_flow:
        raise click.UsageError("--flow and --no-flow are mutually exclusive.")

    click_ctx = click.get_current_context()
    click_ctx.ensure_object(CLIContext)
    click_ctx.obj.options = GlobalOptions(
        dir=dir_,
        dry_run=dry_run,
        force=force,
        allow_incompatible_versions=allow_incompatible_versions,
        skip_unreadable_version_strings=skip_unreadable_version_strings,
        prerelease_token=prerelease_token,
        flow=flow,
        no_flow=no_flow,
        allow_dirty_repository=allow_dirty_repository,
    )


__all__ = ["root_grp"]
