#!/usr/bin/env python3
"""Review-stage entry point for post-D-183 VM-04 observation construction.

Only ``check`` is reachable in the committed configuration.  Mutating planning
commands have independent gates and the simulator execution commands do not
exist yet, so schema approval cannot accidentally start data generation.
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
from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    make_source_pool_manifest,
    seal_formal_selection,
    validate_approved_contract,
    validate_source_pool_manifest,
)


CONFIG = ROOT / "configs" / "vsmt" / "vm04_observation_suitability_proposal_v1.json"
SCHEMA = ROOT / "schemas" / "vsmt_vm04_observation_construction.schema.json"


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ObservationConstructionError(f"duplicate JSON key: {key}")
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


def load_contract() -> dict[str, Any]:
    return validate_approved_contract(read_json(CONFIG))


def require_gate(contract: dict[str, Any], gate: str) -> None:
    if contract["authorization"].get(gate) is not True:
        raise ObservationConstructionError(f"{gate} is not authorized")


def check() -> None:
    contract = load_contract()
    schema = read_json(SCHEMA)
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ObservationConstructionError("observation schema draft changed")
    if len(schema.get("oneOf", [])) != 6:
        raise ObservationConstructionError("observation schema record set changed")
    print(
        "VM04_OBSERVATION_STAGE_CHECK_OK "
        f"status={contract['status']} execution_authorized=false"
    )


def seal_source_pool(input_path: Path, output_path: Path) -> None:
    contract = load_contract()
    require_gate(contract, "source_pool_sealing_authorized")
    source = read_json(input_path)
    if set(source) != {"source_manifest_sha256", "eligible_house_ids",
                       "selection_seed"}:
        raise ObservationConstructionError("source pool input has unexpected fields")
    manifest = make_source_pool_manifest(
        source["eligible_house_ids"],
        source_manifest_sha256=source["source_manifest_sha256"],
        selection_seed=source["selection_seed"],
    )
    write_new_json(output_path, manifest)


def seal_formal(input_pool: Path, pilot_outcomes: Path, output_path: Path) -> None:
    contract = load_contract()
    require_gate(contract, "formal_selection_sealing_authorized")
    pool = validate_source_pool_manifest(read_json(input_pool))
    outcomes = read_json(pilot_outcomes)
    if set(outcomes) != {"source_pool_manifest_sha256",
                         "completion_by_pool_index"}:
        raise ObservationConstructionError("pilot outcome has unexpected fields")
    if outcomes["source_pool_manifest_sha256"] != pool["manifest_sha256"]:
        raise ObservationConstructionError("pilot outcome does not bind source pool")
    raw = outcomes["completion_by_pool_index"]
    if type(raw) is not dict:
        raise ObservationConstructionError("pilot completion must be an object")
    completion = {}
    for key, value in raw.items():
        if type(key) is not str or not key.isdigit():
            raise ObservationConstructionError("pilot pool index must be decimal text")
        completion[int(key)] = value
    selection = seal_formal_selection(
        pool, pilot_completion_by_pool_index=completion)
    write_new_json(output_path, selection)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "seal-source-pool", "seal-formal"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--pilot-outcomes", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.mode == "check":
        check()
    elif arguments.mode == "seal-source-pool":
        if arguments.input is None or arguments.output is None:
            parser.error("seal-source-pool requires --input and --output")
        seal_source_pool(arguments.input, arguments.output)
    else:
        if (arguments.input is None or arguments.pilot_outcomes is None or
                arguments.output is None):
            parser.error("seal-formal requires --input, --pilot-outcomes and --output")
        seal_formal(arguments.input, arguments.pilot_outcomes, arguments.output)


if __name__ == "__main__":
    try:
        main()
    except ObservationConstructionError as error:
        raise SystemExit(f"VM04_OBSERVATION_STAGE_REFUSED: {error}") from error
