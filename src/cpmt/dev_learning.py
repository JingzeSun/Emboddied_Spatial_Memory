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
                                 dtype=torch.long if key in ("y", "group")
                                 else torch.bool if key in (
                                     "labelled", "ambiguous", "recovery",
                                     "calibration", "candidate_legal",
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
            mask = train["relation_mask"][batch]
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
            teachers[name] = torch.softmax(-energy / config["temperature"], dim=1).detach()
    return model, teachers, trace


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
    trace = []
    for step in range(config["student_steps"]):
        batch = torch.randint(len(train["x"]), (config["batch_size"],), device=device)
        x = train["x"][batch]
        logits = model(x)
        has_label = train["labelled"][batch]
        supervised = (F.cross_entropy(logits[has_label], train["y"][batch][has_label])
                      if has_label.any() else logits.sum() * 0)
        loss = supervised
        auxiliary = logits.sum() * 0
        if method in ("cpmt_ctl_core", "execute_current_only", "future_no_execution"):
            auxiliary = F.kl_div(F.log_softmax(logits, dim=-1), teacher[batch],
                                 reduction="batchmean")
            loss = loss + config["distillation_weight"] * auxiliary
        elif method == "direct_future_loss":
            if "relation_targets" in train:
                prediction = model.structured_relation_prediction(
                    x, train["poses"][batch])
                mask = train["relation_mask"][batch]
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
        uniform_expected_accuracy=1 / probs.shape[1],
    )
    details = [dict(index=i, group=int(data["group"][i].cpu()), target=int(targets[i]),
                    predicted=int(predicted[i]), posterior=probs[i].tolist(),
                    teacher_posterior=teacher[i].cpu().tolist(),
                    indistinguishable=bool(ambiguous[i]), decision=decisions[i],
                    toy_location_fact_error=float(facts[i]), toy_excess_nodes=float(growth[i]))
               for i in range(len(probs))]
    return metrics, details


def evaluate(model: nn.Module, data: dict, config: dict,
             teacher: torch.Tensor) -> tuple[dict, list[dict]]:
    with torch.no_grad():
        probs = model(data["x"]).softmax(-1).cpu().numpy()
    return evaluate_probabilities(probs, data, config, teacher)


def oracle_probabilities(data: dict) -> np.ndarray:
    """Return the in-budget oracle choice; this is an upper bound, not a model."""
    targets = data["y"].detach().cpu().numpy()
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
