"""Where a lingering stale entity got stuck (ruling 93 revised, 2026-09-30; read-only, changes no decision).

An optional diagnostic of the node audit (``lean_s2_05_node_audit.py run --trace-residuals``, refused under
``--metrics-only``); no run of record uses it.  The missing-residual rate counts removed or moved objects that still
have a record at their old place, not why that record was never retracted.  Per frame this follows each such
object's stale entities (same identity, centroid within delta_moved of the old place: the rule of
``lean_teacher.missing_residual_rate``) and records their status -- bound to a fragment, existence candidate, excluded
as not visible, retracted, or without an existence row -- and, for a candidate, the teacher's existence label, the
learned head's logit (as decided, with the existence-prior correction, and uncorrected) and the decision.  At the end
every object still residual in the last frame gets the first category that applies (``CATEGORY_ORDER``):
  * carrier_rebound -- a stale entity was bound to a fragment again after the object left;
  * retracted_then_back -- a stale entity was retracted, yet an entity of the same identity remains at the old place;
  * never_eligible -- no stale entity ever became an existence candidate;
  * eligible_teacher_never_gone -- a candidate, but the teacher never labelled it gone;
  * eligible_gone_below_threshold -- a candidate labelled gone, never retracted.
It is not a metric and changes no decision or label.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

MISSING_KINDS = ("remove", "move")
CATEGORY_ORDER = ("carrier_rebound", "retracted_then_back", "never_eligible", "eligible_teacher_never_gone",
                  "eligible_gone_below_threshold")


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


class ResidualTracer:
    def __init__(self, *, teacher: Any, learned: Any, delta_moved_m: float, identity_of: Any) -> None:
        self.teacher = teacher
        self.learned = learned
        self.delta = float(delta_moved_m)
        self.identity_of = identity_of          # (entity) -> {"resolvable", "key"}
        self.timelines: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self.last_residual: list[str] = []
        self.ever_residual: set[str] = set()

    def _watched(self) -> dict[str, list[float]]:
        return {key: list(self.teacher.old_place[key]["centroid_m"]) for key, kind in self.teacher.interventions.items()
                if kind in MISSING_KINDS and key in self.teacher.old_place}

    def observe(self, step: Mapping[str, Any], labelled: Mapping[str, Any]) -> None:
        frame_index = int(labelled["frame_index"])
        missing = labelled.get("missing_residual")
        if missing is None:
            return
        self.last_residual = list(missing.get("residual_keys") or [])
        self.ever_residual.update(self.last_residual)
        watched = self._watched()
        if not watched:
            return
        receipt = step["receipt"]
        existence = receipt["existence"]
        candidates = set(existence["candidates"])
        not_visible = set(existence["excluded_not_visible"])
        retracted = set(existence["excluded_retracted"])
        assigned = {str(c) for c in receipt["assignment"].values() if not str(c).startswith("birth:")}
        rows = {str(r["entity_id"]): r for r in step["stage_b"]["existence_rows"]}
        order = step["stage_b"]["existence_feature_order"]
        labels = labelled.get("existence_labels") or {}
        for entity in step["memory_before"]["entities"]:
            near = [key for key, old in watched.items() if _distance(entity["centroid_m"], old) <= self.delta]
            if not near:
                continue
            identity = self.identity_of(entity)
            if not identity["resolvable"] or identity["key"] not in near:
                continue
            key, eid = identity["key"], str(entity["entity_id"])
            if eid in assigned:
                status = "assigned"
            elif eid in candidates:
                status = "candidate"
            elif eid in not_visible:
                status = "not_visible"
            elif eid in retracted or entity["state"] == "retracted":
                status = "retracted"
            else:
                status = "no_existence_row"
            item: dict[str, Any] = {"frame": frame_index, "state": entity["state"], "status": status}
            if status == "candidate":
                item["label"] = (labels.get(eid) or {}).get("status")
                item["decision"] = existence["decisions"].get(eid)
                if self.learned is not None and eid in rows and not getattr(self.learned, "assoc_only", False):
                    logit = float(self.learned.existence_logits([rows[eid]], order)[eid])
                    offset = float(getattr(getattr(self.learned, "heads", None), "existence_logit_offset", 0.0) or 0.0)
                    item["logit_decision"] = logit
                    item["logit_uncorrected"] = logit - offset
            self.timelines.setdefault(key, {}).setdefault(eid, []).append(item)

    @staticmethod
    def classify(entities: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[str, dict[str, Any]]:
        rows = [item for timeline in entities.values() for item in timeline]
        counts = {"frames": len(rows), "assigned": sum(r["status"] == "assigned" for r in rows),
                  "candidate": sum(r["status"] == "candidate" for r in rows),
                  "candidate_labelled_gone": sum(r["status"] == "candidate" and r.get("label") == "gone" for r in rows),
                  "retract_decisions": sum(r.get("decision") == "RETRACT" for r in rows),
                  "not_visible": sum(r["status"] == "not_visible" for r in rows),
                  "retracted": sum(r["status"] == "retracted" for r in rows),
                  "no_existence_row": sum(r["status"] == "no_existence_row" for r in rows),
                  "entities": len(entities)}
        gone_logits = [r["logit_uncorrected"] for r in rows if r.get("label") == "gone" and "logit_uncorrected" in r]
        counts["max_uncorrected_logit_when_gone"] = max(gone_logits) if gone_logits else None
        if counts["assigned"]:
            category = "carrier_rebound"
        elif counts["retract_decisions"]:
            category = "retracted_then_back"
        elif not counts["candidate"]:
            category = "never_eligible"
        elif not counts["candidate_labelled_gone"]:
            category = "eligible_teacher_never_gone"
        else:
            category = "eligible_gone_below_threshold"
        return category, counts

    def report(self) -> dict[str, Any]:
        final = {}
        for key in sorted(self.last_residual):
            category, counts = self.classify(self.timelines.get(key, {}))
            final[key] = {"category": category, **counts, "kind": self.teacher.interventions.get(key)}
        tally = {name: sum(1 for v in final.values() if v["category"] == name) for name in CATEGORY_ORDER}
        return {"final_residual_objects": len(final), "ever_residual_objects": len(self.ever_residual),
                "categories": tally, "per_object": final,
                "definition": "carriers: same identity and within delta_moved_m of the old centroid, the missing_residual_rate rule; "
                              "status per frame after the window from the runner receipt; categories in CATEGORY_ORDER precedence"}
