# 研究决策日志

状态：`proposed`、`accepted`、`superseded`、`rejected`。accepted 决策改变时，必须记录原因、影响以及是否接触 test 信息。

## D-001 — Observation 与 Memory 分离

- 日期：2026-08-23
- 状态：accepted
- 决策：当前帧使用 ObservationGraph；长期状态使用 world-coordinate graph/version，不复用 image region 作为长期 ID。
- 影响：所有跨帧写入必须经过 association。

## D-002 — Vanishing Point 不是长期世界坐标

- 日期：2026-08-23
- 状态：accepted
- 决策：保存 world structural directions/planes；VP 由当前 pose 投影产生。
- 影响：转弯不冻结 memory，VP 可移动或离开 FOV。

## D-003 — Local Structural Charts

- 日期：2026-08-23
- 状态：accepted
- 决策：使用 Local Chart/Place 和 overlap 表示走廊、转角和房间。
- 当前范围：MVP 将 Chart/Place 作为稳定检索与传播边界，不学习 split/merge。

## D-004 — 不以 RGB Reconstruction 为目标

- 日期：2026-08-23
- 状态：accepted
- 决策：保存 task-relevant geometry、semantics、latent、uncertainty、relation 和 temporal version，不把 RGB decoder 作为 MVP 必需模块。

## D-005 — 多时间尺度 Slot 生命周期

- 日期：2026-08-23
- 状态：superseded by D-011
- 原决策：candidate/transient/persistent/changed/retired。
- 取代原因：单轴 lifecycle 无法表达 actor mobility、stationary motion、persistent occupancy、visibility 和 relation change；现采用 factorized dynamic state + versioned operators。

## D-006 — 主要论文任务为 Memory Robustness

- 日期：2026-08-23
- 状态：superseded by D-008/D-011
- 原决策：memory robustness 为主，query/navigation 为次。
- 取代原因：抗污染只能覆盖 PRESERVE，不能定义 UPDATE/PROPAGATE/STOP。

## D-007 — Latent State 形式

- 日期：2026-08-23
- 状态：accepted as baseline, not core contribution
- 决策：MVP 底层 state update 使用 normalized EMA；bounded prototypes 作为消融。顶层是否修订由 ContextDelta 决定。

## D-008 — 新帧驱动的动态空间语境修订

- 提出日期：2026-08-26
- 接受日期：2026-08-27
- 状态：accepted
- 用户确认：`09_integrated_direction_plan.md` 作为当前蓝图推进，旧合同归档。
- 决策：主问题升级为 online spatial context revision；区分 ObservationGraph、SceneBelief、ActiveContext 和 PersistentWorldMemory；由 pose-aware structured innovation 触发局部版本化图修订。
- 保留：D-001 至 D-004。
- 影响：D-005/D-006 被取代；研究、方法、实验、数据、配置、schema、论文与实施计划全部迁移。
- 研究状态：方向已接受，不代表方法已实现或验证。

## D-009 — Related Work 同行评审准入门槛

- 日期：2026-08-26
- 状态：accepted
- 决策：只有官方 proceedings、出版社或正式接收页核验的同行评审工作可作为 Related Work 事实基石；预印本/投稿为 novelty watch。
- 影响：正式写作检查 `peer_review_status`、`venue_verification_url` 和 `related_work_usage`。

## D-010 — 核心贡献收敛

- 提出日期：2026-08-27
- 接受日期：2026-08-27
- 状态：accepted
- 决策：核心方法收敛为 `Pose-Aware Structured Innovation + Affected-Subgraph Revision`。
- 支撑：factorized state、provenance、versioning、anti-contamination、Chart/Place。
- 评测要求：同时度量 necessary update、necessary propagation、unrelated preservation、latency 和 cost。

## D-011 — MVP 默认技术决策

- 日期：2026-08-27
- 状态：accepted
- 决策来源：用户接受 `09_integrated_direction_plan.md` 为当前蓝图。
- 图范围：object、surface/region、relation、visibility、event；Chart/Place 不学习 split/merge。
- 控制器：deterministic candidate generation + learnable GNN/graph-Transformer scope/operator；typed deterministic executor。
- Oracle：simulator state diff + deterministic ontology mapping + human audit。
- 下游：structured context query；导航延期。
- 人物：category-level actor + episode track，不做长期生物身份。
- 缺席语义：区分 occluded、out-of-FOV、absent-at-old-location、unknown-location、removed-from-scene。
- 阈值：证据类别人工定义；数值只在 train/validation 冻结。
- 影响：`configs/mvp.yaml` 与 current schemas 按此重建。

## D-012 — 合同迁移与归档

- 日期：2026-08-27
- 状态：accepted
- 决策：pre-D008 的 01–09 文档、Checklist、MVP config、episode/memory-slot schema、旧文献综合和 PPT content 移入 `docs/archive/pre_d008/`；原路径建立 current contracts。
- 原因：避免 proposed/accepted 与新旧主任务同时显示；Git 和 archive 双重保留追溯。
- 数据使用：迁移发生在 pre-implementation 阶段，没有使用 test 结果改变问题、阈值或成功门槛。
- 影响：archive 为 superseded/只读；当前规范入口是 `09`、`03`、`configs/mvp.yaml` 和 `schemas/`。

## 新决策模板

```text
## D-XXX — 标题

- 日期：YYYY-MM-DD
- 状态：proposed
- 背景：
- 决策：
- 备选方案：
- 原因：
- 影响：
- 是否接触 test 信息：
- 验证方式：
```
