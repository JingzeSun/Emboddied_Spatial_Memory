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

## D-013 — 图增长、世界修订与任务指代分层

- 日期：2026-08-28
- 状态：accepted
- 用户确认：将转弯后新发现节点/关系、同类多实例与对话指代偏置落实到当前关系设想；导师推荐论文确认为 FARM，而非 ODIN。
- 背景：新帧可能只是揭示此前未观测区域，也可能反证旧 belief；用户当前更想找哪个同类实例，还可能只改变任务语境。三者若共用一种“更新”，会把图增长误当纠错，或让对话偏好污染长期世界事实。
- 决策：
  1. `graph_expansion` 只新增可靠观测到的节点/边，并通过显式 attachment 连接既有 Chart/region/subgraph；未观测区域不预先写成虚构世界节点；
  2. `belief_revision` 只在新证据支持冲突、状态变化或关系失效时关闭、重连或 supersede 旧版本；
  3. `ActiveContext` 保存任务、位姿、路线和对话条件下的候选指代分布；排序变化不删除 `SceneBelief/PersistentWorldMemory` 中未被选中的同类实例；
  4. world、observation/pose、temporal/version 与 query/discourse relation 分层；`left/right/front/behind` 必须带 reference frame，camera-relative 关系默认只在 ObservationGraph/ActiveContext 中派生；
  5. 歧义较大且行动代价不等价时请求澄清，不把 top-1 猜测提交为世界事实。
- FARM 影响：FARM 已覆盖在线对象级记忆、关系谓词检索、同类实例候选排序和 top-K 保留；这些能力只作接口、baseline 与 novelty boundary，不能单独作为本项目核心贡献。FARM 截至本日仅核验到 arXiv/项目页/代码，按 D-009 记为 novelty watch，不作为同行评审事实基石。
- 合同影响：方法、实验、数据、配置、图 schema、ActiveContext schema、论文蓝图和文献定位升级到 v1.1；增加 corner reveal 与 two-box discourse fixtures/指标。
- 是否接触 test 信息：否；项目仍为 pre-implementation，修改来自概念场景和文献核验。
- 验证方式：手写 graph-expansion 与双木箱对话 fixtures；分别评测 attachment、candidate recall/ranking、clarification 与 world-belief preservation；主 revision claim 仍由 E1/E2/E4/E5/E7 证据决定。

## D-014 — 渐进式研究阶段与门禁成为唯一执行主线

- 日期：2026-08-28
- 状态：accepted
- 用户确认：现有信息过于散落；应按“问题/论文痛点 → 创新概念与定义 → 大场景 → WBS → 初步实验 → 分场景训练 → 正式评测/论文/复现”层进组织，并补齐初学者尚不熟悉的后续科研步骤。
- 决策：
  1. 根目录 `START_HERE.md` 成为唯一阶段入口，定义 S0–S8 和 G1–G8；
  2. `09` 只保留论文级问题、核心方法、优先级与 claim-evidence 链；
  3. `12` 负责 `claim → use case → scenario → fixture → work package`，每项含输入、产物、依赖、验收与反证；
  4. 在 oracle/deterministic G3 通过前不训练 learned controller；训练按 innovation、scope/operator、association uncertainty、noisy perception 分阶段去掉 oracle；
  5. verification（是否按合同实现）与 validation（是否解决预定动态场景）分别记录；正式 test 只在主张、配置、阈值和 checkpoint 冻结后运行。
- 性质：研究治理与执行顺序调整，不改变 D-008/D-013 的核心方法主张。
- 是否接触 test 信息：否；项目仍无正式实现或实验结果。
- 影响：README、索引、蓝图、WBS、实现路线、检查清单、实验/数据合同和论文写作均按阶段门禁引用；旧合同仍在 archive/Git 中可追溯。

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
