# Structured Innovation 与 Affected-Subgraph Revision

> 状态：accepted algorithm contract；尚未实现或验证
> 上位蓝图：`09_integrated_direction_plan.md`
> 机器输出：`schemas/context_delta.schema.json`

## 1. 算法目标

输入 base belief (B_{t-1})、当前 ObservationGraph (O_t)、pose/action 与 task，输出：

- structured innovations；
- affected node/edge；
- propagation stop edge；
- typed operations；
- versioned SceneBelief；
- ActiveContext。

算法不得默认扫描和重新编码全部历史 memory。

## 2. Structured Innovation 类型

| 类型 | 最低证据 | 默认行为 |
|---|---|---|
| `matched` | geometry/identity/visibility 一致 | REINFORCE 或小幅 UPDATE_STATE |
| `new` | observation 无可信旧匹配 | ADD candidate |
| `occluded` | 预计可见但有可信 occluder | PRESERVE + occlusion edge |
| `out_of_fov` | 投影不在有效视野 | PRESERVE |
| `reliably_absent` | 应可见、无遮挡、传感器可靠、多证据缺席 | INVALIDATE/SUPERSEDE candidate |
| `conflict` | identity/geometry/relation 不兼容 | QUARANTINE 或候选 revision |
| `ambiguous` | 多匹配/多因果解释接近 | 保留多假设 |
| `sensor_inconsistent` | pose/depth/perception 自相矛盾 | QUARANTINE |

一个 frame 可以同时包含多种 innovation。

## 3. 创新特征

每个 innovation 至少包含：

[
delta_i=[
delta_{	ext{geometry}},
delta_{	ext{identity}},
delta_{	ext{visibility}},
delta_{	ext{motion}},
delta_{	ext{relation}},
C_{	ext{pose}},
C_{	ext{measurement}},
C_{	ext{association}}]
]

所有 `delta` 都以 projected old belief 为参照，不能把 camera-coordinate 差异直接称为 world change。

## 4. 因果解释分数

```text
causal_scores = {
  viewpoint_change,
  occlusion,
  actor_motion,
  object_relocation,
  object_removal,
  identity_revision,
  relation_change,
  sensor_error,
  unknown
}
```

因果头用于控制候选 operator 和传播类型，不要求在 MVP 声称强因果发现。论文中应称 `causal explanation scores` 或 `structured explanation`，除非另有因果识别实验。

## 5. Scope 图

Retriever 不在完整 belief 上盲目 attention，而在候选依赖图上运行：

1. 由 frustum、Chart/Place 和空间索引检索 projected candidates；
2. innovation 关联节点作为 seed；
3. 沿 operator-relevant typed edges 扩展；
4. 对 candidate nodes/edges 预测 include/exclude；
5. 对边预测 propagate/stop；
6. 输出 affected set、control set 与置信度。

Control set 必须包含：

- affected seed 的近邻但无必要修改节点；
- 同 Place 的无关节点；
- 其他 Place/Chart 的远处节点；
- 历史旧版本。

## 6. Operator-specific propagation

### Relocation

```text
chair(old location)
  -> old located_in edge
  -> support/near relations tied to old location
  STOP at unrelated object and stable Place topology
```

### Occlusion

```text
actor -> occludes -> door
door visibility version changes
door identity/geometry/location preserved
STOP before unrelated door relations
```

### Reliable absence

```text
old location edge invalidated
location becomes unknown unless new evidence exists
historical version preserved
STOP before inventing destination
```

### Identity correction

```text
candidate entity versions may merge/relink
dependent event participation may update
STOP at relations unsupported by identity evidence
```

## 7. Revision invariants

所有 delta 应通过：

1. affected/control 不重叠；
2. operation target 存在或为合法 ADD；
3. `before` 与 base version 一致；
4. version chain 无环；
5. `valid_from <= valid_to`；
6. INVALIDATE 不删除 evidence；
7. unknown 不带虚构 geometry；
8. actor ontology 不被 motion duration 改写；
9. PRESERVE 不更新被遮挡结构 latent；
10. stop edge 属于 base graph 且未被越界传播。

不变量失败时整个 delta 进入 quarantine，不做部分静默提交。

## 8. 确定性执行器

```text
function ApplyDelta(base_graph, delta):
    validate_schema(delta)
    validate_base_version(base_graph, delta)
    validate_scope_and_control(delta)
    staged_graph = copy_on_write(base_graph)
    for op in topological_order(delta.operations):
        apply_typed_operator(staged_graph, op)
    validate_graph_invariants(staged_graph)
    validate_control_unchanged(base_graph, staged_graph, delta)
    commit_new_version(staged_graph, delta.provenance)
    return staged_graph
```

copy-on-write 表示逻辑版本，不要求复制所有 tensor。实现可使用 persistent data structure、transaction log 或稀疏 delta overlay。

## 9. Oracle 与学习目标

### Oracle scope

由人工审核的 ContextDelta 直接给 affected/control/stop/operator。用于：

- E0 executor test；
- 方法上限；
- 检查问题定义是否值得；
- 分离 perception、scope 和 executor 错误。

### Deterministic scope

规则基于 innovation type、visibility 和 typed dependencies。它是必须报告的解释性 baseline。

### Learned scope

图模型输出：

- node include probability；
- edge include probability；
- propagation/stop probability；
- operator distribution；
- delta confidence。

训练同时监督正 affected、难负 control 和 stop boundary，不能只监督 change nodes。

## 10. Loss

[
mathcal L =
mathcal L_{	ext{innovation}}
+lambda_nmathcal L_{	ext{node-scope}}
+lambda_emathcal L_{	ext{edge-scope}}
+lambda_bmathcal L_{	ext{boundary}}
+lambda_omathcal L_{	ext{operator}}
+lambda_pmathcal L_{	ext{preserve}}
+lambda_cmathcal L_{	ext{calibration}}
+lambda_rmathcal L_{	ext{revision-cost}}
]

Hard negatives 必须包含与 seed 相邻但不应修改的节点/边。

## 11. Attention 的位置

当前 Transformer 不需要每来一帧就把全部历史 token 重新形成完全图。这里将 attention 限制在：

1. pose/frustum/Chart 检索出的候选；
2. innovation seed 邻域；
3. operator-relevant dependency edges。

可比较：

- dense full-graph attention；
- retrieved subgraph attention；
- message passing GNN；
- hybrid sparse graph Transformer。

核心 claim 不是“用了 sparse attention”，而是 retrieval/scope 有明确 revision semantics 和 stop-boundary supervision。

## 12. 输出审计

每次 revision 日志保存：

```text
base_version
observation_ref
projected_candidate_ids
innovation records
causal scores
affected/control/stop ids
operator logits and chosen operators
invariant results
committed version
latency and memory cost
```

失败日志与成功日志采用相同 schema。

## 13. 第一实现优先级

1. schema-backed dataclasses；
2. deterministic versioned executor；
3. oracle fixtures；
4. delta/preservation/propagation metrics；
5. expected-observation projection；
6. deterministic structured innovation；
7. deterministic scope；
8. learned controller。

在 1–4 未通过前，不训练模型。
