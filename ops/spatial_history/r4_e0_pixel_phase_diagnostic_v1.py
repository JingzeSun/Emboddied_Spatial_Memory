"""D-116 fixed-snapshot E0 pixel-phase causal diagnostic.

The public phase changes only camera x, renders an already sealed snapshot, and
runs the unchanged E0.  Only after every public record is sealed does the audit
phase read XML targets and segmentation.  No physics step, fitting, data repair,
or new observation protocol is authorized here.
"""

from __future__ import annotations

import argparse
from collections import Counter
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


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tests/spatial_world_model")]
from spatial_world_model.pair_contract import require
from spatial_world_model.r4_e0_pixel_phase import (
    gate_gap_trace, phase_fractions, pixel_pitch_m, projected_column)
from spatial_world_model.r4_storage import file_record


CONFIG_PATH = "configs/spatial_history/r4_e0_pixel_phase_diagnostic_v1.json"
CONFIG = json.loads((ROOT / CONFIG_PATH).read_text(encoding="utf-8"))
RUN = Path(CONFIG["run_directory"])
ENVIRONMENT = Path(CONFIG["environment"])
REPORT = ROOT / CONFIG["report"]
STAGE = "SH-05-R4-E0-pixel-phase-v1"
TESTS = (
    "tests.spatial_world_model.test_public_geometry",
    "tests.spatial_world_model.test_public_geometry_audit",
    "tests.spatial_world_model.test_r4_e0_pixel_phase",
)
BOUND = (
    CONFIG_PATH,
    "configs/spatial_history/public_geometry_parallel_v1.json",
    "ops/spatial_history/r4_e0_pixel_phase_diagnostic_v1.py",
    "src/spatial_world_model/public_geometry.py",
    "src/spatial_world_model/public_geometry_audit.py",
    "src/spatial_world_model/r4_e0_pixel_phase.py",
    "src/spatial_world_model/r4_physics_v2.py",
    "src/spatial_world_model/r4_families_v2.py",
    "src/spatial_world_model/two_gate_physics.py",
    "tests/spatial_world_model/test_r4_e0_pixel_phase.py",
    "tests/spatial_world_model/test_public_geometry.py",
    "tests/spatial_world_model/test_public_geometry_audit.py",
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


def _sha(path):
    return file_record(path)["sha256"]


def configuration():
    config = read(ROOT / CONFIG_PATH)
    require(config["version"] == "sh05-r4-e0-pixel-phase-diagnostic-v1", "wrong diagnostic version")
    require(config["status"] == "authorized_diagnostic_not_data_protocol"
            and config["diagnostic_authorized"] is True, "diagnostic not authorized")
    require(all(config[name] is False for name in
                ("data_rebuild_authorized", "training_authorized", "confirmation_authorized")),
            "diagnostic cannot authorize downstream work")
    require(config["source_family"] == "r4-36" and config["worlds"] == ["LL", "LR", "RL", "RR"],
            "source family/world census changed")
    require(config["gates"] == [{"gate_index": 0, "view_key": "A"},
                                 {"gate_index": 1, "view_key": "B"}], "gate/view pairing changed")
    sweep = config["phase_sweep"]
    phase_fractions(sweep["denominator"], sweep["numerators"])
    require(Path(config["run_directory"]) == RUN and Path(config["environment"]) == ENVIRONMENT,
            "runtime path changed")
    require(ROOT / config["report"] == REPORT, "report path changed")
    return config


def require_environment():
    require(os.name != "nt" and resource is not None, "server Linux environment required")
    require(Path(sys.prefix).resolve() == ENVIRONMENT.resolve(), "use the registered spatial-history environment")
    import mujoco
    import numpy
    require((mujoco.__version__, numpy.__version__) == ("3.3.7", "2.2.6"),
            "registered MuJoCo/Numpy versions changed")
    return {"python_prefix": sys.prefix, "mujoco": mujoco.__version__, "numpy": numpy.__version__}


def _bounded_runtime(seconds):
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    def timeout(signum, frame):
        raise TimeoutError(f"{seconds} s pixel-phase diagnostic limit")
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(seconds)


def _source_path(relative):
    base = Path(CONFIG["source_stage"]).resolve(strict=True)
    path = (base / relative).resolve(strict=True)
    require(path.is_relative_to(base) and path.is_file() and not path.is_symlink(),
            "unsafe/missing source: " + relative)
    return path


def source_inventory():
    config = configuration()
    records = {}
    for relative, expected_sha in config["source_records"].items():
        path = _source_path(relative)
        require(_sha(path) == expected_sha, "registered source changed: " + relative)
        records[relative] = file_record(path)
    data_prefix = f'execution/{config["source_family"]}/data'
    public_manifest = read(_source_path(data_prefix + "/public_manifest.json"))
    audit_manifest = read(_source_path(data_prefix + "/audit_manifest.json"))
    needed_public = [f"{world}.json.gz" for world in config["worlds"]]
    needed_audit = ["config.json", "family_result.json"]
    for world in config["worlds"]:
        needed_audit.extend([f"{world}/history_prefix.jsonl.gz", f"{world}/world.xml"])
    require(all(name in public_manifest for name in needed_public), "public manifest is incomplete")
    require(all(name in audit_manifest for name in needed_audit), "audit manifest is incomplete")
    for channel, manifest, names in (("public", public_manifest, needed_public),
                                      ("audit", audit_manifest, needed_audit)):
        for name in names:
            relative = f"{data_prefix}/{channel}/{name}"
            path = _source_path(relative)
            require(file_record(path) == manifest[name], "manifest source changed: " + relative)
            records[relative] = file_record(path)
    release = read(_source_path("execution/release.json"))
    require(release["reviewed_code"] == config["generation_commit"], "generation commit changed")
    require(release["training_authorized"] is False and release["confirmation_authorized"] is False,
            "source release scope changed")
    failure = read(_source_path("execution/failure.json"))
    require("family worker failed: r4-36" in failure["error"], "wrong source failure")
    family = read(_source_path(data_prefix + "/audit/family_result.json"))
    require(family["accepted"] is False and family["failed_checks"] == ["public_geometry"],
            "requires the exact public-geometry-only family failure")
    return records


def _history_record(path, index):
    found = None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            if value["frame_index"] == index:
                found = value
            require(value["frame_index"] <= index or found is not None,
                    "history prefix indices are not ordered")
            if found is not None:
                break
    require(found is not None, "registered frame absent from history prefix")
    return found


def _set_camera(scene, x, original):
    import numpy as np
    position = original["camera_position_m"]
    scene.data.mocap_pos[scene.mocap_id] = [x, position[1], position[2]]
    scene.data.mocap_quat[scene.mocap_id] = scene.config["observation"]["camera_mujoco_quat_wxyz"]
    scene.refresh()
    before = scene.state().copy()
    observation = scene.observe()
    after = scene.state().copy()
    require(np.array_equal(before, after), "render changed integration state")
    require(observation["camera_position_m"][1:] == position[1:], "intervention changed camera y/height")
    for name in ("time_s", "width", "height", "camera_xyzw", "intrinsics", "ee_position_m",
                 "ee_velocity_mps", "previous_velocity_mps"):
        require(observation[name] == original[name], "x intervention changed " + name)
    return observation


def _case_name(world, gate, numerator):
    sign = "m" if numerator < 0 else "p"
    return f"{world}-g{gate}-{sign}{abs(numerator):02d}"


def check():
    config = configuration()
    require_environment()
    require(not RUN.exists(), "diagnostic directory exists; verify/export only")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed")
    _bounded_runtime(config["limits"]["check_wall_s"])
    began = time.monotonic()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name))
                               for name in TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    require(result.wasSuccessful() and not result.skipped and not result.expectedFailures,
            "pixel-phase checks failed")
    RUN.mkdir(parents=True)
    write(RUN / "check_receipt.json", {
        "stage": STAGE, "exit_code": 0, "commit": git("rev-parse", "HEAD"),
        "binding": binding(), "environment": require_environment(),
        "tests_run": result.testsRun, "elapsed_s": time.monotonic() - began,
    })
    print(f"{STAGE} CHECKED tests={result.testsRun} exit=0", flush=True)


def verify_check():
    receipt = read(RUN / "check_receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "invalid check receipt")
    require(receipt["binding"] == binding(), "diagnostic binding changed after check")
    require(receipt["environment"] == require_environment(), "diagnostic environment changed")
    return receipt


def _geom_names(scene, segmentation):
    import mujoco
    result = []
    for object_id, object_type in segmentation.reshape(-1, 2):
        if int(object_type) == int(mujoco.mjtObj.mjOBJ_GEOM) and int(object_id) >= 0:
            result.append(scene.model.geom(int(object_id)).name)
        else:
            result.append(None)
    return result


def _render_public(execution, source_before):
    from spatial_world_model.public_geometry import recover_openings
    from spatial_world_model.r4_physics_v2 import R4SceneV2
    config = configuration()
    family = read(_source_path(f'execution/{config["source_family"]}/data/audit/config.json'))
    e0 = read(ROOT / config["e0"])
    fractions = phase_fractions(config["phase_sweep"]["denominator"],
                                config["phase_sweep"]["numerators"])
    records = {}
    originals = {}
    for world in config["worlds"]:
        prefix = _source_path(f'execution/{config["source_family"]}/data/audit/{world}/history_prefix.jsonl.gz')
        public = read(_source_path(f'execution/{config["source_family"]}/data/public/{world}.json.gz'))
        xml_path = _source_path(f'execution/{config["source_family"]}/data/audit/{world}/world.xml')
        scene = R4SceneV2(xml_path.read_text(encoding="utf-8"), family)
        try:
            for gate in config["gates"]:
                index = family["observation"]["fixed_view_frame_indices"][gate["view_key"]]
                original = _history_record(prefix, index)
                require(original["observation"] == public["history"][index], "prefix/public frame mismatch")
                pitch = pixel_pitch_m(original["observation"], family["geometry"]["wall_height_m"])
                originals[(world, gate["gate_index"])] = {
                    "frame_index": index, "record": original, "pixel_pitch_m": pitch}
                for numerator, fraction in zip(config["phase_sweep"]["numerators"], fractions):
                    scene.restore(original["snapshot"], scene.digest(original["snapshot"]))
                    x = original["observation"]["camera_position_m"][0] + fraction * pitch
                    observation = _set_camera(scene, x, original["observation"])
                    if numerator == 0:
                        require(observation == original["observation"], "zero phase does not reproduce sealed frame")
                    prediction = recover_openings([observation], e0["public_sensor_spec"], e0["extractor"])
                    name = _case_name(world, gate["gate_index"], numerator)
                    path = execution / "public" / (name + ".json.gz")
                    records[name] = {
                        "world": world, "gate_index": gate["gate_index"], "frame_index": index,
                        "phase_numerator": numerator,
                        "phase_denominator": config["phase_sweep"]["denominator"],
                        "offset_x_m": fraction * pitch,
                        "camera_x_m": x,
                        "pixel_pitch_m": pitch,
                        "observation": observation,
                        "prediction": prediction,
                    }
                    write(path, records[name])
                    records[name] = file_record(path)
        finally:
            scene.close()
        print(f"{world} PUBLIC cases={len(config['gates']) * len(fractions)}", flush=True)
    seal = {"stage": STAGE, "source_inputs": source_before, "records": records,
            "public_complete": True, "private_geometry_read_during_public_phase": False}
    write(execution / "public_seal.json", seal)
    return originals, seal


def _evaluate(execution, originals, seal):
    import numpy as np
    from spatial_world_model.public_geometry_audit import assess_geometry, targets_from_xml
    from spatial_world_model.r4_physics_v2 import R4SceneV2
    config = configuration()
    family = read(_source_path(f'execution/{config["source_family"]}/data/audit/config.json'))
    family_result = read(_source_path(f'execution/{config["source_family"]}/data/audit/family_result.json'))
    e0 = read(ROOT / config["e0"])
    rows = []
    for world in config["worlds"]:
        xml_path = _source_path(f'execution/{config["source_family"]}/data/audit/{world}/world.xml')
        xml = xml_path.read_text(encoding="utf-8")
        targets = targets_from_xml(xml)
        scene = R4SceneV2(xml, family)
        try:
            for gate in config["gates"]:
                gate_index = gate["gate_index"]
                original = originals[(world, gate_index)]["record"]
                original_mode = "view_a" if gate_index == 0 else "view_b"
                expected = next(item for item in family_result["geometry"]["rows"]
                                if item["world"] == world and item["mode"] == original_mode)
                for numerator in config["phase_sweep"]["numerators"]:
                    name = _case_name(world, gate_index, numerator)
                    public_path = execution / "public" / (name + ".json.gz")
                    require(file_record(public_path) == seal["records"][name], "sealed public record changed")
                    value = read(public_path)
                    scene.restore(original["snapshot"], scene.digest(original["snapshot"]))
                    observation = _set_camera(scene, value["camera_x_m"], original["observation"])
                    require(observation == value["observation"], "audit rerender differs from sealed public render")
                    before = scene.state().copy()
                    segmentation = scene.render("segmentation")
                    require(np.array_equal(before, scene.state()), "segmentation changed integration state")
                    geom_names = _geom_names(scene, segmentation)
                    target = targets[gate_index]
                    assessment = assess_geometry(value["prediction"], [target], e0["evaluation_only"])
                    trace = gate_gap_trace(
                        observation, geom_names, f"gate_{gate_index}_left", f"gate_{gate_index}_right",
                        family["geometry"]["wall_height_m"], e0["public_sensor_spec"], e0["extractor"])
                    row = {key: value[key] for key in
                           ("world", "gate_index", "frame_index", "phase_numerator", "phase_denominator",
                            "offset_x_m", "camera_x_m", "pixel_pitch_m")}
                    row.update({
                        "candidate_count": len(value["prediction"]["candidates"]),
                        "rejected_counts": value["prediction"]["rejected_counts"],
                        "assessment": assessment,
                        "target": target,
                        "boundary_projection": {
                            "left": projected_column(observation, target["coordinates_m"][0],
                                                     family["geometry"]["wall_height_m"]),
                            "right": projected_column(observation, target["coordinates_m"][1],
                                                      family["geometry"]["wall_height_m"]),
                        },
                        "gate_gap_trace": trace,
                        "zero_phase_matches_original_assessment": (numerator != 0 or (
                            assessment["accepted"] == expected["assessment"]["accepted"]
                            and len(value["prediction"]["candidates"]) == expected["candidate_count"]
                            and value["prediction"]["rejected_counts"] == expected["rejected_counts"])),
                    })
                    rows.append(row)
        finally:
            scene.close()
        print(f"{world} AUDIT cases={len(config['gates']) * len(config['phase_sweep']['numerators'])}", flush=True)
    return rows


def _summary(rows):
    cases = []
    all_blockers = Counter()
    for world in CONFIG["worlds"]:
        for gate in (0, 1):
            selected = [row for row in rows if row["world"] == world and row["gate_index"] == gate]
            zero = next(row for row in selected if row["phase_numerator"] == 0)
            passing = [row["phase_numerator"] for row in selected if row["assessment"]["accepted"]]
            blockers = Counter(failure["geom_name"] for item in zero["gate_gap_trace"]["rows"]
                               for failure in item["failures"])
            all_blockers.update(blockers)
            cases.append({
                "world": world, "gate_index": gate,
                "zero_phase_accepted": zero["assessment"]["accepted"],
                "zero_phase_candidate_count": zero["candidate_count"],
                "zero_phase_nonfarther_gap_pairs": zero["rejected_counts"]["nonfarther_gap_pairs"],
                "zero_phase_blocking_geom_names": dict(blockers),
                "passing_phase_numerators": passing,
                "passing_phase_count": len(passing),
                "outcome_changes_with_x_phase": bool(passing) and len(passing) != len(selected),
                "zero_phase_matches_original": zero["zero_phase_matches_original_assessment"],
                "left_boundary_zero_phase": zero["boundary_projection"]["left"],
                "right_boundary_zero_phase": zero["boundary_projection"]["right"],
                "zero_phase_gap_trace": zero["gate_gap_trace"],
            })
    original_failures = [case for case in cases if not case["zero_phase_accepted"]]
    body_names = {"object", "pusher"}
    blocker_names = {name for name, count in all_blockers.items() if count}
    conclusion = {
        "zero_phase_reproduced_all_cases": all(case["zero_phase_matches_original"] for case in cases),
        "original_failure_case_count": len(original_failures),
        "all_original_failures_change_under_x_only_intervention": all(
            case["outcome_changes_with_x_phase"] for case in original_failures),
        "zero_phase_blocker_geom_names": dict(all_blockers),
        "body_occlusion_supported": bool(blocker_names & body_names),
        "registered_gate_surface_blocker_supported": bool(blocker_names)
            and blocker_names.isdisjoint(body_names)
            and all(name is not None and name.startswith("gate_") for name in blocker_names),
    }
    conclusion["pixel_phase_causal_attribution_supported"] = all((
        conclusion["zero_phase_reproduced_all_cases"],
        conclusion["original_failure_case_count"] > 0,
        conclusion["all_original_failures_change_under_x_only_intervention"],
        not conclusion["body_occlusion_supported"],
        conclusion["registered_gate_surface_blocker_supported"],
    ))
    return {"case_count": len(cases), "render_count": len(rows), "cases": cases,
            "conclusion": conclusion}


def run():
    config = configuration()
    require_environment()
    check_receipt = verify_check()
    execution = RUN / "execution"
    require(not execution.exists(), "diagnostic execution exists; never overwrite")
    _bounded_runtime(config["limits"]["run_wall_s"])
    began = time.monotonic()
    execution.mkdir()
    try:
        source_before = source_inventory()
        write(execution / "started.json", {"stage": STAGE, "time_utc": datetime.now(timezone.utc).isoformat(),
                                             "source_inputs": source_before})
        originals, seal = _render_public(execution, source_before)
        rows = _evaluate(execution, originals, seal)
        write(execution / "private_evaluation.json.gz", {"rows": rows})
        summary = _summary(rows)
        summary.update({
            "scope": "fixed sealed snapshots; camera x only; unchanged E0; private audit after public seal",
            "physics_steps": 0, "training_steps": 0, "data_protocol_selected": False,
            "data_rebuild_authorized": False, "confirmation_read": False,
        })
        write(execution / "summary.json", summary)
        source_after = source_inventory()
        require(source_before == source_after, "sealed source changed during diagnostic")
        outputs = inventory(execution)
        require(sum(item["bytes"] for item in outputs.values()) <= config["limits"]["stage_bytes"],
                "diagnostic output limit exceeded")
        receipt = {
            "stage": STAGE, "exit_code": 0, "commit": check_receipt["commit"],
            "binding": binding(), "check_receipt": file_record(RUN / "check_receipt.json"),
            "source_inputs": source_before, "outputs_before_receipt": outputs,
            "render_count": summary["render_count"], "case_count": summary["case_count"],
            "conclusion": summary["conclusion"], "elapsed_s": time.monotonic() - began,
            "physics_steps": 0, "training_steps": 0, "weight_download_bytes": 0,
        }
        write(execution / "run_receipt.json", receipt)
        print(f"{STAGE} RAN renders={summary['render_count']} causal={summary['conclusion']['pixel_phase_causal_attribution_supported']} exit=0", flush=True)
    except BaseException as error:
        failure = execution / "failure.json"
        if not failure.exists():
            write(failure, {"error": f"{type(error).__name__}: {error}", "elapsed_s": time.monotonic() - began})
        raise


def verify():
    configuration()
    require_environment()
    check_receipt = verify_check()
    receipt = read(RUN / "execution/run_receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "invalid run receipt")
    require(receipt["commit"] == check_receipt["commit"] and receipt["binding"] == binding(),
            "run binding changed")
    require(receipt["source_inputs"] == source_inventory(), "source changed after run")
    current = inventory(RUN / "execution")
    current.pop("run_receipt.json")
    require(current == receipt["outputs_before_receipt"], "diagnostic outputs changed")
    summary = read(RUN / "execution/summary.json")
    require(summary["render_count"] == 264 and summary["case_count"] == 8,
            "diagnostic census changed")
    require(summary["conclusion"] == receipt["conclusion"], "conclusion/receipt mismatch")
    print(f"{STAGE} VERIFIED renders=264 causal={summary['conclusion']['pixel_phase_causal_attribution_supported']} exit=0", flush=True)
    return receipt, summary


def export():
    receipt, summary = verify()
    require(not REPORT.exists(), "diagnostic report exists; never overwrite")
    evaluation = read(RUN / "execution/private_evaluation.json.gz")
    result = {
        "version": CONFIG["version"], "decision": CONFIG["decision"],
        "status": "passed_diagnostic" if receipt["exit_code"] == 0 else "failed_or_incomplete",
        "receipt": receipt, "summary": summary, "evaluation": evaluation,
        "claims": {
            "pixel_phase_causal_attribution": summary["conclusion"]["pixel_phase_causal_attribution_supported"],
            "body_occlusion": summary["conclusion"]["body_occlusion_supported"],
            "new_data_protocol_validated": False, "model_failure": False,
            "training_result": False, "confirmation_result": False,
        },
    }
    raw = encode(result)
    require(len(raw) <= CONFIG["limits"]["report_bytes"], "report size limit exceeded")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("xb") as handle:
        handle.write(raw)
    record = file_record(REPORT)
    print(f"{STAGE} EXPORTED status={result['status']} bytes={record['bytes']} sha256={record['sha256']} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "run", "verify", "export"))
    args = parser.parse_args()
    globals()[args.command]()


if __name__ == "__main__":
    main()
