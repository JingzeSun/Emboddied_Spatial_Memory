"""D-224 / S1-02: the dry-run revert must leave the world where it found it.

S0-02 says a failed revert fails the house.  Checking ``lastActionSuccess`` did not implement
that: in the 4bff1a8 run ``TeleportObject`` reported success while leaving objects 0.05 m to
10.9 m away (eggs that crack, objects ejected by a collider), in three episodes that were then
recorded as successes (LOG-239).  Ruling 34 made this load bearing -- a control container's whole
job is to prove that nothing moved -- so the revert is verified against the real pose here.

No simulator is started: the controller is a fake that replays a scripted sequence of poses.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02a_pilot as runner  # noqa: E402


ORIGIN = {"x": 1.0, "y": 0.9, "z": 2.0}
ROTATION = {"x": 0.0, "y": 0.0, "z": 0.0}


class FakeEvent:
    def __init__(self, metadata):
        self.metadata = metadata


class FakeController:
    """Replays a scripted list of (action_success, resulting position) for TeleportObject.

    白话：假控制器不启动模拟器，只按脚本回答"这次放回报告成功没有、物体最后停在哪"。
    它让"报告成功但其实没放回"这种情况可以在本地复现。
    """

    def __init__(self, script, object_id="Egg|1"):
        self.script = list(script)
        self.object_id = object_id
        self.position = dict(ORIGIN)
        self.calls: list[dict] = []
        self.last_event = self._event()

    def _event(self, success=True, error=""):
        return FakeEvent({"lastActionSuccess": success, "errorMessage": error,
                          "objects": [{"objectId": self.object_id, "position": dict(self.position),
                                       "rotation": dict(ROTATION)}]})

    def step(self, **kwargs):
        self.calls.append(dict(kwargs))
        if kwargs.get("action") == "TeleportObject":
            success, position = self.script.pop(0)
            self.position = dict(position)
            self.last_event = self._event(success)
        else:                      # Pass, or anything else: the world does not move
            self.last_event = self._event(True)
        return self.last_event


class TestRevertVerification(unittest.TestCase):
    def test_a_clean_revert_needs_one_teleport(self) -> None:
        c = FakeController([(True, ORIGIN)])
        out = runner._revert_object(c, "Egg|1", ORIGIN, ROTATION)
        self.assertTrue(out["ok"])
        self.assertEqual(out["drift_m"], 0.0)
        self.assertEqual(len(out["attempts"]), 1)
        self.assertFalse(out["attempts"][0]["force_kinematic"])

    def test_success_with_the_object_elsewhere_is_a_failed_revert(self) -> None:
        """The exact 4bff1a8 signature: the action reports success, the object is metres away."""
        far = {"x": 11.9, "y": 0.9, "z": 2.0}
        c = FakeController([(True, far), (True, far)])
        out = runner._revert_object(c, "Egg|1", ORIGIN, ROTATION)
        self.assertFalse(out["ok"])
        self.assertAlmostEqual(out["drift_m"], 10.9, places=3)
        self.assertEqual(len(out["attempts"]), 2)
        self.assertTrue(all(a["action_success"] for a in out["attempts"]))

    def test_the_kinematic_retry_is_what_recovers_a_settled_object(self) -> None:
        settled = {"x": 1.06, "y": 0.9, "z": 2.0}     # 6 cm off, as physics leaves it
        c = FakeController([(True, settled), (True, ORIGIN)])
        out = runner._revert_object(c, "Egg|1", ORIGIN, ROTATION)
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["attempts"]), 2)
        self.assertTrue(out["attempts"][1]["force_kinematic"])
        self.assertTrue(any(call.get("action") == "Pass" for call in c.calls))

    def test_the_tolerance_is_a_centimetre(self) -> None:
        self.assertEqual(runner.REVERT_TOLERANCE_M, 0.01)
        inside = {"x": ORIGIN["x"] + 0.009, "y": 0.9, "z": 2.0}
        self.assertTrue(runner._revert_object(FakeController([(True, inside)]), "Egg|1", ORIGIN, ROTATION)["ok"])
        outside = {"x": ORIGIN["x"] + 0.011, "y": 0.9, "z": 2.0}
        out = runner._revert_object(FakeController([(True, outside), (True, outside)]), "Egg|1", ORIGIN, ROTATION)
        self.assertFalse(out["ok"])

    def test_an_object_that_no_longer_exists_is_a_failed_revert(self) -> None:
        """An egg that cracks becomes another object; its id stops resolving and that is not 'back'."""
        c = FakeController([(True, ORIGIN), (True, ORIGIN)], object_id="Egg|1")
        c.object_id = "EggCracked|1"
        out = runner._revert_object(c, "Egg|1", ORIGIN, ROTATION)
        self.assertFalse(out["ok"])
        self.assertIsNone(out["drift_m"])

    def test_distance_helpers_handle_a_missing_object(self) -> None:
        self.assertIsNone(runner._distance(None, ORIGIN))
        self.assertIsNone(runner._distance(ORIGIN, None))
        self.assertAlmostEqual(runner._distance(ORIGIN, {"x": 1.0, "y": 0.9, "z": 2.5}), 0.5)


class TestFloorIsNotAContainer(unittest.TestCase):
    """AI2-THOR flags the room floor as a receptacle; its 'viewpoint' is the middle of the house."""

    def test_floor_is_excluded_and_real_receptacles_are_kept(self) -> None:
        meta = {"objects": [
            {"objectId": "Floor|+00.00|+00.00|+00.00", "objectType": "Floor", "receptacle": True,
             "pickupable": False, "position": {"x": 0.0, "y": 0.0, "z": 0.0}},
            {"objectId": "Dresser|2|1", "objectType": "Dresser", "receptacle": True, "pickupable": False,
             "position": {"x": 1.0, "y": 0.5, "z": 2.0}},
            {"objectId": "Mug|1", "objectType": "Mug", "receptacle": True, "pickupable": True,
             "position": {"x": 1.0, "y": 0.9, "z": 2.0}},
        ]}
        out = runner._containers(meta)
        self.assertEqual(sorted(out), ["Dresser|2|1"])


if __name__ == "__main__":
    unittest.main()
