Git workflows
=============

A *flow* is a named sequence of commands run around the version write-back -- some before the
version files are rewritten, some after -- checking out a release branch, merging it, tagging the
result, whatever your release process needs.

Here is one, defined under the key ``release``: it checks out a release branch, merges the
development branch into it, then -- after the version files themselves are rewritten -- commits
and tags the bumped version, and merges the release branch back into development:

.. code-block:: yaml

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
       stage_command: git add "{CHANGED_FILE}"
       post_commands:
         - uv lock
         - git add uv.lock
         - 'git commit -m "chore: bump version to {VERSION}"'
         - git tag {VERSION_TAG}
         - git checkout {DEVELOP_BRANCH}
         - "git merge {RELEASE_BRANCH} -m \"chore: merge branch '{RELEASE_BRANCH}' into '{DEVELOP_BRANCH}'\""

   default_flow: release

This is a ``flows:`` entry in your own ``.vbump.yaml``, keyed by whatever name you'll pass to
``--flow``/``default_flow:`` -- here, ``release``. The commands that run before the version files
are rewritten go under ``pre_commands``; the ones after go under ``post_commands``.
``default_flow:`` picks which flow (if any) runs when neither ``--flow NAME`` nor ``--no-flow`` is
given on the command line.

``stage_command`` is what actually stages the version-bumped files above: vbumper itself never
runs ``git add`` (or any other staging command) on its own -- writing a new version into a file
and staging it are different concerns, and blindly staging *everything* dirty in the working tree
(``git add -A``, ``git commit -a``) risks sweeping in unrelated changes you never meant to commit.
Set ``stage_command`` explicitly and it runs once per file vbumper actually wrote this run, with
``{CHANGED_FILE}`` substituted to that file's path -- so ``git commit`` below has something to
commit. Leave it unset and nothing is staged automatically, same as if the field didn't exist.

The ``uv lock``/``git add uv.lock`` pair above is exactly the kind of project-specific step a flow
needs room for: refreshing a lock file after the version in ``pyproject.toml`` changes, staged
*before* the commit below so the lock file update lands in the same commit as the version bump
itself, rather than a separate one.

If you use `Git flow <https://nvie.com/posts/a-successful-git-branching-model/>`_ in your
projects, here's a flow that drives its ``release`` branch commands directly, gated on the
``develop`` branch it expects:

.. code-block:: yaml

   flows:
     git-flow:
       name: Git flow
       require_on_branch: develop
       pre_commands:
         - git flow release start {VERSION}
       stage_command: git add "{CHANGED_FILE}"
       post_commands:
         - git flow release finish {VERSION}

   default_flow: git-flow

Fields
------

.. list-table::
   :header-rows: 1

   * - Field
     - Default
     - Meaning
   * - ``name``
     - *(none)*
     - Human-readable display name (help/list output only -- the flow key is what
       ``--flow``/``default_flow:`` actually matches).
   * - ``require_on_branch``
     - *(none)*
     - Aborts the run unless the current Git branch matches exactly. May itself be a ``{NAME}``
       placeholder (e.g. ``"{DEVELOP_BRANCH}"``), resolved against this flow's own ``variables:``.
   * - ``variables``
     - ``{}``
     - Arbitrary ``{NAME: value}`` data, each entry substituted as a ``{NAME}`` placeholder into
       every command (e.g. ``RELEASE_BRANCH: main`` above makes ``{RELEASE_BRANCH}`` available).
       Keys may not be ``VERSION``, ``VERSION_TAG``, or ``CHANGED_FILE``, reserved for vbumper's
       own placeholders.
   * - ``pre_commands``
     - ``[]``
     - Commands run, in order, before write-back. Any failure aborts the flow immediately --
       write-back, ``stage_command``, and ``post_commands`` never run.
   * - ``stage_command``
     - *(none)*
     - Optional command run once per file vbumper actually wrote this run, after write-back and
       before ``post_commands``, with ``{CHANGED_FILE}`` substituted to that file's path. Unset
       means nothing is staged automatically.
   * - ``post_commands``
     - ``[]``
     - Commands run, in order, after write-back (and after ``stage_command``, if set). Any
       failure aborts the flow immediately -- remaining ``post_commands`` never run.

Each command is a single string, run through the operating system's own command shell after
placeholder substitution -- ``/bin/sh`` on Unix-like systems, ``cmd.exe`` on Windows. A command
sequence meant to behave identically on both needs to stick to syntax both shells understand, or
be split into separate, simpler commands. ``{VERSION}`` and ``{VERSION_TAG}`` (the computed
version and its tagged form, ``version_tag_prefix`` + version) are always available in every
command; ``{CHANGED_FILE}`` is available only in ``stage_command`` -- it's left as literal,
unreplaced text in ``pre_commands``/``post_commands``, since it's only meaningful once per written
file. ``stage_command`` itself runs once per file that changed, substituting ``{CHANGED_FILE}`` to
that file's path each time -- including under ``--dry-run``, which previews one ``Would execute:
...`` line per file rather than performing any write. A ``{NAME}`` placeholder referenced without
a matching ``variables:`` entry is left as literal, unreplaced text rather than erroring.
Substitution is verbatim -- no value is quoted or escaped on the command's behalf, so a command
relying on a substituted value being treated as a single shell word is responsible for its own
quoting.

``--dry-run`` turns every command in the flow into a ``Would execute: ...`` report -- nothing is
actually run, and no files are written. There is no rollback if a command fails partway through a
flow: the remaining commands are skipped, write-back never runs if the failure was in
``pre_commands``, and which step failed is reported plainly. Recovering the repository from there
is up to you.

Reusing a flow across projects: ``~/.vbumpconfig.yaml``
----------------------------------------------------------

A flow like the ``release`` example above is often identical across several of your projects,
save for one or two variables. Rather than repeating its full definition in every
``.vbump.yaml``, define it once in ``~/.vbumpconfig.yaml`` -- a single, optional, per-user file --
and copy it into a project by name with ``vbump flow add``:

.. code-block:: yaml

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
       stage_command: git add "{CHANGED_FILE}"
       post_commands:
         - 'git commit -m "chore: bump version to {VERSION}"'
         - git tag {VERSION_TAG}
         - git checkout {DEVELOP_BRANCH}
         - "git merge {RELEASE_BRANCH} -m \"chore: merge branch '{RELEASE_BRANCH}' into '{DEVELOP_BRANCH}'\""

.. code-block:: console

   $ vbump flow add release --set RELEASE_BRANCH=master --set-default

writes a full, standalone copy of that flow straight into the project's own ``.vbump.yaml``:

.. code-block:: yaml

   # the project's .vbump.yaml, after the command above
   default_flow: release
   flows:
     release:
       name: Release to main
       require_on_branch: "{DEVELOP_BRANCH}"
       variables:
         DEVELOP_BRANCH: develop
         RELEASE_BRANCH: master
       pre_commands:
         - git checkout {RELEASE_BRANCH}
         - "git merge {DEVELOP_BRANCH} -m \"chore: merge branch '{DEVELOP_BRANCH}' into '{RELEASE_BRANCH}'\""
       stage_command: git add "{CHANGED_FILE}"
       post_commands:
         - 'git commit -m "chore: bump version to {VERSION}"'
         - git tag {VERSION_TAG}
         - git checkout {DEVELOP_BRANCH}
         - "git merge {RELEASE_BRANCH} -m \"chore: merge branch '{RELEASE_BRANCH}' into '{DEVELOP_BRANCH}'\""

Nothing in the written file points back at ``~/.vbumpconfig.yaml`` -- it's a genuinely standalone
flow from here on, indistinguishable from one written by hand. This matters the moment the
project is cloned onto another machine: whoever clones it gets a fully working flow with no
extra setup, whether or not *their* ``~/.vbumpconfig.yaml`` even exists.

``vbump flow add NAME`` accepts:

.. list-table::
   :header-rows: 1

   * - Option
     - Meaning
   * - ``--set NAME=value``
     - Override one variable in the copy (repeatable). Above, it's what turns the template's
       default ``RELEASE_BRANCH: main`` into ``master`` for this one project.
   * - ``--set-default``
     - Also set the project's ``default_flow:`` to this flow's key.
   * - ``--update``
     - Refresh an already-added flow from the (possibly since-edited) template -- ``name``,
       ``require_on_branch``, ``pre_commands``, ``stage_command``, and ``post_commands`` are all
       taken fresh from the template, but the project's own ``variables`` values are preserved
       (layered under any ``--set`` given on the same invocation, which wins). Without
       ``--update``, adding a flow whose key already exists locally is an error.

Naming a flow that isn't defined in ``~/.vbumpconfig.yaml`` is an error, listing what is
available there. ``~/.vbumpconfig.yaml`` is checked at one single, fixed location -- a project
that has never run ``vbump flow add`` is entirely unaffected by whether this file exists or what
it contains, and ``bump`` itself never reads it at all.

``~/.vbumpconfig.yaml`` requires the same ``version: 3`` marker as a project's own
``.vbump.yaml``.

Scaffolding a new project with flows already in place
-------------------------------------------------------

``vbump init --flows=NAME[,NAME...]`` does the same copy at scaffold time, for one or more flows
at once -- useful when a brand new project should start with its release flow already configured,
rather than running ``init`` and ``flow add`` as two separate steps:

.. code-block:: console

   $ vbump init --flows=release,hotfix

Each name is copied in exactly as defined in ``~/.vbumpconfig.yaml``, with no ``--set``/
``--set-default`` equivalent -- ``init`` stays a single, simple scaffolding step; adjust
variables or the default flow afterward with ``vbump flow add NAME --update`` (or by hand) if
needed. An unknown name fails before anything is written, the same as every other ``init``
validation.
