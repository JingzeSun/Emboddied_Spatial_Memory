# 问题形式化

## 1. 在线观测

时刻 `t` 的观测为：

\[
o_t=(I_t,D_t,K,T^w_{c_t},a_{t-1},t^{obs},t^{recv},Q_t),
\]

其中 `Q_t` 保存 pose/depth/measurement uncertainty。第一轮允许 simulator/oracle depth 与 pose，但所有方法共享同一输入。

## 2. Projective Structural Tokens

冻结视觉 backbone 产生 patch features `F_t`。tokenizer 用 depth、surface/plane、object、portal、occlusion、结构线和可选 VP cue 形成临时 regions：

```text
ObservationRegion = {
  region_id, frame_id, image_support, point_support,
  structural_role, latent_set_or_summary, semantics,
  geometry, visibility, dynamic_probability,
  pose_confidence, measurement_confidence, evidence_refs
}
```

一个 world surface 可对应多个 observation regions；一个 region 也可能混合多个 world nodes。region ID 只在 observation 内有效。

## 3. 持久世界状态

`S_t` 至少包含：

- `PlaceNode` 与 `TransitionEdge`：世界拓扑和实际 traversal 分开；
- `LocalChart`：走廊、房间、转角等局部坐标与 dominant directions；
- `PersistentSlot`：surface/object/portal/structural anchor；
- `TransientTrack`：actor、临时障碍和短期 occupancy；
- `Fact/RelationVersion`：geometry、semantic、visibility、contain/support/connect 等状态；
- `Evidence/Transaction`：每次创建、绑定和修订的来源与双时间。

latent、geometry、semantics、lifecycle 和 uncertainty 分字段维护，不能压成一个无法审计的向量。

## 4. Predict-project

旧 memory 在当前 pose 或候选 action 下产生预期观测：

\[
\hat R_t=\Pi_\theta(S_{t-1},T^w_{c_t},K,a_{t-1}).
\]

每个 projected node 给出 image/3D support、expected visibility、结构角色、latent distribution 与 occlusion hypothesis。几何可确定部分使用解析投影；未知 visibility/appearance transition 可学习。

预测不是确认事实。未被当前证据支持的 future/frontier hypothesis 保持 candidate，不能直接写 confirmed memory。

## 5. Association `A_t`

association 是 observation region 与 world node 间的 set-valued relation：

- `BIND`：与已有 node 一致；
- `NEW`：没有可信旧匹配，进入候选 birth；
- `REACTIVATE`：与 retired/temporarily absent node 重新关联；
- `SPLIT`：一个 observation region 对应多个 world nodes，或旧 node 需拆分假设；
- `MERGE`：多个 observation regions 对应同一 world node；
- `UNRESOLVED`：多解接近，保留 hypothesis，不强制匹配。

一对一 Hungarian 只是基线；oracle 可以包含多个等价 association sets。

## 6. Memory Transaction `U_t`

transaction 由 gate、scope 与 typed operations 构成：

```text
gate: BIND | BIRTH | REACTIVATE | SPLIT | MERGE | REVISE | PRESERVE | QUARANTINE
scope: affected nodes/edges + protected controls + stop boundary
operations:
  CREATE_NODE | CREATE_EDGE | REINFORCE | UPDATE_STATE |
  RELINK | RETRACT | REPLACE | PRESERVE | QUARANTINE
valid_time: point or interval
evidence_set: direct supporting observation/event IDs
```

原 ESGBU 的 `Delta G/M/tau/Z` 对应 `REVISE` 及部分 `BIRTH` 分支，不再覆盖全部 association/growth 问题。

## 7. 确定性执行器

executor 必须检查：

- world/node/region 坐标系和引用合法；
- persistent ID 唯一，split/merge lineage 无环；
- candidate 未过确认门不能成为 confirmed；
- occluded/out-of-FOV 不自动 retired；
- unknown location 不带虚构 geometry；
- protected scope 逐字段保持；
- valid/transaction time 合法；
- 每个写操作有 provenance；
- 整个 transaction 原子提交并记录拒绝原因。

同一 canonical transaction 方法共享 executor，且投影前后结果分报。

## 8. 控制边界

主比较固定 backbone、depth、pose、base segmentation/proposals 与输入帧；只替换 tokenizer 或 memory updater 中被研究的一个因素。强感知前端另作 `front-end × updater` 二因素表。

第一篇不主张新的 SLAM、检测、开放本体或完整导航。成功必须同时包含 binding、growth、retention/revision、预测和效率，而不是“最后找到了目标”。
