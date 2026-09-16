"""Private-only physical RELINK label gate over sealed public relation evidence."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cpmt.executor import validate_graph  # noqa: E402
from vsmt.contracts import validate_observation_packet  # noqa: E402
from vsmt.vm04_materializer_receipt import (  # noqa: E402
    validate_materializer_receipt,
)
import vm04_two_house_audit as audit  # noqa: E402


PRIVATE_KEYS = {
    "schema_version", "old_instance_id", "new_instance_id",
    "old_place_region_id", "new_place_region_id",
    "prior_entity_node_id", "prior_edge_id",
    "unforced_robot_action_verified", "stable_actual_relation_changed",
}
CROSSWALK_KEYS = {"schema_version", "observation_index", "bindings"}
BINDING_KEYS = {"instance_id", "region_id", "mask_sha256"}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _located_at(packet, source_region_id, place_region_id):
    return [relation for relation in packet["relation_observations"]
            if relation["relation"] == "located_at" and
            relation["source_region_id"] == source_region_id and
            relation["target_region_id"] == place_region_id]


def _crosswalk_region(path, observation_index, instance_id, packet):
    """Resolve a private instance through the trusted L1 crosswalk."""
    crosswalk = audit.read_json(Path(path))
    require(set(crosswalk) == CROSSWALK_KEYS and
            crosswalk["schema_version"] ==
            "vsmt-vm04-private-region-crosswalk-v1" and
            crosswalk["observation_index"] == observation_index and
            type(crosswalk["bindings"]) is list,
            "private L1 crosswalk schema changed")
    rows = []
    for row in crosswalk["bindings"]:
        require(type(row) is dict and set(row) == BINDING_KEYS and
                all(type(row[key]) is str and row[key] for key in BINDING_KEYS) and
                len(row["mask_sha256"]) == 64,
                "private L1 crosswalk binding changed")
        if row["instance_id"] == instance_id:
            rows.append(row)
    if len(rows) != 1:
        return None, False
    row = rows[0]
    public_regions = [region for region in packet["region_observations"]
                      if region["region_id"] == row["region_id"] and
                      region["structure_kind"] == "entity" and
                      region["mask_sha256"] == row["mask_sha256"]]
    return (row["region_id"], len(public_regions) == 1)


def evaluate_physical_relink(public_root: Path, private_outcome_path: Path,
                             old_crosswalk_path: Path,
                             new_crosswalk_path: Path) -> dict:
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
    materializer_path = public_root / "materializer.receipt.json"
    require(audit.sha256(old_path) == seal["old_packet_sha256"] and
            audit.sha256(prior_path) == seal["prior_memory_sha256"] and
            audit.sha256(post_path) == seal["post_packet_sha256"] and
            audit.sha256(materializer_path) ==
            seal["materializer_receipt_sha256"],
            "sealed public relation source bytes changed")
    materializer = validate_materializer_receipt(
        audit.read_json(materializer_path))
    old_pair = (audit.sha256(old_path), audit.sha256(old_crosswalk_path))
    new_pair = (audit.sha256(post_path), audit.sha256(new_crosswalk_path))
    old_receipt_rows = [
        row for row in materializer["frames"]
        if (row["public_packet_sha256"], row["private_crosswalk_sha256"]) ==
        old_pair
    ]
    new_receipt_rows = [
        row for row in materializer["frames"]
        if (row["public_packet_sha256"], row["private_crosswalk_sha256"]) ==
        new_pair
    ]
    require(len(old_receipt_rows) == len(new_receipt_rows) == 1,
            "crosswalk provenance is not bound by the materializer receipt")
    require(old_receipt_rows[0]["observation_index"] <
            new_receipt_rows[0]["observation_index"],
            "sealed RELINK old observation must precede post observation")
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
                "old_instance_id", "new_instance_id", "old_place_region_id",
                "new_place_region_id", "prior_entity_node_id",
                "prior_edge_id")) and
            type(private["unforced_robot_action_verified"]) is bool and
            type(private["stable_actual_relation_changed"]) is bool,
            "private physical RELINK outcome schema changed")
    old_region_id, old_binding = _crosswalk_region(
        old_crosswalk_path, old_receipt_rows[0]["observation_index"],
        private["old_instance_id"], old)
    new_region_id, new_binding = _crosswalk_region(
        new_crosswalk_path, new_receipt_rows[0]["observation_index"],
        private["new_instance_id"], post)
    old_rows = _located_at(old, old_region_id,
                           private["old_place_region_id"])
    new_rows = _located_at(post, new_region_id,
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
        old_place and new_place and len(old_rows) == len(new_rows) == 1 and
        old_place["structure_kind"] == new_place["structure_kind"] == "place"
        and old_place["mask_sha256"] != new_place["mask_sha256"]
        and old_rows[0]["support_sha256"] != new_rows[0]["support_sha256"])
    crosswalks_verified = old_binding and new_binding
    checks = {
        "same_physical_instance":
            crosswalks_verified and
            private["old_instance_id"] == private["new_instance_id"],
        "private_crosswalk_bindings_verified": crosswalks_verified,
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
        "materializer_receipt_sha256": audit.sha256(materializer_path),
        "old_private_crosswalk_sha256": audit.sha256(old_crosswalk_path),
        "new_private_crosswalk_sha256": audit.sha256(new_crosswalk_path),
        "physical_relink_positive": all(checks.values()),
        "checks": checks,
        "failure_reasons": sorted(key for key, passed in checks.items()
                                  if not passed),
        "private_ids_exported": False,
        "candidate_or_teacher_evaluated": False,
    }
