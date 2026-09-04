# 01 研究合同：学习稀疏、可追溯的世界状态后验修订

## 研究问题

给定旧结构化世界状态与截至当前收到的异步具身证据，如何学习关于最小图编辑程序、受影响范围、有效时间和证据集合的后验，同时由硬结构层保护无关事实？

\[
q_\phi(\Delta G_t,M_t,\tau_t,Z_t\mid G_{t-1},E_{\le t},\Sigma)
\]

核心难点来自部分可见、对象/关系变化、event/arrival 时间不一致、来源冲突、相关证据重复和依赖传播，不来自对象类别识别本身。

## 可证伪假设

- H1 双时间：显式建模 observed/received time 比 arrival-only 和 event-only 更能抵抗 stale overwrite；
- H2 证据充分性：visibility、source reliability 和 evidence grouping 能降低 false-negative retract 与 conflict overcommit；
- H3 稀疏边界：learned affected seed + typed hard closure 比 full-graph write 更少 collateral edits，且不降低 necessary-update recall；
- H4 可追溯后验：显式 time/evidence heads 改善有效时间、校准和审计，而不只提高 edit F1。
- H5 schema 泛化（次级）：共享 schema-conditioned updater 在 registered-but-unseen predicates 上优于 predicate-ID-only 对照；失败时只删除该泛化 claim。

任何假设消融不成立，就从论文贡献中删除；不存在“模型整体分高所以每个模块都创新”。

## 候选贡献层级

1. 新任务与 benchmark：异步证据驱动的结构化图修订事务；
2. 混合模型：ESGBU 学习 `ΔG/M/τ/Z`，executor 保证结构合法；
3. 评价：必要更新、protected controls、valid time、evidence attribution 与 task consequences 同时测量；
4. 泛化：AI2-THOR 多轴 OOD、3RScan/3DSSG 外部重扫，以及单列的 registered-but-unseen predicate 诊断。

第 1 项即使模型不胜也可保留 benchmark 价值；第 2–4 项必须靠结果升级为 contribution。

## 明确不做

- 不训练新的检测器、SLAM、开放词汇本体或完整导航；
- 不把 region binding、动作预测、主动取证、Top-K 当并列创新；
- 不让任务代价反向定义事实真值；
- 不把 attention 图当证据归因；
- 不把 simulator、自动映射和真实 ground truth 混称；
- 不承诺 RA-L/T-RO/IJRR 或“国内 A 类”录用。

## 结构化世界模型的操作性定义

基线至少具备稳定可寻址事实、显式关系/依赖和跨时刻持久增量状态，才进入“结构化 updater”组。双时间、provenance、affected boundary、valid time 和依赖一致性另逐项审计。详细见实验包 `BASELINES.md`。

## 成功判据

主结论不能只靠 edit F1，至少同时覆盖：NUR、CPR/CER、transaction exact、valid-time、calibration、evidence set、constraint rejection 和 task errors。指标定义与数字例子见 `CRITERIA.md`。

## 状态

本合同已按 D-024/D-031 重构；方法、数据和实验尚未实现或验证。HC-018/Q01 已冻结，当前等待 HC-002/Q02.2 核心谓词名单。
