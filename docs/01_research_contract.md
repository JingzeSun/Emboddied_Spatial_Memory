# 01 — 研究合同：问题、概念与论文边界

> 状态：`accepted research contract / not implemented / not validated`

本文只回答五件事：研究什么、为什么不是旧问题、核心概念是什么、论文能主张什么、怎样被反驳。

## 1. 研究问题

> 当当前观测与已有空间信念发生结构化差异时，智能体如何结合 pose、visibility 和 identity evidence，只修订真正受影响的节点与关系，完成必要传播，并在无关边界停止？

## 2. 现有工作的缺口

现有工作已经覆盖：

- posed RGB-D 的在线对象/场景图构建；
- 动态对象、长短期记忆和持久对象状态；
- selective attention/read；
- 关系谓词查询、同类候选 soft ranking 和 top-K；
- 全局或片段级场景协调。

它们不等于本项目要检验的四个问题：

1. 新证据应触发什么 typed world edit？
2. 哪些旧关系必须随状态改变而更新？
3. 哪些无关旧事实必须保持？
4. 传播依据什么停止，旧版本如何追溯？

FARM 已覆盖 online object memory、relational retrieval 和 top-K，当前仅作 preprint novelty watch/基线；不能把这些能力包装成本项目创新。正式文献边界见 `literature/peer_review_audit.md` 和 `literature/notes/farm_2026_DEEP.md`。

## 3. 核心方法

**Pose-Aware Structured Innovation + Affected-Subgraph Revision**

```text
current frame/depth/pose
        ↓
ObservationGraph
        +
ProjectExpectedObservation(SceneBelief, pose)
        ↓
Structured Innovation
        ↓
affected seed → allowed dependency propagation → stop boundary
        ↓
typed ContextDelta
        ↓
deterministic versioned executor
        ↓
new SceneBelief version
```

### 3.1 Structured Innovation

同时输出 observation evidence category 和状态路径：

- evidence：`matched/new/occluded/reliably_absent/conflict/ambiguous/sensor_inconsistent`；
- mode：`reinforcement/graph_expansion/belief_revision/visibility_update/association_ambiguity/sensor_inconsistency`。

“看到新东西”不自动等于“纠正旧世界”。

### 3.2 Affected-Subgraph Revision

控制器输出：

- affected nodes/edges；
- control nodes/edges；
- typed operators；
- propagation stop edges；
- confidence、evidence 和 provenance。

executor 只执行合法 typed delta，不允许 LLM 自由文本直接改图。

## 4. 四个核心概念

| 概念 | 操作性定义 | 核心指标 | 不解决什么 |
|---|---|---|---|
| 动态冲突修订 | 可靠新证据反驳旧状态时产生 typed delta | target graph correctness | 静态对象检索 |
| 版本链 | 保存 valid interval、supersedes 和 evidence | version/provenance validity | top-K 历史 |
| 受影响关系传播 | 沿许可依赖完成必要后果 | required propagation recall | attention 读取范围 |
| 停止边界 | 显式限制无依据传播 | collateral revision/control preservation | token 数量压缩 |

## 5. 四层状态

| 状态 | 只负责 | 禁止 |
|---|---|---|
| ObservationGraph | 当前帧及 camera-relative evidence | 充当长期事实 |
| SceneBelief | 当前多假设、版本化世界信念 | 无证据原地覆盖历史 |
| ActiveContext | 任务/路线/对话下的候选读取视图 | 删除未选世界实例 |
| PersistentWorldMemory | 已巩固的长期版本 | 接收未验证 top-1 猜测 |

graph expansion 写入新 candidate 和 attachment；belief revision 关闭/替换旧版本；ActiveContext 只改变候选排序。

## 6. 论文范围

### P0 核心

- relocation；
- reliable absence with unknown destination；
- occlusion/out-of-FOV preservation；
- operator-specific relation propagation；
- irrelevant innovation 与 stop boundary；
- versioned deterministic execution。

### P1 边界/扩展

- corner reveal 的 graph attachment；
- two-box route/dialogue ActiveContext；
- FARM-style mapper/retrieval interface。

P1 可以验证系统边界，但不与 P0 并列为主贡献。

### 暂不做

- 完整导航闭环；
- learned Chart/Place split/merge；
- 跨人的生物身份 re-ID；
- RGB reconstruction；
- 无约束图编辑；
- 以更大 backbone 代替机制验证。

## 7. 可检验主张

| Claim | 必须比较 | 支持证据 | 直接反证 |
|---|---|---|---|
| structured innovation 比标量变化分数更可修订 | scalar residual | 事件分型与校准 | 无稳定提升或标签不可区分 |
| affected scope 完成必要关系后果 | local matched-slot | propagation recall | 与 local-slot 无差异 |
| stop boundary 保护无关事实 | full graph | collateral/control preservation | 无关修改不下降 |
| versioning 正确表达动态状态 | in-place overwrite | relocation/absence/occlusion invariant | 历史不可追溯或语义混淆 |
| 局部修订有实际成本价值 | full recomputation | latency/memory/edit ratio | 全图同样便宜稳定 |

任何失败 claim 都必须删除、降级或重新定义；不能只换模型继续保留原结论。

## 8. 几何与关系不变量

- pose 使用 `T_world_camera`，变换方向必须显式；
- camera motion 与 world change 分开；
- Vanishing Point 是观测线索，不是长期坐标；
- Chart/Place 是稳定检索与传播边界；
- 方向关系必须有 reference frame；camera-relative left/right 默认不持久化；
- `unknown` 不得变成虚构位置；
- 静止时长不改变 actor ontology。

下一步只读 [`02_scenario_wbs.md`](02_scenario_wbs.md)。
