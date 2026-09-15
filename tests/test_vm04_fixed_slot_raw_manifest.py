"""Original slot join and sealed public/private task boundary."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_fixed_slot_raw_manifest as manifest


def fixtures():
    programs = ["NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK",
                "RETRACT", "SPLIT", "MERGE", "REPLACE"]
    public, private, viewpoints, endpoint = [], [], {}, {}
    houses = []
    for family, house_id in manifest.raw_worker.HOUSE_BY_FAMILY.items():
        houses.append({"house_id": house_id,
                       "source_locator": {"relative_path": "train.jsonl.gz",
                                          "index": len(houses)},
                       "source_record_sha256": "a" * 64})
        poses = [{"position": {"x": float(slot), "y": 0.9, "z": 0.0},
                  "rotation_y_degrees": 0, "horizon_degrees": 0,
                  "standing": True} for slot in range(18)]
        viewpoints[family] = ({"selected_pose_rank_indices": list(range(18)),
                               "ranked_poses": poses}, "b" * 64)
        relink_slots = manifest.raw_worker.ORIGINAL_RELINK_SLOTS[family]
        rest = [slot for slot in range(18) if slot not in relink_slots]
        assignments = [(program, replicate) for program in programs
                       if program != "RELINK" for replicate in (0, 1)]
        by_slot = dict(zip(rest, assignments))
        by_slot.update({slot: ("RELINK", replicate)
                        for replicate, slot in enumerate(relink_slots)})
        for slot in range(18):
            program, replicate = by_slot[slot]
            episode_id = "%s-episode-%02d" % (family, slot)
            public.append({"family_id": family, "slot": slot,
                           "episode_id": episode_id})
            private.append({"episode_id": episode_id,
                            "source_house_id": house_id,
                            "program": program, "replicate": replicate})
            if program == "RELINK":
                endpoint[(family, slot)] = {
                    "endpoint_verdict": {
                        "status": "simulator_endpoint_collision_rejected"},
                    "trial": {"target_object_id": "secret-object-%s-%02d" %
                              (family, slot),
                              "registered_request": {"objectId":
                                  "secret-object-%s-%02d" % (family, slot)}},
                    "private_slot_sha256": "c" * 64,
                    "semantic_positive_label_issued": False,
                }
    return ({"public": {"episodes": public},
             "private": {"assignments": private}},
            viewpoints, {"houses": houses}, endpoint)


class FixedSlotManifestTests(unittest.TestCase):
    def test_seals_36_original_slots_without_exporting_private_ids(self):
        plans, viewpoints, inventory, endpoint = fixtures()
        tasks = manifest.build_tasks(plans, viewpoints, inventory,
                                     endpoint, manifest.audit.read_json(
                                         manifest.CONFIG)[
                                             "source_d173_endpoint_receipt_sha256"])
        self.assertEqual(len(tasks), 36)
        self.assertEqual([(task["family_id"], task["slot"])
                          for task in tasks if task["program"] == "RELINK"],
                         [("audit-family:00", 4), ("audit-family:00", 11),
                          ("audit-family:01", 6), ("audit-family:01", 12)])
        with TemporaryDirectory() as temp:
            root = Path(temp) / "tasks"
            rows = manifest.seal(tasks, {
                "source_scan_receipt_sha256": "e" * 64,
                "source_endpoint_receipt_sha256": "d" * 64}, root)
            self.assertEqual(len(rows), 36)
            public = json.loads((root / "public/task-manifest.json").read_text())
            self.assertEqual(public["slot_count"], 36)
            self.assertFalse(public["private_ids_exported"])
            self.assertNotIn("secret-object", (root /
                "public/task-manifest.json").read_text())
            self.assertIn("secret-object", (root /
                "private/audit-family_00/slot_04.json").read_text())
            with self.assertRaisesRegex(ValueError, "task root exists"):
                manifest.seal(tasks, {}, root)

    def test_missing_original_endpoint_blocks_all_task_writes(self):
        plans, viewpoints, inventory, endpoint = fixtures()
        del endpoint[("audit-family:00", 4)]
        with self.assertRaisesRegex(ValueError, "collision evidence"):
            manifest.build_tasks(plans, viewpoints, inventory,
                                 endpoint, "d" * 64)


if __name__ == "__main__":
    unittest.main()
