"""Artificial pixel values only; no rendering or physical-success evidence."""
from copy import deepcopy
import unittest

from r4_examples_v2 import public as source
from test_r4_families_v2 import inputs
from spatial_world_model.r4_families_v2 import manifest, family_config, ACTIONS, NAMES
from spatial_world_model.r4_public_v2 import make_public, model_input, validate_public, audit_family
from spatial_world_model.r4_query_v2 import from_public_query, model_features


def fixture():
    proposal, base = inputs()
    config = family_config(base, manifest(proposal)["rows"][0])
    history = source(range(121))["history"]
    for row in history:
        row["camera_position_m"][0] = config["observation"]["camera_x_m"]
    return make_public(history, config), config


class R4PublicV2Tests(unittest.TestCase):
    def test_anonymous_nine_slots_reach_native_recent_query(self):
        public, _ = fixture()
        self.assertIsInstance(public["actions"], list)
        for i in range(9):
            selected = model_input(public, i, history_mode="recent")
            self.assertEqual(selected["controls"], public["actions"][i])
            query = from_public_query(selected, history_mode="recent")
            features = model_features(query, history_mode="recent")
            self.assertEqual(set(features), {"history", "controls", "goal", "domain_spec"})
            self.assertEqual(len(features["history"]["rgb"][0]), 19200)

    def test_old_version_ids_duplicate_and_bad_pixels_rejected(self):
        public, _ = fixture()
        for change in (lambda p: p.update(schema_version="spatial-history-two-gate-public-v1"),
                       lambda p: p.update(family_id="r4-39"),
                       lambda p: p["actions"].__setitem__(8, p["actions"][0]),
                       lambda p: p["history"][0]["rgb"].__setitem__(0, 256)):
            bad = deepcopy(public); change(bad)
            with self.assertRaises(ValueError):
                validate_public(bad)

    def test_ninth_candidate_is_in_information_cost_denominator(self):
        public, config = fixture()
        worlds = {w: public for w in NAMES}
        outcomes = {w: {a: a == "c22" for a in ACTIONS} for w in NAMES}
        audit = audit_family(worlds, outcomes, config)
        self.assertEqual(audit["minimum_information_regret"], 0)
        self.assertFalse(audit["accepted"])
        self.assertTrue(audit["checks"]["each_world_has_success"])
        self.assertEqual(len(audit["frame_information"][0]["equivalence_groups"][0]["action_expected_failure_cost"]), 9)

    def test_all_worlds_and_fixed_frames_remain_in_information_audit(self):
        public, config = fixture()
        worlds = {w: public for w in NAMES}
        outcomes = {w: {a: i == j for i, a in enumerate(ACTIONS)} for j, w in enumerate(NAMES)}
        audit = audit_family(worlds, outcomes, config)
        self.assertEqual(len(audit["frame_information"]), 121)
        self.assertEqual(audit["minimum_information_regret"], .75)
        outcomes["LL"] = {a: False for a in ACTIONS}
        audit = audit_family(worlds, outcomes, config)
        self.assertFalse(audit["checks"]["each_world_has_success"])
        self.assertFalse(audit["accepted"])

    def test_reordered_candidates_fail_registered_audit(self):
        public, config = fixture()
        swapped = deepcopy(public)
        swapped["actions"][0], swapped["actions"][8] = swapped["actions"][8], swapped["actions"][0]
        outcomes = {w: {a: i == j for i, a in enumerate(ACTIONS)} for j, w in enumerate(NAMES)}
        audit = audit_family({w: swapped for w in NAMES}, outcomes, config)
        self.assertFalse(audit["checks"]["registered_common_actions"])
