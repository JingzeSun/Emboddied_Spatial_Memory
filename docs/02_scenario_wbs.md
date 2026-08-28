# 02 — 场景 WBS：从概念到机器 Fixture

> 状态：`current design work / fixtures not yet implemented`

本文只做一件事：把论文概念拆成能输入、执行、判分的最小场景。

## 1. 分解规则

```text
Claim（要证明什么）
  → Use Case（在哪类现实问题中发生）
  → Scenario（哪个因素组合）
  → Fixture（精确旧图、观测和期望图）
  → Test（怎样自动判分）
```

每个 fixture 必须只改变一个关键因素，并与一个反事实 fixture 成对出现。

## 2. 当前 WBS

| ID | 优先级 | 场景 | 唯一关键证据 | 正确结果 | 主要检验 |
|---|---|---|---|---|---|
| R1 | P0 | 椅子从 A 搬到可见 B | 同一 identity 在 B 可靠重现 | 关闭 A 版本，建立 B 版本 | revision/version |
| R2 | P0 | 推车和箱子移动 | support dependency | 必要关系随之更新，无关对象不变 | propagation/stop |
| R3 | P0 | 旧址可靠为空，去向未知 | 可见、无遮挡、可靠、多帧缺席 | 旧位置失效；新位置 unknown | absence semantics |
| R4 | P0 | 与 R3 相同但被遮挡 | occluder 存在 | 保留旧 belief，只更新 visibility | preservation |
| R5 | P0 | 人长期站在门口 | stationary duration | actor 仍是 actor；门 identity 不变 | ontology invariant |
| R6 | P0 | 远处无关灯具变化 | 无依赖路径 | 空/最小 delta，目标子图不变 | stop/control |
| X1 | P1 | 转弯后首次看到新区域 | 此前 never observed | 创建节点/边并连接 attachment | graph expansion |
| X2 | P1 | 先见箱 A，右转见箱 B，再说找箱子 | route/dialogue context | A/B 均保留；排序或澄清 | ActiveContext |

## 3. Fixture 目录和文件

```text
tests/fixtures/<fixture_id>/
├─ base_belief.json
├─ observation_graph.json
├─ oracle_delta.json
├─ expected_belief.json
├─ metadata.yaml
└─ README.md
```

`README.md` 必须用自然语言说明该 fixture 检验哪个 claim、唯一变化因素是什么、哪些结果会反驳合同。

## 4. Fixture 必填字段

```yaml
fixture_id: R2_cart_box_cascade
priority: P0
claim_ids: [affected_propagation, stop_boundary]
counterfactual_group_id: CF_dependency_01
inputs:
  base_belief_ref: base_belief.json
  observation_graph_ref: observation_graph.json
  pose_ref: embedded_or_external
oracle:
  innovation_mode: belief_revision
  affected_node_ids: []
  affected_edge_ids: []
  control_node_ids: []
  control_edge_ids: []
  propagation_stop_edge_ids: []
  ordered_operations: []
expected:
  belief_ref: expected_belief.json
  allowed_equivalence_class: null
falsifiers: []
provenance: {}
```

若存在多个最小正确 delta，填写 `allowed_equivalence_class`，按 target invariant 判分，不伪造唯一集合真值。

## 5. P0 Fixture 精确定义

### R1 — Chair relocation

```text
base: chair_1 located_in zone_A, valid at v0
observation: chair_1 reliably matched in zone_B
innovation: belief_revision/conflict
must change: chair location version
must preserve: chair identity, unrelated objects
expected: A closes; B opens; supersedes/provenance complete
counterfactual: category same but identity evidence says new chair → ADD, not SUPERSEDE
```

### R2 — Cart-box cascade

```text
base: cart_1 supports box_1; cart_1 in A; plant_1 in C
observation: cart_1 and box_1 reliably reappear in B
seed: cart_1 location conflict
affected: cart dynamic state and relationship-dependent consequences
preserve: supports(cart_1, box_1), plant_1 and all C relations
stop: every edge leaving the dependency subgraph without causal/constraint evidence
```

必须先由 D-016 决定 `box located_in` 是存储边还是由 support+geometry 派生；未决定前 R2 没有训练真值。

### R3 — Reliable absence, destination unknown

```text
base: chair_1 in A
observation: A reliably visible and empty; no chair match elsewhere
expected: invalidate old location; current location=unknown
forbidden: fabricate B; mark removed_from_scene without independent evidence
```

### R4 — Occlusion control

与 R3 共用旧图、物体和 pose，只增加可信 occluder/降低可见区域。正确输出必须从 `INVALIDATE` 变为 `PRESERVE + visibility_update`。

### R5 — Stationary person

```text
actor.motion: moving → stationary
actor.persistence: may increase
door.visibility: visible → occluded
actor ontology: unchanged
door identity/geometry: unchanged
```

### R6 — Irrelevant innovation

变化区域与目标子图没有人工许可的 dependency path。正确 affected set 为空或仅包含变化自身；不得沿 room contains 边扩散到所有对象。

## 6. P1 边界 Fixture

### X1 — Corner reveal

```text
past: region_B never observed
now: pose-aligned new surface/region appears after turn
output: created nodes/edges + attachment_node_ids
forbidden: close old valid facts merely because graph grew
```

### X2 — Two-box ActiveContext

```text
PersistentWorldMemory: box_A and box_B remain
SceneBelief: both identities, geometry and versions remain
ActiveContext: box_B gains route/discourse/current-place score
decision: select only if safe; otherwise ask clarification
```

世界图在 query 前后必须相同。

## 7. 六组单因素反事实

| Group | 只改变 | 应改变的正确操作 |
|---|---|---|
| CF-identity | same identity ↔ new instance | SUPERSEDE ↔ ADD |
| CF-visibility | reliably empty ↔ occluded | INVALIDATE ↔ PRESERVE |
| CF-dependency | support relation 有 ↔ 无 | propagate ↔ stop |
| CF-relevance | 有依赖路径 ↔ 无关 | affected ↔ control |
| CF-history | old hypothesis 有 ↔ never observed | revision ↔ expansion |
| CF-dialogue | route/dialogue history | ActiveContext ranking 变，world graph 不变 |

## 8. 人工确认门

下列内容不能由模型替研究者决定：

1. identity continuation；
2. relation storage/derivation；
3. operator-specific propagation matrix；
4. reliable absence evidence rubric；
5. stop equivalence/scoring；
6. clarification action cost。

这些决定写入 `DECISIONS.md`，数值阈值只能用 train/validation 冻结。

## 9. 完成标准

- R1–R6、X1–X2 均有完整六文件目录；
- 每个 P0 有正例、反例、control；
- schema 能表达所有字段；
- 任意研究者只看 fixture 就能写出期望 invariant；
- 自动映射、VLM/LLM 评审没有被称为 ground truth。

通过后进入 [`03_pilot_protocol.md`](03_pilot_protocol.md)。
