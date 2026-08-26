# Outputs

运行产物使用如下结构：

```text
outputs/<run_id>/
├── config.yaml
├── environment.txt
├── dataset_manifest.json
├── metrics_per_episode.jsonl
├── metrics_summary.json
├── artifacts/
└── failure_cases/
```

除本 README 外，`outputs/` 默认不进入版本控制。需要长期保留的图表应复制到论文或报告专用目录，并附生成命令和 run ID。
