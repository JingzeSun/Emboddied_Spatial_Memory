"""D-224 / S2-05 tests: the controlled training of ruling 81-2 on a synthetic development root.

The plan gives A7/A19 the own-data budget U, B and C the aggregated budget V, every condition the same validation
interval K (one own pass) and the registered seeds 7/19; the script trains on the right records (B = round 0 + own,
training houses only), validates on the own selection houses, spends exactly its budget, and a timing run writes a
projection for all four conditions and no weights.  CPU only, well under a minute.
"""
from __future__ import annotations

import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_controlled_training as controlled  # noqa: E402
from test_vsmt_lean_model import labelled_frame  # noqa: E402
from vsmt import lean_model as model  # noqa: E402

SCRIPT = PROJECT_ROOT / "ops" / "vsmt" / "lean_s2_05_controlled_training.py"
HOUSES = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(32)]


def write_pass(root: Path, pass_name: str, arm: str, offset: int) -> None:
    for index, house in enumerate(HOUSES):
        base = root / pass_name / house / arm
        base.mkdir(parents=True)
        (base / "receipt.json").write_text(json.dumps({"status": "succeeded", "mask_source": "simulator_instance_masks"}))
        with gzip.open(base / "training_records.jsonl.gz", "wt") as handle:
            handle.write(json.dumps({**labelled_frame(offset + index, drop=("lamp" if index % 2 else None), new=(index % 3 == 0)), "tick": 1}) + "\n")


class PlanTests(unittest.TestCase):
    def test_budgets_interval_and_seeds(self) -> None:
        plans = {c: controlled.plan_condition(c, own_updates_per_pass=10, round0_updates_per_pass=7, epochs=20, seeds=[7, 19, 31, 43, 59])
                 for c in controlled.CONDITIONS}
        self.assertEqual({c: p["update_budget"] for c, p in plans.items()}, {"A7": 200, "A19": 200, "B": 340, "C": 340,
                                                                              "A31": 200, "A43": 200, "A59": 200})
        self.assertEqual({p["evaluate_every"] for p in plans.values()}, {10})
        self.assertEqual({c: p["seed"] for c, p in plans.items()}, {"A7": 7, "A19": 19, "B": 7, "C": 7, "A31": 31, "A43": 43, "A59": 59})
        self.assertEqual({c: p["data"] for c, p in plans.items()}, {"A7": "own", "A19": "own", "B": "aggregated", "C": "own",
                                                                     "A31": "own", "A43": "own", "A59": "own"})
        with self.assertRaises(ValueError):
            controlled.plan_condition("D", own_updates_per_pass=10, round0_updates_per_pass=7, epochs=20, seeds=[7, 19])
        with self.assertRaises(ValueError):
            controlled.plan_condition("A7", own_updates_per_pass=0, round0_updates_per_pass=7, epochs=20, seeds=[7, 19])


class ScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "dev"
        write_pass(cls.root, "dagger_round_0", "ELU-P", 100)
        write_pass(cls.root, "dagger_round_1", "VSMT-lean", 200)
        write_pass(cls.root, "dagger_round_1", "AssocOnly", 300)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_script(self, arm: str, condition: str, *extra: str) -> dict:
        out = Path(self.tmp.name) / "out" / arm / condition / ("timing" if extra else "run")
        done = subprocess.run([sys.executable, str(SCRIPT), "--output-root", str(self.root), "--arm", arm, "--condition", condition,
                               "--out-dir", str(out), *extra], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        return {"receipt": json.loads((out / controlled.RECEIPT_FILE).read_text()), "weights": out / controlled.WEIGHTS_FILE}

    def test_conditions_train_on_the_right_records_and_spend_their_budget(self) -> None:
        own = controlled.load_split(self.root / "dagger_round_1", "VSMT-lean")
        round0 = controlled.load_split(self.root / "dagger_round_0", "ELU-P")
        self.assertEqual(len(own["holdout"]["selection_houses"]), 2)
        own_pass = model.updates_per_pass(own["train"], assoc_only=False)
        round0_pass = model.updates_per_pass(round0["train"], assoc_only=False)
        a7 = self.run_script("VSMT-lean", "A7")
        b = self.run_script("VSMT-lean", "B")
        for result, budget, frames in ((a7, 20 * own_pass, len(own["train"])), (b, 20 * (own_pass + round0_pass), len(own["train"]) + len(round0["train"]))):
            receipt = result["receipt"]
            self.assertEqual(receipt["updates_taken"], budget)
            self.assertEqual(receipt["update_budget_used"], budget)
            self.assertEqual(receipt["evaluate_every_used"], own_pass)
            self.assertEqual(receipt["train_frames"], frames)
            self.assertEqual(receipt["validation_frames"], len(own["validation"]))
            self.assertEqual(receipt["checkpoints"][-1]["updates"], budget)
            self.assertTrue(result["weights"].exists())
            self.assertEqual(json.loads(result["weights"].read_text())["sha256"], receipt["weights_sha256"])
            self.assertEqual(len(receipt["input_files"]), 64)
        self.assertEqual(a7["receipt"]["plan"]["seed"], 7)
        self.assertEqual(b["receipt"]["plan"]["V"], b["receipt"]["update_budget_used"])

    def test_a_timing_run_projects_every_condition_and_writes_no_weights(self) -> None:
        timing = self.run_script("AssocOnly", "C", "--timing-updates", "5")
        receipt = timing["receipt"]
        self.assertTrue(receipt["timing_run"])
        self.assertEqual(receipt["updates_taken"], 5)
        self.assertEqual(set(receipt["projected_seconds"]), set(controlled.CONDITIONS))
        # the rate is measured between two checkpoints, so the one-off record preparation is reported on its own
        self.assertEqual([mark[0] for mark in receipt["timing_marks"]], [2, 4, 5])
        self.assertGreaterEqual(receipt["in_call_preparation_seconds"], 0.0)
        self.assertFalse(timing["weights"].exists())


if __name__ == "__main__":
    unittest.main()
