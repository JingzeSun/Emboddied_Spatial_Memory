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
    assert_numeric_freeze_complete,
    make_source_pool_manifest,
    validate_approved_contract,
)
from vsmt.vm04_pilot_family_completion import (  # noqa: E402
    seal_formal_selection_from_pilot,
)
from vsmt.vm04_materializer_code_manifest import (  # noqa: E402
    make_vm04_materializer_code_manifest,
    verify_vm04_materializer_code_checkout,
)


CONFIG = ROOT / "configs" / "vsmt" / "vm04_observation_suitability_v4.json"
LEGACY_CONFIGS = (
    ROOT / "configs" / "vsmt" / "vm04_observation_suitability_v2.json",
    ROOT / "configs" / "vsmt" / "vm04_observation_suitability_proposal_v1.json",
)
SCHEMA = ROOT / "schemas" / "vsmt_vm04_observation_construction.schema.json"
MATERIALIZER_SCHEMAS = (
    ROOT / "schemas" / "vsmt_vm04_materializer_config.schema.json",
    ROOT / "schemas" / "vsmt_vm04_materializer_assets_receipt.schema.json",
    ROOT / "schemas" / "vsmt_vm04_materializer_code_manifest.schema.json",
    ROOT / "schemas" / "vsmt_vm04_materializer_receipt.schema.json",
    ROOT / "schemas" / "vsmt_vm04_program_matcher.schema.json",
    ROOT / "schemas" / "vsmt_vm04_episode_construction_receipt.schema.json",
    ROOT / "schemas" / "vsmt_vm04_online_program_plan_seal.schema.json",
    ROOT / "schemas" / "vsmt_vm04_parent_program_request.schema.json",
)


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
    for materializer_schema_path in MATERIALIZER_SCHEMAS:
        materializer_schema = read_json(materializer_schema_path)
        if materializer_schema.get("$schema") != (
                "https://json-schema.org/draft/2020-12/schema"):
            raise ObservationConstructionError(
                f"materializer schema draft changed: {materializer_schema_path.name}"
            )
    print(
        "VM04_OBSERVATION_STAGE_CHECK_OK "
        f"status={contract['status']} execution_authorized=false"
    )


def seal_materializer_code(
    code_root: Path, reviewed_commit: str, output_path: Path,
) -> None:
    """Create a reviewed source manifest only after its independent gate opens."""

    contract = load_contract()
    require_gate(contract, "materializer_code_sealing_authorized")
    try:
        manifest = make_vm04_materializer_code_manifest(
            code_root, reviewed_git_commit=reviewed_commit,
        )
        verify_vm04_materializer_code_checkout(
            manifest, repository_root=code_root,
        )
    except (OSError, ValueError) as error:
        raise ObservationConstructionError(str(error)) from error
    write_new_json(output_path, manifest)


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


def freeze_status() -> None:
    """Report whether every scientific choice is frozen, without opening work."""

    contract = load_contract()
    report = assert_numeric_freeze_complete(contract)
    pending = report["pending_artifact_digests"]
    print(
        "VM04_NUMERIC_FREEZE_OK "
        f"contract={report['contract_version']} status={report['status']} "
        f"scientific_decisions_frozen=true pending_artifact_digests={len(pending)} "
        f"pilot_completion_reviewed="
        f"{str(report['pilot_family_completion_reviewed']).lower()} "
        f"generation_authorized="
        f"{str(report['generation_authorized']).lower()}"
    )
    for name in pending:
        print(f"  pending_artifact_digest {name}")


def seal_formal(input_pool: Path, pilot_outcomes: Path, output_path: Path) -> None:
    """Seal the formal house count from mechanically derived pilot completion.

    ``--pilot-outcomes`` must be a completion record produced by
    :func:`vsmt.vm04_pilot_family_completion.derive_pilot_family_completion`
    from sealed route receipts; a hand-written boolean table is rejected by the
    record's own digest and provenance fields.
    """

    contract = load_contract()
    require_gate(contract, "formal_selection_sealing_authorized")
    pool = read_json(input_pool)
    completion = read_json(pilot_outcomes)
    selection = seal_formal_selection_from_pilot(pool, completion)
    write_new_json(output_path, selection)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=(
        "check", "freeze-status", "seal-materializer-code", "seal-source-pool",
        "seal-formal",
    ))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--code-root", type=Path)
    parser.add_argument("--reviewed-commit")
    parser.add_argument("--pilot-outcomes", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.mode == "check":
        check()
    elif arguments.mode == "freeze-status":
        freeze_status()
    elif arguments.mode == "seal-materializer-code":
        if (arguments.code_root is None or arguments.reviewed_commit is None or
                arguments.output is None):
            parser.error(
                "seal-materializer-code requires --code-root, "
                "--reviewed-commit and --output"
            )
        seal_materializer_code(
            arguments.code_root, arguments.reviewed_commit, arguments.output,
        )
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
