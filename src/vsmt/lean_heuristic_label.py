"""HeuristicLabel's labels (D-224-SW ruling T, D-224-X X3/X4, ruling 104-1 1c): ELU-P's public decisions on any trajectory.

白话：HeuristicLabel 这个消融回答“把私有实例真值换成公开启发式的决定当标签，学到的东西会差多少”。它的标签是 ELU-P 在预登记
``rollout_config``（θ_a 0.7、无距离门、自由空间权重 1.0、撤回门 0.0）加 S3 拟合量下、对同一帧封存特征行会作的决定：
  * 关联：ELU-P 的门 logit（余弦 ≥ θ_a 记余弦、否则哨兵；新建 logit＝θ_a）在同一召回列上用同一求解器联合求解，每个色块分到的
    列（某个实体或它自己的新建列）就是它的目标；
  * 存在：对这一帧可判定的每个实体（应可见、未被这条轨迹分配、未撤回），若 ELU-P 这一帧会把某个色块绑给它，记 present；否则
    取 ELU-P 的对数几率——与 ELU-P 臂同一递推（每个可判定帧减去衰减与覆盖乘权重，每次匹配加增益），沿这条轨迹的可判定行与匹配
    累积——低于撤回门记 gone，否则 present。
这个“影子”对数几率等价于裁决 89-2 的历史摘要的线性式，但按 ELU-P 臂的递推逐步算，所以在 ELU-P 自己的轨迹上与臂的决定逐位相同
（裁决 104-2 的 G4 门：逐行比较，不一致 0 行）；在 HeuristicLabel 自己的轨迹上，它就是“ELU-P 看到同样的观察序列会怎么判”。
输入是 runner 的一步产物（阶段 A、阶段 B、回执、提交后的记忆），输出一条与 teacher 记录同格式的训练记录。所有色块与可判定行都有
标签、都进损失。它只读公开特征行与三个拟合量（私有真值只经这三个标量进来，合同已写明），不读任何私有文件，也不改 runner。
"""

from __future__ import annotations

from typing import Any, Mapping

from cpmt.hashing import clone_json

from vsmt import lean_arms as arms
from vsmt import lean_assignment as la

STAGE = "vsmt.lean.heuristic_label.v1"
LABEL_RULE = arms.HEURISTIC_LABEL_RULE  # the string the S0-05 HeuristicLabel block carries (ruling 104-1 1c)
LABELLER_ARM = "ELU-P"


class LeanHeuristicLabelError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanHeuristicLabelError(code)


def validate_label_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """An ELU-P configuration at the registered rollout_config, no distance gate, with three finite fitted values (X4)."""

    from vsmt import lean_runner as lr

    checked = lr.validate_arm_config(LABELLER_ARM, dict(config))
    for name in arms.ROLLOUT_CONFIG_PARAMETERS:
        _require(checked[name] == arms.ROLLOUT_CONFIG[name], f"label_config_not_the_rollout_config:{name}")
    _require(checked[arms.ROLLOUT_CONFIG_GATE_PARAMETER] is None, "label_config_has_a_distance_gate")
    for name in arms.ELU_P_FITTED:
        _require(type(checked[name]) in (int, float) and type(checked[name]) is not bool, f"label_config_fitted_value_invalid:{name}")
    return checked


class HeuristicLabeller:
    """The stateful labeller of one episode: feed it every runner step in order."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = validate_label_config(config)
        self.log_odds: dict[str, float] = {}
        self.totals = {"frames": 0, "fragments": 0, "fragments_birth": 0, "existence_rows": 0, "existence_gone": 0,
                       "bound_by_the_labeller_while_eligible": 0}
        self.reproduction: dict[str, int] | None = None

    def _solve(self, stage_a: Mapping[str, Any]) -> dict[str, str]:
        logits = arms.gate_association_logits(stage_a, theta_a=self.config["theta_a"], d_a=self.config["d_a"],
                                              reactivates_retracted=arms.REACTIVATES_RETRACTED[LABELLER_ARM])
        solution = la.solve_frame(stage_a, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])
        return {str(fragment): str(column) for fragment, column in solution["assignment"].items()}

    def label(self, step: Mapping[str, Any], *, arm: str, arm_config: Mapping[str, Any]) -> dict[str, Any]:
        """One frame's HeuristicLabel training record, and on ELU-P's own trajectory the comparison with ELU-P's decisions."""

        from vsmt import lean_model

        # AssocOnly skips the existence step, so its receipts list no eligible row and nothing could be labelled gone
        _require(arm != "AssocOnly", "heuristic_labels_need_the_existence_step")
        stage_a, stage_b, receipt = step["stage_a"], step["stage_b"], step["receipt"]
        assignment = self._solve(stage_a)
        _require(set(assignment) == {str(f) for f in stage_a["rows"]}, "labeller_assignment_does_not_cover_the_fragments")
        bound = {column for column in assignment.values() if not column.startswith(la.BIRTH_COLUMN_PREFIX)}
        targets = {fragment: ({"status": "birth", "target": column} if column.startswith(la.BIRTH_COLUMN_PREFIX)
                              else {"status": "labelled", "target": column})
                   for fragment, column in assignment.items()}
        order = list(stage_b["existence_feature_order"])
        candidates = [str(entity_id) for entity_id in receipt["existence"]["candidates"]]
        rows_by_id = {str(row["entity_id"]): row for row in stage_b["existence_rows"]}
        eligible = [rows_by_id[entity_id] for entity_id in candidates]
        before = dict(self.log_odds)
        result = arms.elu_p_existence(eligible, order, state=before, initial_log_odds=self.config["initial_log_odds"],
                                      persistence_log_decay_per_tick=self.config["persistence_log_decay_per_tick"],
                                      free_space_weight=self.config["free_space_weight"], retract_threshold=self.config["retract_threshold"])
        decisions = result["decisions"]
        labels = {entity_id: {"status": "present" if entity_id in bound or decisions[entity_id] == "NOOP" else "gone"}
                  for entity_id in candidates}
        # the state follows this trajectory: its eligible rows (above), then its own matches; an illegal frame rolls back,
        # and entities that left the memory (folded by the shared de-duplication) are dropped, as the runner does for ELU-P
        matched = sorted(str(column) for column in receipt["assignment"].values() if not str(column).startswith(la.BIRTH_COLUMN_PREFIX))
        after = arms.elu_p_observe_matches(result["state"], matched, initial_log_odds=self.config["initial_log_odds"],
                                           match_gain=self.config["match_gain"])
        if receipt.get("illegal_program") is not None:
            after = before
        live = {str(entity["entity_id"]) for entity in step["state"]["memory"]["entities"]}
        self.log_odds = {key: value for key, value in after.items() if key in live}
        record = lean_model.validate_training_record({
            "stage_a": stage_a, "targets": targets, "existence_rows": eligible, "existence_feature_order": order,
            "existence_labels": labels,
        })
        self.totals["frames"] += 1
        self.totals["fragments"] += len(targets)
        self.totals["fragments_birth"] += sum(1 for t in targets.values() if t["status"] == "birth")
        self.totals["existence_rows"] += len(labels)
        self.totals["existence_gone"] += sum(1 for label in labels.values() if label["status"] == "gone")
        self.totals["bound_by_the_labeller_while_eligible"] += sum(1 for entity_id in candidates if entity_id in bound)
        if arm == LABELLER_ARM and dict(arm_config) == self.config:  # ruling 104-2 G4: on ELU-P's own trajectory, row by row
            if self.reproduction is None:
                self.reproduction = {"fragments": 0, "fragment_mismatches": 0, "existence_rows": 0, "existence_mismatches": 0}
            actual_assignment = {str(f): str(c) for f, c in receipt["assignment"].items()}
            actual_decisions = {str(e): str(d) for e, d in receipt["existence"]["decisions"].items()}
            self.reproduction["fragments"] += len(assignment)
            self.reproduction["fragment_mismatches"] += sum(1 for f, c in assignment.items() if actual_assignment.get(f) != c)
            self.reproduction["existence_rows"] += len(candidates)
            self.reproduction["existence_mismatches"] += sum(1 for e in candidates if actual_decisions.get(e) != decisions[e])
        return {"training_record": record, "assignment": assignment, "decisions": decisions}

    def summary(self) -> dict[str, Any]:
        return {"stage": STAGE, "rule": LABEL_RULE, "config": clone_json(self.config), "totals": dict(self.totals),
                "reproduction": None if self.reproduction is None else dict(self.reproduction)}


__all__ = ["HeuristicLabeller", "LABEL_RULE", "LeanHeuristicLabelError", "STAGE", "validate_label_config"]
