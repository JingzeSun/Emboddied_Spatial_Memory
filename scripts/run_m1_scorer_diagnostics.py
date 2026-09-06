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
    CANDIDATE_FEATURE_DIM,
    selection_error_decomposition,
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
    inner_online = ~np.asarray(inner_dev_np["recovery"], dtype=bool)
    fitting_online = ~np.asarray(fitting_np["recovery"], dtype=bool)
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

    oracle_probabilities = structured_relation_oracle_probabilities(
        inner_online_np,
        future_weight=float(hard["energy"]["weights"]["future"]),
        temperature=float(hard["energy"]["temperature"]),
    )
    relation_oracle = selection_error_decomposition(
        oracle_probabilities, inner_online_np,
    )
    _ambiguity_cap(relation_oracle)
    target_only = structured_relation_target_only_diagnostics(inner_online_np)
    relation_oracle_by_group = {}
    target_only_by_group = {}
    for group_id in inner_groups:
        group_np = _subset_rows(
            inner_online_np,
            np.asarray(inner_online_np["group"]) == group_id,
        )
        group_probabilities = structured_relation_oracle_probabilities(
            group_np,
            future_weight=float(hard["energy"]["weights"]["future"]),
            temperature=float(hard["energy"]["temperature"]),
        )
        group_oracle = selection_error_decomposition(
            group_probabilities, group_np,
        )
        _ambiguity_cap(group_oracle)
        relation_oracle_by_group[str(group_id)] = group_oracle
        target_only_by_group[str(group_id)] = (
            structured_relation_target_only_diagnostics(group_np)
        )

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
        diagnostics = {
            "seed": int(seed),
            "fitting_all_learning_rows": outcome_scorer_diagnostics(
                scorer, fitting, teachers["train"],
            ),
            "fitting_online_chain": outcome_scorer_diagnostics(
                scorer, fitting, teachers["train"], row_mask=fitting_online,
            ),
            "inner_dev_all_learning_rows": outcome_scorer_diagnostics(
                scorer, held_out, teachers["validation"],
            ),
            "inner_dev_online_chain": outcome_scorer_diagnostics(
                scorer, held_out, teachers["validation"],
                row_mask=inner_online,
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
        "schema_version": "cpmt-m1-scorer-diagnostic-v1",
        "runner": "run_m1_scorer_diagnostics_v1",
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
        "structured_relation_target_oracle": relation_oracle,
        "structured_relation_target_oracle_by_group": relation_oracle_by_group,
        "structured_relation_target_only": target_only,
        "structured_relation_target_only_by_group": target_only_by_group,
        "outcome_scorer_diagnostics": scorer_runs,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / "af_report.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
