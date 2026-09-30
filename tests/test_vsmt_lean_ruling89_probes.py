"""Ruling 89-2 / 89-3 probes: rule decisions as functions of the extended existence row, the same-input check, event coverage
and the checks reading."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt", ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_assignment as la  # noqa: E402

import ruling89_checks as checks  # noqa: E402
import ruling89_probes as probes  # noqa: E402


def row(entity_id: str, **values: float) -> dict:
    features = {name: 0.0 for name in la.EXISTENCE_FEATURES}
    features["state_is_active"] = 1.0
    features.update(values)
    return {"entity_id": entity_id, "features": [features[name] for name in la.EXISTENCE_FEATURES]}


def f_of(r: dict) -> dict:
    return probes.row_values(r["features"], la.EXISTENCE_FEATURES)


class RuleTests(unittest.TestCase):
    def test_rac_counts_this_frame_and_retracts_at_n(self) -> None:
        self.assertEqual(probes.rac_decision(f_of(row("a", free_space_coverage_ratio=0.7, rac_run_rho_070=2.0)), 0.7, 3), "RETRACT")
        self.assertEqual(probes.rac_decision(f_of(row("a", free_space_coverage_ratio=0.7, rac_run_rho_070=1.0)), 0.7, 3), "NOOP")
        self.assertEqual(probes.rac_decision(f_of(row("a", free_space_coverage_ratio=0.6, rac_run_rho_070=9.0)), 0.7, 3), "NOOP")
        self.assertEqual(probes.rac_decision(f_of(row("a", free_space_coverage_ratio=0.9, rac_run_rho_085=1.0)), 0.85, 2), "RETRACT")

    def test_elu_p_is_the_linear_log_odds(self) -> None:
        values = {"initial_log_odds": 1.0, "match_gain": 0.5, "persistence_log_decay_per_tick": 0.1, "free_space_weight": 1.0,
                  "retract_threshold": 0.0}
        # 1.0 + 0.5*2 - 0.1*(3+1) - 1.0*(1.2+0.5) = -0.1 -> RETRACT
        f = f_of(row("a", matches_since_birth=2.0, eligible_frames_since_birth=3.0, free_space_coverage_sum_since_birth=1.2,
                     free_space_coverage_ratio=0.5))
        self.assertEqual(probes.elu_p_decision(f, values), "RETRACT")
        f = f_of(row("a", matches_since_birth=3.0, eligible_frames_since_birth=3.0, free_space_coverage_sum_since_birth=1.2,
                     free_space_coverage_ratio=0.5))
        self.assertEqual(probes.elu_p_decision(f, values), "NOOP")

    def test_the_order_must_be_the_ruling_89_order(self) -> None:
        with self.assertRaises(ValueError):
            probes.row_values([0.0] * 12, la.LEGACY_EXISTENCE_FEATURES)


class SameInputTests(unittest.TestCase):
    def test_functions_of_the_row_never_give_two_answers(self) -> None:
        order = list(la.EXISTENCE_FEATURES)
        records = [{"existence_feature_order": order,
                    "existence_rows": [row("a", free_space_coverage_ratio=0.9, rac_run_rho_070=4.0, rac_run_rho_085=4.0),
                                       row("b", free_space_coverage_ratio=0.9, rac_run_rho_070=4.0, rac_run_rho_085=4.0),
                                       row("c", free_space_coverage_ratio=0.1)]}]
        report = probes.same_input_report(records)
        self.assertTrue(report["pass"])
        self.assertEqual(report["rows"], 3)
        self.assertEqual(report["per_rule"]["rac_rho0.7_n3"]["distinct_inputs"], 2)
        self.assertEqual(report["per_rule"]["rac_rho0.7_n3"]["inputs_with_a_retract"], 1)


class CoverageEventTests(unittest.TestCase):
    def test_a_spell_is_one_event_whatever_its_length(self) -> None:
        names = list(la.ASSOCIATION_FEATURES)

        def assoc(ticks: float, state: str) -> list:
            f = {n: 0.0 for n in names}
            f["ticks_since_last_seen"] = ticks
            f[f"state_is_{state}"] = 1.0
            return [f[n] for n in names]

        rows = []
        for tick, ticks in ((10, 4.0), (11, 5.0), (12, 6.0)):  # one dormant spell starting at tick 6
            rows.append(("p0:ELU-P", "house-1", {"tick": tick, "stage_a": {"association_rows": [
                {"fragment_id": "f", "entity_id": "e1", "features": assoc(ticks, "dormant")}]},
                "targets": {"f": {"status": "labelled", "target": "e1"}}}))
        rows.append(("p0:ELU-P", "house-2", {"tick": 30, "stage_a": {"association_rows": [
            {"fragment_id": "f", "entity_id": "e9", "features": assoc(20.0, "retracted")}]},
            "targets": {"f": {"status": "labelled", "target": "e9"}}}))
        report = probes.coverage_events({"train": rows, "selection": []})
        self.assertEqual(report["train"]["dormant"], {"events": 1, "houses": 1, "labelled_target_rows": 3})
        self.assertEqual(report["train"]["retracted"]["events"], 1)
        self.assertFalse(report["pass"])


class ChecksTests(unittest.TestCase):
    @staticmethod
    def merged(mrr: float, f1: float, identity: float, categories: list[str]) -> dict:
        return {"schema_version": "vsmt-s2-05-node-audit-merged-v10", "per_episode": [
            {"episode_id": "h1", "report": {"missing_residual_rate": {"missing_residual_rate": mrr}, "node_prf1": {"node_f1": f1},
                                            "identity_continuity": {"identity_continuity": identity},
                                            "false_retract_rate_in_scope": {"false_retract_rate": 0.2}},
             "identity_attribution": [{"category": c} for c in categories]}]}

    def test_the_existence_cell_line(self) -> None:
        good = {s: self.merged(0.04, 0.94, 0.6, []) for s in checks.SEEDS}
        p3 = {t: {"pass": True, "readings": {"last_epoch": {"train": {"balanced_agreement": 1.0}, "selection": {"balanced_agreement": 1.0}}}}
              for t in checks.EXISTENCE_P3}
        audit = {"pass": True, "groups": {}}
        out = checks.existence_side({"pass": True, "per_rule": {}}, p3, good, audit)
        self.assertTrue(out["pass"])
        # no fallback to the same-input table: without the history audit check 1 fails
        missing = checks.existence_side({"pass": True, "per_rule": {}}, p3, good)
        self.assertFalse(missing["pass"])
        self.assertEqual(missing["history_audit"]["reason"], "history_audit_missing")
        bad = dict(good)
        bad[7] = self.merged(0.30, 0.94, 0.6, [])
        self.assertFalse(checks.existence_side({"pass": True, "per_rule": {}}, p3, bad, audit)["pass"])

    def test_the_association_pairing_needs_the_82_1_rule_and_fewer_births(self) -> None:
        new = {s: self.merged(0.0, 0.9, 0.5 + 0.01 * i, ["kept"] * 6 + ["chose_birth"] * 2) for i, s in enumerate(checks.SEEDS)}
        old = {s: self.merged(0.0, 0.9, 0.3, ["kept"] * 3 + ["chose_birth"] * 5) for s in checks.SEEDS}
        p3 = {t: {"pass": True, "readings": {"last_epoch": {"train": {"balanced_agreement": 1.0}, "selection": {"balanced_agreement": 1.0}}}}
              for t in checks.ASSOCIATION_P3}
        out = checks.association_side({"pass": True, "train": {}}, p3, new, old)
        self.assertTrue(out["paired_same_recall"]["pass"])
        self.assertTrue(out["pass"])
        self.assertFalse(checks.association_side({"pass": True, "train": {}}, p3, old, new)["pass"])


class ReportOnlyTests(unittest.TestCase):
    def test_ruling_93_makes_p3_reported_only(self) -> None:
        good = {s: ChecksTests.merged(0.04, 0.94, 0.6, []) for s in checks.SEEDS}
        failing = {t: {"pass": False, "readings": {"last_epoch": {"train": {"balanced_agreement": 0.9}, "selection": {"balanced_agreement": 0.9}}}}
                   for t in checks.EXISTENCE_P3}
        audit = {"pass": True, "groups": {}}
        try:
            self.assertFalse(checks.existence_side(None, failing, good, audit)["pass"])
            checks.P3_REPORT_ONLY["on"] = True
            out = checks.existence_side(None, failing, good, audit)
            self.assertTrue(out["pass"])
            self.assertEqual(out["p3_role"], "reported_only")
            self.assertFalse(out["p3"]["pass"])  # still reported
        finally:
            checks.P3_REPORT_ONLY["on"] = False


class KeyEventTests(unittest.TestCase):
    def test_existence_breakdown_counts_every_row_once_by_rule_and_teacher_label(self) -> None:
        from vsmt import lean_model as model
        heads = model.make_heads(assoc_only=False, seed=3)
        order = list(la.EXISTENCE_FEATURES)
        rows = [row("a", free_space_coverage_ratio=0.95), row("b", free_space_coverage_ratio=0.1), row("c", free_space_coverage_ratio=0.79)]
        keep = {"existence_rows": rows, "existence_feature_order": order,
                "existence_labels": {"a": {"status": "gone"}, "b": {"status": "present"}}}
        decisions = {r["entity_id"]: probes.p3_existence_decision("handcost", f_of(r)) for r in rows}
        out = probes.key_events(heads, [({}, keep, decisions)], "handcost")
        self.assertEqual(out["rule_RETRACT_teacher_gone"]["rows"], 1)
        self.assertEqual(out["rule_NOOP_teacher_present"]["rows"], 1)
        self.assertEqual(out["rule_NOOP_teacher_unlabelled"]["rows"], 1)
        self.assertEqual(out["near_threshold_NOOP"]["rows"], 1)  # 0.79 is within 1/64 of 0.8
        self.assertEqual(sum(v["rows"] for k, v in out.items() if k.startswith("rule_")), 3)

    def test_association_breakdown_on_a_labelled_frame(self) -> None:
        import test_vsmt_lean_model as fixture
        from vsmt import lean_model as model
        import ruling88_probes as r88p
        record = fixture.labelled_frame(11, drop="lamp", new=True)
        keep = {k: v for k, v in record.items() if not k.startswith("_")}
        decisions = r88p.rule_assignment(keep, "taf")
        heads = model.make_heads(assoc_only=True, seed=3)
        out = probes.key_events(heads, [({}, keep, decisions)], "taf")
        self.assertEqual(sum(v["rows"] for k, v in out.items() if k.startswith("rule_")), len(decisions))
        for v in out.values():
            self.assertLessEqual(v["disagreements"], v["rows"])


class JointTests(unittest.TestCase):
    def test_the_four_89_4_lines(self) -> None:
        good = {s: ChecksTests.merged(0.08, 0.80, 0.50, []) for s in checks.SEEDS}
        out = checks.joint_check(good)
        self.assertTrue(out["pass"])  # false retract 0.2 <= 0.35 in the fixture
        bad = {s: ChecksTests.merged(0.08, 0.80, 0.40, []) for s in checks.SEEDS}
        self.assertFalse(checks.joint_check(bad)["pass"])
        self.assertFalse(checks.joint_check({7: good[7]})["pass"])  # all five seeds are required


if __name__ == "__main__":
    unittest.main()
