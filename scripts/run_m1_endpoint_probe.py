"""Run the fixed D-047 train-only endpoint viability probe.

This is the one registered anchor: Set Transformer, A/C/E plus deterministic F,
five seeds, lr=0.0006, 3000 updates and C auxiliary weight 1.0.  It reads only
the 1000-group train arrays, reconstructs the frozen 201-group inner-dev audits,
and writes resumable causal results, the H3-vs-H1 teacher contrast, and the
mechanical endpoint/power assessment.  It does not read validation or test.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.dev_learning import (  # noqa: E402
    apply_candidate_admissibility_to_probabilities,
    candidate_admissibility_mask,
    masked_candidate_probabilities,
    outcome_scorer_diagnostics,
    tensors,
    train_outcome_scorer,
    train_student,
)
from cpmt.m1_af_rollout import (  # noqa: E402
    CANDIDATE_FEATURE_DIM,
    CURRENT_RELATION_QUERIES,
    causal_rollout_metrics,
    selection_error_decomposition,
    training_inner_dev_mask,
    rollout_learning_arrays_from_audits,
)
from cpmt.m1_metrics import endpoint_viability_assessment  # noqa: E402
from cpmt.m1_protocol import (  # noqa: E402
    load_and_validate,
    load_and_validate_endpoint_probe,
    protocol_sha256,
)
from cpmt.m1_rollout import (  # noqa: E402
    generate_m1_paired_rollout_split,
    teacher_horizon_contrast,
)
from cpmt.run_provenance import arrays_sha256, capture_run_provenance  # noqa: E402

METHODS = {"A": "cpmt_ctl_core", "C": "direct_future_loss",
           "E": "future_no_execution"}
ALL_METHODS = (*METHODS, "F")


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def _load_train(path: Path, hard: dict) -> tuple[dict[str, np.ndarray], dict]:
    arrays = {k: v for k, v in np.load(path, allow_pickle=True).items()}
    digest = arrays_sha256(arrays)
    manifest_path = path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        raise ValueError(f"train manifest is required: {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("arrays_digest") != digest:
        raise ValueError("train arrays digest does not match manifest")
    if manifest.get("protocol_sha256") != protocol_sha256(hard):
        raise ValueError("train arrays protocol does not match active config")
    if manifest.get("dataset_version") != hard["data"]["dataset_version"]:
        raise ValueError("train arrays dataset does not match active config")
    if manifest.get("split") != "train":
        raise ValueError("endpoint probe accepts train arrays only")
    if manifest.get("teacher_health_gate", {}).get("pass") is not True:
        raise ValueError("train arrays did not pass the teacher health gate")
    return arrays, {"path": str(path), "manifest_path": str(manifest_path),
                    "arrays_digest": digest, "manifest": manifest}


def _subset(data: dict[str, np.ndarray], mask: np.ndarray) -> dict[str, np.ndarray]:
    return {k: v[mask] if isinstance(v, np.ndarray) and len(v) == len(mask) else v
            for k, v in data.items()}


def _architecture_settings(hard: dict) -> dict:
    spec = hard["architecture_evaluation"]["cross_candidate_set_transformer_v1"]
    return {"architecture": "cross_candidate_set_transformer_v1",
            "hidden_dim": int(spec["model_dim"]),
            "attention_heads": int(spec["attention_heads"]),
            "set_attention_blocks": int(spec["set_attention_blocks"]),
            "feedforward_dim": int(spec["feedforward_dim"]),
            "architecture_dropout": float(spec["dropout"])}


def _audit_path(audit_dir: Path, group: int) -> Path:
    return audit_dir / f"train_inner_dev_{group:06d}.json.gz"


def _write_audit(task: tuple[str, int, str]) -> tuple[int, str]:
    config_path, group, out_name = task
    config = load_and_validate(Path(config_path))
    _, audits, _ = generate_m1_paired_rollout_split(
        config, "train", paired_groups=1, start_group_index=group,
    )
    target = Path(out_name)
    tmp = target.with_name(target.name + f".tmp-{os.getpid()}")
    with gzip.open(tmp, "wt", encoding="utf-8") as stream:
        json.dump({"schema_version": "cpmt-m1-inner-dev-audit-v1",
                   "group": group, "audits": audits}, stream, allow_nan=False)
    tmp.replace(target)
    return group, str(target)


def _reconstruct_audits(config_path: Path, hard: dict, train: dict,
                        groups: list[int], audit_dir: Path, workers: int) -> list[dict]:
    audit_dir.mkdir(parents=True, exist_ok=True)
    missing = [g for g in groups if not _audit_path(audit_dir, g).exists()]
    tasks = [(str(config_path), g, str(_audit_path(audit_dir, g))) for g in missing]
    if tasks:
        print(f"reconstructing {len(tasks)} inner-dev paired audits with {workers} workers",
              flush=True)
        with mp.Pool(processes=workers) as pool:
            for done, _ in enumerate(pool.imap_unordered(_write_audit, tasks), 1):
                if done == len(tasks) or done % max(1, len(tasks) // 20) == 0:
                    print(f"  audits {done}/{len(tasks)}", flush=True)
    audits = []
    for group in groups:
        path = _audit_path(audit_dir, group)
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
        if payload.get("group") != group or len(payload.get("audits", [])) != 2:
            raise ValueError(f"invalid cached audit {path}")
        audits.extend(payload["audits"])
    rebuilt = rollout_learning_arrays_from_audits(hard, audits, future_hash_bins=32)
    selected = np.isin(np.asarray(train["group"], dtype=np.int64), groups)
    expected = _subset(train, selected)
    rebuilt["group"] = np.asarray([int(g) for g in rebuilt["group"]], dtype=np.int64)
    # A one-group reconstruction naturally labels its rows zero; recover the
    # registered group index from the audit order before exact comparison.
    # Copy the labels before rewriting the output array; a view would change
    # the later boolean masks as each local group is assigned its registered
    # group index.
    local_groups = np.asarray(rebuilt["group"], dtype=np.int64).copy()
    for local, gid in enumerate(groups):
        rebuilt["group"][local_groups == local] = gid
    order = np.lexsort((np.arange(len(expected["y"])), expected["group"]))
    for key in expected:
        a, b = np.asarray(rebuilt[key]), np.asarray(expected[key])[order]
        if a.shape != b.shape or not np.array_equal(a, b, equal_nan=True):
            raise ValueError(f"reconstructed audits do not match train arrays: {key}")
    return audits


def _save_npz(path: Path, **arrays: np.ndarray) -> None:
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with tmp.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    tmp.replace(path)


def _train_cfg(hard: dict, smoke: dict) -> dict:
    return dict(smoke, **_architecture_settings(hard), horizon=3, batch_size=64,
                device="cpu", student_steps=3000, scorer_steps=3000,
                learning_rate=0.0006, distillation_weight=1.0,
                auxiliary_weight=1.0, candidate_feature_dim=CANDIDATE_FEATURE_DIM,
                current_relation_dim=len(CURRENT_RELATION_QUERIES),
                standardize_future_term=True, energy_weights=hard["energy"]["weights"],
                temperature=float(hard["energy"]["temperature"]),
                current_evidence_scope_ranks=int(hard["candidates"][
                    "proposal_retrieval"]["enumerated_ranks"]),
                commit_probability=0.0, margin_threshold=0.0,
                mechanism_diagnostic_slices=hard["evaluation"]["mechanism_diagnostic_slices"])


def _cache_scorer(path: Path, fitting: dict, inner: dict, cfg: dict, seed: int,
                  device: torch.device, diagnostic: dict) -> dict:
    if path.exists():
        loaded = np.load(path, allow_pickle=False)
        meta = json.loads(str(loaded["meta"]))
        if meta.get("seed") != seed or meta.get("updates") != 3000:
            raise ValueError(f"scorer cache metadata mismatch: {path}")
        return {"train": torch.as_tensor(loaded["train"], device=device),
                "validation": torch.as_tensor(loaded["inner_dev"], device=device)}
    scorer, learned, trace = train_outcome_scorer(
        fitting, inner, cfg, seed, device,
    )
    diagnostic["scorer_diagnostics"] = outcome_scorer_diagnostics(
        scorer, inner, learned["validation"], row_mask=~inner["recovery"],
        energy_weights=cfg["energy_weights"], temperature=cfg["temperature"],
        total_variation_thresholds=(0.01, 0.05, 0.10),
    )
    diagnostic["training_trace"] = trace
    _save_npz(path, train=learned["train"].detach().cpu().numpy(),
              inner_dev=learned["validation"].detach().cpu().numpy(),
              meta=np.asarray(json.dumps({"seed": seed, "updates": 3000})))
    return {"train": learned["train"], "validation": learned["validation"]}


def _method_teacher(method: str, fitting: dict, learned: dict) -> torch.Tensor:
    teacher = learned["train"] if method == "future_no_execution" else fitting["pstar"]
    return apply_candidate_admissibility_to_probabilities(
        teacher, candidate_admissibility_mask(fitting, fitting["penalties"]),
    )


def _run(args: argparse.Namespace) -> int:
    hard = load_and_validate(args.config)
    probe = load_and_validate_endpoint_probe(args.overlay, hard)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    provenance = capture_run_provenance(PROJECT, component="m1_endpoint_probe",
                                        entrypoint=Path(__file__))
    train, train_input = _load_train(args.train, hard)
    if len(set(np.asarray(train["group"], dtype=np.int64))) != 1000:
        raise ValueError("endpoint anchor requires exactly 1000 train groups")
    inner_mask = training_inner_dev_mask(train)
    fitting_np, inner_np = _subset(train, ~inner_mask), _subset(train, inner_mask)
    groups = sorted(set(int(v) for v in inner_np["group"]))
    if len(groups) != int(probe["source_protocol"]["inner_dev_paired_groups"]):
        raise ValueError("inner-dev group count does not match probe contract")
    audits = _reconstruct_audits(args.config, hard, train, groups,
                                 out / "audits", args.workers)
    h1_path = out / "teacher_horizon_contrast.json"
    if h1_path.exists():
        h1 = json.loads(h1_path.read_text(encoding="utf-8"))
    else:
        h1 = teacher_horizon_contrast(hard, audits, contrast_horizon=1)
        _atomic_json(h1_path, h1)
    # Release the full arrays before constructing tensors where possible; the
    # arrays themselves remain available through the two selected copies.
    del train
    smoke = json.loads((PROJECT / "configs" / "m1_af_smoke.json").read_text(encoding="utf-8"))
    cfg = _train_cfg(hard, smoke)
    device = torch.device("cuda" if args.device == "cuda" or
                          (args.device == "auto" and torch.cuda.is_available()) else "cpu")
    cfg["device"] = device.type
    torch.set_num_threads(args.threads)
    fitting, inner = tensors(fitting_np, device), tensors(inner_np, device)
    causal_dir = out / "causal"
    causal_dir.mkdir(parents=True, exist_ok=True)
    run_diagnostics = {}
    for short, method in METHODS.items():
        for seed in [7, 19, 31, 43, 59]:
            result_path = causal_dir / f"{short}_seed{seed}.json"
            scorer_cache = out / f"scorer_seed{seed}.npz"
            scorer_info = out / f"scorer_seed{seed}.json"
            if method == "cpmt_ctl_core" or method == "direct_future_loss":
                # A/C do not consume the learned scorer; this branch preserves
                # the registered teacher and avoids an unnecessary fit.
                learned = {"train": fitting["pstar"]}
            else:
                info = {}
                learned = _cache_scorer(scorer_cache, fitting, inner, cfg, seed,
                                         device, info)
                if info:
                    _atomic_json(scorer_info, info)
            if result_path.exists():
                print(f"reuse {result_path.name}", flush=True)
                continue
            began = time.time()
            model, trace = train_student(
                method, fitting, _method_teacher(method, fitting, learned),
                cfg, seed, device,
            )
            with torch.no_grad():
                probabilities = masked_candidate_probabilities(
                    model(inner["x"]), candidate_admissibility_mask(inner, model(inner["x"])),
                ).cpu().numpy()
            forced = selection_error_decomposition(probabilities, inner_np)
            metrics, sequences = causal_rollout_metrics(model, audits, cfg)
            metrics.update(method=method, seed=seed, seconds=time.time() - began,
                           teacher_forced_inner_dev=forced)
            _atomic_json(result_path, {"schema_version": "cpmt-m1-endpoint-causal-v1",
                                       "short_method": short, "aggregate": metrics,
                                       "sequences": sequences, "training_trace": trace})
            print(f"causal {short} seed={seed} active={metrics['final_active_graph_correctness']:.4f}",
                  flush=True)
    # F is deterministic and independent of training seed.
    fpath = causal_dir / "F_oracle.json"
    if not fpath.exists():
        metrics, sequences = causal_rollout_metrics(None, audits, cfg, oracle=True)
        metrics.update(method="oracle_candidate_program", seed=None)
        _atomic_json(fpath, {"schema_version": "cpmt-m1-endpoint-causal-v1",
                             "short_method": "F", "aggregate": metrics,
                             "sequences": sequences})
    endpoint_rows = []
    for short in ALL_METHODS:
        paths = [causal_dir / f"{short}_seed{s}.json" for s in [7, 19, 31, 43, 59]] if short != "F" else [fpath]
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for sequence in payload["sequences"]:
                endpoint_rows.append({"paired_group_id": sequence["metrics"]["paired_group_id"],
                                      "method": short, "metrics": sequence["metrics"]})
    assessment = endpoint_viability_assessment(
        endpoint_rows, expected_groups=201,
        minimum_effect=0.03, planning_effect=0.06,
        burden_minimum_effect=float(probe["power_planning"]["open_fact_error_auc_null_boundary_minimum_effect"]),
        burden_planning_effect=float(probe["power_planning"]["open_fact_error_auc_planning_true_effect"]),
        z_one_sided_alpha=float(probe["power_planning"]["z_one_sided_alpha"]),
        z_power=float(probe["power_planning"]["z_power"]), minimum_test_groups=200,
    )
    report = {"schema_version": "cpmt-m1-endpoint-viability-report-v4",
              "formal_run": False, "formal_method_effect_claim": False,
              "status": "complete", "protocol_sha256": protocol_sha256(hard),
              "dataset_version": hard["data"]["dataset_version"],
              "probe_config_sha256": hashlib.sha256(args.overlay.read_bytes()).hexdigest(),
              "input_arrays": train_input, "inner_dev_paired_groups": 201,
              "fitting_paired_groups": 799, "architecture": _architecture_settings(hard),
              "methods": {**METHODS, "F": "oracle_candidate_program"},
              "seeds": [7, 19, 31, 43, 59], "learning_rate": 0.0006,
              "student_updates": 3000, "scorer_updates": 3000,
              "c_auxiliary_weight": 1.0,
              "commit_rule": probe["commit_rule"],
              "endpoint_assessment": assessment, "teacher_horizon_contrast": h1,
              "training_provenance": provenance,
              "access_boundary": probe["access_boundary"],
              "causal_result_directory": str(causal_dir),
              "failure_records": "runner log and per-stage atomic outputs",
              "validation_arrays_read": False, "validation_trial_consumed": False,
              "test_generated": False, "test_access": False}
    _atomic_json(out / "endpoint_probe_report.json", report)
    print(f"ENDPOINT_PROBE_COMPLETE disposition={assessment['disposition']} "
          f"selected_test_groups={assessment['selected_test_groups']}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT / "configs" / "m1_hard_condition.json")
    parser.add_argument("--overlay", type=Path, default=PROJECT / "configs" / "m1_endpoint_viability_probe.json")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if args.workers <= 0 or args.threads <= 0:
        parser.error("--workers and --threads must be positive")
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
