"""The trained VSMT-lean cost heads and the shared ReID heads, from Hugging Face layer T0.

The cost heads and the SAM 2.1 ReID head come from the revision the paper cites; the instance-mask ReID head was added
in a later revision (``results/vsmt_lean_hf_release_T0_addendum_1fc9efe.json``).  Every file is checked twice: the
downloaded file against the release record (``results/vsmt_lean_hf_release_T0_*``) and the extracted weights against the
digest that the S3-04 freeze receipt (``results/vsmt_lean_s3_04_freeze_*``) recorded for the file that ran on test.  The existence threshold ``tau_r`` is the one S3-04 selected on validation for
that front end.  Nothing here is trained or tuned.
"""

from __future__ import annotations

import hashlib
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _repo

T0_REPOSITORY = "Jsun0632/vsmt-lean"
T0_REVISION = "0b2ce7f8bb5de862fd500f10b23e55ba4eebf372"
T0_MANIFEST = _repo.RESULTS_DIR / "vsmt_lean_hf_release_T0_2d179b9.json"
T0_ADDENDUM = _repo.RESULTS_DIR / "vsmt_lean_hf_release_T0_addendum_1fc9efe.json"
FREEZE_RECEIPT = _repo.RESULTS_DIR / "vsmt_lean_s3_04_freeze_dea8c20.json"

#: Front end -> the mask source the frozen code names it by.
MASK_SOURCES = {"sam2": "sam2", "instance": "simulator_instance_masks"}
SEEDS = (7, 19, 31, 43, 59)
ARM = "VSMT-lean"
#: The ReID head released per front end (the instance-mask head is in the T0 addendum).
REID_HEAD_FILES = {"sam2": "reid/reid_head_vitb14_154776d.json", "instance": "reid/reid_head_vitb14_oracle_caa50c7.json"}


class WeightsError(ValueError):
    """A weights file that is missing, unreleased or does not have the pinned digest."""


@dataclass(frozen=True)
class PretrainedWeights:
    """Everything the memory needs from training: the three cost heads, the ReID head and the threshold."""

    front_end: str
    mask_source: str
    seed: int
    tau_r: float
    heads: dict[str, Any]
    reid_head: dict[str, Any]
    provenance: dict[str, Any]


def default_cache_dir() -> Path:
    """``$VSMT_MEMORY_CACHE``, or ``~/.cache/vsmt_memory``."""

    return Path(os.environ.get("VSMT_MEMORY_CACHE") or Path.home() / ".cache" / "vsmt_memory")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_row(path_in_repo: str) -> dict[str, Any]:
    """The release record of a T0 file, with the revision to download it at (the paper's, or the addendum's)."""

    rows = [{**row, "revision": T0_REVISION} for row in _repo.load_json(T0_MANIFEST)["items"]
            if row["path_in_repo"] == path_in_repo]
    addendum = _repo.load_json(T0_ADDENDUM)
    rows += [{**row, "revision": addendum["revision"]} for row in addendum["manifest_addendum"]["items"]
             if row["path_in_repo"] == path_in_repo]
    if len(rows) != 1:
        raise WeightsError(f"{path_in_repo} is not in the T0 release records")
    return rows[0]


def _frozen_digest(path_suffix: str) -> str:
    """The SHA-256 the freeze receipt recorded for the head file whose server path ends with ``path_suffix``."""

    heads = _repo.load_json(FREEZE_RECEIPT)["frozen_bytes"]["heads"]
    pairs = heads.items() if isinstance(heads, dict) else heads
    matches = [digest for path, digest in pairs if str(path).endswith(path_suffix)]
    if len(matches) != 1:
        raise WeightsError(f"the freeze receipt records no single head file ending with {path_suffix}")
    return str(matches[0])


def selected_tau_r(front_end: str) -> float:
    """The existence threshold S3-04 selected for VSMT-lean on this front end (validation only)."""

    receipt = _repo.load_json(FREEZE_RECEIPT)
    return float(receipt["fronts"][front_end]["selection"]["arms"][ARM]["config"]["tau_r"])


def _download(path_in_repo: str, cache_dir: Path) -> Path:
    """The release file, from the cache when it already has the manifest's digest (works offline), else downloaded."""

    row = _manifest_row(path_in_repo)
    cached = cache_dir / "t0" / path_in_repo
    if cached.is_file() and cached.stat().st_size == row["bytes"] and _sha256(cached) == row["sha256"]:
        return cached
    from huggingface_hub import hf_hub_download

    local = Path(hf_hub_download(repo_id=T0_REPOSITORY, repo_type="model", filename=path_in_repo, revision=row["revision"],
                                 local_dir=str(cache_dir / "t0")))
    if local.stat().st_size != row["bytes"] or _sha256(local) != row["sha256"]:
        raise WeightsError(f"{path_in_repo} does not match the T0 release manifest")
    return local


def _extract_member(archive: Path, suffix: str, target: Path) -> Path:
    with tarfile.open(archive) as tar:
        members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith(suffix)]
        if len(members) != 1:
            raise WeightsError(f"{archive.name} holds no single member ending with {suffix}")
        source = tar.extractfile(members[0])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read())
    return target


def load_pretrained(front_end: str = "sam2", seed: int = 7, *, cache_dir: Path | None = None,
                    restored_root: Path | None = None, reid_head_path: Path | None = None) -> PretrainedWeights:
    """The VSMT-lean weights of one front end and seed, downloaded once and digest-checked.

    ``restored_root`` reuses files already restored by ``ops/vsmt/hf_fetch.py --dest <root>`` or
    ``reproduce/fetch_extras.py --dest <root>`` (their server-layout paths under that root) instead of downloading.
    ``reid_head_path`` supplies a ReID head file directly; it must still have the digest the freeze receipt recorded.
    """

    if front_end not in MASK_SOURCES:
        raise WeightsError(f"front_end must be one of {sorted(MASK_SOURCES)}")
    if seed not in SEEDS:
        raise WeightsError(f"seed must be one of {SEEDS}")
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    tar_path = f"weights/{front_end}/{ARM}.tar"
    member = f"s{seed}/weights_grouped.json"
    tar_row = _manifest_row(tar_path)
    heads_digest = _frozen_digest(f"/{front_end}/training/round1/{ARM}/{member}")

    if restored_root is not None:
        heads_file = Path(restored_root) / tar_row["restore_path"] / member
        if not heads_file.exists():
            raise WeightsError(f"{heads_file} is missing: restore {tar_path} with hf_fetch.py first")
    else:
        heads_file = cache_dir / front_end / ARM / member
        if not heads_file.exists() or _sha256(heads_file) != heads_digest:
            _extract_member(_download(tar_path, cache_dir), f"/{member}", heads_file)
    if _sha256(heads_file) != heads_digest:
        raise WeightsError(f"{heads_file} is not the head file the freeze receipt recorded")

    if reid_head_path is not None:
        reid_file = Path(reid_head_path)
        reid_source = "given path"
    elif front_end in REID_HEAD_FILES:
        reid_row = _manifest_row(REID_HEAD_FILES[front_end])
        reid_file = (Path(restored_root) / reid_row["restore_path"] if restored_root is not None
                     else _download(REID_HEAD_FILES[front_end], cache_dir))
        reid_source = f"{T0_REPOSITORY}@{reid_row['revision'][:12]}:{REID_HEAD_FILES[front_end]}"
    else:  # pragma: no cover - every front end has a released head
        raise WeightsError(f"no released ReID head for {front_end}")
    reid_name = "lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json" if front_end == "instance" \
        else "exports/reid_head_vitb14_154776d.json"
    if _sha256(reid_file) != _frozen_digest(reid_name):
        raise WeightsError(f"{reid_file} is not the ReID head the freeze receipt recorded for {front_end}")

    return PretrainedWeights(
        front_end=front_end, mask_source=MASK_SOURCES[front_end], seed=seed, tau_r=selected_tau_r(front_end),
        heads=_repo.load_json(heads_file), reid_head=_repo.load_json(reid_file),
        provenance={"repository": T0_REPOSITORY, "revision": T0_REVISION, "heads_file": f"{tar_path}:{member}",
                    "heads_sha256": heads_digest, "reid_head": reid_source, "reid_head_sha256": _sha256(reid_file),
                    "tau_r_source": f"{FREEZE_RECEIPT.name}: fronts.{front_end}.selection.arms.{ARM}.config"})


__all__ = ["MASK_SOURCES", "PretrainedWeights", "SEEDS", "T0_REPOSITORY", "T0_REVISION", "WeightsError",
           "default_cache_dir", "load_pretrained", "selected_tau_r"]
