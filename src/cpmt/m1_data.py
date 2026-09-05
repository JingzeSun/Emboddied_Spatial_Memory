"""Deterministic train/validation paired worlds for the frozen M1 contract.

The C00-C11 fixtures are semantic archetypes only. Generated records receive
fresh namespaces, synthetic online cues, independently executed candidate
branches, and a separate audit view. Formal test generation is intentionally
absent from this module.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .errors import CPMTError
from .executor import execute_transaction
from .hashing import canonical_json, seal_graph
from .m1_protocol import validate_m1_protocol


PROJECT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT / "experiments" / "counterfactual_transaction_learning"
    / "fixtures" / "draft"
)
SPLIT_SEED_OFFSET = {"train": 0, "validation": 100_000_000}
ASSET_BUCKETS = {"train": range(0, 32), "validation": range(32, 40)}
ONLINE_DENY_SUBSTRINGS = (
    "future", "oracle", "ground_truth", "simulator_hidden", "reference_program",
    "teacher", "audit", "persistent_object_id",
)

# primary is the original positive semantic; contrast creates its paired latent
# sibling. cue_name describes the lawful past/current signal in identifiable
# groups and is set to an uninformative midpoint in ambiguous groups.
FAMILY_RULES = {
    "C00": ("NOOP", "RELINK", "pose_compensation_consistency"),
    "C01": ("BIND", "BIRTH", "identity_continuity"),
    "C02": ("BIRTH", "BIND", "prior_observation_coverage"),
    "C03": ("REACTIVATE", "BIND", "dormant_identity_support"),
    "C04": ("SPLIT", "NOOP", "evidence_bimodality"),
    "C05": ("MERGE", "NOOP", "cross_node_identity_continuity"),
    "C06": ("REPLACE", "RELINK", "identity_discontinuity"),
    "C07": ("RETRACT", "NOOP", "reliable_visible_empty"),
    "C08": ("RELINK", "NOOP", "persistent_topology_change"),
    "C09": ("RELINK", "NOOP", "pose_reliability"),
    "C10": ("BIND", "NOOP", "static_surface_support"),
    "C11": ("BIND", "NOOP", "target_relevance_without_collateral"),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _namespace(value: Any, family: str, namespace: str) -> Any:
    if isinstance(value, str):
        return value.replace(family, namespace)
    if isinstance(value, list):
        return [_namespace(item, family, namespace) for item in value]
    if isinstance(value, dict):
        return {
            key: _namespace(item, family, namespace)
            for key, item in value.items()
        }
    return value


def _program_label(program: Mapping[str, Any]) -> str:
    if program["template"] == "COMPOSITE":
        return str(program.get("composition_label", "COMPOSITE"))
    return str(program["template"])


def _load_archetype(family: str) -> dict[str, Any]:
    directory = FIXTURE_ROOT / family
    case = _read_json(directory / "case.json")
    world = _read_json(directory / case["prior_graph_ref"])
    programs = [
        _read_json(directory / reference)
        for reference in case["candidate_transaction_refs"]
    ]
    evidence = [
        _read_json(path)
        for path in sorted((directory / "evidence").glob("*.json"))
    ]
    return {"case": case, "world": world, "programs": programs, "evidence": evidence}


def _synthetic_noop(case: Mapping[str, Any], namespace: str) -> dict[str, Any]:
    return {
        "schema_version": "cpmt-0.2",
        "transaction_id": f"tx-{namespace}-noop-control",
        "intent": "PRESERVE",
        "template": "NOOP",
        "base_graph_version": "v0",
        "operations": [],
        "evidence_refs": list(case["current_observation_refs"]),
        "protected_ids": list(case["protected_ids"]),
        "declared_edit_cost": 0,
        "declared_growth_cost": 0,
        "proposer": "fixed_m1_generator",
    }


def _materialize_archetype(
    raw: Mapping[str, Any], family: str, split: str, group_index: int,
) -> dict[str, Any]:
    namespace = f"{family}:{split}:{group_index:06d}"
    case = _namespace(deepcopy(raw["case"]), family, namespace)
    world = _namespace(deepcopy(raw["world"]), family, namespace)
    world["graph_id"] = f"world:{namespace}"
    world["graph_hash"] = None
    world = seal_graph(world)
    programs = _namespace(deepcopy(raw["programs"]), family, namespace)
    evidence_events = _namespace(deepcopy(raw["evidence"]), family, namespace)
    for program in programs:
        program["proposer"] = "fixed_m1_generator"
    if "NOOP" not in {_program_label(program) for program in programs}:
        programs.append(_synthetic_noop(case, namespace))
    if len(programs) > 16:
        raise ValueError(f"{family} archetype exceeds frozen K=16")
    evidence_by_id = {
        event["evidence_id"]: event for event in evidence_events
    }
    return {
        "namespace": namespace,
        "case": case,
        "world": world,
        "programs": programs,
        "evidence_by_id": evidence_by_id,
    }


def _state_tokens(graph: Mapping[str, Any]) -> set[str]:
    """Decision-relevant structural tokens for controlled future scoring."""
    tokens: set[str] = set()
    for node in graph["nodes"]:
        view = {
            key: node.get(key)
            for key in (
                "node_id", "node_version_id", "node_type", "lifecycle",
                "valid_from", "valid_to", "canonical_id", "predecessor_ids",
                "evidence_refs", "latent_refs",
            )
        }
        tokens.add("node:" + canonical_json(view))
    for edge in graph["edges"]:
        view = {
            key: edge.get(key)
            for key in (
                "edge_id", "edge_version_id", "source", "target", "relation",
                "frame", "valid_from", "valid_to", "evidence_refs",
            )
        }
        tokens.add("edge:" + canonical_json(view))
    return tokens


def project_structural_observation(
    graph: Mapping[str, Any], pose_bucket: int,
) -> frozenset[str]:
    """Fixed structural-token projection into a pose-conditioned view.

    This is an M1 analytic projector, not a learned visual representation or
    Projective Node Orbit. It prevents the teacher from comparing directly to
    the hidden reference graph while keeping the controlled task auditable.
    """
    return frozenset(
        hashlib.sha256(f"{pose_bucket}|{token}".encode("utf-8")).hexdigest()
        for token in _state_tokens(graph)
    )


def _execute_candidates(materialized: Mapping[str, Any]) -> list[dict[str, Any]]:
    base = materialized["world"]
    before = canonical_json(base)
    records = []
    for index, program in enumerate(materialized["programs"]):
        try:
            post = execute_transaction(
                base,
                program,
                evidence_by_id=materialized["evidence_by_id"],
            )
            failure = None
        except CPMTError as error:
            post = None
            failure = {"type": type(error).__name__, "message": str(error)}
        if canonical_json(base) != before:
            raise AssertionError("candidate execution mutated the immutable base")
        records.append({
            "candidate_index": index,
            "transaction_id": program["transaction_id"],
            "template": _program_label(program),
            "base_graph_hash": base["graph_hash"],
            "legal": failure is None,
            "post_graph": post,
            "post_graph_hash": post["graph_hash"] if post is not None else None,
            "failure": failure,
        })
    return records


def _choose_candidate(records: Iterable[Mapping[str, Any]], label: str) -> int:
    for record in records:
        if record["template"] == label and record["legal"]:
            return int(record["candidate_index"])
    raise ValueError(f"no legal {label} candidate in archetype")


def _teacher_posterior(energies: list[dict[str, Any]], temperature: float) -> list[float]:
    legal_totals = [
        float(item["total"]) for item in energies if not item["masked"]
    ]
    if not legal_totals:
        raise ValueError("paired group contains no legal candidate")
    minimum = min(legal_totals)
    weights = [
        0.0 if item["masked"]
        else math.exp(-(float(item["total"]) - minimum) / temperature)
        for item in energies
    ]
    denominator = sum(weights)
    return [weight / denominator for weight in weights]


def _candidate_energies(
    records: list[dict[str, Any]], reference_index: int,
    programs: list[dict[str, Any]], weights: Mapping[str, float],
    temperature: float, future_schedule: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[float], list[dict[str, Any]]]:
    reference = records[reference_index]["post_graph"]
    if reference is None:
        raise AssertionError("reference candidate must be legal")
    future_trace = []
    for step in future_schedule:
        projection = project_structural_observation(reference, step["pose_bucket"])
        future_trace.append({
            "step": step["step"],
            "source": "actual_executed_synthetic_trajectory",
            "pose_bucket": step["pose_bucket"],
            "pose_valid": True,
            "visibility_valid": True,
            "visibility_mask": "all_archetype_structural_tokens",
            "structural_observation": sorted(projection),
        })
    energies = []
    for record, program in zip(records, programs, strict=True):
        illegal = 0.0 if record["legal"] else 1.0
        if record["post_graph"] is None:
            future = 0.0
        else:
            step_errors = []
            for step in future_trace:
                prediction = project_structural_observation(
                    record["post_graph"], step["pose_bucket"]
                )
                target = frozenset(step["structural_observation"])
                step_errors.append(float(len(prediction ^ target)))
            future = float(np.mean(step_errors))
        current_refs = set(program.get("evidence_refs", []))
        now = 0.0 if current_refs else 1.0
        terms = {
            "now": now,
            "future": future,
            "edit": float(program.get("declared_edit_cost", 0.0)),
            "growth": float(program.get("declared_growth_cost", 0.0)),
            "collateral": 0.0,
            "illegal": illegal,
        }
        total = (
            sum(weights[key] * terms[key] for key in weights)
            if not illegal else None
        )
        energies.append({**terms, "total": total, "masked": bool(illegal)})
    return energies, _teacher_posterior(energies, temperature), future_trace


def _contains_forbidden_online_key(value: Any, path: str = "") -> list[str]:
    violations = []
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower().replace("-", "_")
            current = f"{path}.{key}" if path else str(key)
            if any(token in lowered for token in ONLINE_DENY_SUBSTRINGS):
                violations.append(current)
            violations.extend(_contains_forbidden_online_key(item, current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_contains_forbidden_online_key(item, f"{path}[{index}]"))
    return violations


def validate_online_payload(online: Mapping[str, Any]) -> None:
    violations = _contains_forbidden_online_key(online)
    if violations:
        raise ValueError(f"online payload contains audit-only fields: {violations}")


def _online_record(
    materialized: Mapping[str, Any], family: str, split: str, world_seed: int,
    asset_family: str, cue_name: str, cue_value: float, cue_reliability: float,
    region_signature: list[float],
) -> dict[str, Any]:
    case = materialized["case"]
    online = {
        "schema_version": "cpmt-m1-online-v1",
        "case_family": family,
        "paired_group_id": f"pair:{materialized['namespace']}",
        "world_seed": world_seed,
        "asset_family": asset_family,
        "split": split,
        "decision_time": int(case["decision_time"]),
        "prior_world": materialized["world"],
        "current_regions": [{
            "region_ref": reference,
            "anonymous_signature": region_signature,
        } for reference in case["current_observation_refs"]],
        "history_cues": {
            "cue_name": cue_name,
            "value": cue_value,
            "reliability": cue_reliability,
        },
        "pose_history": [{"time_index": int(case["decision_time"]), "valid": True}],
        "action_history": ["controlled_revisit"],
        "candidate_programs": materialized["programs"],
    }
    validate_online_payload(online)
    return online


def generate_m1_split(
    config: Mapping[str, Any], split: str, *, groups_per_family: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Generate only train/validation records; formal test stays sealed."""
    validate_m1_protocol(config)
    if split not in SPLIT_SEED_OFFSET:
        raise ValueError("M1 generator only exposes train/validation; test is sealed")
    count = (
        int(groups_per_family) if groups_per_family is not None
        else int(config["data"]["groups_per_family"][split])
    )
    if count <= 0:
        raise ValueError("groups_per_family must be positive")
    raw_by_family = {
        family: _load_archetype(family)
        for family in config["data"]["scenario_families"]
    }
    online_records: list[dict[str, Any]] = []
    audit_records: list[dict[str, Any]] = []
    family_counts = {family: 0 for family in raw_by_family}
    labelled_groups = 0
    ambiguous_groups = 0
    base_seed = 260_906 + SPLIT_SEED_OFFSET[split]
    label_fraction = float(config["training"]["main_label_fraction"])
    weights = config["energy"]["weights"]
    temperature = float(config["energy"]["temperature"])

    for family_index, (family, raw) in enumerate(raw_by_family.items()):
        primary, contrast, cue_name = FAMILY_RULES[family]
        buckets = list(ASSET_BUCKETS[split])
        for group_index in range(count):
            world_seed = base_seed + family_index * 1_000_000 + group_index
            rng = np.random.default_rng(world_seed)
            materialized = _materialize_archetype(raw, family, split, group_index)
            executions = _execute_candidates(materialized)
            reference_indices = (
                _choose_candidate(executions, primary),
                _choose_candidate(executions, contrast),
            )
            ambiguous = group_index % 4 == 0
            labelled = split == "train" and bool(rng.random() < label_fraction)
            ambiguous_groups += int(ambiguous)
            labelled_groups += int(labelled)
            asset_family = f"{family}-asset-{buckets[group_index % len(buckets)]:02d}"
            region_signature = rng.normal(0.0, 1.0, 8).round(6).tolist()
            future_schedule = []
            for step in range(1, int(config["future"]["primary_horizon"]) + 1):
                future_schedule.append({
                    "step": step,
                    "pose_bucket": int(rng.integers(0, 8)),
                })
            sibling_online = []
            for sibling_index, reference_index in enumerate(reference_indices):
                cue_value = 0.5 if ambiguous else float(1 - sibling_index)
                cue_reliability = 0.0 if ambiguous else 1.0
                online = _online_record(
                    materialized, family, split, world_seed, asset_family,
                    cue_name, cue_value, cue_reliability, region_signature,
                )
                sibling_online.append(online)
                energies, posterior, future_trace = _candidate_energies(
                    executions, reference_index, materialized["programs"],
                    weights, temperature, future_schedule,
                )
                winner = int(np.argmax(posterior))
                reference_execution = executions[reference_index]
                audit_records.append({
                    "schema_version": "cpmt-m1-audit-v1",
                    "case_id": f"case:{materialized['namespace']}:s{sibling_index}",
                    "case_family": family,
                    "paired_group_id": online["paired_group_id"],
                    "world_seed": world_seed,
                    "asset_family": asset_family,
                    "split": split,
                    "ambiguity": "epistemically_ambiguous" if ambiguous else "identifiable",
                    "online": online,
                    "reference_program_index": reference_index,
                    "reference_transaction_id": reference_execution["transaction_id"],
                    "reference_template": reference_execution["template"],
                    "reference_post_graph_hash": reference_execution["post_graph_hash"],
                    "transaction_label_available": labelled,
                    "executed_candidates": executions,
                    "candidate_energies": energies,
                    "teacher_posterior": posterior,
                    "teacher_winner_index": winner,
                    "candidate_coverage_at_k": 1.0,
                    "future_trace": future_trace,
                })
                online_records.append(online)
                family_counts[family] += 1
                if winner != reference_index:
                    raise AssertionError(
                        f"teacher misranks generated reference in {family} group {group_index}"
                    )
            if ambiguous:
                if canonical_json(sibling_online[0]) != canonical_json(sibling_online[1]):
                    raise AssertionError("ambiguous siblings must have identical online input")
            else:
                left = deepcopy(sibling_online[0])
                right = deepcopy(sibling_online[1])
                left.pop("history_cues")
                right.pop("history_cues")
                if canonical_json(left) != canonical_json(right):
                    raise AssertionError(
                        "identifiable siblings may differ only in lawful history cues"
                    )

    summary = {
        "status": "generator_interface_validation_only",
        "dataset_version": config["data"]["dataset_version"],
        "split": split,
        "groups_per_family": count,
        "paired_groups": count * len(raw_by_family),
        "cases": len(audit_records),
        "family_case_counts": family_counts,
        "ambiguous_groups": ambiguous_groups,
        "ambiguous_group_fraction": ambiguous_groups / (count * len(raw_by_family)),
        "labelled_groups": labelled_groups,
        "labelled_group_fraction": labelled_groups / (count * len(raw_by_family)),
        "test_generated": False,
        "formal_data_ready": False,
        "source_fixture_status": "human_draft_semantic_archetypes",
        "variation_scope": (
            "fresh IDs, asset signatures, history cues, poses, and visibility; "
            "world topology remains at archetype level"
        ),
        "candidate_budget_k": config["candidates"]["budget_k"],
        "candidate_coverage": float(np.mean([
            record["candidate_coverage_at_k"] for record in audit_records
        ])),
        "candidate_coverage_note": (
            "reference programs are injected by this interface generator; "
            "coverage is not the frozen formal gate result"
        ),
    }
    return online_records, audit_records, summary


def records_sha256(records: Iterable[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(canonical_json(record).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
