"""D-213 unified sparse graph, typed transaction gate, and ablation views.

This module is intentionally independent of teacher/private records.  The gate
is applied to public candidate proposals before teacher labels may be opened;
the same policy can audit a sealed catalog afterwards.  It does not invent
place observations or turn the legacy coordinate scaffold into learned place
identity.
"""

from __future__ import annotations

from collections import Counter
import hashlib
from typing import Any, Mapping, Sequence

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json

from .contracts import canonical_sha256, validate_candidate_catalog


ATOMIC_TEMPLATES = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
    "SPLIT", "MERGE",
)
NODE_TYPES = ("place", "entity", "surface", "fragment")
RELATION_TYPES = (
    "located_at", "contains", "supported_by", "adjacent_to",
    "route_transition",
)
ABLATION_VARIANTS = (
    "Place-4", "VSMT-Typed", "VSMT-Flat8", "VSMT-NoPlace",
    "VSMT-NoVersion",
)

CONTRACT_SCHEMA = "vsmt-d213-unified-typed-graph-v1"
GATE_AUDIT_SCHEMA = "vsmt-d213-type-gate-audit-v1"
MODEL_VIEW_SCHEMA = "vsmt-d213-ablation-memory-view-v1"
COMPLEXITY_SCHEMA = "vsmt-d213-graph-complexity-v1"


class D213Error(ValueError):
    """The approved D-213 architecture or type gate was violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D213Error(message)


def _exact_keys(value: Any, keys: set[str], name: str) -> Mapping[str, Any]:
    _require(type(value) is dict, f"{name} must be an object")
    _require(set(value) == keys, f"{name} must contain exactly {sorted(keys)}")
    return value


def _template(program: Mapping[str, Any]) -> str:
    template = str(program.get("template", ""))
    if template == "COMPOSITE":
        _require(
            program.get("composition_label") == "REPLACE"
            and program.get("component_templates") == ["RETRACT", "BIRTH"],
            "the only admitted composite is REPLACE=[RETRACT,BIRTH]",
        )
        return "REPLACE"
    _require(template in ATOMIC_TEMPLATES, "candidate uses an unknown atom")
    return template


def _scope_from_bucket_id(bucket_id: str) -> str:
    _require("|" in bucket_id, "candidate bucket does not encode template and scope")
    _, scope = bucket_id.split("|", 1)
    _require(bool(scope), "candidate scope is empty")
    return scope


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the user-approved architecture without opening any run gate."""

    expected = {
        "schema_version", "decision_id", "status", "authorization",
        "unified_graph", "transaction_vocabulary", "typed_gate",
        "relation_compilation", "candidate_boundary", "shared_frontend",
        "main_comparison", "ablations", "complexity_metrics",
    }
    record = _exact_keys(contract, expected, "D-213 contract")
    _require(record["schema_version"] == CONTRACT_SCHEMA,
             "D-213 contract schema changed")
    _require(record["decision_id"] == "D-213", "D-213 decision identity changed")
    _require(
        record["status"] == "approved_implementation_not_generation_authorized",
        "D-213 status changed",
    )
    authorization = _exact_keys(record["authorization"], {
        "raw_generation", "adapter_materialization", "training",
        "validation_effect", "confirmation",
    }, "D-213 authorization")
    _require(all(value is False for value in authorization.values()),
             "D-213 implementation must not open a run gate")

    graph = _exact_keys(record["unified_graph"], {
        "node_types", "relation_types", "active_retrieval_is_sparse",
        "historical_versions_excluded_from_active_retrieval",
        "contained_entity_refs_role", "place_identity_source",
    }, "D-213 unified graph")
    _require(graph["node_types"] == list(NODE_TYPES), "unified node types changed")
    _require(graph["relation_types"] == list(RELATION_TYPES),
             "unified relation types changed")
    _require(graph["active_retrieval_is_sparse"] is True,
             "active graph retrieval must stay sparse")
    _require(graph["historical_versions_excluded_from_active_retrieval"] is True,
             "historical versions may not enter ordinary retrieval")
    _require(graph["contained_entity_refs_role"] == "derived_cache_only",
             "contained_entity_refs cannot become a source of truth")
    _require(graph["place_identity_source"] == "learned_revisable_not_metric_grid",
             "metric grid cannot define place identity")

    vocabulary = _exact_keys(record["transaction_vocabulary"], {
        "atomic_templates", "replace_is_composite", "create_is_atom",
    }, "D-213 transaction vocabulary")
    _require(vocabulary["atomic_templates"] == list(ATOMIC_TEMPLATES),
             "the eight-atom vocabulary changed")
    _require(vocabulary["replace_is_composite"] == ["RETRACT", "BIRTH"],
             "REPLACE must remain RETRACT+BIRTH")
    _require(vocabulary["create_is_atom"] is False,
             "CREATE may not become a ninth atom")

    typed = _exact_keys(record["typed_gate"], {
        "place", "entity", "surface", "fragment", "relation", "global",
        "gate_stage", "teacher_may_change_gate",
    }, "D-213 typed gate")
    expected_gate = {
        "place": ["NOOP", "BIND", "BIRTH", "MERGE"],
        "entity": list(ATOMIC_TEMPLATES),
        "surface": [
            "NOOP", "BIND", "BIRTH", "REACTIVATE", "RETRACT", "SPLIT",
            "MERGE",
        ],
        "fragment": [
            "NOOP", "BIND", "BIRTH", "REACTIVATE", "RETRACT", "SPLIT",
            "MERGE",
        ],
        "relation": [
            "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
        ],
        "global": ["NOOP"],
    }
    for scope, templates in expected_gate.items():
        _require(typed[scope] == templates, f"typed gate for {scope} changed")
    _require(typed["gate_stage"] == "before_candidate_seal_and_teacher",
             "typed gate must precede candidate seal and teacher")
    _require(typed["teacher_may_change_gate"] is False,
             "teacher may not change the type gate")

    compilation = _exact_keys(record["relation_compilation"], {
        "new_relation", "endpoint_correction", "close_wrong_relation",
        "restore_historical_relation",
    }, "D-213 relation compilation")
    _require(compilation == {
        "new_relation": "BIRTH+ADD_EDGE",
        "endpoint_correction": "RELINK",
        "close_wrong_relation": "RETRACT",
        "restore_historical_relation": "REACTIVATE",
    }, "relation operation compilation changed")

    boundary = _exact_keys(record["candidate_boundary"], {
        "inputs", "private_teacher_future_visible", "invalid_type_pairs",
        "candidate_miss_policy",
    }, "D-213 candidate boundary")
    _require(boundary["inputs"] == [
        "public_current_observation", "prior_predicted_memory",
        "public_pose_belief", "public_transition_action_summary",
    ], "candidate inputs changed")
    _require(boundary["private_teacher_future_visible"] is False,
             "candidate gate may not see private, teacher, or future")
    _require(boundary["invalid_type_pairs"] == "rejected_before_scoring",
             "typed candidates must be rejected before scoring")
    _require(boundary["candidate_miss_policy"] == "record_not_repair",
             "candidate miss cannot be repaired after seal")

    frontend = _exact_keys(record["shared_frontend"], {
        "input", "frozen", "identical_cached_bytes_for_main_methods",
        "method_private_frontend_allowed", "internal_memory_mechanisms_may_differ",
    }, "D-213 shared frontend")
    _require(frontend == {
        "input": "RGB-D+intrinsics+public_pose_belief+public_actions_summary",
        "frozen": True,
        "identical_cached_bytes_for_main_methods": True,
        "method_private_frontend_allowed": False,
        "internal_memory_mechanisms_may_differ": True,
    }, "shared frontend fairness contract changed")

    comparison = _exact_keys(record["main_comparison"], {
        "primary_method", "methods", "claim_scope",
    }, "D-213 main comparison")
    _require(comparison["primary_method"] == "VSMT-Typed",
             "VSMT-Typed must remain the primary method")
    _require(comparison["methods"] == ["VSMT", "TAF", "ELU", "WFR", "LOW"],
             "main comparison methods changed")
    _require(comparison["claim_scope"] == "memory_update_mechanism_under_shared_frontend",
             "main comparison claim scope changed")

    ablations = record["ablations"]
    _require(type(ablations) is dict and list(ablations) == list(ABLATION_VARIANTS),
             "D-213 ablation set or order changed")
    for name, row in ablations.items():
        _exact_keys(row, {
            "node_scope", "type_gate", "version_history_visible_to_model",
            "role", "main_table",
        }, f"D-213 ablation {name}")
    _require(ablations["VSMT-Typed"]["main_table"] is True,
             "VSMT-Typed must be the main VSMT row")
    _require(all(
        row["main_table"] is False for name, row in ablations.items()
        if name != "VSMT-Typed"
    ), "ablations other than VSMT-Typed cannot be main-table methods")

    metrics = record["complexity_metrics"]
    _require(metrics == [
        "active_node_count_by_type", "active_edge_count_by_relation",
        "historical_node_version_count", "historical_edge_version_count",
        "candidate_count_by_scope_and_atom", "type_gate_rejection_count",
        "illegal_transaction_count", "peak_active_node_count",
        "peak_candidate_count", "runtime_ms", "peak_memory_bytes",
    ], "D-213 complexity metrics changed")
    return clone_json(dict(record))


def _typed_templates(scope: str, contract: Mapping[str, Any]) -> set[str]:
    gate = contract["typed_gate"]
    if scope == "global":
        return set(gate["global"])
    if scope in NODE_TYPES:
        return set(gate[scope])
    if scope.startswith("relation:"):
        relation = scope.split(":", 1)[1]
        _require(relation in RELATION_TYPES, f"unknown relation scope {relation!r}")
        return set(gate["relation"])
    raise D213Error(f"unknown candidate scope {scope!r}")


def _allowed_templates_validated(
    scope: str, *, variant: str, validated: Mapping[str, Any],
) -> frozenset[str]:
    _require(variant in ABLATION_VARIANTS, f"unknown ablation variant {variant!r}")
    if variant == "VSMT-Flat8":
        return frozenset(ATOMIC_TEMPLATES)
    if variant == "Place-4":
        if scope == "global":
            return frozenset({"NOOP"})
        if scope == "place":
            return frozenset(validated["typed_gate"]["place"])
        if scope.startswith("relation:"):
            relation = scope.split(":", 1)[1]
            if relation in {"adjacent_to", "route_transition"}:
                return frozenset(validated["typed_gate"]["relation"])
            return frozenset()
        return frozenset()
    if variant == "VSMT-NoPlace":
        if scope == "place":
            return frozenset()
        if scope.startswith("relation:"):
            relation = scope.split(":", 1)[1]
            if relation in {
                "located_at", "contains", "adjacent_to", "route_transition",
            }:
                return frozenset()
    return frozenset(_typed_templates(scope, validated))


def allowed_templates(
    scope: str, *, variant: str, contract: Mapping[str, Any],
) -> frozenset[str]:
    """Return the selector-visible atom set for one typed candidate scope."""

    return _allowed_templates_validated(
        scope, variant=variant, validated=validate_contract(contract),
    )


def validate_unsealed_candidate_rows(
    rows: Sequence[Mapping[str, Any]], *, variant: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail before sealing when a proposed program violates the type gate.

    Each row has exactly ``program`` and ``enumeration``; this deliberately
    matches the public generator's last unsealed representation and has no
    teacher/private argument.
    """

    validated = validate_contract(contract)
    counts: Counter[str] = Counter()
    for index, row in enumerate(rows):
        _exact_keys(row, {"program", "enumeration"}, f"candidate row {index}")
        program = row["program"]
        enumeration = row["enumeration"]
        _require(type(program) is dict, f"candidate row {index} program is invalid")
        _require(type(enumeration) is dict,
                 f"candidate row {index} enumeration is invalid")
        bucket_id = str(enumeration.get("bucket_id", ""))
        scope = _scope_from_bucket_id(bucket_id)
        template = _template(program)
        admitted = _allowed_templates_validated(
            scope, variant=variant, validated=validated,
        )
        if template == "REPLACE":
            _require(
                scope == "entity" or scope.startswith("relation:"),
                f"REPLACE is not legal for scope {scope!r}",
            )
            _require({"RETRACT", "BIRTH"} <= admitted,
                     f"REPLACE components are not legal for scope {scope!r}")
        else:
            _require(template in admitted,
                     f"{template} is not legal for scope {scope!r} in {variant}")
        _require(program.get("template") != "CREATE",
                 "CREATE cannot appear as a ninth transaction atom")
        if scope.startswith("relation:") and template == "BIRTH":
            operations = program.get("operations", [])
            _require(
                any(operation.get("op_type") == "ADD_EDGE"
                    for operation in operations),
                "relation BIRTH must compile to ADD_EDGE",
            )
        counts[f"{scope}|{template}"] += 1
    payload = {
        "schema_version": GATE_AUDIT_SCHEMA,
        "variant": variant,
        "candidate_count": len(rows),
        "candidate_count_by_scope_and_atom": dict(sorted(counts.items())),
        "type_gate_rejection_count": 0,
        "gate_stage": validated["typed_gate"]["gate_stage"],
        "gate_inputs_public_only": True,
    }
    payload["audit_sha256"] = canonical_sha256(payload)
    return payload


def audit_sealed_candidate_catalog(
    catalog: Mapping[str, Any], *, variant: str, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Recheck, but never edit, an already sealed public candidate catalog."""

    sealed = validate_candidate_catalog(catalog)
    rows = [
        {"program": item["program"], "enumeration": item["enumeration"]}
        for item in sealed["candidates"]
    ]
    audit = validate_unsealed_candidate_rows(
        rows, variant=variant, contract=contract,
    )
    audit["catalog_sha256"] = sealed["catalog_sha256"]
    audit["audit_sha256"] = canonical_sha256({
        key: value for key, value in audit.items() if key != "audit_sha256"
    })
    return audit


def _strip_version_fields(record: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    result = clone_json(dict(record))
    for key in (
        f"{kind}_version_id", "valid_from", "valid_to", "predecessor_ids",
        "provenance",
    ):
        result.pop(key, None)
    return result


def build_ablation_memory_view(
    memory: Mapping[str, Any], *, variant: str, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact model-visible memory view for one registered ablation."""

    validated = validate_contract(contract)
    _require(variant in ABLATION_VARIANTS, f"unknown ablation variant {variant!r}")
    graph = clone_json(dict(memory))
    validate_graph(graph, verify_hash=True)
    open_nodes = [node for node in graph["nodes"] if node.get("valid_to") is None]
    open_edges = [edge for edge in graph["edges"] if edge.get("valid_to") is None]

    if variant == "Place-4":
        nodes = [node for node in open_nodes if node.get("node_type") == "place"]
    elif variant == "VSMT-NoPlace":
        nodes = [node for node in open_nodes if node.get("node_type") != "place"]
    else:
        nodes = open_nodes
    node_ids = {str(node["node_id"]) for node in nodes}
    edges = [
        edge for edge in open_edges
        if str(edge["source"]) in node_ids and str(edge["target"]) in node_ids
    ]

    version_visible = bool(
        validated["ablations"][variant]["version_history_visible_to_model"]
    )
    if version_visible:
        if variant == "Place-4":
            history_nodes = [
                node for node in graph["nodes"] if node.get("node_type") == "place"
            ]
        elif variant == "VSMT-NoPlace":
            history_nodes = [
                node for node in graph["nodes"] if node.get("node_type") != "place"
            ]
        else:
            history_nodes = graph["nodes"]
        history_node_ids = {str(node["node_id"]) for node in history_nodes}
        history_edges = [
            edge for edge in graph["edges"]
            if str(edge["source"]) in history_node_ids
            and str(edge["target"]) in history_node_ids
        ]
        model_nodes = clone_json(history_nodes)
        model_edges = clone_json(history_edges)
        transaction_log = clone_json(graph["transaction_log"])
    else:
        model_nodes = [_strip_version_fields(node, kind="node") for node in nodes]
        model_edges = [_strip_version_fields(edge, kind="edge") for edge in edges]
        transaction_log = []

    view: dict[str, Any] = {
        "schema_version": MODEL_VIEW_SCHEMA,
        "variant": variant,
        "source_graph_sha256": graph["graph_hash"],
        "node_types_visible": sorted({
            str(node.get("node_type")) for node in model_nodes
        }),
        "type_gate_enabled": variant != "VSMT-Flat8",
        "version_history_visible_to_model": version_visible,
        "nodes": model_nodes,
        "edges": model_edges,
        "transaction_log": transaction_log,
    }
    view["view_sha256"] = canonical_sha256(view)
    return view


def validate_unified_graph(
    memory: Mapping[str, Any], *, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate node/edge types and any materialized derived place cache."""

    validate_contract(contract)
    graph = clone_json(dict(memory))
    validate_graph(graph, verify_hash=True)
    node_types = {
        str(node["node_id"]): str(node.get("node_type"))
        for node in graph["nodes"] if node.get("valid_to") is None
    }
    _require(all(kind in NODE_TYPES for kind in node_types.values()),
             "unified graph contains an unknown node type")
    endpoint_types = {
        "located_at": ("entity", "place"),
        "contains": ("place", "entity"),
        "supported_by": ("entity", "surface"),
        "adjacent_to": ("place", "place"),
        "route_transition": ("place", "place"),
    }
    contained: dict[str, set[str]] = {
        node_id: set() for node_id, kind in node_types.items() if kind == "place"
    }
    for edge in graph["edges"]:
        if edge.get("valid_to") is not None:
            continue
        relation = str(edge.get("relation"))
        _require(relation in endpoint_types,
                 f"unified graph contains unknown relation {relation!r}")
        source = str(edge["source"])
        target = str(edge["target"])
        _require((node_types.get(source), node_types.get(target)) == endpoint_types[relation],
                 f"relation {relation!r} has invalid endpoint types")
        if relation == "located_at":
            contained[target].add(source)
        elif relation == "contains":
            contained[source].add(target)
    for node in graph["nodes"]:
        if node.get("valid_to") is not None or node.get("node_type") != "place":
            continue
        state = node.get("vsmt_observation_state")
        if type(state) is not dict or "contained_entity_refs" not in state:
            continue
        _require(
            state["contained_entity_refs"] == sorted(contained[str(node["node_id"])]),
            "contained_entity_refs must equal the relation-derived cache",
        )
    return graph


def graph_complexity_metrics(
    memory: Mapping[str, Any], *, contract: Mapping[str, Any],
    candidate_catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive graph/candidate size diagnostics instead of trusting model reports."""

    graph = validate_unified_graph(memory, contract=contract)
    active_nodes = [node for node in graph["nodes"] if node.get("valid_to") is None]
    active_edges = [edge for edge in graph["edges"] if edge.get("valid_to") is None]
    candidate_counts: Counter[str] = Counter()
    catalog_sha256 = None
    if candidate_catalog is not None:
        sealed = validate_candidate_catalog(candidate_catalog)
        catalog_sha256 = sealed["catalog_sha256"]
        for item in sealed["candidates"]:
            scope = _scope_from_bucket_id(item["enumeration"]["bucket_id"])
            candidate_counts[f"{scope}|{_template(item['program'])}"] += 1
    result: dict[str, Any] = {
        "schema_version": COMPLEXITY_SCHEMA,
        "graph_sha256": graph["graph_hash"],
        "candidate_catalog_sha256": catalog_sha256,
        "active_node_count_by_type": dict(sorted(Counter(
            str(node["node_type"]) for node in active_nodes
        ).items())),
        "active_edge_count_by_relation": dict(sorted(Counter(
            str(edge["relation"]) for edge in active_edges
        ).items())),
        "historical_node_version_count": len(graph["nodes"]) - len(active_nodes),
        "historical_edge_version_count": len(graph["edges"]) - len(active_edges),
        "candidate_count_by_scope_and_atom": dict(sorted(candidate_counts.items())),
        "active_node_count": len(active_nodes),
        "active_edge_count": len(active_edges),
        "candidate_count": sum(candidate_counts.values()),
    }
    result["metrics_sha256"] = hashlib.sha256(
        canonical_json(result).encode("utf-8")
    ).hexdigest()
    return result
