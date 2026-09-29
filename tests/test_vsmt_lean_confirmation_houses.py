"""Ruling 81 confirmation houses: the generator's confirmation stage takes exactly the frozen list.

The list is train-block positions 50..99 under the frozen S1-02a split; the S1-02 development houses
are positions 0..49.  The pool is the 10,000 ProcTHOR-10K train ids by index, so no source file is read.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02a_pilot as runner  # noqa: E402
from vsmt import lean_pilot  # noqa: E402


class TestConfirmationHouses(unittest.TestCase):
    def setUp(self) -> None:
        contract = json.loads(runner.CONTRACT_S1_02A.read_text(encoding="utf-8"))
        pool = [f"{runner.DATASET_TAG}-{i:05d}" for i in range(10000)]
        self.block = lean_pilot.train_block(pool, contract["split_freeze"])
        self.registry = json.loads(runner.CONFIRMATION_REGISTRY.read_text(encoding="utf-8"))

    def test_the_stage_returns_the_frozen_positions(self) -> None:
        houses = runner.confirmation_houses(self.block, self.registry)
        self.assertEqual(houses, self.block[50:100])
        self.assertEqual(houses, self.registry["houses"])
        self.assertEqual(len(houses), 50)

    def test_disjoint_from_the_development_houses(self) -> None:
        houses = set(runner.confirmation_houses(self.block, self.registry))
        self.assertFalse(houses & set(self.block[:50]))

    def test_a_list_that_differs_from_the_recomputed_block_is_refused(self) -> None:
        tampered = copy.deepcopy(self.registry)
        tampered["houses"][3] = self.block[10]
        with self.assertRaises(SystemExit):
            runner.confirmation_houses(self.block, tampered)
        shifted = copy.deepcopy(self.registry)
        shifted["positions"] = [49, 98]
        with self.assertRaises(SystemExit):
            runner.confirmation_houses(self.block, shifted)


if __name__ == "__main__":
    unittest.main()
