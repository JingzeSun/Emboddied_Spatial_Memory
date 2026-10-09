#!/usr/bin/env python3
"""S3-02 run support (ruling 103): input checks, stage markers, the checks between stages, worker sizing, the test seal and verify.

Ruling 103 requires S3-02 to run as one command: generate 450 houses (train 300, validation 50, test 100), add the geometry
reloads, build the instance-segmentation and SAM2 caches, and write test to separate roots that are sealed.
``s3_02_data.sh`` starts each stage's computation in order; this script keeps the books and runs the checks between stages:
  * check: before anything runs, verifies every input -- the S3 manifests, the ProcTHOR source at its registered digest, the
    private salt's digest, the front-end assets, both ReID heads (pinned per source by S0-03), the simulator interpreter, the
    cards, the cgroup quota and memory, and whether the free data disk holds the outputs not yet written (the projection of
    all outputs from the committed S1 reports minus the bytes already under this run's roots) -- and writes the run manifest
    inputs.json;
  * stage-state / mark / status: one marker file per stage (done / hold / stopped / failed, with commit and exit code);
    after a commit change, a stage finished earlier stays valid only if every changed file is one of the three files of the
    generator-commit registration or a document;
  * disk: before generation (and before a resume after an interruption) recomputes the disk needed from the measured bytes per
    house, again minus the bytes this run has already written;
  * movecheck: ruling 36 -- at least 120 executed moves on train, at least 60 of them source-first; otherwise stop for a scale
    ruling;
  * hold: ruling 103-3 -- every generator commit in the raw receipts must be in the S1-03 pose registry, otherwise hold until
    a registration commit; a commit whose camera_pose encoder differs from the registered one stops the run (cannot be
    registered);
  * geometry-ok / cache-ok: whether each split of the geometry reloads and caches is complete, matches the raw episodes one to
    one, and failed only for data reasons;
  * workers: the instance-segmentation cache's worker count (2 threads each, from the cgroup quota and memory) and the card
    list; sam2-measure: SAM2 trials with 1-4 workers on one card, the per-card count with the highest throughput and the
    projected hours (ruling 84-4) -- a trial in which an episode fails for a data reason (e.g. too many fragments) counts and
    is listed, one that fails for another reason (e.g. GPU memory) does not; trial-ok: whether a trial ran to its end (exit 0,
    or exit 1 with a trial receipt);
  * seal-pending / test-summary / seal: the pending-seal markers of the test roots, the counts-only test summary and the seal
    (ruling 103-1);
  * verify: at the end checks that every split agrees across raw episodes, geometry and both caches, recomputes the seal,
    checks every export's digest, compares the four measured houses byte for byte with their train copies (recorded only) and
    writes the final run manifest.
It runs no method and reads no evaluation result; on test it computes only byte digests and counts.

Usage (from the driver; see ops/vsmt/s3_02_data.sh):
  python ops/vsmt/s3_02_manifest.py check --run-root R --autodl-root A --source S --salt-file F --assets-json J ...
  python ops/vsmt/s3_02_manifest.py stage-state --run-root R --stage generate
  python ops/vsmt/s3_02_manifest.py mark --run-root R --stage generate --status done --exit 0 --started <utc>
  python ops/vsmt/s3_02_manifest.py movecheck --run-root R --raw-root <raw>
  python ops/vsmt/s3_02_manifest.py hold --run-root R --raw-root <raw>
  python ops/vsmt/s3_02_manifest.py verify --run-root R --export-dir E --tag T --raw-root ... --geometry-root ... ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from s2_06_manifest import environment, git, load_json, payload_digest_ok, resources, sha256_file, utc_now, write_json  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402

STAGE = "vsmt.lean.s3_02.manifest.v1"
STAGES = ("check", "measure", "generate", "hold", "geometry", "instance-cache", "sam2-measure", "sam2-cache", "export", "verify")
STATUSES = ("done", "hold", "stopped", "failed")
SPLITS = ("train", "validation", "test")
INSTANCE, SAM2 = "simulator_instance_masks", "sam2"
#: the files the pre-authorised registration commit changes (ruling 103-3, as 2339baa -> 6b65cb1): the S1-03 pose registry and the
#: two tests that pin it.  A stage finished at an earlier commit stays done when the commits since changed only these and documents.
REGISTRATION_FILES = ("configs/vsmt/lean_s1_03_frontend_cache_v1.json", "tests/test_vsmt_lean_cross_contract.py",
                      "tests/test_vsmt_lean_public_pose.py")
DOCUMENT_PREFIXES = ("docs/", "results/")
DOCUMENT_FILES = ("README.md", "EXECUTE.md", "AGENTS.md")
S1_03_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
ASSET_REGISTRY = ROOT / "configs" / "vsmt" / "lean_s1_assets_capacity_v2.json"
GENERATOR = "ops/vsmt/lean_s1_02a_pilot.py"
#: ruling 103-4: the geometry reload keeps its measured setting
GEOMETRY_WORKERS = 8
#: the instance-segmentation cache's measured setting (results/vsmt_lean_s1_03_report_oracle_8ebbd05.json: CPU-bound at two threads
#: per worker, 1,369 MiB peak RSS and 496 MiB VRAM per worker); the worker count follows this host's quota and memory
CACHE_THREADS = 2
INSTANCE_RSS_GIB = 1369.4 / 1024.0
MEMORY_RESERVE_GIB = 8.0
#: ruling 84-4: SAM2 throughput on one card with 1..4 workers, on the largest train episodes, before the long run
SAM2_TRIAL_WORKERS = (1, 2, 3, 4)
SAM2_TRIAL_FRAMES = 60
#: the disk projection rests on the committed S1 reports: raw bytes per attempted house, cache bytes per cached episode, the
#: higher of the two S1-era success rates (confirmation 43/50; development 39/50), and a margin
RAW_REPORT = "results/vsmt_lean_s1_02b_report_5f9aa71.json"
CACHE_REPORTS = {INSTANCE: "results/vsmt_lean_s1_03_report_oracle_8ebbd05.json", SAM2: "results/vsmt_lean_s1_03_report_154776d.json"}
SUCCESS_RATE_PLANNING = 43 / 50
DISK_MARGIN = 1.10
#: cache failures that are properties of the data (the D-215 boundary and the frozen checks); any other reason stops the run
CACHE_DATA_FAILURES = ("proposal_overflow", "duplicate_proposal_mask", "fragment_depth_support_insufficient", "descriptor_not_unit_norm")


def manifests(repo: Path = ROOT) -> dict[str, list[str]]:
    from vsmt import lean_s3_manifests

    contract = load_json(repo / "configs" / "vsmt" / "lean_s1_02a_pilot_v2.json")
    registry = load_json(repo / "configs" / "vsmt" / "lean_ruling81_confirmation_houses.json")
    manifest = load_json(repo / "configs" / "vsmt" / "lean_s3_01_manifests.json")
    lean_s3_manifests.validate(manifest, contract["split_freeze"], registry)
    return {split: list(manifest[split]) for split in SPLITS}


def receipts(root: Path) -> dict[str, dict[str, Any]]:
    """{episode: receipt} of the episode directories directly under one root."""

    out = {}
    if Path(root).is_dir():
        for path in sorted(Path(root).glob("procthor10k-*/receipt.json")):
            out[path.parent.name] = load_json(path)
    return out


def succeeded(root: Path) -> list[str]:
    return sorted(name for name, receipt in receipts(root).items() if receipt.get("status") == "succeeded")


# --------------------------------------------------------------------------
# check and disk
# --------------------------------------------------------------------------

def disk_projection(repo: Path, *, houses: int, raw_gb_per_house: float | None = None) -> dict[str, Any]:
    """The disk S3-02 will write: raw episodes for every house, both caches for the expected successes, times a margin."""

    raw = load_json(repo / RAW_REPORT)
    committed_raw = raw["bytes_written_total"] / 1e9 / len(raw["houses"])
    per_house = max(committed_raw, raw_gb_per_house or 0.0)
    caches = {}
    for source, report in CACHE_REPORTS.items():
        stage = load_json(repo / report)["stage"]
        caches[source] = stage["bytes_written_total"] / 1e9 / stage["episodes_succeeded"]
    episodes = houses * SUCCESS_RATE_PLANNING
    need = (houses * per_house + episodes * sum(caches.values())) * DISK_MARGIN
    return {"houses": houses, "raw_gb_per_house": per_house, "raw_gb_per_house_committed": committed_raw,
            "raw_gb_per_house_measured": raw_gb_per_house, "cache_gb_per_episode": caches,
            "episodes_expected": episodes, "success_rate_planning": SUCCESS_RATE_PLANNING, "margin": DISK_MARGIN,
            "need_gb": round(need, 1), "basis": [RAW_REPORT, *CACHE_REPORTS.values()]}


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def written_bytes(roots: Sequence[str | Path]) -> int:
    """The bytes of every file under the given roots (a missing root counts 0): what this run has already written there."""

    total = 0
    for root in roots:
        if not Path(root).is_dir():
            continue
        for directory, _subdirectories, files in os.walk(root):
            for name in files:
                try:
                    total += os.lstat(os.path.join(directory, name)).st_size
                except OSError:  # removed while walking: nothing left to count
                    continue
    return total


def run_roots(text: str | None) -> list[str]:
    return [item for item in (text or "").split(",") if item]


def disk_requirement(projection: Mapping[str, Any], *, written: int, min_free_gib: float | None) -> dict[str, Any]:
    """The free space this run still needs: the projection of all its outputs minus what its roots already hold.

    check reruns at every new commit (e.g. the registration commit after the hold), when the raw episodes (about 108 GB) are
    already on disk; comparing the free space with the projection of all outputs (about 337 GB) would then wrongly refuse a
    disk with less than about 446 GB free at the start. Inputs: the projection, the bytes already under this run's roots and
    an optional manual floor. Output: the space still needed, projection minus written (at least 0); with MIN_FREE_GIB that
    value is used and recorded as a manual override. Example: projection 337 GB, 109 GB written: 228 GB must be free. It
    decides only whether to start and changes no output; the cache's own disk floor still guards against a full disk.
    """

    if min_free_gib is not None:
        return {"required_gb": float(min_free_gib) * 2 ** 30 / 1e9, "basis": "MIN_FREE_GIB set by the operator",
                "written_bytes": int(written), "projection_gb": projection["need_gb"]}
    return {"required_gb": max(0.0, projection["need_gb"] - written / 1e9),
            "basis": "the projection of every output minus the bytes this run's roots already hold",
            "written_bytes": int(written), "projection_gb": projection["need_gb"]}


def check_inputs(args: argparse.Namespace) -> dict[str, Any]:
    from vsmt import lean_assignment as la

    import lean_s1_02a_pilot as generator

    problems: list[str] = []
    repo = Path(args.repo_root).resolve()
    try:
        lists = manifests(repo)
    except Exception as exc:  # noqa: BLE001 - recorded, never fatal before the report is written
        problems.append(f"manifests:{exc}")
        lists = {split: [] for split in SPLITS}
    registry = {row["asset_id"]: row for row in load_json(repo / "configs" / "vsmt" / "lean_s1_assets_capacity_v2.json")["asset_registry"]}
    source = Path(args.source)
    pinned = registry["procthor_10k_dataset"]
    source_entry: dict[str, Any] = {"file": str(source), "registered_sha256": pinned["sha256"], "registered_bytes": pinned["bytes"]}
    if not source.is_file():
        problems.append(f"source_missing:{source}")
    else:
        source_entry.update(sha256=sha256_file(source), bytes=source.stat().st_size)
        if (source_entry["sha256"], source_entry["bytes"]) != (pinned["sha256"], pinned["bytes"]):
            problems.append("source_differs_from_the_registry")
    salt = Path(args.salt_file).resolve()
    salt_entry: dict[str, Any] = {"file": str(salt), "required_sha256": generator.S3_SALT_SHA256}
    if not salt.is_file():
        problems.append(f"salt_missing:{salt}")
    elif repo in salt.parents:
        problems.append("salt_inside_the_repository")
    else:
        salt_entry["sha256"] = sha256_file_text(salt)
        if salt_entry["sha256"] != generator.S3_SALT_SHA256:
            problems.append("salt_is_not_the_s1_salt")
    assets_entry: dict[str, Any] = {"file": args.assets_json}
    try:
        import lean_s1_03_cache as cache_runner

        assets_entry["verified"] = cache_runner.verify_assets(load_json(Path(args.assets_json)), load_json(S1_03_CONTRACT))
    except Exception as exc:  # noqa: BLE001
        problems.append(f"frontend_assets:{exc}"[:300])
    heads = {}
    for mask_source, path in ((SAM2, Path(args.sam2_reid)), (INSTANCE, Path(args.instance_reid))):
        entry: dict[str, Any] = {"file": str(path), "pinned_sha256": la.reid_weights_sha256_for(mask_source)}
        if not path.is_file():
            problems.append(f"reid_head_missing:{mask_source}")
        else:
            payload = load_json(path)
            entry.update(file_sha256=sha256_file(path), payload_sha256=payload.get("sha256"))
            entry["matches"] = payload.get("sha256") == entry["pinned_sha256"] and payload_digest_ok(payload)
            if not entry["matches"]:
                problems.append(f"reid_head_digest_differs:{mask_source}")
        heads[mask_source] = entry
    simulator: dict[str, Any] = {"python": args.sim_python}
    try:
        done = subprocess.run([args.sim_python, "-c", "import ai2thor, sys; print(ai2thor.__version__, sys.version.split()[0])"],
                              capture_output=True, text=True, timeout=300)
        simulator["ai2thor_and_python"] = done.stdout.strip()
        if done.returncode != 0:
            problems.append("simulator_python_cannot_import_ai2thor")
    except (OSError, subprocess.TimeoutExpired) as exc:
        problems.append(f"simulator_python:{exc!r}"[:200])
    gpus = gpu_list()
    if not gpus:
        problems.append("no_gpu_visible")
    projection = disk_projection(repo, houses=sum(len(v) for v in lists.values()))
    autodl = Path(args.autodl_root)
    free = free_gb(autodl) if autodl.exists() else 0.0
    roots = run_roots(args.run_roots)
    requirement = disk_requirement(projection, written=written_bytes(roots), min_free_gib=args.min_free_gib)
    need = requirement["required_gb"]
    if free < need:
        problems.append(f"disk: {free:.0f} GB free under {autodl}, {need:.0f} GB needed (projection {projection['need_gb']} GB, "
                        f"{requirement['written_bytes'] / 1e9:.0f} GB already written by this run; expand the data disk or set "
                        "MIN_FREE_GIB with a reason)")
    if git("status", "--porcelain", cwd=repo):
        problems.append("the worktree is not clean")
    policy = load_json(S1_03_CONTRACT)["public_pose_correction"]
    return {"problems": problems, "manifests": {split: {"houses": len(v), "first": v[:1]} for split, v in lists.items()},
            "source": source_entry, "salt": salt_entry, "frontend_assets": assets_entry, "reid_heads": heads,
            "simulator": simulator, "gpus": gpus, "disk": {"free_gb": round(free, 1), "required_gb": round(need, 1),
                                                           "projection": projection, "override_gib": args.min_free_gib,
                                                           "written_bytes": requirement["written_bytes"], "run_roots": roots,
                                                           "basis": requirement["basis"]},
            "pose_registry": list(policy["correct_encoder_since_code_commits"])}


def sha256_file_text(path: Path) -> str:
    """The salt's digest by the generator's rule: sha256 of the stripped text (``_read_private_salt``)."""

    return hashlib.sha256(Path(path).read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()


def gpu_list() -> list[dict[str, Any]]:
    try:
        text = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    out = []
    for line in text.strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3 and parts[0].isdigit():
            out.append({"index": int(parts[0]), "name": parts[1], "memory_total_mib": float(parts[2])})
    return out


def cmd_check(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    result = check_inputs(args)
    report = {"stage": STAGE, "step": "check", "checked_utc": utc_now(), "code_commit": git("rev-parse", "HEAD", cwd=Path(args.repo_root)),
              "run_root": str(run_root), "resources": resources(), "environment": environment(), **result}
    write_json(run_root / "inputs.json", report)
    print(f"[s3-02-check] manifests {[result['manifests'][s]['houses'] for s in SPLITS]}, {len(result['gpus'])} GPUs, "
          f"disk {result['disk']['free_gb']} GB free / {result['disk']['required_gb']} GB needed; problems: {result['problems'] or 'none'}")
    return 0 if not result["problems"] else 3


def cmd_disk(args: argparse.Namespace) -> int:
    measure = load_json(Path(args.measure_root) / "measure_receipt.json")
    measured = max(row["bytes_written"] for row in measure["per_house"]) / 1e9
    projection = disk_projection(Path(args.repo_root), houses=args.houses, raw_gb_per_house=measured)
    free = free_gb(Path(args.autodl_root))
    roots = run_roots(args.run_roots)
    requirement = disk_requirement(projection, written=written_bytes(roots), min_free_gib=args.min_free_gib)
    need = requirement["required_gb"]
    out = {"stage": STAGE, "step": "disk", "checked_utc": utc_now(), "free_gb": round(free, 1), "required_gb": round(need, 1),
           "projection": projection, "override_gib": args.min_free_gib, "written_bytes": requirement["written_bytes"],
           "run_roots": roots, "basis": requirement["basis"], "enough": free >= need}
    write_json(Path(args.run_root) / "disk.json", out)
    print(f"[s3-02-disk] {free:.0f} GB free, {need:.0f} GB needed (raw {projection['raw_gb_per_house']:.3f} GB per house measured "
          f"{measured:.3f}; {requirement['written_bytes'] / 1e9:.1f} GB already written): {'ok' if out['enough'] else 'NOT ENOUGH'}")
    return 0 if out["enough"] else 3


# --------------------------------------------------------------------------
# stage markers
# --------------------------------------------------------------------------

def marker_path(run_root: Path, stage: str) -> Path:
    if stage not in STAGES:
        raise SystemExit(f"unknown stage {stage}")
    return Path(run_root) / "stages" / f"{stage}.json"


def allowed_change(path: str) -> bool:
    return path in REGISTRATION_FILES or path in DOCUMENT_FILES or path.startswith(DOCUMENT_PREFIXES)


def stage_state(run_root: Path, stage: str, head: str, repo: Path, accept_code_change: bool) -> tuple[str, str]:
    """('done' | 'todo' | 'blocked', reason) for one stage at the current commit."""

    path = marker_path(run_root, stage)
    if not path.exists():
        return "todo", "no marker"
    marker = load_json(path)
    if marker.get("status") != "done":
        return "todo", f"marker status {marker.get('status')}"
    if marker.get("commit") == head:
        return "done", "same commit"
    if stage == "check":
        return "todo", "a new commit is checked again"
    changes = [line for line in git("diff", "--name-only", marker["commit"], head, cwd=repo).splitlines() if line]
    outside = [p for p in changes if not allowed_change(p)]
    if not outside:
        return "done", f"commit changed only registration/document files: {changes}"
    if accept_code_change:
        return "done", f"code changed since {marker['commit'][:12]} and ACCEPT_CODE_CHANGE=1: {outside}"
    return "blocked", f"code changed since the stage ran at {marker['commit'][:12]}: {outside}"


def cmd_stage_state(args: argparse.Namespace) -> int:
    head = git("rev-parse", "HEAD", cwd=Path(args.repo_root))
    state, reason = stage_state(Path(args.run_root), args.stage, head, Path(args.repo_root), args.accept_code_change)
    print(f"{state}\t{reason}")
    return {"done": 0, "todo": 1, "blocked": 2}[state]


def cmd_mark(args: argparse.Namespace) -> int:
    commit = git("rev-parse", "HEAD", cwd=Path(args.repo_root))
    path = marker_path(Path(args.run_root), args.stage)
    history = []
    if path.exists():
        previous = load_json(path)
        history = previous.get("history", []) + [{k: previous.get(k) for k in ("status", "commit", "exit", "finished_utc", "detail")}]
    write_json(path, {"stage": args.stage, "status": args.status, "commit": commit, "exit": args.exit, "started_utc": args.started,
                      "finished_utc": utc_now(), "detail": args.detail, "accept_code_change": bool(args.accept_code_change),
                      "history": history})
    print(f"[s3-02] stage {args.stage}: {args.status} (exit {args.exit}) at {commit[:12]}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    for stage in STAGES:
        path = marker_path(Path(args.run_root), stage)
        if path.exists():
            marker = load_json(path)
            print(f"{stage:15s} {marker['status']:8s} {marker['commit'][:12]} exit {marker['exit']} {marker['finished_utc']} {marker.get('detail') or ''}")
        else:
            print(f"{stage:15s} -")
    return 0


# --------------------------------------------------------------------------
# the checks between stages
# --------------------------------------------------------------------------

def move_check(raw_root: Path) -> dict[str, Any]:
    receipt = load_json(Path(raw_root) / "train" / "s3_receipt.json")
    return {"stage": STAGE, "step": "movecheck", "checked_utc": utc_now(), "rule": "ruling 36: train moves >= 120 and source-first >= 60",
            "move_minimum": receipt["move_minimum"], "houses_planned": receipt["houses_planned"], "succeeded": receipt["succeeded"],
            "below_minimum": bool(receipt["move_minimum"]["below_minimum"])}


def cmd_movecheck(args: argparse.Namespace) -> int:
    path = Path(args.raw_root) / "train" / "s3_receipt.json"
    if not path.exists():
        print(f"[s3-02-movecheck] no train receipt at {path}")
        return 3
    out = move_check(Path(args.raw_root))
    write_json(Path(args.run_root) / "movecheck.json", out)
    minimum = out["move_minimum"]
    print(f"[s3-02-movecheck] train moves {minimum['moves']} (>= {minimum['minimum_train']}), source-first {minimum['moves_source_first']} "
          f"(>= {minimum['minimum_train_source_first']}): {'BELOW, stop for a scale ruling' if out['below_minimum'] else 'met'}")
    return 4 if out["below_minimum"] else 0


def encoder_source(commit: str, repo: Path) -> str:
    """The generator's camera_pose function at one commit (the encoder the pose registry is about)."""

    text = subprocess.check_output(["git", "show", f"{commit}:{GENERATOR}"], cwd=str(repo)).decode("utf-8")
    start = text.index("\ndef camera_pose(")
    end = text.index("\ndef ", start + 1)
    return text[start:end].strip()


def hold_report(raw_root: Path, repo: Path) -> dict[str, Any]:
    """Ruling 103-3: are the raw receipts' generator commits registered, and is each one's encoder the registered one?"""

    policy = load_json(S1_03_CONTRACT)["public_pose_correction"]
    registered = list(policy["correct_encoder_since_code_commits"])
    commits = sorted({str(r.get("code_commit")) for split in SPLITS for r in receipts(Path(raw_root) / split).values()})
    reference = registered[-1]
    reference_source = encoder_source(reference, repo)
    rows = {}
    for commit in commits:
        try:
            source = encoder_source(commit, repo)
        except (subprocess.CalledProcessError, ValueError) as exc:
            rows[commit] = {"registered": commit in registered, "encoder_readable": False, "detail": repr(exc)[:200]}
            continue
        rows[commit] = {"registered": commit in registered, "encoder_readable": True,
                        "encoder_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                        "encoder_equals_registered": source == reference_source}
    unregistered = [c for c in commits if not rows[c]["registered"]]
    changed = [c for c in unregistered if not rows[c].get("encoder_equals_registered")]
    return {"stage": STAGE, "step": "hold", "checked_utc": utc_now(), "generator_commits": rows, "registered": registered,
            "reference_commit": reference, "unregistered": unregistered, "encoder_changed": changed,
            "rule": ("ruling 103-3: the generator commit joins public_pose_correction.correct_encoder_since_code_commits by a commit that "
                     "changes only the S1-03 contract and its two pinning tests (as 2339baa -> 6b65cb1), pre-authorised; a commit whose "
                     "camera_pose encoder differs from the registered one cannot be registered this way")}


def cmd_hold(args: argparse.Namespace) -> int:
    report = hold_report(Path(args.raw_root), Path(args.repo_root))
    write_json(Path(args.run_root) / "hold.json", report)
    if not report["generator_commits"]:
        print("[s3-02-hold] no raw receipts")
        return 3
    if report["encoder_changed"]:
        print(f"[s3-02-hold] the camera_pose encoder of {report['encoder_changed']} differs from {report['reference_commit'][:12]}: stop")
        return 11
    if report["unregistered"]:
        print(f"[s3-02-hold] register {report['unregistered']} in the S1-03 pose registry (ruling 103-3), commit, then run 'all'")
        return 10
    print(f"[s3-02-hold] every generator commit is registered: {sorted(report['generator_commits'])}")
    return 0


def geometry_problems(root: Path, raw_root: Path) -> list[str]:
    if not (Path(root) / "s1_04_geometry_receipt.json").exists():
        return [f"no_stage_receipt:{root}"]
    raw, built = receipts(raw_root), receipts(root)
    problems = []
    for episode, source in sorted(raw.items()):
        row = built.get(episode)
        if row is None:
            problems.append(f"geometry_missing:{episode}")
        elif source.get("status") == "succeeded" and row.get("status") != "succeeded":
            problems.append(f"geometry_failed:{episode}:{row.get('reason')}")
        elif source.get("status") != "succeeded" and row.get("reason") != "source_episode_not_succeeded":
            problems.append(f"geometry_unexpected:{episode}:{row.get('reason')}")
    return problems


def cache_problems(root: Path, raw_root: Path, mask_source: str) -> list[str]:
    from vsmt import lean_frontend_cache as fc

    stage = Path(root) / "s1_03_receipt.json"
    if not stage.exists():
        return [f"no_complete_stage_receipt:{root}"]
    receipt = load_json(stage)
    problems = []
    if not receipt.get("complete") or receipt.get("mask_source") != mask_source:
        problems.append(f"stage_receipt_incomplete_or_other_source:{root}")
    cached = receipts(root)
    for episode in succeeded(raw_root):
        row = cached.get(episode)
        if row is None:
            problems.append(f"cache_missing:{episode}")
        elif row.get("status") == "failed" and row.get("reason") not in CACHE_DATA_FAILURES:
            problems.append(f"cache_failed_not_by_the_data:{episode}:{row.get('reason')}")
        elif row.get("status") not in ("succeeded", "failed"):
            problems.append(f"cache_not_final:{episode}:{row.get('status')}")
        elif row.get("status") == "succeeded":
            seal = Path(root) / episode / "episode_seal.json"
            if not seal.exists() or fc.sealed_mask_source(load_json(seal)) != mask_source:
                problems.append(f"cache_sealed_with_another_source:{episode}")
    return problems


def cmd_geometry_ok(args: argparse.Namespace) -> int:
    problems = geometry_problems(Path(args.root), Path(args.raw_root))
    print(f"[s3-02-geometry] {args.root}: {problems[:5] or 'ok'}{' ...' if len(problems) > 5 else ''}")
    return 0 if not problems else 3


def cmd_cache_ok(args: argparse.Namespace) -> int:
    problems = cache_problems(Path(args.root), Path(args.raw_root), args.mask_source)
    if not args.quiet or not problems:
        print(f"[s3-02-cache] {args.root}: {problems[:5] or 'ok'}{' ...' if len(problems) > 5 else ''}")
    return 0 if not problems else 3


# --------------------------------------------------------------------------
# workers
# --------------------------------------------------------------------------

def instance_cache_workers(cpu_quota: int, memory_bytes: int) -> dict[str, Any]:
    """Two threads per worker up to the CPU quota, and the memory the measured peak RSS allows (1.25 x, a reserve kept)."""

    by_cpu = max(1, cpu_quota // CACHE_THREADS)
    by_memory = max(1, int((memory_bytes / 2 ** 30 - MEMORY_RESERVE_GIB) // (1.25 * INSTANCE_RSS_GIB)))
    return {"workers": min(by_cpu, by_memory), "threads": CACHE_THREADS, "by_cpu": by_cpu, "by_memory": by_memory,
            "basis": ("8ebbd05 measured the instance cache CPU-bound at two threads per worker (8 x 2 = its 16-CPU quota), 1,369 MiB peak "
                      "RSS and 496 MiB VRAM per worker; the same rule on this host: workers = min(quota / 2, (memory - 8 GiB) / "
                      "(1.25 x 1.34 GiB)), spread over every card")}


def cmd_workers(args: argparse.Namespace) -> int:
    info = resources()
    plan = instance_cache_workers(int(args.cpu_quota or info["cpu_quota"]), int(args.memory_bytes or info["memory_bytes"]))
    gpus = [str(row["index"]) for row in gpu_list()] or ["0"]
    plan.update({"gpus": gpus, "geometry_workers": GEOMETRY_WORKERS, "cpu_quota": info["cpu_quota"], "memory_bytes": info["memory_bytes"]})
    if args.workers:
        plan["workers"] = int(args.workers)
        plan["override"] = "INSTANCE_WORKERS set by the operator"
    path = Path(args.run_root) / "workers.json"
    previous = load_json(path) if path.exists() else {}
    write_json(path, {**previous, "instance_cache": plan})
    print(f"{plan['workers']} {','.join(gpus)}")
    return 0


def trial_rate(trial_root: Path) -> dict[str, Any]:
    """Frames per second of one SAM2 trial: summed over its concurrent workers from their processing time, and from the wall.

    Failed episodes are listed with their reason and the frames they processed; a failure the data causes (``CACHE_DATA_FAILURES``,
    e.g. a SAM2 frame with more proposals than the cap) is told apart from any other (e.g. CUDA out of memory with too many workers).
    """

    named = receipts(trial_root)
    rows = list(named.values())
    stage = load_json(trial_root / "trial_receipt.json")
    frames = sum(int(r.get("frames_processed") or 0) for r in rows)
    processing = sum(int(r.get("frames_processed") or 0) / sum((r.get("seconds_by_part") or {}).values())
                     for r in rows if sum((r.get("seconds_by_part") or {}).values()) > 0)
    failed = [{"episode": name, "reason": r.get("reason"), "frames_processed": int(r.get("frames_processed") or 0)}
              for name, r in sorted(named.items()) if r.get("status") != "succeeded"]
    data = sum(1 for f in failed if f["reason"] in CACHE_DATA_FAILURES)
    return {"episodes": len(rows), "succeeded": len(rows) - len(failed), "frames": frames,
            "frames_per_second": round(processing, 4), "frames_per_second_wall": round(frames / max(stage["wall_clock_seconds"], 1e-6), 4),
            "wall_seconds": stage["wall_clock_seconds"], "peak_vram_reserved_mib": stage.get("peak_vram_reserved_mib_max"),
            "failed": failed, "data_failures": data, "other_failures": len(failed) - data}


def choose_sam2_workers(rates: Mapping[int, Mapping[str, Any]]) -> int:
    """The per-card worker count with the highest processing rate among usable trials (fewer workers on a tie).

    A trial (k workers on one card, each over the first 60 frames of one large episode) is usable if it has exactly k episodes,
    processed frames, and any failed episode failed for a data reason -- e.g. a frame of the largest house with more fragments
    than the cap says something about the data, not about k workers, so throughput is taken from the processed frames and the
    failure listed; a trial that failed for another reason (e.g. GPU memory) is not usable. Only when no trial is usable does
    the stage stop. It decides the workers per card only and changes no cache content.
    """

    usable = {k: r for k, r in rates.items()
              if r["episodes"] == k and int(r.get("frames") or 0) > 0 and int(r.get("other_failures") or 0) == 0}
    if not usable:
        raise SystemExit("no SAM2 trial is usable: each one failed for a reason other than the data, or processed no frame")
    return max(sorted(usable), key=lambda k: (usable[k]["frames_per_second"], -k))


def trial_finished(trial_root: Path, exit_code: int) -> tuple[bool, str]:
    """Did one SAM2 trial run to its end?  The cache builder exits 1 when any episode failed, data failures included.

    Exit 0, or exit 1 with the trial receipt written (the failed episodes are judged by ``choose_sam2_workers``), is a finished
    trial; any other exit (an abort or an interruption) or a missing trial receipt is not.
    """

    if exit_code not in (0, 1):
        return False, f"exit {exit_code}: the trial was aborted or interrupted"
    if not (Path(trial_root) / "trial_receipt.json").is_file():
        return False, f"exit {exit_code} without a trial receipt: the cache builder stopped before the end"
    return True, "finished" if exit_code == 0 else "finished with failed episodes (judged by the worker choice)"


def cmd_trial_ok(args: argparse.Namespace) -> int:
    finished, reason = trial_finished(Path(args.root), int(args.exit))
    print(f"[s3-02-sam2-trial] {args.root}: {reason}")
    return 0 if finished else 3


def cmd_sam2_measure(args: argparse.Namespace) -> int:
    rates = {}
    for spec in args.trial:
        k, path = spec.split("=", 1)
        rates[int(k)] = {**trial_rate(Path(path)), "root": path}
    best = choose_sam2_workers(rates)
    gpus = [g for g in args.gpus.split(",") if g]
    frames = sum(int(receipts(Path(args.raw_root) / split)[e].get("observations") or 0)
                 for split in SPLITS for e in succeeded(Path(args.raw_root) / split))
    rate = rates[best]["frames_per_second"] * len(gpus)
    out = {"stage": STAGE, "step": "sam2-measure", "measured_utc": utc_now(), "trials": rates, "workers_per_card": best,
           "gpus": gpus, "workers": best * len(gpus), "frames_to_cache": frames, "frames_per_second_all_cards": round(rate, 3),
           "projected_hours": round(frames / max(rate, 1e-9) / 3600.0, 1),
           "rule": ("ruling 84-4: the per-card worker count with the highest processing rate on one card, times the cards; a trial "
                    "whose failed episodes all failed for a data reason counts (its failures are listed), any other failure "
                    "drops that trial"),
           "note": "trials process the first frames of the largest train episodes; the run continues after this measurement"}
    write_json(Path(args.run_root) / "sam2_measure.json", out)
    print(f"{out['workers']} {out['workers_per_card']} {out['projected_hours']}")
    return 0


# --------------------------------------------------------------------------
# the test seal and the counts-only test summary
# --------------------------------------------------------------------------

def cmd_seal_pending(args: argparse.Namespace) -> int:
    root = Path(args.root)
    marker = root / ts.MARKER_NAME
    if marker.exists() and load_json(marker).get("state") == ts.STATE_SEALED:
        print(f"[s3-02-seal] {root} is already sealed")
        return 0
    ts.write_marker(root, kind=args.kind, state=ts.STATE_PENDING)
    print(f"[s3-02-seal] {root}: pending marker")
    return 0


def test_summary(raw: Path, geometry: Path, instance: Path, sam2: Path) -> dict[str, Any]:
    """Counts only (ruling 103-1): no house id, no per-house row, nothing a method could be tuned on."""

    def reasons(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in rows.values():
            if row.get("status") != "succeeded":
                out[str(row.get("reason"))] = out.get(str(row.get("reason")), 0) + 1
        return dict(sorted(out.items()))

    stage = load_json(raw / "s3_receipt.json")
    out = {"raw": {k: stage[k] for k in ("houses_planned", "succeeded", "failed", "failures_by_reason", "null_window_episodes",
                                         "null_window_failed", "yield_house_level_non_null", "moves_executed", "moves_source_first",
                                         "controls_total", "controls_outside_U", "actual_workers")}}
    geometry_rows = receipts(geometry)
    out["geometry"] = {"episodes": len(geometry_rows), "succeeded": sum(1 for r in geometry_rows.values() if r.get("status") == "succeeded"),
                       "failures_by_reason": reasons(geometry_rows)}
    for name, root in (("instance_cache", instance), ("sam2_cache", sam2)):
        receipt = load_json(root / "s1_03_receipt.json")
        out[name] = {k: receipt.get(k) for k in ("episodes_planned", "episodes_succeeded", "episodes_failed", "frames_total",
                                                 "fragments_total", "bytes_written_total", "wall_clock_seconds", "actual_workers",
                                                 "mask_source", "complete")}
        out[name]["failures_by_reason"] = reasons(receipts(root))
    return {"stage": STAGE, "step": "test-summary", "written_utc": utc_now(), "rule": ts.RULE, "counts_only": True, **out}


def cmd_test_summary(args: argparse.Namespace) -> int:
    write_json(Path(args.out), test_summary(Path(args.raw), Path(args.geometry), Path(args.instance_cache), Path(args.sam2_cache)))
    print(f"[s3-02-test-summary] {args.out}")
    return 0


def test_roots(args: argparse.Namespace) -> dict[str, Path]:
    return {"raw": Path(args.raw), "geometry": Path(args.geometry), "instance_cache": Path(args.instance_cache),
            "sam2_cache": Path(args.sam2_cache)}


def cmd_seal(args: argparse.Namespace) -> int:
    seal, digest = ts.seal_roots(test_roots(args), houses=manifests(Path(args.repo_root))["test"], tag=args.tag)
    write_json(Path(args.out), {**seal, "seal_sha256": digest})
    print(f"[s3-02-seal] test sealed: {seal['counts']} -> {digest[:16]}")
    return 0


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def repeat_check(measure_root: Path, train_root: Path) -> dict[str, Any]:
    """The four measured houses against their train copies: the same house generated twice by the same commit (recorded only)."""

    rows = {}
    keys = ("status", "reason", "observations", "actions", "null_window", "executed_interventions", "sampled_interventions",
            "feasible_set_size", "invisible_container_set_size", "window_frames", "moves_executed", "moves_source_first", "controls")
    for house, first in sorted(receipts(measure_root).items()):
        second_path = Path(train_root) / house / "receipt.json"
        if not second_path.exists():
            rows[house] = {"train_copy": False}
            continue
        second = load_json(second_path)
        row: dict[str, Any] = {"train_copy": True, "receipt_fields_equal": {k: first.get(k) == second.get(k) for k in keys}}
        for plane in ("public", "private", "provenance"):
            a, b = Path(measure_root) / house / plane, Path(train_root) / house / plane
            if a.is_dir() and b.is_dir():
                row[f"{plane}_identical"] = ts.tree_digest(a)["sha256"] == ts.tree_digest(b)["sha256"]
        rows[house] = row
    return {"houses": rows, "all_identical": bool(rows) and all(
        r.get("train_copy") and all(r["receipt_fields_equal"].values()) and all(v for k, v in r.items() if k.endswith("_identical"))
        for r in rows.values()),
            "role": "a determinism record of the generator, not a gate"}


def verify(args: argparse.Namespace) -> dict[str, Any]:
    run_root, export_dir = Path(args.run_root), Path(args.export_dir)
    problems: list[str] = []
    stages = {stage: (load_json(marker_path(run_root, stage)) if marker_path(run_root, stage).exists() else None) for stage in STAGES}
    for stage in STAGES[:-1]:
        if not stages[stage] or stages[stage]["status"] != "done":
            problems.append(f"stage_not_done:{stage}")
    lists = manifests(Path(args.repo_root))
    raw, geometry = Path(args.raw), Path(args.geometry)
    caches = {INSTANCE: Path(args.instance_cache), SAM2: Path(args.sam2_cache)}
    splits = {}
    for split in SPLITS:
        attempted = sorted(receipts(raw / split))
        if attempted != sorted(lists[split]):
            problems.append(f"raw_houses_differ_from_the_manifest:{split}")
        problems += [f"{split}:{p}" for p in geometry_problems(geometry / split, raw / split)]
        for source, root in caches.items():
            problems += [f"{split}:{source}:{p}" for p in cache_problems(root / split, raw / split, source)]
        splits[split] = {"houses": len(lists[split]), "attempted": len(attempted), "raw_succeeded": len(succeeded(raw / split)),
                         "geometry_succeeded": len(succeeded(geometry / split)),
                         **{f"cache_succeeded_{source}": len(succeeded(root / split)) for source, root in caches.items()}}
    seal_path = run_root / "test_seal.json"
    seal_problems = ["seal_missing"]
    if seal_path.exists():
        seal = load_json(seal_path)
        seal_problems = ts.verify_seal({k: v for k, v in seal.items() if k != "seal_sha256"})
        if ts.seal_sha256({k: v for k, v in seal.items() if k != "seal_sha256"}) != seal.get("seal_sha256"):
            seal_problems.append("seal_file_digest_differs")
    problems += [f"test_seal:{p}" for p in seal_problems]
    for split in ("train", "validation"):  # test roots must stay sealed; the others must not carry a marker
        for root in (raw / split, geometry / split, *(c / split for c in caches.values())):
            if ts.sealed_marker(root) is not None:
                problems.append(f"marker_on_a_non_test_root:{root}")
    exports = sorted(p for p in export_dir.glob(f"*_{args.tag}.json")
                     if not p.name.startswith(("vsmt_lean_s3_02_manifest_", "vsmt_lean_s3_02_verify_")) and not p.name.endswith(".status.json"))
    files = {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in exports}
    movecheck = load_json(run_root / "movecheck.json") if (run_root / "movecheck.json").exists() else None
    if not movecheck or movecheck["below_minimum"]:
        problems.append("ruling_36_move_minimum_not_met_or_not_checked")
    return {"problems": problems, "stages": stages, "splits": splits, "test_seal_problems": seal_problems, "exports": files,
            "movecheck": movecheck, "generator_repeat": repeat_check(raw / "measure", raw / "train")}


def cmd_verify(args: argparse.Namespace) -> int:
    result = verify(args)
    run_root, export_dir = Path(args.run_root), Path(args.export_dir)
    manifest = {"stage": STAGE, "step": "manifest", "tag": args.tag, "written_utc": utc_now(),
                "code_commit": git("rev-parse", "HEAD", cwd=Path(args.repo_root)),
                "stage_commits": {stage: (marker or {}).get("commit") for stage, marker in result["stages"].items()},
                "inputs": load_json(run_root / "inputs.json") if (run_root / "inputs.json").exists() else None,
                "workers": load_json(run_root / "workers.json") if (run_root / "workers.json").exists() else None,
                "roots": {"raw": args.raw, "geometry": args.geometry, "instance_cache": args.instance_cache, "sam2_cache": args.sam2_cache},
                "splits": result["splits"], "exports": result["exports"], "movecheck": result["movecheck"],
                "generator_repeat": result["generator_repeat"], "test_seal_problems": result["test_seal_problems"],
                "problems": result["problems"],
                "reproduction": ("bash ops/vsmt/s3_02_data.sh all at the recorded commits regenerates every root; whether the generator "
                                 "repeats a house byte for byte is recorded in generator_repeat (four houses), the caches are expected to "
                                 "repeat per episode on the same card model but were not compared; README 'How to reproduce S3-02'")}
    write_json(export_dir / f"vsmt_lean_s3_02_manifest_{args.tag}.json", manifest)
    write_json(export_dir / f"vsmt_lean_s3_02_verify_{args.tag}.json",
               {"stage": STAGE, "step": "verify", "problems": result["problems"], "exports_checked": len(result["exports"]),
                "splits": result["splits"], "generator_repeat_all_identical": result["generator_repeat"]["all_identical"],
                "manifest_sha256": sha256_file(export_dir / f"vsmt_lean_s3_02_manifest_{args.tag}.json")})
    print(f"[s3-02-verify] splits {result['splits']}; generator repeat identical: {result['generator_repeat']['all_identical']}; "
          f"problems: {result['problems'] or 'none'}")
    return 0 if not result["problems"] else 3


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name: str, func, *required: str, repo: bool = False, run: bool = True) -> argparse.ArgumentParser:
        p = sub.add_parser(name)
        if run:
            p.add_argument("--run-root", required=True)
        if repo:
            p.add_argument("--repo-root", default=str(ROOT))
        for option in required:
            p.add_argument(f"--{option}", required=True)
        p.set_defaults(func=func)
        return p

    p = command("check", cmd_check, "autodl-root", "source", "salt-file", "assets-json", "sam2-reid", "instance-reid", "sim-python", repo=True)
    p.add_argument("--min-free-gib", type=float, default=None)
    p.add_argument("--run-roots", default="", help="comma-separated roots this run writes the projected outputs into; their bytes "
                                                   "are subtracted from the projection")
    p = command("disk", cmd_disk, "autodl-root", "measure-root", repo=True)
    p.add_argument("--houses", type=int, default=450)
    p.add_argument("--min-free-gib", type=float, default=None)
    p.add_argument("--run-roots", default="", help="as for check")
    for name, func in (("stage-state", cmd_stage_state), ("mark", cmd_mark)):
        p = command(name, func, "stage", repo=True)
        p.add_argument("--accept-code-change", action="store_true")
        if name == "mark":
            p.add_argument("--status", required=True, choices=STATUSES)
            p.add_argument("--exit", type=int, required=True)
            p.add_argument("--started", required=True)
            p.add_argument("--detail", default="")
    command("status", cmd_status)
    command("movecheck", cmd_movecheck, "raw-root")
    command("hold", cmd_hold, "raw-root", repo=True)
    command("geometry-ok", cmd_geometry_ok, "root", "raw-root", run=False)
    p = command("cache-ok", cmd_cache_ok, "root", "raw-root", run=False)
    p.add_argument("--mask-source", required=True, choices=(INSTANCE, SAM2))
    p.add_argument("--quiet", action="store_true")
    p = command("workers", cmd_workers)
    for option in ("workers", "cpu-quota", "memory-bytes"):
        p.add_argument(f"--{option}", default=None)
    p = command("sam2-measure", cmd_sam2_measure, "raw-root", "gpus")
    p.add_argument("--trial", action="append", required=True, help="k=<trial root>")
    p = command("trial-ok", cmd_trial_ok, "root", run=False)
    p.add_argument("--exit", type=int, required=True, help="the cache builder's exit code for this trial")
    p = command("seal-pending", cmd_seal_pending, "root", run=False)
    p.add_argument("--kind", required=True, choices=ts.SEAL_KINDS)
    command("test-summary", cmd_test_summary, "raw", "geometry", "instance-cache", "sam2-cache", "out", run=False)
    command("seal", cmd_seal, "raw", "geometry", "instance-cache", "sam2-cache", "tag", "out", repo=True, run=False)
    command("verify", cmd_verify, "export-dir", "tag", "raw", "geometry", "instance-cache", "sam2-cache", repo=True)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
