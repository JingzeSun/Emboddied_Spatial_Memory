"""Pure geometry and executed-candidate audit for the visual pilot.

The simulator runner supplies camera poses, anonymized observations and place
coordinates.  This module deliberately has no AI2-THOR dependency so the
online/future boundary and the immutable-base execution contract can be unit
tested without launching Unity.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Iterable, Mapping

from .executor import SCHEMA_VERSION, execute_transaction
from .hashing import compute_graph_hash, seal_graph


ENERGY_KEYS = (
    "now",
    "future",
    "edit",
    "growth",
    "collateral",
    "illegal",
)


def project_world_point(
    point: Mapping[str, float],
    camera: Mapping[str, Any],
    *,
    width: int,
    height: int,
    fov_degrees: float,
) -> dict[str, float | bool]:
    """Project a world point with a fixed pinhole camera model.

    AI2-THOR uses +z as yaw zero and positive camera horizon when looking
    down.  Coordinates are returned in normalized image space.
    """
    origin = camera["position"]
    rotation = camera["rotation"]
    dx = float(point["x"]) - float(origin["x"])
    dy = float(point["y"]) - float(origin["y"])
    dz = float(point["z"]) - float(origin["z"])

    yaw = math.radians(float(rotation.get("y", 0.0)))
    x_camera = dx * math.cos(yaw) - dz * math.sin(yaw)
    z_yaw = dx * math.sin(yaw) + dz * math.cos(yaw)

    horizon = math.radians(float(camera.get("horizon", 0.0)))
    y_camera = dy * math.cos(horizon) + z_yaw * math.sin(horizon)
    z_camera = -dy * math.sin(horizon) + z_yaw * math.cos(horizon)
    if z_camera <= 1e-6:
        return {
            "visible": False,
            "u": float("nan"),
            "v": float("nan"),
            "depth": z_camera,
        }

    tangent = math.tan(math.radians(float(fov_degrees)) / 2.0)
    aspect = float(width) / float(height)
    x_ndc = x_camera / (z_camera * tangent * aspect)
    y_ndc = y_camera / (z_camera * tangent)
    u = (x_ndc + 1.0) / 2.0
    v = (1.0 - y_ndc) / 2.0
    return {
        "visible": 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0,
        "u": u,
        "v": v,
        "depth": z_camera,
    }


def backproject_image_point(
    center: Iterable[float],
    depth: float,
    camera: Mapping[str, Any],
    *,
    width: int,
    height: int,
    fov_degrees: float,
) -> dict[str, float]:
    """Lift one depth-backed image point into the world coordinate frame."""
    u, v = [float(value) for value in center]
    z_camera = float(depth)
    tangent = math.tan(math.radians(float(fov_degrees)) / 2.0)
    aspect = float(width) / float(height)
    x_camera = (2.0 * u - 1.0) * z_camera * tangent * aspect
    y_camera = (1.0 - 2.0 * v) * z_camera * tangent

    horizon = math.radians(float(camera.get("horizon", 0.0)))
    dy = y_camera * math.cos(horizon) - z_camera * math.sin(horizon)
    z_yaw = y_camera * math.sin(horizon) + z_camera * math.cos(horizon)

    yaw = math.radians(float(camera["rotation"].get("y", 0.0)))
    dx = x_camera * math.cos(yaw) + z_yaw * math.sin(yaw)
    dz = -x_camera * math.sin(yaw) + z_yaw * math.cos(yaw)
    origin = camera["position"]
    return {
        "x": float(origin["x"]) + dx,
        "y": float(origin["y"]) + dy,
        "z": float(origin["z"]) + dz,
    }


def _open_entities(graph: Mapping[str, Any]) -> list[str]:
    return [
        node["node_id"]
        for node in graph["nodes"]
        if node.get("node_type") == "entity" and node.get("valid_to") is None
    ]


def _open_location(
    graph: Mapping[str, Any], node_id: str
) -> str | None:
    matches = [
        edge["target"]
        for edge in graph["edges"]
        if edge.get("source") == node_id
        and edge.get("relation") == "located_at"
        and edge.get("valid_to") is None
    ]
    if len(matches) > 1:
        raise ValueError(f"entity {node_id!r} has multiple open locations")
    return matches[0] if matches else None


def projected_entities(
    graph: Mapping[str, Any],
    geometry: Mapping[str, Mapping[str, float]],
    camera: Mapping[str, Any],
    *,
    width: int,
    height: int,
    fov_degrees: float,
) -> list[dict[str, float | str]]:
    """Project all open entity locations encoded by an executed graph."""
    projected: list[dict[str, float | str]] = []
    for node_id in _open_entities(graph):
        place_id = _open_location(graph, node_id)
        if place_id is None or place_id not in geometry:
            continue
        result = project_world_point(
            geometry[place_id],
            camera,
            width=width,
            height=height,
            fov_degrees=fov_degrees,
        )
        if result["visible"]:
            projected.append(
                {
                    "node_id": node_id,
                    "u": float(result["u"]),
                    "v": float(result["v"]),
                    "depth": float(result["depth"]),
                }
            )
    return projected


def frame_disagreement(
    predicted: Iterable[Mapping[str, float]],
    observed: Iterable[Mapping[str, Any]],
) -> float:
    """Return a small deterministic set-matching error for one view."""
    remaining_predictions = list(predicted)
    remaining_observations = list(observed)
    normalizer = max(
        1, len(remaining_predictions), len(remaining_observations)
    )
    matched_cost = 0.0
    while remaining_predictions and remaining_observations:
        best: tuple[float, int, int] | None = None
        for prediction_index, prediction in enumerate(remaining_predictions):
            for observation_index, observation in enumerate(
                remaining_observations
            ):
                center = observation["center"]
                center_error = math.hypot(
                    float(prediction["u"]) - float(center[0]),
                    float(prediction["v"]) - float(center[1]),
                )
                depth_error = min(
                    abs(
                        float(prediction["depth"])
                        - float(observation["depth"])
                    )
                    / 5.0,
                    1.0,
                )
                cost = min(center_error + depth_error, 1.0)
                candidate = (cost, prediction_index, observation_index)
                if best is None or candidate < best:
                    best = candidate
        assert best is not None
        matched_cost += best[0]
        del remaining_predictions[best[1]]
        del remaining_observations[best[2]]
    unmatched = len(remaining_predictions) + len(remaining_observations)
    return (matched_cost + float(unmatched)) / float(normalizer)


def _has_evidence(graph: Mapping[str, Any], evidence_ref: str) -> bool:
    return any(
        evidence_ref in record.get("evidence_refs", [])
        for collection in (graph["nodes"], graph["edges"])
        for record in collection
        if record.get("valid_to") is None
    )


def _protected_signature(
    graph: Mapping[str, Any], protected_ids: Iterable[str]
) -> list[dict[str, Any]]:
    protected = set(protected_ids)
    records = [
        deepcopy(record)
        for collection in (graph["nodes"], graph["edges"])
        for record in collection
        if record.get("node_id") in protected
        or record.get("edge_id") in protected
    ]
    return sorted(
        records,
        key=lambda record: (
            str(record.get("node_version_id", "")),
            str(record.get("edge_version_id", "")),
        ),
    )


def candidate_energy(
    base_graph: Mapping[str, Any],
    post_graph: Mapping[str, Any],
    program: Mapping[str, Any],
    geometry: Mapping[str, Mapping[str, float]],
    current_view: Mapping[str, Any],
    future_views: Iterable[Mapping[str, Any]],
    *,
    width: int,
    height: int,
    fov_degrees: float,
) -> dict[str, float]:
    """Compute all six required hindsight energy components separately."""

    def view_error(view: Mapping[str, Any]) -> float:
        predictions = projected_entities(
            post_graph,
            geometry,
            view["camera"],
            width=width,
            height=height,
            fov_degrees=fov_degrees,
        )
        return frame_disagreement(predictions, view["regions"])

    binding_penalty = (
        0.0
        if _has_evidence(post_graph, current_view["evidence_ref"])
        else 0.75
    )
    now = view_error(current_view) + binding_penalty
    future_errors = [view_error(view) for view in future_views]
    future = sum(future_errors) / max(1, len(future_errors))
    collateral = float(
        _protected_signature(base_graph, program["protected_ids"])
        != _protected_signature(post_graph, program["protected_ids"])
    )
    return {
        "now": now,
        "future": future,
        "edit": float(program.get("declared_edit_cost", 0.0)),
        "growth": float(program.get("declared_growth_cost", 0.0)),
        "collateral": collateral,
        "illegal": 0.0,
    }


def total_energy(terms: Mapping[str, float]) -> float:
    """Combine recorded terms for this interface audit only."""
    return (
        terms["now"]
        + terms["future"]
        + 0.1 * terms["edit"]
        + 0.25 * terms["growth"]
        + 10.0 * terms["collateral"]
        + 1_000_000.0 * terms["illegal"]
    )


def teacher_posterior(
    rollouts: Iterable[Mapping[str, Any]], temperature: float = 0.25
) -> dict[str, float]:
    """Turn post-execution hindsight energies into a normalized teacher."""
    items = list(rollouts)
    legal = [item for item in items if not item["energy"]["illegal"]]
    if not legal:
        return {str(item["template"]): 0.0 for item in items}
    minimum = min(float(item["total_energy"]) for item in legal)
    weights: dict[str, float] = {}
    for item in items:
        name = str(item["template"])
        if item["energy"]["illegal"]:
            weights[name] = 0.0
        else:
            weights[name] = math.exp(
                -(float(item["total_energy"]) - minimum) / temperature
            )
    denominator = sum(weights.values())
    return {
        name: value / denominator for name, value in weights.items()
    }


def execute_visual_candidates(
    base_graph: Mapping[str, Any],
    programs: Iterable[Mapping[str, Any]],
    geometry: Mapping[str, Mapping[str, float]],
    current_view: Mapping[str, Any],
    future_views: Iterable[Mapping[str, Any]],
    *,
    width: int,
    height: int,
    fov_degrees: float,
) -> dict[str, Any]:
    """Clone one immutable base, execute each candidate, then score it."""
    base = deepcopy(dict(base_graph))
    base_hash = compute_graph_hash(base)
    future = list(future_views)
    rollouts: list[dict[str, Any]] = []
    for program_value in programs:
        program = deepcopy(dict(program_value))
        try:
            post_graph = execute_transaction(base, program)
            terms = candidate_energy(
                base,
                post_graph,
                program,
                geometry,
                current_view,
                future,
                width=width,
                height=height,
                fov_degrees=fov_degrees,
            )
            rollout = {
                "template": program["template"],
                "transaction_id": program["transaction_id"],
                "status": "executed",
                "base_graph_hash": base_hash,
                "post_graph_hash": compute_graph_hash(post_graph),
                "program": program,
                "energy": terms,
                "total_energy": total_energy(terms),
                "post_graph": post_graph,
                "failure": None,
            }
        except Exception as exc:  # explicit illegal candidate, never hidden
            terms = {
                "now": 0.0,
                "future": 0.0,
                "edit": float(program.get("declared_edit_cost", 0.0)),
                "growth": float(program.get("declared_growth_cost", 0.0)),
                "collateral": 0.0,
                "illegal": 1.0,
            }
            rollout = {
                "template": program["template"],
                "transaction_id": program["transaction_id"],
                "status": "illegal",
                "base_graph_hash": base_hash,
                "post_graph_hash": None,
                "program": program,
                "energy": terms,
                "total_energy": total_energy(terms),
                "post_graph": None,
                "failure": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        if compute_graph_hash(base) != base_hash:
            raise RuntimeError("candidate execution mutated the immutable base")
        rollouts.append(rollout)

    posterior = teacher_posterior(rollouts)
    for rollout in rollouts:
        rollout["teacher_probability"] = posterior[rollout["template"]]
    winner = max(rollouts, key=lambda item: item["teacher_probability"])
    return {
        "base_graph_hash": base_hash,
        "winner": winner["template"],
        "rollouts": rollouts,
    }


def _node(
    node_id: str,
    node_type: str,
    provenance: str,
    *,
    evidence_refs: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "node_version_id": f"{node_id}@v0",
        "node_type": node_type,
        "lifecycle": "confirmed",
        "valid_from": 0,
        "valid_to": None,
        "evidence_refs": list(evidence_refs),
        "latent_refs": [f"latent:{node_id}"],
        "canonical_id": None,
        "predecessor_ids": [],
        "provenance": [provenance],
    }


def _edge(
    source: str,
    target: str,
    provenance: str,
    *,
    version: int = 0,
    valid_from: int = 0,
    evidence_refs: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "edge_id": "target-location",
        "edge_version_id": f"target-location@v{version}",
        "source": source,
        "target": target,
        "relation": "located_at",
        "frame": "world",
        "valid_from": valid_from,
        "valid_to": None,
        "evidence_refs": list(evidence_refs),
        "provenance": [provenance],
    }


def make_visual_base(
    case_id: str,
    *,
    known_target: bool,
    old_place: str = "place-old",
    current_place: str = "place-current",
) -> dict[str, Any]:
    """Create the smallest versioned world needed by the visual pilot."""
    provenance = f"visual-pilot:{case_id}:base"
    nodes = [
        _node("boundary-protected", "surface", provenance),
        _node(old_place, "place", provenance),
    ]
    if current_place != old_place:
        nodes.append(_node(current_place, "place", provenance))
    edges: list[dict[str, Any]] = []
    if known_target:
        nodes.append(
            _node(
                "target-known",
                "entity",
                provenance,
                evidence_refs=[f"obs:{case_id}:t0"],
            )
        )
        edges.append(_edge("target-known", old_place, provenance))
    graph = {
        "schema_version": SCHEMA_VERSION,
        "graph_id": f"world:{case_id}",
        "graph_version": "v0",
        "parent_version": None,
        "nodes": nodes,
        "edges": edges,
        "transaction_log": [],
        "graph_hash": None,
    }
    return seal_graph(graph)


def make_visual_programs(
    case_id: str,
    base_graph: Mapping[str, Any],
    *,
    current_place: str = "place-current",
) -> list[dict[str, Any]]:
    """Build the fixed NOOP/BIND/BIRTH/RELINK candidate family."""
    evidence_ref = f"obs:{case_id}:current"
    base_version = str(base_graph["graph_version"])
    protected = ["boundary-protected"]

    def header(
        template: str,
        intent: str,
        operations: list[dict[str, Any]],
        edit: float,
        growth: float,
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "transaction_id": f"tx:{case_id}:{template.lower()}",
            "intent": intent,
            "template": template,
            "base_graph_version": base_version,
            "operations": operations,
            "evidence_refs": [evidence_ref],
            "protected_ids": protected,
            "declared_edit_cost": edit,
            "declared_growth_cost": growth,
            "proposer": "deterministic",
        }

    noop = header("NOOP", "PRESERVE", [], 0.0, 0.0)
    bind = header(
        "BIND",
        "ASSOCIATE",
        [
            {
                "op_id": "assert-known-target",
                "op_type": "ASSERT_PRECONDITION",
                "arguments": {
                    "kind": "node_lifecycle",
                    "node_id": "target-known",
                    "allowed": ["candidate", "confirmed"],
                },
            },
            {
                "op_id": "attach-current-evidence",
                "op_type": "ATTACH_EVIDENCE",
                "arguments": {
                    "target_kind": "node",
                    "target_id": "target-known",
                    "evidence_ref": evidence_ref,
                },
            },
            {
                "op_id": "record-bind",
                "op_type": "RECORD_PROVENANCE",
                "arguments": {
                    "target_kind": "node",
                    "target_id": "target-known",
                    "provenance_ref": f"tx:{case_id}:bind",
                },
            },
        ],
        0.25,
        0.0,
    )
    born_node = _node(
        "target-new",
        "entity",
        f"tx:{case_id}:birth",
        evidence_refs=[evidence_ref],
    )
    born_node["lifecycle"] = "candidate"
    birth_edge = _edge(
        "target-new",
        current_place,
        f"tx:{case_id}:birth",
        evidence_refs=[evidence_ref],
    )
    birth_edge["edge_id"] = "target-new-location"
    birth_edge["edge_version_id"] = "target-new-location@v0"
    birth = header(
        "BIRTH",
        "EXPAND",
        [
            {
                "op_id": "assert-new-target",
                "op_type": "ASSERT_PRECONDITION",
                "arguments": {"kind": "node_absent", "node_id": "target-new"},
            },
            {
                "op_id": "create-new-target",
                "op_type": "CREATE_NODE",
                "arguments": {"node": born_node},
            },
            {
                "op_id": "locate-new-target",
                "op_type": "ADD_EDGE",
                "arguments": {"edge": birth_edge},
            },
        ],
        1.0,
        1.0,
    )
    relink = header(
        "RELINK",
        "REVISE",
        [
            {
                "op_id": "close-old-location",
                "op_type": "CLOSE_EDGE_VERSION",
                "arguments": {"edge_id": "target-location", "at": 1},
            },
            {
                "op_id": "record-old-location",
                "op_type": "RECORD_PROVENANCE",
                "arguments": {
                    "target_kind": "edge",
                    "edge_version_id": "target-location@v0",
                    "provenance_ref": f"tx:{case_id}:relink",
                },
            },
            {
                "op_id": "open-current-location",
                "op_type": "ADD_EDGE",
                "arguments": {
                    "edge": _edge(
                        "target-known",
                        current_place,
                        f"tx:{case_id}:relink",
                        version=1,
                        valid_from=1,
                        evidence_refs=[evidence_ref],
                    )
                },
            },
        ],
        1.0,
        0.0,
    )
    return [noop, bind, birth, relink]


def online_payload(
    case_id: str,
    base_graph: Mapping[str, Any],
    programs: Iterable[Mapping[str, Any]],
    current_view: Mapping[str, Any],
    geometry: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    """Build and validate the exact information available at inference."""
    payload = {
        "schema_version": "cpmt-visual-online-0.1",
        "case_id": case_id,
        "base_graph": deepcopy(dict(base_graph)),
        "candidate_programs": deepcopy(list(programs)),
        "current_view": deepcopy(dict(current_view)),
        "candidate_geometry": deepcopy(dict(geometry)),
    }
    assert_online_boundary(payload)
    return payload


def assert_online_boundary(payload: Mapping[str, Any]) -> None:
    """Reject future/audit identifiers from a recursively nested payload."""
    forbidden_fragments = (
        "future",
        "hindsight",
        "teacher",
        "oracle",
        "ground_truth",
        "object_id",
        "objectid",
        "instance_id",
        "audit_ref",
    )

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                lowered = str(key).lower()
                if any(fragment in lowered for fragment in forbidden_fragments):
                    raise ValueError(f"online boundary violation at {path}.{key}")
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(payload, "online")
