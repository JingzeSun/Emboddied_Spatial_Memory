#!/usr/bin/env bash
# Single mutable server handoff entrypoint for CPMT.
# Current stage: read-only S4 cost inventory of the existing v5 train arrays.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v3_s4_v5_cost_inventory"
CPMT_REQUIRED_ANCESTOR="70355ac"
CPMT_EXPECTED_GENERATION_COMMIT="72afa7da33e0465e6e45d57e2a9675248ac65447"
CPMT_EXPECTED_PROTOCOL="34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v5-shared-static-preflight"
CPMT_EXPECTED_ARRAYS_DIGEST="f68205b58a6d4a97f92e3432b0d1d3515a5b739a5b226994e4030515b930d7b0"
# This timing came from the successful server terminal output for the same
# manifest. The old manifest did not persist wall time, so it is explicitly
# labelled as operator-observed rather than machine-recovered provenance.
CPMT_OPERATOR_OBSERVED_G40_SECONDS="42.5"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_GIT_STATUS="$(git -C "$CPMT_REPO_DIR" status --porcelain)" || exit 2
CPMT_BASE_DIR="$CPMT_REPO_DIR/outputs/m1-v2-v5-shared-static-preflight-g40-72afa7d"
CPMT_ARRAYS_PATH="$CPMT_BASE_DIR/train.npz"
CPMT_MANIFEST_PATH="$CPMT_BASE_DIR/train.manifest.json"
CPMT_SHARD_DIR="$CPMT_BASE_DIR/train_shards"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED stage=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

printf "SERVER_STEP_BEGIN stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "mode=read_only_existing_train_arrays test_access=false\n"

[[ -z "$CPMT_GIT_STATUS" ]] || cpmt_fail "working_tree_not_clean"
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor \
  "$CPMT_REQUIRED_ANCESTOR" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "required_result_commit_not_in_history"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
[[ -f "$CPMT_ARRAYS_PATH" ]] || cpmt_fail "train_arrays_missing"
[[ -f "$CPMT_MANIFEST_PATH" ]] || cpmt_fail "train_manifest_missing"

if ! python - \
  "$CPMT_REPO_DIR" "$CPMT_ARRAYS_PATH" "$CPMT_MANIFEST_PATH" \
  "$CPMT_SHARD_DIR" "$CPMT_EXPECTED_GENERATION_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" \
  "$CPMT_EXPECTED_ARRAYS_DIGEST" "$CPMT_OPERATOR_OBSERVED_G40_SECONDS" <<'PY'
import json
import os
import resource
import sys
import zipfile
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
shard_dir = Path(sys.argv[4])
expected_generation_commit = sys.argv[5]
expected_protocol = sys.argv[6]
expected_dataset = sys.argv[7]
expected_digest = sys.argv[8]
observed_g40_seconds = float(sys.argv[9])

sys.path.insert(0, str(repo / "src"))
from cpmt.m1_protocol import load_and_validate, protocol_sha256
from cpmt.m1_rollout import TEMPLATE_FAMILY
from cpmt.run_provenance import arrays_sha256


def gib(value: float) -> float:
    return float(value / (1024 ** 3))


def current_rss_bytes() -> int | None:
    status_path = Path("/proc/self/status")
    if not status_path.exists():
        return None
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return None


config = load_and_validate(repo / "configs" / "m1_hard_condition.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
assert protocol_sha256(config) == expected_protocol
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["arrays_digest"] == expected_digest
assert manifest["generation_provenance"]["git_commit"] == expected_generation_commit
assert manifest["generation_provenance"]["git_dirty"] is False
assert manifest["split"] == "train"
assert manifest["paired_groups"] == 40
assert manifest["decisions"] == 1680
assert manifest["online_chain_decisions"] == 1600
assert manifest["recovery_training_examples"] == 80
assert manifest["formal_run"] is False
assert manifest["test_generated"] is False

rss_before = current_rss_bytes()
with np.load(arrays_path, allow_pickle=True) as archive:
    arrays = {key: archive[key] for key in archive.files}
rss_after = current_rss_bytes()
assert arrays_sha256(arrays) == expected_digest

archive_members = {}
with zipfile.ZipFile(arrays_path) as handle:
    for item in handle.infolist():
        archive_members[Path(item.filename).stem] = {
            "stored_bytes": int(item.compress_size),
            "npy_bytes": int(item.file_size),
        }

array_rows = []
for name, value in arrays.items():
    member = archive_members.get(name, {})
    array_rows.append({
        "name": name,
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "ndarray_nbytes": int(value.nbytes),
        "archive_stored_bytes": int(member.get("stored_bytes", 0)),
        "archive_npy_bytes": int(member.get("npy_bytes", 0)),
        "object_dtype": bool(value.dtype.hasobject),
    })
array_rows.sort(key=lambda row: row["archive_stored_bytes"], reverse=True)

merged_bytes = arrays_path.stat().st_size
shard_paths = sorted(shard_dir.glob("*.npz")) if shard_dir.is_dir() else []
shard_bytes = sum(path.stat().st_size for path in shard_paths)
ndarray_nbytes = sum(row["ndarray_nbytes"] for row in array_rows)
npy_payload_bytes = sum(row["archive_npy_bytes"] for row in array_rows)
object_arrays = [row["name"] for row in array_rows if row["object_dtype"]]

families = list(config["data"]["scenario_families"])
implemented_families = sorted(set(TEMPLATE_FAMILY.values()))
missing_families = sorted(set(families) - set(implemented_families))
assert families == [f"C{index:02d}" for index in range(12)]
assert missing_families == ["C09", "C10", "C11"]

groups_per_family = config["data"]["groups_per_family"]
split_groups = {
    split: int(groups_per_family[split]) * len(families)
    for split in ("train", "validation", "test")
}
rows_per_group = manifest["decisions"] / manifest["paired_groups"]
online_rows_per_group = (
    manifest["online_chain_decisions"] / manifest["paired_groups"]
)
recovery_rows_per_group = (
    manifest["recovery_training_examples"] / manifest["paired_groups"]
)
assert rows_per_group == 42.0
assert online_rows_per_group == 40.0
assert recovery_rows_per_group == 2.0

projections = {}
for split, group_count in split_groups.items():
    factor = group_count / manifest["paired_groups"]
    rows = int(group_count * rows_per_group)
    projections[split] = {
        "paired_groups": group_count,
        "learning_rows": rows,
        "online_rows": int(group_count * online_rows_per_group),
        "recovery_rows": int(group_count * recovery_rows_per_group),
        "candidate_slots_k16": rows * int(config["candidates"]["budget_k"]),
        "merged_array_gib_linear_reference": gib(merged_bytes * factor),
        "merged_plus_retained_shards_gib_linear_reference": gib(
            (merged_bytes + shard_bytes) * factor
        ) if shard_paths else None,
        "generation_hours_linear_reference": (
            observed_g40_seconds * factor / 3600.0
        ),
    }

all_groups = sum(split_groups.values())
all_factor = all_groups / manifest["paired_groups"]
all_rows = int(all_groups * rows_per_group)
projections["all_splits"] = {
    "paired_groups": all_groups,
    "learning_rows": all_rows,
    "candidate_slots_k16": all_rows * int(config["candidates"]["budget_k"]),
    "merged_array_gib_linear_reference": gib(merged_bytes * all_factor),
    "merged_plus_retained_shards_gib_linear_reference": gib(
        (merged_bytes + shard_bytes) * all_factor
    ) if shard_paths else None,
    "generation_hours_linear_reference": observed_g40_seconds * all_factor / 3600.0,
}

report = {
    "schema_version": "cpmt-m1-s4-cost-inventory-v1",
    "status": "read_only_reference_inventory_not_v3_benchmark",
    "formal_run": False,
    "test_access": False,
    "test_generated": False,
    "source": {
        "arrays": str(arrays_path),
        "manifest": str(manifest_path),
        "protocol_sha256": expected_protocol,
        "dataset_version": expected_dataset,
        "arrays_digest": expected_digest,
        "paired_groups": manifest["paired_groups"],
        "generation_seconds": observed_g40_seconds,
        "generation_seconds_provenance": (
            "operator_observed_successful_server_terminal_output; not persisted "
            "in v5 manifest"
        ),
    },
    "contract_conformance": {
        "configured_families": families,
        "implemented_rollout_families": implemented_families,
        "missing_rollout_families": missing_families,
        "groups_per_family": groups_per_family,
        "minimum_test_support_per_family": config["data"][
            "minimum_test_support_per_family"
        ],
        "current_cli_paired_groups_semantics": "mixed_total_not_per_family",
    },
    "observed_storage": {
        "merged_npz_bytes": merged_bytes,
        "merged_npz_gib": gib(merged_bytes),
        "retained_shard_count": len(shard_paths),
        "retained_shard_bytes": shard_bytes,
        "retained_shard_gib": gib(shard_bytes),
        "ndarray_nbytes_pointer_based_for_object_dtype": ndarray_nbytes,
        "npy_payload_bytes": npy_payload_bytes,
        "object_dtype_arrays": object_arrays,
        "rss_before_loading_bytes": rss_before,
        "rss_after_loading_bytes": rss_after,
        "process_peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
    },
    "per_group_reference": {
        "learning_rows": rows_per_group,
        "online_rows": online_rows_per_group,
        "recovery_rows": recovery_rows_per_group,
        "candidate_slots_k16": rows_per_group * int(config["candidates"]["budget_k"]),
        "merged_npz_bytes": merged_bytes / manifest["paired_groups"],
        "retained_shard_bytes": (
            shard_bytes / len(shard_paths) if shard_paths else None
        ),
        "generation_seconds": observed_g40_seconds / manifest["paired_groups"],
    },
    "linear_reference_projections": projections,
    "largest_archive_members": array_rows[:12],
    "limits": [
        "Projection is based on v5 and is not a v3 benchmark.",
        "C09-C11, live now/collateral, and cross-candidate attention may change cost.",
        "Linear time assumes the observed 8-worker throughput continues.",
        "Object-array ndarray.nbytes counts pointers, so RSS and archive bytes are also reported.",
        "Training cost is not inferred from fixed-step scorer diagnostics.",
    ],
}

print("COST_INPUT_OK arrays_digest={}".format(expected_digest))
print("CONFORMANCE_MISSING_FAMILIES {}".format(" ".join(missing_families)))
print(
    "OBSERVED_G40 merged_bytes={} shard_count={} shard_bytes={} "
    "rss_after_bytes={} generation_seconds={:.1f}".format(
        merged_bytes, len(shard_paths), shard_bytes, rss_after,
        observed_g40_seconds,
    )
)
for split in ("train", "validation", "test", "all_splits"):
    row = projections[split]
    print(
        "LINEAR_REFERENCE split={} groups={} rows={} candidate_slots={} "
        "merged_gib={:.3f} merged_plus_shards_gib={} generation_hours={:.3f}".format(
            split,
            row["paired_groups"],
            row["learning_rows"],
            row["candidate_slots_k16"],
            row["merged_array_gib_linear_reference"],
            (
                "{:.3f}".format(row["merged_plus_retained_shards_gib_linear_reference"])
                if row["merged_plus_retained_shards_gib_linear_reference"] is not None
                else "not_available"
            ),
            row["generation_hours_linear_reference"],
        )
    )
print("LARGEST_ARRAY_MEMBERS")
for row in array_rows[:12]:
    print(
        "  {} shape={} dtype={} archive_bytes={} ndarray_nbytes={}".format(
            row["name"], row["shape"], row["dtype"],
            row["archive_stored_bytes"], row["ndarray_nbytes"],
        )
    )
print("COST_INVENTORY_JSON={}".format(json.dumps(report, separators=(",", ":"))))
PY
then
  cpmt_fail "cost_inventory_failed"
fi

[[ -z "$(git -C "$CPMT_REPO_DIR" status --porcelain)" ]] || \
  cpmt_fail "read_only_stage_changed_worktree"
printf "SERVER_STEP_OK stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=return_terminal_output_for_D_039_resource_decision\n"
