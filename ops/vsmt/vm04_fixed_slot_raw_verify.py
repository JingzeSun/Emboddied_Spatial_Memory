"""Read-only digest and public/private boundary verification of fixed raw slots."""

from __future__ import annotations

from pathlib import Path

import vm04_two_house_audit as audit


CAMERA_KEYS = {
    "frame_index", "time_s", "pose", "calibration",
    "last_action_success", "past_actions", "rgb_sha256", "depth_sha256",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def verify_public_frame(episode: Path, frame_index: int,
                        expected_camera_sha256: str) -> None:
    frame = episode / "public" / ("frame_%04d" % frame_index)
    require({path.name for path in frame.iterdir()} ==
            {"rgb.npy", "depth.npy", "camera.json"},
            "public frame contains missing or extra files")
    camera_path = frame / "camera.json"
    camera = audit.read_json(camera_path)
    require(set(camera) == CAMERA_KEYS and
            camera["frame_index"] == frame_index and
            camera["last_action_success"] is True,
            "public camera schema or frame order changed")
    require(audit.sha256(camera_path) == expected_camera_sha256 and
            audit.sha256(frame / "rgb.npy") == camera["rgb_sha256"] and
            audit.sha256(frame / "depth.npy") == camera["depth_sha256"],
            "public RGB-D/camera digest changed")


def verify_private_frame(episode: Path, frame_index: int,
                         expected_camera_sha256: str,
                         expected_mapping_sha256: str | None) -> None:
    frame = episode / "private" / ("frame_%04d" % frame_index)
    require({path.name for path in frame.iterdir()} ==
            {"instance_masks.npz", "mapping.json"},
            "private frame contains missing or extra files")
    mapping_path = frame / "mapping.json"
    mapping = audit.read_json(mapping_path)
    require(mapping["frame_index"] == frame_index and
            mapping["public_camera_sha256"] == expected_camera_sha256 and
            audit.sha256(frame / "instance_masks.npz") ==
            mapping["instance_masks_sha256"],
            "private mask/mapping or public binding changed")
    if expected_mapping_sha256 is not None:
        require(audit.sha256(mapping_path) == expected_mapping_sha256,
                "private mapping digest changed")


def verify_slot(episode: Path, task: dict, terminal_path: Path,
                expected_terminal_sha256: str) -> dict:
    """Verify one original terminal without changing or relabeling its files."""
    names = ("raw.receipt.json", "raw.failure.json", "raw.not_started.json")
    require(terminal_path.name in names and
            [name for name in names if (episode / name).is_file()] ==
            [terminal_path.name] and
            audit.sha256(terminal_path) == expected_terminal_sha256,
            "slot has multiple terminals or changed terminal bytes")
    terminal = audit.read_json(terminal_path)
    require(terminal["family_id"] == task["family_id"] and
            terminal["slot"] == task["slot"] and
            terminal["episode_id"] == task["episode_id"] and
            terminal["task_sha256"] == audit.canonical_sha256(task) and
            terminal["source_record_sha256"] == task["source_record_sha256"] and
            terminal["fixed_pose_sha256"] ==
            audit.canonical_sha256(task["fixed_pose"]) and
            terminal["constructed"] is False and
            terminal["semantic_positive_label_issued"] is False and
            terminal["relink_coverage_gap"] ==
            (task["program"] == "RELINK" and
             terminal_path.name != "raw.receipt.json"),
            "slot identity, failure coverage or label boundary changed")
    kind = terminal_path.name
    if kind == "raw.not_started.json":
        require(terminal["attempted"] is False and
                terminal["raw_complete"] is False and
                not (episode / "public").exists() and
                not (episode / "private").exists(),
                "not-started slot acquired attempted data")
        return {"kind": kind, "public_frames": 0, "private_frames": 0}

    require(terminal["attempted"] is True and
            terminal["raw_complete"] == (kind == "raw.receipt.json"),
            "attempt/raw terminal boundary changed")
    if kind == "raw.receipt.json":
        require(task["program"] != "RELINK" and
                terminal["frame_count"] == 32 and
                len(terminal["frame_receipts"]) == 32 and
                len(list((episode / "public").glob(
                    "frame_*/camera.json"))) == 32 and
                len(list((episode / "private").glob(
                    "frame_*/mapping.json"))) == 32 and
                terminal["construction_assessment_pending"] is True,
                "complete slot shape or RELINK stop rule changed")
        frames = terminal["frame_receipts"]
        for index, row in enumerate(frames):
            require(row["frame_index"] == index, "raw frame order changed")
            verify_public_frame(episode, index, row["public_camera_sha256"])
            verify_private_frame(episode, index,
                                 row["public_camera_sha256"],
                                 row["private_mapping_sha256"])
        require(audit.sha256(episode / "private/intervention.json") ==
                terminal["private_intervention_sha256"],
                "private intervention digest changed")
        return {"kind": kind, "public_frames": 32, "private_frames": 32}

    prefix_count = terminal["public_prefix_frame_count"]
    require(type(prefix_count) is int and 0 <= prefix_count <= 32 and
            terminal["raw_complete"] is False and
            terminal.get("relink_collision_observed_this_run") is False,
            "failure prefix or collision provenance changed")
    if terminal["schema_version"] == "vsmt-vm04-fixed-slot-process-failure-v1":
        cameras = terminal["public_prefix_camera_sha256"]
        require(len(cameras) == prefix_count,
                "process failure camera prefix changed")
        for index, expected in enumerate(cameras):
            verify_public_frame(episode, index, expected)
        private_rows = terminal["private_prefix_mapping_receipts"]
        for row in private_rows:
            index = row["frame_index"]
            require(type(index) is int and 0 <= index < prefix_count,
                    "process failure private frame has no public camera")
            verify_private_frame(episode, index, cameras[index],
                                 row["private_mapping_sha256"])
        # A killed worker can leave a partially written private frame; keep
        # the partial attempt rather than treating it as a complete episode.
        return {"kind": kind, "public_frames": prefix_count,
                "private_frames": len(private_rows)}

    require(terminal["schema_version"] ==
            "vsmt-vm04-fixed-slot-raw-failure-v1" and
            len(terminal["public_prefix_frame_receipts"]) == prefix_count and
            len(list((episode / "public").glob(
                "frame_*/camera.json"))) == prefix_count and
            len(list((episode / "private").glob(
                "frame_*/mapping.json"))) == prefix_count,
            "worker failure prefix changed")
    for index, row in enumerate(terminal["public_prefix_frame_receipts"]):
        require(row["frame_index"] == index, "failure frame order changed")
        verify_public_frame(episode, index, row["public_camera_sha256"])
        verify_private_frame(episode, index,
                             row["public_camera_sha256"],
                             row["private_mapping_sha256"])
    require(audit.sha256(episode / "private/construction-failure.json") ==
            terminal["private_failure_sha256"],
            "private failure digest changed")
    if (task["program"] == "RELINK" and terminal["reason"] ==
            "prior_D173_fixed_endpoint_collision"):
        require(prefix_count == 24 and
                terminal["registered_endpoint_receipt_sha256"] ==
                task["endpoint_failure_evidence"]["endpoint_receipt_sha256"],
                "original RELINK prefix or D-173 binding changed")
    return {"kind": kind, "public_frames": prefix_count,
            "private_frames": prefix_count}
