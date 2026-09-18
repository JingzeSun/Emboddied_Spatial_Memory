import json
from pathlib import Path
import unittest

import numpy as np

from vsmt.d210_place_memory import validate_contract
from vsmt.d211_p0_smoke import seal_reachable_scan, validate_d211_contract
from vsmt.d212_route_survey import (
    build_route_bundle_row,
    plan_route_from_reachable_scan,
    public_frame_descriptor,
    public_region_refs,
)


ROOT = Path(__file__).resolve().parents[1]


class D212RouteSurveyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = validate_contract(json.loads((
            ROOT / "configs/vsmt/vm04_d210_dual_layer_p0_v1.json"
        ).read_text(encoding="utf-8")))
        cls.overlay = validate_d211_contract(json.loads((
            ROOT / "configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json"
        ).read_text(encoding="utf-8")), base_contract=cls.base)

    def scan(self, house_slot):
        source = self.overlay["source_binding"]["houses"][house_slot]
        return seal_reachable_scan(
            house_slot=house_slot,
            source_house_id=source["source_house_id"],
            raw_positions=[
                {"x": x * .25, "y": .9, "z": z * .25}
                for x in range(-16, 17) for z in range(-16, 17)
            ], contract=self.overlay, base_contract=self.base)

    def observations(self, planned):
        route = planned["route_plan"]
        annotations = planned["provisional_annotations"]
        rows = []
        for index in range(route["observation_count"]):
            role = "unknown"
            refs = []
            if route["scenario_id"] == "P08":
                if index in annotations["room_anchor_observation_indices"]:
                    role, refs = "room", [f"region:{index:024x}"]
                elif index in annotations["corridor_observation_indices"]:
                    role = "corridor"
            rows.append({
                "observation_index": index,
                "rgb_sha256": f"{index % 16:x}" * 64,
                "depth_sha256": f"{(index + 1) % 16:x}" * 64,
                "calibration_sha256": "e" * 64,
                "place_descriptor": [1.0, float(index + 1),
                                     float((index % 3) + 1)],
                "public_region_role": role,
                "visible_entity_region_refs": refs,
            })
        return rows

    def test_all_twelve_fixed_slots_plan_and_recompute(self):
        for slot_spec in self.base["slot_plan"]:
            scan = self.scan(slot_spec["house_slot"])
            planned = plan_route_from_reachable_scan(
                slot=slot_spec["slot"], reachable_scan=scan,
                contract=self.overlay, base_contract=self.base)
            row = build_route_bundle_row(
                planned=planned, reachable_scan=scan,
                public_observations=self.observations(planned),
                contract=self.overlay, base_contract=self.base)
            self.assertEqual(slot_spec["slot"], row["route_plan"]["slot"])
            self.assertLessEqual(row["route_plan"]["planned_action_count"], 128)
            self.assertTrue(row["execution_binding"][
                "all_planned_translation_endpoints_preverified_reachable"])

    def test_descriptor_and_region_proposals_use_only_rgbd_arrays(self):
        rgb = np.arange(12 * 16 * 3, dtype=np.uint8).reshape(12, 16, 3)
        depth = np.linspace(.2, 4.0, 12 * 16, dtype=np.float32).reshape(12, 16)
        descriptor = public_frame_descriptor(rgb, depth)
        refs = public_region_refs(rgb, depth)
        self.assertEqual(16, len(descriptor))
        self.assertAlmostEqual(1.0, sum(value * value for value in descriptor),
                               places=6)
        self.assertTrue(refs)
        self.assertTrue(all(ref.startswith("region:") for ref in refs))

    def test_figure_eight_uses_scan_relative_cells_on_offset_grid(self):
        source = self.overlay["source_binding"]["houses"][0]
        scan = seal_reachable_scan(
            house_slot=0, source_house_id=source["source_house_id"],
            raw_positions=[
                {"x": .125 + x * .25, "y": .9, "z": -.125 + z * .25}
                for x in range(-10, 11) for z in range(-10, 11)
            ], contract=self.overlay, base_contract=self.base)
        planned = plan_route_from_reachable_scan(
            slot=9, reachable_scan=scan, contract=self.overlay,
            base_contract=self.base)
        row = build_route_bundle_row(
            planned=planned, reachable_scan=scan,
            public_observations=self.observations(planned),
            contract=self.overlay, base_contract=self.base)
        self.assertEqual(0, row["scenario_receipt"]["derived_facts"]
                         ["noncenter_overlap_count"])


if __name__ == "__main__":
    unittest.main()
