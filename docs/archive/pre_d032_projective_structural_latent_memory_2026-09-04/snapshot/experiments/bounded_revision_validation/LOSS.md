# 损失设计

## 主目标

四项损失与四个预测变量一一对应：

\[
\mathcal L_{core}=\mathcal L_{edit}
+\lambda_M\mathcal L_{mask}
+\lambda_\tau\mathcal L_{time}
+\lambda_Z\mathcal L_{evidence}.
\]

| 项 | 监督对象 | 推荐实现 |
|---|---|---|
| `L_edit` | `ΔG_t` | 分层 transaction NLL，处理 no-op 类别不平衡 |
| `L_mask` | `M_t` | weighted BCE/focal 或集合 Dice，同时报告 precision/recall |
| `L_time` | `τ_t` | 精确时刻用 NLL；只有区间时用 interval-censored NLL |
| `L_evidence` | `Z_t` | evidence-to-edit 多标签 BCE 或集合损失 |

起始值建议 `λM=1, λτ=1, λZ=0.5`，只是 pilot 初值；只在 validation 上按预注册网格调整。

## 为什么不直接用七项 loss

`L_state` 通常由编辑程序执行结果决定，`L_preserve` 与 mask/KEEP 重复；并列加入会重复惩罚同一错误。不可违反的结构约束应由硬投影保证。`L_task` 可能把“任务重要”误学成“事实更真”。所以 state correctness、preservation、constraint violation 和 task error 先作为核心评估，而不是默认训练项。

只有发现四项主目标无法学习某个派生性质时才增加辅助项，并做独立消融：

- `L_sparse`：mask recall 已达标但范围过宽时；
- `L_constraint_soft`：只帮助优化，最终仍保留硬检查；
- `L_task`：仅作次级 cost-sensitive 微调，且事实指标不得下降；
- GradNorm、uncertainty weighting、PCGrad：只有实际诊断出尺度或梯度冲突后再用。

## 数字例子

某 batch 的 raw loss 为 `edit=0.82, mask=0.31, time=1.20, evidence=0.44`：

\[
L=0.82+1\times0.31+1\times1.20+0.5\times0.44=2.55.
\]

若 time 梯度范数长期是 edit 的 12 倍，先检查时间单位、桶划分和标签噪声，再在 validation 比固定权重与自动平衡；不能直接在 test 上调 `λτ`。

## 必报诊断

每个 epoch 保存 raw/weighted losses、各头梯度范数、mask 大小分布、投影拒绝率、验证指标、NaN 数、缺失标签数和无合法事务数。失败样本不得从均值中静默删除。

## Loss 到实验 Criteria 的纵列

| Loss | 学到的变量 | 不能用什么假象判断成功 | 对应 Criteria | 数字触发器 |
|---|---|---|---|---|
| `L_edit` | `ΔG_t` | micro-F1 被大量KEEP抬高 | C1/C2 | micro=.95、macro=.76时仍看长尾和exact |
| `L_mask` | `M_t` | mask很小但漏改 | C3–C7/C15 | 写比例减半、NUR 97→88%，拒绝该配置 |
| `L_time` | `τ_t` | arrival time预测很准 | C8/C9 | received=968、event=602；预测968仍算错 |
| `L_evidence` | `Z_t` | attention好看 | C10/C11 | 真3选4命中2，F1=57.1%；再做删除干预 |
| hard executor | 结构合法性 | 投影后0非法掩盖原始候选差 | C13 | pre4%、reject3.5%、post0三项都报 |
| optional `L_task` | 下游偏好 | cost降低等于事实更真 | C14与C3/C5/C12联报 | cost 88→70但CPR下降即不能采用 |

是否增加 auxiliary loss 由这张表的失败模式触发，不由“loss项数看起来不够多”触发。
