# M1-v2 收口执行流程

本文件是 M1-v2 从当前 pretest 走到结束的唯一流程大纲。它解决“下一步做什么、看到什么结果后走哪条分支”的问题；输入是已登记的 M1 合同和每阶段结果，输出是下一个有界任务。例如 E 的 target-only oracle 高、但 scorer train accuracy 低时，下一步是优化诊断，不是改 target。它不是实验结果日志、不是新的方法合同，也不代替机器可读配置。

## 文件职责与优先级

| 文件 | 只负责什么 |
|---|---|
| 本文件 | 阶段顺序、分支条件、当前指针、允许调整的开发细节 |
| [`EXECUTE.md`](../../EXECUTE.md) | 已经发生的 run、失败、结果与当前看板；不再承担完整流程 |
| [`configs/m1_hard_condition.json`](../../configs/m1_hard_condition.json) | 方法、候选、split、门槛、seed 和 test 边界的机器真值 |
| [`HARD_CONDITION_EXPERIMENT.md`](HARD_CONDITION_EXPERIMENT.md) | M1 实验合同与白话解释 |
| [`docs/DECISIONS.md`](../../docs/DECISIONS.md) | 已接受的重要方法、预算或流程变更 |

冲突时，已接受的 decision 和机器合同高于本流程。流程细节可以随 train/validation 结果调整，但不能藉此绕过重新冻结或偷看 test。

## 当前指针

- 当前阶段：**v5 S2 已选定 1000 steps；执行 10-group 同预算五 seed 数据量锚点**。
- 最近有效证据：v5 S2 的 arrays/manifest/report 已验收并导入 `results/`；1000−300 的 paired-group 95% CI 为 `[+0.008750,+0.045000]`，按预登记规则选择 1000。完整数字与 provenance 见 `EXECUTE.md` LOG-032。
- 已完成：同一份 40-group v4 arrays 确定性截取 10/40 groups，运行 scorer steps {60,300,1000} × seed 7。40-group 全 train 上，static preflight 对 2,552/2,552 个 executor-illegal 候选全部静态拒绝、合法误拒 0；过滤后 target-only 均匀并列期望由 0.7729 升至 0.9698，assembled oracle accuracy 由 0.7438 升至 0.9525，其 exact-ambiguity capped 读数由 0.7275 升至 0.9275。D-038 已接受把同一只读预检变成 A–E 共享 mask；旧 v4 过滤数字仍只作采纳依据，不冒充 v5 方法成绩。
- scorer 分支：40-group inner-dev 的未过滤/过滤后 teacher accuracy 在 steps 60/300/1000 分别为 0.0500/0.5688/0.5031 与 0.0625/0.7469/0.7094。1000 steps 虽将 held-out BCE 从 0.1016 降到 0.0744，候选排序却低于 300 steps；共同 group 1 在 10/40 groups、300/1000 steps 过滤后均为 0.875，也没有显示扩大到 S3 的明确数据收益。因此 300 steps 只是当前单 seed 候选，尚未固定。
- 当前分支：D-038 已接受，dataset version 为 `m1-paired-latent-worlds-v5-shared-static-preflight`；服务器全测、v5 40-group train arrays、S1、S2 五 seed 比较与两个 report 导出均已通过。v5 尚无与已选 1000 steps 同预算的 10-group 读数，不能把 S1 的 10-group/60-step 与 40-group/1000-step 混成数据量效应；因此下一步只跑 10 groups × 1000 steps × seeds `{7,19,31,43,59}`，不修改 scorer loss，不读取 validation/test。
- 数据量锚点判据（运行前固定）：只在 10-group 固定留出的共同 paired group 1 上，逐 seed 计算 `40 groups − 10 groups` 的 candidate-ranking accuracy。若五 seed 中至少 4 个严格为正，且五 seed 均值 `>= 0.025`（该 group 的 40 online decisions 中至少一个平均决策），才称“有明确继续增大 train diversity 的方向性信号”并进入 S3；否则 S3 不触发、进入 S4 预冻结审计。该锚点只有一个独立 group，故不报虚假的 CI、不重新选择 1000 steps、也不单独支持性能结论。
- 预登记方向：共享 mask 主要移除旧 E 会选而 A–D 已由执行信息避开的静态非法候选，因此预期 v5 的 `A_vs_E` 单步与 causal margin 相对 v3/v4 历史读数缩小，触发主对比 stop rule 的概率上升；若 margin 不缩小或仍通过门槛，才是更强证据。该方向在运行前固定，结果出来后不得把“缩小”或“不缩小”任一方向改写成预先支持 CTL。
- scorer 选择规则：共享 mask 后的 inner-dev candidate-ranking accuracy 是主选择量；同一 paired group、同一 seed 的 1000−300 先配对，再在每个 group 内对五个登记 seed 求平均，最后对 8 个 group 差值用固定 seed=260906 做 10,000 次单层 paired-group bootstrap，取 95% percentile CI。只有 CI 下界大于 0 才选 1000，否则选计算更省的 300；不得把 5×8 格子当成 40 个独立样本。总体/判别性 BCE 与 reference ranking margin 只解释目标是否失配，不按 BCE 单独选预算。若多 seed 复现“总体 BCE 改善但判别性 BCE、margin 或排序下降”，另立 decision 后才可测试 future-derived listwise loss，不得直接用全量 reference index 监督。
- BCE 分解判据：`ranking_relevant_bce` 是 loss-mismatch 的主 BCE 诊断，因为它直接筛出会改变 oracle mismatch 贡献、因而可能改变候选能量排序的位置；`target_discriminative_bce` 是次级解释量，只回答同一坐标在准入候选间是否同时出现真/假。两者不必是包含关系；发生冲突时，预算仍只按 candidate-ranking accuracy 的预登记置信区间选择，是否改 loss 以 ranking-relevant BCE、reference margin 与实际排序的多 seed 共变为主，且必须另立 decision。
- 边界：`test_access=false`、`validation_arrays_read=false`、`validation_trial_consumed=false`；本轮不训练 student、不校准 gate、不跑 causal，不进入 PNO/M2 或全局 reconciliation。

## 总流程

```text
S0 工程上限与校准闭环（已完成）
  ↓
S1 E/target/scorer 诊断闭环（已完成）
  ↓
S2 scorer 优化 × train 规模二维曲线（seed 7 已完成）
  ↓
S2 共享 static preflight 已接受；v5 1000-step 预算已选，10-group 同预算锚点（当前）
  ↓
S3 更大 train 规模交互确认（S2 显示需要时）
  ↓
S4 正式规模/能量/分母预冻结审计
  ↓
S5 train/validation 正式规模预演
  ↓
S6 重新冻结 + 一次性 formal test
  ↓
S7 M1 成功 / no-go / 不确定收口
```

## 阶段大纲与转向条件

| 阶段 | 要回答的问题 | 初始执行细节 | 离开该阶段前必须有的输出 |
|---|---|---|---|
| S0 ✓ | 指标、恢复路径和 calibration 分母是否成立 | 10/4 groups、seed 7、60 updates 的 smoke | observable final active=1、恢复一步；calibration/report/recovery=40/120/8；干净 provenance |
| S1（v4/v5 ✓） | E 低是 target、能量组装、优化还是泛化问题 | 10-group train arrays 按 SHA-256 留出完整 inner-dev group；scorer=60、seed=7；不读 validation | v5 shared-mask 不变量、target/assembly 与 scorer 接线已复核；结果见 `EXECUTE.md` LOG-031 |
| S2（v4 seed 7 ✓；v5 ✓，锚点待跑） | E 是优化不足、数据不足还是两者交互；逐关系 BCE 是否与候选排序失配 | D-038 后先以 10 groups/60 steps/seed 7 重跑 S1；再在同一 40-group v5 train arrays 上跑 steps {300,1000} × seeds {7,19,31,43,59}；已选 1000 后，补 10 groups × 1000 × 五 seed 的同预算共同-group 锚点；只用 train/inner-dev | shared-mask 不变量、v5 S1 与 300/1000 五 seed 完整；按 paired-group CI 规则已选择唯一 scorer budget=1000；锚点满足预登记方向判据才进入 S3，不据 BCE 单独改 loss |
| S3 | 40 groups 后是否仍明确受数据多样性限制 | 仅在 S2 的 10→40 同预算锚点满足预登记方向判据后，在一个更大 train-group 点上复扫 S2 的两个 scorer steps，而不是顺序固定旧最优；仍只用 train/inner-dev | 确认最优 steps 是否随数据规模改变，并判定数据曲线继续上升或已经饱和；不得同时改容量或 target |
| S4 | 正式 run 的分母、能量和终止规则是否唯一 | 解决 `groups_per_family` 名称与“每 family 最低决策实例数”的歧义；核查 now/collateral；报 A 的 10×/1× teacher 消融 | 唯一 train/validation/test paired-group 总数、每 family 最低 support、固定训练步数/门控选择法、不确定结果处理规则 |
| S5 | 锁定设置在足量 train/validation 上是否值得进入 test | 生成满足 C00–C11 support 的 train 和与已查看 4 groups 不重叠的新 validation confirmation；5 seeds；10% labels 主设置；完整 20-step causal 和 10,000 paired bootstrap | coverage/invariant/provenance 全通过；calibration 选唯一共享 gate；新的 report 半区仅报一次；没有触发明确 stop rule |
| S6 | 封存后的未见数据是否支持 CTL 主张 | 记录 protocol/code/data/hyperparameter hash，单独人工解封 test；test 不选阈值、checkpoint 或方法 | 5 seeds 完整 A–F causal 结果、逐例指标、paired CI、所有失败和完整 provenance |
| S7 | M1 是否成功且可以结束 | 严格按下方终止规则 | 唯一 pass/no-go/inconclusive 结论；更新 EXECUTE/DECISIONS/claim ledger；不再调 M1 |

## S1 诊断分支

target-only oracle（只看目标的上限）不加 penalty、不标准化，直接比较每个候选声称与真实 future 的 mismatch。它输出正确候选是否在最小集合、是否唯一最小、并列集合大小和均匀打破并列时的期望准确率。例如 3 个 RELINK 都得到最小 mismatch 时，coverage 可以是 100%，但期望准确率只有 1/3。它不是可部署的 E，也不允许靠候选顺序冒充唯一判断。

| 诊断组合 | 结论 | 后续分支 |
|---|---|---|
| target-only 高，assembled oracle 高，E train 低 | target 和组装有信息，scorer 没优化好 | 进 S2，不改 target |
| target-only 高，assembled oracle 低 | 标准化/权重/penalty 破坏目标信号 | 只在 train/inner-dev 内诊断组装；若改公式须新 decision 和重新冻结 |
| target-only 低，或最小集合长期很大 | target 缺关系或只能缩小范围 | 在 test 前重构 target，升 dataset version，重跑 S1 |
| E fitting 高、inner-dev 低 | 组间泛化问题 | 进 S3，优先数据多样性/正则化诊断 |
| relation oracle illegal rate 高 | target/penalty 偏爱不可执行声明 | 在不执行候选的 E 边界内检查声明约束；不偷用 executor illegal mask |

transaction static preflight（事务静态预检）已由 D-038 接受为 A–E 共享 online admissibility mask：它读取 immutable prior world、候选程序、在线证据和 protected IDs，输出“已能静态拒绝”或“预检通过但执行未知”。固定 K=16 槽位和失败审计仍完整，拒绝项只在训练归一化、softmax、calibration 和 commit selection 前不可选。例如候选直接触碰 protected node 会被拒绝，但需要应用操作后才暴露的坏引用仍可能通过。它不生成 post-edit world、不等于最终 executor legality；A/D/F 的执行后 illegal 能量和 `remaining_executor_illegal_candidates` 仍必须保留。

admitted-uniform random accuracy（准入集合均匀随机准确率）解决 mask 后仍把随机地板写成固定 `1/16` 的问题。输入是每一行的 16 个预检布尔值，输出是逐行 `1/有效候选数` 再求平均；例如两行分别剩 2 和 4 个候选时，随机地板是 `(1/2+1/4)/2=0.375`，不是 `1/平均候选数`。它不等于模型准确率，也不使用 reference 或 executor legality。

residual decision-impact upper bound（残余非法决策影响上界）解决只报残余候选总数却不知道最多影响多少决策的问题。输入是“预检通过但执行后非法”的行列 mask，输出是至少含一个此类候选的决策行比例；例如 100 行中有 3 行含残余非法项，则 executor illegal 通道最多改变 3% 的 teacher 决策。它是严格上界，不等于真的改变了 3%，也不为没有 post-edit world 的失败候选虚构 future 能量。

E 的 scorer 与 A–E 的 online student 使用两个独立预算：student updates 仍对 A–E 完全一致，E 额外 scorer updates 单列并报告。60→600 的非仓库 scratch probe 只作为提出二维曲线的线索，不作为选择正式设置的证据；scorer 选择只看上述可追溯 train/inner-dev 曲线。held-out BCE 早停目前仅是候选方案，未登记 patience、最大步数和 checkpoint 规则前不启用。

validation trial 预算单独保留给 student/commit 开发：已查看的历史 smoke 保守计 1 次，共享 student updates 最多 2 个新点，C auxiliary weight 最多 3 个登记点，总计不超过 6。train/inner-dev scorer 曲线不计作 validation trial，但每个配置仍必须在报告中列出，不能无限搜索。LOG-022 已经查看过的 4-group report 半区不再被称为 S5 首次确认；S4 必须登记一个不重叠的 validation confirmation group range。

## 允许调整与必须重新冻结的边界

| 类型 | 处理方式 |
|---|---|
| 可在当前阶段调整 | 诊断输出字段、CPU/GPU 线程、worker 数、不改数据的批处理方式、上表的开发曲线点；调整前先改本阶段计划，结果写 EXECUTE |
| 只能在 trial 预算内选 | checkpoint、learning rate、C auxiliary weight、共享 student updates、E scorer 的已声明容量/正则化；只用 train/inner-dev/calibration，累计不超过每方法 6 个 validation trials |
| 必须新 decision + 新 dataset/protocol hash + 从 S1 重跑 | 启用 static-preflight 候选过滤、E target 定义、能量标准化/权重、recovery 触发/范围、K、候选生成器、H 主值、online feature 语义、主指标或效应门槛 |
| test 解封后禁止调整 | 所有会影响方法、数据、阈值、checkpoint、排除项或报告口径的内容；test 只产生最终结论 |

白话：“细节可调”解决开发中不可能一次猜对训练成本的问题。输入是当前阶段未触及 test 的诊断，输出是下一个事先记录的设置。例如 300 updates 仍上升时可按计划跑 1000；看到 test 不理想后再改权重不可以。它不等于随时移动门槛或无限加数据。

## M1 成功与结束定义

单步准确率 90%、relation oracle 高或 observable oracle=1 都不是 M1 成功。M1 只在重新冻结后的 formal test 上判定。

**成功（go）：** A–C 和 A–E 两个主对比均必须同时满足：

- final active-graph correctness 差值的 95% CI 下界 `>= +0.03`；
- contamination reduction 的 95% CI 下界 `>= 2.0 / 100 decisions`；
- false-birth 差值的 CI 下界 `>= -1.0 / 100`；
- collateral 差值的 CI 下界 `>= -0.5 / 100`；
- A–C/A–E 交并检验经 Holm–Bonferroni 校正后 `p <= 0.05`；
- executor invariant violation 为 0；candidate coverage@16 总体 `>=98%`、每 family `>=95%`；
- 5 个登记 seed、10,000 次 paired-group bootstrap、失败 run 和 provenance 都完整。

**明确 no-go：** 任一主对比的 CI 上界仍低于已登记的主效应门槛，或 coverage/invariant/safety 门失败且不属于 test 前已证明的独立工程故障。M1 以负结果结束，不用 PNO、第二任务或更大模型救结果，不进入 M2。

**不确定：** CI 同时覆盖“无效”和“最小有意义效应”。这不等于成功。S4 必须在 test 解封前事先选定“最多一次固定扩样”或“固定样本后以 inconclusive/no-go 收口”；未预先写明时，test 后不得自行扩样。

白话：M1 成功解决“CTL 这台修订发动机是否值得装进完整系统”的问题。输入是封存后从未用于选方法的 test sequence，输出是 A 相对 C/E 的长期当前世界正确性、污染和安全差值。例如 A 单步只有 85%，但 20 步后比 C/E 多 3 个百分点且每 100 步少 2 个错误开放事实，才可能通过。它不等于训练准确率高、oracle 可达或一个对照输了。

## 每阶段如何更新本流程

1. 跑之前：在“当前指针”写明阶段、本次设置和允许的分支；不得只留在对话里。
2. 跑之后：数字、失败和 provenance 只追加到 `EXECUTE.md`，本文件只移动阶段指针并记录下一分支。
3. 若只调开发细节：改本文件对应阶段；若改方法、数据语义、预算或终止规则：同时追加 `docs/DECISIONS.md` 并更新合同。
4. 只有当前阶段的必需输出齐全才能勾选并进入下一阶段。

## 最终交付清单

- 冻结 config、protocol hash、code/source-tree hash、train/validation/test manifests 与 arrays digest；
- 5 seeds 的模型/checkpoint、预算、wall-clock、峰值显存与 p95 latency；
- 逐候选能量、逐例指标、candidate/teacher/amortization/rollout error 分解；
- A–C/A–E paired CI、Holm 校正、safety、coverage、invariant 与恢复诊断；
- 完整失败 run、排除原因和 provenance；
- `EXECUTE.md` 最终 LOG、`docs/DECISIONS.md` 终止决定与 claim ledger 状态。
