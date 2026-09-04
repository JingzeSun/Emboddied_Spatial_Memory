# 数据路线与切分约束

状态：候选路线，待 HC-020、HC-021、HC-033。

## 1. 分层路线

| Tier | 数据 | 目的 | 可支持的结论 |
|---|---|---|---|
| T0 | 手工小型 fixtures | schema、executor、指标正确性 | 只能证明可执行 |
| T1 | 程序化结构场景 | 系统控制视角、遮挡、重复结构和动态变化 | 机制因果与压力测试 |
| T2 | AI2-THOR / Habitat 类模拟器 | 具身序列、动作和布局泛化 | 中等规模模拟证据 |
| T3 | 3RScan / ScanNet 类重访或真实回放 | 真实噪声、重访、场景变化 | 离线真实场景证据 |
| T4 | 真实机器人 | 延迟、漂移、动态人类环境 | 部署证据 |

具体数据集只在许可证、字段、任务适配和可复现性审查后进入冻结清单。

## 2. 一个 episode 至少需要

- RGB 或视频帧；可选 depth、camera intrinsics、camera pose/odometry。
- 动作或相邻位姿变化。
- region proposals 或生成它们所需的原始信号。
- oracle observation-region ↔ world-node identity。
- oracle world-node lifecycle、局部 Chart/Place attachment。
- 若有环境变化：旧事实、新事实、valid time、evidence 与 transaction。
- scene、layout、appearance、dynamic regime、sensor regime 元数据。

缺失字段必须标为 unknown，不能以启发式自动标注冒充 ground truth。

## 3. 切分规则

1. 以 scene/layout 为主键切分，禁止相邻帧跨 train/test。
2. 同一几何场景的纹理重渲染不得同时出现在 train 与 test 主表中。
3. validation 用于阈值、提示、早停和方法选择；test 不参与任何选择。
4. 保留至少四个泛化桶：unseen scene、unseen layout、unseen appearance、unseen dynamics。
5. corruption 随机种子与强度表冻结后再跑 test。
6. 若用 foundation-model pseudo label，保存模型标识、版本、prompt 和置信度，并在人工子集上测噪声。

## 4. 标注质量

- 双人标注或仲裁子集用于估计 node identity 与 transaction 一致性。
- 报告无法判定的 region；它们进入 ignore/ambiguous 集而非强制标签。
- 自动 pose/depth 不是 ground truth；若作为输入和 oracle 双重使用，必须分开版本。
- 对移动物体显式区分 identity 不变与 location fact 改变。

## 5. 数据版本

每次冻结记录：数据集名称、版本/commit、许可证、下载日期、scene 清单、split 哈希、生成器 commit、标注协议版本、排除项及原因。大型资产不提交仓库；仓库只存 manifest、脚本和小 fixtures。

