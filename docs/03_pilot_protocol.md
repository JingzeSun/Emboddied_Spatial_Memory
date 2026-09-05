# 03 CPMT 核心实验协议

定位：正式 M1 所需比较与证据规格，不维护运行状态。实际结果与当前冻结情况见 [实验记录](../EXECUTE.md)；开发运行不能替代正式门槛。

## M0 Oracle fixtures

每个 fixture 输入 prior graph、current regions、candidate programs、oracle/equivalent programs、future evidence、expected post-graph 和 protected IDs。

所有候选从同一 base version 执行。wrong version、missing precondition、illegal lifecycle、protected mutation、dangling edge 和 duplicate transaction 必须被拒绝且 base graph 不变。

## M1 六个必要对照

| ID | 方法 | 执行候选 | future supervision | post-edit world |
|---|---|---:|---:|---:|
| A | CPMT-CTL Core（M1 固定解析表征） | 是 | 是 | 是 |
| B | Direct transaction classifier | 否 | 否 | 否 |
| C | Direct + future auxiliary loss | 否 | 是 | 否 |
| D | Execute + current-only | 是 | 否 | 是 |
| E | Future scorer without execution | 否 | 是 | 否 |
| F | Oracle candidates/program | 是 | 是 | 是 |

只在 M1 通过后，M2 才增加一个强领域基线；不同时实现一长串弱比较。

命名边界：M1 的 A 只检验 executed post-world hindsight supervision，因此叫 CPMT-CTL Core。只有 M2 接入 Projective Node Orbit、真实 observation regions 和 canonical world-node latents 后，才使用 Full CPMT。白话：M1 先验证“怎样学会改档案”，M2 才补齐“不同视角下档案里的同一对象应该长什么样”；前者不是完整视觉系统。

## 公平条件

- A–E 使用相同数据、前端、可见字段、训练步数和合理参数预算；
- A/D 使用相同 candidate budget；
- C 获得独立合理调参；
- F 明确标作 upper bound；
- 所有方法报告 wall-clock、显存和失败 run；
- paired group 与 world seed 不跨 split。

## 主要终点

1. post-execution graph correctness；
2. long-horizon memory contamination；
3. node growth/false birth；
4. protected/collateral violation。

program exact match、template macro-F1、candidate coverage 和 latent error 是诊断指标。

## 固定解释

- A≈C：未来监督有效，但 executable transaction learning 未成立；
- A≈E：不需要 post-edit execution，CPMT 主机制未成立；
- F coverage 低：candidate generator 失败；
- teacher 好、online 差：amortization 失败；
- 单步好、self-rollout 差：persistent-memory claim 失败。

精确 effect threshold 和 CI 在正式 test 前冻结，不根据 test 重写。
