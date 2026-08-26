# 方法规范

本文把完整设想转换为可实现、可测试的接口。尚未确定的部分明确标为“待决定”。

## 1. 坐标约定

- `K`：camera intrinsic matrix。
- `T^w_c(t)`：把时刻 `t` 的 camera coordinate 转换到 world coordinate。
- `X_c(t)`：camera coordinate 中的 3D 点。
- `X_w = T^w_c(t) X_c(t)`。

从 `t` 时刻重投影到 `t+1`：

\[
X_{c_{t+1}} = (T^w_c(t+1))^{-1} T^w_c(t) X_{c_t}
\]

然后使用 `K` 投影到新图像。所有实现和测试必须遵守这一方向，不能只写含义不明确的 `RX+t`。

纯旋转时可使用：

\[
u_{t+1} \sim K R_{c_{t+1}\leftarrow c_t} K^{-1}\tilde{u}_t
\]

但仍需处理出视野、新进入视野和前景遮挡。

## 2. 四级表示层次

### Level 1 — World Space

保存长期世界坐标、全局拓扑以及 Chart 之间的相对关系。

### Level 2 — Local Structural Chart

一个 Chart 表示局部一致的结构区域，例如走廊、房间或转角邻域：

```text
Chart = {
  chart_id,
  chart_type,
  world_frame,
  dominant_directions,
  member_slot_ids,
  neighbor_relations,
  confidence,
  lifecycle,
  provenance
}
```

### Level 3 — Perspective-Aligned Observation Region

当前帧中的临时观测单元：

```text
ObservationRegion = {
  frame_id,
  region_id,
  image_mask_or_polygon,
  depth_statistics,
  camera_geometry,
  structural_direction,
  semantic_distribution,
  latent,
  visibility,
  dynamic_probability,
  uncertainty
}
```

它只回答“当前看到了什么”，不作为长期记忆 ID。

### Level 4 — Visual Latent Tokens

由 frozen DINOv2 patch features 在结构区域中聚合得到。MVP 使用归一化 weighted pooling；后续再比较 attention pooling、prototype set 或 feature distribution。

## 3. Persistent World Slot

长期 slot 的最小契约见 `schemas/memory_slot.schema.json`。概念字段包括：

```text
WorldSlot = {
  slot_id,
  slot_type,               # surface/object/portal/topology/dynamic
  chart_ids,
  world_geometry,
  latent_state,
  semantic_distribution,
  visibility_state,
  persistence_probability,
  dynamic_probability,
  static_confidence,
  pose_uncertainty,
  observation_count,
  first_seen,
  last_seen,
  lifecycle,
  provenance
}
```

几何、语义、视觉 latent 和时间状态分别维护，避免把所有变化都压入单个向量。

## 4. Observation Pipeline

```text
I_t
├── frozen DINOv2 ───────────────> dense latent features
├── depth estimator / RGB-D ─────> depth + confidence
├── line/plane/VP detector ──────> structural cues
├── optical flow estimator ──────> observed flow
└── optional detector/segmenter ─> semantic/instance evidence

pose + depth + K ────────────────> predicted ego-motion flow
observed flow - predicted flow ──> residual motion evidence

latent + depth + structure ──────> observation regions
```

Vanishing Point 是由 world structural direction 和当前 camera pose 产生的观测线索，不进入长期记忆作为固定像素坐标。

## 5. Frame-to-World Association

这是核心算法，不应只作为流程箭头。

对于 observation region `i` 和 world slot `j`，候选匹配分数至少考虑：

\[
s_{ij} =
w_g s_{geometry} +
w_p s_{projection} +
w_z s_{latent} +
w_s s_{semantic} +
w_t s_{temporal}
\]

并输出 association confidence `C_assoc(i,j)`。其中：

- `s_geometry`：平面、法向、深度范围或 3D 包围体一致性；
- `s_projection`：由 pose 预测的投影与当前 region 重叠；
- `s_latent`：视觉 latent 相似度；
- `s_semantic`：类别或属性兼容性；
- `s_temporal`：轨迹和最近可见状态的一致性。

实现必须处理：

- 一个旧 slot 被当前多个 region 切分；
- 多个 observation region 合并到同一 surface；
- 暂时遮挡后重现；
- 新 slot 创建与旧 slot 复活；
- 错误关联的撤销或降权。

MVP 可从 gated nearest-neighbor + assignment 开始；正式方法再比较 optimal transport、图匹配或 learned association。

## 6. Ego-motion Compensation 与动态概率

根据 pose、depth 和 `K` 计算静态世界应产生的 `f_ego`，再计算：

\[
f_{residual} = f_{obs} - f_{ego}
\]

动态概率不能只依赖 residual flow：静止行人、同向移动物体和错误深度都可能产生歧义。推荐组合：

```text
P_dynamic = Fuse(
  residual_motion,
  semantic_or_instance_evidence,
  depth_order_and_occlusion,
  multi_frame_consistency,
  track_history,
  estimator_uncertainty
)
```

MVP 先使用可解释的加权或规则模型，并保留每项证据；数据充分后再学习 fusion/gating。

## 7. Slot 生命周期与多时间尺度状态

外部仍可提供 Static Memory 和 Dynamic Memory 两个视图，但内部不能只有一次性的二分类：

```text
candidate
├── transient ──> decayed / retired
└── persistent ─> changed ─> confirmed replacement
                         └─> rejected change
```

- `candidate`：新结构或新 Chart，等待多帧确认；
- `transient`：短时实体或临时占据，带 TTL/decay；
- `persistent`：长期结构或稳定对象；
- `changed`：与历史状态冲突，但尚未确认是否永久变化；
- `retired`：长期不可见且有消失证据，不等同于暂时出视野。

这使系统能够区分行人遮挡、静止行人、门开合和椅子永久移动。

## 8. Soft Memory Update

对关联 `(i,j)` 定义：

\[
\alpha_{ij} =
C_{assoc}
C_{visibility}
(1-P_{dynamic})
C_{pose}
C_{measurement}
\]

latent 更新采用归一化形式：

\[
m_j^{t+1} = \operatorname{Normalize}((1-\alpha_{ij})m_j^t + \alpha_{ij}z_i^t)
\]

同时单独更新观测计数、几何协方差、时间状态和 provenance。完全遮挡意味着“没有新的静态证据”，而不是“原 slot 消失”。

待比较的 latent state：

1. 单 prototype EMA；
2. mean + covariance；
3. bounded prototype set；
4. key/value evidence bank。

## 9. Local Chart 创建与 Overlap

当前 region 对 Chart 使用 soft posterior：

\[
p(c\mid R_i^t, T^w_{c_t}, G_i^t)
\]

转弯时不同 region 可分别支持 Chart A、Chart B 或 corner relation；不使用整帧手工设定的 80/20 比例。

新 Chart 经以下证据逐步确认：

- 多帧几何一致；
- pose registration 一致；
- dominant direction 或局部拓扑一致；
- 与已有 Chart 无法合理合并；
- 有足够可追溯观测。

Chart edge 至少保存 relative transform、connection type、confidence 和 supporting observations。

## 10. 输出接口

MVP 输出三类查询：

1. `retrieve(slot_query)`：根据语义、外观或结构属性检索 world slot；
2. `query_topology(chart_a, chart_b)`：返回连接和相对关系；
3. `project_memory(T, K)`：把当前可见的 world memory 投影回 observation frame。

导航策略是下游消费者，不与记忆更新逻辑强耦合。

## 11. 必测失败模式

- pose 漂移和尺度漂移；
- depth 边界错误；
- 极端斜视角和 motion blur；
- stationary pedestrian；
- 重复纹理和相似门；
- region split/merge；
- 非 Manhattan、曲面或开放空间；
- 长期真实变化被错误冻结；
- 错误新建或错误合并 Chart。

## 12. 建议实现模块

```text
src/
├── perception/       feature, depth, flow, structural cues
├── geometry/         transforms, projection, ego-flow
├── regions/          observation-space partition and pooling
├── association/      region-to-slot and region-to-chart matching
├── memory/           slot state, lifecycle, update, provenance
├── charts/           chart creation, overlap, topology
├── queries/          retrieval and projection interfaces
└── evaluation/       memory and downstream metrics
```

## 13. 向动态语境修订的接口迁移（proposed）

若 D-008 接受，本文件中的几何、region、association、WorldSlot 和 Chart 不被推翻，而成为语境修订的感知与长期存储底座。需要新增：

```text
src/
├── belief/            multi-hypothesis SceneBelief and version intervals
├── innovation/        expected-observation projection and structured comparison
├── revision/          affected-subgraph retrieval, controller and operators
├── context/           task/pose-conditioned ActiveContext selection
└── evaluation/        delta, propagation, preservation and collateral metrics
```

第 8 节的 EMA 只作为 `REINFORCE/UPDATE_STATE` 的低层数值操作，`(1-P_dynamic)` 不再作为所有动态证据的总决策。一个长期静止的人与一把被搬动后静止的椅子都说明：entity mobility、current motion、persistence、visibility 和 persistent change 必须解耦。完整接口流和迁移边界见 `09_integrated_direction_plan.md`。
