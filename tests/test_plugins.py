import unittest
from typing import Iterator

from vbumper.core.configs.protocols import DiscovererConfigProtocol
from vbumper.core.discoverers.protocols import DiscovererProtocol
from vbumper.core.entry_point import CorePlugin
from vbumper.core.plugins import installer as _installer_module
from vbumper.core.plugins.installer import get_config_cls, install_plugin, install_plugins


class _FakePlugin:
    """A minimal `VBumpPluginProtocol` implementation contributing a fixed set of config
    classes, for exercising the registry without depending on the real (in-tree or
    entry-point-installed) plugins."""

    def __init__(self, config_classes):
        self._config_classes = config_classes

    def iter_config_classes(
        self,
    ) -> Iterator[type[DiscovererConfigProtocol[DiscovererProtocol]]]:
        yield from self._config_classes


class PluginRegistryTestCase(unittest.TestCase):
    """Base class: restores the real (entry-point-derived) plugin registry after each test, so
    a test that installs a fake plugin never leaks into later tests."""

    def setUp(self):
        install_plugins()
        self.addCleanup(install_plugins)


class TestInstallPluginConfigClasses(PluginRegistryTestCase):
    def test_duplicate_config_type_across_plugins_raises(self):
        from vbumper.core.files.builtins.pyproject import PyProjectTomlFileConfig

        with self.assertRaises(ValueError):
            install_plugin(_FakePlugin([PyProjectTomlFileConfig]))

    def test_install_plugins_resets_config_class_registry(self):
        get_config_cls("pyproject-toml")  # no raise: the stock plugin registered it

        install_plugins()

        get_config_cls("pyproject-toml")  # still no raise: re-registered from scratch


class TestStockPluginContributesNoFlows(unittest.TestCase):
    """Flows are never plugin-contributed -- a named flow comes from a project's own `flows:` or
    from `~/.vbumpconfig.yaml` (see `vbumper.config.flow.FlowConfig.recall`). `CorePlugin` (and
    `VBumpPluginProtocol` in general) has no `iter_flows` at all."""

    def test_core_plugin_has_no_iter_flows(self):
        self.assertFalse(hasattr(CorePlugin(), "iter_flows"))


class TestModuleLevelRegistryState(unittest.TestCase):
    """Guards the private config-class registry directly (looked up fresh on the module each
    time, since `install_plugins()` reassigns rather than mutates it in place)."""

    def setUp(self):
        install_plugins()
        self.addCleanup(install_plugins)

    def test_install_plugin_populates_the_config_class_registry(self):
        from vbumper.core.files.builtins.npm import PackageJsonFileConfig

        self.assertIn("package-json", _installer_module._config_cls_by_type)
        self.assertIs(_installer_module._config_cls_by_type["package-json"], PackageJsonFileConfig)


if __name__ == "__main__":
    unittest.main()
