# Projective Structural Latent Memory 实验包

这是 D-032 后唯一活动实验包。研究对象不是单次 scene-graph edit，而是连续在线闭环：

\[
R_t=\operatorname{Tokenize}(o_t),\quad
\hat R_t=\operatorname{PredictProject}(S_{t-1},a_{t-1},T_t),
\]

\[
q_\theta(A_t,U_t\mid R_t,\hat R_t,S_{t-1},a_{t-1},\Sigma),\quad
S_t=\operatorname{Execute}(S_{t-1},A_t,U_t).
\]

目标是让视觉 latent 在世界坐标中获得长期身份，同时正确处理首次揭示、重访、遮挡、动态实体、传感错误与真实变化。

## 文件导航

| 文件 | 只回答什么 |
|---|---|
| `PROBLEM_FORMULATION.md` | 输入、状态、association 与 transaction 语义 |
| `LEARNED_MODEL.md` | tokenizer、predict-project、binding、growth/revision 与 executor |
| `LOSS.md` | 层级概率因子怎样训练，不堆重复 loss |
| `DATASETS.md` | hand/symbolic、simulator、重扫与真实轨职责 |
| `SCENARIOS.md` | S00–S11 反例与控制变量 |
| `BASELINES.md` | patch、warp、slot、window、graph、full recompute 公平比较 |
| `CRITERIA.md` | B/G/M/R/P/T/E 指标唯一字典 |
| `PROTOCOL.md` | 从判尺到外部验证的执行顺序 |
| `NOVELTY_AND_FALSIFIERS.md` | 近邻工作、剩余主张和 kill 条件 |
| `APPLICATION_AND_TASKS.md` | 狭窄应用与只读下游 |
| `PUBLICATION_GATES.md` | 具身论文到强期刊/通用 ML 的证据门 |
| `templates/`、`fixtures/` | 机器可执行 case/run 合同 |

## 三个必须分开的因果问题

1. **representation**：structural regions 是否比 fixed patches/objects 更适合绑定；
2. **memory update**：predict-project/bind/grow/revise 是否比 warp/fuse/recompute 更可靠；
3. **task value**：更正确的 memory 是否改善 query/navigation/planning。

不能用更强视觉前端回答第 2 问，也不能用任务分数代替第 1/2 问。

## 当前状态

- 文档合同：D-032 后重构；HC-020～034 均待冻结；
- schema、fixture、数据、代码、训练、结果：未实现/未验证；
- 第一反证：若 pose-warp + IoU/appearance + lifecycle rules 已与 PSLM 等价，则学习型 memory transducer 不成立；
- 第二反证：若 recent-N full recomputation 与 persistent memory 等价且成本可接受，则长期增量状态主张不成立。
