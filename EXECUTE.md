# 当前执行页

> 这是项目唯一的日常执行入口。
>
> 当前阶段：`A — 冻结可判分合同`
>
> 当前状态：`in progress / no implementation / no experimental evidence`

## 现在先做什么

完成 A1–A3。完成前不搭大模型、不收大数据、不写论文结果。

### A1：人工冻结六项语义

在 [`docs/DECISIONS.md`](docs/DECISIONS.md) 新增 D-016，明确：

| 决策 | 推荐默认值 | 为什么必须人工确认 |
|---|---|---|
| 搬迁 identity | 高置信关联时保持同一 ID；低置信进入多假设 | 决定是 `SUPERSEDE` 还是 `ADD` |
| 关系存储/派生 | `supports/contains` 存储；`near/above/located_in` 逐项决定 | 决定关系是否需要显式编辑 |
| 传播依赖 | 只沿人工许可的 operator-specific relation | 决定 affected truth |
| reliable absence | 旧址应可见、无可信遮挡、传感器可靠、多帧满足 | 决定 preserve 还是 invalidate |
| stop truth | 接受满足 target invariant 的多个最小范围 | 避免伪造唯一 ground truth |
| clarification | 候选歧义会导致不同且有代价的行动时询问 | 决定 ActiveContext 行为，不改变世界事实 |

产物：D-016。验收：六项都能直接转成 fixture 字段或判分规则。

### A2：写八个 micro fixtures

严格按 [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md) 写：

```text
P0 core revision
├─ R1 chair relocation
├─ R2 cart-box relation cascade
├─ R3 reliable absence, destination unknown
├─ R4 occlusion control
├─ R5 stationary person remains actor
└─ R6 irrelevant innovation / stop

P1 boundary tests
├─ X1 corner reveal / graph attachment
└─ X2 two boxes / ActiveContext
```

每个 fixture 必须包含：`base graph + observation + innovation + affected/control/stop + operations + expected graph + counterfactual`。

产物：`tests/fixtures/<fixture_id>/`。验收：人不看实现也能判断输出是否正确；无未决语义。

### A3：做合同连通检查

检查 fixture 字段能否落入：

- `schemas/episode.schema.json`；
- `schemas/observation_graph.schema.json`；
- `schemas/belief_graph.schema.json`；
- `schemas/context_delta.schema.json`；
- `schemas/active_context.schema.json`。

产物：合同检查记录。验收：合法样例均可表达，非法 version/ID/operator/reference frame 有明确拒绝规则。

## A 阶段退出门

只有同时满足以下条件才进入 B：

- 六项人工语义已写入决策日志；
- 六个 P0 fixture 全部有正例、单因素反例和 control；
- X1/X2 明确标为边界测试，不冒充核心 revision 证据；
- `unknown/absent/occluded/out_of_fov/removed` 不混用；
- graph expansion、belief revision、ActiveContext 使用不同写入路径；
- 所有计划仍明确标注为“未实现/未验证”。

## 接下来做什么

```text
A 合同冻结
  ↓ pass
B 实现 schema + versioned executor + evaluator
  ↓ pass
C 运行 oracle mechanism pilot
  ↓ core mechanism survives falsification
D 分阶段训练 innovation/scope/operator/stop
  ↓ validation success
E 感知接入、正式测试、论文和复现
```

每阶段的具体合同：

- A：[`docs/01_research_contract.md`](docs/01_research_contract.md) 与 [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md)；
- B/C：[`docs/03_pilot_protocol.md`](docs/03_pilot_protocol.md)；
- D：[`docs/04_training_plan.md`](docs/04_training_plan.md)；
- E：[`docs/05_formal_evaluation_and_paper.md`](docs/05_formal_evaluation_and_paper.md)。

## 禁止跳级

- oracle executor 不能 exact match：修合同/执行器，不训练；
- oracle affected scope 不优于 local-slot：重审关系传播是否必要；
- oracle scope 不优于 full-graph 的无关保持/成本：收缩局部修订主张；
- validation 失败：不看 test 调参；
- 正式 test 后改协议：建立新 protocol version，保留旧结果。

## 每次工作结束只更新三处

1. 本页的“当前阶段/当前任务”；
2. `docs/DECISIONS.md` 中真正改变合同的决策；
3. 对应阶段文档中的验收状态。

不要再新建平行蓝图、个人清单或第二套实验合同。
