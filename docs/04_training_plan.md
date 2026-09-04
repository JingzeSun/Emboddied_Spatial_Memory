# 04 训练计划：层级 memory transducer，而不是平行 loss 堆叠

## 训练样本

每个样本是一段在线更新前缀，不是孤立图片或单次事实分类：

```text
previous world memory S_(t-1)
current RGB/depth/pose/action/time
observation regions R_t
projected expectation Rhat_t
oracle association A_t
oracle memory transaction U_t
next observation / next world state labels when available
```

训练时可以 teacher-force oracle prior memory；正式 online rollout 必须同时报告使用模型自身历史造成的误差累积。

## 层级因子化

模型不宣称四个独立 head 等于联合后验。推荐显式因子化：

\[
q(A,U\mid X)=q(A\mid X)
q(g\mid A,X)
q(M\mid g,A,X)
q(\Delta,\tau,Z\mid M,g,A,X),
\]

其中 `g` 表示 `bind/new/reactivate/split/merge/unresolved` gate，`M` 是允许写入范围，`Delta/tau/Z` 是创建或修订事务。不存在的分支不计算伪标签 loss。

## 核心目标

\[
L_{core}=L_{project}+\lambda_A L_{association}+\lambda_U L_{transaction}.
\]

- `L_project`：当前 pose/action 下 expected visibility、对应 region 与 structural latent 的预测；
- `L_association`：带 dustbin/abstention 的 set matching，覆盖 bind/new/reactivate/split/merge；
- `L_transaction`：层级 transaction NLL，内部条件化 birth/attachment/revision/scope/time/evidence，而不是把七个互相重复的 loss 并排相加。

identity contrastive、sparsity、calibration、task loss 只在诊断表明必要时加入，并必须有独立消融。executor legality、protected invariance 与版本无环是硬验证，不靠 soft loss 假装保证。

## 课程顺序

1. oracle regions + oracle pose 的一对一 binding；
2. partial overlap、out-of-FOV 与 reappearance；
3. new-node birth 和 delayed confirmation；
4. region split/merge 与 perceptual aliasing；
5. Chart attachment 与转弯 overlap；
6. transient/occlusion/stationary actor；
7. relocation/reliable absence/late evidence revision；
8. pose/depth/region noise；
9. action-conditioned next-view prediction；
10. online self-rollout 与 simulator OOD。

curriculum 只使用 train/validation；正式主表另跑无课程或统一预算对照。

## 候选优化配置

```yaml
optimizer: AdamW
learning_rate: [1e-4, 3e-4]
weight_decay: [1e-4, 1e-2]
sequence_length: [4, 8, 16]
max_regions_per_frame: [32, 64]
max_active_nodes: [128, 256]
hidden_dim: [128, 256]
dropout: [0.1, 0.2]
gradient_clip_norm: 1.0
precision: bf16_or_fp32
formal_seeds: at_least_5_pending_HC_031
```

这些是 validation 搜索空间，不是 accepted 最优值。

## checkpoint 规则

候选词典序：

1. 先满足 association recall、false merge、duplicate birth 与 protected-memory 硬门；
2. 在满足者中最大化 transaction exact 和 attachment exact；
3. 再比较 online rollout retention 与 calibration；
4. 再并列时选 p95 latency/memory 更低者。

正式规则由 HC-031 在 test 解封前冻结。

## 公平训练

- 所有方法共享 frozen backbone、region proposals、depth/pose 和数据顺序；
- representation ablation 只替换 tokenizer，update policy 保持一致；
- update ablation 共享 tokenizer/projector；
- 参数匹配、训练 step 匹配和 wall-clock 匹配分别报告；
- candidate/binding recall 单独报告，不能让 PSLM 获得更强前端；
- online rollout 与 teacher-forced 结果分列。

## 运行记录

每次 run 保存 raw/weighted losses、各条件分支样本数、梯度范数、region/node 数、birth/merge 分布、projection rejection、teacher-forced 与 rollout 指标、显存/延迟、缺失标签、崩溃与失败样本。
