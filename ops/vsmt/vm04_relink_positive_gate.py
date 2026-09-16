"""Private-only physical RELINK label gate over sealed public relation evidence."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cpmt.executor import validate_graph  # noqa: E402
from vsmt.contracts import validate_observation_packet  # noqa: E402
import vm04_two_house_audit as audit  # noqa: E402


PRIVATE_KEYS = {
    "schema_version", "old_instance_id", "new_instance_id",
    "old_region_id", "new_region_id", "old_place_region_id",
    "new_place_region_id", "prior_entity_node_id", "prior_edge_id",
    "unforced_robot_action_verified", "stable_actual_relation_changed",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _located_at(packet, source_region_id, place_region_id):
    return [relation for relation in packet["relation_observations"]
            if relation["relation"] == "located_at" and
            relation["source_region_id"] == source_region_id and
            relation["target_region_id"] == place_region_id]


def evaluate_physical_relink(public_root: Path, private_outcome_path: Path) -> dict:
    """Open private identity only after public packet/graph bytes are sealed."""
    public_root = Path(public_root)
    seal_path = public_root / "relink-proof.seal.json"
    seal = audit.read_json(seal_path)
    marker = audit.read_json(public_root / "relink-proof.seal.success.json")
    require(marker == {"receipt_sha256": audit.sha256(seal_path)} and
            seal["schema_version"] == "vsmt-vm04-relink-public-proof-v1",
            "public RELINK proof seal is absent or changed")
    old_path = public_root / "old-observation-packet.json"
    prior_path = public_root / "prior-memory.json"
    post_path = public_root / "post-observation-packet.json"
    require(audit.sha256(old_path) == seal["old_packet_sha256"] and
            audit.sha256(prior_path) == seal["prior_memory_sha256"] and
            audit.sha256(post_path) == seal["post_packet_sha256"],
            "sealed public relation source bytes changed")
    old = validate_observation_packet(audit.read_json(old_path))
    prior = audit.read_json(prior_path)
    validate_graph(prior, verify_hash=True)
    post = validate_observation_packet(audit.read_json(post_path))
    require(post["prior_memory_ref"]["graph_sha256"] ==
            prior["graph_hash"],
            "post packet prior-memory binding changed")

    # This private file is read after the public evidence and its hashes.
    private = audit.read_json(Path(private_outcome_path))
    require(set(private) == PRIVATE_KEYS and
            private["schema_version"] == "vsmt-vm04-relink-private-outcome-v1" and
            all(type(private[key]) is str and private[key] for key in (
                "old_instance_id", "new_instance_id", "old_region_id",
                "new_region_id", "old_place_region_id",
                "new_place_region_id", "prior_entity_node_id",
                "prior_edge_id")) and
            type(private["unforced_robot_action_verified"]) is bool and
            type(private["stable_actual_relation_changed"]) is bool,
            "private physical RELINK outcome schema changed")
    old_rows = _located_at(old, private["old_region_id"],
                           private["old_place_region_id"])
    new_rows = _located_at(post, private["new_region_id"],
                           private["new_place_region_id"])
    old_edges = [edge for edge in prior["edges"]
                 if edge["edge_id"] == private["prior_edge_id"] and
                 edge["source"] == private["prior_entity_node_id"] and
                 edge["relation"] == "located_at" and
                 edge["valid_to"] is None]
    old_supported = any(
        "observation:" + row["support_sha256"] in edge["evidence_refs"]
        for row in old_rows for edge in old_edges)
    old_regions = {row["region_id"]: row
                   for row in old["region_observations"]}
    new_regions = {row["region_id"]: row
                   for row in post["region_observations"]}
    old_place = old_regions.get(private["old_place_region_id"])
    new_place = new_regions.get(private["new_place_region_id"])
    distinct_public_places = bool(
        old_place and new_place and old_rows and new_rows and
        old_place["structure_kind"] == new_place["structure_kind"] == "place"
        and old_place["centroid_m"] != new_place["centroid_m"]
        and old_rows[0]["support_sha256"] != new_rows[0]["support_sha256"])
    checks = {
        "same_physical_instance":
            private["old_instance_id"] == private["new_instance_id"],
        "public_old_relation_supported": old_supported,
        "public_new_relation_supported": bool(new_rows),
        "public_places_distinct": distinct_public_places,
        "unforced_robot_action_verified":
            private["unforced_robot_action_verified"],
        "stable_actual_relation_changed":
            private["stable_actual_relation_changed"],
    }
    return {
        "schema_version": "vsmt-vm04-physical-relink-verdict-v1",
        "public_proof_seal_sha256": audit.sha256(seal_path),
        "private_outcome_sha256": audit.sha256(private_outcome_path),
        "physical_relink_positive": all(checks.values()),
        "checks": checks,
        "failure_reasons": sorted(key for key, passed in checks.items()
                                  if not passed),
        "private_ids_exported": False,
        "candidate_or_teacher_evaluated": False,
    }
