# 基线与结构化审计

## 1. 不凭论文自称判断“结构化世界模型”

逐个方法填写审计表，并引用代码路径、数据结构或论文段落。主表中，“结构化 updater”至少满足 SA1–SA3；其余能力逐项报告，不能用一个 yes/no 掩盖差异。

| ID | 审计问题 | 判定证据 |
|---|---|---|
| SA1 | 世界事实是否是可寻址对象 | 节点/三元组/slot 有稳定 ID，可单独读写 |
| SA2 | 关系或依赖是否显式存在 | typed edge、relation table 或明确 adjacency |
| SA3 | 状态是否跨时间持久并增量更新 | 有 `state_{t-1} → state_t`，不是每帧重建后丢弃 |
| SA4 | 是否区分 event time 与 arrival time | 两个字段和不同排序语义 |
| SA5 | 是否保存证据/provenance | 更新能反查输入事件 |
| SA6 | 是否表达 affected/protected boundary | 可说明哪些事实允许或禁止修改 |
| SA7 | 是否有有效时间语义 | 事实何时成立，不只是最后更新时间 |
| SA8 | 是否维护依赖一致性 | 前提变化会沿 typed dependency 有界传播 |

例如，一个 Transformer 把全图序列化但没有稳定事实 ID 或显式边，只能算“使用结构化输入文本”，不能自动归为结构化世界模型。一个 GNN 每帧预测 scene graph 但不持久增量状态，满足 SA1/SA2，不满足 SA3。

## 2. 两层公平比较

### Updater-isolation 主表

所有方法得到相同 prior graph、evidence events、candidate facts、visibility、identity 和 dependency input；统一输出 canonical transaction；所有可适配方法经过同一 executor。这里回答“更新推断谁更好”。

### Native-system 外部表

成熟方法使用其原生感知与记忆管线，只作生态位与外部比较。输入、训练数据或输出语义不同就明确标 `not directly comparable`，不拿它替代主因果比较。

## 3. 必跑基线

| 组 | ID | 方法 | 目的 |
|---|---|---|---|
| 规则 | R0 | Last-arrival-wins | 暴露迟到消息错误 |
| 规则 | R1 | Last-observation-time-wins | 检查只有 event time 是否足够 |
| 规则 | R2 | Bayesian/confidence filter | 概率聚合下限 |
| 规则 | R3 | hand-written evidence gate | 强工程规则基线 |
| 平坦学习 | L0 | FlatFact-MLP | 没有历史/图结构 |
| 时序学习 | L1 | GRU event sequence | 轻量历史基线 |
| 时序学习 | L2 | Event-Transformer | 全历史、无显式依赖传播 |
| 图学习 | L3 | TGN-style | temporal graph 强基线 |
| 图学习 | L4 | FullGraph-HGT | 全图异构更新，检验稀疏性价值 |
| 本方法 | M0 | ESGBU | 稀疏 mask + edit/time/evidence |
| 上界 | O0 | Oracle updater | evaluator 上界，不参与现实排名 |

Scene Graph Memory、Continuous Scene Representations、SceneGraphFusion、DiffVSGG 和 Embodied VideoAgent 用于问题重合审计；只有能在统一输入输出下可靠适配时才进入数值主表。

## 4. 容量与预算匹配

- L2/L3/L4/M0 报 tiny/base 两档或参数差不超过 10%；
- 同时做相同训练 step、相同 wall-clock 上限两种预算；
- 相同 train/validation/test、seed 列表、early stopping 和 checkpoint 规则；
- candidate retrieval recall 单独报告且各方法共享；
- 主表同时给投影前与投影后，避免把 executor 的收益全算给本方法。

## 5. 结构化消融

若要回答“收益来自结构化还是 updater”，至少比较：

1. 同一 Event-Transformer：flat facts vs explicit typed graph；
2. 同一 HGT：full-graph write vs learned sparse mask；
3. 同一 ESGBU：typed edges shuffled/removed；
4. 同一输出：无 executor vs shared executor。
5. 同一 ESGBU：schema-conditioned vs predicate-ID-only vs schema fields removed，并在 registered-but-unseen predicate split 单列。

这四组比“某篇论文自称 world model”更能支撑因果结论。

## 方法行的 Criteria 纵列

| Method | 它控制/缺少什么 | 最能暴露差异的 Criteria | 数字判例 | 结果怎样解释 |
|---|---|---|---|---|
| R0 Last-arrival | 无event time | C2/C5/C8 | 602秒旧证据968秒到达并覆盖720秒事实，C2=0 | 证明arrival-only脆弱 |
| R1 Last-event | 有event time，无冲突/来源学习 | C1/C2/C12 | 两高可信来源冲突仍选最新，QUARANTINE F1下降 | 双时间仍不够 |
| R2 Bayes filter | 概率聚合，无显式closure | C3–C7/C12 | commit校准好但CER=25% | 概率不等于结构边界 |
| R3 evidence gate | 手写visibility/source/time规则 | C1–C13 | 若各OOD轴近oracle，学习必要性失败 | 最重要规则下限 |
| L0 FlatFact-MLP | 无历史、无图 | C1/C2/C3 | no-delay可好，stale/conflict应差 | 历史必要性下限 |
| L1 GRU | 有序历史，无显式图 | C1/C2/C12 | 优于L0说明历史有用 | 与Transformer轻量对照 |
| L2 Event-Transformer | 全历史，无typed closure | C1/C2/C8/C12 | 与M0等价则图结构主张失败 | 强时序基线 |
| L3 TGN-style | temporal graph memory | C1–C8/C12 | 与M0等价则新图机制不足 | 成熟动态图基线 |
| L4 FullGraph-HGT | 同异构图但全图可写 | C3–C7/C15 | 与M0准确相同但p95更慢，只支持效率claim | 稀疏性的直接对照 |
| M0 ESGBU | schema-conditioned sparse mask+time+evidence | C1–C15 | ID内强但held-out predicate等于ID-only时，删除schema泛化claim | 候选方法 |
| O0 Oracle | 使用真事务 | evaluator全部criteria | 12/12 oracle必须100% | 判尺上界，不参加现实排名 |

每一行在结果表旁重复“缺少什么”和“最能暴露差异的 criteria”，避免读者再跳回本文件猜比较目的。
