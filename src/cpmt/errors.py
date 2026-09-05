"""Executor failures are explicit so tests can audit rejection causes."""


class CPMTError(Exception):
    """Base class for CPMT contract failures."""


class ContractError(CPMTError):
    """A graph or transaction does not satisfy the M0 contract."""


class VersionMismatchError(CPMTError):
    """The program was proposed for a different immutable base version."""


class DuplicateTransactionError(CPMTError):
    """A transaction identifier has already been committed."""


class PreconditionError(CPMTError):
    """A declared or template-level precondition is false."""


class ProtectedMutationError(CPMTError):
    """A program attempts to mutate protected world state."""


class UnsupportedTemplateError(CPMTError):
    """The current M0 slice has not implemented this template."""


class InvariantViolation(CPMTError):
    """The resulting graph would violate a world invariant."""
