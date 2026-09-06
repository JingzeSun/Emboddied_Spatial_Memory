"""Train small online networks and development baselines on fixed spatial data.

No function named model.forward takes labels, future images, or simulator truth.
Future observations are confined to auxiliary losses and hindsight teachers.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .pending import decide_commit

METHODS = (
    "cpmt_ctl_core",
    "direct_classifier",
    "direct_future_loss",
    "execute_current_only",
    "future_no_execution",
    "oracle_candidate_program",
)


def candidate_admissibility_mask(
    data: dict[str, torch.Tensor], candidate_values: torch.Tensor,
) -> torch.Tensor:
    """Return the shared online static-preflight mask for candidate values.

    Older synthetic development fixtures predate transaction preflight and use
    an all-true mask.  M1-v2 arrays always carry the explicit mask.
    """
    mask = data.get("candidate_static_preflight_pass")
    if mask is None:
        mask = torch.ones_like(candidate_values, dtype=torch.bool)
    else:
        mask = mask.to(device=candidate_values.device, dtype=torch.bool)
    if mask.shape != candidate_values.shape:
        raise ValueError("candidate admissibility mask has the wrong shape")
    if torch.any(~mask.any(dim=-1)):
        raise ValueError("static preflight rejected every candidate in a row")
    return mask


def masked_candidate_logits(
    logits: torch.Tensor, static_preflight_pass: torch.Tensor,
) -> torch.Tensor:
    """Make statically rejected candidates unavailable without reindexing K."""
    mask = static_preflight_pass.to(device=logits.device, dtype=torch.bool)
    if logits.shape != mask.shape:
        raise ValueError("candidate logits and admissibility mask differ")
    if torch.any(~mask.any(dim=-1)):
        raise ValueError("static preflight rejected every candidate in a row")
    return logits.masked_fill(~mask, -torch.inf)


def masked_candidate_probabilities(
    logits: torch.Tensor, static_preflight_pass: torch.Tensor,
) -> torch.Tensor:
    """Softmax only over candidates admitted by the shared online preflight."""
    return torch.softmax(
        masked_candidate_logits(logits, static_preflight_pass), dim=-1,
    )


def apply_candidate_admissibility_to_probabilities(
    probabilities: torch.Tensor, static_preflight_pass: torch.Tensor,
) -> torch.Tensor:
    """Apply and renormalize the shared mask to an existing distribution."""
    mask = static_preflight_pass.to(
        device=probabilities.device, dtype=torch.bool,
    )
    if probabilities.shape != mask.shape:
        raise ValueError("candidate probabilities and admissibility mask differ")
    if torch.any(~mask.any(dim=-1)):
        raise ValueError("static preflight rejected every candidate in a row")
    masked = probabilities * mask.to(probabilities.dtype)
    denominator = masked.sum(dim=-1, keepdim=True)
    if torch.any(denominator <= 0):
        raise ValueError("admissibility mask removed all probability mass")
    return masked / denominator


def split_online_features(
    online_features: torch.Tensor, num_candidates: int, candidate_dim: int,
) -> tuple[torch.Tensor, torch.Tensor | None]:
    """Split the shared online vector into world context and candidate descriptors.

    A zero candidate_dim keeps the legacy layout in which the whole vector is
    context and the head predicts a slot index.
    """
    if candidate_dim <= 0:
        return online_features, None
    context_dim = online_features.shape[-1] - num_candidates * candidate_dim
    if context_dim <= 0:
        raise ValueError("online vector is too short for the declared candidate block")
    context = online_features[..., :context_dim]
    blocks = online_features[..., context_dim:].reshape(
        *online_features.shape[:-1], num_candidates, candidate_dim
    )
    return context, blocks


class OnlineModel(nn.Module):
    """Score candidates from shared online input.

    With a candidate block the head is a shared per-candidate scorer, so it is
    permutation-equivariant and a slot index carries no learnable meaning.  The
    candidate list is randomly permuted per decision, so an index-addressed head
    can only memorize training worlds.
    """
    def __init__(
        self, input_dim: int, hidden: int, future_dim: int, horizon: int,
        num_candidates: int = 3, candidate_dim: int = 0,
        relation_dim: int = 0,
    ):
        super().__init__()
        self.num_candidates = int(num_candidates)
        self.candidate_dim = int(candidate_dim)
        self.relation_dim = int(relation_dim)
        self.context_dim = (
            input_dim - self.num_candidates * self.candidate_dim
            if self.candidate_dim else input_dim
        )
        if self.context_dim <= 0:
            raise ValueError("online vector is too short for the declared candidate block")
        self.encoder = nn.Sequential(nn.Linear(self.context_dim, hidden), nn.ReLU(),
                                     nn.Linear(hidden, hidden), nn.ReLU())
        if self.candidate_dim:
            self.candidate_scorer = nn.Sequential(
                nn.Linear(hidden + self.candidate_dim, hidden), nn.ReLU(),
                nn.Linear(hidden, 1))
        else:
            self.classifier = nn.Linear(hidden, num_candidates)
        # Same head is allocated in every method; only C uses its gradients.
        self.future_head = nn.Sequential(nn.Linear(hidden + horizon, hidden),
                                         nn.ReLU(), nn.Linear(hidden, future_dim))
        if self.relation_dim:
            descriptor_dim = self.candidate_dim or self.num_candidates
            self.relation_head = nn.Sequential(
                nn.Linear(hidden + descriptor_dim + horizon, hidden), nn.ReLU(),
                nn.Linear(hidden, self.relation_dim),
            )

    def forward(self, online_features: torch.Tensor) -> torch.Tensor:
        context, blocks = split_online_features(
            online_features, self.num_candidates, self.candidate_dim)
        encoded = self.encoder(context)
        if blocks is None:
            return self.classifier(encoded)
        expanded = encoded.unsqueeze(-2).expand(
            *blocks.shape[:-1], encoded.shape[-1])
        return self.candidate_scorer(
            torch.cat((expanded, blocks), dim=-1)).squeeze(-1)

    def auxiliary_prediction(self, online_features: torch.Tensor,
                             actual_future_poses: torch.Tensor) -> torch.Tensor:
        context, _ = split_online_features(
            online_features, self.num_candidates, self.candidate_dim)
        return self.future_head(torch.cat(
            (self.encoder(context), actual_future_poses), dim=-1))

    def structured_relation_prediction(
        self, online_features: torch.Tensor, actual_future_poses: torch.Tensor,
    ) -> torch.Tensor:
        """Predict every candidate-scoped future relation without execution."""
        if not self.relation_dim:
            raise ValueError("structured relation head is not configured")
        context, blocks = split_online_features(
            online_features, self.num_candidates, self.candidate_dim)
        encoded = self.encoder(context)
        if blocks is None:
            blocks = torch.eye(
                self.num_candidates, device=online_features.device,
            ).expand(len(online_features), -1, -1)
        expanded = encoded.unsqueeze(1).expand(-1, self.num_candidates, -1)
        poses = actual_future_poses.unsqueeze(1).expand(
            -1, self.num_candidates, -1)
        return self.relation_head(torch.cat((expanded, blocks, poses), dim=-1))


class OutcomeScorer(nn.Module):
    """Predict future features from pre-edit input and candidate descriptor.

    Its inputs never include post-world arrays or executable graph branches.
    """
    def __init__(
        self, input_dim: int, hidden: int, future_dim: int, horizon: int,
        num_candidates: int = 3, candidate_dim: int = 0, dropout: float = 0.0,
    ):
        super().__init__()
        self.num_candidates = int(num_candidates)
        self.candidate_dim = int(candidate_dim)
        self.context_dim = (
            input_dim - self.num_candidates * self.candidate_dim
            if self.candidate_dim else input_dim
        )
        # A one-hot slot descriptor makes the scorer index-addressed, so its
        # teacher cannot transfer to a world with a different permutation.
        descriptor_dim = self.candidate_dim or self.num_candidates
        # Dropout and weight decay are available so this baseline can be given
        # a fair chance; without them the scorer memorises its few labelled
        # decisions and its teacher does not transfer to held-out worlds.
        layers: list[nn.Module] = [
            nn.Linear(self.context_dim + descriptor_dim + horizon, hidden), nn.ReLU()]
        if dropout > 0.0:
            layers.append(nn.Dropout(float(dropout)))
        layers.extend([nn.Linear(hidden, hidden), nn.ReLU()])
        if dropout > 0.0:
            layers.append(nn.Dropout(float(dropout)))
        layers.append(nn.Linear(hidden, future_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor, descriptor: torch.Tensor,
                poses: torch.Tensor) -> torch.Tensor:
        context, _ = split_online_features(
            x, self.num_candidates, self.candidate_dim)
        return self.net(torch.cat((context, descriptor, poses), dim=-1))


def tensors(data: dict, device: torch.device) -> dict[str, torch.Tensor]:
    return {key: torch.as_tensor(value, device=device,
                                 dtype=torch.long if key in (
                                     "y", "group",
                                     "candidate_execution_failure_code",
                                     "candidate_static_preflight_failure_code",
                                 )
                                 else torch.bool if key in (
                                     "labelled", "ambiguous", "recovery",
                                     "calibration", "candidate_legal",
                                     "candidate_static_preflight_pass",
                                 )
                                 else torch.float32)
            for key, value in data.items()}


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def train_outcome_scorer(train: dict, validation: dict, config: dict, seed: int,
                         device: torch.device) -> tuple[nn.Module, dict, list[dict]]:
    torch.manual_seed(seed + 10000)
    num_candidates = int(train["penalties"].shape[1])
    if int(validation["penalties"].shape[1]) != num_candidates:
        raise ValueError("train/validation candidate dimensions differ")
    candidate_dim = int(config.get("candidate_feature_dim", 0))
    structured = all(
        key in train and key in validation
        for key in ("relation_targets", "relation_mask", "relation_desired")
    )
    scorer_penalty_key = (
        "no_execution_penalties" if structured else "penalties"
    )
    if scorer_penalty_key not in train or scorer_penalty_key not in validation:
        raise ValueError("no-execution scorer penalty inputs are missing")
    output_dim = (
        int(train["relation_targets"].shape[-1])
        if structured else int(train["future"].shape[1])
    )
    model = OutcomeScorer(train["x"].shape[1],
                          int(config.get("scorer_hidden_dim", config["hidden_dim"])),
                          output_dim, config["horizon"],
                          num_candidates=num_candidates,
                          candidate_dim=candidate_dim,
                          dropout=float(config.get("scorer_dropout", 0.0))).to(device)

    def descriptors_for(data: dict, index: torch.Tensor | None,
                        candidate: torch.Tensor) -> torch.Tensor:
        """Describe a candidate by its own features, never by its slot index."""
        rows = data["x"] if index is None else data["x"][index]
        _, blocks = split_online_features(rows, num_candidates, candidate_dim)
        if blocks is None:
            return F.one_hot(candidate, num_candidates).float()
        return blocks[torch.arange(len(rows), device=rows.device), candidate]

    optimizer = torch.optim.Adam(
        model.parameters(), lr=config["learning_rate"],
        weight_decay=float(config.get("scorer_weight_decay", 0.0)))
    supervised_rows = (
        torch.arange(len(train["x"]), device=device)
        if structured else train["labelled"].nonzero().flatten()
    )
    if len(supervised_rows) == 0:
        raise ValueError("no labelled factual examples for no-execution scorer")
    trace = []
    for step in range(config["scorer_steps"]):
        batch = supervised_rows[torch.randint(
            len(supervised_rows), (config["batch_size"],), device=device,
        )]
        if structured:
            rows = train["x"][batch]
            _, blocks = split_online_features(rows, num_candidates, candidate_dim)
            if blocks is None:
                blocks = torch.eye(num_candidates, device=device).expand(
                    len(rows), -1, -1)
            flat_rows = rows.unsqueeze(1).expand(
                -1, num_candidates, -1).reshape(-1, rows.shape[-1])
            flat_blocks = blocks.reshape(-1, blocks.shape[-1])
            flat_poses = train["poses"][batch].unsqueeze(1).expand(
                -1, num_candidates, -1).reshape(-1, train["poses"].shape[-1])
            pred = model(flat_rows, flat_blocks, flat_poses).reshape(
                len(rows), num_candidates, output_dim)
            elementwise = F.binary_cross_entropy_with_logits(
                pred, train["relation_targets"][batch], reduction="none",
            )
            candidate_mask = candidate_admissibility_mask(
                train, train["penalties"],
            )[batch]
            mask = (
                train["relation_mask"][batch]
                * candidate_mask.unsqueeze(-1).to(
                    train["relation_mask"].dtype,
                )
            )
            loss = (elementwise * mask).sum() / mask.sum().clamp_min(1.0)
        else:
            pred = model(
                train["x"][batch],
                descriptors_for(train, batch, train["y"][batch]),
                train["poses"][batch],
            )
            loss = F.mse_loss(pred, train["future"][batch])
        if not torch.isfinite(loss):
            raise FloatingPointError("no-execution scorer loss is non-finite")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 0 or (step + 1) % 50 == 0:
            trace.append({
                "step": step + 1,
                "future_relation_bce" if structured else "future_mse":
                    float(loss.detach().cpu()),
            })
    # The shared energy weights are calibrated for a future term measured in
    # differing structural tokens.  This scorer reports a mean squared error
    # over hashed features, which is about three orders of magnitude smaller, so
    # without rescaling the penalty term decides the argmax and this method
    # silently becomes execute_current_only.
    normalize = bool(config.get("standardize_future_term", False))
    model.eval()  # also disables dropout while the teacher is produced
    teachers = {}
    with torch.no_grad():
        for name, data in (("train", train), ("validation", validation)):
            errors = []
            for candidate in range(num_candidates):
                column = torch.full(
                    (len(data["x"]),), candidate, dtype=torch.long, device=device,
                )
                prediction = model(
                    data["x"], descriptors_for(data, None, column), data["poses"],
                )
                if structured:
                    mask = data["relation_mask"][:, candidate]
                    desired = data["relation_desired"][:, candidate]
                    error = F.binary_cross_entropy_with_logits(
                        prediction, desired, reduction="none",
                    )
                    errors.append(
                        (error * mask).sum(-1) / mask.sum(-1).clamp_min(1.0)
                    )
                else:
                    errors.append(((prediction - data["future"]) ** 2).mean(-1))
            future_error = torch.stack(errors, dim=1)
            if normalize:
                centre = future_error.mean(dim=1, keepdim=True)
                spread = future_error.std(dim=1, keepdim=True)
                future_error = torch.where(
                    spread > 0, (future_error - centre) / spread,
                    torch.zeros_like(future_error),
                )
            energy = (config["energy_weights"]["future"] * future_error
                      + data[scorer_penalty_key])
            admissible = candidate_admissibility_mask(data, energy)
            energy = energy.masked_fill(~admissible, torch.inf)
            teachers[name] = torch.softmax(-energy / config["temperature"], dim=1).detach()
    return model, teachers, trace


def outcome_scorer_diagnostics(
    model: OutcomeScorer, data: dict, teacher: torch.Tensor, *,
    row_mask: np.ndarray | torch.Tensor | None = None,
) -> dict:
    """Separate relation fitting from downstream candidate ranking.

    Masked BCE is the scorer's actual supervised objective against future
    relation truth. Teacher accuracy is the candidate choice after the
    unchanged E energy assembly. Comparing train and held-out subsets therefore
    distinguishes optimization failure from generalization or assembly failure
    without changing what E sees or selects.
    """
    required = ("relation_targets", "relation_mask", "relation_desired", "y")
    if any(key not in data for key in required):
        raise ValueError("structured scorer diagnostics require relation targets")
    device = data["x"].device
    if row_mask is None:
        selected = torch.arange(len(data["x"]), device=device)
    else:
        mask = torch.as_tensor(row_mask, dtype=torch.bool, device=device)
        if mask.ndim != 1 or len(mask) != len(data["x"]):
            raise ValueError("scorer diagnostic row mask has the wrong shape")
        selected = mask.nonzero().flatten()
    if len(selected) == 0:
        raise ValueError("scorer diagnostic subset is empty")

    rows = data["x"][selected]
    poses = data["poses"][selected]
    _, blocks = split_online_features(
        rows, model.num_candidates, model.candidate_dim,
    )
    if blocks is None:
        blocks = torch.eye(model.num_candidates, device=device).expand(
            len(rows), -1, -1,
        )
    flat_rows = rows.unsqueeze(1).expand(
        -1, model.num_candidates, -1,
    ).reshape(-1, rows.shape[-1])
    flat_blocks = blocks.reshape(-1, blocks.shape[-1])
    flat_poses = poses.unsqueeze(1).expand(
        -1, model.num_candidates, -1,
    ).reshape(-1, poses.shape[-1])
    with torch.no_grad():
        logits = model(flat_rows, flat_blocks, flat_poses).reshape(
            len(rows), model.num_candidates, -1,
        )
        targets = data["relation_targets"][selected]
        relation_mask = data["relation_mask"][selected]
        candidate_mask = candidate_admissibility_mask(
            data, data["penalties"],
        )[selected]
        active_relation_mask = (
            relation_mask.bool() & candidate_mask.unsqueeze(-1)
        )
        elementwise = F.binary_cross_entropy_with_logits(
            logits, targets, reduction="none",
        )
        supervised_elements = active_relation_mask.sum()
        if supervised_elements <= 0:
            raise ValueError(
                "scorer diagnostic subset has no supervised relations"
            )
        masked_bce = (
            elementwise * active_relation_mask
        ).sum() / supervised_elements
        binary_correct = (
            (logits.sigmoid() >= 0.5) == (targets >= 0.5)
        ).float()
        masked_binary_accuracy = (
            binary_correct * active_relation_mask
        ).sum() / supervised_elements

        # Two decompositions test the concrete hypothesis that easy relation
        # elements can improve aggregate BCE while candidate ranking worsens.
        # A target-discriminative coordinate contains both future truth values
        # across admitted candidates.  A ranking-relevant coordinate makes a
        # different oracle mismatch contribution for at least two candidates.
        target_positive = (
            (targets >= 0.5) & active_relation_mask
        ).any(dim=1)
        target_negative = (
            (targets < 0.5) & active_relation_mask
        ).any(dim=1)
        coordinate_has_two = active_relation_mask.sum(dim=1) >= 2
        target_discriminative_coordinate = (
            coordinate_has_two & target_positive & target_negative
        )
        desired = data["relation_desired"][selected]
        oracle_contribution = torch.abs(targets - desired)
        contribution_min = oracle_contribution.masked_fill(
            ~active_relation_mask, torch.inf,
        ).min(dim=1).values
        contribution_max = oracle_contribution.masked_fill(
            ~active_relation_mask, -torch.inf,
        ).max(dim=1).values
        ranking_relevant_coordinate = (
            coordinate_has_two
            & ((contribution_max - contribution_min) > 1e-6)
        )

        def loss_slice(coordinate_mask: torch.Tensor) -> tuple[int, float | None]:
            elements = (
                active_relation_mask & coordinate_mask.unsqueeze(1)
            )
            count = int(elements.sum().cpu())
            if count == 0:
                return 0, None
            value = (elementwise * elements).sum() / elements.sum()
            return count, float(value.cpu())

        target_disc_count, target_disc_bce = loss_slice(
            target_discriminative_coordinate,
        )
        target_nondisc_count, target_nondisc_bce = loss_slice(
            ~target_discriminative_coordinate,
        )
        ranking_count, ranking_bce = loss_slice(ranking_relevant_coordinate)
        nonranking_count, nonranking_bce = loss_slice(
            ~ranking_relevant_coordinate,
        )
        predicted = teacher[selected].argmax(dim=1)
        reference = data["y"][selected]
        static_rejected_selection_rate = (
            ~candidate_mask[
                torch.arange(len(selected), device=device), predicted
            ]
        ).float().mean()
        teacher_accuracy = (predicted == reference).float().mean()
        reference_probability = teacher[selected][
            torch.arange(len(selected), device=device), reference
        ]
        wrong_probability = teacher[selected].clone()
        wrong_probability[
            torch.arange(len(selected), device=device), reference
        ] = -torch.inf
        best_wrong_probability = wrong_probability.max(dim=1).values
        probability_margin = reference_probability - best_wrong_probability
        log_probability_margin = (
            torch.log(reference_probability.clamp_min(1e-12))
            - torch.log(best_wrong_probability.clamp_min(1e-12))
        )
        illegal_rate = None
        if "candidate_legal" in data:
            legal = data["candidate_legal"][selected]
            illegal_rate = (~legal[
                torch.arange(len(selected), device=device), predicted
            ]).float().mean()
    return {
        "rows": int(len(selected)),
        "supervised_relation_elements": int(supervised_elements.cpu()),
        "static_preflight_excluded_relation_elements": int((
            relation_mask.bool() & ~candidate_mask.unsqueeze(-1)
        ).sum().cpu()),
        "masked_bce": float(masked_bce.cpu()),
        "masked_binary_accuracy": float(masked_binary_accuracy.cpu()),
        "target_discriminative_relation_elements": target_disc_count,
        "target_discriminative_bce": target_disc_bce,
        "target_nondiscriminative_relation_elements": target_nondisc_count,
        "target_nondiscriminative_bce": target_nondisc_bce,
        "ranking_relevant_relation_elements": ranking_count,
        "ranking_relevant_bce": ranking_bce,
        "ranking_irrelevant_relation_elements": nonranking_count,
        "ranking_irrelevant_bce": nonranking_bce,
        "teacher_accuracy": float(teacher_accuracy.cpu()),
        "mean_effective_candidate_count": float(
            candidate_mask.sum(dim=1).float().mean().cpu()
        ),
        "raw_static_rejected_selection_rate": float(
            static_rejected_selection_rate.cpu()
        ),
        "reference_probability_margin_mean": float(
            probability_margin.mean().cpu()
        ),
        "reference_probability_margin_median": float(
            probability_margin.median().cpu()
        ),
        "reference_log_probability_margin_mean": float(
            log_probability_margin.mean().cpu()
        ),
        "reference_positive_margin_rate": float(
            (probability_margin > 0).float().mean().cpu()
        ),
        "raw_illegal_selection_rate": (
            float(illegal_rate.cpu()) if illegal_rate is not None else None
        ),
    }


def train_student(method: str, train: dict, teacher: torch.Tensor,
                  config: dict, seed: int,
                  device: torch.device) -> tuple[OnlineModel, list[dict]]:
    # Matched architecture, initial weights, batches, optimizer and update count.
    torch.manual_seed(seed)
    num_candidates = int(train["penalties"].shape[1])
    model = OnlineModel(train["x"].shape[1], config["hidden_dim"],
                        train["future"].shape[1], config["horizon"],
                        num_candidates=num_candidates,
                        candidate_dim=int(config.get("candidate_feature_dim", 0)),
                        relation_dim=(
                            int(train["relation_targets"].shape[-1])
                            if "relation_targets" in train else 0
                        ),
                        ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    full_candidate_mask = candidate_admissibility_mask(
        train, train["penalties"],
    )
    teacher = apply_candidate_admissibility_to_probabilities(
        teacher, full_candidate_mask,
    )
    references = train["y"]
    if torch.any(~full_candidate_mask[
        torch.arange(len(references), device=device), references
    ]):
        raise ValueError("a reference transaction failed static preflight")
    trace = []
    for step in range(config["student_steps"]):
        batch = torch.randint(len(train["x"]), (config["batch_size"],), device=device)
        x = train["x"][batch]
        candidate_mask = full_candidate_mask[batch]
        raw_logits = model(x)
        zero = raw_logits.sum() * 0
        logits = masked_candidate_logits(raw_logits, candidate_mask)
        has_label = train["labelled"][batch]
        supervised = (F.cross_entropy(logits[has_label], train["y"][batch][has_label])
                      if has_label.any() else zero)
        loss = supervised
        auxiliary = zero
        if method in ("cpmt_ctl_core", "execute_current_only", "future_no_execution"):
            log_probabilities = F.log_softmax(logits, dim=-1)
            # Avoid the undefined 0 * -inf product on rejected candidates.
            log_probabilities = log_probabilities.masked_fill(
                ~candidate_mask, 0.0,
            )
            auxiliary = F.kl_div(
                log_probabilities, teacher[batch], reduction="batchmean",
            )
            loss = loss + config["distillation_weight"] * auxiliary
        elif method == "direct_future_loss":
            if "relation_targets" in train:
                prediction = model.structured_relation_prediction(
                    x, train["poses"][batch])
                mask = (
                    train["relation_mask"][batch]
                    * candidate_mask.unsqueeze(-1).to(
                        train["relation_mask"].dtype,
                    )
                )
                elementwise = F.binary_cross_entropy_with_logits(
                    prediction, train["relation_targets"][batch], reduction="none",
                )
                auxiliary = (
                    (elementwise * mask).sum() / mask.sum().clamp_min(1.0)
                )
            else:
                auxiliary = F.mse_loss(
                    model.auxiliary_prediction(x, train["poses"][batch]),
                    train["future"][batch])
            loss = loss + config["auxiliary_weight"] * auxiliary
        if not torch.isfinite(loss):
            raise FloatingPointError(f"{method} loss is non-finite")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 0 or (step + 1) % 50 == 0:
            trace.append(dict(step=step + 1, loss=float(loss.detach().cpu()),
                              labelled_ce=float(supervised.detach().cpu()),
                              auxiliary=float(auxiliary.detach().cpu())))
    model.eval()
    return model, trace


def evaluate_probabilities(probs: np.ndarray, data: dict, config: dict,
                           teacher: torch.Tensor) -> tuple[dict, list[dict]]:
    """Evaluate a selected transaction after applying its recorded branch costs.

    Direct baselines do not execute counterfactual branches while learning, but
    their selected transaction is assessed with the same post-world metrics.
    """
    targets = data["y"].cpu().numpy()
    ambiguous = np.asarray(
        data["ambiguous"].cpu().numpy(), dtype=np.bool_,
    )
    identifiable = np.logical_not(ambiguous)
    predicted = probs.argmax(-1)
    teacher_pred = teacher.argmax(-1).cpu().numpy()
    rows = np.arange(len(probs))
    facts = data["fact_errors"].cpu().numpy()[rows, predicted]
    growth = data["excess_nodes"].cpu().numpy()[rows, predicted]
    decisions = [decide_commit(
        {str(k): float(v) for k, v in enumerate(p)}, decision_id=f"eval:{i}",
        at=2, commit_probability=config["commit_probability"],
        margin_threshold=config["margin_threshold"]) for i, p in enumerate(probs)]
    committed = np.asarray(
        [d["action"] == "COMMIT" for d in decisions], dtype=np.bool_,
    )
    quarantined = np.logical_not(committed)
    static_mask_tensor = candidate_admissibility_mask(data, data["penalties"])
    static_mask = static_mask_tensor.detach().cpu().numpy()
    if np.any(probs[~static_mask] > 1e-8):
        raise ValueError(
            "evaluation probabilities include a static-preflight rejection"
        )
    effective_candidate_count = static_mask.sum(axis=1)
    def mean(values: np.ndarray, mask: np.ndarray | None = None):
        selected = values if mask is None else values[mask]
        return float(selected.mean()) if len(selected) else None
    metrics = dict(
        accuracy=mean(predicted == targets),
        identifiable_accuracy=mean(predicted == targets, identifiable),
        indistinguishable_accuracy=mean(predicted == targets, ambiguous),
        indistinguishable_mean_confidence=mean(probs.max(-1), ambiguous),
        indistinguishable_quarantine_rate=mean(quarantined, ambiguous),
        commit_coverage=mean(committed),
        committed_accuracy=mean(predicted == targets, committed),
        nll=float(-np.log(np.maximum(probs[rows, targets], 1e-12)).mean()),
        brier=float(((probs - np.eye(probs.shape[1])[targets]) ** 2).sum(-1).mean()),
        teacher_accuracy=mean(teacher_pred == targets),
        teacher_correct_student_wrong=mean((teacher_pred == targets) & (predicted != targets)),
        toy_location_fact_error=mean(facts),
        toy_excess_node_count=mean(growth),
        committed_toy_location_fact_error=mean(facts, committed),
        uniform_expected_accuracy=float(
            np.mean(1.0 / effective_candidate_count)
        ),
        mean_effective_candidate_count=float(effective_candidate_count.mean()),
    )
    details = [dict(index=i, group=int(data["group"][i].cpu()), target=int(targets[i]),
                    predicted=int(predicted[i]), posterior=probs[i].tolist(),
                    teacher_posterior=teacher[i].cpu().tolist(),
                    static_preflight_pass=static_mask[i].tolist(),
                    indistinguishable=bool(ambiguous[i]), decision=decisions[i],
                    toy_location_fact_error=float(facts[i]), toy_excess_nodes=float(growth[i]))
               for i in range(len(probs))]
    return metrics, details


def evaluate(model: nn.Module, data: dict, config: dict,
             teacher: torch.Tensor) -> tuple[dict, list[dict]]:
    with torch.no_grad():
        logits = model(data["x"])
        probs = masked_candidate_probabilities(
            logits, candidate_admissibility_mask(data, logits),
        ).cpu().numpy()
    teacher = apply_candidate_admissibility_to_probabilities(
        teacher,
        candidate_admissibility_mask(data, data["penalties"]),
    )
    return evaluate_probabilities(probs, data, config, teacher)


def oracle_probabilities(data: dict) -> np.ndarray:
    """Return the in-budget oracle choice; this is an upper bound, not a model."""
    targets = data["y"].detach().cpu().numpy()
    mask = candidate_admissibility_mask(data, data["penalties"])
    if torch.any(~mask[
        torch.arange(len(data["y"]), device=data["y"].device), data["y"]
    ]):
        raise ValueError("oracle reference transaction failed static preflight")
    return np.eye(int(data["penalties"].shape[1]), dtype=np.float32)[targets]


def run_seed(train_np: dict, validation_np: dict, config: dict, seed: int,
             output: Path, device: torch.device) -> tuple[dict, dict]:
    train, validation = tensors(train_np, device), tensors(validation_np, device)
    start = time.perf_counter()
    scorer, learned_teachers, scorer_trace = train_outcome_scorer(
        train, validation, config, seed, device)
    _sync(device)
    scorer_seconds = time.perf_counter() - start
    torch.save(scorer.state_dict(), output / f"scorer_seed{seed}.pt")
    results, records = {}, {}
    for method in METHODS:
        if method == "oracle_candidate_program":
            candidate_count = int(validation["penalties"].shape[1])
            teacher_validation = F.one_hot(
                validation["y"], candidate_count,
            ).float()
            metrics, details = evaluate_probabilities(
                oracle_probabilities(validation), validation, config,
                teacher_validation,
            )
            metrics.update(
                seed=seed,
                initial_accuracy=None,
                student_seconds=0.0,
                scorer_seconds=0.0,
                total_parameters=0,
                additional_scorer_parameters=0,
                peak_allocated_mb=0.0 if device.type == "cuda" else None,
                oracle_upper_bound=True,
                candidate_coverage=1.0,
            )
            metrics["observable_information_accuracy_ceiling"] = (
                1 - 0.5 * float(validation_np["ambiguous"].mean())
            )
            results[method] = metrics
            records[method] = dict(training_trace=[], validation_cases=details)
            print(
                f"seed={seed} method={method} acc={metrics['accuracy']:.3f} "
                "upper_bound=true",
                flush=True,
            )
            continue
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        if method == "future_no_execution":
            teacher_train = learned_teachers["train"]
            teacher_validation = learned_teachers["validation"]
        elif method == "execute_current_only":
            teacher_train = train["pstar_current"]
            teacher_validation = validation["pstar_current"]
        else:
            teacher_train = train["pstar"]
            teacher_validation = validation["pstar"]
        torch.manual_seed(seed)
        candidate_count = int(train["penalties"].shape[1])
        initial = OnlineModel(train["x"].shape[1], config["hidden_dim"],
                              train["future"].shape[1], config["horizon"],
                              num_candidates=candidate_count,
                              candidate_dim=int(config.get("candidate_feature_dim", 0))
                              ).to(device)
        initial_metrics, _ = evaluate(initial, validation, config, teacher_validation)
        del initial
        _sync(device)
        start = time.perf_counter()
        model, trace = train_student(method, train, teacher_train, config, seed, device)
        _sync(device)
        seconds = time.perf_counter() - start
        metrics, details = evaluate(model, validation, config, teacher_validation)
        metrics.update(seed=seed, initial_accuracy=initial_metrics["accuracy"],
                       student_seconds=seconds,
                       scorer_seconds=scorer_seconds if method == "future_no_execution" else 0,
                       total_parameters=sum(p.numel() for p in model.parameters()),
                       additional_scorer_parameters=(sum(p.numel() for p in scorer.parameters())
                                                     if method == "future_no_execution" else 0),
                       peak_allocated_mb=(torch.cuda.max_memory_allocated(device) / 2**20
                                          if device.type == "cuda" else None))
        # This ceiling concerns only deliberately identical BIRTH/RELINK pairs.
        metrics["observable_information_accuracy_ceiling"] = (
            1 - 0.5 * float(validation_np["ambiguous"].mean()))
        results[method] = metrics
        records[method] = dict(training_trace=trace, validation_cases=details)
        torch.save(model.state_dict(), output / f"{method}_seed{seed}.pt")
        print(f"seed={seed} method={method} acc={metrics['accuracy']:.3f} "
              f"identifiable={metrics['identifiable_accuracy']:.3f} "
              f"ambiguous={metrics['indistinguishable_accuracy']:.3f}", flush=True)
    records["outcome_scorer_training"] = scorer_trace
    return results, records
