"""D-224 / S2-04 tests: the teacher and evaluator wiring over the S2-01 runner's steps.

Pinned here on a hand-built five-frame episode (a mug and a book seen twice, then after the
two-frame unobservable window the mug is removed and the book moved one metre; a wall fragment
resolves to a structural key throughout): the private overlap table is digest-checked against the
sealed frame; private truth opens only against the step receipt's two-seal gate and frames must
arrive in order; the S0-04 labels come out as the rules say (birth, labelled, gone for the removed
mug's entity, present-by-structure for the wall's entity); every frame's decomposition is additive;
node P/R/F1, the Missing residual rate at the episode end, identity continuity at the first
re-observation, recovery latency from the first observable frame, contamination AUC and size/cost
carry exactly the frozen fields; TAF (never retracts) keeps the stale mug entity while ELU-P
retracts it and the two reports differ exactly there; the training record holds the runner's
eligible rows only; mutating the private plane changes labels and no public byte; the machine
contract binds the implementation.  CPU only, seconds.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for item in (SRC_ROOT, PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402

from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt import lean_model  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402
from test_vsmt_lean_runner import CONFIGS, POLICY, box_block, cache_frame, fragment_row  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s2_04_evaluation_v1.json"
TEACHER_POLICY = {"dominance_min_share": 0.5, "delta_moved_m": 0.5, "should_be_visible_min_ratio": 1 / 64, "entity_geometry_samples_per_axis": 4}
NUISANCE_META = {"path": "cache/ep-0001", "seed": 20260920, "house_index": 1}
DIM, SIDE = 8, 8


def unit(seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=DIM)
    return [float(v) for v in values / np.linalg.norm(values)]


def xyz(x: float, y: float, z: float) -> dict[str, float]:
    return {"x": x, "y": y, "z": z}


MUG, BOOK, WALL = unit(1), unit(2), unit(3)
A, B, C, W = [0.0, 0.0, 2.0], [1.0, 0.0, 2.0], [2.0, 0.0, 2.0], [0.0, 0.5, 2.9]
SEES_ALL = [box_block([-2.0, -1.0, 0.5], [3.0, 1.0, 3.0], ordinal=0, kind="visibility")]
FREE_AT_A_AND_B = [box_block([-0.5, -0.5, 1.5], [0.5, 0.5, 2.5], ordinal=0, kind="free-space"),
                   box_block([0.5, -0.5, 1.5], [1.5, 0.5, 2.5], ordinal=1, kind="free-space")]
LABEL_OF = {"Mug|1": 1, "Book|2": 2, "wall|3": 3}


def region(rows: tuple[int, int], cols: tuple[int, int]) -> np.ndarray:
    mask = np.zeros((SIDE, SIDE), dtype=bool)
    mask[rows[0]:rows[1], cols[0]:cols[1]] = True
    return mask


MASKS = {"mug": region((0, 2), (0, 2)), "book_early": region((2, 4), (2, 4)), "book_late": region((2, 4), (4, 6)), "wall": region((6, 8), (0, 8))}


def fragment(fragment_id: str, *, descriptor: list[float], centroid: list[float], mask: np.ndarray) -> dict[str, Any]:
    row = fragment_row(fragment_id, descriptor=descriptor, centroid=centroid, pixels=int(mask.sum()))
    row["mask_sha256"] = fc.mask_sha256_of(mask)
    return row


def label_image(present: dict[str, np.ndarray]) -> np.ndarray:
    image = np.zeros((SIDE, SIDE), dtype=np.int64)
    for key, mask in present.items():
        image[mask] = LABEL_OF[key]
    return image


def episode() -> dict[str, Any]:
    """Five frames; window = frames 0-1; after it the mug is removed and the book moved from B to C."""

    frames, masks, records, images = [], [], [], []
    for index in range(5):
        early = index <= 1
        parts: list[tuple[str, np.ndarray, dict[str, Any]]] = []
        if early:
            parts.append(("Mug|1", MASKS["mug"], fragment(f"f{index}:mug", descriptor=MUG, centroid=A, mask=MASKS["mug"])))
            parts.append(("Book|2", MASKS["book_early"], fragment(f"f{index}:book", descriptor=BOOK, centroid=B, mask=MASKS["book_early"])))
        else:
            parts.append(("Book|2", MASKS["book_late"], fragment(f"f{index}:book", descriptor=BOOK, centroid=C, mask=MASKS["book_late"])))
        if index != 4:  # the wall is not proposed in the last frame, so its entity becomes an existence candidate
            parts.append(("wall|3", MASKS["wall"], fragment(f"f{index}:wall", descriptor=WALL, centroid=W, mask=MASKS["wall"])))
        frame = cache_frame(index + 1, [p[2] for p in parts], visibility=SEES_ALL, free_space=([] if early else FREE_AT_A_AND_B))
        frames.append(frame)
        masks.append({"masks": np.stack([p[1] for p in parts]), "mask_sha256": [p[2]["mask_sha256"] for p in parts]})
        keys = ["Mug|1", "Book|2", "wall|3"] if early else ["Book|2", "wall|3"]
        poses = {"Mug|1": xyz(*A), "Book|2": xyz(*(B if early else C)), "wall|3": xyz(*W)}
        records.append({"observation_index": index, "instance_mask_path": f"{index:04d}.instance.png",
                        "object_id_to_entity_id": {k: LABEL_OF[k] for k in keys},
                        "object_poses": {k: poses[k] for k in keys},
                        "object_visibility": {k: (2000 if k == "wall|3" else 300) for k in keys},
                        "frame_digest": frame["frame_digest"]})
        present = {"Book|2": MASKS["book_early"] if early else MASKS["book_late"], "wall|3": MASKS["wall"]}
        if early:
            present["Mug|1"] = MASKS["mug"]
        images.append(label_image(present))
    metadata = [
        {"objectId": "Mug|1", "assetId": "Mug_1", "objectType": "Mug", "pickupable": True, "receptacle": False,
         "position": xyz(*A), "rotation": xyz(0.0, 0.0, 0.0), "axisAlignedBoundingBox": {"center": xyz(0.0, 0.05, 2.0), "size": xyz(0.2, 0.1, 0.2)}},
        {"objectId": "Book|2", "assetId": "Book_2", "objectType": "Book", "pickupable": True, "receptacle": False,
         "position": xyz(*B), "rotation": xyz(0.0, 0.0, 0.0), "axisAlignedBoundingBox": {"center": xyz(1.0, 0.05, 2.0), "size": xyz(0.2, 0.1, 0.2)}},
    ]
    table = og.build_geometry_table(episode_id="ep-0001", house_id="house-1", source_index=1, code_commit="abc123",
                                    metadata_objects=metadata, camera_position_world=xyz(0.0, 0.0, 0.0),
                                    agent_pose={"position": xyz(0.0, 0.0, 0.0), "rotation": xyz(0.0, 0.0, 0.0), "cameraHorizon": 0.0})
    executed = [{"kind": "remove", "object_id": "Mug|1", "executed": True},
                {"kind": "move", "object_id": "Book|2", "point": xyz(*C), "executed": True}]
    return {"frames": frames, "masks": masks, "records": records, "images": images, "table": table, "executed": executed, "window": [0, 1]}


def run_and_label(arm: str, *, data: dict[str, Any] | None = None, config: dict[str, Any] | None = None):
    data = data or episode()
    steps = list(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=config or CONFIGS[arm], policy=POLICY,
                                descriptor="vitb14"))
    teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
    labelled = [teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                    label_image=data["images"][i], runtime_s=0.01 * (i + 1), peak_memory_bytes=1000 + i)
                for i, step in enumerate(steps)]
    return steps, teacher, labelled, teacher.episode_report()


def entity_of(memory: dict[str, Any], fragment_prefix: str) -> str:
    return next(str(e["entity_id"]) for e in memory["entities"] if e["evidence"][0]["fragment_id"].endswith(fragment_prefix))


class OverlapTableTests(unittest.TestCase):
    def test_shares_are_over_all_fragment_pixels_and_masks_are_digest_checked(self) -> None:
        data = episode()
        table = ev.fragment_instances(data["frames"][0], data["masks"][0], data["images"][0], ev.object_of_label(data["records"][0]))
        self.assertEqual(table["f0:mug"], {"overlap": {"Mug|1": 1.0}, "pixel_count": 4})
        self.assertEqual(table["f0:wall"], {"overlap": {"wall|3": 1.0}, "pixel_count": 16})
        # a fragment straddling the mug and background: share over all its pixels, background unlisted
        straddle = region((0, 2), (0, 4))
        frame = cache_frame(1, [fragment("f:x", descriptor=MUG, centroid=A, mask=straddle)], visibility=SEES_ALL, free_space=[])
        masks = {"masks": np.stack([straddle]), "mask_sha256": [frame["fragments"][0]["mask_sha256"]]}
        self.assertEqual(ev.fragment_instances(frame, masks, data["images"][0], {1: "Mug|1"})["f:x"], {"overlap": {"Mug|1": 0.5}, "pixel_count": 8})
        tampered = {"masks": np.stack([region((0, 2), (0, 3))]), "mask_sha256": masks["mask_sha256"]}
        with self.assertRaises(ev.LeanEvaluationError) as caught:
            ev.fragment_instances(frame, tampered, data["images"][0], {1: "Mug|1"})
        self.assertTrue(str(caught.exception).startswith("fragment_masks_do_not_match_the_sealed_frame"))

    def test_policy_values_must_be_explicit(self) -> None:
        self.assertEqual(ev.validate_policy(TEACHER_POLICY)["delta_moved_m"], 0.5)
        for name in ev.POLICY_FIELDS:
            broken = dict(TEACHER_POLICY)
            broken[name] = None
            with self.subTest(name=name), self.assertRaises(ev.LeanEvaluationError) as caught:
                ev.validate_policy(broken)
            self.assertEqual(str(caught.exception), f"policy_value_missing:{name}")


class TafEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.steps, cls.teacher, cls.frames, cls.episode = run_and_label("TAF")

    def test_labels_follow_the_s0_04_rules(self) -> None:
        first, second, third, last = self.frames[0], self.frames[1], self.frames[2], self.frames[4]
        self.assertEqual({t["status"] for t in first["targets"].values()}, {"birth"})
        self.assertEqual({t["status"] for t in second["targets"].values()}, {"labelled"})
        memory_after_two = self.steps[1]["state"]["memory"]
        mug_entity, book_entity, wall_entity = (entity_of(memory_after_two, s) for s in (":mug", ":book", ":wall"))
        self.assertEqual(second["targets"]["f1:book"]["target"], book_entity)
        # after the window: the book's fragment at C is labelled with the book's entity, the mug's entity is gone
        self.assertEqual(third["targets"]["f2:book"], {**third["targets"]["f2:book"], "status": "labelled", "target": book_entity, "key": "Book|2"})
        self.assertEqual(third["existence_labels"][mug_entity]["status"], "gone")
        self.assertEqual(third["existence_labels"][mug_entity]["reason"], "absent")
        # the last frame: the wall is not proposed, its entity is a candidate and is present by structure
        self.assertEqual(last["existence_labels"][wall_entity], {"status": "present", "key": "wall|3", "reason": "structural_never_intervened", "displacement_m": None})
        self.assertEqual(set(last["existence_labels"]), {mug_entity, wall_entity})
        self.assertEqual(self.steps[4]["receipt"]["existence"]["candidates"], sorted([mug_entity, wall_entity]))

    def test_every_frame_decomposition_is_additive_and_taf_pays_for_the_missed_retracts(self) -> None:
        totals = [f["decomposition"]["totals"] for f in self.frames]
        for total in totals:
            self.assertEqual(sum(total[k] for k in ("recall_miss", "teacher_error", "amortization_error", "correct", "unlabelled", "duplicate_of_labelled")), total["decisions"])
        self.assertEqual([t["decisions"] for t in totals], [3, 3, 3, 3, 3])
        self.assertEqual([t["amortization_error"] for t in totals], [0, 0, 1, 1, 1])  # NOOP on the gone mug each frame
        self.assertEqual(self.episode["diagnostics"]["decomposition_totals"]["correct"], 12)
        self.assertEqual([f["decomposition"]["existence"]["missed_retract"] for f in self.frames], [0, 0, 1, 1, 1])

    def test_node_metrics_per_frame_and_micro_over_the_episode(self) -> None:
        self.assertEqual([f["node_prf1"]["node_f1"] for f in self.frames[:2]], [1.0, 1.0])
        self.assertEqual(self.frames[2]["node_prf1"], {"node_precision": 0.5, "node_recall": 1.0, "node_f1": 2 / 3, "matched": 1, "predicted": 2, "truth": 1})
        self.assertEqual(len(self.frames[2]["out_of_scope_entities"]), 1)  # the wall's entity, every frame
        self.assertEqual(self.frames[2]["truth_in_scope"], ["Book|2"])
        report = self.episode["report"]
        self.assertEqual(report["node_prf1"], {"node_precision": 0.7, "node_recall": 1.0, "node_f1": 2 * 0.7 / 1.7, "matched": 7, "predicted": 10, "truth": 7})
        # ruling 72 (B): every entity centroid sits on its object's truth centroid and its box on the truth box
        # here, so the IoU column equals the centroid primary column frame by frame and over the episode
        self.assertEqual([f["node_prf1_iou"] for f in self.frames], [f["node_prf1"] for f in self.frames])
        self.assertEqual(report["node_prf1_iou"], report["node_prf1"])
        self.assertEqual([f["contamination_fraction"] for f in self.frames], [0.0, 0.0, 0.5, 0.5, 0.5])
        self.assertAlmostEqual(report["contamination_auc"]["contamination_auc"], 0.3125)
        self.assertEqual(report["contamination_auc"]["frames"], 5)

    def test_intervention_metrics_from_the_tracker_places(self) -> None:
        report, diagnostics = self.episode["report"], self.episode["diagnostics"]
        self.assertEqual(diagnostics["interventions"], {"Mug|1": "remove", "Book|2": "move"})
        self.assertEqual(diagnostics["old_place_observable_since_intervention"], ["Book|2", "Mug|1"])
        # Missing residual: the mug's entity still stands (dormant) at A, the book's entity followed the BIND to C
        self.assertEqual(report["missing_residual_rate"], {"missing_residual_rate": 0.5, "residual": 1, "judged": 2, "not_yet_observable": 0})
        self.assertEqual(diagnostics["missing_residual_series"], [None, None, 0.5, 0.5, 0.5])
        # identity continuity: the book's first re-observation after the move is bound to its pre-move carrier
        self.assertEqual(report["identity_continuity"], {"identity_continuity": 1.0, "kept": 1, "judged": 1, "no_prior_carrier": 0})
        self.assertEqual(diagnostics["reobserved_at"], {"Book|2": 2})
        book_entity = entity_of(self.steps[1]["state"]["memory"], ":book")
        self.assertEqual(diagnostics["carriers_before_move"], {"Book|2": [book_entity]})
        # recovery: the book is correct at the first observable frame (latency 0); the mug never recovers under TAF
        self.assertEqual(report["recovery_latency_frames"], {"recovery_latency_frames": 0.0, "recovered": 1, "unrecovered": ["Mug|1"],
                                                             "never_observable": [], "per_object": {"Book|2": 0, "Mug|1": None}})
        self.assertEqual(report["false_retract_rate"], {"false_retract_rate": None, "false_retracts": 0, "judged_retracts": 0, "ambiguous_retracts": 0})
        self.assertEqual(self.steps[4]["receipt"]["entities_by_state"], {"active": 2, "dormant": 1, "retracted": 0})

    def test_size_cost_and_the_report_carry_exactly_the_frozen_fields(self) -> None:
        report = self.episode["report"]
        lt.assert_report_keys(report)
        self.assertEqual(set(report), set(lt.METRICS))
        for metric, fields in lt.METRIC_FIELDS.items():
            self.assertEqual(tuple(report[metric]), fields, metric)
        self.assertAlmostEqual(report["size_and_cost"]["runtime_per_frame_s"], 0.03)
        self.assertEqual(report["size_and_cost"]["peak_memory_bytes"], 1004)
        self.assertEqual(report["size_and_cost"]["active_entity_count"], (3 + 3 + 3 + 2 + 2) / 5)
        self.assertEqual(ev.headline_values(report)["missing_residual_rate"], 0.5)
        self.assertNotIn("size_and_cost", ev.headline_values(report))

    def test_training_records_hold_the_eligible_rows_only_and_the_probes_run(self) -> None:
        for frame, step in zip(self.frames, self.steps):
            record = lean_model.validate_training_record(frame["training_record"])
            candidates = step["receipt"]["existence"]["candidates"]
            self.assertEqual([r["entity_id"] for r in record["existence_rows"]], candidates)
            self.assertEqual(set(record["existence_labels"]), set(candidates))
            self.assertEqual(set(record["targets"]), set(step["stage_a"]["rows"]))
            self.assertEqual(record["stage_a"]["seal_sha256"], step["stage_a"]["seal_sha256"])
        probes = ev.nuisance_probes(self.frames)
        self.assertEqual(probes["association_rows"], 3 + 3 + 2 + 2 + 1)
        self.assertEqual(probes["existence_rows"], 0 + 0 + 1 + 1 + 2)
        self.assertIsInstance(probes["largest_advantage"], float)
        self.assertEqual(set(probes["association"]["per_label"]), set(ev.NUISANCE_ASSOCIATION_LABELS))
        self.assertEqual(set(probes["existence"]["per_label"]), {"existence_status"})
        row = self.frames[2]["nuisance"]["association"][0]
        self.assertEqual({k: row[k] for k in ("path", "seed", "house_index", "frame_index")}, {**NUISANCE_META, "frame_index": 2})


class EluPEpisodeTests(unittest.TestCase):
    def test_elu_p_retracts_the_removed_mug_and_the_report_differs_exactly_there(self) -> None:
        steps, _, frames, episode = run_and_label("ELU-P")
        _, _, taf_frames, taf = run_and_label("TAF")
        mug_entity = entity_of(steps[1]["state"]["memory"], ":mug")
        self.assertEqual(steps[3]["receipt"]["existence"]["decisions"][mug_entity], "RETRACT")
        self.assertEqual(frames[3]["existence_labels"][mug_entity]["status"], "gone")
        self.assertEqual(frames[3]["decomposition"]["existence"], {"candidates": 1, "teacher_error": 0, "correct": 1, "false_retract": 0, "missed_retract": 0})
        report = episode["report"]
        self.assertEqual(report["false_retract_rate"], {"false_retract_rate": 0.0, "false_retracts": 0, "judged_retracts": 1, "ambiguous_retracts": 0})
        self.assertEqual(report["missing_residual_rate"], {"missing_residual_rate": 0.0, "residual": 0, "judged": 2, "not_yet_observable": 0})
        self.assertEqual(report["recovery_latency_frames"]["per_object"], {"Book|2": 0, "Mug|1": 1})
        self.assertEqual(report["recovery_latency_frames"]["recovery_latency_frames"], 0.5)
        self.assertEqual(report["identity_continuity"], taf["report"]["identity_continuity"])
        self.assertEqual([f["contamination_fraction"] for f in frames], [0.0, 0.0, 0.5, 0.0, 0.0])
        self.assertLess(report["contamination_auc"]["contamination_auc"], taf["report"]["contamination_auc"]["contamination_auc"])
        # the two arms read the same private truth: identical targets wherever the same fragments were sealed
        self.assertEqual({k: v["status"] for k, v in frames[2]["targets"].items()}, {k: v["status"] for k, v in taf_frames[2]["targets"].items()})


class GateAndInvarianceTests(unittest.TestCase):
    def test_private_mutation_changes_labels_and_no_public_byte(self) -> None:
        data = episode()
        steps = list(lr.run_episode(data["frames"], episode_id="ep-0001", arm="TAF", config=CONFIGS["TAF"], policy=POLICY, descriptor="vitb14"))
        before = canonical_json([{"receipt": s["receipt"], "stage_a": s["stage_a"], "stage_b": s["stage_b"]} for s in steps])
        mutated = copy.deepcopy(data)
        for image in mutated["images"][:2]:
            image[MASKS["mug"]] = 0  # the mug's pixels become background in the first two frames
        outputs = []
        for plane in (data, mutated):
            teacher = ev.EpisodeTeacher(arm="TAF", geometry_table=plane["table"], executed_interventions=plane["executed"], window=plane["window"],
                                        policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
            outputs.append([teacher.label_frame(step, cache_frame=plane["frames"][i], private_record=plane["records"][i], masks=plane["masks"][i],
                                                label_image=plane["images"][i], runtime_s=0.0, peak_memory_bytes=0) for i, step in enumerate(steps)])
        after = canonical_json([{"receipt": s["receipt"], "stage_a": s["stage_a"], "stage_b": s["stage_b"]} for s in steps])
        self.assertEqual(before, after)
        self.assertEqual(outputs[0][0]["targets"]["f0:mug"]["status"], "birth")
        self.assertEqual(outputs[1][0]["targets"]["f0:mug"]["status"], "unlabelled")
        self.assertNotEqual(canonical_json(outputs[0][2]["existence_labels"]), canonical_json(outputs[1][2]["existence_labels"]))

    def test_the_gate_and_the_frame_order_are_enforced(self) -> None:
        data = episode()
        steps = list(lr.run_episode(data["frames"], episode_id="ep-0001", arm="TAF", config=CONFIGS["TAF"], policy=POLICY, descriptor="vitb14"))

        def teacher():
            return ev.EpisodeTeacher(arm="TAF", geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                     policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)

        def label(t, i, step=None, record=None):
            return t.label_frame(step or steps[i], cache_frame=data["frames"][i], private_record=record or data["records"][i],
                                 masks=data["masks"][i], label_image=data["images"][i], runtime_s=0.0, peak_memory_bytes=0)

        tampered = copy.deepcopy(steps[0])
        tampered["receipt"]["private_gate"]["stage_b_seal_sha256"] = "0" * 64
        with self.assertRaises(ev.LeanEvaluationError) as caught:
            label(teacher(), 0, step=tampered)
        self.assertEqual(str(caught.exception), "private_gate_invalid")
        with self.assertRaises(ev.LeanEvaluationError) as caught:
            label(teacher(), 1)  # the second frame first
        self.assertEqual(str(caught.exception), "private_record_out_of_order")
        wrong_record = {**data["records"][0], "frame_digest": "f" * 64}
        with self.assertRaises(ev.LeanEvaluationError) as caught:
            label(teacher(), 0, record=wrong_record)
        self.assertTrue(str(caught.exception).startswith("private_record_out_of_order"))
        # an unknown non-structural private key fails the episode instead of shrinking the scope
        unknown = teacher()
        record = copy.deepcopy(data["records"][0])
        record["object_visibility"]["Ceiling|7"] = 500
        with self.assertRaises(ev.LeanEvaluationError) as caught:
            label(unknown, 0, record=record)
        self.assertEqual(str(caught.exception), "truth_key_outside_geometry_table:Ceiling|7")

    def test_a_spawned_after_reload_key_is_out_of_scope_and_its_entity_is_present_by_rule(self) -> None:
        # ruling 69: the wall's private key becomes a physics-spawned key; the episode still runs, the
        # key stays out of the node scope, its entity's existence label is present by rule
        data = episode()
        spawned = "Egg|surface|1|9|EggCracked_0"
        for record in data["records"]:
            for field in ("object_id_to_entity_id", "object_poses", "object_visibility"):
                record[field][spawned] = record[field].pop("wall|3")
        steps, _, frames, report = run_and_label("TAF", data=data)
        entity = entity_of(steps[1]["state"]["memory"], ":wall")
        self.assertEqual(frames[4]["existence_labels"][entity], {"status": "present", "key": spawned, "reason": "spawned_after_reload", "displacement_m": None})
        self.assertEqual(frames[0]["truth_in_scope"], ["Book|2", "Mug|1"])
        self.assertEqual(report["diagnostics"]["spawned_after_reload_keys"], [spawned])
        self.assertEqual(len(frames[2]["out_of_scope_entities"]), 1)

    def test_interventions_without_a_window_or_on_an_absent_object_are_refused(self) -> None:
        data = episode()
        with self.assertRaises(og.LeanObjectGeometryError):
            ev.EpisodeTeacher(arm="TAF", geometry_table=data["table"], executed_interventions=data["executed"], window=None,
                              policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
        with self.assertRaises(ev.LeanEvaluationError) as caught:
            ev.EpisodeTeacher(arm="TAF", geometry_table=data["table"], executed_interventions=[{"kind": "teleport", "object_id": "Mug|1"}],
                              window=[0, 1], policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
        self.assertEqual(str(caught.exception), "intervention_kind_unknown:teleport")
        # no interventions at all: the intervention metrics are undefined and counted, nothing crashes
        _, _, frames, episode_report = run_and_label("TAF", data={**data, "executed": [], "window": None})
        self.assertEqual(episode_report["report"]["missing_residual_rate"]["missing_residual_rate"], None)
        self.assertEqual(episode_report["report"]["identity_continuity"]["judged"], 0)
        self.assertEqual(episode_report["report"]["recovery_latency_frames"]["recovered"], 0)
        self.assertTrue(all(f["missing_residual"] is None for f in frames))


class MachineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_contract_binds_the_implementation(self) -> None:
        checked = ev.validate_evaluation_contract(self.contract)
        self.assertEqual(checked["stage_id"], "S2-04")
        self.assertEqual(checked["derivation_rules"]["recovery_place"], ev.RECOVERY_PLACE_RULE)
        self.assertEqual(checked["policy_values_without_defaults"], [])
        # both bits opened on 2026-09-24 (rulings 64/67, the S2-05 review) and named by the activation policy
        self.assertTrue(all(checked["authorization"].values()))
        self.assertEqual(sorted(checked["activation_policy"]["active_true_authorizations"]), sorted(checked["authorization"]))
        for key, path in checked["depends_on"].items():
            if key.endswith("_contract"):
                self.assertTrue((PROJECT_ROOT / path).is_file(), path)
        self.assertTrue((PROJECT_ROOT / checked["pure_core_relative_path"]).is_file())

    def test_weakened_claims_and_unruled_bits_are_refused(self) -> None:
        for edit, code in (
            (lambda c: c["derivation_rules"].__setitem__("place_observable", "another"), "contract_rule_mismatch:place_observable"),
            (lambda c: c["derivation_rules"].__setitem__("no_public_byte_is_read_or_written", False), "contract_claim_weakened:no_public_byte_is_read_or_written"),
            (lambda c: c["derivation_rules"]["recovery_place"].__setitem__("moved", "new_place"), "contract_rule_mismatch:recovery_place"),
            (lambda c: c["headline_fields"].__setitem__("node_prf1", "node_recall"), "contract_headline_fields_mismatch"),
            (lambda c: c.pop("activation_policy"), "contract_bit_opened_without_a_ruling:label_generation_run"),
            (lambda c: c["policy_values_without_defaults"].append("x"), "contract_registers_a_value_slot_it_does_not_own"),
        ):
            broken = copy.deepcopy(self.contract)
            edit(broken)
            with self.subTest(code=code), self.assertRaises(ev.LeanEvaluationError) as caught:
                ev.validate_evaluation_contract(broken)
            self.assertEqual(str(caught.exception), code)
        opened = copy.deepcopy(self.contract)
        opened["authorization"] = {name: False for name in opened["authorization"]}
        opened.pop("activation_policy", None)
        ev.validate_evaluation_contract(opened)  # the closed form stays valid
        opened["authorization"]["label_generation_run"] = True
        opened["activation_policy"] = {"opened_by": "D-224-S1 ruling <n>", "opened_on": "2026-09-30", "active_true_authorizations": ["label_generation_run"]}
        self.assertTrue(ev.validate_evaluation_contract(opened)["authorization"]["label_generation_run"])


if __name__ == "__main__":
    unittest.main()
