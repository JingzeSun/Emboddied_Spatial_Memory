# 实验协议

## Phase 0：冻结判尺，不训练

1. 完成 HC-004/005/013/015/016/017/018/019；
2. 冻结 canonical schema、等价事务、metric version 和 candidate hard gates；
3. 建立 12 个 smoke families，每例由人复核 oracle edit、affected/protected、time、evidence 与 task delta；
4. evaluator 对 oracle 必须 100%，对故意错误必须报预期失败。

退出条件：不是“文档写完”，而是任意输入都能生成可追溯的评分和失败原因。

## Phase 1：确定性反证

跑 R0–R3 与 O0。每个方法、每个 case 保存投影前事务、投影后事务、版本 diff 和全部指标。

若简单 incident-edge recompute 已在 S01–S11 上等价于 oracle，则“学习稀疏影响范围”的必要性被削弱；先增加真实困难因子或收缩论文，不急着训练。

## Phase 2：symbolic 学习 pilot

只开 train/validation。顺序为 L0 → L1 → L2 → L3 → L4 → M0-tiny。一次只改变一个模块；统一候选 facts、hidden 档、step 预算和 early stopping。

进入下一阶段的必要条件：学习模型优于规则，且 M0 相对 L2/L4 的优势不只在 edit F1，还至少覆盖保护/校准/时间中的两类。

## Phase 3：AI2-THOR

先生成少量 development episodes 打通 oracle/frozen perception 两轨，再冻结数据生成器与 split。正式实验至少 5 个 seeds；逐场景 bootstrap 95% CI，并做 paired 比较。

主表：ID + unseen room。OOD 表分别改变 delay、conflict、change frequency、composition 与 dependency depth，不把多轴混成一个无法解释的“hard split”。

## Phase 4：3RScan/3DSSG 外部有效性

不改主阈值。先 zero-shot；若域适配，另用 validation scans 并报告 adapted 结果。只评价数据真正支持的对象/关系变化和区间时间，不伪造 arrival/source 标签。

## Phase 5：消融与失败分析

按预注册顺序：无双时间、无 source、无 visibility、无 grouping、无 typed edges、无 mask、无 time head、无 evidence head、无 executor、可选 task loss。每次只关一个组件。

失败案例至少按 stale overwrite、false negative、conflict overcommit、missed dependency、collateral edit、time error、wrong evidence、projection rejection 分类。

## 数据隔离

- train：拟合参数；
- validation：阈值、loss 权重、提示、early stopping、checkpoint 与 baseline 超参；
- ID-test/OOD-test/external-test：只在合同冻结后运行；
- 看过 test 后的任何改动产生新版本和新 test，不得覆盖旧结果。

## 正式运行必须保存

```text
run_id, timestamp, decision_ids, contract_hash, metric_version,
code_commit, dirty_diff_hash, environment, hardware,
data_manifest_hash, split_hash, generator_version,
model/baseline ID, parameter_count, FLOPs,
seed, optimizer, loss weights, checkpoint rule,
raw predictions, projected predictions, metrics, failures.
```

主结论报告 effect size 与不确定性，不只报 p-value；同一场景/事件流方法间用 paired bootstrap 或预注册配对检验。多 OOD/消融检验说明是否校正多重比较。
