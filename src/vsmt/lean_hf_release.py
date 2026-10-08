"""Hugging Face release of the S3 products (ruling 110, PLAN S3-05R): what goes where, and how each piece is made checkable.

白话：把 S3 的产物分四层（T0 结果与权重、T1 评估输入、T2 训练与审计记录、T3 训练输入）发到 Hugging Face，别人可以只下其中一层。
每条 episode 目录打成一个确定性 tar（文件按路径排序，时间、属主、权限固定），所以同一个目录无论何时何地打包，tar 的 sha256
都相同；清单里同时记 tar 的 sha256 和目录的树摘要（与 test 封印同一种算法），下载的人解包后重算树摘要就能逐字节核对。
输入是 B1 上的目录和已有的封印、cache 导出；输出是一份清单（每一项：仓库里的路径、恢复到哪里、字节数、sha256、树摘要、
与已有摘要的核对结果）。例如 test 的一条 raw episode，清单里的树摘要必须等于 S3-02 test 封印里那条的摘要。它不改任何产物，
也不读 test 的内容做任何计算以外的事——只算字节摘要。

Pure functions only (no network); ops/vsmt/hf_release.py and ops/vsmt/hf_fetch.py do the uploading and downloading.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from vsmt import lean_test_seal

STAGE = "vsmt.lean.s3_05r.hf_release.v1"
MANIFEST_NAME = "MANIFEST.json"
#: never released: the pool's lock, half-written files, and the hosts directory (addresses and key paths of rented machines)
EXCLUDED_NAMES = frozenset({".lock", "hosts"})
EXCLUDED_SUFFIXES = (".tmp",)
TAR_FORMAT = tarfile.GNU_FORMAT
FILE_MODE, DIR_MODE = 0o644, 0o755


class ReleaseError(ValueError):
    """A refusal with a stable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReleaseError(code)


def file_sha256(path: Path) -> str:
    return lean_test_seal.file_sha256(Path(path))


def tree_digest(directory: Path) -> dict[str, Any]:
    """The S3-02 seal's per-directory digest (relative path, size and sha256 of every file, sorted by path) over the files a
    release tar holds; equal to ``lean_test_seal.tree_digest`` whenever nothing in the directory is excluded."""

    directory = Path(directory)
    _require(directory.is_dir(), f"not_a_directory:{directory}")
    rows, total = [], 0
    for path in _members(directory):
        if path.is_file():
            size = path.stat().st_size
            total += size
            rows.append(f"{path.relative_to(directory).as_posix()}\t{size}\t{file_sha256(path)}")
    return {"files": len(rows), "bytes": total, "sha256": hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()}


def excluded(name: str) -> bool:
    return name in EXCLUDED_NAMES or name.endswith(EXCLUDED_SUFFIXES)


# --------------------------------------------------------------------------
# deterministic tar
# --------------------------------------------------------------------------

def _members(directory: Path) -> list[Path]:
    out = []
    for path in sorted(directory.rglob("*"), key=lambda p: p.relative_to(directory).as_posix()):
        _require(not path.is_symlink(), f"symlink_not_released:{path}")
        if any(excluded(part) for part in path.relative_to(directory).parts):
            continue
        out.append(path)
    return out


def write_deterministic_tar(directory: Path, target: Path) -> None:
    """Tar ``directory`` as ``<name>/...``: members sorted by path, mtime 0, owner 0/0 without names, modes 644/755, GNU format.

    The same directory content gives the same bytes whatever the file times, owners, permissions or creation order."""

    directory = Path(directory)
    _require(directory.is_dir(), f"not_a_directory:{directory}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")

    def info(name: str, *, is_dir: bool, size: int = 0) -> tarfile.TarInfo:
        member = tarfile.TarInfo(name)
        member.type = tarfile.DIRTYPE if is_dir else tarfile.REGTYPE
        member.mode = DIR_MODE if is_dir else FILE_MODE
        member.mtime = 0
        member.uid = member.gid = 0
        member.uname = member.gname = ""
        member.size = size
        return member

    with tarfile.open(temporary, "w", format=TAR_FORMAT) as archive:
        archive.addfile(info(directory.name, is_dir=True))
        for path in _members(directory):
            name = f"{directory.name}/{path.relative_to(directory).as_posix()}"
            if path.is_dir():
                archive.addfile(info(name, is_dir=True))
            else:
                with path.open("rb") as handle:
                    archive.addfile(info(name, is_dir=False, size=path.stat().st_size), handle)
    os.replace(temporary, target)


def safe_extract(archive_path: Path, destination: Path) -> Path:
    """Extract a release tar under ``destination`` (refusing absolute paths, '..', links and special files); returns the top dir."""

    destination = Path(destination)
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        _require(bool(members), "empty_archive")
        top = members[0].name.split("/")[0]
        for member in members:
            parts = Path(member.name).parts
            _require(not Path(member.name).is_absolute() and ".." not in parts and parts[0] == top, f"unsafe_member:{member.name}")
            _require(member.isdir() or member.isreg(), f"unsupported_member:{member.name}")
        target = destination / top
        _require(not target.exists(), f"restore_target_exists:{target}")
        destination.mkdir(parents=True, exist_ok=True)
        for member in members:
            out = destination / member.name
            if member.isdir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, out.open("wb") as sink:
                    while True:
                        chunk = source.read(1 << 20)
                        if not chunk:
                            break
                        sink.write(chunk)
    return target


# --------------------------------------------------------------------------
# what goes where
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Group:
    """One release group: a directory on the coordinator, how it is cut into items, and where its items go.

    mode 'children': every child directory is one tar item, every top-level file one file item;
    mode 'files': every file under the root (recursively) is one file item at its relative path."""

    repo: str
    repo_type: str
    prefix: str
    root: str
    restore_to: str
    mode: str
    checks: tuple[str, ...] = ()


@dataclass
class Item:
    group: Group
    kind: str            # 'tar' or 'file'
    source: Path
    path_in_repo: str
    restore_path: str    # relative to the restore base (the coordinator's /root/autodl-tmp)
    name: str
    record: dict[str, Any] = field(default_factory=dict)


def items_of(group: Group) -> list[Item]:
    root = Path(group.root)
    _require(root.is_dir(), f"group_root_missing:{root}")
    _require(group.mode in ("children", "files"), f"unknown_mode:{group.mode}")
    out: list[Item] = []
    if group.mode == "children":
        for path in sorted(root.iterdir(), key=lambda p: p.name):
            if excluded(path.name):
                continue
            _require(not path.is_symlink(), f"symlink_not_released:{path}")
            if path.is_dir():
                out.append(Item(group, "tar", path, f"{group.prefix}/{path.name}.tar", f"{group.restore_to}/{path.name}", path.name))
            elif path.is_file():
                out.append(Item(group, "file", path, f"{group.prefix}/_root/{path.name}", f"{group.restore_to}/{path.name}", path.name))
    else:
        for path in _members(root):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                out.append(Item(group, "file", path, f"{group.prefix}/{relative}", f"{group.restore_to}/{relative}", relative))
    return out


def tiers(base: str, *, s3_02_tag: str = "3f6ef1d", s3_04_commit: str = "dea8c20", user: str = "Jsun0632") -> dict[str, list[Group]]:
    """The four tiers of ruling 110 as groups over the coordinator's directories (base = /root/autodl-tmp)."""

    raw, geometry = f"vsmt_outputs/s3-02-{s3_02_tag}", f"vsmt_private/s3-02-geometry-{s3_02_tag}"
    cache = {front: f"vsmt_caches/s3-02-{front}-{s3_02_tag}" for front in ("instance", "sam2")}

    def split_groups(repo: str, split: str) -> list[Group]:
        rows = [("raw", raw), ("geometry", geometry), ("instance_cache", cache["instance"]), ("sam2_cache", cache["sam2"])]
        return [Group(repo, "dataset", f"{split}/{kind}", f"{base}/{path}/{split}", f"{path}/{split}", "children",
                      ("test_seal",) if split == "test" else (("cache_export",) if kind.endswith("_cache") else ()))
                for kind, path in rows]

    t0 = f"{user}/vsmt-lean"
    run3, run5 = "vsmt_private/s3-03-run", "vsmt_private/s3-05-run"
    out = {
        "T0": [Group(t0, "model", f"weights/{front}", f"{base}/{run3}/{front}/training/round1", f"{run3}/{front}/training/round1",
                     "children") for front in ("instance", "sam2")]
              + [Group(t0, "model", "exports", f"{base}/vsmt_outputs/exports", "vsmt_outputs/exports", "files"),
                 Group(t0, "model", f"s3-04-{s3_04_commit}", f"{base}/vsmt_private/s3-04-{s3_04_commit}",
                       f"vsmt_private/s3-04-{s3_04_commit}", "files"),
                 Group(t0, "model", "reid", f"{base}/vsmt_private/exports", "vsmt_private/exports", "files")],
        "T1": split_groups(f"{user}/vsmt-lean-s3-eval", "validation") + split_groups(f"{user}/vsmt-lean-s3-eval", "test"),
        "T3": split_groups(f"{user}/vsmt-lean-s3-train", "train"),
    }
    records = f"{user}/vsmt-lean-s3-records"
    t2: list[Group] = []
    for run in (run3, run5):
        t2.append(Group(records, "dataset", run.split("/")[-1], f"{base}/{run}", run, "children"))
    out["T2"] = t2
    return out


# --------------------------------------------------------------------------
# checks against the digests that already exist
# --------------------------------------------------------------------------

def seal_expectations(seal: Mapping[str, Any], kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Per-episode tree digests and top-level file digests the S3-02 test seal holds for one kind."""

    _require(kind in lean_test_seal.SEAL_KINDS, f"unknown_seal_kind:{kind}")
    entry = seal["kinds"][kind]
    return dict(entry["episodes"]), dict(entry["root_files"])


def check_item(item: Item, record: Mapping[str, Any], *, seal: Mapping[str, Any] | None = None,
               cache_exports: Mapping[str, Mapping[str, str]] | None = None) -> list[str]:
    """Problems for one built item against the digests that existed before the release (empty means it agrees).

    test_seal: a test episode's tree digest (and a top-level file's sha256) equals the S3-02 seal's;
    cache_export: a cache episode's receipt.json names the episode_seal_sha256 the S3-02 cache export lists."""

    problems: list[str] = []
    kind = item.group.prefix.split("/")[-1]
    if "test_seal" in item.group.checks:
        _require(seal is not None, "test_seal_check_needs_the_seal")
        episodes, root_files = seal_expectations(seal, kind)
        if item.kind == "tar":
            if episodes.get(item.name) != record["tree"]:
                problems.append(f"test_seal_differs:{kind}:{item.name}")
        elif item.name not in (lean_test_seal.MARKER_NAME, lean_test_seal.READ_RECORD_NAME):
            expected = root_files.get(item.name)
            if expected is None or expected.get("sha256") != record["sha256"] or expected.get("bytes") != record["bytes"]:
                problems.append(f"test_seal_root_file_differs:{kind}:{item.name}")
    if "cache_export" in item.group.checks and item.kind == "tar":
        expected = (cache_exports or {}).get(kind, {}).get(item.name)
        receipt = item.source / "receipt.json"
        found = json.loads(receipt.read_text(encoding="utf-8")).get("episode_seal_sha256") if receipt.is_file() else None
        if expected is not None and found != expected:
            problems.append(f"cache_export_differs:{kind}:{item.name}")
    return problems


def cache_export_expectations(export: Mapping[str, Any]) -> dict[str, str]:
    """episode id -> episode_seal_sha256 from an S3-02 cache export (succeeded episodes only)."""

    return {row["episode_id"]: row["episode_seal_sha256"] for row in export.get("episodes", [])
            if row.get("status") == "succeeded" and row.get("episode_seal_sha256")}


# --------------------------------------------------------------------------
# records, batches and the manifest
# --------------------------------------------------------------------------

def build_item(item: Item, staging: Path) -> dict[str, Any]:
    """Make the uploadable file under ``staging`` at its repo path and return its record (sha256, bytes, tree for a tar)."""

    target = Path(staging) / item.path_in_repo
    target.parent.mkdir(parents=True, exist_ok=True)
    if item.kind == "tar":
        write_deterministic_tar(item.source, target)
        record = {"tree": tree_digest(item.source)}
    else:
        _require(item.source.is_file(), f"source_missing:{item.source}")
        with item.source.open("rb") as source, target.open("wb") as sink:
            while True:
                chunk = source.read(1 << 20)
                if not chunk:
                    break
                sink.write(chunk)
        record = {}
    record.update({"path_in_repo": item.path_in_repo, "kind": item.kind, "restore_path": item.restore_path,
                   "source": str(item.source), "bytes": target.stat().st_size, "sha256": file_sha256(target)})
    if item.kind == "file":
        _require(record["sha256"] == file_sha256(item.source), f"copy_differs:{item.source}")
    return record


def batches(sizes: Sequence[tuple[str, int]], limit_bytes: int) -> list[list[str]]:
    """Consecutive batches of item keys, each at most ``limit_bytes`` (an item larger than the limit is a batch of its own)."""

    out: list[list[str]] = []
    current: list[str] = []
    used = 0
    for key, size in sizes:
        if current and used + size > limit_bytes:
            out.append(current)
            current, used = [], 0
        current.append(key)
        used += size
    if current:
        out.append(current)
    return out


def manifest(tier: str, records: Sequence[Mapping[str, Any]], *, code_commit: str, repos: Iterable[tuple[str, str]],
             problems: Sequence[str], written_utc: str) -> dict[str, Any]:
    rows = sorted(records, key=lambda r: r["path_in_repo"])
    body = {"stage": STAGE, "tier": tier, "code_commit": code_commit, "repos": sorted(set(repos)), "written_utc": written_utc,
            "restore_base": "/root/autodl-tmp", "rule": ("each item is a deterministic tar of one directory (members sorted, mtime 0, "
            "owner 0/0, modes 644/755, GNU format) or one file; sha256 is of the uploaded bytes; tree is the S3-02 seal digest of "
            "the directory (relative path, size and sha256 of every file)"),
            "counts": {"items": len(rows), "bytes": sum(int(r["bytes"]) for r in rows)}, "items": rows, "problems": list(problems)}
    body["manifest_sha256"] = hashlib.sha256(json.dumps({k: v for k, v in body.items() if k not in ("written_utc",)},
                                                        sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return body


def verify_restored(record: Mapping[str, Any], restored: Path) -> list[str]:
    """After download: a tar's directory tree digest, or a file's sha256 and size, equals the manifest record."""

    restored = Path(restored)
    if record["kind"] == "tar":
        if not restored.is_dir():
            return [f"restored_missing:{record['path_in_repo']}"]
        return [] if tree_digest(restored) == record["tree"] else [f"tree_differs:{record['path_in_repo']}"]
    if not restored.is_file():
        return [f"restored_missing:{record['path_in_repo']}"]
    ok = restored.stat().st_size == record["bytes"] and file_sha256(restored) == record["sha256"]
    return [] if ok else [f"file_differs:{record['path_in_repo']}"]
