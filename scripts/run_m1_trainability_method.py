"""Run one isolated A-F method for a nonformal M1 optimization point."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np
import torch

from cpmt.dev_learning import METHODS
from cpmt.m1_af_method import run_af_method
from cpmt.m1_protocol import load_and_validate
from cpmt.m1_trainability import (
    resolve_trainability_ladder,
    subset_paired_array_groups,
)


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as stored:
        return {key: stored[key].copy() for key in stored.files}


def load_shard_audits(run_root: Path, split: str, paired_groups: int):
    audits = []
    for group_index in range(paired_groups):
        matches = sorted(
            path.parent for path in (run_root / "shards").glob(
                f"{split}_{group_index:06d}_attempt*/complete.json"
            )
        )
        if not matches:
            raise FileNotFoundError(f"missing complete {split} shard {group_index}")
        with (matches[0] / "audit_sequences.jsonl").open(
            "r", encoding="utf-8",
        ) as handle:
            audits.extend(json.loads(line) for line in handle if line.strip())
    return audits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--method", choices=METHODS, required=True)
    parser.add_argument("--train-paired-groups", type=int, required=True)
    parser.add_argument("--student-steps", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    output = args.output.resolve()
    outputs_root = (PROJECT / "outputs").resolve()
    if not run_root.is_relative_to(outputs_root) or not output.is_relative_to(
        outputs_root
    ):
        raise ValueError("trainability method paths must remain inside project outputs")
    if args.train_paired_groups <= 0 or args.student_steps <= 0 or args.seed < 0:
        raise ValueError("invalid isolated trainability method point")
    output.mkdir(parents=True, exist_ok=False)

    hard = load_and_validate(run_root / "m1_hard_condition.json")
    af = json.loads((run_root / "m1_af_smoke.json").read_text(encoding="utf-8"))
    ladder_raw = json.loads(
        (run_root / "m1_trainability_ladder.json").read_text(encoding="utf-8")
    )
    ladder = resolve_trainability_ladder(hard, af, ladder_raw)
    config = dict(ladder["base_af_config"])
    config["student_steps"] = args.student_steps
    config["scorer_steps"] = args.student_steps
    torch.set_num_threads(int(config["cpu_threads"]))
    torch.use_deterministic_algorithms(True)

    train = subset_paired_array_groups(
        load_npz(run_root / "train_arrays.npz"), args.train_paired_groups,
    )
    validation = load_npz(run_root / "validation_arrays.npz")
    validation_audits = load_shard_audits(
        run_root, "validation", int(ladder["validation_paired_groups"]),
    )
    result, details, models = run_af_method(
        train, validation, validation_audits, config, args.seed, args.method,
    )
    result.update({
        "method": args.method,
        "student_steps": args.student_steps,
        "train_paired_groups": args.train_paired_groups,
        "train_decisions": int(len(train["y"])),
        "labelled_fraction": float(train["labelled"].mean()),
    })
    write_json(output / "details.json", details)
    for name, model in models.items():
        torch.save(model.state_dict(), output / f"{name}.pt")
    write_json(output / "result.json", result)
    digest = hashlib.sha256((output / "result.json").read_bytes()).hexdigest()
    write_json(output / "complete.json", {
        "status": "complete",
        "method": args.method,
        "train_paired_groups": args.train_paired_groups,
        "student_steps": args.student_steps,
        "seed": args.seed,
        "result_sha256": digest,
        "test_generated": False,
    })
    print(json.dumps({
        "status": "complete",
        "method": args.method,
        "groups": args.train_paired_groups,
        "steps": args.student_steps,
        "output": str(output),
    }), flush=True)


if __name__ == "__main__":
    main()
