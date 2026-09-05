"""Generate one trainability paired-group shard in an isolated process."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np

from cpmt.m1_af_rollout import rollout_learning_arrays_from_audits
from cpmt.m1_protocol import load_and_validate
from cpmt.m1_rollout import (
    generate_m1_paired_rollout_split,
    records_sha256,
)
from cpmt.m1_trainability import reference_candidate_audit


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hard-config", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "validation"), required=True)
    parser.add_argument("--group-index", type=int, required=True)
    parser.add_argument("--future-hash-bins", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.group_index < 0 or args.future_hash_bins <= 0:
        raise ValueError("invalid shard index or future hash bins")
    output = args.output.resolve()
    if not output.is_relative_to((PROJECT / "outputs").resolve()):
        raise ValueError("shard output must remain inside project outputs")
    output.mkdir(parents=True, exist_ok=False)
    hard = load_and_validate(args.hard_config)
    online, audits, summary = generate_m1_paired_rollout_split(
        hard, args.split, paired_groups=1,
        start_group_index=args.group_index,
    )
    arrays = rollout_learning_arrays_from_audits(
        hard, audits, future_hash_bins=args.future_hash_bins,
    )
    arrays["group"] = np.full_like(arrays["group"], args.group_index)
    np.savez_compressed(output / "arrays.npz", **arrays)
    write_jsonl(output / "audit_sequences.jsonl", audits)
    write_jsonl(output / "online_steps.jsonl", online)
    audit_digest = records_sha256(audits)
    summary.update({
        "learning_cases": int(len(arrays["y"])),
        "online_feature_dim": int(arrays["x"].shape[1]),
        "future_target_dim": int(arrays["future"].shape[1]),
        "labelled_fraction": float(arrays["labelled"].mean()),
        "ambiguous_decision_fraction": float(arrays["ambiguous"].mean()),
        "audit_sha256": audit_digest,
        "candidate_audit": reference_candidate_audit(audits),
        "test_generated": False,
        "formal_data_ready": False,
    })
    write_json(output / "summary.json", summary)
    file_digest = hashlib.sha256()
    for name in ("arrays.npz", "audit_sequences.jsonl", "online_steps.jsonl"):
        file_digest.update((output / name).read_bytes())
    write_json(output / "complete.json", {
        "status": "complete",
        "split": args.split,
        "group_index": args.group_index,
        "audit_sha256": audit_digest,
        "file_bundle_sha256": file_digest.hexdigest(),
        "test_generated": False,
    })
    print(json.dumps({
        "status": "complete",
        "split": args.split,
        "group_index": args.group_index,
        "output": str(output),
    }), flush=True)


if __name__ == "__main__":
    main()
