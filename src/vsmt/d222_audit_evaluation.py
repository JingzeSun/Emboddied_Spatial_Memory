"""D-222 one-shot audit of the frozen structural estimator.

E-08 evaluates the E-06 weights on the 128 sealed audit houses.  It computes
only the metrics D-222 froze before any audit observation existed, it refuses to
run against weights whose bytes differ from the ones it is bound to, and it
never refits anything: there is no optimizer in this module.

Intervals are bootstrapped over *houses*, not over frames.  The 32 observations
inside one house are highly correlated, so a frame-level resample would report a
falsely narrow interval.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from .d215_frontend_freeze import STRUCTURAL_LABELS


CONTRACT_SCHEMA = "vsmt-vm04-d222-structural-audit-v1"
REPORT_SCHEMA = "vsmt-vm04-d222-audit-report-v1"
CLOSED_STATUS = "metrics_frozen_audit_closed"
ACTIVE_STATUS = "frozen_executable_audit"
AUTHORIZATION_KEYS = {
    "audit_rgbd_generation", "audit_feature_materialization",
    "audit_evaluation", "estimator_retraining", "production_reader",
    "p04_p08_qualification", "route_or_raw_generation", "private_evaluation",
}


class D222Error(ValueError):
    """A stable D-222 contract or audit failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D222Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_d222_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the audit contract and its one-shot boundary."""

    value = clone_json(dict(contract))
    _require(value.get("schema_version") == CONTRACT_SCHEMA and
             value.get("decision_id") == "D-222",
             "D-222 contract identity changed")
    status = value.get("status")
    _require(status in {CLOSED_STATUS, ACTIVE_STATUS},
             "D-222 contract status is not a registered state")
    authorization = value["authorization"]
    _require(set(authorization) == AUTHORIZATION_KEYS,
             "D-222 authorization has unexpected fields")
    for name in value["run_authorization_policy"]["must_remain_false"]:
        _require(authorization[name] is False,
                 f"D-222 must keep {name} false")
    if status == CLOSED_STATUS:
        _require(not any(authorization.values()),
                 "the closed D-222 contract must keep every audit gate false")

    one_shot = value["one_shot"]
    _require(one_shot["audit_runs_once"] is True and
             one_shot["terminal_receipt_blocks_a_second_run"] is True and
             one_shot["audit_failure_may_add_houses_change_model_or_thresholds"]
             is False and
             one_shot[
                 "audit_may_not_select_a_checkpoint_a_temperature_or_a_threshold"]
             is True,
             "D-222 one-shot boundary changed")

    metrics = value["frozen_metric_definitions"]
    _require(metrics["frozen_before_any_audit_observation_existed"] is True and
             metrics["no_metric_outside_this_list_may_be_computed_or_reported"]
             is True and metrics["calibration_error"]["bins"] == 15,
             "D-222 frozen metric definitions changed")
    bootstrap = metrics["bootstrap"]
    _require(bootstrap["unit"] == "house" and
             type(bootstrap["resamples"]) is int and
             bootstrap["resamples"] > 0 and
             type(bootstrap["seed"]) is int and
             bootstrap["percentiles"] == [2.5, 97.5],
             "D-222 bootstrap definition changed")

    sample = value["audit_sample"]
    _require(sample["human_judgements_required"] == 0 and
             sample["model_inputs"] ==
             "public_rgbd_and_camera_intrinsics_only" and
             sample["reachable_grid_read_at_inference"] is False and
             sample["failure_policy"] ==
             "retain_per_house_failure_without_replacement",
             "D-222 audit sample boundary changed")
    _require(value["frozen_model_binding"][
                 "retraining_or_refitting_during_audit"] is False,
             "D-222 must forbid refitting during the audit")
    return value


def verify_frozen_model(
    contract: Mapping[str, Any], *, weights: Mapping[str, Any],
    normalization: Mapping[str, Any], training_receipt: Mapping[str, Any],
) -> dict[str, str]:
    """Confirm the audit evaluates exactly the E-06 bytes it is bound to."""

    value = validate_d222_contract(contract)
    binding = value["frozen_model_binding"]
    observed = {
        "weights_sha256": weights["weights_sha256"],
        "normalization_receipt_sha256":
            normalization["normalization_receipt_sha256"],
        "training_receipt_sha256":
            training_receipt["training_receipt_sha256"],
    }
    for key, actual in observed.items():
        _require(actual == binding[key],
                 f"D-222 is bound to a different {key}")
    _require(weights["model_id"] == binding["model_id"],
             "D-222 is bound to a different model id")
    _require(weights["semantic_head_present"] is False,
             "D-222 refuses a model that carries a semantic head")
    return observed


def _probabilities(features: np.ndarray, *, weights: np.ndarray,
                   bias: np.ndarray, mean: np.ndarray, std: np.ndarray,
                   temperature: float) -> np.ndarray:
    normalized = (features.astype(np.float64) - mean) / std
    logits = (normalized @ weights.T + bias) / temperature
    logits -= np.max(logits, axis=1, keepdims=True)
    exponential = np.exp(logits)
    return exponential / exponential.sum(axis=1, keepdims=True)


def _point_metrics(probabilities: np.ndarray,
                   labels: np.ndarray) -> dict[str, float]:
    index = np.arange(len(labels))
    truth = np.maximum(probabilities[index, labels], 1e-300)
    predicted = np.argmax(probabilities, axis=1)
    return {
        "structural_nll": float(-np.log(truth).mean()),
        "structural_accuracy": float((predicted == labels).mean()),
    }


def _expected_calibration_error(probabilities: np.ndarray, labels: np.ndarray,
                                bins: int) -> dict[str, Any]:
    confidence = probabilities.max(axis=1)
    correct = (np.argmax(probabilities, axis=1) == labels)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(labels)
    error = 0.0
    table = []
    for index in range(bins):
        low, high = edges[index], edges[index + 1]
        in_bin = ((confidence > low) & (confidence <= high) if index
                  else (confidence >= low) & (confidence <= high))
        count = int(in_bin.sum())
        if count == 0:
            table.append({"bin_low": float(low), "bin_high": float(high),
                          "count": 0, "mean_confidence": None,
                          "accuracy": None})
            continue
        mean_confidence = float(confidence[in_bin].mean())
        accuracy = float(correct[in_bin].mean())
        error += (count / total) * abs(accuracy - mean_confidence)
        table.append({"bin_low": float(low), "bin_high": float(high),
                      "count": count, "mean_confidence": mean_confidence,
                      "accuracy": accuracy})
    return {"calibration_error": float(error), "bin_table": table}


def _house_bootstrap(
    probabilities: np.ndarray, labels: np.ndarray, houses: Sequence[str], *,
    resamples: int, seed: int, percentiles: Sequence[float],
) -> dict[str, Any]:
    """Cluster bootstrap over houses; frames inside a house move together."""

    unique = sorted(set(houses))
    index_by_house = {house: np.flatnonzero(np.asarray(houses) == house)
                      for house in unique}
    generator = np.random.default_rng(seed)
    accuracy_draws = np.empty(resamples, dtype=np.float64)
    nll_draws = np.empty(resamples, dtype=np.float64)
    class_draws = {name: {"recall": [], "precision": [], "mean_nll": []}
                   for name in STRUCTURAL_LABELS}
    for draw in range(resamples):
        picked = generator.integers(0, len(unique), size=len(unique))
        rows = np.concatenate([index_by_house[unique[item]] for item in picked])
        sub_probabilities = probabilities[rows]
        sub_labels = labels[rows]
        point = _point_metrics(sub_probabilities, sub_labels)
        accuracy_draws[draw] = point["structural_accuracy"]
        nll_draws[draw] = point["structural_nll"]
        predicted = np.argmax(sub_probabilities, axis=1)
        truth = np.maximum(
            sub_probabilities[np.arange(len(sub_labels)), sub_labels], 1e-300)
        for class_index, name in enumerate(STRUCTURAL_LABELS):
            actual = sub_labels == class_index
            guessed = predicted == class_index
            class_draws[name]["recall"].append(
                float((predicted[actual] == class_index).mean())
                if actual.any() else math.nan)
            class_draws[name]["precision"].append(
                float((sub_labels[guessed] == class_index).mean())
                if guessed.any() else math.nan)
            class_draws[name]["mean_nll"].append(
                float(-np.log(truth[actual]).mean())
                if actual.any() else math.nan)

    def interval(values: Any) -> list[float] | None:
        array = np.asarray(values, dtype=np.float64)
        array = array[np.isfinite(array)]
        if array.size == 0:
            return None
        return [float(np.percentile(array, item)) for item in percentiles]

    return {
        "houses": len(unique),
        "per_house_interval": {
            "structural_accuracy": interval(accuracy_draws),
            "structural_nll": interval(nll_draws),
        },
        "per_class_interval": {
            name: {statistic: interval(values)
                   for statistic, values in draws.items()}
            for name, draws in class_draws.items()
        },
    }


def evaluate_frozen_estimator(
    *, audit_arrays: Mapping[str, Any], weights: Mapping[str, Any],
    normalization: Mapping[str, Any], training_receipt: Mapping[str, Any],
    d222_contract: Mapping[str, Any], run_commit: str,
) -> dict[str, Any]:
    """Run the one-shot audit and return only the pre-registered metrics."""

    contract = validate_d222_contract(d222_contract)
    bound = verify_frozen_model(
        contract, weights=weights, normalization=normalization,
        training_receipt=training_receipt)
    _require(contract["status"] == ACTIVE_STATUS and
             contract["authorization"]["audit_evaluation"] is True,
             "D-222 audit evaluation is not authorized")

    features = np.asarray(audit_arrays["features"])
    labels = np.asarray(audit_arrays["structural_labels"]).astype(int)
    houses = [str(item) for item in audit_arrays["house_ids"]]
    _require(features.ndim == 2 and features.shape[1] == 396 and
             features.shape[0] == len(labels) == len(houses) and
             np.isfinite(features).all(),
             "D-222 audit arrays are malformed")
    _require(labels.min() >= 0 and labels.max() < 3,
             "D-222 audit labels are out of range")

    probabilities = _probabilities(
        features,
        weights=np.asarray(weights["structural_weights"], dtype=np.float64),
        bias=np.asarray(weights["structural_bias"], dtype=np.float64),
        mean=np.asarray(normalization["mean"], dtype=np.float64),
        std=np.asarray(normalization["population_std_floor_1e_6"],
                       dtype=np.float64),
        temperature=float(weights["structural_temperature"]))

    definitions = contract["frozen_metric_definitions"]
    point = _point_metrics(probabilities, labels)
    calibration = _expected_calibration_error(
        probabilities, labels, definitions["calibration_error"]["bins"])
    bootstrap = definitions["bootstrap"]
    intervals = _house_bootstrap(
        probabilities, labels, houses, resamples=bootstrap["resamples"],
        seed=bootstrap["seed"], percentiles=bootstrap["percentiles"])

    ordered = np.argsort(-probabilities, axis=1)
    ties = int(np.sum(probabilities[np.arange(len(labels)), ordered[:, 0]] ==
                      probabilities[np.arange(len(labels)), ordered[:, 1]]))
    support = {name: int((labels == index).sum())
               for index, name in enumerate(STRUCTURAL_LABELS)}

    report = {
        "schema_version": REPORT_SCHEMA,
        "run_commit": run_commit,
        "frozen_model": bound,
        "observations": int(len(labels)),
        "houses": intervals["houses"],
        "class_support": support,
        "structural_nll": point["structural_nll"],
        "structural_accuracy": point["structural_accuracy"],
        "argmax_tie_count": ties,
        "calibration_error": calibration["calibration_error"],
        "calibration_bin_table": calibration["bin_table"],
        "per_class_interval": intervals["per_class_interval"],
        "per_house_interval": intervals["per_house_interval"],
        "bootstrap": {"unit": "house", "resamples": bootstrap["resamples"],
                      "seed": bootstrap["seed"],
                      "percentiles": list(bootstrap["percentiles"])},
        "metrics_outside_the_frozen_list_computed": False,
        "model_refitted_during_audit": False,
        "audit_used_to_select_anything": False,
        "reachable_grid_read_at_inference": False,
    }
    report["audit_report_sha256"] = _sha(report)
    return report
