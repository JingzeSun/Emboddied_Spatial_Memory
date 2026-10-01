"""S2-06 tests: the run support of the one-command driver (ruling 100-6).

Pinned: worker counts follow the cgroup quota and memory (audits single-threaded, trainings TRAIN_THREADS each, at most ten);
a stage finished at an earlier commit stays done only if the commits since changed nothing but the SAM2 fit registration
and documents (otherwise refused unless the operator accepts it), a hold is redone, and the check is redone at every new
commit; a determinism probe ignores only wall time, commit, head path and timings; verify finds every training whose
weights differ from its receipt, every merged audit of the wrong source or size, and a missing or differing probe; the
driver's stage list is the helper's and every stage has its function.  CPU only, seconds (a throwaway git repository).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s2_06_manifest as support  # noqa: E402
from cpmt.hashing import canonical_json  # noqa: E402

DRIVER = PROJECT_ROOT / "ops" / "vsmt" / "s2_06_sam2.sh"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=str(repo), text=True).strip()


def weights(seed: int) -> dict:
    body = {"heads": {"association": [seed, 1, 2]}, "training": {"seed": seed}}
    return {**body, "sha256": hashlib.sha256(canonical_json({k: v for k, v in body.items() if k != "training"}).encode("utf-8")).hexdigest()}


class TestWorkers(unittest.TestCase):
    def test_the_four_gpu_instance(self) -> None:
        plan = support.plan_workers(68, 240 * 2 ** 30, audit_gib=4.0, train_gib=24.0, train_threads=4)
        self.assertEqual((plan["workers"], plan["pass_workers"], plan["train_parallel"]), (58, 39, 9))
        plan = support.plan_workers(68, 240 * 2 ** 30, audit_gib=2.0, train_gib=12.0, train_threads=4)
        self.assertEqual((plan["workers"], plan["pass_workers"], plan["train_parallel"]), (64, 39, 10))
        plan = support.plan_workers(12, 62 * 2 ** 30, audit_gib=4.0, train_gib=24.0, train_threads=4)
        self.assertEqual((plan["workers"], plan["pass_workers"], plan["train_parallel"]), (8, 8, 2))


class TestStageState(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.run = Path(self.tmp.name) / "run"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        for path in ("src/vsmt/lean_runner.py", "configs/vsmt/lean_s0_arms_v2.json", "README.md"):
            (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / path).write_text("0\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "x")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def commit(self, path: str) -> str:
        (self.repo / path).write_text((self.repo / path).read_text(encoding="utf-8") + "1\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", path)
        return git(self.repo, "rev-parse", "HEAD")

    def mark(self, stage: str, status: str = "done") -> None:
        support.write_json(support.marker_path(self.run, stage), {"stage": stage, "status": status, "commit": git(self.repo, "rev-parse", "HEAD")})

    def state(self, stage: str, accept: bool = False) -> str:
        return support.stage_state(self.run, stage, git(self.repo, "rev-parse", "HEAD"), self.repo, accept)[0]

    def test_registration_and_documents_keep_a_stage_code_does_not(self) -> None:
        self.assertEqual(self.state("calibration"), "todo")
        self.mark("calibration")
        self.mark("check")
        self.mark("elu-p-fit", status="hold")
        self.assertEqual((self.state("calibration"), self.state("check"), self.state("elu-p-fit")), ("done", "done", "todo"))
        self.commit("configs/vsmt/lean_s0_arms_v2.json")  # the SAM2 fit registration
        self.commit("README.md")
        self.assertEqual((self.state("calibration"), self.state("check")), ("done", "todo"))  # the check is redone at a new commit
        self.commit("src/vsmt/lean_runner.py")
        self.assertEqual(self.state("calibration"), "blocked")
        self.assertEqual(self.state("calibration", accept=True), "done")


class TestProbeAndVerify(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_probe_ignores_only_volatile_fields(self) -> None:
        audit = {"schema_version": "v", "episode_id": "e1", "wall_seconds": 10.0, "code_commit": "a", "heads": "/x/w.json",
                 "final_memory_digest": "d1", "report": {"node_prf1": {"node_f1": 0.8},
                                                         "size_and_cost": {"active_entity_count": 3.0, "lifecycle_version_count": 2.0,
                                                                           "runtime_per_frame_s": 0.1, "peak_memory_bytes": 5}}}
        again = copy.deepcopy(audit)
        again.update(wall_seconds=12.0, code_commit="b", heads="/y/w.json")
        again["report"]["size_and_cost"].update(runtime_per_frame_s=0.3, peak_memory_bytes=9)
        original, rerun, out = self.root / "o.json", self.root / "r.json", self.root / "p.json"
        original.write_text(json.dumps(audit), encoding="utf-8")
        rerun.write_text(json.dumps(again), encoding="utf-8")
        self.assertEqual(support.main(["probe", "--rerun", str(rerun), "--original", str(original), "--out", str(out)]), 0)
        again["final_memory_digest"] = "d2"
        rerun.write_text(json.dumps(again), encoding="utf-8")
        self.assertEqual(support.main(["probe", "--rerun", str(rerun), "--original", str(original), "--out", str(out)]), 3)
        again["report"]["size_and_cost"]["active_entity_count"] = 4.0  # a decided quantity, not a timing
        again["final_memory_digest"] = "d1"
        rerun.write_text(json.dumps(again), encoding="utf-8")
        self.assertEqual(support.main(["probe", "--rerun", str(rerun), "--original", str(original), "--out", str(out)]), 3)
        merged = self.root / "m.json"  # against a merged export row: the seven-metric report without size and cost
        merged.write_text(json.dumps({"per_episode": [{"episode_id": "e1", "report": audit["report"]}]}), encoding="utf-8")
        self.assertEqual(support.main(["probe", "--rerun", str(rerun), "--merged", str(merged), "--out", str(out)]), 0)

    def build_run(self) -> tuple[Path, Path]:
        run, exports = self.root / "run", self.root / "exports"
        for stage in support.STAGES[:-1]:
            support.write_json(support.marker_path(run, stage), {"stage": stage, "status": "done", "commit": "c"})
        for directory in ["round0/VSMT-lean", "round0/AssocOnly"] + [f"round1/{a}/A{s}" for a in ("VSMT-lean", "AssocOnly") for s in support.SEEDS]:
            payload = weights(len(directory))
            receipt = {"weights_sha256": payload["sha256"], "best_epoch": 0, "code_commit": "c", "validation_curve_terms": [{"association": 1.0}]}
            if directory.startswith("round1/VSMT-lean"):
                grouped = weights(len(directory) + 1)
                support.write_json(run / "training" / directory / "weights_grouped.json", grouped)
                receipt["group_selection"] = {"weights_sha256": grouped["sha256"]}
            support.write_json(run / "training" / directory / "weights.json", payload)
            support.write_json(run / "training" / directory / "training_receipt.json", receipt)
        for group in support.AUDIT_GROUPS + support.INSTANCE_GROUPS:
            source = support.INSTANCE if group.startswith("INSTANCE-") else support.SAM2
            support.write_json(exports / f"vsmt_lean_s2_06_audit_{group}_t1.json",
                               {"mask_source": source, "episodes": 39, "arm": support.GROUP_ARM[group], "code_commits": ["c"]})
        for name in ("sam2", "instance"):
            support.write_json(run / "verify" / f"probe_{name}.json", {"identical": True})
        return run, exports

    def test_verify_checks_every_recorded_digest(self) -> None:
        run, exports = self.build_run()
        self.assertEqual(support.verify(run, exports, "t1", PROJECT_ROOT)["problems"], [])
        payload = json.loads((run / "training" / "round1" / "AssocOnly" / "A31" / "weights.json").read_text(encoding="utf-8"))
        payload["heads"]["association"][0] = 999  # the file no longer matches its own digest or the receipt
        support.write_json(run / "training" / "round1" / "AssocOnly" / "A31" / "weights.json", payload)
        support.write_json(exports / "vsmt_lean_s2_06_audit_NOVER-A7_t1.json", {"mask_source": "simulator_instance_masks", "episodes": 39,
                                                                               "arm": "NoVersion", "code_commits": ["c"]})
        support.write_json(run / "verify" / "probe_sam2.json", {"identical": False})
        support.write_json(support.marker_path(run, "audits"), {"stage": "audits", "status": "failed", "commit": "c"})
        problems = support.verify(run, exports, "t1", PROJECT_ROOT)["problems"]
        self.assertEqual(sorted(problems), sorted(["stage_not_done:audits", "weights_differ_from_the_receipt:training/round1/AssocOnly/A31",
                                                   "merged_audit_inconsistent:NOVER-A7", "determinism_probe_differs:sam2"]))


class TestDriver(unittest.TestCase):
    def test_the_driver_runs_the_helpers_stages_each_with_its_function(self) -> None:
        text = DRIVER.read_text(encoding="utf-8")
        stages = re.search(r'^STAGES="([^"]+)"', text, re.M).group(1).split()
        self.assertEqual(tuple(stages), support.STAGES)
        for stage in stages:
            self.assertRegex(text, rf"(?m)^stage_{stage.replace('-', '_')}\(\) \{{", stage)
        self.assertNotIn("\r\n", DRIVER.read_bytes().decode("utf-8"))
        self.assertIn("--mask-source sam2", text)
        self.assertIn("--revision-91", text)


if __name__ == "__main__":
    unittest.main()
