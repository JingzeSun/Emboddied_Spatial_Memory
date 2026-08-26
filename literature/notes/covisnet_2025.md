# CoViS-Net：通读记录

## 基本信息

- 论文：CoViS-Net: A Cooperative Visual Spatial Foundation Model for Multi-Robot Applications
- 年份/会议：CoRL 2024，PMLR 2025
- 本地文件：`papers/blumenkamp25a.pdf`
- 官方来源：https://proceedings.mlr.press/v270/blumenkamp25a.html
- 阅读层级：通读；重点核对相对位姿、位姿不确定性和 BEV 聚合

## 一句话结论

CoViS-Net 的亮点是把相对位姿及其 aleatoric uncertainty 与多机器人视觉特征共同聚合到 BEV；对本项目最直接的启发是显式保存 `C_pose` 并让错误位姿影响写入权重，而不是把所有对齐结果视作等可信。

## 核心方法

- 每台机器人以冻结 DINOv2 ViT-S/14 编码图像，再传输紧凑视觉 embedding。
- 成对位姿编码器预测相对平移、旋转及不确定性，即使图像没有重叠也尝试估计。
- 多节点聚合器把不同机器人视觉信息变换并融合为统一 BEV。
- 训练包含位姿高斯负对数似然、旋转 chordal loss，以及 BEV 的 Dice/BCE 类损失。
- 在 Habitat/HM3D 的约 800 个场景训练，并用真实多机器人平台验证通信和控制。

## 对本项目的启发

- 每次记忆写入都应绑定位姿来源、时间戳和位姿协方差/置信度。
- 关联门限可随位姿不确定性自适应；低置信度时允许候选挂起，而非强制合并。
- 可以建立 `pose_noise × turning_angle` 二维评测切片，观察错误对齐如何引发槽位复制或污染。
- BEV 只是记忆的一种读出，不应成为唯一内部表示；对象和表面证据仍需可追溯。

## 与本项目的差异和局限

- 研究的是多机器人同时协作与相对位姿，不是单体跨时间的长期记忆。
- BEV 聚合强调任务预测，不负责对象生命周期和“旧世界状态是否仍成立”。
- 对动态对象、遮挡、暂态证据和持久变化没有专门的记忆协议。
- 预测式 BEV 可能包含合理但未观测的区域，若用于记忆真值需要区分 observation 与 hallucination。

## 建议采用方式

- 将其列为 **位姿不确定性与多视图融合参考**。
- MVP 至少实现 `pose_confidence` 字段和基于置信度的写入门控。
- 后续比较固定门限、位姿置信门控和联合外观—几何关联三种策略。

