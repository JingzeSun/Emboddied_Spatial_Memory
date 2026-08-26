# Current Machine Contracts

这些 schema 对应 D-008 accepted 的 Affected-Subgraph Revision MVP：

- `episode.schema.json`：counterfactual episode、传感器、oracle 和 query；
- `observation_graph.schema.json`：单帧观测图；
- `belief_graph.schema.json`：版本化 SceneBelief/PersistentWorldMemory 图；
- `context_delta.schema.json`：affected/control/stop 与 typed operations。

旧 `memory_slot.schema.json` 已移入 `docs/archive/pre_d008/schemas/`，不再是现行接口。所有 schema 使用 JSON Schema 2020-12。正式数据生成器必须记录 schema version，并在写入后立即验证。
