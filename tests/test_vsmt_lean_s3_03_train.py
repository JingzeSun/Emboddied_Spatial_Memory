"""S3-03 training (ruling 104): the streamed path trains the same weights as the list path, the entry reads the registered
sources, split and recipe, and refuses what it must not train on.

Pinned here: the streamed encoding statistics equal the whole-matrix ones bit for bit, also beyond numpy's pairwise-summation
block sizes; ``train_heads_streamed`` equals ``train_heads`` in weights, grouped weights, curves and per-epoch terms under the
registered and the ruling 99-1 recipes; ``snapshot_weights`` at the last epoch carries the final digests and the best callback
changes nothing; the checkpoint split of the committed S3 train manifest is 240 / 60 in manifest order; the training settings
are the ruling 99-1 values the evaluated entry used; the entry trains the reference weights from files, writes the receipt
with the per-epoch terms and the best-so-far pointer, and refuses episodes outside the S3 train manifest, two mask sources, a
wrong label source, an unregistered seed, a later seed in round 0 and a sealed root; the probe reports identical.  CPU torch.
"""

from __future__ import annotations

import gzip
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt", PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_model as model  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402
from vsmt import lean_test_seal  # noqa: E402

import s3_03_train as entry  # noqa: E402
from test_vsmt_lean_model import labelled_frame  # noqa: E402

MANIFEST = json.loads((PROJECT_ROOT / "configs" / "vsmt" / "lean_s3_01_manifests.json").read_text(encoding="utf-8"))
RECIPE_99_1 = dict(field_encoding=True, existence_class_weight=True, cosine_min_learning_rate=1e-5, gradient_clip_norm=1.0,
                   existence_prior_correction=True)


def fixture_records() -> tuple[list[dict], list[dict]]:
    train = [labelled_frame(s, drop=("lamp" if s % 2 else None), new=(s % 3 == 0)) for s in range(30, 42)]
    validation = [labelled_frame(s, drop=("book" if s % 2 else None), new=(s % 2 == 0)) for s in range(50, 54)]
    out = []
    for record in train + validation:  # a present label on every row still unlabelled, so both classes occur
        for row in record["existence_rows"]:
            record["existence_labels"].setdefault(str(row["entity_id"]), {"status": "present"})
        out.append(json.loads(json.dumps({k: v for k, v in record.items() if not k.startswith("_")})))
    return out[:12], out[12:]


def synthetic_records(count: int, rows: int, seed: int) -> list[dict]:
    """Records with only the feature tables, many rows each, values spanning signs and magnitudes (counts get clipped)."""

    rng = np.random.default_rng(seed)

    def table(width: int, n: int) -> list[dict]:
        values = rng.lognormal(0.0, 2.0, size=(n, width)) * rng.choice([-1.0, 1.0], size=(n, width))
        return [{"features": [float(v) for v in row]} for row in values]

    return [{"stage_a": {"association_rows": table(14, rows), "birth_rows": table(4, 7)}, "existence_rows": table(17, rows // 2)}
            for _ in range(count)]


class StreamedStatisticsTests(unittest.TestCase):
    def test_the_streamed_statistics_are_the_whole_matrix_statistics(self):
        train, _ = fixture_records()
        self.assertEqual(model.field_encoding_statistics(train), model.field_encoding_statistics_streamed(iter(train)))
        heads = ["association", "birth"]
        self.assertEqual(model.field_encoding_statistics(train, heads=heads), model.field_encoding_statistics_streamed(iter(train), heads=heads))

    def test_bit_for_bit_beyond_the_pairwise_block_sizes(self):
        records = synthetic_records(450, 40, seed=3)  # 18,000 association rows, 9,000 existence rows per column
        whole = model.field_encoding_statistics(records)
        streamed = model.field_encoding_statistics_streamed(iter(records))
        self.assertEqual(whole, streamed)
        self.assertEqual(streamed["association"]["rows"], 18000)
        self.assertEqual(streamed["existence"]["rows"], 9000)


class StreamedTrainingTests(unittest.TestCase):
    def check_same(self, listed: dict, streamed: dict) -> None:
        self.assertEqual(listed["weights"]["sha256"], streamed["weights"]["sha256"])
        self.assertEqual((listed.get("grouped") or {}).get("weights", {}).get("sha256"),
                         (streamed.get("grouped") or {}).get("weights", {}).get("sha256"))
        for key in ("train_curve", "validation_curve", "train_curve_terms", "validation_curve_terms", "best_epoch", "updates_taken"):
            self.assertEqual(listed[key], streamed[key], key)
        self.assertEqual(listed["weights"]["training"], streamed["weights"]["training"])

    def test_the_streamed_path_trains_the_list_path_weights(self):
        train, validation = fixture_records()
        cases = (("registered", False, {}),
                 ("ruling 99-1 VSMT-lean round 1", False, {**RECIPE_99_1, "group_selection": True}),
                 ("ruling 99-1 AssocOnly", True, {**RECIPE_99_1, "existence_class_weight": False}))
        for name, assoc_only, kwargs in cases:
            with self.subTest(name=name):
                values = dict(learning_rate=1e-3, weight_decay=1e-4, epochs=4, seed=7, assoc_only=assoc_only, **kwargs)
                listed = model.train_heads(train, validation, **values)
                fast = model.train_heads_streamed(lambda: iter(train), lambda: iter(validation), optimizer_foreach=True, **values)
                self.check_same(listed, fast)  # ruling 104-7: AdamW foreach is the registered optimizer path bit for bit
                streamed = model.train_heads_streamed(lambda: iter(train), lambda: iter(validation), **values)
                self.check_same(listed, streamed)

    def test_the_best_callback_changes_nothing_and_its_last_snapshot_is_the_result(self):
        train, validation = fixture_records()
        values = dict(learning_rate=1e-3, weight_decay=1e-4, epochs=4, seed=7, assoc_only=False, **RECIPE_99_1, group_selection=True)
        plain = model.train_heads(train, validation, **values)
        snapshots = []
        hooked = model.train_heads(train, validation, **values, best_callback=lambda snapshot: snapshots.append(model.snapshot_weights(snapshot)))
        self.check_same(plain, hooked)
        self.assertEqual(len(snapshots), 4)
        last = snapshots[-1]
        self.assertEqual(last["weights"]["sha256"], plain["weights"]["sha256"])
        self.assertEqual(last["grouped"]["sha256"], plain["grouped"]["weights"]["sha256"])
        self.assertEqual(last["best_epoch"], plain["best_epoch"])
        self.assertEqual(last["best_epoch_by_group"], plain["grouped"]["best_epoch_by_group"])
        for snapshot in snapshots:  # a snapshot whose epochs equal the final ones carries the final digests
            if snapshot["best_epoch_by_group"] == plain["grouped"]["best_epoch_by_group"]:
                self.assertEqual(snapshot["grouped"]["sha256"], plain["grouped"]["weights"]["sha256"])
        model.load_heads(json.loads(json.dumps(last["grouped"])))  # its own digest holds


class AdamWForeachTests(unittest.TestCase):
    """Ruling 104-7: AdamW's foreach path past the step counts where its bias corrections settle (about 37k at beta2 0.999).

    The training tests run a few hundred steps; this runs 45,000 on a tiny model so a torch whose two paths round the bias
    correction differently (e.g. ``x ** 0.5`` against ``math.sqrt``) fails here, at the server's check, before any run.
    """

    def test_forty_five_thousand_steps_bit_for_bit(self):
        import torch

        def run(foreach):
            torch.manual_seed(7)
            params = [torch.nn.Parameter(torch.randn(5)), torch.nn.Parameter(torch.randn(3, 2)), torch.nn.Parameter(torch.randn(1))]
            options = {"foreach": True} if foreach else {}
            optimiser = torch.optim.AdamW(params, lr=1e-3, weight_decay=1e-4, **options)
            for step in range(45_000):
                if step % 2_250 == 0:  # a rate that moves, as the cosine schedule does once per epoch
                    for group in optimiser.param_groups:
                        group["lr"] = 1e-5 + (1e-3 - 1e-5) * (1 + math.cos(math.pi * step / 45_000)) / 2
                for index, param in enumerate(params):
                    param.grad = torch.sin(torch.arange(param.numel(), dtype=torch.float32).reshape(param.shape) * 0.37 + step * 0.013 + index)
                optimiser.step()
            return [param.detach().clone() for param in params]

        for left, right in zip(run(False), run(True)):
            self.assertTrue(torch.equal(left, right))


class S3RulesTests(unittest.TestCase):
    def test_the_checkpoint_split_of_the_committed_manifest(self):
        split = s3.checkpoint_split(MANIFEST["train"])
        self.assertEqual(len(split["training_houses"]), 240)
        self.assertEqual(len(split["selection_houses"]), 60)
        self.assertEqual(split["training_houses"] + split["selection_houses"], MANIFEST["train"])
        with self.assertRaises(s3.LeanS3_03Error):
            s3.checkpoint_split(MANIFEST["train"][:299])
        with self.assertRaises(s3.LeanS3_03Error):
            s3.manifest_houses(MANIFEST, "test")

    def test_the_manifest_split_guard(self):
        self.assertIsNone(s3.manifest_split_refusal(MANIFEST["train"][0], "train"))
        self.assertIsNone(s3.manifest_split_refusal(MANIFEST["validation"][0], "validation"))
        self.assertIn("episode_not_in_the_s3_train_manifest", s3.manifest_split_refusal(MANIFEST["validation"][0], "train"))
        self.assertIn("episode_not_in_the_s3_validation_manifest", s3.manifest_split_refusal(MANIFEST["train"][0], "validation"))
        self.assertIn("split_not_readable_in_s3_03:test", s3.manifest_split_refusal(MANIFEST["test"][0], "test"))
        self.assertEqual(s3.load_manifest(), MANIFEST)

    def test_the_training_settings_are_the_evaluated_recipe(self):
        import argparse

        import ruling89_probes

        evaluated = ruling89_probes.revision_kwargs(argparse.Namespace(revision_91=True))
        contract = json.loads((PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["arms"]["VSMT-lean"]["training"]["s2r_recipe"]["gradient_clip_norm"], s3.GRADIENT_CLIP_NORM)
        for arm in s3.TRAINED_ARMS:
            for round_index in s3.ROUNDS:
                settings = s3.training_settings(arm, round_index)
                for key, value in evaluated.items():
                    self.assertEqual(settings["kwargs"][key], value, (arm, round_index, key))
                self.assertTrue(settings["kwargs"]["field_encoding"])
                self.assertEqual(settings["kwargs"]["existence_class_weight"], arm != "AssocOnly")
                grouped = round_index == 1 and arm in ("VSMT-lean", "HeuristicLabel")
                self.assertEqual(settings["kwargs"]["group_selection"], grouped)
                self.assertEqual(settings["uses"], "grouped" if grouped else "total")
                self.assertEqual(settings["label_source"], "heuristic" if arm == "HeuristicLabel" else "teacher")
        with self.assertRaises(s3.LeanS3_03Error):
            s3.training_settings("NoVersion", 1)  # NoVersion uses VSMT-lean's heads (ruling 99-1)


EPISODES = ("h1", "h2", "h3", "h4")


def synthetic_report(arm: str, index: int, seed: int | None, house: str, *, events: int = 6) -> dict:
    """A report with every headline field, the value a deterministic function of the run and the house."""

    from vsmt import lean_evaluation as ev

    base = (sum(map(ord, arm)) % 7) / 100 + index / 1000 + (seed or 0) / 10000 + int(house[1:]) / 100000
    report = {metric: {field: base} for metric, field in ev.HEADLINE_FIELD.items()}
    for metric in ("identity_continuity", "retrieval_success"):
        report[metric]["events"] = events
    if arm in ("TAF", "LOW", "AssocOnly"):  # never retract: the false-retract rates are undefined everywhere
        report["false_retract_rate"]["false_retract_rate"] = None
        report["false_retract_rate_in_scope"]["false_retract_rate"] = None
    return report


def synthetic_runs(*, skip_seed: tuple[str, int] | None = None) -> list[dict]:
    from vsmt import lean_arms as arms

    runs = []
    for arm, seeded in s3.SELECTION_ARMS.items():
        for index, config in enumerate(arms.enumerate_configs(arm, arms.FROZEN_GRIDS[arm])):
            for seed in (arms.SEEDS if seeded else (None,)):
                if skip_seed is not None and (arm, seed) == skip_seed:
                    continue
                runs.append({"arm": arm, "config_index": index, "config": dict(config), "seed": seed,
                             "reports": {house: synthetic_report(arm, index, seed, house) for house in EPISODES}})
    return runs


class SelectionReadingTests(unittest.TestCase):
    """Ruling 104-1 1f: the validation readings S3-04 selects from."""

    def test_the_readings_exclusions_means_and_reference(self):
        from vsmt import lean_arms as arms

        runs = synthetic_runs()
        self.assertEqual(len(runs), 208)  # 31 learned configurations x 5 seeds + 53 rule configurations
        mrr_undefined = next(r for r in runs if r["arm"] == "RAC" and r["config_index"] == 3)
        mrr_undefined["reports"]["h3"]["missing_residual_rate"]["missing_residual_rate"] = None
        out = s3.selection_readings(runs, mask_source="simulator_instance_masks")
        self.assertEqual(out["metrics"]["missing_residual_rate"]["excluded_houses"], ["h3"])  # one undefined run excludes it for all
        self.assertEqual(out["metrics"]["node_prf1"]["excluded_houses"], [])
        self.assertEqual(out["metrics"]["false_retract_rate"]["not_applicable_arms"], ["AssocOnly", "LOW", "TAF"])
        self.assertEqual(out["metrics"]["false_retract_rate"]["excluded_houses"], [])
        self.assertIsNone(out["readings"]["TAF"]["0"]["mean"]["false_retract_rate"])
        row = out["readings"]["VSMT-lean"]["2"]
        expected = sum(sum(synthetic_report("VSMT-lean", 2, seed, h)["node_prf1"]["node_f1"] for h in EPISODES) / 4 for seed in arms.SEEDS) / 5
        self.assertAlmostEqual(row["mean"]["node_prf1"], expected, places=15)
        self.assertEqual(row["seeds_present"], list(arms.SEEDS))
        self.assertEqual(row["seeds_missing"], [])
        mrr = sum(synthetic_report("RAC", 3, None, h)["missing_residual_rate"]["missing_residual_rate"] for h in ("h1", "h2", "h4")) / 3
        self.assertAlmostEqual(out["readings"]["RAC"]["3"]["mean"]["missing_residual_rate"], mrr, places=15)
        self.assertEqual(out["reference"]["arm"], "AssocOnly")
        self.assertEqual(out["reference"]["missing_residual_rate"], out["readings"]["AssocOnly"]["0"]["mean"]["missing_residual_rate"])
        self.assertEqual(out["key_events"]["missing_residual_rate_houses"], 3)
        self.assertTrue(out["key_events"]["identity_continuity"]["equal_across_runs"])
        for arm in s3.SELECTION_ARMS:  # the inputs are what select_configuration takes
            choice = arms.select_configuration(s3.selection_validation(out, arm), arm=arm,
                                               reference_missing_residual_rate=out["reference"]["missing_residual_rate"])
            self.assertIn(choice["selected"], range(len(out["readings"][arm])))
        self.assertEqual(json.loads(json.dumps(out)), out)  # JSON as written

    def test_a_missing_seed_is_named_and_the_mean_uses_the_seeds_present(self):
        out = s3.selection_readings(synthetic_runs(skip_seed=("NoVersion", 31)), mask_source="sam2")
        row = out["readings"]["NoVersion"]["0"]
        self.assertEqual(row["seeds_missing"], [31])
        self.assertEqual(row["seeds_present"], [7, 19, 43, 59])
        self.assertAlmostEqual(row["mean"]["node_prf1"], sum(v["node_prf1"] for v in row["per_seed"].values()) / 4, places=15)

    def test_refusals(self):
        runs = synthetic_runs()
        with self.assertRaisesRegex(s3.LeanS3_03Error, "selection_runs_incomplete:LOW"):
            s3.selection_readings([r for r in runs if not (r["arm"] == "LOW" and r["config_index"] == 4)], mask_source="sam2")
        with self.assertRaisesRegex(s3.LeanS3_03Error, "selection_run_duplicated"):
            s3.selection_readings(runs + [runs[0]], mask_source="sam2")
        changed = [dict(r) for r in runs]
        changed[5] = {**changed[5], "reports": {h: v for h, v in changed[5]["reports"].items() if h != "h4"}}
        with self.assertRaisesRegex(s3.LeanS3_03Error, "selection_runs_cover_different_episodes"):
            s3.selection_readings(changed, mask_source="sam2")
        wrong = [dict(r) for r in runs]
        taf = next(i for i, r in enumerate(wrong) if r["arm"] == "TAF")
        wrong[taf] = {**wrong[taf], "config": {"theta_a": 0.65, "d_a": None}}
        with self.assertRaisesRegex(s3.LeanS3_03Error, "selection_config_not_the_grid_member"):
            s3.selection_readings(wrong, mask_source="sam2")
        seeded_rule = [dict(r) for r in runs]
        seeded_rule[taf] = {**seeded_rule[taf], "seed": 7}
        with self.assertRaisesRegex(s3.LeanS3_03Error, "selection_seed_invalid:TAF"):
            s3.selection_readings(seeded_rule, mask_source="sam2")

    def test_an_arm_without_any_run_is_named_and_left_out(self):
        from vsmt import lean_arms as arms

        runs = [r for r in synthetic_runs() if r["arm"] != "AssocOnly"]
        with self.assertRaisesRegex(s3.LeanS3_03Error, "selection_runs_incomplete:AssocOnly"):
            s3.selection_readings(runs, mask_source="sam2")
        out = s3.selection_readings(runs, mask_source="sam2", absent_arms={"AssocOnly": "every seed diverged in round 0"})
        self.assertEqual(out["arms_absent"], {"AssocOnly": "every seed diverged in round 0"})
        self.assertNotIn("AssocOnly", out["readings"])
        self.assertIsNone(out["reference"]["missing_residual_rate"])
        choice = arms.select_configuration(s3.selection_validation(out, "VSMT-lean"), arm="VSMT-lean",
                                           reference_missing_residual_rate=out["reference"]["missing_residual_rate"])
        self.assertEqual(choice["reason"], "reference_missing_residual_rate_undefined")
        with self.assertRaisesRegex(s3.LeanS3_03Error, "selection_absent_arm_has_runs"):
            s3.selection_readings(synthetic_runs(), mask_source="sam2", absent_arms={"AssocOnly": "x"})

    def test_events_that_differ_between_runs_are_reported(self):
        runs = synthetic_runs()
        runs[0]["reports"]["h1"]["identity_continuity"]["events"] = 7
        out = s3.selection_readings(runs, mask_source="sam2")
        self.assertFalse(out["key_events"]["identity_continuity"]["equal_across_runs"])
        self.assertEqual(out["key_events"]["identity_continuity"]["events_per_run"], [24, 25])
        self.assertTrue(out["key_events"]["retrieval_success"]["equal_across_runs"])


class EntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.train, self.validation = fixture_records()
        self.training_houses = sorted(MANIFEST["train"][:3])
        self.selection_houses = sorted(MANIFEST["train"][240:242])

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_pass(self, name: str, arm: str, *, mask_source: str = "simulator_instance_masks", file: str = "training_records.jsonl.gz",
                   extra_house: str | None = None) -> Path:
        root = self.tmp / name
        chunks = {house: self.train[i * 4:(i + 1) * 4] for i, house in enumerate(self.training_houses)}
        chunks.update({house: self.validation[i * 2:(i + 1) * 2] for i, house in enumerate(self.selection_houses)})
        if extra_house is not None:
            chunks[extra_house] = self.train[:1]
        for house, records in chunks.items():
            folder = root / house / arm
            folder.mkdir(parents=True)
            (folder / "receipt.json").write_text(json.dumps({"status": "succeeded", "mask_source": mask_source}), encoding="utf-8")
            with gzip.open(folder / file, "wt", encoding="utf-8") as handle:
                for tick, record in enumerate(records, start=1):
                    handle.write(json.dumps({"tick": tick, **record}) + "\n")
        return root

    def reference(self, sources: list[tuple[Path, str]], *, file: str = "training_records.jsonl.gz") -> tuple[list[dict], list[dict]]:
        train, validation = [], []
        for root, arm in sources:
            for house in sorted(p.name for p in root.iterdir()):
                rows = list(entry.read_records(root / house / arm / file))
                (train if house in self.training_houses else validation).extend(rows)
        return train, validation

    def test_the_entry_trains_the_reference_weights_and_writes_the_receipt(self):
        round0 = self.write_pass("dagger_round_0", "ELU-P")
        round1 = self.write_pass("dagger_round_1", "VSMT-lean")
        out = self.tmp / "training" / "round1" / "VSMT-lean" / "A7"
        code = entry.main(["train", "--source", f"{round0}:ELU-P:teacher", "--source", f"{round1}:VSMT-lean:teacher",
                           "--arm", "VSMT-lean", "--round", "1", "--seed", "7", "--out-dir", str(out), "--threads", "1", "--best-so-far",
                           "--foreach"])
        self.assertEqual(code, 0)
        receipt = json.loads((out / "training_receipt.json").read_text(encoding="utf-8"))
        train, validation = self.reference([(round0, "ELU-P"), (round1, "VSMT-lean")])
        expected = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=20, seed=7, assoc_only=False,
                                     **RECIPE_99_1, group_selection=True)
        self.assertEqual(receipt["weights_sha256"], expected["weights"]["sha256"])  # the registered path, trained here with foreach
        self.assertTrue(receipt["optimizer_foreach"])
        self.assertEqual(receipt["group_selection"]["weights_sha256"], expected["grouped"]["weights"]["sha256"])
        self.assertEqual(receipt["validation_curve_terms"], expected["validation_curve_terms"])
        self.assertEqual(len(receipt["train_curve_terms"]), 20)
        self.assertEqual(receipt["split"]["training_houses_present"], 3)
        self.assertEqual(receipt["split"]["selection_houses_present"], 2)
        self.assertEqual(len(receipt["split"]["training_houses_absent"]), 237)
        self.assertEqual(receipt["mask_source"], "simulator_instance_masks")
        self.assertEqual(receipt["uses"], "grouped")
        self.assertEqual(len(receipt["files"]), 10)
        pointer = json.loads((out / "best_so_far" / "pointer.json").read_text(encoding="utf-8"))
        self.assertEqual(pointer["epoch"], 19)
        self.assertEqual(pointer["grouped"]["sha256"], receipt["group_selection"]["weights_sha256"])
        self.assertTrue((out / pointer["grouped"]["file"]).exists())
        saved = json.loads((out / "weights_grouped.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["sha256"], receipt["group_selection"]["weights_sha256"])
        self.assertEqual(entry.main(["train", "--source", f"{round0}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "1", "--seed", "7",
                                     "--out-dir", str(out), "--threads", "1"]), 2)  # never over an existing receipt

    def test_assoc_only_round_0_keeps_one_selection(self):
        round0 = self.write_pass("dagger_round_0", "ELU-P")
        out = self.tmp / "training" / "round0" / "AssocOnly"
        self.assertEqual(entry.main(["train", "--source", f"{round0}:ELU-P:teacher", "--arm", "AssocOnly", "--round", "0", "--seed", "7",
                                     "--out-dir", str(out), "--threads", "1"]), 0)
        receipt = json.loads((out / "training_receipt.json").read_text(encoding="utf-8"))
        self.assertIsNone(receipt["group_selection"])
        self.assertFalse((out / "weights_grouped.json").exists())
        self.assertTrue(receipt["assoc_only"])
        self.assertEqual(receipt["uses"], "total")

    def test_heuristic_label_trains_on_its_own_records(self):
        heuristic = self.write_pass("dagger_round_0", "ELU-P", file="heuristic_training_records.jsonl.gz")
        out = self.tmp / "training" / "round0" / "HeuristicLabel"
        self.assertEqual(entry.main(["train", "--source", f"{heuristic}:ELU-P:heuristic", "--arm", "HeuristicLabel", "--round", "0",
                                     "--seed", "7", "--out-dir", str(out), "--threads", "1"]), 0)
        receipt = json.loads((out / "training_receipt.json").read_text(encoding="utf-8"))
        train, validation = self.reference([(heuristic, "ELU-P")], file="heuristic_training_records.jsonl.gz")
        expected = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=20, seed=7, assoc_only=False,
                                     **RECIPE_99_1)
        self.assertEqual(receipt["weights_sha256"], expected["weights"]["sha256"])
        self.assertEqual(receipt["label_source"], "heuristic")
        self.assertIsNone(receipt["group_selection"])  # round 0 keeps the total-loss selection

    def test_refusals(self):
        round0 = self.write_pass("dagger_round_0", "ELU-P")
        out = str(self.tmp / "out")
        base = ["train", "--arm", "VSMT-lean", "--round", "0", "--seed", "7", "--out-dir", out, "--threads", "1"]
        self.assertEqual(entry.main(base[:3] + ["--source", f"{round0}:ELU-P:heuristic"] + base[3:]), 2)  # wrong label source
        heuristic = self.write_pass("heuristic_round_0", "ELU-P", file="heuristic_training_records.jsonl.gz")
        self.assertEqual(entry.main(["train", "--source", f"{heuristic}:ELU-P:teacher", "--arm", "HeuristicLabel", "--round", "0",
                                     "--seed", "7", "--out-dir", out, "--threads", "1"]), 2)  # HeuristicLabel reads its own records
        self.assertEqual(entry.main(["train", "--source", f"{round0}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "0",
                                     "--seed", "8", "--out-dir", out, "--threads", "1"]), 2)  # an unregistered seed
        self.assertEqual(entry.main(["train", "--source", f"{round0}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "0",
                                     "--seed", "19", "--out-dir", out, "--threads", "1"]), 2)  # round 0 trains once, at seed 7
        outside = self.write_pass("outside", "ELU-P", extra_house=MANIFEST["validation"][0])
        self.assertEqual(entry.main(["train", "--source", f"{outside}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "0",
                                     "--seed", "7", "--out-dir", out, "--threads", "1"]), 2)  # a validation house is never trained on
        sam2 = self.write_pass("sam2_round_1", "VSMT-lean", mask_source="sam2")
        self.assertEqual(entry.main(["train", "--source", f"{round0}:ELU-P:teacher", "--source", f"{sam2}:VSMT-lean:teacher",
                                     "--arm", "VSMT-lean", "--round", "1", "--seed", "7", "--out-dir", out, "--threads", "1"]), 2)
        lean_test_seal.write_marker(self.tmp, kind="raw", state=lean_test_seal.STATE_PENDING)  # a source under a sealed root
        self.assertEqual(entry.main(["train", "--source", f"{round0}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "0",
                                     "--seed", "7", "--out-dir", out, "--threads", "1"]), 2)
        self.assertFalse(Path(out, "training_receipt.json").exists())

    def test_the_timing_output_feeds_the_thread_choice(self):
        import s3_03_jobs

        round0 = self.write_pass("dagger_round_0", "ELU-P")
        out = self.tmp / "timing.json"
        self.assertEqual(entry.main(["time", "--source", f"{round0}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "0",
                                     "--houses", "2", "--threads", "1,2", "--out", str(out)]), 0)
        timing = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual([row["threads"] for row in timing["timings"]], [1, 2])
        self.assertEqual(timing["timings"][1]["thread_settings"]["requested"], 2)
        choice = s3_03_jobs.choose_train_threads({row["threads"]: row["epoch_seconds"] for row in timing["timings"]}, cores=8)
        self.assertIn(choice["train_threads"], (1, 2))

    def test_the_probe_reports_identical(self):
        round0 = self.write_pass("dagger_round_0", "ELU-P")
        probe = self.tmp / "probe.json"
        self.assertEqual(entry.main(["probe", "--source", f"{round0}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "0",
                                     "--houses", "2", "--epochs", "2", "--threads", "1", "--out", str(probe), "--foreach"]), 0)
        report = json.loads(probe.read_text(encoding="utf-8"))
        self.assertTrue(report["identical"])
        self.assertTrue(report["optimizer_foreach"])
        self.assertEqual(len(report["houses"]), 3)  # two training houses and one selection house


if __name__ == "__main__":
    unittest.main()
