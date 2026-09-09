"""Pre-rebuild planning helpers; no training, data access or test release."""
from __future__ import annotations

import math


def validate_rebuild_test_marker(marker: dict, root, plan: dict, *, expected_tests: int | None = None) -> None:
    """Bind server full-test evidence to corrected science, preserving history."""
    from cpmt.m1_protocol import protocol_sha256
    from cpmt.run_provenance import source_tree_sha256
    required = {
        "schema_version": "cpmt-scope-rebuild-tests-v1",
        "corrected_protocol_sha256": plan["corrected_source"]["protocol_sha256"],
        "rebuild_plan_sha256": protocol_sha256(plan),
        "exit_code": 0, "failures": 0, "errors": 0, "skipped": 0,
        "source_tree_unchanged": True, "test_access": False,
        "validation_confirmation_run": False, "new_confirmation_groups_generated": False,
    }
    if any(marker.get(k) != v for k, v in required.items()):
        raise ValueError("scope rebuild test marker failed/status/binding mismatch")
    count = marker.get("tests_run", 0)
    if count < 280 or count != marker.get("expected_tests") or (expected_tests is not None and count != expected_tests):
        raise ValueError("scope rebuild full-test count mismatch")
    if marker.get("provenance", {}).get("git_dirty") is not False:
        raise ValueError("scope rebuild tests require clean provenance")
    if marker.get("source_and_tests_sha256") != source_tree_sha256(root, roots=("src", "scripts", "configs", "tests")):
        raise ValueError("scope rebuild test marker does not cover current source/tests")


def corrected_test_groups(plan: dict, cells: dict, *, oracle_integrity_pass: bool) -> int:
    """One train-only recalculation with a frozen floor, never an effect chase.

    This helper is not yet wired into the historical registration validator.
    Callers must validate the corrected probe provenance before supplying cells.
    """
    if not oracle_integrity_pass:
        raise ValueError("oracle integrity failure: stop without endpoint switch")
    endpoints = plan["endpoints"]
    metrics = [endpoints[k] for k in ("semantic", "support", "burden")]
    expected = {(m, c) for m in metrics for c in endpoints["contrasts"]}
    if set(cells) != expected:
        raise ValueError("exactly six registered endpoint/contrast cells required")
    power = plan["test_size"]
    required = [int(power["floor"])]
    multiple = int(power["round_up_to_multiple"])
    for index, metric in enumerate(metrics):
        delta = endpoints["planning_effects"][index] - endpoints["minimum_effects"][index]
        for contrast in endpoints["contrasts"]:
            cell = cells[(metric, contrast)]
            sd = float(cell["paired_group_standard_deviation"])
            if cell["nondegenerate"] is not True or not math.isfinite(sd) or sd <= 0:
                raise ValueError("degenerate/invalid endpoint: stop without switch")
            raw = ((power["z_one_sided_alpha"] + power["z_power"]) * sd / delta) ** 2
            required.append(math.ceil(raw / multiple) * multiple)
    return max(required)


def feasible_layouts(plan: dict, *, cpu_capacity: float, gpu_free_gib: float,
                     host_available_gib: float) -> tuple[list[dict], list[dict]]:
    """Conservative capacity screen, not a guarantee against memory failure."""
    limits = plan["concurrency"]
    accepted, rejected = [], []
    for workers, threads in limits["benchmark_layouts"]:
        reasons = []
        if workers * threads > cpu_capacity:
            reasons.append("cpu_capacity")
        if workers * limits["gpu_memory_budget_gib_per_process"] + limits["gpu_memory_reserve_gib"] > gpu_free_gib:
            reasons.append("gpu_headroom")
        if workers * limits["host_memory_budget_gib_per_process"] + limits["host_memory_reserve_gib"] > host_available_gib:
            reasons.append("host_memory_headroom")
        row = {"workers": workers, "threads": threads}
        if reasons:
            rejected.append(dict(row, reasons=reasons))
        else:
            accepted.append(row)
    return accepted, rejected


def runtime_recommendation(layouts: list[dict]) -> dict:
    """Prefer lower concurrency when timings are practically tied."""
    if not layouts or any(not math.isfinite(x["elapsed_seconds"]) or x["elapsed_seconds"] <= 0 for x in layouts):
        raise ValueError("finite positive complete-layout times required")
    fastest = min(x["elapsed_seconds"] for x in layouts)
    candidates = [x for x in layouts if x["elapsed_seconds"] <= fastest * 1.05]
    chosen = min(candidates, key=lambda x: (x["workers"], x["threads"]))
    return {"workers": chosen["workers"], "threads": chosen["threads"],
            "elapsed_seconds": chosen["elapsed_seconds"], "preliminary_runtime_only": True}
