# 分阶段实验协议

状态：计划中。任何越级实验都不能替代前置 gate。

## P0 冻结问题与边界

- 完成 HC-020–HC-034 中当前阶段必需项。
- 冻结 observation/world/transaction schema 与 scenario IDs。
- 记录允许的输入、oracle-only 字段和第一篇论文明确不做的内容。

产物：签字后的 HC、schema 版本、case contract。

## P1 评价器与确定性执行器

- 对 T0 fixtures 实现 schema validation、transaction execute、constraint check 与 B/G/M/R/P 指标。
- 每个正例至少有四个 targeted corruption。
- 同输入、同版本、同 seed 的执行结果必须一致。

Gate：所有 evaluator 单元测试通过，人工复核结果一致。此阶段不训练模型。

## P2 规则基线与 oracle 分解

- 实现 R0–R4 与 O0。
- 分别测 oracle association + learned/rule transaction，以及 learned association + oracle transaction。
- 找出误差来自感知、绑定、birth/attachment 还是 revision。

Gate：指标能区分预设 corruption，且没有 oracle 泄漏。

## P3 最小学习系统

- 先训练 L0/L1，再加入 `PredictProject` 与 transaction decoder。
- 从单 Chart、静态几何、小规模动作开始；达到明确机制增益后才扩展。
- 保存 config、seed、data version、code commit、backbone ID、完整失败日志。

Gate：M0 相对最强公平基线的改善跨 seed 稳定，并通过预注册的最小效果量。

## P4 模拟器 rollout

- 扩展至多 Chart、长序列、遮挡、重复结构和动态干扰。
- 同时报告 teacher-forced 与 full rollout。
- 检查节点数、错误累积、延迟和显存随 episode 长度的增长。

Gate：改善不只存在于短窗或单帧，且没有以无界节点增长换取 recall。

## P5 预测、修订与下游价值

- 独立评价 P1–P3，验证预测是否帮助绑定或 frontier/attachment。
- 在环境变化场景测 R1–R6。
- 以 read-only memory API 做 T1，下游任务不得直接修改 memory。

Gate：移除核心模块造成预注册退化，且 memory 改善能转化为至少一个下游任务收益。

## P6 外部与真实数据

- 在 T3 做冻结协议回放；条件允许再做 T4。
- 对齐输入后运行可复现的外部强基线。
- 报告传感器失败、位姿漂移、未知动态和延迟。

## P7 消融、反例与论文冻结

- 完成 BASELINES 的必需消融与 NOVELTY 中的 falsifier。
- 冻结 test 脚本与 checkpoint，再一次性生成主表。
- 把负结果、异常 episode 和不支持主张的结果写入论文材料。

## 运行记录

每次正式 run 必须带 `run_manifest`：代码 commit、dirty 状态、配置哈希、数据版本、split、模型 ID、seed、硬件、开始/结束时间、完整指标、失败信息与输出位置。

