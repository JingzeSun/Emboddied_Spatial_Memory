"""Entry-point checks for the post-D-183 observation planning stage."""

import importlib.util
import io
import json
from pathlib import Path
import tempfile
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "ops" / "vsmt" / "vm04_observation_stage.py"
SPEC = importlib.util.spec_from_file_location("vm04_observation_stage", PATH)
stage = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(stage)


class ObservationStageTests(unittest.TestCase):
    def test_check_is_read_only_and_reports_execution_closed(self):
        output = io.StringIO()
        with redirect_stdout(output):
            stage.check()
        self.assertIn("VM04_OBSERVATION_STAGE_CHECK_OK", output.getvalue())
        self.assertIn("execution_authorized=false", output.getvalue())

    def test_source_pool_gate_refuses_before_reading_input_or_writing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing.json"
            output = root / "pool.json"
            with self.assertRaisesRegex(
                    stage.ObservationConstructionError,
                    "source_pool_sealing_authorized is not authorized"):
                stage.seal_source_pool(missing, output)
            self.assertFalse(output.exists())

    def test_code_manifest_gate_refuses_before_reading_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            absent = root / "absent-checkout"
            output = root / "materializer-code.json"
            with self.assertRaisesRegex(
                    stage.ObservationConstructionError,
                    "materializer_code_sealing_authorized is not authorized"):
                stage.seal_materializer_code(
                    absent, "f" * 40, output,
                )
            self.assertFalse(absent.exists())
            self.assertFalse(output.exists())

    def test_formal_gate_refuses_before_reading_pilot_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "formal.json"
            with self.assertRaisesRegex(
                    stage.ObservationConstructionError,
                    "formal_selection_sealing_authorized is not authorized"):
                stage.seal_formal(root / "pool.json", root / "pilot.json", output)
            self.assertFalse(output.exists())

    def test_formal_sealing_rejects_boolean_input_even_if_gate_opens(self):
        """D-205 implemented the derivation, so the boolean table must now be
        rejected by the completion record's own schema rather than by a
        not-implemented stub."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "formal.json"
            contract = stage.read_json(stage.CONFIG)
            contract["authorization"][
                "formal_selection_sealing_authorized"] = True
            pool_path = root / "pool.json"
            pool_path.write_text(json.dumps(stage.make_source_pool_manifest(
                [f"train:{index:06d}" for index in range(70)],
                source_manifest_sha256="a" * 64,
                selection_seed=260916,
            )), encoding="utf-8")
            hand_written = root / "hand-written-booleans.json"
            hand_written.write_text(json.dumps(
                {str(index): True for index in range(6)}
            ), encoding="utf-8")
            with patch.object(stage, "load_contract", return_value=contract):
                with self.assertRaisesRegex(
                        stage.ObservationConstructionError,
                        "wrong pilot family completion schema"):
                    stage.seal_formal(pool_path, hand_written, output)
            self.assertFalse(output.exists())

    def test_formal_sealing_rejects_a_forged_completion_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "formal.json"
            contract = stage.read_json(stage.CONFIG)
            contract["authorization"][
                "formal_selection_sealing_authorized"] = True
            pool = stage.make_source_pool_manifest(
                [f"train:{index:06d}" for index in range(70)],
                source_manifest_sha256="a" * 64,
                selection_seed=260916,
            )
            pool_path = root / "pool.json"
            pool_path.write_text(json.dumps(pool), encoding="utf-8")
            forged = {
                "schema_version": "vsmt-vm04-pilot-family-completion-v1",
                "source_pool_manifest_sha256": pool["manifest_sha256"],
                "families": [
                    {"pool_index": index, "family_complete": True,
                     "incompletion_reasons": []} for index in range(6)
                ],
                "pilot_completed_families": 6,
                "caller_supplied_completion_boolean_used": False,
                "model_or_identifiability_inputs_used": False,
                "completion_sha256": "0" * 64,
            }
            forged_path = root / "forged.json"
            forged_path.write_text(json.dumps(forged), encoding="utf-8")
            with patch.object(stage, "load_contract", return_value=contract):
                with self.assertRaisesRegex(
                        stage.ObservationConstructionError,
                        "pilot completion digest mismatch"):
                    stage.seal_formal(pool_path, forged_path, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
