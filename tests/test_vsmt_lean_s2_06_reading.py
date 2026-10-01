"""S2-06 tests: the ruling 100-3 reading, and the 82-1 comparison generalised to any two arms without changing its default output.

Pinned: (1) the committed instance-segmentation development reading (ruling 96, LOG-295) is reproduced field for field from
the committed merged audits it names -- so the generalised 82-1 code and ruling95_reading are unchanged in effect; (2) VSMT-lean
against NoVersion reads by the same 82-1 rule with orders named after the two arms and no gate; (3) on hand-made audits the
SAM2 and instance-segmentation classifications are set side by side; (4) a SAM2 input naming another mask source, or a
recomputation that differs from the committed reading, is refused.  CPU only, seconds.
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

import ruling82_seed_analysis as r82  # noqa: E402
import s2_06_reading as reading  # noqa: E402

RESULTS = PROJECT_ROOT / "results"
SEEDS = (7, 19, 31, 43, 59)
RULE_ARMS = ("TAF", "ELU-P", "RAC", "LOW")
HOUSES = [f"h{i:02d}" for i in range(10)]


def committed_instance_inputs() -> tuple[dict, dict, dict]:
    committed = json.loads((RESULTS / "vsmt_lean_ruling96_reading_7c76970.json").read_text(encoding="utf-8"))
    groups, rule_arms = {}, {}
    for key, spec in committed["inputs"].items():
        payload = json.loads((RESULTS / spec["file"]).read_text(encoding="utf-8"))
        if ":" in key:
            arm, seed = key.split(":")
            groups[(arm, int(seed))] = payload
        else:
            rule_arms[key] = payload
    return groups, rule_arms, committed


def merged(*, f1=0.8, mrr=0.3, identity=0.5, source="sam2"):
    report = {"node_prf1": {"node_f1": f1}, "node_prf1_iou": {"node_f1": f1 / 2}, "missing_residual_rate": {"missing_residual_rate": mrr},
              "identity_continuity": {"identity_continuity": identity}, "contamination_auc": {"contamination_auc": 0.4},
              "recovery_latency_frames": {"recovery_latency_frames": 100.0}, "false_retract_rate_in_scope": {"false_retract_rate": 0.3},
              "false_retract_rate": {"false_retract_rate": 0.3}}
    return {"mask_source": source, "per_episode": [{"episode_id": h, "report": report} for h in HOUSES], "pooled_loss_tally": {}}


def front(source: str, vsmt_mrr, assoc_mrr, noversion_identity):
    groups = {}
    for i, seed in enumerate(SEEDS):
        groups[("VSMT-lean", seed)] = merged(mrr=vsmt_mrr[i], source=source)
        groups[("AssocOnly", seed)] = merged(mrr=assoc_mrr[i], source=source)
        groups[("NoVersion", seed)] = merged(mrr=vsmt_mrr[i], identity=noversion_identity[i], source=source)
    rule_arms = {arm: merged(mrr=m, source=source) for arm, m in zip(RULE_ARMS, (0.7, 0.1, 0.09, 0.3))}
    return {"groups": groups, "rule_arms": rule_arms}


class TestTheCommittedInstanceReadingIsReproduced(unittest.TestCase):
    def test_the_ruling_96_reading_is_recomputed_field_for_field(self) -> None:
        groups, rule_arms, committed = committed_instance_inputs()
        groups.update({("NoVersion", seed): groups[("VSMT-lean", seed)] for seed in SEEDS})  # a stand-in: only AssocOnly is compared
        instance = {"groups": groups, "rule_arms": rule_arms}
        result = reading.read(instance, instance, committed)
        self.assertEqual(result["instance_reading_check"]["reproduced_fields"], list(reading.COMPARED_FIELDS))
        self.assertEqual(result["classification_95_3"]["simulator_instance_masks"], "gain_shown_on_development")
        broken = copy.deepcopy(committed)
        broken["rule_85_4"]["ratio"] += 0.01
        with self.assertRaises(ValueError) as caught:
            reading.read(instance, instance, broken)
        self.assertEqual(str(caught.exception), "instance_reading_not_reproduced:rule_85_4")


class TestTwoArmGeneralisation(unittest.TestCase):
    def test_the_default_output_is_the_old_one_and_other_arms_are_named(self) -> None:
        sam2 = front("sam2", [0.10, 0.12, 0.11, 0.13, 0.12], [0.30, 0.32, 0.31, 0.29, 0.33], [0.40, 0.41, 0.39, 0.42, 0.40])
        default = r82.analyse({k: v for k, v in sam2["groups"].items() if k[0] != "NoVersion"})
        self.assertNotIn("arms", default)
        self.assertEqual(default["rule"], r82.RULE)
        version = r82.analyse({k: v for k, v in sam2["groups"].items() if k[0] != "AssocOnly"}, arms=("VSMT-lean", "NoVersion"))
        self.assertEqual(version["arms"], ["VSMT-lean", "NoVersion"])
        self.assertIn("VSMT-lean and NoVersion", version["rule"])
        self.assertEqual(version["summary"]["identity_continuity"], "VSMT-lean_better")  # 0.5 against about 0.40 at every seed
        self.assertEqual(version["summary"]["missing_residual_rate"], "not_distinguishable_on_the_development_set")  # equal
        with self.assertRaises(ValueError):
            r82.analyse({k: v for k, v in sam2["groups"].items() if k != ("NoVersion", 59)}, arms=("VSMT-lean", "NoVersion"))


class TestS206Reading(unittest.TestCase):
    def test_both_front_ends_are_read_by_the_same_rules_side_by_side(self) -> None:
        sam2 = front("sam2", [0.10, 0.12, 0.11, 0.13, 0.12], [0.30, 0.32, 0.31, 0.29, 0.33], [0.40, 0.41, 0.39, 0.42, 0.40])
        instance = front("simulator_instance_masks", [0.20, 0.40, 0.25, 0.35, 0.30], [0.3] * 5, [0.5] * 5)
        result = reading.read(sam2, instance, None)
        self.assertEqual(result["classification_95_3"], {"sam2": "gain_shown_on_development",
                                                         "simulator_instance_masks": "no_gain_shown_on_development"})
        self.assertFalse(result["classification_matches_instance_segmentation"])
        self.assertEqual(result["orders_vs_no_version_report_only"]["sam2"]["identity_continuity"], "VSMT-lean_better")
        self.assertEqual(result["rule_85_4"]["sam2"]["best_rule_arm"], "RAC")
        row = result["side_by_side"]["missing_residual_rate"]["sam2"]
        self.assertAlmostEqual(row["five_seed_mean"]["VSMT-lean"], 0.116)
        self.assertEqual(row["rule_arm_house_mean"]["RAC"], 0.09)
        self.assertEqual(row["order_vs_assoc_only"], "VSMT-lean_better")
        self.assertIsNone(result["instance_reading_check"])

    def test_inputs_of_the_wrong_mask_source_are_refused(self) -> None:
        sam2 = front("sam2", [0.1] * 5, [0.3] * 5, [0.4] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = []
            for (arm, seed), payload in sam2["groups"].items():
                path = root / f"s-{arm}-{seed}.json"
                payload = {**payload, "mask_source": "simulator_instance_masks"} if (arm, seed) == ("NoVersion", 7) else payload
                path.write_text(json.dumps(payload), encoding="utf-8")
                args += ["--sam2-group", f"{arm}:{seed}:{path}", "--instance-group", f"{arm}:{seed}:{path}"]
            for arm, payload in sam2["rule_arms"].items():
                path = root / f"r-{arm}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                args += ["--sam2-rule-arm", f"{arm}:{path}", "--instance-rule-arm", f"{arm}:{path}"]
            self.assertEqual(reading.main(args + ["--output", str(root / "out.json")]), 2)


if __name__ == "__main__":
    unittest.main()
