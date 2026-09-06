# 01 CPMT 研究合同

定位：已确认的研究问题与拟验证假设，不维护实现进度；当前实现、实验结果与未完成项统一见 [实验记录](../EXECUTE.md)。

## 研究问题

在部分可观测、视角持续改变且世界可能真实变化的环境中，机器人如何从序列本身学习：当前结构证据应当绑定已有节点、扩张世界，还是修订既有事实，同时避免视角、遮挡和位姿误差污染长期记忆？

## 唯一主假设

与直接预测 transaction label 或增加 future auxiliary loss 相比，先在同一旧图的版本副本上执行竞争性 transaction programs，再用当前与未来投影一致性评价执行后世界，能够产生更可靠的 hindsight supervision；由此蒸馏的 online updater 能减少长期 world-graph contamination。

## 方法角色

- CPMT：完整具身空间记忆系统；
- CTL：从 future-conditioned transaction posterior 蒸馏 online transaction policy 的核心学习机制；
- Projective Node Orbit：使同一世界节点解释多视角 observation latents 的表征基础；
- Versioned Deterministic Executor：使候选解释成为真实 graph interventions 的执行基础。

主创新只归于 CTL 的 executable counterfactual supervision。表征与 executor 是否构成额外贡献，必须由独立消融决定，不能预先宣称。

### 教师可以不同意参考标签

白话：教师不是答案本身，是一个**打分器**。它把每个候选真的执行一遍，再看"执行完的世界，和后来实际观测到的世界像不像"，同时对"改动越大越不划算"扣分。所以当两个候选对未来预测得**几乎一样好**时，便宜的那个会赢——哪怕它不是我们标注的参考答案。

这是设计意图，不是缺陷。能量函数写的就是"未来一致性 + 最小改动代价"，把后半句去掉才是错的。

paired sibling 的反事实 rollout 必须沿该 sibling 实际登记的 primary/contrast policy 前进。hindsight 的视野跨过 ambiguity pivot 时，参考候选继续执行该分支的真实后续事务，故其 `future_raw` 必须为 0；若代码把 contrast sibling 偷换回 primary policy，产生的非零误差是分支实现错误，不是合理的 teacher disagreement。即使参考轨迹正确，其他候选仍可能在有限观察下得到相同 future 分数，此时 edit/growth 等最小改动先验可以让教师与事务标签不同意。

因此：

- 教师与参考标签的一致率**记录为 `teacher_reference_agreement`**，不作为断言拦截；生成器不会因为教师不同意而失败。
- 该比率若显著下降，属于需要解释的实验事实（可能是候选等效、能量权重或数据问题）；但必须先验证参考候选的分支 trace 为零误差，不能把 policy 错配包装成教师性质。
- 报告 A 的表现时必须一并报告该比率、reference future error 与 disagreement 分解，不能只报学生准确率。

## 拟议 claim

> CPMT learns online persistent-memory revision from a hindsight posterior over executable world transactions, evaluated by current and future projective consistency under a minimal-world-change prior.

这里的 counterfactual 是对内部 memory state 的干预，不是物理世界因果效应。

## 事务范围

主要意图：

- PRESERVE：NOOP；
- ASSOCIATE：BIND / REACTIVATE；
- EXPAND：BIRTH；
- REVISE：RELINK / RETRACT / SPLIT / MERGE。

REPLACE 是 RETRACT+BIRTH 的复合程序。QUARANTINE 是低置信度 wrapper，不属于 world mutation。

## 首篇边界

固定 DINO-family backbone、depth、pose、region proposals 和 deterministic candidate generator。禁止把 active disambiguation、第二任务领域、learned proposer、端到端视觉训练或导航同时并入。

## 成功条件

1. M1 的 CPMT-CTL Core 在预注册 paired cases 上优于 direct+future-loss 与 no-execution future scorer；
2. 改善落在 post-execution graph correctness 和 long-horizon contamination；
3. growth、collateral edit、protected violation 和 illegal program 不恶化；
4. candidate miss、hindsight teacher error、online amortization error 分开报告；
5. SPLIT/MERGE/RETRACT 有正例并由同一 executor 处理；
6. teacher 优势能部分保留到 online self-rollout。

## 失败解释

- Full≈direct+future：核心机制失败，不能称 CPMT 学习贡献；
- Full≈no-execution：真实执行候选不是必要条件；
- 只有 Node Orbit 有效：降级为 representation work；
- 只有 oracle/executor 有效：降级为 deterministic memory system；
- candidate coverage 低：先修候选，不评价 scorer；
- 只有单步准确率改善：不能声称 persistent memory 改善。

## 证据顺序

M0 executor fixtures → M1 hard-condition → M2 embodied visual self-rollout → M3 one external/real validation。

任何阶段均区分 planned、implemented、validated、failed。数值 gate 在正式 test 前冻结。
