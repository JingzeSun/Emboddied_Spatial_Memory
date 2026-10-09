# Reproducing VSMT-lean

This document gives the commands, inputs, stop conditions and outputs for every stage behind the paper, from the
committed result files back to data generation. The method is specified in [METHOD.md](METHOD.md), the data in
[DATA.md](DATA.md); results and failures are logged in [EXECUTE.md](../EXECUTE.md).

**Quick start.** The entry points in [`reproduce/`](../reproduce/) run from a clone of `main` after the installation of
the README (`uv sync`, then `uv pip install matplotlib==3.10.8 huggingface_hub pillow`; a later `uv sync` removes the
packages it did not install, so repeat the second command after it, or use `uv sync --inexact`). Run them with
`uv run`, because `check_env.py` inspects the interpreter that runs it. Each creates its own clean worktree
of the commit it needs (`paper-v1` for L0, the S3-05 run commit `8d58475` for L1) in the system's temporary directory
with `git worktree add`, which registers it in this clone's `.git`, and removes it afterwards (`--keep-worktree` keeps
the L0 one for inspection). Reports go to `outputs/reproduce/` (not tracked).

| Goal | Command | Needs | Time (measured) |
|---|---|---|---|
| See what this machine lacks for a level | `uv run python reproduce/check_env.py --level L0` (or `L1`, `L2`, `L3`, `full`, `plugin`, `all`) | nothing | seconds |
| L0: recompute every statistic and rebuild Tables II–III and Figures 3–4 | `uv run python reproduce/paper.py` | CPU; `matplotlib==3.10.8` for byte-identical figures | 2–3 min on a laptop |
| L1: re-run the frozen audits on the S3-04 probe episodes (validation) | `uv run python reproduce/l1_eval.py --data-root <root> --front sam2 --scope probe` | T0 and T1 validation ([section 3](#3-data-and-weights-on-hugging-face-s3-05r)) | 50 audits per front end, about 1.5 min each single-threaded |
| L1: re-run the test audits (a further read of test, [section 1](#1-reproduction-levels-and-determinism)) | `... --scope test --acknowledge-post-publication-reread` | T1 test (68 GiB) | 25 runs x 85–87 episodes per front end; the original took about 22 h on about 100 cores |
| Retraining and the full pipeline | [section 11](#11-full-pipeline-from-procthor-10k) | Linux; GPUs for the simulator and the caches (training is CPU only); about 410 GB disk; the outside-rerun edits of section 11 | days |
| Use the memory on another RGB-D stream | [PLUGIN.md](PLUGIN.md) | CPU | 0.4 s per frame |

Conventions used below:

- Code version: run every stage command from a checkout of the tag `paper-v1`, the state that produced the paper,
  except where a section names the commit a stage ran at (S2-06, S3-04, S3-05); the entry points in `reproduce/` run
  from `main` and create their own worktrees. On `main`,
  comments and docstrings were later translated and the code of earlier project directions removed (the retained
  code is otherwise unchanged); the stage drivers compare the code against the digests recorded by earlier steps, and
  the L0 recomputation requires `src/` and `configs/` to equal the frozen commit `dea8c20`, which holds at the tag.
  The one exception is the S3-04 freeze check, which holds only at `dea8c20` itself (section 8).
- Server paths assume `AUTODL=/root/autodl-tmp` and, on the maintainers' servers, the clone
  `/root/Emboddied_Spatial_Memory` (the actual directory name); use your own clone path.
- B1 is the maintainers' coordinating server of the paper's runs and w1–w6 their worker hosts.
- Every server stage runs in a clean, detached worktree of a reviewed commit and is resumable: running `all` again
  continues from the last completed step. A step refuses to reuse its output if the code changed after it completed,
  except for the files listed for that stage.
- `<commit>` is the reviewed commit; `<tag>` is the short hash of the commit on which a run's first `check` ran; it
  suffixes the run's output names (it is not a Git tag).
- An *audit* is one closed-loop evaluation of an arm configuration and head set on one episode; it writes per-episode
  metrics.
- "The project owner" is the maintainer who reviews code and approves stage transitions; the release key and the
  contract switches below are issued by the owner.

## Contents

1. [Reproduction levels and determinism](#1-reproduction-levels-and-determinism)
2. [Paper results index (L0)](#2-paper-results-index-l0)
3. [Data and weights on Hugging Face (S3-05R)](#3-data-and-weights-on-hugging-face-s3-05r)
4. [S2-06: SAM 2.1 development table](#4-s2-06-sam-21-development-table-ruling-100-6)
5. [S3-02: formal data](#5-s3-02-formal-data-ruling-103)
6. [S3-03: training and selection readings](#6-s3-03-training-and-selection-readings-ruling-104)
7. [S3-04: freeze after validation](#7-s3-04-freeze-after-validation-ruling-106)
8. [S3-05: one-time test run](#8-s3-05-one-time-test-run-ruling-107)
9. [LLM-op arm](#9-llm-op-arm-ruling-105)
10. [S3-07: external check on 3RScan](#10-s3-07-external-check-on-3rscan)
11. [Full pipeline from ProcTHOR-10K](#11-full-pipeline-from-procthor-10k)

## 1. Reproduction levels and determinism

| Level | Needs | Reproduces |
|---|---|---|
| L0 | this repository (`results/`), CPU | every statistic, table and data figure of the paper ([section 2](#2-paper-results-index-l0)) |
| L1 | HF T0 + T1 (weights; validation and test episodes, geometry, both caches) | the evaluation audits |
| L2 | HF T2 (training and audit records) | inspection of training; intermediate outputs |
| L3 | HF T3 (training inputs), or ProcTHOR-10K and the code | retraining without regenerating data (T3), or the full pipeline from ProcTHOR-10K |

**L1 and re-reading test.** `reproduce/l1_eval.py` runs the frozen audit entry with the configurations, heads and ReID
head of the S3-04 freeze receipt and compares every audit with the paper's: `--scope probe` with the S3-04 probe audits
in T0 (validation only), `--scope test` with the per-episode records of `results/vsmt_lean_s3_05_merged_*`. The test
split was read once for the paper (S3-05, LOG-306). A re-run of the test audits reproduces that read with nothing left
to choose, but it is a further read of test, so it is recorded: the entry refuses without
`--acknowledge-post-publication-reread`, writes `REPRODUCTION_READ.json` (time, commit, receipt digest, purpose) into its
own output directory before reading anything, never writes into the test roots (whose markers stay as released:
opened by receipt `4fd08d4f…`), and exports only the comparison, never new statistics. A re-run by the project owner is
also logged in EXECUTE as a reproduction read. The instance-mask ReID head (`5cea91cf…`) is not in any Hugging Face
layer, so from the release alone only the SAM 2.1 audits can be re-run.

**L3 from the released data.** The S3-03 and S3-04 drivers require the four test roots to be sealed (they check the
markers, never the episodes); the released test roots are marked opened, because they were released after S3-05.
Retraining with the existing drivers therefore needs data regenerated by S3-02 (section 11); a driver that retrains
from T3 alone does not exist yet.

**The private salt.** The full pipeline from ProcTHOR-10K reproduces the same episodes only with the private salt of
ruling 37, which decides the no-change draw and is not released; with another salt the draw differs. The released
episodes (T1, T3) carry the draw that was used.

Determinism boundary:

- Weights are bit-identical for the same commit and the same `TRAIN_THREADS` (ruling 96); this was verified only on
  Intel AVX-512 with MKL. On an AMD host (w1), bit identity was obtained only after an MKL setting in
  `/etc/environment` loaded through `LD_PRELOAD` (EXECUTE LOG-304 and LOG-307 section C; the exact setting is not
  recorded); other CPUs may differ in the last bits.
- Audits are deterministic within one environment (the S3-04 probes reproduce bit for bit on the servers). Across
  environments a few near-tie decisions can differ: the S3-04 probe audit of VSMT-lean (SAM 2.1, seed 7) on
  `procthor10k-0.1.2-train-02318`, re-run on a Windows laptop (Intel 13th generation, torch 2.14.0, numpy 2.5.2) instead
  of the server (Linux, Xeon 8352V, torch 2.8.0, numpy 2.3.2), gave identical final entity states and identical
  values for every metric of the audit report, while the error decomposition differed in 19 of about 5,500 decisions
  and the per-frame seal chain differed (EXECUTE LOG-316).
- The data generator reproduces episode structure; byte identity is not guaranteed (LOG-303).
- SAM 2.1 caches are expected to be deterministic but were not checked byte for byte.
- LLM-op is reproduced by replaying its archived API calls, which reproduces the run byte for byte; the hosted API
  itself is not reproducible.

## 2. Paper results index (L0)

Every number in the paper comes from a committed export in `results/`; tables and data figures are generated by
scripts and are never edited by hand. A machine-readable index, `results/vsmt_lean_s3_06_paper_index_154043e.json`
(the current one; `…_cd3ee83.json` is the earlier index written with the reanalysis, before the S3-07 exports; a run of
`reproduce/paper.py` writes a third one in its temporary worktree and discards it), lists each item with its file, fields, command and the SHA-256 of every file checked against the stage manifests.
That index uses the numbering of the first draft (`table_1` … `table_8`, `appendix_*`); the mapping to the current
paper is:

| Current paper | Index items | Files (`results/`) and fields |
|---|---|---|
| Table I (arms) | — | none (description only) |
| Table II (test results) | `table_1_main_instance`, `table_2_main_sam2` | `vsmt_lean_s3_05_statistics_8d58475.json` → `fronts.<front>.main_table` (means), `fronts.<front>.primary_gate.metrics.<metric>.lower_bound_two_level` (lower bound), `fixed_sequence.steps` (fixed-order step), `exclusion_lists`; event and denominator counts in `vsmt_lean_s3_06_reanalysis_cd3ee83.json` → `d4_counts` (`per_arm_kept_houses` for the houses behind the table means, `per_arm_all_houses` for absolute counts over all usable episodes) |
| Fig. 3 (pre-registered test) | `table_3_main_gate` | statistics → `fixed_sequence`, `fronts.<front>.primary_gate`, `fronts.<front>.original_gate`; two-sided 90% intervals in reanalysis → `d3_intervals` |
| Fig. 4 (comparison matrix) | `table_4_ablations`, `table_5_rule_arms`, `table_8_external_3rscan` | reanalysis → `d3_intervals` (panels a, b); `vsmt_lean_s3_07_statistics_aa94373.json` → `fronts.instance.comparisons`, `exclusion_lists` (panel c) |
| Table III (LLM-op) | `appendix_llm_op` | `vsmt_lean_llm_op_dea8c20.json`; other arms on the same episode in `vsmt_lean_s4_llm_op_context_2b50a12.json` |
| Sections IV-A, IV-C, IV-D (data, selection, null calibration) | `appendix_data`, `appendix_selection`, `appendix_power` | `vsmt_lean_s3_02_*_3f6ef1d.json`; `vsmt_lean_s3_04_selection_{instance,sam2}_dea8c20.json`; `vsmt_lean_s3_01_planning_6c57903.json` |
| Section V-A (per-house counts), V-E (ledger, memory size) | `figure_3_per_house`, `table_6_decomposition`, `table_7_size_and_cost` | reanalysis → `d5_per_house`, `d6_decomposition`, `d7_size_and_cost`; statistics → `fronts.<front>.decomposition_totals`, `size_and_cost_episode_means` |
| Not in the current paper | `figure_2_tradeoff`, `appendix_selection_curves`, `appendix_training` | `vsmt_lean_s3_03_{readings,trainings}_{instance,sam2}_10f7013.json` and the files above |

The provenance of each stage: S3-05 run `8d58475`, frozen at `dea8c20` (receipt `4fd08d4f…`); S3-06 reanalysis
`cd3ee83`; S3-07 run `aa94373` (code on branch `s3-07-impl`); LLM-op context export `2b50a12`.

**One command (L0).** `python reproduce/paper.py` (from `main`) runs the recomputation below and the two table and
figure scripts in a temporary worktree of `paper-v1`, compares the recomputed readings D1–D8 with the committed
`vsmt_lean_s3_06_reanalysis_cd3ee83.json` (the input list is compared on the files that run used; the tag also holds
the later S3-07 exports) and the regenerated tables and figures with the committed files, prints the rows of Table II
and exits with 0 only if everything is equal; its report lists the compared fields, inputs and files with their SHA-256
(text files as written, with LF line endings as in git; a Windows checkout with `core.autocrlf` holds CRLF copies) and
the numpy, torch and matplotlib versions. Measured on 2026-10-09 on Windows laptops: 2–3 minutes, all equal. That the
recomputation would notice a change is covered by the tests of the reanalysis (among them
`test_a_changed_number_stops_the_replay` and `test_an_export_that_differs_from_its_manifest_is_refused`), which run in
seconds: `PYTHONPATH=src uv run python -m unittest discover -s tests -t tests -p test_vsmt_lean_s3_06_reanalysis.py`.
The figure PDFs are byte-identical only with `matplotlib==3.10.8`, the version that wrote them; with another version
the script reports them as not compared.

**Recompute the statistics (L0).** CPU only; it does not read any test root or connect to a server. Run it from the
repository root on a commit whose `src/`, `ops/`, `configs/` and inputs have no uncommitted changes, whose inputs are
tracked by git, and whose `src/` and `configs/` equal the frozen commit `dea8c20`, such as the tag `paper-v1`
(on `main` it refuses with exit code 2):

```bash
git checkout paper-v1
python ops/vsmt/s3_06_reanalysis.py run --workers 8
```

The script first reproduces `vsmt_lean_s3_05_statistics_8d58475.json` value for value from the two merged audits
with the frozen `lean_s3_05` functions (`receipt_sha256` and `written_utc` excepted); on any difference it stops with
exit code 3 and writes only the differing fields. Only then does it compute D2–D8 and write
`results/vsmt_lean_s3_06_reanalysis_<tag>.json` and `results/vsmt_lean_s3_06_paper_index_<tag>.json`. To rewrite
only the index (for example after a later stage added exports), run
`python ops/vsmt/s3_06_reanalysis.py index --reanalysis-tag <tag of the committed reanalysis>`: it recomputes no
statistic, only the SHA-256 of every indexed file, compares them with the stage manifests and writes
`vsmt_lean_s3_06_paper_index_<current commit>.json`. Existing outputs of the same commit are not overwritten unless
`--replace` is given. Exit codes: 0 done; 2 refused (uncommitted changes, untracked or missing inputs, inputs that
disagree with a manifest, `src/` or `configs/` different from the frozen commit, output exists); 3 recomputation
differs; 4 written, but a consistency check reported a problem; 1 unexpected error. D2–D8 are descriptive readings
computed after the test (no gate, no correction for multiplicity); D3 and D5 are advantages, signed so that positive
favours VSMT-lean.

| Inputs (read only) | Outputs |
|---|---|
| `vsmt_lean_s3_05_*_8d58475.json` (seven files, each checked against the S3-05 manifest), `vsmt_lean_s3_04_{freeze,manifest}_dea8c20.json` | D1 recomputation check, D2 all metrics of VSMT-lean against AssocOnly, D3 two-sided 90% intervals, D4 event and denominator counts, D5 per-house paired differences, D6 decomposition shares, D7 size and cost, D8 consistency checks; the paper index |

**Scripts behind other committed files.** These scripts are not stage drivers, but the paper relies on what they wrote;
each reads only committed files unless stated otherwise:

| Script | Writes | Reads |
|---|---|---|
| `ops/vsmt/s3_01_manifests.py` | `configs/vsmt/lean_s3_01_manifests.json`: the test (100), validation (50) and train (positions 100–399) house lists (ruling 102-8) | the frozen split in `configs/vsmt/lean_s1_02a_pilot_v2.json`, the confirmation list `configs/vsmt/lean_ruling81_confirmation_houses.json` |
| `ops/vsmt/s3_01_planning.py` | `results/vsmt_lean_s3_01_planning_6c57903.json`: event denominators, null calibration and power (paper Section IV-D) | the committed development and confirmation audits |
| `ops/vsmt/lean_s1_05_select_descriptor.py` | `results/vsmt_lean_s1_05_descriptor_freeze_154776d.json` (SAM 2.1) and `..._oracle_caa50c7.json` (instance masks): the descriptor choice of ruling 47 | the committed S1-04 reports and contracts |
| `ops/vsmt/s4_llm_op_context.py` | `results/vsmt_lean_s4_llm_op_context_2b50a12.json`: the other arms on the LLM-op episode (Table III) | the S3-03 run root and the validation caches on the server, the committed freeze, readings and LLM-op exports |

**Rebuild the paper.** From the repository root (MiKTeX or TeX Live):

```bash
python paper/tools/make_tables.py
python paper/tools/make_figures.py
python paper/tools/check_draft.py
bash paper/tools/build.sh
```

`build.sh` writes the anonymous review version and the final version to `paper/build/` and fails on more than eight
pages, any overfull box, undefined references, or identifying text in the review PDF; see
[paper/README.md](../paper/README.md).

## 3. Data and weights on Hugging Face (S3-05R)

The data, weights and records behind the paper are released in four independently downloadable layers (ruling 110):

| Layer | Repository | Content | Revision cited in the paper | Check |
|---|---|---|---|---|
| T0 | [`Jsun0632/vsmt-lean`](https://huggingface.co/Jsun0632/vsmt-lean) (model) | results and weights: round-1 weights of both front ends, all exports (including S3-07), the S3-04 freeze directory, ReID heads | `0b2ce7f8bb5de862fd500f10b23e55ba4eebf372` | `results/vsmt_lean_hf_release_T0_2d179b9.json`, `verify`: 699 items, `pass` |
| T1 | [`Jsun0632/vsmt-lean-s3-eval`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-eval) (dataset) | validation and test: raw episodes, geometry, instance and SAM 2.1 caches | `1bb81d27554d3795439172c418dc1416bff0c56e` | `results/vsmt_lean_hf_release_T1_2d179b9.json`, `verify`: 582 items, `pass` |
| T2 | [`Jsun0632/vsmt-lean-s3-records`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-records) (dataset) | training and audit records (S3-03 and S3-05 run roots) | `1d45b57add4a89f4586a4b128a0cc7d1a81721c8` | `results/vsmt_lean_hf_release_T2_2d179b9.json`, `verify`: 33 items, `pass` |
| T3 | [`Jsun0632/vsmt-lean-s3-train`](https://huggingface.co/datasets/Jsun0632/vsmt-lean-s3-train) (dataset) | training inputs: train raw episodes, geometry, both caches | `d0396685929460b65496883b6007df5f6f23c0c9` | `results/vsmt_lean_hf_release_T3_2d179b9.json`, `verify`: 1,113 items, `pass` |

Later commits on these repositories only add the cards (`README.md`) and the licence file; no data file changed.
Each episode directory is one deterministic tar (members sorted by path, time 0, owner 0/0, modes 644/755);
`MANIFEST.json` records the SHA-256, size, restore path and directory-tree digest of every item (the same algorithm
as the S3-02 test seal). Before upload, every test episode was checked against the seal and every cache against the
S3-02 exports. `hf_fetch.py` checks each downloaded file against the manifest, unpacks it, recomputes the tree digest
and stops with exit code 3 on any mismatch (verified items are skipped on a rerun). Restore paths match the server
layout (under `/root/autodl-tmp`), so repository scripts need no path changes. `--dest` may be any directory; the
stage drivers, however, also read absolute `/root/autodl-tmp/...` paths recorded in the exports and receipts, so a
server reproduction should restore there or make `/root/autodl-tmp` a link to the restore directory. T2 restores whole
S3-03 run roots, inside which T0 restores the round-1 weights; restore T2 into its own `--dest`, otherwise the second
layer stops with `existing_target_differs`. The instance-mask ReID head (`5cea91cf…`), which the instance-mask runs of
S3-03 to S3-05 used, is not in any layer. `python reproduce/check_env.py --level L1 --data-root <dest>` lists what is
restored (`--deep` recomputes every digest).

Download and restore (any machine), for example the validation instance cache:

```bash
python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-eval --repo-type dataset --revision 1bb81d27554d3795439172c418dc1416bff0c56e --select validation/instance_cache/ --dest /root/autodl-tmp
```

Release (maintainers only; server B1, after `hf auth login`; the script sources `/etc/network_turbo` itself; rerunning
the same command resumes):

```bash
setsid nohup bash ops/vsmt/hf_release.sh T0 T1 > /root/autodl-tmp/vsmt_outputs/run_logs/hf-release.log 2>&1 < /dev/null &
```

Each layer runs: release tests → `plan` → `run` (pack, check, upload in batches, 20 GiB by default) → `verify`
(remote sizes and SHA-256 against the manifest; manifest and repository revision exported as
`vsmt_lean_hf_release_<layer>_<commit>.json`).

**Licences and attribution (ruling 114, approved 2026-10-08; details in docs/DECISIONS.md, "D-224-S3-05R").**

- RGB-D frames, poses, private ground truth, geometry tables and both caches (T1–T3): frames are rendered by
  AI2-THOR 5.0.0 (© 2021 Allen Institute for AI, Apache-2.0) in ProcTHOR-10K 0.1.2 houses (Apache-2.0), with objects
  changed by our intervention scripts; features are computed with DINOv2 ViT-B/14 and SAM 2.1 Hiera Small (both
  Apache-2.0). Our contributions are released under CC-BY-4.0; upstream material remains under Apache-2.0. Please cite
  ProcTHOR, AI2-THOR, DINOv2, SAM 2 and this work.
- T0 weights: Apache-2.0 (ruling 114-2); the result JSON files under `exports/`: CC-BY-4.0.
- 3RScan: neither this repository nor Hugging Face redistributes any 3RScan data (scans, instance maps rendered from
  the annotated meshes, ground truth or features); the 3RScan terms allow non-commercial research only and forbid
  redistribution. Only our metric exports (`results/vsmt_lean_s3_07_*_aa94373.json`) are public.
- The four repository cards follow ruling 114 (since 2026-10-08 20:04: T0 `apache-2.0`, T1–T3 `cc-by-4.0`, with the
  upstream notices, the full `LICENSE-APACHE-2.0` text and the 3RScan non-redistribution statement).

## 4. S2-06: SAM 2.1 development table (ruling 100-6)

S2-06 checks whether the development-set pattern seen with instance masks (against the same-recipe AssocOnly: far
fewer stale entities, higher identity continuity, slightly lower node F1) persists with SAM 2.1 segmentation when
every trainable and fitted part is redone on SAM 2.1 under the frozen rules. It produces the seven-arm SAM 2.1
development table and its pre-registered interpretation, side by side with the instance-mask reading. It is not a
test, not a cross-front-end transfer test (the heads are retrained on SAM 2.1), and not used to change the method.

Run (server; clean detached worktree of the reviewed commit; no GPU needed):

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s2-06-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s2-06-<commit>
nohup bash ops/vsmt/s2_06_sam2.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s2-06-<commit>.log 2>&1 &
bash ops/vsmt/s2_06_sam2.sh status
```

Rerunning `all` resumes from the last completed stage; a completed stage refuses reuse if the code changed afterwards
(changes that only register the SAM 2.1 fitted values, and documentation, are exempt). Stages, reads, writes and stop
points are listed at the top of [`ops/vsmt/s2_06_sam2.sh`](../ops/vsmt/s2_06_sam2.sh).

| Input (`AUTODL=/root/autodl-tmp`) | Default path | Check before running (`check`) |
|---|---|---|
| SAM 2.1 development cache | `$AUTODL/vsmt_caches/lean-s1-03-154776d` (39 episodes, 44,097 frames) | every seal names mask source sam2 |
| Instance-mask development cache | `$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05` | the same 39 episodes, source instance masks |
| Geometry reload, S1-02 episodes | `$AUTODL/vsmt_private/lean-s1-04-geometry-154776d`, `$AUTODL/vsmt_outputs/lean-s1-02{a,b}-5f9aa71` | present for every episode |
| SAM 2.1 ReID head | `$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json` | digest `f6fc67e5…` (pinned per source in S0-03) |
| Instance-mask ReID head | `$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json` | digest `5cea91cf…` |
| Instance-mask grouped heads (for the NoVersion fill-in) | `$AUTODL/vsmt_private/ruling96-7c76970/training/round1/VSMT-lean/A{7,19,31,43,59}/weights_grouped.json` | digests equal `ops/vsmt/ruling97_freeze.json` |
| Instance-mask readings shown alongside | `results/vsmt_lean_ruling96_*_7c76970.json`, `results/vsmt_lean_ruling95_*_d835cd3.json`, `results/vsmt_lean_s2_05_calibration_oracle_850c533.json` | digests equal the inputs of the committed interpretation |

| Stage | What it does | Estimated time (rough; the pilot measures it) |
|---|---|---|
| check | full test suite; all inputs written to the run manifest | about 10 min |
| pilot | the largest SAM 2.1 episode: its calibration job (kept as part of the calibration pass) and one timed TAF audit | 1.5–2.5 h |
| calibration → grid-review → elu-p-fit | ruling-75 calibration pass; the grid review of ruling 100-2 step 2 (judged relative to instance masks per ruling 101 (1)(a); stops if out of grid); ELU-P fit (summed over all development episodes, ruling 101 (2)(a); the first run stops here for the registration commit) | 1.5–2.5 h |
| round0 → train0 → round1 → train1 | round-0 ELU-P records; seed 7 of both learned arms; their round-1 records; 5 seeds per arm (grouped checkpoint selection for VSMT-lean) | 5–7 h |
| audits → instance-noversion | 19 groups × 39 audits on SAM 2.1; NoVersion fill-in on instance masks, 5 × 39 (first checks that the current code reproduces one 7c76970 audit field for field) | 7–10 h |
| merge → reading → verify | merge, interpretation per ruling 100-3, determinism probe, all digests checked, final run manifest | about 30 min |

**Stop conditions.** If the grid review finds a point out of grid, the driver writes a `stopped` marker and waits for a
ruling on grids stored per `mask_source`. Under ruling 101 (1)(a), a point counts as out of grid only if the SAM 2.1
point lies outside the grid on a different side from the instance-mask point; points outside on the same side are
listed for S3-01 and do not stop the run. On the first run, `elu-p-fit` writes a `hold` marker: the three SAM 2.1
fitted values are first registered in S0-05 (pre-authorised by ruling 68 (10), one commit); running `all` on that
commit checks that the refit equals the registered values bit for bit and continues. A run on the final commit does
not stop here.

**Outputs.** `$AUTODL/vsmt_outputs/exports/vsmt_lean_s2_06_*_<tag>.json`, committed to `results/`: input check, pilot,
calibration, grid review, fit, pass exports, 12 training receipts (with per-epoch loss terms), 24 merged audits,
interpretation, run manifest and verify report. Every table value is computed by
[`ops/vsmt/s2_06_reading.py`](../ops/vsmt/s2_06_reading.py) from the merged audits; the reading first recomputes the
instance-mask reading from the committed exports and checks it against the committed interpretation. Weights are not
committed; they stay in `$RUN_ROOT/training/` on the server, with digests in the run manifest.

**Checking a reproduction.** With the same commit and the same `TRAIN_THREADS` (default 4), retrained weights are
bit-identical (verified in ruling 96) and audits are deterministic; `verify` reruns one audit, checks every weight and
receipt digest, and with `REPRO_TRAINING=1` also retrains round-0 AssocOnly and compares digests. Compare your run
manifest with the weight and export digests in `results/vsmt_lean_s2_06_manifest_<tag>.json`.

## 5. S3-02: formal data (ruling 103)

S3-02 generates the formal data from ProcTHOR-10K 0.1.2, the private salt used in S1, the frozen front-end assets and
the reviewed code. Following the three committed lists (train 300, validation 50, test 100; ruling 102-8) it generates
raw episodes, adds the geometry reload, builds the instance-mask and SAM 2.1 caches, and writes a root and receipts
per split. Test is written to separate roots and sealed: until S3-05, every data-reading entry point (training,
selection, audits) refuses a test root. If train yields fewer than 120 executed relocations, the driver stops for a
scale ruling instead of relaxing rules or adding samples. S3-02 does not train or evaluate; for test it computes only
digests and counts.

Run (server with 4 GPUs; free data-disk space of at least the total projected by `check`, about 340 GB; clean detached
worktree of the reviewed commit):

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s3-02-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s3-02-<commit>
nohup bash ops/vsmt/s3_02_data.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-02-<commit>.log 2>&1 &
bash ops/vsmt/s3_02_data.sh status
```

Rerunning `all` resumes; a completed stage refuses reuse if the code changed afterwards (the three files that register
the generator commit, and documentation, are exempt). Stages, reads, writes and stop conditions are listed at the top of
[`ops/vsmt/s3_02_data.sh`](../ops/vsmt/s3_02_data.sh).

| Input (`AUTODL=/root/autodl-tmp`) | Default path | Check before running (`check`) |
|---|---|---|
| ProcTHOR-10K 0.1.2 source | `$AUTODL/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz` | digest and size equal the S1-01 registration (`d64450ec…`, 52,316,238 bytes) |
| Private salt (ruling 37) | `$AUTODL/vsmt_private/null_window_salt.txt` | outside the repository; digest equals the one used by every S1 generation (`8f4eae85…`) |
| Front-end assets | `$AUTODL/vsmt_private/s103_assets.json` | SAM 2.1 and DINOv2 checked byte for byte against the S1-03 contract and the S1-01 registration |
| Both ReID heads (used from S3-03) | `$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json`, `$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json` | digests equal the per-source pins of S0-03 |
| Simulator interpreter | `$AUTODL/vsmt-envs/simulator-py39/bin/python` | imports ai2thor |

| Stage | What it does | Estimated time (rough; measured during the run) |
|---|---|---|
| check | full test suite; inputs, GPUs, cgroup quota and memory, free data-disk space written to the run manifest (the disk requirement is projected for all outputs minus what this run has already written, so a rerun after `hold` on the registration commit requires only the remainder) | about 15 min |
| measure | first 4 train houses, 4 concurrent workers, measured per-worker use (measure root, not part of the S3 data) | about 25 min |
| generate | disk need recomputed from measured bytes; one process pool over 450 houses (worker count derived by the S1-01 rule, simulator concurrency extrapolated from the 16 workers of the confirmation set); ruling-36 check | about 8–9 h |
| hold | the first run stops here: the generator commit is registered in the S1-03 pose registry (registration commit pre-authorised by ruling 103-3); run `all` again on that commit | — |
| geometry | geometry reload of the three splits, 8 simulator workers | about 15 min |
| instance-cache | instance-mask cache, 2 threads per worker, worker count from the cgroup quota and memory, all GPUs, large episodes dispatched first | about 2 h |
| sam2-measure | 1–4 workers on one GPU, picks the per-GPU worker count with the highest throughput and prints the projected total time, then continues; episodes that fail because of the data (e.g. too many fragments) still count and are listed; a level that fails for other reasons (e.g. out of GPU memory) does not count; the stage stops only if no level counts | about 15 min |
| sam2-cache | SAM 2.1 cache, best per-GPU worker count × GPUs | about 20–40 h |
| export → verify | exports (train and validation per house; test counts only), test seal, consistency and seal checks across splits, final run manifest | about 30 min |

**Stop conditions.** `generate` writes `stopped` and stops if train has fewer than 120 relocations or fewer than 60
source-first revisits, pending a scale ruling (ruling 36). The first run writes `hold` and stops at `hold` until the
generator commit is registered. If the generator commit's camera_pose encoding differs from the registered one, `hold`
writes `stopped`: such a commit cannot be registered this way. A cache episode that fails because of the data itself
(e.g. too many SAM 2.1 fragments) is recorded and does not fail the stage; any other failure fails the stage and stops
for inspection, without rerunning or replacing episodes.

**Outputs.** Raw episodes `$AUTODL/vsmt_outputs/s3-02-<tag>/{measure,train,validation,test}`, geometry
`$AUTODL/vsmt_private/s3-02-geometry-<tag>/<split>`, caches `$AUTODL/vsmt_caches/s3-02-{instance,sam2}-<tag>/<split>`;
exports `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_02_*_<tag>.json`, committed to `results/`: input check, measurement,
generation plan, per-house reports for train and validation, geometry and cache reports, test count summary,
worker basis, ruling-36 check, registration record, SAM 2.1 trial, run manifest and verify. The test seal
(`vsmt_lean_s3_02_test_seal_<tag>.json`) stays in the export directory and is released in T0 `exports/`; it is not in
`results/`.

**Benchmark before the formal run** (`ops/vsmt/s3_02_bench.sh`, one RTX 5090, reads the development set only, not a
formal stage): in a clean detached worktree run
`nohup bash ops/vsmt/s3_02_bench.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-02-bench-<commit>.log 2>&1 &`;
all output goes to `/root/autodl-tmp/vsmt_bench/<tag>` and is exported as `vsmt_lean_s3_02_bench_*_<tag>.json`. Seven
steps: check (full tests, GPU and torch, inputs) → compat (generator footprint on 4 houses on this machine) →
sam2-scaling (1–4 SAM 2.1 workers per GPU on the same work) → caches (both caches in sequence and concurrently) →
audit-profile (cProfile of the closed-loop audit) → train-device (memory composition of the training records and one
epoch each on CPU and GPU) → collect. Roughly 3 hours in total and about 6 GB written.

**Checking a reproduction.** On the same commit the generator output for a house is deterministic: `verify` compares
the 4 measured houses byte for byte with the same houses in train and records the result in the run manifest. Caches
are expected to be deterministic per episode on the same GPU model (not verified byte for byte). Compare your run
manifest with `results/vsmt_lean_s3_02_manifest_<tag>.json`; the test seal digest is in
`vsmt_lean_s3_02_test_seal_<tag>.json` (export directory; T0 `exports/`), and S3-05 checks it before reading test.

## 6. S3-03: training and selection readings (ruling 104)

From the S3-02 train and validation data (test roots stay sealed; only their seal markers are read), and under the
frozen method (the recipe of ruling 99-1), grids and selection rules, S3-03 produces: the ELU-P fitted values of both
front ends, round-0 and round-1 trajectories and HeuristicLabel labels, 36 trainings (each recording per-epoch train and
validation loss terms), 208 configuration groups × about 42 validation closed-loop audits (metrics only), and the
selection readings for S3-04. The run is one dependency-driven job pool: a job is dispatched as soon as its inputs
exist, the critical path (fit, trajectories, training) has priority, and audits of the deterministic arms use the
remaining cores.
S3-03 does not select configurations (S3-04 does), does not read test, and does not change the method or the grids.

Run (server, CPU only; S3-02 complete with its exports in `$AUTODL/vsmt_outputs/exports`; clean detached
worktree of the reviewed commit):

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s3-03-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s3-03-<commit>
nohup bash ops/vsmt/s3_03_train_select.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-03-<commit>.log 2>&1 &
bash ops/vsmt/s3_03_train_select.sh status
```

Resuming: rerunning `all` keeps completed jobs. If the code changed afterwards, reuse is refused (registration files of
the ELU-P fitted values and documentation exempt) unless `ACCEPT_CODE_CHANGE=1` is set, which is recorded in the job
state. Jobs that were running at an interruption have their partial output moved to `$RUN_ROOT/interrupted/` before
rerunning; audits keep completed configurations. The choice whether to adopt an existing calibration pass is written to
the run root and reused on every resume (it can be changed before any calibration or adoption job has run; a different
choice afterwards is refused). Failed jobs and jobs whose gate failed are not rerun automatically: the driver stops
before them on resume, and `RETRY_FAILED=1` reruns them after a fix or ruling (partial output moved to
`$RUN_ROOT/failed/`). Only one driver may run per run root (file lock `$RUN_ROOT/.lock`). The job graph and
subcommands are in [`ops/vsmt/s3_03_manifest.py`](../ops/vsmt/s3_03_manifest.py), the dispatch rules in
[`ops/vsmt/s3_03_jobs.py`](../ops/vsmt/s3_03_jobs.py).

| Input (`AUTODL=/root/autodl-tmp`) | Default path | Check before running (`check`) |
|---|---|---|
| S3-02 data | raw episodes `$AUTODL/vsmt_outputs/s3-02-3f6ef1d/{train,validation}`, geometry `$AUTODL/vsmt_private/s3-02-geometry-3f6ef1d/<split>`, caches `$AUTODL/vsmt_caches/s3-02-{instance,sam2}-3f6ef1d/<split>` | the S3-02 run manifest has no problem; every export digest it records matches; per-house raw receipts, per-episode cache seals and geometry receipts equal the exports; counts equal the run manifest |
| S3-02 test seal | `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_02_test_seal_3f6ef1d.json` | each of the four test roots has `TEST_SEALED.json` with state sealed and the digest of this seal (only these four marker files are read) |
| Both ReID heads | `$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json` (SAM 2.1), `$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json` (instance masks) | digests equal the per-source pins of S0-03 |
| Optional: an existing calibration pass (S3 pre-fit) | `ADOPT_CALIBRATION_INSTANCE=<pass root>` | receipts, configuration and source match for every episode, and the smallest episode rerun on this commit is byte-identical in both outputs before adoption |

| Part | What it does |
|---|---|
| check | full test suite; the checks above; the usable train and validation episodes of each front end (in the list, raw, geometry and cache present) written to `$RUN_ROOT/inputs.json` |
| calibration pass → fit | TAF θ_a 0.7 without gate, with histograms and ELU-P counts; the three values fitted on all usable S3 train episodes and written as in-run values (ruling 104-1 1b); a rejected (degenerate) fit stops the run |
| round 0 → gate | ELU-P trajectories under rollout_config plus this front end's fitted values, writing teacher records and HeuristicLabel records together; gate: the HeuristicLabel decision function matches the arm's decisions row by row on ELU-P's own trajectories (G4), and the largest nuisance-probe advantage over the whole split is ≤ 0.05; a failure stops before training |
| training | round 0 of three arms (seed 7, checkpoint selected on the total validation loss) → round-1 trajectories (VSMT-lean and HeuristicLabel with τ_r 0.5, AssocOnly without configuration) → round 1 with 5 seeds per arm (grouped checkpoint selection for VSMT-lean and HeuristicLabel); first 240 houses for training, last 60 for checkpoint selection (104-1 1a); the thread count is chosen during round 0 by measuring 1–4 threads on 20 + 5 houses and fixed for the run; the optimiser uses AdamW's multi-tensor path (bit-identical to the registered path: pinned by the test suite and rechecked on real records by the training-equivalence probe); a training that crashes or runs out of memory is rerun once with the same inputs and seed; divergence is recorded as a result, seeds are not replaced |
| audits | 208 groups on validation: deterministic arms TAF 12, ELU-P 12, RAC 12, LOW 5 and HandCost 12 (ELU-P and others with fitted values); learned arms VSMT-lean, NoVersion and HeuristicLabel with 10 τ_r values × 5 seeds each, AssocOnly × 5 seeds; each job is up to 3 (deterministic arms) or 5 (learned arms) configurations of one arm and one head set on one episode, the cache is verified once per job, metrics only; jobs are not preemptible, so a single job is kept under about half an hour to avoid long low-priority jobs blocking the critical path |
| probes | audit equivalence (a full audit and a metrics-only audit agree field for field on one train episode) before all audits; training equivalence (the registered list path and this run's streaming plus multi-tensor path are bit-identical) before round-0 training; a failure stops the run; finally one audit on a validation episode is rerun to check determinism |
| readings | merge completeness; selection readings per front end (per-metric exclusion lists, house means, seed means, missing seeds noted, AssocOnly reference values); report only: 89-3 ① state coverage, grid positions of both calibration passes (101 (1)(a) reading), label composition |
| export → verify | exports `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_03_*_<tag>.json`; verify requires all jobs finished, all gates passed, and the fitted values registered in S0-05 equal to this run's values bit for bit |

**Registration of the fitted values (ruling 104-1 1b, without stopping).** The run uses its in-run fitted values. The
registration commit replaces the two development-set fitted values in S0-05 in place with this run's values (old values
go to the `SUPERSEDED_VALUES` ledger) and changes only the files listed in `REGISTRATION_FILES` in
`ops/vsmt/s3_03_manifest.py`; it is made locally during the run and pulled to the server after the run ends (a running
checkout is never pulled). Before that pull, `verify` reports `elu_p_values_not_registered` and exits with 3, as
expected; no job is rerun. After pulling the registration commit, run `all` once more: all completed jobs are kept and
`verify` passes.

**Stop conditions.** `check` fails; a fit is rejected or not finite; the round-0 gate fails (a G4 mismatch, or a nuisance
advantage above 0.05: first decompose read-only, then propose a ruling; the threshold is not relaxed); the audit
equivalence, training equivalence or determinism probe differs; any job fails for engineering reasons (training is
first rerun once automatically). On a stop, running jobs finish and no new job is dispatched.

**Outputs.** Run root `$AUTODL/vsmt_private/s3-03-run` (`inputs.json`, `workers.json`, `pool.json`, per-job state and
measured memory in `jobs/`, and per front end `calibration/`, `fit/`, `round0/`, `round1/`, `training/`, `audit/`,
`merged/`, `gates/`, `selection_readings.json`, `coverage.json`); logs in
`$AUTODL/vsmt_outputs/run_logs/s3-03-<tag>/` (one per job); exports committed to `results/`: input check, worker basis,
measured threads and choice, fits and calibration of both front ends, gates and probes, training receipt summaries
(with per-epoch loss terms), selection readings, state coverage, grid positions, job summary, run manifest and verify.
The shell exits 0 when `verify` passes, otherwise with the exit code of the step that stopped (the status JSON
`$AUTODL/vsmt_outputs/exports/s3_03_<tag>.status.json` names the step).

**Checking a reproduction.** With the same commit and `TRAIN_THREADS`, training weights are bit-identical (ruling 96)
and audits are deterministic (determinism probe). Compare your run manifest with
`results/vsmt_lean_s3_03_manifest_<tag>.json` and the selection readings with
`vsmt_lean_s3_03_readings_<front>_<tag>.json`.

## 7. S3-04: freeze after validation (ruling 106)

S3-04 reads the completed S3-03 run root (read only) and its exports and writes a freeze receipt: the single
configuration of every arm per front end, the 25 runs per test episode (one configuration for each of the 5
deterministic arms, i.e. the four rule-based arms and HandCost; 5 seeds for each of the 4 learned arms), the statistics
S3-05 computes, and the fingerprints of every code file (`src/`, `ops/`, `configs/`) and weight file that run on test
day. For example, for VSMT-lean with instance masks, those of the 10 τ_r values whose validation Missing residual rate
is not below AssocOnly's are removed first, and the remaining value with the highest node F1 is chosen. S3-04 does not read test, train or compute the gate; S3-05 unseals test only after the
receipt is committed and pushed and the project owner confirms (106-5).

Preconditions: S3-03 has passed its final verify on the registration commit
(`vsmt_lean_s3_03_verify_<tag>.json` has no problem); the freeze commit already contains the S3-05 entry point
`ops/vsmt/s3_05_test.sh` (106-1 (a): the freeze covers the code S3-05 executes; without the entry point no receipt is
written); a clean detached worktree of the freeze commit on B1.

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s3-04-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s3-04-<commit>
bash ops/vsmt/s3_04_freeze.sh all
bash ops/vsmt/s3_04_freeze.sh status
```

About 30–60 minutes, in the foreground. Rerunning `all` keeps the steps already passed on this commit; a different
commit redoes everything in a new output root. The driver does not power off the host. Exports are pulled back and committed
from another checkout (committing in the freeze worktree changes the commit and starts a new freeze). If only an
operational defect in `ops/` must be fixed before unsealing, set `PREVIOUS_RECEIPT=<old freeze_receipt.json>`: a receipt
is written only if the new selection equals the old receipt bit for bit (106-4 (a)).

| Step | What it does | Pass threshold (otherwise stop, no receipt) |
|---|---|---|
| suite | full test suite | all pass |
| check | G1: S3-03 verify has no problem, exports equal their manifest, the 30 round-1 weight files equal the training receipts, S0-05 registered values equal the run values; G5: the four test roots' seal markers are still sealed with the digest of the S3-02 seal (marker files only) | all equal |
| select (both front ends) | G2: selection readings recomputed with the frozen code from the merged audits, compared value for value with S3-03; G3: the event counts of identity continuity and retrieval success take a single value across all runs; configurations chosen per 102-4; test run list and probe episodes fixed | equal value for value; a single value |
| probe (both front ends) | G4: every selected run (5 seeds for learned arms) rerun on the 2 validation episodes with the fewest frames that have identity events (about 100 small audits, at the largest safe parallelism under the cgroup, with the same single-thread environment as the S3-03 job pool) | bit-identical to the S3-03 audits (wall-clock, commit and head paths excepted) |
| receipt | freeze receipt and exports | all of the above pass, the S3-05 entry point exists, the worktree is clean |
| verify | receipt digest, code and frozen files against the receipt, export digests; run manifest | no problem |

Reported only, with consequences fixed in advance (106-3): arms whose constraint cannot be met (claim boundaries per
102-1 / 102-4), missing seeds (any gate involving them is undecidable in S3-05), selections at a grid edge (the grid is
not changed, 102-6), validation event counts.

**Outputs.** Output root `$AUTODL/vsmt_private/s3-04-<commit>` (JSON of each step, `freeze_receipt.json`,
`<front>/probe/`); exports `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_04_{freeze,check,selection_<front>,probe_<front>,manifest,verify}_<commit>.json`.
Next (106-5): pull the exports, commit them to `results/`, push `main` and `s1-02a-runner`, and unseal test in S3-05
only after the project owner confirms. After the freeze, `src/` and `configs/` do not change; an `ops/`-only fix before
unsealing reruns the whole of S3-04 with `PREVIOUS_RECEIPT` set (see above; 106-4).

## 8. S3-05: one-time test run (ruling 107)

S3-05 runs the frozen arms on test once: it takes the code, configurations and weights pinned by the S3-04 freeze
receipt and the test split, read once, and produces the main table of both front ends, the comparison of VSMT-lean with
every ablation and rule-based arm, the three steps of the fixed-order primary gate, the node-F1 difference with its 90%
interval, the decomposition, size and cost, and per-episode failures. If any file in `src/` changed after the receipt
was committed, `check` stops and test stays sealed. It runs once and tunes nothing.

Preconditions: the S3-04 receipt has been pulled, committed to `results/` and pushed (106-5), and the project owner has
confirmed and given the release key (the first 12 hexadecimal characters of the receipt's `receipt_sha256` field); a
detached worktree on the coordinating server (B1) whose
`src/`, `ops/` and `configs/` equal the freeze commit and whose `results/` contains the receipt.
The receipt fingerprints every tracked file in `src/`, `ops/` and `configs/`, so the code check holds only for the
freeze commit `dea8c20` and the run commit `8d58475` (same code); later commits, `paper-v1` included, add files to
`ops/` (the reanalysis and release scripts) and are reported as different.

```bash
git -C <clone> worktree add --detach /root/autodl-tmp/vsmt_worktrees/s3-05-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s3-05-<commit>
setsid nohup env S3_05_GO=<first 12 characters of receipt_sha256> RECEIPT=/root/autodl-tmp/vsmt_private/s3-04-<freeze commit>/freeze_receipt.json bash ops/vsmt/s3_05_test.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-05.log 2>&1 < /dev/null &
bash ops/vsmt/s3_05_test.sh status
```

| Step | What it does |
|---|---|
| suite | full test suite |
| check | `verify_freeze` against the receipt (code, weights, registered ELU-P values, test list); the receipt is committed in `results/`; the release key equals the first 12 characters of the receipt digest |
| unseal | the S3-02 seal digest equals the one recorded in the receipt; every episode of the four test roots is recomputed and must equal the seal before they are opened; this is read 1, recorded in `TEST_READ.json` next to each root (a resume is the same read; the S3-03 / S3-04 entry points still refuse); the usable test episodes per front end are fixed |
| run | job pool: each job is one run of the receipt on one test episode (node audit, metrics only, `--manifest-split test --test-receipt`; the entry point rechecks that the configuration is the frozen one); a crash is rerun once with the same inputs, a second failure is recorded as a data failure and the run continues; no metric is printed or exported during the run |
| merge → stats | after all jobs, one merge per run, then the statistics computed once per 107-4 (`lean_s3_05`) |
| export | `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_05_*_<commit>.json` and the run manifest |

**Worker hosts (107-3).** Test data can be copied to worker hosts only after unsealing:
`remote_hosts.py setup --run-root $AUTODL/vsmt_private/s3-05-run --name <host> --address <address> --port <port> --kinds test`, with the code worktree synchronised to
the freeze commit. The run copied B1 → w4 and B1 → w5 directly, per the machine revision of ruling 107 (2026-10-07);
the w4 → w1 relay of 107-3 (`--relay-from w4 --relay-key <key on w4 that can log in to w1>`) was not used, and placing
that key on w4 requires the project owner's consent.
`remote_hosts.py admit --run-root $AUTODL/vsmt_private/s3-05-run --name <host> --address <address> --port <port> --kinds test --reference-run-root $AUTODL/vsmt_private/s3-03-run` checks test file by file against the seal on
the worker host (recorded in the read record) and reruns S3-03 validation audits on the freeze commit for a
bit-for-bit comparison (test is not read). The job pool reads `<run root>/hosts/` every 30 seconds.

## 9. LLM-op arm (ruling 105)

LLM-op (registered as an appendix arm; the paper has no appendix and reports it in Table III, outside the test
comparison) asks whether a frozen large language model can perform the memory revision without training. It reads the same
sealed feature tables as the other arms (rendered as tables with headers) and two registered instructions; the model is
DeepSeek `deepseek-flash` (V4.1-Flash as of 2026-10-04) in its default reasoning mode. Each frame asks two questions:
association first (for each fragment, one recalled entity or BIRTH), then, after the solve, existence (RETRACT or NOOP
for each decidable entity). It produces closed-loop metrics for one validation episode per front end (ruling 108;
originally 15), with the same node audit and metrics as the other arms, every call archived, and one export. It does
not train, select, enter the main table or read test; it is independent of the S3-03 job pool and can run on another
machine at the same time.

Preconditions: the two run switches (`pilot_run`, `validation_run`) of the contract
[`configs/vsmt/lean_s3_03_llm_op_v1.json`](../configs/vsmt/lean_s3_03_llm_op_v1.json) are opened by one commit after the
project owner has reviewed the code (until then pilot and formal runs refuse); S3-03 `check` has written `inputs.json` (validation
of both front ends complete); on the LLM-op host (no GPU needed; at least 16 cores, 64 GB RAM and 50 GB data disk
recommended) the operator writes the key file `/root/.config/vsmt/deepseek.env` (one line `DEEPSEEK_API_KEY=...`, mode 600).

```bash
# S3-02 host (read only; clean detached worktree of the reviewed commit)
bash ops/vsmt/llm_op.sh plan                         # draw the validation episode and the pilot episode; writes plan.json and transfer.txt
# with an existing 15-episode plan (before ruling 108): SUPERSEDE_PLAN=1 bash ops/vsmt/llm_op.sh plan; the old plan is kept as plan.superseded.<sha12>.json
SSH_KEY=<private key accepted by the LLM-op host> bash ops/vsmt/llm_op.sh transfer <LLM-op host address> <port>   # copies by absolute path (about 8 GB for 15 episodes; rsync skips existing files)
# LLM-op host (clean checkout of the same commit)
bash ops/vsmt/llm_op.sh test                         # full test suite
bash ops/vsmt/llm_op.sh check                        # recompute cache seals per episode, check receipts, geometry tables and both ReID heads, read the key, query the API
bash ops/vsmt/llm_op.sh pilot                        # 200-frame train pilot per front end; stops with exit 3 at a decision point (archived calls are replayed, not paid again)
nohup bash ops/vsmt/llm_op.sh run > /root/autodl-tmp/vsmt_outputs/run_logs/llm-op.log 2>&1 &
bash ops/vsmt/llm_op.sh status                       # progress, cost, STOP reason; stop with bash ops/vsmt/llm_op.sh stop
bash ops/vsmt/llm_op.sh replay-check                 # replay the shortest episode per front end from the archive; must equal the formal run byte for byte (before export)
bash ops/vsmt/llm_op.sh export                       # results/vsmt_lean_llm_op_<commit>.json
```

| Step | What it does | Stop conditions |
|---|---|---|
| plan | takes, in ascending order of sha256("vsmt-lean-llm-op-105-2\|" + episode ID), the first validation episode usable on both front ends (ruling 108; 105-2 originally took the first 15); the pilot is the first train episode in the same order with at least 200 frames; records seal digests, rows per frame (mean of this front end's S3-03 round-0 ELU-P receipts) and the paths to copy (the pilot copies only the public side and the generation receipts) | the plan is written once (`SUPERSEDE_PLAN=1` replaces only an old plan that differs in episode count, has the same salt string and draw order, and whose formal run has not started; the old plan is renamed and kept); S3-03 inputs record a problem or are still provisional (unless `ALLOW_PROVISIONAL=1`, recorded in the plan) |
| check | the drawn and pilot caches recomputed frame by frame against the plan's seals; raw receipt and geometry-table digests; both ReID heads are the per-source pins of S0-03; the key is readable and the API lists `deepseek-flash`; parallelism set from memory and cores | any mismatch |
| pilot | real API calls on the first 200 frames of the pilot episode per front end, public stage only, no private files, no metrics; tokens, latency, invalid answers and fallbacks, returned model name; projected cost = price per row × full-frame rows (the larger of the registered value and the pilot's) × planned frames, all at peak price (worst case), plus the pilot's own cost; the model name is registered | projection above 30 USD (ruling 108; originally 150); a call type not exercised in the pilot cannot be priced; a call type with a fallback rate above 2%; the two front ends return different model names (after the project owner decides, `ACCEPT_PILOT=1`, recorded in the run record) |
| run | 2 jobs (2 front ends × 1 episode) of the LLM-op formal node audit in parallel (metrics only, validation); archived calls are always replayed and a gap in the archive is refused; rerunning `run` after an interruption resumes from the archive | at 30 USD in the ledger (pilot included) no new job starts (started jobs can still resume); at 40 USD a STOP file is written (ruling 108; originally 150 / 200) and every process stops before its next call (each process also checks the ledger itself, so this holds without the driver); a changed model name or a fatal 4xx writes STOP; a killed or failed driver also writes STOP; after an engineering failure no new job is dispatched |
| replay-check | the shortest episode per front end replayed from the archive only (no API call); trajectory digest and metrics must equal the formal run byte for byte; recorded in `replay/check.json` | any difference: exit 3 |
| export | per-episode metrics and merge, per-front-end call statistics (fallback rate above 2% flagged as "format unreliable"), cost, model name, pilot report, replay check and run record | an unfinished episode; no passed replay check |

**Outputs.** Run root `$AUTODL/vsmt_private/llm-op-run` (`plan.json`, `transfer.txt`, `check.json`, `pilot/`,
`model.json`, `archive/<front>/<episode>.jsonl` with its `.ledger.json`, `audit/<front>/<episode>/LLM-op/node_audit.json`,
`run.json`, `logs/`, possibly `STOP`); exports committed to `results/`. Shell exit codes: 0 done; 2 refused (contract
switch closed, previous step missing, plan or code changed); 3 decision point (projection above the cap, STOP,
unfinished); other values are failures (see `logs/`).

**Checking a reproduction.** Answers of a hosted API cannot be reproduced byte for byte, so reproduction relies on the
archive: `replay-check` reads only the archive and makes no API call; with the same code on the same machine the
trajectory digest and metrics must equal the formal run byte for byte. It must run before `export` (after export writes
to `results/` the checkout is no longer clean and the replayed audit refuses). The paper cites "DeepSeek V4.1-Flash
(API, access date)", with the model name taken from each returned answer. The ledger covers only the archive in this
run root; the actual bill is the DeepSeek console's (off-peak holiday prices are not counted by the ledger, which can
only overestimate).

## 10. S3-07: external check on 3RScan

The external check runs the frozen arms of S3-04 on 3RScan validation (instance masks rendered from the annotated
meshes, i.e. proxy truth; 108 episodes in 46 scenes; reported only, never part of the gate). Its code is on branch
[`s3-07-impl`](https://github.com/JingzeSun/VSMT/tree/s3-07-impl) (`ops/vsmt/s3_07_*.py`), not yet merged into `main`.
Reproducing it requires 3RScan access granted by TUM; no 3RScan data is redistributed. The run used commit `aa94373`
(frozen at `dea8c20`, hosts B1, w4 and w5):

```bash
FRONTS=instance bash ops/vsmt/s3_07_external.sh audit
```

Results: `results/vsmt_lean_s3_07_statistics_aa94373.json` (`fronts.instance.main_table`, `comparisons` with two-sided
90% intervals, `exclusion_lists`, `cache_data_failures`, `fronts_missing`, `not_applicable`); per-episode values in
`results/vsmt_lean_s3_07_merged_instance_aa94373.json`. The SAM 2.1 column cannot be computed with the frozen front end
(3 of 110 episodes usable).

## 11. Full pipeline from ProcTHOR-10K

This section lists what regenerating the paper's data, training and evaluation from ProcTHOR-10K takes. Every stage
reuses its existing driver; nothing here is a new algorithm. Status: the drivers ran in this order for the paper, each
at the commit named below; an outside rerun of the whole chain has not been attempted. The drivers enforce the paper's
private inputs (the salt, the ReID-head digests, the registered generator commits), so an outside rerun must first
make the edits listed under "Outside rerun" in its own clone. `python reproduce/check_env.py --level full
--data-root <root>` checks the host.

**Environment (the paper's runs).**

- Linux; data under `/root/autodl-tmp` (`AUTODL`; the drivers honour the variable, but the generator's disk check and
  the paths recorded in receipts use `/root/autodl-tmp` literally, so make it a link to the data disk).
- Main interpreter (`PY`, default `/root/miniconda3/bin/python3.12`): Python 3.12.3 with torch 2.8.0+cu128 and numpy
  2.3.2 (recorded in each run manifest, e.g. `results/vsmt_lean_s3_02_manifest_3f6ef1d.json`; `uv.lock` pins newer
  versions, so bit identity needs these), plus hydra-core, omegaconf, iopath and the `sam2` package installed from
  the pinned clone (hydra resolves the SAM 2.1 configuration through `pkg://sam2`).
- Simulator interpreter (`SIM_PY`, default `$AUTODL/vsmt-envs/simulator-py39/bin/python`): Python 3.9 with ai2thor 5.0.0
  (CloudRendering; needs Vulkan and downloads the simulator build on first use), the `procthor` package at commit
  `53d5bd4c`, pillow and psutil.
- GPUs: every stage that runs the simulator (S1-02 and S3-02 generation, the S1-04 and S3-02 geometry reloads) needs a
  GPU with Vulkan for CloudRendering, and generation calls `nvidia-smi`; the caches (S1-03, S3-02) and the S1-04
  diagnostics run on CUDA; training, selection and audits (S2, S3-03 to S3-05) are CPU only. The paper used 4 x RTX
  5090, 100 cores and 360 GiB memory for S3-02, and a 32-core host with remote workers (`ops/vsmt/remote_hosts.py`) for
  S3-03 and S3-05.
- Disk: S3-02 alone projected 346.5 GB (`results/vsmt_lean_s3_02_disk_3f6ef1d.json`); with the development episodes
  (about 13 GB), the S1 caches (about 20 GB) and the S3-03 and S3-05 run roots (about 28 GiB, the size of T2), the whole
  chain on one disk needs about 410 GB (the paper's host had 470 GB).
- `git`, `flock`, `nvidia-smi`; every stage runs in a clean, detached worktree (untracked files count as changes).

**Assets** (pinned in `configs/vsmt/lean_s1_assets_capacity_v2.json` and the S1-03 contract; each checked by digest).
`$ASSETS_JSON` is a flat JSON object mapping `sam2_repository`, `sam2_checkpoint`, `dinov2_repository`,
`dinov2_vits14_checkpoint` and `dinov2_vitb14_checkpoint` to local paths; the repositories must be clean clones at the
pinned commits.

| Asset | Pin | Where the drivers look |
|---|---|---|
| ProcTHOR-10K 0.1.2 `train.jsonl.gz` | Git LFS repository `github.com/allenai/procthor-10k` at `d54954a8`, 52,316,238 bytes, SHA-256 `d64450ec…` | `$SOURCE` (`$AUTODL/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz`) |
| SAM 2.1 Hiera Small | repository `2b90b9f5` (clean clone), checkpoint `https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt` (`6d1aa6f3…`) | `$ASSETS_JSON`: `sam2_repository`, `sam2_checkpoint` |
| DINOv2 | repository `7764ea0f` (clean clone); ViT-B/14 `https://dl.fbaipublicfiles.com/dinov2/dinov2_vitb14/dinov2_vitb14_pretrain.pth` (`0b8b82f8…`); ViT-S/14 pinned by digest only (`b938bf1b…`; the official `…/dinov2_vits14/dinov2_vits14_pretrain.pth` has the same size, 88,283,115 bytes) | `$ASSETS_JSON`: `dinov2_repository`, `dinov2_vits14_checkpoint`, `dinov2_vitb14_checkpoint` |
| ReID heads | SAM 2.1 `f6fc67e5…` (released in T0 `reid/`); instance masks `5cea91cf…` (not released) | `$SAM2_REID`, `$INSTANCE_REID` |
| Private salt of ruling 37 | SHA-256 `8f4eae85…`; not released | `$SALT_FILE` (outside the repository) |

**Stages.** Run each in a clean worktree (`git worktree add --detach <path> <commit>`); "paper run" names the commit
or output tag of the paper's run.

| Stage | Command (main interpreter unless noted) | Paper run | Duration |
|---|---|---|---|
| S1-02 development episodes | `$SIM_PY ops/vsmt/lean_s1_02a_pilot.py --stage s1-02a --output-root <A> --source $SOURCE --private-salt-file $SALT_FILE`; then `--stage s1-02b --output-root <B> --pilot-root <A>` with the same source and salt; `ops/vsmt/lean_s1_02b_export.py --output-root <B> --out <export>` | `5f9aa71` | not recorded here |
| S1-03 caches | `ops/vsmt/lean_s1_03_cache.py --episode-roots <A>,<B> --output-root <C> --assets-json $ASSETS_JSON --mask-source sam2 --workers N --worker-basis "<evidence>"` (again with `simulator_instance_masks`); `ops/vsmt/lean_s1_03_export.py --cache-root <C> --out <export>` | caches `154776d` (SAM 2.1), `oracle-8ebbd05` (instance) | about 20 h at 2 workers (SAM 2.1) |
| S1-04 geometry, diagnostics, ReID heads | `$SIM_PY ops/vsmt/lean_s1_04_object_geometry.py --episode-roots <A>,<B> --source $SOURCE --output-root <G> --workers N`; `ops/vsmt/lean_s1_04_diagnostics.py --cache-root <C> --episode-roots <A>,<B> --geometry-root <G> --output-root <D> --workers N --reid` (CUDA by default) | `154776d`, `caa50c7` | not recorded here |
| S1-05 descriptor choice | `ops/vsmt/lean_s1_05_select_descriptor.py --s1-04-report <D report> --out <file>`; its other defaults read the paper's S1-02, S1-03 and ruling-56 exports, so pass a rerun's own (the ruling-56
estimate's script is not in the tree; its source is embedded in the export, field `script_source`) | `154776d`, `caa50c7` | seconds |
| S2 development tables | not part of the chain: S2 informed rulings and none of its outputs is an S3 input; S2-06 ran at `c0b166e` and `dffc36d` and reads development run roots of rulings 95 and 96 that are not released, and at `paper-v1` its ELU-P refit stops (S0-05 holds the S3-03 values) | `c0b166e` | about 16–23 h |
| S3-01 lists and planning | `ops/vsmt/s3_01_manifests.py` (rewrites `configs/vsmt/lean_s3_01_manifests.json`; reproduces it byte for byte); `ops/vsmt/s3_01_planning.py --output <file>` | `6c57903` | minutes |
| S3-02 formal data | `bash ops/vsmt/s3_02_data.sh all` (section 5; reads `PY`, `SIM_PY`, `AUTODL`, `SOURCE`, `SALT_FILE`, `ASSETS_JSON`, `SAM2_REID`, `INSTANCE_REID`) | `3f6ef1d` | about 28 h |
| S3-03 training and selection readings | `S3_02_TAG=<your S3-02 tag> bash ops/vsmt/s3_03_train_select.sh all` (section 6; the default tag is the paper's `3f6ef1d`; the training thread count is measured in round 0 and has no override; the paper's run chose 1, `results/vsmt_lean_s3_03_train_threads_10f7013.json`) | `10f7013`, registration `5a9fd94` | about 2.7 days on 32 cores plus remote workers |
| S3-04 freeze | `S3_03_TAG=<your S3-03 tag> bash ops/vsmt/s3_04_freeze.sh all` (section 7; default `10f7013`) | `dea8c20` | 30–60 min |
| S3-05 test, once | `S3_02_TAG=<tag> S3_05_GO=<first 12 hexadecimal characters of the receipt's receipt_sha256 field> RECEIPT=<freeze_receipt.json> bash ops/vsmt/s3_05_test.sh all` (section 8) | `8d58475` | about 22 h on about 100 cores |

S3-06 (`ops/vsmt/s3_06_reanalysis.py`, `reproduce/paper.py`) recomputes this repository's exports only: its input tags
are fixed and it requires `src/` and `configs/` to equal `dea8c20`. A rerun's test statistics are the `stats` step of
its own S3-05.

**Outside rerun.** The edits below, made in the rerun's own clone and committed in this order, let the chain run
without the paper's private inputs; each changes `ops/`, `configs/`, `src/` or `tests/`, so the rerun's freeze is its
own and this repository's `paper-v1` is not affected.

1. Salt. Write a new salt (at least 32 characters) to a file outside the repository and set `S3_SALT_SHA256` in
   `ops/vsmt/lean_s1_02a_pilot.py` to its SHA-256; S1-02 records the salt's digest, and S3-02 `generate` and `check`
   refuse any salt other than the registered one. The no-change draw, and with it every episode, then differs from
   the released data.
2. Generator commit. Before S1-03, add the S1-02 generator commit to `public_pose_correction.correct_encoder_since_code_commits`
   in `configs/vsmt/lean_s1_03_frontend_cache_v1.json` (episodes from an unlisted commit are refused by S1-03 and S1-04);
   S3-02 stops at `hold` for the same registration of its own generator commit (section 5). The same commit updates
   `tests/test_vsmt_lean_cross_contract.py` and `tests/test_vsmt_lean_public_pose.py`, which pin the contract (the
   `REGISTRATION_FILES` of `ops/vsmt/s3_02_manifest.py`).
3. ReID heads. Train both heads in S1-04, run S1-05, and commit the rerun's S1-04 reports and S1-05 receipts to
   `results/`. Then re-pin the heads' payload digests (`sha256` inside the weights file) in
   `src/vsmt/lean_assignment.py` (`SELECTED_REID_WEIGHTS_SHA256`, `REID_WEIGHTS_SHA256_BY_MASK_SOURCE`),
   `configs/vsmt/lean_s0_assignment_v2.json` (rewriting `reid_adapter_head.selection_result` with its
   `heads_by_mask_source` receipts, input reports and their digests, gains and superseded digests),
   `configs/vsmt/lean_s2_01_runner_v1.json` and `tests/test_vsmt_lean_s2_01_entry.py`, and update the S0-03 and S2-01
   rule digests in `FROZEN_RULE_SHA256` of `tests/test_vsmt_lean_cross_contract.py`, whose tests check the selection
   against the committed reports. Every stage runs the full test suite first, so an incomplete re-pin stops it. Without
   the instance-mask head, S3-02 `check` refuses.
4. ELU-P values. After S3-03, register the refitted values in S0-05 as described in section 6.

**Other limits.** Starting from the released T3 instead of S3-02 is not supported by the S3-03 driver (sealed test
markers, [section 1](#1-reproduction-levels-and-determinism)). The drivers were written for the AutoDL hosts: worker
hosts are configured through `ops/vsmt/remote_hosts.py` and the S3-03 pool sizes itself from cgroup limits.
