"""S3-01 (ruling 102-8): the three S3 manifests, derived from the split S1-02a froze.

白话：S3 要在生成任何正式数据之前，把 test、validation、train 三份 house 名单写死。输入是 S1-02a 冻结的划分参数（seed
20260920、validation 50、test 100）与 ProcTHOR-10K 0.1.2 的 house 池（train-00000 到 train-09999），输出三份互斥名单：
test 与 validation 就是划分本身的前两份（成员早已固定）；train 按裁决 102-8 取 train 块第 100～399 位共 300 个——
第 0～49 位是 S1 的开发 house，第 50～99 位是裁决 81 的确认集，两者都不进 S3，S3 的 train 与开发、确认过程完全分开。
例如确认集名单可以由同一函数逐项重算出来（第 50～99 位），与登记文件 `lean_ruling81_confirmation_houses.json` 一致。
它不生成任何数据、不读任何 house 内容，也不改 S1-02a 合同：那里的 `train_houses` 值槽按“train 块前缀”设计，裁决 102-8 改取
第 100～399 位，所以那个值槽保持 null，S3 的 train 以本模块和登记清单为准。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from vsmt.lean_intervention import assign_split

SCHEMA_VERSION = "vsmt-lean-s3-01-manifests-v1"
DATASET_TAG = "procthor10k-0.1.2-train"
POOL_SIZE = 10_000
#: Ruling 102-8: positions of the train block (the split's third part, in split order).
DEVELOPMENT_POSITIONS = (0, 49)
CONFIRMATION_POSITIONS = (50, 99)
TRAIN_POSITIONS = (100, 399)
RULE = (
    "assign_split over procthor10k-0.1.2-train-00000..09999 with the S1-02a split_freeze (seed 20260920, test 100, validation 50, "
    "the rest train in split order); test and validation are the split's first two parts; the S3 train is positions 100..399 of the "
    "train block (ruling 102-8); positions 0..49 (S1 development) and 50..99 (ruling-81 confirmation) are excluded from S3"
)


class LeanS3ManifestError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS3ManifestError(code)


def house_pool(size: int = POOL_SIZE) -> list[str]:
    """The ProcTHOR-10K 0.1.2 train houses by index, the pool S1-02a split."""

    return [f"{DATASET_TAG}-{i:05d}" for i in range(size)]


def houses_sha256(houses: Sequence[str]) -> str:
    """The list digest rule of the ruling-81 registry: sha256 of json.dumps(list)."""

    return hashlib.sha256(json.dumps(list(houses)).encode("utf-8")).hexdigest()


def derive(freeze: Mapping[str, Any], pool: Sequence[str] | None = None) -> dict[str, list[str]]:
    """The S3 manifests and the two excluded blocks from the frozen split."""

    pool = list(pool if pool is not None else house_pool())
    for name in ("seed", "validation_houses", "test_houses"):
        _require(type(freeze.get(name)) is int, f"split_freeze_value_missing:{name}")
    validation, test = freeze["validation_houses"], freeze["test_houses"]
    split = assign_split(pool, seed=freeze["seed"], train=len(pool) - validation - test, validation=validation, test=test)
    block = list(split["train"])
    _require(len(block) > TRAIN_POSITIONS[1], "train_block_too_short")

    def positions(span: tuple[int, int]) -> list[str]:
        return block[span[0]:span[1] + 1]

    return {"test": list(split["test"]), "validation": list(split["validation"]), "train": positions(TRAIN_POSITIONS),
            "development_excluded": positions(DEVELOPMENT_POSITIONS), "confirmation_excluded": positions(CONFIRMATION_POSITIONS)}


def build(freeze: Mapping[str, Any], *, split_freeze_source: str, confirmation_registry: Mapping[str, Any]) -> dict[str, Any]:
    """The manifest file: lists, digests, positions and overlap checks; the confirmation block must equal the ruling-81 list."""

    lists = derive(freeze)
    _require(lists["confirmation_excluded"] == list(confirmation_registry["houses"]), "confirmation_block_does_not_match_the_registry")
    _require(houses_sha256(lists["confirmation_excluded"]) == confirmation_registry["houses_sha256"], "confirmation_digest_mismatch")
    names = ("test", "validation", "train", "development_excluded", "confirmation_excluded")
    overlaps = {f"{a}|{b}": len(set(lists[a]) & set(lists[b])) for i, a in enumerate(names) for b in names[i + 1:]}
    _require(all(v == 0 for v in overlaps.values()), "manifests_overlap")
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "D-224-S1 ruling 102-8 (2026-10-02, 「待裁 102 修订稿二全按推荐」)",
        "rule": RULE,
        "split_freeze_source": split_freeze_source,
        "split_freeze": {name: freeze[name] for name in ("seed", "validation_houses", "test_houses")},
        "pool": {"first": house_pool()[0], "last": house_pool()[-1], "size": POOL_SIZE},
        "positions": {"development_excluded": list(DEVELOPMENT_POSITIONS), "confirmation_excluded": list(CONFIRMATION_POSITIONS),
                      "train": list(TRAIN_POSITIONS)},
        "counts": {name: len(lists[name]) for name in names},
        "sha256": {name: houses_sha256(lists[name]) for name in names},
        "overlaps": overlaps,
        "status": "lists only: no data generated, nothing read; test is read once in S3-05",
        "generation_settings": "S3-02 generates every listed house with dry-run at most 8 destination containers per object (ruling 39) "
                               "and maximum_actions 4000 (ruling 40); failures are recorded and never replaced",
        "s1_02a_train_houses_slot": "stays null: it was designed as a train-block prefix, ruling 102-8 takes positions 100..399 instead",
        "plain_language_zh": ("S3 的三份名单（裁决 102-8）：test 100 个与 validation 50 个由 S1-02a 冻结的划分直接给出；train 取 train 块第"
                              " 100～399 位共 300 个，S1 开发 house（第 0～49 位）与裁决 81 确认集（第 50～99 位）都不进 S3。生成失败照记，"
                              "不替换；test 只在 S3-05 读一次。"),
        **{name: lists[name] for name in ("test", "validation", "train")},
    }


def validate(manifest: Mapping[str, Any], freeze: Mapping[str, Any], confirmation_registry: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute the file from the frozen split; any difference is refused."""

    expected = build(freeze, split_freeze_source=str(manifest.get("split_freeze_source")), confirmation_registry=confirmation_registry)
    for name in ("test", "validation", "train"):
        _require(list(manifest.get(name) or []) == expected[name], f"manifest_list_mismatch:{name}")
    for name in ("schema_version", "rule", "split_freeze", "positions", "counts", "sha256", "overlaps"):
        _require(manifest.get(name) == expected[name], f"manifest_field_mismatch:{name}")
    return dict(manifest)


__all__ = [
    "CONFIRMATION_POSITIONS",
    "DEVELOPMENT_POSITIONS",
    "LeanS3ManifestError",
    "RULE",
    "SCHEMA_VERSION",
    "TRAIN_POSITIONS",
    "build",
    "derive",
    "house_pool",
    "houses_sha256",
    "validate",
]
