# Observation、Belief、Context 与长期记忆边界

> 状态：accepted representation contract；尚未实现
> 继承要求：地点级记忆、路线经历和透视结构要求来自已确认 Q1；旧详细记录见 `archive/pre_d008/07_long_short_term_memory_block.md`

## 1. 四种状态不能合并

| 状态 | 回答的问题 | 生命周期 | 是否允许不确定/多假设 |
|---|---|---|---|
| ObservationGraph | 当前帧看到了什么 | 单帧 | 是 |
| SceneBelief | 结合历史后当前相信什么 | 在线、可撤销 | 是，必须允许 |
| ActiveContext | 当前任务此刻需要读什么 | task/pose-conditioned | 读取视图 |
| PersistentWorldMemory | 哪些知识已稳定巩固 | 长期、版本化 | 保留历史版本 |

禁止 `new frame → overwrite memory`，也禁止把 ActiveContext 当成完整世界副本。

## 2. 短期工作区

```text
ShortTermWorkspace = {
  observation_window,
  association_hypotheses,
  structured_innovations,
  candidate_context_deltas,
  dynamic_tracks,
  visibility_and_occlusion_state,
  pose_depth_uncertainty,
  quarantined_evidence
}
```

它保存可撤销证据，不只是最近若干帧 token，也不只是“是否进入新地点”的分类结果。

## 3. SceneBelief

SceneBelief 是当前修订的直接对象：

- 允许同一实体有多个 candidate identity/location hypothesis；
- 显式保存可见性、冲突和 unknown；
- 新 evidence 可以增强、反证或 supersede 旧版本；
- quarantine 不提交长期 memory；
- 任何版本都可追溯到 observation 和 controller。

## 4. 长期空间记忆

长期记忆仍由地点、内容、路线和版本历史组成：

[
M_{\text{long}}=G_{\text{place}}+S_{\text{content}}+H_{\text{route}}+H_{\text{version}}
]

- `G_place`：Place、Chart、portal 和 transition；
- `S_content`：对象、surface、event 与它们的关系；
- `H_route`：实际经历的 place/transition 顺序；
- `H_version`：节点/边的有效区间、supersedes 和 evidence。

MVP 不学习 Chart/Place split/merge，但必须保留稳定 Chart/Place 锚点，支持“前一个走廊”“两个转弯之前”等 Q1 已确认查询。

## 5. 读取路径

```text
task + pose + body state
        │
        ▼
retrieve candidate Place/Chart
        │
        ▼
expand task-relevant entity/relation/event subgraph
        │
        ▼
join current SceneBelief visibility/state
        │
        ▼
ActiveContext + evidence trace
```

读取可以是 selective attention；本项目创新重点不在读取本身，而在此前发生的 belief revision。

## 6. 写入路径

```text
ObservationGraph
  -> StructuredInnovation
  -> Candidate ContextDelta
  -> Validate invariants
  -> Apply to SceneBelief
  -> Multi-frame consolidation
  -> PersistentWorldMemory
```

写入长期记忆至少需要 evidence reliability、version validity、provenance 和 operator-specific confirmation。

## 7. Factorized Dynamic State

```text
entity_mobility: actor / movable / fixed / unknown
motion_state: moving / stationary / unknown
persistence_state: transient / recurrent / persistent / unknown
change_state: unchanged / candidate / confirmed / rejected
visibility_state:
  visible / partially_occluded / occluded / out_of_fov /
  reliably_absent / unknown
```

这些维度正交：

- 人可以是 actor + stationary + persistent occupancy；
- 被移动后静止的椅子仍是 movable；
- fixed door 可以暂时 occluded；
- reliably absent 只说明旧位置，不自动说明新位置。

## 8. 版本与 provenance

节点/边不原地抹除：

```text
VersionRecord = {
  record_id,
  valid_from,
  valid_to,
  supersedes,
  operation,
  evidence_refs,
  controller_revision,
  confidence,
  commit_status
}
```

原始 observation 永久保留引用；压缩/归档只能改变存储层，不能让结论失去证据来源。

## 9. Consolidation 策略

### 可立即进入 belief、不能立即长期提交

- 新实体；
- relocation candidate；
- reliable absence candidate；
- identity conflict；
- 新 relation/event。

### 可以直接保持

- expected occlusion；
- out-of-FOV；
- 低置信 sensor inconsistency；
- 与当前子图无关的新 evidence。

### 长期提交

- 多帧或多视角确认；
- operator invariants 通过；
- 不在 quarantine；
- before/after/version chain 完整；
- 人工定义的证据标准满足。

## 10. 哨兵不变量

### 人永远站在门口

- actor node 长期存在；
- occupancy 可以进入 persistent；
- door visibility 可以长期 occluded；
- door identity、geometry、portal relation 不被人覆盖；
- actor 不能因 stationary duration 变成 surface。

### 椅子永远被搬走

- 若新位置可见：旧位置 edge 结束，新位置 edge 生效；
- 若只确认旧址缺席：location 变 unknown；
- 若证据表明离开场景：才使用 removed-from-scene；
- 历史查询仍能回答旧位置和变更时间。

## 11. 与 Chart/Place 的关系

Chart/Place 是检索、坐标和传播边界的重要先验：

- 当前 frustum 先限制候选 Chart/Place；
- affected-subgraph 默认不跨无证据的 Place 边界；
- 转弯时允许多 Chart overlap；
- 新 Place/Chart 的 split/merge 在 MVP 中只使用 oracle/固定规则，不作为学习目标。

## 12. 查询接口

MVP 至少支持：

- `where_is(entity, time?)`；
- `what_changed(region, interval)`；
- `why_preserved(entity)`；
- `what_occludes(entity)`；
- `previous_place(traversal, offset)`；
- `evidence_for(node_or_edge_version)`。

答案必须附 belief version 和 evidence refs，不能只返回自然语言。

## 13. v1.1 ActiveContext 保持不变量

同类实例检索采用“读取视图变化，世界事实不变”的合同：

```text
PersistentWorldMemory: box_A, box_B
SceneBelief:          both identities and versions
ActiveContext:        route/dialogue/task-conditioned ranking
```

必须满足：

1. 非 top-1 候选不会因未被选择而删除或失效；
2. route/dialogue recency 不写入 world relation；
3. camera-relative directional relation 只作派生证据；
4. 歧义且行动代价不等价时允许 `ask_clarification`；
5. ActiveContext 的证据轨迹指向 belief version 和 factor breakdown。

图增长也不得绕过四层边界：新观测先进入 ObservationGraph，可靠 attachment 形成 candidate SceneBelief，巩固后才进入 PersistentWorldMemory。
