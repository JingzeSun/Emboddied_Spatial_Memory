# 文献笔记索引

## 本轮综合

- [跨论文综合与研究建议](00_cross_paper_synthesis.md)

## 精读笔记

- [Scene Graph Memory](scene_graph_memory_2023_DEEP.md)：部分可观测动态图位置预测，以及它与具体 belief delta 的边界
- [Khronos](khronos_2024_DEEP.md)：短期动态、长期变化和 4D reconciliation，以及它与关系级修订范围的边界
- [Embodied VideoAgent](embodied_videoagent_2025_DEEP.md)：3D re-ID、对象状态更新，以及它与 affected-subgraph revision 的边界
- [FARM](farm_2026_DEEP.md)：在线关系空间记忆、同类候选检索，以及它与版本化 affected-subgraph revision 的边界
- [ODIN](odin_2024_DEEP.md)：posed RGB-D 的 2D/3D 交替融合，以及 cross-view attention 与 persistent revision 的边界
- [g3D-LF](g3dlf_2024_DEEP.md)：追加式三维语言特征场及其动态更新空白
- [MTU3D](mtu3d_2025_DEEP.md)：对象 query、3D IoU 关联、计数平均和 memory bank
- [DINO-WM](dinowm_2025_DEEP.md)：DINO patch latent、动作预测及其与持久记忆的边界

## 通读笔记

- [RoomTour3D](roomtour3d_2025.md)：真实视频数据与显著转向轨迹
- [G²VLM](g2vlm_2025.md)：几何/语义双专家观测前端
- [GR3D](gr3d_2026.md)：区域 grounding 和单目三维证据
- [HSGM](hsgm_2026.md)：分层语义—几何地图与规划解耦
- [CoViS-Net](covisnet_2025.md)：位姿不确定性和多视图 BEV 聚合
- [Dense Knot Untangling](knot_untangling_2021.md)：非核心论文，仅保留恢复策略启发

## 记录规范

- `*_DEEP.md`：精读到方法状态、更新公式、实验论据、失败模式和可复现基线。
- 普通笔记：记录论文角色、主要机制、关键差异和采用方式。
- 笔记中的数字用于研究定位；正式写作前应回到 PDF 表格逐项核对输入设置、数据划分和指标方向。
