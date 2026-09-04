# 05 — 正式评测、论文与复现

> 状态：`future protocol / no formal results`

本文件只在合同、pilot 和训练门通过后执行。当前内容是计划，不是实验结论。

## 1. 系统集成顺序

逐层增加现实风险，不把定位、感知、预测、修订和规划误差一次混在一起：

当前 posterior-first 候选顺序先于下面的完整闭环：symbolic event streams → AI2-THOR oracle/noisy tracks → 3RScan/Dyn-THOR secondary tracks。每一级只在前一级留下未被强基线解释的差异时继续。

1. oracle graph + oracle action/pose 的完整 belief loop；
2. simulator geometry + known pose，验证结构预测和假设生命周期；
3. simulator RGB-D + known pose，接入 observation mapping；
4. deterministic structural regions + region-to-world binding，隔离观测绑定错误；
5. learned structural predictor 与 evidence assimilation；仅在消融支持时学习 region binder/tokenizer；
6. estimated pose/depth/detector 及噪声 sweep；
7. 重复走廊、回环、长序列和多次回访；
8. 外部对象变化、遮挡、搬迁和关系传播；
9. 离散短视界主动取证与任务规划；
10. 真实序列与人工审查；
11. 接口公平时接入 FARM-style mapper/retrieval。

分别报告 perception、pose、prediction、association、assimilation、revision 和 planning 失败，不能只给一个端到端成功率。

### 1.1 核心因果比较

核心表必须固定相同的 candidate fact graph、evidence events、identity/visibility、typed dependency 与 candidate retrieval，只替换 posterior revision controller。否则更强 detector、layout、Top-K 或 action policy 带来的收益不能归因于本项目。

主实验输入输出固定为：

~~~text
输入：candidate fact subgraph + evidence events
    + observed/received time + source/group + typed dependencies
输出：preserve/quarantine/commit + targets/operators
    → executor closure + valid time/version + provenance
~~~

主判据同时要求 necessary updates 完整和 protected controls 不变。

## 2. 正式实验包

当前 P0 主表先回答四个 learned posterior 问题：

| Experiment | 唯一问题 | 关键对照 | 直接反证 |
|---|---|---|---|
| FP1 Gate & calibration | 何时 preserve/quarantine/commit | rules、MLP、Event-Transformer | unsafe commit 不降或置信度不可校准 |
| FP2 Sparse typed transaction | 是否只选择必要 targets/operators | local、full-graph、FullGraph-RGT | necessary recall 相同但 collateral edit 不改善 |
| FP3 Bi-temporal correction | 是否正确使用 event/arrival time 修订历史 | 去 event time、去 arrival time、latest overwrite | 时间打乱不掉分或迟到证据持续写错区间 |
| FP4 Typed dependency OOD | 是否推广到更深/更大的依赖图 | flat、untyped、TGN-style | typed-edge 消融在 depth OOD 等价 |

原 F0–F9 继续保留为完整系统的前置、鲁棒性和下游实验，不再全部挤进首张主表。

| Experiment | 人话问题 | 与核心母命题的关系 | 性质 |
|---|---|---|---|
| F0 Representation binding | 当前帧区域能否稳定对应持久世界单元 | 决定新证据允许修改谁 | 前置消融 |
| F1 Structural prediction | 行动后候选是否包含真实下一状态 | 提供可被反证的 expected prior | 前置消融 |
| F2 Hypothesis lifecycle | 猜测能否保持、确认或撤销 | semantic status 与生效门 | 核心组成 |
| F3 Perceptual aliasing | 新区域、回环与定位不确定能否分开 | topology append/merge/abstain | 核心前置 |
| F4 Active verification | 能否低代价获得决定 revision 的证据 | 证据不足时补证 | 辅助价值 |
| F5 Reveal vs change | 揭示、遮挡、缺席和搬迁能否分开 | preserve/revise 与 semantic transition | **核心直接实验** |
| F6 Bounded revision | 必要后果是否更新且花盆保持 | affected/control/propagate/stop | **核心直接实验** |
| F7 Version and recovery | 失效事实能否追溯、撤销和恢复 | valid time/version/provenance | **核心直接实验** |
| F8 Robustness/efficiency | 噪声和长历史下是否仍可用 | 核心机制的稳定性与成本 | 压力测试 |
| F9 Downstream value | 正确信念是否改善找物或路线 | posterior 是否有任务价值 | 下游证明 |

R5 和 Q1 作为不变量/边界 case study 单独报告，不能代替 F1–F7。

## 3. 必须比较的基线

基线按它们排除的解释分组：

### 观测表示与世界绑定

- fixed image patches；
- full-frame latent / global EMA；
- object-only slots；
- geometry-only plane/region proposals；
- oracle region boundary + oracle world association；
- proposed hybrid region cues + bounded world-node write。

### 地图与假设

- observed-only map；
- greedy append；
- top-1 hypothesis commit；
- classical/learned frontier exploration；
- 接口公平的 online topological mapping。

### 世界状态修订

- append-only；
- local matched-slot；
- pose-warped global EMA；
- full-graph recomputation；
- deterministic/oracle affected-subgraph。

学习型主对照必须再包含：

- FlatFact-MLP：相同事实特征，无事件序列和图边；
- Event-Transformer：相同 evidence history，无图邻接；
- TGN-style memory：通用动态图事件记忆/更新；
- FullGraph-RGT：相同 typed graph encoder，预测整图快照；
- BEGR-FlatDecoder：相同参数预算，去掉 gate→operator 的分层因子化；
- BEGR-Net：分层稀疏事务 + deterministic executor。

所有 learned baseline 使用同一 candidate set、split、容量档位、early-stopping metric 和 trial budget；参数量、训练时间与 peak memory 实测报告。

### 动作选择

- random admissible action；
- nearest frontier；
- task-only、无 information value；
- information-only、无 task/risk cost；
- oracle one-step action。

任何外部系统若输入传感器、地图粒度、动作空间或任务定义不同，必须说明适配，不用不公平排行榜支撑主张。

## 4. 核心指标

论文主表首先报告四组 revision 指标，其他指标进入前置消融或下游表：

| 核心问题 | 主指标 |
|---|---|
| 语义状态是否改对 | evidence-path / typed-transition accuracy，false world edit |
| 拓扑与必要后果是否改全 | necessary-update recall，affected-scope precision/recall，stop-edge accuracy |
| 有效时间和历史是否正确 | valid-time accuracy，version continuity，provenance validity，recovery |
| 无关旧事实是否保持 | control preservation，collateral revision rate，transaction integrity |

### 区域绑定与 latent 写入

- region-to-world association precision/recall；
- duplicate-node rate 与 false merge；
- split/merge recovery；
- latent drift / contamination；
- unrelated world-node preservation；
- write-gate coverage、abstention quality 与 nodes-per-meter；

这些指标必须按“同一表面跨视角”“遮挡 split/merge”“相似但不同表面”“新 portal/surface”“pose 漂移”分组报告，不能只给平均数。

### 预测与假设

- candidate recall/precision；
- hypothesis calibration；
- false predicted extent；
- promotion/rejection accuracy；
- candidate-to-confirmed contamination；
- recovery after wrong hypothesis。

### 拓扑与定位歧义

- graph/topology correctness 或预注册的 graph edit metric；
- false append；
- false merge；
- loop-closure decision；
- localization abstention quality。

### 修订与保持

- target invariant accuracy；
- required propagation recall；
- affected scope precision/recall/F1；
- control-subgraph preservation；
- collateral revision rate；
- stop-edge accuracy；
- version/provenance validity。

### 学习与概率质量

- gate/operator macro-F1，避免多数 preserve 类掩盖 quarantine/commit；
- transaction exact match：gate、targets、operators、time/version validity 全部正确才算命中；
- NLL、multiclass Brier score 与 ECE；
- risk–coverage / selective risk：允许 abstain 后，覆盖率下降多少、unsafe commit 降多少；
- counterfactual pair consistency：只改一个证据字段时，两例是否都给出相应不同决策；
- ID 与 OOD 的绝对差值，不用单一总平均掩盖 dependency-depth 或 delay 失效。

### 行动价值

- steps-to-correct-belief；
- task success / path cost；
- information gain；
- redundant observation count；
- collision/risk violation；
- total utility/cost，计算式必须在 test 前冻结。

### 系统成本

- latency；
- peak memory；
- edited-node/edge ratio；
- hypothesis count growth；
- version storage growth。

不能用 query top-K 或导航成功率替代内部 belief 正确性。

## 5. 正式 test 前冻结

```text
claim
  → experiment
  → dataset/split
  → baseline and interface adapter
  → metric
  → statistical test / confidence interval
  → expected falsifier
```

同时冻结：

- HC-013 对应的功能级硬门、acceptable set、No-Go 与指标聚合规则及其 accepted D 决策；
- HC-014 对应的区域来源、world-node association、split/merge、低置信处理、latent 写入门与指标定义及其 accepted D 决策；
- experiment contract version；
- dataset manifest 与 split hash；
- thresholds、prompt、loss、utility weights 和 checkpoint；
- random seeds；
- model/code identifiers；
- equivalence-class scoring；
- exclusions、missing-data 和 failed-run policy。
- train/validation/ID-test/OOD-test 的 environment、template family 与 counterfactual-group 划分；
- B0–B7/L0–L5 的 candidate input、容量档位、trial budget 和 early-stopping metric；
- calibration 只在 validation 拟合，test 不重新估温度；
- paired bootstrap 或其他置信区间方法及 seed；

## 6. Related Work 结构与准入

正式论文按问题关系组织，而不是一篇论文一节：

1. **World models and latent dynamics**：状态—动作条件预测与 imagined rollout；
2. **Temporal/dynamic graph learning**：event-based memory、动态图更新与时序消息传递；
3. **Structured/object-centric world models**：对象、关系、拓扑和组合动力学；
4. **Structural observation and 2D-to-3D fusion**：layout/plane/slot/feature lifting，以及观测单元怎样绑定持久 3D/world nodes；
5. **Active SLAM and topological exploration**：在线扩图、回环、frontier 和行动选择；
6. **Belief state under partial observability**：多假设、不确定性和 object permanence；
7. **Persistent scene memory and graph revision**：长期状态、动态变化、双时间、版本和局部更新；
8. **Relational retrieval**：FARM 等查询能力，只作为接口或 novelty watch。

准入规则：

- `verified_peer_reviewed + foundation/adjacent` 才能作为事实主干；
- preprint/submission 只作 novelty watch，正文出现时明确状态；
- FARM 投稿前重新核验 venue；
- 世界模型方向新增论文必须先进入 `literature/library.csv` 与 `peer_review_audit.md`；
- 不声称 first world model、first online map、first active exploration、first structured memory、first dynamic memory、first graph revision 或 first relational retrieval；
- 不声称首次使用 perspective、plane、region、slot 或 2D-to-3D feature fusion；需要验证的是它们是否为本项目的 bounded belief write 提供额外作用；
- 当前最窄的创新假设是：**在同一感知、预测和 association 输入下，对世界事实的 semantic status、topological relation 与 valid time 做 evidence-gated、affected/control/stop-aware 的版本化 posterior revision**。是否升级为论文 contribution 必须由系统文献审计和冻结实验共同决定。

## 7. 论文结构

```text
1 Introduction
  partial observability + changing world
  → predicted structure is not fact
  → active evidence + bounded posterior revision
  → narrow claims and evidence

2 Related Work
  world models
  → structured belief
  → active mapping
  → persistent revision

3 Problem Formulation
  event time / arrival time / valid time / transaction time
  → entity / fact / evidence / typed dependency graph
  → sparse revision transaction / protected controls

4 Method
  event encoder + typed relational graph encoder
  → hierarchical preserve/quarantine/commit decoder
  → target/operator/evidence attribution
  → deterministic closure + bitemporal versioned executor

5 Experimental Protocol
  W/R/Q sequence families
  → counterfactuals
  → baselines, metrics, split/test rules

6 Results
  claim-by-claim
  → bounded posterior revision
  → upstream ablations
  → downstream value
  → failures

7 Limitations and Ethics
  sensor/pose assumptions
  → topology/ontology limits
  → open-world uncertainty
  → deployment risk
```

章节按问题和证据组织，不按代码目录堆叠。

## 8. 投稿前证据门

- 每条 contribution 有 baseline、metric、ablation 和 falsifier；
- 同时报告内部 belief 正确性和下游任务收益；
- 主表数字来自冻结的正式协议；
- confidence interval/统计方法明确；
- false append/merge、错误确认、风险动作、negative result 和缺失均记录；
- 自动估计或模型评审没有称为 ground truth；
- test 没有用于模型、阈值、prompt、动作权重或 checkpoint 选择；
- 主图和表格可从 run artifacts 重建。

## 9. 可复现产物

发布或提供：

- schema、config 和 version；
- W0/W/R/Q micro-sequences 与 evaluator；
- region proposals、association records、allowed-write masks 与对应失败样例；
- deterministic predictor/assimilator/planner baselines；
- data generation/validation scripts；
- environment/lockfile；
- seed、data/split hash、code/model ID；
- raw per-sequence metrics、belief transitions 和失败引用；
- 至少一个干净环境重放命令。

大型数据、checkpoint、PDF 和运行输出不提交 Git，通过外部存储和 manifest 管理。

## 10. 结论强度规则

| 证据达到 | 最多能写 |
|---|---|
| 只有合同和序列设计 | we formulate / propose to evaluate |
| oracle pilot | belief loop is executable under oracle inputs |
| deterministic validation | rule-based mechanism survives controlled counterfactuals |
| learned validation | learned components improve on validation scope |
| frozen formal test | method supports对应的正式 claim |
| external/real replication | stronger generalization statement |

不要把“已定义”写成“已实现”，不要把“已实现”写成“已验证”，也不要把下游成功自动归因于内部 world belief。

若 F0 不能优于 fixed patch、full-frame latent 或 object-only，论文删除“结构区域绑定”贡献表述，只把最简单可用的表示留作工程接口；若只在 oracle boundary 下有效，则结论必须限定为 association 机制上限，不能归因于真实视觉能力。
