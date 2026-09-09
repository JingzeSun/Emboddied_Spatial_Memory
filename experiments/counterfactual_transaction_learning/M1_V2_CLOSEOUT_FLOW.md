# M1 收口执行流程（v7 范围修复重建）

本文件沿用 D-035 批准的固定文件名，是 M1 从当前修正版本 pretest 走到结束的唯一流程大纲。它解决“下一步做什么、看到什么结果后走哪条分支”的问题；输入是已登记的 M1 合同和每阶段结果，输出是下一个有界任务。例如 E 的 target-only oracle 高、但 scorer train accuracy 低时，下一步是优化诊断，不是改 target。它不是实验结果日志、不是新的方法合同，也不代替机器可读配置。

## 文件职责与优先级

| 文件 | 只负责什么 |
|---|---|
| 本文件 | 阶段顺序、分支条件、当前指针、允许调整的开发细节 |
| [`EXECUTE.md`](../../EXECUTE.md) | 已经发生的 run、失败、结果与当前看板；不再承担完整流程 |
| [`configs/m1_hard_condition_v7.json`](../../configs/m1_hard_condition_v7.json) + [`m1_scope_rebuild_plan.json`](../../configs/m1_scope_rebuild_plan.json) | 修正版本的生成合同与重建前固定规则；旧 v6 hard/overlay/post-probe registration 保留作历史来源，新组合登记待修正 probe 后接线，test 未解封 |
| [`HARD_CONDITION_EXPERIMENT.md`](HARD_CONDITION_EXPERIMENT.md) | M1 实验合同与白话解释 |
| [`docs/DECISIONS.md`](../../docs/DECISIONS.md) | 已接受的重要方法、预算或流程变更 |

冲突时，已接受的 decision 和机器合同高于本流程。流程细节可以随 train/validation 结果调整，但不能藉此绕过重新冻结或偷看 test。

## 当前指针

- 当前阶段：**修正 train 已验收；严格错误分支检查 FAIL（LOG-078）。当前 D-053 显式不可用槽位诊断已实现，先按 `bash ops/m1_candidate_availability.sh test`、`check`、`export` 完成服务器验证；复用原 16 组审计，不重生成。正式默认模式仍严格，诊断 PASS 不放行预算；先审查兼容性/完整轨迹结果并确定正式规则，再回到下方固定 probe 与其他选参前条件。**
- 历史 S2 证据：v5 S2 的 arrays/manifest/report 已验收；1000−300 的 paired-group 95% CI 为 `[+0.008750,+0.045000]`，按预登记规则选择 1000。10-group 同预算锚点中共同 group 1 的 40−10 平均差为 `+0.005000`、仅 `1/5` seed 严格为正，未达 S3 触发条件。完整数字与 provenance 见 `EXECUTE.md` LOG-032/033。
- 已完成：同一份 40-group v4 arrays 确定性截取 10/40 groups，运行 scorer steps {60,300,1000} × seed 7。40-group 全 train 上，static preflight 对 2,552/2,552 个 executor-illegal 候选全部静态拒绝、合法误拒 0；过滤后 target-only 均匀并列期望由 0.7729 升至 0.9698，assembled oracle accuracy 由 0.7438 升至 0.9525，其 exact-ambiguity capped 读数由 0.7275 升至 0.9275。D-038 已接受把同一只读预检变成 A–E 共享 mask；旧 v4 过滤数字仍只作采纳依据，不冒充 v5 方法成绩。
- scorer 分支：40-group inner-dev 的未过滤/过滤后 teacher accuracy 在 steps 60/300/1000 分别为 0.0500/0.5688/0.5031 与 0.0625/0.7469/0.7094。1000 steps 虽将 held-out BCE 从 0.1016 降到 0.0744，候选排序却低于 300 steps；共同 group 1 在 10/40 groups、300/1000 steps 过滤后均为 0.875，也没有显示扩大到 S3 的明确数据收益。因此 300 steps 只是当前单 seed 候选，尚未固定。
- 历史 v6 分支（不作为修正版执行指令）：D-043 提交 `53539ce` 已在干净服务器运行 191 项测试，12-group train-only health 亦以完全相同的历史 digest 通过。1000-group train 随后用 16 workers 在 1001.0 秒内生成 40,000 rows，teacher agreement=`1.0`、health gate PASS，arrays digest=`e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168`。运行时报告已导出为 `results/m1_v6_d043_runtime_profile.json`：固定 300-step 实测外推原 12 格 Set Transformer/MLP 分别约 3.128/1.239 小时、峰值约 2.60/1.99 GB，合计约 4.367 小时；D-046 对同一逐方法实测路径保守加入每臂 10 条 C 附加路径后约为 3.640/1.395、合计 5.036 小时，仍只是 planning estimate，没有科学指标。D-044–D-047 已把 exact/graded 一次切换、节点安全、完整 collateral、F gate、AUC `40/80`、test 检验力规则和 H=1 teacher 主文机制对照冻结到专用 train-only overlay；当前不读取 validation/test、不直接启动完整网格。
- 成本边界：修正版 train/validation 为 1000/200 个总混合 paired groups，test N 按 D-051 一次性六格公式确定且不低于 1350，不乘 12；旧组合登记的 1350 不直接冒充修正版最终 N；原 test=200 的全 split 成本外推仅是历史估算，不能覆盖新规模。运行成本与已生成数据见 EXECUTE。完整预算网格仍按 D-046 登记，未获新结果前不扩网格；test 仅在 S6 完成入口接线、复核规模和重新冻结后生成。
- 数据量锚点判据（运行前固定）：只在 10-group 固定留出的共同 paired group 1 上，逐 seed 计算 `40 groups − 10 groups` 的 candidate-ranking accuracy。若五 seed 中至少 4 个严格为正，且五 seed 均值 `>= 0.025`（该 group 的 40 online decisions 中至少一个平均决策），才称“有明确继续增大 train diversity 的方向性信号”并进入 S3；否则 S3 不触发、进入 S4 预冻结审计。该锚点只有一个独立 group，故不报虚假的 CI、不重新选择 1000 steps、也不单独支持性能结论。
- 预登记方向：共享 mask 主要移除旧 E 会选而 A–D 已由执行信息避开的静态非法候选，因此预期 v5 的 `A_vs_E` 单步与 causal margin 相对 v3/v4 历史读数缩小，触发主对比 stop rule 的概率上升；若 margin 不缩小或仍通过门槛，才是更强证据。该方向在运行前固定，结果出来后不得把“缩小”或“不缩小”任一方向改写成预先支持 CTL。
- scorer 选择规则：共享 mask 后的 inner-dev candidate-ranking accuracy 是主选择量；同一 paired group、同一 seed 的 1000−300 先配对，再在每个 group 内对五个登记 seed 求平均，最后对 8 个 group 差值用固定 seed=260906 做 10,000 次单层 paired-group bootstrap，取 95% percentile CI。只有 CI 下界大于 0 才选 1000，否则选计算更省的 300；不得把 5×8 格子当成 40 个独立样本。总体/判别性 BCE 与 reference ranking margin 只解释目标是否失配，不按 BCE 单独选预算。若多 seed 复现“总体 BCE 改善但判别性 BCE、margin 或排序下降”，另立 decision 后才可测试 future-derived listwise loss，不得直接用全量 reference index 监督。
- BCE 分解判据：`ranking_relevant_bce` 是 loss-mismatch 的主 BCE 诊断，因为它直接筛出会改变 oracle mismatch 贡献、因而可能改变候选能量排序的位置；`target_discriminative_bce` 是次级解释量，只回答同一坐标在准入候选间是否同时出现真/假。两者不必是包含关系；发生冲突时，预算仍只按 candidate-ranking accuracy 的预登记置信区间选择，是否改 loss 以 ranking-relevant BCE、reference margin 与实际排序的多 seed 共变为主，且必须另立 decision。
- D-043/D-046 预算边界：每种架构先选 E scorer，再让 A–E 在 C weight=1 锚点上从完全相同的 12 格中以同一 reference accuracy 各自选 `(lr,updates)`；精确平手取更少 updates、再取更小 lr。随后只在 C 已冻结的计算格上复用 weight=1 并补跑 0.1/10 两条路径，以相同 group-first/五 seed 聚合选最高，精确平手优先 1、再取较小权重；不做 36 格联合搜索。10000 触顶照实接受、不扩格；共享格与 A/E 交叉格只作算力敏感性诊断。`test_access=false`、`validation_arrays_read=false`、`validation_trial_consumed=false`；不校准 gate、不跑 causal，不进入 PNO/M2 或全局 reconciliation。
- 历史 D-044–D-047 endpoint 边界（D-051 已关闭重新选择 endpoint；当前按下方总流程）：只在 Set Transformer 主臂以固定 `(lr=0.0006, updates=3000, C weight=1)` 跑 A/C/E、五 seed 和 F；所有方法固定 `(commit_probability=0, margin_threshold=0)`，不再用两折单步代理选择 shared raw-softmax gate。F 任一 semantic exact/graded、open-memory graded、open-fact AUC 或 node integrity 失败立即停止。semantic exact 的 A−C/A−E 均有至少 7 个非零 paired-group 差且 SD>0 时保留 exact；否则仅在 active graded 两对照均满足时一次切换，开关禁止读取赢家、效应方向和大小；open-memory graded 与 `open_fact_error_auc_per_100_decisions` 是固定 co-primary，也必须对两对照非退化。AUC minimum/planning 固定为 20 步持续等价的 `40/80`（8/16 个错误事实×决策步暴露）；probe 观察到的均值、效应或 SD 只能报告，不能回调该门。test N 取 selected semantic/open-memory/open-fact AUC × 两对照的 paired-SD 功效需求最大值。机制–指标矩阵另要求 C10 的相反 BIND/NOOP 被 evidence-support 通道看见、C11 指定对照被 unrelated collateral 看见；C10 单步仍按信息上限预期约 0.5，不宣称模型能预测未见未来。probe 还必须在同一 201 个完整 train/inner-dev groups 上，以完全相同候选、当前证据、外生轨迹和非 future 能量重算 H=1 teacher，主文报告 H3-vs-H1 的分布差异；它不参与 endpoint switch、test N 或成败门。validation/test 仍封存。

## 历史指标层审计处置（D-045/D-046，后续以 D-051 为准）

依据：[2026-09-07 指标层审计](../../docs/reviews/2026-09-07_metric_layer_audit.md)。该文件及后续 Claude 反馈是外部只读复核，不是 ground truth；以下事项已由 D-045/D-046 逐项裁定并完成本地接线，只有服务器 full test 成功后才算通过工程验证。

1. **污染构念对齐（已接线）**：`memory_contamination` 已降为兼容 alias；规范量改为 extra/missing open-fact error，并把额外事实拆成 new-write/stale-retention。M1 明确不声称原始 Dynamic Contamination Rate。
2. **终点与时间负担（已接线）**：terminal burden 与 AUC burden 已分开登记；正式长期负担 co-primary 是 extra+missing 的 `open_fact_error_auc_per_100_decisions`，并已纳入 test-N 功效规划。
3. **指标命名清理（已接线）**：history/post、contamination 与 unresolved 兼容 alias 已从正式 endpoint summary 排除；exact 是首选二值语义终点，graded 只作一次性同构 fallback。
4. **统计/门修正（已接线）**：空 recovery 分母返回 `None` 并报告 eligible denominator；`false_birth_growth` 使用集合差；shared gate 固定为 `(0,0)` always-attempt，不再用一步 proxy 选择 20-step gate。
5. **minimal-world-change（已裁定）**：edit/growth posterior influence 继续原样报告，不事后调权；论文只称其为注册 prior/regularizer，不称其为已验证主机制。
6. **范围边界（已裁定）**：M1 只验证 CPMT/CTL 的受控 persistent-world revision；独立 dynamic/transient memory、decay、static retention、reappearance/viewpoint consistency 留给 M2/M3。

处置结果：规范名改为 extra/missing open-fact error，并拆 new-write/stale-retention；terminal 与 AUC 并列，`open_fact_error_auc_per_100_decisions` 成为固定 co-primary 且纳入 test-N；D-046 将其 effect 门冻结为 20 步持续等价 `40/80`，并禁止按 probe 尺度回调。正式主表排除 history/post、contamination 和 unresolved 兼容别名；空 recovery 为 `null`、false-birth 用集合差；minimal-world-change 只称注册正则；M1 不声称原始 DCR 或完整 static/dynamic 双记忆。D-044 的 shared cross-fitted gate 被固定 `(0,0)` 无选择 gate supersede，且 D-046 分开 attempt、实际 commit 与 executor quarantine；C weight 改为 train/inner-dev 顺序选择，validation 只确认。完成顺序现为：**服务器 full test → 固定 endpoint probe → 再决定是否进入完整预算网格**。A1/A2/A4 的 evidence/node/collateral 覆盖修复保持，不重复返工；C10 继续按信息上限约 0.5 解释，不宣称能预测未见未来。

## 历史主张、执行与轨迹边界补正（D-047）

D-047 不改变 A/C/E、数据、候选、executor、co-primary 或通过门，只消除三种容易伤害论文可信度的过度表述。第一，claim 改为“真实执行候选世界后，以 current/随后实际观测的 future evidence 为主要评分信号”，edit/growth 只称预登记正则，不再与 current/future 并列成已验证机制。第二，online 网络只评分且不读 `post_graph`/future，D-048 进一步校正为：共享生成器和评测器仍展开候选，只有选中合法世界持久化；M2 单次执行部署路径尚未实现。第三，M1 的 event/observation/pose/revisit schedule 是 seed 固定、模型运行前预生成的外生输入，故 M1 不评测 active navigation 或 action policy。

teacher agreement=`1.0` 继续按 fixture 事实披露，M1 只声称传播软 executable hindsight distribution，不声称普遍重写 hard labels。为避免这句话沦为免责说明，endpoint probe 必须在同一 201 个完整 train/inner-dev groups 上增加 H3-vs-H1 teacher horizon contrast：只截短执行后 future trace，其余输入与能量全部固定；agreement、top-1、entropy、TV、KL、argmax change 和 reference-probability shift 总体/逐 family 报告，并进入论文主文。它是机制解释，不是重训 H=1 student、不是新方法/co-primary，也不改变 A-vs-C/E 成败规则；弱或零结果必须披露并收窄“多步 future 起作用”的叙述，不能据此调参。

## M1 后续改进候选（单一记录处，不是当前调门清单）

以下项目集中保留在本流程文件，不另建 TODO/交接文档。它们只能用于解释当前 M1、设计一个明确的新协议版本或在 M1 go 后规划 M2/M3；不得因为 endpoint probe、validation 或 test 数字“不理想”就回改 D-046、扩当前网格或重跑同一 confirmatory test。若 formal M1 no-go，仍执行既定 stop rule：报告负结果，不靠这些项目扩模型或进入 M2。

- 轨迹负担可增加 survival profile、首次错误到修复的持续时长分布和按 extra/missing/new-write/stale 分层的描述图，帮助解释 AUC 由“少量长错”还是“大量短错”产生；它们不替代 `40` 的共同绝对门，也不新增 co-primary。
- 若未来另开全新协议，可研究半程持续锚点、按 reference graph size 标准化或相对 baseline 的 AUC estimand；必须在新数据/新 hash 和任何新 probe 前重新论证，不能用当前观测尺度选择。
- C 的 36 格联合 `(lr,updates,aux)` 搜索只保留为未来资源敏感性方案；当前 M1 固定顺序搜索。若未来使用，必须给其他方法的选择机会与算力公平性单独论证，不能在当前 C 结果不佳时临时启用。
- confidence calibration、risk–coverage 与允许合法低置信 abstention 可作为部署诊断或新协议研究；当前 M1 的主效果固定 `(0,0)` always-attempt，并只把 confidence 曲线作非选择性报告。
- minimal-world-change 的 edit/growth 权重效应可在当前 M1 结论之外做预登记消融；当前权重不因 posterior influence 小而上调，也不把该项宣传成已验证主机制。
- 独立 Static Structural Memory 与 Dynamic/Transient Memory、decay、dynamic-to-static contamination、static retention、reappearance 和 viewpoint consistency 继续属于 M2/M3 planned 范围；只有 M1 go 后才能按既定顺序实现。

白话：这份候选清单解决“当前实验跑完后，哪些科学问题值得继续追、又不会反过来污染已经冻结的考试规则”。输入是当前合同已知的构念边界和将来正式结果，输出是下一项独立研究的备选设计。例如 AUC 很高时可以画错误持续时长分布解释原因，但不能把 40 改成 20 让同一结果过门。它不等于补救列表、不授权看结果调参，也不覆盖 M1 失败即停止扩模型的规则。

## 总流程

S0–S3 保留原版本开发历史；下面 S4 起按 D-051 修正版本执行。旧 v8 数据、旧预算和模型只作历史证据，不作为修正版放行依据。

```text
S0 工程上限与校准闭环（历史完成）
  ↓
S1 E/target/scorer 诊断闭环（历史完成）
  ↓
S2 scorer 优化与数据规模诊断、共享 static preflight（历史完成）
  ↓
S3 更大 train 规模交互确认（未触发，跳过）
  ↓
S4 修正版本的选参前检查与预算选择
  ├─ 修正 1000 组 train 生成与健康验收
  ├─ 固定 train 错误分支完整 20 步检查、失败现场与导出审查 ← 当前
  ├─ 固定 anchor probe：F integrity、固定三项终点非退化、按 D-051 机械确定 N
  ├─ 预算并行接线与等价检查、fit/inner-dev 同口径诊断
  ├─ train-only 小样本贯通实际模型保存/加载、20 步评测、配对汇总及导出
  └─ 上述全部通过，才运行两臂完整原预算网格并验收
  ↓
S5 锁定配置、全 train 重训；独立 200 组 validation 一次性确认
  ↓
S6 重新冻结、单独解封 + 一次性 formal test
  ↓
S7 M1 成功 / no-go / 不确定收口
```

### 完整选参前的放行条件

当前先检查，不启动完整预算。检查失败时先定位工程原因；不得删除断言、换掉失败组或改效应门以求通过。以下开发工作只用 train；不提前读取或生成 validation/test。状态证据统一见 EXECUTE，未实现事项明确保留为 planned。

| 检查 | 何时做、要交付什么 | 当前实现边界 |
|---|---|---|
| 修正 train 验收 | 其余检查之前；组数、普通/recovery 行数、family 编码、digest 与来源一致 | 已有生成及验收回执，见 LOG-077；不重生成 |
| 错误分支 20 步 | 现在；固定 16 组、七条选择规则，检查 C11 范围外目标、MERGE 配对、K=16、immutable base、边序不变和失败现场 | 实际报告 FAIL，见 LOG-078；修复审查中，不能把 NOOP 完成或快照复现当工程 PASS。恢复案例由重建审计核验，不保证任意错误组合都能恢复 |
| 固定 anchor probe | 错误分支检查通过后、完整网格前；修正版 F、三项 co-primary 非退化、H3/H1 诊断及六格 SD；按既定规则登记 N | 须接入修正数据与 D-051 规则；exact 不重选，F 或非退化失败即停止；这是固定配置探针，不是完整选参 |
| 并行预算与泛化诊断 | 完整网格前；独立进程随机流/汇总等价、资源检查、同一 checkpoint 的 fit 与 inner-dev 同口径分数和差距 | planned：旧 runtime 测速不等于完整预算接线已通过；差距只作诊断，不增加选参规则 |
| 后续真实代码路径贯通 | 完整网格前；少量固定 train 数据、诊断权重，贯通保存→加载→完整 20 步→paired-group 汇总→统计→导出；同时检查复用、来源绑定和失败拒绝 | planned：必须调用后续正式 runner 的实际公共路径；单独 mock 或另写简化评测器不算通过。覆盖普通/recovery 编码、成对轨迹与分母；不报告为方法成绩 |

白话：小样本贯通检查解决“模型都训完了，才发现后续程序读不了权重或统计字段”的问题。输入是预先固定的少量 train 场景及短训诊断权重，输出是从训练到报告的完整工程证据。例如加载保存的模型，让它连续修改记忆 20 步，再检验每组两条轨迹能否进入同一统计和导出路径。它不是正式选参、不是独立泛化验证，也不保证覆盖未来所有场景；其规模和诊断设置须在运行前固定，不能根据成绩挑选。

阶段实现可在不运行服务器任务的同时准备，但实际执行必须满足前置条件；固定 probe 的结果用于按已有公式填充新登记，不用于临时改评价代码。后续 S5/S6 的公共代码、schema、配对与来源检查必须提前准备并经过上述 train-only 路径验证，最终输入、配置和 test 解封仍按阶段冻结。不能把“尚未允许运行 S6”理解为“等完整训练结束才实现 S6”。

## 阶段大纲与转向条件

| 阶段 | 要回答的问题 | 初始执行细节 | 离开该阶段前必须有的输出 |
|---|---|---|---|
| S0 ✓ | 指标、恢复路径和 calibration 分母是否成立 | 10/4 groups、seed 7、60 updates 的 smoke | observable final active=1、恢复一步；calibration/report/recovery=40/120/8；干净 provenance |
| S1（v4/v5 ✓） | E 低是 target、能量组装、优化还是泛化问题 | 10-group train arrays 按 SHA-256 留出完整 inner-dev group；scorer=60、seed=7；不读 validation | v5 shared-mask 不变量、target/assembly 与 scorer 接线已复核；结果见 `EXECUTE.md` LOG-031 |
| S2（v4 seed 7 ✓；v5 ✓） | E 是优化不足、数据不足还是两者交互；逐关系 BCE 是否与候选排序失配 | D-038 后先以 10 groups/60 steps/seed 7 重跑 S1；再在同一 40-group v5 train arrays 上跑 steps {300,1000} × seeds {7,19,31,43,59}；已选 1000 后，补 10 groups × 1000 × 五 seed 的同预算共同-group 锚点；只用 train/inner-dev | shared-mask 不变量、v5 S1 与 300/1000 五 seed 完整；按 paired-group CI 规则已选择唯一 scorer budget=1000；锚点未满足预登记方向判据，故 S3 跳过，不据 BCE 单独改 loss |
| S3 | 40 groups 后是否仍明确受数据多样性限制 | 仅在 S2 的 10→40 同预算锚点满足预登记方向判据后，在一个更大 train-group 点上复扫 S2 的两个 scorer steps，而不是顺序固定旧最优；仍只用 train/inner-dev | 确认最优 steps 是否随数据规模改变，并判定数据曲线继续上升或已经饱和；不得同时改容量或 target |
| S4 | 修正版本的工程路径、指标登记和预算是否可放行 | 先满足上方全部选参前放行条件；D-051 固定 exact/support/AUC、原安全门和 `(0,0)` gate，以修正 train 固定 anchor 核验 F/非退化，按六格 SD 及 1350 下限机械确定 N；随后两臂按 D-043/D-046 原网格及 C 顺序权重规则选参 | 工程报告、修正 probe 与组合登记、两臂完整预算报告及来源绑定全部验收；架构不择优、不重新选择 endpoint、不扩网格，validation/test 仍封存；旧成本/结果只见 EXECUTE 历史 LOG |
| S5 | 锁定设置在足量 train/validation 上是否值得进入 test | 使用满足 C00–C11 support 的 train 和与已查看 4 groups 不重叠的新 200-group validation confirmation；所有 C weight/lr/updates 与固定 `(0,0)` gate 均已冻结；5 seeds、10% labels、完整 20-step causal 和 10,000 paired bootstrap | coverage/invariant/provenance 全通过；validation 不选择任何设置、全部 200 groups 只确认一次；没有触发明确 stop rule |
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

E 的 scorer 与 A–E 的 online student 使用两个独立预算：E 额外 scorer 参数/updates 单列；A–E student 架构与 12 格搜索机会完全一致，但允许按同一 reference 指标选不同 `(lr,updates)`。60→600 的非仓库 scratch probe 只作为提出二维曲线的线索，不作为选择正式设置的证据；scorer 选择只看上述可追溯 train/inner-dev 曲线。held-out BCE 早停不启用。

D-043 已把新曲线定为两架构各自的 learning rate `{0.0002,0.0006,0.002}` × `{300,1000,3000,10000}` 前缀 checkpoints × 五 seed，并改用完整 1000-group train 的固定 inner-dev。E scorer 先按 reference candidate-ranking accuracy 选择；随后 A–E 各自按同一 reference-candidate selection accuracy 选格。最高均值胜，只有精确平手才取更小 updates、再取更小 lr；10000 胜出直接接受并标 ceiling。相同网格还输出一个 A–E 共享格和 A/E 在彼此格上的交叉读数，均不反向改变正式配置。它是有限网格而非 held-out BCE early stopping；架构身份、网格上界和选择量不随中间结果扩张。

D-046 后不再有活动 validation trial 选择预算：C auxiliary weight 与 learning rate/checkpoint 都只读 train/inner-dev，commit gate 固定 `(0,0)`；所有点必须完整报告且不得扩张。新的 200-group validation 是纯 confirmation，只能在全部设置冻结后完整运行一次并报告。LOG-022 已经查看过的 4-group report 半区仍是历史开发结果，不得并入 S5 confirmation 或用于选择。

## 允许调整与必须重新冻结的边界

| 类型 | 处理方式 |
|---|---|
| 可在当前阶段调整 | 诊断输出字段、CPU/GPU 线程、worker 数和不改数据/训练轨迹的批处理方式；结果写 EXECUTE |
| 只能按已登记规则选 | learning rate/checkpoint 只从相同 12 格用 train/inner-dev 选择；C weight 只在其已选计算格上顺序比较 `{0.1,1,10}`；validation 不选择任何设置，commit gate 固定 `(0,0)`；任何扩格须新 decision |
| 必须新 decision + 新 dataset/protocol hash + 从 S1 重跑 | 启用 static-preflight 候选过滤、E target 定义、能量标准化/权重、recovery 触发/范围、K、候选生成器、H 主值、online feature 语义、主指标或效应门槛 |
| test 解封后禁止调整 | 所有会影响方法、数据、阈值、checkpoint、排除项或报告口径的内容；test 只产生最终结论 |

白话：“细节可调”解决开发中不可能一次猜对训练成本的问题。输入是当前阶段未触及 test 的诊断，输出是下一个事先记录的设置。例如 300 updates 仍上升时可按计划跑 1000；看到 test 不理想后再改权重不可以。它不等于随时移动门槛或无限加数据。

## M1 成功与结束定义

单步准确率 90%、relation oracle 高或 observable oracle=1 都不是 M1 成功。M1 只在重新冻结后的 formal test 上判定。

**成功（go）：** A–C 和 A–E 两个主对比均必须同时满足：

- D-051 固定的 exact active-world semantic correctness（`final_active_graph_correctness`）差值的 95% CI 下界 `>= +0.03`；
- graded open-memory support correctness 差值的 95% CI 下界 `>= +0.03`；
- `open_fact_error_auc_per_100_decisions` reduction 的 95% CI 下界 `>= 40.0`；
- false-birth 差值的 CI 下界 `>= -1.0 / 100`；
- collateral 差值的 CI 下界 `>= -0.5 / 100`；
- A–C/A–E 交并检验经 Holm–Bonferroni 校正后 `p <= 0.05`；
- executor invariant violation 为 0；candidate coverage@16 总体 `>=98%`、每 family `>=95%`；
- 5 个登记 seed、10,000 次 paired-group bootstrap、失败 run 和 provenance 都完整。

**明确 no-go：** 任一主对比的 CI 上界仍低于已登记的主效应门槛，或 coverage/invariant/safety 门失败且不属于 test 前已证明的独立工程故障。M1 以负结果结束，不用 PNO、第二任务或更大模型救结果，不进入 M2。

**不确定：** CI 同时覆盖“无效”和“最小有意义效应”。这不等于成功。S4 必须在 test 解封前事先选定“最多一次固定扩样”或“固定样本后以 inconclusive/no-go 收口”；未预先写明时，test 后不得自行扩样。

白话：M1 成功解决“CTL 这台修订发动机是否值得装进完整系统”的问题。输入是封存后从未用于选方法的 test sequence，输出是 A 相对 C/E 的长期当前世界语义、开放记忆支持、全过程开放事实负担和安全差值。例如 A 即使终点修对，也必须比 C/E 至少多 3 个百分点的 semantic/support 正确度并累计减少 40 个 AUC 单位（8 个错误事实×决策步暴露）才可能通过。它不等于训练准确率高、oracle 可达、只在最后一步补救或一个对照输了。

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
