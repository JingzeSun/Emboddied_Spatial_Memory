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
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.hashing import canonical_json  # noqa: E402
from cpmt.m1_af_rollout import rollout_learning_arrays_from_audits  # noqa: E402
from cpmt.m1_protocol import load_and_validate, protocol_sha256  # noqa: E402
from cpmt.m1_rollout import generate_m1_paired_rollout_split  # noqa: E402

ARRAY_KEYS_ORDERED = None  # discovered from the first shard


def _shard(task: tuple[str, str, int, int, str]) -> tuple[int, str]:
    """Generate exactly one paired group and write it as a shard."""
    config_path, split, group_index, future_hash_bins, out_dir = task
    config = load_and_validate(Path(config_path))
    _, audits, _ = generate_m1_paired_rollout_split(
        config, split, paired_groups=1, start_group_index=group_index,
    )
    arrays = rollout_learning_arrays_from_audits(
        config, audits, future_hash_bins=future_hash_bins,
    )
    # Every shard sees only its own group, so the local group column is all
    # zeros; the parent restores the serial numbering on merge.
    path = Path(out_dir) / f"{split}_{group_index:06d}.npz"
    np.savez(path, **arrays)
    return group_index, str(path)


def generate_parallel(
    config_path: Path, split: str, paired_groups: int, *,
    future_hash_bins: int, workers: int, out_dir: Path,
) -> dict[str, np.ndarray]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (str(config_path), split, index, future_hash_bins, str(out_dir))
        for index in range(paired_groups)
    ]
    started = time.time()
    with mp.Pool(processes=workers) as pool:
        done = 0
        results: list[tuple[int, str]] = []
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
    for group_index, path in results:
        shard = np.load(path, allow_pickle=True)
        for key in shard.files:
            merged.setdefault(key, []).append(shard[key])
        rows = len(shard["y"])
        groups.append(np.full(rows, group_index, dtype=np.int64))
    arrays = {key: np.concatenate(value) for key, value in merged.items()}
    arrays["group"] = np.concatenate(groups)
    print(f"generated {paired_groups} paired groups in "
          f"{time.time()-started:.1f}s with {workers} workers", flush=True)
    return arrays


def _digest(arrays: dict[str, np.ndarray]) -> str:
    import hashlib
    digest = hashlib.sha256()
    for key in sorted(arrays):
        value = np.asarray(arrays[key])
        digest.update(key.encode("utf-8"))
        digest.update(str(value.dtype).encode("utf-8"))
        digest.update(str(value.shape).encode("utf-8"))
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(PROJECT / "configs" / "m1_hard_condition.json"))
    parser.add_argument("--split", choices=["train", "validation"], required=True)
    parser.add_argument("--paired-groups", type=int, required=True)
    parser.add_argument("--future-hash-bins", type=int, default=32)
    parser.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    parser.add_argument("--out", required=True, help="output .npz path")
    parser.add_argument("--shard-dir", default=None)
    parser.add_argument("--verify", action="store_true",
                        help="also generate serially and require identical arrays")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_and_validate(config_path)
    out = Path(args.out)
    shard_dir = Path(args.shard_dir) if args.shard_dir else out.parent / f"{out.stem}_shards"
    print(f"protocol sha256 {protocol_sha256(config)[:16]}  "
          f"dataset {config['data']['dataset_version']}", flush=True)

    arrays = generate_parallel(
        config_path, args.split, args.paired_groups,
        future_hash_bins=args.future_hash_bins, workers=args.workers,
        out_dir=shard_dir,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, **arrays)
    print(f"wrote {out}  decisions={len(arrays['y'])}  digest={_digest(arrays)[:16]}")

    if args.verify:
        print("verifying against a serial run...", flush=True)
        started = time.time()
        _, audits, _ = generate_m1_paired_rollout_split(
            config, args.split, paired_groups=args.paired_groups,
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
        "runner": "generate_m1_parallel",
        "split": args.split,
        "paired_groups": args.paired_groups,
        "workers": args.workers,
        "protocol_sha256": protocol_sha256(config),
        "dataset_version": config["data"]["dataset_version"],
        "decisions": int(len(arrays["y"])),
        "arrays_digest": _digest(arrays),
        "formal_run": False,
        "test_generated": False,
    }
    (out.with_suffix(".manifest.json")).write_text(
        canonical_json(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
