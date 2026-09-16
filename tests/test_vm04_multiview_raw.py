"""File-boundary tests for the post-D-183 multiview raw writer."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PATH = ROOT / "ops" / "vsmt" / "vm04_multiview_raw.py"
SPEC = importlib.util.spec_from_file_location("vm04_multiview_raw", PATH)
raw = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(raw)

from tests.test_vm04_multiview_worker import CONTRACT, Event, _plan  # noqa: E402
from vsmt.vm04_observation_runner import ObservationConstructionError  # noqa: E402


class MultiviewRawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((
            ROOT / "schemas/vsmt_vm04_multiview_raw.schema.json"
        ).read_text(encoding="utf-8"))

    def _assert_schema_keys(self, definition, record):
        expected = set(self.schema["$defs"][definition]["required"])
        self.assertEqual(set(record), expected)

    def test_writes_split_frame_and_retains_failure_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            store = raw.RawEpisodeStore(
                episode, plan=_plan(), contract=CONTRACT)
            public_frame = store.extract_public_frame(Event((0.0, 0.0)), 0)
            self.assertEqual(set(public_frame), {
                "rgb", "depth_m", "camera", "source_frame_sha256",
                "private_fields_removed",
            })
            receipt = store.finalize({
                "status": "raw_failure",
                "reason": "registered_camera_action_failed",
                "public_observation_prefix": [],
                "intervention_executed": False,
                "private_intervention_record": None,
            })
            self.assertEqual(receipt["frame_count"], 1)
            public_bytes = b"".join(
                path.read_bytes() for path in (episode / "public").rglob("*")
                if path.is_file()
            )
            self.assertNotIn(b"private|object", public_bytes)
            private_map = json.loads((
                episode / "private/raw/frame_0000/mapping.json"
            ).read_text(encoding="utf-8"))
            public_camera = json.loads((
                episode / "public/raw/frame_0000/camera.json"
            ).read_text(encoding="utf-8"))
            public_record = json.loads((
                episode / "public/raw/frame_0000/frame.json"
            ).read_text(encoding="utf-8"))
            self._assert_schema_keys("publicCamera", public_camera)
            self._assert_schema_keys("publicFrame", public_record)
            self._assert_schema_keys("privateFrameMap", private_map)
            self.assertEqual(
                private_map["private_instance_ids"], ["private|object"])
            public_manifest = json.loads((
                episode / "public/raw.manifest.json"
            ).read_text(encoding="utf-8"))
            private_manifest = json.loads((
                episode / "private/raw.manifest.json"
            ).read_text(encoding="utf-8"))
            self._assert_schema_keys("publicManifest", public_manifest)
            self._assert_schema_keys("privateManifest", private_manifest)
            self.assertTrue((episode / "public/raw.terminal.json").is_file())
            self.assertTrue((episode / "private/raw.manifest.json").is_file())

    def test_rejects_noncontiguous_frame_and_second_terminal(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            store = raw.RawEpisodeStore(
                episode, plan=_plan(), contract=CONTRACT)
            with self.assertRaisesRegex(
                    ObservationConstructionError, "contiguous"):
                store.extract_public_frame(Event((0.0, 0.0)), 1)
            store.extract_public_frame(Event((0.0, 0.0)), 0)
            result = {
                "status": "raw_failure", "reason": "test_failure",
                "public_observation_prefix": [],
                "intervention_executed": False,
                "private_intervention_record": None,
            }
            store.finalize(result)
            with self.assertRaisesRegex(
                    ObservationConstructionError, "already finalized"):
                store.finalize(result)

    def test_existing_episode_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            episode.mkdir()
            with self.assertRaisesRegex(
                    ObservationConstructionError, "already exists"):
                raw.RawEpisodeStore(episode, plan=_plan(), contract=CONTRACT)


if __name__ == "__main__":
    unittest.main()
