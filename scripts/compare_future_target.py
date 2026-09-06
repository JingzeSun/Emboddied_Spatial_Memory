"""Measure whether the future target representation was handicapping method E.

E predicts the future without executing candidates, so its teacher is only as
good as the space it regresses in. The hashed structural projection is exact
but metric-free: two worlds differing by one edge fall into unrelated buckets,
so the squared error says almost nothing about how wrong a prediction is. A
world latent keeps the same state where distance means something.

This holds everything else fixed and swaps only that target, because "we made
the baseline stronger" has to be a measurement rather than an assertion. If E
does not improve, the hashed target was not the limitation and the claim that
A beats E stands on its own; if it does improve, A's margin over E must be
re-reported against the stronger baseline.

Generation dominates the runtime and is cached per representation, so an
interrupted run resumes from the arrays already on disk.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.dev_learning import (  # noqa: E402
    candidate_admissibility_mask, masked_candidate_probabilities,
    train_outcome_scorer, train_student, tensors,
)
from cpmt.m1_af_rollout import (  # noqa: E402
    CANDIDATE_FEATURE_DIM, build_rollout_learning_arrays,
    selection_error_decomposition, uniform_admissible_random_accuracy,
)
from cpmt.m1_protocol import load_and_validate  # noqa: E402

REPRESENTATIONS = ("hashed_tokens", "world_latent")


def _arrays(hard, split, groups, cache: Path):
    if cache.exists():
        return {k: v for k, v in np.load(cache, allow_pickle=True).items()}
    data, _, _ = build_rollout_learning_arrays(
        hard, split, paired_groups=groups, future_hash_bins=32)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=PROJECT / "configs" / "m1_hard_condition.json")
    parser.add_argument("--train-groups", type=int, default=120)
    parser.add_argument("--validation-groups", type=int, default=40)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="*", default=[7, 19, 31])
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()

    hard = load_and_validate(args.config)
    torch.set_num_threads(args.threads)
    device = torch.device("cpu")
    report: dict[str, dict] = {}

    for representation in REPRESENTATIONS:
        variant = copy.deepcopy(hard)
        variant["future"]["target_representation"] = representation
        train = _arrays(variant, "train", args.train_groups,
                        args.cache_dir / f"{representation}_train.npz")
        validation = _arrays(variant, "validation", args.validation_groups,
                             args.cache_dir / f"{representation}_validation.npz")
        for data in (train, validation):
            data.pop("teacher_matches_reference", None)
        T, V = tensors(train, device), tensors(validation, device)
        cfg = dict(hidden_dim=64, horizon=int(hard["future"]["primary_horizon"]),
                   learning_rate=2e-3, batch_size=64, student_steps=1000,
                   scorer_steps=1000, distillation_weight=1.0, auxiliary_weight=1.0,
                   candidate_feature_dim=CANDIDATE_FEATURE_DIM,
                   standardize_future_term=True,
                   energy_weights=hard["energy"]["weights"],
                   temperature=float(hard["energy"]["temperature"]))
        teacher, e_student, a_student = [], [], []
        for seed in args.seeds:
            _, learned, _ = train_outcome_scorer(T, V, cfg, seed, device)
            teacher.append(float(
                (learned["validation"].cpu().numpy().argmax(1) == validation["y"]).mean()))
            for method, store in (("future_no_execution", e_student),
                                  ("cpmt_ctl_core", a_student)):
                target = (learned["train"] if method == "future_no_execution"
                          else T["pstar"])
                model, _ = train_student(method, T, target, cfg, seed, device)
                with torch.no_grad():
                    logits = model(V["x"])
                    probs = masked_candidate_probabilities(
                        logits, candidate_admissibility_mask(V, logits),
                    ).cpu().numpy()
                store.append(selection_error_decomposition(probs, validation)["accuracy"])
            print(f"  {representation} seed {seed} done", flush=True)
        report[representation] = {
            "future_target_dim": int(train["future"].shape[1]),
            "e_teacher_validation_accuracy": float(np.mean(teacher)),
            "e_teacher_std": float(np.std(teacher)),
            "e_student_accuracy": float(np.mean(e_student)),
            "a_student_accuracy": float(np.mean(a_student)),
            "a_minus_e": float(np.mean(a_student) - np.mean(e_student)),
            "seeds": args.seeds,
        }
        r = report[representation]
        print(f"{representation:<15} dim {r['future_target_dim']:>4} | "
              f"E teacher {r['e_teacher_validation_accuracy']:.4f} | "
              f"E student {r['e_student_accuracy']:.4f} | "
              f"A student {r['a_student_accuracy']:.4f} | "
              f"A-E {r['a_minus_e']:+.4f}", flush=True)

    d_teacher = float((np.asarray(validation["pstar_current"]).argmax(1)
                       == validation["y"]).mean())
    random_floor = uniform_admissible_random_accuracy(
        validation["candidate_static_preflight_pass"],
        row_mask=~np.asarray(validation["recovery"], dtype=bool),
    )
    hashed, latent = report["hashed_tokens"], report["world_latent"]
    report["comparison"] = {
        "d_teacher_validation_accuracy": d_teacher,
        "random_floor": random_floor,
        "admitted_uniform_random_accuracy": random_floor,
        "e_teacher_gain": latent["e_teacher_validation_accuracy"]
        - hashed["e_teacher_validation_accuracy"],
        "a_minus_e_change": latent["a_minus_e"] - hashed["a_minus_e"],
        "formal_run": False,
    }
    print(f"\nD teacher (no future term at all) {d_teacher:.4f}   "
          f"admitted-uniform random floor {random_floor:.4f}")
    print(f"E teacher gain from the latent target "
          f"{report['comparison']['e_teacher_gain']:+.4f}")
    print(f"A's margin over E changes by "
          f"{report['comparison']['a_minus_e_change']:+.4f}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
