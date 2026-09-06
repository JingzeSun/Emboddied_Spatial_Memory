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
    train_outcome_scorer, train_student, tensors,
)
from cpmt.m1_af_rollout import (  # noqa: E402
    CANDIDATE_FEATURE_DIM, causal_rollout_metrics,
    rollout_learning_arrays_from_audits, selection_error_decomposition,
)
from cpmt.m1_protocol import load_and_validate, protocol_sha256  # noqa: E402
from cpmt.m1_rollout import generate_m1_paired_rollout_split  # noqa: E402

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


def _load(path: Path) -> dict[str, np.ndarray]:
    data = {k: v for k, v in np.load(path, allow_pickle=True).items()}
    # Carried by the generator for reporting; not a model input.
    data.pop("teacher_matches_reference", None)
    return data


def _teachers(train, learned, method):
    if method == "future_no_execution":
        return learned["train"]
    if method == "execute_current_only":
        return train["pstar_current"]
    return train["pstar"]


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
    smoke = json.loads(
        (PROJECT / "configs" / "m1_af_smoke.json").read_text(encoding="utf-8"))
    seeds = args.seeds or list(hard["training"]["formal_seeds"])
    torch.set_num_threads(args.threads)
    out_dir = args.out_dir
    causal_dir = out_dir / "causal"
    causal_dir.mkdir(parents=True, exist_ok=True)

    train_np, validation_np = _load(args.train), _load(args.validation)
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
    ceiling = 1 - 0.5 * float(validation_np["ambiguous"].mean())
    print(f"  random floor {1/16:.4f}   observable ceiling {ceiling:.4f}", flush=True)

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
    # Train every seed first, so the single-step table and the primary contrasts
    # are on screen within minutes. The causal replay that follows takes orders
    # of magnitude longer, and its per-pair results are written as they land.
    trained: dict[int, dict] = {}
    print(f"\ntraining {len(seeds)} seeds x {len(STUDENTS)} students "
          f"on {len(train_np['y'])} decisions", flush=True)
    for seed in seeds:
        began = time.time()
        _, learned, _ = train_outcome_scorer(T, V, cfg, seed, device)
        scorer_teacher.append(float(
            (learned["validation"].cpu().numpy().argmax(1) == validation_np["y"]).mean()))
        models = {}
        for method in STUDENTS:
            model, _ = train_student(
                method, T, _teachers(T, learned, method), cfg, seed, device)
            models[method] = model
            with torch.no_grad():
                probs = model(V["x"]).softmax(1).cpu().numpy()
            forced[method].append(selection_error_decomposition(probs, validation_np))
        trained[seed] = models
        print(f"  seed {seed} trained in {time.time()-began:.0f}s", flush=True)

    print(f"\n{'method':<24}{'accuracy':>20}{'template':>10}{'identif.':>10}{'ambig.':>9}")
    print("-" * 73)
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
        }
        s = summary[method]
        print(f"{LABEL[method]:<24}{s['accuracy_mean']:>11.4f} +/- {s['accuracy_std']:.4f}"
              f"{s['template']:>10.4f}{s['identifiable']:>10.4f}{s['ambiguous']:>9.4f}")

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
              f"{len(val_audits)} sequences; results land one file at a time",
              flush=True)
        for seed in seeds:
            for method in ALL_METHODS:
                target = causal_dir / f"{method}_seed{seed}.json"
                if target.exists():
                    continue
                began = time.time()
                oracle = method == "oracle_candidate_program"
                metrics, _ = causal_rollout_metrics(
                    None if oracle else trained[seed][method], val_audits, cfg,
                    oracle=oracle)
                metrics.update(method=method, seed=seed,
                               seconds=time.time() - began)
                target.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
                print(f"  seed {seed} {method:<26} "
                      f"final={metrics['final_post_graph_correctness']:.4f}"
                      f"  mean={metrics['mean_post_graph_correctness']:.4f}"
                      f"  ({metrics['seconds']:.0f}s)", flush=True)

    causal_summary: dict[str, dict] = {}
    if not args.skip_causal:
        print(f"\n{'method':<24}{'final':>10}{'mean':>10}{'contam/100':>12}"
              f"{'missing/100':>13}{'falsebirth/100':>16}")
        print("-" * 85)
        for method in ALL_METHODS:
            rows = [json.loads((causal_dir / f"{method}_seed{s}.json").read_text())
                    for s in seeds if (causal_dir / f"{method}_seed{s}.json").exists()]
            if not rows:
                continue
            def col(key):
                return float(np.mean([r[key] for r in rows]))
            causal_summary[method] = {
                "final_post_graph_correctness": col("final_post_graph_correctness"),
                "final_std": float(np.std(
                    [r["final_post_graph_correctness"] for r in rows])),
                "mean_post_graph_correctness": col("mean_post_graph_correctness"),
                "memory_contamination_per_100": col("memory_contamination_per_100"),
                "missing_open_facts_per_100": col("missing_open_facts_per_100"),
                "false_birth_growth_per_100": col("false_birth_growth_per_100"),
                "collateral_violation_per_100": col("collateral_violation_per_100"),
                "seeds_completed": len(rows),
            }
            c = causal_summary[method]
            print(f"{LABEL[method]:<24}{c['final_post_graph_correctness']:>10.4f}"
                  f"{c['mean_post_graph_correctness']:>10.4f}"
                  f"{c['memory_contamination_per_100']:>12.3f}"
                  f"{c['missing_open_facts_per_100']:>13.3f}"
                  f"{c['false_birth_growth_per_100']:>16.3f}")

    report = {
        "runner": "run_m1_af_scaled",
        "formal_run": False,
        "test_generated": False,
        "protocol_sha256": protocol_sha256(hard),
        "dataset_version": hard["data"]["dataset_version"],
        "seeds": seeds,
        "train_decisions": int(len(train_np["y"])),
        "validation_decisions": int(len(validation_np["y"])),
        "observable_ceiling": ceiling,
        "teacher_reference_agreement": {
            "train": float((np.asarray(train_np["pstar"]).argmax(1)
                            == train_np["y"]).mean()),
            "validation": float((np.asarray(validation_np["pstar"]).argmax(1)
                                 == validation_np["y"]).mean()),
        },
        "scorer_teacher_validation_accuracy": scorer_teacher,
        "teacher_forced": summary,
        "primary_contrasts": contrasts,
        "causal_rollout": causal_summary,
        "causal_complete": bool(causal_summary) and all(
            v["seeds_completed"] == len(seeds) for v in causal_summary.values()),
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
