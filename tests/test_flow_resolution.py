import unittest

import pydantic

from vbumper.config.flow import FlowConfig, FlowDefinition
from vbumper.config.root import resolve_all_flows
from vbumper.core.exceptions import ConfigurationError


class TestResolveAllFlowsWithoutRecall(unittest.TestCase):
    def test_a_full_local_definition_is_used_as_is(self):
        entry = FlowConfig(name="release", pre_commands=["echo hi"])
        resolved = resolve_all_flows({"release": entry}, global_flows={})

        self.assertEqual(resolved["release"].name, "release")
        self.assertEqual(resolved["release"].pre_commands, ["echo hi"])

    def test_result_is_a_flow_definition_not_a_flow_config(self):
        entry = FlowConfig(name="release")
        resolved = resolve_all_flows({"release": entry}, global_flows={})

        self.assertIsInstance(resolved["release"], FlowDefinition)
        self.assertNotIsInstance(resolved["release"], FlowConfig)


class TestResolveAllFlowsWithRecall(unittest.TestCase):
    def setUp(self):
        self.global_flow = FlowDefinition(
            name="global release",
            require_on_branch="{DEVELOP_BRANCH}",
            variables={"DEVELOP_BRANCH": "develop", "RELEASE_BRANCH": "main"},
            pre_commands=["git checkout {RELEASE_BRANCH}"],
            post_commands=["git tag {VERSION_TAG}"],
        )

    def test_recall_adopts_the_global_definition_wholesale(self):
        entry = FlowConfig(recall="release")
        resolved = resolve_all_flows(
            {"my-release": entry}, global_flows={"release": self.global_flow}
        )

        flow = resolved["my-release"]
        self.assertEqual(flow.name, "global release")
        self.assertEqual(flow.pre_commands, ["git checkout {RELEASE_BRANCH}"])
        self.assertEqual(flow.post_commands, ["git tag {VERSION_TAG}"])

    def test_recall_merges_variables_key_by_key_onto_the_global_definition(self):
        entry = FlowConfig(recall="release", variables={"RELEASE_BRANCH": "master"})
        resolved = resolve_all_flows(
            {"my-release": entry}, global_flows={"release": self.global_flow}
        )

        self.assertEqual(
            resolved["my-release"].variables,
            {"DEVELOP_BRANCH": "develop", "RELEASE_BRANCH": "master"},
        )
        # The precondition tracks the (unchanged) DEVELOP_BRANCH variable, not a stale copy.
        self.assertEqual(resolved["my-release"].require_on_branch, "{DEVELOP_BRANCH}")

    def test_unknown_recall_target_raises_configuration_error(self):
        entry = FlowConfig(recall="does-not-exist")
        with self.assertRaises(ConfigurationError):
            resolve_all_flows({"my-release": entry}, global_flows={"release": self.global_flow})

    def test_recalled_flow_is_addressed_by_the_project_local_key(self):
        entry = FlowConfig(recall="release")
        resolved = resolve_all_flows(
            {"my-release": entry}, global_flows={"release": self.global_flow}
        )

        self.assertIn("my-release", resolved)
        self.assertNotIn("release", resolved)


class TestFlowConfigRecallValidation(unittest.TestCase):
    def test_recall_alone_is_valid(self):
        FlowConfig(recall="release", variables={"RELEASE_BRANCH": "master"})  # no raise

    def test_recall_with_pre_commands_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            FlowConfig(recall="release", pre_commands=["echo hi"])

    def test_recall_with_post_commands_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            FlowConfig(recall="release", post_commands=["echo hi"])

    def test_recall_with_name_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            FlowConfig(recall="release", name="renamed")

    def test_recall_with_require_on_branch_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            FlowConfig(recall="release", require_on_branch="main")

    def test_flow_definition_has_no_recall_field(self):
        with self.assertRaises(pydantic.ValidationError):
            FlowDefinition.model_validate({"recall": "release"})


if __name__ == "__main__":
    unittest.main()
