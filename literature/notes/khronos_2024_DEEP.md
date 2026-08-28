# Khronos 精读：4D 时空协调与关系级修订范围的边界

> 论文：**Khronos: A Unified Approach for Spatio-Temporal Metric-Semantic SLAM in Dynamic Environments**
> venue：Robotics: Science and Systems 2024
> 同行评审状态：`verified_peer_reviewed / foundation`
> 精读日期：2026-08-28
> 官方来源：[RSS proceedings](https://www.roboticsproceedings.org/rss20/p081.html) · DOI 10.15607/RSS.2024.XX.081

## 一句话结论

Khronos 已经统一处理短期运动、长期出现/消失、pose 优化和历史时空地图协调；我们的空间不能再是“有快慢记忆”或“会发现变化”，而应落在认知关系图的 typed edit、affected/control/stop 及其联合评测。

## 方法主线

```text
RGB-D + semantics + odometry
  → active temporal window
  → object fragments + local map
  → global deformation/factor-graph optimization
  → geometric presence/absence verification
  → reconciliation into spatio-temporal map
```

active window 以近似恒定成本追踪短期动态；较慢的全局过程联合优化 robot pose、background 与 fragments，并在重访/回环后协调历史。论文用可变形 ray evidence 区分 presence、absence 与 occlusion，从而不把“没看到”直接当成“消失”。

## 实验与证据

- 模拟数据评估 background、object、motion、change detection 与 4D 时态质量；
- Jackal 与 Boston Dynamics Spot 上进行真实长序列实验；
- active window 报告实时处理，global optimization / reconciliation 异步运行；
- 真实例子包含椅子搬动、物体新增/移除、行人和推车等短期动态。

## 优点

1. 形式化 Spatio-temporal Metric-semantic SLAM，而非只做动态 outlier rejection；
2. 快慢过程职责分明，既支持在线运行又允许后续历史纠正；
3. absence evidence 显式依赖几何可见性，而非单帧缺检；
4. 同时提供模拟指标、真实平台与运行时间分析。

## 论文明确给出的局限

- fragment association 使用 bbox centroid，对 partial observation 与 occlusion 敏感；
- fragment 间缺少完整 6DoF registration；
- 当前只做几何 association，因此移动过的 fragments 不会被重新关联；
- ray-based change detection 依赖参考表面，在大而稀疏的开放空间会变弱；
- 保留所有 fragments 会导致记忆持续增长。

## 对本项目可借鉴的内容

1. reliable absence rubric 至少包含旧址可见、无遮挡、传感可靠与跨帧证据；
2. 版本评测不仅看最终图，还要看“在时间 t 对历史时刻的 belief”是否改善；
3. 把 local fast path 与 slow revision 分开，但不要把快慢分层本身当贡献；
4. 用 moved-chair、removed-object 和 occlusion 做外部场景对照；
5. 把 fragment association 错误作为 T4 ambiguity/quarantine 的重要 failure source。

## 与当前项目的最小差异

Khronos 的 edit 单位主要是 pose、surface 与 object fragment 的时空协调。当前项目的 edit 单位是版本化 SceneBelief 中的 node/edge/operator，并要求：

- 预测 required affected set；
- 显式给出 control set 与 stop edge；
- 对关系依赖做 operator-specific propagation；
- 用 deterministic transaction 执行并保存 provenance；
- 单独报告 necessary propagation 与 unrelated preservation。

## Evidence pointers

- Sec. III：SMS 问题定义；
- Sec. V-A：active window；
- Sec. V-B：global optimization；
- Sec. V-C：reconciliation 与 deformable change detection；
- Sec. VI：模拟、真实平台与 runtime；
- Sec. VII：fragment association、稀疏表面与 memory growth 局限。
