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
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from vsmt import lean_arms as arms
from vsmt import lean_assignment as la

WEIGHTS_SCHEMA_VERSION = "vsmt-lean-cost-heads-weights-v1"
#: Ruling 89-2 / 89-3 (2026-09-30): heads whose first layer is the field-wise encoding instead of the row LayerNorm.
WEIGHTS_SCHEMA_VERSION_FIELD_WISE = "vsmt-lean-cost-heads-weights-v2-field-wise"

HEAD_NAMES = ("association", "existence", "birth")
HEAD_FEATURES: dict[str, tuple[str, ...]] = {
    "association": la.ASSOCIATION_FEATURES,
    "existence": la.EXISTENCE_FEATURES,
    "birth": la.BIRTH_FEATURES,
}
HIDDEN_WIDTH = 128
HIDDEN_LAYERS = 2
ARCHITECTURE = "LayerNorm(input) -> Linear(input, 128) -> GELU -> Linear(128, 128) -> GELU -> Linear(128, 1), one such head per feature table"
ARCHITECTURE_FIELD_WISE = ("FieldEncoding(input) -> Linear(input, 128) -> GELU -> Linear(128, 128) -> GELU -> Linear(128, 1), one such "
                           "head per feature table")
#: Ruling 89-2 (a) / 89-3 (a): the field-wise encoding.  A whole-row LayerNorm is invariant to scaling the row, so a
#: large count in one field (ticks since last seen, observation count) crushed every other cue of that row (ruling 88,
#: finding 3).  Instead each field is encoded on its own: counts and frame numbers take log1p and are then standardised
#: with the mean and standard deviation over the training houses; other unbounded quantities (distances, a log ratio, a
#: height difference) are standardised only; ratios, cosines, bounded margins, one-hots and flags pass unchanged.
FIELD_ENCODING: dict[str, str] = {
    **{name: "identity" for name in (
        "cosine_to_descriptor_mean", "cosine_to_best_view_descriptor", "aabb_iou", "state_is_active", "state_is_dormant",
        "state_is_retracted", "cosine_margin_to_runner_up", "mutual_best", "should_be_visible_ratio", "free_space_coverage_ratio",
        "camera_view_cosine", "best_fragment_cosine", "best_fragment_still_unassigned", "best_cosine_to_any_entity",
        "depth_valid_ratio")},
    **{name: "standardize" for name in (
        "centroid_distance_m", "log_size_ratio", "support_height_difference_m", "camera_distance_m")},
    **{name: "log1p_standardize" for name in (
        "ticks_since_last_seen", "missed_opportunity_count", "cosine_rank_within_recall", "observation_count",
        "rac_run_rho_070", "rac_run_rho_085", "matches_since_birth", "eligible_frames_since_birth",
        "free_space_coverage_sum_since_birth", "active_entities_within_radius", "pixel_count")},
}
FIELD_ENCODING_STATISTICS_RULE = ("mean and population standard deviation of each encoded field over every row of that head's table in the "
                                  "training houses' records; a standard deviation below 1e-8 is replaced by 1; identity fields keep 0 and 1")
#: Ruling 89-2 (a): the existence loss weights gone rows by (present rows / gone rows) of the training houses.
EXISTENCE_CLASS_WEIGHT_RULE = "binary cross-entropy with pos_weight = present rows / gone rows over the training houses' records"
#: Proposed for pending ruling 91 only (2026-09-30, off by default, not a registered recipe): the learning rate of epoch e is
#: lr_min + (lr - lr_min) * (1 + cos(pi * e / epochs)) / 2 and each step's gradient norm is clipped.
EXISTENCE_PRIOR_CORRECTION_RULE = ("the existence logit handed to decisions is the head output minus ln(pos_weight): training with pos_weight w "
                                   "moves the optimal logit up by ln w, so without it tau_r 0.5 acts like tau_r 1/(1+w)")
COSINE_SCHEDULE_RULE = "per epoch e of E: lr_e = lr_min + (lr - lr_min) * (1 + cos(pi * e / E)) / 2; gradient norm clipped before each step"
#: Ruling 96 (a) (2026-10-01): the head groups of the per-group checkpoint selection and the validation term each is kept on.
#: The association and birth heads share one cross-entropy (a fragment's softmax over its recalled columns and the BIRTH
#: column), so they are one group and keep one epoch.
GROUP_SELECTION = (("association_birth", ("association", "birth"), "association"), ("existence", ("existence",), "existence"))
GROUP_SELECTION_RULE = ("training unchanged; the association and birth heads keep together the epoch of the lowest association "
                        "validation term, the existence head the epoch of the lowest existence validation term, ties to the earlier "
                        "epoch; the total-loss selection is kept alongside")
#: The S0-05 contract's own words for the loss (bound by the arms validator through the contract).
LOSS_RULE = ("per-fragment softmax cross-entropy over [recalled columns..., BIRTH column] plus "
             "per-entity existence binary cross-entropy, equal weights")
EARLY_STOPPING_RULE = "every registered epoch runs; the weights of the epoch with the lowest validation loss are kept (ties to the earlier epoch); no patience value"
BATCH_RULE = "per_frame"
#: D-224-S1 ruling 79-5 (a), 2026-09-28: each head draws its initial weights from its own seed derived from (seed, head
#: name), so the association and birth heads start bit-identical in VSMT-lean and in AssocOnly (which builds no existence
#: head).  Before, one shared stream ran association -> existence -> birth, and AssocOnly's birth head drew other numbers.
INITIALISATION_RULE = "per-head torch.manual_seed(int.from_bytes(sha256(f'{seed}|{head}')[:8], 'big') % 2**63) before building each head"
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

def head_seed(seed: int, name: str) -> int:
    """The initialisation seed of one head (ruling 79-5 (a)): independent of which other heads are built."""

    return int.from_bytes(hashlib.sha256(f"{int(seed)}|{name}".encode("utf-8")).digest()[:8], "big") % (2 ** 63)


def _field_encoder_class() -> Any:
    import torch

    class FieldEncoding(torch.nn.Module):
        """log1p on the flagged fields, then (x - mean) / std per field; buffers only, nothing is trained."""

        def __init__(self, width: int) -> None:
            super().__init__()
            self.register_buffer("log1p", torch.zeros(width))
            self.register_buffer("mean", torch.zeros(width))
            self.register_buffer("std", torch.ones(width))

        def forward(self, x: Any) -> Any:
            logged = torch.where(self.log1p > 0.5, torch.log1p(torch.clamp(x, min=0.0)), x)
            return (logged - self.mean) / self.std

    return FieldEncoding


def encode_rows_numpy(rows: Any, names: Sequence[str]) -> Any:
    """The log1p step of the field-wise encoding on a float64 matrix (for the statistics)."""

    matrix = np.asarray(rows, dtype=np.float64).reshape(-1, len(names))
    for index, name in enumerate(names):
        if FIELD_ENCODING[name] == "log1p_standardize":
            matrix[:, index] = np.log1p(np.clip(matrix[:, index], 0.0, None))
    return matrix


def _encoding_entry(name: str, columns: Mapping[int, Any], rows: int) -> dict[str, Any]:
    """One head's statistics from its encoded (log1p already applied) non-identity columns, by field index."""

    names = HEAD_FEATURES[name]
    kinds = [FIELD_ENCODING[field] for field in names]
    mean, std = [0.0] * len(names), [1.0] * len(names)
    for index, column in columns.items():
        mean[index] = float(column.mean())
        spread = float(column.std())
        std[index] = spread if spread >= 1e-8 else 1.0
    return {"fields": list(names), "kinds": kinds, "log1p": [1.0 if k == "log1p_standardize" else 0.0 for k in kinds],
            "mean": mean, "std": std, "rows": rows}


def _head_tables(record: Mapping[str, Any]) -> tuple[tuple[str, Sequence[Mapping[str, Any]]], ...]:
    return (("association", record["stage_a"]["association_rows"]), ("birth", record["stage_a"]["birth_rows"]),
            ("existence", record["existence_rows"]))


def field_encoding_statistics(records: Sequence[Mapping[str, Any]], *, heads: Sequence[str] = HEAD_NAMES) -> dict[str, Any]:
    """Per head: which fields take log1p, and the mean / std the encoding subtracts and divides by (training houses only)."""

    tables: dict[str, list[list[float]]] = {name: [] for name in heads}
    for record in records:
        for name, rows in _head_tables(record):
            if name in tables:
                tables[name].extend(row["features"] for row in rows)
    out: dict[str, Any] = {}
    for name in heads:
        names = HEAD_FEATURES[name]
        columns: dict[int, Any] = {}
        if tables[name]:
            matrix = encode_rows_numpy(tables[name], names)
            columns = {index: matrix[:, index] for index, field in enumerate(names) if FIELD_ENCODING[field] != "identity"}
        out[name] = _encoding_entry(name, columns, len(tables[name]))
    return out


def field_encoding_statistics_streamed(records: Iterable[Mapping[str, Any]], *, heads: Sequence[str] = HEAD_NAMES) -> dict[str, Any]:
    """``field_encoding_statistics`` over records read one at a time (ruling 104-3, the first of the two streamed passes).

    Only the fields the encoding standardises are kept, one float64 column each, so neither the raw records nor the
    identity fields are ever all in memory.  The numbers are those of ``field_encoding_statistics``: the same float64
    values in the same row order, log1p on the same contiguous clipped column, numpy's mean and population std of the
    column (pinned by test against the whole-matrix function, beyond numpy's pairwise-summation block sizes).

    白话：编码统计要用训练 house 的全部特征行，现行做法先把全部原始记录读进内存再算（S3 第 1 轮约 85 GB）。这里逐条读，
    只留下要标准化的那几列（每列一个连续的 float64 数组），读完一条就丢；算出的均值与标准差与整表算法逐位相同。
    """

    keep = {name: [index for index, field in enumerate(HEAD_FEATURES[name]) if FIELD_ENCODING[field] != "identity"] for name in heads}
    chunks: dict[str, list[Any]] = {name: [] for name in heads}
    counts = {name: 0 for name in heads}
    for record in records:
        for name, rows in _head_tables(record):
            if name not in chunks or not rows:
                continue
            matrix = np.asarray([row["features"] for row in rows], dtype=np.float64).reshape(-1, len(HEAD_FEATURES[name]))
            chunks[name].append(matrix[:, keep[name]])
            counts[name] += matrix.shape[0]
    out: dict[str, Any] = {}
    for name in heads:
        columns: dict[int, Any] = {}
        if counts[name]:
            for position, index in enumerate(keep[name]):
                column = np.concatenate([chunk[:, position] for chunk in chunks[name]])
                if FIELD_ENCODING[HEAD_FEATURES[name][index]] == "log1p_standardize":
                    column = np.log1p(np.clip(column, 0.0, None))
                columns[index] = column
        chunks[name] = []
        out[name] = _encoding_entry(name, columns, counts[name])
    return out


def make_heads(*, assoc_only: bool, seed: int, encoding: Mapping[str, Any] | None = None) -> Any:
    """The three (or, for AssocOnly, two) heads with a seeded initialisation.

    白话：每个头按"seed 加头名"各自播种再初始化（裁决 79-5 (a)），所以同一 seed 下 AssocOnly 与 VSMT-lean 的关联头、
    新建头起点逐位相同，因果对照只差存在头与生命周期，不再多一份随机初始化的差别。
    """

    import torch

    _require(type(seed) is int and seed >= 0, "seed_invalid")
    heads = torch.nn.ModuleDict()
    encoder = _field_encoder_class() if encoding is not None else None
    for name in HEAD_NAMES:
        if assoc_only and name == "existence":
            continue
        torch.manual_seed(head_seed(int(seed), name))
        width = len(HEAD_FEATURES[name])
        if encoder is None:
            first = torch.nn.LayerNorm(width)
        else:
            stats = encoding[name]
            _require(list(stats["fields"]) == list(HEAD_FEATURES[name]), f"encoding_fields_drifted:{name}")
            first = encoder(width)
            with torch.no_grad():
                first.log1p.copy_(torch.as_tensor(stats["log1p"], dtype=torch.float32))
                first.mean.copy_(torch.as_tensor(stats["mean"], dtype=torch.float32))
                first.std.copy_(torch.as_tensor(stats["std"], dtype=torch.float32))
        heads[name] = torch.nn.Sequential(
            first,
            torch.nn.Linear(width, HIDDEN_WIDTH), torch.nn.GELU(),
            torch.nn.Linear(HIDDEN_WIDTH, HIDDEN_WIDTH), torch.nn.GELU(),
            torch.nn.Linear(HIDDEN_WIDTH, 1),
        )
    heads.feature_orders = {name: tuple(HEAD_FEATURES[name]) for name in heads}
    heads.encoding = None if encoding is None else clone_json(dict(encoding))
    heads.existence_logit_offset = 0.0  # pending ruling 91 only: -ln(pos_weight) when the prior correction is on
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
    encoding = getattr(heads, "encoding", None)
    orders = getattr(heads, "feature_orders", None) or {name: tuple(HEAD_FEATURES[name]) for name in tensors}
    body = {"schema_version": WEIGHTS_SCHEMA_VERSION if encoding is None else WEIGHTS_SCHEMA_VERSION_FIELD_WISE,
            "architecture": ARCHITECTURE if encoding is None else ARCHITECTURE_FIELD_WISE,
            "heads": sorted(tensors), "feature_orders": {name: list(orders[name]) for name in tensors},
            "tensors": tensors, "training": dict(training)}
    if encoding is not None:
        body["encoding"] = {"rule": FIELD_ENCODING_STATISTICS_RULE, "per_head": {name: encoding[name] for name in tensors}}
    offset = float(getattr(heads, "existence_logit_offset", 0.0) or 0.0)
    if offset != 0.0:  # pending ruling 91 only; inside the digest
        body["existence_logit_offset"] = {"value": offset, "rule": EXISTENCE_PRIOR_CORRECTION_RULE}
    body["sha256"] = hashlib.sha256(canonical_json({k: v for k, v in body.items() if k != "training"}).encode("utf-8")).hexdigest()
    return body


def load_heads(payload: Mapping[str, Any], *, device: str = "cpu") -> Any:
    """Rebuild the heads from a payload, refusing a wrong schema, a wrong feature order or a bad digest."""

    import torch

    schema = payload.get("schema_version")
    _require(schema in (WEIGHTS_SCHEMA_VERSION, WEIGHTS_SCHEMA_VERSION_FIELD_WISE), "weights_schema_invalid")
    expected = hashlib.sha256(canonical_json({k: v for k, v in payload.items() if k not in ("training", "sha256")}).encode("utf-8")).hexdigest()
    _require(payload.get("sha256") == expected, "weights_digest_mismatch")
    names = list(payload["heads"])
    _require(names in (sorted(HEAD_NAMES), sorted(n for n in HEAD_NAMES if n != "existence")), "weights_heads_invalid")
    legacy_existence = False
    for name in names:
        order = list(payload["feature_orders"][name])
        if name == "existence" and schema == WEIGHTS_SCHEMA_VERSION and order == list(la.LEGACY_EXISTENCE_FEATURES):
            # a head trained before ruling 89-2: it loads (its association and birth heads still score) but cannot
            # score the extended existence rows; LeanScorer refuses that call
            legacy_existence = True
            continue
        _require(order == list(HEAD_FEATURES[name]), f"weights_feature_order_drifted:{name}")
    encoding = payload["encoding"]["per_head"] if schema == WEIGHTS_SCHEMA_VERSION_FIELD_WISE else None
    heads = make_heads(assoc_only="existence" not in names, seed=0, encoding=encoding)
    if "existence_logit_offset" in payload:
        heads.existence_logit_offset = float(payload["existence_logit_offset"]["value"])
    if legacy_existence:
        width = len(la.LEGACY_EXISTENCE_FEATURES)
        heads["existence"] = torch.nn.Sequential(
            torch.nn.LayerNorm(width), torch.nn.Linear(width, HIDDEN_WIDTH), torch.nn.GELU(),
            torch.nn.Linear(HIDDEN_WIDTH, HIDDEN_WIDTH), torch.nn.GELU(), torch.nn.Linear(HIDDEN_WIDTH, 1))
        heads.feature_orders["existence"] = tuple(la.LEGACY_EXISTENCE_FEATURES)
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
        _require(tuple(getattr(self.heads, "feature_orders", HEAD_FEATURES)["existence"]) == HEAD_FEATURES["existence"],
                 "legacy_existence_head_cannot_score_the_ruling_89_rows")
        _require(tuple(order) == HEAD_FEATURES["existence"], "stage_b_existence_order_drifted")
        values = _logits(self.heads["existence"], [r["features"] for r in rows],
                         width=len(HEAD_FEATURES["existence"]), device=self.device)
        offset = float(getattr(self.heads, "existence_logit_offset", 0.0) or 0.0)
        return {str(r["entity_id"]): value + offset for r, value in zip(rows, values)}


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


def prepare_frame(record: Mapping[str, Any], *, device: str = "cpu") -> dict[str, Any]:
    """Everything ``frame_loss`` needs from one record, checked once and turned into tensors once.

    Engineering (2026-09-27, round-0 timing probe: 389 s per epoch for 32,550 frames on one CPU thread): training
    re-validated, deep-copied and re-tensorised every record at every step of every epoch.  The record is fixed, so
    the same checks and the same tensors can be made once; ``prepared_loss`` then runs exactly the operations
    ``frame_loss`` ran, in the same order, so losses and trained weights are bit for bit the same (pinned by test).
    """

    import torch

    checked = validate_training_record(record)
    stage_a = checked["stage_a"]
    association_by_fragment: dict[str, list[tuple[str, list[float]]]] = {}
    for row in stage_a["association_rows"]:
        association_by_fragment.setdefault(str(row["fragment_id"]), []).append((str(row["entity_id"]), row["features"]))
    birth_features = {str(row["fragment_id"]): row["features"] for row in stage_a["birth_rows"]}
    association: list[tuple[Any, Any, Any]] = []
    excluded = {status: 0 for status in ASSOCIATION_EXCLUDED_STATUSES}
    for fragment_id in sorted(checked["targets"]):
        target = checked["targets"][fragment_id]
        if target["status"] not in ASSOCIATION_LOSS_STATUSES:
            excluded[target["status"]] += 1
            continue
        pairs = association_by_fragment.get(fragment_id, [])
        order = list(stage_a["recall"][fragment_id])
        _require([entity_id for entity_id, _ in pairs] == order, f"record_association_rows_out_of_recall_order:{fragment_id}")
        columns = [*order, f"{la.BIRTH_COLUMN_PREFIX}{fragment_id}"]
        pair_rows = (_rows_tensor([f for _, f in pairs], width=len(HEAD_FEATURES["association"]), device=device)
                     if pairs else None)
        birth_row = _rows_tensor([birth_features[fragment_id]], width=len(HEAD_FEATURES["birth"]), device=device)
        association.append((pair_rows, birth_row, torch.as_tensor([columns.index(target["target"])], device=device)))
    existence_rows, existence_targets = [], []
    existence_excluded = 0
    for row in checked["existence_rows"]:
        label = checked["existence_labels"].get(str(row["entity_id"]))
        if label is None:
            continue
        if label["status"] in EXISTENCE_EXCLUDED_STATUSES:
            existence_excluded += 1
            continue
        existence_rows.append(row["features"])
        existence_targets.append(EXISTENCE_TARGETS[label["status"]])
    existence = None
    if existence_rows:
        existence = (_rows_tensor(existence_rows, width=len(HEAD_FEATURES["existence"]), device=device),
                     torch.as_tensor(existence_targets, dtype=torch.float32, device=device), len(existence_rows))
    return {"association": association, "association_excluded": excluded, "existence": existence,
            "existence_excluded": existence_excluded}


def prepared_loss(heads: Any, prepared: Mapping[str, Any], *, existence_pos_weight: Any = None) -> dict[str, Any]:
    """The registered loss on one prepared frame (see ``prepare_frame``); the operations of ``frame_loss``.

    ``existence_pos_weight`` (ruling 89-2 (a), a 1-element tensor) weights the gone rows; None is the unweighted loss.
    """

    import torch

    assoc_only = is_assoc_only(heads)
    terms: list[Any] = []
    counted = {"association_terms": 0, "association_excluded": dict(prepared["association_excluded"]),
               "existence_terms": 0, "existence_excluded": prepared["existence_excluded"]}
    for pair_rows, birth_row, index in prepared["association"]:
        logits = []
        if pair_rows is not None:
            logits.append(heads["association"](pair_rows).reshape(-1))
        logits.append(heads["birth"](birth_row).reshape(-1))
        scores = torch.cat(logits)
        terms.append(("association", torch.nn.functional.cross_entropy(scores.unsqueeze(0), index)))
        counted["association_terms"] += 1
    if prepared["existence"] is not None and not assoc_only:
        rows, target, count = prepared["existence"]
        logits = heads["existence"](rows).reshape(-1)
        terms.append(("existence", torch.nn.functional.binary_cross_entropy_with_logits(logits, target, pos_weight=existence_pos_weight)))
        counted["existence_terms"] = count
    association = [value for kind, value in terms if kind == "association"]
    existence = [value for kind, value in terms if kind == "existence"]
    parts = []
    if association:
        parts.append(torch.stack(association).mean())
    if existence:
        parts.append(existence[0])
    loss = torch.stack(parts).sum() if parts else None
    # the two terms kept apart for the per-epoch record (user, 2026-09-30); the loss above is unchanged
    return {"loss": loss, **counted, "association_loss": parts[0] if association else None,
            "existence_loss": existence[0] if existence else None}


def batch_prepared(prepared: Mapping[str, Any], *, device: str = "cpu") -> dict[str, Any]:
    """One prepared frame with its fragments batched: one forward per head per frame instead of one per fragment.

    Engineering for the ruling-89 recipe (2026-09-30; one registered 20-epoch training on the round-1 records took 5,522 s,
    most of it in per-fragment forward calls).  The loss is the same function -- the mean over labelled fragments of the
    softmax cross-entropy over [recalled columns..., BIRTH] plus the existence term -- computed on a padded score matrix whose
    padding is -inf, so values agree with ``prepared_loss`` up to float summation order (pinned by test).  It is used only
    under ``field_encoding``; the registered default path is untouched.
    """

    import torch

    pairs, births, index_rows, targets = [], [], [], []
    offset = 0
    for pair_rows, birth_row, target in prepared["association"]:
        count = 0 if pair_rows is None else int(pair_rows.shape[0])
        if pair_rows is not None:
            pairs.append(pair_rows)
        births.append(birth_row)
        index_rows.append((offset, count))
        offset += count
        targets.append(int(target.item()))
    batched: dict[str, Any] = {"fragments": len(targets), "existence": prepared["existence"],
                               "association_excluded": prepared["association_excluded"], "existence_excluded": prepared["existence_excluded"]}
    if targets:
        width = max(count for _, count in index_rows) + 1
        total_pairs = offset
        index = torch.zeros((len(targets), width), dtype=torch.long, device=device)
        mask = torch.zeros((len(targets), width), dtype=torch.bool, device=device)
        for row, (start, count) in enumerate(index_rows):
            if count:
                index[row, :count] = torch.arange(start, start + count, device=device)
            index[row, count] = total_pairs + row
            mask[row, :count + 1] = True
        batched.update({"pairs": torch.cat(pairs) if pairs else None, "births": torch.cat(births), "index": index, "mask": mask,
                        "targets": torch.as_tensor(targets, dtype=torch.long, device=device)})
    return batched


def batched_loss(heads: Any, batched: Mapping[str, Any], *, existence_pos_weight: Any = None) -> dict[str, Any]:
    """``prepared_loss`` on a ``batch_prepared`` frame (same terms, same weights, batched forward calls)."""

    import torch

    parts = []
    association_loss = existence_loss = None
    if batched["fragments"]:
        pair_logits = heads["association"](batched["pairs"]).reshape(-1) if batched["pairs"] is not None else None
        birth_logits = heads["birth"](batched["births"]).reshape(-1)
        flat = birth_logits if pair_logits is None else torch.cat([pair_logits, birth_logits])
        scores = flat[batched["index"]].masked_fill(~batched["mask"], float("-inf"))
        association_loss = torch.nn.functional.cross_entropy(scores, batched["targets"])
        parts.append(association_loss)
    existence_terms = 0
    if batched["existence"] is not None and not is_assoc_only(heads):
        rows, target, count = batched["existence"]
        logits = heads["existence"](rows).reshape(-1)
        existence_loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, target, pos_weight=existence_pos_weight)
        parts.append(existence_loss)
        existence_terms = count
    loss = torch.stack(parts).sum() if parts else None
    return {"loss": loss, "association_terms": batched["fragments"], "existence_terms": existence_terms,
            "association_loss": association_loss, "existence_loss": existence_loss}


def frame_loss(heads: Any, record: Mapping[str, Any], *, device: str = "cpu") -> dict[str, Any]:
    """The registered loss on one labelled frame, with the term counts; None when no term applies.

    白话：对本帧每个有明确目标的色块，在"它召回的实体们 + 新建"之间算 softmax 交叉熵；对每个有明确
    gone/present 标签的存在候选算二元交叉熵；两项各自取平均后等权相加。召回漏掉（正确实体不在候选
    里）、无标注、身份含糊、同帧重复的色块和身份含糊的候选都不进损失，只计数。
    """

    return prepared_loss(heads, prepare_frame(record, device=device))


# --------------------------------------------------------------------------
# 4. training: AdamW, per-frame batches, best epoch by validation loss
# --------------------------------------------------------------------------

class _TermMeans:
    """Running means of the summed loss and of each term over the frames that carry it (the per-epoch record)."""

    def __init__(self) -> None:
        self.sums = {"total": 0.0, "association": 0.0, "existence": 0.0}
        self.counts = {"total": 0, "association": 0, "existence": 0}

    def add(self, out: Mapping[str, Any]) -> None:
        for key, name in (("total", "loss"), ("association", "association_loss"), ("existence", "existence_loss")):
            value = out.get(name)
            if value is not None:
                self.sums[key] += float(value.item())
                self.counts[key] += 1

    def means(self) -> dict[str, float | None]:
        return {key: (self.sums[key] / self.counts[key]) if self.counts[key] else None for key in self.sums}


def _mean_loss_and_terms(heads: Any, prepared_records: Sequence[Mapping[str, Any]], *, existence_pos_weight: Any = None,
                         loss_fn: Any = None) -> dict[str, float | None]:
    import torch

    tally = _TermMeans()
    with torch.no_grad():
        for prepared in prepared_records:
            tally.add((loss_fn or prepared_loss)(heads, prepared, existence_pos_weight=existence_pos_weight))
    return tally.means()


def _mean_loss(heads: Any, prepared_records: Sequence[Mapping[str, Any]], *, existence_pos_weight: Any = None,
               loss_fn: Any = None) -> float | None:
    import torch

    values = []
    with torch.no_grad():
        for prepared in prepared_records:
            out = (loss_fn or prepared_loss)(heads, prepared, existence_pos_weight=existence_pos_weight)
            if out["loss"] is not None:
                values.append(float(out["loss"].item()))
    return float(np.mean(values)) if values else None


def _check_training_values(*, learning_rate: Any, weight_decay: Any, epochs: Any, seed: Any) -> None:
    for name, value in (("learning_rate", learning_rate), ("weight_decay", weight_decay), ("epochs", epochs), ("seed", seed)):
        _require(value is not None, f"training_value_not_frozen:{name}")
    _require(_finite(learning_rate, "learning_rate_invalid") > 0.0, "learning_rate_invalid")
    _require(_finite(weight_decay, "weight_decay_invalid") >= 0.0, "weight_decay_invalid")
    _require(type(epochs) is int and epochs >= 1, "epochs_invalid")
    _require(type(seed) is int and seed >= 0, "seed_invalid")


def _trained_head_names(assoc_only: bool) -> list[str]:
    return [n for n in HEAD_NAMES if not (assoc_only and n == "existence")]


def _existence_class_weight(frames: Sequence[Mapping[str, Any]], *, device: str) -> tuple[Any, dict[str, Any]]:
    """Ruling 89-2 (a): pos_weight = present rows / gone rows over the training frames (prepared or batched alike)."""

    import torch

    gone = sum(int(round(float(p["existence"][1].sum().item()))) for p in frames if p["existence"] is not None)
    total = sum(p["existence"][2] for p in frames if p["existence"] is not None)
    _require(gone >= 1 and total - gone >= 1, "existence_class_weight_needs_both_classes")
    class_counts = {"gone": gone, "present": total - gone, "pos_weight": (total - gone) / gone}
    return torch.as_tensor([(total - gone) / gone], dtype=torch.float32, device=device), class_counts


def train_heads(
    train_records: Sequence[Mapping[str, Any]], validation_records: Sequence[Mapping[str, Any]], *,
    learning_rate: float | None, weight_decay: float | None, epochs: int | None, seed: int | None,
    assoc_only: bool, device: str = "cpu", epoch_callback: Any = None,
    field_encoding: bool = False, existence_class_weight: bool = False,
    cosine_min_learning_rate: float | None = None, gradient_clip_norm: float | None = None,
    existence_prior_correction: bool = False, group_selection: bool = False, best_callback: Any = None,
    optimizer_foreach: bool = False,
) -> dict[str, Any]:
    """Train the heads once and keep the best-validation epoch; every value explicit, None refused.

    ``group_selection`` (ruling 96 (a), off by default): training runs exactly as without it; at every epoch end the run
    additionally remembers, per head group, the weights of the epoch whose own validation term is lowest (``GROUP_SELECTION``),
    and returns that combination under ``grouped`` next to the unchanged total-loss selection.

    Ruling 89-2 / 89-3 switches (both off by default, which is the registered recipe bit for bit): ``field_encoding``
    builds the heads with the field-wise encoding whose statistics come from ``train_records`` only;
    ``existence_class_weight`` weights gone rows by present / gone rows of ``train_records`` (validation scored alike).

    白话：按登记的 seed 初始化并洗牌，每帧一个 batch，AdamW；每个 epoch 结束在 validation 上算一次
    平均损失，跑完全部登记的 epoch 后保留 validation 损失最低那个 epoch 的权重（并列取更早的）。
    同样的数据、同样的值、同一设备两次训练权重逐位相同。损失出现非有限值即判发散并如实返回。
    ``epoch_callback(epoch, heads)``（裁决 79-3，只读诊断用，默认不调用）在每个 epoch 的 validation 之后
    被调用一次，此时头处于 eval 模式；它不得改动头或优化器，训练结果与不传时逐位相同。
    ``best_callback(snapshot)``（裁决 104-7 推测执行，默认不调用）在其后被调用，拿到“到目前为止最好的”检查点
    （总损失与分组各自的），用 ``snapshot_weights`` 可以写出此刻若训练结束会返回的权重；它同样只读。
    ``train_heads_streamed`` 是同一训练的流式版本（S3-03），两者逐位相同。
    """

    _check_training_values(learning_rate=learning_rate, weight_decay=weight_decay, epochs=epochs, seed=seed)
    _require(len(train_records) >= 1 and len(validation_records) >= 1, "training_records_missing")
    # every record checked and turned into tensors once, in the order the checks ran before (see ``prepare_frame``)
    train_prepared = [prepare_frame(record, device=device) for record in train_records]
    validation_prepared = [prepare_frame(record, device=device) for record in validation_records]
    encoding = field_encoding_statistics(train_records, heads=_trained_head_names(assoc_only)) if field_encoding else None
    pos_weight, class_counts = (_existence_class_weight(train_prepared, device=device) if existence_class_weight and not assoc_only
                                else (None, None))
    loss_fn = prepared_loss
    if field_encoding:  # the ruling-89 recipe: one forward per head per frame (batch_prepared), same loss
        train_prepared = [batch_prepared(p, device=device) for p in train_prepared]
        validation_prepared = [batch_prepared(p, device=device) for p in validation_prepared]
        loss_fn = batched_loss
    return _train_on_frames(
        train_prepared, validation_prepared, loss_fn=loss_fn, encoding=encoding, pos_weight=pos_weight, class_counts=class_counts,
        learning_rate=learning_rate, weight_decay=weight_decay, epochs=epochs, seed=seed, assoc_only=assoc_only, device=device,
        epoch_callback=epoch_callback, best_callback=best_callback, field_encoding=field_encoding,
        existence_class_weight=existence_class_weight, cosine_min_learning_rate=cosine_min_learning_rate,
        gradient_clip_norm=gradient_clip_norm, existence_prior_correction=existence_prior_correction, group_selection=group_selection,
        optimizer_foreach=optimizer_foreach)


def train_heads_streamed(
    train_records: Callable[[], Iterable[Mapping[str, Any]]], validation_records: Callable[[], Iterable[Mapping[str, Any]]], *,
    learning_rate: float | None, weight_decay: float | None, epochs: int | None, seed: int | None,
    assoc_only: bool, device: str = "cpu", epoch_callback: Any = None,
    field_encoding: bool = False, existence_class_weight: bool = False,
    cosine_min_learning_rate: float | None = None, gradient_clip_norm: float | None = None,
    existence_prior_correction: bool = False, group_selection: bool = False, best_callback: Any = None,
    optimizer_foreach: bool = False,
) -> dict[str, Any]:
    """``train_heads`` on records read one at a time (ruling 104-3; the approved reading "流式准备、留在 CPU", 2026-10-03).

    ``train_records`` and ``validation_records`` are callables that return a fresh iterator over the records each time
    they are called, in the order ``train_heads`` would get them as lists.  With the field-wise encoding the training
    records are read twice: the first pass keeps only the columns the encoding standardises
    (``field_encoding_statistics_streamed``); the second turns each record into its prepared (and batched) tensors and
    drops the record.  Everything after preparation is the same function as ``train_heads``, so the weights, curves and
    per-epoch terms are bit-identical (pinned by test, and on the server by the training equivalence probe, ruling 104-2).

    白话：现行训练先把全部原始记录读进内存（每条记录约 170 KB，S3 第 1 轮每个进程约 85 GB），再转张量。这里逐条读：
    第一遍只取算编码统计要的那几列，第二遍逐条转成张量、原始记录读完即丢，内存只剩张量（约为原来的 3%）。
    训练本身与 ``train_heads`` 是同一段代码，结果逐位相同。它不改配方、不改选点，只改数据怎样进内存。
    """

    _check_training_values(learning_rate=learning_rate, weight_decay=weight_decay, epochs=epochs, seed=seed)
    encoding = (field_encoding_statistics_streamed(train_records(), heads=_trained_head_names(assoc_only)) if field_encoding
                else None)

    def prepared(source: Callable[[], Iterable[Mapping[str, Any]]]) -> list[dict[str, Any]]:
        frames = []
        for record in source():
            frame = prepare_frame(record, device=device)
            frames.append(batch_prepared(frame, device=device) if field_encoding else frame)
        return frames

    train_frames = prepared(train_records)
    validation_frames = prepared(validation_records)
    _require(len(train_frames) >= 1 and len(validation_frames) >= 1, "training_records_missing")
    pos_weight, class_counts = (_existence_class_weight(train_frames, device=device) if existence_class_weight and not assoc_only
                                else (None, None))
    return _train_on_frames(
        train_frames, validation_frames, loss_fn=batched_loss if field_encoding else prepared_loss, encoding=encoding,
        pos_weight=pos_weight, class_counts=class_counts, learning_rate=learning_rate, weight_decay=weight_decay, epochs=epochs,
        seed=seed, assoc_only=assoc_only, device=device, epoch_callback=epoch_callback, best_callback=best_callback,
        field_encoding=field_encoding, existence_class_weight=existence_class_weight, cosine_min_learning_rate=cosine_min_learning_rate,
        gradient_clip_norm=gradient_clip_norm, existence_prior_correction=existence_prior_correction, group_selection=group_selection,
        optimizer_foreach=optimizer_foreach)


def _train_on_frames(
    train_prepared: Sequence[Mapping[str, Any]], validation_prepared: Sequence[Mapping[str, Any]], *, loss_fn: Any,
    encoding: Mapping[str, Any] | None, pos_weight: Any, class_counts: Mapping[str, Any] | None,
    learning_rate: float, weight_decay: float, epochs: int, seed: int, assoc_only: bool, device: str, epoch_callback: Any,
    best_callback: Any, field_encoding: bool, existence_class_weight: bool, cosine_min_learning_rate: float | None,
    gradient_clip_norm: float | None, existence_prior_correction: bool, group_selection: bool, optimizer_foreach: bool = False,
) -> dict[str, Any]:
    """The training loop of ``train_heads`` on frames already prepared (and batched under the field-wise encoding).

    ``optimizer_foreach`` (ruling 104-7, a conditional item): AdamW's multi-tensor path instead of the default single-tensor path
    on CPU.  It does the same arithmetic element by element; it is used only where the weights are shown identical bit for bit --
    a test pins it on the suite's torch, and S3-03's training probe checks it on real records before the run relies on it.
    """

    import torch

    offset = -math.log(float(pos_weight.item())) if existence_prior_correction and pos_weight is not None else None
    heads = make_heads(assoc_only=assoc_only, seed=int(seed), encoding=encoding).to(device)
    if optimizer_foreach:
        optimiser = torch.optim.AdamW(heads.parameters(), lr=float(learning_rate), weight_decay=float(weight_decay), foreach=True)
    else:
        optimiser = torch.optim.AdamW(heads.parameters(), lr=float(learning_rate), weight_decay=float(weight_decay))
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    train_curve: list[float | None] = []
    validation_curve: list[float | None] = []
    best: tuple[float, int, dict[str, Any]] | None = None
    diverged = False
    updates_taken = 0
    train_terms: list[dict[str, float | None]] = []       # per epoch: mean of each term while the epoch updates
    validation_terms: list[dict[str, float | None]] = []  # per epoch: each term at the epoch-end weights
    best_by_group: dict[str, tuple[float, int, dict[str, Any]]] = {}  # ruling 96 (a); stays empty when group_selection is off
    for epoch in range(int(epochs)):
        if cosine_min_learning_rate is not None:  # pending ruling 91 only; None keeps the registered constant rate
            rate = float(cosine_min_learning_rate) + (float(learning_rate) - float(cosine_min_learning_rate)) * (1.0 + math.cos(math.pi * epoch / int(epochs))) / 2.0
            for group in optimiser.param_groups:
                group["lr"] = rate
        heads.train()
        order = torch.randperm(len(train_prepared), generator=generator).tolist()
        total, count = 0.0, 0
        epoch_terms = _TermMeans()
        for index in order:
            out = loss_fn(heads, train_prepared[index], existence_pos_weight=pos_weight)
            if out["loss"] is None:
                continue
            if not torch.isfinite(out["loss"]):
                diverged = True
                break
            optimiser.zero_grad()
            out["loss"].backward()
            if gradient_clip_norm is not None:
                torch.nn.utils.clip_grad_norm_(heads.parameters(), float(gradient_clip_norm))
            optimiser.step()
            total += float(out["loss"].item())
            count += 1
            updates_taken += 1
            epoch_terms.add(out)
        if diverged:
            train_curve.append(None)
            validation_curve.append(None)
            break
        heads.eval()
        train_curve.append(total / count if count else None)
        train_terms.append(epoch_terms.means())
        held_out = _mean_loss_and_terms(heads, validation_prepared, existence_pos_weight=pos_weight, loss_fn=loss_fn)
        validation_terms.append(held_out)
        validation = held_out["total"]
        validation_curve.append(validation)
        if validation is not None and (best is None or validation < best[0]):
            best = (validation, epoch, {name: {k: v.detach().cpu().clone() for k, v in module.state_dict().items()}
                                       for name, module in heads.items()})
        if group_selection:  # bookkeeping only: no parameter, optimiser or generator state is touched
            for group, members, term in GROUP_SELECTION:
                value = held_out.get(term)
                if all(name in heads for name in members) and value is not None and (group not in best_by_group or value < best_by_group[group][0]):
                    best_by_group[group] = (value, epoch, {name: {k: v.detach().cpu().clone() for k, v in heads[name].state_dict().items()}
                                                           for name in members})
        if epoch_callback is not None:
            epoch_callback(epoch, heads)
        if best_callback is not None:  # ruling 104-7: read-only, like epoch_callback
            best_callback({"epoch": epoch, "heads": heads, "best": None if best is None else (best[1], best[2]),
                           "best_by_group": {group: (entry[1], entry[2]) for group, entry in best_by_group.items()},
                           "existence_logit_offset": offset, "group_selection": bool(group_selection)})
    _require(best is not None or diverged, "validation_loss_undefined_on_every_epoch")
    if best is not None:
        with torch.no_grad():
            for name, state in best[2].items():
                heads[name].load_state_dict(state)
    training = {"optimizer": OPTIMIZER, "learning_rate": learning_rate, "weight_decay": weight_decay, "epochs": epochs,
                "seed": seed, "assoc_only": assoc_only, "batch": BATCH_RULE, "early_stopping": EARLY_STOPPING_RULE,
                "initialisation": INITIALISATION_RULE,
                "best_epoch": None if best is None else best[1], "train_frames": len(train_prepared),
                "validation_frames": len(validation_prepared), "device": device, "diverged": diverged}
    if field_encoding or existence_class_weight:
        training.update({"field_encoding": bool(field_encoding), "existence_class_weight": class_counts,
                         "existence_class_weight_rule": EXISTENCE_CLASS_WEIGHT_RULE if existence_class_weight else None,
                         "updates_taken": updates_taken})
    if offset is not None:  # pending ruling 91 only
        heads.existence_logit_offset = offset
    if cosine_min_learning_rate is not None or gradient_clip_norm is not None or existence_prior_correction:
        training.update({"existence_prior_correction": bool(existence_prior_correction),"cosine_min_learning_rate": cosine_min_learning_rate, "gradient_clip_norm": gradient_clip_norm,
                         "schedule_rule": COSINE_SCHEDULE_RULE})
    training["loss_terms_per_epoch"] = {"train_running_mean": train_terms, "validation_at_epoch_end": validation_terms}
    out = {"weights": weights_payload(heads, training=training), "heads": heads, "train_curve": train_curve,
           "validation_curve": validation_curve, "best_epoch": None if best is None else best[1], "diverged": diverged,
           "updates_taken": updates_taken, "train_curve_terms": train_terms, "validation_curve_terms": validation_terms}
    if group_selection and best is not None:
        import copy

        grouped = copy.deepcopy(heads)  # starts as the total-loss selection; a group without any term value keeps it
        epochs_by_group = {group: None for group, members, _ in GROUP_SELECTION if all(name in heads for name in members)}
        with torch.no_grad():
            for group, (_, epoch_index, states) in best_by_group.items():
                for name, state in states.items():
                    grouped[name].load_state_dict(state)
                epochs_by_group[group] = epoch_index
        grouped_training = dict(training, selection_rule=GROUP_SELECTION_RULE, best_epoch_by_group=epochs_by_group)
        out["grouped"] = {"weights": weights_payload(grouped, training=grouped_training), "heads": grouped,
                          "best_epoch_by_group": epochs_by_group}
    return out


def snapshot_weights(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """The weights a training would return if it ended at this epoch end (ruling 104-7, speculation by weights digest).

    ``snapshot`` is what ``best_callback`` receives.  The payloads are built the way ``train_heads`` builds its result -- a
    copy of the heads with the best state loaded and the prior offset set, then, under group selection, a copy with each
    group's best state -- so at the epoch the run finally keeps, their digests equal the final ones (pinned by test); the
    live heads are not touched.  The ``training`` block of a snapshot only names the epochs (no digest covers ``training``).

    白话：推测执行要在训练还没结束时，就知道“如果现在停，会留下哪份权重”。输入是回调拿到的当前最好检查点，输出是同样
    构造的权重文件；训练结束时最终选中的权重若与某次快照相同，两者的摘要逐位相等，下游按摘要认领推测产物。它不改训练。
    """

    import copy

    import torch

    if snapshot["best"] is None:
        return {"weights": None, "grouped": None, "best_epoch": None, "best_epoch_by_group": None}
    best_epoch, best_state = snapshot["best"]
    heads = copy.deepcopy(snapshot["heads"])
    with torch.no_grad():
        for name, state in best_state.items():
            heads[name].load_state_dict(state)
    if snapshot["existence_logit_offset"] is not None:
        heads.existence_logit_offset = snapshot["existence_logit_offset"]
    training = {"snapshot_epoch": snapshot["epoch"], "best_epoch": best_epoch}
    out: dict[str, Any] = {"weights": weights_payload(heads, training=training), "grouped": None, "best_epoch": best_epoch,
                           "best_epoch_by_group": None}
    if snapshot["group_selection"]:
        grouped = copy.deepcopy(heads)
        epochs_by_group = {group: None for group, members, _ in GROUP_SELECTION if all(name in heads for name in members)}
        with torch.no_grad():
            for group, (epoch_index, states) in snapshot["best_by_group"].items():
                for name, state in states.items():
                    grouped[name].load_state_dict(state)
                epochs_by_group[group] = epoch_index
        out["grouped"] = weights_payload(grouped, training=dict(training, best_epoch_by_group=epochs_by_group))
        out["best_epoch_by_group"] = epochs_by_group
    return out


#: D-224-S1 ruling 81-2 (2026-09-28), diagnostics only: the controlled comparison counts training in optimizer updates.
UPDATE_BUDGET_RULE = ("updates are the optimizer steps actually taken (frames without a loss term are skipped and not counted); "
                      "the validation loss is scored every evaluate_every updates and at the last update; the weights of the "
                      "checkpoint with the lowest validation loss are kept (ties to the earlier checkpoint)")


def has_loss_term(prepared: Mapping[str, Any], *, assoc_only: bool) -> bool:
    """Would ``prepared_loss`` take an optimizer step on this prepared frame?"""

    return bool(prepared["association"]) or (prepared["existence"] is not None and not assoc_only)


def updates_per_pass(records: Sequence[Mapping[str, Any]], *, assoc_only: bool, device: str = "cpu") -> int:
    """Optimizer updates one pass over ``records`` takes (the frames that carry a loss term)."""

    return sum(1 for record in records if has_loss_term(prepare_frame(record, device=device), assoc_only=assoc_only))


def train_heads_by_updates(
    train_records: Sequence[Mapping[str, Any]], validation_records: Sequence[Mapping[str, Any]], *,
    learning_rate: float | None, weight_decay: float | None, update_budget: int | None, evaluate_every: int | None,
    seed: int | None, assoc_only: bool, device: str = "cpu", checkpoint_callback: Any = None,
) -> dict[str, Any]:
    """Train for a fixed number of optimizer updates, scoring validation every ``evaluate_every`` updates (ruling 81-2).

    白话：裁决 81-2 的受控对照要让“数据多了”和“训练多了”分得开，所以训练量按真正执行的优化器更新次数计，
    验证按固定的更新间隔打分，而不是按 epoch。输入与 ``train_heads`` 相同，另加更新预算和验证间隔；输出同样是
    最佳检查点的权重、各检查点的验证损失与收敛情况。数据一遍用完就按同一个洗牌生成器再洗一遍，直到预算用完
    （可以停在一遍的中间）。例如只用本臂数据、预算是累积数据 20 遍的步数，就等于把本臂数据多训练约一倍。
    预算设为“20 遍的步数”、间隔设为“一遍的步数”时，它与 ``train_heads`` 逐位相同（有测试）。这只是诊断用的
    训练方式，不是登记的训练配方。
    """

    import torch

    for name, value in (("learning_rate", learning_rate), ("weight_decay", weight_decay), ("update_budget", update_budget),
                        ("evaluate_every", evaluate_every), ("seed", seed)):
        _require(value is not None, f"training_value_not_frozen:{name}")
    _require(_finite(learning_rate, "learning_rate_invalid") > 0.0, "learning_rate_invalid")
    _require(_finite(weight_decay, "weight_decay_invalid") >= 0.0, "weight_decay_invalid")
    _require(type(update_budget) is int and update_budget >= 1, "update_budget_invalid")
    _require(type(evaluate_every) is int and evaluate_every >= 1, "evaluate_every_invalid")
    _require(type(seed) is int and seed >= 0, "seed_invalid")
    _require(len(train_records) >= 1 and len(validation_records) >= 1, "training_records_missing")
    train_prepared = [prepare_frame(record, device=device) for record in train_records]
    validation_prepared = [prepare_frame(record, device=device) for record in validation_records]
    _require(any(has_loss_term(p, assoc_only=assoc_only) for p in train_prepared), "training_records_without_a_loss_term")

    heads = make_heads(assoc_only=assoc_only, seed=int(seed)).to(device)
    optimiser = torch.optim.AdamW(heads.parameters(), lr=float(learning_rate), weight_decay=float(weight_decay))
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    checkpoints: list[dict[str, Any]] = []
    best: tuple[float, int, dict[str, Any]] | None = None
    diverged = False
    updates = 0
    passes = 0
    window_total, window_count = 0.0, 0
    while updates < update_budget and not diverged:
        heads.train()
        order = torch.randperm(len(train_records), generator=generator).tolist()
        passes += 1
        for index in order:
            out = prepared_loss(heads, train_prepared[index])
            if out["loss"] is None:
                continue
            if not torch.isfinite(out["loss"]):
                diverged = True
                break
            optimiser.zero_grad()
            out["loss"].backward()
            optimiser.step()
            updates += 1
            window_total += float(out["loss"].item())
            window_count += 1
            if updates % evaluate_every == 0 or updates == update_budget:
                heads.eval()
                validation = _mean_loss(heads, validation_prepared)
                checkpoints.append({"updates": updates, "pass": passes, "train_mean_since_last_checkpoint": window_total / window_count,
                                    "validation": validation})
                window_total, window_count = 0.0, 0
                if validation is not None and (best is None or validation < best[0]):
                    best = (validation, updates, {name: {k: v.detach().cpu().clone() for k, v in module.state_dict().items()}
                                                  for name, module in heads.items()})
                if checkpoint_callback is not None:
                    checkpoint_callback(updates, heads)
                heads.train()
            if updates >= update_budget:
                break
    _require(best is not None or diverged, "validation_loss_undefined_on_every_checkpoint")
    if best is not None:
        with torch.no_grad():
            for name, state in best[2].items():
                heads[name].load_state_dict(state)
    training = {"optimizer": OPTIMIZER, "learning_rate": learning_rate, "weight_decay": weight_decay, "update_budget": update_budget,
                "evaluate_every": evaluate_every, "updates_taken": updates, "passes_started": passes, "seed": seed, "assoc_only": assoc_only,
                "batch": BATCH_RULE, "early_stopping": UPDATE_BUDGET_RULE, "initialisation": INITIALISATION_RULE,
                "best_update": None if best is None else best[1], "train_frames": len(train_records),
                "validation_frames": len(validation_records), "device": device, "diverged": diverged}
    return {"weights": weights_payload(heads, training=training), "heads": heads, "checkpoints": checkpoints,
            "best_update": None if best is None else best[1], "updates_taken": updates, "diverged": diverged}


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
    "EXISTENCE_CLASS_WEIGHT_RULE",
    "FIELD_ENCODING",
    "GROUP_SELECTION",
    "GROUP_SELECTION_RULE",
    "WEIGHTS_SCHEMA_VERSION_FIELD_WISE",
    "field_encoding_statistics",
    "field_encoding_statistics_streamed",
    "batch_prepared",
    "batched_loss",
    "INITIALISATION_RULE",
    "UPDATE_BUDGET_RULE",
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
    "prepare_frame",
    "prepared_loss",
    "is_assoc_only",
    "load_heads",
    "has_loss_term",
    "head_seed",
    "make_heads",
    "parameter_count",
    "recipe_matches_contract",
    "snapshot_weights",
    "train_heads",
    "train_heads_by_updates",
    "train_heads_streamed",
    "updates_per_pass",
    "validate_training_record",
    "weights_payload",
]
