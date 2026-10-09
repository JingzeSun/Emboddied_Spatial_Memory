"""D-224-S1 ruling 9: the lean cores reuse pure helpers without the old line.

Two things are pinned here.  First, that the copied helpers still return
exactly what ``vsmt.graph_ops`` returned, so cutting the import moved no
number.  ``graph_ops`` was removed from ``main`` after the tag ``paper-v1``;
its outputs on the same random inputs were recorded there as the digests
below (SHA-256 over ``float.hex`` of each value, one per line), and the
degenerate cases and opaque IDs as literal values.  Second, that no lean
module imports ``vsmt.graph_ops`` or anything under ``cpmt`` except the pure
``cpmt.hashing``, and that importing the lean modules loads neither at run
time, so the archived unified-graph executor and ``GraphRevision`` no longer
reach the current entry points.
"""

from __future__ import annotations

import ast
import hashlib
import math
from pathlib import Path
import random
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_geometry  # noqa: E402

#: ``graph_ops.cosine_similarity`` and ``graph_ops.centroid_distance`` on the inputs drawn below, at ``paper-v1``.
GRAPH_OPS_COSINE_SHA256 = "6c52c6df5256781e0915aceca262d207991ecc651eba59773ecdbcd09fa2deb7"
GRAPH_OPS_DISTANCE_SHA256 = "c03947ac1ac5b4e56d654de2600ef92efc5c65ecf01097cbaed5644857c23b12"
GRAPH_OPS_DEGENERATE_COSINES = (
    (([], []), -1.0),
    (([1.0], []), -1.0),
    (([0.0, 0.0], [1.0, 2.0]), -1.0),
    (([1.0, 2.0], [1.0, 2.0]), 0.9999999999999998),
    (([1.0, 2.0], [-1.0, -2.0]), -0.9999999999999998),
)
GRAPH_OPS_OPAQUE_IDS = (
    (("chair", 3), "entity:8d80f83ad0964662"),
    (("a", "b", "c"), "entity:fa1844c2988ad15a"),
    ((0,), "entity:a37bbbb0764cc5bf"),
    (("house-0001", "cup"), "entity:a9c6d657c39c1efe"),
)


def float_digest(values: list[float]) -> str:
    return hashlib.sha256("\n".join(value.hex() for value in values).encode()).hexdigest()


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
        values = []
        for _ in range(200):
            width = rng.randint(1, 8)
            left = [rng.uniform(-3.0, 3.0) for _ in range(width)]
            right = [rng.uniform(-3.0, 3.0) for _ in range(width)]
            values.append(lean_geometry.cosine_similarity(left, right))
        self.assertEqual(float_digest(values), GRAPH_OPS_COSINE_SHA256)

    def test_cosine_agrees_on_the_degenerate_cases(self) -> None:
        for (left, right), expected in GRAPH_OPS_DEGENERATE_COSINES:
            self.assertEqual(lean_geometry.cosine_similarity(left, right), expected)

    def test_centroid_distance_agrees_on_random_points(self) -> None:
        rng = random.Random(224002)
        values = []
        for _ in range(200):
            left = {"centroid_m": [rng.uniform(-9.0, 9.0) for _ in range(3)]}
            right = {"centroid_m": [rng.uniform(-9.0, 9.0) for _ in range(3)]}
            values.append(lean_geometry.centroid_distance(left, right))
        self.assertEqual(float_digest(values), GRAPH_OPS_DISTANCE_SHA256)

    def test_opaque_id_agrees_and_stays_opaque(self) -> None:
        for parts, expected in GRAPH_OPS_OPAQUE_IDS:
            copied = lean_geometry.opaque_id(*parts, prefix="entity")
            self.assertEqual(copied, expected)
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

    def test_importing_the_lean_modules_loads_no_archived_module(self) -> None:
        # The package __init__ files no longer import the archived modules, so the
        # boundary above also holds at run time (it did not before paper-v1).
        code = ("import sys\n"
                f"sys.path.insert(0, {str(SRC_ROOT)!r})\n"
                f"for name in {LEAN_MODULES!r}:\n"
                "    __import__('vsmt.' + name)\n"
                "print(' '.join(sorted(m for m in sys.modules if m.split('.')[0] in ('vsmt', 'cpmt'))))\n")
        loaded = set(subprocess.check_output([sys.executable, "-c", code], text=True).split())
        self.assertIn("cpmt.hashing", loaded)
        self.assertEqual({name for name in loaded if not name.startswith("vsmt.lean_")} - {"vsmt", "cpmt", "cpmt.hashing"},
                         set())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
