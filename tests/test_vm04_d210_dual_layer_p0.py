import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cpmt.hashing import canonical_json
from vsmt.d210_place_memory import (
    ADAPTER_PACKET_SCHEMA,
    D210Error,
    aggregate_p0_metrics,
    build_continuous_pose_belief,
    build_p0_manifests,
    build_place_adapter_input,
    build_public_keyframe,
    build_route_plan,
    build_transition_action_summary,
    classify_private_loop_pair,
    evaluate_place_episode,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d210_dual_layer_p0_v1.json"


def sha(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class D210DualLayerP0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = validate_contract(json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")))

    def route(self, slot, count=8):
        pattern = ["MoveAhead", "RotateLeft", "MoveRight", "RotateRight"]
        return build_route_plan(
            slot=slot,
            action_names=[pattern[index % len(pattern)] for index in range(count)],
            keyframe_observation_indices=[0, count // 2, count],
            contract=self.contract,
        )

    def keyframe(self, index):
        return build_public_keyframe(
            observation_index=index, rgb_sha256="1" * 64,
            depth_sha256="2" * 64, visual_geometry_sha256="3" * 64,
            visible_entity_refs=["entity:chair"])

    def belief(self, index):
        return build_continuous_pose_belief(
            observation_index=index,
            mean_x_y_z_yaw=[1.0, 0.0, 2.0, 90.0],
            covariance_diagonal=[0.02, 0.01, 0.02, 2.0],
            source_id="causal-visual-inertial-belief-v1")

    def test_contract_freezes_approved_scope_without_opening_generation(self):
        self.assertEqual(0.25, self.contract["movement"]["move_magnitude_m"])
        self.assertEqual(90.0, self.contract["movement"]["body_rotation_degrees"])
        self.assertIsNone(
            self.contract["movement"]["scientific_maximum_route_actions"])
        self.assertEqual(128,
                         self.contract["movement"]["mechanical_route_action_guard"])
        self.assertFalse(any(self.contract["authorization"].values()))
        self.assertFalse(self.contract["scope"]
                         ["place_identity_is_a_metric_grid_cell"])
        self.assertEqual(["NOOP", "BIND", "BIRTH", "MERGE"],
                         self.contract["memory_layers"]
                         ["versioned_topological_place_graph"]
                         ["place_operations"])
        self.assertEqual(["CREATE", "RELINK"], self.contract["memory_layers"]
                         ["versioned_topological_place_graph"]
                         ["relation_operations"])

    def test_route_has_no_24_step_limit_and_hint_is_not_a_cap(self):
        # P01's planning hint ends at 32; 56 is still legal under D-210.
        plan = self.route(0, 56)
        self.assertEqual(56, plan["planned_action_count"])
        self.assertEqual(57, plan["observation_count"])
        self.assertEqual({"action": "MoveAhead", "moveMagnitude": 0.25},
                         plan["actions"][0]["request"])
        self.assertEqual({"action": "RotateLeft", "degrees": 90.0},
                         plan["actions"][1]["request"])
        self.route(0, 128)
        with self.assertRaisesRegex(D210Error, "128-action mechanical guard"):
            self.route(0, 129)

    def test_twelve_slot_manifests_keep_house_identity_private(self):
        routes = [self.route(slot) for slot in range(12)]
        houses = [
            {"house_slot": 0, "source_house_id": "house-A",
             "source_record_sha256": "a" * 64},
            {"house_slot": 1, "source_house_id": "house-B",
             "source_record_sha256": "b" * 64},
        ]
        public, private = build_p0_manifests(
            source_houses=houses, route_plans=routes, contract=self.contract)
        self.assertEqual(12, public["episode_count"])
        self.assertEqual(12, private["episode_count"])
        self.assertTrue(public["source_house_ids_exported"] is False)
        self.assertTrue(all("source_house_id" not in row
                            for row in public["episodes"]))
        self.assertIn("house-A", canonical_json(private))
        self.assertEqual(
            ["P01", "P02", "P03", "P04", "P01", "P02", "P03", "P04",
             "P05", "P07", "P06", "P08"],
            [row["scenario_id"] for row in public["episodes"]],
        )

    def test_edge_summary_compresses_actions_without_replaying_the_list(self):
        actions = [
            {"action": "MoveAhead"}, {"action": "RotateLeft"},
            {"action": "RotateLeft"}, {"action": "MoveRight"},
        ]
        summary = build_transition_action_summary(
            actions=actions, start_observation_index=2,
            end_observation_index=6,
            estimated_delta_mean_x_z_yaw=[0.25, 0.25, 180.0],
            estimated_delta_covariance_diagonal=[0.02, 0.02, 3.0],
            confidence=0.8, raw_action_span_sha256="c" * 64,
            contract=self.contract,
        )
        self.assertNotIn("actions", summary)
        self.assertEqual(4, summary["step_count"])
        self.assertEqual(0.5, summary["nominal_translation_m_total"])
        self.assertEqual([{"direction": "left", "quarter_turns": 2}],
                         summary["ordered_quarter_turns"])

    def test_private_loop_gate_uses_continuous_regions_not_grid_cells(self):
        self.assertEqual("positive", classify_private_loop_pair(
            position_error_m=0.35, same_reachable_component=True,
            pre_registered_distinct_branch_or_room=False,
            contract=self.contract))
        self.assertEqual("negative", classify_private_loop_pair(
            position_error_m=1.5, same_reachable_component=True,
            pre_registered_distinct_branch_or_room=False,
            contract=self.contract))
        self.assertEqual("negative", classify_private_loop_pair(
            position_error_m=0.2, same_reachable_component=False,
            pre_registered_distinct_branch_or_room=True,
            contract=self.contract))
        self.assertEqual("unlabelled", classify_private_loop_pair(
            position_error_m=0.8, same_reachable_component=True,
            pre_registered_distinct_branch_or_room=False,
            contract=self.contract))

    def test_adapter_exposes_keyframe_belief_and_summary_not_grid_truth(self):
        summary = build_transition_action_summary(
            actions=[{"action": "MoveAhead"}], start_observation_index=0,
            end_observation_index=1,
            estimated_delta_mean_x_z_yaw=[0.0, 0.24, 0.0],
            estimated_delta_covariance_diagonal=[0.01, 0.01, 1.0],
            confidence=0.9, raw_action_span_sha256="d" * 64,
            contract=self.contract,
        )
        prior = {"graph_version": 3, "places": ["p0"], "relations": []}
        packet = {
            "schema_version": ADAPTER_PACKET_SCHEMA,
            "decision_time_s": 1.0,
            "current_keyframe": self.keyframe(1),
            "pose_belief": self.belief(1),
            "incoming_transition_action_summary": summary,
            "region_observations": [{"region_ref": "region:1"}],
            "relation_observations": [],
            "prior_memory_ref": {"graph_version": 3,
                                 "graph_sha256": sha(prior)},
            "public_constants": {"planner_grid_size_m": 0.5,
                                 "planner_grid_role":
                                     "candidate_retrieval_only"},
        }
        adapter = build_place_adapter_input(
            packet, prior_memory=prior, contract=self.contract)
        self.assertIn("current_keyframe", adapter)
        self.assertIn("continuous_pose_belief", adapter)
        self.assertIn("incoming_transition_action_summary", adapter)
        self.assertNotIn("actions", canonical_json(adapter))
        self.assertNotIn("place_id", adapter["public_constants"])
        poisoned = json.loads(json.dumps(packet))
        poisoned["region_observations"][0]["world_pose"] = [1, 2, 3]
        with self.assertRaisesRegex(D210Error, "forbidden field"):
            build_place_adapter_input(
                poisoned, prior_memory=prior, contract=self.contract)

    def metric(self, scenario_id):
        reference = {
            "candidate_catalog_sha256": "e" * 64,
            "place_membership": [
                {"observation_id": "a", "place_id": "truth:X"},
                {"observation_id": "b", "place_id": "truth:X"},
                {"observation_id": "c", "place_id": "truth:Y"},
            ],
            "loop_pairs": [
                {"pair_id": "ab", "is_same_place": True},
                {"pair_id": "ac", "is_same_place": False},
            ],
            "edge_endpoint_pairs": [["adjacent_to", "truth:X", "truth:Y"]],
            "entity_place_attachments": [["chair", "truth:Y"]],
        }
        prediction = {
            "candidate_catalog_sha256": "e" * 64,
            "place_membership": [
                {"observation_id": "a", "place_id": "pred:1"},
                {"observation_id": "b", "place_id": "pred:1"},
                {"observation_id": "c", "place_id": "pred:2"},
            ],
            "loop_pair_predictions": [
                {"pair_id": "ab", "is_same_place": True},
                {"pair_id": "ac", "is_same_place": False},
            ],
            "edge_endpoint_pairs": [["adjacent_to", "pred:1", "pred:2"]],
            "entity_place_attachments": [["chair", "pred:2"]],
            "contamination_series": [1.0, 0.5, 0.0],
            "error_decomposition": {
                "candidate_miss": 0, "teacher_error": 0,
                "amortization_error": 0, "illegal_transaction": 0,
                "collateral_change": 0,
            },
        }
        return evaluate_place_episode(
            scenario_id=scenario_id, prediction=prediction,
            reference=reference, contract=self.contract)

    def test_metrics_are_label_invariant_and_keep_oracles_out(self):
        metric = self.metric("P03")
        self.assertEqual(1.0, metric["place_pairwise_f1"])
        self.assertEqual(0.0, metric["duplicate_place_rate"])
        self.assertEqual(0.0, metric["false_merge_rate"])
        self.assertEqual(0.5, metric["contamination_auc"])
        self.assertFalse(metric["exact_action_or_true_pose_oracle_included"])

    def test_private_metrics_are_bound_to_the_sealed_candidate_catalog(self):
        reference = {
            "candidate_catalog_sha256": "e" * 64,
            "place_membership": [{"observation_id": "a", "place_id": "t"}],
            "loop_pairs": [], "edge_endpoint_pairs": [],
            "entity_place_attachments": [],
        }
        prediction = {
            "candidate_catalog_sha256": "f" * 64,
            "place_membership": [{"observation_id": "a", "place_id": "p"}],
            "loop_pair_predictions": [], "edge_endpoint_pairs": [],
            "entity_place_attachments": [], "contamination_series": [0.0],
            "error_decomposition": {
                "candidate_miss": 0, "teacher_error": 0,
                "amortization_error": 0, "illegal_transaction": 0,
                "collateral_change": 0,
            },
        }
        with self.assertRaisesRegex(D210Error, "sealed candidate catalog"):
            evaluate_place_episode(
                scenario_id="P03", prediction=prediction, reference=reference,
                contract=self.contract)

    def test_headline_aggregation_excludes_control_scenarios(self):
        result = aggregate_p0_metrics(
            [self.metric("P01"), self.metric("P03")], contract=self.contract)
        self.assertEqual(2, result["episode_count"])
        self.assertEqual(1, result["headline_episode_count"])
        self.assertEqual(["P01", "P02"],
                         result["control_scenarios_excluded_from_headline"])
        self.assertTrue(result["diagnostic_oracles_excluded"])
        self.assertRegex(result["aggregate_sha256"], r"^[0-9a-f]{64}$")

    def test_stage_check_reports_closed_gates(self):
        command = [sys.executable, str(
            ROOT / "ops/vsmt/vm04_d210_p0_stage.py"), "check"]
        completed = subprocess.run(
            command, cwd=ROOT, check=True, capture_output=True, text=True)
        report = json.loads(completed.stdout)
        self.assertEqual(12, report["slot_count"])
        self.assertFalse(report["execution_authorized"])
        self.assertFalse(report["place_identity_is_a_metric_grid_cell"])

    def test_seal_command_rejects_before_touching_external_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [
                sys.executable,
                str(ROOT / "ops/vsmt/vm04_d210_p0_stage.py"),
                "seal-batch", "--source-houses", str(root / "missing-houses.json"),
                "--routes", str(root / "missing-routes.json"),
                "--output-root", str(root / "output"),
            ]
            completed = subprocess.run(
                command, cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("not frozen_executable", completed.stderr)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
