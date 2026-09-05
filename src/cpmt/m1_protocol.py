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
    _require(config["resources"]["cloud_spend_authorized_aud"] == 0,
             "cloud spend requires a separate user authorization")


def load_and_validate(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_m1_protocol(config)
    return config


def protocol_sha256(config: Mapping[str, Any]) -> str:
    payload = json.dumps(
        config, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
