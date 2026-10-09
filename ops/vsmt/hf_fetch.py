#!/usr/bin/env python3
"""S3-05R: download a released tier (or part of it) from Hugging Face, check every byte, and restore the original layout.

白话：从 Hugging Face 下某一层（或其中一部分，例如只要 validation 的 instance cache），每个文件先对清单核 sha256，tar 解包后
再重算目录树摘要，与清单（也就是上传时对过封印和 S3-02 导出的那份）逐项相等才算恢复成功；恢复到的位置与 B1 上原来的相对路径
一致（默认根目录 /root/autodl-tmp），所以仓库里的脚本不用改路径就能接着跑。例如
  python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-eval --repo-type dataset --revision <提交> --select validation/instance_cache/
会恢复出 vsmt_caches/s3-02-instance-3f6ef1d/validation/ 下的每条 episode。已经恢复且核对一致的项会跳过；有任何不一致就停下并退出 3。

Usage:
  python ops/vsmt/hf_fetch.py --repo REPO --repo-type dataset|model [--revision SHA] [--select PREFIX ...] [--dest /root/autodl-tmp]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import lean_hf_release as hf  # noqa: E402


class HubDownloader:
    def __init__(self) -> None:
        from huggingface_hub import hf_hub_download
        self.download = hf_hub_download

    def fetch(self, repo: str, repo_type: str, path: str, revision: str | None, directory: Path) -> Path:
        return Path(self.download(repo_id=repo, repo_type=repo_type, filename=path, revision=revision, local_dir=str(directory)))


def say(text: str) -> None:
    print(f"[hf-fetch] {text}", flush=True)


def selected(rows: Sequence[dict[str, Any]], prefixes: Sequence[str]) -> list[dict[str, Any]]:
    return [r for r in rows if not prefixes or any(r["path_in_repo"].startswith(p) for p in prefixes)]


def restore(repo: str, repo_type: str, revision: str | None, *, dest: Path, prefixes: Sequence[str], downloader: Any,
            manifest_path: Path | None = None) -> dict[str, Any]:
    """Download, check and restore; returns {'restored', 'skipped', 'problems'} (stops at the first problem)."""

    work = Path(tempfile.mkdtemp(prefix="hf-fetch-", dir=str(dest) if dest.exists() else None))
    try:
        if manifest_path is None:
            manifest_path = downloader.fetch(repo, repo_type, hf.MANIFEST_NAME, revision, work)
        body = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        rows = selected(body["items"], prefixes)
        say(f"{repo}@{revision or 'main'}: manifest {body['manifest_sha256'][:12]}, {len(rows)} of {len(body['items'])} items selected")
        restored, skipped = 0, 0
        for row in rows:
            target = dest / row["restore_path"]
            if target.exists():
                if hf.verify_restored(row, target):
                    return {"restored": restored, "skipped": skipped, "problems": [f"existing_target_differs:{row['restore_path']}"]}
                skipped += 1
                continue
            local = downloader.fetch(repo, repo_type, row["path_in_repo"], revision, work)
            if local.stat().st_size != row["bytes"] or hf.file_sha256(local) != row["sha256"]:
                return {"restored": restored, "skipped": skipped, "problems": [f"download_differs:{row['path_in_repo']}"]}
            if row["kind"] == "tar":
                out = hf.safe_extract(local, target.parent)
                if out != target:
                    return {"restored": restored, "skipped": skipped, "problems": [f"tar_top_differs:{row['path_in_repo']}"]}
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local, target)
            problems = hf.verify_restored(row, target)
            if problems:
                return {"restored": restored, "skipped": skipped, "problems": problems}
            local.unlink()
            restored += 1
        return {"restored": restored, "skipped": skipped, "problems": []}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--repo-type", required=True, choices=["dataset", "model"])
    parser.add_argument("--revision", default=None, help="pin the commit the paper names (README); default: the current head")
    parser.add_argument("--select", nargs="*", default=[], help="path prefixes in the repo, e.g. validation/instance_cache/")
    parser.add_argument("--dest", default="/root/autodl-tmp")
    parser.add_argument("--manifest", default=None, help="a local MANIFEST.json instead of the repo's")
    args = parser.parse_args(argv)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        result = restore(args.repo, args.repo_type, args.revision, dest=dest, prefixes=args.select, downloader=HubDownloader(),
                         manifest_path=Path(args.manifest) if args.manifest else None)
    except hf.ReleaseError as error:
        say(f"refused: {error}")
        return 2
    say(f"restored {result['restored']}, already present {result['skipped']}, problems {result['problems']}")
    return 0 if not result["problems"] else 3


if __name__ == "__main__":
    sys.exit(main())
