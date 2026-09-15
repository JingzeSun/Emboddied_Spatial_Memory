"""Catch malformed VSMT config digests without rewriting frozen v1/v2."""

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LEGACY_ERRATUM = {
    (version, field): value
    for version in ("v1", "v2")
    for field, value in (
        ("public_episode_manifest_sha256",
         "403a7039cea8d8097fca1344d0041bc021ee6a231cffbede38066e690ab1bf406"),
        ("private_episode_manifest_sha256",
         "cb8e05aea4dda7f92b9463adf411986e0183f8a6660217a4bd08f6b5ac36ecaa4"),
    )
}


def malformed_digests(path: Path, value):
    """List invalid non-null *_sha256 leaves with their JSON location."""
    issues = []

    def walk(item, location):
        if type(item) is dict:
            for key, child in item.items():
                child_location = location + (key,)
                if key.endswith("_sha256") and child is not None and (
                    type(child) is not str or HEX64.fullmatch(child) is None
                ):
                    issues.append((path, child_location, child))
                walk(child, child_location)
        elif type(item) is list:
            for index, child in enumerate(item):
                walk(child, location + (index,))

    walk(value, ())
    return issues


class ConfigDigestShapeTests(unittest.TestCase):
    def test_vsmt_configs_have_only_exact_frozen_legacy_erratum(self):
        issues = []
        for path in sorted((ROOT / "configs/vsmt").rglob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            issues.extend(malformed_digests(path, value))
        actual = {}
        for path, location, value in issues:
            self.assertEqual(location[0], "planning_stage_binding")
            self.assertEqual(len(location), 2)
            self.assertIn(path.name, (
                "vm04_l1_two_house_audit_proposal_v1.json",
                "vm04_l1_two_house_audit_proposal_v2.json"))
            version = path.stem.rsplit("_", 1)[-1]
            actual[(version, location[-1])] = value
        self.assertEqual(actual, LEGACY_ERRATUM)

    def test_any_new_invalid_digest_is_not_an_erratum(self):
        path = ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["new_manifest_sha256"] = "f" * 65
        issues = malformed_digests(path, value)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][1], ("new_manifest_sha256",))


if __name__ == "__main__":
    unittest.main()
