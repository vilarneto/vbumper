Version Bumper
===============

*Version Bumper* keeps a project's `Semantic Versioning <https://semver.org/>`_ number in sync
across every place that declares it: ``pyproject.toml``, ``package.json``, an Xcode project, a
Sphinx ``conf.py``, CI config, among references in your own source code, documentation files,
etc. It can optionally drive a release's Git workflow (tagging, branch merges) as part of the
version bumping action.

It solves the recurring pain of a version living in several files at once and going stale in some
of them after a manual bump: *Version Bumper* refuses to write anything if the files it finds
disagree, and rewrites every file in place, changing only the version string and leaving
everything else about the file untouched.

Installation instructions and a minimal taste of the command line are in the project's
`README <https://github.com/vilarneto/vbumper#readme>`_. This site is the full reference.

Newcomers
---------

.. toctree::
   :maxdepth: 2

   newcomers/intro

Guide
-----

.. toctree::
   :maxdepth: 2

   guide/configuration
   guide/file-regexp
   guide/git-workflows

Plugin developers
------------------

.. toctree::
   :maxdepth: 2

   plugins/index

Reference
---------

.. toctree::
   :maxdepth: 2

   cli/index
