from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tests.test_vm04_multiview_worker import CONTRACT, _plan  # noqa: E402
from vsmt.vm04_observation_runner import public_route_projection  # noqa: E402
from vsmt.vm04_public_context import (  # noqa: E402
    REGISTERED_ACTIONS,
    make_public_frame_contexts,
    validate_public_frame_context_bundle,
)


def vectors():
    actions = sorted(REGISTERED_ACTIONS)
    return {
        action: [1.0 if index == column else 0.0 for column in range(len(actions))]
        for index, action in enumerate(actions)
    }


def build(**updates):
    route = public_route_projection(_plan(), contract=CONTRACT)
    values = {
        "decision_times_s": [float(index) for index in range(6)],
        "decision_time_rule_id": "fixture.observation-index-seconds.v1",
        "action_command_vectors": vectors(),
        "action_encoding_id": "fixture.one-hot-actions.v1",
        "robot_states": [
            {"feature_names": [], "values": []} for _ in range(6)
        ],
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "l1.oracle-mask.public-depth.v1",
        },
    }
    values.update(updates)
    return make_public_frame_contexts(route, **values)


class Vm04PublicContextTests(unittest.TestCase):
    def test_contexts_contain_only_completed_action_prefix(self):
        result = build()
        self.assertEqual(validate_public_frame_context_bundle(result), result)
        contexts = result["contexts"]
        self.assertEqual(len(contexts), 6)
        self.assertEqual(contexts[0]["past_actions"], [])
        self.assertEqual(len(contexts[3]["past_actions"]), 3)
        self.assertEqual(
            [row["end_time_s"] for row in contexts[3]["past_actions"]],
            [1.0, 2.0, 3.0],
        )
        self.assertEqual(result["manifest"]["observation_count"], 6)
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn('"program"', encoded)
        self.assertNotIn("target_instance", encoded)

    def test_time_or_encoding_is_never_defaulted(self):
        parameters = inspect.signature(make_public_frame_contexts).parameters
        for name in (
            "decision_times_s", "decision_time_rule_id",
            "action_command_vectors", "action_encoding_id",
        ):
            self.assertIs(parameters[name].default, inspect.Parameter.empty)
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            build(decision_times_s=[0.0, 1.0, 1.0, 3.0, 4.0, 5.0])
        duplicate = vectors()
        duplicate["MoveAhead"] = duplicate["MoveBack"]
        with self.assertRaisesRegex(ValueError, "distinct command vectors"):
            build(action_command_vectors=duplicate)

    def test_private_or_program_field_in_public_route_is_rejected(self):
        route = public_route_projection(_plan(), contract=CONTRACT)
        route["program"] = "RELINK"
        with self.assertRaisesRegex(ValueError, "unexpected fields"):
            make_public_frame_contexts(
                route,
                decision_times_s=[float(index) for index in range(6)],
                decision_time_rule_id="fixture.times.v1",
                action_command_vectors=vectors(),
                action_encoding_id="fixture.actions.v1",
                robot_states=[
                    {"feature_names": [], "values": []} for _ in range(6)
                ],
                public_constants={
                    "coordinate_frame": "map", "depth_unit": "metre",
                    "descriptor_model_id": "dinov2.vits14",
                    "proposal_model_id": "l1.oracle-mask.public-depth.v1",
                },
            )

    def test_public_route_digest_and_full_action_table_are_bound(self):
        route = public_route_projection(_plan(), contract=CONTRACT)
        tampered = deepcopy(route)
        tampered["registered_actions"][0]["action"] = "LookUp"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            make_public_frame_contexts(
                tampered,
                decision_times_s=[float(index) for index in range(6)],
                decision_time_rule_id="fixture.times.v1",
                action_command_vectors=vectors(),
                action_encoding_id="fixture.actions.v1",
                robot_states=[
                    {"feature_names": [], "values": []} for _ in range(6)
                ],
                public_constants={
                    "coordinate_frame": "map", "depth_unit": "metre",
                    "descriptor_model_id": "dinov2.vits14",
                    "proposal_model_id": "l1.oracle-mask.public-depth.v1",
                },
            )
        incomplete = vectors()
        incomplete.pop("LookDown")
        with self.assertRaisesRegex(ValueError, "cover every registered action"):
            build(action_command_vectors=incomplete)

    def test_context_or_manifest_tampering_is_rejected(self):
        context_changed = deepcopy(build())
        context_changed["contexts"][1]["decision_time_s"] = 1.5
        with self.assertRaisesRegex(ValueError, "decision-time digest"):
            validate_public_frame_context_bundle(context_changed)
        manifest_changed = deepcopy(build())
        manifest_changed["manifest"]["action_encoding_id"] = "changed.v2"
        with self.assertRaisesRegex(ValueError, "manifest digest"):
            validate_public_frame_context_bundle(manifest_changed)


if __name__ == "__main__":
    unittest.main()
