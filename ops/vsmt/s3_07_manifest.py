#!/usr/bin/env python3
"""S3-07 (ruling 111, 2026-10-07): the external validation on 3RScan -- the steps of ``ops/vsmt/s3_07_external.sh``.

S3-07 runs the arms, configurations and weights pinned by the S3-04 freeze receipt, unchanged, on the converted 3RScan
validation episodes; reported only, no gate. Two phases on two kinds of host:
  * GPU phase (an RTX 5090 host as in S3-02): ``check`` (E1 code-difference allow list, receipt committed, converter
    commit registered in the pose registry, cache generator reads ``3rscan-*`` directories, contract's formal bit open
    and four sample slots registered) -> ``render`` (annotated-mesh rendering) -> ``convert`` (three-plane episodes and
    geometry tables) -> ``reader-check`` (read back through the frozen readers) -> ``cache`` (S1-03 caches of both front
    ends; construction failures recorded with the frozen reason codes) -> ``e2`` (the two smallest S3-02 train
    episodes' caches rebuilt at this commit, seals equal to the committed S3-02 exports) -> ``handoff`` (tree digests of
    every root and the usable episodes);
  * audit phase (B1 and admitted workers): ``check`` -> ``receive`` (copied roots equal the hand-over digests) ->
    ``inputs`` (run inputs: roots, ReID heads, usable episodes per front end) -> ``e3`` (the receipt's G4 probe audits on
    ``probe_episodes`` rerun at this commit, byte for byte against S3-03; workers admitted with ``remote_hosts.py admit
    --kinds audit --reference-run-root <S3-03 run root>``) -> ``run`` (job pool: one job per test run of the receipt and
    episode; node audit metrics only, without ``--manifest-split``; a crash is rerun once with the same inputs, a second
    failure is a data failure; exit code 2 is a refusal and stops the run) -> ``merge`` -> ``stats`` (``lean_s3_07``:
    pooled by scene, reported only) -> ``export``.
Inputs: the freeze receipt, the S3-03 run root (weights and ReID heads) and the 3RScan conversion outputs; outputs: each
front end's external-validation table, comparison intervals, failure and not-applicable lists. Example: a file in
``src/`` changed after the receipt and outside the allow list stops ``check`` with exit code 3; an episode whose SAM 2.1
cache fails with ``proposal_overflow`` leaves that front end's usable list and enters the failure list, and is not
replaced. It selects nothing, trains nothing, reads no test data, is not part of the gate and changes no frozen
function.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_03_jobs as pool  # noqa: E402
import s3_03_manifest as s303  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_public_pose as pp  # noqa: E402
from vsmt import lean_s3_04 as s4  # noqa: E402
from vsmt import lean_s3_07 as s7  # noqa: E402
from vsmt import lean_s3_07_3rscan as r3  # noqa: E402
from vsmt import lean_test_seal  # noqa: E402

STAGE = "vsmt.lean.s3_07.driver.v1"
NODE_AUDIT = HERE.parent / "lean_s2_05_node_audit.py"
CACHE_ENTRY = HERE.parent / "lean_s1_03_cache.py"
RENDER_ENTRY = HERE.parent / "s3_07_render.py"
CONVERT_ENTRY = HERE.parent / "s3_07_convert.py"
REMOTE_SCRIPT = HERE.parent / "remote_hosts.py"
JOBS_SCRIPT = HERE.parent / "s3_03_jobs.py"
S0_05_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json"
S1_03_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
FRONTS = dict(s4.FRONTS)
#: E1 (ruling 111-7): code files that may differ from the freeze receipt -- the S3-07 files and the registration commit's edits
ALLOWED_PREFIXES = ("src/vsmt/lean_s3_07", "ops/vsmt/s3_07_", "configs/vsmt/lean_s3_07_")
ALLOWED_FILES = ("configs/vsmt/lean_s1_03_frontend_cache_v1.json", "ops/vsmt/lean_s1_03_cache.py")
#: the S3-02 train episodes E2 regenerates (the two smallest; ruling 111-7) and the committed exports holding their seals
E2_EPISODES = ("procthor10k-0.1.2-train-03642", "procthor10k-0.1.2-train-00946")
E2_EXPORTS = {"instance": "results/vsmt_lean_s3_02_instance_cache_train_3f6ef1d.json", "sam2": "results/vsmt_lean_s3_02_sam2_cache_train_3f6ef1d.json"}
CACHE_DATA_FAILURES = ("proposal_overflow", "duplicate_proposal_mask", "fragment_depth_support_insufficient", "descriptor_not_unit_norm")
MEMORY_GIB = {"audit": 2.0, "small": 0.5}
PRIORITY = {"learned": 2, "rule": 3}
AUDIT_RETRIES = 1
PROBE_GIB = 2.0
#: the 3RScan roots are stored under the split key "validation" because the shared tools (remote_hosts kind "audit") read it
SPLIT_KEY = "validation"
SPLIT_MEANING = "3RScan validation (external data, ruling 111); not the ProcTHOR validation split"
#: the GPU phase's hand-over document (digests, usable episodes); "handoff.json" is the handoff step's own record
HANDOVER_FILE = "handover.json"

load_json = s303.load_json
write_json = s303.write_json
utc_now = s303.utc_now


class DriverError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DriverError(code)


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


#: step records live in their own directory: the pool input inputs.json (read by s3_03_jobs / remote_hosts as the S3-03 and S3-05
#: pools do) and the hand-over handover.json sit at the run root, and a step record must never overwrite them (the "inputs" step
#: record did, on B1 at 589db97: remote_hosts.static_paths then found no "roots")
STEPS_DIR = "steps"


def step_path(run_root: Path, name: str) -> Path:
    return run_root / STEPS_DIR / f"{name}.json"


def finish(run_root: Path, name: str, payload: dict[str, Any]) -> int:
    payload = {"stage": STAGE, "step": name, "code_commit": git("rev-parse", "HEAD"), "written_utc": utc_now(), **payload}
    payload["pass"] = not payload.get("problems")
    target = step_path(run_root, name)
    _require(target.name not in ("inputs.json", "handover.json") or target.parent.name == STEPS_DIR, "step_record_would_overwrite_an_input")
    write_json(target, payload)
    print(f"[s3-07-{name}] pass={payload['pass']}; problems: {payload.get('problems')[:6] if payload.get('problems') else 'none'}")
    return 0 if payload["pass"] else 3


#: paths a registration commit may touch between the converter commit and the cache/audit commit (ruling 111-7: the converter
#: commit is appended to the S1-03 pose policy after the episodes exist, as S3-02 did at 4ad0233); a step passed at the earlier
#: commit stays passed when nothing else changed
REGISTRATION_PATHS = ("configs/vsmt/lean_s1_03_frontend_cache_v1.json", "tests/", "docs/", "results/", "README.md", "EXECUTE.md", "AGENTS.md")


def registration_only_changes(since_commit: str) -> bool:
    """True when every file changed between ``since_commit`` and HEAD is a registration path or an S3-07 file (the driver and
    the converter are not frozen code; what they wrote stays valid while the frozen code is the frozen code -- E1 checks that)."""

    try:
        changed = [name for name in git("diff", "--name-only", since_commit, "HEAD").splitlines() if name]
    except subprocess.CalledProcessError:
        return False
    return all(any(name == path or name.startswith(path) for path in REGISTRATION_PATHS) or code_change_allowed(name)
               for name in changed)


def passed(run_root: Path, name: str) -> bool:
    path = step_path(run_root, name)
    if not path.exists() or not bool(load_json(path).get("pass")):
        return False
    commit = str(load_json(path).get("code_commit") or "")
    return commit == git("rev-parse", "HEAD") or registration_only_changes(commit)


def receipt_of(args: argparse.Namespace) -> dict[str, Any]:
    return load_json(Path(args.receipt))


def tracked_code_files() -> list[str]:
    return [name for name in git("ls-files", *s4.CODE_DIRECTORIES).splitlines() if name]


def episode_receipts(root: Path) -> dict[str, dict[str, Any]]:
    """{episode: receipt} of the ``3rscan-*`` episode directories directly under one root."""

    out = {}
    if Path(root).is_dir():
        for path in sorted(Path(root).glob(f"{r3.EPISODE_PREFIX}*/receipt.json")):
            out[path.parent.name] = load_json(path)
    return out


# --------------------------------------------------------------------------
# E1 and check
# --------------------------------------------------------------------------

def code_change_allowed(path: str) -> bool:
    return path in ALLOWED_FILES or any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def disallowed_code_differences(recorded: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """E1: every file whose digest differs from the freeze receipt, outside the S3-07 files and the registration edits."""

    out = []
    for item in s4.code_differences(recorded, current):
        path = item.split(":", 1)[-1] if ":" in item else item
        if not code_change_allowed(path):
            out.append(item)
    return out


def registration_problems(code_commit: str) -> list[str]:
    """The converter commit must be a registered correct encoder, and the cache generator must find ``3rscan-*`` directories."""

    import lean_s1_03_cache as cache_runner

    problems = []
    policy = load_json(S1_03_CONTRACT)["public_pose_correction"]
    try:
        if pp.correction_applies(code_commit, policy):
            problems.append(f"converter_commit_registered_as_defective:{code_commit[:12]}")
    except pp.LeanPublicPoseError as exc:
        problems.append(f"converter_commit_not_registered:{exc}")
    globs = getattr(cache_runner, "EPISODE_DIRECTORY_GLOBS", ("procthor10k-*",))
    if f"{r3.EPISODE_PREFIX}*" not in globs:
        problems.append("cache_generator_does_not_scan_3rscan_directories (ruling 111-7 (a): the registration commit widens the glob)")
    return problems


def cmd_check(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    lean_test_seal.refuse_sealed([run_root, args.s3_03_run_root], reader="s3-07 check")
    receipt = receipt_of(args)
    problems: list[str] = []
    if s4.receipt_body_sha256(receipt) != receipt.get("receipt_sha256"):
        problems.append("freeze_receipt_digest_differs")
    current = s4.code_digest(ROOT, tracked_code_files())
    differences = s4.code_differences(receipt["code"], current)
    problems += disallowed_code_differences(receipt["code"], current)[:20]
    tag = receipt["freeze_commit"][:7]
    committed = f"results/vsmt_lean_s3_04_freeze_{tag}.json"
    try:
        published = json.loads(git("show", f"HEAD:{committed}"))
        if s4.canonical_sha256(published) != s4.canonical_sha256(receipt):
            problems.append(f"committed_receipt_differs:{committed}")
    except (subprocess.CalledProcessError, ValueError):
        problems.append(f"receipt_not_committed:{committed}")
    contract = r3.load_contract()
    null_slots = r3.blocking_null_slots(contract)
    if null_slots or not contract["authorization"]["formal_conversion"]:
        problems.append(f"formal_conversion_not_open:null_slots={null_slots}:authorization={contract['authorization']['formal_conversion']}")
    # the converter commit is the one the converted episodes record; before any exists, the commit about to convert (HEAD)
    receipts = episode_receipts(Path(args.episode_root)) if args.episode_root else {}
    converter_commits = sorted({str(row.get("code_commit")) for row in receipts.values() if row.get("status") == "succeeded"})
    commit = git("rev-parse", "HEAD")
    if len(converter_commits) > 1:
        problems.append(f"converted_episodes_from_several_commits:{converter_commits}")
    registration = registration_problems(converter_commits[0] if converter_commits else commit)
    if converter_commits:
        problems += registration
    else:  # nothing converted yet: the registration of this commit is reported, not required (it happens after conversion)
        pass
    if args.role == "audit":
        s0_05 = load_json(S0_05_CONTRACT)
        for front, values in receipt["frozen_bytes"]["elu_p_registered"].items():
            if dict(arms.elu_p_fitted(s0_05, FRONTS[front]) or {}) != dict(values):
                problems.append(f"elu_p_values_differ:{front}")
        for path, digest in sorted(receipt["frozen_bytes"]["heads"].items()):
            if not Path(path).exists() or s4.file_sha256(Path(path)) != digest:
                problems.append(f"heads_file_differs_or_missing:{path}")
    return finish(run_root, "check", {"role": args.role, "converter_commits": converter_commits,
                                      "registration_of_this_commit_if_it_converts": registration,
                                      "receipt": {"path": args.receipt, "receipt_sha256": receipt["receipt_sha256"],
                                                                      "freeze_commit": receipt["freeze_commit"], "committed_as": committed},
                                      "code_differences_from_the_freeze": differences, "allowed": {"prefixes": ALLOWED_PREFIXES, "files": ALLOWED_FILES},
                                      "contract_sha256": s4.file_sha256(r3.CONTRACT_PATH), "problems": problems})


# --------------------------------------------------------------------------
# GPU phase: render, convert, reader-check, cache, e2, handoff
# --------------------------------------------------------------------------

def run_logged(argv: Sequence[str], log: Path, *, env: Mapping[str, str] | None = None) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as handle:
        return subprocess.run(list(argv), stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT), env=env).returncode


def cmd_render(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "check"), "render_needs_a_passed_check_at_this_commit")
    argv = [sys.executable, str(RENDER_ENTRY), "--scans-root", args.scans_root, "--meta", args.meta, "--out-root", args.render_root,
            "--purpose", "formal", "--workers", str(args.workers), "--worker-basis", args.worker_basis, "--resume"]
    code = run_logged(argv, Path(args.log_dir) / "render.log")
    receipt = load_json(Path(args.render_root) / "render_receipt.json") if (Path(args.render_root) / "render_receipt.json").exists() else {}
    by_status = receipt.get("by_status") or {}
    problems = [] if code == 0 else [f"render_exit:{code}:by_status={by_status}"]
    return finish(run_root, "render", {"render_root": args.render_root, "by_status": by_status, "workers": receipt.get("workers_actual"),
                                       "problems": problems})


def cmd_convert(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "render"), "convert_needs_a_passed_render_at_this_commit")
    argv = [sys.executable, str(CONVERT_ENTRY), "convert", "--scans-root", args.scans_root, "--meta", args.meta, "--labels", args.labels,
            "--render-root", args.render_root, "--out-root", args.episode_root, "--geometry-root", args.geometry_root, "--purpose", "formal",
            "--workers", str(args.workers), "--worker-basis", args.worker_basis, "--resume"]
    code = run_logged(argv, Path(args.log_dir) / "convert.log")
    receipts = episode_receipts(Path(args.episode_root))
    by_status: dict[str, int] = {}
    for row in receipts.values():
        by_status[row.get("status")] = by_status.get(row.get("status"), 0) + 1
    failed = sorted((e, row.get("reason")) for e, row in receipts.items() if row.get("status") != "succeeded")
    problems = [] if code == 0 or (code == 1 and receipts) else [f"convert_exit:{code}"]
    return finish(run_root, "convert", {"episode_root": args.episode_root, "geometry_root": args.geometry_root, "by_status": by_status,
                                        "failed_pairs": failed, "rule": "a failed pair is recorded, never replaced", "problems": problems})


def cmd_reader_check(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "convert"), "reader_check_needs_a_passed_convert_at_this_commit")
    report = run_root / "reader_check_report.json"
    argv = [sys.executable, str(CONVERT_ENTRY), "reader-check", "--out-root", args.episode_root, "--geometry-root", args.geometry_root,
            "--report", str(report)]
    run_logged(argv, Path(args.log_dir) / "reader_check.log")
    rows = load_json(report)["episodes"] if report.exists() else []
    failed = [row["episode_id"] for row in rows if not row["passed"]]
    succeeded_conversion = {e for e, row in episode_receipts(Path(args.episode_root)).items() if row.get("status") == "succeeded"}
    unexpected = sorted(e for e in failed if e in succeeded_conversion)
    problems = [f"frozen_readers_refuse_converted_episodes:{unexpected[:5]}"] if unexpected else []
    return finish(run_root, "reader-check", {"checked": len(rows), "failed": failed, "problems": problems})


def cache_root_of(args: argparse.Namespace, front: str) -> Path:
    return Path(args.cache_root_base) / front


def cache_report(cache_root: Path, episode_root: Path, mask_source: str) -> tuple[dict[str, Any], list[str]]:
    """Every converted episode has a final cache receipt: succeeded, or failed by one of the frozen data reasons."""

    stage = cache_root / "s1_03_receipt.json"
    problems = []
    if not stage.exists():
        return {"complete": False}, [f"no_complete_stage_receipt:{cache_root}"]
    receipt = load_json(stage)
    if not receipt.get("complete") or receipt.get("mask_source") != mask_source:
        problems.append(f"stage_receipt_incomplete_or_other_source:{cache_root}")
    cached = episode_receipts(cache_root)
    converted = [e for e, row in episode_receipts(episode_root).items() if row.get("status") == "succeeded"]
    usable, data_failures = [], []
    for episode in converted:
        row = cached.get(episode)
        if row is None:
            problems.append(f"cache_missing:{episode}")
        elif row.get("status") == "succeeded":
            usable.append({"episode_id": episode, "frames": int(row.get("frames") or 1), "episode_seal_sha256": row.get("episode_seal_sha256")})
        elif row.get("status") == "failed" and row.get("reason") in CACHE_DATA_FAILURES:
            data_failures.append({"episode_id": episode, "reason": row.get("reason"), "detail": str(row.get("detail") or "")[:200]})
        else:
            problems.append(f"cache_failed_not_by_the_data:{episode}:{row.get('status')}:{row.get('reason')}")
    return {"complete": bool(receipt.get("complete")), "code_commit": receipt.get("code_commit"), "usable": usable,
            "data_failures": data_failures, "converted": len(converted)}, problems


def cmd_cache(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "reader-check"), "cache_needs_a_passed_reader_check_at_this_commit")
    out: dict[str, Any] = {}
    problems: list[str] = []
    for front, source in FRONTS.items():
        cache_root = cache_root_of(args, front)
        resume = cache_root.exists() and any(cache_root.iterdir())
        workers = args.sam2_workers if front == "sam2" else args.instance_workers
        argv = [sys.executable, str(CACHE_ENTRY), "--episode-roots", args.episode_root, "--output-root", str(cache_root),
                "--assets-json", args.assets_json, "--workers", str(workers), "--worker-basis", args.worker_basis, "--mask-source", source,
                "--gpus", args.gpus, "--largest-first", *(["--resume"] if resume else [])]
        env = {**os.environ, **pool.thread_environment(2)}  # the S3-02 cache runs: two threads per worker
        code = run_logged(argv, Path(args.log_dir) / f"cache-{front}.log", env=env)
        report, front_problems = cache_report(cache_root, Path(args.episode_root), source)
        out[front] = {**report, "exit": code, "cache_root": str(cache_root), "workers": workers}
        problems += [f"{front}:{item}" for item in front_problems]
    return finish(run_root, "cache", {"fronts": out, "gpus": args.gpus, "problems": problems})


def e2_comparison(regenerated: Mapping[str, Mapping[str, Any]], exports: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """E2: the regenerated episode seals against the committed S3-02 exports, per front and episode."""

    rows = []
    for front, cached in regenerated.items():
        reference = {row["episode_id"]: row for row in exports[front]["episodes"]}
        for episode in E2_EPISODES:
            new, old = cached.get(episode) or {}, reference.get(episode) or {}
            rows.append({"front": front, "episode_id": episode, "status": new.get("status"), "episode_seal_sha256": new.get("episode_seal_sha256"),
                         "s3_02_episode_seal_sha256": old.get("episode_seal_sha256"),
                         "identical": bool(new.get("status") == "succeeded" and new.get("episode_seal_sha256") is not None
                                           and new.get("episode_seal_sha256") == old.get("episode_seal_sha256"))})
    return rows


def cmd_e2(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "check"), "e2_needs_a_passed_check_at_this_commit")
    out_base = run_root / "e2"
    regenerated: dict[str, dict[str, Any]] = {}
    exits = {}
    for front, source in FRONTS.items():
        out_root = out_base / front
        resume = out_root.exists() and any(out_root.iterdir())
        argv = [sys.executable, str(CACHE_ENTRY), "--episode-roots", args.s3_02_train_root, "--output-root", str(out_root),
                "--assets-json", args.assets_json, "--workers", "2", "--worker-basis", "E2: the two smallest S3-02 train episodes, one per card",
                "--mask-source", source, "--gpus", args.gpus, "--largest-first", *(["--resume"] if resume else [])]
        exits[front] = run_logged(argv, Path(args.log_dir) / f"e2-{front}.log", env={**os.environ, **pool.thread_environment(2)})
        regenerated[front] = {name: row for name, row in ((p.parent.name, load_json(p)) for p in sorted(out_root.glob("procthor10k-*/receipt.json")))}
    exports = {front: json.loads(git("show", f"HEAD:{path}")) for front, path in E2_EXPORTS.items()}
    rows = e2_comparison(regenerated, exports)
    problems = [f"e2_not_identical:{row['front']}:{row['episode_id']}" for row in rows if not row["identical"]]
    return finish(run_root, "e2", {"rows": rows, "exits": exits, "exports": E2_EXPORTS, "gpus": args.gpus, "problems": problems})


def root_digests(roots: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    return {name: lean_test_seal.tree_digest(Path(path)) for name, path in sorted(roots.items())}


def cmd_handoff(args: argparse.Namespace) -> int:
    """The GPU phase's hand-over: digests of every root the audit phase receives, and the usable episodes per front end."""

    run_root = Path(args.run_root)
    for name in ("cache", "e2"):
        _require(passed(run_root, name), f"handoff_needs_a_passed_{name}_at_this_commit")
    cache = load_json(step_path(run_root, "cache"))["fronts"]
    roots = {"episodes": Path(args.episode_root), "geometry": Path(args.geometry_root),
             **{f"cache_{front}": Path(cache[front]["cache_root"]) for front in FRONTS}}
    handoff = {"stage": STAGE, "step": "handoff", "code_commit": git("rev-parse", "HEAD"), "written_utc": utc_now(),
               "receipt_sha256": receipt_of(args)["receipt_sha256"], "roots": {k: str(v) for k, v in roots.items()},
               "digests": root_digests(roots), "episodes": {front: cache[front]["usable"] for front in FRONTS},
               "cache_data_failures": {front: cache[front]["data_failures"] for front in FRONTS},
               "e2": load_json(step_path(run_root, "e2"))["rows"], "split_key": SPLIT_KEY, "split_meaning": SPLIT_MEANING}
    write_json(run_root / HANDOVER_FILE, handoff)  # not handoff.json: that name is the step record finish() writes
    return finish(run_root, "handoff", {"roots": handoff["roots"], "episodes": {f: len(v) for f, v in handoff["episodes"].items()},
                                        "handover": str(run_root / HANDOVER_FILE), "problems": []})


# --------------------------------------------------------------------------
# audit phase: receive, inputs, e3, run, merge, stats, export
# --------------------------------------------------------------------------

def cmd_receive(args: argparse.Namespace) -> int:
    """The copied roots equal the hand-over's digests, and the hand-over is of this receipt."""

    run_root = Path(args.run_root)
    _require(passed(run_root, "check"), "receive_needs_a_passed_check_at_this_commit")
    handoff = load_json(run_root / HANDOVER_FILE)
    problems = []
    if handoff.get("receipt_sha256") != receipt_of(args)["receipt_sha256"]:
        problems.append("handoff_of_another_receipt")
    digests = root_digests({name: Path(path) for name, path in handoff["roots"].items()})
    for name, digest in digests.items():
        if digest != handoff["digests"].get(name):
            problems.append(f"root_differs_from_the_handoff:{name}")
    if any(not row["identical"] for row in handoff.get("e2", [])):
        problems.append("handoff_e2_not_identical")
    return finish(run_root, "receive", {"digests": digests, "problems": problems})


def usable_episodes(handoff: Mapping[str, Any], reader_failed: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    """Per front end: converted, read back by the frozen readers, and cached without a data failure."""

    out = {}
    for front in FRONTS:
        out[front] = [row for row in handoff["episodes"][front] if row["episode_id"] not in set(reader_failed)]
    return out


def cmd_inputs(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "receive"), "inputs_needs_a_passed_receive_at_this_commit")
    receipt = receipt_of(args)
    handoff = load_json(run_root / HANDOVER_FILE)
    s3_03 = s303.load_context(Path(args.s3_03_run_root))
    fronts = [front for front in FRONTS if front in receipt["fronts"]]
    if args.fronts:  # amendment 3 of ruling 111: the SAM 2.1 column is reported as not computable, only the instance column runs
        wanted = [f for f in args.fronts.split(",") if f]
        _require(all(f in fronts for f in wanted), "fronts_not_in_the_receipt:" + args.fronts)
        fronts = wanted
    reader = run_root / "reader_check_report.json"
    reader_failed = load_json(reader)["failed"] if reader.exists() else []
    episodes = usable_episodes(handoff, reader_failed)
    inputs = {"stage": STAGE, "written_utc": utc_now(), "code_commit": git("rev-parse", "HEAD"), "fronts": fronts,
              "receipt": {"path": str(Path(args.receipt).resolve()), "receipt_sha256": receipt["receipt_sha256"]},
              "receipt_sha256": receipt["receipt_sha256"], "s3_03_run_root": str(Path(args.s3_03_run_root).resolve()),
              "split_key": SPLIT_KEY, "split_meaning": SPLIT_MEANING,
              "roots": {"raw": {SPLIT_KEY: handoff["roots"]["episodes"]}, "geometry": {SPLIT_KEY: handoff["roots"]["geometry"]},
                        "cache": {front: {SPLIT_KEY: handoff["roots"][f"cache_{front}"]} for front in fronts}},
              "reid": {front: {"file": str(s3_03.inputs["reid"][front]["file"])} for front in fronts},
              "episodes": {front: {SPLIT_KEY: episodes[front]} for front in fronts},
              "counts": {front: {"usable": len(episodes[front]), "cache_data_failures": len(handoff["cache_data_failures"][front])}
                         for front in fronts},
              "cache_data_failures": handoff["cache_data_failures"], "reader_check_failed": reader_failed,
              "fronts_not_run": {front: {"usable_episodes": len(handoff["episodes"][front]),
                                         "cache_data_failures": len(handoff["cache_data_failures"][front]),
                                         "rule": args.fronts_rule or "operator choice"}
                                 for front in FRONTS if front in receipt["fronts"] and front not in fronts}}
    write_json(run_root / "inputs.json", inputs)
    return finish(run_root, "inputs", {"counts": inputs["counts"], "problems": []})


def e3_tasks(receipt: Mapping[str, Any], ctx: s303.RunContext, run_root: Path) -> list[dict[str, Any]]:
    """E3: the S3-04 G4 probe audits (the receipt's test_runs on its probe_episodes) rerun here, outputs under this run root."""

    import s3_04_manifest as s304

    tasks = []
    for front in ctx.fronts:
        if front not in receipt["fronts"]:
            continue
        select = {"test_runs": receipt["fronts"][front]["test_runs"], "probe_episodes": receipt["fronts"][front]["probe_episodes"]}
        tasks += s304.probe_tasks(ctx, front, select, run_root / "e3")
    return tasks


def cmd_e3(args: argparse.Namespace) -> int:
    import lean_s2_05_node_audit as audit
    import s3_04_manifest as s304

    run_root = Path(args.run_root)
    _require(passed(run_root, "inputs"), "e3_needs_a_passed_inputs_at_this_commit")
    ctx = s303.load_context(Path(args.s3_03_run_root))
    tasks = e3_tasks(receipt_of(args), ctx, run_root)
    workers = s304.worker_count(len(tasks), args.workers)
    print(f"[s3-07-e3] {len(tasks)} probe audits on {workers['actual']} workers", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers["actual"]) as executor:
        rows = list(executor.map(s304.run_task, tasks))
    problems = []
    for row in rows:
        if row["exit"] != 0 or not Path(row["rerun"]).exists() or not Path(row["original"]).exists():
            row["identical"] = False
            problems.append(f"e3_audit_failed_or_missing:{row['group']}:{row['episode']}:exit{row['exit']}")
            continue
        first, again = load_json(Path(row["original"])), load_json(Path(row["rerun"]))
        left, right = audit.comparable_metrics(first), audit.comparable_metrics(again)
        row["differing_fields"] = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
        row["identical"] = not row["differing_fields"] and first.get("audit") == again.get("audit")
        if not row["identical"]:
            problems.append(f"e3_differs:{row['group']}:{row['episode']}:{row['differing_fields'][:4]}")
    return finish(run_root, "e3", {"workers": workers, "rows": rows, "problems": problems,
                                   "compared": "every audit field but wall time, commit and head path (comparable_metrics)"})


def group_root(run_root: Path, front: str, run: Mapping[str, Any]) -> Path:
    return run_root / front / "audit" / s303.group_name(run["arm"], int(run["config_index"]), run["seed"])


def merged_path(run_root: Path, front: str, run: Mapping[str, Any]) -> Path:
    return run_root / front / "merged" / f"{s303.group_name(run['arm'], int(run['config_index']), run['seed'])}.json"


def audit_argv(inputs: Mapping[str, Any], front: str, run: Mapping[str, Any], episode: str, run_root: Path, heads: Path | None) -> list[str]:
    """A metrics-only node audit of one frozen run on one 3RScan episode: no manifest split, no test receipt (ruling 111-6)."""

    cache = inputs["roots"]["cache"][front][SPLIT_KEY]
    entries = [{"config": dict(run["config"]), "output_root": str(group_root(run_root, front, run))}]
    return [sys.executable, str(NODE_AUDIT), "run", "--cache-root", cache, "--episode-root", str(Path(inputs["roots"]["raw"][SPLIT_KEY]) / episode),
            "--geometry-root", inputs["roots"]["geometry"][SPLIT_KEY], "--episode-id", episode, "--arm", run["arm"],
            "--descriptor", s303.s3_descriptor(), "--weights", inputs["reid"][front]["file"], "--mask-source", FRONTS[front],
            "--device", "cpu", "--metrics-only", "--skip-existing", "--configs", json.dumps(entries),
            *(["--heads", str(heads)] if heads is not None else [])]


def build_jobs(run_root: Path, inputs: Mapping[str, Any], receipt: Mapping[str, Any]) -> list[pool.Job]:
    s3_03 = s303.load_context(Path(inputs["s3_03_run_root"]))
    frozen = receipt["frozen_bytes"]["heads"]
    jobs = []
    for front in inputs["fronts"]:
        frames = {row["episode_id"]: int(row["frames"]) for row in inputs["episodes"][front][SPLIT_KEY]}
        for run in receipt["fronts"][front]["test_runs"]:
            heads = s3_03.heads_file(front, 1, run["heads_arm"], run["seed"]) if run["seed"] is not None else None
            _require(heads is None or str(heads) in frozen, f"heads_not_frozen_by_the_receipt:{heads}")
            seeded = run["seed"] is not None
            for episode in frames:
                job_id = f"{front}/external/{run['arm']}/{'rule' if not seeded else 's%d' % run['seed']}/{episode}"

                def build(f: str = front, r: Mapping[str, Any] = run, e: str = episode, h: Path | None = heads) -> list[str]:
                    return audit_argv(inputs, f, r, e, run_root, h)

                jobs.append(pool.Job(job_id, "audit", (), PRIORITY["learned" if seeded else "rule"], float(frames[episode]), 1, "audit",
                                     build, keep_partial=True, retries=AUDIT_RETRIES, stops_on_failure=False, exit_status={2: "gate_failed"},
                                     remote_push=tuple(str(p) for p in ((heads,) if heads is not None else ())),
                                     remote_pull=(str(group_root(run_root, front, run) / episode),), group=front))
    return jobs


def cmd_run(args: argparse.Namespace) -> int:
    import remote_hosts

    run_root = Path(args.run_root)
    for name in ("inputs", "e3"):
        _require(passed(run_root, name), f"run_needs_a_passed_{name}_at_this_commit")
    inputs, receipt = load_json(run_root / "inputs.json"), receipt_of(args)
    _require(inputs["receipt_sha256"] == receipt["receipt_sha256"], "inputs_of_another_receipt")
    info = s303.resources()
    cores = int(args.budget_cores or info["cpu_quota"]) - pool.RESERVE_CORES
    gib = int(info["memory_bytes"]) / 2 ** 30 - pool.RESERVE_GIB
    jobs = build_jobs(run_root, inputs, receipt)
    write_json(run_root / "workers.json", {"budget_cores": cores, "budget_gib": round(gib, 1), "resources": info, "jobs": len(jobs),
                                           "memory_gib": MEMORY_GIB, "written_utc": utc_now(),
                                           "rule": "ruling 104-3 / 111-6: cgroup cores less 2 and memory less 8 GiB; single-threaded audits"})
    runner = pool.Pool(jobs, run_root=run_root, log_dir=Path(args.log_dir), budget_cores=cores, budget_gib=gib, memory_defaults=MEMORY_GIB,
                       train_threads=lambda: 1, commit=git("rev-parse", "HEAD"), poll_seconds=args.poll_seconds, disk_root=run_root,
                       min_free_gib=args.min_free_gib, memory_limit_bytes=int(info["memory_bytes"]) - int(pool.RESERVE_GIB * 2 ** 30),
                       wrapper=[sys.executable, str(JOBS_SCRIPT), "run-measured"], memory_fixed=MEMORY_GIB, group_order=inputs["fronts"],
                       hosts=lambda: remote_hosts.load_hosts(run_root), remote_runner=[sys.executable, str(REMOTE_SCRIPT), "remote-run"],
                       suspend_host=lambda name, reason: remote_hosts.suspend(run_root, name, reason))
    print(f"[s3-07-run] {len(jobs)} external audits, {cores} cores, {round(gib, 1)} GiB", flush=True)
    code = runner.run()
    print(f"[s3-07-run] finished: {runner.stop_reason or 'all jobs ended'}")
    return code


def job_states(run_root: Path) -> dict[str, dict[str, Any]]:
    return {load_json(p)["job_id"]: load_json(p) for p in sorted((run_root / "jobs").glob("*.json")) if not p.name.endswith(".rss.json")}


def cmd_merge(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    inputs, receipt = load_json(run_root / "inputs.json"), receipt_of(args)
    states = job_states(run_root)
    graph = build_jobs(run_root, inputs, receipt)
    not_ended = [job.job_id for job in graph if states.get(job.job_id, {}).get("status") not in ("done", "failed")]
    problems = [f"jobs_not_ended:{len(not_ended)}:{not_ended[:5]}"] if not_ended else []
    rows: list[dict[str, Any]] = []
    if not problems:
        for front in inputs["fronts"]:
            for run in receipt["fronts"][front]["test_runs"]:
                target = merged_path(run_root, front, run)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.unlink()
                audits = list(group_root(run_root, front, run).glob(f"*/{run['arm']}/*.json"))
                done = subprocess.run([sys.executable, str(NODE_AUDIT), "merge", "--output-root", str(group_root(run_root, front, run)),
                                       "--arm", run["arm"], "--results", str(target)], capture_output=True, text=True)
                rows.append({"front": front, "group": target.stem, "exit": done.returncode, "merged": target.exists(), "audits": len(audits)})
                if audits and (done.returncode != 0 or not target.exists()):
                    problems.append(f"merge_failed:{front}:{target.stem}:exit{done.returncode}:{(done.stderr or '').strip()[-160:]}")
    return finish(run_root, "merge", {"groups": rows, "problems": problems})


def statistics_from_merged(run_root: Path, inputs: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    seed, iterations = receipt["statistics"]["bootstrap_seed"], receipt["statistics"]["bootstrap_iterations"]
    per_front = {}
    for front in inputs["fronts"]:
        episodes = [row["episode_id"] for row in inputs["episodes"][front][SPLIT_KEY]]
        runs = []
        for run in receipt["fronts"][front]["test_runs"]:
            path = merged_path(run_root, front, run)
            rows = {row["episode_id"]: row for row in load_json(path)["per_episode"]} if path.exists() else {}
            runs.append({"arm": run["arm"], "seed": run["seed"], "rows": rows})
        tables = s7.scene_tables(runs, episodes)
        per_front[front] = {**s7.front_statistics(tables, runs, seed=seed, iterations=iterations),
                            "cache_data_failures": inputs["cache_data_failures"][front], "reader_check_failed": inputs["reader_check_failed"]}
    return s7.external_statistics(per_front)


def cmd_stats(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "merge"), "stats_need_the_merge_step")
    inputs, receipt = load_json(run_root / "inputs.json"), receipt_of(args)
    result = statistics_from_merged(run_root, inputs, receipt)
    write_json(run_root / "statistics.json", {**result, "receipt_sha256": receipt["receipt_sha256"], "written_utc": utc_now()})
    failures = {front: len(block["failures"]) for front, block in result["fronts"].items()}
    print(f"[s3-07-stats] written {run_root / 'statistics.json'}; audit failures {failures}")
    return finish(run_root, "stats", {"failures": failures, "problems": []})


def cmd_export(args: argparse.Namespace) -> int:
    run_root, export_dir = Path(args.run_root), Path(args.export_dir)
    _require(passed(run_root, "stats"), "export_needs_the_stats_step")
    tag = git("rev-parse", "HEAD")[:7]
    inputs = load_json(run_root / "inputs.json")
    states = job_states(run_root)
    by_status: dict[str, int] = {}
    for state in states.values():
        by_status[state["status"]] = by_status.get(state["status"], 0) + 1
    exports = {f"vsmt_lean_s3_07_statistics_{tag}.json": load_json(run_root / "statistics.json"),
               f"vsmt_lean_s3_07_inputs_{tag}.json": inputs,
               f"vsmt_lean_s3_07_check_{tag}.json": load_json(step_path(run_root, "check")),
               f"vsmt_lean_s3_07_handover_{tag}.json": load_json(run_root / HANDOVER_FILE),
               f"vsmt_lean_s3_07_e3_{tag}.json": load_json(step_path(run_root, "e3")),
               f"vsmt_lean_s3_07_jobs_{tag}.json": {"by_status": by_status, "failed": sorted(k for k, s in states.items() if s["status"] == "failed"),
                                                    "hosts": sorted({s.get("host") or "local" for s in states.values()})}}
    for front in inputs["fronts"]:
        for path in sorted((run_root / front / "merged").glob("*.json")):
            exports.setdefault(f"vsmt_lean_s3_07_merged_{front}_{tag}.json", {})[path.stem] = load_json(path)
    for name, payload in exports.items():
        write_json(export_dir / name, payload)
    manifest = {"stage": STAGE, "tag": tag, "written_utc": utc_now(), "receipt_sha256": inputs["receipt_sha256"],
                "exports": {name: {"sha256": s4.file_sha256(export_dir / name), "bytes": (export_dir / name).stat().st_size} for name in sorted(exports)}}
    write_json(export_dir / f"vsmt_lean_s3_07_manifest_{tag}.json", manifest)
    return finish(run_root, "export", {"exports": sorted(exports), "problems": []})


def cmd_status(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    by_status: dict[str, int] = {}
    for state in job_states(run_root).values() if (run_root / "jobs").exists() else ():
        by_status[state["status"]] = by_status.get(state["status"], 0) + 1
    names = ("check", "render", "convert", "reader-check", "cache", "e2", "handoff", "receive", "inputs", "e3", "merge", "stats", "export")
    steps = {name: load_json(step_path(run_root, name)).get("pass") for name in names if step_path(run_root, name).exists()}
    print(json.dumps({"steps": steps, "jobs_by_status": by_status}, indent=1))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    commands = {"check": cmd_check, "render": cmd_render, "convert": cmd_convert, "reader-check": cmd_reader_check, "cache": cmd_cache,
                "e2": cmd_e2, "handoff": cmd_handoff, "receive": cmd_receive, "inputs": cmd_inputs, "e3": cmd_e3, "run": cmd_run,
                "merge": cmd_merge, "stats": cmd_stats, "export": cmd_export, "status": cmd_status}
    for name, func in commands.items():
        command = sub.add_parser(name)
        command.add_argument("--run-root", required=True)
        if name != "status":
            command.add_argument("--receipt", required=True)
            command.add_argument("--s3-03-run-root", required=True)
            command.add_argument("--log-dir", default=None)
        if name == "check":
            command.add_argument("--role", choices=("gpu", "audit"), required=True)
            command.add_argument("--episode-root", default=None)
        if name in ("render", "convert"):
            command.add_argument("--scans-root", required=True)
            command.add_argument("--meta", required=True)
            command.add_argument("--render-root", required=True)
            command.add_argument("--workers", type=int, required=True)
            command.add_argument("--worker-basis", default="")
        if name == "convert":
            command.add_argument("--labels", required=True)
        if name in ("convert", "reader-check", "cache", "handoff"):
            command.add_argument("--episode-root", required=True)
        if name in ("convert", "reader-check", "handoff"):
            command.add_argument("--geometry-root", required=True)
        if name in ("cache", "e2"):
            command.add_argument("--assets-json", required=True)
            command.add_argument("--gpus", required=True)
        if name == "cache":
            command.add_argument("--cache-root-base", required=True)
            command.add_argument("--instance-workers", type=int, required=True)
            command.add_argument("--sam2-workers", type=int, required=True)
            command.add_argument("--worker-basis", default="")
        if name == "e2":
            command.add_argument("--s3-02-train-root", required=True)
        if name == "inputs":
            command.add_argument("--fronts", default=None, help="comma-separated front ends to run (amendment 3: instance only)")
            command.add_argument("--fronts-rule", default=None, help="the ruling that limits the front ends, recorded")
        if name == "e3":
            command.add_argument("--workers", type=int, default=None)
        if name == "run":
            command.add_argument("--budget-cores", type=int, default=None)
            command.add_argument("--poll-seconds", type=float, default=2.0)
            command.add_argument("--min-free-gib", type=float, default=20.0)
        if name == "export":
            command.add_argument("--export-dir", required=True)
        command.set_defaults(func=func)
    args = parser.parse_args(argv)
    if getattr(args, "log_dir", None) is None and args.step != "status":
        args.log_dir = str(Path(args.run_root) / "logs")
    try:
        return args.func(args)
    except (DriverError, r3.LeanS307Error, s7.LeanS3_07Error, lean_test_seal.LeanTestSealError) as exc:
        print(f"[s3-07-{args.step}] refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
