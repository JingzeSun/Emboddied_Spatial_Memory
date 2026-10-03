"""Ruling 103-1: the S3 test data are generated in S3-02 and sealed until S3-05.

白话：裁决 103-1 让 test 的原始 episode、几何重载与两套 cache 跟 train／validation 一起生成，但写进单独的根并封存——S3-03／S3-04
的入口拒绝读 test 根，S3-05 先核对封印再读，且只读一次。这个模块做三件事：
  * 标记：每个 test 根放一个 ``TEST_SEALED.json``。生成期间是“待封印”（``pending``，还没有摘要）；S3-02 把四个根都生成完以后，
    算出封印并把标记换成带封印摘要的正式标记（``sealed``）；
  * 守卫：``refuse_sealed(paths, reader=...)``——给定的任一路径本身、它的任一上级目录，或（裁决 104-6）它的任一直接子目录里有
    这个标记就拒绝；读取数据的入口在加载任何数据之前调用它，所以 test 根即使被误传给训练、选参或审计入口，也在读第一帧之前就停下，
    把三个 split 的上一级目录传进来也一样被挡住；
  * 封印：逐 episode 计算目录树摘要（每个文件的相对路径、字节数与 sha256 排序后再求 sha256），原始 episode、几何重载、实例分割
    cache、SAM2 cache 四类根各一份，连同根下各阶段回执的摘要写成一个封印文件；S3-05 用 ``verify_seal`` 重算并逐项比对。
输入是四个 test 根的路径与 test 名单，输出是标记、封印与核对结果。例如有人把 SAM2 cache 的 test 根传给节点审计入口，入口报出挡住
它的标记路径并以退出码 2 结束。它只算字节摘要，不看任何帧的内容，不删除、不移动任何文件；它也不是“永远不能读”：S3-05 的入口在核对
封印之后另行解封，那一步在 S3-05 实现时登记。
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
    _require(state in (STATE_PENDING, STATE_SEALED), f"unknown_state:{state}")
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
    """Raise if any given path lies in a sealed (or pending) test root; a data-reading entry calls this before loading anything."""

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
            for p in sorted(root.iterdir()) if p.is_file() and p.name != MARKER_NAME}


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


def verify_seal(seal: Mapping[str, Any], roots: Mapping[str, str | Path] | None = None) -> list[str]:
    """Recompute every digest of a seal (at its own roots, or at ``roots``) and list each difference; empty means intact."""

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
            if state.get("state") != STATE_SEALED or state.get("seal_sha256") != seal_sha256(seal):
                problems.append(f"marker_not_this_seal:{kind}")
    return problems


def seal_roots(roots: Mapping[str, str | Path], *, houses: Sequence[str], tag: str) -> tuple[dict[str, Any], str]:
    """Build the seal and turn every pending marker into the sealed one; returns the seal and its digest."""

    seal = build_seal(roots, houses=houses, tag=tag)
    digest = seal_sha256(seal)
    for kind in SEAL_KINDS:
        write_marker(Path(roots[kind]), kind=kind, state=STATE_SEALED, seal_digest=digest)
    return seal, digest


__all__ = [
    "LeanTestSealError",
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
