"""D-224 / S1-02 I1: the intervention selector, as a pure function.

Enumerate every feasible (object, kind, shared window) triple first, then
sample from that set with an RNG derived from the frozen split seed and the
house id.  Never sample-then-retry: that would favour objects in easily
hidden places, which is selecting samples by how concealable they are.

白话：这个模块解决"这条 episode 该动哪些物体、怎么动"。输入是这栋房子的物体表
（谁可拾取、谁在哪个容器上）、扫掠一里每个物体最多可见了多少像素、过渡段内始
终看不见的容器集合 U、每个目标容器放不放得下，以及冻结的 seed 和 house id；输
出是至多 6 个干预（物体、类型、源、目标、复制件的新 id）和一个"本条是不是空窗
口"的判定。例如 F 里有 9 个可行三元组，就从 9 个里无放回抽最多 6 个，同一物体
只用一次。它不启动模拟器、不看图像、不做任何顺序重抽。
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json
from vsmt.lean_intervention import (
    INTERVENTION_KINDS,
    MAXIMUM_INTERVENTIONS_PER_EPISODE,
    MIN_VISIBLE_PIXELS,
    P_NULL_WINDOW,
    RNG_PURPOSE_TAGS,
)


class LeanSelectionError(ValueError):
    """Raised for an inadmissible object table or an unregistered RNG tag."""


def derive_rng(split_seed: int, house_id: str, purpose: str) -> random.Random:
    """A Random seeded from (split seed, house id, purpose tag) and nothing else.

    白话：随机数不引入新种子，全部由已冻结的划分 seed、house id 和一个用途标签
    派生。同一 house 在任何机器上抽到同样的干预；换个用途标签就得到另一条互不
    重叠的随机流。标签不在登记表里就报错。
    """

    if purpose not in RNG_PURPOSE_TAGS:
        raise LeanSelectionError(f"rng_purpose_not_registered:{purpose}")
    digest = hashlib.sha256(canonical_json([split_seed, house_id, purpose]).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def is_null_window(split_seed: int, house_id: str) -> bool:
    """Whether this episode executes zero interventions by design (p = 0.2)."""

    return derive_rng(split_seed, house_id, "null_window").random() < P_NULL_WINDOW


def eligible_objects(
    objects: Sequence[Mapping[str, Any]],
    visible_pixels: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Objects that may be intervened on.

    白话：合格物体＝可拾取、在某个容器内或其上、扫掠一中至少一帧可见像素 ≥196、
    不是 agent 或结构件。输入是物体表和"每个物体最多可见了多少像素"，输出合格
    物体列表（按 id 排序）。看不见的物体记忆里没有实体，动它没有意义。
    """

    out: list[dict[str, Any]] = []
    for obj in objects:
        if not obj.get("pickupable"):
            continue
        if obj.get("parent_receptacle") is None:
            continue
        if obj.get("is_agent") or obj.get("is_structure"):
            continue
        if visible_pixels.get(obj["object_id"], 0) < MIN_VISIBLE_PIXELS:
            continue
        out.append(dict(obj))
    return sorted(out, key=lambda o: o["object_id"])


def unseen_objects(objects: Sequence[Mapping[str, Any]], visible_pixels: Mapping[str, int]) -> list[dict[str, Any]]:
    """Pickupable objects on a receptacle that have never been rendered so far (0 px).

    白话（裁决 30，proposed）：`add` 的另一种来源——不是复制已见物体，而是把 house 里
    一个**从未出现在任何私有掩码里**的真实物体搬到 U 容器上。对记忆来说它就是新实体
    （BIRTH），而且它是真实 prefab，实例分割能登记它。输入是物体表和"每个物体至今最
    多可见像素"，输出 0 像素的合格物体（按 id 排序）。它不等于"没看清"的物体：哪怕
    1 个像素也算见过。
    """

    out: list[dict[str, Any]] = []
    for obj in objects:
        if not obj.get("pickupable") or obj.get("parent_receptacle") is None:
            continue
        if obj.get("is_agent") or obj.get("is_structure"):
            continue
        if visible_pixels.get(obj["object_id"], 0) > 0:
            continue
        out.append(dict(obj))
    return sorted(out, key=lambda o: o["object_id"])


def feasible_triples(
    eligible: Sequence[Mapping[str, Any]],
    receptacles: Sequence[str],
    invisible_containers: set[str],
    placement_ok: Mapping[str, bool],
    unseen: Sequence[Mapping[str, Any]] | None = None,
    pair_ok: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Every (object, kind, ...) whose involved containers are all in U.

    白话：先定过渡段、算出其内始终不可见的容器集合 U，再穷举：remove 要源容器
    ∈ U；move 要源、目标都 ∈ U 且目标放得下且目标 ≠ 源；add（复制已有物体）要目
    标 ∈ U 且放得下。输出按确定顺序排列的可行三元组列表 F，抽样只从 F 里抽。
    """

    out: list[dict[str, Any]] = []
    sorted_receptacles = sorted(receptacles)
    for obj in eligible:
        src = obj["parent_receptacle"]
        oid = obj["object_id"]
        if src in invisible_containers:
            out.append({"kind": "remove", "object_id": oid, "asset_id": obj.get("asset_id"),
                        "source": src, "destination": None})
        for dst in sorted_receptacles:
            if dst not in invisible_containers or not placement_ok.get(dst, False):
                continue
            if dst != src and src in invisible_containers:
                out.append({"kind": "move", "object_id": oid, "asset_id": obj.get("asset_id"),
                            "source": src, "destination": dst})
            if unseen is None:
                out.append({"kind": "add", "object_id": oid, "asset_id": obj.get("asset_id"),
                            "source": None, "destination": dst})
    if unseen is not None:
        for obj in unseen:
            for dst in sorted_receptacles:
                if dst not in invisible_containers or not placement_ok.get(dst, False) or dst == obj["parent_receptacle"]:
                    continue
                out.append({"kind": "add", "object_id": obj["object_id"], "asset_id": obj.get("asset_id"),
                            "source": obj["parent_receptacle"], "destination": dst, "add_source": "unseen_existing"})
    if pair_ok is not None:
        # dry-run prescreen (ruling 31, proposed): a move/add is feasible only if the simulator
        # actually placed the object there and it was visible from the destination's viewpoint
        kept = []
        for row in out:
            if row["kind"] == "remove":
                kept.append(row); continue
            hit = pair_ok.get((row["object_id"], row["destination"]))
            if hit is None:
                continue
            kept.append({**row, "point": hit["point"], "verified_pixels": hit["pixels"], "dry_run_tries": hit["tries"]})
        out = kept
    for t in out:
        if t["kind"] not in INTERVENTION_KINDS:
            raise LeanSelectionError("unregistered_kind")
    return out


def sample_interventions(
    feasible: Sequence[Mapping[str, Any]], *, split_seed: int, house_id: str,
    maximum: int = MAXIMUM_INTERVENTIONS_PER_EPISODE, stratify_by_kind: bool = True,
    one_placement_per_destination: bool = True,
) -> list[dict[str, Any]]:
    """Draw up to ``maximum`` triples without replacement, one object at most once.

    白话：从 F 里用派生 RNG 无放回抽，抽到的物体不再抽第二次（add 复制它算用过
    它）。输出带序号的干预列表；复制件的新 id 由 (house, 物体, 序号) 派生。

    ``stratify_by_kind``（裁决 29，已采纳，默认开）：每个名额先在"还有可用三元组"
    的类型里均匀抽一个类型，再在该类型里均匀抽三元组。关掉即回到 S1-02b 首跑的按
    三元组均匀抽，add 因三元组数量占优而几乎总被抽中——只用于复算旧运行。
    ``one_placement_per_destination``（裁决 32，已采纳，默认开）：每个目的容器每条
    episode 至多一次放置，remove 不限。
    """

    rng = derive_rng(split_seed, house_id, "intervention")
    pool = list(feasible)
    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    placed: set[str] = set()
    while pool and len(chosen) < maximum:
        if one_placement_per_destination:
            pool = [t for t in pool if t["kind"] == "remove" or t["destination"] not in placed]
            if not pool:
                break
        if stratify_by_kind:
            pool = [t for t in pool if t["object_id"] not in used]
            if not pool:
                break
            kinds = sorted({t["kind"] for t in pool})
            kind = kinds[rng.randrange(len(kinds))]
            of_kind = [i for i, t in enumerate(pool) if t["kind"] == kind]
            pick = pool.pop(of_kind[rng.randrange(len(of_kind))])
        else:
            pick = pool.pop(rng.randrange(len(pool)))
        if pick["object_id"] in used:
            continue
        used.add(pick["object_id"])
        if pick["kind"] != "remove":
            placed.add(pick["destination"])
        row = dict(pick)
        row["index"] = len(chosen)
        if row["kind"] == "add" and row.get("add_source") != "unseen_existing":
            tag = hashlib.sha256(canonical_json([house_id, row["object_id"], row["index"]]).encode("utf-8")).hexdigest()[:12]
            row["generated_id"] = f"dup_{tag}"
        chosen.append(row)
    return chosen


def revisit_sequence(
    interventions: Sequence[Mapping[str, Any]], *, split_seed: int, house_id: str,
) -> list[str]:
    """Containers sweep two revisits, in order; move's two ends ordered by RNG.

    白话：扫掠二要重访的容器序列。remove 重访源，add 重访目标，move 两端都重
    访，先源还是先目标由派生 RNG 逐个决定。重复容器只保留第一次出现。
    """

    rng = derive_rng(split_seed, house_id, "revisit_order")
    seq: list[str] = []
    for row in interventions:
        if row["kind"] == "remove":
            ends = [row["source"]]
        elif row["kind"] == "add":
            ends = [row["destination"]]
        else:
            ends = [row["source"], row["destination"]]
            if rng.random() < 0.5:
                ends.reverse()
        for c in ends:
            if c not in seq:
                seq.append(c)
    return seq


__all__ = [
    "LeanSelectionError",
    "derive_rng",
    "eligible_objects",
    "feasible_triples",
    "is_null_window",
    "revisit_sequence",
    "sample_interventions",
]
