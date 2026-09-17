#!/usr/bin/env python3
"""Check or seal the D-210 two-house, twelve-slot P0 manifests.

The committed contract permits ``check`` only.  ``seal-batch`` fails before it
reads source-house or route files unless the two narrow sealing gates are both
opened in a reviewed successor contract.  It never runs a simulator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d210_place_memory import (  # noqa: E402
    build_p0_manifests,
    validate_contract,
    validate_route_plan,
)


DEFAULT_CONTRACT = ROOT / "configs/vsmt/vm04_d210_dual_layer_p0_v1.json"


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_reject_duplicate_pairs)


def write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")


def load_contract(path: Path) -> dict[str, Any]:
    return validate_contract(read_json(path))


def check(contract_path: Path) -> dict[str, Any]:
    contract = load_contract(contract_path)
    return {
        "decision_id": contract["decision_id"],
        "status": contract["status"],
        "slot_count": len(contract["slot_plan"]),
        "scenario_order": [row["scenario_id"]
                           for row in contract["slot_plan"]],
        "scientific_maximum_route_actions":
            contract["movement"]["scientific_maximum_route_actions"],
        "mechanical_route_action_guard":
            contract["movement"]["mechanical_route_action_guard"],
        "place_identity_is_a_metric_grid_cell":
            contract["scope"]["place_identity_is_a_metric_grid_cell"],
        "authorization": contract["authorization"],
        "execution_authorized": all(contract["authorization"][name] is True
                                    for name in (
                                        "source_house_binding_authorized",
                                        "route_plan_sealing_authorized",
                                    )),
    }


def seal_batch(
    *, contract_path: Path, source_houses_path: Path, routes_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    authorization = contract["authorization"]
    if contract["status"] != "frozen_executable":
        raise ValueError("D-210 contract is not frozen_executable")
    for gate in ("source_house_binding_authorized",
                 "route_plan_sealing_authorized"):
        if authorization[gate] is not True:
            raise ValueError(f"{gate} is not authorized")
    # External paths are intentionally untouched until both gates pass.
    source_bundle = read_json(source_houses_path)
    route_bundle = read_json(routes_path)
    if (type(source_bundle) is not dict or set(source_bundle) != {
            "schema_version", "houses"} or
            source_bundle["schema_version"] !=
            "vsmt-vm04-d210-p0-source-houses-v1"):
        raise ValueError("D-210 source-house bundle is invalid")
    if (type(route_bundle) is not dict or set(route_bundle) != {
            "schema_version", "routes"} or
            route_bundle["schema_version"] !=
            "vsmt-vm04-d210-p0-route-bundle-v1"):
        raise ValueError("D-210 route bundle is invalid")
    routes = [validate_route_plan(row, contract)
              for row in route_bundle["routes"]]
    public, private = build_p0_manifests(
        source_houses=source_bundle["houses"], route_plans=routes,
        contract=contract)
    if output_root.exists():
        raise ValueError("D-210 output root exists; sealed batches are immutable")
    for route in sorted(routes, key=lambda row: row["slot"]):
        write_new_json(output_root / "provenance/routes" /
                       f"slot_{route['slot']:02d}.json", route)
    write_new_json(output_root / "public/manifest.json", public)
    write_new_json(output_root / "private/manifest.json", private)
    receipt = {
        "schema_version": "vsmt-vm04-d210-p0-seal-receipt-v1",
        "slot_count": 12,
        "public_manifest_sha256": public["manifest_sha256"],
        "private_manifest_sha256": private["manifest_sha256"],
        "simulator_started": False,
        "episodes_generated": 0,
    }
    write_new_json(output_root / "seal.receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    seal_parser = subparsers.add_parser("seal-batch")
    seal_parser.add_argument("--source-houses", type=Path, required=True)
    seal_parser.add_argument("--routes", type=Path, required=True)
    seal_parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "check":
        result = check(arguments.contract)
    else:
        result = seal_batch(
            contract_path=arguments.contract,
            source_houses_path=arguments.source_houses,
            routes_path=arguments.routes,
            output_root=arguments.output_root,
        )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
