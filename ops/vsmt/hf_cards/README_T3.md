---
license: cc-by-4.0
viewer: false
tags:
- embodied-ai
- spatial-memory
- procthor
- ai2thor
---

# VSMT-lean S3 training inputs (T3)

Training inputs of the VSMT-lean S3 experiments: the train split of the ProcTHOR-10K episodes, in the same layout as the
evaluation tier (`train/<kind>/<episode>.tar`, `kind` in `raw`, `geometry`, `instance_cache`, `sam2_cache`; root files under
`train/<kind>/_root/`). Every cache episode was checked against the S3-02 cache exports before upload.

## Download and verify

Every item is listed in `MANIFEST.json` with its sha256, size, restore path and (for tars) the directory tree digest. The
release tools live in the code repository `JingzeSun/VSMT` (`ops/vsmt/hf_fetch.py`): it downloads the selected items at a
pinned revision, checks every sha256, extracts each tar safely, recomputes the tree digest, and restores the original layout
under a base directory (default `/root/autodl-tmp`) so the repository's scripts run unchanged:

```bash
python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-train --repo-type dataset --revision <commit> --select train/instance_cache/ --dest /root/autodl-tmp
```

Each episode directory is one deterministic, uncompressed tar (members sorted by path, mtime 0, owner 0/0, modes 644/755,
GNU format), so the same directory always gives the same bytes. The tars are not WebDataset shards, which is why the
automatic dataset viewer is disabled.

## Upstream licences and notices

- Frames, depth, poses and ground truth were rendered with AI2-THOR 5.0.0 (Copyright 2021 Allen Institute for AI,
  Apache License 2.0) in houses of ProcTHOR-10K 0.1.2 (Apache License 2.0). Objects were removed, moved or added by this
  project's intervention scripts. Rendering engine: Unity, as shipped in the AI2-THOR 5.0.0 build.
- Fragment masks were computed with SAM 2.1 (Hiera Small) and descriptors with DINOv2 ViT-B/14, both Apache License 2.0;
  no model weights of these upstream projects are redistributed here.
- The CC-BY-4.0 licence of this repository covers this project's own contributions (episode design, interventions, labels,
  caches, records and manifests). The upstream material remains under the Apache License 2.0, whose full text is in
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
