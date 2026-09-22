"""Ruling 49 follow-up: does the pitch-sign defect change the unobservable-window verdicts of the
already generated S1-02 episodes?  Read-only audit; nothing is generated, modified or re-run.

Usage (server, frontend env; the S1-04 contract's ``private_plane_reading`` and ``server_run`` bits
must be open -- this reads the private instance masks of episodes whose cache was sealed long ago):
    python ops/vsmt/lean_s1_02_window_audit.py \\
        --episode-roots /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<c>,/root/autodl-tmp/vsmt_outputs/lean-s1-02b-<c> \\
        --output-root /root/autodl-tmp/vsmt_private/lean-s1-02-window-audit-<commit> --workers 8

Why this audit exists.  S1-02 decided the unobservable window U by sealing one public visibility
subject per container from its best sweep-one frame and asking whether that subject projects any
unoccluded sample into *every* transition frame (ruling 35).  Both the seal and the projection used
the public camera pose, which ruling 49 found to be written with the pitch sign flipped.  Within one
yaw the error cancels (the seal and the assessment rotate by the same wrong amount about the same
axis); across yaws it does not.  So a container may have been recorded invisible when a correctly
posed projection would have seen it, or the reverse.

What one worker does, per episode:
  1. read the stored ``provenance/window_verdicts.json``: the window, which frame each container's
     subject was sealed from, and which containers were recorded invisible;
  2. rebuild each subject twice from the same private mask, public depth and frame digest -- once
     with the pose exactly as written (the control) and once with the ruling-49 correction (the
     test) -- and project both over every transition frame with the matching pose;
  3. report the control verdicts, the test verdicts, and the difference.  The control exists to
     prove the audit reproduces what generation recorded: if control != stored, the audit itself is
     not trusted for that episode and it is reported as ``control_mismatch``, never as a finding.

Poses are read relative (the public plane's frame) rather than absolute as generation did; every
frame of an episode shares one origin offset, so sealing and projecting in the episode frame gives
the same unoccluded counts, and the control check is what proves it.

白话：S1-02 当初怎么判断"这个容器在不可观测窗口里一直看不见"？它从扫掠一里挑一帧把容器封成一
个公开可见性主体，再把这个主体投影到窗口的每一帧，看有没有未被遮挡的采样点。封印和投影都用了
俯仰角写反的位姿。同一朝向下这个错误会抵消，换了朝向就不抵消，所以窗口判定可能有真假变化。这
个入口只读地把每条 episode 重算两遍：一遍完全照原样（对照，用来证明复算能复现当初记录的结果），
一遍用裁决 49 修正后的位姿（检验），然后报告差异。它不改任何数据，不重跑模拟器，也不自行修正
已生成的判定——判定要不要改属于用户裁决。
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import numpy as np  # noqa: E402

import lean_s1_02a_pilot as pilot  # noqa: E402
from vsmt import lean_public_pose as pp  # noqa: E402
from vsmt.vm04_public_visibility import (  # noqa: E402
    assess_public_visibility_from_depth, seal_public_visibility_subject,
)

S1_03_CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
S1_04_CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
REQUIRED_AUTHORIZATION = ("private_plane_reading", "server_run")
#: Registered outcomes of this audit, so a run cannot invent a category that quietly means "fine".
OUTCOMES = ("agrees", "verdicts_differ", "control_mismatch", "no_window", "episode_unreadable")


class AuditFailure(Exception):
    def __init__(self, outcome: str, detail: str = "") -> None:
        assert outcome in OUTCOMES, outcome
        super().__init__(f"{outcome}: {detail}")
        self.outcome, self.detail = outcome, detail


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------

def container_mask(private_record: dict[str, Any], labels: np.ndarray, container_id: str) -> np.ndarray | None:
    """The container's private mask at one frame, or None when it carries no label there."""

    label = private_record["object_id_to_entity_id"].get(container_id)
    if label is None:
        return None
    return np.asarray(labels) == int(label)


def invisible_from_counts(counts: dict[str, list[int]]) -> list[str]:
    """Ruling 35: a container is in U when it has no unoccluded sample in any transition frame."""

    return sorted(cid for cid, values in counts.items() if values and not any(v > 0 for v in values))


def rendered_pixels_in_window(private_records: list[dict[str, Any]], container_ids: list[str]) -> dict[str, int]:
    """Total private instance-mask pixels each container was rendered with over the window frames.

    This is the pose-independent cross-check: ``object_visibility`` is what the simulator itself
    rendered in that frame, so a container with pixels there was on screen, whatever any
    projection says.  A container recorded as unobservable while the simulator was drawing it is a
    defect of the verdict, not of the correction.

    白话：不依赖任何位姿的旁证。私有帧记录里的 `object_visibility` 是模拟器当帧实际画出的像素数，
    窗口内某个容器像素数大于 0，就说明它当时在画面上；如果它同时被登记成"窗口内不可见"，那就是
    判定本身错了，与我们怎么修位姿无关。
    """

    totals = {cid: 0 for cid in container_ids}
    for record in private_records:
        visibility = record.get("object_visibility") or {}
        for cid in totals:
            totals[cid] += int(visibility.get(cid, 0))
    return totals


#: Which named containers each intervention kind touches, as the S0-02 rule "every container
#: involved must be invisible in every window frame" reads them.
CONTAINERS_BY_KIND = {"remove": ("source",), "move": ("source", "destination"), "add": ("destination",)}


def intervention_containers(row: dict[str, Any], *, strict: bool) -> list[str]:
    """The containers one executed intervention involves.

    ``strict`` takes every container the row names (source and destination alike); otherwise the
    roles above.  The two differ only for ``add``, whose ``source`` holds an object the agent has
    never seen.  Both are reported; which one the frozen rule means is the user's to say.
    """

    roles = ("source", "destination") if strict else CONTAINERS_BY_KIND.get(str(row.get("kind")), ())
    return sorted({str(row[role]) for role in roles if row.get(role)})


def intervention_soundness(executed: list[dict[str, Any]], corrected_u: list[str],
                           rendered: dict[str, int]) -> dict[str, Any]:
    """Would each executed intervention still satisfy the frozen rule with a correct visibility test?

    S0-02 ``intervention_window``: an intervention runs only when every container it involves is
    invisible in every window frame, and a container re-entering view fails the whole episode.
    This re-asks that question against the corrected verdicts, per intervention and per rule
    reading, and never changes anything.

    白话：S0-02 合同写明"涉及的全部容器在窗口每一帧都不可见才执行干预，源容器中途重新进入视野
    整条 episode 失败"。这里就是把这句话用修正后的可见性重新问一遍：每条已执行的干预，它涉及的
    容器是否仍然全部落在修正后的 U 里。输出只是判断依据，不改任何数据，也不替用户裁决。
    """

    corrected = set(corrected_u)
    rows = []
    for row in executed:
        entry = {"kind": row.get("kind"), "object_id": row.get("object_id"),
                 "source": row.get("source"), "destination": row.get("destination")}
        for name, strict in (("strict", True), ("by_role", False)):
            containers = intervention_containers(row, strict=strict)
            outside = [cid for cid in containers if cid not in corrected]
            entry[name] = {"containers": containers, "containers_outside_corrected_u": outside,
                           "still_sound": not outside}
        entry["containers_the_simulator_rendered_in_window"] = sorted(
            cid for cid in intervention_containers(row, strict=True) if rendered.get(cid, 0) > 0)
        rows.append(entry)
    return {
        "executed_interventions": len(rows),
        "sound_strict": sum(1 for r in rows if r["strict"]["still_sound"]),
        "sound_by_role": sum(1 for r in rows if r["by_role"]["still_sound"]),
        "episode_still_valid_strict": all(r["strict"]["still_sound"] for r in rows),
        "episode_still_valid_by_role": all(r["by_role"]["still_sound"] for r in rows),
        "rows": rows,
    }


def read_executed_interventions(provenance_dir: Path) -> list[dict[str, Any]]:
    path = provenance_dir / "interventions.json"
    if not path.exists():
        return []
    return [row for row in json.loads(path.read_text(encoding="utf-8")).get("executed", [])
            if row.get("executed", True)]


def compare_sets(stored: list[str], control: list[str], test: list[str]) -> dict[str, Any]:
    """Control against what generation stored, and test against the control."""

    stored_set, control_set, test_set = set(stored), set(control), set(test)
    return {
        "stored_invisible": sorted(stored_set),
        "control_invisible": sorted(control_set),
        "corrected_invisible": sorted(test_set),
        "control_reproduces_generation": stored_set == control_set,
        "control_only": sorted(control_set - stored_set),
        "stored_only": sorted(stored_set - control_set),
        "corrected_adds": sorted(test_set - control_set),
        "corrected_removes": sorted(control_set - test_set),
        "verdicts_change": control_set != test_set,
    }


# --------------------------------------------------------------------------
# one episode
# --------------------------------------------------------------------------

def _load_frame(episode_root: Path, index: int, *, code_commit: str, policy: dict[str, Any]) -> dict[str, Any]:
    public = episode_root / "public"
    record = json.loads((public / f"{index:04d}.frame.json").read_text(encoding="utf-8"))
    depth = np.load(public / record["depth_path"]).astype(np.float32)
    written = {"position_m": [float(v) for v in record["relative_pose"]["position_m"]],
               "quaternion_xyzw": [float(v) for v in record["relative_pose"]["quaternion_xyzw"]]}
    return {"record": record, "depth": depth, "pose_written": written,
            "pose_corrected": pp.public_camera_pose(record, code_commit=code_commit, policy=policy),
            "frame_digest": record["frame_digest"]}


def audit_episode(task: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    episode_root = Path(task["episode_root"])
    out_dir = Path(task["out"])
    receipt: dict[str, Any] = {"episode_id": task["episode_id"], "code_commit": task["commit"],
                               "episode_code_commit": task["episode_code_commit"]}
    try:
        from PIL import Image

        out_dir.mkdir(parents=True, exist_ok=True)
        policy = task["pose_policy"]
        commit = task["episode_code_commit"]
        verdict_path = episode_root / "provenance" / "window_verdicts.json"
        if not verdict_path.exists():
            raise AuditFailure("no_window", "no window_verdicts.json")
        stored = json.loads(verdict_path.read_text(encoding="utf-8"))
        window = stored.get("window")
        if not window:
            raise AuditFailure("no_window", "window is null")
        low, high = int(window[0]), int(window[1])
        sealed_subjects = {cid: row for cid, row in (stored.get("subjects") or {}).items()
                           if row.get("sealed") and row.get("frame") is not None}
        if not sealed_subjects:
            raise AuditFailure("no_window", "no sealed container subject")

        calibration = pilot.intrinsics()
        subjects: dict[str, dict[str, Any]] = {}
        for container_id, row in sorted(sealed_subjects.items()):
            index = int(row["frame"])
            frame = _load_frame(episode_root, index, code_commit=commit, policy=policy)
            private_record = json.loads((episode_root / "private" / f"{index:04d}.frame.json").read_text(encoding="utf-8"))
            labels = np.asarray(Image.open(episode_root / "private" / private_record["instance_mask_path"]))
            mask = container_mask(private_record, labels, container_id)
            if mask is None or int(mask.sum()) < pilot.MIN_SUBJECT_PIXELS:
                continue
            reference = f"container:{pilot.sha(container_id)[:16]}"
            pair = {}
            for variant in ("written", "corrected"):
                pair[variant] = seal_public_visibility_subject(
                    subject_public_ref=reference, source_public_packet_sha256=frame["frame_digest"],
                    source_observation_index=index, public_mask=mask, public_depth_m=frame["depth"],
                    camera_calibration=calibration, camera_pose=frame[f"pose_{variant}"], config=pilot.VIS_CONFIG)
            subjects[container_id] = pair

        counts = {"written": {cid: [] for cid in subjects}, "corrected": {cid: [] for cid in subjects}}
        window_private: list[dict[str, Any]] = []
        for index in range(low + 1, high + 1):
            frame = _load_frame(episode_root, index, code_commit=commit, policy=policy)
            window_private.append(json.loads((episode_root / "private" / f"{index:04d}.frame.json").read_text(encoding="utf-8")))
            for container_id, pair in subjects.items():
                for variant in ("written", "corrected"):
                    result = assess_public_visibility_from_depth(
                        subject=pair[variant], current_observation_index=index, public_depth_m=frame["depth"],
                        camera_calibration=calibration, camera_pose=frame[f"pose_{variant}"],
                        current_public_support_sha256=None, terminal_reobservation_phase=False, config=pilot.VIS_CONFIG)
                    counts[variant][container_id].append(int(result["assessment"]["unoccluded_public_sample_count"]))

        stored_invisible = sorted(stored.get("invisible") or [])
        rendered = rendered_pixels_in_window(window_private, sorted(set(list(subjects) + stored_invisible)))
        comparison = compare_sets(stored_invisible,
                                  invisible_from_counts(counts["written"]),
                                  invisible_from_counts(counts["corrected"]))
        outcome = ("control_mismatch" if not comparison["control_reproduces_generation"]
                   else ("verdicts_differ" if comparison["verdicts_change"] else "agrees"))
        rendered_in_stored_u = sorted(cid for cid in stored_invisible if rendered.get(cid, 0) > 0)
        rendered_in_corrected_u = sorted(cid for cid in comparison["corrected_invisible"] if rendered.get(cid, 0) > 0)
        executed = read_executed_interventions(episode_root / "provenance")
        for row in executed:
            for role in ("source", "destination"):
                cid = row.get(role)
                if cid and cid not in rendered:
                    rendered[cid] = rendered_pixels_in_window(window_private, [cid])[cid]
        soundness = intervention_soundness(executed, comparison["corrected_invisible"], rendered)
        report = {
            "episode_id": task["episode_id"], "episode_code_commit": commit,
            "pose_correction_applied": pp.correction_applies(commit, policy),
            "window": [low, high], "transition_frames": high - low,
            "containers_sealed_in_audit": sorted(subjects), "containers_sealed_at_generation": sorted(sealed_subjects),
            "outcome": outcome, "comparison": comparison,
            "unoccluded_totals": {variant: {cid: int(sum(values)) for cid, values in table.items()}
                                  for variant, table in counts.items()},
            "rendered_pixels_in_window": rendered,
            "stored_u_containers_the_simulator_rendered": rendered_in_stored_u,
            "corrected_u_containers_the_simulator_rendered": rendered_in_corrected_u,
            "intervention_soundness": soundness,
        }
        (out_dir / "window_audit.json").write_text(json.dumps(report), encoding="utf-8")
        receipt.update({"status": "succeeded", "outcome": outcome, "window_frames": high - low,
                        "containers": len(subjects), "verdicts_change": comparison["verdicts_change"],
                        "corrected_adds": comparison["corrected_adds"], "corrected_removes": comparison["corrected_removes"],
                        "control_reproduces_generation": comparison["control_reproduces_generation"],
                        "stored_u_size": len(stored_invisible), "corrected_u_size": len(comparison["corrected_invisible"]),
                        "stored_u_rendered_count": len(rendered_in_stored_u),
                        "corrected_u_rendered_count": len(rendered_in_corrected_u),
                        "executed_interventions": soundness["executed_interventions"],
                        "interventions_sound_strict": soundness["sound_strict"],
                        "interventions_sound_by_role": soundness["sound_by_role"],
                        "episode_still_valid_strict": soundness["episode_still_valid_strict"],
                        "episode_still_valid_by_role": soundness["episode_still_valid_by_role"]})
    except AuditFailure as failure:
        receipt.update({"status": "failed", "outcome": failure.outcome, "detail": failure.detail[:400]})
    except Exception as exc:  # noqa: BLE001
        receipt.update({"status": "failed", "outcome": "episode_unreadable",
                        "detail": (repr(exc) + " | " + traceback.format_exc()[-800:])})
    receipt.update({"wall_seconds": round(time.time() - started, 1), "worker_pid": os.getpid()})
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return receipt


def stage_report(results: list[dict[str, Any]], *, commit: str, requested_workers: int, actual_workers: int,
                 worker_basis: str, wall_seconds: float) -> dict[str, Any]:
    succeeded = [r for r in results if r["status"] == "succeeded"]
    changed = [r for r in succeeded if r.get("verdicts_change")]
    return {
        "stage": "s1-02-window-audit", "code_commit": commit,
        "episodes_planned": len(results), "episodes_audited": len(succeeded),
        "episodes_by_outcome": {name: sum(1 for r in results if r.get("outcome") == name) for name in OUTCOMES},
        "control_reproduced_generation": sum(1 for r in succeeded if r.get("control_reproduces_generation")),
        "episodes_with_changed_verdicts": [
            {"episode_id": r["episode_id"], "adds": r.get("corrected_adds"), "removes": r.get("corrected_removes")}
            for r in changed],
        "containers_added_by_correction": sum(len(r.get("corrected_adds") or []) for r in succeeded),
        "containers_removed_by_correction": sum(len(r.get("corrected_removes") or []) for r in succeeded),
        "stored_u_total": sum(r.get("stored_u_size", 0) for r in succeeded),
        "corrected_u_total": sum(r.get("corrected_u_size", 0) for r in succeeded),
        # the pose-independent cross-check: a container the simulator was still drawing during the
        # window cannot honestly be called unobservable, whatever any projection says
        "stored_u_containers_the_simulator_rendered": sum(r.get("stored_u_rendered_count", 0) for r in succeeded),
        "corrected_u_containers_the_simulator_rendered": sum(r.get("corrected_u_rendered_count", 0) for r in succeeded),
        # S0-02 intervention_window: an intervention runs only when every container it involves is
        # invisible in every window frame, and a container re-entering view fails the whole episode
        "executed_interventions": sum(r.get("executed_interventions", 0) for r in succeeded),
        "interventions_still_sound_strict": sum(r.get("interventions_sound_strict", 0) for r in succeeded),
        "interventions_still_sound_by_role": sum(r.get("interventions_sound_by_role", 0) for r in succeeded),
        "episodes_with_interventions": sum(1 for r in succeeded if r.get("executed_interventions", 0) > 0),
        "episodes_still_valid_strict": sum(1 for r in succeeded
                                           if r.get("executed_interventions", 0) > 0 and r.get("episode_still_valid_strict")),
        "episodes_still_valid_by_role": sum(1 for r in succeeded
                                            if r.get("executed_interventions", 0) > 0 and r.get("episode_still_valid_by_role")),
        "failures": [{"episode_id": r["episode_id"], "outcome": r.get("outcome"), "detail": (r.get("detail") or "")[:200]}
                     for r in results if r["status"] != "succeeded"],
        "requested_workers": requested_workers, "actual_workers": actual_workers, "worker_basis": worker_basis,
        "wall_clock_seconds": round(wall_seconds, 1),
        "reads_only": True, "modifies_no_generated_file": True,
        "note": "a changed verdict is a finding for the user to rule on, never a correction applied here",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--episode-roots", required=True, help="comma-separated S1-02 output roots")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker-basis", default="")
    parser.add_argument("--allow-dirty", action="store_true", help="tests only")
    args = parser.parse_args()

    s1_04 = json.loads(S1_04_CONTRACT_PATH.read_text(encoding="utf-8"))
    closed = [name for name in REQUIRED_AUTHORIZATION if s1_04["authorization"].get(name) is not True]
    if closed:
        print(f"[s1-02-window-audit] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[s1-02-window-audit] refused: the checkout is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    policy = json.loads(S1_03_CONTRACT_PATH.read_text(encoding="utf-8"))["public_pose_correction"]
    out_root = Path(args.output_root).resolve()
    if out_root.exists() and any(out_root.iterdir()):
        print(f"[s1-02-window-audit] refused: output root exists and is not empty: {out_root}", file=sys.stderr)
        return 2
    out_root.mkdir(parents=True, exist_ok=True)

    tasks = []
    for root in args.episode_roots.split(","):
        for directory in sorted(Path(root).glob("procthor10k-*")):
            receipt_path = directory / "receipt.json"
            if not receipt_path.exists():
                continue
            source = json.loads(receipt_path.read_text(encoding="utf-8"))
            if source.get("status") != "succeeded":
                continue
            try:
                pp.correction_applies(source.get("code_commit"), policy)
            except pp.LeanPublicPoseError as exc:
                print(f"[s1-02-window-audit] refused: {directory.name}: {exc}", file=sys.stderr)
                return 2
            tasks.append({"episode_id": directory.name, "episode_root": str(directory),
                          "out": str(out_root / directory.name), "commit": commit,
                          "episode_code_commit": source["code_commit"], "pose_policy": policy})
    if not tasks:
        print("[s1-02-window-audit] no succeeded episodes under the given roots; refusing", file=sys.stderr)
        return 2

    actual = max(1, min(args.workers, len(tasks)))
    (out_root / "plan.json").write_text(json.dumps({
        "stage": "s1-02-window-audit", "commit": commit, "episodes": [t["episode_id"] for t in tasks],
        "pose_correction": {"decision_id": policy["decision_id"], "rule": policy["rule"]},
        "requested_workers": args.workers, "actual_workers": actual, "worker_basis": args.worker_basis,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1), encoding="utf-8")
    print(f"[s1-02-window-audit] {len(tasks)} episodes, {actual} workers, commit {commit[:12]}", flush=True)
    started = time.time()
    results: list[dict[str, Any]] = []
    if actual <= 1:
        for task in tasks:
            results.append(audit_episode(task))
            print(f"[s1-02-window-audit] {len(results)}/{len(tasks)} {results[-1]['episode_id']} "
                  f"{results[-1]['status']} {results[-1].get('outcome')}", flush=True)
    else:
        context = mp.get_context("spawn")
        with context.Pool(processes=actual) as pool:
            for receipt in pool.imap_unordered(audit_episode, tasks, chunksize=1):
                results.append(receipt)
                print(f"[s1-02-window-audit] {len(results)}/{len(tasks)} {receipt['episode_id']} "
                      f"{receipt['status']} {receipt.get('outcome')}", flush=True)
    results.sort(key=lambda r: r["episode_id"])
    report = stage_report(results, commit=commit, requested_workers=args.workers, actual_workers=actual,
                          worker_basis=args.worker_basis, wall_seconds=time.time() - started)
    (out_root / "s1_02_window_audit_receipt.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
