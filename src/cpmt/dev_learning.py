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


class OnlineModel(nn.Module):
    def __init__(
        self, input_dim: int, hidden: int, future_dim: int, horizon: int,
        num_candidates: int = 3,
    ):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, hidden), nn.ReLU(),
                                     nn.Linear(hidden, hidden), nn.ReLU())
        self.classifier = nn.Linear(hidden, num_candidates)
        # Same head is allocated in every method; only C uses its gradients.
        self.future_head = nn.Sequential(nn.Linear(hidden + horizon, hidden),
                                         nn.ReLU(), nn.Linear(hidden, future_dim))

    def forward(self, online_features: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.encoder(online_features))

    def auxiliary_prediction(self, online_features: torch.Tensor,
                             actual_future_poses: torch.Tensor) -> torch.Tensor:
        return self.future_head(torch.cat(
            (self.encoder(online_features), actual_future_poses), dim=-1))


class OutcomeScorer(nn.Module):
    """Predict future features from pre-edit input and candidate descriptor.

    Its inputs never include post-world arrays or executable graph branches.
    """
    def __init__(
        self, input_dim: int, hidden: int, future_dim: int, horizon: int,
        num_candidates: int = 3,
    ):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(input_dim + num_candidates + horizon, hidden),
                                 nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(),
                                 nn.Linear(hidden, future_dim))

    def forward(self, x: torch.Tensor, descriptor: torch.Tensor,
                poses: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat((x, descriptor, poses), dim=-1))


def tensors(data: dict, device: torch.device) -> dict[str, torch.Tensor]:
    return {key: torch.as_tensor(value, device=device,
                                 dtype=torch.long if key in ("y", "group")
                                 else torch.bool if key in ("labelled", "ambiguous")
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
    model = OutcomeScorer(train["x"].shape[1], config["hidden_dim"],
                          train["future"].shape[1], config["horizon"],
                          num_candidates=num_candidates).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    labelled = train["labelled"].nonzero().flatten()
    if len(labelled) == 0:
        raise ValueError("no labelled factual examples for no-execution scorer")
    trace = []
    for step in range(config["scorer_steps"]):
        batch = labelled[torch.randint(len(labelled), (config["batch_size"],), device=device)]
        pred = model(
            train["x"][batch],
            F.one_hot(train["y"][batch], num_candidates).float(),
            train["poses"][batch],
        )
        loss = F.mse_loss(pred, train["future"][batch])
        if not torch.isfinite(loss):
            raise FloatingPointError("no-execution scorer loss is non-finite")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 0 or (step + 1) % 50 == 0:
            trace.append(dict(step=step + 1, future_mse=float(loss.detach().cpu())))
    model.eval()
    teachers = {}
    with torch.no_grad():
        for name, data in (("train", train), ("validation", validation)):
            energies = []
            for candidate in range(num_candidates):
                descriptors = torch.zeros(
                    (len(data["x"]), num_candidates), device=device,
                )
                descriptors[:, candidate] = 1
                prediction = model(data["x"], descriptors, data["poses"])
                future_mse = ((prediction - data["future"]) ** 2).mean(-1)
                energies.append(config["energy_weights"]["future"] * future_mse
                                + data["penalties"][:, candidate])
            energy = torch.stack(energies, dim=1)
            teachers[name] = torch.softmax(-energy / config["temperature"], dim=1).detach()
    return model, teachers, trace


def train_student(method: str, train: dict, teacher: torch.Tensor,
                  config: dict, seed: int, device: torch.device) -> tuple[nn.Module, list[dict]]:
    # Matched architecture, initial weights, batches, optimizer and update count.
    torch.manual_seed(seed)
    num_candidates = int(train["penalties"].shape[1])
    model = OnlineModel(train["x"].shape[1], config["hidden_dim"],
                        train["future"].shape[1], config["horizon"],
                        num_candidates=num_candidates).to(device)
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
            auxiliary = F.mse_loss(model.auxiliary_prediction(x, train["poses"][batch]),
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
    ambiguous = data["ambiguous"].cpu().numpy()
    predicted = probs.argmax(-1)
    teacher_pred = teacher.argmax(-1).cpu().numpy()
    rows = np.arange(len(probs))
    facts = data["fact_errors"].cpu().numpy()[rows, predicted]
    growth = data["excess_nodes"].cpu().numpy()[rows, predicted]
    decisions = [decide_commit(
        {str(k): float(v) for k, v in enumerate(p)}, decision_id=f"eval:{i}",
        at=2, commit_probability=config["commit_probability"],
        margin_threshold=config["margin_threshold"]) for i, p in enumerate(probs)]
    committed = np.asarray([d["action"] == "COMMIT" for d in decisions])
    def mean(values: np.ndarray, mask: np.ndarray | None = None):
        selected = values if mask is None else values[mask]
        return float(selected.mean()) if len(selected) else None
    metrics = dict(
        accuracy=mean(predicted == targets),
        identifiable_accuracy=mean(predicted == targets, ~ambiguous),
        indistinguishable_accuracy=mean(predicted == targets, ambiguous),
        indistinguishable_mean_confidence=mean(probs.max(-1), ambiguous),
        indistinguishable_quarantine_rate=mean(~committed, ambiguous),
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
                              num_candidates=candidate_count).to(device)
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
