"""Read-only SH-02 failure diagnosis from existing, hash-verified trajectories.

No MuJoCo/NumPy import, simulation, filtering or source/run-file modification.
Writes one small results JSON, including real contact episodes and endpoints.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from contract_check import ROOT, encode, git, require, sha, write_new


RUN = Path("/root/autodl-tmp/spatial-history/sh02-engineering-v1-eglfix1")
SOURCE = ROOT / "results/spatial_history_physics_v1_eglfix1.json"
REPORT = ROOT / "results/spatial_history_contact_diagnostic_v1.json"
SELF = "ops/spatial_history/contact_diagnose.py"
HELPER = "ops/spatial_history/contract_check.py"
DOC = "docs/DATA.md"


def file_sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checkpoint(row):
    # Actual observations from the saved privileged trace, never model inputs.
    return {k: row[k] for k in ("time_s", "object_position_m", "ee_position_m", "ee_velocity_mps",
                                "command_mps", "actuator_force_n", "contacts")}


def summarize(raw):
    trace = raw["trace"]
    require(trace and all(a["time_s"] < b["time_s"] for a, b in zip(trace, trace[1:])), "empty/unordered trace")
    endpoints = {row["time_s"]: row for row in trace}
    intervals = [checkpoint(endpoints[row["time_s"]]) for row in raw["future"]]
    counts, maximum_force, first, last = Counter(), {}, {}, {}
    episodes, active = [], None
    for index, row in enumerate(trace):
        groups = {}
        for contact in row["contacts"]:
            pair = "|".join(contact["geoms"])
            groups[pair] = max(groups.get(pair, 0.), contact["normal_force_n"])
        for pair, force in groups.items():
            counts[pair] += 1  # Multiple contact points count as one physics step.
            maximum_force[pair] = max(maximum_force.get(pair, 0.), force)
            first.setdefault(pair, checkpoint(row))
            last[pair] = checkpoint(row)
        if "object|pusher" in groups:
            if active is None:
                active = {"first": checkpoint(row), "previous": checkpoint(trace[index-1]) if index else None,
                          "steps": 0, "max_normal_force_n": 0.}
            active["steps"] += 1
            active["max_normal_force_n"] = max(active["max_normal_force_n"], groups["object|pusher"])
            active["last"] = checkpoint(row)
        elif active is not None:
            active["next"] = checkpoint(row)
            episodes.append(active)
            active = None
    if active is not None:
        active["next"] = None
        episodes.append(active)
    return {"physics_steps": len(trace), "first": checkpoint(trace[0]), "last": checkpoint(trace[-1]),
            "object_axis_ranges_m": [[min(r["object_position_m"][a] for r in trace),
                                       max(r["object_position_m"][a] for r in trace)] for a in range(3)],
            "contact_pairs": {p: {"steps": counts[p], "max_normal_force_n": maximum_force[p],
                                    "first": first[p], "last": last[p]} for p in sorted(counts)},
            "object_pusher_episodes": episodes, "control_endpoints": intervals,
            "minimum_object_pusher_center_distance_m": min(math.dist(r["object_position_m"], r["ee_position_m"]) for r in trace)}


def main():
    require(sys.version_info >= (3, 11), "Python 3.11+ required")
    require(not git("status", "--porcelain", "--", SELF, HELPER, DOC, str(SOURCE.relative_to(ROOT))), "diagnostic/source report must be committed and clean")
    exported, receipt = read_json(SOURCE), read_json(RUN / "receipt.json")
    require(exported["receipt"] == receipt and exported["receipt_sha256"] == file_sha(RUN / "receipt.json"), "source report/receipt mismatch")
    require(receipt["stage"] == "SH-02" and receipt["exit_code"] == 1, "expected preserved SH-02 failure")
    for name, digest in receipt["binding"].items():
        blob = subprocess.check_output(["git", "-C", str(ROOT), "show", receipt["commit"] + ":" + name])
        require(sha(blob) == digest, f"original Git source mismatch: {name}")
    for name, digest in receipt["artifacts"].items():
        path = (RUN / name).resolve()
        require(path.is_relative_to(RUN.resolve()), f"artifact outside run: {name}")
        require(file_sha(path) == digest, f"artifact changed: {name}")
    branches = []
    for world in range(2):
        record_name = f"fixture/world-{world}-record.json"
        require(record_name in receipt["artifacts"], "world record not bound by original receipt")
        record = read_json(RUN / record_name)
        for action in range(2):
            name = f"fixture/world-{world}-action-{action}-trace.json"
            require(name in receipt["artifacts"], "trace not bound by original receipt")
            raw = read_json(RUN / name)
            require(raw["future"] == record["branches"][action]["future"]
                    and raw["base_snapshot_sha256"] == record["branches"][action]["base_snapshot_sha256"], "trace/record branch mismatch")
            summary = summarize(raw)
            branches.append({"world_index": world, "action_index": action, "trace_sha256": receipt["artifacts"][name],
                             "initial_state": record["initial_state"], "hidden_obstacles": record["hidden_obstacles"], **summary})
            print(f"SH-02 DIAG world={world} action={action} object_y_range={summary['object_axis_ranges_m'][1]} "
                  f"pusher_contact_episodes={len(summary['object_pusher_episodes'])}", flush=True)
    report = {"kind": "read_only_contact_diagnostic", "source_report": str(SOURCE.relative_to(ROOT)),
              "source_report_sha256": file_sha(SOURCE), "original_receipt_sha256": exported["receipt_sha256"],
              "original_commit": receipt["commit"], "diagnostic_commit": git("rev-parse", "HEAD"),
              "diagnostic_binding": {p: file_sha(ROOT / p) for p in (SELF, HELPER, DOC)},
              "source_artifact_count_verified": len(receipt["artifacts"]),
              "simulation_rerun": False, "branches": branches}
    if REPORT.exists():
        # Documentation/report commits do not force re-export of identical data.
        saved = read_json(REPORT)
        require({k: v for k, v in saved.items() if k != "diagnostic_commit"}
                == {k: v for k, v in report.items() if k != "diagnostic_commit"}, "different report exists; not overwritten")
    else:
        write_new(REPORT, report)
    print(f"SH-02 CONTACT-DIAG EXPORTED {REPORT} exit=0", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"SH-02 CONTACT-DIAG FAILED exit=1: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
