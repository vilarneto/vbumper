# Version Bumper

A project’s version number may live in more than one place. The build tool reads it from `pyproject.toml` or `package.json` to stamp the artifact it publishes; the binary itself needs to know it to answer `--version` on the command line or fill in an “About” dialog; a mobile app shows it in the splash screen; a Web app embeds it into the header of the footer; the docs site shows it in a corner via Sphinx’s `release`; CI config pins it for a release job; and so on.

Each of these is an independent artifact, and a single project can easily accumulate a handful of them: a Python package might declare its version in `pyproject.toml` for packaging, again in a Sphinx `conf.py` for the docs build, and once more in a `.gitlab-ci.yml` pin for a release job. The trouble starts once a release means touching all of them by hand: it’s easy to bump the package version and forget the docs, or update an Xcode target’s `Info.plist` and leave a sibling test target’s copy behind. Nothing enforces that they stay in agreement, so drift is silent.

*Version Bumper* keeps a project’s [Semantic Versioning](https://semver.org/) number in sync across every place that declares it: `pyproject.toml`, `package.json`, an Xcode project, a Sphinx `conf.py`, CI config, among references in your own source code, documentation files, etc. *Version Bumper* can optionally drive a release’s Git workflow (tagging, branch merges) as part of the version bumping action.

It solves the recurring pain of a version living in several files at once and going stale in some of them after a manual bump: *Version Bumper* refuses to write anything if the files it finds disagree, and rewrites every file in place, changing only the version string and leaving everything else about the file untouched.

## Installation

*Version Bumper* is distributed on PyPI as the `vbumper` package. It’s a standalone command-line tool, so the recommended way to install it is into its own isolated environment with [`pipx`](https://pipx.pypa.io) — this keeps its dependencies separate from any project you run it against, while still putting the `vbump` command on your `PATH`:

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

## Try it on a real project

The best way to get a feel for *Version Bumper* is to run it somewhere it has nothing to lose: `cd` into an existing Python or Node project (something with a `pyproject.toml` or `package.json` will do). Nothing below writes anything until the “Bump it” step, so feel free to follow along on a real repo.

**Start with a config file.** *Version Bumper* needs a `.vbump.yaml` file at the project root. You don't have to write one by hand: `vbump init` scans the directory and generates a starting one for you:

```bash
$ vbump init
Wrote .vbump.yaml
Detected discoverers: pyproject-toml
```

It found your `pyproject.toml` and wrote this:

```yaml
# .vbump.yaml
version: 3

discoverers:
  - type: pyproject-toml
```

Most important here is the `discoverers:` key: it lists the places to look for version annotations — here, the one entry `init` means, “the `version = "..."` line in `pyproject.toml`.”

Each entry under `discoverers:` is called a *discoverer* — a rule for finding and reading a version somewhere. `vbump init` only pre-fills what it actually found; from here on, teaching *Version Bumper* about a new place to look, another built-in or a pattern of your own, means adding another line under `discoverers:` by hand (see [Recognize your own file formats](#recognize-your-own-file-formats)).

**See what it finds.** Once a config file exists, `list` goes looking for exactly what it names:

```bash
$ vbump list
File pyproject.toml  1.2.3
```

Just one file here, but the same command works whether it names one *container* — *Version Bumper*'s term for any place a discoverer actually finds and reads a version, a file in every example in this walkthrough — or a dozen: a `pyproject.toml` next to a `package.json` for a bundled frontend, an Xcode project with several targets, a Dockerfile pin, all of them read together. Agreement is the whole point: whatever *Version Bumper* is told to look for, `list` confirms every place found is telling the same story. If a project has more than one container and they disagree — the docs still stuck on `1.2.2` after `pyproject.toml` got bumped by hand ahead of a release — `list` would show that mismatch instead, and every command below would refuse to touch anything until it’s sorted out (or waved through with `--allow-incompatible-versions`, once you’ve confirmed the divergence is fine).

**Ask for just the version.** Once you trust the files agree, `print` gives you the one number, with nothing else — handy for scripting a build step:

```bash
$ vbump print
1.2.3
```

`vbump print` is a nice one-liner that can be used in shell scripts:

```
CURRENT_VERSION=$(vbump print)
```

**Preview before touching anything.** `-n`/`--dry-run` runs the full command but reports what *would* change instead of changing it — the safest way to see a command’s effect for the first time:

```bash
$ vbump -n patch
Would update File pyproject.toml: 1.2.3 -> 1.2.4
```

**Bump it for real.** Drop `-n` once you’re happy with the preview, and the file is rewritten in place — nothing else about it changes, only the version string:

```bash
$ vbump patch
Updated File pyproject.toml: -> 1.2.4
```

**Chain steps together.** Cutting a release candidate for the next minor version is two logical bumps, but one release: `minor` computes `1.3.0`, then `rc` moves that straight into `1.3.0-rc.1`, and both are written together, once:

```bash
$ vbump minor rc
Updated File pyproject.toml: -> 1.3.0-rc.1
```

**Iterate on the prerelease, then release it.** Each further `rc` (or the token-agnostic `lower`) advances the serial; `stable` drops the prerelease tag once you’re ready to ship:

```bash
$ vbump rc       # 1.3.0-rc.1 -> 1.3.0-rc.2
$ vbump stable   # 1.3.0-rc.2 -> 1.3.0
```

**Reach for `set` when you need an exact number**, bypassing the usual increment logic entirely — useful right after adopting Version Bumper in a project, or to jump to a version scheme change:

```bash
$ vbump set 2.0.0-beta.1
Updated File pyproject.toml: -> 2.0.0-beta.1
```

Every one of these commands scales to as many containers as your config names — a second `discoverers:` entry means a second line in each of the outputs above, updated in lockstep, nothing more.

That covers the everyday loop: `init` once, then look with `list`/`print`, preview with `-n`, then bump, chain, or `set`. Everything from here on — the full command/option reference, config, built-in file types, Git workflows — fills in the edges of that loop.

## How it works

Every run walks through the same five steps:

1. **Discover.** Version Bumper scans a directory for every *version container* named under the config's `discoverers:` — a file that holds a version number, recognized by name/path and content pattern (`pyproject.toml`, `package.json`, an Xcode project, …).

2. **Read.** Each container yields its current version, which falls into one of four states:
   — **versioned**: holds a single, valid version;
   — **unversioned**: explicitly empty (e.g. `"version": ""`) — a normal, no-warning “not set yet” state, distinct from a file that never declares a version field at all (which isn’t a version container in the first place);
   — **invalid**: holds something that fails to parse as semver;
   — **mismatched**: holds two or more *different* values internally (some containers, like an Xcode target, keep more than one copy, e.g., one per build configuration).

   If the containers found in a project disagree (across containers, or within a single mismatched one), then Version Bumper stops and tells you. This safety check is the reason the tool exists in the first place; you can lift it explicitly with [`--allow-incompatible-versions`](#global-options) once you’ve confirmed the disagreement is fine.

3. **Bump.** With every container in agreement, Version Bumper computes the new version: increment major/minor/patch, move into or through a prerelease, drop a prerelease, or set an explicit value. Several of these can be chained in one invocation, applied left to right.

4. **Write back.** Every changed container is rewritten in place. An unversioned container is filled in with the resulting version.

5. **(Optional) Git workflow.** Wrap the write-back in a configurable sequence of Git commands (or any other commands): tag, merge, commit, whatever a release process calls for (see [Git workflows](#git-workflows)).

## Recognize your own file formats

Real projects almost always keep the version somewhere the built-ins don’t know about: a `Dockerfile`, a shell script, a Helm chart, a hand-rolled version header in a language Version Bumper doesn’t ship a recognizer for. This is one of the main reasons to reach for Version Bumper in the first place — you’re not limited to the built-in list, and teaching it a new file takes one entry in `.vbump.yaml`, no plugin or code required.

Say your project’s `Dockerfile` pins the image version in an `ARG`:

```dockerfile
ARG VERSION=1.2.3
```

A few lines of config turn that into a container Version Bumper discovers, reads, and rewrites right alongside `pyproject.toml`:

```yaml
version: 3

discoverers:
  - type: file-regexp
    include: /Dockerfile
    version: '(?m)^ARG VERSION=(?P<version>.*)$'
```

```bash
$ vbump list
pyproject.toml   1.2.3
Dockerfile       1.2.3

$ vbump patch
Wrote pyproject.toml: 1.2.3 -> 1.2.4
Wrote Dockerfile:     1.2.3 -> 1.2.4
```

That’s the whole recipe: a filename pattern (`include`) and a regular expression with a named `(?P<version>...)` group. The leading `/` in `/Dockerfile` anchors the pattern to the discovery root; without it, `Dockerfile` would also match a nested one, like `services/api/Dockerfile`, the same way `.gitignore` treats a leading slash. See [Adding your own file recognizer](#adding-your-own-file-recognizer) for the full field reference, including matching by directory, encoding, and files with more than one copy of the version to keep in sync.

A Sphinx docs build is another common case — `conf.py` declares `release = "..."`, but only a `conf.py` that’s actually Sphinx’s own config file should ever be touched, not some unrelated `conf.py` a project happens to also have (a pytest fixture, another tool’s config, …). If your project keeps that file at the conventional `docs/source/conf.py` path, an anchored, depth-agnostic `include:` narrows to exactly that:

```yaml
discoverers:
  - type: file-regexp
    include: "**/docs/source/conf.py"
    version: "(?m)^release = ['\"](?P<version>[^'\"]*)['\"]$"
```

(A different layout, e.g. `docs/conf.py` with no `source/` directory, just needs a matching `include:` glob for that path instead.)

A static HTML page can carry its version in its own `<meta>` tag — there’s no real HTML/web standard for this, so it’s always a per-project convention, but a common one:

```html

<meta name="version" content="1.2.3">
```

```yaml
discoverers:
  - type: file-regexp
    include: ["*.html", "*.htm"]
    version: '(?i)<meta\s+name="version"\s+content="(?P<version>[^"]*)"\s*/?>'
```

## Usage

### Command-line shape

`vbump` commands can be chained in one invocation and run in the order given, so **nothing is written to disk until every chained subcommand has run**, and only if at least one container’s version actually changed.

```
vbump [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...
```

Global options apply to the whole invocation and must come before the first subcommand.

### Global options

| Option                              | Description                                                                                                                                                                                                 |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--dir DIR`, `-d DIR`               | Restrict discovery to this directory (default: `.`).                                                                                                                                                        |
| `--dry-run`, `-n`                   | Report what would change (files, Git commands) without touching anything.                                                                                                                                   |
| `--allow-incompatible-versions`     | Proceed even if discovered containers disagree, or a container itself holds mismatched/invalid values. Writing such a container over its previous, unparseable content is only ever allowed with this flag. |
| `--skip-unreadable-version-strings` | Ignore containers whose value doesn’t parse as semver, instead of aborting.                                                                                                                                 |
| `--force`, `-f`                     | Allow a major/minor/patch bump even when the current version is a prerelease. Unrelated to `--allow-incompatible-versions` — this is purely about bumping over a prerelease.                                |
| `--prerelease-token TEXT`           | Token to use when entering/advancing a prerelease with `prerelease`/`lower` (default: `rc`). `alpha`/`beta`/`rc` set the token explicitly and ignore this option.                                           |
| `--flow NAME`                       | Run this named Git workflow instead of the config’s `default_flow`.                                                                                                                                         |
| `--no-flow`                         | Skip any Git workflow for this invocation, even if `default_flow` is configured.                                                                                                                            |
| `--allow-dirty-repository`          | Run a Git workflow even with uncommitted changes in the working tree. Normally a dirty tree aborts before anything runs.                                                                                    |
| `--version`                         | Show `vbump`’s own version and exit.                                                                                                                                                                        |
| `-h`, `--help`                      | Show help and exit — available on the group and on every subcommand.                                                                                                                                        |

### Commands

| Command                 | Effect                                                                                                                                                                                    |
|-------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `init`                  | Scaffold a starting `.vbump.yaml`, pre-populated with a `- type: ...` entry for each built-in that finds something in the target directory. Refuses to overwrite an existing config file. |
| `list`                  | Show every discovered container and its current version (or `(unversioned)` / `(invalid version)` / `(mismatched versions)`).                                                             |
| `print`                 | Print the single common version, or nothing if no container is versioned yet. See below for what chaining it with other commands does.                                                   |
| `patch`                 | `1.2.3` → `1.2.4`                                                                                                                                                                         |
| `minor`                 | `1.2.3` → `1.3.0`                                                                                                                                                                         |
| `major`                 | `1.2.3` → `2.0.0`                                                                                                                                                                         |
| `prerelease`            | Move into a prerelease, or advance its serial if already in one, using `--prerelease-token` (bumps the patch first the first time).                                                       |
| `alpha` / `beta` / `rc` | Same as `prerelease`, but pin the token to `alpha`/`beta`/`rc` regardless of `--prerelease-token`.                                                                                        |
| `lower`                 | Automatic selection between `prerelease` and `patch`: Advance the prerelease serial if already a prerelease, otherwise bump the patch.                                                    |
| `stable`                | Drop any prerelease component, keeping the version otherwise unchanged.                                                                                                                   |
| `set VERSION`           | Set an explicit version string, bypassing whatever agreement (or disagreement) existed before.                                                                                            |
| `sync`                  | Write the single highest version found across all discovered containers back over every versioned and unversioned one, asking for confirmation first. See below.                          |

Chaining works left to right: `vbump minor rc` first computes the minor bump, then applies a prerelease bump on top of the result, and writes the final version once, at the end.

`print` anywhere in a chain makes the whole invocation read-only: `vbump prerelease print` computes the version a real `prerelease` would move to and prints it, but writes nothing back and runs no Git workflow — regardless of where `print` sits in the chain, not just at the end.

If no versioned container exists at all (every container found is unversioned), bump commands have no base value to increment from and will error out; `set` still works, since it doesn’t need one.

`sync` is not part of that chain: unlike the bump family, it doesn’t need containers to already agree, since reconciling disagreement is exactly its job, and it can’t be combined with `patch`/`minor`/etc. in one invocation. It takes the highest semver among all versioned containers (erroring out if none is found) and writes it over every versioned/unversioned container. It has its own local options, on top of the global ones above:

| Option                 | Description                                                                                                                                             |
|------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--include-mismatched` | Also consider values found inside mismatched containers when picking the highest version, and overwrite such containers too.                            |
| `--fix-invalid`        | Also overwrite invalid containers with the resulting version (they never contribute to picking it, since an invalid container retains no parsed value). |
| `--no-input`           | Skip the confirmation prompt and proceed as if the user answered yes.                                                                                   |

## Configuration

A `.vbump.yaml` (or `.vbump.yml`) is required at your project root, as every discoverer (built-in types included) is opt-in and must be listed under `discoverers:` to run (see [Try it on a real project](#try-it-on-a-real-project) for `vbump init`, which scaffolds one). Version Bumper looks for it directly in the directory named by `--dir`/`-d`, which must be a directory — it does not walk upward past that root looking for one.

```yaml
version: 3
version_tag_prefix: v

exclude:
  - "**/testing/fixtures/"

discoverers:
  - type: file-regexp
    include: /docker/Dockerfile
    version: '(?m)^ARG VERSION=(?P<version>.*)$'
```

Optionally driving a release's Git workflow as part of the same command is configured the same way, under `flows:`/`default_flow:` — see [Git workflows](#git-workflows) below.

A [JSON Schema](src/vbumper/config/vbumper-config.schema.json) for this format ships with the package, for editor validation/autocompletion.

### Top-level keys

| Key                  | Default      | Meaning                                                                                                                                                                                                                                                                                                                    |
|----------------------|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `version`            | *(required)* | Config format version. Must be `3`.                                                                                                                                                                                                                                                                                        |
| `version_tag_prefix` | `"v"`        | Prefix prepended to the Git tag name by a flow’s `{VERSION_TAG}` placeholder (never to file contents).                                                                                                                                                                                                                     |
| `exclude`            | `[]`         | Extra gitignore-style patterns to prune from discovery, added on top of a large built-in default list (VCS directories, language/build caches, IDE folders, editor swap files, …). A bare string is accepted in place of a one-element list. Applies to *every* discoverer, and can prune whole directories from the walk. |
| `discoverers`        | `[]`         | Extra discoverer entries, added on top of the built-ins (see [Built-in containers](#built-in-containers) and [Adding your own file recognizer](#adding-your-own-file-recognizer)).                                                                                                                                         |
| `flows`              | `{}`         | Named Git (or other) release workflows (see [Git workflows](#git-workflows)).                                                                                                                                                                                                                                              |
| `default_flow`       | *(none)*     | Key of the flow to run when neither `--flow` nor `--no-flow` is given. Must name an entry under `flows` (see [Git workflows](#git-workflows)).                                                                                                                                                                             |

### `exclude` vs. a discoverer’s own `include`

Two different filters narrow down what discovery looks at — both gitignore-style glob patterns (matched via [`pathspec`](https://pypi.org/project/pathspec/)’s gitignore matcher, the same engine Git itself uses for `.gitignore`), but at different scope and with opposite intent:

- **`exclude:`** is project-wide and applies to every discoverer. It’s a deny-list on top of the built-in defaults — everything is a candidate except what it (or the defaults) rule out. Because it can rule out whole directories, an excluded directory is pruned from the walk entirely, never descended into.
- **A discoverer’s own `include:`** (only meaningful for `file-regexp`; the other built-ins already know which filenames they’re looking for) is local to that one entry, required, and an allow-list — nothing is a candidate for that discoverer except what matches; project-wide `exclude` still applies on top. There’s no separate “base directory” field to scope an entry to a subtree — use an anchored pattern instead (e.g. `include: /docker/**/Dockerfile`). Unlike `exclude`, `include` never prunes directories — a directory that doesn’t itself match may still contain matching files below it.

Both accept a single pattern as a bare string, or a list of them, and support full gitignore syntax, including negation (`!keep/this/`) to carve an exception back out of a broader pattern.

### `.vbumpignore`

Dropping an empty `.vbumpignore` file in any directory opts that whole subtree out of discovery, the same way an `exclude:`-matched directory is pruned — regardless of what `exclude`/`include` patterns say. Its contents don’t matter, only its presence; useful for a vendored dependency, a generated output directory, or a scratch project nested inside the repository, without needing the top-level config to know about it.

A `.vbump.yaml`/`.vbump.yml` found in a subdirectory Version Bumper descends into while scanning is similarly never read or merged into the run doing the scanning — it’s pruned the same way, with an advisory pointing at running `vbump -d <subdir>` separately. A monorepo with independently versioned components needs multiple independent Version Bumper roots, not an on-the-fly config merge.

### Built-in containers

Each of these takes no parameters beyond `type:` — activating one is a single `- type: ...` line under `discoverers:` (see [Configuration](#configuration)), with no `include:` needed since the filename/key is fixed by convention:

| Type             | File              | What’s matched                                                                                                                                                                                                                                                                                                                                                                                    |
|------------------|-------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `pyproject-toml` | `pyproject.toml`  | `version = "..."` at the start of a line.                                                                                                                                                                                                                                                                                                                                                         |
| `package-json`   | `package.json`    | The top-level `"version"` key, read/written as JSON — every other key is preserved verbatim.                                                                                                                                                                                                                                                                                                      |
| `info-plist`     | `Info.plist`      | `CFBundleShortVersionString`, gated on the file actually being a standard Apple property list.                                                                                                                                                                                                                                                                                                    |
| `xcode-pbxproj`  | `project.pbxproj` | `MARKETING_VERSION = ...;`, gated on the standard Xcode ASCII-plist header. Each `PBXNativeTarget` declared in the file (e.g. an app target and its test target) is discovered as its own, independent container — bumping one never touches the other — and a target’s several build-configuration copies (typically Debug and Release) are treated as one container that must agree internally. |

### Adding your own file recognizer

Anything else regex-shaped can be added with a `file-regexp` entry under `discoverers:`. The full shape:

```yaml
discoverers:
  - type: file-regexp
    include: /docker/Dockerfile   # required; can also be a list
    version: '(?m)^ARG VERSION=(?P<version>.*)$'
```

Fields:

| Field                    | Default      | Meaning                                                                                                                                                                                                                                                                           |
|--------------------------|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `version`                | *(required)* | A regular expression with a named group `(?P<version>...)`, matched against the file’s full contents.                                                                                                                                                                             |
| `include`                | *(required)* | Gitignore-style pattern(s) narrowing which files are candidates for this entry, matched relative to the discovery root (`--dir`/`-d`, default `.`). Must carry at least one pattern — use an anchored pattern (e.g. `/docker/**/Dockerfile`) to scope an entry to a subdirectory. |
| `encoding`               | `"utf-8"`    | Text encoding used to read and write matching files.                                                                                                                                                                                                                              |
| `allow_multiple_matches` | `false`      | Whether more than one match inside the same file is allowed (and must agree) rather than treated as a hard error.                                                                                                                                                                 |

Everything about the matched file other than the version string itself is preserved untouched on write-back.

### Git workflows

A *flow* is a named sequence of commands run around the version write-back — some before the version files are rewritten, some after — checking out a release branch, merging it, tagging the result, whatever your release process needs.

Here is one, defined under the key `release`: it checks out a release branch, merges the development branch into it, then — after the version files themselves are rewritten — commits and tags the bumped version, and merges the release branch back into development:

```yaml
flows:
  release:
    name: Release to main
    variables:
      DEVELOP_BRANCH: develop
      RELEASE_BRANCH: main
    require_on_branch: "{DEVELOP_BRANCH}"
    pre_commands:
      - git checkout {RELEASE_BRANCH}
      - "git merge {DEVELOP_BRANCH} -m \"chore: merge branch '{DEVELOP_BRANCH}' into '{RELEASE_BRANCH}'\""
    post_commands:
      - 'git commit -m "chore: bump version to {VERSION}"'
      - git tag {VERSION_TAG}
      - uv lock
      - git add uv.lock
      - 'git commit -m "chore: update uv.lock"'
      - git checkout {DEVELOP_BRANCH}
      - "git merge {RELEASE_BRANCH} -m \"chore: merge branch '{RELEASE_BRANCH}' into '{DEVELOP_BRANCH}'\""

default_flow: release
```

This is a `flows:` entry in your own `.vbump.yaml`, keyed by whatever name you'll pass to `--flow`/`default_flow:` — here, `release`. The commands that run before the version files are rewritten go under `pre_commands`; the ones after go under `post_commands`. `default_flow:` picks which flow (if any) runs when neither `--flow NAME` nor `--no-flow` is given on the command line.

The `uv lock`/`git add uv.lock`/`git commit` trio above is exactly the kind of project-specific step a flow needs room for: refreshing a lock file after the version in `pyproject.toml` changes, then committing that alongside the version bump itself.

If you use [Git flow](https://nvie.com/posts/a-successful-git-branching-model/) in your projects, here's a flow that drives its `release` branch commands directly, gated on the `develop` branch it expects:

```yaml
flows:
  git-flow:
    name: Git flow
    require_on_branch: develop
    pre_commands:
      - git flow release start {VERSION}
    post_commands:
      - git flow release finish {VERSION}

default_flow: git-flow
```

Fields:

| Field               | Default  | Meaning                                                                                                                                                                                                                                                                   |
|---------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `name`              | *(none)* | Human-readable display name (help/list output only — the flow key is what `--flow`/`default_flow:` actually matches).                                                                                                                                                     |
| `require_on_branch` | *(none)* | Aborts the run unless the current Git branch matches exactly. May itself be a `{NAME}` placeholder (e.g. `"{DEVELOP_BRANCH}"`), resolved against this flow's own `variables:`.                                                                                            |
| `variables`         | `{}`     | Arbitrary `{NAME: value}` data, each entry substituted as a `{NAME}` placeholder into every command (e.g. `RELEASE_BRANCH: main` above makes `{RELEASE_BRANCH}` available). Keys may not be `VERSION` or `VERSION_TAG`, reserved for the two placeholders below.          |
| `pre_commands`      | `[]`     | Commands run, in order, before write-back. Any failure aborts the flow immediately — write-back and `post_commands` never run.                                                                                                                                            |
| `post_commands`     | `[]`     | Commands run, in order, after write-back. Any failure aborts the flow immediately — remaining `post_commands` never run.                                                                                                                                                  |

Each command is a single string, run through the operating system's own command shell after placeholder substitution — `/bin/sh` on Unix-like systems, `cmd.exe` on Windows. A command sequence meant to behave identically on both needs to stick to syntax both shells understand, or be split into separate, simpler commands. `{VERSION}` and `{VERSION_TAG}` (the computed version and its tagged form, `version_tag_prefix` + version) are always available; a `{NAME}` placeholder referenced without a matching `variables:` entry is left as literal, unreplaced text rather than erroring. Substitution is verbatim — no value is quoted or escaped on the command's behalf, so a command relying on a substituted value being treated as a single shell word is responsible for its own quoting.

`--dry-run` turns every command in the flow into a `Would execute: ...` report — nothing is actually run, and no files are written. There is no rollback if a command fails partway through a flow: the remaining commands are skipped, write-back never runs if the failure was in `pre_commands`, and which step failed is reported plainly. Recovering the repository from there is up to you.

#### Reusing a flow across projects: `~/.vbumpconfig.yaml`

A flow like the `release` example above is often identical across several of your projects, save for one or two variables. Rather than repeating its full definition in every `.vbump.yaml`, define it once in `~/.vbumpconfig.yaml` — a single, optional, per-user file — and pull it into a project by name:

```yaml
# ~/.vbumpconfig.yaml
version: 3
flows:
  release:
    name: Release to main
    require_on_branch: "{DEVELOP_BRANCH}"
    variables:
      DEVELOP_BRANCH: develop
      RELEASE_BRANCH: main
    pre_commands:
      - git checkout {RELEASE_BRANCH}
      - "git merge {DEVELOP_BRANCH} -m \"chore: merge branch '{DEVELOP_BRANCH}' into '{RELEASE_BRANCH}'\""
    post_commands:
      - 'git commit -m "chore: bump version to {VERSION}"'
      - git tag {VERSION_TAG}
      - git checkout {DEVELOP_BRANCH}
      - "git merge {RELEASE_BRANCH} -m \"chore: merge branch '{RELEASE_BRANCH}' into '{DEVELOP_BRANCH}'\""
```

```yaml
# a project's .vbump.yaml
flows:
  my-release:
    recall: release
    variables:
      RELEASE_BRANCH: master

default_flow: my-release
```

`recall: NAME` adopts that flow's definition wholesale (`name`, `require_on_branch`, `pre_commands`, `post_commands`); the entry may only additionally set `variables`, merged key-by-key onto the recalled definition's own (your keys win, everything else from `~/.vbumpconfig.yaml` survives). Naming a flow that isn't defined there is a configuration error, reported at the point the flow is resolved. `~/.vbumpconfig.yaml` is checked at one single, fixed location — a project without a `recall:` anywhere is entirely unaffected by whether this file exists or what it contains. A flow defined in `~/.vbumpconfig.yaml` cannot itself use `recall:` — it must be a full definition.

`~/.vbumpconfig.yaml` requires the same `version: 3` marker as a project's own `.vbump.yaml`.
