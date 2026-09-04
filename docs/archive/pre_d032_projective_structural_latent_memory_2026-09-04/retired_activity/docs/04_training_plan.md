# 04 训练计划：小型神经模型 + 硬结构投影

## 训练对象

每个样本是一个在线 revision transaction，不是整段视频分类：prior graph、截至当前的 evidence events、共享 candidate facts/dependencies、predicate schema `Σ`，以及 `ΔG/M/τ/Z` 标签。

模型和 executor 边界见实验包 `LEARNED_MODEL.md`；本文件只规定训练顺序和防泄漏。

## 课程顺序

1. 无延迟、单来源、单事实修改；
2. 加入 no-change controls 和负证据 visibility；
3. 加入 event/arrival 乱序与重复 group；
4. 加入多来源冲突和 QUARANTINE；
5. 加入 dependency depth 与 protected controls；
6. 加入 valid-time interval；
7. 转入 AI2-THOR oracle，再测试 frozen perception。

主训练使用 schema-conditioned 共享编辑头；predicate-ID-only 只作消融。registered-but-unseen predicate 使用预先冻结的单列 split，不与 unseen room/delay 等 OOD 轴混成一个总分，也不通过修改输出头适配测试谓词。

curriculum 只用 train/validation 选择，正式主表另跑无课程对照。

## 目标函数

\[
L=L_{edit}+\lambda_ML_{mask}+\lambda_\tau L_{time}+\lambda_ZL_{evidence}.
\]

初始 `λM=1, λτ=1, λZ=0.5`。`state/preserve/constraint/task` 默认是评估，不是第五到第八个 loss。只有 raw loss、梯度范数和验证失败证明需要时才增加辅助项，并做独立消融。

## 候选优化配置

```yaml
optimizer: AdamW
learning_rate: [1e-4, 3e-4]
weight_decay: [1e-4, 1e-2]
batch_transactions: [16, 32]
dropout: [0.1, 0.2]
gradient_clip_norm: 1.0
precision: bf16_or_fp32
seeds: [待冻结的至少5个正式种子]
```

这些是 validation 搜索空间，不是 accepted 最优值。tiny 调试可以单 seed；正式结论至少多 seed 并报告区间。

## checkpoint 规则

不用含 test 的综合分。推荐 validation 上词典序选择：

1. 先满足 NUR 和 CPR 硬门；
2. 在满足者中最大化 transaction exact；
3. 若并列，选 ECE 更低者；
4. 再并列，选参数/延迟更小者。

若 HC-013 最终不用这些门，必须在首次正式训练前追加决策。

## 类别与图规模处理

- edit 类别长尾：weighted sampler 或 focal/weighted CE，只由 train 频率估计；
- protected controls：保留真实比例，并另外构造平衡诊断集；
- 大图：共享 candidate retrieval，记录 recall；不能让 ESGBU 获得更好的候选；
- time label 缺失：mask 掉该 loss 并计数，不丢掉整个事务；
- evidence set 多解：使用 HC-013 冻结的等价集合规则。

## 基线公平性

L2/L3/L4/M0 做 tiny/base 或参数相差不超过 10% 的配对，同时做相同 wall-clock 上限。所有方法共享 data split、seed 列表、candidate facts、early stopping 和 executor；投影前后均报。

## 任务 loss

默认不训练 `L_task`。若事实指标稳定后做 cost-sensitive 微调：阻断 task-to-fact truth 的直接信息泄漏，单独报告 before/after，并要求 NUR、CPR、time 与 calibration 不下降。否则结论只能是“为某任务偏好牺牲了真值质量”。

## 训练阶段记录

每次 run 保存四项 raw/weighted loss、各头梯度范数、mask 大小、投影拒绝、吞吐/显存、验证指标和失败样本。自动 loss balancing、PCGrad 或大 backbone 只有出现明确诊断证据时才进入新 decision。
