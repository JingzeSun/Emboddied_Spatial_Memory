"""Ruling 104-2 tests for the split-level nuisance probe by counts.

Pinned: ``lean_teacher.nuisance_probe_from_counts`` equals ``nuisance_probe`` on the rows it counts, field by field and
label by label (random rows with heavy ties, booleans and missing values); ``lean_evaluation.NuisanceTally`` fed frame by
frame equals ``nuisance_probes`` over the pooled frames exactly, including a block with fewer than two rows.  CPU, seconds.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402

ASSOCIATION_STATUSES = ("labelled", "identity_ambiguous", "duplicate_of_labelled", "birth", "recall_miss", "unlabelled")


def frames(seed: int, count: int, *, houses: int = 4) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for tick in range(count):
        house = rng.randrange(houses)
        meta = {"path": f"cache/ep-{house:04d}", "seed": 20260920, "house_index": None if house == 3 else house, "frame_index": tick % 7}
        association = [{**meta, "association_status": rng.choice(ASSOCIATION_STATUSES[: rng.randint(2, 6)]),
                        "association_target_is_birth": rng.random() < 0.2} for _ in range(rng.randint(0, 5))]
        existence = [{**meta, "existence_status": rng.choice(("present", "gone", "identity_ambiguous"))} for _ in range(rng.randint(0, 2))]
        out.append({"association": association, "existence": existence})
    return out


class NuisanceTallyTests(unittest.TestCase):
    def test_the_count_form_equals_the_row_form(self) -> None:
        for seed in range(12):
            rows = [row for frame in frames(seed, 40) for row in frame["association"]]
            if len(rows) < 2:
                continue
            for field in lt.NUISANCE_FIELDS:
                for label in ("association_status", "association_target_is_birth"):
                    labels: dict[str, int] = {}
                    groups: dict[str, dict[str, int]] = {}
                    for row in rows:
                        item = str(row[label])
                        labels[item] = labels.get(item, 0) + 1
                        group = groups.setdefault(str(row[field]), {})
                        group[item] = group.get(item, 0) + 1
                    with self.subTest(seed=seed, field=field, label=label):
                        self.assertEqual(lt.nuisance_probe_from_counts(labels, groups, field=field, label=label),
                                         lt.nuisance_probe(rows, field=field, label=label))

    def test_the_tally_equals_the_pooled_probes(self) -> None:
        for seed, count in ((1, 200), (2, 50), (3, 3), (4, 1)):
            pooled = frames(seed, count)
            tally = ev.NuisanceTally()
            for frame in pooled:
                tally.add(frame)
            with self.subTest(seed=seed):
                self.assertEqual(tally.result(), ev.nuisance_probes([{"nuisance": frame} for frame in pooled]))
        tally = ev.NuisanceTally()
        tally.add({"association": [], "existence": [{"path": "p", "seed": 1, "house_index": 1, "frame_index": 0, "existence_status": "gone"}]})
        self.assertEqual(tally.result(), {"association_rows": 0, "existence_rows": 1, "association": None, "existence": None,
                                          "largest_advantage": None})


if __name__ == "__main__":
    unittest.main()
