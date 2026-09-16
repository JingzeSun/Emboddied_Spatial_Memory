"""Tests for append-only multiview raw-to-packet materialization."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OPS = ROOT / "ops" / "vsmt"
for path in (SRC, OPS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

PATH = OPS / "vm04_multiview_materializer.py"
SPEC = importlib.util.spec_from_file_location("vm04_multiview_materializer", PATH)
materializer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(materializer)

from tests.test_vm04_multiview_raw import raw  # noqa: E402
from tests.test_vm04_multiview_worker import (  # noqa: E402
    ACTION_REQUESTS,
    CONTRACT,
    Controller,
    _capture,
    _plan,
    worker,
)
from tests.test_vsmt_public_candidates import graph_fixture, packet_fixture  # noqa: E402


CODE_SHA = "a" * 64
CONFIG_SHA = "b" * 64


def _build_raw_episode(episode_root):
    store = raw.RawEpisodeStore(
        episode_root, plan=_plan(), contract=CONTRACT)
    result = worker._execute_route_core(
        Controller(), plan=_plan(), contract=CONTRACT,
        action_request_templates=ACTION_REQUESTS,
        trusted_public_frame_extractor=store.extract_public_frame,
        public_capture=_capture(),
        private_intervention=lambda event, route: {
            "success": True, "private_id_exported": False,
        },
    )
    assert result["status"] == "raw_complete"
    store.finalize(result)


def _materialize(public_raw, private_raw, index):
    packet = packet_fixture(graph_fixture())
    packet["sample_id_hash"] = f"{index + 1:x}" * 64
    entity = next(
        row for row in packet["region_observations"]
        if row["structure_kind"] == "entity")
    return {
        "public_packet": packet,
        "private_crosswalk": {
            "schema_version": "vsmt-vm04-private-region-crosswalk-v1",
            "frame_role": "old" if index == 0 else "new",
            "bindings": [{
                "instance_id": private_raw["private_instance_ids"][0],
                "region_id": entity["region_id"],
                "mask_sha256": entity["mask_sha256"],
            }],
        },
    }


class MultiviewMaterializerTests(unittest.TestCase):
    def test_materializes_all_frames_and_seals_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_materialize,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
            )
            self.assertEqual(result["status"], "materialized_complete")
            self.assertEqual(result["frame_count"], 6)
            receipt = json.loads((
                episode / "materialized/public/materializer.receipt.json"
            ).read_text(encoding="utf-8"))
            self.assertEqual(receipt["frame_count"], 6)
            self.assertEqual(receipt["materializer_code_sha256"], CODE_SHA)
            self.assertFalse(
                receipt["deployment_reader_may_open_private_crosswalks"])
            verified = materializer.verify_materialized_episode(episode)
            self.assertEqual(verified["status"], "materialized_verified")
            self.assertEqual(verified["frame_count"], 6)

    def test_raw_tamper_retains_failure_without_success_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)
            with (episode / "public/raw/frame_0000/rgb.npy").open("ab") as handle:
                handle.write(b"tamper")
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_materialize,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
            )
            self.assertEqual(result["status"], "materialized_failure")
            self.assertEqual(result["frame_count"], 0)
            self.assertFalse((
                episode / "materialized/public/materializer.receipt.json"
            ).exists())
            self.assertTrue((
                episode / "materialized/private/materializer.failure.json"
            ).is_file())

    def test_callback_failure_keeps_completed_materialized_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)

            def fail_second(public_raw, private_raw, index):
                if index == 1:
                    raise RuntimeError("private diagnostic detail")
                return _materialize(public_raw, private_raw, index)

            result = materializer.materialize_episode_core(
                episode, materialize_frame=fail_second,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
            )
            self.assertEqual(result["frame_count"], 1)
            self.assertTrue((
                episode / "materialized/public/frame_0000.json"
            ).is_file())
            public_failure = (episode / (
                "materialized/public/materializer.failure.json"
            )).read_text(encoding="utf-8")
            self.assertNotIn("private diagnostic detail", public_failure)

    def test_private_instance_id_in_public_packet_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)

            def leak_private_id(public_raw, private_raw, index):
                output = _materialize(public_raw, private_raw, index)
                entity = next(
                    row for row in output["public_packet"]["region_observations"]
                    if row["structure_kind"] == "entity")
                entity["region_id"] = private_raw["private_instance_ids"][0]
                output["private_crosswalk"]["bindings"][0][
                    "region_id"] = private_raw["private_instance_ids"][0]
                return output

            result = materializer.materialize_episode_core(
                episode, materialize_frame=leak_private_id,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
            )
            self.assertEqual(result["status"], "materialized_failure")
            self.assertEqual(result["frame_count"], 0)
            private_failure = json.loads((episode / (
                "materialized/private/materializer.failure.json"
            )).read_text(encoding="utf-8"))
            self.assertIn("opaque ordinals", private_failure["exception_message"])

    def test_production_entry_refuses_before_read_or_output(self):
        contract = copy.deepcopy(CONTRACT)
        with tempfile.TemporaryDirectory() as temporary:
            absent = Path(temporary) / "absent-episode"
            with self.assertRaisesRegex(
                    materializer.ObservationConstructionError,
                    "materializer code digest is not frozen"):
                materializer.run_authorized_materializer(
                    absent, contract=contract,
                    materialize_frame=_materialize,
                    materializer_code_sha256=CODE_SHA,
                    materializer_config_sha256=CONFIG_SHA,
                )
            self.assertFalse(absent.exists())

    def test_verifier_rejects_packet_changed_after_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_materialize,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
            )
            self.assertEqual(result["status"], "materialized_complete")
            packet_path = episode / "materialized/public/frame_0000.json"
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            packet["decision_time_s"] += 1.0
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaisesRegex(
                    materializer.ObservationConstructionError,
                    "materialized frame binding changed"):
                materializer.verify_materialized_episode(episode)


if __name__ == "__main__":
    unittest.main()
