# 后验图修订相关工作与结构化审计

## 当前问题

ESGBU 不以“有图、有 Transformer、会更新记忆”为创新，而是学习 `q(ΔG,M,τ,Z | G,E)`，并测试双时间、负证据充分性、最小写边界、有效时间和证据集合。

## 结构化审计 SA1–SA8

最低结构化条件：SA1 稳定可寻址事实、SA2 显式关系/依赖、SA3 跨时间持久增量状态。SA4 双时间、SA5 provenance、SA6 affected/protected、SA7 valid time、SA8 dependency consistency 是额外能力，不因方法有 GNN 自动成立。

| 工作 | 已确认重合 | 仍需逐实现审计 |
|---|---|---|
| Scene Graph Memory | 部分可观测动态图、学习关系/位置记忆 | 双时间、最小写集、valid time、evidence set |
| SceneGraphFusion | GNN 增量 3D scene graph | 长期冲突、protected controls、事务 provenance |
| Continuous Scene Representations | 在线更新连续关系表示 | 显式编辑程序和依赖停止边界 |
| DiffVSGG | 在线视频图的迭代更新 | 迟到证据、有效时间和无关保护 |
| Embodied VideoAgent | 持久对象记忆与状态更新 | 显式最小修订、双时间和依赖事务 |
| TGN | event-based dynamic graph 强 backbone | 世界事实语义、写约束和 evidence sufficiency |
| Structured World Belief | POMDP 中结构化 object-relation belief | 当前异步证据图编辑输出是否覆盖 |

“9 月 1 日 DSG”尚缺准确题名/版本/官方链接，不能凭缩写下结论。补齐后按 SA1–SA8 和 `ΔG/M/τ/Z` 逐项填表；若其已经覆盖同一组合，应缩小或更换 claim。

## Loss 结论

默认四项 loss 与四个随机变量一一对应。Kendall uncertainty weighting、GradNorm 和 PCGrad 都是出现实际尺度/梯度冲突后的比较项，不是让方法显得复杂的装饰。硬约束由 executor 保证，state/preserve/task 先做评价。

## 数据结论

- symbolic：快速反证和训练控制，不替代具身证据；
- AI2-THOR：可控主轨，提供 scripted changes、视角、遮挡和 simulator event time；
- 3RScan/3DSSG：真实重扫外部轨，主要支持变化区间；
- native method 数据不同则只进外部表，主因果比较仍用统一 canonical input。

## 核心来源

[Scene Graph Memory](https://proceedings.mlr.press/v202/kurenkov23a.html)、[SceneGraphFusion](https://openaccess.thecvf.com/content/CVPR2021/html/Wu_SceneGraphFusion_Incremental_3D_Scene_Graph_Prediction_From_RGB-D_Sequences_CVPR_2021_paper.html)、[Continuous Scene Representations](https://openaccess.thecvf.com/content/CVPR2022/html/Gadre_Continuous_Scene_Representations_for_Embodied_AI_CVPR_2022_paper.html)、[DiffVSGG](https://openaccess.thecvf.com/content/CVPR2025/html/Chen_DiffVsgg_Diffusion-Driven_Online_Video_Scene_Graph_Generation_CVPR_2025_paper.html)、[Embodied VideoAgent](https://openaccess.thecvf.com/content/ICCV2025/html/Fan_Embodied_VideoAgent_Persistent_Memory_from_Egocentric_Videos_and_Embodied_Sensors_ICCV_2025_paper.html)、[TGN](https://arxiv.org/abs/2006.10637)、[Structured World Belief](https://proceedings.mlr.press/v139/singh21a.html)、[GradNorm](https://proceedings.mlr.press/v80/chen18a.html)、[uncertainty weighting](https://openaccess.thecvf.com/content_cvpr_2018/html/Kendall_Multi-Task_Learning_Using_CVPR_2018_paper.html)、[PCGrad](https://proceedings.neurips.cc/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html)。

