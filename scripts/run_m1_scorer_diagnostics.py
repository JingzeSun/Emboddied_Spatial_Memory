"""Run S1/S2 scorer diagnostics using only a held-out part of train.

This entrypoint exists so target/scorer development never consumes the
validation report partition. It deterministically holds out complete paired
train groups, trains E's outcome scorer on the remainder, and reports raw
target information, assembled-oracle behavior, and scorer fit/generalization.
It does not train online students, calibrate commit gates, run causal rollout,
read validation arrays, or touch test.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.dev_learning import (  # noqa: E402
    outcome_scorer_diagnostics,
    tensors,
    train_outcome_scorer,
)
from cpmt.m1_af_rollout import (  # noqa: E402
    CANDIDATE_FAILURE_TYPES,
    CANDIDATE_FEATURE_DIM,
    selection_error_decomposition,
    static_preflight_diagnostics,
    structured_relation_oracle_probabilities,
    structured_relation_target_only_diagnostics,
    training_inner_dev_mask,
)
from cpmt.m1_protocol import load_and_validate, protocol_sha256  # noqa: E402
from cpmt.m1_trainability import subset_paired_array_groups  # noqa: E402
from cpmt.run_provenance import (  # noqa: E402
    arrays_sha256,
    capture_run_provenance,
)


def _load_train(
    path: Path, *, expected_protocol_sha256: str,
    expected_dataset_version: str,
) -> tuple[dict[str, np.ndarray], dict]:
    data = {key: value for key, value in np.load(
        path, allow_pickle=True,
    ).items()}
    digest = arrays_sha256(data)
    manifest_path = path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        raise ValueError(f"generation manifest is required for {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("arrays_digest") != digest:
        raise ValueError("train arrays do not match their generation manifest")
    if manifest.get("protocol_sha256") != expected_protocol_sha256:
        raise ValueError("train arrays do not match the active protocol")
    if manifest.get("dataset_version") != expected_dataset_version:
        raise ValueError("train arrays do not match the active dataset version")
    if manifest.get("split") != "train":
        raise ValueError("scorer diagnostics accept train arrays only")
    data.pop("teacher_matches_reference", None)
    return data, {
        "path": str(path),
        "arrays_digest": digest,
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }


def _subset_rows(
    data: dict[str, np.ndarray], mask: np.ndarray,
) -> dict[str, np.ndarray]:
    return {
        key: value[mask]
        if isinstance(value, np.ndarray) and len(value) == len(mask)
        else value
        for key, value in data.items()
    }


def _ambiguity_cap(diagnostics: dict) -> None:
    ambiguous_fraction = float(diagnostics["ambiguous_fraction"])
    diagnostics["exact_ambiguity_capped_accuracy"] = float(
        (1.0 - ambiguous_fraction)
        * float(diagnostics["identifiable_accuracy"])
        + ambiguous_fraction * 0.5
    )
    diagnostics["exact_ambiguity_pair_cap"] = 0.5


def _relation_diagnostics(
    arrays: dict[str, np.ndarray], hard: dict, *,
    use_static_preflight: bool,
) -> dict:
    preflight = (
        np.asarray(arrays["candidate_static_preflight_pass"], dtype=bool)
        if use_static_preflight else None
    )
    probabilities = structured_relation_oracle_probabilities(
        arrays,
        future_weight=float(hard["energy"]["weights"]["future"]),
        temperature=float(hard["energy"]["temperature"]),
        static_preflight_pass=preflight,
    )
    oracle = selection_error_decomposition(probabilities, arrays)
    _ambiguity_cap(oracle)
    return {
        "scope_rows": int(len(arrays["y"])),
        "uses_static_preflight_filter": use_static_preflight,
        "target_only": structured_relation_target_only_diagnostics(
            arrays, static_preflight_pass=preflight,
        ),
        "assembled_oracle": oracle,
    }


def _apply_static_preflight_to_probabilities(
    probabilities: torch.Tensor, static_preflight_pass: torch.Tensor,
) -> torch.Tensor:
    """Post-hoc diagnostic mask; it does not alter scorer training or methods."""
    if probabilities.shape != static_preflight_pass.shape:
        raise ValueError("scorer probabilities and static preflight mask differ")
    masked = probabilities * static_preflight_pass.to(probabilities.dtype)
    denominator = masked.sum(dim=1, keepdim=True)
    if torch.any(denominator <= 0):
        raise ValueError("static preflight rejected every scorer candidate")
    return masked / denominator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path,
                        default=PROJECT / "configs" / "m1_hard_condition.json")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7])
    parser.add_argument("--scorer-steps", type=int, required=True)
    parser.add_argument(
        "--paired-groups", type=int, default=None,
        help=(
            "optional deterministic prefix of complete train paired groups; "
            "use one larger array file for directly comparable size sweeps"
        ),
    )
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    if args.scorer_steps <= 0:
        parser.error("--scorer-steps must be positive")

    hard = load_and_validate(args.config)
    active_protocol_sha256 = protocol_sha256(hard)
    train_np, train_input = _load_train(
        args.train,
        expected_protocol_sha256=active_protocol_sha256,
        expected_dataset_version=str(hard["data"]["dataset_version"]),
    )
    available_groups = sorted(set(int(value) for value in train_np["group"]))
    if args.paired_groups is not None:
        train_np = subset_paired_array_groups(train_np, args.paired_groups)
    selected_groups = sorted(set(int(value) for value in train_np["group"]))
    train_input["available_paired_groups"] = len(available_groups)
    train_input["selected_paired_groups"] = len(selected_groups)
    train_input["selected_training_view_digest"] = arrays_sha256(train_np)
    inner_dev = training_inner_dev_mask(train_np)
    fitting_np = _subset_rows(train_np, ~inner_dev)
    inner_dev_np = _subset_rows(train_np, inner_dev)
    selected_online = ~np.asarray(train_np["recovery"], dtype=bool)
    inner_online = ~np.asarray(inner_dev_np["recovery"], dtype=bool)
    fitting_online = ~np.asarray(fitting_np["recovery"], dtype=bool)
    selected_online_np = _subset_rows(train_np, selected_online)
    inner_online_np = _subset_rows(inner_dev_np, inner_online)
    fitting_groups = sorted(set(int(value) for value in fitting_np["group"]))
    inner_groups = sorted(set(int(value) for value in inner_dev_np["group"]))
    if set(fitting_groups) & set(inner_groups):
        raise AssertionError("train inner-dev partition split a paired group")

    smoke = json.loads(
        (PROJECT / "configs" / "m1_af_smoke.json").read_text(encoding="utf-8")
    )
    cfg = dict(
        smoke,
        hidden_dim=64,
        horizon=int(hard["future"]["primary_horizon"]),
        learning_rate=2e-3,
        batch_size=64,
        device="cpu",
        scorer_steps=int(args.scorer_steps),
        candidate_feature_dim=CANDIDATE_FEATURE_DIM,
        standardize_future_term=True,
        energy_weights=hard["energy"]["weights"],
        temperature=float(hard["energy"]["temperature"]),
    )
    torch.set_num_threads(args.threads)
    device = torch.device("cpu")

    all_train_relations = _relation_diagnostics(
        selected_online_np, hard, use_static_preflight=False,
    )
    all_train_relations_filtered = _relation_diagnostics(
        selected_online_np, hard, use_static_preflight=True,
    )
    inner_relations = _relation_diagnostics(
        inner_online_np, hard, use_static_preflight=False,
    )
    inner_relations_filtered = _relation_diagnostics(
        inner_online_np, hard, use_static_preflight=True,
    )
    all_train_relations_by_group = {}
    for group_id in selected_groups:
        group_np = _subset_rows(
            selected_online_np,
            np.asarray(selected_online_np["group"]) == group_id,
        )
        all_train_relations_by_group[str(group_id)] = {
            "unfiltered": _relation_diagnostics(
                group_np, hard, use_static_preflight=False,
            ),
            "static_preflight_filtered": _relation_diagnostics(
                group_np, hard, use_static_preflight=True,
            ),
        }
    inner_relations_by_group = {}
    for group_id in inner_groups:
        group_np = _subset_rows(
            inner_online_np,
            np.asarray(inner_online_np["group"]) == group_id,
        )
        inner_relations_by_group[str(group_id)] = {
            "unfiltered": _relation_diagnostics(
                group_np, hard, use_static_preflight=False,
            ),
            "static_preflight_filtered": _relation_diagnostics(
                group_np, hard, use_static_preflight=True,
            ),
        }

    fitting = tensors(fitting_np, device)
    held_out = tensors(inner_dev_np, device)
    scorer_runs = []
    print(
        f"train-inner-dev split: fitting_groups={len(fitting_groups)} "
        f"inner_dev_groups={len(inner_groups)}; scorer_steps={args.scorer_steps}",
        flush=True,
    )
    for seed in args.seeds:
        started = time.time()
        scorer, teachers, trace = train_outcome_scorer(
            fitting, held_out, cfg, int(seed), device,
        )
        fitting_teacher_filtered = _apply_static_preflight_to_probabilities(
            teachers["train"], fitting["candidate_static_preflight_pass"],
        )
        inner_teacher_filtered = _apply_static_preflight_to_probabilities(
            teachers["validation"],
            held_out["candidate_static_preflight_pass"],
        )
        diagnostics = {
            "seed": int(seed),
            "online_admissibility_mask": "transaction_static_preflight_v1",
            "scorer_training_objective": "pointwise_masked_relation_bce",
            "fitting_all_learning_rows": outcome_scorer_diagnostics(
                scorer, fitting, teachers["train"],
            ),
            "fitting_online_chain": outcome_scorer_diagnostics(
                scorer, fitting, teachers["train"], row_mask=fitting_online,
            ),
            "fitting_online_chain_static_preflight_filtered": (
                outcome_scorer_diagnostics(
                    scorer, fitting, fitting_teacher_filtered,
                    row_mask=fitting_online,
                )
            ),
            "inner_dev_all_learning_rows": outcome_scorer_diagnostics(
                scorer, held_out, teachers["validation"],
            ),
            "inner_dev_online_chain": outcome_scorer_diagnostics(
                scorer, held_out, teachers["validation"],
                row_mask=inner_online,
            ),
            "inner_dev_online_chain_static_preflight_filtered": (
                outcome_scorer_diagnostics(
                    scorer, held_out, inner_teacher_filtered,
                    row_mask=inner_online,
                )
            ),
            "inner_dev_online_by_group": {
                str(group_id): outcome_scorer_diagnostics(
                    scorer,
                    held_out,
                    teachers["validation"],
                    row_mask=(
                        inner_online
                        & (np.asarray(inner_dev_np["group"]) == group_id)
                    ),
                )
                for group_id in inner_groups
            },
            "inner_dev_online_by_group_static_preflight_filtered": {
                str(group_id): outcome_scorer_diagnostics(
                    scorer,
                    held_out,
                    inner_teacher_filtered,
                    row_mask=(
                        inner_online
                        & (np.asarray(inner_dev_np["group"]) == group_id)
                    ),
                )
                for group_id in inner_groups
            },
            "training_trace": trace,
            "wall_seconds": float(time.time() - started),
        }
        scorer_runs.append(diagnostics)
        fit = diagnostics["fitting_online_chain"]
        dev = diagnostics["inner_dev_online_chain"]
        print(
            f"seed {seed}: fit BCE={fit['masked_bce']:.4f} "
            f"teacher={fit['teacher_accuracy']:.4f}; "
            f"inner-dev BCE={dev['masked_bce']:.4f} "
            f"teacher={dev['teacher_accuracy']:.4f}",
            flush=True,
        )

    report = {
        "schema_version": "cpmt-m1-scorer-diagnostic-v3",
        "runner": "run_m1_scorer_diagnostics_v3",
        "formal_run": False,
        "test_generated": False,
        "causal_complete": False,
        "protocol_sha256": active_protocol_sha256,
        "dataset_version": hard["data"]["dataset_version"],
        "training_provenance": capture_run_provenance(
            PROJECT,
            component="m1_train_inner_dev_scorer_diagnostic",
            entrypoint=Path(__file__),
        ),
        "input_arrays": {"train": train_input},
        "partition": {
            "rule": "sha256(rollout-pair:train:{group_index:06d}) mod 5 == 0",
            "held_out_fraction_nominal": 0.2,
            "available_train_groups": len(available_groups),
            "selected_train_groups": len(selected_groups),
            "fitting_group_ids": fitting_groups,
            "inner_dev_group_ids": inner_groups,
            "fitting_learning_rows": int(len(fitting_np["y"])),
            "inner_dev_learning_rows": int(len(inner_dev_np["y"])),
            "inner_dev_online_rows": int(inner_online.sum()),
            "validation_arrays_read": False,
            "validation_report_partition_accessed": False,
            "validation_trial_consumed": False,
        },
        "seeds": [int(seed) for seed in args.seeds],
        "training_budget": {
            "online_students_trained": False,
            "outcome_scorer_steps": int(args.scorer_steps),
            "total_train_groups": len(selected_groups),
        },
        "online_admissibility_mask": {
            "name": "transaction_static_preflight_v1",
            "enabled_for_methods": ["A", "B", "C", "D", "E"],
            "candidate_slots_retained": True,
            "executor_illegal_energy_retained": True,
        },
        # The compatibility aliases now report the registered shared-mask
        # method boundary. Explicit unfiltered values remain below solely for
        # before/after attribution.
        "structured_relation_target_oracle": (
            inner_relations_filtered["assembled_oracle"]
        ),
        "structured_relation_target_only": inner_relations_filtered[
            "target_only"
        ],
        "structured_relation_diagnostics": {
            "all_selected_train_online": {
                "unfiltered": all_train_relations,
                "static_preflight_filtered": all_train_relations_filtered,
            },
            "inner_dev_online": {
                "unfiltered": inner_relations,
                "static_preflight_filtered": inner_relations_filtered,
            },
            "all_selected_train_online_by_group": (
                all_train_relations_by_group
            ),
            "inner_dev_online_by_group": inner_relations_by_group,
        },
        "static_preflight_diagnostics": {
            "definition": (
                "read-only header/base/template/protected checks; pass is "
                "not proof that transaction execution will succeed"
            ),
            "candidate_failure_type_codebook": {
                str(index): name
                for index, name in enumerate(CANDIDATE_FAILURE_TYPES)
            },
            "all_selected_train_online": static_preflight_diagnostics(
                selected_online_np,
            ),
            "inner_dev_online": static_preflight_diagnostics(
                inner_online_np,
            ),
        },
        "outcome_scorer_diagnostics": scorer_runs,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / "af_report.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
