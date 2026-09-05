"""Canonical hashing for immutable world snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def clone_json(value: Any) -> Any:
    """Clone a schema-native JSON tree without copy.deepcopy memo state."""
    if isinstance(value, dict):
        return {key: clone_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone_json(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"CPMT schema value is not JSON-native: {type(value).__name__}")


def compute_graph_hash(graph: dict[str, Any]) -> str:
    # Only the top-level seal is excluded.  A deep copy is unnecessary because
    # canonical_json is read-only; avoiding it also keeps repeated executor
    # validation from recursively cloning the complete versioned graph.
    payload = dict(graph)
    payload.pop("graph_hash", None)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def seal_graph(graph: dict[str, Any]) -> dict[str, Any]:
    sealed = clone_json(graph)
    sealed["graph_hash"] = compute_graph_hash(sealed)
    return sealed
