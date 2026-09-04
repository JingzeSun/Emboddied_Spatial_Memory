# 04 — 训练计划：BEGR-Net 双时间后验修订

> 状态：`candidate posterior-first plan / blocked by HC and pilot gates / no model trained`

只有 [人工确认中心](DECISIONS.md) 的相关 HC 条目全部获得用户回答并形成对应 D 决策、schema 连通且 `03_pilot_protocol.md` 的 Go 条件满足后，本文件才生效。

## 1. 训练单位

当前 P0 样本是一条 revision transaction：

~~~text
(candidate fact subgraph,
 evidence events with observed_at/received_at/source/group,
 typed dependencies,
 base version)
  → preserve / quarantine / commit
  → targets + typed operators | commit
  → deterministic closure/time/version/provenance
~~~

prediction、region binding、active action 与真实 perception 暂用 fixed/oracle 输入；下面保留的完整闭环训练单位属于后续集成，不与 P0 同时优化。

训练样本不是单独一帧，而是一个有动作和前后 belief 的时间步：

```text
(B_t, hypothesis_t, action_t, pose/history, optional goal)
  → predicted prior B^-_{t+1}
  → expected observation + structural hypotheses

(B^-_{t+1}, O_{t+1})
  → temporary structural regions
  → region-to-world association + allowed latent writes
  → evidence path
  → hypothesis promotion/rejection/retention
  → affected/control/stop + typed operations
  → posterior B_{t+1}

(B_{t+1}, hypotheses, goal)
  → next observation/action
```

必须监督：

- 哪些只是预测，绝不能写入 confirmed graph；
- 哪些证据允许确认或撤销候选；
- 真实变化时该改什么、不能改什么；
- 下一动作要验证什么或推进什么任务。

只监督最终导航成功或 query answer，无法证明内部世界信念是正确的。

训练也不能变成多个 head 的任务拼盘。统一学习目标是：

~~~text
PosteriorRevisionController(B^-_{t+1}, associated evidence)
  → semantic transition
  → topology edit + necessary propagation + stop
  → valid-from / valid-to + provenance
  → affected set + protected control set
~~~

prediction、region binding 和 active action 分别产生 prior、evidence ownership 和补充证据；它们是否更强不能替代 posterior revision 本身的监督。

## 2. 分阶段训练

### 2.1 当前 posterior-only 候选顺序

| Stage | 学习对象 | 固定项 | 退出/早停 |
|---|---|---|---|
| T0-P | 不训练：evaluator、versioned executor、B0–B7 | 全部输入 oracle | 12 smoke fixtures 100% 通过，注入错误均被抓到 |
| T1-P | FlatFact-MLP / Event-Transformer | candidate graph、dependency、executor | 256 样本可 overfit；label prior 未饱和 |
| T2-P | TGN-style / FullGraph-RGT | 相同事件、split、容量与调参预算 | 强 learned baselines 建立 |
| T3-P | BEGR-Net gate + target/operator + evidence attribution | closure/time/version 为 hard executor | validation 同时改善 necessary update、control、stop 与概率质量 |
| T4-P | 单因素 OOD 与结构消融 | 冻结 checkpoint/threshold | time/typed edge/source/group 的作用可被反事实支持 |
| T5-P | AI2-THOR / 3RScan / Dyn-THOR secondary tracks | 不用其 test 调参 | 明确外部效度及失败边界 |

是否允许 T0-P 先于完整闭环实施由 HC-018 冻结。

### 2.2 后续完整闭环集成

| Stage | 学习对象 | 仍保留的 oracle | 进入条件 | 退出条件 |
|---|---|---|---|---|
| T0-R | 不训练；先用 oracle/deterministic 结构区域与 world-node binding 跑通 W0 | region boundary、association、split/merge | contract + HC-014 frozen | 比 fixed patch/full-frame latent 更少重复、错绑和污染；否则删除该复杂度 |
| T1 | 动作后的结构候选与预期可见区域 | pose、association、posterior | pilot passed | hypothesis recall/calibration 超过规则与 observed-only |
| T2 | confirm/expand/revise/preserve/quarantine | pose、association、scope/operator | T1 frozen | 单因素路径分类与 promotion/rejection 稳定 |
| T2-R（可选） | region-to-world association、write gate；必要时再学习 tokenizer | pose、oracle world nodes、posterior | T0-R 有效且 T2 stable | association、duplicate/false-merge、latent contamination 同时优于简单表示 |
| T3 | new segment / loop closure / localization ambiguity | pose uncertainty、oracle update | T2 stable | false append/merge 与错误提交率可控 |
| T4 | revision affected scope、operator、propagation/stop | perception、association | T3 stable | 必要后果和无关保持同时改善 |
| T5 | 离散主动取证动作 | 安全约束、动作候选、oracle dynamics | T4 stable | 更低总代价消除任务相关歧义 |
| T6 | noisy perception + 组合场景 | fixture oracle 仅用于评测 | T5 stable | 噪声曲线可解释，未见组合保留主趋势 |

不要一开始端到端训练全部模块，也不要从 corridor micro-sequence 直接跳到视频生成或完整导航。

T0-R 失败时仍可保留视觉 encoder 与对象/几何观测，不训练结构区域模块；这意味着它只是没有证明必要性的工程复杂度，不影响继续检验较高层 belief loop。

阶段角色必须这样解释：T1/T2/T3 提供 revision 所需的 prior、evidence path 与拓扑身份；T4 是核心 affected/control/stop + typed versioned revision；T5 只学习在证据不足时补证；T6 检查核心机制面对真实噪声是否仍成立。

## 3. 模型接口

P0 只实现三个 learned interfaces：

~~~text
EvidenceEventEncoder:
  observed_at / received_at / delay
  source / evidence_group / polarity / coverage

RelationalFactEncoder:
  entity nodes / reified fact nodes
  supports / contradicts / derived_from / moves_with / stop relations

HierarchicalTransactionDecoder:
  preserve / quarantine / commit
  targets + ADD / INVALIDATE / RELINK / SUPERSEDE / REINFORCE
  supporting_evidence_ids
~~~

其输出必须进入 deterministic executor；模型不能直接返回一张不可追踪的新快照。下面的 StructuralPredictor、ObservationBridge、AssociationHead 与 ActionValueHead 均是后续集成接口。

```text
StructuralPredictor:
  expected_visible_elements
  candidate_graphs
  candidate_confidence
  incompatibility / required_evidence

StructuralObservationBridge:
  temporary observation regions + boundary/source cues
  candidate world-node matches
  matched / new-candidate / ambiguous / quarantine
  split / merge evidence
  allowed persistent-latent write targets

AssimilationHead:
  confirm / expand / revise / preserve / quarantine
  evidence_category
  reliability

AssociationHead:
  new_segment / loop_closure / localization_ambiguous
  object identity hypotheses

RevisionHead:
  affected nodes/edges
  control nodes/edges
  stop edges
  typed operator + arguments

ActionValueHead:
  task_value
  information_value
  action_cost
  risk / admissibility
```

GNN、graph Transformer、RSSM 或其他模型只是候选实现。论文贡献取决于结构化 belief contract 和证据，不取决于 backbone 名称。

## 4. 训练目标

~~~text
L = L_revision_nll + lambda_ev L_evidence + lambda_sp R_sparse

L_revision_nll =
  - log p(gate | X)
  - 1[gate=commit] log p(targets, operators | gate, X)
~~~

`L_revision_nll` 是一个事务联合分布的因子分解，不是 gate、state、scope、stop、operator 各训一个互相竞争的 head。`L_evidence` 只在 supporting-evidence 标签可靠时启用；`R_sparse` 只惩罚多余 target，不能代替 necessary-update recall。

候选 validation 搜索范围：`lambda_ev ∈ {0, 0.1, 0.3, 1.0}`，`lambda_sp ∈ {0, 1e-4, 1e-3, 1e-2}`。它们是调参网格，不是 accepted 常数；最终值、trial budget 和选择依据必须记录。

### 4.1 为什么删除原来的多项 loss

| 旧目标 | 当前归宿 | 原因 |
|---|---|---|
| final state + typed operator | joint revision NLL | 两者高度重复，避免同一错误被重复计权 |
| affected/control/stop | typed dependency closure + evaluator | 有明确合同就使用硬结构，避免三个输出互相矛盾 |
| valid time/version | bitemporal rule + executor validation | 多数真实变化只有删失区间，不伪造精确回归标签 |
| preservation/constraint | write mask、precondition、atomic transaction | 禁止项不能依赖软 penalty |
| provenance | executor 强制 + 可选 evidence attribution | 每个 commit 必须有来源，不允许“平均上还行” |
| task/action cost | downstream evaluation only | 保持 posterior 对任务无关，避免导航偏好污染事实 |
| calibration | temperature scaling + ECE/Brier/selective risk | 先测概率质量，不默认再增加一个目标 |

### 4.2 什么时候才用多任务 loss balancing

只有共享 encoder 确实同时训练多个任务时，先记录各 loss 梯度范数和两两 cosine。若连续多个 epoch 出现明显量级失衡或负 cosine，再把 uncertainty weighting、GradNorm 或 PCGrad 作为预注册消融；没有诊断证据时不启用，也不把 loss-balancing 本身当贡献。

以下约束保留给后续完整闭环训练；它们不增加到 P0 主 loss：

- 预测 loss 不能奖励把所有可能结构都列出来；
- cost loss 不能单独优化，否则“不预测、不修改、不行动”会成为退化解；
- hard negatives 必须包含视觉相似但拓扑不同的走廊，以及相邻但不应修改的关系；
- region hard negatives 必须包含“同一墙面因视角/遮挡而 split”和“外观相似但属于不同世界表面”这对相反情况；
- association loss 不能奖励把所有观测都绑到最近节点；低置信时允许 abstain/quarantine；
- learned tokenizer 只有在 deterministic geometry/semantic regions 的消融不足时才引入，避免把 backbone 容量误当成方法贡献；
- 多个合理 hypotheses/posteriors/actions 使用 set 或 equivalence-class 目标；
- confidence 必须可校准，不能只看 top-1 accuracy；
- 所有权重和阈值只用 train/validation 选择。

完整系统的监督/评价按母命题分组，而不是按代码模块罗列：

| 母命题部分 | P0 训练或 hard/evaluation contract |
|---|---|
| semantic status 怎样改变 | evidence path、candidate/confirmed separation、typed operator |
| topology 怎样改变 | association、affected scope、relation propagation、stop boundary |
| 有效时间怎样改变 | valid-from/valid-to、version continuity、promotion/invalidation time |
| 哪些旧事实必须保持 | control preservation、collateral edit penalty、transaction integrity |
| 何时需要下一条证据 | calibration、abstention、action information value |

## 5. 数据课程

P0 先按后验机制增加难度：

~~~text
同步单来源的 preserve/commit
  → reliable absence 与 quarantine
  → 同组重复帧 vs 独立 evidence groups
  → late-but-valid vs stale late arrival
  → 多来源冲突与第三来源补证
  → one-hop typed dependency
  → unseen multi-hop dependency depth
  → 更大 control set 与 graph size
  → retroactive correction + concurrent base versions
  → AI2-THOR 上游噪声
  → 3RScan/Dyn-THOR 外部有效性
~~~

下面的原课程保留给完整闭环集成：

```text
同一表面跨视角由远变近
  → 遮挡造成临时 split/恢复 merge
  → 新 portal/surface 与相似旧表面的歧义
  → 单步直走廊候选
  → 候选确认与否定
  → 墙 + 左/右开口
  → 门洞 / 房间 / 走廊多假设
  → 重复外观：new vs loop vs pose ambiguity
  → 主动侧看或转向
  → ego-motion reveal vs relocation/absence/occlusion
  → one-hop dependency revision
  → multi-hop propagation + stop
  → 重复搬迁/version chain
  → 结构扩展与真实变化同帧出现
  → 未见场景组合
```

每次只增加一种困难。走廊是用于隔离核心变量的最小环境，不代表最终只在走廊上验证。

## 6. 数据切分

- posterior 主 split 同时按 `template_family + environment_seed + counterfactual_group` 分组；
- source ID、arrival delay、dependency depth 与 graph size 各预留至少一个 OOD range；
- 主 split 单位：`environment_layout_family`；
- 同一几何布局的纹理、光照、渲染和时间变体不跨 split；
- 同一 counterfactual group 不跨 split；
- 重复走廊的同源拓扑模板不跨 split；
- 同一动态事件脚本和 asset/trajectory template 记录独立 split；
- train：学习参数；
- validation：阈值、loss、动作权重、提示、模型和 checkpoint 选择；
- test：所有合同冻结后只用于正式报告。

接触 test 后修改协议，必须建立新 protocol version 并保留旧结果。

## 7. 每阶段都要报告什么

- 与 FlatFact-MLP、Event-Transformer、TGN-style、FullGraph-RGT 和 flat decoder 比较；
- transaction exact match、NLL、Brier、ECE、risk–coverage、pair consistency 与 ID/OOD gap；
- 与 deterministic controller 和 oracle 上限比较；
- 与 observed-only、greedy append、top-1 commit、frontier-only 比较；
- candidate recall 与 calibration；
- region-to-world association precision/recall、duplicate-node、false merge、split/merge recovery；
- latent contamination、unrelated-region preservation、允许写入覆盖率和 abstention；
- false expansion、false append、false merge、错误确认和拒绝；
- reveal/change 分类；
- required propagation 与 control preservation；
- steps-to-correct-belief、task success、information value 和 action cost；
- graph size、history length、pose noise 和 visual aliasing sweep；
- 失败按 perception、prediction、association、assimilation、revision、executor、planning 分桶。

## 8. 训练成功门

学习方法必须在 validation 上同时满足：

P0 posterior-only 首先检查：

1. 256-case tiny-set 能过拟合，否则停止并排查实现/标签；
2. 相对最强 learned baseline 同时看 necessary update、control/collateral、unsafe commit 与 calibration，不以单一 final graph F1 宣称成功；
3. event-time、arrival-time、typed-edge、evidence-group、hierarchical-decoder 消融与相应 counterfactual/OOD 结果一致；
4. 不靠把绝大多数案例 quarantine 获得高 commit precision；
5. executor hard failures 为 0 的要求是否成立由 HC-013 冻结，发生数始终逐例报告。

下面九项是完整闭环集成门：

1. 结构候选比 observed-only 提供额外有效信息，而不是枚举一切；
2. region binding 比 fixed patch/full-frame latent/object-only 至少减少一种关键错绑或污染，且不以严重漏写换取；
3. candidate/confirmed 污染率低于 greedy/top-1；
4. 重复走廊中 false append 和 false merge 至少一项显著改善，另一项不能严重恶化；
5. reveal、occlusion 和真实变化能够走不同状态路径；
6. revision 不能靠少编辑换来明显漏改；
7. 主动取证降低任务相关歧义的总代价，而不是只增加观察次数；
8. 未见 layout/event 组合保留主趋势；
9. config、seed、data hash、code/model ID 能重放结果。

其中第 3–6 项共同决定核心 revision claim；第 1–2 项是输入表示和先验前置，第 7 项是辅助价值，第 8–9 项是泛化与复现。不能用前置模块的高分掩盖核心修订失败。

失败时可以：

- 保留 deterministic 方法；
- 把主动取证降为下游应用；
- 收缩 loop closure 或拓扑预测主张；
- 只保留 bounded belief revision。

不能默认把失败解释为“模型不够大”。

## 9. 训练范围边界

- 第一版预测结构状态或图，不要求生成 RGB/video；
- 第一版 planner 只处理离散动作和短视界；
- predictor 不能直接提交 confirmed fact；
- ObservationRegion 和透视远近标签不能跨帧充当持久 identity；
- 未完成 region-to-world association 的特征不能写入持久 world-node latent；
- 第一阶段不学习 Chart/Place split/merge；
- planner 不能改写 PersistentWorldMemory；
- test 不用于动作权重、风险阈值或 checkpoint 选择；
- 自动标签必须记录生成规则和人工审查比例。

通过后进入 [`05_formal_evaluation_and_paper.md`](05_formal_evaluation_and_paper.md)。
