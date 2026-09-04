# Embodied Spatial Memory：双时间证据图后验修订

当前候选主线：在部分可观测、对象会移动且关系会变化的室内环境中，让智能体在**事件时间与证据到达时间不一致**、多来源证据可能冲突的条件下，只修改必要的世界事实及依赖关系，保留无关事实，并记录有效时间、事务时间和证据来源。

论文唯一母命题不是把这些模块拼起来，而是：

> **新证据怎样有限、可追溯地改变世界事实的语义状态、拓扑关系和有效时间，同时保护无关旧知识。**

动作预测提供 expected prior，结构区域与 association 提供证据归属，主动观察负责补证，Top-K 负责下游读取；它们已从当前训练方案移到后续集成层。核心创新假设只落在 **bi-temporal evidence-gated affected-subgraph posterior revision**。

当前训练型方法工作名为 **BEGR-Net**：用 event Transformer 编码乱序证据，用 typed relational graph encoder 表示事实依赖，用分层 decoder 先判断 `preserve / quarantine / commit`，提交时再选择 target 与 typed operator；dependency closure、valid interval、atomic version 和 provenance 仍由 deterministic executor 强制执行。详见 [`LEARNED_MODEL.md`](experiments/bounded_revision_validation/LEARNED_MODEL.md)。

核心不是“走一步就多加一个地图节点”，而是维护一条可追溯的闭环：

```text
旧世界信念 + 动作
  → 候选结构与预期观测
  → 新证据中的临时结构区域
  → 区域绑定到旧世界节点 / 新节点候选 / 歧义暂缓
  → 确认 / 扩展 / 修订 / 保留未知
  → 新版本世界信念
  → 下一步主动取证或任务行动
```

> 当前状态：D-022 已接受后验核心聚焦；BEGR-Net 是本轮重构后的候选训练主线，不是已接受或已验证的 contribution。HC-001–005、HC-011、HC-013、HC-015–018 仍需人工冻结后才能形成正式 benchmark；尚未实现，尚未训练，尚未验证。HC-006–010、HC-012、HC-014 属于后续闭环集成，相关 schema/config 仍保持不变。

## 后验核心实验包

当前方向已经收窄到 posterior revision。唯一核心实验包位于
[`experiments/bounded_revision_validation/`](experiments/bounded_revision_validation/README.md)，其中已拆开：

- [`PROTOCOL.md`](experiments/bounded_revision_validation/PROTOCOL.md)：固定 observation、prediction、association、visibility 与 dependency input，只替换 updater；
- [`BASELINES.md`](experiments/bounded_revision_validation/BASELINES.md)：不用论文自称判断“结构化”，而用 SA1–SA7 审计，并把主 updater 比较与结构表示消融分开；
- [`CRITERIA.md`](experiments/bounded_revision_validation/CRITERIA.md)：规则、公式、每项指标的白话含义与数字算例；
- [`NOVELTY_AND_FALSIFIERS.md`](experiments/bounded_revision_validation/NOVELTY_AND_FALSIFIERS.md)：与 2026-09-01 DSG 动态场景图工作的重叠、剩余假设和反证条件；
- [`DATASETS.md`](experiments/bounded_revision_validation/DATASETS.md)：数据轨道、标注缺口和最小切片。
- [`LEARNED_MODEL.md`](experiments/bounded_revision_validation/LEARNED_MODEL.md)：BEGR-Net 的输入输出、分层模型、精简 loss、训练规模、学习基线和反证检查。

候选实验环境分工如下，另以 symbolic event-stream generator 提供足量、可控的训练事务：

- **AI2-THOR Rearrangement**：可控改变对象位置、朝向和开闭状态，适合 scripted change、遮挡、可靠重观测及精确事件时间；`visible=false` 不得直接当可靠缺失；
- **3RScan + 3DSSG**：真实室内环境多次重扫、跨扫描固定实例 ID 与关系图，适合长期变化外部效度；通常只有变化时间区间，没有精确物理事件时刻；
- **Dyn-THOR / DSG**：直接审计动态 scene-graph 节点/边更新的重叠部分；目前按预印本 novelty watch 使用。

这些数据尚未下载或跑通，以上是实验职责分配，不是已验证结果。AI2-THOR、3RScan 与 Dyn-THOR
分别报告，不合并成一个总平均分。

首个应用叙事暂定为**共享室内设施中的移动资产与安全状态记忆**：例如仓库、实验室或医院后台区域内，推车、容器、门禁/通道状态会被人或机器人改变，多台相机与巡检机器人异步上报。论文不以“识别椅子”为贡献，而以迟到证据、可靠缺失、关系级联、冲突隔离和无关事实保护为困难来源；具体行业部署效果不在当前 claim 内。

## 唯一入口

先读 [`EXECUTE.md`](EXECUTE.md)。它只回答：**现在做什么、产物放哪里、做到什么算通过、下一步是什么。**

之后按顺序阅读，不跳级：

1. [`docs/01_research_contract.md`](docs/01_research_contract.md)：问题、创新概念和论文边界；
2. [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md)：场景怎样拆成机器可执行 fixture；
3. [`docs/03_pilot_protocol.md`](docs/03_pilot_protocol.md)：第一版代码和无学习实验怎么做；
4. [`docs/04_training_plan.md`](docs/04_training_plan.md)：pilot 成功后训练什么；
5. [`docs/05_formal_evaluation_and_paper.md`](docs/05_formal_evaluation_and_paper.md)：正式评测、论文和复现。

Accepted 决策统一记录在 [`docs/DECISIONS.md`](docs/DECISIONS.md)。机器接口以 [`configs/mvp.yaml`](configs/mvp.yaml) 和 [`schemas/`](schemas/README.md) 为准。文献准入以 [`literature/peer_review_audit.md`](literature/peer_review_audit.md) 为准。

## 人工确认与换对话

- 所有需要用户/研究者人工确认的问题，只能登记在 [`docs/DECISIONS.md` 的“人工确认中心”](docs/DECISIONS.md)；
- 每个 HC 的场景、输入输出、允许/禁止答案和评价候选在 [`docs/human_confirmation/`](docs/human_confirmation/README.md) 的同名工作表展开；工作表不维护状态；
- 每项使用稳定的 `HC-XXX`，同时映射到对应研究板块、schema/config/fixture 和运行日志；
- 其他文档只引用 HC ID，不维护第二份清单；
- 用户确认后必须追加 `D-XXX` 决策并更新 HC 状态，未明确回答不得视为同意；
- 新开对话时复制 [`docs/NEW_CHAT_HANDOFF_PROMPT.md`](docs/NEW_CHAT_HANDOFF_PROMPT.md)。它只负责交接上下文，日常工作仍从 `EXECUTE.md` 开始。

旧的 `docs/00–12`、旧入口和旧清单已完整归档到 [`docs/archive/pre_execution_v2_2026-08-28/`](docs/archive/pre_execution_v2_2026-08-28/README.md)，不再作为现行合同。原始技术设想和导师 notes 没有移动或覆盖。
