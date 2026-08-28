# 04 — 训练计划：逐层移除 Oracle

> 状态：`blocked by pilot gate / no model trained`

只有 `03_pilot_protocol.md` 的 Go 条件全部满足后，本文件才生效。

## 1. 训练单位

```text
(base_belief, observation_graph, pose, visibility, history)
    → innovation category/mode
    → affected/control/stop
    → typed operations or target invariant
    → target belief version
```

必须监督“该改什么”和“绝不能改什么”。只监督最终 query answer 无法证明修订机制。

## 2. 分阶段训练

| Stage | 学习对象 | 仍保留的 oracle | 进入条件 | 退出条件 |
|---|---|---|---|---|
| T1 | innovation mode/reliability | pose、association、graph | pilot passed | 分类与校准超过规则基线 |
| T2 | affected nodes/edges | perception、association | T1 frozen | scope + propagation/preservation 同时改善 |
| T3 | operator + stop | perception、association | T2 stable | executor success，stop calibrated |
| T4 | association ambiguity/quarantine | pose、object observations | T3 stable | ID switch/false merge 可控、可恢复 |
| T5 | noisy perception adapter | fixture oracle 仅评测 | T4 stable | 噪声退化曲线可解释 |
| T6 | multi-scenario curriculum | 无训练时 oracle | T5 stable | 未见场景组合泛化 |

不要端到端同时训练全部模块；每阶段只移除一层 oracle，方便失败归因。

## 3. 模型接口

```text
InnovationHead:
  category, mode, reliability, causal factors

ScopeHead:
  affected_node_logits, affected_edge_logits

StopHead:
  stop_edge_logits

OperatorHead:
  operator type + typed arguments

CommitHead:
  commit / quarantine / ask clarification
```

GNN、graph Transformer 或其他模型只是可替换实现。论文贡献取决于输出合同和证据，不取决于 backbone 名称。

## 4. 训练目标

```text
L_total =
    L_innovation
  + lambda_node L_node_scope
  + lambda_edge L_edge_scope
  + lambda_stop L_stop_boundary
  + lambda_op L_operator
  + lambda_keep L_control_preservation
  + lambda_cal L_calibration
  + lambda_cost L_revision_cost
```

约束：

- `L_cost` 不能单独优化，否则“不修改”成为退化解；
- hard negatives 必须包含与 seed 相邻但不应修改的边；
- 多种正确 scope 用 invariant/equivalence loss；
- loss 权重只用 train/validation 选择。

## 5. 数据课程

```text
single relocation
  → absence vs occlusion
  → one-hop dependency
  → multi-hop with stop boundary
  → irrelevant innovation
  → identity ambiguity
  → repeated relocation/version chain
  → expansion + revision mixed frame
  → ActiveContext boundary case
```

## 6. 数据切分

- 主 split 单位：`scene_family`；
- 同一 counterfactual group 不跨 split；
- 同一 base scene 的渲染变体和时间相邻片段不跨 split；
- asset/trajectory template 记录独立 split；
- train：学习参数；
- validation：阈值、loss、prompt、model/checkpoint 选择；
- test：合同全部冻结后只作正式报告。

接触 test 后修改任何协议，必须建立新 protocol version 并保留旧结果。

## 7. 验证矩阵

每阶段同时报告：

- 与 deterministic controller 比较；
- 与 oracle 上限差距；
- required propagation 与 control preservation；
- calibration 与 abstention/quarantine；
- graph size、history length 和 affected ratio sweep；
- 失败按 perception/association/innovation/scope/operator/executor 分桶。

## 8. 训练成功门

学习方法必须在 validation 上：

1. 超过 deterministic baseline；
2. 不能靠减少编辑量换来明显漏改；
3. stop/control 指标不能下降；
4. 未见 scene family 保留主趋势；
5. 置信度能支持 commit/quarantine 决策；
6. 结果可由 config、seed、data hash、code/model ID 重放。

失败时允许形成 deterministic 方法或收缩主张；不默认解释为“模型不够大”。

通过后进入 [`05_formal_evaluation_and_paper.md`](05_formal_evaluation_and_paper.md)。
