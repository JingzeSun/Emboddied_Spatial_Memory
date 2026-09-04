# Schema 索引

状态：v0.1 草案，待 HC-021–HC-030 后冻结。

- `observation_region.schema.json`：单帧/短窗的结构 latent 区域。
- `world_memory.schema.json`：持久世界节点、关系和版本事实。
- `memory_transaction.schema.json`：唯一允许写入 memory 的操作合同。
- `memory_update_case.schema.json`：实验 case、oracle 和控制项。
- `evidence_event.schema.json`：证据来源、时间与可靠性。
- `run_manifest.schema.json`：正式运行的可复现元数据。

最重要的不变量：observation region ID 不能冒充 world node ID；模型输出 transaction，executor 决定是否接受并执行。

