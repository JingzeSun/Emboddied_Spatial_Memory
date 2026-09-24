"""D-224 / S2-05 tests: the read-only node-matching audit over the S2-04 synthetic episode.

Pinned on the five-frame TAF episode of the S2-04 tests (a mug removed and a book moved after the
window, a structural wall): the audit reproduces the evaluator's per-frame node counts under the
current rule, its entity and truth categories partition the predicted and truth totals, the stale
mug entity is counted as such on every frame after the window, the oracle identity grouping never
scores below the current rule, the merged report pools two audits, and a labelled record the
evaluator would disagree with is refused.  CPU only, seconds.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_node_audit as audit_module  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402
from test_vsmt_lean_evaluation import NUISANCE_META, TEACHER_POLICY, episode  # noqa: E402
from test_vsmt_lean_runner import CONFIGS, POLICY  # noqa: E402


def run_audit(arm: str = "TAF"):
    data = episode()
    teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
    captured = audit_module.capture_truth_table(teacher)
    audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"],
                                   groups=audit_module.object_groups(data["table"]))
    frames = []
    labelled_frames = []
    for i, step in enumerate(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=CONFIGS[arm], policy=POLICY, descriptor="vitb14")):
        labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                       label_image=data["images"][i], runtime_s=0.01, peak_memory_bytes=1000)
        labelled_frames.append(labelled)
        frames.append(audit.observe(step, labelled, captured["table"]))
    return audit, frames, labelled_frames, teacher.episode_report()


class NodeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit, cls.frames, cls.labelled, cls.episode = run_audit("TAF")
        cls.report = cls.audit.report()

    def test_the_current_rule_reproduces_the_evaluator_and_the_categories_partition_the_totals(self) -> None:
        current = self.report["rules"]["iou_0.3_current"]
        self.assertEqual({k: current[k] for k in ("matched", "predicted", "truth")}, {"matched": 7, "predicted": 10, "truth": 7})
        self.assertEqual(current["f1"], self.episode["report"]["node_prf1"]["node_f1"])
        self.assertEqual(sum(self.report["entity_categories"].values()), 10)
        self.assertEqual(sum(self.report["truth_categories"].values()), 7)
        for frame, labelled in zip(self.frames, self.labelled, strict=True):
            self.assertEqual(frame["rules"]["iou_0.3_current"]["matched"], labelled["node_prf1"]["matched"])
            self.assertEqual(frame["rules"]["centroid_within_0.5m"]["matched"], labelled["node_prf1_centroid"]["matched"])  # ruling 70 column
            self.assertEqual(sum(frame["entity"].values()), labelled["node_prf1"]["predicted"])
            self.assertEqual(sum(frame["truth"].values()), labelled["node_prf1"]["truth"])

    def test_the_stale_mug_entity_is_counted_after_the_window_and_nothing_else_is_lost(self) -> None:
        # TAF never retracts: the mug's entity stays in memory on frames 2-4 while the mug is gone
        self.assertEqual([f["entity"]["own_object_absent_stale"] for f in self.frames], [0, 0, 1, 1, 1])
        self.assertEqual(self.report["entity_categories"]["matched"], 7)
        self.assertEqual(self.report["truth_categories"], {**{name: 0 for name in audit_module.TRUTH_CATEGORIES}, "matched": 7})
        self.assertEqual(self.report["truth_by_group"], {"pickupable": {**{name: 0 for name in audit_module.TRUTH_CATEGORIES}, "matched": 7}})
        self.assertEqual(set(self.report["truth_by_type"]), {"Mug", "Book"})
        # the wall's entity resolves to a present structural key: out of scope, not a prediction
        self.assertEqual(self.report["out_of_scope_entities_per_frame_mean"], 1.0)

    def test_alternative_rules_are_scored_on_the_same_sets_and_the_oracle_grouping_is_an_upper_bound(self) -> None:
        rules = self.report["rules"]
        for rule in audit_module.RULES:
            self.assertEqual(rules[rule]["truth"], 7, rule)
            self.assertLessEqual(rules[rule]["matched"], rules[rule]["truth"], rule)
        self.assertGreaterEqual(rules["iou_0.1"]["matched"], rules["iou_0.3_current"]["matched"])
        self.assertGreaterEqual(rules["iou_positive"]["matched"], rules["iou_0.1"]["matched"])
        self.assertGreaterEqual(rules["oracle_identity_groups_iou_0.3"]["matched"], rules["iou_0.3_current"]["matched"])
        self.assertLessEqual(rules["oracle_identity_groups_iou_0.3"]["predicted"], rules["iou_0.3_current"]["predicted"])
        self.assertEqual(len(self.report["rule_matched_per_frame"]["centroid_within_0.5m"]), 5)

    def test_a_labelled_record_the_evaluator_would_disagree_with_is_refused(self) -> None:
        data = episode()
        teacher = ev.EpisodeTeacher(arm="TAF", geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                    policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
        captured = audit_module.capture_truth_table(teacher)
        audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"])
        step = next(iter(lr.run_episode(data["frames"][:1], episode_id="ep-0001", arm="TAF", config=CONFIGS["TAF"], policy=POLICY, descriptor="vitb14")))
        labelled = teacher.label_frame(step, cache_frame=data["frames"][0], private_record=data["records"][0], masks=data["masks"][0],
                                       label_image=data["images"][0], runtime_s=0.01, peak_memory_bytes=1000)
        broken = copy.deepcopy(labelled)
        broken["node_prf1"]["matched"] += 1
        with self.assertRaises(audit_module.NodeAuditError) as caught:
            audit.observe(step, broken, captured["table"])
        self.assertEqual(str(caught.exception), "audit_disagrees_with_the_labels:matched")

    def test_merge_pools_two_audits_and_refuses_an_empty_root(self) -> None:
        payload = {"schema_version": audit_module.SCHEMA_VERSION, "arm": "TAF", "code_commit": "abc", "episode_id": "ep-0001",
                   "frames": 5, "config": CONFIGS["TAF"], "final_entities_by_state": {"active": 3}, "audit": self.report}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("ep-0001", "ep-0002"):
                (root / name / "TAF").mkdir(parents=True)
                (root / name / "TAF" / audit_module.AUDIT_FILE_NAME).write_text(json.dumps({**payload, "episode_id": name}), encoding="utf-8")
            merged = audit_module.merge_audits(root, "TAF")
            self.assertEqual(merged["episodes"], 2)
            self.assertEqual(merged["pooled_rules"]["iou_0.3_current"], {**merged["pooled_rules"]["iou_0.3_current"], "matched": 14, "predicted": 20, "truth": 14})
            self.assertEqual(merged["pooled_entity_categories"]["own_object_absent_stale"], 6)
            self.assertFalse(merged["private_ids_exported"])
            with self.assertRaises(audit_module.NodeAuditError):
                audit_module.merge_audits(root, "LOW")


if __name__ == "__main__":
    unittest.main()
