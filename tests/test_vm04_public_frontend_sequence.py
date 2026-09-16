from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tests.test_vm04_public_frontend import config as frontend_config  # noqa: E402
from vsmt.causal_prior import PublicBootstrapConfig  # noqa: E402
from vsmt.vm04_public_context import (  # noqa: E402
    REGISTERED_ACTIONS,
    make_public_frame_contexts,
)
from vsmt.vm04_public_frontend_sequence import (  # noqa: E402
    Vm04PublicFrontendSequence,
)
from vsmt.vm04_online_plan_seal import (  # noqa: E402
    make_online_program_plan_request,
)


def bootstrap_config() -> PublicBootstrapConfig:
    return PublicBootstrapConfig(
        association_rules={
            kind: {
                "visual_weight": 0.5,
                "geometry_weight": 0.5,
                "geometry_scale_m": 1.0,
                "association_threshold": 0.7,
            }
            for kind in ("entity", "surface", "fragment")
        },
        support_envelope_reliability_threshold=0.9,
        maximum_regions_per_packet=512,
        builder_revision="fixture.v1",
    )


def context_bundle() -> dict:
    constants = {
        "coordinate_frame": "map",
        "depth_unit": "metre",
        "descriptor_model_id": "dinov2.vits14",
        "proposal_model_id": "l1.oracle-mask.public-depth.v1",
    }
    route = {
        "schema_version": "vsmt-vm04-public-observation-route-v1",
        "consumer_scope": "construction_provenance_only_not_adapter_input",
        "episode_id": "episode:sequence",
        "branch_type": "out_of_view_then_reobservation",
        "visibility_subject_kind": "target_track",
        "visibility_subject_public_ref": "subject:0001",
        "visibility_subject_seal_sha256": "a" * 64,
        "visibility_builder_config_sha256": "b" * 64,
        "initial_pose": {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0, "yaw_deg": 0.0},
        "registered_actions": [{"step_index": 0, "action": "MoveAhead"}],
        "phase_observation_indices": {
            "precondition_visible": [0, 1],
            "challenge_hidden": [0, 1],
            "reobserved": [0, 1],
        },
        "planned_poses": {
            name: {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0, "yaw_deg": 0.0}
            for name in ("precondition", "challenge", "reobservation")
        },
        "intervention_after_observation_index": None,
        "terminal_reobservation_indices": [0, 1],
        "private_route_plan_sha256": "d" * 64,
    }
    from cpmt.hashing import canonical_json
    import hashlib
    route["public_route_sha256"] = hashlib.sha256(
        canonical_json(route).encode("utf-8")
    ).hexdigest()
    actions = sorted(REGISTERED_ACTIONS)
    return make_public_frame_contexts(
        route,
        decision_times_s=[0.0, 1.0],
        decision_time_rule_id="fixture.index-seconds.v1",
        action_command_vectors={
            action: [1.0 if row == column else 0.0 for column in range(8)]
            for row, action in enumerate(actions)
        },
        action_encoding_id="fixture.one-hot.v1",
        robot_states=[
            {"feature_names": [], "values": []},
            {"feature_names": [], "values": []},
        ],
        public_constants=constants,
    )


def raws(index: int):
    mask = np.zeros((1, 224, 224), dtype=np.uint8)
    mask[0, :14, :14] = 1
    public = {
        "rgb": np.zeros((224, 224, 3), dtype=np.uint8),
        "depth_m": np.full((224, 224), 2.0, dtype=np.float32),
        "camera": {
            "pose": {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            "calibration": {
                "fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5,
            },
        },
        "rgb_sha256": "a" * 64,
        "depth_sha256": "b" * 64,
        "source_frame_sha256": f"{index + 10:x}" * 64,
    }
    private = {
        "instance_masks": mask,
        "private_instance_ids": ["Chair|private"],
    }
    return public, private


def tokens(_rgb, _index):
    result = np.zeros((16, 16, 4), dtype=np.float32)
    result[..., 0] = 1.0
    return result


class Vm04PublicFrontendSequenceTests(unittest.TestCase):
    def test_online_plan_seals_current_memory_before_next_frame(self):
        callback = Vm04PublicFrontendSequence(
            public_frame_context_bundle=context_bundle(),
            patch_token_extractor=tokens,
            frontend_config=frontend_config(),
            bootstrap_config=bootstrap_config(),
            builder_code_sha256="c" * 64,
        )
        callback(*raws(0), 0)
        route = {
            "episode_id": "episode:sequence",
            "program": "BIRTH",
            "route_plan_sha256": "d" * 64,
            "visibility_subject_seal_sha256": "a" * 64,
            "terminal_reobservation_indices": [0, 1],
            "split_merge_artifact_plan": None,
        }
        request = make_online_program_plan_request(
            episode_id=route["episode_id"], family_id="family:fixture",
            program="BIRTH", route_plan_sha256=route["route_plan_sha256"],
            terminal_observation_index=1,
            precondition_refs={
                "reveal_locus_public_ref": "locus:fixture",
                "absence_scope_sha256": "e" * 64,
            },
            visibility_subject_seal_sha256=
                route["visibility_subject_seal_sha256"],
            matcher_config_sha256="f" * 64,
        )
        sealed = callback.seal_program_construction_plan_before_observation(
            request=request, route_plan=route, observation_index=1,
            materializer_code_sha256="1" * 64,
        )
        self.assertEqual(
            sealed["matcher_prior_memory"]["graph_hash"],
            sealed["construction_plan"]["prior_memory_sha256"],
        )
        self.assertEqual(
            sealed["temporal_receipt"]["last_completed_observation_index"], 0
        )
        with self.assertRaisesRegex(ValueError, "exactly once"):
            callback.seal_program_construction_plan_before_observation(
                request=request, route_plan=route, observation_index=1,
                materializer_code_sha256="1" * 64,
            )
        callback(*raws(1), 1)

    def test_contiguous_frames_build_and_replay_one_public_memory_chain(self):
        callback = Vm04PublicFrontendSequence(
            public_frame_context_bundle=context_bundle(),
            patch_token_extractor=tokens,
            frontend_config=frontend_config(),
            bootstrap_config=bootstrap_config(),
            builder_code_sha256="c" * 64,
        )
        first = callback(*raws(0), 0)
        second = callback(*raws(1), 1)
        final = callback.finalized_result()

        self.assertEqual(first["private_crosswalk"]["observation_index"], 0)
        self.assertEqual(second["private_crosswalk"]["observation_index"], 1)

        self.assertEqual(
            first["public_packet"]["prior_memory_ref"]["graph_sha256"],
            final["causal_prior_receipt"]["initial_memory_sha256"],
        )
        self.assertEqual(
            second["public_packet"]["prior_memory_ref"]["graph_sha256"],
            final["causal_prior_receipt"]["version_chain_sha256s"][1],
        )
        self.assertEqual(
            final["prior_memory"]["graph_hash"],
            final["causal_prior_receipt"]["final_prior_memory_sha256"],
        )
        self.assertEqual(
            final["ordered_public_packet_sha256s"],
            final["causal_prior_receipt"]["ordered_public_packet_sha256s"],
        )

    def test_out_of_order_or_incomplete_finalize_fails_closed(self):
        callback = Vm04PublicFrontendSequence(
            public_frame_context_bundle=context_bundle(),
            patch_token_extractor=tokens,
            frontend_config=frontend_config(),
            bootstrap_config=bootstrap_config(),
            builder_code_sha256="c" * 64,
        )
        with self.assertRaisesRegex(ValueError, "contiguous from zero"):
            callback(*raws(1), 1)
        callback(*raws(0), 0)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            callback.finalized_result()

    def test_api_has_no_program_target_teacher_or_future_channel(self):
        names = inspect.signature(Vm04PublicFrontendSequence).parameters
        self.assertFalse(any(
            token in name
            for name in names
            for token in ("program", "target", "teacher", "future")
        ))
        malformed = context_bundle()
        malformed["contexts"][0]["private_program"] = "SPLIT"
        with self.assertRaisesRegex(ValueError, "unexpected fields"):
            Vm04PublicFrontendSequence(
                public_frame_context_bundle=malformed,
                patch_token_extractor=tokens,
                frontend_config=frontend_config(),
                bootstrap_config=bootstrap_config(),
                builder_code_sha256="c" * 64,
            )


if __name__ == "__main__":
    unittest.main()
