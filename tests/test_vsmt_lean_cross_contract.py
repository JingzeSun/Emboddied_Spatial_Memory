"""D-224 / S0-06 cross-contract consistency checks over the five S0 contracts.

S0-06 is the user's review of S0-01 to S0-05.  This module is the machine
part of that review: every contract validates against its own module, and
the facts the contracts share (arm names, atoms, states, feature names the
arms read, the two-seal rule, the candidate states, the all-false
authorisation bits and the still-null policy values) agree across files.
Nothing here is a result and nothing here approves a contract.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_arms, lean_assignment, lean_intervention, lean_memory, lean_teacher  # noqa: E402


CONFIG_DIR = PROJECT_ROOT / "configs" / "vsmt"
CONTRACTS = {
    "S0-01": ("lean_s0_entity_memory_v1.json", lean_memory, lean_memory.validate_entity_memory_contract),
    "S0-02": ("lean_s0_intervention_data_v1.json", lean_intervention, lean_intervention.validate_intervention_data_contract),
    "S0-03": ("lean_s0_assignment_v1.json", lean_assignment, lean_assignment.validate_assignment_contract),
    "S0-04": ("lean_s0_teacher_metrics_v1.json", lean_teacher, lean_teacher.validate_teacher_contract),
    "S0-05": ("lean_s0_arms_v1.json", lean_arms, lean_arms.validate_arms_contract),
}


def load(stage: str) -> dict[str, Any]:
    return json.loads((CONFIG_DIR / CONTRACTS[stage][0]).read_text(encoding="utf-8"))


def lookup(contract: dict[str, Any], path: str) -> Any:
    """Follow a dotted path; a bare key (S0-01 style) is searched for anywhere in the tree."""

    if "." in path:
        node: Any = contract
        for part in path.split("."):
            node = node[part]
        return node
    hits: list[Any] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == path:
                    hits.append(item)
                walk(item)

    walk(contract)
    if len(hits) != 1:
        raise KeyError(f"{path}: found {len(hits)} times")
    return hits[0]


class TestEveryContractValidates(unittest.TestCase):
    def test_each_contract_passes_its_own_validator_and_names_its_stage(self) -> None:
        for stage, (_, module, validator) in CONTRACTS.items():
            contract = load(stage)
            validator(contract)
            self.assertEqual(contract["decision_id"], "D-224", stage)
            self.assertEqual(contract["stage_id"], stage, stage)
            self.assertEqual(contract["schema_version"], module.CONTRACT_SCHEMA_VERSION, stage)

    def test_every_authorisation_bit_is_false_everywhere(self) -> None:
        for stage in CONTRACTS:
            bits = load(stage)["authorization"]
            self.assertTrue(bits, stage)
            self.assertTrue(all(value is False for value in bits.values()), stage)

    def test_every_registered_policy_value_is_still_null(self) -> None:
        for stage in CONTRACTS:
            contract = load(stage)
            paths = contract["policy_values_without_defaults"]
            self.assertTrue(paths, stage)
            for path in paths:
                self.assertIsNone(lookup(contract, path), f"{stage}:{path}")

    def test_pure_core_paths_exist(self) -> None:
        for stage in CONTRACTS:
            relative = load(stage)["pure_core_relative_path"]
            self.assertTrue((PROJECT_ROOT / relative).is_file(), f"{stage}:{relative}")


class TestSharedFacts(unittest.TestCase):
    def test_atoms_states_and_birth_prefix_agree_across_modules(self) -> None:
        self.assertEqual(lean_memory.ATOMS, lean_arms.ATOMS)
        self.assertEqual(lean_memory.ENTITY_STATES, lean_teacher.ENTITY_STATES)
        self.assertEqual(lean_memory.ENTITY_STATES, lean_arms.ENTITY_STATES)
        self.assertEqual(lean_assignment.BIRTH_COLUMN_PREFIX, lean_teacher.BIRTH_COLUMN_PREFIX)
        self.assertEqual(lean_assignment.BIRTH_COLUMN_PREFIX, lean_arms.BIRTH_COLUMN_PREFIX)
        self.assertEqual(tuple(load("S0-01")["entity_states"]), lean_memory.ENTITY_STATES)

    def test_arm_names_agree_between_the_evaluator_and_the_arms_contract(self) -> None:
        self.assertEqual(lean_teacher.METHOD_ARM, lean_arms.METHOD_ARM)
        self.assertEqual(lean_teacher.CONTROL_ARMS, lean_arms.CONTROL_ARMS)
        self.assertEqual(lean_teacher.ABLATION_ARMS, lean_arms.ABLATION_ARMS)
        self.assertEqual(lean_teacher.APPENDIX_ARM, lean_arms.APPENDIX_ARM)
        self.assertEqual(lean_teacher.OPTIONAL_ARM, lean_arms.OPTIONAL_ARM)
        self.assertEqual(lean_teacher.DECOMPOSITION, lean_arms.DECOMPOSITION)
        statistics = load("S0-04")["statistics"]
        arms = load("S0-05")["arms"]
        self.assertEqual(statistics["method_arm"], arms["method"])
        self.assertEqual(list(statistics["controls"]), list(arms["controls"]))
        self.assertEqual(list(statistics["ablations"]), list(load("S0-05")["ablations"]["names"]))
        self.assertEqual(statistics["appendix_arm"], load("S0-05")["appendix_arm"]["name"])
        self.assertEqual(statistics["optional_arm"], load("S0-05")["optional_arm"]["name"])
        self.assertIn("AssocOnly", arms["main_table"])

    def test_the_arms_read_only_features_the_assignment_contract_freezes(self) -> None:
        s03 = load("S0-03")
        association = set(s03["association_feature_order"])
        existence = set(s03["existence_feature_order"])
        for name in ("cosine_to_descriptor_mean", "centroid_distance_m", "state_is_retracted"):
            self.assertIn(name, association, name)
        for name in ("should_be_visible_ratio", "free_space_coverage_ratio", "state_is_retracted"):
            self.assertIn(name, existence, name)
        self.assertEqual(tuple(s03["association_feature_order"]), lean_assignment.ASSOCIATION_FEATURES)
        self.assertEqual(tuple(s03["existence_feature_order"]), lean_assignment.EXISTENCE_FEATURES)

    def test_the_two_seal_rule_is_stated_on_both_sides(self) -> None:
        self.assertEqual(load("S0-03")["seal"]["teacher_may_open_private_only_after"], "both_stage_seals_exist")
        self.assertTrue(load("S0-03")["seal"]["two_stage"])
        self.assertTrue(load("S0-04")["private_gate"]["requires_both_stage_seals"])
        self.assertTrue(load("S0-03")["seal"]["teacher_assignment_must_not_feed_existence_features"])
        self.assertTrue(load("S0-04")["private_gate"]["teacher_uses_current_policy_assignment_not_its_own"])

    def test_existence_candidates_are_the_same_states_for_the_teacher_and_the_arms(self) -> None:
        self.assertEqual(tuple(load("S0-04")["labels"]["existence"]["candidate_states"]), ("active", "dormant"))
        self.assertEqual(lean_teacher.EXISTENCE_CANDIDATE_STATES, ("active", "dormant"))
        order = list(lean_assignment.EXISTENCE_FEATURES)
        rows = []
        for state in lean_memory.ENTITY_STATES:
            features = [0.0] * len(order)
            features[order.index("should_be_visible_ratio")] = 1.0
            features[order.index(f"state_is_{state}")] = 1.0
            rows.append({"entity_id": f"entity:{state}", "features": features})
        kept = lean_arms.eligible_existence_rows(rows, order, visible_min_ratio=0.5)
        self.assertEqual([row["entity_id"] for row in kept["eligible"]], ["entity:active", "entity:dormant"])
        self.assertEqual(kept["excluded_retracted"], ["entity:retracted"])
        self.assertTrue(load("S0-05")["shared"]["existence_candidates_are_active_or_dormant_and_should_be_visible"])

    def test_the_assoc_only_counterfactual_is_stated_consistently(self) -> None:
        self.assertEqual(lean_arms.VOCABULARY["AssocOnly"], ("BIND", "BIRTH"))
        self.assertTrue(load("S0-05")["ablations"]["AssocOnly"]["reported_in_main_table"])
        self.assertTrue(load("S0-04")["statistics"]["assoc_only_reported_in_main_table"])
        self.assertTrue(load("S0-03")["recall_rule"]["global_channel_covers_every_state"])
        self.assertTrue(load("S0-03")["recall_rule"]["identical_for_all_five_arms"])

    def test_the_selection_metric_is_a_reported_metric_and_not_a_main_gate_metric(self) -> None:
        metric = load("S0-05")["budget"]["selection_metric"]
        fields = load("S0-04")["metrics"]["reported_fields"]
        self.assertIn(metric, fields["node_prf1"])
        self.assertNotIn(metric, {name for name, _direction in lean_teacher.MAIN_GATE})

    def test_the_shared_dormancy_and_visibility_values_are_registered_once_each(self) -> None:
        self.assertIsNone(load("S0-01")["shared_dormancy"]["dormancy_missed_opportunity_limit"])
        self.assertIsNone(load("S0-05")["shared"]["should_be_visible_min_ratio"])
        for stage in ("S0-02", "S0-03", "S0-04"):
            text = json.dumps(load(stage))
            self.assertNotIn("should_be_visible_min_ratio", text, stage)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
