# Active VSMT and historical CPMT schemas

`vsmt_vm01_contracts.schema.json` 是当前 VM-01 的机读外形合同，覆盖公开观测、封存候选、teacher 标签、共同结果、私有评价和私有扰动审计六类记录。它解决文件串线和多余字段混入的问题；输入一个 JSON 记录，输出 schema 接受或拒绝。例如带 `reference_spec` 的公开观测会因额外字段被拒绝。它不定义 BIND/BIRTH 等价、事务评分权重或模型效果；精确时间、摘要绑定、禁止信息来源和候选先于 teacher 的运行时约束由 `src/vsmt/contracts.py` 执行。

以下文件是旧 CPMT pipeline 的历史跨模块边界：

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
