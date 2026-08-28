# 同行评审与引用用途审计

审计日期：2026-08-28。

本文件回答两个不同问题：

1. 哪些工作已经有可核验的同行评审出版记录，可以支撑论文 `Related Work` 的核心论述；
2. 哪些工作虽然新且接近，但目前只有预印本或投稿记录，只能用于创新性查重和风险预警。

## 1. 判定规则

只有在会议/期刊官方 proceedings、出版社页面，或明确标注已发表状态的官方 OpenReview 页面中找到对应条目，才标记为 `verified_peer_reviewed`。作者主页、项目主页、社交媒体中的“accepted”声明不单独作为核验依据。

`library.csv` 的 `related_work_usage` 使用四级策略：

- `foundation`：同行评审已核验，且直接定义本项目的问题、表示或更新机制；可以作为 Related Work 主干和论述依据；
- `adjacent`：同行评审已核验，但只覆盖数据、grounding、导航、feature field 或 world model 的邻近部分；可以引用，不能代替直接基线；
- `novelty_watch_only`：预印本、投稿或 venue 尚未由官方来源核实；只用于查重、边界说明和实验设计，不用来支撑“已有共识”或性能结论；
- `excluded`：已确认离题，不进入主线综述。

当论文状态变化时，先更新 `peer_review_status` 和 `venue_verification_url`，再改变引用用途。不得仅根据 arXiv 页面上的备注自动升级。

## 2. 可作为主干的已核验工作

| 研究轴 | 工作 | 已核验 venue | 对“空间语境更新”的意义 | 官方证据 |
|---|---|---|---|---|
| 分层空间组织 | Hydra | RSS 2022 | 证明对象、Place、Room 等多层场景图可以在线增量构建，并在回环后跨层纠正 | [RSS proceedings](https://www.roboticsproceedings.org/rss18/p050.html) |
| 动态先验 | Scene Graph Memory | ICML 2023 | 把部分可观测动态图和对象位置预测明确化；说明动态规律本身不是空白 | [PMLR](https://proceedings.mlr.press/v202/kurenkov23a.html) |
| 开放词汇图 | ConceptGraphs | ICRA 2024 | 从 posed RGB-D 多视角关联得到开放词汇对象图，是对象级空间语境的直接表示先例 | [IEEE Xplore](https://ieeexplore.ieee.org/document/10610243) |
| 层次语义图 | HOV-SG | RSS 2024 | 将 floor-room-object 层次和开放词汇特征结合，限定本项目不能只以“层次空间结构”为新意 | [RSS proceedings](https://roboticsproceedings.org/rss20/p077.html) |
| 短/长期变化 | Khronos | RSS 2024 | 用 fast active window 与 slow long-term reconciliation 统一短期动态和长期变化，是双时间尺度的关键基石 | [RSS proceedings](https://www.roboticsproceedings.org/rss20/p081.html) |
| 图像式空间记忆 | 3D-Mem | CVPR 2025 | 以 snapshot 保留对象及周边上下文，并增量聚合/检索；是非 slot 图像记忆强基线 | [CVF Open Access](https://openaccess.thecvf.com/content/CVPR2025/html/Yang_3D-Mem_3D_Scene_Memory_for_Embodied_Exploration_and_Reasoning_CVPR_2025_paper.html) |
| 长短期任务记忆 | KARMA | ICRA 2025 | 已提出长期 3D scene graph 加短期对象位置/状态变化；“长短期分库”不能单独作为创新 | [IEEE DOI](https://doi.org/10.1109/ICRA55743.2025.11128047) |
| 持久对象更新 | Embodied VideoAgent | ICCV 2025 | 已实现 pose/depth 驱动的 3D re-ID、对象状态更新和持久对象记忆，是最直接对象级基线之一 | [CVF Open Access](https://openaccess.thecvf.com/content/ICCV2025/html/Fan_Embodied_VideoAgent_Persistent_Memory_from_Egocentric_Videos_and_Embodied_Sensors_ICCV_2025_paper.html) |
| Attention 读记忆 | 3DLLM-Mem | NeurIPS 2025 | 用 working-memory token 查询并选择性融合 episodic spatial-temporal memory，直接回答“新帧是否需要重算全部旧上下文” | [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/61f527a737e4ba61f3e10d6c3f0c4b55-Abstract-Conference.html) |

## 3. 可引用但属于邻近路线

这些工作均有官方 proceedings 条目，但它们分别侧重数据、grounding、导航或未来生成。它们可以建立研究背景和强基线，不能直接证明本项目的 belief/context revision 有效。

- ODIN（CVPR 2024 Highlight）：posed RGB-D 的 2D within-view / 3D cross-view 交替融合；它是跨视角实例感知基石，不维护持久 belief 或 revision delta；
- RoomTour3D（CVPR 2025）：大规模几何轨迹与导航数据；
- g3D-LF（CVPR 2025）：可在线构建的 3D-language feature field；
- MTU3D（ICCV 2025）：无需显式重建的在线 query-based spatial memory 与主动探索；
- DINO-WM（ICML 2025）：冻结视觉 latent 上的 action-conditioned future prediction；
- Learning 3D Persistent Embodied World Models（NeurIPS 2025）：把生成结果写入持久 3D map，再反过来约束后续生成；
- CoViS-Net（CoRL 2024 proceedings published 2025）：relative pose 与局部 BEV 空间先验；
- G²VLM、GR3D、HSGM、AstraNav-Memory（CVPR 2026）：分别覆盖几何 grounding、3D-aware grounding、分层语义几何地图和压缩图像式长期记忆。

## 4. 只做创新性预警的工作

截至审计日，下列条目没有找到足以升级为 `verified_peer_reviewed` 的官方出版记录，因此不作为 Related Work 的论述基石：

| 工作 | 当前可核验状态 | 与本项目的重合风险 |
|---|---|---|
| SpatialMem | arXiv 2601.14895 | 结构锚点、metric-aligned hierarchy、长视频检索 |
| SpaMEM | arXiv 2604.22409；数据卡称 under review，另有作者接受声明但尚无官方 proceedings 条目 | action-conditioned dynamic spatial belief evolution 与分层诊断 |
| ChangingGrounding | OpenReview 页面仍为 `Submitted to ICLR 2026` | 变化场景中的记忆驱动 grounding 与重新探索 |
| ViSAGE | arXiv 2607.28678 / ACL ARR 投稿记录 | 延迟身份证据反向纠正历史多模态记忆 |
| DYNEMO-SLAM | arXiv 2503.02050 | 将动态实体作为持久 landmark，而非 outlier |
| R4DSG | arXiv 2608.11017 | 稳定 anchor、动态对象和 anchor-relative transition |
| Embodied-Navigator / TAMP-Nav | arXiv 2608.17512 | 关键节点保真、anchor-trajectory memory 和冗余轨迹压缩 |

这并不意味着这些工作“不可信”或“不重要”。策略只是：可以在内部查新、proposal 风险分析和 baseline 候选中使用；正式论文若必须提及，应明确写作 preprint/submission，并避免用其结果支撑已被领域共同验证的结论。

## 5. 对本项目创新边界的直接结论

同行评审工作已经覆盖：层次场景图、长短期分层、持久对象身份、对象状态更新、动态图预测、图像/token 压缩记忆、attention 检索和持久 3D world model。因此下面这些都不能单独成为方法创新：

- “加入空间语境”；
- “用 posed RGB-D 和 3D attention 让新旧视图交互”；
- “新帧查询旧记忆”；
- “把动态物体和静态背景分开”；
- “设置长短期记忆”；
- “只更新一部分记忆”。

更有机会的最小方法贡献应落在：**pose-aware structured innovation 如何触发可学习的局部图编辑，以及如何同时约束必要传播和无关保持**。需要把它实现为明确的 operator/gating/objective，而不是仅换一种存储结构，并用反事实测试区分抗噪声与真实语境修正。

