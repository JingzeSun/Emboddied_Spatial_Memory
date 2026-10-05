"""S3-04 (ruling 106): the choice on validation, the five checks and the freeze receipt (lean_s3_04 and ops/vsmt/s3_04_manifest.py)."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402
from vsmt import lean_s3_04 as s4  # noqa: E402

EPISODES = ("h1", "h2", "h3", "h4")
FRAMES = {"h1": 900, "h2": 300, "h3": 120, "h4": 500}
FIT = {"initial_log_odds": 4.7, "persistence_log_decay_per_tick": 2e-5, "match_gain": 3.5}


def synthetic_report(arm: str, index: int, seed: int | None, house: str, *, events: int = 6) -> dict:
    """Every headline field, the value a deterministic function of the run and the house (as in the S3-03 tests)."""

    base = (sum(map(ord, arm)) % 7) / 100 + index / 1000 + (seed or 0) / 10000 + int(house[1:]) / 100000
    report = {metric: {field: base} for metric, field in ev.HEADLINE_FIELD.items()}
    for metric in s4.EVENT_METRICS:
        report[metric]["events"] = events
    if arm in ("TAF", "LOW", "AssocOnly"):
        report["false_retract_rate"]["false_retract_rate"] = None
        report["false_retract_rate_in_scope"]["false_retract_rate"] = None
    return report


def synthetic_runs(*, skip_seed: tuple[str, int] | None = None, without: str | None = None) -> list[dict]:
    runs = []
    for arm, seeded in s3.SELECTION_ARMS.items():
        if arm == without:
            continue
        for index, config in enumerate(arms.enumerate_configs(arm, arms.FROZEN_GRIDS[arm])):
            for seed in (arms.SEEDS if seeded else (None,)):
                if skip_seed is not None and (arm, seed) == skip_seed:
                    continue
                reports = {house: synthetic_report(arm, index, seed, house) for house in EPISODES}
                runs.append({"arm": arm, "config_index": index, "config": dict(config), "seed": seed, "reports": reports})
    return runs


class SelectionTests(unittest.TestCase):
    """Ruling 106-2."""

    def test_every_arm_takes_what_select_configuration_takes(self):
        readings = s3.selection_readings(synthetic_runs(), mask_source="simulator_instance_masks")
        out = s4.select_front(readings)
        self.assertEqual(set(out["arms"]), set(s3.SELECTION_ARMS))
        for arm in s3.SELECTION_ARMS:
            expected = arms.select_configuration(s3.selection_validation(readings, arm), arm=arm,
                                                 reference_missing_residual_rate=readings["reference"]["missing_residual_rate"])
            row = out["arms"][arm]
            self.assertEqual(row["selected"], expected["selected"], arm)
            self.assertEqual(row["config"], readings["readings"][arm][str(expected["selected"])]["config"])
            self.assertEqual(row["validation_mean"], readings["readings"][arm][str(expected["selected"])]["mean"])
        self.assertEqual(out["not_frozen"], s4.NOT_FROZEN)
        self.assertEqual(json.loads(json.dumps(out)), out)

    def test_an_unsatisfiable_constraint_takes_the_node_f1_maximum_and_is_reported(self):
        runs = synthetic_runs()
        for run in runs:
            if run["arm"] == "VSMT-lean":  # every tau_r leaves more stale entities than AssocOnly
                for report in run["reports"].values():
                    report["missing_residual_rate"]["missing_residual_rate"] = 0.9
        out = s4.select_front(s3.selection_readings(runs, mask_source="sam2"))
        row = out["arms"]["VSMT-lean"]
        self.assertFalse(row["constraint_satisfiable"])
        self.assertEqual(row["reason"], "constraint_not_satisfiable")
        self.assertEqual(row["selected"], 9)  # the synthetic node F1 grows with the index
        self.assertIn("VSMT-lean", out["report_only"]["constraint_not_satisfiable"])
        self.assertEqual(out["report_only"]["grid_edge"]["VSMT-lean"], [{"parameter": "tau_r", "value": 0.9, "position": "last"}])

    def test_a_missing_seed_and_an_absent_arm(self):
        out = s4.select_front(s3.selection_readings(synthetic_runs(skip_seed=("HeuristicLabel", 31)), mask_source="sam2"))
        self.assertEqual(out["report_only"]["seeds_missing"], {"HeuristicLabel": [31]})
        runs = s4.test_runs(out, elu_p_values=FIT)
        self.assertEqual(len(runs), 24)  # 5 rule arms + 4 learned arms x 5 seeds, less the missing seed
        absent = s3.selection_readings(synthetic_runs(without="AssocOnly"), mask_source="sam2",
                                       absent_arms={"AssocOnly": "every seed's training diverged"})
        chosen = s4.select_front(absent)
        self.assertTrue(chosen["arms"]["AssocOnly"]["absent"])
        self.assertEqual(sorted(chosen["report_only"]["constraint_not_satisfiable"]), sorted(arms.SELECTION_CONSTRAINED_ARMS))
        self.assertEqual(chosen["report_only"]["arms_absent"], ["AssocOnly"])
        self.assertNotIn("AssocOnly", {run["arm"] for run in s4.test_runs(chosen, elu_p_values=FIT)})

    def test_the_test_run_list(self):
        out = s4.select_front(s3.selection_readings(synthetic_runs(), mask_source="simulator_instance_masks"))
        runs = s4.test_runs(out, elu_p_values=FIT)
        self.assertEqual(len(runs), 25)
        elu = next(run for run in runs if run["arm"] == "ELU-P")  # the runner configuration, as S3-03 ran it and G4 verifies it
        self.assertEqual(elu["config"], {**elu["grid_config"], **FIT})
        taf = next(run for run in runs if run["arm"] == "TAF")
        self.assertEqual(taf["config"], taf["grid_config"])
        with self.assertRaises(s4.LeanS3_04Error):
            s4.test_runs(out, elu_p_values={})
        receipt = {"fronts": {"instance": {"test_runs": runs, "selection": out}}}
        self.assertEqual(s4.selection_differences(receipt, copy.deepcopy(receipt)), [])
        changed = copy.deepcopy(receipt)
        changed["fronts"]["instance"]["test_runs"][0]["config_index"] += 1
        self.assertEqual(s4.selection_differences(receipt, changed), ["instance:.test_runs[0].config_index"])
        self.assertEqual([run["arm"] for run in runs[:5]], list(s4.TEST_RULE_ARMS))
        self.assertTrue(all(run["seed"] is None and run["heads_arm"] is None for run in runs[:5]))
        self.assertEqual({run["heads_arm"] for run in runs if run["arm"] == "NoVersion"}, {"VSMT-lean"})
        self.assertEqual([run["seed"] for run in runs if run["arm"] == "AssocOnly"], list(arms.SEEDS))

    def test_grid_edges(self):
        self.assertEqual(s4.grid_edge("VSMT-lean", {"tau_r": 0.15}), [{"parameter": "tau_r", "value": 0.15, "position": "first"}])
        self.assertEqual(s4.grid_edge("VSMT-lean", {"tau_r": 0.5}), [])
        self.assertEqual(s4.grid_edge("TAF", {"theta_a": 0.7, "d_a": None}), [{"parameter": "d_a", "value": None, "position": "first"}])
        self.assertEqual(s4.grid_edge("AssocOnly", {}), [])


class CheckTests(unittest.TestCase):
    """Ruling 106-3 G2, G3 and the G4 episodes."""

    def test_readings_equal_after_a_json_round_trip(self):
        readings = s3.selection_readings(synthetic_runs(), mask_source="sam2")
        recorded = {**json.loads(json.dumps(readings)), "front": "sam2", "written_utc": "2026-10-07T00:00:00Z"}
        self.assertEqual(s4.readings_differences(recorded, s3.selection_readings(synthetic_runs(), mask_source="sam2")), [])
        recorded["readings"]["RAC"]["2"]["mean"]["node_prf1"] += 1e-12
        self.assertEqual(s4.readings_differences(recorded, readings), [".readings.RAC.2.mean.node_prf1"])
        self.assertEqual(s4.differences({"a": 1}, {"a": 1.0}), [".a"])  # a type change is a difference
        self.assertEqual(s4.differences({"a": 1}, {}), [".a:missing_on_right"])

    def test_events_must_take_one_value(self):
        self.assertEqual(s4.event_problems(s3.selection_readings(synthetic_runs(), mask_source="sam2")), [])
        runs = synthetic_runs()
        runs[0]["reports"]["h1"]["identity_continuity"]["events"] = 7
        problems = s4.event_problems(s3.selection_readings(runs, mask_source="sam2"))
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("events_differ_across_runs:identity_continuity"))

    def test_probe_episodes_are_the_smallest_with_an_identity_event(self):
        reports = {house: synthetic_report("AssocOnly", 0, 7, house) for house in EPISODES}
        reports["h3"]["identity_continuity"]["events"] = 0  # the smallest episode has no identity event
        self.assertEqual(s4.probe_episodes(reports, FRAMES), ["h2", "h4"])
        for report in reports.values():
            report["identity_continuity"]["events"] = 0
        with self.assertRaises(s4.LeanS3_04Error):
            s4.probe_episodes(reports, FRAMES)


class FreezeTests(unittest.TestCase):
    """Ruling 106-4: the code digest and what S3-05 checks before it unseals."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name, text in (("src/vsmt/a.py", "x = 1\n"), ("ops/vsmt/b.sh", "echo b\n"), ("configs/vsmt/c.json", "{}\n")):
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(text, encoding="utf-8")
        self.files = ["src/vsmt/a.py", "ops/vsmt/b.sh", "configs/vsmt/c.json"]

    def tearDown(self):
        self.tmp.cleanup()

    def receipt(self) -> dict:
        receipt = {"code": s4.code_digest(self.root, self.files),
                   "frozen_bytes": {"heads": {"/w/VSMT-lean/s7/weights_grouped.json": "aa"},
                                    "elu_p_registered": {"instance": {"match_gain": 3.5}},
                                    "test_manifest_sha256": s4.test_manifest_sha256({"test": ["b", "a"]})}}
        receipt["receipt_sha256"] = s4.receipt_body_sha256(receipt)
        return receipt

    def test_the_frozen_code_passes_and_any_change_is_named(self):
        receipt = self.receipt()
        kwargs = dict(heads={"/w/VSMT-lean/s7/weights_grouped.json": "aa"}, registered_values={"instance": {"match_gain": 3.5}},
                      test_manifest_sha256=s4.test_manifest_sha256({"test": ["a", "b"]}))
        self.assertEqual(s4.verify_freeze(receipt, code=s4.code_digest(self.root, self.files), **kwargs), [])
        (self.root / "ops/vsmt/b.sh").write_text("echo c\n", encoding="utf-8")
        (self.root / "ops/vsmt/new.py").write_text("", encoding="utf-8")
        current = s4.code_digest(self.root, self.files + ["ops/vsmt/new.py"])
        self.assertEqual(s4.verify_freeze(receipt, code=current, **kwargs), ["code_added:ops/vsmt/new.py", "code_changed:ops/vsmt/b.sh"])

    def test_frozen_bytes_and_the_receipt_digest(self):
        receipt = self.receipt()
        code = s4.code_digest(self.root, self.files)
        problems = s4.verify_freeze(receipt, code=code, heads={"/w/VSMT-lean/s7/weights_grouped.json": "bb"},
                                    registered_values={"instance": {"match_gain": 3.1}}, test_manifest_sha256="x")
        self.assertEqual(problems, ["heads_file_differs:/w/VSMT-lean/s7/weights_grouped.json", "elu_p_values_differ:instance",
                                    "test_manifest_differs"])
        tampered = copy.deepcopy(receipt)
        tampered["code"]["files"]["src/vsmt/a.py"] = "0" * 64
        self.assertIn("freeze_receipt_digest_differs", s4.verify_freeze(
            tampered, code=code, heads={"/w/VSMT-lean/s7/weights_grouped.json": "aa"},
            registered_values={"instance": {"match_gain": 3.5}}, test_manifest_sha256=s4.test_manifest_sha256({"test": ["a", "b"]})))
        with self.assertRaises(s4.LeanS3_04Error):
            s4.code_digest(self.root, ["tests/test_x.py"])  # only src/, ops/ and configs/

    def test_the_statistics_plan_names_the_registered_rules(self):
        plan = s4.statistics_plan()
        self.assertEqual(plan["bootstrap_seed"], 20261002)
        self.assertEqual(plan["bootstrap_iterations"], 10000)
        self.assertEqual(plan["fixed_sequence"]["steps"], [["simulator_instance_masks", ["missing_residual_rate", "identity_continuity"]],
                                                           ["sam2", ["missing_residual_rate"]], ["sam2", ["identity_continuity"]]])
        self.assertEqual(plan["primary_gate"]["comparison"], ["VSMT-lean", "AssocOnly"])


class DriverTests(unittest.TestCase):
    """ops/vsmt/s3_04_manifest.py on a synthetic S3-03 run root (one front end)."""

    def setUp(self):
        import s3_03_manifest as s303

        self.s303 = s303
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.run_root, self.out_root, self.export_dir = base / "s3-03-run", base / "s3-04", base / "exports"
        self.export_dir.mkdir(parents=True)
        inputs = {"fronts": ["instance"], "s3_02": {"tag": "3f6ef1d"},
                  "roots": {"raw": {"validation": str(base / "raw")}, "geometry": {"validation": str(base / "geometry")},
                            "cache": {"instance": {"validation": str(base / "cache")}}},
                  "reid": {"instance": {"file": str(base / "reid.json")}},
                  "episodes": {"instance": {"validation": [{"episode_id": h, "frames": FRAMES[h]} for h in EPISODES], "train": []}}}
        s303.write_json(self.run_root / "inputs.json", inputs)
        self.ctx = s303.load_context(self.run_root)
        runs = synthetic_runs()
        for run in runs:
            merged = {"metrics_only": True, "mask_source": "simulator_instance_masks",
                      "per_episode": [{"episode_id": h, "config": run["config"], "report": run["reports"][h]} for h in EPISODES]}
            s303.write_json(self.ctx.merged_path("instance", run["arm"], run["config_index"], run["seed"]), merged)
        readings = s3.selection_readings(runs, mask_source="simulator_instance_masks")
        s303.write_json(self.ctx.front_dir("instance") / "selection_readings.json",
                        {**readings, "front": "instance", "written_utc": "2026-10-07T00:00:00Z"})
        s303.write_json(self.ctx.fit_values_path("instance"),
                        {"front": "instance", "mask_source": "simulator_instance_masks", "values": {"initial_log_odds": 4.7,
                         "persistence_log_decay_per_tick": 2e-5, "match_gain": 3.5},
                         "values_sha256": s303.canonical_sha256({"initial_log_odds": 4.7, "persistence_log_decay_per_tick": 2e-5,
                                                                 "match_gain": 3.5})})

    def tearDown(self):
        self.tmp.cleanup()

    def main(self, *argv: str) -> int:
        import s3_04_manifest as driver

        return driver.main([*argv, "--out-root", str(self.out_root), "--s3-03-run-root", str(self.run_root),
                            "--export-dir", str(self.export_dir), "--s3-03-tag", "10f7013"])

    def test_select_passes_on_s3_03s_readings_and_fails_on_a_changed_value(self):
        import s3_04_manifest as driver

        self.assertEqual(self.main("select", "--front", "instance"), 0)
        select = driver.load_json(self.out_root / "select_instance.json")
        self.assertTrue(select["pass"])
        self.assertEqual(select["g2"]["differences"], [])
        self.assertEqual(len(select["test_runs"]), 25)
        self.assertEqual(select["probe_episodes"], ["h3", "h2"])
        path = self.ctx.front_dir("instance") / "selection_readings.json"
        recorded = driver.load_json(path)
        recorded["reference"]["missing_residual_rate"] = 0.5
        driver.write_json(path, recorded)
        self.assertEqual(self.main("select", "--front", "instance"), 3)
        self.assertIn("g2_readings_differ:.reference.missing_residual_rate", driver.load_json(self.out_root / "select_instance.json")["problems"])

    def test_probe_tasks_rerun_each_selected_run_into_the_s3_04_root(self):
        import s3_04_manifest as driver

        self.assertEqual(self.main("select", "--front", "instance"), 0)
        select = driver.load_json(self.out_root / "select_instance.json")
        tasks = driver.probe_tasks(self.ctx, "instance", select, self.out_root)
        self.assertEqual(len(tasks), 50)  # 25 runs x 2 episodes
        elu = next(task for task in tasks if task["arm"] == "ELU-P")
        entry = json.loads(elu["argv"][elu["argv"].index("--configs") + 1])
        self.assertEqual(entry[0]["config"]["match_gain"], 3.5)  # the run-local fitted values, as in S3-03
        self.assertEqual(elu["original_host"], "local")
        driver.write_json(self.run_root / "jobs" / "instance__audit__ELU-P__rule__c00-02__h3.json", {"status": "done", "host": "w1"})
        tasks = driver.probe_tasks(self.ctx, "instance", select, self.out_root)
        named = [task for task in tasks if task["arm"] == "ELU-P" and task["episode"] == "h3"]
        self.assertTrue(all(task["original_job"].startswith("instance/audit/ELU-P/rule/c") for task in named))
        if select["selection"]["arms"]["ELU-P"]["selected"] <= 2:
            self.assertEqual(named[0]["original_host"], "w1")
        self.assertTrue(entry[0]["output_root"].startswith(str(self.out_root)))
        self.assertTrue(elu["original"].startswith(str(self.run_root)))
        no_version = next(task for task in tasks if task["arm"] == "NoVersion")
        heads = no_version["argv"][no_version["argv"].index("--heads") + 1]
        self.assertIn("VSMT-lean", heads)
        self.assertTrue(heads.endswith("weights_grouped.json"))
        with mock.patch.object(self.s303, "resources", return_value={"cpu_quota": 32, "memory_bytes": 60 * 2 ** 30}):
            self.assertEqual(driver.worker_count(50, None)["actual"], 26)  # (60 - 8) / 2 GiB
            self.assertEqual(driver.worker_count(10, None)["actual"], 10)

    def test_heads_are_checked_against_their_training_receipts(self):
        import s3_04_manifest as driver

        for arm in s3.TRAINED_ARMS:
            for seed in arms.SEEDS:
                directory = self.ctx.training_dir("instance", 1, arm, seed)
                grouped = arm != "AssocOnly"
                payload = {"sha256": f"{arm}-{seed}"}
                driver.write_json(directory / ("weights_grouped.json" if grouped else "weights.json"), payload)
                receipt = {"weights_sha256": "total", "diverged": False,
                           "group_selection": {"weights_sha256": f"{arm}-{seed}"} if grouped else None}
                if not grouped:
                    receipt["weights_sha256"] = f"{arm}-{seed}"
                driver.write_json(directory / "training_receipt.json", receipt)
                driver.write_json(self.run_root / "jobs" / f"instance__t1__{arm}__s{seed}.json", {"status": "done"})
        rows, problems = driver.heads_record(self.ctx, "instance")
        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 15)
        self.assertTrue(all(row["usable"] for row in rows.values()))
        driver.write_json(self.ctx.training_dir("instance", 1, "VSMT-lean", 7) / "weights_grouped.json", {"sha256": "other"})
        driver.write_json(self.run_root / "jobs" / "instance__t1__HeuristicLabel__s19.json", {"status": "diverged"})
        # a round-0 divergence leaves every round-1 training of the arm skipped: a result, as S3-03 counts it (ruling 102-9)
        driver.write_json(self.run_root / "jobs" / "instance__t1__AssocOnly__s31.json",
                          {"status": "skipped", "reason": "dependency_diverged:instance/t0/AssocOnly"})
        rows, problems = driver.heads_record(self.ctx, "instance")
        self.assertEqual(problems, ["heads_differ_from_the_training_receipt:instance/t1/VSMT-lean/s7"])
        self.assertFalse(rows["HeuristicLabel|19"]["usable"])
        self.assertFalse(rows["AssocOnly|31"]["usable"])
        driver.write_json(self.run_root / "jobs" / "instance__t1__AssocOnly__s31.json", {"status": "skipped", "reason": "operator"})
        self.assertIn("training_not_done_or_files_missing:instance/t1/AssocOnly/s31:skipped", driver.heads_record(self.ctx, "instance")[1])

    def test_no_receipt_before_every_check_passed_and_s3_05s_entry_exists(self):
        import s3_04_manifest as driver

        with mock.patch.object(driver, "S3_05_ENTRY", "ops/vsmt/not_there.sh"):
            self.assertEqual(self.main("receipt"), 3)
        problems = driver.load_json(self.out_root / "receipt.json")["problems"]
        self.assertIn("check_not_passed_at_this_commit", problems)
        self.assertIn("probe_instance_not_passed_at_this_commit", problems)
        self.assertTrue(any(item.startswith("s3_05_entry_missing:ops/vsmt/not_there.sh") for item in problems))
        self.assertFalse((self.out_root / "freeze_receipt.json").exists())

    def test_a_test_root_is_refused(self):
        from vsmt import lean_test_seal

        lean_test_seal.write_marker(self.run_root, kind="raw", state=lean_test_seal.STATE_PENDING)
        self.assertEqual(self.main("select", "--front", "instance"), 2)


if __name__ == "__main__":
    unittest.main()
