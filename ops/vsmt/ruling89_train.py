#!/usr/bin/env python3
"""Development-stage training entry (S2-R, rulings 89-2/89-3): one head set from concatenated record sources at one seed.

Used by the S2-06 SAM 2.1 development table (ops/vsmt/s2_06_sam2.sh: stages train0 and train1, and the optional retraining in
verify). The paper's S3 training entry is ops/vsmt/s3_03_train.py, which takes the recipe from
`lean_s3_03.training_settings`. This script produces no paper table row and reads no validation/test data.

Inputs: one or more record sources ``<run root>:<pass>:<arm>`` (e.g. the round-0 ELU-P records and the arm's own round-1
records), a registered seed and the arm (VSMT-lean or AssocOnly). Outputs: weights.json (total-loss selection),
weights_grouped.json with --group-selection (ruling 96 (a)) and training_receipt.json. Recipe: the S0-05 values (AdamW,
learning rate 1e-3, weight decay 1e-4, 20 epochs, checkpoints scored on held-out selection houses; the 39 development houses
are split 30 train / 9 selection by the S1-02a split seed, `lean_reid_head.holdout_split`) plus the two ruling-89 changes:
field-wise encoding (statistics from the training houses only) and the class-weighted existence loss (gone weight = present
rows / gone rows on the training houses; AssocOnly has no existence term). --revision-91 adds the cosine-decayed learning
rate (1e-3 to 1e-5), gradient-norm clipping at 1.0 and the -ln w existence prior correction; its --help text still says
"pending ruling 91", but these are part of the recipe frozen by ruling 99-1 and S2-06 always passes the flag. Sources are
concatenated in full without resampling; the budget is 20 epochs over the concatenation, and the updates taken are recorded
in the receipt.

Usage:
  python ops/vsmt/ruling89_train.py --source <root>:dagger_round_0:ELU-P [--source <root>:dagger_round_1:VSMT-lean] --arm VSMT-lean
      --seed 7 --out-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402

import ruling89_probes as probes  # noqa: E402  (sources, the house split)

STAGE = "vsmt.lean.ruling89.train.v1"


def main(argv: Sequence[str] | None = None) -> int:
    from vsmt import lean_model as model

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", dest="sources", action="append", required=True)
    parser.add_argument("--arm", required=True, choices=["VSMT-lean", "AssocOnly"])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--revision-91", action="store_true", help="pending ruling 91 only: cosine-decayed rate and gradient clipping")
    parser.add_argument("--group-selection", action="store_true",
                        help="ruling 96 (a): also write weights_grouped.json (association+birth by their term, existence by its own); "
                             "weights.json stays the total-loss selection and training is unchanged")
    args = parser.parse_args(argv)
    if args.seed not in arms.SEEDS:
        print(f"seed {args.seed} is not a registered seed {arms.SEEDS}", file=sys.stderr)
        return 2
    entry = probes.r88p._entry()
    training = entry.load_json(entry.S0_05_CONTRACT)["arms"]["VSMT-lean"]["training"]
    model.recipe_matches_contract(learning_rate=training["learning_rate"], epochs=training["epochs"], seeds=training["seeds"],
                                  dagger_rounds=training["dagger_rounds"], main_table_round=training["main_table_round"])
    groups, split, files = probes.load_groups(args.sources)
    train_records = [{k: v for k, v in row.items() if k != "tick"} for _, _, row in groups["train"]]
    validation_records = [{k: v for k, v in row.items() if k != "tick"} for _, _, row in groups["selection"]]
    assoc_only = args.arm == "AssocOnly"
    started = time.time()
    result = model.train_heads(train_records, validation_records, learning_rate=float(training["learning_rate"]),
                               weight_decay=float(training["weight_decay"]), epochs=int(training["epochs"]), seed=int(args.seed),
                               assoc_only=assoc_only, device=args.device, field_encoding=True, existence_class_weight=not assoc_only,
                               **probes.revision_kwargs(args), **({"group_selection": True} if args.group_selection else {}))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "weights.json").write_text(json.dumps(result["weights"]), encoding="utf-8")
    grouped = result.get("grouped")
    if grouped is not None:
        (out_dir / "weights_grouped.json").write_text(json.dumps(grouped["weights"]), encoding="utf-8")
    receipt = {"stage": STAGE, "arm": args.arm, "assoc_only": assoc_only, "seed": args.seed, "sources": args.sources, "holdout": split,
               "recipe": {"learning_rate": training["learning_rate"], "weight_decay": training["weight_decay"], "epochs": training["epochs"],
                          "field_encoding": True, "existence_class_weight": not assoc_only, **probes.revision_kwargs(args),
                          "concatenation": "every source in full, no resampling; the budget is the registered epochs over the concatenation"},
               "train_frames": len(train_records), "validation_frames": len(validation_records),
               "updates_taken": result["updates_taken"], "existence_class_weight": result["weights"]["training"].get("existence_class_weight"),
               "train_curve": result["train_curve"], "validation_curve": result["validation_curve"], "best_epoch": result["best_epoch"],
               "train_curve_terms": result["train_curve_terms"], "validation_curve_terms": result["validation_curve_terms"],
               "diverged": result["diverged"], "weights_sha256": result["weights"]["sha256"],
               "group_selection": None if grouped is None else {"rule": model.GROUP_SELECTION_RULE, "best_epoch_by_group": grouped["best_epoch_by_group"],
                                                               "weights_sha256": grouped["weights"]["sha256"], "file": "weights_grouped.json"},
               "files": files, "device": args.device,
               "code_commit": entry._git("rev-parse", "HEAD"), "wall_seconds": round(time.time() - started, 1),
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out_dir / "training_receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(f"[ruling89-train] {args.arm} seed {args.seed}: best epoch {result['best_epoch']}, diverged {result['diverged']}, "
          f"{result['updates_taken']} updates, weights {result['weights']['sha256'][:12]}, {receipt['wall_seconds']} s"
          + ("" if grouped is None else f"; grouped epochs {grouped['best_epoch_by_group']}, weights {grouped['weights']['sha256'][:12]}"))
    return 0 if not result["diverged"] else 1


if __name__ == "__main__":
    sys.exit(main())
