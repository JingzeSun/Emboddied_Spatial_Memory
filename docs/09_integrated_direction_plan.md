# 动态空间语境修订：当前论文蓝图

> 状态：`accepted / current blueprint / pre-implementation / not validated`
>
> 接受日期：2026-08-27；v1.1 状态分层：2026-08-28。
>
> 决策依据：D-008、D-010、D-011、D-012、D-013、D-014。

本文只回答“论文为什么做、核心贡献是什么、证据应怎样支持它”。研究阶段和门禁见 [`../START_HERE.md`](../START_HERE.md)，场景与精确 fixture 见 [`12_use_case_and_fixture_contract.md`](12_use_case_and_fixture_contract.md)。原始设想仍是不可覆盖的 source artifact；pre-D008 合同保存在 `archive/pre_d008/`。

## 1. 主问题

> 当新观测与版本化空间信念发生结构化差异时，智能体如何在当前位姿和可见性条件下解释差异，只修改真正受影响的节点与关系，在必要依赖上传播，并在无关边界停止？

```text
O_t = Observe(frame, depth, pose, intrinsics, optional cues)
E_t = ProjectExpectedObservation(B_{t-1}, pose)
I_t = CompareStructured(O_t, E_t)
S_t = RetrieveAffectedSubgraph(B_{t-1}, I_t)
Δ_t = ProposeTypedDelta(B_{t-1}[S_t], I_t)
B_t = ApplyVersioned(B_{t-1}, Δ_t)
X_t = SelectActiveContext(B_t, task, route, dialogue, pose)
```

- `O_t`：当前帧 `ObservationGraph`；
- `B_t`：可追溯、可撤销、多假设的 `SceneBelief`；
- `X_t`：任务/路线/对话条件下的 `ActiveContext` 读取视图；
- `PersistentWorldMemory`：只接收经过巩固的版本化 belief。

## 2. 核心方法贡献

候选方法名：**Pose-Aware Affected-Subgraph Revision**。

### 2.1 Pose-Aware Structured Innovation

把旧 belief 投影到当前参考系，在节点、身份、几何、可见性和关系层比较新旧证据，输出结构化 innovation，而不是无类型的全局 feature residual。

innovation mode 至少区分：

- `reinforcement`：新证据支持旧 belief；
- `graph_expansion`：此前未知区域首次被观测；
- `belief_revision`：新证据反驳旧状态；
- `visibility_update`：遮挡、视野外或重新可见；
- `association_ambiguity`：不能可靠决定实体延续或新建；
- `sensor_inconsistency`：pose/depth/detector 互相矛盾。

### 2.2 Affected-Subgraph Revision

从 innovation seed 沿允许的关系依赖检索 affected nodes/edges、control nodes/edges、typed operators 与 propagation stop edges。控制器产生可审计 `ContextDelta`，确定性 executor 负责 schema、版本和 invariant。自由文本模型不能直接编辑图。

### 2.3 四个可检验概念

| 概念 | 论文要解决的具体问题 | 核心观测 |
|---|---|---|
| 动态冲突修订 | 新证据与旧状态不一致时改什么 | revision correctness |
| 版本链 | 状态何时有效、何时失效、被什么替代 | temporal/provenance validity |
| 受影响关系传播 | 一个状态变化必然牵连哪些依赖 | required propagation recall |
| 停止边界 | 传播在哪里必须停止 | control preservation / collateral edits |

这四者不等于在线对象存储、16 类查询谓词、同类实例 top-K、soft relation ranking 或 attention 稀疏化。

## 3. 三层状态边界

### 3.1 Graph expansion

拐角后看到以前不可见的新 surface/region/object，应创建节点/边并显式连接旧 Chart/region 的 attachment boundary。它是结构获取能力，不是旧 belief 纠错，当前只作必要支撑与扩展实验。

### 3.2 World belief revision

只有可靠新证据反驳旧状态时，才关闭、重连、失效或 supersede 旧版本。`unknown location` 不能被写成虚构新位置；`occluded/out_of_fov` 不能自动写成 removal。

### 3.3 ActiveContext update

直行看到箱 A、右转看到箱 B，用户再说“找箱子”时：

- 世界记忆继续保留 A 和 B；
- route recency、current place、dialogue focus 只重排候选；
- 若歧义会导致不同且有代价的行动，系统询问澄清；
- top-1 选择不能覆盖为世界事实。

这部分是下游验证/系统扩展，不是动态修订的主贡献。

## 4. 与抗噪声和既有工作的差异

抗噪声回答“这个证据是否可信”；本方法还要回答“可信证据要求怎样修改结构”。即使 detector、depth 和 pose 都是 oracle，搬迁仍会带来版本关闭、关系传播和 stop boundary，因此核心问题不退化为去噪。

FARM 已经覆盖在线对象记忆、关系谓词检索、soft ranking 和 top-K 保留。它可以作为 construction/retrieval 接口与强基线，但截至 2026-08-28 仅核验到预印本，不能作为同行评审事实基石。详见 `literature/notes/farm_2026_DEEP.md`。

## 5. MVP 边界与优先级

### P0：论文核心

- object/region/relation/visibility/event 图；
- episode 内 identity track；
- pose-aware expected observation；
- structured innovation；
- affected/control/stop；
- typed, deterministic, versioned executor；
- relocation、absence、occlusion、relation cascade、irrelevant innovation fixtures；
- oracle → deterministic → learned scope/operator。

### P1：必要支撑

- provenance、多假设、quarantine；
- Local Structural Chart/Place 作为稳定底座；
- graph expansion attachment；
- ActiveContext 及证据轨迹 query。

### 暂缓

- learned Chart/Place split/merge；
- 完整导航策略闭环；
- 跨人的长期 re-ID；
- 端到端 RGB reconstruction/generation；
- 开放世界类别持续学习；
- 无约束 LLM 图编辑。

## 6. 技术流程

```text
RGB / Depth / Pose / Intrinsics / Time
                 ↓
Perception + Geometry Frontend
                 ↓
ObservationGraph ───────────────┐
                               │ compare
PersistentWorldMemory → project expected observation
                               ↓
              Pose-Aware Structured Innovation
                               ↓
      affected seed → dependency propagation → stop
                               ↓
          deterministic / hybrid revision controller
                               ↓
       Versioned ContextDelta → revised SceneBelief
                      ↙                    ↘
             ActiveContext             consolidation
                                           ↓
                                PersistentWorldMemory
```

## 7. 哨兵场景与不变量

所有实现和正式结论必须覆盖：

1. 长期站立的人仍是 actor，时间长短不改变 ontology；
2. 椅子在可见新位置重现，旧位置版本失效、新版本建立；
3. 旧址可靠为空但去向未知，不编造新位置；
4. 遮挡和 out-of-FOV 不等于不存在；
5. 推车移动时必要依赖传播，无关对象保持；
6. 无关局部创新在 stop boundary 停止；
7. 转弯后首次显露的新子图正确 attachment，不误作 revision；
8. 两个同类箱子都保留，路线/对话只改变 ActiveContext 排序；
9. pose/depth 噪声进入 ambiguity/quarantine，不直接污染世界图。

## 8. 论文证据链

| Claim | 最低证据 | 失败意味着什么 |
|---|---|---|
| structured innovation 比标量变化分数信息更充分 | E1 分类、校准和 turning/occlusion 反事实 | 概念分型或感知合同失败 |
| affected scope 能找到最小充分修改范围 | E2 scope/operator、required propagation | scope 不是必要研究对象 |
| stop boundary 限制连带破坏 | E2/E5 preservation、collateral、stop accuracy | 停止机制无效 |
| 版本链可表达搬迁/缺席/遮挡 | E0/E4 target invariants、provenance | 状态本体或 executor 失败 |
| 局部修订比全图重算更有效率 | E7 latency、memory、edited ratio sweep | 收缩效率主张 |
| 修订改善下游语境读取 | E8 query 与 evidence trace | 下游价值未被证明 |

任何 claim 没有指标、对照、消融和反证条件，都不得写进 contributions。

## 9. 最小落地顺序

1. S1/S2：冻结概念、关系语义和 WBS fixtures；
2. S3：实现 schema、版本化 executor、oracle fixtures 和指标；
3. S3：比较 local-slot、full-graph 与 oracle affected-subgraph；
4. S4：训练 innovation，再训练 scope/operator/stop；
5. S5：逐步接入 perception、长序列与真实序列；
6. S6–S8：冻结主张和测试合同，写作、复现、发布。

详细门禁见 [`../START_HERE.md`](../START_HERE.md)，具体工作包见 [`10_implementation_roadmap.md`](10_implementation_roadmap.md)。

## 10. 当前可声明与不可声明

### 现在可以说

- 已接受研究问题、方法候选、状态分层和渐进式验证合同；
- 已有 schema/config 草案、场景合同和文献定位；
- 尚处 pre-implementation。

### 现在不能说

- 方法已经实现或优于基线；
- graph expansion、ActiveContext 或 FARM 对比已经验证；
- 任何百分比门槛或性能提升已经成立；
- 预印本结论是同行评审共识。

## 11. 文档职责

- `START_HERE.md`：唯一阶段入口；
- `01_research_question.md`：研究问题、假设和反证；
- `02_method_spec.md`：算法和接口；
- `03_experiment_contract.md`：实验和统计规则；
- `04_dataset_spec.md`：数据、split 和标注；
- `05_related_work_matrix.md`：文献定位；
- `06_decision_log.md`：接受、取代和拒绝的决策；
- `07_long_short_term_memory_block.md`：四层记忆边界；
- `08_dynamic_context_revision.md`：关系依赖、传播和停止；
- `10_implementation_roadmap.md`：工程工作包；
- `11_paper_blueprint.md`：论文故事和 claim-evidence map；
- `12_use_case_and_fixture_contract.md`：场景 WBS 与精确 fixture；
- `CHECKLIST.md`：当前执行队列。
