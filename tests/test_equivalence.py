from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.equivalence import (  # noqa: E402
    validate_canonical_memory_state_equality,
    validate_identity_correspondence,
)
from cpmt.errors import ContractError  # noqa: E402
from cpmt.executor import execute_transaction  # noqa: E402
from cpmt.hashing import seal_graph  # noqa: E402
from cpmt.pending import (  # noqa: E402
    create_pending_store,
    decide_commit,
    quarantine_evidence,
)


FIXTURE_ROOT = (
    PROJECT_ROOT
    / "experiments"
    / "counterfactual_transaction_learning"
    / "fixtures"
    / "draft"
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_world(case_family: str) -> dict:
    return seal_graph(
        load_json(FIXTURE_ROOT / case_family / "world.json")
    )


def load_program(case_family: str, filename: str) -> dict:
    return load_json(
        FIXTURE_ROOT
        / case_family
        / "transactions"
        / filename
    )


def c02_policy(**updates: object) -> dict:
    policy = {
        "schema_version": "cpmt-0.2",
        "policy_id": "policy:C02:local-id",
        "base_graph_version": "v0",
        "fixed_identity_ids": ["mug-1", "wall-protected"],
        "exchangeable_identity_sets": [],
        "externally_anchored_new_ids": [],
        "raw_latent_exact_match": False,
        "comparison_mode": "canonical_memory_state",
        "future_projection_defines_equivalence": False,
    }
    policy.update(updates)
    return policy


def c02_post_worlds() -> tuple[dict, dict, dict]:
    base = load_world("C02")
    left = execute_transaction(
        base,
        load_program("C02", "birth.json"),
    )
    renamed = load_program("C02", "birth.json")
    renamed["transaction_id"] = "tx-C02-birth-renamed"
    for operation in renamed["operations"]:
        arguments = operation["arguments"]
        if arguments.get("node_id") == "cup-2":
            arguments["node_id"] = "temporary-object-8472"
        node = arguments.get("node")
        if node:
            node["node_id"] = "temporary-object-8472"
            node["node_version_id"] = "temporary-object-8472@v0"
            node["provenance"] = ["tx-C02-birth-renamed"]
    right = execute_transaction(base, renamed)
    return base, left, right


class IdentityCorrespondenceTests(unittest.TestCase):
    def test_local_new_identity_can_be_alpha_renamed(self) -> None:
        base, left, right = c02_post_worlds()
        validate_identity_correspondence(
            base,
            left,
            right,
            identity_mapping={
                "mug-1": "mug-1",
                "wall-protected": "wall-protected",
                "cup-2": "temporary-object-8472",
            },
            policy=c02_policy(),
        )

    def test_anchored_old_identity_cannot_be_swapped(self) -> None:
        base, left, right = c02_post_worlds()
        with self.assertRaises(ContractError):
            validate_identity_correspondence(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "wall-protected",
                    "wall-protected": "mug-1",
                    "cup-2": "temporary-object-8472",
                },
                policy=c02_policy(),
            )

    def test_new_identity_cannot_map_to_old_identity(self) -> None:
        base, left, right = c02_post_worlds()
        with self.assertRaises(ContractError):
            validate_identity_correspondence(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "temporary-object-8472",
                    "cup-2": "wall-protected",
                },
                policy=c02_policy(
                    fixed_identity_ids=["mug-1"],
                ),
            )

    def test_mapping_must_cover_a_strict_bijection(self) -> None:
        base, left, right = c02_post_worlds()
        with self.assertRaises(ContractError):
            validate_identity_correspondence(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                },
                policy=c02_policy(),
            )

    def test_declared_exchangeable_ids_may_permute_at_identity_layer(
        self,
    ) -> None:
        base = load_world("C05")
        mapping = {
            identity_id: identity_id
            for identity_id in {
                node["node_id"] for node in base["nodes"]
            }
        }
        mapping["chair-a"] = "chair-b"
        mapping["chair-b"] = "chair-a"
        policy = {
            "schema_version": "cpmt-0.2",
            "policy_id": "policy:C05:declared-symmetry",
            "base_graph_version": "v0",
            "fixed_identity_ids": ["wall-protected"],
            "exchangeable_identity_sets": [["chair-a", "chair-b"]],
            "externally_anchored_new_ids": [],
            "raw_latent_exact_match": False,
            "comparison_mode": "canonical_memory_state",
            "future_projection_defines_equivalence": False,
        }
        validate_identity_correspondence(
            base,
            deepcopy(base),
            deepcopy(base),
            identity_mapping=mapping,
            policy=policy,
        )

    def test_external_new_identity_anchor_must_keep_its_id(self) -> None:
        base, left, right = c02_post_worlds()
        with self.assertRaises(ContractError):
            validate_identity_correspondence(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                    "cup-2": "temporary-object-8472",
                },
                policy=c02_policy(
                    externally_anchored_new_ids=["cup-2"],
                ),
            )


def c09_pending_store() -> dict:
    decision = decide_commit(
        {"bind": 0.52, "birth": 0.48},
        decision_id="decision:C09:t5",
        at=5,
        commit_probability=0.7,
        margin_threshold=0.15,
    )
    return quarantine_evidence(
        create_pending_store("pending-C09"),
        pending_id="trace-chair-uncertain",
        decision=decision,
        evidence_event={
            "evidence_id": "obs:C09:t5:ambiguous-chair",
            "time_index": 5,
            "viewpoint_id": "view:C09:t5",
            "reliability": 0.2,
            "visibility": "unknown",
            "pose_valid": False,
            "depth_valid": False,
        },
        latent_ref="latent:C09:coarse-chair-like",
        spatial_ref="space:C09:left-or-right",
        semantic_hints=["chair-like", "furniture"],
        provenance_ref="fixture:C09:quarantine",
    )


class CanonicalMemoryStateEqualityTests(unittest.TestCase):
    def test_alpha_renamed_audit_different_results_are_equal(self) -> None:
        base, left, right = c02_post_worlds()
        validate_canonical_memory_state_equality(
            base,
            left,
            right,
            identity_mapping={
                "mug-1": "mug-1",
                "wall-protected": "wall-protected",
                "cup-2": "temporary-object-8472",
            },
            policy=c02_policy(),
        )

    def test_serialization_order_does_not_change_state(self) -> None:
        base, left, right = c02_post_worlds()
        right["nodes"].reverse()
        right = seal_graph(right)
        validate_canonical_memory_state_equality(
            base,
            left,
            right,
            identity_mapping={
                "mug-1": "mug-1",
                "wall-protected": "wall-protected",
                "cup-2": "temporary-object-8472",
            },
            policy=c02_policy(),
        )

    def test_lifecycle_difference_is_not_equal(self) -> None:
        base, left, right = c02_post_worlds()
        right_new = next(
            node
            for node in right["nodes"]
            if node["node_id"] == "temporary-object-8472"
        )
        right_new["lifecycle"] = "confirmed"
        right = seal_graph(right)
        with self.assertRaises(ContractError):
            validate_canonical_memory_state_equality(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                    "cup-2": "temporary-object-8472",
                },
                policy=c02_policy(),
            )

    def test_evidence_assignment_difference_is_not_equal(self) -> None:
        base, left, right = c02_post_worlds()
        right_new = next(
            node
            for node in right["nodes"]
            if node["node_id"] == "temporary-object-8472"
        )
        right_new["evidence_refs"] = ["obs:different"]
        right = seal_graph(right)
        with self.assertRaises(ContractError):
            validate_canonical_memory_state_equality(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                    "cup-2": "temporary-object-8472",
                },
                policy=c02_policy(),
            )

    def test_latent_assignment_difference_is_not_equal(self) -> None:
        base, left, right = c02_post_worlds()
        right_new = next(
            node
            for node in right["nodes"]
            if node["node_id"] == "temporary-object-8472"
        )
        right_new["latent_refs"] = ["latent:different-view-set"]
        right = seal_graph(right)
        with self.assertRaises(ContractError):
            validate_canonical_memory_state_equality(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                    "cup-2": "temporary-object-8472",
                },
                policy=c02_policy(),
            )

    def test_identity_permission_does_not_hide_world_difference(
        self,
    ) -> None:
        base = load_world("C05")
        mapping = {
            identity_id: identity_id
            for identity_id in {
                node["node_id"] for node in base["nodes"]
            }
        }
        mapping["chair-a"] = "chair-b"
        mapping["chair-b"] = "chair-a"
        policy = {
            "schema_version": "cpmt-0.2",
            "policy_id": "policy:C05:identity-only",
            "base_graph_version": "v0",
            "fixed_identity_ids": ["wall-protected"],
            "exchangeable_identity_sets": [["chair-a", "chair-b"]],
            "externally_anchored_new_ids": [],
            "raw_latent_exact_match": False,
            "comparison_mode": "canonical_memory_state",
            "future_projection_defines_equivalence": False,
        }
        with self.assertRaises(ContractError):
            validate_canonical_memory_state_equality(
                base,
                deepcopy(base),
                deepcopy(base),
                identity_mapping=mapping,
                policy=policy,
            )

    def test_protected_state_difference_is_not_equal(self) -> None:
        base, left, right = c02_post_worlds()
        with self.assertRaises(ContractError):
            validate_canonical_memory_state_equality(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                    "cup-2": "temporary-object-8472",
                },
                policy=c02_policy(),
                left_protected_ids={"wall-protected"},
                right_protected_ids=set(),
            )

    def test_pending_memory_difference_is_not_equal(self) -> None:
        base, left, right = c02_post_worlds()
        with self.assertRaises(ContractError):
            validate_canonical_memory_state_equality(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                    "cup-2": "temporary-object-8472",
                },
                policy=c02_policy(),
                left_pending_store=c09_pending_store(),
                right_pending_store=create_pending_store("other-name"),
            )

    def test_future_projection_cannot_define_equivalence(self) -> None:
        base, left, right = c02_post_worlds()
        policy = c02_policy(
            future_projection_defines_equivalence=True,
        )
        with self.assertRaises(ContractError):
            validate_canonical_memory_state_equality(
                base,
                left,
                right,
                identity_mapping={
                    "mug-1": "mug-1",
                    "wall-protected": "wall-protected",
                    "cup-2": "temporary-object-8472",
                },
                policy=policy,
            )


if __name__ == "__main__":
    unittest.main()
