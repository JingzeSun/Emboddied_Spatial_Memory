# Schema contracts

活动 schema 已按 D-024/D-025 改为五个独立接口：

- `world_graph.schema.json`：旧世界状态与 typed dependency；
- `evidence_event.schema.json`：双时间、来源、可见性与 group；
- `revision_transaction.schema.json`：`ΔG/M/τ/Z` 候选事务；
- `revision_case.schema.json`：一个训练/评价样本；
- `run_manifest.schema.json`：正式运行 provenance。

`revision_case.evaluation_contract` 把适用 Criterion 的局部含义、计算口径、分子/分母数值例子与负责的 Human Confirmation 一起带入案例文件，避免运行时脱离统一判据。

这些是设计草案，尚未绑定代码或验证器。旧 ObservationGraph/ActiveContext/ContextDelta 等 schema 已保存在 D-024 前快照，不再是当前活动接口。

JSON Schema 只验证形状；互斥、最小闭包、有效时间顺序、证据可达性和等价事务由 executor/evaluator 检查。
