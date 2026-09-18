#!/usr/bin/env python3
"""Closed-by-default D-218 offline blind annotation package stage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any, Iterator
import zlib

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d217_estimator_development import validate_d217_contract  # noqa: E402
from vsmt.d218_estimator_frontend import (  # noqa: E402
    adjudicate_annotations,
    make_annotation_package,
    make_annotation_submission,
    public_observation_sha256,
    validate_annotation_package,
    validate_d218_contract,
    validate_upstream_contracts,
)


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D217_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"
D218_PATH = ROOT / "configs/vsmt/vm04_d218_estimator_annotation_features_v1.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")


def _write_or_verify_bytes(path: Path, payload: bytes) -> bool:
    """Write one immutable file, or verify exact bytes after interruption."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _require(path.is_file() and _sha256(path) ==
                 hashlib.sha256(payload).hexdigest(),
                 "existing annotation output bytes changed")
        return True
    with path.open("xb") as handle:
        handle.write(payload)
    return False


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True).strip()


def _load_contracts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    d215 = validate_d215_contract(_read_json(D215_PATH))
    d217 = validate_d217_contract(_read_json(D217_PATH))
    d218 = validate_d218_contract(_read_json(D218_PATH))
    validate_upstream_contracts(
        d215_contract=d215, d217_contract=d217, d218_contract=d218)
    _require(_sha256(D215_PATH) == d218["bindings"]["d215_file_sha256"] and
             _sha256(D217_PATH) == d218["bindings"]["d217_file_sha256"],
             "D-218 bound upstream file bytes changed")
    return d215, d217, d218


def _execution_checkout(contract: dict[str, Any], authorization: str) -> str:
    _require(contract["status"] ==
             contract["activation_policy"]["active_status"],
             "D-218 execution is closed pending implementation review")
    _require(contract["authorization"][authorization] is True,
             f"D-218 {authorization} is not authorized")
    head = _git("rev-parse", "HEAD")
    parent = _git("rev-parse", "HEAD^")
    _require(parent == contract["expected_reviewed_implementation_commit"],
             "D-218 activation parent is not the reviewed implementation")
    changed = _git("diff-tree", "--no-commit-id", "--name-only", "-r", head)
    _require(changed.splitlines() ==
             contract["activation_policy"]["activation_commit_may_change_only"],
             "D-218 activation changed files outside its allowlist")
    _require(not _git("status", "--porcelain"),
             "D-218 execution requires a clean checkout")
    return head


def check() -> dict[str, Any]:
    _, _, contract = _load_contracts()
    return {
        "schema_version": "vsmt-vm04-d218-check-v1",
        "status": contract["status"],
        "execution_authorized": any(contract["authorization"].values()),
        "annotation_package_export":
            contract["authorization"]["annotation_package_export"],
        "annotation_submission_import":
            contract["authorization"]["annotation_submission_import"],
        "audit_open": contract["authorization"]["audit_open_or_generation"],
        "estimator_training": contract["authorization"]["estimator_training"],
        "production_reader": contract["authorization"]["production_reader"],
        "p04_p08_qualification":
            contract["authorization"]["p04_p08_qualification"],
        "route_or_raw_generation":
            contract["authorization"]["route_or_raw_generation"],
    }


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload +
            struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def _png_bytes(rgb: np.ndarray) -> bytes:
    _require(rgb.dtype == np.uint8 and rgb.ndim == 3 and rgb.shape[2] == 3,
             "PNG input must be RGB uint8")
    height, width, _ = rgb.shape
    raw = b"".join(b"\x00" + row.tobytes(order="C") for row in rgb)
    return (b"\x89PNG\r\n\x1a\n" +
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2,
                                               0, 0, 0)) +
            _png_chunk(b"IDAT", zlib.compress(raw, 9)) +
            _png_chunk(b"IEND", b""))


def _depth_false_color(depth: np.ndarray) -> np.ndarray:
    valid = np.isfinite(depth) & (depth >= 0.05) & (depth <= 20.0)
    normalized = np.zeros(depth.shape, dtype=np.float64)
    normalized[valid] = ((np.log(depth[valid].astype(np.float64)) -
                          np.log(0.05)) / (np.log(20.0) - np.log(0.05)))
    near = 1.0 - normalized
    red = np.clip(2.0 * near, 0.0, 1.0)
    blue = np.clip(2.0 * normalized, 0.0, 1.0)
    green = np.clip(1.0 - np.abs(2.0 * normalized - 1.0), 0.0, 1.0)
    output = np.stack((red, green, blue), axis=-1)
    output[~valid] = 0.0
    return np.asarray(np.rint(output * 255.0), dtype=np.uint8)


def _validate_public_receipt(path: Path, npz_path: Path) -> dict[str, Any]:
    receipt = _read_json(path)
    expected = {
        "schema_version", "split", "sample_rank", "public_house_ref",
        "observation_count", "observation_ids_sha256", "rgbd_npz_sha256",
        "contains_house_world_pose_grid_instance_scenario_teacher_or_future",
        "public_receipt_sha256",
    }
    _require(set(receipt) == expected and
             receipt["schema_version"] ==
             "vsmt-vm04-d217-public-rgbd-house-v1" and
             receipt["split"] in {"train", "calibration"} and
             receipt["observation_count"] == 32 and
             receipt["contains_house_world_pose_grid_instance_scenario_teacher_or_future"]
             is False and receipt["rgbd_npz_sha256"] == _sha256(npz_path),
             "D-217 public RGB-D receipt changed")
    digest = receipt.pop("public_receipt_sha256")
    _require(digest == hashlib.sha256(
        canonical_json(receipt).encode("utf-8")).hexdigest(),
        "D-217 public RGB-D receipt digest changed")
    receipt["public_receipt_sha256"] = digest
    return receipt


def _public_houses(public_root: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    _require(public_root.is_dir(), "D-218 public RGB-D root is missing")
    _require(not (public_root / "audit").exists(),
             "D-218 must not open or package audit observations")
    for split in ("train", "calibration"):
        for sample in sorted((public_root / split).glob("sample_*")):
            npz_path = sample / "rgbd.npz"
            receipt_path = sample / "receipt.json"
            _require(npz_path.is_file() and receipt_path.is_file(),
                     "public RGB-D sample is incomplete")
            yield npz_path, _validate_public_receipt(receipt_path, npz_path)


HTML = """<!doctype html>
<meta charset="utf-8"><title>VSMT E-04 blind annotation</title>
<style>body{font-family:system-ui;max-width:980px;margin:auto;background:#111;color:#eee}
.images{display:flex;gap:16px}.images img{width:46%;image-rendering:auto;border:1px solid #555}
button{font-size:18px;margin:8px;padding:10px 18px}.selected{outline:4px solid #4af}
input{font-size:16px;padding:6px}code{color:#9ef}</style>
<h1>VSMT E-04 单帧盲标</h1>
<p>只根据当前 RGB 和固定色标深度图判断：<b>1 房间</b>、<b>2 走廊</b>、<b>3 不确定</b>。不要推测 house、路线或任务角色。</p>
<p>标注者代码：<input id="annotator" placeholder="至少3字符"> <span id="progress"></span></p>
<div class="images"><img id="rgb"><img id="depth"></div>
<div><button data-label="room">1 房间</button><button data-label="corridor">2 走廊</button><button data-label="unknown">3 不确定</button></div>
<div><button id="prev">上一张</button><button id="next">下一张</button><button id="download">下载提交 JSON</button></div>
<p>观察：<code id="obs"></code></p><script src="tasks.js"></script><script>
const p=window.VSMT_ANNOTATION_PACKAGE, key='vsmt-e04-'+p.annotation_package_sha256;
let saved=JSON.parse(localStorage.getItem(key)||'{"index":0,"labels":{}}'), i=saved.index||0;
const $=x=>document.getElementById(x); function show(){let t=p.tasks[i];$('rgb').src=t.rgb_media_path;$('depth').src=t.depth_media_path;$('obs').textContent=t.observation_id;$('progress').textContent=`${i+1}/${p.tasks.length}`;document.querySelectorAll('[data-label]').forEach(b=>b.classList.toggle('selected',saved.labels[t.task_id]===b.dataset.label));saved.index=i;localStorage.setItem(key,JSON.stringify(saved));}
function mark(label){saved.labels[p.tasks[i].task_id]=label;if(i+1<p.tasks.length)i++;show();}
document.querySelectorAll('[data-label]').forEach(b=>b.onclick=()=>mark(b.dataset.label));
document.onkeydown=e=>{if(e.key==='1')mark('room');if(e.key==='2')mark('corridor');if(e.key==='3')mark('unknown');if(e.key==='ArrowLeft'){$('prev').click()}if(e.key==='ArrowRight'){$('next').click()}};
$('prev').onclick=()=>{i=Math.max(0,i-1);show()};$('next').onclick=()=>{i=Math.min(p.tasks.length-1,i+1);show()};
$('download').onclick=()=>{let id=$('annotator').value.trim();if(id.length<3){alert('请输入至少3字符的稳定标注者代码');return}if(Object.keys(saved.labels).length!==p.tasks.length){alert('尚未完成全部任务');return}let out={schema_version:'vsmt-vm04-d218-raw-browser-submission-v1',package_role:p.package_role,annotation_package_sha256:p.annotation_package_sha256,annotator_id:id,labels_by_task_id:saved.labels,other_annotator_results_seen:false,scenario_house_route_identity_seen:false};let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out)],{type:'application/json'}));a.download=p.package_role+'-submission.json';a.click()};show();
</script>"""


def export_packages(*, public_root: Path, output_root: Path) -> dict[str, Any]:
    _, _, contract = _load_contracts()
    activation = _execution_checkout(contract, "annotation_package_export")
    final_path = output_root / "export.receipt.json"
    if final_path.is_file():
        existing = _read_json(final_path)
        digest = existing.pop("export_receipt_sha256", None)
        _require(digest == hashlib.sha256(
            canonical_json(existing).encode("utf-8")).hexdigest(),
            "existing annotation export receipt changed")
        existing["export_receipt_sha256"] = digest
        return existing
    media_root = output_root / "media"
    records: list[dict[str, Any]] = []
    source_receipts: list[str] = []
    reused_media_files = 0
    for npz_path, receipt in _public_houses(public_root):
        source_receipts.append(receipt["public_receipt_sha256"])
        with np.load(npz_path, allow_pickle=False) as arrays:
            _require(set(arrays.files) == {
                "rgb_uint8", "depth_m_float32", "camera_intrinsics_float64",
                "observation_ids"}, "D-217 public NPZ arrays changed")
            for index in range(32):
                observation_id = str(arrays["observation_ids"][index])
                rgb = arrays["rgb_uint8"][index]
                depth = arrays["depth_m_float32"][index]
                intrinsics = arrays["camera_intrinsics_float64"][index]
                public_sha = public_observation_sha256(
                    observation_id=observation_id, rgb_uint8=rgb,
                    depth_m_float32=depth,
                    camera_intrinsics_float64=intrinsics)
                rgb_bytes = _png_bytes(rgb)
                depth_bytes = _png_bytes(_depth_false_color(depth))
                rgb_name = f"{public_sha}.rgb.png"
                depth_name = f"{public_sha}.depth.png"
                for name, payload in ((rgb_name, rgb_bytes),
                                      (depth_name, depth_bytes)):
                    path = media_root / name
                    reused_media_files += int(_write_or_verify_bytes(path, payload))
                records.append({
                    "observation_id": observation_id,
                    "public_observation_sha256": public_sha,
                    "rgb_media_path": f"../../media/{rgb_name}",
                    "rgb_media_sha256": hashlib.sha256(rgb_bytes).hexdigest(),
                    "depth_media_path": f"../../media/{depth_name}",
                    "depth_media_sha256": hashlib.sha256(depth_bytes).hexdigest(),
                })
    packages = {}
    for role in ("annotator_a", "annotator_b"):
        package = make_annotation_package(
            records, package_role=role, d218_contract=contract)
        package_root = output_root / "packages" / role
        manifest_bytes = (canonical_json(package) + "\n").encode("utf-8")
        _write_or_verify_bytes(package_root / "manifest.json", manifest_bytes)
        tasks_js = "window.VSMT_ANNOTATION_PACKAGE=" + canonical_json(package) + ";\n"
        _write_or_verify_bytes(
            package_root / "tasks.js", tasks_js.encode("utf-8"))
        _write_or_verify_bytes(
            package_root / "index.html", HTML.encode("utf-8"))
        packages[role] = package["annotation_package_sha256"]
    receipt = {
        "schema_version": "vsmt-vm04-d218-annotation-export-receipt-v1",
        "activation_commit": activation,
        "observation_count": len(records),
        "media_file_count": len(records) * 2,
        "reused_media_file_count": reused_media_files,
        "source_public_receipts_sha256": hashlib.sha256(
            canonical_json(sorted(source_receipts)).encode("utf-8")).hexdigest(),
        "packages": packages,
        "audit_opened": False,
        "private_input_read": False,
        "estimator_training_reader_route_or_raw_run": False,
    }
    receipt["export_receipt_sha256"] = hashlib.sha256(
        canonical_json(receipt).encode("utf-8")).hexdigest()
    _write_new(final_path, receipt)
    return receipt


def seal_submissions(
    *, package_a_path: Path, package_b_path: Path,
    raw_submission_a_path: Path, raw_submission_b_path: Path,
    adjudication_path: Path | None, output_path: Path,
) -> dict[str, Any]:
    _, _, contract = _load_contracts()
    activation = _execution_checkout(contract, "annotation_submission_import")
    _require(not output_path.exists(), "D-218 adjudication output exists")
    package_a = validate_annotation_package(
        _read_json(package_a_path), d218_contract=contract)
    package_b = validate_annotation_package(
        _read_json(package_b_path), d218_contract=contract)

    def submission(path: Path, package: dict[str, Any]) -> dict[str, Any]:
        raw = _read_json(path)
        _require(set(raw) == {
            "schema_version", "package_role", "annotation_package_sha256",
            "annotator_id", "labels_by_task_id", "other_annotator_results_seen",
            "scenario_house_route_identity_seen"} and
            raw["schema_version"] ==
            "vsmt-vm04-d218-raw-browser-submission-v1" and
            raw["package_role"] == package["package_role"] and
            raw["annotation_package_sha256"] ==
            package["annotation_package_sha256"] and
            raw["other_annotator_results_seen"] is False and
            raw["scenario_house_route_identity_seen"] is False,
            "raw browser submission boundary changed")
        return make_annotation_submission(
            package=package, annotator_id=raw["annotator_id"],
            labels_by_task_id=raw["labels_by_task_id"],
            d218_contract=contract)

    a = submission(raw_submission_a_path, package_a)
    b = submission(raw_submission_b_path, package_b)
    adjudicator_id = None
    labels = None
    if adjudication_path is not None:
        raw = _read_json(adjudication_path)
        _require(set(raw) == {"adjudicator_id", "labels_by_observation_id"},
                 "adjudication import has unexpected fields")
        adjudicator_id = raw["adjudicator_id"]
        labels = raw["labels_by_observation_id"]
    adjudication = adjudicate_annotations(
        package_a=package_a, package_b=package_b,
        submission_a=a, submission_b=b, adjudicator_id=adjudicator_id,
        adjudicated_labels_by_observation_id=labels,
        d218_contract=contract)
    result = {
        "schema_version": "vsmt-vm04-d218-adjudication-stage-receipt-v1",
        "activation_commit": activation,
        "semantic_adjudication": adjudication,
        "audit_opened": False,
        "estimator_training_reader_route_or_raw_run": False,
    }
    result["stage_receipt_sha256"] = hashlib.sha256(
        canonical_json(result).encode("utf-8")).hexdigest()
    _write_new(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    export = commands.add_parser("export-packages")
    export.add_argument("--public-root", type=Path, required=True)
    export.add_argument("--output-root", type=Path, required=True)
    seal = commands.add_parser("seal-submissions")
    seal.add_argument("--package-a", type=Path, required=True)
    seal.add_argument("--package-b", type=Path, required=True)
    seal.add_argument("--submission-a", type=Path, required=True)
    seal.add_argument("--submission-b", type=Path, required=True)
    seal.add_argument("--adjudication", type=Path)
    seal.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "check":
        result = check()
    elif args.command == "export-packages":
        result = export_packages(
            public_root=args.public_root, output_root=args.output_root)
    else:
        result = seal_submissions(
            package_a_path=args.package_a, package_b_path=args.package_b,
            raw_submission_a_path=args.submission_a,
            raw_submission_b_path=args.submission_b,
            adjudication_path=args.adjudication, output_path=args.output)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
