# Pose-Aware Affected-Subgraph Revision

面向动态室内具身环境的在线空间信念修订研究工作区。

> 当前研究方向与渐进式执行合同已经接受；项目处于 S1/S2、尚未实现、尚未验证。
>
> 从这里开始：[`START_HERE.md`](START_HERE.md)
>
> 论文蓝图：[`docs/09_integrated_direction_plan.md`](docs/09_integrated_direction_plan.md)

## 核心问题

> 当新观测与旧空间信念产生结构化差异时，智能体如何在当前位姿下解释差异，只修订真正受影响的空间子图，并保持无关旧知识稳定？

核心方法由两部分组成：

1. **Pose-Aware Structured Innovation**：将旧 belief 投影到当前视角，在实体、几何、身份、可见性和关系层比较新旧证据；
2. **Affected-Subgraph Revision**：预测 affected nodes/edges、typed operators、必要关系传播和 stop boundary，生成版本化 `ContextDelta`。

`graph_expansion`、`belief_revision`、`visibility_update` 与 `association_ambiguity` 必须分型；任务、路线和对话只改变 `ActiveContext` 的候选排序，不删除未被选中的长期世界实例。

抗污染、factorized dynamic state、provenance、Local Structural Chart 和长期记忆都是必要底座，不单独作为论文主创新。

## 方法流程

```text
RGB / Depth / Pose / Time
        ↓
ObservationGraph ← Projected Expected Observation
        ↓
Pose-Aware Structured Innovation
        ↓
Affected-Subgraph Retrieval (seed → propagate → stop)
        ↓
Hybrid Scope/Operator Controller
        ↓
Versioned ContextDelta → SceneBelief
        ├── ActiveContext / structured query
        └── Consolidation → PersistentWorldMemory
```

## MVP 边界

- 编辑 object、surface/region、relation、visibility 和 event；
- Chart/Place 作为稳定锚点，暂不学习 split/merge；
- 人物只做 category + episode track；
- 先做 oracle/deterministic mechanism pilot，再训练 GNN/graph Transformer；
- 不做 RGB reconstruction、完整导航闭环或无约束 LLM 图编辑。

核心哨兵场景是搬迁、可靠缺席、遮挡、关系级联和无关创新。图增长与双木箱 ActiveContext 是 P1 支撑场景：前者检查新子图 attachment，后者检查路线/对话只重排候选而不污染长期世界图。

## 推荐阅读顺序

1. [`START_HERE.md`](START_HERE.md)：问题到投稿/复现的 S0–S8 阶段与门禁；
2. [`docs/09_integrated_direction_plan.md`](docs/09_integrated_direction_plan.md)：当前论文蓝图；
3. [`docs/12_use_case_and_fixture_contract.md`](docs/12_use_case_and_fixture_contract.md)：场景 WBS 与精确 fixture；
4. [`docs/01_research_question.md`](docs/01_research_question.md)：问题、假设、贡献与证伪；
5. [`docs/02_method_spec.md`](docs/02_method_spec.md)：算法与接口；
6. [`docs/08_dynamic_context_revision.md`](docs/08_dynamic_context_revision.md)：innovation、scope、operator 和 invariants；
7. [`docs/03_experiment_contract.md`](docs/03_experiment_contract.md)：基线、指标、消融和 test 规则；
8. [`docs/04_dataset_spec.md`](docs/04_dataset_spec.md)：counterfactual episode 与 oracle delta；
9. [`docs/10_implementation_roadmap.md`](docs/10_implementation_roadmap.md)：工程工作包；
10. [`docs/11_paper_blueprint.md`](docs/11_paper_blueprint.md)：论文故事和 claim-evidence map；
11. [`CHECKLIST.md`](CHECKLIST.md)：当前执行队列；
12. [`docs/06_decision_log.md`](docs/06_decision_log.md)：accepted/superseded 决策。

## 机器合同

- [`configs/mvp.yaml`](configs/mvp.yaml)：现行 MVP 配置；
- [`schemas/episode.schema.json`](schemas/episode.schema.json)：episode；
- [`schemas/observation_graph.schema.json`](schemas/observation_graph.schema.json)：单帧图；
- [`schemas/belief_graph.schema.json`](schemas/belief_graph.schema.json)：版本化 belief；
- [`schemas/context_delta.schema.json`](schemas/context_delta.schema.json)：图增长/修订；
- [`schemas/active_context.schema.json`](schemas/active_context.schema.json)：任务、路线与对话条件下的候选读取视图。

## 文献与旧合同

Related Work 只使用经官方来源核验的同行评审工作作为事实基石；预印本只做 novelty watch。见 [`literature/peer_review_audit.md`](literature/peer_review_audit.md)。FARM 当前属于 novelty watch，精读见 [`literature/notes/farm_2026_DEEP.md`](literature/notes/farm_2026_DEEP.md)。

pre-D008 研究、方法、实验、配置、schema 和旧论文分析已归档到 [`docs/archive/pre_d008/`](docs/archive/pre_d008/README.md)。原始技术设想、PDF、原型图和导师 notes 未移动或覆盖。

## 当前阶段

当前是 **S1/S2 contract integration / pre-implementation**。下一门禁是 G2：人工冻结六项 ground-truth 语义并写完 P0/P1 micro fixtures；G3 oracle mechanism pilot 通过前不训练大模型。
