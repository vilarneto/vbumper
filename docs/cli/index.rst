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

``vbump flow add`` isn't a true Click subcommand of ``flow`` above (see
:mod:`vbumper.cli.flow`'s docstring for why), so ``:nested: full`` can't reach its own options --
documented directly instead, from the same underlying command object:

.. click:: vbumper.cli.flow:add_command
   :prog: vbump flow add
