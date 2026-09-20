"""D-224 / S0-06 cross-contract consistency checks over the S0 and S1-01 contracts.

S0-06 is the user's review of S0-01 to S0-05.  This module is the machine
part of that review: every contract validates against its own module, and
the facts the contracts share (arm names, atoms, states, feature names the
arms read, the two-seal rule, the candidate states, the all-false
authorisation bits and the still-null policy values) agree across files.
Since D-224-X the live contracts are the ``_v2`` files; the reviewed ``_v1``
bytes stay in the tree frozen, and this module pins their digests so a
silent edit of a reviewed contract is caught.  S1-01 is checked here too:
it consumes S0-02 and S0-03, and nothing else verifies that the simulator
and descriptor identities it registers are the ones those contracts assume.
Nothing here is a result and nothing here approves a contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import (  # noqa: E402
    lean_arms, lean_assets, lean_assignment, lean_intervention, lean_memory, lean_teacher,
)


CONFIG_DIR = PROJECT_ROOT / "configs" / "vsmt"
CONTRACTS = {
    "S0-01": ("lean_s0_entity_memory_v2.json", lean_memory, lean_memory.validate_entity_memory_contract),
    "S0-02": ("lean_s0_intervention_data_v2.json", lean_intervention, lean_intervention.validate_intervention_data_contract),
    "S0-03": ("lean_s0_assignment_v2.json", lean_assignment, lean_assignment.validate_assignment_contract),
    "S0-04": ("lean_s0_teacher_metrics_v2.json", lean_teacher, lean_teacher.validate_teacher_contract),
    "S0-05": ("lean_s0_arms_v2.json", lean_arms, lean_arms.validate_arms_contract),
}

#: The reviewed v1 contracts, byte-frozen (D-224-X: "追加 v2 不改已审字节").
FROZEN_V1_SHA256 = {
    "lean_s0_entity_memory_v1.json": "b9d23c33a63dffcc722584ac9d3db700bfe3bbfc054f90390e505775292d8220",
    "lean_s0_intervention_data_v1.json": "ca951ff941abc1fa920f52b292902a3904fb751aa7a39ff4328cd6be576dddd8",
    "lean_s0_assignment_v1.json": "e6d8e3808365e4bd2f99b15d7394c4b13399e311f85d41e0ade30443861db6ca",
    "lean_s0_teacher_metrics_v1.json": "700452d1ed57153f1aaf6be631c97094b6111242dca3dd2ae1ba4506a1c24c85",
    "lean_s0_arms_v1.json": "32c1d16e33ac49da389147fd08804c9e53d18fae5ece7becdd83161c8d5b27d3",
    "lean_s1_assets_capacity_v1.json": "a85c98a8d92a9e4a2fd48d3ee20fcf898decfb8afa6c74aa00ecd2578508c6af",
}

#: S1-01 is not one of the five S0 contracts and does not share their
#: all-false rule, so it is loaded separately rather than added to CONTRACTS.
S1_01_CONTRACT = "lean_s1_assets_capacity_v2.json"


def load_s1_01() -> dict[str, Any]:
    return json.loads((CONFIG_DIR / S1_01_CONTRACT).read_text(encoding="utf-8"))


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


class TestReviewedV1BytesAreFrozen(unittest.TestCase):
    def test_each_v1_contract_still_has_its_reviewed_digest(self) -> None:
        for name, expected in FROZEN_V1_SHA256.items():
            digest = hashlib.sha256((CONFIG_DIR / name).read_bytes()).hexdigest()
            self.assertEqual(digest, expected, name)

    def test_each_v2_contract_names_its_frozen_v1(self) -> None:
        for stage in CONTRACTS:
            contract = load(stage)
            supersedes = contract["supersedes_contract"]
            v1_name = Path(supersedes["path"]).name
            self.assertIn(v1_name, FROZEN_V1_SHA256, stage)
            self.assertEqual(supersedes["v1_sha256"], FROZEN_V1_SHA256[v1_name], stage)
            self.assertTrue(supersedes["v1_bytes_frozen"], stage)
            self.assertTrue(contract["schema_version"].endswith("-v2"), stage)


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

    def test_the_not_applicable_rule_matches_the_arm_vocabularies(self) -> None:
        """Review correction (LOG-225): false_retract_rate is not applicable to arms without RETRACT."""

        rule = load("S0-04")["statistics"]["metric_not_applicable_rule"]
        self.assertEqual(rule, {"false_retract_rate": "arms_whose_vocabulary_lacks_RETRACT"})
        self.assertEqual(rule, lean_teacher.METRIC_NOT_APPLICABLE_RULE)
        never = lean_arms.arms_without_atom("RETRACT")
        self.assertEqual(never, ("TAF", "LOW", "AssocOnly"))
        for arm in never:
            self.assertFalse(load("S0-05")["arms"].get(arm, load("S0-05")["ablations"].get(arm, {})).get("retracts", False), arm)
        houses = {f"h{i}": {"VSMT-lean": 0.1, "ELU-P": 0.2, "TAF": None, "LOW": None, "AssocOnly": None} for i in range(3)}
        self.assertEqual(lean_teacher.undefined_houses(houses, arms=list(houses["h0"]), not_applicable=never), [])
        self.assertEqual(len(lean_teacher.undefined_houses(houses, arms=list(houses["h0"]))), 3)

    def test_the_assoc_only_counterfactual_is_stated_consistently(self) -> None:
        self.assertEqual(lean_arms.VOCABULARY["AssocOnly"], ("BIND", "BIRTH"))
        self.assertTrue(load("S0-05")["ablations"]["AssocOnly"]["reported_in_main_table"])
        self.assertTrue(load("S0-04")["statistics"]["assoc_only_reported_in_main_table"])
        self.assertTrue(load("S0-03")["recall_rule"]["global_channel_covers_every_state"])
        self.assertTrue(load("S0-03")["recall_rule"]["identical_for_all_five_arms"])
        # D-224-X ruling X3: the counterfactual retrains, it does not reuse weights.
        self.assertTrue(load("S0-05")["ablations"]["AssocOnly"]["retrained_not_weight_reuse"])
        self.assertTrue(load("S0-05")["ablations"]["AssocOnly"]["existence_loss_term_removed"])

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


class TestD224XRulingsAgreeAcrossContracts(unittest.TestCase):
    """The v2 changes touch more than one contract; the shared facts must line up."""

    def test_lifecycle_version_count_excludes_exactly_the_bind_versions_s0_01_defines(self) -> None:
        opened_by = tuple(load("S0-01")["version_record"]["opened_by_values"])
        self.assertEqual(opened_by, lean_memory.VERSION_OPENED_BY)
        excludes = tuple(load("S0-04")["metrics"]["size_and_cost"]["lifecycle_version_excludes"])
        self.assertEqual(excludes, lean_teacher.LIFECYCLE_VERSION_EXCLUDES)
        self.assertTrue(set(excludes) < set(opened_by))
        self.assertIn("lifecycle_version_count", load("S0-04")["metrics"]["reported_fields"]["size_and_cost"])

    def test_the_duplicate_status_is_a_registered_association_status(self) -> None:
        statuses = tuple(load("S0-04")["labels"]["association_statuses"])
        self.assertEqual(statuses, lean_teacher.ASSOCIATION_STATUSES)
        self.assertIn("duplicate_of_labelled", statuses)
        self.assertEqual(load("S0-04")["labels"]["same_frame_duplicates"]["others_status"], "duplicate_of_labelled")
        # S0-01 is what makes the duplicate structural: one fragment per entity per frame.
        self.assertTrue(load("S0-01")["frame_program"]["each_entity_at_most_once"])

    def test_the_rollout_config_is_an_elu_p_grid_shape_with_the_gate_left_out(self) -> None:
        s05 = load("S0-05")
        rollout = s05["arms"]["ELU-P"]["rollout_config"]
        grid = s05["arms"]["ELU-P"]["grid"]
        self.assertEqual(set(rollout) | {lean_arms.ROLLOUT_CONFIG_GATE_PARAMETER}, set(grid))
        self.assertEqual(s05["arms"]["VSMT-lean"]["training"]["dagger_round_0_memory_source"], lean_arms.ROLLOUT_CONFIG_ARM)
        self.assertEqual(s05["ablations"]["HeuristicLabel"]["label_source_arm"], lean_arms.ROLLOUT_CONFIG_ARM)

    def test_the_split_prefix_order_puts_train_last(self) -> None:
        self.assertEqual(tuple(load("S0-02")["split_rule"]["prefix_assignment"]), ("test", "validation", "train"))
        self.assertEqual(lean_intervention.SPLIT_PREFIX_ORDER, ("test", "validation", "train"))

    def test_the_solver_and_evaluator_rewrites_are_declared_equivalent(self) -> None:
        self.assertTrue(load("S0-03")["solver"]["columns_identical_to_v1_canonicalisation"])
        self.assertTrue(load("S0-03")["solver"]["canonicalisation_never_re_solves_the_matrix"])
        self.assertTrue(load("S0-04")["metrics"]["evaluator_matching_per_component_equals_dense_solve"])

    def test_every_v2_contract_carries_the_d224x_rulings_it_implements(self) -> None:
        for stage, keys in (("S0-01", ("X6_version_opened_by", "X6_dedup_fold")), ("S0-02", ("X6_split_order",))):
            rulings = load(stage)["user_rulings"]
            self.assertEqual(rulings["decision_id"], "D-224-X", stage)
            for key in keys:
                self.assertIn(key, rulings, f"{stage}:{key}")
        self.assertEqual(load("S0-04")["user_rulings_v2"]["decision_id"], "D-224-X")
        self.assertEqual(load("S0-05")["user_rulings_v2"]["decision_id"], "D-224-X")
        self.assertEqual(load("S0-03")["review_history"][-1]["decision_id"], "D-224-X")


class TestS1ConsumesTheS0Contracts(unittest.TestCase):
    """S1-01 registers the assets S0-02 and S0-03 assume.  Nothing else checks
    that the two sides still name the same simulator, dataset and weights."""

    def setUp(self) -> None:
        self.s1 = load_s1_01()
        self.registry = {row["asset_id"]: row for row in self.s1["asset_registry"]}

    def test_s1_01_passes_its_own_validator(self) -> None:
        checked = lean_assets.validate_assets_capacity_contract(self.s1)
        self.assertEqual(checked["stage_id"], "S1-01")
        self.assertEqual(checked["decision_id"], "D-224")

    def test_s1_01_consumes_the_live_v2_contracts_not_the_frozen_v1(self) -> None:
        depends = self.s1["depends_on"]
        self.assertEqual(depends["s0_02_contract"],
                         f"configs/vsmt/{CONTRACTS['S0-02'][0]}")
        self.assertEqual(depends["s0_03_contract"],
                         f"configs/vsmt/{CONTRACTS['S0-03'][0]}")

    def test_the_simulator_s1_registers_is_the_one_s0_02_pins(self) -> None:
        source = load("S0-02")["source"]
        ai2thor = self.registry["ai2thor"]
        self.assertEqual(source["simulator"], "AI2-THOR")
        # S0-02 pins the version; S1-01 pins the tag that version resolves to.
        self.assertIn(source["simulator_version"], ai2thor["pinned_path"])
        self.assertEqual(self.registry["procthor_10k_dataset"]["role"], "house_pool")
        self.assertIn(source["dataset"].split("-")[0].lower(),
                      self.registry["procthor_10k_dataset"]["source_url"])

    def test_the_frozen_descriptors_s1_registers_match_d215(self) -> None:
        d215 = json.loads((CONFIG_DIR / "vm04_d215_frontend_freeze_v1.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(self.registry["sam2_checkpoint"]["sha256"],
                         d215["sam2"]["checkpoint_sha256"])
        self.assertEqual(self.registry["sam2_repository"]["pinned_ref"],
                         d215["sam2"]["repository_commit"])

    def test_both_descriptor_sizes_s0_03_may_choose_between_are_registered(self) -> None:
        # S0-03 registers a ReID head over the frozen descriptor and leaves the
        # choice to S1-05, so both candidates must exist as registered assets.
        reid = load("S0-03")["reid_adapter_head"]
        self.assertEqual(reid["input"], "frozen_dinov2_descriptor")
        self.assertEqual(reid["selection_stage"], "S1-05")
        for asset_id in ("dinov2_vit_s14_checkpoint", "dinov2_vit_b14_checkpoint"):
            row = self.registry[asset_id]
            self.assertIsNotNone(row["sha256"], asset_id)
            self.assertIsNotNone(row["bytes"], asset_id)

    def test_generation_is_closed_on_both_sides(self) -> None:
        # S1-01 may not generate episodes, and S0-02 has not been authorised
        # to either; if one side opened, the other would be stale.
        self.assertIn("route_or_episode_generation", self.s1["must_remain_false"])
        self.assertIs(load("S0-02")["authorization"]["episode_generation"], False)

    def test_the_occupancy_measurement_is_owned_by_the_stage_that_can_run(self) -> None:
        self.assertEqual(self.s1["worker_rule"]["measurement_stage"], "S1-02a")
        self.assertNotIn("single_worker_occupancy_measurement", self.s1["authorization"])

    def test_s1_01_keeps_no_open_policy_value_behind(self) -> None:
        self.assertEqual(self.s1["policy_values_without_defaults"], [])
        self.assertEqual(self.s1["worker_rule"]["headroom_fraction"], 0.2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
