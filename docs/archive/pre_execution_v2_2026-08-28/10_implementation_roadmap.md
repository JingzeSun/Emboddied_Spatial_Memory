# 快速落地实施路线

> 状态：`current execution decomposition / not implemented`
>
> 阶段依据：[`../START_HERE.md`](../START_HERE.md)；fixture 依据：[`12_use_case_and_fixture_contract.md`](12_use_case_and_fixture_contract.md)。

## 1. 当前目标

当前只实现 S3 的最短可证伪闭环：

```text
hand-authored base belief
  + observation graph
  + oracle ContextDelta
  → schema validation
  → versioned executor
  → revised belief
  → exact graph / scope / propagation / preservation metrics
```

这个闭环不需要 GPU、DINO 或大模型。它先验证研究对象、关系语义、operator、版本链和指标是否自洽。

## 2. 工作包与依赖

| WP | 内容 | 依赖 | 产物 | 完成标准 |
|---|---|---|---|---|
| WP-00 | Python 工程和可重复环境 | 无 | `pyproject.toml`、test/lint 命令 | 干净环境一条命令运行测试 |
| WP-01 | Schema-backed contracts | current schemas | typed graph/delta/context records | JSON round-trip；非法 version/ID/enum 被拒绝 |
| WP-02 | Immutable/versioned graph store | WP-01 | graph versions、validity、supersedes | 旧版本不可原地覆盖 |
| WP-03 | Deterministic delta executor | WP-01/02 | typed operators、transaction、invariants | oracle fixtures exact match |
| WP-04 | Micro-fixture loader | WP-01 | R1A/R1B/R2A/R2B/R3A/R4A/X1A/X2A | 正例、反例、control 可重放 |
| WP-05 | Evaluator | WP-01–04 | exact/scope/propagation/preservation/cost | 人工注入错误使对应指标恶化 |
| WP-06 | Geometry/visibility | WP-00 | SE(3)、frustum、projection、visibility | 合成 round-trip 与反事实通过 |
| WP-07 | Association hypotheses | WP-06 | gated candidates、ambiguity、quarantine | perfect/noisy 两种模式可切换 |
| WP-08 | Structured innovation | WP-06/07 | typed innovations、confidence | E1 可运行且可校准 |
| WP-09 | Deterministic affected scope | WP-03/08 | seed/propagate/stop rules | E2/E5 可运行 |
| WP-10 | Learned controller | WP-08/09 | innovation/scope/operator/stop heads | validation 上超过 deterministic baseline |
| WP-11 | Perception/simulator adapter | WP-01–10 | state diff、manifest、noise adapter | 可区分模块失败来源 |
| WP-12 | ActiveContext query | WP-02 | ranked candidates、evidence trace、clarification | X2A 不污染 world belief |
| WP-13 | Formal runner/artifacts | 全部 | config-driven run、raw/aggregate outputs | 任一数字可追溯 |

依赖主链：

```text
00 → 01 → 02 → 03 → 04/05
                  ↓
             S3 oracle gate
                  ↓
06 → 07 → 08 → 09 → 10 → 11
                         ↘ 12
                           → 13
```

## 3. 里程碑

### M0：合同冻结

- 人工确认 identity、关系派生、传播、reliable absence、stop truth 和 clarification cost；
- schema/config/fixture 字段一致；
- `START_HERE`、`09`、`12` 不再有概念冲突。

验收：G2 通过。当前正在进行。

### M1：Oracle revision vertical slice

- 完成 WP-00–05；
- 运行 E0、E1 单点规则版、E2 oracle scope；
- 比较 append-only、local-slot、full-graph、oracle scope。

验收：必要传播完整、control 无非预期修改、版本/provenance 有效。未通过则回到概念或 fixture，不进入训练。

### M2：Pose-aware structured innovation

- 完成 WP-06–08；
- 区分 world change、camera motion、occlusion 和 sensor inconsistency；
- 输出校准后的 innovation mode 与证据来源。

验收：验证集 E1 明确优于标量 residual，并通过反事实检查。

### M3：Predicted affected subgraph

- 完成 WP-09；
- 比较 local-slot、full-graph、oracle、deterministic predicted scope；
- 做图规模、历史长度和 affected-ratio sweep。

验收：传播完整性与无关保持同时改善，不能只靠减少编辑数。

### M4：Learned controller

- 按 T1 innovation → T2 scope/operator/stop → T3 ambiguity 顺序训练；
- executor 保持确定性；
- 只在 train/validation 选阈值、loss、prompt 和 checkpoint。

验收：G4 通过；否则保留 deterministic 方案或收缩主张。

### M5：系统集成与正式实验

- 完成 WP-11–13；
- 逐步加入 simulator、感知噪声、长序列和真实数据；
- 接口公平时加入 FARM-style mapper/retrieval/fuse-merge 基线；
- 冻结正式测试合同后一次性运行 test。

验收：G5–G7 通过，结果与失败信息可复现。

## 4. 第一批可交付物

1. Python 包、锁文件和测试入口；
2. 五类现行 schema 的 typed records；
3. `PRESERVE/ADD/UPDATE_STATE/RELINK/INVALIDATE/SUPERSEDE/QUARANTINE` executor；
4. 五个 P0 revision fixture 与两个 P1 extension fixture；
5. exact graph、scope、propagation、preservation、stop、version 指标；
6. E0–E2 oracle/deterministic pilot 报告。

## 5. 训练工作包何时启动

只有同时满足以下条件才创建 learned controller：

- fixture ground truth 无未决语义；
- deterministic executor 100% 通过 oracle exact/invariant 检查；
- oracle scope 比 matched-slot 更完整；
- oracle scope 比 full-graph 更少 collateral edits；
- 数据 split、counterfactual group 和 validation 门槛已冻结。

## 6. 代码接口

```python
expected = project_expected_observation(base_belief, camera)
innovation = compare_structured(observation_graph, expected)
scope = retrieve_affected_subgraph(base_belief, innovation, controller)
delta = propose_context_delta(base_belief, innovation, scope)
revised = executor.apply(base_belief, delta)
context = select_active_context(revised, task, route, dialogue, camera)
```

公开 API 使用 schema-backed typed objects；controller 输出 proposal，executor 执行合同和 invariant。

## 7. 目标目录

```text
src/embodied_spatial_memory/
├─ contracts/
├─ geometry/
├─ belief/
├─ innovation/
├─ revision/
├─ context/
├─ baselines/
└─ evaluation/

tests/
├─ fixtures/
├─ contracts/
├─ geometry/
├─ revision/
└─ evaluation/
```

## 8. 正式运行产物

```text
outputs/<run_id>/
├─ config.yaml
├─ environment.json
├─ dataset_manifest.json
├─ predictions/
├─ metrics_per_episode.jsonl
├─ aggregate_metrics.json
├─ revisions/
├─ failures/
└─ run.log
```

大型数据、checkpoint、模型权重和运行输出不进入 Git。

## 9. 风险优先级

| 优先级 | 风险 | 处理 |
|---|---|---|
| R0 | Delta/stop 真值无唯一或可判定义 | 先冻结关系语义和等价类评分 |
| R0 | Oracle scope 不优于 local-slot | 停止扩模型，重审问题必要性 |
| R1 | visibility 错误支配 absence | 独立评测 projection/visibility |
| R1 | 传播标签成本过高 | 收缩 P0 edge types |
| R2 | learned controller 数据不足 | deterministic baseline + synthetic curriculum |
| R2 | full recompute 同样好且不贵 | 扩大图规模/历史 sweep；必要时收缩效率 claim |
| R3 | query 与 revision 指标脱节 | evidence-trace query；不强行保留下游 claim |

## 10. 暂缓事项

完整导航、巨大 Transformer、learned Chart split/merge、十几个数据集、backbone 调优、无约束图编辑。它们都不能替代 G2/G3 的概念和机制验证。
