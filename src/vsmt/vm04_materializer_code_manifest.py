"""Seal and verify the complete repository source boundary of VM-04 materialization."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Mapping

from cpmt.hashing import canonical_json, clone_json


SCHEMA = "vsmt-vm04-materializer-code-manifest-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ENTRY_PATHS = (
    "ops/vsmt/vm04_multiview_materializer.py",
    "ops/vsmt/vm04_observation_stage.py",
)
PACKAGE_ROOTS = ("src/cpmt", "src/vsmt")
TOP_KEYS = {
    "schema_version", "reviewed_git_commit", "source_inventory_policy",
    "sources", "manifest_sha256",
}
POLICY = {
    "entry_paths": list(ENTRY_PATHS),
    "package_roots": list(PACKAGE_ROOTS),
    "recursive_suffix": ".py",
    "symlinks_allowed": False,
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_value(value: Any) -> str:
    return _sha_bytes(canonical_json(value).encode("utf-8"))


def _safe_source_path(value: Any) -> str:
    _require(type(value) is str and value != "", "source path must be nonempty")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and
             "." not in path.parts and str(path) == value and "\\" not in value,
             "source path must be a normalized repository-relative POSIX path")
    return value


def _inventory(repository_root: Path) -> list[str]:
    root = repository_root.resolve(strict=True)
    paths = list(ENTRY_PATHS)
    for package_root in PACKAGE_ROOTS:
        directory = root / package_root
        _require(directory.is_dir() and not directory.is_symlink(),
                 f"source root is missing or symlinked: {package_root}")
        paths.extend(
            path.relative_to(root).as_posix()
            for path in directory.rglob("*.py")
            if path.is_file()
        )
    ordered = sorted(set(paths))
    for relative in ordered:
        path = root / relative
        _require(path.is_file() and not path.is_symlink(),
                 f"source file is missing or symlinked: {relative}")
        _require(path.resolve(strict=True).is_relative_to(root),
                 f"source file escapes repository root: {relative}")
    return ordered


def make_vm04_materializer_code_manifest(
    repository_root: Path, *, reviewed_git_commit: str,
) -> dict[str, Any]:
    """Build an unsigned-review candidate from the exact current source bytes."""

    _require(HEX40.fullmatch(reviewed_git_commit) is not None,
             "reviewed_git_commit must be a lowercase 40-character Git commit")
    root = repository_root.resolve(strict=True)
    record: dict[str, Any] = {
        "schema_version": SCHEMA,
        "reviewed_git_commit": reviewed_git_commit,
        "source_inventory_policy": clone_json(POLICY),
        "sources": [
            {"path": relative, "sha256": _sha_bytes((root / relative).read_bytes())}
            for relative in _inventory(root)
        ],
    }
    record["manifest_sha256"] = _sha_value(record)
    return record


def validate_vm04_materializer_code_manifest(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate structure and the self-seal without touching a checkout."""

    _require(type(raw) is dict and set(raw) == TOP_KEYS,
             "materializer code manifest has unexpected fields")
    record = clone_json(raw)
    _require(record["schema_version"] == SCHEMA,
             "wrong materializer code manifest schema")
    _require(type(record["reviewed_git_commit"]) is str and
             HEX40.fullmatch(record["reviewed_git_commit"]) is not None,
             "reviewed_git_commit must be a lowercase 40-character Git commit")
    _require(record["source_inventory_policy"] == POLICY,
             "materializer source inventory policy changed")
    sources = record["sources"]
    _require(type(sources) is list and len(sources) > 0,
             "materializer source inventory must be nonempty")
    paths: list[str] = []
    for row in sources:
        _require(type(row) is dict and set(row) == {"path", "sha256"},
                 "materializer source row has unexpected fields")
        paths.append(_safe_source_path(row["path"]))
        _require(type(row["sha256"]) is str and
                 HEX64.fullmatch(row["sha256"]) is not None,
                 "materializer source digest must be a lowercase SHA-256")
    _require(paths == sorted(set(paths)),
             "materializer source paths must be unique and sorted")
    claimed = record.pop("manifest_sha256")
    _require(type(claimed) is str and HEX64.fullmatch(claimed) is not None,
             "manifest_sha256 must be a lowercase SHA-256")
    _require(claimed == _sha_value(record),
             "materializer code manifest digest mismatch")
    record["manifest_sha256"] = claimed
    return record


def _git(repository_root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    _require(result.returncode == 0,
             "unable to verify materializer sources at reviewed Git commit")
    return result.stdout


def verify_vm04_materializer_code_checkout(
    raw: Mapping[str, Any], *, repository_root: Path,
) -> dict[str, Any]:
    """Require manifest, checkout inventory and reviewed commit bytes to agree."""

    record = validate_vm04_materializer_code_manifest(raw)
    root = repository_root.resolve(strict=True)
    expected_paths = [row["path"] for row in record["sources"]]
    _require(_inventory(root) == expected_paths,
             "materializer checkout source inventory changed")

    commit = record["reviewed_git_commit"]
    commit_paths = _git(root, "ls-tree", "-r", "--name-only", commit).decode(
        "utf-8"
    ).splitlines()
    relevant_commit_paths = sorted(
        path for path in commit_paths
        if path in ENTRY_PATHS or any(
            path.startswith(package_root + "/") and path.endswith(".py")
            for package_root in PACKAGE_ROOTS
        )
    )
    _require(relevant_commit_paths == expected_paths,
             "reviewed Git commit source inventory differs from manifest")

    for row in record["sources"]:
        relative = row["path"]
        actual_sha = _sha_bytes((root / relative).read_bytes())
        _require(actual_sha == row["sha256"],
                 f"materializer checkout source changed: {relative}")
        committed_sha = _sha_bytes(_git(root, "show", f"{commit}:{relative}"))
        _require(committed_sha == row["sha256"],
                 f"materializer reviewed source changed: {relative}")
    return record
