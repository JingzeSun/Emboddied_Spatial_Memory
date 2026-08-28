# FARM 精读：关系空间记忆已经覆盖了什么

> 论文：**FARM: Find Anything using Relational Spatial Memory**
> 作者单位：UC Berkeley、Stanford University
> 版本：arXiv:2606.15476v3，2026-07-26
> 精读日期：2026-08-28
> 同行评审状态：`preprint_only / novelty_watch_only`
> 本地 PDF：`papers_detail/2606.15476v3.pdf`（Git 忽略）
> SHA256：`1E510FF937A97862AA10A2B9A6CB50CC1DD674F6AA88BBC4E5D0CD50D3998A27`

## 核验结论

导师推荐的 Berkeley/Stanford 工作是 FARM，不是 ODIN。截至精读日，可核验来源只有：

- [arXiv v3](https://arxiv.org/abs/2606.15476)；
- [作者项目页](https://goldengait.github.io/farm/)；
- [官方代码仓库](https://github.com/GoldenGait/FARM-Project)；
- [DBLP CoRR 条目](https://dblp.org/rec/journals/corr/abs-2606.15476.html)，类型为 informal/other publication。

没有找到官方 proceedings、出版社或正式接收页。因此按 D-009，它可以迫使我们收紧创新、设计 baseline，但不能作为论文 Related Work 的同行评审事实基石。投稿前必须重查状态。

## 一句话答案

FARM 已经把“根据显式空间关系从大量同类对象中找到目标”做得很直接；它没有解决“新帧反证旧世界状态时，应改哪些旧节点和关系、传播到哪里、在哪里停止”，也没有定义“对话和路线使某个同类实例暂时更显著，但其他实例仍保留”的跨轮意图状态。

## 问题与表示

FARM 同时研究两个任务：

1. 从 posed RGB-D 流在线构建紧凑、开放词汇的对象级记忆；
2. 把自然语言指代表达编译成目标、锚点与关系谓词，再从记忆中返回目标实例排名。

每个 entity 保存：

- 单个 3D Gaussian，表示位置和范围；
- 用于跨视角 association 的 detection-time appearance feature；
- 最多 `k` 个有视角多样性的代表 crop 及其 camera pose；
- VLM caption；
- caption-text、SigLIP2 image、Qwen3-VL image 三类 retrieval embedding；
- covisibility 与基于 Gaussian Hellinger distance 的 adjacency。

论文明确不在 mapping 阶段穷举 containment、left-of、between 等高阶关系；任务需要的关系在 query time 从对象几何和保存视图中计算。

## 新帧怎样进入 FARM 记忆

同步关键路径是：

```text
detect masks
  → depth/pose lift to one Gaussian per detection
  → feature/class prefilter
  → Hellinger-distance neighbor search
  → union-find correspondence
  → sufficient-statistics fuse or initialize entity
  → representative-view selection
  → covisibility/adjacency update
```

caption 和三类 retrieval embedding 异步回写，不阻塞 mapping。

这对我们的启发与限制同样明确：

- unmatched detection 会初始化新 entity，FARM 确实支持对象图增长；
- detection 若同时连接多个旧 entity，union-find 会合并它们，loser 的关系、caption、view 和 identity history 被 winner 吸收；
- Gaussian 与 appearance 用累积统计融合，属于 construction/association 更新；
- 论文没有为 relocation、reliably absent、occluded、unknown location、removed-from-scene 定义 typed conflict/revision protocol；
- 没有 affected/control/stop、有效区间、supersedes 或可撤销多假设执行器；
- 前端还会过滤 wall/floor 等“uninformative”类别，所以它并不表示我们所需的 surface/region/Chart 结构补全。

因此，拐角后看到新建筑面/区域这一例子不能再只写成“首次增量发现对象”。我们的合同必须区分：

- `graph_expansion`：过去未知、现在首次观测，新增 node/edge 并连接旧 attachment boundary；
- `belief_revision`：已有旧假设被可靠新 evidence 反证，需要关闭、重连或 supersede；
- `visibility_update`：只是遮挡、视野外或重新可见；
- `association_ambiguity`：暂时不能决定是旧实体延续还是新实体。

## 关系检索到底做了什么

FARM 用 Qwen3.5-9B 把 query 编译为 typed QueryGraph。固定谓词表包含 16 类：

```text
Near, On, Above, Below, NextTo, Between,
Inside, InRegion, LeftOf, RightOf, InFrontOf, Behind,
Closest, Farthest, HasAttribute, IsCategory
```

流程为：

1. 可选 region scoping；
2. 多 embedding reciprocal-rank fusion 给全部 active entities 排 semantic candidate；
3. 用对象 Gaussian 或保存视图计算 soft predicate；
4. 对 star-shaped target-anchor query 贪心绑定每个 anchor；
5. 用 semantic score 与关系几何平均加权，保留候选而不是 hard delete；
6. 用 projected-view VLM 对 top-5 重排；
7. 返回 target、总分、每个 predicate 分数和绑定 anchor。

`LeftOf/RightOf/InFrontOf/Behind` 不是无参考系的世界事实：论文在目标对象保存的 camera views 中计算 image-plane left/right 和 camera-frame depth。这个细节支持我们把 camera-relative directional relation 放在 ObservationGraph/ActiveContext，而不是永久写成无 reference frame 的 BeliefEdge。

## 两个木箱场景

假设沿直线先见到 `box_A`，听到“往右拐”后又见到 `box_B`，随后用户只说“找木箱”。正确状态应是：

```text
PersistentWorldMemory: {box_A, box_B} 都保留
SceneBelief: 两个实例各有 geometry/version/confidence
ActiveContext candidates:
  box_B ↑ discourse_recency + after_route_turn + current_place
  box_A 保留为次候选
resolution:
  若分数差和行动风险足够安全 → ranked choice
  若两者仍实质歧义 → ask "右转后看到的，还是直行时看到的？"
```

FARM 能处理“右转后木箱附近有某显式 landmark”这类单条关系 query，也能保留 top-K；但论文的输入是单个 query `q`，没有定义 dialogue history、route-event recency、implicit current focus 或 clarification policy。因而我们可以实现这个能力，但必须把它定位为 `ActiveContext/IntentBelief` 的扩展和 E8 验证，不应声称关系检索本身是新贡献。

## 实验与可复核结果

论文报告 67 个室内/室外场景和 44,031 条 query，场景范围约 15–15,000 m²。主表在 ScanNet-30、HM3D-30 和 FARM-Scenes 上报告 Accuracy@1、Recall@5/10、MRR、memory size、mapping latency 与 query latency。

可用于内部判断的关键事实：

- FARM mapping 约 8 Hz；FARM-Scenes 平均约 59 ms/frame，memory 约 65.2 MiB；
- ScanNet-30 A@1/R@10 为 35.9/74.6，HM3D-30 为 7.9/26.9，FARM-Scenes 为 24.2/47.3；
- 关系谓词 + multi-embedding 的 locked retrieval 在消融中优于 pure embedding；
- VLM reranking 并不稳定：ScanNet-5 可轻微下降，HM3D-5/FARM-Scenes 才改善；
- ScanNet 主要失败在 top-1 重排，HM3D 主要失败在目标根本没进入 candidate set；
- 论文 limitation 明确承认手工 predicate 未校准、固定距离和统一权重会导致错误，并且 benchmark 主要只评 target-anchor 关系，尚未充分处理 anchor-anchor compositional reasoning。

这些数值来自预印本，正式论文中若提必须明确其状态；不能写成已同行评审结论。

## 与当前项目的重合和剩余空间

| 维度 | FARM | 当前项目应保留的差异 |
|---|---|---|
| 新对象发现 | unmatched detection 新建 entity | 增加 surface/region/Chart attachment 与 expansion/revision 分型 |
| 跨视角关联 | feature + Gaussian + union-find merge | 允许歧义、版本、quarantine，避免不可逆错误 merge |
| 同类实例检索 | target-anchor soft predicate + top-K | 不作为核心创新；可作 E8 baseline |
| 方向关系 | 在保存 camera view 中求 left/right/front/behind | 所有方向关系显式带 reference frame |
| 对话/路线偏置 | 未定义 | ActiveContext 候选分布、route/discourse factors、澄清政策 |
| 动态世界冲突 | 未给出 typed protocol | relocation/absence/occlusion/unknown 的版本化 ContextDelta |
| 修改范围 | construction loop 的 association/fusion 邻域 | affected node/edge/operator/stop 的监督与评测 |
| 无关保持 | 未报告 world-belief collateral edits | control-subgraph preservation 核心指标 |

## 论文边界如何调整

不能再声称：

- 首次在线构建可关系查询的对象记忆；
- 首次从显式 target-anchor 关系找到同类实例；
- 首次输出关系候选 top-K；
- “根据当前 query 只计算需要的关系”本身是 selective revision；
- 单纯的图增长或对象 association 是核心新意。

仍可在实验支持后主张：

- 新证据相对版本化 belief 的 pose-aware typed innovation；
- 区分 graph expansion、belief revision、visibility update 与 association ambiguity；
- 显式预测 affected nodes/edges/operators 和 propagation stop boundary；
- 在 embodied visibility uncertainty 下版本化执行；
- 联合评测 necessary propagation、unrelated preservation 与 revision cost。

## 建议采用方式

1. 参考 FARM 的 `ScoredCandidate + per-predicate breakdown + bound anchors` 设计 ActiveContext 输出，但增加 dialogue/route factors、clarification 和 belief-preservation invariant。
2. 把 FARM-style locked relational retrieval 作为 E8 强 baseline；若官方代码可在共同数据上运行，再做外部横向比较。
3. 把 FARM-style online mapper 视作可替换 construction front-end；所有 revision controller 主比较共享相同 association 输入。
4. 增加 `FARM-style fuse/merge` 机制基线，专门测试 moved object、reliable absence 和 erroneous merge 时是否污染旧关系。
5. 单独报告 `candidate recall` 与 `relational ranking`，不要让 top-1 重排掩盖 memory construction 失败。

## Evidence pointers

- Sec. 2.1–2.2 / Appendix D.1：对象记忆、detect-lift-associate-fuse、union-find、Gaussian 累积与 covisibility；
- Sec. 2.3 / Appendix B、D.2：QueryGraph、soft predicate、star decomposition、候选排名与 top-5 rerank；
- Table 1–2：主结果、memory/latency、representation 与 retrieval 消融；
- Sec. 4.1：手工 predicate 校准和 anchor compositionality limitation；
- Appendix F.6：candidate recall 与 top-1 failure 分解；
- 项目页和代码仓库：系统演示、硬件、部署和可复现入口。
