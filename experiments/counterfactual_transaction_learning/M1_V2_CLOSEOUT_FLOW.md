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

- 当前阶段：**S2 scorer 优化 × train 规模二维曲线**。
- 最近有效证据：[`results/m1-v2-s1-innerdev-7518f99-20260906T120940Z.json`](../../results/m1-v2-s1-innerdev-7518f99-20260906T120940Z.json)，详见 `EXECUTE.md` LOG-026。
- S1 分支结论：10-group train 只留出 1 个 inner-dev paired group。target-only 将 K=16 缩到至多 2 个，均匀打破并列的期望准确率为 0.600；同组装 relation oracle 为 0.575，明显高于 E scorer 的 0.050，但 oracle 的非法候选选择率为 0.375。故当前不改 relation target，进入 S2 检验优化量与数据量交互；同时把 legality/assembly 缺口保留为独立阻塞项，不能把 E 的全部失败只归因于训练步数。
- 正在执行：按 D-037 先审计只读 static preflight，再在干净提交上生成一份 40-group train arrays；同一文件确定性截取前 10/40 groups，运行 scorer steps {60,300,1000} × train groups {10,40}、seed 7 的 2×3。target-only/assembled oracle 在全部 selected train online rows 上报告 aggregate 与逐 group 值；scorer 仍按既定 SHA-256 规则分 fitting/inner-dev，并以共同 group 1 作直接规模对照、以 40-group 的 8 个 held-out groups 观察泛化。该阶段不读 validation/report、不训练 student、不校准 gate、不跑 causal。
- 离开 S2 的条件：先检查 static preflight 对 executor illegal 的召回、合法误拒和过滤前后 oracle，但不得把过滤上界当作 E 成绩；再判断 scorer 是否接近未过滤 assembled oracle并区分 steps、groups 及其交互。若静态预检高召回且零/近零误拒，先提出是否共享启用的新 decision；若 40 groups 仍随数据明确改善则进入 S3；若 scorer 已贴近低 oracle 则回到 test 前的 assembly/声明约束修订。不得用单个 inner-dev group 的 57.5% 或旧 validation report 的 80.83% 单独选方法。
- 边界：`test_access=false`；不生成或读取 test，不进入 PNO/M2，不实现全局 reconciliation。

## 总流程

```text
S0 工程上限与校准闭环（已完成）
  ↓
S1 E/target/scorer 诊断闭环（已完成）
  ↓
S2 scorer 优化 × train 规模二维曲线（当前）
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
| S1 ✓ | E 低是 target、能量组装、优化还是泛化问题 | 10-group train arrays 按 SHA-256 留出完整 inner-dev group；scorer=60、seed=7；不读 validation | target-only expected=0.600；assembled oracle=0.575、illegal=0.375；E fitting/inner-dev teacher 均为 0.050；目标有信息，但单 group 不足以分开优化、组间波动和 assembly legality |
| S2 | E 是优化不足、数据不足还是两者交互；非法并列能否被只读预检识别 | scorer-only；同一 40-group arrays 确定性截取前 10/40 groups，steps {60,300,1000} × total train groups {10,40} 的 2×3；先 seed 7，再对选定点补齐 5 seeds；不读 validation | 全-train 与逐 group 的 target/assembly；static-preflight 非法召回、合法误拒、failure/template 分解及过滤上界；E fitting/inner-dev BCE、teacher accuracy、非法选择与成本曲线；固定 scorer steps 或提出已登记早停规则 |
| S3 | 40 groups 后是否仍明确受数据多样性限制 | 若 10→40 仍明确改善，在一个更大 train-group 点上复扫 S2 的两个 scorer steps，而不是顺序固定旧最优；仍只用 train/inner-dev | 确认最优 steps 是否随数据规模改变，并判定数据曲线继续上升或已经饱和；不得同时改容量或 target |
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

transaction static preflight（事务静态预检）当前只是 S2 诊断：它读取 immutable prior world、候选程序、在线证据和 protected IDs，输出“已能静态拒绝”或“预检通过但执行未知”。例如候选直接触碰 protected node 会被拒绝，但需要应用操作后才暴露的坏引用仍可能通过。它不生成 post-edit world、不等于最终 executor legality，也尚未进入 A–E 的选择路径；过滤后的 oracle 只是决定是否值得另立方法决策的上界。

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
