"""S3-03 job pool (ruling 104-7): one dependency-driven pool instead of stages that wait for each other.

白话：S3-03 的几千个作业（拟合趟、第 0／1 轮轨迹的每条 episode、36 次训练、validation 审计的每条 episode）不再按段等齐：
每个作业写明它依赖谁、要几个核、属于哪类内存，池子每隔一两秒看一次，有空槽就从输入已齐的作业里按优先级派发——关键路径
（拟合、轨迹、训练）先于学习臂审计，学习臂审计先于规则臂审计；同级按预计耗时从长到短；不抢占。排在前面却放不下的作业会先
“占住”它要的核与内存，后面的作业只能用剩下的，所以关键路径不会被一波小作业饿死。每类作业的内存先按缺省值记账，跑完一个就
按实测峰值 ×1.25 上调；每轮派发前还看 cgroup 的实时内存与数据盘剩余，越线就暂停派发。作业结束按退出码定状态：0 完成；
登记的特殊码（训练发散记“发散”、门不过记“门未过”）；其他非零码是工程失败——训练可同输入同种子自动重跑一次（裁决 104-3），
其余失败即停止派发新作业、等在跑的结束。续跑时已完成的作业保留（代码自那以后只改了登记文件或文档才算，否则拒绝，除非显式
接受）；上次中断时还在跑的作业，残留输出先挪到 ``interrupted/`` 留存再重跑。输入是作业清单与机器资源，输出是每个作业的状态
文件、日志与实测内存。例如 120 核的机器上，三个第 0 轮训练一就绪就各占 4 核先走，其余空槽由审计填满。它不决定科学口径，
命令与依赖由 ``s3_03_manifest`` 按裁决 104 生成。
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]

STATUSES = ("pending", "running", "done", "failed", "diverged", "skipped", "gate_failed")
TERMINAL = ("done", "failed", "diverged", "skipped", "gate_failed")
#: A job whose dependency ended in one of these is not run and is recorded as skipped (a result, not a failure).
SKIPPING = ("diverged", "skipped")
#: Exit codes that never trigger the automatic rerun: success and a refusal (the entry refused its inputs).
NO_RETRY_CODES = (0, 2)
#: Ruling 104-3: the reserve kept free for the system.
RESERVE_CORES = 2
RESERVE_GIB = 8.0
#: Every job but a training runs one thread; numerical libraries are pinned so results never depend on the machine.
THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")


class PoolError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PoolError(code)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def state_key(job_id: str) -> str:
    return job_id.replace("/", "__")


def thread_environment(threads: int) -> dict[str, str]:
    return {name: str(int(threads)) for name in THREAD_VARIABLES}


def measured_gib(peak_bytes: int | None, default: float) -> float:
    """1.25 x a measured peak, rounded up to half a GiB (the S2-06 rule), or the default before any measurement."""

    if not peak_bytes:
        return default
    return max(1.0, math.ceil(1.25 * peak_bytes / 2 ** 30 * 2) / 2)


def choose_train_threads(per_epoch_seconds: Mapping[int, float], *, cores: int, trainings: int = 30) -> dict[str, Any]:
    """Ruling 104-3: the thread count under which the round-1 trainings are expected to finish first.

    白话：输入在约 20 个训练 house 上实测的每 epoch 秒数（1～4 线程各一个）和可用核数，输出整趟固定的 TRAIN_THREADS。
    t 线程时最多同时跑 min(30, 可用核数 // t) 个训练，30 个要排 ceil(30 / 并行数) 波，每波耗时正比于 t 线程的每 epoch 秒数；
    取预计总时长最短的 t，并列取线程少的。例如 100 核：1 线程每 epoch 10 s、4 线程 4 s，30 个都能同时跑，选 4 线程。
    它只是预计，不保证真实完成时间；内存由派发时的记账另管。
    """

    _require(bool(per_epoch_seconds), "train_threads_need_measurements")
    _require(int(cores) >= 1 and int(trainings) >= 1, "train_threads_need_cores_and_trainings")
    rows = []
    for threads, seconds in sorted((int(t), float(s)) for t, s in per_epoch_seconds.items()):
        _require(threads >= 1 and seconds > 0 and math.isfinite(seconds), f"train_threads_measurement_invalid:{threads}")
        parallel = max(1, min(int(trainings), int(cores) // threads))
        waves = math.ceil(int(trainings) / parallel)
        rows.append({"threads": threads, "seconds_per_epoch": seconds, "parallel": parallel, "waves": waves,
                     "relative_completion": waves * seconds})
    best = min(rows, key=lambda row: (row["relative_completion"], row["threads"]))
    return {"train_threads": best["threads"], "candidates": rows, "cores": int(cores), "trainings": int(trainings),
            "rule": ("ruling 104-3: the thread count minimising ceil(trainings / min(trainings, cores // t)) x seconds per epoch at t "
                     "threads, measured on about 20 training houses during round 0; ties to fewer threads; fixed for the run")}


def cgroup_working_set() -> int | None:
    """The container's working set now (cgroup v2: memory.current minus inactive_file), or None where it cannot be read.

    memory.current also counts the page cache of every file read, which the kernel reclaims under pressure; reading a few
    hundred GB of caches would make it look full.  The working set leaves out the inactive file pages (the Kubernetes rule).
    """

    try:
        current = int(Path("/sys/fs/cgroup/memory.current").read_text(encoding="utf-8").strip())
        stat = dict(line.split() for line in Path("/sys/fs/cgroup/memory.stat").read_text(encoding="utf-8").splitlines() if line.strip())
        return max(0, current - int(stat.get("inactive_file", 0)))
    except (OSError, ValueError):
        return None


@dataclasses.dataclass
class Job:
    """One unit of work: what it waits for, what it costs, and how to build its command when it is dispatched."""

    job_id: str
    kind: str
    deps: tuple[str, ...]
    priority: int
    cost: float
    cores: int | None              # None: the run's TRAIN_THREADS, read when the job is dispatched
    memory: str                    # a memory class: jobs of one class share one measured estimate
    build: Callable[[], list[str]]
    outputs: tuple[str, ...] = ()  # moved aside (never deleted) before a rerun after a failure or an interruption
    retries: int = 0
    exit_status: Mapping[int, str] = dataclasses.field(default_factory=dict)
    keep_partial: bool = False     # the job resumes over its own finished outputs (audits with --skip-existing)
    soft_deps: tuple[str, ...] = ()  # must have ended, in any of done / diverged / skipped (the readings over every merge)


class Pool:
    """The dispatcher.  ``launch`` starts one command and returns an object with ``poll()``; tests pass their own."""

    def __init__(self, jobs: Sequence[Job], *, run_root: Path, log_dir: Path, budget_cores: int, budget_gib: float,
                 memory_defaults: Mapping[str, float], train_threads: Callable[[], int], commit: str,
                 code_change: Callable[[str], list[str]] | None = None, accept_code_change: bool = False,
                 poll_seconds: float = 2.0, disk_root: Path | None = None, min_free_gib: float = 20.0,
                 memory_now: Callable[[], int | None] = cgroup_working_set, memory_limit_bytes: int | None = None,
                 launch: Callable[..., Any] | None = None, wrapper: Sequence[str] | None = None,
                 sleep: Callable[[float], None] = time.sleep, retry_failed: bool = False) -> None:
        self.jobs = {job.job_id: job for job in jobs}
        _require(len(self.jobs) == len(jobs), "job_ids_repeat")
        for job in jobs:
            for dep in (*job.deps, *job.soft_deps):
                _require(dep in self.jobs, f"job_dependency_unknown:{job.job_id}:{dep}")
        self.run_root, self.log_dir = Path(run_root), Path(log_dir)
        self.budget_cores, self.budget_gib = max(1, int(budget_cores)), float(budget_gib)
        self.memory_defaults = dict(memory_defaults)
        self.train_threads = train_threads
        self.commit = commit
        self.code_change = code_change
        self.accept_code_change = accept_code_change
        self.poll_seconds = poll_seconds
        self.disk_root = disk_root
        self.min_free_gib = min_free_gib
        self.memory_now = memory_now
        self.memory_limit_bytes = memory_limit_bytes
        self.launch = launch or self._launch
        self.wrapper = list(wrapper or [])
        self.sleep = sleep
        self.retry_failed = retry_failed
        self.state_dir = self.run_root / "jobs"
        self.states: dict[str, dict[str, Any]] = {}
        self.running: dict[str, tuple[Any, Any, int, float]] = {}
        self.stop_reason: str | None = None
        self.measured: dict[str, int] = {}
        self.memory_paused = False

    # -- state ---------------------------------------------------------------

    def _state_path(self, job_id: str) -> Path:
        return self.state_dir / f"{state_key(job_id)}.json"

    def _save(self, job_id: str) -> None:
        write_json(self._state_path(job_id), self.states[job_id])

    def status(self, job_id: str) -> str:
        return self.states[job_id]["status"]

    def load(self) -> None:
        for job_id in self.jobs:
            path = self._state_path(job_id)
            self.states[job_id] = load_json(path) if path.exists() else {"job_id": job_id, "status": "pending", "attempts": 0, "history": []}
        memory = self.run_root / "memory_classes.json"
        if memory.exists():
            self.measured = {name: int(value) for name, value in load_json(memory).get("peak_bytes", {}).items()}

    def prepare(self) -> list[str]:
        """Resume: keep finished jobs whose code is unchanged (or changed only where allowed); set interrupted ones aside."""

        self.load()
        problems: list[str] = []
        changes: dict[str, list[str]] = {}
        for job_id, job in self.jobs.items():
            state = self.states[job_id]
            if state["status"] == "running":  # the pool stopped while it ran: keep its partial outputs, run it again
                if not job.keep_partial:
                    self._set_aside(job, "interrupted", state.get("attempts", 0))
                state["history"].append({"status": "interrupted", "commit": state.get("commit"), "at_utc": utc_now()})
                state["status"] = "pending"
                self._save(job_id)
            elif state["status"] in ("failed", "gate_failed") and self.retry_failed:  # asked for explicitly, never by default
                if not job.keep_partial:
                    self._set_aside(job, "failed", state.get("attempts", 0))
                state["history"].append({"status": f"{state['status']}_then_retried_on_request", "exit": state.get("exit"),
                                         "reason": state.get("reason"), "commit": state.get("commit"), "at_utc": utc_now()})
                state["status"] = "pending"
                self._save(job_id)
            elif state["status"] == "done" and state.get("commit") != self.commit and self.code_change is not None:
                commit = str(state.get("commit"))
                if commit not in changes:
                    changes[commit] = self.code_change(commit)
                if changes[commit] and not self.accept_code_change:
                    problems.append(f"code_changed_since:{commit[:12]}:{','.join(changes[commit][:6])}")
        return sorted(set(problems))

    def _set_aside(self, job: Job, why: str, attempt: int) -> None:
        for output in job.outputs:
            path = Path(output)
            if path.exists():
                target = self.run_root / why / f"{state_key(job.job_id)}-attempt{attempt}" / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target))

    # -- resources -------------------------------------------------------------

    def cores_of(self, job: Job) -> int:
        cores = job.cores if job.cores is not None else int(self.train_threads())
        return max(1, min(int(cores), self.budget_cores))

    def gib_for(self, memory_class: str) -> float:
        default = float(self.memory_defaults.get(memory_class, self.memory_defaults.get("default", 4.0)))
        return min(measured_gib(self.measured.get(memory_class), default), self.budget_gib)

    def gib_of(self, job: Job) -> float:
        return self.gib_for(job.memory)

    def _launch(self, argv: list[str], *, log: Path, env: Mapping[str, str]) -> tuple[Any, Any]:
        handle = open(log, "ab")
        process = subprocess.Popen(argv, stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT), env=dict(env))
        return process, handle

    # -- the loop --------------------------------------------------------------

    def ready(self) -> list[Job]:
        out = [job for job_id, job in self.jobs.items()
               if self.status(job_id) == "pending" and all(self.status(dep) == "done" for dep in job.deps)
               and all(self.status(dep) in ("done", *SKIPPING) for dep in job.soft_deps)]
        return sorted(out, key=lambda job: (job.priority, -job.cost, job.job_id))

    def propagate_skips(self) -> None:
        changed = True
        while changed:
            changed = False
            for job_id, job in self.jobs.items():
                if self.status(job_id) != "pending":
                    continue
                blocked = [dep for dep in job.deps if self.status(dep) in SKIPPING]
                if blocked:
                    self.states[job_id].update({"status": "skipped", "reason": f"dependency_{self.status(blocked[0])}:{blocked[0]}",
                                                "finished_utc": utc_now()})
                    self._save(job_id)
                    changed = True

    def dispatch(self) -> list[str]:
        if self.disk_root is not None:
            free = shutil.disk_usage(self.disk_root).free / 2 ** 30
            if free < self.min_free_gib:
                self.stop_reason = f"disk_below_{self.min_free_gib}_gib:{round(free, 1)}"
                return []
        current = self.memory_now() if self.memory_limit_bytes else None
        self.memory_paused = bool(current is not None and current > self.memory_limit_bytes)
        if self.memory_paused:
            return []
        used_cores = sum(entry[2] for entry in self.running.values())
        used_gib = sum(entry[3] for entry in self.running.values())
        free_cores, free_gib = self.budget_cores - used_cores, self.budget_gib - used_gib
        started: list[str] = []
        for job in self.ready():
            cores, gib = self.cores_of(job), self.gib_of(job)
            if cores <= free_cores and gib <= free_gib:
                self.start(job, cores=cores, gib=gib)
                if self.stop_reason:
                    break
                free_cores -= cores
                free_gib -= gib
                started.append(job.job_id)
            else:  # head-of-line reservation: what a higher job needs is not lent to a lower one
                free_cores -= cores
                free_gib -= gib
            if free_cores <= 0 or free_gib <= 0:
                break
        return started

    def start(self, job: Job, *, cores: int, gib: float) -> None:
        state = self.states[job.job_id]
        try:
            argv = [str(item) for item in job.build()]
        except Exception as exc:  # a command that cannot be built is an engineering failure, never retried silently
            state.update({"status": "failed", "reason": f"build_failed:{type(exc).__name__}:{exc}", "finished_utc": utc_now()})
            self._save(job.job_id)
            self.stop_reason = f"failed:{job.job_id}"
            return
        self.log_dir.mkdir(parents=True, exist_ok=True)
        key = state_key(job.job_id)
        log = self.log_dir / f"{key}.log"
        rss = self.state_dir / f"{key}.rss.json"
        command = [*self.wrapper, "--out", str(rss), "--", *argv] if self.wrapper else argv
        env = {**os.environ, **thread_environment(cores)}
        state.update({"status": "running", "attempts": int(state.get("attempts", 0)) + 1, "commit": self.commit, "command": argv,
                      "cores": cores, "gib": gib, "log": str(log), "started_utc": utc_now(), "started_at": time.time()})
        self._save(job.job_id)
        process, handle = self.launch(command, log=log, env=env)
        self.running[job.job_id] = (process, handle, cores, gib)

    def reap(self) -> list[str]:
        finished: list[str] = []
        for job_id, (process, handle, _cores, _gib) in list(self.running.items()):
            code = process.poll()
            if code is None:
                continue
            if handle is not None:
                handle.close()
            del self.running[job_id]
            finished.append(job_id)
            job, state = self.jobs[job_id], self.states[job_id]
            peak = None
            rss = self.state_dir / f"{state_key(job_id)}.rss.json"
            if rss.exists():
                peak = load_json(rss).get("max_rss_children_bytes")
            if peak:
                self.measured[job.memory] = max(int(peak), self.measured.get(job.memory, 0))
                write_json(self.run_root / "memory_classes.json", {"peak_bytes": self.measured, "updated_utc": utc_now()})
            state.update({"exit": code, "max_rss_bytes": peak, "finished_utc": utc_now(),
                          "wall_seconds": round(time.time() - float(state.get("started_at") or time.time()), 1)})
            status = "done" if code == 0 else job.exit_status.get(code)
            if status is None and code not in NO_RETRY_CODES and state["attempts"] <= job.retries:
                state["history"].append({"status": "failed_then_rerun", "exit": code, "attempt": state["attempts"], "at_utc": utc_now()})
                self._set_aside(job, "failed", state["attempts"])
                state["status"] = "pending"  # ruling 104-3: a crash or an out-of-memory kill reruns once, same inputs, same seed
            elif status is None:
                state["status"] = "failed"
                self.stop_reason = self.stop_reason or f"failed:{job_id}"
            else:
                state["status"] = status
                if status == "gate_failed":
                    self.stop_reason = self.stop_reason or f"gate_failed:{job_id}"
            self._save(job_id)
        return finished

    def snapshot(self) -> dict[str, Any]:
        counts: dict[str, dict[str, int]] = {}
        for job_id, job in self.jobs.items():
            row = counts.setdefault(job.kind, {})
            row[self.status(job_id)] = row.get(self.status(job_id), 0) + 1
        payload = {"updated_utc": utc_now(), "commit": self.commit, "stop_reason": self.stop_reason, "memory_paused": self.memory_paused,
                   "budget": {"cores": self.budget_cores, "gib": self.budget_gib},
                   "running": sorted(self.running), "counts_by_kind": counts,
                   "memory_estimates_gib": {name: self.gib_for(name) for name in sorted(set(self.memory_defaults) | set(self.measured))}}
        write_json(self.run_root / "pool.json", payload)
        return payload

    def run(self, *, max_rounds: int | None = None) -> int:
        problems = self.prepare()
        if problems:
            self.stop_reason = "blocked:" + ";".join(problems)
            self.snapshot()
            return 2
        rounds = 0
        last_snapshot = 0.0
        while True:
            self.reap()
            self.propagate_skips()
            if self.stop_reason is None:
                self.dispatch()
            pending = [job_id for job_id in self.jobs if self.status(job_id) in ("pending", "running")]
            if not self.running and (self.stop_reason is not None or not pending):
                break
            if not self.running and not self.ready() and not self.memory_paused:
                self.stop_reason = "stuck:" + ",".join(sorted(pending)[:5])
                break
            if time.time() - last_snapshot > 10:
                self.snapshot()
                last_snapshot = time.time()
            rounds += 1
            if max_rounds is not None and rounds >= max_rounds:
                break
            self.sleep(self.poll_seconds)
        self.snapshot()
        if self.stop_reason is None:
            return 0
        return 3 if self.stop_reason.startswith("gate_failed") else 1


__all__ = [
    "Job",
    "Pool",
    "PoolError",
    "RESERVE_CORES",
    "RESERVE_GIB",
    "STATUSES",
    "TERMINAL",
    "choose_train_threads",
    "measured_gib",
    "thread_environment",
]
