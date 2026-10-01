#!/usr/bin/env python3
"""Ruling 97 (a): verify the frozen inputs of the confirmation run and write its group plan and episode list (read-only).

白话：确认集只读一次，所以开跑前把冻结清单（`ops/vsmt/ruling97_freeze.json`）逐项核对：15 个头文件各自的权重摘要必须等于冻结值，
并且能按自身摘要加载；四个规则臂的配置必须等于代码里登记的开发配置；确认集名单的摘要必须等于冻结值；评估的 episode 是名单里
同时有 episode、oracle cache 与几何重载目录的 house，个数必须等于冻结的 43（其余按缺失记录，不补不换）。输出 19 个组的计划
（组名、臂、配置、头文件路径）与 episode 名单。例如某个 AssocOnly 头的摘要与冻结值不同，就退出码 3，链停下、不跑任何审计。
它不读任何评估结果，也不改任何文件。

Usage:
  python ops/vsmt/ruling97_verify.py --freeze ops/vsmt/ruling97_freeze.json --autodl-root /root/autodl-tmp \
      --plan <tsv> --episodes <txt> --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

STAGE = "vsmt.lean.ruling97.verify.v1"


def verify(freeze: dict[str, Any], autodl: Path, repo: Path) -> dict[str, Any]:
    from vsmt import lean_model as model
    import lean_s2_05_development as dev

    problems: list[str] = []
    plan: list[tuple[str, str, dict[str, Any], str]] = []
    for name, spec in freeze["arms"].items():
        if name == "rule arms":
            for arm, config in spec.items():
                if dev.expected_pass_config("dagger_round_0" if arm == "ELU-P" else "development_table", arm) != config:
                    problems.append(f"rule_config_changed:{arm}")
                plan.append((f"RULE-{arm}", arm, config, ""))
            continue
        for seed, head in sorted(spec["heads"].items(), key=lambda item: int(item[0])):
            group, path = f"{spec['group']}-A{seed}", autodl / head["path"]
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                model.load_heads(payload)  # refuses a digest that does not match the content
                if payload.get("sha256") != head["sha256"]:
                    problems.append(f"digest_differs:{group}")
            except Exception as exc:  # a missing or unreadable file is a failed check, not a crash
                problems.append(f"head_unreadable:{group}:{type(exc).__name__}")
            plan.append((group, spec["arm"], spec["config"], str(path)))
    listed = json.loads((repo / freeze["confirmation_houses"]["file"]).read_text(encoding="utf-8"))
    if listed["houses_sha256"] != freeze["confirmation_houses"]["houses_sha256"]:
        problems.append("confirmation_list_changed")
    roots = {key: autodl / value for key, value in freeze["data_roots"].items()}
    episodes = [h for h in listed["houses"] if all((roots[key] / h).is_dir() for key in ("episodes", "cache", "geometry"))]
    missing = [h for h in listed["houses"] if h not in episodes]
    expected = int(freeze["confirmation_houses"]["expected_evaluated"])
    if len(episodes) != expected:
        problems.append(f"evaluated_episodes:{len(episodes)}_expected:{expected}")
    return {"problems": problems, "plan": plan, "episodes": episodes, "missing": missing}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--autodl-root", required=True)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--episodes", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    freeze_path = Path(args.freeze)
    result = verify(json.loads(freeze_path.read_text(encoding="utf-8")), Path(args.autodl_root), Path(args.repo_root))
    Path(args.plan).write_text("".join(f"{g}\t{a}\t{json.dumps(c)}\t{h}\n" for g, a, c, h in result["plan"]), encoding="utf-8")
    Path(args.episodes).write_text("".join(f"{e}\n" for e in result["episodes"]), encoding="utf-8")
    report = {"stage": STAGE, "freeze_sha256": hashlib.sha256(freeze_path.read_bytes()).hexdigest(), "problems": result["problems"],
              "groups": [g for g, _, _, _ in result["plan"]], "evaluated_episodes": result["episodes"], "missing_houses": result["missing"],
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"[ruling97-verify] {len(result['plan'])} groups, {len(result['episodes'])} episodes, {len(result['missing'])} missing houses; "
          f"problems: {result['problems'] or 'none'}")
    return 0 if not result["problems"] else 3


if __name__ == "__main__":
    sys.exit(main())
