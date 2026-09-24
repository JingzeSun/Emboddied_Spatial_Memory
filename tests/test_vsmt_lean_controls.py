"""D-224 / S2-02 tests: the controls' provenance, the ELU-P fitted quantities and the LLM-op interface.

Pinned here: every rule control and the appendix arm carry a provenance record that matches the
contract's source line and states not-an-official-implementation with no copied upstream code; the
three ELU-P estimators reproduce hand-computed values and refuse degenerate counts instead of
clamping, and the combined fit runs only on the train split after the feature seals at a frozen
rollout_config; the LLM-op rendering is deterministic, covers every sealed row and carries no private
token, the parser accepts exactly one choice per row within the offered options and refuses anything
else, the choices become logits the shared solver honours (with BIRTH as the fallback when two
fragments pick one entity), and the entry refuses every split but validation while the S2-01 runner
refuses the arm altogether.  Standard library plus the lean modules; no model is called.
"""

from __future__ import annotations

import hashlib
import json
import math
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
from vsmt import lean_controls as lc  # noqa: E402
from vsmt import lean_memory as lm  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402

CONTRACT = json.loads((PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json").read_text(encoding="utf-8"))
RECALL = {"local_count": la.RECALL_LOCAL_COUNT, "global_count": la.RECALL_GLOBAL_COUNT, "local_radius_m": la.RECALL_LOCAL_RADIUS_M}
ROLLOUT = {"theta_a": 0.6, "free_space_weight": 1.0, "retract_threshold": -1.0}


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def unit(seed: int, dim: int = 4) -> list[float]:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=dim)
    return [float(v) for v in values / np.linalg.norm(values)]


def fragment(fragment_id: str, *, descriptor: list[float], centroid: list[float]) -> dict[str, Any]:
    return {"fragment_id": fragment_id, "descriptor": list(descriptor), "centroid_m": list(centroid),
            "aabb_min_m": [v - 0.1 for v in centroid], "aabb_max_m": [v + 0.1 for v in centroid],
            "pixel_count": 400, "depth_valid_ratio": 1.0, "supported_by": None}


def stage_a_and_rows() -> tuple[dict[str, Any], list[dict[str, Any]], list[str], dict[str, str]]:
    """Two remembered objects, two fragments (one per object) plus a novel one; every entity has an existence row."""

    mug, book = unit(1), unit(2)
    ops = [{"atom": "BIRTH", "fragment": {k: v for k, v in fragment(f"region:{n}", descriptor=d, centroid=c).items() if k != "depth_valid_ratio"}}
           for n, d, c in (("mug", mug, [0.0, 0.0, 2.0]), ("book", book, [1.0, 0.0, 2.0]))]
    memory = lm.apply_program(lm.empty_memory(episode_id="ep-0001"), {"frame_digest": digest("f1"), "operations": ops},
                              method_id="LLM-op", dormancy_missed_opportunity_limit=2)
    ids = {e["evidence"][0]["fragment_id"].split(":")[1]: str(e["entity_id"]) for e in memory["entities"]}
    frame = {"frame_digest": digest("f2"), "tick": 2, "camera_position_m": [0.0, 1.5, -1.0], "camera_forward": [0.0, 0.0, 1.0],
             "fragments": [fragment("f2:a", descriptor=mug, centroid=[0.0, 0.0, 2.0]), fragment("f2:b", descriptor=book, centroid=[1.0, 0.0, 2.0]),
                           fragment("f2:c", descriptor=unit(9), centroid=[2.0, 0.0, 2.0])],
             "entity_geometry": {eid: {"should_be_visible_ratio": 1.0, "free_space_coverage_ratio": 0.0} for eid in ids.values()}}
    stage_a = la.build_assignment_inputs(frame, memory, birth_neighbourhood_radius_m=la.RECALL_BIRTH_NEIGHBOURHOOD_RADIUS_M, **RECALL)
    solution = la.solve_frame(stage_a, association_logits={f"{r['fragment_id']}|{r['entity_id']}": -1.0 for r in stage_a["association_rows"]},
                              birth_logits={f: 0.0 for f in stage_a["rows"]})
    stage_b = la.seal_solution_and_existence(solution, frame, memory, inputs=stage_a)
    return stage_a, stage_b["existence_rows"], list(stage_b["existence_feature_order"]), ids


class ProvenanceTests(unittest.TestCase):
    def test_every_control_and_the_appendix_arm_have_a_matching_clean_room_record(self) -> None:
        lines = lc.assert_provenance_matches_contract(CONTRACT)
        self.assertEqual(set(lines), set(arms.CONTROL_ARMS) | {arms.APPENDIX_ARM})
        for arm in (*arms.CONTROL_ARMS, arms.APPENDIX_ARM):
            record = lc.provenance(arm)
            self.assertTrue(record["not_an_official_implementation"], arm)
            self.assertFalse(record["upstream_code_copied"], arm)
            self.assertTrue(record["borrowed"] and record["departs"], arm)
        self.assertEqual(lc.provenance("LOW")["inspired_by"], [])
        self.assertTrue(all(url.startswith("https://") for url in lc.provenance("TAF")["source_urls"] + lc.provenance("ELU-P")["source_urls"]))
        with self.assertRaises(lc.LeanControlsError):
            lc.provenance("VSMT-lean")
        broken = json.loads(json.dumps(CONTRACT))
        broken["arms"]["TAF"]["source"] = "official ConceptGraphs"
        with self.assertRaises(lc.LeanControlsError) as caught:
            lc.assert_provenance_matches_contract(broken)
        self.assertEqual(str(caught.exception), "provenance_source_differs:TAF")


class EluPFitTests(unittest.TestCase):
    def test_the_three_estimators_reproduce_hand_values(self) -> None:
        prior = lc.fit_initial_log_odds(in_place_object_frames=90, object_frames=100)
        self.assertAlmostEqual(prior["value"], math.log(0.9 / 0.1))
        decay = lc.fit_persistence_log_decay(intervention_events=3, object_ticks=3000)
        self.assertAlmostEqual(decay["value"], -math.log(1.0 - 0.001))
        gain = lc.fit_match_gain(hit_frames=80, hit_total=100, false_frames=10, false_total=100)
        self.assertAlmostEqual(gain["value"], math.log(0.8 / 0.1))
        zero_hazard = lc.fit_persistence_log_decay(intervention_events=0, object_ticks=10)
        self.assertEqual(zero_hazard["value"], 0.0)

    def test_degenerate_counts_are_refused_not_clamped(self) -> None:
        cases = (
            (lambda: lc.fit_initial_log_odds(in_place_object_frames=0, object_frames=0), "fit_degenerate:no_object_frames"),
            (lambda: lc.fit_initial_log_odds(in_place_object_frames=100, object_frames=100), "fit_degenerate:prior_is_zero_or_one"),
            (lambda: lc.fit_initial_log_odds(in_place_object_frames=0, object_frames=100), "fit_degenerate:prior_is_zero_or_one"),
            (lambda: lc.fit_persistence_log_decay(intervention_events=5, object_ticks=5), "fit_degenerate:hazard_at_or_above_one"),
            (lambda: lc.fit_persistence_log_decay(intervention_events=0, object_ticks=0), "fit_degenerate:no_object_ticks"),
            (lambda: lc.fit_match_gain(hit_frames=80, hit_total=100, false_frames=0, false_total=100), "fit_degenerate:rate_is_zero"),
            (lambda: lc.fit_match_gain(hit_frames=80, hit_total=100, false_frames=10, false_total=0), "fit_degenerate:no_frames"),
            (lambda: lc.fit_match_gain(hit_frames=-1, hit_total=100, false_frames=10, false_total=100), "count_invalid:hit_frames"),
        )
        for call, code in cases:
            with self.subTest(code=code), self.assertRaises(lc.LeanControlsError) as caught:
                call()
            self.assertEqual(str(caught.exception), code)

    def test_the_combined_fit_runs_on_train_after_the_seals_at_the_frozen_rollout_config(self) -> None:
        counts = {"initial_log_odds": {"in_place_object_frames": 90, "object_frames": 100},
                  "persistence_log_decay_per_tick": {"intervention_events": 3, "object_ticks": 3000},
                  "match_gain": {"hit_frames": 80, "hit_total": 100, "false_frames": 10, "false_total": 100}}
        out = lc.fit_elu_p_quantities(counts, split="train", seals_written=True, rollout_config=ROLLOUT)
        self.assertEqual(set(out["values"]), set(arms.ELU_P_FITTED))
        self.assertTrue(out["shared_by_every_elu_p_configuration"])
        self.assertEqual(out["definitions"], lc.ELU_P_DEFINITIONS)
        for kwargs, code in (
            (dict(split="validation", seals_written=True, rollout_config=ROLLOUT), "elu_p_fit_split_not_train:validation"),
            (dict(split="train", seals_written=False, rollout_config=ROLLOUT), "elu_p_fit_before_feature_seals"),
            (dict(split="train", seals_written=True, rollout_config={**ROLLOUT, "theta_a": None}), "rollout_config_value_not_frozen:theta_a"),
        ):
            with self.subTest(code=code), self.assertRaises(lc.LeanControlsError) as caught:
                lc.fit_elu_p_quantities(counts, **kwargs)
            self.assertEqual(str(caught.exception), code)
        partial = {k: v for k, v in counts.items() if k != "match_gain"}
        with self.assertRaises(lc.LeanControlsError):
            lc.fit_elu_p_quantities(partial, split="train", seals_written=True, rollout_config=ROLLOUT)


class LlmOpInterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_a, self.rows, self.order, self.ids = stage_a_and_rows()
        self.eligible = [str(r["entity_id"]) for r in self.rows]

    def answer(self, fragment_choices: Mapping[str, str], existence_choices: Mapping[str, str]) -> str:
        lines = [f"{k} -> {v}" for k, v in fragment_choices.items()] + [f"{k} -> {v}" for k, v in existence_choices.items()]
        return "\n".join(lines) + "\n"

    def test_rendering_is_deterministic_covers_every_row_and_names_no_private_thing(self) -> None:
        text = lc.render_frame_text(self.stage_a, self.rows, existence_feature_order=self.order)
        self.assertEqual(text, lc.render_frame_text(self.stage_a, self.rows, existence_feature_order=self.order))
        for fragment_id in self.stage_a["rows"]:
            self.assertIn(f"FRAGMENT {fragment_id}", text)
        for row in self.stage_a["association_rows"]:
            self.assertIn(f"candidate {row['entity_id']}:", text)
        for entity_id in self.eligible:
            self.assertIn(f"EXISTENCE {entity_id}:", text)
        for name in la.ASSOCIATION_FEATURES + la.BIRTH_FEATURES + la.EXISTENCE_FEATURES:
            self.assertIn(f"{name}=", text)
        for token in ("house", "scene", "object_id", "instance", "private", "Mug", "Book", "procthor"):
            self.assertNotIn(token, text)
        with self.assertRaises(lc.LeanControlsError):
            lc.render_frame_text(self.stage_a, self.rows, existence_feature_order=list(reversed(self.order)))

    def test_parsing_accepts_exactly_one_offered_choice_per_row_and_refuses_the_rest(self) -> None:
        mug, book = self.ids["mug"], self.ids["book"]
        good = self.answer({"f2:a": mug, "f2:b": book, "f2:c": lc.BIRTH_WORD}, {mug: "NOOP", book: "RETRACT"})
        # every entity is an eligible candidate here because the neutral solve birthed everything
        parsed = lc.parse_llm_response(good, self.stage_a, self.eligible)
        self.assertEqual(parsed["fragment_choices"]["f2:c"], lc.BIRTH_WORD)
        self.assertEqual(parsed["existence_choices"][book], "RETRACT")
        bad = (
            (self.answer({"f2:a": mug, "f2:b": book}, {mug: "NOOP", book: "NOOP"}), "fragment_rows_incomplete"),
            (self.answer({"f2:a": mug, "f2:b": book, "f2:c": lc.BIRTH_WORD}, {mug: "NOOP"}), "existence_rows_incomplete"),
            (self.answer({"f2:a": "entity:nowhere", "f2:b": book, "f2:c": lc.BIRTH_WORD}, {mug: "NOOP", book: "NOOP"}), "choice_not_offered:f2:a"),
            (self.answer({"f2:a": mug, "f2:b": book, "f2:c": lc.BIRTH_WORD}, {mug: "DELETE", book: "NOOP"}), "decision_not_retract_or_noop"),
            (good + f"f2:a -> {book}\n", "duplicate_fragment:f2:a"),
            (good + "f9:z -> BIRTH\n", "unknown_row:f9:z"),
            ("garbage without an arrow\n" + good, "line:garbage"),
        )
        for text, detail in bad:
            with self.subTest(detail=detail), self.assertRaises(lc.LeanControlsError) as caught:
                lc.parse_llm_response(text, self.stage_a, self.eligible)
            self.assertIn(detail, str(caught.exception))

    def test_choices_become_logits_the_shared_solver_honours_with_birth_as_the_conflict_fallback(self) -> None:
        mug, book = self.ids["mug"], self.ids["book"]
        logits = lc.choices_to_logits({"f2:a": mug, "f2:b": book, "f2:c": lc.BIRTH_WORD}, self.stage_a)
        solution = la.solve_frame(self.stage_a, **logits)
        self.assertEqual(solution["assignment"], {"f2:a": mug, "f2:b": book, "f2:c": f"{la.BIRTH_COLUMN_PREFIX}f2:c"})
        arms.assert_no_sentinel_chosen(solution["assignment"], logits["association_logits"])
        conflict = lc.choices_to_logits({"f2:a": mug, "f2:b": mug, "f2:c": lc.BIRTH_WORD}, self.stage_a)
        solved = la.solve_frame(self.stage_a, **conflict)
        takers = [f for f, column in solved["assignment"].items() if column == mug]
        self.assertEqual(len(takers), 1)
        other = next(f for f in ("f2:a", "f2:b") if f not in takers)
        self.assertEqual(solved["assignment"][other], f"{la.BIRTH_COLUMN_PREFIX}{other}")
        arms.assert_no_sentinel_chosen(solved["assignment"], conflict["association_logits"])
        with self.assertRaises(lc.LeanControlsError):
            lc.choices_to_logits({"f2:a": mug}, self.stage_a)

    def test_the_entry_runs_on_validation_only_and_the_runner_refuses_the_arm(self) -> None:
        mug, book = self.ids["mug"], self.ids["book"]
        scripted = self.answer({"f2:a": mug, "f2:b": book, "f2:c": lc.BIRTH_WORD}, {mug: "NOOP", book: "RETRACT"})
        seen: list[str] = []

        def llm(prompt: str) -> str:
            seen.append(prompt)
            return scripted

        out = lc.llm_op_frame(self.stage_a, self.rows, existence_feature_order=self.order, llm=llm, split="validation")
        self.assertEqual(out["arm"], "LLM-op")
        self.assertEqual(out["prompt_status"], "not_in_this_stage")
        self.assertEqual(out["decisions"], {mug: "NOOP", book: "RETRACT"})
        self.assertEqual(seen, [out["prompt_text"]])
        program = arms.compile_program(la.solve_frame(self.stage_a, **out["logits"])["assignment"],
                                       {eid: "active" for eid in self.ids.values()}, arm="LLM-op",
                                       existence_decisions={})  # entities assigned this frame carry no existence decision
        self.assertEqual(sorted(op["atom"] for op in program), ["BIND", "BIND", "BIRTH"])
        for split in ("train", "test"):
            with self.subTest(split=split), self.assertRaises(arms.LeanArmsError) as caught:
                lc.llm_op_frame(self.stage_a, self.rows, existence_feature_order=self.order, llm=llm, split=split)
            self.assertEqual(str(caught.exception), f"split_not_allowed:LLM-op:{split}")
        self.assertNotIn("LLM-op", lr.RUNNABLE_ARMS)
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.initial_state(episode_id="ep-0001", arm="LLM-op")
        self.assertEqual(str(caught.exception), "arm_not_runnable_here:LLM-op")


if __name__ == "__main__":
    unittest.main()
