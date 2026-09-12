"""Server-only E0 orchestration checks; synthetic files, no real recovery run."""
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops/spatial_history"))
import public_geometry_check as ops


class PublicGeometryOpsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def config(self):
        return json.loads((ops.ROOT / ops.CONFIG).read_text(encoding="utf-8"))

    def test_active_config_preserves_proposal_scientific_values(self):
        config = ops.configuration()
        proposal = json.loads((ops.ROOT / ops.PROPOSAL).read_text(encoding="utf-8"))
        for key in ("public_sensor_spec", "extractor", "evaluation_only", "budget_proposal", "claims", "source"):
            self.assertEqual(config[key], proposal[key])
        self.assertFalse(config["training_authorized"])
        changed = {**config, "extractor": {**config["extractor"], "plane_tolerance_m": 1}}
        with patch.object(ops, "read", return_value=changed), self.assertRaises(ValueError):
            ops.configuration()

    def test_fixed_census_and_public_request_strip_private_fields(self):
        config = self.config()
        inputs = {"public": {w: {"relative_path": w + "/public.json", "sha256": "a" * 64, "bytes": 12}
                             for w in ("LL", "LR", "RL", "RR")}}
        jobs = ops.jobs(config, inputs, Path("/source"))
        self.assertEqual(len(jobs), 16)
        self.assertEqual(sum(121 if j["indices"] is None else len(j["indices"]) for j in jobs), 500)
        request = ops.public_request(jobs[0], config)
        self.assertEqual(set(request), {"public_path", "expected_sha256", "expected_bytes", "history_indices",
                                        "public_sensor_spec", "extractor"})
        for key in ("world", "expected_candidates", "evaluation_only", "source", "xml"):
            self.assertNotIn(key, request)

    def test_failed_or_interrupted_directory_cannot_restart(self):
        (self.directory / "started.json").write_text("preserve")
        with patch.object(ops, "verify", side_effect=ValueError("incomplete")), \
                patch.object(ops, "configuration") as config, patch.object(ops, "source_inputs") as sources:
            with self.assertRaises(ValueError):
                ops.run(self.directory, ops.SOURCE)
            config.assert_not_called()
            sources.assert_not_called()
        self.assertEqual((self.directory / "started.json").read_text(), "preserve")

    def test_writer_reserves_export_space_and_does_not_overwrite(self):
        ops.save(self.directory, "one.json", {"value": 1})
        with self.assertRaises(FileExistsError):
            ops.save(self.directory, "one.json", {"value": 2})
        with patch.object(ops, "LIMIT_BYTES", 80), patch.object(ops, "RESERVE", 0):
            with self.assertRaisesRegex(ValueError, "budget"):
                ops.save(self.directory, "two.json", {"long": "x" * 100})
        self.assertFalse((self.directory / "two.json").exists())

    def sealed(self):
        for i in range(16):
            ops.save(self.directory, f"predictions/query-{i:02d}.json", {"example": i})
        return {"predictions": ops.manifest(self.directory), "public_complete": True}

    def test_seal_requires_every_prediction_and_exact_bytes(self):
        seal = self.sealed()
        ops.verify_seal(self.directory, seal)
        missing = {**seal, "predictions": dict(seal["predictions"])}
        missing["predictions"].pop("predictions/query-15.json")
        with self.assertRaises(ValueError):
            ops.verify_seal(self.directory, missing)
        (self.directory / "predictions/query-00.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            ops.verify_seal(self.directory, seal)

    def test_private_evaluation_cannot_start_before_seal(self):
        with self.assertRaises(FileNotFoundError):
            ops.worker_evaluate(self.directory, {"xml": {}, "jobs": [], "evaluation_only": {}})

    def test_private_key_in_public_request_is_rejected_before_loading(self):
        with self.assertRaisesRegex(ValueError, "request boundary"):
            ops.worker_public(self.directory, "query-00", {"layout_truth": {}})

    def test_memory_limit_kills_child_group_and_preserves_exit(self):
        child = Mock(pid=12345, returncode=-9)
        child.poll.return_value = None
        with patch.object(ops.subprocess, "Popen", return_value=child), \
                patch.object(ops, "tree_memory", return_value=(ops.LIMIT_RSS + 1, ops.LIMIT_RSS + 1)), \
                patch.object(ops.os, "killpg") as kill:
            ledger = []
            with self.assertRaisesRegex(ValueError, "failed"):
                ops.run_child(self.directory, "tests", "tests", {}, ops.time.monotonic(), ledger)
            kill.assert_called_once_with(child.pid, signal.SIGKILL)
        self.assertEqual(len(ledger), 1)
        self.assertIn("memory limit", ledger[0]["error"])
        self.assertTrue((self.directory / "exits/tests.json").is_file())

    def test_export_is_idempotent_but_never_overwrites_different_bytes(self):
        ops.save(self.directory, "started.json", {"example": True})
        saved = {"exit_code": 1, "elapsed_s": 1801, "artifacts": ops.manifest(self.directory)}
        ops.save(self.directory, "receipt.json", saved)
        report = self.directory.parent / (self.directory.name + "-export.json")
        self.addCleanup(lambda: report.unlink(missing_ok=True))
        with patch.object(ops, "verify", return_value=saved):
            ops.export(self.directory, report)
            raw = report.read_bytes()
            ops.export(self.directory, report)
            self.assertEqual(raw, report.read_bytes())
            report.write_text("different report")
            with self.assertRaises(ValueError):
                ops.export(self.directory, report)
            self.assertEqual(report.read_text(), "different report")

    def test_first_successful_export_shares_run_wall_clock_budget(self):
        self.assertEqual(ops.export_remaining_s({"elapsed_s": 1700}, 20), 80)
        for saved, elapsed in (({"elapsed_s": 1799}, 0), ({"elapsed_s": 1700}, 101),
                               ({"elapsed_s": float("nan")}, 0), ({"elapsed_s": -1}, 0)):
            with self.assertRaises(ValueError):
                ops.export_remaining_s(saved, elapsed)

    def test_export_closeout_failure_cannot_publish_or_reuse_success(self):
        saved = {"exit_code": 0, "elapsed_s": 10, "artifacts": {}}
        ops.save(self.directory, "receipt.json", saved)
        report = self.directory.parent / (self.directory.name + "-export.json")
        pending = report.with_name(report.stem + ".pending.json")
        self.addCleanup(lambda: report.unlink(missing_ok=True))
        self.addCleanup(lambda: pending.unlink(missing_ok=True))
        with patch.object(ops, "verify", return_value=saved), \
                patch.object(ops, "tree_memory", return_value=(ops.LIMIT_RSS + 1, ops.LIMIT_RSS + 1)):
            with self.assertRaisesRegex(ValueError, "closeout memory"):
                ops.export(self.directory, report)
            self.assertFalse(report.exists())
            self.assertTrue(pending.exists())
            with self.assertRaisesRegex(ValueError, "interrupted export preserved"):
                ops.export(self.directory, report)

    def test_source_rejects_unaccepted_r3_receipt(self):
        r3 = {"status": "failed"}
        with patch.object(ops.reader_ops, "source_inputs", return_value={}), \
                patch.object(ops, "read", return_value=r3), patch.object(ops.reader_ops, "verify") as verify:
            with self.assertRaisesRegex(ValueError, "accepted R3"):
                ops.source_inputs(self.directory)
            verify.assert_not_called()

    def test_frame_census_rejects_wrong_per_query_counts_even_with_correct_total(self):
        config = self.config()
        inputs = {"public": {w: {"relative_path": w + "/public.json", "sha256": "a" * 64, "bytes": 12}
                             for w in ("LL", "LR", "RL", "RR")}}
        jobs = ops.jobs(config, inputs, Path("/source"))
        records = {j["id"]: {"history_frames": 121 if j["indices"] is None else len(j["indices"]),
                              "prediction": {"history_frames": 121 if j["indices"] is None else len(j["indices"])},
                              "prediction_sha256": "same"} for j in jobs}
        evaluation = {"rows": [{"id": j["id"], "assessment": {"accepted": True}} for j in jobs]}
        with patch.object(ops, "read", side_effect=lambda p: records[p.stem]):
            self.assertTrue(all(ops.inventory_checks(self.directory, jobs, evaluation).values()))
            records["query-00"]["history_frames"] -= 1
            records["query-01"]["history_frames"] += 1
            checks = ops.inventory_checks(self.directory, jobs, evaluation)
            self.assertTrue(checks["exact_500_frame_consumptions"])
            self.assertFalse(checks["per_query_frame_counts"])

    def test_whole_command_memory_watch_also_covers_nonworker_work(self):
        stop = Mock()
        stop.is_set.return_value = False
        monitor = {"sampled_live_rss_peak_bytes": 0, "conservative_live_hwm_peak_bytes": 0, "error": None}
        with patch.object(ops, "MONITOR", monitor), \
                patch.object(ops, "tree_memory", return_value=(1, ops.LIMIT_RSS + 1)), patch.object(ops.os, "kill") as kill:
            ops.watch_command(stop)
            kill.assert_called_once_with(ops.os.getpid(), signal.SIGUSR1)
        stop.set.assert_called_once()
        self.assertIn("whole-command", monitor["error"])


if __name__ == "__main__":
    unittest.main()
