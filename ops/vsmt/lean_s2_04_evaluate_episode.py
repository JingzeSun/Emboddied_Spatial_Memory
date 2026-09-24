"""S2-04: run one arm over one cached episode with the S2-01 runner and label, decompose and score it frame by frame.

Usage (server, frontend env; the S2-04 and S2-01 bits must be open, every policy value frozen):
    python ops/vsmt/lean_s2_04_evaluate_episode.py \\
        --cache-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<commit> \\
        --episode-root /root/autodl-tmp/vsmt_outputs/lean-s1-02b-<commit>/<episode> \\
        --geometry-root /root/autodl-tmp/vsmt_private/lean-s1-04-geometry-<commit> \\
        --episode-id procthor10k-0.1.2-train-00406 \\
        --arm TAF --config '{"theta_a": 0.6, "d_a": null}' \\
        --descriptor reid_projection:vitb14 --weights <reid_head_vitb14.json> \\
        [--heads <vsmt-lean weights payload for a learned arm>] \\
        --output-root /root/autodl-tmp/vsmt_private/lean-s2-04-<commit> [--frames N]

What it does: validates the S2-04 and S2-01 contracts and refuses while a required bit is closed;
gathers every policy value from the contract that owns it (S0-01 dormancy and dedup, S0-05
should-be-visible minimum, S2-01 sampling resolution, S0-04 dominance share and delta_moved) and
refuses with the list still null; loads the sealed cache episode, its recovered masks, the private
records and instance images, the S1-04 geometry table and the intervention log; drives
``lean_runner.run_episode`` (timing each frame) and hands every step to ``EpisodeTeacher``; streams
labels, training records and nuisance rows, and writes a receipt with the runner summary, the
seven-metric report, the diagnostics and the nuisance probes.  Multi-episode, multi-arm
orchestration is S2-05.

白话：这个入口把 S2-01 的 runner 和 S2-04 的 teacher 接在一起跑一条 episode、一个臂。公开阶段先跑，
每帧回执带着两段封存摘要，私有侧凭它打开这一帧的实例图与位姿打标签、记账、算指标输入；跑完写七项
指标。它不编排多条 episode（S2-05），不训练。
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
import lean_s2_01_runner as s2_01  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "vsmt"
S2_04_CONTRACT = CONFIG_DIR / "lean_s2_04_evaluation_v1.json"
S0_04_CONTRACT = CONFIG_DIR / "lean_s0_teacher_metrics_v2.json"
REQUIRED_S2_04 = ("label_generation_run", "server_run")
REQUIRED_S2_01 = ("episode_run", "server_run")


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def gather_teacher_policy() -> tuple[dict[str, Any], list[str]]:
    """The S2-04 policy values from the contracts that own them, plus the slots still null."""

    runner_policy, missing = s2_01.gather_policy()
    labels = load_json(S0_04_CONTRACT)["labels"]
    policy = {
        "dominance_min_share": labels["fragment_dominance"]["dominance_min_share"],
        "delta_moved_m": labels["existence"]["delta_moved_m"],
        "should_be_visible_min_ratio": runner_policy["should_be_visible_min_ratio"],
        "entity_geometry_samples_per_axis": runner_policy["entity_geometry_samples_per_axis"],
    }
    if policy["dominance_min_share"] is None:
        missing.append("S0-04 labels.fragment_dominance.dominance_min_share")
    if policy["delta_moved_m"] is None:
        missing.append("S0-04 labels.existence.delta_moved_m")
    return {"runner": runner_policy, "teacher": policy}, missing


def peak_rss_bytes() -> int:
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except (ImportError, AttributeError):  # Windows: no resource module; the receipt says so
        return 0


class Stream:
    def __init__(self, path: Path) -> None:
        self.handle = gzip.open(path, "wb", compresslevel=6)
        self.path = path

    def write(self, row: dict[str, Any]) -> None:
        self.handle.write((json.dumps(row) + "\n").encode("utf-8"))

    def close(self) -> int:
        self.handle.close()
        return self.path.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--episode-root", required=True, help="the S1-02 episode directory (public/, private/, provenance/, receipt.json)")
    parser.add_argument("--geometry-root", required=True, help="the S1-04 object geometry output root")
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--arm", required=True, choices=list(lr.RUNNABLE_ARMS))
    parser.add_argument("--config", required=True, help="JSON object with the arm's registered parameters")
    parser.add_argument("--descriptor", required=True, choices=list(lr.DESCRIPTOR_CHOICES))
    parser.add_argument("--weights", default=None, help="the frozen ReID weights file; required for the selected descriptor")
    parser.add_argument("--heads", default=None, help="an S2-03 weights payload; required for a learned arm")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--frames", type=int, default=None, help="run only the first N frames (trial)")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--calibration", action="store_true", help="S2-05 calibration pass: also write the calibration histograms")
    parser.add_argument("--elu-p-counts", action="store_true", help="S2-05 fit pass: also write the ELU-P count records")
    parser.add_argument("--allow-dirty", action="store_true", help="tests only")
    args = parser.parse_args()

    contract = ev.validate_evaluation_contract(load_json(S2_04_CONTRACT))
    runner_contract = lr.validate_runner_contract(load_json(s2_01.S2_01_CONTRACT))
    closed = [f"S2-04 {name}" for name in REQUIRED_S2_04 if contract["authorization"].get(name) is not True]
    closed += [f"S2-01 {name}" for name in REQUIRED_S2_01 if runner_contract["authorization"].get(name) is not True]
    if closed:
        print(f"[s2-04] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    policy, missing = gather_teacher_policy()
    if missing:
        print(f"[s2-04] refused: policy values still null: {missing}", file=sys.stderr)
        return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[s2-04] refused: the checkout is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    config = json.loads(args.config)
    lr.validate_arm_config(args.arm, config)

    scorer = None
    if args.arm in lr.LEARNED_ARMS:
        if not args.heads:
            print(f"[s2-04] refused: {args.arm} needs --heads (an S2-03 weights payload)", file=sys.stderr)
            return 2
        from vsmt import lean_model

        scorer = lean_model.LeanScorer(lean_model.load_heads(load_json(Path(args.heads)), device=args.device), device=args.device)
    projector = None
    weights_sha256 = None
    if args.descriptor == la.SELECTED_DESCRIPTOR:
        if not args.weights:
            print("[s2-04] refused: --weights is required for the selected descriptor", file=sys.stderr)
            return 2
        payload = load_json(Path(args.weights))
        projector = lr.descriptor_projector(payload, expected_sha256=la.SELECTED_REID_WEIGHTS_SHA256, device=args.device)
        weights_sha256 = payload["sha256"]

    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    episode_root = Path(args.episode_root).resolve()
    frames, seal = diag.load_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s())
    if args.frames is not None:
        frames = frames[: int(args.frames)]
    count = len(frames)
    masks = diag.load_masks(cache_dir, count)
    records, images = diag.load_private(episode_root, count)
    table = og.validate_geometry_table(load_json(Path(args.geometry_root).resolve() / args.episode_id / og.TABLE_FILE_NAME))
    executed, window = diag.cache_runner_read_interventions(episode_root / "provenance")
    episode_receipt = load_json(episode_root / "receipt.json") if (episode_root / "receipt.json").exists() else {}
    split_seed = int(load_json(CONFIG_DIR / "lean_s1_02a_pilot_v2.json")["split_freeze"]["seed"])
    nuisance_meta = {"path": str(cache_dir), "seed": split_seed, "house_index": episode_receipt.get("source_index")}

    out_dir = Path(args.output_root).resolve() / args.episode_id / args.arm
    if out_dir.exists() and any(out_dir.iterdir()):
        print(f"[s2-04] refused: output directory exists and is not empty: {out_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    teacher = ev.EpisodeTeacher(arm=args.arm, geometry_table=table, executed_interventions=executed, window=window,
                                policy=policy["teacher"], nuisance_meta=nuisance_meta)
    collector = counter = None
    if args.calibration or args.elu_p_counts:
        from vsmt import lean_development as dev

        collector = dev.CalibrationCollector() if args.calibration else None
        counter = (dev.EluPCounter(geometry_table=table, executed_interventions=executed, window=window, policy=policy["teacher"])
                   if args.elu_p_counts else None)
    labels_stream, training_stream, nuisance_stream = (Stream(out_dir / name) for name in
                                                       ("labels.jsonl.gz", "training_records.jsonl.gz", "nuisance.jsonl.gz"))
    started = time.time()
    receipts: list[dict[str, Any]] = []
    state = None
    mark = time.time()
    for index, step in enumerate(lr.run_episode(frames, episode_id=args.episode_id, arm=args.arm, config=config,
                                                policy=policy["runner"], descriptor=args.descriptor, projector=projector, scorer=scorer)):
        runtime = time.time() - mark
        receipts.append(step["receipt"])
        state = step["state"]
        labelled = teacher.label_frame(step, cache_frame=frames[index], private_record=records[index], masks=masks[index],
                                       label_image=images[index], runtime_s=runtime, peak_memory_bytes=peak_rss_bytes())
        if collector is not None:
            collector.observe(step, labelled)
        if counter is not None:
            counter.observe(step, cache_frame=frames[index], private_record=records[index], evidence=teacher.evidence)
        training_stream.write({"tick": labelled["tick"], **labelled["training_record"]})
        nuisance_stream.write({"tick": labelled["tick"], **labelled["nuisance"]})
        labels_stream.write({k: v for k, v in labelled.items() if k not in ("training_record", "nuisance")})
        mark = time.time()
    summary = lr.episode_summary(state, receipts)
    episode = teacher.episode_report()
    summary.update({
        "stage": ev.STAGE_ID, "code_commit": commit, "cache_root": str(cache_dir), "episode_root": str(episode_root),
        "episode_seal_sha256": seal["payload_sha256"], "frames_requested": args.frames, "config": config,
        "descriptor": args.descriptor, "weights_sha256": weights_sha256, "heads": args.heads,
        "policy": policy, "window": window, "executed_interventions": len(executed),
        "report": episode["report"], "diagnostics": episode["diagnostics"],
        "nuisance_probes": ev.nuisance_probes([{"nuisance": row} for row in _reread(out_dir / "nuisance.jsonl.gz")]),
        "peak_memory_source": "resource.getrusage ru_maxrss" if peak_rss_bytes() else "unavailable_on_this_platform",
        "wall_seconds": round(time.time() - started, 1),
        "labels_file_bytes": labels_stream.close(), "training_file_bytes": training_stream.close(),
        "nuisance_file_bytes": nuisance_stream.close(),
    })
    if collector is not None:
        (out_dir / "calibration.json").write_text(json.dumps(collector.to_json()), encoding="utf-8")
        summary["calibration"] = collector.report()
    if counter is not None:
        counts = counter.finish()
        (out_dir / "elu_p_counts.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")
        summary["elu_p_counts"] = counts
    summary["status"] = "succeeded"
    (out_dir / "receipt.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    report = summary["report"]
    print(f"[s2-04] {args.arm} {args.episode_id}: {summary['frames']} frames, node F1 {report['node_prf1']['node_f1']}, "
          f"MRR {report['missing_residual_rate']['missing_residual_rate']}, continuity {report['identity_continuity']['identity_continuity']}, "
          f"{summary['wall_seconds']} s")
    return 0


def _reread(path: Path) -> list[dict[str, Any]]:
    path_handle = gzip.open(path, "rb")
    try:
        return [json.loads(line) for line in path_handle.read().decode("utf-8").splitlines() if line]
    finally:
        path_handle.close()


if __name__ == "__main__":
    sys.exit(main())
