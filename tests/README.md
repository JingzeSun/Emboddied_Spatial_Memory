# Tests

Run the whole suite from the repository root (`tests/` has no `__init__.py`, so it is both the start and the
top-level directory):

```bash
PYTHONPATH=src python -m unittest discover -s tests -t tests -p "test_*.py"
```

A single module runs as `python -m unittest tests.test_vsmt_lean_memory`. Tests that exercise `ops/vsmt/` scripts put
that directory on `sys.path` themselves. Several tests call `git` (for example to read the generator source at a
registered commit), so the suite needs a clone with full history. Passing tests show that the code does what its
contracts say; they are not evidence that the method works.

| Group | Modules |
|---|---|
| Method and evaluation (`src/vsmt/lean_*`) | `test_vsmt_lean_` + `memory`, `geometry`, `assignment`, `model`, `runner`, `runner_revert`, `arms`, `controls`, `heuristic_label`, `llm_op`, `teacher`, `evaluation`, `nuisance_tally`, `development`, `frontend_cache`, `frontend_diagnostics`, `reid_head`, `public_pose`, `object_geometry`, `object_caches`, `object_table`, `intervention`, `route_and_selection`, `window_probe`, `pilot`, `pilot_capacity`, `assets`, `confirmation_houses`, `s3_01_manifests`, `test_seal`, `hf_release`; contract digests and their binding to the code in `cross_contract` |
| Stage entry points (`ops/vsmt/`) | `test_vsmt_lean_` + `s1_03_mask_recovery`, `s1_03_runner`, `s1_04_diagnostics_runner`, `s1_04_geometry_tool`, `s1_05_selection`, `s2_01_entry`, `s2_04_entry`, `s2_05_entry`, `node_audit`, `s2_06_grid_review`, `s2_06_manifest`, `s2_06_reading`, `s3_01_planning`, `s3_generator`, `s3_02_bench`, `s3_02_manifest`, `s3_03_driver`, `s3_03_train`, `s3_04`, `s3_05`, `s3_05_unseal`, `s3_06_reanalysis`, `s4_llm_op_context`, `llm_op_driver`; `test_vsmt_hf_fetch`, `test_vsmt_hf_release_driver`, `test_vsmt_remote_hosts` |
| Development analyses reused by S2-06 and S3-03 | `test_vsmt_lean_` + `ruling82_seed_analysis`, `ruling88_analysis`, `ruling88_probes`, `ruling89_history_audit`, `ruling89_probes`, `ruling89_recall`, `ruling95_reading`, `residual_trace` |
| Helpers from earlier directions still in use | `test_l1_entities`, `test_l1_masks`, `test_l1_structures`, `test_vm04_public_visibility`, `test_vm04_observation_runner`, `test_vm04_observation_suitability_contract`, `test_vm04_two_house_worker` |

The tests of earlier project directions were removed from `main` with their modules after the tag `paper-v1`.
