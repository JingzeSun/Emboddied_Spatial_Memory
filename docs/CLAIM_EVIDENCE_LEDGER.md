# CPMT Claim–Evidence Ledger

只有达到预注册 gate 后才能把 proposed 改为 supported；代码存在只算 implemented。

| ID | 拟议 claim | 必需证据 | 状态 | 失败时 |
|---|---|---|---|---|
| CL-01 | post-edit execution 比 direct+future loss/no-execution 更有效 | M1 A vs C/E paired CI | proposed | 放弃 CTL 主创新 |
| CL-02 | future hindsight posterior 减少 transaction labels | M2 0/1/10/100% curve | proposed | 不声称 label efficiency |
| CL-03 | hindsight 可摊销为无未来 online updater | M2 teacher/student/self-rollout | proposed | 仅保留 offline reconciliation |
| CL-04 | Projective Node Orbit 支持跨视角事务评价 | M2 orbit vs EMA ablation | proposed | 替换表征，不影响 M1 定义 |
| CL-05 | CPMT 减少长期记忆污染和节点膨胀 | M2 long rollout | proposed | 不称 persistent improvement |
| CL-06 | 结论可迁移到一个 external/现实来源 | M3 evidence | proposed | 明确 simulator-only |

每次正式结果填写 run IDs、effect/CI、失败 case 和 decision reference。advisor/model 评价、unit test 或少量 demo 不是 supported evidence。

## 开发证据（不改变上述 claim 状态）

D-027，run ctl-dev-20260905T071400973427Z：四方法、三种子、1152 train/384 validation。CTL 90.54%，direct+future loss 90.89%，无执行评分器 90.63%；**不支持 CL-01 的相对优势**。小型无未来在线网络可训练，但不满足 CL-03 所需的视觉/self-rollout 证据。没有正式 test、paired CI 或 M1 gate 判定；详见 [开发结果](../experiments/counterfactual_transaction_learning/DEVELOPMENT_RESULTS.md)。白话：确认机器能学，不把它误写成方法比别人强。
