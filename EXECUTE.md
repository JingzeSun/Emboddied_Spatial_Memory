# 实验记录与当前进度

本文件是 embodied_spatial_memory 的唯一实验/架构进度记录，复用原 EXECUTE.md，不再按新对话创建文件。当前看板可更新；只有实验结果、架构实质变化或需保留的失败 run 才追加历史 LOG，普通对话不逐轮记录；管理规则见 D-032。

## 当前看板

> **2026-09-07 更新（LOG-032）：** v5 40-group 的 scorer steps `{300,1000}` × seeds `{7,19,31,43,59}` 已在同一 arrays 上完成；以 8 个 paired inner-dev groups 为统计单位、每组先平均五 seed，1000−300 的 effect=`+0.026875`，95% CI=`[+0.008750,+0.045000]`，`p_nonpositive=0.000900`，故按预登记规则选择 1000 steps。两个 report 已通过 exporter 导入并提交 `results/`；不进入 S3、student、causal 或 test。

最后更新：2026-09-07，LOG-032 v5 S2 五 seed 预算选择与 report 导出；正式 M1 gate 未运行、未生成或读取 test。

| 项目 | 当前事实 |
|---|---|
| 方向 | CPMT 具身空间记忆；CTL 是主学习假设，用户希望面向 ML 研究 |
| 已完成 | M0 合同与 M1-v1 历史基线；程序化 paired 20-step 与固定 K=16；D-034 的 M1-v2 active/history 指标、局部恢复机会、结构化 E、共享 commit 校准、可观测 oracle 和分阶段 provenance；最小 train/validation 接线及 causal smoke 已通过 |
| 阶段 | M1-v2 `pretest_lock_candidate`；只开放 train/validation，尚未重新冻结，正式 gate 未运行，不是 M2/Full CPMT |
| 最近结果 | v5 S1 的 target/assembly 与 scorer 接线改善已由 LOG-031 记录；S2 五 seed 在 40 groups 上选择 1000 steps：300/1000 inner-dev teacher mean=`0.767500/0.794375`，总体 masked BCE mean=`0.086793/0.062483`，ranking-relevant BCE mean=`0.153600/0.102113`，reference margin mean=`0.379248/0.309308`。预算选择只依据 candidate-ranking accuracy 的预登记 CI，不把 BCE 或 margin 当选择量 |
| 尚缺 | 已将两个 S2 report 导入并提交 `results/`；下一步依据可比的 10→40 数据量证据决定是否进入 S3。test 仍封存，PNO 与 Khronos 式全局慢路径属 M2 |
| 数据/算力 | 用户提示本机 CPU 负载可能诱发内存损坏；本轮本机重任务到此停止。后续数据生成、训练、causal rollout 和全套测试优先在 AutoDL 上由干净 Git 提交运行，本地只读取导出的 output。云实例仍由用户手动启停和定时关机 |
| 当前决定 | D-034：M1-v2 只加入有界、证据触发的局部补偿，E 不执行候选评分分支；D-038：static preflight 是 A–E 共享 online mask，但不替代 executor illegal 或候选审计；全局 reconciliation、PNO 与 M2 顺序不变 |
| 人工待定 | 正式 test 解封仍需以后单独事件；当前不读取 test。scorer loss 不因本轮 BCE 下降自动修改；1000 steps 已按 ranking CI 选定，S3 是否需要仍待数据量交互判断 |
| Git 备份 | D-038 科学代码基线为 `72afa7d`；S2 report 已在提交 `ececefb` 导入 `results/`，服务器大产物仍位于 ignored `outputs/`。本轮起服务器操作只通过版本化的 `ops/run_next_server_step.sh` 交付，脚本所在提交仍须先 push、服务器再 pull |

白话：M1-v2 现在仍是“考前定卷”，不是已冻结或已通过。旧容量诊断证明简单 MLP 在给足标签时能拟合可见训练关系；新的 K=16 与恢复审计只证明候选、executor 和 active-world 评测路径可达。这些都不等于 CTL 已胜出，更不是带 PNO 的 Full CPMT。

## 当前任务清单

M1-v2 的阶段顺序、转向条件和成功/失败终点见 [M1-v2 收口执行流程](experiments/counterfactual_transaction_learning/M1_V2_CLOSEOUT_FLOW.md)。下表只保留任务完成状态，不再承担流程解释。

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
- [ ] 在不进入 M2、不动 test 的前提下，在 AutoDL 的干净提交上完成 M1-v2 全套测试与足量 train/validation 预演；根据 report 半区的 active、contamination、recovery 和 paired CI 决定是否重新冻结，再单独申请 test 解封。
- [x] **(1) 强化 E 的 outcome scorer 目标空间与监督覆盖。** E 已改为候选作用域的未来关系查询；训练覆盖全部 K=16 候选，目标只读实际 reference future，不执行候选，也不复用 executor 导出的 illegal/collateral。C 使用同一关系目标作 direct auxiliary。当前只验证接线，E 是否真正变强须由服务器足量 run 回答。
- [x] **(2) 校准 commit/quarantine 策略。** validation paired groups 已按固定 SHA-256 规则分成 calibration/report；预登记网格只在前者选择一组 A–E 共享阈值，后者只汇报。网格包含 K=16 未校准 softmax 可达到的低阈值，避免所有模型因烟测阈值不可达而机械地零提交。
- [ ] **(3) 如实计算 `now` 与 `collateral` 能量项并报告哪些项真正在变化。** 协议声明 6 项，实际只有 `future`/`edit`/`growth` 变化：`now` 因 `_program_header` 给每个候选都写入 `evidence_refs` 而恒为 0；`collateral`（权重 10.0，全场最大）硬编码为 0，且因 `_check_protected` 把任何触碰受保护 ID 的操作判为非法而与 illegal mask 结构性冗余。须让实现与声明一致，并记录该冗余，避免审稿人误以为有 6 个有效项。
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

- 类型/状态：M1-development、train/inner-dev、scorer-only 的五 seed 预算比较完成；服务器脚本 `ops/run_next_server_step.sh` 返回 `SERVER_STEP_OK`。结果仍在服务器 ignored `outputs/`，尚未通过 exporter 导入 `results/`，因此本条记录不构成 formal gate 或 CTL 结论。
- 数据/provenance：同一 v5 train arrays，digest=`f68205b58a6d4a97f92e3432b0d1d3515a5b226994e4030515b930d7b0`，40 paired groups、1,600 online + 80 recovery；训练提交 `d35434b410ebe473ae6400dedf9b6869c30b1cda`，protocol=`34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a`，dataset=`m1-paired-latent-worlds-v5-shared-static-preflight`。两点均 `validation_arrays_read=false`、`validation_trial_consumed=false`、`test_generated=false`、未训练 online student、未校准 gate、未跑 causal。
- 设置/主结果：40 groups，固定 scorer 配置，steps `{300,1000}`，seeds `{7,19,31,43,59}`。inner-dev candidate-ranking teacher mean 为 `0.767500`（300）与 `0.794375`（1000）；总体 masked BCE mean 为 `0.086793` 与 `0.062483`，ranking-relevant BCE mean 为 `0.153600` 与 `0.102113`，reference probability margin mean 为 `0.379248` 与 `0.309308`。这些 BCE/margin 是解释量，不是预算选择量。
- 统计选择：每个共同 paired inner-dev group 先对五 seed 求均值，再对 8 个 group 差值做固定 seed=`260906`、10,000 次单层 paired bootstrap。1000−300 effect=`+0.026875`，95% percentile CI=`[+0.008750,+0.045000]`，`p_nonpositive=0.000900`；因为 CI 下界大于 0，唯一预登记预算选择为 **1000 scorer steps**。
- 解释/边界：这支持“在当前 40-group train/inner-dev 诊断上，1000 比 300 的候选排序更好”，不支持 CTL 优越性、causal 泛化或正式 M1 通过。1000 的 margin 均值低于 300，说明 BCE/margin 与排序仍非同一选择量；不据此另立 loss decision。
- 结论/下一步：两个 S2 JSON 已由 exporter 导入 `results/` 并在提交 `ececefb` 中保存；下一步再判断 10→40 是否仍有明确数据量收益，决定是否进入 S3。不得读取 validation、生成 test 或运行 student/causal。

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
