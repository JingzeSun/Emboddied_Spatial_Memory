"""Fixed SH-03 case adaptation and acceptance, without a new physics engine.

Standard-library checks import no numerical package. generate_case alone loads
the approved SH-02 generator. Every completed case is saved, including failures.
"""
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .pair_contract import audit_pair, require


def validate_case(case):
    require(set(case) == {"case_id", "wall_y_m", "start_x_m", "history_arc_samples"}, "case fields mismatch")
    require(isinstance(case["case_id"], str) and re.fullmatch(r"sh03-[0-9]{2}", case["case_id"]), "unsafe case id")
    require(type(case["wall_y_m"]) in (int, float) and case["wall_y_m"] in (0.52, 0.58, 0.64, 0.70), "unregistered wall distance")
    require(type(case["start_x_m"]) in (int, float) and case["start_x_m"] in (-0.02, 0.02), "unregistered common start")
    require(type(case["history_arc_samples"]) is int and case["history_arc_samples"] in (13, 23), "unregistered history length")


def validate_registry(registry):
    require(set(registry) == {"stage", "version", "family_id", "split", "prior_receipt_sha256",
                             "unique_branches", "replay_branches", "output_budget_bytes", "cases"}, "registry fields mismatch")
    require(registry["stage"] == "SH-03" and registry["version"] == "sh03-development-v1"
            and registry["split"] == "development"
            and registry["family_id"] == "sh03-fixed-factorial-development", "unsupported stage/split/family")
    require(registry["prior_receipt_sha256"] == "97d83ca73cdad22a9c1ab46ce24dc0b7e8e50103e174f968dca6fc2455460a6b", "unapproved prerequisite")
    cases = registry["cases"]
    require(len(cases) == 16 and [c["case_id"] for c in cases] == [f"sh03-{i:02d}" for i in range(16)], "case inventory/order changed")
    for case in cases:
        validate_case(case)
    expected = list(itertools.product((0.52, 0.58, 0.64, 0.70), (-0.02, 0.02), (13, 23)))
    require([(c["wall_y_m"], c["start_x_m"], c["history_arc_samples"]) for c in cases] == expected, "incomplete/duplicated factorial cases")
    require(registry["unique_branches"] == registry["replay_branches"] == 64
            and registry["output_budget_bytes"] == 2 * 1024**3, "budget changed")
    return cases


def prepare_case(base_config, base_xml, case):
    """Only wall depth, shared starting x, camera aim and arc duration vary."""
    validate_case(case)
    config = deepcopy(base_config)
    config["version"] = "sh03-development-v1"
    config["history_arc_samples"] = case["history_arc_samples"]
    config["camera_target_m"][0] = case["start_x_m"]
    tree = ET.fromstring(base_xml)
    tree.set("model", "sh03-development-v1")
    changes = [("./worldbody/geom[@name='wall']", 1, case["wall_y_m"]),
               ("./worldbody/body[@name='object']", 0, case["start_x_m"]),
               ("./worldbody/body[@name='pusher']", 0, case["start_x_m"])]
    for path, axis, value in changes:
        element = tree.find(path)
        require(element is not None, f"missing base entity: {path}")
        pos = element.attrib["pos"].split()
        pos[axis] = str(value)
        element.set("pos", " ".join(pos))
    return config, ET.tostring(tree, encoding="unicode")


def assess(contract, evidence, config):
    """Classify a completed case; a failed contrast is retained, never replaced."""
    branches, history = evidence["branches"], evidence["history_visibility"]
    recent = config["recent_frames"]
    hits = [b for b in branches if b["hidden_contact_steps"] > 0]
    separation = evidence["final_separation_m_by_action"]
    checks = {
        "paired_input_contract": contract.get("contract_valid") is True,
        "early_evidence_differs": contract.get("early_visual_evidence_differs") is True,
        "branch_order": [(b["world_index"], b["action_index"]) for b in branches] == [(0, 0), (0, 1), (1, 0), (1, 1)],
        "early_wall_visible": len(history) == 2 and all(h[0]["wall"] >= config["minimum_early_wall_pixels"] for h in history),
        "recent_wall_hidden_object_visible": len(history) == 2 and all(len(h) > recent and all(v["wall"] == 0 and v["object"] > 0 for v in h[-recent:]) for h in history),
        "complete_nonlayout_state_equal": evidence["nonlayout_integration_equal"] is True,
        "observing_preserves_state": evidence["observation_preserves_snapshot"] == [True, True],
        "independent_replay_exact": evidence["replay_equal"] == [True] * 4,
        "expected_wall_contact_pattern": [b["wall_contact_steps"] > 0 for b in branches] == [True, False, False, True],
        "positive_contacts_out_of_view": len(hits) == 2 and all(b["max_contact_object_pixels"] == 0 for b in hits),
        "no_screen_contact": len(branches) == 4 and all(b["screen_contact_steps"] == 0 for b in branches),
        "planar_and_force_bounds": len(branches) == 4 and all(
            config["minimum_object_height_m"] <= b["object_z_range_m"][0]
            <= b["object_z_range_m"][1] <= config["maximum_object_height_m"]
            and 0 <= b["max_tilt_rad"] <= config["maximum_tilt_rad"]
            and 0 <= b["max_actuator_force_n"] <= 20 + 1e-9 for b in branches),
        "both_actions_have_contrast": len(separation) == 2 and all(math.isfinite(d) and d >= config["minimum_outcome_separation_m"] for d in separation),
    }
    return {"checks": checks, "failed_checks": [k for k, v in checks.items() if not v],
            "accepted": all(checks.values()), "contract": contract,
            "branches": branches, "separation_m_by_action": separation}


def generate_case(directory, base_config_path, base_xml_path, case, registry):
    from .physics_fixture import generate_fixture, save_json
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    base_config = json.loads(Path(base_config_path).read_text(encoding="utf-8"))
    config, xml = prepare_case(base_config, Path(base_xml_path).read_text(encoding="utf-8"), case)
    save_json(directory / "input_config.json", config)
    (directory / "input_model.xml").write_text(xml, encoding="utf-8")
    raw_pair, evidence = generate_fixture(directory / "raw", directory / "input_config.json", directory / "input_model.xml")
    # Preserve original generator output; only dataset bookkeeping differs here.
    pair = {**raw_pair, "pair_id": case["case_id"], "family_id": registry["family_id"], "split": registry["split"]}
    save_json(directory / "pair.json", pair)
    try:
        contract = audit_pair(pair)
    except ValueError as error:
        contract = {"contract_valid": False, "error": str(error)}
    report = {"case": case, **assess(contract, evidence, config)}
    save_json(directory / "audit.json", report)
    return report
