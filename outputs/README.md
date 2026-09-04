# Outputs

运行输出、大型日志和 checkpoint 不提交 Git。本目录只保留说明与可选的小型汇总。

每个正式 run 的外部目录至少包含：

```text
<run_id>/
  manifest.yaml
  config.yaml
  environment.txt
  observation_regions.jsonl
  proposed_transactions.jsonl
  executed_memory_versions.jsonl
  metrics.json
  failures.jsonl
  logs/
  checkpoints/      # external only
```

`manifest.yaml` 必须保存 decision IDs、contract/metric/data/split/code hash、seed、方法与 backbone ID、硬件、test access、退出码和失败信息。模板见 `experiments/projective_structural_latent_memory/templates/run_manifest.example.yaml`。

必须同时保存模型提出的 transaction 与 executor 接受/拒绝后的 memory version，不能只保存最终图。当前没有正式运行输出。
