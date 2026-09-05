# Contract Fixtures

这里提交小型、可人工逐行审计的 JSON fixture，不提交正式数据。

每个 fixture 包含 prior graph、current observation、candidate programs、oracle equivalence、future evidence、expected post-graph、protected IDs、paired_group_id 和 split placeholder。

M0 目标是 C00–C11 加 corruption variants。HC-001 未确认前，只能创建 draft，不得标 ground truth。

当前已添加 C00–C11，每个目录包含 case.json、world.json 和竞争事务；C01 另含 candidate 显式确认的 draft 正例。C04/C05 检查 SPLIT/MERGE，C06/C07 检查 REPLACE/RETRACT，C08 检查拓扑改变与临时阻挡，C09 检查 pose fault、真实修改与 QUARANTINE，C10 检查动态 actor 污染，C11 检查 collateral/protected state。

C09 的 `commit/uncertain.json` 与弱 evidence 用于 D-023 pending-memory 合同。全部案例仍为 human_draft；单元测试只验证可执行语义，不把 oracle 标记当作已经验证的科学结论。
