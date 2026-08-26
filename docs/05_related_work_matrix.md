# 相关工作矩阵

## 1. 引用准入门槛

完整机器可读目录见 `literature/library.csv`，逐项证据和判定规则见 `literature/peer_review_audit.md`。

只有 `peer_review_status=verified_peer_reviewed` 的条目才能作为 Related Work 的事实与论述基石。预印本和投稿可以用于创新性查重、边界说明或 baseline 候选，但不得写成领域已经验证的结论。

## 2. 同行评审已核验：Related Work 主干

| 工作 | 官方 venue | 已覆盖能力 | 对本项目创新边界的约束 |
|---|---|---|---|
| [Hydra](https://www.roboticsproceedings.org/rss18/p050.html) | RSS 2022 | 对象—Place—Room 多层场景图、在线增量构建、回环后跨层纠正 | “分层空间语境”和“新证据修正旧图”都已有系统先例 |
| [Scene Graph Memory](https://proceedings.mlr.press/v202/kurenkov23a.html) | ICML 2023 | 部分可观测动态图、对象位置预测 | 动态规律学习本身不是空白 |
| [ConceptGraphs](https://ieeexplore.ieee.org/document/10610243) | ICRA 2024 | posed RGB-D 多视角关联、开放词汇对象图 | 对象级空间图不能单独构成创新 |
| [HOV-SG](https://www.roboticsproceedings.org/rss20/p077.html) | RSS 2024 | floor-room-object 层次、开放词汇特征、语言导航 | 仅提出层次结构或空间语义层不够 |
| [Khronos](https://www.roboticsproceedings.org/rss20/p081.html) | RSS 2024 | 短期 active window、长期 fragment reconciliation、场景变化 | “快/慢记忆”和背景保护已有直接先例 |
| [3D-Mem](https://openaccess.thecvf.com/content/CVPR2025/html/Yang_3D-Mem_3D_Scene_Memory_for_Embodied_Exploration_and_Reasoning_CVPR_2025_paper.html) | CVPR 2025 | snapshot 上下文、增量聚合、主动探索与检索 | 图像式上下文记忆是结构 slot 的必要强基线 |
| [KARMA](https://doi.org/10.1109/ICRA55743.2025.11128047) | ICRA 2025 | 长期 3D scene graph、短期对象位置/状态与替换 | “长短期分库”不能作为主创新 |
| [Embodied VideoAgent](https://openaccess.thecvf.com/content/ICCV2025/html/Fan_Embodied_VideoAgent_Persistent_Memory_from_Egocentric_Videos_and_Embodied_Sensors_ICCV_2025_paper.html) | ICCV 2025 | pose/depth、3D re-ID、persistent object memory、状态更新 | 持久对象槽和动态更新已有直接强基线 |
| [3DLLM-Mem](https://proceedings.neurips.cc/paper_files/paper/2025/hash/61f527a737e4ba61f3e10d6c3f0c4b55-Abstract-Conference.html) | NeurIPS 2025 | working-memory query 对 episodic spatial-temporal memory 的选择性 attention | “新帧只读取相关旧记忆”本身不是创新；必须研究写入与结构修正 |

## 3. 同行评审已核验：邻近路线与强基线

| 工作 | 官方 venue | 本项目借鉴 | 与本项目的差异/风险 |
|---|---|---|---|
| RoomTour3D | CVPR 2025 | 室内视频、几何轨迹、VLN 数据规模 | 重点是数据与 instruction tuning |
| g3D-LF | CVPR 2025 | 3D-language feature field、在线更新 | posed RGB-D 连续场；需说明为何需要可编辑结构 slot/Chart |
| MTU3D | ICCV 2025 | 在线 query-based spatial memory、active exploration | 已强调无需显式重建，是直接任务强基线 |
| DINO-WM | ICML 2025 | frozen DINO latent、无 RGB decoding 的规划 | 预测 future latent，不维护可追溯的世界坐标 belief graph |
| Learning 3D Persistent Embodied World Models | NeurIPS 2025 | 新生成 RGB-D 写入 3D map，并约束后续生成 | 偏未来生成和全局一致性，不是证据驱动的实体/关系编辑 |
| CoViS-Net | CoRL 2024 | relative pose、BEV 和 unseen-region prior | 多机器人空间估计，不是单机器人长期语境修正 |
| G²VLM | CVPR 2026 | 统一几何学习与空间推理 | 重点是 3D grounding/reconstruction，不是在线 persistent memory |
| GR3D | CVPR 2026 | 2D/3D grounding 与 spatial reasoning | 不直接解决长期 slot 写入和回溯修正 |
| HSGM | CVPR 2026 | 几何/语义/决策层次地图 | 是结构地图与规划强对照，但没有动态生命周期 |
| AstraNav-Memory | CVPR 2026 | 压缩 image-centric long memory | 代表不显式建结构 slot 的强路线 |

`papers/p013.pdf` 已识别为 RSS 2021 绳结操作论文，属于离题条目，保留索引但不进入主线综述。

## 4. 只做创新性预警：尚未完成官方同行评审核验

| 工作 | 当前状态 | 为什么仍必须跟踪 |
|---|---|---|
| [SpatialMem](https://arxiv.org/abs/2601.14895) | arXiv | 结构锚点、层次 metric memory 与 clutter/occlusion 高度接近 |
| [SpaMEM](https://arxiv.org/abs/2604.22409) | arXiv；本轮未找到官方 proceedings 条目 | 直接评测 action-conditioned dynamic spatial belief evolution |
| [ChangingGrounding](https://openreview.net/forum?id=CU8HVTe9Oh) | OpenReview 仍显示 Submitted to ICLR 2026 | 变化场景中的记忆驱动 grounding 与重新探索 |
| [ViSAGE](https://arxiv.org/abs/2607.28678) | arXiv / ACL ARR 投稿记录 | 延迟身份信息反向修正历史多模态记忆 |
| [DYNEMO-SLAM](https://arxiv.org/abs/2503.02050) | arXiv | 动态实体作为持久 landmark，而不是 outlier |
| [R4DSG](https://arxiv.org/abs/2608.11017) | arXiv | stable anchor、persistent identity、anchor-relative transition |
| [Embodied-Navigator / TAMP-Nav](https://arxiv.org/abs/2608.17512) | arXiv | 关键节点选择性保真与 anchor-trajectory memory |

## 5. 相关工作分组

论文不应只按年份罗列，建议按以下问题组织：

1. **Image/token memory**：保存帧、token 或压缩上下文；
2. **Metric/semantic maps**：voxel、BEV、occupancy、feature fields；
3. **Object/anchor/scene-graph memory**：可解释实体和关系；
4. **Latent world models**：预测未来 latent 或用于规划；
5. **Dynamic-scene filtering**：ego-motion、dynamic SLAM、遮挡与变化检测；
6. **Embodied benchmarks**：VLN、ObjNav、EQA、真实动态机器人数据。

## 6. 当前差异化主张

最安全的主张不是“首次使用 latent memory”或“首次不重建 RGB”，而是：

> 面向相机转弯和动态遮挡，通过世界结构方向、Local Structural Chart、persistent slot association 与多证据 soft update，显式测量并抑制长期空间记忆污染，同时保持对真实持久变化的响应。

这个主张是否成立，必须由强基线和 `03_experiment_contract.md` 中的反事实配对评测决定。

若 D-008 被接受，候选新增主张为：

> 根据新观测与旧空间信念的 pose-aware structured innovation，对实体、遮挡、事件、Chart、Place 和空间关系执行最小充分、证据可追溯的局部语境修正，并同时评测必要传播与无关保持。

该表述当前是 proposed research claim，不是已实现或已验证结论。其相对同行评审主干（尤其 Khronos、Embodied VideoAgent、3DLLM-Mem、Hydra）和预印本风险项（尤其 SpaMEM、SpatialMem、ViSAGE、R4DSG、ChangingGrounding）的最小新增贡献必须通过查新、强基线与消融确认。

## 7. 每篇精读必须回答

1. 它的 memory coordinate system 是什么？
2. 如何处理 camera pose 和 viewpoint change？
3. memory unit 是 frame、patch、voxel、object、anchor 还是 latent slot？
4. 如何创建、关联、更新和删除 memory？
5. 是否显式处理动态遮挡与真实变化？
6. 评测是否包含 counterfactual clean/dynamic 对照？
7. 使用什么传感器、监督和重建假设？
8. 本项目相对它的最小新增贡献是什么？
