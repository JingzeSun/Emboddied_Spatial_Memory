"""Pending ruling 53 probe: the optional window segment walked after the transition.

A fake grid controller stands in for AI2-THOR: MoveAhead succeeds when the next cell is reachable
and the edge is not blocked, turns and looks always succeed, every step yields an empty frame.  The
tests pin the three things the estimate depends on: the segment is exactly L actions long, a replan
around a blocked edge does not extend it, and reaching the farthest cell before L fails the house
instead of shortening the window.  No simulator, no episode root outside a temporary directory.
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02a_pilot as runner  # noqa: E402
from vsmt import lean_route  # noqa: E402

GRID = lean_route.GRID_M


class _Event:
    def __init__(self, meta: dict) -> None:
        self.metadata = meta
        self.frame = np.zeros((runner.HEIGHT, runner.WIDTH, 3), dtype=np.uint8)
        self.depth_frame = np.ones((runner.HEIGHT, runner.WIDTH), dtype=np.float32)
        self.instance_masks: dict = {}


class FakeGridController:
    """Moves on integer cells; rejects a MoveAhead across a blocked edge or off the grid (once per edge)."""

    def __init__(self, cells: set, start: tuple[int, int], yaw: int, reject_edges: set | None = None) -> None:
        self.cells, self.cell, self.yaw, self.horizon = cells, start, yaw, 30
        self.reject_edges = set(reject_edges or set())
        self.rejected: list = []
        self.last_event = _Event(self._meta(True, ""))

    def _meta(self, ok: bool, msg: str) -> dict:
        x, z = self.cell[0] * GRID, self.cell[1] * GRID
        return {"agent": {"position": {"x": x, "y": 0.9, "z": z}, "rotation": {"x": 0, "y": self.yaw, "z": 0},
                          "cameraHorizon": self.horizon},
                "cameraPosition": {"x": x, "y": 1.5, "z": z}, "objects": [], "lastActionSuccess": ok, "errorMessage": msg}

    def step(self, action: str, **_: object) -> _Event:
        ok, msg = True, ""
        if action == "MoveAhead":
            dx, dz = lean_route._HEADING[self.yaw]
            nxt = (self.cell[0] + dx, self.cell[1] + dz)
            e = lean_route.edge(self.cell, nxt)
            if nxt not in self.cells or e in self.reject_edges:
                ok, msg = False, "blocked by fake wall"
                self.reject_edges.discard(e)
                self.rejected.append(e)
            else:
                self.cell = nxt
        elif action == "RotateRight":
            self.yaw = (self.yaw + 90) % 360
        elif action == "RotateLeft":
            self.yaw = (self.yaw - 90) % 360
        elif action == "LookDown":
            self.horizon += 30
        elif action == "LookUp":
            self.horizon -= 30
        else:
            raise AssertionError(action)
        self.last_event = _Event(self._meta(ok, msg))
        return self.last_event


def _yaw_for(heading: tuple[int, int]) -> int:
    return next(y for y, h in lean_route._HEADING.items() if tuple(h) == heading)


class TestWindowSegment(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "episode"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _episode(self, controller: FakeGridController) -> runner.Episode:
        ep = runner.Episode("fake-house", self.out, {})
        ep.capture(controller.last_event, None)
        return ep

    def test_farthest_cell_respects_the_blocklist(self) -> None:
        cells = {(x, 0) for x in range(4)}
        self.assertEqual(runner._farthest_cell(cells, (0, 0), set()), (3, 0))
        self.assertEqual(runner._farthest_cell(cells, (0, 0), {lean_route.edge((2, 0), (3, 0))}), (2, 0))

    def test_segment_is_exactly_L_actions_and_U_range_matches(self) -> None:
        cells = {(x, 0) for x in range(12)}
        ctl = FakeGridController(cells, (0, 0), _yaw_for((1, 0)))
        ep = self._episode(ctl)
        rec = runner._walk_window_segment(ctl, ep, cells, set(), [], frames=4, replan_on=True)
        self.assertEqual(rec["frames_walked"], 4)
        self.assertEqual(rec["segment"], [0, 4])
        self.assertEqual(rec["target_cell"], [11, 0])
        self.assertEqual(rec["path_actions_available"], 11)
        self.assertEqual(ctl.cell, (4, 0))
        self.assertEqual(len(ep.actions_done), 5)  # the initial capture plus 4 actions
        self.assertTrue((self.out / "provenance" / "window_segment.json").exists())

    def test_a_replan_does_not_extend_the_segment(self) -> None:
        cells = {(x, z) for x in range(12) for z in (0, 1)}
        # block the third edge of the path the planner will actually take, so the replan is forced
        target = runner._farthest_cell(cells, (0, 0), set())
        path = lean_route.bfs_path(cells, (0, 0), target)
        wall = lean_route.edge(path[2], path[3])
        ctl = FakeGridController(cells, (0, 0), _yaw_for((1, 0)), reject_edges={wall})
        ep = self._episode(ctl)
        blocked: set = set()
        replans: list = []
        rec = runner._walk_window_segment(ctl, ep, cells, blocked, replans, frames=6, replan_on=True)
        self.assertEqual(len(replans), 1)
        self.assertEqual(rec["frames_walked"], 6)          # the rejected MoveAhead counts as a frame too
        self.assertEqual(rec["segment"][1] - rec["segment"][0], 6)
        self.assertIn(wall, blocked)
        self.assertEqual(ctl.rejected, [wall])

    def test_reaching_the_farthest_cell_early_fails_instead_of_shortening(self) -> None:
        cells = {(x, 0) for x in range(6)}
        ctl = FakeGridController(cells, (0, 0), _yaw_for((1, 0)))
        ep = self._episode(ctl)
        with self.assertRaises(runner.PilotFailure) as caught:
            runner._walk_window_segment(ctl, ep, cells, set(), [], frames=20, replan_on=True)
        self.assertEqual(caught.exception.reason, "intervention_window_unavailable")
        self.assertIn("5 < 20", caught.exception.detail)
        self.assertIn("5 actions", caught.exception.detail)
        self.assertTrue((self.out / "provenance" / "window_segment.json").exists())

    def test_tail_window_is_the_last_L_frames_and_the_leave_segment_precedes_it(self) -> None:
        leave, window = runner._tail_window([10, 70], 40)
        self.assertEqual(window, [30, 70])
        self.assertEqual(leave, [10, 30])
        leave, window = runner._tail_window([10, 50], 40)   # exactly L: an empty leave segment is allowed
        self.assertEqual((leave, window), ([10, 10], [10, 50]))

    def test_tail_window_fails_a_short_transition_instead_of_shortening(self) -> None:
        with self.assertRaises(runner.PilotFailure) as caught:
            runner._tail_window([10, 36], 40)
        self.assertEqual(caught.exception.reason, "intervention_window_unavailable")
        self.assertIn("26 < 40", caught.exception.detail)

    def test_resolve_window_is_ruling_53_by_default_and_keeps_old_roots_replayable(self) -> None:
        self.assertEqual(runner._resolve_window({}), ("transition_tail", 30))
        self.assertEqual(runner._resolve_window({"window_mode": "transition_tail", "window_segment_frames": 30}), ("transition_tail", 30))
        self.assertEqual(runner._resolve_window({"window_segment_frames": 40}), ("u_turn", 40))   # first probe root f2982a6
        self.assertEqual(runner._resolve_window({"window_mode": "whole_transition", "window_segment_frames": 30}), ("whole_transition", 0))
        with self.assertRaises(runner.PilotFailure):
            runner._resolve_window({"window_mode": "transition_tail", "window_segment_frames": 0})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
