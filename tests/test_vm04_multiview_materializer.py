"""Tests for append-only multiview raw-to-packet materialization."""

import copy
import hashlib
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
from cpmt.errors import InvariantViolation  # noqa: E402
from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.causal_prior import (  # noqa: E402
    advance_public_bootstrap,
    build_causal_prior,
    empty_public_memory,
)
from vsmt.vm04_public_context import (  # noqa: E402
    REGISTERED_ACTIONS,
    make_public_frame_contexts,
)
from tests.test_vm04_public_frontend_sequence import bootstrap_config  # noqa: E402
from tests.test_vm04_materializer_config import (  # noqa: E402
    asset_receipt,
    fixture as materializer_config,
)
from tests.test_vm04_public_frontend_sequence import (  # noqa: E402
    context_bundle as sealed_context_bundle,
    tokens as patch_tokens,
)
from tests.test_vm04_program_matcher import config as program_matcher_config  # noqa: E402
from vsmt.vm04_program_construction import (  # noqa: E402
    make_program_construction_plan,
)
from vsmt.vm04_program_matcher import matcher_config_sha256  # noqa: E402
from vsmt.vm04_online_plan_seal import (  # noqa: E402
    make_online_program_plan_request,
    seal_online_program_construction_plan,
)


CODE_SHA = "a" * 64
CONFIG_SHA = "b" * 64
ASSET_SHA = "c" * 64


def _code_manifest():
    value = {
        "schema_version": "vsmt-vm04-materializer-code-manifest-v1",
        "reviewed_git_commit": "d" * 40,
        "source_inventory_policy": {
            "entry_paths": [
                "ops/vsmt/vm04_multiview_materializer.py",
                "ops/vsmt/vm04_observation_stage.py",
            ],
            "package_roots": ["src/cpmt", "src/vsmt"],
            "recursive_suffix": ".py",
            "symlinks_allowed": False,
        },
        "sources": [{
            "path": "ops/vsmt/vm04_multiview_materializer.py",
            "sha256": "e" * 64,
        }],
    }
    value["manifest_sha256"] = hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()
    return value


def _build_raw_episode(episode_root, route_plan=None):
    route_plan = route_plan or _plan()
    store = raw.RawEpisodeStore(
        episode_root, plan=route_plan, contract=CONTRACT)
    result = worker._execute_route_core(
        Controller(), plan=route_plan, contract=CONTRACT,
        action_request_templates=ACTION_REQUESTS,
        trusted_public_frame_extractor=store.extract_public_frame,
        public_capture=_capture(),
        private_intervention=lambda event, route: {
            "success": True, "private_id_exported": False,
        },
    )
    assert result["status"] == "raw_complete"
    store.finalize(result)


def _birth_route():
    route = _plan()
    route["program"] = "BIRTH"
    route["visibility_subject_kind"] = "reveal_locus"
    route.pop("route_plan_sha256")
    route["route_plan_sha256"] = hashlib.sha256(
        canonical_json(route).encode("utf-8")
    ).hexdigest()
    return route


def _online_birth_request(route):
    return make_online_program_plan_request(
        episode_id=route["episode_id"], family_id="family:fixture",
        program="BIRTH", route_plan_sha256=route["route_plan_sha256"],
        terminal_observation_index=route["terminal_reobservation_indices"][-1],
        precondition_refs={
            "reveal_locus_public_ref": "locus:fixture",
            "absence_scope_sha256": "f" * 64,
        },
        visibility_subject_seal_sha256=
            route["visibility_subject_seal_sha256"],
        matcher_config_sha256=matcher_config_sha256(program_matcher_config()),
    )


def _materialize(public_raw, private_raw, index):
    packet = packet_fixture(graph_fixture())
    packet["sample_id_hash"] = f"{index + 1:x}" * 64
    entity = next(
        row for row in packet["region_observations"]
        if row["structure_kind"] == "entity")
    entity["mask_sha256"] = materializer._mask_sha256(
        private_raw["instance_masks"][0])
    return {
        "public_packet": packet,
        "private_crosswalk": {
            "schema_version": "vsmt-vm04-private-region-crosswalk-v1",
            "observation_index": index,
            "bindings": [{
                "instance_id": private_raw["private_instance_ids"][0],
                "region_id": entity["region_id"],
                "mask_sha256": entity["mask_sha256"],
            }],
        },
    }


class FixtureSequenceMaterializer:
    def __init__(self, episode_root):
        self.episode_root = Path(episode_root)
        self.memory = empty_public_memory()
        self.memories = []
        self.packets = []
        self.config = bootstrap_config()

    def __call__(self, public_raw, private_raw, index):
        output = _materialize(public_raw, private_raw, index)
        packet = packet_fixture(self.memory)
        packet["sample_id_hash"] = f"{index + 1:x}" * 64
        packet["decision_time_s"] = float(index + 1)
        entity = next(
            row for row in packet["region_observations"]
            if row["structure_kind"] == "entity"
        )
        entity["mask_sha256"] = materializer._mask_sha256(
            private_raw["instance_masks"][0]
        )
        output["public_packet"] = packet
        output["private_crosswalk"]["bindings"][0]["region_id"] = entity[
            "region_id"
        ]
        output["private_crosswalk"]["bindings"][0]["mask_sha256"] = entity[
            "mask_sha256"
        ]
        advanced = advance_public_bootstrap(
            packet, self.memory, config=self.config,
        )
        self.memory = advanced["post_memory"]
        self.memories.append(copy.deepcopy(self.memory))
        self.packets.append(packet)
        return output

    def seal_program_construction_plan_before_observation(
        self, *, request, route_plan, observation_index,
        materializer_code_sha256,
    ):
        return seal_online_program_construction_plan(
            request=request, route_plan=route_plan,
            prior_memory=self.memory,
            last_completed_observation_index=observation_index - 1,
            materializer_code_sha256=materializer_code_sha256,
        )

    def finalized_result(self):
        replay = build_causal_prior(
            self.packets, config=self.config, builder_code_sha256=CODE_SHA,
        )
        route = json.loads((
            self.episode_root / "provenance/route.json"
        ).read_text(encoding="utf-8"))
        actions = sorted(REGISTERED_ACTIONS)
        bundle = make_public_frame_contexts(
            route,
            decision_times_s=[
                float(index + 1) for index in range(len(self.packets))
            ],
            decision_time_rule_id="fixture.index-seconds.v1",
            action_command_vectors={
                action: [
                    1.0 if row == column else 0.0 for column in range(8)
                ]
                for row, action in enumerate(actions)
            },
            action_encoding_id="fixture.one-hot.v1",
            robot_states=[
                {"feature_names": [], "values": []}
                for _ in self.packets
            ],
            public_constants=self.packets[0]["public_constants"],
        )
        return {
            "prior_memory": replay["prior_memory"],
            "causal_prior_receipt": replay["receipt"],
            "public_frame_context_manifest": bundle["manifest"],
            "ordered_public_packet_sha256s": replay["receipt"][
                "ordered_public_packet_sha256s"
            ],
        }


def _fixture_materializer(episode_root):
    return FixtureSequenceMaterializer(episode_root)


class MultiviewMaterializerTests(unittest.TestCase):
    def test_online_plan_is_written_before_terminal_frame_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            route = _birth_route()
            _build_raw_episode(episode, route)
            terminal_rgb = episode / "public/raw/frame_0005/rgb.npy"
            with terminal_rgb.open("ab") as handle:
                handle.write(b"terminal-tamper")
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_fixture_materializer(episode),
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
                online_construction_plan_request=_online_birth_request(route),
            )
            self.assertEqual(result["status"], "materialized_failure")
            self.assertEqual(result["frame_count"], 5)
            seal_root = episode / "materialized/construction-plan-seal"
            self.assertTrue((
                seal_root / "online-plan-temporal.sealed.json"
            ).is_file())
            temporal = json.loads((
                seal_root / "online-plan-temporal.receipt.json"
            ).read_text(encoding="utf-8"))
            self.assertEqual(temporal["sealed_before_observation_index"], 5)
            self.assertFalse(temporal[
                "terminal_public_frame_opened_before_seal"
            ])
            self.assertFalse((episode / (
                "materialized/public/materializer.receipt.json"
            )).exists())

    def test_seals_failed_public_matcher_as_construction_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            route = _birth_route()
            _build_raw_episode(episode, route)
            callback = _fixture_materializer(episode)
            result = materializer.materialize_episode_core(
                episode, materialize_frame=callback,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
            )
            self.assertEqual(result["status"], "materialized_complete")
            prior = callback.memories[
                route["terminal_reobservation_indices"][-1] - 1
            ]
            match_config = program_matcher_config()
            construction = make_program_construction_plan(
                episode_id=route["episode_id"], family_id="family:fixture",
                program="BIRTH", prior_memory=prior,
                prior_memory_sha256=prior["graph_hash"],
                precondition_refs={
                    "reveal_locus_public_ref": "locus:fixture",
                    "absence_scope_sha256": "f" * 64,
                },
                visibility_subject_seal_sha256=
                    route["visibility_subject_seal_sha256"],
                matcher_config_sha256=matcher_config_sha256(match_config),
                artifact_plan=None,
            )
            sealed = materializer.seal_episode_construction_evidence_core(
                episode, contract=CONTRACT,
                construction_plan=construction,
                matcher_prior_memory=prior,
                matcher_config=match_config,
            )
            self.assertEqual(sealed["status"],
                             "construction_evidence_sealed")
            self.assertEqual(sealed["episode_construction_status"],
                             "construction_failure")
            self.assertFalse(sealed["program_public_match_satisfied"])
            verified = materializer.verify_episode_construction_evidence(
                episode, contract=CONTRACT,
            )
            self.assertEqual(verified["episode_construction_status"],
                             "construction_failure")
            audit = json.loads((episode / (
                "materialized/construction-audit/"
                "episode-construction.receipt.json"
            )).read_text(encoding="utf-8"))
            self.assertFalse(
                audit["deployment_reader_may_open_construction_audit"]
            )
            matcher_path = episode / (
                "materialized/construction-audit/program-matcher.receipt.json"
            )
            matcher_path.write_text(
                matcher_path.read_text(encoding="utf-8") + " ",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                    materializer.ObservationConstructionError,
                    "construction audit file digest changed"):
                materializer.verify_episode_construction_evidence(
                    episode, contract=CONTRACT,
                )

    def test_construction_audit_rejects_wrong_causal_prior(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            route = _birth_route()
            _build_raw_episode(episode, route)
            callback = _fixture_materializer(episode)
            materializer.materialize_episode_core(
                episode, materialize_frame=callback,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
            )
            correct_prior = callback.memories[
                route["terminal_reobservation_indices"][-1] - 1
            ]
            wrong_prior = callback.memories[-1]
            match_config = program_matcher_config()
            construction = make_program_construction_plan(
                episode_id=route["episode_id"], family_id="family:fixture",
                program="BIRTH", prior_memory=wrong_prior,
                prior_memory_sha256=wrong_prior["graph_hash"],
                precondition_refs={
                    "reveal_locus_public_ref": "locus:fixture",
                    "absence_scope_sha256": "f" * 64,
                },
                visibility_subject_seal_sha256=
                    route["visibility_subject_seal_sha256"],
                matcher_config_sha256=matcher_config_sha256(match_config),
                artifact_plan=None,
            )
            self.assertNotEqual(correct_prior["graph_hash"],
                                wrong_prior["graph_hash"])
            with self.assertRaisesRegex(
                    materializer.ObservationConstructionError,
                    "not the causal memory immediately before terminal observation"):
                materializer.seal_episode_construction_evidence_core(
                    episode, contract=CONTRACT,
                    construction_plan=construction,
                    matcher_prior_memory=wrong_prior,
                    matcher_config=match_config,
                )
            self.assertFalse((episode / (
                "materialized/construction-audit"
            )).exists())

    def test_materializes_all_frames_and_seals_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_fixture_materializer(episode),
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
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
                episode, materialize_frame=_fixture_materializer(episode),
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
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
                materializer_assets_receipt_sha256=ASSET_SHA,
            )
            self.assertEqual(result["frame_count"], 1)
            self.assertTrue((
                episode / "materialized/public/frame_0000.json"
            ).is_file())
            public_failure = (episode / (
                "materialized/public/materializer.failure.json"
            )).read_text(encoding="utf-8")
            self.assertNotIn("private diagnostic detail", public_failure)

    def test_stateless_callback_cannot_seal_a_complete_episode(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_materialize,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
            )
            self.assertEqual(result["status"], "materialized_failure")
            self.assertEqual(result["frame_count"], 6)
            self.assertFalse((episode / (
                "materialized/public/materializer.receipt.json"
            )).exists())
            failure = json.loads((episode / (
                "materialized/private/materializer.failure.json"
            )).read_text(encoding="utf-8"))
            self.assertIn("finalized_result", failure["exception_message"])

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
                materializer_assets_receipt_sha256=ASSET_SHA,
            )
            self.assertEqual(result["status"], "materialized_failure")
            self.assertEqual(result["frame_count"], 0)
            private_failure = json.loads((episode / (
                "materialized/private/materializer.failure.json"
            )).read_text(encoding="utf-8"))
            self.assertIn("opaque ordinals", private_failure["exception_message"])

    def test_crosswalk_cannot_bind_instance_to_a_different_public_mask(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)

            def wrong_mask(public_raw, private_raw, index):
                output = _materialize(public_raw, private_raw, index)
                entity = next(
                    row for row in output["public_packet"]["region_observations"]
                    if row["structure_kind"] == "entity")
                entity["mask_sha256"] = "f" * 64
                output["private_crosswalk"]["bindings"][0][
                    "mask_sha256"] = "f" * 64
                return output

            result = materializer.materialize_episode_core(
                episode, materialize_frame=wrong_mask,
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
            )
            self.assertEqual(result["status"], "materialized_failure")
            self.assertEqual(result["frame_count"], 0)
            private_failure = json.loads((episode / (
                "materialized/private/materializer.failure.json"
            )).read_text(encoding="utf-8"))
            self.assertIn(
                "uniquely bind a public entity mask",
                private_failure["exception_message"],
            )

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
                    materializer_assets_receipt_sha256=ASSET_SHA,
                )
            self.assertFalse(absent.exists())

    def test_configured_production_entry_uses_sealed_config_digest(self):
        config = materializer_config()
        contract = copy.deepcopy(CONTRACT)
        contract["crosswalk_provenance"][
            "expected_materializer_code_sha256"
        ] = CODE_SHA
        contract["crosswalk_provenance"][
            "expected_materializer_config_sha256"
        ] = config["config_sha256"]
        with tempfile.TemporaryDirectory() as temporary:
            absent = Path(temporary) / "absent-episode"
            with self.assertRaisesRegex(
                    materializer.ObservationConstructionError,
                    "materialization is not authorized"):
                materializer.run_authorized_materializer_from_config(
                    absent,
                    contract=contract,
                    raw_materializer_config=config,
                    public_frame_context_bundle=sealed_context_bundle(),
                    patch_token_extractor=patch_tokens,
                    materializer_code_sha256=CODE_SHA,
                    materializer_assets_receipt=asset_receipt(config),
                )
            self.assertFalse(absent.exists())

    def test_verified_model_entry_authorizes_before_asset_or_episode_read(self):
        config = materializer_config()
        code_manifest = _code_manifest()
        contract = copy.deepcopy(CONTRACT)
        contract["crosswalk_provenance"][
            "expected_materializer_code_sha256"
        ] = code_manifest["manifest_sha256"]
        contract["crosswalk_provenance"][
            "expected_materializer_config_sha256"
        ] = config["config_sha256"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(
                    materializer.ObservationConstructionError,
                    "materialization is not authorized"):
                materializer.run_authorized_materializer_with_verified_model(
                    root / "absent-episode",
                    contract=contract,
                    raw_materializer_config=config,
                    public_frame_context_bundle=sealed_context_bundle(),
                    repository_root=root / "absent-repository",
                    checkpoint_path=root / "absent-checkpoint.pth",
                    materializer_code_manifest=code_manifest,
                    code_repository_root=root / "absent-code-repository",
                )
            self.assertEqual(list(root.iterdir()), [])

    def test_verifier_rejects_packet_changed_after_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_fixture_materializer(episode),
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
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

    def test_verifier_rejects_prior_memory_changed_after_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode"
            _build_raw_episode(episode)
            result = materializer.materialize_episode_core(
                episode, materialize_frame=_fixture_materializer(episode),
                materializer_code_sha256=CODE_SHA,
                materializer_config_sha256=CONFIG_SHA,
                materializer_assets_receipt_sha256=ASSET_SHA,
            )
            self.assertEqual(result["status"], "materialized_complete")
            prior_path = episode / "materialized/public/prior-memory.json"
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
            prior["graph_id"] = "graph:tampered"
            prior_path.write_text(json.dumps(prior), encoding="utf-8")
            with self.assertRaises(InvariantViolation):
                materializer.verify_materialized_episode(episode)


if __name__ == "__main__":
    unittest.main()
