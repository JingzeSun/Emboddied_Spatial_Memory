# Projective Structural Latent Memory：竞争图谱

核查日期：2026-09-04。以下结论优先基于论文官方 proceedings；“对 PSLM 的含义”为本项目推断。

## 1. Latent world model

### DINO-WM（ICML 2025）

官方页：https://proceedings.mlr.press/v267/zhou25t.html

论文以动作条件预测预训练 DINOv2 spatial patch features，并用未来 feature 进行 test-time action sequence optimization。它直接否定“无需 RGB reconstruction、预测 foundation latent”可以单独作为创新。

对 PSLM 的含义：必须独立评价 `PredictProject`，并证明长期 persistent world state、region-to-node binding 与版本修订是新增能力。若只预测下一帧 latent，贡献落回 DINO-WM 邻域。

### 4D Latent World Model（ICLR 2026 在审版本）

OpenReview：https://openreview.net/pdf?id=iB9qx28gv4

在审稿件使用 structured sparse voxel latent 预测 3D scene evolution 并服务机器人规划。发表状态不确定，不能写成已发表事实；但它说明“3D structured latent world model”这一表述已非常拥挤。

对 PSLM 的含义：差异必须落在可持续 node identity、在线增长和可审计 transaction，而非仅“4D/3D latent”。

## 2. 多视角与 foundation-feature 3D perception

### ODIN（CVPR 2024）

官方页：https://openaccess.thecvf.com/content/CVPR2024/html/Jain_ODIN_A_Single_Model_for_2D_and_3D_Segmentation_CVPR_2024_paper.html

ODIN 通过 2D within-view 与 3D cross-view 操作交替融合 posed RGB-D tokens。它是多视角 region/token 融合的强参照。

### ConceptFusion（RSS 2023）

官方页：https://roboticsproceedings.org/rss19/p066.html

ConceptFusion 将开放集、多模态 foundation features 融入 3D map。它说明 feature map 的开放语义和多模态查询不是 PSLM 的核心新意。

对 PSLM 的含义：需要共享前端或做 backbone 消融，防止收益被更强 feature 解释。

## 3. 分层在线 scene memory

### 3D Dynamic Scene Graphs（RSS 2020）

官方页：https://roboticsproceedings.org/rss16/p079.html

该工作以 place、object、human 等节点和多层关系构建 actionable spatial representation。

### Hydra（RSS 2022）

官方页：https://roboticsproceedings.org/rss18/p050.html

Hydra 实时增量构建分层 3D scene graph，并处理 place extraction、room segmentation、loop closure 与图优化。

对 PSLM 的含义：Place/Chart/node hierarchy 与实时构图本身不是创新。需要证明 learned observation-to-world transaction 与 projective latent expectation。

## 4. 长期动态与修订

### Khronos（RSS 2024）

官方页：https://roboticsproceedings.org/rss20/p081.html

Khronos 将短期动态跟踪与长期变化推理解耦，构建实时 spatio-temporal metric-semantic map。

### SuperMap（RSS 2026）

官方页：https://roboticsproceedings.org/rss22/p052.html

SuperMap 提供 3D-aware instance association/reactivation、存在与标签置信度更新、appearance/disappearance/relocation、4D scene graph 历史查询和语言导航。

对 PSLM 的含义：这是当前最直接威胁。PSLM 若只在对象层做 reactivation 和 stale-map pruning，会缺乏新颖性。候选差异是：

- surface/object/portal/occlusion 混合 region，而非仅 instance map。
- prior memory 的 action-conditioned projective structural prediction。
- observation proposal split/merge 与 world identity split/merge 的显式区分。
- birth、attachment、revision 共用一个可约束 transaction space。
- 与规则式 3D association/reactivation 的正面对照。

## 5. 必须持续搜索的关键词

- persistent latent spatial memory / object permanence / online world graph
- action-conditioned 3D latent world model / projective world model
- data association with abstention / set-valued tracking / neural SLAM memory
- lifelong scene graph / 4D mapping / change-aware navigation
- region-to-world correspondence / dynamic map revision / temporal knowledge graph for robots

在论文冻结前必须重新搜索 2026–2027 新工作；若出现完整 project-bind-transact 闭环，需要重写 claim boundary。

