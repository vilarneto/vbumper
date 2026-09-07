CLI reference
=============

``vbump`` commands can be chained in one invocation and run in the order given, so **nothing is
written to disk until every chained subcommand has run**, and only if at least one container's
version actually changed:

.. code-block:: text

   vbump [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

Global options apply to the whole invocation and must come before the first subcommand. The
reference below is generated directly from ``vbump``'s own command definitions, so it can never
drift out of sync with the actual CLI.

.. click:: vbumper.cli._grp:root_grp
   :prog: vbump
   :nested: full
