# 基线与预算公平性

状态：候选集合，最终选择待 HC-032。

## 1. 内部机制基线

| ID | 名称 | 保留 | 移除/替换 | 用途 |
|---|---|---|---|---|
| R0 | Fixed image-patch memory | 冻结视觉特征 | 无投影、无节点持久化 | 检验纯外观缓存 |
| R1 | Perspective-grid memory | 透视/VP 区域 | 仅帧内或短窗结构 | 检验透视 tokenizer 本身 |
| R2 | Pose-warped feature map | 同一前端、深度/位姿 | 最近邻融合，无 learned binding | 检验几何投影即可解释多少 |
| R3 | IoU+appearance slot averaging | 持久 slot | 手工加权匹配与 EMA | 对照旧方法核心 |
| R4 | Rule lifecycle memory | R3 + 可见性规则 | 无 learned transaction | 检验规则是否足够 |
| L0 | Learned pair matcher | 同一 region/node encoder | 无上下文、无 predict-project | 检验 pair learning |
| L1 | Local graph matcher | 局部关系上下文 | 无行动条件预测 | 检验图上下文 |
| L2 | Recent-N 3D fusion | 3D/时序融合 | 无长期版本记忆 | 检验短窗强基线 |
| L3 | Full recomputation graph | 全历史重建 | 非增量 | 精度上界与计算代价对照 |
| M0 | PSLM | 完整循环 | 无 | 主方法 |
| O0 | Oracle association | oracle 绑定 | 学习绑定被替换 | 分离绑定与 transaction 上限 |

## 2. 外部系统定位

DINO-WM、ConceptFusion、ODIN、Hydra、Khronos、SuperMap 用于比较研究问题和公开任务。只有在输入、输出与评测协议可对齐时才做数值对比；否则报告机制级差异，不制造伪公平排行榜。

不得把 L2/L3 写成上述系统的“复现”，除非使用其官方实现、默认协议并记录必要改动。

## 3. 公平性约束

1. 能共享的视觉 backbone、region proposals、深度、位姿与训练数据必须共享。
2. 每种基线同时报告 teacher-forced 与 rollout；不能让某一方独享 oracle history。
3. 同一学习预算下报告参数量、训练步数、有效样本、GPU 时长；同一部署预算下报告延迟和显存。
4. 阈值只在 validation 调整，各方法拥有同等搜索预算。
5. 主方法独有输入必须做“去掉该输入”的消融；基线无法消费某输入时明确说明。
6. full recomputation 与 online 方法分别报告质量和累计计算，不只比较最终精度。

## 4. 必需消融

- 无 projective structural tokenizer：改用规则 grid 或普通 patch token。
- 无 `PredictProject`：只从当前观测与 memory 匹配。
- 无关系上下文：node 独立匹配。
- 无 `UNRESOLVED/QUARANTINE`：强制 bind/new。
- 无 delayed confirmation：单帧即可 birth。
- 无版本与 evidence：直接覆写事实。
- old ESGBU-only：正确 target 给定，只学习/预测 revision fields。
- 无 learned component：规则投影、匹配和 transaction。

## 5. 结论边界

- 若 M0 只胜过 R0/R1，证据不足以支持新方法。
- 若 R2/R4 与 M0 相当，学习式绑定/transaction 的必要性失败。
- 若 L1 与 M0 相当，action-conditioned predict-project 的贡献失败。
- 若 L3 更准但代价明显更高，可支持“增量效率”而非“绝对精度”主张。
- 若优势仅来自更强 backbone，必须降格为表征收益。

