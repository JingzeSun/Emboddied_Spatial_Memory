"""Validation for the pre-test M1 hard-condition protocol lock candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


EXPECTED_METHODS = {
    "A": ("cpmt_ctl_core", True, True, True),
    "B": ("direct_classifier", False, False, False),
    "C": ("direct_future_loss", False, True, False),
    "D": ("execute_current_only", True, False, True),
    "E": ("future_no_execution", False, True, False),
    "F": ("oracle_candidate_program", True, True, True),
}
ENERGY_TERMS = {"now", "future", "edit", "growth", "collateral", "illegal"}
GROUP_KEYS = {"paired_group_id", "world_seed", "asset_family"}
REQUIRED_TEMPLATES = {
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT", "SPLIT", "MERGE"
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_m1_protocol(config: Mapping[str, Any]) -> None:
    """Reject incomplete, leaky, or silently weakened M1 protocol settings."""
    _require(config.get("protocol") == "m1-hard-condition-v1", "wrong protocol")
    _require(config.get("stage") == "M1", "stage must be M1")
    _require(config.get("status") in {"pretest_lock_candidate", "frozen_pretest"},
             "protocol must be a pre-test candidate or frozen pre-test contract")
    _require(config.get("test_access") is False, "test access must remain false")

    methods = config.get("methods", [])
    _require(len(methods) == 6, "exactly six A-F methods are required")
    observed = {
        item["id"]: (
            item["name"], item["execute_candidates"],
            item["future_supervision"], item["post_edit_world"],
        )
        for item in methods
    }
    _require(observed == EXPECTED_METHODS, "A-F method semantics changed")

    data = config["data"]
    _require(set(data["group_keys"]) == GROUP_KEYS, "paired split keys are incomplete")
    _require(data["retain_method_failures"] is True, "method failures must be retained")
    _require("sealed" in data["test_release"], "test must remain sealed")
    _require(len(data["scenario_families"]) == 12, "C00-C11 are required")
    _require(data["minimum_test_support_per_family"] >= 100,
             "per-family test support is too small")

    future = config["future"]
    _require(future["source"] == "actual_executed_trajectory",
             "future poses must come from the executed trajectory")
    _require(future["primary_horizon"] > 0, "future horizon must be positive")
    forbidden = set(future["online_export_excludes"])
    _require({"future_evidence", "oracle_equivalence", "simulator_hidden_state"}
             <= forbidden, "online export leakage denylist is incomplete")

    candidates = config["candidates"]
    _require(candidates["budget_k"] == 16, "A/D/F candidate K must stay fixed at 16")
    _require(set(candidates["templates"]) == REQUIRED_TEMPLATES,
             "required executable template coverage changed")
    _require(candidates["coverage_gate_overall"] >= candidates["coverage_gate_each_family"],
             "overall coverage gate cannot be below the family gate")
    retrieval = candidates["proposal_retrieval"]
    # An exact hash of the hidden argument is an oracle pointer: it forces the
    # reference into a fixed generator slot and makes coverage meaningless.
    _require(
        float(retrieval["noise_sigma"]) > 0.0
        or float(retrieval["distractor_weight"]) > 0.0,
        "proposal retrieval must not be an exact hash of the hidden argument",
    )

    observation = config["observation"]
    # The online observation must be generated from the world, otherwise the
    # only template signal left is a scenario label naming the answer.
    _require(observation["source"] == "world_generated_appearance_v1",
             "online observation must be generated from the executed world")
    _require(observation["occlusion_is_neutral"] is True,
             "occlusion must stay neutral evidence, never a negative observation")
    _require(0.0 <= float(observation["appearance_noise"]) <= 1.0,
             "appearance noise must be within [0, 1]")

    energy = config["energy"]
    _require(set(energy["terms"]) == ENERGY_TERMS, "all six energy terms are required")
    _require(set(energy["weights"]) == ENERGY_TERMS - {"illegal"},
             "legal energy weights are incomplete")
    _require(energy["illegal"] == "positive_infinity_mask",
             "illegal candidates must be masked")
    _require(energy["temperature"] > 0, "temperature must be positive")

    training = config["training"]
    _require(training["formal_seeds"] == [7, 19, 31, 43, 59],
             "five registered formal seeds changed")
    _require(training["same_online_encoder_A_to_E"] is True,
             "A-E must share the online encoder")
    _require(training["same_student_updates_A_to_E"] is True,
             "A-E student update budgets must match")
    _require(training["test_selects_nothing"] is True,
             "test cannot select any setting")

    evaluation = config["evaluation"]
    _require(evaluation["primary_contrasts"] == ["A_vs_C", "A_vs_E"],
             "primary contrasts must be A-C and A-E")
    _require(set(evaluation["primary_metrics"]) == {
        "post_graph_correctness", "memory_contamination",
        "false_birth_growth", "collateral_violation",
    }, "primary metrics changed")
    _require(evaluation["bootstrap"]["unit"] == "paired_group_id",
             "bootstrap must preserve paired groups")
    _require(evaluation["bootstrap"]["confidence"] == 0.95,
             "confidence level must be 95%")
    _require(evaluation["invariant_violation_gate"] == 0,
             "invariant violations must have zero tolerance")
    resources = config["resources"]
    # Cloud cost is controlled by the operator, who starts pay-as-you-go
    # instances by hand and schedules their shutdown, so the protocol records
    # the authorization rather than gating on it. A declared budget must still
    # be a non-negative number; null means "operator controlled, no cap set".
    budget = resources["cloud_spend_authorized_aud"]
    _require(budget is None or (isinstance(budget, (int, float))
                                and not isinstance(budget, bool) and budget >= 0),
             "cloud spend authorization must be null or a non-negative amount")
    _require(isinstance(resources.get("cloud_spend_control"), str)
             and resources["cloud_spend_control"].strip() != "",
             "resources must record how cloud spend is controlled")


def load_and_validate(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_m1_protocol(config)
    return config


def protocol_sha256(config: Mapping[str, Any]) -> str:
    payload = json.dumps(
        config, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
