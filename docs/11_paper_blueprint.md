# 论文蓝图

> 状态：current writing blueprint；所有贡献均待实验验证
> 方法蓝图：`09_integrated_direction_plan.md`

## 1. 暂定标题

优先：

> **Pose-Aware Affected-Subgraph Revision for Online Embodied Spatial Memory**

备选：

- Structured Innovation for Local Revision of Embodied Spatial Beliefs
- Revising What Changed: Pose-Aware Local Graph Editing for Embodied Memory

标题暂不使用 `first`、`causal` 或 `world model`，除非对应实验和定义足够严格。

## 2. 核心故事

现有 spatial memory 工作擅长构建、聚合、检索或预测状态，但在线新观测到来时，常见选择是 append、average、slot update 或 recompute。真正困难的是：

1. 新旧差异究竟来自 viewpoint、occlusion、actor、relocation、absence 还是 sensor error；
2. 哪些旧节点和关系必须改变；
3. 必要影响传播到哪里；
4. 在哪里停止，避免改坏无关知识。

本文把更新重新定义为 pose-aware affected-subgraph revision。

## 3. 摘要逻辑

1. **背景**：具身智能体必须维护随视角和场景变化演化的空间记忆。
2. **缺口**：已有方法多聚焦 memory construction/readout，或用 append/average/object-state update；它们不显式监督关系级修订范围和停止边界。
3. **方法**：投影旧 belief，生成 structured innovation，检索 affected subgraph，预测 typed operators 和 stop edges，由版本化执行器应用。
4. **评测**：反事实历史组，联合测 necessary update、propagation、unrelated preservation、latency 和 cost。
5. **结果**：只在真实实验后填写，不预写提升百分比。

## 4. Contributions 模板

实验支持后最多写三条：

1. We formulate online embodied spatial-memory updating as pose-aware structured innovation followed by affected-subgraph revision.
2. We introduce a hybrid scope-and-operator controller with an evidence-preserving typed graph executor and explicit propagation stopping.
3. We provide a counterfactual evaluation protocol that jointly measures required edits, required relational propagation, unaffected-subgraph preservation, and revision cost.

若某条消融不成立，删除或降级，不以定性案例替代。

## 5. 章节结构

### 1 Introduction

- 场景：长期站立的人、被搬走的椅子；
- 抛出 preserve/update/isolate 不统一的问题；
- 指出“更新一个 slot”与“重组关系子图”的差别；
- 给出 formulation 和三条贡献。

### 2 Related Work

1. pose-aligned spatial memory construction；
2. persistent/dynamic scene memory；
3. selective context and historical correction；
4. changing-scene evaluation。

正式引用策略见 `05_related_work_matrix.md`。

### 3 Problem Formulation

- ObservationGraph、SceneBelief、PersistentWorldMemory、ActiveContext；
- ContextDelta；
- affected/control/stop；
- open-world unknown 与 version validity。

### 4 Method

4.1 Expected-observation projection
4.2 Pose-aware structured innovation
4.3 Affected-subgraph retrieval
4.4 Scope/operator controller
4.5 Versioned graph executor and consolidation

### 5 Data and Evaluation

- counterfactual history groups；
- oracle delta generation and human audit；
- baselines；
- metrics；
- implementation details。

### 6 Experiments

- E1 innovation；
- E2 scope/operator；
- E3 stationary actor；
- E4 relocation/absence/occlusion；
- E5 stop boundary；
- E6 robustness；
- E7 efficiency；
- E8 query。

### 7 Limitations

- oracle/estimated pose-depth gap；
- graph ontology dependence；
- delta annotation cost；
- ambiguity and open-world removal；
- Chart/Place split/merge deferred；
- no full navigation loop。

## 6. 主图

一张图必须同时显示：

1. old belief；
2. pose-conditioned projection；
3. current observation；
4. structured innovations；
5. affected subgraph 与 stop boundary；
6. typed ContextDelta；
7. revised belief/ActiveContext。

定性例子同时使用 stationary person/door 和 chair relocation，避免主图退化为“去噪”。

## 7. 主表

### Table 1 — Overall revision

方法 × Delta F1 / Propagation / Collateral / Query / Cost。

### Table 2 — Sentinel scenarios

方法 × stationary actor / occlusion / visible relocation / reliable absence / irrelevant innovation。

### Table 3 — Robustness and efficiency

pose/depth noise、graph size、history length、latency、memory。

### Table 4 — Ablation

projection、structured innovation、relation propagation、stop boundary、versioned executor、factorized state、learned controller。

## 8. Claim—证据映射

| Claim | 主表/实验 | 必要消融 | 失败时处理 |
|---|---|---|---|
| structured innovation 有效 | E1 | scalar residual | 降为工程表示 |
| affected scope 有效 | E2 | matched-slot/full recompute | 放弃核心方法 |
| stop boundary 有效 | E5 | no-boundary/no-preserve | 删除局部性 claim |
| factorized state 处理 actor | E3 | binary dynamic | 降为分析 |
| absence semantics 有效 | E4 | no visibility reasoning | 收缩到 relocation |
| 成本优势 | E7 | dense/full graph | 不声称效率 |
| 下游价值 | E8 | stale/no revision | 只报告内部指标并承认限制 |

## 9. Related Work 使用边界

同行评审基石：Hydra、Scene Graph Memory、ConceptGraphs、Khronos、KARMA、3D-Mem、Embodied VideoAgent、3DLLM-Mem。

并行预印本风险：SpatialMem、SpaMEM、ChangingGrounding、ViSAGE、R4DSG、DYNEMO-SLAM。它们只用于创新边界和实验设计；若投稿前获得正式接收，再更新引用角色。

## 10. 不应再出现的旧叙事

- “主要目标是降低 static memory contamination”；
- “核心方法是 dynamic gate + soft EMA”；
- “创新是 long/short-term dual memory”；
- “动态对象只是干扰者”；
- “只要新帧不覆盖旧帧就成功”；
- “所有 Chart/Place/导航模块都是第一篇论文贡献”。

抗污染、EMA、Chart 和长期 memory 都保留，但它们服务于 graph revision 主线。

## 11. 论文写作启动条件

- E0 exact executor 通过；
- 至少一个 oracle revision vertical slice；
- delta/control/stop 指标单元测试通过；
- Related Work 状态复核；
- 主图可以从真实 run log 自动生成；
- contributions 每条都有预注册实验。
