#!/usr/bin/env python3
"""Multi-worker recovery for the D-156 VM-04 public seal and private audit.

The source generation/materialization stage is immutable.  This entrypoint
binds that stage by digest, recomputes public profile tasks with independent
workers, atomically promotes complete task directories, and only then permits
the separately-invoked private evaluator to read private files.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Mapping, Sequence


OPS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = OPS_ROOT.parents[1]
if str(OPS_ROOT) not in sys.path:
    sys.path.insert(0, str(OPS_ROOT))

import vm04_two_house_audit as core  # noqa: E402


RECOVERY_CONFIG_PATH = (
    PROJECT_ROOT / "configs/vsmt/vm04_public_seal_parallel_recovery_v1.json"
)
PUBLIC_PROFILE_IDS = ("strict", "balanced", "permissive_capacity_upper_bound")
PUBLIC_ARTIFACT_ROOT = Path("public_audit_parallel_v1/completed")
PRIVATE_ARTIFACT_ROOT = Path("private_audit_parallel_v1/completed")


def load_recovery_config() -> dict[str, Any]:
    value = core.read_json(RECOVERY_CONFIG_PATH)
    core.require(
        value.get("version") == "vsmt-vm04-public-seal-parallel-recovery-v1",
        "wrong public-seal recovery config",
    )
    parallel = value.get("parallel_public_seal", {})
    core.require(parallel.get("requested_workers") == 12, "recovery worker count changed")
    core.require(parallel.get("maximum_wall_clock_seconds") is None,
                 "public-seal recovery may not have a wall-clock timeout")
    core.require(parallel.get("wall_clock_timeout_allowed") is False,
                 "public-seal recovery wall-clock timeout must remain disabled")
    core.require(value.get("training_authorized") is False, "recovery may not train")
    core.require(value.get("confirmation_authorized") is False,
                 "recovery may not open confirmation")
    return value


def choose_worker_count(requested: int, task_count: int, visible_cpus: int | None) -> int:
    """Use every frozen safe worker while never inventing unavailable CPUs."""

    core.require(type(requested) is int and requested >= 2, "multiple workers are required")
    core.require(type(task_count) is int and task_count >= 0, "invalid task count")
    cpus = visible_cpus if visible_cpus is not None else os.cpu_count()
    core.require(type(cpus) is int and cpus >= requested,
                 f"requested {requested} workers but only {cpus} CPUs are visible")
    return min(requested, task_count) if task_count else 0


def _source_stage(output_root: Path, recovery: Mapping[str, Any]) -> Path:
    source_code = str(recovery["source_stage"]["reviewed_code"])
    return core.stage_directory(output_root, source_code)


def verify_source_stage(stage: Path, recovery: Mapping[str, Any]) -> None:
    expected = recovery["source_stage"]
    files = {
        "materialize_receipt_sha256": stage / "materialize.receipt.json",
        "materialize_success_sha256": stage / "materialize.success.json",
        "public_episode_plan_sha256": stage / "public/episode_plan.json",
        "failed_public_resource_stop_sha256": stage / "public_audit/resource-stop.json",
        "started_sha256": stage / "started.json",
    }
    for key, path in files.items():
        core.require(path.is_file(), f"missing frozen source-stage file: {path}")
        core.require(core.sha256(path) == expected[key], f"source-stage digest changed: {key}")
    materialize, _ = core._marker(stage, "materialize")
    core.require(materialize["reviewed_code"] == expected["reviewed_code"],
                 "materialize receipt binds another code revision")
    core.require(
        materialize["completed_count"] == expected["materialized_complete_episode_count"]
        and materialize["failed_count"] == expected["materialized_failed_episode_count"],
        "materialized terminal counts changed",
    )


def _peak_rss_bytes() -> int:
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except (ImportError, OSError):
        return 0


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _task_receipt_files(root: Path, relative_paths: Sequence[str]) -> dict[str, str]:
    return {relative: core.sha256(root / relative) for relative in relative_paths}


def _promote_attempt(attempt: Path, final: Path) -> None:
    final.parent.mkdir(parents=True, exist_ok=True)
    core.require(not final.exists(), f"completed task already exists: {final}")
    os.replace(attempt, final)
    _fsync_directory(final.parent)


def run_public_profile_task(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Compute one public episode/profile task and atomically publish it."""

    started = time.monotonic()
    stage = Path(str(payload["stage"]))
    episode_id = str(payload["episode_id"])
    profile = dict(payload["profile"])
    profile_id = str(profile["profile_id"])
    parallel_root = stage / "public_audit_parallel_v1"
    attempt = parallel_root / "attempts" / (
        f"{episode_id.replace(':', '__')}--{profile_id}--pid{os.getpid()}--{time.time_ns()}"
    )
    final = stage / PUBLIC_ARTIFACT_ROOT / episode_id / profile_id
    attempt.mkdir(parents=True)
    try:
        materialized = stage / "materialized/public" / episode_id
        frames = [core.read_json(materialized / f"frame_{index:04d}.json")
                  for index in range(25)]
        result = core.replay_public_episode(
            frames, profile=profile, profile_id=profile_id,
            capacities=list(payload["capacities"]), values=dict(payload["values"]),
        )
        prior = result.pop("full_prior_memory")
        catalogs = result.pop("full_catalogs")
        core.write_new_json(attempt / "prior.json", prior)
        result["prior_memory_file_sha256"] = core.sha256(attempt / "prior.json")
        for capacity, catalog in catalogs.items():
            relative = f"catalogs/cap_{capacity}.json"
            core.write_new_json(attempt / relative, catalog)
            result["catalogs"][str(capacity)]["catalog_file_sha256"] = core.sha256(
                attempt / relative
            )
        core.write_new_json(attempt / "result.json", result)
        relative_paths = ["prior.json", "result.json"] + [
            f"catalogs/cap_{capacity}.json" for capacity in payload["capacities"]
        ]
        receipt = {
            "schema_version": "vsmt-vm04-public-profile-task-receipt-v1",
            "episode_id": episode_id,
            "profile_id": profile_id,
            "pid": os.getpid(),
            "file_sha256s": _task_receipt_files(attempt, relative_paths),
            "task_output_sha256": core.canonical_sha256(
                _task_receipt_files(attempt, relative_paths)
            ),
            "wall_seconds": time.monotonic() - started,
            "peak_RSS_bytes": _peak_rss_bytes(),
            "private_data_opened": False,
            "success": True,
        }
        core.write_new_json(attempt / "task.receipt.json", receipt)
        _promote_attempt(attempt, final)
        return {
            "task_id": f"{episode_id}/{profile_id}",
            "episode_id": episode_id,
            "profile_id": profile_id,
            "pid": os.getpid(),
            "wall_seconds": receipt["wall_seconds"],
            "peak_RSS_bytes": receipt["peak_RSS_bytes"],
            "task_receipt_sha256": core.sha256(final / "task.receipt.json"),
            "finished_monotonic_ns": time.monotonic_ns(),
        }
    except BaseException as error:
        core.write_new_json(attempt / "failure.json", {
            "episode_id": episode_id, "profile_id": profile_id,
            "error_type": type(error).__name__, "error": str(error),
            "pid": os.getpid(), "success": False,
        })
        raise


def validate_public_profile_task(
    stage: Path, episode_id: str, profile_id: str, capacities: Sequence[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = stage / PUBLIC_ARTIFACT_ROOT / episode_id / profile_id
    receipt_path = root / "task.receipt.json"
    core.require(receipt_path.is_file(), f"missing completed public task: {episode_id}/{profile_id}")
    receipt = core.read_json(receipt_path)
    core.require(receipt.get("success") is True, "public task is not successful")
    core.require(receipt.get("episode_id") == episode_id and receipt.get("profile_id") == profile_id,
                 "public task identity changed")
    expected_paths = {"prior.json", "result.json"} | {
        f"catalogs/cap_{capacity}.json" for capacity in capacities
    }
    digests = receipt.get("file_sha256s")
    core.require(type(digests) is dict and set(digests) == expected_paths,
                 "public task file manifest changed")
    for relative, digest in digests.items():
        core.require(core.sha256(root / relative) == digest,
                     f"public task file digest changed: {relative}")
    core.require(receipt["task_output_sha256"] == core.canonical_sha256(digests),
                 "public task output digest changed")
    result = core.read_json(root / "result.json")
    core.require(result["profile_id"] == profile_id, "public task result profile changed")
    core.require(result["prior_memory_file_sha256"] == digests["prior.json"],
                 "public prior binding changed")
    for capacity in capacities:
        core.require(
            result["catalogs"][str(capacity)]["catalog_file_sha256"]
            == digests[f"catalogs/cap_{capacity}.json"],
            f"public catalog binding changed at capacity {capacity}",
        )
    return result, receipt


def _run_worker_pool(
    worker: Callable[[Mapping[str, Any]], dict[str, Any]],
    payloads: Sequence[Mapping[str, Any]], *, requested_workers: int, label: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    actual = choose_worker_count(requested_workers, len(payloads), os.cpu_count())
    if actual == 0:
        return [], [], []
    context = multiprocessing.get_context("spawn")
    completed: list[dict[str, Any]] = []
    errors: list[str] = []

    def on_complete(value: dict[str, Any]) -> None:
        completed.append(value)
        print(
            f"{label}_PROGRESS completed={len(completed)}/{len(payloads)} "
            f"task={value['task_id']} pid={value['pid']} wall={value['wall_seconds']:.1f}s",
            flush=True,
        )

    def on_error(error: BaseException) -> None:
        errors.append(f"{type(error).__name__}: {error}")
        print(f"{label}_WORKER_FAILED {errors[-1]}", flush=True)

    pool = context.Pool(processes=actual)
    process_rows = [{"pid": process.pid} for process in pool._pool]
    async_results = [
        pool.apply_async(worker, (payload,), callback=on_complete, error_callback=on_error)
        for payload in payloads
    ]
    pool.close()
    pool.join()
    for row, process in zip(process_rows, pool._pool):
        row["exit_code"] = process.exitcode
    for result in async_results:
        try:
            result.get()
        except BaseException:
            pass
    core.require(not errors, f"{label} worker failures: {errors}")
    core.require(len(completed) == len(payloads), f"{label} lacks completed task results")
    order = [row["task_id"] for row in sorted(
        completed, key=lambda row: row["finished_monotonic_ns"]
    )]
    return completed, process_rows, order


def _write_run_receipt(root: Path, value: Mapping[str, Any]) -> Path:
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / f"run-{time.time_ns()}.json"
    core.write_new_json(path, dict(value))
    return path


def run_parallel_public_seal(reviewed_code: str, output_root: Path) -> None:
    recovery = load_recovery_config()
    config = core.assert_two_house_action_authorized(core.load_config(), action="generate")
    commit, bindings = core.verify_checkout(reviewed_code)
    stage = _source_stage(output_root, recovery)
    verify_source_stage(stage, recovery)
    core.require(not (stage / "public.seal.json").exists(), "public seal already exists")
    public_plan = core.validate_public_episode_plan(
        core.read_json(stage / "public/episode_plan.json")
    )
    profiles = config["audit_only_association_profiles"]["profiles"]
    core.require(tuple(row["profile_id"] for row in profiles) == PUBLIC_PROFILE_IDS,
                 "association profile order changed")
    values = config["audit_only_lifecycle_and_capacity_values"]
    capacities = list(values["candidate_capacity_replay_values"])
    requested = int(recovery["parallel_public_seal"]["requested_workers"])
    payloads: list[dict[str, Any]] = []
    resumed: list[str] = []
    for plan in public_plan["episodes"]:
        episode_id = plan["episode_id"]
        materialized = stage / "materialized/public" / episode_id
        if (materialized / "failure.json").exists():
            continue
        for profile in profiles:
            profile_id = profile["profile_id"]
            try:
                validate_public_profile_task(stage, episode_id, profile_id, capacities)
                resumed.append(f"{episode_id}/{profile_id}")
            except (FileNotFoundError, RuntimeError):
                payloads.append({
                    "stage": str(stage), "episode_id": episode_id,
                    "profile": profile, "capacities": capacities, "values": values,
                })
    total = len(payloads) + len(resumed)
    core.require(total == recovery["parallel_public_seal"]["expected_heavy_task_count"],
                 f"expected 48 public tasks, observed {total}")
    print(
        f"PUBLIC_SEAL_PARALLEL_START requested_workers={requested} "
        f"pending={len(payloads)} resumed={len(resumed)}",
        flush=True,
    )
    started = time.monotonic()
    completed, worker_exits, completion_order = _run_worker_pool(
        run_public_profile_task, payloads,
        requested_workers=requested, label="PUBLIC_SEAL",
    )
    parallel_root = stage / "public_audit_parallel_v1"
    run_receipt = {
        "schema_version": "vsmt-vm04-public-seal-parallel-run-receipt-v1",
        "current_execution_reviewed_code": commit,
        "source_stage_reviewed_code": recovery["source_stage"]["reviewed_code"],
        "requested_workers": requested,
        "actual_workers": choose_worker_count(requested, len(payloads), os.cpu_count()),
        "resumed_task_ids": sorted(resumed),
        "dispatched_task_count": len(payloads),
        "completed_tasks": sorted(completed, key=lambda row: row["task_id"]),
        "worker_exits": worker_exits,
        "completion_order": completion_order,
        "wall_seconds": time.monotonic() - started,
        "wall_clock_timeout_seconds": None,
        "success": True,
    }
    run_path = _write_run_receipt(parallel_root, run_receipt)
    rows: list[dict[str, Any]] = []
    canonical_tasks: list[str] = []
    for plan in public_plan["episodes"]:
        episode_id = plan["episode_id"]
        materialized = stage / "materialized/public" / episode_id
        profile_results: dict[str, Any] = {}
        receipts: list[dict[str, Any]] = []
        if (materialized / "failure.json").exists():
            status = "failed"
            failure_sha = core.sha256(materialized / "failure.json")
            for profile_id in PUBLIC_PROFILE_IDS:
                profile_results[profile_id] = core._empty_profile_result(profile_id)
        else:
            status = "constructed"
            failure_sha = None
            for profile_id in PUBLIC_PROFILE_IDS:
                result, receipt = validate_public_profile_task(
                    stage, episode_id, profile_id, capacities
                )
                profile_results[profile_id] = result
                receipts.append(receipt)
                canonical_tasks.append(f"{episode_id}/{profile_id}")
        rows.append({
            "episode_id": episode_id, "family_id": plan["family_id"],
            "slot": plan["slot"], "status": status,
            "failure_sha256": failure_sha, "profiles": profile_results,
            "capacity_audit": {
                profile_id: {
                    capacity: result["capacity_summary"]
                    for capacity, result in value["catalogs"].items()
                }
                for profile_id, value in profile_results.items()
            },
            "runtime": {
                "wall_seconds": sum(float(row["wall_seconds"]) for row in receipts),
                "peak_rss_bytes": max(
                    [int(row["peak_RSS_bytes"]) for row in receipts] or [0]
                ),
            },
        })
    seal = core.make_public_seal(
        rows, public_manifest_sha256=public_plan["manifest_sha256"],
        capacities=capacities, worker_completion_order=canonical_tasks,
    )
    core.write_new_json(stage / "public.seal.json", seal)
    process_manifest = {
        "schema_version": "vsmt-vm04-public-seal-parallel-processes-v1",
        "requested_workers": requested,
        "actual_workers": run_receipt["actual_workers"],
        "canonical_task_order": canonical_tasks,
        "actual_completion_order": completion_order,
        "worker_exits": worker_exits,
        "run_receipt_sha256": core.sha256(run_path),
        "success": True,
    }
    core.write_new_json(parallel_root / "processes.json", process_manifest)
    receipt = {
        "schema_version": "vsmt-vm04-two-house-public-seal-receipt-v2",
        "stage_id": core.STAGE_ID,
        "reviewed_code": commit,
        "source_stage_reviewed_code": recovery["source_stage"]["reviewed_code"],
        "bound_sha256": bindings,
        "recovery_config_sha256": core.sha256(RECOVERY_CONFIG_PATH),
        "materializer_receipt_sha256": core.sha256(stage / "materialize.receipt.json"),
        "public_artifact_root": str(PUBLIC_ARTIFACT_ROOT),
        "parallel_process_manifest_sha256": core.sha256(parallel_root / "processes.json"),
        "public_seal_sha256": core.sha256(stage / "public.seal.json"),
        "canonical_episode_digest": seal["canonical_episode_digest"],
        "episode_count": 36,
        "constructed_count": sum(row["status"] == "constructed" for row in rows),
        "failed_count": sum(row["status"] == "failed" for row in rows),
        "requested_workers": requested,
        "actual_workers": run_receipt["actual_workers"],
        "wall_clock_timeout_seconds": None,
        "success": True,
        "private_data_opened": False,
        "teacher_computed": False,
        "method_predictions_computed": False,
        "wall_seconds": time.monotonic() - started,
    }
    receipt_path = stage / "public-seal.receipt.json"
    core.write_new_json(receipt_path, receipt)
    core.write_new_json(stage / "public-seal.success.json", {
        "schema_version": "vsmt-vm04-two-house-public-seal-success-v2",
        "reviewed_code": commit,
        "source_stage_reviewed_code": recovery["source_stage"]["reviewed_code"],
        "receipt_sha256": core.sha256(receipt_path),
        "public_seal_sha256": seal["public_seal_sha256"],
        "success": True,
    })
    print(
        f"VM04_TWO_HOUSE_PUBLIC_SEAL_PARALLEL_OK stage={stage} "
        f"tasks={total} workers={run_receipt['actual_workers']}",
        flush=True,
    )


def run_private_episode_task(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one fixed episode after the public seal and atomically publish it."""

    started = time.monotonic()
    stage = Path(str(payload["stage"]))
    assignment = dict(payload["assignment"])
    public_row = dict(payload["public_row"])
    values = dict(payload["values"])
    episode_id = assignment["episode_id"]
    attempt = stage / "private_audit_parallel_v1/attempts" / (
        f"{episode_id.replace(':', '__')}--pid{os.getpid()}--{time.time_ns()}"
    )
    final = stage / PRIVATE_ARTIFACT_ROOT / episode_id
    attempt.mkdir(parents=True)
    try:
        base = {
            "episode_id": episode_id, "family_id": assignment["family_id"],
            "program": assignment["program"], "replicate": assignment["replicate"],
        }
        matcher: dict[str, Any] | None = None
        if public_row["status"] != "constructed":
            row = {
                **base, "constructed": False,
                "construction_failure_reason": "raw_or_materialization_failure",
                "canonical_reference_key_sha256_by_profile": None,
                "entity_retract_legal_at_margin_0_02": False,
                "entity_retract_legal_at_margin_0_05": False,
            }
        else:
            family_root = (
                stage / "execution" / assignment["family_id"] / "episodes" / episode_id
            )
            intervention = core.read_json(family_root / "private/intervention.json")
            targets = intervention["target_instance_ids"]
            crosswalks = [
                core.read_json(stage / "materialized/private" / episode_id /
                               f"frame_{index:04d}.json")
                for index in range(32)
            ]
            raw_mappings = [
                core.read_json(family_root / "private" / f"frame_{index:04d}" /
                               "mapping.json")
                for index in range(32)
            ]
            decision_frame = core.read_json(
                stage / "materialized/public" / episode_id / "frame_0024.json"
            )
            references: dict[str, str] = {}
            match_counts: dict[str, int] = {}
            strict_memory: Mapping[str, Any] | None = None
            strict_target_node: str | None = None
            construction_nodes: list[str] = []
            for profile_id in PUBLIC_PROFILE_IDS:
                profile = public_row["profiles"][profile_id]
                target_nodes = core._target_node_ids(
                    profile["bootstrap_trace"], crosswalks, targets[0]
                )
                if profile_id == "strict":
                    construction_nodes = target_nodes
                task_root = stage / PUBLIC_ARTIFACT_ROOT / episode_id / profile_id
                memory_path = task_root / "prior.json"
                core.require(core.sha256(memory_path) == profile["prior_memory_file_sha256"],
                             "sealed prior memory digest mismatch")
                memory = core.read_json(memory_path)
                open_nodes = core._open_entity_nodes(memory)
                latest_target = next(
                    (node_id for node_id in reversed(target_nodes) if node_id in open_nodes),
                    None,
                )
                current_target_index = 1 if assignment["program"] == "REPLACE" else 0
                current_regions = (
                    sorted({
                        region_id for target in targets
                        for region_id in core._target_regions(crosswalks[24], target)
                    })
                    if assignment["program"] == "SPLIT"
                    else core._target_regions(crosswalks[24], targets[current_target_index])
                )
                purpose_by_program = {
                    "BIND": ["bind"], "BIRTH": ["birth"],
                    "REACTIVATE": ["reactivate"],
                    "SPLIT": ["split-left", "split-right"],
                    "REPLACE": ["node-replace-birth"],
                }
                current_evidence = core._region_evidence_refs(
                    decision_frame, current_regions,
                    purpose_by_program.get(assignment["program"], ["unused"]),
                ) if assignment["program"] in purpose_by_program else set()
                incident_edges = {
                    str(edge["edge_id"]) for edge in memory["edges"]
                    if edge.get("valid_to") is None and latest_target in {
                        str(edge["source"]), str(edge["target"])
                    }
                }
                target_version = (
                    str(open_nodes[latest_target]["node_version_id"])
                    if latest_target in open_nodes else None
                )
                catalog_path = task_root / "catalogs/cap_64.json"
                core.require(
                    core.sha256(catalog_path)
                    == profile["catalogs"]["64"]["catalog_file_sha256"],
                    "sealed capacity-64 catalog digest mismatch",
                )
                reference, count = core.strict_reference_key(
                    core.read_json(catalog_path), program=assignment["program"],
                    target_node_ids=(
                        target_nodes[-2:] if assignment["program"] == "MERGE"
                        else ([] if latest_target is None else [latest_target])
                    ),
                    current_evidence_refs=current_evidence,
                    incident_edge_ids=incident_edges,
                    target_node_version_id=target_version,
                )
                references[profile_id] = reference
                match_counts[profile_id] = count
                if profile_id == "strict":
                    strict_memory = memory
                    strict_target_node = latest_target
            constructed, failure_reason = core.assess_private_construction(
                program=assignment["program"], target_ids=targets,
                crosswalks=crosswalks, raw_mappings=raw_mappings,
                target_node_ids=construction_nodes,
            )
            retract = assignment["program"] == "RETRACT" and constructed
            row = {
                **base, "constructed": constructed,
                "construction_failure_reason": failure_reason,
                "canonical_reference_key_sha256_by_profile": references if constructed else None,
                "entity_retract_legal_at_margin_0_02": bool(
                    retract and strict_memory is not None and core._retract_legal_at_margin(
                        strict_memory, strict_target_node, decision_frame,
                        margin_m=0.02, values=values,
                    )
                ),
                "entity_retract_legal_at_margin_0_05": bool(
                    retract and strict_memory is not None and core._retract_legal_at_margin(
                        strict_memory, strict_target_node, decision_frame,
                        margin_m=0.05, values=values,
                    )
                ),
            }
            matcher = {
                "episode_id": episode_id,
                "canonical_reference_match_count_by_profile": match_counts,
                "reference_is_existing_candidate_only_when_match_count_is_one": True,
            }
        core.write_new_json(attempt / "result.json", row)
        paths = ["result.json"]
        if matcher is not None:
            core.write_new_json(attempt / "matcher.json", matcher)
            paths.append("matcher.json")
        receipt = {
            "schema_version": "vsmt-vm04-private-episode-task-receipt-v1",
            "episode_id": episode_id,
            "pid": os.getpid(),
            "file_sha256s": _task_receipt_files(attempt, paths),
            "wall_seconds": time.monotonic() - started,
            "peak_RSS_bytes": _peak_rss_bytes(),
            "private_data_opened": public_row["status"] == "constructed",
            "success": True,
        }
        core.write_new_json(attempt / "task.receipt.json", receipt)
        _promote_attempt(attempt, final)
        return {
            "task_id": episode_id, "pid": os.getpid(),
            "wall_seconds": receipt["wall_seconds"],
            "peak_RSS_bytes": receipt["peak_RSS_bytes"],
            "task_receipt_sha256": core.sha256(final / "task.receipt.json"),
            "finished_monotonic_ns": time.monotonic_ns(),
        }
    except BaseException as error:
        core.write_new_json(attempt / "failure.json", {
            "episode_id": episode_id, "error_type": type(error).__name__,
            "error": str(error), "pid": os.getpid(), "success": False,
        })
        raise


def validate_private_episode_task(stage: Path, episode_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    root = stage / PRIVATE_ARTIFACT_ROOT / episode_id
    receipt = core.read_json(root / "task.receipt.json")
    core.require(receipt.get("success") is True and receipt.get("episode_id") == episode_id,
                 "private task identity or success changed")
    files = receipt.get("file_sha256s")
    core.require(type(files) is dict and "result.json" in files,
                 "private task file manifest changed")
    for relative, digest in files.items():
        core.require(core.sha256(root / relative) == digest,
                     f"private task digest changed: {episode_id}/{relative}")
    row = core.read_json(root / "result.json")
    matcher = core.read_json(root / "matcher.json") if "matcher.json" in files else None
    return row, matcher


def run_parallel_private_evaluation(reviewed_code: str, output_root: Path) -> None:
    recovery = load_recovery_config()
    config = core.assert_two_house_action_authorized(core.load_config(), action="private-eval")
    commit, bindings = core.verify_checkout(reviewed_code)
    stage = _source_stage(output_root, recovery)
    verify_source_stage(stage, recovery)
    public_receipt, _ = core._marker(stage, "public-seal")
    core.require(
        public_receipt.get("reviewed_code") == recovery["source_stage"]["reviewed_code"],
        "public seal was not produced by the registered source stage",
    )
    core.require(public_receipt["public_seal_sha256"] == core.sha256(stage / "public.seal.json"),
                 "public seal changed before private opening")
    core.require(not (stage / "private-evaluation.json").exists(),
                 "private evaluation already exists")
    seal = core.read_json(stage / "public.seal.json")
    plans = core.validate_episode_plans({
        "public": core.read_json(stage / "public/episode_plan.json"),
        "private": core.read_json(stage / "private/episode_plan.json"),
    })
    public_by_id = {row["episode_id"]: row for row in seal["episodes"]}
    values = config["audit_only_lifecycle_and_capacity_values"]
    requested = int(recovery["parallel_public_seal"]["requested_workers"])
    payloads: list[dict[str, Any]] = []
    resumed: list[str] = []
    for assignment in plans["private"]["assignments"]:
        episode_id = assignment["episode_id"]
        try:
            validate_private_episode_task(stage, episode_id)
            resumed.append(episode_id)
        except (FileNotFoundError, RuntimeError):
            payloads.append({
                "stage": str(stage), "assignment": assignment,
                "public_row": public_by_id[episode_id], "values": values,
            })
    print(
        f"PRIVATE_EVAL_PARALLEL_START requested_workers={requested} "
        f"pending={len(payloads)} resumed={len(resumed)}",
        flush=True,
    )
    started = time.monotonic()
    completed, worker_exits, completion_order = _run_worker_pool(
        run_private_episode_task, payloads,
        requested_workers=requested, label="PRIVATE_EVAL",
    )
    rows: list[dict[str, Any]] = []
    matcher_records: list[dict[str, Any]] = []
    for assignment in plans["private"]["assignments"]:
        row, matcher = validate_private_episode_task(stage, assignment["episode_id"])
        rows.append(row)
        if matcher is not None:
            matcher_records.append(matcher)
    evaluation = core.evaluate_private_recall(seal, rows)
    core.write_new_json(stage / "private-evaluation.json", evaluation)
    matcher_path = stage / "private/matcher-receipt.json"
    core.write_new_json(matcher_path, {
        "schema_version": "vsmt-vm04-two-house-private-matcher-receipt-v2",
        "records": matcher_records,
        "strict_reference_uses_preexisting_sealed_candidates_only": True,
    })
    parallel_root = stage / "private_audit_parallel_v1"
    run_path = _write_run_receipt(parallel_root, {
        "schema_version": "vsmt-vm04-private-eval-parallel-run-receipt-v1",
        "current_execution_reviewed_code": commit,
        "source_stage_reviewed_code": recovery["source_stage"]["reviewed_code"],
        "requested_workers": requested,
        "actual_workers": choose_worker_count(requested, len(payloads), os.cpu_count()),
        "resumed_task_ids": sorted(resumed),
        "completed_tasks": sorted(completed, key=lambda row: row["task_id"]),
        "completion_order": completion_order,
        "worker_exits": worker_exits,
        "wall_seconds": time.monotonic() - started,
        "wall_clock_timeout_seconds": None,
        "success": True,
    })
    core.write_new_json(parallel_root / "processes.json", {
        "schema_version": "vsmt-vm04-private-eval-parallel-processes-v1",
        "requested_workers": requested,
        "actual_workers": choose_worker_count(requested, len(payloads), os.cpu_count()),
        "canonical_episode_order": [row["episode_id"] for row in rows],
        "actual_completion_order": completion_order,
        "worker_exits": worker_exits,
        "run_receipt_sha256": core.sha256(run_path),
        "success": True,
    })
    receipt = {
        "schema_version": "vsmt-vm04-two-house-private-eval-receipt-v2",
        "stage_id": core.STAGE_ID,
        "reviewed_code": commit,
        "source_stage_reviewed_code": recovery["source_stage"]["reviewed_code"],
        "bound_sha256": bindings,
        "public_seal_file_sha256": core.sha256(stage / "public.seal.json"),
        "evaluation_file_sha256": core.sha256(stage / "private-evaluation.json"),
        "matcher_receipt_sha256": core.sha256(matcher_path),
        "parallel_process_manifest_sha256": core.sha256(parallel_root / "processes.json"),
        "episode_count": 36,
        "constructed_count": sum(row["constructed"] for row in rows),
        "failed_construction_count": sum(not row["constructed"] for row in rows),
        "requested_workers": requested,
        "actual_workers": choose_worker_count(requested, len(payloads), os.cpu_count()),
        "private_opened_after_public_seal": True,
        "teacher_ranking_or_probability_computed": False,
        "method_predictions_or_effects_computed": False,
        "wall_clock_timeout_seconds": None,
        "wall_seconds": time.monotonic() - started,
        "success": True,
    }
    receipt_path = stage / "private-eval.receipt.json"
    core.write_new_json(receipt_path, receipt)
    core.write_new_json(stage / "private-eval.success.json", {
        "schema_version": "vsmt-vm04-two-house-private-eval-success-v2",
        "reviewed_code": commit,
        "source_stage_reviewed_code": recovery["source_stage"]["reviewed_code"],
        "receipt_sha256": core.sha256(receipt_path),
        "evaluation_sha256": evaluation["evaluation_sha256"],
        "success": True,
    })
    print(
        f"VM04_TWO_HOUSE_PRIVATE_EVAL_PARALLEL_OK stage={stage} "
        f"constructed={receipt['constructed_count']} workers={receipt['actual_workers']}",
        flush=True,
    )


def report_status(output_root: Path) -> None:
    recovery = load_recovery_config()
    stage = _source_stage(output_root, recovery)
    verify_source_stage(stage, recovery)
    capacities = [16, 32, 64]
    public_complete = 0
    private_complete = 0
    for episode_root in (stage / PUBLIC_ARTIFACT_ROOT).glob("*"):
        if not episode_root.is_dir():
            continue
        for profile_id in PUBLIC_PROFILE_IDS:
            try:
                validate_public_profile_task(stage, episode_root.name, profile_id, capacities)
                public_complete += 1
            except (FileNotFoundError, RuntimeError):
                pass
    for episode_root in (stage / PRIVATE_ARTIFACT_ROOT).glob("*"):
        if not episode_root.is_dir():
            continue
        try:
            validate_private_episode_task(stage, episode_root.name)
            private_complete += 1
        except (FileNotFoundError, RuntimeError):
            pass
    print(json.dumps({
        "stage": str(stage),
        "public_profile_tasks_complete": public_complete,
        "public_profile_tasks_expected": 48,
        "public_seal_complete": (stage / "public-seal.success.json").is_file(),
        "private_episode_tasks_complete": private_complete,
        "private_episode_tasks_expected": 36,
        "private_evaluation_complete": (stage / "private-eval.success.json").is_file(),
    }, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("status", "public-seal", "private-eval"))
    parser.add_argument("--reviewed-code")
    parser.add_argument(
        "--output-root", type=Path, default=Path("/root/autodl-tmp/vsmt_outputs")
    )
    arguments = parser.parse_args()
    if arguments.mode == "status":
        report_status(arguments.output_root)
        return
    core.require(arguments.reviewed_code is not None, "--reviewed-code is required")
    if arguments.mode == "public-seal":
        run_parallel_public_seal(arguments.reviewed_code, arguments.output_root)
    else:
        run_parallel_private_evaluation(arguments.reviewed_code, arguments.output_root)


if __name__ == "__main__":
    main()
