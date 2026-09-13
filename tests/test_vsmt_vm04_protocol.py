from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.vm04_protocol import (  # noqa: E402
    ALL_SPLITS,
    DEVELOPMENT_SPLITS,
    REGISTERED_PROGRAMS,
    assert_vm04_action_authorized,
    make_episode_plan_manifests,
    make_family_split_manifest,
    validate_vm04_protocol,
)


CONFIG_PATH = PROJECT_ROOT / "configs" / "vsmt" / "vm04_data_protocol_proposal_v1.json"


def protocol() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


class VM04ProtocolTests(unittest.TestCase):
    def test_proposal_arithmetic_and_eight_atoms_are_consistent(self) -> None:
        record = validate_vm04_protocol(protocol())
        self.assertEqual(record["experimental_unit"]["programs_per_family"], 9)
        self.assertEqual(record["split_proposal"]["total_episodes"], 1332)
        self.assertEqual(record["split_proposal"]["total_observations"], 42624)

    def test_every_mutating_action_fails_closed_for_the_proposal(self) -> None:
        for action in (
            "asset_download", "audit_generation", "train_validation_generation",
            "confirmation_generation", "training",
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError, "not frozen_executable"):
                    assert_vm04_action_authorized(protocol(), action=action)

    def test_family_split_is_deterministic_disjoint_and_input_order_invariant(self) -> None:
        houses = [f"house-{index:04d}" for index in range(80)]
        left = make_family_split_manifest(
            houses, config=protocol(), source_manifest_sha256="a" * 64,
        )
        right = make_family_split_manifest(
            list(reversed(houses)), config=protocol(), source_manifest_sha256="a" * 64,
        )
        self.assertEqual(left, right)
        rows = left["families"]
        self.assertEqual(len(rows), 74)
        self.assertEqual(len({row["source_house_id"] for row in rows}), 74)
        for split_name in ALL_SPLITS:
            expected = protocol()["split_proposal"][f"{split_name}_families"]
            self.assertEqual(sum(row["split"] == split_name for row in rows), expected)

    def test_public_episode_ids_do_not_encode_program_assignment(self) -> None:
        families = make_family_split_manifest(
            [f"house-{index:04d}" for index in range(80)],
            config=protocol(), source_manifest_sha256="a" * 64,
        )
        left = make_episode_plan_manifests(
            families,
            config=protocol(),
            assignment_salt_sha256="b" * 64,
            included_splits=DEVELOPMENT_SPLITS,
        )
        right = make_episode_plan_manifests(
            families,
            config=protocol(),
            assignment_salt_sha256="c" * 64,
            included_splits=DEVELOPMENT_SPLITS,
        )
        self.assertEqual(left["public"], right["public"])
        self.assertNotEqual(left["private"], right["private"])
        self.assertFalse(any(
            program in row["episode_id"]
            for row in left["public"]["episodes"]
            for program in REGISTERED_PROGRAMS
        ))

    def test_each_development_family_has_two_private_slots_per_program(self) -> None:
        config = protocol()
        families = make_family_split_manifest(
            [f"house-{index:04d}" for index in range(80)],
            config=config, source_manifest_sha256="a" * 64,
        )
        plans = make_episode_plan_manifests(
            families,
            config=config,
            assignment_salt_sha256="b" * 64,
            included_splits=DEVELOPMENT_SPLITS,
        )
        public = plans["public"]
        private = plans["private"]
        development_family_count = sum(
            config["split_proposal"][f"{name}_families"]
            for name in DEVELOPMENT_SPLITS
        )
        self.assertEqual(public["episode_count"], development_family_count * 18)
        mapping = {row["episode_id"]: row for row in private["assignments"]}
        for family_id in {row["family_id"] for row in public["episodes"]}:
            episode_ids = [
                row["episode_id"] for row in public["episodes"]
                if row["family_id"] == family_id
            ]
            counts = {
                program: sum(mapping[episode_id]["program"] == program
                             for episode_id in episode_ids)
                for program in REGISTERED_PROGRAMS
            }
            self.assertEqual(set(counts.values()), {2})

    def test_confirmation_episode_plan_remains_sealed(self) -> None:
        config = protocol()
        families = make_family_split_manifest(
            [f"house-{index:04d}" for index in range(80)],
            config=config, source_manifest_sha256="a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "not frozen_executable"):
            make_episode_plan_manifests(
                families,
                config=config,
                assignment_salt_sha256="b" * 64,
                included_splits=("confirmation",),
            )

    def test_manifest_tampering_does_not_change_source_config(self) -> None:
        original = protocol()
        changed = deepcopy(original)
        changed["experimental_unit"]["episodes_per_family"] = 17
        with self.assertRaisesRegex(ValueError, "arithmetic"):
            validate_vm04_protocol(changed)
        self.assertEqual(protocol(), original)


if __name__ == "__main__":
    unittest.main()
