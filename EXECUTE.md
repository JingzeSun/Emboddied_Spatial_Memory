# 实验记录与当前进度

本文件是 embodied_spatial_memory 的唯一实验/架构进度记录，复用原 EXECUTE.md，不再按新对话创建文件。当前看板可更新；只有实验结果、架构实质变化或需保留的失败 run 才追加历史 LOG，普通对话不逐轮记录；管理规则见 D-032。

## 当前看板

> **2026-09-10 更新（S5 完成，科学门未通过）：** 已拉取 `ea6859e` 的 data/confirmation 导出并复核。369 项全测、200 组数据健康、50 模型完整评测与 F 通过；24 组效应/CI 独立复算一致。主架构 A/C/E exact 为 0.9205/0.8980/0.5200；A−C support 仅 +0.001911，burden reduction +0.690，其 CI 上界远低于登记门。两架构均未通过主比较；触发既有 S5 no-go 停止条件，S6 不放行。这是 S5 确认结论，不冒称 S6 test 结果。详见 LOG-090。

最后更新：2026-09-10，S5 报告及来源已复核；LOG-092 完成 group 69 原始轨迹分析，LOG-093 完成全部已导出序列的恢复分层，LOG-094 完成全体 400000 步保存的候选可达性分层。当前协议失败结果解释与收口继续；不改门、不扩模型、不进入 M2，test 保持封存。

| 项目 | 当前事实 |
|---|---|
| 方向 | CPMT 具身空间记忆；CTL 是主学习假设，用户希望面向 ML 研究 |
| 已完成 | M0 合同与 M1-v1 历史基线；程序化 paired 20-step 与固定 K=16；D-034 的 M1-v2 active/history 指标、局部恢复机会、结构化 E、共享 commit 校准、可观测 oracle 和分阶段 provenance；最小 train/validation 接线及 causal smoke 已通过 |
| 阶段 | M1-v7：S5 独立确认已完成，工程 PASS、科学 no-go；当前协议停止向 S6 推进 |
| 最近结果 | [`m1_v7_d055_s5_confirmation.json`](results/m1_v7_d055_s5_confirmation.json)：200 配对组、50 学生模型、400000 次连续决策；两架构 A−C/A−E 均未通过登记检查。详细效应、CI、seed 与泛化诊断见 LOG-090 |
| 尚缺 | 全体逐步选择/候选可达性导出已同步并复核（LOG-094）；错误分支 teacher 排名及具体候选世界的进一步归因仍缺。论文可支持结论整理仍需完成；S6 未运行，当前停止条件下不作为待启动任务 |
| 数据/算力 | 用户提示本机 CPU 负载可能诱发内存损坏；本轮本机重任务到此停止。D-046 顺序 C weight 搜索按既有逐方法实测路径的最坏 10000-update 外推，两臂总计划约 5.036 小时（非新实测）。后续数据生成、训练、causal rollout 和全套测试优先在 AutoDL 上由干净 Git 提交运行，本地只读取导出的 output。云实例仍由用户手动启停和定时关机 |
| 当前决定 | D-039–D-043 固定 live energy、真实 C10/C11、current/posterior 审计、Pre-LN 双架构和 A–E 对称 12 格。D-044–D-046 的 endpoint、open-fact AUC `40/80`、固定 gate、C 顺序权重和纯 confirmation 保留；D-047 收紧 claim，拆清 online network/shared executor，登记外生轨迹，并把 H3-vs-H1 teacher 对照设为主文必报、无选择无成败门的机制证据。M1 不声称原始 DCR、完整动态记忆或 active navigation；全局 reconciliation、PNO 与 M2 顺序不变 |
| 人工待定 | 正式 test 解封仍需以后单独事件；当前不读取 validation/test。D-043 无额外人工选择；运行时剖析只供用户决定何时租用算力，不改变登记网格 |
| Git 备份 | D-038 科学代码基线为 `72afa7d`；S2 40-group reports 已在提交 `ececefb`、10-group 锚点已在 `70355ac` 导入 `results/`，服务器大产物仍位于 ignored `outputs/`。服务器操作只通过版本化的 `ops/run_next_server_step.sh` 交付，脚本所在提交仍须先 push、服务器再 pull |

白话：M1-v6 现在仍是“考前定卷”，不是已冻结或已通过。Pre-LN 和逐方法对称调优只是在排除架构/优化混淆；新的 K=16、固定量程与恢复审计也只证明候选、executor、teacher 和 active-world 评测路径可达。这些都不等于 CTL 已胜出，更不是带 PNO 的 Full CPMT。

## 当前任务清单

M1-v6 的阶段顺序、转向条件和成功/失败终点见 [M1-v6 收口执行流程](experiments/counterfactual_transaction_learning/M1_V2_CLOSEOUT_FLOW.md)。文件名按 D-035 保留；下表只保留任务完成状态，不再承担流程解释。

- [x] 首轮训练与结果审计：LOG-002。
- [x] 收敛重复进度入口：LOG-004。
- [x] 准备单房间试点范围，核查版本、字段、online 边界和渲染兼容性；许可正式审查仍待完成。
- [x] 交付并由用户接受三类可视化案例、候选世界/教师分数、失败与实测资源。
- [x] 写出正式 M1 的 split、future、A–F 公平性、指标、效应门槛和预算候选；校验器保持 test_access=false。
- [x] D-031 接受 D-030 并记录 frozen hash；M1 A 重命名为 CPMT-CTL Core。
- [x] 实现并在 validation smoke 中验证 C00–C11 paired generator、单步图指标、20-step 指标接口与 paired bootstrap；保留投影反例。
- [x] 扩展为首版程序化 world topology，并构造连续 20-step state sequence；错误选择后的下一步从预测图继续，独立样本不冒充 self-rollout。
- [x] 为连续序列补 paired latent siblings，并把 A–F 接入非正式 train/validation causal smoke；完成 CPU 资源测量和首轮 leakage audit。
- [x] 在扩 K=16 前完成全标签容量、4→10 paired groups、60→1000 updates 的可学习性阶梯；分开记录 candidate miss、teacher error 与 amortization error。
- [x] 实现去重、确定性的 K=16 candidate generator，并完成 reference 参数解耦和 C00–C08 validation 开发 coverage 审计。
- [ ] 在不进入 M2、不动 test 的前提下，在 AutoDL 的干净提交上完成 D-044–D-047 full test、含 H3-vs-H1 teacher 主文机制对照的 train-only endpoint probe 与足量 train/validation 预演；按 semantic、open-memory support、全过程 open-fact burden、recovery 和 paired CI 决定是否重新冻结，再单独申请 test 解封。
- [x] **(1) 强化 E 的 outcome scorer 目标空间与监督覆盖。** E 已改为候选作用域的未来关系查询；训练覆盖全部 K=16 候选，目标只读实际 reference future，不执行候选，也不复用 executor 导出的 illegal/collateral。C 使用同一关系目标作 direct auxiliary。当前只验证接线，E 是否真正变强须由服务器足量 run 回答。
- [x] **(2) 固定 commit/quarantine 策略。** D-045/D-046 已 supersede 旧 validation calibration/report 阈值选择：M1 主比较对 A/C/E/F 一律使用 `commit_probability=0`、`margin_threshold=0` 的 always-attempt gate；`commit_attempt_rate=1`，实际 commit 与 executor-illegal deterministic QUARANTINE 分开报告。confidence/risk-coverage 只作诊断，不再决定阈值或主效果。
- [x] **(3) 如实计算 `now` 与 `collateral` 并报告实际影响。** D-039–D-041 已把 executed-now 改为当前匿名投影的固定自然量程、把 legal unrelated mutation 记为 collateral，并常驻逐项 posterior influence/逐 family 预期模式；12-group v8 health 中两项均有可测 posterior 影响，且 C11 collateral 对照通过。它仍不宣称每个 family 的六项都非零。
- [x] **(4a) M1-v2 有界局部恢复。** 按 D-034，exact ambiguity 后固定安排一次相关可见证据重访；用同一 K=16 proposer 和 versioned executor 产生/提交补偿 RELINK，旧错不回填且 provenance 不删除。可观测 oracle 已证明候选路径能在 1 步内恢复 active world；learned recovery 尚待服务器验证。
- [ ] **(4b) Khronos 式全局慢路径（M2）。** 全图、跨多对象、异步重访协调会改变系统时序与方法能力，仍不是 M1 的局部补偿修复；只有 M1-v2 hard condition 支持继续后才实现。

具体试点（开发接口已执行，尚非正式实验）：

1. 一个公开训练场景的房间，制作换视角重见、首次发现此前未见对象、原对象移动后重访。原建议 5–10 房屋仅在接口验证后再考虑。
2. 展示连续画面、相机位置、截至当前的记忆与合理事务，由用户判断是否符合空间认知目标。
3. 最小投影器：候选世界＋固定几何/位姿 → 可见区域、位置及可比较观测。例如移动后的椅子应在新位置出现；不是完整 Projective Node Orbit（PNO），不要求 RGB 生成或同时学习深度、位姿、动力学。
4. 从同一 base 真实执行候选，展示 now/future/edit/growth/collateral/illegal 与教师概率；检查移动、遮挡、多余修改、证据不足。
5. 模拟器全场景真值仅供独立审计/声明的离线监督；在线 memory 只能由截至当前的观测构建，不包含隐藏位置、对象 ID、未来和完整重建。
6. 正式 M1 支持继续后才做 PNO/固定前端视觉整合、使用自身记忆的长期自滚动；正式失败停止主 claim 的规则不变。

单房间三项已交付并获人工接受；D-031 已冻结 M1 数值和命名。当前进入 train/validation 实现，先增加真正的 world/sequence 多样性，再接 A–F；不能因为 96-case generator smoke 或单元测试成功就解封 test、进入 M2。任何付费资源仍无授权。

## 文件职责：规格与记录分开

| 文件/目录 | 职责；何时更新 |
|---|---|
| 本文件 | 当前看板＋实验结果、架构变化和需保留失败 run；普通对话不逐轮追加 LOG |
| [README.md](README.md)、[AGENTS.md](AGENTS.md) | 稳定研究简介与工作规则，不复制最新结果 |
| [DECISIONS.md](docs/DECISIONS.md) | 重要方法/预算/流程决定，实际接受或修改时才追加；普通讨论不逐条编号 |
| docs/01–05、活动实验合同 | 方法/数据/训练/评价规格，实质变化才修改 |
| [白话词典](docs/PLAIN_LANGUAGE_GLOSSARY.md) | 概念解释，不是状态面板 |
| [人工确认索引](docs/human_confirmation/README.md) | 表单导航；当前待定事项只在本看板 |
| [claim ledger](docs/CLAIM_EVIDENCE_LEDGER.md) | 正式证据和 claim 状态，不是日常日志 |
| [首轮报告](experiments/counterfactual_transaction_learning/DEVELOPMENT_RESULTS.md) | 已存在的单次结果分析快照，保留；其“下一步”仅代表当时意见 |
| docs/NEW_CHAT_HANDOFF_PROMPT.md | 固定跳转，不再维护第二份长摘要 |
| docs/reviews/ | 历史周报/模板保留；以后导师反馈写本文件，用户确需独立报告时再导出 |
| archive、docs/source、prototype、literature | 历史、原始资料与文献，不为精简删除 |
| outputs/<run_id>/ | 配置、权重、逐例结果、失败和快照；每次真实 run 分目录，不提交 Git |

“一个记录文件”不等于把代码/配置/全部结果塞入 Markdown。机器实验仍需各自产物才能复现；禁止的是每个新对话新增计划、交接或报告。

## 长期研究边界

用户首次科研、单人推进，老师每周评价；助手负责研究/工程辅助，用户负责重要人工决策。所有方法和公式附白话说明。CPMT 是完整方法，CTL 是核心学习机制；executor、KL 和事务标签本身不是创新。

- D-018–D-025：范围锁、生命周期/版本、SPLIT/MERGE、事实级撤回、pending、身份对应与保守状态等价，详见合同和决策日志。
- D-026：即时在线判断不预读下一帧；之后可以修订，不回填为先前已正确；证据不足允许 QUARANTINE。
- 等价只处理同一 base、同一时刻的表示差异；未来投影相似不能合并不同世界。
- 不加主动策略、第二领域、learned proposer、端到端 backbone 或大规模导航。
- 正式 M1 必须比较 direct+future loss 和 no-execution scorer；仅 latent loss 改善不支持长期记忆 claim。
- 不用 test 调参、筛模型或改门槛；开发数据不改称未见 test。

## 历史记录（按工作事件追加，不按对话建文件）

发现旧结果错误，追加更正并引用原 LOG；不静默改写历史结论。补充同一事件的未完成字段应注明核验性质。

<a id="log-001"></a>
### LOG-001｜2026-09-05｜M0 合同实现回顾

- 类型：已完成工作的追溯汇总，不是本次重新运行。
- 目的：让事务确定、合法、可回滚，不检验 learning 收益。
- 决策：D-019 lifecycle/version、D-020 candidate 确认/休眠、D-021 SPLIT/MERGE、D-022 reliable absence/REPLACE、D-023 pending、D-024 映射、D-025 规范化状态相等。
- 产物：C00–C11 draft fixtures、world/program/pending/commit/equivalence schemas；executor、maintenance、pending、equivalence、hashing。
- 覆盖：NOOP/BIND/BIRTH/REACTIVATE/RELINK/事实级 RETRACT/SPLIT/MERGE/COMPOSITE:REPLACE；弱证据暂存、检索/归档/重激活/消费；身份双射和规范化状态比较。
- 验证：63 个测试通过，HC-001 关闭；支持事务与 QUARANTINE 有正例，存在配对案例；错误版本/生命周期、protected 破坏、缺 provenance、重复事务等拒绝；执行/gate 无未来，无物理删除历史。不是所有可能 invariant 的全面证明。
- 尚缺：node-level RETRACT、PNO、完整学习验证；后续开发训练见 LOG-002。
- 参考：[事务合同](experiments/counterfactual_transaction_learning/TRANSACTION_SEMANTICS.md)、[测试](tests/README.md)、[HC-001](docs/human_confirmation/HC-001_transaction_semantics.md)。

<a id="log-002"></a>
### LOG-002｜2026-09-05｜首轮 CTL CUDA 开发实验

- 状态：M1-development，run complete，未支持相对优势；非正式 M1 gate。
- 授权：D-027，用户要求在 4070 Laptop 开始 CTL 实验。
- 目的：验证执行世界 → 未来能量 → 软教师 → 无未来在线学生的训练链路。
- Run：ctl-dev-20260905T071400973427Z；[目录](outputs/ctl_dev/ctl-dev-20260905T071400973427Z/)、[manifest](outputs/ctl_dev/ctl-dev-20260905T071400973427Z/manifest.json)、[指标](outputs/ctl_dev/ctl-dev-20260905T071400973427Z/metrics.json)、[协议](experiments/counterfactual_transaction_learning/DEVELOPMENT.md)、[原报告](experiments/counterfactual_transaction_learning/DEVELOPMENT_RESULTS.md)。
- 配置：[ctl_dev.json](configs/ctl_dev.json)；1152 train/384 validation，384/128 组，数据种子 260905，训练种子 7/19/31，无 test。实际 252/1152 有标签（21.875%），不是零标签学习。
- 方法：CTL 解析教师、直接分类、分类＋future loss、无执行评分器；学生同网络/初始化/批次/300 步/标签子集，评分器另有参数和训练。
- 资源：RTX 4070 Laptop 约 8 GiB；Python 3.12.10、torch 2.11.0+cu126、NumPy 2.4.3。12 学生＋3 评分器、15 份权重；约 13.83 秒，张量峰值约 66 MiB；不能据此推算视觉成本。

- 代码：src/cpmt/dev_data.py、dev_learning.py、scripts/run_ctl_dev.py、tests/test_ctl_dev.py；72 个测试实际通过（原 63＋新增 9）。
- 版本：HEAD 89153fb6197f8cee007776cab5ed8fe633797357，dirty=true；source_sha256 38897b8fd96229e6c117ab7d53620887fef1bef227c72341f4296e6d0f477761。按 source_snapshot 和数据哈希复现，不只看 HEAD。
- 结果：同一数据三个种子平均 accuracy：CTL 90.54%，直接分类 90.89%，分类＋future loss 90.89%，无执行评分器 90.63%。
- 数据上限：35 对/70 例整个在线输入相同但答案不同，总体上限 90.8854%；可辨识部分对照达 100%，所有方法不可辨识部分 50%。
- 反例/限制：单次身份—位置错误四方法均约 0.1823/例；CTL 暂缓更多但整体概率评分不优于直接分类。暂缓率不是独立可靠性证据；位置指标不覆盖版本/证据错误或长期污染。
- 运行失败：manifest failures 为空，只表示无运行异常，不表示无科学反例。
- 结论：训练链路实现，当前可辨识题饱和；无标签效率、PNO、长期污染减少或执行独立价值的支持；不宣布 M1 go，也不是正式全方法否决。
- Git：输出/权重 ignored；代码文档未 commit/push。旧 archive/pslm-pre-ctt-20260904 / eba4339 不含这次新实现。

<a id="log-003"></a>
### LOG-003｜2026-09-05｜方法诊断与公开数据讨论

- 类型：解释/诊断/建议，不是新实验；D-028 proposed。
- 用户关切：任务太简单，想用公开数据并考虑租服务器；追问 loss 预测以及四项未完成工作的顺序。
- 实际预测：三个位置“数量＋四维外观”，每帧 15 数、三帧 45 数；手写 render、窗口内世界不变、仅视角换位。不是 DINO/PNO/RGB 生成/学习动力学。
- E 是世界评分：now 仅位置兼容，future 为数字 MSE，edit/growth 各 0.005、collateral 1，温度 0.06 得到软教师 p*。非法分支使开发 run 失败。p* 不是天然校准的真实后验。
- 真正学习：有标签 CE＋全样本 KL(p*||q)，仅更新在线 MLP，executor/render 无梯度；未来仅给离线教师/辅助头。直接 future loss 通过共享编码预测未来，无执行 scorer 从修改前输入＋候选描述预测结果。
- 实际 BIND 算例 validation:1260905:BIND：BIND/BIRTH/冗余 RELINK 能量 0.01864/0.18954/0.02364，教师概率 50.56%/2.93%/46.51%。老师排名对但近乎犹豫；标签却要求 BIND。需对齐代价与评价，不能因投影一样违反 D-025 合并版本/证据不同的世界。
- 其他缺口：CTL 解析教师掌握规则而无执行对照需学预测，知识不公平；只测单次更新；后续新事件归因、visibility mask、尾部策略未充分明确。
- 待检验价值：同在线信息/有限标签下，学习效率、空间组合变化和连续修订是否改善；不会创造当前不存在的信息，更复杂数据不保证胜出。
- 数据提案：ProcTHOR＋AI2-THOR 主环境，3RScan 现实重访验证；不是开箱即用 CTL 数据，后者不是完整连续搬运动作轨迹。来源/字段/许可见 [DATASETS.md](experiments/counterfactual_transaction_learning/DATASETS.md)。
- 范围从原建议 5–10 房屋细化为先单房间三类案例，补最小投影接口，人工看评分，再冻结 M1；PNO/视觉/长期验证在正式 M1 支持继续后。
- 云建议：24 GB 单卡、32–64 GB RAM Linux 仅未实测估计，先测渲染/缓存/训练资源，费用另确认。
- 状态：未下载/适配公开数据、装模拟器、采集场景、租服务器或新训练。“保存对话”是文档授权，不等于采纳科研提案。

<a id="log-004"></a>
### LOG-004｜2026-09-05｜工作区与记录方式审计

- 类型：文档工程；用户要求单一实验记录，不逐对话加文件；D-029 accepted。
- 范围：根目录/Git/项目索引，embodied 活动 Markdown 的入口、状态和链接；其他项目只检查边界和完整性，不改变其方法/产物。
- 审计前：embodied 共 102 个 Markdown（含 archive/outputs），排除二者为 72 个；文献 21、docs 25、活动实验 16。多数为规格/文献/历史，不能当作重复进度页全部删掉。
- 问题：EXECUTE、长交接、README、人工确认首页重复状态/下一步；普通对话多处复制；研究合同仍写“方法未实现”，WBS 写“当前只执行 M0”，HC-003 写“训练与评估代码尚未实现”。
- 其他问题：reviews 默认按日期新建周报；DECISIONS 索引遗漏 D-027/D-028，早期 D-003 不学习 split/merge 需按后续 D-018/D-021 理解。

- 工作区边界：根 docs/05_E1_V1_1_SENSITIVITY_PROTOCOL.md 未在根 README 索引，不属本项目，不擅自归类或迁移。多路径 untracked，无当前成果的 Git 提交备份。
- 处理：复用本文件为唯一看板/追加记录；交接和人工确认首页改固定导航；README/合同不复制最新结果；修正过期状态；导师反馈默认追加本文件。
- 保留：原始资料、历史文献、既有结果报告、代码、配置、权重和输出；不删除文件、不新增第二日志、不修改其他项目。
- 验证：整理前后 Markdown 均为 102 个，排除 archive/outputs 后均 72 个；未新增或删除文档。活动 Markdown 本地断链均为 0。
- 完整性：813 个受保护文件（代码/配置/原始资料/归档/运行输出，排除临时 __pycache__）聚合 SHA256 前后相同：7769de1678982613621007cd125c8c6cb399a391ea6640a3008660b828904a04；其他项目 117 个 Markdown 聚合 SHA256 相同：50e61ff33e0a3a3f105e8f0a6e2494b74e2ec483f175ba7e11ab3e227609c6f0。
- 导航：长交接/人工确认/周会页已改固定指向，本文件保留 LOG-001–004 与可追加模板；未改动/覆盖原始 run 或冻结结果报告，未 commit/push。
- 研究影响：未改 loss、数据、阈值、测试或实验结论，未重新训练；72 测试为此前结果。
- 后续：普通实验/调试/讨论/导师意见只追加本文件；重要合同变化才联动 DECISIONS 和对应规格，不再每对话建交接/STATUS/TODO/报告。

<a id="log-005"></a>
### LOG-005｜2026-09-05｜iTHOR 单房间视觉接口与宿主机稳定性审计

- 类型/状态：M1-development 工程试点完成；不是正式 M1 gate，不是 M2，不支持 CTL 相对优势结论。
- 授权：用户确认执行 LOG-003/D-028 的下一步，并在首次宿主机蓝屏后明确要求继续；未授权云费用或租服务器。
- 目的：把“换视角重见、首次发现、同一物体搬移后重访”接到真实 RGB/depth/pose、确定性事务执行和 post-edit hindsight 教师。白话：先看真实房间里管道能否把“还是原物体、第一次见到、原物体换位置”分开；输入是截至当前的匿名区域和记忆，输出是执行后的候选世界、六项分数和老师概率；它不等于神经网络已经学会，也不等于 PNO。

- 环境：Windows 11 宿主＋WSL2 Ubuntu 24.04，Linux 6.18.33.2，Python 3.12.3，AI2-THOR 5.0.0，NumPy 2.5.2，Linux64 build `f0825767cd50d69f666c7f282e54abfe58f1e917`，NVIDIA driver 581.42，RTX 4070 Laptop 8188 MiB；iTHOR `FloorPlan1`，480×320，FOV 90°，不访问 test。
- 数据边界：[数据 manifest](data/manifests/ithor_floorplan1_visual_pilot.json)。online 每例只含 base graph、固定候选、当前 RGB/depth 引用、当前匿名区域、相机和由 depth+pose 得到的候选几何；simulator object ID/name/真位置、future views 和教师只在 `audit.json`。三份 online JSON 的 `future/hindsight/teacher/oracle/ground_truth/object-id/instance-id/audit-ref/target-name` 扫描为 0 命中。
- 实现：[视觉接口模块](src/cpmt/visual_pilot.py)、[runner](scripts/run_visual_pilot.py)、[测试](tests/test_visual_pilot.py)。固定针孔投影与反投影不是 PNO；region 来自 simulator instance mask，只用于接口审计，不冒充已实现的视觉前端。
- Executor 修正：合同已写 RELINK 必须改变位置/拓扑，因此同一 target 的空转 RELINK 现在显式拒绝；不是调教师权重。合成开发生成器同步把此分支保留为 `illegal=1`＋失败记录＋空 post-world，而不是丢候选或使整个 run 崩溃；`configs/ctl_dev.json` 补上 illegal 权重。未追加 DECISIONS，因为这是落实既有 TRANSACTION_SEMANTICS，不是新方法决定。

- 最终 Run：[visual-pilot-20260905T133934890249Z](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/)，[manifest](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/manifest.json)，[case summary](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/case_summary.json)。Apple 初始位于岛台，搬移到水槽旁，旧地点重访为空，新地点重访可见；[初始](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/frames/t0_seen_rgb.png)、[转身](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/frames/t1_away_rgb.png)、[重见](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/frames/t2_reappear_rgb.png)、[搬移后](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/frames/t4_relocated_current_rgb.png)、[旧地点重访](outputs/visual_pilot/visual-pilot-20260905T133934890249Z/frames/t5_old_place_revisit_rgb.png)。目标中心约在 (0.496, 0.492) 与 (0.509, 0.531)，不再贴边。
- 候选/教师结果：每例 NOOP/BIND/BIRTH/RELINK 都引用相同 base hash；合法候选真实执行并保存 post hash，非法候选保存错误。重见：BIND 94.3383%，NOOP 5.1908%，BIRTH 0.4709%，同地点 RELINK illegal；首次发现：BIRTH 99.9932%，NOOP 0.0068%，BIND/RELINK illegal；搬移重访：RELINK 95.2141%，BIRTH 4.7404%，BIND 0.0431%，NOOP 0.0024%。所有分支分别保存 now/future/edit/growth/collateral/illegal；三个 top-1 与预期一致。
- 资源：最终 run 17.704 秒、33 文件、2,854,286 bytes；Linux build cache 1005 MiB。WSLg 图形显存未被 `nvidia-smi` 的前后快照正确计为峰值（均约 7 MiB），因此没有伪报显存峰值；接口 run 只证明本地能渲染/执行，不能外推正式视觉训练显存。
- 验证：Windows 项目环境执行 78 个单元测试全部通过，包含 executor、pending、equivalence、旧 CTL 开发链和新增视觉接口；fixture/unit test 通过不等于方法有效。最终 manifest SHA256 `9B75B1CA2E499168BFB8D39C49EB8027663869047F68223ABA99215C4DED4263`，case summary SHA256 `5EED9262BB7F8FB10EE74C0A2160B6432D41239D81C470148C7FAAC2488E2676`。
- 代码追溯：HEAD 仍是 `89153fb6197f8cee007776cab5ed8fe633797357` 且 dirty；final run 对应 runner SHA256 `C22A9298378FE63107588724A225F16097B81293526CC941536F0781641ADE70`、visual module `C6D56B05228EB3E369D6C04141F4C683FEDE1AC7536E37B0AB4544C99CD7C533`、executor `290847C499BBC31699BE9B702DA3BC02C991B20BC4D4A20A33A1CB3AD371013B`。Git 备份仍未完成；此前向现有 GitHub main 推送整个未审查 dirty 工作区的升级请求被安全审查拒绝，未绕过。

- 宿主机故障：9 月 4 日 23:07 与 9 月 5 日 23:06 均有 `SYSTEM_SERVICE_EXCEPTION 0x3B`，本次屏幕显示 `Ntfs.sys`；最新 minidump 为 `C:\Windows\Minidump\090526-29953-01.dmp`。首次 Linux64 smoke 从 D 盘 NTFS 直接执行，约 154 秒结束后约 2 分钟蓝屏，只有时间相关性，不能据此认定 Ntfs.sys 或本项目是根因。事件日志同时报告 D: healthy，未见 disk/stornvme 超时/坏块事件。
- 缓解：Unity build 非破坏性复制到 WSL ext4 的 `/home/jingzesun/.cache/cpmt-ai2thor`，runner 拒绝 `/mnt/...` build cache，并补 partial-controller 失败清理；迁移后 smoke 启动由 154 秒降到 7.6 秒。其后多次启动/最终 run 至 23:40 未新增 BugCheck，但长期稳定性尚未证明。
- 保留失败：[CloudRendering/Vulkan](outputs/visual_pilot/visual-pilot-20260905T125312025514Z/) 因 llvmpipe 初始化崩溃；[GLX 初始化超时](outputs/visual_pilot/visual-pilot-20260905T132652101300Z/) 暴露残留 Unity PID，已按精确路径终止并修 cleanup；[旧 API 参数](outputs/visual_pilot/visual-pilot-20260905T133032219967Z/)；[落点被墙遮挡](outputs/visual_pilot/visual-pilot-20260905T133741461861Z/)。[首个三例成功 run](outputs/visual_pilot/visual-pilot-20260905T133154289338Z/) 保留为反例：目标贴边、冗余 RELINK 合法导致 BIND 55.53% vs RELINK 41.14%，不可作为最终交付。
- 结论：当前下一步不需要租服务器。单房间 RGB/depth/执行/教师接口在 8 GiB 本地机已完成，瓶颈是正式 M1 合同与科学对照，不是训练容量。若之后固定视觉特征缓存或正式训练实测超过 8 GiB，或宿主蓝屏经 dump/驱动排查仍复发，再单独评估 24 GiB Linux 单卡；数据应在服务器端从公开源下载，只同步代码、manifest、特征/小结果，避免上传悉尼。
- 下一步/人工事项：用户先判断三组画面与 BIND/BIRTH/RELINK 语义是否符合空间认知目标；随后冻结正式 M1 的 paired split、标签/知识/计算公平、future 范围、六方法、主指标和最小有意义差异。正式 M1 go 前不扩到 PNO/M2、更多房屋或付费 GPU；Windows 长时 GPU run 前建议独立分析 minidump/驱动与内存稳定性。

<a id="log-006"></a>
### LOG-006｜2026-09-06｜正式 M1 pre-test lock candidate 与 A–F 接线

- 类型/状态：协议与工程实现完成一段；D-030 为 proposed，尚未 frozen；未生成/读取 test，未重新训练正式模型。
- 授权与人工判断：用户确认 LOG-005 当前三组画面/目标可接受并要求开始下一步。该确认只覆盖单房间视觉案例与 BIND/BIRTH/RELINK 语义，不自动批准全部数值门槛或 formal data。
- 目的：把“正式 M1 怎样才算赢、怎样必须停”从空白表单变成 test 前可审计配置，并补齐旧开发 harness 缺少的 D/F。白话：先把考试规则、六位参赛者和判卷单位固定成候选，再做题；输入是既有研究合同和未触碰 test 的开发证据，输出是机器可校验配置与反例测试；它不是 M1 已通过。
- 配置：[m1_hard_condition.json](configs/m1_hard_condition.json)，协议 `m1-hard-condition-v1`，状态 `pretest_lock_candidate`，canonical SHA256 `10b62691a0ecf4611a6b5ce7451fcd62d25095c2ed91c5b05e174e7918ad082b`。校验入口：[validate_m1_protocol.py](scripts/validate_m1_protocol.py)，实现：[m1_protocol.py](src/cpmt/m1_protocol.py)，详细白话与单位见 [HARD_CONDITION_EXPERIMENT.md](experiments/counterfactual_transaction_learning/HARD_CONDITION_EXPERIMENT.md)。
- future/split：future 只取实际执行轨迹；主 H=3，报告 H=1/5；按有效 pose/visibility mask，尾部至少一帧则保留、零 future 只诊断；online/future cache 分离。C00–C11 每 family 候选规模为 1000/200/200 train/validation/test paired groups，联合 group key 不跨 split，test 尚不生成。
- 候选/教师：A/D/F 共用 deterministic K=16，八原子事务全覆盖；REPLACE/QUARANTINE 保持既有语义；能量权重 now/future/edit/growth/collateral=1/1/0.1/0.25/10，illegal 正无穷 mask，temperature=0.25；coverage gate 总体 98%、每 family 95%。
- 公平/统计：A–E 共用 online encoder、字段、split 和学生更新预算，参数差≤10%，每方法最多 6 个 validation trials；C 独立选 future auxiliary weight；E 的额外 scorer 资源明报；F 只作 K 内 oracle。主标签 10%，另报 0/1/10/100%，seeds=7/19/31/43/59。primary 仅 A–C/A–E，paired stratified bootstrap 10,000 次、95% CI、Holm–Bonferroni。
- go/no-go 候选：每项主对比都需 post-graph correctness 绝对 +3 percentage points，且 20-step contamination 每 100 决策减少 2，校正 CI 排除零；false-birth/collateral 非劣 margin 为每 100 决策 1/0.5，invariant violation=0。若 CI 排除所注册收益则停止扩模型，不进入 M2。
- 开发代码：`dev_data.py` 新增 current-only posterior；`dev_learning.py` 的方法表扩为 A–F，D 用删除 future 项的执行教师，F 用候选预算内 reference program；直接方法仍只在最终评价时用共同 executor 应用所选事务。D-027 原四方法结果和输出保持原样，未被新代码回写。
- 验证：协议校验输出 A–F、K=16、H=3、五 seeds、test_access=false 和上述哈希；85 个全套单元测试通过。新增负例覆盖开启 test、删除方法、把计划动作当 future、拆散 paired bootstrap；六方法完成 2-step CPU smoke，F upper bound=100%。smoke 的其余 33.3% 是两步未收敛工程检查，不是实验结果。
- 资源：无云实例/费用，`cloud_spend_authorized_aud=0`；先本地实现与测量，单正式 run 候选上限 2 小时，新 BugCheck 停止长 run。没有再次启动 Unity 或 GPU 长任务。
- 尚缺/下一步：研究者确认 D-030 数值后才能记 `frozen_pretest`；其前可继续实现但只用 train/validation。尚未实现 C00–C11 批量 paired generator、完整 graph metrics、20-step self-rollout、bootstrap 聚合和正式 A–F runner，因此不能运行 gate、进入 PNO/M2 或形成论文 claim。

<a id="log-007"></a>
### LOG-007｜2026-09-06｜M1 Core 命名冻结、paired generator 与指标首段

- 类型/状态：D-031 accepted；M1 frozen-pretest implementation 进行中。完成命名修正、C00–C11 train/validation generator interface、图指标和 paired statistics 首段；未训练正式 A–F、未生成/读取 test、未启动 GPU/Unity。
- 命名：M1 A 从 `full_cpmt` 改为 `cpmt_ctl_core` / CPMT-CTL Core，表示固定解析表征下的 executed post-world hindsight supervision。Full CPMT 只保留给 M2 同时含 Projective Node Orbit、versioned world graph、executor 与 CTL 的系统。历史 D-027 输出不改名。
- 冻结：用户接受 D-030 并要求继续，配置状态改为 `frozen_pretest`；[配置](configs/m1_hard_condition.json) canonical SHA256 `fa09da245047cbe0399cac49049357173700301565dcab53b452da4682c00287`，文件 SHA256 `d793770f1cbe6afb0f364c50135c9824fbd105010daa2514d5590617c2d5f244`。`test_access=false` 且生成脚本枚举中没有 test。
- 生成器：[m1_data.py](src/cpmt/m1_data.py) 与 [generate_m1_pairs.py](scripts/generate_m1_pairs.py)。C00–C11 human-draft fixtures 仅作语义 archetype；每组重新命名 world/program/evidence，两个 sibling 共用 base、候选、asset、current region 与轨迹。25% 组整个 online 输入相同但 reference 不同；其余组只在可观测的 family-specific history cue 上不同。train/validation 的 group/world seed/asset buckets 分离。
- 候选/未来：每个候选从同一 immutable base 真实执行，C06/C07 使用完整 evidence records，非法 C11 collateral 分支保留 failure；八原子事务都有 reference 正例。reference post-world 经固定 pose-conditioned structural-token projector 生成 H=3 future observations，候选只能经同一 projector 与观测比较，不能直接读取 reference graph。该 projector 是 M1 可审计表征，不是 PNO/RGB/learned dynamics。
- 成功 smoke：[m1-pairs-validation-20260905T152924895678Z](outputs/m1_data/m1-pairs-validation-20260905T152924895678Z/)；48 paired groups、96 cases、C00–C11 各 8 cases、ambiguous groups=12/48=25%、online forbidden-field 文本扫描 0 命中、candidate reference coverage=100%、manifest failures=[]、wall=0.101 秒、5 个文件共 1,525,705 bytes。manifest 使用 `run_manifest.schema.json` 的标准顶层结构；online SHA256 `303b28b0acb7f98778b48c34cae9c14a45c34238e2e088df55929472f77e7824`，audit SHA256 `01004b16aa478abe185ae1f97b06a6c9beaf76a3eec0dfb6e8948d565fdeb63c`。
- 覆盖率限制：此 smoke 将 reference programs 注入候选，100% 只证明接口表达/执行覆盖，不是 frozen coverage@16 gate。变化目前只有 fresh IDs、asset signatures、history cues、poses 与 visibility；world topology 仍是 12 个 archetype，`formal_data_ready=false`，不能称正式数据。
- 失败/修正：较早 [48-case smoke](outputs/m1_data/m1-pairs-validation-20260905T151939031804Z/) 使用 64 维 lossy hash projection，规模太小未暴露冲突，现已 superseded。扩大到每类 4 组的 [失败 run](outputs/m1_data/m1-pairs-validation-20260905T152255346502Z/) 在 C01 group 3 将 BIRTH reference 排到 NOOP 后，manifest 完整保留。原因是固定维哈希碰撞/visibility 恰好抹掉 BIRTH–NOOP 差异，而 growth prior 使 NOOP 获胜；修正为无碰撞的 pose-conditioned structural-token observation，并增加“future 不得含 reference graph、每例错误合法候选 future>0”测试。修正后的 [首个成功 run](outputs/m1_data/m1-pairs-validation-20260905T152447141500Z/) 因 manifest 使用自定义顶层字段而被后续标准结构 run 取代，数据内容及两个数据 SHA 与最终 run 一致。没有按 family 手调答案或接触 test。
- 指标：[m1_metrics.py](src/cpmt/m1_metrics.py) 分开计算 post-graph correctness、错误开放事实、missing facts、false birth、collateral、raw invalid 与 fallback commit；20-step 接口要求真实有序状态序列，长度不符即拒绝，未把当前独立 cases 冒充 self-rollout。paired bootstrap 先在 sibling 内聚合、按 family 分层、以 group 为重采样单位，并实现 Holm–Bonferroni。
- 验证：101 个全套单元测试通过；新增 16 项生成器/指标测试覆盖十二 family、事务正例、base immutability、非法分支、teacher top-1、online 泄漏、exact ambiguous pair、split/asset 隔离、投影非 oracle、错误分项、20-step 长度、paired effect direction 与 Holm。活动范围 JSON 85 个解析通过，活动代码/合同中旧 `full_cpmt` M1 ID 搜索为 0。
- 资源/边界：本次仅 CPU，小 smoke 不说明正式规模工期；云预算仍 AUD 0。下一步是让 world topology、对象数、关系和事件顺序真正程序化，并产生可由前一步预测图继续执行的 20-step train/validation sequence；之后才接 A–F runner 和测资源。

<a id="log-008"></a>
### LOG-008｜2026-09-06｜程序化连续 20-step rollout 首段

- 类型/状态：M1 frozen-pretest implementation；完成程序化空间图与连续 self-rollout 数据/回放接口验证。未训练 A–F、未生成/读取 test、未启动 GPU/Unity，不形成方法效果结论。
- 目的/白话：解决“20 个独立 case 不能冒充长期记忆”的问题。输入是冻结 M1 配置、train/validation split 与序列数，输出是 20 个首尾相接的 base/post graphs、逐步候选、H=3 hindsight 和可从预测状态重建下一步候选的回放接口。例如在一次 RELINK 应发生时选 NOOP，后续步骤不再偷偷切回 reference graph，错误位置会带到第 20 步并同时产生 contamination 和 missing fact。它不是 PNO、视觉轨迹、正式 paired latent 数据或已训练模型。
- 实现：[m1_rollout.py](src/cpmt/m1_rollout.py) 程序化生成 4–7 个 place、1–3 个 surface、随机 filler object/located-at 关系及事件排列；每条固定 20 个决策，包含 NOOP×3、BIND×4、BIRTH×3、REACTIVATE×1、RELINK×3、RETRACT×3、SPLIT×1、MERGE×1、REPLACE×1。[generate_m1_rollouts.py](scripts/generate_m1_rollouts.py) 只开放 train/validation 并写标准 manifest。
- 连续性：reference 第 t 步真实执行后的 post graph 是 t+1 的 base；self-rollout 接口则在方法自己的 predicted graph 上重新构造下一步候选。每步三个候选从同一 immutable base 克隆执行，包括 reference、合法 contrast 和 protected-state 非法分支；非法选择保留 failure 并按 QUARANTINE wrapper 不提交。
- Hindsight：每个当步候选被实际执行后，再沿该候选分支执行之后至多两个已发生的 reference events，和真实 reference sequence 的第 t/t+1/t+2 状态投影比较；末尾严格为 3/2/1 步 mask。逐候选继续保存 now/future/edit/growth/collateral/illegal，online records 不含 future/reference/teacher/oracle 字段。
- 成功 smoke：[m1-rollout-validation-20260905T154658634674Z](outputs/m1_rollout/m1-rollout-validation-20260905T154658634674Z/)；4 条 sequence、80 个有序决策、4 个不同 topology/order signatures，place=4–7、surface=1–3、initial nodes=24–27、candidate set=3。5 个文件共 10,287,987 bytes，wall=1.449 秒，failures=[]，test_generated=false，formal_data_ready=false；online SHA256 `9bf67144bf77ce45dcc71a5810091651fd4eb61c746ed343061472288e5129dd`，audit SHA256 `b1554d2847e8b911dabad0d01425c1d7e5be120686bea00bd90404a3fb5990ba`。
- 反例/修正：首次单序列诊断中，REPLACE 的新对象证据已进入 program 但漏出 `evidence_by_id`，executor 以 missing evidence 拒绝 reference；补齐独立 observation record 后通过。首次全量新测试曾报告一次 graph circular-reference，未改代码即无法在相同 3-sequence 重放、10-sequence stress 或第二次全量测试中复现，因此不据此宣布稳定，只保留为后续重复压力测试观察项。首次正式写盘在创建新 `outputs/m1_rollout` 目录前被 sandbox 拒绝，没有生成 run 目录；取得限定输出授权后同一命令成功，这不是方法/生成器失败。
- 验证：新增 8 项测试，覆盖真实 20-step hash chain、九类 program 正例、同源 base、protected failure、H=3 tail mask、oracle 精确重放、错误 RELINK 长期污染、topology/relation/order 多样性、确定性、split 隔离和 test seal；全套 109 tests 通过。强制在第 4 个决策把 RELINK 改选 NOOP 的诊断回放得到 final correctness=0、contamination=5/100、missing=5/100、false birth=0、collateral=0；这只是指标/传播反例，不是模型结果。最终 online 文本泄漏扫描 0 命中，manifest 顶层/枚举检查通过。
- 局限/下一步：当前序列是受控结构图，candidate set=3 而非最终去重后的 K=16，且没有 paired latent siblings；`formal_data_ready=false`。下一步先把 paired sibling 语义接入连续链并验证相同 online evidence 下的不同合法 reference，再将 A–F 统一接到 causal rollout runner，测 CPU/GPU/显存/延迟后才判断是否需要服务器。

<a id="log-009"></a>
### LOG-009｜2026-09-06｜paired continuous rollout 与 A–F causal smoke

- 类型/状态：M1 frozen-pretest engineering smoke 完成；不是 formal run、不是 go/no-go。连续 paired latent sibling、A–F 统一在线编码/训练接口和基于方法自身 predicted graph 的 20-step causal rollout 已实现；未生成/读取 test，未启动 GPU/Unity，未改冻结协议和预算。
- 目的/白话：paired latent sibling 解决“模型是否只记住表面线索”的问题。输入是一条相同的初始世界、事件计划和截至歧义点的在线记录；输出是两个 sibling，它们在歧义决策处看到完全一样的当前输入，却因之后真实发生的事件不同而有不同合法 reference。例如同一当前画面既可暂不改记忆，也可能应当 RELINK，只有事后实际轨迹能区分。它不等于复制同一个答案两次，也不等于让 online 模型偷看未来。causal rollout 解决“单步准确但写坏世界后偷偷回到标准答案”的问题：每种方法选中的事务先由同一 deterministic executor 提交，下一步候选再从该方法自己的预测图重建；输出是完整 20-step 图指标。它不等于 teacher-forced 单步分类，也不等于 PNO、视觉训练或 Full CPMT。
- paired 数据实现：[m1_rollout.py](src/cpmt/m1_rollout.py) 为每个 group 生成两个 sibling；歧义 pivot 之前和当步的 online payload 字节级相同，sibling 0 执行 primary reference，sibling 1 执行合法 contrast，随后 reference graph、future trace 与事件链自然分叉。train 标签按 group 整组抽取冻结主比例 10%，validation 为 0；`materialize_rollout_step` 可在调用方提供的 predicted graph 上重建下一步三个候选。旧 unpaired 接口保留为显式 legacy mode。
- paired smoke：[m1-rollout-paired-validation-20260905T161033488389Z](outputs/m1_rollout/m1-rollout-paired-validation-20260905T161033488389Z/)；4 paired groups、8 sequences、160 decisions、4 个 exact ambiguous decision pairs、4 个 topology/order signatures，place=4–7、surface=1–3、initial nodes=24–27、candidate set=3。5 个文件共 20,413,857 bytes，wall=4.855 秒，failures=[]，`paired_latent_siblings_ready=true`、`test_generated=false`、`formal_data_ready=false`；逻辑 online/audit SHA256 为 `2e9a31f1521865f6d17e419be840ab24e1ccb615560f05843cb21d18c285dbe1` / `8a98047917a971e23b32fac2ee470e391734cd9a5a435cf41455452fcba3b08d`。
- A–F 实现：[m1_af_rollout.py](src/cpmt/m1_af_rollout.py)、[run_m1_af_rollout.py](scripts/run_m1_af_rollout.py) 与非正式配置 [m1_af_smoke.json](configs/m1_af_smoke.json)。A 是 executed hindsight posterior 的 CPMT-CTL Core；B 是有限标签直接分类；C 是 direct+future loss；D 是 execute+current-only teacher；E 是不执行候选的 learned future scorer；F 是 candidate-program oracle upper bound。A–E 共用 130 维 online encoder、同一 23,526 参数学生、相同初始化/更新预算/commit rule/executor；99 维 future target 只在训练教师或 auxiliary 中使用，不进入 online `forward`。E 另有 19,363 参数 scorer 并单独报告；F 不参与公平训练比较。
- A–F smoke：[m1-af-rollout-smoke-20260905T161841570586Z](outputs/m1_af_rollout/m1-af-rollout-smoke-20260905T161841570586Z/)；seed=7，train=10 paired groups/20 sequences/400 decisions，validation=4/8/160，train 标签组比例严格 10%、validation 0%，每条 20 步，candidate=3 而冻结预算是 K=16。CPU wall=26.143 秒，19 个文件共 70,606,351 bytes，failures=[]；data manifest SHA256 `b007483047c6bca5c56ab68e3345e18f280788918602bc208bb892dffe370814`，train/validation 逻辑 audit SHA256 为 `5b6f8b477660319650a446c9c0ea3a8d0a1fc70b5962b341d6ea9f1494d1cce5` / `5746c57ab8e90a745f0b0816de3b6fcba6b43abc8a8f811d36b2fe2e6a181b40`，协议 hash 仍是 `fa09da245047cbe0399cac49049357173700301565dcab53b452da4682c00287`。
- 结果：teacher-forced accuracy 为 A/B/C/D/E/F=`75.00/57.50/54.38/58.13/58.13/100%`，歧义点 A–E 均为 50%；20-step mean correctness=`15.63/10.00/10.00/10.63/10.63/100%`，final correctness=`0/0/0/0/0/100%`。每 100 决策 contamination=`1.25/11.25/12.50/17.50/17.50/0`，missing=`1.25/8.75/10.00/11.25/11.25/0`，false birth=`8.13/9.38/8.13/0.63/0.63/0`，collateral 全为 0。A–E 单次网络 forward 的 p95 为 0.138–0.159 ms；该延迟不含 Python generator/executor，不能外推正式吞吐。
- 解释/反例：A 在这个极小 validation smoke 的 teacher-forced accuracy 和 contamination 上较好，但五个可学习方法的 final correctness 全为 0，A 的 false birth 仍为 8.13/100；只有 F=100% 说明 reference 在当前三个候选内可达。D/E 的训练教师 accuracy 仅 36.25%，也显示 current-only/no-execution target 在此接口很弱。只有 1 seed、4 validation groups、无 trials/置信区间/10,000 次 bootstrap，且 candidate=3，因此既不能宣布 A 优于 B/C/E，也不能运行或通过 M1 gate。
- 泄漏/验证：online encoder 显式拒绝 audit payload；改动 future storage 不改变 online feature；paired pivot 的 online vector 相同而 reference label 不同；所有方法下一步都从各自 predicted graph 重建。新增 8 项测试后全套 117 tests 在 17.949 秒内通过，覆盖 paired determinism/split/asset/test seal、双 sibling oracle replay、future 隔离、非法候选 mask、六方法参数公平与 F 的完整因果回放；online JSONL 对 future/reference/teacher/oracle 等禁词扫描 0 命中。86 个活动 JSON 全部解析，旧 M1 `full_cpmt` ID 为 0，冻结协议复算 hash 一致；实际两个成功 manifest 的 required/allowed/enums/关键嵌套字段检查通过，均 `status=complete`、`failures=[]`。
- 调试记录：paired dry-run 首次与另一 Python 进程并发时无输出返回 exit 1，立即单独重试通过；首次按模块名调用新增 unittest 时报告 0 tests，显式类调用及之后 full discovery 均正常发现并通过。最终审计时全局 `python` 不在 PATH，改用项目 `.venv` 后通过；环境未安装可选 `jsonschema` 包，因此没有为审计临时联网安装，而是按仓库 schema 做上述结构/枚举检查。它们均未改变科学结果；鉴于此前 Windows 蓝屏历史，后续不并发施压长 Python/Unity 任务。
- 资源/结论：当前瓶颈是候选构造和正式统计规模，不是 8 GiB 显存；这一阶段纯 CPU 约 26 秒，本地足以继续，不租服务器，云预算仍 AUD 0。下一步固定为实现确定、去重的 K=16 generator，记录 candidate miss 与 coverage@K，再进行完整 train/validation、5 seeds、每方法 trials 和 paired bootstrap。完成开发审计前不解封 test；正式 M1 未支持继续时不进入 PNO/M2。

<a id="log-010"></a>
### LOG-010｜2026-09-06｜M1 可学习性阶梯与宿主隔离执行

- 类型/状态：M1-development trainability diagnostic 完成；`formal_run=false`、`test_access=false`、candidate=3，未运行正式 gate。目的不是再比较一次排行榜，而是在扩 K=16 前判断简单 MLP 是否具有基本拟合能力，并把 candidate miss、teacher error 与 amortization error 分开。
- 目的/白话：全标签容量测试解决“低分是不是因为这个网络连训练集都学不会”。输入是 4 个 train paired groups 的全部事务标签，输出是训练集 teacher-forced 与因果回放；exact ambiguous pivot 的两个 sibling 在线输入完全相同但答案相反，所以任何确定性在线模型的总体可观测上限是 97.5%、歧义点上限是 50%，不是 100%。优化/数据阶梯输入相同 10% group labels，分别改变 4→10 groups 和 60→300→1000 updates，输出 validation 学习曲线。它不等于用 validation 选正式 checkpoint，也不等于 CTL 已赢。
- 实现：[m1_trainability.py](src/cpmt/m1_trainability.py) 提供 group-safe subset、candidate audit、可观测上限、全标签容量点和 teacher/amortization 分解；[run_m1_trainability.py](scripts/run_m1_trainability.py) 写标准 manifest、配置、数组、逐点权重/明细与失败记录；配置为 [m1_trainability_ladder.json](configs/m1_trainability_ladder.json)。所有点继续使用 A–E 共用的 130→64→64→3 学生、Adam、batch=64、seed=7 和同一 executor/commit rule。
- 数据/Run：成功 run [m1-trainability-20260905T165725697345Z](outputs/m1_trainability/m1-trainability-20260905T165725697345Z/)；train=10 paired groups/400 decisions/10% group labels，validation=4/160/0 labels；candidate reference coverage=100%、candidate miss=0、illegal reference=0，但 reference 是主动注入的三个候选之一，绝不是正式 K=16 coverage。CPU wall=102.054 秒，131 个文件共 74,993,602 bytes，manifest `status=complete`、`failures=[]`、data hash `96d7fca830d4130584258f4b2ca5f5d93c019701b0a39c70e584325bae4fd34b`，`test_generated=false`、`formal_data_ready=false`。新旧 train/validation NPZ 与 LOG-009 A–F smoke 数组逐项完全相同，证明分片没有换数据。
- 全标签容量结果：direct classifier 在 60/300/1000/3000 updates 的 teacher-forced accuracy 均为 97.5%，可辨识部分均 100%，歧义点均 50%，与理论 teacher-forced 上限差 0，因此 `capacity_pass=true`。20-step train causal mean correctness=`53.13/62.50/62.50/53.13%`，final=`37.5/50/50/37.5%`；本数据回放中的最好 final 为 50%，3000 steps 因 confidence/commit 与错误分支传播降回 37.5%，说明拟合能力通过但 causal calibration 不随更新数单调改善。
- held-out 步数曲线（10 groups）：A CPMT-CTL Core 在 60/300/1000 updates 的 teacher-forced accuracy=`75.00/85.63/88.75%`，可辨识 accuracy=`76.32/87.50/90.79%`，ambiguous 恒为 50%；20-step mean correctness=`15.63/30.63/34.38%`，final=`0/12.5/12.5%`。A 的 teacher error 恒为 0，student-to-teacher amortization error 从 25.00% 降至 14.38% 再到 11.25%，说明增加优化主要让学生更接近 executed hindsight teacher。
- 对照曲线：B direct classifier accuracy=`57.50/58.13/60.63%`，C direct+future=`54.38/55.00/57.50%`，两者 final 始终 0；D execute+current-only=`58.13/57.50/60.00%`，E no-execution scorer=`58.13/57.50/58.13%`，两者 final 也始终 0。D/E 的 soft-teacher error 都是 63.75%，表明它们的主要瓶颈先在教师而非学生。A 在 1000 steps 的 contamination/missing/false-birth 为 `1.25/1.25/2.50` 每 100 decisions，B 为 `8.75/6.25/6.25`，C 为 `11.25/8.75/6.25`；样本太小，不作显著性或优越性声明。
- 数据量诊断：相同 1000 updates 下，A 从 4 groups 的 accuracy/mean/final=`75.00/18.75/0%` 提高到 10 groups 的 `88.75/34.38/12.5%`。这是与“更多 paired worlds 有帮助”一致的单 seed 方向性证据，不是学习曲线已经饱和，也没有排除特定生成器模式被记住。
- F/oracle：所有点继续为 100%，因为它直接读取 audit reference index；这里只证明正确候选和 executor 路径可达。candidate miss=0 不能归功于模型，必须等 K=16 固定生成器不注入答案后重新测。
- 宿主失败与恢复：初始 20-group 单进程 run `m1-trainability-20260905T163901749381Z` 无 traceback 退出；收敛到 10 groups 后 `...164010053699Z` 在标准库 `deepcopy` 报内部 `IndexError`，`...164557801706Z` 再次无 traceback 退出；首个部分完成 run `...165408418134Z` 在容量和两个曲线点后报 `SystemError: unknown opcode 199`。这些 run 均保留并标 `failed`，不是方法负结果。局部工程修正用 JSON-native recursive clone 代替热路径无必要的整图 `deepcopy`，保持 immutable clone；但 Windows 仍偶发 `0xC0000005`，说明宿主根因没有解决。
- 隔离执行：[generate_m1_trainability_shard.py](scripts/generate_m1_trainability_shard.py) 每个 paired group 一个新进程，[run_m1_trainability_point.py](scripts/run_m1_trainability_point.py) 每个训练点一个新进程；固定 group/seed/配置失败时只在新 attempt 目录重试，不能跳样本或换 seed，只有 `complete.json` 才纳入父 run。成功 run 中 train group 9 和 `g4_s1000` 各有一次 `0xC0000005`，第二次相同输入成功；两次失败完整列入父 metrics 的 attempt log，父 manifest 无未解决 failure。
- 验证：新增 JSON clone independence、trainability test seal、paired subset、coverage/ceiling、真实学生容量和 offset-shard equivalence 测试；全套 123 tests 在 12.480 秒内通过。offset group 1 与一次生成两组中的 group 1 online/audit hash 完全一致；这说明分片只改变进程边界，不改变世界、标签或未来。
- 结论/下一步（执行优先级已更新）：排除“当前 MLP 容量不足以拟合可见训练关系”这一解释；当前剩余主要问题是有限 paired 数据下的泛化/学生摊销、D/E 教师质量和长期 commit 校准。A 的方向性提升允许继续实现 deterministic deduplicated K=16 candidate generator，但仍不得宣称 M1 go。由于本次神经训练很轻，租 GPU 仍无价值。Windows 诊断建议保留，但用户后续明确不再把解决宿主稳定性作为继续开发或普通验证的前置条件；运行失败按次记录并隔离重试。

<a id="log-011"></a>
### LOG-011｜2026-09-06｜Windows/SSD 稳定性诊断与 Git 备份

- 类型/状态：宿主诊断进行中；只读检查已完成，高风险修复尚未执行。用户要求先将仓库中应由 Git 管理的全部内容推送到现有 `origin/main`，作为固件操作前的源码/合同备份。Git 备份不包含 `.gitignore` 排除的 outputs、本地数据、论文、模型权重、缓存和虚拟环境，也不等于整机或实验产物备份。
- 症状/白话：轻量 CPU 训练也随机出现 `python.exe` 读写无效内存、标准库内部 `unknown opcode` 和对象状态不可能损坏；这不是普通 Python 异常。2026-09-06 留有 6 份 Python crash dump，WER 记录 `0xc0000005`，故障位置为 `python312.dll` 或未知地址；当前环境为 CPython 3.12.14、CPU-only PyTorch 2.14.0、NumPy 2.5.2，因此不能归因于 4070 显存不足或 CUDA OOM。
- 系统证据：ROG Strix G16 G614JIR、i9-14900HX、单条 Samsung 16 GiB DDR5-5600、BIOS 320；Windows 11 25H2 build 26200.9168。2026-09-04 与 09-05 连续两次 `SYSTEM_SERVICE_EXCEPTION 0x3B`/`c0000005`，后一次 WER 提示可能相关驱动 `Ntfs.sys`；2026-07-09 另有 `0xEF`。2026-08-24 曾因临界温度事件进入休眠。过去一年没有 Windows Memory Diagnostics 完成记录，因此 RAM 尚未排除。
- 存储证据：过去一年有 9 次 WHEA corrected PCIe error，全部来自 Intel PCI Express Root Port #21 (`8086:7A44`)；其唯一子设备是 Samsung NVMe (`144D:A80C`)，即承载 C:/D:、Windows、项目和 Python 的 Samsung SSD 990 PRO 1TB。该盘基础状态为 Healthy/Online，但固件仅 `4B2QJXD7`；Samsung 官方后续 `7B2QJXD7` 明确修复间歇性无法识别和蓝屏，最新版 `8B2QJXD7` 继续改善读取稳定性。E: 是独立的 Kingston SNV2S2000G 2TB，不在该错误端口。
- 风险边界：SSD 固件更新通常不格式化或改写 C:/D: 用户文件，但写固件期间断电、蓝屏或失败可能使整块系统盘不可识别。尚未下载安装 Samsung Magician，未更新 SSD/BIOS，未运行 SFC/DISM/chkdsk、压力测试或内存测试，未改注册表，未触发重启。电池读取为 100%；BitLocker 状态因当前进程无管理员权限而未能核验。
- 判断/后续状态：当前最强、但尚未最终证明的根因候选是旧版 990 PRO 固件/PCIe 存储链路；RAM、散热、BIOS 与系统驱动仍是备选。源码 Git 备份已完成；用户选择暂不更新固件，并后续取消“稳定性先行”的项目执行限制，因此普通开发与验证继续。若将来重新考虑固件/BIOS/磁盘修复，仍须先备份不可替代的 C:/D: 数据、确认 BitLocker 恢复密钥，并在执行任何高风险命令前明确告知用户；这条安全边界不等于当前研究前置条件。

<a id="log-012"></a>
### LOG-012｜2026-09-06｜固定 K=16 候选实现与宿主中止

- 类型/状态：M1-development 工程实现部分完成、运行验证被宿主 access violation 中止；`formal_run=false`、`test_access=false`，未生成 test、未训练 A–F、未运行 coverage gate。用户选择暂不更新 SSD 固件，并要求继续项目下一步；任何系统/固件高风险操作仍禁止自动执行。
- 目的/白话：固定 K=16 candidate generator 解决“此前三个候选里 reference 是不是被直接塞进去”的问题。输入只能是当前 versioned world、当前证据标识、当前时刻和固定种子；输出最多 16 个可执行事务程序、非法失败与 canonical 去重审计。例如隐藏答案改成 BIRTH 或 RELINK 时，生成器仍应产生完全相同的候选列表，reference 必须另行执行后再按 memory state 匹配。它不等于 learned proposer、不读取未来，也不表示 coverage 已通过。
- 实现：`m1_rollout.py` 新增 `fixed_deterministic_k16_v1`，候选覆盖 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE 与复合 REPLACE；候选事件先裁剪到六个允许字段，不复制 `primary_template`/`scenario_family`，每个候选从同一 base 交给 deterministic executor。合法 post-world 用 `canonicalize_memory_state` 去重，非法候选原样保留。事件 ID 改成不含事务类型的中性 step ID；paired pivot 显式选择不同语义的合法 contrast，不再随便取任意非 reference 下标。
- Coverage 接口：新增 `audit_m1_candidate_coverage` 与 `scripts/audit_m1_candidates.py`。输入为 train/validation group 数，输出逐决策 reference canonical match、总体/逐 family support 与 coverage、candidate miss、K、去重和 gate 状态；不构造 future、不训练、不开放 test。`reference_candidate_audit` 与隔离 runner 同步增加逐 family coverage、candidate count min/max 和 generator ID。
- 学习接线：`OnlineModel`、`OutcomeScorer`、one-hot、oracle、Brier 和 A–F causal adapter 从硬编码三类改为由 `penalties.shape[1]`/冻结 K 自动定维；旧 candidate=3 结果保持原样，不能被新代码重新标成 K=16 结果。对应测试与中英文职责说明已更新，但高负载验证没有执行。
- 已通过验证：修改前后的相关文件曾做 `py_compile`，0.2 秒通过；随后只生成一个初始 world 的一个决策，得到 16 个候选、九类事务齐全、15 legal/1 protected illegal、canonical duplicate=0，0.3 秒完成。更改隐藏 `primary_template` 时候选字节级不变的测试已写入，但尚未运行测试类。
- 失败：尝试一个单线程、CPU-only、内存内的 20-step validation sequence 时，3.8 秒后 Python 发生 fatal access violation 并退出，exit=1；faulthandler 栈位于 `hashing.py:clone_json` → `m1_rollout.py:_candidate_state_signature/generate_fixed_candidates/_candidate_programs/_generate_sequence`。新 dump 为 `%LOCALAPPDATA%/CrashDumps/python.exe.34644.dmp`，约 2.5 MB，时间 2026-09-06 03:27:55。Windows 没有蓝屏；没有生成 run 目录或科学结果。
- 当时的静态收敛：该次 access violation 后没有立即重试 Python，只通过代码编辑去掉 candidate signature 中不必要的整图深拷贝，并让 hindsight counterfactual future 分支直接执行独立 hidden reference。后来用户明确取消“以解决稳定性为优先”的工作策略，正常开发与验证从 LOG-013 恢复；既往故障仍保留为运行风险，失败时采用独立进程重试，不再把全部 Python/训练一概暂停。
- 当时终审发现的 coverage 边界：生成器没有读取 `primary_template`/`scenario_family`，但受控 fixture 的隐藏 reference 参数仍复用了 candidate generator 的 current-world 排序，所以 LOG-012 的 100% 不能当独立 coverage。该缺口已由 LOG-013 的 audit-only `reference_spec` 与匿名 observation 检索解耦修复；LOG-012 的 `reference_arguments_independent=false` 只保留为当时事实。
- Git 备份：上述未验证代码以 `1b9a078` 推送到 `origin/wip/k16-candidate-generator`，本地/远端 SHA 一致；`origin/main` 仍停在 candidate=3 的 `fa9606c`，没有把 access-violation 后未重跑的实现伪装成稳定主线。
- 结论/下一步（已由 LOG-013 更新）：本条记录结束时 K=16 完整链、coverage@16 与动态 A–F 尚未验证。其“先解决宿主稳定性、只允许静态审查”的执行限制已被用户后续指示取消；正式 M1、test、PNO 和云资源的原有方法/授权限制不变。

<a id="log-013"></a>
### LOG-013｜2026-09-06｜K=16 隐藏 reference 解耦与 validation 开发审计

- 类型/状态：M1-development 候选架构修复及 validation coverage 审计完成；`formal_run=false`、`test_access=false`、`formal_gate_eligible=false`。未训练 A–F、未生成 test、未改变 frozen M1 门槛。
- 目的/白话：这次修复解决“候选生成器虽然看不到事务名称，却能否通过同一套 ID 排序间接猜到隐藏答案”的问题。输入是当前 world 与不含对象/边 ID 的匿名 16 维 observation query，输出是由固定检索、九类事务槽位、真实执行和 canonical 去重得到的 K=16 候选。例如隐藏 reference 指向某条 RETRACT edge，生成器只能用匿名 query 在当前图中检索 edge，不能读取 `reference_spec`；审计端再独立执行 reference 并比较 post-world。它不等于 learned candidate generator、不等于真实视觉 proposal，也不把 100% 开发 coverage 当正式证据。
- 架构变化：完整隐藏事务移入 audit-only `reference_spec`；online/candidate 路径只接收 `proposal_observation` 的匿名数值向量。候选生成在删掉整个 `reference_spec`、改变 `scenario_family` 后仍须字节级不变，且 observation 中不得出现 `rollout:` 身份字符串。causal replay 从每种方法自己的 predicted world 直接重建候选，不依赖隐藏 reference；错误分支使后续 oracle program 前置条件不成立时，记录 `counterfactual_rollout_failures`，以 `QUARANTINE_KEEP_CURRENT_WORLD` 保持该错误世界继续回放，而不是跳回标准答案。
- 三个类型报错：`m1_trainability.py` 的 paired-group 子集返回值改为 `list[Mapping[str, Any]]`；`dev_learning.train_student` 的返回模型从宽泛 `nn.Module` 收窄为 `OnlineModel`，因此 `causal_rollout_metrics` 调用和 `run_label_rich_capacity_point` 返回值不再类型冲突。依赖检查同时把 NumPy bool 反转改为 `np.logical_not`。Pyright 对 `m1_rollout.py`、`test_m1_rollout.py`、`m1_trainability.py`、`dev_learning.py` 报告 0 errors/0 warnings。
- Run/结果：[m1-candidate-audit-20260905T180744201161Z](outputs/m1_candidate_audit/m1-candidate-audit-20260905T180744201161Z/) 使用系统 CPython 3.12.10、validation 4 paired groups/80 decisions，wall=2.476 秒、failures=0、candidate reference coverage=100%、miss=0、C00–C08 每 family=100%、`reference_template_independent=true`、`reference_arguments_independent=true`、`coverage_thresholds_met=true`、`test_generated=false`。一组 20-step 诊断也成功生成；错误候选分支共保留 9 次后续 reference 前置条件失败，没有将分支重置为 oracle world。
- 验证/局限：三个关键 `test_m1_rollout` 用例在开发过程中曾分别以独立进程通过，覆盖删掉 reference 后候选不变、coverage/test seal、真实 later-reference hindsight 与 tail mask；最终复核时前两项通过，第三项连续三次在 `setUpClass` 生成数据期间被系统级 access violation 中止，均未进入测试断言，因此本轮只确认静态检查和前两项，不写成“全套通过”。按用户指示不另开稳定性优先工作流，只保留失败事实并在后续正常运行中隔离重试。当前审计只覆盖受控 C00–C08 和匿名固定检索，未覆盖 C09–C11、正式规模、独立视觉 observation、A–F 学习或统计置信区间，所以 `coverage_gate_pass=false`。
- 结论/下一步：reference 类型和参数已与候选生成输入/排序解耦，K=16 开发 coverage 接口可以继续使用；100% 数值只证明当前受控检索闭环。下一步先补 C09–C11 并扩大 train/validation coverage 审计，再运行动态 K=16 A–F smoke；仍不开放 test、不进入 PNO/M2、不产生云费用。

<a id="log-014"></a>
### LOG-014—2026-09-06—固定 K=16 A–F 可学习性阶梯完成（非正式）

- 类型/状态：M1-development，run complete；`formal_run=false`、`test_access=false`，不构成 M1 go/no-go，也不授权 M2/PNO、test 或云资源。
- 目的/白话：确认 K=16 候选的 reference/排序解耦后，学生能否仅从当前在线向量，把“候选真实执行后再由 hindsight 形成”的教师选择学出来。输入是 10 个 train paired groups（400 decisions）和 4 个 validation paired groups（160 decisions）；输出是 A–F 的单步选择和用各自错误世界继续的 20-step causal rollout。比如 A 选错第 6 步后，第 7 步会在它的错误 world 上重新生成 K=16 候选；它不读取 reference、future 或 test。它不等于 Full CPMT，更不等于真实视觉 PNO 训练。
- 改变/固定：使用 LOG-013 的 audit-only `reference_spec`、固定 deterministic K=16 generator 与同一版本 executor。为保留偶发原生进程崩溃下的有效结果，新增 `m1_af_method.py` 与 method worker，将同一曲线点的 A–F 分别在独立进程训练/causal replay；同一 data、seed、步数和方法只承认带 `complete.json` 的完整 attempt，六项齐全才聚合。它是恢复/保留机制，不改变科学协议或选择最优 attempt。
- 配置/数据/版本/资源：run [`m1-trainability-20260905T184650400036Z`](outputs/m1_trainability/m1-trainability-20260905T184650400036Z/)；commit `c9eb18d365507ac6fc4cfae6d5bff3beb1cd5a22`、dirty=false、seed=7、CPU（WSL CPython 3.12.3、Torch 2.14.0+cpu、NumPy 2.5.2、2 threads）。训练点是 (4 groups,1000 steps)、(10,60)、(10,300)、(10,1000)；A–E 同为 46,003 参数，E 另有 41,827 参数 outcome scorer；future 只用于 hindsight training。数据 audit：train/validation candidate miss=0，K=16，C00–C08 在该小规模受控诊断中每 family coverage=100%；非正式数据仍未覆盖 C09–C11 或独立视觉输入。
- Run/结果：[`metrics.json`](outputs/m1_trainability/m1-trainability-20260905T184650400036Z/metrics.json) 与 [`manifest.json`](outputs/m1_trainability/m1-trainability-20260905T184650400036Z/manifest.json) 保存逐方法、逐例、hash 与所有 attempt。全标签 capacity（B、4 groups）在 60/300/1000/3000 steps 都是 overall 97.5%、identifiable 100%，20-step final post-graph correctness 为 37.5%/37.5%/50.0%/50.0%。A 的四点依次为 teacher-forced 6.25%/6.88%/9.38%/6.25%，final post-graph correctness 全为 0%。在最大点 (10 groups,1000 steps) 上，A/B/C/D/E 的 teacher-forced accuracy 为 6.25%/2.50%/6.25%/8.12%/6.88%，其 final correctness 全为 0%；F 是 oracle candidate program，teacher-forced 与 final 都为 100%。
- 验证/误差：A 的 executed-hindsight teacher error 四点均为 0，而 amortization error 为 93.75%/93.13%/90.63%/93.75%；candidate miss=0。这说明该受控数据中教师、候选覆盖与执行接口足以给出正确答案，但当前学生未把教师后验从 468 维 online feature 学到可泛化选择。它不是“CTL 已被 MLP 击败”：97.5% capacity 的 B 使用 100% 标签，而 A–E 曲线使用 10% 标签；同时 B 的 causal final 最高只有 50%，没有任何非 oracle 方法在这次小规模 self-rollout 成功。
- 失败/局限：重试中保留 Windows/WSL 的 returncode `-11` 与少量解释器异常；例如 g10_s300 的 B 在第 11 次才完成，C/E/F 分别在第 8/5/3 次完成。完成产物均来自单独成功进程，失败 attempt 没有覆盖它们。run 只有一个 seed、4 个 validation paired groups、C00–C08 受控 fixture、固定结构向量前端，且无 confidence interval；不能作显著性、现实视觉、长期泛化或正式 M1 结论。
- 结论/下一步：本次 K=16 开发诊断的容量检查通过，却没有支持 CTL 的学习效果；在没有解释高 amortization error 前，不扩模型、不进 M2、不用 test。下一项应是冻结本 run 后的可复现诊断，逐项核对在线特征对正确候选的可辨识信息、A 的目标/损失数值与优化更新；若这些诊断确认无误，按 M1 stop rule 不以增加表征或任务去寻找正结果。

<a id="log-015"></a>
### LOG-015—2026-09-06—修复 K=16 在线接口并把模板决策改为证据驱动（非正式）

- 类型/状态：M1-development，代码改动与小规模诊断；`formal_run=false`、`test_access=false`，不构成 M1 go/no-go，也不授权 M2/PNO、test 或云资源。
- 目的/白话：LOG-014 里 A 的 amortization error 高达 90%+，本轮先查清原因再决定是否继续。诊断在 LOG-014 冻结的 arrays 上进行，结论是任务本身坏了，不是方法输了。
- 诊断（在 `m1-trainability-20260905T184650400036Z` 的 arrays 上，全标签）：
  1. **head 是索引式的。** `Linear(hidden,16)` 预测的是槽位下标，而候选列表按 `candidate_seed` 随机置换，正确下标在世界间均匀分布。只把 head 换成共享逐候选打分器、特征一字未改，validation 从 10.0% 升到 65.6%，参数量 46,003 降到 24,228。
  2. **同模板候选编码相同。** 16 个候选里平均 10.8 个特征块逐位相同；58.1% 的 validation 决策中正确候选与至少一个错误候选无法区分。当时特征的信息上限只有 68.5%，共享打分器已达 66.9%，即已吃满。
  3. **参数那一半是查表。** `proposal_observation` 是真值参数 ID 的精确 SHA-256：136/136 个有参数的场合点积恒为 1.000，正确候选永远落在生成器的 slot-0 系列，从未出现 slot-1/slot-2。
  4. **模板那一半是标签。** `scenario_family` 是 online 输入里的 12 维 one-hot，单独预测正确模板达 546/560=97.5%，缺口恰为 ambiguous pivot 比例。而 `anonymous_signature` 与 `cue_value` 经核对与事件完全无关，是独立随机数——输入里当时不存在任何合法证据通道。
- 改变/固定：(a) `OnlineModel`/`OutcomeScorer` 改为置换等变的共享候选打分，旧的索引 head 仅在 candidate_dim=0 的 K=3 开发路径保留；(b) online 记录携带 proposal query，候选块加入参数对齐度，同模板候选不再同码；(c) 观测改由执行中的世界生成——节点有固定外观描述符，观测为描述符加噪声，附 `visibility`/`pose_valid`/`depth_valid`/`reliability`/`evidence_novel` 与七项记忆比对量，`scenario_family` 与随机 cue 移出 online 只留 audit，歧义点改用遮挡实现；(d) 新增 `observation` 协议段与校验（`occlusion_is_neutral` 必须为真），`dataset_version` 升到 `m1-paired-latent-worlds-v3`。语义取自 `docs/02_scenario_wbs.md`、C00–C11 fixture 的 evidence schema 与 `dev_data.py` 已有的 latent→render 因果链，未发明新语义。
- Run/结果（10 train + 4 validation paired groups、160 个 validation 决策、全标签容量设置）：先以 seed=7 得索引 head train 97.5% / validation 12.5%，共享打分器 train 97.5% / validation 90.0%（参数 53,683→25,188）；机器降频稳定后复跑，上述数值逐位复现，确认生成与训练是确定性的、未被硬件损坏污染。随后以协议登记的五个正式 seed [7,19,31,43,59] 复核：索引 head **0.0925 ± 0.0222**（区间 [0.056,0.125]，几乎等于 0.0625 的随机基线），共享打分器 **0.8863 ± 0.0292**（区间 [0.844,0.925]，template 同为 0.886，argument-given-template 100%）。可观测上限 0.9750，故与上限之间尚余约 9 个百分点，首次出现方法间可比较的空间。
- 验证/对照：把那 14 维证据特征清零，五 seed 下 validation 由 0.8863 ± 0.0292 降至 **0.4738 ± 0.0315**，且两组区间完全不重叠（0.844 > 0.519），确认是生成的证据在起作用而非新捷径。九个模板的证据签名两两不同，且各自对应设计语义（MERGE margin=0.018、REACTIVATE dormant=0.822、RETRACT visible_empty、NOOP 三分之一带 pose/depth 故障）。
- 失败/局限：早期单 seed 消融中出现 “both zeroed” 61.3% 高于 “evidence zeroed” 48.1% 这一信息论上不可能的倒挂；五 seed 复核给出 evidence-zeroed 0.4738 ± 0.0315，与当初的 48.1% 一致，确认该倒挂是单次采样噪声而非数据缺陷。本轮只是全标签容量诊断，**尚未运行 A–F 方法比较**，因此不构成任何关于 CTL 的结论。`evidence_novel` 由生成器随传感器报告声明，尚未由每节点视角覆盖算出，是本轮证据通道里派生程度最弱的一项。参数检索仍近乎 oracle：审计新增实测字段 `reference_argument_decided_by_query` 取代原先的布尔断言。测试方面初次为 10/11，`test_m1_rollout` 取不到干净整模块运行；机器降频稳定后复跑，立刻暴露出一条被硬件损坏掩盖的真实缺陷——审计已把 `reference_arguments_independent` 布尔换成实测的 `reference_argument_decided_by_query`，但测试仍断言旧键（`KeyError`）。修正断言后该模块 15/15 通过，全套 11/11 全部一次通过。
- 环境/硬件定位：本机三天内三次内核态蓝屏（`0x3B`×2、`0x1E`，均为 `0xc0000005`），同类堆损坏在 Windows CPython 与 WSL Linux 下均出现，14 天零 WHEA。内存为单条 Samsung DDR5-5600 SODIMM，跑在 JEDEC 标称频率与 1.1V，无 XMP 可关；Windows 内存诊断标准模式通过、扩展模式在第一项 21% 处挂死无结论。改用本仓库自身负载做量化探针（`tmp/stability_probe.py`，同 seed 须给出同一 digest，可捕获不崩溃的静默损坏）：Performance 模式 12 次中 10 次失败（83%），把 Armoury Crate 切到 Silent 后频率由约 3509MHz 降至约 3133MHz（−11%），16 次中仅 1 次失败（6%），Fisher 精确检验 p≈2e-5。**内存不会因 CPU 降频而好转，故定位为处理器封装侧而非该 DIMM**，与 i9-14900HX 所属 Intel 13/14 代 Vmin shift 退化一致；微码已是 `0x12B`（只阻止继续退化，不修复已退化硅），BIOS 为 G614JIR.320 (2024-10-24)。注意 Windows 电源计划的“最大处理器状态”在本机无效（实测限到 40% 频率不变），只有 Armoury Crate 能控频。后续所有实验一律在 Silent 模式下运行，6% 残余失败率意味着 digest 校验必须保留；**LOG-014 全部数值、以及本轮在切换前产生的数值，均须在 Silent 模式下复核。**
- 结论/下一步：LOG-014 的 6.25% 不能作为 CTL 的负面证据——当时的任务两半都是查表，接口也拿不到必要信息。修复后 0.886 与 0.975 上限之间才有可比空间。`test_m1_rollout` 已补齐，全套 11/11 一次通过。下一步是在 Silent 模式下运行多 seed 的 A–F 比较（A 对 C、A 对 E），这是 D-031 的主对比；仍不开放 test、不进入 PNO/M2、不产生云费用。

<a id="log-016"></a>
### LOG-016—2026-09-06—A–F 预检：修正 future 项量纲，E 此前不可测（非正式）

- 类型/状态：M1-development，A–F 正式比较**尚未运行**；`formal_run=false`、`test_access=false`。本条只记录预检与一处实现缺陷的修正。
- 目的/白话：在跑 A–F 之前确认两件事——修好接口后还有没有方法间可比较的空间，以及 A–E 的控制是否真的只差监督信号。结论是空间有，但 `A_vs_E` 这个协议登记的主对比在修正前测不出任何东西。
- 空间与基线调优（10% 标签、五 seed、teacher-forced，validation 160 决策）：B 只用标签得 0.6013 ± 0.0294，可观测上限 0.9750，空间充足。为避免稻草人，对 C/D/E 各扫 `auxiliary/distillation_weight ∈ {0.1,0.3,1.0,3.0}` 并在 validation 上取各自最优（这偏袒基线，A 固定用协议的 1.0）：C 在四个权重下都是 0.610–0.624，与 B 的 0.601 基本持平，说明**把 future 当辅助回归项对候选选择贡献接近零**；D/E 在任何权重下都停在 0.19–0.24，远低于 B。
- 发现的实现缺陷：D/E 低于 B 的原因是 teacher 本身只有约 17% 正确，蒸馏把学生带偏。进一步核查发现 **E 的 teacher 与 D 逐位相同**，且把 scorer 的标签量从 40 加到 1600、步数从 1000 加到 3000 后数值**完全不变**。量纲测量给出根因：候选间 penalty 项跨度 0.700，而 `weights["future"] × 学到的 future MSE` 跨度只有 0.0032（比值 4.58e-03），直接验证 `argmax decided by penalties alone: True`。共享的 `energy.weights["future"]` 同时作用于两种量纲——A 的 future 是结构 token 计数（几十到几百），E 的是 32 维哈希特征上的 MSE（约 1e-3）——因此 E 静默退化成 D。这不是数据或训练不足，正式规模也修不好。
- 改变/固定：新增 `standardize_future_term()`，在每次决策内对候选做 z 标准化后再乘权重，使权重对两种方法含义一致；保留原始值于 `future_raw` 供审计。A 的能量组装改为先收集全部候选 future 再标准化。E 的 teacher 同样处理，但以 `standardize_future_term` 配置项门控，仅在 K=16 rollout 路径开启，旧 K=3 `ctl_dev` 路径行为不变。
- 修正后结果：E 与 D 的 argmax 一致率由 1.0000 降至 0.1330，E 不再是 D。A 的 teacher 仍为 1.0000（标准化保序，且其 future 项跨度仍约为 penalty 项的 3–5 倍，从 219 倍失衡变为合理量级差）。学生（10% 标签、五 seed）：A 0.8287 ± 0.0109、C 0.6162 ± 0.0318、B 0.6013 ± 0.0294、E 0.2175 ± 0.0269、D 0.2062 ± 0.0168。**A 由修正前的 0.8650 降至 0.8287，该降幅是修正量纲失衡的直接代价，说明此前 A 的部分优势来自 future 项的量级压制；正式报告一律使用修正后数字。**
- E 的规模曲线（修正后重跑，三 seed；修正前该曲线全程恒定，未测到任何东西）：teacher validation 由 40 标签的 0.1469 升至 800 标签的 0.2958，二十倍数据带来 +0.1490。但 train 同期升至 0.52，train/val 差距持续扩大，1600 标签加到 3000 步 val 反而下降。**瓶颈是过拟合而非数据量**。
- 结论/下一步：`A_vs_C` 可信且是实质结论。`A_vs_E` **在开发规模下不得报告**——修正前它测的是被淹没的 teacher，修正后仍是"完美 teacher 对不泛化的 scorer"，且 dev 规模低估 E 约一倍。运行正式 A–F 之前，E 的 scorer 需要正则化或容量调整，否则该对比是稻草人。测试：全套 11/11 一次通过（同时修正了测试统计脚本把 `NOPASS` 计为 `PASS` 的缺陷）。仍不开放 test、不进入 PNO/M2、不产生云费用。

<a id="log-017"></a>
### LOG-017—2026-09-06—E 的 scorer 受限于标签量而非正则化（非正式）

- 类型/状态：M1-development，A–F 正式比较仍未运行；`formal_run=false`、`test_access=false`。
- 目的/白话：LOG-016 修好 future 项量纲后，E 的 teacher 出现 train 0.52 / validation 0.25 的明显过拟合。在跑正式 A–F 之前先确认这是实现未调优还是方法本身的限制，否则 `A_vs_E` 是稻草人对比。
- 改变/固定：`OutcomeScorer` 增加可选 dropout，`train_outcome_scorer` 支持 `scorer_weight_decay`、`scorer_hidden_dim`、`scorer_dropout`，三者**默认值均为当前行为**，其他路径与历史结果不受影响；生成 teacher 时 `model.eval()` 关闭 dropout。这些是为正式规模预留的钩子，本轮未改变任何默认。
- 方法：从 40 个 train paired group 中按 `group` 完整切出 8 组作 inner-dev（sibling 不拆开），在 inner-dev 上选参，**validation 全程不参与选择**，因此报出的 validation 数字未经选择。网格为 weight decay ∈ {0,1e-4,1e-3,1e-2} × dropout ∈ {0,0.2,0.4} × hidden ∈ {32,64} × steps ∈ {300,1000}，共 48 组、每组 2 seed。
- 结果：inner-dev 上最优配置**就是现有默认**（wd=0、dropout=0、hidden=64、steps=1000，0.2078），所有加正则化、缩容量或提前停止的变体都更差（次优 0.2047，第三 0.1922，依次下降）。以该配置在全部 train 上重拟合、五 seed 评 validation 得 **0.1256 ± 0.0135**，低于 D 的 0.1656，仅高于随机的 0.0625——学出来的 future 项相对于只用 penalty 项是有害的。
- 根因更正：**瓶颈是标签量而非过拟合**，LOG-016 中"过拟合是binding constraint"的判断有误。核查确认 scorer 实际只见到 **160 个有标签决策**（协议 `main_label_fraction=0.1`），因为它只能在真值候选索引已知处训练。对照 LOG-016 的规模曲线：800 个标签时 teacher validation 为 0.2958，是本轮 160 标签下 0.1256 的两倍以上。
- 结论/下一步：`A_vs_E` **在开发规模下无法解决，且不是调参能解决的**；协议的 10% 是比例而非绝对值，故 E 的标签数随数据集规模增长，补救办法是运行正式规模。`A_vs_C` 不受此影响（C 无 teacher，仅有辅助回归项），该对比在开发规模即成立。仍不开放 test、不进入 PNO/M2、不产生云费用。

<a id="log-018"></a>
### LOG-018—2026-09-06—正式规模 A–F teacher-forced 预演（非正式，causal 未完成）

- 类型/状态：M1-development，**正式规模预演，不是正式 M1 gate**。仓库无正式运行入口（`resolve_af_smoke_config` 强制 `formal_run=false`），本条不消耗 gate、不触发 stop rule；`test_access=false`，未生成 test。
- 目的/白话：用协议要求的规模和五个登记 seed 跑一遍 A–F，看接口修复后方法之间到底差多少，并检验开发规模下"E 不可测"的结论是不是规模假象。
- 规模换算修正：按 `groups_per_family` 反推 paired group 数时，**每组实际只产出约 1.93 个稀有模板而非 2 个**——ambiguity pivot 会把 sibling 1 在该步的参考模板替换为对比模板，吃掉一个实例。首次按 500/100 组生成时 REPLACE 仅 963/1000 与 185/200，补到 540/120 组后全部达标。
- 数据（`outputs/m1_formal_dryrun/`，outputs 不入版本库）：train 540 组 21,600 决策、validation 120 组 4,800 决策，x 维 588；标签 10.00%、歧义 5.00%、可观测上限 0.9750；最稀有模板 train 1,041 ≥1,000、validation 225 ≥200。生成耗时 278s 与 68s（16 workers、约 115 组/分钟）。
- 教师一致率：train **0.999769**（21,600 中 5 次不同意）、validation **0.999792**（4,800 中 1 次）。断言已按 D-033 之外的设计决定改为记录，详见 `docs/01_research_contract.md` 新增小节；不同意集中在 sibling 1 的 pivot 前 horizon−1 窗口，且发生于两候选未来项近似打平、最小改动代价接管时。
- Run/结果（teacher-forced，五 seed [7,19,31,43,59]，validation 4,800 决策）：

  | 方法 | accuracy | template | identifiable | ambiguous |
  |---|---|---|---|---|
  | A CTL core | **0.9512 ± 0.0026** | 0.9537 | 0.9868 | 0.2758 |
  | B labels only | 0.9206 ± 0.0125 | 0.9286 | 0.9550 | 0.2675 |
  | C direct future loss | 0.9160 ± 0.0126 | 0.9243 | 0.9500 | 0.2700 |
  | D execute current only | 0.8953 ± 0.0156 | 0.9004 | 0.9280 | 0.2742 |
  | E learned scorer | 0.8827 ± 0.0133 | 0.8873 | 0.9148 | 0.2717 |

  `A−C=+0.0352`、`A−E=+0.0685`、`A−B=+0.0306`，三者五 seed 区间均不重叠。F oracle 上界 1.0000，随机基线 0.0625。
- 与开发规模的差异：LOG-016/017 的 A 0.8287 / B 0.6013 / E 0.2175 在正式规模变为 0.9512 / 0.9206 / 0.8827。数据由 400 增至 21,600 后**基线自身大幅提升，A 的领先由 +0.26 收窄至 +0.031**。E 的 scorer teacher 由 0.1256（160 标签）升至 **0.2616**（2,160 标签），学生由 0.2175 升至 0.8827，**确认开发规模下 E 的崩溃是标签量假象而非方法缺陷**；`A_vs_E` 至此才具备可报告性。A 的 seed 方差最小（±0.0026），与其教师覆盖全部 21,600 个决策、而 B/C 仅有 2,160 个标签一致。
- 读数注意：`identifiable_accuracy` 0.9868 高于 0.9750，并不矛盾——0.9750 是**总体**上限（`1−0.5×歧义比例`），identifiable 子集自身上限为 1.0、歧义子集为 0.5。报告时须分层给出，不得用子集准确率对比总体上限。另需注意**所有方法的歧义子集准确率均约 0.27，明显低于构造上限 0.50**，尚未解释。
- 未完成：**20-step causal self-rollout 未跑完**，用户中止以改用服务器。该指标（`final/mean_post_graph_correctness` 与 contamination/missing/false-birth/collateral 分项）才是协议主指标族，单步准确率不能替代它支持"减少长期 world-graph 污染"的主张。已实现断点续跑：每个 (方法, seed) 结果单独落盘于 `outputs/m1_formal_dryrun/causal/`。
- 结论/下一步：接口修复后 A 在正式规模仍领先且五 seed 区间不重叠，但**领先幅度远小于开发规模所示**，且尚无 causal rollout 与 paired bootstrap 置信区间，因此不构成任何 M1 结论。下一步在服务器上补跑 causal rollout 与 10,000 次 paired bootstrap；仍不开放 test、不进入 PNO/M2。

<a id="log-019"></a>
### LOG-019—2026-09-06—M1-v2 局部恢复、结构化 E 与评测语义闭环（非正式）

- 类型/状态：D-034 对应的架构实质变化与 train/validation 接线验证；M1-v2 仍为 `pretest_lock_candidate`，不是正式 gate，`test_access=false`。
- 目的/白话：旧 final 把“当前世界已经修好但历史留有错误版本”永久算错，也没有给模型一次真正可观察的改错机会；旧 E 又只看过正确候选的 descriptor。新接口让 exact ambiguity 后的下一次相关可见观察可以产生补偿 RELINK，并让 E 对全部 16 个候选回答“该候选声称的未来关系是否成立”。输入仍只有截至当前的 online world/observation/candidate program，输出分别是即时选择、当前 active world、证据支持、完整历史和恢复耗时；它不回填旧分数、不删除 provenance，也不是全图异步优化。
- 改变/固定：paired future 按每个 sibling 实际 primary/contrast policy 前进；teacher future 用 `10×active semantic + 1×open-memory support`，closed history 只审计；每个 sibling 增加一个错误 pivot 分支上的 recovery 训练例，online causal 链在下一步使用同一固定 K=16 自然提供补偿候选。E 的 relation scorer 读取实际 reference future 为全部 K 构造稠密标签，但不读取候选 post-world、executor legality 或 collateral；C 共用目标作 direct future auxiliary。validation group 固定分 calibration/report，A–E 共用一个阈值；主终态改为 active correctness，history-exact 仅兼容诊断。生成、训练、导出分别记录 HEAD/dirty/diff/source tree、protocol 和数组 digest。
- 配置/数据/版本：活动配置 `m1-hard-condition-v2`、dataset `m1-paired-latent-worlds-v4-recovery`；本机仅生成 2 train groups（84 行）和 4 validation groups（168 行），seed=7、student/scorer=2 updates，用于接线而非性能。test 未生成/读取。
- 验证/结果：生成阶段 teacher/reference agreement 为 1.0；最小完整 causal smoke 的 report 半区含 3 paired groups/6 sequences。observable-information oracle 强制两个不可辨 sibling 作同一个 pivot 选择，结果 final active=1.0、mean active=0.975、final history=0.5、final contamination=0、recovery-within-3=1.0、平均 1 步恢复。这证明局部证据、补偿候选与 active/history 指标语义闭环；history=0.5 正是错误版本仍被保留，而不是被“洗白”。F oracle active/history 均为 1.0。仅 2 updates 的 A–E 全部 final active=0，按设计不解释为科学结果。
- 测试/修复：相关 43-test 运行曾有 1 个旧断言失败；原因是该断言依赖“contrast sibling 被错误地按 primary future 前进”制造的伪 `REFERENCE_PROGRAM_CONSTRUCTION` 失败。改为正确分支 policy 后，测试现在验证真实 causal branch failure 仍统一 `QUARANTINE_KEEP_CURRENT_WORLD`，且伪构造失败不再出现。随后相关 2 tests 与不触发重生成的 18 个协议/指标/provenance tests 通过。用户提示本机 CPU 负载可能导致内存损坏，因此未在本机重跑全套；完整测试和足量训练改到 AutoDL。
- 失败/局限：`now` 仍弱，`collateral` 仍与 protected/illegal 高度冗余；learned A–E 尚未证明能利用恢复例；validation 小样本的 hash 半区不保证正好 50/50；全局多对象 reconciliation 未实现。当前所有结果均来自 dirty 开发树，不能作为可复现实验数字。
- 结论/下一步：可观测可达范围不再被 history-exact 错误压成零，E 的 15/16 候选零监督缺口也已从实现上关闭。下一步先提交干净树并推送，由 AutoDL `git pull` 后运行全套测试、足量 train/validation A–F、共享 commit calibration、20-step causal rollout 与 10,000 次 paired bootstrap；通过后才考虑重新冻结 M1-v2。仍不开放 test、不进入 PNO/M2。

<a id="log-020"></a>
### LOG-020—2026-09-06—M1-v2 首次服务器全测失败与预生成修正

- 类型/状态：需要保留的服务器失败 run 与后续工程修正；不是方法负结果，不是 M1 gate，`test_access=false`。
- 失败证据：AutoDL 在提交 `f0d3357` 上执行 `python -m unittest discover -s tests -v`，139 个测试中 3 个失败，均来自 `test_m1_trainability`。生成数据已由每个 sibling 20 个 online decision 加 1 个 recovery training example 变为 21 行，但 `subset_paired_array_groups` 仍断言 `paired_groups*2*20`；2 groups 实际 84 行、每 sibling 21 行、recovery 4 行，`relation_targets=(84,16,18)`。因此失败是行数合同没有同步，不是训练或 CTL 数字；昂贵 v4 数据尚未生成。
- 修正：paired subset 与各 runner 的 online/recovery/learning-row 计数改为从数组和注册 horizon 推导，不再新增 `21` 魔数；counterfactual future 不再按 template 取第一个合法候选，而是重建 `primary`/`contrast_noop` 策略并按 canonical post-state signature 唯一匹配，未来若修改 pivot contrast 必须显式扩展；E 的 protected-touch penalty 改为复用 executor 同语义的结构化 ID 提取，不再在 operations repr 中做子串搜索；endpoint bootstrap 配置明示为一层 mixed 20-step stratum。
- 指标澄清：注册的 `recovery_rate_within_window` 只以“pivot 后状态恰为另一个 sibling reference 所覆盖的错误状态”为 eligible；另报 designed trigger、out-of-scope pivot error，以及 arbitrary-first-error recovery，避免早期无关错误占掉恢复分母。当前 fixture 只验证预设重访到达后的改正，不声称学会触发检测，也不声称覆盖其余 14 个 pivot 候选。
- 验证：本地仅做变更文件 `py_compile`、JSON 解析与 `git diff --check`，均通过；因本机原生稳定性风险，未运行全量测试。下一步把干净提交推到 AutoDL 重跑全套；通过前不生成正式 v4 arrays。A 的 `10×active/1×open-memory` 对 `1×/1×` 消融保留为全测通过后的低成本预注册消融，不在这次故障修复里改变主 teacher。
- 首次重跑补充：提交 `ee7eed2` 的全测在 executor 模块结束、进入 `TestM1AFCausalRollout.setUpClass` 后长时间无输出。原因不是死锁，而是该提交把 canonical signature catalog lookup 错误地用于每个 primary future step，使原本一次 reference execution 膨胀为反复 K=16 执行。随后的修正恢复 primary 的单事务直执行，只让真正的 paired contrast policy 做 K=16 signature 唯一匹配；该次被人工中止的 run 不产生测试通过结论。
- 第二次重跑：性能修正提交 `f0097a0` 在 AutoDL 完整运行 141 tests、129.485 秒；其中 138 项通过，3 项在同一 trainability subset 路径报 `KeyError: 'ambiguity'`。根因是完整性检查误写字段名，数组合同实际使用 `ambiguous`；现改为正确字段，并在 recovery arrays 缺该必需标签时给出明确断言。这仍是单一工程错误，不是三种独立失败或方法结果。
- 最终验证：用户确认 AutoDL 在干净提交 `aed1946` 上全套测试全部通过；141 项中的 executor、M1-v2 rollout、A–F adapter、observable oracle、recovery 分母、protocol 与 trainability 路径均通过。该结果关闭实现阻塞，但仍只是工程验证，不构成 CTL 有效性或 M1 go/no-go 结果。

<a id="log-021"></a>
### LOG-021—2026-09-06—M1-v2 upper-bound/calibration pretest smoke

- 类型/状态：M1-development 非正式 smoke；生成、训练、causal replay 与结果导出完整，`formal_run=false`、`test_access=false`，不作 go/no-go 判定。
- 数据/provenance：生成与训练来自干净提交 `3104359`；train 10 paired groups = 400 online rows + 20 recovery rows，validation 4 groups = 160 online + 8 recovery，seed=7，student/scorer=60 updates。train/validation teacher-reference agreement 均为 1.0；导出结果为 `results/m1-v2-pretest-smoke-20260906T102332Z.json`，结果提交 `bc72d10`。
- 上限与接线：report 半区含 3 paired groups/6 sequences。observable-information oracle 的 mean active=0.975、final active=1.0、final contamination/missing=0；designed eligible=3/6、recovery-within-window=1.0、平均 1 步，out-of-scope=0。final history/open-memory=0.5，说明旧错版本仍被保留而 active world 已修复。
- 学习读数：teacher-forced A/B/C/D/E 准确率分别为 0.4667/0.3750/0.3417/0.3250/0.0667，E scorer teacher=0.0500。causal A–E 的 final active 均为 0；A mean active=0.0833、contamination=2.5，C contamination=18.33，E contamination=32.5。这些数字只有 3 个 report groups、1 seed 和 60 updates，不支持方法比较。learned 方法的 designed eligible 均为 0、out-of-scope fraction=1，原因是它们在 pivot 前已偏离且 pivot 后状态不是有界 sibling error state；这不等于候选恢复路径失败。
- 阻塞/无效项：commit calibration 报告 42 calibration learning rows，正确的 online 分母应为 40；多出的 2 条是 calibration groups 内的 synthetic recovery examples。因此选出的 probability=0、margin=0 以及依赖该阈值的 paired contrasts 均不可作为结论。
- 修正/下一步：calibration 和 report 均排除 recovery-only training rows；online feature 与 E penalty 共用 executor-style 结构化 protected-ID 匹配。新增 structured relation-target oracle，在不执行候选的边界内检验 E 的目标本身是否足以排序；它不是 E 成绩或 F oracle。先在服务器跑全测，再重跑同一 10/4 smoke，不生成正式 v4/test。

<a id="log-022"></a>
### LOG-022—2026-09-06—M1-v2 corrected calibration 与 relation-target oracle retest

- 类型/状态：M1-development 非正式 retest 完成；`formal_run=false`、`test_access=false`，不作 go/no-go。
- 数据/provenance：生成、训练和导出均来自干净提交 `318c5a1`，source-tree hash 一致；结果为 `results/m1-v2-retest-318c5a1-20260906T105905Z.json`，提交 `8460444`。train=10 groups/400 online+20 recovery，validation=4 groups/160 online+8 recovery，seed=7，60 updates。train/validation arrays digest 与 LOG-021 逐位一致，证明该数据在两个干净代码版本上确定复现；protected-ID 修复未改变这批没有前缀碰撞的实例。
- 校准：`calibration_rows=40`、`report_rows=120`、`excluded_recovery_training_rows=8`，正确排除所有 recovery-only rows。选出的共享 gate 仍为 probability=0、margin=0，calibration commit rate=0.90；这是现有小样本的有效重算，不是 formal gate。
- E 诊断：structured relation-target assembled oracle 在 120 个 online report rows 上为 0.8083，template=0.8083、argument-given-template=1.0；E scorer teacher=0.0500，E student=0.0667，causal raw-invalid selection=0.95。因此“目标完全没信息”已被排除；当前首要瓶颈是 scorer 优化/泛化，同时 target+组装仍有 19.17% 模板选择缺口。该 oracle 使用真实 future，其 ambiguous=0.8333 不是可部署在线上限。
- 学习与 causal：A/B/C/D/E teacher-forced 为 0.4667/0.3750/0.3417/0.3250/0.0667，与 LOG-021 一致。A–E final active 均为 0；A mean active=0.0833、contamination=2.5，C/E contamination=18.33/32.5。paired report 只有 3 groups 且 active effect=0，不作性能结论；10,000 次 bootstrap 不会增加独立样本。observable oracle 仍为 final active=1、designed recovery=1、time-to-recovery=1 步。
- 结论/下一步：校准泄漏已关闭，E 问题已缩小到可诊断范围。后续不再靠对话临时给顺序；按 [M1-v2 收口执行流程](experiments/counterfactual_transaction_learning/M1_V2_CLOSEOUT_FLOW.md) 从 S1 执行，先补 target-only/并列、E train/calibration BCE/accuracy 和 oracle illegal-rate，再进固定数据的 5-seed 优化曲线。

<a id="log-023"></a>
### LOG-023—2026-09-06—S1 target/assembly/scorer 诊断实现

- 类型/状态：M1-development 诊断代码实质变化，提交 `89a7b3d`；服务器全测和干净 diagnostic retest 尚未运行，S1 未关闭。
- 实现：新增 target-only relation diagnostic，只按 raw masked mismatch 报 reference-in-minimum、unique-reference、tie size 和 uniform-tie expected accuracy；不加 penalty、不标准化、不用 executor 合法性选候选。selection decomposition 新增 `raw_illegal_selection_rate`，合法性只事后审计。E scorer 新增 train-all、train-online、validation-calibration-online、validation-report-online 的 masked BCE、masked binary accuracy、teacher accuracy 和事后 illegal rate，并保留训练 trace。
- 不变边界：没有修改 relation target、E 的 BCE 训练、标准化、能量权重、K=16、数据、candidate order、commit gate、主指标或效应门槛；没有生成或读取 test，也没有重复 causal rollout。
- 本地轻量验证：四个改动 Python 文件通过 `py_compile`；两个新增纯诊断单测直接通过。读取现有 120 条 validation report rows 的非正式预览为 target-only reference-in-minimum=1.0000、unique-reference=0.6333、uniform-tie expected=0.8139、mean tie=1.3833、max tie=3；同一 assembled oracle 的事后 illegal-selection=0.1417。该预览不是干净提交上的导出报告，不用于关闭 S1。
- 下一步：AutoDL 在干净提交上运行 143 个全套测试；通过后复用 `outputs/m1-v2-retest-318c5a1-20260906T105905Z/{train,validation}.npz`，只跑 seed 7、60 updates 的 teacher-forced diagnostic retest 并导回结果。依据 train/calibration BCE 与 teacher accuracy 决定进入 S2 还是先处理 target/assembly。

<a id="log-024"></a>
### LOG-024—2026-09-06—解除 E scorer/student 更新数绑定并细分 rollout 失效

- 类型/状态：M1-development runner/诊断代码实质变化，提交 `64d9ea2`；尚待 AutoDL 全测和干净报告，不改变正式方法或 gate。
- 新线索：外部只读 scratch probe 报告在 6 train/2 validation groups 上，E teacher 随 scorer steps 60/600/3000 为 0.0476/0.6190/0.5833。因其数据规模不同、未导出逐例结果和 provenance，本仓库不把它当正式证据；它只支持优先检验优化预算与数据量的交互，并撤回任何 K=3 与 K=16 smoke 的等规模性能比较。
- 接口修正：`run_m1_af_scaled.py` 新增独立 `--scorer-steps`；`--student-steps` 继续对 A–E online student 完全一致，E 的额外 scorer updates 在报告 `training_budget` 中单列。省略新参数时仅为兼容旧命令沿用 student 值。合同原已允许 E 额外 scorer 更新、耗时和参数单列，因此没有改公平性定义。
- 新分解：relation oracle 报 `exact_ambiguity_capped_accuracy`，把不可辨 paired pivot 的 future-reading 成绩封顶为 0.5，但明确不称 E 严格理论上限；template error 拆成非法候选和合法但错模板。causal 指标新增 `initial_step_raw_invalid_selection_rate`，与全轨迹 invalid 并列，区分初始策略错误与 self-rollout 漂移后的复合失控。
- 本地轻量预览：现有 120 report rows 上 relation oracle 的 19.17% template error 可拆为 14.17% 非法错模板与 5.00% 合法错模板；exact-ambiguity capped diagnostic=0.7917。语法、diff 和纯诊断测试通过；这些仍需干净服务器报告确认。
- 流程调整：S2 改为 student=1000 固定，scorer steps {300,1000} × train groups {10,40} 的 teacher-forced 2×2，使用共同 validation 且只按 calibration/inner-dev 选择；连同既有 60-update smoke 累计不超过每方法 6 次 validation trial。held-out BCE early stopping 仍是 proposed，未写入训练协议前不得启用。

<a id="log-025"></a>
### LOG-025—2026-09-06—S1/S2 train/inner-dev 隔离与旧 report 退役

- 类型/状态：M1-development 数据选择/runner 实质变化，D-036 accepted，提交 `58b5d6f`；尚待 AutoDL 全测和干净 S1 报告。
- 问题：最初的 relation/target-only oracle 在 validation report rows 上计算，LOG-022 又据此决定继续优化 scorer，已经违反“report 不作选择”的意图；流程同时声称 S5 才首次查看 report，不再成立。此前也没有真正的 train/inner-dev 代码，若用 validation 扫 scorer steps × groups 会挤占 6-trial 预算。
- 修正：新增 `training_inner_dev_mask`，按 canonical train paired-group ID 的 SHA-256 `mod 5 == 0` 固定留出完整 group，siblings 与 recovery rows 不拆。新增 `run_m1_scorer_diagnostics.py`，输入只有 train arrays；在 fitting groups 上训练 E scorer，在 inner-dev 上报告 target-only、assembled oracle、masked BCE、binary/teacher accuracy、非法选择分解和 trace。报告显式记录未读 validation、未消费 validation trial、未训练 student、未校准 gate、未跑 causal。
- validation 状态：旧 4-group report 仍作为历史事实保留，但以后不再用于方法/checkpoint/S5 go-no-go。S4 必须在机器 config 中登记不重叠的新 validation confirmation group range，S5 才能对其 calibration/report 各执行相应的一次性职责。test 仍未生成或读取。
- 曲线/早停：S2 在 train/inner-dev 上做 scorer steps {300,1000} × total train groups {10,40}；若更大数据仍有收益，S3 在最大 group 点复扫两个 steps，避免顺序坐标搜索。early stopping 继续标 proposed，未固定 patience、最大步数和 checkpoint tie-break 前不启用。
- 本地验证：新脚本 `py_compile` 与 `--help` 通过，合成 group 的 inner-dev 完整性检查通过。功能 smoke 因本机仅有旧 protocol 的 v2 arrays 而被 manifest guard 正确拒绝；不绕过哈希，留待 AutoDL 使用 `3820f5e0…` 的现有 train arrays。全套测试尚未在本机运行。
- 下一步：AutoDL 对最新干净提交运行预计 144 项测试；通过后执行 seed 7、scorer 60 steps 的 train/inner-dev S1 run 并导回。根据 fitting/inner-dev BCE 和 teacher accuracy 进入 S2 或回到 assembly/target 分支。

<a id="log-026"></a>

### LOG-026—2026-09-06—S1 train/inner-dev 结果与 S2 可比性补强

- 类型/状态：M1-development scorer-only 诊断完成；S1 关闭并进入 S2。结果文件为 `results/m1-v2-s1-innerdev-7518f99-20260906T120940Z.json`，结果提交 `67f739d`；`formal_run=false`、`test_generated=false`、`causal_complete=false`，不构成 M1 go/no-go。
- 数据/provenance：复用 generation commit `318c5a1` 的 train arrays，digest=`483b389a94eb666d347bff472fdeb97180ca0d1291354beac9b0e52259e144e3`，协议 hash=`3820f5e06e27989dc87f3c887b147eefe3be0a6f7bb01a72bbbba708709b49bb`。训练和导出均来自干净提交 `7518f99`、source-tree hash=`679e89eb1364ab01bed43b89d9969efb58f5931cfbeda0470ca7ffdccac26d49`。报告明确 `validation_arrays_read=false`、`validation_report_partition_accessed=false`、`validation_trial_consumed=false`；没有训练 online student 或运行 causal。
- 分母/设置：train 共 10 paired groups，固定哈希留出 group 1；fitting=9 groups/378 learning rows，inner-dev=1 group/42 learning rows，其中 online chain=40。seed=7，scorer=60 updates，耗时 1.13 秒。由于 inner-dev 的独立单位只有 1 个 paired group，本轮只决定后续诊断分支，不估计稳定泛化性能。
- target/assembly：inner-dev target-only 的 reference-in-minimum=0.95、unique-reference-minimum=0.25、uniform-tie expected accuracy=0.60、mean/max minimum-set size=1.7/2；说明结构化关系目标通常能把 K=16 缩到一对，但多数行不能唯一决定正确候选。使用正式标准化与 no-execution penalties 后，relation oracle accuracy=0.575、identifiable=0.5789、ambiguous=0.5、argument-given-template=1.0；错误中 illegal wrong-template=0.375、legal wrong-template=0.05。旧 validation report 的 0.8083 与该单-group 0.575 暂不能解释为真实性能变化，只证明必须报告组间波动。
- scorer：online fitting/inner-dev masked BCE=0.2612/0.2706，binary accuracy=0.9007/0.8925，teacher accuracy=0.05/0.05，raw illegal selection=0.45/0.85。接近的 BCE 与极差排序同时表明逐关系 binary accuracy 被负类占比主导，60 updates 尚未把关系预测转化为候选排序；但 assembled oracle 本身也有高 illegal rate，不能把 E 的全部缺口只归为优化不足。
- 结论/分支：不重构 relation target；按既定 S2 跑 scorer steps {300,1000} × train groups {10,40}。进入下一次服务器 run 前，诊断 runner 增加 `--paired-groups`，使一份 40-group arrays 可确定性截取同源 10/40 规模，并增加 target/oracle/scorer 的逐 inner-dev-group 报告。它只提高开发曲线的可比性，不改 target、energy、loss、K、候选、protocol 或 test seal；共同 group 1 用于直接规模对照，40-group aggregate 的 8 个 held-out groups 用于观察组间波动。
- 下一步：在本地只做语法、边界单测与 diff 审计；提交后由 AutoDL 先跑全测，再生成 40-group train arrays 并运行四个固定 S2 点。若 scorer 随 steps/groups 接近 oracle，则继续选定预算；若 scorer 已贴近仍低且高-illegal 的 oracle，则在 test 前回到 assembly/声明约束分支并重新登记任何公式变化。

<a id="log-027"></a>

### LOG-027—2026-09-06—S2 静态预检审计与 2×3 曲线准备

- 类型/状态：M1-development 诊断/runner 架构实质变化已完成，提交 `742c2f4`；D-037 accepted。尚未在服务器生成新数组或取得 S2 科学结果，不构成方法改进证据或 M1 go/no-go。
- 目的/假设：检验 relation target 的并列中有多少非法候选可仅靠当前世界与事务文本静态拒绝，并把 target/assembly 的固定诊断从单个 inner-dev group 扩到全部 selected train；同时用同源 60-step 锚点补齐 scorer steps 与 train groups 的二维曲线。白话说，它先查“错误答案是不是在动手前就能看出不合规”，再查 E 是没训够还是数据不够，不把 executor 跑完后的答案偷给在线模型。
- 实现/边界：`preflight_transaction` 只运行 graph/header/base-version/duplicate transaction、template-level precondition 与 protected-ID 检查，不应用 operation、不产生 `post_graph`；返回通过不等于最终合法。generation 新增 static-preflight pass/failure 与 executor failure code；`candidate_legal` 只作事后审计标签。诊断报告非法召回、合法误拒、剩余非法、effective K、template/failure 分解、非法最小集合成员及过滤前后 target-only/assembled oracle；过滤 mask 不进入 A–E、teacher、loss、student 或 causal 选择。
- 数据选择：target-only 与 assembled oracle 改为在全部 selected train online rows 上报告 aggregate 和逐 paired-group 数字；scorer 仍只在 fitting groups 训练、在固定 SHA-256 inner-dev groups 报泛化。S2 使用同一份 40-group train arrays 的确定性前缀，固定 seed 7，完整扫描 train groups {10,40} × scorer steps {60,300,1000}；不读 validation/report/test，不训练 online student、不校准 gate、不跑 causal。
- 本地验证：`py_compile`、`git diff --check`、静态预检只读/通过不等于执行成功的 executor 单测，以及生成数组/过滤诊断两个定向 M1 测试均通过；两个 M1 定向测试耗时 32.424 秒。依用户关于本机 CPU/内存风险的提示，未在本机跑全套测试或生成 40-group 数据；全测是 AutoDL 运行的前置 gate。
- 局限/治理：外部 scratch 使用 executor `candidate_legal` 得到的 94.4% 仅是禁止部署的上界，不进入仓库正式结论。即使 static preflight 在 S2 中表现良好，启用它作为共享 online admissibility mask 仍须新 decision、修改方法合同/protocol hash 并从 S1 重跑；D-037 不授权事后打开过滤。
- 下一步：在 AutoDL 拉取含本条记录的干净提交，先跑全套测试；通过后重新生成带新 audit 字段的 40-group train arrays，运行六个 S2 点并逐个导出 provenance 完整的 JSON。根据预先登记的分支表，先判断静态预检是否值得提出方法变更，再区分 scorer 优化不足、数据多样性不足或 assembly 上限不足。

<a id="log-028"></a>

### LOG-028—2026-09-06—S2 seed-7 scorer 二维曲线与静态预检触发

- 类型/状态：M1-development、train-only、scorer-only 的 S2 诊断完成；六份结果由提交 `ea25201` 导回，代表文件为 `results/m1-v2-s2-g40-s300-c4f5df4-clean.json`。`formal_run=false`、`test_access=false`、`validation_arrays_read=false`、`validation_trial_consumed=false`、`causal_complete=false`；本轮不构成 M1 go/no-go。
- 数据/provenance：AutoDL 在干净提交 `c4f5df4ba4a4b61ff7604736b5460f8497997a38` 生成、训练并导出；protocol hash=`3820f5e06e27989dc87f3c887b147eefe3be0a6f7bb01a72bbbba708709b49bb`，dataset=`m1-paired-latent-worlds-v4-recovery`，40-group arrays digest=`f68205b58a6d4a97f92e3432b0d1d3515a5b739a5b226994e4030515b930d7b0`，共 1,680 learning rows（1,600 online + 80 recovery）。六点均用 seed 7、16 threads，并从同一 arrays 确定性截取前 10/40 groups；10/40 视图 digest 分别为 `5e5ce0243d29e4cbda0c67cc6ec5d845205a9e6a11322addbd2111aac084d764`/`7a4c0ea1e336c4144fc6b8d6bb8cefe944c70bdbefdb425a61a9e5e4f5fd1683`。
- static preflight 审计：40 groups 的 25,600 个 candidate slots 中，executor 判非法 2,552 个（9.96875%）；只读 preflight 拒绝 2,552 个，非法召回=1.0、precision=1.0、合法误拒=0、通过后剩余非法=0、reference pass=1.0，effective K 均值=14.405（范围 12–15）。非法来源为 BIND 1,600、REACTIVATE 770、RELINK 182；PreconditionError 770、ProtectedMutationError 1,782，均被召回。白话：这些候选在真正改图前，仅看当前世界和事务声明就能确定不合规；这不是执行候选得到的未来答案，也不代表所有未来非法情形都会被预检覆盖。
- target/assembly：未过滤 target-only 的 reference coverage=0.99125、unique=0.55875、均匀并列期望=0.77292、平均并列数=1.445；静态过滤后 coverage 不变，unique=0.9525、均匀并列期望=0.96979、平均并列数=1.05125。正式能量组装的未过滤 accuracy=0.74375、illegal selection=0.20875、exact-ambiguity capped=0.7275；过滤诊断上界分别为 0.9525、0、0.9275。最小 relation 集合包含非法候选的行占 0.39375；非法并列成员的平均 penalty=0.05，低于合法并列成员的 0.14946，说明当前 assembly 会在关系 mismatch 并列时系统性偏爱声明更少的非法程序。
- scorer 曲线：inner-dev 结果如下；“filtered teacher”只是在相同 scorer 输出上事后施加 static mask 的诊断，不是本轮 E 方法。

| train groups | scorer steps | inner-dev BCE | teacher | illegal selection | filtered teacher |
|---:|---:|---:|---:|---:|---:|
| 10 | 60 | 0.2706 | 0.0500 | 0.8500 | 0.1000 |
| 10 | 300 | 0.0996 | 0.3750 | 0.5500 | 0.8750 |
| 10 | 1000 | 0.1517 | 0.6250 | 0.3000 | 0.8750 |
| 40 | 60 | 0.2702 | 0.0500 | 0.4938 | 0.0625 |
| 40 | 300 | 0.1016 | 0.5688 | 0.2406 | 0.7469 |
| 40 | 1000 | 0.0744 | 0.5031 | 0.2625 | 0.7094 |

- 解释/不确定性：60→300 steps 明确解除欠优化；40 groups 上 300→1000 虽继续降低 held-out BCE，却降低候选级 teacher accuracy，表明逐关系 BCE 与最终候选排序并不完全一致，不能只按 BCE 选预算。共同 inner-dev group 1 在 10/40 groups、300/1000 steps 的 filtered teacher 均为 0.875，没有显示扩大训练数据的清晰收益；10-group 仅一个 inner-dev group，所有性能判断仍受单 seed 与组间波动限制。300 steps 只是进入多 seed 比较的候选，不是已冻结最优点。
- 治理结论：D-037 的“高非法召回且零/近零合法误拒”触发条件已经满足，但 D-037 只授权审计。0.9525 是使用真值 relation target 加事后静态过滤的 oracle 诊断，不是 E、A 或 CTL 的成绩。不得在现有 protocol hash 下直接启用 mask，也不得据此进入 S3 或正式 causal。
- 下一步/人工事项：先决定是否提出新 decision，将同一个只读 static preflight 作为 A–E 共享 online admissibility mask。若接受，须同时修改方法合同与 protocol hash、保持 test 封存并从 S1 重跑，然后在 40 groups 上对 300/1000 steps 补齐登记 seeds；若不接受，则留在未过滤方法边界内修复 assembly/声明约束。只有该边界闭合且多 seed 结果明确后，才按流程判断是否需要 S3。

### LOG-029—2026-09-07—D-038 共享 static-preflight mask 合同与本地实现

- 类型/状态：M1-development 方法边界与架构实质变化完成；D-038 accepted，本地相关测试通过，干净服务器全测和新协议实验尚未运行，不构成 M1 go/no-go 或 E 性能结果。
- 目的/白话：共享 online admissibility mask 解决“事务在不改世界前就已能确定违反版本、前置条件或 protected state，却仍只让 no-execution baseline 为它分配概率”的不公平。输入是 immutable prior world、candidate program、截至当前证据和 protected IDs，输出是在原 K=16 槽位上的允许/拒绝值；例如 BIND 明写要碰 protected node 时，A–E 都在 softmax 前把它置零。它不执行候选、不产生 post-edit world、不保证 pass 项合法，也不删除 failure/provenance 或 executor illegal。
- 决策/合同：`docs/DECISIONS.md` 追加 D-038；活动合同登记 A–E 在训练归一化、online softmax、共享 calibration 与 commit selection 共用 `transaction_static_preflight_v1`。机器 config 升为 dataset `m1-paired-latent-worlds-v5-shared-static-preflight`，protocol hash=`34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a`；K、target、energy weights、executor、recovery、主指标/门槛和 formal seeds 不变。
- 实现：`dev_learning.py` 新增共享 mask/renormalization helper；E scorer 与 C relation auxiliary 的逐关系训练分母排除预检拒绝候选，A–E student 的有标签 CE、KL、inference probability 共用同一 mask。joint/isolated/scaled/trainability/历史 target-comparison 路径均改用 mask；causal rollout 从每一步重新 materialize 的候选读取只读 preflight flag，若选择被静态拒绝项立即失败。calibration 拒绝任何给预检失败候选非零概率的 run。
- 诊断/白话：新增 target-discriminative BCE、ranking-relevant BCE、互补分母，以及 reference 对最佳错误候选的 probability/log-probability margin。它解决总体 BCE 是否被容易而不区分候选的位置主导；输入是 relation logits、真实 reference future、候选声明和共享 mask，输出是分解损失与排序 margin。例如只有正确 RELINK 支持新位置的坐标进入判别性分母。它只读 train/inner-dev，不改 scorer loss、不用 reference index 训练，也不表示 listwise loss 已采纳或有效。
- 不变量/报告：K=16 槽位不重排；reference 必须 pass、每行至少一个 admissible；`remaining_executor_illegal_candidates`、合法误拒、effective K 和 failure/template 分解常驻。`preflight pass` 明确不声称 executor legal；A/D/F 的执行后 illegal 正无穷 mask 与六项能量继续保留。scorer/AF 报告 schema 升到 v3，并明确 shared mask/illegal-retention 元数据。
- 本地验证：`py_compile` 通过；protocol validator 和 11 个 protocol tests 通过；16 个 `test_m1_af_rollout` 通过；`test_ctl_dev`＋`test_m1_trainability` 共 15 个通过，总计 42 个不重复相关测试。测试中的既有小型 in-memory validation fixture 只验证接线，不读取已保存 validation arrays/report、不用于方法或预算选择，因此不消耗 validation trial。未运行全仓库测试、数据生成或训练。
- provenance/边界：D-038 合同/实现提交=`5939b16`；旧 v4 arrays/report 因 protocol hash 不匹配不能作为 D-038 后成绩。`test_access=false`，未生成或读取 formal test；未训练正式 student、未校准 gate、未跑正式 causal，未进入 S3/M2。
- 下一步：先形成干净 Git 提交并在服务器跑全测；成功后只生成 v5 40-group train arrays，先以其 10-group prefix 跑 S1 60 steps/seed 7，再跑 40 groups × scorer steps {300,1000} × seeds {7,19,31,43,59}。主选择量是 shared-mask 后的 inner-dev candidate ranking，按 paired group 比较；1000−300 的 95% CI 下界大于 0 才选 1000，否则选 300。BCE/margin 只用于决定是否另立 scorer-loss decision。

### LOG-030—2026-09-07—D-038 运行前解释、随机地板与残余影响上界收口

- 类型/状态：M1-development 诊断与预登记补强，提交 `e344422`；不改变 D-038 方法边界、loss、预算、dataset version 或 protocol hash。干净服务器全测和任何 v5 数据/训练尚未运行，不构成性能结果。
- 预登记方向：共享 mask 主要增强旧 E，因此在运行前明确预期 v5 的 A−E 单步与 causal margin 相对 v3/v4 历史读数缩小，主对比触发 stop rule 的概率上升。若 margin 不缩小或仍过门槛才是更强证据；结果出来后不得把任一方向事后改写成原假设。
- 随机地板/白话：旧脚本的固定 `1/16` 已改为 admitted-uniform random accuracy。它解决每行有效候选数不同后随机基线失真的问题；输入是逐行 static-preflight mask，输出是先算每行 `1/K_i` 再求平均。例如两行分别剩 2 和 4 个候选时结果为 0.375。它不等于 `1/平均 K`，也不读取 reference 或 executor legality。scorer-only 与 scaled 报告均常驻该值。
- NOOP 不变量：新增生成数据单测，要求每行至少含一个 NOOP 且所有 NOOP 通过 static preflight；这把“不会全部拒绝”从隐式生成器性质变成回归测试。mask helper 的全拒绝异常仍保留，避免静默产生无定义 softmax。
- BCE 主次：报告新增 `scorer_diagnostic_policy`。预算唯一主选择量仍是 shared-mask inner-dev candidate-ranking accuracy；在解释 loss mismatch 时，`ranking_relevant_bce` 是主 BCE 诊断，`target_discriminative_bce` 是次级解释量。两者冲突不改预算规则；只有 ranking-relevant BCE、reference margin 与实际排序的多 seed 共变支持另立 loss decision。
- 残余影响/白话：`maximum_teacher_decision_change_rate_due_to_residual_executor_illegal` 统计“至少含一个预检通过但执行失败候选”的决策行比例，是 executor illegal 通道最多能改变多少 teacher 选择的严格上界。例如 100 行只有 3 行含残余非法项，上界为 3%。没有直接构造所谓“A 去掉 illegal 的 teacher”，因为执行失败候选没有 post-edit world，其 future 能量未定义；硬设为 0 会虚构反事实。若以后该上界非零且实质，再以新 decision 定义额外对照。
- 验证：修改文件通过 `py_compile` 与 `git diff --check`；`test_m1_af_rollout` 18 项、`test_m1_protocol` 11 项、`test_ctl_dev` 11 项和 `test_m1_trainability` 4 项，共 44 个不重复相关测试通过。未在本机跑全仓库测试、生成数据或训练；服务器全测按新增两项测试预期约 152 项，以服务器实际 discovery 数和最终 `OK` 为准。
- 边界/下一步：`test_access=false`，未读取 validation report/test。推送截至本提交的干净 main 后，服务器先核对实际仓库路径和 commit，再单独运行全测；只有全测退出码 0 才生成 v5 train arrays 并重跑 S1。

### LOG-031—2026-09-07—v5 train arrays 与 S1 shared-mask 重跑

- 类型/状态：M1-development、train/inner-dev、scorer-only 的 v5 S1 重跑完成并通过产物验收；服务器全测先行通过。结果仍在服务器 ignored `outputs/`，尚未通过 exporter 导入 `results/`，因此本条记录使用服务器 manifest/report 的终端验收数字，不冒充正式 gate。
- 数据/provenance：干净提交 `72afa7da33e0465e6e45d57e2a9675248ac65447`、protocol hash=`34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a`、dataset=`m1-paired-latent-worlds-v5-shared-static-preflight`。40 paired groups 共 1,680 learning rows（1,600 online + 80 recovery），teacher/reference agreement=1，arrays digest=`f68205b58a6d4a97f92e3432b0d1d3515a5b226994e4030515b930d7b0`。该 digest 与 v4 相同是因为 D-037 已把 preflight 审计字段写入数组，D-038 改的是 A–E 对字段的共享使用；v5 manifest/protocol 仍明确隔离新方法边界，旧 manifest 不能复用。
- S1 设置/边界：从同一 40-group arrays 确定性截取前 10 groups；9 fitting groups/378 learning rows、1 inner-dev group/42 learning rows（40 online），scorer steps=60、seed=7。`validation_arrays_read=false`、`validation_trial_consumed=false`、`test_generated=false`；未训练 online student、未校准 gate、未跑 causal。
- static preflight：400 个 selected online rows 共拒绝 632 个候选，mean effective K=14.42，admitted-uniform random accuracy=0.069473；reference pass=1、合法误拒=0、预检通过后 residual executor-illegal=0。shared mask 没有删除 K=16 槽位或替代 executor legality。
- target/assembly：同一 inner-dev rows 上，target-only coverage 保持 0.95，unique-reference 与 uniform-tie expected accuracy 均由未过滤的 0.25/0.60 升至 shared-mask 的 0.95/0.95；assembled oracle accuracy 由 0.575 升至 0.95，raw illegal selection 由 0.375 降至 0，exact-ambiguity capped accuracy=0.925。这是 target/assembly 上限与 shared-mask 接线证据，不是 E 的可部署成绩。
- scorer：fitting BCE/ranking-relevant BCE/teacher accuracy=`0.2526/0.4069/0.1361`；inner-dev=`0.2546/0.4054/0.2000`，target-discriminative BCE=0.4054，reference probability margin mean=-0.238502，positive-margin rate=0.20。相对 v4 S1 的 fitting/inner-dev teacher=`0.05/0.05` 与 BCE=`0.2612/0.2706` 是正面提升，但 E 仍远低于 0.95 oracle 且 margin 为负，60 steps 仍属欠优化诊断点。
- 结论/下一步：S1 shared-mask 不变量、target/assembly 与 scorer 接线通过，按预登记进入同一 40-group arrays 上的 steps {300,1000} × seeds {7,19,31,43,59}。为避免把 5 seeds × 8 inner-dev groups 冒充 40 个独立样本，预算比较先在每个共同 paired group 内对五 seeds 求平均，再对 8 个 paired-group 差值做 10,000 次单层 bootstrap（95% percentile CI，固定 seed=260906）；只有 1000−300 的 CI 下界大于 0 才选 1000，否则选 300。BCE 与 margin 只作 loss-mismatch 解释，不能单独改预算或 loss。

### LOG-032—2026-09-07—v5 S2 scorer budget comparison

- 类型/状态：M1-development、train/inner-dev、scorer-only 的五 seed 预算比较完成；服务器脚本 `ops/run_next_server_step.sh` 返回 `SERVER_STEP_OK`。两个原始 report 后续已通过 exporter 导入 `results/`；无论导出与否，本条都不构成 formal gate 或 CTL 结论。
- 数据/provenance：同一 v5 train arrays，digest=`f68205b58a6d4a97f92e3432b0d1d3515a5b226994e4030515b930d7b0`，40 paired groups、1,600 online + 80 recovery；训练提交 `d35434b410ebe473ae6400dedf9b6869c30b1cda`，protocol=`34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a`，dataset=`m1-paired-latent-worlds-v5-shared-static-preflight`。两点均 `validation_arrays_read=false`、`validation_trial_consumed=false`、`test_generated=false`、未训练 online student、未校准 gate、未跑 causal。
- 设置/主结果：40 groups，固定 scorer 配置，steps `{300,1000}`，seeds `{7,19,31,43,59}`。inner-dev candidate-ranking teacher mean 为 `0.767500`（300）与 `0.794375`（1000）；总体 masked BCE mean 为 `0.086793` 与 `0.062483`，ranking-relevant BCE mean 为 `0.153600` 与 `0.102113`，reference probability margin mean 为 `0.379248` 与 `0.309308`。这些 BCE/margin 是解释量，不是预算选择量。
- 统计选择：每个共同 paired inner-dev group 先对五 seed 求均值，再对 8 个 group 差值做固定 seed=`260906`、10,000 次单层 paired bootstrap。1000−300 effect=`+0.026875`，95% percentile CI=`[+0.008750,+0.045000]`，`p_nonpositive=0.000900`；因为 CI 下界大于 0，唯一预登记预算选择为 **1000 scorer steps**。
- 解释/边界：这支持“在当前 40-group train/inner-dev 诊断上，1000 比 300 的候选排序更好”，不支持 CTL 优越性、causal 泛化或正式 M1 通过。1000 的 margin 均值低于 300，说明 BCE/margin 与排序仍非同一选择量；不据此另立 loss decision。
- 结论/下一步：两个 S2 JSON 已由 exporter 导入 `results/` 并在提交 `ececefb` 中保存；下一步再判断 10→40 是否仍有明确数据量收益，决定是否进入 S3。不得读取 validation、生成 test 或运行 student/causal。

### LOG-033—2026-09-07—v5 S2 10-group 同预算数据量锚点

- 类型/状态：M1-development、train/inner-dev、scorer-only 的预登记锚点完成；服务器入口返回 `SERVER_STEP_OK stage=m1_v2_v5_s2_g10_s1000_five_seed_anchor`。原始 report 后续已导出至 `results/m1-v2-s2-g10-s1000-v5-72afa7d.json` 并在提交 `70355ac` 保存；它仍不构成 formal gate 或 CTL 结论。
- 目的/固定：只回答在已选 1000 scorer steps 下，10→40 groups 是否显示足够明确的继续扩大 train diversity 信号。固定 v5 arrays、共同 inner-dev group 1、seeds `{7,19,31,43,59}`；不改 scorer loss，不重新选择预算，不读 validation/test。
- 数据/provenance：输入 arrays digest=`f68205b58a6d4a97f92e3432b0d1d3515a5b739a5b226994e4030515b930d7b0`，protocol=`34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a`，dataset=`m1-paired-latent-worlds-v5-shared-static-preflight`；训练提交 `d8665d8068a55847bc6a5d38f8e52f2e34c2eca4` 干净。10-group 拟合/inner-dev group 划分为 `9/1`，并保持 `validation_arrays_read=false`、`validation_trial_consumed=false`、`test_generated=false`、`causal_complete=false`。
- 结果/判据：10-group group 1 的逐 seed candidate-ranking accuracy 为 `{7:0.925,19:0.925,31:0.875,43:0.875,59:0.925}`；对应 40-group 为 `{7:0.925,19:0.925,31:0.850,43:0.925,59:0.925}`。40−10 差为 `{7:0,19:0,31:-0.025,43:+0.050,59:0}`，均值=`+0.005000`、严格正差=`1/5`。预登记触发条件为均值 `>=0.025` 且至少 `4/5` 严格为正；两项均未满足，故 **S3 不触发**。
- 局限/决定：这仅有一个独立 group，不能构造可信 CI，也不支持“更多数据无效”的普遍结论；它只否定了继续投入 S3 的预登记必要条件。该 report 已导出；随后进入 S4 预冻结审计，不训练 student、不跑 causal、不生成或读取 test。

### LOG-034—2026-09-07—S4 v5 成本盘点与 D-039 M1-v3 重启

- 类型/状态：M1-development、train-only 的只读资源盘点完成；D-039 方法/架构/预算变化已接受，v6 实现尚未完成。本条不是训练结果、formal gate 或 CTL 性能结论。
- 输入/provenance：服务器仓库 `/root/Emboddied_Spatial_Memory`，干净提交 `356ee23c54fe8e8bd0beb250b0afa3c54587be0c`；只读既有 v5 40-group `train.npz` 与 manifest，arrays digest=`f68205b58a6d4a97f92e3432b0d1d3515a5b739a5b226994e4030515b930d7b0`、protocol=`34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a`。`test_access=false`、`test_generated=false`；没有读取 validation/test、生成新数据或训练模型。
- conformance 发现：合同的 `groups_per_family` 已明确为 train/validation/test=`1000/200/200` **每 family**，而现有 CLI `--paired-groups` 实现为跨 family 的混合总数；连续 rollout 模板映射只覆盖 C00–C08，C09–C11 缺失。由于旧 gate 只遍历实际出现 family，缺失 family 可静默通过。两者均是代码没有实现已冻结合同的 bug，不是新的规模或任务选择。
- 观测成本：40 paired groups 共 1,680 learning rows（1,600 online＋80 recovery）和 26,880 candidate slots；合并 NPZ=`11,977,314` bytes，40 个保留分片=`12,262,560` bytes，加载后 RSS=`45,338,624` bytes、进程 peak RSS=`50,823,168` bytes。该次已成功生成任务的操作者终端记录为 42.5 秒；v5 manifest 本身未持久化该 wall-clock，因此标记为 operator-observed provenance。
- 线性参考：按 v5 每 group 42 rows/672 slots 外推，train=`12,000` groups/`504,000` rows/`8,064,000` slots/约 `6.773 GiB`（合并＋分片）/`3.542 h`；validation 与 test 各=`2,400` groups/`100,800` rows/`1,612,800` slots/约 `1.355 GiB`/`0.708 h`。三 split 合计=`16,800` groups/`705,600` rows/`11,289,600` slots/约 `4.685 GiB` 合并、`9.482 GiB` 含分片、`4.958 h`。
- 局限：这是旧 v5、8-worker 吞吐下的线性参考；C09–C11、live now/collateral、新 current target、Set Transformer 和训练成本都未包含。它证明当前规模在磁盘数量级上可行，不证明 v6 成本严格线性，也不是开始生成 test 的许可。
- 决定：D-039 将 per-family/C00–C11 归为 conformance 修复；now/collateral、C/E 对称 current target 与 cross-candidate Set Transformer 归为方法/架构变化，活动协议/data hash 升级并从 S1/S2 重跑。Set Transformer 是主臂，旧 MLP 是同数组的次级容量稳健性臂，两者均完整跑 A–F，不能事后择优。旧 v5 的 1000 scorer steps 作废。
- 资源边界：用户明确要求删除 `formal_run_wall_time_limit_hours=2`；活动配置改为只测量和报告实际 wall-clock，不设仓库固定上限。云实例仍由操作者手动启停/定时关机，BugCheck 停止规则保留。该调整不改变 test seal 或失败留存。
- 下一步：完成 D-039 的 protocol/contract 锁定后实现 conformance、energy、target 和两架构接线；本地只跑轻量静态/协议测试。随后把版本化服务器入口改为全测，再做小规模 v6 train-only cost/teacher-health benchmark；门通过后才登记新的 S1/S2 scorer/student 预算网格。

### LOG-035—2026-09-07—M1-v3 v6 实现与本地健康探针

- 类型/状态：架构与实验实现完成；train-only 小规模健康/成本探针完成。不是正式训练结果、validation trial、test 或 M1 go/no-go。
- 目的/白话：把 D-039 从合同变成可运行代码，并在付费服务器启动前检查数据、教师和两种模型入口是否连通。输入是每个 C00–C11 family 各 1 个 train paired group，输出是 v6 arrays、逐 family 教师健康、六项能量活性和 Set Transformer/MLP 的最短训练探针。例如 C09 当前证据无效时 `now` 保持中性，但该 family 仍必须出现在分母和健康报告里。它不等于每项能量在每个 family 都有判别力，也不等于模型已优于对照。
- 改变/固定：生成器按 `groups_per_family` 实现 12-family 分母；final step 因没有下一时刻 future 不进入监督 rows；`now` 使用当前有效证据的执行后投影误差并在准入候选内标准化，`future` 从下一决策起算；`collateral` 记录合法事务对当前证据范围外既有开放事实的改变，新事实只计 growth。C/E 获得不执行候选的三维 current relation target。主架构是无位置编码、两层候选间 self-attention 的 Set Transformer，次臂保留共享候选 MLP，两者均接入 A–F。
- Run/产物：本地 ignored `outputs/m1-v3-local-health-v2`；12 paired groups、480 rows、24 recovery rows、生成约 24.7 秒、合并 NPZ 3,955,902 bytes。Set/MLP 的 1-step scorer 探针分别只作 shape/训练路径检查。未生成或读取 validation/test。
- 验证/结果：协议测试 19 项通过；A–F/可训练性/开发学习组合测试 36 项通过；本地数据 teacher/reference agreement 总体及各 family 均为 1.0，health gate 通过，C00–C11 均有支持。服务器完整测试仍待运行，故不能写成全套通过。
- 局限：本地规模极小；C09 的 `now` 因无有效当前 evidence 结构性中性；1-step scorer 数值不是可比较成绩；正式规模时间/磁盘和新预算尚未选择。
- 下一步：推送干净实现提交；服务器先单独执行 `full_test`，成功后再执行 `health_benchmark` 并导出带 provenance 的 JSON。两者通过后才登记新的 S1/S2 网格。

### LOG-036—2026-09-07—D-040 v7 机制修复与本地审计探针

- 类型/状态：D-039 首版实现审计为无效并完成替代实现；M1-development、train-only 的 v7 机制/合同探针通过。不是 formal run、validation trial、test 或 CTL 性能结论。
- 目的/白话：阻止“改 family 标签就算新机制”、规模被混合 schedule 重复乘 12，以及两条 now 通道用不同分母造成假强弱。输入是总混合 paired-group 合同、C10/C11 的真实传感/事务行为和当前证据，输出是 v7 arrays、行为指纹、legal collateral 对照与同分母 now 指标。例如 C10 的当前帧不告诉模型动态 actor 是否会持续，两个 group 分别以 NOOP/BIND 为 reference；它不等于手写 family one-hot，也不允许在线模型读取以后答案。
- 作废/修复：LOG-035 的 v6 12-group 产物只保留为发现问题的本地失败探针，不进入训练或成绩。D-040 将正式规模改为 train/validation/test=`1000/200/200` 个总混合 groups（共 1400，不乘 12）；C10 改为平衡 transient-NOOP/persistent-BIND，C11 加入 shared-preflight admitted 且 executor-legal 的 BIND+collateral 候选。executed-now 的 target 从错误的 reference post-world 改为当前有效匿名传感观测；SPLIT latent 与 MERGE evidence scope 同步修正，避免正确事务被误罚。
- 审计：family gate 按 reference template、观测有效性和真实 legal collateral 形成 fingerprint，`scenario_variant` 只作 provenance、不参与指纹；要求 12 个 family 指纹不重复、C10 同时含 NOOP/BIND、C11 每行都有 collateral=1 的合法对照而 reference collateral=0。`current_now_comparability` 只在两条 now 都可算的同一行和同一 admitted+legal 候选集合上报告 reference-in-minimum、unique、uniform-tie expected 与并列数，缺失行另计；它不裁剪强 baseline，也不向 C/E 的训练或在线推理提供 executor legality。
- 本地 Run/产物：ignored `outputs/m1-v4-local-health-g2-final/`；2 个总混合 train paired groups、80 learning rows（76 online＋4 recovery），2 workers 生成 10.1 秒，arrays digest 前缀=`24de3376c64c6523`，并与独立串行生成逐数组一致。teacher/reference agreement=`1.0`、无 disagreement；12 个行为指纹唯一，C10 reference 为 `{BIND,NOOP}`，C11 legal-collateral contrast rate=`1.0`，三类 health gate 均通过。未生成或读取 validation/test。
- now 数字：76 个 online learning rows 中共同可比 64、executed-now 不可用 12；2 个 exact-ambiguity pairs 的 current target/mask/desired identity rate=`1.0`。C10 的 proxy reference-in-minimum=`0.5`、uniform-tie expected=`0.5`；executed-now reference-in-minimum=`1.0`但约 14.5 个候选并列、uniform-tie expected=`0.06905`。这说明当前传感确实不能靠执行区分 C10 的持久性，future 才承担该信息；不能只看 reference-in-minimum 宣称任一通道更强。
- 验证：协议 21 项、A–F/current-now 22 项、rollout 19 项，以及 data/metrics/trainability/dev-learning 32 项针对性测试均通过；Python 编译、服务器脚本 `bash -n` 与 `git diff --check` 通过。服务器完整测试尚未运行，故不写成全套通过。
- 成本/下一步：LOG-035 的 v6 12-group 24.7 秒/3.96 MB 线性换算到当前 1400 总 groups 约 48 分钟/0.46 GB，仅作旧实现计划参考。推送干净提交后，服务器先单独跑 `full_test`；同一提交成功后才跑 12-group v7 `health_benchmark`，用其真实时间/体积登记新的 S1/S2 有限预算网格。test 继续封存。

### LOG-037—2026-09-07—D-041 v8 固定 current 量程与软后验审计接线

- 类型/状态：能量数值稳健性修复、审计与报告架构变化已完成本地接口验证；M1-development、非正式小规模 run。不是 validation trial、formal test 或 CTL 性能结论。
- 目的/白话：消除同行候选近零方差把微小 current 误差吹成数个标准差的问题，同时用 CTL 实际蒸馏的完整概率分布判断能量项是否参与监督。输入是 executed current raw mismatch、传感器自然范围、完整 teacher posterior 和生成器机制标签；输出是 0–1 fixed-range now、逐项 leave-one-out posterior 距离和五个预登记描述性切片。例如第一名不变但正确候选概率从低置信变高置信时，posterior audit 会记录变化；它不调权重、不按结果挑 family，也不等于方法已经胜出。
- 改变/固定：protocol=`m1-hard-condition-v5`，dataset=`m1-paired-latent-worlds-v8-fixed-range-current-energy`。executed appearance/appearance+place/visible-empty now 分别除以 2/4/1；future 继续逐决策 z-score。C/E 的 current scorer 训练仍用 BCE，推理能量改为 sigmoid probability 对 desired bit 的平均绝对误差且不再 z-score。权重、temperature、A–F、K=16、C10/C11、1000/200/200 总混合规模与两架构不变。
- 审计/报告：generation manifest schema 升为 v5，常驻 now/future/edit/growth/collateral leave-one-out 的 total variation、KL、argmax 与 reference 概率变化，总体和逐 family 同报；fixed-range health 要求 scaled∈[0,1] 且等于 raw/natural-range。A–F report/causal schema 升为 v4，按固定优先级输出 exact ambiguity、C10 temporal underdetermination、C11 side-effect sensitive、C09 current unavailable 和 other 五个互斥切片；切片 `primary_gate=false`。
- 本地 train Run/产物：ignored `outputs/review-v8-g2/train.npz`；2 个总混合 paired groups、80 learning rows（76 online＋4 recovery），2 workers 生成 11.2 秒，arrays digest 前缀=`613684ee14ca6532`，与 16.5 秒独立串行生成逐数组一致。teacher/reference agreement=`1.0`、C04=`1.0`、12-family/fingerprint/C10/C11/current health 全通过；未生成 test。
- fixed-range/posterior 结果：976 个 admitted+legal 且 now 可用候选的 natural range 只取 `{1,2,4}`，scaled min/max=`0.011485/0.996704`，`raw/range` 最大绝对误差=`0`。leave-now-out 的 argmax change=`0`，但 mean posterior total variation=`0.075224`、full-minus-ablated reference probability mean=`+0.075012`；因此 fixed-range now 没有制造赢家翻转，却明确改变 KL 蒸馏的软监督。其余 mean TV 为 future=`0.676529`、edit=`0.022025`、growth=`0.021476`、collateral=`0.014206`；这些是小规模活性审计，不是效果门或权重选择依据。
- 报告链路探针：另生成 ignored 4-group validation 接口数据（160 learning rows，152 online＋8 recovery，teacher agreement=`1.0`），用 1 scorer/student step 跑 Set Transformer A–F `--skip-causal`，只验证 report schema 和五切片覆盖；report-half 每方法各含 exact/C10/C11/C09/other=`6/6/6/12/84` rows。1-step 模型数值没有训练意义，不登记为方法成绩或 validation trial。
- 验证：protocol/rollout/A–F 三组 69 项针对性测试通过；data/metrics/trainability 21 项与 CTL dev 11 项兼容测试通过；2-group train 串并行 digest 一致；4-group A–F report 可完整落盘；Python compile 与 `git diff --check` 通过。服务器 full test 尚未运行，故不写成全套通过。
- 局限/下一步：小规模 posterior 数字只证明审计和能量通路活着，不预测正式 A–C/A–E 效应。推送干净提交后先在服务器运行独立 `full_test`；同一提交成功后才运行 12-group v8 train-only health/cost/posterior benchmark。两者通过后再登记两架构 S1/S2 有限预算网格；validation report 与 test 继续封存。

### LOG-038—2026-09-07—now family 预期模式与 E/teacher 同尺 current 审计

- 类型/状态：D-041 的预登记与诊断报告加固已完成本地接口验证；不改能量、权重、teacher、训练目标、数据内容或主门。不是 validation trial、formal test 或 CTL 性能结果。
- 目的/白话：同时防止两种静默误读。第一，冻结哪些 family 的 executed-now 按构造应为数值零、哪些应非零，使正式 run 的结构退化会被点名；输入是逐 family 的完整/leave-now-out posterior，输出是零/非零及偏离名单，例如 C07 变零会报警而 C11 为零符合预期。第二，在 S1 用同一批行、同一温度和同一 `now=1` 权重并排测 executed teacher 与 E scorer 的 leave-current-out 影响；输出是同一套 TV/KL/argmax/reference 概率指标。它不要求两侧影响相等、不裁剪 E、不调权重、不设通过门；C 只有共享 auxiliary target，没有独立 current-energy posterior，故不伪造 C 消融量。
- 实现/合同：生成 manifest 新增 C01/C02/C04/C06/C07/C08 预期非零、C00/C03/C05/C09/C10/C11 预期数值零的模式；`1e-6` 是吸收 float32 posterior 重构中约 `1e-8` 舍入的数值容差，远低于最小 TV 报告档 0.001。S1 scorer report schema 升为 v5，对 fitting 与 inner-dev online 行分别输出 E 的 current posterior influence，并与同分母 executed-now 结果集中并报；A–F report schema 同步升为 v5。
- 本地接线 Run/产物：ignored `outputs/local-audit-v8-g4b/train.npz`，4 个总混合 train paired groups、160 learning rows（152 online＋8 recovery），4 workers 生成 12.0 秒，arrays digest 前缀=`e25849dab8b015c4`，teacher/reference agreement=`1.0`、health gate PASS、未生成 test。逐 family observed nonzero/zero 与冻结集合完全一致，无偏离。
- scorer 报告探针：ignored `outputs/local-audit-v8-g4b/scorer-s1/af_report.json`；Set Transformer、seed 7、scorer 仅 1 step。fitting/inner-dev 的 E current leave-out mean TV=`0.007184/0.008066`，同一行 executed-now mean TV=`0.070387/0.075941`。该 scorer 几乎未训练，数字只验证“同尺、同行、并排”数据链，不能据此说 A/E 谁更强或选择预算。
- 验证：Python compile 通过；protocol＋A–F 49 项及 CTL dev 11 项兼容测试通过；服务器脚本语法与无参数边界通过；4-group 生成、family 模式匹配和 1-step scorer v5 report 完整落盘。开发中第一次 scorer 探针因配置新增审计字段后旧 manifest 的 protocol hash 不匹配而按设计拒绝，重生成同内容 arrays 后通过；另一次实现探针只请求 now 而无法重构完整 teacher，修为先按全部有限能量重构再提取 now 后通过。这两次均发生在本地 ignored 开发产物，不是服务器失败 run。
- 局限/下一步：小样本模式匹配和 1-step E 影响不预测正式规模。当前 `ops/run_next_server_step.sh` 只承载服务器 full test；其唯一成功标志出现后，下一提交才把同一入口改写为 12-group health benchmark。validation report 与 test 继续封存。

### LOG-039—2026-09-07—M1-v5/v8 服务器完整测试通过

- 类型/状态：干净服务器工程复核通过；不是数据生成、训练、validation trial、formal test 或方法效果结果。
- 输入/provenance：终端解析的 server repo=`/root/Emboddied_Spatial_Memory`，commit=`c27e2581b5ced881d0d9f8283ad8c1865fdc1342`，protocol SHA-256=`1af46e526e94fb0f186166bf2e34a16c61468e2e70fe583b602341eead994189`，dataset=`m1-paired-latent-worlds-v8-fixed-range-current-energy`，test access=false。
- 结果：`python -m unittest discover -s tests -p 'test_*.py'` 共运行 175 项，用时 323.357 秒，全部通过；`FULL_TEST_EXIT=0`。log 与匹配 commit/protocol/dataset 的成功 marker 已写入服务器 ignored `outputs/m1-v5-server-preflight/`。
- 白话：本次 full test 回答“新审计和旧功能能否在同一干净版本上共同通过自动检查”。输入是冻结候选配置、科学代码和全套测试，输出是 175 项通过及可复用 marker；例如后续 health 脚本会先核对 marker 的 commit 和 protocol，避免为了换一份运维脚本再花 323 秒重跑。它不等于 teacher health 通过、不等于 CTL 优于对照，也没有生成或读取 test split。
- 下一步：只运行 12-group v8 train-only health/cost benchmark，验证 teacher health、12-family mechanism、now 预期激活模式、posterior influence、产物体积与生成耗时；不训练、不读 validation/test。成功后先审查并导出报告，再登记新 S1/S2 有限预算。

### LOG-040—2026-09-07—M1-v5/v8 服务器 12-group health generation 通过

- 类型/状态：train-only 小规模 teacher-health、机制与成本 benchmark 通过；不是 scorer/student 训练、validation trial、formal run 或方法效果结果。
- 输入/provenance：server repo=`/root/Emboddied_Spatial_Memory`，generation handoff commit=`d0dafc23d8ee618a7f4083601025bb53888c50d3`，科学代码仍为已全测 commit `c27e2581b5ced881d0d9f8283ad8c1865fdc1342`，protocol SHA-256=`1af46e526e94fb0f186166bf2e34a16c61468e2e70fe583b602341eead994189`，dataset=`m1-paired-latent-worlds-v8-fixed-range-current-energy`。split=train、总混合 paired groups=12、workers=16；validation/test access=false。
- 结果：生成 480 learning rows（456 online＋24 recovery），用时 17.744 秒；teacher/reference agreement=`1.0`、0/456 disagreement，12 个 family 各自 agreement 均为 `1.0`，teacher health PASS。逐 family now 预期模式 `matches_expected_pattern=true`，leave-now-out posterior mean TV=`0.071170335`。完整 arrays digest=`e924f96d4cf28179df010766e4275244cbb78cb9f9425ed514093bdbca3958c3`；合并 NPZ=`3,986,922` bytes，保留 shards=`4,098,264` bytes。
- 成本参考：按 12-group 实测线性外推，1000 个正式 train 总混合 groups 的生成约 24.6 分钟、合并 NPZ 约 332 MB；1400 个全部 split 合计约 34.5 分钟、合并 NPZ 约 465 MB。若同时保留 shards，1000 train 约 674 MB、全部 split 约 943 MB。这只是规划参考，不是固定时限或严格线性保证。
- 白话：health generation 回答“正式生成前，v8 teacher、12 个 family、now 模式和产物规模是否健康”。输入是 12 个 train paired groups，输出是带完整逐候选能量与 provenance 的 arrays/manifest；例如本次 C01/C02/C04/C06/C07/C08 非零、其余六个数值零的模式全部吻合。它不训练 E 或在线 student、不比较 A/C/E，也不生成 validation/test。
- 导出/复核：报告 [`m1_v5_s4_v8_health_benchmark.json`](results/m1_v5_s4_v8_health_benchmark.json) 由服务器 commit `e47a7e4` 单独入库，本地 fast-forward pull 后核对 schema、完整 digest、三段 commit provenance、175 项 full-test 证据与 test seal 全部一致。posterior mean TV 为 future=`0.681108`、now=`0.071170`、growth=`0.025655`、edit=`0.022655`、collateral=`0.015360`；C11 的 collateral mean TV=`0.136628`，说明专门机制对该项确有局部影响。current 同分母审计为 388 行：executed-now reference-in-min=`0.994845`，proxy=`0.935567`；C10 proxy uniform-tie=`0.5`，符合 temporal underdetermination 预期。
- 下一步：在任何选择性训练前登记两架构各自的 v8 S1/S2 scorer/student 有限预算网格，再以 train/inner-dev 运行；不重生成 health、不迁移旧 v5/v7 预算、不读取 validation/test。

### LOG-041—2026-09-07—D-043 Pre-LN 与严格 A–E 对称预算接线

- 类型/状态：训练架构与预算选择实现变更已完成本地轻量验证；尚未运行服务器 full test、数据生成或选择性训练。不是方法效果、validation trial、formal run 或 test 结果。
- 目的/白话：排除“Set Transformer 沿用 MLP 单点学习率而没训好”和“A 只是获得更多搜索机会”两类混淆。输入是同一 v8 train/inner-dev、两条固定架构臂以及完全相同的 3 learning rates × 4 checkpoints × 5 seeds 网格，输出是 E scorer 与 A–E 每个 student 的确定性选择、共享格和 A/E 交叉格读数。例如 A 即使自选 10000 steps，报告仍显示 A/E 在 E 所选步数上的同格差异。它不增加 future 信息、不按结果换主架构，也不读取 validation/test。
- 改变/固定：protocol 升为 `m1-hard-condition-v6`，dataset 保持 v8。主臂两层 attention 从 Post-LN 改为 Pre-LN 并增加末端 LayerNorm；MLP 不改，不同时加入 warmup/scheduler/clipping。scorer/student 网格固定为 lr `{0.0002,0.0006,0.002}` × steps `{300,1000,3000,10000}`。同一架构内 A–E 的模型类、输入、mask、参数模块/形状、optimizer、batch、seed 和 12 格完全相同，监督/loss 是刻意变化的变量；C relation head 仍在所有方法中分配。
- 选择/报告：scorer 与各方法都按同一 train/inner-dev online reference-candidate accuracy、先跨 seed 后跨完整 paired group 等权选择；精确平手依次取更少 steps、更小 lr。每个选择同时保存确定性第二名和固定 seed=`260907`、10,000 次 paired-group bootstrap 95% CI，但 CI 不改选择规则。10000 胜出时接受并标 ceiling，不追加网格。逐方法最优定义正式配置；共享格及 A/E 在彼此所选格上的读数只作算力敏感性诊断。
- 本地验证：预算/协议轻量测试与 Python 编译已通过；完整测试计数、服务器运行时间和新 protocol hash 待最终 diff 收口后复核。本地未运行重训练或全套测试，以遵守本机重负载边界。
- 局限/下一步：本 LOG 只证明控制与报告路径被实现，不证明 Pre-LN 或 CTL 带来正向提升。下一步在干净服务器提交上只跑 full test；通过后另一次提交把活动入口改写为 12-group v8 health/digest invariance，arrays digest 必须等于 `e924f96d4cf28179df010766e4275244cbb78cb9f9425ed514093bdbca3958c3`，否则不启动 1000-group train。

### LOG-042—2026-09-07—M1-v6/v8 D-043 服务器完整测试通过

- 类型/状态：干净服务器工程复核通过；不是数据生成、训练、validation trial、formal test 或方法效果结果。
- 输入/provenance：server repo=`/root/Emboddied_Spatial_Memory`，commit=`53539ce54320c8098f210c7a62eaee05f9ecd41f`，protocol SHA-256=`73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec`，dataset=`m1-paired-latent-worlds-v8-fixed-range-current-energy`；generation/training/validation/test access 均为 false。
- 结果：`python -m unittest discover -s tests -p 'test_*.py'` 共运行 191 项，用时 327.918 秒，全部通过，`FULL_TEST_EXIT=0`。log=`outputs/m1-v6-v8-d043-full-test-53539ce/full_test.log`，匹配 commit/protocol/dataset/test count 的 JSON marker=`full_test.ok.json`；唯一成功标志为 `SERVER_STEP_OK id=m1_v6_v8_d043_architecture_budget_full_test`。
- 白话：本次 full test 回答“Pre-LN、逐方法 12 格选择、共享/交叉预算和旧 executor/rollout 能否在同一干净版本上共同通过自动检查”。输入是 D-043 的科学代码、合同和测试，输出是 191 项通过与可复用 marker；例如下一阶段会先核对 marker，避免仅因改运维入口而重跑五分多钟测试。它不等于数组内容未变、不等于模型已训练，也不证明 CTL 优于 C/E。
- 下一步：只重生成 12-group v8 train-only health arrays，复核 teacher/family/now gate，并要求 arrays digest 逐位等于 D-041 的 `e924f96d4cf28179df010766e4275244cbb78cb9f9425ed514093bdbca3958c3`。通过后才登记 1000-group train generation；validation/test 继续封存。

### LOG-043—2026-09-07—D-043 服务器 12-group arrays digest 不变性通过

- 类型/状态：train-only 小规模生成回归与数据/训练合同解耦检查通过；不是 scorer/student 训练、validation trial、formal run 或方法效果结果。
- 输入/provenance：server repo=`/root/Emboddied_Spatial_Memory`；已全测科学 commit=`53539ce54320c8098f210c7a62eaee05f9ecd41f`，health handoff commit=`402c44cd65f89affde436ab05304493ed7856103`；protocol SHA-256=`73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec`，dataset=`m1-paired-latent-worlds-v8-fixed-range-current-energy`。split=train、总混合 paired groups=12、workers=16；validation/test access=false。
- 结果：17.957 秒生成 480 learning rows（456 online＋24 recovery），merged NPZ=`3,986,922` bytes；teacher/reference agreement=`1.0`、health gate PASS、逐 family now pattern 匹配。arrays digest=`e924f96d4cf28179df010766e4275244cbb78cb9f9425ed514093bdbca3958c3`，与 D-041/LOG-040 逐位相同；`HEALTH_ARRAYS_DIGEST_INVARIANT=true`，唯一成功标志为 `SERVER_STEP_OK id=m1_v6_v8_d043_health_g12_arrays_digest_invariance`。服务器 Git 工作树保持干净。
- 白话：digest 不变性回答“D-043 改网络和调参规则时，有没有意外改变训练样本”。输入是相同 seed/12 groups 但新 protocol hash 下重新生成的 arrays，输出是逐字节内容哈希与旧 v8 完全一致。例如 Pre-LN 和新的 12 格只存在于训练阶段，所以候选、能量和 teacher 数组不应变化，本次确实没变。它不说明新模型更好，也不替代 1000-group 预算选择。
- 下一步：生成唯一 1000-group v8 train arrays；先复用 191-test marker 和本次 health artifact，继续只读 train、不训练、不读 validation/test。按 12-group 实测线性参考，预计约 25 分钟、merged arrays 约 332 MB，保留 shards 后总量约 674 MB；实际时间与 digest 必须由 manifest 报告。

### LOG-044—2026-09-07—D-043 服务器 1000-group train arrays 生成通过

- 类型/状态：唯一正式规模 train-only arrays 生成与 teacher-health 验收通过；不是 scorer/student 训练、预算选择、validation trial、formal run 或方法效果结果。
- 输入/provenance：server repo=`/root/Emboddied_Spatial_Memory`；generation handoff commit=`8a837e65ea8279a460ed712654142da888956af4`，已全测科学 commit=`53539ce54320c8098f210c7a62eaee05f9ecd41f`；protocol SHA-256=`73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec`，dataset=`m1-paired-latent-worlds-v8-fixed-range-current-energy`。split=train、总混合 paired groups=1000、workers=16；training/validation/test access=false。
- 结果：1001.0 秒生成 40,000 learning rows（38,000 online＋2,000 recovery），1000/1000 shards 完整保留；merged NPZ=`331,410,122` bytes、retained shards=`341,522,000` bytes。teacher/reference agreement=`1.0`、teacher health PASS、逐 family now pattern 匹配。arrays digest=`e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168`；arrays=`outputs/m1-v6-v8-d043-train-g1000-53539ce/train.npz`，manifest=`train.manifest.json`，唯一成功标志为 `SERVER_STEP_OK id=m1_v6_v8_d043_train_generation_g1000`。
- 白话：这一步回答“用于预算选择的足量训练数据是否已经完整、健康地落盘”。输入是 1000 条混合 20-step paired groups，输出是同一份供两种架构、A–E 共用的不可变训练数组和 manifest；例如后续 Set Transformer 与 MLP 都必须读取上述同一 digest。它不训练模型、不读取 validation/test，也不说明 CTL 已经提升。
- 下一步：先全测一个固定 300-step、单 seed、单 learning-rate 的 train/inner-dev 运行时剖析入口，再分别测两种架构。剖析只导出墙钟、显存、参数量及线性成本估计，不保存准确率、不做预算选择；正式 12 格 × 5 seeds 网格仍完全按 D-043 执行。

### LOG-045—2026-09-07—D-043 运行时剖析入口服务器完整测试通过

- 类型/状态：纯成本剖析入口的干净服务器工程复核通过；不是模型剖析本身、预算选择、validation trial、formal run 或方法效果结果。
- 输入/provenance：server repo=`/root/Emboddied_Spatial_Memory`，commit=`8b304e39403731bc6be28c26ff38699da71d879a`，protocol SHA-256=`73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec`，dataset=`m1-paired-latent-worlds-v8-fixed-range-current-energy`；generation/training/profiling/validation/test access 均为 false。
- 结果：`python -m unittest discover -s tests -p 'test_*.py'` 共运行 192 项，用时 323.186 秒，全部通过，`FULL_TEST_EXIT=0`。log=`outputs/m1-v6-v8-d043-profile-full-test-8b304e3/full_test.log`，匹配 commit/protocol/dataset/test count 的 marker=`full_test.ok.json`；唯一成功标志为 `SERVER_STEP_OK id=m1_v6_v8_d043_runtime_profile_full_test`。
- 白话：本次 full test 回答“新增的计时路径能否与既有训练、executor 和审计代码共同通过自动检查”。输入是只增加剖析模式后的完整代码与测试，输出是 192 项通过和可复用 marker；例如下个入口必须先核对 marker 才能读取 1000-group train arrays。它没有训练模型、没有产生准确率，也不说明完整网格需要多久。
- 下一步：用同一 train arrays、seed=7、lr=0.0006、steps=300 依次剖析 Set Transformer 和 MLP；每臂只运行一个 scorer 及 A–E 各一条路径。输出只含墙钟、参数量、显存及保守线性投影，不参与 D-043 的任何选择。

### LOG-046—2026-09-07—D-043 两架构运行时剖析通过

- 类型/状态：planning-only 训练成本剖析完成；不是预算选择、方法效果、validation trial 或 formal run。
- 输入/provenance：server repo=`/root/Emboddied_Spatial_Memory`，活动 handoff commit=`51bf03a243c3686b948b8f3abe20be21361b0b87`，已全测 profiler commit=`8b304e39403731bc6be28c26ff38699da71d879a`；输入是唯一 1000-group train arrays digest=`e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168`。每臂固定 seed=7、lr=`0.0006`、steps=300，只运行一个 E scorer 和 A–E 各一条 student 路径；selection/scientific metrics/validation/test 均为 false。
- 结果：Set Transformer 完整登记网格保守线性投影=`3.128` 小时，峰值显存约 `2602.039` MB；shared MLP 投影=`1.239` 小时，峰值约 `1989.218` MB；两臂合计=`4.367` 小时。两份报告均通过 schema、protocol、dataset、arrays digest、固定 profile 点和无选择/无科学指标检查；唯一成功标志为 `SERVER_STEP_OK id=m1_v6_v8_d043_two_architecture_runtime_profile`。
- 白话：运行时剖析回答“已登记的 180 万次更新在当前服务器上大约要跑多久”。输入是每个架构的一条短训练路径，输出按 learning rate、seed、checkpoint 和方法数线性外推的计划时间；例如主臂短路径较慢，投影约 3.128 小时。它不是硬时限、不保证实际严格线性，也没有比较 A/C/E 的准确率。
- 下一步：先把服务器两份完整 JSON 及 provenance 导出到 `results/`。随后在不读取 validation/test 的前提下另立预登记，补 active-node error 常驻安全量和一次固定 anchor 的 endpoint 非退化/检验力探针；探针通过或按事先开关切换后才运行完整预算网格。

### LOG-047—2026-09-08—D-044 endpoint/safety/power 评价协议接线

- 类型/状态：评价协议与科学指标实现变更；已完成本地定向测试，尚未运行服务器 full test 或固定 endpoint probe，不是方法效果、validation trial 或 formal test 结果。
- 输入/provenance：已拉取服务器导出提交 `0fc8371404d8dd4688399a6b17720cddde7d062a`，报告为 `results/m1_v6_d043_runtime_profile.json`；输入 train arrays digest=`e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168`。报告确认 Set Transformer/MLP 完整网格保守线性投影=`3.128/1.239` 小时、合计 `4.367` 小时，峰值约 `2602/1989` MB，且 selection/scientific metrics/validation/test 均未运行。
- 改变/固定：接受 D-044，但不直接把 semantic exact endpoint 换掉。新增与 `_active_graph_state` 完全同字段、保留重复记录的 multiset-Jaccard graded correctness；另对含 `evidence_refs` 的 `_open_memory_state` 增加 graded correctness 和 evidence attachment error，作为固定 co-primary support endpoint。常驻 active/open node/edge symmetric difference 与参考规模；collateral 聚合改为 protected 与 evidence-scope-external unrelated mutation 的逐步并集，同时保留两个分量。机制–指标矩阵逐 family 枚举非 reference admitted+legal 候选，C10 指定 BIND/NOOP 必须由 open-memory/evidence 检出，C11 指定对照必须由 unrelated collateral 检出。新增 group-first endpoint assessment，F integrity 失败即停；semantic exact/graded 的一次切换不读取赢家、方向或效应大小，test N 取 semantic/support 两类 endpoint 的 paired-SD 功效需求最大值。
- 白话：这次接线解决“整图全对指标若全为零会看不见真实差异，边级计数看不见节点身份，以及 active state 看不见 evidence 附着”的问题。输入是同一个终点 active/open memory，输出有 semantic exact/graded、support graded、evidence 和节点/边错误数；例如 lifecycle 改错会在 node error 中出现，C10 错误 BIND 则由 evidence-support 出现。20-step 是逐步接收新观测的闭环长度，不是预测第 20 步；C10 单步当前不可判定仍预期约 0.5，不据此声称 CTL 能预知未来。它不是因 A 输赢换指标，也没有使用 validation/test。
- 验证：首轮 `tests.test_m1_metrics` 与 `tests.test_m1_af_rollout` 共 36 项通过，随后补入 endpoint switch/F gate、open-memory/evidence 与 probe config 单测。配置 `configs/m1_endpoint_viability_probe.json` 冻结 Set Transformer、A/C/E+F、五 seed、`0.0006/3000`、799/201 split、两折 train-inner-dev cross-fit gate、7-group非退化下限、semantic/support graded `0.03`、node safety `1.0/100` 与 test power 公式。
- 覆盖复核：新增 open-memory/evidence 与机制矩阵后，44 项相关单测通过，Python compile、probe JSON、server shell syntax 与 `git diff --check` 通过。ignored 本地产物 `outputs/local-d044-coverage-g2/train.npz` 用 2 个 train paired groups/2 workers 在 12.7 秒生成 80 learning rows，teacher agreement=`1.0`、扩展 health gate PASS；C10 指定相反 BIND/NOOP `4/4` rows 被 open-memory+evidence 检出，C11 指定 collateral BIND `4/4` 被 unrelated collateral 检出，12 family 均至少有一个非 reference admitted+legal 候选被渐进通道看见。先跑 1 group 时 health 按既有规则因 C10 只含一个 variant 而失败，这是预期的最小分母保护，不是正式失败 run。
- 局限/下一步：当前只实现评价底层、机械决策函数和预登记；尚未训练 anchor 或观察 endpoint 数值，也没有选中 exact/graded 分支。下一步先在干净服务器运行全套测试；通过后实现/运行唯一 probe runner，导出报告并按 D-044 自动改写正式 protocol，之后才可启动 D-043 完整预算网格。

### LOG-048—2026-09-08—D-045 指标构念与全过程负担接线

- 类型/状态：指标构念、统计合同、报告 schema 与 gate 公平性修订已接受并完成本地接线；对应 Claude 指标审计的 C1/C7 阻断项以及 C2–C6、B1–B4。尚未运行服务器 full test、endpoint probe、预算网格、validation 或 test，因此没有方法效果结论。
- 改变/固定：规范量改为 extra/missing open-fact error，并把每步 extra 拆成 new incorrect write 与 retained stale fact；terminal 只报终点归一化负担，AUC 报二十步累计状态负担。`open_fact_error_auc_per_100_decisions` 固定为第三个 co-primary，test N 取 selected semantic、graded open-memory support、open-fact AUC 三类 × A−C/A−E 的功效需求最大值。正式 endpoint summary 排除 history/post 重复 alias、`unresolved_active_error`、旧 contamination 名和旧数组 `excess_nodes`；M1 不声称原始 Dynamic Contamination Rate 或完整 static/dynamic 双记忆。
- 统计/公平性修复：conditional recovery 空分母改为 JSON `null` 且保留 eligible denominator；正式 false-birth 改用预测开放 entity ID 减 reference ID 的集合差，另报 missing entities；D-044 cross-fit raw-softmax gate 被固定 `(commit_probability=0, margin_threshold=0)` always-attempt gate supersede，A/C/E/F 不再按一步 proxy 或不同概率尺度选择阈值。validation calibration/report 隔离仍为 C auxiliary-weight 选择保留，但 gate selection 消耗 0 行，report 半区仍不参与选择。
- 兼容与不变量：旧 v8 train arrays 的 `excess_nodes` 是 pre-D-045 净基数诊断，只为复用不可变训练输入保留，禁止进入正式 safety；正式 causal metric 从逐步图状态重算集合差。首个 2-group 本地生成因直接替换该数组字段得到不同 digest prefix=`e2efe5`，据此回退为上述显式兼容边界；最终 ignored `outputs/local-d045-metric-invariance-g2b/train.npz` 的 digest=`613684ee14ca6532653e98b5dc8e0a91aaf6e7464b1eeb9c09d8f36a4bc56580`，与 D-044 同规模输入逐位一致，teacher agreement=`1.0`、health gate PASS。该小产物只验证生成不变量，不是科学 run。
- 本地验证：协议/指标 52 项、连续 rollout 20 项、A–F rollout 26 项，共 98 项定向测试通过；Python compile、probe JSON、server shell syntax 与 `git diff --check` 通过。A–F suite 首次运行曾在 fixture 构建时报一次 `stored graph_hash does not match graph contents`，未改代码立即重跑即 26/26 通过，本轮再次相同运行仍 26/26 通过；鉴于本机既有高负载不稳定风险，该瞬时失败保留记录，不能替代干净服务器 full test。
- 白话：D-045 解决“错误已经能看见，但名字、时间口径和决策门仍可能让结论答错问题”。输入是同一 20-step self-rollout 的逐步预测/reference 世界、固定候选概率与 eligible 分母，输出是规范终点量、全过程负担、分解后的错误来源和无选择执行规则。例如错边前 19 步存在、最后一步修好时 terminal 为零但 AUC 仍计 19 步。它不证明 A 优于 C/E、不验证动态 actor 覆盖静态槽，也不授权 endpoint probe、完整网格或 test。
- 下一步：活动服务器入口只运行 D-044/D-045 full test，唯一成功标志为 `SERVER_STEP_OK id=m1_v6_v8_d045_metric_semantics_full_test`。成功后另一次提交才把入口改写为固定 train-only endpoint probe；full test 前不得启动 probe 或完整预算网格。

### LOG-049—2026-09-08—D-046 AUC 持续等价门与确认集职责接线

- 类型/状态：评价阈值、训练选择和报告接口的实质变更已接受并完成首轮本地接线；尚未运行服务器 full test、endpoint probe、预算网格、validation 或 test，没有方法效果结论。
- 改变/固定：在任何 probe 数字前把 open-fact AUC minimum/planning 从无独立构念依据的 `2/4` 改为 20 步持续等价 `40/80`，对应每组减少 8/16 个错误开放事实×决策步暴露；更高 minimum 使通过门更严，功效 N 下降只是 planning-minus-null 扩大的数学推论。probe 即使显示效应尺度低于 40 也只能报告真实量级失败，不得回调阈值。
- 训练/validation：A–E 先在 C weight=1 锚点上共享同一 12 格 lr/updates 搜索；固定 C 计算格后复用 weight=1、只补跑 0.1/10 两条路径，再以相同 complete-group/五-seed reference accuracy 选 weight，平手优先 1、再取较小权重。validation 改为所有选择冻结后的单次 200-group confirmation，历史 calibration bit 不参与选择。D-043 历史 profile 保守外推新增两条 C 路径后，两臂总计划约 `5.036` 小时；这是规划估计而非新实测。
- gate/report：新增 `commit_attempt_rate` 与 `executor_quarantine_rate`，保留实际 `commit_rate`；固定 `(0,0)` 时 attempt=1 且等于 commit+quarantine。移除 confidence abstention 预计给 E 错误施加上行压力并可能扩大 A−E，但不是保证、gate 理由或成功条件。
- 本地验证：Python compile 通过；endpoint overlay、预算选择、功效与 source protocol 共 64 项测试通过；另有两项真实 rollout 定向测试在 32.651 秒内通过。第一次点名 rollout 测试时写错 unittest 类名，只产生 2 个加载错误且未执行被测代码，修正类名后通过；该操作错误不属于科学失败 run。全仓库测试仍必须在干净服务器运行。
- 白话：D-046 解决“AUC 已经测全过程，但通过门仍拿终点数字硬套，以及 validation 只剩给 C 选一个权重”的问题。输入是 20 步错误暴露定义、既有 train/inner-dev split 和固定 gate，输出是事前冻结的持续效应门、两阶段有限 C 搜索和纯确认 validation。例如末步修好但前段长期出错会过 terminal 却挂 AUC；C 的另两个权重只在已选计算格补跑。它不证明 CTL 有效、不允许结果不好后改 40、也不读取 validation/test。
- 后续改进记录：所有不属于当前冻结路径的候选集中写在 `M1_V2_CLOSEOUT_FLOW.md` 的“M1 后续改进候选”一节；只能用于新协议或 M1 go 后的 M2/M3，不能作为同一 confirmatory run 的补救清单。
- 下一步：活动服务器入口改为只运行 D-044–D-046 full test。通过后另一次提交才把入口改写为固定 train-only endpoint probe；probe 前不得启动完整预算网格，probe 结果不得改变 AUC `40/80`。

### LOG-050—2026-09-08—D-047 claim、执行/轨迹边界与 H=1 主文机制对照

- 类型/状态：研究主张与机制报告合同补正；已完成本地文档、配置、计算函数和单测接线，尚未运行服务器 full test 或 endpoint probe，不是方法效果结果。
- 改变/固定：研究 claim 改为“真实执行候选世界后，以 current evidence 与随后实际观测的 future evidence 为主要评分信号”，minimal-world-change 只称注册正则；明确 online 网络不读 future/候选 `post_graph` 且不展开全部候选，但 CPMT 系统仍由共享 executor 只应用最终选中的事务；M1 event/observation/pose/revisit schedule 登记为 seed 固定、模型运行前预生成的外生输入，不声称 active navigation/action policy。
- H=1：endpoint probe 必须在同一 201 个 train/inner-dev paired groups 上重算 H=1 executed teacher，唯一变化是把 H=3 的后续实际观测 trace 截为下一步。两种 horizon 的 agreement/top-1/entropy 与 H3-vs-H1 的 TV/KL/argmax/reference-probability shift 总体和逐 family 报告，并进入论文主文。该分析不重训 student、不进入 endpoint switch、test N、超参数、validation/test 选择或 M1 pass/fail；弱/零结果只会收窄多步 future 机制叙述，不能触发调参。
- 白话：这项补正回答“老师始终选参考标签时，未来多看两步是否仍改变完整监督分布”。输入是同一批真实执行的候选和固定外生轨迹，输出是 H=3 与 H=1 teacher 概率的距离；例如第一名不变但正确候选概率明显提高，仍属于可蒸馏的变化。它不制造 teacher 改标签、不替代 A-vs-C/E 主比较，也不增加一条为了过关的新门。
- 验证：新增 `teacher_horizon_contrast` 从重建 audit 在不修改输入的情况下重算短 horizon posterior；overlay/endpoint report schema 升为 v4，validator 锁住 201-group、held-fixed、主文/no-gate/no-retune 与外生边界。endpoint/protocol/budget/metrics 36 项及连续 rollout 21 项定向测试通过，Python compile、JSON、shell syntax 与 diff 检查通过；2-group 非科学接口 smoke 的 H3/H1 agreement 均为 1、mean TV=`0.002271`、argmax change=`0`，只证明分布路径可计算，不解释为正式机制强度。首次同命令在进入 H=1 函数前因本机生成器对象瞬时出现非 JSON-native `code` 类型失败，未改代码原样重跑成功；另一次合并测试暴露 validator 仍匹配旧 aggregation 字串，修正为锁定 group-first/per-group 新合同后通过。未读取 validation/test，既有 1000-group arrays digest 不变；全仓库仍待干净服务器验收。
- 下一步：活动服务器入口只运行 D-044–D-047 full test；成功后另一次提交实现 endpoint probe runner，把已冻结的 H3-vs-H1 输出与 endpoint/test-N 报告一起落盘，之后才考虑完整预算网格。

### LOG-051—2026-09-08—D-047 full test 通过并交付固定 endpoint probe 入口

- 类型/状态：服务器 full test 已由用户确认 `SERVER_OK`；固定 endpoint probe runner 已实现并完成本地定向验证，尚未取得 endpoint 科学结果。
- 输入/边界：唯一 train arrays=`outputs/m1-v6-v8-d043-train-g1000-53539ce/train.npz`，digest=`e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168`；固定 Set Transformer、A/C/E+F、seed=`7,19,31,43,59`、lr=`0.0006`、student/scorer=`3000`、C weight=`1.0`；完整 test marker 来自 commit `d36ab9730fed0c32a2d7924ac0969c5acc013019`。validation/test 均封存。
- 实现：`scripts/run_m1_endpoint_probe.py` 重建冻结的 201 个 train/inner-dev paired audits，逐 seed/method 原子保存 scorer cache 与 causal sequence rows，保存 H3-vs-H1 teacher 对照，最后调用预登记 endpoint switch 与三类 co-primary（含 AUC `40/80`）功效计算。`ops/run_next_server_step.sh` 只承载这一阶段，支持已有文件续跑并在报告完成后写 marker；大产物固定写入服务器数据盘 `/root/autodl-tmp/cpmt_outputs/`，不再增长系统盘。阶段成功后自动调用 endpoint 专用 exporter，仅将小型 `results/m1_v6_d047_endpoint_probe.json` 提交并推送，完整逐序列 JSON 仍留在服务器数据盘。
- 本地验证：endpoint/protocol/metrics/rollout 相关定向测试 `72` 项通过（162.786 秒）；Python compile、shell syntax、JSON 与 `git diff --check` 通过。此次验证没有读取 train 之外的数据，也没有生成 test 或运行完整预算网格。
- 白话：这一步回答“固定的 M1 anchor 是否足以让预登记的终点门和 AUC 门做出机械决定”。输入是既有 train arrays 和 201 个冻结 inner-dev groups，输出是可续跑的 A/C/E/F 因果结果、H3-vs-H1 teacher 机制证据和 endpoint/test-N 报告；它不等于正式 test，也不把 probe 结果自动当成 CTL 成功。
- 下一步：服务器同步仓库后运行 `ops/run_next_server_step.sh`；只在报告明确完成并人工审查 disposition、selected metric、三类功效 N 与 H3-vs-H1 后，才决定是否进入 C 顺序权重和两架构完整预算网格。

### LOG-052—2026-09-08—D-047 endpoint probe 导出复核与效应尺度边界

- 类型/状态：固定 train-only endpoint probe 完成并本地复核；`formal_run=false`、`formal_method_effect_claim=false`、validation/test access=false。`retain_exact_endpoint` 只确认指标可用，不等于 M1 通过，也不自动启动完整预算网格。
- 产物/provenance：`git pull --ff-only` 拉取结果提交 `ed440f6`；报告为 [`m1_v6_d047_endpoint_probe.json`](results/m1_v6_d047_endpoint_probe.json)。实际运行与导出来自干净 commit `7f73a548be12a80889478c73f04d2324cd185667`，source hash=`dd6a4939a878c46e3f37c0f545c0a3b12c51a5ad1995069df69b7c4e48f6d313`；既有 train arrays digest=`e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168`。fitting/inner-dev=`799/201`，Set Transformer，seed=`7,19,31,43,59`，lr=`0.0006`，student/scorer=`3000`，C weight=`1`，gate=`(0,0)`；报告环境为 RTX 4080 SUPER。
- 完整性复核：marker 对原 endpoint report 的 SHA-256、本地 Git 中运行 commit 的 entrypoint/overlay/source 哈希全部匹配；source 重构按 `.gitattributes` 对 `.ps1` 使用 CRLF，不能直接拿 Git blob 的 LF 摘要误判来源不一致。A/C/E 各五份 aggregate 与 F 一份共 16 份，每份 402 sequences；三类主量及 graded 诊断的均值差和登记功效公式重算一致。原始 train arrays 与逐 sequence causal 文件仍在服务器，未在本地独立重算 paired SD 或完整轨迹；导出报告不替代原始文件验收。
- endpoint：F exact/graded/open-memory=`1`，open-fact AUC 与节点错误=`0`，oracle failure groups 为空。exact A−C/A−E 的非零 paired groups=`103/154`，均超过登记下限 7；support 和 burden 两对照也非退化，故保留 `final_active_graph_correctness`，不切 graded。正式 test 规划 N=`1350`，由 exact A−E 的 paired SD=`0.392052` 主导；exact A−C 需 400，其余所选主量的功效 N 均受下限 200 约束。N 按预登记最小/规划效应计算，不按观察到的赢家或效应大小选取；尚未生成 test 或改写正式 config。
- 固定 anchor 效果（相同 groups，五 seed 等权；不是正式 CI/pass）：终点 exact A/C/E=`0.918407960/0.793034826/0.471144279`，A−C=`0.125373134`、A−E=`0.447263682`。open-memory graded A/C/E=`0.932013311/0.920288271/0.878167308`，差值=`0.011725040/0.053846003`，其中 A−C 低于登记 0.03。open-fact AUC A/C/E=`8.830845771/12.383084577/14.134328358`，减少=`3.552238806/5.303482587`，均低于登记最小减少 40；不能以 exact 较好抵消这两项主量要求。
- 效应尺度限制：在本批固定 C/E anchor 不变时，因 AUC 非负，即使 A 的负担降到 0，最大平均减少也只有 `12.383085/14.134328`，仍小于 40。这是当前 anchor 的尺度限制，不是对未运行的完整调优或新 split 作失败预言。增加 test N 只改善精度，不会把小效应放大为 40；不据此调低 40、改相对指标、弱化对照或增加 M2 模块。当前尚非 S5/S6 正式 stop-rule 判定。
- 安全描述：五 seed 均值 false birth A/C/E=`0.587065/1.614428/4.803483`，active-node error=`1.577114/4.320896/15.037313`，collateral violation=`0/0.009950/1.313433`（均沿用报告 per-100 口径）。三方法 raw-invalid selection 均为 0；这些均值不是正式安全置信界验收。A 的连续候选选择准确率约 `0.919851`，不能与终点整图正确率混用。
- H3/H1：同一 201 个完整 groups 的 7638 个非末步决策（每条轨迹末步无 future 对照）上，两种 horizon teacher/reference argmax agreement 均为 1；总体 TV mean=`0.003293445`、median=`0`、p95=`0.019239392`、max=`0.190402847`，argmax change=`0`。H3/H1 top-1 mean=`0.747663149/0.750053878`，reference probability shift=`-0.002390729`；各 family mean TV 约 `0.000010–0.006909`。这支持“增加两步只对软分布产生较小平均变化”的边界，不支持“多步普遍纠正标签”或“学生因 H3 更好”；没有训练 H1 student。按 D-047 收窄多步机制叙述，不改 horizon、权重、主比较或 gate。
- 白话：这次输入是冻结的训练集内部 anchor，输出是可用的考试指标、样本量规划和候选世界学习的初步读数。例如 A 的整图正确率较高，但相对于 C 的开放记忆改善只有约 1.17 个百分点，累计错误减少也未达 40；不能只挑整图数字宣布通过。H3/H1 第一名不变且分布差异较小，也不等于 future 整项无用。它不是正式 M1 go/no-go，不能代替真实视觉或部署路径等价性检验。
- 下一步边界：当前脚本与输入大产物保持，避免重跑已完成 probe。正式协议登记与进入预算网格前，按既定流程处置 endpoint/test N，完成之前识别的审计/部署依赖及教师信息来源核查；不因本报告扩格、改门或开启 M2。没有新增方法决定，不追加 D 编号。

## 后续条目模板

将新事件追加在此模板之前；更新顶部看板，不复制整段对话。

~~~text
### LOG-XXX｜YYYY-MM-DD｜事件名称

- 类型/状态：计划 / 运行中 / 完成 / 失败 / 无效；区分工程与科学结论。
- 目的/假设：要回答什么，附白话。
- 改变/固定：相对哪个 LOG/run。
- 配置/数据/版本/种子/资源：实验填完整；讨论写不适用。
- Run/产物：链接 manifest、配置、指标/失败；没运行明确写无。
- 验证/结果：主对照、分母、误差与不确定性。
- 失败/局限：反例、缺失数据、未排除解释。
- 结论/决定：支持/不支持什么，重要决定链接 D-XXX。
- 下一步/人工事项：具体交付和必要权限；同步看板。
~~~

## LOG-053（2026-09-08）：D-048 登记与执行/教师边界核查

- 将 LOG-052 机械结果登记到 `configs/m1_post_probe_registration.json`：exact、support 与 burden 三终点，test N=1350，原最小/规划效应和 test 封存保留。登记规范化 JSON hash=`d366935b14975a18cf3e0af58833fcb8a1151c5929c8848d40677d692fd51e1d`。原生成协议 hash、v8 train arrays 与 probe overlay 不变；新增校验器核对来源/overlay/probe 指纹与 six-cell SD 的 N 计算，预算 runner 读取 train 前校验并记录登记。
- 代码核查发现需纠正此前“额外执行仅属于评测审计”的表述：`_prepare_fixed_candidates` 本身执行全部候选，规范化合法执行后世界并检查重复；`_build_fixed_candidate_catalog` 固定产出 16 个、prepare 在去重后不足 16 个时报错，故成功数据没有候选删减，但存在执行依赖和失败守卫。`materialize_rollout_step` 再展开所有候选；网络只读独立 online vector 与共享静态 preflight mask，只有选中合法 post-world 持久化。代码读取未见 future/post-world/reference index 进入 A–E 网络选择；这不是完整部署等价性证明。保留生成器，仅改正误导性 docstring 和合同，新增原目录/排列一致、重复必须报错与未选中执行结果污染测试。
- A 的 counterfactual trace 沿登记后续参考事务推进，future 对比使用参考图生成的结构观测；C/E future relation targets 来自相同参考后续轨迹，其构造不执行候选；当前目标来自当前观测与声明。共享合成参考来源不等于传感器证据，不能自然推出无标注真实视觉训练。新增 C/E 目标无执行检查；M2 草案补充部署与教师接口验收边界。
- `p95_forward_latency_ms` 排除候选生成/分支审计与完整提交，仅为网络前向及相关张量/概率处理计时。保留历史字段和值，不重解释为端到端耗时。H3/H1 与删项 TV 只作教师分布诊断，不作贡献百分比/学生收益证据；LOG-052 数值和原 passing gates 不变。
- 本地验证：4 项纯登记单元测试通过（约 0.1 秒），组合协议 CLI 通过。新增 rollout 边界测试与全套 unittest 留待服务器；未运行本地重训练/causal 任务，未访问服务器原始数组、validation 或 test。本次没有改候选算法、teacher target、能量或优化，不要求重跑已完成 probe。

## LOG-054（2026-09-08）：D-048 全测失败与过期合同断言修正

- 用户服务器截图显示提交 `9fc1080` 的全套测试运行 221 项，耗时 239.461 秒，`FAILED (failures=1)`，进程退出码 1、日志写入退出码 0。失败日志/marker 保留于 `/root/autodl-tmp/cpmt_outputs/m1-v6-d048-full-test-9fc1080/`；本轮依据截图登记，尚未读取服务器 marker 文件原文。
- 唯一失败是 `test_claim_execution_and_exogenous_trajectory_boundaries_are_locked` 的旧第 243 行，要求研究合同包含“只执行最终选中的单个事务”。D-048 已纠正该过强表述，但上一轮遗漏同步这条文本测试。这不是本次发现的候选执行、训练或未来泄漏故障；截图所示其余测试没有失败，新增边界测试没有报告失败。
- 修正测试以已校验 D-048 登记中的执行边界为准：候选生成/评测均执行全部候选、共享静态 mask、仅选中合法世界持久化、在线不读 future/post-world、单次执行部署尚未实现。D-047 overlay 的原字符串只保留为来源快照检查，不再强制活动合同复述旧说法。研究算法、数据、能量、登记 hash 和 passing gates 均不变。
- 本地 10 项 endpoint 协议测试与 4 项登记测试全部通过；不在本地运行全套或 rollout 重任务。服务器入口继续只承担修复后的全套验证，不重跑已完成 probe/训练数组，也不提前进入预算训练。未覆盖或删除旧失败产物。

## LOG-055（2026-09-08）：D-048 全套复验通过

- 用户截图显示提交 `27d79ea` 的 221 项 unittest 全部通过，耗时 238.729 秒，`FULL_TEST_EXIT=0`、`LOG_WRITE_EXIT=0`，并输出唯一 `SERVER_STEP_OK id=m1_v6_d048_registration_boundary_full_test`。
- 成功 marker 路径为 `/root/autodl-tmp/cpmt_outputs/m1-v6-d048-full-test-27d79ea/full_test.ok.json`。此处按截图验收；下一服务器入口在训练前直接读取该 marker，核对精确提交、221 项/退出码、登记 hash 与当前源码/测试树 hash，不重跑测试。LOG-054 的旧失败目录保留。
- 该结果完成 D-048 工程验证前提，包含新增执行边界测试；不等于 CTL 通过 M1。已有 train arrays、probe、方法和效应门槛不变。本地没有新增科学代码或重训练，后续预算训练尚无运行结果。

## LOG-056（2026-09-08）：主架构预算启动与 MLP 并行调度

- 用户截图显示仓库更新至 `72f1b8a`，入口通过 full-test/registration 前提并输出 `SERVER_STEP_STARTED`，后台 shell PID=2004；随后 `nvidia-smi` 显示 Python PID=2027、约 3788 MiB / 32760 MiB 显存、GPU utilization=5%。这是单次资源快照，不能推出持续低利用率、进度百分比或必然的并行加速；尚无预算完成报告。
- 根据用户希望利用余量同时运行既定 MLP 对照，保留主架构 checkout 的 HEAD 与文件不动，仅用 fetch 获取提交，再在数据盘创建 detached worktree 启动 MLP。输入训练数组通过 Git common-dir 解析到原仓库，仍只读同一已验收 digest；MLP 的输出/锁/进程/日志独立，原主架构不重启、不移动、不更改参数。
- 这仅改变已登记两臂的调度，不增加架构、预算或选择机会，不按中途方法成绩决定是否运行 MLP。两臂仍各自 8 个 PyTorch threads，MLP 仍使用既定完整网格与 C 顺序权重。MLP 的 started/resource_start/resource_end 元数据记录可能的 GPU 共享和进程快照；并行区间的两臂 wall-clock 不作为独占 GPU 速度比较，原 3.640/1.395 小时估算不保证在共享条件下成立。
- 本次没有修改 src/scripts/configs/tests，继续读取并校验 `27d79ea` 的 221 项全测 marker，不再跑测试或生成数据。新入口仍只承担 MLP 预算阶段，后台防重复启动；无完整报告的失败不自动重训。预算结束后再交付结果导出，不提前打开 validation/test。

## LOG-057（2026-09-08）：MLP 训练后验收键名错误与无重训修复

- 用户截图中旧 MLP 入口报 `previous_attempt_requires_review_no_automatic_restart`，回溯为 `cpmt_finish_report` 内嵌 Python 第 18 行。按提交 `04c8319` 精确定位，该行错误要求 `student_hyperparameters_by_method` 的键为 `A/B/C/D/E`；正式 runner 按合同输出的是 `cpmt_ctl_core/direct_classifier/direct_future_loss/execute_current_only/future_no_execution`。原 Set Transformer 入口 `72f1b8a` 也有相同检查错误。
- 执行到这行意味着旧验收器已读到 `runner_exit.txt=0`、可解析的 `budget_report.json`，并通过原训练 commit/clean、协议/登记 hash、train digest 和 split/access 检查；据此认定 MLP 科学 runner 已正常结束，尚未完成产物验收。截图不是训练算法失败的证据；完整 JSON 尚未拉回本地，不宣称后续完整格子检查已经通过。
- 将活动服务器阶段改为两臂既有报告验收：从独立 acceptance worktree 读取旧产物，以机器合同里的完整方法名校验，同时检查各 seed/lr/checkpoint 的格子完整性、C anchor 复用及附加权重、source hash 与原始训练提交。对持锁的运行任务只显示 pending；没有成功 runner 退出记录或报告不完整时保留失败，不启动训练。
- 已验收后补写原 schema 的 `budget.ok.json`，其中 commit 仍是实际训练提交；另写 `budget.acceptance.json` 保存本次验收提交、旧 worker exit 和修复原因。训练报告不改写、失败日志不删除、原训练 checkout 不更新。当前代码仅变更 ops 和进度记录，src/scripts/configs/tests 及 221 项 full-test 前提保持不变。
- 本地 Bash/内嵌 Python 语法检查通过；使用真实预算配置构造两臂报告元数据，13 项轻检查覆盖完整方法名、拒绝旧字母键、缺失格子、错误训练 commit、test 访问、C 固定计算设置漂移和 marker 防覆盖。未进行本地重训练，未访问服务器原始 arrays；先前运维模拟未采用真实方法键名，未发现此错，现已补足。

## LOG-058（2026-09-09）：两臂预算验收通过，准备报告导出

- 用户截图显示独立 acceptance 入口同时输出两条 `BUDGET_ARM_ACCEPTED`，Set Transformer 原训练提交 `72f1b8a879b86c6b37f107ac29a14989a6b67f07`、MLP 原训练提交 `04c8319460df47a0a17960341880d28497897709`，最终 `SERVER_STEP_OK id=m1_v6_d048_budget_reports_acceptance accepted_arms=2`，`ACCEPTANCE_EXIT=0 LOG_WRITE_EXIT=0`。服务器输出时间为 2026-09-08 16:12:33 UTC；本条按用户当前本地日期记载。此处依据截图，完整报告与验收 JSON 尚待导回本地。
- 这表明既有 runner 退出及完整预算格子、登记、原始 provenance 的验收通过；原入口的拒绝重启/键名断言不再作为训练失败判断。没有重跑训练，也不根据截图中的单条 checkpoint 判断正式效果。validation/test 与完整 causal 尚未运行。
- 活动入口改为独立导出阶段：先验证两臂报告 hash 与 acceptance marker，再调用仓库 exporter，在数据盘暂存并核对后生成 `results/m1_v6_d048_budget_set_transformer.json` 与 `results/m1_v6_d048_budget_mlp.json`。已有完整导出核对一致后复用，不覆盖不匹配产物；不包含自动 Git 提交或任何后续训练。
- 原 exporter 虽会收集普通 JSON，却拒绝只有 budget_report 的目录，且未把预算训练来源挂到 pipeline training。补充 budget_report 支持与原始训练 provenance；这是导出代码变更，导出 source hash 因此改变，原训练 source/commit 保持原样记录，不冒充重新训练。入口核对相对原训练提交的 src/scripts/configs/tests 差异仅为 exporter。无需为报告包装重跑科学预算或全套重测试。
- 本地仅进行 Bash/内嵌 Python/导出器静态检查及小型 JSON 导出检查；不进行重训练、rollout 或硬件 benchmark。用户已选择暂不开展新的并行提速验证；既定 S5/S6 的登记接线与必要正确性检查仍需完成。

## LOG-059（2026-09-09）：D-048 两臂预算结果导回与选择复核

- 结果提交 `4d90e4b` 已 fast-forward 拉取；[Set Transformer 报告](results/m1_v6_d048_budget_set_transformer.json) SHA-256=`00e494f540126e42be05f9c18d4c373d12ffbfd3e1fc1a5cd64c1f453d408fee`，[MLP 报告](results/m1_v6_d048_budget_mlp.json) SHA-256=`1379d4d8ba908b9490989bbda254cfaf68c7219ad74bff7adfe4651d4c1a7692`，均与用户服务器导出输出完全一致。按 runner 原 sorted/indented JSON 序列化复原 budget_report，字节 hash 亦与各自 budget.ok.json 一致；acceptance 的 validated_marker 相等。
- 两臂原训练 source hash 相同：`ab859af7e89e71f878d21a4f85c6ab7aa4b65306b0f015a302a3b4c3ae040678`，原训练提交分别为 `72f1b8a`/`04c8319`，clean；导出提交为 `9dfb329`，clean，导出 source hash=`aec02be089ea6028e6224fdcffc8f544ec6627774adb9b47dfc76d2ad904b194`。后者包含新增 budget 导出支持，不替代原训练 provenance。
- 每臂 1000 paired groups 固定划分为 799 fitting 与 201 inner-dev，无交叉；学习行数 31960/8040，预算选择所用 inner-dev online 行数为每 seed 7638。逐条检查 60 scorer、300 student 与 15 C 权重 checkpoint 行的 seed/lr/steps/weight 格子完整且无重复；从 201 组的逐组分数重新按组内五 seed 平均、再组间平均复算全部 12 格与 C 顺序权重，所选配置及报告均值一致（数值核对容差 1e-12）。这不是 375 次独立从头训练。
- 结果是固定参考历史下的单步参考候选选择正确率，用途是决定正式训练设置；例如前一步参考记忆正确时本步是否选中登记候选。它不测模型自有错误记忆的连续积累，不是最终世界正确率，也不是未见 validation/test 的泛化估计。所有 `validation_arrays_read/validation_trial_consumed/test_access/formal_run/test_generated/causal_complete` 边界均为 false，预算合同与本地登记一致。
- 过拟合边界：代码把 train.npz 按完整 paired group 分成互斥 fitting/held_out，checkpoint 指标在 held_out 上计算；因此不是 799 拟合组的训练集准确率。不过 201 inner-dev 被反复用于超参数与 C 权重选择，最高分存在选择乐观偏差；五 seed 不能消除这一偏差。独立 S5 confirmation 与最终 S6 test 仍必需，不能将当前约 94% 称为独立测试准确率。

| 方法 | Set Transformer：lr / updates / reference accuracy | MLP：lr / updates / reference accuracy |
|---|---|---|
| A CPMT-CTL Core | 0.0006 / 3000 / 94.223619% | 0.002 / 3000 / 93.870123% |
| B direct classifier | 0.0002 / 10000 / 93.631841% | 0.0006 / 10000 / 93.288819% |
| C direct+future loss | 0.0006 / 10000 / 94.053417%；aux=1 | 0.002 / 10000 / 94.035088%；aux=10 |
| D execute-current-only | 0.002 / 3000 / 91.796282% | 0.0002 / 10000 / 90.421576% |
| E future-no-execution student | 0.0006 / 1000 / 92.084315% | 0.002 / 3000 / 91.521341% |

- E 的 outcome scorer 单独选择：Set Transformer 为 lr=0.0002、1000 updates，candidate-ranking accuracy=86.260801%；MLP 为 lr=0.002、10000 updates，84.619010%。该 scorer 排序率不等于上表 E student 的参考选择正确率。
- C 在固定计算格上的 aux {0.1,1,10} 正确率：Set Transformer `{94.024614%,94.053417%,93.252160%}`，选 1；MLP `{93.553286%,93.807279%,94.035088%}`，选 10。两臂 B/C、MLP D 与 MLP scorer 触及 10000 上界，按原规则接受并报告，不事后扩张网格。
- 正式选定配置的单步均值差：Set Transformer A−C=`+0.170202` 个百分点，A−E=`+2.139303` 个百分点；MLP A−C=`−0.164965` 个百分点，A−E=`+2.348782` 个百分点。共享计算格诊断的 A−C 分别为 `+0.667714/+0.510605` 个百分点，不能以较好看的共享格替换逐方法最优配置。报告内 selected-vs-runner-up 的 CI 比较的是超参数格，并非 A−C/A−E 方法间 CI；不据此宣布方法显著性。
- 判断：A 的已选更新数为 3000，而 B/C 为 10000，可作为学习曲线描述；未核算教师成本等因素，不能直接称总算力效率提升。两臂 A 高于 E 的单步均值尚有方向性信号，A 对 C 则接近且跨架构方向不一致，不能宣布 CTL 已有效。也不能把这些单步差值套入 20-step semantic/support/AUC 的正式通过门；这批结果本身没有给出 formal no-go。
- 报告中 scorer+student 两段 wall_seconds 合计约 Set Transformer 5.8175 小时、MLP 1.9600 小时；均为 CUDA、8 threads，PyTorch 分配显存峰值约 2604.35/1991.66 MiB。两臂存在并行共享资源，不作为独占速度比较，两段耗时之和也不充当总日历时间或 S5/S6 ETA。
- 本轮只读取结果 JSON、代码与登记，并进行轻量逐组数值复算；没有训练、读取原始 arrays 或打开 validation/test。当前预算 runner 未保存可直接复用的模型权重；后续按已选格训练并保存正式模型不等于重扫这次预算网格。S5 入口仍需落实逐方法预算/组合登记与既定一次性 200-group、五 seed、20-step confirmation；不新增并行提速验证，不重跑已完成预算。

## LOG-060（2026-09-09）：D-049 已选配置训练/模型保存入口实现，待服务器全测

- 用户明确要求开始下一阶段。按 D-049 增加 `configs/m1_s5_training_plan.json`、纯元数据/模型产物模块 `src/cpmt/m1_s5_training.py` 与 `scripts/run_m1_s5_train.py`。plan 绑定 LOG-059 的两份完整导出指纹和原选中配置，规范化 plan SHA-256=`eef52f674a7570ff8de9d14684cea9c1c96ebf734285d5e164735743ed03954d`；已有生成合同、probe、budget exports 与数组不改写。
- 新 runner 在完整 1000-group train 上按既定两臂、五 seed、A–E 逐方法配置训练；保留原 label mask，顺序 CUDA/8 threads，共保存 50 student 与 10 E scorer。直接调用既有 train_student/train_outcome_scorer，不修改目标或学习算法；scorer 的第二数据参数是 train alias，不读取 validation。注册 gate 明确覆盖为 `(0,0)`，不继承 smoke 默认。F 不训练。
- 模型文件含 CPU state_dict、构造参数、训练配置与绑定；manifest 记录 trace、成本、原始 provenance 和模型 hash。已完成目录复用并加载核对；incomplete 目录和异常保留，不自动重训。每个模型完成后更新全局清单；训练阶段只读 train，不计算 validation 或 20-step causal，完整 S5 evaluator 尚待接线。
- 新增 13 项检查：8 项纯元数据/产物检查已在本地通过，涵盖报告指纹、配置漂移、数据访问边界、60 个计划组件、hash 复用与中断保护；另 5 项 runner/小模型检查只在服务器运行，覆盖两架构两类模型加载、C 权重与固定 gate、scorer train alias、完整 60 模型调度及第二次运行零重训。未在本地做训练、causal 或 CPU 压力测试。
- 当前唯一服务器入口只运行新完整套件（预计 234 项=既有 221+新增 13），数据盘保留日志和成功/失败 marker，成功按源码/测试树及 plan hash 复用。全测通过前不预埋真实训练；服务器通过输出到来后才改写同一 ops 文件交付训练阶段。新代码尚无服务器测试/训练结果，旧 221 项通过不冒充本次验证。

## LOG-061（2026-09-09）：D-049 234 项服务器全测通过，交付固定配置训练

- 用户服务器输出确认 `FULL_TEST_RESULT tests=234 exit=0`，成功 marker 为 `/root/autodl-tmp/cpmt_outputs/m1-v6-d049-full-test-c6d7644/full_test.ok.json`，唯一 `SERVER_STEP_OK id=m1_v6_d049_s5_training_full_test`，`FULL_TEST_EXIT=0 LOG_WRITE_EXIT=0`。本条按用户粘贴的服务器输出登记；未提供 wall_seconds，不另估测试耗时。训练入口会直接复核该 marker 的精确提交、234 项结果、plan/registration 及科学代码/测试树 hash，不重跑全测。
- 当前唯一服务器入口改为 `m1_v6_d049_s5_selected_training`：从 Git common-dir 解析实际主仓库路径，读取已验收的 `outputs/m1-v6-v8-d043-train-g1000-53539ce/train.npz`；固定输出 `/root/autodl-tmp/cpmt_outputs/m1-v6-d049-s5-selected-training`。nohup 后台运行既有 D-049 runner，两架构顺序、五 seeds、50 student+10 scorer；训练逐个保存模型，仍不读 validation/test、不生成数据、不扫描预算。
- 重复运行入口先查独占锁，运行中只报告状态和日志尾部；完成后校验 runner exit、完整 60 个方法/seed/架构键、train/plan/source/test-marker 绑定、每个模型文件 hash 与 manifest/provenance，再写 training.ok.json。原始失败/中断记录不覆盖、不自动重启；科学 runner 的已完成模型复用能力保留，具体失败续跑须先复核。训练期间保持 checkout 不变。
- 本轮仅变更 ops/进度记录，src/scripts/configs/tests 相对 `c6d7644` 无变化，234 项新验证证据可复用。Bash 与三个内嵌 Python 语法检查通过；用真实固定计划和临时的 60 个元数据模型检查成功验收、成功复用、拒绝缺失模型、文件损坏、source 漂移、test 访问和非零 runner exit，共 7 项轻检查通过。没有本地模型训练、CUDA 运行或新的验证集访问。
- 当前仅交付启动阶段，尚未收到真实训练启动/模型完成输出，不记训练结果或 M1 成功；训练完成后再独立处理 S5 confirmation 的接线和数据边界。

## LOG-062（2026-09-09）：用户确认固定配置训练验收通过，交付清单导出

- 用户在上一阶段完成状态核对后回复“通过了”。据此记录其确认 D-049 固定配置训练/60 模型验收通过；本轮尚未收到 training.ok.json、完整训练清单或最终日志，不补写实测耗时、训练分数、模型 hash，也不称本地已完成独立验收。S5 validation 与 S6 test 仍未运行。
- 当前唯一入口改为 `m1_v6_d049_s5_training_export`：取得原 worker 锁后只读原训练目录，核对 runner exit、精确训练提交 `af2ed07108f52b186623bba08731a35de84ed88b`、原 234 项成功 marker、固定 plan/registration、1000 groups/40000 rows、全部 60 个模型 manifest 与文件 hash。验收通过后通过仓库 exporter 导出唯一 `results/m1_v6_d049_s5_training.json`，大模型文件与 arrays 留在服务器。已有一致导出复用，不覆盖不匹配产物；不自动 Git 提交。
- exporter 增加 training_manifest 支持，保留原训练 provenance，并单独记录导出 provenance；该文件是本轮 src/scripts/configs/tests 相对原训练提交唯一允许的差异。仅包装既有报告，不改变训练或评测算法，不因导出代码 hash 变化要求重新训练或重跑全套测试。
- 后续仍须先完成一次性独立 200-group validation confirmation 的登记接线与必要正确性检查，再复用固定模型做每条 20 步连续评测。训练完成不等于 S5 confirmation 已完成；本轮不生成或读取 validation/test，不实施新的并行提速验证。
- 本地 Bash、内嵌 Python 和 exporter 语法检查通过；8 项轻量临时文件检查覆盖实际 exporter 打包、精确复用、损坏权重、缺失模型 manifest、错误完成 marker、非零 runner exit、导出内容漂移及旧全测证据漂移的拒绝。未加载或执行模型，未读取数据集。

## LOG-063（2026-09-09）：D-049 固定配置训练报告导回与本地复核

- 结果提交 `3221caf` 已 fast-forward 拉取。[训练报告](results/m1_v6_d049_s5_training.json) SHA-256=`50313a11befab8d6921e4876f2f9e36ff8913762268dc16a0c6d4de2bb47c6f6`，与服务器导出输出完全一致。按原 sorted/indented JSON 加结尾换行复原 training_manifest，SHA-256=`dd6a4079f5bd447ca7119c1d4dd0f7fac0b05657f2fb538b8dfb3a6401ae1b7c`，与 training.ok.json 一致；status=complete、runner_exit_code=0、models=60。
- 固定 plan 与 post-probe registration 均与本地一致，既有 train arrays digest 保持不变。使用完整 1000 groups、40000 学习行，其中 4000 行带标签，原 label mask 复用。两架构各五 seed、25 student+5 scorer，共 50 student+10 scorer；逐个核对 component、模型路径、SHA 字段、训练配置、原始 provenance 与日志终止步数，所有模型达到已选预算，记录的 trace 数值均有限。C 的辅助权重仍分别为 1/10，gate=(0,0)，CUDA/8 threads；没有重新选配置。
- 训练提交 `af2ed07108f52b186623bba08731a35de84ed88b`，source SHA-256=`0963d03bfac3be34be9588e5629661da5724d9276cc827e1b95a090da04f2cb9`；导出提交 `c5288ac9b7508733947868513068ca06d560492d`，source SHA-256=`c1c59a5e1955b31cd7c081ddd0ad6103a3a61a7eca99a0f113dad08351d31e56`。两阶段 clean，分别从对应 Git 提交按服务器 LF checkout 规则重建源文件字节并复算 source/entrypoint hash，一致。导出阶段包含 exporter 支持变更，未覆盖原训练来源。
- 各模型 wall_seconds 求和：Set Transformer 3121.429 秒（52.024 分钟），MLP 1720.548 秒（28.676 分钟），合计 4841.977 秒（80.700 分钟）。这是模型函数计时之和，不含完整调度、保存/加载与验收等全部开销，不冒充总日历耗时。同架构 A–E 的 student 参数量一致，分别为 359673/33017；逐模型 PyTorch allocated 显存峰值的最大值分别为 3336.471/2570.354 MiB，不等于 nvidia-smi 整机显存占用。
- 本次报告只有训练 trace 与模型完成证据；没有新泛化准确率或 20-step causal 结果，不能根据 loss 或成功 marker 宣布 CTL 有效。formal_run、validation_arrays_read、test_access、causal_complete、model_selection_performed 均为 false。训练函数允许 hindsight/辅助目标，online_future_access=false；原 D-047/D-048 执行边界保持。
- 本地读取的是导出的 JSON 与 Git 对象，没有下载或重新加载服务器模型权重；权重文件的实际 hash 验收来自服务器完成/导出阶段，本地核对其清单与绑定。未训练、未重跑全测、未读取 validation/test。后续仍需接线一次独立 200-group、每条 20 步的 S5 confirmation，复用已保存模型，不重扫预算。

## LOG-064（2026-09-09）：D-050 S5 独立确认数据/保存模型评测入口实现，待服务器全测

- 用户在 LOG-063 报告核对后明确授权开始。新增 `configs/m1_s5_confirmation_plan.json`、纯元数据模块 `src/cpmt/m1_s5_confirmation.py` 与 `scripts/run_m1_s5_confirmation.py`，落实 D-050：绑定原训练导出和既定合同，排除历史 validation 0–3，新范围固定 4–203，共 200 组。未读取或生成这些确认数据，尚无 S5 指标。
- 数据模式复用既有 generator/array encoder，16-worker 仅传路径、组号与小型绑定，每组完整保存 paired audit、learning arrays 与 SHA。parent 汇总原覆盖/教师健康规则；失败保留且不得替换样本。成功数据再次访问只验 hash，不重生成或改写完成 manifest。
- 评测模式校验原 60 个模型产物，直接加载 50 student，CPU/1 thread 串行；每模型 400 条完整 20-step 轨迹。F oracle 和 observable oracle 各一次，F 按原完整性门先检查。逐方法/seed 保存完整 sequence choices、指标、固定参考历史诊断与逐候选执行失败；继承原固定 gate 和统计函数，paired group 含两 sibling/五 seed，保留三项效应与安全门、Holm 校正。此处只说明实现，不表示真实 200-group 评测已经运行或通过。
- 原 `causal_rollout_metrics` 仅新增默认关闭的选择后审计回调，新增记录不进入网络/选择输入；生成审计保留六项参考 hindsight 能量与 future branches，分叉世界单独记录实际候选执行。新源码与旧训练 hash 分开绑定；原 60 个模型不重训，不改变候选、教师目标或核心指标公式。exporter 已支持最终 S5 报告的 training/evaluation/export provenance。
- 每个完整生成/评测单元原子发布并校验文件 hash，partial 和失败保留、拒绝自动重试。数据目录唯一 consumption 记录与评测目录 trial 共同绑定 data/model/plan/source/runtime/output，防止换配置、环境或目录重开确认；生成数组和原训练文件不改写。完整报告只供既定 S5 stop rule 复核，不自动解封 test。
- 新增 16 项检查：8 项纯元数据检查已在本地通过，覆盖实际固定报告绑定、历史隔离、test/gate 漂移、单元内容校验、失败保留、同一数据的输出位置占用、配对重复/缺失与 20-step hash 连续性；另外 8 项包含 train fixtures/小模型/runner 接线的检查只交由服务器运行，覆盖原生成编码复用、缓存、审计回调不改变 oracle 轨迹、固定参考历史诊断、完整单元复用、失败链和按组统计。没有本地训练、真实 rollout、benchmark 或完整套件运行。
- 当前唯一 ops 阶段为 `m1_v6_d050_s5_confirmation_full_test`，预计 250 项（原 234+16），使用数据盘临时目录，成功 marker 绑定新 plan 与完整 source/tests hash；Bash、新增 Python 及内嵌 Python 静态检查已通过。旧 234 项训练测试保持其历史效力，本轮新科学代码仍需服务器完整验证；此入口不预埋数据生成、50 模型评测或 Git 导出。
- 另用纯元数据替身执行完整调度检查：两臂 50 个 student 加两种 oracle 全部被调度；第二次访问没有新增模型加载、单步前向或 rollout 调用。该检查没有导入/执行真实模型，不能代替待服务器运行的 8 项 runner 集成检查。

## LOG-065（2026-09-09）：用户确认 D-050 新全测通过，交付固定确认数据生成

- 用户对上一阶段回复“通过了”，按该确认记录新全测通过；本轮未附最终日志或 marker JSON，不补记测试耗时。生成入口会实际读取约定的 `/root/autodl-tmp/cpmt_outputs/m1-v6-d050-full-test-4b8522e/full_test.ok.json`，要求提交为 `4b8522e7ae4527dc505be35d3ada79698b239467`、250 项全部成功，以及新 plan/registration/source/tests 绑定一致；不重跑测试。
- 当前唯一阶段改为 `m1_v6_d050_s5_confirmation_data`，输出固定 `/root/autodl-tmp/cpmt_outputs/m1-v6-d050-s5-validation-g200`。后台调用已通过服务器测试的 runner `generate` 模式，16 workers 生成 validation 4–203 的 200 个完整配对组（400 条轨迹、8000 个在线决策）；保留此前固定的历史排除范围、原生成器和编码器，不训练、不运行模型确认、不访问 test。
- 原工作目录保持不变时，重复运行入口只报告持锁任务状态和日志尾部；完成后核对 runner exit、完整 200 组 shard hash、每组 summary 的 split/index/2 siblings/40 decisions、总 manifest 的 400 sequences/8000 decisions、原覆盖和教师健康门及 provenance，再写 generation.ok.json。成功产物只验收复用，失败/中断保留并拒绝自动重启；不得用新组替换失败组。尚未收到真实生成完成输出。
- 本轮只改 ops 与既有进度记录，src/scripts/configs/tests 保持 `4b8522e` 的科学代码不变，可复用刚通过的 250 项验证。Bash 和三个内嵌 Python 静态检查通过；8 项纯元数据/临时文件检查覆盖完整验收、成功复用、损坏分片、错误 test 访问、教师健康失败、缺失组、错误来源提交和非零 runner exit 的拒绝。未在本地生成数据、加载数组或执行模型。

## LOG-066（2026-09-09）：S5 确认数据 C11 生成失败，保留产物并定位证据范围问题

- 用户截图显示并行生成最后可见 `S5_DATA_GROUP_OK index=60 completed=59/200`，随后 `ValueError: C11 collateral stress requires an unprotected node outside the current evidence scope`；`GENERATION_RUN_EXIT=1`、`SERVER_STEP_FAILED id=m1_v6_d050_s5_confirmation_data reason=generation_failed_requires_review`。栈位于 `_generate_sequence → _candidate_programs → _build_fixed_candidate_catalog → _proposal_context`；尚未运行模型确认。并行返回顺序不能确定失败组，也不能把截图中的 59 当作最终实际完整目录总数。
- 静态核查发现独立的实现问题：`_current_online_evidence_scope` 注释定义检索后的“一跳”子图，但循环直接用持续增长的 selected 集合判定后续边，可能跨多跳传播且依赖边记录顺序。用实际函数体的三节点/两条边纯字典反例，固定检索种子 a 时，边顺序 a-b、b-c 会纳入 c；反向边顺序则不会。未生成任何数据集或运行模型。该反例证明代码和一跳注释不一致，但尚未证明它足以解释本次真实失败。
- 此函数不仅决定 C11 无关候选，还参与 reference/recovery 的 collateral 能量以及自有记忆 rollout 的 collateral 指标；不能仅为让生成通过而删除断言、收缩范围、改组号或添加节点。当前未改它，也未据此要求重跑整个 M1；是否需要修订定义、哪些既有数据/模型/评测受影响，必须以确切现场与后续影响核查决定。
- 当前唯一入口改为 `m1_v6_d050_s5_generation_diagnostic`：持原 worker 锁确认任务已退出，仅读原目录的开始/退出/manifest/complete/failure 元数据，列出完整、失败和中断组。从已有精确 C11 failure.json 中取最小组号，仅按原生成规则在内存复现这一组；使用 sys.settrace 读取 evidence scope 扩展前后集合与异常帧，保存实际 graph/event、sequence/sibling/step、bind targets 和候选池。它不替换函数、不改返回值，不重扫 200 组，不覆盖原分片或继续模型评测。
- 诊断独立保存到 `/root/autodl-tmp/cpmt_outputs/m1-v6-d050-s5-generation-diagnostic`，最终通过仓库 exporter 输出唯一 `results/m1_v6_d050_s5_generation_failure.json`；原元数据前后指纹必须一致。匹配的诊断/导出可复用；即使未复现或出现不同异常也明确保存该状态，不冒称根因已确认。新增 exporter 仅支持 diagnostic_report 及独立 provenance，是本轮 src/scripts/configs/tests 唯一变化；原生成/执行/模型/指标代码保持失败时版本。
- 本地 Bash/内嵌 Python/exporter 静态检查通过；三节点真实 scope 函数反例与观察器检查验证初始/最终范围、异常上下文捕获和输入未修改，diagnostic-only 导出包装检查通过。没有本地真实 group 生成、模型运行、全套测试或 validation 模型指标。尚待服务器诊断返回，不追加新方法 decision、不更换固定确认范围、不删除失败记录。

## LOG-067（2026-09-09）：S5 group 78 诊断导回，确认多跳扩展导致现场候选耗尽

- 结果提交 `2948462` 已 fast-forward 拉取。[诊断报告](results/m1_v6_d050_s5_generation_failure.json) SHA-256=`b1714dd3b1bc74e16830526bd8352e3e9acf538e78b36b85cae453aa908ac73e`，与服务器截图一致。诊断 provenance 为干净提交 `d02e5c904cf91cda2c05d126c822d9892ca5b672`；报告记录 original_metadata_unchanged=true、model_evaluation_performed=false、replacement_groups_generated=false、test_access=false。
- 200 个预定组的清单中，完整目录与 parent manifest 各 59 个，另有 17 个 incomplete 目录；不把所有 incomplete 目录都判成同一异常。服务器按原规则仅复现已记录的 C11 失败组 78，status=reproduced_expected_failure。现场为 sibling 0、world_seed=200360984；异常帧外层 sequence_context.step_index 为 null，但保存的 event.step_index=2 明确定位第 3 步，event_id 后缀 10 不是序列第 11 步。
- 本地仅对保存的 graph/event 和检索集合做纯字典复算：初始检索含 12 个节点/边标识；原逐边循环得到 42 个标识，与服务器捕获集合完全相同。以固定初始检索集合判断每条边的一跳范围得到 40 个标识；差集恰为 entity:mover:0 及 edge:mover-location:0。原循环经先前加入的 place:4 继续传播，把这两个标识额外纳入。沿用原生命周期、protected_id 与 bind_targets 过滤后，原范围的可用候选为 0，一跳范围的可用候选为 1（entity:mover:0）。
- 解释：证据范围用于判断哪些既有记忆与当前观测相关，输入是当前图与检索结果，输出是节点/边标识集合。例如此现场的 mover:0 原本在一跳范围外，可作为 C11 检查误改无关记忆的对象；多跳传播却把它标成相关。这不是新模型能力，也不是准确率或过拟合结果。该现场已支持“非预期扩展导致候选耗尽”的解释，但单次范围复算不等于修正后整个组、200 组或自有记忆轨迹都能成功。
- 调用点复核：范围函数同时参与 C11 候选选择、reference/recovery 的 collateral 能量以及 causal rollout 的 collateral 指标。修正可能影响旧候选及教师分布，不能只改 validation 后直接接旧模型，也不能仅凭此次故障宣布全 M1 必须重跑。下一步先确定既有训练数据/教师与指标的实际影响，再决定修复及重新冻结范围；本轮仅记录证据，不改算法、配置、ops 或训练产物，不启动模型评测或 test。

## LOG-068（2026-09-09）：交付已有 train 审计上的范围影响诊断，生产算法未修改

- 用户要求下一步。新增 `scripts/run_m1_scope_impact.py` 作为只读诊断入口，唯一 ops 阶段为 `m1_v6_d050_train_scope_impact`。从已接受 D-047 export 的 causal 目录字段解析同一 probe 的 audits 目录，核对原服务器报告与导出内容一致，要求原有 201 个 train/inner-dev gzip 文件齐全；缺失即停止，不自动重建、不重新生成 validation、不加载模型或执行候选。组号沿用原 train paired-group hash 划分，成对读取，每组落盘结果后释放大审计内容。
- 诊断解决“范围修正会不会改变旧训练所用的候选与监督”的问题。输入是已有 reference/recovery 的图、观测查询、候选执行后世界与教师能量；输出是逐组/逐步的范围差集、C11 新旧候选对象、collateral 差值，以及固定候选下的原始/共享 mask 后教师概率总变差距离（Total Variation，TV）与首选变化。例如范围缩小后某次误改记忆新增 collateral 惩罚，教师概率可能改变；若 C11 的候选对象也改变，则只记录需要重新生成评估，不能把旧候选评分当成修正后的完整数据。TV 不是性能提升百分比。
- 诊断中的 proposed 一跳函数使用与生产相同的检索查询，仅用不可变检索集合做一轮边扩展；不替换或 monkeypatch 任何生产函数。每步先复算并核对原 scope、collateral、teacher posterior，再计算条件变化；非 collateral 能量保留。生产 src/configs 与原生成提交保持一致，仅增加诊断 runner，先前 exporter 包装差异仍保留。此次没有接受新的科学定义或回调原门槛，不追加方法 decision。
- 输出独立位于 `/root/autodl-tmp/cpmt_outputs/m1-v6-d050-train-scope-impact`，每组保存输入 SHA-256、绑定和逐步结果；最后以既有 exporter 导出唯一 `results/m1_v6_d050_train_scope_impact.json`。后台单进程、CPU 线程设为 1、屏蔽 CUDA；重复入口只查运行状态或核对成功报告，失败/中断保留并拒绝自动重启。原完整/失败 S5 分片不改写；成功标志只表示这项诊断完成，不授权恢复生成或 test。
- 8 项纯字典检查通过，涵盖一跳边顺序不变性、边标识检索、关闭边、保护/生命周期过滤、共享 mask、查询保留、固定候选重评分及缓存不一致拒绝；Bash、内嵌 Python 和 runner 静态检查通过。另对已导回的失败图做只读检索复算，新诊断函数重现原 42 / proposed 40 个标识和 1 个范围外候选，没有生成序列或执行模型。本机未做真实 train 审计扫描、训练、rollout、benchmark 或完整测试。
- 解释限制预先保留：201 个缓存组属于已有 1000-group train 的子集；它们不是全 train 覆盖，也不是模型自行选择后的所有世界。固定候选后验只隔离 scope 对能量的影响；C11 候选改变后的完整教师、连续轨迹与最终 collateral 指标仍未重算。阳性结果支持界定重算范围，零结果不自动证明所有旧模型与评测可原样复用。尚待服务器运行结果。

## LOG-069（2026-09-09）：train 范围影响报告导回，确认候选与软监督实际受影响

- 结果提交 `0a3ce08` 已 fast-forward 拉取。[影响报告](results/m1_v6_d050_train_scope_impact.json) SHA-256=`1df79a525ca3e4f2d3de4a17ce4aa3f05c68ac4b07f14f4f5d2f79a4373691b0`，与用户服务器输出一致。诊断来自干净提交 `05bc12902d6d54ecbeaa670b4dee52b3b67901f1`；本地以 Git blob 核对入口、hard config 和已接受 probe export 指纹，并从逐行记录复算总体汇总与配对结构。201 组各两条完整 20-step reference 轨迹，另各 sibling 一条 recovery，共 8040+402=8442 条，无重复键或缺失 reference 步。
- 一跳范围与原范围不同的记录为 7141/8442（84.588960%），涉及全部 201 组；这是相关范围标识集合发生变化的比例，不等于错误率。C11 候选对象改变为 169/402（42.039801%），涉及 86/201 组；因此修复不只是修正某一失败 validation 组的外围判断，也会改变已有 train 候选输入。
- 固定原候选与执行后世界复算 collateral 后，667 个候选能量发生变化，分布在 490/8442 条记录（5.804312%，涉及 135 组）；共享 mask 后教师分布变化条数同为 490，其中 reference 477/8040、recovery 13/402。教师首选改变为 0；总体平均 TV=0.001638966，变化记录平均 TV=0.028237035，最大 TV=0.245158421。变化分布覆盖 C00–C11 与 recovery，不能把影响归为仅 C11。TV 是概率分布距离，不是准确率、贡献率或性能提升。
- 工程判断：当前 CTL 学习完整软教师分布，首选未变不能推出训练目标未变；169 个 C11 对象替换还没有重新执行，因此上述固定候选差异不代表修正后的完整教师效果。已有报告足以否定“仅修 validation 然后把旧模型直接当作修正版训练结果”的做法。旧数组、模型、预算/probe 报告仍保留为旧实现的历史证据；新正式确认需要采用一致的数据/候选/教师定义。具体重算与重新冻结方案尚未接受，本条不直接重开预算网格或推倒 executor/网络架构。
- 本次服务器诊断循环 wall_seconds=57.920909（不含全部前置检查/测试/导出），model_evaluation_performed=false、candidates_executed=false、validation_read=false、test_access=false。本地只读导出 JSON、Git blob 并做轻量统计核对，没有读取原始审计缓存、训练或执行 rollout。该结果是实现影响证据，不是 CTL 科学假设失败，也不证明修正后的性能会升降。
- 下一项是生产一跳修复及相应正确性检查，并明确新旧产物边界、重新冻结和受影响数据/训练/评测的处理方案；旧 59 个完整 validation 分片与 17 个 incomplete 目录继续保留，不混入修正后的数据。当前 ops 仍为已完成的影响诊断，未交付恢复生成或正式评测入口。

## LOG-070（2026-09-09）：D-051 重跑规则固定，交付有界并行选参路径测速

- 用户接受重训并要求检查多线程提速、控制过拟合。代码核查确认预算入口每次只处理一架构，内部 scorer 的 lr×seed、student 的 seed×method×lr 仍串行；`--threads` 控制一个进程内部 CPU 并行，不会并行网格。每条 lr 路径已经复用 300/1000/3000/10000 的 prefix checkpoints，不能把重复训练这些 checkpoint 当成新的节省空间。训练函数调用全局 torch.manual_seed，正式并发应使用独立进程隔离状态，保留 scorer/student/C-weight 阶段依赖。
- D-051 与 `configs/m1_scope_rebuild_plan.json` 在任何修正数据/probe 前记录：完整原预算重跑、旧模型不作为修正版模型复用，exact 固定，F/非退化失败停止，test N 按原公式六格 SD 需求与 1350 取最大且仅估一次。新纯元数据 helper `src/cpmt/m1_scope_rebuild.py` 实现 N 算术、资源准入与耗时选择；尚未接入旧 `m1_registration.py`，不会伪造新 probe 或绕过旧来源绑定。生产 scope 修复、hard/dataset/registration 升版、完整预算并行调度与新增 fit/inner-dev 差距报告均待各自后续实现。
- 新 `scripts/run_m1_budget_concurrency_probe.py` 只在 Linux/AutoDL 运行，直接调用既有 `--runtime-profile-only`，原 train 数组路径来自已接受 probe export。最多比较 (进程,线程)=(1,8)/(1,1)/(2,1)/(4,1)；每配置同样四个任务，两次各架构，每任务固定 scorer+A–E 各 300 updates。最多 16 个短任务、28800 model updates，不进行完整网格、超参数选择、新数组生成、模型保存或独立 validation/test 访问。它会计算旧 train/inner-dev 的既有诊断用于计时，但不导出科学准确率或用分数选调度。
- 读取实际 CPU affinity/cgroup quota、主存余量及唯一 GPU 的 UUID/显存；总线程不超过 CPU 容量，按每进程预留 GPU 4 GiB、主存 8 GiB 并各留 2 GiB 余量筛掉不满足的布局。该准入只是保守估计，不保证不发生 OOM；实际异常保留日志并停止交付后续阶段，不自动重试。ThreadPoolExecutor 仅监管独立 Python 子进程，不在共享 Torch 状态中训练。按完整固定任务集耗时比较，5% 内优先少进程再少线程，报告建议仅作 runtime 初选，不宣称全预算速度或数值等价已验证。
- 唯一 ops 阶段为 `m1_v6_d051_budget_concurrency`，输出独立 `/root/autodl-tmp/cpmt_outputs/m1-v6-d051-budget-concurrency`，完成后导出唯一 `results/m1_v6_d051_budget_concurrency.json`。后台运行、锁保护、重复调用查状态或校验成功、失败/中断不自动重启；旧服务器产物不改写。原训练算法/硬合同保持历史版本，测速新文件只记录自身来源；旧数据这里只用于计算成本，不作为修正版科学证据。
- 8 项本地纯元数据测试通过：样本量下限、六格最大值、忽略观测效应、F/退化/不完整拒绝、CPU quota、显存余量、耗时平手及原搜索/confirmation 边界。新 Python 与 ops/内嵌 Python 静态检查通过，没有本地训练、数据生成、CUDA、真实 rollout、全套测试或 benchmark。服务器实际速度、最优并发数尚无结果；不承诺 2/4 进程线性加速。
- 成本解释纠正：旧 D-046 的约 5.036 小时是外推，不是新实测；LOG-059 的两臂 scorer/student 时间合计另约 7.78 小时且两臂并行共享硬件，不能当作总日历时间。旧 1000-group 生成约 1001 秒、60 模型 refit 的逐模型耗时合计约 80.7 分钟，因此预算搜索值得优化，不能称其为相对重建的“零头”。这些历史数值不直接给出新实例/新版本 ETA。

## LOG-071（2026-09-09）：D-051 并行测速导回，初选 4 个独立进程、各 1 线程

- 结果提交 `7cac5ae` 已 fast-forward 拉取。[测速报告](results/m1_v6_d051_budget_concurrency.json) SHA-256=`3cbac84b29b4fdc56b7440013739ba2199167069b0d5a4e5fd59bd2b9629add0`，与用户服务器输出一致。运行来自干净提交 `026526aee09cebe380bc93ad564b569ec9e67587`；本地以 Git blob 核对入口与计划指纹，核对四种配置各自四个相同任务、两架构各两次、seed=7、lr=0.0006、scorer+A–E 各 300 updates、CUDA/线程条件和非科学结果标记，复算速度比及原建议规则一致。
- 服务器报告 CPU affinity=128，但 cgroup CPU 配额实际相当于 16 核；可用主存约 61.63 GiB，GPU 报告为 RTX 4080 SUPER、总显存约 31.99 GiB、开始时空闲约 31.47 GiB。四种布局均通过预先资源准入并完成；这些是本次运行环境，不把 host 可见 128 CPU 当作实例可用算力。
- 相同完整四任务耗时：1 进程×8 线程 121.813104 秒；1×1 为 121.149692 秒；2×1 为 60.778837 秒；4×1 为 43.098219 秒。相对 1×1 的速度比分别为 0.994554、1、1.993287、2.811014；4×1 的该工作集耗时减少约 64.43%。按 D-051 已固定“最快耗时 5% 内优先少进程再少线程”规则，初选 4 进程×1 线程。1 与 8 线程的约 0.55% 差异不当作稳定统计优势。
- 四个布局耗时合计约 346.839852 秒（5.78 分钟），不含所有入口检查与最终导出；各子进程 PyTorch 分配显存峰值 Transformer 2602.039 MiB、MLP 1989.218 MiB，不能把单进程峰值相加冒称测得整机峰值。当前结果说明短任务并行有价值，未测试 8 个进程，也不据此追加并发扫描。
- 限制：每配置只有一个固定混合任务批次，两次同架构任务仍是相同 seed 的计时重复，不是五 seed 科学重复；长短任务、冷启动、数据读取、scorer 选择与 C 权重阶段依赖都可能影响正式网格效率。不能把旧“约 5 小时”直接除以 2.81 当作承诺 ETA。profile 没有保存模型概率用于等价比较，完整预算分片 runner 尚未实现；后续新数据资源检查和串行/并行数值与汇总一致性验证仍需要。
- 这批报告没有新方法准确率、修正后数据或模型、独立 confirmation/test；不改变 D-051 的固定网格、paired-group 隔离或防过拟合边界。本地只读 JSON/Git 并做轻量复算，无训练、CUDA、rollout 或新的 benchmark。当前 ops 保留已完成测速阶段；下一项按 D-051 进入独立 scope 修复与版本接线。后续预计不超过 30 分钟的任务按新 AGENTS 规则前台运行，不重复本次测速。

## LOG-072（2026-09-09）：独立一跳修复、v7/v9 版本隔离与前台完整测试入口

- 用户同意进入修复。提交 `31f0e0f` 只修改 `src/cpmt/m1_rollout.py` 中生产 scope 的一处循环：先保存 frozenset(selected)，再以该固定集合判断每条边。该提交仅 2 行增加/1 行替换，不混入候选策略、训练目标、模型或统计规则。C11 无范围外候选时仍报错；没有主动扩充图或回退到其它对象。
- 新 `configs/m1_hard_condition_v7.json` 为修正生成合同，dataset=`m1-paired-latent-worlds-v9-one-hop-scope`，规范化 SHA-256=`adc6badc93dcca11904e12cb93396d26c3a4e728ccf438ce9a3a4f442f93901f`；rebuild plan 精确绑定路径/hash。相对原合同仅改变 protocol/dataset 标识并增加 scope 查询、ranks=3、open-only、检索边端点、非递归、边序不变、候选无关、无 future/post-world 和四处消费者的定义，预算、seed、组数与所有科学门保持。旧 hard/overlay/registration/模型计划不改写，旧指纹仍能核查历史报告；不能用旧 test=200 生成正式 test。
- 生产 coverage/rollout 生成要求新协议；每条新序列审计保存 source_binding。已有审计编码、H3/H1 对照、materialize 和 execute_rollout_choices 在处理前验证版本，编码还比较精确 config hash，拒绝无绑定/v8 或来源不匹配记录。并行生成默认使用新合同，并拒绝覆盖既有 shard 目录或目标 arrays/manifest；正式新生成阶段以后在新目录运行，旧成功与失败产物不移动删除。低层图查询函数仍可用于只读历史现场分析，不把这种分析当新生成结果。
- 既有会生成连续轨迹的四个测试文件改用 v7 合同；历史登记/报告元数据测试仍读取原 v6 合同，防止为了全测通过而改写旧结果的预期来源。新增 14 项范围与版本检查：生产函数的一跳/边序/检索边/关闭边、保存的 group78 现场恢复目标、该对象误改的 collateral 从旧范围下 0 变为新范围下 1、空池断言保留、合同最小差异、旧生成与审计拒绝、编码来源及旧分片防覆盖。它们只操作小字典/临时文件或已公开诊断图；没有重新生成 group78，也没有执行候选或模型。
- 14 项新增轻检查在本地通过；随后补充 full-test marker 的来源、计划、失败/数量/test 访问拒绝断言，并单独重验该纯元数据用例通过。4 项历史 registration 元数据检查亦通过，旧报告/1350/hash 仍可核查。Python/ops 内嵌 Python/Bash 静态检查通过。未在本地执行真实生成、模型训练、causal rollout 或完整套件；旧服务器 250 项成功仅保留历史效力，不能覆盖本次生产修复。
- 唯一 ops 阶段为 `m1_v7_d051_scope_rebuild_full_test`，预计 280 项（既有 266+新增 14），前台显示完整输出并 tee 日志。输出目录由完整 src/scripts/configs/tests 源码 hash 的前缀确定，避免只更新文档/ops 后默认重测；成功 marker 同时锁完整 hash、新合同、rebuild plan、测试数量与干净 provenance。匹配成功复用，失败/中断保留并拒绝自动重启；使用小型历史 train/validation fixtures 和已保存 group78 诊断图，不启动 1000/200-group 实验生成、confirmation 或 test。正式训练与模型预算任务尚未启动。


## LOG-073（2026-09-09）：修正版服务器 280 项全测成功，交付独立 train 生成入口

- 用户返回 `FULL_TEST_RESULT tests=280 exit=0`、`SERVER_STEP_OK id=m1_v7_d051_scope_rebuild_full_test` 与 `FULL_TEST_EXIT=0 LOG_WRITE_EXIT=0`。成功 marker 路径为 `/root/autodl-tmp/cpmt_outputs/m1-v7-d051-full-test-719bb2d494d9/full_test.ok.json`。这是用户提供的终端回执；本地未读取服务器 marker 正文，下一入口会调用既有 validator 核验完整 source/tests hash、计划、v7 合同、280 项数量和无失败/跳过等条件。全测成功是工程证据，不是 CTL 有效性结果。
- 唯一 ops 阶段改为 `m1_v7_d051_corrected_train_generation`，调用既有 `scripts/generate_m1_parallel.py`，固定 v7 合同、train=1000 总混合 paired groups、原 group/seed namespace 和 future_hash_bins=32。最多 16 个生成进程、每进程 BLAS 1 线程；按实际 CPU affinity/cgroup 配额限制进程数，并检查可用主存和磁盘。生成进程不等于后续预算的 4 个训练进程。历史同规模生成约 1001 秒，故本次前台显示进度、保存日志和退出码，该历史耗时不是新版本 ETA 保证。
- 输入是修正合同及已成功全测标记，输出是独立 `/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-719bb2d494d9/` 下的 train.npz、manifest、1000 个分片、运行来源与验收 marker。例如第 78 组仍按原 train 组号生成，不借用旧 validation 第 78 组或换组规避异常。这是 planned 的训练数据重建，不是已经完成的模型训练或确认评测；不改候选/executor/学习算法，不打开 validation/test。
- 入口持独占锁，已有成功产物核对绑定与完整文件 hash 后复用；runner 已有 exit=0 但缺验收 marker 时只续做验收。失败、没有退出证据的中断或未知旧文件均保留并拒绝自动重新生成。首次验收检查正式 manifest/provenance、教师健康门、逐 family 的 1000-group 覆盖、全部精确分片名/大小、数组 digest 与每组 40 个 online decisions，并保存每个分片的 SHA-256。生成成功后本阶段直接结束，不预埋训练、probe、导出或 push。
- 本轮仅修改 ops 与既有实验记录/流程指针，src/scripts/configs/tests 不变，复用刚通过的服务器全测。本地只做 Bash/内嵌 Python 静态检查、入口纯元数据分支检查和 diff 审查；未运行真实数据生成、训练、rollout 或完整测试。修正 train 实际成功、digest 和教师健康结果尚待服务器返回。

## LOG-074（2026-09-09）：隔离实现选参前错误分支检查，尚未运行真实场景

- 用户接受前置工程检查，并澄清服务器成功的是 280 项完整测试，尚非 train 生成。隔离分支实现 runner/helper；生成任务保持原科学源码，固定组号和规则事先记录在 D-051。原终点、安全门、N 和训练划分不变。
- 固定矩阵为 16×2×7=224 条轨迹、4480 次决策。调用生产 materializer、scope 和 executor 图验证器，每步延续选中世界；选择器只接收模板、位置与静态预检。worker 按完整 paired group 读取分片，使用 spawn、CPU/BLAS 一线程；禁止在本机启动真实检查。
- 要求 corrected train 成功标记，核验协议、train=1000、32 bins、健康门、manifest、合并数组和固定 16 个分片文件 hash；生成提交到检查提交之间生产模块不得改变，仅新增工程 helper。只重建 16 组 audit，重新编码须与已验收分片 digest 一致；未改生成器、候选、能量或软监督算法。
- 每步记录 base/post hash、scope、C11 范围外可用目标、MERGE 配对和 executor 失败。构造异常保存当前图/event/步数；生成异常保存限定生成器 frame 的图/event 上下文及 traceback。失败保留，不自动重跑或替换组；漏跑、重复或不足 20 步均不能 PASS。
- 11 项轻量控制流测试通过（0.004 秒）：状态传递、输入不可变、非法执行保留世界、构造失败现场、边序、K 坍缩、非 train 拒绝、选择不读取执行/未来、模板缺失回退、C11 计数和完整矩阵。AST 与 CLI help 检查通过。未运行真实生成、训练、causal rollout 或新增完整套件，不宣称真实工程检查通过。
- runner 尚未成为活动服务器阶段。后续按 D-052 统一准备阶段脚本和固定命令，不再逐步改写唯一入口。并行预算完整接线、fit/inner-dev 差距报告、新 probe/组合登记仍待完成。后续文档修正恢复了先前 PowerShell ASCII 管道损坏的中文，本记录的科学内容与检查规则不变。

## LOG-075（2026-09-09）：train 生成成功，修复运维验收混用轨迹与学习行计数

- 用户终端回执：1000 paired groups、16 workers、1187.1 秒；输出 `/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-719bb2d494d9/train.npz`，learning_rows=40000，其中普通学习行 38000、recovery=2000，digest 前缀 `a1d9f7517feb3c30`。teacher/reference agreement=1.0（38000 普通学习行无分歧），teacher health PASS，GENERATION_RUN_EXIT=0。完整 hash 和服务器 manifest 尚未读回，本记录不把终端前缀当完整指纹。
- 后续 `accept()` 抛 `generation manifest binding/count mismatch`，GENERATION_EXIT=1、LOG_WRITE_EXIT=0。根因是交付的 ops 验收错误要求 manifest.online_chain_decisions=40000、每组普通训练行=40，并把 learning_group_support_by_family 与 causal 覆盖都要求为 1000；这是验收实现错误，不是已发现的新生成器失败。保留 attempt、runner_exit、分片、原 manifest 和失败 JSON，不删改生成产物。
- 编码器 `rollout_learning_arrays_from_audits` 既有行为：完整审计仍每条 20 步，但最后一步无 future_states，编码时跳过；每条保留 19 个普通学习行和 1 个恢复样本，每配对组 38+2=40 行。manifest 的历史字段 online_chain_decisions 实际记普通学习行，不是完整审计决策数。旧 D-043/D-049 报告已记录 38000+2000；旧 learning 覆盖 C03/C04/C05/C06 分别为 961/959/958/954 组，而 causal 仍各 1000。这里核对的是历史字段语义，不用旧数值要求新结果相同。
- 修复只在 ops：header 要求 total=40000、reference-learning=38000、recovery=2000；逐组验证 38 普通+2 恢复并拒绝非法组号、dtype、漏组、总行不一致。causal family 仍各 1000；learning family 覆盖从实际非 recovery 行按 group 与 scenario_family_index 重算，要求与 manifest 完全一致，不再错误固定全为 1000。字段不匹配输出具体 expected/actual。协议、来源、完整文件、数组 digest、健康门等原检查保留。
- 增加 `--accept-only`：必须已有 attempt 与 runner_exit，随后仍核验绑定和 exit=0；缺失、中断或失败绝不启动生成。复用同一 source-bound 目录与既有 280 项全测 marker；数据生成 provenance 保留原提交，当前验收 provenance 单独记录。成功输出明确区分 learning_rows/reference_learning_rows/recovery_rows。
- `ops/tests/test_corrected_train_acceptance.py` 从实际内嵌 Python 提取验收函数，使用小型合成计数向量和临时空文件运行 11 项轻量测试，全部通过（0.142 秒）；覆盖正确口径、字段错误、分组恢复数量错位、漏组/非法组、family 覆盖过报、causal 门保留及 accept-only 无重生成路径。Bash/Python 语法与 diff 检查通过。新增运维测试放 ops/tests，不改变 src/scripts/configs/tests 的科学测试指纹；没有在本地生成数据、训练、跑真实 rollout 或全套测试。
- 当前仅交付修复后续验，尚无 generation.ok.json 成功回执；先验收再进入已登记工程检查，不据此降低任何科学验收门。这次需要同步是必要 bug 修复，按 D-052 允许，不恢复逐步切换必须 pull 的旧规则。

## LOG-076（2026-09-09）：accept-only 错误拒绝 RECOVERY_RELINK 的 -1 编码

- 用户在提交 `badb4b7cacd12cfadb2e2b84e59402e5c095a48e` 运行 accept-only，日志确认复用了 280 项全测且没有重生成；在 `validate_family_support` 抛 `invalid scenario family codes`，GENERATION_EXIT=1、LOG_WRITE_EXIT=0。已有生成产物和两次失败现场继续保留，尚未收到 generation.ok.json 成功证据。
- 根因是上一验收补丁遗漏真实恢复编码，而非数据类型漂移：生成器的 recovery_examples 使用 scenario_family=`RECOVERY_RELINK`；编码器对配置的 C00–C11 查表，未在表中的恢复名称按既有约定得到整数 -1。验收把所有行一律要求为 0–11，错误拒绝 2000 个合法恢复样本。上一版测试只用普通 family 编号构造恢复行，未覆盖生产约定；这是验收实现与测试遗漏。
- 本次只改 ops：普通非 recovery 行必须落在 0–11，recovery 行必须恰为 -1；拒绝普通行 -1、恢复行 -2/0/12，保留 shape/dtype 检查及错误取值报告。family 覆盖只统计普通行。行数、逐组 38+2、causal 各 1000、learning 覆盖重算、hash、协议、来源及 health gate 均不变，不改产物或编码器，不放宽科学验收门。
- 测试从实际 m1_rollout 的 recovery 构造中提取名称，并从实际 m1_af_rollout 编码函数中提取 scenario_family_index 表达式用于轻量 fixture，避免手写普通 family 编号掩盖恢复约定；不 import Torch、不执行生成器。运维回归共 14 项通过（0.611 秒），Bash/内嵌 Python 语法与 diff 检查通过。src/scripts/configs/tests 无变更，既有生成和全测指纹继续使用；服务器只需修复版本的 accept-only，实际最终验收结果仍待回执。

## LOG-077（2026-09-09）：修正 train 完整验收成功，固定工程检查与导出一并交付

- 用户返回 GENERATION_ACCEPT_ONLY（无重生成）、GENERATION_ACCEPTED groups=1000 learning_rows=40000 reference_learning_rows=38000 recovery_rows=2000、SERVER_STEP_OK 与两项 exit=0。arrays_digest=`a1d9f7517feb3c301e856d774369adc9754475a884d236bc49dad43af231136e`；marker=`/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-719bb2d494d9/generation.ok.json`。这是服务器验收成功回执，完整 marker 将由下一阶段读取核验并随导出带回；不假称本地已读取服务器文件。原两次运维失败保留。
- 纳入 LOG-074 已实现的固定 16-group/224-trajectory/4480-decision train 分支检查；生产生成器、编码器、scope、executor 与科学合同均不改。先核验已验收 marker、完整数组指纹、manifest 和分片 hash，确认生成提交到检查提交之间既有生产模块未变（仅允许新增工程 helper），再重建 16 组 audit 并比对其编码与分片 digest。每步使用 production materializer 推进真实所选世界，不用参考世界覆盖错误状态。
- D-052 交付为 `bash ops/m1_train_preflight.sh check` 与 `... export`，同一提交一次同步。固定读取上述实际服务器 marker 和完整数组指纹，输出路径由当前检查源码/测试 hash 绑定。check 前台打印进度、保存 check.log 和退出证据，按 CPU/cgroup 与主存余量最多 4 worker、每进程一线程，GPU 禁用；实际工程检查耗时尚未实测，不给确定 ETA。已完成 PASS/FAIL 均核验后复用，不自动重跑；不完整尝试保留并拒绝重启。
- export 核验源代码/输入绑定、退出码、固定矩阵与逐组文件 hash；无论工程通过还是已完成失败都可导出，失败包含现场 JSON 和末尾日志。导出固定到 `results/m1_v7_d051_train_branch_preflight.json`，包含生成 marker、检查报告、文件指纹和独立导出 provenance，拒绝覆盖不一致的旧导出。成功输出 EXPORT_VERIFIED/PREFLIGHT_EXPORT_OK 不等于工程 PASS；以 report.gate.pass 决定能否进入 probe/预算。中断且无 completion 的尝试仍须审查，不能拿部分成功组放行。
- 新检查控制流 11 项轻量测试通过（0.003 秒）；运维首跑、成功复用、失败不重跑并导出现场、二次导出复用、文件篡改、来源改变、缺报告/中断防护共 7 项测试通过（0.311 秒）。后者使用微型本地报告和模拟子进程，仅验证文件与调度链路；不是实际服务器数据或真实 rollout 测试。AST、CLI help、Bash 语法与 diff 检查完成。本地未执行生成、训练或真实 causal rollout；新增检查代码不冒用旧 280 项全测证据。
- 原生成入口保留历史/兼容用途，不再作为下一阶段命令。固定工程检查尚未运行，probe/预算 runner 新登记接线与 fit/inner-dev 差距诊断仍待后续阶段完成；验收成功不等于方法通过或允许 M2/S6。


## LOG-078（2026-09-09）：固定合并压力分支暴露候选生成器状态耗尽，暂停完整预算

- 拉取结果提交 `4636a55`，读取 `results/m1_v7_d051_train_branch_preflight.json`，文件 SHA-256=`ea058b7468517f59027c740adbc73540c6c97357d323fc7ba43eb8e6cdd16449`，与用户服务器导出一致。服务器 CPU 4 worker、每 worker 1 torch thread，报告 wall=96.721 秒；工程 gate=false，224 条预期轨迹仅 16 条完整成功、4480 次预期决策仅 320 次计入完整轨迹。该计数不含失败轨迹中已执行的步数，不代表只尝试了 320 步。
- 全部 16 组完成 sibling 0 的 NOOP 20 步，随后在 prefer_merge 失败。13 组报 `fixed candidate generator found fewer than two merge pairs`：组 0/133/266/333/399/466/532/599/666/732/799/932/999；其失败图均只剩 2 个 open confirmed 实体，无法提供两对不同实体组合。组 66/199/865 报 `C11 collateral stress requires an unprotected node outside the current evidence scope`。失败 step_index 为 7–17（零基），不是第二条分支一开始就失败。每组遇首个异常即停止，其余策略和 sibling 尚未覆盖，不能据此宣称只有这两类故障。
- traceback 均进入生产 `materialize_rollout_step → generate_fixed_candidates → _proposal_context`，并非新增 checker 自己的 MERGE/C11 断言。正式 `causal_rollout_metrics` 在模型预测前调用同一 materializer；若模型到达这些状态，也会中断评测。固定偏好合并是压力规则，本报告不估计实际 A–E 模型发生概率，不判 CTL 科学 no-go。
- 本地仅读取已有 16 个失败快照，对 `validate_graph` 和单次 `_proposal_context` 做轻量重放：16 个图均通过 invariant，16 个异常及消息全部一致复现（0.016 秒）。3 个 C11 快照反转边序后 scope 均不变；本次 C11 同名异常不能据此说是一跳修复失效。未生成数据、未推进完整 rollout、未训练或读取 validation/test。
- 白话：状态耗尽指连续合法编辑会消耗后续候选构造所需的对象。输入是已被合并多次的记忆图，输出本应仍是可评分候选或明确的不可用槽位；例如只剩两个实体时只有一对可合并组合，原生成器仍索要两对便抛错。它不等于图结构非法，也不证明模型一定这样选择。当前关于不可用槽位的处理只是待设计方向，尚未实现或接受；不能直接删断言、复制 NOOP 凑 K、添加对象或换组放行。
- 已验收的参考 train 仍保留，检查证明其重建分片 digest 一致。参考轨迹生成通过不保证偏离参考后的所有状态可处理。完整选参继续暂停；先设计同时符合候选 K/去重、online 公平性与 C11 coverage 语义的修复，并评估是否改变原 train 候选/监督，再决定重建范围。没有根据本次报告自动重生成、重训或改变已登记效应门。失败现场完整保留，不覆盖原报告。


## LOG-079（2026-09-09）：实现 opt-in 不可用槽位诊断及同版本 test/check/export

- 针对 LOG-078，在 `m1_rollout.py` 加入默认 false 的 `allow_unavailable`；原严格生成、教师与正式评测调用保持默认。实验分支处理 MERGE 配对不足、C11 无范围外对象、SPLIT 无证据与 canonical 去重空位。无法构造的位置保留为显式不可用槽位，mask=false、post=null、execution_attempted=false，不执行空槽，不伪造新世界或补充对象。所有实际事务执行原 executor；正常槽位与原随机排列不变。正式采纳尚待验证和登记，不能把运行不中断等同于方法有效。
- 本地对 16 个已保存失败图进行一次候选构造及执行检查：全部原异常在默认严格模式继续复现；opt-in 均返回 16 格，其中恰好 1 个不可用槽位，唯一正常 NOOP 可选，其余真实候选从原 immutable base 执行。图/hash 不变，未生成新场景或推进完整 20 步。另以一个保存图构造非 C11 的局部 fixture，验证正常模式的程序、证据和顺序一致；它不是保存参考轨迹的兼容性证明。
- 新增 8 项单元测试通过（1.227 秒）：真实失败严格复现、opt-in 槽位/世界/准入边界、空槽不调用 executor、隐藏参考字段不影响结果、正常候选兼容、canonical 重复不补合法 NOOP、未知错误仍拒绝、正式入口默认严格。原 11 项轻量 branch helper 测试通过（0.003 秒）。未在本机生成数据、训练、运行完整 rollout 或完整套件。
- 新诊断 runner `scripts/run_m1_candidate_availability_check.py` 绑定原失败报告 SHA-256 和 16 组已保存审计 gzip hash。计划先核对每组 40 个参考步骤+2 个恢复步骤：当前 strict/opt-in 程序与证据一致、程序及执行结果与保存审计一致、无不可用参考槽位；然后跑原固定 224 条完整轨迹/4480 次决策。不同于旧诊断遇异常停止该组，新诊断保留每条失败图和 traceback 后继续检查剩余固定分支，任何失败仍使总 gate=false。逐步报告不可用原因、C11 无目标暴露及全部完整/失败分支，不改变组集。
- 服务器入口为 `ops/m1_candidate_availability.sh test|check|export`，一次同步后分块执行，全部前台。先运行完整 unittest discovery（预期至少 299 项、零错误/失败/跳过），marker 绑定当前 source/tests、ops 与原报告 hash；check 仅复用服务器旧 `/root/autodl-tmp/cpmt_outputs/m1-v7-d051-branch-preflight-a488142c3548/run/` 的审计，不调用 train 生成。CPU 最多 4 worker、每进程一线程。工程结果只能说明保存的 16 组参考兼容，不自动推广为全部 1000 组。
- 新输出使用独立 source-bound `m1-v7-d053-availability-*`，已完成失败或成功都可核验并导出到精确 `results/m1_v7_d053_candidate_availability.json`，包含完整失败快照、逐组摘要及文件指纹；源头报告、原失败目录、train 数组保持。中断/未知产物不自动覆盖或重启，失败出口明确仍可 export；`formal_budget_authorized=false` 恒定。
- 新运维 5 项微型文件测试通过（0.166 秒）：失败不重跑、失败导出与复用、产物篡改拒绝、中断拒绝重启、full-test 失败阻止诊断。AST、Bash 语法和 diff 检查通过。这些只验证本地控制流，不替代服务器完整测试或真实矩阵。原严格工程门仍 FAIL，正式模式接入、评价口径与来源兼容性尚待后续审查。


## LOG-080（2026-09-09）：D-053 全矩阵通过，审查候选不可用分布及执行拒绝

- 拉取提交 `762ab50`，读取 `results/m1_v7_d053_candidate_availability.json`，文件 SHA-256=`d1a1fd70782c42a3842414f57a0fcc2293e4dbf11f2ead681e3a170fe2cd6d7f`。报告绑定原失败报告 SHA-256 `ea058b7468517f59027c740adbc73540c6c97357d323fc7ba43eb8e6cdd16449`，运行提交 `b7caeda3dfb4ef28704b6ecd74cfc9563e27837e`、干净工作树和 source/tests=`46784c2d40c0879fc30068de4e4de2e1507f0db823d15d4d4ef23986da9f617e`。本地按该提交 Git 文件及 Linux 换行规则（.ps1 依 .gitattributes 使用 CRLF）重构来源指纹一致；直接比较 Windows 工作树字节会因换行不同而不一致，不据此误报科学源码变化。
- 全测 299、errors/failures/skipped=0、exit=0；test/check binding 一致。16 组均 reference_steps_verified=40、recovery_steps_verified=2，总 640+32。固定矩阵完整 224 条，每条 20 步，共 4480 次；failed_groups=[]、failure_snapshots={}、gate=true、check exit=0。实际 wall=95.374 秒，4 CPU worker；不作为后续模型训练或完整评测 ETA。
- 本地重新计算矩阵 gate，逐分支选中模板数之和均为 20；各分支不可用原因总和与逐组一致。用导出内容重构各组 result.json，SHA-256 与报告记录一致，并与 completion manifest 交叉核对所有逐组文件指纹。成功轨迹 gzip 本体仍在服务器，未在本地逐条读取；兼容性与逐步 invariant 通过证据来自已验收服务器 runner 和报告，不声称本地重新执行了 4480 步。
- 不可用统计是槽位暴露次数，不是失败轨迹数或全部不同决策数：MERGE 配对不足 304 个，全部出现在 prefer_merge、覆盖 16 组；C11 无目标 12 次，也仅在 prefer_merge，涉及 0/66/199/333/865/932 六组的 12 条 sibling 轨迹。canonical 重复 8 个，仅在 prefer_retract，涉及 133/333/799/865 四组。SPLIT 无证据处理本次未触发，不能宣称该分支已获真实矩阵验证。12 次 C11 无目标均保留在完整轨迹中，不排除时刻或组、不把不可触发损害当作安全改善。
- 每条规则共 32 条轨迹/640 次选择。prefer_merge 实际选 MERGE=504、NOOP=136；prefer_retract 为 RETRACT=630、NOOP=10；NOOP、RELINK、SPLIT、BIRTH 优先规则各选其模板 640 次。prefer_split 的 544/640（85%）次选中程序被 executor 拒绝并保留 base，固定随机规则另有 10 次执行拒绝，其余规则无选中执行拒绝。拒绝是既有 QUARANTINE 语义，不是图 invariant 崩溃；因此完整 20 步不代表 20 次成功修改或学习到恢复。报告未导出成功轨迹内所有拒绝原因正文，不臆测这 544 次具体由哪一 precondition/invariant 引起。
- 固定随机的 640 次选择没有不可用槽位，仍包含原执行拒绝；这只能说明该固定小样本路径未触发槽位修复，不能推断实际模型触发率为零。正常参考/恢复状态在保存的 16 组上候选、顺序、证据和执行记录一致，支持继续审查该方案；不等于证明全部 1000 组学习数组/教师不变或真实模型泛化成立。
- 结论：接受本份诊断报告为 D-053 工程证据，不覆盖 LOG-078 的严格 FAIL，也不将 proposed 模式自动切为正式。接下来应落实共享候选可用性规则、unavailable/非法执行/候选缺失的独立口径、C11 可用性披露和生成/评测来源绑定，再按既定条件进入固定 probe 与小样本模型贯通。当前无新生成、训练、validation/test 访问；formal_budget_authorized=false。没有基于此报告重生成 train、扩网格、调整安全或效应门。


## LOG-081（2026-09-09）：正式可用性评测接线、独立统计及 train 来源桥接

- 用户要求继续正式接入，D-054 固定新评测策略。新增 `configs/m1_candidate_availability_policy.json` 与 `m1_candidate_policy.py`，严格验证完整策略后才在 `causal_rollout_metrics` 启用 slot handling；S5 evaluation_config 只从 evaluation plan 接收策略，丢弃 checkpoint 自带的同名项，防止未登记切换。旧默认调用、旧组合登记仍保持历史行为，新 fixed probe 和 S5 最终计划尚需绑定本策略。
- 新统计仅在在线选定动作并持久化之后读取评测参考：逐步记录 unavailable/真实构造/执行拒绝/可选合法数量、当前参考语义是否可由候选达到、C11 范围外目标和指定合法 collateral 对照是否可用。序列与总体汇总单列，原 rollout_graph_metrics、paired group、20 步、co-primary、安全分母/阈值均不改。C11 零分母返回 null；不可用不混成 executor-illegal。语义不可达诊断不等于已定位生成器单独责任，也不进入在线输入、选参或新成败门。
- 新 `m1_train_reuse.py` 绑定原生成提交、marker/arrays/evidence 指纹与已审查的五个源码差异：m1_rollout、m1_branch_preflight、m1_af_rollout、新 candidate_policy 和 train_reuse。除已锁定的精确源码变化外，原生成器/executor/依赖不得变；m1_af_rollout 通过 AST 比较要求训练和编码的所有原定义不变，仅排除 causal evaluator 及其新 import。默认严格生成路径经源码审查，16 组参考行为一致仍作有限实测支持。所有 1000 shards+train.npz+manifest 共 1002 个文件须与原验收 SHA-256 一致才允许建立复用记录；不修改原 marker、原 generation commit 或数组。
- 本地四项候选策略测试通过（0.199 秒）：完整策略漂移拒绝，C11 空槽与 executor 拒绝分别计数且保留分母，零 C11 分母为 null，不可用位置不能变可选。五项来源测试通过（0.281 秒）：1002 文件名覆盖、单片改变拒绝、未审查源码拒绝、清单缺片拒绝、当前真实源码差异及训练编码 AST 对比。文件覆盖测试用微型 metadata 和 mock digest，不假称已在本地读取服务器全部数组。
- 新服务器集成测试调用真实 causal_rollout_metrics，在固定一组 train fixture 上核对 full-reference oracle 原指标不变、连续 MERGE 的特征评分模型遇耗尽仍完成两条 20 步并输出不可用统计，以及保存模型不能越过计划启用策略。测试不训练模型，不是完整 checkpoint 保存/加载小预演。本地未运行这些真实 rollout 测试；新的完整测试静态计数为 311 项，须在 AutoDL 通过。
- 同一版本交付 `ops/m1_candidate_policy.sh test|reuse|export`，全部前台。test 复用已验证的全测交付函数并绑定其源码；reuse 只读原 `/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-719bb2d494d9/generation.ok.json` 及其文件，显示每 100 文件进度；成功/已完成失败均可导出到 `results/m1_v7_d054_candidate_policy_and_train_reuse.json`。新输出目录 source-bound，旧产物不覆盖，中断不自动重启。
- 三项运维微型测试通过（0.052 秒）：已完成失败不重复验证、失败可导出且重复导出复用、完成报告篡改拒绝；AST、Bash 语法、diff 检查通过。本轮未生成完整 train、训练、运行完整矩阵或访问正式 validation/test；311 项服务器全测与实际 1002 文件核验尚待回执。即便 reuse accepted，formal_budget_authorized 仍为 false，固定 probe/新组合登记、并行选参和模型小预演仍须完成。


## LOG-082（2026-09-09）：D-054 服务器全测与原 train 复用验收报告复核通过

- 拉取结果提交 `754149c`，报告 `results/m1_v7_d054_candidate_policy_and_train_reuse.json` SHA-256=`2d7ff07ccb1cf9ff29084d39ccd0faa653c678ae40dfaf6f3388aabb1c1a965c`。运行提交 `2febabf9ef60b8f37e212714b54354499bf0e811`、工作树干净；full_test 为 311 项，errors/failures/skipped 均为 0，test/reuse exit 均为 0，accepted=true。
- 服务器报告 verified_files=1002、verified_train_groups=1000，原 generation commit、marker SHA-256 和 arrays digest 均与复用策略一致；数组 digest 仍为 `a1d9f7517feb3c301e856d774369adc9754475a884d236bc49dad43af231136e`。编码定义检查为 unchanged_except_causal_evaluation，五个源码差异与已审查清单一致；共享候选策略完整匹配登记配置。
- 本地重构内部 reuse.report.json 的序列化 SHA-256，与 completion 的 `de495a5367ae8b1b0d00b171ac859857460e0716918df637175b65a850b6a035` 一致；test/completion/report 来源绑定一致。按运行提交的 Git 文件及 Linux 换行规则（.ps1 为 CRLF）重构 source/tests=`176275ba3aa76e8f0fe561f9d5b0d4064d532f3db2fef7dfaa56d4f7989c869b`、source=`0548ba886ff71391500de96becbd57073d03defd7c0b4d701169f9e4ac8e8a75`，以及两个运维文件和共用全测交付函数指纹，全部一致。两份历史证据报告指纹亦与策略一致。
- 接受该报告为原修正版 train 的复用依据：无需重新生成 1000 组。1002 文件读取发生在服务器，本地没有这些数组，也未重做全测或轨迹；参考行为实测仍限于已有 16 组，all_groups_regenerated_and_compared=false，不把字节核验描述成全部 1000 组的新行为对照。全测包含小型集成 fixture，通过不等于真实模型学习或泛化成立。
- data_generated/training_performed/validation_access/test_access/formal_budget_authorized 均为 false。复用数据不复用修复前的模型或选参结论；固定 probe/新组合登记、并行选参与同口径 fit/inner-dev 诊断、真实模型保存/加载和配对评测导出小预演仍待完成。当前只更新验收记录与流程指针，无方法、预算、门槛或科学代码变更。


## LOG-083（2026-09-09）：修正版固定 anchor probe 与机械组合登记交付

- 新增 scripts/run_m1_corrected_probe.py，沿用 D-051 固定 Set Transformer、A/C/E、五 seeds、lr=0.0006、3000 updates、C weight=1；799 fit/201 inner-dev 的完整 paired-group 分区不变。绑定已验收 D-054 报告、修正版协议、重建计划、旧 overlay 中的固定 anchor 来源和共享槽位策略；旧 v6 runner/registration 不改写。生成/编码来源仍严格匹配原 D-054 五文件审查清单，没有因为新增运维和 probe 脚本而重生成完整 train。
- prepare 只读原 train.npz/manifest 指纹及固定 201 个 shard；worker 自行读取对应 shard，重建该组两条参考审计并用既有数组比较函数逐字段精确对照。单组局部编号映射回原 group，先写 audit 后比较，避免 daemon worker 嵌套创建 Pool。最多 4 worker，按 cgroup CPU/内存限制下调；每个 worker 仅处理一组世界，不向 worker pickle 全部审计。全局 H3/H1 诊断与 F 评测使用可重复磁盘迭代器；F exact/graded/open-memory/AUC/node 任一失败即不开放训练。
- train 在 CPU、torch/BLAS 单线程下顺序执行固定 20 模型（5 scorers+15 students），保留原 Adam/随机流/监督目标与注释 mask；每个模型独立完成目录、精确 binding 和文件哈希，保存 primitive/tensor checkpoint 并加载核验。学生输出固定 3000-step 的 fit/inner-dev 同口径 reference-history 诊断及差距，E scorer 保存原 outcome diagnostics；无 checkpoint/设备/参数择优。它不是两臂完整网格，也不把 inner-dev 分数当独立 test 精度。完整预算逐 checkpoint 的同口径诊断仍待实现。
- evaluate 只从保存权重加载，顺序跑 15 个 method/seed，每个 201 组、402 条完整轨迹、8040 次决策；磁盘迭代保留每组两条 sibling，完整 20 步不拆。逐步写实际 materialized 候选、选择与持久化世界，validate_graph 检查执行后世界；保留失败及来源。序列须满足精确 paired-group/sibling 覆盖、20 步索引、前后图哈希链和共享 mask。CPU 前向 p95 在本阶段无训练/其他评测 worker 竞争时计量，仍只代表网络及相关 tensor 操作，不代表整个系统延迟或机器全局独占。
- summarize 在均值/SD 前核验每组 A/C/E 五 seed×两 sibling 与 F 两 sibling 完整无重复，再调用既有 group-first 统计；强制三项既定 co-primary 均非退化，禁止旧 graded 回退。F 或固定终点不可用时 N=null、registration=null，保留报告；通过时按六格原功效公式、向上取 10 整数和 floor=1350 创建 cpmt-m1-corrected-post-probe-registration-v1。登记包含效应/安全门、共享槽位和执行边界，test 与完整预算授权恒为 false；这是待结果回传核验的新登记产物，后续 S5/S6 消费入口尚未因此自动接好或解封。
- 新 ops/m1_corrected_probe.sh 同一版本提供 test/prepare/train/evaluate/status/summarize/export；测试、准备、固定训练和汇总前台，预计超过半小时的完整评测默认后台，并有独立 status。每步检查前置 marker、源文件及日志指纹；成功复用，失败/中断不自动重启。export 可导出已完成失败的 traceback/log tail，也可在成功汇总后导出报告和封存登记；精确路径为 results/m1_v7_d054_corrected_endpoint_probe.json。要求至少 20 GiB 空闲磁盘保存审计；不会删除或覆盖旧输出。CPU 固定训练尚无本轮耗时实测，不给精确 ETA。
- 本地 11 项轻量检查通过（0.898 秒）：固定合同与 201 分区、N 下限和上调公式、禁止 graded 切换、F 失败、缺 seed/重复 sibling/非有限值拒绝、登记重算与封存、状态链断裂拒绝；3 项运维微型测试通过（0.018 秒）：已完成失败不重算、中断不重启、前置失败阻止后续。另添加服务器完整测试中的一组真实 train 重建→数组对照→模型保存/加载预测一致→两条 20 步→完成产物复用测试；该模型未训练，本地未运行该生成/rollout fixture，不将其写成短训模型小预演完成。静态预计全套测试 323 项，实际以服务器回执为准。无本地重任务、真实 anchor 训练、validation/test 访问或新科学成绩。


## LOG-084（2026-09-09）：不干扰运行中 probe 的 GPU 并发公共路径开发

- 用户要求等待 evaluate 时先执行不冲突的工作。本轮仅在本地开发和运行轻量 metadata/metric/artifact 测试；未访问服务器、未启动 GPU/CPU 训练或生成数据，也未修改 run_m1_corrected_probe.py 或其运维入口。用户回执显示 prepare/train exit=0、20 模型已保存、evaluate 在运行；这不是新 probe 汇总或成绩验收。
- 新 scripts/m1_training_jobs.py 使用 ThreadPoolExecutor 管理最多四个独立 Python 子进程；调度线程不持有共享模型、optimizer 或随机流，每个子进程只跑一条 architecture/seed/method/lr 路径。每条路径保留同一个优化器连续更新，在固定 checkpoints 保存 CPU tensor 权重、教师缓存、概率、同口径指标及 trace。所有子进程 CUDA_VISIBLE_DEVICES 固定同一 GPU UUID，OMP/MKL/OpenBLAS/torch 均单线程，不把四进程误称四张 GPU。
- worker 复用现有 train_student/train_outcome_scorer、model_kwargs、shared mask、teacher 选择与 durable complete_unit；生成器、学习算法和 src/ 下的原编码/执行器均未变。budget 模式按既有 group hash 拆完整组，refit 模式使用全部输入 train 并明确 inner_dev=null/independent=false。A/C/分类器使用原 pstar，current-only 使用 pstar_current，E 只读同架构/seed/数据/模式的已完成 scorer；依赖的 marker 与模型文件指纹须一致。独立 scorer 批次全部完成后才派发学生，不拆一个 optimizer 的更新路径。
- 固定 GPU 检查计划在执行前写入 fixed_plan()：原修正版 train 的 group 0..9，读取原分片并核对 generation marker/逐片 hash，不重新生成或重采样标签；10 组共 400 学习行，按原 hash 是 9 个 fit 组和 1 个 inner-dev 组。两架构×seeds 7/19，scorer+A–E，steps 10/30，lr=0.0006，C weight=1；分别运行 budget/refit 的单进程与四进程，共 96 条短训练路径、48 对比较。小样本仅验证工程等价，不据一个 inner-dev 组判断泛化、选超参或改变效应门。
- checkpoint 的 fit 与 inner-dev 使用同一普通行 reference-ranking accuracy 和逐组均值；recovery 参与训练但从普通行指标分母排除。指标与旧预算 helper 的同口径结果在轻量 fixture 中一致；学生前向分批 64 行，避免增加全 fit 评估时的显存峰值。完整预算 checkpoints 300/1000/3000/10000 的正式编排仍待接入，不能将短检查的 10/30 分数冒作选参成绩。
- 对拍比较精确 tensor 值、概率、教师、逐 checkpoint 指标和 trace；不要求 torch.save ZIP 字节一致，不根据看到的误差临时放宽容差。每个模型从保存权重加载；学生重新前向概率须与保存记录一致。每个架构内 A–E 参数签名核对一致。差异、子进程失败、未完成任务和 traceback 均保留；无自动重试、覆盖或替换样本。已完成失败也能 export，报告包含失败子进程日志尾部，避免只有父进程报错而缺失根因。
- 新 ops/m1_parallel_training_check.sh test/check/export 为前台有界检查，独立源码绑定输出目录，精确导出 results/m1_v7_d054_training_process_check.json。test/check 之前均检查 /proc 中是否仍有当前 corrected probe evaluate，若存在则在新 attempt/训练前拒绝，避免污染本轮 CPU 延迟。四进程必须通过既有 cgroup CPU、显存和内存保守阈值；这只是十组检查容量，full_population_resource_check_completed=false，不能外推已满足 1000 组四进程的实际峰值。完整预算与 S5 正式登记消费保持禁止，机器报告显式 full_budget_or_s5_registration_consumption_implemented=false；后续仍须完成两者编排，不能遗漏 S5。
- 本地 13 项公共路径轻量检查通过（0.416 秒）：冻结架构/GPU 单线程配置、禁止正式任务/参数扩张、E 依赖错 seed 拒绝、完整组隔离与 refit 非独立、指标对照旧定义、masked/nonfinite 拒绝、四并发上限/排序、重复任务和失败不重试、精确数值比较、微小差异拒绝、配置漂移和权重篡改拒绝。4 项运维微型测试通过（0.028 秒）：活动 probe 阻止启动、完成失败不重启、中断不重启、失败可导出并复用。测试只使用小型数组/tensor 文件和受控调度函数，没有模型训练或 GPU；AST、Bash 语法、diff 检查通过，原 D-054 generation/encoding 来源桥接仍一致。静态全套预计 336 项，服务器新全测及 GPU 对拍尚未运行。
- 重要交接边界：新脚本会改变全局 source/tests 指纹。当前服务器不能 pull；必须先用当前版本跑完 evaluate、summarize、export，保留并提交该精确 probe 结果，再同步新阶段。没有要求为本轮本地开发重复已成功的 prepare/train，也没有将开发中的 GPU 方案套进当前 CPU probe。

## LOG-085（2026-09-09）：预先接线后续检查、固定并行预算与全 train 重训

- 用户要求复用当前 probe 已覆盖的工程证据，并把已确定的后续阶段一次准备好。本轮实现 `ops/m1_corrected_followon.sh` 的命名动作和对应正式 runner，未操作服务器或启动训练/生成/rollout。当前 probe 的 runner、运维脚本和 `src/` 科学模块未修改；仍须在原服务器版本完成 probe 汇总/导出。阶段顺序和命令只维护在 M1_V2_CLOSEOUT_FLOW，不新增交接文件。
- 新 `m1_corrected_training_plan.py` 消费修正 probe 的完整导出，逐例重算原登记，F/固定终点失败时不发放预算。核对固定合同、train digest、旧运行 commit 的科学 src 与 probe 实现；新全局 source/tests hash 不冒充旧 probe 的运行来源。GPU 对拍报告须对应当前源码，48 对保存权重/概率/指标再次核验。后续直接复用该来源完整测试回执，不再因更换 ops 入口重跑全套测试。
- 训练 worker 增加带配方指纹和 ready 回执的 train-only 模式。两臂共 30 条 scorer 优化器路径，选完对应 scorer 后才派发 150 条 A–E 路径；每条连续更新到 10000，并在 300/1000/3000/10000 保存 checkpoint，不把它们当四次独立训练。之后仅在 C 已选计算格补 0.1/10，两臂共 20 条；基线 weight=1 复用。共 200 条路径、740 个不重复 checkpoint 观察。使用原 group-first/等权五 seed reducer、平手规则、原 260907 seed 的预算不确定性诊断和共享/交叉计算格诊断；不扩网格、不选架构或幸运 seed。fit/inner-dev 同口径分数与差距、参考槽位静态不可用、教师参考错误与学生/教师不一致分别记录；这些不是完整视觉候选召回或独立泛化成绩。
- 全 train refit 从预算保存的逐组指标重新核对选择结果，复用同一公共 GPU worker，在原 1000 组、原 label mask 上从头训练 10 scorer+50 student。E 只消费同架构/seed/数组/人口/来源的已完成 scorer；C 读取最终已选 weight。refit 的 inner_dev=null/independent=false，不把已用于拟合的旧 inner-dev 继续称为独立验证。两臂预算和 refit 都按四独立进程、每进程一条 torch/BLAS CPU 线程接线；服务器运行与容量验证尚未完成。
- 固定容量检查使用两架构各 scorer/A、seed 7、lr=0.0006、完整 1000 组 refit 人口、两步更新，四条路径同时运行并记录资源采样及分配峰值；只作运行资源门，不用分数调参或宣称长任务资源保证。显存/主存余量失败即保留现场，不能静默改科学配方。
- 新 `m1_paired_evaluation.py` 按完整 paired group 分片，spawn worker 只接收路径/小型配置，自行加载一个保存模型和每组两条审计轨迹。模型加载放在首个任务内，错误传回 parent，避免 initializer 失败导致反复派生 worker。每条轨迹保持 20 步状态连续，保留实际候选执行、在线输入、选择与持续世界；审计使用 gzip level 1。parent 按组号合并并拒绝缺项/重复/断链，worker 前向 p95 不用于报告；关闭进程池后单独重放已记录的在线前向，验证 argmax 选择不变并测同范围 p95。这是网络及概率运算耗时，不是系统总延迟或机器全局独占测量。
- 新增接口检查复用 GPU 对拍的两架构 A/C/E、seed 7、30-step refit 权重；固定原 inner-dev 组号前四组，共六模型×四组×两 sibling×20=960 次决策/布局。只对新增路径运行不分片串行与四 worker 两种布局，全部逐例科学记录须精确相等，不按效果挑样本或放宽容差。另直接读取 probe 已保存的 201 组五 seed 逐例 JSON，调用原 paired bootstrap/安全门/Holm 公共数值路径；不重跑 120600 次 probe 决策、不为接口检查额外训练。四组和 201 组统计均明确 train-only 工程用途，不据此作 M1 成败判断。
- 每步单独保存来源、attempt、exit、日志 hash、产物指纹；成功复用，失败/中断不自动重跑，导出能保留失败日志与子进程现场。阶段可连续使用已生成但未提交的精确 results 导出，科学代码必须干净；不为每个成功步骤要求 git commit/pull。预算根据历史同网格耗时默认后台；refit 读取当前机器已完成预算路径估时，只有预计超过 1800 秒才默认后台，否则前台，`--foreground` 可明确覆盖。其余短检查前台输出。
- 本地通过 18 项新轻量测试（0.151 秒）、13 项公共 worker 回归（0.451 秒）、7 项运维检查（0.031 秒）和原 4 项 GPU 对拍运维检查（0.017 秒），共 42 项。覆盖完整配方、拒绝扩格/漏 seed/重复任务、真实预算编排配模拟分数验证三道顺序及 C 不重选计算格、配对/链校验、分片排序、单进程前向 mask/选择字段、复用/失败拒绝与导出、refit 耗时估算。这里只运行小型数组/tensor 与 metadata/模拟任务，不是实际 GPU 或真实 rollout 验证。AST、Bash 语法及原 generation/encoding 来源桥接检查通过；服务器全测、GPU 对拍、容量和实际新增接口检查均 pending。
- 实现边界：本交付止于检查、两臂原网格及 60 模型 refit，并提供后续可复用的配对评测/统计函数。正式 S5 confirmation/S6 的新数据生成、一次性消费 reservation、最终报告与 test 解封仍未由本入口实现或授权；不把公共接口已写好表述成正式 S5/S6 已通过。

## LOG-086（2026-09-10）：修正版固定 anchor probe 导出复核通过

- 从 main `58fe92a` 拉取 `results/m1_v7_d054_corrected_endpoint_probe.json`，文件 SHA-256=`86ba54c4fdb9457bba373d6d1187a25d2bd0c059e75a7fbda51d80013a8ac720`。原运行 commit=`e5c25231e006c469789a02ba2c40e1a644e03034`、干净工作树，source/tests=`b7ec2ddbfcddc475a3760c8a72b71a1108758dbd19728a4fdbc49d2714b5aecc`，train digest 仍为已验收的 `a1d9f7517feb3c301e856d774369adc9754475a884d236bc49dad43af231136e`。后续正式消费者 `consume_probe()` 在本地读取实际导出后通过：合同、原运行科学 src/probe 实现、配对支持、F/终点及完整登记一致；没有读取服务器大数组或重跑轨迹。
- 回执：323 项 full test，failures/errors/skipped=0；prepare/train/evaluate/summarize 均 exit=0，分别耗时 1984.981/1871.076/14315.849/7.371 秒。evaluate 约 3 小时 58 分钟，summarize 实测约 7.4 秒。failure map 为空。A/C/E 各五 seed×402 条轨迹、每条 20 步，另有 F 的 402 条参考轨迹；导出保留 6432 条终点记录。完整候选执行审计、权重和状态链仍在服务器，不能把本地 JSON 核验称为重新执行验收。
- F exact/active graded/open-memory graded 均为 1，open-fact AUC 与 active-node error 均为 0；固定三项 co-primary 对两条主对照均非退化。逐组先平均两 sibling/五 seed，独立复算六格 paired SD 与均值，均与报告一致。六格原功效公式需求均低于 floor；最大原始需求来自 exact A−E，约 842.997，按 10 向上取整为 850，仍按 D-051 下限维持 N=1350。保留 exact，不重选 endpoint、不调效应门、不生成 test。
- 五 seed 均值（A/C/E）：最终 semantic exact=`0.920398/0.748756/0.382587`；final graded open-memory correctness=`0.932137/0.918196/0.859446`；全程 open-fact error AUC/100 decisions（越低越好）=`9.164179/22.393035/13.159204`。A−C exact/support 改善为 `0.171642/0.013941`，burden 减少 `13.228856`；A−E 对应为 `0.537811/0.072691/3.995025`。A−C support 均值仍低于 0.03，两项 burden 减少均低于 40；因此不是全部成败门通过，不能据此宣布 M1 成功。这里只按既定规则接受指标可用性与样本量登记，不基于固定探针成绩另开调参规则。
- 固定参考历史的单步 fitting/inner-dev accuracy（A/C/E）分别为 `0.944997/0.942236`、`0.934866/0.932757`、`0.905942/0.903561`，差距约 `0.002761/0.002109/0.002380`。这不是独立 validation/test，也不能用小单步差距担保连续运行泛化；C/E 的最终 exact 跨 seed 波动明显，原因仍需固定预算诊断，不从目前结果直接归因或改变搜索。
- H3-vs-H1：7638 普通行、201 完整组，平均 TV=`0.0033031878`、KL=`0.0034901599`、argmax change=0，两种 teacher/reference agreement 均为 1。H3 reference probability 相对 H1 平均变化 `-0.0024014093`；仅为教师分布诊断，不证明 H3 学生优于 H1。上述结果不进入样本量以外的新选择，也不改变预登记成功条件。
- 本轮只改记录与流程指针，未改变源代码、配置、测试或运维入口；服务器已取得 `ef210c0` 后续代码时，可直接执行已交付的 follow-on `test`，无需为本次文档记录再同步一次。新来源完整测试、GPU 对拍、容量/新增接口等条件仍 pending；不重复原 probe。

## LOG-087（2026-09-10）：follow-on 单次迭代器导致空评测，修复并保留旧成功证据

- 用户提供服务器失败回执：`m1_v7_d054_followon_interfaces` exit=1，目录 `/root/autodl-tmp/cpmt_outputs/m1-v7-d054-followon-cc2d5e2113ed`；NumPy 空均值警告后抛出 `ValueError: missing/duplicate sibling pair`。前置步骤成功目前依据用户操作记录，恢复入口仍须逐项核验实际 marker、退出状态和文件 hash，不能把本地检查称为服务器验收。
- 根因已从调用链定位：新增 `m1_paired_evaluation.run_serial` 传入一次性 generator；`causal_rollout_metrics` 先遍历检查两 sibling 的 pivot，再遍历执行轨迹，第二遍为空。这是适配器错误，并非候选缺失或模型训练失败。固定 probe 使用自己的可重复读取对象，原已验收结果不受此处错误影响。
- 修复只将该适配器改为 `ReplayableAudits`。白话：它解决“检查读过一遍后，正式评测无数据”的问题；输入为固定分片路径与 hash，输出为每次重新读取的同一组审计记录。例如配对预检查读完两条轨迹后，执行循环仍能重新读取两条。它不是复制所有 audits 到每个 worker，也不改变轨迹、候选、标签、模型或统计门。
- 新 `repair-test` / `repair-adopt` 恢复入口检查与 `ef210c0` 的来源差异仅为本次迭代器替换及新增回归测试；重新运行当前来源完整测试，随后只读核验旧 GPU 对拍、四条容量训练路径、train/probe 输入、退出记录及旧失败的空执行文件。旧目录原样保留，新目录明确记录原执行来源与复用角色；不把旧测试冒充新测试、不自动重新训练、不删除失败分片。若发现不同失败、已有实际执行或后续预算启动，则拒绝此次特定恢复。
- 本地 4 项读取器/实际核心循环入口回归、5 项恢复验证和 7 项阶段运维回归通过，共 16 项；实际核心循环测试在第二次遍历入口主动停止，不执行真实轨迹。未在本机训练、生成或运行真实 rollout。服务器新版全测、复用核验、串行/分片实测仍 pending；本次不改变科学合同、原网格、N=1350 或验收门，不新增科学 decision。

## LOG-088（2026-09-10）：修正版两臂预算与 60 模型 refit 导出复核

- 从 `4c89e59` fast-forward 拉取服务器结果提交 `cb13046`。三个文件 SHA-256：checks=`727a968e4bc62a3110e1d8f9b9cb2fc7092aa506fe8e77dd6a3c56e3122b0a97`，budget=`0233215aca1b2c46c7a084d90fa11dd46b5ee9f6aa128deec834502a8365c0e7`，refit=`1e9f496edf5a5502fa3c0320594a132eb462f25be173237d87bc522674e47af2`；路径分别为 `results/m1_v7_d054_corrected_checks.json`、`results/m1_v7_d054_corrected_budget.json`、`results/m1_v7_d054_corrected_refit.json`。GitHub 大于 50 MB 的提示为建议性警告，推送已成功，不删除或改写原导出。
- 三份导出 pass=true，当前 failures/failed_jobs 为空，全部阶段退出码 0，validation/test access=false；旧 iterator 失败保留在 verified_input_adoption，不能将当前空失败表解释为从未发生错误。修复后 358 项全测 failures/errors/skipped=0。新来源为 `5d279f14e2f652e1d9edf94dcdfe61693c02d6012eaf8f308304270a9b7dedf3`。接口检查 202.977 秒，预算 7484.050 秒（2 小时 4 分 44 秒），refit 1136.194 秒（18 分 56 秒）；复用 prepare/capacity 的 0 秒是核验复用记录，不是原执行时间。
- 预算 799 fit/201 inner-dev，200 条优化器路径、740 个 checkpoint 观察（120 scorer、600 student、20 C 附加）。本地只读取导出的逐组 JSON，以五 seed 组内均值再组间均值独立复算全部 12 个架构/方法的学习率和步数选择，以及 C 在固定计算格的权重选择，均与记录相同；未重新运行 bootstrap 或服务器模型。budget 与 refit 所嵌预算报告完全相同。
- 选定 `(lr,steps,weight)`：Set Transformer 的 A=`(.0006,3000,1)`、B=`(.0002,10000,1)`、C=`(.0002,3000,10)`、D=`(.0006,3000,1)`、E=`(.002,3000,1)`、scorer=`(.0006,1000,1)`；MLP 的 A=`(.002,3000,1)`、B=`(.0006,10000,1)`、C=`(.0006,10000,10)`、D=`(.0002,10000,1)`、E=`(.002,3000,1)`、scorer=`(.002,10000,1)`。按原规则接受 10000 触顶，不扩搜索网格，不按结果择优架构。
- refit 两架构×六角色×五 seed=60，模型条目无缺失/重复；逐项核对 full-train 1000 组、mode=refit、学习率/步数/权重与已选设置一致。所有 refit checkpoint 的 inner_dev=null、inner_dev_independent=false，未将全 train 重训后的内部成绩冒充独立泛化指标。本地未持有服务器权重，权重实际文件核验依赖服务器 exporter 所记录的完成证据；此次不是重新执行训练。
- 科学结论边界：本轮支持工程链路、预算选择及模型产物完整，不等于 S5 独立确认或 M1 go。下一阶段需绑定当前登记和权重的新 S5 confirmation 入口，旧 v6 验证入口不能直接复用；test 未解封，N=1350 与既有门保持。未为本次结果另设科学 decision。


## LOG-089（2026-09-10）：D-055 S5 独立确认整阶段入口实现

- 新增冻结计划、只读模型/来源消费者、S5 正式 runner 及 ops 命名子命令。现有 `4c89e59` 的 src/scripts/configs 文件逐一比较保持不变；新阶段消费 LOG-088 三个精确导出 hash 和修正组合登记，不能将旧 full-test marker 当作新版本测试。读取本地实际导出确认计划/60 模型矩阵绑定通过；test N 仍为 1350。
- 同一交付含 test、prepare、smoke、generate、export-data、evaluate、status、summarize、export-confirmation。阶段按 marker/source/runtime/manifest/digest 依赖守门，运行不训练任何模型；唯一固定 validation 范围 4–203，50 个学生模型及两个共享 oracle、配对统计与逐例审计接线完成。准备阶段核验并加载全部 60 模型，固定 train 第 1 组的小预演只补新的写入/oracle/正式权重消费。原 probe/预算/refit 不重跑。
- 继续使用已验收的可重复磁盘审计读取器和四 worker paired-group 评测。父级原子完成目录与执行分片目录分开，避免完成时 rename 使记录的 shard 路径失效；串行前向重放在关闭池后独立测量，完整轨迹及失败原地保留。生成并发按 cgroup CPU/内存限额最多 16；小预演实际磁盘占用外推正式审计存储并加 25% 余量，生成前检查可用空间。该外推仅规划，不保证后续峰值。
- 新固定全局数据 reservation 防止换 source-derived 目录重开验证；实际模型读 validation 前写独立消费回执。忙锁明确返回非零并说明请求未执行，后台 launch 明示 completed=false；成功、失败、中断分开记录，任何异常都不自动重训、换样本或改门。单步诊断复用原实现，bootstrap/安全/Holm 复用原公共统计；导出压缩职责，只保存本阶段报告、逐组指标和来源指纹，不再次嵌套全部预算/refit 巨大 JSON。
- 本地 11 项新轻量测试和 6 项运维测试通过（共 17 项）：固定范围/禁 test/禁选参、旧算法桥接、实际 60 模型导出矩阵、新分片写读/篡改拒绝、可重复 oracle 输入/F 失败保留、当前 policy 覆盖旧 payload、健康门失败、消费早于验证读取、原子 rename 后 shard 路径与复用、完整两架构五方法五 seed 汇总接线、全局 reservation 和禁止中断重试。只用本地导出、微型 arrays 与模拟模型/统计，未运行真实模型训练、生成或 self-rollout。服务器新版全测、train 小预演、validation 生成/评测均 pending。
- 实现本阶段不等于 S5 已通过；最终结果仍按既有 stop rule 复核，不自动开启 S6。完整方法、统计效应门、安全门、固定 exact 与 N 未修改；方法和流程边界见 D-055，命令顺序只在 M1_V2_CLOSEOUT_FLOW 维护。


## LOG-090（2026-09-10）：S5 独立确认复核，工程完整但触发科学 no-go

- 拉取结果提交 `ea6859e`。`results/m1_v7_d055_s5_data.json` SHA-256=`a4ef7d0395f8527b2002704ba047fcd6d318ec5b22073728c7f60ae41da0ab6e`；`results/m1_v7_d055_s5_confirmation.json` SHA-256=`fa6426a96d0a1e8ca4cd7bb409ba9e6bbebf852d322a50cd47c6ea023e917e67`。同时导入的 `m1_v7_d054_training_process_check.json` 文件 hash 与旧 refit 的 input_exports 绑定一致。
- 369 项 full test，errors/failures/skipped=0；prepare/smoke/generate/evaluate/summarize 均 exit=0，实耗分别 12.884/88.342/209.606/14339.792/72.202 秒；评测约 3 小时 58 分 59 秒。两份导出 engineering_pass=true、failure_units/failures 为空，data 是模型评测前快照（trial=false），confirmation 保留消费回执（trial=true）；两者不矛盾。
- 换机核验：所有 S5 binding/runtime 同为 `autodl-container-2xu0qgs8j6-08076b4e`，Python 3.12.3、NumPy 2.3.2、Torch 2.8.0+cu128、CPU/单线程；新机器在 prepare 重新加载同一 refit 权重。逐模型 model_sha256 与旧 60 模型导出对应项一致，NumPy/Torch 版本与训练记录一致；这不等于不同机器逐决策重执行等价验证。S5 源码指纹 `bea8616e86b697733e7b331f4b11c1bd77f6d681de91e0244b4fcdcf89b0611a` 独立从 `4d4b65b` 的 Git 文件及 Linux 行尾规则复算一致，ops/shell 字节 hash 匹配。summarize 的 git_dirty 仅来自两个允许的未跟踪 results 导出，科学源码 diff 为空，不作为混用代码的证据。
- 完整性：validation 编号恰为 4–203，400 sibling sequences；50 个 `(architecture,method,seed)` 无缺失/重复，每模型 400 条指标、200 执行分片、8000 次独立前向重放，共 400000 learned decisions，两个共享 oracle 各 400 条。所有阶段 binding/full-test/source 一致；两个 report 用原 write_json 序列化独立复算 raw report_sha256，data manifest 与消费回执绑定一致。生成参考轨迹 candidate coverage 和解析 teacher/reference agreement 均为 1，各 family 健康门通过，invariant=0；F exact/support=1、burden/node error=0。这里的 coverage/teacher=1 只针对参考轨迹，不证明模型错误分支的候选或教师永远正确。
- 主架构 Set Transformer 五 seed 平均 `(final exact, open-memory support, open-fact burden)`：A CTL=`(0.9205,0.933069,8.915)`；B direct classifier=`(0.7820,0.920135,14.645)`；C direct future loss=`(0.8980,0.931158,9.605)`；D execute current only=`(0.5745,0.903168,28.300)`；E future scorer without execution=`(0.5200,0.891306,17.320)`。burden 越低越好，语义为整个连续过程的开放事实错误累积并按每 100 次决策计，不是错误百分比。
- 主架构 A−C：exact 改善 `+0.0225`，95% CI `[0.0050,0.0405]`；support 改善 `+0.001911334`，CI `[0.000382941,0.003559497]`；burden reduction `+0.690`，CI `[-0.705,2.045]`。要求分别为 CI 下界至少 `0.03/0.03/40`，三项均不满足；support 与 burden 的上界也远低于各自门，符合明确 no-go，非仅样本少而未显著。相对 E 的 exact/support 改善 `+0.4005/+0.041763878`，各自 CI 下界 `0.3570/0.037297688` 超过 0.03；burden reduction `8.405 [5.240,11.840]` 仍不足 40。两主对比交并/Holm p 均为 1，原因是所有 co-primary 必须同时满足，不能据其否认单项有改善。
- MLP 五 seed 平均 A/C/E：exact=`0.7885/0.7825/0.4525`，support=`0.921008/0.919304/0.884286`，burden=`16.210/11.385/26.780`。A−C exact `+0.0060 [-0.0270,0.0395]`，support `+0.001703860 [-0.001464057,0.004811680]`；burden reduction 为 `-4.825 [-7.480,-2.500]`，即 A 在整个过程累计更多错误，不是只因严格门未过。A−E burden reduction `10.570 [6.385,14.990125]` 也远低于 40。两架构、两主对照的 false-birth/collateral/active-node 三项安全非劣 CI 均通过原门；当前瓶颈为效果而非这三项安全门。
- 本地独立按 200 paired groups、每组两 sibling/五 seed 构造差值，固定 RNG=260906、10000 次重采样，用向量化实现复算两架构×两对照×六效应/安全量的均值与 95% CI，共 24 组，与导出相符（误差容限 1e-12）；基于报告交并 p 复算 Holm 一致。只读已导出指标，未重跑真实模型、生成、执行轨迹或测试集。统计 CI 对配对场景重采样，不能解释成已覆盖任意新训练 seed 的不确定性。
- 泛化诊断：同口径 reference-history 单步 accuracy，主架构 A 全 train=`94.4426%`、validation=`94.3289%`，差 `0.1137` 个百分点；C=`94.4542%→94.2395%`，差 `0.2147` 点。MLP A=`93.9247%→93.5737%`，差 `0.3510` 点。没有明显整体单步 train/validation 崩塌证据，但这不能排除连续错误积累和初始化不稳，也不能把单步分数与终点 exact 直接相减称为泛化差。E 训练时 learned scorer teacher 的参考准确率约 84%，S5 teacher_forced 中 teacher_error=0 是解析 pstar/reference 的诊断，不能据此声称 E 的 learned teacher 完美。
- Seed 稳定性：主架构 A−C exact 在 seed 7/19/31/43/59 的差分别 `+0.1200/+0.0425/-0.0225/-0.0050/-0.0225`，只有 2/5 为正；不得删除任何 seed。MLP A exact 为 `0.55/0.87/0.7925/0.8775/0.8525`，seed 7 明显偏低；MLP E seed 7 exact=0.0425，单步均分无法刻画这种连续失稳。主架构 probe A exact≈0.920398 与 S5≈0.9205 数值接近，而 C≈0.748756→0.8980；两次数据、预算和全 train refit 都不同，只能描述强对照在完整流程中追近，不能归因于某一个超参数。
- 尺度诊断：在这批固定 S5 上，C 平均 burden 仅主架构 9.605、MLP 11.385，而该指标非负，因此即便 A 的 burden 降到 0，样本平均改善也达不到 40。说明既定要求高于当前强对照剩余可改善空间；此迹象在固定 probe 已存在，应明确披露规划局限，不能事后把 40 降低让本次结果过门。即使暂不考虑该门，主架构 A−C support 增益仍小、seed 不一致，MLP 全程负担还更差，因此不能把未通过完全解释为门槛设置问题。
- 错误分解（探索性描述）：主架构 extra-open-fact burden 中 A/C 的新错误写入=`2.160/1.215`，旧错误滞留=`2.2975/3.5875`，A 在两类错误之间存在方向相反的差异；这两项只分解 extra 部分，不是总 burden。MLP 新写入=`2.330/0.335`、滞留=`5.725/5.3575`，A 两项更高。需要已有执行轨迹才能定位具体动作和恢复时间，当前汇总不足以断言某种事务必然是原因。
- 处置：按已登记 S5 stop rule，当前协议以 S5 科学 no-go 进入分析收口，S6 不放行、test 仍封存，不用更大模型/PNO/M2 或改门救结果。这不是 S6 test 的负结果。当前可报告“相对无执行评分器有明显描述性优势，但未建立相对充分调参 direct future loss 的登记幅度增益及跨 seed 稳定性”；不宣称 CTL 无任何作用，也不宣称主张已得到验证。下一步如需定位，可只读已保存轨迹作明示的事后失败分析，不重训或改本次确认规则。


## LOG-091（2026-09-10）：S5 事后案例分析打样，同组跨 seed 的胜负反转

- 本轮只读 LOG-090 已核验的 `results/m1_v7_d055_s5_confirmation.json` 逐序列指标，不重训、不重新运行 validation、不访问 test。此为事后探索性解释，不修改正式统计、门槛或 no-go。分析单位保持同架构、同 seed、同 paired group 的两条 sibling，不把选中的极端案例当作总体效应。
- 选例规则：在主架构 Set Transformer 的 1000 个 `(seed, paired_group)` 单位内，对两条 sibling 求平均，按 C−A 的 open-fact burden 从大到小排序，同分按 seed、group 升序；取首例 seed 7、validation group 69，再完整查看同组五个登记 seed。它是优势极端案例之一，不是预先指定或随机代表案例。
- A 为 CTL 完整方法，C 为 direct future loss。组 69 的 `(A final exact, C final exact, A burden, C burden)`：seed 7=`(1,0,5,205)`；19=`(0,1,205,5)`；31/43/59 均为 `(1,1,5,5)`。该组跨五 seed 的 A/C exact 均为 0.8、burden 均为 45。只展示 seed 7 会掩盖 seed 19 的反向结果。
- Seed 7：A 的 sibling 0 全部 20 个决策后活动世界都正确，burden=0；sibling 1 首错 step_index=2（第 3 次决策），一决策后恢复，19/20 个决策后世界正确，burden=10。C 两条 sibling 均在 step_index=0 后出现错误，20 个决策后活动世界均未完全正确，终点错误，burden 分别 210/200。Seed 19 的结果方向反转：A 两条全程未完全正确、burden=200/210；C 一条短暂错误后恢复、另一条全程正确、burden=10/0。
- 指标白话：这里 burden 汇总每个决策后的额外和缺失开放事实，再按每 100 次决策计；输入是 20 步的事实差异，输出是过程累计负担，例如 burden=200 对应本条 20 步内 40 个错误事实×决策步暴露，不是 200% 的序列失败率。失败序列的 registered_selection_accuracy 仍可达 0.8–0.9；它衡量登记候选索引匹配，不等于已经分叉的世界恢复正确。首次错误索引从 0 起算；recovery_eligible 只表示出现错误，不证明修复候选存在。
- 已知现象是同场景跨训练 seed 的方法胜负反转，以及部分运行早期出错后世界始终未完全恢复。尚不能断言某个 BIND/MERGE 等事务导致失败、同一条错误事实持续全部 20 步、或 CTL 本身缺少恢复能力。须从原服务器已保存的 execution.jsonl.gz 对齐 group 69、seed 7/19、A/C 的 8 条完整序列，检查首错候选、模型概率、实际提交及后续修复候选；优先区分 candidate miss、可用候选上的模型选择错误和执行状态问题。教师排序若未被原轨迹记录，不能凭 reference-history teacher=1 补推错误分支教师正确。
- 本轮未读取服务器原始逐步轨迹，因此上述机制归因仍待证据；不启动新实验，不改变 LOG-090 的科学处置。
- 为上述只读提取交付 `ops/export_m1_s5_case.py`：锁定原 S5 导出 SHA，从报告查找四个真实 shard 路径，核验完整文件哈希、逐例指标、八条 20 步轨迹、状态链及共同参考审计；原始 result/execution/reference 文件无损 gzip+base64 封装到 `results/m1_v7_d055_s5_case_group69.json`。只读既有产物，不导入模型或 executor；失败不重跑、不覆盖已有不同导出。3 项微型磁盘测试通过，覆盖完整提取和字节还原、复用/拒绝覆盖、篡改/配对不符、缺失决策拒绝；服务器真实提取尚待执行。


## LOG-092（2026-09-10）：group 69 完整轨迹分析，首步身份误修与后续候选恢复边界

- 消费服务器案例导出 `results/m1_v7_d055_s5_case_group69.json`（提交 `637fe7e`），核验 gzip/base64 解码后的原始文件 SHA、四个完成标记、参考审计、来源 S5 报告及 8 条/160 步完整矩阵。本地只对已有图和候选结果作比较，不加载模型、不调用 generator/executor、不访问 test、不搜索未发生的替代多步分支。`ops/analyze_m1_s5_case.py` 生成 `results/m1_v7_d055_s5_case_group69_analysis.json`；只保存本次派生差异及来源 hash，不重复嵌入原始轨迹或上游报告。
- 全部 2560 个候选槽位按原 active-world 语义比较；逐步正确标记和候选 exact reachability 与原轨迹相符，8 条序列的 open-fact burden 与原指标逐一一致。每条 sibling 的首次 online 输入在四个模型之间完全相同，不能把首步胜负归于输入/候选不同。
- 第一次决策是 C06：原参考要求 REPLACE，当前实现是撤回旧位置关系并创建新实体及其位置关系（不是物理删除旧节点）。具体原关系为 `entity:replace-old -> place:1`，参考将其关闭并建立 `candidate:...event:03:current:replace -> place:4`；错误 RELINK 则建立 `entity:replace-old -> place:4`。两个程序均合法且可选，REPLACE 是唯一能当步达到参考 active-world exact 的候选（index 5）；错误 RELINK 为 index 4。
- 首步 `(P(REPLACE), P(错误 RELINK))`：A seed 7=`(0.8303743005,0.1499751955)`；C seed 7=`(0.0234276634,0.9734008312)`；A seed 19=`(0.3620305657,0.5962856412)`；C seed 19=`(0.9914267063,0.0083800228)`。两条 sibling 的首步概率相同。它们是模型输出概率，不是已经校准的正确概率；不能据四个点宣布校准优劣。
- 首步参考解析 teacher 正确选 index 5，posterior=0.9554073851，对 index 4 为 0.0031752211。由于此刻实际 base 与参考 base 相同，首步可排除“正确候选不存在”和“该参考 teacher 排错”作为失败原因；A seed 19 是学生选择/监督摊销误差，C seed 7 是在线选择错误。不能据此进一步断言训练优化还是表示能力导致，也不把这份参考 teacher 当成 C 自身的损失目标或 E 的 learned teacher。
- 四条首步失败序列（C seed 7 两条、A seed 19 两条）均保留上述同一额外位置事实、缺失同一正确位置事实到第 20 步，新 replacement 节点也一直缺失。从第 2 至第 20 次决策，在实际到达的 base 上，全部可选合法候选均无法恢复完整参考活动世界，且无一个候选能创建原参考要求的 replacement 节点，共 76/76 个后续决策。源码的 birth/replace ID 由当前事件 evidence ref 构造，见 `m1_rollout.py` `_proposal_context`；该首事件节点错过后，后续实际候选没有补建它的入口。这是实际路径上的一步恢复边界，不证明所有未探索多步路径都不可能恢复，也不涉及真实视觉物体的身份等价放宽。
- 不能概括为“后续没有任何修正候选”：第 6 次决策存在 RETRACT（index 3）可移除原错位置边，和 RELINK（index 5）可改变该边；二者仍不能补齐缺失的新实体/正确关系，而且该步参考任务为 BIRTH，选它们会漏掉当步新节点。它们不是完整修复机会，不能只以 edge burden 较小就宣布更好策略；本轮不按事后指标重新选动作。
- 另一类错误确实得到修复：登记歧义 pivot 为 step_index=2（第 3 次），紧接着 step_index=3 提供可见的 mover 位置回访。A seed 7 sibling 1 错把 mover 从 place:4 移到 place:0，下一步以 RELINK 移回 place:4，选择概率 0.964517653；C seed 19 sibling 0 在该移动时选 NOOP，下一步以 RELINK 补移，概率 0.999371350。C seed 7 sibling 0、A seed 19 sibling 1 也修好了这一 mover 错误，只是首步 C06 错误仍在，因此全图 exact 仍为 0。故不能从全图未恢复推出模型对后续位置错误完全没有纠错能力。
- 负担的逐事实分解：四条首步失败序列各有同一 extra+missing 两个位置事实跨 20 步持续，对各条 burden 贡献 200；四条总 burden=820，其中 800（97.56%）来自这一首步遗留，余下 20 来自两条各一次的短暂 mover 错误。这是对已发生轨迹的加法分解，不是重跑干预后的因果效应。成功的两模型各为 burden 0/10，方向依 sibling 而异。final active exact 不等于证据支持也全部正确，不混同 support 指标。
- 解释修正：LOG-091 的 seed 反转成立，但“未恢复”的原因现在细分为首步可避免的模型误选 + 后续实际候选缺少完整身份修复选项；专门设计的 C08 位置回访恢复在 A/C 上均可成功。该例不支持 CTL 独有恢复优势，也不能推广为全部 M1 错误不可恢复。参考轨迹 coverage=1 不等于错误分支 recovery coverage=1；当前证据未显示非法事务被错误提交或 executor 执行偏离所选程序。既有 S5 no-go 不因本案例而改判，未修改候选、指标、门槛或训练预算。

## LOG-093（2026-09-10）：全体 S5 恢复分层，已登记局部恢复接近满分

- 只读固定 results/m1_v7_d055_s5_confirmation.json（SHA-256=fa6426a96d0a1e8ca4cd7bb409ba9e6bbebf852d322a50cd47c6ea023e917e67），新增 ops/analyze_m1_s5_recovery.py 及派生 results/m1_v7_d055_s5_recovery_analysis.json。覆盖两架构、A–E、五 seed、全部 200 paired groups、每组两 sibling，共 50 模型、20000 条序列指标；不是 20000 个独立场景，也未重读全部 400000 步执行记录。未训练、未执行候选/模型、未访问 test。
- 口径：已登记有界错误要求 pivot 后实际 world hash 命中预先覆盖的另一参考 pivot 世界；恢复要求其可见重访触发且随后全图正确。它是窄范围的既有指标，不能把范围外错误等同于没有修复候选。完整中文字段释义在 HARD_CONDITION_EXPERIMENT 的“S5 事后恢复分层”；原指标、分母、门槛及停止结论均未改动。这里报告方法各自进入该范围后的条件频数，不作不同错误子集之间的因果比较。
- 主架构 Set Transformer 的已登记恢复成功/范围内错误：A=668/668，B=622/624，C=659/659，D=561/563，E=525/525；MLP：A=639/640，B=625/625，C=633/633，D=475/475，E=500/501。全部为 5907/5913，仅 6 次未恢复。A 是 CTL，C 是 direct future loss，E 是 future scorer without execution；三者在主架构各 seed 上该范围内均无恢复失败。此项在当前数据上接近满分，未提供 CTL 独有恢复优势的区分证据；不等于所有类型错误都可恢复。
- 每架构/方法共 2000 条序列。主架构 A/C：曾全图出错=1079/1103，首次出错后曾恢复=969/952，首次出错后始终未恢复=110/151；曾恢复但终点再次出错=49/53，故终点错误=159/204。首个决策即错=65/69。终点错误与从未恢复必须分开；已有局部修复仍可能被另一遗留错误遮蔽，见 LOG-092。
- 主架构 A−C 的平均全过程负担差为 -0.690（负值表示 A 较少）；按整条序列是否曾恢复分层后，始终未恢复序列贡献差=-0.930，曾恢复序列贡献差=+0.240，两者相加回到原结果。该划分描述方法各自轨迹，不是将两者差异因果归于恢复能力；也不是逐错误事实追踪。
- MLP A/C：首次出错后始终未恢复=287/293，但这类序列负担总和=18820/9430；除以各自完整 2000 条分母，对总均值差贡献 +4.695。曾恢复类贡献 +0.130，合计 A−C=+4.825，与 LOG-090 一致。因此未恢复条数略少仍可伴随更重的错误负担，不能只报恢复次数或终点正确率。
- group 69 的首步长期身份错误不能直接推广到全体：主架构 A/C 首步即错序列承载的完整负担总和仅 2520/2970，占各自总负担约 14.13%/15.46%；MLP 为 1970/1910、约 6.08%/8.39%。这些是整条序列承载的负担，包含后续新错误，不是首步错误本身的贡献；大量其余负担需要另作逐步定位。
- 来源矩阵、二值标志、首错/三步恢复时序、pivot 范围划分、触发/成功嵌套与终点恢复恒等式全部核验。报告生成及相同字节复用成功；另用原 extra/missing 均值独立复算十个方法臂的 burden，并从原终点字段复核错误数，20000 条交叉检查通过。脚本只用标准库，没有运行本机训练或全套测试；输出保留每模型及每 paired-group/seed 分层，未挑 seed 或组。
- 当前证据边界：confirmation 导出没有逐步 choice.candidate_availability，因此本次不能统计全体“有正确候选却选错”“错误后无完整修复候选”“有修复候选却失败”的决策数，也不能补推分叉世界的 teacher 排名。原服务器逐步记录仍存在，不能将未导出字段说成未保存产物。若继续该归因，应从已完成分片只读导出所需字段并校验 marker/hash，无须重训或重评测。现有 S5 no-go 不改判，S6 仍不放行。


## LOG-094（2026-09-10）：全体 400000 步可达性复核，主架构 A/C 的持续错误与完整候选缺失

- 已拉取服务器提交 ed66a16 的 results/m1_v7_d055_s5_availability.json，原始字节 SHA-256=4fa2d663e6f84d5b3b5913fd2921f384d73cd92388f997c24dae4ae3c87a28d3。固定 confirmation SHA、导出器/测试代码绑定、50 模型、10000 分片来源、200 paired groups、20000 条序列和 400000 步完整矩阵全部匹配；逐模型 payload 哈希、时间轴指标与八格汇总复算一致，导出前置测试回执为 9 项通过。可达性是原评测保存的 choice 诊断，本地没有重新读取服务器原 candidate/execution 世界，也没有重新训练或评测。
- 本地运维异常保留：首次直接运行 export_m1_s5_availability.py verify 返回 exit=1、stdout/stderr 均空，原因未确定。随后显式分阶段读取并检查源报告哈希、解析导出、核对 code_binding，再调用同一 verify_export 函数，完整返回 50/10000/20000/400000/200 并以 exit=0 结束。没有改代码、覆盖报告或重跑服务器计算；不把第一次无输出退出说成已成功。
- 统计单位与语义：每架构/方法 2000 条序列、40000 个决策。prior_wrong 表示上一决策后世界相对上一时刻参考已经错误；reachable 表示本步实际候选集中有可选且合法的完整正确世界；correct 表示实际提交后对本步参考正确。这是实际路径上的一步可达性，不证明多步绝对不可修复，也不保证恢复全部由主动纠错而非参考目标变化造成。不能用本步 family 标签推断原错误发生在哪个 family。
- 主架构 Set Transformer 的 A/C 四类关键计数：上一刻正确且有正确候选、本步转错=1128/1156；上一刻已错、本步有完整正确候选且恢复=969/952；上一刻已错、有完整候选但仍错=0/0；上一刻已错、本步无完整正确候选且仍错=1398/1889。其余是始终正确的 36505/36003 步；两者所有“上一刻正确但本步不可达”及“不可达却正确”的格子均为 0。五个 seed 分别也没有 A/C 的“有完整候选却恢复失败”。
- 因此，主架构 A/C 的错误后完整候选可用比例分别为 969/2367=40.94%、952/2841=33.51%；其余 59.06%/66.49% 没有一步完整正确选项。在实际存在完整正确选项的错误后决策中，两者观察到的全图恢复率均为 100%。两方法访问的错误世界/机会分母不同，不能把可用比例差当作候选预算不公平或 CTL 因果恢复优势；也不能因后续不可达，抹掉此前“正确候选存在却转错”的选择事实。
- “正确候选存在”不等于在线证据足以判定正确：A/C 上述 1128/1156 次从正确转错中，969/952 次发生于 epistemically_ambiguous_pivot 的 C08；这是登记的信息不足位置歧义，不能全部称为可避免误判。按连续错误段起止追踪，主架构这些歧义段随后全部恢复；其余 159/204 段持续至终点，与原终点错误序列数一致。非该歧义的新错按当前 family 分别为 A/C：C02=20/14、C04=30/59、C05=40/53、C06=23/49、C08 sequence_context=46/29。标签分层仍不足以断言每个新错的教师、优化或具体事务原因。
- 对 LOG-093 的首次错误后始终未恢复序列补充分母：A 的 110 条中有 5 条、C 的 151 条中有 10 条直到最后一个决策才首次出错，没有任何后续决策，不能算给过恢复机会。余下 A=105 条共 1223 个后续决策、C=141 条共 1714 个后续决策，保存的完整正确候选可达数全部为 0。全体 prior_wrong 计数还包括首次恢复后再次出错等情况，不能将 1223/1714 与总计 1398/1889 混为同一分母。
- 其他方法并非没有真实的机会内失败：主架构 E 在 957 个错误后完整候选机会中恢复 763 次、失败 194 次（恢复率 79.73%），另有 10221 个错误后无完整选项的步骤。194 次均发生在当前 C03 步，实际选 SPLIT=168、MERGE=26；这只是保存标签和可达性，尚未重读该处候选世界或教师排名，不能从模板名称直接判定具体结构错误。B/D 分别有 2/7 次机会内未恢复。
- MLP A/C：有完整候选时恢复 924/927 与 922/922，分别 3/0 次失败；无完整候选且仍错为 3807/4314。A 的三个机会内失败均选择 REPLACE：seed 31、group 119、sibling 0、step_index 5；seed 7、group 119、sibling 1、step_index 5；seed 7、group 136、sibling 1、step_index 3（索引从 0 起）。这些是有界且来源明确的后续候选世界审计对象，不因此重训或更改候选。MLP E 另有 4 次机会内未恢复，B/D 为 0。
- 全部十个架构/方法臂合并：上一刻正确且本步正确=312429 步，正确转错=14790 步，错误后有完整候选且恢复=8561 步，错误后有完整候选但仍错=210 步，错误后无完整候选且仍错=64010 步，总和 400000。合并计数只是工程/描述核对，不作为不同模型/seed 的独立样本显著性检验。
- 结论范围：LOG-092 的“初始选择失误与后续候选修复边界必须分开”已在全体保存的步骤中得到更广的描述证据；主架构 A 相对 C 的收益不能解释成“同有完整修复机会时 A 更会恢复”。同时，主架构 E 和 MLP A/E 确实存在候选可达却未恢复的步骤，不能把所有未恢复一律甩给候选生成器。错误分支 teacher error 与 amortization error 仍未分开；全体保存可达性不是完整候选图重审，更不是所有替代多步路径的可达性证明。S5 no-go、原统计/效应门和 test 封存保持。
