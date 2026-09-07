# Version Bumper

[![PyPI](https://img.shields.io/pypi/v/vbumper)](https://pypi.org/project/vbumper/)
[![Python versions](https://img.shields.io/pypi/pyversions/vbumper)](https://pypi.org/project/vbumper/)
[![License](https://img.shields.io/pypi/l/vbumper)](LICENSE)
[![Release](https://github.com/vilarneto/vbumper/actions/workflows/release.yml/badge.svg)](https://github.com/vilarneto/vbumper/actions/workflows/release.yml)

A project’s version number may live in more than one place. The build tool reads it from `pyproject.toml` or `package.json` to stamp the artifact it publishes; the binary itself needs to know it to answer `--version` on the command line or fill in an “About” dialog; a mobile app shows it in the splash screen; a Web app embeds it into the header of the footer; the docs site shows it in a corner via Sphinx’s `release`; CI config pins it for a release job; and so on.

Each of these is an independent artifact, and a single project can easily accumulate a handful of them: a Python package might declare its version in `pyproject.toml` for packaging, again in a Sphinx `conf.py` for the docs build, and once more in a `.gitlab-ci.yml` pin for a release job. The trouble starts once a release means touching all of them by hand: it’s easy to bump the package version and forget the docs, or update an Xcode target’s `Info.plist` and leave a sibling test target’s copy behind. Nothing enforces that they stay in agreement, so drift is silent.

*Version Bumper* keeps a project’s [Semantic Versioning](https://semver.org/) number in sync across every place that declares it: `pyproject.toml`, `package.json`, an Xcode project, a Sphinx `conf.py`, CI config, among references in your own source code, documentation files, etc. *Version Bumper* can optionally drive a release’s Git workflow (tagging, branch merges) as part of the version bumping action.

It solves the recurring pain of a version living in several files at once and going stale in some of them after a manual bump: *Version Bumper* refuses to write anything if the files it finds disagree, and rewrites every file in place, changing only the version string and leaving everything else about the file untouched.

**Full documentation:** the walkthrough, the complete CLI reference, config format, built-in container types, `file-regexp` fields, Git workflow config, and the plugin developer guide all live at [vbumper.readthedocs.io](https://vbumper.readthedocs.io).

## Installation

*Version Bumper* is distributed on PyPI as the [`vbumper`](https://pypi.org/project/vbumper/) package. It’s a standalone command-line tool, so the recommended way to install it is into its own isolated environment with [`pipx`](https://pipx.pypa.io) — this keeps its dependencies separate from any project you run it against, while still putting the `vbump` command on your `PATH`:

```bash
pipx install vbumper
```

If you don’t have `pipx` yet, install it first ([full instructions](https://pipx.pypa.io/stable/installation/)):

```bash
# macOS
brew install pipx
pipx ensurepath

# Windows (with Scoop)
scoop install pipx
pipx ensurepath

# Otherwise, on any platform with Python already installed
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

You can also install `vbumper` with [`uv`](https://docs.astral.sh/uv/), which works the same way as `pipx` here:

```bash
uv tool install vbumper
```

To upgrade later:

```bash
pipx upgrade vbumper
# or: uv tool upgrade vbumper
```

To use `vbump` as part of a `uv`-managed project’s own tooling instead — e.g. so `uv run vbump` picks up a pinned version — add it as a dev dependency:

```bash
uv add --dev vbumper
```

Any other way of installing a PyPI package (`pip install vbumper`, …) works the same way, though it’s not recommended for a standalone CLI tool, since it either pollutes your current environment or requires you to manage a dedicated one yourself.

## Try it

```bash
$ vbump init
Wrote .vbump.yaml
Detected discoverers: pyproject-toml

$ vbump list
File pyproject.toml  1.2.3

$ vbump -n patch
Would update File pyproject.toml: 1.2.3 -> 1.2.4

$ vbump patch
Updated File pyproject.toml: -> 1.2.4
```

`vbump init` scans the project and scaffolds a `.vbump.yaml` naming every version container it finds; `list` shows what's discovered and confirms they agree; `-n`/`--dry-run` previews a command before it touches anything; dropping `-n` writes the change for real. The full guided walkthrough — chaining bumps, prereleases, `set`, and everything else — is in the [docs](https://vbumper.readthedocs.io).

## Issues and contributing

Found a bug, or have a built-in/feature request? Open an issue on [GitHub](https://github.com/vilarneto/vbumper/issues).
