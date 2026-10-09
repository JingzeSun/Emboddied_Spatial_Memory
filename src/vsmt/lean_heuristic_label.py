"""HeuristicLabel's labels (D-224-SW ruling T, D-224-X X3/X4, ruling 104-1 1c): ELU-P's public decisions on any trajectory.

The HeuristicLabel ablation measures what the learned heads lose when the private-instance teacher is replaced by a
public heuristic. Its labels are the decisions ELU-P would make on the same sealed feature rows of a frame, at the
registered ``rollout_config`` (theta_a 0.7, no distance gate, free-space weight 1.0, retract threshold 0.0) with the
three values fitted for S3:
  * association: ELU-P's gate logits (the cosine when cosine >= theta_a, otherwise the sentinel; birth logit theta_a)
    are solved jointly over the same recall columns by the same solver; each fragment's assigned column (an entity or
    its own birth column) is its target;
  * existence: every entity eligible this frame (should be visible, not assigned on this trajectory, not retracted) is
    present if ELU-P binds a fragment to it this frame; otherwise it takes ELU-P's log-odds, updated by the ELU-P arm's
    recursion (each eligible frame subtracts the decay plus weight x free-space coverage, each match adds the gain)
    along this trajectory's eligible rows and matches, and is gone below the retract threshold, present otherwise.
This shadow log-odds equals the linear form of the ruling-89-2 history summary but is computed step by step with the
ELU-P recursion, so on ELU-P's own trajectory it reproduces the arm's decisions exactly (ruling 104-2 gate G4: row-by-row
comparison, 0 mismatching rows); on HeuristicLabel's own trajectory it is what ELU-P would decide on the same
observation sequence.
Input: one runner step (stage A, stage B, receipt, committed memory). Output: one training record in the teacher's
format; every fragment and every eligible row is labelled and enters the loss. Reads only public feature rows and the
three fitted values (private truth enters only through these three scalars, as the contract states); reads no private
file and does not modify the runner.
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
