"""D-224 / D-224-S1: the three pure helpers the VSMT-lean cores reuse.

METHOD §13 says the lean cores reuse only pure functions that cannot produce
a second numerical semantics.  They used to reach those functions through
``vsmt.graph_ops``, but that module imported ``cpmt.executor.validate_graph``
at module level and defined ``GraphRevision`` and the place scaffold in the
same file, so importing one pure helper pulled the whole archived
unified-graph line into the current entry point.  Ruling 9 of D-224-S1 cut
that edge: the three helpers (cosine similarity, centroid distance, opaque
ID) are copied here **verbatim**, so the numbers do not move, and no lean
module imports ``vsmt.graph_ops`` or ``cpmt.executor`` any more.  Since
``vsmt/__init__.py`` stopped importing the archived modules and
``graph_ops`` was removed from ``main`` after the tag ``paper-v1``, the
boundary also holds at run time.

``test_vsmt_lean_geometry.py`` pins these copies to the outputs of
``graph_ops`` recorded at ``paper-v1`` (digests over random inputs, plus the
degenerate cosines and opaque IDs as literal values) and checks the import
boundary at source level and at run time.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping

from cpmt.hashing import canonical_json


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    numerator = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return -1.0
    return max(-1.0, min(1.0, numerator / (left_norm * right_norm)))


def centroid_distance(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    return math.sqrt(sum(
        (float(a) - float(b)) ** 2
        for a, b in zip(left["centroid_m"], right["centroid_m"])
    ))


def opaque_id(*parts: object, prefix: str) -> str:
    encoded = canonical_json([str(part) for part in parts]).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()[:16]}"


__all__ = ["centroid_distance", "cosine_similarity", "opaque_id"]
