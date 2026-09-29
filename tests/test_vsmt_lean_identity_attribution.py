"""D-224 / S2-05 tests: the ruling 86-0 reading of first re-observation attributions on hand-made merged v7 audits.

Objects pair by episode and intervention ordinal within a seed; only objects judged in both arms enter the 2x2 table;
VSMT-lean's failures where AssocOnly kept are filed lifecycle-side (a carrier was ever retracted, or every present
carrier is dormant/retracted), hygiene-side (carriers gone or no longer resolving) or association-side; the majority
side picks the second revision round.  CPU only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import identity_attribution_analysis as ia  # noqa: E402


def kept(ordinal):
    return {"ordinal": ordinal, "judged": True, "category": "kept", "carrier_states": ["active"], "carriers_still_resolving": 1}


def failed(ordinal, category="chose_birth", states=("retracted",), retracted=True, resolving=1):
    return {"ordinal": ordinal, "judged": True, "category": category, "carrier_states": list(states),
            "carrier_ever_retracted": retracted, "carriers_still_resolving": resolving}


def no_prior(ordinal):
    return {"ordinal": ordinal, "judged": False, "category": "no_prior_carrier", "no_prior_reason": "never_fragmented_before_move"}


def merged(records_by_episode):
    return {"schema_version": "vsmt-s2-05-node-audit-merged-v7",
            "per_episode": [{"episode_id": e, "identity_attribution": r} for e, r in records_by_episode.items()]}


class AttributionReadingTests(unittest.TestCase):
    def test_lifecycle_majority_and_common_objects_only(self) -> None:
        groups = {
            ("VSMT-lean", 7): merged({"h1": [failed(0), failed(1), kept(2), no_prior(3)],
                                      "h2": [failed(0, category="carrier_gone", states=(), retracted=False, resolving=0)]}),
            ("AssocOnly", 7): merged({"h1": [kept(0), kept(1), kept(2), kept(3)], "h2": [kept(0)]}),
        }
        out = ia.analyse(groups)
        pair = out["paired"]["VSMT-lean_vs_AssocOnly"]
        self.assertEqual(pair["pooled"], {"both_kept": 1, "only_left_kept": 0, "only_right_kept": 3, "neither": 0, "common_judged": 4})
        self.assertEqual(pair["left_failure_sides"], {"lifecycle": 2, "hygiene": 1, "association": 0})
        self.assertEqual(out["reading"]["verdict"], "round_2_targets_the_lifecycle_side")
        self.assertEqual(out["per_group"]["VSMT-lean:7"]["categories"]["no_prior_carrier"], 1)
        self.assertAlmostEqual(out["per_group"]["VSMT-lean:7"]["identity_continuity_pooled"], 0.25)

    def test_hygiene_majority_and_a_tie_goes_to_the_user(self) -> None:
        hygiene = {("VSMT-lean", 7): merged({"h1": [failed(0, "chose_other_entity", ("active",), False, 0),
                                                     failed(1, "carrier_gone", (), False, 0), failed(2, "chose_birth", ("active",), False, 1)]}),
                   ("AssocOnly", 7): merged({"h1": [kept(0), kept(1), kept(2)]})}
        self.assertEqual(ia.analyse(hygiene)["reading"]["verdict"], "round_2_targets_the_co_observation_veto")
        tie = {("VSMT-lean", 7): merged({"h1": [failed(0), failed(1, "carrier_gone", (), False, 0)]}),
               ("AssocOnly", 7): merged({"h1": [kept(0), kept(1)]})}
        self.assertEqual(ia.analyse(tie)["reading"]["verdict"], "neither_side_holds_a_majority_user_decides")


if __name__ == "__main__":
    unittest.main()
