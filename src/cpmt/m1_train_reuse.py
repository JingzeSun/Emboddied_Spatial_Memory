"""Read-only D-054 generation provenance bridge; never rewrites train metadata."""
from __future__ import annotations

import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOTS = ("src", "scripts/generate_m1_parallel.py", "configs/m1_hard_condition_v7.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_generation_files(root, commit):
    require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "invalid generation commit")
    raw = subprocess.check_output(["git", "archive", commit, *ROOTS], cwd=root)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        return {p.name: archive.extractfile(p).read().replace(b"\r\n", b"\n")
                for p in archive.getmembers() if p.isfile()}


def source_changes(root, commit):
    old = git_generation_files(root, commit)
    listed = subprocess.check_output(["git", "ls-files", "--", *ROOTS], cwd=root, text=True).splitlines()
    current = {name: (root / name).read_bytes().replace(b"\r\n", b"\n") for name in listed}
    # Include newly authored source files during local policy preparation.
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", *ROOTS],
                                       cwd=root, text=True).splitlines()
    current.update({name: (root / name).read_bytes().replace(b"\r\n", b"\n") for name in untracked})
    changes = {name: {"change": "added" if name not in old else "deleted" if name not in current else "modified",
                      "normalized_sha256": hashlib.sha256(current[name]).hexdigest() if name in current else None}
               for name in sorted(set(old) | set(current)) if old.get(name) != current.get(name)}
    # All pre-existing encoding/learning functions and global definitions must
    # remain identical. Only the causal evaluator and its new import may differ.
    def encoding_tree(raw):
        tree = ast.parse(raw.decode("utf-8"))
        tree.body = [node for node in tree.body
                     if not (isinstance(node, ast.FunctionDef) and node.name == "causal_rollout_metrics")
                     and not (isinstance(node, ast.ImportFrom) and node.module == "m1_candidate_policy")]
        return ast.dump(tree, include_attributes=False)
    require(encoding_tree(old["src/cpmt/m1_af_rollout.py"]) == encoding_tree(current["src/cpmt/m1_af_rollout.py"]),
            "training encoding/learning definitions changed; review data compatibility")
    return changes


def validate_train_reuse(root, marker_path, policy, *, progress=None):
    """Validate all accepted file bytes plus the exact reviewed source delta."""
    root, marker_path = Path(root), Path(marker_path)
    require(policy["schema_version"] == "cpmt-m1-train-reuse-policy-v1" and policy["decision"] == "D-054",
            "wrong train reuse policy")
    require(policy["test_access"] is False and policy["regeneration_performed"] is False, "reuse access drift")
    require(file_digest(marker_path) == policy["generation_marker_sha256"], "accepted generation marker changed")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    require(marker["schema_version"] == "cpmt-scope-rebuild-train-v1" and marker["exit_code"] == 0,
            "generation not accepted")
    require(marker["arrays_digest"] == policy["arrays_digest"], "train arrays identity changed")
    require(marker["attempt"]["provenance"]["git_commit"] == policy["generation_commit"], "wrong generator source")
    require(marker["binding"]["protocol_sha256"] == policy["generation_protocol_sha256"]
            and marker["binding"]["groups"] == 1000 and marker["binding"]["split"] == "train",
            "generation contract changed")
    require(marker["test_access"] is False and marker["validation_generated"] is False
            and marker["training_performed"] is False, "wrong generation boundary")
    require(marker["manifest"]["teacher_health_gate"]["pass"] is True, "teacher health failed")
    for name, expected in policy["evidence_reports"].items():
        require(file_digest(root / name) == expected, "compatibility evidence report changed: " + name)
    require(source_changes(root, policy["generation_commit"]) == policy["reviewed_source_changes"],
            "source changes exceed the reviewed generation/evaluation bridge")
    directory = marker_path.parent.resolve()
    require(Path(marker["arrays_path"]).resolve() == directory / "train.npz", "arrays path mismatch")
    expected_names = ["train.npz", "train.manifest.json"] + [f"shards/train_{g:06d}.npz" for g in range(1000)]
    require(set(marker["file_sha256"]) == set(expected_names), "accepted file list incomplete")
    for index, name in enumerate(expected_names, 1):
        require(file_digest(directory / name) == marker["file_sha256"][name], "accepted train file changed: " + name)
        if progress and (index % 100 == 0 or index == len(expected_names)):
            progress(index, len(expected_names))
    require(json.loads((directory / "train.manifest.json").read_text(encoding="utf-8")) == marker["manifest"],
            "manifest body mismatch")
    return {"schema_version": "cpmt-m1-train-reuse-verification-v1", "accepted": True,
            "generation_commit": policy["generation_commit"], "arrays_digest": marker["arrays_digest"],
            "generation_marker_sha256": file_digest(marker_path), "verified_files": len(expected_names),
            "verified_train_groups": 1000, "encoding_definition_check": "unchanged_except_causal_evaluation",
            "reference_behavior_evidence_groups": 16, "all_groups_regenerated_and_compared": False,
            "source_changes": policy["reviewed_source_changes"], "test_access": False,
            "validation_access": False, "data_generated": False, "training_performed": False,
            "formal_budget_authorized": False}
