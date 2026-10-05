#!/usr/bin/env python3
"""S3-03 driver (ruling 104): ELU-P fit, DAgger rounds 0 and 1, the 36 trainings, the validation audits and the selection readings.

白话：S3-03 回答“正式实验里每个臂拿什么权重、哪些配置候选去考 validation”。输入是 S3-02 的 train／validation 数据（只读，
test 根封存不碰）、冻结的方法与网格；输出是两套前端各自的 ELU-P 拟合量（运行内的值，登记提交在运行期间或之后另做，verify
核对两者逐位相等）、第 0／1 轮轨迹与 HeuristicLabel 标签、36 次训练（逐 epoch 分项损失）、208 组 × 约 42 条 validation 闭环
审计，以及给 S3-04 的选参读数。整趟由一个依赖驱动的作业池（``s3_03_jobs``）跑：每套前端的拟合趟 → 拟合 → 第 0 轮 → 门
（HeuristicLabel 复现 G4 与 split 级 nuisance 探针）→ 第 0 轮训练 → 第 1 轮 → 第 1 轮训练 → 学习臂审计；规则臂审计（ELU-P
等拟合）一开始就用空槽跑；审计等价探针与训练等价探针与正式作业同时跑，不过即停下。它不选配置（S3-04）、不读 test、不改方法。

Usage (server; normally through ops/vsmt/s3_03_train_select.sh):
  python ops/vsmt/s3_03_manifest.py check --run-root R --autodl-root /root/autodl-tmp --s3-02-tag 3f6ef1d --export-dir E \\
      --instance-reid <instance head> --sam2-reid <sam2 head>
  python ops/vsmt/s3_03_manifest.py run --run-root R --log-dir L [--accept-code-change] [--adopt-calibration instance=<pass root>]
  python ops/vsmt/s3_03_manifest.py status --run-root R
  python ops/vsmt/s3_03_manifest.py export --run-root R --export-dir E --tag T
  python ops/vsmt/s3_03_manifest.py verify --run-root R --export-dir E --tag T
The job subcommands (fit, gate-round0, train-threads, probe-audit, adopt-calibration, readings, probe-determinism, coverage,
run-measured) are what the pool runs; README "How to reproduce S3-03" lists the whole flow.
"""

from __future__ import annotations

import argparse
import dataclasses
import gzip
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_03_jobs as pool  # noqa: E402
JOBS_SCRIPT = HERE.parent / "s3_03_jobs.py"  # its run-measured wrapper imports only the standard library
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402

STAGE = "vsmt.lean.s3_03.driver.v1"
#: front key -> mask source (rulings 72, 83-3: instance segmentation is the main table, SAM 2.1 the second)
FRONTS = {"instance": "simulator_instance_masks", "sam2": "sam2"}
SPLITS = ("train", "validation")
S2_04_ENTRY = HERE.parent / "lean_s2_04_evaluate_episode.py"
NODE_AUDIT = HERE.parent / "lean_s2_05_node_audit.py"
REMOTE_SCRIPT = HERE.parent / "remote_hosts.py"
TRAIN_ENTRY = HERE.parent / "s3_03_train.py"
GRID_REVIEW = HERE.parent / "s2_06_grid_review.py"
S2_05_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s2_05_development_v1.json"
S0_05_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json"
#: Ruling 104-1 1b: the commit registering the S3 fitted values may touch only these (and documents); a run continues over it.
REGISTRATION_FILES = ("configs/vsmt/lean_s0_arms_v2.json", "src/vsmt/lean_arms.py", "tests/test_vsmt_lean_cross_contract.py",
                      "tests/test_vsmt_lean_arms.py", "tests/test_vsmt_lean_s2_05_entry.py", "tests/test_vsmt_lean_ruling88_probes.py")
DOCUMENT_FILES = ("README.md", "EXECUTE.md", "AGENTS.md")
DOCUMENT_PREFIXES = ("docs/", "results/")
#: Ruling 104-7 priorities: control jobs (gates, probes, merges) > the critical path > learned-arm audits > rule-arm audits.
PRIORITY = {"control": 0, "critical": 1, "learned_audit": 2, "rule_audit": 3}
#: Memory classes (GiB) before the first measurement of each; afterwards 1.25 x the measured peak (S2-06 rule).  S2-06 measured
#: 2.0 GiB for one pass or audit process (1.25 x the peak of its largest episode) and 10.5 GiB for a development-scale training;
#: S3 trainings stream, so their peak is unknown before the first one ends.  Round-1 trainings read about twice round 0's records
#: and the probes far less, so each has its own class and no measurement lowers another's estimate.
MEMORY_DEFAULTS_GIB = {"pass": 4.0, "audit": 4.0, "audit_full": 6.0, "train0": 24.0, "train1": 24.0, "train_probe": 12.0,
                       "train_timing": 8.0, "gate": 6.0, "small": 2.0}
#: Ruling 104-7, bounded job length: nothing is preempted, so a long low-priority job that starts while the critical path waits
#: for its next inputs holds its core until it ends.  An audit job takes at most this many configurations (about 20-35 minutes on
#: a typical episode, estimated from the development profile); the cache is still verified once per job, not once per config.
CONFIGS_PER_AUDIT_JOB = {"rule": 3, "learned": 5}
#: The disk floor of a resumed run's check (the pool stops dispatching below the same floor); a first check asks for --min-free-gib.
RUN_FLOOR_GIB = 20.0
#: What one running job may still write before it ends (records of a pass, an audit chunk, a training's snapshots); the pool's
#: disk floor is RUN_FLOOR_GIB plus this for every running job, so about 98 passes writing at once cannot fill the disk unseen.
INFLIGHT_GIB = 0.5
#: The adoption choice of the first run, kept so that every resume builds the same graph.
ADOPT_FILE = "adopt_calibration.json"
#: Ruling 104-7 conditional item: the trainings, the timing and the training probe use AdamW's multi-tensor path.  It is
#: bit-identical to the default path where checked (a suite test the check step runs on the server's torch; the training
#: probe on real records, registered path against the run's); a difference stops the run before its results are used.
OPTIMIZER_FOREACH = True
TIMING_TRAINING_HOUSES = 20
TIMING_SELECTION_HOUSES = TIMING_TRAINING_HOUSES // 4  # s3_03_train.subset takes a quarter as many selection houses
PROBE_TRAIN_HOUSES = 12
TRAINING_COST = 1e12  # trainings first among the critical-path jobs ready at the same time
NUISANCE_GATE_RULE = ("ruling 104-2: the round-0 split passes when the largest advantage of the nuisance probe over its pooled rows "
                      "(lean_teacher NUISANCE_FIELDS x labels, S0-04 scope rule) is at most S0-04's maximum_advantage (0.05); a "
                      "failure stops the run before training, for a read-only breakdown and a ruling, never a wider line")
G4_RULE = ("ruling 104-2 G4: on ELU-P's own round-0 trajectory the HeuristicLabel label function reproduces ELU-P's association and "
           "existence decisions row for row; any mismatch stops the run before training")


class DriverError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DriverError(code)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

load_json = pool.load_json
write_json = pool.write_json
utc_now = pool.utc_now


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def git(*arguments: str, repo: Path = ROOT) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(repo), text=True).strip()


def allowed_change(path: str) -> bool:
    return path in REGISTRATION_FILES or path in DOCUMENT_FILES or path.startswith(DOCUMENT_PREFIXES)


def disallowed_changes(since: str, repo: Path = ROOT) -> list[str]:
    """Files changed since ``since`` that are neither registration files nor documents (the S2-06 code-change rule)."""

    return [path for path in git("diff", "--name-only", since, "HEAD", repo=repo).splitlines() if path and not allowed_change(path)]


def read_gz_lines(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def resources() -> dict[str, Any]:
    import s2_06_manifest

    return s2_06_manifest.resources()


def calibration_config() -> dict[str, Any]:
    from vsmt import lean_development as dev

    return dict(dev.CALIBRATION_ARM_CONFIG["config"])


def rollout_config(values: Mapping[str, Any]) -> dict[str, Any]:
    """ELU-P at the registered rollout_config, no distance gate, with a front end's fitted values (ruling 104-1 1b)."""

    return {**{name: arms.ROLLOUT_CONFIG[name] for name in arms.ROLLOUT_CONFIG_PARAMETERS}, arms.ROLLOUT_CONFIG_GATE_PARAMETER: None,
            **{name: values[name] for name in arms.ELU_P_FITTED}}


def development_config(arm: str) -> dict[str, Any]:
    """An arm's registered development configuration (S2-05 contract), in runner form."""

    from vsmt import lean_development as dev

    contract = dev.validate_development_contract(load_json(S2_05_CONTRACT))
    config = dev.development_configuration(contract, arm)
    _require(config is not None, f"development_configuration_null:{arm}")
    return dict(config)


def round1_config(arm: str) -> dict[str, Any]:
    """Ruling 104-1: round-1 rollouts at the registered development configuration (VSMT-lean's for HeuristicLabel; none for AssocOnly)."""

    return {} if arm == "AssocOnly" else development_config("VSMT-lean")


def audit_configs(arm: str) -> list[dict[str, Any]]:
    return [dict(config) for config in arms.enumerate_configs(arm, arms.FROZEN_GRIDS[arm])]


def heads_arm(arm: str) -> str:
    """Whose trained heads an audited learned arm uses: NoVersion runs VSMT-lean's (ruling 99-1 / 104-1 1d)."""

    return "VSMT-lean" if arm == "NoVersion" else arm


def group_name(arm: str, index: int, seed: int | None) -> str:
    return f"{arm}-c{index:02d}" + ("" if seed is None else f"-s{seed}")


# --------------------------------------------------------------------------
# the run context
# --------------------------------------------------------------------------

@dataclasses.dataclass
class RunContext:
    """Paths and inputs of one run; everything a job command needs is derived here."""

    run_root: Path
    inputs: Mapping[str, Any]
    python: str = sys.executable
    fronts: tuple[str, ...] = ("instance", "sam2")
    adopt: Mapping[str, str] = dataclasses.field(default_factory=dict)

    def front_dir(self, front: str) -> Path:
        return self.run_root / front

    def pass_root(self, front: str, name: str) -> Path:
        return self.front_dir(front) / name

    def training_dir(self, front: str, round_index: int, arm: str, seed: int) -> Path:
        return self.front_dir(front) / "training" / f"round{round_index}" / arm / f"s{seed}"

    def heads_file(self, front: str, round_index: int, arm: str, seed: int) -> Path:
        uses = s3.training_settings(arm, round_index)["uses"]
        return self.training_dir(front, round_index, arm, seed) / ("weights_grouped.json" if uses == "grouped" else "weights.json")

    def group_root(self, front: str, arm: str, index: int, seed: int | None) -> Path:
        return self.front_dir(front) / "audit" / group_name(arm, index, seed)

    def merged_path(self, front: str, arm: str, index: int, seed: int | None) -> Path:
        return self.front_dir(front) / "merged" / f"{group_name(arm, index, seed)}.json"

    def gates_dir(self, front: str) -> Path:
        return self.front_dir(front) / "gates"

    def fit_values_path(self, front: str) -> Path:
        return self.front_dir(front) / "fit" / "elu_p_values.json"

    def fit_values(self, front: str) -> dict[str, Any]:
        payload = load_json(self.fit_values_path(front))
        _require(payload.get("mask_source") == FRONTS[front], f"fit_values_of_another_front:{front}")
        _require(canonical_sha256(payload["values"]) == payload.get("values_sha256"), f"fit_values_digest_differs:{front}")
        return dict(payload["values"])

    def train_threads(self) -> int:
        return int(load_json(self.run_root / "train_threads.json")["train_threads"])

    def raw_root(self, split: str) -> Path:
        return Path(self.inputs["roots"]["raw"][split])

    def geometry_root(self, split: str) -> Path:
        return Path(self.inputs["roots"]["geometry"][split])

    def cache_root(self, front: str, split: str) -> Path:
        return Path(self.inputs["roots"]["cache"][front][split])

    def reid(self, front: str) -> str:
        return str(self.inputs["reid"][front]["file"])

    def episodes(self, front: str, split: str) -> list[dict[str, Any]]:
        return list(self.inputs["episodes"][front][split])

    def frames(self, front: str, split: str) -> dict[str, int]:
        return {row["episode_id"]: int(row.get("frames") or 1) for row in self.episodes(front, split)}

    # -- commands --------------------------------------------------------------

    def s2_04(self, front: str, split: str, episode: str, arm: str, config: Mapping[str, Any], output_root: Path, *,
              heads: Path | None = None, flags: Sequence[str] = ()) -> list[str]:
        return [self.python, str(S2_04_ENTRY), "--cache-root", str(self.cache_root(front, split)),
                "--episode-root", str(self.raw_root(split) / episode), "--geometry-root", str(self.geometry_root(split)),
                "--episode-id", episode, "--arm", arm, "--config", json.dumps(dict(config)), "--descriptor", s3_descriptor(),
                "--weights", self.reid(front), "--mask-source", FRONTS[front], "--output-root", str(output_root), "--device", "cpu",
                "--manifest-split", split, *(["--heads", str(heads)] if heads is not None else []), *flags]

    def audit(self, front: str, episode: str, arm: str, seed: int | None, configs: Sequence[tuple[int, Mapping[str, Any]]], *,
              heads: Path | None = None) -> list[str]:
        entries = [{"config": dict(config), "output_root": str(self.group_root(front, arm, index, seed))} for index, config in configs]
        return [self.python, str(NODE_AUDIT), "run", "--cache-root", str(self.cache_root(front, "validation")),
                "--episode-root", str(self.raw_root("validation") / episode), "--geometry-root", str(self.geometry_root("validation")),
                "--episode-id", episode, "--arm", arm, "--descriptor", s3_descriptor(), "--weights", self.reid(front),
                "--mask-source", FRONTS[front], "--device", "cpu", "--metrics-only", "--manifest-split", "validation",
                "--skip-existing", "--configs", json.dumps(entries), *(["--heads", str(heads)] if heads is not None else [])]

    def train(self, front: str, arm: str, round_index: int, seed: int) -> list[str]:
        kind = s3.training_settings(arm, round_index)["label_source"]
        sources = [f"{self.pass_root(front, 'round0')}:ELU-P:{kind}"]
        if round_index == 1:
            sources.append(f"{self.pass_root(front, 'round1')}:{arm}:{kind}")
        argv = [self.python, str(TRAIN_ENTRY), "train"]
        for source in sources:
            argv += ["--source", source]
        return argv + ["--arm", arm, "--round", str(round_index), "--seed", str(seed),
                       "--out-dir", str(self.training_dir(front, round_index, arm, seed)), "--threads", str(self.train_threads()),
                       "--best-so-far", "--checkpoint", *(["--foreach"] if OPTIMIZER_FOREACH else [])]

    def manifest(self, command: str, *extra: str) -> list[str]:
        return [self.python, str(HERE), command, "--run-root", str(self.run_root), *extra]


def s3_descriptor() -> str:
    from vsmt import lean_assignment as la

    return la.SELECTED_DESCRIPTOR


# --------------------------------------------------------------------------
# the job graph (ruling 104-7)
# --------------------------------------------------------------------------

def training_house_order(ctx: RunContext, front: str) -> tuple[list[str], list[str]]:
    """The front's usable train episodes split by ruling 104-1 1a, each in manifest order."""

    split = s3.checkpoint_split(s3.manifest_houses(s3.load_manifest(), "train"))
    usable = {row["episode_id"] for row in ctx.episodes(front, "train")}
    return ([house for house in split["training_houses"] if house in usable],
            [house for house in split["selection_houses"] if house in usable])


def build_jobs(ctx: RunContext) -> list[pool.Job]:
    """Every job of the run with its dependencies, priority, cost, cores, memory class and command."""

    P = PRIORITY
    jobs: list[pool.Job] = []
    for front in ctx.fronts:
        train_frames, validation_frames = ctx.frames(front, "train"), ctx.frames(front, "validation")
        train = [row["episode_id"] for row in ctx.episodes(front, "train")]
        validation = [row["episode_id"] for row in ctx.episodes(front, "validation")]
        _require(bool(train) and bool(validation), f"no_episodes:{front}")
        gates = ctx.gates_dir(front)
        jobs.append(pool.Job(f"{front}/probe-audit", "probe_audit", (), P["control"], 2.0 * min(train_frames.values()), 1, "audit_full",
                             lambda f=front: ctx.manifest("probe-audit", "--front", f), outputs=(str(gates / "audit_probe"),),
                             exit_status={3: "gate_failed"}))
        calibration = ctx.pass_root(front, "calibration")
        if front in ctx.adopt:
            jobs.append(pool.Job(f"{front}/adopt-calibration", "adopt_calibration", (), P["critical"], 1.0, 1, "pass",
                                 lambda f=front: ctx.manifest("adopt-calibration", "--front", f, "--from", str(ctx.adopt[f])),
                                 outputs=(str(calibration), str(gates / "adopt_probe")), exit_status={3: "gate_failed"}))
            calibration_ids = [f"{front}/adopt-calibration"]
        else:
            calibration_ids = []
            for episode in train:
                job_id = f"{front}/cal/{episode}"
                jobs.append(pool.Job(job_id, "calibration", (), P["critical"], train_frames[episode], 1, "pass",
                                     lambda f=front, e=episode, root=calibration: ctx.s2_04(f, "train", e, "TAF", calibration_config(), root,
                                                                                            flags=("--calibration", "--elu-p-counts", "--no-training-records")),
                                     outputs=(str(calibration / episode / "TAF"),)))
                calibration_ids.append(job_id)
        jobs.append(pool.Job(f"{front}/fit", "fit", tuple(calibration_ids), P["control"], 0.0, 1, "gate",
                             lambda f=front: ctx.manifest("fit", "--front", f), exit_status={3: "gate_failed"}))
        round0 = ctx.pass_root(front, "round0")
        round0_ids = []
        for episode in train:
            job_id = f"{front}/r0/{episode}"

            # every loop value is bound as a default: the builder runs at dispatch, after the loop has moved on to the last front
            def build_round0(f: str = front, e: str = episode, root: Path = round0) -> list[str]:
                config = rollout_config(ctx.fit_values(f))
                return ctx.s2_04(f, "train", e, "ELU-P", config, root, flags=("--heuristic-labels", json.dumps(config)))

            jobs.append(pool.Job(job_id, "round0", (f"{front}/fit",), P["critical"], train_frames[episode], 1, "pass", build_round0,
                                 outputs=(str(round0 / episode / "ELU-P"),)))
            round0_ids.append(job_id)
        jobs.append(pool.Job(f"{front}/gate-r0", "gate_round0", tuple(round0_ids), P["control"], 0.0, 1, "gate",
                             lambda f=front: ctx.manifest("gate-round0", "--front", f), exit_status={3: "gate_failed"}))
        jobs.append(pool.Job(f"{front}/probe-train", "probe_train", (f"{front}/gate-r0", "train-threads"), P["control"], 0.0, None, "train_probe",
                             lambda f=front: [ctx.python, str(TRAIN_ENTRY), "probe", "--source", f"{ctx.pass_root(f, 'round0')}:ELU-P:teacher",
                                              "--arm", "VSMT-lean", "--round", "0", "--houses", str(PROBE_TRAIN_HOUSES), "--epochs", "1",
                                              "--threads", str(ctx.train_threads()), "--out", str(ctx.gates_dir(f) / "train_probe.json"),
                                              *(["--foreach"] if OPTIMIZER_FOREACH else [])],
                             exit_status={3: "gate_failed"}))
        round1 = ctx.pass_root(front, "round1")
        round1_ids: dict[str, list[str]] = {}
        for arm in s3.TRAINED_ARMS:
            jobs.append(pool.Job(f"{front}/t0/{arm}", "train0", (f"{front}/gate-r0", "train-threads", f"{front}/probe-train"),
                                 P["critical"], TRAINING_COST, None,
                                 "train0", lambda f=front, a=arm: ctx.train(f, a, 0, arms.SEEDS[0]),
                                 outputs=(str(ctx.training_dir(front, 0, arm, arms.SEEDS[0])),), retries=1, exit_status={3: "diverged"},
                                 resumable=True, remote_push=(str(ctx.pass_root(front, "round0")),),
                                 remote_pull=(str(ctx.training_dir(front, 0, arm, arms.SEEDS[0])),)))
            round1_ids[arm] = []
            for episode in train:
                job_id = f"{front}/r1/{arm}/{episode}"

                def build_round1(f: str = front, a: str = arm, e: str = episode, root: Path = round1) -> list[str]:
                    extra: tuple[str, ...] = ()
                    if a == "HeuristicLabel":  # ruling 104-1 1c: its round-1 labels on its own trajectory; no teacher records needed
                        extra = ("--heuristic-labels", json.dumps(rollout_config(ctx.fit_values(f))), "--no-training-records")
                    return ctx.s2_04(f, "train", e, a, round1_config(a), root, heads=ctx.heads_file(f, 0, a, arms.SEEDS[0]), flags=extra)

                jobs.append(pool.Job(job_id, "round1", (f"{front}/t0/{arm}",), P["critical"], train_frames[episode], 1, "pass", build_round1,
                                     outputs=(str(round1 / episode / arm),)))
                round1_ids[arm].append(job_id)
            for seed in arms.SEEDS:
                jobs.append(pool.Job(f"{front}/t1/{arm}/s{seed}", "train1", (f"{front}/gate-r0", f"{front}/t0/{arm}", *round1_ids[arm]),
                                     P["critical"], TRAINING_COST, None, "train1", lambda f=front, a=arm, s=seed: ctx.train(f, a, 1, s),
                                     outputs=(str(ctx.training_dir(front, 1, arm, seed)),), retries=1, exit_status={3: "diverged"},
                                     resumable=True, remote_push=(str(ctx.pass_root(front, "round0")), str(ctx.pass_root(front, "round1"))),
                                     remote_pull=(str(ctx.training_dir(front, 1, arm, seed)),)))
        jobs.append(pool.Job(f"{front}/coverage", "coverage", (*round0_ids, *round1_ids["VSMT-lean"]), P["control"], 0.0, 1, "gate",
                             lambda f=front: ctx.manifest("coverage", "--front", f), stops_on_failure=False))  # report only
        merge_ids = []
        for arm, seeded in s3.SELECTION_ARMS.items():
            configs = list(enumerate(audit_configs(arm)))
            for seed in (arms.SEEDS if seeded else (None,)):
                if seeded:
                    deps: tuple[str, ...] = (f"{front}/probe-audit", f"{front}/t1/{heads_arm(arm)}/s{seed}")
                    priority = P["learned_audit"]
                else:
                    deps = (f"{front}/probe-audit", f"{front}/fit") if arm == "ELU-P" else (f"{front}/probe-audit",)
                    priority = P["rule_audit"]
                size = CONFIGS_PER_AUDIT_JOB["learned" if seeded else "rule"]
                chunks = [configs[start:start + size] for start in range(0, len(configs), size)]
                audit_ids = []
                for episode in validation:
                    for part in chunks:
                        span = f"c{part[0][0]:02d}-{part[-1][0]:02d}"
                        job_id = f"{front}/audit/{arm}/{'rule' if seed is None else f's{seed}'}/{span}/{episode}"

                        def build_audit(f: str = front, a: str = arm, s: int | None = seed, e: str = episode,
                                        c: list = part) -> list[str]:
                            chosen = c
                            if a == "ELU-P":  # ruling 104-1 1b: every ELU-P configuration carries the run-local fitted values
                                values = ctx.fit_values(f)
                                chosen = [(index, {**config, **values}) for index, config in c]
                            heads = ctx.heads_file(f, 1, heads_arm(a), s) if s is not None else None
                            return ctx.audit(f, e, a, s, chosen, heads=heads)

                        heads_file = ctx.heads_file(front, 1, heads_arm(arm), seed) if seed is not None else None
                        jobs.append(pool.Job(job_id, "audit", deps, priority, validation_frames[episode] * len(part), 1, "audit",
                                             build_audit, keep_partial=True,
                                             remote_push=(str(heads_file),) if heads_file is not None else (),
                                             remote_pull=tuple(str(ctx.group_root(front, arm, index, seed) / episode) for index, _ in part)))
                        audit_ids.append(job_id)
                for index, _config in configs:
                    job_id = f"{front}/merge/{group_name(arm, index, seed)}"
                    jobs.append(pool.Job(job_id, "merge", tuple(audit_ids), P["control"], 0.0, 1, "small",
                                         lambda f=front, a=arm, i=index, s=seed: [ctx.python, str(NODE_AUDIT), "merge",
                                                                                  "--output-root", str(ctx.group_root(f, a, i, s)), "--arm", a,
                                                                                  "--results", str(ctx.merged_path(f, a, i, s))]))
                    merge_ids.append(job_id)
        jobs.append(pool.Job(f"{front}/readings", "readings", (), P["control"], 0.0, 1, "gate",
                             lambda f=front: ctx.manifest("readings", "--front", f), soft_deps=tuple(merge_ids), exit_status={3: "gate_failed"}))
        jobs.append(pool.Job(f"{front}/probe-determinism", "probe_determinism", (f"{front}/readings",), P["control"],
                             float(min(validation_frames.values())), 1, "audit", lambda f=front: ctx.manifest("probe-determinism", "--front", f),
                             outputs=(str(gates / "determinism"),), exit_status={3: "gate_failed"}))
    for job in jobs:
        job.group = job.job_id.split("/", 1)[0]
        if job.kind in ("train0", "train1"):
            job.rank = 0
    first = ctx.fronts[0]
    training_houses, selection_houses = training_house_order(ctx, first)
    timing_deps = tuple(f"{first}/r0/{house}" for house in training_houses[:TIMING_TRAINING_HOUSES] + selection_houses[:TIMING_SELECTION_HOUSES])
    jobs.append(pool.Job("timing", "timing", timing_deps, PRIORITY["control"], 0.0, 4, "train_timing",
                         lambda: [ctx.python, str(TRAIN_ENTRY), "time", "--source", f"{ctx.pass_root(first, 'round0')}:ELU-P:teacher",
                                  "--arm", "VSMT-lean", "--round", "0", "--houses", str(TIMING_TRAINING_HOUSES), "--threads", "1,2,3,4",
                                  "--out", str(ctx.run_root / "train_timing.json"), *(["--foreach"] if OPTIMIZER_FOREACH else [])]))
    jobs.append(pool.Job("train-threads", "train_threads", ("timing",), PRIORITY["control"], 0.0, 1, "small",
                         lambda: ctx.manifest("train-threads", "--trainings", str(len(s3.TRAINED_ARMS) * len(arms.SEEDS) * len(ctx.fronts)))))
    if set(ctx.fronts) == set(FRONTS):  # the S3 calibration passes' grid positions, ruling 101 (1)(a) reading, report only (102-6)
        jobs.append(pool.Job("grid-reading", "grid_reading", ("instance/fit", "sam2/fit"), PRIORITY["control"], 0.0, 1, "small",
                             lambda: [ctx.python, str(GRID_REVIEW), "--calibration", str(ctx.front_dir("sam2") / "fit" / "calibration_report.json"),
                                      "--reference", str(ctx.front_dir("instance") / "fit" / "calibration_report.json"),
                                      "--output", str(ctx.run_root / "grid_reading.json")], exit_status={4: "done"},
                             stops_on_failure=False))  # report only (ruling 102-6 keeps the grids)
    return jobs


# --------------------------------------------------------------------------
# check (inputs of the run)
# --------------------------------------------------------------------------

def s3_02_roots(autodl: Path, tag: str) -> dict[str, Any]:
    return {"raw": autodl / "vsmt_outputs" / f"s3-02-{tag}", "geometry": autodl / "vsmt_private" / f"s3-02-geometry-{tag}",
            "cache": {front: autodl / "vsmt_caches" / f"s3-02-{front}-{tag}" for front in FRONTS}}


def reid_heads(reid: Mapping[str, Path], fronts: Sequence[str], problems: list[str]) -> dict[str, Any]:
    """Each front end's ReID head against its S0-03 pinned digest (a mismatch is added to ``problems``)."""

    from vsmt import lean_assignment as la
    import s2_06_manifest

    heads = {}
    for front in fronts:
        path = Path(reid[front])
        payload = load_json(path) if path.exists() else {}
        pinned = la.reid_weights_sha256_for(FRONTS[front])
        ok = bool(payload) and payload.get("sha256") == pinned and s2_06_manifest.payload_digest_ok(payload)
        heads[front] = {"file": str(path), "file_sha256": sha256_file(path) if path.exists() else None, "payload_sha256": payload.get("sha256"),
                        "pinned_sha256": pinned, "matches": ok}
        if not ok:
            problems.append(f"reid_head_differs_from_the_pinned_digest:{front}")
    return heads


def root_digests(roots: Mapping[str, Any], fronts: Sequence[str]) -> dict[str, Any]:
    """What a provisional check rests on, read from the roots: every succeeded raw receipt's sha256, each geometry stage receipt's
    sha256, and every succeeded cache episode's seal payload digest, per split (train and validation only; test is never read)."""

    import s3_02_manifest as s3_02

    out: dict[str, Any] = {"raw": {}, "geometry": {}, "cache": {front: {} for front in fronts}}
    for split in SPLITS:
        raw_root, geometry_root = Path(roots["raw"]) / split, Path(roots["geometry"]) / split
        out["raw"][split] = {house: sha256_file(raw_root / house / "receipt.json") for house in s3_02.succeeded(raw_root)}
        receipt = geometry_root / "s1_04_geometry_receipt.json"
        out["geometry"][split] = sha256_file(receipt) if receipt.exists() else None
        for front in fronts:
            cache_root = Path(roots["cache"][front]) / split
            seals = {}
            for episode in s3_02.succeeded(cache_root):
                seal = cache_root / episode / "episode_seal.json"
                seals[episode] = load_json(seal).get("payload_sha256") if seal.exists() else None
            out["cache"][front][split] = seals
    return out


def provisional_inputs(*, roots: Mapping[str, Any], reid: Mapping[str, Path], fronts: Sequence[str]) -> dict[str, Any]:
    """The inputs before S3-02 has exported its run manifest (user 2026-10-04: start S3-03 on the S3-02 host's free CPU while the SAM2
    cache still runs). Train and validation are read from their roots and must already be complete by S3-02's own completeness rules
    (geometry_problems, cache_problems: every raw episode accounted for, a cache failure only for a data reason, the stage receipt
    complete); the test roots only need their markers (pending until S3-02 seals them; never read). The usable episodes are built
    exactly as from the exports, and root_digests records what they rest on. The first full check after S3-02's export recomputes
    the digests and the episodes and stops the run if anything differs (cmd_check); verify refuses inputs that are still provisional.
    """

    from vsmt import lean_object_geometry as og
    from vsmt import lean_test_seal
    import s3_02_manifest as s3_02

    problems: list[str] = []
    refusal = lean_test_seal.refusal([Path(roots["raw"]) / split for split in SPLITS] + [Path(roots["geometry"]) / split for split in SPLITS]
                                     + [Path(roots["cache"][front]) / split for front in fronts for split in SPLITS], reader="s3-03 check")
    if refusal:
        problems.append(f"train_or_validation_root_sealed:{refusal}")
    manifest = s3.load_manifest()
    episodes: dict[str, dict[str, list[dict[str, Any]]]] = {front: {} for front in fronts}
    counts: dict[str, Any] = {}
    for split in SPLITS:
        houses = s3.manifest_houses(manifest, split)
        raw_root, geometry_root = Path(roots["raw"]) / split, Path(roots["geometry"]) / split
        raw_ok = set(s3_02.succeeded(raw_root))
        problems += [f"provisional_geometry_incomplete:{split}:{item}" for item in s3_02.geometry_problems(geometry_root, raw_root)[:5]]
        geometry_ok = {house for house in houses if (geometry_root / house / og.TABLE_FILE_NAME).exists()}
        split_counts = {"manifest_houses": len(houses), "raw_succeeded": len(raw_ok), "geometry_tables": len(geometry_ok)}
        for front in fronts:
            source = FRONTS[front]
            cache_root = Path(roots["cache"][front]) / split
            problems += [f"provisional_cache_incomplete:{front}:{split}:{item}" for item in s3_02.cache_problems(cache_root, raw_root, source)[:5]]
            cache_ok = {episode: receipt for episode, receipt in s3_02.receipts(cache_root).items() if receipt.get("status") == "succeeded"}
            usable = [house for house in houses if house in raw_ok and house in geometry_ok and house in cache_ok]
            outside = sorted(set(cache_ok) - set(houses))
            if outside:
                problems.append(f"cache_episodes_outside_the_manifest:{front}:{split}:{outside[:3]}")
            episodes[front][split] = [{"episode_id": house, "frames": int(cache_ok[house].get("frames") or 0)} for house in usable]
            split_counts[f"usable_{front}"] = len(usable)
        counts[split] = split_counts
    markers = {}
    for kind, root in (("raw", Path(roots["raw"]) / "test"), ("geometry", Path(roots["geometry"]) / "test"),
                       *((f"{front}_cache", Path(roots["cache"][front]) / "test") for front in fronts)):
        marker_path = root / lean_test_seal.MARKER_NAME  # only the marker file is read, never a test episode
        marker = load_json(marker_path) if marker_path.exists() else {}
        # recorded only: S3-02 may not have built this test root yet (the SAM2 test cache comes last) and a provisional run never
        # reads test; the full check after S3-02's export requires every test root sealed by the exported seal
        markers[kind] = {"path": str(marker_path), "root_exists": root.exists(), "state": marker.get("state")}
        if marker and marker.get("state") not in (lean_test_seal.STATE_PENDING, lean_test_seal.STATE_SEALED):
            problems.append(f"test_root_marker_in_an_unknown_state:{kind}:{marker.get('state')}")
    heads = reid_heads(reid, fronts, problems)
    return {"problems": problems, "provisional": {"digests": root_digests(roots, fronts), "written_utc": utc_now(),
                                                  "rule": "user 2026-10-04: start beside S3-02; confirmed by the first full check"},
            "s3_02": {"tag": None, "manifest": None, "code_commit": None},
            "roots": {"raw": {split: str(Path(roots["raw"]) / split) for split in SPLITS},
                      "geometry": {split: str(Path(roots["geometry"]) / split) for split in SPLITS},
                      "cache": {front: {split: str(Path(roots["cache"][front]) / split) for split in SPLITS} for front in fronts}},
            "reid": heads, "test_seal": {"provisional": True, "markers": markers}, "episodes": episodes, "counts": counts}


def confirm_provisional(previous: Mapping[str, Any], report: Mapping[str, Any], roots: Mapping[str, Any],
                        fronts: Sequence[str]) -> dict[str, Any] | None:
    """Any check after a provisional one (a provisional resume, or the first full check once S3-02 has exported): the episodes and
    the root digests must be exactly what the run started from."""

    if not previous.get("provisional") or "episodes" not in report:
        return None
    digests = (report.get("provisional") or {}).get("digests") or root_digests(roots, fronts)
    differs = [part for part, same in (("episodes", previous.get("episodes") == report["episodes"]),
                                       ("digests", previous["provisional"].get("digests") == digests)) if not same]
    return {"provisional_checked_utc": previous["provisional"].get("written_utc"), "confirmed_utc": utc_now(), "differs": differs}


def check_inputs(*, roots: Mapping[str, Any], export_dir: Path, tag: str, reid: Mapping[str, Path],
                 fronts: Sequence[str] = tuple(FRONTS), provisional: bool = False) -> dict[str, Any]:
    """Ruling 104-2: the S3-02 products equal its run manifest, the four test roots are sealed by the exported seal, the heads match.
    With ``provisional`` and no S3-02 run manifest yet, provisional_inputs reads the train and validation roots instead."""

    from vsmt import lean_object_geometry as og
    from vsmt import lean_test_seal

    problems: list[str] = []
    name = lambda part: export_dir / f"vsmt_lean_s3_02_{part}_{tag}.json"  # noqa: E731
    manifest_path = name("manifest")
    if not manifest_path.exists():
        if provisional:
            return provisional_inputs(roots=roots, reid=reid, fronts=fronts)
        return {"problems": [f"s3_02_manifest_missing:{manifest_path}"]}
    s3_02 = load_json(manifest_path)
    if s3_02.get("problems"):
        problems.append(f"s3_02_manifest_has_problems:{s3_02['problems'][:5]}")
    for file_name, record in sorted((s3_02.get("exports") or {}).items()):
        path = export_dir / file_name
        if not path.exists() or sha256_file(path) != record.get("sha256"):
            problems.append(f"s3_02_export_differs_from_its_manifest:{file_name}")
    refusal = lean_test_seal.refusal([Path(roots["raw"]) / split for split in SPLITS] + [Path(roots["geometry"]) / split for split in SPLITS]
                                     + [Path(roots["cache"][front]) / split for front in fronts for split in SPLITS], reader="s3-03 check")
    if refusal:
        problems.append(f"train_or_validation_root_sealed:{refusal}")
    manifest = s3.load_manifest()
    episodes: dict[str, dict[str, list[dict[str, Any]]]] = {front: {} for front in fronts}
    counts: dict[str, Any] = {}
    for split in SPLITS:
        houses = s3.manifest_houses(manifest, split)
        raw_root, geometry_root = Path(roots["raw"]) / split, Path(roots["geometry"]) / split
        raw_rows = (load_json(name(f"raw_{split}")).get("houses") or []) if name(f"raw_{split}").exists() else []
        raw_ok = set()
        for row in raw_rows:
            if row.get("status") != "succeeded":
                continue
            receipt = raw_root / row["house_id"] / "receipt.json"
            if not receipt.exists() or sha256_file(receipt) != row.get("receipt_sha256"):
                problems.append(f"raw_receipt_differs_from_the_export:{split}:{row['house_id']}")
            raw_ok.add(row["house_id"])
        geometry_receipt = geometry_root / "s1_04_geometry_receipt.json"
        if not name(f"geometry_{split}").exists() or not geometry_receipt.exists() or sha256_file(geometry_receipt) != sha256_file(name(f"geometry_{split}")):
            problems.append(f"geometry_receipt_differs_from_the_export:{split}")
        geometry_ok = {house for house in houses if (geometry_root / house / og.TABLE_FILE_NAME).exists()}
        split_counts = {"manifest_houses": len(houses), "raw_succeeded": len(raw_ok), "geometry_tables": len(geometry_ok)}
        recorded = (s3_02.get("splits") or {}).get(split) or {}
        if recorded.get("raw_succeeded") is not None and recorded["raw_succeeded"] != len(raw_ok):
            problems.append(f"raw_succeeded_differs_from_the_s3_02_manifest:{split}")
        for front in fronts:
            source = FRONTS[front]
            cache_root = Path(roots["cache"][front]) / split
            rows = (load_json(name(f"{front}_cache_{split}")).get("episodes") or []) if name(f"{front}_cache_{split}").exists() else []
            cache_ok: dict[str, dict[str, Any]] = {}
            for row in rows:
                if row.get("status") != "succeeded":
                    continue
                seal = cache_root / row["episode_id"] / "episode_seal.json"
                sealed = load_json(seal) if seal.exists() else {}
                if sealed.get("payload_sha256") != row.get("episode_seal_sha256") or (sealed.get("mask_source") or "sam2") != source:
                    problems.append(f"cache_seal_differs_from_the_export:{front}:{split}:{row['episode_id']}")
                cache_ok[row["episode_id"]] = row
            recorded_cache = recorded.get(f"cache_succeeded_{source}")
            if recorded_cache is not None and recorded_cache != len(cache_ok):
                problems.append(f"cache_succeeded_differs_from_the_s3_02_manifest:{front}:{split}")
            usable = [house for house in houses if house in raw_ok and house in geometry_ok and house in cache_ok]
            outside = sorted(set(cache_ok) - set(houses))
            if outside:
                problems.append(f"cache_episodes_outside_the_manifest:{front}:{split}:{outside[:3]}")
            episodes[front][split] = [{"episode_id": house, "frames": int(cache_ok[house].get("frames") or 0)} for house in usable]
            split_counts[f"usable_{front}"] = len(usable)
        counts[split] = split_counts
    seal_path = name("test_seal")
    seal_report: dict[str, Any] = {"file": str(seal_path)}
    if not seal_path.exists():
        problems.append("test_seal_export_missing")
    else:
        seal = load_json(seal_path)
        body = {key: value for key, value in seal.items() if key != "seal_sha256"}
        digest = seal.get("seal_sha256")
        if lean_test_seal.seal_sha256(body) != digest:
            problems.append("test_seal_export_digest_differs")
        markers = {}
        for kind in lean_test_seal.SEAL_KINDS:  # ruling 104-2: only the four marker files are read, never a test episode
            marker_path = Path(body["kinds"][kind]["root"]) / lean_test_seal.MARKER_NAME
            marker = load_json(marker_path) if marker_path.exists() else {}
            ok = marker.get("state") == lean_test_seal.STATE_SEALED and marker.get("seal_sha256") == digest
            markers[kind] = {"path": str(marker_path), "state": marker.get("state"), "matches": ok}
            if not ok:
                problems.append(f"test_root_not_sealed_by_the_exported_seal:{kind}")
        seal_report.update({"seal_sha256": digest, "markers": markers})
    heads = reid_heads(reid, fronts, problems)
    return {"problems": problems, "s3_02": {"tag": tag, "manifest": {"file": str(manifest_path), "sha256": sha256_file(manifest_path)},
                                            "code_commit": s3_02.get("code_commit")},
            "roots": {"raw": {split: str(Path(roots["raw"]) / split) for split in SPLITS},
                      "geometry": {split: str(Path(roots["geometry"]) / split) for split in SPLITS},
                      "cache": {front: {split: str(Path(roots["cache"][front]) / split) for split in SPLITS} for front in fronts}},
            "reid": heads, "test_seal": seal_report, "episodes": episodes, "counts": counts}


def cmd_check(args: argparse.Namespace) -> int:
    run_root, export_dir = Path(args.run_root), Path(args.export_dir)
    fronts = tuple(f for f in args.fronts.split(",") if f)
    roots = s3_02_roots(Path(args.autodl_root), args.s3_02_tag)
    previous = load_json(run_root / "inputs.json") if (run_root / "inputs.json").exists() else {}
    report = check_inputs(roots=roots, export_dir=export_dir, tag=args.s3_02_tag,
                          reid={"instance": Path(args.instance_reid), "sam2": Path(args.sam2_reid)}, fronts=fronts,
                          provisional=args.provisional)
    confirmation = confirm_provisional(previous, report, roots, fronts)
    if confirmation is not None:
        report["provisional_confirmation" if not report.get("provisional") else "provisional_recheck"] = confirmation
        if report.get("provisional"):
            report["provisional"]["started_utc"] = previous["provisional"].get("started_utc") or previous["provisional"].get("written_utc")
        if confirmation["differs"]:
            report["problems"].append(f"provisional_inputs_changed:{confirmation['differs']}")
    elif report.get("provisional"):
        report["provisional"]["started_utc"] = report["provisional"]["written_utc"]
    if git("status", "--porcelain", repo=Path(args.repo_root)):
        report["problems"].append("worktree_not_clean")
    info = resources()
    free = shutil.disk_usage(run_root.parent if run_root.parent.exists() else Path("/")).free / 2 ** 30
    floor = RUN_FLOOR_GIB if run_started(run_root) else args.min_free_gib  # a resume has already written most of its outputs
    if free < floor:
        report["problems"].append(f"disk_free_below_{floor}_gib:{round(free, 1)}")
    payload = {"stage": STAGE, "step": "check", "checked_utc": utc_now(), "code_commit": git("rev-parse", "HEAD", repo=Path(args.repo_root)),
               "run_root": str(run_root), "fronts": list(fronts), "resources": info, "disk_free_gib": round(free, 1), **report}
    write_json(run_root / "inputs.json", payload)
    print(f"[s3-03-check] {payload['counts'] if 'counts' in payload else ''}; problems: {payload['problems'] or 'none'}")
    return 0 if not payload["problems"] else 3


# --------------------------------------------------------------------------
# run and status
# --------------------------------------------------------------------------

def load_context(run_root: Path, *, adopt: Mapping[str, str] | None = None) -> RunContext:
    inputs = load_json(run_root / "inputs.json")
    if adopt is None and (run_root / ADOPT_FILE).exists():
        adopt = load_json(run_root / ADOPT_FILE)["adopt"]
    return RunContext(run_root=run_root, inputs=inputs, fronts=tuple(inputs.get("fronts") or FRONTS), adopt=dict(adopt or {}))


def run_started(run_root: Path) -> bool:
    return any(path for path in (run_root / "jobs").glob("*.json")) if (run_root / "jobs").exists() else False


def calibration_settled(run_root: Path) -> bool:
    """Whether a calibration or adoption job has run (or runs): after that the adoption choice can no longer change."""

    for path in (run_root / "jobs").glob("*.json") if (run_root / "jobs").exists() else ():
        if path.name.endswith(".rss.json"):
            continue
        state = load_json(path)
        job_id = str(state.get("job_id", ""))
        if ("/cal/" in job_id or job_id.endswith("/adopt-calibration")) and state.get("status") in ("done", "running"):
            return True
    return False


def resolve_adopt(run_root: Path, requested: Mapping[str, str] | None) -> dict[str, str]:
    """The run's adoption choice, kept in the run root so every resume builds the same job graph.

    A resume without the option keeps it.  A different choice is accepted only while no calibration or adoption job has run
    (for example after a refused adoption probe); afterwards it is refused.
    """

    unknown = sorted(set(requested or {}) - set(FRONTS))
    _require(not unknown, f"adopt_calibration_names_no_front:{unknown}")
    path = run_root / ADOPT_FILE
    saved = dict(load_json(path)["adopt"]) if path.exists() else None
    if requested is None and saved is not None:
        return saved
    chosen = dict(requested or {})
    if saved is not None and chosen == saved:
        return saved
    _require(not calibration_settled(run_root), f"adopt_calibration_differs_from_the_settled_choice:{saved}")
    write_json(path, {"adopt": chosen, "replaced": saved, "written_utc": utc_now(),
                      "rule": "kept for every resume; it may change only while no calibration or adoption job has run"})
    return chosen


def note_refusal(run_root: Path, reason: str) -> None:
    """A refused run says so in pool.json, so the status file never shows an earlier run's stop reason."""

    path = run_root / "pool.json"
    old = load_json(path) if path.exists() else {}
    write_json(path, {**old, "stop_reason": f"run_refused:{reason}", "running": [], "updated_utc": utc_now()})


def cmd_run(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    inputs = load_json(run_root / "inputs.json")
    head = git("rev-parse", "HEAD")
    if inputs.get("problems") or inputs.get("code_commit") != head:
        reason = f"run check at {head[:12]} first (problems: {inputs.get('problems')}, checked at {str(inputs.get('code_commit'))[:12]})"
        note_refusal(run_root, reason)
        print(f"[s3-03-run] refused: {reason}", file=sys.stderr)
        return 2
    requested = None if args.adopt_calibration is None else dict(item.split("=", 1) for item in args.adopt_calibration)
    try:
        adopt = resolve_adopt(run_root, requested)
    except DriverError as exc:
        note_refusal(run_root, str(exc))
        raise
    ctx = load_context(run_root, adopt=adopt)
    info = resources()
    cores = int(args.budget_cores or info["cpu_quota"]) - pool.RESERVE_CORES
    memory_bytes = int(args.memory_bytes or info["memory_bytes"])
    gib = memory_bytes / 2 ** 30 - pool.RESERVE_GIB
    defaults = dict(MEMORY_DEFAULTS_GIB)
    for item in args.memory_gib or []:
        key, value = item.split("=", 1)
        defaults[key] = float(value)
    fixed = {}
    for item in args.memory_fixed_gib or []:  # user 2026-10-04: tighter reservations on a memory-bound host; the live guard stays
        key, value = item.split("=", 1)
        _require(float(value) > 0, f"memory_fixed_gib_not_positive:{item}")
        fixed[key] = float(value)
    write_json(run_root / "workers.json", {"budget_cores": cores, "budget_gib": round(gib, 1), "reserve_cores": pool.RESERVE_CORES,
                                           "reserve_gib": pool.RESERVE_GIB, "memory_defaults_gib": defaults, "resources": info,
                                           "rule": ("ruling 104-3: cores and memory from the cgroup (cpu.max, memory.max), 2 cores and 8 GiB kept "
                                                    "free; single-threaded jobs pinned to one thread, trainings to TRAIN_THREADS; memory per "
                                                    "class 1.25 x the measured peak once measured"),
                                           "adopt_calibration": adopt, "written_utc": utc_now(),
                                           "memory_guard": ("cgroup memory.stat anon+shmem" if pool.cgroup_process_bytes() is not None else
                                                            "unavailable here (no cgroup v2 memory.stat): dispatch never pauses on memory"),
                                           "memory_fallbacks": {"train1": "2 x the measured round-0 peak until a round-1 training is measured"},
                                           "inflight_gib_per_running_job": INFLIGHT_GIB,
                                           "memory_fixed_gib": fixed or None,
                                           "remote_hosts": {"dir": str(run_root / "hosts"), "rule": (
                                               "user 2026-10-04: hosts admitted by remote_hosts.py admit (same environment, code and "
                                               "inputs byte for byte, audits rerun identical) are read every 30 s; audits and trainings "
                                               "may run there, everything else runs here; outputs are pulled back to the same paths")},
                                           "memory_fixed_rule": ("an operator's reservation per class (MEMORY_FIXED_GIB) replaces the measured "
                                                                 "peak x 1.25 and the fallback; scheduling only, no output changes; the live "
                                                                 "cgroup guard still pauses dispatch") if fixed else None})
    import remote_hosts

    jobs = build_jobs(ctx)
    runner = pool.Pool(jobs, run_root=run_root, log_dir=Path(args.log_dir), budget_cores=cores, budget_gib=gib, memory_defaults=defaults,
                       train_threads=ctx.train_threads, commit=head, code_change=disallowed_changes,
                       accept_code_change=args.accept_code_change, poll_seconds=args.poll_seconds, disk_root=run_root,
                       min_free_gib=args.min_free_gib, memory_limit_bytes=memory_bytes - int(pool.RESERVE_GIB * 2 ** 30),
                       wrapper=[ctx.python, str(JOBS_SCRIPT), "run-measured"], retry_failed=args.retry_failed,
                       memory_fallbacks={"train1": ("train0", 2.0)}, inflight_gib=INFLIGHT_GIB, group_order=ctx.fronts,
                       memory_fixed=fixed, hosts=lambda: remote_hosts.load_hosts(run_root),
                       remote_runner=[ctx.python, str(REMOTE_SCRIPT), "remote-run"],
                       suspend_host=lambda name, reason: remote_hosts.suspend(run_root, name, reason))
    print(f"[s3-03-run] {len(jobs)} jobs, {cores} cores, {round(gib, 1)} GiB, fronts {list(ctx.fronts)}, commit {head[:12]}", flush=True)
    code = runner.run()
    print(f"[s3-03-run] finished: {runner.stop_reason or 'all jobs ended'}")
    return code


def cmd_status(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    snapshot = load_json(run_root / "pool.json") if (run_root / "pool.json").exists() else {}
    states = [load_json(path) for path in sorted((run_root / "jobs").glob("*.json")) if not path.name.endswith(".rss.json")]
    by_status: dict[str, int] = {}
    for state in states:
        by_status[state["status"]] = by_status.get(state["status"], 0) + 1
    print(json.dumps({"stop_reason": snapshot.get("stop_reason"), "updated_utc": snapshot.get("updated_utc"), "jobs_by_status": by_status,
                      "counts_by_kind": snapshot.get("counts_by_kind"), "running": len(snapshot.get("running") or []),
                      "failed": [s["job_id"] for s in states if s["status"] in ("failed", "gate_failed")][:10],
                      "diverged": [s["job_id"] for s in states if s["status"] == "diverged"]}, indent=1))
    return 0


# --------------------------------------------------------------------------
# job subcommands: fit, the round-0 gate, the thread count, probes, readings, coverage, adoption
# --------------------------------------------------------------------------

def episode_dir(ctx: RunContext, front: str, pass_name: str, episode: str, arm: str) -> Path:
    return ctx.pass_root(front, pass_name) / episode / arm


def cmd_fit(args: argparse.Namespace) -> int:
    """Ruling 104-1 1b: the calibration report and the ELU-P fit of one front end, written into the run (run-local values)."""

    from vsmt import lean_development as dev

    ctx = load_context(Path(args.run_root))
    front, source = args.front, FRONTS[args.front]
    collector, records, episodes, problems = dev.CalibrationCollector(), [], [], []
    for row in ctx.episodes(front, "train"):
        folder = episode_dir(ctx, front, "calibration", row["episode_id"], "TAF")
        receipt = load_json(folder / "receipt.json") if (folder / "receipt.json").exists() else {}
        if receipt.get("status") != "succeeded" or receipt.get("mask_source") != source or receipt.get("config") != calibration_config():
            problems.append(f"calibration_episode_unusable:{row['episode_id']}")
            continue
        collector.merge(dev.CalibrationCollector.from_json(load_json(folder / "calibration.json")))
        records.append(load_json(folder / "elu_p_counts.json"))
        episodes.append(row["episode_id"])
    out_dir = ctx.front_dir(front) / "fit"
    if problems:
        write_json(out_dir / "elu_p_fit.json", {"stage": STAGE, "front": front, "problems": problems})
        print(f"[s3-03-fit] {front}: {len(problems)} calibration episodes unusable: {problems[:3]}", file=sys.stderr)
        return 1
    report = {"stage": dev.STAGE_ID, "pass": "calibration", "arm": "TAF", "episodes": episodes, "mask_source": source,
              "code_commit": git("rev-parse", "HEAD"), **collector.report(), "histograms": collector.to_json()["histograms"]}
    write_json(out_dir / "calibration_report.json", report)
    rollout = {name: arms.ROLLOUT_CONFIG[name] for name in arms.ROLLOUT_CONFIG_PARAMETERS}
    registered = arms.elu_p_fitted(load_json(S0_05_CONTRACT), source)
    try:
        fitted = dev.fit_elu_p(records, rollout_config=rollout)
    except dev.LeanDevelopmentError as exc:  # ruling 104-2: a degenerate fit stops the run
        write_json(out_dir / "elu_p_fit.json", {"stage": STAGE, "front": front, "refused": str(exc), "episodes": len(episodes)})
        print(f"[s3-03-fit] {front}: the fit is refused: {exc}", file=sys.stderr)
        return 3
    values = {name: fitted["values"][name] for name in arms.ELU_P_FITTED}
    finite = all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in values.values())
    write_json(out_dir / "elu_p_fit.json", {"stage": STAGE, "front": front, "mask_source": source, "episodes": episodes, **fitted,
                                            "values_registered_in_s0_05_at_fit_time": registered, "code_commit": git("rev-parse", "HEAD"),
                                            "rule": ("ruling 104-1 1b: the S3 fit over every usable S3 train episode of this front end; the run "
                                                     "reads these run-local values, the registration commit replaces S0-05's values with them, "
                                                     "and verify checks the two equal bit for bit")})
    if not finite:
        print(f"[s3-03-fit] {front}: non-finite fitted values {values}", file=sys.stderr)
        return 3
    write_json(ctx.fit_values_path(front), {"front": front, "mask_source": source, "values": values, "values_sha256": canonical_sha256(values),
                                            "episodes": len(episodes), "code_commit": git("rev-parse", "HEAD"), "written_utc": utc_now()})
    print(f"[s3-03-fit] {front}: {values} from {len(episodes)} episodes")
    return 0


def cmd_gate_round0(args: argparse.Namespace) -> int:
    """Ruling 104-2: G4 (HeuristicLabel reproduces ELU-P on its own trajectory) and the split-level nuisance probe, plus readings."""

    from vsmt import lean_evaluation as ev
    from vsmt import lean_teacher as lt

    ctx = load_context(Path(args.run_root))
    front = args.front
    expected = rollout_config(ctx.fit_values(front))
    reproduction = {"fragments": 0, "fragment_mismatches": 0, "existence_rows": 0, "existence_mismatches": 0}
    heuristic_totals: dict[str, int] = {}
    tally = ev.NuisanceTally()
    problems: list[str] = []
    for row in ctx.episodes(front, "train"):
        folder = episode_dir(ctx, front, "round0", row["episode_id"], "ELU-P")
        receipt = load_json(folder / "receipt.json") if (folder / "receipt.json").exists() else {}
        block = (receipt.get("heuristic_records") or {}).get("reproduction")
        if receipt.get("status") != "succeeded" or receipt.get("config") != expected or block is None:
            problems.append(f"round0_episode_unusable:{row['episode_id']}")
            continue
        for name in reproduction:
            reproduction[name] += int(block[name])
        for name, value in receipt["heuristic_records"]["totals"].items():
            heuristic_totals[name] = heuristic_totals.get(name, 0) + int(value)
        for line in read_gz_lines(folder / "nuisance.jsonl.gz"):
            tally.add(line)
    nuisance = tally.result()
    largest = nuisance["largest_advantage"]
    g4_pass = not problems and reproduction["fragment_mismatches"] == 0 and reproduction["existence_mismatches"] == 0
    nuisance_pass = not problems and (largest is None or largest <= lt.NUISANCE_MAXIMUM_ADVANTAGE)
    report = {"stage": STAGE, "gate": "round0", "front": front, "episodes": len(ctx.episodes(front, "train")), "problems": problems,
              "g4": {"rule": G4_RULE, "reproduction": reproduction, "pass": g4_pass},
              "nuisance": {"rule": NUISANCE_GATE_RULE, "maximum_advantage": lt.NUISANCE_MAXIMUM_ADVANTAGE, "largest_advantage": largest,
                           "pass": nuisance_pass, "probes": nuisance},
              "label_composition_report_only": {"teacher": {block: tally.labels[block] for block in tally.labels},
                                                "heuristic_label_totals": heuristic_totals},
              "pass": g4_pass and nuisance_pass, "checked_utc": utc_now()}
    write_json(ctx.gates_dir(front) / "round0.json", report)
    print(f"[s3-03-gate-round0] {front}: G4 {reproduction} pass={g4_pass}; nuisance largest {largest} pass={nuisance_pass}")
    return 0 if report["pass"] else 3


def cmd_train_threads(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    timing = load_json(run_root / "train_timing.json")
    workers = run_root / "workers.json"  # the run's own budget (it may have been set below the quota)
    cores = int(load_json(workers)["budget_cores"]) if workers.exists() else int(resources()["cpu_quota"]) - pool.RESERVE_CORES
    choice = pool.choose_train_threads({row["threads"]: row["epoch_seconds"] for row in timing["timings"]}, cores=cores,
                                       trainings=int(args.trainings))
    write_json(run_root / "train_threads.json", {**choice, "timing_file_sha256": sha256_file(run_root / "train_timing.json"),
                                                  "houses": timing.get("houses"), "written_utc": utc_now()})
    print(f"[s3-03-train-threads] TRAIN_THREADS={choice['train_threads']} ({choice['candidates']})")
    return 0


def smallest(rows: Sequence[Mapping[str, Any]]) -> str:
    return sorted(rows, key=lambda row: (int(row.get("frames") or 0), row["episode_id"]))[0]["episode_id"]


def cmd_probe_audit(args: argparse.Namespace) -> int:
    """Ruling 104-2: the metrics-only audit equals the full node audit on one S3 train episode (TAF at the calibration config)."""

    import lean_s2_05_node_audit as audit

    ctx = load_context(Path(args.run_root))
    front = args.front
    episode = smallest(ctx.episodes(front, "train"))
    base = ctx.gates_dir(front) / "audit_probe"
    files = {}
    for mode in ("full", "metrics"):
        argv = [ctx.python, str(NODE_AUDIT), "run", "--cache-root", str(ctx.cache_root(front, "train")),
                "--episode-root", str(ctx.raw_root("train") / episode), "--geometry-root", str(ctx.geometry_root("train")),
                "--episode-id", episode, "--arm", "TAF", "--config", json.dumps(calibration_config()), "--descriptor", s3_descriptor(),
                "--weights", ctx.reid(front), "--mask-source", FRONTS[front], "--device", "cpu", "--manifest-split", "train",
                "--output-root", str(base / mode), *(["--metrics-only"] if mode == "metrics" else [])]
        completed = subprocess.run(argv)
        if completed.returncode != 0:
            print(f"[s3-03-probe-audit] {front}: the {mode} audit exited {completed.returncode}", file=sys.stderr)
            return 1
        files[mode] = base / mode / episode / "TAF" / audit.AUDIT_FILE_NAME
    result = audit.compare_audits(load_json(files["full"]), load_json(files["metrics"]))
    write_json(ctx.gates_dir(front) / "audit_equivalence.json", {"stage": STAGE, "gate": "audit_equivalence", "front": front, **result,
                                                                 "files": {k: str(v) for k, v in files.items()}, "checked_utc": utc_now()})
    print(f"[s3-03-probe-audit] {front} {episode}: identical={result['identical']}")
    return 0 if result["identical"] else 3


def cmd_adopt_calibration(args: argparse.Namespace) -> int:
    """Take an existing calibration pass of this front end (the S3 pre-fit) after reproducing one of its episodes byte for byte."""

    ctx = load_context(Path(args.run_root))
    front, source, origin = args.front, FRONTS[args.front], Path(getattr(args, "from"))
    target = ctx.pass_root(front, "calibration")
    names = ("receipt.json", "calibration.json", "elu_p_counts.json")
    problems, commits = [], set()
    for row in ctx.episodes(front, "train"):
        folder = origin / row["episode_id"] / "TAF"
        receipt = load_json(folder / "receipt.json") if (folder / "receipt.json").exists() else {}
        if (receipt.get("status") != "succeeded" or receipt.get("mask_source") != source or receipt.get("config") != calibration_config()
                or not all((folder / name).exists() for name in names)):
            problems.append(row["episode_id"])
        commits.add(receipt.get("code_commit"))
    extra = sorted(p.name for p in origin.iterdir() if p.is_dir() and p.name not in {r["episode_id"] for r in ctx.episodes(front, "train")})
    if problems or extra:
        print(f"[s3-03-adopt] {front}: refused: unusable {problems[:3]} ({len(problems)}), outside the run's episodes {extra[:3]}", file=sys.stderr)
        return 2
    episode = smallest(ctx.episodes(front, "train"))
    probe_root = ctx.gates_dir(front) / "adopt_probe"
    completed = subprocess.run(ctx.s2_04(front, "train", episode, "TAF", calibration_config(), probe_root,
                                         flags=("--calibration", "--elu-p-counts", "--no-training-records")))
    if completed.returncode != 0:
        return 1
    same = {name: sha256_file(probe_root / episode / "TAF" / name) == sha256_file(origin / episode / "TAF" / name)
            for name in ("calibration.json", "elu_p_counts.json")}
    report = {"stage": STAGE, "front": front, "adopted_from": str(origin), "receipt_commits": sorted(str(c) for c in commits),
              "probe_episode": episode, "probe_identical": same, "identical": all(same.values()), "checked_utc": utc_now()}
    write_json(ctx.gates_dir(front) / "adopt_calibration.json", report)
    if not report["identical"]:
        print(f"[s3-03-adopt] {front}: the calibration of {episode} does not reproduce: {same}", file=sys.stderr)
        return 3
    for row in ctx.episodes(front, "train"):
        destination = target / row["episode_id"] / "TAF"
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copy2(origin / row["episode_id"] / "TAF" / name, destination / name)
    print(f"[s3-03-adopt] {front}: {len(ctx.episodes(front, 'train'))} calibration episodes adopted from {origin} (probe identical)")
    return 0


def job_status(run_root: Path, job_id: str) -> str | None:
    path = run_root / "jobs" / f"{pool.state_key(job_id)}.json"
    return load_json(path)["status"] if path.exists() else None


def cmd_readings(args: argparse.Namespace) -> int:
    """Ruling 104-1 1f: the selection readings of one front end from every merged validation group (merge completeness checked)."""

    ctx = load_context(Path(args.run_root))
    front = args.front
    validation = sorted(row["episode_id"] for row in ctx.episodes(front, "validation"))
    runs, problems, absent_seeds = [], [], {}
    for arm, seeded in s3.SELECTION_ARMS.items():
        for index, config in enumerate(audit_configs(arm)):
            for seed in (arms.SEEDS if seeded else (None,)):
                path = ctx.merged_path(front, arm, index, seed)
                if not path.exists():
                    training = f"{front}/t1/{heads_arm(arm)}/s{seed}" if seed is not None else None
                    if training is not None and job_status(ctx.run_root, training) in ("diverged", "skipped"):
                        absent_seeds.setdefault(arm, set()).add(seed)
                    else:
                        problems.append(f"merged_group_missing:{group_name(arm, index, seed)}")
                    continue
                merged = load_json(path)
                rows = {row["episode_id"]: row for row in merged["per_episode"]}
                if sorted(rows) != validation or not merged.get("metrics_only") or merged.get("mask_source") != FRONTS[front]:
                    problems.append(f"merged_group_incomplete:{group_name(arm, index, seed)}")
                    continue
                configs = {json.dumps(row["config"], sort_keys=True) for row in rows.values()}
                runs.append({"arm": arm, "config_index": index, "config": json.loads(next(iter(configs))) if len(configs) == 1 else None,
                             "seed": seed, "reports": {episode: row["report"] for episode, row in rows.items()}})
    absent_arms = {arm: "every seed's training diverged (ruling 102-9: a result)" for arm, seeds in absent_seeds.items()
                   if len(seeds) == len(arms.SEEDS)}
    if problems:
        write_json(ctx.front_dir(front) / "selection_readings.json", {"stage": STAGE, "front": front, "problems": problems})
        print(f"[s3-03-readings] {front}: {problems[:5]}", file=sys.stderr)
        return 3
    readings = s3.selection_readings(runs, mask_source=FRONTS[front], absent_arms=absent_arms)
    write_json(ctx.front_dir(front) / "selection_readings.json", {**readings, "front": front, "written_utc": utc_now()})
    print(f"[s3-03-readings] {front}: {len(runs)} runs over {len(validation)} episodes; absent arms {sorted(absent_arms)}")
    return 0


def determinism_group(ctx: RunContext, front: str) -> tuple[str, int, dict[str, Any], int | None] | None:
    """The audit group the determinism probe reruns: VSMT-lean at its development tau_r (first seed with a result), else TAF at its
    development configuration -- every seed of VSMT-lean may have diverged (ruling 102-9: a result), the probe still runs."""

    tau = round1_config("VSMT-lean")
    candidates: list[tuple[str, int, dict[str, Any], int | None]] = [
        ("VSMT-lean", audit_configs("VSMT-lean").index(tau), tau, seed) for seed in arms.SEEDS]
    taf = development_config("TAF")
    candidates.append(("TAF", audit_configs("TAF").index(taf), taf, None))
    return next((c for c in candidates if ctx.merged_path(front, c[0], c[1], c[3]).exists()), None)


def cmd_probe_determinism(args: argparse.Namespace) -> int:
    """Ruling 104-2: one validation audit run again gives the same audit (all but wall time, commit, head path and timings)."""

    import lean_s2_05_node_audit as audit

    ctx = load_context(Path(args.run_root))
    front = args.front
    episode = smallest(ctx.episodes(front, "validation"))
    chosen = determinism_group(ctx, front)
    if chosen is None:
        print(f"[s3-03-probe-determinism] {front}: no audit group to rerun", file=sys.stderr)
        return 1
    arm, index, config, seed = chosen
    original = ctx.group_root(front, arm, index, seed) / episode / arm / audit.AUDIT_FILE_NAME
    rerun_root = ctx.gates_dir(front) / "determinism"
    heads = ctx.heads_file(front, 1, heads_arm(arm), seed) if seed is not None else None
    argv = ctx.audit(front, episode, arm, seed, [(index, config)], heads=heads)
    argv[argv.index("--configs") + 1] = json.dumps([{"config": config, "output_root": str(rerun_root)}])
    completed = subprocess.run(argv)
    if completed.returncode != 0:
        return 1
    rerun = load_json(rerun_root / episode / arm / audit.AUDIT_FILE_NAME)
    first = load_json(original)
    identical = audit.comparable_metrics(first) == audit.comparable_metrics(rerun) and first.get("audit") == rerun.get("audit")
    write_json(ctx.gates_dir(front) / "determinism.json", {"stage": STAGE, "gate": "determinism", "front": front, "episode_id": episode,
                                                           "group": group_name(arm, index, seed), "identical": identical,
                                                           "compared": "everything but wall time, commit, head path and timings",
                                                           "checked_utc": utc_now()})
    print(f"[s3-03-probe-determinism] {front} {episode}: identical={identical}")
    return 0 if identical else 3


def cmd_coverage(args: argparse.Namespace) -> int:
    """Report only (ruling 104-2 readings): ruling 89-3 (1) state coverage in events on the training houses of VSMT-lean's records."""

    import ruling89_probes as r89

    ctx = load_context(Path(args.run_root))
    front = args.front
    training, _selection = training_house_order(ctx, front)

    def rows() -> Iterator[tuple[str, str, dict[str, Any]]]:
        for pass_name, arm in (("round0", "ELU-P"), ("round1", "VSMT-lean")):
            for house in training:
                path = episode_dir(ctx, front, pass_name, house, arm) / "training_records.jsonl.gz"
                for record in read_gz_lines(path):
                    yield pass_name, house, record

    report = r89.coverage_events({"train": rows()})
    write_json(ctx.front_dir(front) / "coverage.json", {"stage": STAGE, "reading": "ruling 89-3 (1) state coverage in events, report only",
                                                        "front": front, "training_houses": len(training), **report, "written_utc": utc_now()})
    print(f"[s3-03-coverage] {front}: {report['train']} pass={report['pass']}")
    return 0


# --------------------------------------------------------------------------
# export and verify
# --------------------------------------------------------------------------

def training_summary(path: Path) -> dict[str, Any]:
    receipt = load_json(path)
    keys = ("arm", "round", "seed", "label_source", "uses", "mask_source", "sources", "split", "best_epoch", "diverged", "updates_taken",
            "optimizer_foreach",
            "train_curve", "validation_curve", "train_curve_terms", "validation_curve_terms", "weights_sha256", "group_selection",
            "existence_class_weight", "threads", "wall_seconds", "peak_rss_bytes", "code_commit")
    return {key: receipt.get(key) for key in keys} | {"receipt_sha256": sha256_file(path)}


def cmd_export(args: argparse.Namespace) -> int:
    ctx = load_context(Path(args.run_root))
    export_dir, tag = Path(args.export_dir), args.tag
    written = []

    def put(name: str, payload: Any) -> None:
        path = export_dir / f"vsmt_lean_s3_03_{name}_{tag}.json"
        write_json(path, payload)
        written.append(path.name)

    put("inputs", ctx.inputs)
    for name in ("workers", "train_timing", "train_threads", "grid_reading", "memory_classes", "pool"):
        if (ctx.run_root / f"{name}.json").exists():
            put(name, load_json(ctx.run_root / f"{name}.json"))
    for front in ctx.fronts:
        fit_dir = ctx.front_dir(front) / "fit"
        for name, path in (("fit", fit_dir / "elu_p_fit.json"), ("fit_values", ctx.fit_values_path(front)),
                           ("calibration", fit_dir / "calibration_report.json"), ("readings", ctx.front_dir(front) / "selection_readings.json"),
                           ("coverage", ctx.front_dir(front) / "coverage.json")):
            if path.exists():
                put(f"{name}_{front}", load_json(path))
        gates = {path.stem: load_json(path) for path in sorted(ctx.gates_dir(front).glob("*.json"))}
        if gates:
            put(f"gates_{front}", gates)
        trainings = sorted((ctx.front_dir(front) / "training").glob("round*/*/s*/training_receipt.json"))
        if trainings:
            put(f"trainings_{front}", {str(path.relative_to(ctx.front_dir(front))): training_summary(path) for path in trainings})
    states = [load_json(path) for path in sorted((ctx.run_root / "jobs").glob("*.json")) if not path.name.endswith(".rss.json")]
    summary: dict[str, Any] = {}
    for state in states:
        kind = state["job_id"].split("/")[1] if "/" in state["job_id"] else state["job_id"]
        row = summary.setdefault(kind, {"jobs": 0, "by_status": {}, "wall_seconds": 0.0, "max_rss_bytes": 0})
        row["jobs"] += 1
        row["by_status"][state["status"]] = row["by_status"].get(state["status"], 0) + 1
        row["wall_seconds"] = round(row["wall_seconds"] + float(state.get("wall_seconds") or 0.0), 1)
        row["max_rss_bytes"] = max(row["max_rss_bytes"], int(state.get("max_rss_bytes") or 0))
    put("jobs", {"by_kind": summary, "not_done": [s["job_id"] for s in states if s["status"] != "done"][:200]})
    print(f"[s3-03-export] {len(written)} files to {export_dir}")
    return 0


def verify(ctx: RunContext, export_dir: Path, tag: str) -> dict[str, Any]:
    problems: list[str] = []
    states = {load_json(path)["job_id"]: load_json(path) for path in sorted((ctx.run_root / "jobs").glob("*.json"))
              if not path.name.endswith(".rss.json")}
    never = []
    for job in build_jobs(ctx):  # the run's whole graph, so a job that never started is named too
        state = states.get(job.job_id)
        if state is None:
            never.append(job.job_id)
        elif state["status"] not in ("done", "diverged", "skipped"):
            problems.append(f"job_not_ended:{job.job_id}:{state['status']}")
        elif state["status"] == "skipped" and "dependency_" not in str(state.get("reason")):
            problems.append(f"job_skipped_without_a_diverged_dependency:{job.job_id}")
    if never:
        problems.append(f"jobs_never_started:{len(never)}:{never[:20]}")
    if ctx.inputs.get("provisional"):  # a run started beside S3-02 is valid only after a full check confirmed its inputs
        problems.append("inputs_still_provisional: run all again after S3-02 has exported its run manifest")
    contract = load_json(S0_05_CONTRACT)
    registered = {}
    for front in ctx.fronts:
        for gate, flag in (("audit_equivalence", "identical"), ("round0", "pass"), ("train_probe", "identical"), ("determinism", "identical")):
            path = ctx.gates_dir(front) / f"{gate}.json"
            if not path.exists() or load_json(path).get(flag) is not True:
                problems.append(f"gate_not_passed:{front}:{gate}")
        if not (ctx.front_dir(front) / "selection_readings.json").exists() or load_json(ctx.front_dir(front) / "selection_readings.json").get("problems"):
            problems.append(f"readings_missing:{front}")
        run_values = ctx.fit_values(front) if ctx.fit_values_path(front).exists() else None
        contract_values = arms.elu_p_fitted(contract, FRONTS[front])
        registered[front] = {"run_local": run_values, "registered": contract_values, "equal": run_values == contract_values}
        if run_values != contract_values:  # ruling 104-1 1b: the registration commit must carry exactly the run's values
            problems.append(f"elu_p_values_not_registered:{front}")
    threads = ctx.train_threads() if (ctx.run_root / "train_threads.json").exists() else None
    for front in ctx.fronts:  # ruling 104-3 / 104-7: one optimizer path and one thread count for every training of the run
        for path in sorted((ctx.front_dir(front) / "training").glob("round*/*/s*/training_receipt.json")):
            receipt = load_json(path)
            if bool(receipt.get("optimizer_foreach")) != OPTIMIZER_FOREACH or (receipt.get("threads") or {}).get("requested") != threads:
                problems.append(f"training_settings_differ:{path.relative_to(ctx.run_root).as_posix()}")
    exports = sorted(p for p in export_dir.glob(f"vsmt_lean_s3_03_*_{tag}.json")
                     if not p.name.startswith(("vsmt_lean_s3_03_manifest_", "vsmt_lean_s3_03_verify_")))
    return {"problems": problems, "registered_values": registered,
            "exports": {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in exports},
            "jobs_by_status": {status: sum(1 for s in states.values() if s["status"] == status) for status in pool.STATUSES}}


def cmd_verify(args: argparse.Namespace) -> int:
    ctx = load_context(Path(args.run_root))
    export_dir = Path(args.export_dir)
    result = verify(ctx, export_dir, args.tag)
    manifest = {"stage": STAGE, "step": "manifest", "tag": args.tag, "written_utc": utc_now(), "code_commit": git("rev-parse", "HEAD"),
                "inputs_commit": ctx.inputs.get("code_commit"), **result,
                "reproduction": ("bash ops/vsmt/s3_03_train_select.sh all at the recorded commits reproduces every export; trainings are "
                                 "bit-identical at the same commit and TRAIN_THREADS, audits are deterministic (the probe); README "
                                 "'How to reproduce S3-03'")}
    write_json(export_dir / f"vsmt_lean_s3_03_manifest_{args.tag}.json", manifest)
    write_json(export_dir / f"vsmt_lean_s3_03_verify_{args.tag}.json",
               {"stage": STAGE, "step": "verify", "problems": result["problems"], "exports_checked": len(result["exports"]),
                "manifest_sha256": sha256_file(export_dir / f"vsmt_lean_s3_03_manifest_{args.tag}.json")})
    print(f"[s3-03-verify] {len(result['exports'])} exports; jobs {result['jobs_by_status']}; problems: {result['problems'][:8] or 'none'}")
    return 0 if not result["problems"] else 3


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    for name in ("run-root", "autodl-root", "s3-02-tag", "export-dir", "instance-reid", "sam2-reid"):
        check.add_argument(f"--{name}", required=True)
    check.add_argument("--repo-root", default=str(ROOT))
    check.add_argument("--fronts", default="instance,sam2")
    check.add_argument("--min-free-gib", type=float, default=100.0)
    check.add_argument("--provisional", action="store_true",
                       help="before S3-02 has exported its run manifest: read train and validation from their roots (confirmed later)")
    check.set_defaults(func=cmd_check)
    run = sub.add_parser("run")
    run.add_argument("--run-root", required=True)
    run.add_argument("--log-dir", required=True)
    run.add_argument("--accept-code-change", action="store_true")
    run.add_argument("--retry-failed", action="store_true", help="rerun failed and gate-failed jobs (their outputs set aside first)")
    run.add_argument("--adopt-calibration", action="append", help="<front>=<calibration pass root> (the S3 pre-fit), reproduced first")
    run.add_argument("--memory-gib", action="append", help="<class>=<GiB>: a default before the first measurement")
    run.add_argument("--memory-fixed-gib", action="append", help="<class>=<GiB>: a fixed reservation (no margin, no fallback); recorded")
    run.add_argument("--budget-cores", type=int, default=None)
    run.add_argument("--memory-bytes", type=int, default=None)
    run.add_argument("--poll-seconds", type=float, default=2.0)
    run.add_argument("--min-free-gib", type=float, default=20.0)
    run.set_defaults(func=cmd_run)
    status = sub.add_parser("status")
    status.add_argument("--run-root", required=True)
    status.set_defaults(func=cmd_status)
    for name, func in (("fit", cmd_fit), ("gate-round0", cmd_gate_round0), ("probe-audit", cmd_probe_audit), ("readings", cmd_readings),
                       ("probe-determinism", cmd_probe_determinism), ("coverage", cmd_coverage), ("adopt-calibration", cmd_adopt_calibration)):
        job = sub.add_parser(name)
        job.add_argument("--run-root", required=True)
        job.add_argument("--front", required=True, choices=list(FRONTS))
        if name == "adopt-calibration":
            job.add_argument("--from", required=True)
        job.set_defaults(func=func)
    threads = sub.add_parser("train-threads")
    threads.add_argument("--run-root", required=True)
    threads.add_argument("--trainings", type=int, required=True)
    threads.set_defaults(func=cmd_train_threads)
    for name, func in (("export", cmd_export), ("verify", cmd_verify)):
        command = sub.add_parser(name)
        command.add_argument("--run-root", required=True)
        command.add_argument("--export-dir", required=True)
        command.add_argument("--tag", required=True)
        command.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (DriverError, pool.PoolError, s3.LeanS3_03Error) as exc:
        print(f"[s3-03] refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
