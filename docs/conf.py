"""Sphinx configuration for Version Bumper's documentation."""

# Force-import every module that attaches a subcommand to `root_grp` via
# `@root_grp.command(...)`. `vbumper.cli._cli.cli()` normally does this lazily, as a deliberate
# startup-time optimization -- but sphinx-click introspects `root_grp` directly, so without these
# imports it would render a CLI reference with zero subcommands and no error. This is the
# standard, documented way sphinx-click handles a Click app whose commands are split across
# modules; it doesn't touch `vbumper`'s own lazy-import structure, only this docs build.
import vbumper.cli.bump
import vbumper.cli.init
import vbumper.cli.list_
import vbumper.cli.sync

project = "Version Bumper"
copyright = "Vilar da Camara Neto"
author = "Vilar da Camara Neto"

extensions = [
    "sphinx_click",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = ["_static"]
html_title = "Version Bumper"
