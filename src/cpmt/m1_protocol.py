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
EXPECTED_SCENARIO_FAMILIES = [f"C{index:02d}" for index in range(12)]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_m1_protocol(config: Mapping[str, Any]) -> None:
    """Reject incomplete, leaky, or silently weakened M1 protocol settings."""
    _require(config.get("protocol") == "m1-hard-condition-v5", "wrong protocol")
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
    _require(data["scenario_families"] == EXPECTED_SCENARIO_FAMILIES,
             "C00-C11 are required in canonical order")
    _require(
        data.get("continuous_rollout_required_families")
        == data["scenario_families"],
        "continuous rollout must implement every configured family",
    )
    _require(
        data.get("generation_count_semantics")
        == "total_mixed_paired_groups_each_group_contains_all_families",
        "generation counts must be total mixed paired groups",
    )
    _require(
        data.get("paired_groups")
        == {"train": 1000, "validation": 200, "test": 200},
        "mixed paired-group split sizes changed",
    )
    _require(
        data.get("legacy_fixture_groups_per_family")
        == {"train": 1000, "validation": 200, "test": 200},
        "legacy fixture-only scale changed",
    )
    _require(
        data.get("family_coverage_domain")
        == "all_configured_families_missing_family_fails",
        "coverage must fail when a configured family is absent",
    )
    _require(
        data.get("family_mechanism_contract")
        == {
            "C10": "balanced_transient_dynamic_actor_NOOP_vs_persistent_background_BIND_with_same_current_observation_distribution",
            "C11": "necessary_BIND_vs_admitted_legal_BIND_with_unrelated_open_memory_mutation",
            "behavioral_fingerprint_gate": True,
        },
        "C10/C11 behavioral family mechanisms changed",
    )
    _require(data["minimum_test_support_per_family"] == 200,
             "per-family test support must remain 200 independent mixed groups")
    _require(
        int(data["paired_groups"]["test"])
        >= int(data["minimum_test_support_per_family"]),
        "mixed test groups cannot meet per-family independent-group support",
    )

    future = config["future"]
    # A hashed target has no metric structure, so a learned outcome scorer
    # regressing towards it is a weakened baseline rather than a fair one.
    _require(future["target_representation"] in future["target_representation_options"],
             "future target representation must be one of the declared options")
    _require(future["source"] == "actual_executed_trajectory",
             "future poses must come from the executed trajectory")
    _require(future["primary_horizon"] > 0, "future horizon must be positive")
    _require(int(future.get("start_offset_decisions", 0)) == 1,
             "future must start after the current decision to avoid duplicating now")
    _require(
        future.get("no_execution_target")
        == "candidate_scoped_future_relations_v1",
        "C/E must use the registered structured future-relation target",
    )
    _require(
        future.get("no_execution_now_target")
        == "candidate_scoped_current_relations_v1",
        "C/E must receive the registered symmetric current-relation target",
    )
    no_execution_now_inputs = str(future.get("no_execution_now_target_inputs", ""))
    for forbidden_now_source in (
        "candidate_post_world", "executor_outcome", "legality", "future",
    ):
        _require(
            f"never_{forbidden_now_source}" in no_execution_now_inputs,
            "C/E current target may not use post-world, executor, legality, or future",
        )
    _require(
        future.get("no_execution_now_target_policy")
        == {
            "argument_cosine_minimum": 0.8,
            "novel_entity_best_maximum": 0.6,
            "split_best_minimum": 0.55,
            "split_best_maximum": 0.8,
            "dormant_match_minimum": 0.8,
            "merge_best_minimum": 0.8,
            "merge_second_minimum": 0.8,
        },
        "candidate-scoped current-relation policy changed",
    )
    _require(
        future.get("no_execution_candidate_execution")
        == "forbidden_for_candidate_scoring_and_target_construction;_selected_transaction_uses_shared_executor",
        "E may not execute non-reference candidates while scoring",
    )
    forbidden = set(future["online_export_excludes"])
    _require({"future_evidence", "oracle_equivalence", "simulator_hidden_state"}
             <= forbidden, "online export leakage denylist is incomplete")

    candidates = config["candidates"]
    _require(candidates["budget_k"] == 16, "A/D/F candidate K must stay fixed at 16")
    _require(set(candidates["templates"]) == REQUIRED_TEMPLATES,
             "required executable template coverage changed")
    _require(candidates["coverage_gate_overall"] >= candidates["coverage_gate_each_family"],
             "overall coverage gate cannot be below the family gate")
    admissibility = candidates.get("online_admissibility_mask", {})
    _require(
        admissibility.get("name") == "transaction_static_preflight_v1",
        "M1-v2 requires the registered transaction static-preflight mask",
    )
    _require(
        admissibility.get("shared_methods") == ["A", "B", "C", "D", "E"],
        "the online admissibility mask must be identical for A-E",
    )
    _require(
        admissibility.get("pass_semantics")
        == "preflight_pass_means_execution_outcome_unknown_not_legal",
        "static preflight pass cannot claim executor legality",
    )
    for key in (
        "reference_must_pass", "reject_all_candidates_forbidden",
        "executor_illegal_energy_retained",
        "remaining_executor_illegal_candidates_always_reported",
    ):
        _require(admissibility.get(key) is True,
                 f"online admissibility contract weakened: {key}")
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

    recovery = config["recovery"]
    _require(
        recovery["mode"] == "bounded_online_compensating_transaction_v1",
        "M1-v2 requires the bounded online recovery path",
    )
    _require(recovery["trigger"] == "deterministic_relevant_visible_contradiction",
             "recovery trigger must remain deterministic and evidence based")
    _require(int(recovery["lookback_decisions"]) == 3,
             "M1-v2 recovery lookback must stay fixed at three decisions")
    _require(recovery["candidate_generator"] == "same_fixed_deterministic_k16",
             "recovery must not introduce a learned or expanded proposer")
    _require(recovery["global_async_reconciliation"] == "M2_only",
             "global reconciliation cannot enter M1")

    energy = config["energy"]
    _require(set(energy["terms"]) == ENERGY_TERMS, "all six energy terms are required")
    _require(set(energy["weights"]) == ENERGY_TERMS - {"illegal"},
             "legal energy weights are incomplete")
    _require(
        energy.get("now_semantics")
        == "post_edit_projection_mismatch_against_valid_current_online_observation",
        "now must measure post-edit current projection consistency",
    )
    _require(
        energy.get("now_target_source")
        == "current_online_sensor_only_never_reference_post_world",
        "now may not use the reference post-world as its target",
    )
    _require(
        energy.get("now_normalization")
        == "fixed_natural_range_without_candidate_spread_scaling;_visible_appearance_divide_2;_visible_appearance_plus_place_divide_4;_visible_empty_divide_1;_candidate_relation_probability_absolute_error_bounded_0_1;_executed_teacher_excludes_executor_illegal;_store_raw_scale_and_scaled",
        "now must use the registered fixed natural-range normalization",
    )
    _require(
        energy.get("future_normalization")
        == "per_method_per_decision_zscore_over_available_admitted_candidates;_executed_teacher_excludes_executor_illegal;_store_raw_and_scaled",
        "future must retain the registered per-decision normalization",
    )
    _require(
        energy.get("no_execution_current_inference_energy")
        == "mean_absolute_error_between_sigmoid_relation_probability_and_desired_bit_bounded_0_1;_BCE_remains_training_loss",
        "no-execution current energy must be bounded probability error while BCE remains the training loss",
    )
    posterior_audit = energy.get("posterior_influence_audit", {})
    _require(
        posterior_audit.get("terms")
        == ["now", "future", "edit", "growth", "collateral"],
        "posterior influence audit must cover every finite teacher energy term",
    )
    _require(
        posterior_audit.get("total_variation_thresholds")
        == [0.001, 0.01, 0.05, 0.1]
        and posterior_audit.get("metrics")
        == [
            "mean_median_p95_max_total_variation",
            "fraction_above_each_threshold",
            "argmax_change_rate",
            "mean_KL_full_to_ablated",
            "full_minus_ablated_reference_probability",
        ]
        and posterior_audit.get("primary_interpretation")
        == "posterior_distribution_not_argmax_only",
        "posterior influence audit thresholds or interpretation changed",
    )
    expected_now_pattern = posterior_audit.get(
        "expected_now_activation_pattern", {}
    )
    _require(
        expected_now_pattern.get("metric")
        == "leave_now_out_posterior_mean_total_variation"
        and expected_now_pattern.get("expected_nonzero_mean_tv_families")
        == ["C01", "C02", "C04", "C06", "C07", "C08"]
        and expected_now_pattern.get("expected_zero_mean_tv_families")
        == ["C00", "C03", "C05", "C09", "C10", "C11"]
        and float(expected_now_pattern.get(
            "numerical_zero_tolerance", -1.0
        )) == 1e-6
        and expected_now_pattern.get("deviation_action")
        == "report_family_names_without_gate_or_weight_tuning",
        "expected executed-now family activation pattern changed",
    )
    _require(
        posterior_audit.get("no_execution_comparison")
        == "S1_reports_the_same_leave_current_out_posterior_metrics_for_E_on_the_same_rows;_C_shares_the_current_target_as_an_auxiliary_but_has_no_separately_assembled_current_energy_posterior;_report_only_without_gate_or_weight_tuning",
        "S1 no-execution current influence comparison changed",
    )
    _require(
        energy.get("collateral_semantics")
        == "binary_any_legal_preexisting_open_memory_mutation_outside_candidate_independent_current_online_evidence_scope",
        "collateral must measure legal unrelated open-memory churn",
    )
    _require(
        energy.get("protected_touch_semantics") == "executor_illegal_not_collateral",
        "protected touches must remain executor-illegal",
    )
    _require(float(energy["weights"]["collateral"]) == 1.0,
             "live normalized collateral weight must stay at the registered value")
    health = energy.get("teacher_health_gate", {})
    _require(float(health.get("reference_agreement_overall_minimum", 0.0)) == 0.95,
             "teacher health gate overall threshold changed")
    _require(float(health.get("reference_agreement_each_family_minimum", 0.0)) == 0.90,
             "teacher health gate family threshold changed")
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
    _require(
        training.get("validation_only_selection")
        == ["direct_future_auxiliary_weight", "shared_commit_rule"],
        "validation may only select the registered C weight and shared commit rule",
    )
    budget = training.get("pretest_budget_selection", {})
    _require(
        budget.get("stage") == "v8_s1_s2_train_inner_dev_only"
        and int(budget.get("train_paired_groups", 0)) == 1000
        and budget.get("inner_dev_partition")
        == "sha256_rollout_pair_train_group_mod_5_equals_0_complete_groups",
        "v8 budget selection must use the registered train/inner-dev groups",
    )
    _require(
        budget.get("architectures")
        == ["cross_candidate_set_transformer_v1", "shared_candidate_mlp_v1"]
        and budget.get("architecture_budgets_selected_independently") is True
        and budget.get("architecture_result_selection_forbidden") is True,
        "budget selection must retain both independent architecture arms",
    )
    _require(
        budget.get("seeds") == training["formal_seeds"]
        and float(budget.get("learning_rate", 0.0)) == 0.002
        and int(budget.get("batch_size", 0)) == 64,
        "budget selection seeds or optimizer settings changed",
    )
    _require(
        budget.get("scorer_update_checkpoints") == [300, 1000, 3000]
        and budget.get("student_update_checkpoints") == [300, 1000, 3000]
        and budget.get("checkpoint_execution")
        == "one_identical_seeded_training_trajectory_to_maximum_and_evaluate_registered_prefix_checkpoints",
        "finite scorer/student checkpoint grids changed",
    )
    _require(
        budget.get("scorer_selection_metric")
        == "inner_dev_online_reference_candidate_ranking_accuracy"
        and budget.get("scorer_selection_aggregation")
        == "equal_weight_mean_over_seed_and_complete_paired_group",
        "scorer budget selection metric changed",
    )
    _require(
        budget.get("student_selection_methods")
        == [
            "cpmt_ctl_core", "direct_classifier", "direct_future_loss",
            "execute_current_only", "future_no_execution",
        ]
        and budget.get("student_selection_metric")
        == "inner_dev_online_student_argmax_matches_method_specific_teacher_argmax"
        and budget.get("student_selection_aggregation")
        == "equal_method_weight_then_equal_seed_and_complete_paired_group_weight",
        "shared student budget selection metric changed",
    )
    _require(
        float(budget.get("direct_future_auxiliary_weight_anchor", -1.0)) == 1.0
        and budget.get("selection_rule")
        == "highest_registered_aggregate_mean_with_exact_ties_to_fewer_updates"
        and budget.get("selected_scorer_fixed_before_student_grid") is True
        and budget.get("student_updates_shared_A_to_E_within_architecture") is True,
        "budget ordering, tie break, or A-E fairness changed",
    )
    _require(
        budget.get("validation_arrays_read") is False
        and budget.get("validation_trial_consumed") is False
        and budget.get("test_access") is False,
        "budget selection may not access validation or test",
    )
    architecture = config.get("architecture_evaluation", {})
    _require(
        architecture.get("primary") == "cross_candidate_set_transformer_v1",
        "the cross-candidate Set Transformer must remain the primary architecture",
    )
    _require(
        architecture.get("secondary") == "shared_candidate_mlp_v1",
        "the shared-candidate MLP must remain the secondary architecture control",
    )
    _require(
        architecture.get("registered")
        == ["cross_candidate_set_transformer_v1", "shared_candidate_mlp_v1"],
        "both registered architecture arms are required",
    )
    _require("selection" in str(architecture.get("between_architecture_selection", "")),
             "architecture results may not be used for post-hoc model selection")
    _require(
        architecture.get("run_scope")
        == "same_v8_arrays_and_full_A_to_F_within_each_architecture",
        "each architecture arm must run the full A-F method table on the same v8 arrays",
    )
    set_spec = architecture.get("cross_candidate_set_transformer_v1", {})
    _require(
        {
            "model_dim": set_spec.get("model_dim"),
            "attention_heads": set_spec.get("attention_heads"),
            "set_attention_blocks": set_spec.get("set_attention_blocks"),
            "feedforward_dim": set_spec.get("feedforward_dim"),
            "dropout": set_spec.get("dropout"),
            "candidate_output": set_spec.get("candidate_output"),
        }
        == {
            "model_dim": 128,
            "attention_heads": 4,
            "set_attention_blocks": 2,
            "feedforward_dim": 256,
            "dropout": 0.0,
            "candidate_output": "shared_equivariant_score_head",
        },
        "cross-candidate Set Transformer specification changed",
    )
    mlp_spec = architecture.get("shared_candidate_mlp_v1", {})
    _require(
        int(mlp_spec.get("hidden_dim", 0)) == 64
        and mlp_spec.get("cross_candidate_interaction") is False
        and mlp_spec.get("candidate_output")
        == "shared_equivariant_score_head",
        "shared-candidate MLP specification changed",
    )
    calibration = training["commit_calibration"]
    _require(calibration["shared_across_methods"] is True,
             "A-E must share one calibrated commit rule")
    _require(calibration["calibration_fraction"] == 0.5,
             "validation calibration/report split must remain half-and-half")
    _require(calibration["report_partition_selects_nothing"] is True,
             "validation report partition cannot tune the commit rule")
    _require(
        calibration["partition"]
        == "sha256_paired_group_id_even_calibration_odd_report",
        "commit calibration partition rule changed",
    )
    for key in ("commit_probability_grid", "margin_threshold_grid"):
        values = calibration[key]
        _require(values and len(values) == len(set(values)),
                 f"{key} must be nonempty and unique")
    _require(
        any(float(value) <= 1.0 / float(config["candidates"]["budget_k"])
            for value in calibration["commit_probability_grid"]),
        "commit grid must contain a threshold reachable by an uncalibrated "
        "K-way softmax",
    )

    evaluation = config["evaluation"]
    _require(evaluation["primary_contrasts"] == ["A_vs_C", "A_vs_E"],
             "primary contrasts must be A-C and A-E")
    _require(set(evaluation["primary_metrics"]) == {
        "active_graph_correctness", "memory_contamination",
        "false_birth_growth", "collateral_violation",
    }, "primary metrics changed")
    _require(int(evaluation["recovery_window_decisions"])
             == int(recovery["lookback_decisions"]),
             "recovery metric window must match the registered lookback")
    _require(evaluation["bootstrap"]["unit"] == "paired_group_id",
             "bootstrap must preserve paired groups")
    _require(
        evaluation["bootstrap"]["stratify_by"]
        == "single_mixed_registered_20_step_endpoint_stratum",
        "20-step sequence endpoints form one mixed registered bootstrap stratum",
    )
    _require(evaluation["bootstrap"]["confidence"] == 0.95,
             "confidence level must be 95%")
    _require(evaluation["invariant_violation_gate"] == 0,
             "invariant violations must have zero tolerance")
    _require(
        "active_graph_correctness_absolute"
        in evaluation["meaningful_effect"],
        "meaningful effect must follow the active-world primary metric",
    )
    slices = evaluation.get("mechanism_diagnostic_slices", {})
    expected_slice_order = [
        "exact_online_ambiguity",
        "temporal_underdetermination",
        "execution_side_effect_sensitive",
        "current_sensor_unavailable",
        "other_registered_mechanisms",
    ]
    _require(
        slices.get("selection_rule")
        == "pre_registered_generator_mechanism_only_never_empirical_accuracy_threshold",
        "mechanism slices may not be selected from measured accuracy",
    )
    _require(
        slices.get("precedence") == expected_slice_order,
        "mechanism slice precedence changed",
    )
    _require(
        slices.get("exact_online_ambiguity", {}).get("definition")
        == "ambiguity_equals_epistemically_ambiguous_pivot"
        and slices.get("temporal_underdetermination", {}).get("definition")
        == "scenario_family_equals_C10"
        and slices.get("execution_side_effect_sensitive", {}).get("definition")
        == "scenario_family_equals_C11"
        and slices.get("current_sensor_unavailable", {}).get("definition")
        == "scenario_family_equals_C09"
        and slices.get("other_registered_mechanisms", {}).get("definition")
        == "all_remaining_online_rows",
        "mechanism slice definitions changed",
    )
    _require(
        slices.get("primary_gate") is False
        and slices.get("full_mixed_20_step_causal_endpoint_remains_primary") is True,
        "diagnostic mechanism slices may not replace the mixed causal gate",
    )
    _require(
        slices.get("reported_metrics")
        == [
            "selection_accuracy", "commit_rate",
            "committed_registered_accuracy",
            "active_correctness_after_decision",
            "selected_collateral_rate",
        ],
        "mechanism slice metrics changed",
    )
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
    _require("formal_run_wall_time_limit_hours" not in resources,
             "the superseded fixed formal-run wall-time cap must not return")
    _require(
        resources.get("formal_run_wall_time_policy")
        == "measure_and_report_without_repository_fixed_cap",
        "formal run time must be measured without a repository fixed cap",
    )


def load_and_validate(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_m1_protocol(config)
    return config


def protocol_sha256(config: Mapping[str, Any]) -> str:
    payload = json.dumps(
        config, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
