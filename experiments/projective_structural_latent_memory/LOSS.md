# 损失设计

## 原则

Loss 只实现概率结构，不作为创新来源。association、birth、scope、operator、time 和 evidence 不能被写成互相独立却声称“联合后验”的平行 heads。

## 层级目标

令 `X_t=(R_t,Rhat_t,S_(t-1),a_(t-1),Sigma)`：

\[
q(A,U\mid X)=q(A\mid X)
q(g\mid A,X)
q(M\mid g,A,X)
q(\Delta,\tau,Z\mid M,g,A,X).
\]

核心训练目标为：

\[
L_{core}=L_{project}+\lambda_A L_{association}+\lambda_U L_{transaction}.
\]

| 项 | 监督对象 | 推荐实现 | 不适用时 |
|---|---|---|---|
| `L_project` | expected support/visibility/latent | visibility CE + masked latent distribution/retrieval loss | 无动作未来标签时只训当前pose投影 |
| `L_association` | set-valued A | bipartite/set NLL，带 dustbin、split/merge | 无可见候选仍保留NEW/UNRESOLVED |
| `L_transaction` | gate→scope→typed ops/time/evidence | conditional transaction NLL | 分支不存在则mask并计数 |

`L_transaction` 内部可以记录 raw branch losses，但论文方法仍是一个条件化事务似然；不能因为日志有七列就宣称七个任务创新。

## 防退化

- 全部 `UNRESOLVED/QUARANTINE`：由 coverage、birth recall 与 selective-risk curve 暴露；
- 从不 birth：G1 new-node recall 暴露；
- 每帧都 birth：duplicate/false birth 与 memory growth 暴露；
- 永久 freeze：真实 relocation/revision 指标暴露；
- 全图 rewrite：protected/collateral 与效率暴露；
- latent collapse：matching retrieval、dispersion 和 view-conditioned prototype 使用率暴露。

## 可选辅助项

只有验证失败诊断支持时才加入：

- identity contrastive：同一 node 跨视角不可分时；
- diversity/prototype regularizer：所有 prototype 坍缩时；
- calibration loss：温度缩放等后处理不足时；
- sparsity regularizer：必要召回已过门但 active scope 过宽时；
- task loss：只作次级微调，且 memory truth 指标不得下降。

每项必须有 before/after、梯度诊断和独立消融。

## 硬约束不进入 soft loss 冒充保证

ID 唯一、version 无环、candidate/confirmed 权限、protected controls、坐标合法、valid time、provenance 和 atomic commit 由 executor 强制。论文同时报告 pre-violation、repair/rejection 与 post-violation。

## 必报训练诊断

- raw/weighted 三项 core loss；
- transaction 内每个实际分支样本量和损失；
- 各模块梯度范数与 cosine；
- bind/new/unresolved、birth/merge/revision 预测分布；
- active node/region 数与 prototype 使用率；
- teacher-forced/online rollout 差距；
- missing label、N/A、NaN、executor rejection 和失败样本。
