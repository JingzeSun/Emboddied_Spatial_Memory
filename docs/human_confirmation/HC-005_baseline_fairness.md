# HC-005 Baseline Fairness

- 状态：M1 v1 已由 D-031 冻结
- 最早激活：M1；当前 active
- 建议默认：A–E 共享前端、split、train steps 与参数量区间；A/D/F 相同 candidate K；同时报告 wall-clock/显存。

需确认 direct+future-loss 是否获得独立合理调参、MHT/scene-graph updater 的实现来源、full recomputation 的计算预算，以及无法复现公开实现时的处理规则。

M1 v1 冻结选择（D-030/D-031）：A=`CPMT-CTL Core`，固定 A–F；A–E 共用 online encoder/输入/split/学生更新数，参数量差异不超过 10%，每方法最多 6 次 validation trial；C 单独在 auxiliary weight={0.1,1,10} 选择；E 的额外 scorer 参数、更新和资源单列；A/D/F 共用 deterministic K=16；F 仅作 upper bound。MHT/scene-graph updater 留到 M1 通过后的 M2，full recomputation 当前不进入主比较。所有方法选择最终事务后用同一 executor 计算图指标。

研究者选择：v1 已确认；Full CPMT 名称保留给 M2 接入 PNO 后的完整系统；test 尚未解封。

日期 / 理由 / 影响：2026-09-06；先排除 direct+future loss 与 no-execution 解释，同时明报 E 的额外计算；当前仅配置/校验，不是结果。
