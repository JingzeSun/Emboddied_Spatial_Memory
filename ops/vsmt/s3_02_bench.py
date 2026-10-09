#!/usr/bin/env python3
"""S3-02 speed bench support: input check, episode choice, resource sampler and the summaries of the five measurements.

On 2026-10-03 the user asked for a speed bench on one RTX 5090 before the S3-02 setup was fixed
(「1 卡 5090 测速，写测速脚本，测 ①②③④⑤」). ``s3_02_bench.sh`` starts each measurement in order; this script keeps the books
and writes the summaries:
  * check: records the machine (cards, driver, whether torch computes on the card, cgroup quota and memory, data disk) and
    whether each input exists; refuses any input root inside a sealed S3 test root (the ruling 103-1 guard);
  * episodes / config: picks development episodes from their receipts (median size or largest) and gives a development-table
    arm's registered configuration;
  * sampler: every few seconds records GPU memory, GPU utilisation, container memory and cumulative CPU time; the driver
    stops it when a measurement ends;
  * compat (5): the generator's occupancy measurement of 4 houses on this machine: success, per-worker footprint, and the
    workers the S1-01 rule allows at other quotas;
  * scaling (1): SAM2 with 1-4 workers on one card over the same episodes and frames; throughput = frames completed / wall
    clock; failures listed separately; whether the episode seals agree across the trials;
  * caches (2): the two caches one after the other and both at once: total wall clocks, each cache's throughput, resource
    peaks, and whether both ways write the same seals;
  * profile (3): one closed-loop audit under cProfile, time by function and by module;
  * train-bench (4): memory and time to load one record set and to prepare it as tensors, then one timed epoch on the CPU
    and one on the GPU (the frozen recipe via ``ruling89_probes.revision_kwargs``);
  * collect: every export of this bench with its digest.
Reads development data only (no validation/test, no S3 root); every output goes to the bench directory. Not a formal stage;
changes no method, threshold or data.

Usage (from the driver; see ops/vsmt/s3_02_bench.sh):
  python ops/vsmt/s3_02_bench.py check --out X --repo-root R --autodl-root A --episode-roots E --sam2-cache C ...
  python ops/vsmt/s3_02_bench.py scaling --trial 1=<root> --trial 2=<root> ... --out X
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_test_seal  # noqa: E402

STAGE = "vsmt.lean.s3_02.bench.v1"
#: cache failures that are properties of the data (as in s3_02_manifest.CACHE_DATA_FAILURES)
CACHE_DATA_FAILURES = ("proposal_overflow", "duplicate_proposal_mask", "fragment_depth_support_insufficient", "descriptor_not_unit_norm")
#: S1-01 worker rule (lean_s1_assets_capacity_v2.json worker_rule.headroom_fraction)
HEADROOM = 0.2


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str, cwd: Path = ROOT) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(cwd), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def receipts(root: str | Path) -> dict[str, dict[str, Any]]:
    """{episode: receipt} of the episode directories directly under one root."""

    out = {}
    if Path(root).is_dir():
        for path in sorted(Path(root).glob("procthor10k-*/receipt.json")):
            out[path.parent.name] = load_json(path)
    return out


def roots_of(text: str | None) -> list[str]:
    return [item for item in (text or "").split(",") if item]


# --------------------------------------------------------------------------
# the machine
# --------------------------------------------------------------------------

def cgroup_value(name: str) -> str | None:
    try:
        return Path("/sys/fs/cgroup", name).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def cgroup_cpu_usec() -> int | None:
    for line in (cgroup_value("cpu.stat") or "").splitlines():
        if line.startswith("usage_usec "):
            return int(line.split()[1])
    return None


def cgroup_process_bytes() -> int | None:
    stat = cgroup_value("memory.stat")
    if stat is None:
        return None
    values = dict(line.split()[:2] for line in stat.splitlines() if len(line.split()) >= 2)
    return int(values.get("anon", 0)) + int(values.get("shmem", 0))


def gpu_rows() -> list[dict[str, Any]]:
    """One row per card: index, name, memory used and total (MiB), utilisation (%), driver."""

    try:
        text = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,driver_version",
                               "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in text.strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 6 and parts[0].isdigit():
            rows.append({"index": int(parts[0]), "name": parts[1], "memory_used_mib": float(parts[2]),
                         "memory_total_mib": float(parts[3]), "utilization_pct": float(parts[4]), "driver": parts[5]})
    return rows


def torch_probe() -> dict[str, Any]:
    """Can torch compute on this card (a 5090 needs a build with sm_120 kernels)?"""

    try:
        import torch
    except Exception as exc:  # noqa: BLE001 - recorded, not raised
        return {"importable": False, "error": repr(exc)[:300]}
    out: dict[str, Any] = {"importable": True, "version": torch.__version__, "cuda_build": torch.version.cuda,
                           "cuda_available": bool(torch.cuda.is_available())}
    if out["cuda_available"]:
        try:
            out.update({"device": torch.cuda.get_device_name(0), "capability": list(torch.cuda.get_device_capability(0)),
                        "arch_list": torch.cuda.get_arch_list()})
            x = torch.randn(256, 256, device="cuda")
            out["matmul_ok"] = bool(torch.isfinite(x @ x).all().item())
        except Exception as exc:  # noqa: BLE001
            out["error"] = repr(exc)[:300]
            out["matmul_ok"] = False
    return out


def machine() -> dict[str, Any]:
    quota = cgroup_value("cpu.max")
    cores = None
    if quota and quota.split()[0] != "max":
        cores = int(quota.split()[0]) / int(quota.split()[1])
    memory = cgroup_value("memory.max")
    return {"cgroup_cpu_quota": cores, "cgroup_memory_max_bytes": int(memory) if memory and memory != "max" else None,
            "os_cpu_count": os.cpu_count(), "platform": platform.platform(), "python": sys.version.split()[0], "gpus": gpu_rows()}


# --------------------------------------------------------------------------
# check, episodes, config
# --------------------------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    problems: list[str] = []
    repo = Path(args.repo_root)
    roots = {"episode_roots": roots_of(args.episode_roots), "sam2_cache": [args.sam2_cache], "instance_cache": [args.instance_cache],
             "geometry_root": [args.geometry_root]}
    sealed = lean_test_seal.refusal([p for paths in roots.values() for p in paths], reader="s3-02 bench")
    if sealed:  # ruling 103-1: the bench reads the development data only
        problems.append(f"sealed:{sealed}")
    inputs: dict[str, Any] = {}
    episodes = {}
    for root in roots["episode_roots"]:
        rows = receipts(root)
        episodes[root] = {"episodes": len(rows), "succeeded": sum(1 for r in rows.values() if r.get("status") == "succeeded")}
    inputs["episode_roots"] = episodes
    for name in ("sam2_cache", "instance_cache", "geometry_root"):
        path = Path(getattr(args, name))
        rows = receipts(path)
        inputs[name] = {"path": str(path), "exists": path.is_dir(),
                        "succeeded": sum(1 for r in rows.values() if r.get("status") == "succeeded")}
    for name in ("assets_json", "sam2_reid", "instance_reid", "source", "salt_file", "heads"):
        path = Path(getattr(args, name))
        inputs[name] = {"path": str(path), "exists": path.is_file()}
    records = {}
    for spec in args.record_sources:
        root, pass_name, arm = spec.rsplit(":", 2)
        directory = Path(root) / pass_name
        records[spec] = {"exists": directory.is_dir(),
                         "episodes": len(list(directory.glob(f"*/{arm}/training_records.jsonl.gz"))) if directory.is_dir() else 0}
    inputs["record_sources"] = records
    simulator: dict[str, Any] = {"python": args.sim_python}
    try:
        done = subprocess.run([args.sim_python, "-c", "import ai2thor, sys; print(ai2thor.__version__, sys.version.split()[0])"],
                              capture_output=True, text=True, timeout=300)
        simulator.update({"ai2thor_and_python": done.stdout.strip(), "exit": done.returncode})
    except (OSError, subprocess.TimeoutExpired) as exc:
        simulator["error"] = repr(exc)[:200]
    inputs["simulator"] = simulator
    probe = torch_probe()
    if not probe.get("matmul_ok"):
        problems.append("torch cannot compute on the card")
    autodl = Path(args.autodl_root)
    disk = shutil.disk_usage(autodl) if autodl.exists() else None
    if git("status", "--porcelain", cwd=repo):
        problems.append("the worktree is not clean")
    out = {"stage": STAGE, "step": "check", "checked_utc": utc_now(), "code_commit": git("rev-parse", "HEAD", cwd=repo),
           "machine": machine(), "torch": probe, "inputs": inputs,
           "disk": None if disk is None else {"free_gb": round(disk.free / 1e9, 1), "total_gb": round(disk.total / 1e9, 1)},
           "suite": {"exit": args.suite_exit, "summary": args.suite_summary}, "problems": problems,
           "role": "a bench on the development data; nothing here is S3 data or a formal stage"}
    write_json(args.out, out)
    print(f"[bench-check] {probe.get('device')} capability {probe.get('capability')}, torch {probe.get('version')}; "
          f"problems: {problems or 'none'}")
    return 0 if not problems else 3


def episode_sizes(episode_roots: Sequence[str], cache_root: str | None = None) -> list[tuple[str, str, int]]:
    """(episode, root, frames) of every succeeded raw episode (and, with a cache root, succeeded there too), largest first."""

    cached = None
    if cache_root:
        cached = {name for name, r in receipts(cache_root).items() if r.get("status") == "succeeded"}
    rows = []
    for root in episode_roots:
        for name, receipt in receipts(root).items():
            if receipt.get("status") != "succeeded" or (cached is not None and name not in cached):
                continue
            rows.append((name, str(root), int(receipt.get("observations") or 0)))
    return sorted(rows, key=lambda row: (-row[2], row[0]))


def pick_episode(rows: Sequence[tuple[str, str, int]], how: str) -> tuple[str, str, int]:
    if not rows:
        raise SystemExit("no episode to pick")
    return rows[0] if how == "largest" else rows[len(rows) // 2]


def cmd_episodes(args: argparse.Namespace) -> int:
    sealed = lean_test_seal.refusal([*roots_of(args.episode_roots), args.cache_root], reader="s3-02 bench episodes")
    if sealed:
        print(sealed, file=sys.stderr)
        return 2
    name, root, frames = pick_episode(episode_sizes(roots_of(args.episode_roots), args.cache_root), args.pick)
    print(f"{name}\t{root}\t{frames}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    import lean_s2_05_development as development

    config = development.expected_pass_config(args.pass_name, args.arm, mask_source=args.mask_source)
    if config is None:
        print(f"no registered configuration for {args.pass_name} {args.arm}", file=sys.stderr)
        return 2
    print(json.dumps(config))
    return 0


# --------------------------------------------------------------------------
# the resource sampler
# --------------------------------------------------------------------------

def sample() -> dict[str, Any]:
    gpus = gpu_rows()
    return {"t": time.time(), "cpu_usec": cgroup_cpu_usec(), "memory_bytes": cgroup_process_bytes(),
            "gpu_memory_mib": sum(g["memory_used_mib"] for g in gpus) if gpus else None,
            "gpu_utilization_pct": (sum(g["utilization_pct"] for g in gpus) / len(gpus)) if gpus else None}


def cmd_sampler(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as handle:
        while True:
            handle.write(json.dumps(sample()) + "\n")
            handle.flush()
            time.sleep(float(args.interval))


def summarise_samples(path: str | Path) -> dict[str, Any]:
    """Peaks and means of one sampler file: container memory, GPU memory and utilisation, CPU cores in use."""

    rows = []
    if Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:  # a line cut by the kill
                continue
    if not rows:
        return {"samples": 0}
    cpu = [(r["t"], r["cpu_usec"]) for r in rows if r.get("cpu_usec") is not None]
    rates = [(c1 - c0) / 1e6 / (t1 - t0) for (t0, c0), (t1, c1) in zip(cpu, cpu[1:]) if t1 > t0]
    memory = [r["memory_bytes"] for r in rows if r.get("memory_bytes") is not None]
    vram = [r["gpu_memory_mib"] for r in rows if r.get("gpu_memory_mib") is not None]
    util = [r["gpu_utilization_pct"] for r in rows if r.get("gpu_utilization_pct") is not None]

    def mean(values: Sequence[float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    return {"samples": len(rows), "seconds": round(rows[-1]["t"] - rows[0]["t"], 1),
            "cpu_cores_mean": mean(rates), "cpu_cores_peak": round(max(rates), 2) if rates else None,
            "memory_peak_gib": round(max(memory) / 2 ** 30, 2) if memory else None,
            "gpu_memory_peak_mib": max(vram) if vram else None, "gpu_utilization_mean_pct": mean(util)}


# --------------------------------------------------------------------------
# ⑤ compat: the generator on this machine
# --------------------------------------------------------------------------

def workers_at(occupancy: Mapping[str, Any], *, cores: float, memory_gib: float) -> dict[str, Any]:
    """The S1-01 rule's CPU and memory bounds at a given quota (headroom 0.2), next to the verified simulator limit."""

    cpu = occupancy.get("cpu_cores_per_worker") or 0.0
    ram = occupancy.get("ram_gb_per_worker") or 0.0
    by_cpu = int(cores * (1 - HEADROOM) // cpu) if cpu > 0 else None
    by_memory = int(memory_gib * 2 ** 30 / 1e9 * (1 - HEADROOM) // ram) if ram > 0 else None
    bounds = [b for b in (by_cpu, by_memory) if b is not None]
    return {"cores": cores, "memory_gib": memory_gib, "by_cpu": by_cpu, "by_memory": by_memory,
            "bound": min(bounds) if bounds else None}


def cmd_compat(args: argparse.Namespace) -> int:
    measure = Path(args.measure_root)
    out: dict[str, Any] = {"stage": STAGE, "step": "compat", "written_utc": utc_now(), "measure_root": str(measure),
                           "measured": load_json(args.measured) if Path(args.measured).is_file() else None}
    receipt_path = measure / "measure_receipt.json"
    if not receipt_path.is_file():
        out["result"] = "no measurement receipt: the generator did not run to its end on this machine"
        write_json(args.out, out)
        print(f"[bench-compat] {out['result']}")
        return 3
    receipt = load_json(receipt_path)
    occupancy = receipt.get("occupancy") or {}
    out.update({"houses": receipt.get("houses"), "succeeded": receipt.get("succeeded"), "failed": receipt.get("failed"),
                "per_house": receipt.get("per_house"), "machine_peaks": receipt.get("machine"), "occupancy": occupancy,
                "wall_clock_seconds": receipt.get("wall_clock_seconds"),
                "workers_by_quota": [workers_at(occupancy, cores=c, memory_gib=m) for c, m in ((25, 90), (50, 180), (100, 360))],
                "note": ("the simulator limit is not measured here (16 = the confirmation run); these are the CPU and memory "
                         "bounds of the S1-01 rule at one, two and four cards of this host type")})
    out["result"] = "the generator ran on this card" if receipt.get("succeeded") else "no house succeeded"
    write_json(args.out, out)
    print(f"[bench-compat] {out['result']}: {receipt.get('succeeded')}/{len(receipt.get('houses') or [])}; "
          f"per worker {occupancy.get('cpu_cores_per_worker')} cores, {occupancy.get('ram_gb_per_worker')} GB")
    return 0 if receipt.get("succeeded") else 3


# --------------------------------------------------------------------------
# ① SAM2 scaling and ② the two caches
# --------------------------------------------------------------------------

def cache_run(root: str | Path) -> dict[str, Any]:
    """One trial-mode cache run: frames, wall, throughput (frames / wall), failures split by kind, the episode seals."""

    root = Path(root)
    named = receipts(root)
    stage = load_json(root / "trial_receipt.json") if (root / "trial_receipt.json").is_file() else {}
    frames = sum(int(r.get("frames_processed") or r.get("frames") or 0) for r in named.values())
    wall = float(stage.get("wall_clock_seconds") or 0.0)
    failed = [{"episode": n, "reason": r.get("reason"), "frames_processed": int(r.get("frames_processed") or 0)}
              for n, r in sorted(named.items()) if r.get("status") != "succeeded"]
    data = sum(1 for f in failed if f["reason"] in CACHE_DATA_FAILURES)
    return {"root": str(root), "finished": bool(stage), "episodes": sorted(named), "frames": frames, "wall_seconds": wall,
            "frames_per_second": round(frames / wall, 4) if wall > 0 else None, "actual_workers": stage.get("actual_workers"),
            "peak_vram_reserved_mib": stage.get("peak_vram_reserved_mib_max"), "failed": failed, "data_failures": data,
            "other_failures": len(failed) - data,
            "seals": {n: r.get("episode_seal_sha256") for n, r in sorted(named.items()) if r.get("status") == "succeeded"}}


def seals_agree(runs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Whether every episode sealed in two or more runs carries the same seal in each (content equal up to the frames processed)."""

    by_episode: dict[str, dict[str, str]] = {}
    for name, run in runs.items():
        for episode, seal in run["seals"].items():
            by_episode.setdefault(episode, {})[name] = seal
    compared = {e: s for e, s in by_episode.items() if len(s) >= 2}
    differ = sorted(e for e, s in compared.items() if len(set(s.values())) > 1)
    return {"episodes_compared": len(compared), "differ": differ, "all_equal": bool(compared) and not differ}


def scaling_summary(trials: Mapping[int, str | Path]) -> dict[str, Any]:
    runs = {k: cache_run(root) for k, root in sorted(trials.items())}
    same_work = len({tuple(r["episodes"]) for r in runs.values()}) == 1
    usable = {k: r for k, r in runs.items() if r["finished"] and r["frames"] > 0 and r["other_failures"] == 0}
    best = max(sorted(usable), key=lambda k: (usable[k]["frames_per_second"] or 0.0, -k)) if usable else None
    return {"stage": STAGE, "step": "sam2-scaling", "written_utc": utc_now(),
            "metric": "frames completed / wall clock of the whole trial (model loading included); failures listed",
            "trials": {str(k): r for k, r in runs.items()}, "same_work_in_every_trial": same_work,
            "best_workers_per_card": best, "seals": seals_agree({str(k): r for k, r in runs.items()})}


def cmd_scaling(args: argparse.Namespace) -> int:
    trials = {}
    for spec in args.trial:
        k, path = spec.split("=", 1)
        trials[int(k)] = path
    out = scaling_summary(trials)
    write_json(args.out, out)
    rates = {k: v["frames_per_second"] for k, v in out["trials"].items()}
    print(f"[bench-scaling] frames/s by workers {rates}; best {out['best_workers_per_card']}; same work {out['same_work_in_every_trial']}; "
          f"seals equal {out['seals']['all_equal']}")
    return 0 if out["best_workers_per_card"] is not None else 3


def caches_summary(roots: Mapping[str, str | Path], phase_walls: Mapping[str, float], samples: Mapping[str, str | Path]) -> dict[str, Any]:
    """``roots`` keys: seq-instance, seq-sam2, par-instance, par-sam2."""

    runs = {name: cache_run(root) for name, root in roots.items()}
    out: dict[str, Any] = {"stage": STAGE, "step": "caches", "written_utc": utc_now(), "runs": runs,
                           "phase_wall_seconds": dict(phase_walls),
                           "resources": {phase: summarise_samples(path) for phase, path in samples.items()}}
    seq, par = phase_walls.get("sequential"), phase_walls.get("parallel")
    out["parallel_over_sequential"] = round(par / seq, 3) if seq and par else None
    for kind in ("instance", "sam2"):
        alone, together = runs.get(f"seq-{kind}"), runs.get(f"par-{kind}")
        if alone and together and alone["frames_per_second"] and together["frames_per_second"]:
            out[f"{kind}_rate_together_over_alone"] = round(together["frames_per_second"] / alone["frames_per_second"], 3)
        if alone and together:
            out[f"{kind}_seals"] = seals_agree({"sequential": alone, "parallel": together})
    out["reading"] = ("parallel is worth adopting only if parallel_over_sequential is clearly below 1, no run failed for a non-data "
                      "reason and both seal comparisons are all equal")
    return out


def cmd_caches(args: argparse.Namespace) -> int:
    roots = dict(spec.split("=", 1) for spec in args.run)
    walls = {k: float(v) for k, v in (spec.split("=", 1) for spec in args.phase_wall)}
    samples = dict(spec.split("=", 1) for spec in args.samples)
    out = caches_summary(roots, walls, samples)
    write_json(args.out, out)
    print(f"[bench-caches] walls {walls}; parallel/sequential {out['parallel_over_sequential']}; "
          f"seals instance {out.get('instance_seals', {}).get('all_equal')}, sam2 {out.get('sam2_seals', {}).get('all_equal')}")
    return 0


# --------------------------------------------------------------------------
# ③ audit profile
# --------------------------------------------------------------------------

def bucket_of(path: str) -> str:
    """A coarse home for a profiled function: the project module, or the library it lives in."""

    norm = path.replace("\\", "/")
    for marker in ("/src/vsmt/", "/ops/vsmt/", "/src/cpmt/"):
        if marker in norm:
            return norm.split(marker, 1)[1].split("/")[0]
    for library in ("numpy", "torch", "scipy", "json", "gzip", "zlib", "shapely", "PIL"):
        if f"/{library}/" in norm or norm.endswith(f"/{library}.py"):
            return library
    if norm.startswith("~") or norm.startswith("<"):
        return "builtins"
    return "other"


def profile_summary(prof: str | Path, *, top: int = 30) -> dict[str, Any]:
    import pstats

    stats = pstats.Stats(str(prof))
    rows = []
    for (path, line, function), (cc, nc, tt, ct, _callers) in stats.stats.items():
        rows.append({"function": f"{Path(path).name}:{line}:{function}", "bucket": bucket_of(path), "calls": nc,
                     "self_seconds": round(tt, 3), "cumulative_seconds": round(ct, 3)})
    total = sum(r["self_seconds"] for r in rows)
    buckets: dict[str, float] = {}
    for r in rows:
        buckets[r["bucket"]] = buckets.get(r["bucket"], 0.0) + r["self_seconds"]
    return {"total_self_seconds": round(total, 1),
            "by_bucket": {k: {"self_seconds": round(v, 1), "share": round(v / total, 3) if total else None}
                          for k, v in sorted(buckets.items(), key=lambda kv: -kv[1])},
            "top_cumulative": sorted(rows, key=lambda r: -r["cumulative_seconds"])[:top],
            "top_self": sorted(rows, key=lambda r: -r["self_seconds"])[:top]}


def cmd_profile(args: argparse.Namespace) -> int:
    out: dict[str, Any] = {"stage": STAGE, "step": "audit-profile", "written_utc": utc_now(), "episode": args.episode,
                           "frames": args.frames, "profiles": {},
                           "caveat": "cProfile adds overhead to tight Python loops; read shares, not absolute seconds"}
    for spec in args.prof:
        name, prof, measured = spec.split("=", 1)[0], *spec.split("=", 1)[1].split(",")
        entry: dict[str, Any] = {"measured": load_json(measured) if Path(measured).is_file() else None}
        if Path(prof).is_file():
            entry.update(profile_summary(prof, top=args.top))
            wall = (entry["measured"] or {}).get("wall_seconds")
            entry["seconds_per_frame_under_profile"] = round(wall / args.frames, 3) if wall and args.frames else None
        else:
            entry["result"] = "no profile written"
        out["profiles"][name] = entry
    write_json(args.out, out)
    print(f"[bench-profile] {args.episode}: " + "; ".join(f"{n} {e.get('seconds_per_frame_under_profile')} s/frame" for n, e in out["profiles"].items()))
    return 0


# --------------------------------------------------------------------------
# ④ training: memory composition and one epoch on each device
# --------------------------------------------------------------------------

def rss_bytes() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def tensor_bytes(value: Any) -> int:
    """Bytes held by the tensors inside a prepared frame (nested dicts, lists and tuples)."""

    if hasattr(value, "element_size") and hasattr(value, "nelement"):
        return int(value.element_size() * value.nelement())
    if isinstance(value, Mapping):
        return sum(tensor_bytes(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(tensor_bytes(v) for v in value)
    return 0


def cmd_train_bench(args: argparse.Namespace) -> int:
    import gc

    import torch

    import ruling89_probes as probes
    from vsmt import lean_model as model

    entry = probes.r88p._entry()
    training = entry.load_json(entry.S0_05_CONTRACT)["arms"]["VSMT-lean"]["training"]
    assoc_only = args.arm == "AssocOnly"
    out: dict[str, Any] = {"stage": STAGE, "step": "train-device", "written_utc": utc_now(), "sources": args.source, "arm": args.arm,
                           "threads": args.threads, "epochs": args.epochs, "rss_bytes": {"start": rss_bytes()},
                           "caveat": ("timing only: the registered recipe (ruling 99-1) runs on the CPU; a GPU run computes in "
                                      "other kernels, so its weights are not the recipe's; one epoch, not the registered 20")}
    torch.set_num_threads(int(args.threads))
    started = time.time()
    groups, _split, files = probes.load_groups(args.source)
    train_records = [{k: v for k, v in row.items() if k != "tick"} for _, _, row in groups["train"]]
    validation_records = [{k: v for k, v in row.items() if k != "tick"} for _, _, row in groups["selection"]]
    del groups
    gc.collect()
    out.update({"files": len(files), "train_frames": len(train_records), "validation_frames": len(validation_records),
                "load_seconds": round(time.time() - started, 1)})
    out["rss_bytes"]["records_loaded"] = rss_bytes()
    started = time.time()
    prepared = [model.batch_prepared(model.prepare_frame(record)) for record in train_records]
    out["prepare_seconds_cpu"] = round(time.time() - started, 1)
    out["rss_bytes"]["records_and_prepared"] = rss_bytes()
    out["prepared_tensor_bytes"] = sum(tensor_bytes(p) for p in prepared)
    del prepared
    gc.collect()
    out["rss_bytes"]["prepared_freed"] = rss_bytes()
    kwargs = probes.revision_kwargs(argparse.Namespace(revision_91=True))
    runs = {}
    for device in [d for d in args.devices.split(",") if d]:
        if device == "cuda" and not torch.cuda.is_available():
            runs[device] = {"result": "cuda not available"}
            continue
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        started = time.time()
        result = model.train_heads(train_records, validation_records, learning_rate=float(training["learning_rate"]),
                                   weight_decay=float(training["weight_decay"]), epochs=int(args.epochs), seed=7,
                                   assoc_only=assoc_only, device=device, field_encoding=True,
                                   existence_class_weight=not assoc_only, **kwargs)
        runs[device] = {"wall_seconds": round(time.time() - started, 1), "updates_taken": result["updates_taken"],
                        "diverged": result["diverged"], "train_curve": result["train_curve"],
                        "peak_cuda_bytes": int(torch.cuda.max_memory_allocated()) if device == "cuda" else None}
        gc.collect()
    out["runs"] = runs
    try:
        import resource

        out["rss_bytes"]["peak"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except ImportError:
        pass
    write_json(args.out, out)
    print(f"[bench-train] {out['train_frames']} train frames; rss {out['rss_bytes']}; prepared tensors {out['prepared_tensor_bytes']} B; "
          + "; ".join(f"{d} {r.get('wall_seconds')} s" for d, r in runs.items()))
    return 0


# --------------------------------------------------------------------------
# collect
# --------------------------------------------------------------------------

def cmd_collect(args: argparse.Namespace) -> int:
    export_dir = Path(args.export_dir)
    name = f"vsmt_lean_s3_02_bench_manifest_{args.tag}.json"
    files = {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size}
             for p in sorted(export_dir.glob(f"vsmt_lean_s3_02_bench_*_{args.tag}.json")) if p.name != name}
    write_json(export_dir / name, {"stage": STAGE, "step": "collect", "written_utc": utc_now(), "tag": args.tag,
                                   "code_commit": git("rev-parse", "HEAD"), "exports": files})
    print(f"[bench-collect] {len(files)} exports -> {export_dir / name}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check")
    for name in ("out", "repo-root", "autodl-root", "episode-roots", "sam2-cache", "instance-cache", "geometry-root", "assets-json",
                 "sam2-reid", "instance-reid", "source", "salt-file", "sim-python", "heads"):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--record-source", dest="record_sources", action="append", default=[])
    p.add_argument("--suite-exit", type=int, default=None)
    p.add_argument("--suite-summary", default="")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("episodes")
    p.add_argument("--episode-roots", required=True)
    p.add_argument("--cache-root", default=None)
    p.add_argument("--pick", choices=("median", "largest"), default="median")
    p.set_defaults(func=cmd_episodes)
    p = sub.add_parser("config")
    p.add_argument("--pass", dest="pass_name", required=True)
    p.add_argument("--arm", required=True)
    p.add_argument("--mask-source", default="sam2")
    p.set_defaults(func=cmd_config)
    p = sub.add_parser("sampler")
    p.add_argument("--out", required=True)
    p.add_argument("--interval", default="2")
    p.set_defaults(func=cmd_sampler)
    p = sub.add_parser("compat")
    for name in ("measure-root", "measured", "out"):
        p.add_argument(f"--{name}", required=True)
    p.set_defaults(func=cmd_compat)
    p = sub.add_parser("scaling")
    p.add_argument("--trial", action="append", required=True, help="k=<trial root>")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_scaling)
    p = sub.add_parser("caches")
    p.add_argument("--run", action="append", required=True, help="seq-instance|seq-sam2|par-instance|par-sam2=<root>")
    p.add_argument("--phase-wall", action="append", default=[], help="sequential|parallel=<seconds>")
    p.add_argument("--samples", action="append", default=[], help="<phase>=<sampler file>")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_caches)
    p = sub.add_parser("profile")
    p.add_argument("--prof", action="append", required=True, help="<name>=<profile file>,<run-measured json>")
    p.add_argument("--episode", required=True)
    p.add_argument("--frames", type=int, required=True)
    p.add_argument("--top", type=int, default=30)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_profile)
    p = sub.add_parser("train-bench")
    p.add_argument("--source", action="append", required=True)
    p.add_argument("--arm", choices=("VSMT-lean", "AssocOnly"), default="VSMT-lean")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--devices", default="cpu,cuda")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_train_bench)
    p = sub.add_parser("collect")
    p.add_argument("--export-dir", required=True)
    p.add_argument("--tag", required=True)
    p.set_defaults(func=cmd_collect)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
