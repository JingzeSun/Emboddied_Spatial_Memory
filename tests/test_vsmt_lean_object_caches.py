"""Ruling 104-7 tests for the two per-object caches: the descriptor-norm memo of ``cosine_matrix`` and the identity memo of
``entity_identities``.

The forms before the caches are kept here verbatim and every result is compared bit for bit (float64 bytes, or ``==`` on
the identity records): random and edge inputs (zero rows, negative zeros, unequal widths, empty sides) through repeated
calls that hit the memo; the runner scenario's memories through a growing evidence map, a second map object with the same
entries, a caller that changes what it got, a memory without a digest and more memories than the memo keeps.  CPU, seconds.
"""
from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import test_vsmt_lean_runner as fixtures  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402
from vsmt.lean_geometry import cosine_similarity  # noqa: E402


def cosine_matrix_before_the_cache(left_rows, right_rows):
    """``lean_assignment.cosine_matrix`` as it was before ruling 104-7 (LOG-254 form), verbatim."""

    left = [[float(v) for v in row] for row in left_rows]
    right = [[float(v) for v in row] for row in right_rows]
    if not left or not right:
        return [[-1.0] * len(right) for _ in left]
    widths = {len(row) for row in left} | {len(row) for row in right}
    if len(widths) != 1 or 0 in widths:
        return [[cosine_similarity(a, b) for b in right] for a in left]
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    dot = la._NeumaierSum((a.shape[0], b.shape[0]))
    for k in range(a.shape[1]):
        dot.add(a[:, k][:, None] * b[:, k][None, :])
    dot = dot.result()
    left_norm = np.asarray([math.sqrt(sum(float(value) ** 2 for value in row)) for row in left], dtype=np.float64)
    right_norm = np.asarray([math.sqrt(sum(float(value) ** 2 for value in row)) for row in right], dtype=np.float64)
    denominator = left_norm[:, None] * right_norm[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.clip(dot / denominator, -1.0, 1.0)
    zero = (left_norm[:, None] == 0.0) | (right_norm[None, :] == 0.0)
    return np.where(zero, -1.0, ratio).tolist()


def entity_identities_before_the_cache(memory, evidence_instance):
    return {str(entity["entity_id"]): lt.entity_identity(entity, evidence_instance) for entity in memory["entities"]}


def bits(matrix) -> bytes:
    return np.asarray(matrix, dtype=np.float64).tobytes() if matrix and matrix[0] else repr(matrix).encode()


class NormMemoTests(unittest.TestCase):
    def test_every_cosine_is_the_uncached_one_to_the_last_bit(self) -> None:
        rng = random.Random(104)
        entities = [[rng.gauss(0.0, 1.0) for _ in range(128)] for _ in range(40)]
        entities[3] = [0.0] * 128  # a zero row gives the -1.0 convention
        entities[5] = [-0.0 if i % 2 else 0.0 for i in range(128)]
        entities[7] = [1e-300 * rng.random() for _ in range(128)]  # squares underflow
        for frame in range(30):  # the same entity rows frame after frame, as the memo will see them
            fragments = [[rng.gauss(0.0, 1.0) for _ in range(128)] for _ in range(rng.randint(1, 12))]
            if frame % 7 == 0:
                entities[rng.randrange(len(entities))] = [rng.gauss(0.0, 1.0) for _ in range(128)]  # a descriptor changes
            for left, right in ((fragments, entities), (fragments, entities), (entities, entities)):
                self.assertEqual(bits(la.cosine_matrix(left, right)), bits(cosine_matrix_before_the_cache(left, right)))
        self.assertGreater(la._row_norm.cache_info().hits, 0)

    def test_edge_shapes_keep_their_conventions(self) -> None:
        cases = (([], [[1.0, 2.0]]), ([[1.0, 2.0]], []), ([[1.0, 2.0]], [[1.0, 2.0, 3.0]]), ([[]], [[]]),
                 ([[1, 2], [3, 4]], [[0, 0], [5, 6]]))
        for left, right in cases:
            with self.subTest(left=left, right=right):
                self.assertEqual(repr(la.cosine_matrix(left, right)), repr(cosine_matrix_before_the_cache(left, right)))


class IdentityMemoTests(unittest.TestCase):
    def setUp(self) -> None:
        steps, _ = fixtures.run_all("TAF", config={"theta_a": 0.7, "d_a": None})
        self.memories = [step["state"]["memory"] for step in steps]
        self.evidence: dict[str, str | None] = {}
        for step in steps:  # the scenario's two objects: region:a is object A, region:b object B
            for fragment_id in step["stage_a"]["rows"]:
                self.evidence[f"{step['receipt']['frame_digest']}|{fragment_id}"] = "Obj|A" if fragment_id.endswith("a") else "Obj|B"

    def test_every_identity_is_the_uncached_one(self) -> None:
        evidence: dict[str, str | None] = {}
        for memory in self.memories:
            for key, value in self.evidence.items():  # the map grows by new keys only, as the teacher's does
                if key not in evidence:
                    evidence[key] = value
                    for again in range(2):  # the second call is a memo hit
                        self.assertEqual(lt.entity_identities(memory, evidence), entity_identities_before_the_cache(memory, evidence))
        same_entries = dict(evidence)  # another map object with the same entries and length
        for memory in self.memories:
            self.assertEqual(lt.entity_identities(memory, same_entries), entity_identities_before_the_cache(memory, same_entries))
        resolved = lt.entity_identities(self.memories[-1], evidence)
        self.assertTrue(any(row["resolvable"] for row in resolved.values()))

    def test_a_caller_that_changes_its_result_changes_nobody_else_s(self) -> None:
        first = lt.entity_identities(self.memories[-1], self.evidence)
        for row in first.values():
            row["key"] = "changed"
            row["keys_seen"].append("changed")
        self.assertEqual(lt.entity_identities(self.memories[-1], self.evidence),
                         entity_identities_before_the_cache(self.memories[-1], self.evidence))

    def test_no_digest_and_more_memories_than_the_memo_keeps(self) -> None:
        undigested = {"entities": self.memories[-1]["entities"]}
        self.assertEqual(lt.entity_identities(undigested, self.evidence), entity_identities_before_the_cache(undigested, self.evidence))
        maps = [dict(self.evidence) for _ in range(lt.IDENTITY_MEMO_SIZE + 3)]
        for evidence in maps:
            for memory in self.memories:
                self.assertEqual(lt.entity_identities(memory, evidence), entity_identities_before_the_cache(memory, evidence))
        self.assertLessEqual(len(lt._IDENTITY_MEMO), lt.IDENTITY_MEMO_SIZE)


if __name__ == "__main__":
    unittest.main()
