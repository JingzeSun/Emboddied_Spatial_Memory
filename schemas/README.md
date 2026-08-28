# Current Machine Contracts

这些 JSON Schema 对应 D-013 接受的 v1.1 状态分层，目前是合同草案，尚未通过实现验证：

- `episode.schema.json`：counterfactual episode、传感器、oracle 与 query；
- `observation_graph.schema.json`：单帧观测图和显式 reference frame；
- `belief_graph.schema.json`：版本化 `SceneBelief/PersistentWorldMemory`；
- `context_delta.schema.json`：graph expansion、affected/control/stop 与 typed operations；
- `active_context.schema.json`：任务、路线、对话条件下的候选排序、证据分解与澄清决定。

旧 `memory_slot.schema.json` 已移入 `docs/archive/pre_d008/schemas/`，不再是现行接口。所有 schema 使用 JSON Schema 2020-12。正式数据生成器必须记录 schema/contract version，并在写入后立即验证。

状态边界：

- `ObservationGraph` 可含 camera-relative directional relations；
- `SceneBelief` 的方向关系必须有稳定 reference frame，不能永久写入无参考系的 left/right；
- `ContextDelta` 修改世界图；
- `ActiveContext` 只改变候选显著性，不删除未选中的长期实例。
