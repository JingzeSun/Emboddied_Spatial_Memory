# 快速落地实施路线

> 状态：current execution decomposition
> 原则：先打通可证伪 vertical slice，再接真实 perception 和 learned controller

## 1. 最短闭环

```text
hand-authored base belief
      + observation graph
      + oracle delta
              │
              ▼
       versioned executor
              │
              ▼
         revised belief
              │
              ▼
delta / propagation / preservation metrics
              │
              ▼
structured context query
```

这个闭环不需要 DINO、GPU 或大数据。它先验证研究对象、operator、schema 和指标。

## 2. 工作包依赖

| WP | 内容 | 依赖 | 产物 | 完成标准 |
|---|---|---|---|---|
| WP0 | Python 工程与锁文件 | 无 | `pyproject.toml`、CI/本地测试入口 | 新环境可运行 schema tests |
| WP1 | Contract dataclasses | schemas | graph/delta typed records | JSON round-trip 且拒绝非法样例 |
| WP2 | Versioned graph executor | WP1 | typed operators、transaction、invariants | E0 fixtures exact match |
| WP3 | Metrics | WP1–2 | delta/scope/propagation/preservation/cost | 人工错误均使对应指标恶化 |
| WP4 | Micro fixtures | WP1 | stationary/occlusion/relocation/absence/isolate | 每类 preserve/update/isolate 可运行 |
| WP5 | Geometry projection | WP0 | SE(3)、frustum、visibility、expected observation | 合成 round-trip 和 FOV tests 通过 |
| WP6 | Observation association | WP5 | gated candidates、ambiguity | oracle/perfect 与噪声模式可分 |
| WP7 | Structured innovation | WP5–6 | typed innovations、calibration | E1 可运行 |
| WP8 | Deterministic scope | WP2、WP7 | seed/propagate/stop rules | E2/E5 可运行 |
| WP9 | Simulator pipeline | WP1–4 | state diff、delta mapper、manifest | D1 pilot 可重复生成 |
| WP10 | Learned controller | WP7–9 | GNN/graph Transformer | 超过 deterministic scope |
| WP11 | Context query | WP2 | query/evidence trace | E8 可运行 |
| WP12 | Formal runner | 全部 | config-driven run/aggregate | 任一数字可追溯 |

## 3. 第一周可交付

1. 建 Python 包、依赖锁和 test command；
2. 实现 BeliefGraph/ContextDelta 加载与 schema validation；
3. 实现 `PRESERVE/RELINK/INVALIDATE/SUPERSEDE`；
4. 建四个 hand-authored fixtures：
   - person occludes door；
   - stationary person remains actor；
   - chair relocation；
   - reliable absence with unknown destination；
5. 实现 E0 exact graph match；
6. 实现 delta precision/recall、collateral revision 和 propagation completeness。

完成后才算“方向开始落地”，不是创建空模块目录。

## 4. 第二阶段可交付

- SE(3) 与 projection；
- projected visibility；
- ObservationGraph；
- deterministic innovation；
- matched/new/occluded/reliably_absent 分类；
- deterministic affected-subgraph rules；
- append-only、EMA、local-slot、full recompute baselines。

## 5. 第三阶段可交付

- simulator counterfactual generator；
- oracle delta mapper；
- 人工审计 UI/报告；
- learned scope/operator controller；
- context query；
- E0–E8 统一 runner。

## 6. 代码接口建议

```python
innovation = compare_structured(
    observation_graph,
    project_expected_observation(base_belief, camera),
)

scope = retrieve_affected_subgraph(
    base_belief,
    innovation,
    controller=controller,
)

delta = propose_context_delta(base_belief, innovation, scope)
revised = executor.apply(base_belief, delta)
context = select_active_context(revised, task, camera)
```

公开 API 使用 schema-backed typed objects，避免模块间传递无法审计的任意 dict。

## 7. 目录目标

```text
src/embodied_spatial_memory/
├── contracts/
├── geometry/
├── belief/
├── innovation/
├── revision/
├── context/
├── baselines/
└── evaluation/

tests/
├── fixtures/
├── contracts/
├── geometry/
├── revision/
└── evaluation/
```

perception 模块在 deterministic vertical slice 后接入，防止 GPU 模型掩盖图编辑错误。

## 8. 实验运行产物

```text
outputs/<run_id>/
├── config.yaml
├── environment.json
├── dataset_manifest.json
├── predictions/
├── metrics_per_episode.jsonl
├── aggregate_metrics.json
├── revisions/
├── failures/
└── run.log
```

## 9. 风险优先级

| 优先级 | 风险 | 先验对策 |
|---|---|---|
| R0 | Delta 真值无法唯一定义 | 先做人工微图和歧义政策 |
| R0 | Oracle scope 不优于 local slot | 停止扩模型，重审问题 |
| R1 | 可见性错误支配 absence | 单独评测 projection/visibility |
| R1 | 关系传播标注成本过高 | 限制 MVP edge types |
| R2 | 学习 controller 数据不足 | deterministic baseline + synthetic curriculum |
| R2 | full recompute 更强且不贵 | 做图规模和历史长度 sweep |
| R3 | 下游 query 与图质量脱节 | 使用 evidence-trace query |

## 10. 暂缓事项

- 不先接完整导航；
- 不先训练大 Transformer；
- 不先做 Chart/Place split/merge；
- 不先扩充十几个数据集；
- 不先优化 DINO backbone；
- 不在 executor/invariants 完成前生成正式论文数字。
