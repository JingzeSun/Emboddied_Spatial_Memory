"""Reproducible source fingerprints for generation, training and export runs."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
from typing import Any, Iterable


def _git(project: Path, *args: str) -> str | None:
    try:
        return subprocess.run(
            ("git", *args), cwd=project, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True, timeout=30,
        ).stdout.strip()
    except Exception:
        return None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arrays_sha256(arrays: dict[str, Any]) -> str:
    """Hash named NumPy arrays including name, dtype, shape and raw bytes."""
    import numpy as np
    digest = hashlib.sha256()
    for key in sorted(arrays):
        value = np.asarray(arrays[key])
        digest.update(key.encode("utf-8"))
        digest.update(str(value.dtype).encode("utf-8"))
        digest.update(str(value.shape).encode("utf-8"))
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def source_tree_sha256(
    project: Path, roots: Iterable[str] = ("src", "scripts", "configs"),
) -> str:
    """Hash tracked and untracked source inputs from their working-tree bytes."""
    normalized_roots = tuple(str(root) for root in roots)
    listed = _git(
        project, "ls-files", "--cached", "--others", "--exclude-standard",
        "--", *normalized_roots,
    )
    paths = [] if listed is None else sorted(
        line for line in listed.splitlines() if line.strip()
    )
    if not paths:
        for root in normalized_roots:
            base = project / root
            if base.exists():
                paths.extend(
                    path.relative_to(project).as_posix()
                    for path in base.rglob("*") if path.is_file()
                )
        paths = sorted(set(paths))
    digest = hashlib.sha256()
    for relative in paths:
        path = project / relative
        if not path.is_file():
            continue
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def capture_run_provenance(
    project: Path, *, component: str, entrypoint: Path | None = None,
) -> dict[str, Any]:
    """Capture the exact working tree used by one pipeline stage.

    HEAD alone is insufficient when arrays are generated, models are trained,
    and reports are exported at different times.  HEAD plus the dirty diff and
    working-tree source hash distinguishes those stages without claiming that
    the later export commit generated earlier numbers.
    """
    status = _git(project, "status", "--porcelain")
    diff = _git(project, "diff", "--binary", "HEAD")
    result: dict[str, Any] = {
        "schema_version": "cpmt-run-provenance-v1",
        "component": component,
        "git_commit": _git(project, "rev-parse", "HEAD"),
        "git_branch": _git(project, "rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(status),
        "git_status": status.splitlines() if status else [],
        "git_diff_sha256": hashlib.sha256(
            (diff or "").encode("utf-8")
        ).hexdigest(),
        "source_tree_sha256": source_tree_sha256(project),
    }
    if entrypoint is not None:
        resolved = entrypoint.resolve()
        result["entrypoint"] = (
            resolved.relative_to(project.resolve()).as_posix()
            if resolved.is_relative_to(project.resolve()) else str(resolved)
        )
        result["entrypoint_sha256"] = file_sha256(resolved)
    return result
