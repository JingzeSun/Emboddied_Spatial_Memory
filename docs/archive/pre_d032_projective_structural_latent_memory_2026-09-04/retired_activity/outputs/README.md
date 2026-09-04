# Outputs

运行输出与 checkpoint 不提交 Git。本目录只保留说明和可选小汇总。

每个正式 run 的外部目录应包含：

```text
<run_id>/
  manifest.yaml
  config.yaml
  environment.txt
  raw_predictions.jsonl
  projected_predictions.jsonl
  metrics.json
  failures.jsonl
  logs/
  checkpoints/      # external only
```

`manifest.yaml` 必须保存 decision IDs、contract/metric/data/split/code hash、seed、方法与模型 ID、硬件、test access、退出码和失败信息。模板见 `experiments/bounded_revision_validation/templates/run_manifest.example.yaml`。

