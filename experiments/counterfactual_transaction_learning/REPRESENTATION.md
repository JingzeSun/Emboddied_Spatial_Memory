# Projective Node Orbit

状态：**CPMT 表征基础；首篇固定/轻量，未实现、未验证**。

## 定义

令 \(m_j\) 为第 \(j\) 个世界节点的 canonical world latent，\(T_t\) 为具身视角，\(\Pi\) 为 view-conditioned projector：

\[
z_{t,i}\approx \Pi(T_t,m_j).
\]

节点对应的 observation-latent orbit 为：

\[
\mathcal O(m_j)
=
\{\Pi(T,m_j)\mid T\in\mathcal T_{\mathrm{reachable}}\}.
\]

因此 identity continuation 不由 EMA feature proximity 定义，而由同一 canonical node 是否能在给定 pose/visibility 下持续解释多个 structural regions 定义。

## 固定数据流

1. frozen DINO-family backbone 提取 patch features；
2. 固定 region proposals 按透视结构、深度连续性和局部几何形成 regions；
3. 每个 region 保留 feature、support、depth、camera ray、pose、visibility 和 uncertainty；
4. region 投影到 Local Structural Chart；转向期允许 mixed-chart evidence；
5. projector/transport 生成当前和未来视角下的 node predictions；
6. 只有 committed transaction 可把 evidence 写入 canonical world node。

VP 只是 observation cue，不是 world coordinate。无可靠 depth/pose 时必须降低几何置信度。

## 首篇训练边界

默认冻结 backbone、depth、pose 和 region proposals。只允许固定 projector 或轻量 transport calibration；不把 end-to-end orbit representation 与 CTL 同时作为主变量。

可选辅助约束：

\[
\mathcal L_{\mathrm{orbit}}
=
\mathcal L_{\mathrm{project}}
+\lambda_{\mathrm{cycle}}\mathcal L_{\mathrm{cycle}}
+\lambda_{\mathrm{equiv}}\mathcal L_{\mathrm{equiv}}
+\lambda_{\mathrm{vis}}\mathcal L_{\mathrm{visibility}}.
\]

这些损失只服务于表征，不构成 CTL 创新。

## 必测消融

- EMA/mean prototype；
- 无 projective regions；
- 无 pose/depth transport；
- 无 visibility；
- Projective Node Orbit。

若 CPMT 的收益完全由本消融解释，主结论降级为 representation work。
