"""D-224 / S0-02: read-only checks for the VSMT-lean intervention data contract.

This module holds every rule that decides *whether a generated episode is
admissible*, and none of the machinery that generates one.  It does not open
AI2-THOR, does not read RGB-D, does not touch numpy and does not write files.
The generator (S1-02) will call these checks; the checks must therefore be
runnable at contract-review time, before any data exists.

白话：这个模块解决"一条已经计划好或已经生成的 episode 合不合规"。输入是 house
划分、路线计划、干预计划、逐观察可见性判定和三面文件清单，输出是通过或拒绝并
给出原因。例如一次干预的源容器在窗口内某一帧仍然可见，整条 episode 被拒。它不
生成数据、不调用模拟器、不读取 RGB-D，也不判断干预在科学上是否有趣。

Four rules carry the S0-02 continue gate:

1. The split is a pure function of ``(seed, house_id)``, so no house can be
   moved between train/validation/test after the fact.
2. An intervention may only run while **every** container it touches is
   unobservable for the whole window.  The judgement is not re-derived here:
   the generator supplies the per-observation visibility verdicts produced by
   ``vm04_public_visibility``, and this module requires them to be complete,
   contiguous and uniformly negative.
3. ``private`` and ``provenance`` never appear in a deployment reader's
   whitelist, and the three planes never share a file.
4. A failed house keeps a receipt and is never replaced, so the realised
   sample is whatever the frozen manifest produced.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json


CONTRACT_SCHEMA_VERSION = "vsmt-lean-s0-intervention-data-v3"

#: The three reading faces.  A file belongs to exactly one.
PLANES = ("public", "private", "provenance")

#: Prefix allocation order of the hash-sorted house list (D-224-X ruling X6).
#: ``test`` and ``validation`` take the first two blocks, ``train`` the third,
#: so a later reduction of the train size (the only size S3-01 may lower) can
#: never move a house into or out of test or validation.
SPLIT_PREFIX_ORDER = ("test", "validation", "train")

#: Planes a deployment-time reader (frontend, recall, features, any of the
#: five arms) may mount.  Everything else is teacher/evaluator/audit only.
DEPLOYMENT_READABLE_PLANES = frozenset({"public"})

#: Intervention kinds.  ``move`` keeps the simulator object, ``remove`` takes
#: it out of the scene, ``add`` introduces one from the house's own pool.
INTERVENTION_KINDS = ("remove", "move", "add")

#: The registered action alphabet.  Magnitudes live in the contract.
ACTIONS = (
    "MoveAhead", "MoveBack", "MoveLeft", "MoveRight",
    "RotateLeft", "RotateRight", "LookUp", "LookDown",
)

#: Fields every public frame record must carry, and nothing more.
PUBLIC_FRAME_FIELDS = (
    "observation_index", "rgb_path", "depth_path", "intrinsics",
    "relative_pose", "action_summary", "frame_digest",
)

#: Fields the private plane carries.  None of these may leak into public.
PRIVATE_FRAME_FIELDS = (
    "observation_index", "instance_mask_path", "object_id_to_entity_id",
    "object_poses", "object_visibility", "frame_digest",
)
#: D-224-S1 ruling 45 (2026-09-22): one per-episode private geometry table, read from a single
#: simulator reload of the house at the house-authored agent pose, written by the S1-04 tool.
#: It carries what the per-frame private record never had: each object's initial rotation and
#: axis-aligned box, so a truth box for frame t is the initial box translated by the recorded
#: private position.  The episode runner never writes it and no deployment reader may mount it.
PRIVATE_HOUSE_GEOMETRY_FILE = "object_geometry.json"
PRIVATE_HOUSE_GEOMETRY_FIELDS = (
    "object_id", "asset_id", "object_type", "pickupable", "receptacle",
    "initial_position_world_m", "initial_rotation_degrees",
    "initial_aabb_center_world_m", "initial_aabb_size_m",
)

#: Identifiers that must never appear in a public record, at any depth.
FORBIDDEN_PUBLIC_KEYS = frozenset({
    "house_id", "scene_name", "scenario", "object_id", "instance_id",
    "entity_id", "intervention", "intervention_log", "teacher", "label",
    "reference", "future", "split",
})

#: Reasons a house may be recorded as failed.  The list is closed so a
#: generator cannot invent a reason that quietly means "replaced".
FAILURE_REASONS = (
    "house_load_failed",
    "route_not_placeable",
    "action_rejected",
    "intervention_window_unavailable",
    "intervention_execution_failed",
    "frame_write_failed",
)

#: R1 / I1 rule constants (D-224-S1 rulings 23/24).  The contract binds them.
COVERAGE_DEFINITION = "every_eligible_container_observed_once_before_and_the_revisit_set_once_after"
#: D-224-S1 ruling 34 (twin control): sweep two revisits the intervened containers plus an equal
#: number of seeded unintervened controls; a null episode builds the same revisit set and skips
#: only the execution.
REVISIT_SET = "intervened_containers_plus_equal_seeded_controls_from_U_holding_a_seen_object"
NULL_EPISODE_RULE = "same_pipeline_including_dry_run_sampling_controls_route_and_cap_execution_skipped"
#: D-224-S1 ruling 35: the container visibility subject is sealed from the sweep-one frame in
#: which the container has the most private mask pixels (the viewpoint frame was 0 px for 972/1521
#: containers in the 4bff1a8 run, LOG-239).
SUBJECT_SEAL_FRAME = "sweep_one_frame_with_the_most_container_pixels"
MIN_SUBJECT_PIXELS = 512  # 32 samples x stride 4^2 of the shared visibility config
#: D-224-S1 ruling 36: dataset-level move minimum, judged on the S3-01 train block.
MOVE_MINIMUM_TRAIN = 120
MOVE_MINIMUM_SOURCE_FIRST_TRAIN = 60
#: D-224-S1 ruling 37: the null-window draw mixes a private salt that lives outside the
#: repository; only its sha256 is written to provenance.
NULL_WINDOW_SALT_RULE = "sha256(split_seed, house_id, null_window, private_salt)_salt_registered_by_sha256_only"
#: D-224-S1 ruling 38: eligibility pixels come from sweep-one frames only; the unseen pool from
#: every frame before the window.
ELIGIBLE_PIXEL_FRAMES = "sweep_one_only"
UNSEEN_PIXEL_FRAMES = "every_frame_before_the_window"
VIEWPOINT_DISTANCE_M = (0.75, 2.5)
VIEWPOINT_PITCH_OPTIONS = (-30, 0, 30)
ROUTE_STRUCTURE = ("sweep_one", "transition", "sweep_two")
PATH_ENCODING = "turn_then_move_ahead_no_strafe"
MIN_VISIBLE_PIXELS = 196
RNG_PURPOSE_TAGS = ("intervention", "revisit_order", "null_window", "control_revisit", "dry_run_order")
ADD_SOURCE = "relocate_never_rendered_existing_object_via_PlaceObjectAtPoint"
REMOVE_EXECUTOR = "DisableObject"
SAMPLING = "kind_first_uniform_over_kinds_with_remaining_triples_then_triple_uniform"
PLACEMENT_PRESCREEN = "dry_run_place_peek_revert_in_window"
DRY_RUN_MAX_POINTS = 32
#: D-224-S1 ruling 39 (2026-09-21): destinations tested per candidate object in the dry run, drawn by
#: the seeded RNG; 0 tests every destination and exists only to replay the S1 runs.
DRY_RUN_DESTINATIONS_PER_OBJECT = 8
MAX_REPLANS = 32
P_NULL_WINDOW = 0.2
MINIMUM_WINDOW_FRAMES = 20
MAXIMUM_ACTIONS = 4000  # D-224-S1 ruling 40 (2026-09-21): 2000 -> 4000, a scope boundary
MAXIMUM_ACTIONS_SUPERSEDED = 2000
MAXIMUM_INTERVENTIONS_PER_EPISODE = 6
MINIMUM_YIELD = 0.6


class LeanInterventionError(ValueError):
    """Raised for any inadmissible split, route, intervention or layout."""


# --------------------------------------------------------------------------
# small validators
# --------------------------------------------------------------------------

def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanInterventionError(code)


def _int(value: Any, code: str, *, minimum: int | None = None) -> int:
    _require(type(value) is int and type(value) is not bool, code)
    if minimum is not None:
        _require(value >= minimum, code)
    return value


def _identifier(value: Any, code: str) -> str:
    _require(type(value) is str and 1 <= len(value) <= 128, code)
    _require(all(char.isalnum() or char in "-_:." for char in value), code)
    return value


def _hex64(value: Any, code: str) -> str:
    _require(type(value) is str and len(value) == 64, code)
    _require(all(char in "0123456789abcdef" for char in value), code)
    return value


def _reject_forbidden_keys(value: Any, *, code: str) -> None:
    if type(value) is dict:
        for key, item in value.items():
            _require(key not in FORBIDDEN_PUBLIC_KEYS, f"{code}:{key}")
            _reject_forbidden_keys(item, code=code)
    elif type(value) is list:
        for item in value:
            _reject_forbidden_keys(item, code=code)


# --------------------------------------------------------------------------
# 1. split
# --------------------------------------------------------------------------

def house_split_rank(house_id: str, *, seed: int) -> str:
    """Return the deterministic ordering key for one house.

    白话：输入 house 标识和登记的 seed，输出一个只由这两者决定的排序键。例如同
    一个 house 在任何机器、任何时间都得到同一个键，因此划分无法在看过结果后被
    调整。它不表示这个 house 属于哪一份，那由下面的前缀规则决定。
    """

    _identifier(house_id, "house_id_invalid")
    _int(seed, "split_seed_invalid", minimum=0)
    payload = canonical_json([seed, house_id]).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assign_split(
    house_ids: Sequence[str], *, seed: int, train: int, validation: int, test: int,
) -> dict[str, list[str]]:
    """Split houses by hash prefix into three mutually exclusive lists.

    白话：输入候选 house 清单与三份规模，输出 train/validation/test 三个互斥列
    表。排序后的前缀先给 test、再给 validation、最后给 train（D-224-X 裁决 X6）：
    这样 S3-01 若按成品率下调 train 规模，test 与 validation 的成员一个都不会变；
    反过来 test/validation 的规模与 seed 必须在第一条 episode 生成前冻结，因为
    改它们会挪动 train 的起点。它不生成任何数据，也不检查 house 是否真的可加载。
    """

    _require(type(house_ids) is list or type(house_ids) is tuple, "house_ids_invalid")
    sizes = {"train": train, "validation": validation, "test": test}
    for name, value in sizes.items():
        _int(value, f"split_size_{name}_invalid", minimum=0)
    unique = [_identifier(item, "house_id_invalid") for item in house_ids]
    _require(len(set(unique)) == len(unique), "house_ids_duplicate")
    total = train + validation + test
    _require(len(unique) >= total, "house_pool_smaller_than_split")

    ordered = sorted(unique, key=lambda item: (house_split_rank(item, seed=seed), item))
    return {
        "test": ordered[:test],
        "validation": ordered[test:test + validation],
        "train": ordered[test + validation:total],
    }


def validate_split_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute the split from its own declared inputs and require a match.

    白话：输入一份划分清单，输出同样内容的副本，并在清单与按规则重算的结果不
    一致时拒绝。例如有人把一个 house 从 test 挪到 train，重算立刻不符。它不检查
    这些 house 是否已经生成成功。
    """

    _require(type(manifest) is dict, "split_manifest_not_object")
    _require(
        set(manifest.keys()) == {
            "seed", "house_pool", "train", "validation", "test",
        },
        "split_manifest_fields_invalid",
    )
    seed = _int(manifest["seed"], "split_seed_invalid", minimum=0)
    recomputed = assign_split(
        list(manifest["house_pool"]), seed=seed,
        train=len(manifest["train"]),
        validation=len(manifest["validation"]),
        test=len(manifest["test"]),
    )
    for name in ("train", "validation", "test"):
        _require(
            list(manifest[name]) == recomputed[name],
            f"split_{name}_does_not_match_the_rule",
        )
    members = [item for name in ("train", "validation", "test") for item in manifest[name]]
    _require(len(set(members)) == len(members), "split_houses_not_mutually_exclusive")
    return clone_json(dict(manifest))


# --------------------------------------------------------------------------
# 2. route and intervention plan
# --------------------------------------------------------------------------

def validate_route_plan(
    plan: Mapping[str, Any], *, maximum_actions: int,
) -> dict[str, Any]:
    """Check one pre-registered route: closed action alphabet, budget, order.

    白话：输入执行前登记的完整动作序列，输出同样内容的副本，并在出现未登记动
    作、超出机械保护上限或观察序号不连续时拒绝。例如把一个未登记的 Teleport 混
    进路线会被拒。它不检查路线在这个 house 里是否真的走得通，那要等真实执行。
    """

    _require(type(plan) is dict, "route_plan_not_object")
    _require(
        set(plan.keys()) == {"house_id", "actions", "observation_count"},
        "route_plan_fields_invalid",
    )
    _identifier(plan["house_id"], "house_id_invalid")
    limit = _int(maximum_actions, "route_action_limit_invalid", minimum=1)
    actions = plan["actions"]
    _require(type(actions) is list, "route_actions_invalid")
    _require(len(actions) <= limit, "route_exceeds_action_protection_limit")
    for action in actions:
        _require(action in ACTIONS, "route_action_not_registered")
    # Observation 0 precedes every action, so counts differ by exactly one.
    _require(
        _int(plan["observation_count"], "route_observation_count_invalid", minimum=1)
        == len(actions) + 1,
        "route_observation_count_mismatch",
    )
    return clone_json(dict(plan))


def validate_intervention_plan(
    plan: Mapping[str, Any], *, maximum_interventions: int, observation_count: int,
) -> dict[str, Any]:
    """Check the declared interventions of one episode.

    白话：输入一条 episode 的干预计划，输出同样内容的副本，并在干预数量超限、
    类型不在三类之内、窗口越界或两次干预共用同一物体时拒绝。例如一个物体先被
    移走又被搬动，属于矛盾计划。它不判断窗口内容器是否真的看不见，那由
    assert_windows_unobservable 检查。
    """

    _require(type(plan) is dict, "intervention_plan_not_object")
    _require(
        set(plan.keys()) == {"house_id", "interventions"},
        "intervention_plan_fields_invalid",
    )
    _identifier(plan["house_id"], "house_id_invalid")
    limit = _int(
        maximum_interventions, "intervention_limit_invalid", minimum=1,
    )
    frames = _int(observation_count, "observation_count_invalid", minimum=2)

    interventions = plan["interventions"]
    _require(type(interventions) is list, "interventions_invalid")
    _require(len(interventions) <= limit, "too_many_interventions")

    seen_objects: set[str] = set()
    for item in interventions:
        _require(type(item) is dict, "intervention_not_object")
        _require(
            set(item.keys()) == {
                "intervention_id", "kind", "object_ref", "source_container_ref",
                "target_container_ref", "window_start_index", "window_end_index",
                "container_refs",
            },
            "intervention_fields_invalid",
        )
        _identifier(item["intervention_id"], "intervention_id_invalid")
        kind = item["kind"]
        _require(kind in INTERVENTION_KINDS, "intervention_kind_unknown")
        object_ref = _identifier(item["object_ref"], "intervention_object_ref_invalid")
        _require(object_ref not in seen_objects, "intervention_object_used_twice")
        seen_objects.add(object_ref)

        source = item["source_container_ref"]
        target = item["target_container_ref"]
        if kind == "remove":
            _identifier(source, "intervention_source_required")
            _require(target is None, "remove_must_not_have_target")
        elif kind == "add":
            _require(source is None, "add_must_not_have_source")
            _identifier(target, "intervention_target_required")
        else:  # move
            _identifier(source, "intervention_source_required")
            _identifier(target, "intervention_target_required")
            _require(source != target, "move_source_equals_target")

        start = _int(item["window_start_index"], "window_start_invalid", minimum=0)
        end = _int(item["window_end_index"], "window_end_invalid", minimum=0)
        _require(start <= end, "window_inverted")
        _require(end < frames, "window_past_last_observation")

        refs = item["container_refs"]
        _require(type(refs) is list and refs, "container_refs_invalid")
        for ref in refs:
            _identifier(ref, "container_ref_invalid")
        expected = {value for value in (source, target) if value is not None}
        _require(
            expected <= set(refs),
            "container_refs_missing_source_or_target",
        )
    return clone_json(dict(plan))


def assert_windows_unobservable(
    plan: Mapping[str, Any], visibility: Mapping[str, Any],
) -> dict[str, Any]:
    """Require every touched container to be unobservable for the whole window.

    白话：输入干预计划和逐观察的公开可见性判定，输出一份逐干预的回执，并在窗口
    内任何一帧任何相关容器被判为可见、或判定缺失、或判定不连续时拒绝。例如源容
    器在窗口中间的一帧重新进入视野，整条 episode 失败，不缩短窗口、不换物体。
    它不自己计算可见性；判定必须由 `vm04_public_visibility` 在公开深度上产生。

    ``visibility`` maps ``"<container_ref>@<observation_index>"`` to a verdict
    dict carrying ``visible`` and the receipt digest of the depth frame it was
    computed from, so a verdict cannot be asserted without naming its evidence.
    """

    _require(type(visibility) is dict, "visibility_not_object")
    receipts: list[dict[str, Any]] = []
    for item in plan["interventions"]:
        start = int(item["window_start_index"])
        end = int(item["window_end_index"])
        for ref in item["container_refs"]:
            for index in range(start, end + 1):
                key = f"{ref}@{index}"
                _require(key in visibility, f"visibility_verdict_missing:{key}")
                verdict = visibility[key]
                _require(type(verdict) is dict, "visibility_verdict_not_object")
                _require(
                    set(verdict.keys()) == {"visible", "depth_frame_digest"},
                    "visibility_verdict_fields_invalid",
                )
                _hex64(
                    verdict["depth_frame_digest"], "visibility_digest_invalid",
                )
                _require(
                    verdict["visible"] is False,
                    f"container_visible_inside_window:{key}",
                )
        receipts.append({
            "intervention_id": item["intervention_id"],
            "container_refs": sorted(item["container_refs"]),
            "window_start_index": start,
            "window_end_index": end,
            "verdict_count": len(item["container_refs"]) * (end - start + 1),
        })
    return {"house_id": plan["house_id"], "window_receipts": receipts}


# --------------------------------------------------------------------------
# 3. three planes and reader whitelists
# --------------------------------------------------------------------------

def validate_three_plane_layout(layout: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the three faces are disjoint and correctly populated.

    白话：输入一条 episode 的三面文件清单，输出同样内容的副本，并在同一个文件同
    时出现在两面、或公开面出现 private 字段名时拒绝。例如把 instance mask 写进
    public 目录会被拒。它不打开这些文件，只检查清单与字段名。
    """

    _require(type(layout) is dict, "layout_not_object")
    _require(set(layout.keys()) == set(PLANES), "layout_planes_invalid")
    seen: set[str] = set()
    for plane in PLANES:
        paths = layout[plane]
        _require(type(paths) is list and paths, f"layout_{plane}_empty")
        for path in paths:
            _require(type(path) is str and path, "layout_path_invalid")
            _require(path not in seen, f"layout_path_in_two_planes:{path}")
            seen.add(path)
            _require(
                path.startswith(f"{plane}/"),
                f"layout_path_outside_its_plane:{path}",
            )
    return clone_json(dict(layout))


def assert_reader_whitelist(
    *, reader_id: str, requested_planes: Sequence[str], deployment_reader: bool,
) -> dict[str, Any]:
    """Refuse any deployment reader that asks for private or provenance.

    白话：输入一个读取器的标识与它想挂载的面，输出通过回执，并在部署期读取器请
    求 private 或 provenance 时拒绝。例如候选特征计算器请求 instance mask 会被
    拒。它不检查该读取器实际打开了什么文件，那由运行期回执另行核对。
    """

    _identifier(reader_id, "reader_id_invalid")
    _require(type(deployment_reader) is bool, "deployment_reader_flag_invalid")
    planes = list(requested_planes)
    _require(planes, "reader_requested_no_plane")
    for plane in planes:
        _require(plane in PLANES, "reader_requested_unknown_plane")
    if deployment_reader:
        illegal = sorted(set(planes) - DEPLOYMENT_READABLE_PLANES)
        _require(not illegal, f"deployment_reader_requested:{','.join(illegal)}")
    return {
        "reader_id": reader_id,
        "granted_planes": sorted(set(planes)),
        "deployment_reader": deployment_reader,
    }


def validate_public_frame_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Check one public frame record and reject any private identifier in it.

    白话：输入一条公开帧记录，输出同样内容的副本，并在字段不符或任何层级出现
    house/object/instance 之类标识时拒绝。例如在内参里塞一个 scene_name 会被拒。
    它不读取图像本身，也不验证 depth 数值是否合理。
    """

    _require(type(record) is dict, "public_frame_not_object")
    _require(
        tuple(sorted(record.keys())) == tuple(sorted(PUBLIC_FRAME_FIELDS)),
        "public_frame_fields_invalid",
    )
    _int(record["observation_index"], "public_frame_index_invalid", minimum=0)
    _hex64(record["frame_digest"], "public_frame_digest_invalid")
    _reject_forbidden_keys(record, code="public_frame_forbidden_key")
    return clone_json(dict(record))


# --------------------------------------------------------------------------
# 4. failure receipts
# --------------------------------------------------------------------------

def validate_failure_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Check that a failed house is kept, explained and not replaced.

    白话：输入一条失败回执，输出同样内容的副本，并在原因不在封闭清单内、或声称
    已被替换时拒绝。例如把失败的 house 换成下一个候选会被拒。它不判断这次失败是
    否可以修复。
    """

    _require(type(receipt) is dict, "failure_receipt_not_object")
    _require(
        set(receipt.keys()) == {
            "house_id", "split", "reason", "failed_at_observation_index",
            "kept_prefix_observation_count", "replaced",
        },
        "failure_receipt_fields_invalid",
    )
    _identifier(receipt["house_id"], "house_id_invalid")
    _require(
        receipt["split"] in {"train", "validation", "test"},
        "failure_receipt_split_invalid",
    )
    _require(receipt["reason"] in FAILURE_REASONS, "failure_reason_unknown")
    _int(
        receipt["failed_at_observation_index"],
        "failure_index_invalid", minimum=0,
    )
    _int(
        receipt["kept_prefix_observation_count"],
        "failure_prefix_invalid", minimum=0,
    )
    _require(receipt["replaced"] is False, "failed_house_must_not_be_replaced")
    return clone_json(dict(receipt))


def summarize_yield(
    *, planned: int, succeeded: int, failures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return the realised yield, with every failure accounted for.

    白话：输入计划数、成功数和全部失败回执，输出成品率摘要，并在数目对不上时拒
    绝。例如计划 50 条、成功 47 条却只有 2 份失败回执，说明有一条被静默丢弃。
    它不决定成品率是否足够，那由 S0-02 登记的下限和用户裁决决定。
    """

    total = _int(planned, "planned_invalid", minimum=1)
    ok = _int(succeeded, "succeeded_invalid", minimum=0)
    records = [validate_failure_receipt(item) for item in failures]
    _require(ok + len(records) == total, "planned_does_not_equal_success_plus_failure")
    return {
        "planned": total,
        "succeeded": ok,
        "failed": len(records),
        "yield": ok / total,
        "failure_reasons": sorted({str(item["reason"]) for item in records}),
    }


# --------------------------------------------------------------------------
# machine contract
# --------------------------------------------------------------------------

def validate_intervention_data_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S0-02 machine contract agrees with this implementation.

    白话：输入 S0-02 机器合同，输出同样内容的副本，并在动作字母表、干预三类、三
    面划分、部署可读面、失败原因清单或授权位与本实现不一致时拒绝。例如合同多出
    一个 "teleport" 动作会被拒。它不检查仍为 null 的数值。
    """

    _require(type(contract) is dict, "contract_not_object")
    _require(
        contract.get("schema_version") == CONTRACT_SCHEMA_VERSION,
        "contract_schema_version_invalid",
    )
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == "S0-02", "contract_stage_id_invalid")

    required = {
        "intervention_kinds", "planes", "deployment_readable_planes",
        "failure_reasons", "forbidden_public_keys", "public_frame_fields",
        "private_frame_fields", "split_rule", "route", "intervention_window",
        "authorization",
    }
    missing = sorted(required - set(contract.keys()))
    _require(not missing, f"contract_missing_sections:{','.join(missing)}")

    # The action alphabet belongs to the route section, not the top level.
    _require(tuple(contract["route"]["actions"]) == ACTIONS, "contract_actions_mismatch")
    _require(
        tuple(contract["intervention_kinds"]) == INTERVENTION_KINDS,
        "contract_intervention_kinds_mismatch",
    )
    _require(tuple(contract["planes"]) == PLANES, "contract_planes_mismatch")
    _require(
        frozenset(contract["deployment_readable_planes"]) == DEPLOYMENT_READABLE_PLANES,
        "contract_deployment_planes_mismatch",
    )
    _require(
        tuple(contract["failure_reasons"]) == FAILURE_REASONS,
        "contract_failure_reasons_mismatch",
    )
    _require(
        frozenset(contract["forbidden_public_keys"]) == FORBIDDEN_PUBLIC_KEYS,
        "contract_forbidden_keys_mismatch",
    )
    # D-224-S1 ruling 45 (2026-09-22): the private plane also carries one per-episode object
    # geometry table, written after generation by the S1-04 reload tool, never by the runner.
    geometry = contract["private_house_geometry"]
    _require(geometry["plane"] == "private", "contract_house_geometry_plane_mismatch")
    _require(geometry["file"] == PRIVATE_HOUSE_GEOMETRY_FILE, "contract_house_geometry_file_mismatch")
    _require(tuple(geometry["fields"]) == PRIVATE_HOUSE_GEOMETRY_FIELDS,
             "contract_house_geometry_fields_mismatch")
    for name in ("one_per_episode", "episode_origin_world_m_recorded",
                 "never_readable_by_a_deployment_reader"):
        _require(geometry[name] is True, f"contract_house_geometry_{name}_weakened")
    _require(geometry["written_by_the_episode_runner"] is False,
             "contract_house_geometry_written_by_runner")
    _require(
        tuple(contract["public_frame_fields"]) == PUBLIC_FRAME_FIELDS,
        "contract_public_frame_fields_mismatch",
    )
    _require(
        tuple(contract["private_frame_fields"]) == PRIVATE_FRAME_FIELDS,
        "contract_private_frame_fields_mismatch",
    )
    _require(
        contract["intervention_window"]["verdict_source"]
        == "vm04_public_visibility.assess_public_visibility_from_depth",
        "contract_window_verdict_source_mismatch",
    )
    _require(
        contract["intervention_window"]["every_container_every_frame_must_be_invisible"]
        is True,
        "contract_window_rule_weakened",
    )
    _require(
        tuple(contract["split_rule"]["prefix_assignment"]) == SPLIT_PREFIX_ORDER,
        "contract_split_prefix_order_mismatch",
    )
    for name in (
        "test_and_validation_sizes_and_seed_frozen_before_first_generation",
        "train_size_may_only_decrease_after_registration",
    ):
        _require(
            contract["split_rule"][name] is True,
            f"contract_split_rule_{name}_weakened",
        )

    # A registered value is either still open, and then it must say so in
    # policy_values_without_defaults, or frozen, and then it must have left
    # that list.  Requiring null outright would have made it impossible to
    # ever record the value the contract was written to carry.
    open_values = contract["policy_values_without_defaults"]
    for section, names in (
        ("split_rule", ("train_houses", "validation_houses", "test_houses", "seed")),
        ("route", ("maximum_actions", "translation_m", "rotation_degrees",
                   "look_degrees")),
        ("intervention_window", ("maximum_interventions_per_episode",
                                 "minimum_yield")),
    ):
        for name in names:
            registered = f"{section}.{name}"
            if contract[section][name] is None:
                _require(registered in open_values,
                         f"contract_{section}_{name}_null_but_not_registered_as_open")
            else:
                _require(registered not in open_values,
                         f"contract_{section}_{name}_frozen_but_still_listed_as_open")

    # The step magnitudes must agree with the source grid.  snap_to_grid is
    # on, so a step that is not the grid size leaves the agent unable to
    # reach grid points, or silently snapped somewhere else -- either way
    # one route walks differently in different houses.
    route = contract["route"]
    source = contract["source"]
    if route["translation_m"] is not None:
        _require(route["translation_m"] == source["grid_size_m"],
                 "contract_step_does_not_match_the_source_grid")
        _require(route["rotation_degrees"] == source["rotate_step_degrees"],
                 "contract_turn_does_not_match_the_source_rotation")
        _require(route.get("magnitudes_frozen_by") not in (None, ""),
                 "contract_magnitudes_frozen_without_naming_the_ruling")
        for name in ("route.translation_m", "route.rotation_degrees",
                     "route.look_degrees"):
            _require(name not in contract["policy_values_without_defaults"],
                     "contract_magnitude_frozen_but_still_listed_as_open")


    # R1 / I1 rule sections: every constant the planner and selector will
    # read is bound here, so the contract cannot drift from the code.
    rp = contract["route_planning"]
    iw = contract["intervention_window"]
    _require(rp["coverage_definition"] == COVERAGE_DEFINITION, "contract_coverage_changed")
    _require(rp["coverage_is_over_entities_not_space"] is True, "contract_coverage_over_space")
    _require(tuple(rp["viewpoint_distance_m"]) == VIEWPOINT_DISTANCE_M, "contract_viewpoint_distance_changed")
    _require(rp["viewpoint_distance_is_a_search_range_not_a_target"] is True, "contract_viewpoint_range_semantics")
    _require(tuple(rp["viewpoint_pitch_options_degrees"]) == VIEWPOINT_PITCH_OPTIONS, "contract_pitch_options_changed")
    _require(tuple(rp["structure"]) == ROUTE_STRUCTURE, "contract_route_structure_changed")
    _require(rp["path_encoding"] == PATH_ENCODING, "contract_path_encoding_changed")
    _require(rp["no_local_search_after_tour"] is True, "contract_local_search_allowed")
    _require(rp["sweep_two_revisits_source_and_destination_for_move"] is True, "contract_move_revisit_weakened")
    _require(rp["move_revisit_order"] == "seeded_random_per_intervention", "contract_revisit_order_changed")
    _require(rp["reachable_set_written_to_provenance_only"] is True, "contract_reachable_set_leaks")
    _require(rp["route_is_a_pure_function_of_house_and_frozen_parameters"] is True, "contract_route_not_pure")
    sel = contract["intervention_selection"]
    _require(sel["eligible_object"]["observed_in_sweep_one_with_min_visible_pixels"] == MIN_VISIBLE_PIXELS,
             "contract_min_visible_pixels_changed")
    _require(sel["eligible_object"]["receptacle_is_the_first_non_Floor_entry_of_parentReceptacles"] is True,
             "contract_parent_receptacle_rule_weakened")
    _require(sel["eligible_object"]["full_parentReceptacles_list_written_to_provenance_object_table"] is True,
             "contract_parent_list_unrecorded")
    _require(sel["enumerate_then_sample"] is True and sel["sequential_resample_on_failure_forbidden"] is True,
             "contract_sampling_rule_weakened")
    _require(tuple(sel["rng_purpose_tags"]) == RNG_PURPOSE_TAGS, "contract_rng_tags_changed")
    _require(sel["no_new_seed"] is True, "contract_new_seed_allowed")
    _require(sel["add_source"] == ADD_SOURCE, "contract_add_source_changed")
    _require(sel["placement_prescreen_during_enumeration"] is True, "contract_prescreen_dropped")
    _require(sel["remove_executor"] == REMOVE_EXECUTOR, "contract_remove_executor_changed")
    _require(sel["sampling"] == SAMPLING, "contract_sampling_changed")
    pp = sel["placement_prescreen"]
    _require(pp["method"] == PLACEMENT_PRESCREEN, "contract_prescreen_method_changed")
    _require(pp["maximum_points_per_destination"] == DRY_RUN_MAX_POINTS, "contract_dry_run_points_changed")
    _require(pp["destinations_tested_per_object"] == DRY_RUN_DESTINATIONS_PER_OBJECT, "contract_dry_run_destinations_changed")
    _require(pp["feasible_set_size_is_over_tested_pairs_only"] is True, "contract_feasible_set_semantics_changed")
    _require(pp["receipt_records_pairs_tested_pairs_total_and_the_ratio_estimate"] is True, "contract_pairs_unrecorded")
    _require(pp["peek_min_visible_pixels"] == MIN_VISIBLE_PIXELS, "contract_peek_threshold_changed")
    _require(pp["peek_is_a_private_off_route_render_never_captured"] is True, "contract_peek_leaks_to_public")
    _require(pp["one_placement_per_destination_per_episode"] is True, "contract_multi_placement_allowed")
    _require(pp["revert_failure_fails_the_house"] is True, "contract_revert_failure_tolerated")
    _require(sel["unseen_object"]["never_rendered_in_any_private_mask_before_the_window"] is True, "contract_unseen_weakened")
    be = rp["blocked_edge_replanning"]
    _require(be["maximum_replans_per_episode"] == MAX_REPLANS, "contract_max_replans_changed")
    _require(be["blocklist_and_replans_written_to_provenance"] is True, "contract_replans_unrecorded")
    _require(sel["p_null_window"] == P_NULL_WINDOW, "contract_p_null_changed")
    _require(sel["eligible_object"]["pixel_count_frames"] == ELIGIBLE_PIXEL_FRAMES, "contract_eligible_frames_changed")
    _require(sel["unseen_object"]["pixel_count_frames"] == UNSEEN_PIXEL_FRAMES, "contract_unseen_frames_changed")
    _require(sel["null_window_private_salt"]["rule"] == NULL_WINDOW_SALT_RULE, "contract_null_salt_rule_changed")
    _require(sel["null_window_private_salt"]["never_in_the_repository_or_public_plane"] is True, "contract_null_salt_leaks")
    rs = rp["revisit_set"]
    _require(rs["rule"] == REVISIT_SET, "contract_revisit_set_changed")
    _require(rs["controls_equal_in_number_to_intervened_containers"] is True, "contract_control_count_changed")
    _require(rs["controls_drawn_from_U_minus_intervened_first"] is True, "contract_controls_not_from_U")
    _require(rs["control_must_hold_a_seen_eligible_object"] is True, "contract_controls_may_be_empty")
    _require(rs["changed_and_control_interleaved_by_seeded_rng"] is True, "contract_controls_not_interleaved")
    _require(rs["null_episode_rule"] == NULL_EPISODE_RULE, "contract_null_episode_rule_changed")
    _require(rs["controls_outside_U_are_weaker_and_reported_separately"] is True, "contract_control_reporting_dropped")
    _require(iw["container_subject_sealed_from"] == SUBJECT_SEAL_FRAME, "contract_seal_frame_changed")
    _require(iw["minimum_subject_pixels"] == MIN_SUBJECT_PIXELS, "contract_subject_pixels_changed")
    _require(iw["null_window_episode_runs_the_same_pipeline_and_skips_only_execution"] is True, "contract_null_not_twin")
    _require(iw["null_window_episode_fails_under_the_same_rules_and_is_excluded_from_yield"] is True, "contract_null_yield_rule_changed")
    mm = iw["move_minimum"]
    _require(mm["train_moves"] == MOVE_MINIMUM_TRAIN and mm["train_moves_source_first"] == MOVE_MINIMUM_SOURCE_FIRST_TRAIN,
             "contract_move_minimum_changed")
    _require(mm["below_minimum_triggers_a_scale_ruling_not_a_relaxation"] is True, "contract_move_minimum_weakened")
    _require(iw["minimum_window_frames"] == MINIMUM_WINDOW_FRAMES, "contract_min_window_changed")
    _require(iw["window_is_the_whole_transition_segment"] is True, "contract_window_not_whole_transition")
    _require(iw["feasible_set_is_computed_for_the_shared_window"] is True, "contract_feasible_set_not_joint")
    _require(iw["maximum_interventions_per_episode"] == MAXIMUM_INTERVENTIONS_PER_EPISODE, "contract_max_interventions_changed")
    _require(iw["minimum_yield"] == MINIMUM_YIELD, "contract_min_yield_changed")
    _require(contract["route"]["maximum_actions"] == MAXIMUM_ACTIONS, "contract_max_actions_changed")
    _require(contract["route"]["maximum_actions_superseded"]["value"] == MAXIMUM_ACTIONS_SUPERSEDED,
             "contract_max_actions_supersede_changed")
    _require(contract["route"]["maximum_actions_is_a_scope_boundary_not_a_budget"] is True, "contract_max_actions_not_a_scope_boundary")
    _require(contract["route"]["cap_hit_is_a_construction_failure_not_a_truncation"] is True,
             "contract_cap_truncates")

    _require(
        all(value is False for value in contract["authorization"].values()),
        "contract_authorization_must_be_all_false",
    )
    return clone_json(dict(contract))


def check_move_minimum(moves: int, moves_source_first: int, *, is_train_block: bool) -> dict[str, Any]:
    """Judge the dataset-level move minimum (ruling 36).

    白话：数据集里 move 太少，identity_continuity 和 REACTIVATE 就没有统计力。输入是一个
    生成批次里执行成功的 move 数和其中"源先重访"的数目，以及这批是不是 S3-01 的 train
    块；输出是判决表。train 块低于 120／60 记 `below_minimum`，触发规模裁决而不是放宽规则；
    S1 的 50 条只报告数字，不判门。它不改变抽样规则，也不补样。
    """

    result = {"moves": int(moves), "moves_source_first": int(moves_source_first),
              "minimum_train": MOVE_MINIMUM_TRAIN, "minimum_train_source_first": MOVE_MINIMUM_SOURCE_FIRST_TRAIN,
              "gate_applies": bool(is_train_block)}
    if is_train_block:
        result["below_minimum"] = bool(moves < MOVE_MINIMUM_TRAIN or moves_source_first < MOVE_MINIMUM_SOURCE_FIRST_TRAIN)
    else:
        result["below_minimum"] = None
    return result


__all__ = [
    "ACTIONS",
    "ADD_SOURCE",
    "DRY_RUN_DESTINATIONS_PER_OBJECT",
    "DRY_RUN_MAX_POINTS",
    "MAX_REPLANS",
    "PLACEMENT_PRESCREEN",
    "REMOVE_EXECUTOR",
    "SAMPLING",
    "COVERAGE_DEFINITION",
    "ELIGIBLE_PIXEL_FRAMES",
    "MIN_SUBJECT_PIXELS",
    "MOVE_MINIMUM_SOURCE_FIRST_TRAIN",
    "MOVE_MINIMUM_TRAIN",
    "NULL_EPISODE_RULE",
    "NULL_WINDOW_SALT_RULE",
    "REVISIT_SET",
    "SUBJECT_SEAL_FRAME",
    "UNSEEN_PIXEL_FRAMES",
    "check_move_minimum",
    "MAXIMUM_ACTIONS",
    "MAXIMUM_ACTIONS_SUPERSEDED",
    "PRIVATE_HOUSE_GEOMETRY_FIELDS",
    "PRIVATE_HOUSE_GEOMETRY_FILE",
    "MAXIMUM_INTERVENTIONS_PER_EPISODE",
    "MINIMUM_WINDOW_FRAMES",
    "MINIMUM_YIELD",
    "MIN_VISIBLE_PIXELS",
    "PATH_ENCODING",
    "P_NULL_WINDOW",
    "RNG_PURPOSE_TAGS",
    "ROUTE_STRUCTURE",
    "VIEWPOINT_DISTANCE_M",
    "VIEWPOINT_PITCH_OPTIONS",
    "CONTRACT_SCHEMA_VERSION",
    "DEPLOYMENT_READABLE_PLANES",
    "FAILURE_REASONS",
    "FORBIDDEN_PUBLIC_KEYS",
    "INTERVENTION_KINDS",
    "PLANES",
    "PRIVATE_FRAME_FIELDS",
    "PUBLIC_FRAME_FIELDS",
    "SPLIT_PREFIX_ORDER",
    "LeanInterventionError",
    "assert_reader_whitelist",
    "assert_windows_unobservable",
    "assign_split",
    "house_split_rank",
    "summarize_yield",
    "validate_failure_receipt",
    "validate_intervention_data_contract",
    "validate_intervention_plan",
    "validate_public_frame_record",
    "validate_route_plan",
    "validate_split_manifest",
    "validate_three_plane_layout",
]
