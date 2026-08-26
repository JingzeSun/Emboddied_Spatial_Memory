# Data

大型数据、生成缓存和训练产物不提交 Git。数据合同见 `docs/04_dataset_spec.md` 与 `schemas/episode.schema.json`。

仓库允许保存：

- 无版权问题的 hand-authored micro fixtures；
- 小型 manifest 示例；
- split/ontology/operator 配置；
- 数据生成和人工审计说明；
- 文件 hash，不保存大型媒体本体。

外部数据根目录建议：

```text
<external_data_root>/
├── raw/
├── interim/
├── processed/
├── manifests/
├── oracle_graphs/
├── context_deltas/
├── queries/
└── splits/
```

第一批数据不是视频数据集，而是可人工检查的 belief/observation/delta 微图；它们用于 executor 和 metrics，不得被称为论文规模数据。
