"""CPMT M0 contracts, executor and deterministic commit wrapper."""

from .executor import execute_transaction, validate_graph
from .equivalence import (
    canonicalize_memory_state,
    validate_canonical_memory_state_equality,
    validate_identity_correspondence,
)
from .hashing import compute_graph_hash, seal_graph
from .maintenance import apply_dormancy_maintenance
from .pending import (
    consume_pending,
    create_pending_store,
    decide_commit,
    quarantine_evidence,
    register_relevant_opportunity,
    retrieve_pending,
    validate_commit_decision,
    validate_pending_store,
)

__all__ = [
    "compute_graph_hash",
    "canonicalize_memory_state",
    "apply_dormancy_maintenance",
    "consume_pending",
    "create_pending_store",
    "decide_commit",
    "execute_transaction",
    "quarantine_evidence",
    "register_relevant_opportunity",
    "retrieve_pending",
    "seal_graph",
    "validate_commit_decision",
    "validate_canonical_memory_state_equality",
    "validate_graph",
    "validate_identity_correspondence",
    "validate_pending_store",
]
