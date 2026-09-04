# 论文级别与证据门槛

状态：内部审稿合同；不是对录用的保证。

## Gate 0：可执行而非概念

- schema、fixtures、executor 和指标测试完整。
- 至少 S00–S11 可重放；oracle 与 corruption 经人工复核。
- 明确报告“已实现/已验证/计划中”。

未通过时只适合内部方法提案。

## Gate 1：不是又一次规则更新

- M0 胜过 R2/R4、L0/L1，而非只胜 R0。
- old ESGBU-only 消融不能解释主要收益。
- `PredictProject`、binding、birth/attachment、transaction 至少三项有可重复独立贡献。

未通过时应缩为稳健映射或 revision 模块论文。

## Gate 2：长期与在线属性成立

- 长 rollout 中 B2/B3/B4、M1/M2 和 G4 受控。
- 在线增量成本相对 full recomputation 有明确优势。
- 不是依靠无限增长、过度 abstention 或 oracle pose 泄漏。

## Gate 3：强机器人/视觉论文证据

- 至少一个标准模拟或真实回放基准，跨 unseen scene/layout。
- 与可对齐的强外部方法比较；完整效率与失败分析。
- 至少一个下游任务从 memory 获益。

## Gate 4：顶级 ML/AI 期刊候选

除 Gate 0–3 外，至少满足两项：

- 跨任务、跨传感器或跨环境的明显一般化，而非单一机器人 pipeline。
- 对部分可观测下 latent world memory 的新建模或学习原则，有清楚数学解释。
- 新 benchmark/协议揭示现有 latent world model 与 scene memory 的系统性缺口。
- 规模和统计强度足以支撑普适结论，且核心增益不依赖特定 backbone。
- 对 association/birth/revision 的不确定性或一致性给出可验证的新机制。

只有“DINO latent + 节点 + 新 loss”不够通过 Gate 4。

## Stop / Pivot 条件

- 公平规则基线达到同等质量与更低成本。
- node identity oracle 本身无法可靠定义或标注一致性过低。
- 预测模块无法独立评价，也不帮助绑定/行动。
- 真实噪声下一直依赖 oracle pose/depth 才成立。
- 下游收益在冻结 test 上消失。

触发后应保留负结果并记录 pivot，不继续堆模块掩盖核心假设失败。

