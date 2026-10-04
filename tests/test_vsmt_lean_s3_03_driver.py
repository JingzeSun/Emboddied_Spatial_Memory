"""Ruling 104-7 / 104-2 tests for the S3-03 driver: the job pool (ops/vsmt/s3_03_jobs.py) and the run's graph and job
subcommands (ops/vsmt/s3_03_manifest.py).

Pinned with fake processes (no real job runs): the pool starts ready jobs by priority and cost, lends no core a waiting
higher job needs, reruns a crashed training once with its partial output set aside, skips what a diverged training feeds
while a job with soft dependencies still runs, stops new work after a gate failure or a failure (a refusal is never
rerun), resumes over finished jobs, sets interrupted ones aside, refuses a code change unless accepted, measures memory
per class, pins one thread per ordinary job; the thread choice of ruling 104-3.  On a fake S3-02 tree with real manifest
ids, check accepts consistent inputs and names each kind of inconsistency; the whole graph runs to the end under fake
processes with every ordering the protocol needs, and each kind of command carries the registered options.  On synthetic
outputs, the fit, the round-0 gate and the readings subcommands write what the next jobs read.  CPU, seconds.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_03_jobs as pool  # noqa: E402
import s3_03_manifest as driver  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402

MANIFEST = s3.load_manifest()


class FakeProcess:
    def __init__(self, code: int, polls: int = 1) -> None:
        self.code, self.polls = code, polls

    def poll(self):
        if self.polls > 0:
            self.polls -= 1
            return None
        return self.code


class FakeLauncher:
    """Starts nothing: records the order and the environment, returns a process that ends after one poll."""

    def __init__(self, codes: dict | None = None, effects: dict | None = None) -> None:
        self.codes = {key: list(value) for key, value in (codes or {}).items()}
        self.effects = effects or {}
        self.started: list[str] = []
        self.envs: dict[str, dict] = {}

    def __call__(self, argv, *, log, env):
        job_id = Path(log).stem.replace("__", "/")  # the pool names each job's log after its id
        self.started.append(job_id)
        self.envs[job_id] = dict(env)
        if job_id in self.effects:
            self.effects[job_id](argv)
        codes = self.codes.get(job_id)
        return FakeProcess(codes.pop(0) if codes else 0), None


def job(job_id: str, *, deps=(), priority=1, cost=1.0, cores=1, memory="pass", **extra) -> pool.Job:
    return pool.Job(job_id, extra.pop("kind", "k"), tuple(deps), priority, cost, cores, memory, lambda j=job_id: ["job", j], **extra)


class PoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pool(self, jobs, launcher, **options) -> pool.Pool:
        values = dict(run_root=self.tmp / "run", log_dir=self.tmp / "logs", budget_cores=4, budget_gib=64.0,
                      memory_defaults={"pass": 4.0, "train": 8.0, "small": 1.0}, train_threads=lambda: 4, commit="c1",
                      launch=launcher, sleep=lambda seconds: None, memory_limit_bytes=None)
        values.update(options)
        return pool.Pool(jobs, **values)

    def test_priority_cost_and_reservation(self) -> None:
        launcher = FakeLauncher()
        jobs = [job("a", cores=2, cost=10), job("b", deps=("a",), cores=2), job("t", deps=("a",), cores=4, cost=1e12),
                job("r1", priority=3), job("r2", priority=3), job("r3", priority=3)]
        self.assertEqual(self.pool(jobs, launcher).run(), 0)
        self.assertEqual(launcher.started, ["a", "r1", "r2", "t", "b", "r3"])
        launcher = FakeLauncher()
        jobs = [job("x", priority=3, cores=1), job("t", deps=("gate",), cores=4), job("gate", priority=0, cores=1),
                job("y", deps=("gate",), priority=3)]
        self.assertEqual(self.pool(jobs, launcher, run_root=self.tmp / "second").run(), 0)
        self.assertLess(launcher.started.index("t"), launcher.started.index("y"))  # y never takes a core t is waiting for

    def test_ready_jobs_go_by_rank_then_readiness_then_group_then_length(self) -> None:
        launcher = FakeLauncher()
        jobs = [job("x", priority=0, cost=0), job("a1", cost=5, group="instance"), job("a2", cost=4, group="instance"),
                job("b", deps=("x",), cost=100, group="instance")]
        self.assertEqual(self.pool(jobs, launcher, budget_cores=1).run(), 0)
        self.assertEqual(launcher.started, ["x", "a1", "a2", "b"])  # b became ready later: its length does not let it jump ahead
        launcher = FakeLauncher()
        jobs = [job("s", cost=10, group="sam2"), job("i", cost=1, group="instance"), job("x", priority=0, cost=0),
                job("t", deps=("x",), rank=0, cost=1, group="sam2")]
        runner = self.pool(jobs, launcher, run_root=self.tmp / "groups", budget_cores=1, group_order=("instance", "sam2"))
        self.assertEqual(runner.run(), 0)
        self.assertEqual(launcher.started, ["x", "t", "i", "s"])  # a training first, then the first front end's job

    def test_round_one_memory_is_estimated_from_round_zero_until_measured(self) -> None:
        runner = self.pool([job("p")], FakeLauncher(), memory_fallbacks={"train1": ("train0", 2.0)}, memory_defaults={"train0": 24.0, "train1": 24.0})
        self.assertEqual(runner.gib_for("train1"), 24.0)
        runner.measured["train0"] = 4 * 2 ** 30
        self.assertEqual(runner.gib_for("train1"), 10.0)  # 1.25 x 2 x 4 GiB
        runner.measured["train1"] = 6 * 2 ** 30
        self.assertEqual(runner.gib_for("train1"), 7.5)  # its own measurement wins

    def test_the_disk_floor_grows_with_the_running_jobs(self) -> None:
        launcher = FakeLauncher()

        class Long(FakeLauncher):
            def __call__(inner, argv, *, log, env):
                process, handle = super().__call__(argv, log=log, env=env)
                process.polls = 10 ** 6
                return process, handle

        free = shutil.disk_usage(self.tmp).free / 2 ** 30
        runner = self.pool([job("a"), job("b")], Long(), disk_root=self.tmp, min_free_gib=0.0, inflight_gib=0.6 * free)
        runner.load()
        self.assertEqual(runner.dispatch(), ["a"])  # room for what one job may write, not for two
        self.assertEqual(runner.dispatch(), [])
        self.assertIsNone(runner.stop_reason)  # a pause while a job runs, not a stop
        runner = self.pool([job("a")], Long(), run_root=self.tmp / "full", disk_root=self.tmp, min_free_gib=0.0, inflight_gib=2 * free)
        runner.load()
        self.assertEqual(runner.dispatch(), [])
        self.assertTrue(runner.stop_reason.startswith("disk_below_"))  # nothing runs and nothing fits: stop

    def test_the_wrapper_records_the_exit_and_passes_it_on(self) -> None:
        out = self.tmp / "rss.json"
        self.assertEqual(pool.run_measured(["--out", str(out), "--", sys.executable, "-c", "import sys; sys.exit(4)"]), 4)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["exit"], 4)
        with self.assertRaises(pool.PoolError):
            pool.run_measured(["--", "x"])

    def test_a_crashed_training_reruns_once_with_its_partial_output_set_aside(self) -> None:
        out = self.tmp / "training" / "s7"

        def partial(argv):
            out.mkdir(parents=True, exist_ok=True)
            (out / "weights.json").write_text("partial", encoding="utf-8")

        launcher = FakeLauncher(codes={"t": [-9, 0]}, effects={"t": partial})
        runner = self.pool([job("t", cores=None, memory="train", outputs=(str(out),), retries=1, exit_status={3: "diverged"})], launcher)
        self.assertEqual(runner.run(), 0)
        state = json.loads((self.tmp / "run" / "jobs" / "t.json").read_text(encoding="utf-8"))
        self.assertEqual((state["status"], state["attempts"]), ("done", 2))
        self.assertEqual(state["history"][0]["status"], "failed_then_rerun")
        self.assertTrue((self.tmp / "run" / "failed" / "t-attempt1" / "s7" / "weights.json").exists())
        self.assertEqual(launcher.envs["t"]["OMP_NUM_THREADS"], "4")  # a training gets TRAIN_THREADS

    def test_a_resumable_training_keeps_its_checkpoint_after_a_crash_or_an_interruption(self) -> None:
        out = self.tmp / "training" / "s7"

        def partial(argv):
            (out / "checkpoint").mkdir(parents=True, exist_ok=True)
            (out / "checkpoint" / "state.pt").write_text("epoch 5", encoding="utf-8")

        launcher = FakeLauncher(codes={"t": [-9, 0]}, effects={"t": partial})
        spec = dict(cores=None, memory="train", outputs=(str(out),), retries=1, exit_status={3: "diverged"}, resumable=True)
        self.assertEqual(self.pool([job("t", **spec)], launcher).run(), 0)
        self.assertEqual(launcher.started, ["t", "t"])
        self.assertTrue((out / "checkpoint" / "state.pt").exists())  # the rerun continues from it
        self.assertFalse((self.tmp / "run" / "failed").exists())
        state_dir = self.tmp / "run" / "jobs"
        pool.write_json(state_dir / "t.json", {"job_id": "t", "status": "running", "commit": "c1", "attempts": 2, "history": []})
        launcher = FakeLauncher()
        self.assertEqual(self.pool([job("t", **spec)], launcher).run(), 0)
        self.assertEqual(launcher.started, ["t"])
        self.assertTrue((out / "checkpoint" / "state.pt").exists())
        self.assertFalse((self.tmp / "run" / "interrupted").exists())

    def test_a_drain_starts_nothing_more_and_ends_when_the_running_jobs_end(self) -> None:
        run_root = self.tmp / "run"

        class Draining(FakeLauncher):
            def __call__(self, argv, *, log, env):
                process, handle = super().__call__(argv, log=log, env=env)
                process.polls = 3
                (run_root / pool.DRAIN_FILE).write_text("", encoding="utf-8")  # asked for while the first job runs
                return process, None

        launcher = Draining()
        runner = self.pool([job("a", cores=4), job("b"), job("c", deps=("a",))], launcher)
        self.assertEqual(runner.run(), 1)
        self.assertEqual(launcher.started, ["a"])
        self.assertEqual((runner.stop_reason, runner.status("a"), runner.status("b"), runner.status("c")), ("drained", "done", "pending", "pending"))
        again = FakeLauncher()
        self.assertEqual(self.pool([job("a", cores=4), job("b"), job("c", deps=("a",))], again).run(), 1)  # the file still stands
        self.assertEqual(again.started, [])
        (run_root / pool.DRAIN_FILE).unlink()
        self.assertEqual(self.pool([job("a", cores=4), job("b"), job("c", deps=("a",))], again).run(), 0)
        self.assertEqual(sorted(again.started), ["b", "c"])

    def test_divergence_skips_what_it_feeds_and_soft_dependents_still_run(self) -> None:
        launcher = FakeLauncher(codes={"t": [3]})
        jobs = [job("t", exit_status={3: "diverged"}), job("audit", deps=("t",)), job("merge", deps=("audit",)),
                job("rule"), job("merge-rule", deps=("rule",)), job("readings", soft_deps=("merge", "merge-rule"))]
        runner = self.pool(jobs, launcher)
        self.assertEqual(runner.run(), 0)
        self.assertEqual({j: runner.status(j) for j in runner.jobs},
                         {"t": "diverged", "audit": "skipped", "merge": "skipped", "rule": "done", "merge-rule": "done", "readings": "done"})
        self.assertEqual(launcher.envs["rule"]["OMP_NUM_THREADS"], "1")

    def test_a_gate_failure_or_a_failure_stops_new_work_and_a_refusal_is_not_rerun(self) -> None:
        launcher = FakeLauncher(codes={"gate": [3]})
        runner = self.pool([job("gate", priority=0, exit_status={3: "gate_failed"}), job("later", priority=3)], launcher, budget_cores=1)
        self.assertEqual(runner.run(), 3)
        self.assertEqual(launcher.started, ["gate"])
        self.assertTrue(runner.stop_reason.startswith("gate_failed:gate"))
        launcher = FakeLauncher(codes={"t": [2]})
        runner = self.pool([job("t", retries=1), job("after", deps=("t",))], launcher, run_root=self.tmp / "refusal")
        self.assertEqual(runner.run(), 1)
        self.assertEqual((runner.status("t"), launcher.started), ("failed", ["t"]))
        again = FakeLauncher()
        runner = self.pool([job("t", retries=1), job("after", deps=("t",))], again, run_root=self.tmp / "refusal")
        self.assertEqual(runner.run(), 2)  # a failed job is never rerun by itself, and a resume stops before it again
        self.assertEqual(runner.stop_reason, "blocked:stopped_before:failed:t")
        self.assertEqual(again.started, [])
        runner = self.pool([job("t", retries=1), job("after", deps=("t",))], again, run_root=self.tmp / "refusal", retry_failed=True)
        self.assertEqual(runner.run(), 0)
        self.assertEqual(again.started, ["t", "after"])
        launcher = FakeLauncher(codes={"reading": [1]})  # a report-only job's failure is recorded and the run goes on
        runner = self.pool([job("reading", stops_on_failure=False), job("work", priority=3)], launcher, run_root=self.tmp / "report")
        self.assertEqual(runner.run(), 0)
        self.assertEqual((runner.status("reading"), runner.status("work"), runner.stop_reason), ("failed", "done", None))

    def test_a_resume_stops_again_before_a_failed_gate_unless_retried(self) -> None:
        jobs = [job("probe", priority=0, exit_status={3: "gate_failed"}), job("train", priority=1), job("reading", stops_on_failure=False)]
        launcher = FakeLauncher(codes={"probe": [3], "reading": [1]})
        root = self.tmp / "gate"
        self.assertEqual(self.pool(jobs, launcher, run_root=root, budget_cores=1).run(), 3)
        again = FakeLauncher()
        runner = self.pool(jobs, again, run_root=root)
        self.assertEqual(runner.run(), 2)
        self.assertEqual(runner.stop_reason, "blocked:stopped_before:gate_failed:probe")  # the report-only failure blocks nothing
        self.assertEqual(again.started, [])
        runner = self.pool(jobs, again, run_root=root, retry_failed=True)
        self.assertEqual(runner.run(), 0)
        self.assertEqual(sorted(again.started), ["probe", "reading", "train"])

    def test_resume_keeps_finished_jobs_sets_interrupted_ones_aside_and_guards_code_changes(self) -> None:
        state_dir = self.tmp / "run" / "jobs"
        state_dir.mkdir(parents=True)
        out = self.tmp / "out-b"
        out.mkdir()
        (out / "half.json").write_text("{", encoding="utf-8")
        pool.write_json(state_dir / "a.json", {"job_id": "a", "status": "done", "commit": "c0", "attempts": 1, "history": []})
        pool.write_json(state_dir / "b.json", {"job_id": "b", "status": "running", "commit": "c0", "attempts": 1, "history": []})
        jobs = [job("a"), job("b", deps=("a",), outputs=(str(out),))]
        blocked = self.pool(jobs, FakeLauncher(), code_change=lambda commit: ["src/vsmt/lean_runner.py"])
        self.assertEqual(blocked.run(), 2)
        self.assertIn("code_changed_since:c0", blocked.stop_reason)
        launcher = FakeLauncher()
        runner = self.pool(jobs, launcher, code_change=lambda commit: ["src/vsmt/lean_runner.py"], accept_code_change=True)
        self.assertEqual(runner.run(), 0)
        self.assertEqual(launcher.started, ["b"])
        self.assertTrue((self.tmp / "run" / "interrupted" / "b-attempt1" / "out-b" / "half.json").exists())
        state = json.loads((state_dir / "b.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["status"] for entry in state["history"]], ["interrupted"])
        pool.write_json(state_dir / "t.json", {"job_id": "t", "status": "running", "commit": "c1", "attempts": 1, "history": []})
        launcher = FakeLauncher(codes={"t": [-9, 0]})  # interrupted once, then a crash: the crash still gets its rerun
        runner = self.pool([job("t", retries=1)], launcher)
        self.assertEqual(runner.run(), 0)
        state = json.loads((state_dir / "t.json").read_text(encoding="utf-8"))
        self.assertEqual((state["status"], state["attempts"], state["crashes"]), ("done", 3, 1))

    def test_memory_is_measured_per_class_and_the_disk_floor_stops(self) -> None:
        def measured(argv):
            pool.write_json(self.tmp / "run" / "jobs" / "p.rss.json", {"max_rss_children_bytes": 6 * 2 ** 30})

        guarded = self.pool([job("g"), job("h", priority=3)], FakeLauncher(), run_root=self.tmp / "guarded", budget_cores=1,
                            memory_limit_bytes=1, memory_now=lambda: 2)
        guarded.load()
        self.assertEqual(guarded.dispatch(), ["g"])  # nothing of the pool's own runs: memory held elsewhere is no reason to wait
        guarded.budget_cores = 2
        self.assertEqual(guarded.dispatch(), [])
        self.assertTrue(guarded.memory_paused)  # above the line while its jobs run: nothing new starts, nothing running stops
        runner = self.pool([job("p")], FakeLauncher(effects={"p": measured}))
        self.assertEqual(runner.gib_for("pass"), 4.0)
        self.assertEqual(runner.run(), 0)
        self.assertEqual(runner.gib_for("pass"), 7.5)  # 1.25 x 6 GiB, rounded up to half a GiB
        self.assertEqual(json.loads((self.tmp / "run" / "memory_classes.json").read_text(encoding="utf-8"))["peak_bytes"]["pass"], 6 * 2 ** 30)
        launcher = FakeLauncher()
        runner = self.pool([job("q")], launcher, disk_root=self.tmp, min_free_gib=1e12)
        self.assertEqual(runner.run(), 1)
        self.assertEqual(launcher.started, [])
        self.assertTrue(runner.stop_reason.startswith("disk_below"))

    def test_a_fixed_reservation_replaces_the_measured_peak_and_the_fallback(self) -> None:
        # user 2026-10-04 on the memory-bound CPU host: MEMORY_FIXED_GIB reserves exactly what the operator names
        runner = self.pool([job("p")], FakeLauncher(), memory_fallbacks={"train1": ("pass", 2.0)},
                           memory_fixed={"train1": 5.5, "pass": 1.5, "huge": 1e6})
        runner.measured["pass"] = 6 * 2 ** 30
        self.assertEqual(runner.gib_for("pass"), 1.5)  # not 7.5 (1.25 x the measured 6 GiB)
        self.assertEqual(runner.gib_for("train1"), 5.5)  # not the 2 x fallback
        self.assertEqual(runner.gib_for("huge"), 64.0)  # never above the budget
        self.assertEqual(runner.gib_for("small"), 1.0)  # an unnamed class keeps the measured/default rule

    def test_the_thread_choice(self) -> None:
        choice = pool.choose_train_threads({1: 10.0, 2: 6.0, 3: 5.0, 4: 4.0}, cores=100)
        self.assertEqual(choice["train_threads"], 3)  # 4 threads fit only 25 at once: two waves of 4 s (8) lose to one of 5 s
        self.assertEqual([row["waves"] for row in choice["candidates"]], [1, 1, 1, 2])
        self.assertEqual(pool.choose_train_threads({1: 2.0, 2: 2.0}, cores=100)["train_threads"], 1)  # ties to fewer threads
        self.assertEqual(pool.choose_train_threads({1: 10.0, 4: 3.0}, cores=8, trainings=30)["train_threads"], 1)  # 4 waves x 10 < 15 x 3
        self.assertEqual(pool.choose_train_threads({1: 10.0, 4: 2.0}, cores=8, trainings=30)["train_threads"], 4)  # 15 x 2 < 4 x 10
        with self.assertRaises(pool.PoolError):
            pool.choose_train_threads({}, cores=8)


def fake_inputs(root: Path, *, fronts=("instance", "sam2")) -> dict:
    train = MANIFEST["train"][:3] + MANIFEST["train"][240:242]
    validation = MANIFEST["validation"][:2]
    return {"code_commit": "c1", "fronts": list(fronts), "problems": [],
            "roots": {"raw": {split: str(root / "raw" / split) for split in driver.SPLITS},
                      "geometry": {split: str(root / "geometry" / split) for split in driver.SPLITS},
                      "cache": {front: {split: str(root / "cache" / front / split) for split in driver.SPLITS} for front in fronts}},
            "reid": {front: {"file": str(root / f"reid_{front}.json")} for front in fronts},
            "episodes": {front: {"train": [{"episode_id": house, "frames": 100 + i} for i, house in enumerate(train)],
                                 "validation": [{"episode_id": house, "frames": 50 + i} for i, house in enumerate(validation)]}
                         for front in fronts}}


VALUES = {"initial_log_odds": 4.7, "persistence_log_decay_per_tick": 2e-05, "match_gain": 3.5}


def write_fit(ctx: driver.RunContext, front: str) -> None:
    pool.write_json(ctx.fit_values_path(front), {"front": front, "mask_source": driver.FRONTS[front], "values": VALUES,
                                                 "values_sha256": driver.canonical_sha256(VALUES)})


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.ctx = driver.RunContext(run_root=self.tmp / "run", inputs=fake_inputs(self.tmp), python="py")
        self.jobs = {job.job_id: job for job in driver.build_jobs(self.ctx)}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def argv(self, job_id: str) -> list[str]:
        return self.jobs[job_id].build()

    def option(self, argv: list[str], name: str) -> str:
        return argv[argv.index(name) + 1]

    def test_the_graph_counts(self) -> None:
        kinds: dict[str, int] = {}
        for job in self.jobs.values():
            kinds[job.kind] = kinds.get(job.kind, 0) + 1
        self.assertEqual(kinds, {"probe_audit": 2, "calibration": 10, "fit": 2, "round0": 10, "gate_round0": 2, "probe_train": 2,
                                 "train0": 6, "round1": 30, "train1": 30, "coverage": 2, "audit": 212, "merge": 416, "readings": 2,
                                 "probe_determinism": 2, "timing": 1, "train_threads": 1, "grid_reading": 1})
        self.assertEqual(len(self.jobs["instance/readings"].soft_deps), 208)
        self.assertIn("instance/probe-train", self.jobs["instance/t0/VSMT-lean"].deps)  # ruling 104-2: certified before it trains
        audits = [job for job in self.jobs.values() if job.kind == "audit"]
        self.assertTrue(all(f"{job.group}/probe-audit" in job.deps for job in audits))
        self.assertEqual({job.rank for job in self.jobs.values() if job.kind in ("train0", "train1")}, {0})
        self.assertEqual((self.jobs["sam2/r0/" + MANIFEST["train"][0]].group, self.jobs["timing"].group), ("sam2", ""))
        self.assertEqual(self.jobs["timing"].deps, tuple(f"instance/r0/{house}" for house in MANIFEST["train"][:3] + MANIFEST["train"][240:242]))

    def test_every_pass_job_writes_under_its_own_front(self) -> None:
        # 2026-10-04 on the S3-02 host: the round-0 builder read its output root from the enclosing loop at dispatch time, so the
        # instance round-0 jobs wrote into sam2/round0 and the SAM2 jobs of the same episodes failed; every builder binds it now
        for front in driver.FRONTS:
            write_fit(self.ctx, front)
        checked = 0
        for job in self.jobs.values():
            if job.kind not in ("calibration", "round0", "round1"):
                continue
            output = Path(self.option(self.argv(job.job_id), "--output-root"))
            self.assertEqual(output.relative_to(self.ctx.run_root).parts[0], job.job_id.split("/", 1)[0], job.job_id)
            checked += 1
        self.assertEqual(checked, 50)

    def test_the_whole_graph_runs_in_protocol_order_under_fake_processes(self) -> None:
        effects = {"instance/fit": lambda argv: write_fit(self.ctx, "instance"), "sam2/fit": lambda argv: write_fit(self.ctx, "sam2"),
                   "train-threads": lambda argv: pool.write_json(self.ctx.run_root / "train_threads.json", {"train_threads": 3})}

        launcher = FakeLauncher(effects=effects)
        jobs = list(self.jobs.values())
        runner = pool.Pool(jobs, run_root=self.ctx.run_root, log_dir=self.tmp / "logs", budget_cores=64, budget_gib=1024.0,
                           memory_defaults=driver.MEMORY_DEFAULTS_GIB, train_threads=self.ctx.train_threads, commit="c1",
                           launch=launcher, sleep=lambda seconds: None, memory_limit_bytes=None)
        self.assertEqual(runner.run(), 0, runner.stop_reason)
        self.assertTrue(all(runner.status(job_id) == "done" for job_id in self.jobs))
        order = {job_id: index for index, job_id in enumerate(launcher.started)}
        for job_id, job in self.jobs.items():
            for dep in (*job.deps, *job.soft_deps):
                self.assertLess(order[dep], order[job_id], f"{dep} before {job_id}")
        for front in ("instance", "sam2"):
            self.assertLess(order[f"{front}/t1/VSMT-lean/s31"], order[f"{front}/audit/NoVersion/s31/c05-09/{MANIFEST['validation'][0]}"])
            self.assertLess(order[f"{front}/fit"], order[f"{front}/audit/ELU-P/rule/c09-11/{MANIFEST['validation'][0]}"])

    def test_each_kind_of_command_carries_the_registered_options(self) -> None:
        write_fit(self.ctx, "instance")
        pool.write_json(self.ctx.run_root / "train_threads.json", {"train_threads": 3})
        house, episode = MANIFEST["train"][0], MANIFEST["validation"][1]
        argv = self.argv(f"instance/cal/{house}")
        self.assertEqual((self.option(argv, "--arm"), json.loads(self.option(argv, "--config"))), ("TAF", {"theta_a": 0.7, "d_a": None}))
        self.assertEqual(self.option(argv, "--manifest-split"), "train")
        for flag in ("--calibration", "--elu-p-counts", "--no-training-records"):
            self.assertIn(flag, argv)
        rollout = {"theta_a": 0.7, "free_space_weight": 1.0, "retract_threshold": 0.0, "d_a": None, **VALUES}
        argv = self.argv(f"instance/r0/{house}")
        self.assertEqual((self.option(argv, "--arm"), json.loads(self.option(argv, "--config"))), ("ELU-P", rollout))
        self.assertEqual(json.loads(self.option(argv, "--heuristic-labels")), rollout)
        self.assertNotIn("--no-training-records", argv)
        argv = self.argv(f"instance/r1/HeuristicLabel/{house}")
        self.assertEqual(json.loads(self.option(argv, "--config")), {"tau_r": 0.5})
        self.assertEqual(self.option(argv, "--heads"), str(self.ctx.run_root / "instance/training/round0/HeuristicLabel/s7/weights.json"))
        self.assertEqual(json.loads(self.option(argv, "--heuristic-labels")), rollout)
        self.assertIn("--no-training-records", argv)
        argv = self.argv(f"instance/r1/AssocOnly/{house}")
        self.assertEqual((json.loads(self.option(argv, "--config")), "--heuristic-labels" in argv), ({}, False))
        argv = self.argv("instance/t1/VSMT-lean/s19")
        self.assertEqual([argv[i + 1] for i, a in enumerate(argv) if a == "--source"],
                         [f"{self.ctx.run_root / 'instance' / 'round0'}:ELU-P:teacher", f"{self.ctx.run_root / 'instance' / 'round1'}:VSMT-lean:teacher"])
        self.assertEqual((self.option(argv, "--threads"), self.option(argv, "--seed"), self.option(argv, "--round")), ("3", "19", "1"))
        for job_id in ("instance/t1/VSMT-lean/s19", "instance/t0/AssocOnly", "instance/probe-train", "timing"):
            self.assertIn("--foreach", self.argv(job_id))  # ruling 104-7: pinned by the suite, probed on real records
        jobs = {j.job_id: j for j in driver.build_jobs(self.ctx)}
        for job_id, item in jobs.items():  # user 2026-10-04: every training continues from its checkpoint, nothing else does
            self.assertEqual(item.resumable, item.kind in ("train0", "train1"), job_id)
        for job_id in ("instance/t1/VSMT-lean/s19", "instance/t0/AssocOnly"):
            self.assertIn("--checkpoint", self.argv(job_id))
        argv = self.argv("instance/t0/HeuristicLabel")
        self.assertEqual([argv[i + 1] for i, a in enumerate(argv) if a == "--source"], [f"{self.ctx.run_root / 'instance' / 'round0'}:ELU-P:heuristic"])
        argv = self.argv(f"instance/audit/NoVersion/s31/c00-04/{episode}")
        self.assertEqual(self.option(argv, "--heads"), str(self.ctx.run_root / "instance/training/round1/VSMT-lean/s31/weights_grouped.json"))
        entries = json.loads(self.option(argv, "--configs"))
        self.assertEqual([e["config"] for e in entries], [{"tau_r": v} for v in arms.FROZEN_GRIDS["NoVersion"]["tau_r"][:5]])
        self.assertEqual(entries[3]["output_root"], str(self.ctx.run_root / "instance/audit/NoVersion-c03-s31"))
        entries = json.loads(self.option(self.argv(f"instance/audit/NoVersion/s31/c05-09/{episode}"), "--configs"))
        self.assertEqual(entries[0]["output_root"], str(self.ctx.run_root / "instance/audit/NoVersion-c05-s31"))
        for flag in ("--metrics-only", "--skip-existing"):
            self.assertIn(flag, argv)
        self.assertEqual(self.option(argv, "--manifest-split"), "validation")
        argv = self.argv(f"instance/audit/AssocOnly/s7/c00-00/{episode}")
        self.assertEqual(self.option(argv, "--heads"), str(self.ctx.run_root / "instance/training/round1/AssocOnly/s7/weights.json"))
        self.assertEqual(json.loads(self.option(argv, "--configs")), [{"config": {}, "output_root": str(self.ctx.run_root / "instance/audit/AssocOnly-c00-s7")}])
        argv = self.argv(f"instance/audit/ELU-P/rule/c00-02/{episode}")
        entries = json.loads(self.option(argv, "--configs"))
        self.assertEqual(len(entries), 3)  # ruling 104-7: at most three configurations per rule-arm audit job
        self.assertEqual(len(json.loads(self.option(self.argv(f"instance/audit/LOW/rule/c03-04/{episode}"), "--configs"))), 2)
        self.assertTrue(all({k: e["config"][k] for k in VALUES} == VALUES for e in entries))
        self.assertNotIn("--heads", argv)
        argv = self.argv("instance/merge/RAC-c05")
        self.assertEqual((self.option(argv, "--arm"), self.option(argv, "--results")), ("RAC", str(self.ctx.run_root / "instance/merged/RAC-c05.json")))


class CheckTests(unittest.TestCase):
    """A fake S3-02 tree with real manifest ids: check accepts it and names each kind of inconsistency."""

    TAG = "abc1234"

    def setUp(self) -> None:
        from vsmt import lean_object_geometry as og
        from vsmt import lean_test_seal

        self.tmp = Path(tempfile.mkdtemp())
        self.autodl = self.tmp / "autodl"
        self.roots = driver.s3_02_roots(self.autodl, self.TAG)
        self.export_dir = self.tmp / "exports"
        self.export_dir.mkdir()
        self.houses = {"train": MANIFEST["train"][:4], "validation": MANIFEST["validation"][:2]}
        exports = {}

        def export(part, payload):
            path = self.export_dir / f"vsmt_lean_s3_02_{part}_{self.TAG}.json"
            pool.write_json(path, payload)
            exports[path.name] = {"sha256": driver.sha256_file(path)}

        splits = {}
        for split, houses in self.houses.items():
            raw_rows = []
            for house in houses:
                receipt = Path(self.roots["raw"]) / split / house / "receipt.json"
                pool.write_json(receipt, {"house_id": house, "status": "succeeded"})
                raw_rows.append({"house_id": house, "status": "succeeded", "receipt_sha256": driver.sha256_file(receipt)})
                pool.write_json(Path(self.roots["geometry"]) / split / house / og.TABLE_FILE_NAME, {"episode_id": house})
                pool.write_json(Path(self.roots["geometry"]) / split / house / "receipt.json", {"status": "succeeded"})  # read by a provisional check
            export(f"raw_{split}", {"houses": raw_rows})
            pool.write_json(Path(self.roots["geometry"]) / split / "s1_04_geometry_receipt.json", {"split": split})
            shutil.copy2(Path(self.roots["geometry"]) / split / "s1_04_geometry_receipt.json", self.export_dir / "tmp.json")
            export(f"geometry_{split}", json.loads((self.export_dir / "tmp.json").read_text(encoding="utf-8")))
            (self.export_dir / "tmp.json").unlink()
            counts = {"raw_succeeded": len(houses)}
            for front, source in driver.FRONTS.items():
                rows = []
                for i, house in enumerate(houses):
                    if front == "sam2" and split == "train" and i == 3:
                        rows.append({"episode_id": house, "status": "failed"})  # one SAM2 cache failed: absent, not replaced
                        pool.write_json(Path(self.roots["cache"][front]) / split / house / "receipt.json",
                                        {"status": "failed", "reason": "proposal_overflow"})
                        continue
                    seal = {"payload_sha256": f"{front}-{house}"}
                    if front == "instance":
                        seal["mask_source"] = source
                    pool.write_json(Path(self.roots["cache"][front]) / split / house / "episode_seal.json", seal)
                    pool.write_json(Path(self.roots["cache"][front]) / split / house / "receipt.json", {"status": "succeeded", "frames": 900 + i})
                    rows.append({"episode_id": house, "status": "succeeded", "episode_seal_sha256": seal["payload_sha256"], "frames": 900 + i})
                export(f"{front}_cache_{split}", {"episodes": rows})
                pool.write_json(Path(self.roots["cache"][front]) / split / "s1_03_receipt.json", {"complete": True, "mask_source": source})
                counts[f"cache_succeeded_{source}"] = sum(1 for row in rows if row["status"] == "succeeded")
            splits[split] = counts
        kinds = {"raw": Path(self.roots["raw"]) / "test", "geometry": Path(self.roots["geometry"]) / "test",
                 "instance_cache": Path(self.roots["cache"]["instance"]) / "test", "sam2_cache": Path(self.roots["cache"]["sam2"]) / "test"}
        body = {"schema_version": lean_test_seal.SCHEMA_VERSION, "kinds": {kind: {"root": str(root)} for kind, root in kinds.items()}}
        digest = lean_test_seal.seal_sha256(body)
        for kind, root in kinds.items():
            lean_test_seal.write_marker(root, kind=kind, state=lean_test_seal.STATE_SEALED, seal_digest=digest)
        export("test_seal", {**body, "seal_sha256": digest})
        pool.write_json(self.export_dir / f"vsmt_lean_s3_02_manifest_{self.TAG}.json",
                        {"problems": [], "exports": exports, "splits": splits, "code_commit": "g3f6ef1d"})
        self.reid = {front: self.tmp / f"reid_{front}.json" for front in driver.FRONTS}
        for front, path in self.reid.items():
            pool.write_json(path, {"sha256": f"head-{front}"})

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def check(self, provisional: bool = False) -> dict:
        import s2_06_manifest
        from vsmt import lean_assignment as la

        with mock.patch.object(la, "reid_weights_sha256_for", lambda source: f"head-{'instance' if source == 'simulator_instance_masks' else 'sam2'}"), \
                mock.patch.object(s2_06_manifest, "payload_digest_ok", lambda payload: True):
            return driver.check_inputs(roots=self.roots, export_dir=self.export_dir, tag=self.TAG, reid=self.reid, provisional=provisional)

    def hide_the_s3_02_manifest(self) -> Path:
        path = self.export_dir / f"vsmt_lean_s3_02_manifest_{self.TAG}.json"
        hidden = self.tmp / "manifest.hidden"
        path.rename(hidden)
        return hidden

    def test_a_provisional_check_reads_the_roots_and_builds_the_same_episodes(self) -> None:
        # user 2026-10-04: start beside S3-02 before its run manifest exists; the episodes equal the full check's
        full = self.check()
        hidden = self.hide_the_s3_02_manifest()
        self.assertEqual(self.check()["problems"], [f"s3_02_manifest_missing:{self.export_dir / f'vsmt_lean_s3_02_manifest_{self.TAG}.json'}"])
        provisional = self.check(provisional=True)
        self.assertEqual(provisional["problems"], [])
        self.assertEqual(provisional["episodes"], full["episodes"])
        self.assertTrue(provisional["test_seal"]["provisional"])
        hidden.rename(self.export_dir / f"vsmt_lean_s3_02_manifest_{self.TAG}.json")
        # with the manifest back, the full check runs even when provisional is asked, and confirms the provisional start
        again = self.check(provisional=True)
        self.assertNotIn("provisional", again)
        confirmation = driver.confirm_provisional(provisional, again, self.roots, tuple(driver.FRONTS))
        self.assertEqual(confirmation["differs"], [])

    def test_inputs_that_changed_after_a_provisional_start_are_named(self) -> None:
        hidden = self.hide_the_s3_02_manifest()
        provisional = self.check(provisional=True)
        hidden.rename(self.export_dir / f"vsmt_lean_s3_02_manifest_{self.TAG}.json")
        house = self.houses["train"][0]
        pool.write_json(Path(self.roots["raw"]) / "train" / house / "receipt.json", {"house_id": house, "status": "succeeded", "edited": True})
        confirmation = driver.confirm_provisional(provisional, self.check(), self.roots, tuple(driver.FRONTS))
        self.assertEqual(confirmation["differs"], ["digests"])

    def test_a_provisional_check_accepts_a_test_root_not_built_yet(self) -> None:
        # the SAM2 test cache is S3-02's last step: its root may not exist (or carry no marker) while S3-03 starts
        self.hide_the_s3_02_manifest()
        shutil.rmtree(Path(self.roots["cache"]["sam2"]) / "test")
        report = self.check(provisional=True)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["test_seal"]["markers"]["sam2_cache"], {"path": str(Path(self.roots["cache"]["sam2"]) / "test" / "TEST_SEALED.json"),
                                                                        "root_exists": False, "state": None})

    def test_a_provisional_check_refuses_an_incomplete_cache(self) -> None:
        self.hide_the_s3_02_manifest()
        house = self.houses["validation"][1]
        (Path(self.roots["cache"]["sam2"]) / "validation" / house / "receipt.json").unlink()  # still being built
        problems = self.check(provisional=True)["problems"]
        self.assertIn(f"provisional_cache_incomplete:sam2:validation:cache_missing:{house}", problems)

    def test_consistent_inputs_are_accepted(self) -> None:
        report = self.check()
        self.assertEqual(report["problems"], [])
        self.assertEqual([row["episode_id"] for row in report["episodes"]["instance"]["train"]], self.houses["train"])
        self.assertEqual([row["episode_id"] for row in report["episodes"]["sam2"]["train"]], self.houses["train"][:3])
        self.assertEqual(report["episodes"]["instance"]["validation"][1], {"episode_id": self.houses["validation"][1], "frames": 901})
        self.assertTrue(all(marker["matches"] for marker in report["test_seal"]["markers"].values()))

    def test_each_inconsistency_is_named(self) -> None:
        from vsmt import lean_test_seal

        house = self.houses["validation"][0]
        seal = Path(self.roots["cache"]["sam2"]) / "validation" / house / "episode_seal.json"
        pool.write_json(seal, {"payload_sha256": "changed"})
        receipt = Path(self.roots["raw"]) / "train" / self.houses["train"][1] / "receipt.json"
        pool.write_json(receipt, {"house_id": "edited"})
        lean_test_seal.write_marker(Path(self.roots["geometry"]) / "test", kind="geometry", state=lean_test_seal.STATE_PENDING)
        (self.export_dir / f"vsmt_lean_s3_02_instance_cache_train_{self.TAG}.json").write_text("{}", encoding="utf-8")
        problems = self.check()["problems"]
        self.assertIn(f"cache_seal_differs_from_the_export:sam2:validation:{house}", problems)
        self.assertIn(f"raw_receipt_differs_from_the_export:train:{self.houses['train'][1]}", problems)
        self.assertIn("test_root_not_sealed_by_the_exported_seal:geometry", problems)
        self.assertIn(f"s3_02_export_differs_from_its_manifest:vsmt_lean_s3_02_instance_cache_train_{self.TAG}.json", problems)


class SubcommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.run_root = self.tmp / "run"
        pool.write_json(self.run_root / "inputs.json", fake_inputs(self.tmp, fronts=("instance",)))
        self.ctx = driver.load_context(self.run_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, command: str, *extra: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), mock.patch.object(driver, "git", lambda *a, **k: "c1"):
            code = driver.main([command, "--run-root", str(self.run_root), *extra])
        return code, err.getvalue()

    def test_the_fit_writes_the_values_the_round0_jobs_read(self) -> None:
        from vsmt import lean_development as dev

        counts = {"initial_log_odds": {"in_place_object_frames": 386794, "object_frames": 390257},
                  "persistence_log_decay_per_tick": {"intervention_events": 402, "object_ticks": 20649255},
                  "match_gain": {"hit_frames": 849649, "hit_total": 2724027, "false_frames": 224, "false_total": 24269}}
        for row in self.ctx.episodes("instance", "train"):
            folder = driver.episode_dir(self.ctx, "instance", "calibration", row["episode_id"], "TAF")
            pool.write_json(folder / "receipt.json", {"status": "succeeded", "mask_source": "simulator_instance_masks",
                                                      "config": driver.calibration_config()})
            pool.write_json(folder / "calibration.json", dev.CalibrationCollector().to_json())
            pool.write_json(folder / "elu_p_counts.json", counts)
        code, err = self.call("fit", "--front", "instance")
        self.assertEqual(code, 0, err)
        values = self.ctx.fit_values("instance")
        self.assertEqual(set(values), set(arms.ELU_P_FITTED))
        fit = json.loads((self.run_root / "instance" / "fit" / "elu_p_fit.json").read_text(encoding="utf-8"))
        self.assertEqual(fit["counts"]["initial_log_odds"]["object_frames"], 5 * 390257)
        self.assertTrue((self.run_root / "instance" / "fit" / "calibration_report.json").exists())
        bad = driver.episode_dir(self.ctx, "instance", "calibration", self.ctx.episodes("instance", "train")[0]["episode_id"], "TAF")
        pool.write_json(bad / "receipt.json", {"status": "succeeded", "mask_source": "sam2", "config": driver.calibration_config()})
        self.assertEqual(self.call("fit", "--front", "instance")[0], 1)

    def round0(self, *, mismatches: int = 0, leak: bool = False) -> None:
        import test_vsmt_lean_nuisance_tally as tally

        write_fit(self.ctx, "instance")
        config = driver.rollout_config(VALUES)
        for i, row in enumerate(self.ctx.episodes("instance", "train")):
            folder = driver.episode_dir(self.ctx, "instance", "round0", row["episode_id"], "ELU-P")
            pool.write_json(folder / "receipt.json", {
                "status": "succeeded", "config": config,
                "heuristic_records": {"reproduction": {"fragments": 10, "fragment_mismatches": mismatches if i == 0 else 0,
                                                       "existence_rows": 4, "existence_mismatches": 0},
                                      "totals": {"frames": 5, "existence_gone": 1}}})
            frames = tally.frames(i, 30)
            if leak:  # the label follows the frame index: the probe must see it
                for frame in frames:
                    for item in frame["association"]:
                        item["association_status"] = "birth" if item["frame_index"] % 2 else "labelled"
            with gzip.open(folder / "nuisance.jsonl.gz", "wt", encoding="utf-8") as handle:
                for tick, frame in enumerate(frames, start=1):
                    handle.write(json.dumps({"tick": tick, **frame}) + "\n")

    def test_the_round0_gate(self) -> None:
        self.round0()
        code, err = self.call("gate-round0", "--front", "instance")
        self.assertEqual(code, 0, err)
        gate = json.loads((self.run_root / "instance" / "gates" / "round0.json").read_text(encoding="utf-8"))
        self.assertEqual(gate["g4"]["reproduction"], {"fragments": 50, "fragment_mismatches": 0, "existence_rows": 20, "existence_mismatches": 0})
        self.assertEqual(gate["label_composition_report_only"]["heuristic_label_totals"], {"frames": 25, "existence_gone": 5})
        self.assertTrue(gate["pass"])
        self.round0(mismatches=2)
        self.assertEqual(self.call("gate-round0", "--front", "instance")[0], 3)
        self.round0(leak=True)
        code, _ = self.call("gate-round0", "--front", "instance")
        gate = json.loads((self.run_root / "instance" / "gates" / "round0.json").read_text(encoding="utf-8"))
        self.assertEqual((code, gate["g4"]["pass"], gate["nuisance"]["pass"]), (3, True, False))

    def test_the_readings_name_a_diverged_seed_and_refuse_a_missing_group(self) -> None:
        from test_vsmt_lean_s3_03_train import synthetic_report

        episodes = [row["episode_id"] for row in self.ctx.episodes("instance", "validation")]
        for arm, seeded in s3.SELECTION_ARMS.items():
            for index, config in enumerate(driver.audit_configs(arm)):
                for seed in (arms.SEEDS if seeded else (None,)):
                    if heads := (driver.heads_arm(arm) if seed == 31 else None):
                        if heads == "VSMT-lean":
                            continue  # VSMT-lean s31 diverged: neither VSMT-lean nor NoVersion has a group
                    rows = [{"episode_id": e, "config": config, "report": synthetic_report(arm, index, seed, e.replace("procthor10k-0.1.2-train-", "h"))}
                            for e in episodes]
                    pool.write_json(self.ctx.merged_path("instance", arm, index, seed),
                                    {"metrics_only": True, "mask_source": "simulator_instance_masks", "per_episode": rows})
        pool.write_json(self.run_root / "jobs" / f"{pool.state_key('instance/t1/VSMT-lean/s31')}.json",
                        {"job_id": "instance/t1/VSMT-lean/s31", "status": "diverged"})
        code, err = self.call("readings", "--front", "instance")
        self.assertEqual(code, 0, err)
        readings = json.loads((self.run_root / "instance" / "selection_readings.json").read_text(encoding="utf-8"))
        self.assertEqual(readings["readings"]["NoVersion"]["0"]["seeds_missing"], [31])
        self.assertEqual(readings["readings"]["HeuristicLabel"]["0"]["seeds_missing"], [])
        self.ctx.merged_path("instance", "LOW", 2, None).unlink()
        self.assertEqual(self.call("readings", "--front", "instance")[0], 3)

    def test_the_adoption_choice_is_kept_and_changes_only_before_calibration(self) -> None:
        self.assertEqual(driver.resolve_adopt(self.run_root, {"instance": "/prefit"}), {"instance": "/prefit"})
        self.assertEqual(driver.resolve_adopt(self.run_root, None), {"instance": "/prefit"})  # a resume without the option keeps it
        self.assertEqual(driver.load_context(self.run_root).adopt, {"instance": "/prefit"})
        pool.write_json(self.run_root / "jobs" / "instance__adopt-calibration.json", {"job_id": "instance/adopt-calibration", "status": "gate_failed"})
        self.assertEqual(driver.resolve_adopt(self.run_root, {}), {})  # a refused adoption may give way to a calibration pass
        self.assertIsNone(driver.load_context(self.run_root).adopt.get("instance"))
        pool.write_json(self.run_root / "jobs" / "instance__cal__x.json", {"job_id": "instance/cal/x", "status": "done"})
        with self.assertRaisesRegex(driver.DriverError, "adopt_calibration_differs_from_the_settled_choice"):
            driver.resolve_adopt(self.run_root, {"instance": "/prefit"})
        self.assertEqual(driver.resolve_adopt(self.run_root, None), {})
        with self.assertRaisesRegex(driver.DriverError, "adopt_calibration_names_no_front"):
            driver.resolve_adopt(self.tmp / "other", {"gpu": "/x"})

    def test_a_refused_run_says_so_in_the_pool_snapshot(self) -> None:
        pool.write_json(self.run_root / "pool.json", {"stop_reason": "gate_failed:an earlier run"})
        err = io.StringIO()
        with contextlib.redirect_stderr(err), mock.patch.object(driver, "git", lambda *a, **k: "another-commit"):
            self.assertEqual(driver.main(["run", "--run-root", str(self.run_root), "--log-dir", str(self.tmp / "logs")]), 2)
        self.assertTrue(json.loads((self.run_root / "pool.json").read_text(encoding="utf-8"))["stop_reason"].startswith("run_refused:"))

    def test_the_determinism_probe_falls_back_to_taf_when_every_vsmt_seed_diverged(self) -> None:
        self.assertIsNone(driver.determinism_group(self.ctx, "instance"))
        taf = driver.development_config("TAF")
        index = driver.audit_configs("TAF").index(taf)
        pool.write_json(self.ctx.merged_path("instance", "TAF", index, None), {})
        self.assertEqual(driver.determinism_group(self.ctx, "instance"), ("TAF", index, taf, None))
        tau = driver.round1_config("VSMT-lean")
        pool.write_json(self.ctx.merged_path("instance", "VSMT-lean", driver.audit_configs("VSMT-lean").index(tau), 19), {})
        self.assertEqual(driver.determinism_group(self.ctx, "instance")[0::3], ("VSMT-lean", 19))

    def test_verify_names_jobs_that_never_started_and_training_settings_that_differ(self) -> None:
        pool.write_json(self.run_root / "train_threads.json", {"train_threads": 3})
        for seed, foreach, threads in ((7, True, 3), (19, False, 3), (31, True, 2)):
            pool.write_json(self.ctx.training_dir("instance", 1, "VSMT-lean", seed) / "training_receipt.json",
                            {"optimizer_foreach": foreach, "threads": {"requested": threads}})
        result = driver.verify(self.ctx, self.tmp / "exports", "t")
        differ = sorted(p.rsplit("/", 2)[-2] for p in result["problems"] if p.startswith("training_settings_differ:"))
        self.assertEqual(differ, ["s19", "s31"])
        never = [p for p in result["problems"] if p.startswith("jobs_never_started:")]
        self.assertEqual(len(never), 1)
        self.assertEqual(int(never[0].split(":")[1]), len(driver.build_jobs(self.ctx)))

    def test_the_thread_count_from_the_timing(self) -> None:
        pool.write_json(self.run_root / "train_timing.json", {"timings": [{"threads": 1, "epoch_seconds": 10.0}, {"threads": 4, "epoch_seconds": 2.0}],
                                                               "houses": ["h"]})
        with mock.patch.object(driver, "resources", lambda: {"cpu_quota": 10}):
            code, err = self.call("train-threads", "--trainings", "30")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.ctx.train_threads(), 4)
        pool.write_json(self.run_root / "train_timing.json", {"timings": [{"threads": 1, "epoch_seconds": 10.0}, {"threads": 2, "epoch_seconds": 5.2}]})
        with mock.patch.object(driver, "resources", lambda: {"cpu_quota": 10}):
            self.assertEqual(self.call("train-threads", "--trainings", "30")[0], 0)
        self.assertEqual(self.ctx.train_threads(), 1)  # 8 cores: 4 waves x 10 s beat 8 x 5.2 s
        pool.write_json(self.run_root / "workers.json", {"budget_cores": 4})
        with mock.patch.object(driver, "resources", lambda: {"cpu_quota": 10}):
            self.assertEqual(self.call("train-threads", "--trainings", "30")[0], 0)
        self.assertEqual(self.ctx.train_threads(), 2)  # the run's budget of 4: 15 waves x 5.2 s beat 8 x 10 s


if __name__ == "__main__":
    unittest.main()
