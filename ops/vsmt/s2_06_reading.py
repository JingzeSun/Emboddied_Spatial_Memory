#!/usr/bin/env python3
"""S2-06 reading (ruling 100-3, registered before the run): the SAM 2.1 development table read by the fixed rules, beside instance segmentation.

白话：S2-06 问的是：S2-R 在实例分割前端上看到的模式——相对同配方 AssocOnly，Missing 残留率大幅更低、身份连续率更高、节点 F1
小幅更低；相对规则臂多指标取舍——换成 SAM2 前端、所有可训练与可拟合的部分都按冻结规则在 SAM2 上重来以后，还在不在。输入是
七臂节点审计的合并结果：SAM2 上的 VSMT-lean、NoVersion、AssocOnly（各 5 个种子）与 TAF、ELU-P、RAC、LOW（各一份），以及实例
分割开发集上的同一套（VSMT-lean 分组头 7c76970、AssocOnly 与规则臂 d835cd3、本阶段补的 NoVersion）。输出按裁决 100-3 写死的读法：
  * VSMT-lean 对 AssocOnly：82-1 逐项先后与 95-3 归类（`ruling95_reading.read` 原样复用），两套前端各一份；
  * VSMT-lean 对 NoVersion：82-1 逐项先后，只报告、不设门（版本保留本身的作用），两套前端各一份；
  * 规则臂：house 均值与 85-4 比值（对 Missing 残留率最低的规则臂）；
  * 逐项并排：每个指标每个臂的五种子均值与先后，SAM2 一列、实例分割一列。
实例分割那份 AssocOnly 读数从已提交的合并导出重算，并与已提交的判读（`results/vsmt_lean_ruling96_reading_7c76970.json`）逐项
核对，不一致就拒绝——表里每个数都由本脚本从文件算出，不手抄。例如 SAM2 上 Missing 残留率 5/5 更低、节点 F1 分不出，就归
“开发集上显示收益”，与实例分割的归类并排写出。它不是 test，不选参、不改方法；39 个开发 house 里 30 个是训练 house，读数是样本内的。

Usage:
  python ops/vsmt/s2_06_reading.py \
      --sam2-group VSMT-lean:7:<merged audit> ... --sam2-group NoVersion:59:<...> --sam2-group AssocOnly:59:<...> \
      --sam2-rule-arm TAF:<merged audit> ... \
      --instance-group VSMT-lean:7:results/vsmt_lean_ruling96_audit_GROUPED-A7_7c76970.json ... \
      --instance-group NoVersion:7:<merged audit> ... --instance-group AssocOnly:7:results/vsmt_lean_ruling95_audit_ASSOC-A7_d835cd3.json ... \
      --instance-rule-arm TAF:results/vsmt_lean_ruling95_audit_RULE-TAF_d835cd3.json ... \
      --instance-reading results/vsmt_lean_ruling96_reading_7c76970.json --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ruling82_seed_analysis as r82  # noqa: E402
import ruling95_reading as r95  # noqa: E402

STAGE = "vsmt.lean.s2_06.reading.v1"
LEARNED = ("VSMT-lean", "NoVersion", "AssocOnly")
FRONTS = ("sam2", "simulator_instance_masks")
READING_RULE = (
    "ruling 100-3 (registered before the run): VSMT-lean against AssocOnly by the 82-1 rule metric by metric and the ruling 95-3 "
    "classification; VSMT-lean against NoVersion by the 82-1 rule, reported without a gate, on both front ends; rule arms by house "
    "mean and the 85-4 ratio against the rule arm with the lowest Missing residual rate; every item beside the instance-segmentation "
    "development reading; development, in-sample (30 of the 39 houses train the heads); never used to change the method")
#: the committed instance-segmentation reading the recomputation must reproduce (ruling 96, LOG-295)
COMPARED_FIELDS = ("classification", "orders_82_1", "comparison_82_1", "rule_arms", "rule_85_4", "lines_89_4_reference_only")


def front_reading(groups: Mapping[tuple[str, int], Mapping[str, Any]], rule_arms: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Both registered readings of one front end."""

    assoc = r95.read({key: value for key, value in groups.items() if key[0] in ("VSMT-lean", "AssocOnly")}, rule_arms)
    version = r82.analyse({key: value for key, value in groups.items() if key[0] in ("VSMT-lean", "NoVersion")},
                          arms=("VSMT-lean", "NoVersion"))
    return {"vsmt_lean_vs_assoc_only": assoc,
            "vsmt_lean_vs_no_version_report_only": {"orders_82_1": version["summary"], "comparison_82_1": version}}


def side_by_side(readings: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Per metric: five-seed means of the three learned arms, the rule-arm house means and both orders, one column per front end."""

    out: dict[str, Any] = {}
    for metric in r82.METRICS:
        row: dict[str, Any] = {}
        for front, reading in readings.items():
            assoc = reading["vsmt_lean_vs_assoc_only"]["comparison_82_1"]["metrics"][metric]
            version = reading["vsmt_lean_vs_no_version_report_only"]["comparison_82_1"]["metrics"][metric]
            row[front] = {
                "five_seed_mean": {"VSMT-lean": assoc["seed_spread"]["VSMT-lean"]["mean"], "AssocOnly": assoc["seed_spread"]["AssocOnly"]["mean"],
                                   "NoVersion": version["seed_spread"]["NoVersion"]["mean"]},
                "rule_arm_house_mean": {arm: rows[metric]["mean"] for arm, rows in reading["vsmt_lean_vs_assoc_only"]["rule_arms"].items()},
                "order_vs_assoc_only": assoc["seed_paired_gaps"]["order"], "mean_gap_vs_assoc_only": assoc["seed_paired_gaps"]["mean_gap"],
                "order_vs_no_version": version["seed_paired_gaps"]["order"], "mean_gap_vs_no_version": version["seed_paired_gaps"]["mean_gap"],
            }
        out[metric] = row
    return out


def read(sam2: Mapping[str, Any], instance: Mapping[str, Any], committed: Mapping[str, Any] | None) -> dict[str, Any]:
    readings = {"sam2": front_reading(sam2["groups"], sam2["rule_arms"]),
                "simulator_instance_masks": front_reading(instance["groups"], instance["rule_arms"])}
    check = None
    if committed is not None:  # the instance-segmentation AssocOnly reading must be the committed one, recomputed from its inputs
        recomputed = readings["simulator_instance_masks"]["vsmt_lean_vs_assoc_only"]
        differing = [field for field in COMPARED_FIELDS if json.loads(json.dumps(recomputed[field])) != committed.get(field)]
        if differing:
            raise ValueError(f"instance_reading_not_reproduced:{','.join(differing)}")
        check = {"reproduced_fields": list(COMPARED_FIELDS), "committed_stage": committed.get("stage")}
    classes = {front: reading["vsmt_lean_vs_assoc_only"]["classification"] for front, reading in readings.items()}
    return {
        "reading_rule": READING_RULE,
        "classification_95_3": classes,
        "classification_matches_instance_segmentation": classes["sam2"] == classes["simulator_instance_masks"],
        "orders_vs_assoc_only": {front: r["vsmt_lean_vs_assoc_only"]["orders_82_1"] for front, r in readings.items()},
        "orders_vs_no_version_report_only": {front: r["vsmt_lean_vs_no_version_report_only"]["orders_82_1"] for front, r in readings.items()},
        "rule_85_4": {front: r["vsmt_lean_vs_assoc_only"]["rule_85_4"] for front, r in readings.items()},
        "side_by_side": side_by_side(readings),
        "readings": readings,
        "instance_reading_check": check,
        "caveat": ("development reading on the 39 development houses of each front end (30 of them train the learned heads: in-sample); "
                   "the 82-1 rule is a seed-stability criterion, not a significance test; the SAM2 heads are retrained on SAM2 records, so "
                   "this is not a cross-front-end transfer test; the reading informs the S3-01 two-front-end rule and the ruling 84-6 mask-layer "
                   "decision only, never a change to the method"),
    }


def parse_groups(specs: list[str], inputs: dict[str, Any], prefix: str) -> dict[tuple[str, int], Any]:
    groups = {}
    for spec in specs:
        arm, seed, path = spec.split(":", 2)
        if arm not in LEARNED:
            raise ValueError(f"unknown_learned_arm:{arm}")
        file = Path(path)
        groups[(arm, int(seed))] = json.loads(file.read_text(encoding="utf-8"))
        inputs[f"{prefix}:{arm}:{seed}"] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    return groups


def parse_rule_arms(specs: list[str], inputs: dict[str, Any], prefix: str) -> dict[str, Any]:
    arms = {}
    for spec in specs:
        arm, path = spec.split(":", 1)
        file = Path(path)
        arms[arm] = json.loads(file.read_text(encoding="utf-8"))
        inputs[f"{prefix}:{arm}"] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    return arms


def mask_sources(groups: Mapping[Any, Mapping[str, Any]]) -> set[Any]:
    return {merged.get("mask_source") for merged in groups.values()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sam2-group", action="append", required=True, help="ARM:SEED:PATH (VSMT-lean, NoVersion, AssocOnly)")
    parser.add_argument("--sam2-rule-arm", action="append", required=True, help="ARM:PATH (TAF, ELU-P, RAC, LOW)")
    parser.add_argument("--instance-group", action="append", required=True)
    parser.add_argument("--instance-rule-arm", action="append", required=True)
    parser.add_argument("--instance-reading", default=None, help="the committed instance-segmentation reading to reproduce")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    inputs: dict[str, Any] = {}
    try:
        sam2 = {"groups": parse_groups(args.sam2_group, inputs, "sam2"), "rule_arms": parse_rule_arms(args.sam2_rule_arm, inputs, "sam2")}
        instance = {"groups": parse_groups(args.instance_group, inputs, "instance"),
                    "rule_arms": parse_rule_arms(args.instance_rule_arm, inputs, "instance")}
        # every SAM2 merge must name sam2 (node audit v11); the instance merges are v11 (NoVersion) or older exports without the field
        if mask_sources({**sam2["groups"], **{(arm, 0): m for arm, m in sam2["rule_arms"].items()}}) != {"sam2"}:
            raise ValueError("a SAM2 input does not name the sam2 mask source")
        if mask_sources({**instance["groups"], **{(arm, 0): m for arm, m in instance["rule_arms"].items()}}) - {"simulator_instance_masks", None}:
            raise ValueError("an instance-segmentation input names another mask source")
        committed = None
        if args.instance_reading:
            file = Path(args.instance_reading)
            committed = json.loads(file.read_text(encoding="utf-8"))
            inputs["instance_reading"] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        result = read(sam2, instance, committed)
    except (ValueError, OSError) as exc:
        print(f"[s2-06-reading] refused: {exc}", file=sys.stderr)
        return 2
    output = {"stage": STAGE, "inputs": inputs, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **result}
    Path(args.output).write_text(json.dumps(output, indent=1), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("classification_95_3", "classification_matches_instance_segmentation", "orders_vs_assoc_only",
                                                  "orders_vs_no_version_report_only")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
