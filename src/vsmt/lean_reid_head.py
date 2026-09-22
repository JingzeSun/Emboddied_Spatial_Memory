"""D-224-E / D-224-S1 ruling 47: the shared ReID adapter head, as a pure core.

A single linear layer from a frozen DINOv2 descriptor (384 or 768 dimensions) to 128 dimensions,
L2-normalised, trained once with a supervised contrastive loss over the diagnostic-labelled
fragments of the 30 training houses of the cached development block, then frozen; every arm
shares the same bytes, so it is not a private advantage of any method.  It is scored (cross-view
separation, ``lean_frontend_diagnostics``) on the 12 selection houses only, and S1-05 keeps it
only if its median separation beats the best frozen descriptor by the ledgered 0.05 margin.

白话：这个模块实现共享 ReID 投影头。输入是冻结描述子与诊断标注（哪个色块属于哪个物体），输出
是一个 128 维单位向量的线性投影。训练目标是"同一物体的色块拉近、不同物体的色块推开"（有监督
对比损失）。它只在前 30 条训练 house 上训练一次、在后 12 条选择 house 上评分；权重文件只有浮点
数，不含任何私有字节。它不做身份判定，不属于任何臂。

The five training values (temperature, epochs, batch size, learning rate, seed) are registered
null in the S1-04 contract and must be frozen by ruling before ``train_head`` is called for real;
the functions here take them as explicit arguments and refuse ``None``.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json
from vsmt.lean_assignment import (
    REID_OUTPUT_DIMENSION, REID_SELECTION_HOUSES, REID_SELECTION_RULE_THRESHOLD, REID_TRAINING_HOUSES,
)
from vsmt.lean_intervention import house_split_rank

WEIGHTS_SCHEMA_VERSION = "vsmt-lean-reid-head-weights-v1"
FROZEN_SETS = ("vits14", "vitb14")


class LeanReIDError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanReIDError(code)


# --------------------------------------------------------------------------
# hold-out (ruling 47)
# --------------------------------------------------------------------------

def holdout_split(house_ids: Sequence[str], *, seed: int) -> dict[str, Any]:
    """The first 30 cached development houses by S0-02 split rank train, the last 12 select.

    白话：把有 cache 的开发 house 按 S0-02 的哈希前缀顺序排好，前 30 条只训练、之后至多 12 条只
    选择。没有 cache 的 house 不在输入里，自然被跳过；不足 12 条就如实记缺口，不顶替。
    """

    ids = sorted(set(house_ids), key=lambda house: (house_split_rank(house, seed=seed), house))
    _require(len(ids) == len(house_ids), "house_ids_duplicated")
    training = ids[:REID_TRAINING_HOUSES]
    selection = ids[REID_TRAINING_HOUSES:REID_TRAINING_HOUSES + REID_SELECTION_HOUSES]
    return {
        "training_houses": training,
        "selection_houses": selection,
        "training_shortfall": REID_TRAINING_HOUSES - len(training),
        "selection_shortfall": REID_SELECTION_HOUSES - len(selection),
        "houses_beyond_the_holdout": ids[REID_TRAINING_HOUSES + REID_SELECTION_HOUSES:],
        "order": "s0_02_house_split_rank",
        "seed": seed,
    }


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def training_set(episodes: Mapping[str, Sequence[Mapping[str, Any]]], *, descriptor_key: str) -> dict[str, Any]:
    """Descriptors and integer classes from the labelled fragments of the given episodes.

    A class is one (episode, object) pair; classes with a single fragment stay as negatives only.
    """

    vectors: list[Sequence[float]] = []
    classes: list[int] = []
    index: dict[tuple[str, str], int] = {}
    for episode_id in sorted(episodes):
        for frame in episodes[episode_id]:
            for fragment in frame["fragments"]:
                key = fragment.get("object")
                if key is None:
                    continue
                label = index.setdefault((episode_id, key), len(index))
                vectors.append(fragment[descriptor_key])
                classes.append(label)
    _require(len(vectors) > 0, "no_labelled_fragments")
    matrix = np.asarray(vectors, dtype=np.float32)
    _require(matrix.ndim == 2, "descriptor_shape_invalid")
    counts = np.bincount(np.asarray(classes), minlength=len(index))
    return {
        "descriptors": matrix,
        "classes": np.asarray(classes, dtype=np.int64),
        "class_count": len(index),
        "classes_with_positives": int((counts >= 2).sum()),
        "fragments": int(matrix.shape[0]),
    }


# --------------------------------------------------------------------------
# model and loss (torch imported lazily so the module imports without it)
# --------------------------------------------------------------------------

def supervised_contrastive_loss(embeddings: Any, classes: Any, *, temperature: float) -> Any:
    """SupCon (Khosla et al. 2020) over one batch of unit embeddings; anchors without a positive are skipped."""

    import torch

    _require(temperature > 0.0, "temperature_invalid")
    z = embeddings
    n = z.shape[0]
    logits = (z @ z.T) / temperature
    eye = torch.eye(n, dtype=torch.bool, device=z.device)
    logits = logits.masked_fill(eye, float("-inf"))
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    same = (classes.unsqueeze(0) == classes.unsqueeze(1)) & ~eye
    positives = same.sum(dim=1)
    anchors = positives > 0
    if not bool(anchors.any()):
        return z.sum() * 0.0
    # select before multiplying: the masked diagonal is -inf and 0 * -inf would be NaN
    summed = torch.where(same, log_prob, torch.zeros_like(log_prob)).sum(dim=1)
    per_anchor = -summed[anchors] / positives[anchors]
    return per_anchor.mean()


def make_head(input_dimension: int, *, output_dimension: int = REID_OUTPUT_DIMENSION) -> Any:
    import torch

    _require(input_dimension > 0 and output_dimension > 0, "dimension_invalid")
    return torch.nn.Linear(input_dimension, output_dimension, bias=True)


def project_with(head: Any, descriptors: np.ndarray) -> np.ndarray:
    import torch

    with torch.no_grad():
        out = head(torch.as_tensor(np.asarray(descriptors, dtype=np.float32), device=head.weight.device))
        return torch.nn.functional.normalize(out, dim=1).cpu().numpy().astype(np.float64)


def train_head(
    descriptors: np.ndarray, classes: np.ndarray, *, output_dimension: int, temperature: float | None,
    epochs: int | None, batch_fragments: int | None, learning_rate: float | None, seed: int | None,
    device: str = "cpu",
) -> dict[str, Any]:
    """Train the projection once; returns the weights payload and the loss curve.

    白话：按登记的种子洗牌、按批做对比学习，每个 epoch 记一次平均损失；损失出现 NaN 或 Inf 即
    判训练发散并如实返回。同一输入与同一五个值在同一设备上两次训练得到逐位相同的权重。
    """

    import torch

    for name, value in (("temperature", temperature), ("epochs", epochs), ("batch_fragments", batch_fragments),
                        ("learning_rate", learning_rate), ("seed", seed)):
        _require(value is not None, "training_value_not_frozen:" + name)
    _require(epochs >= 1 and batch_fragments >= 2 and learning_rate > 0.0 and temperature > 0.0, "training_values_invalid")
    matrix = np.asarray(descriptors, dtype=np.float32)
    labels = np.asarray(classes, dtype=np.int64)
    _require(matrix.ndim == 2 and matrix.shape[0] == labels.shape[0] and matrix.shape[0] >= 2, "training_set_invalid")
    torch.manual_seed(int(seed))
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    head = make_head(int(matrix.shape[1]), output_dimension=output_dimension).to(device)
    optimiser = torch.optim.Adam(head.parameters(), lr=float(learning_rate))
    x = torch.as_tensor(matrix, device=device)
    y = torch.as_tensor(labels, device=device)
    count = int(matrix.shape[0])
    curve: list[float] = []
    diverged = False
    for _ in range(int(epochs)):
        order = torch.randperm(count, generator=generator).to(device)
        total, batches = 0.0, 0
        for start in range(0, count, int(batch_fragments)):
            batch = order[start:start + int(batch_fragments)]
            if batch.shape[0] < 2:
                continue
            z = torch.nn.functional.normalize(head(x[batch]), dim=1)
            loss = supervised_contrastive_loss(z, y[batch], temperature=float(temperature))
            if not torch.isfinite(loss):
                diverged = True
                break
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            total += float(loss.item())
            batches += 1
        curve.append(total / batches if batches else float("nan"))
        if diverged:
            break
    payload = weights_payload(head, input_dimension=int(matrix.shape[1]), output_dimension=output_dimension,
                              training={"temperature": temperature, "epochs": epochs, "batch_fragments": batch_fragments,
                                        "learning_rate": learning_rate, "seed": seed, "fragments": count,
                                        "classes": int(labels.max()) + 1 if count else 0, "device": device})
    return {"weights": payload, "loss_curve": curve, "diverged": diverged, "head": head}


def weights_payload(head: Any, *, input_dimension: int, output_dimension: int, training: Mapping[str, Any]) -> dict[str, Any]:
    """The frozen head as plain floats plus a digest; no private byte can enter this file."""

    weight = head.weight.detach().cpu().numpy().astype(np.float64).tolist()
    bias = head.bias.detach().cpu().numpy().astype(np.float64).tolist()
    body = {"schema_version": WEIGHTS_SCHEMA_VERSION, "input_dimension": input_dimension,
            "output_dimension": output_dimension, "weight": weight, "bias": bias, "training": dict(training)}
    body["sha256"] = hashlib.sha256(canonical_json({k: v for k, v in body.items() if k != "training"}).encode("utf-8")).hexdigest()
    return body


def load_head(payload: Mapping[str, Any], *, device: str = "cpu") -> Any:
    import torch

    _require(payload.get("schema_version") == WEIGHTS_SCHEMA_VERSION, "weights_schema_invalid")
    expected = hashlib.sha256(canonical_json({k: v for k, v in payload.items() if k not in ("training", "sha256")}).encode("utf-8")).hexdigest()
    _require(payload.get("sha256") == expected, "weights_digest_mismatch")
    head = make_head(int(payload["input_dimension"]), output_dimension=int(payload["output_dimension"]))
    with torch.no_grad():
        head.weight.copy_(torch.as_tensor(np.asarray(payload["weight"], dtype=np.float32)))
        head.bias.copy_(torch.as_tensor(np.asarray(payload["bias"], dtype=np.float32)))
    return head.to(device)


def project_frames(frames: Sequence[Mapping[str, Any]], head: Any, *, source_key: str, target_key: str = "reid_projection") -> list[dict[str, Any]]:
    """Copy of the frames with the projection of ``source_key`` added under ``target_key``."""

    out = []
    for frame in frames:
        fragments = list(frame["fragments"])
        if fragments:
            projected = project_with(head, np.asarray([f[source_key] for f in fragments], dtype=np.float32))
        rows = []
        for n, fragment in enumerate(fragments):
            row = dict(fragment)
            row[target_key] = projected[n].tolist()
            rows.append(row)
        out.append({**frame, "fragments": rows})
    return out


# --------------------------------------------------------------------------
# selection (S1-05 rule, ruling 47)
# --------------------------------------------------------------------------

def select_descriptor(median_separation: Mapping[str, float | None], *, threshold: float = REID_SELECTION_RULE_THRESHOLD) -> dict[str, Any]:
    """Which descriptor S1-05 freezes: the projection only if it beats the best frozen set by the margin.

    Keys of ``median_separation``: ``vits14``, ``vitb14`` and any ``reid_projection:<set>`` entries,
    all measured on the selection houses only.  Ties among frozen sets go to the primary (vits14).
    """

    frozen = {name: median_separation.get(name) for name in FROZEN_SETS}
    _require(all(value is not None for value in frozen.values()), "frozen_separation_missing")
    best_frozen = max(FROZEN_SETS, key=lambda name: (frozen[name], name == "vits14"))
    projections = {name: value for name, value in median_separation.items()
                   if name.startswith("reid_projection") and value is not None}
    chosen = best_frozen
    gain = None
    if projections:
        best_projection = max(sorted(projections), key=lambda name: projections[name])
        gain = float(projections[best_projection]) - float(frozen[best_frozen])
        if gain >= threshold:
            chosen = best_projection
    return {
        "chosen": chosen,
        "best_frozen": best_frozen,
        "best_frozen_median_separation": float(frozen[best_frozen]),
        "projection_gain_over_best_frozen": gain,
        "threshold": threshold,
        "frozen_descriptor_baseline_must_be_reported": chosen != best_frozen,
    }


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


__all__ = [
    "FROZEN_SETS",
    "LeanReIDError",
    "WEIGHTS_SCHEMA_VERSION",
    "holdout_split",
    "load_head",
    "make_head",
    "project_frames",
    "project_with",
    "select_descriptor",
    "supervised_contrastive_loss",
    "train_head",
    "training_set",
    "weights_payload",
]
