# Data

No data are tracked in this directory. The data behind the paper (raw episodes, geometry tables and both front-end
caches of the S3 splits; weights and result exports) are released on Hugging Face in four layers, and the generation
pipeline from ProcTHOR-10K is described stage by stage; see [docs/REPRODUCE.md](../docs/REPRODUCE.md) and, for sources,
splits, interventions and fields, [docs/DATA.md](../docs/DATA.md).

On the servers the data live under `/root/autodl-tmp/vsmt_{outputs,caches,private,sources}`. `data/cache/` is an
ignored local cache. The hand-made fixtures of earlier project directions were removed from `main` after the tag
`paper-v1`.
