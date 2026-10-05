"""S3-04 (ruling 106, 2026-10-05): the configuration choice on validation and the freeze before test, as pure functions.

白话：裁决 106 把 S3-04 写定为"每套前端每个臂拿哪个配置去考 test、考 test 那天跑哪份代码与哪些权重"。这个模块把其中可测试的
部分写成纯函数，供 ``ops/vsmt/s3_04_manifest.py`` 的各步调用：
  * 选择（106-2）：在 S3-03 的选参读数上对每个臂调用 ``lean_arms.select_configuration``（102-4 的约束、节点 F1、并列取编号小），
    并给出只报告的项（约束不可满足、缺种子、选中点落在网格端点）；
  * 读数复算（106-3 G2）：从合并审计重算的读数与 S3-03 记下的读数逐值比较；
  * 共同事件（G3）：身份连续率与检索成功率的事件数在全部运行里只能有一个值；
  * 复现探针的 episode（G4）：帧数最少、且至少有 1 个身份连续率事件的 2 条 validation episode；
  * test 运行清单（106-4）：每套前端每条 test episode 25 个运行（5 个规则臂各 1 个配置、4 个学习臂各 5 个种子）；
  * 代码摘要（106-4）：受 Git 跟踪的 src/、ops/、configs/ 每个文件的 sha256 与总摘要；S3-05 入口用 ``verify_freeze`` 逐项重算。
输入是读数、清单与文件内容，输出是选择、差异清单与回执各块。例如实例分割前端 VSMT-lean 十个 τ_r 里 validation Missing 残留率
都高于 AssocOnly，选择就取节点 F1 最大的那个并记 constraint_not_satisfiable，回执里写明它不能支持"撤回减少了陈旧实体"。
它不读 test、不训练、不算主门、不比较哪个臂赢。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

STAGE = "vsmt.lean.s3_04.v1"
#: front key -> mask source; both front ends are frozen together, before either test root is unsealed (ruling 106-1 (a))
FRONTS = {"instance": "simulator_instance_masks", "sam2": "sam2"}
#: the directories whose every Git-tracked file S3-05 may execute or read as a rule (ruling 106-4)
CODE_DIRECTORIES = ("src", "ops", "configs")
#: the arms S3-05 runs on test (ruling 102-2 / PLAN S3-05: the five arms of the main table and the four ablations)
TEST_RULE_ARMS = ("TAF", "ELU-P", "RAC", "LOW", "HandCost")
TEST_LEARNED_ARMS = ("VSMT-lean", "NoVersion", "HeuristicLabel", "AssocOnly")
NOT_FROZEN = {
    "VSMT-lean-ctx": "optional arm, never trained in S3-03 (D-224-EFG): not frozen, not run on test",
    "LLM-op": "appendix arm, validation only (S0-05 appendix_arm, ruling 105): not frozen, not run on test",
}
#: G3: the events of these metrics depend only on the front end and the private labels (rulings 102-0, 102-5)
EVENT_METRICS = ("identity_continuity", "retrieval_success")
#: G4: how many validation episodes the frozen code reruns per front end
PROBE_EPISODES_PER_FRONT = 2

SELECTION_RULE = (
    "ruling 106-2: per front end every arm chooses on its own validation readings with lean_arms.select_configuration (ruling 102-4: "
    "the six arms with RETRACT only among configurations whose Missing residual rate is below the same front end's AssocOnly, "
    "node F1 on the main node column, ties to the smallest index; NoVersion and HeuristicLabel choose their own tau_r); learned arms "
    "and AssocOnly read the mean over the seeds present, a missing seed is named and the S3-05 gate involving that arm is not "
    "evaluable (ruling 102-9); a constraint that cannot be met takes the node-F1 maximum and is recorded (ruling 102-1 bounds the "
    "claim); VSMT-lean-ctx and LLM-op are not frozen"
)
CHECKS_RULE = (
    "ruling 106-3: G1 S3-03's verify at the registration commit reported no problem, its exports equal its manifest and every "
    "round-1 weights file equals its training receipt; G2 the readings recomputed by the frozen code from the merged audits equal "
    "S3-03's value for value; G3 the identity-continuity and retrieval-success event counts take one value over every run of a "
    "front end; G4 the frozen code reruns every selected run (learned arms at every seed) on the two validation episodes with the "
    "fewest frames among those with an identity-continuity event and reproduces S3-03's audits bit for bit (wall time, commit and "
    "head path excluded); G5 the four test roots still carry sealed markers with the seal digest S3-02 exported (marker files only). "
    "All five must pass before a freeze receipt is written; a failure stops for a read-only diagnosis and a ruling, never a wider line"
)
FREEZE_CHANGE_RULE = (
    "ruling 106-4 (a): src/ and configs/ never change after the freeze; before the test roots are unsealed an operations-only fix "
    "(ops/) is followed by a complete new S3-04 run whose selection must equal the previous receipt bit for bit, the difference "
    "recorded; after unsealing any change needs a ruling first and is recorded as a deviation"
)
PUBLICATION_RULE = (
    "ruling 106-5 (a): the freeze receipt and its exports are committed to results/ and pushed to main and s1-02a-runner, and the "
    "user confirms, before S3-05 unseals any test root"
)


class LeanS3_04Error(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS3_04Error(code)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def as_json(value: Any) -> Any:
    """The value as it reads back from a JSON file (tuples become lists, keys strings), so a recomputation compares to a file."""

    return json.loads(json.dumps(value, sort_keys=True))


# --------------------------------------------------------------------------
# selection (ruling 106-2)
# --------------------------------------------------------------------------

def grid_edge(arm: str, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Report only (ruling 102-6 keeps the grids): the grid parameters whose chosen value is the first or last of its frozen list."""

    from vsmt import lean_arms as arms

    edges = []
    for name in arms.GRID_PARAMETERS[arm]:
        values = list(arms.FROZEN_GRIDS[arm][name])
        if len(values) < 2:
            continue
        position = values.index(config[name])
        if position in (0, len(values) - 1):
            edges.append({"parameter": name, "value": config[name], "position": "first" if position == 0 else "last"})
    return edges


def select_front(readings: Mapping[str, Any]) -> dict[str, Any]:
    """Ruling 106-2: every arm's one configuration of one front end from S3-03's selection readings."""

    from vsmt import lean_arms as arms
    from vsmt import lean_s3_03 as s3

    reference = readings["reference"][arms.SELECTION_CONSTRAINT_METRIC]
    absent = dict(readings.get("arms_absent") or {})
    chosen: dict[str, Any] = {}
    for arm in s3.SELECTION_ARMS:
        if arm in absent:
            chosen[arm] = {"absent": True, "why": absent[arm]}
            continue
        choice = arms.select_configuration(s3.selection_validation(readings, arm), arm=arm, reference_missing_residual_rate=reference)
        row = readings["readings"][arm][str(choice["selected"])]
        chosen[arm] = {**choice, "absent": False, "config": dict(row["config"]), "seeds_present": list(row["seeds_present"]),
                       "seeds_missing": list(row["seeds_missing"]), "validation_mean": dict(row["mean"]),
                       "validation_per_seed": dict(row["per_seed"]), "grid_edge": grid_edge(arm, row["config"])}
    report = {
        "constraint_not_satisfiable": sorted(arm for arm, row in chosen.items() if row.get("constraint_satisfiable") is False),
        "seeds_missing": {arm: row["seeds_missing"] for arm, row in chosen.items() if row.get("seeds_missing")},
        "arms_absent": sorted(absent),
        "grid_edge": {arm: row["grid_edge"] for arm, row in chosen.items() if row.get("grid_edge")},
        "consequences": ("report only, consequences fixed before the freeze: constraint_not_satisfiable -> the arm's result cannot "
                         "support 'its retraction reduces stale entities', and on VSMT-lean no primary claim (rulings 102-1, 102-4); "
                         "a missing seed -> the S3-05 gate involving the arm is not evaluable (ruling 102-9); a grid edge -> reported "
                         "beside the grid, the grids stay (ruling 102-6)"),
    }
    return {"stage": STAGE, "rule": SELECTION_RULE, "mask_source": readings["mask_source"],
            "reference": dict(readings["reference"]), "arms": chosen, "report_only": report, "not_frozen": dict(NOT_FROZEN)}


# --------------------------------------------------------------------------
# G2 / G3 / G4 inputs
# --------------------------------------------------------------------------

def differences(left: Any, right: Any, path: str = "", limit: int = 20) -> list[str]:
    """Paths where two JSON values differ (at most ``limit``)."""

    out: list[str] = []

    def walk(a: Any, b: Any, where: str) -> None:
        if len(out) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    out.append(f"{where}.{key}:missing_on_{'left' if key not in a else 'right'}")
                else:
                    walk(a[key], b[key], f"{where}.{key}")
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for index, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{where}[{index}]")
        elif type(a) is not type(b) or a != b:  # strict: 1 against 1.0 or True against 1 is a difference too
            out.append(where or ".")

    walk(left, right, path)
    return out[:limit]


def readings_differences(recorded: Mapping[str, Any], recomputed: Mapping[str, Any]) -> list[str]:
    """G2: S3-03's selection readings against the recomputation (the file's own front and time stamp aside)."""

    kept = {key: value for key, value in recorded.items() if key not in ("front", "written_utc")}
    return differences(as_json(kept), as_json(recomputed))


def event_problems(readings: Mapping[str, Any]) -> list[str]:
    """G3: each event metric has one event count over every run of the front end (rulings 102-0, 102-5)."""

    problems = []
    for metric in EVENT_METRICS:
        block = (readings.get("key_events") or {}).get(metric) or {}
        if block.get("equal_across_runs") is not True:
            problems.append(f"events_differ_across_runs:{metric}:{block.get('events_per_run')}")
    return problems


def probe_episodes(reports: Mapping[str, Mapping[str, Any]], frames: Mapping[str, int],
                   count: int = PROBE_EPISODES_PER_FRONT) -> list[str]:
    """G4: the ``count`` validation episodes with the fewest frames among those with an identity-continuity event (ties by id)."""

    with_events = [episode for episode, report in reports.items() if int(report["identity_continuity"]["events"]) >= 1]
    _require(bool(with_events), "probe_needs_an_episode_with_an_identity_event")
    return sorted(with_events, key=lambda episode: (int(frames[episode]), episode))[:count]


def heads_arm(arm: str) -> str:
    """Whose trained heads a learned arm runs: NoVersion runs VSMT-lean's (rulings 99-1, 104-1 1d)."""

    return "VSMT-lean" if arm == "NoVersion" else arm


def test_runs(selection: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Ruling 106-4: the runs S3-05 makes on every test episode of one front end, in a fixed order."""

    rows = []
    for arm in (*TEST_RULE_ARMS, *TEST_LEARNED_ARMS):
        row = selection["arms"][arm]
        if row.get("absent"):
            continue
        seeds: Sequence[int | None] = row["seeds_present"] if arm in TEST_LEARNED_ARMS else (None,)
        for seed in seeds:
            rows.append({"arm": arm, "config_index": int(row["selected"]), "config": dict(row["config"]), "seed": seed,
                         "heads_arm": heads_arm(arm) if seed is not None else None})
    return rows


# --------------------------------------------------------------------------
# the test-executable code digest (ruling 106-4)
# --------------------------------------------------------------------------

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def code_digest(root: Path, files: Iterable[str]) -> dict[str, Any]:
    """Every listed file (relative to ``root``) with its sha256, and one digest over the list."""

    listed = sorted(set(str(name) for name in files))
    _require(bool(listed), "code_digest_needs_files")
    _require(all(name.split("/", 1)[0] in CODE_DIRECTORIES for name in listed), "code_digest_file_outside_the_code_directories")
    per_file = {name: file_sha256(Path(root) / name) for name in listed}
    return {"directories": list(CODE_DIRECTORIES), "files": per_file, "file_count": len(per_file), "sha256": canonical_sha256(per_file)}


def code_differences(recorded: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Files added, removed or changed since the freeze (empty when the code is the frozen code)."""

    old, new = dict(recorded["files"]), dict(current["files"])
    out = [f"added:{name}" for name in sorted(set(new) - set(old))]
    out += [f"removed:{name}" for name in sorted(set(old) - set(new))]
    out += [f"changed:{name}" for name in sorted(set(old) & set(new)) if old[name] != new[name]]
    return out


def receipt_body_sha256(receipt: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})


def statistics_plan() -> dict[str, Any]:
    """What S3-05 computes on test (rulings 102-2, 102-3, 102-5), named so that the S3-05 code is held to it."""

    from vsmt import lean_teacher as lt

    return {
        "primary_gate": {"function": "lean_teacher.primary_gate", "comparison": list(lt.PRIMARY_COMPARISON),
                         "metrics": [list(item) for item in lt.MAIN_GATE], "seeds": list(lt.GATE_SEEDS),
                         "rule": lt.MAIN_GATE_RULE},
        "fixed_sequence": {"function": "lean_teacher.fixed_sequence", "steps": [[front, list(metrics)] for front, metrics in lt.FIXED_SEQUENCE],
                           "rule": lt.FIXED_SEQUENCE_RULE},
        "original_gate": {"function": "lean_teacher.original_gate", "role": "reported, never gating; strongest control per metric on test"},
        "ablations": {"function": "lean_teacher.ablation_report", "arms": list(lt.ABLATION_ARMS), "role": "reported, never gating"},
        "bootstrap_seed": lt.BOOTSTRAP_SEED, "bootstrap_iterations": lt.BOOTSTRAP_ITERATIONS,
        "confidence_one_sided": lt.CONFIDENCE_ONE_SIDED,
        "eighth_metric": "retrieval_success (ruling 102-5), computed with the others, no gate, no selection",
    }


def verify_freeze(receipt: Mapping[str, Any], *, code: Mapping[str, Any], heads: Mapping[str, str],
                  registered_values: Mapping[str, Mapping[str, Any]], test_manifest_sha256: str) -> list[str]:
    """What S3-05's entry checks before it unseals: the receipt is whole, the code and every frozen byte are the frozen ones.

    ``heads`` maps each frozen weights path to its current file sha256; ``registered_values`` the S0-05 ELU-P values per front.
    """

    problems = []
    if receipt_body_sha256(receipt) != receipt.get("receipt_sha256"):
        problems.append("freeze_receipt_digest_differs")
    problems += [f"code_{item}" for item in code_differences(receipt["code"], code)][:20]
    for path, digest in sorted(receipt["frozen_bytes"]["heads"].items()):
        if heads.get(path) != digest:
            problems.append(f"heads_file_differs:{path}")
    for front, values in receipt["frozen_bytes"]["elu_p_registered"].items():
        if dict(registered_values.get(front) or {}) != dict(values):
            problems.append(f"elu_p_values_differ:{front}")
    if receipt["frozen_bytes"]["test_manifest_sha256"] != test_manifest_sha256:
        problems.append("test_manifest_differs")
    return problems


def test_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """The digest of the committed test house list (the list, not any test data)."""

    return canonical_sha256(sorted(str(house) for house in manifest["test"]))


__all__ = [
    "CHECKS_RULE",
    "CODE_DIRECTORIES",
    "EVENT_METRICS",
    "FREEZE_CHANGE_RULE",
    "FRONTS",
    "LeanS3_04Error",
    "NOT_FROZEN",
    "PROBE_EPISODES_PER_FRONT",
    "PUBLICATION_RULE",
    "SELECTION_RULE",
    "STAGE",
    "TEST_LEARNED_ARMS",
    "TEST_RULE_ARMS",
    "as_json",
    "canonical_sha256",
    "code_differences",
    "code_digest",
    "differences",
    "event_problems",
    "file_sha256",
    "grid_edge",
    "heads_arm",
    "probe_episodes",
    "readings_differences",
    "receipt_body_sha256",
    "select_front",
    "statistics_plan",
    "test_manifest_sha256",
    "test_runs",
    "verify_freeze",
]
