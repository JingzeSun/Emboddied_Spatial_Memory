"""S3-06 (ruling 113): the read-only reanalysis -- replay of the committed statistics first, then D2..D8 and the paper index."""

from __future__ import annotations

import contextlib
import io
import json
import platform
import random
import statistics
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_06_reanalysis as ra  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_s3_04 as s4  # noqa: E402
from vsmt import lean_s3_05 as s5  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402

HOUSES = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(8)]
ITERATIONS = 120
SEED = 20261002
PLAN = [(arm, None, index) for index, arm in enumerate(("TAF", "ELU-P", "RAC", "LOW", "HandCost"))]
PLAN += [(arm, seed, 5 + index) for index, arm in enumerate(("VSMT-lean", "NoVersion", "HeuristicLabel", "AssocOnly"))
         for seed in arms.SEEDS]


def report(base: float, *, retract: bool, events: int, judged_retracts: int = 2, recovered: int = 2,
           unrecovered: int = 1) -> dict:
    out = {metric: {field: base} for metric, field in ev.HEADLINE_FIELD.items()}
    out["node_prf1"].update(matched=8, predicted=10, truth=9)
    out["node_prf1_iou"].update(matched=4, predicted=10, truth=9)
    out["missing_residual_rate"].update(residual=1, judged=2, not_yet_observable=0)
    for metric in ("false_retract_rate", "false_retract_rate_in_scope"):
        judged = judged_retracts if retract else 0
        out[metric].update(false_retracts=min(1, judged), judged_retracts=judged, ambiguous_retracts=0)
        if not judged:
            out[metric]["false_retract_rate"] = None
    out["identity_continuity"].update(kept=min(1, events), events=events, no_prior_carrier=min(1, events))
    out["identity_continuity_conditional"].update(kept=min(1, events), judged=min(2, events))
    out["retrieval_success"].update(successes=min(1, events), events=events, no_query=0, empty_candidates=0)
    if not events:  # no re-observed moved object in this house: the three event metrics are undefined for every run
        for metric in ("identity_continuity", "identity_continuity_conditional", "retrieval_success"):
            out[metric][ev.HEADLINE_FIELD[metric]] = None
    out["recovery_latency_frames"].update(recovered=recovered, unrecovered=[f"Cup|surface|{i}|2" for i in range(unrecovered)],
                                          never_observable=[])
    if not recovered:
        out["recovery_latency_frames"]["recovery_latency_frames"] = None
    out["contamination_auc"]["frames"] = 100
    out["size_and_cost"] = {"active_entity_count": 10.0, "lifecycle_version_count": 20.0, "runtime_per_frame_s": 0.2,
                            "peak_memory_bytes": 1000}
    return out


def synthetic_front(gain: float, rng: random.Random) -> tuple[list[dict], dict]:
    """The receipt's test runs and the merged export of one front end (a VSMT-lean gain on every metric), with three undefined
    cells: house 0 has no identity event (excluded for all), NoVersion seed 19 judged no retract in house 1 (an extra exclusion
    for that comparison only), LOW recovered nothing in house 2 (excluded for recovery latency, two unrecovered objects there)."""

    test_runs, merged = [], {}
    for arm, seed, index in PLAN:
        rows = []
        for position, house in enumerate(HOUSES):
            base = 0.3 + 0.01 * position + rng.uniform(-0.02, 0.02) + (gain if arm == "VSMT-lean" else 0.0)
            no_retract = (arm, seed, position) == ("NoVersion", 19, 1)
            nothing_recovered = (arm, position) == ("LOW", 2)
            rows.append({"episode_id": house,
                         "report": report(base, retract=arm not in ("TAF", "LOW", "AssocOnly"), events=0 if position == 0 else 3,
                                          judged_retracts=0 if no_retract else 2, recovered=0 if nothing_recovered else 2,
                                          unrecovered=2 if nothing_recovered else 1),
                         "decomposition_totals": {"recall_miss": 1, "teacher_error": 2, "amortization_error": 3, "correct": 4,
                                                  "unlabelled": 0, "duplicate_of_labelled": 0, "decisions": 10}})
        test_runs.append({"arm": arm, "config_index": index, "config": {}, "seed": seed})
        merged[ra.group_name(arm, index, seed)] = {"arm": arm, "per_episode": rows}
    return test_runs, merged


def committed_statistics(receipt: dict, merged: dict, inputs: dict) -> dict:
    """What the S3-05 stats step wrote: the frozen functions with S3-05's own control list."""

    per_front = {}
    for front in ra.FRONTS:
        episodes = ra.front_episodes(inputs, front)
        runs = ra.front_runs(receipt, merged[front], front)
        tables, failures = s5.tables(runs, episodes)
        per_front[front] = {**s5.front_statistics(tables, runs, seed=SEED, iterations=ITERATIONS), "episodes": len(episodes),
                            "failures": failures}
    return {**s5.test_statistics(per_front), "receipt_sha256": receipt["receipt_sha256"], "written_utc": "2026-10-07T23:17:53Z"}


def write_results(base: Path) -> dict:
    """A results directory with the five S3-05 exports, their manifest and the S3-04 receipt and manifest."""

    rng = random.Random(5)
    receipt_body = {"freeze_commit": "d" * 40, "environment": {"python": platform.python_version()},
                    "statistics": {"bootstrap_seed": SEED, "bootstrap_iterations": ITERATIONS,
                                   "ablations": {"arms": list(lt.ABLATION_ARMS), "role": "reported, never gating"}},
                    "fronts": {}}
    merged = {}
    for front, gain in (("instance", 0.2), ("sam2", 0.05)):
        receipt_body["fronts"][front], merged[front] = synthetic_front(gain, rng)
        receipt_body["fronts"][front] = {"test_runs": receipt_body["fronts"][front]}
    receipt = {**receipt_body, "receipt_sha256": s4.receipt_body_sha256(receipt_body)}
    inputs = {"episodes": {front: {"test": [{"episode_id": house, "frames": 100} for house in HOUSES]} for front in ra.FRONTS},
              "receipt_sha256": receipt["receipt_sha256"]}
    stats = committed_statistics(receipt, merged, inputs)
    exports = {ra.export_path(base, "s3_05", "statistics", ra.S3_05_TAG): stats,
               ra.export_path(base, "s3_05", "inputs", ra.S3_05_TAG): inputs}
    for front in ra.FRONTS:
        exports[ra.export_path(base, "s3_05", f"merged_{front}", ra.S3_05_TAG)] = merged[front]
    for path, payload in exports.items():
        ra.write_json(path, payload)
    ra.write_json(ra.export_path(base, "s3_05", "manifest", ra.S3_05_TAG),
                  {"receipt_sha256": receipt["receipt_sha256"],
                   "exports": {path.name: {"sha256": ra.file_sha256(path), "bytes": path.stat().st_size} for path in exports}})
    freeze = ra.export_path(base, "s3_04", "freeze", ra.S3_04_TAG)
    ra.write_json(freeze, receipt)
    ra.write_json(ra.export_path(base, "s3_04", "manifest", ra.S3_04_TAG),
                  {"exports": {freeze.name: {"sha256": ra.file_sha256(freeze), "bytes": freeze.stat().st_size}}})
    return {"receipt": receipt, "statistics": stats, "merged": merged, "inputs": inputs}


class HelperTests(unittest.TestCase):
    def test_group_names_follow_the_s3_03_rule(self):
        self.assertEqual(ra.group_name("TAF", 2, None), "TAF-c02")
        self.assertEqual(ra.group_name("VSMT-lean", 8, 19), "VSMT-lean-c08-s19")

    def test_the_frozen_control_list_is_restored(self):
        frozen = s5.COMPARED_ARMS
        with self.assertRaises(RuntimeError):
            with ra.compared_arms(frozen + ("AssocOnly",)):
                self.assertIn("AssocOnly", s5.COMPARED_ARMS)
                raise RuntimeError("stop")
        self.assertEqual(s5.COMPARED_ARMS, frozen)

    def test_plan_controls_add_what_the_plan_lists(self):
        receipt = {"statistics": {"ablations": {"arms": ["NoVersion", "HandCost", "HeuristicLabel", "AssocOnly"]}}}
        self.assertEqual(ra.plan_controls(receipt), tuple(s5.COMPARED_ARMS) + ("AssocOnly",))

    def test_json_differences_name_the_paths(self):
        self.assertEqual(ra.json_differences({"a": [1, 2], "b": 1}, {"a": [1, 3], "b": 1}), [".a[1]"])
        self.assertEqual(ra.json_differences({"a": 1}, {"a": 1}), [])
        self.assertEqual(ra.json_differences({"a": 1.0}, {"a": 1}), [".a"])  # a float that became an int is a difference


class SyntheticRunTests(unittest.TestCase):
    """The whole reanalysis on two small synthetic front ends whose 'committed' statistics come from the frozen functions."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._tmp.name)
        cls.made = write_results(cls.base)
        cls.loaded, cls.problems = ra.load_inputs(cls.base)
        cls.outcome = ra.reanalyse(cls.loaded, workers=1)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_inputs_check_against_their_manifests(self):
        self.assertEqual(self.problems, [])

    def test_the_replay_reproduces_the_committed_statistics(self):
        self.assertTrue(self.outcome["replay_equal"], self.outcome.get("differences"))
        self.assertEqual(self.outcome["problems"], [])

    def test_d2_adds_assoc_only_through_the_frozen_function(self):
        d2 = self.outcome["d2_assoc_only"]
        self.assertEqual(d2["added"], ["AssocOnly"])
        instance = d2["per_front"]["instance"]
        self.assertEqual(set(instance), set(s5.REPORT_METRICS))
        self.assertTrue(instance["false_retract_rate"]["not_applicable"])  # AssocOnly never retracts
        self.assertAlmostEqual(instance["retrieval_success"]["mean_advantage"], 0.2, places=1)
        gate = self.made["statistics"]["fronts"]["instance"]["primary_gate"]["metrics"]["identity_continuity"]
        self.assertEqual(instance["identity_continuity"]["lower_bound_two_level"], gate["lower_bound_two_level"])
        self.assertNotIn("AssocOnly", s5.COMPARED_ARMS)

    def test_the_synthetic_data_has_exclusions(self):
        instance = self.made["statistics"]["fronts"]["instance"]
        self.assertEqual(instance["exclusion_lists"]["identity_continuity"]["excluded_houses"], [HOUSES[0]])
        self.assertEqual(instance["exclusion_lists"]["recovery_latency_frames"]["excluded_houses"], [HOUSES[2]])
        self.assertEqual(instance["comparisons"]["false_retract_rate"]["NoVersion"]["extra_excluded_for_this_control"],
                         [HOUSES[1]])

    def test_d3_lower_percentile_is_the_exported_bound(self):
        d3 = self.outcome["d3_intervals"]["sam2"]["node_prf1"]
        exported = self.made["statistics"]["fronts"]["sam2"]["comparisons"]["node_prf1"]["HandCost"]
        self.assertEqual(d3["HandCost"]["interval_90"][0], exported["lower_bound_two_level"])
        self.assertLessEqual(d3["HandCost"]["interval_90"][0], d3["HandCost"]["interval_90"][1])
        node = self.made["statistics"]["fronts"]["sam2"]["node_f1_vs_assoc_only"]["interval_90"]
        self.assertEqual(d3["AssocOnly"]["interval_90"], node)
        self.assertNotIn("TAF", self.outcome["d3_intervals"]["instance"]["false_retract_rate"])  # not applicable
        extra = self.outcome["d3_intervals"]["instance"]["false_retract_rate"]["NoVersion"]  # the extra-exclusion path
        exported = self.made["statistics"]["fronts"]["instance"]["comparisons"]["false_retract_rate"]["NoVersion"]
        self.assertEqual((extra["houses"], extra["interval_90"][0]), (len(HOUSES) - 1, exported["lower_bound_two_level"]))

    def test_d4_counts_kept_and_all_houses(self):
        identity = self.outcome["d4_counts"]["instance"]["identity_continuity"]
        self.assertEqual((identity["kept_houses"], identity["excluded_houses"]), (len(HOUSES) - 1, 1))
        self.assertEqual(identity["per_arm_kept_houses"]["TAF"], {"kept": 7, "events": 21, "no_prior_carrier": 7})
        self.assertEqual(identity["per_arm_kept_houses"]["VSMT-lean"]["mean"]["events"], 21)
        recovery = self.outcome["d4_counts"]["instance"]["recovery_latency_frames"]
        self.assertEqual(recovery["per_arm_kept_houses"]["LOW"], {"recovered": 14, "unrecovered": 7, "never_observable": 0})
        self.assertEqual(recovery["per_arm_all_houses"]["LOW"], {"recovered": 14, "unrecovered": 9, "never_observable": 0})
        self.assertEqual(self.outcome["d4_counts"]["instance"]["false_retract_rate"]["not_applicable"], ["AssocOnly", "LOW", "TAF"])

    def test_d5_d6_d7_d8(self):
        d5 = self.outcome["d5_per_house"]["instance"]["identity_continuity"]
        self.assertEqual(d5["houses"], len(HOUSES) - 1)
        self.assertEqual(d5["summary"]["favourable"], len(HOUSES) - 1)
        means = [row["mean"] for row in d5["per_house"].values()]
        self.assertAlmostEqual(statistics.fmean(means),
                               self.made["statistics"]["fronts"]["instance"]["primary_gate"]["metrics"]["identity_continuity"]
                               ["mean_advantage"], places=12)
        shares = self.outcome["d6_decomposition"]["instance"]["per_arm"]["VSMT-lean"]["shares"]
        self.assertAlmostEqual(sum(shares.values()), 1.0)
        self.assertEqual(self.outcome["d6_decomposition"]["instance"]["per_arm"]["VSMT-lean"]["runs"], 5)
        cost = self.outcome["d7_size_and_cost"]["instance"]["per_arm"]["AssocOnly"]["active_entity_count"]
        self.assertEqual(cost, {"mean": 10.0, "min": 10.0, "max": 10.0})
        d8 = self.outcome["d8_consistency"]["instance"]
        self.assertEqual(d8["decomposition_rows"], len(PLAN) * len(HOUSES))
        self.assertEqual(d8["missing_residual_judged_differs_across_runs"], {})

    def test_a_process_pool_gives_the_same_numbers(self):
        pooled = ra.reanalyse(self.loaded, workers=2)
        self.assertTrue(pooled["replay_equal"])
        self.assertEqual(pooled["workers"]["actual"], 2)
        for key in ("d2_assoc_only", "d3_intervals", "d4_counts", "d5_per_house", "d8_consistency"):
            self.assertEqual(ra.normalise(pooled[key]), ra.normalise(self.outcome[key]), key)

    def test_a_changed_number_stops_the_replay(self):
        stats = json.loads(json.dumps(self.made["statistics"]))
        stats["fronts"]["sam2"]["main_table"]["node_prf1"]["TAF"]["mean"] += 1e-12
        outcome = ra.reanalyse({**self.loaded, "statistics": stats}, workers=1)
        self.assertFalse(outcome["replay_equal"])
        self.assertEqual(outcome["differences"], [".fronts.sam2.main_table.node_prf1.TAF.mean"])
        self.assertNotIn("d3_intervals", outcome)

    def test_an_export_that_differs_from_its_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_results(base)
            path = ra.export_path(base, "s3_05", "inputs", ra.S3_05_TAG)
            path.write_bytes(path.read_bytes() + b" ")
            _loaded, problems = ra.load_inputs(base)
            self.assertIn(f"export_differs_from_manifest:{path.name}", problems)

    def test_the_paper_index_checks_every_file_against_its_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ra.write_json(base / "a_export.json", {"x": 1})
            listed = {"exports": {"a_export.json": {"sha256": ra.file_sha256(base / "a_export.json"), "bytes": 7}}}
            for name in ra.STAGE_MANIFESTS:
                ra.write_json(base / name, listed if name.startswith("vsmt_lean_s3_05") else {"exports": {}})
            items = ({"item": "t", "content": "c", "files": ["a_export.json", "missing_{s3_06}.json"], "fields": [],
                      "command": "x", "commits": {"reanalysis": "{s3_06}"}},)
            original = ra.PAPER_ITEMS
            try:
                ra.PAPER_ITEMS = items
                index, problems = ra.paper_index(base, "abc1234")
            finally:
                ra.PAPER_ITEMS = original
            files = index["items"][0]["files"]
            self.assertFalse(files[0]["matches_manifest"])  # the manifest says 7 bytes, the file is longer
            self.assertEqual(index["items"][0]["commits"], {"reanalysis": "abc1234"})
            self.assertEqual(problems, ["index_file_differs_from_manifest:a_export.json", "index_file_missing:missing_abc1234.json"])

    def test_the_checks_fail_when_they_should(self):
        committed = self.made["statistics"]["fronts"]
        # D2: an AssocOnly gate-metric block that is not the primary gate's
        block = json.loads(json.dumps(self.outcome["d2_assoc_only"]["per_front"]["instance"]))
        block["identity_continuity"]["lower_bound_two_level"] += 1e-9
        front = {"comparisons": {metric: {"AssocOnly": value} for metric, value in block.items()},
                 "primary_gate": committed["instance"]["primary_gate"]}
        self.assertEqual(ra.d2_assoc_only(front)[1], ["d2_differs_from_primary_gate:identity_continuity.lower_bound_two_level"])
        # D3: a lower percentile that is not the exported bound
        key = "sam2|node_prf1|HandCost"
        exported = committed["sam2"]["comparisons"]["node_prf1"]["HandCost"]
        _out, problems = ra.d3_intervals({key: {"interval_90": [exported["lower_bound_two_level"] - 1e-9, 1.0],
                                                "houses": exported["houses"]}}, committed)
        self.assertIn(f"d3_lower_percentile_differs:{key}", problems)
        # D8: one run that saw a different number of identity events, one row whose decomposition does not add up
        runs = json.loads(json.dumps(ra.front_runs(self.made["receipt"], self.made["merged"]["sam2"], "sam2")))
        runs[3]["rows"][HOUSES[4]]["report"]["identity_continuity"]["events"] = 4
        runs[0]["rows"][HOUSES[5]]["decomposition_totals"]["correct"] = 5
        _checked, problems = ra.d8_consistency(runs, HOUSES)
        self.assertEqual(problems, [f"d8_events_differ_across_runs:identity_continuity.events:{HOUSES[4]}",
                                    f"d8_decomposition_does_not_add_up:TAF:{HOUSES[5]}"])


@contextlib.contextmanager
def patched(**values):
    saved = {name: getattr(ra, name) for name in values}
    for name, value in values.items():
        setattr(ra, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(ra, name, value)


def refresh_manifest(results: Path, path: Path) -> None:
    """After changing a committed export on purpose, record its new digest so that only the reanalysis notices."""

    manifest_path = ra.export_path(results, "s3_05", "manifest", ra.S3_05_TAG)
    manifest = ra.load_json(manifest_path)
    manifest["exports"][path.name] = {"sha256": ra.file_sha256(path), "bytes": path.stat().st_size}
    ra.write_json(manifest_path, manifest)


class CommandRunTests(unittest.TestCase):
    """The command's refusals and exit codes, with git replaced by stubs and a small repository in a temporary directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.results = self.root / "results"
        self.made = write_results(self.results)
        ra.write_json(self.results / "a_export.json", {"x": 1})
        listed = {"exports": {"a_export.json": {"sha256": ra.file_sha256(self.results / "a_export.json"),
                                                "bytes": (self.results / "a_export.json").stat().st_size}}}
        ra.write_json(self.results / "stage_manifest.json", listed)
        self.items = ({"item": "t", "content": "c", "files": ["a_export.json", "vsmt_lean_s3_06_reanalysis_{s3_06}.json"],
                       "fields": [], "command": "x", "commits": {"reanalysis": "{s3_06}"}},)
        self.untracked: list[str] = []
        self.frozen_differs = False

    def tearDown(self):
        self._tmp.cleanup()

    def run_command(self, *extra: str) -> tuple[int, str]:
        output = io.StringIO()
        with patched(ROOT=self.root, PAPER_ITEMS=self.items, STAGE_MANIFESTS=("stage_manifest.json",),
                     code_state=lambda inputs: ("abc1234" + "0" * 33, []), untracked=lambda inputs: list(self.untracked),
                     frozen_code_differs=lambda commit: self.frozen_differs), contextlib.redirect_stdout(output):
            code = ra.main(["run", "--results", str(self.results), "--out-dir", str(self.results), "--workers", "1", *extra])
        return code, output.getvalue()

    def test_a_clean_run_writes_both_outputs_and_refuses_to_overwrite_them(self):
        code, text = self.run_command()
        self.assertEqual(code, ra.EXIT_OK, text)
        written = ra.load_json(self.results / "vsmt_lean_s3_06_reanalysis_abc1234.json")
        self.assertEqual(written["d1_replay"]["equal"], True)
        self.assertEqual(written["freeze_commit"], "d" * 40)
        self.assertTrue(written["environment"]["python_minor_matches_the_freeze"])
        index = ra.load_json(self.results / "vsmt_lean_s3_06_paper_index_abc1234.json")
        self.assertEqual(index["problems"], [])
        self.assertEqual(index["items"][0]["files"][1]["file"], "results/vsmt_lean_s3_06_reanalysis_abc1234.json")
        self.assertEqual(self.run_command()[0], ra.EXIT_REFUSED)  # the outputs exist
        self.assertEqual(self.run_command("--replace")[0], ra.EXIT_OK)

    def test_a_replay_difference_writes_only_the_differences(self):
        path = ra.export_path(self.results, "s3_05", "statistics", ra.S3_05_TAG)
        stats = ra.load_json(path)
        stats["fronts"]["instance"]["main_table"]["node_prf1"]["LOW"]["mean"] += 1e-12
        ra.write_json(path, stats)
        refresh_manifest(self.results, path)
        code, _text = self.run_command()
        self.assertEqual(code, ra.EXIT_REPLAY_DIFFERS)
        differences = ra.load_json(self.results / "vsmt_lean_s3_06_replay_differences_abc1234.json")["differences"]
        self.assertEqual(differences, [".fronts.instance.main_table.node_prf1.LOW.mean"])
        self.assertFalse((self.results / "vsmt_lean_s3_06_reanalysis_abc1234.json").exists())

    def test_a_consistency_problem_exits_4(self):
        path = ra.export_path(self.results, "s3_05", "merged_sam2", ra.S3_05_TAG)
        merged = ra.load_json(path)
        merged[ra.group_name("RAC", 2, None)]["per_episode"][3]["report"]["retrieval_success"]["events"] = 7
        ra.write_json(path, merged)
        refresh_manifest(self.results, path)
        code, text = self.run_command()
        self.assertEqual(code, ra.EXIT_PROBLEMS, text)
        problems = ra.load_json(self.results / "vsmt_lean_s3_06_reanalysis_abc1234.json")["problems"]
        self.assertEqual(problems, [f"sam2:d8_events_differ_across_runs:retrieval_success.events:{HOUSES[3]}"])

    def test_refusals(self):
        self.untracked = ["results/vsmt_lean_s3_05_statistics_8d58475.json"]
        self.assertEqual(self.run_command()[0], ra.EXIT_REFUSED)
        self.untracked, self.frozen_differs = [], True
        self.assertEqual(self.run_command()[0], ra.EXIT_REFUSED)
        self.frozen_differs = False
        ra.export_path(self.results, "s3_05", "statistics", ra.S3_05_TAG).unlink()
        code, text = self.run_command()  # a missing input is a refusal with a reason, not a traceback
        self.assertEqual(code, ra.EXIT_REFUSED)
        self.assertIn("export_missing", text)
        with patched(ROOT=self.root):
            outside = ra.main(["run", "--results", str(self.root.parent), "--workers", "1"])
        self.assertEqual(outside, ra.EXIT_REFUSED)


@unittest.skipUnless(ra.export_path(ROOT / "results", "s3_05", "statistics", ra.S3_05_TAG).exists(), "S3-05 exports not present")
class CommittedExportsTests(unittest.TestCase):
    """Plumbing only on the committed S3-05 exports: no bootstrap, no D-reading (those wait for the reviewed run)."""

    @classmethod
    def setUpClass(cls):
        cls.loaded, cls.problems = ra.load_inputs(ROOT / "results")

    def test_the_committed_inputs_match_their_manifests(self):
        self.assertEqual(self.problems, [])
        self.assertEqual(ra.plan_controls(self.loaded["receipt"]), tuple(s5.COMPARED_ARMS) + ("AssocOnly",))

    def test_runs_map_onto_the_merged_groups_and_one_main_table_cell_reproduces(self):
        expected = {"instance": 87, "sam2": 85}
        for front in ra.FRONTS:
            runs = ra.front_runs(self.loaded["receipt"], self.loaded["merged"][front], front)
            episodes = ra.front_episodes(self.loaded["inputs"], front)
            self.assertEqual((len(runs), len(episodes)), (25, expected[front]))
            tables, failures = s5.tables(runs, episodes)
            self.assertEqual(failures, [])
            committed = self.loaded["statistics"]["fronts"][front]
            excluded = set(committed["exclusion_lists"]["node_prf1"]["excluded_houses"])
            kept = [house for house in sorted(tables["node_prf1"]) if house not in excluded]
            mean = statistics.fmean(tables["node_prf1"][house]["VSMT-lean:7"] for house in kept)
            self.assertEqual(mean, committed["main_table"]["node_prf1"]["VSMT-lean"]["per_seed"]["VSMT-lean:7"])


if __name__ == "__main__":
    unittest.main()
