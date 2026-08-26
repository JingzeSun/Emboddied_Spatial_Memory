# 研究问题、假设与贡献边界

> 合同版本：v1.0
> 状态：研究方向已接受；方法尚未实现；假设尚未验证
> 上位蓝图：`09_integrated_direction_plan.md`

## 1. 主问题

机器人接收连续观测：

[
o_t=(I_t,D_t,T^w_{c_t},K,a_{t-1},	ext{optional semantics/flow})
]

已有空间信念图 (B_{t-1}=(V,E))。本项目研究：

> 能否通过当前位姿下的 structured innovation，预测新证据真正影响的节点、关系、操作符和传播停止边界，从而以最小充分的局部图修订形成新空间语境，并保持无关历史知识稳定？

目标输出不是新帧摘要，而是：

[
Delta B_t=
{	ext{operations},V_{	ext{affected}},E_{	ext{affected}},
E_{	ext{stop}},	ext{confidence},	ext{provenance}}
]

## 2. 中心假设

### H1 — Structured innovation

在相同 perception、pose 和 association 输入下，对象/关系/可见性级 structured innovation 比全局 feature residual 或单一 dynamic probability 更准确地区分 viewpoint、occlusion、new entity、relocation、reliable absence 和 sensor inconsistency。

### H2 — Affected-subgraph scope

显式预测 affected nodes/edges 与 propagation stop boundary，比 full recomputation、global EMA 和 local-slot-only update 获得更高的 delta precision/recall、传播完整性和无关子图保持率。

### H3 — Factorized dynamics

将 entity mobility、current motion、persistence、visibility 和 change state 解耦，能降低长期静止 actor 被固化为结构的错误，并更好地区分椅子搬迁、旧址缺席与遮挡。

### H4 — Efficient context revision

受影响子图上的版本化修订能在不牺牲 context query 正确率的情况下，降低每帧编辑节点比例、时延和峰值显存。

## 3. 候选论文贡献

1. 一种 pose-aware structured innovation 表示，把旧 belief 的 expected observation 与新 ObservationGraph 在实体、几何、可见性和关系层对齐比较。
2. 一种 causally scoped affected-subgraph revision 方法，联合预测编辑范围、typed operator 和传播停止边界，由确定性版本化执行器应用。
3. 一套反事实 revision 评测合同，联合度量 necessary update、necessary propagation、unrelated preservation、revision latency 和 cost。

以上是待验证 claim，不得在实验前写成已经证明的贡献。Factorized state、provenance、Chart 和 context query 是使上述贡献可实现、可评测的支撑。

## 4. 冻结的 MVP 输入与输出

### 输入

- RGB；
- metric depth 或明确来源的估计 depth；
- camera intrinsics；
- `T_world_camera` pose 及其来源/置信度；
- timestamp；
- 可选 flow、semantic、instance evidence。

### 图范围

- node：object、surface/region、event；
- edge：spatial、containment、visibility/occlusion、identity/track、event participation；
- Chart/Place 只作为稳定锚点，不在 MVP 学习 split/merge。

### 输出

- `StructuredInnovation`；
- `ContextDelta`；
- versioned `SceneBelief`；
- task-conditioned `ActiveContext`；
- 结构化 context query answer 与 evidence trace。

## 5. 非目标

- 不生成或修复照片级 RGB；
- 不把完整导航策略训练作为第一篇论文条件；
- 不做人脸识别或长期生物身份追踪；
- 不在 MVP 学习 Chart/Place split/merge；
- 不以“更大 VLM”代替图修订算法；
- 不允许 LLM 无 schema、无 operator 地自由改写 memory；
- 不声称单目 depth/pose 是 ground truth。

## 6. 关键不变量

1. Observation、SceneBelief、ActiveContext 与 PersistentWorldMemory 不得混为同一状态。
2. camera motion 必须通过 pose/geometry 解释，不能直接当成 scene change。
3. 长期静止不能改变 actor ontology。
4. `occluded/out_of_fov/reliably_absent` 必须可区分。
5. 未知去向不能被写成虚构位置。
6. 原始 evidence 不覆盖；修订使用版本和有效时间。
7. 每个 edit 必须能追溯到 episode、frame、association、visibility 和 controller revision。
8. 测试集不得用于阈值、prompt、baseline 或模型选择。

## 7. 主任务与次任务

- 主任务：`affected_subgraph_revision`；
- 第一验证任务：`structured_context_query`；
- 次级鲁棒性：viewpoint、turning、pose/depth noise；
- 后续外部效度：lightweight navigation。

## 8. 证伪条件

出现以下任一结果，应削弱或放弃核心 claim：

- oracle affected-subgraph 不能明显优于 local-slot-only update；
- structured innovation 不优于简单 residual/dynamic score；
- scope 变小只带来漏改，propagation completeness 显著下降；
- 方法通过“什么都不改”取得低 collateral revision；
- stationary actor、relocation 和 reliable absence 无法同时正确处理；
- 优势只在 oracle pose/depth 下存在；
- full recomputation 在相同输入下准确率和成本均不差于本方法；
- context query 不受修订质量影响。

## 9. 论文一句话

> We study how pose-aware structured innovations should trigger minimal sufficient, evidence-traceable revisions of an embodied spatial belief graph, including where relational propagation must stop.
