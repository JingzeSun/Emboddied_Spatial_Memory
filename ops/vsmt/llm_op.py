#!/usr/bin/env python3
"""LLM-op driver (ruling 105): the plan on the S3-02 host; check, pilot, run, status, export and replay-check on the LLM-op host.

白话：附录臂 LLM-op 的整趟流程。输入是 S3-03 检查过的 train／validation 名单与数据根（只读，test 根不碰）、登记的合同和
DeepSeek 密钥（只在新机器的文件里）；输出是每套前端 1 条 validation episode（裁决 108；原 105-2 为 15 条）的闭环指标（与其他臂同一个 node audit、同一套
指标）、全部调用存档、试点报告和 results/ 里的一份导出。步骤：
  plan   （S3-02 那台机器）按裁决 105-2／108 抽 1 条 validation episode、选试点 episode（已有按旧条数写的计划时，
         只有 --supersede 才把它改名保留为 plan.superseded.<sha12>.json 再重写，抽签顺序必须相同、正式运行不能已开始），记下各封印摘要、每帧行数（S3-03 第 0 轮
         ELU-P 回执的均值）和要拷的路径清单 transfer.txt；
  check  （新机器）逐条重算 cache 封印、核对原始回执、几何表和两个 ReID 头，读密钥、查 API 能否用，定并行数；
  pilot  两套前端各在试点 episode 的前 200 帧上真调 API（只跑公开阶段，不读私有、不算指标），按每行价钱推算总费用，
         超过 30 美元（裁决 108）就停下汇报；登记返回的模型名；
  run    2 个作业（2 套前端 × 1 条）并行跑 node audit 的 LLM-op 正式审计；累计（含试点）30 美元不再开新作业，40 美元写 STOP
         全部停下；中断的作业重跑时从存档回放、不重复花钱；
  status 进度、费用、回退与模型名；stop 写 STOP（所有进程在下一次调用前停下）；
  replay-check  每套前端按存档只回放最短的一条 episode，核对轨迹摘要与指标和正式运行逐字节相同（复现性），记进
         replay/check.json——必须在 export 之前跑（export 往 results/ 里写文件，checkout 不再干净，回放的审计会拒绝）；
  export 两套前端的逐 episode 指标与合并、调用统计（回退率超过 2% 标“格式不可靠”）、费用、模型名与回放核对，写进 results/。
它不训练、不选参、不读 test；没有用户审过代码后打开的合同位，pilot 和 run 一律拒绝。

Usage (normally through ops/vsmt/llm_op.sh):
  python ops/vsmt/llm_op.py plan   --run-root R --inputs /root/autodl-tmp/vsmt_private/s3-03-run/inputs.json [--allow-provisional]
  python ops/vsmt/llm_op.py check  --run-root R [--workers N]
  python ops/vsmt/llm_op.py pilot  --run-root R
  python ops/vsmt/llm_op.py run    --run-root R [--workers N] [--accept-pilot] [--resume-after-stop]
  python ops/vsmt/llm_op.py status --run-root R
  python ops/vsmt/llm_op.py stop   --run-root R
  python ops/vsmt/llm_op.py replay-check --run-root R [--front instance --episode <episode id>]
  python ops/vsmt/llm_op.py export --run-root R --out results/vsmt_lean_llm_op_<commit>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_llm_op as llm  # noqa: E402

STAGE = "vsmt.lean.llm_op.driver.v1"
NODE_AUDIT = HERE.parent / "lean_s2_05_node_audit.py"
SPLITS = ("train", "validation")
#: Measured S3-03 'pass' class (1.25 x the measured peak of a closed-loop pass without training records), per LLM-op process.
JOB_MEMORY_GIB = 1.5
MEMORY_RESERVE_GIB = 8.0
POLL_SECONDS = 15.0
#: Exit code of a step that ended at a decision point (projection over the cap, a stop, unfinished work), not a failure.
EXIT_DECISION = 3


class DriverError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DriverError(code)


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def utc() -> str:
    return llm.utc_now().isoformat()


# --------------------------------------------------------------------------
# the plan (S3-02 host)
# --------------------------------------------------------------------------

class Plan:
    """plan.json and the paths it names; the same absolute paths hold on the LLM-op host after the transfer."""

    def __init__(self, run_root: Path) -> None:
        self.run_root = Path(run_root)
        self.data = load_json(self.run_root / "plan.json")

    def raw_root(self, split: str) -> Path:
        return Path(self.data["roots"]["raw"][split])

    def geometry_root(self, split: str) -> Path:
        return Path(self.data["roots"]["geometry"][split])

    def cache_root(self, front: str, split: str) -> Path:
        return Path(self.data["roots"]["cache"][front][split])

    def reid(self, front: str) -> Path:
        return Path(self.data["reid"][front]["file"])

    @property
    def episodes(self) -> list[str]:
        return [row["episode_id"] for row in self.data["draw"]["episodes"]]

    @property
    def pilot_episode(self) -> str:
        return str(self.data["pilot"]["episode_id"])

    def frames(self, episode: str) -> int:
        return int({row["episode_id"]: row["frames"] for row in self.data["draw"]["episodes"]}[episode])


def sealed_refusal(roots: Mapping[str, Any], *, reader: str) -> str | None:
    """Ruling 103-1: no LLM-op step reads a sealed S3 test root (the guard looks at each root and one level below it)."""

    from vsmt import lean_test_seal

    paths = [roots["raw"][split] for split in SPLITS] + [roots["geometry"][split] for split in SPLITS]
    paths += [roots["cache"][front][split] for front in llm.FRONTS for split in SPLITS]
    return lean_test_seal.refusal(paths, reader=reader)


def usable_lists(inputs: Mapping[str, Any], split: str) -> dict[str, dict[str, int]]:
    """Per front end, the S3-03 check's usable episodes of a split with their frame counts."""

    out: dict[str, dict[str, int]] = {}
    for front in llm.FRONTS:
        rows = inputs["episodes"][front][split]
        out[front] = {str(row["episode_id"]): int(row["frames"]) for row in rows}
    return out


def rows_per_frame(s3_03_run_root: Path, front: str) -> dict[str, Any]:
    """Ruling 105-8: the rows a full frame carries, from the S3-03 round-0 ELU-P receipts of this front end (train)."""

    frames = fragments = existence = receipts = 0
    for path in sorted((s3_03_run_root / front / "round0").glob("*/ELU-P/receipt.json")):
        payload = load_json(path)
        if payload.get("status") not in (None, "succeeded") or not payload.get("frames"):
            continue
        receipts += 1
        frames += int(payload["frames"])
        existence += int(payload["existence_candidates"])
        fragments += int((payload.get("nuisance_probes") or {}).get("association_rows") or 0)
    if receipts == 0:
        return {"receipts": 0}
    per_fragment_rows = 1 + 8  # the NEW row plus all 8 recalled candidates: an upper bound
    return {"receipts": receipts, "frames": frames, "fragments_per_frame": fragments / frames,
            "existence_rows": existence / frames, "association_rows": per_fragment_rows * fragments / frames,
            "source": f"{s3_03_run_root}/{front}/round0/*/ELU-P/receipt.json (train, ELU-P at the rollout configuration)"}


def plan(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    old_plan = None
    if (run_root / "plan.json").exists():
        if not args.supersede:
            print(f"[llm-op] refused: {run_root / 'plan.json'} exists; a plan is written once (--supersede only for a plan an "
                  "amendment of the episode count made stale, ruling 108)", file=sys.stderr)
            return 2
        old_plan = load_json(run_root / "plan.json")
        if len(old_plan["draw"]["episodes"]) == llm.EPISODES_PER_FRONT or old_plan["draw"]["salt"] != llm.DRAW_SALT:
            print("[llm-op] refused: --supersede replaces only a plan with another episode count under the same salt",
                  file=sys.stderr)
            return 2
        if any((run_root / "archive").glob("*/*.jsonl")):
            print("[llm-op] refused: the run of record has started; its plan cannot be superseded", file=sys.stderr)
            return 2
    inputs_path = Path(args.inputs)
    inputs = load_json(inputs_path)
    refusal = sealed_refusal(inputs["roots"], reader="llm-op plan")
    if refusal:
        print(f"[llm-op] refused: {refusal}", file=sys.stderr)
        return 2
    if inputs.get("problems"):  # the S3-03 check writes its findings even when it stops on them
        print(f"[llm-op] refused: the S3-03 check recorded problems: {inputs['problems'][:5]}", file=sys.stderr)
        return 2
    if inputs.get("provisional") and not args.allow_provisional:
        print("[llm-op] refused: the S3-03 inputs are still provisional (S3-02 has not exported); wait for the full check, or "
              "--allow-provisional (recorded in the plan)", file=sys.stderr)
        return 2
    validation = usable_lists(inputs, "validation")
    train = usable_lists(inputs, "train")
    both = sorted(set(validation["instance"]) & set(validation["sam2"]))
    for episode in both:
        _require(validation["instance"][episode] == validation["sam2"][episode], f"frame_counts_differ_between_fronts:{episode}")
    order = llm.draw_order(both)
    if old_plan is not None and old_plan["draw"]["order"] != order:
        print("[llm-op] refused: the validation order differs from the superseded plan's; the draw must not change", file=sys.stderr)
        return 2
    _require(len(order) >= llm.EPISODES_PER_FRONT, f"too_few_validation_episodes:{len(order)}")
    drawn = order[: llm.EPISODES_PER_FRONT]
    train_both = [e for e in llm.draw_order(set(train["instance"]) & set(train["sam2"])) if train["instance"][e] >= llm.PILOT_FRAMES]
    _require(bool(train_both), "no_train_episode_for_the_pilot")
    pilot_episode = train_both[0]
    roots = inputs["roots"]
    reid = {front: {"file": inputs["reid"][front]["file"], "file_sha256": inputs["reid"][front]["file_sha256"],
                    "payload_sha256": inputs["reid"][front]["payload_sha256"]} for front in llm.FRONTS}

    def episode_digests(split: str, episode: str, *, geometry: bool) -> dict[str, Any]:
        raw = Path(roots["raw"][split]) / episode
        out = {"raw_receipt_sha256": file_sha256(raw / "receipt.json"),
               "cache_seal": {front: load_json(Path(roots["cache"][front][split]) / episode / "episode_seal.json")["payload_sha256"]
                              for front in llm.FRONTS}}
        if geometry:
            out["geometry_table_sha256"] = file_sha256(Path(roots["geometry"][split]) / episode / "object_geometry.json")
        return out

    s3_03_root = Path(inputs.get("run_root") or inputs_path.parent)
    rows = {front: rows_per_frame(s3_03_root, front) for front in llm.FRONTS}
    for front in llm.FRONTS:  # a front end without round-0 receipts borrows the other's means, flagged
        if not rows[front].get("receipts"):
            other = next(f for f in llm.FRONTS if f != front)
            _require(bool(rows[other].get("receipts")), "no_round0_receipts_for_the_rows_per_frame")
            rows[front] = {**rows[other], "borrowed_from": other}
    payload = {
        "stage": llm.STAGE_ID, "driver": STAGE, "ruling": llm.RULING, "written_utc": utc(), "code_commit": git("rev-parse", "HEAD"),
        "contract_sha256": file_sha256(llm.CONTRACT_PATH),
        "inputs": {"file": str(inputs_path), "sha256": file_sha256(inputs_path), "provisional": bool(inputs.get("provisional")),
                   "allow_provisional": bool(args.allow_provisional), "s3_03_code_commit": inputs.get("code_commit")},
        "roots": {"raw": dict(roots["raw"]), "geometry": dict(roots["geometry"]),
                  "cache": {front: dict(roots["cache"][front]) for front in llm.FRONTS}},
        "reid": reid,
        "draw": {"salt": llm.DRAW_SALT, "population": len(order), "order": order,
                 "episodes": [{"episode_id": e, "frames": validation["instance"][e], **episode_digests("validation", e, geometry=True)}
                              for e in drawn]},
        "pilot": {"episode_id": pilot_episode, "frames_available": train["instance"][pilot_episode], "frames": llm.PILOT_FRAMES,
                  **episode_digests("train", pilot_episode, geometry=False)},
        "planned_frames": {front: sum(validation[front][e] for e in drawn) for front in llm.FRONTS},
        "rows_per_frame": rows,
    }
    if old_plan is not None:  # ruling 108: the stale plan and its transfer list are kept beside the new ones, never deleted
        old_sha = file_sha256(run_root / "plan.json")
        kept = run_root / f"plan.superseded.{old_sha[:12]}.json"
        _require(not kept.exists(), f"superseded_plan_already_kept:{kept.name}")
        (run_root / "plan.json").replace(kept)
        if (run_root / "transfer.txt").exists():
            (run_root / "transfer.txt").replace(run_root / f"transfer.superseded.{old_sha[:12]}.txt")
        payload["supersedes"] = {"file": kept.name, "sha256": old_sha, "episodes_per_front": len(old_plan["draw"]["episodes"]),
                                 "code_commit": old_plan.get("code_commit"), "ruling": "108"}
    lines: list[str] = []
    for episode in drawn:
        lines += [str(Path(roots["raw"]["validation"]) / episode), str(Path(roots["geometry"]["validation"]) / episode)]
        lines += [str(Path(roots["cache"][front]["validation"]) / episode) for front in llm.FRONTS]
    # the pilot reads the public plane and the generator receipt of its episode, never the private plane
    lines += [str(Path(roots["raw"]["train"]) / pilot_episode / "public"), str(Path(roots["raw"]["train"]) / pilot_episode / "receipt.json")]
    lines += [str(Path(roots["cache"][front]["train"]) / pilot_episode) for front in llm.FRONTS]
    for split in SPLITS:
        for name in ("plan.json", "s1_03_receipt.json"):
            lines += [str(Path(roots["cache"][front][split]) / name) for front in llm.FRONTS if (Path(roots["cache"][front][split]) / name).exists()]
        for name in ("plan.json", "s1_04_geometry_receipt.json"):
            if (Path(roots["geometry"][split]) / name).exists():
                lines.append(str(Path(roots["geometry"][split]) / name))
        if (Path(roots["raw"][split]) / "s3_receipt.json").exists():
            lines.append(str(Path(roots["raw"][split]) / "s3_receipt.json"))
    lines += [reid[front]["file"] for front in llm.FRONTS]
    lines.append(str(run_root / "plan.json"))
    write_json(run_root / "plan.json", payload)
    (run_root / "transfer.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[llm-op] plan: {len(drawn)} validation episodes per front ({payload['planned_frames']} frames), pilot {pilot_episode}; "
          f"{len(lines)} paths in {run_root / 'transfer.txt'}")
    return 0


# --------------------------------------------------------------------------
# check (LLM-op host)
# --------------------------------------------------------------------------

def verify_episode(item: tuple[str, str, str, str]) -> dict[str, Any]:
    """One cache episode re-verified the way the S2-04 entry does (every frame seal recomputed); returns the seal and frame count."""

    import lean_s1_04_diagnostics as diag
    import lean_s2_04_evaluate_episode as s2_04

    front, split, cache_root, episode = item
    try:
        seal, paths = s2_04.verify_cache_episode(Path(cache_root) / episode, diag.registered_descriptor_asset_sha256s(),
                                                 mask_source=llm.FRONTS[front])
    except Exception as exc:  # noqa: BLE001 -- a refusal is a finding of the check, reported with its type
        return {"front": front, "split": split, "episode": episode, "ok": False, "problem": f"{type(exc).__name__}: {exc}"}
    return {"front": front, "split": split, "episode": episode, "ok": True, "seal": seal["payload_sha256"], "frames": len(paths)}


def resources() -> dict[str, Any]:
    import s2_06_manifest

    return s2_06_manifest.resources()


def choose_workers(info: Mapping[str, Any], jobs: int, requested: int | None) -> dict[str, Any]:
    """The largest safe number of concurrent episodes: the jobs, the memory at JOB_MEMORY_GIB each, and the cores (two kept)."""

    memory_gib = float(info["memory_bytes"]) / 2 ** 30 - MEMORY_RESERVE_GIB
    by_memory = max(1, int(memory_gib // JOB_MEMORY_GIB))
    by_cores = max(1, int(info["cpu_quota"]) - 2)
    chosen = min(int(jobs), by_memory, by_cores)
    actual = min(chosen, int(requested)) if requested else chosen
    return {"jobs": int(jobs), "by_memory": by_memory, "by_cores": by_cores, "chosen": chosen, "requested": requested, "actual": actual,
            "basis": (f"min(jobs, (memory.max - {MEMORY_RESERVE_GIB} GiB) / {JOB_MEMORY_GIB} GiB per episode process, cores - 2); "
                      "an LLM-op process waits on the API most of the time (about 0.2 s of CPU per frame)")}


def api_check(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """The key loads and the models endpoint answers with the registered model listed; the key itself is never printed."""

    try:
        key = llm.load_api_key(environ)
    except llm.LlmOpError as exc:
        return {"ok": False, "problem": str(exc)}
    try:
        status, text = llm.HttpTransport(api_key=key, timeout_s=60.0).get(llm.MODELS_ENDPOINT)
    except llm.TransportError as exc:
        return {"ok": False, "problem": f"transport_error:{exc}"}
    models: list[str] = []
    try:
        models = sorted(str(item.get("id")) for item in json.loads(text).get("data") or [])
    except (ValueError, AttributeError):
        pass
    ok = status == 200 and llm.MODEL in models
    return {"ok": ok, "http_status": status, "models": models,
            **({} if ok else {"problem": f"http_{status}" if status != 200 else f"model_not_listed:{llm.MODEL}"})}


def check(args: argparse.Namespace) -> int:
    from concurrent.futures import ProcessPoolExecutor

    from vsmt import lean_assignment as la

    run_root = Path(args.run_root)
    plan_ = Plan(run_root)
    refusal = sealed_refusal(plan_.data["roots"], reader="llm-op check")
    if refusal:
        print(f"[llm-op] refused: {refusal}", file=sys.stderr)
        return 2
    problems: list[str] = []
    contract = llm.load_contract()
    if git("status", "--porcelain") and not args.allow_dirty:
        problems.append("checkout_not_clean")
    items = [(front, "validation", str(plan_.cache_root(front, "validation")), e) for e in plan_.episodes for front in llm.FRONTS]
    items += [(front, "train", str(plan_.cache_root(front, "train")), plan_.pilot_episode) for front in llm.FRONTS]
    info = resources()
    workers = choose_workers(info, len(plan_.episodes) * len(llm.FRONTS), args.workers)
    pool_size = max(1, min(len(items), int(info["cpu_quota"]) - 2))
    if pool_size == 1:
        results = [verify_episode(item) for item in items]
    else:
        with ProcessPoolExecutor(max_workers=pool_size) as executor:
            results = list(executor.map(verify_episode, items))
    expected = {(row["episode_id"], front): seal for row in plan_.data["draw"]["episodes"] for front, seal in row["cache_seal"].items()}
    expected.update({(plan_.pilot_episode, front): seal for front, seal in plan_.data["pilot"]["cache_seal"].items()})
    frames = {row["episode_id"]: int(row["frames"]) for row in plan_.data["draw"]["episodes"]}
    for result in results:
        tag = f"{result['front']}:{result['split']}:{result['episode']}"
        if not result["ok"]:
            problems.append(f"cache:{tag}:{result['problem']}")
        elif result["seal"] != expected[(result["episode"], result["front"])]:
            problems.append(f"cache_seal_differs_from_the_plan:{tag}")
        elif result["split"] == "validation" and result["frames"] != frames[result["episode"]]:
            problems.append(f"frame_count_differs_from_the_plan:{tag}")
    for row in plan_.data["draw"]["episodes"]:
        raw = plan_.raw_root("validation") / row["episode_id"]
        if not (raw / "receipt.json").is_file() or file_sha256(raw / "receipt.json") != row["raw_receipt_sha256"]:
            problems.append(f"raw_receipt:{row['episode_id']}")
        for plane in ("public", "private", "provenance"):
            if not (raw / plane).is_dir():
                problems.append(f"raw_{plane}_missing:{row['episode_id']}")
        table = plan_.geometry_root("validation") / row["episode_id"] / "object_geometry.json"
        if not table.is_file() or file_sha256(table) != row["geometry_table_sha256"]:
            problems.append(f"geometry_table:{row['episode_id']}")
    pilot_raw = plan_.raw_root("train") / plan_.pilot_episode
    if not (pilot_raw / "receipt.json").is_file() or file_sha256(pilot_raw / "receipt.json") != plan_.data["pilot"]["raw_receipt_sha256"]:
        problems.append(f"raw_receipt:{plan_.pilot_episode}")
    for front, mask_source in llm.FRONTS.items():
        head = plan_.reid(front)
        if not head.is_file() or file_sha256(head) != plan_.data["reid"][front]["file_sha256"]:
            problems.append(f"reid_file:{front}")
        elif load_json(head).get("sha256") != la.reid_weights_sha256_for(mask_source):
            problems.append(f"reid_head_not_the_pinned_one:{front}")
    api = api_check()
    if not api["ok"]:
        problems.append(f"api:{api['problem']}")
    payload = {"stage": llm.STAGE_ID, "driver": STAGE, "checked_utc": utc(), "code_commit": git("rev-parse", "HEAD"),
               "contract_sha256": file_sha256(llm.CONTRACT_PATH), "authorization": dict(contract["authorization"]),
               "plan_sha256": file_sha256(run_root / "plan.json"), "episodes_verified": results, "api": api,
               "resources": info, "workers": workers, "problems": problems, "ok": not problems}
    write_json(run_root / "check.json", payload)
    print(f"[llm-op] check: {len(results)} cache episodes re-verified, API {'ok' if api['ok'] else api.get('problem')}, "
          f"workers {workers['actual']} ({workers['basis']}); {'ok' if not problems else 'problems: ' + '; '.join(problems)}")
    return 0 if not problems else 1


def require_check(run_root: Path) -> dict[str, Any]:
    path = run_root / "check.json"
    _require(path.exists(), "no_check_json: run the check first")
    payload = load_json(path)
    _require(payload.get("ok") is True, "the check found problems; see check.json")
    _require(payload.get("plan_sha256") == file_sha256(run_root / "plan.json"), "plan_changed_since_the_check")
    _require(payload.get("code_commit") == git("rev-parse", "HEAD"), "code_changed_since_the_check: run the check again")
    return payload


# --------------------------------------------------------------------------
# the pilot (public phase only, train, 200 frames)
# --------------------------------------------------------------------------

def pilot_one(args: argparse.Namespace) -> int:
    """One front end's pilot: the runner over the first 200 frames of the pilot episode, live calls, no private read."""

    import lean_s1_04_diagnostics as diag
    import lean_s2_01_runner as s2_01
    import lean_s2_04_evaluate_episode as s2_04
    import lean_s2_05_node_audit as audit
    from vsmt import lean_assignment as la
    from vsmt import lean_runner as lr

    run_root = Path(args.run_root)
    plan_ = Plan(run_root)
    front = args.front
    contract = llm.load_contract()
    if not llm.authorized(contract, "pilot_run"):
        print("[llm-op] refused: the contract's pilot_run bit is closed", file=sys.stderr)
        return 2
    refusal = sealed_refusal(plan_.data["roots"], reader="llm-op pilot")
    if refusal:
        print(f"[llm-op] refused: {refusal}", file=sys.stderr)
        return 2
    episode = plan_.pilot_episode
    cache_dir = plan_.cache_root(front, "train") / episode
    episode_root = plan_.raw_root("train") / episode
    seal, frame_paths = s2_04.verify_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s(), mask_source=llm.FRONTS[front])
    frame_paths = frame_paths[: llm.PILOT_FRAMES]
    projector, weights_sha256 = s2_01.reid_projector(la.SELECTED_DESCRIPTOR, str(plan_.reid(front)), mask_source=llm.FRONTS[front],
                                                     device="cpu")
    policy, missing = s2_04.gather_teacher_policy()
    _require(not missing, f"policy_values_still_null:{missing}")
    archive = run_root / "pilot" / "archive" / f"{front}.jsonl"
    caller = llm.make_caller(archive_path=archive, mode="live", run_root=run_root, expected_model=None)
    scorer = llm.LlmOpScorer(caller, split=llm.PILOT_SPLIT, pilot=True, frames=len(frame_paths))
    depth_view = s2_04.episode_depth_reader(episode_root, cache_dir)

    def frames():
        for index, path in enumerate(frame_paths):
            frame = diag.cache_runner.load_cache_frame(path)
            frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(index, frame)
            yield frame

    started = time.time()
    receipts: list[dict[str, Any]] = []
    state = None
    try:
        for step in lr.run_episode(frames(), episode_id=episode, arm=llm.ARM, config={}, policy=policy["runner"],
                                   descriptor=la.SELECTED_DESCRIPTOR, projector=projector, scorer=scorer):
            receipts.append(step["receipt"])
            state = step["state"]
    except llm.LlmOpStop as exc:
        print(f"[llm-op] pilot {front} stopped ({type(exc).__name__}): {exc.detail}", file=sys.stderr)
        return int(exc.exit_code)
    scorer.close()
    summary = lr.episode_summary(state, receipts)
    payload = {"front": front, "episode_id": episode, "frames": len(receipts), "episode_seal_sha256": seal["payload_sha256"],
               "weights_sha256": weights_sha256, "wall_seconds": round(time.time() - started, 1), "llm_op": scorer.summary(),
               "atoms": summary["atoms"], "illegal_programs": summary["illegal_programs"],
               "final_entities_by_state": summary["final_entities_by_state"], "trajectory_sha256": audit.trajectory_sha256(receipts),
               "archive_sha256": file_sha256(archive), "code_commit": git("rev-parse", "HEAD"), "computes_metrics": False}
    write_json(run_root / "pilot" / f"{front}.json", payload)
    print(f"[llm-op] pilot {front}: {len(receipts)} frames, ${payload['llm_op']['cost_usd']:.4f}, "
          f"fallbacks {payload['llm_op']['association']['fallbacks']}+{payload['llm_op']['existence']['fallbacks']}, "
          f"models {payload['llm_op']['models_seen']}, {payload['wall_seconds']} s")
    return 0


def pilot_report(run_root: Path, plan_: Plan) -> dict[str, Any]:
    """Both front ends' pilots: tokens, latency, format compliance, the returned model and the projection against the cap.

    The cap is checked against the worst case -- every planned call at the peak price -- plus what the pilot itself spent: with
    30 episodes running at once most of the money goes out within a day, so the peak share is not the week's average.  A
    call kind the pilot could not price, a fallback rate above 2% or two model names are decision points too.
    """

    fronts: dict[str, Any] = {}
    models: set[str] = set()
    worst = expected = 0.0
    unpriced: list[str] = []
    format_problems: list[str] = []
    for front in llm.FRONTS:
        payload = load_json(run_root / "pilot" / f"{front}.json")
        stats = payload["llm_op"]
        models.update(stats["models_seen"])
        projection = llm.project_cost(stats, planned_frames=plan_.data["planned_frames"][front],
                                      rows_per_frame=plan_.data["rows_per_frame"][front])
        worst += projection["projected_usd_worst"]
        expected += projection["projected_usd_expected"]
        unpriced += [f"{front}:{kind}" for kind in projection["unpriced_kinds"]]
        for kind in ("association", "existence"):
            rate = stats[kind]["fallback_rate"]
            if rate is not None and rate > llm.FORMAT_UNRELIABLE_FALLBACK_RATE:
                format_problems.append(f"{front}:{kind}:{rate:.3f}")
        fronts[front] = {"frames": payload["frames"], "cost_usd": stats["cost_usd"], "wall_seconds": payload["wall_seconds"],
                         "association": {k: stats["association"][k] for k in ("calls", "attempts", "invalid", "fallbacks", "fallback_rate",
                                                                              "tokens", "latency_s", "skipped_without_rows")},
                         "existence": {k: stats["existence"][k] for k in ("calls", "attempts", "invalid", "fallbacks", "fallback_rate",
                                                                          "tokens", "latency_s", "skipped_without_rows")},
                         "projection": projection, "models_seen": stats["models_seen"]}
    spent = llm.run_spend_usd(run_root)["pilot_usd"]
    total = worst + spent
    return {"stage": llm.STAGE_ID, "written_utc": utc(), "code_commit": git("rev-parse", "HEAD"),
            "plan_sha256": file_sha256(run_root / "plan.json"), "fronts": fronts, "models_seen": sorted(models),
            "model": next(iter(models)) if len(models) == 1 else None, "one_model": len(models) == 1,
            "projected_usd_expected_total": expected, "projected_usd_worst_total": worst, "pilot_spend_usd": spent,
            "projected_total_with_pilot_usd": total, "unpriced": unpriced, "format_problems": format_problems,
            "format_ok": not format_problems, "cap_usd": llm.CAP_USD, "within_cap": total <= llm.CAP_USD and not unpriced}


def pilot(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    require_check(run_root)
    plan_ = Plan(run_root)
    contract = llm.load_contract()
    if not llm.authorized(contract, "pilot_run"):
        print("[llm-op] refused: the contract's pilot_run bit is closed (opened only after the user's code review)", file=sys.stderr)
        return 2
    if (run_root / llm.STOP_FILE).exists():
        print(f"[llm-op] refused: {run_root / llm.STOP_FILE} exists", file=sys.stderr)
        return 2
    logs = run_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    processes = {}
    for front in llm.FRONTS:
        handle = open(logs / f"pilot-{front}.log", "a", encoding="utf-8")
        processes[front] = (subprocess.Popen([sys.executable, str(HERE), "pilot-one", "--run-root", str(run_root), "--front", front],
                                             stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT)), handle)
    codes = {}
    for front, (process, handle) in processes.items():
        codes[front] = process.wait()
        handle.close()
    if any(codes.values()):
        print(f"[llm-op] pilot: a front end did not finish {codes}; see {logs}", file=sys.stderr)
        return 1
    report = pilot_report(run_root, plan_)
    write_json(run_root / "pilot" / "report.json", report)
    if report["one_model"]:
        existing = llm.registered_model(run_root)
        if existing is not None and existing != report["model"]:
            print(f"[llm-op] the pilot saw {report['model']}, model.json holds {existing}; stopping", file=sys.stderr)
            return EXIT_DECISION
        write_json(run_root / llm.MODEL_FILE, {"model": report["model"], "registered_utc": utc(), "from": "pilot"})
    for front, row in report["fronts"].items():
        print(f"[llm-op] pilot {front}: {row['frames']} frames, ${row['cost_usd']:.4f}, association invalid {row['association']['invalid']} "
              f"fallbacks {row['association']['fallbacks']}, existence invalid {row['existence']['invalid']} fallbacks "
              f"{row['existence']['fallbacks']}, latency p50 {row['association']['latency_s']['p50']} / {row['existence']['latency_s']['p50']} s, "
              f"projected ${row['projection']['projected_usd_off_peak']:.2f} off peak, ${row['projection']['projected_usd_worst']:.2f} all at peak")
    print(f"[llm-op] pilot: models {report['models_seen']}; projected ${report['projected_usd_expected_total']:.2f} expected, "
          f"${report['projected_total_with_pilot_usd']:.2f} at worst with the pilot's own spend, against the ${llm.CAP_USD:.0f} cap -> "
          f"{'within' if report['within_cap'] else 'OVER or unpriced: stop and report (ruling 105-8)'}; unpriced {report['unpriced']}; "
          f"format problems {report['format_problems']}")
    return 0 if report["within_cap"] and report["one_model"] and report["format_ok"] else EXIT_DECISION


# --------------------------------------------------------------------------
# the run (validation, 2 front ends x EPISODES_PER_FRONT episodes; one since ruling 108)
# --------------------------------------------------------------------------

def job_id(front: str, episode: str) -> str:
    return f"{front}:{episode}"


def archive_path(run_root: Path, front: str, episode: str) -> Path:
    return run_root / "archive" / front / f"{episode}.jsonl"


def audit_path(run_root: Path, front: str, episode: str) -> Path:
    return run_root / "audit" / front / episode / llm.ARM / "node_audit.json"


def job_command(plan_: Plan, front: str, episode: str, *, mode: str, output_root: Path, python: str = sys.executable) -> list[str]:
    from vsmt import lean_assignment as la

    run_root = plan_.run_root
    return [python, str(NODE_AUDIT), "run", "--metrics-only", "--manifest-split", "validation",
            "--cache-root", str(plan_.cache_root(front, "validation")), "--episode-root", str(plan_.raw_root("validation") / episode),
            "--geometry-root", str(plan_.geometry_root("validation")), "--episode-id", episode, "--arm", llm.ARM, "--config", "{}",
            "--descriptor", la.SELECTED_DESCRIPTOR, "--weights", str(plan_.reid(front)), "--mask-source", llm.FRONTS[front],
            "--device", "cpu", "--output-root", str(output_root), "--llm-op-archive", str(archive_path(run_root, front, episode)),
            "--llm-op-mode", mode, "--llm-op-run-root", str(run_root)]


def ledger_cost(run_root: Path) -> dict[str, Any]:
    """The run's spend so far from the archives' ledgers (main run and pilot), the same sum every worker checks before a call."""

    return llm.run_spend_usd(run_root)


def audit_complete(path: Path, episode: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = load_json(path)
    except ValueError:
        return False
    return payload.get("episode_id") == episode and payload.get("arm") == llm.ARM and isinstance(payload.get("report"), dict) \
        and isinstance(payload.get("llm_op"), dict) and payload.get("metrics_only") is True


def write_stop(run_root: Path, reason: str) -> None:
    llm.write_stop(run_root, reason)


def classify(code: int) -> str:
    return {0: "done", llm.EXIT_STOPPED: "stopped", llm.EXIT_MODEL_CHANGED: "model_changed", llm.EXIT_API_FATAL: "api_fatal",
            llm.EXIT_SERVICE_UNAVAILABLE: "interrupted", llm.EXIT_ARCHIVE: "archive_problem", 2: "refused"}.get(int(code), "failed")


def memory_ok(info: Mapping[str, Any]) -> bool:
    import s3_03_jobs

    held = s3_03_jobs.cgroup_process_bytes()
    if held is None:
        return True
    return held / 2 ** 30 + JOB_MEMORY_GIB <= float(info["memory_bytes"]) / 2 ** 30 - MEMORY_RESERVE_GIB


def run(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    checked = require_check(run_root)
    plan_ = Plan(run_root)
    contract = llm.load_contract()
    if not llm.authorized(contract, "validation_run"):
        print("[llm-op] refused: the contract's validation_run bit is closed (opened only after the user's code review)", file=sys.stderr)
        return 2
    report_path = run_root / "pilot" / "report.json"
    if not report_path.exists():
        print("[llm-op] refused: no pilot report; run the pilot first (ruling 105-8)", file=sys.stderr)
        return 2
    report = load_json(report_path)
    if report.get("plan_sha256") != file_sha256(run_root / "plan.json") or report.get("code_commit") != git("rev-parse", "HEAD"):
        print("[llm-op] refused: the pilot report belongs to another plan or commit; run the pilot again (its archive replays, "
              "nothing is paid twice)", file=sys.stderr)
        return 2
    decision = not (report.get("within_cap") and report.get("format_ok") and report.get("one_model"))
    if decision and not args.accept_pilot:
        print(f"[llm-op] refused: the pilot ended at a decision point (worst-case projection ${report['projected_total_with_pilot_usd']:.2f} "
              f"against ${llm.CAP_USD:.0f}, unpriced {report['unpriced']}, format problems {report['format_problems']}, models "
              f"{report['models_seen']}); the user decides (then --accept-pilot)", file=sys.stderr)
        return EXIT_DECISION
    model = llm.registered_model(run_root)
    if model is None:
        print("[llm-op] refused: no model.json (the pilot registers the model name)", file=sys.stderr)
        return 2
    state_path = run_root / "run.json"
    state = load_json(state_path) if state_path.exists() else {"jobs": {}, "events": []}
    stop = run_root / llm.STOP_FILE
    if stop.exists():
        if not args.resume_after_stop:
            print(f"[llm-op] refused: {stop} exists ({stop.read_text(encoding='utf-8').strip()}); resume only after the user decides "
                  "(--resume-after-stop)", file=sys.stderr)
            return EXIT_DECISION
        kept = stop.with_name(f"STOP.{len([p for p in run_root.glob('STOP.*')]) + 1}")
        stop.replace(kept)
        state["events"].append({"utc": utc(), "event": "resumed_after_stop", "stop_kept_as": kept.name})
    if args.accept_pilot and decision:
        state["events"].append({"utc": utc(), "event": "pilot_decision_accepted", "projected_usd": report["projected_total_with_pilot_usd"],
                                "unpriced": report["unpriced"], "format_problems": report["format_problems"]})
    info = resources()
    workers = choose_workers(info, len(plan_.episodes) * len(llm.FRONTS), args.workers)
    jobs = sorted(((front, episode) for episode in plan_.episodes for front in llm.FRONTS),
                  key=lambda item: (-plan_.frames(item[1]), list(llm.FRONTS).index(item[0]), item[1]))
    blocked = [job_id(*j) for j in jobs if state["jobs"].get(job_id(*j), {}).get("status") in ("failed", "refused", "archive_problem")]
    if blocked and not args.retry_failed:
        print(f"[llm-op] refused: earlier failures {blocked}; inspect the logs, then --retry-failed", file=sys.stderr)
        return 1
    pending = [j for j in jobs if not audit_complete(audit_path(run_root, *j), j[1])]
    for front, episode in jobs:
        if audit_complete(audit_path(run_root, front, episode), episode):
            state["jobs"].setdefault(job_id(front, episode), {})["status"] = "done"
    running: dict[str, tuple[subprocess.Popen, Any, tuple[str, str]]] = {}
    logs = run_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    state.update({"stage": llm.STAGE_ID, "driver": STAGE, "code_commit": git("rev-parse", "HEAD"), "model": model,
                  "workers": workers, "resources": info, "check_utc": checked["checked_utc"]})

    def started(job: tuple[str, str]) -> bool:
        """An episode that has made calls (or was started) is not new: the cap does not hold it back, only a STOP does."""

        return archive_path(run_root, *job).exists() or int(state["jobs"].get(job_id(*job), {}).get("starts") or 0) > 0

    def terminate(signum: int, frame: Any) -> None:
        raise SystemExit(128 + int(signum))

    handlers = {sig: signal.signal(sig, terminate) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        return _run_loop(run_root, plan_, state, state_path, jobs, pending, running, logs, workers, info, stop, started)
    except BaseException as exc:  # the driver going away must not leave the workers unattended
        llm.write_stop(run_root, f"driver_ended:{type(exc).__name__}; every worker stops before its next call")
        state.setdefault("events", []).append({"utc": utc(), "event": "driver_ended", "reason": type(exc).__name__})
        try:
            write_json(state_path, state)
        except OSError:
            pass
        raise
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def _run_loop(run_root: Path, plan_: Plan, state: dict[str, Any], state_path: Path, jobs: list[tuple[str, str]],
              pending: list[tuple[str, str]], running: dict[str, Any], logs: Path, workers: Mapping[str, Any],
              info: Mapping[str, Any], stop: Path, started: Any) -> int:
    halt = False
    while True:
        for key in list(running):
            process, handle, (front, episode) = running[key]
            code = process.poll()
            if code is None:
                continue
            handle.close()
            status = classify(code)
            if status == "done" and not audit_complete(audit_path(run_root, front, episode), episode):
                status = "failed"
            row = state["jobs"].setdefault(key, {})
            row.update({"status": status, "exit_code": code, "finished_utc": utc()})
            del running[key]
            if status in ("model_changed", "api_fatal"):
                write_stop(run_root, f"{status} in {key} (exit {code}); see logs/{front}-{episode}.log")
            if status in ("failed", "refused", "archive_problem"):
                halt = True  # an engineering failure: no new job until the user has looked
        cost = ledger_cost(run_root)  # read after the finished jobs' last calls, before any start
        if cost["total_usd"] >= llm.SAFETY_STOP_USD and not stop.exists():
            write_stop(run_root, f"safety_stop_usd:{llm.SAFETY_STOP_USD} reached (ledger ${cost['total_usd']:.2f})")
            state["events"].append({"utc": utc(), "event": "safety_stop", "ledger_usd": cost["total_usd"]})
        can_dispatch = not halt and not stop.exists()
        # the memory guard waits only while this run's own processes hold memory (the S3-03 pool's rule); at the cap no new
        # episode starts, but one that has already made calls resumes (ruling 105-8: running episodes finish)
        while can_dispatch and len(running) < workers["actual"] and (not running or memory_ok(info)):
            choice = next((job for job in pending if cost["total_usd"] < llm.CAP_USD or started(job)), None)
            if choice is None:
                break
            pending.remove(choice)
            front, episode = choice
            key = job_id(front, episode)
            handle = open(logs / f"{front}-{episode}.log", "a", encoding="utf-8")
            handle.write(f"\n=== start {utc()} ===\n")
            handle.flush()
            command = job_command(plan_, front, episode, mode="live", output_root=run_root / "audit" / front)
            try:
                process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT))
            except BaseException:
                handle.close()
                raise
            running[key] = (process, handle, (front, episode))
            row = state["jobs"].setdefault(key, {})
            row.update({"status": "running", "started_utc": utc(), "starts": int(row.get("starts") or 0) + 1, "pid": process.pid})
        state.update({"updated_utc": utc(), "cost": cost, "running": sorted(running), "pending": [job_id(*j) for j in pending],
                      "stop": stop.read_text(encoding="utf-8").strip() if stop.exists() else None, "halted_on_failure": halt})
        write_json(state_path, state)
        startable = can_dispatch and any(cost["total_usd"] < llm.CAP_USD or started(job) for job in pending)
        if not running and not startable:
            break
        time.sleep(POLL_SECONDS)
    done = sum(1 for j in jobs if audit_complete(audit_path(run_root, *j), j[1]))
    print(f"[llm-op] run: {done}/{len(jobs)} episodes done, ledger ${state['cost']['total_usd']:.2f}"
          f"{'; STOP: ' + state['stop'] if state['stop'] else ''}{'; halted on a failure' if halt else ''}")
    return 0 if done == len(jobs) else (1 if halt else EXIT_DECISION)


def stop_run(args: argparse.Namespace) -> int:
    """The user's stop: STOP in the run root; every worker stops before its next call and a later run waits for the user."""

    wrote = llm.write_stop(Path(args.run_root), "stopped by the user (llm_op.sh stop)")
    print(f"[llm-op] {'STOP written' if wrote else 'STOP was already there'}: {Path(args.run_root) / llm.STOP_FILE}")
    return 0


def status(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    plan_ = Plan(run_root)
    state = load_json(run_root / "run.json") if (run_root / "run.json").exists() else {"jobs": {}}
    cost = ledger_cost(run_root)
    print(f"[llm-op] ledger: main ${cost['main_usd']:.2f}, pilot ${cost['pilot_usd']:.2f}, total ${cost['total_usd']:.2f} "
          f"(cap ${llm.CAP_USD:.0f}, safety stop ${llm.SAFETY_STOP_USD:.0f}); model {llm.registered_model(run_root)}")
    stop = run_root / llm.STOP_FILE
    if stop.exists():
        print(f"[llm-op] STOP: {stop.read_text(encoding='utf-8').strip()}")
    for episode in plan_.episodes:
        for front in llm.FRONTS:
            ledger = archive_path(run_root, front, episode).with_name(f"{episode}.jsonl.ledger.json")
            last = load_json(ledger).get("last_tick") if ledger.exists() else None
            row = state["jobs"].get(job_id(front, episode), {})
            done = audit_complete(audit_path(run_root, front, episode), episode)
            print(f"  {front:8s} {episode}  {'done' if done else row.get('status', 'pending'):14s} last tick {last} / {plan_.frames(episode)}")
    return 0


# --------------------------------------------------------------------------
# export and the replay check
# --------------------------------------------------------------------------

def call_totals(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summed LLM-op call statistics over a front end's episodes, with the fallback rates ruling 105-6 reports."""

    out: dict[str, Any] = {}
    for kind in ("association", "existence"):
        total = {"calls": 0, "attempts": 0, "fallbacks": 0, "skipped_without_rows": 0, "rows": 0, "invalid": {},
                 "tokens": {"input_cache_hit": 0, "input_cache_miss": 0, "output": 0, "reasoning": 0}, "cost_usd": 0.0}
        for row in rows:
            stats = row[kind]
            for name in ("calls", "attempts", "fallbacks", "skipped_without_rows", "rows"):
                total[name] += int(stats[name])
            for reason, count in stats["invalid"].items():
                total["invalid"][reason] = total["invalid"].get(reason, 0) + int(count)
            for name, value in stats["tokens"].items():
                total["tokens"][name] += int(value)
            total["cost_usd"] += float(stats["cost_usd"])
        total["fallback_rate"] = total["fallbacks"] / total["calls"] if total["calls"] else None
        total["invalid"] = dict(sorted(total["invalid"].items()))
        total["cost_usd"] = round(total["cost_usd"], 6)
        out[kind] = total
    rates = [out[kind]["fallback_rate"] for kind in out if out[kind]["fallback_rate"] is not None]
    out["format_unreliable"] = any(rate > llm.FORMAT_UNRELIABLE_FALLBACK_RATE for rate in rates)
    return out


def export(args: argparse.Namespace) -> int:
    import lean_s2_05_node_audit as audit

    run_root = Path(args.run_root)
    plan_ = Plan(run_root)
    missing = [job_id(front, e) for e in plan_.episodes for front in llm.FRONTS if not audit_complete(audit_path(run_root, front, e), e)]
    if missing:
        print(f"[llm-op] refused: {len(missing)} episodes unfinished: {missing}", file=sys.stderr)
        return EXIT_DECISION
    replayed = load_json(run_root / "replay" / "check.json") if (run_root / "replay" / "check.json").exists() else {}
    unchecked = [front for front in llm.FRONTS
                 if not (replayed.get(front, {}).get("same_trajectory") and replayed.get(front, {}).get("same_metrics"))]
    if unchecked:
        print(f"[llm-op] refused: no passed replay-check for {unchecked}; run replay-check first (before export, while the checkout "
              "is clean)", file=sys.stderr)
        return EXIT_DECISION
    fronts: dict[str, Any] = {}
    commits: set[str] = set()
    models: set[str] = set()
    for front in llm.FRONTS:
        rows = []
        for episode in plan_.episodes:
            payload = load_json(audit_path(run_root, front, episode))
            commits.add(str(payload["code_commit"]))
            models.update(payload["llm_op"]["models_seen"])
            rows.append({"episode_id": episode, "frames": payload["frames"], "report": payload["report"],
                         "trajectory_sha256": payload["trajectory_sha256"], "decomposition_totals": payload["decomposition_totals"],
                         "final_entities_by_state": payload["final_entities_by_state"], "llm_op": payload["llm_op"]})
        merged = audit.merge_audits(run_root / "audit" / front, llm.ARM)
        fronts[front] = {"mask_source": llm.FRONTS[front], "episodes": rows, "merged": merged,
                         "calls": call_totals([row["llm_op"] for row in rows])}
    result = {
        "stage": llm.STAGE_ID, "driver": STAGE, "ruling": llm.RULING, "exported_utc": utc(), "code_commits": sorted(commits),
        "contract_sha256": file_sha256(llm.CONTRACT_PATH), "model": sorted(models), "one_model": len(models) == 1,
        "plan": {key: plan_.data[key] for key in ("draw", "pilot", "planned_frames", "rows_per_frame", "inputs", "reid", "code_commit")},
        "check": {key: load_json(run_root / "check.json")[key] for key in ("checked_utc", "resources", "workers", "api", "code_commit")},
        "pilot": load_json(run_root / "pilot" / "report.json"), "cost": ledger_cost(run_root), "replay_check": replayed,
        "run": {key: value for key, value in load_json(run_root / "run.json").items() if key in ("events", "workers", "jobs")},
        "fronts": fronts,
        "appendix_only": "never in the main table, never on test; compare with every other arm on these episodes only (ruling 105-2)",
    }
    out = Path(args.out)
    write_json(out, result)
    print(f"[llm-op] export: {out} ({', '.join(f'{f}: format unreliable {fronts[f]['calls']['format_unreliable']}' for f in fronts)}; "
          f"models {sorted(models)}; ledger ${result['cost']['total_usd']:.2f})")
    return 0


def replay_one(plan_: Plan, front: str, episode: str) -> dict[str, Any]:
    """One episode replayed from its archive alone (no API call can happen) against its run of record."""

    import lean_s2_05_node_audit as audit

    run_root = plan_.run_root
    record_path = audit_path(run_root, front, episode)
    _require(audit_complete(record_path, episode), f"no_finished_run_of_record:{front}:{episode}")
    scratch = run_root / "replay" / front
    target = scratch / episode / llm.ARM / "node_audit.json"
    if target.exists():
        target.unlink()
    code = subprocess.call(job_command(plan_, front, episode, mode="replay", output_root=scratch), cwd=str(ROOT))
    row: dict[str, Any] = {"front": front, "episode_id": episode, "exit_code": code, "checked_utc": utc(),
                           "code_commit": git("rev-parse", "HEAD")}
    if code != 0 or not target.exists():
        return {**row, "same_trajectory": False, "same_metrics": False}
    record, replay = load_json(record_path), load_json(target)
    return {**row, "same_trajectory": record["trajectory_sha256"] == replay["trajectory_sha256"],
            "same_metrics": audit.comparable_metrics({k: v for k, v in record.items() if k != "llm_op"})
            == audit.comparable_metrics({k: v for k, v in replay.items() if k != "llm_op"}),
            "replayed_attempts": replay["llm_op"]["association"]["replayed_attempts"] + replay["llm_op"]["existence"]["replayed_attempts"],
            "attempts": replay["llm_op"]["association"]["attempts"] + replay["llm_op"]["existence"]["attempts"]}


def replay_check(args: argparse.Namespace) -> int:
    """Ruling 105-7: replayed from its archive alone, an episode reproduces its run of record's trajectory and metrics byte for byte.

    Without --front/--episode it replays, per front end, the drawn episode with the fewest frames.  It runs before export:
    export writes into results/, after which the checkout is no longer clean and the replay's audit would refuse.
    """

    run_root = Path(args.run_root)
    plan_ = Plan(run_root)
    if args.front or args.episode:
        _require(bool(args.front and args.episode), "give_both_front_and_episode")
        targets = [(args.front, args.episode)]
    else:
        shortest = min(plan_.episodes, key=lambda e: (plan_.frames(e), e))
        targets = [(front, shortest) for front in llm.FRONTS]
    path = run_root / "replay" / "check.json"
    record = load_json(path) if path.exists() else {}
    ok = True
    for front, episode in targets:
        row = replay_one(plan_, front, episode)
        record[front] = row
        ok = ok and row["same_trajectory"] and row["same_metrics"]
        print(f"[llm-op] replay-check {front} {episode}: exit {row['exit_code']}, trajectory "
              f"{'same' if row['same_trajectory'] else 'DIFFERS'}, metrics {'same' if row['same_metrics'] else 'DIFFER'}")
    write_json(path, record)
    return 0 if ok else EXIT_DECISION


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--run-root", required=True)
    p.add_argument("--inputs", required=True, help="the S3-03 check's inputs.json (its usable train and validation lists and roots)")
    p.add_argument("--allow-provisional", action="store_true", help="plan from provisional S3-03 inputs (recorded in the plan)")
    p.add_argument("--supersede", action="store_true",
                   help="ruling 108: replace a plan written for another episode count (kept as plan.superseded.<sha12>.json)")
    p.set_defaults(func=plan)
    p = sub.add_parser("check")
    p.add_argument("--run-root", required=True)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--allow-dirty", action="store_true", help="tests only")
    p.set_defaults(func=check)
    p = sub.add_parser("pilot")
    p.add_argument("--run-root", required=True)
    p.set_defaults(func=pilot)
    p = sub.add_parser("pilot-one")
    p.add_argument("--run-root", required=True)
    p.add_argument("--front", required=True, choices=tuple(llm.FRONTS))
    p.set_defaults(func=pilot_one)
    p = sub.add_parser("run")
    p.add_argument("--run-root", required=True)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--accept-pilot", action="store_true",
                   help="the user accepted the pilot's decision point (projection over the cap, an unpriced call kind, format problems)")
    p.add_argument("--resume-after-stop", action="store_true", help="the user decided to go on after a STOP (kept as STOP.<n>)")
    p.add_argument("--retry-failed", action="store_true")
    p.set_defaults(func=run)
    p = sub.add_parser("status")
    p.add_argument("--run-root", required=True)
    p.set_defaults(func=status)
    p = sub.add_parser("stop")
    p.add_argument("--run-root", required=True)
    p.set_defaults(func=stop_run)
    p = sub.add_parser("export")
    p.add_argument("--run-root", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=export)
    p = sub.add_parser("replay-check")
    p.add_argument("--run-root", required=True)
    p.add_argument("--front", default=None, choices=tuple(llm.FRONTS))
    p.add_argument("--episode", default=None)
    p.set_defaults(func=replay_check)
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (DriverError, llm.LlmOpError) as exc:
        print(f"[llm-op] refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
