# VSMT-lean: Versioned Lifecycle Transactions for Object-Level Spatial Memory

Code, configurations, result exports and paper source for the manuscript *Versioned Lifecycle Transactions for
Object-Level Spatial Memory: A Pre-Registered Evaluation Under Unobserved Changes* (under review).
Weights and data: [Hugging Face, Jsun0632](https://huggingface.co/Jsun0632) ·
Reproduction guide: [docs/REPRODUCE.md](docs/REPRODUCE.md) · Paper source: [paper/](paper/)

## Overview

A robot that revisits a changed home must decide, for every remembered object it cannot see, whether the object is
hidden, missed by the detector, removed or moved, and it must re-identify objects that were moved. VSMT-lean is the
entity-lifecycle core of versioned structural memory transactions: an object-level memory that applies five
operations per frame as one transaction.

| Operation | Effect |
|---|---|
| `NOOP` | keeps an unmatched entity that should be visible and counts a missed opportunity |
| `BIND` | attaches a fragment to an active entity as new evidence |
| `BIRTH` | creates an entity from an unassigned fragment |
| `RETRACT` | closes the current version of an entity; history is kept, nothing is deleted |
| `REACTIVATE` | opens a new version of a dormant or retracted entity with the same identity |

`REPLACE` is the composite `RETRACT` + `BIRTH`. `MERGE` is a deterministic de-duplication rule shared byte for byte by
all compared methods, not a learned operation. `SPLIT`, `RELINK`, place and topology revision, and relation edges are
outside the scope of the first paper.

Each frame, a frozen front end (simulator instance masks or SAM 2.1, with RGB-D geometry and frozen DINOv2 descriptors)
turns the image into anonymous mask fragments. Recall proposes candidate entities per fragment; one rectangular
Hungarian assignment decides `BIND`, `REACTIVATE` or `BIRTH`; an existence head decides `RETRACT` or `NOOP` for every
unmatched entity that should be visible; and the executor applies the whole program to a copy of the previous memory,
all or nothing. The only learned part is three small MLP cost heads (association, birth, existence; 54,787 parameters),
trained in two DAgger rounds on hindsight labels from the simulator's instance ground truth. Candidate sets and feature
tables are sealed before any ground-truth file is opened, so the teacher can label candidates but never add, remove or
reorder them; no object identity, class, change log or future frame is ever an input.

The evaluation compares nine arms that read byte-identical front-end outputs: VSMT-lean; the ablations `AssocOnly`
(same association head, only `BIND`/`BIRTH`; the counterfactual for the lifecycle vocabulary), `NoVersion` (retraction
deletes), `HeuristicLabel` (labels copied from a rule-based arm) and `HandCost` (hand-written costs); and four
rule-based mechanisms re-implemented on the same interface (`TAF`, `ELU-P`, `RAC`, `LOW`; adapters of published
mechanisms, not official reproductions). Data are procedurally generated ProcTHOR-10K houses with object changes made
during an unobserved window. The primary hypothesis, the testing order and the statistics were registered internally
before validation or test data were read, and the test was run once.

## Main results

Test split, one read, 87 ProcTHOR houses (85 with SAM 2.1 outputs). The inference target is the training procedure
(five seeds). The primary hypothesis was tested in a fixed order against the same-recipe `AssocOnly` ablation;
"lower bound" is the two-level one-sided 95% lower bound of VSMT-lean's advantage.

| Front end | Metric | AssocOnly | VSMT-lean | Lower bound | Fixed-order step |
|---|---|---|---|---|---|
| Simulator instance masks | Missing residual rate (MRR, lower is better) | 0.642 | 0.115 | 0.467 | 1: holds |
| Simulator instance masks | Identity continuity (IdC) | 0.104 | 0.211 | 0.049 | 1: holds |
| SAM 2.1 masks | Missing residual rate (MRR, lower is better) | 0.235 | 0.055 | 0.135 | 2: holds |
| SAM 2.1 masks | Identity continuity (IdC) | 0.082 | 0.063 | −0.049 | 3: fails |

- The simulator instance masks segment almost perfectly, so the first two rows concern memory updates given near-ideal
  segmentation. With SAM 2.1, stale entities also fall, but identity continuity does not improve, and more than half
  of VSMT-lean's in-scope retractions concern objects still in place.
- Node F1 differs from `AssocOnly` by +0.003 (instance masks) and +0.009 (SAM 2.1); no margin was registered, so these
  are reported as differences only.
- No method leads on every metric. The originally registered gate against the strongest rule-based arm is not met: with
  instance masks `ELU-P` leaves fewer stale entities (MRR 0.075 vs. 0.115), while per house on average 92.4% of its
  in-scope retractions concern objects still in place.
- In a descriptive ablation, deleting instead of retracting (`NoVersion`) leaves slightly fewer stale entities but drops
  identity continuity to 0.006 (instance masks) and 0.014 (SAM 2.1).

The full results (all arms and metrics, intervals, ledgers, the 3RScan external check and the LLM-op appendix arm) are
in the paper and in `results/`; [docs/REPRODUCE.md](docs/REPRODUCE.md#2-paper-results-index-l0) maps every table and
figure to its file and fields. The admissible claims are fixed in [docs/METHOD.md](docs/METHOD.md) (section 2,
ruling 113).

## Installation

Python 3.11 or 3.12 with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

This installs the core dependencies (`numpy`, `torch`), which cover the memory, the cost heads, the evaluator, the
statistics and the L0 recomputation. Data generation runs AI2-THOR in a separate Python 3.9 simulator environment on
the servers (`$AUTODL/vsmt-envs/simulator-py39`, see
[docs/REPRODUCE.md](docs/REPRODUCE.md#5-s3-02-formal-data-ruling-103)). Building the paper needs MiKTeX or TeX Live.

Run the test suite from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -t tests -p "test_*.py"
```

## Data and weights

All S3 products are on Hugging Face in four independently downloadable layers; the paper cites these revisions.

| Layer | Repository | Content | Revision |
|---|---|---|---|
| T0 | [`Jsun0632/vsmt-lean`](https://huggingface.co/Jsun0632/vsmt-lean) | results and weights | `0b2ce7f8bb5d` |
| T1 | [`Jsun0632/vsmt-lean-s3-eval`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-eval) | validation and test inputs | `1bb81d27554d` |
| T2 | [`Jsun0632/vsmt-lean-s3-records`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-records) | training and audit records | `1d45b57add4a` |
| T3 | [`Jsun0632/vsmt-lean-s3-train`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-train) | training inputs | `d03966859294` |

For example, to fetch the validation instance-mask cache:

```bash
python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-eval --repo-type dataset --revision 1bb81d27554d3795439172c418dc1416bff0c56e --select validation/instance_cache/ --dest /root/autodl-tmp
```

Full revisions, manifests and verification are described in
[docs/REPRODUCE.md](docs/REPRODUCE.md#3-data-and-weights-on-hugging-face-s3-05r).

## Reproducing the paper

Every statistic, table and data figure can be recomputed from the committed exports on a CPU, without the data:

```bash
python ops/vsmt/s3_06_reanalysis.py run --workers 8
python paper/tools/make_tables.py
python paper/tools/make_figures.py
bash paper/tools/build.sh
```

The first command reproduces the S3-05 test statistics value for value before computing anything else.
Deeper levels re-run the evaluation (T1), inspect training (T2), retrain (T3) or regenerate everything from
ProcTHOR-10K; [docs/REPRODUCE.md](docs/REPRODUCE.md) gives the commands, inputs, stop points and the determinism
boundary of every stage (weights are bit-identical for the same commit and thread count, verified on Intel AVX-512
with MKL).

## Repository structure

| Path | Content |
|---|---|
| `src/vsmt/lean_*.py` | core implementation: entity memory and executor; features, recall and assignment; front-end caches; compared arms; cost heads; runner; teacher and evaluator; statistics |
| `ops/vsmt/` | server entry points of every stage (data generation, caches, training and selection, freeze, test, reanalysis, release) |
| `configs/vsmt/lean_*.json` | versioned machine-readable contracts; rule digests are pinned by cross-contract tests |
| `tests/` | unit and contract tests |
| `results/` | committed result exports with manifests and digests (the source of every number in the paper) |
| `paper/` | LaTeX source of the paper and the scripts that generate its tables and figures |
| `docs/` | method, data, plan, decisions and reproduction guide |
| `data/`, `outputs/` | source and split lists; large server outputs (not tracked) |
| `src/cpmt/`, `src/spatial_world_model/`, non-`lean` modules in `src/vsmt/`, `experiments/`, `schemas/`, `docs/source/`, `prototype/` | earlier project directions, original source material and literature, kept for provenance; not used by any current entry point |

The code and configuration files are frozen: the S3-04 freeze receipt fingerprints every tracked file in `src/`,
`ops/` and `configs/`, and S3-05 rechecks those fingerprints. Comments inside these files are therefore left as they
were at the freeze, partly in Chinese.

## Documentation

| Document | Content |
|---|---|
| [docs/METHOD.md](docs/METHOD.md) | method specification, arms, metrics, statistics and the admissible claims |
| [docs/DATA.md](docs/DATA.md) | data sources, splits, interventions, fields and leakage checks |
| [docs/REPRODUCE.md](docs/REPRODUCE.md) | stage-by-stage reproduction and the paper results index |
| [docs/PLAN.md](docs/PLAN.md) | stage plan and current status |
| [EXECUTE.md](EXECUTE.md) | experiment log: results, failures and claim evidence |
| [docs/DECISIONS.md](docs/DECISIONS.md) | research decisions (rulings) and their rationale |
| [paper/README.md](paper/README.md) | building the paper and its checks |
| [AGENTS.md](AGENTS.md) | working rules for coding agents in this repository |

`EXECUTE.md` and `docs/DECISIONS.md` are the original research records and are written in Chinese up to 2026-10-09;
later entries are in English. The Chinese versions of the other documents are preserved under the tag
`docs-zh-2026-10-09`.

## Branches

- `main`: current work; `s1-02a-runner` mirrors `main` for the servers.
- `s3-07-impl`: the 3RScan conversion, rendering and external-check driver (not yet merged into `main`).
- `archive/pre-d224-unified-graph`: earlier project directions (CPMT, spatial world model, unified graph, eight-atom
  vocabulary), superseded by decision D-224.

## Licence

- Weights (T0): Apache-2.0. Data (T1–T3) and result exports: CC-BY-4.0 for this project's contributions; the AI2-THOR
  renderings, ProcTHOR-10K houses and the SAM 2.1 and DINOv2 features they contain remain under Apache-2.0.
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

This work builds on AI2-THOR, ProcTHOR-10K, SAM 2, DINOv2 and 3RScan. The LLM-op appendix arm used the DeepSeek API.
