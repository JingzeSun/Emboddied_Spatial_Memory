"""S3-03 (ruling 104, 2026-10-03): the registered rules of training and configuration selection, as pure functions.

This is the module where the paper's training recipe (ruling 99-1, METHOD section 7) is assembled:
``training_settings`` returns, per trained arm and DAgger round, the recipe switches that ``ops/vsmt/s3_03_train.py``
passes to ``lean_model.train_heads_streamed`` together with the S0-05 learning rate, weight decay and epochs.  The
functions and constants are shared by the training entry, the scheduler and the selection readings:
  * training and selection houses (104-1 1a): the S3 train manifest, already in S0-02 split order, gives its first 240
    houses to training and its last 60 to checkpoint scoring only.  The split is fixed by the manifest, independent of
    outcomes; a house whose generation or cache failed is absent and never replaced.  The development-stage
    ``holdout_split`` (the first 30 houses train, the rest select) would train S3 on 30 houses, so S3 does not use it;
  * per learned arm and round, the training settings (the ruling-99-1 recipe, 104-1 1c / 1d): the label source (teacher
    records or HeuristicLabel records), whether there is no existence head (AssocOnly), and whether the checkpoint is
    chosen by grouped selection (round 1 of VSMT-lean and HeuristicLabel) or by the total held-out loss;
  * the manifest guard (104-6): the fit pass and the round-0 / round-1 rollouts take only episodes of the S3 train
    manifest, the validation audits only episodes of the validation manifest; test is never handed out;
  * the selection readings (104-1 1f): over every validation audit of one front end (each arm and configuration, the
    learned arms and AssocOnly at each seed) one exclusion list per metric, then the house mean of every run and the
    seed mean of the seeded arms, giving the AssocOnly reference and the inputs of S3-04's ``select_configuration``.
Inputs are the committed manifest and arm names (the readings also take each run's per-episode reports); outputs are
house lists, settings and readings.  Example: round-1 HeuristicLabel reads ``heuristic_training_records.jsonl.gz`` with
grouped selection; a validation episode handed to a round-0 rollout is refused by the entry as not in the train
manifest (exit code 2).  The module reads no data file, trains nothing and selects no configuration (S3-04 does).
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

STAGE = "vsmt.lean.s3_03.v1"
MANIFEST_PATH = Path(__file__).resolve().parents[2] / "configs" / "vsmt" / "lean_s3_01_manifests.json"
MANIFEST_SPLIT_RULE = (
    "ruling 104-6: the fit, round-0 and round-1 passes take only episodes of the S3 train manifest, the validation audits only "
    "episodes of the validation manifest; test is never handed out (ruling 103-1)"
)

#: Ruling 104-1 1a: the S3 train manifest in its split order, the first 240 houses train and the last 60 score checkpoints.
TRAINING_HOUSE_COUNT = 240
SELECTION_HOUSE_COUNT = 60
CHECKPOINT_SPLIT_RULE = (
    "ruling 104-1 1a: the S3 train manifest (configs/vsmt/lean_s3_01_manifests.json, already in S0-02 split order) gives its "
    "first 240 houses to training and its last 60 to checkpoint selection; the split is fixed by the manifest, a house whose "
    "generation or cache failed is simply absent and never replaced; the encoding statistics and the class weight come from "
    "the training houses only, the ELU-P fit and the rollouts use every train house"
)

#: The records each label source writes next to an S2-04 episode receipt (ruling 104-1 1c: HeuristicLabel's own file).
RECORD_FILES = {"teacher": "training_records.jsonl.gz", "heuristic": "heuristic_training_records.jsonl.gz"}

#: The three trained arms (NoVersion uses VSMT-lean's heads, ruling 99-1 / 104-1 1d) and their label sources.
TRAINED_ARMS = ("VSMT-lean", "AssocOnly", "HeuristicLabel")
LABEL_SOURCE = {"VSMT-lean": "teacher", "AssocOnly": "teacher", "HeuristicLabel": "heuristic"}
ROUNDS = (0, 1)
#: Ruling 99-1 / 96: round 1 keeps the grouped selection for the arms with an existence head; round 0 the total-loss one.
GROUPED_ARMS_IN_ROUND_1 = ("VSMT-lean", "HeuristicLabel")
#: Ruling 99-1 (the evaluated recipe, ``s2r_recipe`` in S0-05): field-wise encoding, class-weighted existence loss, cosine
#: rate 1e-3 -> 1e-5, gradient clipping 1.0, decisions on the ln w corrected logit.  These are the values the evaluated
#: entry passed (``ruling89_probes.revision_kwargs`` with --revision-91); a test binds the two.
COSINE_MIN_LEARNING_RATE = 1e-5
GRADIENT_CLIP_NORM = 1.0


class LeanS3_03Error(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS3_03Error(code)


def checkpoint_split(train_manifest: Sequence[str]) -> dict[str, Any]:
    """The training houses and the checkpoint-selection houses of the S3 train manifest (ruling 104-1 1a)."""

    houses = [str(house) for house in train_manifest]
    _require(len(houses) == TRAINING_HOUSE_COUNT + SELECTION_HOUSE_COUNT, f"train_manifest_size_{len(houses)}")
    _require(len(set(houses)) == len(houses), "train_manifest_duplicated")
    return {"rule": CHECKPOINT_SPLIT_RULE, "training_houses": houses[:TRAINING_HOUSE_COUNT],
            "selection_houses": houses[TRAINING_HOUSE_COUNT:]}


def training_settings(arm: str, round_index: int) -> dict[str, Any]:
    """What one training of ``arm`` in ``round_index`` reads and how it is trained and selected (rulings 99-1, 104-1)."""

    _require(arm in TRAINED_ARMS, f"arm_not_trained_in_s3:{arm}")
    _require(round_index in ROUNDS, f"round_invalid:{round_index}")
    assoc_only = arm == "AssocOnly"
    return {
        "arm": arm, "round": round_index, "label_source": LABEL_SOURCE[arm], "record_file": RECORD_FILES[LABEL_SOURCE[arm]],
        "assoc_only": assoc_only,
        "kwargs": {"field_encoding": True, "existence_class_weight": not assoc_only,
                   "cosine_min_learning_rate": COSINE_MIN_LEARNING_RATE, "gradient_clip_norm": GRADIENT_CLIP_NORM,
                   "existence_prior_correction": True,
                   "group_selection": round_index == 1 and arm in GROUPED_ARMS_IN_ROUND_1},
        "uses": "grouped" if round_index == 1 and arm in GROUPED_ARMS_IN_ROUND_1 else "total",
    }


def manifest_houses(manifest: Mapping[str, Any], split: str) -> list[str]:
    """One split's committed house list; ``test`` is never handed out here (ruling 103-1)."""

    _require(split in ("train", "validation"), f"split_not_readable_in_s3_03:{split}")
    houses = manifest.get(split)
    _require(isinstance(houses, list) and bool(houses), f"manifest_split_missing:{split}")
    return [str(house) for house in houses]


#: Ruling 104-1 1f: the validation runs S3-03 reads per front end -- arm -> whether it runs at each registered seed.
SELECTION_ARMS = {"VSMT-lean": True, "NoVersion": True, "HeuristicLabel": True, "AssocOnly": True,
                  "TAF": False, "ELU-P": False, "RAC": False, "LOW": False, "HandCost": False}
SELECTION_READING_RULE = (
    "ruling 104-1 1f: per front end and metric one exclusion list over every validation run read (each arm and configuration, "
    "the learned arms and AssocOnly at each seed present): a house is excluded for every run when the metric is undefined in "
    "any applicable run (an arm without RETRACT is not applicable to the false-retract metrics); a run's reading is the mean of "
    "its headline values over the remaining houses; an arm with seeds reads the mean over the seeds present and names a missing "
    "seed; S3-03 writes the readings and the AssocOnly reference, S3-04 chooses with select_configuration"
)


def _run_key(arm: str, index: int, seed: int | None) -> str:
    return f"{arm}|{index}|{'-' if seed is None else seed}"


def selection_readings(runs: Sequence[Mapping[str, Any]], *, mask_source: str,
                       absent_arms: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Ruling 104-1 1f: the validation readings of one front end, and the inputs S3-04's ``select_configuration`` takes.

    ``runs`` lists every validation audit group of that front end as ``{"arm", "config_index", "config", "seed" (None for a rule
    arm), "reports": {episode_id: report}}``; every registered configuration of every arm must be present (an arm with seeds at
    one seed at least), and every run must cover the same episodes.  ``absent_arms`` names an arm with no run at all and why
    (every seed's training diverged, ruling 102-9: a result); it is left out and named, and if it is AssocOnly the reference
    is undefined, which ``select_configuration`` records as constraint_not_satisfiable.
    """

    from vsmt import lean_arms as arms
    from vsmt import lean_evaluation as ev
    from vsmt import lean_teacher as lt

    _require(bool(runs), "selection_readings_need_runs")
    absent = {str(arm): str(why) for arm, why in (absent_arms or {}).items()}
    _require(set(absent) <= set(SELECTION_ARMS), "selection_absent_arm_unknown")
    _require(not any(str(run["arm"]) in absent for run in runs), "selection_absent_arm_has_runs")
    grids = {arm: arms.enumerate_configs(arm, arms.FROZEN_GRIDS[arm]) for arm in SELECTION_ARMS if arm not in absent}
    keys: dict[str, Mapping[str, Any]] = {}
    houses: set[str] | None = None
    for run in runs:
        arm, index, seed = str(run["arm"]), int(run["config_index"]), run.get("seed")
        _require(arm in SELECTION_ARMS, f"selection_arm_unknown:{arm}")
        _require(0 <= index < len(grids[arm]), f"selection_config_index_invalid:{arm}:{index}")
        _require({name: run["config"][name] for name in arms.GRID_PARAMETERS[arm]} == grids[arm][index],
                 f"selection_config_not_the_grid_member:{arm}:{index}")
        _require((seed in arms.SEEDS) if SELECTION_ARMS[arm] else seed is None, f"selection_seed_invalid:{arm}:{seed}")
        key = _run_key(arm, index, seed)
        _require(key not in keys, f"selection_run_duplicated:{key}")
        covered = set(map(str, run["reports"]))
        _require(houses is None or covered == houses, f"selection_runs_cover_different_episodes:{key}")
        houses = covered
        keys[key] = run
    present = {(str(r["arm"]), int(r["config_index"])) for r in runs}
    for arm, configs in grids.items():
        missing = [index for index in range(len(configs)) if (arm, index) not in present]
        _require(not missing, f"selection_runs_incomplete:{arm}:{missing}")
    ordered_houses = sorted(houses or ())
    _require(bool(ordered_houses), "selection_readings_need_episodes")
    without_retract = set(arms.arms_without_atom("RETRACT"))
    metrics: dict[str, Any] = {}
    run_means: dict[str, dict[str, float | None]] = {key: {} for key in keys}
    for metric, field in ev.HEADLINE_FIELD.items():
        not_applicable = sorted(arm for arm in grids if metric in lt.METRIC_NOT_APPLICABLE_RULE and arm in without_retract)
        applicable = [key for key, run in keys.items() if str(run["arm"]) not in not_applicable]
        table = {house: {key: keys[key]["reports"][house][metric][field] for key in applicable} for house in ordered_houses}
        excluded = lt.undefined_houses(table, arms=applicable) if applicable else list(ordered_houses)
        kept = [house for house in ordered_houses if house not in set(excluded)]
        metrics[metric] = {"field": field, "excluded_houses": excluded, "effective_houses": len(kept), "not_applicable_arms": not_applicable}
        for key in keys:
            values = [float(table[house][key]) for house in kept] if key in applicable else []
            run_means[key][metric] = statistics.fmean(values) if values else None
    readings: dict[str, dict[str, Any]] = {}
    for arm, configs in grids.items():
        readings[arm] = {}
        for index, config in enumerate(configs):
            seeds = sorted(int(r["seed"]) for r in runs if str(r["arm"]) == arm and int(r["config_index"]) == index and r.get("seed") is not None)
            per_seed = {str(seed): run_means[_run_key(arm, index, seed)] for seed in seeds}
            if SELECTION_ARMS[arm]:
                mean = {metric: (statistics.fmean([row[metric] for row in per_seed.values()])
                                 if all(row[metric] is not None for row in per_seed.values()) else None)
                        for metric in ev.HEADLINE_FIELD}
            else:
                mean = dict(run_means[_run_key(arm, index, None)])
            readings[arm][str(index)] = {
                "config": config, "seeds_present": seeds,
                "seeds_missing": [seed for seed in arms.SEEDS if seed not in seeds] if SELECTION_ARMS[arm] else [],
                "per_seed": per_seed, "mean": mean,
            }
    reference = (readings[arms.SELECTION_REFERENCE_ARM]["0"] if arms.SELECTION_REFERENCE_ARM in readings
                 else {"seeds_present": [], "seeds_missing": list(arms.SEEDS), "mean": {"missing_residual_rate": None, "node_prf1": None}})
    events = {}
    for metric in ("identity_continuity", "retrieval_success"):  # ruling 102-0 / 102-5: one set of events for every arm
        totals = sorted({sum(int(keys[key]["reports"][house][metric]["events"]) for house in ordered_houses) for key in keys})
        events[metric] = {"events_per_run": totals, "equal_across_runs": len(totals) == 1}
    return {
        "stage": STAGE, "rule": SELECTION_READING_RULE, "mask_source": mask_source, "episodes": ordered_houses,
        "runs": sorted(keys), "metrics": metrics, "readings": readings, "arms_absent": absent,
        "reference": {"arm": arms.SELECTION_REFERENCE_ARM, "config_index": 0, "seeds_present": reference["seeds_present"],
                      "seeds_missing": reference["seeds_missing"],
                      arms.SELECTION_CONSTRAINT_METRIC: reference["mean"]["missing_residual_rate"],
                      arms.SELECTION_METRIC: reference["mean"]["node_prf1"]},
        "selection_inputs": {arm: {index: {arms.SELECTION_METRIC: row["mean"]["node_prf1"],
                                           arms.SELECTION_CONSTRAINT_METRIC: row["mean"]["missing_residual_rate"]}
                                   for index, row in rows.items()} for arm, rows in readings.items()},
        "key_events": {"missing_residual_rate_houses": metrics["missing_residual_rate"]["effective_houses"], **events},
    }


def selection_validation(readings: Mapping[str, Any], arm: str) -> dict[int, dict[str, Any]]:
    """The mapping ``select_configuration`` takes for ``arm`` (configuration index -> its two readings), from ``selection_readings``."""

    return {int(index): dict(values) for index, values in readings["selection_inputs"][arm].items()}


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def manifest_split_refusal(episode_id: str, split: str, manifest: Mapping[str, Any] | None = None) -> str | None:
    """Ruling 104-6: why ``episode_id`` may not be read as an episode of ``split``, or None when it is one."""

    try:
        houses = manifest_houses(load_manifest() if manifest is None else manifest, split)
    except LeanS3_03Error as exc:
        return f"{exc} ({MANIFEST_SPLIT_RULE})"
    if str(episode_id) not in set(houses):
        return f"episode_not_in_the_s3_{split}_manifest:{episode_id} ({MANIFEST_SPLIT_RULE})"
    return None


__all__ = [
    "CHECKPOINT_SPLIT_RULE",
    "COSINE_MIN_LEARNING_RATE",
    "GRADIENT_CLIP_NORM",
    "GROUPED_ARMS_IN_ROUND_1",
    "LABEL_SOURCE",
    "LeanS3_03Error",
    "MANIFEST_PATH",
    "MANIFEST_SPLIT_RULE",
    "RECORD_FILES",
    "ROUNDS",
    "SELECTION_ARMS",
    "SELECTION_HOUSE_COUNT",
    "SELECTION_READING_RULE",
    "STAGE",
    "TRAINED_ARMS",
    "TRAINING_HOUSE_COUNT",
    "checkpoint_split",
    "load_manifest",
    "manifest_houses",
    "manifest_split_refusal",
    "selection_readings",
    "selection_validation",
    "training_settings",
]
