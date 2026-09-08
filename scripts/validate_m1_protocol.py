"""Validate and fingerprint the M1 pre-test protocol candidate; never open test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_protocol import load_and_validate, load_and_validate_endpoint_probe, protocol_sha256
from cpmt.m1_registration import load_registration


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=PROJECT / "configs" / "m1_hard_condition.json",
    )
    args = parser.parse_args()
    config = load_and_validate(args.config)
    overlay = load_and_validate_endpoint_probe(
        PROJECT / "configs/m1_endpoint_viability_probe.json", config,
    )
    registration = load_registration(PROJECT, config, overlay)
    summary = {
        "protocol": config["protocol"],
        "status": config["status"],
        "test_access": config["test_access"],
        "methods": [item["id"] for item in config["methods"]],
        "candidate_k": config["candidates"]["budget_k"],
        "primary_horizon": config["future"]["primary_horizon"],
        "formal_seeds": config["training"]["formal_seeds"],
        "primary_contrasts": config["evaluation"]["primary_contrasts"],
        "protocol_sha256": protocol_sha256(config),
        "post_probe_registration_sha256": protocol_sha256(registration),
        "evaluation_plan": registration["evaluation_plan"],
        "execution_boundary": registration["execution_boundary"],
        "test_release_authorized": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
