# 视觉空间记忆文献综合记录

## 1. 本轮阅读范围

普通通读：RoomTour3D、G²VLM、GR3D、HSGM、CoViS-Net，以及一篇相关性筛查后判定为非核心的绳结操作论文。

重点精读：g3D-LF、MTU3D、DINO-WM。

本记录不重复摘要，而是回答：各论文把什么当作世界状态，如何跨时间更新，在哪些条件下会失效，以及本项目怎样形成可检验的新意。

## 2. 方法总表

| 工作 | 主要状态表示 | 跨帧/跨视图机制 | 更新规则 | 动态/遮挡 | 本项目中的角色 |
|---|---|---|---|---|---|
| RoomTour3D | 几何恢复的视频轨迹与指令 | 离线 COLMAP 重建 | 数据生成，不是在线记忆 | 未建模 | 真实视频数据、转向切片 |
| G²VLM | 几何 token + 语义 token | 共享注意力融合 | 输入级推理，无长期状态 | 未建模 | 强几何/语义观测前端 |
| GR3D | grounded region token + 单目 3D 框 | 区域与语言绑定 | 输入级 grounding | 未建模 | 可检查的语义证据接口 |
| HSGM | 几何图 + 语义 BEV + 决策层 | 地图坐标聚合 | 面向导航的地图维护 | 无显式生命周期 | 结构化地图/规划 baseline |
| CoViS-Net | 多机器人 embedding + BEV | 相对位姿和不确定性聚合 | learned aggregation | 未建模对象状态 | 位姿置信与融合参考 |
| g3D-LF | 世界坐标中的语言特征点 | 深度/位姿投影 | 追加式集合并集 | 无显式机制 | feature-field baseline |
| MTU3D | 对象 query memory bank | 3D 框 IoU 匹配 | mask 并集 + 计数平均 | 无显式机制 | 最直接 object-memory baseline |
| DINO-WM | DINO patch 短历史 latent | 动作条件 Transformer | 下一 latent 预测 | 动力学中隐式吸收 | frozen patch 与短时模型参考 |

## 3. 四条已有路线

### 3.1 坐标化积累：g3D-LF

它简单、通用，天然支持 novel-view、panorama 和 BEV 读出。缺点是把“更多观测”近似等同于“更好记忆”。场景静态、位姿准确和深度可靠时很有效；对象移动、暂时遮挡、人物经过或位姿跳变时，追加式积累会保留互相冲突的世界版本。

### 3.2 对象化积累：MTU3D

它将世界状态从无身份点集推进到全局对象 query。核心问题随之变成“怎样判断是不是同一个对象”。三维框 IoU + 均值更新在干净静态场景够用，却不具备不确定性、可见性和变化推理。

### 3.3 预测式 latent：DINO-WM

它关注动作之后画面表示如何变化，擅长短期动力学和目标图像规划。它保留 spatial patch，但没有把 patch 绑定到持久世界实体。它和本项目应是快、慢两种时间尺度的互补模块。

### 3.4 任务地图与 grounding：HSGM、GR3D、G²VLM

这些工作说明几何、语义、区域证据和规划接口必须结构化。它们能提升空间问答和导航，但通常假设提供给推理器的状态已经正确，没有深入定义长期状态怎样维护。

## 4. 研究空白的精确定义

> 给定带噪声位姿的连续视觉观测，如何构建一个证据可追溯、结构可查询的世界状态，使其在视角变化和短时遮挡下保持实体与表面一致，同时能在真实持久变化发生后受控更新，而不被瞬时动态观测污染？

这一定义可直接落到模块：

- **证据可追溯**：槽位保存来源帧、区域、置信度和位姿。
- **结构可查询**：表面、对象、拓扑，而不是只有全局向量。
- **视角一致**：世界对齐 + 外观/几何联合关联。
- **遮挡保持**：由可见性预测决定“没看到”是否构成反证。
- **受控更新**：区分候选变化和已确认变化。
- **抗动态污染**：短期缓冲与长期记忆分离。

## 5. 建议的方法骨架

### 5.1 两个时间尺度

```text
Observation buffer B_t -> association/evidence -> persistent memory M_t
快、可撤销                                      慢、需确认
```

- `B_t` 保存最近观测和未确认实体，容纳路人、反光和检测抖动等瞬时事件。
- `M_t` 只保存达到确认条件的结构/对象，以及经过确认的持久变化。

### 5.2 三种结构单元

1. **Surface chart**：墙、地、桌面等局部表面及其坐标系、边界和视觉原型。
2. **Object slot**：对象身份、类别分布、外观原型、几何支持和生命周期。
3. **Topological edge**：相邻、支撑、包含、可达、遮挡等关系。

这能同时吸收 g3D-LF 的连续空间覆盖、MTU3D 的对象身份和 HSGM 的规划可用结构。

### 5.3 证据账本

每个长期槽位不只存平均特征，还保存压缩后的证据统计：

```text
slot = {
  identity, geometry, appearance_distribution, semantics,
  observation_count, last_seen, visibility_state,
  pose_confidence, dynamic_probability,
  support_evidence, conflict_evidence
}
```

“未观测到对象”只有在对象预计可见且当前感知可靠时，才算冲突证据。

### 5.4 关联与状态转移

先做几何可行性门控，再融合外观、语义、位姿和历史一致性。更新至少应包含：

```text
candidate -> confirm -> visible / occluded / out_of_view
                         |          |
                         +-> relocate / retire / reactivate
```

这比只提出一个更复杂的 attention 模块更容易形成清楚、可证伪的贡献。

## 6. 四个核心假设

### H1：结构槽位优于追加式点场

在相同视觉骨干、深度和位姿下，结构槽位应降低重复实体率和内存增长，同时维持或提升新视角读出。

### H2：可见性推理优于“没看到即删除”和“永不删除”

在短期遮挡与真实移除的配对实验中，可见性感知更新应同时获得更低误删率和更低 stale memory。

### H3：两阶段变化确认能抑制动态污染

对路人经过、手持物短时进入等瞬态干扰，短期 buffer 应显著降低长期槽位污染；对物体真正搬动，又不应产生过长确认延迟。

### H4：位姿置信门控能避免批量复制

在转身和 pose jump 条件下，保存并使用 `C_pose` 应降低 duplicate slot rate；收益应在低噪声条件下较小，在高噪声条件下显著。

## 7. 实验矩阵

### 7.1 控制变量与基线

固定视觉骨干、检测/分割器、深度、位姿输入、下游查询头和训练数据，只替换 memory representation/update。

1. Latest-frame / no memory。
2. Frame feature cache 或 DINO short-history。
3. g3D-LF 风格 append-only feature field。
4. MTU3D 风格 3D-IoU + count-average object memory。
5. HSGM/BEV 类任务地图。
6. 本项目完整结构生命周期记忆。

### 7.2 场景条件

| 条件 | 目的 |
|---|---|
| 静态重访 | 基本跨视角一致性 |
| 90°/180° 转身 | 关联和位姿敏感性 |
| 部分/完全遮挡 | object permanence |
| 路人或临时物体经过 | transient contamination |
| 对象持久移动/移除 | 更新延迟与 stale memory |
| 相似对象并列/交换 | 错误合并和 ID switch |
| 位姿高斯噪声/突跳 | confidence-aware writing |
| 长轨迹与多次回环 | 内存增长和错误累积 |

### 7.3 指标

记忆本体：association precision/recall、ID switch、duplicate slot、incorrect merge、surface consistency、dynamic contamination、stale retention time、change detection delay、projected grounding IoU、memory size 和时延。

下游任务：目标检索/空间问答准确率，ObjNav/VLN 的 SR、SPL、nDTW，以及失败归因中 perception、memory、policy 各自比例。

## 8. 当前要避免的论述风险

- 只说“比 feature field 更结构化”，却不给结构单元和状态转移的严格定义。
- 把更强的 DINO、VLM 或深度模型收益误写成记忆机制收益。
- 只在静态仿真场景做下游任务，无法支持动态鲁棒性主张。
- 以 RGB-D 真值位姿训练，却宣称纯视觉或真实在线鲁棒。
- 只报告 SR/SPL，不直接度量 ID、污染和过期记忆。
- 把所有移动对象都删除；某些动态对象仍有长期身份，关键是建模状态而非简单过滤。

## 9. 建议的近期执行顺序

1. 实现 `MTU3D-IoU-Avg` 和 `AppendOnlyFeatureField` 两个最小基线。
2. 在合成序列上只验证对象槽位生命周期，暂不接大模型。
3. 加入表面 chart，证明结构不仅服务对象追踪，也稳定背景和支撑关系。
4. 建立 static、occlusion、transient、persistent-change 四组最小对照。
5. 最后接导航或问答，验证记忆改进能转化为任务收益。

## 10. Related work 组织建议

1. **3D feature fields and grounded spatial representations**：g3D-LF、G²VLM、GR3D。
2. **Online object memories and semantic-geometric maps**：MTU3D、HSGM、CoViS-Net。
3. **Latent world models and persistent memory distinction**：DINO-WM，明确短时预测与长期状态维护的差异。

RoomTour3D 放到 data/real-world pretraining；绳结论文不进入核心 related work。

