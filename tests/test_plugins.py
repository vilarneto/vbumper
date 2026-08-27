import unittest
from typing import Iterator

from vbumper.config.flow import FlowConfig
from vbumper.config.root import VBumpConfig
from vbumper.core.configs.protocols import DiscovererConfigProtocol
from vbumper.core.discoverers.protocols import DiscovererProtocol
from vbumper.core.plugins import installer as _installer_module
from vbumper.core.plugins.installer import (
    get_config_cls,
    install_plugin,
    install_plugins,
    iter_registered_flows,
)


class _FakePlugin:
    """A minimal `VBumpPluginProtocol` implementation contributing no config classes and a
    fixed set of flows, for exercising the registry without depending on the real (in-tree or
    entry-point-installed) plugins."""

    def __init__(self, flows: dict[str, FlowConfig]):
        self._flows = flows

    def iter_config_classes(
        self,
    ) -> Iterator[type[DiscovererConfigProtocol[DiscovererProtocol]]]:
        return iter(())

    def iter_flows(self) -> Iterator[tuple[str, FlowConfig]]:
        yield from self._flows.items()


class PluginRegistryTestCase(unittest.TestCase):
    """Base class: restores the real (entry-point-derived) plugin registry after each test, so
    a test that installs a fake plugin never leaks into later tests."""

    def setUp(self):
        install_plugins()
        self.addCleanup(install_plugins)


class TestInstallPluginFlows(PluginRegistryTestCase):
    def test_installing_a_plugin_registers_its_flows(self):
        flow = FlowConfig(name="fake flow")
        install_plugin(_FakePlugin({"fake-flow": flow}))

        self.assertIn(("fake-flow", flow), list(iter_registered_flows()))

    def test_two_plugins_contributing_disjoint_flow_keys_both_register(self):
        flow_a = FlowConfig(name="flow a")
        flow_b = FlowConfig(name="flow b")
        install_plugin(_FakePlugin({"flow-a": flow_a}))
        install_plugin(_FakePlugin({"flow-b": flow_b}))

        registered = dict(iter_registered_flows())
        self.assertEqual(registered["flow-a"], flow_a)
        self.assertEqual(registered["flow-b"], flow_b)

    def test_duplicate_flow_key_across_plugins_raises(self):
        install_plugin(_FakePlugin({"dup": FlowConfig(name="first")}))
        with self.assertRaises(ValueError):
            install_plugin(_FakePlugin({"dup": FlowConfig(name="second")}))

    def test_duplicate_flow_key_leaves_the_first_registration_intact(self):
        first = FlowConfig(name="first")
        install_plugin(_FakePlugin({"dup": first}))
        with self.assertRaises(ValueError):
            install_plugin(_FakePlugin({"dup": FlowConfig(name="second")}))

        self.assertEqual(dict(iter_registered_flows())["dup"], first)

    def test_install_plugins_resets_flow_registry(self):
        install_plugin(_FakePlugin({"transient": FlowConfig(name="transient")}))
        self.assertIn("transient", dict(iter_registered_flows()))

        install_plugins()

        self.assertNotIn("transient", dict(iter_registered_flows()))


class TestStockFlowsAreRegistered(PluginRegistryTestCase):
    """`install_plugins()` picks up the stock plugin via the `vbumper.plugin` entry point (see
    `pyproject.toml`), which must contribute `git-flow`/`git-main` -- see
    `vbumper.core.entry_point.CorePlugin.iter_flows`."""

    def test_git_flow_and_git_main_are_registered_by_default(self):
        registered = dict(iter_registered_flows())
        self.assertIn("git-flow", registered)
        self.assertIn("git-main", registered)

    def test_git_flow_matches_the_documented_command_sequence(self):
        flow = dict(iter_registered_flows())["git-flow"]
        self.assertEqual(flow.require_on_branch, "develop")
        self.assertEqual(flow.pre_commands, [["git", "flow", "release", "start", "{VERSION}"]])
        self.assertEqual(flow.post_commands, [["git", "flow", "release", "finish", "{VERSION}"]])

    def test_git_main_matches_the_documented_command_sequence(self):
        flow = dict(iter_registered_flows())["git-main"]
        self.assertEqual(flow.require_on_branch, "{DEVELOP_BRANCH}")
        self.assertEqual(flow.variables, {"DEVELOP_BRANCH": "develop", "RELEASE_BRANCH": "main"})
        self.assertEqual(
            flow.pre_commands,
            [
                ["git", "checkout", "{RELEASE_BRANCH}"],
                [
                    "git",
                    "merge",
                    "{DEVELOP_BRANCH}",
                    "-m",
                    "chore: merge branch '{DEVELOP_BRANCH}' into '{RELEASE_BRANCH}'",
                ],
            ],
        )
        self.assertEqual(
            flow.post_commands,
            [
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
        )

    def test_stock_config_classes_are_still_registered_alongside_stock_flows(self):
        # Sanity check that adding `iter_flows()` didn't disturb the pre-existing config-class
        # registration path on the same plugin.
        get_config_cls("pyproject-toml")  # no raise


class TestAllFlowsMerge(PluginRegistryTestCase):
    def test_all_flows_includes_plugin_contributed_flows_with_no_project_config(self):
        config = VBumpConfig.default()
        self.assertIn("git-flow", config.all_flows)
        self.assertIn("git-main", config.all_flows)

    def test_project_flow_with_a_new_key_is_added_alongside_plugin_flows(self):
        custom = FlowConfig(name="custom")
        config = VBumpConfig(flows={"custom": custom})

        all_flows = config.all_flows
        self.assertIn("git-flow", all_flows)
        self.assertIn("git-main", all_flows)
        self.assertEqual(all_flows["custom"], custom)

    def test_project_flow_tunes_name_and_require_on_branch_on_a_plugin_flow(self):
        stock = dict(iter_registered_flows())["git-main"]
        override = FlowConfig(name="overridden git-main", require_on_branch="trunk")
        config = VBumpConfig(flows={"git-main": override})

        merged = config.all_flows["git-main"]
        self.assertEqual(merged.name, "overridden git-main")
        self.assertEqual(merged.require_on_branch, "trunk")
        # Everything the override left unset survives from the stock flow.
        self.assertEqual(merged.pre_commands, stock.pre_commands)
        self.assertEqual(merged.post_commands, stock.post_commands)
        self.assertEqual(merged.variables, stock.variables)
        # The plugin's own definition is untouched -- only this config's view is overridden.
        self.assertNotEqual(dict(iter_registered_flows())["git-main"], merged)

    def test_project_flow_merges_variables_key_by_key_onto_a_plugin_flow(self):
        config = VBumpConfig(flows={"git-main": FlowConfig(variables={"RELEASE_BRANCH": "master"})})

        merged = config.all_flows["git-main"]
        self.assertEqual(
            merged.variables, {"DEVELOP_BRANCH": "develop", "RELEASE_BRANCH": "master"}
        )
        # The precondition tracks the (unchanged) DEVELOP_BRANCH variable, not a stale copy.
        self.assertEqual(merged.require_on_branch, "{DEVELOP_BRANCH}")

    def test_project_flow_cannot_override_pre_commands_on_a_plugin_flow(self):
        from vbumper.core.exceptions import ConfigurationError

        config = VBumpConfig(flows={"git-main": FlowConfig(pre_commands=[["echo", "hi"]])})

        with self.assertRaises(ConfigurationError):
            _ = config.all_flows

    def test_project_flow_cannot_override_post_commands_on_a_plugin_flow(self):
        from vbumper.core.exceptions import ConfigurationError

        config = VBumpConfig(flows={"git-main": FlowConfig(post_commands=[["echo", "hi"]])})

        with self.assertRaises(ConfigurationError):
            _ = config.all_flows

    def test_all_flows_is_recomputed_live_from_the_registry(self):
        config = VBumpConfig.default()
        self.assertNotIn("fake-flow", config.all_flows)

        install_plugin(_FakePlugin({"fake-flow": FlowConfig(name="fake")}))

        self.assertIn("fake-flow", config.all_flows)


class TestModuleLevelRegistryState(unittest.TestCase):
    """Guards the two private registries directly (looked up fresh on the module each time,
    since `install_plugins()` reassigns rather than mutates them in place) -- a regression here
    (e.g. `install_plugin` populating the wrong dict) would silently break every other test in
    this module without one direct check of the underlying state."""

    def setUp(self):
        install_plugins()
        self.addCleanup(install_plugins)

    def test_flow_and_config_class_registries_share_install_plugins_lifecycle(self):
        install_plugin(_FakePlugin({"fake-flow": FlowConfig(name="fake")}))

        self.assertIn("fake-flow", _installer_module._flow_by_key)
        # Unaffected: the fake plugin contributed no config classes.
        self.assertIn("pyproject-toml", _installer_module._config_cls_by_type)


if __name__ == "__main__":
    unittest.main()
