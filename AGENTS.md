# Project Instructions

## Current direction (D-224; takes precedence over the historical directions below)

- On 2026-09-19 the user approved D-224 rulings A to D: the first paper is narrowed to **VSMT-lean (versioned entity-lifecycle transactions)**.
  - Model: a frozen public front end (ruling 72: main-table fragments come from simulator instance segmentation and expose only mask geometry, with SAM 2.1 demoted to a robustness appendix; from ruling 83-3 on, SAM 2.1 is promoted to a second full main table, planned) + RGB-D geometry + DINOv2; three MLP cost heads with 54,207 parameters in total (originally stated as about 40,000; ruling 63 corrected the number; the recipe frozen by ruling 99 has 54,787, see docs/METHOD.md); one rectangular Hungarian assignment per frame.
  - Data: ProcTHOR multi-house full-coverage revisits plus unobserved-window interventions.
  - Metrics: aligned with Dyn-THOR. Node P/R/F1 uses "same identity, and centroid ≤ δ_moved or inside the ground-truth box expanded by 0.25 m" as the primary column and the configuration-selection metric (ruling 77 added the identity and box tests to the centroid criterion of ruling 72 (B)); IoU 0.3 is the secondary column `node_prf1_iou` (ruling 72 (B) switched ruling 70 to option (b)). Neither column enters the primary gate; both use the same matching mechanism as Dyn-THOR with a different overlap test.
- Five atomic operations: NOOP/BIND/BIRTH/RETRACT/REACTIVATE. REPLACE is a composite program. MERGE is a deterministic de-duplication shared by all five methods. SPLIT, RELINK, place, surface, relation edges, the type gate, post-state encoding and NECS are all out of the first paper.
- Main comparison: VSMT-lean / TAF / ELU-P / RAC / LOW. Four ablations: NoVersion / HandCost / HeuristicLabel / **AssocOnly**. AssocOnly (the same learned association head, with a vocabulary of only BIND and BIRTH) is the only causal counterfactual for contribution one and **must be reported side by side in the main table**. `LLM-op` is a mandatory appendix arm, run only on validation; it enters neither the main table nor test. `VSMT-lean-ctx` is an optional arm. At most 12 full configurations per method; rule-based arms have no gradient.
- The S2-05 development table also runs `NoVersion` and `AssocOnly` as early risk readings. Development differences must not be used to pick a winner, tune the grid or drop ablations, but they may prompt a design revision (ruling 66, 2026-09-24): the revision must be registered as a ruling, completed before S3-01 freezes the formal data, and must not read validation/test.
- The teacher uses private instance ground truth at time t. The recall set and feature matrix are sealed before any private file is opened. `recall_miss`, `teacher_error` and `amortization_error` are recorded separately.
- Documents of earlier directions are archived on branch `archive/pre-d224-unified-graph`. METHOD/PLAN/DATA on `main` contain only the lean version; remove superseded text before adding new text. Old source code stays in the tree, is not deleted, and is not part of the current entry points.
- Status (2026-09-28): all S0 contracts have been reviewed; S1 and S2 are complete (S2-05 development table LOG-270, seven arms, 39/39). Rulings 79 to 82 are approved.
  - Ruling 81 removes "revise only once" and replaces it with development revisions bounded by scope, budget and stop conditions, and freezes the confirmation-set list (LOG-275).
  - Ruling 82 first measures training variation over 5 seeds, because a single training run can flip the order of two arms (LOG-276/277).
  - S3 is paused until the revisions converge and are checked on the confirmation set. The current execution point is maintained only in docs/PLAN.md.
- 2026-09-29: ruling 83 approved (LOG-278, documents only). The configuration-selection constraints and the eighth item, retrieval success, are frozen before S3-01; direction B is the revision round under 81-1; SAM 2.1 is promoted to a second full main table; a new S3-07 external validation is added (3RScan preferred); target venue per ruling 83-6 (see docs/DECISIONS.md).
- Same day: ruling 84 approved. 84-1 takes (b): the ReID head is pinned once per `mask_source`. The rest follow the recommendations: a SAM2 calibration pass; a new S2-06 SAM2 development table; the S3 SAM2 cache budget set by multi-GPU measurement; the disk expanded to ≥300 GB before S3-02; the mask-layer revision deferred; S3-02 run on a multi-GPU RTX 5090-class host. The 82-1 seed study was stopped before its receipt so that the instance could be cloned, and is re-run after cloning.
- 2026-09-29: ruling 88 approved. From then on, every stage first registers and passes its own mechanism checks (decision upper bound, label consistency, imitation sufficiency, state coverage, open-loop/closed-loop gap, critical-event budget), with pass thresholds frozen before the run, so that a failing mechanism is no longer discovered only at the development table. The revision rounds of ruling 81 are settled under the original rules once ruling 87 produces its numbers; later changes go into the S2-R redesign track. Existence labels are aligned with the node primary column. Tier B of ruling 87 is not used as evidence of reversibility.
- D-059's single-responsibility scientific commits, user code review and server rules remain in force.
- 2026-10-02: the S2-06 SAM 2.1 development table is complete (LOG-300). Ruling 102 (the S3-01 freeze draft, second revision, all items as recommended) is approved and implemented, pending the user's code review: identity continuity is computed on the same set of events for all arms; the primary gate is the two-level bootstrap of VSMT-lean against AssocOnly plus 82-1, testing the two front ends in a fixed order; the configuration-selection constraints; the eighth item, retrieval success; the S3 list takes train positions 100 to 399.
- 2026-10-02: S3-01 is closed (LOG-301). Ruling 103 (the S3-02 stage protocol) is approved and implemented, pending the user's code review: test sealing and read-entry guards, an S3 stage in the generator, multi-GPU cache, and a one-command driver `ops/vsmt/s3_02_data.sh`. Extrapolating from the S1 report, S3-02 writes about 337 GB to disk.

## Previous direction (D-122; superseded by D-224, kept only for auditing old code and old runs)

- On 2026-09-13, following the supervisor's advice, the user switched the first paper's priority back to structural memory revision. The old S5 no-go stands; the shortfall of the original A against C is not rewritten as a success.
- Proposed method name: Versioned Structural Memory Transactions (VSMT). It handles nodes, relations, evidence, lifecycles and structural extension, and is not limited to object lifecycles.
- The first paper's candidate core contribution is fixed as the combination "typed executable transactions + versioned state/side-effect audit + candidate-before-teacher learning boundary". DINOv2, the scene graph, the deterministic executor, the names of the eight atoms and storing historical bytes must not individually be presented as novelties.
- Keep the eight atomic templates NOOP, BIND, BIRTH, REACTIVATE, RELINK, RETRACT, SPLIT, MERGE; REPLACE remains the composite program RETRACT+BIRTH. Transactions on their own are not claimed as a first proposal.
- The first paper's main comparison becomes: VSMT, paper-mechanism adapters that can be implemented independently on the same public input/state/output interface, and one naive baseline. The old A/C/E may appear only as training-mechanism ablations within the new contract and no longer carry the sole claim.
- Paper-mechanism adapters draw only on the mechanisms of published papers and state the citation, the differences and their status as unofficial reproductions; they do not copy upstream source code, class names, default configurations or text. If official code is run later, it must be registered as a separate reproduction route with its license, commit, original settings and task adaptation.
- The old `proposal_observation.node_query/edge_query/place_query/merge_queries` carry the risk of a reference-identity shortcut derived from `reference_spec` parameters and must not be reused in new data or main experiments. Every deployment query must be computed online from the current public observation and the previously predicted memory.
- The candidate set must be generated and sealed before the teacher, the future, the reference transaction and private ground truth become visible. The teacher may only assign training labels to existing candidates and must not insert, delete, reorder or patch candidates. A missing correct candidate counts as a candidate miss.
- Semantic equivalences such as BIND/BIRTH, REACTIVATE/BIRTH, RELINK/REPLACE and SPLIT/MERGE, and metric weights, are ruled on by the user. The implementer must first present positive and negative cases that separate the boundary, the candidate options and their effect on results, and must not silently write a semantic answer into the information-safety contract.
- New data must be regenerated, with public physical/visual inputs and private supervision in separate files and separate readers. Simulator instance IDs, ground-truth masks, reference transactions, future observations and actual future states must not enter deployment inputs or candidate generation.
- The old C00–C11 serve only as symbolic-execution/semantic-boundary regressions. The old LATENT consists of symbolic IDs, synthetic cues and reference-derived queries and must not enter the VSMT main experiments. In the main table VSMT/TAF/ELU/WFR/LOW must share one frozen RGB-D front end; oracle structured is only a separate-column mechanism diagnostic.
- Only the literature and old-implementation audit, the method/data/anti-cheating contracts and a separate branch are approved. The concrete data split, generation budget, model budget, confirmation set and effect runs must still be frozen, before and after the user's code review respectively.
- D-059's single-responsibility scientific commits, user code review and server rules remain in force. Old code, results, source materials, the D-062 spatial world model branch and reproduction paths are kept.

## Previous direction (D-062; paused but preserved)

- On 2026-09-11 the user explicitly authorized the switch from memory revision to a spatial world model and the start of execution. The workspace may be restructured when necessary, but old code, results, source materials and reproduction paths are kept.
- Candidate question: whether, when recent observations are identical but earlier history reveals different structure in occluded regions, a model can predict the different out-of-view interaction consequences of the same robot control command, and improve the selection among fixed candidate actions.
- First test reproducible failures of existing methods. Do not presuppose that a persistent three-dimensional state, dynamics prediction or their combination is novel, and do not bind to CTL in advance.
- This round allows comparing the consequences of fixed candidate control sequences. It does not cover active exploration policies, open-world settings, complex manipulation, language interfaces or high-quality video generation.
- The main data/model controls must include a long-history predictor, history retrieval, and a map with simple dynamics. Beating only short-history models that lack sufficient information does not support a new mechanism.
- Distinguish robot control commands, planned motion computed from robot kinematics, actual motion after execution, and future object transforms. The last two must not be disguised as deployable action inputs.
- The first batch is an independent paired-data contract and input boundary, defined in METHOD/DATA. Hand-made fixtures are not evidence about the simulator, physical correctness or model failure.
- D-059's single-responsibility scientific commits, user code review and server-run rules remain in force. This authorization to start does not approve unreviewed modules as baselines. New train/test splits, training budgets and mechanisms must still be registered concretely first.
- Old and new experimental protocols apply separately: the old test stays sealed and the old no-go is not rewritten. New modules need not implement the old transaction operations or the six energy terms, and old test receipts cannot certify new code.

## Historical CPMT direction (only for auditing old code and old runs)

- The full method is Counterfactual Projective Memory Transactions (CPMT).
- The core learning mechanism is Counterfactual Transaction Learning (CTL).
- The research object is always embodied spatial memory; the first paper does not generalize to a second task domain.
- Projective Node Orbit is the fixed/lightweight representation basis; Versioned Deterministic Executor is the necessary execution basis.
- The sole claim: whether post-edit executable hindsight supervision can learn online world-memory revision that is more reliable than direct future loss.

## Historical CPMT first-paper scope

Allowed:

- fixed backbone, depth, pose and region proposals;
- NOOP, BIND, BIRTH, REACTIVATE, RELINK, RETRACT, SPLIT, MERGE;
- REPLACE as the composite program RETRACT+BIRTH;
- deterministic QUARANTINE as a low-confidence wrapper;
- controlled, embodied and one external/real-world validation across M0–M3.

Must not be added without authorization:

- an active disambiguation/action policy;
- a second, non-embodied application domain;
- a learned candidate generator;
- an end-to-end foundation backbone;
- large-scale navigation or language tasks;
- calling the executor, the KL loss or transaction labels a novelty on their own.

## Non-negotiable hard conditions for old CPMT runs

- All candidates are cloned from the same immutable base version and actually executed.
- Energy must record now, future, edit, growth, collateral and illegal separately.
- The hindsight posterior is formed from the post-execution world; online inference must not read the future.
- direct+future-loss and future-scorer-without-execution are mandatory main controls.
- SPLIT/MERGE/RETRACT must have executable positive examples, but may serve as a combined stress test rather than three parallel research directions.
- RETRACT closes a version and does not physically delete provenance.
- QUARANTINE does not modify the persistent world.

## Old CPMT execution order (the current pointer has been superseded by D-122/D-125)

1. M0: contracts, executor, oracle fixtures;
2. M1: hard-condition go/no-go;
3. M2: visual online/self-rollout with a fixed perception front end;
4. M3: one external/real-world source, the paper and the artifact.

If M1 fails, stop scaling the model; do not look for positive results by adding representations or tasks.

The exception for the user's explicit change of direction on 2026-09-11 is recorded in docs/DECISIONS.md D-058: the M1 no-go and the test seal are kept, and M2 public-observation integration may proceed independently; neither the integration nor new-stage results count as passing the old M1. Concrete training still requires fixing the new stage's method, data and budget first; scaling the model according to results is not authorized.

D-059 further authorizes reviewing real data first and then fully rebuilding a new-protocol M1; the full plan and the current pointer are maintained only in docs/PLAN.md. The user explicitly requires gatekeeping of code: scientific changes are delivered as readable single-responsibility commits with input/output examples and the necessary server tests, and are merged into a new scientific baseline, or used by the effect experiments that depend on them, only after the user has reviewed them; no further scientific code is stacked on unreviewed modules. The old M1 negative result and its artifacts are kept; delivering the current plan does not automatically freeze later scientific contracts/budgets.

## Old CPMT implementation and experiments

- candidates, executor, projection, hindsight and online must be replaceable, with errors recorded separately.
- The executor is gradient-free, deterministic and versioned, and checks preconditions, protected state, invariants, provenance, idempotency and atomic rollback.
- Formal runs save config, seed, data/code hash, front-end IDs, future-use policy, per-candidate energies, per-example metrics and complete failures.
- Paired groups do not cross splits; test is not used to tune thresholds, choose prompts, filter methods or choose checkpoints.
- Results must distinguish candidate miss, teacher error and amortization error.

## Server terminal command delivery rules (mandatory across conversations)

- Default: one delivery per stage, one sync, then run step by step. Once a stage's method and input contract are settled, prepare in advance the entry points it needs for testing, generation, checks, training, evaluation, acceptance and export, run appropriate checks, and commit/push. The user syncs once at the start of the stage and then runs the existing commands; do not repeatedly change scripts or ask for a pull to switch steps. A stage is a settled, ordered set of work; it does not require implementing the whole M1 or an unsettled next milestone in advance. Stage delivery is not a one-click pipeline that ignores failures, and it does not change the experimental method, the statistical protocol, test sealing or running tasks.
- `ops/run_next_server_step.sh` is no longer mandatory as the only entry point, and a version is no longer limited to one functional step. Several function-named scripts under a stable `ops/<stage>/`, or named subcommands of a stage script, are allowed; simple tasks may call the formal runner directly, without adding a wrapper only for uniformity. Existing entry points stay for compatibility and history; running tasks are not forced to migrate or restart.
- Later steps may be written in advance, but a step whose conditions are not met must not be executed. Each step states its step ID, input preconditions, read/write boundary, resume policy, output path and success marker, and automatically verifies the markers, manifests, digests and registrations it depends on before running. Frozen mechanical rules may consume earlier steps' results automatically; a new scientific decision or an unauthorized test unseal still requires a pause and must not be bypassed by a pre-written script.
- Deliver short commands and continuation conditions in order. Split environment/version checks, tests, generation, checks, training, evaluation, export and Git wrap-up into blocks by function; do not paste script bodies or overlong commands that run from tests to push. When the user asks for the commands one at a time, send only the current step; later steps keep using the same delivered version, with no new commit just to send the next command.
- Update the version and sync again only for a bug that must be fixed, a change of scientific code/config/contract, or a genuinely needed new capability; a running checkout is not pulled. Operations scripts go in `ops/` and do not duplicate experiment algorithms. Changes to the formal runner, config or contracts still follow the existing test, decision and re-freeze rules and must not borrow old test markers.
- Tasks that succeeded and have manifest/digest/exit evidence are reused; they are not re-run by default because of a reconnect, a step switch or a documentation update. Verify artifacts first and continue from the earliest missing step. Keep the state of failed/interrupted tasks as it is; silent re-runs, overwriting or replacing samples are forbidden. Start a dependent step only after each computation has finished and saved its exit evidence; do not ask again whether to continue after every success.
- For a pure Git wrap-up, give exactly three commands: `git add -- results/file.json ...`, `git commit -m ...`, `git push origin main`. Do not change scripts, create a handoff, or make a commit that only carries commit commands in order to commit artifacts. List several accepted reports from the same batch path by path; do not wildcard the whole `results/`.
- Foreground or background is decided by expected duration, not by task type. Checks, tests, speed measurements, data generation, training and similar tasks expected to take no more than 30 minutes run in the foreground by default, showing progress, results and exit status directly, optionally also saving a log; only tasks expected to take more than 30 minutes run in the background by default. When the duration is unknown, do not apply the background template automatically; when the user specifies, follow the user. A short task must not require checking a separate log or re-running the entry point to see its result. This rule does not require interrupting or restarting background tasks that are already running.
- Server data generation, hyperparameter search/tuning, training, validation, testing, checks and audits must use multiple workers whenever there are two or more independently executable work units; they must not default to serial execution or be fixed at a small worker count without checking resources. Before running, choose the largest safe worker count at that time from the available CPU cores, GPU count and GPU memory, RAM, I/O, simulator concurrency safety and the measured footprint of a single worker. Single-GPU training must at least parallelize data loading or other safely shardable parts, and must not launch several training processes merely to satisfy this rule when they would compete for GPU memory, reduce throughput or change numerical semantics. The entry point must record the requested/actual worker counts, the resource basis, the task sharding, exit status and a deterministic merge order. A single worker is allowed only when the task is inherently serial or an upstream component has been shown by measurement not to support concurrency, and the reason, evidence and expected time must be stated before launch; do not discover after a long run that the entry point is serial. Tasks already running are not interrupted automatically because of this rule; whether to stop and restart them remains the user's explicit decision.
- Formal server generation, tuning, training, validation, testing, checks and audits must not be force-failed because a preset wall-clock limit is reached; a task may run as long as it needs, and when it is expected to take more than 30 minutes it moves to the background under the existing rule and keeps saving progress, exit and resume evidence. Safety guards on RAM, GPU memory, free disk space and runaway processes must still be kept, to avoid crashing the machine, filling the data disk or damaging other artifacts; these safety lines must not be disguised as a shorter compute-time budget. If paper experiments need compute budgets for statistics, record only the actual usage, or separately freeze training steps/sample counts for fair comparison; do not cut legitimate tasks with a wall-clock timeout.
- Do not set `set -e` in the user's interactive parent shell. If a block really needs fail-fast, put it only in a `bash -c` subshell, so that a failure returns to the current terminal instead of closing the window. Each heavy block shows or saves its exit status, and the next block states its continuation condition.
- Shell variables must not use Bash/system special names such as `GROUPS`, `SECONDS`, `RANDOM`, `PWD`, `HOME`; use task-specific names such as `TRAIN_GROUPS`, `SCORER_STEPS`, `CPMT_RUN_DIR`. Check that variables hold the expected values before generating commands.
- Do not guess the remote repository path or its spelling from the shell prompt, a web file tree or the local directory. On first connection or after a rebuild, obtain the machine's actual path with `pwd -P`, `find ... -name .git` or `git rev-parse --show-toplevel` and reuse it verbatim. The spelling `Emboddied` in this repository's remote name must not be corrected.
- `outputs/` holds large server artifacts and is not in Git by default. For local analysis, first use the repository's exporter to produce `results/*.json` with manifest/provenance, then, under the pure Git wrap-up exception, give add/commit/push with exact paths; the user pulls locally and reads them. Do not misreport "no exported report" as "no arrays generated".
- Before deleting, moving or rebuilding a server directory, first resolve it read-only and show the exact target; do not delete without the user's explicit request. Even when the user has explicitly asked for a deletion, avoid wildcards and guessed paths, and state whether uncommitted `outputs` would be lost.

## Decisions that need the user

- Whenever the next step needs the user's approval, ruling or freeze, the final reply must list directly in the reply body: the pending item, the recommended option, the other options, the effect of each on results/resources/claims, and a short approval sentence the user can copy and send back. Do not give only file links or ask the user to search the documents; file links serve only as evidence. If nothing in this round needs the user's decision, say so explicitly with the phrase `本轮无需裁决` ("no ruling needed this round").

## Codex model and reasoning-depth recommendation

- The final reply of every task, responsibility batch or server-step delivery ends with a separate line `下一任务建议：<model> / <reasoning depth> — <one-sentence reason>` (the Chinese prefix means "next-task recommendation" and is kept literally). Choose by the scientific risk, semantic uncertainty and verifiability of the next piece of work, not mechanically by line count or task name; if there is no definite next task, write `暂无` ("none for now"). The recommendation only helps the user switch models; it does not mean that the next stage has authorization to run, train, download, confirm or merge.
- GPT-6 Astra High is the default for research questions, input/label boundaries, fairness of controls, failure attribution, and complex scientific development and review spanning METHOD/DATA/PLAN. Use this tier even when the code is short but could change a research conclusion.
- GPT-6 Astra Ultra is reserved for final protocol freezes, audits before launching expensive experiments, critical reviews of whether evidence supports a claim, and tasks where the user explicitly asks for several independent lines of evidence or parallel agent review. Ultra is not the default for everyday small fixes.
- GPT-5.6 Sol High is for implementing well-bounded modules from a reviewed specification, adding necessary tests, general fault localization and server engineering checks. As soon as it finds that a change would alter data, inputs, labels, scoring, thresholds, splits or budgets, it stops modifying on its own and recommends switching back to Astra High for deliberation.
- GPT-5.6 Sol Medium is for paths, logs, commands, Git wrap-up and low-risk fixes that are already localized. Sol Ultra is an option only when the plan is already clear, the task genuinely splits into several independent implementations/read-only checks, and the user allows parallel work; it is not enabled by default for the sake of being "more rigorous".
- Recommend the exact model names and reasoning depths actually selectable in the current Codex interface. If a listed tier is unavailable, name the closest available substitute and do not claim a switch that did not happen. Scientific deliberation and engineering execution may be split into two rounds: Astra High settles/reviews the semantics, Sol High implements the frozen rules, and, when needed, Astra High checks that the implementation did not change the scientific meaning.

## File roles and protection

- README.md is the public entry point: overview, results summary, installation, data and weights, citation.
- docs/REPRODUCE.md holds the stage-by-stage reproduction commands: S2-06, S3-02 to S3-05, the S3-05R release and download, LLM-op, and the paper results index.
- Working rules live in this file; the full plan, the stages and the current pointer only in docs/PLAN.md; the method and its terminology only in docs/METHOD.md; data sources/fields only in docs/DATA.md.
- Experimental results, substantive architecture changes, failures that must be kept and claim evidence go only into EXECUTE.md; its top dashboard may be updated. Important method/budget/process changes are appended to docs/DECISIONS.md; ordinary discussion does not create a LOG entry or decision for every round.
- A new conversation first reads the current pointer in docs/PLAN.md, then the EXECUTE dashboard and the latest LOG. Do not create separate handoff, STATUS, TODO, weekly-report, confirmation-table or glossary files; the exception is a standalone external deliverable the user needs.
- D-060 reorganized the documents and deleted duplicates at the user's explicit request; the old detailed contracts, confirmation tables, templates and the copies of the two proposals are available in the Git history at c24ced2, and no archive copy is re-created. Old M1 contract/result snapshots and historical code notes that still exist represent only their version at the time and do not override the new plan.
- docs/source/full_technical_vision.txt, the original prototype figures/PDF, notes.txt, paper PDFs and other source materials are not overwritten or deleted; literature notes are kept. Cleaning up scientific source code, schemas, configs, fixtures, run results and server outputs requires checking reproduction dependencies first.
- Completed runs are reused under their original code/data/config hashes; new code must not borrow old receipts. Source hashes may include READMEs inside src/scripts/tests, so these bytes must not be changed casually while tidying documentation.
- New scientific code is delivered one responsibility at a time as reviewable commits with concrete inputs/outputs and the necessary server tests, and is merged into a new scientific baseline or used by dependent effect experiments only after the user has reviewed it. Passing tests does not mean the method is effective.
- Unimplemented content is marked planned. Data, weights and per-example machine results are stored according to engineering responsibility, not stuffed into Markdown, and no progress file is added per conversation.

## Documentation language

- Project documentation (README.md, docs/, paper/README.md, and new EXECUTE.md and docs/DECISIONS.md entries) is written in English. EXECUTE.md and docs/DECISIONS.md entries written before 2026-10-09 stay in Chinese as historical records and are not translated or edited. Verbatim user quotes stay in the original language. In this repository this replaces the workspace-level rule that documentation is mainly in Chinese.
- Replies to the user in the conversation are written in Chinese, with identifiers in English.
- Documentation is concise and technical: define every abbreviation at first use, state implemented / verified /
  planned status explicitly, and do not add plain-language restatements.

## Commit messages

- Commit messages are written in English: an imperative subject line of at most 72 characters (an optional scope prefix such as `paper:` or `docs:` is fine), a blank line, then a body wrapped at about 72 columns that states what changed and why, citing rulings, LOG entries and the user's approval where relevant.
- No AI attribution lines: no `Co-Authored-By` trailer and no "Generated with" line.
- Scientific changes keep the single-responsibility commit rule of D-059 stated above.
