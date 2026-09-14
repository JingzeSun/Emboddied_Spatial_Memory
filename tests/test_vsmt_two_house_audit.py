from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.two_house_audit import (  # noqa: E402
    REGISTERED_PROGRAMS,
    assert_two_house_action_authorized,
    capacity_probe,
    evaluate_private_recall,
    make_episode_plans,
    make_public_seal,
    make_source_inventory,
    select_audit_houses,
    validate_episode_plans,
    validate_house_selection,
    validate_public_episode_plan,
    validate_source_inventory,
    validate_two_house_config,
)


CONFIG_PATH = (
    PROJECT_ROOT / "configs" / "vsmt" / "vm04_l1_two_house_audit_proposal_v1.json"
)


def config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def houses(count: int = 6) -> list[dict]:
    return [
        {
            "house_id": f"train_{index}",
            "source_file_sha256": hashlib.sha256(f"file-{index}".encode()).hexdigest(),
            "source_record_sha256": hashlib.sha256(f"row-{index}".encode()).hexdigest(),
            "source_locator": {"relative_path": "train.json", "index": index},
        }
        for index in range(count)
    ]


def licenses() -> list[dict]:
    return [{"name": "LICENSE", "sha256": "a" * 64, "bytes": 123}]


def inventory(rows: list[dict] | None = None) -> dict:
    return make_source_inventory(
        houses() if rows is None else rows,
        source_release_commit="d54954a81e7126001e552c2d7904ee2e0d49eaae",
        license_files=licenses(),
    )


def plans() -> dict[str, dict]:
    source = inventory()
    selection = select_audit_houses(source, split_seed=260914)
    return make_episode_plans(
        selection, inventory=source, assignment_salt=b"s" * 32,
        config_version=config()["version"],
    )


def public_rows(public_plan: dict) -> list[dict]:
    key = hashlib.sha256(b"reference-key").hexdigest()
    catalogs = {
        "16": {"canonical_candidate_key_sha256s": [key]},
        "32": {"canonical_candidate_key_sha256s": [key]},
        "64": {"canonical_candidate_key_sha256s": [key]},
    }
    return [
        {
            "episode_id": row["episode_id"],
            "family_id": row["family_id"],
            "slot": row["slot"],
            "status": "constructed",
            "profiles": {
                "strict": {"catalogs": deepcopy(catalogs)},
                "balanced": {"catalogs": deepcopy(catalogs)},
                "permissive_capacity_upper_bound": {"catalogs": deepcopy(catalogs)},
            },
            "capacity_audit": {},
            "runtime": {"wall_seconds": 0.1, "peak_rss_bytes": 1},
        }
        for row in public_plan["episodes"]
    ]


class TwoHouseAuditContractTests(unittest.TestCase):
    def test_frozen_config_is_implementation_only(self) -> None:
        value = validate_two_house_config(config())
        self.assertEqual(value["status"], "approved_for_implementation_not_executable")
        self.assertTrue(value["audit_numeric_values_approved"])
        self.assertTrue(value["implementation_authorized"])
        for action in ("inventory", "select", "generate", "private-eval"):
            with self.assertRaisesRegex(ValueError, "not authorized"):
                assert_two_house_action_authorized(value, action=action)

    def test_inventory_is_order_independent_and_does_not_select(self) -> None:
        forward = inventory()
        reverse = inventory(list(reversed(houses())))
        self.assertEqual(forward, reverse)
        self.assertFalse(forward["selection_performed"])
        self.assertFalse(forward["generation_performed"])
        self.assertFalse(forward["private_data_opened"])
        self.assertEqual(validate_source_inventory(forward), forward)

    def test_inventory_rejects_duplicate_house_ids(self) -> None:
        rows = houses()
        rows[-1]["house_id"] = rows[0]["house_id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            inventory(rows)

    def test_selection_is_a_pure_function_of_frozen_inventory(self) -> None:
        source = inventory()
        selected = select_audit_houses(source, split_seed=260914)
        self.assertEqual(len(selected["audit_house_ids"]), 2)
        self.assertEqual(
            validate_house_selection(selected, inventory=source), selected,
        )
        tampered = deepcopy(selected)
        tampered["audit_house_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "not reproducible"):
            validate_house_selection(tampered, inventory=source)

    def test_public_plan_never_exposes_program_or_house(self) -> None:
        value = plans()
        self.assertEqual(validate_episode_plans(value), value)
        self.assertEqual(validate_public_episode_plan(value["public"]), value["public"])
        self.assertEqual(len(value["public"]["episodes"]), 36)
        rendered = json.dumps(value["public"], sort_keys=True)
        self.assertNotIn("source_house_id", rendered)
        for program in REGISTERED_PROGRAMS:
            self.assertNotIn(f'"{program}"', rendered)
        counts = {}
        for row in value["private"]["assignments"]:
            counts[(row["family_id"], row["program"])] = (
                counts.get((row["family_id"], row["program"]), 0) + 1
            )
        self.assertTrue(all(value == 2 for value in counts.values()))

    def test_private_salt_changes_assignment_not_public_slots(self) -> None:
        source = inventory()
        selection = select_audit_houses(source, split_seed=260914)
        first = make_episode_plans(
            selection, inventory=source, assignment_salt=b"a" * 32,
            config_version=config()["version"],
        )
        second = make_episode_plans(
            selection, inventory=source, assignment_salt=b"b" * 32,
            config_version=config()["version"],
        )
        self.assertEqual(first["public"], second["public"])
        self.assertNotEqual(first["private"], second["private"])

    def test_public_seal_digest_ignores_worker_completion_order(self) -> None:
        plan = plans()["public"]
        rows = public_rows(plan)
        first = make_public_seal(
            rows, public_manifest_sha256=plan["manifest_sha256"],
            capacities=[16, 32, 64], worker_completion_order=["family:0", "family:1"],
        )
        second = make_public_seal(
            list(reversed(rows)), public_manifest_sha256=plan["manifest_sha256"],
            capacities=[16, 32, 64], worker_completion_order=["family:1", "family:0"],
        )
        self.assertEqual(
            first["canonical_episode_digest"], second["canonical_episode_digest"],
        )
        self.assertNotEqual(first["worker_completion_order"], second["worker_completion_order"])

    def test_public_seal_rejects_private_fields(self) -> None:
        plan = plans()["public"]
        rows = public_rows(plan)
        rows[0]["program"] = "NOOP"
        with self.assertRaisesRegex(ValueError, "private field"):
            make_public_seal(
                rows, public_manifest_sha256=plan["manifest_sha256"],
                capacities=[16, 32, 64], worker_completion_order=[],
            )

    def test_public_plan_standalone_validator_rejects_private_companion_fields(self) -> None:
        value = plans()["public"]
        value["program"] = "NOOP"
        with self.assertRaisesRegex(ValueError, "unexpected fields"):
            validate_public_episode_plan(value)

    def test_private_evaluation_reports_strict_and_margin_recall(self) -> None:
        plan = plans()
        key = hashlib.sha256(b"reference-key").hexdigest()
        seal = make_public_seal(
            public_rows(plan["public"]),
            public_manifest_sha256=plan["public"]["manifest_sha256"],
            capacities=[16, 32, 64], worker_completion_order=["f0", "f1"],
        )
        rows = []
        for assignment in plan["private"]["assignments"]:
            rows.append({
                "episode_id": assignment["episode_id"],
                "family_id": assignment["family_id"],
                "program": assignment["program"],
                "replicate": assignment["replicate"],
                "constructed": True,
                "construction_failure_reason": None,
                "canonical_reference_key_sha256_by_profile": {
                    "strict": key,
                    "balanced": key,
                    "permissive_capacity_upper_bound": key,
                },
                "entity_retract_legal_at_margin_0_02": assignment["program"] == "RETRACT",
                "entity_retract_legal_at_margin_0_05": False,
            })
        result = evaluate_private_recall(seal, rows)
        self.assertEqual(result["episode_count"], 36)
        self.assertTrue(all(
            row["strict_exact_canonical_reference_program_recall"]["strict"]["16"]
            for row in result["episodes"]
        ))
        retract = next(row for row in result["episodes"] if row["program"] == "RETRACT")
        self.assertIsNotNone(
            retract["entity_RETRACT_legal_candidate_recall"]["margin_0_02_m"]
        )
        self.assertIsNone(
            retract["entity_RETRACT_legal_candidate_recall"]["margin_0_05_m"]
        )
        self.assertIsNone(result["semantic_equivalence_class_recall"])
        self.assertIsNone(
            result["episodes"][0]["candidate_miss_reason"]["strict"]["16"]
        )

    def test_capacity_probe_refuses_wrong_worker_count_or_large_prediction(self) -> None:
        value = capacity_probe(
            free_bytes=10_000_000_000, visible_cpu_count=12,
            requested_workers=2, predicted_wall_seconds=100,
            predicted_stage_bytes=1000, config=config(),
        )
        self.assertTrue(value["ready"])
        wrong = capacity_probe(
            free_bytes=10_000_000_000, visible_cpu_count=12,
            requested_workers=1, predicted_wall_seconds=100,
            predicted_stage_bytes=1000, config=config(),
        )
        self.assertFalse(wrong["ready"])
        slow = capacity_probe(
            free_bytes=10_000_000_000, visible_cpu_count=12,
            requested_workers=2, predicted_wall_seconds=1801,
            predicted_stage_bytes=1000, config=config(),
        )
        self.assertFalse(slow["ready"])


if __name__ == "__main__":
    unittest.main()
