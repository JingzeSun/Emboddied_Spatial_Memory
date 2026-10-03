"""Ruling 104-1 1c / 104-2 G4 tests for HeuristicLabel's labels (lean_heuristic_label).

Pinned on the runner's hand-built scenario (A and B seen twice, A gone for two frames while its place is visible and
free, A back): the label configuration must be ELU-P at the registered rollout_config with no distance gate and three
numeric fitted values; on ELU-P's own trajectory the labels are ELU-P's association and existence decisions row by
row (no mismatch, and the scenario does retract A) and the labeller's log-odds equal the arm's state after every
frame; on TAF's trajectory the labels follow that trajectory (TAF keeps A, the labeller calls A gone in both frames A
is eligible) and no reproduction block is kept; where the trajectory births every fragment, the labeller's own solve
binds the old entities and labels them present; AssocOnly's trajectory is refused (it has no existence step); every
record is accepted by the trainer's own preparation.  CPU, seconds; nothing here reads a real cache or a private file.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import test_vsmt_lean_runner as fixtures  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_heuristic_label as hl  # noqa: E402
from vsmt import lean_model as model  # noqa: E402

#: ELU-P at the registered rollout_config.  The fitted values make the scenario retract A on its first eligible frame:
#: 0.5 + 0.25 after the second sighting, then -0.5 decay and -1.0 for a fully covered free space gives -0.75 < 0.
LABEL_CONFIG = {**arms.ROLLOUT_CONFIG, "d_a": None, "initial_log_odds": 0.5, "persistence_log_decay_per_tick": 0.5,
                "match_gain": 0.25}


class ConfigTests(unittest.TestCase):
    def test_only_the_rollout_config_with_fitted_values_is_accepted(self):
        self.assertEqual(hl.validate_label_config(LABEL_CONFIG), LABEL_CONFIG)
        for name, value, code in (("theta_a", 0.6, "label_config_not_the_rollout_config:theta_a"),
                                  ("free_space_weight", 2.0, "label_config_not_the_rollout_config:free_space_weight"),
                                  ("retract_threshold", -1.0, "label_config_not_the_rollout_config:retract_threshold"),
                                  ("d_a", 1.0, "label_config_has_a_distance_gate")):
            with self.subTest(name=name), self.assertRaisesRegex(hl.LeanHeuristicLabelError, code):
                hl.validate_label_config({**LABEL_CONFIG, name: value})
        for value in (None, True):  # a fitted value still null, or not a number
            with self.subTest(value=value), self.assertRaises(ValueError):
                hl.validate_label_config({**LABEL_CONFIG, "match_gain": value})


class TrajectoryTests(unittest.TestCase):
    def test_on_elu_p_s_own_trajectory_the_labels_are_its_decisions(self):
        steps, _ = fixtures.run_all("ELU-P", config=LABEL_CONFIG)
        labeller = hl.HeuristicLabeller(LABEL_CONFIG)
        retracted = 0
        for step in steps:
            out = labeller.label(step, arm="ELU-P", arm_config=LABEL_CONFIG)
            receipt, record = step["receipt"], out["training_record"]
            self.assertEqual({f: t["target"] for f, t in record["targets"].items()}, receipt["assignment"])
            self.assertEqual(out["decisions"], receipt["existence"]["decisions"])
            self.assertEqual({e: label["status"] for e, label in record["existence_labels"].items()},
                             {e: "gone" if d == "RETRACT" else "present" for e, d in receipt["existence"]["decisions"].items()})
            self.assertEqual(labeller.log_odds, step["state"]["arm_state"]["log_odds"])  # the shadow state is the arm's state
            retracted += sum(1 for d in receipt["existence"]["decisions"].values() if d == "RETRACT")
        self.assertEqual(retracted, 1, "the scenario must retract A for the comparison to mean anything")
        summary = labeller.summary()
        self.assertEqual(summary["reproduction"], {"fragments": 8, "fragment_mismatches": 0, "existence_rows": 1, "existence_mismatches": 0})
        self.assertEqual(summary["totals"]["bound_by_the_labeller_while_eligible"], 0)
        self.assertEqual(summary["rule"], hl.LABEL_RULE)
        other = hl.HeuristicLabeller(LABEL_CONFIG)  # ELU-P at another configuration is another trajectory: no G4 block
        elsewhere = {**LABEL_CONFIG, "retract_threshold": -1.0}
        for step in fixtures.run_all("ELU-P", config=elsewhere)[0]:
            other.label(step, arm="ELU-P", arm_config=elsewhere)
        self.assertIsNone(other.summary()["reproduction"])

    def test_on_taf_s_trajectory_the_labels_follow_that_trajectory(self):
        config = {"theta_a": 0.7, "d_a": None}
        steps, _ = fixtures.run_all("TAF", config=config)
        a = steps[1]["receipt"]["assignment"]["region:a"]
        labeller = hl.HeuristicLabeller(LABEL_CONFIG)
        gone = []
        for step in steps:
            out = labeller.label(step, arm="TAF", arm_config=config)
            self.assertTrue(all(d == "NOOP" for d in step["receipt"]["existence"]["decisions"].values()))  # TAF never retracts
            gone += [(step["receipt"]["tick"], e) for e, label in out["training_record"]["existence_labels"].items()
                     if label["status"] == "gone"]
        self.assertEqual(gone, [(3, a), (4, a)])  # still eligible at 4 on this trajectory, and further below the threshold
        self.assertIsNone(labeller.summary()["reproduction"])

    def test_the_labeller_s_own_solve_binds_what_the_trajectory_left(self):
        config = {"tau_r": 0.5}
        steps, _ = fixtures.run_all("HeuristicLabel", config=config, scorer=fixtures.CosineScorer(birth=5.0, existence=-10.0))
        labeller = hl.HeuristicLabeller(LABEL_CONFIG)
        bound_present = 0
        for step in steps:
            out = labeller.label(step, arm="HeuristicLabel", arm_config=config)
            self.assertTrue(all(c.startswith(la.BIRTH_COLUMN_PREFIX) for c in step["receipt"]["assignment"].values()))
            labels = out["training_record"]["existence_labels"]
            for target in out["training_record"]["targets"].values():
                if target["status"] == "labelled" and target["target"] in labels:
                    self.assertEqual(labels[target["target"]]["status"], "present")
                    bound_present += 1
        self.assertEqual(bound_present, 6)
        self.assertEqual(labeller.summary()["totals"]["bound_by_the_labeller_while_eligible"], bound_present)

    def test_assoc_only_s_trajectory_is_refused(self):
        steps, _ = fixtures.run_all("AssocOnly", config={}, scorer=fixtures.CosineScorer())
        with self.assertRaisesRegex(hl.LeanHeuristicLabelError, "heuristic_labels_need_the_existence_step"):
            hl.HeuristicLabeller(LABEL_CONFIG).label(steps[0], arm="AssocOnly", arm_config={})

    def test_every_record_is_accepted_by_the_trainer(self):
        steps, _ = fixtures.run_all("ELU-P", config=LABEL_CONFIG)
        labeller = hl.HeuristicLabeller(LABEL_CONFIG)
        for step in steps:
            model.prepare_frame(labeller.label(step, arm="ELU-P", arm_config=LABEL_CONFIG)["training_record"])


if __name__ == "__main__":
    unittest.main()
