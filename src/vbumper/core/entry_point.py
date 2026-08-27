from typing import TYPE_CHECKING, Iterator

from vbumper.core.configs.protocols import DiscovererConfigProtocol
from vbumper.core.plugins import VBumpPluginProtocol

if TYPE_CHECKING:
    from vbumper.config.flow import FlowConfig
    from vbumper.core.discoverers.protocols import DiscovererProtocol


class CorePlugin(VBumpPluginProtocol):
    """Registers the discoverer config classes and Git workflow flows that ship in-tree with
    vbumper itself, as opposed to ones installed from a separate plugin distribution."""

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

    def iter_flows(self) -> Iterator[tuple[str, FlowConfig]]:
        from vbumper.config.flow import FlowConfig

        yield (
            "git-flow",
            FlowConfig(
                name="Git flow",
                require_on_branch="develop",
                pre_commands=[["git", "flow", "release", "start", "{VERSION}"]],
                post_commands=[["git", "flow", "release", "finish", "{VERSION}"]],
            ),
        )
        yield (
            "git-main",
            FlowConfig(
                name="'main' version bump",
                require_on_branch="{DEVELOP_BRANCH}",
                variables={"DEVELOP_BRANCH": "develop", "RELEASE_BRANCH": "main"},
                pre_commands=[
                    ["git", "checkout", "{RELEASE_BRANCH}"],
                    [
                        "git",
                        "merge",
                        "{DEVELOP_BRANCH}",
                        "-m",
                        "chore: merge branch '{DEVELOP_BRANCH}' into '{RELEASE_BRANCH}'",
                    ],
                ],
                post_commands=[
                    ["git", "commit", "-m", "chore: bump version to {VERSION}"],
                    ["git", "tag", "{VERSION_TAG}"],
                    ["git", "checkout", "{DEVELOP_BRANCH}"],
                    [
                        "git",
                        "merge",
                        "{RELEASE_BRANCH}",
                        "-m",
                        "chore: merge branch '{RELEASE_BRANCH}' into '{DEVELOP_BRANCH}'",
                    ],
                ],
            ),
        )


__all__ = ["CorePlugin"]
