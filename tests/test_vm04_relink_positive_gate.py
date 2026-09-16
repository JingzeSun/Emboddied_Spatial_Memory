"""D-177: same instance and two public relation proofs are mandatory."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
sys.path.insert(0, str(ROOT / "src"))

from cpmt.hashing import seal_graph
from tests.test_vsmt_public_candidates import graph_fixture, packet_fixture
from vsmt.vm04_materializer_receipt import make_materializer_receipt
import vm04_relink_positive_gate as gate


class PhysicalRelinkPositiveGateTests(unittest.TestCase):
    def reseal_materializer(self, public, old_crosswalk, new_crosswalk):
        materializer_path = public / "materializer.receipt.json"
        current = gate.audit.read_json(materializer_path)
        rows = current["frames"]
        rows[0]["public_packet_sha256"] = gate.audit.sha256(
            public / "old-observation-packet.json")
        rows[0]["private_crosswalk_sha256"] = gate.audit.sha256(old_crosswalk)
        rows[1]["public_packet_sha256"] = gate.audit.sha256(
            public / "post-observation-packet.json")
        rows[1]["private_crosswalk_sha256"] = gate.audit.sha256(new_crosswalk)
        rebuilt = make_materializer_receipt(
            rows, episode_id=current["episode_id"],
            route_plan_sha256=current["route_plan_sha256"],
            raw_episode_manifest_sha256=current["raw_episode_manifest_sha256"],
            materializer_code_sha256=current["materializer_code_sha256"],
            materializer_config_sha256=current["materializer_config_sha256"],
            public_frame_context_manifest_sha256=current[
                "public_frame_context_manifest_sha256"
            ],
            causal_prior_receipt_sha256=current[
                "causal_prior_receipt_sha256"
            ],
            prior_memory_sha256=current["prior_memory_sha256"],
            materializer_assets_receipt_sha256=current[
                "materializer_assets_receipt_sha256"
            ],
        )
        materializer_path.unlink()
        gate.audit.write_new_json(materializer_path, rebuilt)
        seal_path = public / "relink-proof.seal.json"
        seal = gate.audit.read_json(seal_path)
        seal["old_packet_sha256"] = gate.audit.sha256(
            public / "old-observation-packet.json")
        seal["post_packet_sha256"] = gate.audit.sha256(
            public / "post-observation-packet.json")
        seal["materializer_receipt_sha256"] = gate.audit.sha256(
            materializer_path)
        seal_path.unlink()
        gate.audit.write_new_json(seal_path, seal)
        marker = public / "relink-proof.seal.success.json"
        marker.unlink()
        gate.audit.write_new_json(
            marker, {"receipt_sha256": gate.audit.sha256(seal_path)})

    def case(self, root, *, new_instance="asset:A", old_relation=True,
             new_relation=True):
        public = root / "public"
        private = root / "private/outcome.json"
        graph = graph_fixture()
        graph["edges"][0]["evidence_refs"] = ["observation:" + "b" * 64]
        graph = seal_graph(graph)
        old = packet_fixture(graph)
        post = packet_fixture(graph)
        post["region_observations"][2]["mask_sha256"] = "8" * 64
        post["region_observations"][2]["centroid_m"] = [1.5, 0.0, 0.0]
        post["relation_observations"][0]["support_sha256"] = "c" * 64
        if not old_relation:
            old["relation_observations"] = []
        if not new_relation:
            post["relation_observations"] = []
        files = {
            "old-observation-packet.json": old,
            "prior-memory.json": graph,
            "post-observation-packet.json": post,
        }
        for name, content in files.items():
            gate.audit.write_new_json(public / name, content)
        gate.audit.write_new_json(private, {
            "schema_version": "vsmt-vm04-relink-private-outcome-v1",
            "old_instance_id": "asset:A", "new_instance_id": new_instance,
            "old_place_region_id": "region:0002",
            "new_place_region_id": "region:0002",
            "prior_entity_node_id": "entity-a",
            "prior_edge_id": "edge:located",
            "unforced_robot_action_verified": True,
            "stable_actual_relation_changed": True,
        })
        old_crosswalk = root / "private/old-crosswalk.json"
        new_crosswalk = root / "private/new-crosswalk.json"
        for path, role, instance_id in (
                (old_crosswalk, "old", "asset:A"),
                (new_crosswalk, "new", new_instance)):
            gate.audit.write_new_json(path, {
                "schema_version": "vsmt-vm04-private-region-crosswalk-v1",
                "frame_role": role,
                "bindings": [{"instance_id": instance_id,
                              "region_id": "region:0000",
                              "mask_sha256": "5" * 64}],
            })
        materializer = public / "materializer.receipt.json"
        gate.audit.write_new_json(materializer, make_materializer_receipt(
            [
                {
                    "observation_index": 0,
                    "raw_public_frame_sha256": "1" * 64,
                    "raw_private_masks_sha256": "2" * 64,
                    "public_packet_sha256": gate.audit.sha256(
                        public / "old-observation-packet.json"),
                    "private_crosswalk_sha256": gate.audit.sha256(
                        old_crosswalk),
                },
                {
                    "observation_index": 1,
                    "raw_public_frame_sha256": "3" * 64,
                    "raw_private_masks_sha256": "4" * 64,
                    "public_packet_sha256": gate.audit.sha256(
                        public / "post-observation-packet.json"),
                    "private_crosswalk_sha256": gate.audit.sha256(
                        new_crosswalk),
                },
            ],
            episode_id="episode:relink", route_plan_sha256="5" * 64,
            raw_episode_manifest_sha256="6" * 64,
            materializer_code_sha256="7" * 64,
            materializer_config_sha256="8" * 64,
            public_frame_context_manifest_sha256="9" * 64,
            causal_prior_receipt_sha256="a" * 64,
            prior_memory_sha256=gate.audit.sha256(
                public / "prior-memory.json"
            ),
            materializer_assets_receipt_sha256="b" * 64,
        ))
        seal = public / "relink-proof.seal.json"
        gate.audit.write_new_json(seal, {
            "schema_version": "vsmt-vm04-relink-public-proof-v1",
            "old_packet_sha256": gate.audit.sha256(
                public / "old-observation-packet.json"),
            "prior_memory_sha256": gate.audit.sha256(
                public / "prior-memory.json"),
            "post_packet_sha256": gate.audit.sha256(
                public / "post-observation-packet.json"),
            "materializer_receipt_sha256": gate.audit.sha256(materializer),
        })
        gate.audit.write_new_json(
            public / "relink-proof.seal.success.json",
            {"receipt_sha256": gate.audit.sha256(seal)})
        return public, private, old_crosswalk, new_crosswalk

    def test_positive_requires_same_instance_and_both_public_relation_proofs(self):
        with TemporaryDirectory() as temp:
            public, private, old_crosswalk, new_crosswalk = self.case(Path(temp))
            verdict = gate.evaluate_physical_relink(
                public, private, old_crosswalk, new_crosswalk)
            self.assertTrue(verdict["physical_relink_positive"])
            self.assertTrue(verdict["checks"]["same_physical_instance"])
            self.assertTrue(
                verdict["checks"]["private_crosswalk_bindings_verified"])
            self.assertTrue(verdict["checks"]["public_old_relation_supported"])
            self.assertTrue(verdict["checks"]["public_new_relation_supported"])
            self.assertFalse(verdict["candidate_or_teacher_evaluated"])
            self.assertNotIn("asset:A", str(verdict))

    def test_different_instance_is_not_relink_or_automatic_quarantine(self):
        with TemporaryDirectory() as temp:
            public, private, old_crosswalk, new_crosswalk = self.case(
                Path(temp), new_instance="asset:B")
            verdict = gate.evaluate_physical_relink(
                public, private, old_crosswalk, new_crosswalk)
            self.assertFalse(verdict["physical_relink_positive"])
            self.assertEqual(verdict["failure_reasons"],
                             ["same_physical_instance"])
            self.assertNotIn("QUARANTINE", str(verdict))

    def test_missing_either_public_relation_prevents_positive(self):
        for missing in ("old", "new"):
            with self.subTest(missing=missing), TemporaryDirectory() as temp:
                public, private, old_crosswalk, new_crosswalk = self.case(
                    Path(temp), old_relation=missing != "old",
                    new_relation=missing != "new")
                verdict = gate.evaluate_physical_relink(
                    public, private, old_crosswalk, new_crosswalk)
                self.assertFalse(verdict["physical_relink_positive"])
                self.assertIn("public_%s_relation_supported" % missing,
                              verdict["failure_reasons"])

    def test_same_public_place_is_not_a_relink_positive(self):
        with TemporaryDirectory() as temp:
            public, private, old_crosswalk, new_crosswalk = self.case(Path(temp))
            post_path = public / "post-observation-packet.json"
            post = gate.audit.read_json(post_path)
            post["region_observations"][2]["centroid_m"] = [1.0, 0.0, 0.0]
            post["region_observations"][2]["mask_sha256"] = "7" * 64
            post_path.unlink()
            gate.audit.write_new_json(post_path, post)
            self.reseal_materializer(public, old_crosswalk, new_crosswalk)
            verdict = gate.evaluate_physical_relink(
                public, private, old_crosswalk, new_crosswalk)
            self.assertFalse(verdict["physical_relink_positive"])
            self.assertIn("public_places_distinct", verdict["failure_reasons"])

    def test_public_packet_tamper_after_seal_is_rejected_before_private_label(self):
        with TemporaryDirectory() as temp:
            public, private, old_crosswalk, new_crosswalk = self.case(Path(temp))
            (public / "post-observation-packet.json").write_text(
                "{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,
                                        "sealed public relation source bytes"):
                gate.evaluate_physical_relink(
                    public, private, old_crosswalk, new_crosswalk)

    def test_crosswalk_must_bind_private_instance_to_public_entity_mask(self):
        with TemporaryDirectory() as temp:
            public, private, old_crosswalk, new_crosswalk = self.case(Path(temp))
            content = gate.audit.read_json(new_crosswalk)
            content["bindings"][0]["mask_sha256"] = "6" * 64
            new_crosswalk.unlink()
            gate.audit.write_new_json(new_crosswalk, content)
            self.reseal_materializer(public, old_crosswalk, new_crosswalk)
            verdict = gate.evaluate_physical_relink(
                public, private, old_crosswalk, new_crosswalk)
            self.assertFalse(verdict["physical_relink_positive"])
            self.assertFalse(
                verdict["checks"]["private_crosswalk_bindings_verified"])
            self.assertIn("same_physical_instance", verdict["failure_reasons"])

    def test_crosswalk_change_after_materializer_receipt_is_rejected(self):
        with TemporaryDirectory() as temp:
            public, private, old_crosswalk, new_crosswalk = self.case(Path(temp))
            content = gate.audit.read_json(new_crosswalk)
            content["bindings"].append({
                "instance_id": "asset:unused",
                "region_id": "region:0000",
                "mask_sha256": "5" * 64,
            })
            new_crosswalk.unlink()
            gate.audit.write_new_json(new_crosswalk, content)
            with self.assertRaisesRegex(
                    RuntimeError, "crosswalk provenance"):
                gate.evaluate_physical_relink(
                    public, private, old_crosswalk, new_crosswalk)


if __name__ == "__main__":
    unittest.main()
