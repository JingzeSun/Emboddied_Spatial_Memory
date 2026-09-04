# 跨论文综合：PSLM 还剩什么空间

核查日期：2026-09-04。

## 已经拥挤的区域

1. 预训练视觉 latent 预测未来：DINO-WM 已证明可在不重建像素的情况下预测 DINOv2 patch features 并用于 zero-shot planning。
2. 多视角 2D/3D token 融合：ODIN 等工作已系统建模 within-view 与 cross-view 融合。
3. foundation feature 写入 3D map：ConceptFusion 等已覆盖开放集、多模态特征融合。
4. 在线分层 scene graph：3D DSG 与 Hydra 已覆盖 place/object/room 等层级和实时增量构图。
5. 动态、长期和版本环境：Khronos 已覆盖时空 metric-semantic mapping；SuperMap 进一步覆盖 3D-aware instance association/reactivation、存在/标签置信度、历史查询与语言导航。

因此“DINO latent + 透视 + graph node + 在线更新”本身不新。

## 仍可检验的窄命题

当前最有希望的差异不是表示组件，而是决策闭环：

> 世界记忆先投影为动作/视角条件下的预期结构 latent；模型在 observation regions 与 persistent world nodes 之间做 set-valued、可拒识的绑定，并把 birth、local attachment 与 evidence/time/scope-aware revision 作为统一 transaction 执行。

这一定义将三类通常分开的错误放到同一因果链中：

- 视角变化被误判成新世界，造成 duplicate birth。
- 新区域被误绑定旧节点，造成 false merge 和覆盖不足。
- 真正环境变化被普通 feature fusion 吸收，造成 stale/contaminated memory。

## 最强竞争压力

SuperMap 已明确处理 identity drift、reactivation、appearance/disappearance、relocation 与历史查询。因此 PSLM 不能把这些能力本身作为新颖性。必须证明 projective latent expectation、surface/portal/frontier 级 binding、set mapping 或统一 transaction 相对其类机制带来可重复新收益。

## 投稿判断

- 只实现 latent node 与 EMA/新 loss：不够方法创新。
- 有可靠 B/G/R evaluator，并胜过 pose-warp、rule lifecycle、local graph matcher：可形成方法论文。
- 再有长 rollout、真实回放、下游价值和一般性学习原则：才有资格讨论顶级 ML/AI 期刊。

