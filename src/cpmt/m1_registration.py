"""Bind the completed train-only probe to a sealed, post-probe evaluation plan.

The v6 generation protocol and v4 probe remain immutable source contracts.
This module does not generate data, train models, or authorize test access.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from cpmt.m1_protocol import (
    protocol_sha256, validate_m1_endpoint_probe, validate_m1_protocol,
)


def validate_registration(
    registration: Mapping[str, Any], source: Mapping[str, Any],
    overlay: Mapping[str, Any], probe: Mapping[str, Any],
) -> None:
    """Fail before training if evidence, endpoint, gates or test plan drift."""
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    validate_m1_protocol(source)
    validate_m1_endpoint_probe(overlay, source)
    require(registration.get("schema_version") == "cpmt-m1-post-probe-registration-v1",
            "wrong registration schema")
    require(registration.get("test_access") is False, "test remains sealed")
    require(registration.get("status") == "registered_pretest_not_test_release",
            "registration is not a test release")
    require(registration.get("execution_boundary") == {
        "candidate_generation_executes_all": True,
        "evaluation_materializes_all": True,
        "online_selection_mask": "shared_static_preflight",
        "online_reads_future_or_candidate_post_world": False,
        "only_selected_legal_world_persists": True,
        "single_execution_deployment_implemented": False,
        "p95_forward_latency_scope": "network_and_associated_tensor_probability_operations",
    }, "execution boundary must supersede the historical overlay wording")
    for key, value in (("source_protocol_sha256", source),
                       ("probe_overlay_sha256", overlay),
                       ("endpoint_probe_sha256", probe)):
        require(registration.get(key) == protocol_sha256(value), f"{key} mismatch")
    require(probe.get("status") == "complete"
            and probe.get("validation_arrays_read") is False
            and probe.get("test_access") is False, "probe access/status mismatch")
    assessment = probe["endpoint_assessment"]
    require(assessment["oracle_integrity_pass"] is True
            and assessment["winner_or_effect_sign_used_for_switch"] is False,
            "probe integrity/switch policy failed")
    require(assessment["disposition"] == "retain_exact_endpoint",
            "this registration binds the completed exact-endpoint probe")
    metrics = [assessment["selected_metric"], assessment["required_support_metric"],
               assessment["required_burden_metric"]]
    require(metrics == ["final_active_graph_correctness",
                        "final_graded_open_memory_correctness",
                        "open_fact_error_auc_per_100_decisions"], "endpoint drift")
    required_counts = []
    power = overlay["power_planning"]
    for index, metric in enumerate(metrics):
        null, planned = (40.0, 80.0) if index == 2 else (0.03, 0.06)
        for contrast in ("A_vs_C", "A_vs_E"):
            cell = assessment["by_metric"][metric][contrast]
            require(cell["nondegenerate"] is True, "degenerate co-primary")
            require(cell["null_minimum_effect"] == null
                    and cell["planning_effect"] == planned, "effect gate drift")
            sd = float(cell["paired_group_standard_deviation"])
            require(math.isfinite(sd) and sd >= 0, "invalid paired-group SD")
            raw = ((float(power["z_one_sided_alpha"]) + float(power["z_power"]))
                   * sd / (planned - null)) ** 2
            count = max(200, int(math.ceil(raw / 10.0)) * 10)
            require(count == cell["required_test_groups_for_planning_effect"],
                    "power arithmetic mismatch")
            required_counts.append(count)
    count = max(required_counts)
    require(count == assessment["selected_test_groups"] == 1350,
            "registered test count mismatch")
    expected_plan = {
        "paired_groups": {"train": 1000, "validation": 200, "test": count},
        "semantic_metric": metrics[0], "support_metric": metrics[1],
        "burden_metric": metrics[2],
        "minimum_effects": [0.03, 0.03, 40.0],
        "planning_effects": [0.06, 0.06, 80.0],
        "primary_contrasts": ["A_vs_C", "A_vs_E"],
        "commit_probability": 0.0, "margin_threshold": 0.0,
        "validation_selects_settings": False,
    }
    require(registration.get("evaluation_plan") == expected_plan,
            "evaluation plan differs from frozen rules and completed probe")


def load_registration(
    root: Path, source: Mapping[str, Any], overlay: Mapping[str, Any],
) -> dict[str, Any]:
    registration = json.loads(
        (root / "configs/m1_post_probe_registration.json").read_text(encoding="utf-8")
    )
    exported = json.loads(
        (root / registration["evidence_report"]).read_text(encoding="utf-8")
    )
    validate_registration(registration, source, overlay, exported["endpoint_probe"])
    return registration
