"""D-224 / S2-05: read-only node-matching audit of one episode run (evidence for the pending ruling 70).

Usage:
    python ops/vsmt/lean_s2_05_node_audit.py run --cache-root <S1-03 cache root> --episode-root <S1-02 episode dir> \\
        --geometry-root <S1-04 geometry root> --episode-id <id> --arm LOW --config '{"d_low": null}' \\
        --descriptor vitb14 --weights <reid weights> --output-root <audit root> [--frames N]
    python ops/vsmt/lean_s2_05_node_audit.py merge --output-root <audit root> --arm LOW --results <results/*.json>

The ``run`` subcommand replays exactly what the S2-04 entry does (the S2-01 runner over the sealed
cache, the S2-04 teacher labelling every step behind the two-seal gate) and, after every frame,
decomposes the node precision/recall loss of the committed memory under the IoU matching rule
(max-weight matching on 3D IoU >= 0.3, ruling C; the secondary column node_prf1_iou since ruling 72 (B),
whose primary column is the centroid-within-delta rule, re-scored below as centroid_within_0.5m and
checked against the evaluator) and re-scores the same predictions
under alternative rules that a ruling could pick.  It writes one ``node_audit.json`` per episode
and arm; it writes no label, training record, receipt or contract byte and freezes nothing.
``merge`` pools the audits of one arm into a committed ``results/`` report.  No private key
enters either file: truth-side rows are grouped by the ProcTHOR type prefix and by the
pickupable / receptacle / other group only.

白话：这是给"节点 F1 为什么低"找原因的只读审计，不是新指标、不是新规则。输入和 S2-04 入口完全一样
（冻结 cache、S1-02 的 episode 目录、S1-04 几何表、臂与配置），输出每帧把"记忆里的实体"和"范围内在场
的真值物体"各自分类：实体为什么没匹配上（身份含糊、物体已不在、位置对但框太小、物体被另一个实体
占了），真值物体为什么没被匹配（有同身份实体但框太小、同身份实体离得远、只有身份含糊的实体在附近、
根本没有实体——再分从未出过色块与出过色块但丢了）；并把同一批预测按几种备选口径（IoU 0.1、IoU>0、
质心落在真值框内、质心 0.5 m 内、按私有身份并框后的 IoU 0.3 上界）重新计分。例如某帧 48 个实体里
41 个身份含糊、64 个真值物体里 62 个附近没有任何实体，就说明问题主要在记忆而不在匹配口径。它不改
任何合同或数值，产物只用于裁决 70 的讨论；按身份并框的上界用了私有身份，只能作诊断列，不是方法。

v2（裁决 76 (1)(a)）再加三块只读统计与两列：质心主列自己的分类账（"离得远"拆成物体真被搬动、物体没动两类）；
每次 BIRTH 的原因（首次出现、没有承载实体、正确实体没被召回、召回了但 logit 不过新建线——TAF 即余弦低于 θ_a、
合格却在联合分配里输了），用同一个 logit 函数在封存行上重算；每个去重时刻，去重之后剩下的实体对按状态组合
（active／dormant）与私有身份（同物体／不同物体／含糊）在余弦、距离、IoU 各档下能过几对——同物体对是还能收回
的重复，不同物体对是误合并风险；以及两列"先最大匹配数、再最大权"的匹配数。按身份并框那两列只是分组诊断，
同时改了数量与几何，不是上界（LOG-262）。

v3（裁决 79-2／79-3，2026-09-28）再加一块只读统计：每个存在候选（本帧没被匹配、应可见的实体）按八项归档——标签状态、
标签原因、物体的干预类别、窗口阶段（帧号 > window_end 才算窗口后，同评价器）、实体按节点主列规则（裁决 77：质心
≤ δ_moved 或落在真值框外扩 0.25 m 内）是否仍在原处、提交后的记忆里是否另有实体按同一规则承载该物体、本帧该物体
有没有色块、学生的决定（RETRACT／NOOP）。白话：输入是重跑时每帧的旧记忆、标签、学生决定和真值框，输出"撤回正标签和
假撤回各落在什么实体上"。例如沙发表面质心离中心 0.7 m、但在沙发框内，标签是 gone、节点主列却算它在原处，这一格就
是标签与指标的冲突；另有实体承载的那一格是重复实体。它不改任何标签、决定或指标，只计数。

v4（裁决 80-3／80-4，2026-09-28）：每个色块的关联决定按四项归档——teacher 状态（该绑定的 labelled、该新建的
birth、召回漏掉、身份含糊、未标注）、结果（正确、绑错到别的实体、该绑却新建、该新建却绑定）、被选中实体此前
的状态（active／dormant／retracted，新建记 birth）、该物体此前是否出过色块（首次出现与否）。同帧重复色块按
三分解的同组规则判，与 decompose_frame 的 correct／amortization_error 逐帧对得上。白话：输入是每帧旧记忆里各
实体的状态、teacher 目标和学生的分配，输出"关联错在哪儿、错绑到的是休眠还是活动实体"。例如一个首次出现的物体
被绑到一个休眠实体上，就记为"该新建却绑定、dormant、首次出现"。另加诊断开关 --dormancy-override（只用于诊断，
不是登记的臂或配置）：把共享休眠的错失上限换成给定值，取极大值即等于关闭休眠。

v5（裁决 81-3，2026-09-28）：失去承载的事件与此后的缺失时长。一个在场、在节点范围内的物体，上一帧提交后的记忆里
有按节点主列规则（裁决 77）合格的实体承载它，这一帧一个都没有了，就是一次“失去承载”；按它原先各承载实体这一帧
的遭遇归因——被学生绑到别的物体的色块上（误绑定）、被撤回、被去重折叠、被绑到本物体的色块却离开了原处、身份
改变、物体真值位置变了、其他；几个承载实体原因不一记为混合。此后该物体没有合格实体的帧数记在这一段缺失里，
直到重新有合格实体、物体离场或 episode 结束，同一段只归到开启它的那一次事件。白话：输入是逐帧提交前后的记忆、
学生的分配与存在决定、只读真值，输出“哪次操作之后丢了哪个物体、丢了多久”。例如杯子 A 唯一的实体被绑到杯子 B
的色块上，A 随后 100 帧没有实体，就记一次误绑定事件和一段 100 帧的缺失。它不是反事实：拦下这次绑定之后记忆
和分配都会变，不能据此算出“修好就能挽回多少”。

v11（裁决 84-1 (b)，由裁决 100-1 (i) 落地，2026-10-01）：审计按 episode 封印声明的 mask 来源取 ReID 头摘要核对 --weights
（实例分割 5cea91cf…、SAM2 f6fc67e5…；SAM2 封印没有 mask_source 字段即 sam2），--mask-source 给出时须与封印一致；回执记下
mask_source 与权重摘要，合并时一组审计里出现两种来源（或新旧回执混合，旧回执没有这一项）就拒绝。它不改任何审计口径。

v12 起的作业形式（裁决 104-7，2026-10-03）：``run --configs '[{"config": …, "output_root": …}, …]'`` 让一个作业在同一条
episode 上审计同一臂（同一组头）的多个配置——cache 只核验一次，每个配置各自重读几何表与干预日志、各用一个新 teacher 从第一帧
跑闭环、各写各的审计文件（先写临时文件再改名，作业中途停下不会留下看似完成的文件）；``--skip-existing`` 续跑时保留已完成且
episode、臂、配置与模式都对得上的那几份。白话：省掉的是重复核验 cache 与重复启动进程，每个配置的结果与单独跑一次逐字节相同
（测试对拍）。

v12（裁决 104-4 ①，2026-10-03）：``run --metrics-only`` 是 S3 的正式闭环审计——同一个 runner、同一个 teacher、同一份指标
报告，只是不建 NodeAudit、不跑 v2～v10 的诊断块（``audit`` 记 null），也不收任何诊断开关（oracle、覆盖值、残留追踪）。
两种模式的审计文件都新记三样东西：``metrics_only``、teacher 的三分解计数 ``decomposition_totals``（只有计数，没有私有键）、
逐帧封存链摘要 ``trajectory_sha256``（每帧的 tick、阶段 A／B 封存摘要与提交后的记忆摘要连成一串再取 sha256）。``compare``
子命令把同一 episode 的完整审计与 metrics-only 审计逐项对拍（除墙钟时间、提交号、头文件路径、实测耗时与内存、``audit`` 块
与模式标记外全部相等），不同即退出码 3——这是裁决 104-2 的审计等价探针。合并时 metrics-only 与完整审计不混合；
metrics-only 的合并只有逐 episode 报告与三分解计数的合计，选参读数只读逐 episode 的报告。白话：输入与完整审计相同，输出
少了只用于诊断的分类账，指标一个字节都不变；例如 TAF 一条 836 帧的 episode，省下的是按七八种备选口径重新匹配的时间。
它不改指标、标签或任何决定。
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_teacher as lt  # noqa: E402

AUDIT_FILE_NAME = "node_audit.json"
SCHEMA_VERSION = "vsmt-s2-05-node-audit-v12"  # v2: ruling 76 (1)(a) centroid ledger, birth reasons, dedup tallies, count-first columns;
#                                             v3: ruling 79-2 existence-candidate tally; v4: ruling 80-4 association tally;
#                                             v5: ruling 81-3 loss-of-carrier events and absence durations;
#                                             v6: direction B (2026-09-29): folds filed by whether the two records were ever observed in the same frame;
#                                             v7: ruling 86-0 (2026-09-29): every moved object's first labelled re-observation attributed;
#                                             v8: ruling 87-2 (2026-09-29): a kept re-observation also records its carrier's state (dormant or retracted)
#                                             v9: ruling 88-2 (2026-09-29): the teacher-as-policy decision ceiling (--oracle-*), recorded under "oracle"
#                                             v10: ruling 89-1 (2026-09-30): each re-observation records the original carrier's public global cosine
#                                                  rank; --recall-global-count overrides k' for diagnostics, recorded as recall_global_count
#                                             v11: ruling 84-1 (b) under ruling 100-1 (i) (2026-10-01): the ReID head follows the episode's sealed
#                                                  mask source; mask_source and weights_sha256 recorded, a merge never mixes sources
#                                             v12: ruling 104-4 (1) (2026-10-03): --metrics-only (no NodeAudit, audit null); every audit
#                                                  records metrics_only, decomposition_totals and trajectory_sha256; a merge never mixes modes
ACCEPTED_AUDIT_SCHEMAS = ("vsmt-s2-05-node-audit-v8", "vsmt-s2-05-node-audit-v9", "vsmt-s2-05-node-audit-v10",
                          "vsmt-s2-05-node-audit-v11", SCHEMA_VERSION)
MERGED_SCHEMA_VERSION = "vsmt-s2-05-node-audit-merged-v12"
#: Ruling 104-4 (1): what may differ between a full audit and a metrics-only audit of the same run -- wall time, commit, the head
#: file's path, the measured per-frame time and peak memory of S0-04 size_and_cost (measured, never decided on), the diagnostic
#: block itself and the mode flag.  Everything else must be equal (the audit equivalence probe of ruling 104-2).
VOLATILE_AUDIT_KEYS = ("wall_seconds", "code_commit", "heads")
VOLATILE_REPORT_FIELDS = ("runtime_per_frame_s", "peak_memory_bytes")
MODE_KEYS = ("audit", "metrics_only")

#: Why an in-memory prediction (an entity in ``active``/``dormant`` whose object is not a present
#: out-of-scope one) did not match under the IoU 0.3 column (the primary column until ruling 72 (B), secondary since).
ENTITY_CATEGORIES = (
    "matched",
    "identity_ambiguous_unmatched",          # no strict majority over its keyed evidence, and no IoU match either
    "own_object_absent_stale",               # resolves to an object that is no longer present
    "own_object_far_stale_location",         # resolves to a present object but sits more than delta away from it
    "own_object_near_box_too_small",         # within delta of its object, IoU with the truth box below the threshold
    "own_object_taken_by_another_entity",    # IoU with its own object passes, another entity holds the match
)
#: Why a present in-scope truth object was not matched under the IoU 0.3 column (secondary since ruling 72 (B)).
TRUTH_CATEGORIES = (
    "matched",
    "resolved_entity_near_but_box_too_small",  # an entity of its identity within delta, IoU below the threshold
    "resolved_entity_far",                     # entities of its identity exist, all more than delta away
    "only_ambiguous_entity_near",              # no entity of its identity; an ambiguous entity within delta
    "no_entity_fragmented_before",             # no entity near; the object did produce a labelled fragment earlier
    "no_entity_never_fragmented",              # no entity near; the front end never produced a fragment of it
)
#: Alternative scorings of the same predictions and truth objects, each with the evaluator's matcher.
RULES = (
    "iou_0.3_secondary",
    "iou_0.1",
    "iou_positive",
    "centroid_inside_truth_box_padded_0.25m",
    "centroid_within_0.5m",
    "oracle_identity_groups_iou_0.3",
    "oracle_identity_groups_centroid_within_0.5m",
    # ruling 76 (1)(a): the same two columns under the count-first objective (most matches, then most weight);
    # since ruling 76 (3)(a) these two reproduce the evaluator and the plain two above keep the earlier max-weight objective
    "centroid_within_0.5m_count_first",
    "iou_0.3_count_first",
    # metric candidates for the pending node-metric ruling (read-only): large objects whose visible surface centroid sits
    # more than 0.5 m from the whole-box centre, and a pair that must also be the entity's own object
    "centroid_0.5m_or_in_box_0.25m_count_first",
    "identity_centroid_0.5m_count_first",
    "identity_centroid_0.5m_or_in_box_0.25m_count_first",
)
PAD_M = 0.25
CENTROID_RADIUS_M = 0.5

#: Ruling 76 (1)(a): why an in-memory prediction did not match under the primary centroid column.
CENTROID_ENTITY_CATEGORIES = (
    "matched",
    "identity_ambiguous_unmatched",
    "own_object_absent",                       # resolves to an object no longer present
    "own_object_far_object_moved",             # more than delta from its object, which moved more than delta since the entity last saw it
    "own_object_far_object_not_moved",         # more than delta from its object, which has not moved: surface centroid off the box centre, or a wrong bind
    "own_object_near_unmatched",               # within delta of its object, another entity (or the matcher) took the match
)
#: Ruling 76 (1)(a): why a present in-scope truth object was not matched under the primary centroid column.
CENTROID_TRUTH_CATEGORIES = (
    "matched",
    "resolved_entity_near_unmatched",
    "resolved_entity_far",
    "only_ambiguous_entity_near",
    "no_entity_fragmented_before",
    "no_entity_never_fragmented",
)
#: Ruling 76 (1)(a): why a fragment was born, from the sealed stage-A rows and the arm's own logits.
BIRTH_REASONS = (
    "unlabelled_fragment",                 # the fragment has no dominant private object
    "first_labelled_observation",          # no earlier fragment of this object
    "no_resolved_carrier",                 # the object was fragmented before, but no entity resolves to it now
    "correct_carrier_not_recalled",        # an entity resolves to it but is not among the sealed candidates
    "correct_carrier_below_birth_logit",   # recalled, but its association logit does not beat the birth logit (TAF: cosine below theta_a)
    "correct_carrier_lost_joint_competition",  # recalled and eligible, the joint solve still chose birth
)
#: Ruling 76 (1)(a): the dedup gate values tallied over entity pairs at every dedup tick (the frozen ones are 0.8 / 0.5 / 0.05).
DEDUP_COSINES = (0.5, 0.6, 0.7, 0.8, 0.9)
DEDUP_DISTANCES_M = (0.25, 0.5, 1.0)
DEDUP_IOUS = (0.0, 0.05, 0.1)
DEDUP_STATE_PAIRS = ("active_active", "active_dormant", "dormant_dormant")
DEDUP_IDENTITIES = ("same_object", "different_objects", "ambiguous")
#: v6: a fold whose two records both hold evidence from one and the same tick joined two entities that were observed
#: side by side in one frame -- with instance masks two fragments of one frame are two objects, so such a fold is a
#: wrong merge by construction; "never_co_observed" folds are the ones a co-observation veto would still allow
FOLD_COOBSERVATION = ("co_observed", "never_co_observed")
#: v7 (ruling 86-0): why a moved object's first labelled re-observation did or did not keep a pre-move entity id; the
#: categories follow the decision pipeline and are mutually exclusive (first that applies)
REOBSERVATION_CATEGORIES = ("kept", "carrier_gone", "carrier_not_recalled", "chose_birth", "chose_other_entity", "no_prior_carrier")
NO_PRIOR_REASONS = ("never_fragmented_before_move", "no_resolving_entity_at_move")
#: Ruling 79-2: the fields of one existence-candidate tally row (the count follows them).
EXISTENCE_TALLY_FIELDS = (
    "status", "reason", "object_class", "phase",
    "entity_in_place_node_rule",            # yes / no / object_absent / out_of_scope / n/a (identity ambiguous)
    "another_entity_carries_the_object",    # on the committed memory, by the node rule; same values
    "fragment_of_the_object_this_frame",    # yes / no / n/a
    "decision",                             # RETRACT / NOOP
)
#: Ruling 81-3: why an object lost its last qualifying carrier, judged per former carrier (one cause, or mixed).
LOSS_CAUSES = (
    "wrong_bind",                  # the carrier took a fragment of another object this frame
    "bound_unlabelled_fragment",   # the carrier took a fragment without a dominant private object
    "own_bind_off_place",          # the carrier took a fragment of its own object and left the place/box
    "retract",                     # the student retracted the carrier
    "folded",                      # the shared dedup folded the carrier into another record
    "fold_survivor_changed",       # the carrier survived a fold and took the other record's geometry or evidence
    "removed",                     # the carrier is gone from memory for another reason
    "identity_changed",            # the carrier no longer resolves to the object (no bind, no fold)
    "object_truth_changed",        # the object's truth centroid changed while the carrier stayed
    "other",
    "mixed_with_wrong_bind",       # several former carriers, different causes, one of them a wrong bind
    "mixed",
)
LOSS_DURATION_BINS = ((1, "1"), (5, "2-5"), (20, "6-20"), (100, "21-100"), (500, "101-500"), (None, ">500"))
LOSS_RULE = ("a present in-scope object whose qualifying carriers (node primary rule, ruling 77) on the previous frame's committed memory "
             "are all gone from this frame's committed memory loses its carrier; the absence interval counts the following in-scope "
             "frames without a qualifying carrier until one returns, the object leaves or the episode ends; one interval per loss")
#: Ruling 80-4: the fields of one association tally row (the count follows them).
ASSOCIATION_TALLY_FIELDS = (
    "target_status",       # labelled / birth / recall_miss / identity_ambiguous / unlabelled / duplicate_of_labelled
    "outcome",             # correct / wrong_bind / birth_instead_of_bind / bind_instead_of_birth / bind / birth / grouped
    "chosen_state",        # the state before the frame of the entity the outcome names (active / dormant / retracted), or birth
    "first_observation",   # yes / no: no fragment of this object before this frame; n/a without a key
)


def _count_first(weights: Sequence[Sequence[float]]) -> int:
    """Matches under the count-first objective (ruling 76 (3)(a), the evaluator's own since then)."""

    if not weights or not weights[0]:
        return 0
    return len(lt._max_weight_matching(weights, count_first=True))


class NodeAuditError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise NodeAuditError(code)


_distance = lt._distance  # the evaluator's own distance, so the centroid rule reproduces its column bit for bit


def _inside_padded(point: Sequence[float], lower: Sequence[float], upper: Sequence[float], pad: float) -> bool:
    return all(float(lo) - pad <= float(p) <= float(hi) + pad for p, lo, hi in zip(point, lower, upper, strict=True))


def _union(boxes: Sequence[tuple[Sequence[float], Sequence[float]]]) -> tuple[list[float], list[float]]:
    lower = [min(float(b[0][axis]) for b in boxes) for axis in range(3)]
    upper = [max(float(b[1][axis]) for b in boxes) for axis in range(3)]
    return lower, upper


def _prf(matched: int, predicted: int, truth: int) -> dict[str, Any]:
    precision = matched / predicted if predicted else None
    recall = matched / truth if truth else None
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0.0:
        f1 = 0.0
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
    return {"matched": matched, "predicted": predicted, "truth": truth, "precision": precision, "recall": recall, "f1": f1}


def object_groups(geometry_table: Mapping[str, Any]) -> dict[str, str]:
    """pickupable / receptacle / other per private key, from the S1-04 geometry table rows."""

    groups: dict[str, str] = {}
    for row in geometry_table["objects"]:
        groups[str(row["object_id"])] = "pickupable" if row.get("pickupable") else ("receptacle" if row.get("receptacle") else "other")
    return groups


def trajectory_sha256(receipts: Sequence[Mapping[str, Any]]) -> str:
    """Ruling 104-4 (1): one digest of the run's per-frame seal chain (tick, both stage seals, the committed memory digest)."""

    chain = [[int(r["tick"]), str(r["stage_a_seal_sha256"]), str(r["stage_b_seal_sha256"]), str(r["memory_digest_after"])] for r in receipts]
    return hashlib.sha256(json.dumps(chain, separators=(",", ":")).encode("utf-8")).hexdigest()


def comparable_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    """An audit without what may differ between a full and a metrics-only audit of the same run (ruling 104-4 (1))."""

    out = {key: value for key, value in payload.items() if key not in VOLATILE_AUDIT_KEYS + MODE_KEYS}
    report = dict(out.get("report") or {})
    if "size_and_cost" in report:
        report["size_and_cost"] = {k: v for k, v in report["size_and_cost"].items() if k not in VOLATILE_REPORT_FIELDS}
    out["report"] = report
    return out


def compare_audits(full: Mapping[str, Any], metrics_only: Mapping[str, Any]) -> dict[str, Any]:
    """Ruling 104-2 audit equivalence probe: a full audit and a metrics-only audit of one episode, field by field."""

    _require(not full.get("metrics_only") and full.get("audit") is not None, "compare_needs_a_full_audit")
    _require(bool(metrics_only.get("metrics_only")) and metrics_only.get("audit") is None, "compare_needs_a_metrics_only_audit")
    left, right = comparable_metrics(full), comparable_metrics(metrics_only)
    differing = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
    return {"episode_id": metrics_only.get("episode_id"), "arm": metrics_only.get("arm"), "identical": not differing,
            "differing_fields": differing, "compared_fields": sorted(set(left) | set(right)),
            "excluded": {"keys": list(VOLATILE_AUDIT_KEYS + MODE_KEYS), "size_and_cost": list(VOLATILE_REPORT_FIELDS)}}


def capture_truth_table(teacher: Any) -> dict[str, Any]:
    """Make the teacher's truth-table builder hand back the table it built for the latest frame.

    The wrapper returns the builder's own table unchanged; the teacher's behaviour is not altered.
    """

    captured: dict[str, Any] = {}
    original: Callable[..., dict[str, dict[str, Any]]] = teacher.builder.update

    def capturing_update(private_record: Mapping[str, Any], tracker_truth: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        table = original(private_record, tracker_truth)
        captured["table"] = table
        return table

    teacher.builder.update = capturing_update
    return captured


def capture_dedup_folds() -> list[dict[str, Any]]:
    """Ruling 76 (1)(a): record the two records of every shared-dedup fold as they were just before it.

    The wrapper calls the shared maintenance function unchanged and returns its result; it only keeps, per
    fold, the two records' states and evidence so the audit can file the fold by private identity once the
    teacher has labelled the frame.  Nothing reaches the method.
    """

    from vsmt import lean_memory as lm

    captured: list[dict[str, Any]] = []
    original = lm._apply_dedup
    if getattr(original, "_audit_wrapper", False):
        original = original._audit_original  # type: ignore[attr-defined]

    def capturing(memory: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        before = {str(e["entity_id"]): {"state": e["state"], "evidence": [dict(item) for item in e["evidence"]], "supported_by": e.get("supported_by")}
                  for e in memory["entities"]}
        changes = original(memory, **kwargs)
        for change in changes:
            captured.append({"canonical": before[str(change["canonical_entity_id"])], "folded": before[str(change["folded_entity_id"])],
                             "canonical_id": str(change["canonical_entity_id"]), "folded_id": str(change["folded_entity_id"])})
        return changes

    capturing._audit_wrapper = True  # type: ignore[attr-defined]
    capturing._audit_original = original  # type: ignore[attr-defined]
    lm._apply_dedup = capturing
    return captured


def attribute_reobservation(
    *, key: str, carriers: Sequence[str], states: Mapping[str, str], identities: Mapping[str, Mapping[str, Any]],
    recall: Sequence[str], chosen: str, target: Mapping[str, Any], association_logits: Mapping[str, float] | None,
    birth_logit: float | None, distances: Mapping[str, float], fragment_id: str, fragmented_at_move: set[str] | None,
    ever_retracted: set[str], folded_ids: set[str], deleted_ids: set[str],
) -> dict[str, Any]:
    """v7 (ruling 86-0): one moved object's first labelled re-observation, filed by where the pre-move identity was lost.

    白话：输入一个被搬动物体搬动后第一次带标签重见的那一帧——搬动前承载它的实体（窗口末帧按证据多数票认定，和身份连续率的
    分母同一口径）、这一帧之前的记忆状态、该色块的召回列表、学生的实际选择、teacher 的目标与各格 logit——输出这次重见接没接回
    原编号，以及没接回时卡在哪一步：原实体已不在记忆里（被合并掉或被 NoVersion 删除）、原实体在但没进召回、进了召回但学生选了新建、
    进了召回但学生选了别的实体；搬动前根本没有承载实体的，再分“搬动前从没出过色块”和“出过但没有实体按多数票认它”。例如杯子搬动前由
    实体 A 承载，A 在窗口里被错撤成 retracted，重见时 A 进了召回、学生却选了新建，就记 chose_birth、原实体状态 retracted、曾被撤回。
    它只读，不改任何决定；判定“接回”与评价器的身份连续率完全相同（选中的列属于搬动前承载实体之一）。
    """

    from vsmt import lean_assignment as la

    carrier_ids = [str(c) for c in carriers]
    is_birth = str(chosen).startswith(la.BIRTH_COLUMN_PREFIX)
    if is_birth:
        chosen_kind = "birth"
    elif chosen in carrier_ids:
        chosen_kind = "carrier"
    else:
        chosen_kind = f"other_{states.get(chosen, 'unknown')}"
    status = str(target.get("status"))
    wanted = target.get("target")
    if status in ("labelled", "birth") and wanted is not None:
        wanted = str(wanted)
        teacher_kind = "birth" if wanted.startswith(la.BIRTH_COLUMN_PREFIX) else ("carrier" if wanted in carrier_ids else "other_entity")
    else:
        teacher_kind = status
    record: dict[str, Any] = {"judged": bool(carrier_ids), "chosen_kind": chosen_kind, "teacher_status": status, "teacher_target_kind": teacher_kind,
                              "carriers": len(carrier_ids),
                              # v8 (ruling 87-2): the state of the carrier a kept re-observation went back to -- BIND to an active one,
                              # REACTIVATE of a dormant one (NoVersion keeps those) or of a retracted one (only a versioned memory can)
                              "chosen_carrier_state": states.get(chosen) if chosen in carrier_ids else None}
    if not carrier_ids:
        record["category"] = "no_prior_carrier"
        record["no_prior_reason"] = ("never_fragmented_before_move" if fragmented_at_move is not None and key not in fragmented_at_move
                                     else "no_resolving_entity_at_move")
        return record
    present = [c for c in carrier_ids if c in states]
    gone = [c for c in carrier_ids if c not in states]
    recall_set = {str(e) for e in recall}
    recalled = [c for c in present if c in recall_set]
    resolving = [c for c in present if (identities.get(c) or {}).get("resolvable") and (identities.get(c) or {}).get("key") == key]
    record.update({
        "carriers_present": len(present), "carriers_recalled": len(recalled), "carriers_still_resolving": len(resolving),
        "carrier_states": sorted({states[c] for c in present}),
        "carriers_gone_by": sorted({"folded" if c in folded_ids else ("deleted" if c in deleted_ids else "unknown") for c in gone}),
        "carrier_ever_retracted": any(c in ever_retracted for c in carrier_ids),
    })
    if chosen in carrier_ids:
        category = "kept"
    elif not present:
        category = "carrier_gone"
    elif not recalled:
        category = "carrier_not_recalled"
    elif is_birth:
        category = "chose_birth"
    else:
        category = "chose_other_entity"
    record["category"] = category
    if recalled:
        logit_of = (lambda c: float(association_logits[f"{fragment_id}|{c}"])) if association_logits is not None else None
        best = max(recalled, key=logit_of) if logit_of is not None else recalled[0]
        record["best_carrier_state"] = states[best]
        record["best_carrier_distance_m"] = distances.get(best)
        if logit_of is not None:
            chosen_logit = birth_logit if is_birth else association_logits.get(f"{fragment_id}|{chosen}")
            record["best_carrier_logit"] = logit_of(best)
            record["chosen_minus_best_carrier_logit"] = (None if chosen_logit is None else float(chosen_logit) - logit_of(best))
    return record


def original_carrier_global_rank(memory: Mapping[str, Any], view: Mapping[str, Any], *, fragment_id: str,
                                 carriers: Sequence[str]) -> dict[str, Any]:
    """v10 (ruling 89-1): the public rank of the original carrier in the recall's global cosine ordering (read-only).

    白话：输入重见那一帧之前的记忆、这一帧的公开视图（投影后的描述子）、色块和搬动前的承载实体，输出“原实体”（仍在记忆里的承载实体中
    首版本最早的那个）在“这个色块对全部实体的余弦从高到低、并列按实体 ID”排序里的名次（从 1 起）和记忆里的实体数。排序键与 S0-03 召回
    的全局通道逐位相同（``cosine_matrix`` 与 ``recall_for_fragment`` 的 ``everywhere`` 排序），所以名次 ≤ k′ 就等于全局通道会召回它。
    例如名次 4 说明 k′ 从 3 加到 4 就能召回。它只读，不改召回、不改决定；私有身份只用来指出哪个实体是原实体，名次本身是公开量。
    """

    from vsmt import lean_assignment as la

    present = {str(e["entity_id"]): e for e in memory["entities"]}
    alive = [present[str(c)] for c in carriers if str(c) in present]
    if not alive:
        return {"original_carrier_global_rank": None, "entities_in_memory": len(present)}
    original = sorted(alive, key=lambda e: (int(e["versions"][0]["opened_at"]), str(e["entity_id"])))[0]
    fragment = next(f for f in view["fragments"] if str(f["fragment_id"]) == str(fragment_id))
    ids = [str(e["entity_id"]) for e in memory["entities"]]
    row = la.cosine_matrix([fragment["descriptor"]], [e["descriptor_mean"] for e in memory["entities"]])[0]
    ordered = [entity_id for _, entity_id in sorted(zip(row, ids), key=lambda item: (-item[0], item[1]))]
    return {"original_carrier_global_rank": ordered.index(str(original["entity_id"])) + 1, "entities_in_memory": len(ids)}


def fold_coobservation(fold: Mapping[str, Any]) -> str:
    """v6: whether the two records of a captured fold share an evidence tick (were observed in the same frame)."""

    left = {int(item["tick"]) for item in fold["canonical"]["evidence"]}
    right = {int(item["tick"]) for item in fold["folded"]["evidence"]}
    return "co_observed" if left & right else "never_co_observed"


class NodeAudit:
    """Per-frame loss decomposition and alternative scorings over one episode run."""

    def __init__(self, *, evidence: Mapping[str, str | None], iou_min: float, delta_moved_m: float,
                 groups: Mapping[str, str] | None = None, arm: str | None = None, config: Mapping[str, Any] | None = None,
                 scorer: Any = None, dedup: Mapping[str, Any] | None = None,
                 interventions: Mapping[str, str] | None = None, window_end: int | None = None,
                 carriers_before_move: Mapping[str, Sequence[str]] | None = None) -> None:
        self.evidence = evidence
        # v7 (ruling 86-0): the evaluator's own carriers-before-move map (a live reference, filled at the window end),
        # each intervention's ordinal (the only object handle that leaves the audit), and the lifecycle history
        self.carriers_before_move = carriers_before_move
        self.intervention_ordinal = {key: index for index, key in enumerate(dict(interventions or {}))}
        self.fragmented_at_move: set[str] | None = None
        self.ever_retracted: set[str] = set()
        self.folded_ids: set[str] = set()
        self.deleted_ids: set[str] = set()
        self.identity_attribution: list[dict[str, Any]] = []
        # ruling 79-2: the existence-candidate tally needs each object's executed intervention and the window end
        self.interventions = dict(interventions or {})
        self.window_end = None if window_end is None else int(window_end)
        self.existence_tally: dict[tuple[str, ...], int] = {}
        self.association_tally: dict[tuple[str, ...], int] = {}  # ruling 80-4
        # ruling 81-3: carriers of the previous frame, open absence intervals, events and closed intervals
        self.loss_prev_carriers: dict[str, set[str]] | None = None
        self.loss_prev_truth: dict[str, list[float]] = {}
        self.loss_open: dict[str, dict[str, Any]] = {}
        self.loss_events: dict[tuple[str, str], int] = {}
        self.loss_intervals: dict[str, dict[str, Any]] = {}
        self.uncarried_seen_frames = 0
        self.uncarried_without_event_frames = 0
        # ruling 76 (1)(a): the birth reasons need the arm's logits, the dedup tallies the frozen period
        self.arm = arm
        self.config = dict(config) if config is not None else None
        self.scorer = scorer
        self.dedup_period = int(dedup["period_ticks"]) if dedup else None
        self.centroid_entity_counts = {name: 0 for name in CENTROID_ENTITY_CATEGORIES}
        self.centroid_truth_counts = {name: 0 for name in CENTROID_TRUTH_CATEGORIES}
        self.birth_reasons = {scope: {name: 0 for name in BIRTH_REASONS} for scope in ("in_scope_object", "other")}
        self.dedup_ticks = 0
        self.dedup_folds = 0
        self.dedup_pairs = {f"{states}|{identity}": {"pairs": 0, "pass": {}} for states in DEDUP_STATE_PAIRS for identity in DEDUP_IDENTITIES}
        self.truth_centroid_changes: dict[str, list[tuple[int, list[float]]]] = {}
        self.fold_capture: list[dict[str, Any]] | None = None  # set by run(): capture_dedup_folds()
        self.folds_by_identity = {f"{states}|{identity}": 0 for states in DEDUP_STATE_PAIRS for identity in DEDUP_IDENTITIES}
        self.folds_by_coobservation = {f"{identity}|{co}": 0 for identity in DEDUP_IDENTITIES for co in FOLD_COOBSERVATION}
        self.iou_min = float(iou_min)
        self.delta = float(delta_moved_m)
        self.groups = dict(groups or {})
        self.frames = 0
        self.entity_counts = {name: 0 for name in ENTITY_CATEGORIES}
        self.truth_counts = {name: 0 for name in TRUTH_CATEGORIES}
        self.rule_sums = {rule: {"matched": 0, "predicted": 0, "truth": 0} for rule in RULES}
        self.wrong_identity_matches = {rule: 0 for rule in RULES if rule.endswith("_count_first")}
        self.rule_matched_per_frame: dict[str, list[int]] = {rule: [] for rule in RULES}
        self.by_type: dict[str, dict[str, int]] = {}
        self.by_group: dict[str, dict[str, int]] = {}
        self.keys_fragmented: set[str] = set()
        self.in_memory_per_frame: list[int] = []
        self.out_of_scope_per_frame: list[int] = []
        self.own_iou_near_values: list[float] = []   # IoU of a resolved entity within delta of its present object
        self.own_distance_values: list[float] = []   # centroid distance of a resolved entity to its present object

    # -- one frame --------------------------------------------------------------

    def observe(self, step: Mapping[str, Any], labelled: Mapping[str, Any], truth_table: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        memory_after = step["state"]["memory"]
        self._keys_before_frame = set(self.keys_fragmented)  # ruling 76 (1)(a): "first observation" means before this frame
        for target in labelled["targets"].values():
            if target.get("key") is not None:
                self.keys_fragmented.add(str(target["key"]))
        frame_eval = lt.evaluate_frame(memory_after, truth_objects=truth_table, evidence_instance=self.evidence,
                                       iou_min=self.iou_min, delta_moved_m=self.delta)
        for name in lt.METRIC_FIELDS["node_prf1"]:
            _require(frame_eval[name] == labelled["node_prf1"][name], f"audit_disagrees_with_the_labels:{name}")
        identities = lt.entity_identities(memory_after, self.evidence)
        out_of_scope = set(frame_eval["out_of_scope_entities"])
        in_memory = [e for e in memory_after["entities"] if e["state"] in lt.MEMORY_PRESENT_STATES]
        predictions = [e for e in in_memory if str(e["entity_id"]) not in out_of_scope]
        present_keys = [key for key in sorted(truth_table) if truth_table[key]["present"] and truth_table[key]["in_scope"]]
        _require(len(predictions) == frame_eval["predicted"] and len(present_keys) == frame_eval["truth"], "audit_prediction_sets_differ")
        # the categories decompose the IoU 0.3 column's loss ("box too small" only means something there)
        matched_entity = {entity_id: key for entity_id, key in frame_eval["iou_matched_pairs"]}
        matched_keys = set(matched_entity.values())
        boxes = {key: (truth_table[key]["aabb_min_m"], truth_table[key]["aabb_max_m"], truth_table[key]["centroid_m"]) for key in present_keys}

        # matrices over predictions x present keys
        iou_rows: list[list[float]] = []
        dist_rows: list[list[float]] = []
        inside_rows: list[list[bool]] = []
        for entity in predictions:
            iou_rows.append([lt._aabb_iou(entity["aabb_min_m"], entity["aabb_max_m"], boxes[key][0], boxes[key][1]) for key in present_keys])
            dist_rows.append([_distance(entity["centroid_m"], boxes[key][2]) for key in present_keys])
            inside_rows.append([_inside_padded(entity["centroid_m"], boxes[key][0], boxes[key][1], PAD_M) for key in present_keys])
        column_of = {key: index for index, key in enumerate(present_keys)}

        # entity-side categories
        resolving: dict[str, list[int]] = {key: [] for key in present_keys}
        ambiguous_rows: list[int] = []
        frame_entity = {name: 0 for name in ENTITY_CATEGORIES}
        for row, entity in enumerate(predictions):
            entity_id = str(entity["entity_id"])
            identity = identities[entity_id]
            if entity_id in matched_entity:
                category = "matched"
                if identity["resolvable"] and identity["key"] in resolving:
                    resolving[identity["key"]].append(row)
                elif not identity["resolvable"]:
                    ambiguous_rows.append(row)
            elif not identity["resolvable"]:
                category = "identity_ambiguous_unmatched"
                ambiguous_rows.append(row)
            else:
                key = identity["key"]
                if key not in column_of:  # present out-of-scope objects were filtered; only absent ones remain
                    _require(truth_table[key]["present"] is not True, f"audit_unexpected_key_state:{key}")
                    category = "own_object_absent_stale"
                else:
                    resolving[key].append(row)
                    column = column_of[key]
                    own_iou, own_distance = iou_rows[row][column], dist_rows[row][column]
                    self.own_distance_values.append(own_distance)
                    if own_iou >= self.iou_min:
                        category = "own_object_taken_by_another_entity"
                    elif own_distance <= self.delta:
                        category = "own_object_near_box_too_small"
                        self.own_iou_near_values.append(own_iou)
                    else:
                        category = "own_object_far_stale_location"
            frame_entity[category] += 1
        # truth-side categories
        frame_truth = {name: 0 for name in TRUTH_CATEGORIES}
        for key in present_keys:
            column = column_of[key]
            if key in matched_keys:
                category = "matched"
            elif resolving[key]:
                near = any(dist_rows[row][column] <= self.delta for row in resolving[key])
                category = "resolved_entity_near_but_box_too_small" if near else "resolved_entity_far"
            elif any(dist_rows[row][column] <= self.delta for row in ambiguous_rows):
                category = "only_ambiguous_entity_near"
            elif key in self.keys_fragmented:
                category = "no_entity_fragmented_before"
            else:
                category = "no_entity_never_fragmented"
            frame_truth[category] += 1
            type_row = self.by_type.setdefault(lt.structural_type_of(key), {name: 0 for name in TRUTH_CATEGORIES})
            type_row[category] += 1
            group_row = self.by_group.setdefault(self.groups.get(key, "other"), {name: 0 for name in TRUTH_CATEGORIES})
            group_row[category] += 1

        # alternative rules on the same predictions
        rule_matched: dict[str, int] = {}
        rule_predicted: dict[str, int] = {}
        threshold = self.iou_min
        weights_by_rule = {
            "iou_0.3_secondary": [[v if v >= threshold else 0.0 for v in row] for row in iou_rows],
            "iou_0.1": [[v if v >= 0.1 else 0.0 for v in row] for row in iou_rows],
            "iou_positive": [[v if v > 0.0 else 0.0 for v in row] for row in iou_rows],
            "centroid_inside_truth_box_padded_0.25m": [[(1.0 / (1.0 + d)) if inside else 0.0 for d, inside in zip(drow, irow, strict=True)]
                                                       for drow, irow in zip(dist_rows, inside_rows, strict=True)],
            # = the primary column node_prf1 since ruling 72 (B) (delta_moved_m is the frozen 0.5 m); checked against the evaluator below
            "centroid_within_0.5m": [[(1.0 / (1.0 + d)) if d <= self.delta else 0.0 for d in row] for row in dist_rows],
        }
        # oracle grouping by private identity: one union box per resolved key, ambiguous entities stay single
        groups: dict[str, list[int]] = {}
        for row, entity in enumerate(predictions):
            identity = identities[str(entity["entity_id"])]
            name = f"key:{identity['key']}" if identity["resolvable"] else f"entity:{entity['entity_id']}"
            groups.setdefault(name, []).append(row)
        group_iou: list[list[float]] = []
        group_dist: list[list[float]] = []
        for rows in groups.values():
            lower, upper = _union([(predictions[r]["aabb_min_m"], predictions[r]["aabb_max_m"]) for r in rows])
            centre = [(a + b) / 2.0 for a, b in zip(lower, upper, strict=True)]
            group_iou.append([lt._aabb_iou(lower, upper, boxes[key][0], boxes[key][1]) for key in present_keys])
            group_dist.append([_distance(centre, boxes[key][2]) for key in present_keys])
        weights_by_rule["oracle_identity_groups_iou_0.3"] = [[v if v >= threshold else 0.0 for v in row] for row in group_iou]
        weights_by_rule["oracle_identity_groups_centroid_within_0.5m"] = [[(1.0 / (1.0 + d)) if d <= CENTROID_RADIUS_M else 0.0 for d in row]
                                                                          for row in group_dist]
        weights_by_rule["centroid_within_0.5m_count_first"] = weights_by_rule["centroid_within_0.5m"]
        weights_by_rule["iou_0.3_count_first"] = weights_by_rule["iou_0.3_secondary"]
        own = [[bool(identities[str(entity["entity_id"])]["resolvable"]) and identities[str(entity["entity_id"])]["key"] == key
                for key in present_keys] for entity in predictions]
        place_or_box = [[(1.0 / (1.0 + d)) if (d <= self.delta or inside) else 0.0 for d, inside in zip(drow, irow, strict=True)]
                        for drow, irow in zip(dist_rows, inside_rows, strict=True)]
        weights_by_rule["centroid_0.5m_or_in_box_0.25m_count_first"] = place_or_box
        weights_by_rule["identity_centroid_0.5m_count_first"] = [[w if ok else 0.0 for w, ok in zip(wrow, orow, strict=True)]
                                                                 for wrow, orow in zip(weights_by_rule["centroid_within_0.5m"], own, strict=True)]
        weights_by_rule["identity_centroid_0.5m_or_in_box_0.25m_count_first"] = [[w if ok else 0.0 for w, ok in zip(wrow, orow, strict=True)]
                                                                                 for wrow, orow in zip(place_or_box, own, strict=True)]
        for rule in RULES:
            weights = weights_by_rule[rule]
            if rule.endswith("_count_first"):
                pairs = lt._max_weight_matching(weights, count_first=True) if weights and present_keys else []
                matched = len(pairs)
                self.wrong_identity_matches[rule] += sum(1 for row, column in pairs if not own[row][column])
            else:
                matched = len(lt._max_weight_matching(weights)) if weights and present_keys else 0
            rule_matched[rule] = matched
            rule_predicted[rule] = len(weights)
            sums = self.rule_sums[rule]
            sums["matched"] += matched
            sums["predicted"] += len(weights)
            sums["truth"] += len(present_keys)
            self.rule_matched_per_frame[rule].append(matched)
        # ruling 76 (3)(a): the evaluator matches count-first; the plain two columns keep the earlier max-weight objective
        _require(rule_matched["iou_0.3_count_first"] == frame_eval["node_prf1_iou"]["matched"],
                 "audit_iou_rule_does_not_reproduce_the_evaluator")
        # ruling 72 (B): the centroid rule is the primary column node_prf1
        # ruling 77 (1)(a): the primary column is the own-object-and-place candidate
        _require(rule_matched["identity_centroid_0.5m_or_in_box_0.25m_count_first"] == frame_eval["matched"],
                 "audit_centroid_rule_does_not_reproduce_the_evaluator")

        # ruling 76 (1)(a): the primary centroid column's own ledger, the birth reasons and the dedup pair tallies
        tick = int(memory_after["tick"])
        centroid_ledger = self._centroid_ledger(frame_eval, predictions, identities, present_keys, dist_rows, column_of, truth_table, tick)
        if self.arm is not None:
            self._birth_reasons(step, labelled, truth_table)
        if self.dedup_period is not None and tick % self.dedup_period == 0:
            self._dedup_pairs(memory_after, identities)
        folds = [(str(f.get("canonical_id")), str(f.get("folded_id"))) for f in (self.fold_capture or [])]  # ruling 81-3, before filing
        if self.fold_capture is not None:
            self._file_folds()
        self._tally_existence(step, labelled, truth_table, predictions, identities)
        self._tally_association(step, labelled)
        self._tally_losses(step, labelled, truth_table, predictions, identities, folds)
        # v7 (ruling 86-0): attribute first re-observations on the memory before this frame, then record this frame's history
        if self.window_end is not None and int(labelled["frame_index"]) == self.window_end:
            self.fragmented_at_move = set(self.keys_fragmented)
        self._attribute_reobservations(step, labelled)
        for op in (step["receipt"].get("program") or {}).get("operations") or []:
            if op.get("atom") == "RETRACT":
                self.ever_retracted.add(str(op["entity_id"]))
        self.folded_ids.update(folded for _, folded in folds)
        self.deleted_ids.update(str(e) for e in step["receipt"].get("no_version_deleted") or [])

        for name, count in frame_entity.items():
            self.entity_counts[name] += count
        for name, count in frame_truth.items():
            self.truth_counts[name] += count
        self.frames += 1
        self.in_memory_per_frame.append(len(in_memory))
        self.out_of_scope_per_frame.append(len(out_of_scope))
        return {"frame_index": labelled["frame_index"], "entity": frame_entity, "truth": frame_truth,
                "centroid_entity": centroid_ledger["entity"], "centroid_truth": centroid_ledger["truth"],
                "rules": {rule: {"matched": rule_matched[rule], "predicted": rule_predicted[rule], "truth": len(present_keys)} for rule in RULES}}

    # -- ruling 79-2 -------------------------------------------------------------

    def _in_place(self, centroid: Sequence[float], record: Mapping[str, Any]) -> bool:
        """The node primary column's place test (ruling 77 (1)(a)): within delta of the centre, or inside the padded box."""

        if _distance(centroid, record["centroid_m"]) <= self.delta:
            return True
        lower, upper = record.get("aabb_min_m"), record.get("aabb_max_m")
        return lower is not None and upper is not None and _inside_padded(centroid, lower, upper, PAD_M)

    def _tally_existence(self, step: Mapping[str, Any], labelled: Mapping[str, Any], truth_table: Mapping[str, Mapping[str, Any]],
                         predictions: Sequence[Mapping[str, Any]], identities: Mapping[str, Mapping[str, Any]]) -> None:
        """File every existence candidate of the frame by its label, its place under the node rule, other carriers and the decision."""

        labels = labelled.get("existence_labels") or {}
        decisions = {str(k): str(v) for k, v in ((step["receipt"].get("existence") or {}).get("decisions") or {}).items()}
        _require(set(decisions) == set(labels), "audit_existence_decisions_differ_from_labels")
        if not labels:
            return
        before = {str(e["entity_id"]): e for e in step["memory_before"]["entities"]}
        fragment_keys = {str(t["key"]) for t in labelled["targets"].values() if t.get("key") is not None}
        frame_index = int(labelled["frame_index"])
        phase = "after_window" if self.window_end is not None and frame_index > self.window_end else "at_or_before_window_end"
        carriers: dict[str, set[str]] = {}
        for entity in predictions:
            identity = identities[str(entity["entity_id"])]
            record = truth_table.get(identity["key"]) if identity["resolvable"] else None
            if record is not None and record["present"] is True and record["in_scope"] is True and self._in_place(entity["centroid_m"], record):
                carriers.setdefault(str(identity["key"]), set()).add(str(entity["entity_id"]))
        for entity_id, label in labels.items():
            key = label.get("key")
            if key is None:
                klass, in_place, carrier, fragment = "no_key", "n/a", "n/a", "n/a"
            else:
                klass = self.interventions.get(str(key), "never_intervened")
                fragment = "yes" if str(key) in fragment_keys else "no"
                record = truth_table.get(str(key))
                if record is None or record["present"] is not True:
                    in_place = carrier = "object_absent"
                elif record["in_scope"] is not True:
                    in_place = carrier = "out_of_scope"
                else:
                    in_place = "yes" if self._in_place(before[entity_id]["centroid_m"], record) else "no"
                    carrier = "yes" if carriers.get(str(key), set()) - {entity_id} else "no"
            row = (str(label["status"]), str(label.get("reason")), klass, phase, in_place, carrier, fragment, decisions[entity_id])
            self.existence_tally[row] = self.existence_tally.get(row, 0) + 1

    # -- ruling 81-3 -------------------------------------------------------------

    def _close_interval(self, key: str, closure: str) -> None:
        interval = self.loss_open.pop(key)
        row = self.loss_intervals.setdefault(interval["cause"], {"intervals": 0, "recovered": 0, "object_gone": 0, "censored": 0,
                                                                 "frames": 0, "bins": {label: 0 for _, label in LOSS_DURATION_BINS}})
        row["intervals"] += 1
        row[closure] += 1
        row["frames"] += int(interval["frames"])
        for upper, label in LOSS_DURATION_BINS:
            if upper is None or interval["frames"] <= upper:
                row["bins"][label] += 1
                break

    def _tally_losses(self, step: Mapping[str, Any], labelled: Mapping[str, Any], truth_table: Mapping[str, Mapping[str, Any]],
                      predictions: Sequence[Mapping[str, Any]], identities: Mapping[str, Mapping[str, Any]],
                      folds: Sequence[tuple[str, str]]) -> None:
        """Loss-of-carrier events of this frame and the absence frames they open (ruling 81-3)."""

        present = {key for key, row in truth_table.items() if row["present"] is True and row["in_scope"] is True}
        carriers: dict[str, set[str]] = {key: set() for key in present}
        for entity in predictions:
            identity = identities[str(entity["entity_id"])]
            if identity["resolvable"] and identity["key"] in carriers and self._in_place(entity["centroid_m"], truth_table[identity["key"]]):
                carriers[identity["key"]].add(str(entity["entity_id"]))
        # 1. close the intervals of objects carried again or gone
        for key in list(self.loss_open):
            if key not in present:
                self._close_interval(key, "object_gone")
            elif carriers[key]:
                self._close_interval(key, "recovered")
        # 2. open an interval for every object that lost its last carrier this frame
        if self.loss_prev_carriers is not None:
            assignment = {str(k): str(v) for k, v in step["receipt"]["assignment"].items()}
            bound = {column: fragment for fragment, column in assignment.items() if not column.startswith(lt.BIRTH_COLUMN_PREFIX)}
            decisions = {str(k): str(v) for k, v in ((step["receipt"].get("existence") or {}).get("decisions") or {}).items()}
            after = {str(e["entity_id"]): e for e in step["state"]["memory"]["entities"]}
            folded = {folded_id for _, folded_id in folds}
            survivors = {canonical_id for canonical_id, _ in folds}
            targets = labelled["targets"]
            for key, before in self.loss_prev_carriers.items():
                if not before or key not in present or carriers[key]:
                    continue

                def cause_of(entity_id: str) -> str:
                    if decisions.get(entity_id) == "RETRACT":
                        return "retract"
                    if entity_id in folded:
                        return "folded"
                    if entity_id not in after:
                        return "removed"
                    if entity_id in bound:
                        fragment_key = (targets.get(bound[entity_id]) or {}).get("key")
                        if fragment_key is None:
                            return "bound_unlabelled_fragment"
                        return "own_bind_off_place" if str(fragment_key) == key else "wrong_bind"
                    if entity_id in survivors:
                        return "fold_survivor_changed"
                    identity = identities.get(entity_id)
                    if identity is None or not identity["resolvable"] or identity["key"] != key:
                        return "identity_changed"
                    if key in self.loss_prev_truth and [float(v) for v in truth_table[key]["centroid_m"]] != self.loss_prev_truth[key]:
                        return "object_truth_changed"
                    return "other"

                causes = {cause_of(entity_id) for entity_id in sorted(before)}
                cause = next(iter(causes)) if len(causes) == 1 else ("mixed_with_wrong_bind" if "wrong_bind" in causes else "mixed")
                klass = self.interventions.get(key, "never_intervened")
                self.loss_events[(cause, klass)] = self.loss_events.get((cause, klass), 0) + 1
                self.loss_open[key] = {"cause": cause, "start": int(labelled["frame_index"]), "frames": 0}
        # 3. count this frame's uncarried in-scope frames of objects seen before
        for key in present:
            if carriers[key] or key not in self.keys_fragmented:
                continue
            self.uncarried_seen_frames += 1
            if key in self.loss_open:
                self.loss_open[key]["frames"] += 1
            else:
                self.uncarried_without_event_frames += 1
        self.loss_prev_carriers = carriers
        self.loss_prev_truth = {key: [float(v) for v in truth_table[key]["centroid_m"]] for key in present}

    def _loss_report(self) -> dict[str, Any]:
        intervals = json.loads(json.dumps(self.loss_intervals))
        for interval in self.loss_open.values():  # open at the end: censored (the state itself is left as it is)
            row = intervals.setdefault(interval["cause"], {"intervals": 0, "recovered": 0, "object_gone": 0, "censored": 0,
                                                           "frames": 0, "bins": {label: 0 for _, label in LOSS_DURATION_BINS}})
            row["intervals"] += 1
            row["censored"] += 1
            row["frames"] += int(interval["frames"])
            for upper, label in LOSS_DURATION_BINS:
                if upper is None or interval["frames"] <= upper:
                    row["bins"][label] += 1
                    break
        _require(sum(int(row["frames"]) for row in intervals.values()) + self.uncarried_without_event_frames == self.uncarried_seen_frames,
                 "audit_loss_frames_do_not_sum")
        return {"rule": LOSS_RULE, "causes": list(LOSS_CAUSES), "event_fields": ["cause", "object_class"],
                "events": [[*row, count] for row, count in sorted(self.loss_events.items())],
                "intervals": {cause: intervals[cause] for cause in sorted(intervals)},
                "uncarried_seen_object_frames": self.uncarried_seen_frames,
                "uncarried_without_loss_event_frames": self.uncarried_without_event_frames}

    # -- ruling 80-4 -------------------------------------------------------------

    def _tally_association(self, step: Mapping[str, Any], labelled: Mapping[str, Any]) -> None:
        """File every fragment's decision by its teacher status, the outcome, the chosen entity's prior state and first sighting.

        Same-frame duplicates are judged with their keeper exactly as ``lean_teacher.decompose_frame`` does (the keeper is
        correct when some member reached the target and no member was bound to another existing entity).
        """

        targets = labelled["targets"]
        assignment = {str(k): str(v) for k, v in step["receipt"]["assignment"].items()}
        _require(set(assignment) == set(targets), "audit_assignment_differs_from_targets")
        state_of = {str(e["entity_id"]): str(e["state"]) for e in step["memory_before"]["entities"]}
        groups: dict[str, list[str]] = {}
        for fragment_id, target in targets.items():
            if target["status"] == "duplicate_of_labelled":
                groups.setdefault(str(target["duplicate_of"]), []).append(str(fragment_id))

        def is_birth(column: str) -> bool:
            return column.startswith(lt.BIRTH_COLUMN_PREFIX)

        for fragment_id in sorted(targets):
            target = targets[fragment_id]
            status = str(target["status"])
            key = target.get("key")
            first = "n/a" if key is None else ("yes" if str(key) not in self._keys_before_frame else "no")
            chosen = assignment[fragment_id]
            if status == "duplicate_of_labelled":
                row = (status, "grouped", "birth" if is_birth(chosen) else state_of.get(chosen, "unknown"), first)
            elif status in ("labelled", "birth"):
                wanted = str(target["target"])
                members = [fragment_id] + sorted(groups.get(fragment_id, []))
                reached = any(assignment[m] == wanted for m in members)
                misbound = sorted(assignment[m] for m in members if not is_birth(assignment[m]) and assignment[m] != wanted)
                if reached and not misbound:
                    row = (status, "correct", "birth" if is_birth(wanted) else state_of.get(wanted, "unknown"), first)
                elif misbound:
                    outcome = "bind_instead_of_birth" if status == "birth" else "wrong_bind"
                    row = (status, outcome, state_of.get(misbound[0], "unknown"), first)
                else:  # every member went to its own birth column while an existing entity was wanted
                    row = (status, "birth_instead_of_bind", "birth", first)
            else:
                row = (status, "birth" if is_birth(chosen) else "bind", "birth" if is_birth(chosen) else state_of.get(chosen, "unknown"), first)
            self.association_tally[row] = self.association_tally.get(row, 0) + 1

    # -- ruling 76 (1)(a) --------------------------------------------------------

    def _truth_centroid_at(self, key: str, tick: int) -> list[float] | None:
        """The object's truth centroid as last recorded at or before ``tick`` (None if never recorded by then)."""

        found = None
        for at, centroid in self.truth_centroid_changes.get(key, []):
            if at > tick:
                break
            found = centroid
        return found

    def _centroid_ledger(self, frame_eval: Mapping[str, Any], predictions: Sequence[Mapping[str, Any]],
                         identities: Mapping[str, Mapping[str, Any]], present_keys: Sequence[str],
                         dist_rows: Sequence[Sequence[float]], column_of: Mapping[str, int],
                         truth_table: Mapping[str, Mapping[str, Any]], tick: int) -> dict[str, dict[str, int]]:
        for key in present_keys:  # record where each present object is, only when it changes
            centroid = [float(v) for v in truth_table[key]["centroid_m"]]
            history = self.truth_centroid_changes.setdefault(key, [])
            if not history or history[-1][1] != centroid:
                history.append((tick, centroid))
        matched_entity = {str(entity_id): key for entity_id, key in frame_eval["matched_pairs"]}
        matched_keys = set(matched_entity.values())
        resolving: dict[str, list[int]] = {key: [] for key in present_keys}
        ambiguous_rows: list[int] = []
        entity_counts = {name: 0 for name in CENTROID_ENTITY_CATEGORIES}
        for row, entity in enumerate(predictions):
            entity_id = str(entity["entity_id"])
            identity = identities[entity_id]
            if not identity["resolvable"]:
                ambiguous_rows.append(row)
            elif identity["key"] in resolving:
                resolving[identity["key"]].append(row)
            if entity_id in matched_entity:
                category = "matched"
            elif not identity["resolvable"]:
                category = "identity_ambiguous_unmatched"
            elif identity["key"] not in column_of:
                category = "own_object_absent"
            elif dist_rows[row][column_of[identity["key"]]] <= self.delta:
                category = "own_object_near_unmatched"
            else:
                then = self._truth_centroid_at(identity["key"], int(entity["last_seen_tick"]))
                now = truth_table[identity["key"]]["centroid_m"]
                moved = then is not None and _distance(then, now) > self.delta
                category = "own_object_far_object_moved" if moved else "own_object_far_object_not_moved"
            entity_counts[category] += 1
        truth_counts = {name: 0 for name in CENTROID_TRUTH_CATEGORIES}
        for key in present_keys:
            column = column_of[key]
            if key in matched_keys:
                category = "matched"
            elif resolving[key]:
                near = any(dist_rows[row][column] <= self.delta for row in resolving[key])
                category = "resolved_entity_near_unmatched" if near else "resolved_entity_far"
            elif any(dist_rows[row][column] <= self.delta for row in ambiguous_rows):
                category = "only_ambiguous_entity_near"
            elif key in self.keys_fragmented:
                category = "no_entity_fragmented_before"
            else:
                category = "no_entity_never_fragmented"
            truth_counts[category] += 1
        _require(entity_counts["matched"] == frame_eval["matched"] and truth_counts["matched"] == frame_eval["matched"],
                 "audit_centroid_ledger_does_not_reproduce_the_evaluator")
        for name, count in entity_counts.items():
            self.centroid_entity_counts[name] += count
        for name, count in truth_counts.items():
            self.centroid_truth_counts[name] += count
        return {"entity": entity_counts, "truth": truth_counts}

    def _birth_reasons(self, step: Mapping[str, Any], labelled: Mapping[str, Any], truth_table: Mapping[str, Mapping[str, Any]]) -> None:
        """Why each fragment the committed program gave birth to was born (the arm's logits recomputed on the sealed rows)."""

        from vsmt import lean_arms as arms
        from vsmt import lean_assignment as la
        from vsmt import lean_runner as lr

        if step["receipt"].get("illegal_program"):
            return  # the empty program was committed: nothing was born
        births = sorted(str(fragment_id) for fragment_id, column in step["stage_b"]["assignment"].items()
                        if str(column).startswith(la.BIRTH_COLUMN_PREFIX))
        if not births:
            return
        logits = lr._association_logits(self.arm, lr.validate_arm_config(self.arm, self.config), step["stage_a"], self.scorer)
        carriers: dict[str, set[str]] = {}
        for entity_id, identity in lt.entity_identities(step["memory_before"], self.evidence).items():
            if identity["resolvable"]:
                carriers.setdefault(str(identity["key"]), set()).add(entity_id)
        recalled: dict[str, set[str]] = {}
        for row in step["stage_a"]["association_rows"]:
            recalled.setdefault(str(row["fragment_id"]), set()).add(str(row["entity_id"]))
        for fragment_id in births:
            target = labelled["targets"].get(fragment_id) or {}
            key = target.get("key")
            scope = "in_scope_object" if key is not None and truth_table.get(key, {}).get("in_scope") is True else "other"
            if key is None:
                reason = "unlabelled_fragment"
            elif key not in self._keys_before_frame:
                reason = "first_labelled_observation"
            elif not carriers.get(key):
                reason = "no_resolved_carrier"
            else:
                candidates = carriers[key] & recalled.get(fragment_id, set())
                birth_logit = float(logits["birth_logits"][fragment_id])
                eligible = [entity_id for entity_id in candidates
                            if float(logits["association_logits"][f"{fragment_id}|{entity_id}"]) > arms.INELIGIBLE_LOGIT
                            and float(logits["association_logits"][f"{fragment_id}|{entity_id}"]) >= birth_logit]
                if not candidates:
                    reason = "correct_carrier_not_recalled"
                elif not eligible:
                    reason = "correct_carrier_below_birth_logit"
                else:
                    reason = "correct_carrier_lost_joint_competition"
            self.birth_reasons[scope][reason] += 1

    # -- v7, ruling 86-0 -----------------------------------------------------------

    def _attribute_reobservations(self, step: Mapping[str, Any], labelled: Mapping[str, Any]) -> None:
        """File every moved object's first labelled re-observation of this frame (the evaluator's own set and carriers)."""

        from vsmt import lean_assignment as la
        from vsmt import lean_runner as lr

        continuity = labelled.get("identity_continuity") or {}
        reobserved = continuity.get("reobserved") or {}
        if not reobserved or self.carriers_before_move is None:
            return
        memory_before = step["memory_before"]
        states = {str(e["entity_id"]): str(e["state"]) for e in memory_before["entities"]}
        identities = lt.entity_identities(memory_before, self.evidence)
        stage_a = step["stage_a"]
        assignment = {str(k): str(v) for k, v in step["receipt"]["assignment"].items()}
        logits = None
        if self.arm is not None:
            logits = lr._association_logits(self.arm, lr.validate_arm_config(self.arm, self.config), stage_a, self.scorer)
        distance_index = la.ASSOCIATION_FEATURES.index("centroid_distance_m")
        kept = 0
        for key in sorted(reobserved):
            fragment_id = str(reobserved[key])
            distances = {str(r["entity_id"]): float(r["features"][distance_index])
                         for r in stage_a["association_rows"] if str(r["fragment_id"]) == fragment_id}
            record = attribute_reobservation(
                key=str(key), carriers=self.carriers_before_move.get(key, []), states=states, identities=identities,
                recall=stage_a["recall"].get(fragment_id, []), chosen=assignment[fragment_id], target=labelled["targets"][fragment_id],
                association_logits=None if logits is None else logits["association_logits"],
                birth_logit=None if logits is None else float(logits["birth_logits"][fragment_id]),
                distances=distances, fragment_id=fragment_id, fragmented_at_move=self.fragmented_at_move,
                ever_retracted=self.ever_retracted, folded_ids=self.folded_ids, deleted_ids=self.deleted_ids)
            record.update(original_carrier_global_rank(memory_before, step["view"], fragment_id=fragment_id,
                                                       carriers=self.carriers_before_move.get(key, [])))
            kept += int(record["category"] == "kept")
            self.identity_attribution.append({"ordinal": self.intervention_ordinal.get(key), "frame_index": int(labelled["frame_index"]), **record})
        # the attribution must reproduce the evaluator's own count for this frame
        _require(kept == int(continuity.get("kept", 0)), "audit_attribution_disagrees_with_identity_continuity")

    def _file_folds(self) -> None:
        """File the folds captured this frame by state pair and private identity (the teacher has labelled the frame)."""

        while self.fold_capture:
            fold = self.fold_capture.pop(0)
            left, right = (lt.entity_identity(fold[side], self.evidence) for side in ("canonical", "folded"))
            states = "_".join(sorted((fold["canonical"]["state"], fold["folded"]["state"])))
            if not (left["resolvable"] and right["resolvable"]):
                identity = "ambiguous"
            else:
                identity = "same_object" if left["key"] == right["key"] else "different_objects"
            self.folds_by_identity[f"{states}|{identity}"] += 1
            self.folds_by_coobservation[f"{identity}|{fold_coobservation(fold)}"] += 1

    def _dedup_pairs(self, memory_after: Mapping[str, Any], identities: Mapping[str, Mapping[str, Any]]) -> None:
        """At a dedup tick, tally the entity pairs left after the fold by state pair and private identity at every gate value."""

        import numpy as np

        from vsmt import lean_memory as lm

        self.dedup_ticks += 1
        record = memory_after["transaction_log"][-1]
        _require(int(record["tick"]) == int(memory_after["tick"]), "audit_dedup_log_not_at_the_tick")
        self.dedup_folds += len(record["post_maintenance"]["dedup"])
        entities = sorted((e for e in memory_after["entities"] if e["state"] in ("active", "dormant")), key=lambda e: str(e["entity_id"]))
        if len(entities) < 2:
            return
        descriptors = np.asarray([e["descriptor_mean"] for e in entities], dtype=np.float64)
        norms = np.linalg.norm(descriptors, axis=1)
        norms[norms == 0.0] = 1.0
        unit = descriptors / norms[:, None]
        cosine = unit @ unit.T
        centroids = np.asarray([e["centroid_m"] for e in entities], dtype=np.float64)
        distance = np.linalg.norm(centroids[:, None, :] - centroids[None, :, :], axis=2)
        count = len(entities)
        for i in range(count):
            left = entities[i]
            left_identity = identities[str(left["entity_id"])]
            for j in range(i + 1, count):
                right = entities[j]
                right_identity = identities[str(right["entity_id"])]
                states = "_".join(sorted((left["state"], right["state"])))
                if not (left_identity["resolvable"] and right_identity["resolvable"]):
                    identity = "ambiguous"
                elif left_identity["key"] == right_identity["key"]:
                    identity = "same_object"
                else:
                    identity = "different_objects"
                tally = self.dedup_pairs[f"{states}|{identity}"]
                tally["pairs"] += 1
                pair_cosine, pair_distance = float(cosine[i, j]), float(distance[i, j])
                if pair_cosine < DEDUP_COSINES[0] or pair_distance > DEDUP_DISTANCES_M[-1]:
                    continue
                pair_iou = lm._aabb_iou(left, right)
                for c in DEDUP_COSINES:
                    if pair_cosine < c:
                        break
                    for d in DEDUP_DISTANCES_M:
                        if pair_distance > d:
                            continue
                        for u in DEDUP_IOUS:
                            if pair_iou < u:
                                continue
                            name = f"cos{c}|d{d}|iou{u}"
                            tally["pass"][name] = tally["pass"].get(name, 0) + 1


    # -- the episode -------------------------------------------------------------

    def report(self) -> dict[str, Any]:
        def quantiles(values: Sequence[float]) -> dict[str, Any]:
            if not values:
                return {"count": 0}
            ordered = sorted(values)
            at = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]  # noqa: E731
            return {"count": len(ordered), "p10": at(0.1), "p25": at(0.25), "p50": at(0.5), "p75": at(0.75), "p90": at(0.9),
                    "mean": sum(ordered) / len(ordered)}

        current = self.rule_sums["iou_0.3_secondary"]  # the categories partition the IoU column's sets, which are the primary's too
        _require(sum(self.entity_counts.values()) == current["predicted"], "audit_entity_categories_do_not_sum")
        _require(sum(self.truth_counts.values()) == current["truth"], "audit_truth_categories_do_not_sum")
        primary = self.rule_sums["centroid_within_0.5m"]
        _require(sum(self.centroid_entity_counts.values()) == primary["predicted"], "audit_centroid_entity_categories_do_not_sum")
        _require(sum(self.centroid_truth_counts.values()) == primary["truth"], "audit_centroid_truth_categories_do_not_sum")
        if self.fold_capture is not None and self.dedup_period is not None:
            _require(sum(self.folds_by_identity.values()) == self.dedup_folds, "audit_captured_folds_do_not_match_the_log")
        return {
            "schema_version": SCHEMA_VERSION,
            "frames": self.frames,
            "iou_min": self.iou_min, "delta_moved_m": self.delta, "pad_m": PAD_M, "centroid_radius_m": CENTROID_RADIUS_M,
            "rules": {rule: _prf(s["matched"], s["predicted"], s["truth"]) for rule, s in self.rule_sums.items()},
            "wrong_identity_matches": dict(self.wrong_identity_matches),
            "entity_categories": dict(self.entity_counts),
            "truth_categories": dict(self.truth_counts),
            "truth_by_group": {group: dict(row) for group, row in sorted(self.by_group.items())},
            "truth_by_type": {name: dict(row) for name, row in sorted(self.by_type.items(), key=lambda item: (-sum(item[1].values()), item[0]))},
            "in_memory_entities_per_frame_mean": (sum(self.in_memory_per_frame) / self.frames) if self.frames else None,
            "out_of_scope_entities_per_frame_mean": (sum(self.out_of_scope_per_frame) / self.frames) if self.frames else None,
            "own_object_iou_when_near": quantiles(self.own_iou_near_values),
            "own_object_centroid_distance_m": quantiles(self.own_distance_values),
            "rule_matched_per_frame": {rule: list(values) for rule, values in self.rule_matched_per_frame.items()},
            "centroid_entity_categories": dict(self.centroid_entity_counts),
            "centroid_truth_categories": dict(self.centroid_truth_counts),
            "birth_reasons": {scope: dict(row) for scope, row in self.birth_reasons.items()} if self.arm is not None else None,
            "identity_attribution": {"records": list(self.identity_attribution),
                                     "counts": {name: sum(1 for r in self.identity_attribution if r["category"] == name)
                                                for name in REOBSERVATION_CATEGORIES}},
            "dedup": {"period_ticks": self.dedup_period, "ticks": self.dedup_ticks, "folds": self.dedup_folds,
                      "folds_by_identity": dict(self.folds_by_identity) if self.fold_capture is not None else None,
                      "folds_by_coobservation": dict(self.folds_by_coobservation) if self.fold_capture is not None else None,
                      "gate_values": {"cosine": list(DEDUP_COSINES), "distance_m": list(DEDUP_DISTANCES_M), "iou": list(DEDUP_IOUS)},
                      "pairs_after_fold": {name: {"pairs": row["pairs"], "pass": dict(sorted(row["pass"].items()))}
                                           for name, row in self.dedup_pairs.items()}} if self.dedup_period is not None else None,
            "existence_tally_fields": list(EXISTENCE_TALLY_FIELDS),
            "existence_tally": [[*row, count] for row, count in sorted(self.existence_tally.items())],
            "association_tally_fields": list(ASSOCIATION_TALLY_FIELDS),
            "association_tally": [[*row, count] for row, count in sorted(self.association_tally.items())],
            "loss_tally": self._loss_report(),
        }


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

#: v9 (ruling 88-2 (i)): the teacher-as-policy decision ceiling.  A decisive logit, far outside any trained head's range.
ORACLE_LOGIT = 20.0
ORACLE_ARMS = ("VSMT-lean", "NoVersion", "AssocOnly")
ORACLE_FALLBACK_STATUSES = ("recall_miss", "unlabelled", "identity_ambiguous", "duplicate_of_labelled")


def augment_recall(recall: Mapping[str, Sequence[str]], memory: Mapping[str, Any], *, instances: Mapping[str, Mapping[str, Any]],
                   evidence: Mapping[str, str | None], dominance_min_share: float) -> tuple[dict[str, list[str]], int]:
    """Ruling 88-2 (i) oracle recall: a fragment whose dominant object has carriers none of which was recalled gets the carrier
    with the earliest first version (the teacher's own target rule) appended; returns the new recall and the additions."""

    carriers: dict[str, list[Mapping[str, Any]]] = {}
    for entity in memory["entities"]:
        identity = lt.entity_identity(entity, evidence)
        if identity["resolvable"]:
            carriers.setdefault(str(identity["key"]), []).append(entity)
    out = {str(fid): list(ids) for fid, ids in recall.items()}
    added = 0
    for fragment_id, ids in out.items():
        dominance = lt.fragment_dominance(instances[fragment_id]["overlap"], dominance_min_share=dominance_min_share)
        if dominance["status"] != "dominant" or not carriers.get(dominance["key"]):
            continue
        matching = sorted(carriers[dominance["key"]], key=lambda e: (int(e["versions"][0]["opened_at"]), str(e["entity_id"])))
        if any(str(e["entity_id"]) in ids for e in matching):
            continue
        ids.append(str(matching[0]["entity_id"]))
        added += 1
    return out, added


class OracleDiagnostic:
    """Ruling 88-2 (i): the teacher's decisions used as the policy, a diagnostic mode of the node audit (never a method).

    白话：它回答“这套词表、召回与执行器在每步决定都对时最多能做到多好”。每帧在求解之前，它按 S0-04 的规则直接算 teacher 的关联目标
    （标为 labelled 或 birth 的色块取该列，召回漏掉、无标注、身份含糊、同帧重复的色块一律新建并计数）和存在标签（可判定候选里 gone 的撤回，
    其余不撤回；标签口径是节点主列或诊断用的“仅质心”），把它们写成远超学习头量程的 logit 交给同一个 runner；可以只替换关联或只替换存在，
    另一半用学习头（2×2 混合格）；可选“补召回”，把色块主导物体的最早承载实体补进召回。例如被拿走的杯子在第一次可判定时就被撤回，被搬走的
    书第一次重见就接回原编号。它在两段封存之前读私有真值，所以只能作诊断：产物标 ``oracle``，不写训练记录，不进任何表，不选参。
    """

    def __init__(self, *, teacher: Any, geometry_table: Mapping[str, Any], executed_interventions: Sequence[Mapping[str, Any]],
                 window: Sequence[int] | None, policy: Mapping[str, Any], arm: str, episode_id: str, association: bool,
                 existence_rule: str | None, recall: bool, learned: Any = None) -> None:
        from vsmt import lean_object_geometry as og
        from vsmt import lean_runner as lr

        _require(arm in ORACLE_ARMS, f"oracle_arm_not_supported:{arm}")
        _require(association or existence_rule is not None, "oracle_without_an_oracle_part")
        _require(existence_rule is None or existence_rule in lt.EXISTENCE_PLACE_RULES, "oracle_existence_rule_unknown")
        _require(not (arm == "AssocOnly" and existence_rule is not None), "oracle_existence_for_assoc_only")
        _require(not recall or association, "oracle_recall_needs_oracle_association")
        needs_learned = (not association) or (arm != "AssocOnly" and existence_rule is None)
        _require(learned is not None or not needs_learned, "oracle_needs_learned_heads_for_the_other_part")
        self.teacher = teacher
        self.policy = dict(policy)
        self.association = bool(association)
        self.existence_rule = existence_rule
        self.recall = bool(recall)
        self.learned = learned
        executed = [row for row in executed_interventions if row.get("executed", True)]
        self.tracker = og.EpisodeTruthTracker(geometry_table, executed_interventions=executed, window=window)
        self.memory = lr.initial_state(episode_id=episode_id, arm=arm)["memory"]
        self.frame: dict[str, Any] = {}
        self.counts: dict[str, Any] = {"frames": 0, "association_fallback_birth": {s: 0 for s in ORACLE_FALLBACK_STATUSES},
                                       "association_targets_taken": 0, "existence_gone": 0, "existence_not_gone": 0, "recall_additions": 0}
        self.last_frame_index = -1
        self.counted_frame = -1

    # -- per frame -------------------------------------------------------------------

    def prepare(self, frame_index: int, cache_frame: Mapping[str, Any], private_record: Mapping[str, Any], masks: Mapping[str, Any],
                label_image: Any) -> None:
        """The private truth of one frame, before the runner sees the frame (the diagnostic's only departure from the S2-04 order)."""

        from vsmt import lean_evaluation as ev

        _require(int(frame_index) == self.last_frame_index + 1, "oracle_frames_out_of_order")
        self.last_frame_index = int(frame_index)
        self.frame = {
            "instances": ev.fragment_instances(cache_frame, masks, label_image, ev.object_of_label(private_record)),
            "object_state": ev.object_state_from_truth(self.tracker.update(int(frame_index), private_record)),
        }
        self.counts["frames"] += 1

    def commit(self, memory: Mapping[str, Any]) -> None:
        """M_t after the runner's step: the memory the next frame's oracle decisions read."""

        self.memory = memory

    # -- the scorer interface the runner calls ----------------------------------------

    @property
    def assoc_only(self) -> bool:
        return self.existence_rule is None and (self.learned is None or bool(getattr(self.learned, "assoc_only", False)))

    def association_and_birth_logits(self, stage_a: Mapping[str, Any]) -> dict[str, Any]:
        if not self.association:
            return self.learned.association_and_birth_logits(stage_a)
        targets = lt.association_targets(self.memory, recall=stage_a["recall"], fragment_instance=self.frame["instances"],
                                         evidence_instance=self.teacher.evidence, dominance_min_share=self.policy["dominance_min_share"])
        count = self.counted_frame != self.last_frame_index  # the runner's call; the audit's re-scoring is not counted
        self.counted_frame = self.last_frame_index
        association: dict[str, float] = {}
        birth: dict[str, float] = {}
        for fragment_id in stage_a["rows"]:
            target = targets[str(fragment_id)]
            status = str(target["status"])
            chosen = str(target["target"]) if status in ("labelled", "birth") else f"{lt.BIRTH_COLUMN_PREFIX}{fragment_id}"
            if count and status in ORACLE_FALLBACK_STATUSES:
                self.counts["association_fallback_birth"][status] += 1
            elif count and status == "labelled":
                self.counts["association_targets_taken"] += 1
            birth[str(fragment_id)] = ORACLE_LOGIT if chosen.startswith(lt.BIRTH_COLUMN_PREFIX) else -ORACLE_LOGIT
        for row in stage_a["association_rows"]:
            fragment_id, entity_id = str(row["fragment_id"]), str(row["entity_id"])
            target = targets[fragment_id]
            taken = target["status"] == "labelled" and str(target["target"]) == entity_id
            association[f"{fragment_id}|{entity_id}"] = ORACLE_LOGIT if taken else -ORACLE_LOGIT
        return {"association_logits": association, "birth_logits": birth}

    def existence_labels(self, candidates: Sequence[str]) -> dict[str, dict[str, Any]]:
        """The S2-04 teacher's existence labels on M_{t-1} (structural and spawned objects first, present), under the cell's rule."""

        by_id = {str(e["entity_id"]): e for e in self.memory["entities"]}
        labels: dict[str, dict[str, Any]] = {}
        remaining: list[str] = []
        for entity_id in candidates:
            identity = lt.entity_identity(by_id[entity_id], self.teacher.evidence)
            if identity["resolvable"] and (lt.structural_type_of(identity["key"]) in lt.STRUCTURAL_TYPES_EXCLUDED
                                           or lt.is_spawned_after_reload(identity["key"])):
                labels[entity_id] = {"status": "present"}
            else:
                remaining.append(entity_id)
        labels.update(lt.existence_labels(self.memory, candidates=remaining, object_state=self.frame["object_state"],
                                          evidence_instance=self.teacher.evidence, delta_moved_m=self.policy["delta_moved_m"],
                                          place_rule=self.existence_rule))
        return labels

    def existence_logits(self, rows: Sequence[Mapping[str, Any]], order: Sequence[str]) -> dict[str, float]:
        if self.existence_rule is None:
            return self.learned.existence_logits(rows, order)
        labels = self.existence_labels([str(row["entity_id"]) for row in rows])
        out = {}
        for row in rows:
            gone = labels[str(row["entity_id"])]["status"] == "gone"
            self.counts["existence_gone" if gone else "existence_not_gone"] += 1
            out[str(row["entity_id"])] = ORACLE_LOGIT if gone else -ORACLE_LOGIT
        return out

    # -- oracle recall ------------------------------------------------------------------

    def recall_patch(self) -> Any:
        """A context manager that, for the oracle-recall cell only, appends missing carriers inside S0-03's recall."""

        import contextlib

        from vsmt import lean_assignment as la

        oracle = self

        @contextlib.contextmanager
        def patched():
            if not oracle.recall:
                yield
                return
            original = la.build_recall

            def build_recall(frame: Mapping[str, Any], memory: Mapping[str, Any], **kwargs: Any) -> dict[str, list[str]]:
                recall, added = augment_recall(original(frame, memory, **kwargs), memory, instances=oracle.frame["instances"],
                                               evidence=oracle.teacher.evidence, dominance_min_share=oracle.policy["dominance_min_share"])
                oracle.counts["recall_additions"] += added
                return recall

            la.build_recall = build_recall
            try:
                yield
            finally:
                la.build_recall = original

        return patched()

    def describe(self) -> dict[str, Any]:
        return {"association": self.association, "existence_rule": self.existence_rule, "recall": self.recall,
                "learned_part": None if self.learned is None else ("existence" if self.association else "association"),
                "private_truth_enters_decisions": True, "diagnostic_only": True, "counts": self.counts}


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def run(args: argparse.Namespace) -> int:
    import lean_s1_04_diagnostics as diag
    import lean_s2_01_runner as s2_01
    import lean_s2_04_evaluate_episode as s2_04
    from vsmt import lean_assignment as la
    from vsmt import lean_evaluation as ev
    from vsmt import lean_object_geometry as og
    from vsmt import lean_runner as lr
    from vsmt import lean_test_seal

    refusal = lean_test_seal.refusal([args.cache_root, args.episode_root, args.geometry_root], reader="node-audit run")
    if refusal:  # ruling 103-1: sealed S3 test roots are read only by S3-05
        print(f"[node-audit] refused: {refusal}", file=sys.stderr)
        return 2
    diagnostic_options = [name for name, given in (
        ("--dedup-override", bool(args.dedup_override)), ("--dormancy-override", args.dormancy_override is not None),
        ("--oracle-association", bool(args.oracle_association)), ("--oracle-existence", args.oracle_existence is not None),
        ("--oracle-recall", bool(args.oracle_recall)), ("--trace-residuals", bool(args.trace_residuals)),
        ("--recall-global-count", args.recall_global_count is not None)) if given]
    if args.metrics_only and diagnostic_options:  # ruling 104-4 (1): a run of record takes no diagnostic option
        print(f"[node-audit] refused: --metrics-only takes no diagnostic option: {diagnostic_options}", file=sys.stderr)
        return 2
    if getattr(args, "manifest_split", None):  # ruling 104-6: an S3-03 audit reads only episodes of its manifest split
        from vsmt import lean_s3_03

        problem = lean_s3_03.manifest_split_refusal(args.episode_id, args.manifest_split)
        if problem:
            print(f"[node-audit] refused: {problem}", file=sys.stderr)
            return 2
    contract = ev.validate_evaluation_contract(s2_04.load_json(s2_04.S2_04_CONTRACT))
    runner_contract = lr.validate_runner_contract(s2_04.load_json(s2_01.S2_01_CONTRACT))
    closed = [f"S2-04 {name}" for name in s2_04.REQUIRED_S2_04 if contract["authorization"].get(name) is not True]
    closed += [f"S2-01 {name}" for name in s2_04.REQUIRED_S2_01 if runner_contract["authorization"].get(name) is not True]
    if closed:
        print(f"[node-audit] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    policy, missing = s2_04.gather_teacher_policy()
    if missing:
        print(f"[node-audit] refused: policy values still null: {missing}", file=sys.stderr)
        return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[node-audit] refused: the checkout is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    try:  # ruling 104-7: one job may audit several configurations of one arm on one episode
        plan = config_plan(args)
    except NodeAuditError as exc:
        print(f"[node-audit] refused: {exc}", file=sys.stderr)
        return 2
    if args.dedup_override:
        # diagnostic only: the same runner under another shared-dedup triple (a candidate for a ruling), recorded in the payload
        from vsmt import lean_memory as lm

        policy["runner"]["dedup"] = lm.validate_dedup_policy({**policy["runner"]["dedup"], **json.loads(args.dedup_override)})
    if args.dormancy_override is not None:
        # ruling 80-3, diagnostic only: the shared dormancy limit replaced (a huge value switches dormancy off), recorded in the payload
        policy["runner"]["dormancy_missed_opportunity_limit"] = int(args.dormancy_override)
    if args.recall_global_count is not None:
        # ruling 89-1, diagnostic only: the global recall channel's k' replaced for this run (the runner reads la.RECALL_GLOBAL_COUNT per frame)
        _require(int(args.recall_global_count) >= 1, "recall_global_count_invalid")
        la.RECALL_GLOBAL_COUNT = int(args.recall_global_count)
    for config, _ in plan:
        lr.validate_arm_config(args.arm, config)
    learned = None
    oracle_requested = bool(args.oracle_association or args.oracle_existence or args.oracle_recall)
    heads_needed = (not args.oracle_association) or (args.arm != "AssocOnly" and args.oracle_existence is None)
    if args.arm in lr.LEARNED_ARMS and (heads_needed or args.heads):
        if not args.heads:
            print(f"[node-audit] refused: {args.arm} needs --heads", file=sys.stderr)
            return 2
        from vsmt import lean_model

        learned = lean_model.LeanScorer(lean_model.load_heads(s2_04.load_json(Path(args.heads)), device=args.device), device=args.device)
    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    try:  # ruling 84-1 (b): the head pinned for the episode's sealed mask source; --mask-source, when given, must be that source
        mask_source = args.mask_source or s2_01.sealed_mask_source_of(cache_dir)
        projector, weights_sha256 = s2_01.reid_projector(args.descriptor, args.weights, mask_source=mask_source, device=args.device)
    except s2_01.EntryRefusal as exc:
        print(f"[node-audit] refused: {exc}", file=sys.stderr)
        return 2
    pending: list[tuple[dict[str, Any], Path]] = []
    for config, output_root in plan:
        out_dir = Path(output_root).resolve() / args.episode_id / args.arm
        existing = out_dir / AUDIT_FILE_NAME
        if existing.exists():
            if getattr(args, "skip_existing", False) and complete_audit(existing, episode_id=args.episode_id, arm=args.arm, config=config,
                                                                         metrics_only=bool(args.metrics_only)):
                print(f"[node-audit] kept: {existing}")
                continue
            print(f"[node-audit] refused: audit exists: {existing}", file=sys.stderr)
            return 2
        pending.append((config, out_dir))
    if not pending:
        return 0

    episode_root = Path(args.episode_root).resolve()
    seal, frame_paths = s2_04.verify_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s(), mask_source=mask_source)
    if args.frames is not None:
        frame_paths = frame_paths[: int(args.frames)]
    episode_receipt = s2_04.load_json(episode_root / "receipt.json") if (episode_root / "receipt.json").exists() else {}
    split_seed = int(s2_04.load_json(s2_04.CONFIG_DIR / "lean_s1_02a_pilot_v2.json")["split_freeze"]["seed"])

    def audit_one(config: dict[str, Any], out_dir: Path) -> int:
        """One configuration's closed loop from scratch: its own geometry table, intervention log, policy copy and teacher."""

        out_dir.mkdir(parents=True, exist_ok=True)
        run_policy = copy.deepcopy(policy)
        table = og.validate_geometry_table(s2_04.load_json(Path(args.geometry_root).resolve() / args.episode_id / og.TABLE_FILE_NAME))
        executed, window = diag.cache_runner_read_interventions(episode_root / "provenance")
        nuisance_meta = {"path": str(cache_dir), "seed": split_seed, "house_index": episode_receipt.get("source_index")}
        teacher = ev.EpisodeTeacher(arm=args.arm, geometry_table=table, executed_interventions=executed, window=window,
                                    policy=run_policy["teacher"], nuisance_meta=nuisance_meta)
        captured = None if args.metrics_only else capture_truth_table(teacher)  # ruling 104-4 (1): no diagnostic block to feed
        scorer = learned  # the heads' own scorer, before any oracle wraps it (the residual trace reads its logits)
        oracle = None
        if oracle_requested:
            # ruling 88-2 (i), diagnostic only: the teacher's decisions become the policy (private truth before the seals)
            try:
                oracle = OracleDiagnostic(teacher=teacher, geometry_table=table, executed_interventions=executed, window=window,
                                          policy=run_policy["teacher"], arm=args.arm, episode_id=args.episode_id,
                                          association=bool(args.oracle_association), existence_rule=args.oracle_existence,
                                          recall=bool(args.oracle_recall), learned=learned)
            except NodeAuditError as exc:
                print(f"[node-audit] refused: {exc}", file=sys.stderr)
                return 2
            scorer = oracle
        audit = None
        if not args.metrics_only:
            audit = NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=run_policy["teacher"]["delta_moved_m"],
                              groups=object_groups(table), arm=args.arm, config=config, scorer=scorer, dedup=run_policy["runner"]["dedup"],
                              interventions=teacher.interventions, window_end=teacher.window_end,
                              carriers_before_move=teacher.carriers_before_move)
            audit.fold_capture = capture_dedup_folds()
        tracer = None
        if args.trace_residuals:
            # ruling 93 revised (2026-09-30), read-only: where each lingering stale entity got stuck; changes no decision
            import residual_trace

            tracer = residual_trace.ResidualTracer(teacher=teacher, learned=learned, delta_moved_m=run_policy["teacher"]["delta_moved_m"],
                                                   identity_of=lambda entity: lt.entity_identity(entity, teacher.evidence))
        started = time.time()
        current: dict[str, Any] = {}

        depth_view = s2_04.episode_depth_reader(episode_root, cache_dir)

        def private_of(index: int) -> tuple[Any, Any, Any]:
            masks = diag.cache_runner.read_masks_file(cache_dir / f"{index:04d}{diag.cache_runner.MASK_FILE_SUFFIX}")
            record, image = s2_04.load_private_frame(episode_root, index)
            return record, image, masks

        def frames():
            for index, path in enumerate(frame_paths):
                frame = diag.cache_runner.load_cache_frame(path)
                frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(index, frame)  # ruling 74
                current["frame"] = frame
                if oracle is not None:  # ruling 88-2 (i): the oracle reads the frame's private truth before the runner's step
                    current["private"] = private_of(index)
                    record, image, masks = current["private"]
                    oracle.prepare(index, frame, record, masks, image)
                yield frame

        state = None
        receipts: list[dict[str, Any]] = []
        mark = time.time()
        with (oracle.recall_patch() if oracle is not None else contextlib.nullcontext()):
            for index, step in enumerate(lr.run_episode(frames(), episode_id=args.episode_id, arm=args.arm, config=config,
                                                        policy=run_policy["runner"], descriptor=args.descriptor, projector=projector,
                                                        scorer=scorer)):
                runtime = time.time() - mark
                receipts.append(step["receipt"])
                state = step["state"]
                cache_frame = current["frame"]
                record, image, masks = current.pop("private") if oracle is not None else private_of(index)
                labelled = teacher.label_frame(step, cache_frame=cache_frame, private_record=record, masks=masks,
                                               label_image=image, runtime_s=runtime, peak_memory_bytes=s2_04.peak_rss_bytes())
                if audit is not None:
                    audit.observe(step, labelled, captured["table"])
                if tracer is not None:
                    tracer.observe(step, labelled)
                if oracle is not None:
                    oracle.commit(step["state"]["memory"])
                mark = time.time()
        summary = lr.episode_summary(state, receipts)
        episode = teacher.episode_report()
        payload = {
            "schema_version": SCHEMA_VERSION, "stage": "S2-05 node audit (read-only)", "code_commit": commit,
            "episode_id": args.episode_id, "arm": args.arm, "config": config, "descriptor": args.descriptor,
            "mask_source": mask_source, "weights_sha256": weights_sha256,
            "dedup_policy": run_policy["runner"]["dedup"], "dedup_override": json.loads(args.dedup_override) if args.dedup_override else None,
            "dormancy_override": args.dormancy_override,
            "recall_global_count": la.RECALL_GLOBAL_COUNT, "recall_global_count_override": args.recall_global_count,
            "frames": summary["frames"], "frames_requested": args.frames, "episode_seal_sha256": seal["payload_sha256"],
            "final_memory_digest": summary["final_memory_digest"], "final_entities_by_state": summary["final_entities_by_state"],
            "report_node_prf1": episode["report"]["node_prf1"], "report_node_prf1_iou": episode["report"]["node_prf1_iou"],
            "report": episode["report"], "heads": args.heads,
            "decomposition_totals": episode["diagnostics"]["decomposition_totals"], "trajectory_sha256": trajectory_sha256(receipts),
            "oracle": None if oracle is None else oracle.describe(),
            "metrics_only": bool(args.metrics_only),
            "audit": None if audit is None else audit.report(),
            "residual_trace": None if tracer is None else tracer.report(),
            "wall_seconds": round(time.time() - started, 1),
        }
        write_json_atomic(out_dir / AUDIT_FILE_NAME, payload)
        if audit is None:
            report = payload["report"]
            print(f"[node-audit] {args.arm} {args.episode_id} {json.dumps(config, sort_keys=True)} (metrics only): {summary['frames']} frames, "
                  f"node F1 {report['node_prf1']['node_f1']}, MRR {report['missing_residual_rate']['missing_residual_rate']}, "
                  f"{payload['wall_seconds']} s")
            return 0
        rules = payload["audit"]["rules"]
        print(f"[node-audit] {args.arm} {args.episode_id}: {summary['frames']} frames, current F1 {rules['iou_0.3_secondary']['f1']}, "
              f"oracle-group IoU F1 {rules['oracle_identity_groups_iou_0.3']['f1']}, centroid-0.5m F1 {rules['centroid_within_0.5m']['f1']}, "
              f"{payload['wall_seconds']} s")
        return 0

    for config, out_dir in pending:
        code = audit_one(config, out_dir)
        if code != 0:
            return code
    return 0


def config_plan(args: argparse.Namespace) -> list[tuple[dict[str, Any], str]]:
    """Ruling 104-7: the (configuration, output root) pairs of one job -- ``--config`` with ``--output-root``, or ``--configs``."""

    configs = getattr(args, "configs", None)
    if configs:
        _require(args.config is None and args.output_root is None, "configs_excludes_config_and_output_root")
        entries = json.loads(configs)
        _require(type(entries) is list and bool(entries), "configs_must_be_a_non_empty_list")
        plan: list[tuple[dict[str, Any], str]] = []
        for entry in entries:
            _require(type(entry) is dict and set(entry) == {"config", "output_root"} and type(entry["config"]) is dict
                     and type(entry["output_root"]) is str and bool(entry["output_root"]), "configs_entry_invalid")
            plan.append((entry["config"], entry["output_root"]))
        roots = [str(Path(root).resolve()) for _, root in plan]
        _require(len(set(roots)) == len(roots), "configs_output_roots_repeat")
        return plan
    _require(args.config is not None and args.output_root is not None, "config_and_output_root_required")
    return [(json.loads(args.config), args.output_root)]


def complete_audit(path: Path, *, episode_id: str, arm: str, config: Mapping[str, Any], metrics_only: bool) -> bool:
    """Whether an existing audit file is this job's finished output (resume skips it; anything else is refused)."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (payload.get("schema_version") == SCHEMA_VERSION and payload.get("episode_id") == episode_id and payload.get("arm") == arm
            and payload.get("config") == dict(config) and bool(payload.get("metrics_only")) == metrics_only
            and isinstance(payload.get("report"), dict))


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """Written whole or not at all: a job stopped mid-write leaves no audit that looks finished."""

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)


def merge_audits(output_root: Path, arm: str) -> dict[str, Any]:
    """Pool the node audits of one arm under an audit root: per-episode rows and pooled sums."""

    episodes: list[dict[str, Any]] = []
    pooled_rules = {rule: {"matched": 0, "predicted": 0, "truth": 0} for rule in RULES}
    pooled_entity = {name: 0 for name in ENTITY_CATEGORIES}
    pooled_truth = {name: 0 for name in TRUTH_CATEGORIES}
    pooled_group: dict[str, dict[str, int]] = {}
    pooled_type: dict[str, dict[str, int]] = {}
    commits: set[str] = set()
    pooled_centroid_entity = {name: 0 for name in CENTROID_ENTITY_CATEGORIES}
    pooled_centroid_truth = {name: 0 for name in CENTROID_TRUTH_CATEGORIES}
    pooled_births = {scope: {name: 0 for name in BIRTH_REASONS} for scope in ("in_scope_object", "other")}
    pooled_dedup: dict[str, Any] = {"ticks": 0, "folds": 0, "folds_by_identity": {}, "folds_by_coobservation": {}, "pairs_after_fold": {}}
    pooled_attribution: dict[str, int] = {name: 0 for name in REOBSERVATION_CATEGORIES}
    pooled_wrong: dict[str, int] = {}
    pooled_existence: dict[tuple[str, ...], int] = {}
    pooled_association: dict[tuple[str, ...], int] = {}
    pooled_loss_events: dict[tuple[str, ...], int] = {}
    pooled_loss_intervals: dict[str, dict[str, Any]] = {}
    pooled_uncarried = {"uncarried_seen_object_frames": 0, "uncarried_without_loss_event_frames": 0}
    oracle_settings: set[str] = set()
    recall_counts: set[Any] = set()
    mask_sources: set[Any] = set()
    modes: set[bool] = set()
    pooled_decomposition: dict[str, int] = {}
    for path in sorted(output_root.glob(f"*/{arm}/{AUDIT_FILE_NAME}")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _require(payload.get("schema_version") in ACCEPTED_AUDIT_SCHEMAS and payload.get("arm") == arm, f"audit_file_invalid:{path}")
        oracle_setting = {k: v for k, v in (payload.get("oracle") or {}).items() if k != "counts"} or None
        oracle_settings.add(json.dumps(oracle_setting, sort_keys=True))
        recall_counts.add(payload.get("recall_global_count"))
        mask_sources.add(payload.get("mask_source"))  # None for an audit written before v11
        modes.add(bool(payload.get("metrics_only")))  # False for an audit written before v12
        commits.add(str(payload["code_commit"]))
        for name, value in (payload.get("decomposition_totals") or {}).items():
            pooled_decomposition[name] = pooled_decomposition.get(name, 0) + int(value)
        if payload.get("metrics_only"):  # ruling 104-4 (1): the report and the counts, no diagnostic block
            episodes.append({
                "episode_id": payload["episode_id"], "frames": payload["frames"], "config": payload["config"],
                "code_commit": payload["code_commit"], "report": payload["report"], "dormancy_override": None, "oracle": None,
                "final_entities_by_state": payload["final_entities_by_state"],
                "decomposition_totals": payload["decomposition_totals"], "trajectory_sha256": payload["trajectory_sha256"],
                "audit_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
            continue
        audit = payload["audit"]
        for rule in RULES:
            for name in ("matched", "predicted", "truth"):
                pooled_rules[rule][name] += int(audit["rules"][rule][name])
        for name in ENTITY_CATEGORIES:
            pooled_entity[name] += int(audit["entity_categories"][name])
        for name in TRUTH_CATEGORIES:
            pooled_truth[name] += int(audit["truth_categories"][name])
        for rule, value in (audit.get("wrong_identity_matches") or {}).items():
            pooled_wrong[rule] = pooled_wrong.get(rule, 0) + int(value)
        for name in CENTROID_ENTITY_CATEGORIES:
            pooled_centroid_entity[name] += int(audit["centroid_entity_categories"][name])
        for name in CENTROID_TRUTH_CATEGORIES:
            pooled_centroid_truth[name] += int(audit["centroid_truth_categories"][name])
        for scope, row in (audit.get("birth_reasons") or {}).items():
            for name in BIRTH_REASONS:
                pooled_births[scope][name] += int(row[name])
        for name, value in ((audit.get("identity_attribution") or {}).get("counts") or {}).items():
            pooled_attribution[name] = pooled_attribution.get(name, 0) + int(value)
        if audit.get("dedup"):
            pooled_dedup["ticks"] += int(audit["dedup"]["ticks"])
            pooled_dedup["folds"] += int(audit["dedup"]["folds"])
            for name, value in (audit["dedup"].get("folds_by_identity") or {}).items():
                pooled_dedup["folds_by_identity"][name] = pooled_dedup["folds_by_identity"].get(name, 0) + int(value)
            for name, value in (audit["dedup"].get("folds_by_coobservation") or {}).items():
                pooled_dedup["folds_by_coobservation"][name] = pooled_dedup["folds_by_coobservation"].get(name, 0) + int(value)
            for name, row in audit["dedup"]["pairs_after_fold"].items():
                target = pooled_dedup["pairs_after_fold"].setdefault(name, {"pairs": 0, "pass": {}})
                target["pairs"] += int(row["pairs"])
                for gate, value in row["pass"].items():
                    target["pass"][gate] = target["pass"].get(gate, 0) + int(value)
        for row in audit.get("existence_tally") or []:
            pooled_existence[tuple(row[:-1])] = pooled_existence.get(tuple(row[:-1]), 0) + int(row[-1])
        for row in audit.get("association_tally") or []:
            pooled_association[tuple(row[:-1])] = pooled_association.get(tuple(row[:-1]), 0) + int(row[-1])
        loss = audit.get("loss_tally") or {}
        for row in loss.get("events") or []:
            pooled_loss_events[tuple(row[:-1])] = pooled_loss_events.get(tuple(row[:-1]), 0) + int(row[-1])
        for cause, row in (loss.get("intervals") or {}).items():
            target = pooled_loss_intervals.setdefault(cause, {"intervals": 0, "recovered": 0, "object_gone": 0, "censored": 0, "frames": 0,
                                                              "bins": {label: 0 for _, label in LOSS_DURATION_BINS}})
            for name in ("intervals", "recovered", "object_gone", "censored", "frames"):
                target[name] += int(row[name])
            for label, value in row["bins"].items():
                target["bins"][label] += int(value)
        for name in pooled_uncarried:
            pooled_uncarried[name] += int(loss.get(name) or 0)
        for group, row in audit["truth_by_group"].items():
            target = pooled_group.setdefault(group, {name: 0 for name in TRUTH_CATEGORIES})
            for name in TRUTH_CATEGORIES:
                target[name] += int(row[name])
        for type_name, row in audit["truth_by_type"].items():
            target = pooled_type.setdefault(type_name, {name: 0 for name in TRUTH_CATEGORIES})
            for name in TRUTH_CATEGORIES:
                target[name] += int(row[name])
        episodes.append({
            "episode_id": payload["episode_id"], "frames": payload["frames"], "config": payload["config"],
            "code_commit": payload["code_commit"], "report": payload.get("report"), "dormancy_override": payload.get("dormancy_override"),
            "oracle": payload.get("oracle"),
            "final_entities_by_state": payload["final_entities_by_state"],
            "identity_attribution": (audit.get("identity_attribution") or {}).get("records"),
            "rules_f1": {rule: audit["rules"][rule]["f1"] for rule in RULES},
            "iou_0.3_secondary": audit["rules"]["iou_0.3_secondary"],
            "centroid_primary": audit["rules"]["centroid_within_0.5m"],
            "entity_categories": audit["entity_categories"], "truth_categories": audit["truth_categories"],
            "centroid_entity_categories": audit["centroid_entity_categories"], "centroid_truth_categories": audit["centroid_truth_categories"],
            "birth_reasons": audit.get("birth_reasons"), "dedup_folds": (audit.get("dedup") or {}).get("folds"),
            "in_memory_entities_per_frame_mean": audit["in_memory_entities_per_frame_mean"],
            "own_object_iou_when_near": audit["own_object_iou_when_near"],
            "own_object_centroid_distance_m": audit["own_object_centroid_distance_m"],
            "decomposition_totals": payload.get("decomposition_totals"), "trajectory_sha256": payload.get("trajectory_sha256"),
            "audit_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    _require(bool(episodes), f"no_audits_found:{output_root}/*/{arm}")
    _require(len(oracle_settings) == 1, "audits_mix_oracle_settings")  # ruling 88-2: one cell per merge
    _require(len(recall_counts) == 1, "audits_mix_recall_global_counts")  # ruling 89-1: one k' per merge (None = pre-v10 audit)
    _require(len(mask_sources) == 1, "audits_mix_mask_sources")  # ruling 84-1 (b): one front end per merge (None = pre-v11 audit)
    _require(len(modes) == 1, "audits_mix_metrics_only_and_full")  # ruling 104-4 (1): one mode per merge
    if modes == {True}:
        return {
            "schema_version": MERGED_SCHEMA_VERSION, "metrics_only": True, "oracle": None,
            "recall_global_count": next(iter(recall_counts)), "mask_source": next(iter(mask_sources)),
            "stage": "S2-05 node audit (metrics only, pooled)", "arm": arm, "output_root": str(output_root),
            "code_commits": sorted(commits), "episodes": len(episodes),
            "pooled_decomposition_totals": pooled_decomposition,
            "per_episode": episodes,
            "private_ids_exported": False,
        }
    return {
        "schema_version": MERGED_SCHEMA_VERSION, "metrics_only": False,
        "oracle": json.loads(next(iter(oracle_settings))),
        "recall_global_count": next(iter(recall_counts)),
        "mask_source": next(iter(mask_sources)),
        "stage": "S2-05 node audit (read-only, pooled)", "arm": arm, "output_root": str(output_root),
        "code_commits": sorted(commits), "episodes": len(episodes),
        "pooled_rules": {rule: _prf(s["matched"], s["predicted"], s["truth"]) for rule, s in pooled_rules.items()},
        "pooled_entity_categories": pooled_entity, "pooled_truth_categories": pooled_truth,
        "pooled_centroid_entity_categories": pooled_centroid_entity, "pooled_centroid_truth_categories": pooled_centroid_truth,
        "pooled_birth_reasons": pooled_births, "pooled_dedup": pooled_dedup, "pooled_wrong_identity_matches": pooled_wrong,
        "pooled_identity_attribution": pooled_attribution,
        "existence_tally_fields": list(EXISTENCE_TALLY_FIELDS),
        "pooled_existence_tally": [[*row, count] for row, count in sorted(pooled_existence.items())],
        "association_tally_fields": list(ASSOCIATION_TALLY_FIELDS),
        "pooled_association_tally": [[*row, count] for row, count in sorted(pooled_association.items())],
        "pooled_loss_tally": {"rule": LOSS_RULE, "events": [[*row, count] for row, count in sorted(pooled_loss_events.items())],
                              "intervals": {cause: pooled_loss_intervals[cause] for cause in sorted(pooled_loss_intervals)}, **pooled_uncarried},
        "pooled_truth_by_group": {group: row for group, row in sorted(pooled_group.items())},
        "pooled_truth_by_type": {name: row for name, row in sorted(pooled_type.items(), key=lambda item: (-sum(item[1].values()), item[0]))[:40]},
        "pooled_decomposition_totals": pooled_decomposition,
        "per_episode": episodes,
        "private_ids_exported": False,
    }


def merge(args: argparse.Namespace) -> int:
    try:
        merged = merge_audits(Path(args.output_root).resolve(), args.arm)
    except NodeAuditError as exc:
        print(f"[node-audit] refused: {exc}", file=sys.stderr)
        return 2
    results = Path(args.results)
    results.parent.mkdir(parents=True, exist_ok=True)
    results.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    if merged["metrics_only"]:
        print(f"[node-audit] merged {merged['episodes']} metrics-only audits of {args.arm}; wrote {results}")
        return 0
    pooled = merged["pooled_rules"]
    print(f"[node-audit] merged {merged['episodes']} episodes of {args.arm}: " +
          ", ".join(f"{rule} F1 {pooled[rule]['f1']:.3f}" if pooled[rule]["f1"] is not None else f"{rule} F1 null" for rule in RULES))
    print(f"[node-audit] wrote {results}")
    return 0


def compare(args: argparse.Namespace) -> int:
    """Ruling 104-2: the audit equivalence probe over one episode's full and metrics-only audits."""

    try:
        result = compare_audits(json.loads(Path(args.full).read_text(encoding="utf-8")),
                                json.loads(Path(args.metrics_only).read_text(encoding="utf-8")))
    except NodeAuditError as exc:
        print(f"[node-audit] refused: {exc}", file=sys.stderr)
        return 2
    result.update({"full": str(args.full), "metrics_only_audit": str(args.metrics_only)})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"[node-audit] compare {result['arm']} {result['episode_id']}: identical={result['identical']}"
          + ("" if result["identical"] else f", differing {result['differing_fields']}"))
    return 0 if result["identical"] else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="audit one episode under one arm and configuration")
    run_parser.add_argument("--cache-root", required=True)
    run_parser.add_argument("--episode-root", required=True)
    run_parser.add_argument("--geometry-root", required=True)
    run_parser.add_argument("--episode-id", required=True)
    run_parser.add_argument("--arm", required=True)
    run_parser.add_argument("--config", default=None, help="one configuration (with --output-root), or use --configs")
    run_parser.add_argument("--descriptor", required=True)
    run_parser.add_argument("--weights", default=None)
    run_parser.add_argument("--heads", default=None)
    run_parser.add_argument("--output-root", default=None)
    run_parser.add_argument("--configs", default=None,
                            help="ruling 104-7: a JSON list of {config, output_root}: several configurations of this arm on this episode "
                                 "in one job; the cache is verified once, each configuration runs from scratch into its own root")
    run_parser.add_argument("--skip-existing", action="store_true",
                            help="resume: keep a configuration whose finished audit is already there (same episode, arm, config, mode)")
    run_parser.add_argument("--frames", type=int, default=None)
    run_parser.add_argument("--device", default="cpu")
    run_parser.add_argument("--allow-dirty", action="store_true")
    run_parser.add_argument("--dedup-override", default=None, help="diagnostic: JSON of shared-dedup values to replace (never a run of record)")
    run_parser.add_argument("--dormancy-override", type=int, default=None,
                            help="diagnostic (ruling 80-3): replace the shared dormancy missed-opportunity limit; a huge value switches dormancy off")
    run_parser.add_argument("--oracle-association", action="store_true",
                            help="diagnostic (ruling 88-2 (i)): the teacher's association targets decide; never a run of record")
    run_parser.add_argument("--oracle-existence", default=None, choices=("node_primary", "centroid_only"),
                            help="diagnostic (ruling 88-2 (i)): the teacher's existence labels under this place rule decide")
    run_parser.add_argument("--oracle-recall", action="store_true",
                            help="diagnostic (ruling 88-2 (i)): append the earliest carrier of each fragment's dominant object to its recall")
    run_parser.add_argument("--trace-residuals", action="store_true",
                            help="ruling 93 revised, read-only: trace where each lingering stale entity got stuck (residual_trace)")
    run_parser.add_argument("--recall-global-count", type=int, default=None,
                            help="diagnostic (ruling 89-1): replace the global recall channel's k' for this run; recorded in the payload")
    from vsmt import lean_assignment as la

    run_parser.add_argument("--mask-source", default=None, choices=tuple(la.REID_WEIGHTS_SHA256_BY_MASK_SOURCE),
                            help="ruling 84-1 (b): the mask source the episode must be sealed with; omitted, the seal's own source is used. "
                                 "The ReID weights must be the head pinned for that source")
    run_parser.add_argument("--metrics-only", action="store_true",
                            help="ruling 104-4 (1): the run of record -- the runner and the teacher's report without the diagnostic blocks "
                                 "of v2-v10 (audit null); refused together with any diagnostic option")
    run_parser.add_argument("--manifest-split", default=None, choices=("train", "validation"),
                            help="ruling 104-6: refuse an episode that is not in this split of the S3 manifest (every S3-03 audit names it)")
    run_parser.set_defaults(func=run)
    merge_parser = sub.add_parser("merge", help="pool the audits of one arm into a results/ report")
    merge_parser.add_argument("--output-root", required=True)
    merge_parser.add_argument("--arm", required=True)
    merge_parser.add_argument("--results", required=True)
    merge_parser.set_defaults(func=merge)
    compare_parser = sub.add_parser("compare", help="ruling 104-2: a full and a metrics-only audit of one episode, field by field")
    compare_parser.add_argument("--full", required=True)
    compare_parser.add_argument("--metrics-only", required=True)
    compare_parser.add_argument("--out", required=True)
    compare_parser.set_defaults(func=compare)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
