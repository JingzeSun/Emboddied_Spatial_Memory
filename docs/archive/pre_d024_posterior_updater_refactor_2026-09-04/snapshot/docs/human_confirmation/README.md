# 人工判题工作表

> 每份 HC 已直接内嵌对应的指标解释、公式、数字算例和待冻结选择，可独立阅读；[HC 指标白话说明与数字算例](METRIC_GUIDE.md)只作为跨 HC 术语索引。其中的数字仅演示计算方法，不是已接受阈值。

本目录展开 HC-001～HC-018 的场景、输入输出、允许答案和评价标准，供研究者逐项思考与填写。

## 治理边界

- `docs/DECISIONS.md` 仍是唯一的 HC 状态、推荐默认值和最终用户回答入口；
- 本目录不是第二份待确认清单，不单独维护 pending/accepted 状态；
- 每个 `HC-XXX.md` 只详细展开同一个 HC 的判题空间；
- 用户明确回答后，先在 `DECISIONS.md` 追加 `D-XXX`，再把接受的规则回填到 schema/config/fixture；
- 未确认内容只能称为设计候选，不能称为 ground truth；
- 任何数值阈值只用 validation 选择，正式 test 不参与选择。

## 每个工作表怎样使用

posterior-first 的推荐阅读顺序是：先决定 [HC-018](HC-018.md) 是否允许窄通道先行；若选 A，再依次处理 HC-015/016（时间与提交门）、HC-001/004/011（身份、可靠缺失与变化来源）、HC-002/003/005（关系与等价事务）、HC-013/017（总评测与基线准入）。这只是阅读顺序，不在本文件复制状态或最终答案。

1. 先阅读“固定不变量”，这些来自已接受合同，不需要重新讨论；
2. 对场景矩阵逐行判断允许输出、禁止输出和是否需要更多证据；
3. 对“必须由研究者选择”的问题给出明确回答；
4. 允许多个正确答案时，定义 acceptable set 或等价不变量，不强迫唯一图；
5. 在 `DECISIONS.md` 记录最终回答和新的 `D-XXX`；
6. fixture metadata 与正式 run manifest 保存实际采用的 `decision_ids`。

## 通用场景记录格式

每个场景至少包含：

| 字段 | 含义 |
|---|---|
| Scenario ID | 稳定编号，例如 `HC001-S01` |
| 初始世界 | confirmed facts、hypotheses、history |
| 动作 | planned、executed、pose transition |
| 观测 | 可见区域、identity/geometry/pose evidence、可靠性 |
| 唯一变化 | 与同组反事实相比只改变哪一项 |
| 允许输出 | 可接受的状态路径、operator 或 action set |
| 禁止输出 | 一票否决的错误 |
| 评价 | hard invariant、分类指标、校准或成本指标 |
| 依赖决定 | HC/D ID 与 protocol version |

## 每个基础场景应继续做的系统变化

工作表中的场景行是基础语义案例。转成 fixture 时，优先沿以下维度做单因素 sweep，而不是把所有组合一次混在一起：

- 证据：强 / 弱 / 缺失 / 多模态冲突 / 共同原因错误；
- 可见性：完整 / 部分 / 遮挡 / out-of-FOV / reliably empty；
- pose：oracle / 小噪声 / 大协方差 / 漂移 / 跳变 / loop correction；
- 时间：连续 / 短遮挡 / 长间隔 / 周期重现 / 慢变化；
- 数量：单实例 / 同类双实例 / 多候选 / detector split/merge；
- 几何：近/远、局部/完整覆盖、同层/跨层、可行/不可能运动；
- 任务：歧义无关 / 有代价 / 高风险 / deadline / 可逆与不可逆；
- 传感器：oracle graph / known pose RGB-D / estimated pose/depth/detector；
- 输出：唯一允许答案 / acceptable set / 必须 abstain/quarantine。

组合场景只有在单因素场景通过后才加入，并记录它由哪些基础 Scenario ID 组成。

## 评价分层

- **合同硬门**：候选不得冒充事实、非法操作原子拒绝、版本无环、query 不改世界等；oracle pilot 中必须全部通过；
- **语义硬门**：identity、absence、propagation、promotion 等由对应 HC 冻结后判定；
- **学习指标**：precision/recall、calibration、latency、cost 等，阈值只在 validation 上冻结；
- **端到端指标**：最终 belief、任务成功、累计成本和失败类型，不能用平均分掩盖任一硬门失败。

文件名当前为 `HC-001.md` 至 `HC-018.md`。新增人工问题必须先在 `DECISIONS.md` 登记新的 HC，再创建对应工作表。

当前场景库是覆盖已知变量的广泛初稿，不声称数学意义上的穷尽。发现新的边界或失败类型时，只追加到对应 HC 工作表并记录来源；是否改变判题规则仍需回到 `DECISIONS.md` 由用户明确确认。
