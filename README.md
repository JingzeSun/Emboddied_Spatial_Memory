# VSMT-lean: Versioned Lifecycle Transactions for Object-Level Spatial Memory

Code, configurations, result exports and paper source for the manuscript *Versioned Lifecycle Transactions for
Object-Level Spatial Memory: A Pre-Registered Evaluation Under Unobserved Changes* (under review).
Weights and data: [Hugging Face, Jsun0632](https://huggingface.co/Jsun0632) ·
Reproduction guide: [docs/REPRODUCE.md](docs/REPRODUCE.md) · Memory plug-in: [docs/PLUGIN.md](docs/PLUGIN.md) ·
Paper source: [paper/](paper/)

## Start here

| I want to … | Go to |
|---|---|
| see the main results | [Main results](#main-results) below |
| reproduce the paper's test results (CPU, about 3 minutes, no download) | `uv run python reproduce/paper.py` · [docs/REPRODUCE.md](docs/REPRODUCE.md) |
| check what my machine lacks for a reproduction level | `uv run python reproduce/check_env.py --level L0` (`L1`, `L2`, `L3`, `full`, `plugin`) |
| re-run the evaluation from the released data | `uv run python reproduce/l1_eval.py` · [docs/REPRODUCE.md, section 1](docs/REPRODUCE.md#1-reproduction-levels-and-determinism) |
| regenerate the data and retrain, stage by stage | [docs/REPRODUCE.md, section 11](docs/REPRODUCE.md#11-full-pipeline-from-procthor-10k) |
| use the memory on my own RGB-D stream (robot, dataset) | [docs/PLUGIN.md](docs/PLUGIN.md) · package [`vsmt_memory/`](vsmt_memory/) |
| understand the method, data and admissible claims | [docs/METHOD.md](docs/METHOD.md) · [docs/DATA.md](docs/DATA.md) |

## Overview

A robot that revisits a changed home must decide, for every remembered object it cannot see, whether the object is
hidden, missed by the detector, removed or moved, and it must re-identify objects that were moved. VSMT-lean is the
entity-lifecycle core of Versioned Structural Memory Transactions (VSMT; the full design also revises places and
relations, which are not part of this work): an object-level memory that applies five operations per frame as one
transaction.

| Operation | Effect |
|---|---|
| `NOOP` | keeps an unmatched entity that should be visible and counts a missed opportunity |
| `BIND` | attaches a fragment to an active entity as new evidence |
| `BIRTH` | creates an entity from an unassigned fragment |
| `RETRACT` | closes the current version of an entity; history is kept, nothing is deleted |
| `REACTIVATE` | opens a new version of a dormant or retracted entity with the same identity |

`REPLACE` is the composite `RETRACT` + `BIRTH`. `MERGE` is a deterministic deduplication rule shared byte for byte by
all compared methods, not a learned operation. `SPLIT`, `RELINK`, place and topology revision, and relation edges are
outside the scope of this paper.

Each frame, a frozen front end (simulator instance masks or SAM 2.1, with RGB-D geometry and frozen DINOv2 descriptors)
turns the image into anonymous mask fragments. Recall proposes candidate entities per fragment; one rectangular
Hungarian assignment decides `BIND`, `REACTIVATE` or `BIRTH`; an existence head decides `RETRACT` or `NOOP` for every
unmatched entity that should be visible; and the executor applies the whole program to a copy of the previous memory,
all or nothing. Apart from a ReID projection of the DINOv2 descriptors that every compared method shares (trained once
per front end), the only learned components are three small MLP cost heads (association, birth, existence; 54,787
parameters in total), trained in two rounds of DAgger (dataset aggregation) on hindsight labels derived from the
simulator's instance ground truth. Candidate sets and feature tables are sealed (hashed and recorded) before any
ground-truth file is opened, so the hindsight teacher can label candidates but never add, remove or reorder them; no
object identity, class, change log or future frame is ever an input.

The evaluation compares nine arms (compared methods) that read byte-identical front-end outputs: VSMT-lean; the
ablations `AssocOnly` (same association head, only `BIND`/`BIRTH`; the counterfactual for the lifecycle vocabulary),
`NoVersion` (retraction deletes), `HeuristicLabel` (labels copied from a rule-based arm) and `HandCost` (hand-written
costs); and four rule-based mechanisms re-implemented on the same interface (`TAF`, `ELU-P`, `RAC`, `LOW`; adapters of
published mechanisms, not official reproductions). Data are procedurally generated ProcTHOR-10K houses with object
changes made during an unobserved window. The primary hypothesis (revised after development and confirmation
readings), the testing order and the statistics were registered internally before validation or test data were read,
and the test was run once.

## Main results

Test split, read once: 87 of the 100 test houses produced usable episodes (85 with SAM 2.1 outputs;
[docs/DATA.md, section 9](docs/DATA.md#9-status)). Each mean is taken after the registered per-metric exclusion of
houses on which the metric is undefined for any main-table run (every arm and seed): 62 houses for MRR and 58 for IdC
with instance masks, 61 and 56 with SAM 2.1. The inference target is the training procedure
(five seeds). The primary hypothesis was tested in a fixed order against the same-recipe `AssocOnly` ablation.
"Lower bound" is the one-sided 95% lower bound of VSMT-lean's advantage from a two-level (seeds and houses) bootstrap.
MRR (Missing residual rate) is the share of removed or moved objects that still have an entity (a *stale entity*) at
their old place after it was seen empty; IdC (identity continuity) is the share of moved objects whose first new
observation is attached to the entity that carried them before.

| Front end | Metric | AssocOnly | VSMT-lean | Lower bound | Fixed-order step |
|---|---|---|---|---|---|
| Simulator instance masks | MRR (lower is better) | 0.642 | 0.115 | 0.467 | 1: holds |
| Simulator instance masks | IdC | 0.104 | 0.211 | 0.049 | 1: holds |
| SAM 2.1 masks | MRR (lower is better) | 0.235 | 0.055 | 0.135 | 2: holds |
| SAM 2.1 masks | IdC | 0.082 | 0.063 | −0.049 | 3: does not hold |

- The simulator instance masks segment almost perfectly, so the first two rows concern memory updates given near-ideal
  segmentation. With SAM 2.1, stale entities also fall, but identity continuity does not improve, and more than half
  of VSMT-lean's in-scope retractions (walls, floors, doors, windows and ceilings excluded) concern objects still in
  place.
- Node F1 differs from `AssocOnly` by +0.003 (instance masks) and +0.009 (SAM 2.1); no margin was registered, so these
  are reported as differences only.
- No method leads on every metric. The originally registered gate against the strongest rule-based arm is not met on
  either front end: with instance masks `ELU-P` leaves fewer stale entities (MRR 0.075 vs. 0.115), while per house on
  average 92.4% of its in-scope retractions concern objects still in place.
- In a descriptive ablation, deleting instead of retracting (`NoVersion`) leaves slightly fewer stale entities but drops
  identity continuity to 0.006 (instance masks) and 0.014 (SAM 2.1).

The full results (all arms and metrics, intervals, error ledgers, the 3RScan external check and the LLM-op arm in
Table III) are in the paper and in `results/`; [docs/REPRODUCE.md](docs/REPRODUCE.md#2-paper-results-index-l0) maps
every table and figure to its file and fields. The admissible claims are fixed in [docs/METHOD.md](docs/METHOD.md)
(section 2, ruling 113).

## Installation

Python 3.11 or 3.12 with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv pip install matplotlib==3.10.8 huggingface_hub pillow
```

`uv sync` installs the core dependencies (`numpy`, `torch`), which cover the memory, the cost heads, the evaluator,
the statistics and the recomputation of all statistics from `results/`; `matplotlib` is needed for the paper figures
(3.10.8 wrote the committed ones byte for byte), `huggingface_hub` for downloads and `pillow` for the memory plug-in. Run the commands below with `uv run` or inside the activated `.venv`. Data
generation runs AI2-THOR in a separate Python 3.9 simulator environment on the servers
(`$AUTODL/vsmt-envs/simulator-py39`, see [docs/REPRODUCE.md, section 11](docs/REPRODUCE.md#11-full-pipeline-from-procthor-10k)).
Building the paper needs MiKTeX or TeX Live.

Run the test suite from the repository root:

```bash
PYTHONPATH=src uv run python -m unittest discover -s tests -t tests -p "test_*.py"
```

## Data and weights

The data and weights behind the paper's results are on Hugging Face in four independently downloadable layers; the
paper cites these revisions. Two inputs were added to T0 after the paper's revision (decision D-224-REPRO): the ReID
head of the instance-mask front end (`5cea91cf…`), needed to re-run the instance-mask audits, and the salt of ruling 37,
which decided the no-change draw and is needed to regenerate the data; `uv run python reproduce/fetch_extras.py --dest
<data root>` fetches and checks both (neither is needed to recompute the statistics;
[docs/REPRODUCE.md, section 1](docs/REPRODUCE.md#1-reproduction-levels-and-determinism)).

| Layer | Repository | Content | Revision |
|---|---|---|---|
| T0 | [`Jsun0632/vsmt-lean`](https://huggingface.co/Jsun0632/vsmt-lean) | results and weights | `0b2ce7f8bb5d` |
| T1 | [`Jsun0632/vsmt-lean-s3-eval`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-eval) | validation and test inputs | `1bb81d27554d` |
| T2 | [`Jsun0632/vsmt-lean-s3-records`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-records) | training and audit records | `1d45b57add4a` |
| T3 | [`Jsun0632/vsmt-lean-s3-train`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-train) | training inputs | `d03966859294` |
| T0 addendum | [`Jsun0632/vsmt-lean`](https://huggingface.co/Jsun0632/vsmt-lean) | instance-mask ReID head, salt of ruling 37 | `1fc9efe87f99` (after the paper) |

For example, to fetch the validation instance-mask cache:

```bash
uv run python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-eval --repo-type dataset --revision 1bb81d27554d3795439172c418dc1416bff0c56e --select validation/instance_cache/ --dest /root/autodl-tmp
```

Full revisions, manifests and verification are described in
[docs/REPRODUCE.md](docs/REPRODUCE.md#3-data-and-weights-on-hugging-face-s3-05r).

## Reproducing the paper

Every statistic, table and data figure can be recomputed from the committed exports on a CPU, without downloading any
data. From `main`, one command does it in a temporary worktree of the tag `paper-v1` (created in the system's
temporary directory and removed afterwards) and checks every output against the committed files:

```bash
uv run python reproduce/paper.py
```

By hand, run the commands from a checkout of the tag `paper-v1`, the state of the repository that produced the paper
(the recomputation refuses to run unless `src/` and `configs/` equal the frozen commit `dea8c20`, which holds at the
tag but not on `main`, where comments were translated and earlier code removed):

```bash
git checkout paper-v1
uv run python ops/vsmt/s3_06_reanalysis.py run --workers 8
uv run python paper/tools/make_tables.py
uv run python paper/tools/make_figures.py
bash paper/tools/build.sh
```

The first command recomputes the test statistics and checks them value for value against the committed test export
(stage S3-05) before computing anything else. The further reproduction levels re-run the evaluation (T1), inspect
training (T2), or regenerate the data and retrain (T3 holds the training inputs, but the drivers need the data
regenerated, see section 1 of the guide); [docs/REPRODUCE.md](docs/REPRODUCE.md) gives
the commands, inputs, stop conditions and the determinism boundary of every stage (weights are bit-identical for the
same commit and thread count, verified on Intel AVX-512 with MKL).

## Repository structure

| Path | Content |
|---|---|
| `src/vsmt/lean_*.py` | the method and its evaluation: entity memory and executor; front-end cache; recall, features, seals and assignment; cost heads; per-frame loop; arms; teacher, metrics and statistics; data-generation rules; stage logic (training recipe, freeze, test statistics, test seal) |
| `src/vsmt/` (other modules), `src/cpmt/hashing.py` | helpers from earlier project directions that the current code still uses (fragment geometry, DINOv2 pooling, free space and visibility; canonical JSON and hashing) |
| `ops/vsmt/` | stage entry points: data generation, caches, training and selection, freeze, test, reanalysis, LLM-op, release |
| `configs/vsmt/` | versioned machine-readable contracts (`lean_*.json`) and four contracts of earlier directions that current code or tests still read (front-end assets and the observation runner); rule digests are pinned by cross-contract tests |
| `tests/` | unit and contract tests |
| `schemas/` | one JSON schema of an earlier direction, read by the tests of `vm04_observation_runner` |
| `results/` | committed result exports with manifests and digests (the source of every number in the paper) |
| `reproduce/` | one-command reproduction entry points (L0, L1) and the environment check |
| `vsmt_memory/` | the memory as a plug-in for an RGB-D stream, with examples and tests ([docs/PLUGIN.md](docs/PLUGIN.md)) |
| `paper/` | LaTeX source of the paper and the scripts that generate its tables and figures |
| `docs/` | method, data, reproduction guide, plan and decisions |
| `data/`, `outputs/` | local data and large server outputs (not tracked) |

[docs/METHOD.md](docs/METHOD.md) section 13 maps every component of the paper to a file and function. Several stage
scripts keep the names of the stage that introduced them (for example `ops/vsmt/lean_s1_02a_pilot.py` is the data
generator and `ops/vsmt/lean_s2_05_node_audit.py` the audit runner of S3-03 and S3-05); the code map lists them.

The tag `paper-v1` is the state that produced the paper. On `main`, comments and docstrings were translated to English
after the tag (syntax trees otherwise unchanged; the two package `__init__.py` files no longer import anything), and
the code of earlier project directions (the CPMT executor, the unified graph, place layer and structure estimators,
their contracts, tests and fixtures) and six one-off development scripts were removed; they remain at their original
paths under the tag. The retained code behaves identically, and the `lean_*` contracts and all results are unchanged.
The S3-07 code (3RScan check) was merged into `main` afterwards (`21e0d6e`) as it ran; it is not in `paper-v1`, and its
comments are partly in Chinese.

## Documentation

| Document | Content |
|---|---|
| [docs/METHOD.md](docs/METHOD.md) | method specification, arms, metrics, statistics and the admissible claims |
| [docs/DATA.md](docs/DATA.md) | data sources, splits, interventions, fields and leakage checks |
| [docs/REPRODUCE.md](docs/REPRODUCE.md) | stage-by-stage reproduction and the paper results index |
| [docs/PLUGIN.md](docs/PLUGIN.md) | using the memory on another RGB-D stream: inputs, outputs, weights, verification |
| [paper/README.md](paper/README.md) | building the paper and its checks |

Project records:

| Record | Content |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | stage plan and current status |
| [EXECUTE.md](EXECUTE.md) | experiment log: results, failures and claim evidence |
| [docs/DECISIONS.md](docs/DECISIONS.md) | research decisions (rulings) and their rationale |
| [AGENTS.md](AGENTS.md) | working rules for coding agents in this repository |

`EXECUTE.md` and `docs/DECISIONS.md` are the original research records and are written in Chinese up to 2026-10-09;
later entries are in English. The Chinese versions of the other documents are preserved under the tag
`docs-zh-2026-10-09`.

## Tags and branches

- `paper-v1` (tag): the code, configurations, results and paper source that produced the manuscript; use it for every
  reproduction step. Only re-checking the S3-04 freeze receipt needs the freeze commit `dea8c20` itself (the receipt
  fingerprints every file in `src/`, `ops/` and `configs/`, and later commits add scripts to `ops/`).
- `main`: current work; `s1-02a-runner` mirrors `main` for the servers.
- `s3-07-impl`: the 3RScan conversion, rendering and external-check driver, merged into `main` on 2026-10-09
  (`21e0d6e`); kept for its history.
- `archive/pre-d224-unified-graph`: documents of the unified-graph and eight-atom directions, superseded by decision
  D-224.
- `archive/cpmt-m1-20260917`, `archive/spatial-world-model-20260917`: snapshots taken before the CPMT/M1 and
  spatial-world-model code left `main` (commit `d7159ba`).
- `docs-zh-2026-10-09` (tag): the Chinese versions of the documents before their translation.

## Licence

- Code and configurations: Apache-2.0 ([LICENSE](LICENSE)). The paper text and figures in `paper/` are not covered.
- Weights (T0): Apache-2.0. Data (T1–T3) and result exports: CC-BY-4.0 for this project's contributions; the upstream
  material they contain (AI2-THOR renderings of ProcTHOR-10K houses; SAM 2.1 and DINOv2 features) remains under
  Apache-2.0.
- No 3RScan data are redistributed; reproducing the 3RScan check requires access granted by TUM.

When using the data, please also cite ProcTHOR, AI2-THOR, DINOv2 and SAM 2.

## Citation

```bibtex
@misc{sun2026vsmtlean,
  title  = {Versioned Lifecycle Transactions for Object-Level Spatial Memory: A Pre-Registered Evaluation Under Unobserved Changes},
  author = {Sun, Jingze},
  year   = {2026},
  note   = {Manuscript under review},
  url    = {https://github.com/JingzeSun/VSMT}
}
```

## Acknowledgements

This work builds on AI2-THOR, ProcTHOR-10K, SAM 2, DINOv2 and 3RScan. The LLM-op arm used the DeepSeek API.
