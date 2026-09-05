# CPMT Data Plan

定位：候选数据来源、字段与适配验收规格；实际选型、是否下载/运行和当前下一步统一见 [实验记录](../../EXECUTE.md)。候选来源不是默认已接受的正式数据。

## 三层

1. M0：12–30 个可审计 graph fixtures；
2. M1：程序化 paired latent worlds；
3. M2/M3：一个 embodied simulator 主数据源和一个 external/现实来源。

不增加第二个非具身应用领域。

## 必需字段

world_seed、paired_group_id、split、observations、poses、actions、visibility、prior world、candidate programs、oracle equivalence、future evidence、protected IDs、generator version。

online export 物理删除 future、oracle 和 hidden state。

## Split

paired group、world seed、asset family 和同源轨迹不跨 split。validation 选择 horizon/K/weights/checkpoint；test 在 freeze commit 后一次性正式运行。

现实数据无法唯一判断 transaction 时保留 ambiguity（不确定性）/多假设，不把模型判断当 ground truth。只有满足 D-025 保守状态相等条件才使用 equivalence；不能因暂时分不清或未来投影相似而合并不同世界。

## 2026-09-05 公开来源候选（D-028 proposed）

用户希望从简单任务走向公开具身数据，并愿意考虑租服务器。助手建议以下组合；用户尚未正式确认具体数据源、试点规模和预算。下列来源已在本轮对话查询，尚未下载数据或检验安装可用性。

### 主环境候选：ProcTHOR＋AI2-THOR

白话：ProcTHOR 提供公开的室内房屋场景，AI2-THOR 让相机/机器人在里面移动和观察；输入场景与动作，输出观测和环境记录。例如绕到椅子背面、离开后重访，检查该绑定旧节点还是修改位置。它不是下载即用的 CTL 事务训练集。

- ProcTHOR 提供程序生成的可交互房屋；[官方介绍](https://procthor.allenai.org/) 与 [ProcTHOR-10K 仓库](https://github.com/allenai/procthor-10k)。
- AI2-THOR 提供 RGB、深度、分割及 agent/object 元数据；[观测和状态接口](https://ai2thor.allenai.org/ithor/documentation/environment-state/)。对象操作需按具体版本验证，不能假定所有资产都能自由移动/创建。
- 拟覆盖：换视角重见、首次揭示、物体移动、遮挡但未消失、重访修订；首次看见不等于物理上刚创建。
- 尚缺：版本锁定、许可核查、轨迹与变化事件生成、样本筛选、身份对照审计、数据导出、候选世界的视觉特征投影。
- 输入边界：GT 实例 ID、不可见对象位置、完整场景图和未来只能进入独立审计/允许的离线监督；在线 memory 必须来自截至当前的观测。即使先用分割轮廓，也要移除跨帧对象编号/固定颜色暗含的身份答案。

### 现实验证候选：3RScan

白话：同一真实房间在不同状态下被重复扫描，输入不同扫描中的 RGB-D 和相机位姿，评估旧对象对应和变化。例如重访后原物体换了位置，旧记忆是否得到正确修订；它不是完整记录搬运过程的连续机器人动作数据。

- 官方提供标定 RGB-D、相机位姿、跨扫描对齐、实例对应及变化对象信息；[官方仓库](https://github.com/WaldJohannaU/3RScan)、[项目与获取入口](https://waldjohannau.github.io/RIO/)。
- 适合候选用途：跨重访身份与位置修订的现实验证；不假定它覆盖所有 CTL 事务或有完整动作日志。
- 获取流程、数据许可和实际字段覆盖尚需核查；代码仓库的许可不自动等同于数据许可。
- 跨扫描对齐/实例对应属于需要声明的参考信息；若固定 pose 条件使用参考对齐，必须对所有方法一致开放并明确 oracle 条件，不把完整重建泄漏进在线旧世界。
- 不能从缺少标注直接推断对象消失；歧义/漏标/无法建立的事务应保留并报告。

## 数据适配验收规格

本节规定接口应满足什么，不维护当前任务顺序、规模或完成状态；这些只在 [实验记录](../../EXECUTE.md)。

1. 可追溯：许可、数据/模拟器版本、场景/资产列表、时间、相机参数和实际动作齐全，失败显式记录。
2. 可观察：支持重见、首次揭示、移动后重访的连续样本；呈现画面、位姿、当时记忆、候选和独立参考，不把首次发现等同于物理新建。
3. 无泄漏：online 与 audit 物理隔离，检查实例 ID/颜色、不可见对象、未来、完整重建，以及同源轨迹/资产跨 split 泄漏。
4. 可投影：候选 post-world＋固定几何/位姿输出可见性、位置和可比较观测。白话：能检查“这样改以后从另一个视角会看见什么”；不等于完整 PNO 或生成未来 RGB，不能用三位置换位替代真实 3D 投影。
5. 可审计教师：真实执行候选、记录所有能量分项/概率，覆盖遮挡、冗余编辑和信息不足；不只查排名第一。
6. 可计费：测渲染吞吐、固定前端特征提取耗时、峰值显存、缓存体积及训练耗时，不把硬件建议当实测保证。
7. 可比较：公开训练部分用于开发，test 不触碰；正式比较前冻结标签/知识/计算公平条件、split、评分/评价与差异门槛。
8. 可解释限制：不可辨识案例单独分析；复杂数据不保证 CTL 胜出；数据适配不能代替正式 M1 gate，不能把准备工作写成 M2 或长期效果已验证。

来源候选和接口合同的实质变化才更新本文件；普通讨论与下一步追加 EXECUTE，不按对话扩写另一份进度清单。
