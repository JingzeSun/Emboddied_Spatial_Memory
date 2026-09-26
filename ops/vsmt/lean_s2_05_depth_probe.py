"""D-224 / S2-05, ruling 73 (2): read-only probe of a per-point depth test for the existence evidence.

Usage (server; same inputs as the S2-04 entry):
    python ops/vsmt/lean_s2_05_depth_probe.py pool --cache-root <S1-03 cache root> --mask-source simulator_instance_masks \\
        --episode-roots <S1-02 root>,<S1-02 root> --geometry-root <S1-04 geometry root> \\
        --descriptor reid_projection:vitb14 --weights <reid weights> --output-root <probe root> \\
        --episodes <id>,<id>,... --arms TAF,LOW --workers 14 --worker-basis "..."
    python ops/vsmt/lean_s2_05_depth_probe.py merge --output-root <probe root> --results results/<name>.json

What ``run`` does for one episode and one arm (at its registered development configuration): it replays
exactly what the S2-04 entry replays -- the S2-01 runner over the sealed cache, the S2-04 teacher behind the
two-seal gate -- and at every frame takes the memory the runner decided on (``memory_before``, M_{t-1}) and
every active or dormant entity in it.  For each entity it computes, on the same 64 box sample points the
runner uses (``lean_runner.sample_points``):

* the current rule: ``should_be_visible_ratio`` and ``free_space_coverage_ratio`` from the frozen D-223
  block frusta (``lean_runner.entity_geometry``);
* the probed rule: each point is projected into this frame's public depth image (public intrinsics, the
  causal public pose read under the S1-03 pose policy); with the axial depth z of the point and the depth d
  measured at its pixel, a point is *seen through* when d > z + margin, *on the surface* when |d - z| <= margin,
  *occluded* when d < z - margin, and unobserved when it falls outside the image or the depth is invalid.
  probed visible ratio = (seen through + on surface) / 64; probed free ratio = seen through / (seen through +
  on surface), undefined when no point is observed.  Margins 0.05, 0.10 and 0.20 m are all reported; none is
  frozen here.

and it labels the entity with the teacher's existence rule (gone / present / identity_ambiguous; structural
keys are present by rule and kept apart), for every active or dormant entity rather than only the runner's
candidates, so the probed rule is not judged only on rows the current rule admitted.  Only histograms and
counts leave the run: no private key, no box, no depth.

白话：这是裁决 73 (2) 的探针，回答"逐点深度检验能不能比现在的块视锥更好地分开'已拿走'和'还在'"。输入与
S2-04 入口相同，加上每帧公开深度图；输出是每个臂、每种余量下两类实体的旧/新比例直方图与区分度（AUC）。
例如杯子被拿走后相机再看桌面，杯子原位置的采样点投到深度图上，测到的是后面的桌面或墙（更远），这些点
算"看穿"；杯子还在时测到的是杯子表面（差不多远），算"在表面"。它不改任何合同、不进任何表、不冻结余量，
结论只用于裁决 73 的后续提案。
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
from typing import Any, Mapping, Sequence

import numpy as np

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

SCHEMA_VERSION = "vsmt-s2-05-depth-probe-v1"
PROBE_FILE_NAME = "depth_probe.json"
MARGINS_M = (0.05, 0.10, 0.20)
BINS = 50
#: rows are grouped by the teacher's existence status; structural present rows are kept apart
GROUPS = ("gone", "present", "present_structural", "identity_ambiguous")
#: the development configuration each probed arm runs at (S2-05 development slots, ruling 68)
PROBE_ARMS = ("TAF", "LOW")


class DepthProbeError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DepthProbeError(code)


# --------------------------------------------------------------------------
# the probed rule
# --------------------------------------------------------------------------

def point_depth_counts(points_world: np.ndarray, depth: np.ndarray, calibration: Mapping[str, Any],
                       pose: Mapping[str, Any], *, margin_m: float, minimum_depth_m: float = 0.05,
                       maximum_depth_m: float = 20.0) -> dict[str, np.ndarray]:
    """Per-entity counts of seen-through / on-surface / occluded / unobserved points.

    ``points_world`` is (E, P, 3).  The camera convention is the frozen back-projection's
    (``l1_entities.backproject_public_entity_geometry``): world = R @ camera + position, camera +x right,
    +y up, +z forward, u = cx + fx x / z, v = cy - fy y / z, pixel = (round(v), round(u)).
    """

    from vsmt.l1_entities import _camera_values

    fx, fy, cx, cy, position, rotation = _camera_values(calibration, pose)
    points = np.asarray(points_world, dtype=np.float64)
    _require(points.ndim == 3 and points.shape[-1] == 3, "points_shape")
    camera = (points - position) @ rotation          # row vectors: (R^T (p - t))^T = (p - t)^T R
    x, y, z = camera[..., 0], camera[..., 1], camera[..., 2]
    height, width = depth.shape
    with np.errstate(divide="ignore", invalid="ignore"):
        u = np.where(z > 0, cx + fx * x / z, -1.0)
        v = np.where(z > 0, cy - fy * y / z, -1.0)
    column = np.rint(u).astype(np.int64)
    row = np.rint(v).astype(np.int64)
    in_image = (z > minimum_depth_m) & (column >= 0) & (column < width) & (row >= 0) & (row < height)
    measured = np.full(z.shape, np.nan)
    measured[in_image] = depth[row[in_image], column[in_image]]
    valid = in_image & np.isfinite(measured) & (measured >= minimum_depth_m) & (measured <= maximum_depth_m)
    through = valid & (measured > z + margin_m)
    surface = valid & (np.abs(measured - z) <= margin_m)
    occluded = valid & (measured < z - margin_m)
    return {"through": through.sum(axis=1), "surface": surface.sum(axis=1), "occluded": occluded.sum(axis=1),
            "unobserved": (~valid).sum(axis=1), "points": np.full(points.shape[0], points.shape[1])}


def _hist(values: Sequence[float]) -> list[int]:
    counts, _ = np.histogram(np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0), bins=BINS, range=(0.0, 1.0))
    return [int(c) for c in counts]


def auc_from_histograms(high: Sequence[int], low: Sequence[int]) -> float | None:
    """P(X_high > X_low) + 0.5 P(same bin) from two histograms on the same bins."""

    a, b = np.asarray(high, dtype=np.float64), np.asarray(low, dtype=np.float64)
    if a.sum() == 0 or b.sum() == 0:
        return None
    below = np.concatenate([[0.0], np.cumsum(b)[:-1]])
    return float((a * (below + 0.5 * b)).sum() / (a.sum() * b.sum()))


class Accumulator:
    """Histograms per group of the current and the probed ratios; rows only, never keys or boxes."""

    def __init__(self) -> None:
        self.values: dict[str, dict[str, list[float]]] = {group: {} for group in GROUPS}
        self.rows = {group: 0 for group in GROUPS}

    def add(self, group: str, name: str, value: float | None) -> None:
        if value is not None:
            self.values[group].setdefault(name, []).append(float(value))

    def report(self) -> dict[str, Any]:
        return {"rows": dict(self.rows), "bins": BINS,
                "histograms": {group: {name: _hist(values) for name, values in sorted(series.items())}
                               for group, series in self.values.items()},
                "counts": {group: {name: len(values) for name, values in sorted(series.items())}
                           for group, series in self.values.items()}}


def group_of(label: Mapping[str, Any]) -> str:
    if label["status"] == "present" and label.get("reason") in ("structural_never_intervened", "spawned_after_reload"):
        return "present_structural"
    return str(label["status"])


def observe_frame(accumulator: Accumulator, *, memory_before: Mapping[str, Any], labels: Mapping[str, Mapping[str, Any]],
                  current: Mapping[str, Mapping[str, float]], depth: np.ndarray, calibration: Mapping[str, Any],
                  pose: Mapping[str, Any], samples_per_axis: int) -> None:
    """One frame: both rules for every labelled active or dormant entity of M_{t-1}."""

    from vsmt import lean_runner as lr

    entities = [e for e in memory_before["entities"] if str(e["entity_id"]) in labels]
    if not entities:
        return
    points = np.stack([lr.sample_points(e["aabb_min_m"], e["aabb_max_m"], samples_per_axis=samples_per_axis) for e in entities])
    by_margin = {margin: point_depth_counts(points, depth, calibration, pose, margin_m=margin) for margin in MARGINS_M}
    for index, entity in enumerate(entities):
        entity_id = str(entity["entity_id"])
        group = group_of(labels[entity_id])
        accumulator.rows[group] += 1
        old = current[entity_id]
        accumulator.add(group, "current_visible", old["should_be_visible_ratio"])
        if old["should_be_visible_ratio"] > 0.0:
            accumulator.add(group, "current_free_given_visible", old["free_space_coverage_ratio"])
        for margin, counts in by_margin.items():
            observed = int(counts["through"][index] + counts["surface"][index])
            total = int(counts["points"][index])
            accumulator.add(group, f"probed_visible_m{margin:.2f}", observed / total)
            if observed:
                accumulator.add(group, f"probed_free_given_observed_m{margin:.2f}", int(counts["through"][index]) / observed)
            if observed >= 8:  # at least an eighth of the box observed this frame
                accumulator.add(group, f"probed_free_given_observed8_m{margin:.2f}", int(counts["through"][index]) / observed)


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def run(args: argparse.Namespace) -> int:
    import lean_s1_03_cache as cache_runner
    import lean_s1_04_diagnostics as diag
    import lean_s2_01_runner as s2_01
    import lean_s2_04_evaluate_episode as s2_04
    from vsmt import lean_assignment as la
    from vsmt import lean_development as dev
    from vsmt import lean_evaluation as ev
    from vsmt import lean_object_geometry as og
    from vsmt import lean_runner as lr

    contract = ev.validate_evaluation_contract(s2_04.load_json(s2_04.S2_04_CONTRACT))
    runner_contract = lr.validate_runner_contract(s2_04.load_json(s2_01.S2_01_CONTRACT))
    closed = [f"S2-04 {n}" for n in s2_04.REQUIRED_S2_04 if contract["authorization"].get(n) is not True]
    closed += [f"S2-01 {n}" for n in s2_04.REQUIRED_S2_01 if runner_contract["authorization"].get(n) is not True]
    if closed:
        print(f"[depth-probe] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    policy, missing = s2_04.gather_teacher_policy()
    if missing:
        print(f"[depth-probe] refused: policy values still null: {missing}", file=sys.stderr)
        return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[depth-probe] refused: the checkout is not clean", file=sys.stderr)
        return 2
    _require(args.arm in PROBE_ARMS, f"arm_not_probed:{args.arm}")
    development = dev.validate_development_contract(s2_04.load_json(ROOT / "configs" / "vsmt" / "lean_s2_05_development_v1.json"))
    config = dev.development_configuration(development, args.arm)
    projector = None
    if args.descriptor == la.SELECTED_DESCRIPTOR:
        payload = s2_04.load_json(Path(args.weights))
        projector = lr.descriptor_projector(payload, expected_sha256=la.SELECTED_REID_WEIGHTS_SHA256, device="cpu")

    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    episode_root = Path(args.episode_root).resolve()
    seal, frame_paths = s2_04.verify_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s(), mask_source=args.mask_source)
    if args.frames is not None:  # smoke only
        frame_paths = frame_paths[: int(args.frames)]
    table = og.validate_geometry_table(s2_04.load_json(Path(args.geometry_root).resolve() / args.episode_id / og.TABLE_FILE_NAME))
    executed, window = diag.cache_runner_read_interventions(episode_root / "provenance")
    episode_receipt = s2_04.load_json(episode_root / "receipt.json")
    split_seed = int(s2_04.load_json(s2_04.CONFIG_DIR / "lean_s1_02a_pilot_v2.json")["split_freeze"]["seed"])
    nuisance_meta = {"path": str(cache_dir), "seed": split_seed, "house_index": episode_receipt.get("source_index")}
    pose_policy = s2_04.load_json(cache_runner.CONTRACT_PATH)["public_pose_correction"]
    episode_commit = str(episode_receipt["code_commit"])

    out_dir = Path(args.output_root).resolve() / args.episode_id / args.arm
    if (out_dir / PROBE_FILE_NAME).exists():
        print(f"[depth-probe] refused: probe exists: {out_dir / PROBE_FILE_NAME}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    teacher = ev.EpisodeTeacher(arm=args.arm, geometry_table=table, executed_interventions=executed, window=window,
                                policy=policy["teacher"], nuisance_meta=nuisance_meta)
    captured: dict[str, Any] = {}
    original = teacher._existence_labels

    def capture(memory_before, candidates, object_state):  # the object state of this frame, for the wider label set
        captured["object_state"] = object_state
        return original(memory_before, candidates, object_state)

    teacher._existence_labels = capture
    accumulator = Accumulator()
    samples = int(policy["runner"]["entity_geometry_samples_per_axis"])
    public_dir = episode_root / "public"
    started = time.time()
    current: dict[str, Any] = {}

    depth_view = s2_04.episode_depth_reader(episode_root)

    def frames():
        for index, path in enumerate(frame_paths):
            frame = diag.cache_runner.load_cache_frame(path)
            frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(index)  # ruling 74: the runner reads it
            current["frame"] = frame
            yield frame

    count = 0
    for index, step in enumerate(lr.run_episode(frames(), episode_id=args.episode_id, arm=args.arm, config=config,
                                                policy=policy["runner"], descriptor=args.descriptor, projector=projector)):
        cache_frame = current["frame"]
        masks = diag.cache_runner.read_masks_file(cache_dir / f"{index:04d}{diag.cache_runner.MASK_FILE_SUFFIX}")
        record, image = s2_04.load_private_frame(episode_root, index)
        teacher.label_frame(step, cache_frame=cache_frame, private_record=record, masks=masks,
                            label_image=image, runtime_s=0.0, peak_memory_bytes=0)
        memory_before = step["memory_before"]
        wide = [str(e["entity_id"]) for e in memory_before["entities"] if e["state"] in ("active", "dormant")]
        labels = original(memory_before, wide, captured["object_state"])
        public = cache_runner.read_public_frame(public_dir, index)
        _require(public["record"]["frame_digest"] == cache_frame["frame_digest"], "public_frame_differs_from_cache")
        pose = cache_runner.causal_pose(public["record"], code_commit=episode_commit, policy=pose_policy)
        current_geometry = lr.entity_geometry_blocks(memory_before, cache_frame, samples_per_axis=samples)  # the superseded rule, for comparison
        observe_frame(accumulator, memory_before=memory_before, labels=labels, current=current_geometry,
                      depth=public["depth"], calibration=public["record"]["intrinsics"], pose=pose, samples_per_axis=samples)
        count += 1
    payload = {"schema_version": SCHEMA_VERSION, "stage": "S2-05 depth probe (read-only, ruling 73 (2))",
               "code_commit": _git("rev-parse", "HEAD"), "episode_id": args.episode_id, "arm": args.arm, "config": config,
               "descriptor": args.descriptor, "mask_source": args.mask_source, "frames": count,
               "episode_seal_sha256": seal["payload_sha256"], "margins_m": list(MARGINS_M), "samples_per_axis": samples,
               "probe": accumulator.report(), "wall_seconds": round(time.time() - started, 1)}
    (out_dir / PROBE_FILE_NAME).write_text(json.dumps(payload), encoding="utf-8")
    print(f"[depth-probe] {args.arm} {args.episode_id}: {count} frames, rows {payload['probe']['rows']}, {payload['wall_seconds']} s")
    return 0


def pool(args: argparse.Namespace) -> int:
    roots = [Path(p).resolve() for p in args.episode_roots.split(",") if p]
    tasks = []
    for episode_id in [e for e in args.episodes.split(",") if e]:
        found = [root / episode_id for root in roots if (root / episode_id / "receipt.json").exists()]
        _require(len(found) == 1, f"episode_root_not_unique:{episode_id}")
        for arm in [a for a in args.arms.split(",") if a]:
            if (Path(args.output_root) / episode_id / arm / PROBE_FILE_NAME).exists():
                continue
            tasks.append([sys.executable, str(HERE), "run", "--cache-root", args.cache_root, "--mask-source", args.mask_source,
                          "--episode-root", str(found[0]), "--geometry-root", args.geometry_root, "--episode-id", episode_id,
                          "--arm", arm, "--descriptor", args.descriptor, "--weights", args.weights, "--output-root", args.output_root])
    out = Path(args.output_root)
    out.mkdir(parents=True, exist_ok=True)
    plan = {"stage": "S2-05 depth probe", "commit": _git("rev-parse", "HEAD"), "tasks": len(tasks), "requested_workers": args.workers,
            "actual_workers": max(1, min(args.workers, len(tasks) or 1)), "worker_basis": args.worker_basis,
            "episodes": args.episodes.split(","), "arms": args.arms.split(","), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out / f"plan-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"[depth-probe] {len(tasks)} runs, {plan['actual_workers']} workers", flush=True)

    def one(command: list[str]) -> tuple[str, int, str]:
        completed = subprocess.run(command, capture_output=True, text=True, cwd=str(ROOT))
        return " ".join(command[command.index("--episode-id") + 1: command.index("--episode-id") + 2] + [command[command.index("--arm") + 1]]), \
            completed.returncode, (completed.stdout + completed.stderr)[-600:]

    failed = 0
    with multiprocessing.pool.ThreadPool(processes=plan["actual_workers"]) as workers:
        for name, code, tail in workers.imap_unordered(one, tasks):
            failed += int(code != 0)
            print(f"[depth-probe] {name} exit {code} {tail.strip().splitlines()[-1] if tail.strip() else ''}", flush=True)
    print(f"[depth-probe] done, {failed} failed", flush=True)
    return 0 if not failed else 1


def merge(args: argparse.Namespace) -> int:
    root = Path(args.output_root)
    arms: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob(f"*/*/{PROBE_FILE_NAME}")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _require(payload.get("schema_version") == SCHEMA_VERSION, f"probe_file_invalid:{path}")
        target = arms.setdefault(payload["arm"], {"episodes": [], "rows": {g: 0 for g in GROUPS}, "histograms": {g: {} for g in GROUPS},
                                                  "commits": set(), "config": payload["config"]})
        target["episodes"].append({"episode_id": payload["episode_id"], "frames": payload["frames"], "rows": payload["probe"]["rows"],
                                   "wall_seconds": payload["wall_seconds"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        target["commits"].add(payload["code_commit"])
        for group in GROUPS:
            target["rows"][group] += payload["probe"]["rows"][group]
            for name, counts in payload["probe"]["histograms"][group].items():
                prior = target["histograms"][group].setdefault(name, [0] * BINS)
                target["histograms"][group][name] = [a + b for a, b in zip(prior, counts)]
    report: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "stage": "S2-05 depth probe merge (read-only, ruling 73 (2))",
                              "output_root": str(root), "margins_m": list(MARGINS_M), "bins": BINS, "arms": {}}
    for arm, target in sorted(arms.items()):
        gone, present = target["histograms"]["gone"], target["histograms"]["present"]
        separation = {name: {"auc_gone_above_present": auc_from_histograms(gone.get(name, []), present.get(name, [])),
                             "gone_rows": int(sum(gone.get(name, []))), "present_rows": int(sum(present.get(name, [])))}
                      for name in sorted(set(gone) | set(present))}
        report["arms"][arm] = {"config": target["config"], "commits": sorted(target["commits"]), "episodes": target["episodes"],
                               "rows": target["rows"], "separation": separation, "histograms": target["histograms"]}
    Path(args.results).write_text(json.dumps(report, indent=1), encoding="utf-8")
    for arm, block in report["arms"].items():
        print(arm, json.dumps({k: v["auc_gone_above_present"] for k, v in block["separation"].items()}, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "pool"):
        p = sub.add_parser(name)
        p.add_argument("--cache-root", required=True)
        p.add_argument("--mask-source", required=True)
        p.add_argument("--geometry-root", required=True)
        p.add_argument("--descriptor", required=True)
        p.add_argument("--weights", required=True)
        p.add_argument("--output-root", required=True)
        p.add_argument("--allow-dirty", action="store_true")
    run_p = sub.choices["run"]
    run_p.add_argument("--episode-root", required=True)
    run_p.add_argument("--episode-id", required=True)
    run_p.add_argument("--arm", required=True)
    run_p.add_argument("--frames", type=int, default=None, help="smoke only: the first N frames")
    run_p.set_defaults(func=run)
    pool_p = sub.choices["pool"]
    pool_p.add_argument("--episode-roots", required=True)
    pool_p.add_argument("--episodes", required=True)
    pool_p.add_argument("--arms", default=",".join(PROBE_ARMS))
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
