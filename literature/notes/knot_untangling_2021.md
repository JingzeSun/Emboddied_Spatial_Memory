# Untangling Dense Non-Planar Knots：通读记录

## 基本信息

- 论文：Untangling Dense Non-Planar Knots by Learning Manipulation Features and Recovery Policies
- 年份/会议：2021，Robotics: Science and Systems
- 本地文件：`papers/p013.pdf`
- 官方来源：https://www.roboticsproceedings.org/rss17/p013.html
- 阅读层级：快速通读、相关性筛查
- 身份说明：依据本地文件名 `p013.pdf` 与 RSS XVII 论文编号识别；后续引用前建议再人工目视核对首页。

## 一句话结论

这篇论文研究绳结解开与失败恢复，并非视觉空间记忆论文；它对本项目的边缘价值是“进展监测—异常检测—恢复策略”这一闭环思想，不应进入核心 related work 主线。

## 方法与证据

- HULK 提供基础解结动作。
- LOKI 学习更精确的操作特征定位。
- SPiDERMan 监测操作进展并在卡住、遮挡或绳索状态异常时触发恢复动作。
- 论文在真实 da Vinci 机器人上执行大量绳结和动作试验，报告约 68.3% 的整体成功率，并优于无恢复基线。

## 对本项目可能有用的抽象

- 不要把记忆更新设计成永不失败的单向管线；需要监测“本次关联/写入是否可信”。
- 当不确定性过高时，可触发重新观察、换视角或延迟确认，而不是立即覆盖长期状态。
- 下游行为可以作为记忆错误的外部信号，但不能替代显式的记忆一致性指标。

## 处理建议

- 在文献库中标记为 `skimmed_offtopic`。
- 不放入核心视觉空间记忆对比表。
- 若论文后续强调 active perception 或 recovery，可在讨论章节用一句话引出“记忆失败后的主动重观察”。

