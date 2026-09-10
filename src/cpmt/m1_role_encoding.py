"""Opt-in role encoding prototype; method validity has not been established.

The legacy candidate block and world context are retained verbatim. Five role
groups append similarities against the existing node/edge/place queries only.
See HARD_CONDITION_EXPERIMENT.md, D-056 prototype contract, for Chinese semantics.
"""
from __future__ import annotations

from copy import deepcopy
from functools import partial
from typing import Any, Mapping

import numpy as np

from .m1_af_rollout import (
    CANDIDATE_FEATURE_DIM, ONLINE_CONTEXT_DIM, QUERY_KINDS,
    causal_rollout_metrics, online_feature_vector,
    rollout_learning_arrays_from_audits,
)
from .m1_rollout import (
    ARGUMENT_ID_KEYS, CANDIDATE_BUDGET, PROPOSAL_FEATURE_DIM,
    candidate_argument_ids, stable_retrieval_feature,
)

ENCODINGS = ('pooled_v1', 'pooled_padded_v1', 'argument_roles_v1')
ROLES = ('edge_argument', 'node_argument', 'edge_source', 'edge_target', 'node_record')
ROLE_BLOCK_DIM = len(QUERY_KINDS) * 2 + 1
ROLE_FEATURE_DIM = len(ROLES) * ROLE_BLOCK_DIM
EXPANDED_CANDIDATE_DIM = CANDIDATE_FEATURE_DIM + ROLE_FEATURE_DIM


def candidate_dim(encoding: str) -> int:
    if encoding not in ENCODINGS:
        raise ValueError(f'unknown role prototype encoding {encoding!r}')
    return CANDIDATE_FEATURE_DIM if encoding == 'pooled_v1' else EXPANDED_CANDIDATE_DIM


def argument_role_ids(program: Mapping[str, Any]) -> dict[str, list[str]]:
    """Group exactly the original identifier set, without parsing identity names."""
    roles: dict[str, set[str]] = {role: set() for role in ROLES}
    for operation in program['operations']:
        args = operation['arguments']
        for key in ARGUMENT_ID_KEYS:
            value = args.get(key)
            if isinstance(value, str):
                role = 'edge_argument' if key == 'edge_id' else 'node_argument'
                roles[role].add(value.split('@')[0])
        edge = args.get('edge')
        if isinstance(edge, Mapping):
            for key in ('source', 'target'):
                roles[f'edge_{key}'].add(str(edge[key]))
        node = args.get('node')
        if isinstance(node, Mapping):
            roles['node_record'].add(str(node['node_id']))
    if set().union(*roles.values()) != set(candidate_argument_ids(program)):
        raise ValueError('role encoder changed the legacy identifier set')
    return {role: sorted(values) for role, values in roles.items()}


def role_features(program: Mapping[str, Any], observation: Mapping[str, Any]) -> np.ndarray:
    queries = {key: np.asarray(observation[key], dtype=np.float64) for key in QUERY_KINDS}
    if any(q.shape != (PROPOSAL_FEATURE_DIM,) or not np.isfinite(q).all() for q in queries.values()):
        raise ValueError('invalid existing proposal query')
    values = []
    for identifiers in argument_role_ids(program).values():
        if not identifiers:
            values.extend([0.0] * ROLE_BLOCK_DIM)
            continue
        vectors = np.asarray([stable_retrieval_feature(value) for value in identifiers])
        for query in queries.values():
            matches = vectors @ query
            values.extend([float(matches.max()), float(matches.mean())])
        values.append(len(identifiers) / 6.0)
    return np.asarray(values, dtype=np.float32)


def encode_online(online: Mapping[str, Any], *, encoding: str) -> np.ndarray:
    width = candidate_dim(encoding)
    legacy = online_feature_vector(online)
    if encoding == 'pooled_v1':
        return legacy
    blocks = legacy[ONLINE_CONTEXT_DIM:].reshape(CANDIDATE_BUDGET, CANDIDATE_FEATURE_DIM)
    extra = np.zeros((CANDIDATE_BUDGET, ROLE_FEATURE_DIM), dtype=np.float32)
    if encoding == 'argument_roles_v1':
        extra = np.stack([role_features(p, online['proposal_observation']) for p in online['candidate_programs']])
    result = np.concatenate((legacy[:ONLINE_CONTEXT_DIM], np.concatenate((blocks, extra), axis=1).ravel()))
    if result.shape != (ONLINE_CONTEXT_DIM + CANDIDATE_BUDGET * width,) or not np.isfinite(result).all():
        raise ValueError('role prototype feature layout mismatch')
    return result


def configure(config: Mapping[str, Any], *, encoding: str) -> dict[str, Any]:
    """Bind model dimensions explicitly; never reinterpret old checkpoints."""
    width = candidate_dim(encoding)
    if config.get('formal_run') is not False or config.get('test_access') is not False:
        raise ValueError('role prototype requires nonformal, test-sealed config')
    result = deepcopy(dict(config))
    result.update(online_encoding=encoding, candidate_feature_dim=width,
                  online_feature_dim=ONLINE_CONTEXT_DIM + CANDIDATE_BUDGET * width)
    return result


def learning_arrays(hard_config, audits, config):
    """Use the registered target builder; only its online encoding is replaced."""
    encoding = config['online_encoding']
    _check_config(config, encoding)
    _check_audits(audits)
    return rollout_learning_arrays_from_audits(
        hard_config, audits, future_hash_bins=int(config['future_hash_bins']),
        feature_encoder=partial(encode_online, encoding=encoding),
    )


def _check_config(config, encoding):
    expected = configure(config, encoding=encoding)
    for key in ('candidate_feature_dim', 'online_feature_dim'):
        if config.get(key) != expected[key]:
            raise ValueError(f'role prototype config mismatch: {key}')


def _check_audits(audits):
    if not audits or any(audit.get('split') != 'train' for audit in audits):
        raise ValueError('role prototype stage requires nonempty train-only audits')


def rollout_metrics(model, audits, config, *, audit_sink=None):
    """Encode each freshly materialized own-state input through the same adapter."""
    encoding = config['online_encoding']
    _check_config(config, encoding)
    _check_audits(audits)
    if getattr(model, 'candidate_dim', None) != candidate_dim(encoding):
        raise ValueError('model candidate width does not match encoding')
    if getattr(model, 'context_dim', None) != ONLINE_CONTEXT_DIM:
        raise ValueError('model context width does not match encoding')
    return causal_rollout_metrics(
        model, audits, config, audit_sink=audit_sink,
        feature_encoder=partial(encode_online, encoding=encoding),
    )
