"""D-089: artificial checks, sealed public predictions, then read-only audit.

Foreground, fixed 16 histories/144 primary branches; no generation or training.
Existing or interrupted stages are never rerun or overwritten.
"""
import argparse
import gzip
import hashlib
import shutil
import xml.etree.ElementTree as ET
import ast
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
from contract_check import ROOT, Tee, encode, git, require, sha

STAGE = "SH-04-R4-cd-v1"
RUN = Path("/root/autodl-tmp/spatial-history/sh04-r4-cd-audit-v1")
SOURCE = Path("/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v2")
REPORT = ROOT / "results/spatial_history_r4_map_control_v1.json"
CONFIG = "configs/spatial_history/r4_map_control_audit_v1.json"
CONFIG_SHA = "215bbf2bb0c1163c2db72e0eec8b359c0a2c9a03d3c035302e920f3c954ae863"
TESTS = ("tests/spatial_world_model/test_r4_map_control.py",
         "tests/spatial_world_model/test_r4_map_control_ops.py")
BOUND = ("src/spatial_world_model/__init__.py",
         "src/spatial_world_model/pair_contract.py",
         "src/spatial_world_model/two_gate_contract.py",
         "src/spatial_world_model/r4_query_v2.py",
         "src/spatial_world_model/r4_scoring_v2.py",
         "src/spatial_world_model/r4_coverage.py",
         "src/spatial_world_model/r4_object_association.py",
         "src/spatial_world_model/r4_observed_map.py",
         "src/spatial_world_model/r4_control_proxy.py",
         "src/spatial_world_model/r4_proxy_readout.py",
         "src/spatial_world_model/r4_proxy_audit.py",
         "tests/spatial_world_model/test_r4_map_control.py",
         "tests/spatial_world_model/test_r4_map_control_ops.py",
         "tests/spatial_world_model/test_r4_object_association.py",
         "tests/spatial_world_model/r4_examples_v2.py",
         "ops/spatial_history/contract_check.py",
         "ops/spatial_history/r4_map_control_check.py",
         "configs/spatial_history/r4_map_control_audit_v1.json",
         "results/spatial_history_r4_object_association_v1.json",
         "results/spatial_history_r4_engineering_subset_v2.json",
         "docs/METHOD.md",
         "docs/DATA.md")
LIMIT_S, LIMIT_BYTES, LIMIT_RSS = 300, 8 * 1024**2, 512 * 1024**2
CLAIMS = {"real_history_object_association_verified": False, "public_geometry_recovery_verified": False,
          "full_3d_map_verified": False, "physical_predictability_verified": False,
          "model_experiment_run": False, "long_term_memory_claim_verified": False}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def configuration():
    raw = (ROOT / CONFIG).read_bytes()
    require(sha(raw) == CONFIG_SHA, "registered c/d config changed")
    value = json.loads(raw)
    require(value["tests"] == list(TESTS), "test registration changed")
    return value


def binding():
    return {name: sha((ROOT / name).read_bytes()) for name in BOUND}


def test_names():
    names = []
    for name in TESTS:
        tree = ast.parse((ROOT / name).read_bytes())
        names.extend(f"{Path(name).stem}.{cls.name}.{fn.name}" for cls in tree.body
                     if isinstance(cls, ast.ClassDef) for fn in cls.body
                     if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"))
    require(names and len(names) == len(set(names)), "test inventory empty/duplicate")
    return sorted(names)


def inventory():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(
        importlib.import_module(Path(name).stem)) for name in TESTS)
    def flatten(item):
        return [n for child in item for n in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]
    require(sorted(flatten(suite)) == test_names(), "runtime/AST test inventory differs")
    return suite


def used_bytes(directory):
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def write_new(directory, path, value):
    raw = encode(value)
    require(used_bytes(directory) + len(raw) <= LIMIT_BYTES, "stage/report byte limit")
    with path.open("xb") as handle:
        handle.write(raw)


def source_matches_commit(commit, sources):
    require(type(commit) is str and len(commit) == 40
            and all(c in "0123456789abcdef" for c in commit), "full source commit required")
    require(sources == binding(), "current sources differ")
    require(all(sha(subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{n}"])) == digest
                for n, digest in sources.items()), "source bytes differ from recorded Git commit")


def verify(directory):
    configuration()
    receipt = read(directory / "receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "no successful map/control check receipt")
    source_matches_commit(receipt["commit"], receipt["binding"])
    names = test_names()
    require(receipt["test_names"] == names and receipt["tests_run"] == len(names), "test census mismatch")
    require(all(receipt[k] == 0 for k in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")),
            "incomplete checks")
    require(receipt["claims"] == CLAIMS and receipt["new_simulation_steps"] == receipt["new_training_steps"]
            == receipt["new_weight_download_bytes"] == receipt["real_history_queries"] == 0, "scope/claims changed")
    require(receipt["artifacts"] == {n: sha((directory / n).read_bytes()) for n in ("started.json", "tests.log")},
            "evidence digest changed")
    started = read(directory / "started.json")
    require(all(started[k] == receipt[k] for k in ("stage", "commit", "binding")), "started/receipt mismatch")
    require(set(p.name for p in directory.iterdir()) == {"started.json", "tests.log", "receipt.json"},
            "unexpected or failure artifact")
    require(0 <= receipt["elapsed_s"] <= LIMIT_S and 0 < receipt["peak_rss_bytes"] <= LIMIT_RSS,
            "time/memory receipt invalid")
    require(receipt["stage_bytes"] == used_bytes(directory) <= LIMIT_BYTES, "stage byte count changed")
    print(f"{STAGE} VERIFIED tests={len(names)} exit=0", flush=True)
    return receipt


def run(directory):
    if directory.exists():
        print("Existing stage: verify only; no rerun or overwrite.", flush=True)
        return verify(directory)
    configuration()
    require(not git("status", "--porcelain", "--", *BOUND), "bound sources must be committed and clean")
    before, commit = binding(), git("rev-parse", "HEAD")
    source_matches_commit(commit, before)
    began = time.monotonic()
    directory.mkdir(parents=True, exist_ok=False)
    try:
        write_new(directory, directory / "started.json", {"stage": STAGE, "commit": commit, "binding": before,
                  "started": datetime.now(timezone.utc).isoformat()})
        suite = inventory()
        with (directory / "tests.log").open("x", encoding="utf-8") as log:
            result = unittest.TextTestRunner(stream=Tee(log), verbosity=2).run(suite)
        names = test_names()
        counts = {"failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                  "expected_failures": len(result.expectedFailures), "unexpected_successes": len(result.unexpectedSuccesses)}
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        elapsed = time.monotonic() - began
        passed = (not any(counts.values()) and result.testsRun == len(names) and before == binding()
                  and elapsed <= LIMIT_S and rss <= LIMIT_RSS)
        receipt = {"stage": STAGE, "commit": commit, "binding": before, "python": sys.version,
                   "platform": platform.platform(), "test_names": names, "tests_run": result.testsRun,
                   **counts, "artifacts": {n: sha((directory / n).read_bytes()) for n in ("started.json", "tests.log")},
                   "elapsed_s": elapsed, "peak_rss_bytes": rss, "stage_bytes": 0,
                   "new_simulation_steps": 0, "new_training_steps": 0, "new_weight_download_bytes": 0, "real_history_queries": 0,
                   "claims": CLAIMS, "exit_code": 0 if passed else 1}
        evidence_bytes = used_bytes(directory)
        for _ in range(10):
            total = evidence_bytes + len(encode(receipt))
            if receipt["stage_bytes"] == total:
                break
            receipt["stage_bytes"] = total
        require(receipt["stage_bytes"] == evidence_bytes + len(encode(receipt)), "receipt size did not settle")
        write_new(directory, directory / "receipt.json", receipt)
        require(passed, "map/control checks failed; preserve stage and export")
        return verify(directory)
    except BaseException as error:
        if not (directory / "receipt.json").exists():
            try:
                write_new(directory, directory / "failure.json", {"stage": STAGE, "exit_code": 1,
                          "error": f"{type(error).__name__}: {error}", "elapsed_s": time.monotonic() - began})
            except (OSError, ValueError, MemoryError):
                print("Could not write failure receipt; incomplete stage preserved.", file=sys.stderr, flush=True)
        raise


def export(directory, report_path):
    configuration()
    require(directory.is_dir(), "no map/control check stage to export")
    error, receipt = None, None
    try:
        receipt = verify(directory)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as problem:
        error = f"{type(problem).__name__}: {problem}"
    artifacts = {}
    require(used_bytes(directory) <= LIMIT_BYTES, "stage too large for registered export")
    for name in ("started.json", "tests.log", "receipt.json", "failure.json"):
        path = directory / name
        if path.is_file():
            raw = path.read_bytes()
            artifacts[name] = {"bytes": len(raw), "sha256": sha(raw), "text": raw.decode("utf-8", errors="replace")}
    value = {"kind": "r4_map_control_artificial_engineering_check", "status": "passed" if error is None else "failed_or_incomplete",
             "verification_error": error, "receipt": receipt, "source_artifacts": artifacts,
             "receipt_sha256": artifacts.get("receipt.json", {}).get("sha256"), "claims": CLAIMS}
    raw = encode(value)
    require(used_bytes(directory) + len(raw) <= LIMIT_BYTES, "stage plus report byte limit")
    if report_path.exists():
        require(report_path.read_bytes() == raw, "different existing report; never overwrite")
    else:
        write_new(directory, report_path, value)
    print(f"{STAGE} EXPORTED status={value['status']} path={report_path} exit=0", flush=True)


def record(path):
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block); count += len(block)
    return {"bytes": count, "sha256": digest.hexdigest()}


def source_path(name, registration):
    require(name in registration["files"], "unregistered source")
    path = SOURCE / name
    require(path.resolve().is_relative_to(SOURCE.resolve())
            and not any(p.is_symlink() for p in (path, *path.parents) if p != SOURCE and p.is_relative_to(SOURCE)), "source path escape/symlink")
    require(record(path) == registration["files"][name], "source digest changed: " + name)
    return path


def source_marker(registration):
    path = SOURCE / "run_receipt.json"
    require(record(path) == registration["generation_receipt"], "original generation receipt changed")
    # Acceptance/commit were verified when this immutable digest was registered.
    # Do not decode the original aggregate receipt: it can contain private audit results.
    return record(path)


def registration_slots(registration):
    return [(f,w,a) for f in registration["families"] for w in registration["worlds"] for a in registration["actions"]]


def stage_record(directory):
    return {p.relative_to(directory).as_posix(): record(p)
            for p in sorted(directory.rglob("*")) if p.is_file()}


def save_audit(path, value, *, failure=False):
    limits = configuration()["limits"]
    raw = encode(value)
    if path.suffix == ".gz": raw = gzip.compress(raw, mtime=0)
    reserve = 0 if failure else limits["failure_reserve_bytes"] + limits["export_bytes"]
    require(used_bytes(RUN) + len(raw) <= limits["audit_stage_plus_export_bytes"] - reserve, "audit byte budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle: handle.write(raw)
    return record(path)


def load_gzip(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle: return json.load(handle)


def audit_started():
    value = read(RUN / "run_started.json")
    require(value["stage"] == STAGE, "audit stage mismatch")
    source_matches_commit(value["commit"], value["binding"])
    return value


def prediction_seal():
    started = audit_started()
    seal = read(RUN / "public_seal.json")
    require(seal["commit"] == started["commit"] and seal["binding"] == started["binding"], "public seal source mismatch")
    require(seal["history_count"] == 16 and seal["branch_count"] == 144, "incomplete public seal")
    require(seal["private_truth_read"] is False and seal["formal_prediction_count"] == 0, "public phase scope changed")
    expected = {f"public/{f}/{w}/map.json.gz" for f,w,a in registration_slots(configuration()["source_registration"])}
    expected |= {f"public/{f}/{w}/{a}.json.gz" for f,w,a in registration_slots(configuration()["source_registration"])}
    require(set(seal["files"]) == expected, "public output census")
    require(stage_record(RUN / "public") == {n.removeprefix("public/"):v for n,v in seal["files"].items()}, "public prediction bytes changed")
    return seal


def predict_phase():
    from spatial_world_model import r4_observed_map as maps, r4_control_proxy as dynamics, r4_proxy_readout as readout
    from spatial_world_model import r4_object_association as objects
    from spatial_world_model.r4_query_v2 import from_public_query, validate_controls, domain_spec, SOURCE_VERSION
    cfg = configuration(); registration = cfg["source_registration"]
    started = audit_started()
    require(not (RUN / "public").exists() and not (RUN / "public_seal.json").exists(), "public phase cannot restart")
    files, sources, worlds = {}, {}, []
    for family in registration["families"]:
        for world in registration["worlds"]:
            name = f"execution/{family}/data/public/{world}.json.gz"
            path = source_path(name, registration); sources[name] = registration["files"][name]
            public = load_gzip(path)
            require(set(public) == {"schema_version","history","actions","goal"}
                    and public["schema_version"] == "spatial-history-r4-public-family-v2", "public family schema")
            require(len(public["actions"]) == 9, "nine controls")
            # Validate all native frames once; this value adapter has no instance/file access.
            validated = from_public_query({"schema_version":SOURCE_VERSION,"history":public["history"],
                                          "controls":public["actions"][0],"goal":public["goal"]})
            del validated
            controls = []
            for action in public["actions"]:
                require(len(action) == 200 and all(set(row) == {"ee_velocity_mps","duration_s"} for row in action), "control rows")
                value = {key:[row[key] for row in action] for key in ("ee_velocity_mps","duration_s")}
                validate_controls(value)
                require(value not in controls, "duplicate candidate")
                controls.append(value)
            frames = [{key:row[key] for key in objects.FIELDS.split()} for row in public["history"]]
            for i,row in enumerate(frames): row["time_s"] = (i-120)/10
            observed = maps.build_map({"schema_version":maps.HISTORY_VERSION,"frames":frames},
                                     objects.sensor_spec(),objects.common_shape_spec(),maps.parameters(),history_mode="full")
            stem = f"public/{family}/{world}"
            files[stem+"/map.json.gz"] = save_audit(RUN / (stem+"/map.json.gz"), observed)
            states = []
            for slot,(action,control) in enumerate(zip(registration["actions"],controls)):
                proxy = dynamics.predict_control(observed,control,domain_spec(),dynamics.parameters())
                task = readout.readout(observed,proxy,public["goal"],readout.parameters())
                require(proxy["main_prediction"] is None and proxy["eligible_for_P"] is False
                        and task["formal_prediction"] is None, "engineering scope changed")
                files[stem+f"/{action}.json.gz"] = save_audit(RUN / (stem+f"/{action}.json.gz"), {"proxy":proxy,"task":task})
                states.append({"slot":slot,"action":action,"proxy_status":proxy["status"],"readout_status":task["status"]})
                print(f"{STAGE} PUBLIC {family}/{world}/{action} {proxy['status']} {task['status']}", flush=True)
            worlds.append({"family":family,"world":world,"map_status":observed["status"],"branches":states})
            del public, frames, observed, proxy, task
    save_audit(RUN / "public_seal.json", {"stage":STAGE,"commit":started["commit"],"binding":started["binding"],
               "history_count":len(worlds),"branch_count":sum(len(w["branches"]) for w in worlds),
               "source_public_files":sources,"files":files,"worlds":worlds,"private_truth_read":False,
               "formal_prediction_count":0})
    print(f"{STAGE} SEALED histories=16 branches=144 exit=0", flush=True)


def actual_geometry(path):
    root = ET.parse(path).getroot()
    boxes, floors = [], []
    for geom in root.findall("./worldbody/geom"):
        kind = geom.get("type")
        require(not any(key in geom.attrib for key in ("quat","euler","axisangle","xyaxes","zaxis","fromto")), "rotated evaluation geometry unsupported")
        position = [float(v) for v in geom.get("pos","0 0 0").split()]
        size = [float(v) for v in geom.get("size","").split()]
        require(len(position) == 3, "geometry position")
        if kind == "plane": floors.append(position[2])
        elif kind == "box":
            require(len(size) == 3, "box extent")
            boxes.append([position[0]-size[0],position[0]+size[0],position[1]-size[1],position[1]+size[1]])
        else: raise ValueError("unsupported static evaluation geometry")
    require(len(floors) == 1 and boxes, "original static geometry missing")
    return boxes, floors[0]


def evaluate_phase():
    # Imported only after the public process exited successfully and all outputs were sealed.
    seal = prediction_seal()
    phase = read(RUN / "predict_exit.json")
    require(phase["exit_code"] == 0 and phase["public_seal"] == record(RUN / "public_seal.json"), "public exit/seal missing")
    from spatial_world_model import r4_proxy_audit as evaluator
    require(not (RUN / "evaluation").exists(), "evaluation cannot restart")
    registration = configuration()["source_registration"]
    worlds, sources = [], {}
    for family in registration["families"]:
        for world in registration["worlds"]:
            observed = load_gzip(RUN / f"public/{family}/{world}/map.json.gz")
            xml = f"execution/{family}/data/audit/{world}/world.xml"
            boxes,floor = actual_geometry(source_path(xml,registration)); sources[xml] = registration["files"][xml]
            row = {"family":family,"world":world,"map":evaluator.compare_map(observed,boxes,floor),
                   "association_status":observed["current_object"]["status"],"frame_audit":observed["frame_audit"],"branches":[]}
            for action in registration["actions"]:
                value = load_gzip(RUN / f"public/{family}/{world}/{action}.json.gz")
                trace = f"execution/{family}/data/audit/{world}/primary-{action}/trajectory.jsonl.gz"
                labels = f"execution/{family}/data/labels/{world}-{action}.json.gz"
                with gzip.open(source_path(trace,registration),"rt",encoding="utf-8") as handle:
                    actual = [json.loads(line) for line in handle if line.strip()]
                target = load_gzip(source_path(labels,registration))
                require(target["trajectory"] == registration["files"][trace], "label/actual trajectory binding mismatch")
                sources[trace] = registration["files"][trace]; sources[labels] = registration["files"][labels]
                metrics = evaluator.compare_branch(value["proxy"],value["task"],actual,target["labels"])
                metrics["object_association"] = evaluator.compare_object(observed["current_object"],actual[0])
                row["branches"].append({"action":action,**metrics})
                del actual, value, target
            row["selection"] = evaluator.nominal_selection(row["branches"])
            save_audit(RUN / f"evaluation/{family}-{world}.json.gz",row)
            worlds.append(row)
            print(f"{STAGE} AUDIT {family}/{world} branches=9 exit=0", flush=True)
    branches = [b for w in worlds for b in w["branches"]]
    statuses = {s:sum(b["proxy_status"] == s for b in branches) for s in sorted({b["proxy_status"] for b in branches})}
    summary = {"stage":STAGE,"history_count":len(worlds),"branch_count":len(branches),"worlds":worlds,
               "proxy_status_counts":statuses,"nominal_complete_count":statuses.get("nominal_complete",0),
               "nominal_task_readout_count":sum(b["nominal_success"] is not None for b in branches),
               "formal_prediction_count":0,"eligible_for_P_count":0,"formal_model_ready":False,
               "public_seal":record(RUN / "public_seal.json"),"source_truth_files":sources,
               "new_generation_steps":0,"new_training_steps":0,"new_weight_download_bytes":0,
               "interpretation":"engineering_execution_completeness_only_no_accuracy_acceptance_threshold"}
    require(len(worlds) == 16 and len(branches) == 144 and len(sources) == 304, "audit denominator")
    save_audit(RUN / "summary.json",summary)


def launch_phase(step, remaining):
    require(remaining > 0, "audit time exhausted")
    began = time.monotonic()
    process = subprocess.Popen([sys.executable,"-B",str(Path(__file__).resolve()),step],cwd=ROOT)
    try:
        code = process.wait(timeout=remaining)
    except BaseException:
        process.kill(); process.wait()
        raise
    result = {"exit_code":code,"elapsed_s":time.monotonic()-began,
              "peak_rss_bytes":resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
              "rss_measurement":"cumulative_max_over_completed_children"}
    if step == "_predict" and code == 0: result["public_seal"] = record(RUN / "public_seal.json")
    save_audit(RUN / ("predict_exit.json" if step == "_predict" else "evaluate_exit.json"),result)
    require(code == 0, "phase failed; preserve output and export")
    return result


def audit_run():
    if (RUN / "run_started.json").exists() or (RUN / "run_failure.json").exists():
        return audit_verify()
    checked = verify(RUN / "check")
    cfg = configuration(); limits = cfg["limits"]; registration = cfg["source_registration"]
    require(checked["commit"] == git("rev-parse","HEAD"), "check must belong to this stage commit")
    require(not git("status","--porcelain","--",*BOUND), "bound sources dirty")
    original = source_marker(registration)
    require(shutil.disk_usage(RUN).free >= limits["audit_stage_plus_export_bytes"], "insufficient disk budget")
    available = next(int(line.split()[1])*1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
    require(available >= limits["minimum_available_memory_bytes"], "insufficient memory budget")
    began = time.monotonic()
    save_audit(RUN / "run_started.json",{"stage":STAGE,"commit":checked["commit"],"binding":checked["binding"],
               "source_receipt":original,"limits":limits,"started":datetime.now(timezone.utc).isoformat()})
    try:
        prediction = launch_phase("_predict",limits["audit_run_wall_s"]-(time.monotonic()-began))
        prediction_seal()
        evaluation = launch_phase("_evaluate",limits["audit_run_wall_s"]-(time.monotonic()-began))
        elapsed = time.monotonic()-began
        require(elapsed <= limits["audit_run_wall_s"], "audit wall budget")
        require(max(prediction["peak_rss_bytes"],evaluation["peak_rss_bytes"]) <= limits["audit_process_as_and_rss_bytes"], "audit RSS budget")
        parent_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        require(parent_rss <= limits["audit_process_as_and_rss_bytes"], "parent RSS budget")
        save_audit(RUN / "audit_receipt.json",{"stage":STAGE,"commit":checked["commit"],"binding":checked["binding"],
                   "exit_code":0,"elapsed_s":elapsed,"prediction":prediction,"evaluation":evaluation,
                   "parent_peak_rss_bytes":parent_rss,"files":stage_record(RUN),"summary":record(RUN / "summary.json"),"claims":CLAIMS})
        return audit_verify()
    except BaseException as error:
        if not (RUN / "run_failure.json").exists():
            save_audit(RUN / "run_failure.json",{"stage":STAGE,"exit_code":1,"elapsed_s":time.monotonic()-began,
                       "error":f"{type(error).__name__}: {error}"},failure=True)
        raise


def audit_verify():
    cfg = configuration(); limits = cfg["limits"]
    verify(RUN / "check")
    started = audit_started(); seal = prediction_seal()
    receipt = read(RUN / "audit_receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0 and receipt["claims"] == CLAIMS, "no successful audit receipt")
    require(all(receipt[k] == started[k] for k in ("commit","binding")), "audit source mismatch")
    require(not (RUN / "run_failure.json").exists(), "failure artifact present")
    current = stage_record(RUN); current.pop("audit_receipt.json")
    require(current == receipt["files"], "audit evidence changed")
    require(receipt["summary"] == record(RUN / "summary.json"), "summary digest changed")
    summary = read(RUN / "summary.json")
    require(summary["history_count"] == len(summary["worlds"]) == 16
            and summary["branch_count"] == sum(len(w["branches"]) for w in summary["worlds"]) == 144, "summary denominator")
    require([(w["family"],w["world"],b["action"]) for w in summary["worlds"] for b in w["branches"]]
            == registration_slots(cfg["source_registration"]), "query identity/order changed")
    require(summary["public_seal"] == record(RUN / "public_seal.json"), "summary/public seal mismatch")
    require(summary["formal_model_ready"] is False and all(summary[k] == 0 for k in
            ("formal_prediction_count","eligible_for_P_count","new_generation_steps","new_training_steps","new_weight_download_bytes")), "audit scope changed")
    require({**seal["source_public_files"],**summary["source_truth_files"]} == cfg["source_registration"]["files"], "consumed source census/digests")
    require(0 <= receipt["elapsed_s"] <= limits["audit_run_wall_s"], "audit time receipt")
    require(0 < receipt["parent_peak_rss_bytes"] <= limits["audit_process_as_and_rss_bytes"], "parent RSS receipt")
    for name in ("prediction","evaluation"):
        require(receipt[name]["exit_code"] == 0 and 0 < receipt[name]["peak_rss_bytes"] <= limits["audit_process_as_and_rss_bytes"], "phase receipt")
        require(receipt[name]["rss_measurement"] == "cumulative_max_over_completed_children", "RSS semantics")
    require(receipt["prediction"] == read(RUN / "predict_exit.json")
            and receipt["evaluation"] == read(RUN / "evaluate_exit.json"), "child exit evidence mismatch")
    require(used_bytes(RUN) <= limits["audit_stage_plus_export_bytes"]-limits["export_bytes"], "audit size")
    print(f"{STAGE} VERIFIED histories=16 branches=144 formal_ready=False exit=0",flush=True)
    return receipt


def export_audit():
    cfg = configuration(); require(RUN.is_dir(), "no stage to export")
    error, receipt = None, None
    try: receipt = audit_verify()
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as problem:
        error = f"{type(problem).__name__}: {problem}"
    evidence = {}
    for name in ("check/started.json","check/tests.log","check/receipt.json","check/failure.json",
                 "run_started.json","predict_exit.json","evaluate_exit.json","audit_receipt.json","run_failure.json"):
        path = RUN / name
        if path.is_file():
            raw = path.read_bytes()
            evidence[name] = {**record(path),"text":raw.decode("utf-8",errors="replace")}
    logs = {}
    for name in ("predict.log","evaluate.log"):
        path = RUN / name
        if path.exists(): logs[name] = {**record(path),"tail":path.read_text(encoding="utf-8",errors="replace")[-16000:]}
    malformed = {}
    def optional_json(name):
        path = RUN / name
        if not path.is_file(): return None
        try:
            require(path.stat().st_size <= cfg["limits"]["export_bytes"], "diagnostic JSON too large")
            return read(path)
        except (ValueError,OSError,UnicodeError) as problem:
            malformed[name] = {**record(path),"error":f"{type(problem).__name__}: {problem}"}
            return None
    summary = optional_json("summary.json")
    seal = optional_json("public_seal.json")
    value = {"kind":"r4_map_control_readonly_engineering_audit","stage":STAGE,"status":"passed" if error is None else "failed_or_incomplete",
             "verification_error":error,"receipt":receipt,"source_artifacts":evidence,"log_tails":logs,
             "public_seal":seal,"summary":summary,"stage_inventory":stage_record(RUN),"claims":CLAIMS,
             "formal_model_ready":False,"malformed_json":malformed}
    raw = encode(value)
    require(len(raw) <= cfg["limits"]["export_bytes"] and used_bytes(RUN)+len(raw) <= cfg["limits"]["audit_stage_plus_export_bytes"], "export budget")
    if REPORT.exists(): require(REPORT.read_bytes() == raw,"different existing report; never overwrite")
    else:
        with REPORT.open("xb") as handle: handle.write(raw)
    print(f"{STAGE} EXPORTED status={value['status']} path={REPORT} exit=0",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("check","run","verify","export","_predict","_evaluate"))
    step = parser.parse_args().step
    require(platform.system() == "Linux" and (3,11) <= sys.version_info[:2] < (3,13),"Linux Python 3.11/3.12 only")
    require(Path(sys.prefix) == Path("/root/autodl-tmp/spatial-history-venv-v1"),"use existing isolated server environment")
    cfg = configuration(); limits = cfg["limits"]
    heavy = step in ("run","_predict","_evaluate")
    memory = limits["audit_process_as_and_rss_bytes"] if heavy else LIMIT_RSS
    resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
    resource.setrlimit(resource.RLIMIT_FSIZE,(limits["audit_stage_plus_export_bytes"],)*2)
    # Parent run owns the total alarm and kills/waits its child on interruption.
    def timeout(signum,frame): raise KeyboardInterrupt("command time budget; preserve stage")
    signal.signal(signal.SIGALRM,timeout)
    signal.alarm(limits["audit_run_wall_s"] if heavy else LIMIT_S)
    os.chdir(ROOT); sys.path.insert(0,str(ROOT / "src"))
    if step in ("_predict","_evaluate"):
        log_name = "predict.log" if step == "_predict" else "evaluate.log"
        with (RUN / log_name).open("x",encoding="utf-8") as log:
            original_out = sys.stdout
            class ConsoleLog:
                def write(self, value):
                    original_out.write(value); log.write(value)
                def flush(self):
                    original_out.flush(); log.flush()
            sys.stdout = ConsoleLog()
            try: (predict_phase if step == "_predict" else evaluate_phase)()
            finally: sys.stdout = original_out
    else:
        {"check":lambda:run(RUN / "check"),"run":audit_run,"verify":audit_verify,"export":export_audit}[step]()


if __name__ == "__main__":
    try: main()
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError,KeyboardInterrupt,MemoryError) as error:
        print(f"{STAGE} FAILED exit=1: {error}",file=sys.stderr,flush=True)
        sys.exit(1)
