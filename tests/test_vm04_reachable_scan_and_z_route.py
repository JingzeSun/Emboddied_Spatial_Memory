"""Tests for the real public reachable scan and the place-layer Z route.

These cover the second D-207 engineering item: a real ``GetReachablePositions``
scan, per-step reachability verification as the long-route yield guard, and the
Z-route family constructor with its mandatory later disambiguation.  They also
re-assert that none of this moves a frozen number or opens an authorization.
"""

import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    assert_numeric_freeze_complete,
    make_public_visibility_assessment,
    public_route_projection,
    validate_route_plan,
)
from vsmt.vm04_public_route_builder import (  # noqa: E402
    build_route_plan_from_public_graph,
)
from vsmt.vm04_place_route_builder import (  # noqa: E402
    build_z_route_plan,
    registered_place_programs,
    seal_z_route_geometry,
    validate_z_route_geometry,
    z_route_segments,
)
from vsmt.vm04_reachable_scan import (  # noqa: E402
    ReachableGrid,
    nominal_route_poses,
    registered_grid_size_m,
    seal_public_reachable_scan,
    seal_route_step_reachability,
    validate_public_reachable_scan,
    validate_route_step_reachability,
)


CONFIG_DIRECTORY = ROOT / "configs" / "vsmt"
CONTRACT_PATH = CONFIG_DIRECTORY / "vm04_observation_suitability_v4.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
SUBJECT_SHA = "a" * 64
CONFIG_SHA = "b" * 64
SUPPORT_SHA = "c" * 64
GRID = 0.25


def _sha(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _assessment(state, *, subject="place-anchor:A"):
    if state == "out_of_view":
        projected, unoccluded, support = 0, 0, None
    elif state == "occluded":
        projected, unoccluded, support = 7, 0, None
    else:
        projected, unoccluded, support = 7, 7, SUPPORT_SHA
    return make_public_visibility_assessment(
        subject_public_ref=subject,
        subject_reference_sealed_before_frame=True,
        projected_public_sample_count=projected,
        unoccluded_public_sample_count=unoccluded,
        current_public_support_sha256=support,
        terminal_reobservation_phase=False,
    )


def _builder_receipt(assessment, index):
    receipt = {
        "schema_version": "vsmt-vm04-public-visibility-builder-receipt-v1",
        "subject_seal_sha256": SUBJECT_SHA,
        "current_observation_index": index,
        "current_public_depth_sha256": hashlib.sha256(
            f"depth{index}".encode("utf-8")).hexdigest(),
        "camera_calibration_and_pose_sha256": hashlib.sha256(
            f"camera{index}".encode("utf-8")).hexdigest(),
        "config_sha256": CONFIG_SHA,
        "assessment_sha256": assessment["assessment_sha256"],
        "invalid_or_missing_depth_treated_as_unoccluded": True,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def _grid_positions(planned, *, margin_m=0.5, drop=()):
    """A reachable grid covering every planned pose, minus dropped cells."""

    xs = [pose["x_m"] for pose in planned]
    zs = [pose["z_m"] for pose in planned]
    dropped = {(round(x, 6), round(z, 6)) for x, z in drop}
    positions = []
    steps_x = int(round((max(xs) - min(xs) + 2 * margin_m) / GRID))
    steps_z = int(round((max(zs) - min(zs) + 2 * margin_m) / GRID))
    for i in range(steps_x + 1):
        for j in range(steps_z + 1):
            x = round(min(xs) - margin_m + i * GRID, 6)
            z = round(min(zs) - margin_m + j * GRID, 6)
            if (x, z) in dropped:
                continue
            positions.append({"x": x, "y": 0.9, "z": z})
    return positions


def _z_geometry(*, disambiguation=None, **overrides):
    values = {
        "corridor_a_length_m": 4.0,
        "connector_length_m": 3.0,
        "corridor_b_length_m": 4.0,
        "turn_degrees": 90.0,
        "first_turn": "RotateRight",
        "corridor_a_public_ref": "corridor:A",
        "corridor_b_public_ref": "corridor:B",
        "later_disambiguation_actions": (
            ["RotateRight"] * 6 + ["MoveAhead"] * 8
            if disambiguation is None else disambiguation
        ),
        "distinguishing_public_ref": "landmark:doorway-A",
    }
    values.update(overrides)
    return seal_z_route_geometry(contract=CONTRACT, **values)


def _z_scan_rows(planned, segments, *, hidden_state="out_of_view",
                 corridor_b_state=None, pose_shift=None):
    rows = []
    for index, pose in enumerate(planned):
        if index <= segments["corridor_a"][1]:
            state = "visible"
        elif index >= segments["later_disambiguation"][0]:
            state = "visible"
        elif (corridor_b_state is not None and
              segments["corridor_b"][0] <= index <= segments["corridor_b"][1]):
            state = corridor_b_state
        else:
            state = hidden_state
        assessment = _assessment(state)
        receipt = _builder_receipt(assessment, index)
        scan_pose = dict(pose)
        if pose_shift is not None and index == pose_shift[0]:
            scan_pose["x_m"] = scan_pose["x_m"] + pose_shift[1]
        rows.append({
            "observation_index": index,
            "pose": scan_pose,
            "visibility_assessment": assessment,
            "visibility_builder_receipt": receipt,
            "public_evidence_sha256": receipt["receipt_sha256"],
            "current_public_depth_sha256":
                receipt["current_public_depth_sha256"],
            "camera_calibration_and_pose_sha256":
                receipt["camera_calibration_and_pose_sha256"],
            "scan_phase": "pre_intervention_public_route_scan",
            "support_role": (
                "pre_intervention_public_subject_or_locus_not_post_action"
                "_confirmation"
            ),
            "future_or_action_outcome_used": False,
        })
    return rows


def _build_z(**overrides):
    geometry = overrides.pop("geometry", None) or _z_geometry()
    expansion = z_route_segments(geometry, contract=CONTRACT)
    initial = {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0, "yaw_deg": 0.0}
    planned = nominal_route_poses(
        initial, expansion["registered_action_names"], contract=CONTRACT)
    scan = overrides.pop("scan", None) or seal_public_reachable_scan(
        house_id="house:pilot-01",
        raw_positions=_grid_positions(planned, drop=overrides.pop("drop", ())),
        contract=CONTRACT,
    )
    rows = overrides.pop("rows", None)
    if rows is None:
        rows = _z_scan_rows(planned, expansion["segments"],
                            **overrides.pop("row_options", {}))
    arguments = {
        "episode_id": "episode:place:001",
        "program": "BIND",
        "branch_type": "out_of_view_then_reobservation",
        "visibility_subject_public_ref": "place-anchor:A",
        "visibility_subject_seal_sha256": SUBJECT_SHA,
        "visibility_builder_config_sha256": CONFIG_SHA,
        "geometry": geometry,
        "initial_pose": initial,
        "reachable_scan": scan,
        "pose_scan_rows": rows,
        "contract": CONTRACT,
    }
    arguments.update(overrides)
    return build_z_route_plan(**arguments)


def _chain_graph(hidden_steps):
    """A linear pose chain whose only valid route is longer than 24 steps."""

    states = ["visible", "visible"] + ["out_of_view"] * hidden_steps + [
        "visible", "visible"]
    scans, edges = [], []
    for index, state in enumerate(states):
        assessment = _assessment(state, subject="subject:0001")
        receipt = _builder_receipt(assessment, index)
        scans.append({
            "pose_id": f"pose:{index}",
            "pose": {"x_m": round(index * GRID, 6), "y_m": 0.9, "z_m": 0.0,
                     "yaw_deg": 0.0 if index < 2 else 30.0},
            "visibility_assessment": assessment,
            "visibility_builder_receipt": receipt,
            "current_public_depth_sha256":
                receipt["current_public_depth_sha256"],
            "camera_calibration_and_pose_sha256":
                receipt["camera_calibration_and_pose_sha256"],
            "public_evidence_sha256": receipt["receipt_sha256"],
            "scan_phase": "pre_intervention_public_route_scan",
            "support_role": (
                "pre_intervention_public_subject_or_locus_not_post_action"
                "_confirmation"
            ),
            "future_or_action_outcome_used": False,
        })
        if index:
            edges.append({"from_pose_id": f"pose:{index - 1}",
                          "to_pose_id": f"pose:{index}",
                          "action": "MoveAhead"})
    return scans, edges


class FrozenStateUnchangedTests(unittest.TestCase):
    """Neither builder may move a frozen number or open an authorization."""

    def test_every_authorization_bit_is_still_false(self):
        authorization = CONTRACT["authorization"]
        self.assertEqual(len(authorization), 14)
        self.assertTrue(all(value is False for value in authorization.values()))

    def test_pending_artifact_digests_are_still_the_same_eight(self):
        report = assert_numeric_freeze_complete(CONTRACT)
        self.assertEqual(len(report["pending_artifact_digests"]), 8)
        self.assertFalse(report["generation_authorized"])

    def test_earlier_contract_versions_keep_their_bytes(self):
        expected = {
            "vm04_observation_suitability_proposal_v1.json":
                "2d99d51995e1b8f0ded5e66f1f0df9b8fab94c452655324ba289105eb38ba4c3",
            "vm04_observation_suitability_v2.json":
                "48b50df4adc162e2896145a01d2ab4eb8c87d4dbb943898abab29bb18079fa59",
            "vm04_observation_suitability_v3.json":
                "31d2e156b8a4c1ca39837aadc004c804a3e016e0bf9d55c0d211f96054130723",
        }
        for name, digest in expected.items():
            self.assertEqual(
                hashlib.sha256(
                    (CONFIG_DIRECTORY / name).read_bytes()).hexdigest(),
                digest, name)

    def test_scan_grid_is_the_frozen_move_magnitude(self):
        self.assertEqual(registered_grid_size_m(CONTRACT), GRID)
        self.assertEqual(
            CONTRACT["observation_trajectory"]["frozen_numeric_values"]
            ["maximum_route_steps"], 24)


class ReachableScanTests(unittest.TestCase):
    def setUp(self):
        self.positions = [{"x": i * GRID, "y": 0.9, "z": j * GRID}
                          for i in range(8) for j in range(8)]

    def test_seals_and_revalidates_a_real_scan(self):
        scan = seal_public_reachable_scan(
            house_id="house:001", raw_positions=self.positions,
            contract=CONTRACT)
        self.assertEqual(scan["cell_count"], 64)
        self.assertEqual(validate_public_reachable_scan(
            scan, contract=CONTRACT), scan)
        grid = ReachableGrid(scan, contract=CONTRACT)
        self.assertTrue(grid.contains(0.0, 0.0))
        self.assertTrue(grid.contains(1.75, 1.75))
        self.assertFalse(grid.contains(2.0, 0.0))

    def test_rejects_an_empty_or_failed_query(self):
        with self.assertRaises(ObservationConstructionError):
            seal_public_reachable_scan(
                house_id="house:001", raw_positions=[], contract=CONTRACT)
        with self.assertRaises(ObservationConstructionError):
            seal_public_reachable_scan(
                house_id="house:001", raw_positions=self.positions,
                contract=CONTRACT, source_action_success=False)

    def test_rejects_positions_off_one_registered_grid(self):
        positions = self.positions + [{"x": 0.1, "y": 0.9, "z": 0.0}]
        with self.assertRaises(ObservationConstructionError):
            seal_public_reachable_scan(
                house_id="house:001", raw_positions=positions,
                contract=CONTRACT)

    def test_rejects_a_repeated_cell_and_a_second_floor(self):
        with self.assertRaises(ObservationConstructionError):
            seal_public_reachable_scan(
                house_id="house:001",
                raw_positions=self.positions + [self.positions[0]],
                contract=CONTRACT)
        with self.assertRaises(ObservationConstructionError):
            seal_public_reachable_scan(
                house_id="house:001",
                raw_positions=self.positions + [
                    {"x": 0.0, "y": 3.9, "z": 0.0}],
                contract=CONTRACT)

    def test_rejects_a_tampered_digest_or_attestation(self):
        scan = seal_public_reachable_scan(
            house_id="house:001", raw_positions=self.positions,
            contract=CONTRACT)
        for field, value in (
            ("private_identity_used", True),
            ("future_or_action_outcome_used", True),
            ("positions_chosen_after_a_failure", True),
            ("cell_count", 63),
            ("house_id", "house:002"),
        ):
            tampered = dict(scan)
            tampered[field] = value
            with self.assertRaises(ObservationConstructionError):
                validate_public_reachable_scan(tampered, contract=CONTRACT)


class NominalKinematicsTests(unittest.TestCase):
    def test_translation_and_rotation_follow_the_frozen_templates(self):
        poses = nominal_route_poses(
            {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0, "yaw_deg": 0.0},
            ["MoveAhead", "RotateRight", "RotateRight", "RotateRight",
             "MoveAhead"],
            contract=CONTRACT)
        self.assertEqual(len(poses), 6)
        self.assertAlmostEqual(poses[1]["z_m"], 0.25)
        self.assertAlmostEqual(poses[4]["yaw_deg"], 90.0)
        self.assertAlmostEqual(poses[5]["x_m"], 0.25)
        self.assertAlmostEqual(poses[5]["z_m"], 0.25, places=9)

    def test_refuses_to_translate_from_a_non_axis_aligned_heading(self):
        with self.assertRaises(ObservationConstructionError) as caught:
            nominal_route_poses(
                {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0, "yaw_deg": 0.0},
                ["RotateRight", "MoveAhead"], contract=CONTRACT)
        self.assertIn("axis aligned", str(caught.exception))

    def test_look_actions_do_not_move_the_agent(self):
        poses = nominal_route_poses(
            {"x_m": 1.0, "y_m": 0.9, "z_m": 2.0, "yaw_deg": 90.0},
            ["LookDown", "LookUp"], contract=CONTRACT)
        for pose in poses:
            self.assertEqual((pose["x_m"], pose["z_m"]), (1.0, 2.0))


class StepReachabilityTests(unittest.TestCase):
    def test_a_fully_reachable_route_seals_and_recomputes(self):
        result = _build_z()
        receipt = result["step_reachability"]
        self.assertTrue(receipt["every_planned_step_verified_reachable"])
        self.assertFalse(receipt["tolerances_relaxed_to_raise_yield"])
        self.assertFalse(receipt["blocked_route_replacement_allowed"])
        self.assertEqual(len(receipt["steps"]),
                         receipt["verified_step_count"] + 1)
        self.assertEqual(
            validate_route_step_reachability(
                receipt, plan=result["route_plan"],
                scan=validate_public_reachable_scan(
                    seal_public_reachable_scan(
                        house_id="house:pilot-01",
                        raw_positions=_grid_positions(nominal_route_poses(
                            {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0,
                             "yaw_deg": 0.0},
                            z_route_segments(_z_geometry(), contract=CONTRACT)
                            ["registered_action_names"], contract=CONTRACT)),
                        contract=CONTRACT),
                    contract=CONTRACT),
                contract=CONTRACT),
            receipt)

    def test_one_blocked_cell_fails_the_whole_route(self):
        with self.assertRaises(ObservationConstructionError) as caught:
            _build_z(drop=((0.0, 1.0),))
        self.assertIn("reachable", str(caught.exception))

    def test_a_tampered_verification_receipt_is_refused(self):
        result = _build_z()
        tampered = dict(result["step_reachability"])
        tampered["every_planned_step_verified_reachable"] = False
        with self.assertRaises(ObservationConstructionError):
            validate_route_step_reachability(
                tampered, plan=result["route_plan"],
                scan=seal_public_reachable_scan(
                    house_id="house:pilot-01",
                    raw_positions=_grid_positions(nominal_route_poses(
                        {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0, "yaw_deg": 0.0},
                        z_route_segments(_z_geometry(), contract=CONTRACT)
                        ["registered_action_names"], contract=CONTRACT)),
                    contract=CONTRACT),
                contract=CONTRACT)


class ZRouteGeometryTests(unittest.TestCase):
    def test_the_frozen_z_shape_fits_the_place_budget_exactly(self):
        expansion = z_route_segments(_z_geometry(), contract=CONTRACT)
        self.assertEqual(expansion["place_layer_budget"], 64)
        self.assertEqual(len(expansion["registered_action_names"]), 64)
        self.assertEqual(expansion["turn_actions_each"], 3)
        self.assertEqual(expansion["first_turn"], "RotateRight")
        self.assertEqual(expansion["second_turn"], "RotateLeft")

    def test_the_geometry_alone_costs_the_registered_fifty_actions(self):
        expansion = z_route_segments(
            _z_geometry(disambiguation=["MoveAhead"]), contract=CONTRACT)
        self.assertEqual(len(expansion["registered_action_names"]), 51)
        self.assertEqual(
            CONTRACT["place_identity_revision"]["z_route_family"]
            ["approximate_actions_required"], 50)

    def test_a_z_route_without_later_disambiguation_is_refused(self):
        with self.assertRaises(ObservationConstructionError) as caught:
            _z_geometry(disambiguation=[])
        self.assertIn("one-shot association", str(caught.exception))

    def test_visually_similar_corridors_and_distinct_refs_are_required(self):
        geometry = _z_geometry()
        tampered = dict(geometry)
        tampered["corridors_visually_similar_by_construction"] = False
        tampered["geometry_sha256"] = _sha({
            key: value for key, value in tampered.items()
            if key != "geometry_sha256"})
        with self.assertRaises(ObservationConstructionError):
            validate_z_route_geometry(tampered, contract=CONTRACT)
        with self.assertRaises(ObservationConstructionError):
            _z_geometry(corridor_b_public_ref="corridor:A")

    def test_geometry_tuned_after_results_is_refused(self):
        geometry = _z_geometry()
        tampered = dict(geometry)
        tampered["tuned_after_seeing_outcomes"] = True
        tampered["geometry_sha256"] = _sha({
            key: value for key, value in tampered.items()
            if key != "geometry_sha256"})
        with self.assertRaises(ObservationConstructionError):
            validate_z_route_geometry(tampered, contract=CONTRACT)

    def test_lengths_and_turns_must_be_whole_registered_steps(self):
        with self.assertRaises(ObservationConstructionError):
            _z_geometry(corridor_a_length_m=4.1)
        with self.assertRaises(ObservationConstructionError):
            z_route_segments(_z_geometry(turn_degrees=45.0), contract=CONTRACT)

    def test_a_geometry_over_the_place_budget_is_refused(self):
        with self.assertRaises(ObservationConstructionError) as caught:
            z_route_segments(_z_geometry(connector_length_m=6.0),
                             contract=CONTRACT)
        self.assertIn("place-layer budget", str(caught.exception))


class ZRouteBuildTests(unittest.TestCase):
    def test_builds_a_sealed_place_layer_route(self):
        result = _build_z()
        plan = result["route_plan"]
        self.assertEqual(plan["family_layer"], "place")
        self.assertEqual(len(plan["registered_actions"]), 64)
        self.assertEqual(plan, validate_route_plan(plan, contract=CONTRACT))
        phases = plan["phase_observation_indices"]
        self.assertLess(max(phases["precondition_visible"]),
                        min(phases["challenge_hidden"]))
        self.assertLess(max(phases["challenge_hidden"]),
                        min(phases["reobserved"]))
        self.assertIsNone(plan["intervention_after_observation_index"])

    def test_the_receipt_records_the_ambiguous_window_and_disambiguation(self):
        receipt = _build_z()["z_route_receipt"]
        self.assertTrue(receipt["ambiguous_commitment_observation_indices"])
        self.assertTrue(receipt["later_disambiguation_observation_indices"])
        self.assertEqual(receipt["distinguishing_public_ref"],
                         "landmark:doorway-A")
        self.assertTrue(receipt["registered_turns"]["turns_are_opposite"])
        self.assertFalse(receipt["failed_route_replacement_allowed"])
        self.assertEqual(receipt["registered_action_count"], 64)

    def test_corridor_b_must_be_observed_while_the_anchor_is_hidden(self):
        with self.assertRaises(ObservationConstructionError) as caught:
            _build_z(row_options={"corridor_b_state": "visible"})
        self.assertIn("ambiguous commitment", str(caught.exception))

    def test_a_scan_pose_off_the_planned_pose_is_refused(self):
        with self.assertRaises(ObservationConstructionError) as caught:
            _build_z(row_options={"pose_shift": (5, 0.5)})
        self.assertIn("planned pose", str(caught.exception))

    def test_only_registered_place_programs_may_build_a_z_route(self):
        self.assertEqual(registered_place_programs(CONTRACT),
                         frozenset({"BIND", "BIRTH", "MERGE", "SPLIT"}))
        with self.assertRaises(ObservationConstructionError):
            _build_z(program="RELINK")

    def test_place_split_and_merge_need_a_pre_registered_artifact_plan(self):
        with self.assertRaises(ObservationConstructionError) as caught:
            _build_z(program="MERGE")
        self.assertIn("artifact", str(caught.exception))

    def test_an_incomplete_public_scan_is_refused(self):
        geometry = _z_geometry()
        expansion = z_route_segments(geometry, contract=CONTRACT)
        initial = {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0, "yaw_deg": 0.0}
        planned = nominal_route_poses(
            initial, expansion["registered_action_names"], contract=CONTRACT)
        rows = _z_scan_rows(planned, expansion["segments"])
        with self.assertRaises(ObservationConstructionError):
            _build_z(rows=rows[:-1])

    def test_the_public_projection_still_carries_no_world_anchor(self):
        plan = _build_z()["route_plan"]
        projection = public_route_projection(plan, contract=CONTRACT)
        self.assertNotIn("initial_pose", projection)
        self.assertNotIn("planned_poses", projection)
        self.assertTrue(projection["world_pose_excluded"])
        self.assertEqual(projection["family_layer"], "place")


class LayeredBudgetTests(unittest.TestCase):
    """The entity builder must read the layered budget, not the flat cap."""

    def test_place_layer_accepts_a_route_the_entity_cap_refuses(self):
        scans, edges = _chain_graph(hidden_steps=24)
        arguments = {
            "episode_id": "episode:long",
            "program": "BIND",
            "branch_type": "out_of_view_then_reobservation",
            "visibility_subject_public_ref": "subject:0001",
            "visibility_subject_seal_sha256": SUBJECT_SHA,
            "visibility_builder_config_sha256": CONFIG_SHA,
            "pose_scans": scans,
            "edges": edges,
            "split_merge_artifact_plan": None,
            "contract": CONTRACT,
        }
        with self.assertRaises(ObservationConstructionError):
            build_route_plan_from_public_graph(
                family_layer="entity", **arguments)
        plan = build_route_plan_from_public_graph(
            family_layer="place", **arguments)
        self.assertGreater(len(plan["registered_actions"]), 24)
        self.assertEqual(plan["family_layer"], "place")

    def test_a_scanned_pose_off_the_reachable_grid_is_refused(self):
        scans, edges = _chain_graph(hidden_steps=2)
        poses = [scan["pose"] for scan in scans]
        scan = seal_public_reachable_scan(
            house_id="house:001",
            raw_positions=_grid_positions(poses, drop=((0.5, 0.0),)),
            contract=CONTRACT)
        with self.assertRaises(ObservationConstructionError) as caught:
            build_route_plan_from_public_graph(
                episode_id="episode:grid", program="BIND",
                branch_type="out_of_view_then_reobservation",
                visibility_subject_public_ref="subject:0001",
                visibility_subject_seal_sha256=SUBJECT_SHA,
                visibility_builder_config_sha256=CONFIG_SHA,
                pose_scans=scans, edges=edges,
                split_merge_artifact_plan=None, contract=CONTRACT,
                reachable_scan=scan)
        self.assertIn("reachable cell", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
