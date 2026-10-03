"""S2-04: run one arm over one cached episode with the S2-01 runner and label, decompose and score it frame by frame.

Usage (server, frontend env; the S2-04 and S2-01 bits must be open, every policy value frozen):
    python ops/vsmt/lean_s2_04_evaluate_episode.py \\
        --cache-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<commit> \\
        --episode-root /root/autodl-tmp/vsmt_outputs/lean-s1-02b-<commit>/<episode> \\
        --geometry-root /root/autodl-tmp/vsmt_private/lean-s1-04-geometry-<commit> \\
        --episode-id procthor10k-0.1.2-train-00406 \\
        --arm TAF --config '{"theta_a": 0.6, "d_a": null}' \\
        --descriptor reid_projection:vitb14 --weights <the ReID head of that mask source> \\
        --mask-source simulator_instance_masks \\
        [--heads <vsmt-lean weights payload for a learned arm>] \\
        --output-root /root/autodl-tmp/vsmt_private/lean-s2-04-<commit> [--frames N]

What it does: validates the S2-04 and S2-01 contracts and refuses while a required bit is closed;
gathers every policy value from the contract that owns it (S0-01 dormancy and dedup, S0-05
should-be-visible minimum, S2-01 sampling resolution, S0-04 dominance share and delta_moved) and
refuses with the list still null; checks the ReID weights against the head S0-03 pins for
``--mask-source`` (ruling 84-1 (b)); loads the sealed cache episode, its recovered masks, the private
records and instance images, the S1-04 geometry table and the intervention log; drives
``lean_runner.run_episode`` (timing each frame) and hands every step to ``EpisodeTeacher``; streams
labels, training records and nuisance rows, closes the three streams, re-reads the nuisance file
(complete only once closed; LOG-256) and writes a receipt with the runner summary, the
seven-metric report, the diagnostics and the nuisance probes.  Multi-episode, multi-arm
orchestration is S2-05.

S3-03 options (ruling 104): ``--heuristic-labels <ELU-P configuration JSON>`` also writes HeuristicLabel's
training records (``heuristic_training_records.jsonl.gz``, ``lean_heuristic_label``) and a ``heuristic_records``
receipt block whose ``reproduction`` counts, on ELU-P's own trajectory at that configuration, the rows where the
label function and ELU-P's decisions differ (ruling 104-2 G4 needs none); ``--no-training-records`` writes no
teacher training record.

白话：这个入口把 S2-01 的 runner 和 S2-04 的 teacher 接在一起跑一条 episode、一个臂。公开阶段先跑，
每帧回执带着两段封存摘要，私有侧凭它打开这一帧的实例图与位姿打标签、记账、算指标输入；跑完写七项
指标。它不编排多条 episode（S2-05），不训练。S3-03 起可加 ``--heuristic-labels``：同一趟顺带写一份
HeuristicLabel 的训练记录（标签是 ELU-P 在 rollout_config 下会作的决定），在 ELU-P 自己的轨迹上还逐行
核对标签与臂的决定一致；``--no-training-records`` 则不写 teacher 训练记录（用不上它们的趟省盘）。
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
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402
from vsmt import lean_test_seal  # noqa: E402

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


def verify_cache_episode(cache_dir: Path, descriptor_asset_sha256s: dict[str, Any], *,
                         mask_source: str | None = None) -> tuple[dict[str, Any], list[Path]]:
    """The S1-04 loader's checks (every frame seal recomputed, the episode seal recomputed) without keeping the frames.

    白话：和 S1-04 的加载器做同样的核对——逐帧重算封印、重算 episode 封印——但核对完就丢掉帧，只留
    帧文件路径；处理阶段再逐帧读入。最大的开发 episode 有 3473 帧，整条读进内存要近 20 GB，流式读每个
    worker 只占一两 GB，16 核才用得上。核对与处理读到的是同一批字节，产物不变。裁决 72：封印按它声明的
    mask 来源重算；调用方给了 ``mask_source`` 时，另一来源的 cache 一律拒绝，实例分割与 SAM2 不会混用。
    """

    receipt_path = cache_dir / "receipt.json"
    if not receipt_path.exists() or load_json(receipt_path).get("status") != "succeeded":
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", "no succeeded cache receipt")
    seal_path = cache_dir / "episode_seal.json"
    if not seal_path.exists():
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", "no episode seal")
    seal = load_json(seal_path)
    if seal.get("frontend_config_sha256") != diag.fc.D223_FRONTEND_CONFIG_SHA256:
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", "episode seal names another frontend config")
    try:
        sealed_source = diag.fc.sealed_mask_source(seal)
    except diag.fc.LeanFrontendCacheError as exc:
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", exc.detail) from exc
    if mask_source is not None and sealed_source != mask_source:
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed",
                                      f"episode sealed with mask source {sealed_source}, the run names {mask_source}")
    paths = sorted(cache_dir.glob(f"*{diag.cache_runner.FRAME_FILE_SUFFIX}"))
    if len(paths) != int(seal.get("episode_frame_count", -1)):
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", f"{len(paths)} frame files for a seal over {seal.get('episode_frame_count')}")
    seal_inputs = []
    for path in paths:
        frame = diag.cache_runner.load_cache_frame(path)
        try:
            diag.fc.verify_frame_seal(frame, frontend_config_sha256=diag.fc.D223_FRONTEND_CONFIG_SHA256,
                                      descriptor_asset_sha256s=descriptor_asset_sha256s)
        except diag.fc.LeanFrontendCacheError as exc:
            raise diag.DiagnosticsFailure("cache_missing_or_unsealed", f"{path.name}: {exc.detail}") from exc
        seal_inputs.append({"tick": frame["tick"], "frame_seal": frame["frame_seal"]})
        del frame
    try:
        recomputed = diag.fc.seal_episode(seal_inputs, frontend_config_sha256=diag.fc.D223_FRONTEND_CONFIG_SHA256,
                                          mask_source=sealed_source)
    except diag.fc.LeanFrontendCacheError as exc:
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", exc.detail) from exc
    if recomputed["payload_sha256"] != seal.get("payload_sha256"):
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", "episode seal mismatch")
    return seal, paths


def recomputed_frame_digest(public: Path, record: dict[str, Any], depth_raw: Any) -> str:
    """Ruling 76 (4)(a): the S1-02 public frame digest recomputed from the bytes read -- the rgb PNG pixels, the
    depth array as saved, and the record's observation index, relative pose and action summary.

    白话：S1-02 生成时把 RGB 与深度的字节摘要连同三个公开字段一起算成 frame_digest。读取方以前只把记录里的摘要
    字串转交给 runner，文件被改了也看不出来（审查者把深度整体加 0.2 m、摘要不变，照样通过）。这里按同一定义
    重算，不符就拒。它只读公开面，不改任何数。
    """

    import hashlib

    import numpy as np
    from PIL import Image

    from cpmt.hashing import canonical_json

    rgb_path = public / record["rgb_path"]
    if rgb_path.parent.resolve() != public.resolve():
        raise diag.DiagnosticsFailure("public_input_missing_or_malformed", f"rgb path escapes the public plane: {rgb_path}")
    with Image.open(rgb_path) as image:
        rgb = np.asarray(image, dtype=np.uint8)
    payload = {"rgb": hashlib.sha256(rgb.tobytes()).hexdigest(), "depth": hashlib.sha256(np.asarray(depth_raw).tobytes()).hexdigest(),
               **{key: record[key] for key in ("observation_index", "relative_pose", "action_summary")}}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def public_depth_view(episode_root: Path, index: int, *, episode_commit: str, pose_policy: dict[str, Any],
                      cache_dir: Path, fragments: list[dict[str, Any]]) -> dict[str, Any]:
    """Ruling 74: one frame's public depth view -- the S1-02 public record's frame digest and intrinsics, the depth
    file it names and the causal pose read under the S1-03 pose policy; nothing of the private plane.

    白话：逐点深度检验要本帧的公开深度图、内参和位姿。它们本来就在 S1-02 的公开面里（cache 只存了由深度算出
    的体积），这里按帧号读出来，交给 runner 与 teacher；帧摘要随行，runner 核对它和 cache 帧是同一帧。
    """

    import numpy as np

    public = episode_root / "public"
    record = load_json(public / f"{index:04d}.frame.json")
    depth_path = public / record["depth_path"]
    if depth_path.parent.resolve() != public.resolve():
        raise diag.DiagnosticsFailure("public_input_missing_or_malformed", f"depth path escapes the public plane: {depth_path}")
    pose = diag.cache_runner.causal_pose(record, code_commit=episode_commit, policy=pose_policy)
    depth_raw = np.load(depth_path)
    if recomputed_frame_digest(public, record, depth_raw) != record["frame_digest"]:
        raise diag.DiagnosticsFailure("public_input_missing_or_malformed", f"frame {index}: the rgb/depth bytes do not reproduce the frame digest")
    view = {"frame_digest": record["frame_digest"], "depth_m": depth_raw.astype(np.float32),
            "calibration": record["intrinsics"], "pose": pose}
    # ruling 75 (2)(a): each fragment's surface points, from the cache's own mask file re-digested against the sealed frame
    masks = diag.cache_runner.read_masks_file(cache_dir / f"{index:04d}{diag.cache_runner.MASK_FILE_SUFFIX}")
    if len(masks["mask_sha256"]) != len(fragments):
        raise diag.DiagnosticsFailure("cache_missing_or_unsealed", f"frame {index}: {len(masks['mask_sha256'])} masks for {len(fragments)} fragments")
    surface: dict[str, Any] = {}
    for position, fragment in enumerate(fragments):
        mask = masks["masks"][position]
        if diag.fc.mask_sha256_of(mask) != fragment["mask_sha256"]:
            raise diag.DiagnosticsFailure("cache_missing_or_unsealed", f"frame {index}: mask {position} does not reproduce {fragment['fragment_id']}")
        surface[str(fragment["fragment_id"])] = lr.fragment_surface_points(mask, view)
    view["fragment_surface_points"] = surface
    return view


def episode_depth_reader(episode_root: Path, cache_dir: Path) -> Any:
    """``(index, cache frame) -> public depth view`` for one episode (its generator commit read once, the pose policy from S1-03)."""

    commit = str(load_json(episode_root / "receipt.json")["code_commit"])
    policy = load_json(diag.cache_runner.CONTRACT_PATH)["public_pose_correction"]
    return lambda index, frame: public_depth_view(episode_root, index, episode_commit=commit, pose_policy=policy,
                                                  cache_dir=cache_dir, fragments=list(frame["fragments"]))


def load_private_frame(episode_root: Path, index: int) -> tuple[dict[str, Any], Any]:
    """One private record and its instance image (the S1-04 loader's reading, one frame at a time)."""

    import numpy as np
    from PIL import Image

    private = episode_root / "private"
    record = load_json(private / f"{index:04d}.frame.json")
    return record, np.asarray(Image.open(private / record["instance_mask_path"]))


def peak_rss_bytes() -> int:
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except (ImportError, AttributeError):  # Windows: no resource module; the receipt says so
        return 0


class NullStream:
    """A stream that writes nothing (``--no-training-records``): the pass needs no training record, only its other outputs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows = 0

    def write(self, row: dict[str, Any]) -> None:
        return None

    def close(self) -> int:
        return 0


class Stream:
    def __init__(self, path: Path) -> None:
        self.handle = gzip.open(path, "wb", compresslevel=6)
        self.path = path
        self.rows = 0

    def write(self, row: dict[str, Any]) -> None:
        self.handle.write((json.dumps(row) + "\n").encode("utf-8"))
        self.rows += 1

    def close(self) -> int:
        self.handle.close()
        return self.path.stat().st_size


def finish_streams(labels_stream: Stream, training_stream: Stream, nuisance_stream: Stream) -> dict[str, Any]:
    """Close the three streams, then re-read the nuisance file and run the S0-04 probes over its rows.

    The order is the point: a gzip member is complete only once its writer is closed. Re-reading the
    nuisance file while it was still open (the entry did so until LOG-256) returned no rows while the
    compressed output still sat in the gzip buffers, so every receipt carried an empty probe block, and
    raised EOFError once part of it had reached the disk, which happened from about 32 KB of compressed
    output and cost the calibration pass every episode of 1262 frames or more. The re-read row count
    must equal the rows written; anything else is refused, never patched.
    """

    sizes = {"labels_file_bytes": labels_stream.close(), "training_file_bytes": training_stream.close(),
             "nuisance_file_bytes": nuisance_stream.close()}
    rows = _reread(nuisance_stream.path)
    if len(rows) != nuisance_stream.rows:
        raise RuntimeError(f"nuisance_stream_reread_mismatch: {len(rows)} rows re-read, {nuisance_stream.rows} written")
    return {**sizes, "nuisance_rows_written": nuisance_stream.rows,
            "nuisance_probes": ev.nuisance_probes([{"nuisance": row} for row in rows])}


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
    parser.add_argument("--mask-source", required=True, choices=list(diag.fc.MASK_SOURCES),
                        help="ruling 72: the mask source the cache must be sealed with; a cache of the other source is refused")
    parser.add_argument("--heuristic-labels", default=None,
                        help="ruling 104-1 1c: an ELU-P configuration at the rollout_config with the S3 fitted values; also write "
                             "HeuristicLabel's training records (heuristic_training_records.jsonl.gz), and on ELU-P's own trajectory "
                             "count where the label function and ELU-P's decisions differ (ruling 104-2 G4)")
    parser.add_argument("--no-training-records", action="store_true",
                        help="do not write the teacher's training records (a pass that trains nothing on them, e.g. the fit pass)")
    parser.add_argument("--manifest-split", default=None, choices=("train", "validation"),
                        help="ruling 104-6: refuse an episode that is not in this split of the S3 manifest (every S3-03 pass names it)")
    parser.add_argument("--allow-dirty", action="store_true", help="tests only")
    args = parser.parse_args()
    refusal = lean_test_seal.refusal([args.cache_root, args.episode_root, args.geometry_root], reader="s2-04")  # ruling 103-1: sealed S3 test roots are read only by S3-05
    if refusal:
        print(f"[s2-04] refused: {refusal}", file=sys.stderr)
        return 2
    if args.manifest_split:  # ruling 104-6: an S3-03 pass reads only episodes of its manifest split
        from vsmt import lean_s3_03

        problem = lean_s3_03.manifest_split_refusal(args.episode_id, args.manifest_split)
        if problem:
            print(f"[s2-04] refused: {problem}", file=sys.stderr)
            return 2

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
    labeller = None
    if args.heuristic_labels:  # ruling 104-1 1c; checked before anything is read or written
        from vsmt import lean_heuristic_label as hl

        try:
            if args.arm == "AssocOnly":
                raise hl.LeanHeuristicLabelError("heuristic_labels_need_the_existence_step")
            labeller = hl.HeuristicLabeller(json.loads(args.heuristic_labels))
        except ValueError as exc:  # the labeller's and the runner's refusals, and malformed JSON
            print(f"[s2-04] refused: --heuristic-labels {exc}", file=sys.stderr)
            return 2

    scorer = None
    if args.arm in lr.LEARNED_ARMS:
        if not args.heads:
            print(f"[s2-04] refused: {args.arm} needs --heads (an S2-03 weights payload)", file=sys.stderr)
            return 2
        from vsmt import lean_model

        scorer = lean_model.LeanScorer(lean_model.load_heads(load_json(Path(args.heads)), device=args.device), device=args.device)
    try:  # ruling 84-1 (b): the head pinned for --mask-source, which verify_cache_episode below holds the seal to
        projector, weights_sha256 = s2_01.reid_projector(args.descriptor, args.weights, mask_source=args.mask_source, device=args.device)
    except s2_01.EntryRefusal as exc:
        print(f"[s2-04] refused: {exc}", file=sys.stderr)
        return 2

    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    episode_root = Path(args.episode_root).resolve()
    seal, frame_paths = verify_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s(), mask_source=args.mask_source)
    if args.frames is not None:
        frame_paths = frame_paths[: int(args.frames)]
    count = len(frame_paths)
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
    labels_stream, nuisance_stream = Stream(out_dir / "labels.jsonl.gz"), Stream(out_dir / "nuisance.jsonl.gz")
    training_stream = (NullStream if args.no_training_records else Stream)(out_dir / "training_records.jsonl.gz")
    heuristic_stream = Stream(out_dir / "heuristic_training_records.jsonl.gz") if labeller is not None else None
    started = time.time()
    receipts: list[dict[str, Any]] = []
    state = None
    mark = time.time()
    current: dict[str, Any] = {}

    depth_view = episode_depth_reader(episode_root, cache_dir)

    def frames():  # one frame in memory at a time; the runner consumes exactly one per step
        for index, path in enumerate(frame_paths):
            frame = diag.cache_runner.load_cache_frame(path)
            frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(index, frame)  # rulings 74/75: attached after the seal check, never written
            current["frame"] = frame
            yield frame

    for index, step in enumerate(lr.run_episode(frames(), episode_id=args.episode_id, arm=args.arm, config=config,
                                                policy=policy["runner"], descriptor=args.descriptor, projector=projector, scorer=scorer)):
        runtime = time.time() - mark
        receipts.append(step["receipt"])
        state = step["state"]
        cache_frame = current["frame"]
        masks = diag.cache_runner.read_masks_file(cache_dir / f"{index:04d}{diag.cache_runner.MASK_FILE_SUFFIX}")
        record, image = load_private_frame(episode_root, index)
        labelled = teacher.label_frame(step, cache_frame=cache_frame, private_record=record, masks=masks,
                                       label_image=image, runtime_s=runtime, peak_memory_bytes=peak_rss_bytes())
        if collector is not None:
            collector.observe(step, labelled)
        if counter is not None:
            counter.observe(step, cache_frame=cache_frame, private_record=record, evidence=teacher.evidence)
        training_stream.write({"tick": labelled["tick"], **labelled["training_record"]})
        if labeller is not None:
            heuristic = labeller.label(step, arm=args.arm, arm_config=config)
            heuristic_stream.write({"tick": labelled["tick"], **heuristic["training_record"]})
        nuisance_stream.write({"tick": labelled["tick"], **labelled["nuisance"]})
        labels_stream.write({k: v for k, v in labelled.items() if k not in ("training_record", "nuisance")})
        mark = time.time()
    summary = lr.episode_summary(state, receipts)
    episode = teacher.episode_report()
    streams = finish_streams(labels_stream, training_stream, nuisance_stream)  # closed before the re-read (LOG-256)
    if heuristic_stream is not None:
        summary["heuristic_records"] = {**labeller.summary(), "file": heuristic_stream.path.name, "rows": heuristic_stream.rows,
                                        "file_bytes": heuristic_stream.close()}
        reproduction = summary["heuristic_records"]["reproduction"]
        if reproduction is not None and (reproduction["fragment_mismatches"] or reproduction["existence_mismatches"]):
            print(f"[s2-04] HeuristicLabel labels differ from ELU-P's decisions on its own trajectory: {reproduction}", file=sys.stderr)
    summary["training_records_written"] = not args.no_training_records
    summary.update({
        "stage": ev.STAGE_ID, "code_commit": commit, "cache_root": str(cache_dir), "episode_root": str(episode_root),
        "episode_seal_sha256": seal["payload_sha256"], "mask_source": args.mask_source, "frames_requested": args.frames, "config": config,
        "descriptor": args.descriptor, "weights_sha256": weights_sha256, "heads": args.heads,
        "policy": policy, "window": window, "executed_interventions": len(executed),
        "report": episode["report"], "diagnostics": episode["diagnostics"],
        "nuisance_probes": streams["nuisance_probes"], "nuisance_rows_written": streams["nuisance_rows_written"],
        "peak_memory_source": "resource.getrusage ru_maxrss" if peak_rss_bytes() else "unavailable_on_this_platform",
        "wall_seconds": round(time.time() - started, 1),
        "labels_file_bytes": streams["labels_file_bytes"], "training_file_bytes": streams["training_file_bytes"],
        "nuisance_file_bytes": streams["nuisance_file_bytes"],
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
