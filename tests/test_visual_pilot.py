from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import compute_graph_hash
from cpmt.visual_pilot import (
    ENERGY_KEYS,
    assert_online_boundary,
    backproject_image_point,
    execute_visual_candidates,
    make_visual_base,
    make_visual_programs,
    online_payload,
    project_world_point,
)


WIDTH = 100
HEIGHT = 100
FOV = 90.0
OLD = {"x": 0.0, "y": 0.0, "z": 2.0}
CURRENT = {"x": 2.0, "y": 0.0, "z": 0.0}


def camera(yaw: float) -> dict[str, object]:
    return {
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": yaw, "z": 0.0},
        "horizon": 0.0,
    }


def view(
    case_id: str,
    yaw: float,
    visible: bool,
) -> dict[str, object]:
    return {
        "evidence_ref": f"obs:{case_id}:current",
        "camera": camera(yaw),
        "regions": (
            [{"center": [0.5, 0.5], "depth": 2.0}] if visible else []
        ),
    }


class VisualPilotTests(unittest.TestCase):
    def score_case(
        self,
        case_id: str,
        *,
        known_target: bool,
        old_place: str,
        current_place: str,
        geometry: dict[str, dict[str, float]],
        current: dict[str, object],
        future: list[dict[str, object]],
    ) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
        base = make_visual_base(
            case_id,
            known_target=known_target,
            old_place=old_place,
            current_place=current_place,
        )
        programs = make_visual_programs(
            case_id,
            base,
            current_place=current_place,
        )
        result = execute_visual_candidates(
            base,
            programs,
            geometry,
            current,
            future,
            width=WIDTH,
            height=HEIGHT,
            fov_degrees=FOV,
        )
        return base, result, programs

    def test_projection_respects_yaw_and_view_frustum(self) -> None:
        forward = project_world_point(
            OLD,
            camera(0.0),
            width=WIDTH,
            height=HEIGHT,
            fov_degrees=FOV,
        )
        self.assertTrue(forward["visible"])
        self.assertAlmostEqual(float(forward["u"]), 0.5)
        self.assertAlmostEqual(float(forward["v"]), 0.5)

        turned = project_world_point(
            CURRENT,
            camera(90.0),
            width=WIDTH,
            height=HEIGHT,
            fov_degrees=FOV,
        )
        self.assertTrue(turned["visible"])
        self.assertAlmostEqual(float(turned["u"]), 0.5)
        self.assertFalse(
            project_world_point(
                OLD,
                camera(180.0),
                width=WIDTH,
                height=HEIGHT,
                fov_degrees=FOV,
            )["visible"]
        )

        recovered = backproject_image_point(
            [forward["u"], forward["v"]],
            float(forward["depth"]),
            camera(0.0),
            width=WIDTH,
            height=HEIGHT,
            fov_degrees=FOV,
        )
        self.assertAlmostEqual(recovered["x"], OLD["x"])
        self.assertAlmostEqual(recovered["y"], OLD["y"])
        self.assertAlmostEqual(recovered["z"], OLD["z"])

    def test_three_cases_execute_from_one_base_and_rank_expected_edit(self) -> None:
        cases = [
            (
                "reappearance",
                True,
                "place-old",
                "place-old",
                {"place-old": OLD},
                view("reappearance", 0.0, True),
                [view("reappearance", 0.0, True)],
                "BIND",
            ),
            (
                "first-reveal",
                False,
                "place-current",
                "place-current",
                {"place-current": OLD},
                view("first-reveal", 0.0, True),
                [view("first-reveal", 0.0, True)],
                "BIRTH",
            ),
            (
                "relocation-revisit",
                True,
                "place-old",
                "place-current",
                {"place-old": OLD, "place-current": CURRENT},
                view("relocation-revisit", 90.0, True),
                [
                    view("relocation-revisit", 0.0, False),
                    view("relocation-revisit", 90.0, True),
                ],
                "RELINK",
            ),
        ]
        for (
            case_id,
            known,
            old_place,
            current_place,
            geometry,
            current,
            future,
            expected,
        ) in cases:
            with self.subTest(case=case_id):
                base, result, _ = self.score_case(
                    case_id,
                    known_target=known,
                    old_place=old_place,
                    current_place=current_place,
                    geometry=geometry,
                    current=current,
                    future=future,
                )
                self.assertEqual(result["winner"], expected)
                self.assertEqual(compute_graph_hash(base), result["base_graph_hash"])
                self.assertTrue(
                    all(
                        rollout["base_graph_hash"] == result["base_graph_hash"]
                        for rollout in result["rollouts"]
                    )
                )
                self.assertTrue(
                    all(
                        tuple(rollout["energy"].keys()) == ENERGY_KEYS
                        for rollout in result["rollouts"]
                    )
                )

    def test_first_reveal_retains_illegal_candidates(self) -> None:
        _, result, _ = self.score_case(
            "first-reveal",
            known_target=False,
            old_place="place-current",
            current_place="place-current",
            geometry={"place-current": OLD},
            current=view("first-reveal", 0.0, True),
            future=[view("first-reveal", 0.0, True)],
        )
        by_template = {
            rollout["template"]: rollout for rollout in result["rollouts"]
        }
        self.assertEqual(by_template["BIND"]["status"], "illegal")
        self.assertEqual(by_template["BIND"]["energy"]["illegal"], 1.0)
        self.assertEqual(by_template["RELINK"]["status"], "illegal")
        self.assertEqual(by_template["BIRTH"]["status"], "executed")

    def test_base_is_immutable(self) -> None:
        base = make_visual_base(
            "relocation-revisit",
            known_target=True,
            old_place="place-old",
            current_place="place-current",
        )
        before = deepcopy(base)
        execute_visual_candidates(
            base,
            make_visual_programs(
                "relocation-revisit", base, current_place="place-current"
            ),
            {"place-old": OLD, "place-current": CURRENT},
            view("relocation-revisit", 90.0, True),
            [view("relocation-revisit", 0.0, False)],
            width=WIDTH,
            height=HEIGHT,
            fov_degrees=FOV,
        )
        self.assertEqual(base, before)

    def test_online_payload_has_no_future_or_audit_identifiers(self) -> None:
        base = make_visual_base(
            "reappearance",
            known_target=True,
            old_place="place-old",
            current_place="place-old",
        )
        programs = make_visual_programs(
            "reappearance", base, current_place="place-old"
        )
        payload = online_payload(
            "reappearance",
            base,
            programs,
            view("reappearance", 0.0, True),
            {"place-old": OLD},
        )
        assert_online_boundary(payload)
        for forbidden in (
            {"future_views": []},
            {"nested": {"teacher_score": 1.0}},
            {"target_object_id": "simulator-id"},
        ):
            with self.assertRaises(ValueError):
                assert_online_boundary(forbidden)


if __name__ == "__main__":
    unittest.main()
