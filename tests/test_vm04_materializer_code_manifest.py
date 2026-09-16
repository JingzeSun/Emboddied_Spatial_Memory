"""Tests for the reviewed source boundary of the VM-04 materializer."""

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_materializer_code_manifest import (  # noqa: E402
    make_vm04_materializer_code_manifest,
    validate_vm04_materializer_code_manifest,
    verify_vm04_materializer_code_checkout,
)


def _git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ).stdout.strip()


def _repository(root):
    files = {
        "ops/vsmt/vm04_multiview_materializer.py": b"ENTRY = True\n",
        "src/cpmt/__init__.py": b"CPMT = True\n",
        "src/vsmt/__init__.py": b"VSMT = True\n",
        "src/vsmt/nested/module.py": b"VALUE = 1\n",
    }
    for relative, payload in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    _git(root, "init")
    _git(root, "config", "user.email", "vm04@example.invalid")
    _git(root, "config", "user.name", "VM04 Test")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "review materializer")
    return _git(root, "rev-parse", "HEAD")


class MaterializerCodeManifestTest(unittest.TestCase):
    def test_manifest_binds_checkout_and_reviewed_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commit = _repository(root)
            manifest = make_vm04_materializer_code_manifest(
                root, reviewed_git_commit=commit,
            )
            verified = verify_vm04_materializer_code_checkout(
                manifest, repository_root=root,
            )
            self.assertEqual(verified["manifest_sha256"],
                             manifest["manifest_sha256"])
            self.assertEqual(
                [row["path"] for row in verified["sources"]],
                sorted([
                    "ops/vsmt/vm04_multiview_materializer.py",
                    "src/cpmt/__init__.py",
                    "src/vsmt/__init__.py",
                    "src/vsmt/nested/module.py",
                ]),
            )

    def test_checkout_byte_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commit = _repository(root)
            manifest = make_vm04_materializer_code_manifest(
                root, reviewed_git_commit=commit,
            )
            (root / "src/vsmt/nested/module.py").write_bytes(b"VALUE = 2\n")
            with self.assertRaisesRegex(ValueError, "checkout source changed"):
                verify_vm04_materializer_code_checkout(
                    manifest, repository_root=root,
                )

    def test_added_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commit = _repository(root)
            manifest = make_vm04_materializer_code_manifest(
                root, reviewed_git_commit=commit,
            )
            (root / "src/vsmt/late.py").write_bytes(b"LATE = True\n")
            with self.assertRaisesRegex(ValueError, "inventory changed"):
                verify_vm04_materializer_code_checkout(
                    manifest, repository_root=root,
                )

    def test_missing_source_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commit = _repository(root)
            manifest = make_vm04_materializer_code_manifest(
                root, reviewed_git_commit=commit,
            )
            (root / "src/cpmt/__init__.py").unlink()
            with self.assertRaisesRegex(ValueError, "inventory changed"):
                verify_vm04_materializer_code_checkout(
                    manifest, repository_root=root,
                )

            escaped = copy.deepcopy(manifest)
            escaped["sources"][0]["path"] = "../outside.py"
            with self.assertRaisesRegex(ValueError, "normalized repository-relative"):
                validate_vm04_materializer_code_manifest(escaped)

    def test_manifest_digest_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commit = _repository(root)
            manifest = make_vm04_materializer_code_manifest(
                root, reviewed_git_commit=commit,
            )
            manifest["sources"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "manifest digest mismatch"):
                validate_vm04_materializer_code_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
