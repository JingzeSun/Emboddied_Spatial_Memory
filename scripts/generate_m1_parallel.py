"""Generate M1 paired rollout arrays across processes, one paired group each.

Generation is the CPU-bound half of a formal run and every paired group depends
only on its own seed, so groups fan out across cores with no coordination. Each
worker writes its own shard and the parent concatenates them in group order, so
the merged arrays are byte-identical to a serial run; ``--verify`` checks that
against a serial reference instead of assuming it.

This is a runner, not a protocol change: it produces the same data the serial
path produces, and it does not train, evaluate, or touch the sealed test split.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.hashing import canonical_json  # noqa: E402
from cpmt.m1_af_rollout import (  # noqa: E402
    TEMPLATES,
    current_now_comparability_diagnostics,
    posterior_term_influence_diagnostics,
    rollout_learning_arrays_from_audits,
)
from cpmt.m1_protocol import load_and_validate, protocol_sha256  # noqa: E402
from cpmt.m1_rollout import generate_m1_paired_rollout_split  # noqa: E402
from cpmt.run_provenance import arrays_sha256, capture_run_provenance  # noqa: E402

ARRAY_KEYS_ORDERED = None  # discovered from the first shard


def _shard(
    task: tuple[str, str, int, int, str],
) -> tuple[int, str, dict[str, object]]:
    """Generate exactly one paired group and write it as a shard."""
    config_path, split, group_index, future_hash_bins, out_dir = task
    config = load_and_validate(Path(config_path))
    _, audits, summary = generate_m1_paired_rollout_split(
        config, split, paired_groups=1, start_group_index=group_index,
    )
    arrays = rollout_learning_arrays_from_audits(
        config, audits, future_hash_bins=future_hash_bins,
    )
    # Every shard sees only its own group, so the local group column is all
    # zeros; the parent restores the serial numbering on merge.
    path = Path(out_dir) / f"{split}_{group_index:06d}.npz"
    np.savez(path, **arrays)
    return group_index, str(path), summary["family_mechanism_audit"]


def _aggregate_family_mechanism_audits(
    audits: list[dict[str, object]], families: list[str],
) -> dict[str, object]:
    """Combine per-shard behavior facts without trusting family labels alone."""
    by_family: dict[str, object] = {}
    fingerprints: dict[str, str] = {}
    for family in families:
        support = 0
        reference_templates: Counter[str] = Counter()
        observation_modes: Counter[str] = Counter()
        scenario_variants: Counter[str] = Counter()
        collateral_count = 0.0
        for audit in audits:
            item = audit["by_family"][family]
            item_support = int(item["support"])
            support += item_support
            reference_templates.update(item["reference_template_counts"])
            observation_modes.update(item["observation_mode_counts"])
            scenario_variants.update(item["scenario_variant_counts"])
            rate = item["explicit_legal_collateral_contrast_rate"]
            if rate is not None:
                collateral_count += float(rate) * item_support
        fingerprint_payload = {
            "reference_templates": sorted(reference_templates),
            "observation_modes": sorted(observation_modes),
            "has_explicit_legal_collateral_contrast": collateral_count > 0.0,
        }
        fingerprint = canonical_json(fingerprint_payload)
        fingerprints[family] = fingerprint
        by_family[family] = {
            "support": support,
            "reference_template_counts": dict(sorted(reference_templates.items())),
            "observation_mode_counts": dict(sorted(observation_modes.items())),
            "scenario_variant_counts": dict(sorted(scenario_variants.items())),
            "behavioral_fingerprint_payload": fingerprint_payload,
            "behavioral_fingerprint_sha256": hashlib.sha256(
                fingerprint.encode("utf-8")
            ).hexdigest(),
            "explicit_legal_collateral_contrast_rate": (
                collateral_count / support if support else None
            ),
        }
    duplicate_groups = [
        sorted(group) for group in {
            tuple(sorted(
                family for family, value in fingerprints.items()
                if value == fingerprint
            ))
            for fingerprint in fingerprints.values()
        }
        if len(group) > 1
    ]
    paired_group_support_by_family = {
        family: sum(
            int(audit["by_family"][family]["support"] > 0)
            for audit in audits
        )
        for family in families
    }
    return {
        "by_family": by_family,
        "paired_group_support_by_family": paired_group_support_by_family,
        "behavioral_fingerprints_unique": not duplicate_groups,
        "duplicate_behavioral_fingerprint_groups": sorted(duplicate_groups),
        "c10_reference_templates": sorted(
            by_family["C10"]["reference_template_counts"]
        ),
        "c10_dynamic_static_variants_present": (
            set(by_family["C10"]["reference_template_counts"])
            == {"BIND", "NOOP"}
        ),
        "c11_legal_collateral_contrast_present": (
            float(by_family["C11"][
                "explicit_legal_collateral_contrast_rate"
            ] or 0.0) == 1.0
        ),
    }


def generate_parallel(
    config_path: Path, split: str, paired_groups: int, *,
    future_hash_bins: int, workers: int, out_dir: Path,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (str(config_path), split, index, future_hash_bins, str(out_dir))
        for index in range(paired_groups)
    ]
    started = time.time()
    with mp.Pool(processes=workers) as pool:
        done = 0
        results: list[tuple[int, str, dict[str, object]]] = []
        for item in pool.imap_unordered(_shard, tasks, chunksize=1):
            results.append(item)
            done += 1
            if done % max(1, paired_groups // 20) == 0 or done == paired_groups:
                rate = done / (time.time() - started)
                remaining = (paired_groups - done) / rate if rate else 0.0
                print(f"  {done}/{paired_groups} groups  "
                      f"{rate*60:.1f}/min  eta {remaining/60:.1f} min", flush=True)
    results.sort()
    merged: dict[str, list[np.ndarray]] = {}
    groups: list[np.ndarray] = []
    for group_index, path, _ in results:
        shard = np.load(path, allow_pickle=True)
        for key in shard.files:
            merged.setdefault(key, []).append(shard[key])
        rows = len(shard["y"])
        groups.append(np.full(rows, group_index, dtype=np.int64))
    arrays = {key: np.concatenate(value) for key, value in merged.items()}
    arrays["group"] = np.concatenate(groups)
    print(f"generated {paired_groups} paired groups in "
          f"{time.time()-started:.1f}s with {workers} workers", flush=True)
    family_mechanism_audit = _aggregate_family_mechanism_audits(
        [item[2] for item in results],
        list(load_and_validate(config_path)["data"]["scenario_families"]),
    )
    return arrays, family_mechanism_audit


def _digest(arrays: dict[str, np.ndarray]) -> str:
    return arrays_sha256(arrays)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(PROJECT / "configs" / "m1_hard_condition.json"))
    parser.add_argument("--split", choices=["train", "validation"], required=True)
    parser.add_argument(
        "--paired-groups", type=int, required=True,
        help=(
            "total mixed paired groups; every group contains all C00-C11 "
            "families, so this value is not multiplied by 12"
        ),
    )
    parser.add_argument("--future-hash-bins", type=int, default=32)
    parser.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    parser.add_argument("--out", required=True, help="output .npz path")
    parser.add_argument("--shard-dir", default=None)
    parser.add_argument("--verify", action="store_true",
                        help="also generate serially and require identical arrays")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_and_validate(config_path)
    paired_groups_total = int(args.paired_groups)
    if paired_groups_total <= 0:
        raise ValueError("paired-groups must be positive")
    configured_families = list(config["data"]["scenario_families"])
    generation_provenance = capture_run_provenance(
        PROJECT, component="m1_array_generation", entrypoint=Path(__file__),
    )
    out = Path(args.out)
    shard_dir = Path(args.shard_dir) if args.shard_dir else out.parent / f"{out.stem}_shards"
    print(f"protocol sha256 {protocol_sha256(config)[:16]}  "
          f"dataset {config['data']['dataset_version']}", flush=True)

    generation_started = time.time()
    arrays, family_mechanism_audit = generate_parallel(
        config_path, args.split, paired_groups_total,
        future_hash_bins=args.future_hash_bins, workers=args.workers,
        out_dir=shard_dir,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, **arrays)
    generation_seconds = time.time() - generation_started
    agree = np.asarray(arrays["teacher_matches_reference"], dtype=bool)
    recovery = np.asarray(arrays["recovery"], dtype=bool)
    online = ~recovery
    family_indices = np.asarray(arrays["scenario_family_index"], dtype=np.int64)
    family_health = {}
    activation_by_family = {}
    learning_group_support_by_family = {}
    for family_index, family in enumerate(configured_families):
        family_mask = online & (family_indices == family_index)
        support = int(family_mask.sum())
        learning_group_support_by_family[family] = int(len(np.unique(
            np.asarray(arrays["group"], dtype=np.int64)[family_mask]
        )))
        family_health[family] = {
            "support": support,
            "reference_agreement": (
                float(agree[family_mask].mean()) if support else None
            ),
        }
        activation_by_family[family] = {
            term: {
                "nonzero_fraction": (
                    float(np.mean(
                        np.asarray(arrays[f"candidate_energy_{term}"])[family_mask]
                        != 0.0
                    )) if support else None
                ),
                "distinct_values": (
                    int(len(np.unique(np.round(
                        np.asarray(arrays[f"candidate_energy_{term}"])[family_mask],
                        9,
                    )))) if support else 0
                ),
            }
            for term in ("now", "collateral")
        }
    reference_templates = np.asarray(arrays["candidate_templates"])[
        np.arange(len(arrays["y"])), np.asarray(arrays["y"], dtype=np.int64)
    ]
    c10_mask = online & (
        family_indices == configured_families.index("C10")
    )
    c10_reference_templates = sorted({
        TEMPLATES[int(value)] for value in reference_templates[c10_mask]
    })
    c11_mask = online & (
        family_indices == configured_families.index("C11")
    )
    bind_code = TEMPLATES.index("BIND")
    c11_legal_collateral = (
        np.asarray(arrays["candidate_static_preflight_pass"], dtype=bool)
        & np.asarray(arrays["candidate_legal"], dtype=bool)
        & (np.asarray(arrays["candidate_templates"], dtype=np.int64) == bind_code)
        & (np.asarray(arrays["candidate_energy_collateral"]) == 1.0)
    )
    c11_contrast_rate = (
        float(c11_legal_collateral[c11_mask].any(axis=1).mean())
        if c11_mask.any() else 0.0
    )
    current_now_audit = current_now_comparability_diagnostics(
        arrays, configured_families,
    )
    influence_contract = config["energy"]["posterior_influence_audit"]
    posterior_influence = posterior_term_influence_diagnostics(
        arrays,
        weights=config["energy"]["weights"],
        temperature=float(config["energy"]["temperature"]),
        scenario_families=configured_families,
        terms=influence_contract["terms"],
        total_variation_thresholds=influence_contract[
            "total_variation_thresholds"
        ],
    )
    family_mechanism_gate = {
        "all_configured_families_in_every_paired_group": all(
            int(value) == paired_groups_total
            for value in family_mechanism_audit[
                "paired_group_support_by_family"
            ].values()
        ),
        "behavioral_fingerprints_unique": family_mechanism_audit[
            "behavioral_fingerprints_unique"
        ],
        "duplicate_behavioral_fingerprint_groups": family_mechanism_audit[
            "duplicate_behavioral_fingerprint_groups"
        ],
        "c10_reference_templates": c10_reference_templates,
        "c10_dynamic_static_variants_present": (
            set(c10_reference_templates) == {"BIND", "NOOP"}
        ),
        "c11_legal_collateral_contrast_rate": c11_contrast_rate,
        "c11_legal_collateral_contrast_present_each_row": (
            c11_contrast_rate == 1.0
        ),
    }
    health_contract = config["energy"]["teacher_health_gate"]
    overall_agreement = float(agree[online].mean())
    overall_pass = overall_agreement >= float(
        health_contract["reference_agreement_overall_minimum"]
    )
    each_family_pass = all(
        item["support"] > 0
        and item["reference_agreement"]
        >= float(health_contract["reference_agreement_each_family_minimum"])
        for item in family_health.values()
    )
    teacher_health_gate = {
        "applicable": args.split == "train",
        "overall_reference_agreement": overall_agreement,
        "overall_minimum": float(
            health_contract["reference_agreement_overall_minimum"]
        ),
        "each_family_minimum": float(
            health_contract["reference_agreement_each_family_minimum"]
        ),
        "by_family": family_health,
        "pass": bool(
            overall_pass
            and each_family_pass
            and family_mechanism_gate[
                "all_configured_families_in_every_paired_group"
            ]
            and family_mechanism_gate["behavioral_fingerprints_unique"]
            and family_mechanism_gate[
                "c10_dynamic_static_variants_present"
            ]
            and family_mechanism_gate[
                "c11_legal_collateral_contrast_present_each_row"
            ]
            and current_now_audit[
                "exact_ambiguity_current_target_identity_rate"
            ] == 1.0
            and current_now_audit["fixed_natural_range_scaling"][
                "all_available_values_within_0_1"
            ]
            and current_now_audit["fixed_natural_range_scaling"][
                "maximum_absolute_scaling_error"
            ] <= 1e-6
        ),
        "failure_action": health_contract["failure_action"],
    }
    print(f"wrote {out}  learning_rows={len(arrays['y'])} "
          f"(online={int((~arrays['recovery']).sum())}, "
          f"recovery={int(arrays['recovery'].sum())})  "
          f"digest={_digest(arrays)[:16]}")
    print(f"teacher/reference agreement {overall_agreement:.6f}  "
          f"({int((~agree[online]).sum())} disagreements of "
          f"{int(online.sum())} online learning rows)")
    print(
        "teacher health gate "
        f"{'PASS' if teacher_health_gate['pass'] else 'FAIL'}",
        flush=True,
    )

    if args.verify:
        print("verifying against a serial run...", flush=True)
        started = time.time()
        _, audits, _ = generate_m1_paired_rollout_split(
            config, args.split, paired_groups=paired_groups_total,
        )
        serial = rollout_learning_arrays_from_audits(
            config, audits, future_hash_bins=args.future_hash_bins,
        )
        serial_seconds = time.time() - started
        if _digest(serial) != _digest(arrays):
            differing = [
                key for key in sorted(serial)
                if not np.array_equal(np.asarray(serial[key]), np.asarray(arrays[key]))
            ]
            print(f"MISMATCH in {differing}")
            return 1
        print(f"identical to serial ({serial_seconds:.1f}s serial)")
    manifest = {
        "schema_version": "cpmt-m1-generation-manifest-v5",
        "runner": "generate_m1_parallel_v5",
        "split": args.split,
        "configured_scenario_families": configured_families,
        "configured_family_count": len(configured_families),
        "paired_groups_total": paired_groups_total,
        "paired_group_count_semantics": (
            "total_mixed_groups_each_group_contains_all_families"
        ),
        "configured_paired_groups_for_split": int(
            config["data"]["paired_groups"][args.split]
        ),
        "causal_paired_group_support_by_family": {
            family: int(value)
            for family, value in family_mechanism_audit[
                "paired_group_support_by_family"
            ].items()
        },
        "learning_group_support_by_family": learning_group_support_by_family,
        "workers": args.workers,
        "generation_seconds": generation_seconds,
        "protocol_sha256": protocol_sha256(config),
        "dataset_version": config["data"]["dataset_version"],
        # ``decisions`` is retained for old readers; M1-v2 distinguishes the
        # actual online chain from counterfactual recovery training rows.
        "decisions": int(len(arrays["y"])),
        "online_chain_decisions": int((~arrays["recovery"]).sum()),
        "recovery_training_examples": int(arrays["recovery"].sum()),
        "arrays_digest": _digest(arrays),
        "merged_npz_bytes": int(out.stat().st_size),
        "retained_shard_count": int(len(list(shard_dir.glob("*.npz")))),
        "retained_shard_bytes": int(sum(
            path.stat().st_size for path in shard_dir.glob("*.npz")
        )),
        "teacher_reference_agreement": overall_agreement,
        "teacher_disagreement_decisions": int((~agree[online]).sum()),
        "teacher_health_gate": teacher_health_gate,
        "family_mechanism_audit": family_mechanism_audit,
        "family_mechanism_gate": family_mechanism_gate,
        "current_now_comparability": current_now_audit,
        "teacher_posterior_term_influence": posterior_influence,
        "live_energy_activation_by_family": activation_by_family,
        "formal_run": False,
        "test_generated": False,
        "generation_provenance": generation_provenance,
    }
    (out.with_suffix(".manifest.json")).write_text(
        canonical_json(manifest), encoding="utf-8")
    if args.split == "train" and not teacher_health_gate["pass"]:
        print(
            "ERROR: train teacher health gate failed; do not start training",
            flush=True,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
