# Baselines

## M1 必做

1. Direct transaction classifier；
2. Direct classifier + future auxiliary loss；
3. Execute candidates + current-only score；
4. Future scorer without post-edit execution；
5. Oracle candidates/program。

M1 的 CPMT-CTL Core 加上述五项构成 A–F，不再同时实现十多个比较。Full CPMT 名称保留给 M2 接入 Projective Node Orbit 后的完整系统。

## M2 只增加一个领域强基线

在 M1 通过后，从 MHT/data association、SuperMap-style updater 或 standard scene-graph updater 中选择一个与最终数据接口最匹配、能够公平复现的强基线。选择理由和实现差异必须记录。

Additive memory、recent-window 和 full recomputation 仅在它们能排除新的关键解释时进入附加实验。

## 公平协议

- 相同 observation front-end、train/validation/test 和 online fields；
- 候选式方法相同 K；
- 参数、optimizer、steps、early stopping 和 validation 次数对齐或披露；
- 同时报告质量、wall-clock、显存、p95 latency 和 memory growth；
- 原实现优先；复现失败必须记录，不以故意弱化版本代表对方；
- test 不为某一方法单独选阈值。

## 禁止

- CPMT 使用 oracle pose/depth 而 baseline 使用 noisy sensors；
- CPMT online 输入含未来；
- 只报平均分而隐藏 family support、非法 program 或灾难性污染。
