#!/usr/bin/env bash
# Mutable CPMT server handoff. Run one phase at a time:
#   bash ops/run_next_server_step.sh full_test
#   bash ops/run_next_server_step.sh health_benchmark

set -uo pipefail

CPMT_SERVER_PHASE="${1:-}"
CPMT_REQUIRED_ANCESTOR="9afa6ab"
CPMT_EXPECTED_PROTOCOL="ccae7003a7d6e1087d348f4b1e9acae9991857ac0ecf64196dca5d2e8d31b0db"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_HEALTH_PAIRED_GROUPS="12"
CPMT_WORKERS="${CPMT_WORKERS:-16}"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_SHORT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 HEAD)" || exit 2
CPMT_PREFLIGHT_DIR="$CPMT_REPO_DIR/outputs/m1-v5-server-preflight"
CPMT_TEST_MARKER="$CPMT_PREFLIGHT_DIR/full_test.ok"
CPMT_HEALTH_DIR="$CPMT_REPO_DIR/outputs/m1-v5-v8-health-g12-$CPMT_SHORT_COMMIT"
CPMT_HEALTH_ARRAYS="$CPMT_HEALTH_DIR/train.npz"
CPMT_HEALTH_MANIFEST="$CPMT_HEALTH_DIR/train.manifest.json"
CPMT_HEALTH_REPORT="$CPMT_REPO_DIR/results/m1_v5_s4_v8_health_benchmark.json"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED phase=%s reason=%s\n" \
    "$CPMT_SERVER_PHASE" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$CPMT_SERVER_PHASE" == "full_test" \
   || "$CPMT_SERVER_PHASE" == "health_benchmark" ]] || \
  cpmt_fail "usage_full_test_or_health_benchmark"
[[ "$CPMT_WORKERS" =~ ^[1-9][0-9]*$ ]] || cpmt_fail "invalid_worker_count"
[[ -z "$(git -C "$CPMT_REPO_DIR" status --porcelain)" ]] || \
  cpmt_fail "working_tree_not_clean"
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor \
  "$CPMT_REQUIRED_ANCESTOR" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "required_protocol_commit_not_in_history"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"

printf "SERVER_STEP_BEGIN phase=%s\n" "$CPMT_SERVER_PHASE"
printf "repo=%s\ncurrent_commit=%s\n" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "test_access=false dataset=%s\n" "$CPMT_EXPECTED_DATASET"

if ! python - "$CPMT_REPO_DIR" "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" <<'PY'
import sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / "src"))
from cpmt.m1_protocol import load_and_validate, protocol_sha256

config = load_and_validate(repo / "configs" / "m1_hard_condition.json")
assert protocol_sha256(config) == sys.argv[2]
assert config["data"]["dataset_version"] == sys.argv[3]
assert config["data"]["scenario_families"] == [f"C{i:02d}" for i in range(12)]
assert config["data"]["paired_groups"] == {
    "train": 1000, "validation": 200, "test": 200,
}
assert config["data"]["generation_count_semantics"] == (
    "total_mixed_paired_groups_each_group_contains_all_families"
)
assert config["resources"]["formal_run_wall_time_policy"] == (
    "measure_and_report_without_repository_fixed_cap"
)
assert config["energy"]["now_normalization"].startswith(
    "fixed_natural_range_without_candidate_spread_scaling"
)
assert config["energy"]["posterior_influence_audit"]["primary_interpretation"] == (
    "posterior_distribution_not_argmax_only"
)
print("PROTOCOL_INPUT_OK sha256={}".format(sys.argv[2]))
PY
then
  cpmt_fail "protocol_validation_failed"
fi

mkdir -p "$CPMT_PREFLIGHT_DIR"

if [[ "$CPMT_SERVER_PHASE" == "full_test" ]]; then
  CPMT_TEST_LOG="$CPMT_PREFLIGHT_DIR/full_test.log"
  (
    cd "$CPMT_REPO_DIR" || exit 2
    python -m unittest discover -s tests -p 'test_*.py'
  ) 2>&1 | tee "$CPMT_TEST_LOG"
  CPMT_TEST_EXIT="${PIPESTATUS[0]}"
  printf "FULL_TEST_EXIT=%s\n" "$CPMT_TEST_EXIT"
  [[ "$CPMT_TEST_EXIT" -eq 0 ]] || cpmt_fail "full_test_failed"
  {
    printf "commit=%s\n" "$CPMT_CURRENT_COMMIT"
    printf "protocol=%s\n" "$CPMT_EXPECTED_PROTOCOL"
  } > "$CPMT_TEST_MARKER"
  printf "SERVER_STEP_OK phase=full_test\n"
  printf "NEXT=run_health_benchmark_only_after_FULL_TEST_EXIT_0\n"
  exit 0
fi

[[ -f "$CPMT_TEST_MARKER" ]] || cpmt_fail "full_test_marker_missing"
grep -Fxq "commit=$CPMT_CURRENT_COMMIT" "$CPMT_TEST_MARKER" || \
  cpmt_fail "full_test_was_not_for_current_commit"
grep -Fxq "protocol=$CPMT_EXPECTED_PROTOCOL" "$CPMT_TEST_MARKER" || \
  cpmt_fail "full_test_protocol_mismatch"

if [[ -f "$CPMT_HEALTH_MANIFEST" ]]; then
  printf "HEALTH_INPUT_REUSE manifest=%s\n" "$CPMT_HEALTH_MANIFEST"
else
  mkdir -p "$CPMT_HEALTH_DIR"
  (
    cd "$CPMT_REPO_DIR" || exit 2
    python scripts/generate_m1_parallel.py \
      --config configs/m1_hard_condition.json \
      --split train \
      --paired-groups "$CPMT_HEALTH_PAIRED_GROUPS" \
      --future-hash-bins 32 \
      --workers "$CPMT_WORKERS" \
      --out "$CPMT_HEALTH_ARRAYS"
  )
  CPMT_GENERATION_EXIT="$?"
  printf "HEALTH_GENERATION_EXIT=%s\n" "$CPMT_GENERATION_EXIT"
  [[ "$CPMT_GENERATION_EXIT" -eq 0 ]] || \
    cpmt_fail "health_generation_or_teacher_gate_failed"
fi

if ! python - \
  "$CPMT_REPO_DIR" "$CPMT_HEALTH_ARRAYS" "$CPMT_HEALTH_MANIFEST" \
  "$CPMT_HEALTH_REPORT" "$CPMT_CURRENT_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
report_path = Path(sys.argv[4])
commit = sys.argv[5]
expected_protocol = sys.argv[6]
expected_dataset = sys.argv[7]

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
assert manifest["schema_version"] == "cpmt-m1-generation-manifest-v5"
assert manifest["runner"] == "generate_m1_parallel_v5"
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["split"] == "train"
assert manifest["configured_scenario_families"] == [f"C{i:02d}" for i in range(12)]
assert manifest["paired_groups_total"] == 12
assert manifest["paired_group_count_semantics"] == (
    "total_mixed_groups_each_group_contains_all_families"
)
assert set(manifest["causal_paired_group_support_by_family"].values()) == {12}
assert manifest["family_mechanism_gate"][
    "all_configured_families_in_every_paired_group"
] is True
assert manifest["family_mechanism_gate"][
    "behavioral_fingerprints_unique"
] is True
assert manifest["family_mechanism_gate"][
    "duplicate_behavioral_fingerprint_groups"
] == []
assert manifest["family_mechanism_gate"][
    "c10_dynamic_static_variants_present"
] is True
assert manifest["family_mechanism_gate"][
    "c11_legal_collateral_contrast_present_each_row"
] is True
assert manifest["current_now_comparability"][
    "exact_ambiguity_current_target_identity_rate"
] == 1.0
scaling = manifest["current_now_comparability"]["fixed_natural_range_scaling"]
assert scaling["all_available_values_within_0_1"] is True
assert scaling["maximum_absolute_scaling_error"] <= 1e-6
assert set(scaling["natural_ranges"]).issubset({1.0, 2.0, 4.0})
posterior_influence = manifest["teacher_posterior_term_influence"]
assert posterior_influence["interpretation"] == (
    "posterior_distribution_not_argmax_only"
)
assert set(posterior_influence["terms"]) == {
    "now", "future", "edit", "growth", "collateral",
}
assert manifest["teacher_health_gate"]["pass"] is True
assert manifest["test_generated"] is False
assert manifest["formal_run"] is False
assert arrays_path.is_file()

train_groups = 1000
all_groups = 1400
benchmark_groups = manifest["paired_groups_total"]
train_scale = train_groups / benchmark_groups
all_scale = all_groups / benchmark_groups
report = {
    "schema_version": "cpmt-m1-v5-health-benchmark-v1",
    "status": "train_only_pretest_health_and_cost_benchmark",
    "formal_run": False,
    "test_access": False,
    "test_generated": False,
    "git_commit": commit,
    "protocol_sha256": expected_protocol,
    "dataset_version": expected_dataset,
    "source_manifest": str(manifest_path),
    "source_arrays": str(arrays_path),
    "arrays_digest": manifest["arrays_digest"],
    "benchmark": {
        "paired_groups_total": manifest["paired_groups_total"],
        "paired_group_count_semantics": manifest[
            "paired_group_count_semantics"
        ],
        "learning_rows": manifest["decisions"],
        "online_chain_decisions": manifest["online_chain_decisions"],
        "recovery_training_examples": manifest["recovery_training_examples"],
        "workers": manifest["workers"],
        "generation_seconds": manifest["generation_seconds"],
        "merged_npz_bytes": manifest["merged_npz_bytes"],
        "retained_shard_count": manifest["retained_shard_count"],
        "retained_shard_bytes": manifest["retained_shard_bytes"],
    },
    "teacher_health_gate": manifest["teacher_health_gate"],
    "family_mechanism_audit": manifest["family_mechanism_audit"],
    "family_mechanism_gate": manifest["family_mechanism_gate"],
    "current_now_comparability": manifest["current_now_comparability"],
    "teacher_posterior_term_influence": posterior_influence,
    "live_energy_activation_by_family": manifest[
        "live_energy_activation_by_family"
    ],
    "linear_cost_references_not_limits": {
        "formal_train_1000_total_mixed_groups": {
            "paired_groups_total": train_groups,
            "learning_rows": round(manifest["decisions"] * train_scale),
            "candidate_slots_k16": round(manifest["decisions"] * train_scale * 16),
            "generation_hours": manifest["generation_seconds"] * train_scale / 3600,
            "merged_npz_bytes": round(manifest["merged_npz_bytes"] * train_scale),
            "merged_plus_shards_bytes": (
                round((manifest["merged_npz_bytes"] + manifest["retained_shard_bytes"])
                      * train_scale)
            ),
        },
        "all_splits_1400_total_mixed_groups": {
            "paired_groups_total": all_groups,
            "learning_rows": round(manifest["decisions"] * all_scale),
            "candidate_slots_k16": round(manifest["decisions"] * all_scale * 16),
            "generation_hours": manifest["generation_seconds"] * all_scale / 3600,
            "merged_npz_bytes": round(manifest["merged_npz_bytes"] * all_scale),
            "merged_plus_shards_bytes": (
                round((manifest["merged_npz_bytes"] + manifest["retained_shard_bytes"])
                      * all_scale)
            ),
        },
    },
    "interpretation": (
        "This benchmark validates v8 train-only fixed current scaling, posterior "
        "influence, family mechanisms, and teacher health; "
        "linear storage/time projections are planning references, not fixed caps."
    ),
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print("HEALTH_REPORT={}".format(report_path))
print("HEALTH_ARRAYS_DIGEST={}".format(manifest["arrays_digest"]))
print("HEALTH_TEACHER_AGREEMENT={:.6f}".format(
    manifest["teacher_health_gate"]["overall_reference_agreement"]
))
print("HEALTH_GENERATION_SECONDS={:.3f}".format(manifest["generation_seconds"]))
PY
then
  cpmt_fail "health_export_failed"
fi

printf "SERVER_STEP_OK phase=health_benchmark\n"
printf "NEXT=commit_exported_health_report_after_review\n"
