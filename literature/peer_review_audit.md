# 模拟审稿审计：Projective Structural Latent Memory

审计日期：2026-09-04　｜　当前结论：有潜力，但尚未达到可投稿证据状态。

## 一句话审稿判断

研究问题比旧 posterior-only loss 更新显著更强，但各组件高度拥挤；能否成为方法创新，完全取决于 projective expectation、set-valued binding 与受控 transaction 是否形成不可被强规则/现有 mapping 系统解释的联合增益。

## 主要优点

- 把 observation region 与 world identity 分开，直面长期 memory 的核心错误。
- 同时评价错误绑定、重复 birth、幻觉扩张与 collateral revision，而非只看最终 task success。
- 用 deterministic executor 承担硬约束，避免“加 penalty 就称安全更新”。
- 保留时间、evidence 和历史版本，能够审计环境认知如何改变。

## 主要拒稿风险

1. 方法可能仍只是 DINO feature、pose warp、graph matcher 和 rule transaction 的拼装。
2. SuperMap 已覆盖 3D association/reactivation、长期变化和语言导航，claim 重叠直接。
3. 依赖 oracle depth/pose/region/node label 时，学习难度可能被人为简化。
4. 统一 transaction 若只是一组分类头和新 loss，不能支撑理论或算法贡献。
5. 没有长 rollout 与 node-growth 曲线，短序列分数无法证明 persistent memory。
6. 没有下游只读任务，世界模型/认知价值只是叙述。

## 审稿人会要求的关键实验

- 同 backbone/region 的 pose-warp、EMA slot、rule lifecycle、local graph matcher。
- 无 `PredictProject`、无 structured region、无 abstention、无 delayed birth、无 evidence/version 的消融。
- teacher-forced 与 rollout 分解；association oracle 与 transaction oracle 上界。
- duplicate birth、false merge、dynamic contamination、collateral edit 和节点增长。
- 至少一个真实噪声/重访数据结果，以及外部系统机制或数值对齐。

## 当前评级

| 维度 | 评级 | 原因 |
|---|---|---|
| 问题重要性 | 高 | 长期具身环境认知是真实瓶颈 |
| 概念清晰度 | 中高 | 合同已清楚，HC 尚未冻结 |
| 方法新颖性 | 中/待证 | 组合命题有空间，组件本身不新 |
| 技术完成度 | 低 | 尚无 executor、model 或结果 |
| 评价严谨性 | 计划中高 | 指标与 falsifier 细，但未执行 |
| 顶级 ML/AI 适配 | 当前不足 | 尚缺一般性学习原则和规模证据 |

## 继续/停止判据

只有当 M0 在公平条件下同时改善 binding stability、controlled growth 和 revision safety，且 `PredictProject` 有独立可测价值，才继续扩展完整论文。若 R2/R4/L1 同等有效，应诚实 pivot 到较小、可复现的 mapping/revision 贡献。
