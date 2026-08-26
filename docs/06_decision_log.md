# 研究决策日志

状态：`proposed`、`accepted`、`superseded`、`rejected`。

## D-001 — Observation 与 Memory 分离

- 日期：2026-08-23
- 状态：accepted
- 决策：透视区域只表示当前 observation；长期状态使用 world-coordinate persistent slots。
- 原因：固定图像区域随转弯和视角改变，不能保持实体身份。
- 影响：所有模块必须显式进行 frame-to-world association。

## D-002 — Vanishing Point 不是长期世界坐标

- 日期：2026-08-23
- 状态：accepted
- 决策：保存 world structural directions/planes，并由当前 pose 投影产生 VP。
- 原因：VP 会随 camera orientation 移动或离开 FOV。
- 影响：结构解析输出必须能与 world directions 对齐。

## D-003 — Local Structural Charts

- 日期：2026-08-23
- 状态：accepted
- 决策：用多个局部 Chart 表示走廊、转角和房间，转弯时允许 soft overlap。
- 原因：单个 perspective grid 不能覆盖拐角、T junction 和多房间连接。
- 影响：需要 Chart lifecycle、Chart association 和 topology edge。

## D-004 — 不以 RGB reconstruction 为目标

- 日期：2026-08-23
- 状态：accepted
- 决策：保存 task-relevant geometry、semantics、latent、uncertainty 和 temporal state，不训练 RGB decoder 作为 MVP 必需模块。
- 原因：研究重点是长期空间组织与更新，而不是视觉生成质量。
- 影响：论文表述仍需承认 depth/pose/geometry registration 的存在。

## D-005 — 多时间尺度 slot 生命周期

- 日期：2026-08-23
- 状态：proposed
- 决策：在 Static/Dynamic 两个外部视图下，引入 candidate、transient、persistent、changed、retired 状态。
- 原因：二分类无法充分处理静止行人、门开合和物体永久移动。
- 待验证：相比简单双库，是否改善 persistent-change F1 且不过度增加复杂度。

## D-006 — 主要论文任务

- 日期：2026-08-23
- 状态：proposed
- 决策：以 memory robustness 为主任务，以结构查询或导航作为次级 downstream validation。
- 原因：同时端到端优化导航、QA 和规划会稀释方法贡献。
- 待决定：最终选择 retrieval/query 还是 lightweight navigation 作为第一下游任务。

## D-007 — Latent state 形式

- 日期：2026-08-23
- 状态：proposed
- 候选：normalized EMA、mean/covariance、bounded prototypes、key/value evidence bank。
- 决策标准：污染、重现一致性、真实变化响应、存储量和时延。

## D-008 — 新帧驱动的动态空间语境修正

- 日期：2026-08-26
- 状态：proposed
- 背景：导师建议动态对象和短期出现不应只被视为静态记忆干扰，而应被学习、记录并参与当前场景解释。现有研究问题和实验合同仍主要以 static memory contamination 为中心。
- 决策：评估将论文主问题升级为 online spatial context revision。明确区分 Observation、Persistent World Memory、SceneBelief 和 ActiveContext；根据新观测与旧 belief 的 pose-aware structured innovation，定位受影响子图并执行版本化 revision operators。
- 备选方案：继续以 memory robustness 为主任务；或只增加 dynamic track/lifecycle 而不引入 context-level revision。
- 原因：单纯抗污染只能解释“为什么不写”；动态场景还要求表示 actor、occupancy、event 和 persistent relation change，并解释新证据为什么以及在多大范围内改变旧空间信念。
- 影响：若接受，D-001 至 D-004 保持不变；D-005 扩展为关系和事件级 belief revision；D-006 需重新决定；需要新增 context/delta schema、动态反事实 episode、update/preserve/isolate 指标和强近邻基线。现有 `03_experiment_contract.md` 在接受前不变。
- 验证方式：先完成 SpaMEM、SpatialMem、ViSAGE、ChangingGrounding 查新；构建带 oracle scene-state delta 的小型 pilot；比较 append-only、全量重算、slot-only lifecycle 和局部 subgraph revision，报告必要修改、无关保持、传播完整性、修正延迟和计算成本。
- 详细提案：`08_dynamic_context_revision.md`。

## D-009 — Related Work 同行评审准入门槛

- 日期：2026-08-26
- 状态：accepted
- 决策：只有能从会议/期刊官方 proceedings、出版社页面或正式 OpenReview 接收页核验的论文，才能标记为 `foundation` 或 `adjacent` 并进入 Related Work 的事实论述；只有预印本、投稿记录或未核实 venue 声明的工作统一标记为 `novelty_watch_only`。
- 原因：避免用未经同行评审的最新工作支撑论文结论，同时仍保留它们对创新边界和方向重合的预警价值。
- 影响：`literature/library.csv` 新增 `peer_review_status`、`venue_verification_url` 和 `related_work_usage`；正式写作前必须复核状态，预印本不得被表述为领域共识。
- 验证方式：核对 `literature/peer_review_audit.md` 中的官方来源；投稿前重新审计全部 `novelty_watch_only` 条目。

## D-010 — 动态语境方向的候选优先级与迁移门

- 日期：2026-08-27
- 状态：proposed
- 背景：现有文档已覆盖“长时间静止的人”和“永久搬走的椅子”，但仍以抗污染、slot 生命周期和 soft update 为主线；若直接叠加 D-008，会形成多个互相竞争的主问题和无法对应实验的贡献列表。
- 决策：候选核心方法收敛为 `Pose-aware Structured Innovation + Affected-Subgraph Revision`；抗污染、factorized dynamic state、版本记录和 provenance 作为必要支撑。先做对象/区域、关系、可见性和事件级 revision pilot，是否加入 Chart/Place split/merge、导航闭环和特定人物长期身份留待后续。
- 备选方案：维持 memory robustness 为唯一主线；或同时实现完整地点拓扑修订与导航策略。
- 原因：局部结构编辑同时覆盖“该改、该保持、该隔离”，能把抗噪声纳入更强问题；先限制图范围可降低标签、归因和系统复杂度。
- 影响：D-006 需在 D-008 接受时改写；`01`–`04` 和 `07` 增加迁移说明，但正式 schema、配置和实验合同暂不改变。两个既有例子升级为跨方法、数据与实验的哨兵场景，并区分可见搬迁、可靠缺席和遮挡/视野外。
- 验证方式：按 `09_integrated_direction_plan.md` 完成 E0–E5 pilot；比较全量重算、全局 EMA、slot lifecycle、local revision、oracle scope 和预测 scope，报告 delta、传播、无关保持、延迟和成本。
- 待确认：D-008 是否升级为候选主方向、MVP 图范围、控制器路线、delta 真值映射、首个下游、身份粒度、缺席语义和成功门槛。

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
- 验证方式：
```
