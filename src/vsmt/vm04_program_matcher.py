"""Public, receipt-bound construction matcher for VM-04 programs.

The matcher is a construction gate, not a semantic oracle.  It consumes only
the sealed public packet, prior public memory, route/visibility receipts and
explicit matcher values.  Private identity may grade a sealed construction
later, but cannot change this receipt or insert a missing program candidate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from typing import Any, Mapping

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json

from .contracts import build_adapter_input, canonical_sha256
from .graph_ops import (
    association_components,
    association_score,
    covering_free_space_times,
    observation_state,
    open_nodes,
    place_scaffold_key,
    validate_threshold,
)
from .vm04_observation_runner import assess_route_receipt
from .vm04_program_construction import (
    ARTIFACT_SCHEMA,
    PLAN_SCHEMA,
    validate_split_merge_artifact_receipt,
)


MATCHER_RECEIPT_SCHEMA = "vsmt-vm04-public-program-matcher-receipt-v1"
LEARNED_STRUCTURE_KINDS = {"entity", "surface", "fragment"}


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _positive(value: Any, name: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    result = float(value)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


@dataclass(frozen=True)
class Vm04ProgramMatcherConfig:
    """All matcher and negative-evidence values are explicit and default-free."""

    association_rules: Mapping[str, Mapping[str, float]]
    minimum_region_reliability: float
    minimum_unique_score_margin: float
    minimum_relation_reliability: float
    free_space_reliability_threshold: float
    support_envelope_reliability_threshold: float
    support_envelope_margin_m: float
    minimum_free_space_time_separation_s: float
    minimum_independent_negative_observations: int

    def __post_init__(self) -> None:
        if set(self.association_rules) != LEARNED_STRUCTURE_KINDS:
            raise ValueError(
                "matcher association rules must cover entity/surface/fragment"
            )
        expected = {
            "visual_weight", "geometry_weight", "geometry_scale_m",
            "association_threshold",
        }
        for kind, rule in self.association_rules.items():
            if type(rule) is not dict or set(rule) != expected:
                raise ValueError(f"matcher {kind} association rule is malformed")
            visual = validate_threshold(
                rule["visual_weight"], f"{kind}.visual_weight", low=0.0, high=1.0,
            )
            geometry = validate_threshold(
                rule["geometry_weight"], f"{kind}.geometry_weight",
                low=0.0, high=1.0,
            )
            if not math.isclose(visual + geometry, 1.0, abs_tol=1e-12):
                raise ValueError("matcher association weights must sum to one")
            _positive(rule["geometry_scale_m"], f"{kind}.geometry_scale_m")
            validate_threshold(
                rule["association_threshold"],
                f"{kind}.association_threshold", low=0.0, high=1.0,
            )
        for name in (
            "minimum_region_reliability", "minimum_unique_score_margin",
            "minimum_relation_reliability", "free_space_reliability_threshold",
            "support_envelope_reliability_threshold",
        ):
            validate_threshold(getattr(self, name), name, low=0.0, high=1.0)
        if (type(self.support_envelope_margin_m) not in {int, float} or
                not math.isfinite(float(self.support_envelope_margin_m)) or
                self.support_envelope_margin_m < 0.0):
            raise ValueError("support_envelope_margin_m must be nonnegative")
        _positive(
            self.minimum_free_space_time_separation_s,
            "minimum_free_space_time_separation_s",
        )
        if (type(self.minimum_independent_negative_observations) is not int or
                self.minimum_independent_negative_observations < 2):
            raise ValueError(
                "minimum_independent_negative_observations must be at least two"
            )


def matcher_config_sha256(config: Vm04ProgramMatcherConfig) -> str:
    if type(config) is not Vm04ProgramMatcherConfig:
        raise ValueError("config must be Vm04ProgramMatcherConfig")
    return canonical_sha256(asdict(config))


def _validate_construction_plan(
    plan: Mapping[str, Any], prior_memory: Mapping[str, Any],
) -> dict[str, Any]:
    value = clone_json(dict(plan))
    seal = value.pop("construction_plan_sha256", None)
    if value.get("schema_version") != PLAN_SCHEMA or seal != canonical_sha256(value):
        raise ValueError("program construction plan seal mismatch")
    validate_graph(prior_memory, verify_hash=True)
    if value.get("prior_memory_sha256") != prior_memory.get("graph_hash"):
        raise ValueError("program matcher prior memory does not match its plan")
    value["construction_plan_sha256"] = seal
    return value


def _match_rows(
    regions: list[Mapping[str, Any]], nodes: list[Mapping[str, Any]],
    config: Vm04ProgramMatcherConfig,
) -> list[dict[str, Any]]:
    rows = []
    for region in regions:
        kind = str(region["structure_kind"])
        if (kind not in LEARNED_STRUCTURE_KINDS or
                float(region["reliability"]) < config.minimum_region_reliability):
            continue
        rule = config.association_rules[kind]
        comparisons = []
        for node in nodes:
            if node.get("node_type") != kind or observation_state(node) is None:
                continue
            components = association_components(
                region, node, geometry_scale_m=rule["geometry_scale_m"],
            )
            if components is None:
                continue
            score = association_score(
                region, node,
                visual_weight=rule["visual_weight"],
                geometry_weight=rule["geometry_weight"],
                geometry_scale_m=rule["geometry_scale_m"],
            )
            comparisons.append({
                "node_version_id": node["node_version_id"],
                "node_id": node["node_id"],
                "lifecycle": node["lifecycle"],
                **components,
                "association_score": float(score),
            })
        comparisons.sort(key=lambda row: (
            -row["association_score"], row["node_version_id"],
        ))
        threshold = float(rule["association_threshold"])
        qualified = [
            row for row in comparisons if row["association_score"] >= threshold
        ]
        if not qualified:
            status = "unmatched"
            selected = None
        else:
            margin = (qualified[0]["association_score"] -
                      qualified[1]["association_score"]
                      if len(qualified) > 1 else 1.0)
            if margin < config.minimum_unique_score_margin:
                status = "ambiguous"
                selected = None
            else:
                status = "unique_match"
                selected = qualified[0]["node_version_id"]
        rows.append({
            "region_id": region["region_id"],
            "mask_sha256": region["mask_sha256"],
            "structure_kind": kind,
            "public_reliability": float(region["reliability"]),
            "association_threshold": threshold,
            "match_status": status,
            "selected_node_version_id": selected,
            "comparisons": comparisons,
        })
    rows.sort(key=lambda row: row["region_id"])
    return rows


def _node_by_version(
    nodes: list[Mapping[str, Any]], version_id: str,
) -> Mapping[str, Any] | None:
    return next(
        (node for node in nodes if node["node_version_id"] == version_id), None,
    )


def _negative_evidence_count(
    node: Mapping[str, Any], free_spaces: list[Mapping[str, Any]],
    config: Vm04ProgramMatcherConfig,
) -> int:
    return len(covering_free_space_times(
        node, free_spaces,
        minimum_reliability=config.free_space_reliability_threshold,
        target_expansion_m=config.support_envelope_margin_m,
        minimum_time_separation_s=config.minimum_free_space_time_separation_s,
        support_reliability_threshold=(
            config.support_envelope_reliability_threshold
        ),
    ))


def _target_region_row(
    match_rows: list[Mapping[str, Any]], route_plan: Mapping[str, Any],
    route_receipt: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    terminal_index = route_plan["terminal_reobservation_indices"][-1]
    terminal = next(
        row for row in route_receipt["observations"]
        if row["observation_index"] == terminal_index
    )
    mask_sha = terminal["visibility_assessment"][
        "current_public_support_sha256"
    ]
    matched = [row for row in match_rows if row["mask_sha256"] == mask_sha]
    if len(matched) > 1:
        raise ValueError("terminal public support matches multiple regions")
    return matched[0] if matched else None


def _matched_place_version(
    place_region: Mapping[str, Any], nodes: list[Mapping[str, Any]],
) -> str | None:
    key = place_scaffold_key(place_region)
    matches = [
        node["node_version_id"] for node in nodes
        if node.get("node_type") == "place"
        and (observation_state(node) or {}).get("place_scaffold_key") == key
    ]
    if len(matches) > 1:
        raise ValueError("place scaffold key maps to multiple open versions")
    return matches[0] if matches else None


def make_program_matcher_receipt(
    *, construction_plan: Mapping[str, Any], prior_memory: Mapping[str, Any],
    current_packet: Mapping[str, Any], route_plan: Mapping[str, Any],
    route_receipt: Mapping[str, Any], observation_contract: Mapping[str, Any],
    config: Vm04ProgramMatcherConfig,
    artifact_plan: Mapping[str, Any] | None = None,
    artifact_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a public construction verdict without asserting identity truth."""

    plan = _validate_construction_plan(construction_plan, prior_memory)
    if plan["matcher_config_sha256"] != matcher_config_sha256(config):
        raise ValueError("program construction plan does not bind matcher config")
    if (plan["episode_id"] != route_plan.get("episode_id") or
            plan["program"] != route_plan.get("program") or
            plan["visibility_subject_seal_sha256"] !=
            route_plan.get("visibility_subject_seal_sha256")):
        raise ValueError("program plan and route plan bindings differ")
    route_verdict = assess_route_receipt(
        route_receipt, plan=route_plan, contract=observation_contract,
    )
    if not route_verdict["constructed"]:
        raise ValueError("program matcher requires a constructed public route")
    model_input = build_adapter_input(current_packet, prior_memory)
    nodes = open_nodes(prior_memory, include_dormant=True)
    regions = model_input["region_observations"]
    rows = _match_rows(regions, nodes, config)
    target = _target_region_row(rows, route_plan, route_receipt)
    refs = plan["precondition_refs"]
    program = plan["program"]
    failures: list[str] = []
    negative_count = 0
    relation_evidence = None

    def require_target() -> Mapping[str, Any] | None:
        if target is None:
            failures.append("terminal_public_support_does_not_select_reliable_region")
        return target

    def target_is(version_id: str, lifecycles: set[str]) -> None:
        row = require_target()
        if row is None:
            return
        if (row["match_status"] != "unique_match" or
                row["selected_node_version_id"] != version_id):
            failures.append("target_region_does_not_uniquely_match_registered_node")
            return
        node = _node_by_version(nodes, version_id)
        if node is None or node["lifecycle"] not in lifecycles:
            failures.append("registered_match_has_wrong_lifecycle")

    if program == "NOOP":
        require_target()
        if any(row["match_status"] != "unique_match" for row in rows):
            failures.append("reliable_current_region_requires_non_NOOP_resolution")
        if any(
            (_node_by_version(nodes, row["selected_node_version_id"]) or {}).get(
                "lifecycle"
            ) not in {"candidate", "confirmed"}
            for row in rows if row["selected_node_version_id"] is not None
        ):
            failures.append("NOOP_current_region_matches_nonactive_memory")
    elif program == "BIND":
        target_is(refs["open_node_version_id"], {"candidate", "confirmed"})
    elif program == "BIRTH":
        row = require_target()
        if row is not None and row["match_status"] != "unmatched":
            failures.append("BIRTH_target_has_public_prior_match")
    elif program == "REACTIVATE":
        target_is(refs["dormant_node_version_id"], {"dormant"})
    elif program == "RELINK":
        target_is(refs["open_entity_node_version_id"], {"candidate", "confirmed"})
        if target is not None:
            region_by_id = {row["region_id"]: row for row in regions}
            relations = []
            for relation in model_input["relation_observations"]:
                if float(relation["reliability"]) < config.minimum_relation_reliability:
                    continue
                if (relation["relation"] == "located_at" and
                        relation["source_region_id"] == target["region_id"]):
                    place_id = relation["target_region_id"]
                elif (relation["relation"] == "contains" and
                      relation["target_region_id"] == target["region_id"]):
                    place_id = relation["source_region_id"]
                else:
                    continue
                place = region_by_id[place_id]
                place_version = _matched_place_version(place, nodes)
                relations.append((relation, place_version))
            expected_new = refs["new_place_public_ref"]
            valid = [
                (relation, place_version) for relation, place_version in relations
                if place_version == expected_new and
                place_version != refs["old_place_node_version_id"]
            ]
            if len(valid) != 1:
                failures.append("RELINK_lacks_unique_registered_new_place_relation")
            else:
                relation_evidence = {
                    "relation_id": valid[0][0]["relation_id"],
                    "new_place_node_version_id": valid[0][1],
                    "support_sha256": valid[0][0]["support_sha256"],
                }
    elif program in {"RETRACT", "REPLACE"}:
        version_name = (
            "open_entity_or_edge_version_id" if program == "RETRACT"
            else "open_old_entity_node_version_id"
        )
        version_id = refs[version_name]
        node = _node_by_version(nodes, version_id)
        if node is None:
            is_open_edge = any(
                edge.get("edge_version_id") == version_id and
                edge.get("valid_to") is None
                for edge in prior_memory["edges"]
            )
            failures.append(
                "edge_RETRACT_public_sufficiency_not_representable"
                if is_open_edge else
                "registered_negative_target_is_not_an_open_node"
            )
        elif node.get("node_type") != "entity":
            failures.append("edge_RETRACT_public_sufficiency_not_representable")
        else:
            negative_count = _negative_evidence_count(
                node, model_input["free_space_observations"], config,
            )
            if negative_count < config.minimum_independent_negative_observations:
                failures.append("insufficient_independent_visible_empty_evidence")
            for row in rows:
                rule = config.association_rules[row["structure_kind"]]
                if any(
                    comparison["node_version_id"] == version_id and
                    comparison["association_score"] >=
                    rule["association_threshold"]
                    for comparison in row["comparisons"]
                ):
                    failures.append("negative_target_still_has_public_region_match")
                    break
        if program == "REPLACE":
            row = require_target()
            if row is not None and row["match_status"] != "unmatched":
                failures.append("REPLACE_new_locus_has_public_prior_match")
    else:
        if (artifact_plan is None or artifact_receipt is None or
                artifact_plan.get("schema_version") != ARTIFACT_SCHEMA or
                plan["artifact_plan_sha256"] !=
                artifact_plan.get("artifact_plan_sha256")):
            failures.append("registered_SPLIT_MERGE_artifact_receipt_missing")
        else:
            artifact = validate_split_merge_artifact_receipt(
                artifact_receipt, plan=artifact_plan,
            )
            if not artifact["artifact_realized_on_every_replay"]:
                failures.append("registered_SPLIT_MERGE_artifact_not_realized")

    unique_failures = sorted(set(failures))
    receipt = {
        "schema_version": MATCHER_RECEIPT_SCHEMA,
        "episode_id": plan["episode_id"],
        "program": program,
        "construction_plan_sha256": plan["construction_plan_sha256"],
        "matcher_config_sha256": matcher_config_sha256(config),
        "prior_memory_sha256": prior_memory["graph_hash"],
        "current_packet_sha256": canonical_sha256(current_packet),
        "route_plan_sha256": route_plan["route_plan_sha256"],
        "route_receipt_sha256": _sha(route_receipt),
        "route_verdict_sha256": route_verdict["verdict_sha256"],
        "region_match_rows": rows,
        "target_region_id": target["region_id"] if target is not None else None,
        "negative_evidence_count": negative_count,
        "relation_evidence": relation_evidence,
        "artifact_receipt_sha256": (
            artifact_receipt.get("receipt_sha256")
            if artifact_receipt is not None else None
        ),
        "program_public_match_satisfied": not unique_failures,
        "construction_failure_reasons": unique_failures,
        "posthoc_relabel_or_replacement_used": False,
        "private_identity_used": False,
        "semantic_identity_truth_established": False,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return clone_json(receipt)


def validate_program_matcher_receipt(
    receipt: Mapping[str, Any], **inputs: Any,
) -> dict[str, Any]:
    """Recompute a matcher receipt from the same sealed public inputs."""

    rebuilt = make_program_matcher_receipt(**inputs)
    if clone_json(dict(receipt)) != rebuilt:
        raise ValueError("program matcher receipt does not reproduce")
    return rebuilt
