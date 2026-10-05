"""S3-05 (ruling 107-1 / 107-2): opening the seal once, and the node audit reading test only under the freeze receipt."""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402
from vsmt import lean_s3_05 as s5  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402

HOUSES = ["procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002", "procthor10k-0.1.2-train-00003"]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sealed_roots(base: Path) -> tuple[dict[str, Path], dict]:
    roots = {kind: base / kind / "test" for kind in ts.SEAL_KINDS}
    for kind, root in roots.items():
        for house in HOUSES:
            write(root / house / "receipt.json", json.dumps({"status": "succeeded", "frames": 100}))
            write(root / house / "public" / "0000.frame.json", f"{kind}-{house}")
        write(root / "stage_receipt.json", json.dumps({"kind": kind}))
        ts.write_marker(root, kind=kind, state=ts.STATE_PENDING)
    seal, _digest = ts.seal_roots(roots, houses=HOUSES, tag="abc1234")
    return roots, seal


class OpenTests(unittest.TestCase):
    """Ruling 107-1."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.roots, self.seal = sealed_roots(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_opened_once_and_a_resume_is_the_same_reading(self):
        self.assertIsNotNone(ts.refusal([self.roots["raw"] / HOUSES[0]], reader="s3-04"))
        with self.assertRaises(ts.LeanTestSealError):
            ts.admit_opened([self.roots["raw"]], reader="s3-05", receipt_sha256="r1")  # sealed, not opened
        record = ts.open_roots(self.seal, receipt_sha256="r1", commit="c1", purpose="test")
        self.assertEqual((record["reading"], record["resumed"]), (1, False))
        ts.admit_opened([self.roots["sam2_cache"] / HOUSES[1]], reader="s3-05", receipt_sha256="r1")
        self.assertIsNotNone(ts.refusal([self.roots["raw"]], reader="s3-03"))  # the old entries still refuse an opened root
        self.assertIsNotNone(ts.refusal_unless_opened([self.roots["raw"]], reader="x", receipt_sha256="r2"))
        self.assertEqual(ts.verify_seal(self.seal, opened_by="r1"), [])  # the read record sits outside the seal
        self.assertEqual(ts.verify_seal(self.seal), [f"marker_not_this_seal:{kind}" for kind in ts.SEAL_KINDS])
        again = ts.open_roots(self.seal, receipt_sha256="r1", commit="c2", purpose="resume")
        self.assertTrue(again["resumed"])
        self.assertEqual(again["opened_utc"], record["opened_utc"])
        with self.assertRaisesRegex(ts.LeanTestSealError, "test_already_opened_for_another_receipt"):
            ts.open_roots(self.seal, receipt_sha256="r2", commit="c3", purpose="second reading")
        entry = ts.record_copy(self.seal, host="w4", problems=[])
        self.assertTrue(entry["verified"])
        copies = json.loads((self.roots["geometry"] / ts.READ_RECORD_NAME).read_text(encoding="utf-8"))["copies"]
        self.assertEqual([c["host"] for c in copies], ["w4"])

    def test_a_changed_byte_keeps_the_roots_sealed(self):
        write(self.roots["instance_cache"] / HOUSES[0] / "public" / "0000.frame.json", "changed")
        with self.assertRaisesRegex(ts.LeanTestSealError, "seal_not_intact"):
            ts.open_roots(self.seal, receipt_sha256="r1", commit="c1", purpose="test")
        marker = json.loads((self.roots["raw"] / ts.MARKER_NAME).read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], ts.STATE_SEALED)


class AuditGuardTests(unittest.TestCase):
    """Ruling 107-1 / 107-2: the node audit reads test only under the freeze receipt, only the frozen configurations."""

    def setUp(self):
        from vsmt import lean_s3_04 as s4

        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.roots, self.seal = sealed_roots(base)
        receipt = {"fronts": {"instance": {"test_runs": [{"arm": "TAF", "config": {"theta_a": 0.7, "d_a": None}}]}}}
        receipt["receipt_sha256"] = s4.receipt_body_sha256(receipt)
        self.receipt = base / "freeze_receipt.json"
        self.receipt.write_text(json.dumps(receipt), encoding="utf-8")
        self.digest = receipt["receipt_sha256"]
        self.episode = str(s3.load_manifest()["test"][0])

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, **overrides):
        values = {"manifest_split": "test", "test_receipt": str(self.receipt), "metrics_only": True, "arm": "TAF",
                  "episode_id": self.episode, "cache_root": str(self.roots["instance_cache"]),
                  "episode_root": str(self.roots["raw"] / HOUSES[0]), "geometry_root": str(self.roots["geometry"]),
                  "mask_source": "simulator_instance_masks"}
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_the_guard(self):
        import lean_s2_05_node_audit as audit

        self.assertIn("needs both", audit.test_refusal(self.args(test_receipt=None)))
        self.assertIn("metrics-only", audit.test_refusal(self.args(metrics_only=False)))
        self.assertIn("episode_not_in_the_s3_test_manifest", audit.test_refusal(self.args(episode_id=HOUSES[0])))
        self.assertIn("test_root_not_opened_for_this_receipt", audit.test_refusal(self.args()))  # still sealed
        ts.open_roots(self.seal, receipt_sha256=self.digest, commit="c", purpose="test")
        self.assertIsNone(audit.test_refusal(self.args()))
        frozen = [({"theta_a": 0.7, "d_a": None}, "/out")]
        self.assertIsNone(audit.test_config_refusal(self.args(), frozen))
        self.assertIn("configuration_not_frozen_for_test", audit.test_config_refusal(self.args(), [({"theta_a": 0.8, "d_a": None}, "/out")]))
        self.assertIn("mask_source_not_frozen", audit.test_config_refusal(self.args(mask_source="sam2"), frozen))


if __name__ == "__main__":
    unittest.main()
