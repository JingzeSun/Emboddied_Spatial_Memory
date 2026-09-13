"""Torch-system loss and metric bridge for verified R4 learning branches."""

from __future__ import annotations

import math

from .pair_contract import require
from .r4_learning_runtime import torch_targets

SYSTEMS = ("L", "R", "F", "W")


def optimizer(model, learning_rate):
    import torch

    require(learning_rate in (0.0001, 0.0003), "unregistered learning rate")
    parameters = [value for value in model.parameters() if value.requires_grad]
    require(parameters, "model has no trainable parameters")
    return torch.optim.AdamW(parameters, lr=learning_rate, weight_decay=0.01)


def branch_loss(system, model, branch, device="cuda"):
    """Use public query as input and separately tensorized labels as targets."""
    require(system in SYSTEMS, "unknown Torch learning system")
    query = branch["model_input"]
    labels, images = torch_targets(branch, device=device, auxiliary=system in ("F", "W"))
    if system in ("L", "R"):
        from .r4_history_predictor import prepare_query
        history, controls, goal, _ = prepare_query(
            query, retrieval=system == "R", device=device,
        )
        return model.loss(history, controls, goal, labels)
    from .r4_torch_task import tensorize
    history, controls, goal = tensorize(query, device=device)
    return model.loss(history, controls, goal, labels, images)


def prediction(system, model, branch, device="cuda"):
    """Return task logits from one deterministic model without opening targets."""
    require(system in SYSTEMS, "unknown Torch prediction system")
    query = branch["model_input"]
    if system in ("L", "R"):
        from .r4_history_predictor import prepare_query
        history, controls, goal, evidence = prepare_query(
            query, retrieval=system == "R", device=device,
        )
        task = model.imagine(model.observe(history), controls, goal)["task"]
        return task, evidence
    from .r4_torch_task import tensorize
    history, controls, goal = tensorize(query, device=device)
    return model.predict(history, controls, goal)["task"], None


def branch_metrics(task, targets):
    """Compute the three registered branch metrics from logits and detached targets."""
    import torch

    position = torch.as_tensor(targets["object_position_m"], dtype=torch.float32,
                               device=task["object_position_m"].device)[None]
    contact = torch.as_tensor(targets["interval_contact"], dtype=torch.float32,
                              device=task["contact_logit"].device)[None]
    success = float(targets["task_success"])
    predicted_position = task["object_position_m"].detach()
    predicted_contact = task["contact_logit"].detach().sigmoid()
    predicted_success = float(task["success_logit"].detach().sigmoid()[0])
    require(predicted_position.shape == (1, 200, 3)
            and predicted_contact.shape == (1, 200), "task prediction shape")
    values = {
        "position_error_m": float((predicted_position - position).square().sum(-1).sqrt().mean()),
        "contact_brier": float((predicted_contact - contact).square().mean()),
        "success_brier": (predicted_success - success) ** 2,
    }
    require(all(math.isfinite(value) for value in values.values()), "nonfinite branch metric")
    return values


def aggregate_metrics(rows):
    """Equal-weight complete branches; no frame or positive-label reweighting."""
    require(rows and all(set(row) == {"position_error_m", "contact_brier", "success_brier"}
                         for row in rows), "complete branch metrics required")
    return {key: math.fsum(row[key] for row in rows) / len(rows) for key in rows[0]}
