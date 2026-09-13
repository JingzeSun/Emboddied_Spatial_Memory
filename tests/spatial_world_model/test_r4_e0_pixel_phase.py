import json
from pathlib import Path
import unittest

from spatial_world_model.public_geometry import recover_openings
from spatial_world_model.r4_e0_pixel_phase import (
    gate_gap_trace,
    phase_fractions,
    pixel_pitch_m,
    projected_column,
)


ROOT = Path(__file__).resolve().parents[2]
E0 = json.loads((ROOT / "configs/spatial_history/public_geometry_parallel_v1.json").read_text())


def observation(boundary_face=True):
    width, height = 8, 5
    depth = [1.4] * (width * height)
    geom = ["floor"] * (width * height)
    for v in range(1, 4):
        for u in (0, 1):
            depth[v * width + u] = 1.1
            geom[v * width + u] = "gate_0_left"
        for u in (5, 6, 7):
            depth[v * width + u] = 1.1
            geom[v * width + u] = "gate_0_right"
        if boundary_face:
            depth[v * width + 4] = 1.100233
            geom[v * width + 4] = "gate_0_right"
    frame = {
        "time_s": 0.0,
        "width": width,
        "height": height,
        "rgb": [0] * (width * height * 3),
        "depth_m": depth,
        "camera_position_m": [0.0, 0.0, 1.4],
        "camera_xyzw": [1.0, 0.0, 0.0, 0.0],
        "intrinsics": [100.0, 100.0, 3.5, 2.0],
        "ee_position_m": [0.0, -0.25, 0.05],
        "ee_velocity_mps": [0.0, 0.0, 0.0],
        "previous_velocity_mps": [0.0, 0.0, 0.0],
    }
    return frame, geom


class PixelPhaseTests(unittest.TestCase):
    def test_registered_phase_sweep_is_symmetric_and_includes_zero(self):
        values = phase_fractions(32, list(range(-16, 17)))
        self.assertEqual(len(values), 33)
        self.assertEqual(values[0], -0.5)
        self.assertEqual(values[16], 0.0)
        self.assertEqual(values[-1], 0.5)
        with self.assertRaises(ValueError):
            phase_fractions(32, [-16, 1, 16])

    def test_pixel_pitch_and_projection_are_world_metric(self):
        frame, _ = observation()
        self.assertAlmostEqual(pixel_pitch_m(frame, 0.3), 0.011)
        value = projected_column(frame, 0.022, 0.3)
        self.assertAlmostEqual(value["projected_u"], 5.5)
        self.assertEqual(value["nearest_pixel_u"], 6)
        self.assertAlmostEqual(value["signed_phase_from_nearest_pixel"], -0.5)

    def test_vertical_boundary_face_explains_unchanged_e0_rejection(self):
        frame, geom = observation(boundary_face=True)
        prediction = recover_openings([frame], E0["public_sensor_spec"], E0["extractor"])
        self.assertEqual(prediction["candidates"], [])
        self.assertEqual(prediction["rejected_counts"]["nonfarther_gap_pairs"], 3)
        trace = gate_gap_trace(frame, geom, "gate_0_left", "gate_0_right", 0.3,
                               E0["public_sensor_spec"], E0["extractor"])
        self.assertEqual(trace["matching_row_pairs"], 3)
        self.assertEqual(trace["farther_passing_row_pairs"], 0)
        self.assertEqual(trace["failed_pixels"], 3)
        self.assertEqual({row["failures"][0]["geom_name"] for row in trace["rows"]},
                         {"gate_0_right"})
        self.assertTrue(all(row["failures"][0]["depth_shortfall_m"] > 0
                            for row in trace["rows"]))

    def test_farther_gap_removes_boundary_failure_without_completing_geometry(self):
        frame, geom = observation(boundary_face=False)
        trace = gate_gap_trace(frame, geom, "gate_0_left", "gate_0_right", 0.3,
                               E0["public_sensor_spec"], E0["extractor"])
        self.assertEqual(trace["matching_row_pairs"], 3)
        self.assertEqual(trace["farther_passing_row_pairs"], 3)
        self.assertEqual(trace["failed_pixels"], 0)


if __name__ == "__main__":
    unittest.main()
