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
import vm04_relink_positive_gate as gate


class PhysicalRelinkPositiveGateTests(unittest.TestCase):
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
        seal = public / "relink-proof.seal.json"
        gate.audit.write_new_json(seal, {
            "schema_version": "vsmt-vm04-relink-public-proof-v1",
            "old_packet_sha256": gate.audit.sha256(
                public / "old-observation-packet.json"),
            "prior_memory_sha256": gate.audit.sha256(
                public / "prior-memory.json"),
            "post_packet_sha256": gate.audit.sha256(
                public / "post-observation-packet.json"),
        })
        gate.audit.write_new_json(
            public / "relink-proof.seal.success.json",
            {"receipt_sha256": gate.audit.sha256(seal)})
        gate.audit.write_new_json(private, {
            "schema_version": "vsmt-vm04-relink-private-outcome-v1",
            "old_instance_id": "asset:A", "new_instance_id": new_instance,
            "old_region_id": "region:0000",
            "new_region_id": "region:0000",
            "old_place_region_id": "region:0002",
            "new_place_region_id": "region:0002",
            "prior_entity_node_id": "entity-a",
            "prior_edge_id": "edge:located",
            "unforced_robot_action_verified": True,
            "stable_actual_relation_changed": True,
        })
        return public, private

    def test_positive_requires_same_instance_and_both_public_relation_proofs(self):
        with TemporaryDirectory() as temp:
            public, private = self.case(Path(temp))
            verdict = gate.evaluate_physical_relink(public, private)
            self.assertTrue(verdict["physical_relink_positive"])
            self.assertTrue(verdict["checks"]["same_physical_instance"])
            self.assertTrue(verdict["checks"]["public_old_relation_supported"])
            self.assertTrue(verdict["checks"]["public_new_relation_supported"])
            self.assertFalse(verdict["candidate_or_teacher_evaluated"])
            self.assertNotIn("asset:A", str(verdict))

    def test_different_instance_is_not_relink_or_automatic_quarantine(self):
        with TemporaryDirectory() as temp:
            public, private = self.case(Path(temp), new_instance="asset:B")
            verdict = gate.evaluate_physical_relink(public, private)
            self.assertFalse(verdict["physical_relink_positive"])
            self.assertEqual(verdict["failure_reasons"],
                             ["same_physical_instance"])
            self.assertNotIn("QUARANTINE", str(verdict))

    def test_missing_either_public_relation_prevents_positive(self):
        for missing in ("old", "new"):
            with self.subTest(missing=missing), TemporaryDirectory() as temp:
                public, private = self.case(
                    Path(temp), old_relation=missing != "old",
                    new_relation=missing != "new")
                verdict = gate.evaluate_physical_relink(public, private)
                self.assertFalse(verdict["physical_relink_positive"])
                self.assertIn("public_%s_relation_supported" % missing,
                              verdict["failure_reasons"])

    def test_same_public_place_is_not_a_relink_positive(self):
        with TemporaryDirectory() as temp:
            public, private = self.case(Path(temp))
            post_path = public / "post-observation-packet.json"
            post = gate.audit.read_json(post_path)
            post["region_observations"][2]["centroid_m"] = [1.0, 0.0, 0.0]
            post_path.unlink()
            gate.audit.write_new_json(post_path, post)
            seal_path = public / "relink-proof.seal.json"
            seal = gate.audit.read_json(seal_path)
            seal["post_packet_sha256"] = gate.audit.sha256(post_path)
            seal_path.unlink()
            gate.audit.write_new_json(seal_path, seal)
            marker = public / "relink-proof.seal.success.json"
            marker.unlink()
            gate.audit.write_new_json(
                marker, {"receipt_sha256": gate.audit.sha256(seal_path)})
            verdict = gate.evaluate_physical_relink(public, private)
            self.assertFalse(verdict["physical_relink_positive"])
            self.assertIn("public_places_distinct", verdict["failure_reasons"])

    def test_public_packet_tamper_after_seal_is_rejected_before_private_label(self):
        with TemporaryDirectory() as temp:
            public, private = self.case(Path(temp))
            (public / "post-observation-packet.json").write_text(
                "{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,
                                        "sealed public relation source bytes"):
                gate.evaluate_physical_relink(public, private)


if __name__ == "__main__":
    unittest.main()
