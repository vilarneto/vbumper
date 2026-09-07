Writing a plugin
=================

The built-in discoverer types (``pyproject-toml``, ``package-json``, ``info-plist``,
``xcode-pbxproj``, ``setup-py``, ``python-version``, and ``file-regexp`` itself) all ship through
the exact same extension mechanism a third-party package uses: a Python entry point in the
``vbumper.plugin`` group. This page walks through that mechanism so you can add your own
discoverer type as an installable plugin, without forking vbumper or waiting on a built-in.

.. note::
   There's no auto-generated API reference from docstrings yet -- this page is hand-written and
   kept in sync by hand for now. The in-tree source referenced below is the authoritative detail
   if anything here goes stale.

What a plugin contributes
--------------------------

A plugin contributes **discoverer configuration classes only**. Flows (Git workflows) are never
plugin- or code-contributed -- a named flow only ever comes from a project's own ``flows:`` or
from ``~/.vbumpconfig.yaml``'s ``flows:`` pulled in via ``recall:`` (see :doc:`../guide/git-workflows`).
This is a deliberate, structural restriction: ``VBumpPluginProtocol`` simply has no method through
which a flow could be contributed.

The protocol a plugin implements
-----------------------------------

``vbumper.core.plugins.protocols.VBumpPluginProtocol`` is a single-method
:class:`typing.Protocol`:

.. code-block:: python

   class VBumpPluginProtocol(Protocol):
       def iter_config_classes(self) -> Iterator[type[DiscovererConfigProtocol[DiscovererProtocol]]]:
           """Iterate over all discoverer configuration classes that this plugin provides."""
           ...

A plugin class implements this protocol (structurally -- there's no base class to inherit from)
and yields one or more discoverer config classes from ``iter_config_classes()``.

The shape a discoverer config class satisfies
------------------------------------------------

Each yielded class must satisfy ``vbumper.core.configs.protocols.DiscovererConfigProtocol``
structurally, not by inheritance -- pydantic's metaclass conflicts with ``Protocol``, which is why
every built-in config class (e.g. ``RegularExpressionFileConfig``) is a plain
``pydantic.BaseModel`` that happens to satisfy this shape rather than a subclass of it. Three
members are required:

- ``get_type() -> str`` (classmethod) -- the ``type:`` string used in a project's
  ``.vbump.yaml`` (lowercase letters and hyphens only, e.g. ``"file-regexp"``).
- ``from_config_dict(data: dict) -> Self`` (classmethod) -- builds the config instance from the
  raw YAML dict given under that discoverer's entry.
- ``create_discoverer(*, path_exclude_patterns=(), dir_root=None) -> Discoverer`` -- builds the
  runtime discoverer object. ``path_exclude_patterns`` carries the project-wide ``exclude:``
  patterns; ``dir_root`` carries the CLI's ``--dir``/``-d`` value as a resolved ``Path``.
  Implementations that have no use for either (e.g. a discoverer that isn't file-based at all)
  may ignore them, but must still accept both parameters so callers can thread them through
  uniformly regardless of which discoverer type is in play.

A class whose ``from_config_dict({})`` succeeds with no user-supplied parameters at all is
"auto-detectable": that's exactly the set of true zero-config built-ins (``pyproject-toml``,
``package-json``, ...) that ``vbump init`` can offer without the user naming them explicitly. A
type like ``file-regexp`` requires an ``include:`` pattern to mean anything, so it's naturally
excluded from that auto-detection with no separate list to maintain.

Registering the entry point
------------------------------

vbumper's own in-tree discoverers register through exactly the mechanism a third-party plugin
package uses. In ``pyproject.toml``:

.. code-block:: toml

   [project.entry-points."vbumper.plugin"]
   core = "vbumper.core.entry_point:CorePlugin"

A third-party plugin package adds the same table to its own ``pyproject.toml``, entry-point group
``vbumper.plugin``, pointing at its own callable class implementing ``VBumpPluginProtocol``. Once
that package is installed alongside ``vbumper`` (into the same environment ``vbump`` runs in),
its config classes become available under their ``get_type()`` names in any project's
``discoverers:`` list, with no other configuration.

``vbumper.core.entry_point.CorePlugin`` is the reference implementation to model:

.. code-block:: python

   class CorePlugin(VBumpPluginProtocol):
       def iter_config_classes(self) -> Iterator[type[DiscovererConfigProtocol[DiscovererProtocol]]]:
           from vbumper.core.files.builtins.infoplist import InfoPlistFileConfig
           from vbumper.core.files.builtins.npm import PackageJsonFileConfig
           from vbumper.core.files.builtins.pbxproj import PBXProjFileConfig
           from vbumper.core.files.builtins.pyproject import PyProjectTomlFileConfig
           from vbumper.core.files.builtins.pythonversion import PythonVersionFileConfig
           from vbumper.core.files.builtins.setuppy import SetupPyFileConfig
           from vbumper.core.files.config import RegularExpressionFileConfig

           yield RegularExpressionFileConfig
           yield PyProjectTomlFileConfig
           yield PackageJsonFileConfig
           yield InfoPlistFileConfig
           yield PBXProjFileConfig
           yield SetupPyFileConfig
           yield PythonVersionFileConfig

At startup, ``vbumper.core.plugins.installer.install_plugins()`` iterates every installed
``vbumper.plugin`` entry point, instantiates each plugin, and indexes every config class it
yields by its ``get_type()`` string -- registering two config classes under the same type string
(whether from the same plugin or two different ones) is a hard error, so a plugin's ``type:``
choice should be namespaced enough to avoid colliding with core or another third party's plugin.
