# 05 CPMT 正式评估与论文门槛

状态：**计划中**。

## Gate 1：Learning mechanism

M1 的 CPMT-CTL Core 必须在相同固定表征与预算下优于 direct+future-loss 和 no-execution scorer。否则停止 CTL 主 claim，也不进入 Full CPMT 的 PNO 集成。

## Gate 2：Online persistence

收益必须从 hindsight teacher 保留到 causal online self-rollout，并减少 graph contamination、false birth 或错误修订。单步 template accuracy 不够。

## Gate 3：Embodied relevance

在 turning、revisit、reveal、relocation、absence 和 occlusion 中至少覆盖主要 failure modes。SPLIT/MERGE 作为组合压力测试；不要求为每类建设独立大数据集。

## Gate 4：External evidence

只需一个可信 external/现实来源。若无法获得可靠 ground truth，诚实报告 qualitative/coverage，不把模型判断当 truth。

## 必须报告

- A–F 主表；
- teacher vs online vs self-rollout；
- 0/1/10/100% label fraction；
- template 与 graph-level metrics；
- candidate/teacher/amortization/rollout error decomposition；
- node growth、collateral edits、runtime 和 failures；
- Projective Node Orbit vs EMA representation；
- claim–evidence table。

## 论文贡献顺序

1. CTL：executable counterfactual hindsight posterior；
2. causal online amortization；
3. CPMT：在 projective embodied memory 中的实例化与长期验证。

executor 与 loss 不单独列为创新。主动消歧、第二领域和导航只写 limitations/future work。

命名规则：M1 报告 `CPMT-CTL Core`；M2 中只有同时包含 Projective Node Orbit、versioned world graph、executor 与 CTL 的系统才报告 `Full CPMT`。不能把解析三位置或固定针孔接口写成 Full CPMT。

## 投稿定位

先完成 Gate 1–3，再根据证据选择 ML venue。不要为预设 venue 增加与核心假设无关的模块。

## 停止规则

- 两次预注册 M1 都无法区分 A 与 C/E：停止 CPMT learning claim；
- test 泄漏或 split 污染：整批结果作废；
- baseline 不公平：不做相对优越性 claim；
- 负结果保留，不事后重定义 primary metric。
