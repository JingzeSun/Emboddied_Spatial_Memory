# Source layout

`src/vsmt/` holds the method and its evaluation; `src/cpmt/` holds only the canonical-JSON and hashing helpers. Import
modules directly (for example `from vsmt import lean_memory`); the packages export nothing. Stage entry points are in
`ops/vsmt/` ([docs/REPRODUCE.md](../docs/REPRODUCE.md)), and [docs/METHOD.md](../docs/METHOD.md) section 13 maps every
paper component to a function.

| Role | Modules (`src/vsmt/`) |
|---|---|
| Entity memory, versions, executor, shared dormancy and deduplication | `lean_memory`, `lean_geometry` |
| Front-end cache: fragment admission, instance masks, seals | `lean_frontend_cache`, `lean_public_pose` |
| Shared ReID projection and the descriptor choice | `lean_reid_head`, `lean_frontend_diagnostics` |
| Recall, features, seals A and B, rectangular assignment | `lean_assignment` |
| Learned cost heads, training | `lean_model`; the paper's recipe in `lean_s3_03.training_settings` |
| Per-frame loop (geometry, assignment, existence, commit) | `lean_runner` |
| Arms: vocabularies, grids, rule-based costs, ELU-P/RAC existence, NoVersion, selection | `lean_arms`, `lean_controls`, `lean_heuristic_label`, `lean_llm_op` |
| Hindsight teacher, ledger, metrics, statistics | `lean_teacher`, `lean_evaluation`, `lean_development` (ELU-P counts) |
| Private ground-truth geometry | `lean_object_geometry` |
| Data generation rules: split, route, interventions, assets | `lean_intervention`, `lean_interventions`, `lean_route`, `lean_pilot`, `lean_assets`, `lean_s3_manifests` |
| Stage logic: freeze, test statistics, test seal | `lean_s3_04`, `lean_s3_05`, `lean_test_seal` |
| Helpers from earlier directions still in use | `l1_masks`, `l1_entities`, `l1_structures`, `shared_frontend_core` (fragment geometry, DINOv2 pooling, free space, visible volume); `vm04_public_visibility`, `vm04_observation_runner` (container visibility in the generator) |

`src/cpmt/hashing.py` provides `canonical_json` and `clone_json`. The modules of earlier project directions (the CPMT
executor, unified graph, place layer, structure estimators and VM-04/VM-05 protocols) were removed from `main` after
the tag `paper-v1` and remain there at their original paths.
