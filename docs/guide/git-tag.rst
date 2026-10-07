Projects with no version file at all
=====================================

Some projects keep no version string in any file: the only source of truth is the latest
``git tag``. This is common for libraries consumed only through their Git history (e.g. an
`iOS Swift package <https://www.swift.org/package-manager/>`_ pinned by tag) rather than a packaged release.

The ``git-tag`` discoverer reads the current version from the highest Semantic Version already
tagged in the repository, instead of from a file:

.. code-block:: yaml

   version: 3

   discoverers:
     - type: git-tag

   flows:
     release:
       name: Tag a release
       post_commands:
         - git tag {VERSION_TAG}
         - git push --tags

   default_flow: release

.. code-block:: console

   $ git tag
   v1.0.0
   v1.1.0
   v1.1.1
   v1.2.0
   v1.2.1
   v1.2.2
   v1.2.3

   $ vbump print
   1.2.3

   $ vbump patch
   Tagged: -> 1.2.4

``git-tag`` is **read-only**: it only ever reports the current version, it never writes anything
back. Creating the actual release tag is left to a flow's own ``post_commands`` (see
:doc:`git-workflows`), as in the example above.

``tag_prefix``
--------------

.. list-table::
   :header-rows: 1

   * - Field
     - Default
     - Meaning
   * - ``tag_prefix``
     - ``"v"``
     - Only tags starting with this prefix are candidates; the prefix is stripped before the
       remainder is parsed as a Semantic Version. An empty string matches every tag in the
       repository.

``tag_prefix`` is this entry's own field, independent of the top-level ``version_tag_prefix``
(which only governs a flow's ``{VERSION_TAG}`` placeholder). If a project uses a non-default
prefix for both reading and writing tags, set the same value in both places by hand; they are
never tied together automatically. A tag that doesn't start with ``tag_prefix``, or whose
remainder doesn't parse as a Semantic Version, is silently ignored rather than being treated as
a configuration error: an ordinary Git repository collects all kinds of unrelated tags over
time, and there is no file list to validate ``git-tag`` against the way other built-ins validate
against a path.

A repository with no matching tag at all is simply unversioned, the same as a fresh project with
an empty version file would be. That's not an error, just nothing to bump from yet (``vbump set
0.1.0`` establishes a starting point).

Not auto-detected by ``vbump init``
--------------------------------------

``vbump init`` never scaffolds a ``git-tag`` entry on its own: the mere presence of tags in a
repository is too weak a signal that a project actually wants this kind of discovery (most
repositories carry at least a few tags that have nothing to do with releases), and a repository
that isn't tagged yet would make the same zero-config probe simply fail outright. Add
``type: git-tag`` to ``discoverers:`` by hand when this is what your project needs.
