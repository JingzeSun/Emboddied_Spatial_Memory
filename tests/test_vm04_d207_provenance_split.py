"""Checks for the D-207 per-layer route budget and provenance channel split.

The deployment-readable invariant here is the one the existing anti-leak test
cannot reach.  That test mutates private, reference or future data and requires
the public bytes to stay identical; a file that already sits on the public side
does not change under that mutation, so the directory invariant is checked
directly instead.
"""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PATH = ROOT / "ops" / "vsmt" / "vm04_multiview_raw.py"
SPEC = importlib.util.spec_from_file_location("vm04_multiview_raw_d207", PATH)
raw = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(raw)

from tests.test_vm04_multiview_worker import CONTRACT, Event, _plan  # noqa: E402
from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    public_route_projection,
    validate_approved_contract,
    validate_route_plan,
)


V3 = ROOT / "configs/vsmt/vm04_observation_suitability_v3.json"
V4 = ROOT / "configs/vsmt/vm04_observation_suitability_v4.json"
V3_SHA256 = "31d2e156b8a4c1ca39837aadc004c804a3e016e0bf9d55c0d211f96054130723"

# A distinctive world pose so a leak is unambiguous in the byte scan.
WORLD_X = 7.25
WORLD_YAW = 42.5


class D207ContractTests(unittest.TestCase):
    def setUp(self):
        self.v3 = json.loads(V3.read_text(encoding="utf-8"))
        self.v4 = json.loads(V4.read_text(encoding="utf-8"))

    def test_v3_bytes_are_untouched(self):
        self.assertEqual(hashlib.sha256(V3.read_bytes()).hexdigest(), V3_SHA256)
        self.assertEqual(self.v4["derived_from"]["source_config_sha256"],
                         V3_SHA256)

    def test_entity_budget_is_the_unchanged_d182_value(self):
        frozen = self.v4["observation_trajectory"]["frozen_numeric_values"]
        by_layer = self.v4["observation_trajectory"][
            "maximum_route_steps_by_family_layer"]
        self.assertEqual(frozen["maximum_route_steps"], 24)
        self.assertEqual(by_layer["entity"], 24)
        self.assertEqual(by_layer["place"], 64)
        self.assertEqual(self.v3["observation_trajectory"][
            "frozen_numeric_values"], frozen)

    def test_place_budget_covers_the_z_route(self):
        z_route = self.v4["place_identity_revision"]["z_route_family"]
        by_layer = self.v4["observation_trajectory"][
            "maximum_route_steps_by_family_layer"]
        self.assertLessEqual(z_route["approximate_actions_required"],
                             by_layer["place"])
        self.assertGreater(z_route["approximate_actions_required"],
                           by_layer["entity"],
                           "the Z route must be the reason the budget rose")

    def test_entity_budget_may_not_be_raised_through_the_layer_table(self):
        raised = copy.deepcopy(self.v4)
        raised["observation_trajectory"][
            "maximum_route_steps_by_family_layer"]["entity"] = 64
        contract = validate_approved_contract(raised)
        plan = _plan()
        plan["registered_actions"] = [
            {"step_index": index, "action": "MoveAhead"} for index in range(30)
        ]
        with self.assertRaises(ObservationConstructionError):
            validate_route_plan(plan, contract=contract)

    def test_budgets_are_not_adjustable_after_results(self):
        rationale = self.v4["observation_trajectory"][
            "route_step_budget_rationale"]
        self.assertFalse(rationale["budgets_may_be_raised_after_seeing_results"])
        self.assertFalse(rationale["tolerances_may_not_be_relaxed_to_raise_yield"])


class RouteBudgetByLayerTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(V4.read_text(encoding="utf-8"))

    def _plan_with(self, *, layer, steps):
        plan = _plan()
        plan["family_layer"] = layer
        plan["registered_actions"] = [
            {"step_index": index, "action": "MoveAhead"} for index in range(steps)
        ]
        plan.pop("route_plan_sha256")
        from cpmt.hashing import canonical_json
        plan["route_plan_sha256"] = hashlib.sha256(
            canonical_json(plan).encode("utf-8")).hexdigest()
        return plan

    def test_entity_layer_rejects_a_place_length_route(self):
        with self.assertRaises(ObservationConstructionError):
            validate_route_plan(self._plan_with(layer="entity", steps=50),
                                contract=self.contract)

    def test_place_layer_accepts_the_z_route_length(self):
        route = validate_route_plan(self._plan_with(layer="place", steps=50),
                                    contract=self.contract)
        self.assertEqual(len(route["registered_actions"]), 50)

    def test_place_layer_still_has_a_ceiling(self):
        with self.assertRaises(ObservationConstructionError):
            validate_route_plan(self._plan_with(layer="place", steps=65),
                                contract=self.contract)

    def test_unregistered_family_layer_is_rejected(self):
        with self.assertRaises(ObservationConstructionError):
            validate_route_plan(self._plan_with(layer="room", steps=4),
                                contract=self.contract)


class ProvenanceSplitTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(V4.read_text(encoding="utf-8"))

    def test_public_projection_carries_no_world_pose(self):
        public = public_route_projection(_plan(), contract=self.contract)
        self.assertNotIn("initial_pose", public)
        self.assertNotIn("planned_poses", public)
        self.assertTrue(public["world_pose_excluded"])
        self.assertEqual(public["consumer_scope"],
                         "construction_provenance_only_not_adapter_input")

    def test_private_plan_keeps_the_world_poses_acceptance_needs(self):
        route = validate_route_plan(_plan(), contract=self.contract)
        self.assertIn("initial_pose", route)
        self.assertIn("planned_poses", route)

    def test_route_is_written_to_provenance_not_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            store = raw.RawEpisodeStore(
                episode, plan=_plan(), contract=CONTRACT)
            store.extract_public_frame(Event((WORLD_X, WORLD_YAW)), 0)
            self.assertTrue((episode / "provenance/route.json").is_file())
            self.assertFalse((episode / "public/route.json").exists())

    def test_deployment_readable_bytes_carry_no_world_pose_or_phase_structure(self):
        """The invariant the private-mutation leak test is structurally blind to."""

        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            store = raw.RawEpisodeStore(
                episode, plan=_plan(), contract=CONTRACT)
            for index in range(2):
                store.extract_public_frame(
                    Event((WORLD_X, WORLD_YAW)), index)

            public_bytes = b"".join(
                path.read_bytes() for path in (episode / "public").rglob("*")
                if path.is_file()
            )
            for leaked in (str(WORLD_X).encode(), str(WORLD_YAW).encode()):
                self.assertNotIn(leaked, public_bytes,
                                 "a world pose value reached public/")
            for structure in (b"phase_observation_indices", b"challenge_hidden",
                              b"precondition_visible", b"branch_type",
                              b"visibility_subject_public_ref"):
                self.assertNotIn(structure, public_bytes,
                                 "episode phase structure reached public/")

            provenance_bytes = (
                episode / "provenance/route.json").read_bytes()
            self.assertIn(b"phase_observation_indices", provenance_bytes)
            self.assertNotIn(str(WORLD_X).encode(), provenance_bytes,
                             "even provenance should not carry the world pose")

    def test_private_side_still_holds_the_world_truth(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            store = raw.RawEpisodeStore(
                episode, plan=_plan(), contract=CONTRACT)
            store.extract_public_frame(Event((WORLD_X, WORLD_YAW)), 0)
            truth = json.loads(
                (episode / "private/raw/frame_0000/camera_truth.json")
                .read_text(encoding="utf-8"))
            self.assertEqual(truth["world_pose"]["position_m"][0], WORLD_X)
            self.assertEqual(truth["world_pose"]["yaw_deg"], WORLD_YAW)
            self.assertEqual(
                truth["role"],
                "post_seal_evaluation_only_never_a_deployment_input")


if __name__ == "__main__":
    unittest.main()
