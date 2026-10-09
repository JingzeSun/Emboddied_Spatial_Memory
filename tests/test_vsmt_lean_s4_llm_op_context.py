"""Tests for ops/vsmt/s4_llm_op_context.py (S4 E1, the read-only context rows of the LLM-op table, paper Table III).

With two fake validation episodes, fake merged audits of the nine arms and fake cache receipts: the script reads the files of
the frozen configurations, averages learned arms over seeds first, computes the percentile as the share below plus half the
share equal, reports a problem when a mean does not match the reading export, and refuses to run with a front end missing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("s4_llm_op_context", ROOT / "ops" / "vsmt" / "s4_llm_op_context.py")
ctx = importlib.util.module_from_spec(SPEC)
sys.modules["s4_llm_op_context"] = ctx
SPEC.loader.exec_module(ctx)

EPISODES = ("procthor10k-0.1.2-train-08800", "procthor10k-0.1.2-train-00269")


def report(f1: float, frr: float | None, auc: float) -> dict:
    return {"node_prf1": {"node_f1": f1}, "node_prf1_iou": {"node_f1": f1 / 2},
            "false_retract_rate": {"false_retract_rate": frr}, "contamination_auc": {"contamination_auc": auc}}


def merged(arm: str, front: str, base: float) -> dict:
    return {"arm": arm, "mask_source": ctx.MASK_SOURCE[front], "per_episode": [
        {"episode_id": EPISODES[0], "report": report(base, None, 0.3), "final_entities_by_state": {"active": 4, "dormant": 2}},
        {"episode_id": EPISODES[1], "report": report(base + 0.2, 0.5, 0.5), "final_entities_by_state": {"active": 8, "dormant": 0}},
    ]}


class Fixture:
    """A temporary S3-03 run root, cache root, freeze, readings and LLM-op export for one front end."""

    def __init__(self, directory: Path, front: str = "instance", skew: float = 0.0) -> None:
        self.run_root = directory / "run"
        self.cache_root = directory / "cache"
        self.freeze = {"fronts": {front: {"selection": {"arms": {}}}}}
        self.readings = {"episodes": list(EPISODES), "readings": {}}
        for index, arm in enumerate(ctx.ARMS):
            config = index % 3
            self.freeze["fronts"][front]["selection"]["arms"][arm] = {"selected": config, "config": {"x": config}}
            base = 0.4 + 0.01 * index
            for path in ctx.run_files(self.run_root, front, arm, config):
                path.parent.mkdir(parents=True, exist_ok=True)
                seed_shift = 0.0 if arm not in ctx.SEEDED else 0.001 * (int(path.stem.rsplit("-s", 1)[1]) - 31)
                path.write_text(json.dumps(merged(arm, front, base + seed_shift)), encoding="utf-8")
            mean_f1 = base + 0.1 + (0.0 if arm not in ctx.SEEDED else 0.001 * (sum(ctx.SEEDS) / 5 - 31))
            self.readings["readings"][arm] = {str(config): {"mean": {
                "node_prf1": mean_f1 + skew, "node_prf1_iou": mean_f1 / 2, "contamination_auc": 0.4}}}
        for name, (frames, fragments) in zip(EPISODES, ((430, 3964), (3872, 30000))):
            path = self.cache_root / "validation" / name / "receipt.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"frames": frames, "fragments": fragments}), encoding="utf-8")
        self.llm_op = {"fronts": {front: {"episodes": [{"episode_id": EPISODES[0], "report": report(0.696, 0.976, 0.49)}]}}}

    def context(self, front: str = "instance") -> tuple[dict, list[str]]:
        problems: list[str] = []
        out = ctx.front_context(front, self.run_root, self.cache_root, self.freeze, self.readings, self.llm_op, {}, problems)
        return out, problems


class PercentileTests(unittest.TestCase):
    def test_mid_rank(self) -> None:
        self.assertEqual(ctx.percentile(2.0, [1.0, 2.0, 3.0, 4.0]), 37.5)
        self.assertEqual(ctx.percentile(0.0, [1.0, 2.0]), 0.0)
        self.assertEqual(ctx.percentile(5.0, [1.0, 2.0]), 100.0)

    def test_summary_skips_undefined(self) -> None:
        out = ctx.summary({"a": None, "b": 0.5, "c": 0.7}, "a")
        self.assertIsNone(out["episode_value"])
        self.assertIsNone(out["episode_percentile"])
        self.assertEqual(out["episodes_defined"], 2)
        self.assertAlmostEqual(out["validation_mean"], 0.6)


class FrontContextTests(unittest.TestCase):
    def test_values_percentiles_and_episode_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp))
            out, problems = fixture.context()
        self.assertEqual(problems, [])
        self.assertEqual(out["episode_id"], EPISODES[0])
        self.assertEqual(out["llm_op"]["node_f1"], 0.696)
        taf = out["arms"]["TAF"]
        self.assertEqual(taf["config_index"], ctx.ARMS.index("TAF") % 3)
        self.assertAlmostEqual(taf["node_f1"]["episode_value"], 0.4 + 0.01 * ctx.ARMS.index("TAF"))
        self.assertEqual(taf["node_f1"]["episode_percentile"], 25.0)  # lowest of two: half of its own rank
        self.assertIsNone(taf["false_retract_rate"]["episode_value"])
        self.assertEqual(out["episode"]["frames"], 430)
        self.assertEqual(out["episode"]["frames_percentile"], 25.0)
        self.assertAlmostEqual(out["episode"]["vsmt_lean_entities_in_memory_at_end"], 6.0)

    def test_learned_arm_is_the_seed_mean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = Fixture(Path(tmp)).context()
        self.assertEqual(len(out["arms"]["VSMT-lean"]["runs"]), 5)
        expected = 0.4 + 0.001 * (sum(ctx.SEEDS) / 5 - 31)
        self.assertAlmostEqual(out["arms"]["VSMT-lean"]["node_f1"]["episode_value"], expected)

    def test_reading_mismatch_is_a_problem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, problems = Fixture(Path(tmp), skew=0.01).context()
        self.assertEqual(len(problems), len(ctx.ARMS))
        self.assertTrue(all("node_prf1" in problem for problem in problems))

    def test_wrong_arm_in_file_is_a_problem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp))
            path = ctx.run_files(fixture.run_root, "instance", "LOW", ctx.ARMS.index("LOW") % 3)[0]
            data = json.loads(path.read_text(encoding="utf-8"))
            data["arm"] = "TAF"
            path.write_text(json.dumps(data), encoding="utf-8")
            _, problems = fixture.context()
        self.assertTrue(any("LOW" in problem and "arm" in problem for problem in problems))


class MainTests(unittest.TestCase):
    def test_missing_cache_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = ctx.main(["--run-root", tmp, "--cache-root", f"instance={tmp}", "--out-dir", tmp])
        self.assertEqual(code, ctx.EXIT_REFUSED)


class SealGuardTests(unittest.TestCase):
    """The guard covers the validation directory it reads, so a sealed test root beside it does not refuse the run."""

    def setUp(self) -> None:
        if str(ROOT / "src") not in sys.path:
            sys.path.insert(0, str(ROOT / "src"))
        from vsmt import lean_test_seal

        self.seal = lean_test_seal
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_root = Path(self.tmp.name) / "cache"
        (self.cache_root / "validation").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_sealed_test_root_beside_validation_does_not_refuse(self) -> None:
        self.seal.write_marker(self.cache_root / "test", kind="instance_cache", state=self.seal.STATE_PENDING)
        self.assertIsNotNone(self.seal.refusal([self.cache_root], reader="x"))  # the parent itself is covered
        self.assertIsNone(ctx.sealed_refusal([self.cache_root / "validation"]))

    def test_a_marker_on_the_read_directory_refuses(self) -> None:
        self.seal.write_marker(self.cache_root / "validation", kind="instance_cache", state=self.seal.STATE_PENDING)
        refusal = ctx.sealed_refusal([self.cache_root / "validation"])
        self.assertIsNotNone(refusal)
        self.assertIn("s4-llm-op-context", refusal)


if __name__ == "__main__":
    unittest.main()
