"""S2-01: run one arm over one cached episode with the common runner and write its receipts.

Usage (server, frontend env; the S2-01 contract's ``episode_run`` and ``server_run`` bits must be open,
and every policy value the runner reads must be frozen in its own contract):
    python ops/vsmt/lean_s2_01_runner.py \\
        --cache-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<commit> \\
        --episode-id procthor10k-0.1.2-train-00406 \\
        --arm TAF --config '{"theta_a": 0.6, "d_a": null}' \\
        --descriptor reid_projection:vitb14 \\
        --weights /root/autodl-tmp/vsmt_private/lean-s1-04-diagnostics-<commit>/reid_head_vitb14.json \\
        --output-root /root/autodl-tmp/vsmt_private/lean-s2-01-<commit> [--frames N]

What it does: validates the S2-01 contract and refuses while its bits are closed; gathers the shared
policy values from the contracts that own them (S0-01 dormancy and dedup, S0-05 should-be-visible
minimum, S2-01 sampling resolution) and refuses with the list of slots still null; loads the sealed
cache episode through the S1-04 loader (every frame seal recomputed from the loaded bytes); loads the
ReID weights and checks their digest against the S1-05 freeze; drives ``lean_runner.run_episode`` and
streams per-frame receipts to ``frames.jsonl.gz``, the two S0-03 seal payloads per frame to
``seals.jsonl.gz`` (the teacher's inputs), and an episode summary to ``receipt.json``.  Learned arms
need a scorer from S2-03 and are refused here; multi-episode, multi-arm orchestration is S2-05.

白话：这个入口把共同 runner 接到真实 cache 上跑一条 episode、一个臂。它先核对合同与授权位，再从各自
的合同读登记值（为 null 就列出来拒绝），加载封印过的 cache（逐帧重算封印），核对权重摘要，然后逐帧
运行并把回执流式写盘。它不编排多条 episode 或多个臂（S2-05），不算指标（S2-04），学习臂要等 S2-03 的
打分器。
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s1_04_diagnostics as diag  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "vsmt"
S2_01_CONTRACT = CONFIG_DIR / "lean_s2_01_runner_v1.json"
S0_01_CONTRACT = CONFIG_DIR / "lean_s0_entity_memory_v2.json"
S0_05_CONTRACT = CONFIG_DIR / "lean_s0_arms_v2.json"
REQUIRED_AUTHORIZATION = ("episode_run", "server_run")


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def gather_policy() -> tuple[dict[str, Any], list[str]]:
    """The shared policy values from the contracts that own them, plus the slots still null."""

    s0_01 = load_json(S0_01_CONTRACT)
    s0_05 = load_json(S0_05_CONTRACT)
    s2_01 = load_json(S2_01_CONTRACT)
    dedup = {name: s0_01["shared_dedup"][name] for name in ("period_ticks", "descriptor_cosine_min", "centroid_distance_max_m", "aabb_iou_min")}
    policy = {
        "dormancy_missed_opportunity_limit": s0_01["shared_dormancy"]["dormancy_missed_opportunity_limit"],
        "dedup": dedup,
        "should_be_visible_min_ratio": s0_05["shared"]["should_be_visible_min_ratio"],
        "entity_geometry_samples_per_axis": s2_01["entity_geometry"]["samples_per_axis"],
    }
    missing = []
    if policy["dormancy_missed_opportunity_limit"] is None:
        missing.append("S0-01 shared_dormancy.dormancy_missed_opportunity_limit")
    missing += [f"S0-01 shared_dedup.{name}" for name, value in dedup.items() if value is None]
    if policy["should_be_visible_min_ratio"] is None:
        missing.append("S0-05 shared.should_be_visible_min_ratio")
    if policy["entity_geometry_samples_per_axis"] is None:
        missing.append("S2-01 entity_geometry.samples_per_axis")
    return policy, missing


def write_jsonl_gz(path: Path, rows: list[dict[str, Any]]) -> int:
    with gzip.open(path, "wb", compresslevel=6) as handle:
        for row in rows:
            handle.write((json.dumps(row) + "\n").encode("utf-8"))
    return path.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--episode-root", required=True,
                        help="ruling 74: the S1-02 episode directory whose public plane gives each frame's depth view")
    parser.add_argument("--arm", required=True, choices=list(lr.RUNNABLE_ARMS))
    parser.add_argument("--config", required=True, help="JSON object with the arm's registered parameters")
    parser.add_argument("--descriptor", required=True, choices=list(lr.DESCRIPTOR_CHOICES))
    parser.add_argument("--weights", default=None, help="the frozen ReID weights file; required for the selected descriptor")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--frames", type=int, default=None, help="run only the first N frames (trial)")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--allow-dirty", action="store_true", help="tests only")
    args = parser.parse_args()

    contract = lr.validate_runner_contract(load_json(S2_01_CONTRACT))
    closed = [name for name in REQUIRED_AUTHORIZATION if contract["authorization"].get(name) is not True]
    if closed:
        print(f"[s2-01] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    policy, missing = gather_policy()
    if missing:
        print(f"[s2-01] refused: policy values still null: {missing}", file=sys.stderr)
        return 2
    if args.arm in lr.LEARNED_ARMS:
        print(f"[s2-01] refused: {args.arm} needs the S2-03 scorer; this entry drives rule arms only", file=sys.stderr)
        return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[s2-01] refused: the checkout is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    config = json.loads(args.config)
    lr.validate_arm_config(args.arm, config)
    projector = None
    weights_sha256 = None
    if args.descriptor == la.SELECTED_DESCRIPTOR:
        if not args.weights:
            print("[s2-01] refused: --weights is required for the selected descriptor", file=sys.stderr)
            return 2
        payload = load_json(Path(args.weights))
        projector = lr.descriptor_projector(payload, expected_sha256=la.SELECTED_REID_WEIGHTS_SHA256, device=args.device)
        weights_sha256 = payload["sha256"]

    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    frames, seal = diag.load_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s())
    if args.frames is not None:
        frames = frames[: int(args.frames)]
    import lean_s2_04_evaluate_episode as s2_04
    depth_view = s2_04.episode_depth_reader(Path(args.episode_root).resolve())
    for index, frame in enumerate(frames):  # ruling 74: the public depth view, attached after the seal check
        frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(index)
    out_dir = Path(args.output_root).resolve() / args.episode_id / args.arm
    if out_dir.exists() and any(out_dir.iterdir()):
        print(f"[s2-01] refused: output directory exists and is not empty: {out_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    receipts: list[dict[str, Any]] = []
    seals: list[dict[str, Any]] = []
    state = None
    for step in lr.run_episode(frames, episode_id=args.episode_id, arm=args.arm, config=config, policy=policy,
                               descriptor=args.descriptor, projector=projector):
        receipts.append(step["receipt"])
        seals.append({"tick": step["receipt"]["tick"], "stage_a": step["stage_a"], "stage_b": step["stage_b"]})
        state = step["state"]
    summary = lr.episode_summary(state, receipts)
    summary.update({
        "code_commit": commit, "cache_root": str(cache_dir), "episode_seal_sha256": seal["payload_sha256"],
        "frames_requested": args.frames, "config": config, "descriptor": args.descriptor, "weights_sha256": weights_sha256,
        "policy": policy, "wall_seconds": round(time.time() - started, 1),
        "frames_file_bytes": write_jsonl_gz(out_dir / "frames.jsonl.gz", receipts),
        "seals_file_bytes": write_jsonl_gz(out_dir / "seals.jsonl.gz", seals),
    })
    (out_dir / "receipt.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"[s2-01] {args.arm} {args.episode_id}: {summary['frames']} frames, atoms {summary['atoms']}, "
          f"illegal {summary['illegal_programs']}, final {summary['final_entities_by_state']}, {summary['wall_seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
