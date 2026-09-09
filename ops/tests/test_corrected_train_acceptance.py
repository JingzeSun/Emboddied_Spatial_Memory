"""Test the actual ops validators without generation, training, or large arrays."""
import ast
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SHELL = (ROOT / "ops/run_next_server_step.sh").read_text(encoding="utf-8")
PYTHON = SHELL.split("<<'PY_GENERATE'", 1)[1].split("\n", 1)[1].split("\nPY_GENERATE", 1)[0]
TREE = ast.parse(PYTHON)


def require(condition, message):
    if not condition:
        raise ValueError(message)


NAMES = {"validate_manifest_header", "validate_learning_counts", "require_accept_only_prerequisites", "validate_family_support"}
NAMESPACE = {"require": require}
exec(compile(ast.Module(body=[node for node in TREE.body if isinstance(node, ast.FunctionDef)
                             and node.name in NAMES], type_ignores=[]), "actual_ops_validators", "exec"), NAMESPACE)


def manifest():
    return {"schema_version": "cpmt-m1-generation-manifest-v5", "split": "train",
            "paired_groups_total": 1000, "configured_paired_groups_for_split": 1000,
            "protocol_sha256": "fixed-protocol", "dataset_version": "fixed-dataset",
            "decisions": 40000, "online_chain_decisions": 38000, "recovery_training_examples": 2000,
            "retained_shard_count": 1000, "formal_run": False, "test_generated": False}


def arrays():
    # Tiny metadata vectors only, not feature tensors or actual train samples.
    return {"group": np.repeat(np.arange(1000), 40), "y": np.zeros(40000, dtype=np.int64),
            "recovery": np.tile([False] * 38 + [True] * 2, 1000)}


class TestCorrectedTrainAcceptance(unittest.TestCase):
    def header(self, value):
        NAMESPACE["validate_manifest_header"](value, {"protocol_sha256": "fixed-protocol"},
                                               {"data": {"dataset_version": "fixed-dataset"}})

    def test_existing_encoder_counts_are_accepted(self):
        self.header(manifest())
        value = arrays(); before = deepcopy(value)
        NAMESPACE["validate_learning_counts"](value, manifest())
        for key in value:
            np.testing.assert_array_equal(value[key], before[key])

    def test_old_wrong_count_and_wrong_binding_fail_with_field_detail(self):
        for key, changed in (("online_chain_decisions", 40000), ("protocol_sha256", "old"),
                             ("dataset_version", "old"), ("split", "validation"),
                             ("recovery_training_examples", 0), ("retained_shard_count", 999)):
            with self.subTest(key=key):
                value = manifest(); value[key] = changed
                with self.assertRaisesRegex(ValueError, key):
                    self.header(value)

    def test_equal_total_cannot_hide_missing_recovery_in_one_group(self):
        value = arrays()
        # Preserve global totals while moving one recovery flag from group 0 to 1.
        value["recovery"][38] = False
        value["recovery"][40] = True
        with self.assertRaisesRegex(ValueError, "38 reference"):
            NAMESPACE["validate_learning_counts"](value, manifest())

    def test_missing_group_is_rejected_even_with_same_row_total(self):
        value = arrays(); value["group"][value["group"] == 999] = 998
        with self.assertRaisesRegex(ValueError, "incomplete paired"):
            NAMESPACE["validate_learning_counts"](value, manifest())

    def test_out_of_range_and_non_boolean_flags_are_rejected(self):
        value = arrays(); value["group"][0] = -1
        with self.assertRaisesRegex(ValueError, "out of range"):
            NAMESPACE["validate_learning_counts"](value, manifest())
        value = arrays(); value["recovery"] = value["recovery"].astype(int)
        with self.assertRaisesRegex(ValueError, "invalid group/recovery"):
            NAMESPACE["validate_learning_counts"](value, manifest())

    def test_row_count_disagreement_is_rejected(self):
        value = arrays(); value["y"] = value["y"][:-1]
        with self.assertRaisesRegex(ValueError, "learning row count"):
            NAMESPACE["validate_learning_counts"](value, manifest())

    def family_fixture(self):
        value = arrays()
        value["scenario_family_index"] = np.tile(np.arange(40) % 12, 1000)
        # In this toy learning table, family C03 is absent from group 0.
        value["scenario_family_index"][[3, 15, 27]] = 0
        families = [f"C{i:02d}" for i in range(12)]
        report = manifest()
        report.update(configured_scenario_families=families,
                      causal_paired_group_support_by_family=dict.fromkeys(families, 1000),
                      learning_group_support_by_family={f: 999 if f == "C03" else 1000 for f in families})
        return value, report, {"data": {"scenario_families": families}}

    def test_learning_family_coverage_can_be_lower_than_causal_coverage(self):
        NAMESPACE["validate_family_support"](*self.family_fixture())

    def test_overstated_learning_coverage_is_rejected(self):
        value, report, hard = self.family_fixture()
        report["learning_group_support_by_family"]["C03"] = 1000
        with self.assertRaisesRegex(ValueError, "differs from encoded rows"):
            NAMESPACE["validate_family_support"](value, report, hard)

    def test_causal_family_requirement_is_not_relaxed(self):
        value, report, hard = self.family_fixture()
        report["causal_paired_group_support_by_family"]["C03"] = 999
        with self.assertRaisesRegex(ValueError, "causal family coverage mismatch"):
            NAMESPACE["validate_family_support"](value, report, hard)

    def test_accept_only_requires_preexisting_attempt_and_exit(self):
        check = NAMESPACE["require_accept_only_prerequisites"]
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with self.assertRaisesRegex(ValueError, "generation will not start"):
                check(out, True)
            (out / "attempt.json").write_text("{}")
            with self.assertRaises(ValueError):
                check(out, True)
            (out / "runner_exit.json").write_text("{}")
            check(out, True)
            # These files only establish presence; main/accept still check bindings and exit=0.

    def test_successful_existing_run_takes_acceptance_without_subprocess(self):
        main = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        source = ast.unparse(main)
        self.assertLess(source.index("require_accept_only_prerequisites"), source.index("subprocess.run"))
        attempt_check = next(n for n in ast.walk(main) if isinstance(n, ast.If)
                             and ast.unparse(n.test) == "attempt_path.exists()")
        self.assertNotIn("subprocess.run", ast.unparse(ast.Module(body=attempt_check.body, type_ignores=[])))
        self.assertIn("failed generation requires review", ast.unparse(attempt_check))


if __name__ == "__main__":
    unittest.main()
