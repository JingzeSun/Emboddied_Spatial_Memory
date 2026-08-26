# 研究问题与贡献边界

## 1. 问题定义

机器人接收连续观测：

\[
o_t = (I_t, D_t, T^w_{c_t}, K, F_t^{obs}, \text{optional semantics})
\]

目标是把随视角变化的观测转换为长期世界状态：

\[
\mathcal{M}_t = \{\mathcal{C}_t, \mathcal{S}^{persistent}_t, \mathcal{S}^{transient}_t\}
\]

其中 `C` 是 Local Structural Charts，`S` 是 persistent world slots。记忆应抵抗相机自运动和短暂遮挡，同时在真实环境变化发生时适当更新。

## 2. 中心假设

**H1 — Viewpoint robustness**  
世界坐标对齐的结构 slot 比固定 image patch 或仅按当前 VP 划分的记忆具有更高的跨视角一致性。

**H2 — Contamination resistance**  
结合 ego-motion compensation、可见性和动态概率的 soft update，能减少行人和临时遮挡对长期静态记忆的污染。

**H3 — Change responsiveness**  
带生命周期和多时间尺度证据的 slot，能比简单冻结或固定 EMA 更好地区分 transient occlusion 与 persistent environmental change。

**H4 — Turning and topology**  
允许多 Chart overlap 的局部结构记忆，能够利用转弯期间的共同可见区域建立更稳定的相对位姿和拓扑连接。

## 3. 预期贡献

1. 一种 observation/world 分离的 pose-aware structural latent representation。
2. 一种面向 region split/merge、遮挡和重现的 frame-to-world association 机制。
3. 一种结合 ego-motion residual、可见性、位姿可靠度和时间持久性的 memory update 机制。
4. 一套配对 clean/dynamic/true-change episode 与针对 memory contamination 的评测协议。

## 4. 非目标

- 不生成或修复 RGB 图像。
- 不以稠密、照片级 3D reconstruction 为主要目标。
- MVP 不同时追求导航、QA、规划三个任务的端到端最优。
- MVP 不解决任意室外、非结构化和极端非 Manhattan 环境。
- 不把 latent next-frame prediction 本身当作主要贡献。

## 5. 表述边界

推荐表述：

> 本方法不存储或预测 RGB 像素，也不构建稠密外观模型；它通过深度、位姿和稀疏结构线索，把视觉 latent 关联到可查询的长期世界结构记忆。

避免表述：

> 本方法完全不需要重建或几何估计。

## 6. 必须保留的模块

1. Observation Space 与 World Memory 的区别；
2. Camera Pose / Ego-motion；
3. Rotation / SE(3) 对齐；
4. Ego-motion compensated optical flow；
5. World structural directions，而不是固定 VP；
6. Local Structural Charts；
7. 转弯时多 Chart overlap；
8. Static / Dynamic 双记忆视图；
9. Soft confidence-based memory update；
10. Frame-to-World association；
11. Persistent world slots；
12. Viewpoint / occlusion / turning / persistent-change robustness。

## 7. MVP 范围建议

- 场景：有墙面、地板、门和拐角的室内走廊/相连房间。
- 输入：RGB、depth、camera intrinsics、pose；optical flow 可在线估计。
- 主评测：记忆保持、污染、重现关联和持久变化识别。
- 次评测：结构查询或轻量导航，不在第一阶段训练大型端到端策略。

## 8. 拟议研究升级：Online Spatial Context Revision

导师建议指出，动态对象和短期出现不能只作为静态记忆的干扰，它们本身也应被学习和记录。基于这一意见，项目新增 D-008 提案：把动态从 soft write gate 的一个负向因素，升级为驱动 `SceneBelief` 与 `ActiveContext` 结构化修正的证据。

候选主问题为：

> 机器人能否根据新观测与已有空间信念之间的 pose-aware structured innovation，在考虑自运动、遮挡、动态实体、传感器不确定性和历史关系的条件下，对空间语境进行局部、可追溯且范围正确的修正？

候选状态转换为：

\[
B_t=\operatorname{Revise}(B_{t-1},o_t,a_{t-1},\mathcal M_{t-1})
\]

\[
X_t(g_t)=\operatorname{SelectRelevantSubgraph}(B_t,g_t,T^w_{c_t})
\]

其中 `B_t` 是当前 SceneBelief，`X_t` 是任务相关 ActiveContext；二者均不等同于当前帧或完整长期记忆。

该提案不废弃 H1–H4，而可能把 contamination resistance 重新定位为语境修正中的 `PRESERVE/ISOLATE` 子能力，同时增加 `UPDATE/PROPAGATE`。完整定义见 `08_dynamic_context_revision.md`。在 D-008 接受前，当前中心假设和 `03_experiment_contract.md` 继续有效。

## 9. 提议中的优先级重组

现有研究问题与 D-008 并非两个平行项目。建议的单一组织方式是：

1. **候选核心问题**：新证据如何产生 pose-aware structured innovation，并触发范围正确的 affected-subgraph revision；
2. **必要基础**：H1 的位姿/视角对齐和 H4 的局部 Chart 组织；
3. **必要安全性质**：H2 的污染抑制对应 `PRESERVE/ISOLATE`；
4. **必要适应性质**：H3 的真实变化响应扩展为节点、关系、事件和有效时间的 `UPDATE/RELINK/SUPERSEDE`；
5. **首个验证任务**：结构化 context query，导航只作后续外部效度验证。

完整迁移审计、哨兵场景和人工确认项见 `09_integrated_direction_plan.md`。以上仍为 `proposed`：未接受 D-008 前，不把候选优先级写进正式实验配置，也不声称原假设已被验证。
