Recognizing your own file formats
==================================

Real projects almost always keep the version somewhere the built-ins don't know about: a
``Dockerfile``, a shell script, a Helm chart, a hand-rolled version header in a language Version
Bumper doesn't ship a recognizer for. This is one of the main reasons to reach for Version Bumper
in the first place -- you're not limited to the built-in list (see :doc:`configuration`), and
teaching it a new file takes one entry in ``.vbump.yaml``, no plugin or code required.

Worked examples
----------------

Say your project's ``Dockerfile`` pins the image version in an ``ARG``:

.. code-block:: dockerfile

   ARG VERSION=1.2.3

A few lines of config turn that into a container Version Bumper discovers, reads, and rewrites
right alongside ``pyproject.toml``:

.. code-block:: yaml

   version: 3

   discoverers:
     - type: file-regexp
       include: /Dockerfile
       version: '(?m)^ARG VERSION=(?P<version>.*)$'

.. code-block:: console

   $ vbump list
   pyproject.toml   1.2.3
   Dockerfile       1.2.3

   $ vbump patch
   Wrote pyproject.toml: 1.2.3 -> 1.2.4
   Wrote Dockerfile:     1.2.3 -> 1.2.4

That's the whole recipe: a filename pattern (``include``) and a regular expression with a named
``(?P<version>...)`` group. The leading ``/`` in ``/Dockerfile`` anchors the pattern to the
discovery root; without it, ``Dockerfile`` would also match a nested one, like
``services/api/Dockerfile``, the same way ``.gitignore`` treats a leading slash. See `Fields`_
below for the full field reference, including matching by directory, encoding, and files with
more than one copy of the version to keep in sync.

A Sphinx docs build is another common case -- ``conf.py`` declares ``release = "..."``, but only
a ``conf.py`` that's actually Sphinx's own config file should ever be touched, not some unrelated
``conf.py`` a project happens to also have (a pytest fixture, another tool's config, ...). If your
project keeps that file at the conventional ``docs/source/conf.py`` path, an anchored,
depth-agnostic ``include:`` narrows to exactly that:

.. code-block:: yaml

   discoverers:
     - type: file-regexp
       include: "**/docs/source/conf.py"
       version: "(?m)^release = ['\"](?P<version>[^'\"]*)['\"]$"

(A different layout, e.g. ``docs/conf.py`` with no ``source/`` directory, just needs a matching
``include:`` glob for that path instead.)

A static HTML page can carry its version in its own ``<meta>`` tag -- there's no real HTML/web
standard for this, so it's always a per-project convention, but a common one:

.. code-block:: html

   <meta name="version" content="1.2.3">

.. code-block:: yaml

   discoverers:
     - type: file-regexp
       include: ["*.html", "*.htm"]
       version: '(?i)<meta\s+name="version"\s+content="(?P<version>[^"]*)"\s*/?>'

Fields
------

Anything else regex-shaped can be added with a ``file-regexp`` entry under ``discoverers:``. The
full shape:

.. code-block:: yaml

   discoverers:
     - type: file-regexp
       include: /docker/Dockerfile   # required; can also be a list
       version: '(?m)^ARG VERSION=(?P<version>.*)$'

.. list-table::
   :header-rows: 1

   * - Field
     - Default
     - Meaning
   * - ``version``
     - *(required)*
     - A regular expression with a named group ``(?P<version>...)``, matched against the file's
       full contents.
   * - ``include``
     - *(required)*
     - Gitignore-style pattern(s) narrowing which files are candidates for this entry, matched
       relative to the discovery root (``--dir``/``-d``, default ``.``). Must carry at least one
       pattern -- use an anchored pattern (e.g. ``/docker/**/Dockerfile``) to scope an entry to a
       subdirectory.
   * - ``encoding``
     - ``"utf-8"``
     - Text encoding used to read and write matching files.
   * - ``allow_multiple_matches``
     - ``false``
     - Whether more than one match inside the same file is allowed (and must agree) rather than
       treated as a hard error.

Everything about the matched file other than the version string itself is preserved untouched on
write-back.
