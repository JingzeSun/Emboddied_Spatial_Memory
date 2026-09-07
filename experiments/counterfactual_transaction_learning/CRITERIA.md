# CPMT Metrics and Criteria

## Primary

1. D-044–D-047 train-only 开关选定的 final active-world semantic correctness（exact 首选、同构 graded 仅在 exact 退化时一次 fallback；完整 history exactness 另列诊断）；
2. final graded open-memory support correctness；
3. `open_fact_error_auc_per_100_decisions`（extra + missing 开放边状态的全过程负担，不互相抵消）。

三项是 co-primary，A–C/A–E 必须同时通过：semantic 与 open-memory 的最小绝对改善均为 0.03，open-fact AUC 的最小绝对减少为 D-046 冻结的 40。false birth、active-node error、protected/unrelated collateral 和 executor invariant 是 safety，不可由主效果抵消。旧 `memory_contamination` 只是终点 extra-open-fact compatibility alias，不代表最初愿景的 Dynamic Contamination Rate（DCR）；独立 dynamic/transient memory 与 DCR 留到 M2/M3。

白话：全过程开放边负担解决“前十九步一直错、最后一步修好却被终点量完全原谅”的问题。输入是每一步预测与 reference 的开放边集合，输出是 extra 和 missing 错误在 20 步中的累计暴露；例如一条过时边留十步会计十步，同时漏掉的新边另计。最小门 40 是“20 步持续等价”建模假设，对应每组平均减少 8 个错误事实×决策步暴露；它不是 terminal 的单位换算、不是错误事件发生率、不是原始动态目标覆盖静态槽的 DCR，也不替代节点和 evidence 指标。probe 看到的尺度或 SD 不能回调此门。

## Learning diagnostics

- intent/template macro-F1；
- program exact/equivalent match；
- candidate coverage@K；
- hindsight teacher accuracy；
- online amortization gap；
- self-rollout degradation；
- valid-program rate。

## Graph diagnostics

- identity F1/ID switches；
- reactivation、relink、retract correctness；
- split/merge correctness；
- edge/topology F1；
- provenance/invariant survival；
- recovery-within-3、recovery time、storage growth、p50/p95 latency；conditional recovery 必须同报 eligible denominator，空分母写 `null`。`unresolved_active_error` 只留兼容明细，不进正式主表。
- 固定 `(0,0)` gate 下同报 `commit_attempt_rate`、实际 `commit_rate` 和 `executor_quarantine_rate`；attempt 固定为 1，且等于后两者之和。

## Label efficiency

报告 0%、1%、10%、100% transaction-label settings。所有设置仍使用相同 transaction language、executor 和数据；只改变人工 transaction labels 的可用量。

## Statistics

formal evaluation 至少 5 seeds，以 `paired_group_id` 为不可拆分单位做 10,000 次 paired bootstrap 95% CI；A vs C/E 报 effect、CI 与 Holm 校正。每个 template 报 support 和 numerator/denominator，失败 run 不丢弃。

数值 gate 在 test 前冻结。safety/invariant 优先于 aggregate accuracy，禁止 composite score 掩盖 protected violations。
