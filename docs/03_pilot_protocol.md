# 03 — Pilot 协议：先证明机制，再训练

> 状态：`planned / implementation not started / thresholds not frozen`

本文是第一版代码和实验的唯一合同。

## 1. Pilot 问题

在 oracle pose、visibility、association 和 graph input 下：

1. typed delta 能否无歧义执行并生成正确版本？
2. affected-subgraph 是否比 local-slot 少漏必要关系？
3. 是否比 full-graph 少修改无关状态、成本更低？
4. relocation、absence、occlusion 和 expansion 是否走不同状态路径？

若 oracle 条件下答案是否定的，不训练神经网络。

## 2. 实现顺序

| Block | 实现 | 产物 | 通过条件 |
|---|---|---|---|
| B0 | Python 环境、test/lint | `pyproject.toml`、lock、test command | 干净环境可运行 |
| B1 | schema-backed records | `src/.../contracts/` | 合法 JSON round-trip，非法数据拒绝 |
| B2 | immutable graph/version store | `src/.../belief/` | 旧版本不原地覆盖，链无环 |
| B3 | typed deterministic executor | `src/.../revision/executor.*` | oracle delta 生成 expected graph |
| B4 | fixture loader | `tests/fixtures/` | R1–R6/X1/X2 可重放 |
| B5 | evaluator | `src/.../evaluation/` | 人工漏改/多改/越界使对应指标恶化 |
| B6 | deterministic controllers | `src/.../innovation/`、`revision/` | 规则基线可运行、证据可解释 |
| B7 | run/artifact layer | config runner、outputs manifest | 任一结果可追溯 |

依赖：`B0 → B1 → B2 → B3 → B4/B5 → B6 → B7`。

## 3. 第一版代码范围

```text
src/embodied_spatial_memory/
├─ contracts/
├─ belief/
├─ revision/
├─ innovation/
├─ context/
├─ baselines/
└─ evaluation/

tests/
├─ fixtures/
├─ contracts/
├─ revision/
└─ evaluation/
```

暂不接 detector、DINO、真实 RGB-D、导航或 learned controller。

## 4. Executor 操作

最小支持：

- `REINFORCE`；
- `ADD`；
- `UPDATE_STATE`；
- `RELINK`；
- `INVALIDATE`；
- `SUPERSEDE`；
- `PRESERVE`；
- `QUARANTINE`。

每次 operation 必须包含 target、before/after、evidence、confidence、valid time 和 provenance。整个 delta 事务失败时不得产生半提交版本。

## 5. 机制型基线

| ID | 方法 | 检查的失败机制 |
|---|---|---|
| P0 | Append-only | 不会关闭错误旧状态 |
| P1 | Pose-warped global EMA | 对齐后全局软更新仍缺 typed edit |
| P2 | Slot lifecycle/local matched-slot | 只改实体、不传播关系 |
| P3 | Full graph recomputation | 准确但范围/成本可能过大 |
| P4 | Oracle affected-subgraph | 问题和 executor 的机制上限 |
| P5 | Deterministic predicted scope | 可解释可落地基线 |
| P6 | FARM-style fuse/merge | 对象融合在动态冲突下的污染风险 |

所有主比较共享同一初始图和 observation/association 输入。

## 6. Pilot 实验顺序

### E0 — Contract wiring

- 输入：oracle graph/delta/scope；
- 结果：expected graph exact/invariant match；
- 目的：证明 schema、executor 和 evaluator 没接错。

### E1 — Single-state revision

- fixtures：R1、R3、R4；
- 比较：append-only、local-slot、oracle scope；
- 目的：区分 relocation、absence、occlusion。

### E2 — Propagation and stop

- fixtures：R2、R6；
- 比较：local-slot、full-graph、oracle scope；
- 目的：同时证明必要传播和无关保持。

### E3 — Ontology invariant

- fixture：R5 duration/occlusion sweep；
- 目的：静止时长不把 actor 固化为 structure。

### E4 — Boundary tests

- X1：attachment precision/recall、false revision；
- X2：candidate recall@K、clarification、world preservation；
- 目的：证明 expansion/context 没有污染 P0 revision 状态。

## 7. 指标

核心：

```text
scope precision / recall / F1
operator accuracy
required propagation recall
stop-edge accuracy
control-subgraph preservation
collateral revision rate
target graph invariant accuracy
version/provenance validity
edited-node ratio
latency / memory / storage growth
```

边界指标不能替代核心指标：query accuracy 高，不代表 revision scope 正确。

## 8. Go/No-Go

进入训练必须同时满足：

1. E0 所有 fixtures exact/invariant match；
2. oracle scope 比 local-slot 完成更多必要关系后果；
3. oracle scope 比 full-graph 少无关修改且成本更低；
4. R3/R4 单因素变化触发不同正确 operator；
5. R5 ontology invariant 全通过；
6. X1 不误关闭旧事实，X2 不删除非 top-1 实例；
7. 所有失败能定位到 schema、executor、ontology 或 fixture。

### No-Go 后怎么办

| 失败 | 行动 |
|---|---|
| E0 失败 | 修 schema/executor |
| local-slot 与 oracle 无差异 | 重审关系传播是否是问题 |
| full-graph 同样便宜且稳定 | 收缩效率/局部性 claim |
| stop 真值不一致 | 改成 invariant/equivalence scoring |
| absence/occlusion 不可判 | 收紧 evidence rubric 或取消该 claim |

## 9. 运行产物

```text
outputs/<run_id>/
├─ config.yaml
├─ environment.json
├─ dataset_manifest.json
├─ predictions/
├─ revisions/
├─ metrics_per_episode.jsonl
├─ aggregate_metrics.json
├─ failures/
└─ run.log
```

Pilot 只用于机制调试，不作为最终论文数字。通过后进入 [`04_training_plan.md`](04_training_plan.md)。
