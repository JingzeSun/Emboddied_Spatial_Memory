# 动态空间语境修订：方向整合与实验路线

> 状态：`proposed`。本文用于整合现有抗污染空间记忆与 D-008 动态语境修订方向，不表示方法已经实现或验证。D-008 未接受前，`03_experiment_contract.md`、现有 schema 与 `configs/mvp.yaml` 仍是冻结基线。

## 1. 方向结论

候选主问题应从“怎样让长期空间记忆不被动态物体污染”上移为：

> 当新观测与旧空间信念发生结构化差异时，系统如何在当前位姿下解释这种差异，只修订真正受影响的局部子图，并保留不应被改写的旧知识？

候选核心方法名为 **Pose-aware Affected-Subgraph Revision**，由两个不可拆开的部分组成：

1. **Pose-aware Structured Innovation**：把旧信念投影到当前观测坐标系，与新观测进行对象、身份、可见性、几何和关系层面的比较，得到结构化创新，而不是一个全局残差或噪声分数。
2. **Affected-Subgraph Revision**：由创新预测哪些旧节点和关系应被修改、影响应传播到哪里、在哪里停止，并用显式操作符产生可审计的 `ContextDelta`。

抗噪声仍然重要，但被重新定位为局部修订中的一种结果：证据不足或被遮挡时执行 `PRESERVE`。完整方法还必须能执行 `UPDATE`、`RELINK`、`INVALIDATE`、`SUPERSEDE` 和 `QUARANTINE`，并控制修改范围。因此它不是把旧抗污染模块换一个名字。

## 2. 现有材料覆盖与真正缺口

两个重要场景已经存在，不再重复造例子：

| 哨兵场景 | 已有覆盖 | 整合后承担的作用 |
|---|---|---|
| 一个人长时间甚至始终站在门口 | `02_method_spec.md`、`07_long_short_term_memory_block.md`、`08_dynamic_context_revision.md` | 检查“运动状态”是否错误改变“实体类型”；人可以 `stationary + persistent occupancy`，但不能被固化成墙或门的一部分 |
| 椅子被永久搬走 | `02_method_spec.md`、`03_experiment_contract.md`、`07_long_short_term_memory_block.md`、`08_dynamic_context_revision.md`、`CHECKLIST.md` | 检查系统能否从暂存冲突进入持久结构修订，而不是永久冻结旧槽位 |

还需要补清一个关键分叉：

- **椅子搬到可见的新位置**：旧位置关系被 `SUPERSEDE/INVALIDATE`，新位置关系被 `ADD/RELINK`，两者由同一变更事件连接。
- **椅子只在旧位置可靠缺席，去向未知**：只能更新为“旧位置失效/物体位置未知/可能离开场景”，不能凭空创造新位置。
- **椅子被遮挡或在视野外**：保留旧信念并记录可见性原因，不能把未看见当成搬走。

这三种情况决定了方法是否真的在做“从新证据重组旧语境”，而不只是阈值式抗噪。

## 3. 方向迁移中的冲突与处理

| 现有表述或设计 | 与新方向的冲突 | 处理方式 |
|---|---|---|
| 主问题是长期记忆抗污染 | 只能解释为什么不写，不能解释该改什么、改多远 | 降为核心修订问题的必要安全目标和主要对照实验 |
| 以 `dynamic_probability` 作为写入负门控 | 静止的人、被搬动后静止的椅子会使“动态/静态”二分失效 | 将实体可动性、当前运动、持续性、可见性和变更状态解耦 |
| WorldSlot 上做 EMA/软更新 | 缺少关系变更、版本、因果范围和传播边界 | 保留为某些 `REINFORCE/UPDATE_STATE` 操作符的底层数值实现，不再承担顶层决策 |
| 当前观测直接写长期记忆 | 混淆观测、暂定信念、任务上下文与稳定世界记忆 | 分成 `Observation → SceneBelief → ActiveContext → PersistentWorldMemory` |
| 旧实验只测污染率、保留率与恢复 | 无法判断是否改对局部结构，也无法看到连带破坏 | 增加 delta、受影响子图、传播完整性和 collateral revision 指标 |
| 当前 schema 只标槽位与事件 | 不能监督图编辑和因果范围 | D-008 接受后再扩展；在此之前先做不破坏旧合同的小型 revision pilot |

## 4. 优先级重新排列

### P0：必须形成的核心方法贡献

- 当前位姿下的结构化创新表示。
- 受影响子图的检索、编辑与传播停止机制。
- 明确证明它优于全量重算、仅追加、全局软更新和仅槽位生命周期管理。

### P1：核心方法成立所需的基础能力

- 位姿对齐和旧信念到当前视图的可见性投影。
- 跨帧对象/区域关联及不确定性。
- 多假设 `SceneBelief`、版本区间和 provenance。
- 可审计的 `ContextDelta` 与修订操作符。

这些是必要支撑，不应各自包装成平行的五个“主创新”。

### P2：最小哨兵场景

1. 人短暂停留、长时间站立和离开。
2. 门被人暂时遮挡，随后重新出现。
3. 椅子搬到已观察到的新位置。
4. 椅子在旧位置持续可靠缺席，但新位置未知。
5. 当前出现与任务无关的新物体，不应引发远处结构改写。
6. 转弯或新地点造成大视角变化，不能误判为世界被整体替换。

### P3：学习型控制器

先用显式规则和 oracle affected-subgraph 验证问题定义与指标，再比较规则、GNN、Transformer 或混合控制器。若 P0 在 oracle 条件下都不能带来收益，不应先扩大模型规模。

### P4：后续扩展

- `Chart/Place` 的 split/merge 与拓扑重组。
- 导航策略闭环。
- 特定人的长期身份记忆。
- 开放世界的语义增量学习。

这些有价值，但不进入第一篇方法论文的最小闭环。

## 5. 统一技术流程

```text
RGB / Depth / Pose / Time
        │
        ▼
Perception & Geometry
(regions, semantics, depth, flow, visibility)
        │
        ├──────────────┐
        ▼              │
ObservationGraph       │
                       ▼
PersistentWorldMemory ── ProjectExpectedObservation(pose)
                               │
                               ▼
                 Pose-aware Structured Innovation
       (match / new / occluded / reliably absent / conflict / ambiguity)
                               │
                               ▼
                     Causal Explanation Head
       (viewpoint / occlusion / actor / relocation / removal / sensor error)
                               │
                               ▼
                    Affected-Subgraph Retriever
                 (seed nodes → relation propagation → stop)
                               │
                               ▼
                       Revision Controller
        (REINFORCE / ADD / UPDATE_STATE / RELINK / INVALIDATE /
                 SUPERSEDE / PRESERVE / QUARANTINE)
                               │
                               ▼
                 SceneBelief + versioned ContextDelta
                     │                         │
                     ▼                         ▼
        task-conditioned ActiveContext     Consolidation
                                               │
                                               ▼
                                   PersistentWorldMemory
```

建议的第一阶段技术栈：

- 感知：现有 DINOv2/检测或分割特征、深度、位姿和光流接口继续使用。
- 表示：对象/区域节点加空间关系、可见性和事件边；`PyTorch Geometric` 或等价稀疏图张量均可，先保持接口中立。
- 创新计算：几何投影与硬可见性规则负责候选生成，学习模块负责匹配置信度与歧义评分。
- 子图修订：先做“规则候选 + 可学习边界/操作符”的混合控制器；它比端到端自由生成更容易监督和审计。
- 存储：节点与边保留 `valid_from/valid_to`、confidence、provenance、supersedes，不原地抹掉历史。
- 查询：先用结构化 context query 评估，不立刻接完整导航系统。

## 6. 最小接口与需求

### 功能需求

1. 同一帧必须能同时出现 `new`、`reliably_absent`、`occluded` 和 `unchanged` 节点。
2. 修订结果必须是节点/边/属性级 delta，并包含传播停止位置。
3. 每个编辑必须能追溯到观测、位姿、匹配、可见性判断和控制器版本。
4. 低置信冲突进入 `candidate/quarantine`，不能立即覆盖已确认历史。
5. 长时间静止不能自动把 actor 变为 fixed structure。
6. 持续可靠缺席可以让旧关系失效，但未知位置不能被虚构。
7. 当前任务只读取 `ActiveContext`，不要求每次新帧重新编码完整世界图。

### 数据与标注需求

- 每帧相机位姿、可见/遮挡/视野外/可靠缺席标签。
- 跨帧实体与区域对应关系。
- 关键时刻的 oracle scene graph 与 `ContextDelta`。
- 受影响节点、受影响边、应停止传播的边界。
- 变更事件的起止、原因类别和证据来源。
- 至少一部分人工审计的反例与歧义样本。

### 非功能需求

- 记录配置、随机种子、数据版本、代码版本和模型标识。
- 报告失败信息和不支持假设的案例。
- 测试场景不得用于调阈值或选择提示词。
- 训练、验证、测试按场景/地点拆分，避免同一环境历史泄漏。

## 7. 实验拆解及每项实验的目的

| 实验 | 核心比较 | 主要指标 | 目的 |
|---|---|---|---|
| E0 Oracle wiring | oracle delta/affected-subgraph 与系统执行结果 | 执行一致率、图完整性 | 先证明图编辑器和评测没有接错 |
| E1 Structured Innovation | 像素/特征残差、动态分数 vs 结构化创新 | innovation 分类 F1、校准、可见性错误率 | 证明“新东西”被解释成不同类型的结构证据 |
| E2 Affected Subgraph | 全量重算、全局 EMA、局部槽位更新、oracle scope、预测 scope | delta P/R、propagation completeness、collateral revision、revision cost | 证明系统知道该改哪里、何处停止 |
| E3 Stationary Actor | 停留时长与遮挡位置分层 | actor→structure 误转率、背景保留率、离开后恢复 | 防止“站得久就成为环境结构” |
| E4 Relocation/Removal | 临时遮挡、可见搬迁、旧址可靠缺席 | 变更确认延迟、错误失效率、新旧关系一致性 | 区分不该改、该换关系和只能标未知的情况 |
| E5 Irrelevant Innovation | 在无关局部引入新物体/关系 | 非相关子图改写率、查询稳定性 | 测传播停止和局部性 |
| E6 Viewpoint/Place | 转弯、回访、新地点 | viewpoint robustness、错误全局修订率 | 防止把视角变化当成世界变化 |
| E7 Efficiency | 图规模、历史长度、受影响范围扫描 | latency、峰值显存、编辑节点比例 | 回答是否真的避免每帧全图重算 |
| E8 Context Query | 旧状态、新状态、遮挡状态和关系查询 | query accuracy、temporal consistency | 验证修订对下游语境读取有用 |

最低基线应包括：append-only、full recomputation、pose-warped EMA、slot lifecycle only、local slot revision、oracle affected-subgraph 和完整方法。

## 8. 需要人工设计而不能交给模型代替的问题

1. **世界本体**：什么是实体、区域、关系、事件；人长期站立时哪些属性允许变化、哪些绝不能变化。
2. **“可靠缺席”的证据标准**：需要几个视角、多长时间、何种可见率，哪些条件只允许判定 unknown。
3. **正确修订范围**：每个场景中哪些节点/边应改，哪些相邻关系必须保留，传播在哪里停止。
4. **错误代价**：误删门、延迟更新椅子、短暂保留过时关系，三者的代价排序是什么。
5. **反事实**：如果人没出现、椅子没移动或相机没有转弯，正确图应是什么；这决定因果对照是否可信。
6. **主任务边界**：第一篇只做对象/关系/可见性/事件，还是把 Chart/Place split/merge 一起纳入。
7. **下游目标**：先以 context query 为主，还是必须证明导航收益。
8. **成功门槛**：哪些指标的最低提升足以支持核心 claim；门槛须在正式测试前冻结。

## 9. 待人工确认的建议默认项

| 决策 | 建议默认项 | 不确认的影响 |
|---|---|---|
| D-008 是否升级为候选主方向 | 先接受为候选主方向，以 revision pilot 结果决定最终论文主线 | 研究问题、合同和实现优先级无法正式迁移 |
| MVP 图范围 | 对象、区域、关系、可见性、事件；暂缓 Chart/Place split/merge | 标注和控制器复杂度可能失控 |
| 控制器路线 | 规则生成候选 + GNN/Transformer 预测 scope/operator 的混合式 | 纯规则上限低；端到端模型难审计 |
| Delta 真值 | 仿真器状态生成 + 确定性映射 + 人工抽检 | 无法可信评估 affected-subgraph |
| 首个下游 | 结构化 context query | 导航会引入策略学习混杂因素 |
| 人的身份粒度 | 类别级 actor + episode 内 track，不做生物身份识别 | 会把问题扩张为 re-ID/隐私任务 |
| 缺席语义 | 区分 absent-at-old-location、unknown-location、removed-from-scene | 模型会把“没看到”误写成确定删除 |
| 时间阈值 | 人工定义证据类别，具体阈值只在训练/验证集确定 | 容易用测试集调参并造成数据泄漏 |

## 10. 文档和工程迁移顺序

1. 先确认第 9 节的主方向、MVP 范围和标签语义。
2. 建一个小型 revision pilot，只验证 E0–E5；旧 MVP 合同保持可复现。
3. pilot 可行后，将 D-008 改为 `accepted`，再扩展 `episode.schema.json`、memory/belief schema 和配置。
4. 实现 `StructuredInnovation`、`AffectedSubgraphRetriever`、`RevisionController` 与 `ContextDelta`。
5. 冻结新实验合同、成功门槛与拆分后，才运行正式测试。
6. 最后再决定是否加入 Chart/Place 重组、学习型长期巩固和导航闭环。

当前不直接修改正式 schema/config 的原因不是保守，而是这些文件代表已接受的可复现实验合同；在关键人工语义没有冻结前先改代码，会把研究假设偷偷写进实现。

## 11. 文献定位与引用边界

当前文献分两层使用，不能因方向改变而混写：

- **Related Work 基石**：只使用已经由官方 proceedings、出版社或正式接收页核验同行评审的工作。Hydra、Modeling Dynamic Environments with Scene Graph Memory、Khronos、Embodied VideoAgent、3DLLM-Mem 等可用于论述场景图组织、动态状态、长期协调和选择性读取的已有基础。
- **创新边界预警**：SpaMEM、SpatialMem、ViSAGE、ChangingGrounding、R4DSG 等当前仍按 `novelty_watch_only` 管理。它们用于避免方向重合、设计强基线和收紧 claim，不用于支撑“领域已经证明”或性能结论；状态变化时必须重新核验。

因此本项目不能声称“首次动态更新空间记忆”“首次结构化空间记忆”或“首次用新证据纠正历史”。可检验的候选增量必须收敛到：在 pose-aware metric memory 中显式预测结构化创新、必要修订范围和传播停止边界，并同时评测 necessary update 与 unrelated preservation。详细准入记录见 `literature/peer_review_audit.md` 和 `05_related_work_matrix.md`。
