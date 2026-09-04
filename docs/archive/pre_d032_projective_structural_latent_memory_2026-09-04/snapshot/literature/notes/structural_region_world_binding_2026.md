# 结构区域到持久世界节点：已评审先例与项目边界

> 状态：2026-08-29 方向综合；引用均已在官方 proceedings 核验。  
> 用途：为 planned `Structural Observation Tokenizer + Region-to-World Structural Binding` 定位，不代表组件已实现或已验证。

## 1. 先给结论

“按照透视、墙面、地面或语义把图像切成区域”不是新的；“把多视图特征抬到统一 3D 空间并融合”也不是新的。现有已评审工作已经覆盖：

- 消失点/房间边界驱动的 layout estimation；
- 单帧 piecewise planar regions；
- 跨片段 plane correspondence、tracking 与 global fusion；
- object-centric slots；
- posed RGB-D 的跨视角 2D/3D token fusion；
- pixel-aligned feature 到 world-aligned 3D map 的融合；
- object/place/room 分层场景图。

本项目仍需验证的窄问题是：

> 当前视角中的临时区域，怎样在歧义、遮挡、动态变化和重复外观下绑定到版本化 world belief；哪些节点允许写，哪些必须保持，何时新建候选、暂缓或回滚。

因此，region partition 是表示底座；只有“绑定 + 有界写入”相对简单表示的消融成立，才能讨论它是否构成方法贡献。

## 2. 同行评审基石

| 工作 | 已经解决什么 | 没有替本项目解决什么 | 可借鉴 |
|---|---|---|---|
| [LayoutNet, CVPR 2018](https://openaccess.thecvf.com/content_cvpr_2018/html/Zou_LayoutNet_Reconstructing_the_CVPR_2018_paper.html) | 用 vanishing points、边界和 Manhattan layout 从单图恢复房间结构 | 不维护跨帧世界 identity，也不处理动态修订 | VP、墙/地/顶边界只作 observation cues |
| [PlaneRCNN, CVPR 2019](https://openaccess.thecvf.com/content_CVPR_2019/html/Liu_PlaneRCNN_3D_Plane_Detection_and_Reconstruction_From_a_Single_Image_CVPR_2019_paper.html) | 从单图检测任意数量的平面 masks、参数与 piecewise planar depth | 单帧区域没有持久版本、写入门或 change/reveal 判别 | plane mask/parameter 可作为 region proposal |
| [Slot Attention, NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/hash/8511df98c02ab60aea1b2356c013bc0f-Abstract.html) | 从视觉特征竞争性形成可交换的对象 slots | slot 不天然是稳定的 world-surface ID，也不规定跨帧版本化更新 | 对象区域可用 slots；不能只靠 object slots 表达空走廊 |
| [NeuralRecon, CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/html/Sun_NeuralRecon_Real-Time_Coherent_3D_Reconstruction_From_Monocular_Video_CVPR_2021_paper.html) | 在 view-independent 3D volume 中进行局部重建和 recurrent global fusion | 目标是连贯几何，不区分 candidate/fact、动态 typed edit 与 control preservation | world-aligned 3D volume 是强几何/融合基线 |
| [PlanarRecon, CVPR 2022](https://openaccess.thecvf.com/content/CVPR2022/html/Xie_PlanarRecon_Real-Time_3D_Plane_Detection_and_Reconstruction_From_Posed_Monocular_CVPR_2022_paper.html) | 多帧 3D plane detection，跨 fragment attention matching、tracking 和 global fusion | 不维护多解释 belief、reliable change、版本链或禁止写入的 control nodes | 最直接的 plane association/fusion 基线；禁止声称首次跨帧区域绑定 |
| [ConceptFusion, RSS 2023](https://roboticsproceedings.org/rss19/p066.html) | 将 pixel-aligned 开放集多模态特征经 SLAM/多视图融合写入 3D map | 没有本项目的 candidate/fact 分离和 evidence-path/typed revision | full/pixel-to-3D feature fusion 基线 |
| [Scene Graph Memory, ICML 2023](https://proceedings.mlr.press/v202/kurenkov23a.html) | 用部分可观测动态图记忆预测对象位置，服务高效搜索 | 不提供表面区域绑定、显式 posterior delta 或 latent write scope | 世界状态/动态先验与下游 search 基石 |
| [ODIN, CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Jain_ODIN_A_Single_Model_for_2D_and_3D_Segmentation_CVPR_2024_paper.html) | 在 2D within-view 与 3D cross-view 层间交替融合 posed RGB-D tokens，增强实例一致性 | 处理的是选定视图集合的分割，不是持续、版本化的 belief write | 强感知前端；同前端下比较不同 binding/revision controller |
| [Hydra, RSS 2022](https://www.roboticsproceedings.org/rss18/p050.html) | 在线构建 object/place/room 等分层 3D scene graph 并做全局优化 | 不以每次新证据的 allowed write、typed posterior 和动态 stop 作为监督目标 | world node / Chart / Place 层级与稳定锚点 |

## 3. 对当前设计的直接约束

### 3.1 不采用“八个透视块 = 八个长期节点”

相机一移动，近/中/远边界和消失点扇区就会变化。它们可以帮助找 wall/floor/opening 边界，但不能成为 world identity。正确分层是：

~~~text
patch / depth / semantic / instance / occlusion / portal cues
  → temporary ObservationRegion
  → association hypotheses
  → world-aligned Surface / Portal / Object
  → stable Chart
  → Place / Route
~~~

### 3.2 用 hybrid regions，而不是只信一种切法

第一版可组合：

1. pose/depth 重投影与几何连续性；
2. plane/surface proposal；
3. semantic/instance masks；
4. occlusion boundary；
5. portal/opening cues；
6. VP/room-layout cues。

VP 只提供弱几何先验。纯对象方法会漏掉没有显著物体的墙、地面和开口；纯平面方法又难表示椅子、箱子和人物。

### 3.3 长期 latent 需要写入权限

每个临时 region 的输出不是“一个向量直接 EMA”，而是：

~~~text
matched old node
| new-node candidate
| several possible nodes
| quarantine

+ allowed write targets
+ reliability / provenance
+ split / merge evidence
~~~

只有 matched 且满足可靠性门的区域可以更新对应 world node；new candidate 先进入 hypothesis；ambiguous/quarantine 不写长期 latent。

## 4. 必须做的消融

| 对照 | 回答什么 |
|---|---|
| fixed image patches | 透视/视角变化是否制造大量错绑 |
| full-frame latent / global EMA | 局部变化是否污染无关区域 |
| object-only slots | 无对象走廊、墙面和开口是否无法表达 |
| geometry-only planes | 对象与非平面结构是否丢失 |
| oracle region + oracle association | 表示桥的机制上限 |
| hybrid region + deterministic association | 不依赖大模型时是否已经有效 |
| learned binder/tokenizer | 学习是否真正超过确定性几何/语义组合 |

核心指标：association precision/recall、duplicate-node rate、false merge、split/merge recovery、latent contamination、control preservation、nodes-per-meter 和 abstention quality。

## 5. 论文能写到什么程度

- 当前：`we introduce a planned structural observation bridge and define its falsifiable contract`；
- oracle/deterministic pilot 通过：可说该桥在受控输入下可执行；
- 相对简单表示的 frozen-test 消融通过：才可说它改善了 bounded belief update；
- 若无改善：删除独立贡献表述，保留最简单可用接口；
- 不写：first perspective partition、first region node、first plane fusion、first 2D-to-3D memory、first object slot。

## 6. 与 HC-014 的关系

本文回答“学界已经做到什么、我们不能重复主张什么”；[HC-014](../../docs/human_confirmation/HC-014.md) 回答“本项目具体怎样判 association、split/merge、new node、quarantine 和 latent write”。在 HC-014 accepted 前，不把这里的建议写入 schema/config。
