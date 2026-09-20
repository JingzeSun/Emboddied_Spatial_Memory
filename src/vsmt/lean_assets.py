"""D-224 / S1-01: read-only checks for the asset and capacity authorization.

This module holds the rules that decide *whether an asset may be placed on
the server at all* and *how many workers a step is allowed to start*.  It
holds none of the machinery that fetches anything.  It does not open a
socket, does not run a subprocess, does not import torch, does not read the
server and does not write files.  The acquisition and probe entry points
(S1-01 proper) will call these checks; the checks must therefore be runnable
at authorization-review time, before a single byte has been downloaded.

白话：这个模块解决"一个资产现在到底允不允许被放到服务器上，以及这台机器现在
能安全开几个 worker"。输入是资产登记表、许可证记录、授权位、获取回执、容量读
数和单 worker 实测占用，输出是通过或拒绝并给出原因，以及一个可复算的 worker
数和卡住它的那一项。例如 ViT-B/14 的来源和摘要都还是 null，任何获取请求都被拒
为 registration_incomplete。它不下载资产、不安装依赖、不探测机器、不证明资产
可用，也不证明这个 worker 数跑得动。

Four rules carry the S1-01 continue gate:

1. **Registration precedes acquisition.**  An asset must already carry a
   registered identity (and a recorded licence) before it may be fetched.
   Bytes that come back may only be *compared* against the registration;
   they may never be written into it.
2. **A mismatch stops.**  Wrong digest, wrong byte count, an unlisted asset
   or an incomplete registration all produce the same verdict, and none of
   them may be answered with a mirror, another tag or a partial asset.
3. **The worker count is derived, not assumed.**  It comes from measured
   single-worker occupancy divided into measured free resources, and the
   receipt records who the binding constraint was.
4. **Receipts exist for failure too**, so a stopped acquisition leaves
   evidence instead of an empty directory.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import clone_json


CONTRACT_SCHEMA_VERSION = "vsmt-lean-s1-assets-capacity-v1"

#: Fields every registry entry carries, in this order.  A registry row with
#: a missing or an extra field is rejected rather than defaulted.
ASSET_ENTRY_FIELDS = (
    "asset_id", "role", "required_by", "source_url", "pinned_ref",
    "pinned_path", "bytes", "sha256", "registered_by", "license",
    "acquisition_mode", "acquisition_status",
)

#: How an asset reaches the server.  The list is closed so nobody can invent
#: a mode that quietly means "fetch whatever works".
ACQUISITION_MODES = (
    "clone_to_server",
    "download_to_server",
    "install_package",
    "verify_already_on_server",
    "register_then_place_on_server",
)

#: Where an asset stands right now.  ``registration_incomplete`` is the only
#: status that blocks acquisition by itself.
ACQUISITION_STATUSES = (
    "registered_not_acquired",
    "on_server_unverified_in_this_stage",
    "registration_incomplete",
)

#: An asset identified by a checkpoint file must carry both numbers; an
#: asset identified by a revision must carry the revision.  These are the
#: two ways a registration can be complete.
_FILE_MODES = frozenset({"download_to_server", "verify_already_on_server"})
_REVISION_MODES = frozenset({"clone_to_server", "install_package"})

#: Licence facts that must be on record before an asset may be fetched.
LICENSE_FIELDS = ("license_name", "license_url_or_file_path",
                  "redistribution_allowed", "research_use_allowed")

#: What the read-only capacity probe reports.
CAPACITY_MEASUREMENTS = (
    "cpu_logical_cores", "cpu_physical_cores", "ram_total_gb",
    "ram_available_gb", "gpu_count", "gpu_name", "gpu_total_vram_gb",
    "gpu_free_vram_gb", "disk_free_gb_asset_root", "disk_free_gb_install_root",
    "python_version", "torch_version", "cuda_available", "egl_resolves",
    "vulkan_resolves",
)

#: Per-worker costs that must be measured, never guessed.  The measurement
#: itself belongs to S1-02a, not here: every one of these can only be read
#: off a real episode run, and route_or_episode_generation is on this
#: stage's closed list, so S1-01 could never have measured them without
#: breaking its own guarantee (D-224-S1 ruling 14).
WORKER_DERIVATION_INPUTS = (
    "cpu_cores_per_worker", "ram_gb_per_worker", "vram_gb_per_worker",
    "disk_gb_per_worker", "simulator_concurrency_limit",
)

#: The resource each per-worker cost is divided into, in the fixed order
#: used to break ties when two constraints bind equally.
_RESOURCE_OF = (
    ("cpu_cores_per_worker", "cpu_logical_cores"),
    ("ram_gb_per_worker", "ram_available_gb"),
    ("vram_gb_per_worker", "gpu_free_vram_gb"),
    ("disk_gb_per_worker", "disk_free_gb_asset_root"),
)

ASSET_RECEIPT_FIELDS = (
    "asset_id", "acquisition_mode", "source_url", "pinned_ref",
    "observed_bytes", "observed_sha256", "registered_bytes",
    "registered_sha256", "match", "worktree_clean_including_untracked",
    "installed_dependency_versions", "torch_version_before",
    "torch_version_after", "failures",
)

CAPACITY_RECEIPT_FIELDS = (
    "measurements", "single_worker_occupancy", "derived_worker_count",
    "binding_constraint", "requested_workers", "actual_workers", "failures",
)

#: The only action a mismatch may produce.
STOP_ACTION = "stop_and_report_verbatim"

#: Bits that stay closed whatever else the user opens.
MUST_REMAIN_FALSE = (
    "asset_substitution_on_digest_mismatch",
    "alternate_version_or_mirror_on_failure",
    "torch_upgrade_reinstall_or_cuda_change",
    "editable_or_build_install_into_the_pinned_worktree",
    "server_base_python_mutation",
    "route_or_episode_generation",
    "frontend_cache_generation",
    "reid_adapter_head_training",
    "model_training",
    "private_plane_read",
    "test_split_read",
)

#: Which authorization bit each acquisition mode consumes, per asset.  A
#: mode alone is not enough: the same mode is opened separately for SAM and
#: for DINO, so that approving one never silently approves the other.
AUTHORIZATION_OF_ASSET = {
    "sam2_repository": "sam2_asset_placement_on_server",
    "sam2_model_config": "sam2_asset_placement_on_server",
    "sam2_checkpoint": "sam2_asset_placement_on_server",
    "dinov2_repository": "dinov2_existing_asset_verification",
    "dinov2_vit_s14_checkpoint": "dinov2_existing_asset_verification",
    "dinov2_vit_b14_checkpoint": "dinov2_vit_b14_asset_placement_on_server",
    "ai2thor": "simulator_asset_installation",
    "procthor_code": "simulator_asset_installation",
    "procthor_10k_dataset": "simulator_asset_installation",
}


class LeanAssetsError(ValueError):
    """Raised for any inadmissible registry, licence, receipt or worker plan."""


# --------------------------------------------------------------------------
# small validators
# --------------------------------------------------------------------------

def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanAssetsError(code)


def _int(value: Any, code: str, *, minimum: int | None = None) -> int:
    _require(type(value) is int and type(value) is not bool, code)
    if minimum is not None:
        _require(value >= minimum, code)
    return value


def _number(value: Any, code: str, *, minimum: float | None = None) -> float:
    _require(type(value) in (int, float) and type(value) is not bool, code)
    number = float(value)
    _require(math.isfinite(number), code)
    if minimum is not None:
        _require(number >= minimum, code)
    return number


def _identifier(value: Any, code: str) -> str:
    _require(type(value) is str and 1 <= len(value) <= 256, code)
    _require(all(char.isalnum() or char in "-_:." for char in value), code)
    return value


def _hex64(value: Any, code: str) -> str:
    _require(type(value) is str and len(value) == 64, code)
    _require(all(char in "0123456789abcdef" for char in value), code)
    return value


def _bool(value: Any, code: str) -> bool:
    _require(type(value) is bool, code)
    return value


# --------------------------------------------------------------------------
# asset registry
# --------------------------------------------------------------------------

def validate_asset_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Check one registry row's shape and its status/identity agreement.

    白话：输入一行资产登记，输出同样内容的副本，并在字段缺失、多出、模式或状态
    不在登记清单内，或"状态说登记完整但标识其实是 null"时拒绝。例如一个 checkpoint
    标成 registered_not_acquired 却没有 sha256，会被拒。它不检查这个资产是否真的
    存在于网上或服务器上。
    """

    _require(type(entry) is dict, "asset_entry_not_object")
    _require(tuple(entry.keys()) == ASSET_ENTRY_FIELDS, "asset_entry_fields_mismatch")

    asset_id = _identifier(entry["asset_id"], "asset_id_invalid")
    _identifier(entry["role"], "asset_role_invalid")
    _identifier(entry["required_by"], "asset_required_by_invalid")
    _require(entry["acquisition_mode"] in ACQUISITION_MODES, "asset_mode_unknown")
    _require(entry["acquisition_status"] in ACQUISITION_STATUSES, "asset_status_unknown")

    if entry["sha256"] is not None:
        _hex64(entry["sha256"], "asset_sha256_invalid")
    if entry["bytes"] is not None:
        _int(entry["bytes"], "asset_bytes_invalid", minimum=1)
    if entry["source_url"] is not None:
        _require(type(entry["source_url"]) is str and entry["source_url"][:8] == "https://",
                 "asset_source_url_invalid")
    if entry["pinned_ref"] is not None:
        _identifier(entry["pinned_ref"], "asset_pinned_ref_invalid")

    complete = registration_is_complete(entry)
    if entry["acquisition_status"] == "registration_incomplete":
        _require(not complete, "asset_status_says_incomplete_but_identity_is_complete")
    else:
        _require(complete, "asset_status_claims_registered_without_a_complete_identity")
        _require(entry["registered_by"] is not None, "asset_registered_by_missing")

    _require(asset_id in AUTHORIZATION_OF_ASSET, "asset_id_has_no_authorization_bit")
    return clone_json(dict(entry))


def registration_is_complete(entry: Mapping[str, Any]) -> bool:
    """Say whether this row identifies its asset tightly enough to verify it.

    白话：输入一行登记，输出 True/False，回答"拿到字节以后有没有东西可以比对"。
    例如一个文件类资产必须同时有字节数和 sha256，一个代码仓库必须有 commit。它不
    回答这个标识是不是正确的那一个。
    """

    mode = entry.get("acquisition_mode")
    if mode in _FILE_MODES:
        if entry.get("sha256") is not None and entry.get("bytes") is not None:
            return True
        # A local git clone is identified by its revision, not by a digest.
        return entry.get("pinned_ref") is not None
    if mode in _REVISION_MODES:
        return entry.get("pinned_ref") is not None
    # register_then_place_on_server is, by construction, not yet complete.
    return False


def validate_asset_registry(entries: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Check the whole registry and index it by ``asset_id``.

    白话：输入整张资产登记表，输出按 asset_id 索引的副本，并在有重复 id、某行不
    合法或表为空时拒绝。例如同一个 checkpoint 被登记两次（一次有摘要一次没有）
    会被拒，否则谁先被读到就决定用哪一份。
    """

    _require(type(entries) in (list, tuple) and len(entries) > 0, "asset_registry_empty")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        validated = validate_asset_entry(entry)
        _require(validated["asset_id"] not in indexed, "asset_registry_duplicate_id")
        indexed[validated["asset_id"]] = validated
    return indexed


def validate_license_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Check one licence record's four required facts.

    白话：输入一个资产的许可证记录，输出副本，并在四项中任意一项缺失或为 null 时
    拒绝。例如只写了 "Apache-2.0" 而没有出处，会被拒。它不判断许可证条款本身，也
    不构成法律意见。
    """

    _require(type(record) is dict, "license_record_not_object")
    _require(tuple(record.keys()) == LICENSE_FIELDS, "license_fields_mismatch")
    _require(type(record["license_name"]) is str and record["license_name"] != "",
             "license_name_missing")
    _require(type(record["license_url_or_file_path"]) is str
             and record["license_url_or_file_path"] != "",
             "license_source_missing")
    _bool(record["redistribution_allowed"], "license_redistribution_flag_invalid")
    _bool(record["research_use_allowed"], "license_research_flag_invalid")
    return clone_json(dict(record))


def acquisition_is_permitted(
    entry: Mapping[str, Any],
    *,
    license_record: Mapping[str, Any] | None,
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    """Decide whether this asset may be fetched right now, and say why not.

    白话：输入一行登记、它的许可证记录和当前授权位，输出 {"permitted": ...,
    "reason": ...}。例如 SAM2 的授权位是 false，返回 permitted=False、reason=
    "authorization_closed"；ViT-B/14 即使授权位打开，也会因 registration_incomplete
    被拒。它不执行获取，也不保证获取会成功。
    """

    validated = validate_asset_entry(entry)
    _require(type(authorization) is dict, "authorization_not_object")

    if validated["acquisition_status"] == "registration_incomplete":
        return {"permitted": False, "reason": "registration_incomplete"}
    if license_record is None:
        return {"permitted": False, "reason": "license_not_recorded"}
    validate_license_record(license_record)
    if not license_record["research_use_allowed"]:
        return {"permitted": False, "reason": "research_use_not_allowed"}

    bit = AUTHORIZATION_OF_ASSET[validated["asset_id"]]
    _require(bit in authorization, "authorization_bit_missing")
    if authorization[bit] is not True:
        return {"permitted": False, "reason": "authorization_closed"}
    for name in MUST_REMAIN_FALSE:
        if authorization.get(name) is True:
            return {"permitted": False, "reason": f"forbidden_bit_open:{name}"}
    return {"permitted": True, "reason": "permitted"}


# --------------------------------------------------------------------------
# receipts
# --------------------------------------------------------------------------

def verify_asset_receipt(
    entry: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare an acquisition receipt against the registration.

    白话：输入一行登记和一份获取回执，输出 {"match": ..., "action": ...,
    "mismatched_fields": [...]}。例如实测 sha256 与登记值不同，match=False、
    action="stop_and_report_verbatim"，并列出 sha256。登记值永远不会被回执改写：
    这个函数只比对，不回写，也不建议任何替代来源。
    """

    validated = validate_asset_entry(entry)
    _require(type(receipt) is dict, "asset_receipt_not_object")
    _require(tuple(receipt.keys()) == ASSET_RECEIPT_FIELDS,
             "asset_receipt_fields_mismatch")
    _require(receipt["asset_id"] == validated["asset_id"],
             "asset_receipt_names_another_asset")
    _require(receipt["acquisition_mode"] == validated["acquisition_mode"],
             "asset_receipt_mode_mismatch")

    # The receipt must echo the registration it was checked against, so a
    # reader of the receipt alone can see what the comparison used.
    _require(receipt["registered_sha256"] == validated["sha256"],
             "asset_receipt_restates_the_registration")
    _require(receipt["registered_bytes"] == validated["bytes"],
             "asset_receipt_restates_the_registration")

    mismatched: list[str] = []
    if validated["sha256"] is not None:
        if receipt["observed_sha256"] is None:
            mismatched.append("sha256_not_observed")
        else:
            _hex64(receipt["observed_sha256"], "asset_receipt_sha256_invalid")
            if receipt["observed_sha256"] != validated["sha256"]:
                mismatched.append("sha256")
    if validated["bytes"] is not None:
        if receipt["observed_bytes"] is None:
            mismatched.append("bytes_not_observed")
        elif _int(receipt["observed_bytes"], "asset_receipt_bytes_invalid",
                  minimum=0) != validated["bytes"]:
            mismatched.append("bytes")
    if validated["acquisition_mode"] in ("clone_to_server", "verify_already_on_server"):
        if receipt["worktree_clean_including_untracked"] is not True:
            mismatched.append("worktree_dirty")
    if (receipt["torch_version_before"] is not None
            and receipt["torch_version_after"] is not None
            and receipt["torch_version_before"] != receipt["torch_version_after"]):
        mismatched.append("torch_version_changed")

    match = not mismatched and not receipt["failures"]
    return {
        "match": match,
        "action": "proceed" if match else STOP_ACTION,
        "mismatched_fields": sorted(mismatched),
    }


def validate_capacity_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Check that a capacity receipt reports every measurement and both counts.

    白话：输入一份容量回执，输出副本，并在缺少 15 项读数之一、缺少单 worker 占用、
    没写 requested/actual worker 数或没写瓶颈时拒绝。例如只写了"用了 8 个 worker"
    而没有依据，会被拒。它不检查这些读数是不是真的来自这台机器。
    """

    _require(type(receipt) is dict, "capacity_receipt_not_object")
    _require(tuple(receipt.keys()) == CAPACITY_RECEIPT_FIELDS,
             "capacity_receipt_fields_mismatch")
    measurements = receipt["measurements"]
    _require(type(measurements) is dict, "capacity_measurements_not_object")
    _require(tuple(sorted(measurements.keys())) == tuple(sorted(CAPACITY_MEASUREMENTS)),
             "capacity_measurements_mismatch")
    occupancy = receipt["single_worker_occupancy"]
    _require(type(occupancy) is dict, "capacity_occupancy_not_object")
    _require(tuple(sorted(occupancy.keys())) == tuple(sorted(WORKER_DERIVATION_INPUTS)),
             "capacity_occupancy_mismatch")
    _int(receipt["derived_worker_count"], "capacity_derived_count_invalid", minimum=1)
    _int(receipt["requested_workers"], "capacity_requested_invalid", minimum=1)
    _int(receipt["actual_workers"], "capacity_actual_invalid", minimum=1)
    _require(receipt["actual_workers"] <= receipt["derived_worker_count"],
             "capacity_actual_exceeds_derived")
    _identifier(receipt["binding_constraint"], "capacity_binding_constraint_invalid")
    _require(type(receipt["failures"]) is list, "capacity_failures_not_list")
    return clone_json(dict(receipt))


# --------------------------------------------------------------------------
# worker derivation
# --------------------------------------------------------------------------

def derive_worker_count(
    measurements: Mapping[str, Any],
    occupancy: Mapping[str, Any],
    *,
    headroom_fraction: float,
    minimum_workers: int = 1,
) -> dict[str, Any]:
    """Derive the largest safe worker count and name the constraint that binds.

    白话：输入实测的机器读数和实测的单 worker 占用，加上一个余量比例，输出
    {"worker_count": n, "binding_constraint": ..., "per_resource": {...}}。做法是
    每项可用资源先乘 (1 − 余量) 再除以单 worker 占用取下整，四项资源与模拟器并发
    上限取最小值。例如内存允许 12 个、显存允许 9 个、模拟器只能 4 个，结果是 4 且
    瓶颈写 simulator_concurrency_limit。占用为 0 的资源不参与（例如纯 CPU 任务的
    显存）；任何一项算出 0 个则报错，而不是悄悄回落到 1。它不保证这个数实际跑得
    稳，只保证它有依据、可复算。
    """

    _require(type(measurements) is dict and type(occupancy) is dict,
             "worker_inputs_not_objects")
    for name in WORKER_DERIVATION_INPUTS:
        _require(name in occupancy and occupancy[name] is not None,
                 f"worker_input_missing:{name}")
    headroom = _number(headroom_fraction, "worker_headroom_invalid", minimum=0.0)
    _require(headroom < 1.0, "worker_headroom_invalid")
    _int(minimum_workers, "worker_minimum_invalid", minimum=1)

    per_resource: dict[str, int] = {}
    for cost_name, resource_name in _RESOURCE_OF:
        per_worker = _number(occupancy[cost_name], f"worker_cost_invalid:{cost_name}",
                             minimum=0.0)
        if per_worker == 0.0:
            continue
        _require(resource_name in measurements and measurements[resource_name] is not None,
                 f"worker_resource_missing:{resource_name}")
        available = _number(measurements[resource_name],
                            f"worker_resource_invalid:{resource_name}", minimum=0.0)
        per_resource[cost_name] = int(math.floor(available * (1.0 - headroom) / per_worker))

    limit = _int(occupancy["simulator_concurrency_limit"],
                 "worker_simulator_limit_invalid", minimum=1)
    per_resource["simulator_concurrency_limit"] = limit
    _require(len(per_resource) > 1, "worker_no_measured_resource")

    # Fixed evaluation order, so two constraints that bind equally always
    # name the same winner on every machine and in every run.
    order = [name for name, _ in _RESOURCE_OF] + ["simulator_concurrency_limit"]
    binding = min((name for name in order if name in per_resource),
                  key=lambda name: (per_resource[name], order.index(name)))
    worker_count = per_resource[binding]
    _require(worker_count >= minimum_workers, "worker_count_below_minimum")
    return {
        "worker_count": worker_count,
        "binding_constraint": binding,
        "per_resource": dict(per_resource),
    }


# --------------------------------------------------------------------------
# contract
# --------------------------------------------------------------------------

def validate_assets_capacity_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S1-01 machine contract agrees with this implementation.

    白话：输入 S1-01 机器合同，输出同样内容的副本，并在字段清单、获取模式、状态
    集合、许可证四项、15 项读数、worker 推导输入、两份回执字段、停止动作、禁止位
    清单或授权位与本实现不一致时拒绝。例如合同把某个摘要不符的动作从"停下"改成
    "换镜像"，会被拒。它不检查仍为 null 的数值，也不批准任何授权。
    """

    _require(type(contract) is dict, "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION,
             "contract_schema_version_invalid")
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == "S1-01", "contract_stage_id_invalid")

    required = {
        "asset_entry_fields", "acquisition_modes", "acquisition_statuses",
        "asset_registry", "registry_rules", "license_registry", "capacity_probe",
        "worker_rule", "receipts", "stop_conditions", "known_conflicts",
        "authorization", "activation_policy", "must_remain_false", "install_roots",
        "continue_gate", "policy_values_without_defaults", "user_rulings",
    }
    missing = sorted(required - set(contract.keys()))
    _require(not missing, f"contract_missing_sections:{','.join(missing)}")

    _require(tuple(contract["asset_entry_fields"]) == ASSET_ENTRY_FIELDS,
             "contract_asset_fields_mismatch")
    _require(tuple(contract["acquisition_modes"]) == ACQUISITION_MODES,
             "contract_modes_mismatch")
    _require(tuple(contract["acquisition_statuses"]) == ACQUISITION_STATUSES,
             "contract_statuses_mismatch")
    _require(tuple(contract["license_registry"]["must_record_per_asset"]) == LICENSE_FIELDS,
             "contract_license_fields_mismatch")
    _require(tuple(contract["capacity_probe"]["measurements"]) == CAPACITY_MEASUREMENTS,
             "contract_measurements_mismatch")
    _require(tuple(contract["worker_rule"]["derivation_inputs"]) == WORKER_DERIVATION_INPUTS,
             "contract_worker_inputs_mismatch")
    _require(tuple(contract["receipts"]["asset_receipt_fields"]) == ASSET_RECEIPT_FIELDS,
             "contract_asset_receipt_fields_mismatch")
    _require(tuple(contract["receipts"]["capacity_receipt_fields"]) == CAPACITY_RECEIPT_FIELDS,
             "contract_capacity_receipt_fields_mismatch")
    _require(tuple(contract["must_remain_false"]) == MUST_REMAIN_FALSE,
             "contract_must_remain_false_mismatch")

    # The registry is the part a reviewer reads line by line, so it is
    # validated with the same code the acquisition step will use.
    registry = validate_asset_registry(contract["asset_registry"])
    _require(set(registry.keys()) == set(AUTHORIZATION_OF_ASSET.keys()),
             "contract_registry_asset_set_mismatch")
    for entry in registry.values():
        _require(entry["license"] is None,
                 "contract_license_must_be_recorded_separately_not_inline")

    # Every stop condition is the same single action, and the two escape
    # hatches stay shut.
    for name, action in contract["stop_conditions"].items():
        if name in ("may_retry_with_another_version_or_mirror",
                    "may_proceed_with_a_partially_verified_asset"):
            _require(action is False, f"contract_stop_escape_open:{name}")
        elif name != "plain_language_zh":
            _require(action == STOP_ACTION, f"contract_stop_action_weakened:{name}")

    for section, names in (
        ("registry_rules", ("registration_precedes_acquisition",
                            "an_asset_without_a_registered_identity_may_not_be_acquired",
                            "a_registered_digest_may_not_be_rewritten_by_an_acquisition",
                            "license_must_be_recorded_before_acquisition",
                            "unlisted_asset_may_not_be_acquired",
                            "upstream_declared_identity_counts_as_registration",
                            "lfs_pointer_materialization_is_not_a_dirty_worktree")),
        ("capacity_probe", ("read_only",)),
        ("worker_rule", ("worker_count_is_derived_not_assumed",
                         "derivation_requires_measured_single_worker_occupancy",
                         "receipt_records_requested_and_actual",
                         "merge_order_is_deterministic_and_independent_of_completion_order",
                         "serial_fallback_requires_a_stated_reason_and_evidence")),
        ("receipts", ("receipt_is_written_even_on_failure",)),
        ("license_registry", ("unrecorded_license_blocks_acquisition",
                              "license_is_not_inferred_from_the_repository_name")),
        ("install_roots", ("writing_outside_these_roots_is_forbidden",)),
        ("continue_gate", ("every_authorization_bit_is_false_until_the_user_opens_it",
                           "registration_precedes_acquisition",
                           "a_mismatch_stops_and_never_substitutes",
                           "worker_count_is_derived_from_measurement_and_recorded",
                           "receipts_exist_for_success_and_failure")),
    ):
        for name in names:
            _require(contract[section][name] is True,
                     f"contract_{section}_{name}_weakened")

    for name in ("may_load_a_model", "may_read_a_public_input",
                 "may_write_outside_the_receipt_path"):
        _require(contract["capacity_probe"][name] is False,
                 f"contract_capacity_probe_{name}_opened")

    _require(contract["worker_rule"]["headroom_fraction"] is None,
             "contract_headroom_must_be_null_before_freeze")
    _require(contract["worker_rule"]["minimum_workers"] == 1,
             "contract_minimum_workers_changed")

    # A conflict may only carry a resolution once a ruling stands behind it,
    # and a resolved conflict must stop claiming to block a later step.
    ruling_id = contract["user_rulings"].get("decision_id")
    _require(type(ruling_id) is str and ruling_id != "", "contract_ruling_id_missing")
    # A conflict is in exactly one of three states.  Unresolved: no plan, no
    # evidence, and it still blocks.  Ruled: a plan that names the ruling,
    # but no receipt yet, so it still blocks.  Discharged: a plan and a
    # receipt, and only then may it stop blocking.
    for conflict in contract["known_conflicts"]:
        _require("evidence_of_resolution" in conflict,
                 "contract_conflict_missing_evidence_field")
        blocks = conflict["blocks"]
        _require(type(blocks) is list, "contract_conflict_blocks_not_list")
        if conflict["resolution"] is None:
            _require(conflict["evidence_of_resolution"] is None,
                     "contract_conflict_has_evidence_without_a_resolution")
            _require(len(blocks) > 0, "contract_unresolved_conflict_blocks_nothing")
        elif conflict["evidence_of_resolution"] is None:
            _require(ruling_id in conflict["resolution"],
                     "contract_conflict_resolved_without_naming_the_ruling")
            _require(len(blocks) > 0, "contract_unexecuted_ruling_stopped_blocking")
        else:
            _require(len(blocks) == 0,
                     "contract_discharged_conflict_still_claims_to_block")

    # Authorization: only the bits the ruling opened may be true, the closed
    # list stays closed, and an exercised bit must be one that is open.
    policy = contract["activation_policy"]
    opened = tuple(policy["active_true_authorizations"])
    _require(policy["opened_by"] == ruling_id, "contract_activation_not_bound_to_the_ruling")
    for name, value in contract["authorization"].items():
        _require(type(value) is bool, "contract_authorization_not_boolean")
        if value:
            _require(name in opened, f"contract_authorization_opened_without_a_ruling:{name}")
    for name in opened:
        _require(name in contract["authorization"], f"contract_opened_bit_unknown:{name}")
        _require(name not in MUST_REMAIN_FALSE, f"contract_opened_a_closed_bit:{name}")
    for name in policy["exercised_so_far"]:
        _require(name in opened, f"contract_exercised_a_bit_that_is_not_open:{name}")

    # The occupancy measurement may not be re-opened here: it needs an
    # episode run, which this stage keeps closed, so authorising it in this
    # contract would promise something the same contract forbids.
    _require("single_worker_occupancy_measurement" not in contract["authorization"],
             "contract_reopened_the_measurement_this_stage_cannot_perform")
    _require(contract["worker_rule"]["measurement_stage"] == "S1-02a",
             "contract_measurement_stage_moved")
    _require(contract["worker_rule"]["measurement_is_not_authorized_in_this_stage"] is True,
             "contract_measurement_claimed_in_this_stage")
    for name in MUST_REMAIN_FALSE:
        _require(contract["authorization"].get(name) is not True,
                 f"contract_closed_bit_opened:{name}")
    return clone_json(dict(contract))


__all__ = [
    "ACQUISITION_MODES",
    "ACQUISITION_STATUSES",
    "ASSET_ENTRY_FIELDS",
    "ASSET_RECEIPT_FIELDS",
    "AUTHORIZATION_OF_ASSET",
    "CAPACITY_MEASUREMENTS",
    "CAPACITY_RECEIPT_FIELDS",
    "CONTRACT_SCHEMA_VERSION",
    "LICENSE_FIELDS",
    "MUST_REMAIN_FALSE",
    "STOP_ACTION",
    "WORKER_DERIVATION_INPUTS",
    "LeanAssetsError",
    "acquisition_is_permitted",
    "derive_worker_count",
    "registration_is_complete",
    "validate_asset_entry",
    "validate_asset_registry",
    "validate_assets_capacity_contract",
    "validate_capacity_receipt",
    "validate_license_record",
    "verify_asset_receipt",
]
