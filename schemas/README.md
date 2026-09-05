# CPMT Schemas

这些 JSON Schema 定义 CPMT pipeline 的跨模块边界：

- observation_region：决策时刻可用的结构观测；
- evidence_event：不可覆盖的证据记录；
- world_graph：versioned persistent memory；
- transaction_program：两级 intent/template 事务与有序 primitives；
- candidate_rollout：候选执行、未来预测和分项能量；
- counterfactual_case：paired case、oracle equivalence 与 split metadata；
- commit_decision：固定门槛下 COMMIT/QUARANTINE 的可重算决定；
- pending_memory：不进入 world graph 的弱证据、检索键、机会轮次与消费审计；
- equivalence_policy：身份双射与“future projection 不定义状态等价”的保守比较约束；
- run_manifest：复现实验和失败审计。

所有 schema 使用 JSON Schema 2020-12。实现必须先 schema validate，再执行语义 invariant；schema 合法不代表事务语义合法。

当前 contract version 是 cpmt-0.2。旧 PSLM schemas 可从 archive/pslm-pre-ctt-20260904 的 eba4339 恢复，不再作为 main 的活动接口。
