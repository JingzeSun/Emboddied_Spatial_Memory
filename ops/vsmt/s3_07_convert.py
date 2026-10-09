"""S3-07 (ruling 111-8 step 4): 3RScan pairs converted into episodes the frozen readers read; the sample check; a reader check.

Usage (GPU host of S3-07, frozen frontend environment; CPU only):
    python ops/vsmt/s3_07_convert.py sample-check --scans-root <3rscan>/scans --meta <3rscan>/meta/3RScan.json \\
        --labels "<3rscan>/meta/3RScan.v2 Semantic Classes - Mapping.csv" --out <report.json>
    python ops/vsmt/s3_07_convert.py convert --scans-root ... --meta ... --labels ... --render-root <s3_07_render root> \\
        --out-root <episodes root> --geometry-root <geometry root> --purpose sample|formal --workers N --worker-basis "<evidence>" \\
        [--slots-from <sample-check report>] [--resume]
    python ops/vsmt/s3_07_convert.py reader-check --out-root <episodes root> --geometry-root <geometry root> --report <json>

Subcommands:
  * ``sample-check`` (111-5 and amendment 1): decides the contract's four sample slots on the registered sample scene (the
    first validation scene by reference-scan ID, with its rescans) under the approved rules -- translation unit (median
    nearest-point distance of unchanged objects after alignment; stop if both readings exceed 0.10 m), OBB axis order
    (median share of an object's own annotated vertices inside its OBB; stop if both are below 95%), image turn (per-scan
    median roll cosine, clockwise >= cos 45 degrees and the largest of the four turns), ambiguity structure (every
    validation scene's ``ambiguity`` readable as instance_source / instance_target). Geometry and annotations only, no
    method; writes one JSON, and the registration commit then writes the slots into the contract.
  * ``convert``: one worker per (reference scan, rescan) pair, writing ``<out>/3rscan-<ref>-<rescan>/{public,private,
    provenance}`` and ``receipt.json`` (last), and ``<geometry>/<episode>/object_geometry.json``. Public frames hold the
    turned, cropped and scaled RGB, the rendered depth, the target intrinsics, the pose relative to observation 0 in the
    project axes and the frame digest; private frames the rendered instance image, the label-to-private-key map, visible
    pixel counts and box centres; intervention log and degenerate window per 111-2 / 111-3. Per-frame diagnostics
    (frames with more than 64 fragments, frames with insufficient depth support under mesh and under sensor depth, the
    sensor depth's valid share and the median mesh-minus-sensor difference) go into the receipt, reported only.
    ``--purpose sample`` converts only the sample scene's pairs into a root ending in ``-sample`` and may take the slot
    values from ``--slots-from`` (for this purpose only); ``--purpose formal`` requires the contract's
    ``authorization.formal_conversion`` open, the four slots registered and a clean checkout, and takes values from the
    contract only.
  * ``reader-check``: reads every converted frame back through the frozen readers -- ``read_public_frame`` and the S2-04
    frame-digest recomputation, ``instance_frame_masks`` and ``admit_proposals``, the geometry-table validation,
    ``EpisodeTruthTracker`` and ``TruthTableBuilder``, presence of the intervened objects before and after the window,
    and pose decoding (the converter commit is added to the pose registry in memory for this read only; the frozen
    contract is not changed). Any failure is recorded on that episode.
Resuming: succeeded episodes are kept; episodes without a receipt (interrupted) are cleared and redone; failed ones are
kept as they are and not redone. It trains nothing, runs no method and reads no test data.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import numpy as np  # noqa: E402

import s3_07_render as render_cli  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_s3_07_3rscan as r3  # noqa: E402
from vsmt import lean_s3_07_episode as ep  # noqa: E402
from vsmt import lean_s3_07_render as rr  # noqa: E402
from vsmt import lean_test_seal  # noqa: E402

STAGE = "vsmt.lean.s3_07.convert.v1"
SAMPLE_SUFFIX = "-sample"
THREAD_VARIABLES = render_cli.THREAD_VARIABLES


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_labels(path: Path, contract: dict[str, Any]) -> dict[str, int]:
    digest = sha256_file(path)
    if digest != contract["truth"]["label_mapping_sha256"]:
        raise r3.LeanS307Error("label_mapping_digest_mismatch:" + digest)
    return r3.parse_label_mapping(Path(path).read_text(encoding="utf-8"))


def scan_inputs(scans_root: Path, scan: str) -> dict[str, Any]:
    """What one scan contributes without rendering: semseg objects, _info, the pose texts by frame stem."""

    directory = Path(scans_root) / scan
    invalid: list[int] = []
    objects = r3.semseg_objects(json.loads((directory / "semseg.v2.json").read_text(encoding="utf-8")), invalid=invalid)
    mesh = rr.read_ply((directory / "labels.instances.annotated.v2.ply").read_bytes())
    with zipfile.ZipFile(directory / "sequence.zip") as archive:
        names = archive.namelist()
        info_name = [name for name in names if name.endswith("_info.txt")]
        if len(info_name) != 1:
            raise r3.LeanS307Error("sequence_info_missing_or_repeated:" + scan)
        prefix = info_name[0][:-len("_info.txt")]
        info = r3.parse_info(archive.read(info_name[0]).decode("utf-8"))
        stems = render_cli.frame_names(names)
        poses = {stem: r3.parse_pose(archive.read(f"{prefix}{stem}.pose.txt").decode("utf-8")) for stem in stems}
    return {"objects": objects, "info": info, "stems": stems, "poses": poses, "prefix": prefix, "mesh": mesh, "obb_invalid": invalid}


# --------------------------------------------------------------------------
# sample check
# --------------------------------------------------------------------------

def sample_check(scans_root: Path, meta: list[dict[str, Any]], labels: dict[str, int]) -> dict[str, Any]:
    scene_scans = render_cli.sample_scans(meta)
    reference = scene_scans[0]
    scene = r3.scene_entry(meta, reference)
    inputs = {scan: scan_inputs(scans_root, scan) for scan in scene_scans}
    vertices = {scan: ep.vertices_by_object(rr.read_ply((Path(scans_root) / scan / "labels.instances.annotated.v2.ply").read_bytes()))
                for scan in scene_scans}
    units, layouts, rolls = {}, {}, {}
    for scan in scene_scans[1:]:
        changes = r3.rescan_changes(scene, scan)
        listed = set(changes["removed"]) | set(changes["nonrigid"]) | {a for a, _b in changes["rigid"]} | set(changes["ambiguity"])
        structural = {oid for oid, row in inputs[reference]["objects"].items() if r3.is_structural(labels[row["label"]])}
        unchanged = sorted((set(inputs[reference]["objects"]) & set(inputs[scan]["objects"])) - listed - structural)
        units[scan] = ep.translation_unit_check(vertices[reference], vertices[scan], unchanged, changes["transform"])
    for scan in scene_scans:
        layouts[scan] = ep.obb_layout_check(inputs[scan]["objects"], vertices[scan])
        rolls[scan] = ep.roll_check([inputs[scan]["poses"][stem] for stem in inputs[scan]["stems"]])
    ambiguity = ep.ambiguity_structure_ok(scene for scene in meta if scene.get("type") == "validation")
    unit_choices = {result["chosen"] for result in units.values()}
    layout_choices = {result["chosen"] for result in layouts.values()}
    slots = {
        "alignment_translation_unit": unit_choices.pop() if len(unit_choices) == 1 and None not in unit_choices else None,
        "obb_axes_layout": layout_choices.pop() if len(layout_choices) == 1 and None not in layout_choices else None,
        "image_rotation_confirmed": True if all(result["passed"] for result in rolls.values()) else None,
        "ambiguity_structure_confirmed": True if ambiguity["passed"] else None,
    }
    return {"stage": STAGE + ".sample_check", "sample_scans": scene_scans, "translation_unit": units, "obb_layout": layouts,
            "rotation": rolls, "ambiguity": ambiguity, "slots": slots,
            "rules": {"unit_maximum_median_m": ep.UNIT_CHECK_MAXIMUM_M, "obb_containment_minimum": ep.OBB_CONTAINMENT_MINIMUM,
                      "obb_tolerance_m": ep.OBB_CONTAINMENT_TOLERANCE_M, "roll": "clockwise median >= cos 45 deg and the largest",
                      "distance_sample_per_object": ep.DISTANCE_SAMPLE},
            "stopped": sorted(name for name, value in slots.items() if value is None)}


# --------------------------------------------------------------------------
# conversion
# --------------------------------------------------------------------------

def frozen_geometry() -> Any:
    import lean_s1_03_cache as cache_runner

    return cache_runner.geometry_config(cache_runner.frozen_frontend())


def load_render(render_root: Path, scan: str, stems: list[str]) -> dict[str, Any]:
    receipt = json.loads((Path(render_root) / scan / "receipt.json").read_text(encoding="utf-8"))
    if receipt.get("status") != "succeeded":
        raise r3.LeanS307Error("render_not_succeeded:" + scan)
    rule = receipt["render_rule"]
    if (rule["label_rule"], rule["coverage_rule"], rule["raster_near_m"]) != (rr.LABEL_RULE, rr.COVERAGE_RULE, rr.RASTER_NEAR_M):
        raise r3.LeanS307Error("render_rule_differs:" + scan)
    if [row["frame"] for row in receipt["per_frame"]] != stems:
        raise r3.LeanS307Error("render_frames_differ:" + scan)
    return receipt


def convert_pair(task: dict[str, Any]) -> dict[str, Any]:
    """One worker, one pair: every frame of both scans written to the three planes, the geometry table, and the receipt last."""

    from PIL import Image

    started = time.time()
    reference, rescan = task["reference"], task["rescan"]
    episode_id = r3.episode_id(reference, rescan)
    out_dir = Path(task["out_root"]) / episode_id
    receipt: dict[str, Any] = {"house_id": reference, "source_index": int(task["source_index"]), "code_commit": task["commit"],
                               "episode_id": episode_id, "stage": STAGE, "purpose": task["purpose"],
                               "contract_sha256": task["contract_sha256"], "slots": task["slots"], "slots_source": task["slots_source"]}
    try:
        meta_scene = task["scene"]
        labels = task["labels"]
        geometry = frozen_geometry()
        inputs = {scan: scan_inputs(Path(task["scans_root"]), scan) for scan in (reference, rescan)}
        plan = ep.plan_pair(meta_scene, rescan, inputs[reference]["objects"], inputs[rescan]["objects"], labels,
                            unit=task["slots"]["alignment_translation_unit"], layout=task["slots"]["obb_axes_layout"],
                            reference_mesh=inputs[reference]["mesh"], rescan_mesh=inputs[rescan]["mesh"])
        renders = {scan: load_render(Path(task["render_root"]), scan, inputs[scan]["stems"]) for scan in (reference, rescan)}
        public, private, provenance = out_dir / "public", out_dir / "private", out_dir / "provenance"
        for directory in (public, private, provenance):
            directory.mkdir(parents=True, exist_ok=False)
        keys = plan["keys"]
        side = {reference: {"key_of_label": keys["reference"], "boxes": plan["box_reference"], "alignment": None},
                rescan: {"key_of_label": keys["rescan"], "boxes": plan["box_rescan"], "alignment": plan["alignment"]}}
        first_pose = inputs[reference]["poses"][inputs[reference]["stems"][0]]
        _rotation0, origin, _residual0 = r3.camera_pose(first_pose)
        index = 0
        residual_max = 0.0
        diagnostics: list[dict[str, Any]] = []
        unknown_pixels = 0
        fov: dict[str, float] = {}
        digests: list[str] = []
        for scan in (reference, rescan):
            info = inputs[scan]["info"]
            target = r3.target_intrinsics(info["color_intrinsics"], info["color_size_wh"])
            fov[scan] = round(2 * np.degrees(np.arctan(112.0 / target["fy"])), 3)
            key_of_label = side[scan]["key_of_label"]
            position_of_key = {key_of_label[oid]: box["centroid_m"] for oid, box in side[scan]["boxes"].items()}
            per_frame = {row["frame"]: row for row in renders[scan]["per_frame"]}
            with zipfile.ZipFile(Path(task["scans_root"]) / scan / "sequence.zip") as archive:
                prefix = inputs[scan]["prefix"]
                for stem in inputs[scan]["stems"]:
                    rgb = r3.upright_rgb(np.asarray(Image.open(io.BytesIO(archive.read(f"{prefix}{stem}.color.jpg"))).convert("RGB")))
                    depth = np.load(Path(task["render_root"]) / scan / f"{stem}.depth.npy")
                    instance = np.asarray(Image.open(Path(task["render_root"]) / scan / f"{stem}.instance.png"))
                    if (render_cli.sha256_bytes(depth.tobytes()) != per_frame[stem]["depth_sha256"]
                            or render_cli.sha256_bytes(instance.tobytes()) != per_frame[stem]["instance_sha256"]):
                        raise r3.LeanS307Error(f"render_digest_mismatch:{scan}:{stem}")
                    rotation, position, residual = r3.camera_pose(inputs[scan]["poses"][stem], alignment=side[scan]["alignment"])
                    residual_max = max(residual_max, residual)
                    record = ep.public_record(index, rgb, depth, intrinsics=target,
                                              relative_pose=r3.relative_pose(rotation, position, origin))
                    Image.fromarray(rgb).save(public / record["rgb_path"])
                    np.save(public / record["depth_path"], depth)
                    (public / f"{index:04d}.frame.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
                    private_record, unknown = ep.private_record(index, instance, key_of_label=key_of_label,
                                                                position_of_key=position_of_key, frame_digest=record["frame_digest"])
                    Image.fromarray(instance).save(private / private_record["instance_mask_path"])
                    (private / f"{index:04d}.frame.json").write_text(json.dumps(private_record) + "\n", encoding="utf-8")
                    unknown_pixels += sum(unknown.values())
                    sensor = r3.sensor_depth_on_target(np.asarray(Image.open(io.BytesIO(archive.read(f"{prefix}{stem}.depth.pgm")))),
                                                       depth_shift=info["depth_shift"], depth_intrinsics=info["depth_intrinsics"],
                                                       color_intrinsics=info["color_intrinsics"], color_size_wh=info["color_size_wh"])
                    diagnostics.append(ep.frame_diagnostics(instance, depth, sensor,
                                                            labels=private_record["object_id_to_entity_id"].values(), geometry=geometry))
                    digests.append(record["frame_digest"])
                    index += 1
        n_reference = len(inputs[reference]["stems"])
        window = ep.window_record(n_reference)
        (provenance / "window_verdicts.json").write_text(json.dumps(window, indent=1), encoding="utf-8")
        classified = plan["classified"]
        (provenance / "interventions.json").write_text(json.dumps({
            "executed": plan["interventions"], "outcomes": classified["outcomes"], "counts": classified["counts"],
            "rescan_id_of": classified["rescan_id_of"], "label_changed": keys["label_changed"],
            "residual_annotations": classified["residual_annotations"], "coverage": plan["coverage"],
            "obb_invalid": {"reference": inputs[reference]["obb_invalid"], "rescan": inputs[rescan]["obb_invalid"]},
            "changes": {key: plan["changes"][key] for key in ("removed", "nonrigid", "rigid", "ambiguity")}}, indent=1),
            encoding="utf-8")
        table = ep.geometry_table(episode_id=episode_id, house_id=reference, source_index=int(task["source_index"]),
                                  code_commit=task["commit"], origin_world_m=origin, rows=plan["table_rows"])
        geometry_dir = Path(task["geometry_root"]) / episode_id
        geometry_dir.mkdir(parents=True, exist_ok=True)
        (geometry_dir / og.TABLE_FILE_NAME).write_text(json.dumps(table, indent=1), encoding="utf-8")
        sensor_shares = [row["sensor_valid_share"] for row in diagnostics]
        medians = [row["mesh_minus_sensor_median_m"] for row in diagnostics if row["mesh_minus_sensor_median_m"] is not None]
        kinds: dict[str, int] = {}
        for row in plan["interventions"]:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        receipt.update({
            "status": "succeeded", "observations": index, "reference_scan": reference, "rescan": rescan,
            "frames_reference": n_reference, "frames_rescan": index - n_reference, "window": window["window"],
            "interventions": kinds, "change_outcomes": classified["counts"], "label_changed": len(keys["label_changed"]),
            "residual_annotations": classified["residual_annotations"],
            "obb_invalid": len(inputs[reference]["obb_invalid"]) + len(inputs[rescan]["obb_invalid"]),
            "not_covered_objects": sum(1 for v in (plan["coverage"] or {}).values() if not v),
            "unknown_label_pixels": int(unknown_pixels), "vertical_fov_deg": fov, "orthonormality_residual_max": residual_max,
            "geometry_objects": len(table["objects"]), "frame_digests_sha256": hashlib.sha256("".join(digests).encode()).hexdigest(),
            "diagnostics": {
                "frames_over_64_regions": sum(1 for row in diagnostics if row["over_cap"]),
                "frames_with_mesh_support_failure": sum(1 for row in diagnostics if row["mesh_support_failures"]),
                "frames_with_sensor_support_failure": sum(1 for row in diagnostics if row["sensor_support_failures"]),
                "regions_per_frame_max": max(row["regions"] for row in diagnostics),
                "sensor_valid_share_mean": float(np.mean(sensor_shares)),
                "mesh_minus_sensor_median_of_frame_medians_m": float(np.median(medians)) if medians else None}})
    except Exception as exc:  # noqa: BLE001 -- the pair's failure is recorded on it; nothing is replaced
        receipt.update({"status": "failed", "reason": type(exc).__name__ + ":" + str(exc)[:200], "detail": traceback.format_exc()[-800:]})
    receipt["wall_seconds"] = round(time.time() - started, 1)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return {key: receipt.get(key) for key in ("episode_id", "status", "observations", "reason", "wall_seconds")}


def plan_episodes(episode_ids: list[str], out_root: Path, *, resume: bool) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """(episodes to convert, receipts kept, interrupted episodes cleared): as the render entry's rule, read on episode receipts --
    succeeded and failed receipts are kept, a directory without a receipt is cleared and redone; without ``resume`` any existing
    episode directory refuses."""

    todo, kept, cleared = [], [], []
    for episode in episode_ids:
        directory = out_root / episode
        receipt = directory / "receipt.json"
        if directory.exists() and not resume:
            raise r3.LeanS307Error("output_exists_pass_resume:" + episode)
        if receipt.exists():
            data = json.loads(receipt.read_text(encoding="utf-8"))
            kept.append({key: data.get(key) for key in ("episode_id", "status", "observations", "reason", "wall_seconds")})
        elif directory.exists():
            shutil.rmtree(directory)
            cleared.append(episode)
            todo.append(episode)
        else:
            todo.append(episode)
    return todo, kept, cleared


def pairs_of(meta: list[dict[str, Any]], purpose: str) -> list[dict[str, Any]]:
    """(reference, rescan, scene, source index): the source index is the scene's place in the sorted validation list."""

    out = []
    scenes = render_cli.validation_scans(meta)
    chosen = scenes[:1] if purpose == "sample" else scenes
    for source_index, scans in enumerate(chosen):
        scene = r3.scene_entry(meta, scans[0])
        for rescan in scans[1:]:
            out.append({"reference": scans[0], "rescan": rescan, "scene": scene, "source_index": source_index})
    return out


def cmd_convert(args: argparse.Namespace) -> int:
    refusal = lean_test_seal.refusal([args.scans_root, args.render_root, args.out_root, args.geometry_root], reader="s3-07 convert")
    if refusal:
        print(f"{refusal}; refusing")
        return 2
    contract = r3.load_contract()
    rr.check_contract(contract)
    contract_sha = sha256_file(r3.CONTRACT_PATH)
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    labels = load_labels(Path(args.labels), contract)
    commit, dirty = render_cli.git_state()
    out_root, geometry_root = Path(args.out_root), Path(args.geometry_root)
    if args.purpose == "sample":
        if not (out_root.name.endswith(SAMPLE_SUFFIX) and geometry_root.name.endswith(SAMPLE_SUFFIX)):
            print(f"a sample conversion writes to roots ending in {SAMPLE_SUFFIX}; refusing")
            return 2
        if args.slots_from:
            report = json.loads(Path(args.slots_from).read_text(encoding="utf-8"))
            slots, source = dict(report["slots"]), "sample_check_report:" + sha256_file(Path(args.slots_from))
        else:
            slots, source = dict(contract["sample_check"]), "contract"
    else:
        if args.slots_from:
            print("--slots-from is for a sample conversion only; refusing")
            return 2
        if r3.blocking_null_slots(contract) or not contract["authorization"]["formal_conversion"] or dirty:
            print(f"formal conversion is not open (authorization {contract['authorization']['formal_conversion']}, null slots "
                  f"{r3.blocking_null_slots(contract)}, {dirty} uncommitted change(s)); refusing")
            return 2
        if out_root.name.endswith(SAMPLE_SUFFIX) or geometry_root.name.endswith(SAMPLE_SUFFIX):
            print(f"a formal conversion must not write to a {SAMPLE_SUFFIX} root; refusing")
            return 2
        slots, source = dict(contract["sample_check"]), "contract"
    missing = sorted(name for name, value in slots.items() if value is None)
    if missing:
        print(f"sample slots still null: {missing}; refusing")
        return 2
    if args.workers < 1:
        print("--workers must be at least 1; refusing")
        return 2
    pairs = pairs_of(meta, args.purpose)
    out_root.mkdir(parents=True, exist_ok=True)
    geometry_root.mkdir(parents=True, exist_ok=True)
    try:
        todo_ids, kept, cleared = plan_episodes([r3.episode_id(p["reference"], p["rescan"]) for p in pairs], out_root,
                                                resume=args.resume)
    except r3.LeanS307Error as exc:
        print(f"{exc}; refusing")
        return 2
    todo = [p for p in pairs if r3.episode_id(p["reference"], p["rescan"]) in set(todo_ids)]
    actual = min(args.workers, max(1, len(todo)))
    plan = {"stage": STAGE, "purpose": args.purpose, "code_commit": commit, "dirty_files": dirty, "contract_sha256": contract_sha,
            "slots": slots, "slots_source": source, "pairs": [r3.episode_id(p["reference"], p["rescan"]) for p in pairs],
            "todo": todo_ids, "kept": [row["episode_id"] for row in kept], "cleared_interrupted": cleared,
            "workers_requested": args.workers, "workers_actual": actual, "worker_basis": args.worker_basis,
            "render_root": str(args.render_root), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out_root / f"plan-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"[s3-07 convert] {args.purpose}: {len(todo)} pairs to convert, {len(kept)} kept, {len(cleared)} interrupted cleared, "
          f"{actual} workers (requested {args.workers}), slots from {source}, commit {commit[:12]}", flush=True)
    for name in THREAD_VARIABLES:
        os.environ[name] = "1"
    tasks = [{**p, "scans_root": str(args.scans_root), "render_root": str(args.render_root), "out_root": str(out_root),
              "geometry_root": str(geometry_root), "labels": labels, "slots": slots, "slots_source": source, "commit": commit,
              "contract_sha256": contract_sha, "purpose": args.purpose} for p in todo]
    results: list[dict[str, Any]] = list(kept)
    started = time.time()
    if tasks:
        with mp.get_context("spawn").Pool(processes=actual) as pool:
            for row in pool.imap_unordered(convert_pair, tasks, chunksize=1):
                results.append(row)
                print(f"[s3-07 convert] {len(results)}/{len(pairs)} {row['episode_id']} {row['status']} frames={row.get('observations')} "
                      f"{row.get('wall_seconds')}s {('reason=' + str(row.get('reason'))) if row['status'] != 'succeeded' else ''}",
                      flush=True)
    by_status: dict[str, int] = {}
    for row in results:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    summary = {**plan, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "wall_seconds": round(time.time() - started, 1),
               "by_status": by_status, "results": sorted(results, key=lambda row: row["episode_id"])}
    (out_root / "convert_receipt.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"[s3-07 convert] done: {by_status}", flush=True)
    return 0 if by_status.get("succeeded", 0) == len(pairs) else 1


# --------------------------------------------------------------------------
# reader check
# --------------------------------------------------------------------------

def reader_check_episode(episode_root: Path, geometry_root: Path) -> dict[str, Any]:
    """The frozen readers on one converted episode, frame by frame; the first refusal is recorded."""

    import lean_s1_03_cache as cache_runner
    import lean_s1_04_diagnostics as diag
    import lean_s2_04_evaluate_episode as s204
    from vsmt import lean_frontend_cache as fc
    from vsmt import lean_public_pose as pp
    from vsmt import lean_runner as lr
    from vsmt.l1_entities import _camera_values

    episode_root = Path(episode_root)
    receipt = json.loads((episode_root / "receipt.json").read_text(encoding="utf-8"))
    out: dict[str, Any] = {"episode_id": episode_root.name, "frames": 0, "passed": False, "failure": None}
    if receipt.get("status") != "succeeded":
        out["failure"] = "conversion_not_succeeded"
        return out
    try:
        policy = copy.deepcopy(json.loads(cache_runner.CONTRACT_PATH.read_text(encoding="utf-8"))["public_pose_correction"])
        policy["correct_encoder_since_code_commits"] = list(policy["correct_encoder_since_code_commits"]) + [receipt["code_commit"]]
        table = og.validate_geometry_table(json.loads((Path(geometry_root) / episode_root.name / og.TABLE_FILE_NAME).read_text(encoding="utf-8")))
        executed, window = diag.cache_runner_read_interventions(episode_root / "provenance")
        tracker = og.EpisodeTruthTracker(table, executed_interventions=executed, window=window)
        builder = lr.TruthTableBuilder()
        public, private = episode_root / "public", episode_root / "private"
        frames = len(list(public.glob("*.frame.json")))
        regions_max = 0
        intervened = {row["object_id"]: row["kind"] for row in executed}
        for index in range(frames):
            frame = cache_runner.read_public_frame(public, index)
            record = frame["record"]
            if frame["rgb"].shape != (224, 224, 3) or frame["depth"].shape != (224, 224):
                raise r3.LeanS307Error(f"frame_shape:{index}")
            if s204.recomputed_frame_digest(public, record, np.load(public / record["depth_path"])) != record["frame_digest"]:
                raise r3.LeanS307Error(f"frame_digest:{index}")
            pose = pp.public_camera_pose(record, code_commit=receipt["code_commit"], policy=policy)
            _camera_values(record["intrinsics"], pose)
            masks = cache_runner.instance_frame_masks(private, index, record, (224, 224))
            admitted = fc.admit_proposals([cache_runner.anonymous(mask, k) for k, mask in enumerate(masks)])
            regions_max = max(regions_max, len(admitted))
            private_record = json.loads((private / f"{index:04d}.frame.json").read_text(encoding="utf-8"))
            truth = tracker.update(index, private_record)
            builder.update(private_record, truth)
            if window is not None and index in (window[1], window[1] + 1):
                for key, kind in intervened.items():
                    if index == window[1] or kind != "remove":
                        if not truth[key]["present"]:
                            raise r3.LeanS307Error(f"intervened_object_absent:{key}:{index}")
            out["frames"] = index + 1
        out.update({"passed": True, "regions_per_frame_max": regions_max, "geometry_objects": len(table["objects"]),
                    "interventions": len(executed), "window": window})
    except Exception as exc:  # noqa: BLE001 -- the refusal is the finding
        out["failure"] = type(exc).__name__ + ":" + str(exc)[:200]
    return out


def cmd_reader_check(args: argparse.Namespace) -> int:
    refusal = lean_test_seal.refusal([args.out_root, args.geometry_root], reader="s3-07 reader-check")
    if refusal:
        print(f"{refusal}; refusing")
        return 2
    episodes = sorted(path for path in Path(args.out_root).iterdir() if path.is_dir() and path.name.startswith(r3.EPISODE_PREFIX))
    rows = [reader_check_episode(path, Path(args.geometry_root)) for path in episodes]
    report = {"stage": STAGE + ".reader_check", "code_commit": render_cli.git_state()[0], "episodes": rows,
              "passed": sum(1 for row in rows if row["passed"]), "failed": [row["episode_id"] for row in rows if not row["passed"]]}
    Path(args.report).write_text(json.dumps(report, indent=1), encoding="utf-8")
    for row in rows:
        print(f"[s3-07 reader-check] {row['episode_id']} frames={row['frames']} passed={row['passed']} "
              f"{('failure=' + str(row['failure'])) if not row['passed'] else ''}", flush=True)
    return 0 if rows and not report["failed"] else 1


def cmd_sample_check(args: argparse.Namespace) -> int:
    refusal = lean_test_seal.refusal([args.scans_root], reader="s3-07 sample-check")
    if refusal:
        print(f"{refusal}; refusing")
        return 2
    contract = r3.load_contract()
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    labels = load_labels(Path(args.labels), contract)
    report = sample_check(Path(args.scans_root), meta, labels)
    report.update({"code_commit": render_cli.git_state()[0], "contract_sha256": sha256_file(r3.CONTRACT_PATH),
                   "meta_sha256": sha256_file(Path(args.meta))})
    Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({"slots": report["slots"], "stopped": report["stopped"]}))
    return 0 if not report["stopped"] else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("sample-check")
    for name in ("--scans-root", "--meta", "--labels", "--out"):
        check.add_argument(name, required=True)
    convert = sub.add_parser("convert")
    for name in ("--scans-root", "--meta", "--labels", "--render-root", "--out-root", "--geometry-root"):
        convert.add_argument(name, required=True)
    convert.add_argument("--purpose", choices=("sample", "formal"), required=True)
    convert.add_argument("--workers", type=int, required=True)
    convert.add_argument("--worker-basis", default="")
    convert.add_argument("--slots-from", default=None)
    convert.add_argument("--resume", action="store_true")
    reader = sub.add_parser("reader-check")
    for name in ("--out-root", "--geometry-root", "--report"):
        reader.add_argument(name, required=True)
    args = parser.parse_args(argv)
    if args.command == "sample-check":
        return cmd_sample_check(args)
    if args.command == "convert":
        return cmd_convert(args)
    return cmd_reader_check(args)


if __name__ == "__main__":
    sys.exit(main())
