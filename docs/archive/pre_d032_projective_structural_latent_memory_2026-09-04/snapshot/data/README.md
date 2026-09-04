# Data interfaces

本目录只保存小 manifest、split ID、下载/生成说明和可提交的微型样本；大型 AI2-THOR、3RScan/3DSSG 数据不提交 Git。

计划数据轨：

```text
data/
  manifests/
    symbolic_v0.yaml
    ai2thor_v0.yaml
    3rscan_v0.yaml
  splits/
    <manifest-hash>/
  samples/
    development_only/
```

统一 transaction 需要 prior graph、evidence events、candidate facts、oracle `ΔG/M/τ/Z` 和 factor vector。完整字段见 `experiments/bounded_revision_validation/DATASETS.md` 与 case template。

每份 manifest 保存来源 URL、许可、版本、校验和、生成/预处理命令、场景 ID、split hash 和是否接触 test。AI2-THOR simulator state 可称 oracle；3RScan 自动映射和人工弱标签按实际来源命名。

当前没有下载或生成任何正式数据。

