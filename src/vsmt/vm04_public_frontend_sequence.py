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
from .vm04_public_frontend import (
    Vm04PublicFrontendConfig,
    materialize_vm04_public_frontend_frame,
)
from .vm04_public_packet_builder import make_public_packet


PUBLIC_FRAME_CONTEXT_KEYS = {
    "sample_id_hash",
    "decision_time_s",
    "robot_state",
    "past_actions",
    "public_constants",
}


class Vm04PublicFrontendSequence:
    """Consume contiguous raw frames and preserve the public memory chain."""

    def __init__(
        self, *, public_frame_contexts: Sequence[Mapping[str, Any]],
        private_frame_roles: Sequence[str],
        patch_token_extractor: Callable[[np.ndarray, int], Any],
        frontend_config: Vm04PublicFrontendConfig,
        bootstrap_config: PublicBootstrapConfig,
        builder_code_sha256: str,
    ) -> None:
        if isinstance(public_frame_contexts, (str, bytes)):
            raise ValueError("public_frame_contexts must be an ordered sequence")
        contexts = []
        for raw in public_frame_contexts:
            if not isinstance(raw, Mapping) or set(raw) != PUBLIC_FRAME_CONTEXT_KEYS:
                raise ValueError(
                    "each public frame context must contain exactly "
                    f"{sorted(PUBLIC_FRAME_CONTEXT_KEYS)}"
                )
            contexts.append(clone_json(dict(raw)))
        roles = list(private_frame_roles)
        if not contexts or len(roles) != len(contexts):
            raise ValueError("private frame roles must match nonempty public contexts")
        if any(type(role) is not str or not role for role in roles):
            raise ValueError("private frame roles must be nonempty strings")
        if not callable(patch_token_extractor):
            raise ValueError("patch_token_extractor must be callable")
        if type(frontend_config) is not Vm04PublicFrontendConfig:
            raise ValueError("frontend_config has the wrong type")
        if type(bootstrap_config) is not PublicBootstrapConfig:
            raise ValueError("bootstrap_config has the wrong type")

        self._contexts = contexts
        self._private_roles = roles
        self._extract_tokens = patch_token_extractor
        self._frontend_config = frontend_config
        self._bootstrap_config = bootstrap_config
        self._builder_code_sha256 = builder_code_sha256
        self._memory = empty_public_memory()
        self._prior_free_space: list[Sequence[Any]] = []
        self._packets: list[dict[str, Any]] = []
        self._next_index = 0
        self._final: dict[str, Any] | None = None

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
            frame_role=self._private_roles[index],
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
