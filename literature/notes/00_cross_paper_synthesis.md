# 文献综合：从 Memory Construction 到 Scoped Belief Revision

> 方向版本：D-008 accepted
> 更新日期：2026-08-28
> 旧综合：`../../docs/archive/pre_d008/literature/00_cross_paper_synthesis.md`

## 1. 新的阅读问题

现在不再只问论文“怎样保存空间记忆”，而要逐篇回答：

1. 新观测到来时，旧状态如何被投影或检索？
2. 差异是像素/feature residual，还是 entity/relation/visibility 级 innovation？
3. 更新单位是 frame、token、voxel、object slot 还是 graph substructure？
4. 方法是否显式决定 affected scope？
5. 关系影响是否传播，在哪里停止？
6. 是否保留历史版本和 evidence？
7. 是否同时评测必要更新与无关保持？
8. 每帧是否隐式重算完整历史？

## 2. 已有路线给出的答案

| 路线 | 代表工作 | 已回答 | 对本项目仍留下的问题 |
|---|---|---|---|
| 增量空间构建 | ConceptGraphs、g3D-LF、MTU3D、3D-Mem | posed observation 如何聚合到 3D/对象/快照 | 冲突 evidence 如何形成 typed revision |
| 跨视角 2D/3D 感知 | ODIN | depth/pose 如何将多视图 token 放入共享 3D 坐标并通过 kNN attention 获得实例一致性 | 当前 forward 的局部读取如何变成跨时、版本化、可停止的 belief write |
| 分层场景图 | Hydra、HOV-SG、HSGM | object/place/room 等结构如何组织 | 哪些层和关系应因局部新证据被修改 |
| 动态图/长期协调 | Scene Graph Memory、Khronos | 动态对象、fast/slow state、fragment reconciliation | operator scope 与无关保持没有统一监督 |
| 持久对象状态 | KARMA、Embodied VideoAgent | 对象 identity、state 和短长期记忆 | relation-level propagation 与 stop boundary |
| 选择性读取 | 3DLLM-Mem | task/current token 如何 attention 到相关历史 | 读取相关不等于写入时修改范围正确 |
| latent dynamics | DINO-WM、Persistent Embodied World Models | action-conditioned future representation | 不直接维护可追溯 belief delta |
| 变化场景预警 | SpatialMem、SpaMEM、ChangingGrounding、ViSAGE、R4DSG | metric anchors、belief evolution、历史纠正、changing-scene task | 必须用更窄、可评测的 scope/operator/stop claim 区分 |

## 3. 当前研究空白

已有工作足以否定宽泛主张：

- 结构化/层次空间记忆不是空白；
- 动态对象记忆不是空白；
- 新证据更新历史不是空白；
- selective attention/read 不是空白；
- long/short-term memory 不是空白。

当前可检验空白是：

> 新旧 spatial belief 的 pose-aware structured innovation 如何成为局部图编辑的监督信号，以及如何显式预测必要关系传播和停止边界，同时保持 control subgraph 不变？

这个空白只有在以下条件同时成立时才有说服力：

- 方法输出 typed ContextDelta；
- baseline 包含 local-slot 与 full recomputation；
- 数据提供 affected/control/stop oracle；
- 指标同时惩罚漏改和多改；
- stationary actor、relocation、absence、occlusion、turning 使用同一机制。

## 4. 与最接近基石的差异

### ODIN

ODIN 已证明 posed RGB-D token 在 2D within-view 与 3D cross-view 层之间交替融合能显著改善跨视角 instance consistency；其 3D kNN attention 是局部读取机制。它没有旧 belief projection、typed innovation、持久版本、关系编辑或 stop supervision，且测试通常对所选全部视图重新前向。因此我们不能以“新帧进入共享 3D 语境”或“局部 3D attention”为贡献，只能以 `innovation → affected write scope → operator/stop → versioned apply` 区分。

ODIN 还要求主实验固定 perception front-end：否则更好的分割会同时提高 association 和下游 query，无法归因于 revision controller。它更适合做可替换前端和 `recent-N joint reparse` 诊断对照，而不是直接的 graph-revision baseline。

### Hydra

Hydra 已做在线分层图构建和全局纠正。我们的差异不能是“图可以纠正”，而要落在每个新观测触发的 structured innovation、局部 scope 和 stop supervision。

### Khronos

Khronos 已统一短期动态与长期变化。我们的差异不能是“快慢记忆”，而是认知 belief graph 上 typed relation edits、control-subgraph preservation 和 context query。

### Embodied VideoAgent

它已做持久对象 identity/state update。我们的差异是从 object update 扩展到显式 affected relation subgraph，并评测传播完整性和连带修改。

### 3DLLM-Mem

它说明 task-conditioned selective reading 已存在。我们的核心必须是 selective revision，不能只换成 sparse attention。

### Scene Graph Memory

它已学习环境特定动态规律。我们的任务不是预测对象通常在哪，而是根据当前可见性与位姿 evidence 修订具体 belief versions。

## 5. 预印本风险如何影响设计

- SpatialMem 迫使我们放弃“metric anchor/hierarchy”作为主 claim；
- SpaMEM 迫使我们提供具体 operator、scope 和 stop，而不是只说 dynamic belief evolution；
- ViSAGE 迫使我们放弃“历史可自我纠正”这一宽泛 claim；
- R4DSG 迫使我们放弃“stable anchor + dynamic object transition”作为主 claim；
- ChangingGrounding 迫使我们区分 belief revision 与 memory-guided active grounding。

它们当前仍是 novelty watch，不支撑正式事实结论。

## 6. 论文的四组 Related Work

1. Pose-aligned spatial memory construction；
2. Persistent and dynamic scene memory；
3. Selective context and historical correction；
4. Changing-scene tasks and evaluation。

每一组末尾都回答同一问题：它是否显式预测 graph edit scope、relation propagation 和 stop boundary？

## 7. 必须复现的机制型基线

不以“复现所有大系统”为目标，先覆盖机制：

1. append-only；
2. pose-warped global EMA；
3. slot lifecycle；
4. local matched-slot revision；
5. full graph recomputation；
6. recent-N joint reparse（ODIN-style perception control；不将其误称为 persistent revision）；
7. oracle affected-subgraph；
8. deterministic predicted scope。

公开方法作为横向外部比较；机制型基线承担核心因果消融。

## 8. 当前论文贡献上限

若 E1、E2、E5 和 E7 全部成立，可以主张：

- pose-aware structured innovation；
- learned affected scope/operator/stop；
- necessary propagation + unrelated preservation evaluation；
- sparse versioned revision with lower cost than full recomputation。

若只证明 E3/E4，则更像 factorized dynamic-state engineering；若只降低 contamination，则回到旧问题；若只提高 query，则无法证明 revision scope。

## 9. 下一轮精读优先级

ODIN 已于 2026-08-28 完成精读；它被降位为 cross-view perception substrate/diagnostic baseline，而不是 revision novelty threat。

1. Hydra：跨层 correction 的实际触发和优化范围；
2. Khronos：fragment reconciliation 的 scope 与长期 commit；
3. Embodied VideoAgent：object-state update 与 relation handling；
4. 3DLLM-Mem：selective attention 计算范围；
5. Scene Graph Memory：transition supervision；
6. SpatialMem/SpaMEM/ViSAGE/R4DSG：仅做 novelty-difference table，并持续核验同行评审状态。

每篇新笔记都使用 `TEMPLATE.md`，增加 `edit scope / propagation / stop / preservation metric` 四项。
