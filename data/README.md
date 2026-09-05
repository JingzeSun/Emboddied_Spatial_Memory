# Data

`manifests/ithor_floorplan1_visual_pilot.json` 只登记 iTHOR `FloorPlan1` 的开发接口用途、build 版本和已生成 smoke 产物。白话说，这个 manifest 解决“这帧图从哪里来、可用于哪一步”的追溯问题：输入是公开场景、软件/build 版本和 run 引用，输出是机器可读的数据边界；例如它明确 `test_access=false` 且禁止直接把 smoke 当正式数据。它不是数据集下载包、许可法律意见、冻结 split 或三案例已经成功的证明。

状态：**尚无 CPMT 正式数据**。本目录只保存小型 manifest、许可说明和生成规则；大型图像、视频、缓存与标注不提交 Git。

## 计划结构

~~~text
data/
  manifests/         数据版本、来源、许可、hash
  splits/            按 paired_group/world_seed/asset_family 的冻结分组
  fixtures/          可提交的小型 contract cases
  generated/         ignored，程序化 simulator 数据
  external/          ignored，外部数据或软链接
  cache/             ignored，online/hindsight 分离导出
~~~

online cache 只能含截止决策时刻可用的 observation/pose/action/prior graph。future evidence、oracle equivalence 与 simulator hidden state 只存在 hindsight/evaluation cache。

数据状态必须区分 human_draft、confirmed_ground_truth、ambiguous、excluded。模型评审不是 ground truth。test split 在 M1/M3 对应 gate 与 freeze commit 完成前保持封存。
