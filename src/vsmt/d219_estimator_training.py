"""D-219 structural-only estimator training.

D-219 removes the semantic room/corridor head from the shared front-end: it
never defined place identity, P08 qualification never read it, and no adapter,
candidate generator, teacher or evaluator consumed it.  This module fits the
single remaining ``basin/bottleneck/unknown`` affine head.

The frozen numerics (inverse-sqrt class weights, golden-section temperature
search, probability metrics, house split manifest) are **imported** from the
reviewed D-216 module rather than copied, so a single-head run cannot silently
drift from the specification the user already approved.  Only the loss, the
early-stopping metric, the checkpoint rule and the temperature count change,
exactly as registered in the D-219 contract.

Private reachable-graph labels are written at train, calibration and audit time
only.  Nothing here reads a grid at inference: the head consumes the same
396-dimensional public feature vector that E-05 already materialized.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from .d215_frontend_freeze import (
    GEOMETRY_FEATURE_ORDER,
    STRUCTURAL_LABELS,
    validate_d215_contract,
)
from .d216_estimator_training import (
    HEX64,
    SPLITS,
    _array_content_digest,
    _class_weights,
    _probability_metrics,
    _sealed,
    _string_vector,
    _temperature,
    validate_house_split_manifest,
)


CONTRACT_SCHEMA = "vsmt-vm04-d219-structural-only-estimator-v1"
BUNDLE_SCHEMA = "vsmt-vm04-d219-structural-training-bundle-v1"
NORMALIZATION_SCHEMA = "vsmt-vm04-d219-normalization-v1"
WEIGHTS_SCHEMA = "vsmt-vm04-d219-structural-head-weights-v1"
TRAINING_RECEIPT_SCHEMA = "vsmt-vm04-d219-training-receipt-v1"
SUCCESS_SCHEMA = "vsmt-vm04-d219-training-success-v1"

CLOSED_STATUS = "implementation_pending_review_all_execution_closed"
ACTIVE_STATUS = "frozen_executable_structural_training"
AUTHORIZATION_KEYS = {
    "structural_training", "audit_open_or_generation", "full_house_expansion",
    "production_reader", "p04_p08_qualification", "route_or_raw_generation",
    "private_evaluation",
}
FROZEN_PREDECESSORS = ("d215", "d216", "d217", "d218")
NPZ_ARRAY_NAMES = (
    "features", "structural_labels", "house_ids", "observation_ids",
    "public_observation_sha256", "structural_label_receipt_sha256",
)
FORBIDDEN_ARRAY_NAMES = (
    "semantic_labels", "semantic_annotation_receipt_sha256",
)


class D219Error(ValueError):
    """A stable D-219 contract, bundle, or training failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D219Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _exact_keys(value: Any, expected: set[str], name: str) -> None:
    _require(type(value) is dict and set(value) == expected,
             f"{name} has unexpected fields")


def validate_d219_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the D-219 contract and its supersession boundary."""

    value = clone_json(dict(contract))
    _require(value.get("schema_version") == CONTRACT_SCHEMA and
             value.get("decision_id") == "D-219",
             "D-219 contract identity changed")
    status = value.get("status")
    _require(status in {CLOSED_STATUS, ACTIVE_STATUS},
             "D-219 contract status is not a registered state")
    _exact_keys(value["authorization"], AUTHORIZATION_KEYS,
                "D-219 authorization")
    authorization = value["authorization"]
    _require(all(item is False or item is True
                 for item in authorization.values()),
             "D-219 authorization values must be booleans")
    if status == CLOSED_STATUS:
        _require(not any(authorization.values()),
                 "the closed D-219 contract must keep every run gate false")
    policy = value["run_authorization_policy"]
    _require(policy["governed_by"] == "D-220" and
             policy["active_status"] == ACTIVE_STATUS and
             policy["separate_single_file_activation_commit_required"] is False
             and policy["clean_checkout_required_for_real_runs"] is True,
             "D-219 run authorization policy changed")
    for name in policy["must_remain_false"]:
        _require(authorization[name] is False,
                 f"D-219 must keep {name} false")

    removed = value["removed_semantic_head"]
    _require(removed["removed_entirely"] is True and
             removed["constant_unknown_placeholder_allowed"] is False and
             removed["human_annotation_stopped"] is True and
             removed["e04_artifacts"]["enters_training"] is False,
             "D-219 semantic removal boundary changed")

    estimator = value["structural_estimator"]
    architecture = estimator["architecture"]
    _require(architecture["semantic_head"] is None and
             architecture["hidden_layers"] == 0 and
             architecture["concatenated_feature_dimension"] == 396 and
             architecture["structural_labels"] == list(STRUCTURAL_LABELS),
             "D-219 structural architecture changed")
    training = estimator["training"]
    _require(training["loss"] == "structural_cross_entropy_only" and
             training["early_stopping_metric"] ==
             "calibration_split_structural_nll" and
             training["p08_route_yield_may_select_checkpoint_or_temperature"]
             is False and
             training["results_may_not_change_any_number_above"] is True,
             "D-219 training boundary changed")

    boundary = value["label_boundary"]
    _require(boundary["inference_inputs"] ==
             "public_rgbd_and_camera_intrinsics_only" and
             boundary["reference_labels_available_to_inference_or_cache"]
             is False and
             boundary["p08_may_read_reachable_grid_truth"] is False and
             boundary["human_semantic_annotation_required"] is False,
             "D-219 label boundary changed")
    _require("inference" in boundary["private_reachable_grid_forbidden_scope"],
             "D-219 must forbid the reachable grid at inference")

    _require(value["e07_scale_decision"]["full_house_expansion"] is False and
             value["e07_scale_decision"]["decided_now"] is True,
             "D-219 development scale decision changed")
    _require(value["e08_audit"]["human_judgements_required"] == 0 and
             value["e08_audit"]["model_inputs"] ==
             "public_rgbd_and_camera_intrinsics_only" and
             value["e08_audit"]["run_once"] is True,
             "D-219 audit boundary changed")
    _require(value["p08_qualification"]["numbers_changed_by_d219"] is False and
             value["p08_qualification"]["may_be_tuned_by_route_yield"] is False,
             "D-219 must not touch the frozen P08 numbers")
    return value


def verify_frozen_predecessors(
    contract: Mapping[str, Any], *, file_bytes: Mapping[str, bytes],
) -> dict[str, str]:
    """Confirm the executed d215->d216->d217->d218 chain is byte-identical.

    E-01..E-03 and E-05 already ran against these exact bytes.  Rewriting any
    of them would invalidate the completed server receipts, so D-219 supersedes
    by reference and this check must pass before any structural run.
    """

    value = validate_d219_contract(contract)
    bindings = value["frozen_predecessor_bindings"]
    digests: dict[str, str] = {}
    for key in FROZEN_PREDECESSORS:
        path = bindings[f"{key}_relative_path"]
        _require(path in file_bytes,
                 f"D-219 frozen predecessor {key} was not supplied")
        actual = hashlib.sha256(file_bytes[path]).hexdigest()
        _require(actual == bindings[f"{key}_file_sha256"],
                 f"D-219 frozen predecessor {key} bytes changed")
        digests[key] = actual
    return digests


def validate_structural_shard_arrays(
    arrays: Mapping[str, Any], *, split: str,
    partition_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one structural-only NPZ and return aggregate audit facts."""

    partition = validate_house_split_manifest(partition_manifest)
    _require(split in SPLITS, "structural shard split is invalid")
    present = set(arrays)
    for name in FORBIDDEN_ARRAY_NAMES:
        _require(name not in present,
                 f"D-219 rejects the removed semantic array {name}")
    _require(present == set(NPZ_ARRAY_NAMES),
             "structural shard arrays differ from the frozen exact schema")
    features = np.asarray(arrays["features"])
    _require(features.dtype == np.dtype("float32") and features.ndim == 2 and
             features.shape[1] == 396 and features.shape[0] > 0 and
             np.isfinite(features).all(),
             "structural features must be finite float32 [N,396]")
    count = int(features.shape[0])
    structural = np.asarray(arrays["structural_labels"])
    _require(structural.dtype == np.dtype("uint8") and
             structural.shape == (count,) and np.all(structural < 3),
             "structural labels must be uint8 class indices in [0,2]")
    houses = _string_vector(arrays["house_ids"], count, "house_ids")
    observations = _string_vector(
        arrays["observation_ids"], count, "observation_ids")
    _require(len(observations) == len(set(observations)),
             "observation IDs must be unique within a shard")
    split_by_house = {row["house_id"]: row["split"] for row in partition["rows"]}
    _require(all(split_by_house.get(house_id) == split for house_id in houses),
             "structural row house does not belong to its declared split")
    digests: dict[str, list[str]] = {}
    for name in ("public_observation_sha256", "structural_label_receipt_sha256"):
        values = _string_vector(arrays[name], count, name)
        _require(all(HEX64.fullmatch(item) is not None for item in values),
                 f"{name} contains a non-SHA-256 value")
        digests[name] = values
    return {
        "row_count": count,
        "house_count": len(set(houses)),
        "observation_ids_sha256": _sha(observations),
        "house_ids_sha256": _sha(houses),
        "public_observation_digests_sha256":
            _sha(digests["public_observation_sha256"]),
        "structural_label_receipts_sha256":
            _sha(digests["structural_label_receipt_sha256"]),
        "array_content_sha256": _array_content_digest(
            arrays, NPZ_ARRAY_NAMES),
        "structural_class_counts": [int(np.sum(structural == index))
                                    for index in range(3)],
        "observation_ids": observations,
    }


def make_structural_bundle_manifest(
    *, split_arrays: Mapping[str, Mapping[str, Any]],
    partition_manifest: Mapping[str, Any],
    d219_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal the structural-only training bundle for one partition."""

    validate_d219_contract(d219_contract)
    partition = validate_house_split_manifest(partition_manifest)
    _require(set(split_arrays) == set(SPLITS),
             "structural bundle must contain train, calibration, and audit")
    summaries = {}
    all_ids: list[str] = []
    for split in SPLITS:
        summary = validate_structural_shard_arrays(
            split_arrays[split], split=split, partition_manifest=partition)
        all_ids.extend(summary.pop("observation_ids"))
        summaries[split] = summary
    _require(len(all_ids) == len(set(all_ids)),
             "observation IDs overlap across structural splits")
    payload = {
        "schema_version": BUNDLE_SCHEMA,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "feature_dimension": 396,
        "array_names": list(NPZ_ARRAY_NAMES),
        "semantic_arrays_present": False,
        "row_counts": {split: summaries[split]["row_count"]
                       for split in SPLITS},
        "structural_class_counts": {
            split: summaries[split]["structural_class_counts"]
            for split in SPLITS
        },
        "split_array_content_sha256": {
            split: summaries[split]["array_content_sha256"] for split in SPLITS
        },
        "global_observation_ids_sha256": _sha(sorted(all_ids)),
        "scenario_route_private_or_future_fields_present": False,
    }
    return _sealed(payload, "structural_bundle_sha256")


def validate_structural_bundle_manifest(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    value = clone_json(dict(manifest))
    _exact_keys(value, {
        "schema_version", "partition_manifest_receipt_sha256",
        "feature_dimension", "array_names", "semantic_arrays_present",
        "row_counts", "structural_class_counts", "split_array_content_sha256",
        "global_observation_ids_sha256",
        "scenario_route_private_or_future_fields_present",
        "structural_bundle_sha256",
    }, "D-219 structural bundle")
    _require(value["schema_version"] == BUNDLE_SCHEMA and
             value["feature_dimension"] == 396 and
             value["array_names"] == list(NPZ_ARRAY_NAMES) and
             value["semantic_arrays_present"] is False and
             value["scenario_route_private_or_future_fields_present"] is False,
             "D-219 structural bundle boundary changed")
    _require(set(value["row_counts"]) == set(SPLITS) and
             set(value["split_array_content_sha256"]) == set(SPLITS) and
             set(value["structural_class_counts"]) == set(SPLITS),
             "D-219 structural bundle split coverage changed")
    digest = value.pop("structural_bundle_sha256")
    _require(digest == _sha(value), "D-219 structural bundle digest mismatch")
    value["structural_bundle_sha256"] = digest
    return value


def fit_and_seal_structural_estimator(
    *, split_arrays: Mapping[str, Mapping[str, Any]],
    partition_manifest: Mapping[str, Any],
    structural_bundle_manifest: Mapping[str, Any],
    d215_contract: Mapping[str, Any], d219_contract: Mapping[str, Any],
    implementation_commit: str, device: str = "cpu",
) -> dict[str, dict[str, Any]]:
    """Fit the single frozen structural head and seal four artifacts."""

    contract = validate_d219_contract(d219_contract)
    d215 = validate_d215_contract(d215_contract)
    partition = validate_house_split_manifest(partition_manifest)
    bundle = validate_structural_bundle_manifest(structural_bundle_manifest)
    _require(bundle["partition_manifest_receipt_sha256"] ==
             partition["partition_manifest_receipt_sha256"],
             "structural bundle is bound to another partition manifest")
    _require(type(implementation_commit) is str and
             len(implementation_commit) == 40 and
             all(char in "0123456789abcdef" for char in implementation_commit),
             "implementation commit must be a lowercase 40-hex git commit")
    _require(set(split_arrays) == set(SPLITS),
             "fit input must contain exactly train/calibration/audit")

    validated: dict[str, dict[str, np.ndarray]] = {}
    for split in SPLITS:
        validate_structural_shard_arrays(
            split_arrays[split], split=split, partition_manifest=partition)
        validated[split] = {
            name: np.asarray(split_arrays[split][name])
            for name in ("features", "structural_labels")
        }
        _require(validated[split]["features"].shape[0] ==
                 bundle["row_counts"][split],
                 f"{split} arrays do not match the sealed bundle row count")
        _require(_array_content_digest(split_arrays[split],
                                       NPZ_ARRAY_NAMES) ==
                 bundle["split_array_content_sha256"][split],
                 f"{split} arrays do not match the sealed content digest")

    train_x = validated["train"]["features"].astype(np.float64)
    mean = train_x.mean(axis=0)
    std = np.maximum(train_x.std(axis=0, ddof=0), 1e-6)
    normalized = {
        split: ((values["features"].astype(np.float64) - mean) / std)
        .astype(np.float32)
        for split, values in validated.items()
    }
    class_weights = _class_weights(validated["train"]["structural_labels"])
    training = contract["structural_estimator"]["training"]

    try:
        import torch
        import torch.nn.functional as torch_f
    except ImportError as error:  # pragma: no cover - environment failure
        raise D219Error(
            "PyTorch is required for D-219 estimator training") from error
    _require(device == "cpu" or device.startswith("cuda"),
             "training device must be cpu or cuda")
    if device.startswith("cuda"):
        _require(torch.cuda.is_available(),
                 "requested CUDA device is unavailable")
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(training["seed"])
    target_device = torch.device(device)
    tensors = {
        split: torch.as_tensor(values, dtype=torch.float32,
                               device=target_device)
        for split, values in normalized.items()
    }
    labels = {
        split: torch.as_tensor(validated[split]["structural_labels"],
                               dtype=torch.long, device=target_device)
        for split in SPLITS
    }
    weight_matrix = torch.nn.Parameter(
        torch.zeros((3, 396), device=target_device))
    bias_vector = torch.nn.Parameter(torch.zeros(3, device=target_device))
    optimizer = torch.optim.AdamW(
        [weight_matrix, bias_vector],
        lr=training["learning_rate"],
        betas=tuple(training["adamw_betas"]),
        eps=training["adamw_epsilon"],
        weight_decay=training["weight_decay"],
    )
    class_tensor = torch.as_tensor(class_weights, dtype=torch.float32,
                                   device=target_device)

    best_metric = math.inf
    patience_reference = math.inf
    stale = 0
    best_epoch = 0
    best_state: tuple[Any, Any] | None = None
    history: list[dict[str, Any]] = []
    train_count = tensors["train"].shape[0]
    batch_size = training["batch_size"]
    for epoch in range(1, training["maximum_epochs"] + 1):
        generator = torch.Generator(device="cpu")
        generator.manual_seed(training["seed"] + epoch)
        order = torch.randperm(train_count, generator=generator)
        batch_loss_sum = 0.0
        for start in range(0, train_count, batch_size):
            indices = order[start:start + batch_size].to(target_device)
            x = tensors["train"].index_select(0, indices)
            y = labels["train"].index_select(0, indices)
            optimizer.zero_grad(set_to_none=True)
            logits = x @ weight_matrix.t() + bias_vector
            loss = torch_f.cross_entropy(logits, y, weight=class_tensor)
            loss.backward()
            optimizer.step()
            batch_loss_sum += float(loss.detach().cpu()) * len(indices)
        with torch.no_grad():
            calibration_logits = (tensors["calibration"] @ weight_matrix.t() +
                                  bias_vector)
            metric = float(torch_f.cross_entropy(
                calibration_logits, labels["calibration"]).cpu())
        history.append({
            "epoch": epoch,
            "train_weighted_mean_loss": batch_loss_sum / train_count,
            "calibration_structural_mean_nll": metric,
        })
        if metric < best_metric:
            best_metric = metric
            best_epoch = epoch
            best_state = tuple(parameter.detach().cpu().clone()
                               for parameter in (weight_matrix, bias_vector))
        if metric < patience_reference - training["early_stopping_minimum_delta"]:
            patience_reference = metric
            stale = 0
        else:
            stale += 1
        if stale >= training["early_stopping_patience_epochs"]:
            break
    _require(best_state is not None, "training did not produce a checkpoint")
    weights_np = best_state[0].numpy().astype(np.float64)
    bias_np = best_state[1].numpy().astype(np.float64)

    def numpy_logits(split: str) -> np.ndarray:
        return normalized[split].astype(np.float64) @ weights_np.T + bias_np

    temperature = _temperature(
        numpy_logits("calibration"),
        validated["calibration"]["structural_labels"].astype(int))
    metrics = {
        split: _probability_metrics(
            numpy_logits(split),
            validated[split]["structural_labels"].astype(int), temperature)
        for split in SPLITS
    }

    normalization = _sealed({
        "schema_version": NORMALIZATION_SCHEMA,
        "model_id": contract["structural_estimator"]["model_id"],
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "structural_bundle_sha256": bundle["structural_bundle_sha256"],
        "feature_order": [f"dinov2_{index:03d}" for index in range(384)] +
            list(GEOMETRY_FEATURE_ORDER),
        "mean": mean.tolist(), "population_std_floor_1e_6": std.tolist(),
        "train_row_count": int(train_count),
    }, "normalization_receipt_sha256")
    weights = _sealed({
        "schema_version": WEIGHTS_SCHEMA,
        "model_id": contract["structural_estimator"]["model_id"],
        "normalization_receipt_sha256":
            normalization["normalization_receipt_sha256"],
        "structural_weights": weights_np.tolist(),
        "structural_bias": bias_np.tolist(),
        "structural_temperature": temperature,
        "semantic_head_present": False,
    }, "weights_sha256")
    receipt = _sealed({
        "schema_version": TRAINING_RECEIPT_SCHEMA,
        "implementation_commit": implementation_commit,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "structural_bundle_sha256": bundle["structural_bundle_sha256"],
        "normalization_receipt_sha256":
            normalization["normalization_receipt_sha256"],
        "weights_sha256": weights["weights_sha256"],
        "d215_split_rule_sha256":
            d215["semantic_structural_estimator"]["training_split"]
            ["split_rule_sha256"],
        "device_type": target_device.type,
        "torch_version": torch.__version__,
        "seed": training["seed"],
        "optimizer": "AdamW",
        "adamw_betas": list(training["adamw_betas"]),
        "adamw_epsilon": training["adamw_epsilon"],
        "epochs_completed": len(history), "best_epoch": best_epoch,
        "best_calibration_structural_mean_nll_before_temperature": best_metric,
        "early_stopped": len(history) < training["maximum_epochs"],
        "structural_train_class_weights": class_weights.tolist(),
        "history": history, "post_temperature_metrics": metrics,
        "semantic_head_trained": False,
        "human_annotation_consumed": False,
        "audit_used_for_checkpoint_or_temperature": False,
        "reachable_grid_read_at_inference": False,
        "wall_clock_timeout_used": False,
        "production_reader_executed": False,
    }, "training_receipt_sha256")
    success = _sealed({
        "schema_version": SUCCESS_SCHEMA,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "structural_bundle_sha256": bundle["structural_bundle_sha256"],
        "normalization_receipt_sha256":
            normalization["normalization_receipt_sha256"],
        "weights_sha256": weights["weights_sha256"],
        "training_receipt_sha256": receipt["training_receipt_sha256"],
        "real_weight_receipt_reviewed": False,
        "audit_authorized": False,
        "production_reader_authorized": False,
    }, "success_receipt_sha256")
    return {"normalization": normalization, "weights": weights,
            "training_receipt": receipt, "success": success}
