Configuration
=============

A ``.vbump.yaml`` (or ``.vbump.yml``) is required at your project root, as every discoverer
(built-in types included) is opt-in and must be listed under ``discoverers:`` to run (see
:doc:`../newcomers/intro` for ``vbump init``, which scaffolds one). Version Bumper looks for it
directly in the directory named by ``--dir``/``-d``, which must be a directory -- it does not walk
upward past that root looking for one.

.. code-block:: yaml

   version: 3
   version_tag_prefix: v

   exclude:
     - "**/testing/fixtures/"

   discoverers:
     - type: file-regexp
       include: /docker/Dockerfile
       version: '(?m)^ARG VERSION=(?P<version>.*)$'

Optionally driving a release's Git workflow as part of the same command is configured the same
way, under ``flows:``/``default_flow:`` -- see :doc:`git-workflows`.

A JSON Schema (``src/vbumper/config/vbumper-config.schema.json``) for this format ships with the
package, for editor validation/autocompletion.

Top-level keys
--------------

.. list-table::
   :header-rows: 1

   * - Key
     - Default
     - Meaning
   * - ``version``
     - *(required)*
     - Config format version. Must be ``3``.
   * - ``version_tag_prefix``
     - ``"v"``
     - Prefix prepended to the Git tag name by a flow's ``{VERSION_TAG}`` placeholder (never to
       file contents).
   * - ``exclude``
     - ``[]``
     - Extra gitignore-style patterns to prune from discovery, added on top of a large built-in
       default list (VCS directories, language/build caches, IDE folders, editor swap files,
       ...). A bare string is accepted in place of a one-element list. Applies to *every*
       discoverer, and can prune whole directories from the walk.
   * - ``discoverers``
     - ``[]``
     - Extra discoverer entries, added on top of the built-ins (see `Built-in containers`_ and
       :doc:`file-regexp`).
   * - ``flows``
     - ``{}``
     - Named Git (or other) release workflows (see :doc:`git-workflows`).
   * - ``default_flow``
     - *(none)*
     - Key of the flow to run when neither ``--flow`` nor ``--no-flow`` is given. Must name an
       entry under ``flows`` (see :doc:`git-workflows`).

``exclude`` vs. a discoverer's own ``include``
------------------------------------------------

Two different filters narrow down what discovery looks at -- both gitignore-style glob patterns
(matched via `pathspec <https://pypi.org/project/pathspec/>`_'s gitignore matcher, the same engine
Git itself uses for ``.gitignore``), but at different scope and with opposite intent:

- **``exclude:``** is project-wide and applies to every discoverer. It's a deny-list on top of
  the built-in defaults -- everything is a candidate except what it (or the defaults) rule out.
  Because it can rule out whole directories, an excluded directory is pruned from the walk
  entirely, never descended into.
- **A discoverer's own ``include:``** (only meaningful for ``file-regexp``; the other built-ins
  already know which filenames they're looking for) is local to that one entry, required, and an
  allow-list -- nothing is a candidate for that discoverer except what matches; project-wide
  ``exclude`` still applies on top. There's no separate "base directory" field to scope an entry
  to a subtree -- use an anchored pattern instead (e.g. ``include: /docker/**/Dockerfile``).
  Unlike ``exclude``, ``include`` never prunes directories -- a directory that doesn't itself
  match may still contain matching files below it.

Both accept a single pattern as a bare string, or a list of them, and support full gitignore
syntax, including negation (``!keep/this/``) to carve an exception back out of a broader pattern.

``.vbumpignore``
-----------------

Dropping an empty ``.vbumpignore`` file in any directory opts that whole subtree out of
discovery, the same way an ``exclude:``-matched directory is pruned -- regardless of what
``exclude``/``include`` patterns say. Its contents don't matter, only its presence; useful for a
vendored dependency, a generated output directory, or a scratch project nested inside the
repository, without needing the top-level config to know about it.

A ``.vbump.yaml``/``.vbump.yml`` found in a subdirectory Version Bumper descends into while
scanning is similarly never read or merged into the run doing the scanning -- it's pruned the same
way, with an advisory pointing at running ``vbump -d <subdir>`` separately. A monorepo with
independently versioned components needs multiple independent Version Bumper roots, not an
on-the-fly config merge.

Built-in containers
--------------------

Each of these takes no parameters beyond ``type:`` -- activating one is a single ``- type: ...``
line under ``discoverers:``, with no ``include:`` needed since the filename/key is fixed by
convention. ``xcode-pbxproj`` is the one exception, with an optional ``targets:`` field (see
below).

.. list-table::
   :header-rows: 1

   * - Type
     - File
     - What's matched
   * - ``pyproject-toml``
     - ``pyproject.toml``
     - ``version = "..."`` at the start of a line.
   * - ``package-json``
     - ``package.json``
     - The top-level ``"version"`` key, read/written as JSON -- every other key is preserved
       verbatim.
   * - ``info-plist``
     - ``Info.plist``
     - ``CFBundleShortVersionString``, gated on the file actually being a standard Apple property
       list.
   * - ``xcode-pbxproj``
     - ``project.pbxproj``
     - ``MARKETING_VERSION = ...;``, gated on the standard Xcode ASCII-plist header. Each
       ``PBXNativeTarget`` declared in the file (e.g. an app target and its test target) is
       discovered as its own, independent container -- bumping one never touches the other -- and
       a target's several build-configuration copies (typically Debug and Release) are treated as
       one container that must agree internally. An optional ``targets:`` field (a target name, or
       a list of them) restricts discovery to just those targets -- omitted (or ``~``) means every
       target, the default; an explicit empty list is rejected, since it could never match
       anything; a name that matches no ``PBXNativeTarget`` under the discovery root is a
       configuration error.
   * - ``setup-py``
     - ``setup.py``
     - A ``version="..."`` keyword argument to ``setup()``, at the start of a line.
   * - ``python-version``
     - ``__init__.py``, ``_version.py``, or ``version.py``
     - A top-level ``__version__ = "..."`` assignment, at the start of a line.
