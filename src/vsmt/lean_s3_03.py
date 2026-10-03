"""S3-03 (ruling 104, 2026-10-03): the registered rules of training and configuration selection, as pure functions.

白话：裁决 104 把 S3-03 的几条规则写定了，这个模块把它们写成可测试的纯函数与常量，供训练入口、调度器与选参读数共用：
  * 训练 house 与选点 house（104-1 1a）：S3 train 清单（已是 S0-02 划分名次顺序）前 240 个训练、后 60 个只给检查点打分；
    由清单决定、与成败无关，生成或 cache 失败的 house 只是缺席、不顶替。开发集用的 ``holdout_split``（按名次前 30 个训练、
    其余全归选点）照搬到 S3 只会用 30 个 house 训练，所以 S3 不用它；
  * 每个学习臂、每一轮的训练设置（99-1 的配方，104-1 1c／1d）：标签来源（teacher 记录或 HeuristicLabel 记录）、是否没有
    存在头（AssocOnly）、是否分组选点（第 1 轮的 VSMT-lean 与 HeuristicLabel）；
  * 清单守卫（104-6）：拟合趟、第 0／1 轮轨迹只收 S3 train 清单里的 episode，validation 审计只收 validation 清单里的，test 一律
    不给。
输入是已提交的清单与臂名，输出是名单与设置。例如第 1 轮的 HeuristicLabel 读 ``heuristic_training_records.jsonl.gz``，分组选点；
一条 validation episode 被误交给第 0 轮轨迹，入口报出它不在 train 清单并以退出码 2 结束。它不读任何数据、不训练、不选配置。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

STAGE = "vsmt.lean.s3_03.v1"
MANIFEST_PATH = Path(__file__).resolve().parents[2] / "configs" / "vsmt" / "lean_s3_01_manifests.json"
MANIFEST_SPLIT_RULE = (
    "ruling 104-6: the fit, round-0 and round-1 passes take only episodes of the S3 train manifest, the validation audits only "
    "episodes of the validation manifest; test is never handed out (ruling 103-1)"
)

#: Ruling 104-1 1a: the S3 train manifest in its split order, the first 240 houses train and the last 60 score checkpoints.
TRAINING_HOUSE_COUNT = 240
SELECTION_HOUSE_COUNT = 60
CHECKPOINT_SPLIT_RULE = (
    "ruling 104-1 1a: the S3 train manifest (configs/vsmt/lean_s3_01_manifests.json, already in S0-02 split order) gives its "
    "first 240 houses to training and its last 60 to checkpoint selection; the split is fixed by the manifest, a house whose "
    "generation or cache failed is simply absent and never replaced; the encoding statistics and the class weight come from "
    "the training houses only, the ELU-P fit and the rollouts use every train house"
)

#: The records each label source writes next to an S2-04 episode receipt (ruling 104-1 1c: HeuristicLabel's own file).
RECORD_FILES = {"teacher": "training_records.jsonl.gz", "heuristic": "heuristic_training_records.jsonl.gz"}

#: The three trained arms (NoVersion uses VSMT-lean's heads, ruling 99-1 / 104-1 1d) and their label sources.
TRAINED_ARMS = ("VSMT-lean", "AssocOnly", "HeuristicLabel")
LABEL_SOURCE = {"VSMT-lean": "teacher", "AssocOnly": "teacher", "HeuristicLabel": "heuristic"}
ROUNDS = (0, 1)
#: Ruling 99-1 / 96: round 1 keeps the grouped selection for the arms with an existence head; round 0 the total-loss one.
GROUPED_ARMS_IN_ROUND_1 = ("VSMT-lean", "HeuristicLabel")
#: Ruling 99-1 (the evaluated recipe, ``s2r_recipe`` in S0-05): field-wise encoding, class-weighted existence loss, cosine
#: rate 1e-3 -> 1e-5, gradient clipping 1.0, decisions on the ln w corrected logit.  These are the values the evaluated
#: entry passed (``ruling89_probes.revision_kwargs`` with --revision-91); a test binds the two.
COSINE_MIN_LEARNING_RATE = 1e-5
GRADIENT_CLIP_NORM = 1.0


class LeanS3_03Error(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS3_03Error(code)


def checkpoint_split(train_manifest: Sequence[str]) -> dict[str, Any]:
    """The training houses and the checkpoint-selection houses of the S3 train manifest (ruling 104-1 1a)."""

    houses = [str(house) for house in train_manifest]
    _require(len(houses) == TRAINING_HOUSE_COUNT + SELECTION_HOUSE_COUNT, f"train_manifest_size_{len(houses)}")
    _require(len(set(houses)) == len(houses), "train_manifest_duplicated")
    return {"rule": CHECKPOINT_SPLIT_RULE, "training_houses": houses[:TRAINING_HOUSE_COUNT],
            "selection_houses": houses[TRAINING_HOUSE_COUNT:]}


def training_settings(arm: str, round_index: int) -> dict[str, Any]:
    """What one training of ``arm`` in ``round_index`` reads and how it is trained and selected (rulings 99-1, 104-1)."""

    _require(arm in TRAINED_ARMS, f"arm_not_trained_in_s3:{arm}")
    _require(round_index in ROUNDS, f"round_invalid:{round_index}")
    assoc_only = arm == "AssocOnly"
    return {
        "arm": arm, "round": round_index, "label_source": LABEL_SOURCE[arm], "record_file": RECORD_FILES[LABEL_SOURCE[arm]],
        "assoc_only": assoc_only,
        "kwargs": {"field_encoding": True, "existence_class_weight": not assoc_only,
                   "cosine_min_learning_rate": COSINE_MIN_LEARNING_RATE, "gradient_clip_norm": GRADIENT_CLIP_NORM,
                   "existence_prior_correction": True,
                   "group_selection": round_index == 1 and arm in GROUPED_ARMS_IN_ROUND_1},
        "uses": "grouped" if round_index == 1 and arm in GROUPED_ARMS_IN_ROUND_1 else "total",
    }


def manifest_houses(manifest: Mapping[str, Any], split: str) -> list[str]:
    """One split's committed house list; ``test`` is never handed out here (ruling 103-1)."""

    _require(split in ("train", "validation"), f"split_not_readable_in_s3_03:{split}")
    houses = manifest.get(split)
    _require(isinstance(houses, list) and bool(houses), f"manifest_split_missing:{split}")
    return [str(house) for house in houses]


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def manifest_split_refusal(episode_id: str, split: str, manifest: Mapping[str, Any] | None = None) -> str | None:
    """Ruling 104-6: why ``episode_id`` may not be read as an episode of ``split``, or None when it is one."""

    try:
        houses = manifest_houses(load_manifest() if manifest is None else manifest, split)
    except LeanS3_03Error as exc:
        return f"{exc} ({MANIFEST_SPLIT_RULE})"
    if str(episode_id) not in set(houses):
        return f"episode_not_in_the_s3_{split}_manifest:{episode_id} ({MANIFEST_SPLIT_RULE})"
    return None


__all__ = [
    "CHECKPOINT_SPLIT_RULE",
    "COSINE_MIN_LEARNING_RATE",
    "GRADIENT_CLIP_NORM",
    "GROUPED_ARMS_IN_ROUND_1",
    "LABEL_SOURCE",
    "LeanS3_03Error",
    "MANIFEST_PATH",
    "MANIFEST_SPLIT_RULE",
    "RECORD_FILES",
    "ROUNDS",
    "SELECTION_HOUSE_COUNT",
    "STAGE",
    "TRAINED_ARMS",
    "TRAINING_HOUSE_COUNT",
    "checkpoint_split",
    "load_manifest",
    "manifest_houses",
    "manifest_split_refusal",
    "training_settings",
]
