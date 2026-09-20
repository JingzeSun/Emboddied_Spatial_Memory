"""D-224-S1 ruling 9: the lean cores reuse pure helpers without the old line.

Two things are pinned here.  First, that the copied helpers still return
exactly what ``vsmt.graph_ops`` returns, so cutting the import moved no
number.  Second, that no lean module imports ``vsmt.graph_ops`` or anything
under ``cpmt`` except the pure ``cpmt.hashing``, so the archived
unified-graph executor and ``GraphRevision`` no longer reach the current
entry point even transitively.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path
import random
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import graph_ops, lean_geometry  # noqa: E402


LEAN_MODULES = ("lean_geometry", "lean_memory", "lean_intervention",
                "lean_assignment", "lean_teacher", "lean_arms", "lean_assets")


def module_imports(name: str) -> set[str]:
    tree = ast.parse((SRC_ROOT / "vsmt" / f"{name}.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


class TestCopiedHelpersAgree(unittest.TestCase):
    def test_cosine_agrees_on_random_vectors(self) -> None:
        rng = random.Random(224001)
        for _ in range(200):
            width = rng.randint(1, 8)
            left = [rng.uniform(-3.0, 3.0) for _ in range(width)]
            right = [rng.uniform(-3.0, 3.0) for _ in range(width)]
            self.assertEqual(lean_geometry.cosine_similarity(left, right),
                             graph_ops.cosine_similarity(left, right))

    def test_cosine_agrees_on_the_degenerate_cases(self) -> None:
        for left, right in (([], []), ([1.0], []), ([0.0, 0.0], [1.0, 2.0]),
                            ([1.0, 2.0], [1.0, 2.0]), ([1.0, 2.0], [-1.0, -2.0])):
            self.assertEqual(lean_geometry.cosine_similarity(left, right),
                             graph_ops.cosine_similarity(left, right))

    def test_centroid_distance_agrees_on_random_points(self) -> None:
        rng = random.Random(224002)
        for _ in range(200):
            left = {"centroid_m": [rng.uniform(-9.0, 9.0) for _ in range(3)]}
            right = {"centroid_m": [rng.uniform(-9.0, 9.0) for _ in range(3)]}
            self.assertEqual(lean_geometry.centroid_distance(left, right),
                             graph_ops.centroid_distance(left, right))

    def test_opaque_id_agrees_and_stays_opaque(self) -> None:
        for parts in (("chair", 3), ("a", "b", "c"), (0,), ("house-0001", "cup")):
            copied = lean_geometry.opaque_id(*parts, prefix="entity")
            self.assertEqual(copied, graph_ops.opaque_id(*parts, prefix="entity"))
            self.assertTrue(copied.startswith("entity:"))
            for part in parts:
                # Short parts can collide with hex digits by chance, so only
                # the distinctive ones are checked for leakage.
                if len(str(part)) >= 4:
                    self.assertNotIn(str(part), copied.split(":", 1)[1])

    def test_a_bad_cosine_would_be_caught(self) -> None:
        # Guard the guard: if the two copies ever diverge, the comparison
        # above must fail rather than pass vacuously.
        self.assertNotEqual(lean_geometry.cosine_similarity([1.0, 0.0], [0.0, 1.0]),
                            lean_geometry.cosine_similarity([1.0, 0.0], [1.0, 0.0]))
        self.assertTrue(math.isclose(
            lean_geometry.cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0))


class TestLeanImportBoundary(unittest.TestCase):
    def test_no_lean_module_imports_the_archived_graph_line(self) -> None:
        for name in LEAN_MODULES:
            for imported in module_imports(name):
                self.assertNotEqual(imported, "vsmt.graph_ops", name)
                self.assertNotEqual(imported, "cpmt.executor", name)
                self.assertNotEqual(imported, "cpmt", name)

    def test_the_only_cpmt_module_a_lean_core_may_touch_is_hashing(self) -> None:
        for name in LEAN_MODULES:
            for imported in module_imports(name):
                if imported.split(".")[0] == "cpmt":
                    self.assertEqual(imported, "cpmt.hashing", name)

    def test_the_transitive_closure_is_free_of_the_old_executor(self) -> None:
        seen: set[str] = set()
        stack = [f"vsmt.{name}" for name in LEAN_MODULES]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            relative = Path(*current.split("."))
            source = SRC_ROOT / relative.with_suffix(".py")
            if not source.exists():
                continue
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    stack.append(node.module)
                elif isinstance(node, ast.Import):
                    stack.extend(alias.name for alias in node.names)
        self.assertNotIn("cpmt.executor", seen)
        self.assertNotIn("vsmt.graph_ops", seen)
        self.assertIn("cpmt.hashing", seen)

    def test_graph_ops_still_serves_the_archived_modules(self) -> None:
        # The old line is kept in the tree; cutting the lean edge must not
        # have deleted or emptied it.
        self.assertTrue(hasattr(graph_ops, "GraphRevision"))
        self.assertIn("cpmt.executor", module_imports("graph_ops"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
