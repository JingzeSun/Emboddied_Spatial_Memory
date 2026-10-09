"""Fetch the two inputs released after the paper's revision: the instance-mask ReID head and the ruling-37 salt.

    python reproduce/fetch_extras.py --dest <data root> [--only reid|salt]

Both files are in Hugging Face layer T0 (``Jsun0632/vsmt-lean``) at revision ``1fc9efe8``, listed in
``MANIFEST_ADDENDUM.json`` there and recorded in ``results/vsmt_lean_hf_release_T0_addendum_1fc9efe.json``.  Each is
downloaded at that revision, checked (size and SHA-256 of the file; the ReID head's payload digest, which the code pins;
the salt's stripped-text digest, which the generator pins) and written to its restore path under ``--dest``, the same
layout ``ops/vsmt/hf_fetch.py`` restores:

- ``vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json`` (needed for the instance-mask runs of L1
  and of the pipeline, and by the memory plug-in's ``front_end="instance"``);
- ``vsmt_private/null_window_salt.txt`` (needed by data generation; keep it outside the code repository).

An existing file with the right digest is kept; one with another digest is refused (exit 3).  Exit codes: 0 done; 2 a
precondition is missing; 3 a digest differs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, load_json  # noqa: E402

RECORD = REPO_ROOT / "results" / "vsmt_lean_hf_release_T0_addendum_1fc9efe.json"
NAMES = {"reid": "reid/reid_head_vitb14_oracle_caa50c7.json", "salt": "inputs/null_window_salt.txt"}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def item_problems(item: dict, path: Path) -> list[str]:
    """What is wrong with a local copy of one addendum item (empty when it is the released file)."""

    if not path.is_file():
        return ["missing"]
    problems = []
    if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
        problems.append("file digest differs")
    if "payload_sha256" in item and json.loads(path.read_text(encoding="utf-8")).get("sha256") != item["payload_sha256"]:
        problems.append("payload digest differs")
    if "stripped_text_sha256" in item:
        text = path.read_text(encoding="utf-8").strip().encode("utf-8")
        if hashlib.sha256(text).hexdigest() != item["stripped_text_sha256"]:
            problems.append("stripped-text digest differs")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dest", type=Path, required=True, help="the data root (the --dest of ops/vsmt/hf_fetch.py)")
    parser.add_argument("--only", choices=tuple(NAMES), default=None)
    args = parser.parse_args(argv)
    record = load_json(RECORD)
    manifest, revision = record["manifest_addendum"], record["revision"]
    wanted = [item for item in manifest["items"] if args.only is None or item["path_in_repo"] == NAMES[args.only]]
    if REPO_ROOT in args.dest.resolve().parents or args.dest.resolve() == REPO_ROOT:
        print("[fetch-extras] refused: --dest must be outside the code repository (the generator refuses a salt inside it)")
        return 2
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[fetch-extras] refused: uv pip install huggingface_hub")
        return 2
    for item in wanted:
        target = args.dest / item["restore_path"]
        if target.exists():
            problems = item_problems(item, target)
            if problems:
                print(f"[fetch-extras] {target} exists and differs from the release ({', '.join(problems)}); not replaced")
                return 3
            print(f"[fetch-extras] kept {target}")
            continue
        with tempfile.TemporaryDirectory() as directory:
            local = Path(hf_hub_download(manifest["repo"], item["path_in_repo"], repo_type=manifest["repo_type"],
                                         revision=revision, local_dir=directory))
            problems = item_problems(item, local)
            if problems:
                print(f"[fetch-extras] {item['path_in_repo']} at {revision[:12]}: {', '.join(problems)}")
                return 3
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, target)
        print(f"[fetch-extras] restored {target} ({item['bytes']} bytes, sha256 {item['sha256'][:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
