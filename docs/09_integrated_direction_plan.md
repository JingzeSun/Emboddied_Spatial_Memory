# 动态空间语境修订：当前项目蓝图

> 状态：`accepted / current blueprint`
> 接受日期：2026-08-27
> 实现状态：尚未实现；实验状态：尚未验证
> 决策依据：`06_decision_log.md` 的 D-008、D-010、D-011 和 D-012

本文是当前项目的最高层研究蓝图。原始技术设想仍是不可覆盖的 source artifact；当前研究问题、方法、实验、数据、论文与实现文件必须拆解并服从本蓝图。pre-D008 合同已移入 `docs/archive/pre_d008/`。

## 1. 一句话主问题

> 当新观测与旧空间信念产生结构化差异时，智能体如何在当前位姿下解释差异，只修订真正受影响的空间子图，并保持无关旧知识稳定？

形式化为：

[
O_t=operatorname{Observe}(I_t,D_t,T^w_{c_t},K,	ext{optional cues})
]

[
delta_t=operatorname{CompareStructured}
left(O_t,operatorname{Project}(B_{t-1},T^w_{c_t},K)ight)
]

[
S_t=operatorname{AffectedSubgraph}(B_{t-1},delta_t),qquad
Delta B_t=pi(B_{t-1}[S_t],delta_t)
]

[
B_t=operatorname{ApplyVersioned}(B_{t-1},Delta B_t),qquad
X_t=operatorname{SelectActiveContext}(B_t,g_t,T^w_{c_t})
]

(O_t) 是当前 ObservationGraph，(B_t) 是可撤销、多假设的 SceneBelief，(X_t) 是任务相关 ActiveContext，PersistentWorldMemory 只接收经过巩固的版本化 belief。

## 2. 核心方法贡献

候选方法名为 **Pose-Aware Affected-Subgraph Revision**，核心只有两个不可拆分的部分：

1. **Pose-Aware Structured Innovation**
   将旧 belief 投影到当前坐标系，在节点、身份、几何、可见性和关系层生成 `matched/new/occluded/reliably_absent/conflict/ambiguous` 结构化创新，而不是一个全局 feature residual。
2. **Affected-Subgraph Revision**
   从创新种子检索旧图依赖，预测需要修改的节点、边、操作符及传播停止边界，生成可审计的 `ContextDelta`，而不是每帧全图重算或仅更新当前 slot。

以下能力是必要支撑，不单独包装为主创新：

- pose/depth/geometry 对齐与 expected-observation projection；
- factorized dynamic state；
- 版本区间、supersedes 和 provenance；
- 抗污染、可见性保持和 quarantine；
- Local Structural Chart 与 Place 拓扑底座；
- context query。

## 3. 与旧方向的关系

旧的“抗污染空间记忆”不是被否定，而是成为新问题中的安全性质：

| 新证据情况 | 正确修订 | 旧抗污染能否覆盖 |
|---|---|---|
| 人暂时遮挡门 | 保留门，增加 actor、occupancy、occlusion | 只能覆盖“保留门” |
| 人长期静止 | actor 仍是 actor，motion 可 stationary，occupancy 可 persistent | 仅靠 motion gate 容易误固化 |
| 椅子搬到可见新位置 | 旧关系 supersede，新关系 add/relink | 不能，只抑制写入会冻结错误状态 |
| 椅子旧址可靠缺席、去向未知 | 旧位置失效，当前位置 unknown | 不能凭空推断新位置 |
| 新证据与远处旧图无关 | 修改局部并在依赖边界停止 | 需要显式 isolate/stop |

EMA、soft update 和 lifecycle 仍可作为 operator 的低层实现，但不再决定顶层修订范围。

## 4. 冻结的 MVP 边界

### 4.1 进入 MVP

- 实体、局部区域、空间关系、可见性和事件节点/边；
- episode 内实体 track，不做跨人的生物身份识别；
- 位姿感知的旧 belief 投影；
- structured innovation；
- affected node/edge 和 stop boundary；
- `REINFORCE/ADD/UPDATE_STATE/RELINK/INVALIDATE/SUPERSEDE/PRESERVE/QUARANTINE`；
- 结构化 context query；
- oracle scope、规则 scope、学习 scope 三阶段。

### 4.2 暂不进入 MVP

- Chart/Place 的 learned split/merge；Chart/Place 仍作为稳定空间底座；
- 完整导航策略闭环；
- 长期人物 re-ID；
- 端到端 RGB 重建或生成；
- 开放世界类别持续学习；
- 无约束 LLM 自由编辑图。

## 5. 当前技术流程

```text
RGB / Depth / Pose / Intrinsics / Time
                    │
                    ▼
       Perception + Geometry Frontend
  (latent, regions, instances, depth, flow, visibility)
                    │
                    ▼
             ObservationGraph
                    │
PersistentWorldMemory ── ProjectExpectedObservation(pose)
                    │                  │
                    └────────┬─────────┘
                             ▼
             Pose-Aware Structured Innovation
                             │
                             ▼
                 Causal Explanation Scores
                             │
                             ▼
                 Affected-Subgraph Retriever
              (seed → dependency propagation → stop)
                             │
                             ▼
                    Revision Controller
          (oracle → deterministic → hybrid learned)
                             │
                             ▼
              Versioned ContextDelta + SceneBelief
                         │                 │
                         ▼                 ▼
                    ActiveContext     Consolidation
                                           │
                                           ▼
                               PersistentWorldMemory
```

## 6. 哨兵场景

所有数据、方法测试和论文定性结果必须覆盖：

1. 人短暂停留、长期站立、离开；
2. 人遮挡门，门重新出现；
3. 椅子移动到可见新位置；
4. 椅子旧址可靠缺席、去向未知；
5. 物体仅被遮挡或处于视野外；
6. 无关局部出现新物体；
7. 转弯、回访和进入新地点；
8. 位姿或深度产生可控噪声。

核心不变量：

- 时间长短不能改变实体 ontology；
- 未看到不等于不存在；
- unknown 不得被写成确定新位置；
- 必要关系必须随变更传播；
- 无关子图必须保持；
- 每次修改都可追溯到 evidence 和 controller revision。

## 7. 方法落地顺序

### M0：契约与可执行样例

- 冻结 JSON schema、配置和 operator 语义；
- 手写最小 belief graph、observation graph 和 oracle delta fixtures；
- 实现 schema validator、versioned graph editor 和 delta metrics。

验收：不依赖神经网络即可执行 preserve、relocate、reliably-absent 和 isolate 四类修订。

### M1：Oracle Revision Vertical Slice

- 从 simulator state 生成 oracle scene graph；
- 人工定义 state diff → ContextDelta 映射；
- 使用 oracle association 和 oracle affected-subgraph；
- 跑 E0、E2 和 context query。

验收：oracle 条件下，必要修改完整且控制子图零连带修改；否则问题或指标定义有错。

### M2：Pose-Aware Structured Innovation

- 实现 projection、visibility 和 association；
- 比较 observation 与 expected observation；
- 输出校准后的创新类别和证据来源。

验收：E1 明确优于全局 residual/dynamic score，且不会把 turning 系统性误判为世界变化。

### M3：Predicted Affected Subgraph

- 规则候选生成；
- 图依赖传播；
- 显式 stop boundary；
- 比较 local slot、full recomputation、oracle scope 和预测 scope。

验收：E2/E5 同时改善 propagation completeness 和 collateral revision，而不是只缩小编辑量。

### M4：Hybrid Learned Controller

- GNN 或 graph Transformer 预测 scope、operator 和置信度；
- 保留 deterministic executor；
- 训练 `state/delta/relation/preserve/calibration/cost` 目标。

验收：学习控制器超过规则控制器，且在未见场景保持校准。

### M5：正式实验与论文

- 冻结 validation 阈值和 test split；
- 跑 E0–E8、强基线、消融、效率和失败案例；
- 完成 context query；
- 根据证据决定是否扩展 Chart/Place 或导航。

## 8. 论文证据链

| 论文 claim | 必须提供的证据 |
|---|---|
| Structured innovation 比动态分数更有信息 | E1 分类、校准、turning/occlusion 反例 |
| Affected-subgraph 能预测正确修改范围 | E2 delta P/R、propagation completeness |
| 方法能限制连带破坏 | E2/E5 collateral revision、control-subgraph preservation |
| 不把静止 actor 固化为结构 | E3 duration sweep 与 actor→structure error |
| 能区分 relocation、absence 与 occlusion | E4 分层结果和定性版本图 |
| 不是全图重算换准确率 | E7 latency、显存、编辑节点比例 |
| 修订对任务语境有用 | E8 context query |

任一主 claim 没有对应指标、对照和消融，都不得写入 contributions。

## 9. 论文创新边界

同行评审工作已经覆盖层次场景图、动态场景图、长短期记忆、持久对象状态、attention 读取和场景变化协调。因此不能声称：

- 首次构建结构化空间记忆；
- 首次保存动态对象；
- 首次用新帧更新旧记忆；
- 首次只读取/更新部分记忆；
- 首次区分长短期记忆。

当前可检验的最小新增量是：

> 在 pose-aware metric belief 上，将新旧观测差异显式结构化，并学习/预测最小充分的图编辑范围及传播停止边界，同时度量 necessary update 与 unrelated preservation。

最新预印本仍只用于 novelty watch；正式 Related Work 的事实基石遵守 D-009 和 `literature/peer_review_audit.md`。

## 10. 当前默认技术选择

| 项目 | 当前决定 |
|---|---|
| 图范围 | object/region/relation/visibility/event |
| 控制器 | deterministic candidates + learnable scope/operator |
| 执行器 | typed deterministic versioned graph editor |
| Delta 真值 | simulator state diff + deterministic mapping + human audit |
| 首个下游 | structured context query |
| 人物身份 | category-level actor + episode track |
| 缺席语义 | occluded / out_of_fov / absent_at_old_location / unknown_location / removed_from_scene |
| 阈值 | 只在 train/validation 冻结 |
| 测试集 | 只作最终报告，不调参 |

若这些决定后续改变，必须更新决策日志、受影响合同和 archive provenance。

## 11. 文档分工

- `01_research_question.md`：问题、假设、贡献和证伪边界；
- `02_method_spec.md`：算法和接口；
- `03_experiment_contract.md`：不可看测试结果后修改的评测规则；
- `04_dataset_spec.md`：场景、标注、oracle 和 split；
- `05_related_work_matrix.md`：论文定位和引用边界；
- `06_decision_log.md`：接受、取代和拒绝的决策；
- `07_long_short_term_memory_block.md`：Observation/Belief/Context/Memory 边界；
- `08_dynamic_context_revision.md`：innovation、scope、operator 和 invariants；
- `10_implementation_roadmap.md`：工程工作包和依赖；
- `11_paper_blueprint.md`：论文故事、图表和 claim-evidence map；
- `CHECKLIST.md`：当前执行队列。
