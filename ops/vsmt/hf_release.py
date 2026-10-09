#!/usr/bin/env python3
"""S3-05R: pack, check and upload one release tier to Hugging Face (ruling 110), resumable; then verify the remote files.

白话：按层（T0～T3）把 B1 上的产物打包、核对、上传到 Hugging Face 的私有仓库。每一项先打成确定性 tar（或原样复制的文件）
放进暂存目录，算 sha256 和树摘要，并与已有摘要核对（test 对 S3-02 封印，cache 对 S3-02 导出）；核对不过就停下、不上传。
暂存目录攒到一批（默认 20 GiB）就提交一次，并把这批记进 done.jsonl，所以中断后再跑会从下一项接着做。全部传完后写清单
（MANIFEST.json，同时上传并复制到 exports），verify 再对照远端每个文件的大小与 sha256。例如 T1 的 test raw 一条 episode 是
test/raw/<id>.tar，清单里记它恢复到 vsmt_outputs/s3-02-3f6ef1d/test/<id>。它不改、不删任何源目录。

Usage (B1, from a checkout of the release commit; network through `source /etc/network_turbo`, token from `hf auth login`):
  python ops/vsmt/hf_release.py plan   --tier T1 --state-dir /root/autodl-tmp/hf-release/T1
  python ops/vsmt/hf_release.py run    --tier T1 --state-dir ... --staging /root/autodl-tmp/hf-staging [--batch-gib 20]
  python ops/vsmt/hf_release.py verify --tier T1 --state-dir ...
  python ops/vsmt/hf_release.py status --tier T1 --state-dir ...
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_hf_release as hf  # noqa: E402

DEFAULT_BASE = "/root/autodl-tmp"
SEAL_EXPORT = "vsmt_outputs/exports/vsmt_lean_s3_02_test_seal_3f6ef1d.json"
CACHE_EXPORTS = {("instance_cache", split): f"results/vsmt_lean_s3_02_instance_cache_{split}_3f6ef1d.json" for split in ("train", "validation")}
CACHE_EXPORTS.update({("sam2_cache", split): f"results/vsmt_lean_s3_02_sam2_cache_{split}_3f6ef1d.json" for split in ("train", "validation")})
FREE_MARGIN_BYTES = 5 * 2 ** 30


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True, check=True).stdout.strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def say(text: str) -> None:
    print(f"[hf-release {time.strftime('%H:%M:%S')}] {text}", flush=True)


class HubUploader:
    """The real Hugging Face side (huggingface_hub imported only here, so tests and planning need no network package)."""

    def __init__(self) -> None:
        from huggingface_hub import HfApi
        self.api = HfApi()

    def ensure_repo(self, repo: str, repo_type: str) -> None:
        self.api.create_repo(repo, repo_type=repo_type, private=True, exist_ok=True)

    def upload(self, repo: str, repo_type: str, folder: Path, message: str) -> str:
        info = self.api.upload_folder(repo_id=repo, repo_type=repo_type, folder_path=str(folder), path_in_repo="", commit_message=message)
        return str(getattr(info, "oid", "") or getattr(info, "commit_url", ""))

    def remote_files(self, repo: str, repo_type: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for entry in self.api.list_repo_tree(repo, repo_type=repo_type, recursive=True, expand=True):
            if not hasattr(entry, "size"):
                continue
            lfs = getattr(entry, "lfs", None)
            sha = getattr(lfs, "sha256", None) if lfs is not None else None
            if sha is None and isinstance(lfs, Mapping):
                sha = lfs.get("sha256")
            out[entry.path] = {"bytes": int(entry.size), "sha256": sha}
        return out

    def head(self, repo: str, repo_type: str) -> str:
        return str(self.api.repo_info(repo, repo_type=repo_type).sha)


def directory_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def plan_items(tier: str, base: str) -> list[hf.Item]:
    groups = hf.tiers(base)[tier]
    return [item for group in groups for item in hf.items_of(group)]


def load_expectations(base: str, tier: str) -> tuple[Mapping[str, Any] | None, dict[str, dict[str, str]]]:
    seal = None
    if tier == "T1":
        seal = json.loads((Path(base) / SEAL_EXPORT).read_text(encoding="utf-8"))
    caches: dict[str, dict[str, str]] = {}
    split = {"T1": "validation", "T3": "train"}.get(tier)
    if split:
        for kind in ("instance_cache", "sam2_cache"):
            path = ROOT / CACHE_EXPORTS[(kind, split)]
            caches[kind] = hf.cache_export_expectations(json.loads(path.read_text(encoding="utf-8")))
    return seal, caches


def done_records(state: Path) -> dict[str, dict[str, Any]]:
    path = state / "done.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["path_in_repo"]: row for row in rows}


def cmd_plan(args: argparse.Namespace) -> int:
    items = plan_items(args.tier, args.base)
    rows = [{"path_in_repo": i.path_in_repo, "kind": i.kind, "source": str(i.source), "restore_path": i.restore_path,
             "repo": i.group.repo, "repo_type": i.group.repo_type, "source_bytes": directory_bytes(i.source)} for i in items]
    plan = {"stage": hf.STAGE, "tier": args.tier, "code_commit": git_head(), "written_utc": utc_now(), "items": rows,
            "counts": {"items": len(rows), "source_bytes": sum(r["source_bytes"] for r in rows)}}
    write_json(Path(args.state_dir) / "plan.json", plan)
    say(f"plan {args.tier}: {len(rows)} items, {plan['counts']['source_bytes'] / 2 ** 30:.1f} GiB -> {args.state_dir}/plan.json")
    return 0


def run_tier(tier: str, *, base: str, state: Path, staging: Path, batch_bytes: int, uploader: Any,
             free_bytes=lambda path: shutil.disk_usage(path).free, commit: str | None = None) -> int:
    """Pack, check and upload every not-yet-uploaded item of ``tier`` in batches; returns 0, or 3 when a check failed."""

    commit = commit or git_head()
    items = plan_items(tier, base)
    seal, caches = load_expectations(base, tier)
    done = done_records(state)
    pending = [i for i in items if i.path_in_repo not in done]
    repos = sorted({(i.group.repo, i.group.repo_type) for i in items})
    for repo, repo_type in repos:
        uploader.ensure_repo(repo, repo_type)
    say(f"{tier}: {len(items)} items, {len(done)} already uploaded, {len(pending)} to go")
    if staging.exists():
        shutil.rmtree(staging)
    batch: list[dict[str, Any]] = []
    used = 0
    state.mkdir(parents=True, exist_ok=True)

    def flush() -> None:
        nonlocal batch, used
        if not batch:
            return
        by_repo: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in batch:
            by_repo.setdefault((row["repo"], row["repo_type"]), []).append(row)
        for (repo, repo_type), rows in sorted(by_repo.items()):
            folder = staging / repo.replace("/", "__")
            ref = uploader.upload(repo, repo_type, folder, f"S3-05R {tier}: {len(rows)} items ({sum(r['bytes'] for r in rows) / 2 ** 30:.2f} GiB), release code {commit[:7]}")
            with (state / "done.jsonl").open("a", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps({**row, "commit_ref": ref, "uploaded_utc": utc_now()}, sort_keys=True, ensure_ascii=False) + "\n")
            say(f"uploaded {len(rows)} items to {repo} ({ref[:12]})")
        shutil.rmtree(staging, ignore_errors=True)
        batch, used = [], 0

    for item in pending:
        estimate = directory_bytes(item.source)
        if batch and (used + estimate > batch_bytes or free_bytes(state) < estimate + FREE_MARGIN_BYTES):
            flush()
        if free_bytes(state) < estimate + FREE_MARGIN_BYTES:
            say(f"STOP: not enough free disk for {item.path_in_repo} ({estimate / 2 ** 30:.1f} GiB)")
            return 3
        # built outside the upload folders first: an item that fails its check never sits where a flush would upload it
        checking = staging.parent / (staging.name + "-check")
        shutil.rmtree(checking, ignore_errors=True)
        record = hf.build_item(item, checking)
        problems = hf.check_item(item, record, seal=seal, cache_exports=caches)
        if not problems:
            target = staging / item.group.repo.replace("/", "__") / item.path_in_repo
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(checking / item.path_in_repo), str(target))
        shutil.rmtree(checking, ignore_errors=True)
        if problems:
            flush()
            write_json(state / "problems.json", {"item": item.path_in_repo, "problems": problems, "written_utc": utc_now()})
            say(f"STOP: {item.path_in_repo} does not match the existing digests: {problems}")
            return 3
        batch.append({**record, "repo": item.group.repo, "repo_type": item.group.repo_type})
        used += record["bytes"]
        if used >= batch_bytes:
            flush()
    flush()
    done = done_records(state)
    records = [done[i.path_in_repo] for i in items]
    body = hf.manifest(tier, records, code_commit=commit, repos=repos, problems=[], written_utc=utc_now())
    write_json(state / hf.MANIFEST_NAME, body)
    for repo, repo_type in repos:
        folder = staging / "manifest"
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(state / hf.MANIFEST_NAME, folder / hf.MANIFEST_NAME)
        uploader.upload(repo, repo_type, folder, f"S3-05R {tier}: manifest {body['manifest_sha256'][:12]}")
        shutil.rmtree(folder, ignore_errors=True)
    say(f"{tier} done: {body['counts']['items']} items, {body['counts']['bytes'] / 2 ** 30:.2f} GiB, manifest {body['manifest_sha256'][:12]}")
    return 0


def verify_tier(tier: str, *, state: Path, uploader: Any) -> dict[str, Any]:
    body = json.loads((state / hf.MANIFEST_NAME).read_text(encoding="utf-8"))
    problems: list[str] = []
    heads = {}
    for repo, repo_type in body["repos"]:
        remote = uploader.remote_files(repo, repo_type)
        heads[repo] = uploader.head(repo, repo_type)
        for row in body["items"]:
            if row.get("repo", repo) != repo:
                continue
            found = remote.get(row["path_in_repo"])
            if found is None:
                problems.append(f"missing_remote:{row['path_in_repo']}")
            elif found["bytes"] != row["bytes"] or (found["sha256"] is not None and found["sha256"] != row["sha256"]):
                problems.append(f"remote_differs:{row['path_in_repo']}")
        if hf.MANIFEST_NAME not in remote:
            problems.append(f"manifest_missing:{repo}")
    report = {"stage": hf.STAGE, "tier": tier, "manifest_sha256": body["manifest_sha256"], "revisions": heads,
              "items": len(body["items"]), "problems": problems, "pass": not problems, "written_utc": utc_now()}
    write_json(state / "verify.json", report)
    return report


CARDS_DIR = ROOT / "ops" / "vsmt" / "hf_cards"
LICENSE_FILE = "LICENSE-APACHE-2.0"


def upload_cards(tier: str, *, uploader: Any, staging: Path, cards_dir: Path = CARDS_DIR) -> list[str]:
    """Ruling 114: the tier's card (README.md, licence metadata, upstream notices, the 3RScan statement) and the Apache-2.0
    text, one commit per repo; returns the commit refs. Data files are not touched."""

    repos = sorted({(g.repo, g.repo_type) for g in hf.tiers(DEFAULT_BASE)[tier]})
    card, licence = cards_dir / f"README_{tier}.md", cards_dir / LICENSE_FILE
    hf._require(card.is_file() and licence.is_file(), f"cards_missing:{tier}")
    refs = []
    for repo, repo_type in repos:
        folder = staging / "cards" / repo.replace("/", "__")
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        shutil.copyfile(card, folder / "README.md")
        shutil.copyfile(licence, folder / LICENSE_FILE)
        refs.append(uploader.upload(repo, repo_type, folder, f"S3-05R {tier}: card and Apache-2.0 notice (ruling 114)"))
        shutil.rmtree(folder, ignore_errors=True)
    return refs


def cmd_cards(args: argparse.Namespace) -> int:
    refs = upload_cards(args.tier, uploader=HubUploader(), staging=Path(args.staging))
    say(f"cards {args.tier}: {refs}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    return run_tier(args.tier, base=args.base, state=Path(args.state_dir), staging=Path(args.staging),
                    batch_bytes=int(args.batch_gib * 2 ** 30), uploader=HubUploader())


def cmd_verify(args: argparse.Namespace) -> int:
    report = verify_tier(args.tier, state=Path(args.state_dir), uploader=HubUploader())
    say(f"verify {args.tier}: pass={report['pass']} items={report['items']} revisions={report['revisions']} problems={report['problems'][:6]}")
    if report["pass"] and args.export_dir:
        name = f"vsmt_lean_hf_release_{args.tier}_{git_head()[:7]}.json"
        body = json.loads((Path(args.state_dir) / hf.MANIFEST_NAME).read_text(encoding="utf-8"))
        write_json(Path(args.export_dir) / name, {**body, "verify": report})
        say(f"export -> {args.export_dir}/{name}")
    return 0 if report["pass"] else 3


def cmd_status(args: argparse.Namespace) -> int:
    state = Path(args.state_dir)
    plan = json.loads((state / "plan.json").read_text(encoding="utf-8")) if (state / "plan.json").exists() else {"items": []}
    done = done_records(state)
    print(json.dumps({"tier": args.tier, "planned": len(plan["items"]), "uploaded": len(done),
                      "uploaded_gib": round(sum(r["bytes"] for r in done.values()) / 2 ** 30, 2),
                      "manifest": (state / hf.MANIFEST_NAME).exists(), "problems": (state / "problems.json").exists()}))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="step", required=True)
    for name, handler in (("plan", cmd_plan), ("run", cmd_run), ("verify", cmd_verify), ("status", cmd_status), ("cards", cmd_cards)):
        p = sub.add_parser(name)
        p.add_argument("--tier", required=True, choices=["T0", "T1", "T2", "T3"])
        p.add_argument("--state-dir", required=True)
        p.add_argument("--base", default=DEFAULT_BASE)
        if name in ("run", "cards"):
            p.add_argument("--staging", required=True)
        if name == "run":
            p.add_argument("--batch-gib", type=float, default=20.0)
        if name == "verify":
            p.add_argument("--export-dir", default=None)
        p.set_defaults(handler=handler)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except hf.ReleaseError as error:
        say(f"refused: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
