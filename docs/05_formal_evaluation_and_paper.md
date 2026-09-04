# 05 正式评价、论文证据与投稿路线

## 正式表格

### Table 1：统一前端下的在线 memory 主结果

比较 patch memory、pose-warp map、IoU/appearance slots、lifecycle memory、recent-N 3D fusion、hierarchical graph、full recomputation、PSLM 与 oracle。报告 B/G/M/R/P/E 主指标，teacher-forced 与 online rollout 分列。

### Table 2：表示与绑定

fixed patches、VP-only regions、plane/surface superpoints、object-only、hybrid structural regions；无 project、geometry-only project、learned projective binding。报告 angle/overlap/pose-noise 曲线。

### Table 3：增长与长期状态

new-place、new-surface、portal、object birth、reactivation、split/merge、Chart attachment、memory budget sweep；同时报 coverage、false birth、duplicate、false merge 和 topology。

### Table 4：动态与修订

occlusion、out-of-FOV、stationary actor、relocation、reliable absence、late evidence、sensor inconsistency；报告 retention、contamination、transaction、protected controls、valid time、evidence 与 calibration。

### Table 5：预测与任务

下一视角 visibility、region retrieval、attachment/frontier prediction，以及冻结 reader 的 temporal query、object retrieval、轻量 navigation/planning。若 prediction 不产生独立收益，不使用 world-model claim。

### Table 6：OOD 与外部有效性

unseen room/layout、turn geometry、object composition、occlusion pattern、history length、graph size、change rate、pose noise 分列；重扫/真实轨单列，不与 simulator 平均。

## 统计与报告

- 正式结论至少 5 个 seeds，逐 episode paired bootstrap 95% CI；
- 报 effect size 与 raw numerator/denominator；
- test 只在 ontology、metric、baseline、threshold 和 checkpoint 冻结后运行；
- crash、silent skip、N/A、projection rejection、memory overflow 和无合法事务均计数；
- 同一物理 episode 的相似裁剪不能跨 split；
- 多 OOD 和多消融说明多重比较策略。

## Figure 计划

1. `predict-project → bind → transact` 方法图；
2. 转弯时 Chart A/B overlap 与新节点确认序列；
3. 遮挡、动态 actor、搬迁三种不同 transaction；
4. 随历史长度的 identity/duplicate/latency 曲线；
5. 成功和失败各至少两个 node-lineage 回放。

## 论文叙事

1. observation-centric latent world models 缺少长期 world identity；
2. 3D feature maps/scene graphs能构建世界，但常用 fuse/merge，缺少统一 birth-and-revision 学习目标；
3. 定义在线 projective structural memory 任务与严格判尺；
4. 提出 projective structural memory transducer；
5. 在同前端下分离 representation、binding、growth、revision 与 prediction；
6. 展示 OOD、真实失败和可证伪边界。

## 投稿判断

- 强机器人会议/RA-L 质量：一个清楚的 memory transducer、可控 simulator、强基线、在线效率和至少有限真实序列；
- T-RO/IJRR：在上述基础上需要真实机器人长序列、跨域、在线规模与更深机制/安全分析；
- TPAMI/JMLR/AIJ 等通用 ML/AI 目标：必须把方法提升为跨环境/跨 schema 的通用结构学习机制，最好有 equivariance、structured inference、校准或 revision 性质，而不是只在一个机器人管线里集成模块。

具体 venue 等结果形状再定，不以目标刊名反推夸大 claim。

## 投稿前硬门

- schema/executor/evaluator 经过 deliberate corruption；
- 最强规则和 recent-N/full recomputation 基线公平；
- 绑定、增长、保持/修订至少三类主指标联合改善；
- action-conditioned prediction 有独立证据才称 world model；
- simulator ID/OOD 完整且无 test 调参；
- 至少一个外部/真实轨，或明确限定模拟器结论；
- 代码、配置、manifest、失败与 lineage 可复现。
