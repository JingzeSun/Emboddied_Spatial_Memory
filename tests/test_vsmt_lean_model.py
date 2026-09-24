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
        self.assertEqual(counts["total"], 54207)
        assoc = model.make_heads(assoc_only=True, seed=0)
        self.assertEqual(set(assoc.keys()), {"association", "birth"})
        self.assertTrue(model.is_assoc_only(assoc))
        self.assertFalse(model.is_assoc_only(heads))

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
