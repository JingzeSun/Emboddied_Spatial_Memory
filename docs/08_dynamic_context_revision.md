# 动态空间语境修正（拟议研究升级）

> 状态：`proposed`，尚未接受、尚未实现、尚未验证。  
> 目的：把“动态信息作为静态记忆写入门控”升级为“新观测触发空间信念与活动语境的结构化修正”。  
> 决策入口：`06_decision_log.md` 中的 D-008。D-008 接受前，本文件不替代 `01_research_question.md`、`03_experiment_contract.md` 或现有 schema。

## 1. 为什么需要这个升级

现有主线主要回答：如何通过 pose、geometry、visibility、ego-motion residual 和 soft update，避免行人、遮挡与临时物体污染长期静态记忆。

这条主线仍然必要，但它容易把动态信息表达成一个负向信号：

```text
dynamic evidence 高 -> 少写或不写 static memory
```

导师建议进一步要求：动态对象和短期出现不能只作为待过滤噪声，它们本身也应被学习、记录，并影响智能体对当前场景的解释。于是研究问题需要从“保护旧记忆”扩展为：

> 当新帧到来时，智能体如何判断旧空间信念中哪些节点和关系应被保留、更新、重连、分裂、合并或暂时挂起，并形成与当前位置和任务相关的新语境？

因此核心映射不是：

```text
New Frame -> New Context
```

而是：

```text
(Previous Belief + Action/Pose + New Observation) -> Context Delta
```

## 2. Observation、Memory、Belief 与 Context 的区别

### 2.1 Observation

`Observation_t` 是时刻 `t` 的传感器证据，包括 RGB、depth、pose、flow、结构区域、语义、可见性及其不确定性。它回答“这一帧测到了什么”。

### 2.2 Persistent World Memory

`WorldMemory_t` 保存 Place、Local Structural Chart、WorldSlot、Transition、Traversal、历史事件与 provenance。它回答“截至目前积累了什么世界知识”。

### 2.3 Scene Belief

`SceneBelief_t` 是智能体基于全部历史证据，对当前世界状态保留的带不确定性解释：

```text
SceneBelief = {
  place_belief,
  active_chart_hypotheses,
  structural_slot_states,
  object_states,
  dynamic_tracks,
  spatial_and_occlusion_relations,
  active_events,
  alternative_hypotheses,
  uncertainty,
  provenance
}
```

它不是单个确定 scene graph；在证据不足时可以同时保留多个假设。

### 2.4 Active Context

`ActiveContext_t` 是从 `SceneBelief_t` 中，按当前 agent pose、可见范围、最近历史和任务目标选出的相关子图：

\[
X_t(g_t)=\operatorname{SelectRelevantSubgraph}(B_t, g_t, T^w_{c_t})
\]

因此 Context 不是整份长期记忆，也不等于当前帧。相同帧在不同历史或不同任务下可以形成不同 Context。

## 3. “动态”不能等同于当前光流

至少分开四个维度：

```text
DynamicState = {
  entity_mobility,       # actor / movable / fixed / unknown
  motion_state,          # moving / stationary / unknown
  persistence_state,     # transient / recurrent / persistent / unknown
  change_state,          # unchanged / candidate_change / confirmed_change
  trajectory,
  occupancy_effect,
  occlusion_targets,
  valid_time,
  interaction_state,
  confidence,
  provenance
}
```

必须区分：

- 行人当前不动：`motion_state=stationary`，但仍是 actor，不能融合进墙面；
- 行人短时经过：保存其轨迹、占据和遮挡事件，同时保护后方结构；
- 行人长期站在门口：不是简单噪声，也不自动成为静态结构，而是高持续度的 actor occupancy；
- 椅子被永久搬动：椅子不是 actor，但其位置关系发生了 persistent change；
- 门暂时被遮挡与门被拆除：当前不可见证据相似，但对旧信念的正确修正不同。

## 4. 新帧驱动语境修正的方法链

### 4.1 预测旧语境在当前帧中应产生什么

使用旧 belief、当前 pose、depth 和相机内参，把当前预计可见的 world slots、Chart 和关系投影到 observation space：

\[
\hat O_t=\operatorname{ProjectExpectedObservation}(B_{t-1},T^w_{c_t},K)
\]

这里预测的是结构、实体、可见性和关系，不要求恢复 RGB。

### 4.2 计算 Structured Innovation

解析实际观测 `O_t`，并与 `\hat O_t` 做 pose-aware association：

\[
\delta_t=\operatorname{CompareStructured}(O_t,\hat O_t)
\]

`delta_t` 至少区分：

- matched and confirmed；
- expected but occluded；
- expected and reliably absent；
- newly observed；
- geometry/semantic/relation conflict；
- association ambiguity；
- sensor-inconsistent evidence。

它不是像素差，也不是单一 feature residual，而是“当前观测相对旧空间信念提供了什么新证据”。

### 4.3 解释变化原因

对每个 innovation 保留以下竞争解释及概率，而不是立即硬分类：

```text
ego_motion
temporary_occlusion
dynamic_actor_motion
sensor_or_registration_error
persistent_object_state_change
new_entity
new_chart_or_place
ambiguous
```

解释需要联合 pose/depth/flow、语义、实例轨迹、可见性、历史关系和多帧一致性。

### 4.4 定位受影响子图

从 `SceneBelief_{t-1}` 中检索与 innovation 有几何、身份、遮挡、拓扑或事件依赖的局部子图。默认不全量重算整个世界，也不能只修改当前可见节点。

### 4.5 执行版本化 revision operators

候选操作包括：

```text
REINFORCE          增强已有节点、关系或假设
ADD                新建实体、事件、Chart、Place 或关系
UPDATE_STATE       更新位置、运动、开合、占据等状态
RELINK             改变实体—地点、实体—事件或 Chart—Place 归属
SPLIT              将错误合并的实体、事件或地点拆开
MERGE              将重复创建的记录统一
INVALIDATE         使旧解释失效，但保留原始证据
SUPERSEDE          用带有效时间的新状态接替旧状态
PRESERVE_OCCLUDED  保留结构，仅更新可见性和遮挡关系
QUARANTINE         证据不足，暂不提交长期写入
```

原始 observation 和 provenance 不覆盖；belief 与关系使用版本或有效时间表示变化。

### 4.6 形成新 belief 与 active context

\[
\Delta B_t=\pi(B_{t-1},O_t,\hat O_t,\delta_t,H_t)
\]

\[
B_t=\operatorname{Apply}(B_{t-1},\Delta B_t)
\]

随后才按当前任务与身体状态选择 `ActiveContext_t`。多帧确认后的稳定变化再巩固进 Persistent World Memory。

## 5. 它为什么不等于抗噪声

| 场景 | 抗噪声/抗污染目标 | 语境修正目标 |
|---|---|---|
| 行人经过并遮挡门 | 不让人物 feature 覆盖门 | 保留门，同时新增人物、轨迹、遮挡与占据关系 |
| 行人长时间站在门口 | 可能长期抑制写入 | 记录 stationary actor 和持续 occupancy，但不把人固化为建筑结构 |
| 椅子被永久搬走 | 防冻结导致漏更新 | 使旧位置关系失效，建立新位置关系和 change event |
| 后续视角证明黑影是猫 | 降低早期低质量帧权重 | 合并跨帧身份并反向修正早期事件的实体归属 |
| 转弯看到新走廊 | 对齐视角、降低错误覆盖 | 建立候选 Chart/Place，并重组地点边界与拓扑关系 |
| 新帧与历史无关 | 抑制无关写入 | 正确执行 `IGNORE/QUARANTINE`，保持旧子图 |

抗噪声的理想输出通常是“恢复或保持一个干净的旧状态”；语境修正允许正确答案本身发生结构变化。抗噪声只是 `PRESERVE` 能力，语境修正还必须具有 `UPDATE`、`PROPAGATE` 和 `ISOLATE` 能力。

## 6. 方法创新候选

若只增加字段、规则或一个 LLM prompt，不足以构成方法创新。候选方法贡献应同时包含：

1. **Pose-aware structured innovation**：先把旧 belief 投影到当前 observation，再在结构、实体、可见性和关系层计算新证据；
2. **Causally scoped subgraph revision**：预测修改对象和传播边界，而不是全局重算或单 slot EMA；
3. **Factorized dynamic state**：分离 mobility、current motion、persistence 和 persistent change；
4. **Versioned evidence-preserving update**：保留原始证据、旧解释、有效时间和 revision provenance；
5. **Learned update/preserve/isolate policy**：训练模型判断何时更新、何时保持、何时隔离，而不只依赖手工阈值。

其中 1+2 是最可能形成核心算法贡献的组合；3+4 是必要表示；5 是否加入取决于数据量和 MVP 结果。

## 7. 候选训练目标

如果实现 learned revision controller，可使用：

\[
\mathcal L =
\mathcal L_{state}
+\lambda_{\Delta}\mathcal L_{delta}
+\lambda_{rel}\mathcal L_{relation}
+\lambda_{keep}\mathcal L_{preserve}
+\lambda_{cal}\mathcal L_{calibration}
+\lambda_{cost}\mathcal L_{revision\_cost}
\]

- `L_state`：新 belief 的节点/属性状态正确性；
- `L_delta`：revision operator、affected node/edge 与 oracle delta 对齐；
- `L_relation`：必要关系传播和时间一致性；
- `L_preserve`：未受影响子图保持稳定；
- `L_calibration`：不确定性与错误率匹配；
- `L_revision_cost`：惩罚无必要的大范围修改。

`L_revision_cost` 不能单独构成稳定性目标，否则“什么都不改”会成为退化解。权重只能用 validation 数据选择。

## 8. 数据与监督增量

现有 counterfactual group 继续保留，并建议新增：

```text
same_frame_different_history
delayed_disambiguation
entity_merge_or_split
relation_change
stationary_actor
recurrent_dynamic_actor
expected_absence_vs_occlusion
chart_or_place_boundary_revision
action_caused_change
irrelevant_new_evidence
```

每个时刻建议提供：

```text
oracle_scene_state_ref
oracle_context_delta_ref
affected_node_ids
affected_edge_ids
required_revision_operators
unchanged_control_subgraph
valid_time
evidence_reliability
```

模拟器状态可以作为受控 world-state oracle；模型评审或自动抽取结果不能称为 ground truth。

## 9. 候选评测

在现有 contamination、retention、reappearance、Chart consistency 和 persistent-change 指标外，增加：

- `Delta Precision / Recall`：实际修改与必要修改的匹配；
- `Preservation Accuracy`：未受影响子图保持率；
- `Propagation Completeness`：新证据必要后果的覆盖；
- `Collateral Revision Rate`：无关节点/关系被错误改变的比例；
- `Revision Latency`：从关键证据出现到正确修正的帧数；
- `Backward Correction Accuracy`：延迟证据纠正早期身份、事件或归属的准确率；
- `Context Query Accuracy`：依赖更新后语境的空间/事件查询准确率；
- `Revision Cost`：受影响节点数、时延、显存和存储增长。

必须同时报告该改、该保持和该隔离三类样本，避免只评估 change cases。

## 10. 与现有项目的兼容关系

若 D-008 接受：

- D-001 到 D-004 保持不变；
- ObservationRegion 仍是当前帧工作单元；
- WorldSlot、Local Structural Chart、Place、Transition 和 Traversal 继续作为长期底座；
- ego-motion compensation 从动态过滤器升级为 structured innovation 的解释证据；
- soft update 成为 revision operators 中 `REINFORCE/UPDATE_STATE/PRESERVE_OCCLUDED` 的低层实现；
- D-005 的 lifecycle 扩展为带关系、事件和有效时间的 belief revision；
- D-006 的主任务需要重新决定：保留 memory robustness，或升级为 online spatial context revision。

在 D-008 接受和 pilot 通过前，不修改现有正式 experiment contract 的成功标准。

## 11. 创新性边界与近邻威胁

- SpaMEM 已研究动态空间 belief evolution，因此不能仅声称“研究新帧如何更新空间记忆”；
- SpatialMem 已使用墙、门、窗等结构锚点组织 3D memory，因此不能仅声称“结构化空间记忆”；
- ViSAGE 已使用延迟身份证据反向修正历史记录，因此不能仅声称“新证据可以改写旧记忆”；
- ChangingGrounding 已研究变化场景中的记忆驱动定位与重新探索，因此不能仅声称“场景变化时使用历史记忆”。

当前候选差异化是：

> 在 pose-aware metric spatial memory 上，根据新观测与旧 belief 的 structured innovation，对实体、遮挡、事件、Chart、Place 和空间关系执行最小充分、证据可追溯的局部语境修正，并显式评测修改传播与无关保持。

该主张仍需完成系统查新、强基线复现和 pilot 证伪，当前不得表述为已验证创新。

## 12. 接受 D-008 前必须回答

1. `SceneBelief` 与 Persistent World Memory 的提交边界是什么？
2. MVP 是否只更新 object/relation，还是同时允许 Chart/Place split/merge？
3. revision operators 使用规则、图网络、Transformer controller 还是分阶段混合方法？
4. oracle context delta 从模拟器直接生成，还是需要人工规则映射？
5. 主下游任务选择 context query 还是 lightweight navigation？
6. 相对 SpaMEM、SpatialMem、ViSAGE 和 ChangingGrounding，最小不可替代贡献能否由消融单独支持？

