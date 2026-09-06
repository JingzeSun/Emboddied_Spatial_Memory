"""Run A-F at an arbitrary scale from arrays that were generated separately.

The existing smoke runner sizes and generates its own data from the smoke
config. This one reads arrays produced by ``generate_m1_parallel.py`` so a run
can be sized from the protocol's groups_per_family instead, and so generation
and training can happen on different machines or at different times.

Two phases are reported. Teacher-forced accuracy answers the single-step
contrasts. The 20-step causal self-rollout replays each sequence on the world
that method's own choices produced, so an early wrong transaction keeps
contaminating later decisions; that is the protocol's primary metric family and
single-step accuracy is not a substitute for it.

Every (method, seed) causal result is written as it completes, so an interrupted
run resumes instead of restarting. This is a runner, not a protocol change: it
reports ``formal_run: false`` and never touches the sealed test split.
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
    outcome_scorer_diagnostics, train_outcome_scorer, train_student, tensors,
)
from cpmt.m1_af_rollout import (  # noqa: E402
    CANDIDATE_FEATURE_DIM, calibrate_shared_commit_rule,
    causal_rollout_metrics, paired_group_is_calibration,
    rollout_learning_arrays_from_audits, selection_error_decomposition,
    structured_relation_oracle_probabilities,
    structured_relation_target_only_diagnostics,
)
from cpmt.m1_protocol import load_and_validate, protocol_sha256  # noqa: E402
from cpmt.m1_metrics import (  # noqa: E402
    holm_bonferroni, paired_stratified_bootstrap,
)
from cpmt.m1_rollout import generate_m1_paired_rollout_split  # noqa: E402
from cpmt.run_provenance import arrays_sha256, capture_run_provenance  # noqa: E402

STUDENTS = ("cpmt_ctl_core", "direct_classifier", "direct_future_loss",
            "execute_current_only", "future_no_execution")
ALL_METHODS = STUDENTS + ("oracle_candidate_program",)
LABEL = {
    "cpmt_ctl_core": "A CTL core",
    "direct_classifier": "B labels only",
    "direct_future_loss": "C direct future loss",
    "execute_current_only": "D execute current only",
    "future_no_execution": "E learned scorer",
    "oracle_candidate_program": "F oracle upper bound",
}


def _load(
    path: Path, *, expected_protocol_sha256: str,
    expected_split: str, expected_dataset_version: str,
) -> tuple[dict[str, np.ndarray], dict]:
    data = {k: v for k, v in np.load(path, allow_pickle=True).items()}
    digest = arrays_sha256(data)
    manifest_path = path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        raise ValueError(f"generation manifest is required for {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("arrays_digest") != digest:
        raise ValueError(
            f"array digest does not match generation manifest for {path}"
        )
    if manifest.get("protocol_sha256") != expected_protocol_sha256:
        raise ValueError(
            f"array protocol does not match active config for {path}"
        )
    if manifest.get("split") != expected_split:
        raise ValueError(f"expected {expected_split} arrays at {path}")
    if manifest.get("dataset_version") != expected_dataset_version:
        raise ValueError(f"array dataset version does not match {path}")
    # Carried by the generator for reporting; not a model input.
    data.pop("teacher_matches_reference", None)
    return data, {
        "path": str(path),
        "arrays_digest": digest,
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }


def _teachers(train, learned, method):
    if method == "future_no_execution":
        return learned["train"]
    if method == "execute_current_only":
        return train["pstar_current"]
    return train["pstar"]


def _subset_rows(data: dict[str, np.ndarray], mask: np.ndarray) -> dict[str, np.ndarray]:
    return {
        key: value[mask] if isinstance(value, np.ndarray)
        and len(value) == len(mask) else value
        for key, value in data.items()
    }


def _paired_causal_statistics(
    payloads_by_method: dict[str, list[dict]], hard: dict,
) -> dict:
    """Compute registered paired-group contrasts from complete causal rows."""
    indexed: dict[str, dict[tuple[int, str], dict]] = {}
    for method, payloads in payloads_by_method.items():
        indexed[method] = {}
        for payload in payloads:
            seed = int(payload["aggregate"]["seed"])
            for sequence in payload["sequences"]:
                metrics = sequence["metrics"]
                key = (seed, str(metrics["sequence_id"]))
                indexed[method][key] = metrics
    if not indexed:
        return {}
    expected = set(indexed["cpmt_ctl_core"])
    if any(set(rows) != expected for rows in indexed.values()):
        raise ValueError("causal method results do not contain the same paired rows")
    rows = []
    for key in sorted(expected):
        anchor = indexed["cpmt_ctl_core"][key]
        rows.append({
            # A 20-step endpoint contains the same registered mixed scenario
            # schedule in every group, so there is one endpoint stratum; the
            # paired group, both siblings, and all seeds remain indivisible.
            "scenario_family": "mixed_registered_20_step_schedule",
            "paired_group_id": str(anchor["paired_group_id"]),
            **{method: method_rows[key] for method, method_rows in indexed.items()},
        })
    bootstrap = hard["evaluation"]["bootstrap"]
    meaningful = hard["evaluation"]["meaningful_effect"]
    safety = hard["evaluation"]["safety_noninferiority_margin_per_100"]
    resamples = int(bootstrap["resamples"])
    confidence = float(bootstrap["confidence"])
    contrasts = {}
    p_values = {}
    for other, short in (
        ("direct_future_loss", "A_vs_C"),
        ("future_no_execution", "A_vs_E"),
    ):
        metrics = {
            "active_graph_correctness": paired_stratified_bootstrap(
                rows, "cpmt_ctl_core", other,
                "final_active_graph_correctness", higher_is_better=True,
                resamples=resamples, confidence=confidence,
                minimum_effect=float(
                    meaningful["active_graph_correctness_absolute"]),
            ),
            "memory_contamination": paired_stratified_bootstrap(
                rows, "cpmt_ctl_core", other,
                "memory_contamination_per_100", higher_is_better=False,
                resamples=resamples, confidence=confidence,
                minimum_effect=float(
                    meaningful["memory_contamination_absolute_per_100"]),
            ),
            "false_birth_noninferiority": paired_stratified_bootstrap(
                rows, "cpmt_ctl_core", other,
                "false_birth_growth_per_100", higher_is_better=False,
                resamples=resamples, confidence=confidence,
                minimum_effect=-float(safety["false_birth_growth"]),
            ),
            "collateral_noninferiority": paired_stratified_bootstrap(
                rows, "cpmt_ctl_core", other,
                "collateral_violation_per_100", higher_is_better=False,
                resamples=resamples, confidence=confidence,
                minimum_effect=-float(safety["collateral_violation"]),
            ),
        }
        # Both co-primary benefits are required. Their maximum one-sided p is
        # the conservative intersection-union p for this contrast; Holm then
        # corrects the registered A-C/A-E family.
        p_values[short] = max(
            metrics["active_graph_correctness"][
                "one_sided_p_at_or_below_minimum"
            ],
            metrics["memory_contamination"][
                "one_sided_p_at_or_below_minimum"
            ],
        )
        contrasts[short] = metrics
    adjusted = holm_bonferroni(p_values)
    alpha = float(hard["evaluation"]["multiple_comparisons"][
        "familywise_alpha"
    ])
    for name, metrics in contrasts.items():
        metrics["intersection_union_p"] = p_values[name]
        metrics["holm_adjusted_p"] = adjusted[name]
        metrics["passes_registered_validation_checks"] = bool(
            adjusted[name] <= alpha
            and metrics["active_graph_correctness"]["ci_low"]
            >= float(meaningful["active_graph_correctness_absolute"])
            and metrics["memory_contamination"]["ci_low"]
            >= float(meaningful["memory_contamination_absolute_per_100"])
            and metrics["false_birth_noninferiority"]["ci_low"]
            >= -float(safety["false_birth_growth"])
            and metrics["collateral_noninferiority"]["ci_low"]
            >= -float(safety["collateral_violation"])
        )
    return {
        "scope": "validation_report_partition_not_formal_test_gate",
        "stratification_note": (
            "each endpoint spans the same mixed registered 20-step scenario "
            "schedule; resampling keeps each paired_group_id intact"
        ),
        "sequence_seed_rows": len(rows),
        "paired_groups": len({row["paired_group_id"] for row in rows}),
        "contrasts": contrasts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=PROJECT / "configs" / "m1_hard_condition.json")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--validation-groups", type=int, required=True,
                        help="paired groups to rebuild as audits for the causal phase")
    parser.add_argument("--seeds", type=int, nargs="*", default=None,
                        help="defaults to the protocol's registered formal seeds")
    parser.add_argument("--student-steps", type=int, default=1000)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--skip-causal", action="store_true",
                        help="teacher-forced only; the primary metrics are then missing")
    args = parser.parse_args()

    hard = load_and_validate(args.config)
    training_provenance = capture_run_provenance(
        PROJECT, component="m1_training_and_causal_evaluation",
        entrypoint=Path(__file__),
    )
    smoke = json.loads(
        (PROJECT / "configs" / "m1_af_smoke.json").read_text(encoding="utf-8"))
    seeds = args.seeds or list(hard["training"]["formal_seeds"])
    torch.set_num_threads(args.threads)
    out_dir = args.out_dir
    causal_dir = out_dir / "causal"
    causal_dir.mkdir(parents=True, exist_ok=True)

    active_protocol_sha256 = protocol_sha256(hard)
    train_np, train_input = _load(
        args.train, expected_protocol_sha256=active_protocol_sha256,
        expected_split="train",
        expected_dataset_version=str(hard["data"]["dataset_version"]),
    )
    validation_np, validation_input = _load(
        args.validation, expected_protocol_sha256=active_protocol_sha256,
        expected_split="validation",
        expected_dataset_version=str(hard["data"]["dataset_version"]),
    )
    report_mask = ~np.asarray(validation_np["calibration"], dtype=bool)
    recovery_mask = np.asarray(validation_np["recovery"], dtype=bool)
    online_report_mask = report_mask & ~recovery_mask
    calibration_online_mask = ~report_mask & ~recovery_mask
    validation_report_np = _subset_rows(validation_np, online_report_mask)
    device = torch.device("cpu")
    cfg = dict(smoke, hidden_dim=64, horizon=int(hard["future"]["primary_horizon"]),
               learning_rate=2e-3, batch_size=64, device="cpu",
               student_steps=args.student_steps, scorer_steps=args.student_steps,
               distillation_weight=1.0, auxiliary_weight=1.0,
               candidate_feature_dim=CANDIDATE_FEATURE_DIM,
               standardize_future_term=True,
               energy_weights=hard["energy"]["weights"],
               temperature=float(hard["energy"]["temperature"]))

    print(f"protocol {protocol_sha256(hard)[:16]}  "
          f"dataset {hard['data']['dataset_version']}  seeds {seeds}")
    print(f"train {len(train_np['y'])} decisions / "
          f"validation {len(validation_np['y'])} decisions", flush=True)
    for name, data in (("train", train_np), ("validation", validation_np)):
        agree = float((np.asarray(data["pstar"]).argmax(1) == data["y"]).mean())
        print(f"  {name} teacher/reference agreement {agree:.6f}")
    online_validation = ~recovery_mask
    ceiling = 1 - 0.5 * float(np.asarray(
        validation_np["ambiguous"], dtype=bool,
    )[online_validation].mean())
    print(f"  random floor {1/16:.4f}   observable ceiling {ceiling:.4f}", flush=True)
    relation_oracle_probabilities = structured_relation_oracle_probabilities(
        validation_np,
        future_weight=float(hard["energy"]["weights"]["future"]),
        temperature=float(hard["energy"]["temperature"]),
    )
    relation_oracle = selection_error_decomposition(
        relation_oracle_probabilities[online_report_mask], validation_report_np,
    )
    target_only = structured_relation_target_only_diagnostics(
        validation_report_np,
    )
    print(
        "  structured relation-target oracle on report rows "
        f"accuracy={relation_oracle['accuracy']:.4f} "
        f"identifiable={relation_oracle['identifiable_accuracy']:.4f} "
        f"ambiguous={relation_oracle['ambiguous_accuracy']:.4f} "
        f"raw_illegal={relation_oracle['raw_illegal_selection_rate']:.4f}",
        flush=True,
    )
    print(
        "  target-only relation diagnostic on report rows "
        f"reference_in_min={target_only['all']['reference_in_minimum_set_rate']:.4f} "
        f"unique_reference={target_only['all']['unique_reference_minimum_rate']:.4f} "
        f"uniform_tie_expected="
        f"{target_only['all']['uniform_tie_break_expected_accuracy']:.4f} "
        f"mean_tie={target_only['all']['mean_minimum_set_size']:.3f}",
        flush=True,
    )

    val_audits = None
    if not args.skip_causal:
        # Causal replay needs the audits, which the array generator discards, so
        # they are rebuilt here. That is the slowest silent stretch in the run,
        # so it reports progress rather than sitting quiet for several minutes.
        started = time.time()
        val_audits = []
        expected = args.validation_groups * 2
        chunk = max(1, min(10, args.validation_groups))
        print(f"rebuilding {expected} validation sequences for causal replay "
              f"(each paired group is generated from its own seed)", flush=True)
        for start in range(0, args.validation_groups, chunk):
            count = min(chunk, args.validation_groups - start)
            _, part, _ = generate_m1_paired_rollout_split(
                hard, "validation", paired_groups=count, start_group_index=start)
            val_audits.extend(part)
            elapsed = time.time() - started
            rate = len(val_audits) / elapsed if elapsed else 0.0
            remaining = (expected - len(val_audits)) / rate if rate else 0.0
            print(f"  {len(val_audits)}/{expected} sequences  "
                  f"{rate*60:.1f}/min  eta {remaining/60:.1f} min", flush=True)
        rebuilt = rollout_learning_arrays_from_audits(
            hard, val_audits, future_hash_bins=32)
        # A mismatch means the replay would score against different worlds than
        # the arrays were built from, which would look plausible and be wrong.
        if len(rebuilt["y"]) != len(validation_np["y"]):
            print("ERROR: --validation-groups does not match the validation arrays "
                  f"({len(rebuilt['y'])} vs {len(validation_np['y'])} decisions)")
            return 1
        if not np.array_equal(np.asarray(rebuilt["y"]),
                              np.asarray(validation_np["y"])):
            print("ERROR: rebuilt validation audits do not match the validation "
                  "arrays; they were not produced by the same config or scale")
            return 1
        print(f"rebuilt {len(val_audits)} sequences in {time.time()-started:.0f}s "
              f"and verified they match the validation arrays", flush=True)

    T, V = tensors(train_np, device), tensors(validation_np, device)
    forced: dict[str, list[dict]] = {m: [] for m in STUDENTS}
    scorer_teacher: list[float] = []
    scorer_diagnostics: list[dict] = []
    calibration_probabilities: dict[str, np.ndarray] = {}
    # Train every seed first, so the single-step table and the primary contrasts
    # are on screen within minutes. The causal replay that follows takes orders
    # of magnitude longer, and its per-pair results are written as they land.
    trained: dict[int, dict] = {}
    print(f"\ntraining {len(seeds)} seeds x {len(STUDENTS)} students "
          f"on {len(train_np['y'])} decisions", flush=True)
    for seed in seeds:
        began = time.time()
        scorer, learned, scorer_trace = train_outcome_scorer(
            T, V, cfg, seed, device,
        )
        scorer_seed_diagnostics = {
            "seed": int(seed),
            "train_all_learning_rows": outcome_scorer_diagnostics(
                scorer, T, learned["train"],
            ),
            "train_online_chain": outcome_scorer_diagnostics(
                scorer, T, learned["train"],
                row_mask=~np.asarray(train_np["recovery"], dtype=bool),
            ),
            "validation_calibration_online": outcome_scorer_diagnostics(
                scorer, V, learned["validation"],
                row_mask=calibration_online_mask,
            ),
            "validation_report_online": outcome_scorer_diagnostics(
                scorer, V, learned["validation"],
                row_mask=online_report_mask,
            ),
            "training_trace": scorer_trace,
        }
        scorer_diagnostics.append(scorer_seed_diagnostics)
        report_diagnostic = scorer_seed_diagnostics["validation_report_online"]
        scorer_teacher.append(report_diagnostic["teacher_accuracy"])
        models = {}
        for method in STUDENTS:
            model, _ = train_student(
                method, T, _teachers(T, learned, method), cfg, seed, device)
            models[method] = model
            with torch.no_grad():
                probs = model(V["x"]).softmax(1).cpu().numpy()
            calibration_probabilities[f"{method}:seed{seed}"] = probs
            forced[method].append(selection_error_decomposition(
                probs[online_report_mask], validation_report_np,
            ))
            recovery_report = report_mask & recovery_mask
            forced[method][-1]["recovery_accuracy"] = (
                float(np.mean(
                    probs.argmax(axis=1)[recovery_report]
                    == validation_np["y"][recovery_report]
                )) if recovery_report.any() else None
            )
        trained[seed] = models
        train_diagnostic = scorer_seed_diagnostics["train_online_chain"]
        calibration_diagnostic = scorer_seed_diagnostics[
            "validation_calibration_online"
        ]
        print(
            f"  seed {seed} trained in {time.time()-began:.0f}s; "
            f"E train BCE={train_diagnostic['masked_bce']:.4f} "
            f"teacher={train_diagnostic['teacher_accuracy']:.4f}; "
            f"calibration BCE={calibration_diagnostic['masked_bce']:.4f} "
            f"teacher={calibration_diagnostic['teacher_accuracy']:.4f}",
            flush=True,
        )

    commit_calibration = calibrate_shared_commit_rule(
        calibration_probabilities, validation_np, hard,
    )
    cfg.update(commit_calibration["selected"])
    print(
        "selected shared commit rule on calibration groups: "
        f"p={cfg['commit_probability']:.3f} "
        f"margin={cfg['margin_threshold']:.3f}; "
        f"report rows={commit_calibration['report_rows']}",
        flush=True,
    )
    report_audits = (
        [
            audit for audit in val_audits
            if not paired_group_is_calibration(str(audit["paired_group_id"]))
        ] if val_audits is not None else None
    )
    if val_audits is not None and not report_audits:
        raise ValueError("validation report partition contains no paired groups")
    gate_tag = (
        f"p{int(round(float(cfg['commit_probability']) * 1000)):03d}_"
        f"m{int(round(float(cfg['margin_threshold']) * 1000)):03d}"
    )

    print(f"\n{'method':<24}{'accuracy':>20}{'template':>10}{'identif.':>10}"
          f"{'ambig.':>9}{'recovery':>10}")
    print("-" * 83)
    summary: dict[str, dict] = {}
    for method in sorted(STUDENTS, key=lambda m: -np.mean(
            [r["accuracy"] for r in forced[m]])):
        acc = np.array([r["accuracy"] for r in forced[method]])
        summary[method] = {
            "accuracy_mean": float(acc.mean()), "accuracy_std": float(acc.std()),
            "accuracy_seeds": [float(v) for v in acc],
            "template": float(np.mean([r["template_accuracy"] for r in forced[method]])),
            "identifiable": float(np.mean(
                [r["identifiable_accuracy"] for r in forced[method]])),
            "ambiguous": float(np.mean([r["ambiguous_accuracy"] for r in forced[method]])),
            "ambiguous_pair_containment": float(np.mean([
                r["ambiguous_pair_containment"] for r in forced[method]
            ])),
            "recovery_accuracy": (
                float(np.mean([
                    r["recovery_accuracy"] for r in forced[method]
                    if r["recovery_accuracy"] is not None
                ])) if any(
                    r["recovery_accuracy"] is not None for r in forced[method]
                ) else None
            ),
        }
        s = summary[method]
        print(f"{LABEL[method]:<24}{s['accuracy_mean']:>11.4f} +/- {s['accuracy_std']:.4f}"
              f"{s['template']:>10.4f}{s['identifiable']:>10.4f}"
              f"{s['ambiguous']:>9.4f}"
              f"{(s['recovery_accuracy'] or 0.0):>10.4f}")

    a = np.array(summary["cpmt_ctl_core"]["accuracy_seeds"])
    contrasts = {}
    for other in ("direct_future_loss", "future_no_execution", "direct_classifier"):
        o = np.array(summary[other]["accuracy_seeds"])
        contrasts[f"A_vs_{other}"] = {
            "difference": float(a.mean() - o.mean()),
            "seed_ranges_disjoint": bool(a.min() > o.max()),
        }
        print(f"A - {LABEL[other]:<22}{a.mean()-o.mean():+.4f}   "
              f"ranges disjoint: {a.min() > o.max()}")

    if not args.skip_causal:
        pairs = len(seeds) * len(ALL_METHODS)
        print(f"\nstarting causal self-rollout: {pairs} (method, seed) pairs over "
              f"{len(report_audits)} report-half sequences; results land one file at a time",
              flush=True)
        for seed in seeds:
            for method in ALL_METHODS:
                target = causal_dir / f"{method}_seed{seed}_{gate_tag}_v3.json"
                if target.exists():
                    continue
                began = time.time()
                oracle = method == "oracle_candidate_program"
                metrics, sequence_rows = causal_rollout_metrics(
                    None if oracle else trained[seed][method], report_audits, cfg,
                    oracle=oracle)
                metrics.update(method=method, seed=seed,
                               seconds=time.time() - began)
                target.write_text(json.dumps({
                    "schema_version": "cpmt-m1-causal-result-v3",
                    "aggregate": metrics,
                    "sequences": sequence_rows,
                }, indent=2), encoding="utf-8")
                print(f"  seed {seed} {method:<26} "
                      f"active={metrics['final_active_graph_correctness']:.4f}"
                      f"  history={metrics['final_history_exactness']:.4f}"
                      f"  ({metrics['seconds']:.0f}s)", flush=True)

        observable_path = causal_dir / f"observable_information_oracle_{gate_tag}_v3.json"
        if not observable_path.exists():
            began = time.time()
            metrics, sequence_rows = causal_rollout_metrics(
                None, report_audits, cfg, observable_oracle=True,
            )
            metrics.update(method="observable_information_oracle",
                           seconds=time.time() - began)
            observable_path.write_text(json.dumps({
                "schema_version": "cpmt-m1-causal-result-v3",
                "aggregate": metrics,
                "sequences": sequence_rows,
            }, indent=2), encoding="utf-8")
            print("  observable information oracle "
                  f"active={metrics['final_active_graph_correctness']:.4f} "
                  f"history={metrics['final_history_exactness']:.4f}", flush=True)

    causal_summary: dict[str, dict] = {}
    causal_payloads: dict[str, list[dict]] = {}
    if not args.skip_causal:
        print(f"\n{'method':<24}{'active':>10}{'mean':>10}{'contam/100':>12}"
              f"{'missing/100':>13}{'falsebirth/100':>16}")
        print("-" * 85)
        for method in ALL_METHODS:
            paths = [
                causal_dir / f"{method}_seed{s}_{gate_tag}_v3.json" for s in seeds
            ]
            payloads = [json.loads(path.read_text())
                        for path in paths if path.exists()]
            rows = [payload["aggregate"] for payload in payloads]
            if not rows:
                continue
            causal_payloads[method] = payloads
            def col(key):
                return float(np.mean([r[key] for r in rows]))
            causal_summary[method] = {
                "final_active_graph_correctness": col(
                    "final_active_graph_correctness"),
                "active_final_std": float(np.std(
                    [r["final_active_graph_correctness"] for r in rows])),
                "mean_active_graph_correctness": col(
                    "mean_active_graph_correctness"),
                "final_open_memory_correctness": col(
                    "final_open_memory_correctness"),
                "final_history_exactness": col("final_history_exactness"),
                "final_post_graph_correctness": col("final_post_graph_correctness"),
                "final_std": float(np.std(
                    [r["final_post_graph_correctness"] for r in rows])),
                "mean_post_graph_correctness": col("mean_post_graph_correctness"),
                "memory_contamination_per_100": col("memory_contamination_per_100"),
                "missing_open_facts_per_100": col("missing_open_facts_per_100"),
                "false_birth_growth_per_100": col("false_birth_growth_per_100"),
                "collateral_violation_per_100": col("collateral_violation_per_100"),
                "memory_contamination_auc_per_100_decisions": col(
                    "memory_contamination_auc_per_100_decisions"),
                "recovery_rate_within_window": col(
                    "recovery_rate_within_window"),
                "designed_recovery_eligible_sequences": col(
                    "designed_recovery_eligible_sequences"),
                "designed_recovery_trigger_rate": col(
                    "designed_recovery_trigger_rate"),
                "designed_recovery_rate_within_window": col(
                    "designed_recovery_rate_within_window"),
                "designed_pivot_error_out_of_scope": col(
                    "designed_pivot_error_out_of_scope"),
                "any_first_error_recovery_eligible_sequences": col(
                    "any_first_error_recovery_eligible_sequences"),
                "any_first_error_recovery_rate_within_window": col(
                    "any_first_error_recovery_rate_within_window"),
                "unresolved_active_error": col("unresolved_active_error"),
                # How often the method actually wrote its choice rather than
                # quarantining it. Without this the commit policy cannot be
                # tuned, and a method that looks accurate by refusing to act
                # cannot be told apart from one that acts correctly.
                "commit_rate": col("commit_rate"),
                "raw_invalid_selection_rate": col("raw_invalid_selection_rate"),
                "registered_selection_accuracy": col(
                    "registered_selection_accuracy"),
                "committed_registered_accuracy": col(
                    "committed_registered_accuracy"),
                "ambiguity_commit_rate": col("ambiguity_commit_rate"),
                "identifiable_commit_rate": col("identifiable_commit_rate"),
                "triggered_revisit_count": col("triggered_revisit_count"),
                "triggered_revisit_commit_rate": col(
                    "triggered_revisit_commit_rate"),
                "triggered_revisit_active_resolution_rate": col(
                    "triggered_revisit_active_resolution_rate"),
                "seeds_completed": len(rows),
            }
            c = causal_summary[method]
            print(f"{LABEL[method]:<24}{c['final_active_graph_correctness']:>10.4f}"
                  f"{c['mean_active_graph_correctness']:>10.4f}"
                  f"{c['memory_contamination_per_100']:>12.3f}"
                  f"{c['missing_open_facts_per_100']:>13.3f}"
                  f"{c['false_birth_growth_per_100']:>16.3f}")

    causal_complete = bool(causal_summary) and all(
        method in causal_summary
        and causal_summary[method]["seeds_completed"] == len(seeds)
        for method in ALL_METHODS
    )
    paired_statistics = (
        _paired_causal_statistics(causal_payloads, hard)
        if causal_complete else None
    )
    report = {
        "schema_version": "cpmt-m1-af-report-v2",
        "runner": "run_m1_af_scaled_v2",
        "formal_run": False,
        "test_generated": False,
        "protocol_sha256": protocol_sha256(hard),
        "training_provenance": training_provenance,
        "input_arrays": {
            "train": train_input,
            "validation": validation_input,
        },
        "dataset_version": hard["data"]["dataset_version"],
        "seeds": seeds,
        "train_decisions": int(np.sum(~np.asarray(train_np["recovery"], dtype=bool))),
        "train_recovery_examples": int(np.sum(train_np["recovery"])),
        "train_learning_rows": int(len(train_np["y"])),
        "validation_decisions": int(np.sum(
            ~np.asarray(validation_np["recovery"], dtype=bool)
        )),
        "validation_recovery_examples": int(np.sum(validation_np["recovery"])),
        "validation_learning_rows": int(len(validation_np["y"])),
        "validation_online_chain_decisions": int(online_validation.sum()),
        "validation_recovery_training_examples": int(recovery_mask.sum()),
        "observable_ceiling": ceiling,
        "teacher_reference_agreement": {
            "train": float((np.asarray(train_np["pstar"]).argmax(1)
                            == train_np["y"]).mean()),
            "validation_report": float((
                np.asarray(validation_np["pstar"]).argmax(1)[online_report_mask]
                == validation_np["y"][online_report_mask]
            ).mean()),
        },
        "structured_relation_target_oracle": relation_oracle,
        "structured_relation_target_only": target_only,
        "commit_calibration": commit_calibration,
        "scorer_teacher_validation_accuracy": scorer_teacher,
        "outcome_scorer_diagnostics": scorer_diagnostics,
        "teacher_forced": summary,
        "primary_contrasts": contrasts,
        "causal_rollout": causal_summary,
        "paired_causal_statistics": paired_statistics,
        "observable_information_oracle": (
            json.loads(observable_path.read_text())[
                "aggregate"
            ] if not args.skip_causal and observable_path.exists()
            else None
        ),
        "causal_complete": causal_complete,
    }
    (out_dir / "af_report.json").write_text(json.dumps(report, indent=2),
                                            encoding="utf-8")
    print(f"\nwrote {out_dir / 'af_report.json'}")
    if args.skip_causal or not report["causal_complete"]:
        print("NOTE: the causal self-rollout is incomplete, so the protocol's "
              "primary metrics are not established by this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
