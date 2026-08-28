# 场景 WBS 与 Micro-fixture 合同

> 状态：`accepted for pilot design / pre-implementation / not validated`
>
> 合同版本：v1.1；决策依据：D-008、D-013、D-014。

## 目的

本文把 `09` 的论文蓝图拆成可实施、可标注、可判分的场景工作包。它不是实验结果，也不预设方法会成功。

一条合格的 fixture 必须能写成：

```text
base SceneBelief
  + current pose / visibility
  + ObservationGraph
  → typed innovation
  → affected / control / stop
  → ordered operators
  → expected target SceneBelief
  → metrics and falsifiers
```

## WBS 结构

### WBS 1：核心 revision claim（P0）

- `UC-R1 可见搬迁`
  - `SC-R1A 单对象位置变化`
    - `FX-R1A-chair-relocation`
  - `SC-R1B 依赖关系级联`
    - `FX-R1B-cart-box-cascade`
- `UC-R2 可靠缺席`
  - `SC-R2A 旧址可靠可见且为空`
    - `FX-R2A-chair-absent-unknown`
  - `SC-R2B 相同几何但被遮挡`
    - `FX-R2B-chair-occluded-control`
- `UC-R3 身份保持`
  - `SC-R3A 长期静止角色`
    - `FX-R3A-stationary-person`
- `UC-R4 无关保持与停止`
  - `SC-R4A 无关远端变化`
    - `FX-R4A-irrelevant-lamp`

### WBS 2：必要支撑能力（P1）

- `UC-X1 图增长`
  - `SC-X1A 转弯后首次显露`
    - `FX-X1A-corner-reveal-attachment`
- `UC-X2 同类实例指代`
  - `SC-X2A 路线与对话改变当前候选`
    - `FX-X2A-two-box-active-context`

WBS 2 支持完整系统叙事，但在当前论文中不与 P0 revision claim 争夺主贡献位置。

## WBS dictionary

| ID | 研究目的 | 关键输入差异 | 期望产物 | 依赖 | 验收条件 |
|---|---|---|---|---|---|
| FX-R1A | 检查位置版本化修订 | 同一 identity 在新位置可靠重现 | close old location + open new state | association oracle | 不并存两个 committed 当前位置；历史可追溯 |
| FX-R1B | 检查必要传播与停止 | 支撑物移动，被支撑物关系依赖 | affected edges + stop edges + delta | 关系语义确认 | 必要边全改、无关边全保留 |
| FX-R2A | 区分未知去向与新位置 | 旧址可靠可见为空，无新匹配 | invalidate old location, set unknown | reliable-absence oracle | 不编造目的地，不误判遮挡 |
| FX-R2B | 保护遮挡状态 | 与 R2A 只差 occluder/visibility | preserve entity/location, update visibility | visibility oracle | 不产生 removal/relocation |
| FX-R3A | 防止静态化污染 | 人长期不动但仍是 agent | preserve semantic identity | identity oracle | 不变成 fixture/structure |
| FX-R4A | 检查 stop boundary | 变化与目标子图无依赖 | empty/minimal revision | graph dependencies | collateral edits 为零 |
| FX-X1A | 检查新子图连接 | 新区域此前未观测 | create nodes/edges + attachment | pose/chart alignment | attachment 正确，不关闭旧有效事实 |
| FX-X2A | 检查语境指代 | 两个木箱、右转事件、含糊 query | ranked candidates/clarification | dialogue/route annotations | 两实例均保留，排序可解释 |

## Fixture 通用字段

每个机器可读 fixture 至少包含：

```yaml
fixture_id: string
claim_ids: [string]
base_graph_ref: string
observation_graph_ref: string
pose_ref: string
oracle:
  innovation_mode: string
  affected_node_ids: []
  affected_edge_ids: []
  control_node_ids: []
  control_edge_ids: []
  propagation_stop_edge_ids: []
  ordered_operations: []
expected_graph_ref: string
counterfactual_group_id: string
allowed_equivalence_class: null
falsifiers: []
provenance: {}
```

如果允许多种最小正确修订，不能强迫单一集合真值；应提供 `allowed_equivalence_class` 或按结果不变量评分。

## 完整示例：推车—箱子关系级联

### Base graph v0

```text
room_1 contains cart_1
cart_1 supports box_1
cart_1 located_in zone_A
box_1 located_in zone_A          # 若此边是由 support+geometry 派生，应标 derivation
plant_1 located_in zone_C        # control
```

### 新观测

在可靠 pose 下，`cart_1` 与 `box_1` 在 `zone_B` 重现，身份匹配可信；`plant_1` 未发生相关变化。

### Oracle innovation

```text
mode: belief_revision
category: conflict
seed: cart_1.location zone_A → zone_B
evidence: current RGB-D + pose + association
```

### 必须人工冻结的两种语义

方案 A：`box_1 located_in zone_A` 是持久存储边。则它属于 affected edge，必须被关闭并建立 zone_B 新版本。

方案 B：该边由 `supports + cart pose + box pose` 派生。则 delta 不直接编辑它，但 target graph 查询结果必须随几何重算为 zone_B。

在确定 A/B 前，这个 fixture 没有唯一 ground truth，不能开始监督训练。

### 预期 scope

```text
affected nodes: cart_1, box_1（仅其动态状态组件）
affected edges: cart_1-located_in-zone_A, 必要时 box_1-located_in-zone_A
preserved edge: cart_1-supports-box_1
control nodes/edges: plant_1 及其位置关系
stop: 所有从当前依赖子图通向 room 其他对象、且无因果/几何依赖的边
```

### 预期操作

1. 关闭 `cart_1 @ zone_A` 的有效区间；
2. 打开 `cart_1 @ zone_B` 新版本；
3. 保留 `supports(cart_1, box_1)`；
4. 按冻结语义更新或派生 `box_1` 的位置；
5. 写入 provenance 和 `supersedes`；
6. 不修改 `plant_1`。

### 反例与 control

- 只观测到 cart，box 被遮挡：不应在无依据时断言 box 同步移动；
- cart 的 association 低置信：进入多假设/quarantine，不应立即覆盖；
- 新观测只是 camera motion：不得产生 world relocation；
- zone_C 的灯亮灭：不得沿 `contains(room_1, *)` 传播到 cart 子图。

### 判分

- target graph invariant；
- required propagation recall；
- preservation accuracy；
- collateral revision rate；
- stop-edge accuracy；
- version/provenance validity；
- edited-node ratio 和 executor latency。

## Counterfactual 设计

每组反事实只改变一个决定正确操作的因素：

| 组 | 固定 | 唯一改变 | 正确结果差异 |
|---|---|---|---|
| CF-visibility | 旧图、物体、pose、旧址 | occluded ↔ reliably visible empty | preserve ↔ invalidate old location |
| CF-identity | 几何和类别 | same identity ↔ new instance | supersede ↔ create new node |
| CF-dependency | 同一移动 | support edge 存在 ↔ 不存在 | propagation ↔ stop |
| CF-relevance | 同一创新大小 | 路径连到目标 ↔ 无关区域 | affected scope ↔ control only |
| CF-expansion | 同一新观测 | old hypothesis exists ↔ never observed | revision ↔ graph expansion |
| CF-dialogue | 两箱和世界图 | route/discourse history | ActiveContext ranking 变化，world graph 不变 |

## Pilot 实验矩阵

| 实验 | Fixtures | 基线 | 核心观测 | Go/No-Go |
|---|---|---|---|---|
| E0 合同连通 | 全部 | 无 | schema、版本、provenance | 100% 可解析和执行 |
| E1 单点修订 | R1A/R2A/R2B | append-only、local-slot | relocation/absence/occlusion 可分 | exact invariant 全通过 |
| E2 范围与传播 | R1B/R4A | local-slot、full-graph | 必要传播 + 无关保持 | oracle 显著支配两端基线 |
| E3 反事实 | 全 CF 组 | invariant-blind rule | 单因素变化导致正确 operator 变化 | 无标签矛盾 |
| E4 图增长 | X1A | append-only object map | attachment，不误 revision | attachment P/R 达门槛 |
| E5 指代读取 | X2A | recency-only、FARM-style | top-K、澄清、世界保持 | candidate 与 preservation 同时满足 |

门槛数值在 validation fixtures 上冻结，不能根据正式 test 结果回填。

## 从 fixture 到工程工作包

```text
WP-01 schema validation
WP-02 immutable/versioned graph store
WP-03 deterministic ContextDelta executor
WP-04 oracle fixture loader
WP-05 graph invariant and exact-match evaluator
WP-06 deterministic innovation/scope/operator baseline
WP-07 learned innovation model
WP-08 learned scope/operator model
WP-09 perception adapter
WP-10 experiment runner and artifact exporter
```

依赖顺序：`01 → 02 → 03 → 04/05 → 06 → 07/08 → 09 → 10`。在 WP-01–05 未通过前，不启动训练工作包。

## 训练分解

### 数据单位

```text
(base_graph, observation_graph, pose, visibility, history)
    → innovation label
    → affected/control/stop labels
    → operator sequence or equivalent target invariant
    → target_graph
```

### 模型职责

1. innovation head：分类 `reinforcement / expansion / revision / visibility / ambiguity / sensor inconsistency`；
2. scope head：节点/边多标签选择；
3. operator head：预测 typed operation 和参数；
4. stop head：边级传播停止；
5. confidence/calibration head：决定 commit、quarantine 或 ask clarification；
6. deterministic executor：验证并执行，不允许自由文本直接改图。

### 场景课程

```text
单对象 relocation
  → absence vs occlusion
  → 单跳关系传播
  → 多跳但有停止边界
  → association ambiguity
  → 长序列多版本
  → graph expansion 与 ActiveContext 混合事件
```

训练时保留场景家族级切分；同一 base scene 的渲染变体、时间相邻片段和反事实对子不得跨 split。

## 人工确认清单

在写第一批机器 fixture 前，负责人必须确认：

1. **identity**：搬迁是否默认同一实体；何时允许 split/merge hypothesis？
2. **relation derivation**：`near/located_in/above` 哪些存储、哪些由几何派生？
3. **propagation semantics**：`supports/contains/attached_to` 中哪些具有方向性依赖？
4. **reliable absence**：最低可见面积、遮挡比例、连续帧数和传感器可靠性如何判？
5. **stop truth**：是标唯一边集，还是接受多个满足不变量的最小 cut？
6. **clarification cost**：何种行动风险或候选差距触发询问？

这些答案记录进 `docs/06_decision_log.md`，且只能用 train/validation 数据冻结。

## 与现有文件的职责边界

- `START_HERE.md`：阶段顺序和门禁；
- `09_integrated_direction_plan.md`：论文级方向与贡献；
- 本文：场景/WBS/fixture 的单一执行合同；
- `03_experiment_contract.md`：正式实验、指标和统计协议；
- `04_dataset_spec.md`：数据来源、切分、标注和质控；
- `10_implementation_roadmap.md`：把 WP 排进实现里程碑；
- `CHECKLIST.md`：当前一页任务，不重复原理。
