---
license: apache-2.0
tags:
- embodied-ai
- spatial-memory
- procthor
- ai2thor
---

# VSMT-lean S3 results and weights (T0)

Results and weights of the VSMT-lean S3 experiments: the round-1 association/existence heads of every learned arm and seed
for both front ends (`weights/<front>/<arm>.tar`), the ReID projection heads (`reid/`), the S3-04 freeze directory
(`s3-04-dea8c20/`) and all experiment exports (`exports/`, including the S3-05 and S3-07 statistics).

## Licence

- Weights, heads and other model files: Apache License 2.0 (this repository's licence; full text in `LICENSE-APACHE-2.0`).
- The result JSON files under `exports/` are provided under CC-BY-4.0.

## Download and verify

Every item is listed in `MANIFEST.json` with its sha256, size, restore path and (for tars) the directory tree digest. The
release tools live in the code repository `JingzeSun/VSMT` (`ops/vsmt/hf_fetch.py`): it downloads the selected items at a
pinned revision, checks every sha256, extracts each tar safely, recomputes the tree digest, and restores the original layout
under a base directory (default `/root/autodl-tmp`) so the repository's scripts run unchanged:

```bash
python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean --repo-type model --revision <commit> --select weights/instance/ --dest /root/autodl-tmp
```

Each episode directory is one deterministic, uncompressed tar (members sorted by path, mtime 0, owner 0/0, modes 644/755,
GNU format), so the same directory always gives the same bytes. 
## Added after the paper's revision (2026-10-09)

The paper cites revision `0b2ce7f8bb5d`. One later commit adds three files and changes no earlier file:

- `reid/reid_head_vitb14_oracle_caa50c7.json`: the ReID projection head of the instance-mask front end (payload digest
  `5cea91cf…`, file SHA-256 `27bf6a10…`, the file the S3-04 freeze receipt recorded), used by every instance-mask run
  of S3-03 to S3-05. Restore path: `vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json`.
- `inputs/null_window_salt.txt`: the private salt of ruling 37, which decided the no-change draw of every generated
  episode (SHA-256 of its stripped text `8f4eae85…`); published after the test split was read, so that the data can be
  regenerated from ProcTHOR-10K. New data generated for other purposes should use a new salt. Restore path:
  `vsmt_private/null_window_salt.txt` (the generator refuses a salt file inside the code repository).
- `MANIFEST_ADDENDUM.json`: both files with their sizes, SHA-256 and restore paths. `reproduce/fetch_extras.py` in the
  code repository downloads them at a pinned revision and checks them.

## Upstream licences and notices

- Frames, depth, poses and ground truth were rendered with AI2-THOR 5.0.0 (Copyright 2021 Allen Institute for AI,
  Apache License 2.0) in houses of ProcTHOR-10K 0.1.2 (Apache License 2.0). Objects were removed, moved or added by this
  project's intervention scripts. Rendering engine: Unity, as shipped in the AI2-THOR 5.0.0 build.
- Fragment masks were computed with SAM 2.1 (Hiera Small) and descriptors with DINOv2 ViT-B/14, both Apache License 2.0;
  no model weights of these upstream projects are redistributed here.
- The training data behind these weights are the CC-BY-4.0 dataset tiers of this release. The upstream material remains under the Apache License 2.0, whose full text is in
  `LICENSE-APACHE-2.0` in this repository.
- Please cite ProcTHOR (Deitke et al., NeurIPS 2022, arXiv:2206.06994), AI2-THOR (Kolve et al., arXiv:1712.05474),
  DINOv2 (Oquab et al., arXiv:2304.07193) and SAM 2 (Ravi et al., arXiv:2408.00714) together with this project.

## 3RScan

No 3RScan data is redistributed in this repository or in any other tier of this release: no scans, renderings,
annotations, ground truth or features computed on its frames. The 3RScan Terms of Use allow non-commercial research use
and grant no right to publish or redistribute the data. The external validation on 3RScan (S3-07) is published only as
per-scene metrics and counts (`exports/vsmt_lean_s3_07_*.json` in `Jsun0632/vsmt-lean`); to reproduce it, request 3RScan
access from TUM and rebuild the inputs with the conversion and rendering code in the code repository (branch
`s3-07-impl`, `ops/vsmt/s3_07_*.py`).
