"""D-224 / S2-03 tests for VSMT-lean's learned cost heads.

Pinned here: the three heads have the registered architecture and an exact parameter count; the
scorer returns logits keyed exactly by the sealed rows; permuting the fragments of a frame or the
entities of the memory leaves every keyed logit and the solved assignment unchanged (the S2-03
continue gate); the loss uses only labelled and birth targets and gone/present labels, excluding
recall_miss, unlabelled, identity_ambiguous, duplicate_of_labelled and ambiguous candidates;
AssocOnly has no existence head and no existence term; training refuses a missing value, is
deterministic under a seed, lowers the loss on separable synthetic frames and keeps the best
validation epoch; the weights round-trip through their digest; the recipe guard binds the frozen
values; the scorer drives the S2-01 runner end to end.  CPU torch, seconds.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_memory as lm  # noqa: E402
from vsmt import lean_model as model  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json"
METHOD_ID = "VSMT-lean"
RECALL = {"local_count": la.RECALL_LOCAL_COUNT, "global_count": la.RECALL_GLOBAL_COUNT, "local_radius_m": la.RECALL_LOCAL_RADIUS_M}
BIRTH_RADIUS = la.RECALL_BIRTH_NEIGHBOURHOOD_RADIUS_M
DIM = 6


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def unit(seed: int, dim: int = DIM) -> list[float]:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=dim)
    return [float(v) for v in values / np.linalg.norm(values)]


def fragment(fragment_id: str, *, descriptor: list[float], centroid: list[float], pixels: int = 400) -> dict[str, Any]:
    return {"fragment_id": fragment_id, "descriptor": list(descriptor), "centroid_m": list(centroid),
            "aabb_min_m": [v - 0.1 for v in centroid], "aabb_max_m": [v + 0.1 for v in centroid],
            "pixel_count": pixels, "depth_valid_ratio": 1.0, "supported_by": None}


def memory_fragment(fragment_id: str, **kwargs: Any) -> dict[str, Any]:
    item = fragment(fragment_id, **kwargs)
    del item["depth_valid_ratio"]
    return item


def frame_with(*fragments: Mapping[str, Any], tick: int, geometry: Mapping[str, tuple[float, float]], seed: str) -> dict[str, Any]:
    return {"frame_digest": digest(seed), "tick": tick, "camera_position_m": [0.0, 1.5, -1.0], "camera_forward": [0.0, 0.0, 1.0],
            "fragments": [dict(item) for item in fragments],
            "entity_geometry": {eid: {"should_be_visible_ratio": v, "free_space_coverage_ratio": c} for eid, (v, c) in geometry.items()}}


def memory_with(objects: Mapping[str, tuple[list[float], list[float]]]) -> tuple[dict[str, Any], dict[str, str]]:
    """One BIRTH per object at tick 1; returns the memory and object -> entity id."""

    operations = [{"atom": "BIRTH", "fragment": memory_fragment(f"region:{name}", descriptor=d, centroid=c)} for name, (d, c) in sorted(objects.items())]
    memory = lm.apply_program(lm.empty_memory(episode_id="ep-0001"), {"frame_digest": digest("f1"), "operations": operations},
                              method_id=METHOD_ID, dormancy_missed_opportunity_limit=2)
    by_object = {e["evidence"][0]["fragment_id"].split(":", 1)[1]: str(e["entity_id"]) for e in memory["entities"]}
    return memory, by_object


OBJECTS = {"mug": (unit(1), [0.0, 0.0, 2.0]), "book": (unit(2), [1.0, 0.0, 2.0]), "lamp": (unit(3), [-1.0, 0.0, 2.5])}


def labelled_frame(seed: int, *, drop: str | None = None, new: bool = False) -> dict[str, Any]:
    """A training record: each object's fragment (slightly perturbed) targets its own entity; optional
    dropped object (an existence candidate labelled gone when free space covers it) and a novel fragment (birth)."""

    memory, ids = memory_with(OBJECTS)
    rng = np.random.default_rng(seed)
    fragments = []
    targets = {}
    for name, (descriptor, centroid) in sorted(OBJECTS.items()):
        if name == drop:
            continue
        noisy = np.asarray(descriptor) + rng.normal(scale=0.05, size=DIM)
        noisy = [float(v) for v in noisy / np.linalg.norm(noisy)]
        fid = f"f{seed}:{name}"
        fragments.append(fragment(fid, descriptor=noisy, centroid=[c + float(rng.normal(scale=0.02)) for c in centroid]))
        targets[fid] = {"status": "labelled", "target": ids[name]}
    if new:
        fid = f"f{seed}:new"
        fragments.append(fragment(fid, descriptor=unit(100 + seed), centroid=[2.0, 0.0, 2.0]))
        targets[fid] = {"status": "birth", "target": f"{la.BIRTH_COLUMN_PREFIX}{fid}"}
    geometry = {ids[name]: ((1.0, 1.0) if name == drop else (1.0, 0.0)) for name in OBJECTS}
    frame = frame_with(*fragments, tick=2, geometry=geometry, seed=f"frame-{seed}")
    stage_a = la.build_assignment_inputs(frame, memory, birth_neighbourhood_radius_m=BIRTH_RADIUS, **RECALL)
    # a deliberately neutral assignment (everything births) only to obtain existence rows for every entity
    solution = la.solve_frame(stage_a, association_logits={f"{r['fragment_id']}|{r['entity_id']}": -1.0 for r in stage_a["association_rows"]},
                              birth_logits={f: 0.0 for f in stage_a["rows"]})
    stage_b = la.seal_solution_and_existence(solution, frame, memory, inputs=stage_a)
    labels = {ids[name]: {"status": ("gone" if name == drop else "present")} for name in OBJECTS if not any(t["target"] == ids[name] for t in targets.values())}
    return {"stage_a": stage_a, "targets": targets, "existence_rows": stage_b["existence_rows"],
            "existence_feature_order": stage_b["existence_feature_order"], "existence_labels": labels,
            "_frame": frame, "_memory": memory, "_ids": ids}


class ArchitectureTests(unittest.TestCase):
    def test_three_heads_with_the_registered_size(self) -> None:
        heads = model.make_heads(assoc_only=False, seed=0)
        counts = model.parameter_count(heads)
        expected = {}
        for name, features in model.HEAD_FEATURES.items():
            width = len(features)
            expected[name] = 2 * width + (width * 128 + 128) + (128 * 128 + 128) + (128 + 1)
        self.assertEqual({k: v for k, v in counts.items() if k != "total"}, expected)
        self.assertEqual(counts["total"], sum(expected.values()))
        # 54,207 before ruling 89-2 appended five history fields to the existence table (5 x 2 LayerNorm + 5 x 128 weights)
        self.assertEqual(counts["total"], 54857)
        assoc = model.make_heads(assoc_only=True, seed=0)
        self.assertEqual(set(assoc.keys()), {"association", "birth"})
        self.assertTrue(model.is_assoc_only(assoc))
        self.assertFalse(model.is_assoc_only(heads))

    def test_assoc_only_and_the_full_model_start_from_the_same_association_and_birth_heads(self) -> None:
        """Ruling 79-5 (a): the causal counterfactual differs from VSMT-lean only by the existence head, not by its init."""

        full = model.make_heads(assoc_only=False, seed=7)
        assoc = model.make_heads(assoc_only=True, seed=7)
        for name in ("association", "birth"):
            left, right = full[name].state_dict(), assoc[name].state_dict()
            self.assertEqual(set(left), set(right))
            for key in left:
                self.assertTrue(bool((left[key] == right[key]).all()), f"{name}.{key}")
        other = model.make_heads(assoc_only=True, seed=8)
        self.assertFalse(bool((other["association"][1].weight == assoc["association"][1].weight).all()))
        self.assertNotEqual(model.head_seed(7, "association"), model.head_seed(7, "birth"))
        self.assertEqual(model.head_seed(7, "birth"), model.head_seed(7, "birth"))
        trained = model.train_heads([labelled_frame(30)], [labelled_frame(50)], learning_rate=1e-3, weight_decay=1e-4, epochs=1, seed=7,
                                    assoc_only=True)
        self.assertEqual(trained["weights"]["training"]["initialisation"], model.INITIALISATION_RULE)

    def test_the_recipe_constants_are_the_contract_values(self) -> None:
        training = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["arms"]["VSMT-lean"]["training"]
        self.assertEqual((model.LEARNING_RATE, model.EPOCHS, model.SEED_COUNT, model.DAGGER_ROUNDS, model.MAIN_TABLE_ROUND),
                         (training["learning_rate"], training["epochs"], training["seed_count"], training["dagger_rounds"], training["main_table_round"]))
        self.assertEqual(model.LOSS_RULE, training["loss"])
        self.assertEqual(model.BATCH_RULE, training["batch"])
        self.assertEqual(model.OPTIMIZER, training["optimizer"])
        self.assertEqual(model.DAGGER_ROUND_0_SOURCE, training["dagger_round_0_memory_source"])
        model.recipe_matches_contract(learning_rate=1e-3, epochs=20, seeds=[7, 19, 31, 43, 59], dagger_rounds=2, main_table_round=1)
        for bad in (dict(learning_rate=1e-4, epochs=20, seeds=[7, 19, 31, 43, 59], dagger_rounds=2, main_table_round=1),
                    dict(learning_rate=1e-3, epochs=10, seeds=[7, 19, 31, 43, 59], dagger_rounds=2, main_table_round=1),
                    dict(learning_rate=1e-3, epochs=20, seeds=[7, 19, 31, 43], dagger_rounds=2, main_table_round=1),
                    dict(learning_rate=1e-3, epochs=20, seeds=[7, 19, 31, 43, 59], dagger_rounds=1, main_table_round=0)):
            with self.subTest(bad=bad), self.assertRaises(model.LeanModelError):
                model.recipe_matches_contract(**bad)

    def test_the_dagger_schedule_is_registered_and_needs_the_rollout_config(self) -> None:
        rounds = model.dagger_schedule({"theta_a": 0.6, "free_space_weight": 1.0, "retract_threshold": -1.0})
        self.assertEqual([r["round"] for r in rounds], [0, 1])
        self.assertEqual(rounds[0]["memory_source"], "ELU-P")
        self.assertEqual(rounds[0]["memory_config"], {"theta_a": 0.6, "free_space_weight": 1.0, "retract_threshold": -1.0})
        self.assertEqual([r["in_main_table"] for r in rounds], [False, True])
        with self.assertRaises(model.LeanModelError):
            model.dagger_schedule({"theta_a": None, "free_space_weight": 1.0, "retract_threshold": -1.0})

    def test_weights_round_trip_through_their_digest(self) -> None:
        heads = model.make_heads(assoc_only=False, seed=3)
        payload = model.weights_payload(heads, training={"note": "test"})
        self.assertEqual(payload["schema_version"], model.WEIGHTS_SCHEMA_VERSION)
        again = model.load_heads(json.loads(json.dumps(payload)))
        self.assertEqual(model.weights_payload(again, training={})["sha256"], payload["sha256"])
        broken = json.loads(json.dumps(payload))
        broken["tensors"]["birth"]["5.bias"][0] += 1e-3  # the read-out layer of LayerNorm/Linear/GELU/Linear/GELU/Linear
        with self.assertRaises(model.LeanModelError) as caught:
            model.load_heads(broken)
        self.assertEqual(str(caught.exception), "weights_digest_mismatch")
        drifted = json.loads(json.dumps(payload))
        drifted["feature_orders"]["birth"] = list(reversed(drifted["feature_orders"]["birth"]))
        drifted["sha256"] = hashlib.sha256(json.dumps(drifted).encode()).hexdigest()
        with self.assertRaises(model.LeanModelError):
            model.load_heads(drifted)


class FieldWiseTests(unittest.TestCase):
    """Ruling 89-2 / 89-3: the field-wise encoding, the class-weighted existence loss and legacy weights."""

    def records(self):
        train = [labelled_frame(s, drop=("lamp" if s % 2 else None), new=(s % 3 == 0)) for s in range(30, 40)]
        validation = [labelled_frame(s, drop=("book" if s % 2 else None)) for s in range(50, 53)]
        for record in train + validation:  # a present label on every row still unlabelled, so both classes occur
            for row in record["existence_rows"]:
                record["existence_labels"].setdefault(str(row["entity_id"]), {"status": "present"})
        return train, validation

    def test_statistics_come_from_the_given_records_and_follow_the_field_kinds(self) -> None:
        train, _ = self.records()
        stats = model.field_encoding_statistics(train)
        for head, names in model.HEAD_FEATURES.items():
            self.assertEqual(stats[head]["fields"], list(names))
            for index, name in enumerate(names):
                kind = model.FIELD_ENCODING[name]
                self.assertEqual(stats[head]["log1p"][index], 1.0 if kind == "log1p_standardize" else 0.0)
                if kind == "identity":
                    self.assertEqual((stats[head]["mean"][index], stats[head]["std"][index]), (0.0, 1.0))
                else:
                    self.assertGreater(stats[head]["std"][index], 0.0)
        at = list(model.HEAD_FEATURES["existence"]).index("observation_count")
        values = [np.log1p(r["features"][at]) for rec in train for r in rec["existence_rows"]]
        self.assertAlmostEqual(stats["existence"]["mean"][at], float(np.mean(values)), places=12)

    def test_the_encoding_is_not_invariant_to_scaling_one_field(self) -> None:
        train, _ = self.records()
        heads = model.make_heads(assoc_only=False, seed=2, encoding=model.field_encoding_statistics(train))
        self.assertNotIn("LayerNorm", repr(heads["existence"][0]))
        order = list(model.HEAD_FEATURES["existence"])
        row = [0.0] * len(order)
        row[order.index("state_is_active")] = 1.0
        far = list(row)
        far[order.index("observation_count")] = 3000.0
        low, high = list(far), list(far)
        high[order.index("free_space_coverage_ratio")] = 1.0
        scorer = model.LeanScorer(heads)
        out = scorer.existence_logits([{"entity_id": "a", "features": low}, {"entity_id": "b", "features": high}], order)
        self.assertNotAlmostEqual(out["a"], out["b"], places=3)

    def test_field_wise_weights_round_trip_and_training_is_deterministic(self) -> None:
        train, validation = self.records()
        kwargs = dict(learning_rate=1e-3, weight_decay=1e-4, epochs=3, seed=7, assoc_only=False,
                      field_encoding=True, existence_class_weight=True)
        first = model.train_heads(train, validation, **kwargs)
        second = model.train_heads(train, validation, **kwargs)
        self.assertEqual(first["weights"]["sha256"], second["weights"]["sha256"])
        payload = first["weights"]
        self.assertEqual(payload["schema_version"], model.WEIGHTS_SCHEMA_VERSION_FIELD_WISE)
        self.assertTrue(payload["training"]["field_encoding"])
        counts = payload["training"]["existence_class_weight"]
        self.assertAlmostEqual(counts["pos_weight"], counts["present"] / counts["gone"])
        self.assertEqual(payload["training"]["updates_taken"], first["updates_taken"])
        again = model.load_heads(json.loads(json.dumps(payload)))
        record = validation[0]
        a = model.LeanScorer(first["heads"]).existence_logits(record["existence_rows"], record["existence_feature_order"])
        b = model.LeanScorer(again).existence_logits(record["existence_rows"], record["existence_feature_order"])
        for key in a:
            self.assertAlmostEqual(a[key], b[key], places=5)
        # the default recipe is untouched by the new switches
        plain = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=3, seed=7, assoc_only=False)
        self.assertEqual(plain["weights"]["schema_version"], model.WEIGHTS_SCHEMA_VERSION)
        self.assertNotIn("field_encoding", plain["weights"]["training"])

    def test_the_class_weight_multiplies_the_gone_rows(self) -> None:
        import torch
        record = labelled_frame(21, drop="lamp")
        heads = model.make_heads(assoc_only=False, seed=1)
        prepared = model.prepare_frame(record)
        plain = model.prepared_loss(heads, prepared)
        weighted = model.prepared_loss(heads, prepared, existence_pos_weight=torch.as_tensor([5.0]))
        self.assertGreater(float(weighted["loss"]), float(plain["loss"]))

    def test_a_legacy_weights_file_loads_but_cannot_score_the_extended_rows(self) -> None:
        heads = model.make_heads(assoc_only=False, seed=3)
        payload = model.weights_payload(heads, training={})
        legacy = json.loads(json.dumps(payload))
        width = len(la.LEGACY_EXISTENCE_FEATURES)
        legacy["feature_orders"]["existence"] = list(la.LEGACY_EXISTENCE_FEATURES)
        legacy["tensors"]["existence"]["0.weight"] = [1.0] * width
        legacy["tensors"]["existence"]["0.bias"] = [0.0] * width
        legacy["tensors"]["existence"]["1.weight"] = [row[:width] for row in legacy["tensors"]["existence"]["1.weight"]]
        from cpmt.hashing import canonical_json
        legacy["sha256"] = hashlib.sha256(canonical_json({k: v for k, v in legacy.items() if k not in ("training", "sha256")}).encode("utf-8")).hexdigest()
        loaded = model.load_heads(legacy)
        scorer = model.LeanScorer(loaded)
        record = labelled_frame(11, drop="lamp", new=True)
        self.assertTrue(scorer.association_and_birth_logits(record["stage_a"])["association_logits"])
        with self.assertRaises(model.LeanModelError) as caught:
            scorer.existence_logits(record["existence_rows"], record["existence_feature_order"])
        self.assertEqual(str(caught.exception), "legacy_existence_head_cannot_score_the_ruling_89_rows")


class ScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = labelled_frame(11, drop="lamp", new=True)
        self.scorer = model.LeanScorer(model.make_heads(assoc_only=False, seed=5))

    def test_logits_are_keyed_exactly_by_the_sealed_rows(self) -> None:
        stage_a = self.record["stage_a"]
        out = self.scorer.association_and_birth_logits(stage_a)
        self.assertEqual(set(out["association_logits"]), {f"{r['fragment_id']}|{r['entity_id']}" for r in stage_a["association_rows"]})
        self.assertEqual(set(out["birth_logits"]), set(stage_a["rows"]))
        existence = self.scorer.existence_logits(self.record["existence_rows"], self.record["existence_feature_order"])
        self.assertEqual(set(existence), {str(r["entity_id"]) for r in self.record["existence_rows"]})
        for value in [*out["association_logits"].values(), *out["birth_logits"].values(), *existence.values()]:
            self.assertTrue(np.isfinite(value))
        with self.assertRaises(model.LeanModelError):
            self.scorer.existence_logits(self.record["existence_rows"], list(reversed(self.record["existence_feature_order"])))
        assoc_only = model.LeanScorer(model.make_heads(assoc_only=True, seed=5))
        with self.assertRaises(model.LeanModelError) as caught:
            assoc_only.existence_logits(self.record["existence_rows"], self.record["existence_feature_order"])
        self.assertEqual(str(caught.exception), "assoc_only_has_no_existence_head")

    def test_permuting_candidates_moves_no_logit_and_changes_no_program(self) -> None:
        # S2-03 continue gate: every entity's logit follows the entity, the final program is unchanged.
        frame, memory = self.record["_frame"], self.record["_memory"]
        shuffled_frame = copy.deepcopy(frame)
        random.Random(4).shuffle(shuffled_frame["fragments"])
        shuffled_memory = copy.deepcopy(memory)
        shuffled_memory["entities"].reverse()
        shuffled_memory = lm.seal_memory(shuffled_memory)
        shuffled_memory["entities"].sort(key=lambda e: str(e["entity_id"]))  # validate_memory demands sorted ids
        shuffled_memory = lm.seal_memory(shuffled_memory)
        outputs = []
        for f, m in ((frame, memory), (shuffled_frame, shuffled_memory)):
            stage_a = la.build_assignment_inputs(f, m, birth_neighbourhood_radius_m=BIRTH_RADIUS, **RECALL)
            logits = self.scorer.association_and_birth_logits(stage_a)
            solution = la.solve_frame(stage_a, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])
            stage_b = la.seal_solution_and_existence(solution, f, m, inputs=stage_a)
            existence = self.scorer.existence_logits(stage_b["existence_rows"], stage_b["existence_feature_order"])
            states = {str(e["entity_id"]): str(e["state"]) for e in m["entities"]}
            program = arms.compile_program(solution["assignment"], states, arm="VSMT-lean",
                                           existence_decisions=arms.learned_existence(existence, tau_r=0.5))
            outputs.append((logits, solution["assignment"], existence, program))
        self.assertEqual(outputs[0][0], outputs[1][0])
        self.assertEqual(outputs[0][1], outputs[1][1])
        self.assertEqual(outputs[0][2], outputs[1][2])
        self.assertEqual(outputs[0][3], outputs[1][3])


class LossTests(unittest.TestCase):
    def test_the_loss_counts_only_labelled_birth_gone_and_present(self) -> None:
        record = labelled_frame(21, drop="lamp", new=True)
        heads = model.make_heads(assoc_only=False, seed=1)
        out = model.frame_loss(heads, record)
        self.assertIsNotNone(out["loss"])
        self.assertEqual(out["association_terms"], 3)  # mug, book labelled + the new fragment's birth
        self.assertEqual(out["existence_terms"], 1)  # the lamp, gone
        # exclusions enter no term but are counted
        excluded = copy.deepcopy(record)
        fid = sorted(excluded["targets"])[0]
        excluded["targets"][fid] = {"status": "recall_miss", "target": excluded["targets"][fid]["target"]}
        lamp = next(iter(excluded["existence_labels"]))
        excluded["existence_labels"][lamp] = {"status": "identity_ambiguous"}
        out2 = model.frame_loss(heads, excluded)
        self.assertEqual(out2["association_terms"], 2)
        self.assertEqual(out2["association_excluded"]["recall_miss"], 1)
        self.assertEqual(out2["existence_terms"], 0)
        self.assertEqual(out2["existence_excluded"], 1)
        for status in ("unlabelled", "identity_ambiguous", "duplicate_of_labelled"):
            variant = copy.deepcopy(record)
            variant["targets"][fid] = {"status": status, "target": None}
            self.assertEqual(model.frame_loss(heads, variant)["association_excluded"][status], 1, status)
        nothing = copy.deepcopy(record)
        for key in nothing["targets"]:
            nothing["targets"][key] = {"status": "unlabelled", "target": None}
        nothing["existence_labels"] = {}
        self.assertIsNone(model.frame_loss(heads, nothing)["loss"])

    def test_assoc_only_has_no_existence_term_and_a_bad_record_is_refused(self) -> None:
        record = labelled_frame(22, drop="lamp")
        assoc = model.frame_loss(model.make_heads(assoc_only=True, seed=1), record)
        self.assertEqual(assoc["existence_terms"], 0)
        self.assertEqual(assoc["association_terms"], 2)
        broken = copy.deepcopy(record)
        fid = sorted(broken["targets"])[0]
        broken["targets"][fid]["target"] = "entity:nowhere"
        with self.assertRaises(model.LeanModelError) as caught:
            model.frame_loss(model.make_heads(assoc_only=False, seed=1), broken)
        self.assertTrue(str(caught.exception).startswith("record_target_not_among_the_fragment_columns"))
        broken = copy.deepcopy(record)
        broken["targets"][fid]["status"] = "guess"
        with self.assertRaises(model.LeanModelError):
            model.frame_loss(model.make_heads(assoc_only=False, seed=1), broken)


class TrainingTests(unittest.TestCase):
    def records(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        train = [labelled_frame(s, drop=("lamp" if s % 2 else None), new=(s % 3 == 0)) for s in range(30, 42)]
        validation = [labelled_frame(s, drop=("book" if s % 2 else None), new=(s % 2 == 0)) for s in range(50, 54)]
        return train, validation

    def test_training_refuses_a_missing_value(self) -> None:
        train, validation = self.records()
        for name in ("learning_rate", "weight_decay", "epochs", "seed"):
            values = {"learning_rate": 1e-3, "weight_decay": 1e-4, "epochs": 2, "seed": 7}
            values[name] = None
            with self.subTest(name=name), self.assertRaises(model.LeanModelError) as caught:
                model.train_heads(train, validation, assoc_only=False, **values)
            self.assertEqual(str(caught.exception), f"training_value_not_frozen:{name}")

    def test_training_is_deterministic_lowers_the_loss_and_keeps_the_best_epoch(self) -> None:
        train, validation = self.records()
        first = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=6, seed=7, assoc_only=False)
        second = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=6, seed=7, assoc_only=False)
        self.assertEqual(first["weights"]["sha256"], second["weights"]["sha256"])
        self.assertFalse(first["diverged"])
        self.assertLess(first["train_curve"][-1], first["train_curve"][0])
        self.assertEqual(first["best_epoch"], int(np.argmin(first["validation_curve"])))
        self.assertEqual(first["weights"]["training"]["best_epoch"], first["best_epoch"])
        self.assertEqual(first["weights"]["training"]["early_stopping"], model.EARLY_STOPPING_RULE)
        other = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=6, seed=8, assoc_only=False)
        self.assertNotEqual(other["weights"]["sha256"], first["weights"]["sha256"])
        # the trained heads separate the synthetic objects: the labelled entity gets the top logit
        scorer = model.LeanScorer(first["heads"])
        hits, total = 0, 0
        for record in validation:
            logits = scorer.association_and_birth_logits(record["stage_a"])
            for fid, target in record["targets"].items():
                if target["status"] != "labelled":
                    continue
                candidates = {c: logits["association_logits"][f"{fid}|{c}"] for c in record["stage_a"]["recall"][fid]}
                candidates[f"{la.BIRTH_COLUMN_PREFIX}{fid}"] = logits["birth_logits"][fid]
                hits += max(candidates, key=candidates.get) == target["target"]
                total += 1
        self.assertGreaterEqual(hits / total, 0.75)
        assoc = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=2, seed=7, assoc_only=True)
        self.assertEqual(sorted(assoc["weights"]["heads"]), ["association", "birth"])
        self.assertTrue(assoc["weights"]["training"]["assoc_only"])

    def test_training_by_updates_reproduces_training_by_epochs_when_aligned(self) -> None:
        """Ruling 81-2: a budget of epochs x updates-per-pass scored every pass is the registered training, bit for bit."""

        train, validation = self.records()
        for assoc_only in (False, True):
            per_pass = model.updates_per_pass(train, assoc_only=assoc_only)
            self.assertGreater(per_pass, 0)
            by_epochs = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=4, seed=7, assoc_only=assoc_only)
            by_updates = model.train_heads_by_updates(train, validation, learning_rate=1e-3, weight_decay=1e-4, update_budget=4 * per_pass,
                                                      evaluate_every=per_pass, seed=7, assoc_only=assoc_only)
            self.assertEqual(by_updates["weights"]["sha256"], by_epochs["weights"]["sha256"], assoc_only)
            self.assertEqual([c["validation"] for c in by_updates["checkpoints"]], by_epochs["validation_curve"])
            self.assertEqual([c["train_mean_since_last_checkpoint"] for c in by_updates["checkpoints"]], by_epochs["train_curve"])
            self.assertEqual(by_updates["best_update"], (by_epochs["best_epoch"] + 1) * per_pass)
            self.assertEqual(by_updates["updates_taken"], 4 * per_pass)
            self.assertEqual(by_updates["weights"]["training"]["early_stopping"], model.UPDATE_BUDGET_RULE)

    def test_training_by_updates_stops_inside_a_pass_and_scores_the_last_update(self) -> None:
        train, validation = self.records()
        per_pass = model.updates_per_pass(train, assoc_only=False)
        out = model.train_heads_by_updates(train, validation, learning_rate=1e-3, weight_decay=1e-4, update_budget=per_pass + 3,
                                           evaluate_every=per_pass, seed=7, assoc_only=False)
        self.assertEqual([c["updates"] for c in out["checkpoints"]], [per_pass, per_pass + 3])
        self.assertEqual([c["pass"] for c in out["checkpoints"]], [1, 2])
        self.assertEqual(out["updates_taken"], per_pass + 3)
        self.assertIn(out["best_update"], (per_pass, per_pass + 3))
        seen = []
        model.train_heads_by_updates(train, validation, learning_rate=1e-3, weight_decay=1e-4, update_budget=5, evaluate_every=2, seed=7,
                                     assoc_only=False, checkpoint_callback=lambda updates, heads: seen.append((updates, heads.training)))
        self.assertEqual(seen, [(2, False), (4, False), (5, False)])
        for name, value in (("update_budget", 0), ("evaluate_every", 0), ("update_budget", None)):
            with self.subTest(name=name), self.assertRaises(model.LeanModelError):
                kwargs = {"update_budget": 4, "evaluate_every": 2, name: value}
                model.train_heads_by_updates(train, validation, learning_rate=1e-3, weight_decay=1e-4, seed=7, assoc_only=False, **kwargs)

    def test_an_epoch_callback_sees_every_epoch_and_changes_nothing(self) -> None:
        """Ruling 79-3 (ii): the read-only per-epoch hook leaves the weights and both curves bit-identical."""

        train, validation = self.records()
        plain = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=4, seed=7, assoc_only=False)
        seen = []

        def callback(epoch, heads):
            self.assertFalse(heads.training)
            seen.append((epoch, model.weights_payload(heads, training={})["sha256"]))

        hooked = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=4, seed=7, assoc_only=False,
                                   epoch_callback=callback)
        self.assertEqual(hooked["weights"]["sha256"], plain["weights"]["sha256"])
        self.assertEqual(hooked["train_curve"], plain["train_curve"])
        self.assertEqual(hooked["validation_curve"], plain["validation_curve"])
        self.assertEqual([epoch for epoch, _ in seen], [0, 1, 2, 3])
        self.assertEqual(dict(seen)[plain["best_epoch"]], plain["weights"]["sha256"])  # the kept weights are that epoch's

    def test_preparing_each_record_once_trains_the_same_weights_as_preparing_it_every_step(self) -> None:
        """2026-09-27: the per-step path (check, copy and tensorise the record at every step) is the reference."""

        import torch

        train, validation = self.records()
        for assoc_only in (False, True):
            fast = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=3, seed=7, assoc_only=assoc_only)
            heads = model.make_heads(assoc_only=assoc_only, seed=7)
            optimiser = torch.optim.AdamW(heads.parameters(), lr=1e-3, weight_decay=1e-4)
            generator = torch.Generator(device="cpu").manual_seed(7)
            best = None
            for epoch in range(3):
                heads.train()
                for index in torch.randperm(len(train), generator=generator).tolist():
                    out = model.frame_loss(heads, train[index])
                    if out["loss"] is None:
                        continue
                    optimiser.zero_grad()
                    out["loss"].backward()
                    optimiser.step()
                heads.eval()
                with torch.no_grad():
                    values = [float(o["loss"].item()) for o in (model.frame_loss(heads, r) for r in validation) if o["loss"] is not None]
                loss = float(np.mean(values))
                if best is None or loss < best[0]:
                    best = (loss, {name: {k: v.detach().clone() for k, v in m.state_dict().items()} for name, m in heads.items()})
                self.assertEqual(fast["validation_curve"][epoch], loss)
            for name, state in best[1].items():
                heads[name].load_state_dict(state)
            for name in heads:
                for key, value in heads[name].state_dict().items():
                    self.assertTrue(torch.equal(value, fast["heads"][name].state_dict()[key]), (assoc_only, name, key))


class RunnerIntegrationTests(unittest.TestCase):
    def test_the_scorer_drives_the_common_runner(self) -> None:
        if str(PROJECT_ROOT / "tests") not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT / "tests"))
        from test_vsmt_lean_runner import CONFIGS, POLICY, scenario  # the hand-built five-frame scenario

        heads = model.make_heads(assoc_only=False, seed=2)
        steps = list(lr.run_episode(scenario(), episode_id="ep-0001", arm="VSMT-lean", config=CONFIGS["VSMT-lean"], policy=POLICY,
                                    descriptor=la.FROZEN_DESCRIPTOR_BASELINE, scorer=model.LeanScorer(heads)))
        summary = lr.episode_summary(steps[-1]["state"], [s["receipt"] for s in steps])
        self.assertEqual(summary["frames"], 5)
        self.assertEqual(summary["illegal_programs"], 0)
        self.assertEqual(summary["atoms"]["BIRTH"] + summary["atoms"]["BIND"] + summary["atoms"]["REACTIVATE"], 8)  # eight fragments over five frames
        assoc = list(lr.run_episode(scenario(), episode_id="ep-0001", arm="AssocOnly", config=CONFIGS["AssocOnly"], policy=POLICY,
                                    descriptor=la.FROZEN_DESCRIPTOR_BASELINE, scorer=model.LeanScorer(model.make_heads(assoc_only=True, seed=2))))
        self.assertEqual(lr.episode_summary(assoc[-1]["state"], [s["receipt"] for s in assoc])["existence_candidates"], 0)


if __name__ == "__main__":
    unittest.main()
