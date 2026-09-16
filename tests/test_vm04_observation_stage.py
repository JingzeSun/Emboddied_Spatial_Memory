"""Entry-point checks for the post-D-183 observation planning stage."""

import importlib.util
import io
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
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "formal.json"
            contract = stage.read_json(stage.CONFIG)
            contract["authorization"][
                "formal_selection_sealing_authorized"] = True
            with patch.object(stage, "load_contract", return_value=contract):
                with self.assertRaisesRegex(
                        stage.ObservationConstructionError,
                        "caller-supplied booleans are forbidden"):
                    stage.seal_formal(
                        root / "missing-pool.json",
                        root / "missing-booleans.json", output,
                    )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
