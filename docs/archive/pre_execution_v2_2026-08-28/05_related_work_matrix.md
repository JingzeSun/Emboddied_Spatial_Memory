# Related Work 与论文定位

> 方向版本：D-013 accepted
> 状态复核：2026-08-28
> 准入规则：`literature/peer_review_audit.md`

## 1. 引用规则

- 只有 `verified_peer_reviewed + foundation/adjacent` 可支撑 Related Work 的事实论述；
- `novelty_watch_only` 只用于查重、baseline 设计和收紧 claim；
- 预印本若在论文中出现，必须明确称为 preprint/submission；
- 投稿前重新核验 venue，不根据作者主页或 arXiv 注释自动升级。

## 2. 论文不再围绕“抗污染组件”组织

旧分组“image memory / map / world model / dynamic filtering”适合旧问题，但不能突出新方法。当前 Related Work 按 **状态如何被写入和修订** 组织：

1. **Pose-aligned spatial memory construction**：旧观测如何进入世界坐标表示；
2. **Persistent object and dynamic scene memory**：实体身份、状态和长期变化如何维护；
3. **Selective memory access and context formation**：新帧/任务如何读取相关旧记忆；
4. **Belief reconciliation and graph correction**：新证据如何纠正已有结构；
5. **Changing-scene benchmarks**：怎样评测真实变化、遮挡和重新探索。

本项目必须把“选择性读取”和“选择性写入/修订”区分开。

## 3. 同行评审主干

| 研究轴 | 工作 | 已有能力 | 对当前 claim 的约束 |
|---|---|---|---|
| 在线分层图与跨层纠正 | [Hydra](https://www.roboticsproceedings.org/rss18/p050.html), RSS 2022 | object-place-room 图、在线构建、回环后优化 | 不能声称首次图纠正或分层语境 |
| 动态图记忆 | [Scene Graph Memory](https://proceedings.mlr.press/v202/kurenkov23a.html), ICML 2023 | 部分可观测动态图、对象位置预测 | 动态规律学习不是空白 |
| 开放词汇对象图 | [ConceptGraphs](https://ieeexplore.ieee.org/document/10610243), ICRA 2024 | posed RGB-D 多视角关联 | 对象级空间图不是创新本身 |
| 短/长期协调 | [Khronos](https://www.roboticsproceedings.org/rss20/p081.html), RSS 2024 | active window、fragment reconciliation、长期变化 | 双时间尺度和变化协调已有直接先例 |
| 跨视角 2D/3D 感知（邻近） | [ODIN](https://openaccess.thecvf.com/content/CVPR2024/html/Jain_ODIN_A_Single_Model_for_2D_and_3D_Segmentation_CVPR_2024_paper.html), CVPR 2024 Highlight | posed RGB-D、2D/3D 交替融合、3D kNN attention、统一 instance query | 不能声称首次让新帧在共享 3D 空间与旧视图交互；attention scope 不等于 revision scope |
| 长短期任务记忆 | [KARMA](https://doi.org/10.1109/ICRA55743.2025.11128047), ICRA 2025 | 长期 scene graph、短期对象状态 | 长短期分库不能作为主贡献 |
| 持久对象更新 | [Embodied VideoAgent](https://openaccess.thecvf.com/content/ICCV2025/html/Fan_Embodied_VideoAgent_Persistent_Memory_from_Egocentric_Videos_and_Embodied_Sensors_ICCV_2025_paper.html), ICCV 2025 | pose/depth、3D re-ID、对象状态更新 | persistent slot/state update 已有强基线 |
| 选择性读取 | [3DLLM-Mem](https://proceedings.neurips.cc/paper_files/paper/2025/hash/61f527a737e4ba61f3e10d6c3f0c4b55-Abstract-Conference.html), NeurIPS 2025 | working memory selective attention to episodic memory | “新帧只关注一部分旧记忆”不能单独声称创新 |
| 图像式增量记忆 | [3D-Mem](https://openaccess.thecvf.com/content/CVPR2025/html/Yang_3D-Mem_3D_Scene_Memory_for_Embodied_Exploration_and_Reasoning_CVPR_2025_paper.html), CVPR 2025 | snapshot context 与增量聚合 | 是非图编辑路线的强基线 |

邻近且可引用的 ODIN、g3D-LF、MTU3D、DINO-WM、Persistent Embodied World Models、G²VLM、GR3D、HSGM、AstraNav-Memory 负责建立 cross-view perception、feature field、object query memory、latent dynamics、future generation、grounding 和导航背景；它们不能代替直接 revision baseline。

### 3.1 ODIN 精读后的准确边界

ODIN 与本项目表面上都让新帧在共享 3D 空间中从旧视图取义，但两者的状态对象不同：

| 维度 | ODIN | 本项目 |
|---|---|---|
| 目标 | 对所选多视图集合做 2D/3D instance/semantic segmentation | 用新 evidence 修订已有版本化 spatial belief |
| 新帧进入方式 | depth/pose unprojection 后与所选帧共同 3D kNN attention | 投影 expected belief，生成 typed innovation，再检索 affected subgraph |
| 计算范围 | 测试通常重跑整场景图像；具身集成处理最近 N 视图 | 计划只执行必要 node/edge/operator，并显式输出 stop boundary |
| 长期状态 | learnable queries 属于当前 forward，不是 persistent object versions | SceneBelief + PersistentWorldMemory + provenance/supersedes |
| 变化语义 | 无 relocation/absence/occlusion/unknown 的 revision protocol | 显式区分并用 typed operator 执行 |
| 保持性 | 不评测无关旧知识是否被误改 | control-subgraph preservation 是核心指标 |

因此 ODIN 应作为两类资产使用：

1. 可选的 ObservationGraph/association 感知前端；
2. `recent-N joint reparse` 诊断对照，用来回答“批量重算多帧是否已经足够”。

所有 revision 方法的主比较仍必须共享同一个前端。几何 kNN attention 的邻域不应被当作 affected-subgraph 真值，因为几何邻近只定义读取信息的来源，不定义哪些旧关系必须修改或在哪里停止。完整证据见 `literature/notes/odin_2024_DEEP.md`。

## 4. 当前创新性预警

截至复核日，下列工作尚未找到足以升级为 `verified_peer_reviewed` 的官方出版记录：

| 工作 | 可核验状态 | 与本项目最接近之处 | 必须做出的差异 |
|---|---|---|---|
| [SpatialMem](https://arxiv.org/abs/2601.14895) | arXiv | metric anchors、层次空间记忆、快速查询 | 我们研究在线 belief edit scope，不是离线建库/查询 |
| [SpaMEM](https://arxiv.org/abs/2604.22409) | arXiv/venue 未官方核验 | action-conditioned dynamic spatial belief 与诊断 | 必须提供 operator、affected scope、stop boundary |
| [ChangingGrounding](https://openreview.net/forum?id=CU8HVTe9Oh) | Submitted to ICLR 2026 | 变化场景、记忆驱动定位和重新探索 | 我们的主任务是 belief revision，不是主动 grounding |
| [ViSAGE](https://arxiv.org/abs/2607.28678) | arXiv/投稿记录 | 延迟身份证据反向纠正历史记忆 | 我们需证明 pose-aware relation propagation 与局部停止 |
| [R4DSG](https://arxiv.org/abs/2608.11017) | arXiv | stable anchor、动态对象、相对变化 | 不能只提出 anchor-relative temporal graph |
| [DYNEMO-SLAM](https://arxiv.org/abs/2503.02050) | arXiv | 动态实体作为持久 landmark | 不能只声称动态对象不应被过滤 |

这些工作可以决定“哪些 claim 不能说”，但不能支撑“已有研究已经验证本方法有效”。

## 5. 当前最小差异化

### 已有工作广泛覆盖

- 空间/层次图；
- posed RGB-D association；
- 持久对象身份和状态更新；
- long/short-term memory；
- dynamic scene reconciliation；
- selective memory attention；
- 变化场景任务和重新探索。

### 本项目必须单独证明

1. 新旧 belief 差异被表示成 typed structured innovation；
2. 模型预测 affected node/edge、operator 和 stop boundary；
3. executor 以版本方式执行，而不是自由生成或原地覆盖；
4. 评测同时包含 necessary propagation 和 unrelated preservation；
5. 在 relocation、reliable absence、occlusion、stationary actor、turning 条件下统一成立；
6. 成本低于 full graph recomputation。

最安全的论文主张：

> We formulate online embodied spatial-memory updating as pose-aware affected-subgraph revision: structured innovations seed typed graph edits whose necessary propagation and stopping boundaries are explicitly predicted and evaluated.

## 6. 论文 Related Work 段落结构

### 6.1 Constructing pose-aligned spatial memories

使用 ConceptGraphs、HOV-SG、g3D-LF、MTU3D、3D-Mem 等说明 frame/feature/object 如何进入 metric memory。段末指出这些方法主要回答 memory construction/aggregation，未把每次新证据写成可监督 graph delta。

### 6.2 Persistent memory in dynamic environments

使用 Scene Graph Memory、Khronos、KARMA、Embodied VideoAgent 说明动态实体、快慢记忆和长期协调已有基础。段末把差异收紧为 explicit revision scope/operator/stop。

### 6.3 Selective context and historical correction

使用 3DLLM-Mem 说明 selective read 已存在；若提 ViSAGE 等预印本，明确其非正式出版状态。强调本项目研究 selective write/revision 及 relation-level propagation。

### 6.4 Changing-scene tasks and evaluation

使用正式同行评审 benchmark 建立背景；ChangingGrounding、SpaMEM 等只作 concurrent preprint 风险说明。强调本项目直接评测 delta、control subgraph 和 revision cost。

## 7. 强基线选择原则

必须覆盖四种失败机制：

1. append-only：不会删除/替换；
2. global update/full recompute：范围过大；
3. slot lifecycle/local update：不会关系传播；
4. oracle affected-subgraph：范围定义上限。

公开系统若无法在相同输入和数据上复现，可作为横向报告；核心因果比较优先实现机制等价 baseline。

## 8. Claim 禁区

不得写：

- first structured spatial memory；
- first dynamic embodied memory；
- first self-correcting memory；
- first selective memory update；
- first long/short-term memory；
- first memory for changing scenes。

可以在有实验支持后写：

- explicit pose-aware structured innovation；
- supervised affected-subgraph and stop-boundary prediction；
- joint evaluation of necessary propagation and unrelated preservation；
- versioned typed editing under embodied visibility uncertainty。

## 9. 写作前复核

1. 每条事实引用是否来自 `foundation/adjacent`；
2. 每个 novelty threat 状态是否重新核验；
3. 每个贡献是否有对应 baseline、metric 和 ablation；
4. 是否把 perception/backbone 收益与 revision mechanism 分开；
5. 是否报告 concurrent work、失败案例和不支持假设的结果。

## 10. FARM 精读后的定位修订

截至 2026-08-28，FARM 只有 arXiv/项目页/代码/CoRR 条目，属于 `novelty_watch_only`，不是同行评审事实基石。

| 维度 | FARM 已覆盖 | 本项目仍需单独证明 |
|---|---|---|
| 在线记忆 | detect/lift/associate/fuse、新 entity 初始化 | 冲突证据下的版本化 belief revision |
| 关系 | 固定谓词和 query-time soft relation | operator-specific dependency propagation |
| 同类实例 | semantic candidates、top-K、VLM rerank | world instances 保留与 ActiveContext 分层 |
| 更新范围 | association/fusion 邻域 | affected/control/stop 监督和 collateral metric |
| 方向关系 | 保存视图中的 camera-relative 判断 | reference frame 合同与长期写入约束 |
| 失败恢复 | union-find merge 与累积融合 | ambiguity/quarantine/supersedes/reversible execution |

因此新增两类使用方式：

1. FARM-style mapper/retrieval 作为可替换接口和 E8 外部/机制基线；
2. FARM-style fuse/merge 作为 relocation、absence、错误 merge 的污染对照。

不得声称首次 online relational object memory、首次同类 top-K 或首次 soft predicate retrieval。完整精读见 `literature/notes/farm_2026_DEEP.md`。
