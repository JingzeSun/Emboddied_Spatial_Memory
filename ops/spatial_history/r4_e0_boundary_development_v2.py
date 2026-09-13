"""D-120: fixed E0-v2 audit over 50 already sealed development families.

All v1/v2 predictions are produced from manifest-bound public histories and
sealed before family results, XML, snapshots, or segmentation are opened.
This stage never completes data generation and never supplies an M input.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import importlib
import json
import os
from pathlib import Path
try:
    import resource
except ImportError:
    resource = None
import signal
import subprocess
import sys
import time
import unittest


if os.name != "nt":
    os.environ.setdefault("MUJOCO_GL", "egl")
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tests/spatial_world_model")]
from spatial_world_model.pair_contract import require
from spatial_world_model.public_geometry_audit import assess_geometry, targets_from_xml
from spatial_world_model.public_geometry_v2 import recover_openings as recover_v2
from spatial_world_model.r4_public_v2 import validate_public
from spatial_world_model.r4_storage import file_record, inventory


CONFIG_PATH = "configs/spatial_history/r4_e0_boundary_development_v2.json"
CONFIG = json.loads((ROOT / CONFIG_PATH).read_text(encoding="utf-8"))
RUN = Path(CONFIG["run_directory"])
ENVIRONMENT = Path(CONFIG["environment"])
REPORT = ROOT / CONFIG["report"]
STAGE = "SH-05-R4-E0-boundary-development-v2"
TESTS = (
    "tests.spatial_world_model.test_public_geometry",
    "tests.spatial_world_model.test_public_geometry_v2",
    "tests.spatial_world_model.test_r4_e0_boundary_development_v2",
)
BOUND = (
    CONFIG_PATH,
    "configs/spatial_history/public_geometry_parallel_v1.json",
    "configs/spatial_history/public_geometry_boundary_v2.json",
    "configs/spatial_history/r4_family_design_v2.json",
    "configs/spatial_history/r4_development_generation_v2.json",
    "ops/spatial_history/r4_e0_boundary_development_v2.py",
    "src/spatial_world_model/public_geometry.py",
    "src/spatial_world_model/public_geometry_audit.py",
    "src/spatial_world_model/public_geometry_v2.py",
    "src/spatial_world_model/r4_physics_v2.py",
    "src/spatial_world_model/r4_public_v2.py",
    "tests/spatial_world_model/test_public_geometry.py",
    "tests/spatial_world_model/test_public_geometry_v2.py",
    "tests/spatial_world_model/test_r4_e0_boundary_development_v2.py",
    "docs/DECISIONS.md",
    "docs/METHOD.md",
    "docs/DATA.md",
)


def read(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def write(path, value):
    path = Path(path)
    raw = encode(value)
    if path.suffix == ".gz":
        raw = gzip.compress(raw, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
    return file_record(path)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def binding():
    return {name: file_record(ROOT / name) for name in BOUND}


def _safe_file(base, relative):
    base = Path(base).resolve(strict=True)
    path = (base / relative).resolve(strict=True)
    require(path.is_relative_to(base) and path.is_file() and not path.is_symlink(),
            "unsafe/missing source: " + relative)
    return path


def family_ids(config=None):
    config = CONFIG if config is None else config
    return (config["released_existing_family_ids"]
            + config["verified_generation_family_ids"]
            + list(config["e0_only_family_status"]))


def family_stage(family_id, config=None):
    config = CONFIG if config is None else config
    if family_id in config["released_existing_family_ids"]:
        return Path(config["source_stages"]["released_existing"])
    require(family_id in (config["verified_generation_family_ids"]
                          + list(config["e0_only_family_status"])),
            "family is outside fixed audit census")
    return Path(config["source_stages"]["stopped_generation"])


def mode_indices(design_row):
    views = design_row["camera"]["view_frame_indices"]
    return {"full": list(range(121)), "view_a": [views["A"]],
            "view_b": [views["B"]], "recent": [119, 120]}


def configuration():
    config = read(ROOT / CONFIG_PATH)
    require(config["version"] == "sh05-r4-e0-boundary-development-v2", "wrong version")
    require(config["status"] == "authorized_fixed_sealed_development_audit"
            and config["development_audit_authorized"] is True, "audit not authorized")
    require(all(config[name] is False for name in (
        "e0_frontend_upgrade_authorized", "dual_m_authorized", "data_completion_authorized",
        "training_authorized", "confirmation_authorized")), "downstream authority changed")
    generation = read(ROOT / config["generation_config"])
    design = read(ROOT / config["design"])
    rows = {row["family_id"]: row for row in design["rows"]}
    excluded = config["excluded_unsealed_family_ids"]
    expected = generation["existing_family_ids"] + [
        item for item in generation["new_family_ids"] if item not in excluded]
    actual = family_ids(config)
    require(len(actual) == len(set(actual)) == config["expected_family_count"] == 50,
            "family census count/uniqueness changed")
    require(set(actual) == set(expected), "sealed family census changed")
    require(excluded == ["r4-23", "r4-58"]
            and not set(excluded).intersection(actual), "unsealed exclusion changed")
    require(config["e0_only_family_status"] == {
        "r4-22": "family_accepted_but_terminal_verify_cancelled",
        "r4-36": "family_rejected_only_by_e0_v1",
    }, "E0-only status changed")
    counts = Counter(rows[item]["split"] for item in actual)
    require(dict(counts) == config["expected_split_counts"], "split census changed")
    require(config["worlds"] == ["LL", "LR", "RL", "RR"]
            and list(config["modes"]) == ["full", "view_a", "view_b", "recent"],
            "world/mode census changed")
    acceptance = config["acceptance"]
    require(acceptance == {
        "expected_case_count": 800,
        "expected_v1_accepted_cases": 796,
        "expected_v1_failed_cases": 4,
        "all_v1_predictions_reproduce_sealed_outputs": True,
        "all_v2_cases_accepted": True,
        "all_v1_accepted_cases_remain_accepted": True,
        "all_v1_failed_cases_resolved_by_boundary_support": True,
        "all_no_boundary_v1_success_geometry_exactly_preserved": True,
        "all_boundary_pixels_registered_gate_walls": True,
        "boundary_pixel_body_hits": 0,
        "maximum_coordinate_interval_width_m": 0.025,
        "private_truth_only_after_public_seal": True,
    }, "acceptance changed")
    require(len(actual) * len(config["worlds"]) * len(config["modes"])
            == acceptance["expected_case_count"], "case count changed")
    require(Path(config["run_directory"]) == RUN and Path(config["environment"]) == ENVIRONMENT,
            "runtime path changed")
    require(config["required_environment"]
            == {"MUJOCO_GL": "egl", "PYOPENGL_PLATFORM": "egl"},
            "render environment changed")
    require(ROOT / config["report"] == REPORT, "report path changed")
    return config, rows


def require_environment():
    require(os.name != "nt" and resource is not None, "server Linux environment required")
    require(Path(sys.prefix).resolve() == ENVIRONMENT.resolve(), "wrong environment")
    require(all(os.environ.get(name) == value
                for name, value in CONFIG["required_environment"].items()),
            "registered EGL environment is not active")
    import mujoco
    import numpy
    require((mujoco.__version__, numpy.__version__) == ("3.3.7", "2.2.6"),
            "registered MuJoCo/Numpy versions changed")
    return {"python_prefix": sys.prefix, "mujoco": mujoco.__version__, "numpy": numpy.__version__}


def _bounded_runtime(seconds):
    resource.setrlimit(resource.RLIMIT_AS, (CONFIG["limits"]["process_as_bytes"],
                                           CONFIG["limits"]["process_as_bytes"]))
    def timeout(signum, frame):
        raise TimeoutError(f"{seconds} s E0-v2 development audit limit")
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(seconds)


def public_census():
    config, _ = configuration()
    result = {}
    for family_id in family_ids(config):
        data = (family_stage(family_id, config) / family_id / "data").resolve(strict=True)
        require(data.is_dir() and not data.is_symlink(), "unsafe family data directory")
        manifest_path = _safe_file(data, "public_manifest.json")
        manifest = read(manifest_path)
        require(set(manifest) == {f"{world}.json.gz" for world in config["worlds"]},
                "public family inventory changed: " + family_id)
        require(manifest == inventory(data / "public"),
                "public manifest mismatch: " + family_id)
        result[family_id] = {"data_directory": str(data),
                             "manifest": file_record(manifest_path), "records": manifest}
    return result


def check():
    config, _ = configuration()
    require_environment()
    require(not RUN.exists(), "audit directory exists; verify/export only")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed")
    _bounded_runtime(config["limits"]["check_wall_s"])
    began = time.monotonic()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name))
                               for name in TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    require(result.wasSuccessful() and not result.skipped and not result.expectedFailures,
            "E0-v2 development checks failed")
    sources = public_census()
    RUN.mkdir(parents=True)
    write(RUN / "check_receipt.json", {
        "stage": STAGE, "exit_code": 0, "commit": git("rev-parse", "HEAD"),
        "binding": binding(), "environment": require_environment(),
        "tests_run": result.testsRun, "elapsed_s": time.monotonic() - began,
        "source_public_census": sources,
    })
    print(f"{STAGE} CHECKED tests={result.testsRun} families={len(sources)} exit=0", flush=True)


def verify_check():
    receipt = read(RUN / "check_receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "invalid check receipt")
    require(receipt["binding"] == binding(), "binding changed after check")
    require(receipt["environment"] == require_environment(), "environment changed")
    require(receipt["source_public_census"] == public_census(), "source public census changed")
    return receipt


def _source_public(family_id, world, census):
    entry = census[family_id]
    path = _safe_file(entry["data_directory"], f"public/{world}.json.gz")
    require(file_record(path) == entry["records"][f"{world}.json.gz"],
            "source public record changed")
    return path


def _public_phase(execution, check_receipt, design_rows):
    from spatial_world_model.public_geometry import recover_openings as recover_v1
    e0_v1, e0_v2 = read(ROOT / CONFIG["e0_v1"]), read(ROOT / CONFIG["e0_v2"])
    census = check_receipt["source_public_census"]
    records = {}
    for family_id in family_ids():
        indices = mode_indices(design_rows[family_id])
        for world in CONFIG["worlds"]:
            source_path = _source_public(family_id, world, census)
            public = read(source_path)
            validate_public(public)
            for mode, selected in indices.items():
                observations = [public["history"][index] for index in selected]
                value = {
                    "family_id": family_id, "split": design_rows[family_id]["split"],
                    "world": world, "mode": mode, "source_frame_indices": selected,
                    "source_public_record": file_record(source_path),
                    "v1_prediction": recover_v1(observations, e0_v1["public_sensor_spec"],
                                                e0_v1["extractor"]),
                    "v2_prediction": recover_v2(observations, e0_v2["public_sensor_spec"],
                                                e0_v2["extractor"]),
                }
                name = f"{family_id}-{world}-{mode}"
                records[name] = write(execution / "public" / f"{name}.json.gz", value)
        print(f"{family_id} PUBLIC cases={len(CONFIG['worlds']) * len(indices)}", flush=True)
    seal = {"stage": STAGE, "records": records, "public_complete": True,
            "family_count": len(family_ids()), "case_count": len(records),
            "new_public_renders": 0, "private_files_read_during_public_phase": False,
            "source_public_census": census}
    write(execution / "public_seal.json", seal)
    return seal


def _candidate_for_v1_audit(candidate):
    value = deepcopy(candidate)
    for support in value["support"]:
        support.pop("boundary_compatible_pixels", None)
        support.pop("transition_kind", None)
    return value


def v1_audit_view(prediction):
    rejected = prediction["rejected_counts"]
    return {
        "schema_version": "public-openings-v1",
        "candidates": [_candidate_for_v1_audit(item) for item in prediction["candidates"]],
        "conflicts": [{"reason": item["reason"],
                       "members": [_candidate_for_v1_audit(member) for member in item["members"]]}
                      for item in prediction["conflicts"]],
        "incomplete_observations": deepcopy(prediction["incomplete_observations"]),
        "rejected_counts": {
            "zero_depth_pixels": rejected["zero_depth_pixels"],
            "clipped_depth_pixels": rejected["clipped_depth_pixels"],
            "insufficient_side_run_pairs": rejected["insufficient_side_run_pairs"],
            "invalid_gap_pairs": rejected["invalid_gap_pairs"],
            "nonfarther_gap_pairs": (rejected["nonboundary_gap_pairs"]
                                     + rejected["gap_without_strict_farther_pairs"]),
            "insufficient_row_groups": rejected["insufficient_row_groups"],
            "insufficient_side_patch_groups": rejected["insufficient_side_patch_groups"],
            "missing_front_groups": rejected["missing_front_groups"],
            "incompatible_boundary_groups": rejected["incompatible_boundary_groups"],
        },
        "history_frames": prediction["history_frames"],
    }


def geometry_signature(prediction):
    return {"candidates": [_candidate_for_v1_audit(item) for item in prediction["candidates"]],
            "conflicts": [{"reason": item["reason"],
                           "members": [_candidate_for_v1_audit(member) for member in item["members"]]}
                          for item in prediction["conflicts"]]}


def boundary_support(prediction, source_indices):
    rows = []
    for candidate_index, candidate in enumerate(prediction["candidates"]):
        for support_index, support in enumerate(candidate["support"]):
            local = support["local_frame_index"]
            require(type(local) is int and 0 <= local < len(source_indices),
                    "boundary support frame outside mode")
            for pixel in support["boundary_compatible_pixels"]:
                rows.append({"candidate_index": candidate_index, "support_index": support_index,
                             "local_frame_index": local,
                             "source_frame_index": source_indices[local],
                             "boundary_kind": support["boundary_kind"], "pixel": list(pixel),
                             "plane_height_interval_m": support["plane_height_interval_m"]})
    return rows


def _geom_names(scene, segmentation):
    import mujoco
    result = []
    for object_id, object_type in segmentation.reshape(-1, 2):
        if int(object_type) == int(mujoco.mjtObj.mjOBJ_GEOM) and int(object_id) >= 0:
            result.append(scene.model.geom(int(object_id)).name)
        else:
            result.append(None)
    return result


def _prefix_rows(path, needed):
    rows = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            if value["frame_index"] in needed:
                rows[value["frame_index"]] = value
    require(set(rows) == set(needed), "private prefix lacks a boundary support frame")
    return rows


def _source_status(family_id, data):
    result = read(_safe_file(data, "audit/family_result.json"))
    if family_id == "r4-36":
        require(result["accepted"] is False and result["failed_checks"] == ["public_geometry"],
                "r4-36 source status changed")
        return "e0_only_v1_rejected"
    require(result["accepted"] is True and result["failed_checks"] == [],
            "accepted source family status changed")
    if family_id == "r4-22":
        require(not (data.parent / "verified.json").exists(), "r4-22 terminal status changed")
        return "e0_only_accepted_unverified"
    if family_id in CONFIG["verified_generation_family_ids"]:
        verified = read(_safe_file(data.parent, "verified.json"))
        require(verified["family_id"] == family_id and verified["accepted"] is True,
                "generation family verification changed")
        return "verified_generation"
    return "released_existing"


def _audit_world(data, family_id, world, public, case_values, config):
    import numpy as np
    from spatial_world_model.r4_physics_v2 import R4SceneV2
    needed = {item["source_frame_index"] for value in case_values
              for item in boundary_support(value["v2_prediction"], value["source_frame_indices"])}
    if not needed:
        return {}, 0
    prefix = _prefix_rows(_safe_file(data, f"audit/{world}/history_prefix.jsonl.gz"), needed)
    xml = _safe_file(data, f"audit/{world}/world.xml").read_text(encoding="utf-8")
    scene = R4SceneV2(xml, config)
    names, renders = {}, 0
    try:
        for index in sorted(needed):
            private = prefix[index]
            require(private["observation"] == public["history"][index],
                    "public/private history observation mismatch")
            scene.restore(private["snapshot"], scene.digest(private["snapshot"]))
            before = scene.state().copy()
            observation = scene.observe()
            require(observation == private["observation"], "private RGBD rerender differs")
            segmentation = scene.render("segmentation")
            require(np.array_equal(before, scene.state()), "private render changed integration state")
            names[index] = _geom_names(scene, segmentation)
            renders += 1
    finally:
        scene.close()
    return names, renders


def _private_phase(execution, seal, design_rows):
    e0_v1 = read(ROOT / CONFIG["e0_v1"])
    rows, private_renders = [], 0
    for family_id in family_ids():
        data = Path(seal["source_public_census"][family_id]["data_directory"])
        status = _source_status(family_id, data)
        family_config = read(_safe_file(data, "audit/config.json"))
        require(family_config["observation"]["fixed_view_frame_indices"]
                == design_rows[family_id]["camera"]["view_frame_indices"],
                "registered view indices changed")
        geometry_seal = read(_safe_file(data, "audit/geometry/public_seal.json"))
        for world in CONFIG["worlds"]:
            public = read(_source_public(family_id, world, seal["source_public_census"]))
            case_values = []
            for mode in CONFIG["modes"]:
                name = f"{family_id}-{world}-{mode}"
                path = execution / "public" / f"{name}.json.gz"
                require(file_record(path) == seal["records"][name], "public output seal changed")
                case_values.append(read(path))
            geom_names, render_count = _audit_world(
                data, family_id, world, public, case_values, family_config)
            private_renders += render_count
            targets = targets_from_xml(
                _safe_file(data, f"audit/{world}/world.xml").read_text(encoding="utf-8"))
            for value in case_values:
                mode = value["mode"]
                original_record = geometry_seal["predictions"][f"{world}-{mode}"]
                original_path = _safe_file(data, "audit/geometry/" + original_record["file"])
                require(file_record(original_path) == {key: original_record[key]
                                                        for key in ("bytes", "sha256")},
                        "sealed original v1 prediction changed")
                original = read(original_path)
                reproduced = value["v1_prediction"] == original
                subset = targets if mode == "full" else (
                    [] if mode == "recent" else [targets[0 if mode == "view_a" else 1]])
                v1_assessment = assess_geometry(value["v1_prediction"], subset,
                                                e0_v1["evaluation_only"])
                v2_assessment = assess_geometry(v1_audit_view(value["v2_prediction"]), subset,
                                                e0_v1["evaluation_only"])
                boundary = boundary_support(value["v2_prediction"], value["source_frame_indices"])
                for item in boundary:
                    u, v = item["pixel"]
                    item["geom_name"] = geom_names[item["source_frame_index"]][
                        v * public["history"][item["source_frame_index"]]["width"] + u]
                    item["registered_gate_wall"] = item["geom_name"] in {
                        "gate_0_left", "gate_0_right", "gate_1_left", "gate_1_right"}
                no_boundary_exact = (bool(boundary) or not v1_assessment["accepted"]
                                     or geometry_signature(value["v2_prediction"])
                                     == geometry_signature(value["v1_prediction"]))
                rows.append({
                    "family_id": family_id, "source_status": status,
                    "split": value["split"], "world": world, "mode": mode,
                    "source_frame_indices": value["source_frame_indices"],
                    "v1_prediction_reproduced": reproduced,
                    "v1_assessment": v1_assessment, "v2_assessment": v2_assessment,
                    "v2_boundary_support": boundary,
                    "no_boundary_v1_success_geometry_exactly_preserved": no_boundary_exact,
                })
        print(f"{family_id} PRIVATE cases={len(CONFIG['worlds']) * len(CONFIG['modes'])}", flush=True)
    return rows, private_renders


def summarize(rows, private_renders):
    v1_pass = [row for row in rows if row["v1_assessment"]["accepted"]]
    v1_fail = [row for row in rows if not row["v1_assessment"]["accepted"]]
    boundary = [item for row in rows for item in row["v2_boundary_support"]]
    widths = [width for row in rows for match in row["v2_assessment"]["matches"]
              for width in match["coordinate_interval_width_m"]]
    names = Counter(item["geom_name"] for item in boundary)
    kinds = Counter(item["boundary_kind"] for item in boundary)
    body_hits = sum(item["geom_name"] in {"object", "pusher"} for item in boundary)
    conclusion = {
        "family_count": len({row["family_id"] for row in rows}),
        "case_count": len(rows),
        "case_counts_by_split": dict(Counter(row["split"] for row in rows)),
        "source_status_counts": dict(Counter(row["source_status"] for row in rows)),
        "v1_accepted_cases": len(v1_pass), "v1_failed_cases": len(v1_fail),
        "v1_failed_case_ids": [f"{row['family_id']}-{row['world']}-{row['mode']}" for row in v1_fail],
        "v2_accepted_cases": sum(row["v2_assessment"]["accepted"] for row in rows),
        "all_v1_predictions_reproduce_sealed_outputs": all(
            row["v1_prediction_reproduced"] for row in rows),
        "all_v2_cases_accepted": all(row["v2_assessment"]["accepted"] for row in rows),
        "all_v1_accepted_cases_remain_accepted": all(
            row["v2_assessment"]["accepted"] for row in v1_pass),
        "all_v1_failed_cases_resolved_by_boundary_support": all(
            row["v2_assessment"]["accepted"] and bool(row["v2_boundary_support"])
            for row in v1_fail),
        "all_no_boundary_v1_success_geometry_exactly_preserved": all(
            row["no_boundary_v1_success_geometry_exactly_preserved"] for row in v1_pass),
        "boundary_support_pixel_count": len(boundary),
        "boundary_support_geom_names": dict(names), "boundary_support_kinds": dict(kinds),
        "all_boundary_pixels_registered_gate_walls": all(
            item["registered_gate_wall"] for item in boundary),
        "boundary_pixel_body_hits": body_hits,
        "maximum_coordinate_interval_width_m": max(widths, default=0.0),
        "private_boundary_frame_renders": private_renders,
    }
    accepted = CONFIG["acceptance"]
    checks = {
        "family_census": conclusion["family_count"] == CONFIG["expected_family_count"],
        "case_census": conclusion["case_count"] == accepted["expected_case_count"],
        "v1_accepted_census": conclusion["v1_accepted_cases"] == accepted["expected_v1_accepted_cases"],
        "v1_failed_census": conclusion["v1_failed_cases"] == accepted["expected_v1_failed_cases"],
        "v1_reproduced": conclusion["all_v1_predictions_reproduce_sealed_outputs"],
        "all_v2_accepted": conclusion["all_v2_cases_accepted"],
        "v1_success_not_degraded": conclusion["all_v1_accepted_cases_remain_accepted"],
        "v1_failures_resolved_with_boundary": conclusion["all_v1_failed_cases_resolved_by_boundary_support"],
        "no_boundary_geometry_preserved": conclusion[
            "all_no_boundary_v1_success_geometry_exactly_preserved"],
        "boundary_pixels_are_registered_walls": conclusion[
            "all_boundary_pixels_registered_gate_walls"],
        "no_boundary_body_hits": conclusion["boundary_pixel_body_hits"]
        == accepted["boundary_pixel_body_hits"],
        "interval_widths_within_limit": conclusion["maximum_coordinate_interval_width_m"]
        <= accepted["maximum_coordinate_interval_width_m"],
    }
    return {"conclusion": conclusion, "checks": checks, "accepted": all(checks.values()),
            "failed_checks": [key for key, value in checks.items() if not value]}


def run():
    config, design_rows = configuration()
    require_environment()
    check_receipt = verify_check()
    execution = RUN / "execution"
    require(not execution.exists(), "audit execution exists; never overwrite")
    _bounded_runtime(config["limits"]["run_wall_s"])
    began = time.monotonic()
    execution.mkdir()
    try:
        write(execution / "started.json", {"stage": STAGE,
              "time_utc": datetime.now(timezone.utc).isoformat(),
              "family_count": len(family_ids())})
        seal = _public_phase(execution, check_receipt, design_rows)
        rows, private_renders = _private_phase(execution, seal, design_rows)
        summary = summarize(rows, private_renders)
        write(execution / "private_evaluation.json.gz", {"rows": rows})
        write(execution / "summary.json", summary)
        require(summary["accepted"], "fixed E0-v2 development acceptance failed: "
                + ",".join(summary["failed_checks"]))
        require(public_census() == check_receipt["source_public_census"],
                "source public census changed during run")
        outputs = inventory(execution)
        require(sum(item["bytes"] for item in outputs.values()) <= config["limits"]["stage_bytes"],
                "stage output limit exceeded")
        receipt = {
            "stage": STAGE, "exit_code": 0, "commit": check_receipt["commit"],
            "binding": binding(), "check_receipt": file_record(RUN / "check_receipt.json"),
            "source_public_census": check_receipt["source_public_census"],
            "outputs_before_receipt": outputs, "summary": summary,
            "source_public_families_reused": len(family_ids()), "new_public_renders": 0,
            "private_boundary_frame_renders": private_renders, "physics_steps": 0,
            "training_steps": 0, "confirmation_read": False,
            "elapsed_s": time.monotonic() - began,
        }
        write(execution / "run_receipt.json", receipt)
        print(f"{STAGE} RAN cases={len(rows)} accepted={summary['accepted']} exit=0", flush=True)
    except BaseException as error:
        failure = execution / "failure.json"
        if not failure.exists():
            write(failure, {"error": f"{type(error).__name__}: {error}",
                            "elapsed_s": time.monotonic() - began})
        raise


def verify():
    configuration()
    require_environment()
    check_receipt = verify_check()
    receipt = read(RUN / "execution/run_receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "invalid run receipt")
    require(receipt["commit"] == check_receipt["commit"] and receipt["binding"] == binding(),
            "run binding changed")
    current = inventory(RUN / "execution")
    current.pop("run_receipt.json")
    require(current == receipt["outputs_before_receipt"], "audit outputs changed")
    require(public_census() == receipt["source_public_census"], "source public census changed")
    summary = read(RUN / "execution/summary.json")
    require(summary == receipt["summary"] and summary["accepted"], "summary mismatch/failure")
    print(f"{STAGE} VERIFIED cases=800 accepted=True exit=0", flush=True)
    return receipt, summary


def export():
    receipt, summary = verify()
    require(not REPORT.exists(), "report exists; never overwrite")
    result = {
        "version": CONFIG["version"], "decision": CONFIG["decision"],
        "status": "passed_sealed_development_audit", "receipt": receipt,
        "summary": summary, "evaluation": read(RUN / "execution/private_evaluation.json.gz"),
        "claims": {
            "e0_v2_all_sealed_development_families_validated": True,
            "e0_v2_frontend_upgrade_authorized": False,
            "r4_22_training_family_ready": False,
            "r4_23_r4_58_completed": False,
            "dual_m_result": False, "training_result": False, "confirmation_result": False,
        },
    }
    raw = encode(result)
    require(len(raw) <= CONFIG["limits"]["report_bytes"], "report size limit exceeded")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("xb") as handle:
        handle.write(raw)
    record = file_record(REPORT)
    print(f"{STAGE} EXPORTED status=passed_sealed_development_audit bytes={record['bytes']} "
          f"sha256={record['sha256']} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "run", "verify", "export"))
    args = parser.parse_args()
    globals()[args.command]()


if __name__ == "__main__":
    main()
