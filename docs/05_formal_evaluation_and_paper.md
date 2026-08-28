# 05 — 正式评测、论文与复现

> 状态：`future protocol / no formal results`

本文件只在 pilot 和训练门通过后执行。

## 1. 系统集成顺序

逐层增加现实风险，不把所有噪声一次引入：

1. oracle graph 的组合泛化；
2. simulator RGB-D + known pose；
3. estimated detector/depth；
4. pose/depth/detection noise sweep；
5. 长序列、回访和多次搬迁；
6. 真实动态序列与人工审查；
7. 接口公平时接入 FARM-style mapper/retrieval。

分别报告 perception、association、revision 和 query 失败，不能用端到端准确率掩盖模块原因。

## 2. 正式实验包

| Experiment | 支持的 claim |
|---|---|
| F1 structured innovation | typed evidence 优于 scalar residual |
| F2 affected scope | 必要修改范围可预测 |
| F3 propagation/stop | 必要传播与无关保持同时成立 |
| F4 semantic counterfactuals | relocation/absence/occlusion/unknown 可分 |
| F5 stationary actor | motion 不改变 ontology |
| F6 robustness | pose/depth/perception 噪声下仍可用 |
| F7 efficiency | 局部修订不是隐式全图重算 |
| F8 downstream query | 修订质量对任务读取有实际价值 |

X1/X2 作为 boundary/case study 单独报告，不代替 F2/F3。

## 3. 主张冻结

正式 test 前建立：

```text
claim
  → experiment
  → dataset/split
  → baseline
  → metric
  → statistical test / confidence interval
  → expected falsifier
```

冻结：

- experiment contract version；
- dataset manifest/split hash；
- thresholds、prompt、loss 和 checkpoint；
- random seeds；
- model/code identifiers；
- exclusions 和 missing-data policy。

## 4. Related Work 使用规则

- `verified_peer_reviewed + foundation/adjacent` 才能作为事实主干；
- preprint/submission 只作 novelty watch，正文出现时明确状态；
- FARM 投稿前重新核验 venue；
- 不声称 first structured memory、first dynamic memory、first selective update 或 first relational retrieval；
- perception/backbone 收益与 revision mechanism 分开归因。

权威清单：`literature/library.csv`、`literature/peer_review_audit.md` 和 `literature/notes/`。

## 5. 论文结构

```text
1 Introduction
  problem → gap → narrow claims → evidence summary

2 Related Work
  construction → dynamic/persistent memory → selective read → belief revision

3 Problem Formulation
  four states → innovation → affected/control/stop → versioned delta

4 Method
  projection → innovation → scope/propagation/stop → executor

5 Experimental Protocol
  counterfactual groups → baselines → metrics → split/test rules

6 Results
  claim-by-claim, including failures

7 Limitations and Ethics
  sensor assumptions → ontology/annotation limits → open-world uncertainty
```

章节按 claim/evidence 组织，不按代码模块堆叠。

## 6. 投稿前证据门

- 每条 contribution 有 baseline、metric、ablation 和 falsifier；
- 主表数字来自冻结正式协议；
- confidence interval/统计方法明确；
- negative result、反例、缺失和失败均记录；
- 自动估计或模型评审没有称为 ground truth；
- test 没有用于模型/阈值/prompt 选择；
- 主图和表格可从 run artifacts 重建。

## 7. 可复现产物

发布或提供：

- schema、config 和 version；
- micro fixtures 与 evaluator；
- deterministic baselines；
- data generation/validation scripts；
- environment/lockfile；
- seed、data/split hash、code/model ID；
- raw per-episode metrics 和失败引用；
- 至少一个干净环境重放命令。

大型数据、checkpoint、PDF 和运行输出不提交 Git，通过外部存储和 manifest 管理。

## 8. 结论强度规则

| 证据达到 | 最多能写 |
|---|---|
| 只有合同/fixtures | we formulate / propose to evaluate |
| oracle pilot | mechanism is executable under oracle inputs |
| validation model results | learned controller improves on validation scope |
| frozen formal test | method supports正式论文 claim |
| external/real replication | stronger generalization statement |

不要让写作领先于证据阶段。
