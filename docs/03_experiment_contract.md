# 实验合同

本文件应在正式查看测试结果前冻结。任何改变都需记录在 `06_decision_log.md`，并说明是否使用了测试信息。

## 1. 主问题

完整方法是否在保持真实变化响应能力的同时，降低 viewpoint change、turning 和 transient occlusion 造成的静态记忆污染？

## 2. 实验单元

最重要的实验单元是 **counterfactual group**：

```text
同一 scene + 同一 camera/action trajectory + 同一初始状态
├── clean
├── viewpoint_or_turning_only
├── transient_occlusion
├── turning_plus_transient
└── persistent_change
```

除受控变量外，其余条件保持一致。所有 train/val/test split 按 scene identity 划分，不能让同一场景的不同动态种子跨 split。

## 3. 基线阶梯

| ID | 基线 | 目的 |
|---|---|---|
| B0 | Current frame only | 证明长期记忆是否有价值 |
| B1 | Fixed ViT patch memory | 对照 image-centric fixed grid |
| B2 | Single-VP perspective regions | 检验透视切分但无 world alignment |
| B3 | Pose-warped regions | 检验 pose compensation 本身 |
| B4 | World slots + fixed EMA | 检验结构 slot 但无动态更新机制 |
| B5 | World slots + residual-flow gate | 检验基础动态抑制 |
| B6 | Full method | association + charts + multi-evidence soft update |

正式论文还应选择可复现的强基线，覆盖 image-centric compressed memory、3D/anchor memory 和 semantic-geometric map 三类，而不是只和弱 patch 基线比较。

## 4. 受控场景

- 原地旋转：0°、15°、30°、45°、60°、90°；
- translation only；
- rotation + translation；
- pedestrian partial/full occlusion；
- stationary pedestrian；
- temporary obstacle；
- door/chair 等真实 persistent change；
- corner、T junction、room entry；
- pose/depth noise sweep。

角度和噪声等级在 pilot 后冻结，不根据测试结果挑选。

## 5. 主指标

### 5.1 Static Memory Drift

比较同一 counterfactual group 的 clean 与 disturbed trajectory 在对应静态 slot 上的状态差异。至少报告 latent、geometry 和 semantic 三部分，而不是只报告一个合成分数。

### 5.2 Dynamic Contamination Rate

动态事件发生后，被错误覆盖、错误改类、错误替换或错误退休的静态 slot 比例。阈值必须在 validation set 上冻结。

### 5.3 Static Memory Retention

遮挡或转弯后，仍可正确检索和投影的历史静态 slot 比例。

### 5.4 Reappearance Consistency

`visible → occluded/out-of-view → visible` 后重新关联到原 slot 的准确率、IDF1 和重复建 slot 率。

### 5.5 Viewpoint Consistency

跨角度对应 slot 的 association accuracy、latent similarity 和几何误差。

### 5.6 Structural Chart Consistency

Chart assignment、Chart edge precision/recall、relative pose error 和重复 Chart 率。

### 5.7 Transient-vs-Persistent Change

对 transient、persistent、unknown 三类事件报告 precision、recall、F1、确认延迟和错误冻结率。

## 6. 次指标

- memory size、每帧更新时延、峰值显存；
- pose/depth noise calibration；
- scene/slot retrieval accuracy；
- 若接入导航：SR、SPL、collision rate、path efficiency；
- 若接入 QA：结构/空间问题 accuracy，并区分可见与依赖记忆的问题。

## 7. 核心消融

1. 无 structure partition；
2. 固定 VP vs world structural directions；
3. 无 pose alignment；
4. 无 depth；
5. raw flow vs ego-motion residual；
6. 无 semantic/instance evidence；
7. hard update vs soft update；
8. 二分类静/动态 vs lifecycle/multi-timescale；
9. 单 Chart vs multi-Chart overlap；
10. EMA latent vs bounded prototype set；
11. oracle pose/depth vs estimated pose/depth；
12. 不同 pose/depth 噪声等级。

## 8. MVP 成功标准（正式实验前冻结数值）

暂不在这里虚构目标百分比。完成 pilot 后，仅使用 validation set 冻结以下门槛：

- B6 的 contamination 显著低于 B3/B4；
- B6 的 persistent-change F1 不低于 B4，避免只靠冻结取得稳定性；
- turning 条件下的 reappearance 和 chart consistency 优于 single-VP；
- 在 pose/depth 合理噪声范围内优势仍存在；
- 报告多个 scene seed 的均值、置信区间和失败案例。

## 9. 可复现性要求

每次正式运行保存：

```text
run_id
code revision
config snapshot
dataset manifest + split version
random seeds
model/checkpoint identifiers
hardware and runtime
raw per-episode metrics
aggregate metrics
failure-case references
```

## 10. 证伪条件

出现以下任一情况，应重新审视核心假设：

- 简单 pose-warped EMA 在主要指标上与完整方法无显著差异；
- 降低动态污染只能通过冻结更新实现，并明显漏掉真实变化；
- Chart 机制没有改善转弯/拓扑指标，却显著增加错误和计算量；
- 方法优势只在 oracle pose/depth 下成立；
- 结构分区不优于无结构 token memory。
