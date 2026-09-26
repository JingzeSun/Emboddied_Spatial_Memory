"""D-224 / S2-05, ruling 75 (1)(a): the existence-evidence ceiling on an ideal memory (read-only diagnostic).

Usage (server):
    python ops/vsmt/lean_s2_05_evidence_ceiling.py pool --cache-root <S1-03 cache root> --mask-source simulator_instance_masks \\
        --episode-roots <S1-02 root>,<S1-02 root> --geometry-root <S1-04 geometry root> --output-root <root> \\
        --workers 11 --worker-basis "..."
    python ops/vsmt/lean_s2_05_evidence_ceiling.py merge --output-root <root> --results <results/*.json>

What ``run`` does for one episode: it keeps an ideal memory -- one entity per private object, built only from the
fragments whose pixels are strictly more than half that object (the S1-04 ideal-memory rule), remembering the
surface points and the box union of those fragments in the latest frame that saw the object and the mean of their
centroids.  At every frame, before adding that frame's fragments, each remembered object is tested on the frame's
public depth view twice -- on its surface points (ruling 75 (2)(a)) and on its box grid (ruling 74) -- and filed by
the private truth: gone_absent (the object has left the scene), gone_moved (present but more than delta_moved_m
from where it was remembered), present.  Histograms of the visible and free ratios per rule and group leave the run;
no key, box, point or depth does.

白话：这是裁决 75 (1)(a) 的"证据上限"。它不跑任何臂：用私有真值给每个物体建一个完美的实体（只收严格过半属于
它的色块），再问同样的逐点检验能把"真被拿走／被挪走／还在"分得多开。和带门 TAF 的校准趟一对照，就能分清低区
分度是证据本身不行，还是实体框和记忆逻辑不行。它读私有面（在 cache 封印核对之后），只作诊断，不进任何表、不冻结
任何值。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing.pool
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_depth_probe as probe  # noqa: E402  (histogram and AUC helpers)

SCHEMA_VERSION = "vsmt-s2-05-evidence-ceiling-v1"
FILE_NAME = "evidence_ceiling.json"
GROUPS = ("gone_absent", "gone_moved", "present")
RULES = ("surface", "grid")
DOMINANCE = 0.5  # the S1-04 ideal-memory labelling: strictly more than half of the fragment's pixels


class IdealMemory:
    """One entity per private object, from its strictly dominated fragments only."""

    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}

    def observe(self, tick: int, fragments: list[dict[str, Any]], owners: dict[str, str | None],
                surface: dict[str, list[list[float]]]) -> None:
        by_key: dict[str, list[dict[str, Any]]] = {}
        for fragment in fragments:
            key = owners.get(str(fragment["fragment_id"]))
            if key is not None:
                by_key.setdefault(key, []).append(fragment)
        for key, rows in by_key.items():
            points = [p for row in rows for p in surface.get(str(row["fragment_id"]), [])]
            lower = [min(float(r["aabb_min_m"][k]) for r in rows) for k in range(3)]
            upper = [max(float(r["aabb_max_m"][k]) for r in rows) for k in range(3)]
            centroid = [float(np.mean([float(r["centroid_m"][k]) for r in rows])) for k in range(3)]
            self.entities[key] = {"tick": tick, "points": points, "aabb_min_m": lower, "aabb_max_m": upper, "centroid_m": centroid}


def owners_of(instances: dict[str, dict[str, Any]]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for fragment_id, row in instances.items():
        overlap = row["overlap"]
        best = max(overlap.items(), key=lambda kv: (kv[1], kv[0]), default=(None, 0.0))
        out[fragment_id] = best[0] if best[1] > DOMINANCE else None
    return out


def ratios_by_rule(memory: IdealMemory, keys: list[str], view: dict[str, Any], samples: int) -> dict[str, dict[str, dict[str, float]]]:
    from vsmt import lean_runner as lr

    pseudo = {"entities": [{"entity_id": key, "aabb_min_m": memory.entities[key]["aabb_min_m"],
                            "aabb_max_m": memory.entities[key]["aabb_max_m"]} for key in keys]}
    return {"surface": lr.entity_geometry(pseudo, view, samples_per_axis=samples,
                                          surface_points={key: memory.entities[key]["points"] for key in keys}),
            "grid": lr.entity_geometry(pseudo, view, samples_per_axis=samples)}


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def run(args: argparse.Namespace) -> int:
    import lean_s1_04_diagnostics as diag
    import lean_s2_04_evaluate_episode as s2_04
    from vsmt import lean_evaluation as ev
    from vsmt import lean_object_geometry as og
    from vsmt import lean_runner as lr
    from vsmt import lean_teacher as lt

    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[evidence-ceiling] refused: the checkout is not clean", file=sys.stderr)
        return 2
    policy, missing = s2_04.gather_teacher_policy()
    if missing:
        print(f"[evidence-ceiling] refused: policy values still null: {missing}", file=sys.stderr)
        return 2
    delta = float(policy["teacher"]["delta_moved_m"])
    samples = int(policy["runner"]["entity_geometry_samples_per_axis"])
    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    episode_root = Path(args.episode_root).resolve()
    seal, frame_paths = s2_04.verify_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s(), mask_source=args.mask_source)
    table = og.validate_geometry_table(s2_04.load_json(Path(args.geometry_root).resolve() / args.episode_id / og.TABLE_FILE_NAME))
    executed, window = diag.cache_runner_read_interventions(episode_root / "provenance")
    tracker = og.EpisodeTruthTracker(table, executed_interventions=[r for r in executed if r.get("executed", True)], window=window)
    depth_view = s2_04.episode_depth_reader(episode_root, cache_dir)
    out_dir = Path(args.output_root).resolve() / args.episode_id
    if (out_dir / FILE_NAME).exists():
        print(f"[evidence-ceiling] refused: exists: {out_dir / FILE_NAME}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    values: dict[str, dict[str, list[float]]] = {f"{rule}:{group}": {"visible": [], "free": []} for rule in RULES for group in GROUPS}
    rows = {group: 0 for group in GROUPS}
    memory = IdealMemory()
    started = time.time()
    for index, path in enumerate(frame_paths):
        frame = diag.cache_runner.load_cache_frame(path)
        view = depth_view(index, frame)
        record, image = s2_04.load_private_frame(episode_root, index)
        truth = tracker.update(index, record)
        keys = sorted(key for key in memory.entities if key in truth and lt.structural_type_of(key) not in lt.STRUCTURAL_TYPES_EXCLUDED)
        if keys:
            ratios = ratios_by_rule(memory, keys, view, samples)
            for key in keys:
                entry = truth[key]
                if not entry["present"]:
                    group = "gone_absent"
                elif lt._distance(entry["centroid_m"], memory.entities[key]["centroid_m"]) > delta:
                    group = "gone_moved"
                else:
                    group = "present"
                rows[group] += 1
                for rule in RULES:
                    r = ratios[rule][key]
                    values[f"{rule}:{group}"]["visible"].append(r["should_be_visible_ratio"])
                    if r["should_be_visible_ratio"] > 0.0:
                        values[f"{rule}:{group}"]["free"].append(r["free_space_coverage_ratio"])
        masks = diag.cache_runner.read_masks_file(cache_dir / f"{index:04d}{diag.cache_runner.MASK_FILE_SUFFIX}")
        instances = ev.fragment_instances(frame, masks, image, ev.object_of_label(record))
        memory.observe(index + 1, list(frame["fragments"]), owners_of(instances), view["fragment_surface_points"])
    payload = {"schema_version": SCHEMA_VERSION, "stage": "S2-05 evidence ceiling on an ideal memory (read-only, ruling 75 (1)(a))",
               "code_commit": _git("rev-parse", "HEAD"), "episode_id": args.episode_id, "mask_source": args.mask_source,
               "frames": len(frame_paths), "episode_seal_sha256": seal["payload_sha256"], "delta_moved_m": delta,
               "rows": rows, "bins": probe.BINS,
               "histograms": {name: {k: probe._hist(v) for k, v in series.items()} for name, series in values.items()},
               "wall_seconds": round(time.time() - started, 1)}
    (out_dir / FILE_NAME).write_text(json.dumps(payload), encoding="utf-8")
    print(f"[evidence-ceiling] {args.episode_id}: {payload['frames']} frames, rows {rows}, {payload['wall_seconds']} s")
    return 0


def pool(args: argparse.Namespace) -> int:
    roots = [Path(p).resolve() for p in args.episode_roots.split(",") if p]
    cache_root = Path(args.cache_root).resolve()
    tasks = []
    for cache_dir in sorted(p for p in cache_root.iterdir() if (p / "receipt.json").exists()):
        if json.loads((cache_dir / "receipt.json").read_text(encoding="utf-8")).get("status") != "succeeded":
            continue
        found = [root / cache_dir.name for root in roots if (root / cache_dir.name / "receipt.json").exists()]
        if len(found) != 1 or (Path(args.output_root) / cache_dir.name / FILE_NAME).exists():
            continue
        tasks.append([sys.executable, str(HERE), "run", "--cache-root", str(cache_root), "--mask-source", args.mask_source,
                      "--episode-root", str(found[0]), "--geometry-root", args.geometry_root, "--episode-id", cache_dir.name,
                      "--output-root", args.output_root])
    Path(args.output_root).mkdir(parents=True, exist_ok=True)
    actual = max(1, min(args.workers, len(tasks) or 1))
    (Path(args.output_root) / f"plan-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json").write_text(json.dumps(
        {"commit": _git("rev-parse", "HEAD"), "tasks": len(tasks), "requested_workers": args.workers, "actual_workers": actual,
         "worker_basis": args.worker_basis}, indent=1), encoding="utf-8")
    print(f"[evidence-ceiling] {len(tasks)} episodes, {actual} workers", flush=True)

    def one(command: list[str]) -> tuple[str, int, str]:
        completed = subprocess.run(command, capture_output=True, text=True, cwd=str(ROOT))
        return command[command.index("--episode-id") + 1], completed.returncode, (completed.stdout + completed.stderr)[-500:]

    failed = 0
    with multiprocessing.pool.ThreadPool(processes=actual) as workers:
        for name, code, tail in workers.imap_unordered(one, tasks):
            failed += int(code != 0)
            print(f"[evidence-ceiling] {name} exit {code} {tail.strip().splitlines()[-1] if tail.strip() else ''}", flush=True)
    print(f"[evidence-ceiling] done, {failed} failed", flush=True)
    return 0 if not failed else 1


def merge(args: argparse.Namespace) -> int:
    root = Path(args.output_root)
    pooled: dict[str, dict[str, list[int]]] = {}
    rows = {group: 0 for group in GROUPS}
    episodes, commits = [], set()
    for path in sorted(root.glob(f"*/{FILE_NAME}")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise SystemExit(f"not an evidence-ceiling file: {path}")
        commits.add(payload["code_commit"])
        episodes.append({"episode_id": payload["episode_id"], "frames": payload["frames"], "rows": payload["rows"],
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for group in GROUPS:
            rows[group] += payload["rows"][group]
        for name, series in payload["histograms"].items():
            for kind, counts in series.items():
                prior = pooled.setdefault(name, {}).setdefault(kind, [0] * probe.BINS)
                pooled[name][kind] = [a + b for a, b in zip(prior, counts)]
    separation = {}
    for rule in RULES:
        present = pooled.get(f"{rule}:present", {})
        for group in ("gone_absent", "gone_moved"):
            gone = pooled.get(f"{rule}:{group}", {})
            for kind in ("visible", "free"):
                separation[f"{rule}:{group}_vs_present:{kind}"] = {
                    "auc_gone_above_present": probe.auc_from_histograms(gone.get(kind, []), present.get(kind, [])),
                    "gone_rows": int(sum(gone.get(kind, []))), "present_rows": int(sum(present.get(kind, [])))}
    report = {"schema_version": SCHEMA_VERSION, "stage": "S2-05 evidence ceiling merge (read-only, ruling 75 (1)(a))",
              "output_root": str(root), "commits": sorted(commits), "episodes": episodes, "rows": rows, "bins": probe.BINS,
              "separation": separation, "histograms": pooled}
    Path(args.results).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v["auc_gone_above_present"] for k, v in separation.items()}, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    pool_p = sub.add_parser("pool")
    for p in (run_p, pool_p):
        p.add_argument("--cache-root", required=True)
        p.add_argument("--mask-source", required=True)
        p.add_argument("--geometry-root", required=True)
        p.add_argument("--output-root", required=True)
    run_p.add_argument("--episode-root", required=True)
    run_p.add_argument("--episode-id", required=True)
    run_p.add_argument("--allow-dirty", action="store_true")
    run_p.set_defaults(func=run)
    pool_p.add_argument("--episode-roots", required=True)
    pool_p.add_argument("--workers", type=int, default=1)
    pool_p.add_argument("--worker-basis", default="")
    pool_p.set_defaults(func=pool)
    merge_p = sub.add_parser("merge")
    merge_p.add_argument("--output-root", required=True)
    merge_p.add_argument("--results", required=True)
    merge_p.set_defaults(func=merge)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
