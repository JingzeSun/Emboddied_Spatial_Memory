# Evidence-Aware Sparse Graph Belief Updater 实验包

这是当前唯一核心实验包。旧版已逐文件归档到 `docs/archive/pre_d024_posterior_updater_refactor_2026-09-04/`。

研究对象是固定上游证据接口后，学习：

\[
q_\phi(\Delta G_t,M_t,\tau_t,Z_t\mid G_{t-1},E_{\le t}).
\]

其中 `ΔG_t` 是稀疏编辑程序，`M_t` 是受影响掩码，`τ_t` 是有效时间，`Z_t` 是直接证据集合。

## 文件导航

| 文件 | 只回答什么 |
|---|---|
| `PROBLEM_FORMULATION.md` | 样本、变量、操作和边界 |
| `LEARNED_MODEL.md` | 模型模块、硬投影和规模 |
| `LOSS.md` | loss 与预测变量如何一一对应 |
| `DATASETS.md` | symbolic、AI2-THOR、3RScan 的职责 |
| `SCENARIOS.md` | 如何按控制变量生成场景 |
| `BASELINES.md` | 如何审计并公平比较结构化基线 |
| `CRITERIA.md` | 每个指标、门槛和数字例子 |
| `PROTOCOL.md` | 运行顺序、数据隔离和统计 |
| `NOVELTY_AND_FALSIFIERS.md` | 与动态图工作的差异和反证条件 |
| `APPLICATION_AND_TASKS.md` | 狭窄应用和任务依赖 |
| `PUBLICATION_GATES.md` | 从 pilot 到强国际论文的证据门 |
| `templates/`、`fixtures/` | 机器可执行合同和手写案例规范 |

## 当前状态

- 设计：已重构，关键 CRITERIA 与 HC-018 执行顺序待人工冻结；
- 实现、下载、训练、验证：均未开始；
- 论文贡献：候选假设，不是已验证结论。

第一反证：若在同输入、同候选事实、同预算和同 executor 下，稀疏方法不能同时改善必要编辑、无关保护、校准/时间和下游错误，或优势只来自更大 backbone，则收缩主张。

