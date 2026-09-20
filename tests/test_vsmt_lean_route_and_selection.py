"""D-224 / S1-02 R1 and I1: the pure planner and selector.

Determinism, the registered exclusions (no strafing, no local search, no
sequential resampling, no new seed) and the failure modes (cap hit raises,
no admissible viewpoint raises) are pinned here.  No simulator is started.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_interventions as sel  # noqa: E402
from vsmt import lean_route as rt  # noqa: E402


def open_room(width: int = 12, depth: int = 12) -> list[dict[str, float]]:
    return [{"x": ix * 0.25, "y": 0.95, "z": iz * 0.25} for ix in range(width) for iz in range(depth)]


START = {"position": {"x": 0.0, "y": 0.95, "z": 0.0}, "rotation": {"x": 0, "y": 0, "z": 0}, "horizon": 0}
CAM = 1.576


class TestGridAndPaths(unittest.TestCase):
    def test_snap_and_cells(self) -> None:
        cells = rt.reachable_cells(open_room(3, 2))
        self.assertEqual(cells, {(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)})

    def test_bfs_is_shortest_and_deterministic(self) -> None:
        cells = rt.reachable_cells(open_room())
        a = rt.bfs_path(cells, (0, 0), (3, 4))
        b = rt.bfs_path(cells, (0, 0), (3, 4))
        self.assertEqual(a, b)
        self.assertEqual(len(a) - 1, 7)

    def test_bfs_refuses_an_unreachable_goal(self) -> None:
        cells = rt.reachable_cells(open_room(4, 4)) - {(1, 0), (1, 1), (1, 2), (1, 3)}
        with self.assertRaises(rt.LeanRouteError):
            rt.bfs_path(cells, (0, 0), (3, 3))

    def test_encoding_never_strafes(self) -> None:
        actions, yaw = rt.encode_path([(0, 0), (1, 0), (1, 1), (0, 1)], 0)
        self.assertFalse({"MoveLeft", "MoveRight", "MoveBack"} & set(actions))
        self.assertEqual(actions.count("MoveAhead"), 3)
        self.assertEqual(yaw, 270)

    def test_turns_are_minimal(self) -> None:
        self.assertEqual(rt.turn_actions(0, 90), ["RotateRight"])
        self.assertEqual(rt.turn_actions(0, 270), ["RotateLeft"])
        self.assertEqual(rt.turn_actions(90, 270), ["RotateRight", "RotateRight"])
        self.assertEqual(rt.look_actions(0, -30), ["LookUp"])
        self.assertEqual(rt.look_actions(30, -30), ["LookUp", "LookUp"])


class TestViewpoints(unittest.TestCase):
    def test_yaw_faces_the_target(self) -> None:
        self.assertEqual(rt.best_yaw(0.0, 1.0)[0], 0)
        self.assertEqual(rt.best_yaw(1.0, 0.0)[0], 90)
        self.assertEqual(rt.best_yaw(0.0, -1.0)[0], 180)
        self.assertEqual(rt.best_yaw(-1.0, 0.0)[0], 270)

    def test_pitch_options_are_the_registered_three(self) -> None:
        self.assertEqual(rt.best_pitch(-40.0)[0], 30)   # below camera -> look down
        self.assertEqual(rt.best_pitch(0.0)[0], 0)
        self.assertEqual(rt.best_pitch(25.0)[0], -30)

    def test_viewpoint_is_nearest_within_the_search_range(self) -> None:
        cells = rt.reachable_cells(open_room())
        center = {"x": 1.5, "y": 0.9, "z": 1.5}
        vp = rt.select_viewpoint(center, cells, camera_height_m=CAM)
        self.assertGreaterEqual(vp["distance_m"], 0.75)
        self.assertLessEqual(vp["distance_m"], 2.5)
        others = rt.admissible_viewpoints(center, cells, camera_height_m=CAM)
        self.assertEqual(vp["distance_m"], min(o["distance_m"] for o in others))

    def test_far_container_has_no_viewpoint(self) -> None:
        cells = rt.reachable_cells(open_room(4, 4))
        with self.assertRaises(rt.LeanRouteError):
            rt.select_viewpoint({"x": 9.0, "y": 0.9, "z": 9.0}, cells, camera_height_m=CAM)


class TestRoute(unittest.TestCase):
    def plan(self, **kw):
        containers = {"c_a": {"x": 1.0, "y": 0.9, "z": 2.0}, "c_b": {"x": 2.5, "y": 0.9, "z": 0.5}}
        return rt.plan_route(reachable=open_room(), start_pose=START, camera_height_m=CAM,
                             containers=containers, revisit_sequence=kw.pop("revisit", ["c_a"]),
                             transition_cell=kw.pop("transition", (10, 10)), **kw)

    def test_route_is_deterministic_and_bookkept(self) -> None:
        a, b = self.plan(), self.plan()
        self.assertEqual(a, b)
        self.assertEqual(a["observation_count"], len(a["actions"]) + 1)
        s1, tr, s2 = a["segments"]["sweep_one"], a["segments"]["transition"], a["segments"]["sweep_two"]
        self.assertEqual(s1[1], tr[0])
        self.assertEqual(tr[1], s2[0])
        self.assertEqual(s2[1], len(a["actions"]))

    def test_actions_are_only_the_registered_eight(self) -> None:
        allowed = {"MoveAhead", "MoveBack", "MoveLeft", "MoveRight", "RotateLeft", "RotateRight", "LookUp", "LookDown"}
        self.assertTrue(set(self.plan()["actions"]) <= allowed)

    def test_sweep_two_only_visits_the_requested_containers(self) -> None:
        plan = self.plan(revisit=["c_b", "c_a"])
        self.assertEqual(plan["revisit_sequence"], ["c_b", "c_a"])

    def test_the_cap_raises_and_never_truncates(self) -> None:
        with self.assertRaises(rt.LeanRouteError):
            self.plan(max_actions=5)

    def test_unknown_revisit_target_is_refused(self) -> None:
        with self.assertRaises(rt.LeanRouteError):
            self.plan(revisit=["nope"])

    def test_start_off_grid_is_refused(self) -> None:
        with self.assertRaises(rt.LeanRouteError):
            rt.plan_route(reachable=open_room(), start_pose={"position": {"x": 9.0, "y": 0.95, "z": 9.0},
                                                             "rotation": {"y": 0}, "horizon": 0},
                          camera_height_m=CAM, containers={}, revisit_sequence=[])


OBJECTS = [
    {"object_id": "Mug|1", "asset_id": "Mug_1", "pickupable": True, "parent_receptacle": "Table|1"},
    {"object_id": "Book|1", "asset_id": "Book_2", "pickupable": True, "parent_receptacle": "Shelf|1"},
    {"object_id": "Sofa|1", "asset_id": "Sofa_3", "pickupable": False, "parent_receptacle": None},
    {"object_id": "Cup|1", "asset_id": "Cup_4", "pickupable": True, "parent_receptacle": "Table|1"},
]
RECEPTACLES = ["Table|1", "Shelf|1", "Counter|1"]
SEEN = {"Mug|1": 500, "Book|1": 300, "Cup|1": 40, "Sofa|1": 9000}


class TestSelection(unittest.TestCase):
    def test_eligibility_needs_pixels_and_a_receptacle(self) -> None:
        ids = [o["object_id"] for o in sel.eligible_objects(OBJECTS, SEEN)]
        self.assertEqual(ids, ["Book|1", "Mug|1"])  # Cup: 40 px; Sofa: not pickupable

    def test_feasible_set_respects_the_shared_window(self) -> None:
        elig = sel.eligible_objects(OBJECTS, SEEN)
        invisible = {"Table|1", "Counter|1"}
        f = sel.feasible_triples(elig, RECEPTACLES, invisible, {"Counter|1": True, "Table|1": True, "Shelf|1": True})
        kinds = {(t["kind"], t["object_id"], t["destination"]) for t in f}
        self.assertIn(("remove", "Mug|1", None), kinds)
        self.assertIn(("move", "Mug|1", "Counter|1"), kinds)
        self.assertNotIn(("remove", "Book|1", None), kinds)          # Shelf visible
        self.assertNotIn(("move", "Book|1", "Counter|1"), kinds)     # source visible
        self.assertIn(("add", "Book|1", "Counter|1"), kinds)         # only the destination must hide

    def test_placement_prescreen_removes_full_destinations(self) -> None:
        elig = sel.eligible_objects(OBJECTS, SEEN)
        f = sel.feasible_triples(elig, RECEPTACLES, set(RECEPTACLES), {"Counter|1": False, "Table|1": True, "Shelf|1": True})
        self.assertFalse([t for t in f if t["destination"] == "Counter|1"])

    def test_sampling_is_seeded_and_one_object_at_most_once(self) -> None:
        elig = sel.eligible_objects(OBJECTS, SEEN)
        f = sel.feasible_triples(elig, RECEPTACLES, set(RECEPTACLES), {r: True for r in RECEPTACLES})
        a = sel.sample_interventions(f, split_seed=20260920, house_id="h1")
        b = sel.sample_interventions(f, split_seed=20260920, house_id="h1")
        self.assertEqual(a, b)
        self.assertEqual(len({r["object_id"] for r in a}), len(a))
        self.assertLessEqual(len(a), 6)
        self.assertNotEqual(a, sel.sample_interventions(f, split_seed=20260921, house_id="h1"))

    def test_add_gets_a_derived_generated_id(self) -> None:
        elig = sel.eligible_objects(OBJECTS, SEEN)
        f = [t for t in sel.feasible_triples(elig, RECEPTACLES, set(RECEPTACLES), {r: True for r in RECEPTACLES}) if t["kind"] == "add"]
        rows = sel.sample_interventions(f, split_seed=1, house_id="h")
        self.assertTrue(all(r["generated_id"].startswith("dup_") for r in rows))

    def test_revisit_includes_both_ends_of_a_move(self) -> None:
        rows = [{"kind": "move", "source": "A", "destination": "B"}, {"kind": "remove", "source": "C", "destination": None}]
        seq = sel.revisit_sequence(rows, split_seed=1, house_id="h")
        self.assertEqual(set(seq), {"A", "B", "C"})
        self.assertEqual(seq, sel.revisit_sequence(rows, split_seed=1, house_id="h"))

    def test_rng_tags_are_registered_only(self) -> None:
        with self.assertRaises(sel.LeanSelectionError):
            sel.derive_rng(1, "h", "anything_else")

    def test_null_window_rate_is_about_p(self) -> None:
        hits = sum(sel.is_null_window(20260920, f"house-{i}") for i in range(2000))
        self.assertTrue(300 < hits < 500, hits)


class TestBlockedEdges(unittest.TestCase):
    def test_a_blocked_edge_forces_a_detour(self) -> None:
        cells = rt.reachable_cells(open_room(4, 4))
        direct = rt.bfs_path(cells, (0, 0), (0, 3))
        self.assertEqual(len(direct) - 1, 3)
        detour = rt.bfs_path(cells, (0, 0), (0, 3), {rt.edge((0, 1), (0, 2))})
        self.assertGreater(len(detour) - 1, 3)
        self.assertNotIn(((0, 1), (0, 2)), list(zip(detour, detour[1:])))

    def test_blocking_every_edge_raises_instead_of_guessing(self) -> None:
        cells = rt.reachable_cells(open_room(2, 2))
        blocked = {rt.edge((0, 0), (0, 1)), rt.edge((0, 0), (1, 0))}
        with self.assertRaises(rt.LeanRouteError):
            rt.bfs_path(cells, (0, 0), (1, 1), blocked)

    def test_plan_route_records_the_blocklist(self) -> None:
        containers = {"c": {"x": 1.0, "y": 0.9, "z": 2.0}}
        plan = rt.plan_route(reachable=open_room(), start_pose=START, camera_height_m=CAM, containers=containers,
                             revisit_sequence=[], blocked={rt.edge((0, 0), (0, 1))})
        self.assertEqual(plan["blocked_edges"], [[[0, 0], [0, 1]]])
        self.assertNotIn("MoveLeft", plan["actions"])


class TestStratifiedSampling(unittest.TestCase):
    """An add-dominated F, like s1-02b house 01543 (F=135, U=5)."""

    def feasible(self) -> list[dict]:
        objs = [{"object_id": f"Obj|{i}", "asset_id": "A", "pickupable": True, "parent_receptacle": "U0" if i < 3 else "V",
                 "is_agent": False, "is_structure": False} for i in range(25)]
        U = {"U0", "U1", "U2", "U3", "U4"}
        ok = {c: True for c in U | {"V"}}
        f = sel.feasible_triples(objs, sorted(U | {"V"}), U, ok)
        kinds = {k: sum(1 for t in f if t["kind"] == k) for k in ("remove", "move", "add")}
        self.assertEqual(kinds, {"remove": 3, "move": 12, "add": 125})
        return f

    def test_default_is_the_contract_stratified_draw_and_the_old_draw_is_still_replayable(self) -> None:
        f = self.feasible()
        a = sel.sample_interventions(f, split_seed=20260920, house_id="h")
        b = sel.sample_interventions(f, split_seed=20260920, house_id="h", stratify_by_kind=True, one_placement_per_destination=True)
        self.assertEqual(a, b)
        old = sel.sample_interventions(f, split_seed=20260920, house_id="h", stratify_by_kind=False, one_placement_per_destination=False)
        self.assertNotEqual(a, old)

    def test_stratified_draw_mixes_kinds_and_is_deterministic(self) -> None:
        f = self.feasible()
        s1 = sel.sample_interventions(f, split_seed=20260920, house_id="h", stratify_by_kind=True)
        s2 = sel.sample_interventions(f, split_seed=20260920, house_id="h", stratify_by_kind=True)
        self.assertEqual(s1, s2)
        self.assertEqual(len(s1), 6)
        self.assertEqual(len({r["object_id"] for r in s1}), 6)
        self.assertGreaterEqual(len({r["kind"] for r in s1}), 2)
        # over many houses, add is no longer nine tenths of the draws
        kinds = [r["kind"] for h in range(60) for r in sel.sample_interventions(f, split_seed=1, house_id=f"h{h}", stratify_by_kind=True, one_placement_per_destination=False)]
        self.assertLess(kinds.count("add") / len(kinds), 0.6)
        uniform = [r["kind"] for h in range(60) for r in sel.sample_interventions(f, split_seed=1, house_id=f"h{h}", stratify_by_kind=False, one_placement_per_destination=False)]
        self.assertGreater(uniform.count("add") / len(uniform), 0.8)

    def test_stratified_draw_never_invents_a_kind(self) -> None:
        f = [t for t in self.feasible() if t["kind"] == "add"]
        s = sel.sample_interventions(f, split_seed=3, house_id="h", stratify_by_kind=True)
        self.assertEqual({r["kind"] for r in s}, {"add"})


class TestUnseenAddSource(unittest.TestCase):
    def objects(self) -> list[dict]:
        mk = lambda i, parent, seen: ({"object_id": f"O|{i}", "asset_id": f"A{i % 3}", "pickupable": True,
                                       "parent_receptacle": parent, "is_agent": False, "is_structure": False}, seen)
        rows = [mk(0, "U0", 500), mk(1, "V", 300), mk(2, "Fridge", 0), mk(3, "Cabinet", 0), mk(4, "U1", 0)]
        self.px = {o["object_id"]: s for o, s in rows}
        return [o for o, _ in rows]

    def test_unseen_means_zero_pixels_so_far(self) -> None:
        objs = self.objects()
        self.assertEqual([o["object_id"] for o in sel.unseen_objects(objs, self.px)], ["O|2", "O|3", "O|4"])
        self.assertEqual([o["object_id"] for o in sel.eligible_objects(objs, self.px)], ["O|0", "O|1"])

    def test_add_rows_come_from_unseen_objects_and_are_real_relocations(self) -> None:
        objs = self.objects(); U = {"U0", "U1"}
        ok = {"U0": True, "U1": True, "V": True, "Fridge": True, "Cabinet": True}
        default = sel.feasible_triples(sel.eligible_objects(objs, self.px), sorted(ok), U, ok)
        self.assertEqual({t["object_id"] for t in default if t["kind"] == "add"}, {"O|0", "O|1"})
        f = sel.feasible_triples(sel.eligible_objects(objs, self.px), sorted(ok), U, ok, unseen=sel.unseen_objects(objs, self.px))
        adds = [t for t in f if t["kind"] == "add"]
        self.assertTrue(all(t["add_source"] == "unseen_existing" for t in adds))
        self.assertEqual({t["object_id"] for t in adds}, {"O|2", "O|3", "O|4"})
        self.assertTrue(all(t["destination"] in U and t["destination"] != t["source"] for t in adds))
        # O|4 already sits on U1, so its only add destination is U0
        self.assertEqual([t["destination"] for t in adds if t["object_id"] == "O|4"], ["U0"])
        # remove/move rows are unchanged by the add source
        self.assertEqual([t for t in default if t["kind"] != "add"], [t for t in f if t["kind"] != "add"])
        s = sel.sample_interventions(adds, split_seed=1, house_id="h", one_placement_per_destination=False)
        self.assertTrue(all("generated_id" not in row for row in s))


class TestDryRunPrescreen(unittest.TestCase):
    def test_pair_ok_filters_placements_and_attaches_the_point(self) -> None:
        objs = [{"object_id": "O|0", "asset_id": "A", "pickupable": True, "parent_receptacle": "U0", "is_agent": False, "is_structure": False},
                {"object_id": "O|9", "asset_id": "B", "pickupable": True, "parent_receptacle": "V", "is_agent": False, "is_structure": False}]
        px = {"O|0": 400, "O|9": 0}
        U = {"U0", "U1"}; ok = {"U0": True, "U1": True, "V": True}
        pair_ok = {("O|0", "U1"): {"point": {"x": 1, "y": 1, "z": 1}, "pixels": 250, "tries": 3}}
        f = sel.feasible_triples(sel.eligible_objects(objs, px), sorted(ok), U, ok, unseen=sel.unseen_objects(objs, px), pair_ok=pair_ok)
        kinds = sorted((t["kind"], t["object_id"], t["destination"]) for t in f)
        self.assertEqual(kinds, [("move", "O|0", "U1"), ("remove", "O|0", None)])
        mv = next(t for t in f if t["kind"] == "move")
        self.assertEqual(mv["point"], {"x": 1, "y": 1, "z": 1}); self.assertEqual(mv["verified_pixels"], 250)

    def test_one_placement_per_destination(self) -> None:
        f = [{"kind": "add", "object_id": f"O|{i}", "asset_id": "A", "source": "V", "destination": "U0", "add_source": "unseen_existing"} for i in range(5)]
        f += [{"kind": "remove", "object_id": "O|7", "asset_id": "A", "source": "U0", "destination": None}]
        s = sel.sample_interventions(f, split_seed=5, house_id="h", one_placement_per_destination=True)
        self.assertEqual(sum(1 for r in s if r["kind"] == "add"), 1)
        self.assertEqual(sum(1 for r in s if r["kind"] == "remove"), 1)
        s2 = sel.sample_interventions(f, split_seed=5, house_id="h", one_placement_per_destination=False)
        self.assertEqual(len(s2), 6)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
