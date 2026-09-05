"""Validate and fingerprint the M1 pre-test protocol candidate; never open test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_protocol import load_and_validate, protocol_sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=PROJECT / "configs" / "m1_hard_condition.json",
    )
    args = parser.parse_args()
    config = load_and_validate(args.config)
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
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
