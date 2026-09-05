# Outputs

正式运行输出不提交 Git；只提交生成逻辑、schema 和小型示例。

~~~text
outputs/<run_id>/
  run_manifest.json
  config.yaml
  environment.json
  candidates/
  sandbox_graphs/
  predictions/
  graph_diffs/
  metrics_per_case.jsonl
  aggregate_metrics.json
  failures/
  run.log
~~~

逐候选记录必须包含 transaction、执行 status/result hash、current/future prediction refs、now/future/edit/growth/collateral/illegal、posterior 与 rank。汇总表不能脱离逐例结果存在。

teacher-forced、self-rollout、validation、test、oracle 和 learned 使用不同 tags。缺 manifest 字段、发生泄漏或实现 bug 的批次标 invalidated，不覆盖旧输出。

宿主不稳定时允许把同一 run 分成 deterministic shards/points：每个 attempt 使用新目录并以 `complete.json` 标记原子完成，失败 attempt 不删除、不改写；父 manifest 必须记录每次 return code，并且只有全部注册 shard 成功后才能汇总。白话说，一个 Python 进程崩溃可以重试同一个固定 group，但不能跳过它或换 seed 来挑成功结果；这种隔离只提高可恢复性，不提高方法分数。
