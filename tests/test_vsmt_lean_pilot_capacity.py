"""The S1-02 generator's capacity reading on a multi-GPU host (4-card vGPU, 2026-09-30)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02a_pilot as runner  # noqa: E402


class TestCapacityOnFourCards(unittest.TestCase):
    def test_reads_gpu_zero_from_a_four_line_listing(self) -> None:
        try:
            import psutil  # noqa: F401
        except ImportError:
            self.skipTest("psutil not installed")
        listing = "\n".join(["NVIDIA GeForce RTX 4080 SUPER, 32760, 1024"] + ["NVIDIA GeForce RTX 4080 SUPER, 32760, 0"] * 3) + "\n"
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout=listing, stderr="")
        with mock.patch.object(runner.subprocess, "run", return_value=done), \
                mock.patch.object(runner.os, "statvfs", return_value=mock.Mock(f_bavail=10, f_frsize=1_000_000_000), create=True):
            measured = runner._capacity_measurements()
        self.assertEqual(measured["gpu_name"], "NVIDIA GeForce RTX 4080 SUPER")
        self.assertAlmostEqual(measured["gpu_total_vram_gb"], 32760 / 1024.0)
        self.assertAlmostEqual(measured["gpu_free_vram_gb"], (32760 - 1024) / 1024.0)
        self.assertAlmostEqual(measured["disk_free_gb_asset_root"], 10.0)


if __name__ == "__main__":
    unittest.main()
