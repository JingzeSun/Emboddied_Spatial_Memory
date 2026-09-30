"""D-224 / S2-R tests: the ruling 96 (a) reproduction check on hand-made training receipts.

Five retrained receipts whose total-loss digests equal the previous ones pass (exit 0) and report each seed's grouped epochs;
one differing digest fails the check (exit 3, nothing downstream may run); a retrained receipt without the grouped selection
is refused (exit 2).  CPU only.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import ruling96_selection_check as check  # noqa: E402


def write(root: Path, seed: int, receipt: dict) -> None:
    (root / f"A{seed}").mkdir(parents=True, exist_ok=True)
    (root / f"A{seed}" / "training_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def receipts(root: Path, *, retrained: bool, differing_seed: int | None = None, grouped: bool = True) -> None:
    for seed in check.SEEDS:
        receipt = {"weights_sha256": f"w{seed}" + ("x" if seed == differing_seed else ""), "best_epoch": 0}
        if retrained:
            receipt["validation_curve_terms"] = [{"total": 3.0, "association": 0.8, "existence": 2.2},
                                                 {"total": 3.5, "association": 0.7, "existence": 2.8}]
            if grouped:
                receipt["group_selection"] = {"best_epoch_by_group": {"association_birth": 1, "existence": 0}, "weights_sha256": f"g{seed}"}
        write(root, seed, receipt)


class SelectionCheckTests(unittest.TestCase):
    def run_check(self, **kwargs) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            previous, retrained, output = Path(tmp) / "old", Path(tmp) / "new", Path(tmp) / "out.json"
            receipts(previous, retrained=False)
            receipts(retrained, retrained=True, **kwargs)
            code = check.main(["--previous", str(previous), "--retrained", str(retrained), "--output", str(output)])
            return code, (json.loads(output.read_text(encoding="utf-8")) if output.exists() else {})

    def test_all_digests_reproduced_pass_and_report_the_grouped_epochs(self) -> None:
        code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertTrue(out["all_reproduced"])
        row = out["seeds"]["7"]
        self.assertEqual(row["grouped_best_epoch_by_group"], {"association_birth": 1, "existence": 0})
        self.assertFalse(row["grouped_equals_total_selection"])
        self.assertEqual(row["validation_terms_per_epoch"][1]["association"], 0.7)

    def test_one_differing_digest_fails_the_check(self) -> None:
        code, out = self.run_check(differing_seed=43)
        self.assertEqual(code, 3)
        self.assertFalse(out["all_reproduced"])
        self.assertFalse(out["seeds"]["43"]["reproduced"])
        self.assertTrue(out["seeds"]["7"]["reproduced"])

    def test_a_receipt_without_the_grouped_selection_is_refused(self) -> None:
        code, out = self.run_check(grouped=False)
        self.assertEqual(code, 2)
        self.assertEqual(out, {})


if __name__ == "__main__":
    unittest.main()
