# CPMT Metrics and Criteria

## Primary

1. post-execution graph correctness；
2. long-horizon memory contamination；
3. false birth / node growth；
4. protected or collateral violation。

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
- recovery time、storage growth、p50/p95 latency。

## Label efficiency

报告 0%、1%、10%、100% transaction-label settings。所有设置仍使用相同 transaction language、executor 和数据；只改变人工 transaction labels 的可用量。

## Statistics

formal evaluation 至少 5 seeds，case-level paired bootstrap 95% CI；A vs C/E 报 effect 与 CI。每个 template 报 support 和 numerator/denominator，失败 run 不丢弃。

数值 gate 在 test 前冻结。safety/invariant 优先于 aggregate accuracy，禁止 composite score 掩盖 protected violations。
