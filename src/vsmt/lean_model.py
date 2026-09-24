"""D-224 / S2-03: VSMT-lean's learned cost heads -- the only trained part of the method.

Three heads score the S0-03 sealed feature rows: the association head a(f, e) over the 14 frozen
association features, the existence head r(e) over the 12 existence features, the birth head b(f)
over the 4 birth features (METHOD section 7).  Each head is LayerNorm on its input followed by two
GELU layers of width 128 and a linear read-out to one logit.  The heads never see a fragment id,
an entity id, a slot, a path or a sample name: they read the feature vectors positionally in the
frozen S0-03 order, so the runner can hand the logits back keyed by the sealed rows.

What this module provides:
  * ``make_heads`` / ``parameter_count`` / ``weights_payload`` / ``load_heads`` -- the network, its
    exact size, and a digest-carrying weights file with no private byte in it;
  * ``LeanScorer`` -- the scorer interface the S2-01 runner calls (``association_and_birth_logits``
    on stage A, ``existence_logits`` on the eligible stage-B rows), keys exactly the sealed rows;
  * ``frame_loss`` -- the registered loss: per-fragment softmax cross-entropy over the fragment's
    recalled columns plus its BIRTH column, plus per-entity existence binary cross-entropy, equal
    weights; fragments whose label is recall_miss / unlabelled / identity_ambiguous /
    duplicate_of_labelled and candidates whose label is identity_ambiguous enter no loss term;
  * ``train_heads`` -- AdamW, per-frame batches, a registered seed, every registered epoch run,
    and the epoch with the lowest validation loss kept (early stopping as best-epoch selection, no
    patience value to freeze); the same values on the same device give the same weights;
  * the AssocOnly switch (``assoc_only=True``): the same association and birth heads, no existence
    head and no existence loss term, trained from scratch (D-224-X ruling X3); NoVersion is a runner
    switch and uses these heads unchanged.

What it does not do: it does not build features (S0-03), does not solve or compile (S0-03, runner),
does not label (S0-04), does not roll out memories (runner) and does not orchestrate DAgger rounds
(S2-05 / S3-03); it only registers the schedule those steps must follow.

白话：这个模块是 VSMT-lean 里唯一要训练的部件。输入是 S0-03 封存好的三张特征表（每行是一个
色块—实体对、一个实体、或一个色块的公开特征），输出三个标量 logit；每个头是"输入归一化 + 两层
128 宽 GELU + 读出一维"的小 MLP，三个头合计五万余参数。训练目标：每个色块在"它召回的实体们 +
新建"之间做 softmax 交叉熵（标签来自 S0-04 teacher），每个应可见未匹配的实体做"已不在"的二元交
叉熵，两项等权；召回漏掉、无标注、身份含糊、同帧重复的色块不进损失。它不看未来，不读私有数据，
不认识任何 ID：换一下候选的顺序，每个实体拿到的 logit 不变。
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from vsmt import lean_arms as arms
from vsmt import lean_assignment as la

WEIGHTS_SCHEMA_VERSION = "vsmt-lean-cost-heads-weights-v1"

HEAD_NAMES = ("association", "existence", "birth")
HEAD_FEATURES: dict[str, tuple[str, ...]] = {
    "association": la.ASSOCIATION_FEATURES,
    "existence": la.EXISTENCE_FEATURES,
    "birth": la.BIRTH_FEATURES,
}
HIDDEN_WIDTH = 128
HIDDEN_LAYERS = 2
ARCHITECTURE = "LayerNorm(input) -> Linear(input, 128) -> GELU -> Linear(128, 128) -> GELU -> Linear(128, 1), one such head per feature table"
#: The S0-05 contract's own words for the loss (bound by the arms validator through the contract).
LOSS_RULE = ("per-fragment softmax cross-entropy over [recalled columns..., BIRTH column] plus "
             "per-entity existence binary cross-entropy, equal weights")
EARLY_STOPPING_RULE = "every registered epoch runs; the weights of the epoch with the lowest validation loss are kept (ties to the earlier epoch); no patience value"
BATCH_RULE = "per_frame"
OPTIMIZER = "AdamW"
#: Recipe values D-224 froze in the S0-05 contract (bound there by lean_arms.TRAINING_FROZEN).
LEARNING_RATE = dict(arms.TRAINING_FROZEN)["arms.VSMT-lean.training.learning_rate"]
EPOCHS = dict(arms.TRAINING_FROZEN)["arms.VSMT-lean.training.epochs"]
SEED_COUNT = dict(arms.TRAINING_FROZEN)["arms.VSMT-lean.training.seed_count"]
DAGGER_ROUNDS = dict(arms.TRAINING_FROZEN)["arms.VSMT-lean.training.dagger_rounds"]
MAIN_TABLE_ROUND = dict(arms.TRAINING_FROZEN)["arms.VSMT-lean.training.main_table_round"]
DAGGER_ROUND_0_SOURCE = arms.ROLLOUT_CONFIG_ARM
#: Label statuses (S0-04) that produce an association loss term; every other status is excluded.
ASSOCIATION_LOSS_STATUSES = ("labelled", "birth")
ASSOCIATION_EXCLUDED_STATUSES = ("recall_miss", "unlabelled", "identity_ambiguous", "duplicate_of_labelled")
EXISTENCE_TARGETS = {"gone": 1.0, "present": 0.0}
EXISTENCE_EXCLUDED_STATUSES = ("identity_ambiguous",)


class LeanModelError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanModelError(code)


def _finite(value: Any, code: str) -> float:
    _require(type(value) in {int, float} and type(value) is not bool, code)
    result = float(value)
    _require(math.isfinite(result), code)
    return result


# --------------------------------------------------------------------------
# 1. the heads
# --------------------------------------------------------------------------

def make_heads(*, assoc_only: bool, seed: int) -> Any:
    """The three (or, for AssocOnly, two) heads with a seeded initialisation."""

    import torch

    _require(type(seed) is int and seed >= 0, "seed_invalid")
    torch.manual_seed(int(seed))
    heads = torch.nn.ModuleDict()
    for name in HEAD_NAMES:
        if assoc_only and name == "existence":
            continue
        width = len(HEAD_FEATURES[name])
        heads[name] = torch.nn.Sequential(
            torch.nn.LayerNorm(width),
            torch.nn.Linear(width, HIDDEN_WIDTH), torch.nn.GELU(),
            torch.nn.Linear(HIDDEN_WIDTH, HIDDEN_WIDTH), torch.nn.GELU(),
            torch.nn.Linear(HIDDEN_WIDTH, 1),
        )
    return heads


def parameter_count(heads: Any) -> dict[str, int]:
    counts = {name: sum(int(p.numel()) for p in module.parameters()) for name, module in heads.items()}
    counts["total"] = sum(counts.values())
    return counts


def is_assoc_only(heads: Any) -> bool:
    return "existence" not in heads


def weights_payload(heads: Any, *, training: Mapping[str, Any]) -> dict[str, Any]:
    """The heads as plain floats plus a digest; no private byte can enter this file."""

    tensors: dict[str, dict[str, list[Any]]] = {}
    for name, module in heads.items():
        tensors[name] = {key: value.detach().cpu().numpy().astype(np.float64).tolist()
                         for key, value in module.state_dict().items()}
    body = {"schema_version": WEIGHTS_SCHEMA_VERSION, "architecture": ARCHITECTURE,
            "heads": sorted(tensors), "feature_orders": {name: list(HEAD_FEATURES[name]) for name in tensors},
            "tensors": tensors, "training": dict(training)}
    body["sha256"] = hashlib.sha256(canonical_json({k: v for k, v in body.items() if k != "training"}).encode("utf-8")).hexdigest()
    return body


def load_heads(payload: Mapping[str, Any], *, device: str = "cpu") -> Any:
    """Rebuild the heads from a payload, refusing a wrong schema, a wrong feature order or a bad digest."""

    import torch

    _require(payload.get("schema_version") == WEIGHTS_SCHEMA_VERSION, "weights_schema_invalid")
    expected = hashlib.sha256(canonical_json({k: v for k, v in payload.items() if k not in ("training", "sha256")}).encode("utf-8")).hexdigest()
    _require(payload.get("sha256") == expected, "weights_digest_mismatch")
    names = list(payload["heads"])
    _require(names in (sorted(HEAD_NAMES), sorted(n for n in HEAD_NAMES if n != "existence")), "weights_heads_invalid")
    for name in names:
        _require(list(payload["feature_orders"][name]) == list(HEAD_FEATURES[name]), f"weights_feature_order_drifted:{name}")
    heads = make_heads(assoc_only="existence" not in names, seed=0)
    with torch.no_grad():
        for name in names:
            state = {key: torch.as_tensor(np.asarray(value, dtype=np.float32)) for key, value in payload["tensors"][name].items()}
            heads[name].load_state_dict(state)
    return heads.to(device)


# --------------------------------------------------------------------------
# 2. the scorer the runner calls
# --------------------------------------------------------------------------

def _rows_tensor(rows: Sequence[Sequence[float]], *, width: int, device: str) -> Any:
    import torch

    matrix = np.asarray([[float(v) for v in row] for row in rows], dtype=np.float32).reshape(-1, width)
    return torch.as_tensor(matrix, device=device)


def _logits(head: Any, rows: Sequence[Sequence[float]], *, width: int, device: str) -> list[float]:
    import torch

    if not rows:
        return []
    with torch.no_grad():
        out = head(_rows_tensor(rows, width=width, device=device))
    return [float(v) for v in out.reshape(-1).cpu().numpy().astype(np.float64)]


class LeanScorer:
    """The S2-01 scorer interface over trained heads: logits keyed exactly by the sealed rows.

    白话：runner 把封存 A 的行交给它，它返回每个（色块，实体）对的关联 logit 与每个色块的新建
    logit；runner 再把可判定的存在行交给它，返回每个实体的"已不在"logit。键就是封存行的键，
    一个不多一个不少；特征按冻结顺序取位置。它不选原子，不读记忆。
    """

    def __init__(self, heads: Any, *, device: str = "cpu") -> None:
        self.heads = heads.to(device).eval()
        self.device = device
        self.assoc_only = is_assoc_only(heads)

    def association_and_birth_logits(self, stage_a: Mapping[str, Any]) -> dict[str, Any]:
        _require(tuple(stage_a["association_feature_order"]) == HEAD_FEATURES["association"], "stage_a_association_order_drifted")
        _require(tuple(stage_a["birth_feature_order"]) == HEAD_FEATURES["birth"], "stage_a_birth_order_drifted")
        rows = list(stage_a["association_rows"])
        births = list(stage_a["birth_rows"])
        association = _logits(self.heads["association"], [r["features"] for r in rows],
                              width=len(HEAD_FEATURES["association"]), device=self.device)
        birth = _logits(self.heads["birth"], [r["features"] for r in births],
                        width=len(HEAD_FEATURES["birth"]), device=self.device)
        return {
            "association_logits": {f"{r['fragment_id']}|{r['entity_id']}": value for r, value in zip(rows, association)},
            "birth_logits": {str(r["fragment_id"]): value for r, value in zip(births, birth)},
        }

    def existence_logits(self, rows: Sequence[Mapping[str, Any]], order: Sequence[str]) -> dict[str, float]:
        _require(not self.assoc_only, "assoc_only_has_no_existence_head")
        _require(tuple(order) == HEAD_FEATURES["existence"], "stage_b_existence_order_drifted")
        values = _logits(self.heads["existence"], [r["features"] for r in rows],
                         width=len(HEAD_FEATURES["existence"]), device=self.device)
        return {str(r["entity_id"]): value for r, value in zip(rows, values)}


# --------------------------------------------------------------------------
# 3. the loss over one labelled frame
# --------------------------------------------------------------------------

def validate_training_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """One labelled frame: stage A, the teacher's targets, the stage-B existence rows and their labels."""

    _require(type(record) is dict, "record_not_object")
    _require({"stage_a", "targets", "existence_rows", "existence_feature_order", "existence_labels"} <= set(record), "record_fields_missing")
    stage_a = record["stage_a"]
    _require(tuple(stage_a["association_feature_order"]) == HEAD_FEATURES["association"], "record_association_order_drifted")
    _require(tuple(stage_a["birth_feature_order"]) == HEAD_FEATURES["birth"], "record_birth_order_drifted")
    _require(tuple(record["existence_feature_order"]) == HEAD_FEATURES["existence"], "record_existence_order_drifted")
    _require(set(record["targets"]) == set(stage_a["rows"]), "record_targets_differ_from_rows")
    for fragment_id, target in record["targets"].items():
        status = target["status"]
        _require(status in ASSOCIATION_LOSS_STATUSES + ASSOCIATION_EXCLUDED_STATUSES, f"record_target_status_unknown:{status}")
        if status in ASSOCIATION_LOSS_STATUSES:
            columns = [*stage_a["recall"][fragment_id], f"{la.BIRTH_COLUMN_PREFIX}{fragment_id}"]
            _require(target["target"] in columns, f"record_target_not_among_the_fragment_columns:{fragment_id}")
    candidates = {str(r["entity_id"]) for r in record["existence_rows"]}
    _require(set(record["existence_labels"]) <= candidates, "record_existence_labels_outside_rows")
    for entity_id, label in record["existence_labels"].items():
        _require(label["status"] in EXISTENCE_TARGETS or label["status"] in EXISTENCE_EXCLUDED_STATUSES,
                 f"record_existence_status_unknown:{label['status']}")
    return clone_json(dict(record))


def frame_loss(heads: Any, record: Mapping[str, Any], *, device: str = "cpu") -> dict[str, Any]:
    """The registered loss on one labelled frame, with the term counts; None when no term applies.

    白话：对本帧每个有明确目标的色块，在"它召回的实体们 + 新建"之间算 softmax 交叉熵；对每个有明确
    gone/present 标签的存在候选算二元交叉熵；两项各自取平均后等权相加。召回漏掉（正确实体不在候选
    里）、无标注、身份含糊、同帧重复的色块和身份含糊的候选都不进损失，只计数。
    """

    import torch

    checked = validate_training_record(record)
    stage_a = checked["stage_a"]
    assoc_only = is_assoc_only(heads)
    association_by_fragment: dict[str, list[tuple[str, list[float]]]] = {}
    for row in stage_a["association_rows"]:
        association_by_fragment.setdefault(str(row["fragment_id"]), []).append((str(row["entity_id"]), row["features"]))
    birth_features = {str(row["fragment_id"]): row["features"] for row in stage_a["birth_rows"]}

    terms: list[Any] = []
    counted = {"association_terms": 0, "association_excluded": {status: 0 for status in ASSOCIATION_EXCLUDED_STATUSES},
               "existence_terms": 0, "existence_excluded": 0}
    for fragment_id in sorted(checked["targets"]):
        target = checked["targets"][fragment_id]
        if target["status"] not in ASSOCIATION_LOSS_STATUSES:
            counted["association_excluded"][target["status"]] += 1
            continue
        pairs = association_by_fragment.get(fragment_id, [])
        order = list(stage_a["recall"][fragment_id])
        _require([entity_id for entity_id, _ in pairs] == order, f"record_association_rows_out_of_recall_order:{fragment_id}")
        columns = [*order, f"{la.BIRTH_COLUMN_PREFIX}{fragment_id}"]
        logits = []
        if pairs:
            logits.append(heads["association"](_rows_tensor([f for _, f in pairs], width=len(HEAD_FEATURES["association"]), device=device)).reshape(-1))
        logits.append(heads["birth"](_rows_tensor([birth_features[fragment_id]], width=len(HEAD_FEATURES["birth"]), device=device)).reshape(-1))
        scores = torch.cat(logits)
        index = torch.as_tensor([columns.index(target["target"])], device=device)
        terms.append(("association", torch.nn.functional.cross_entropy(scores.unsqueeze(0), index)))
        counted["association_terms"] += 1
    existence_rows, existence_targets = [], []
    for row in checked["existence_rows"]:
        label = checked["existence_labels"].get(str(row["entity_id"]))
        if label is None:
            continue
        if label["status"] in EXISTENCE_EXCLUDED_STATUSES:
            counted["existence_excluded"] += 1
            continue
        existence_rows.append(row["features"])
        existence_targets.append(EXISTENCE_TARGETS[label["status"]])
    if existence_rows and not assoc_only:
        logits = heads["existence"](_rows_tensor(existence_rows, width=len(HEAD_FEATURES["existence"]), device=device)).reshape(-1)
        target = torch.as_tensor(existence_targets, dtype=torch.float32, device=device)
        terms.append(("existence", torch.nn.functional.binary_cross_entropy_with_logits(logits, target)))
        counted["existence_terms"] = len(existence_rows)
    association = [value for kind, value in terms if kind == "association"]
    existence = [value for kind, value in terms if kind == "existence"]
    parts = []
    if association:
        parts.append(torch.stack(association).mean())
    if existence:
        parts.append(existence[0])
    loss = torch.stack(parts).sum() if parts else None
    return {"loss": loss, **counted}


# --------------------------------------------------------------------------
# 4. training: AdamW, per-frame batches, best epoch by validation loss
# --------------------------------------------------------------------------

def _mean_loss(heads: Any, records: Sequence[Mapping[str, Any]], *, device: str) -> float | None:
    import torch

    values = []
    with torch.no_grad():
        for record in records:
            out = frame_loss(heads, record, device=device)
            if out["loss"] is not None:
                values.append(float(out["loss"].item()))
    return float(np.mean(values)) if values else None


def train_heads(
    train_records: Sequence[Mapping[str, Any]], validation_records: Sequence[Mapping[str, Any]], *,
    learning_rate: float | None, weight_decay: float | None, epochs: int | None, seed: int | None,
    assoc_only: bool, device: str = "cpu",
) -> dict[str, Any]:
    """Train the heads once and keep the best-validation epoch; every value explicit, None refused.

    白话：按登记的 seed 初始化并洗牌，每帧一个 batch，AdamW；每个 epoch 结束在 validation 上算一次
    平均损失，跑完全部登记的 epoch 后保留 validation 损失最低那个 epoch 的权重（并列取更早的）。
    同样的数据、同样的值、同一设备两次训练权重逐位相同。损失出现非有限值即判发散并如实返回。
    """

    import torch

    for name, value in (("learning_rate", learning_rate), ("weight_decay", weight_decay), ("epochs", epochs), ("seed", seed)):
        _require(value is not None, f"training_value_not_frozen:{name}")
    _require(_finite(learning_rate, "learning_rate_invalid") > 0.0, "learning_rate_invalid")
    _require(_finite(weight_decay, "weight_decay_invalid") >= 0.0, "weight_decay_invalid")
    _require(type(epochs) is int and epochs >= 1, "epochs_invalid")
    _require(type(seed) is int and seed >= 0, "seed_invalid")
    _require(len(train_records) >= 1 and len(validation_records) >= 1, "training_records_missing")
    for record in (*train_records, *validation_records):
        validate_training_record(record)

    heads = make_heads(assoc_only=assoc_only, seed=int(seed)).to(device)
    optimiser = torch.optim.AdamW(heads.parameters(), lr=float(learning_rate), weight_decay=float(weight_decay))
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    train_curve: list[float | None] = []
    validation_curve: list[float | None] = []
    best: tuple[float, int, dict[str, Any]] | None = None
    diverged = False
    for epoch in range(int(epochs)):
        heads.train()
        order = torch.randperm(len(train_records), generator=generator).tolist()
        total, count = 0.0, 0
        for index in order:
            out = frame_loss(heads, train_records[index], device=device)
            if out["loss"] is None:
                continue
            if not torch.isfinite(out["loss"]):
                diverged = True
                break
            optimiser.zero_grad()
            out["loss"].backward()
            optimiser.step()
            total += float(out["loss"].item())
            count += 1
        if diverged:
            train_curve.append(None)
            validation_curve.append(None)
            break
        heads.eval()
        train_curve.append(total / count if count else None)
        validation = _mean_loss(heads, validation_records, device=device)
        validation_curve.append(validation)
        if validation is not None and (best is None or validation < best[0]):
            best = (validation, epoch, {name: {k: v.detach().cpu().clone() for k, v in module.state_dict().items()}
                                       for name, module in heads.items()})
    _require(best is not None or diverged, "validation_loss_undefined_on_every_epoch")
    if best is not None:
        with torch.no_grad():
            for name, state in best[2].items():
                heads[name].load_state_dict(state)
    training = {"optimizer": OPTIMIZER, "learning_rate": learning_rate, "weight_decay": weight_decay, "epochs": epochs,
                "seed": seed, "assoc_only": assoc_only, "batch": BATCH_RULE, "early_stopping": EARLY_STOPPING_RULE,
                "best_epoch": None if best is None else best[1], "train_frames": len(train_records),
                "validation_frames": len(validation_records), "device": device, "diverged": diverged}
    return {"weights": weights_payload(heads, training=training), "heads": heads, "train_curve": train_curve,
            "validation_curve": validation_curve, "best_epoch": None if best is None else best[1], "diverged": diverged}


def recipe_matches_contract(*, learning_rate: float, epochs: int, seeds: Sequence[int], dagger_rounds: int, main_table_round: int) -> dict[str, Any]:
    """The values a run passes must be the ones D-224 froze; seeds are the registered list, not configurations."""

    _require(learning_rate == LEARNING_RATE, "recipe_learning_rate_differs_from_frozen")
    _require(epochs == EPOCHS, "recipe_epochs_differ_from_frozen")
    _require(len(seeds) == SEED_COUNT and len(set(seeds)) == SEED_COUNT and all(type(s) is int for s in seeds), "recipe_seeds_invalid")
    _require(dagger_rounds == DAGGER_ROUNDS and main_table_round == MAIN_TABLE_ROUND, "recipe_dagger_differs_from_frozen")
    return {"learning_rate": learning_rate, "epochs": epochs, "seeds": list(seeds), "dagger_rounds": dagger_rounds,
            "main_table_round": main_table_round}


def dagger_schedule(rollout_config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The registered DAgger rounds: round 0 on ELU-P rollouts at the pre-registered configuration, round 1 on the
    round-0 model's own rollouts; both reported, the main table reads the registered round (D-224, D-224-X ruling X4)."""

    _require(tuple(rollout_config) == arms.ROLLOUT_CONFIG_PARAMETERS, "rollout_config_parameters_mismatch")
    for name in arms.ROLLOUT_CONFIG_PARAMETERS:
        _require(rollout_config[name] is not None, f"rollout_config_value_not_frozen:{name}")
    rounds = []
    for index in range(DAGGER_ROUNDS):
        rounds.append({
            "round": index,
            "memory_source": DAGGER_ROUND_0_SOURCE if index == 0 else "the round-%d model's own rollouts" % (index - 1),
            "memory_config": dict(rollout_config) if index == 0 else None,
            "labels": "S0-04 teacher on the sealed rows of those rollouts",
            "in_main_table": index == MAIN_TABLE_ROUND,
        })
    return rounds


__all__ = [
    "ARCHITECTURE",
    "ASSOCIATION_EXCLUDED_STATUSES",
    "ASSOCIATION_LOSS_STATUSES",
    "BATCH_RULE",
    "DAGGER_ROUNDS",
    "EARLY_STOPPING_RULE",
    "EPOCHS",
    "EXISTENCE_EXCLUDED_STATUSES",
    "EXISTENCE_TARGETS",
    "HEAD_FEATURES",
    "HEAD_NAMES",
    "HIDDEN_LAYERS",
    "HIDDEN_WIDTH",
    "LEARNING_RATE",
    "LOSS_RULE",
    "LeanModelError",
    "LeanScorer",
    "MAIN_TABLE_ROUND",
    "OPTIMIZER",
    "SEED_COUNT",
    "WEIGHTS_SCHEMA_VERSION",
    "dagger_schedule",
    "frame_loss",
    "is_assoc_only",
    "load_heads",
    "make_heads",
    "parameter_count",
    "recipe_matches_contract",
    "train_heads",
    "validate_training_record",
    "weights_payload",
]
