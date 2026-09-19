from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OPS = ROOT / "ops/vsmt"
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d223_f00_topology_precheck import (  # noqa: E402
    D223F00Error,
    analyze_reachable_topology,
    assert_real_precheck_authorized,
    make_private_failure,
    make_public_summary,
    validate_f00_contract,
)
import vm04_d223_f00_topology_precheck as stage  # noqa: E402
import vm04_d223_f00_worker as worker  # noqa: E402


F00_PATH = ROOT / "configs/vsmt/vm04_d223_f00_topology_precheck_v1.json"
D223_PATH = ROOT / "configs/vsmt/vm04_d223_p08_topological_qualification_v1.json"
D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D211_PATH = ROOT / "configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dumbbell():
    cells = ({(x, z) for x in range(-12, -3) for z in range(-4, 5)} |
             {(x, z) for x in range(-3, 4) for z in (0, 1)} |
             {(x, z) for x in range(4, 13) for z in range(-4, 5)})
    return [{"x": x * 0.25, "y": 0.0, "z": z * 0.25}
            for x, z in sorted(cells)]


def _open_basin():
    return [{"x": x * 0.25, "y": 0.0, "z": z * 0.25}
            for x in range(-4, 5) for z in range(-4, 5)]


class _Event:
    def __init__(self, positions):
        self.metadata = {"lastActionSuccess": True, "actionReturn": positions}


class _Controller:
    def __init__(self, positions):
        self.positions = positions
        self.stopped = False

    def step(self, **request):
        if request != {"action": "GetReachablePositions"}:
            raise AssertionError("F-00 worker attempted a non-reachability action")
        return _Event(self.positions)

    def stop(self):
        self.stopped = True


class D223F00TopologyPrecheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f00 = _load(F00_PATH)
        cls.d223 = _load(D223_PATH)
        cls.d215 = validate_d215_contract(_load(D215_PATH))
        cls.d211 = _load(D211_PATH)

    def test_completed_contract_records_result_and_closes_execution(self):
        validated = validate_f00_contract(
            self.f00, d223_contract=self.d223, d215_contract=self.d215,
            d211_contract=self.d211)
        self.assertEqual("approved_design_all_execution_closed",
                         self.d223["status"])
        self.assertFalse(any(validated["authorization"].values()))
        self.assertEqual(1, validated["completion"]["real_run_count"])
        self.assertTrue(validated["completion"]["continue_to_f01"])
        with self.assertRaisesRegex(D223F00Error, "pending code review"):
            assert_real_precheck_authorized(validated)

        active = deepcopy(validated)
        active["status"] = active["activation_policy"]["active_status"]
        active["authorization"]["real_two_house_topology_precheck"] = True
        active["completion"] = None
        validate_f00_contract(
            active, d223_contract=self.d223, d215_contract=self.d215,
            d211_contract=self.d211)
        assert_real_precheck_authorized(active)

        changed = deepcopy(validated)
        changed["authorization"]["route_or_raw_generation"] = True
        with self.assertRaisesRegex(D223F00Error, "completed state"):
            validate_f00_contract(
                changed, d223_contract=self.d223, d215_contract=self.d215,
                d211_contract=self.d211)

    def test_positive_signature_uses_two_distinct_basins_and_is_deterministic(self):
        first = analyze_reachable_topology(
            _dumbbell(), house_slot=0, source_house_id="fixture:0",
            source_record_sha256="a" * 64)
        second = analyze_reachable_topology(
            list(reversed(_dumbbell())), house_slot=0,
            source_house_id="fixture:0", source_record_sha256="a" * 64)
        self.assertEqual(first, second)
        self.assertTrue(first["qualifying_path_exists"])
        self.assertGreaterEqual(first["qualifying_signature_count"], 1)
        labels = [row["structural_label"]
                  for row in first["selected_witness_path"]]
        self.assertEqual("basin", labels[0])
        self.assertEqual("basin", labels[-1])
        self.assertTrue(all(label == "bottleneck" for label in labels[1:-1]))
        self.assertEqual(0, first["new_numeric_parameters"])

    def test_open_area_has_no_bottleneck_signature(self):
        receipt = analyze_reachable_topology(
            _open_basin(), house_slot=0, source_house_id="fixture:0",
            source_record_sha256="a" * 64)
        self.assertFalse(receipt["qualifying_path_exists"])
        self.assertEqual(0, receipt["qualifying_signature_count"])
        self.assertEqual([], receipt["selected_witness_path"])

    def test_same_basin_on_both_sides_cannot_form_a_signature(self):
        positions = [
            {"x": x * 0.25, "y": 0.0, "z": z * 0.25}
            for x, z in ((-1, 0), (-1, 1), (0, 0), (0, 1),
                         (1, 0), (1, 1))]

        def label(_positions, anchor):
            return ("bottleneck" if anchor["x"] == 0.0 and
                    anchor["z"] == 0.0 else "basin")

        with patch("vsmt.d223_f00_topology_precheck."
                   "structural_label_from_reachable", side_effect=label):
            receipt = analyze_reachable_topology(
                positions, house_slot=0, source_house_id="fixture:0",
                source_record_sha256="a" * 64)
        self.assertEqual(1, receipt["connected_component_counts"]["basin"])
        self.assertFalse(receipt["qualifying_path_exists"])

    def test_malformed_or_colliding_reachable_positions_are_rejected(self):
        with self.assertRaisesRegex(D223F00Error, "non-finite"):
            analyze_reachable_topology(
                [{"x": float("nan"), "y": 0, "z": 0}], house_slot=0,
                source_house_id="fixture:0", source_record_sha256="a" * 64)
        with self.assertRaisesRegex(D223F00Error, "collide"):
            analyze_reachable_topology(
                [{"x": 0.0, "y": 0, "z": 0},
                 {"x": 0.01, "y": 0, "z": 0}], house_slot=0,
                source_house_id="fixture:0", source_record_sha256="a" * 64)

    def test_public_summary_omits_house_identity_positions_and_failure_message(self):
        success = analyze_reachable_topology(
            _dumbbell(), house_slot=0, source_house_id="secret-house-0",
            source_record_sha256="a" * 64)
        failure = make_private_failure(
            house_slot=1, source_house_id="secret-house-1",
            source_record_sha256="b" * 64, error_type="RuntimeError",
            message="secret simulator failure")
        summary = make_public_summary(
            [success, failure], requested_worker_count=2,
            actual_worker_count=2, resource_basis={"logical_cpu_count": 8},
            execution_commit="c" * 40)
        encoded = canonical_json(summary)
        self.assertNotIn("secret-house", encoded)
        self.assertNotIn('"selected_witness_path"', encoded)
        self.assertNotIn('"position_labels"', encoded)
        self.assertNotIn('"source_house_id"', encoded)
        self.assertNotIn("simulator failure", encoded)
        self.assertFalse(summary["continue_to_f01"])
        self.assertEqual(["success", "failure"],
                         [row["status"] for row in summary["houses"]])

    def test_worker_reads_only_reachable_metadata_and_stops_controller(self):
        controller = _Controller(_dumbbell())
        row = {
            "house_slot": 0, "source_house_id": "fixture:0",
            "source_record_sha256": "a" * 64,
            "source_locator": {"relative_path": "unused", "index": 0},
        }
        house = {"fixture": True}
        from hashlib import sha256
        row["source_record_sha256"] = sha256(
            canonical_json(house).encode("utf-8")).hexdigest()
        with patch.object(worker.source_worker, "load_source_record",
                          return_value=house), patch.object(
                              worker, "_make_controller",
                              return_value=controller):
            receipt = worker.precheck_house({
                "row": row, "source_root": "unused", "contract": self.f00})
        self.assertTrue(controller.stopped)
        self.assertTrue(receipt["qualifying_path_exists"])
        self.assertFalse(receipt["rgb_depth_or_instance_arrays_read_or_saved"])

    def test_stage_rejects_run_before_reading_paths_or_writing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "must-not-exist"
            with self.assertRaisesRegex(D223F00Error, "pending code review"):
                stage.run(
                    source_inventory_path=root / "missing-inventory.json",
                    source_root=root / "missing-source", output_root=output)
            self.assertFalse(output.exists())

    def test_check_cli_neither_queries_simulator_nor_writes_outputs(self):
        result = subprocess.run(
            [sys.executable, str(OPS / "vm04_d223_f00_topology_precheck.py"),
             "check"], cwd=ROOT, text=True, capture_output=True, check=True)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["real_simulator_queried"])
        self.assertFalse(payload["outputs_written"])
        self.assertFalse(any(payload["authorization"].values()))


if __name__ == "__main__":
    unittest.main()
