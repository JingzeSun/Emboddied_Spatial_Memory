# 数据集与 Episode 规范

## 1. 数据需要回答什么

数据不是为了泛化地训练所有具身能力，而是为了隔离并测量四类因素：

1. viewpoint / turning；
2. ego-motion 与真实动态的分离；
3. transient occlusion 与 reappearance；
4. persistent environmental change。

## 2. 数据角色

建议把数据源分成三类，不能让单个数据集承担所有任务：

| 角色 | 要求 | 用途 |
|---|---|---|
| Controlled synthetic | 可重复轨迹、可控制动态体、完整 pose/depth/visibility | 训练、消融、因果配对评测 |
| Public embodied benchmark | 已有导航或空间任务协议 | 下游有效性和横向比较 |
| Real dynamic sequence | 真实人流、遮挡、传感器误差 | 外部鲁棒性和失败案例 |

具体数据集选择前必须核对许可证、下载大小、传感器、标注、场景重叠和可程序化程度。

## 3. Counterfactual Group

每个 group 共享：

- `scene_id`；
- 初始世界状态；
- camera/action trajectory；
- camera intrinsics；
- 随机种子族；
- 静态结构 ground truth。

只改变 condition：

```text
clean
turning_only
transient_occlusion
turning_plus_transient
persistent_change
```

这样可以直接比较同一 world slot 在受控干扰前后的记忆状态。

## 4. Episode 最小字段

机器可读契约见 `schemas/episode.schema.json`。概念上每个 episode 包含：

```text
episode metadata
scene and split identity
counterfactual group and condition
sensor calibration
ordered frames
camera pose and pose source
RGB/depth/flow references
static/dynamic/visibility annotations
surface/object/chart identity
events and persistent-change labels
trajectory and action metadata
data provenance and license
```

估计值和 ground truth 必须使用不同字段，不能混写。

## 5. 必需标注

### 几何与姿态

- timestamp；
- camera intrinsics；
- `T_world_camera`；
- metric depth 或 depth source；
- pose/depth confidence；
- 可选 structural plane、normal 和 boundaries。

### 跨帧身份

- persistent surface/object ID；
- visibility fraction；
- occluded / out-of-FOV / absent 的区分；
- Chart ID 与 Chart edge ground truth（若可得）。

### 动态和变化

- dynamic instance tracks；
- transient occupancy；
- change event start/end；
- change type；
- 是否应更新长期 memory。

## 6. 数据切分

- 主切分单位是 scene，而不是 frame 或 trajectory。
- 同一 counterfactual group 的所有条件只能位于同一 split。
- 同一真实建筑的不同录制尽量视作同一 scene family。
- validation 用于阈值、生命周期和 metric cut-off；test 只用于最终报告。
- 对合成资产和动态 actor 额外记录 asset split，防止外观泄漏。

## 7. MVP-0 Pilot（暂定）

目标不是训练最终模型，而是验证数据和指标链路：

- 至少包含直走廊、转角、T junction 和 room entry；
- 每个场景至少有 clean、turning、transient、persistent-change；
- 首批构建 20 个可视化检查通过的 paired episodes；
- 手工核验 pose、visibility、persistent ID 和 event label；
- 先跑 B0–B4，确认指标能够区分明显错误。

Pilot 数量不是论文规模，正式规模在数据管线稳定后决定。

## 8. 质量检查

每个 episode 进入训练或评测前检查：

- timestamp 严格递增；
- pose 矩阵合法且坐标约定一致；
- RGB/depth 分辨率与 intrinsics 一致；
- counterfactual trajectories 对齐；
- persistent ID 不因遮挡或出 FOV 改变；
- transient/persistent event 标签无矛盾；
- split 和 provenance 完整；
- 文件 hash/manifest 可重建。

## 9. 数据目录策略

大型数据不放入 Git。建议实际数据根目录由环境变量或本机配置提供：

```text
<external_data_root>/
├── raw/
├── interim/
├── processed/
├── manifests/
└── splits/
```

仓库中的 `data/` 只保存 README、小型 manifest 示例和无版权问题的微型测试样本。
