"""D-118 audit E0-v2 on the already sealed D-116 phase observations.

The public phase reuses all 264 hash-bound RGBD observations and passes only an
observation to E0-v2.  XML, snapshots, segmentation, and targets are opened
only after the complete E0-v2 output seal.  This stage does not alter E0-v1,
render new public frames, step physics, rebuild data, or run a model.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import json
import math
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
from spatial_world_model.public_geometry_v2 import recover_openings
from spatial_world_model.r4_e0_pixel_phase import phase_fractions
from spatial_world_model.r4_storage import file_record


CONFIG_PATH = "configs/spatial_history/r4_e0_boundary_phase_v2.json"
CONFIG = json.loads((ROOT / CONFIG_PATH).read_text(encoding="utf-8"))
RUN = Path(CONFIG["run_directory"])
ENVIRONMENT = Path(CONFIG["environment"])
REPORT = ROOT / CONFIG["report"]
STAGE = "SH-05-R4-E0-boundary-phase-v2"
TESTS = (
    "tests.spatial_world_model.test_public_geometry",
    "tests.spatial_world_model.test_public_geometry_v2",
    "tests.spatial_world_model.test_r4_e0_pixel_phase",
    "tests.spatial_world_model.test_r4_e0_boundary_phase_v2",
)
BOUND = (
    CONFIG_PATH,
    "configs/spatial_history/public_geometry_boundary_v2.json",
    "ops/spatial_history/r4_e0_boundary_phase_v2.py",
    "src/spatial_world_model/public_geometry.py",
    "src/spatial_world_model/public_geometry_audit.py",
    "src/spatial_world_model/public_geometry_v2.py",
    "src/spatial_world_model/r4_e0_pixel_phase.py",
    "src/spatial_world_model/r4_physics_v2.py",
    "tests/spatial_world_model/test_public_geometry.py",
    "tests/spatial_world_model/test_public_geometry_v2.py",
    "tests/spatial_world_model/test_r4_e0_pixel_phase.py",
    "tests/spatial_world_model/test_r4_e0_boundary_phase_v2.py",
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


def inventory(root):
    root = Path(root)
    return {str(path.relative_to(root)).replace("\\", "/"): file_record(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def _case_name(world, gate, numerator):
    sign = "m" if numerator < 0 else "p"
    return f"{world}-g{gate}-{sign}{abs(numerator):02d}"


def configuration():
    config = read(ROOT / CONFIG_PATH)
    require(config["version"] == "sh05-r4-e0-boundary-phase-v2", "wrong version")
    require(config["status"] == "authorized_fixed_public_phase_audit"
            and config["phase_audit_authorized"] is True, "phase audit not authorized")
    require(all(config[name] is False for name in
                ("dual_m_authorized", "data_rebuild_authorized", "training_authorized",
                 "confirmation_authorized")), "phase audit cannot authorize downstream work")
    require(config["source_family"] == "r4-36"
            and config["worlds"] == ["LL", "LR", "RL", "RR"], "source census changed")
    require(config["gates"] == [{"gate_index": 0, "view_key": "A"},
                                 {"gate_index": 1, "view_key": "B"}], "gate census changed")
    sweep = config["phase_sweep"]
    phase_fractions(sweep["denominator"], sweep["numerators"])
    require(len(sweep["numerators"]) * len(config["worlds"]) * len(config["gates"])
            == sweep["source_public_frames"] == 264, "phase census changed")
    require(sweep["new_public_renders"] == 0 and sweep["private_audit_rerenders"] == 264,
            "render boundary changed")
    accepted = config["acceptance"]
    require(accepted == {
        "all_v2_cases_accepted": True,
        "expected_v1_accepted_cases": 262,
        "expected_v1_failed_cases": 2,
        "all_v1_accepted_geometry_exactly_preserved": True,
        "all_v1_failed_cases_resolved_by_boundary_support": True,
        "all_boundary_pixels_registered_gate_walls": True,
        "boundary_pixel_body_hits": 0,
        "maximum_coordinate_interval_width_m": 0.025,
        "private_truth_only_after_public_seal": True,
    }, "acceptance changed")
    require(Path(config["run_directory"]) == RUN and Path(config["environment"]) == ENVIRONMENT,
            "runtime path changed")
    require(config["failed_run_directory"]
            == "/root/autodl-tmp/spatial-history/sh05-r4-e0-boundary-phase-v2",
            "failed run provenance changed")
    require(config["required_environment"]
            == {"MUJOCO_GL": "egl", "PYOPENGL_PLATFORM": "egl"},
            "render environment changed")
    require(ROOT / config["report"] == REPORT, "report path changed")
    return config


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
        raise TimeoutError(f"{seconds} s E0-v2 phase limit")
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(seconds)


def _safe_file(base, relative):
    base = Path(base).resolve(strict=True)
    path = (base / relative).resolve(strict=True)
    require(path.is_relative_to(base) and path.is_file() and not path.is_symlink(),
            "unsafe/missing source: " + relative)
    return path


def source_receipt():
    config = configuration()
    report_path = ROOT / config["source_report"]
    require(file_record(report_path)["sha256"] == config["source_report_sha256"],
            "source report changed")
    report = read(report_path)
    require(report["status"] == "passed_diagnostic" and report["summary"]["render_count"] == 264,
            "source diagnostic incomplete")
    source_run = Path(config["source_run_directory"])
    require(source_run.resolve(strict=True) == source_run and source_run.is_dir()
            and not source_run.is_symlink(), "unsafe source run directory")
    receipt_path = _safe_file(source_run, "execution/run_receipt.json")
    receipt = read(receipt_path)
    require(receipt == report["receipt"], "source run/report receipt mismatch")
    require(file_record(_safe_file(source_run, "check_receipt.json")) == receipt["check_receipt"],
            "source check receipt changed")
    current = inventory(source_run / "execution")
    current.pop("run_receipt.json")
    require(current == receipt["outputs_before_receipt"], "source phase outputs changed")
    return report, receipt


def _source_public_path(name, receipt):
    relative = f"public/{name}.json.gz"
    path = _safe_file(Path(CONFIG["source_run_directory"]) / "execution", relative)
    require(file_record(path) == receipt["outputs_before_receipt"][relative],
            "source public record changed: " + name)
    return path


def _generation_file(relative):
    path = _safe_file(CONFIG["source_generation_stage"], relative)
    _, receipt = source_receipt()
    require(relative in receipt["source_inputs"]
            and file_record(path) == receipt["source_inputs"][relative],
            "generation source changed: " + relative)
    return path


def _history_record(path, index):
    found = None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            if value["frame_index"] == index:
                found = value
                break
    require(found is not None, "registered frame absent")
    return found


def _set_camera(scene, x, original):
    import numpy as np
    position = original["camera_position_m"]
    scene.data.mocap_pos[scene.mocap_id] = [x, position[1], position[2]]
    scene.data.mocap_quat[scene.mocap_id] = scene.config["observation"]["camera_mujoco_quat_wxyz"]
    scene.refresh()
    before = scene.state().copy()
    observation = scene.observe()
    require(np.array_equal(before, scene.state()), "audit render changed integration state")
    require(observation["camera_position_m"][1:] == position[1:], "audit changed camera y/height")
    return observation


def _candidate_for_v1_audit(candidate):
    value = deepcopy(candidate)
    for support in value["support"]:
        support.pop("boundary_compatible_pixels", None)
        support.pop("transition_kind", None)
    return value


def v1_audit_view(prediction):
    """Losslessly expose v2 candidate geometry to the sealed v1 truth evaluator."""
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
    return {
        "candidates": [_candidate_for_v1_audit(item) for item in prediction["candidates"]],
        "conflicts": [{"reason": item["reason"],
                       "members": [_candidate_for_v1_audit(member) for member in item["members"]]}
                      for item in prediction["conflicts"]],
    }


def boundary_support(prediction):
    result = []
    for candidate_index, candidate in enumerate(prediction["candidates"]):
        for support_index, support in enumerate(candidate["support"]):
            for pixel in support["boundary_compatible_pixels"]:
                result.append({"candidate_index": candidate_index, "support_index": support_index,
                               "boundary_kind": support["boundary_kind"], "pixel": list(pixel),
                               "plane_height_interval_m": support["plane_height_interval_m"]})
    return result


def _geom_names(scene, segmentation):
    import mujoco
    result = []
    for object_id, object_type in segmentation.reshape(-1, 2):
        if int(object_type) == int(mujoco.mjtObj.mjOBJ_GEOM) and int(object_id) >= 0:
            result.append(scene.model.geom(int(object_id)).name)
        else:
            result.append(None)
    return result


def check():
    config = configuration()
    require_environment()
    require(not RUN.exists(), "phase directory exists; verify/export only")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed")
    _bounded_runtime(config["limits"]["check_wall_s"])
    began = time.monotonic()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name))
                               for name in TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    require(result.wasSuccessful() and not result.skipped and not result.expectedFailures,
            "E0-v2 phase checks failed")
    source_report, source = source_receipt()
    RUN.mkdir(parents=True)
    write(RUN / "check_receipt.json", {
        "stage": STAGE, "exit_code": 0, "commit": git("rev-parse", "HEAD"),
        "binding": binding(), "environment": require_environment(),
        "tests_run": result.testsRun, "elapsed_s": time.monotonic() - began,
        "source_report": file_record(ROOT / config["source_report"]),
        "source_run_commit": source["commit"],
    })
    print(f"{STAGE} CHECKED tests={result.testsRun} exit=0", flush=True)


def verify_check():
    receipt = read(RUN / "check_receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "invalid check receipt")
    require(receipt["binding"] == binding(), "binding changed after check")
    require(receipt["environment"] == require_environment(), "environment changed")
    source_receipt()
    return receipt


def _public_phase(execution, source):
    e0 = read(ROOT / CONFIG["e0_v2"])
    records = {}
    for world in CONFIG["worlds"]:
        for gate in CONFIG["gates"]:
            for numerator in CONFIG["phase_sweep"]["numerators"]:
                name = _case_name(world, gate["gate_index"], numerator)
                source_path = _source_public_path(name, source)
                old = read(source_path)
                require((old["world"], old["gate_index"], old["phase_numerator"])
                        == (world, gate["gate_index"], numerator), "source case identity changed")
                prediction = recover_openings(
                    [old["observation"]], e0["public_sensor_spec"], e0["extractor"])
                value = {key: old[key] for key in
                         ("world", "gate_index", "frame_index", "phase_numerator",
                          "phase_denominator", "offset_x_m", "camera_x_m", "pixel_pitch_m")}
                value.update({"source_public_record": file_record(source_path),
                              "v1_prediction": old["prediction"], "v2_prediction": prediction})
                path = execution / "public" / (name + ".json.gz")
                records[name] = write(path, value)
        print(f"{world} PUBLIC reused={len(CONFIG['gates']) * len(CONFIG['phase_sweep']['numerators'])}",
              flush=True)
    seal = {"stage": STAGE, "records": records, "public_complete": True,
            "source_public_frames_reused": len(records), "new_public_renders": 0,
            "private_geometry_read_during_public_phase": False}
    write(execution / "public_seal.json", seal)
    return seal


def _audit_boundary_pixels(observation, prediction, geom_names, gate_index):
    from spatial_world_model import public_geometry as geometry
    rotation = geometry._rotation(observation["camera_xyzw"])
    allowed = {f"gate_{gate_index}_left", f"gate_{gate_index}_right"}
    rows = []
    for item in boundary_support(prediction):
        u, v = item["pixel"]
        index = v * observation["width"] + u
        depth = observation["depth_m"][index]
        ray = geometry._ray(observation, rotation, u, v)
        plane_far = geometry._intersection_depths(
            observation, rotation, (u, v), item["plane_height_interval_m"])[1]
        rows.append({**item, "geom_name": geom_names[index], "registered_gate_wall": geom_names[index] in allowed,
                     "actual_depth_m": depth, "plane_far_depth_m": plane_far,
                     "strict_farther_required_depth_m": plane_far + 0.0002,
                     "derived_world_height_m": observation["camera_position_m"][2] + depth * ray[2]})
    return rows


def _private_phase(execution, seal):
    import numpy as np
    from spatial_world_model.r4_physics_v2 import R4SceneV2
    family_prefix = f"execution/{CONFIG['source_family']}/data/audit"
    family = read(_generation_file(family_prefix + "/config.json"))
    e0_v1 = read(ROOT / CONFIG["e0_v1"])
    rows = []
    for world in CONFIG["worlds"]:
        xml_path = _generation_file(f"{family_prefix}/{world}/world.xml")
        xml = xml_path.read_text(encoding="utf-8")
        targets = targets_from_xml(xml)
        prefix = _generation_file(f"{family_prefix}/{world}/history_prefix.jsonl.gz")
        scene = R4SceneV2(xml, family)
        try:
            for gate in CONFIG["gates"]:
                gate_index = gate["gate_index"]
                index = family["observation"]["fixed_view_frame_indices"][gate["view_key"]]
                original = _history_record(prefix, index)
                for numerator in CONFIG["phase_sweep"]["numerators"]:
                    name = _case_name(world, gate_index, numerator)
                    public_path = execution / "public" / (name + ".json.gz")
                    require(file_record(public_path) == seal["records"][name], "public seal changed")
                    value = read(public_path)
                    scene.restore(original["snapshot"], scene.digest(original["snapshot"]))
                    observation = _set_camera(scene, value["camera_x_m"], original["observation"])
                    source_value = read(_safe_file(
                        Path(CONFIG["source_run_directory"]) / "execution", f"public/{name}.json.gz"))
                    require(observation == source_value["observation"], "private rerender differs")
                    before = scene.state().copy()
                    segmentation = scene.render("segmentation")
                    require(np.array_equal(before, scene.state()), "segmentation changed state")
                    geom_names = _geom_names(scene, segmentation)
                    target = targets[gate_index]
                    v1_assessment = assess_geometry(value["v1_prediction"], [target],
                                                    e0_v1["evaluation_only"])
                    v2_assessment = assess_geometry(v1_audit_view(value["v2_prediction"]), [target],
                                                    e0_v1["evaluation_only"])
                    boundary = _audit_boundary_pixels(
                        observation, value["v2_prediction"], geom_names, gate_index)
                    v1_accepted = v1_assessment["accepted"]
                    strict_equal = (not v1_accepted or (
                        not boundary and geometry_signature(value["v2_prediction"])
                        == geometry_signature(value["v1_prediction"])))
                    rows.append({key: value[key] for key in
                                 ("world", "gate_index", "frame_index", "phase_numerator",
                                  "phase_denominator", "offset_x_m", "camera_x_m", "pixel_pitch_m")} | {
                        "v1_assessment": v1_assessment,
                        "v2_assessment": v2_assessment,
                        "v2_evidence_counts": value["v2_prediction"]["evidence_counts"],
                        "v2_boundary_support": boundary,
                        "v1_accepted_geometry_exactly_preserved": strict_equal,
                    })
        finally:
            scene.close()
        print(f"{world} PRIVATE rerenders={len(CONFIG['gates']) * len(CONFIG['phase_sweep']['numerators'])}",
              flush=True)
    return rows


def summarize(rows):
    v1_pass = [row for row in rows if row["v1_assessment"]["accepted"]]
    v1_fail = [row for row in rows if not row["v1_assessment"]["accepted"]]
    boundary = [item for row in rows for item in row["v2_boundary_support"]]
    names = Counter(item["geom_name"] for item in boundary)
    kinds = Counter(item["boundary_kind"] for item in boundary)
    body_hits = sum(item["geom_name"] in {"object", "pusher"} for item in boundary)
    conclusion = {
        "case_count": len(rows),
        "v1_accepted_cases": len(v1_pass),
        "v1_failed_cases": len(v1_fail),
        "v2_accepted_cases": sum(row["v2_assessment"]["accepted"] for row in rows),
        "all_v2_cases_accepted": all(row["v2_assessment"]["accepted"] for row in rows),
        "all_v1_accepted_geometry_exactly_preserved": all(
            row["v1_accepted_geometry_exactly_preserved"] for row in v1_pass),
        "all_v1_failed_cases_resolved_by_boundary_support": all(
            row["v2_assessment"]["accepted"] and bool(row["v2_boundary_support"])
            for row in v1_fail),
        "boundary_support_pixel_count": len(boundary),
        "boundary_support_geom_names": dict(names),
        "boundary_support_kinds": dict(kinds),
        "all_boundary_pixels_registered_gate_walls": all(
            item["registered_gate_wall"] for item in boundary),
        "boundary_pixel_body_hits": body_hits,
    }
    accepted = CONFIG["acceptance"]
    checks = {
        "all_v2_cases_accepted": conclusion["all_v2_cases_accepted"] is accepted["all_v2_cases_accepted"],
        "v1_accepted_census": conclusion["v1_accepted_cases"] == accepted["expected_v1_accepted_cases"],
        "v1_failed_census": conclusion["v1_failed_cases"] == accepted["expected_v1_failed_cases"],
        "v1_geometry_preserved": conclusion["all_v1_accepted_geometry_exactly_preserved"]
        is accepted["all_v1_accepted_geometry_exactly_preserved"],
        "v1_failures_resolved_with_boundary": conclusion["all_v1_failed_cases_resolved_by_boundary_support"]
        is accepted["all_v1_failed_cases_resolved_by_boundary_support"],
        "boundary_pixels_are_registered_walls": conclusion["all_boundary_pixels_registered_gate_walls"]
        is accepted["all_boundary_pixels_registered_gate_walls"],
        "no_boundary_body_hits": conclusion["boundary_pixel_body_hits"] == accepted["boundary_pixel_body_hits"],
    }
    return {"conclusion": conclusion, "checks": checks,
            "accepted": all(checks.values()), "failed_checks": [k for k, v in checks.items() if not v]}


def run():
    config = configuration()
    require_environment()
    check_receipt = verify_check()
    source_report, source = source_receipt()
    execution = RUN / "execution"
    require(not execution.exists(), "phase execution exists; never overwrite")
    _bounded_runtime(config["limits"]["run_wall_s"])
    began = time.monotonic()
    execution.mkdir()
    try:
        write(execution / "started.json", {"stage": STAGE,
              "time_utc": datetime.now(timezone.utc).isoformat(),
              "source_report": file_record(ROOT / config["source_report"])})
        seal = _public_phase(execution, source)
        rows = _private_phase(execution, seal)
        summary = summarize(rows)
        write(execution / "private_evaluation.json.gz", {"rows": rows})
        write(execution / "summary.json", summary)
        require(summary["accepted"], "fixed E0-v2 phase acceptance failed: "
                + ",".join(summary["failed_checks"]))
        source_receipt()
        outputs = inventory(execution)
        require(sum(item["bytes"] for item in outputs.values()) <= config["limits"]["stage_bytes"],
                "stage output limit exceeded")
        receipt = {"stage": STAGE, "exit_code": 0, "commit": check_receipt["commit"],
                   "binding": binding(), "check_receipt": file_record(RUN / "check_receipt.json"),
                   "source_report": file_record(ROOT / config["source_report"]),
                   "outputs_before_receipt": outputs, "summary": summary,
                   "source_public_frames_reused": 264, "new_public_renders": 0,
                   "private_audit_rerenders": 264, "physics_steps": 0,
                   "training_steps": 0, "confirmation_read": False,
                   "elapsed_s": time.monotonic() - began}
        write(execution / "run_receipt.json", receipt)
        print(f"{STAGE} RAN cases=264 accepted={summary['accepted']} exit=0", flush=True)
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
    source_receipt()
    current = inventory(RUN / "execution")
    current.pop("run_receipt.json")
    require(current == receipt["outputs_before_receipt"], "phase outputs changed")
    summary = read(RUN / "execution/summary.json")
    require(summary == receipt["summary"] and summary["accepted"], "summary mismatch/failure")
    print(f"{STAGE} VERIFIED cases=264 accepted=True exit=0", flush=True)
    return receipt, summary


def export():
    receipt, summary = verify()
    require(not REPORT.exists(), "report exists; never overwrite")
    result = {"version": CONFIG["version"], "decision": CONFIG["decision"],
              "status": "passed_phase_audit", "receipt": receipt, "summary": summary,
              "evaluation": read(RUN / "execution/private_evaluation.json.gz"),
              "claims": {"e0_v2_phase_audit": True, "e0_v2_all_development_validated": False,
                         "dual_m_result": False, "training_result": False,
                         "confirmation_result": False}}
    raw = encode(result)
    require(len(raw) <= CONFIG["limits"]["report_bytes"], "report size limit exceeded")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("xb") as handle:
        handle.write(raw)
    record = file_record(REPORT)
    print(f"{STAGE} EXPORTED status=passed_phase_audit bytes={record['bytes']} "
          f"sha256={record['sha256']} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "run", "verify", "export"))
    args = parser.parse_args()
    globals()[args.command]()


if __name__ == "__main__":
    main()
