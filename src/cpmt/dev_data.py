"""Small spatial-memory development data; not a visual benchmark.

Online features contain only observations through t=2. The separate audit
record retains simulator truth, later observations, and executable branches.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

import numpy as np

from .errors import CPMTError
from .executor import execute_transaction
from .hashing import canonical_json, seal_graph

TEMPLATES = ("BIND", "BIRTH", "RELINK")
ONLINE_KEYS = {"base_features", "history", "history_mask", "current_region",
               "observed_position", "decision_time"}


def node(identity: str, kind: str, latent: str, *, at: int = 0,
         lifecycle: str = "confirmed", provenance: str = "sim:init") -> dict:
    return dict(node_id=identity, node_version_id=identity + "@0", node_type=kind,
                lifecycle=lifecycle, valid_from=at, valid_to=None,
                evidence_refs=["obs:initial"] if at == 0 else ["obs:current"],
                latent_refs=[latent], canonical_id=None, predecessor_ids=[],
                provenance=[provenance])


def edge(identity: str, subject: str, position: int, *, at: int = 0,
         provenance: str = "sim:init") -> dict:
    return dict(edge_id=identity, edge_version_id=f"{identity}@{at}",
                source=subject, target=f"place-{position}", relation="located_at",
                frame="world", valid_from=at, valid_to=None,
                evidence_refs=["obs:initial"] if at == 0 else ["obs:current"],
                provenance=[provenance])


def make_world(old_position: int) -> dict:
    nodes = [node("old", "entity", "latent:object"),
             node("protected", "entity", "latent:protected")]
    nodes += [node(f"place-{i}", "place", f"latent:place-{i}") for i in range(3)]
    return seal_graph(dict(schema_version="cpmt-0.2", graph_id="sim-world",
                           graph_version="v0", parent_version=None, nodes=nodes,
                           edges=[edge("old-location", "old", old_position),
                                  edge("protected-location", "protected", 2)],
                           transaction_log=[]))


def make_programs(base: dict, position: int) -> list[dict]:
    """Generate the same three legal alternatives without access to truth."""
    programs = []
    for template in TEMPLATES:
        tx = "tx:" + template
        program = dict(schema_version="cpmt-0.2", transaction_id=tx,
                       intent={"BIND": "ASSOCIATE", "BIRTH": "EXPAND",
                               "RELINK": "REVISE"}[template],
                       template=template, base_graph_version=base["graph_version"],
                       operations=[], evidence_refs=["obs:current"],
                       protected_ids=["protected", "protected-location"],
                       proposer="deterministic_development")
        def op(kind: str, **arguments: Any) -> None:
            program["operations"].append(dict(
                op_id=f"op-{len(program['operations'])}", op_type=kind,
                arguments=arguments))
        if template == "BIND":
            op("ATTACH_EVIDENCE", target_kind="node", target_id="old",
               evidence_ref="obs:current")
            op("RECORD_PROVENANCE", target_kind="node", target_id="old",
               provenance_ref=tx)
        elif template == "BIRTH":
            op("CREATE_NODE", node=node("new", "entity", "latent:object", at=2,
                                       lifecycle="candidate", provenance=tx))
            op("ADD_EDGE", edge=edge("new-location", "new", position, at=2,
                                    provenance=tx))
        else:
            op("CLOSE_EDGE_VERSION", edge_id="old-location", at=2)
            op("RECORD_PROVENANCE", target_kind="edge",
               edge_version_id="old-location@0", provenance_ref=tx)
            op("ADD_EDGE", edge=edge("old-location", "old", position, at=2,
                                    provenance=tx))
        programs.append(program)
    return programs


def graph_objects(graph: dict) -> dict[str, int]:
    return {e["source"]: int(e["target"].split("-")[-1])
            for e in graph["edges"]
            if e["valid_to"] is None and e["relation"] == "located_at"}


def render(objects: dict[str, int], asset: np.ndarray,
           distractor: np.ndarray, flip: int = 0) -> np.ndarray:
    """Analytic three-place observation: object count plus summed appearance.

    This fixed camera permutation is a toy projector, not Projective Node Orbit.
    """
    values = np.zeros((3, len(asset) + 1), dtype=np.float32)
    for identity, position in objects.items():
        values[position, 0] += 1.0
        values[position, 1:] += distractor if identity == "protected" else asset
    if flip:
        values = values[[1, 0, 2]]
    return values


def online_vector(online: dict) -> np.ndarray:
    """Allowlist boundary; never accepts a complete case or hidden truth."""
    if set(online) != ONLINE_KEYS or online["decision_time"] != 2:
        raise ValueError("online input must contain only the declared t<=2 fields")
    return np.concatenate([
        np.asarray(online[key], dtype=np.float32).reshape(-1)
        for key in ("base_features", "history", "history_mask", "current_region",
                    "observed_position")
    ])


def candidate_energy(base: dict, post: dict, online: dict, future: np.ndarray,
                     poses: np.ndarray, asset: np.ndarray, distractor: np.ndarray,
                     program: dict, weights: dict) -> tuple[dict, np.ndarray]:
    prediction = np.stack([render(graph_objects(post), asset, distractor, int(p))
                           for p in poses])
    position = int(np.argmax(online["observed_position"]))
    now = float(position not in graph_objects(post).values())
    future_error = float(np.mean((prediction - future) ** 2))
    growth = float(len(post["nodes"]) - len(base["nodes"]))
    edit = float(sum(o["op_type"] not in {"ASSERT_PRECONDITION", "RECORD_PROVENANCE"}
                     for o in program["operations"]))
    collateral = float(graph_objects(post).get("protected") != 2)
    components = dict(now=now, future=future_error, edit=edit, growth=growth,
                      collateral=collateral, illegal=0.0)
    components["total"] = sum(weights[k] * components[k] for k in weights)
    return components, prediction


def hindsight_posterior(energies: np.ndarray, temperature: float) -> np.ndarray:
    if temperature <= 0 or not np.isfinite(energies).any():
        raise ValueError("positive temperature and at least one legal candidate required")
    logits = -(energies - np.min(energies)) / temperature
    probs = np.exp(logits)
    return (probs / probs.sum()).astype(np.float32)


def generate_split(config: dict, split: str) -> tuple[dict[str, np.ndarray], list[dict]]:
    if split not in {"train", "validation"} or config["test_access"]:
        raise ValueError("development runner has no test split")
    groups = config[f"{split}_groups"]
    rows: list[dict] = []
    audits = []
    for group in range(groups):
        # Disjoint seeds, assets and full sibling groups across splits.
        seed = config["data_seed"] + group + (0 if split == "train" else 1_000_000)
        rng = np.random.default_rng(seed)
        asset = rng.uniform(0.2, 1.0, config["latent_dim"]).astype(np.float32)
        distractor = rng.uniform(-1.0, -0.2, config["latent_dim"]).astype(np.float32)
        old_position = int(rng.integers(2))
        ambiguous = bool(rng.random() < config["ambiguous_fraction"])
        labelled = bool(split == "train" and rng.random() < config["label_fraction"])
        base = make_world(old_position)
        base_before = deepcopy(base)
        past = render({"old": old_position, "protected": 2}, asset, distractor)
        history_noise = rng.normal(0, config["observation_noise"], past.shape).astype(np.float32)
        region = asset + rng.normal(0, config["observation_noise"], asset.shape)
        future_noise = rng.normal(0, config["observation_noise"],
                                 (config["horizon"], *past.shape)).astype(np.float32)
        poses = rng.integers(0, 2, config["horizon"])
        labelled_group = f"{split}:{seed}"
        for target, template in enumerate(TEMPLATES):
            observed = old_position if template == "BIND" else 1 - old_position
            # Independent simulator facts; never derived from executor output.
            truth = {"old": old_position, "protected": 2}
            if template == "BIRTH":
                truth["new"] = observed
            elif template == "RELINK":
                truth["old"] = observed
            mask = np.zeros_like(past)
            mask[2] = 1
            if not ambiguous:
                mask[old_position] = 1
            history = (render(truth, asset, distractor) + history_noise) * mask
            online = dict(base_features=past.tolist(), history=history.tolist(),
                          history_mask=mask.tolist(), current_region=region.tolist(),
                          observed_position=np.eye(3)[observed].tolist(),
                          decision_time=2)
            future = np.stack([render(truth, asset, distractor, int(p))
                               for p in poses]) + future_noise
            programs = make_programs(base, observed)
            posts, components, predictions, candidate_failures = [], [], [], []
            for program in programs:
                try:
                    post = execute_transaction(base, program)
                    component, prediction = candidate_energy(
                        base, post, online, future, poses, asset, distractor,
                        program, config["energy_weights"])
                    failure = None
                except CPMTError as exc:
                    # Illegal branches stay in the fixed candidate set with an
                    # explicit energy and failure; they are never silently dropped.
                    edit = float(sum(
                        operation["op_type"] not in {
                            "ASSERT_PRECONDITION", "RECORD_PROVENANCE"
                        }
                        for operation in program["operations"]
                    ))
                    growth = float(sum(
                        operation["op_type"] == "CREATE_NODE"
                        for operation in program["operations"]
                    ))
                    component = dict(
                        now=0.0,
                        future=0.0,
                        edit=edit,
                        growth=growth,
                        collateral=0.0,
                        illegal=1.0,
                    )
                    component["total"] = sum(
                        config["energy_weights"][key] * component[key]
                        for key in config["energy_weights"]
                    )
                    post = None
                    prediction = None
                    failure = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                posts.append(post)
                components.append(component)
                predictions.append(prediction)
                candidate_failures.append(failure)
            if base != base_before:
                raise AssertionError("candidate execution mutated shared base")
            energies = np.asarray([c["total"] for c in components])
            posterior = hindsight_posterior(energies, config["temperature"])
            current_only_energies = np.asarray([
                sum(
                    config["energy_weights"][key] * component[key]
                    for key in config["energy_weights"]
                    if key != "future"
                )
                for component in components
            ])
            current_only_posterior = hindsight_posterior(
                current_only_energies, config["temperature"]
            )
            # Physical fact error is a toy metric, not full graph equivalence.
            fact_errors = [
                (
                    sum(
                        graph_objects(post).get(k) != truth.get(k)
                        for k in set(graph_objects(post)) | set(truth)
                    )
                    if post is not None
                    else len(truth) + 1
                )
                for post in posts
            ]
            excess_nodes = [
                max(0, len(graph_objects(post)) - len(truth))
                if post is not None
                else 0
                for post in posts
            ]
            penalties = [
                sum(
                    config["energy_weights"][key] * component[key]
                    for key in config["energy_weights"]
                    if key != "future"
                )
                for component in components
            ]
            rows.append(dict(x=online_vector(online), future=future.reshape(-1),
                             poses=poses.astype(np.float32), y=target,
                             pstar=posterior, pstar_current=current_only_posterior,
                             labelled=labelled,
                             ambiguous=ambiguous and target in (1, 2),
                             group=seed, fact_errors=fact_errors, excess_nodes=excess_nodes,
                             # E gets pre-edit compatibility/costs and the executor
                             # legality mask, not future rollout features.
                             penalties=penalties))
            audits.append(dict(case_id=f"{labelled_group}:{template}",
                               paired_group_id=labelled_group, split=split, online=online,
                               hindsight=dict(future=future.tolist(), future_poses=poses.tolist(),
                                              future_times=list(range(3, 3 + config["horizon"])),
                                              simulator_truth=truth, oracle_template=template,
                                              labelled_for_training=labelled),
                               base=base, programs=programs, post_worlds=posts,
                                candidate_energies=components, teacher_posterior=posterior.tolist(),
                                current_only_teacher_posterior=(
                                    current_only_posterior.tolist()
                                ),
                               candidate_failures=candidate_failures,
                               future_predictions=[
                                   p.tolist() if p is not None else None
                                   for p in predictions
                               ]))
    arrays = {key: np.asarray([row[key] for row in rows]) for key in rows[0]}
    return arrays, audits


def dataset_digest(audits: list[dict]) -> str:
    digest = hashlib.sha256()
    for case in audits:
        digest.update(canonical_json(case).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
