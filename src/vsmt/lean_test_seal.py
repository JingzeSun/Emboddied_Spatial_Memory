"""Ruling 103-1: the S3 test data are generated in S3-02 and sealed until S3-05.

Ruling 103-1 generates the raw test episodes, the geometry reload and both caches together with train/validation, but
into separate sealed roots: the S3-03/S3-04 entries refuse the test roots, and S3-05 verifies the seal before it reads
them, once. This module provides:
  * markers: a ``TEST_SEALED.json`` in every test root, ``pending`` (no digest yet) while S3-02 writes it; once all
    four roots are complete, S3-02 computes the seal and replaces each marker by a ``sealed`` one carrying the seal
    digest;
  * the guard: ``refuse_sealed(paths, reader=...)`` refuses when the marker is in a given path itself, in any directory
    above it, or (ruling 104-6) in any directory directly below it; data-reading entries call it before loading
    anything, so a test root passed by mistake to a training, selection or audit entry stops before the first frame,
    and so does the parent directory of the three split roots;
  * the seal: a tree digest per episode (sha256 over the sorted relative path, byte count and sha256 of every file) for
    each of the four root kinds (raw episodes, geometry reload, instance-segmentation cache, SAM 2.1 cache), together
    with the digests of each root's top-level files (its stage receipts), written to one seal file; S3-05 recomputes
    and compares it item by item with ``verify_seal``.
Inputs are the four test root paths and the test manifest; outputs are markers, the seal and verification results.
Example: the SAM 2.1 cache test root passed to the node-audit entry makes it print the blocking marker path and exit
with code 2. The module only computes byte digests: it reads no frame content and deletes or moves no file.

Opening (ruling 107-1, 2026-10-05): ``open_roots`` changes the four markers to ``opened`` (keeping the seal digest and
recording which S3-04 freeze receipt authorised it) only after ``verify_seal`` reports no difference, and writes the
read record ``TEST_READ.json`` into each test root (reading 1, time, commit, receipt digest; a resume after an
engineering failure is the same reading and does not increment it); ``record_copy`` adds the verification of a copy on
a remote host to the same record. ``refuse_sealed`` refuses all three states, so the S3-03/S3-04 entries still cannot
read test; only an S3-05 entry calling ``admit_opened`` with the same receipt digest can.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "vsmt-lean-s3-test-seal-v1"
MARKER_NAME = "TEST_SEALED.json"
#: the four kinds of test root ruling 103-1 seals, in a fixed order
SEAL_KINDS = ("raw", "geometry", "instance_cache", "sam2_cache")
STATE_PENDING = "pending"
STATE_SEALED = "sealed"
#: ruling 107-1: S3-05 verified the seal and opened the root for the run its freeze receipt names
STATE_OPENED = "opened"
#: ruling 107-1: the read record in each opened test root, beside the marker (outside the seal: it did not exist when the
#: seal was taken)
READ_RECORD_NAME = "TEST_READ.json"
RULE = ("ruling 103-1: the test data are generated in S3-02 into their own roots and sealed; the S3-03 and S3-04 entries refuse "
        "them; S3-05 verifies the seal, then reads them once")
#: a seal field that changes between two identical seals and is therefore left out of the seal digest
VOLATILE_SEAL_FIELDS = ("sealed_utc",)


class LeanTestSealError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanTestSealError(code)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_digest(directory: Path) -> dict[str, Any]:
    """Files, bytes and one sha256 over every file under ``directory`` (relative path, size and file sha256, sorted by path)."""

    directory = Path(directory)
    _require(directory.is_dir(), f"not_a_directory:{directory}")
    rows, total = [], 0
    for path in sorted((p for p in directory.rglob("*") if p.is_file()), key=lambda p: p.relative_to(directory).as_posix()):
        size = path.stat().st_size
        total += size
        rows.append(f"{path.relative_to(directory).as_posix()}\t{size}\t{file_sha256(path)}")
    return {"files": len(rows), "bytes": total, "sha256": hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def seal_sha256(seal: Mapping[str, Any]) -> str:
    """The digest a marker and S3-05 refer to: every field of the seal but the time it was written."""

    return hashlib.sha256(_canonical({k: v for k, v in seal.items() if k not in VOLATILE_SEAL_FIELDS}).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# markers and the reader guard
# --------------------------------------------------------------------------

def write_marker(root: Path, *, kind: str, state: str, seal_digest: str | None = None) -> Path:
    """Put the marker into one test root: ``pending`` while S3-02 writes it, ``sealed`` with the seal digest afterwards."""

    _require(kind in SEAL_KINDS, f"unknown_kind:{kind}")
    _require(state in (STATE_PENDING, STATE_SEALED), f"unknown_state:{state}")  # opened only through open_roots
    _require((state == STATE_SEALED) == (seal_digest is not None), "sealed_marker_needs_the_seal_digest")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / MARKER_NAME
    payload = {"schema_version": SCHEMA_VERSION, "kind": kind, "state": state, "seal_sha256": seal_digest, "rule": RULE}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def sealed_marker(path: str | Path) -> Path | None:
    """The marker that covers ``path``, or None: in the path itself, in any directory above it, or (ruling 104-6) in a directory
    directly below it -- a root one level above a test root, such as the parent of the three split roots, holds test data too."""

    resolved = Path(path).resolve()
    for candidate in (resolved, *resolved.parents):
        marker = candidate / MARKER_NAME
        if marker.is_file():
            return marker
    if resolved.is_dir():
        for child in sorted(resolved.iterdir()):
            marker = child / MARKER_NAME
            if marker.is_file():
                return marker
    return None


def refuse_sealed(paths: Iterable[str | Path | None], *, reader: str) -> None:
    """Raise if any given path is covered by a test-root marker (``sealed_marker``) in any state: pending, sealed or
    (ruling 107-1) opened; a data-reading entry calls this before loading anything."""

    for path in paths:
        if path is None or str(path) == "":
            continue
        marker = sealed_marker(path)
        if marker is not None:
            raise LeanTestSealError(f"sealed_test_root:{reader}:{path} is covered by {marker} ({RULE})")


def refusal(paths: Iterable[str | Path | None], *, reader: str) -> str | None:
    """``refuse_sealed`` for an entry that reports refusals itself: the message, or None when no path is sealed."""

    try:
        refuse_sealed(paths, reader=reader)
    except LeanTestSealError as exc:
        return str(exc)
    return None


# --------------------------------------------------------------------------
# the seal
# --------------------------------------------------------------------------

def _root_files(root: Path) -> dict[str, dict[str, Any]]:
    return {p.name: {"bytes": p.stat().st_size, "sha256": file_sha256(p)}
            for p in sorted(root.iterdir())
            if p.is_file() and p.name not in (MARKER_NAME, READ_RECORD_NAME) and not p.name.endswith(".tmp")}


def _succeeded(root: Path) -> list[str]:
    out = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        receipt = directory / "receipt.json"
        if receipt.is_file() and json.loads(receipt.read_text(encoding="utf-8")).get("status") == "succeeded":
            out.append(directory.name)
    return out


def build_seal(roots: Mapping[str, str | Path], *, houses: Sequence[str], tag: str) -> dict[str, Any]:
    """The seal of the four test roots: per episode a tree digest, per root the digests of its top-level files.

    ``houses`` is the committed test manifest; every listed house must have a raw episode directory (attempted, succeeded or failed)
    and no other directory may sit in the raw root.
    """

    _require(tuple(sorted(roots)) == tuple(sorted(SEAL_KINDS)), "seal_needs_exactly_the_four_roots")
    raw = Path(roots["raw"])
    attempted = sorted(p.name for p in raw.iterdir() if p.is_dir())
    _require(attempted == sorted(houses), "raw_test_root_does_not_hold_exactly_the_manifest")
    kinds: dict[str, Any] = {}
    for kind in SEAL_KINDS:
        root = Path(roots[kind])
        _require(root.is_dir(), f"test_root_missing:{kind}")
        kinds[kind] = {"root": str(root),
                       "episodes": {d.name: tree_digest(d) for d in sorted(p for p in root.iterdir() if p.is_dir())},
                       "succeeded": _succeeded(root), "root_files": _root_files(root)}
    return {"schema_version": SCHEMA_VERSION, "rule": RULE, "tag": tag, "houses": list(houses),
            "houses_sha256": hashlib.sha256(json.dumps(list(houses)).encode("utf-8")).hexdigest(),
            "kinds": kinds, "counts": {kind: {"episodes": len(kinds[kind]["episodes"]), "succeeded": len(kinds[kind]["succeeded"])}
                                       for kind in SEAL_KINDS},
            "sealed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def verify_seal(seal: Mapping[str, Any], roots: Mapping[str, str | Path] | None = None, *,
                opened_by: str | None = None) -> list[str]:
    """Recompute every digest of a seal (at its own roots, or at ``roots``) and list each difference; empty means intact.

    With ``opened_by`` (a freeze receipt digest, ruling 107-1) a marker opened for that receipt counts as this seal's too."""

    problems: list[str] = []
    if seal.get("schema_version") != SCHEMA_VERSION:
        return [f"seal_schema_version:{seal.get('schema_version')}"]
    for kind in SEAL_KINDS:
        entry = seal["kinds"][kind]
        root = Path((roots or {}).get(kind) or entry["root"])
        if not root.is_dir():
            problems.append(f"root_missing:{kind}")
            continue
        present = sorted(p.name for p in root.iterdir() if p.is_dir())
        if present != sorted(entry["episodes"]):
            problems.append(f"episode_set_differs:{kind}")
        for episode, digest in sorted(entry["episodes"].items()):
            if (root / episode).is_dir() and tree_digest(root / episode) != digest:
                problems.append(f"episode_digest_differs:{kind}:{episode}")
        if _root_files(root) != entry["root_files"]:
            problems.append(f"root_files_differ:{kind}")
        marker = root / MARKER_NAME
        if not marker.is_file():
            problems.append(f"marker_missing:{kind}")
        else:
            state = json.loads(marker.read_text(encoding="utf-8"))
            accepted = state.get("state") == STATE_SEALED or (
                opened_by is not None and state.get("state") == STATE_OPENED and state.get("opened_by") == opened_by)
            if not accepted or state.get("seal_sha256") != seal_sha256(seal):
                problems.append(f"marker_not_this_seal:{kind}")
    return problems


def seal_roots(roots: Mapping[str, str | Path], *, houses: Sequence[str], tag: str) -> tuple[dict[str, Any], str]:
    """Build the seal and turn every pending marker into the sealed one; returns the seal and its digest."""

    seal = build_seal(roots, houses=houses, tag=tag)
    digest = seal_sha256(seal)
    for kind in SEAL_KINDS:
        write_marker(Path(roots[kind]), kind=kind, state=STATE_SEALED, seal_digest=digest)
    return seal, digest


# --------------------------------------------------------------------------
# opening the seal for S3-05 (ruling 107-1)
# --------------------------------------------------------------------------

def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def open_roots(seal: Mapping[str, Any], *, receipt_sha256: str, commit: str, purpose: str) -> dict[str, Any]:
    """Ruling 107-1: verify the seal, then open the four test roots for the S3-05 run of one freeze receipt.

    The first call verifies every digest and opens the roots as reading 1; a later call for the same receipt (a resume after an
    engineering failure) only re-verifies and returns the same reading; a call for another receipt is refused (test is read once).
    """

    _require(bool(receipt_sha256), "open_needs_the_freeze_receipt_digest")
    digest = seal_sha256(seal)
    markers = {kind: Path(seal["kinds"][kind]["root"]) / MARKER_NAME for kind in SEAL_KINDS}
    states = {kind: json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {} for kind, path in markers.items()}
    opened = [kind for kind, state in states.items() if state.get("state") == STATE_OPENED]
    if opened:
        others = sorted({states[kind].get("opened_by") for kind in opened} - {receipt_sha256})
        _require(not others, f"test_already_opened_for_another_receipt:{others}")
    problems = verify_seal(seal, opened_by=receipt_sha256)
    _require(not problems, f"seal_not_intact:{problems[:5]}")
    if len(opened) == len(SEAL_KINDS):  # the same reading: nothing is written
        record = json.loads((Path(seal["kinds"]["raw"]["root"]) / READ_RECORD_NAME).read_text(encoding="utf-8"))
        return {**record, "resumed": True}
    record = {"schema_version": SCHEMA_VERSION, "rule": "ruling 107-1: test is read once, by the S3-05 run of one freeze receipt",
              "reading": 1, "opened_utc": _utc(), "commit": commit, "receipt_sha256": receipt_sha256, "seal_sha256": digest,
              "purpose": purpose, "copies": []}
    for kind in SEAL_KINDS:
        root = Path(seal["kinds"][kind]["root"])
        _write(root / READ_RECORD_NAME, {**record, "kind": kind})
        _write(markers[kind], {"schema_version": SCHEMA_VERSION, "kind": kind, "state": STATE_OPENED, "seal_sha256": digest,
                               "opened_by": receipt_sha256, "opened_utc": record["opened_utc"], "rule": RULE})
    return {**record, "resumed": False}


def admit_opened(paths: Iterable[str | Path | None], *, reader: str, receipt_sha256: str) -> None:
    """S3-05's reader guard: every given path covered by a test marker must be opened for this freeze receipt."""

    for path in paths:
        if path is None or str(path) == "":
            continue
        marker = sealed_marker(path)
        if marker is None:
            continue
        state = json.loads(marker.read_text(encoding="utf-8"))
        if state.get("state") != STATE_OPENED or state.get("opened_by") != receipt_sha256:
            raise LeanTestSealError(f"test_root_not_opened_for_this_receipt:{reader}:{path} ({marker}: {state.get('state')})")


def refusal_unless_opened(paths: Iterable[str | Path | None], *, reader: str, receipt_sha256: str) -> str | None:
    """``admit_opened`` for an entry that reports refusals itself."""

    try:
        admit_opened(paths, reader=reader, receipt_sha256=receipt_sha256)
    except LeanTestSealError as exc:
        return str(exc)
    return None


def record_copy(seal: Mapping[str, Any], *, host: str, problems: Sequence[str]) -> dict[str, Any]:
    """Ruling 107-1 / 107-3: one copy of the opened test roots to a remote host, and its check there, into every read record."""

    entry = {"host": host, "checked_utc": _utc(), "verified": not problems, "problems": list(problems)[:10]}
    for kind in SEAL_KINDS:
        path = Path(seal["kinds"][kind]["root"]) / READ_RECORD_NAME
        record = json.loads(path.read_text(encoding="utf-8"))
        record.setdefault("copies", []).append(entry)
        _write(path, record)
    return entry


__all__ = [
    "LeanTestSealError",
    "READ_RECORD_NAME",
    "STATE_OPENED",
    "admit_opened",
    "open_roots",
    "record_copy",
    "refusal_unless_opened",
    "MARKER_NAME",
    "RULE",
    "SCHEMA_VERSION",
    "SEAL_KINDS",
    "STATE_PENDING",
    "STATE_SEALED",
    "build_seal",
    "file_sha256",
    "refusal",
    "refuse_sealed",
    "seal_roots",
    "seal_sha256",
    "sealed_marker",
    "tree_digest",
    "verify_seal",
    "write_marker",
]
