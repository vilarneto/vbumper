from typing import TYPE_CHECKING, Iterator

from vbumper.core.configs.protocols import DiscovererConfigProtocol
from vbumper.core.plugins import VBumpPluginProtocol

if TYPE_CHECKING:
    from vbumper.core.discoverers.protocols import DiscovererProtocol


class CorePlugin(VBumpPluginProtocol):
    """Registers the discoverer config classes that ship in-tree with vbumper itself, as opposed
    to ones installed from a separate plugin distribution. Contributes no flows -- see
    `README.md`'s recipes for the Git workflows that used to ship as built-in flows."""

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


__all__ = ["CorePlugin"]
