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

### 面向机器学习论文的四个必答问题

状态：**论文论证要求；对应假设仍待验证，不是新增实验门槛或已成立结论。**

1. **执行后形成监督，究竟比直接 future loss 多解决了什么？** 由 M1 的 A–C/A–E 主比较及机制分析排除替代解释；执行器可用、测试通过或训练收敛不能代替相对收益。
2. **收益能否跨过真实视觉误差，并保留到连续记忆修订？** 由 M2 的固定感知前端与使用自身已提交记忆的连续运行验证；单步准确率不能代替持续世界错误减少，M1 的受控解析观测不能冒充真实视觉证据。
3. **收益是否仍存在于共享表征、共享候选、合理调优的强对照之上？** 主机制比较共享感知信息、候选机会、执行基础和登记的模型选择规则，分别披露额外计算与修订机会；不能把更强前端、更大模型或额外慢路径的收益归给 CTL。
4. **软教师分布为什么有用，其有效边界在哪里？** 报告教师与参考标签的一致性、分布变化及其向在线学生的传递。某能量项移除后分布变化，不等于学生性能提高；H=3 与 H=1 的教师分布对照，不等于已证明多步监督改善学生。若教师第一名始终与参考标签一致，不宣称普遍纠正标签；弱或零机制结果必须收窄叙述。

白话：这四问解决“工程已经完整，但论文为什么是一项学习贡献仍说不清”的问题。输入是既有 M1–M3 协议产生的主比较、机制分解和视觉连续运行证据，输出是可以支持的论文主张与必须保留的边界。例如加入视觉表征后所有方法同幅改善，只能说明前端有帮助，不能据此宣称 CTL 更好。它不是新的实验结果、调参清单或通过门，也不允许在 M1 失败后用表征或模型扩张挽救原主张。

## 停止规则

- 两次预注册 M1 都无法区分 A 与 C/E：停止 CPMT learning claim；
- test 泄漏或 split 污染：整批结果作废；
- baseline 不公平：不做相对优越性 claim；
- 负结果保留，不事后重定义 primary metric。
