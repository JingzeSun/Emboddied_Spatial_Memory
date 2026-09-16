from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_episode_construction_receipt import (  # noqa: E402
    FILE_DIGEST_KEYS,
    EpisodeConstructionReceiptError,
    make_episode_construction_receipt,
    validate_episode_construction_receipt,
)


SHA = "a" * 64


def receipt(*, program="BIRTH", satisfied=True):
    return make_episode_construction_receipt(
        episode_id="episode-001", program=program,
        prior_cutoff_observation_index=2,
        terminal_observation_index=5,
        materializer_receipt_sha256="b" * 64,
        program_matcher_receipt_sha256="c" * 64,
        file_digests={name: SHA for name in FILE_DIGEST_KEYS},
        split_merge_artifact_receipt_file_sha256=(
            "d" * 64 if program in {"SPLIT", "MERGE"} else None
        ),
        program_public_match_satisfied=satisfied,
        construction_failure_reasons=(
            [] if satisfied else ["public_matcher_failed"]
        ),
    )


class EpisodeConstructionReceiptTests(unittest.TestCase):
    def test_positive_match_remains_temporal_seal_pending(self):
        value = receipt()
        self.assertEqual(
            value["episode_construction_status"],
            "public_match_satisfied_temporal_seal_pending",
        )
        self.assertFalse(value["construction_plan_pre_terminal_seal_established"])
        self.assertFalse(value["eligible_for_parent_family_completion"])
        self.assertFalse(value["private_identity_used"])
        self.assertEqual(validate_episode_construction_receipt(value), value)

    def test_failed_matcher_is_retained_as_construction_failure(self):
        value = receipt(satisfied=False)
        self.assertEqual(
            value["episode_construction_status"], "construction_failure"
        )
        self.assertEqual(validate_episode_construction_receipt(value), value)

    def test_caller_cannot_flip_derived_completion_boolean(self):
        value = receipt(satisfied=False)
        changed = copy.deepcopy(value)
        changed["program_public_match_satisfied"] = True
        with self.assertRaises(EpisodeConstructionReceiptError):
            validate_episode_construction_receipt(changed)

    def test_split_merge_artifact_file_binding_is_optional_but_exclusive(self):
        self.assertEqual(
            validate_episode_construction_receipt(receipt(program="SPLIT"))[
                "program"
            ],
            "SPLIT",
        )
        missing = make_episode_construction_receipt(
                episode_id="episode-001", program="SPLIT",
                prior_cutoff_observation_index=0,
                terminal_observation_index=1,
                materializer_receipt_sha256=SHA,
                program_matcher_receipt_sha256=SHA,
                file_digests={name: SHA for name in FILE_DIGEST_KEYS},
                split_merge_artifact_receipt_file_sha256=None,
                program_public_match_satisfied=False,
                construction_failure_reasons=[
                    "registered_SPLIT_MERGE_artifact_receipt_missing"
                ],
        )
        self.assertEqual(missing["episode_construction_status"],
                         "construction_failure")
        with self.assertRaises(EpisodeConstructionReceiptError):
            make_episode_construction_receipt(
                episode_id="episode-001", program="BIRTH",
                prior_cutoff_observation_index=0,
                terminal_observation_index=1,
                materializer_receipt_sha256=SHA,
                program_matcher_receipt_sha256=SHA,
                file_digests={name: SHA for name in FILE_DIGEST_KEYS},
                split_merge_artifact_receipt_file_sha256="d" * 64,
                program_public_match_satisfied=True,
                construction_failure_reasons=[],
            )

    def test_schema_accepts_receipt(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is unavailable")
        schema = json.loads((
            ROOT / "schemas/vsmt_vm04_episode_construction_receipt.schema.json"
        ).read_text(encoding="utf-8"))
        jsonschema.validate(receipt(), schema)


if __name__ == "__main__":
    unittest.main()
