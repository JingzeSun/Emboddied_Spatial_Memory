"""S1-05: apply the frozen ruling-47 selection rule to the S1-04 report and write the S1 close-out receipt.

Usage (local; reads only committed ``results/`` reports and ``configs/`` contracts, no server, no cache):
    python ops/vsmt/lean_s1_05_select_descriptor.py \\
        --s1-04-report results/vsmt_lean_s1_04_diagnostics_154776d.json \\
        --out results/vsmt_lean_s1_05_descriptor_freeze_154776d.json

What it does, in order:
  1. validates the live S0-03 contract with its own validator and reads the ledgered selection threshold,
     the registered 30/12 hold-out sizes and the S1-02a split seed;
  2. reads the S1-04 diagnostics report and refuses anything but a completed ``s1-04-diagnostics`` stage
     whose ReID block computed the selection rule; re-derives the ruling-47 hold-out from the cache episode
     seals the report pins (S0-02 split rank, first 30 train, next 12 select) and refuses if the report's
     hold-out differs, if the two groups overlap, or if a house was scored outside its group;
  3. recomputes the selection from the selection-house medians in the report through
     ``lean_reid_head.select_descriptor`` and refuses if the report's own ``selection_rule`` block says
     anything else -- a stored verdict is never trusted on its own;
  4. writes the freeze receipt: the chosen descriptor, its source set and weights digest, the frozen
     descriptor baseline the paper must report alongside, every candidate's selection-house numbers,
     the recall miss at the frozen recall values, the training-house medians as an annotation only, the
     recorded selection shortfall, and an S1 close-out block pinning the S1-02/S1-03/S1-04 reports, the
     ruling-56 gate re-check and the values S2 inherits frozen or still null.

What it is not: it trains nothing, reads no cache frame and no private file, changes no contract (the
contract edit that records the choice is a separate reviewed commit), and never selects on training houses.

白话：S1-05 回答"五个臂以后读哪一套描述子"。输入是 S1-04 已经算好的诊断报告（选择 house 上两套冻结
描述子与两个投影的跨视角分离度中位数）和 S0-03 合同里冻结的规则（投影要比最好的冻结描述子高 0.05 才
入选）；输出是一份冻结回执：选了谁、它的权重摘要、论文要并列报告的冻结基线、每个候选的数字，以及 S1
三步的收口清单。例如 ViT-B/14 投影后中位分离度 0.236，冻结 ViT-B/14 是 0.143，差 0.093 ≥ 0.05，所以
选投影、并列报告冻结 ViT-B/14。它不是重新算分离度，也不训练；它只把已冻结的规则套到已有的数字上，
并把报告里的结论重算一遍核对。选择组只有 9 条 house 而不是 12 条（cache 只有 39 条），按合同"跳过并计
数、不顶替"照做，回执把缺口写明。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_reid_head as rh  # noqa: E402

SCHEMA_VERSION = "vsmt-lean-s1-05-descriptor-freeze-v1"
STAGE = "S1-05"
CONFIG_DIR = ROOT / "configs" / "vsmt"
S0_03_CONTRACT = CONFIG_DIR / "lean_s0_assignment_v2.json"
S1_02A_CONTRACT = CONFIG_DIR / "lean_s1_02a_pilot_v2.json"
S1_03_CONTRACT = CONFIG_DIR / "lean_s1_03_frontend_cache_v1.json"
S1_04_CONTRACT = CONFIG_DIR / "lean_s1_04_frontend_diagnostics_v1.json"
#: Live contracts whose still-null registered values S2 inherits; read, not restated.
LIVE_CONTRACTS_WITH_OPEN_VALUES = {
    "S0-01": "lean_s0_entity_memory_v2.json",
    "S0-02": "lean_s0_intervention_data_v3.json",
    "S0-03": "lean_s0_assignment_v2.json",
    "S0-04": "lean_s0_teacher_metrics_v2.json",
    "S0-05": "lean_s0_arms_v2.json",
    "S1-03": "lean_s1_03_frontend_cache_v1.json",
    "S1-04": "lean_s1_04_frontend_diagnostics_v1.json",
}
S1_04_STAGE_NAME = "s1-04-diagnostics"
PROJECTION_PREFIX = "reid_projection:"
DEFAULT_S1_02A_REPORT = "results/vsmt_lean_s1_02a_report_5f9aa71.json"
DEFAULT_S1_02B_REPORT = "results/vsmt_lean_s1_02b_report_5f9aa71.json"
DEFAULT_S1_03_REPORT = "results/vsmt_lean_s1_03_report_154776d.json"
DEFAULT_RULING_56_ESTIMATE = "results/vsmt_ruling56_matching_estimate_154776d.json"
#: The S1-04 IoU gate (contract ``fragment_truth_iou.gate_median_iou``) and where the ruling-56 (a)
#: estimate keeps the median that re-checks it under the ruled matching rule (LOG-244 sequel two).
RULING_56_RECHECK_PATH = ("estimate", "non_architectural", "fragment_rows", "frame_union", "median")


class S105Refused(ValueError):
    """Raised with a short machine-readable code; nothing is written when it fires."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S105Refused(code)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*arguments: str) -> str:
    try:
        return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


# --------------------------------------------------------------------------
# pure checks over the S1-04 report (tested on synthetic reports)
# --------------------------------------------------------------------------

def check_report_shape(report: Mapping[str, Any]) -> None:
    """The report must be a completed S1-04 diagnostics stage receipt whose ReID block ran."""

    _require(report.get("stage") == S1_04_STAGE_NAME, "report_is_not_an_s1_04_diagnostics_receipt")
    _require(report.get("episodes_run") == report.get("episodes_planned") and report.get("episodes_failed") == [],
             "report_stage_incomplete_or_episodes_failed")
    _require(isinstance(report.get("cache_episode_seals"), dict) and report["cache_episode_seals"], "report_pins_no_cache_episode_seals")
    _require(set(report["cache_episode_seals"]) == set(report.get("per_house", {})), "report_per_house_differs_from_cache_seals")
    reid = report.get("reid")
    _require(isinstance(reid, dict) and isinstance(reid.get("selection_rule"), dict), "report_has_no_reid_block")
    _require(reid["selection_rule"].get("status") == "computed", "report_selection_rule_not_computed")


def recompute_holdout(report: Mapping[str, Any], *, seed: int) -> dict[str, Any]:
    """Re-derive the ruling-47 hold-out from the cache membership the report pins."""

    return rh.holdout_split(sorted(report["cache_episode_seals"]), seed=seed)


def check_holdout(report: Mapping[str, Any], *, seed: int, contract: Mapping[str, Any]) -> dict[str, Any]:
    """The report's hold-out must equal the recomputation and the groups must not overlap or leak."""

    stored = report["reid"]["holdout"]
    fresh = recompute_holdout(report, seed=seed)
    _require(stored.get("order") == "s0_02_house_split_rank" and stored.get("seed") == seed, "holdout_order_or_seed_differs")
    for key in ("training_houses", "selection_houses", "training_shortfall", "selection_shortfall"):
        _require(stored.get(key) == fresh[key], f"holdout_{key}_differs_from_recomputation")
    training, selection = set(stored["training_houses"]), set(stored["selection_houses"])
    _require(not training & selection, "holdout_groups_overlap")
    _require(set(stored["training_houses_used"]) <= training, "holdout_training_house_used_outside_its_group")
    _require(set(stored["selection_houses_used"]) <= selection, "holdout_selection_house_used_outside_its_group")
    _require(not set(stored["training_houses_used"]) & set(stored["selection_houses_used"]), "holdout_used_groups_overlap")
    _require(stored.get("houses_beyond_the_holdout") == [], "holdout_houses_beyond_the_holdout")
    registered = contract["reid_adapter_head"]["holdout"]
    _require(len(stored["training_houses"]) + stored["training_shortfall"] == registered["training_houses"],
             "holdout_training_count_plus_shortfall_differs_from_contract")
    _require(len(stored["selection_houses"]) + stored["selection_shortfall"] == registered["selection_houses"],
             "holdout_selection_count_plus_shortfall_differs_from_contract")
    _require(stored["selection_houses_used"], "holdout_no_selection_house_scored")
    return {
        "membership_rule": stored.get("membership_rule"),
        "order": stored["order"],
        "seed": seed,
        "training_houses": list(stored["training_houses"]),
        "selection_houses": list(stored["selection_houses"]),
        "training_houses_used": list(stored["training_houses_used"]),
        "selection_houses_used": list(stored["selection_houses_used"]),
        "training_houses_failed_diagnostics": list(stored.get("training_houses_failed_diagnostics", [])),
        "selection_houses_failed_diagnostics": list(stored.get("selection_houses_failed_diagnostics", [])),
        "registered_training_houses": registered["training_houses"],
        "registered_selection_houses": registered["selection_houses"],
        "training_shortfall": stored["training_shortfall"],
        "selection_shortfall": stored["selection_shortfall"],
        "recomputed_from_cache_episode_seals_and_agrees_with_the_report": True,
    }


def candidate_medians(report: Mapping[str, Any]) -> dict[str, float]:
    """Selection-house median separation per candidate: both frozen sets, plus every projection that trained."""

    by_set = report["reid"]["by_set"]
    medians: dict[str, float] = {}
    for name in rh.FROZEN_SETS:
        entry = by_set.get(name)
        _require(isinstance(entry, dict), f"report_missing_frozen_set:{name}")
        _require(entry.get("selection_houses_used", 0) > 0, f"report_frozen_set_not_scored_on_selection_houses:{name}")
        medians[name] = float(entry["selection_houses_separation_frozen"]["median"])
        if entry.get("status") == "succeeded" and entry.get("diverged") is False and entry.get("weights_written") is True:
            _require(isinstance(entry.get("weights_sha256"), str) and len(entry["weights_sha256"]) == 64,
                     f"report_projection_without_weights_digest:{name}")
            medians[f"{PROJECTION_PREFIX}{name}"] = float(entry["selection_houses_separation_projection"]["median"])
    return medians


def apply_rule(report: Mapping[str, Any], *, threshold: float) -> dict[str, Any]:
    """Recompute the ruling-47 selection and refuse if the report's stored verdict differs."""

    medians = candidate_medians(report)
    fresh = rh.select_descriptor(medians, threshold=threshold)
    stored = report["reid"]["selection_rule"]
    _require(stored.get("threshold") == threshold, "report_threshold_differs_from_contract")
    for key in ("chosen", "best_frozen"):
        _require(stored.get(key) == fresh[key], f"report_selection_rule_{key}_differs_from_recomputation")
    _require(abs(float(stored["best_frozen_median_separation"]) - fresh["best_frozen_median_separation"]) < 1e-12,
             "report_best_frozen_median_differs_from_recomputation")
    stored_gain, fresh_gain = stored.get("projection_gain_over_best_frozen"), fresh["projection_gain_over_best_frozen"]
    _require((stored_gain is None) == (fresh_gain is None) and (fresh_gain is None or abs(float(stored_gain) - fresh_gain) < 1e-12),
             "report_projection_gain_differs_from_recomputation")
    excluded = sorted(report["reid"].get("failed_sets", []))
    _require(sorted(stored.get("projections_excluded_after_divergence", [])) == excluded, "report_excluded_projections_differ")
    for name in excluded:
        _require(f"{PROJECTION_PREFIX}{name}" not in medians, f"diverged_projection_entered_the_rule:{name}")
    return {**fresh, "candidate_medians_on_selection_houses": medians,
            "projections_excluded_after_divergence": excluded, "matches_the_report_block": True}


def recall_at_frozen_values(curve: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The grid point of a recall curve at the ruling-57 values (k=5, k'=3, 3 m); None if absent."""

    if not curve:
        return None
    for point in curve["grid_points"]:
        if (point["local_count"], point["global_count"], point["local_radius_m"]) == (
                la.RECALL_LOCAL_COUNT, la.RECALL_GLOBAL_COUNT, la.RECALL_LOCAL_RADIUS_M):
            return dict(point)
    return None


def candidates_table(report: Mapping[str, Any]) -> dict[str, Any]:
    """Every candidate's selection-house numbers, as the report carries them (nothing re-measured)."""

    by_set = report["reid"]["by_set"]
    table: dict[str, Any] = {}
    for name in rh.FROZEN_SETS:
        entry = by_set[name]
        table[name] = {
            "kind": "frozen_descriptor",
            "separation_on_selection_houses": dict(entry["selection_houses_separation_frozen"]),
            "recall_miss_at_frozen_recall_values_on_selection_houses": recall_at_frozen_values(entry.get("selection_houses_recall_curve_frozen")),
        }
        projection = f"{PROJECTION_PREFIX}{name}"
        if entry.get("status") == "succeeded":
            table[projection] = {
                "kind": "shared_reid_projection",
                "source_set": name,
                "weights_file": entry.get("weights_file"),
                "weights_sha256": entry.get("weights_sha256"),
                "training": {
                    "training_houses_used": entry.get("training_houses_used"),
                    "training_fragments": entry.get("training_fragments"),
                    "training_classes": entry.get("training_classes"),
                    "classes_with_positives": entry.get("classes_with_positives"),
                    "epochs_run": len(entry.get("loss_curve") or []),
                    "final_loss": (entry.get("loss_curve") or [None])[-1],
                    "diverged": entry.get("diverged"),
                },
                "separation_on_selection_houses": dict(entry["selection_houses_separation_projection"]),
                "recall_miss_at_frozen_recall_values_on_selection_houses": recall_at_frozen_values(entry.get("selection_houses_recall_curve_projection")),
            }
        else:
            table[projection] = {"kind": "shared_reid_projection", "source_set": name, "status": entry.get("status"),
                                 "reason": entry.get("reason"), "excluded_from_the_rule": True}
    return table


def training_houses_annotation(report: Mapping[str, Any], holdout: Mapping[str, Any]) -> dict[str, Any]:
    """Frozen-set separation medians on the training houses: an annotation, never a basis (PLAN S1-05)."""

    per_house = report["per_house"]
    rows = {house: dict(per_house[house]["separation_median"]) for house in holdout["training_houses_used"] if house in per_house}
    return {
        "note": "training-house separation of the frozen sets is reported for context only; the rule reads the selection houses only",
        "frozen_set_separation_median_by_training_house": rows,
        "projection_was_not_scored_on_training_houses": True,
    }


def frozen_block(selection: Mapping[str, Any], report: Mapping[str, Any], contract: Mapping[str, Any],
                 s1_03_contract: Mapping[str, Any]) -> dict[str, Any]:
    """What S1-05 freezes for every later stage, in one place."""

    chosen = selection["chosen"]
    sets = s1_03_contract["descriptor_sets"]
    dimensions = {sets["primary"]["name"]: sets["primary"]["dimension"], sets["optional_upgrade"]["name"]: sets["optional_upgrade"]["dimension"]}
    if chosen.startswith(PROJECTION_PREFIX):
        source = chosen[len(PROJECTION_PREFIX):]
        entry = report["reid"]["by_set"][source]
        weights = {"weights_file": entry["weights_file"], "weights_sha256": entry["weights_sha256"],
                   "weights_location": "the S1-04 diagnostics private output root on the server; weights are not committed, the digest is",
                   "output_dimension": contract["reid_adapter_head"]["output_dimension"]}
        baseline = selection["best_frozen"]
    else:
        source, weights, baseline = chosen, None, None
    kept = {chosen, source} | ({baseline} if baseline else set())
    unselected = sorted(name for name in selection["candidate_medians_on_selection_houses"] if name not in kept)
    return {
        "selected_descriptor": chosen,
        "source_descriptor_set": source,
        "source_dimension": dimensions[source],
        "projection": weights,
        "frozen_descriptor_baseline": baseline,
        "frozen_descriptor_baseline_must_be_reported_alongside": bool(selection["frozen_descriptor_baseline_must_be_reported"]),
        "source_set_stays_readable_as_the_projection_input_and_the_baseline": source,
        "unselected_dropped_from_the_assignment_view": unselected,
        "cache_bytes_unchanged_the_episode_seals_still_cover_both_sets": True,
        "no_further_descriptor_change": True,
    }


def open_values_entering_s2() -> dict[str, list[str]]:
    """Registered values still null in the live contracts, read from the contracts themselves."""

    out: dict[str, list[str]] = {}
    for stage, name in LIVE_CONTRACTS_WITH_OPEN_VALUES.items():
        contract = load_json(CONFIG_DIR / name)
        slots = list(contract.get("policy_values_without_defaults", []))
        if slots:
            out[stage] = slots
    return out


def _dig(tree: Any, path: tuple[str, ...]) -> Any:
    for part in path:
        tree = tree[part]
    return tree


def s1_closeout(*, s1_02_reports: list[Path], s1_03_report: Path, s1_04_report: Path, s1_04_sha256: str,
                report: Mapping[str, Any], ruling_56_estimate: Path, s1_04_contract: Mapping[str, Any],
                contract: Mapping[str, Any]) -> dict[str, Any]:
    """Pin the S1 products S2 stands on; every number is copied from a committed report, none is recomputed."""

    s1_02_rows = []
    for path in s1_02_reports:
        data = load_json(path)
        s1_02_rows.append({
            "report": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_of(path),
            "stage": data.get("stage"), "generator_code": data.get("reviewed_code"),
            "houses_planned": data.get("houses_planned"),
            "succeeded": len(data["succeeded"]) if isinstance(data.get("succeeded"), list) else data.get("succeeded"),
            "failed": len(data["failed"]) if isinstance(data.get("failed"), list) else data.get("failed"),
            "null_window_episodes": len(data["null_window_episodes"]) if isinstance(data.get("null_window_episodes"), list) else data.get("null_window_episodes"),
            "yield_house_level_non_null": data.get("yield_house_level_non_null"),
            "yield_gate": data.get("yield_gate"), "yield_gate_passed": data.get("yield_gate_passed"),
        })
    s1_03 = load_json(s1_03_report)
    stage = s1_03["stage"]
    estimate = load_json(ruling_56_estimate)
    gate = s1_04_contract["fragment_truth_iou"]["gate_median_iou"]
    iou = report["fragment_truth_iou"]
    recheck = float(_dig(estimate, RULING_56_RECHECK_PATH))
    head = contract["reid_adapter_head"]
    recall = contract["recall_rule"]
    return {
        "s1_02": {"reports": s1_02_rows,
                  "note": "the S1-02 data at 5f9aa71: 39 succeeded of 50 (29 with interventions, 10 null-window), rulings 53/54/55"},
        "s1_03": {"report": str(s1_03_report.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_of(s1_03_report),
                  "code_commit": stage.get("code_commit"), "episodes_planned": stage.get("episodes_planned"),
                  "episodes_succeeded": stage.get("episodes_succeeded"), "episodes_failed": stage.get("episodes_failed"),
                  "frames_total": stage.get("frames_total"), "fragments_total": stage.get("fragments_total"),
                  "complete": stage.get("complete"), "cache_episode_seals_pinned_by_s1_04": len(report["cache_episode_seals"])},
        "s1_04": {"report": str(s1_04_report.relative_to(ROOT)).replace("\\", "/"), "sha256": s1_04_sha256,
                  "code_commit": report.get("code_commit"), "episodes_used": report.get("episodes_used"),
                  "fragments_labelled": report.get("fragments_labelled"), "fragments_unlabelled": report.get("fragments_unlabelled"),
                  "separation_median_by_set_all_development_houses": {name: report["separation_by_set"][name]["median"] for name in rh.FROZEN_SETS},
                  "fragment_truth_iou_single_view_median": iou["truth"]["median"], "gate_median_iou": gate,
                  "gate_fired": bool(iou["median_below_gate"])},
        "s1_04_iou_gate_recheck_under_the_ruled_matching_rule": {
            "ruling": "D-224-S1 ruling 56 continued (2026-09-24): truth node scope excludes door/room/wall/window; the entity box is the same-frame union",
            "estimate_report": str(ruling_56_estimate.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_of(ruling_56_estimate),
            "value_path": ".".join(RULING_56_RECHECK_PATH), "median_iou": recheck, "gate_median_iou": gate,
            "passes": recheck >= gate, "s1_not_redone": True},
        "frozen_values_entering_s2": {
            "S0-03.recall_rule": {name: recall[name] for name in ("local_count", "global_count", "local_radius_m", "birth_neighbourhood_radius_m")},
            "S0-03.reid_adapter_head": {name: head[name] for name in ("output_dimension", "selection_rule_threshold")},
            "S1-04.reid_training": {name: s1_04_contract["reid_training"][name] for name in ("temperature", "epochs", "batch_fragments", "learning_rate", "seed")},
        },
        "null_values_entering_s2": open_values_entering_s2(),
        "null_values_notes": {
            "S0-02": "split_rule slots stay null by design: seed, validation and test sizes are registered once in S1-02a (ruling X6), train_houses at S3-01",
            "S1-03": "supported_by thresholds stay null by ruling 42: no S0-03 feature reads supported_by",
            "others": "to be frozen by ruling before S2-05 runs; S2 code takes them as configuration inputs without defaults",
        },
    }


def build_receipt(report: Mapping[str, Any], *, report_path: Path, report_sha256: str, contract: Mapping[str, Any],
                  s1_03_contract: Mapping[str, Any], seed: int, closeout: Mapping[str, Any] | None,
                  written_at_utc: str, checkout: Mapping[str, Any]) -> dict[str, Any]:
    check_report_shape(report)
    head = contract["reid_adapter_head"]
    threshold = float(head["selection_rule_threshold"])
    holdout = check_holdout(report, seed=seed, contract=contract)
    selection = apply_rule(report, threshold=threshold)
    frozen = frozen_block(selection, report, contract, s1_03_contract)
    gain = selection["projection_gain_over_best_frozen"]
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE,
        "decision_ids": ["D-224-E", "D-224-S1 ruling 47"],
        "written_at_utc": written_at_utc,
        "checkout": dict(checkout),
        "rule": {
            "contract": str(S0_03_CONTRACT.relative_to(ROOT)).replace("\\", "/"),
            "selection_rule": head["selection_rule"],
            "selection_rule_threshold": threshold,
            "selection_rule_threshold_semantics": head["selection_rule_threshold_semantics"],
            "selection_houses_only": True,
            "training_house_separation_is_an_annotation_not_a_basis": True,
            "rule_frozen_by": head.get("values_frozen_by"),
        },
        "input": {
            "s1_04_report": str(report_path.relative_to(ROOT)).replace("\\", "/"),
            "s1_04_report_sha256": report_sha256,
            "s1_04_code_commit": report.get("code_commit"),
            "episodes_used": report.get("episodes_used"),
            "cache_episode_seals_count": len(report["cache_episode_seals"]),
            "cache_episode_seals_sha256": hashlib.sha256(canonical_json(dict(report["cache_episode_seals"])).encode("utf-8")).hexdigest(),
        },
        "holdout": holdout,
        "candidates_on_selection_houses": candidates_table(report),
        "selection": selection,
        "frozen": frozen,
        "training_houses_annotation": training_houses_annotation(report, holdout),
        "selection_shortfall": {
            "registered_selection_houses": holdout["registered_selection_houses"],
            "selection_houses_used": len(holdout["selection_houses_used"]),
            "shortfall": holdout["selection_shortfall"],
            "cause": "the cached development block has fewer episodes than the 30 + 12 the hold-out registers",
            "rule_clause_applied": "holdout.a_house_without_a_cache_is_skipped_and_counted_never_replaced",
            "margin_over_threshold": None if gain is None else gain - threshold,
            "flagged_for_the_user": holdout["selection_shortfall"] > 0,
        },
        "s1_closeout": dict(closeout) if closeout is not None else None,
        "private_ids_exported": False,
        "contains_frames_descriptors_or_masks": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--s1-04-report", required=True)
    parser.add_argument("--s1-02a-report", default=DEFAULT_S1_02A_REPORT)
    parser.add_argument("--s1-02b-report", default=DEFAULT_S1_02B_REPORT)
    parser.add_argument("--s1-03-report", default=DEFAULT_S1_03_REPORT)
    parser.add_argument("--ruling-56-estimate", default=DEFAULT_RULING_56_ESTIMATE)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    contract = la.validate_assignment_contract(load_json(S0_03_CONTRACT))
    s1_03_contract = load_json(S1_03_CONTRACT)
    s1_04_contract = load_json(S1_04_CONTRACT)
    seed = int(load_json(S1_02A_CONTRACT)["split_freeze"]["seed"])
    report_path = (ROOT / args.s1_04_report).resolve()
    report = load_json(report_path)
    report_sha256 = sha256_of(report_path)
    checkout = {"commit": _git("rev-parse", "HEAD") or None, "clean": (_git("status", "--porcelain") == "") if _git("rev-parse", "HEAD") else None}
    try:
        closeout = s1_closeout(
            s1_02_reports=[(ROOT / args.s1_02a_report).resolve(), (ROOT / args.s1_02b_report).resolve()],
            s1_03_report=(ROOT / args.s1_03_report).resolve(), s1_04_report=report_path, s1_04_sha256=report_sha256,
            report=report, ruling_56_estimate=(ROOT / args.ruling_56_estimate).resolve(),
            s1_04_contract=s1_04_contract, contract=contract)
        receipt = build_receipt(report, report_path=report_path, report_sha256=report_sha256, contract=contract,
                                s1_03_contract=s1_03_contract, seed=seed, closeout=closeout,
                                written_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), checkout=checkout)
    except S105Refused as refused:
        print(f"[s1-05] refused: {refused}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:  # LF on every platform: the digest must not depend on the OS
        handle.write(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    frozen, shortfall = receipt["frozen"], receipt["selection_shortfall"]
    print(f"[s1-05] {out} selected {frozen['selected_descriptor']} (source {frozen['source_descriptor_set']}, "
          f"baseline {frozen['frozen_descriptor_baseline']}) gain {receipt['selection']['projection_gain_over_best_frozen']:.4f} "
          f"over {receipt['rule']['selection_rule_threshold']} on {shortfall['selection_houses_used']} selection houses "
          f"(shortfall {shortfall['shortfall']}); sha256 {sha256_of(out)[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
