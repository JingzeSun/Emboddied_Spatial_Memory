"""Stateful trusted callback for one VM-04 public materialization sequence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import clone_json

from .causal_prior import (
    PublicBootstrapConfig,
    advance_public_bootstrap,
    build_causal_prior,
    empty_public_memory,
)
from .contracts import canonical_sha256
from .vm04_public_context import validate_public_frame_context_bundle
from .vm04_online_plan_seal import seal_online_program_construction_plan
from .vm04_public_frontend import (
    Vm04PublicFrontendConfig,
    materialize_vm04_public_frontend_frame,
)
from .vm04_public_packet_builder import make_public_packet


class Vm04PublicFrontendSequence:
    """Consume contiguous raw frames and preserve the public memory chain."""

    def __init__(
        self, *, public_frame_context_bundle: Mapping[str, Any],
        patch_token_extractor: Callable[[np.ndarray, int], Any],
        frontend_config: Vm04PublicFrontendConfig,
        bootstrap_config: PublicBootstrapConfig,
        builder_code_sha256: str,
    ) -> None:
        bundle = validate_public_frame_context_bundle(public_frame_context_bundle)
        contexts = bundle["contexts"]
        if not contexts:
            raise ValueError("public contexts must be nonempty")
        if not callable(patch_token_extractor):
            raise ValueError("patch_token_extractor must be callable")
        if type(frontend_config) is not Vm04PublicFrontendConfig:
            raise ValueError("frontend_config has the wrong type")
        if type(bootstrap_config) is not PublicBootstrapConfig:
            raise ValueError("bootstrap_config has the wrong type")

        self._contexts = contexts
        self._context_manifest = bundle["manifest"]
        self._extract_tokens = patch_token_extractor
        self._frontend_config = frontend_config
        self._bootstrap_config = bootstrap_config
        self._builder_code_sha256 = builder_code_sha256
        self._memory = empty_public_memory()
        self._prior_free_space: list[Sequence[Any]] = []
        self._packets: list[dict[str, Any]] = []
        self._next_index = 0
        self._final: dict[str, Any] | None = None
        self._online_plan_seal: dict[str, Any] | None = None

    def seal_program_construction_plan_before_observation(
        self, *, request: Mapping[str, Any], route_plan: Mapping[str, Any],
        observation_index: int, materializer_code_sha256: str,
    ) -> dict[str, Any]:
        """Seal the current public memory before the terminal raw frame opens."""

        if self._final is not None or self._online_plan_seal is not None:
            raise ValueError("online construction plan may be sealed exactly once")
        if observation_index != self._next_index or observation_index <= 0:
            raise ValueError(
                "online construction plan must seal at the next positive observation"
            )
        sealed = seal_online_program_construction_plan(
            request=request,
            route_plan=route_plan,
            prior_memory=self._memory,
            last_completed_observation_index=observation_index - 1,
            materializer_code_sha256=materializer_code_sha256,
        )
        self._online_plan_seal = clone_json(sealed)
        return clone_json(sealed)

    def __call__(
        self, public_raw: Mapping[str, Any], private_raw: Mapping[str, Any],
        index: int,
    ) -> dict[str, Any]:
        if self._final is not None:
            raise ValueError("public front-end sequence is already finalized")
        if index != self._next_index or not 0 <= index < len(self._contexts):
            raise ValueError("public front-end frames must be contiguous from zero")
        required_public = {
            "rgb", "depth_m", "camera", "rgb_sha256", "depth_sha256",
            "source_frame_sha256",
        }
        required_private = {"instance_masks", "private_instance_ids"}
        if not isinstance(public_raw, Mapping) or not required_public.issubset(public_raw):
            raise ValueError("verified public raw frame is incomplete")
        if not isinstance(private_raw, Mapping) or not required_private.issubset(private_raw):
            raise ValueError("verified private raw frame is incomplete")

        context = self._contexts[index]
        patch_tokens = self._extract_tokens(
            np.asarray(public_raw["rgb"], dtype=np.uint8).copy(), index,
        )
        materialized = materialize_vm04_public_frontend_frame(
            sample_id_hash=context["sample_id_hash"],
            decision_time_s=context["decision_time_s"],
            rgbd_refs={
                "rgb_sha256": public_raw["rgb_sha256"],
                "depth_sha256": public_raw["depth_sha256"],
            },
            camera=public_raw["camera"],
            robot_state=context["robot_state"],
            past_actions=context["past_actions"],
            depth_m=public_raw["depth_m"],
            patch_tokens=patch_tokens,
            private_instance_ids=private_raw["private_instance_ids"],
            private_instance_masks=private_raw["instance_masks"],
            prior_free_space=self._prior_free_space,
            public_constants=context["public_constants"],
            observation_index=index,
            config=self._frontend_config,
        )
        packet = make_public_packet(materialized["frontend_row"], self._memory)
        advanced = advance_public_bootstrap(
            packet, self._memory, config=self._bootstrap_config,
        )
        self._memory = clone_json(advanced["post_memory"])
        self._prior_free_space.append(materialized["current_free_space"])
        self._packets.append(packet)
        self._next_index += 1

        if self._next_index == len(self._contexts):
            replay = build_causal_prior(
                self._packets,
                config=self._bootstrap_config,
                builder_code_sha256=self._builder_code_sha256,
            )
            if replay["prior_memory"] != self._memory:
                raise ValueError(
                    "online public memory differs from independent replay"
                )
            self._final = {
                "prior_memory": clone_json(self._memory),
                "causal_prior_receipt": clone_json(replay["receipt"]),
                "public_frame_context_manifest": clone_json(
                    self._context_manifest
                ),
                "ordered_public_packet_sha256s": [
                    canonical_sha256(packet) for packet in self._packets
                ],
            }
        return {
            "public_packet": packet,
            "private_crosswalk": materialized["private_crosswalk"],
        }

    def finalized_result(self) -> dict[str, Any]:
        """Return the replay-verified sequence result after the last frame."""

        if self._final is None:
            raise ValueError("public front-end sequence is incomplete")
        return clone_json(self._final)
