# 与动态场景图工作的边界及反证实验

状态：**新颖性假设，不是已验证结论。**

## 1. DSG 已经覆盖了什么

2026-09-01 的 DSG 预印本已经明确覆盖：在变化室内环境中维护动态 3D scene graph、检测
Stable/Appeared/Missing 对象、更新空间关系，并在 Dyn-THOR 上评测节点和边。因而以下表述不能再
作为本项目创新：

- “我们首次在动态环境中维护场景图”；
- “我们能检测物体移动并更新关系”；
- “我们不必每次从零构图”；
- 单纯提高最终 node/edge F1。

通用动态/时序图模型也已覆盖 event-based message、node memory 与 temporal update；持久 scene-graph memory、增量 3D scene graph 和动态场景图也不是空白。因此“用了 Transformer/GNN/TGN 更新场景图”本身不是创新。BEGR-Net 必须通过同输入 TGN-style 与 FullGraph-RGT 基线，证明差异来自双时间证据门、稀疏 typed transaction 与可回放 executor，而不是 backbone。

## 2. 本项目可检验的更窄命题

候选命题不是“更好的动态图”，而是：**在输入证据不完整、乱序或冲突时，学习型世界模型如何以证据门控的、可追溯的最小事务修正旧信念。** 它必须同时产生：

1. `evidence_path`：哪条证据支持或阻止写入；
2. typed `add/retract/replace/quarantine/no-op`；
3. `affected_set` 与 `control_set`；
4. 通过显式依赖传播到未直接观测的事实；
5. `valid_time` 区间与 `recorded_at`；
6. 可回放的 version/provenance；
7. 证据不足时正确 stop，而不是补全想象中的状态。

当前最窄的 learned hypothesis 是：分层 `preserve/quarantine/commit → targets/operators` 建模，在同一 candidate graph 和 evidence events 下，能比 flat sequence、通用动态图记忆和 full-graph decoder 更好地联合控制 necessary-update recall、unsafe commit 与 collateral edit；typed closure 与版本合同则提供模型外的正确性边界。

## 3. 真正能区分方法的场景

| 场景 | 共同动态图通常能做的 | 本项目额外要证明的 |
|---|---|---|
| 可靠缺失、去向未知 | 标记 missing | 撤销旧位置但不编造新位置，保留 unknown |
| 遮挡 | 可能判 missing | 证据门阻止 destructive write |
| 推车带着隐藏箱移动 | 更新观测到的推车 | 按 typed dependency 更新未直接观测箱子的关系 |
| 两路证据冲突 | 选最新或最高分 | quarantine，保留分支与来源，等待再观测 |
| 变化时刻未知 | 用扫描/观测时间 | 记录 `(last_supported, first_contradicted]` 与事务时间 |
| 最终快照相同 | node/edge F1 相同 | 区分合法最小事务与“先误删后补回”的版本污染 |
| 无关区域稳定 | 最终图可能仍正确 | 证明 control facts 从未被触碰 |
| 迟到证据/纠错 | 重建新快照 | reopen/retract 指定版本且保持历史可回放 |

## 4. 必须主动尝试推翻自己的实验

| Falsifier | 若观察到什么，原命题应收缩或放弃 |
|---|---|
| F1 Strong-local parity | `incident_edge_recompute` 在 UP/CP/ST/TV 全部与本方法统计等价 |
| F2 Full-graph parity | full graph 在相同硬门下既不多改、成本也无显著劣势 |
| F3 Structure ablation parity | 扁平事实表与 typed dependency graph 表现相同 |
| F4 Provenance no utility | 去掉 provenance/version 不影响纠错、审计或下游任务 |
| F5 Oracle-only gain | 优势只在 oracle identity/visibility 下存在，合理噪声下消失 |
| F6 Annotation fragility | 不同标注者对 `A*`、`C*`、依赖闭包一致性太低 |
| F7 Dataset confinement | 只在手写 fixture 有效，在 AI2-THOR 与 3RScan 均不成立 |
| F8 Temporal ablation parity | 移除 event time 或 arrival time，在 late/stale 场景不掉分 |
| F9 Generic dynamic-model parity | TGN-style 在 UP/CP/ST/TV、校准与 OOD 上统计等价 |
| F10 Decoder parity | flat decoder 与 hierarchical decoder 在同容量预算下等价 |
| F11 Dependency OOD parity | typed-edge 消融在 dependency-depth OOD 不掉分 |
| F12 Synthetic shortcut | label-prior、对象名或模板 ID 即可达到接近主模型的表现 |

不要把 F1/F2 的负结果藏在平均 F1 后面。若强局部基线已足够，贡献应诚实降为时间/证据审计协议；
若连该贡献也无下游价值，则不再声称新型 posterior revision 方法。

## 5. 最小风险前置顺序

1. 12 个 smoke fixtures：先让 oracle revision 100% 通过硬门；
2. 实现 B0–B5 的确定性版本，不先写复杂模型；
3. 在 R3/R4/R2 上找最容易推翻命题的对照；
4. 若有差异，再扩到原 19 + 8 个双时间模板和 symbolic transaction generator；
5. 先跑 flat/Event-Transformer/TGN-style/FullGraph-RGT，再训练 BEGR-Net；
6. 最后才接真实 perception 或完整 DSG/3RScan pipeline。

这能在数天内发现“指标无法区分”或“强基线已经够用”，而不是训练数月后才知道假设不成立。
