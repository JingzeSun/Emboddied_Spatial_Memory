"""Shared helpers of the reproduction entry points: repository paths, git, and temporary worktrees of a tag."""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_TAG = "paper-v1"
FREEZE_COMMIT = "dea8c20f58144882752f2bc3936b87fd6568ef45"
S3_05_RUN_COMMIT = "8d58475"
REPORT_DIR = REPO_ROOT / "outputs" / "reproduce"


class Refusal(Exception):
    """A precondition that is not met; reported with exit code 2."""


def git(*arguments: str, cwd: Path = REPO_ROOT, check: bool = True) -> str:
    result = subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True, text=True)
    if check and result.returncode != 0:
        raise Refusal(f"git {' '.join(arguments)}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def resolve(ref: str) -> str:
    """The full commit a tag or commit names, or a refusal that says how to get it."""

    commit = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    if not commit:
        raise Refusal(f"{ref} is not in this clone; run `git fetch --tags origin` (a shallow clone also needs "
                      "`git fetch --unshallow`)")
    return commit


@contextlib.contextmanager
def worktree(ref: str, *, keep: bool = False) -> Iterator[Path]:
    """A clean, detached worktree of ``ref`` in a short temporary path, removed afterwards unless ``keep``."""

    path = Path(tempfile.mkdtemp(prefix="vsmt-"))
    path.rmdir()
    git("worktree", "add", "--detach", str(path), ref)
    try:
        yield path
    finally:
        if not keep:
            git("worktree", "remove", "--force", str(path), check=False)
            shutil.rmtree(path, ignore_errors=True)
            git("worktree", "prune", check=False)


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_report(name: str, payload: dict[str, Any]) -> Path:
    """Write a report under ``outputs/reproduce/`` (not tracked by git)."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return path
