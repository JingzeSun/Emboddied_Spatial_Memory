"""Independent R4 v2 labels, task metrics, selection and family statistics.

Standard library only; no file I/O, training, simulation or model imports.
Inputs are values supplied by a separately provenance-checked evaluation caller.
See docs/METHOD.md#r4-comparators. Synthetic checks are not model evidence.
"""
from copy import deepcopy
import math
import random

from .pair_contract import keys, label, number, require, vector
from .two_gate_contract import _sample_valid
from .r4_query_v2 import STEPS, validate_controls, validate_prediction, validate_times


VERSION = "spatial-history-r4-scoring-v2"
LABEL_VERSION = "spatial-history-r4-labels-v2"
CANDIDATES = 9
PIXELS = 80 ** 2
WORLD_IDS = ("LL", "LR", "RL", "RR")
LABEL_KEYS = ("schema_version prediction_times_s object_position_m interval_contact task_success "
              "physics_valid visibility_valid object_visible_pixels")


def _mean(values):
    if not values:
        return None
    value = math.fsum(v / len(values) for v in values)
    number(value, "metric mean")
    return value


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def validate_labels(value):
    keys(value, LABEL_KEYS, "labels")
    require(value["schema_version"] == LABEL_VERSION, "v2 label version required")
    validate_times(value["prediction_times_s"])
    for name in ("physics_valid", "visibility_valid"):
        require(type(value[name]) is bool, f"labels.{name}: boolean required")
    if value["physics_valid"]:
        require(type(value["task_success"]) is bool, "valid physics needs boolean task success")
    else:
        require(value["task_success"] is None, "invalid physics must not use raw success")
    for name in ("object_position_m", "interval_contact", "object_visible_pixels"):
        require(isinstance(value[name], list) and len(value[name]) == STEPS, "label count")
    for point in value["object_position_m"]:
        vector(point, 3, "actual position")
    require(all(type(v) is bool for v in value["interval_contact"]), "boolean contact labels")
    require(all(v is None or type(v) is int and 0 <= v <= PIXELS
                for v in value["object_visible_pixels"]), "visibility counts")


def labels_from_trajectory(samples, assessment):
    """Read all 10001 physical rows, excluding t=0 from future intervals.

    ``assessment`` is exactly the validated three-field audit projection, not
    a raw_task_success fallback. This function does not certify its provenance.
    Full rows use the existing D-071 sample validator; no geometry is inferred.
    """
    keys(assessment, "physics_valid visibility_valid task_success", "assessment")
    require(isinstance(samples, list) and len(samples) == 10001, "complete 20 s trace required")
    contacts = [False] * STEPS
    positions, visible = [], []
    for i, sample in enumerate(samples):
        _sample_valid(sample, i)
        require(sample["object_visible_pixels"] is None or sample["object_visible_pixels"] <= PIXELS,
                "visibility exceeds native v2 pixel count")
        if i == 0:
            continue
        for contact in sample["contacts"]:
            geoms = contact["geoms"]
            positive = contact["distance_m"] <= 0 and contact["normal_force_n"] > 1e-6
            if positive and "object" in geoms and any(g.startswith(("gate_", "side_")) for g in geoms):
                contacts[(i - 1) // 50] = True
        if i % 50 == 0:
            positions.append(deepcopy(sample["object_position_m"]))
            visible.append(sample["object_visible_pixels"])
    result = {"schema_version": LABEL_VERSION, "prediction_times_s": [k / 10 for k in range(1, STEPS + 1)],
              "object_position_m": positions, "object_visible_pixels": visible,
              "interval_contact": contacts, **deepcopy(assessment)}
    validate_labels(result)
    return result


def _runs(flags):
    runs = []
    for i, flag in enumerate(flags):
        if flag:
            if i and flags[i - 1]:
                runs[-1][1] = i
            else:
                runs.append([i, i])
    return runs


def _event_counts(actual, predicted):
    # Earliest compatible ordered interval matching, each run used at most once.
    truth, pred = _runs(actual), _runs(predicted)
    i = j = matched = 0
    while i < len(truth) and j < len(pred):
        if truth[i][1] + 1 < pred[j][0]:
            i += 1
        elif pred[j][1] + 1 < truth[i][0]:
            j += 1
        else:
            matched += 1
            i += 1
            j += 1
    return {"actual_runs": len(truth), "predicted_runs": len(pred), "matched_runs": matched,
            "run_recall": _ratio(matched, len(truth)), "run_precision": _ratio(matched, len(pred))}


def score_prediction(prediction, truth):
    validate_prediction(prediction)
    validate_labels(truth)
    require(truth["physics_valid"] and truth["visibility_valid"], "physics or visibility gate invalid")
    distances = [math.dist(p, y) for p, y in zip(prediction["object_position_m"], truth["object_position_m"])]
    for distance in distances:
        number(distance, "position distance")
    actual = truth["interval_contact"]
    probabilities = prediction["obstacle_contact_probability"]
    predicted = [p >= 0.5 for p in probabilities]
    positives, negatives = sum(actual), STEPS - sum(actual)
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum(not a and p for a, p in zip(actual, predicted))
    actual_first = next((i for i, v in enumerate(actual) if v), None)
    predicted_first = next((i for i, v in enumerate(predicted) if v), None)
    invisible = [d for d, pixels in zip(distances, truth["object_visible_pixels"]) if pixels == 0]
    known_visibility = sum(v is not None for v in truth["object_visible_pixels"])
    first_error = None if actual_first is None or predicted_first is None else abs(actual_first - predicted_first) / 10
    return {
        "position_mean_error_m": _mean(distances), "position_terminal_error_m": distances[-1],
        "position_5s_blocks_mean_error_m": [_mean(distances[k:k+50]) for k in range(0, STEPS, 50)],
        "position_invisible_mean_error_m": _mean(invisible),
        "invisible_endpoint_count": len(invisible), "known_visibility_endpoint_count": known_visibility,
        "contact_brier": _mean([(p - a) ** 2 for p, a in zip(probabilities, actual)]),
        "positive_intervals": positives, "negative_intervals": negatives,
        "true_positive_intervals": tp, "false_positive_intervals": fp,
        "positive_interval_recall": _ratio(tp, positives), "negative_interval_false_positive_rate": _ratio(fp, negatives),
        "actual_any_contact": any(actual), "predicted_any_contact": any(predicted),
        "branch_contact_detection": bool(any(predicted)) if any(actual) else None,
        "branch_contact_false_alarm": bool(any(predicted)) if not any(actual) else None,
        "first_contact_error_s": first_error,
        "first_contact_missed": actual_first is not None and predicted_first is None,
        "first_contact_false_alarm": actual_first is None and predicted_first is not None,
        "contact_events": _event_counts(actual, predicted),
        "success_brier": (prediction["task_success_probability"] - truth["task_success"]) ** 2,
        "success_correct": (prediction["task_success_probability"] >= 0.5) == truth["task_success"],
    }


def select_candidates(predictions):
    require(isinstance(predictions, list) and len(predictions) == CANDIDATES, "nine registered candidates required")
    for pred in predictions:
        validate_prediction(pred)
    probabilities = [p["task_success_probability"] for p in predictions]
    best = max(probabilities)
    tied = [i for i, value in enumerate(probabilities) if value == best]
    return [1 / len(tied) if i in tied else 0.0 for i in range(CANDIDATES)]


def score_world(predictions, labels):
    """Nine fixed slots; None/malformed rows remain failures in the denominator."""
    require(isinstance(predictions, list) and len(predictions) == CANDIDATES, "nine prediction slots required")
    require(isinstance(labels, list) and len(labels) == CANDIDATES, "nine label slots required")
    errors, scores, pred_ok, truth_ok = [], [], [], []
    for i, (pred, truth) in enumerate(zip(predictions, labels)):
        try:
            validate_prediction(pred)
            pred_ok.append(True)
        except (ValueError, OverflowError) as error:
            pred_ok.append(False)
            errors.append({"candidate": i, "source": "prediction", "reason": str(error)})
        try:
            validate_labels(truth)
            require(truth["physics_valid"] and truth["visibility_valid"], "physics or visibility invalid")
            truth_ok.append(True)
        except (ValueError, OverflowError) as error:
            truth_ok.append(False)
            errors.append({"candidate": i, "source": "truth", "reason": str(error)})
        score = None
        if pred_ok[-1] and truth_ok[-1]:
            try:
                score = score_prediction(pred, truth)
            except (ValueError, OverflowError) as error:
                pred_ok[-1] = False
                errors.append({"candidate": i, "source": "metric", "reason": str(error)})
        scores.append(score)
    selection = select_candidates(predictions) if all(pred_ok) else None
    valid = all(pred_ok) and all(truth_ok)
    costs = [1 - int(y["task_success"]) for y in labels] if all(truth_ok) else None
    cost = math.fsum(p * c for p, c in zip(selection, costs)) if valid else None
    # These are conservative diagnostic completion bounds, not repaired labels.
    bounds = [cost, cost] if valid else [min(costs), max(costs)] if costs is not None else [0.0, 1.0]
    return {"schema_version": VERSION, "valid": valid, "registered_candidates": CANDIDATES,
            "valid_prediction_candidates": sum(pred_ok), "valid_truth_candidates": sum(truth_ok),
            "selection_probabilities": selection, "expected_actual_cost": cost,
            "expected_actual_cost_bounds": bounds,
            "expected_success": 1 - cost if valid else None,
            "selection_regret": cost - min(costs) if valid else None,
            "candidate_scores": scores, "errors": errors}


def paired_effects(left_pred, left_truth, right_pred, right_truth, *, left_controls, right_controls):
    """Same-control effect error; layout pairing itself belongs to private audit."""
    validate_controls(left_controls)
    validate_controls(right_controls)
    require(left_controls == right_controls, "paired controls differ")
    score_prediction(left_pred, left_truth)
    score_prediction(right_pred, right_truth)
    pred_diff = [[b - a for a, b in zip(pa, pb)] for pa, pb in
                 zip(left_pred["object_position_m"], right_pred["object_position_m"])]
    actual_diff = [[b - a for a, b in zip(pa, pb)] for pa, pb in
                   zip(left_truth["object_position_m"], right_truth["object_position_m"])]
    distances = [math.dist(p, y) for p, y in zip(pred_diff, actual_diff)]
    for distance in distances:
        number(distance, "paired distance")
    return {"direction": "right_minus_left", "pair_position_error_m": _mean(distances),
            "predicted_position_difference_m": pred_diff, "actual_position_difference_m": actual_diff,
            "predicted_contact_difference": [b - a for a, b in zip(left_pred["obstacle_contact_probability"], right_pred["obstacle_contact_probability"])],
            "actual_contact_difference": [int(b) - int(a) for a, b in zip(left_truth["interval_contact"], right_truth["interval_contact"])],
            "predicted_success_difference": right_pred["task_success_probability"] - left_pred["task_success_probability"],
            "actual_success_difference": int(right_truth["task_success"]) - int(left_truth["task_success"])}


def _registry(registry):
    keys(registry, "families model_seeds", "registry")
    families, models = registry["families"], registry["model_seeds"]
    require(isinstance(families, list) and families, "nonempty family registration")
    for family in families:
        label(family, "family")
    require(len(families) == len(set(families)), "duplicate family")
    require(isinstance(models, dict) and models and set(models) <= set("LRMDFP"), "model registration")
    for seeds in models.values():
        require(isinstance(seeds, list) and seeds
                and all(type(s) is int and s >= 0 for s in seeds), "seeds")
        require(len(seeds) == len(set(seeds)), "duplicate seed")
    return families, models


def _bootstrap(values):
    rng = random.Random(7901)
    n = len(values)
    draws = sorted(_mean([values[rng.randrange(n)] for _ in range(n)]) for _ in range(10000))
    # Linear percentile interpolation, explicitly registered for R4-1.
    def percentile(q):
        x = (len(draws) - 1) * q
        lo = int(x)
        hi = min(lo + 1, len(draws) - 1)
        return draws[lo] + (draws[hi] - draws[lo]) * (x - lo)
    return [percentile(0.025), percentile(0.975)]


def summarize_registered(rows, registry):
    """Compute from raw candidate values, never trust prefilled metric rows.

    Registry must be fixed before reading outcomes. Missing rows are explicit;
    seed, world and candidate repetitions never enlarge the family denominator.
    CI unavailable if ANY registered family lacks either method's full result.
    """
    families, models = _registry(registry)
    require(isinstance(rows, list), "evaluation rows")
    indexed, shared_truth = {}, {}
    for row in rows:
        keys(row, "family_id model_id seed world_id predictions labels", "evaluation row")
        require(type(row["family_id"]) is str and row["family_id"] in families, "unregistered family")
        require(type(row["model_id"]) is str and row["model_id"] in models, "unregistered model")
        require(type(row["seed"]) is int and row["seed"] in models[row["model_id"]], "unregistered seed")
        require(type(row["world_id"]) is str and row["world_id"] in WORLD_IDS, "unregistered world")
        key = (row["family_id"], row["model_id"], row["seed"], row["world_id"])
        require(key not in indexed, "duplicate world row, not another independent sample")
        truth_key = (row["family_id"], row["world_id"])
        if truth_key in shared_truth:
            require(row["labels"] == shared_truth[truth_key], "truth changed across models or seeds")
        else:
            shared_truth[truth_key] = row["labels"]
        indexed[key] = score_world(row["predictions"], row["labels"])
    summaries, world_rows, family_regrets = {}, [], {}
    missing_score = score_world([None] * CANDIDATES, [None] * CANDIDATES)
    for model, seeds in models.items():
        family_values, lower, upper, valid_worlds = [], [], [], 0
        for family in families:
            seed_regrets = []
            for seed in seeds:
                scores = []
                for world in WORLD_IDS:
                    key = (family, model, seed, world)
                    score = indexed.get(key, missing_score)
                    scores.append(score)
                    valid_worlds += int(score["valid"])
                    lower.append(score["expected_actual_cost_bounds"][0])
                    upper.append(score["expected_actual_cost_bounds"][1])
                    world_rows.append({"family_id": family, "model_id": model, "seed": seed,
                                       "world_id": world, "missing_registered_row": key not in indexed,
                                       "score": deepcopy(score)})
                seed_regrets.append(_mean([s["selection_regret"] for s in scores])
                                    if all(s["valid"] for s in scores) else None)
            value = _mean(seed_regrets) if all(v is not None for v in seed_regrets) else None
            family_values.append(value)
        valid_values = [v for v in family_values if v is not None]
        registered_worlds = len(families) * len(seeds) * 4
        summaries[model] = {
            "registered_families": len(families), "complete_families": len(valid_values),
            "registered_world_seed_rows": registered_worlds, "valid_world_seed_rows": valid_worlds,
            "valid_world_coverage": valid_worlds / registered_worlds,
            "family_regrets": dict(zip(families, family_values)),
            "mean_regret": _mean(family_values) if len(valid_values) == len(families) else None,
            "conditional_complete_family_mean_regret": _mean(valid_values),
            "full_registered_expected_cost_bounds": [_mean(lower), _mean(upper)],
        }
        family_regrets[model] = family_values
    comparisons = []
    ordered = sorted(models)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            pairs = list(zip(family_regrets[a], family_regrets[b]))
            diffs = [x - y for x, y in pairs if x is not None and y is not None]
            complete = len(diffs) == len(families)
            comparisons.append({"left": a, "right": b, "direction": "left_minus_right",
                                "paired_families": len(diffs), "registered_families": len(families),
                                "mean_regret_difference": _mean(diffs) if complete else None,
                                "descriptive_95_percentile_interval": _bootstrap(diffs) if complete else None,
                                "reason": None if complete else "incomplete_registered_families"})
    return {"schema_version": VERSION, "models": summaries, "world_rows": world_rows,
            "comparisons": comparisons, "bootstrap_unit": "family_after_seed_and_world_mean",
            "bootstrap_samples": 10000, "bootstrap_seed": 7901, "population_claim_verified": False}
