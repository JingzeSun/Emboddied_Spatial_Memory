# Pose-Aware Affected-Subgraph Revision

面向动态室内具身环境的在线空间信念修订研究工作区。

> 当前研究方向已于 2026-08-27 接受；尚未实现，尚未验证。
> 最高层蓝图：[`docs/09_integrated_direction_plan.md`](docs/09_integrated_direction_plan.md)

## 核心问题

> 当新观测与旧空间信念产生结构化差异时，智能体如何在当前位姿下解释差异，只修订真正受影响的空间子图，并保持无关旧知识稳定？

核心方法由两部分组成：

1. **Pose-Aware Structured Innovation**：将旧 belief 投影到当前视角，在实体、几何、可见性和关系层比较新旧证据；
2. **Affected-Subgraph Revision**：预测 affected nodes/edges、typed operators、必要关系传播和 stop boundary，生成版本化 `ContextDelta`。

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

方法保留原始技术设想中的 observation/world 分离、SE(3)、ego-motion compensation、world structural directions、Local Charts、转弯 overlap、persistent slots 和 confidence/provenance，但把 EMA/soft gate 降为 typed operator 的低层实现。

## MVP 边界

- 编辑 object、surface/region、relation、visibility 和 event；
- Chart/Place 作为稳定锚点，暂不学习 split/merge；
- 人物只做 category + episode track；
- 首个下游是 structured context query；
- 先实现 oracle/deterministic vertical slice，再训练 GNN/graph Transformer；
- 不做 RGB reconstruction、完整导航闭环或无约束 LLM 图编辑。

两个哨兵场景：长期静止的人不能变成建筑结构；椅子搬迁、旧址可靠缺席、遮挡和 out-of-FOV 必须得到不同修订。

## 推荐阅读顺序

1. [`docs/09_integrated_direction_plan.md`](docs/09_integrated_direction_plan.md)：当前项目蓝图；
2. [`docs/01_research_question.md`](docs/01_research_question.md)：问题、假设、贡献与证伪；
3. [`docs/02_method_spec.md`](docs/02_method_spec.md)：算法与接口；
4. [`docs/08_dynamic_context_revision.md`](docs/08_dynamic_context_revision.md)：innovation、scope、operator 和 invariants；
5. [`docs/03_experiment_contract.md`](docs/03_experiment_contract.md)：基线、指标、消融和 test 规则；
6. [`docs/04_dataset_spec.md`](docs/04_dataset_spec.md)：counterfactual episode 与 oracle delta；
7. [`docs/10_implementation_roadmap.md`](docs/10_implementation_roadmap.md)：工程工作包；
8. [`docs/11_paper_blueprint.md`](docs/11_paper_blueprint.md)：论文故事和 claim-evidence map；
9. [`CHECKLIST.md`](CHECKLIST.md)：当前执行队列；
10. [`docs/06_decision_log.md`](docs/06_decision_log.md)：accepted/superseded 决策。

## 机器合同

- [`configs/mvp.yaml`](configs/mvp.yaml)：现行 MVP 配置；
- [`schemas/episode.schema.json`](schemas/episode.schema.json)：episode；
- [`schemas/observation_graph.schema.json`](schemas/observation_graph.schema.json)：单帧图；
- [`schemas/belief_graph.schema.json`](schemas/belief_graph.schema.json)：版本化 belief；
- [`schemas/context_delta.schema.json`](schemas/context_delta.schema.json)：图修订。

## 文献与旧合同

Related Work 只使用经官方来源核验的同行评审工作作为事实基石；预印本只做 novelty watch。见 [`literature/peer_review_audit.md`](literature/peer_review_audit.md)。

pre-D008 研究、方法、实验、配置、schema 和旧论文分析已归档到 [`docs/archive/pre_d008/`](docs/archive/pre_d008/README.md)。原始技术设想、PDF、原型图和导师 notes 未移动或覆盖。

## 当前阶段

当前是 **contract-migrated / pre-implementation**。下一个里程碑不是训练大模型，而是完成 schema-backed graph contracts、版本化 executor、四类 micro fixtures 和 E0 oracle wiring。
