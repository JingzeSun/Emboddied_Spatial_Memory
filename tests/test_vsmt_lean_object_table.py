"""Ruling 52: the S1-02 generator's object table attributes objects to the first non-Floor receptacle
and records the full parentReceptacles list.  Pure metadata in, rows out; no simulator."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02a_pilot as runner  # noqa: E402
from vsmt import lean_interventions as sel  # noqa: E402


def meta(*objects: dict) -> dict:
    return {"objects": list(objects)}


def obj(object_id: str, parents: list[str] | None, *, pickupable: bool = True, receptacle: bool = False) -> dict:
    row = {"objectId": object_id, "assetId": "asset_" + object_id.split("|")[0], "pickupable": pickupable, "receptacle": receptacle}
    if parents is not None:
        row["parentReceptacles"] = parents
    return row


class TestObjectTable(unittest.TestCase):
    def test_low_furniture_objects_keep_their_receptacle_and_the_full_list(self) -> None:
        rows = runner._object_table(meta(obj("Bowl|surface|5|20", ["Floor", "TVStand|5|0|0"])))
        self.assertEqual(rows[0]["parent_receptacle"], "TVStand|5|0|0")
        self.assertEqual(rows[0]["parent_receptacles"], ["Floor", "TVStand|5|0|0"])

    def test_floor_only_and_missing_lists_give_no_receptacle(self) -> None:
        rows = runner._object_table(meta(obj("Box|surface|1|1", ["Floor"]), obj("Cup|surface|1|2", None), obj("Pen|surface|1|3", [])))
        self.assertEqual([r["parent_receptacle"] for r in rows], [None, None, None])
        self.assertEqual([r["parent_receptacles"] for r in rows], [["Floor"], [], []])

    def test_the_rule_is_the_selector_rule(self) -> None:
        parents = ["Dresser|3|2___2", "Floor"]
        rows = runner._object_table(meta(obj("Candle|surface|3|13", parents)))
        self.assertEqual(rows[0]["parent_receptacle"], sel.parent_receptacle_of(parents))

    def test_structure_flag_is_unchanged(self) -> None:
        rows = runner._object_table(meta(obj("Wall|1", None, pickupable=False, receptacle=False),
                                         obj("TVStand|5|0|0", ["Floor"], pickupable=False, receptacle=True)))
        self.assertEqual([r["is_structure"] for r in rows], [True, False])
        self.assertFalse(any(r["is_agent"] for r in rows))

    def test_the_train_03361_case_now_yields_a_remove_source(self) -> None:
        rows = runner._object_table(meta(obj("Bowl|surface|5|20", ["Floor", "TVStand|5|0|0"]),
                                         obj("Television|5|0|3", ["Floor", "TVStand|5|0|0"], pickupable=False, receptacle=False)))
        eligible = sel.eligible_objects(rows, {"Bowl|surface|5|20": 579, "Television|5|0|3": 11365})
        self.assertEqual([o["object_id"] for o in eligible], ["Bowl|surface|5|20"])
        feasible = sel.feasible_triples(eligible, ["TVStand|5|0|0"], {"TVStand|5|0|0"}, {"TVStand|5|0|0": False}, unseen=[])
        self.assertEqual([t["kind"] for t in feasible], ["remove"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
