# 数据集、Episode 与 Oracle Delta 规范

> 合同版本：v1.0
> 状态：accepted for pilot；正式数据规模待 pilot 后冻结
> 机器契约：`schemas/episode.schema.json`

## 1. 数据必须回答的问题

数据不是泛化训练所有具身能力，而是隔离以下因素：

1. viewpoint/camera motion 与 world change；
2. visible、occluded、out-of-FOV 与 reliably absent；
3. entity mobility、current motion 与 persistence；
4. relocation、removal 与 unknown location；
5. 必要关系传播和无关子图保持；
6. revision accuracy、latency 和 cost。

## 2. 数据角色

| 角色 | 必要能力 | 用途 |
|---|---|---|
| Controlled synthetic | 可控世界状态、轨迹、actor、visibility、oracle graph | 训练、反事实评测、delta ground truth |
| Public embodied benchmark | 可复现任务/传感器协议 | 外部比较和 context query |
| Real dynamic sequence | 真实遮挡、人流、pose/depth error | 校准、失败案例和外部鲁棒性 |

单个数据集不必承担全部角色。选择数据前记录许可证、传感器、场景重叠、可编程性和下载规模。

## 3. Counterfactual History Group

每个 group 共享：

- `scene_family_id/scene_id`；
- initial oracle scene graph；
- initial belief snapshot；
- camera/action trajectory；
- intrinsics 与 sensor profile；
- asset split 与 random seed family。

只改变目标条件：

```text
unchanged_visible
viewpoint_or_turning_only
transient_occlusion
stationary_actor_short
stationary_actor_long
relocation_visible_destination
reliable_absence_unknown_destination
removed_from_scene
out_of_fov
irrelevant_innovation
sensor_inconsistency
```

## 4. Episode 最小内容

```text
metadata and contract version
scene/split/counterfactual identity
sensor calibration and sources
initial_belief_graph_ref
ordered frames and T_world_camera
observation_graph refs
oracle_scene_graph refs at keyframes
oracle_context_delta refs
events and visibility evidence
query set and expected answers
provenance and license
```

估计 pose/depth 与 simulator/measurement ground truth 使用不同字段，不得混写。

## 5. Oracle Scene State

关键帧 oracle graph 至少包含：

- persistent entity/region/event ID；
- node/edge type；
- world geometry；
- semantic/ontology；
- visibility and occluder；
- mobility、motion、persistence、change state；
- spatial/containment/occlusion/event relation；
- valid time。

模拟器状态是 oracle world state；它不自动等于正确的 `ContextDelta`。

## 6. ContextDelta 真值

采用三段式生成：

1. simulator/world-state diff 生成原始变化；
2. deterministic ontology mapping 将变化映射为 typed operator、affected nodes/edges 和 stop boundary；
3. 人工抽检映射是否符合任务语义。

每个 delta 标注：

```text
base_belief_version
target_scene_version
innovation categories
affected_node_ids
affected_edge_ids
propagation_stop_edge_ids
required_revision_operators
unchanged_control_ids
evidence_reliability
valid_time
mapping_revision
human_audit_status
```

自动 VLM/LLM 评审可作为弱标注或审计辅助，不能称为 ground truth。

## 7. 哨兵场景标注

### 7.1 长期静止的人

固定 actor ontology，改变：

- moving/stationary duration；
- occupied region；
- occluded structure；
- persistence/recurrence；
- leave time。

人工检查 actor 没有出现在 structure control set 中，门/墙 identity 不随停留时长变化。

### 7.2 椅子搬迁

分开标注：

- `relocation_visible_destination`：新旧位置都可由 evidence 连接；
- `reliable_absence_unknown_destination`：只关闭旧位置，location unknown；
- `removed_from_scene`：需要独立离场证据；
- `transient_occlusion/out_of_fov`：不得关闭位置关系。

### 7.3 无关创新

为目标 affected-subgraph 指定远处或无依赖的 control subgraph，检查其 node、edge、version 和 query answer 保持不变。

## 8. 标注人工设计项

必须由研究者在正式数据生成前定义：

1. ontology 与允许的状态转换；
2. reliably absent 的 visibility、视角和时间证据标准；
3. 每类 event 的必要传播边；
4. propagation stop boundary；
5. unchanged control subgraph；
6. relocation、unknown 与 removal 的区分；
7. 错误代价和 ambiguity 处理；
8. query 与 evidence trace 的正确答案。

具体数值阈值仅在 pilot/validation 冻结，不能使用 test。

## 9. 数据切分

- 主切分单位是 scene family；
- 同一 counterfactual group 全部条件位于同一 split；
- 同一建筑的不同录制尽量视为同一 family；
- actor/object assets 记录独立 split；
- test 环境、事件模板和 query 不用于 prompt/阈值选择；
- 合成数据与真实数据分别报告，不把自动估计当真实 ground truth。

## 10. 快速落地数据阶段

### D0 — Hand-authored micro fixtures

每个 operator 和哨兵场景至少一个小图，不依赖 RGB。用于 schema、executor、metrics 单元测试。

### D1 — Simulator oracle pilot

构建少量可视化检查通过的 counterfactual groups，覆盖 E0–E5；数量由数据管线稳定性决定，不作为论文规模。

### D2 — Perception-connected pilot

在同一 simulator episodes 上用实际 projection、association 和 innovation 替换 oracle 输入。

### D3 — Formal dataset

pilot 完成后才冻结规模、场景比例、noise sweep、query 数量和正式 split。

## 11. 质量检查

- timestamp 严格递增；
- pose matrix 合法且方向为 `T_world_camera`；
- intrinsics 与 RGB/depth 分辨率一致；
- counterfactual trajectory 对齐；
- persistent ID 不因遮挡改变；
- visibility/absence 标签无矛盾；
- delta 的 before/after graph 可执行；
- affected set 与 control set 不重叠；
- stop edges 存在于 base graph；
- version chain 无环；
- split、license、provenance、hash 完整；
- 人工抽检状态被记录。

## 12. 目录策略

大型数据不进入 Git：

```text
<external_data_root>/
├── raw/
├── interim/
├── processed/
├── manifests/
├── oracle_graphs/
├── context_deltas/
├── queries/
└── splits/
```

仓库只保存 schema、生成/验证脚本、小型 manifest 与无版权问题的 micro fixtures。
