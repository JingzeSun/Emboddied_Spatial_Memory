# DINO-WM：精读记录

## 1. 基本信息

- 论文：DINO-WM: World Models on Pre-trained Visual Features Enable Zero-shot Planning
- 年份/会议：2025，ICML
- 本地文件：`papers_detail/zhou25t.pdf`
- 官方来源：https://proceedings.mlr.press/v267/zhou25t.html
- 预印本：https://arxiv.org/abs/2411.04983
- 阅读目标：理解其 latent state、动作条件转移、目标代价和 zero-shot planning，并明确它与空间记忆的边界。

## 2. 核心判断

DINO-WM 说明冻结 DINOv2 patch 特征本身就能成为有效的视觉世界模型状态，不必重建 RGB，也能通过预测未来 latent 做规划。它支持本项目采用**冻结、patch-level、无像素解码器**的视觉观测表示。

但 DINO-WM 的 latent 是随相机图像和动作推进的短历史动态状态，目标是预测下一 latent；它没有把观测对齐到持久世界坐标，也没有实体身份、表面结构、遮挡状态和长期变化协议。因此不能把“world model”名称直接等同于本项目的“world memory”。

## 3. 问题设定

像素生成式世界模型常把大量容量用于纹理和视觉细节，且训练复杂。论文问：能否直接在强视觉基础模型的表示空间中学习动作条件动态，并用目标图像做零样本规划？

训练是离线、任务无关的：给定观测—动作轨迹，学习 latent transition；测试时给目标图像，不再训练任务特定策略或奖励模型。

## 4. 模型组成

### 4.1 观测编码器

- 冻结 DINOv2。
- 使用 patch token，而非只用 CLS token。
- 每帧 RGB 被编码成空间 token 网格；空间布局仍保留在 patch 序列中。

### 4.2 动作条件转移模型

- 用 MLP 编码动作，再与每个视觉 patch token 拼接/融合。
- 使用 ViT/Transformer 风格 transition model 预测下一帧的 latent patches。
- 引入多帧历史和因果注意力，确保预测只依赖过去。
- 可选接入 proprioception。

训练目标基本是预测 latent 与冻结 DINO 目标 latent 之间的均方误差：

```text
L_transition = || z_(t+1) - z_hat_(t+1) ||^2
```

### 4.3 可选解码器

像素解码器只用于可视化，不是规划所需。把图像重建损失反传进 transition model 反而会降低部分任务表现；PushT 的一个结果从约 0.92 降到 0.80。

## 5. 规划方式

给定目标 RGB 图像，先编码得到 `z_goal`。对于候选动作序列，世界模型滚动预测终点 latent，以终点与目标的 latent 距离作为代价：

```text
J(a_t:t+H) = || z_hat_(t+H) - z_goal ||^2
```

采用 CEM 搜索动作序列，并以 MPC 方式执行：只执行当前最优序列的前若干步，再根据新观测重新规划。实验显示 MPC 通常优于纯开环或直接对动作做梯度优化。

## 6. 数据与训练设置

- 环境：Maze、Wall、Reacher、PushT、Rope、Granular，共覆盖导航、刚体操控和可变形物体。
- 轨迹规模依环境约 1k–20k。
- 输入图像常规设置为 224 分辨率。
- 训练约 100 epochs。
- 需要离线 state-action 覆盖和已知动作；它不主动探索数据不足的区域。

## 7. 关键实验和证据

### 7.1 规划性能

论文报告 DINO-WM 在 Maze、Wall、Reacher、PushT 等任务上取得约 0.98、0.96、0.92、0.90 的归一化任务分数，在 Rope/Granular 的 Chamfer distance 类指标上约为 0.41/0.26，并优于或匹配 Dreamer、IRIS、TD-MPC2 等像素/latent 世界模型基线。

### 7.2 patch token 的必要性

使用 DINO patch token 的结果明显优于只用全局 CLS token。一个对照中，patch 配置在 Wall、Reacher、PushT 上约 0.96/0.92/0.90，而 CLS 配置约 0.58/0.60/0.44。

这说明基础模型的空间 token 对几何可控性至关重要，也反对把整帧压成单一全局向量。

### 7.3 历史与因果性

多帧历史和 causal mask 对部分接触任务关键。一个 h=3 的配置在使用因果掩码时约 0.92，移除掩码后约 0.08，说明模型很容易在不正确的时间信息流下失效。

### 7.4 组合泛化

在 WallRandom、PushObj、GranularRandom 等改变布局/对象的测试上仍有一定泛化，报告结果约 0.82/0.34/0.63。泛化并非均匀，复杂对象和背景变化仍明显更难。

## 8. 它真正证明了什么

它较有说服力地证明：

- 强自监督视觉 patch 是学习动作动态的有效状态空间。
- 不重建像素也能进行目标图像条件规划。
- 保留空间 patch 比全局表示更适合控制。
- MPC 可以纠正 latent model 的开环误差。

它没有证明：

- latent 跨任意视角重访保持同一世界实体身份。
- 背景变化、人员干扰等 nuisance 不会改变目标代价。
- 模型能区分遮挡和对象真正消失。
- 状态能跨超长轨迹压缩、查询和更新。
- 无动作标签、未知动力学或主动探索时仍有效。

## 9. World model 与 world memory 的边界

| 维度 | DINO-WM | 本项目视觉空间记忆 |
|---|---|---|
| 状态坐标 | 图像 patch / 短历史 latent | 世界对齐的对象、表面和拓扑 |
| 核心操作 | 动作条件下一步预测 | 跨视图关联、状态维护和查询 |
| 时间目标 | 预测未来观测表示 | 保留持久事实并处理变化 |
| 遮挡 | 由 transition 隐式吸收 | 显式可见性/遮挡状态 |
| 动态对象 | 作为画面动力学的一部分 | 区分 transient 与 persistent change |
| 规划目标 | 到目标图像的 latent 距离 | 可服务导航、问答、操作等多种读出 |
| 训练依赖 | 离线 state-action 轨迹 | 可仅从观测序列增量维护；下游另接 planner |

两者可以组合：空间记忆提供持久结构状态，DINO-WM 类局部 transition model 预测短时动作后果。不要让一个模块承担两种时间尺度。

## 10. 对本项目最具体的启发

### 10.1 采用 patch-level frozen feature

对象或表面槽位应聚合 patch/region 特征，不应只保存整帧 CLS。冻结骨干能让基线公平且训练成本可控。

### 10.2 MVP 不需要 RGB 解码器

如果任务目标是关联、读出和规划，不必把像素重建作为主损失。可以用：

- 跨视图特征一致性；
- 槽位重识别；
- 几何/可见性预测；
- 下游任务损失。

### 10.3 区分快状态和慢状态

- 快状态：最近若干帧 patch、运动线索、短时遮挡者。
- 慢状态：已确认对象、表面、房间拓扑和持久变化。

DINO-WM 更接近快状态动力学；本项目核心应是慢状态协议。

### 10.4 目标距离必须结构化

单纯 latent L2 可能被背景或视角变化主导。若以后接规划，建议使用对象/表面加权距离和可见性掩码，而不是全图特征等权。

## 11. 可复现基线与扩展实验

可建立三个层次：

1. `DINO-LatestFrame`：只保存当前 patch。
2. `DINO-ShortHistory`：Transformer 汇聚最近 h 帧，近似 DINO-WM observation state。
3. `PersistentSlotMemory`：世界对齐、显式关联和生命周期。

评测不一定先训练完整 action model，可以固定观测轨迹并比较：

- 目标对象重访匹配；
- 相机转身后的目标检索；
- 遮挡前后状态一致性；
- 背景干扰下的目标相似度漂移；
- 对象移动后的旧/新位置判断。

若后续加入规划，再比较 image-latent goal cost 与 structure-aware goal cost。

## 12. 可直接写入论文的批判性表述草案

> Pre-trained patch features provide a compact and controllable latent space for action-conditioned prediction, avoiding the burden of pixel reconstruction. However, predictive latent state and persistent spatial memory address different temporal abstractions: the former models short-horizon observation dynamics, whereas the latter must preserve entity identity and structural facts across viewpoint changes, occlusion, and persistent scene updates.

## 13. 复现与阅读待办

- [ ] 核对各环境的历史长度、预测 horizon 和 CEM 参数。
- [ ] 查 DINOv2 具体 backbone/patch size 与 token 维度。
- [ ] 区分各表中 score 与 Chamfer distance 的方向，避免错误横向平均。
- [ ] 获取代码后测试 camera-only distractor、moving person 和 target relocation。
- [ ] 调研后续对视觉世界模型 background invariance 的工作，作为讨论而非当前基线。

