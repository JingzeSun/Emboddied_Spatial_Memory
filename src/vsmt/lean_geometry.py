"""D-224 / D-224-S1: the three pure helpers the VSMT-lean cores reuse.

METHOD §13 says the lean cores reuse only pure functions that cannot produce
a second numerical semantics.  They used to reach those functions through
``vsmt.graph_ops``, but that module imports ``cpmt.executor.validate_graph``
at module level and defines ``GraphRevision`` and the place scaffold in the
same file, so importing one pure helper pulled the whole archived
unified-graph line into the current entry point.  Ruling 9 of D-224-S1 cut
that edge: the three helpers are copied here **verbatim**, so the numbers do
not move, and no lean module imports ``vsmt.graph_ops`` or ``cpmt.executor``
any more.

白话：这个模块只放三个小函数——余弦相似度、质心距离和不透明 ID。它解决的是
"为了用 20 行纯函数而把整条已归档的统一图代码拉进当前入口"这个依赖问题。输入
是两个向量、两个带 `centroid_m` 的几何体，或任意几个片段；输出是一个数或一个
字符串。例如两个描述子完全同向，余弦为 1.0。函数体逐字抄自 `vsmt.graph_ops`，
因此任何数值都不会改变；它不是新算法，也不改变任何方法语义。

``vsmt.graph_ops`` keeps its own copies for the archived modules and their
tests.  The two copies are identical today and are not expected to diverge,
because neither line is under development; ``test_vsmt_lean_geometry.py``
pins that equality so a future edit to either side is caught.
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
