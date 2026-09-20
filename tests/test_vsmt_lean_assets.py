"""D-224 / S1-01 read-only checks for the asset and capacity authorization.

The continue gate for S1-01 is: every authorization bit stays false until the
user opens it; registration precedes acquisition; a mismatch stops and never
substitutes; the worker count is derived from measurement and recorded; and
receipts exist for failure as well as success.  These tests prove the checks
reject what they must.  They download nothing, probe nothing, and say nothing
about whether any asset is actually on the server.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.lean_assets import (  # noqa: E402
    ACQUISITION_MODES,
    ACQUISITION_STATUSES,
    ASSET_ENTRY_FIELDS,
    ASSET_RECEIPT_FIELDS,
    AUTHORIZATION_OF_ASSET,
    CAPACITY_MEASUREMENTS,
    CAPACITY_RECEIPT_FIELDS,
    CONTRACT_SCHEMA_VERSION,
    LICENSE_FIELDS,
    MUST_REMAIN_FALSE,
    STOP_ACTION,
    WORKER_DERIVATION_INPUTS,
    LeanAssetsError,
    acquisition_is_permitted,
    derive_worker_count,
    registration_is_complete,
    validate_asset_entry,
    validate_asset_registry,
    validate_assets_capacity_contract,
    validate_capacity_receipt,
    validate_license_record,
    verify_asset_receipt,
)


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_assets_capacity_v2.json"

CHECKPOINT_SHA = "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"
CHECKPOINT_BYTES = 184416285


def entry(**overrides: Any) -> dict[str, Any]:
    """A complete, admissible checkpoint registration, in contract field order."""

    row = {
        "asset_id": "sam2_checkpoint",
        "role": "proposal_weights",
        "required_by": "S1-03",
        "source_url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
        "pinned_ref": None,
        "pinned_path": None,
        "bytes": CHECKPOINT_BYTES,
        "sha256": CHECKPOINT_SHA,
        "registered_by": "D-215",
        "license": None,
        "acquisition_mode": "download_to_server",
        "acquisition_status": "registered_not_acquired",
    }
    row.update(overrides)
    return {name: row[name] for name in ASSET_ENTRY_FIELDS}


def license_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "license_name": "Apache-2.0",
        "license_url_or_file_path": "https://github.com/facebookresearch/sam2/blob/main/LICENSE",
        "redistribution_allowed": False,
        "research_use_allowed": True,
    }
    record.update(overrides)
    return {name: record[name] for name in LICENSE_FIELDS}


def authorization(**overrides: Any) -> dict[str, Any]:
    bits = {name: False for name in set(AUTHORIZATION_OF_ASSET.values())}
    bits.update({name: False for name in MUST_REMAIN_FALSE})
    bits.update(overrides)
    return bits


def receipt(**overrides: Any) -> dict[str, Any]:
    row = {
        "asset_id": "sam2_checkpoint",
        "acquisition_mode": "download_to_server",
        "source_url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
        "pinned_ref": None,
        "observed_bytes": CHECKPOINT_BYTES,
        "observed_sha256": CHECKPOINT_SHA,
        "registered_bytes": CHECKPOINT_BYTES,
        "registered_sha256": CHECKPOINT_SHA,
        "match": True,
        "worktree_clean_including_untracked": None,
        "installed_dependency_versions": {},
        "torch_version_before": "2.8.0+cu128",
        "torch_version_after": "2.8.0+cu128",
        "failures": [],
    }
    row.update(overrides)
    return {name: row[name] for name in ASSET_RECEIPT_FIELDS}


def measurements(**overrides: Any) -> dict[str, Any]:
    values = {
        "cpu_logical_cores": 32,
        "cpu_physical_cores": 16,
        "ram_total_gb": 120.0,
        "ram_available_gb": 100.0,
        "gpu_count": 1,
        "gpu_name": "NVIDIA GeForce RTX 4080 SUPER",
        "gpu_total_vram_gb": 32.0,
        "gpu_free_vram_gb": 31.0,
        "disk_free_gb_asset_root": 33.0,
        "disk_free_gb_install_root": 33.0,
        "python_version": "3.12.3",
        "torch_version": "2.8.0+cu128",
        "cuda_available": True,
        "egl_resolves": True,
        "vulkan_resolves": False,
    }
    values.update(overrides)
    return values


def occupancy(**overrides: Any) -> dict[str, Any]:
    values = {
        "cpu_cores_per_worker": 2.0,
        "ram_gb_per_worker": 4.0,
        "vram_gb_per_worker": 3.0,
        "disk_gb_per_worker": 1.0,
        "simulator_concurrency_limit": 6,
    }
    values.update(overrides)
    return values


class TestAssetEntry(unittest.TestCase):
    def test_a_complete_registration_passes(self) -> None:
        self.assertEqual(validate_asset_entry(entry())["asset_id"], "sam2_checkpoint")

    def test_a_missing_field_is_rejected(self) -> None:
        row = entry()
        del row["sha256"]
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(row)

    def test_an_extra_field_is_rejected(self) -> None:
        row = dict(entry())
        row["mirror_url"] = "https://example.invalid/mirror.pt"
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(row)

    def test_field_order_is_part_of_the_contract(self) -> None:
        row = entry()
        reordered = {name: row[name] for name in reversed(ASSET_ENTRY_FIELDS)}
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(reordered)

    def test_an_unknown_acquisition_mode_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(entry(acquisition_mode="fetch_whatever_works"))

    def test_a_checkpoint_without_a_digest_may_not_claim_to_be_registered(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(entry(sha256=None, bytes=None))

    def test_a_complete_identity_may_not_claim_to_be_incomplete(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(entry(acquisition_status="registration_incomplete"))

    def test_an_incomplete_registration_is_admissible_when_it_says_so(self) -> None:
        row = entry(
            asset_id="dinov2_vit_b14_checkpoint",
            role="descriptor_weights_768d_optional_upgrade",
            source_url=None, bytes=None, sha256=None, registered_by=None,
            acquisition_mode="register_then_place_on_server",
            acquisition_status="registration_incomplete",
        )
        self.assertFalse(registration_is_complete(row))
        validate_asset_entry(row)

    def test_a_repository_is_identified_by_its_revision_not_a_digest(self) -> None:
        row = entry(
            asset_id="sam2_repository", role="proposal_source_code",
            source_url="https://github.com/facebookresearch/sam2",
            pinned_ref="2b90b9f5ceec907a1c18123530e92e794ad901a4",
            bytes=None, sha256=None, acquisition_mode="clone_to_server",
        )
        self.assertTrue(registration_is_complete(row))
        validate_asset_entry(row)

    def test_a_plain_http_source_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(entry(source_url="http://example.invalid/weights.pt"))

    def test_an_asset_with_no_authorization_bit_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_asset_entry(entry(asset_id="some_other_checkpoint"))

    def test_a_duplicate_asset_id_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_asset_registry([entry(), entry(sha256=None, bytes=None,
                                                    acquisition_status="registration_incomplete",
                                                    acquisition_mode="register_then_place_on_server",
                                                    registered_by=None)])

    def test_an_empty_registry_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_asset_registry([])


class TestLicenceAndPermission(unittest.TestCase):
    def test_a_complete_licence_record_passes(self) -> None:
        validate_license_record(license_record())

    def test_a_licence_without_a_source_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_license_record(license_record(license_url_or_file_path=""))

    def test_a_licence_with_a_missing_flag_is_rejected(self) -> None:
        record = license_record()
        del record["research_use_allowed"]
        with self.assertRaises(LeanAssetsError):
            validate_license_record(record)

    def test_a_closed_bit_blocks_acquisition(self) -> None:
        verdict = acquisition_is_permitted(
            entry(), license_record=license_record(), authorization=authorization())
        self.assertEqual(verdict, {"permitted": False, "reason": "authorization_closed"})

    def test_an_open_bit_with_a_recorded_licence_permits_acquisition(self) -> None:
        verdict = acquisition_is_permitted(
            entry(), license_record=license_record(),
            authorization=authorization(sam2_asset_placement_on_server=True))
        self.assertTrue(verdict["permitted"])

    def test_an_open_bit_does_not_rescue_an_incomplete_registration(self) -> None:
        row = entry(
            asset_id="dinov2_vit_b14_checkpoint",
            role="descriptor_weights_768d_optional_upgrade",
            source_url=None, bytes=None, sha256=None, registered_by=None,
            acquisition_mode="register_then_place_on_server",
            acquisition_status="registration_incomplete",
        )
        verdict = acquisition_is_permitted(
            row, license_record=license_record(),
            authorization=authorization(dinov2_vit_b14_asset_placement_on_server=True))
        self.assertEqual(verdict, {"permitted": False, "reason": "registration_incomplete"})

    def test_a_missing_licence_blocks_acquisition(self) -> None:
        verdict = acquisition_is_permitted(
            entry(), license_record=None,
            authorization=authorization(sam2_asset_placement_on_server=True))
        self.assertEqual(verdict, {"permitted": False, "reason": "license_not_recorded"})

    def test_a_licence_that_forbids_research_use_blocks_acquisition(self) -> None:
        verdict = acquisition_is_permitted(
            entry(), license_record=license_record(research_use_allowed=False),
            authorization=authorization(sam2_asset_placement_on_server=True))
        self.assertEqual(verdict, {"permitted": False, "reason": "research_use_not_allowed"})

    def test_a_forbidden_bit_left_open_blocks_everything(self) -> None:
        verdict = acquisition_is_permitted(
            entry(), license_record=license_record(),
            authorization=authorization(
                sam2_asset_placement_on_server=True,
                alternate_version_or_mirror_on_failure=True))
        self.assertFalse(verdict["permitted"])
        self.assertTrue(verdict["reason"].startswith("forbidden_bit_open:"))

    def test_approving_sam_does_not_approve_the_simulator(self) -> None:
        simulator = entry(
            asset_id="ai2thor", role="simulator", required_by="S1-02",
            source_url="https://github.com/allenai/ai2thor.git",
            pinned_ref="f0825767cd50d69f666c7f282e54abfe58f1e917",
            bytes=None, sha256=None, registered_by="LOG-136",
            acquisition_mode="install_package",
        )
        verdict = acquisition_is_permitted(
            simulator, license_record=license_record(),
            authorization=authorization(sam2_asset_placement_on_server=True))
        self.assertEqual(verdict, {"permitted": False, "reason": "authorization_closed"})


class TestAssetReceipt(unittest.TestCase):
    def test_a_matching_receipt_proceeds(self) -> None:
        verdict = verify_asset_receipt(entry(), receipt())
        self.assertEqual(verdict,
                         {"match": True, "action": "proceed", "mismatched_fields": []})

    def test_a_wrong_digest_stops_and_never_substitutes(self) -> None:
        verdict = verify_asset_receipt(entry(), receipt(observed_sha256="0" * 64))
        self.assertEqual(verdict["action"], STOP_ACTION)
        self.assertEqual(verdict["mismatched_fields"], ["sha256"])

    def test_a_wrong_byte_count_stops(self) -> None:
        verdict = verify_asset_receipt(entry(), receipt(observed_bytes=CHECKPOINT_BYTES - 1))
        self.assertEqual(verdict["action"], STOP_ACTION)
        self.assertEqual(verdict["mismatched_fields"], ["bytes"])

    def test_an_unobserved_digest_stops_instead_of_passing_silently(self) -> None:
        verdict = verify_asset_receipt(entry(), receipt(observed_sha256=None))
        self.assertEqual(verdict["mismatched_fields"], ["sha256_not_observed"])

    def test_a_receipt_may_not_restate_a_registration_it_did_not_use(self) -> None:
        with self.assertRaises(LeanAssetsError):
            verify_asset_receipt(entry(), receipt(registered_sha256="1" * 64))

    def test_a_receipt_for_another_asset_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            verify_asset_receipt(entry(), receipt(asset_id="sam2_repository"))

    def test_recorded_failures_stop_even_when_the_digest_matches(self) -> None:
        verdict = verify_asset_receipt(entry(), receipt(failures=["partial_download"]))
        self.assertEqual(verdict["action"], STOP_ACTION)

    def test_a_dirty_worktree_stops_a_clone(self) -> None:
        clone = entry(
            asset_id="sam2_repository", role="proposal_source_code",
            source_url="https://github.com/facebookresearch/sam2",
            pinned_ref="2b90b9f5ceec907a1c18123530e92e794ad901a4",
            bytes=None, sha256=None, acquisition_mode="clone_to_server",
        )
        dirty = receipt(
            asset_id="sam2_repository", acquisition_mode="clone_to_server",
            source_url="https://github.com/facebookresearch/sam2",
            pinned_ref="2b90b9f5ceec907a1c18123530e92e794ad901a4",
            observed_bytes=None, observed_sha256=None,
            registered_bytes=None, registered_sha256=None,
            worktree_clean_including_untracked=False,
        )
        verdict = verify_asset_receipt(clone, dirty)
        self.assertEqual(verdict["mismatched_fields"], ["worktree_dirty"])

    def test_a_torch_version_that_moved_stops(self) -> None:
        verdict = verify_asset_receipt(entry(), receipt(torch_version_after="2.9.0+cu128"))
        self.assertEqual(verdict["mismatched_fields"], ["torch_version_changed"])


class TestWorkerDerivation(unittest.TestCase):
    def test_the_binding_constraint_is_named(self) -> None:
        plan = derive_worker_count(measurements(), occupancy(), headroom_fraction=0.0)
        # 32/2 = 16 cpu, 100/4 = 25 ram, 31/3 = 10 vram, 33/1 = 33 disk, 6 simulator.
        self.assertEqual(plan["worker_count"], 6)
        self.assertEqual(plan["binding_constraint"], "simulator_concurrency_limit")

    def test_headroom_lowers_the_count(self) -> None:
        tight = occupancy(simulator_concurrency_limit=64)
        full = derive_worker_count(measurements(), tight, headroom_fraction=0.0)
        spared = derive_worker_count(measurements(), tight, headroom_fraction=0.5)
        self.assertEqual(full["binding_constraint"], "vram_gb_per_worker")
        self.assertLess(spared["worker_count"], full["worker_count"])

    def test_a_cpu_only_worker_ignores_vram(self) -> None:
        plan = derive_worker_count(
            measurements(gpu_free_vram_gb=0.0),
            occupancy(vram_gb_per_worker=0.0, simulator_concurrency_limit=64),
            headroom_fraction=0.0)
        self.assertEqual(plan["binding_constraint"], "cpu_cores_per_worker")
        self.assertEqual(plan["worker_count"], 16)

    def test_the_same_inputs_always_give_the_same_plan(self) -> None:
        first = derive_worker_count(measurements(), occupancy(), headroom_fraction=0.25)
        second = derive_worker_count(measurements(), occupancy(), headroom_fraction=0.25)
        self.assertEqual(first, second)

    def test_a_tie_is_broken_by_the_registered_resource_order(self) -> None:
        plan = derive_worker_count(
            measurements(cpu_logical_cores=8, ram_available_gb=16.0),
            occupancy(cpu_cores_per_worker=2.0, ram_gb_per_worker=4.0,
                      vram_gb_per_worker=0.0, disk_gb_per_worker=0.0,
                      simulator_concurrency_limit=64),
            headroom_fraction=0.0)
        self.assertEqual(plan["worker_count"], 4)
        self.assertEqual(plan["binding_constraint"], "cpu_cores_per_worker")

    def test_a_machine_too_small_for_one_worker_raises_instead_of_rounding_up(self) -> None:
        with self.assertRaises(LeanAssetsError):
            derive_worker_count(
                measurements(ram_available_gb=2.0),
                occupancy(ram_gb_per_worker=8.0), headroom_fraction=0.0)

    def test_a_guessed_occupancy_is_rejected(self) -> None:
        missing = occupancy()
        missing["ram_gb_per_worker"] = None
        with self.assertRaises(LeanAssetsError):
            derive_worker_count(measurements(), missing, headroom_fraction=0.0)

    def test_a_headroom_of_one_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            derive_worker_count(measurements(), occupancy(), headroom_fraction=1.0)

    def test_a_missing_measurement_a_worker_needs_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            derive_worker_count(measurements(gpu_free_vram_gb=None), occupancy(),
                                headroom_fraction=0.0)


class TestCapacityReceipt(unittest.TestCase):
    def capacity(self, **overrides: Any) -> dict[str, Any]:
        row = {
            "measurements": measurements(),
            "single_worker_occupancy": occupancy(),
            "derived_worker_count": 6,
            "binding_constraint": "simulator_concurrency_limit",
            "requested_workers": 6,
            "actual_workers": 6,
            "failures": [],
        }
        row.update(overrides)
        return {name: row[name] for name in CAPACITY_RECEIPT_FIELDS}

    def test_a_complete_capacity_receipt_passes(self) -> None:
        validate_capacity_receipt(self.capacity())

    def test_a_receipt_missing_a_measurement_is_rejected(self) -> None:
        partial = measurements()
        del partial["vulkan_resolves"]
        with self.assertRaises(LeanAssetsError):
            validate_capacity_receipt(self.capacity(measurements=partial))

    def test_a_receipt_without_single_worker_occupancy_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_capacity_receipt(self.capacity(single_worker_occupancy={}))

    def test_running_more_workers_than_derived_is_rejected(self) -> None:
        with self.assertRaises(LeanAssetsError):
            validate_capacity_receipt(self.capacity(actual_workers=12))

    def test_running_fewer_workers_than_derived_is_allowed_and_recorded(self) -> None:
        checked = validate_capacity_receipt(self.capacity(actual_workers=2))
        self.assertEqual(checked["requested_workers"], 6)
        self.assertEqual(checked["actual_workers"], 2)


class TestContract(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_contract_matches_this_implementation(self) -> None:
        checked = validate_assets_capacity_contract(self.contract)
        self.assertEqual(checked["schema_version"], CONTRACT_SCHEMA_VERSION)
        self.assertEqual(checked["stage_id"], "S1-01")

    def test_only_the_four_ruled_bits_are_open(self) -> None:
        opened = sorted(name for name, value
                        in self.contract["authorization"].items() if value)
        self.assertEqual(opened, ["dinov2_vit_b14_digest_registration",
                                  "frozen_asset_readonly_verification",
                                  "import_dependency_install",
                                  "server_capacity_probe"])
        self.assertEqual(sorted(self.contract["activation_policy"]
                                ["active_true_authorizations"]), opened)

    def test_every_acquisition_and_run_bit_is_still_closed(self) -> None:
        for name in ("sam2_asset_placement_on_server",
                     "dinov2_vit_b14_asset_placement_on_server",
                     "simulator_asset_installation", "server_run"):
            self.assertIs(self.contract["authorization"][name], False, name)

    def test_the_occupancy_measurement_left_this_stage(self) -> None:
        # It needs an episode run, which this stage keeps closed, so it
        # belongs to S1-02a and may not reappear here under any name.
        self.assertNotIn("single_worker_occupancy_measurement",
                         self.contract["authorization"])
        self.assertEqual(self.contract["worker_rule"]["measurement_stage"], "S1-02a")
        self.assertIn("route_or_episode_generation", self.contract["must_remain_false"])

    def test_reopening_the_measurement_here_is_rejected(self) -> None:
        reopened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        reopened["authorization"]["single_worker_occupancy_measurement"] = False
        reopened["activation_policy"]["active_true_authorizations"].append(
            "single_worker_occupancy_measurement")
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(reopened)

    def test_the_derivation_rule_stays_here_even_though_the_measurement_moved(self) -> None:
        rule = self.contract["worker_rule"]
        self.assertEqual(tuple(rule["derivation_inputs"]), WORKER_DERIVATION_INPUTS)
        self.assertIs(rule["derivation_requires_measured_single_worker_occupancy"], True)
        self.assertIs(rule["concurrency_verified_at_is_not_the_derived_count"], True)
        self.assertEqual(rule["headroom_fraction"], 0.2)

    def test_a_bit_opened_outside_the_ruling_is_rejected(self) -> None:
        opened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        opened["authorization"]["simulator_asset_installation"] = True
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(opened)

    def test_the_dependency_install_stays_inside_its_declared_scope(self) -> None:
        scope = self.contract["activation_policy"]["import_dependency_scope"]
        self.assertEqual(scope["packages"], ["hydra-core", "omegaconf", "iopath"])
        self.assertIs(scope["torch_torchvision_numpy_must_not_change"], True)
        self.assertIs(scope["editable_or_build_install_into_the_pinned_worktree"], False)
        self.assertIn("vm04_d224_frozen_sam2_asset_acquisition_v1.json",
                      scope["governed_by"])

    def test_widening_the_activation_policy_to_a_closed_bit_is_rejected(self) -> None:
        widened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        widened["activation_policy"]["active_true_authorizations"].append("model_training")
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(widened)

    def test_an_activation_policy_not_bound_to_the_ruling_is_rejected(self) -> None:
        drifted = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        drifted["activation_policy"]["opened_by"] = "D-999"
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(drifted)

    def test_claiming_to_have_exercised_a_closed_bit_is_rejected(self) -> None:
        overclaimed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        overclaimed["activation_policy"]["exercised_so_far"].append("server_run")
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(overclaimed)

    def test_the_registry_covers_exactly_the_assets_with_authorization_bits(self) -> None:
        registry = validate_asset_registry(self.contract["asset_registry"])
        self.assertEqual(set(registry), set(AUTHORIZATION_OF_ASSET))

    def test_no_asset_is_blocked_on_its_registration_any_more(self) -> None:
        registry = validate_asset_registry(self.contract["asset_registry"])
        blocked = sorted(name for name, row in registry.items()
                         if row["acquisition_status"] == "registration_incomplete")
        self.assertEqual(blocked, [])

    def test_vit_b14_carries_the_identity_recorded_in_log_223(self) -> None:
        registry = validate_asset_registry(self.contract["asset_registry"])
        row = registry["dinov2_vit_b14_checkpoint"]
        self.assertEqual(
            row["source_url"],
            "https://dl.fbaipublicfiles.com/dinov2/dinov2_vitb14/dinov2_vitb14_pretrain.pth")
        self.assertEqual(row["bytes"], 346378731)
        self.assertEqual(
            row["sha256"],
            "0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73")
        self.assertEqual(row["registered_by"], "D-224-S1")
        # Registered now means it follows the ordinary file path, but placing
        # it on the server is still a separate, closed bit.
        self.assertEqual(row["acquisition_mode"], "download_to_server")
        self.assertIs(self.contract["authorization"]
                      ["dinov2_vit_b14_asset_placement_on_server"], False)

    def test_the_house_pool_carries_the_upstream_lfs_identity(self) -> None:
        registry = validate_asset_registry(self.contract["asset_registry"])
        pool = registry["procthor_10k_dataset"]
        self.assertEqual(pool["pinned_ref"], "d54954a81e7126001e552c2d7904ee2e0d49eaae")
        self.assertEqual(pool["bytes"], 52316238)
        self.assertEqual(
            pool["sha256"],
            "d64450ec821aef55351f62885e4d56b3f0d948693af467bb7f6532850ef4fa37")
        self.assertEqual(pool["registered_by"], "D-224-S1")

    def test_the_frozen_sam_identity_matches_d215(self) -> None:
        registry = validate_asset_registry(self.contract["asset_registry"])
        d215 = json.loads((PROJECT_ROOT / "configs" / "vsmt"
                           / "vm04_d215_frontend_freeze_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["sam2_checkpoint"]["sha256"],
                         d215["sam2"]["checkpoint_sha256"])
        self.assertEqual(registry["sam2_checkpoint"]["bytes"],
                         d215["sam2"]["checkpoint_bytes"])
        self.assertEqual(registry["sam2_model_config"]["sha256"],
                         d215["sam2"]["official_model_config_sha256"])
        self.assertEqual(registry["sam2_repository"]["pinned_ref"],
                         d215["sam2"]["repository_commit"])

    def test_a_stop_condition_downgraded_to_a_retry_is_rejected(self) -> None:
        weakened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        weakened["stop_conditions"]["digest_mismatch"] = "retry_with_a_mirror"
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(weakened)

    def test_opening_the_mirror_escape_hatch_is_rejected(self) -> None:
        weakened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        weakened["stop_conditions"]["may_retry_with_another_version_or_mirror"] = True
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(weakened)

    def test_a_capacity_probe_allowed_to_load_a_model_is_rejected(self) -> None:
        weakened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        weakened["capacity_probe"]["may_load_a_model"] = True
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(weakened)

    def test_the_headroom_is_frozen_at_the_ruled_value(self) -> None:
        rule = self.contract["worker_rule"]
        self.assertEqual(rule["headroom_fraction"], 0.2)
        self.assertEqual(rule["headroom_fraction_frozen_by"], "D-224-S1")
        self.assertNotIn("worker_rule.headroom_fraction",
                         self.contract["policy_values_without_defaults"])

    def test_a_headroom_frozen_without_naming_its_ruling_is_rejected(self) -> None:
        loose = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        del loose["worker_rule"]["headroom_fraction_frozen_by"]
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(loose)

    def test_a_frozen_headroom_still_advertised_as_open_is_rejected(self) -> None:
        # Otherwise a later run could treat it as free to re-pick.
        stale = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        stale["policy_values_without_defaults"].append("worker_rule.headroom_fraction")
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(stale)

    def test_a_null_headroom_must_still_be_registered_as_open(self) -> None:
        reopened = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        reopened["worker_rule"]["headroom_fraction"] = None
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(reopened)

    def test_a_headroom_of_one_or_more_is_rejected(self) -> None:
        silly = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        silly["worker_rule"]["headroom_fraction"] = 1.0
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(silly)

    def test_the_headroom_actually_bites_in_the_derivation(self) -> None:
        # 0.2 means every measured resource is used at eighty percent.
        frozen = self.contract["worker_rule"]["headroom_fraction"]
        full = derive_worker_count(measurements(),
                                   occupancy(simulator_concurrency_limit=64),
                                   headroom_fraction=0.0)
        spared = derive_worker_count(measurements(),
                                     occupancy(simulator_concurrency_limit=64),
                                     headroom_fraction=frozen)
        self.assertLess(spared["worker_count"], full["worker_count"])

    def test_the_contract_supersedes_its_reviewed_v1(self) -> None:
        import hashlib
        supersedes = self.contract["supersedes_contract"]
        self.assertTrue(supersedes["v1_bytes_frozen"])
        v1 = PROJECT_ROOT / supersedes["path"]
        self.assertEqual(hashlib.sha256(v1.read_bytes()).hexdigest(),
                         supersedes["v1_sha256"])

    def test_the_s0_dependencies_point_at_the_v2_contracts(self) -> None:
        depends = self.contract["depends_on"]
        self.assertTrue(depends["s0_02_contract"].endswith("_v2.json"))
        self.assertTrue(depends["s0_03_contract"].endswith("_v2.json"))
        for key in ("s0_02_contract", "s0_03_contract"):
            self.assertTrue((PROJECT_ROOT / depends[key]).exists(), key)

    def test_a_conflict_resolved_without_a_ruling_or_evidence_is_rejected(self) -> None:
        early = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        target = next(c for c in early["known_conflicts"]
                      if c["conflict_id"] == "vit_b14_unregistered")
        target["resolution"] = "just use whatever downloads, no ruling behind it"
        target["evidence_of_resolution"] = None
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(early)

    def test_evidence_without_a_resolution_is_rejected(self) -> None:
        early = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        target = next(c for c in early["known_conflicts"]
                      if c["conflict_id"] == "vit_b14_unregistered")
        target["resolution"] = None
        target["evidence_of_resolution"] = "LOG-221"
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(early)

    def test_an_unresolved_conflict_must_still_block_something(self) -> None:
        early = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        target = next(c for c in early["known_conflicts"]
                      if c["conflict_id"] == "vit_b14_unregistered")
        target["resolution"] = None
        target["blocks"] = []
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(early)

    def test_all_four_conflicts_are_discharged_and_none_still_blocks(self) -> None:
        discharged = {c["conflict_id"]: c for c in self.contract["known_conflicts"]
                      if c["evidence_of_resolution"] is not None}
        self.assertEqual(sorted(discharged),
                         ["cloudrendering_requires_vulkan", "procthor_10k_tag_unchosen",
                          "python_version_conflict", "vit_b14_unregistered"])
        for conflict in discharged.values():
            self.assertEqual(conflict["blocks"], [], conflict["conflict_id"])
        self.assertEqual(discharged["vit_b14_unregistered"]["evidence_of_resolution"],
                         "LOG-223")
        for name in ("cloudrendering_requires_vulkan", "procthor_10k_tag_unchosen",
                     "python_version_conflict"):
            self.assertEqual(discharged[name]["evidence_of_resolution"], "LOG-221")

    def test_a_ruling_that_stopped_blocking_before_it_ran_is_rejected(self) -> None:
        early = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        target = next(c for c in early["known_conflicts"]
                      if c["conflict_id"] == "vit_b14_unregistered")
        target["evidence_of_resolution"] = None
        target["blocks"] = []
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(early)

    def test_a_discharged_conflict_that_still_blocks_is_rejected(self) -> None:
        stale = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        target = next(c for c in stale["known_conflicts"]
                      if c["conflict_id"] == "procthor_10k_tag_unchosen")
        target["blocks"] = ["S1-02"]
        with self.assertRaises(LeanAssetsError):
            validate_assets_capacity_contract(stale)

    def test_every_ruling_is_bound_to_the_decision_id(self) -> None:
        rulings = self.contract["user_rulings"]
        self.assertEqual(rulings["decision_id"], "D-224-S1")
        self.assertEqual(len(rulings["rulings"]), 11)

    def test_the_contract_binds_the_d224_governance_core_not_its_whole_file(self) -> None:
        depends = self.contract["depends_on"]
        self.assertIn("d224_supersession_core_sha256", depends)
        d224 = json.loads((PROJECT_ROOT / "configs" / "vsmt"
                           / "vm04_d224_frozen_sam2_asset_acquisition_v1.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(depends["d224_supersession_core_sha256"],
                         d224["supersession_core_sha256"])

    def test_the_declared_null_values_really_are_null(self) -> None:
        for path in self.contract["policy_values_without_defaults"]:
            node: Any = self.contract
            for part in path.split("."):
                if isinstance(node, list):
                    node = next(item for item in node
                                if item.get("asset_id") == part
                                or item.get("conflict_id") == part)
                else:
                    node = node[part]
            self.assertIsNone(node, path)

    def test_the_module_opens_no_file_and_runs_no_process(self) -> None:
        source = (SRC_ROOT / "vsmt" / "lean_assets.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"__future__", "math", "typing", "cpmt"})
        called = {node.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        for forbidden in ("open", "eval", "exec", "__import__"):
            self.assertNotIn(forbidden, called, forbidden)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
