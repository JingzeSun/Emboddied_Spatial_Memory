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

from cpmt.errors import (  # noqa: E402
    ContractError,
    DuplicateTransactionError,
    InvariantViolation,
    PreconditionError,
    ProtectedMutationError,
    UnsupportedTemplateError,
    VersionMismatchError,
)
from cpmt.executor import (  # noqa: E402
    execute_transaction,
    operation_argument_ids,
    preflight_transaction,
    validate_graph,
)
from cpmt.hashing import clone_json, compute_graph_hash, seal_graph  # noqa: E402
from cpmt.maintenance import apply_dormancy_maintenance  # noqa: E402


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


def load_world(
    case_family: str,
    filename: str = "world.json",
) -> dict:
    return seal_graph(load_json(FIXTURE_ROOT / case_family / filename))


def load_program(case_family: str, filename: str) -> dict:
    return load_json(
        FIXTURE_ROOT / case_family / "transactions" / filename
    )


def load_evidence(case_family: str) -> dict[str, dict]:
    evidence_dir = FIXTURE_ROOT / case_family / "evidence"
    return {
        event["evidence_id"]: event
        for event in (
            load_json(path)
            for path in sorted(evidence_dir.glob("*.json"))
        )
    }


class FixtureContractTests(unittest.TestCase):
    def test_c00_to_c11_references_exist_and_remain_draft(self) -> None:
        expected = {
            "C00",
            "C01",
            "C02",
            "C03",
            "C04",
            "C05",
            "C06",
            "C07",
            "C08",
            "C09",
            "C10",
            "C11",
        }
        self.assertEqual(
            expected,
            {
                path.name
                for path in FIXTURE_ROOT.iterdir()
                if path.is_dir()
            },
        )

        for case_family in sorted(expected):
            case_dir = FIXTURE_ROOT / case_family
            for case_path in sorted(case_dir.glob("case*.json")):
                case = load_json(case_path)
                self.assertEqual(case["case_family"], case_family)
                self.assertEqual(case["split"], "draft")
                self.assertEqual(case["status"], "human_draft")
                self.assertTrue(case["future_evidence_refs"])
                if case.get("oracle_commit_action") == "QUARANTINE":
                    self.assertEqual(case["oracle_equivalence"], [])
                else:
                    self.assertTrue(case["oracle_equivalence"])
                self.assertTrue(
                    (case_dir / case["prior_graph_ref"]).is_file()
                )
                for transaction_ref in case[
                    "candidate_transaction_refs"
                ]:
                    self.assertTrue(
                        (case_dir / transaction_ref).is_file()
                    )
                decision_ref = case.get("commit_decision_ref")
                if decision_ref:
                    self.assertTrue((case_dir / decision_ref).is_file())
                for evidence_ref in case.get(
                    "pending_evidence_refs",
                    [],
                ):
                    self.assertTrue((case_dir / evidence_ref).is_file())
            validate_graph(load_world(case_family))


class DeterministicExecutorTests(unittest.TestCase):
    def test_operation_argument_ids_use_structured_exact_fields(self) -> None:
        touched = operation_argument_ids({
            "target_id": "node-10",
            "predecessor_ids": ["node-2@v0"],
            "edge": {"source": "entity-3", "target": "place-4"},
            "evidence_ref": "node-1:mentioned-only-in-evidence",
            "note": "node-1",
        })
        self.assertEqual(
            touched,
            {"node-10", "node-2@v0", "entity-3", "place-4"},
        )
        self.assertNotIn("node-1", touched)

    def test_json_clone_is_independent_and_graph_hash_is_read_only(self) -> None:
        base = load_world("C00")
        before = deepcopy(base)
        cloned = clone_json(base)
        cloned["nodes"][0]["provenance"].append("test:clone-only")
        digest = compute_graph_hash(base)
        self.assertEqual(digest, base["graph_hash"])
        self.assertEqual(base, before)
        self.assertNotEqual(cloned, base)

    def test_c00_noop_preserves_persistent_world(self) -> None:
        base = load_world("C00")
        before = deepcopy(base)
        result = execute_transaction(
            base,
            load_program("C00", "noop.json"),
        )

        self.assertEqual(base, before)
        self.assertEqual(result["graph_version"], base["graph_version"])
        self.assertEqual(result["parent_version"], base["parent_version"])
        self.assertEqual(result["nodes"], base["nodes"])
        self.assertEqual(result["edges"], base["edges"])
        self.assertEqual(
            result["transaction_log"],
            base["transaction_log"],
        )
        self.assertEqual(
            compute_graph_hash(result),
            compute_graph_hash(base),
        )

    def test_c00_relink_preserves_identity_and_versions_edge(self) -> None:
        base = load_world("C00")
        result = execute_transaction(
            base,
            load_program("C00", "relink.json"),
        )

        versions = [
            edge
            for edge in result["edges"]
            if edge["edge_id"] == "chair-location"
        ]
        self.assertEqual(len(versions), 2)
        old = next(
            edge
            for edge in versions
            if edge["edge_version_id"] == "chair-location@v0"
        )
        new = next(
            edge
            for edge in versions
            if edge["edge_version_id"] == "chair-location@v1"
        )
        self.assertEqual(old["valid_to"], 5)
        self.assertEqual(new["source"], "chair-1")
        self.assertEqual(new["target"], "place-right")
        self.assertIsNone(new["valid_to"])
        self.assertEqual(
            len(
                {
                    node["node_id"]
                    for node in result["nodes"]
                }
            ),
            len(
                {
                    node["node_id"]
                    for node in base["nodes"]
                }
            ),
        )

    def test_c01_bind_attaches_evidence_without_new_identity(self) -> None:
        base = load_world("C01")
        result = execute_transaction(
            base,
            load_program("C01", "bind.json"),
        )

        self.assertEqual(len(result["nodes"]), len(base["nodes"]))
        chair = next(
            node
            for node in result["nodes"]
            if node["node_id"] == "chair-1"
        )
        self.assertEqual(chair["lifecycle"], "confirmed")
        self.assertIn(
            "obs:C01:t5:chair",
            chair["evidence_refs"],
        )
        self.assertNotIn(
            "obs:C01:t5:chair",
            next(
                node
                for node in base["nodes"]
                if node["node_id"] == "chair-1"
            )["evidence_refs"],
        )

    def test_c04_split_retracts_source_and_partitions_evidence(self) -> None:
        base = load_world("C04")
        result = execute_transaction(
            base,
            load_program("C04", "split.json"),
        )

        source = next(
            node
            for node in result["nodes"]
            if node["node_id"] == "conflated-1"
        )
        self.assertEqual(source["lifecycle"], "retracted")
        self.assertEqual(source["valid_to"], 5)
        successors = [
            node
            for node in result["nodes"]
            if node["node_id"] in {"object-left", "object-right"}
        ]
        self.assertEqual(len(successors), 2)
        self.assertTrue(
            all(node["lifecycle"] == "candidate" for node in successors)
        )
        evidence = [
            ref
            for node in successors
            for ref in node["evidence_refs"]
        ]
        self.assertEqual(len(evidence), len(set(evidence)))
        self.assertEqual(
            set(evidence),
            set(source["evidence_refs"])
            | {
                "obs:C04:t5:left-object",
                "obs:C04:t5:right-object",
            },
        )
        successor_latents = {
            ref
            for node in successors
            for ref in node["latent_refs"]
        }
        self.assertFalse(
            successor_latents & set(source["latent_refs"])
        )

    def test_c04_split_rejects_duplicate_evidence_atomically(self) -> None:
        base = load_world("C04")
        before = deepcopy(base)
        program = load_program("C04", "split.json")
        creates = [
            operation
            for operation in program["operations"]
            if operation["op_type"] == "CREATE_NODE"
        ]
        creates[1]["arguments"]["node"]["evidence_refs"].append(
            "obs:C04:t0:left-object"
        )

        with self.assertRaises(ContractError):
            execute_transaction(base, program)
        self.assertEqual(base, before)

    def test_c04_split_rejects_old_aggregate_latent(self) -> None:
        base = load_world("C04")
        program = load_program("C04", "split.json")
        first_create = next(
            operation
            for operation in program["operations"]
            if operation["op_type"] == "CREATE_NODE"
        )
        first_create["arguments"]["node"]["latent_refs"] = [
            "latent:C04:conflated-average"
        ]

        with self.assertRaises(ContractError):
            execute_transaction(base, program)

    def test_bind_does_not_implicitly_promote_candidate(self) -> None:
        base = load_world("C01")
        chair = next(
            node
            for node in base["nodes"]
            if node["node_id"] == "chair-1"
        )
        chair["lifecycle"] = "candidate"
        base = seal_graph(base)

        result = execute_transaction(
            base,
            load_program("C01", "bind.json"),
        )
        result_chair = next(
            node
            for node in result["nodes"]
            if node["node_id"] == "chair-1"
        )
        self.assertEqual(result_chair["lifecycle"], "candidate")

    def test_bind_can_explicitly_confirm_with_second_evidence(self) -> None:
        base = load_world("C01", "world-candidate.json")
        result = execute_transaction(
            base,
            load_program("C01", "bind-confirm.json"),
        )
        node = next(
            node
            for node in result["nodes"]
            if node["node_id"] == "chair-candidate"
        )
        self.assertEqual(node["lifecycle"], "confirmed")
        self.assertEqual(len(set(node["evidence_refs"])), 2)

    def test_duplicate_evidence_cannot_confirm_candidate(self) -> None:
        base = load_world("C01", "world-candidate.json")
        before = deepcopy(base)
        program = load_program("C01", "bind-confirm.json")
        for operation in program["operations"]:
            if operation["op_type"] == "ATTACH_EVIDENCE":
                operation["arguments"]["evidence_ref"] = (
                    "obs:C01:t0:candidate-chair"
                )

        with self.assertRaises(PreconditionError):
            execute_transaction(base, program)
        self.assertEqual(base, before)

    def test_c02_birth_creates_candidate_only(self) -> None:
        base = load_world("C02")
        result = execute_transaction(
            base,
            load_program("C02", "birth.json"),
        )

        created = [
            node
            for node in result["nodes"]
            if node["node_id"] == "cup-2"
        ]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["lifecycle"], "candidate")
        self.assertEqual(
            len(
                {
                    node["node_id"]
                    for node in result["nodes"]
                }
            ),
            len(
                {
                    node["node_id"]
                    for node in base["nodes"]
                }
            )
            + 1,
        )

    def test_c03_reactivate_keeps_history_and_opens_confirmed_version(
        self,
    ) -> None:
        base = load_world("C03")
        result = execute_transaction(
            base,
            load_program("C03", "reactivate.json"),
        )

        versions = [
            node
            for node in result["nodes"]
            if node["node_id"] == "chair-historical"
        ]
        self.assertEqual(len(versions), 2)
        old = next(
            node
            for node in versions
            if node["node_version_id"] == "chair-historical@v0"
        )
        new = next(
            node
            for node in versions
            if node["node_version_id"] == "chair-historical@v1"
        )
        self.assertEqual(old["lifecycle"], "dormant")
        self.assertEqual(old["valid_to"], 10)
        self.assertEqual(new["lifecycle"], "confirmed")
        self.assertIsNone(new["valid_to"])
        self.assertIn(
            "chair-historical@v0",
            new["predecessor_ids"],
        )

    def test_c05_merge_keeps_earliest_confirmed_canonical(self) -> None:
        base = load_world("C05")
        result = execute_transaction(
            base,
            load_program("C05", "merge.json"),
        )

        chair_a = [
            node
            for node in result["nodes"]
            if node["node_id"] == "chair-a"
        ]
        chair_b = [
            node
            for node in result["nodes"]
            if node["node_id"] == "chair-b"
        ]
        self.assertEqual(len(chair_a), 2)
        self.assertEqual(len(chair_b), 2)
        self.assertTrue(
            all(
                node["valid_to"] == 5
                for node in chair_a + chair_b
                if node["node_version_id"].endswith("@v0")
            )
        )
        canonical = next(
            node
            for node in chair_a
            if node["node_version_id"] == "chair-a@v1"
        )
        alias = next(
            node
            for node in chair_b
            if node["node_version_id"] == "chair-b@v1"
        )
        self.assertEqual(canonical["lifecycle"], "confirmed")
        self.assertIsNone(canonical["canonical_id"])
        self.assertEqual(
            set(canonical["evidence_refs"]),
            {
                "obs:C05:t0:chair-a",
                "obs:C05:t2:chair-b",
                "obs:C05:t5:same-chair",
            },
        )
        self.assertEqual(
            set(canonical["latent_refs"]),
            {"latent:C05:chair-a", "latent:C05:chair-b"},
        )
        self.assertEqual(alias["lifecycle"], "alias")
        self.assertEqual(alias["canonical_id"], "chair-a")
        self.assertEqual(alias["evidence_refs"], [])
        self.assertEqual(alias["latent_refs"], [])

    def test_c05_merge_rejects_wrong_canonical_atomically(self) -> None:
        base = load_world("C05")
        before = deepcopy(base)
        program = load_program("C05", "merge.json")
        opened = [
            operation["arguments"]["node"]
            for operation in program["operations"]
            if operation["op_type"] == "OPEN_NODE_VERSION"
        ]
        chair_a = next(
            node for node in opened if node["node_id"] == "chair-a"
        )
        chair_b = next(
            node for node in opened if node["node_id"] == "chair-b"
        )
        chair_a["lifecycle"] = "alias"
        chair_a["canonical_id"] = "chair-b"
        chair_a["evidence_refs"] = []
        chair_a["latent_refs"] = []
        chair_a["predecessor_ids"] = ["chair-a@v0"]
        chair_b["lifecycle"] = "confirmed"
        chair_b["canonical_id"] = None
        chair_b["evidence_refs"] = [
            "obs:C05:t0:chair-a",
            "obs:C05:t2:chair-b",
            "obs:C05:t5:same-chair",
        ]
        chair_b["latent_refs"] = [
            "latent:C05:chair-a",
            "latent:C05:chair-b",
        ]
        chair_b["predecessor_ids"] = [
            "chair-a@v0",
            "chair-b@v0",
        ]

        with self.assertRaises(ContractError):
            execute_transaction(base, program)
        self.assertEqual(base, before)

    def test_c06_replace_retracts_fact_but_preserves_old_identity(
        self,
    ) -> None:
        base = load_world("C06")
        result = execute_transaction(
            base,
            load_program("C06", "replace.json"),
            evidence_by_id=load_evidence("C06"),
            reliability_threshold=1.0,
        )

        old_edge = next(
            edge
            for edge in result["edges"]
            if edge["edge_version_id"] == "old-chair-location@v0"
        )
        self.assertEqual(old_edge["valid_to"], 5)
        self.assertTrue(
            {
                "ev:C06:negative-left-t3",
                "ev:C06:negative-left-t5",
            }.issubset(old_edge["evidence_refs"])
        )
        old_identity = next(
            node
            for node in result["nodes"]
            if node["node_version_id"] == "chair-old@v0"
        )
        self.assertEqual(old_identity["lifecycle"], "confirmed")
        self.assertIsNone(old_identity["valid_to"])
        new_identity = next(
            node
            for node in result["nodes"]
            if node["node_version_id"] == "chair-new@v0"
        )
        self.assertEqual(new_identity["lifecycle"], "candidate")
        new_edge = next(
            edge
            for edge in result["edges"]
            if edge["edge_version_id"] == "new-chair-location@v0"
        )
        self.assertEqual(new_edge["source"], "chair-new")
        self.assertEqual(new_edge["target"], "place-right")
        self.assertIsNone(new_edge["valid_to"])

    def test_c06_replace_rejects_wrong_component_order_atomically(
        self,
    ) -> None:
        base = load_world("C06")
        before = deepcopy(base)
        program = load_program("C06", "replace.json")
        create = next(
            operation
            for operation in program["operations"]
            if operation["op_type"] == "CREATE_NODE"
        )
        program["operations"] = [
            create,
            *[
                operation
                for operation in program["operations"]
                if operation is not create
            ],
        ]

        with self.assertRaises(ContractError):
            execute_transaction(
                base,
                program,
                evidence_by_id=load_evidence("C06"),
            )
        self.assertEqual(base, before)

    def test_c06_replace_cannot_retract_old_identity(self) -> None:
        base = load_world("C06")
        program = load_program("C06", "replace.json")
        program["operations"].append(
            {
                "op_id": "wrongly-retract-old-identity",
                "op_type": "SET_LIFECYCLE",
                "arguments": {
                    "node_id": "chair-old",
                    "from": "confirmed",
                    "to": "retracted",
                },
            }
        )

        with self.assertRaises(ContractError):
            execute_transaction(
                base,
                program,
                evidence_by_id=load_evidence("C06"),
            )

    def test_c07_retract_closes_fact_but_keeps_identity(self) -> None:
        base = load_world("C07")
        result = execute_transaction(
            base,
            load_program("C07", "retract.json"),
            evidence_by_id=load_evidence("C07"),
            reliability_threshold=1.0,
        )

        edge = next(
            edge
            for edge in result["edges"]
            if edge["edge_version_id"] == "chair-location@v0"
        )
        self.assertEqual(edge["valid_to"], 7)
        self.assertTrue(
            {
                "ev:C07:negative-t5",
                "ev:C07:negative-t7",
            }.issubset(edge["evidence_refs"])
        )
        identity = next(
            node
            for node in result["nodes"]
            if node["node_version_id"] == "chair-1@v0"
        )
        self.assertEqual(identity["lifecycle"], "confirmed")
        self.assertIsNone(identity["valid_to"])

    def test_c07_occlusion_cannot_retract_fact_atomically(self) -> None:
        base = load_world("C07")
        before = deepcopy(base)

        with self.assertRaises(PreconditionError):
            execute_transaction(
                base,
                load_program("C07", "retract-occluded.json"),
                evidence_by_id=load_evidence("C07"),
            )
        self.assertEqual(base, before)

    def test_c07_low_reliability_cannot_retract_fact(self) -> None:
        evidence = load_evidence("C07")
        evidence["ev:C07:negative-t5"]["reliability"] = 0.5

        with self.assertRaises(PreconditionError):
            execute_transaction(
                load_world("C07"),
                load_program("C07", "retract.json"),
                evidence_by_id=evidence,
                reliability_threshold=1.0,
            )

    def test_c07_invalid_geometry_cannot_retract_fact(self) -> None:
        for field in ("pose_valid", "depth_valid"):
            with self.subTest(field=field):
                evidence = load_evidence("C07")
                evidence["ev:C07:negative-t5"][field] = False
                with self.assertRaises(PreconditionError):
                    execute_transaction(
                        load_world("C07"),
                        load_program("C07", "retract.json"),
                        evidence_by_id=evidence,
                    )

    def test_c07_duplicate_time_view_key_cannot_retract_fact(
        self,
    ) -> None:
        evidence = load_evidence("C07")
        first = evidence["ev:C07:negative-t5"]
        second = evidence["ev:C07:negative-t7"]
        second["time_index"] = first["time_index"]
        second["viewpoint_id"] = first["viewpoint_id"]

        with self.assertRaises(PreconditionError):
            execute_transaction(
                load_world("C07"),
                load_program("C07", "retract.json"),
                evidence_by_id=evidence,
            )

    def test_c07_intervening_positive_breaks_negative_chain(
        self,
    ) -> None:
        evidence = load_evidence("C07")
        evidence["ev:C07:positive-t6"] = {
            "schema_version": "cpmt-0.2",
            "evidence_id": "ev:C07:positive-t6",
            "episode_id": "episode:C07:001",
            "time_index": 6,
            "kind": "observation",
            "source_refs": ["obs:C07:t6:chair-visible"],
            "availability": "online",
            "reliability": 1.0,
            "claim_ref": "chair-location@v0",
            "viewpoint_id": "view:C07:left-positive",
            "visibility": "visible",
            "pose_valid": True,
            "depth_valid": True,
            "verdict": "supports",
            "notes": "A positive sighting interrupts absence evidence.",
        }

        with self.assertRaises(PreconditionError):
            execute_transaction(
                load_world("C07"),
                load_program("C07", "retract.json"),
                evidence_by_id=evidence,
            )

    def test_c07_missing_evidence_record_cannot_retract_fact(
        self,
    ) -> None:
        evidence = load_evidence("C07")
        del evidence["ev:C07:negative-t7"]

        with self.assertRaises(PreconditionError):
            execute_transaction(
                load_world("C07"),
                load_program("C07", "retract.json"),
                evidence_by_id=evidence,
            )

    def test_c08_relink_versions_topology_without_new_identity(
        self,
    ) -> None:
        base = load_world("C08")
        result = execute_transaction(
            base,
            load_program("C08", "relink.json"),
        )

        old = next(
            edge
            for edge in result["edges"]
            if edge["edge_version_id"] == "portal-route@v0"
        )
        new = next(
            edge
            for edge in result["edges"]
            if edge["edge_version_id"] == "portal-route@v1"
        )
        self.assertEqual(old["valid_to"], 5)
        self.assertEqual(new["source"], "portal-1")
        self.assertEqual(new["relation"], "leads_to")
        self.assertEqual(new["target"], "sealed-boundary")
        self.assertEqual(len(result["nodes"]), len(base["nodes"]))

    def test_static_preflight_is_read_only_and_pass_is_not_execution(self) -> None:
        base = load_world("C08")
        before = deepcopy(base)
        legal = load_program("C08", "relink.json")
        self.assertIsNone(preflight_transaction(base, legal))
        self.assertEqual(base, before)

        protected = deepcopy(legal)
        protected["protected_ids"].append("portal-route")
        with self.assertRaises(ProtectedMutationError):
            preflight_transaction(base, protected)
        self.assertEqual(base, before)

        pass_unknown = deepcopy(legal)
        new_edge = next(
            operation["arguments"]["edge"]
            for operation in pass_unknown["operations"]
            if operation["op_type"] == "ADD_EDGE"
        )
        new_edge["target"] = "unknown-static-target"
        self.assertIsNone(preflight_transaction(base, pass_unknown))
        with self.assertRaises(PreconditionError):
            execute_transaction(base, pass_unknown)
        self.assertEqual(base, before)

    def test_c09_pose_fault_noop_and_true_relink_are_both_executable(
        self,
    ) -> None:
        base = load_world("C09")
        noop = execute_transaction(
            base,
            load_program("C09", "noop.json"),
        )
        relink = execute_transaction(
            base,
            load_program("C09", "relink.json"),
        )

        self.assertEqual(
            compute_graph_hash(noop),
            compute_graph_hash(base),
        )
        open_location = next(
            edge
            for edge in relink["edges"]
            if edge["edge_id"] == "chair-location"
            and edge["valid_to"] is None
        )
        self.assertEqual(open_location["target"], "place-right")

    def test_redundant_relink_to_same_target_is_rejected_atomically(
        self,
    ) -> None:
        base = load_world("C09")
        before = deepcopy(base)
        program = load_program("C09", "relink.json")
        new_edge = next(
            operation["arguments"]["edge"]
            for operation in program["operations"]
            if operation["op_type"] == "ADD_EDGE"
        )
        old_edge = next(
            edge
            for edge in base["edges"]
            if edge["edge_id"] == "chair-location"
            and edge["valid_to"] is None
        )
        new_edge["target"] = old_edge["target"]

        with self.assertRaises(ContractError):
            execute_transaction(base, program)
        self.assertEqual(base, before)

    def test_c10_bind_static_surface_without_touching_distractor(
        self,
    ) -> None:
        base = load_world("C10")
        result = execute_transaction(
            base,
            load_program("C10", "bind.json"),
        )

        wall = next(
            node for node in result["nodes"] if node["node_id"] == "wall-1"
        )
        table = next(
            node
            for node in result["nodes"]
            if node["node_id"] == "table-protected"
        )
        base_table = next(
            node
            for node in base["nodes"]
            if node["node_id"] == "table-protected"
        )
        self.assertIn("obs:C10:t5:foreground-change", wall["evidence_refs"])
        self.assertEqual(table, base_table)

    def test_c11_collateral_protected_edit_is_rejected_atomically(
        self,
    ) -> None:
        base = load_world("C11")
        before = deepcopy(base)

        with self.assertRaises(ProtectedMutationError):
            execute_transaction(
                base,
                load_program("C11", "bind-collateral.json"),
            )
        self.assertEqual(base, before)
        valid = execute_transaction(
            base,
            load_program("C11", "bind.json"),
        )
        chair = next(
            node
            for node in valid["nodes"]
            if node["node_id"] == "chair-1"
        )
        self.assertIn("obs:C11:t5:chair", chair["evidence_refs"])

    def test_bind_rejects_dormant_target_atomically(self) -> None:
        base = load_world("C03")
        before = deepcopy(base)
        program = load_program("C03", "bind-active.json")
        for operation in program["operations"]:
            arguments = operation["arguments"]
            if arguments.get("node_id") == "chair-active":
                arguments["node_id"] = "chair-historical"
            if arguments.get("target_id") == "chair-active":
                arguments["target_id"] = "chair-historical"

        with self.assertRaises(PreconditionError):
            execute_transaction(base, program)
        self.assertEqual(base, before)

    def test_reactivate_rejects_retracted_identity_atomically(self) -> None:
        base = load_world("C03")
        historical = next(
            node
            for node in base["nodes"]
            if node["node_id"] == "chair-historical"
        )
        historical["lifecycle"] = "retracted"
        historical["valid_to"] = 9
        base = seal_graph(base)
        before = deepcopy(base)

        with self.assertRaises(PreconditionError):
            execute_transaction(
                base,
                load_program("C03", "reactivate.json"),
            )
        self.assertEqual(base, before)

    def test_wrong_base_version_is_rejected_atomically(self) -> None:
        base = load_world("C01")
        before = deepcopy(base)
        program = load_program("C01", "bind.json")
        program["base_graph_version"] = "some-other-version"

        with self.assertRaises(VersionMismatchError):
            execute_transaction(base, program)
        self.assertEqual(base, before)

    def test_protected_target_is_rejected_atomically(self) -> None:
        base = load_world("C01")
        before = deepcopy(base)

        with self.assertRaises(ProtectedMutationError):
            execute_transaction(
                base,
                load_program("C01", "bind.json"),
                protected_ids={"chair-1"},
            )
        self.assertEqual(base, before)

    def test_missing_transaction_provenance_rejects_result(self) -> None:
        base = load_world("C01")
        before = deepcopy(base)
        program = load_program("C01", "bind.json")
        program["operations"] = [
            operation
            for operation in program["operations"]
            if operation["op_type"] != "RECORD_PROVENANCE"
        ]

        with self.assertRaises(InvariantViolation):
            execute_transaction(base, program)
        self.assertEqual(base, before)

    def test_duplicate_transaction_id_is_explicitly_rejected(self) -> None:
        program = load_program("C01", "bind.json")
        committed = execute_transaction(load_world("C01"), program)
        replay = deepcopy(program)
        replay["base_graph_version"] = committed["graph_version"]

        with self.assertRaises(DuplicateTransactionError):
            execute_transaction(committed, replay)

    def test_unimplemented_template_is_not_silently_executed(self) -> None:
        base = load_world("C01")
        program = load_program("C01", "bind.json")
        program["transaction_id"] = "tx-unimplemented-retract"
        program["intent"] = "REVISE"
        program["template"] = "RETRACT"
        program["retraction_target"] = {
            "kind": "node_version",
            "version_id": "chair-1@v0",
        }

        with self.assertRaises(UnsupportedTemplateError):
            execute_transaction(base, program)

    def test_multiple_open_versions_violate_graph_contract(self) -> None:
        graph = load_world("C01")
        duplicate = deepcopy(graph["nodes"][0])
        duplicate["node_version_id"] = "chair-1@duplicate"
        graph["nodes"].append(duplicate)
        graph["graph_hash"] = None

        with self.assertRaises(InvariantViolation):
            validate_graph(graph)

    def test_dormancy_maintenance_versions_without_deleting(self) -> None:
        base = load_world("C01")
        before = deepcopy(base)
        result = apply_dormancy_maintenance(
            base,
            at=10,
            inactivity_horizon=5,
            last_seen_by_node={"chair-1": 0, "wall-protected": 0},
            maintenance_id="C01-at-10",
        )

        self.assertEqual(base, before)
        versions = [
            node
            for node in result["nodes"]
            if node["node_id"] == "chair-1"
        ]
        self.assertEqual(len(versions), 2)
        old = next(
            node
            for node in versions
            if node["node_version_id"] == "chair-1@v0"
        )
        dormant = next(
            node
            for node in versions
            if node["lifecycle"] == "dormant"
        )
        self.assertEqual(old["valid_to"], 10)
        self.assertIsNone(dormant["valid_to"])
        self.assertEqual(
            dormant["evidence_refs"],
            old["evidence_refs"],
        )
        self.assertEqual(
            dormant["latent_refs"],
            old["latent_refs"],
        )
        wall = next(
            node
            for node in result["nodes"]
            if node["node_id"] == "wall-protected"
        )
        self.assertEqual(wall["lifecycle"], "confirmed")

    def test_dormancy_before_horizon_is_noop(self) -> None:
        base = load_world("C01")
        result = apply_dormancy_maintenance(
            base,
            at=4,
            inactivity_horizon=5,
            last_seen_by_node={"chair-1": 0},
            maintenance_id="C01-at-4",
        )
        self.assertEqual(
            compute_graph_hash(result),
            compute_graph_hash(base),
        )
        self.assertEqual(
            result["transaction_log"],
            base["transaction_log"],
        )


if __name__ == "__main__":
    unittest.main()
