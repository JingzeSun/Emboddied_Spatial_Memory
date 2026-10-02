"""S3-02 tests: the run support of the one-command driver (ruling 103).

Pinned: a stage finished at an earlier commit stays done only if the commits since changed nothing but the generator-commit
registration (the S1-03 contract and its two pinning tests) and documents; the check is redone at every new commit; the disk
projection rests on the committed S1 reports (about 337 GB for 450 houses), and what this run's roots already hold is subtracted
from it (the check after the hold, a resumed generation); ruling 36 stops below 120 moves or 60 source-first
on train; the hold passes registered generator commits, holds an unregistered commit whose camera_pose encoder is the registered
one and stops one whose encoder differs; geometry and caches are complete only when every raw episode is accounted for and a
cache failure is one of the data's own reasons; the instance cache gets two threads per worker up to the quota and the memory
(8 x 2 on the 16-CPU development host); the SAM2 workers per card are the cleanest fastest trial; the test summary carries no
house id; verify finds a missing cache episode, a marker on a train root and a changed sealed file; the driver's stage list is the
helper's.  CPU only, a few seconds (a throwaway git repository, fake roots for the 450 manifest houses).
"""
from __future__ import annotations

import io
import contextlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_02_manifest as support  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402

DRIVER = PROJECT_ROOT / "ops" / "vsmt" / "s3_02_data.sh"
REGISTERED = "2339baa96c123a7676e129881d270bfab252573c"  # the confirmation generation, last in the pose registry
DEFECTIVE = "c222c51a1906f3703a6115c968e77f349306faa9"  # the pre-ruling-49 encoder (pitch sign)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=str(repo), text=True).strip()


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")


def quiet(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args, **kwargs)


class TestStageState(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo, self.run = Path(self.tmp.name) / "repo", Path(self.tmp.name) / "run"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        for path in ("ops/vsmt/lean_s1_02a_pilot.py", *support.REGISTRATION_FILES, "README.md"):
            write(self.repo / path, "0\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "x")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def commit(self, path: str) -> None:
        (self.repo / path).write_text((self.repo / path).read_text(encoding="utf-8") + "1\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", path)

    def mark(self, stage: str, status: str = "done") -> None:
        support.write_json(support.marker_path(self.run, stage), {"stage": stage, "status": status, "commit": git(self.repo, "rev-parse", "HEAD")})

    def state(self, stage: str, accept: bool = False) -> str:
        return support.stage_state(self.run, stage, git(self.repo, "rev-parse", "HEAD"), self.repo, accept)[0]

    def test_only_the_registration_and_documents_keep_a_stage(self) -> None:
        for stage in ("check", "measure", "generate"):
            self.mark(stage)
        self.mark("hold", status="hold")
        self.assertEqual([self.state(s) for s in ("check", "generate", "hold", "geometry")], ["done", "done", "todo", "todo"])
        for path in support.REGISTRATION_FILES + ("README.md",):
            self.commit(path)
        self.assertEqual((self.state("generate"), self.state("check")), ("done", "todo"))  # the check is redone at a new commit
        self.commit("ops/vsmt/lean_s1_02a_pilot.py")
        self.assertEqual(self.state("generate"), "blocked")
        self.assertEqual(self.state("generate", accept=True), "done")


class TestBetweenStages(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_disk_projection_from_the_committed_reports(self) -> None:
        projection = support.disk_projection(PROJECT_ROOT, houses=450)
        self.assertAlmostEqual(projection["raw_gb_per_house"], 11.004086178 / 46)
        self.assertAlmostEqual(projection["cache_gb_per_episode"][support.SAM2], 10.219526242 / 39)
        self.assertAlmostEqual(projection["need_gb"], 337.2, delta=0.2)
        heavier = support.disk_projection(PROJECT_ROOT, houses=450, raw_gb_per_house=0.3)
        self.assertAlmostEqual(heavier["need_gb"], (450 * 0.3 + 450 * 43 / 50 * sum(projection["cache_gb_per_episode"].values())) * 1.1, delta=0.1)
        lighter = support.disk_projection(PROJECT_ROOT, houses=450, raw_gb_per_house=0.1)
        self.assertEqual(lighter["need_gb"], projection["need_gb"])  # never below the committed bytes

    def test_the_disk_need_is_the_projection_less_what_this_run_already_wrote(self) -> None:
        # the check is redone at the registration commit, when about 108 GB of raw episodes are already on disk
        roots = [self.base / "raw" / "train", self.base / "missing", self.base / "cache"]
        write(roots[0] / "procthor10k-0.1.2-train-00001" / "public" / "0000.frame.json", "x" * 1500)
        write(roots[2] / "s1_03_receipt.json", "y" * 500)
        self.assertEqual(support.written_bytes(roots), 2000)
        self.assertEqual(support.run_roots(f"{roots[0]},,{roots[1]}"), [str(roots[0]), str(roots[1])])
        projection = {"need_gb": 337.1}
        self.assertAlmostEqual(support.disk_requirement(projection, written=108 * 10 ** 9, min_free_gib=None)["required_gb"], 229.1)
        self.assertEqual(support.disk_requirement(projection, written=400 * 10 ** 9, min_free_gib=None)["required_gb"], 0.0)
        override = support.disk_requirement(projection, written=108 * 10 ** 9, min_free_gib=100.0)
        self.assertEqual((override["required_gb"], override["basis"]), (100 * 2 ** 30 / 1e9, "MIN_FREE_GIB set by the operator"))

    def test_the_disk_step_before_a_resumed_generation_counts_the_houses_already_written(self) -> None:
        measure, run, train = self.base / "measure", self.base / "run", self.base / "raw" / "train"
        write(measure / "measure_receipt.json", {"per_house": [{"bytes_written": 239_000_000}]})  # below the committed bytes
        write(train / "procthor10k-0.1.2-train-00001" / "frames.bin", "z" * 4000)
        need = support.disk_projection(PROJECT_ROOT, houses=450)["need_gb"]
        args = ["disk", "--run-root", str(run), "--repo-root", str(PROJECT_ROOT), "--autodl-root", str(self.base),
                "--measure-root", str(measure), "--run-roots", str(train)]
        with mock.patch.object(support, "free_gb", return_value=need - 0.000003):
            self.assertEqual(quiet(support.main, args), 0)  # 4 kB already written: the projection less 4 kB is needed
        with mock.patch.object(support, "free_gb", return_value=need - 0.000005):
            self.assertEqual(quiet(support.main, args), 3)
        report = json.loads((run / "disk.json").read_text(encoding="utf-8"))
        self.assertEqual((report["written_bytes"], report["run_roots"], report["enough"]), (4000, [str(train)], False))

    def test_ruling_36_move_check(self) -> None:
        raw, run = self.base / "raw", self.base / "run"
        minimum = {"moves": 130, "moves_source_first": 59, "minimum_train": 120, "minimum_train_source_first": 60,
                   "gate_applies": True, "below_minimum": True}
        write(raw / "train" / "s3_receipt.json", {"move_minimum": minimum, "houses_planned": 300, "succeeded": 250})
        args = ["movecheck", "--run-root", str(run), "--raw-root", str(raw)]
        self.assertEqual(quiet(support.main, args), 4)
        self.assertTrue(json.loads((run / "movecheck.json").read_text(encoding="utf-8"))["below_minimum"])
        write(raw / "train" / "s3_receipt.json", {"move_minimum": {**minimum, "moves_source_first": 60, "below_minimum": False},
                                                   "houses_planned": 300, "succeeded": 250})
        self.assertEqual(quiet(support.main, args), 0)
        self.assertEqual(quiet(support.main, ["movecheck", "--run-root", str(run), "--raw-root", str(self.base / "none")]), 3)

    def raw_with_commit(self, commit: str) -> Path:
        raw = self.base / f"raw-{commit[:7]}"
        for split in support.SPLITS:
            write(raw / split / f"procthor10k-0.1.2-train-0000{len(split)}" / "receipt.json", {"status": "succeeded", "code_commit": commit})
        return raw

    def test_the_registration_hold(self) -> None:
        head = git(PROJECT_ROOT, "rev-parse", "HEAD")
        run = self.base / "run"
        cases = ((REGISTERED, 0), (head, 10), (DEFECTIVE, 11))
        for commit, expected in cases:
            code = quiet(support.main, ["hold", "--run-root", str(run), "--raw-root", str(self.raw_with_commit(commit))])
            self.assertEqual(code, expected, commit)
        report = json.loads((run / "hold.json").read_text(encoding="utf-8"))
        self.assertEqual((report["unregistered"], report["encoder_changed"], report["reference_commit"]), ([DEFECTIVE], [DEFECTIVE], REGISTERED))
        self.assertEqual(support.encoder_source(head, PROJECT_ROOT), support.encoder_source(REGISTERED, PROJECT_ROOT))

    def test_geometry_and_cache_completeness(self) -> None:
        raw, geometry, cache = self.base / "raw", self.base / "geometry", self.base / "cache"
        names = [f"procthor10k-0.1.2-train-0000{i}" for i in range(4)]
        for name, status in zip(names, ("succeeded", "succeeded", "succeeded", "failed")):
            write(raw / name / "receipt.json", {"status": status})
        self.assertEqual(support.geometry_problems(geometry, raw), [f"no_stage_receipt:{geometry}"])
        write(geometry / "s1_04_geometry_receipt.json", {})
        for name in names[:3]:
            write(geometry / name / "receipt.json", {"status": "succeeded"})
        write(geometry / names[3] / "receipt.json", {"status": "failed", "reason": "source_episode_not_succeeded"})
        self.assertEqual(support.geometry_problems(geometry, raw), [])
        write(geometry / names[1] / "receipt.json", {"status": "failed", "reason": "metadata_missing_or_malformed"})
        self.assertEqual(support.geometry_problems(geometry, raw), [f"geometry_failed:{names[1]}:metadata_missing_or_malformed"])
        write(cache / "s1_03_receipt.json", {"complete": True, "mask_source": support.SAM2})
        write(cache / names[0] / "receipt.json", {"status": "succeeded"})
        write(cache / names[0] / "episode_seal.json", {"payload_sha256": "x"})  # a SAM2 seal names no source
        write(cache / names[1] / "receipt.json", {"status": "failed", "reason": "proposal_overflow"})
        self.assertEqual(support.cache_problems(cache, raw, support.SAM2), [f"cache_missing:{names[2]}"])
        write(cache / names[2] / "receipt.json", {"status": "failed", "reason": "public_input_missing_or_malformed"})
        self.assertEqual(support.cache_problems(cache, raw, support.SAM2), [f"cache_failed_not_by_the_data:{names[2]}:public_input_missing_or_malformed"])
        self.assertIn("cache_sealed_with_another_source:" + names[0], " ".join(support.cache_problems(cache, raw, support.INSTANCE)))


class TestCheck(unittest.TestCase):
    def test_every_missing_or_wrong_input_is_named_not_crashed_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write(base / "train.jsonl.gz", "not the registered source")
            write(base / "salt.txt", "a-salt-that-is-not-the-s1-salt-0123456789")
            run = base / "run"
            args = ["check", "--run-root", str(run), "--autodl-root", str(base), "--source", str(base / "train.jsonl.gz"),
                    "--salt-file", str(base / "salt.txt"), "--assets-json", str(base / "assets.json"),
                    "--sam2-reid", str(base / "sam2.json"), "--instance-reid", str(base / "instance.json"),
                    "--sim-python", str(base / "no-python"), "--min-free-gib", "1e9"]
            self.assertEqual(quiet(support.main, args), 3)
            report = json.loads((run / "inputs.json").read_text(encoding="utf-8"))
        problems = " ".join(report["problems"])
        for needle in ("source_differs_from_the_registry", "salt_is_not_the_s1_salt", "frontend_assets:", "reid_head_missing:sam2",
                       f"reid_head_missing:{support.INSTANCE}", "simulator_python", "disk:"):
            self.assertIn(needle, problems)
        self.assertEqual({k: v["houses"] for k, v in report["manifests"].items()}, {"train": 300, "validation": 50, "test": 100})
        self.assertAlmostEqual(report["disk"]["projection"]["need_gb"], 337.2, delta=0.2)

    def test_the_check_redone_after_the_hold_does_not_count_the_written_raw_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / "raw" / "train"
            write(raw / "procthor10k-0.1.2-train-00001" / "public" / "0000.frame.json", "r" * 3000)
            run = base / "run"
            need = support.disk_projection(PROJECT_ROOT, houses=450)["need_gb"]
            args = ["check", "--run-root", str(run), "--autodl-root", str(base), "--source", str(base / "train.jsonl.gz"),
                    "--salt-file", str(base / "salt.txt"), "--assets-json", str(base / "assets.json"),
                    "--sam2-reid", str(base / "sam2.json"), "--instance-reid", str(base / "instance.json"),
                    "--sim-python", str(base / "no-python"), "--run-roots", f"{raw},{base / 'geometry'}"]
            with mock.patch.object(support, "free_gb", return_value=need - 0.000002):  # short of the projection, not of the rest
                quiet(support.main, args)
            report = json.loads((run / "inputs.json").read_text(encoding="utf-8"))
        self.assertNotIn("disk:", " ".join(report["problems"]))
        self.assertEqual((report["disk"]["written_bytes"], report["disk"]["run_roots"]), (3000, [str(raw), str(base / "geometry")]))


class TestWorkersAndSam2(unittest.TestCase):
    def test_instance_cache_workers(self) -> None:
        self.assertEqual(support.instance_cache_workers(16, 62 * 2 ** 30)["workers"], 8)  # the 8ebbd05 host: 8 x 2 threads
        plan = support.instance_cache_workers(100, 240 * 2 ** 30)
        self.assertEqual((plan["workers"], plan["by_cpu"], plan["threads"]), (50, 50, 2))
        self.assertEqual(support.instance_cache_workers(100, 40 * 2 ** 30)["workers"], 19)  # memory binds

    def test_the_sam2_trial_choice(self) -> None:
        def rate(k, fps, ok=None):
            return {"episodes": k, "succeeded": k if ok is None else ok, "frames_per_second": fps}

        self.assertEqual(support.choose_sam2_workers({1: rate(1, 0.40), 2: rate(2, 0.70), 3: rate(3, 0.69), 4: rate(4, 0.50)}), 2)
        self.assertEqual(support.choose_sam2_workers({1: rate(1, 0.40), 2: rate(2, 0.70), 3: rate(3, 0.90, ok=2)}), 2)
        self.assertEqual(support.choose_sam2_workers({2: rate(2, 0.70), 3: rate(3, 0.70)}), 2)
        with tempfile.TemporaryDirectory() as tmp:
            trial = Path(tmp)
            write(trial / "trial_receipt.json", {"wall_clock_seconds": 100.0, "peak_vram_reserved_mib_max": 5300.0})
            for i, seconds in enumerate((60.0, 40.0)):
                write(trial / f"procthor10k-0.1.2-train-0000{i}" / "receipt.json",
                      {"status": "succeeded", "frames_processed": 60, "seconds_by_part": {"sam": seconds * 0.8, "dino": seconds * 0.2}})
            measured = support.trial_rate(trial)
        self.assertEqual((measured["frames"], measured["frames_per_second"], measured["frames_per_second_wall"]), (120, 2.5, 1.2))


class TestSealSummaryAndVerify(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.lists = support.manifests()
        self.roots = {"raw": base / "raw", "geometry": base / "geometry", support.INSTANCE: base / "instance", support.SAM2: base / "sam2"}
        self.run, self.exports = base / "run", base / "exports"
        for split, houses in self.lists.items():
            for index, house in enumerate(houses):
                ok = index % 10 != 0
                write(self.roots["raw"] / split / house / "receipt.json", {"status": "succeeded" if ok else "failed", "code_commit": "c",
                                                                           "observations": 100})
                write(self.roots["geometry"] / split / house / "receipt.json",
                      {"status": "succeeded"} if ok else {"status": "failed", "reason": "source_episode_not_succeeded"})
                if ok:
                    for source in (support.INSTANCE, support.SAM2):
                        write(self.roots[source] / split / house / "receipt.json", {"status": "succeeded"})
                        write(self.roots[source] / split / house / "episode_seal.json",
                              {"mask_source": source} if source == support.INSTANCE else {})
            write(self.roots["raw"] / split / "s3_receipt.json", {
                "houses_planned": len(houses), "succeeded": len(houses) - len(houses) // 10, "failed": len(houses) // 10,
                "failures_by_reason": {"intervention_window_unavailable": len(houses) // 10}, "null_window_episodes": 3,
                "null_window_failed": 0, "yield_house_level_non_null": 0.8, "moves_executed": 400, "moves_source_first": 240,
                "controls_total": 9, "controls_outside_U": 2, "actual_workers": 16})
            write(self.roots["geometry"] / split / "s1_04_geometry_receipt.json", {})
            for source in (support.INSTANCE, support.SAM2):
                write(self.roots[source] / split / "s1_03_receipt.json", {"complete": True, "mask_source": source, "episodes_succeeded": 1})
        for name, kind in (("raw", "raw"), ("geometry", "geometry"), (support.INSTANCE, "instance_cache"), (support.SAM2, "sam2_cache")):
            ts.write_marker(self.roots[name] / "test", kind=kind, state=ts.STATE_PENDING)
        for stage in support.STAGES[:-1]:
            support.write_json(support.marker_path(self.run, stage), {"stage": stage, "status": "done", "commit": "c"})
        support.write_json(self.run / "movecheck.json", {"below_minimum": False})
        write(self.exports / "vsmt_lean_s3_02_inputs_t1.json", "{}")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def seal_args(self, *extra: str) -> list[str]:
        return ["--raw", str(self.roots["raw"] / "test"), "--geometry", str(self.roots["geometry"] / "test"),
                "--instance-cache", str(self.roots[support.INSTANCE] / "test"), "--sam2-cache", str(self.roots[support.SAM2] / "test"), *extra]

    def verify_args(self) -> list[str]:
        return ["verify", "--run-root", str(self.run), "--export-dir", str(self.exports), "--tag", "t1", "--raw", str(self.roots["raw"]),
                "--geometry", str(self.roots["geometry"]), "--instance-cache", str(self.roots[support.INSTANCE]),
                "--sam2-cache", str(self.roots[support.SAM2])]

    def test_summary_seal_and_verify(self) -> None:
        summary_path = self.exports / "vsmt_lean_s3_02_test_summary_t1.json"
        self.assertEqual(quiet(support.main, ["test-summary", *self.seal_args("--out", str(summary_path))]), 0)
        summary = summary_path.read_text(encoding="utf-8")
        self.assertNotIn("procthor10k", summary)  # counts only
        self.assertEqual(json.loads(summary)["geometry"]["failures_by_reason"], {"source_episode_not_succeeded": 10})
        self.assertEqual(quiet(support.main, ["seal", *self.seal_args("--tag", "t1", "--out", str(self.run / "test_seal.json"))]), 0)
        self.assertEqual(quiet(support.main, self.verify_args()), 0)
        manifest = json.loads((self.exports / "vsmt_lean_s3_02_manifest_t1.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["splits"]["train"], {"houses": 300, "attempted": 300, "raw_succeeded": 270, "geometry_succeeded": 270,
                                                       f"cache_succeeded_{support.INSTANCE}": 270, f"cache_succeeded_{support.SAM2}": 270})
        self.assertEqual(set(manifest["exports"]), {"vsmt_lean_s3_02_inputs_t1.json", "vsmt_lean_s3_02_test_summary_t1.json"})
        # break three things: a missing cache episode, a marker on a train root, a changed sealed file
        house = self.lists["validation"][1]
        for path in sorted((self.roots[support.SAM2] / "validation" / house).iterdir()):
            path.unlink()
        (self.roots[support.SAM2] / "validation" / house).rmdir()
        ts.write_marker(self.roots["geometry"] / "train", kind="geometry", state=ts.STATE_PENDING)
        write(self.roots["raw"] / "test" / self.lists["test"][1] / "receipt.json", {"status": "succeeded", "code_commit": "changed"})
        self.assertEqual(quiet(support.main, self.verify_args()), 3)
        problems = json.loads((self.exports / "vsmt_lean_s3_02_verify_t1.json").read_text(encoding="utf-8"))["problems"]
        self.assertIn(f"validation:{support.SAM2}:cache_missing:{house}", problems)
        self.assertIn(f"marker_on_a_non_test_root:{self.roots['geometry'] / 'train'}", problems)
        self.assertIn(f"test_seal:episode_digest_differs:raw:{self.lists['test'][1]}", problems)


class TestDriver(unittest.TestCase):
    def test_the_driver_runs_the_helpers_stages_each_with_its_function(self) -> None:
        text = DRIVER.read_text(encoding="utf-8")
        stages = re.search(r'^STAGES="([^"]+)"', text, re.M).group(1).split()
        self.assertEqual(tuple(stages), support.STAGES)
        for stage in stages:
            self.assertRegex(text, rf"(?m)^stage_{stage.replace('-', '_')}\(\) \{{", stage)
        self.assertNotIn("\r\n", DRIVER.read_bytes().decode("utf-8"))
        for needle in ("--stage s3-measure", "--stage s3 ", "--simulator-concurrency-limit", "run_cache simulator_instance_masks",
                       "run_cache sam2", "--largest-first", "seal-pending", "lean_s1_04_object_geometry.py", "--workers 8"):
            self.assertIn(needle, text)

    def test_both_disk_checks_get_this_runs_roots_but_not_the_measure_root(self) -> None:
        text = DRIVER.read_text(encoding="utf-8")
        roots = re.search(r'^RUN_ROOTS="([^"]+)"', text, re.M).group(1).split(",")
        self.assertEqual(roots, ["$RAW/train", "$RAW/validation", "$RAW/test", "$GEOMETRY", "$INSTANCE_CACHE", "$SAM2_CACHE"])
        for call in (r"M check (?:[^\n]*\\\n)*[^\n]*", r"M disk (?:[^\n]*\\\n)*[^\n]*"):  # the call with its continued lines
            self.assertIn('--run-roots "$RUN_ROOTS"', re.search(call, text).group(0))


if __name__ == "__main__":
    unittest.main()
