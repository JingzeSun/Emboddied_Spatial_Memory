"""D-224 / S2-05 tests: the read-only node-matching audit over the S2-04 synthetic episode.

Pinned on the five-frame TAF episode of the S2-04 tests (a mug removed and a book moved after the
window, a structural wall): the audit reproduces the evaluator's per-frame node counts under the
current rule, its entity and truth categories partition the predicted and truth totals, the stale
mug entity is counted as such on every frame after the window, the oracle identity grouping never
scores below the current rule, the merged report pools two audits, and a labelled record the
evaluator would disagree with is refused.  CPU only, seconds.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_node_audit as audit_module  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402
from test_vsmt_lean_evaluation import NUISANCE_META, TEACHER_POLICY, episode  # noqa: E402
from test_vsmt_lean_runner import CONFIGS, POLICY  # noqa: E402


def run_audit(arm: str = "TAF"):
    data = episode()
    teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
    captured = audit_module.capture_truth_table(teacher)
    audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"],
                                   groups=audit_module.object_groups(data["table"]))
    frames = []
    labelled_frames = []
    for i, step in enumerate(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=CONFIGS[arm], policy=POLICY, descriptor="vitb14")):
        labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                       label_image=data["images"][i], runtime_s=0.01, peak_memory_bytes=1000)
        labelled_frames.append(labelled)
        frames.append(audit.observe(step, labelled, captured["table"]))
    return audit, frames, labelled_frames, teacher.episode_report()


class NodeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit, cls.frames, cls.labelled, cls.episode = run_audit("TAF")
        cls.report = cls.audit.report()

    def test_the_current_rule_reproduces_the_evaluator_and_the_categories_partition_the_totals(self) -> None:
        current = self.report["rules"]["iou_0.3_secondary"]
        self.assertEqual({k: current[k] for k in ("matched", "predicted", "truth")}, {"matched": 7, "predicted": 10, "truth": 7})
        self.assertEqual(self.report["rules"]["iou_0.3_count_first"]["f1"], self.episode["report"]["node_prf1_iou"]["node_f1"])
        self.assertEqual(self.report["rules"]["identity_centroid_0.5m_or_in_box_0.25m_count_first"]["f1"], self.episode["report"]["node_prf1"]["node_f1"])
        self.assertEqual(sum(self.report["entity_categories"].values()), 10)
        self.assertEqual(sum(self.report["truth_categories"].values()), 7)
        for frame, labelled in zip(self.frames, self.labelled, strict=True):
            # ruling 76 (3)(a): the evaluator matches count-first
            self.assertEqual(frame["rules"]["iou_0.3_count_first"]["matched"], labelled["node_prf1_iou"]["matched"])
            self.assertEqual(frame["rules"]["identity_centroid_0.5m_or_in_box_0.25m_count_first"]["matched"], labelled["node_prf1"]["matched"])  # ruling 77 (1)(a): primary
            self.assertEqual(sum(frame["entity"].values()), labelled["node_prf1"]["predicted"])
            self.assertEqual(sum(frame["truth"].values()), labelled["node_prf1"]["truth"])

    def test_the_stale_mug_entity_is_counted_after_the_window_and_nothing_else_is_lost(self) -> None:
        # TAF never retracts: the mug's entity stays in memory on frames 2-4 while the mug is gone
        self.assertEqual([f["entity"]["own_object_absent_stale"] for f in self.frames], [0, 0, 1, 1, 1])
        self.assertEqual(self.report["entity_categories"]["matched"], 7)
        self.assertEqual(self.report["truth_categories"], {**{name: 0 for name in audit_module.TRUTH_CATEGORIES}, "matched": 7})
        self.assertEqual(self.report["truth_by_group"], {"pickupable": {**{name: 0 for name in audit_module.TRUTH_CATEGORIES}, "matched": 7}})
        self.assertEqual(set(self.report["truth_by_type"]), {"Mug", "Book"})
        # the wall's entity resolves to a present structural key: out of scope, not a prediction
        self.assertEqual(self.report["out_of_scope_entities_per_frame_mean"], 1.0)

    def test_alternative_rules_are_scored_on_the_same_sets_and_the_oracle_grouping_is_an_upper_bound(self) -> None:
        rules = self.report["rules"]
        for rule in audit_module.RULES:
            self.assertEqual(rules[rule]["truth"], 7, rule)
            self.assertLessEqual(rules[rule]["matched"], rules[rule]["truth"], rule)
        self.assertGreaterEqual(rules["iou_0.1"]["matched"], rules["iou_0.3_secondary"]["matched"])
        self.assertGreaterEqual(rules["iou_positive"]["matched"], rules["iou_0.1"]["matched"])
        self.assertGreaterEqual(rules["oracle_identity_groups_iou_0.3"]["matched"], rules["iou_0.3_secondary"]["matched"])
        self.assertLessEqual(rules["oracle_identity_groups_iou_0.3"]["predicted"], rules["iou_0.3_secondary"]["predicted"])
        self.assertEqual(len(self.report["rule_matched_per_frame"]["centroid_within_0.5m"]), 5)

    def test_a_labelled_record_the_evaluator_would_disagree_with_is_refused(self) -> None:
        data = episode()
        teacher = ev.EpisodeTeacher(arm="TAF", geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                    policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
        captured = audit_module.capture_truth_table(teacher)
        audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"])
        step = next(iter(lr.run_episode(data["frames"][:1], episode_id="ep-0001", arm="TAF", config=CONFIGS["TAF"], policy=POLICY, descriptor="vitb14")))
        labelled = teacher.label_frame(step, cache_frame=data["frames"][0], private_record=data["records"][0], masks=data["masks"][0],
                                       label_image=data["images"][0], runtime_s=0.01, peak_memory_bytes=1000)
        broken = copy.deepcopy(labelled)
        broken["node_prf1"]["matched"] += 1
        with self.assertRaises(audit_module.NodeAuditError) as caught:
            audit.observe(step, broken, captured["table"])
        self.assertEqual(str(caught.exception), "audit_disagrees_with_the_labels:matched")

    def test_merge_pools_two_audits_and_refuses_an_empty_root(self) -> None:
        payload = {"schema_version": audit_module.SCHEMA_VERSION, "arm": "TAF", "code_commit": "abc", "episode_id": "ep-0001",
                   "frames": 5, "config": CONFIGS["TAF"], "final_entities_by_state": {"active": 3}, "audit": self.report}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("ep-0001", "ep-0002"):
                (root / name / "TAF").mkdir(parents=True)
                (root / name / "TAF" / audit_module.AUDIT_FILE_NAME).write_text(json.dumps({**payload, "episode_id": name}), encoding="utf-8")
            merged = audit_module.merge_audits(root, "TAF")
            self.assertEqual(merged["episodes"], 2)
            self.assertEqual(merged["pooled_rules"]["iou_0.3_secondary"], {**merged["pooled_rules"]["iou_0.3_secondary"], "matched": 14, "predicted": 20, "truth": 14})
            self.assertEqual(merged["pooled_entity_categories"]["own_object_absent_stale"], 6)
            self.assertFalse(merged["private_ids_exported"])
            with self.assertRaises(audit_module.NodeAuditError):
                audit_module.merge_audits(root, "LOW")


class RulingSeventySixAuditTests(unittest.TestCase):
    """Ruling 76 (1)(a): the centroid ledger, the birth reasons, the dedup tallies and the count-first columns."""

    @classmethod
    def setUpClass(cls) -> None:
        data = episode()
        teacher = ev.EpisodeTeacher(arm="TAF", geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                    policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
        captured = audit_module.capture_truth_table(teacher)
        dedup = {**POLICY["dedup"], "period_ticks": 1}  # every tick, so the five-frame episode is tallied
        cls.audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"],
                                           groups=audit_module.object_groups(data["table"]), arm="TAF", config=CONFIGS["TAF"], dedup=dedup)
        from vsmt import lean_memory as lm

        original = lm._apply_dedup
        cls.audit.fold_capture = audit_module.capture_dedup_folds()
        cls.addClassCleanup(setattr, lm, "_apply_dedup", original)
        cls.births = 0
        cls.frames = []
        policy = {**POLICY, "dedup": dedup}
        for i, step in enumerate(lr.run_episode(data["frames"], episode_id="ep-0001", arm="TAF", config=CONFIGS["TAF"], policy=policy, descriptor="vitb14")):
            labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                           label_image=data["images"][i], runtime_s=0.01, peak_memory_bytes=1000)
            cls.births += step["receipt"]["program"]["atom_counts"]["BIRTH"]
            cls.frames.append(cls.audit.observe(step, labelled, captured["table"]))
        cls.report = cls.audit.report()

    def test_count_first_recovers_the_four_pairs_the_max_weight_matcher_trades_for_distance(self) -> None:
        truth, predicted = [0.0, 0.5, 1.0, 1.5], [0.5, 1.0, 1.5, 2.0]
        weights = [[(1.0 / (1.0 + abs(p - t))) if abs(p - t) <= 0.5 else 0.0 for t in truth] for p in predicted]
        self.assertEqual(len(audit_module.lt._max_weight_matching(weights)), 3)
        self.assertEqual(audit_module._count_first(weights), 4)
        self.assertEqual(audit_module._count_first([]), 0)

    def test_the_centroid_ledger_partitions_the_primary_column_and_count_first_never_matches_fewer(self) -> None:
        rules = self.report["rules"]
        primary = rules["centroid_within_0.5m"]
        self.assertEqual(sum(self.report["centroid_entity_categories"].values()), primary["predicted"])
        self.assertEqual(sum(self.report["centroid_truth_categories"].values()), primary["truth"])
        self.assertEqual(self.report["centroid_entity_categories"]["matched"], primary["matched"])
        self.assertGreaterEqual(rules["centroid_within_0.5m_count_first"]["matched"], primary["matched"])
        self.assertGreaterEqual(rules["iou_0.3_count_first"]["matched"], rules["iou_0.3_secondary"]["matched"])
        # the metric candidates: a wider place test never matches fewer; an identity-restricted one never matches a wrong object
        self.assertGreaterEqual(rules["centroid_0.5m_or_in_box_0.25m_count_first"]["matched"], rules["centroid_within_0.5m_count_first"]["matched"])
        self.assertLessEqual(rules["identity_centroid_0.5m_count_first"]["matched"], rules["centroid_within_0.5m_count_first"]["matched"])
        self.assertEqual(self.report["wrong_identity_matches"]["identity_centroid_0.5m_count_first"], 0)
        self.assertEqual(self.report["wrong_identity_matches"]["identity_centroid_0.5m_or_in_box_0.25m_count_first"], 0)
        # the removed mug's entity is the absent one after the window
        self.assertEqual([f["centroid_entity"]["own_object_absent"] for f in self.frames], [0, 0, 1, 1, 1])

    def test_every_committed_birth_gets_exactly_one_reason_and_the_dedup_ticks_are_tallied(self) -> None:
        reasons = self.report["birth_reasons"]
        self.assertEqual(sum(sum(row.values()) for row in reasons.values()), self.births)
        self.assertGreater(self.births, 0)
        dedup = self.report["dedup"]
        self.assertEqual(dedup["ticks"], 5)
        self.assertEqual(sum(dedup["folds_by_identity"].values()), dedup["folds"])
        self.assertEqual(sum(dedup["folds_by_coobservation"].values()), dedup["folds"])  # v6
        fold = {"canonical": {"evidence": [{"tick": 1}, {"tick": 4}]}, "folded": {"evidence": [{"tick": 2}, {"tick": 4}]}}
        self.assertEqual(audit_module.fold_coobservation(fold), "co_observed")
        fold["folded"]["evidence"] = [{"tick": 2}, {"tick": 3}]
        self.assertEqual(audit_module.fold_coobservation(fold), "never_co_observed")
        self.assertEqual(set(dedup["pairs_after_fold"]), {f"{s}|{i}" for s in audit_module.DEDUP_STATE_PAIRS for i in audit_module.DEDUP_IDENTITIES})
        for row in dedup["pairs_after_fold"].values():
            for count in row["pass"].values():
                self.assertLessEqual(count, row["pairs"])


class RulingSeventyNineExistenceTallyTests(unittest.TestCase):
    """Ruling 79-2: every existence candidate is filed once, with the student's own decision."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.results = {}
        for arm in ("RAC", "TAF"):
            data = episode()
            teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                        policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
            captured = audit_module.capture_truth_table(teacher)
            audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"],
                                           groups=audit_module.object_groups(data["table"]), interventions=teacher.interventions,
                                           window_end=teacher.window_end)
            candidates, retracts, labels = 0, 0, []
            for i, step in enumerate(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=CONFIGS[arm], policy=POLICY, descriptor="vitb14")):
                labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                               label_image=data["images"][i], runtime_s=0.01, peak_memory_bytes=1000)
                candidates += len(labelled["existence_labels"])
                retracts += sum(1 for d in step["receipt"]["existence"]["decisions"].values() if d == "RETRACT")
                labels.extend((labelled["frame_index"], label["status"], label.get("reason")) for label in labelled["existence_labels"].values())
                audit.observe(step, labelled, captured["table"])
            cls.results[arm] = {"report": audit.report(), "candidates": candidates, "retracts": retracts, "labels": labels,
                                "window_end": teacher.window_end, "interventions": dict(teacher.interventions)}

    def test_every_candidate_is_filed_once_with_its_decision(self) -> None:
        for arm, result in self.results.items():
            report = result["report"]
            self.assertEqual(report["existence_tally_fields"], list(audit_module.EXISTENCE_TALLY_FIELDS))
            rows = report["existence_tally"]
            self.assertEqual(sum(row[-1] for row in rows), result["candidates"], arm)
            self.assertGreater(result["candidates"], 0, arm)
            self.assertEqual(sum(row[-1] for row in rows if row[7] == "RETRACT"), result["retracts"], arm)
            self.assertTrue(all(len(row) == len(audit_module.EXISTENCE_TALLY_FIELDS) + 1 for row in rows))
        self.assertEqual(sum(row[-1] for row in self.results["TAF"]["report"]["existence_tally"] if row[7] == "RETRACT"), 0)

    def test_the_labels_and_the_place_test_agree_where_they_must(self) -> None:
        for arm, result in self.results.items():
            for row in result["report"]["existence_tally"]:
                status, reason, klass, phase, in_place, carrier, fragment = row[:7]
                if status == "gone" and reason == "absent":
                    self.assertEqual((in_place, carrier), ("object_absent", "object_absent"))
                if status == "present" and reason == "None":
                    self.assertEqual(in_place, "yes", arm)  # within delta is always in place under the node rule
                if klass != "never_intervened" and klass != "no_key":
                    self.assertIn(klass, set(result["interventions"].values()))
                self.assertIn(phase, ("after_window", "at_or_before_window_end"))
                self.assertIn(fragment, ("yes", "no", "n/a"))
        # the phase follows the evaluator: labels on the last window frame are not after the window
        tally_after = sum(row[-1] for row in self.results["TAF"]["report"]["existence_tally"] if row[3] == "after_window")
        labels_after = sum(1 for frame_index, _, _ in self.results["TAF"]["labels"] if frame_index > self.results["TAF"]["window_end"])
        self.assertEqual(tally_after, labels_after)

    def test_the_sofa_inside_its_box_and_the_book_left_at_its_old_place(self) -> None:
        # a sofa entity 0.7 m from the centre but inside the box, while another entity carries the sofa (a leftover),
        # and a moved book's entity left 2 m from the book with nobody carrying it (a stale version the student retracts)
        audit = audit_module.NodeAudit(evidence={}, iou_min=0.3, delta_moved_m=0.5, interventions={"Book|2": "move"}, window_end=0)
        truth = {"Sofa|1": {"present": True, "in_scope": True, "centroid_m": [0.0, 0.0, 0.0], "aabb_min_m": [-1.0, -0.5, -0.5], "aabb_max_m": [1.0, 0.5, 0.5]},
                 "Book|2": {"present": True, "in_scope": True, "centroid_m": [5.0, 0.0, 0.0], "aabb_min_m": [4.9, -0.1, -0.1], "aabb_max_m": [5.1, 0.1, 0.1]}}
        entity = lambda entity_id, x: {"entity_id": entity_id, "centroid_m": [x, 0.0, 0.0]}  # noqa: E731
        step = {"memory_before": {"entities": [entity("e1", 0.7), entity("e2", 3.0)]},
                "receipt": {"existence": {"decisions": {"e1": "NOOP", "e2": "RETRACT"}}}}
        labelled = {"frame_index": 3, "targets": {"f1": {"key": "Sofa|1"}},
                    "existence_labels": {"e1": {"status": "gone", "key": "Sofa|1", "reason": "moved"},
                                         "e2": {"status": "gone", "key": "Book|2", "reason": "moved"}}}
        predictions = [entity("e1", 0.7), entity("e3", 0.1), entity("e2", 3.0)]
        identities = {"e1": {"resolvable": True, "key": "Sofa|1"}, "e2": {"resolvable": True, "key": "Book|2"}, "e3": {"resolvable": True, "key": "Sofa|1"}}
        audit._tally_existence(step, labelled, truth, predictions, identities)
        self.assertEqual(audit.existence_tally, {
            ("gone", "moved", "never_intervened", "after_window", "yes", "yes", "yes", "NOOP"): 1,
            ("gone", "moved", "move", "after_window", "no", "no", "no", "RETRACT"): 1,
        })
        # without the second sofa entity the first one is the sole carrier: "another" must exclude the candidate itself
        audit.existence_tally.clear()
        audit._tally_existence(step, labelled, truth, [entity("e1", 0.7), entity("e2", 3.0)], identities)
        self.assertIn(("gone", "moved", "never_intervened", "after_window", "yes", "no", "yes", "NOOP"), audit.existence_tally)
        with self.assertRaises(audit_module.NodeAuditError):
            audit._tally_existence({**step, "receipt": {"existence": {"decisions": {"e1": "NOOP"}}}}, labelled, truth, predictions, identities)

    def test_merge_pools_the_tally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.results["RAC"]["report"]
            for episode_id in ("ep-a", "ep-b"):
                (root / episode_id / "RAC").mkdir(parents=True)
                payload = {"schema_version": audit_module.SCHEMA_VERSION, "arm": "RAC", "code_commit": "c", "episode_id": episode_id,
                           "frames": 5, "config": {}, "final_entities_by_state": {}, "report": {"node_prf1": None}, "audit": report}
                (root / episode_id / "RAC" / audit_module.AUDIT_FILE_NAME).write_text(json.dumps(payload), encoding="utf-8")
            merged = audit_module.merge_audits(root, "RAC")
        pooled = {tuple(row[:-1]): row[-1] for row in merged["pooled_existence_tally"]}
        for row in report["existence_tally"]:
            self.assertEqual(pooled[tuple(row[:-1])], 2 * row[-1])


class RulingEightyAssociationTallyTests(unittest.TestCase):
    """Ruling 80-4: every fragment decision is filed once and the tally agrees with the three-way decomposition."""

    @classmethod
    def setUpClass(cls) -> None:
        from vsmt import lean_model as model

        cls.results = {}
        for arm in ("TAF", "VSMT-lean"):
            data = episode()
            teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                        policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
            captured = audit_module.capture_truth_table(teacher)
            audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"],
                                           groups=audit_module.object_groups(data["table"]), interventions=teacher.interventions,
                                           window_end=teacher.window_end)
            scorer = model.LeanScorer(model.make_heads(assoc_only=False, seed=3)) if arm == "VSMT-lean" else None
            fragments, correct, errors = 0, 0, 0
            for i, step in enumerate(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=CONFIGS[arm], policy=POLICY,
                                                    descriptor="vitb14", scorer=scorer)):
                labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                               label_image=data["images"][i], runtime_s=0.01, peak_memory_bytes=1000)
                decomposition = labelled["decomposition"]["association"]
                fragments += decomposition["fragments"]
                correct += decomposition["correct"]
                errors += decomposition["amortization_error"]
                audit.observe(step, labelled, captured["table"])
            cls.results[arm] = {"report": audit.report(), "fragments": fragments, "correct": correct, "errors": errors}

    def test_the_tally_agrees_with_the_decomposition(self) -> None:
        for arm, result in self.results.items():
            report = result["report"]
            self.assertEqual(report["association_tally_fields"], list(audit_module.ASSOCIATION_TALLY_FIELDS))
            rows = report["association_tally"]
            self.assertEqual(sum(row[-1] for row in rows), result["fragments"], arm)
            self.assertGreater(result["fragments"], 0)
            judged = [row for row in rows if row[0] in ("labelled", "birth")]
            self.assertEqual(sum(row[-1] for row in judged if row[1] == "correct"), result["correct"], arm)
            self.assertEqual(sum(row[-1] for row in judged if row[1] != "correct"), result["errors"], arm)
            for row in rows:
                self.assertIn(row[2], ("active", "dormant", "retracted", "birth"), arm)
                self.assertIn(row[3], ("yes", "no", "n/a"), arm)

    def test_a_first_sighting_bound_to_a_dormant_entity_and_a_group_keeper(self) -> None:
        audit = audit_module.NodeAudit(evidence={}, iou_min=0.3, delta_moved_m=0.5)
        audit._keys_before_frame = {"Mug|1"}
        step = {"memory_before": {"entities": [{"entity_id": "e1", "state": "active"}, {"entity_id": "e2", "state": "dormant"}]},
                "receipt": {"assignment": {"f1": "e2", "f2": "birth:f2", "f3": "e1", "f4": "birth:f4"}}}
        labelled = {"targets": {
            "f1": {"status": "birth", "target": "birth:f1", "key": "Lamp|9"},             # first sighting, bound to the dormant e2
            "f2": {"status": "labelled", "target": "e1", "key": "Mug|1"},                 # keeper: born, but its duplicate reached e1
            "f3": {"status": "duplicate_of_labelled", "duplicate_of": "f2", "key": "Mug|1"},
            "f4": {"status": "unlabelled", "target": None, "key": None},
        }}
        audit._tally_association(step, labelled)
        self.assertEqual(audit.association_tally, {
            ("birth", "bind_instead_of_birth", "dormant", "yes"): 1,
            ("labelled", "correct", "active", "no"): 1,
            ("duplicate_of_labelled", "grouped", "active", "no"): 1,
            ("unlabelled", "birth", "birth", "n/a"): 1,
        })


class RulingEightyOneLossTallyTests(unittest.TestCase):
    """Ruling 81-3: loss-of-carrier events, their causes and the absence frames they open."""

    @staticmethod
    def truth(**objects):
        return {key: {"present": True, "in_scope": True, "centroid_m": [x, 0.0, 0.0], "aabb_min_m": [x - 0.1, -0.1, -0.1],
                      "aabb_max_m": [x + 0.1, 0.1, 0.1]} for key, x in objects.items()}

    @staticmethod
    def step(assignment, decisions, entities):
        return {"receipt": {"assignment": assignment, "existence": {"decisions": decisions}},
                "state": {"memory": {"entities": [{"entity_id": e} for e in entities]}}}

    def test_a_wrong_bind_opens_an_interval_a_birth_closes_it_and_a_retract_is_censored(self) -> None:
        audit = audit_module.NodeAudit(evidence={}, iou_min=0.3, delta_moved_m=0.5, interventions={"Book|2": "move"}, window_end=0)
        audit.keys_fragmented = {"Mug|1", "Book|2"}
        mug, book, ambiguous = {"resolvable": True, "key": "Mug|1"}, {"resolvable": True, "key": "Book|2"}, {"resolvable": False, "key": None}
        at = lambda entity_id, x: {"entity_id": entity_id, "centroid_m": [x, 0.0, 0.0]}  # noqa: E731
        truth = self.truth(**{"Mug|1": 0.0, "Book|2": 3.0})
        # frame 0: both objects carried
        audit._tally_losses(self.step({}, {}, ["e1", "e2"]), {"frame_index": 0, "targets": {}}, truth,
                            [at("e1", 0.0), at("e2", 3.0)], {"e1": mug, "e2": book}, [])
        # frame 1: e1 takes a fragment of the book and jumps to it; the mug is left with no carrier
        audit._tally_losses(self.step({"f1": "e1"}, {}, ["e1", "e2"]), {"frame_index": 1, "targets": {"f1": {"key": "Book|2"}}}, truth,
                            [at("e1", 3.0), at("e2", 3.0)], {"e1": ambiguous, "e2": book}, [])
        # frame 2: a new entity is born on the mug (recovered after 1 frame); the student retracts the book's only carrier
        audit._tally_losses(self.step({"f2": "birth:f2"}, {"e2": "RETRACT"}, ["e1", "e2", "e3"]), {"frame_index": 2, "targets": {"f2": {"key": "Mug|1"}}},
                            truth, [at("e1", 3.0), at("e3", 0.0)], {"e1": ambiguous, "e3": mug}, [])
        report = audit._loss_report()
        self.assertEqual(report["events"], [["retract", "move", 1], ["wrong_bind", "never_intervened", 1]])
        self.assertEqual(report["intervals"]["wrong_bind"]["recovered"], 1)
        self.assertEqual(report["intervals"]["wrong_bind"]["frames"], 1)
        self.assertEqual(report["intervals"]["wrong_bind"]["bins"]["1"], 1)
        self.assertEqual(report["intervals"]["retract"]["censored"], 1)
        self.assertEqual(report["uncarried_seen_object_frames"], 2)
        self.assertEqual(report["uncarried_without_loss_event_frames"], 0)
        self.assertEqual(audit.loss_open["Book|2"]["cause"], "retract")  # the report did not close it

    def test_fixture_episodes_keep_the_frame_sums_and_file_the_moved_book(self) -> None:
        for arm in ("TAF", "RAC"):
            data = episode()
            teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                        policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
            captured = audit_module.capture_truth_table(teacher)
            audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"],
                                           groups=audit_module.object_groups(data["table"]), interventions=teacher.interventions,
                                           window_end=teacher.window_end)
            for i, step in enumerate(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=CONFIGS[arm], policy=POLICY, descriptor="vitb14")):
                labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                               label_image=data["images"][i], runtime_s=0.01, peak_memory_bytes=1000)
                audit.observe(step, labelled, captured["table"])
            loss = audit.report()["loss_tally"]
            self.assertTrue(all(row[0] in audit_module.LOSS_CAUSES for row in loss["events"]), arm)
            intervals = loss["intervals"]
            self.assertEqual(sum(row["frames"] for row in intervals.values()) + loss["uncarried_without_loss_event_frames"],
                             loss["uncarried_seen_object_frames"])
            for row in intervals.values():
                self.assertEqual(row["recovered"] + row["object_gone"] + row["censored"], row["intervals"])
            # the book moves after the window and is bound at its new place in the same frame, so it is never uncarried
            self.assertEqual(loss["events"], [], arm)

    def test_v7_the_moved_books_first_reobservation_is_attributed_as_kept(self) -> None:
        for arm in ("TAF", "RAC"):
            data = episode()
            teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                        policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
            captured = audit_module.capture_truth_table(teacher)
            audit = audit_module.NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=TEACHER_POLICY["delta_moved_m"],
                                           groups=audit_module.object_groups(data["table"]), arm=arm, config=CONFIGS[arm],
                                           interventions=teacher.interventions, window_end=teacher.window_end,
                                           carriers_before_move=teacher.carriers_before_move)
            for i, step in enumerate(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=CONFIGS[arm], policy=POLICY, descriptor="vitb14")):
                labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                               label_image=data["images"][i], runtime_s=0.01, peak_memory_bytes=1000)
                audit.observe(step, labelled, captured["table"])
            attribution = audit.report()["identity_attribution"]
            self.assertEqual(len(attribution["records"]), 1, arm)
            record = attribution["records"][0]
            # the book is the second executed intervention (ordinal 1), re-observed on frame 2 and bound to its carrier
            self.assertEqual((record["ordinal"], record["frame_index"], record["category"], record["chosen_kind"]), (1, 2, "kept", "carrier"), arm)
            self.assertEqual(record["teacher_target_kind"], "carrier", arm)
            self.assertEqual(attribution["counts"]["kept"], 1, arm)
            self.assertEqual(sum(attribution["counts"].values()), 1, arm)

    def test_v7_attribution_categories_follow_the_decision_pipeline(self) -> None:
        base = dict(key="Cup|4", states={"e1": "retracted", "e2": "active"}, identities={"e1": {"resolvable": True, "key": "Cup|4"}},
                    recall=["e1", "e2"], target={"status": "labelled", "target": "e1"}, association_logits={"f|e1": 1.0, "f|e2": 3.0},
                    birth_logit=2.0, distances={"e1": 2.4}, fragment_id="f", fragmented_at_move={"Cup|4"},
                    ever_retracted={"e1"}, folded_ids=set(), deleted_ids=set())
        attribute = audit_module.attribute_reobservation
        kept = attribute(carriers=["e1"], chosen="e1", **base)
        self.assertEqual((kept["category"], kept["chosen_kind"]), ("kept", "carrier"))
        self.assertEqual(kept["chosen_carrier_state"], "retracted")  # v8: a REACTIVATE of a retracted carrier
        other = attribute(carriers=["e1"], chosen="e2", **base)
        self.assertEqual((other["category"], other["chosen_kind"], other["best_carrier_state"]), ("chose_other_entity", "other_active", "retracted"))
        self.assertIsNone(other["chosen_carrier_state"])
        self.assertAlmostEqual(other["chosen_minus_best_carrier_logit"], 2.0)
        self.assertTrue(other["carrier_ever_retracted"])
        self.assertEqual(other["best_carrier_distance_m"], 2.4)
        born = attribute(carriers=["e1"], chosen="birth:f", **base)
        self.assertEqual(born["category"], "chose_birth")
        self.assertAlmostEqual(born["chosen_minus_best_carrier_logit"], 1.0)
        missed = attribute(carriers=["e1"], chosen="birth:f", **{**base, "recall": ["e2"]})
        self.assertEqual(missed["category"], "carrier_not_recalled")
        gone = attribute(carriers=["e9"], chosen="birth:f", **{**base, "folded_ids": {"e9"}})
        self.assertEqual((gone["category"], gone["carriers_gone_by"]), ("carrier_gone", ["folded"]))
        deleted = attribute(carriers=["e9"], chosen="birth:f", **{**base, "deleted_ids": {"e9"}})
        self.assertEqual(deleted["carriers_gone_by"], ["deleted"])
        never = attribute(carriers=[], chosen="birth:f", **{**base, "fragmented_at_move": set()})
        self.assertEqual((never["category"], never["no_prior_reason"], never["judged"]), ("no_prior_carrier", "never_fragmented_before_move", False))
        unresolved = attribute(carriers=[], chosen="birth:f", **base)
        self.assertEqual(unresolved["no_prior_reason"], "no_resolving_entity_at_move")

    def test_an_object_moved_away_from_its_unbound_carrier(self) -> None:
        audit = audit_module.NodeAudit(evidence={}, iou_min=0.3, delta_moved_m=0.5, interventions={"Cup|4": "move"}, window_end=0)
        audit.keys_fragmented = {"Cup|4"}
        cup = {"resolvable": True, "key": "Cup|4"}
        carrier = {"entity_id": "e4", "centroid_m": [5.0, 0.0, 0.0]}
        audit._tally_losses(self.step({}, {}, ["e4"]), {"frame_index": 0, "targets": {}}, self.truth(**{"Cup|4": 5.0}), [carrier], {"e4": cup}, [])
        audit._tally_losses(self.step({}, {}, ["e4"]), {"frame_index": 1, "targets": {}}, self.truth(**{"Cup|4": 7.0}), [carrier], {"e4": cup}, [])
        self.assertEqual(audit._loss_report()["events"], [["object_truth_changed", "move", 1]])


if __name__ == "__main__":
    unittest.main()
