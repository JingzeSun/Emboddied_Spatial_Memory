"""Private, standard-library E0 scoring; never imported by the public extractor.

The caller supplies already bound XML text and sealed predictions. This module
does not open files, run physics, select observations, or return truth to a
predictor. Passing an engineering gate is not a model or full-map claim.
"""
from copy import deepcopy
import math
import xml.etree.ElementTree as ET


_PREDICTION_KEYS = {"schema_version", "candidates", "conflicts",
                    "incomplete_observations", "rejected_counts", "history_frames"}
_CANDIDATE_KEYS = {"coordinate_intervals_m", "coordinates_m",
                   "plane_height_interval_m", "support"}
_SUPPORT_KEYS = {"local_frame_index", "pixel_pair", "boundary_kind",
                "raw_interval_m", "plane_height_interval_m"}
_BOUNDARIES = ("x_left", "x_right", "y_front")
_REJECTED_KEYS = {"zero_depth_pixels", "clipped_depth_pixels", "insufficient_side_run_pairs",
                  "invalid_gap_pairs", "nonfarther_gap_pairs", "insufficient_row_groups",
                  "insufficient_side_patch_groups", "missing_front_groups", "incompatible_boundary_groups"}
_EVALUATION_KEYS = {
    "query_modes", "worlds", "queries", "total_frame_consumptions", "truth_source",
    "matching", "coordinate_targets", "maximum_coordinate_interval_width_m",
    "maximum_coordinate_midpoint_error_m", "midpoint_error_gate_role",
    "truth_in_each_coordinate_interval_required", "truth_in_plane_height_interval_required",
    "missing_extra_ambiguous_or_conflicting_candidates_allowed", "all_registered_queries_required",
    "invariant_checks", "allow_outcome_labels", "predictor_count_is_not_extractor_input",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _mapping(value, keys, name):
    _require(isinstance(value, dict) and set(value) == keys,
             name + " has missing or unexpected fields")


def _number(value, name):
    _require(type(value) in (int, float), name + " must be a real number")
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    _require(finite, name + " must be finite")
    return value


def _integer(value, name):
    _require(type(value) is int and value >= 0, name + " must be a nonnegative integer")
    return value


def _sequence(value, length, name):
    _require(isinstance(value, list) and len(value) == length,
             name + " has the wrong array shape")


def _vector(value, length, name):
    _sequence(value, length, name)
    for item in value:
        _number(item, name)
    return value


def _interval(value, name):
    _vector(value, 2, name)
    _require(value[0] <= value[1], name + " is reversed")
    _number(value[1] - value[0], name + " width")
    return value


def _json_values(value, name):
    """Reject non-JSON/nonfinite objects even in diagnostic-only subtrees."""
    if value is None or type(value) in (str, bool):
        return
    if type(value) in (int, float):
        _number(value, name)
    elif isinstance(value, list):
        for item in value:
            _json_values(item, name)
    elif isinstance(value, dict):
        _require(all(type(key) is str for key in value), name + " keys must be strings")
        for item in value.values():
            _json_values(item, name)
    else:
        raise ValueError(name + " contains a non-JSON value")


def _xml_vector(text, name):
    _require(isinstance(text, str), name + " is missing")
    try:
        values = [float(item) for item in text.split()]
    except ValueError as error:
        raise ValueError(name + " is not numeric") from error
    return _vector(values, 3, name)


def targets_from_xml(xml_text):
    """Derive two actual openings from direct, unrotated worldbody gate boxes.

    Coordinates are the left inner x, right inner x, and common front y. Gate
    indices identify XML geoms, while returned order is actual ascending y.
    Only this private side knows that the registered source has two gates.
    """
    _require(isinstance(xml_text, str) and xml_text.strip(), "XML text is required")
    upper = xml_text.upper()
    _require("<!DOCTYPE" not in upper and "<!ENTITY" not in upper,
             "XML entities and document types are not supported")
    try:
        tree = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise ValueError("invalid XML") from error
    _require(tree.tag == "mujoco" and len(tree.findall("worldbody")) == 1,
             "one MuJoCo worldbody is required")
    world = tree.find("worldbody")
    orientation = {"quat", "euler", "axisangle", "xyaxes", "zaxis", "fromto"}
    for default in tree.findall(".//default/geom"):
        _require(not orientation.intersection(default.attrib),
                 "inherited geom orientation is not supported")
    expected = {f"gate_{index}_{side}" for index in range(2) for side in ("left", "right")}
    found = {}
    for geom in tree.iter("geom"):
        name = geom.get("name", "")
        if not name.startswith("gate_"):
            continue
        _require(name in expected and name not in found, "unexpected or duplicate gate geom")
        _require(geom in list(world), "gate geom must be directly in world coordinates")
        _require(geom.get("type") == "box" and "class" not in geom.attrib,
                 "gate geom must be an explicit box without a class override")
        _require(not orientation.intersection(geom.attrib), "rotated gate boxes are unsupported")
        position = _xml_vector(geom.get("pos"), name + " pos")
        size = _xml_vector(geom.get("size"), name + " size")
        _require(all(item > 0 for item in size), "box half sizes must be positive")
        found[name] = (position, size)
    _require(set(found) == expected, "all four registered gate boxes are required")
    targets = []
    for index in range(2):
        left, ls = found[f"gate_{index}_left"]
        right, rs = found[f"gate_{index}_right"]
        front_left, front_right = left[1] - ls[1], right[1] - rs[1]
        top_left, top_right = left[2] + ls[2], right[2] + rs[2]
        for value in (front_left, front_right, top_left, top_right):
            _number(value, "derived XML surface")
        # Roundoff tolerance only: no geometric matching/precision gate is relaxed.
        _require(math.isclose(front_left, front_right, rel_tol=0, abs_tol=1e-12),
                 "gate sides have different front edges")
        _require(math.isclose(top_left, top_right, rel_tol=0, abs_tol=1e-12),
                 "gate sides have different top surfaces")
        coordinates = [left[0] + ls[0], right[0] - rs[0], front_left]
        _vector(coordinates, 3, "derived XML coordinates")
        _require(coordinates[0] < coordinates[1], "gate opening is not positive")
        targets.append({"coordinates_m": coordinates, "plane_height_m": top_left,
                        "gate_index": index})
    targets.sort(key=lambda target: target["coordinates_m"][2])
    _require(targets[0]["coordinates_m"][2] < targets[1]["coordinates_m"][2],
             "two distinct gate front positions are required")
    return targets


def _validate_candidate(candidate, history_frames):
    _mapping(candidate, _CANDIDATE_KEYS, "candidate")
    intervals = candidate["coordinate_intervals_m"]
    _sequence(intervals, 3, "coordinate intervals")
    for interval in intervals:
        _interval(interval, "coordinate interval")
    coordinates = _vector(candidate["coordinates_m"], 3, "coordinates")
    for coordinate, interval in zip(coordinates, intervals):
        midpoint = interval[0] / 2 + interval[1] / 2
        _require(math.isclose(coordinate, midpoint, rel_tol=0, abs_tol=1e-12),
                 "coordinate does not equal its interval midpoint")
    _require(coordinates[0] < coordinates[1], "candidate opening is not positive")
    height = _interval(candidate["plane_height_interval_m"], "plane height interval")
    support = candidate["support"]
    _require(isinstance(support, list) and support, "candidate support must be nonempty")
    kinds = set()
    for item in support:
        _mapping(item, _SUPPORT_KEYS, "support")
        frame = _integer(item["local_frame_index"], "support frame")
        _require(frame < history_frames, "support frame is outside supplied history")
        kind = item["boundary_kind"]
        _require(isinstance(kind, str) and kind in _BOUNDARIES, "unknown boundary kind")
        kinds.add(kind)
        _sequence(item["pixel_pair"], 2, "pixel pair")
        for pixel in item["pixel_pair"]:
            _sequence(pixel, 2, "pixel")
            for component in pixel:
                _integer(component, "pixel coordinate")
        raw = _interval(item["raw_interval_m"], "raw support interval")
        raw_height = _interval(item["plane_height_interval_m"], "support plane interval")
        final = intervals[_BOUNDARIES.index(kind)]
        _require(raw[0] <= final[0] <= final[1] <= raw[1],
                 "coordinate interval exceeds supporting interval")
        _require(raw_height[0] <= height[0] <= height[1] <= raw_height[1],
                 "height interval exceeds supporting interval")
    _require(kinds == set(_BOUNDARIES), "all three boundaries require support")


def _validate_prediction(prediction):
    _mapping(prediction, _PREDICTION_KEYS, "prediction")
    _require(prediction["schema_version"] == "public-openings-v1", "unknown prediction schema")
    history_frames = _integer(prediction["history_frames"], "history_frames")
    _require(history_frames > 0, "at least one supplied history frame is required")
    for field in ("candidates", "conflicts", "incomplete_observations"):
        _require(isinstance(prediction[field], list), field + " must be an array")
    for candidate in prediction["candidates"]:
        _validate_candidate(candidate, history_frames)
    for conflict in prediction["conflicts"]:
        _mapping(conflict, {"reason", "members"}, "conflict")
        _require(isinstance(conflict["reason"], str) and conflict["reason"], "conflict reason required")
        _require(isinstance(conflict["members"], list) and len(conflict["members"]) >= 2,
                 "conflict must retain at least two members")
        for member in conflict["members"]:
            _validate_candidate(member, history_frames)
    for incomplete in prediction["incomplete_observations"]:
        _mapping(incomplete, {"local_frame_index", "row_span", "plane_height_interval_m", "reason"},
                 "incomplete observation")
        _require(_integer(incomplete["local_frame_index"], "incomplete frame") < history_frames,
                 "incomplete frame is outside supplied history")
        _sequence(incomplete["row_span"], 2, "incomplete row span")
        for row in incomplete["row_span"]:
            _integer(row, "incomplete row")
        _require(incomplete["row_span"][0] <= incomplete["row_span"][1], "row span is reversed")
        _interval(incomplete["plane_height_interval_m"], "incomplete height interval")
        _require(isinstance(incomplete["reason"], str) and incomplete["reason"],
                 "incomplete reason required")
    rejected = prediction["rejected_counts"]
    _mapping(rejected, _REJECTED_KEYS, "rejected_counts")
    for key, value in rejected.items():
        _require(isinstance(key, str) and key, "rejection names must be nonempty strings")
        _integer(value, "rejected count")
    _json_values(prediction, "prediction")


def _validate_targets(targets):
    _require(isinstance(targets, list), "targets must be an array")
    indices = set()
    previous_y = None
    for target in targets:
        _mapping(target, {"coordinates_m", "plane_height_m", "gate_index"}, "target")
        coordinates = _vector(target["coordinates_m"], 3, "target coordinates")
        _require(coordinates[0] < coordinates[1], "target opening is not positive")
        _number(target["plane_height_m"], "target height")
        index = _integer(target["gate_index"], "target gate index")
        _require(index not in indices, "duplicate target gate index")
        _require(previous_y is None or previous_y < coordinates[2], "targets must follow actual y order")
        indices.add(index)
        previous_y = coordinates[2]


def _complete_assignments(edges, target_count):
    """Return zero, one, or two witnesses; two means uniqueness is disproved."""
    if len(edges) != target_count:
        return []
    order = sorted(range(len(edges)), key=lambda index: (len(edges[index]), index))
    solutions = []

    def visit(depth, used, assigned):
        if len(solutions) >= 2:
            return
        if depth == len(order):
            solutions.append([assigned[index] for index in range(len(edges))])
            return
        index = order[depth]
        for target in edges[index]:
            if target not in used:
                assigned[index] = target
                visit(depth + 1, used | {target}, assigned)
                del assigned[index]

    visit(0, set(), {})
    return solutions


def assess_geometry(prediction, targets, evaluation_parameters):
    """Audit every supplied candidate against every registered target.

    Malformed schemas raise ValueError; valid predictions that miss engineering
    gates return accepted=False with all available diagnostic evidence. An empty
    recent prediction and empty target list have one (empty) complete matching.
    Incomplete observations are retained, not independently treated as failures.
    """
    _validate_prediction(prediction)
    _validate_targets(targets)
    _mapping(evaluation_parameters, _EVALUATION_KEYS, "evaluation parameters")
    _json_values(evaluation_parameters, "evaluation parameters")
    _require(evaluation_parameters["matching"] ==
             "unique_one_to_one_all_candidates_and_targets_no_best_subset", "unsupported matching rule")
    _require(evaluation_parameters["coordinate_targets"] == list(_BOUNDARIES),
             "unsupported coordinate targets")
    for name in ("truth_in_each_coordinate_interval_required", "truth_in_plane_height_interval_required",
                 "all_registered_queries_required", "predictor_count_is_not_extractor_input"):
        _require(evaluation_parameters[name] is True, "required evaluation boundary disabled: " + name)
    for name in ("missing_extra_ambiguous_or_conflicting_candidates_allowed", "allow_outcome_labels"):
        _require(evaluation_parameters[name] is False, "unsupported evaluation permission: " + name)
    maximum_width = _number(evaluation_parameters["maximum_coordinate_interval_width_m"], "maximum width")
    maximum_error = _number(evaluation_parameters["maximum_coordinate_midpoint_error_m"], "maximum midpoint error")
    _require(maximum_width > 0 and maximum_error > 0, "precision limits must be positive")
    _require(maximum_error == maximum_width / 2, "midpoint consistency limit must equal half the width limit")
    candidates = prediction["candidates"]
    diagnostics = []
    edges = []
    for candidate_index, candidate in enumerate(candidates):
        choices = []
        for target_index, target in enumerate(targets):
            contained = [interval[0] <= coordinate <= interval[1]
                         for interval, coordinate in zip(candidate["coordinate_intervals_m"], target["coordinates_m"])]
            height = candidate["plane_height_interval_m"]
            height_contained = height[0] <= target["plane_height_m"] <= height[1]
            errors = [abs(predicted - actual) for predicted, actual
                      in zip(candidate["coordinates_m"], target["coordinates_m"])]
            _vector(errors, 3, "derived midpoint errors")
            diagnostics.append({"candidate_index": candidate_index, "target_index": target_index,
                                "gate_index": target["gate_index"], "coordinate_truth_contained": contained,
                                "height_truth_contained": height_contained, "coordinate_midpoint_error_m": errors})
            if all(contained) and height_contained:
                choices.append(target_index)
        edges.append(choices)
    solutions = _complete_assignments(edges, len(targets))
    unique = len(solutions) == 1
    matches = []
    if unique:
        for candidate_index, target_index in enumerate(solutions[0]):
            match = deepcopy(diagnostics[candidate_index * len(targets) + target_index])
            match["coordinate_interval_width_m"] = [high - low for low, high
                                                    in candidates[candidate_index]["coordinate_intervals_m"]]
            matches.append(match)
    widths_valid = all(high - low <= maximum_width for candidate in candidates
                       for low, high in candidate["coordinate_intervals_m"])
    errors_valid = unique and all(error <= maximum_error for match in matches
                                  for error in match["coordinate_midpoint_error_m"])
    checks = {
        "candidate_count_matches": len(candidates) == len(targets),
        "no_conflicting_candidates": not prediction["conflicts"],
        "coordinate_interval_widths_within_limit": widths_valid,
        "complete_truth_containing_matching_exists": bool(solutions),
        "unique_one_to_one_matching": unique,
        "coordinate_midpoint_errors_within_limit": errors_valid,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {"accepted": not failed, "checks": checks, "failed_checks": failed,
            "matches": matches, "targets": deepcopy(targets),
            "candidate_count": len(candidates), "expected_count": len(targets),
            "eligible_target_indices": edges, "pair_diagnostics": diagnostics,
            "complete_matching_count_capped_at_two": len(solutions),
            "conflict_count": len(prediction["conflicts"]),
            "incomplete_observation_count": len(prediction["incomplete_observations"])}
