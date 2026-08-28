# 方法与接口规范

> 合同版本：v1.1
> 状态：接口已冻结用于 MVP；尚未实现或验证
> 上位蓝图：`09_integrated_direction_plan.md`

## 1. 坐标约定

- `K`：camera intrinsic matrix；
- `T^w_c(t)`：camera coordinate 到 world coordinate；
- `X_w=T^w_c(t)X_c(t)`。

旧帧点投影到当前 camera：

[
X_{c_t}=(T^w_c(t))^{-1}X_w
]

从 (t-1) 到 (t)：

[
X_{c_t}=(T^w_c(t))^{-1}T^w_c(t-1)X_{c_{t-1}}
]

实现不得使用方向含糊的 `RX+t`。纯旋转可用 (KRK^{-1})，但仍必须处理可见性、出视野和前景遮挡。

## 2. 核心状态

### 2.1 ObservationGraph

```text
ObservationGraph = {
  episode_id, frame_id, timestamp,
  T_world_camera, intrinsics, sensor_confidence,
  nodes: [ObservationNode],
  edges: [ObservationEdge],
  provenance
}

ObservationNode = {
  observation_node_id,
  node_type,                  # object / surface / region
  image_support,
  camera_geometry,
  latent_ref,
  semantic_distribution,
  track_evidence,
  visibility_evidence,
  motion_evidence,
  uncertainty
}
```

ObservationGraph 只描述当前帧，不复用长期 node ID。

### 2.2 SceneBeliefGraph

```text
BeliefNode = {
  node_id,
  node_type,
  geometry_distribution,
  semantic_distribution,
  latent_state,
  entity_mobility,
  motion_state,
  persistence_state,
  change_state,
  visibility_state,
  valid_from,
  valid_to,
  supersedes,
  confidence,
  provenance
}

BeliefEdge = {
  edge_id,
  source_id,
  target_id,
  relation_type,
  state,
  valid_from,
  valid_to,
  supersedes,
  confidence,
  provenance
}
```

SceneBelief 允许 candidate、多假设和 quarantine。它不是已经巩固的长期真相。

### 2.3 PersistentWorldMemory

保存经多帧确认的节点、关系、Chart/Place 锚点、历史版本和压缩 evidence。写入必须经过 consolidation policy。

### 2.4 ActiveContext

按任务 (g_t)、当前位置和当前 belief 选出的相关子图。它是读取视图，不是独立复制的全图，也不负责修改 PersistentWorldMemory。

### 2.5 ContextDelta

```text
ContextDelta = {
  delta_id,
  base_belief_version,
  observation_ref,
  innovation_refs,
  affected_node_ids,
  affected_edge_ids,
  propagation_stop_edge_ids,
  operations,
  unchanged_control_ids,
  confidence,
  controller_revision,
  provenance
}
```

机器可读合同见 `schemas/`。

## 3. 感知与 ObservationGraph

```text
RGB ──> frozen visual features
RGB/depth ──> regions, instances, surfaces
pose + depth + K ──> world registration and expected ego flow
observed flow - ego flow ──> residual motion evidence
semantic + track + depth ordering ──> actor/occlusion evidence
```

动态判断不能只依赖 flow；stationary actor、同向运动、深度错误和 camera motion 都会产生歧义。所有估计值保留来源和置信度。

## 4. Frame-to-Belief Association

对 observation node (i) 和 projected belief node (j)：

[
s_{ij}=w_gs_{\text{geometry}}+w_ps_{\text{projection}}+
w_zs_{\text{latent}}+w_ss_{\text{semantic}}+
w_ts_{\text{temporal}}
]

输出不只是最佳匹配，还包括：

- candidate matches 与置信度；
- unmatched observation；
- expected-but-unmatched belief；
- split/merge ambiguity；
- sensor/pose inconsistency；
- visibility support。

MVP 先实现 gated assignment；learned association 不是核心 claim，必须在各方法间保持相同输入或单独消融。

## 5. Expected Observation Projection

`ProjectExpectedObservation` 从 belief 中检索当前 frustum 可能相关的局部图，并输出：

- expected projected geometry/mask；
- expected identity/semantic distribution；
- expected visibility；
- possible occluders；
- relation witnesses；
- pose/depth uncertainty。

它不重新编码完整世界图。检索应先使用 Chart/Place、空间索引和 frustum 做粗筛，再投影局部候选。

## 6. Pose-Aware Structured Innovation

每个 observation/belief 对输出：

```text
Innovation = {
  innovation_id,
  category,        # matched/new/occluded/reliably_absent/conflict/ambiguous/sensor_inconsistent
  observation_node_ids,
  belief_node_ids,
  geometry_delta,
  identity_delta,
  visibility_delta,
  relation_deltas,
  evidence_reliability,
  causal_scores,
  provenance
}
```

`reliably_absent` 的必要条件：

1. belief 预测目标应在当前视野；
2. 预测区域有足够可见率；
3. 没有可信 occluder；
4. pose/depth/perception 可靠；
5. 达到在 validation 冻结的多视角或时间证据标准。

不满足时只能输出 `occluded/out_of_fov/ambiguous`。

## 7. Affected-Subgraph Retrieval

### 7.1 种子

- innovation 直接匹配/冲突的 belief nodes；
- 对应 identity、visibility、location 和 event edges；
- 必须解释的 expected-but-absent 节点。

### 7.2 传播边

只沿有因果/约束意义的 typed relation 扩展，例如：

- object—located_in—region；
- object—occludes—surface；
- object—participates_in—event；
- object—same_identity—version；
- support/containment/spatial relations。

### 7.3 停止条件

- relation 与当前 innovation 无语义依赖；
- 跨越稳定 Chart/Place 边界且无证据；
- 目标节点预计不可见；
- 传播置信度低于 validation 阈值；
- 达到 operator-specific invariant；
- 候选扩展只增加 revision cost 而不改变必要后果。

Retriever 必须输出 stop edge，而不是只输出被选节点。

## 8. Revision Controller

按三个阶段实现：

1. **Oracle controller**：读取 oracle affected-subgraph/operator，验证 executor 与指标；
2. **Deterministic controller**：规则候选、显式阈值、可解释 baseline；
3. **Hybrid learned controller**：GNN/graph Transformer 预测 node/edge scope、operator 和 confidence，执行仍由 deterministic editor 完成。

不采用 LLM 自由文本直接修改图。

## 9. Typed Revision Operators

| Operator | 前置条件 | 主要效果 |
|---|---|---|
| `REINFORCE` | 新旧状态一致 | 增加支持证据、更新置信度 |
| `ADD` | 可靠新实体/边/事件 | 创建 candidate version |
| `UPDATE_STATE` | 同一实体属性变化 | 创建新属性版本 |
| `RELINK` | 关系目标改变 | 关闭旧边并创建新边 |
| `INVALIDATE` | 旧解释被反证 | 关闭有效区间，保留历史 |
| `SUPERSEDE` | 新版本接替旧版本 | 建立 supersedes 链 |
| `PRESERVE` | 遮挡/视野外/证据不足 | 保留 belief，更新可见性/evidence |
| `QUARANTINE` | 冲突但不可靠 | 保留候选，不提交长期记忆 |

每个 operation 必须声明 target、before/after、evidence、confidence 和 valid time。

## 10. 两个哨兵状态轨迹

### 10.1 人长期站在门口

```text
actor.motion: moving -> stationary
actor.persistence: transient -> persistent_occupancy
door.visibility: visible -> occluded
door.ontology/identity/geometry: unchanged
```

时间增加可以提升 occupancy persistence，不能把 actor node 转为 wall/portal/surface。

### 10.2 椅子永久搬走

- 新位置可见：旧 `located_in` edge `SUPERSEDE`，新 edge `ADD/RELINK`；
- 旧址可靠缺席、去向未知：旧 edge `INVALIDATE`，chair location 为 `unknown`；
- 遮挡/视野外：`PRESERVE` 旧 edge，只改 visibility。

## 11. Consolidation

SceneBelief → PersistentWorldMemory 的提交应满足：

- operator 已执行且 invariants 通过；
- evidence 达到 validation 冻结标准；
- 非 quarantine；
- 版本链无环；
- 必要 provenance 完整；
- 若为 removal/relocation，至少存在可靠可见性或新位置证据。

Consolidation 失败不删除 belief candidate，而是保留原因。

## 12. 训练目标

```text
L_total = L_innovation + lambda_s L_scope + lambda_o L_operator
        + lambda_r L_relation + lambda_k L_preserve
        + lambda_c L_calibration + lambda_cost L_revision_cost
```

`revision-cost` 不能单独优化，否则“不修改”会成为退化解。所有权重仅用 train/validation 数据选择。

## 13. 实现模块

```text
src/
├── contracts/        schema-backed typed records
├── geometry/         SE(3), projection, frustum, ego flow
├── perception/       latent, region, object, depth, motion evidence
├── association/      observation-to-belief candidates
├── belief/           graph, versions, provenance, consolidation
├── innovation/       expected observation and structured comparison
├── revision/         scope retrieval, controller, typed executor
├── context/          ActiveContext selection and queries
├── baselines/        append-only, EMA, lifecycle, full recompute
└── evaluation/       delta, preservation, propagation, query, cost
```

详细工作包见 `10_implementation_roadmap.md`。

## 14. 必测失败模式

- pose/depth 误差造成批量 innovation；
- stationary actor 被改成结构；
- occlusion 被当作 absence；
- unknown location 被虚构；
- relation propagation 漏改；
- propagation 越过无关边界；
- graph version cycle；
- duplicate entity 与错误 merge；
- full graph 被隐式重新编码；
- controller 低置信时仍提交长期写入。

## 15. v1.1 规范覆盖层

本节覆盖前文中与 D-013 不一致或未展开的字段；其余基础算法合同继续有效。

### 15.1 Innovation 双层类型

`category` 描述 observation/belief 对齐证据，`innovation_mode` 描述应进入哪条状态路径：

```text
Innovation = {
  innovation_id,
  category,          # matched/new/occluded/reliably_absent/conflict/ambiguous/sensor_inconsistent
  innovation_mode,   # reinforcement/graph_expansion/belief_revision/
                     # visibility_update/association_ambiguity/sensor_inconsistency
  observation_node_ids,
  belief_node_ids,
  geometry_delta,
  identity_delta,
  visibility_delta,
  relation_deltas,
  evidence_reliability,
  causal_scores,
  provenance
}
```

`new` 不自动等于 `belief_revision`；它通常触发 `graph_expansion`。`reliably_absent/conflict` 才可能在证据充分时触发 revision。

### 15.2 ContextDelta 增长字段

除 affected/control/stop 外，v1.1 增加：

```text
created_node_ids
created_edge_ids
attachment_node_ids
```

graph expansion 主要使用 created/attachment；belief revision 主要使用 affected/stop/operators。一个复合帧可同时产生多种 innovation，但不同操作仍需可分解评测。

### 15.3 Relation 与 reference frame

`BeliefEdge` 必须包含：

```text
relation_family    # structural/metric/visibility/event/temporal
reference_frame   # world/gravity/chart/entity + reference_id
derivation         # stored_evidence/derived_from_geometry/aggregated_observation
```

`left_of/right_of/in_front_of/behind` 默认是 observation/query-time camera-relative relation，只能在 `ObservationGraph/ActiveContext` 中派生；若提交到世界 belief，必须转换到稳定 reference frame。`near/above/located_in` 是否存储或派生由 D-015 冻结。

### 15.4 ActiveContext 输出

```text
ActiveContext = {
  belief_version,
  task_pose_route_dialogue_refs,
  candidate_referents: [{entity_id, score, factor_breakdown, relation_evidence}],
  selected_entity_id,
  decision: select | keep_ranked | ask_clarification,
  ambiguity,
  provenance
}
```

选择或排序不会触发 `INVALIDATE/SUPERSEDE`。双木箱中两个 entity 必须继续存在，除非另有世界证据。

### 15.5 实现门禁

先按 `12` 完成机器 fixture，再实现 deterministic executor。只有 oracle scope 同时优于 local-slot 的漏改和 full-graph 的多改，才训练 learned controller。
