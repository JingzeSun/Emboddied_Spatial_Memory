# HC-006 Metrics and Gates

- 状态：M1 v1 已由 D-031 冻结
- 最早激活：M1；当前 active
- 建议默认：primary 为 post-execution graph correctness、memory contamination、false-birth growth、collateral violation；主对比 A–C 与 A–E，paired bootstrap 95% CI。

研究者必须在看 test 前填：

- 最小有意义效应：____
- safety 非劣 margin：____
- candidate coverage@K 最低门：____
- 每 family 最低 support：____
- self-rollout horizon：____
- 多重比较策略：____

M1 v1 冻结填写（D-030/D-031）：

- 最小有意义效应：A 相对 C/E 的 post-graph correctness 至少 +3 percentage points，且 20-step contamination 每 100 决策至少减少 2；两者校正后 95% CI 均排除 0；
- safety 非劣 margin：false-birth growth 每 100 决策 +1，collateral violation 每 100 决策 +0.5；invariant violation 必须为 0；
- candidate coverage@16 最低门：总体 98%、每 family 95%；
- 每 family 最低 test support：200 paired groups；
- self-rollout horizon：20 个决策；
- 多重比较策略：A–C/A–E 两项 primary contrast 使用 Holm–Bonferroni，family-wise alpha=0.05；按 paired_group_id、family 分层 bootstrap 10,000 次。

这些是正式结果之前的建议门槛，不是从 test 倒推的数字；完整单位、例子和“不等于什么”见 [M1 hard-condition](../../experiments/counterfactual_transaction_learning/HARD_CONDITION_EXPERIMENT.md)。

若未填，不得以 test 数值补写。

日期 / 理由 / 影响：2026-09-06；把是否值得继续扩模型变成可证伪条件；研究者已接受，test 仍等待实现验证。
