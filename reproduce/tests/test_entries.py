"""The comparison rules of the reproduction entry points (no worktree, no data)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_env  # noqa: E402
import fetch_extras  # noqa: E402
import l1_eval  # noqa: E402
import paper  # noqa: E402
from _common import REPO_ROOT, load_json  # noqa: E402


class PaperEntryTests(unittest.TestCase):
    def test_reanalysis_comparison_ignores_run_fields_and_later_inputs(self) -> None:
        committed = {"d1_replay": {"equal": True}, "written_utc": "a", "inputs": {"x.json": "1"}}
        recomputed = {"d1_replay": {"equal": True}, "written_utc": "b", "inputs": {"x.json": "1", "later.json": "2"}}
        self.assertEqual(paper.compare_reanalysis(recomputed, committed), ([], ["later.json"]))
        recomputed["inputs"]["x.json"] = "3"
        recomputed["d1_replay"] = {"equal": False}
        self.assertEqual(paper.compare_reanalysis(recomputed, committed)[0], ["d1_replay", "inputs:x.json"])

    def test_table_ii_reads_the_committed_statistics(self) -> None:
        rows = paper.table_ii(load_json(REPO_ROOT / paper.STATISTICS))
        self.assertEqual(len(rows), 4)
        first = rows[0]
        self.assertEqual((round(first["AssocOnly"], 3), round(first["VSMT-lean"], 3), round(first["lower_bound"], 3)),
                         (0.642, 0.115, 0.467))
        self.assertEqual([row["fixed_order_step"] for row in rows],
                         ["1: holds", "1: holds", "2: holds", "3: does not hold"])


class L1EntryTests(unittest.TestCase):
    def test_run_labels_follow_the_s3_names(self) -> None:
        self.assertEqual(l1_eval.run_label({"arm": "VSMT-lean", "config_index": 2, "seed": 7}), "VSMT-lean-c02-s7")
        self.assertEqual(l1_eval.run_label({"arm": "TAF", "config_index": 3, "seed": None}), "TAF-c03")

    def test_classification_separates_metrics_from_the_seal_chain(self) -> None:
        audit = {"report": {"node_prf1": 1, "size_and_cost": {"runtime_per_frame_s": 1}}, "trajectory_sha256": "a",
                 "wall_seconds": 3}
        other = {"report": {"node_prf1": 1, "size_and_cost": {"runtime_per_frame_s": 2}}, "trajectory_sha256": "b",
                 "wall_seconds": 4}
        result = l1_eval.classify(audit, other)
        self.assertTrue(result["metrics_equal"])
        self.assertEqual(result["differing_fields"], ["trajectory_sha256"])
        other["report"]["node_prf1"] = 2
        self.assertFalse(l1_eval.classify(audit, other)["metrics_equal"])

    def test_every_frozen_learned_run_has_one_head_file(self) -> None:
        receipt = load_json(l1_eval.RECEIPT)
        for front in ("instance", "sam2"):
            runs = receipt["fronts"][front]["test_runs"]
            self.assertEqual(len(runs), 25)
            for run in runs:
                path = l1_eval.heads_file(receipt, front, run, Path("/data"))
                self.assertEqual(path is None, run["heads_arm"] is None)

    def test_test_scope_needs_the_acknowledgement(self) -> None:
        self.assertEqual(l1_eval.main(["--data-root", str(REPO_ROOT / "nonexistent"), "--scope", "test"]), 2)


class FetchExtrasTests(unittest.TestCase):
    def test_the_record_lists_both_released_inputs(self) -> None:
        record = load_json(fetch_extras.RECORD)
        paths = sorted(item["path_in_repo"] for item in record["manifest_addendum"]["items"])
        self.assertEqual(paths, sorted(fetch_extras.NAMES.values()))
        self.assertEqual(len(record["revision"]), 40)

    def test_local_copies_are_checked_by_every_digest(self) -> None:
        import hashlib
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            salt = Path(directory) / "salt.txt"
            salt.write_bytes(b"abc\n")
            item = {"bytes": 4, "sha256": hashlib.sha256(b"abc\n").hexdigest(),
                    "stripped_text_sha256": hashlib.sha256(b"abc").hexdigest()}
            self.assertEqual(fetch_extras.item_problems(item, salt), [])
            salt.write_bytes(b"abd\n")
            self.assertEqual(fetch_extras.item_problems(item, salt), ["file digest differs", "stripped-text digest differs"])
            head = Path(directory) / "head.json"
            head.write_text(json.dumps({"sha256": "x"}), encoding="utf-8")
            data = head.read_bytes()
            item = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "payload_sha256": "y"}
            self.assertEqual(fetch_extras.item_problems(item, head), ["payload digest differs"])
            self.assertEqual(fetch_extras.item_problems(item, Path(directory) / "missing"), ["missing"])

    def test_a_destination_inside_the_repository_is_refused(self) -> None:
        self.assertEqual(fetch_extras.main(["--dest", str(REPO_ROOT / "outputs")]), 2)


class EnvironmentCheckTests(unittest.TestCase):
    def test_l0_rows_name_a_fix_for_every_missing_item(self) -> None:
        rows = check_env.check({"L0", "plugin"}, Path("/nonexistent"), deep=False)
        self.assertTrue(rows)
        for row in rows:
            if not row.ok:
                self.assertTrue(row.fix, row.item)


if __name__ == "__main__":
    unittest.main()
