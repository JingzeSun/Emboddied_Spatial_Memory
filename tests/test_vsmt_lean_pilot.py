"""D-224 / S1-02a read-only checks for the four-worker pilot.

The continue gate for S1-02a is: the split is frozen before the first
episode, the pilot houses are recomputed rather than chosen, the four pilot
episodes count towards the fifty, occupancy is complete before anything is
derived from it, and failures are kept and counted.  These tests prove the
checks reject what they must.  They start no simulator and generate no
episode.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import unittest
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_assets, lean_intervention, lean_pilot  # noqa: E402
from vsmt.lean_pilot import (  # noqa: E402
    OCCUPANCY_RECEIPT_FIELDS,
    PILOT_RECEIPT_FIELDS,
    PILOT_TOTAL_HOUSES,
    PILOT_WORKERS,
    REQUIRED_STATISTIC,
    REQUIRED_WORKLOAD,
    LeanPilotError,
    plan_scale_up,
    select_pilot_houses,
    train_block,
    validate_occupancy_receipt,
    validate_pilot_contract,
    validate_pilot_plan,
    validate_pilot_receipt,
    validate_split_freeze,
)


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_02a_pilot_v2.json"

POOL = [f"house-{index:04d}" for index in range(200)]


def freeze(**overrides: Any) -> dict[str, Any]:
    values = {"seed": 260920, "validation_houses": 50, "test_houses": 100,
              "train_houses": None}
    values.update(overrides)
    return values


def occupancy(**overrides: Any) -> dict[str, Any]:
    row = {
        "concurrency_verified_at": PILOT_WORKERS,
        "cpu_cores_per_worker": 2.0,
        "ram_gb_per_worker": 6.0,
        "vram_gb_per_worker": 2.0,
        "disk_gb_per_worker": 1.5,
        "simulator_concurrency_limit": 4,
        "statistic": REQUIRED_STATISTIC,
        "workload": REQUIRED_WORKLOAD,
        "failures": [],
    }
    row.update(overrides)
    return {name: row[name] for name in OCCUPANCY_RECEIPT_FIELDS}


def measurements(**overrides: Any) -> dict[str, Any]:
    values = {
        "cpu_logical_cores": 128, "cpu_physical_cores": 64,
        "ram_total_gb": 1007.0, "ram_available_gb": 894.0,
        "gpu_count": 1, "gpu_name": "NVIDIA GeForce RTX 4080",
        "gpu_total_vram_gb": 32.0, "gpu_free_vram_gb": 31.4,
        "disk_free_gb_asset_root": 43.0, "disk_free_gb_install_root": 43.0,
        "python_version": "3.12.3", "torch_version": "2.8.0+cu128",
        "cuda_available": True, "egl_resolves": True, "vulkan_resolves": True,
    }
    values.update(overrides)
    return values


def pilot_receipt(**overrides: Any) -> dict[str, Any]:
    selected = select_pilot_houses(POOL, freeze())
    row = {
        "split_seed": 260920,
        "split_sizes": {"train": None, "validation": 50, "test": 100},
        "selected_house_ids": selected,
        "planned": PILOT_TOTAL_HOUSES,
        "succeeded": PILOT_TOTAL_HOUSES,
        "failed": 0,
        "failure_receipts": [],
        "wall_clock_seconds": 812.5,
        "exit_codes": [0, 0, 0, 0],
        "code_commit": "0" * 40,
    }
    row.update(overrides)
    return {name: row[name] for name in PILOT_RECEIPT_FIELDS}


class TestSplitFreeze(unittest.TestCase):
    def test_a_complete_freeze_passes(self) -> None:
        self.assertEqual(validate_split_freeze(freeze())["seed"], 260920)

    def test_an_open_seed_blocks_generation(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_split_freeze(freeze(seed=None))

    def test_an_open_validation_or_test_size_blocks_generation(self) -> None:
        for name in ("validation_houses", "test_houses"):
            with self.assertRaises(LeanPilotError):
                validate_split_freeze(freeze(**{name: None}))

    def test_train_size_may_still_be_open_here(self) -> None:
        # It is registered at S3-01 and may only decrease afterwards.
        validate_split_freeze(freeze(train_houses=None))

    def test_a_missing_field_is_rejected(self) -> None:
        partial = freeze()
        del partial["test_houses"]
        with self.assertRaises(LeanPilotError):
            validate_split_freeze(partial)


class TestPilotSelection(unittest.TestCase):
    def test_the_pilot_is_the_head_of_the_train_block(self) -> None:
        selected = select_pilot_houses(POOL, freeze())
        self.assertEqual(selected, train_block(POOL, freeze())[:PILOT_TOTAL_HOUSES])
        self.assertEqual(len(selected), 4)

    def test_the_selection_uses_the_s0_02_split_and_not_a_second_copy(self) -> None:
        split = lean_intervention.assign_split(
            POOL, seed=260920, train=len(POOL) - 150, validation=50, test=100)
        self.assertEqual(select_pilot_houses(POOL, freeze()), split["train"][:4])

    def test_the_pilot_never_touches_test_or_validation(self) -> None:
        split = lean_intervention.assign_split(
            POOL, seed=260920, train=len(POOL) - 150, validation=50, test=100)
        selected = set(select_pilot_houses(POOL, freeze()))
        self.assertFalse(selected & set(split["test"]))
        self.assertFalse(selected & set(split["validation"]))

    def test_changing_the_seed_moves_the_pilot(self) -> None:
        # This is exactly why the seed has to be frozen first.
        self.assertNotEqual(select_pilot_houses(POOL, freeze()),
                            select_pilot_houses(POOL, freeze(seed=260921)))

    def test_changing_the_test_size_moves_the_train_block_start(self) -> None:
        self.assertNotEqual(select_pilot_houses(POOL, freeze()),
                            select_pilot_houses(POOL, freeze(test_houses=101)))

    def test_lowering_the_train_size_leaves_the_pilot_where_it_was(self) -> None:
        # S3-01 may trim the train tail; the head must not move.
        self.assertEqual(select_pilot_houses(POOL, freeze(train_houses=50)),
                         select_pilot_houses(POOL, freeze(train_houses=40)))

    def test_the_same_inputs_always_give_the_same_four(self) -> None:
        self.assertEqual(select_pilot_houses(POOL, freeze()),
                         select_pilot_houses(list(POOL), freeze()))

    def test_a_pool_too_small_for_the_pilot_is_rejected(self) -> None:
        with self.assertRaises(LeanPilotError):
            select_pilot_houses(POOL[:152], freeze())


class TestPilotPlan(unittest.TestCase):
    def plan(self, **overrides: Any) -> dict[str, Any]:
        row = {"workers": PILOT_WORKERS, "houses_per_worker": 1,
               "house_ids": select_pilot_houses(POOL, freeze())}
        row.update(overrides)
        return row

    def test_a_matching_plan_passes(self) -> None:
        validate_pilot_plan(self.plan(), POOL, freeze())

    def test_a_hand_picked_house_is_rejected(self) -> None:
        swapped = select_pilot_houses(POOL, freeze())
        swapped[3] = train_block(POOL, freeze())[40]
        with self.assertRaises(LeanPilotError):
            validate_pilot_plan(self.plan(house_ids=swapped), POOL, freeze())

    def test_reordering_the_houses_is_rejected(self) -> None:
        reordered = list(reversed(select_pilot_houses(POOL, freeze())))
        with self.assertRaises(LeanPilotError):
            validate_pilot_plan(self.plan(house_ids=reordered), POOL, freeze())

    def test_a_duplicate_house_is_rejected(self) -> None:
        selected = select_pilot_houses(POOL, freeze())
        with self.assertRaises(LeanPilotError):
            validate_pilot_plan(self.plan(house_ids=[selected[0]] * 4), POOL, freeze())

    def test_widening_the_pilot_is_rejected(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_pilot_plan(self.plan(workers=8), POOL, freeze())

    def test_more_than_one_house_per_worker_is_rejected(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_pilot_plan(self.plan(houses_per_worker=2), POOL, freeze())


class TestPilotReceipt(unittest.TestCase):
    def test_a_clean_receipt_passes(self) -> None:
        validate_pilot_receipt(pilot_receipt())

    def test_a_silently_dropped_episode_is_caught(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_pilot_receipt(pilot_receipt(succeeded=3, failed=0))

    def test_a_failure_without_a_receipt_is_caught(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_pilot_receipt(pilot_receipt(succeeded=3, failed=1,
                                                 failure_receipts=[]))

    def test_a_kept_failure_passes_and_is_not_replaced(self) -> None:
        selected = select_pilot_houses(POOL, freeze())
        checked = validate_pilot_receipt(pilot_receipt(
            succeeded=3, failed=1,
            failure_receipts=[{"house_id": selected[2],
                               "reason": "intervention_window_unavailable"}]))
        self.assertEqual(checked["selected_house_ids"], selected)
        self.assertEqual(checked["planned"], 4)

    def test_an_invented_failure_reason_is_rejected(self) -> None:
        selected = select_pilot_houses(POOL, freeze())
        with self.assertRaises(LeanPilotError):
            validate_pilot_receipt(pilot_receipt(
                succeeded=3, failed=1,
                failure_receipts=[{"house_id": selected[0], "reason": "looked_boring"}]))

    def test_a_failure_naming_an_unselected_house_is_rejected(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_pilot_receipt(pilot_receipt(
                succeeded=3, failed=1,
                failure_receipts=[{"house_id": "house-9999",
                                   "reason": "house_load_failed"}]))

    def test_regenerating_an_already_generated_house_is_rejected(self) -> None:
        selected = select_pilot_houses(POOL, freeze())
        with self.assertRaises(LeanPilotError):
            validate_pilot_receipt(pilot_receipt(), already_generated=selected[:1])

    def test_an_extra_receipt_field_is_rejected(self) -> None:
        row = dict(pilot_receipt())
        row["notes"] = "looked fine"
        with self.assertRaises(LeanPilotError):
            validate_pilot_receipt(row)


class TestOccupancy(unittest.TestCase):
    def test_a_complete_reading_passes(self) -> None:
        validate_occupancy_receipt(occupancy())

    def test_an_average_instead_of_a_peak_is_rejected(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_occupancy_receipt(occupancy(statistic="mean_over_the_run"))

    def test_a_synthetic_microbenchmark_is_rejected(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_occupancy_receipt(occupancy(workload="a_synthetic_loop"))

    def test_a_reading_from_a_different_concurrency_is_rejected(self) -> None:
        with self.assertRaises(LeanPilotError):
            validate_occupancy_receipt(occupancy(concurrency_verified_at=1))

    def test_a_missing_value_is_rejected(self) -> None:
        row = dict(occupancy())
        del row["vram_gb_per_worker"]
        with self.assertRaises(LeanPilotError):
            validate_occupancy_receipt(row)


class TestScaleUp(unittest.TestCase):
    def test_the_derivation_reuses_the_s1_01_formula(self) -> None:
        plan = plan_scale_up(occupancy(simulator_concurrency_limit=64),
                             measurements(), headroom_fraction=0.2)
        direct = lean_assets.derive_worker_count(
            measurements(),
            {"cpu_cores_per_worker": 2.0, "ram_gb_per_worker": 6.0,
             "vram_gb_per_worker": 2.0, "disk_gb_per_worker": 1.5,
             "simulator_concurrency_limit": 64},
            headroom_fraction=0.2)
        self.assertEqual(plan["worker_count"], direct["worker_count"])
        self.assertEqual(plan["binding_constraint"], direct["binding_constraint"])

    def test_a_count_above_the_verified_concurrency_is_flagged(self) -> None:
        plan = plan_scale_up(occupancy(simulator_concurrency_limit=64),
                             measurements(), headroom_fraction=0.2)
        self.assertGreater(plan["worker_count"], plan["concurrency_verified_at"])
        self.assertTrue(plan["is_extrapolation"])

    def test_a_count_within_the_verified_concurrency_is_not_flagged(self) -> None:
        plan = plan_scale_up(occupancy(), measurements(), headroom_fraction=0.2)
        self.assertEqual(plan["worker_count"], 4)
        self.assertFalse(plan["is_extrapolation"])

    def test_the_frozen_headroom_bites(self) -> None:
        tight = occupancy(simulator_concurrency_limit=64)
        self.assertLess(
            plan_scale_up(tight, measurements(), headroom_fraction=0.2)["worker_count"],
            plan_scale_up(tight, measurements(), headroom_fraction=0.0)["worker_count"])

    def test_an_inadmissible_occupancy_cannot_be_derived_from(self) -> None:
        with self.assertRaises(LeanPilotError):
            plan_scale_up(occupancy(statistic="mean_over_the_run"),
                          measurements(), headroom_fraction=0.2)


class TestContract(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_contract_matches_this_implementation(self) -> None:
        checked = validate_pilot_contract(self.contract)
        self.assertEqual(checked["stage_id"], "S1-02a")

    def test_the_six_bits_are_open_under_the_ruling(self) -> None:
        self.assertTrue(all(self.contract["authorization"].values()))
        self.assertEqual(self.contract["activation_policy"]["opened_by"], "D-224-S1")

    def test_a_bit_outside_the_policy_is_rejected(self) -> None:
        opened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        opened["authorization"]["extra_bit"] = True
        with self.assertRaises(LeanPilotError):
            validate_pilot_contract(opened)

    def test_the_split_is_frozen_at_the_values_the_user_gave(self) -> None:
        frozen = self.contract["split_freeze"]
        self.assertEqual(frozen["seed"], 20260920)
        self.assertEqual(frozen["validation_houses"], 50)
        self.assertEqual(frozen["test_houses"], 100)
        self.assertEqual(frozen["frozen_by"], "D-224-S1")
        self.assertIs(frozen["is_the_single_registered_location"], True)
        for name in ("seed", "validation_houses", "test_houses"):
            self.assertNotIn(f"split_freeze.{name}",
                             self.contract["policy_values_without_defaults"])

    def test_the_train_size_stays_open_for_s3_01(self) -> None:
        self.assertIsNone(self.contract["split_freeze"]["train_houses"])
        self.assertIn("split_freeze.train_houses",
                      self.contract["policy_values_without_defaults"])

    def test_a_half_frozen_split_is_rejected(self) -> None:
        # The dangerous state: it looks decided, yet filling the missing one
        # still moves where the train block starts.
        for name in ("seed", "validation_houses", "test_houses"):
            half = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            half["split_freeze"][name] = None
            with self.assertRaises(LeanPilotError):
                validate_pilot_contract(half)

    def test_a_frozen_value_still_advertised_as_open_is_rejected(self) -> None:
        stale = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        stale["policy_values_without_defaults"].append("split_freeze.seed")
        with self.assertRaises(LeanPilotError):
            validate_pilot_contract(stale)

    def test_a_freeze_that_names_no_ruling_is_rejected(self) -> None:
        loose = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        del loose["split_freeze"]["frozen_by"]
        with self.assertRaises(LeanPilotError):
            validate_pilot_contract(loose)

    def test_the_contract_supersedes_its_reviewed_v1(self) -> None:
        import hashlib
        supersedes = self.contract["supersedes_contract"]
        self.assertTrue(supersedes["v1_bytes_frozen"])
        reviewed = PROJECT_ROOT / supersedes["path"]
        # By content, not by line endings: .gitattributes stores .json with
        # LF, so a Windows working tree can hold CRLF while every Linux
        # checkout holds LF.
        frozen = reviewed.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(frozen).hexdigest(),
                         supersedes["v1_sha256"])

    def test_the_frozen_split_determines_the_pilot(self) -> None:
        # With the split frozen the four houses follow from the pool alone;
        # reading that pool is still a closed bit.
        frozen = self.contract["split_freeze"]
        selected = select_pilot_houses(POOL, frozen)
        self.assertEqual(selected, select_pilot_houses(list(POOL), frozen))
        self.assertEqual(len(selected), 4)
        self.assertIs(self.contract["authorization"]["house_pool_read"], True)

    def test_dropping_the_pilot_from_the_fifty_is_rejected(self) -> None:
        sneaky = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        sneaky["pilot"]["counts_toward_the_development_fifty"] = False
        with self.assertRaises(LeanPilotError):
            validate_pilot_contract(sneaky)

    def test_allowing_regeneration_after_inspection_is_rejected(self) -> None:
        sneaky = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        sneaky["pilot"]["regeneration_after_inspection_forbidden"] = False
        with self.assertRaises(LeanPilotError):
            validate_pilot_contract(sneaky)

    def test_downgrading_peak_to_average_is_rejected(self) -> None:
        sneaky = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        sneaky["occupancy_measurement"]["statistic"] = "mean_over_the_run"
        with self.assertRaises(LeanPilotError):
            validate_pilot_contract(sneaky)

    def test_allowing_a_replacement_house_is_rejected(self) -> None:
        sneaky = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        sneaky["stop_conditions"]["may_replace_a_failed_house"] = True
        with self.assertRaises(LeanPilotError):
            validate_pilot_contract(sneaky)

    def test_the_failure_reasons_are_exactly_s0_02s(self) -> None:
        self.assertEqual(tuple(self.contract["failure_reasons"]),
                         lean_intervention.FAILURE_REASONS)

    def test_the_contract_consumes_the_v2_contracts(self) -> None:
        depends = self.contract["depends_on"]
        self.assertTrue(depends["s0_02_contract"].endswith("_v2.json"))
        self.assertTrue(depends["s1_01_contract"].endswith("_v2.json"))
        for key in ("s0_02_contract", "s1_01_contract"):
            self.assertTrue((PROJECT_ROOT / depends[key]).exists(), key)

    def test_the_module_starts_nothing_and_writes_nothing(self) -> None:
        source = (SRC_ROOT / "vsmt" / "lean_pilot.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertEqual(imported, {"__future__", "typing", "cpmt.hashing",
                                    "vsmt.lean_assets", "vsmt.lean_intervention"})
        called = {node.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        for forbidden in ("open", "eval", "exec", "__import__"):
            self.assertNotIn(forbidden, called, forbidden)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
