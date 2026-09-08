import unittest
from unittest import mock

from vbumper.config.flow import FlowDefinition
from vbumper.config.global_config import GlobalConfig
from vbumper.config.root import VBumpConfig
from vbumper.core.exceptions import UnknownFlowError
from vbumper.core.flows import resolve_selected_flow


class TestResolveSelectedFlowIsProjectLocalOnly(unittest.TestCase):
    """`resolve_selected_flow` only ever looks at a project's own `flows:` -- `~/.vbumpconfig.yaml`
    is a template library consulted only by `vbump flow add`/`vbump init --flows`, never at bump
    time. See `vbumper.config.global_config` for that split."""

    def test_a_project_flow_is_used_as_is(self):
        config = VBumpConfig(flows={"release": FlowDefinition(name="release")})

        key, flow = resolve_selected_flow(config, flow="release", no_flow=False)

        self.assertEqual(key, "release")
        self.assertEqual(flow.name, "release")

    def test_a_same_named_global_flow_has_no_effect_when_the_key_is_local(self):
        config = VBumpConfig(flows={"release": FlowDefinition(name="local release")})
        global_flow = FlowDefinition(name="global release")

        with mock.patch(
            "vbumper.config.global_config.load_global_config",
            return_value=GlobalConfig(flows={"release": global_flow}),
        ) as mocked_load:
            _key, flow = resolve_selected_flow(config, flow="release", no_flow=False)

        self.assertEqual(flow.name, "local release")
        mocked_load.assert_not_called()

    def test_a_global_only_flow_is_not_visible_to_bump(self):
        config = VBumpConfig(flows={})

        with mock.patch(
            "vbumper.config.global_config.load_global_config",
            return_value=GlobalConfig(flows={"release": FlowDefinition(name="release")}),
        ) as mocked_load:
            with self.assertRaises(UnknownFlowError):
                resolve_selected_flow(config, flow="release", no_flow=False)

        mocked_load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
