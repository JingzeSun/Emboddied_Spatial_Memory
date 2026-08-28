# 从研究问题到可复现实验：渐进式研究主线

> 状态：`accepted research program / pre-implementation / not validated`
>
> 本页是项目唯一的阶段入口。`docs/09_integrated_direction_plan.md` 负责回答“论文方向是什么”，`docs/12_use_case_and_fixture_contract.md` 负责回答“怎样拆成可执行场景”，其余文件只展开某一阶段。

## 先说结论

项目当前不该直接训练模型。当前工作位于 **S1 概念合同** 与 **S2 场景分解**：先证明“动态冲突修订、版本链、受影响关系传播、停止边界”是四个可区分、可标注、可反驳的对象，再用无学习的 oracle/deterministic pilot 检查它们是否真的解决了现有在线对象记忆没有解决的问题。

整个研究按以下证据链推进：

```text
问题与文献缺口
  → 可操作概念和主张
  → 大场景与 WBS
  → micro fixtures 与 oracle
  → 无学习机制 pilot
  → 分阶段训练
  → 泛化与系统验证
  → 冻结主张、正式测试
  → 论文、复现与发布
```

任何阶段没有通过退出门槛，都应回到上一级修订；不能靠增加模型规模掩盖合同不清。

## 当前研究对象

### 核心问题

现有在线对象记忆善于把新检测关联、融合、检索出来，但当新证据与旧世界状态冲突时，通常没有显式回答：

1. 这是首次发现、可见性变化、关联歧义，还是旧 belief 真正失效？
2. 哪些节点和关系必须随之改变？
3. 哪些无关节点和关系必须保持不变？
4. 修改应传播到哪里，并依据什么停止？
5. 旧状态何时成立、何时失效、被什么证据取代？

### 核心方法主张

当前最可能成立的核心贡献是：

**Pose-Aware Structured Innovation + Affected-Subgraph Revision**

- `Structured Innovation`：把旧 `SceneBelief` 投影到当前位姿，与新 `ObservationGraph` 比较，区分实体、几何、身份、可见性和关系层的新证据。
- `Affected-Subgraph Revision`：预测受影响节点/边、typed operators、传播路径与停止边界，交给确定性、版本化 executor 执行。

四个核心概念不是同义词：

| 概念 | 可操作定义 | 直接解决的问题 | 不等于 |
|---|---|---|---|
| 动态冲突修订 | 新证据与已有世界状态不一致时，产生有类型、可追溯、可撤销的修改 | 应该改什么状态 | 从静态对象中找目标 |
| 版本链 | 保存状态成立区间、失效时刻、替代关系和证据来源 | 何时成立、被什么取代 | top-K 候选历史 |
| 受影响关系传播 | 从创新种子沿允许的语义依赖修改必要关系 | 一个变化必然牵连什么 | query 读取哪些关系 |
| 停止边界 | 明确哪些相邻关系没有修改依据，并约束传播停止 | 防止连带破坏 | attention 看多少 token |

### 必须分层的三种变化

- `graph_expansion`：拐角后第一次看到新表面、区域或对象；新增节点/边并连接旧图。
- `belief_revision`：可靠新证据反驳旧状态；关闭、重连或 supersede 旧版本。
- `ActiveContext update`：路线、任务和对话只改变同类实例候选排序；不删除长期世界记忆中的其他实例。

FARM 已覆盖在线对象记忆、关系谓词、同类候选排序与 top-K；这些是接口和强基线，不是本项目核心创新。详见 `literature/notes/farm_2026_DEEP.md`。

## 阶段总览与门禁

| 阶段 | 核心问题 | 必交付物 | 退出门槛 | 当前状态 |
|---|---|---|---|---|
| S0 研究治理 | 哪些是事实、决策、计划和结果？ | 状态标签、决策日志、数据隔离规则 | 文档无“计划冒充结果” | 已建立，持续执行 |
| S1 问题与概念 | 缺口是否真实，概念是否可区分？ | 文献矩阵、概念定义、主张边界、大场景 | G1：两名标注者能按定义区分事件类型；反例明确 | 进行中 |
| S2 场景 WBS | 大场景怎样变成可执行任务？ | 场景树、WBS dictionary、micro fixtures、oracle | G2：每个核心主张至少有正例、反例和 control | 进行中 |
| S3 无学习 pilot | 机制在理想输入下有必要且可执行吗？ | schema、deterministic executor、oracle E0–E2 | G3：图精确匹配；传播与保持同时优于局部/全图基线 | 未开始 |
| S4 分阶段训练 | 哪些部分值得学习？ | 数据合同、模型、损失、训练/验证协议 | G4：验证集上超过确定性基线且校准可接受 | 未开始 |
| S5 集成与泛化 | 噪声感知和新场景下还成立吗？ | 仿真/真实序列、鲁棒性、成本、外部基线 | G5：未见场景与感知噪声下主趋势保留 | 未开始 |
| S6 主张冻结与正式评测 | 证据是否足以支持论文表述？ | claim-evidence map、冻结配置、正式测试 | G6：不再用 test 选阈值/提示/方法 | 未开始 |
| S7 写作与复现 | 他人能否审查和复现？ | 论文、局限、环境、种子、完整结果 | G7：干净环境可重放，失败案例可检查 | 未开始 |
| S8 发布与迭代 | 哪些结论可发布，下一步是什么？ | artifact、模型卡/数据说明、后续决策 | G8：公开内容与证据强度一致 | 未开始 |

## S1：问题、论文痛点、概念与大场景

### 输入

- 同行评审文献与正式版本；
- 只作 novelty watch 的预印本，例如 FARM；
- 导师建议、人工场景直觉与反例；
- 当前 `09` 方法蓝图和决策日志。

### 工作

1. 把每篇工作拆成：它维护什么状态、如何吸收新帧、是否处理冲突、是否显式限制修改范围。
2. 把“动态”从口号改成事件类型、输入输出和失败条件。
3. 为每个概念写“解决什么 / 不解决什么 / 怎样被证伪”。
4. 选择能产生不同正确修改的场景，而不是只换视觉外观。

### 当前大轮廓应用场景

| 场景族 | 关键变化 | 正确行为 |
|---|---|---|
| 可见搬迁 | 椅子/箱子从 A 到 B | 关闭旧位置版本，建立新版本并更新必要关系 |
| 可靠缺席但去向未知 | 旧址可见且为空 | 旧位置关系失效，但不能编造新位置 |
| 遮挡/视野外 | 人被门或家具遮住 | 保留身份与最后可靠状态，不误判移除 |
| 关系级联 | 推车移动，箱子仍由它支撑 | 传播到依赖关系，保持无关物体不变 |
| 无关创新 | 远处灯具变化 | stop boundary 阻止传播到目标子图 |
| 图增长 | 转弯后首次看到建筑面/新区域 | 新子图连接已有 attachment boundary，不把它当旧状态纠错 |
| 同类指代 | 直行见箱 A、右转见箱 B，用户说“找箱子” | 两实例都保留；ActiveContext 偏向 B，必要时澄清 |

S1 的产物不是“方法有效”，而是一个可被 S2/S3 检查的合同。

## S2：从大场景到 WBS 和 micro fixture

场景分类不是完整 WBS。这里采用两层结构：

```text
论文主张（why）
  └─ 使用场景 UC（where）
      └─ 场景条件 SC（when）
          └─ micro fixture FX（what exact input/output）
              └─ 工程工作包 WP（how to build/test）
```

每个工作包必须填写：目标、输入、产物、依赖、负责人、验收条件；每个 fixture 必须填写：旧图、新观测、创新类型、affected/control/stop、操作序列、期望新图和失败变体。完整合同见 `docs/12_use_case_and_fixture_contract.md`。

G2 通过条件：

- 每个核心概念至少有一个正例、一个只改变单一因素的反例和一个无关 control；
- 人能仅凭合同写出唯一或受约束的期望图；
- `unknown`、`absent`、`occluded`、`out_of_fov` 不被混写；
- 图增长、世界修订、任务指代不会触发同一套写操作。

若 G2 失败，先缩减关系本体或场景范围，不能直接收集大规模数据。

## S3：无学习初步实验

### 核心问题

先不问模型能不能学，而问：**在 oracle perception、pose 和 association 下，这套表示与局部修订机制是否必要、可执行、可判分？**

### 最小实验顺序

1. **E0 schema wiring**：所有 fixture 能通过 schema，delta 能生成新版本且不原地覆盖。
2. **E1 visible relocation**：比较 append-only、local-slot、full-recompute、oracle affected-subgraph。
3. **E2 relation cascade**：检查必要边 recall 与无关边 preservation。
4. **E3 absence/occlusion counterfactual**：只改 `visibility/reliable_absence`，正确输出必须变化。
5. **E4 irrelevant innovation**：受影响集合应为空或极小。
6. **E5 graph expansion**：检查新子图 attachment，不计入 revision 主指标。
7. **E6 two-box ActiveContext**：检查候选召回、排序、澄清和未选实例保持。

### 初步指标

- exact graph match / schema validity；
- affected node/edge precision、recall、F1；
- required propagation recall；
- control-subgraph preservation、collateral revision rate；
- stop-edge accuracy；
- version/provenance validity；
- revision cost 与 edited-node ratio；
- 扩展场景：attachment precision/recall；
- 指代场景：candidate recall@K、accuracy@1、clarification calibration、nonselected preservation。

### G3 的真正含义

只有当 oracle affected-subgraph 同时满足下面三项，核心机制才值得进入学习阶段：

1. 比只改局部槽位更完整地更新必要关系；
2. 比全图重算更少破坏无关状态，且成本更低；
3. 版本和 provenance 能解释每次修改。

如果 oracle 自己都过不了，说明问题在定义、关系语义或 executor，不在神经网络。

## S4：初步验证成功后怎样训练

不要一开始端到端训练所有模块。推荐逐层去掉 oracle：

| 训练阶段 | 学习对象 | 仍使用的 oracle | 主要验证 |
|---|---|---|---|
| T1 innovation | 事件模式与可靠性 | pose、association、旧图 | 分类、校准、反事实一致性 |
| T2 scope/operator | affected nodes/edges、operator、stop | perception、association | scope F1、传播/保持、图执行成功率 |
| T3 association uncertainty | identity hypotheses 与 quarantine | pose、对象/关系观测 | ID switch、误合并、可恢复性 |
| T4 noisy perception | 联接实际 detector/depth/pose | fixture oracle 只作评测 | 噪声退化曲线、错误归因 |
| T5 multi-scenario curriculum | 跨场景策略与成本权衡 | 无训练时 oracle | 未见布局/关系/变化组合泛化 |

训练样本以 `base graph + observation + ContextDelta + target graph` 为单位。监督至少包括 innovation mode、affected/control/stop、operators、版本结果与不应修改集合；损失与指标必须同时奖励必要传播和无关保持，不能只优化 query accuracy。

数据分割以 `scene_family` 和变化模板分组，避免同一场景或轻微变体泄漏到训练与测试。阈值、prompt、关系权重和停止成本只在 train/validation 冻结，test 只运行一次正式协议。

G4 不通过时，依次判断：标签是否不一致、表示是否不可辨识、确定性规则是否已足够、模型是否只学了场景捷径。可以形成确定性系统论文或收缩主张，但不能把验证集失败包装为“需要更大模型”。

## S5：集成、扩展和外部有效性

按风险由低到高增加现实因素：

1. oracle 图输入上的组合泛化；
2. 仿真 RGB-D、已知 pose；
3. pose/depth/detection 噪声；
4. 长序列、循环观察和多次搬迁；
5. 真实采集序列与人工审查；
6. 若接口公平，接入 FARM-style mapper/retrieval 作外部基线。

这一阶段分开报告：感知失败、association 失败、revision 失败和 query 失败。验证是“是否解决预定使用问题”，不只是“代码是否按 schema 运行”。

## S6–S8：正式评测、论文和复现

### S6 主张冻结

- 写 `claim → experiment → metric → expected falsifier` 对照表；
- 冻结配置、随机种子、数据版本、代码版本和模型标识；
- 在正式测试前锁定统计检验、消融与失败报告；
- 若证据只能支持 oracle setting，就把论文主张限定在那里。

### S7 写作与复现

论文结构以问题和证据组织，而不是以代码模块组织。必须报告假设、局限、负结果、失败样例、计算资源和完整配置。代码发布前在干净环境重放关键表格；自动评审或代理指标不得称为 ground truth。

### S8 发布与下一轮

发布 schema、fixtures、配置、评测器和可运行基线；大型权重/数据通过外部存储提供。记录无法复现或不支持主张的结果，再决定是扩展到 ActiveContext/导航，还是继续收紧动态修订主线。

## 未来两周的正确起步顺序

1. 人工确认 `docs/12_use_case_and_fixture_contract.md` 中六个语义决策。
2. 为五个 P0 revision fixtures 和两个 P1 扩展 fixtures 写机器可读样例。
3. 实现 schema validator、versioned executor 和 exact-graph evaluator。
4. 只跑 E0–E2 oracle/deterministic pilot。
5. 用结果决定是否进入训练；现在不选大型 backbone。

## 人工必须确认的事项

- 同一对象搬迁后是同一 identity 的新状态，还是允许 identity 分裂假设？
- `near` 是存储边还是由几何派生；哪些关系允许传播？
- “可靠缺席”的可见性、遮挡、传感器和持续时间条件是什么？
- 哪些边构成因果依赖，哪些只是相关邻接？
- stop boundary 的人工真值怎样标；多种最小正确范围是否都接受？
- 歧义行动的代价多大时必须澄清？

这些不是实现细节，而是决定 ground truth 是否存在的研究假设。

## 文档导航

- 最高层方法蓝图：`docs/09_integrated_direction_plan.md`
- 场景 WBS 与 fixture 合同：`docs/12_use_case_and_fixture_contract.md`
- 方法定义：`docs/02_method_spec.md`
- 实验合同：`docs/03_experiment_contract.md`
- 数据与标注：`docs/04_dataset_spec.md`
- 关系推理：`docs/08_dynamic_context_revision.md`
- 实现路线：`docs/10_implementation_roadmap.md`
- 论文蓝图：`docs/11_paper_blueprint.md`
- 决策日志：`docs/06_decision_log.md`
- 一页执行清单：`CHECKLIST.md`

## 研究流程参考

本路线不是把工程流程生搬硬套到科研，而是组合三类成熟约束：

- Peffers 等人的 Design Science Research Methodology 将研究组织为问题识别、目标、设计开发、展示、评估和交流；这里对应 S1、S3/S4、S5/S6 和 S7/S8。来源：[A Design Science Research Methodology for Information Systems Research](https://design-science-research.de/en/publication/peffers-2007/)。
- NASA 的 WBS 指南强调分层拆解以及为每个元素记录目标、交付物和依赖；这里用于把主张拆到 fixture 和工程工作包。来源：[NASA Work Breakdown Structures That Include Software](https://swehb.nasa.gov/spaces/SWEHBVB/pages/32604325/7.05%2B-%2BWork%2BBreakdown%2BStructures%2BThat%2BInclude%2BSoftware)。
- 系统工程区分 verification（是否按合同建对）与 validation（是否满足预定使用）；这里分别对应 schema/executor 检查与真实动态场景验证。来源：[NASA Systems Engineering Handbook Appendix](https://www.nasa.gov/reference/system-engineering-handbook-appendix/)。
- 最终主张、局限与复现材料按主流 ML 审稿检查表约束。来源：[NeurIPS Paper Checklist](https://neurips.cc/public/guides/PaperChecklist)。
