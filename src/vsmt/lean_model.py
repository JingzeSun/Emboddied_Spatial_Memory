"""D-224 / S2-03: VSMT-lean's learned cost heads -- the only trained part of the method.

Three heads score the S0-03 sealed feature rows: the association head a(f, e) over the 14 frozen
association features, the existence head r(e) over the 17 existence features (12 before ruling 89-2
appended five history summaries), the birth head b(f) over the 4 birth features (METHOD section 7).
Each head is an input encoding followed by two GELU layers of width 128 and a linear read-out to one
logit.  The heads never see a fragment id, an entity id, a slot, a path or a sample name: they read
the feature vectors positionally in the frozen S0-03 order, so the runner can hand the logits back
keyed by the sealed rows, and permuting the candidate rows leaves each row's logit unchanged.  They
read no future frame and no private file.

Two recipes are implemented; the keyword switches of ``train_heads`` / ``train_heads_streamed`` choose
between them.
  * The paper's recipe (ruling 99-1, METHOD section 7), assembled by ``lean_s3_03.training_settings``:
    the field-wise encoding as input layer (count fields take log1p, then every unbounded field is
    standardised with statistics of the training houses; no learnable parameter; ruling 89-2 / 89-3),
    the existence term weighting gone rows by w = present rows / gone rows (ruling 89-2 (a)), a cosine
    learning-rate schedule 1e-3 -> 1e-5 over the 20 epochs and gradient-norm clipping at 1.0 (ruling
    91), existence decisions on sigmoid(logit - ln w) (ruling 91; stored as ``existence_logit_offset``),
    and, in DAgger round 1 of the arms with an existence head, grouped checkpoint selection (ruling 96
    (a)).  54,787 parameters for VSMT-lean's three heads, 35,842 for AssocOnly's two.
  * The recipe registered in S0-05 before ruling 89 (every switch off, the defaults; kept for the runs
    before ruling 89): a row LayerNorm as input layer, an unweighted existence term, a constant
    learning rate and checkpoint selection by the single total loss (54,207 parameters with the
    12-feature existence head of those runs).

What this module provides:
  * ``make_heads`` / ``parameter_count`` / ``weights_payload`` / ``load_heads`` -- the network, its
    exact size, and a digest-carrying weights file with no private byte in it;
  * ``LeanScorer`` -- the scorer interface the S2-01 runner calls (``association_and_birth_logits``
    on stage A, ``existence_logits`` on the eligible stage-B rows), keys exactly the sealed rows;
  * ``frame_loss`` -- the loss: per-fragment softmax cross-entropy over the fragment's recalled
    columns plus its BIRTH column (labels from the S0-04 teacher), plus per-entity existence binary
    cross-entropy, the two terms added; fragments whose label is recall_miss / unlabelled /
    identity_ambiguous / duplicate_of_labelled and candidates whose label is identity_ambiguous
    enter no loss term;
  * ``train_heads`` / ``train_heads_streamed`` -- AdamW, per-frame batches, a registered seed, every
    registered epoch run, and the epoch with the lowest held-out loss kept (early stopping as
    best-epoch selection, no patience value to freeze); the same values on the same device give the
    same weights.  In this module "validation" (``validation_records``, the validation loss, the
    validation terms) means the held-out *training* houses that score checkpoints -- in S3 the last
    60 houses of the train manifest (the 240/60 split of ``lean_s3_03.checkpoint_split``), at the
    development stages the selection houses of ``lean_reid_head.holdout_split`` -- never the
    validation split;
  * the AssocOnly switch (``assoc_only=True``): the same association and birth heads, no existence
    head and no existence loss term, trained from scratch (D-224-X ruling X3); NoVersion is a runner
    switch and uses these heads unchanged.

What it does not do: it does not build features (S0-03), does not solve or compile (S0-03, runner),
does not label (S0-04), does not roll out memories (runner) and does not orchestrate DAgger rounds
(S2-05 / S3-03); it only registers the schedule those steps must follow.
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
#: Ruling 91 (approved 2026-09-30; part of the ruling-99-1 recipe, off by default here): the existence decision reads the
#: head output minus ln w (this rule), and the learning rate of epoch e is lr_min + (lr - lr_min) * (1 + cos(pi * e / epochs)) / 2
#: with each step's gradient norm clipped (``COSINE_SCHEDULE_RULE``).
EXISTENCE_PRIOR_CORRECTION_RULE = ("the existence logit handed to decisions is the head output minus ln(pos_weight): training with pos_weight w "
                                   "moves the optimal logit up by ln w, so without it tau_r 0.5 acts like tau_r 1/(1+w)")
COSINE_SCHEDULE_RULE = "per epoch e of E: lr_e = lr_min + (lr - lr_min) * (1 + cos(pi * e / E)) / 2; gradient norm clipped before each step"
#: Ruling 96 (a) (2026-10-01): the head groups of the per-group checkpoint selection and the held-out term each is kept on.
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
    column (pinned by test against the whole-matrix function, beyond numpy's pairwise-summation block sizes).  The
    list form holds every raw record in memory (about 85 GB in S3 round 1).
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

    Each head is seeded from (seed, head name) (ruling 79-5 (a)), so at one seed the association and birth heads of
    AssocOnly and VSMT-lean start bit-identical and the causal comparison carries no initialisation difference.  With
    ``encoding`` (ruling 89-2 / 89-3) the input layer is the field-wise encoding with those statistics, otherwise a row
    LayerNorm.
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
    heads.existence_logit_offset = 0.0  # ruling 91: set to -ln(pos_weight) by training when the prior correction is on
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
    if offset != 0.0:  # ruling 91 prior correction; inside the digest
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

    The runner hands it the sealed stage-A rows and receives one association logit per (fragment, entity) row and one
    birth logit per fragment; it then hands it the eligible stage-B existence rows and receives one "gone" logit per
    entity, with the heads' ``existence_logit_offset`` (ruling 91) added.  Features are read positionally in the frozen
    order.  It chooses no atom and reads no memory.
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
    under ``field_encoding``; the default path (the recipe before ruling 89) is untouched.
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

    The association term is the mean, over fragments with a target, of the softmax cross-entropy over [recalled
    columns..., BIRTH]; the existence term is the mean binary cross-entropy over the candidates labelled gone or present
    (unweighted here; ``prepared_loss`` takes the class weight); the two are added.  Fragments with an excluded status
    (``ASSOCIATION_EXCLUDED_STATUSES``, e.g. recall_miss: the correct entity is not among the candidates) and
    identity-ambiguous candidates enter no term and are only counted.
    """

    return prepared_loss(heads, prepare_frame(record, device=device))


# --------------------------------------------------------------------------
# 4. training: AdamW, per-frame batches, best epoch by held-out loss (the "validation" records)
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
    """Train the heads once and keep the best held-out epoch; every value explicit, None refused.

    ``validation_records`` are the records of the held-out training houses that score checkpoints (S3: the last 60
    houses of the train manifest, ``lean_s3_03.checkpoint_split``), not the validation split.  The heads are seeded per
    head (``head_seed``) and the frames shuffled by a generator seeded with ``seed``; one AdamW step per frame; every
    registered epoch runs, the mean held-out loss is scored at each epoch end, and the weights of the lowest epoch are
    kept (ties to the earlier epoch).  The same records and values on the same device give bit-identical weights; a
    non-finite loss stops the training, which is returned with ``diverged`` true.

    With every switch at its default this is the training procedure registered in S0-05 before ruling 89 (row
    LayerNorm, unweighted existence term, constant learning rate, total-loss selection), kept for the runs before ruling
    89; on today's feature rows its existence head is 17 wide, so it reproduces the procedure, not the 12-feature heads
    of those runs (``load_heads`` still loads them).  The paper's recipe (ruling 99-1) is what
    ``lean_s3_03.training_settings`` passes: every switch below on, except ``group_selection`` outside round 1 of
    VSMT-lean and HeuristicLabel and ``existence_class_weight`` for AssocOnly:
      * ``field_encoding`` (ruling 89-2 / 89-3): heads with the field-wise encoding whose statistics come from
        ``train_records`` only;
      * ``existence_class_weight`` (ruling 89-2 (a)): gone rows weighted by present / gone rows of ``train_records``
        (held-out records scored alike);
      * ``cosine_min_learning_rate`` and ``gradient_clip_norm`` (ruling 91): the cosine schedule from ``learning_rate``
        down towards this minimum, and the gradient-norm clipping at every step;
      * ``existence_prior_correction`` (ruling 91): the returned heads carry -ln w as ``existence_logit_offset``;
      * ``group_selection`` (ruling 96 (a)): training runs exactly as without it; at every epoch end the run additionally
        remembers, per head group, the weights of the epoch whose own held-out term is lowest (``GROUP_SELECTION``), and
        returns that combination under ``grouped`` next to the unchanged total-loss selection.

    ``epoch_callback(epoch, heads)`` (ruling 79-3, read-only diagnostics, not called by default) runs once per epoch
    after the held-out scoring, with the heads in eval mode; it must not change the heads or the optimiser, and the
    result is bit-identical to a run without it.  ``best_callback(snapshot)`` (ruling 104-7, speculative execution, not
    called by default, read-only as well) runs after it with the best checkpoints so far (total-loss and grouped);
    ``snapshot_weights`` turns a snapshot into the weights the run would return if it ended at that epoch.
    ``train_heads_streamed`` is the streamed form of the same training (S3-03); the two are bit-identical.
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
    optimizer_foreach: bool = False, checkpoint: "EpochCheckpoint | None" = None,
) -> dict[str, Any]:
    """``train_heads`` on records read one at a time (ruling 104-3; the approved reading "流式准备、留在 CPU", 2026-10-03).

    ``train_records`` and ``validation_records`` are callables that return a fresh iterator over the records each time
    they are called, in the order ``train_heads`` would get them as lists.  With the field-wise encoding the training
    records are read twice: the first pass keeps only the columns the encoding standardises
    (``field_encoding_statistics_streamed``); the second turns each record into its prepared (and batched) tensors and
    drops the record.  Everything after preparation is the same function as ``train_heads``, so the weights, curves and
    per-epoch terms are bit-identical (pinned by test, and on the server by the training equivalence probe, ruling 104-2).
    Only the memory footprint changes: the list form holds every raw record (about 170 KB each, about 85 GB per process
    in S3 round 1), the streamed form only the prepared tensors (about 3 % of that); the recipe and the selection are
    unchanged.  ``checkpoint`` (an ``EpochCheckpoint``) lets a stopped training continue at the next epoch.
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
        optimizer_foreach=optimizer_foreach, checkpoint=checkpoint)


class EpochCheckpoint:
    """The whole training state at an epoch end, so that a stopped training continues instead of starting again.

    After every epoch the file holds the current weights, the AdamW state, the shuffling generator and the torch RNG
    state, the loss curves and per-term losses so far, the best weights so far (total-loss and grouped) and the number
    of updates taken.  A process stopped by a shutdown, an upgrade or an out-of-memory kill is rerun with the same
    command: the records are prepared as usual and training continues at the saved next epoch; a resumed run equals an
    uninterrupted one bit for bit (pinned by test, checked again on the server with real records).  ``key`` is a digest
    of every input of the training (arm, round, seed, recipe, input-file digests, thread count, torch version, ...); a
    saved state with another key is refused, never continued from.  Without a checkpoint the training is unchanged.
    """

    FORMAT = 1

    def __init__(self, path: Any, *, key: str) -> None:
        from pathlib import Path

        _require(isinstance(key, str) and len(key) > 0, "checkpoint_key_missing")
        self.path = Path(path)
        self.key = key
        self.resumed_from_epoch: int | None = None  # the epoch the loaded state continues at; None when nothing was loaded

    def load(self) -> dict[str, Any] | None:
        import torch

        if not self.path.exists():
            return None
        state = torch.load(self.path, map_location="cpu", weights_only=True)
        _require(isinstance(state, dict) and state.get("format") == self.FORMAT, "checkpoint_format_unknown")
        _require(state.get("key") == self.key, "checkpoint_key_mismatch")
        self.resumed_from_epoch = int(state["next_epoch"])
        return state

    def save(self, state: Mapping[str, Any]) -> None:
        import os
        import torch

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        torch.save({"format": self.FORMAT, "key": self.key, **state}, temporary)
        os.replace(temporary, self.path)


def _train_on_frames(
    train_prepared: Sequence[Mapping[str, Any]], validation_prepared: Sequence[Mapping[str, Any]], *, loss_fn: Any,
    encoding: Mapping[str, Any] | None, pos_weight: Any, class_counts: Mapping[str, Any] | None,
    learning_rate: float, weight_decay: float, epochs: int, seed: int, assoc_only: bool, device: str, epoch_callback: Any,
    best_callback: Any, field_encoding: bool, existence_class_weight: bool, cosine_min_learning_rate: float | None,
    gradient_clip_norm: float | None, existence_prior_correction: bool, group_selection: bool, optimizer_foreach: bool = False,
    checkpoint: EpochCheckpoint | None = None,
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
    first_epoch = 0
    saved = checkpoint.load() if checkpoint is not None else None
    if saved is not None:  # continue a stopped training: everything the loop carries from one epoch to the next
        with torch.no_grad():
            for name, state in saved["heads"].items():
                heads[name].load_state_dict(state)
        optimiser.load_state_dict(saved["optimiser"])
        generator.set_state(saved["generator"])
        torch.set_rng_state(saved["torch_rng"])
        train_curve, validation_curve = list(saved["train_curve"]), list(saved["validation_curve"])
        train_terms, validation_terms = list(saved["train_terms"]), list(saved["validation_terms"])
        best = None if saved["best"] is None else tuple(saved["best"])
        best_by_group = {group: tuple(entry) for group, entry in saved["best_by_group"].items()}
        updates_taken = int(saved["updates_taken"])
        first_epoch = int(saved["next_epoch"])
    for epoch in range(first_epoch, int(epochs)):
        if cosine_min_learning_rate is not None:  # ruling 91 (ruling-99-1 recipe); None keeps the pre-ruling-89 constant rate
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
        if checkpoint is not None:  # after the callbacks, so a resumed run never repeats an epoch they have seen
            checkpoint.save({"next_epoch": epoch + 1, "heads": {name: module.state_dict() for name, module in heads.items()},
                             "optimiser": optimiser.state_dict(), "generator": generator.get_state(), "torch_rng": torch.get_rng_state(),
                             "train_curve": train_curve, "validation_curve": validation_curve, "train_terms": train_terms,
                             "validation_terms": validation_terms, "best": None if best is None else list(best),
                             "best_by_group": {group: list(entry) for group, entry in best_by_group.items()},
                             "updates_taken": updates_taken})
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
    if offset is not None:  # ruling 91 prior correction (ruling-99-1 recipe)
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
    Downstream steps claim a speculative product by this digest.
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

    Diagnostics only, not a registered recipe.  The controlled comparison of ruling 81-2 separates "more data" from "more
    training", so the budget counts the optimizer updates actually taken and the held-out loss is scored at a fixed
    update interval rather than per epoch.  Inputs are those of ``train_heads`` without its recipe switches (the
    procedure before ruling 89) plus the budget and the interval; outputs are the weights of the best checkpoint, every checkpoint's held-out loss and the divergence
    flag.  When a pass over the data ends the same generator reshuffles it, until the budget is used (possibly mid-pass):
    e.g. one arm's own records with the update count of 20 passes over the pooled records train that data about twice as
    long.  With a budget of 20 passes' updates and an interval of one pass it equals ``train_heads`` bit for bit (tested).
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
    round-0 model's own rollouts; both reported, the main table reads the registered round (D-224, D-224-X ruling X4).
    Under ruling 99-1 round 1 trains on the round-0 records and these, concatenated in full (METHOD section 7)."""

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
