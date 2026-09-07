# 2026-09-07 指标层审计（外部复核记录）

> 性质：只读复核记录，不是 decision。任何采纳项须另立 D-XXX。
> 依据：干净提交 `8b304e3`，本地 12-group v8 arrays（digest `e924f96d4cf28179`），
> 以及 `results/m1-v2-pretest-smoke-20260906T102332Z.json`（3 paired groups，旧协议，仅作指标行为证据）。

## A 组：机制–指标覆盖缺口

| # | 问题 | 证据 | 状态 |
|---|---|---|---|
| A1 | C10 选错答案对 active-world 完全不可见 | ref=BIND 选 NOOP 仍 active_correct=1.000 (12/12)；ref=NOOP 选 BIND 同样 1.000 (12/12)，fact_errors=0 | 已加 `open_evidence_attachment_error_per_100` 等，待验证 C10 是否真的会动 |
| A2 | C11 legal collateral 对照对 active-world 不可见 | 该候选 active_correct=1.000 (24/24) | 已加 `unrelated_collateral_violation_per_100` |
| A3 | 5/12 家族主指标退化 | 等价 admitted 候选数：C00/C01/C09/C10=3.0，C11=4.0，其余 1.0–1.4 | 未处理 |
| A4 | 边级量看不到节点级错误 | 6,614 admitted+legal 中，fact_errors=0 但 active_correct=0 有 2,009（占 fact_errors=0 的 70.9%） | 已加 `active_node_state_error_per_100` |

建议：冻结前跑一次**机制–指标覆盖矩阵** —— 对 12 个 family 逐个验证"选一个 admitted 但错误的候选，是否至少让一个已注册的渐进指标动起来"。

## B 组：统计与门的问题

| # | 问题 | 证据 |
|---|---|---|
| B1 | `recovery_rate_within_window` 把空分母渲染成真实 0.0 | `designed_eligible` 为空时返回 `0.0` 而非 `None`；smoke 中所有方法 `designed_recovery_eligible_sequences=0.0`，却都报了 `recovery_rate_within_window=0.0`。eligibility 要求 pivot 错误恰好落在两个设计分支之一，错到第三候选记为 `out_of_scope` 被排除 |
| B2 | 共享 commit gate 可能让 A_vs_E 退化成"E 不提交" | smoke：A commit_rate=1.000，E=0.050，E ambiguity_commit_rate=0.000。`shared_across_methods=true`，单一 (commit_probability, margin_threshold) 加在尺度不同的后验上 |
| B3 | commit gate 用单步指标选，主指标是 20 步终点 | `selection: lexicographic_one_step_active_correctness_...` |
| B4 | `false_birth_growth` 是基数差，会抵消 | `max(0, len(open_entities_pred) - len(open_entities_ref))`；错删一个真实体 + 错生一个假实体 → 0，通过 ≤1.0/100 安全门 |
| B5 | n=200 检验力未估算；门是 H0: effect ≤ 0.03 而非 ≤ 0 | 需要 δ ≥ 0.03 + 0.198σ（n=201，Holm 单侧 α=0.025，power 0.80）。σ>0.20 时 200 groups 不够 |

建议 B1：空分母返回 `None` 并强制输出分母；考虑把有真实分母的 `any_first_error_recovery_*` 作为 headline。
建议 B2/B3：把已为 (lr, steps) 采纳的"共享点 + 各自最优 + 交叉读数"三读法作为**通用规则**写进合同，凡跨方法共享的单点选择都适用。

## C 组：命名与构念贴切性

| # | 问题 |
|---|---|
| C1 | `memory_contamination` 把"主动写错"和"该更新没更新"混为一谈。smoke 中 E 的 commit_rate=0.05（几乎不动）却是 contamination 最高的 32.5 —— 一个什么都不做的方法被判为污染最严重，与"避免污染长期记忆"的原始构念相反 |
| C2 | `*_per_100` 不是"每 100 次决策的发生率"，而是 `100 × 终点计数 / horizon`。名字诱导读成 rate |
| C3 | 合同成功条件写的 "post-execution graph correctness" 在实现里对应两个严格度差异很大的量：`post_graph_correct`（= `history_exact`，含关闭版本的全历史精确相等）和 `active_graph_correct`（仅当前活跃世界）。且 `post_graph_correct` 这个名字暗示的是后者 |
| C4 | 同一构念现有三个名字不同、极性/分辨率不同的量并列上报：`final_active_graph_correctness`（二值）、`unresolved_active_error`（= 1 − 前者）、`final_graded_active_world_correctness`（Jaccard） |
| C5 | `history_exactness` 与 `post_graph_correctness` 是同一个值的两个名字，都进了报告 |
| C6 | 主张句里的 "minimal-world-change prior" 在教师中近乎惰性：leave-one-out posterior mean TV 中 edit=0.0227、growth=0.0257，而 future=0.681 |
| C7 | 合同语言强调 long-horizon contamination，但注册阈值（2.0）加在终点量 `memory_contamination_per_100` 上，而非时间积分的 `memory_contamination_auc_per_100_decisions` |
