Getting started
===============

A project's version number may live in more than one place. The build tool reads it from
``pyproject.toml`` or ``package.json`` to stamp the artifact it publishes; the binary itself
needs to know it to answer ``--version`` on the command line or fill in an "About" dialog; a
mobile app shows it in the splash screen; a Web app embeds it into the header or the footer; the
docs site shows it in a corner via Sphinx's ``release``; CI config pins it for a release job; and
so on.

Each of these is an independent artifact, and a single project can easily accumulate a handful of
them: a Python package might declare its version in ``pyproject.toml`` for packaging, again in a
Sphinx ``conf.py`` for the docs build, and once more in a ``.gitlab-ci.yml`` pin for a release
job. The trouble starts once a release means touching all of them by hand: it's easy to bump the
package version and forget the docs, or update an Xcode target's ``Info.plist`` and leave a
sibling test target's copy behind. Nothing enforces that they stay in agreement, so drift is
silent.

Installation
------------

*Version Bumper* is distributed on PyPI as the `vbumper <https://pypi.org/project/vbumper/>`_
package. It's a standalone command-line tool, so the recommended way to install it is into its
own isolated environment with `pipx <https://pipx.pypa.io>`_ -- this keeps its dependencies
separate from any project you run it against, while still putting the ``vbump`` command on your
``PATH``:

.. code-block:: bash

   pipx install vbumper

If you don't have ``pipx`` yet, install it first (`full instructions
<https://pipx.pypa.io/stable/installation/>`_):

.. code-block:: bash

   # macOS
   brew install pipx
   pipx ensurepath

   # Windows (with Scoop)
   scoop install pipx
   pipx ensurepath

   # Otherwise, on any platform with Python already installed
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath

You can also install ``vbumper`` with `uv <https://docs.astral.sh/uv/>`_, which works the same
way as ``pipx`` here:

.. code-block:: bash

   uv tool install vbumper

To upgrade later:

.. code-block:: bash

   pipx upgrade vbumper
   # or: uv tool upgrade vbumper

To use ``vbump`` as part of a ``uv``-managed project's own tooling instead -- e.g. so ``uv run
vbump`` picks up a pinned version -- add it as a dev dependency:

.. code-block:: bash

   uv add --dev vbumper

Any other way of installing a PyPI package (``pip install vbumper``, ...) works the same way,
though it's not recommended for a standalone CLI tool, since it either pollutes your current
environment or requires you to manage a dedicated one yourself.

Try it on a real project
-------------------------

The best way to get a feel for *Version Bumper* is to run it somewhere it has nothing to lose:
``cd`` into an existing Python or Node project (something with a ``pyproject.toml`` or
``package.json`` will do). Nothing below writes anything until the "Bump it" step, so feel free to
follow along on a real repo.

**Start with a config file.** *Version Bumper* needs a ``.vbump.yaml`` file at the project root.
You don't have to write one by hand: ``vbump init`` scans the directory and generates a starting
one for you:

.. code-block:: console

   $ vbump init
   Wrote .vbump.yaml
   Detected discoverers: pyproject-toml

It found your ``pyproject.toml`` and wrote this:

.. code-block:: yaml

   # .vbump.yaml
   version: 3

   discoverers:
     - type: pyproject-toml

Most important here is the ``discoverers:`` key: it lists the places to look for version
annotations -- here, the one entry ``init`` wrote means, "the ``version = \"...\"`` line in
``pyproject.toml``."

Each entry under ``discoverers:`` is called a *discoverer* -- a rule for finding and reading a
version somewhere. ``vbump init`` only pre-fills what it actually found; from here on, teaching
*Version Bumper* about a new place to look, another built-in or a pattern of your own, means
adding another line under ``discoverers:`` by hand (see :doc:`../guide/file-regexp`).

**See what it finds.** Once a config file exists, ``list`` goes looking for exactly what it
names:

.. code-block:: console

   $ vbump list
   File pyproject.toml  1.2.3

Just one file here, but the same command works whether it names one *container* -- *Version
Bumper*'s term for any place a discoverer actually finds and reads a version, a file in every
example in this walkthrough -- or a dozen: a ``pyproject.toml`` next to a ``package.json`` for a
bundled frontend, an Xcode project with several targets, a Dockerfile pin, all of them read
together. Agreement is the whole point: whatever *Version Bumper* is told to look for, ``list``
confirms every place found is telling the same story. If a project has more than one container and
they disagree -- the docs still stuck on ``1.2.2`` after ``pyproject.toml`` got bumped by hand
ahead of a release -- ``list`` would show that mismatch instead, and every command below would
refuse to touch anything until it's sorted out (or waved through with
``--allow-incompatible-versions``, once you've confirmed the divergence is fine).

**Ask for just the version.** Once you trust the files agree, ``print`` gives you the one number,
with nothing else -- handy for scripting a build step:

.. code-block:: console

   $ vbump print
   1.2.3

``vbump print`` is a nice one-liner that can be used in shell scripts:

.. code-block:: text

   CURRENT_VERSION=$(vbump print)

**Preview before touching anything.** ``-n``/``--dry-run`` runs the full command but reports what
*would* change instead of changing it -- the safest way to see a command's effect for the first
time:

.. code-block:: console

   $ vbump -n patch
   Would update File pyproject.toml: 1.2.3 -> 1.2.4

**Bump it for real.** Drop ``-n`` once you're happy with the preview, and the file is rewritten in
place -- nothing else about it changes, only the version string:

.. code-block:: console

   $ vbump patch
   Updated File pyproject.toml: -> 1.2.4

**Chain steps together.** Cutting a release candidate for the next minor version is two logical
bumps, but one release: ``minor`` computes ``1.3.0``, then ``rc`` moves that straight into
``1.3.0-rc.1``, and both are written together, once:

.. code-block:: console

   $ vbump minor rc
   Updated File pyproject.toml: -> 1.3.0-rc.1

**Iterate on the prerelease, then release it.** Each further ``rc`` (or the token-agnostic
``lower``) advances the serial; ``stable`` drops the prerelease tag once you're ready to ship:

.. code-block:: console

   $ vbump rc       # 1.3.0-rc.1 -> 1.3.0-rc.2
   $ vbump stable   # 1.3.0-rc.2 -> 1.3.0

**Reach for** ``set`` **when you need an exact number**, bypassing the usual increment logic
entirely -- useful right after adopting Version Bumper in a project, or to jump to a version
scheme change:

.. code-block:: console

   $ vbump set 2.0.0-beta.1
   Updated File pyproject.toml: -> 2.0.0-beta.1

Every one of these commands scales to as many containers as your config names -- a second
``discoverers:`` entry means a second line in each of the outputs above, updated in lockstep,
nothing more.

That covers the everyday loop: ``init`` once, then look with ``list``/``print``, preview with
``-n``, then bump, chain, or ``set``. Everything from here on -- the full command/option
reference, config, built-in file types, Git workflows -- fills in the edges of that loop.

How it works
-------------

Every run walks through the same five steps:

1. **Discover.** Version Bumper scans a directory for every *version container* named under the
   config's ``discoverers:`` -- a file that holds a version number, recognized by name/path and
   content pattern (``pyproject.toml``, ``package.json``, an Xcode project, ...).

2. **Read.** Each container yields its current version, which falls into one of four states:

   - **versioned**: holds a single, valid version;
   - **unversioned**: explicitly empty (e.g. ``"version": ""``) -- a normal, no-warning "not set
     yet" state, distinct from a file that never declares a version field at all (which isn't a
     version container in the first place);
   - **invalid**: holds something that fails to parse as semver;
   - **mismatched**: holds two or more *different* values internally (some containers, like an
     Xcode target, keep more than one copy, e.g. one per build configuration).

   If the containers found in a project disagree (across containers, or within a single
   mismatched one), then Version Bumper stops and tells you. This safety check is the reason the
   tool exists in the first place; you can lift it explicitly with ``--allow-incompatible-versions``
   (see :doc:`../cli/index`) once you've confirmed the disagreement is fine.

3. **Bump.** With every container in agreement, Version Bumper computes the new version:
   increment major/minor/patch, move into or through a prerelease, drop a prerelease, or set an
   explicit value. Several of these can be chained in one invocation, applied left to right.

4. **Write back.** Every changed container is rewritten in place. An unversioned container is
   filled in with the resulting version.

5. **(Optional) Git workflow.** Wrap the write-back in a configurable sequence of Git commands
   (or any other commands): tag, merge, commit, whatever a release process calls for (see
   :doc:`../guide/git-workflows`).
