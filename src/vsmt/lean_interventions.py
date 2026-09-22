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
    DRY_RUN_DESTINATIONS_PER_OBJECT,
    INTERVENTION_KINDS,
    MAXIMUM_INTERVENTIONS_PER_EPISODE,
    MIN_VISIBLE_PIXELS,
    P_NULL_WINDOW,
    RNG_PURPOSE_TAGS,
)


class LeanSelectionError(ValueError):
    """Raised for an inadmissible object table or an unregistered RNG tag."""


FLOOR_RECEPTACLE_ID = "Floor"


def parent_receptacle_of(parents: Sequence[str] | None) -> str | None:
    """The receptacle an object counts as sitting in or on (ruling 52).

    AI2-THOR's ``parentReceptacles`` lists every receptacle whose trigger box holds the object and
    puts the room ``Floor`` first for anything on low furniture (sofa, TV stand, side table,
    shelving unit, dining table).  Taking entry 0 attributed 99 of the 987 eligible objects of the
    7c10d2c development run to the floor, so they could never be a remove/move source or a control
    holder (LOG-243 supplement).  The first non-Floor entry is the receptacle; an object listed only
    under Floor sits on the floor and has no container; an empty list has none either.

    白话：模拟器给每个物体报的"父容器"是一张表，矮家具上的物体会把房间地板排在表的第一位。
    以前只取第一项，结果放在电视柜上的碗被记成"在地板上"，而地板不是容器，这只碗就永远不能
    被拿走或搬走，电视柜也被当成空的。现在取表里第一个不是 Floor 的受体；只有 Floor 的物体
    确实在地上，返回 None，不算合格物体。输入是父容器表，输出是一个受体 id 或 None。它不判断
    物体是否可见，也不改变 U。
    """

    for parent in parents or []:
        if parent != FLOOR_RECEPTACLE_ID:
            return str(parent)
    return None


def derive_rng(split_seed: int, house_id: str, purpose: str, private_salt: str | None = None) -> random.Random:
    """A Random seeded from (split seed, house id, purpose tag) and, for the null draw only, a private salt.

    白话：随机数不引入新种子，全部由已冻结的划分 seed、house id 和一个用途标签
    派生。同一 house 在任何机器上抽到同样的干预；换个用途标签就得到另一条互不
    重叠的随机流。标签不在登记表里就报错。唯一例外是空窗口抽签（裁决 37）：seed
    写在公开合同里、house id 就是目录名，两者都拿得到，所以再混入一个只存在于仓库
    外的私有盐；provenance 只登记盐的 sha256。
    """

    if purpose not in RNG_PURPOSE_TAGS:
        raise LeanSelectionError(f"rng_purpose_not_registered:{purpose}")
    if (purpose == "null_window") != (private_salt is not None):
        raise LeanSelectionError("private_salt_is_required_for_null_window_and_forbidden_elsewhere")
    parts: list[Any] = [split_seed, house_id, purpose]
    if private_salt is not None:
        if type(private_salt) is not str or len(private_salt) < 32:
            raise LeanSelectionError("private_salt_must_be_a_string_of_at_least_32_characters")
        parts.append(private_salt)
    digest = hashlib.sha256(canonical_json(parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def is_null_window(split_seed: int, house_id: str, private_salt: str) -> bool:
    """Whether this episode executes zero interventions by design (p = 0.2), salted (ruling 37)."""

    return derive_rng(split_seed, house_id, "null_window", private_salt).random() < P_NULL_WINDOW


def select_controls(
    eligible: Sequence[Mapping[str, Any]], receptacles: Sequence[str], invisible_containers: set[str],
    interventions: Sequence[Mapping[str, Any]], *, split_seed: int, house_id: str,
) -> dict[str, Any]:
    """The unintervened control containers sweep two revisits (ruling 34, twin control).

    白话：扫掠二若只重访被干预的容器，"被重访 ⇒ 有变化"就是 100% 的结构捷径。这里
    为每个被干预容器配一个对照容器：从 U（过渡段全程看不见）里去掉被干预集合、只留
    至少持有一个扫掠一里看见过的合格物体的容器，用派生 RNG 无放回抽取同样多个；U 里
    不够时才从 U 外的持物容器补，并把补的数目登记出来。对照容器上什么都没动，重访
    它考的是"没变就不该撤回"。输入是合格物体表、全部容器、U、本条抽中的干预（空窗口
    episode 也传"本该执行"的那份）；输出对照列表、来源计数和缺口。它不改变干预抽样，
    不从空容器里挑对照——重访一个空抽屉什么也测不到。
    """

    involved: set[str] = set()
    for row in interventions:
        for key in ("source", "destination"):
            if row.get(key):
                involved.add(row[key])
    holders: dict[str, list[str]] = {}
    for obj in eligible:
        holders.setdefault(obj["parent_receptacle"], []).append(obj["object_id"])
    intervened = sorted({c for c in involved if c in set(receptacles)})
    wanted = len({row.get("destination") or row.get("source") for row in interventions if row.get("kind")}
                 | {row["source"] for row in interventions if row.get("kind") == "move"})
    inside = [c for c in sorted(receptacles) if c in invisible_containers and c not in involved and holders.get(c)]
    outside = [c for c in sorted(receptacles) if c not in invisible_containers and c not in involved and holders.get(c)]
    rng = derive_rng(split_seed, house_id, "control_revisit")
    chosen: list[dict[str, Any]] = []
    pool = list(inside)
    while pool and len(chosen) < wanted:
        c = pool.pop(rng.randrange(len(pool)))
        chosen.append({"container": c, "from_U": True, "seen_objects": sorted(holders[c])})
    pool = list(outside)
    while pool and len(chosen) < wanted:
        c = pool.pop(rng.randrange(len(pool)))
        chosen.append({"container": c, "from_U": False, "seen_objects": sorted(holders[c])})
    return {"controls": chosen, "wanted": wanted, "intervened_containers": intervened,
            "from_U": sum(1 for c in chosen if c["from_U"]), "from_outside_U": sum(1 for c in chosen if not c["from_U"]),
            "shortfall": wanted - len(chosen), "candidates_in_U": len(inside), "candidates_outside_U": len(outside)}


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


def dry_run_destinations(
    candidates: Sequence[Mapping[str, Any]], invisible_containers: set[str], *, split_seed: int, house_id: str,
    per_object: int = DRY_RUN_DESTINATIONS_PER_OBJECT,
) -> dict[str, list[str]]:
    """Which U destinations the dry run tests for each candidate object (ruling 39, m=8).

    白话：dry-run 的开销是 候选物体 × |U| × 最多 32 个点。裁决 39 后每个候选物体只用派生 RNG
    （标签 dry_run_order）从 U 里随机挑至多 m 个目的容器去试放偷看，自己所在的容器不算。
    被挑中的子集是均匀随机的，所以每个真实可行的 (物体, 目的容器) 对入选概率相同，抽样公平
    性不变；代价是可行集只覆盖测过的那部分，回执要一起记 pairs_tested 与 pairs_total。
    m=0 表示全部测，只用于复算 S1 的 50 条。输出按物体 id 排序、每个物体的目的容器保持抽签顺序。
    """

    if type(per_object) is not int or per_object < 0:
        raise LeanSelectionError("dry_run_destinations_per_object_invalid")
    rng = derive_rng(split_seed, house_id, "dry_run_order")
    out: dict[str, list[str]] = {}
    for obj in sorted(candidates, key=lambda o: o["object_id"]):
        pool = [c for c in sorted(invisible_containers) if c != obj.get("parent_receptacle")]
        if per_object and len(pool) > per_object:
            chosen = []
            for _ in range(per_object):
                chosen.append(pool.pop(rng.randrange(len(pool))))
            out[obj["object_id"]] = chosen
        else:
            rng.shuffle(pool)
            out[obj["object_id"]] = pool
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
    controls: Sequence[str] = (),
) -> list[str]:
    """Containers sweep two revisits, in order; move's two ends ordered by RNG; controls interleaved.

    白话：扫掠二要重访的容器序列。remove 重访源，add 重访目标，move 两端都重
    访，先源还是先目标由派生 RNG 逐个决定。重复容器只保留第一次出现。对照容器
    （裁决 34）再由同一条随机流逐个插到序列的随机位置，因此"变的先、不变的后"这
    种顺序信息不存在。
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
    for c in controls:
        if c in seq:
            raise LeanSelectionError(f"control_is_also_intervened:{c}")
        seq.insert(rng.randrange(len(seq) + 1), c)
    return seq


__all__ = [
    "LeanSelectionError",
    "derive_rng",
    "dry_run_destinations",
    "eligible_objects",
    "feasible_triples",
    "is_null_window",
    "revisit_sequence",
    "sample_interventions",
    "select_controls",
]
