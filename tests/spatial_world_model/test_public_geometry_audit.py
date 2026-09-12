"""Server-only analytic E0 evaluator checks; no simulator/model imports."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from spatial_world_model.public_geometry_audit import assess_geometry, targets_from_xml
from spatial_world_model.public_geometry import recover_openings
from test_public_geometry import opening, parameters as extractor_parameters, rectangle


XML = """<mujoco><default><geom friction="0.25 0.005 0.0001"/></default><worldbody>
<geom name="floor" type="plane" size="3 3 0.1"/>
<geom name="gate_0_left" type="box" pos="-0.55 0.6 0.15" size="0.25 0.025 0.15"/>
<geom name="gate_0_right" type="box" pos="0.45 0.6 0.15" size="0.35 0.025 0.15"/>
<geom name="gate_1_left" type="box" pos="-0.45 2.2 0.15" size="0.35 0.025 0.15"/>
<geom name="gate_1_right" type="box" pos="0.55 2.2 0.15" size="0.25 0.025 0.15"/>
</worldbody></mujoco>"""


def evaluation_parameters():
    path = Path(__file__).resolve().parents[2] / "configs/spatial_history/public_geometry_proposal_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))["evaluation_only"]


def target(x_left=-0.3, x_right=0.1, y_front=0.575, index=0):
    return {"coordinates_m": [x_left, x_right, y_front], "plane_height_m": 0.3, "gate_index": index}


def candidate(actual=None, radius=0.01):
    actual = target() if actual is None else actual
    intervals = [[value - radius, value + radius] for value in actual["coordinates_m"]]
    height = [actual["plane_height_m"] - 0.0001, actual["plane_height_m"] + 0.0001]
    support = [{"local_frame_index": 0, "pixel_pair": [[10, 11], [11, 11]],
                "boundary_kind": kind, "raw_interval_m": list(interval),
                "plane_height_interval_m": list(height)}
               for kind, interval in zip(("x_left", "x_right", "y_front"), intervals)]
    return {"coordinate_intervals_m": intervals,
            "coordinates_m": [(low + high) / 2 for low, high in intervals],
            "plane_height_interval_m": height, "support": support}


def prediction(candidates=None):
    return {"schema_version": "public-openings-v1",
            "candidates": [candidate()] if candidates is None else candidates,
            "conflicts": [], "incomplete_observations": [],
            "rejected_counts": {key: 0 for key in (
                "zero_depth_pixels", "clipped_depth_pixels", "insufficient_side_run_pairs",
                "invalid_gap_pairs", "nonfarther_gap_pairs", "insufficient_row_groups",
                "insufficient_side_patch_groups", "missing_front_groups", "incompatible_boundary_groups")},
            "history_frames": 1}


class PublicGeometryAuditTests(unittest.TestCase):
    def setUp(self):
        self.parameters = evaluation_parameters()

    def assess(self, value=None, targets=None):
        return assess_geometry(prediction() if value is None else value,
                               [target()] if targets is None else targets, self.parameters)

    def test_xml_reads_actual_box_coordinates_without_world_names(self):
        values = targets_from_xml(XML)
        self.assertEqual([item["gate_index"] for item in values], [0, 1])
        for actual, expected in zip(values, [target(), target(-0.1, 0.3, 2.175, 1)]):
            for observed, wanted in zip(actual["coordinates_m"], expected["coordinates_m"]):
                self.assertAlmostEqual(observed, wanted)
            self.assertAlmostEqual(actual["plane_height_m"], 0.3)
        swapped = XML.replace(" 0.6 ", " 4.6 ")
        self.assertEqual([item["gate_index"] for item in targets_from_xml(swapped)], [1, 0])

    def test_xml_rejects_duplicate_missing_nested_or_extra_gates(self):
        geom = '<geom name="gate_0_left" type="box" pos="-0.55 0.6 0.15" size="0.25 0.025 0.15"/>'
        for value in (XML.replace(geom, geom + geom), XML.replace(geom, ""),
                      XML.replace(geom, "<body>" + geom + "</body>"),
                      XML.replace("</worldbody>", geom.replace("gate_0_left", "gate_2_left") + "</worldbody>")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                targets_from_xml(value)

    def test_xml_rejects_rotations_misalignment_and_nonfinite_geometry(self):
        for value in (XML.replace('name="gate_0_left"', 'name="gate_0_left" quat="1 0 0 0"'),
                      XML.replace('<geom friction=', '<geom euler="0 0 1" friction='),
                      XML.replace('pos="0.45 0.6 0.15"', 'pos="0.45 0.61 0.15"'),
                      XML.replace('pos="0.45 0.6 0.15"', 'pos="0.45 0.6 0.16"'),
                      XML.replace('size="0.25 0.025 0.15"', 'size="0 0.025 0.15"'),
                      XML.replace('pos="-0.55 0.6 0.15"', 'pos="NaN 0.6 0.15"'),
                      XML.replace('pos="-0.55 0.6 0.15"', 'pos="1e999 0.6 0.15"'),
                      XML.replace('type="box"', 'type="sphere"', 1),
                      '<!DOCTYPE mujoco [<!ENTITY value "0">]>' + XML,
                      "<invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                targets_from_xml(value)

    def test_valid_unique_matching_accepts_and_preserves_inputs(self):
        targets = [target(), target(-0.1, 0.3, 2.175, 1)]
        value = prediction([candidate(targets[1]), candidate(targets[0])])
        before = deepcopy((value, targets, self.parameters))
        result = self.assess(value, targets)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["failed_checks"], [])
        self.assertEqual([item["target_index"] for item in result["matches"]], [1, 0])
        self.assertEqual((value, targets, self.parameters), before)
        result["targets"][0]["coordinates_m"][0] = 99
        self.assertEqual(targets, before[1])

    def test_empty_recent_is_valid_and_partial_observations_do_not_invent_gates(self):
        value = prediction([])
        value["history_frames"] = 2
        value["incomplete_observations"] = [{"local_frame_index": 0, "row_span": [2, 3],
                                             "plane_height_interval_m": [0.2999, 0.3001],
                                             "reason": "missing_front_witnesses"}]
        result = self.assess(value, [])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["complete_matching_count_capped_at_two"], 1)
        self.assertEqual(result["incomplete_observation_count"], 1)
        self.assertEqual(result["matches"], [])

    def test_extra_or_missing_candidates_fail_without_best_subset(self):
        for value, targets in ((prediction([]), [target()]),
                               (prediction([candidate(), candidate()]), [target()]),
                               (prediction(), [])):
            with self.subTest(candidates=len(value["candidates"]), targets=len(targets)):
                result = self.assess(value, targets)
                self.assertFalse(result["accepted"])
                self.assertIn("candidate_count_matches", result["failed_checks"])
                self.assertEqual(result["matches"], [])

    def test_ambiguous_full_matching_rejects_even_when_all_intervals_are_narrow(self):
        targets = [target(y_front=0.572, index=0), target(y_front=0.578, index=1)]
        result = self.assess(prediction([candidate(), candidate()]), targets)
        self.assertFalse(result["accepted"])
        self.assertTrue(result["checks"]["complete_truth_containing_matching_exists"])
        self.assertTrue(result["checks"]["coordinate_interval_widths_within_limit"])
        self.assertEqual(result["complete_matching_count_capped_at_two"], 2)
        self.assertIn("unique_one_to_one_matching", result["failed_checks"])

    def test_hall_failure_is_not_accepted_as_per_target_coverage(self):
        targets = [target(y_front=0.572, index=0), target(y_front=0.578, index=1),
                   target(y_front=1.0, index=2)]
        value = prediction([candidate(targets[0], radius=0.001),
                            candidate(targets[0], radius=0.001),
                            candidate(target(y_front=0.8), radius=0.3)])
        result = self.assess(value, targets)
        self.assertFalse(result["checks"]["complete_truth_containing_matching_exists"])
        self.assertEqual(result["complete_matching_count_capped_at_two"], 0)

    def test_too_wide_intervals_fail_even_with_exact_midpoints(self):
        result = self.assess(prediction([candidate(radius=0.013)]))
        self.assertFalse(result["accepted"])
        self.assertTrue(result["checks"]["unique_one_to_one_matching"])
        self.assertIn("coordinate_interval_widths_within_limit", result["failed_checks"])

    def test_coordinate_or_height_truth_outside_interval_fails(self):
        for actual in (target(x_left=-0.32), {**target(), "plane_height_m": 0.31}):
            result = self.assess(targets=[actual])
            self.assertFalse(result["accepted"])
            self.assertFalse(result["checks"]["complete_truth_containing_matching_exists"])

    def test_conflict_fails_even_if_resolved_candidates_match(self):
        value = prediction()
        value["conflicts"] = [{"reason": "empty_common_intersection", "members": [candidate(), candidate()]}]
        result = self.assess(value)
        self.assertFalse(result["accepted"])
        self.assertIn("no_conflicting_candidates", result["failed_checks"])
        self.assertEqual(result["conflict_count"], 1)

    def test_private_or_unknown_fields_are_rejected(self):
        for container in ("top", "candidate", "support", "target", "rejected_counts"):
            value, targets = prediction(), [target()]
            selected = {"top": value, "candidate": value["candidates"][0],
                        "support": value["candidates"][0]["support"][0], "target": targets[0],
                        "rejected_counts": value["rejected_counts"]}[container]
            selected["future_task_success"] = True
            with self.subTest(container=container), self.assertRaises(ValueError):
                self.assess(value, targets)

    def test_nonfinite_boolean_wrong_shape_and_midpoint_values_are_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf"), True, "0", 10 ** 1000):
            value = prediction()
            value["candidates"][0]["coordinates_m"][0] = bad
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                self.assess(value)
        for mutate in (lambda value: value["candidates"][0]["coordinate_intervals_m"].pop(),
                       lambda value: value["candidates"][0]["coordinate_intervals_m"].__setitem__(0, [1, 0]),
                       lambda value: value["candidates"][0]["coordinates_m"].__setitem__(0, -0.299),
                       lambda value: value.__setitem__("history_frames", True),
                       lambda value: value["rejected_counts"].__setitem__("invalid", -1)):
            value = prediction()
            mutate(value)
            with self.assertRaises(ValueError):
                self.assess(value)

    def test_support_requires_valid_frames_all_edges_and_enclosing_raw_intervals(self):
        for mutate in (lambda support: support.pop(),
                       lambda support: support[0].__setitem__("local_frame_index", 1),
                       lambda support: support[0].__setitem__("raw_interval_m", [-0.301, -0.299]),
                       lambda support: support[0].__setitem__("pixel_pair", [[-1, 0], [0, 0]]),
                       lambda support: support[0].__setitem__("plane_height_interval_m", [0.3, 0.3])):
            value = prediction()
            mutate(value["candidates"][0]["support"])
            with self.assertRaises(ValueError):
                self.assess(value)

    def test_invalid_private_diagnostics_or_parameters_never_pass_silently(self):
        value = prediction([])
        value["incomplete_observations"] = [{"local_frame_index": 0, "row_span": [0, 1],
                                             "plane_height_interval_m": [0, float("nan")], "reason": "x"}]
        with self.assertRaises(ValueError):
            self.assess(value, [])
        for field, invalid in (("allow_outcome_labels", True),
                               ("maximum_coordinate_interval_width_m", float("nan")),
                               ("maximum_coordinate_midpoint_error_m", 0.013),
                               ("truth_in_each_coordinate_interval_required", False)):
            parameters = deepcopy(self.parameters)
            parameters[field] = invalid
            with self.subTest(field=field), self.assertRaises(ValueError):
                assess_geometry(prediction(), [target()], parameters)

    def test_evaluator_has_no_file_reads_and_no_prediction_dependency(self):
        with patch("builtins.open", side_effect=AssertionError("unexpected file access")):
            values = targets_from_xml(XML)
            result = self.assess(prediction([candidate(values[0]), candidate(values[1])]), values)
        self.assertTrue(result["accepted"])

    def test_extractor_opening_outputs_integrate_with_strict_private_audit(self):
        sensor, extractor = extractor_parameters()
        actual = {"coordinates_m": [-0.02, 0.02, -0.01],
                  "plane_height_m": 1.0, "gate_index": 0}
        first, second, partial = opening(), opening(), opening()
        second["time_s"], partial["time_s"] = 1.0, 2.0
        # A clipped front adds genuine extractor diagnostics; complete earlier
        # observations still supply all three independently specified boundaries.
        rectangle(partial, (1, 5), (7, 7), 0.0)
        rectangle(partial, (10, 14), (7, 7), 0.0)
        observed = recover_openings([first, second, partial], sensor, extractor)
        result = self.assess(observed, [actual])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["candidate_count"], 1)
        self.assertGreater(result["incomplete_observation_count"], 0)
        self.assertEqual({item["local_frame_index"] for item in observed["candidates"][0]["support"]},
                         {0, 1})
        # Inconsistent analytic poses create an overlap chain with no shared
        # interval. Its real extractor conflict schema must be scored as a
        # preserved engineering failure, not rejected as malformed evidence.
        chain = [opening(), opening(), opening()]
        for index, frame in enumerate(chain):
            frame["time_s"] = float(index)
            frame["camera_position_m"][0] = index * 0.015
        conflicted = recover_openings(chain, sensor, extractor)
        self.assertTrue(conflicted["conflicts"])
        conflict_result = self.assess(conflicted, [actual])
        self.assertFalse(conflict_result["accepted"])
        self.assertFalse(conflict_result["checks"]["no_conflicting_candidates"])


if __name__ == "__main__":
    unittest.main()
