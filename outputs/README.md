# Outputs

运行输出不提交 Git；只提交生成逻辑、schema 和必要的小型示例。

正式 run 使用：

```text
outputs/<run_id>/
├── config.yaml
├── environment.json
├── dataset_manifest.json
├── predictions/
├── revisions/
├── metrics_per_episode.jsonl
├── aggregate_metrics.json
├── failures/
└── run.log
```

每个 run 必须记录 code revision、contract version、split、seed、sensor/model IDs、完整失败信息。汇总表不能脱离 per-episode 原始输出存在。

oracle、deterministic 和 learned controller 使用不同 run tags；pilot/test 不得混写。
