# 实验记录与当前进度

本文件是 embodied_spatial_memory 的唯一实验/架构进度记录，复用原 EXECUTE.md，不再按新对话创建文件。当前看板可更新；只有实验结果、架构实质变化或需保留的失败 run 才追加历史 LOG，普通对话不逐轮记录；管理规则见 D-032。

## 当前看板

> **2026-09-06 更新（LOG-014）：** 固定 K=16 的 train/validation 开发阶梯已完成：400 个 train、160 个 validation 决策，未生成或读取 test。全标签 direct capacity 在可观察上限 97.5%（可辨识部分 100%）达到 97.5%，但 10% 标签下的 A=`CPMT-CTL Core` 在四个受控点只有 6.25%–9.38% teacher-forced accuracy、所有点 20-step final post-graph correctness 均为 0%。A 的 executed-hindsight teacher error 为 0，amortization error 为 90.63%–93.75%，所以目前失败点在“学生从在线输入摊销教师后验”，不是 candidate miss 或教师执行。A–E 的同参数量比较也尚未显示 CTL 优势；F=100% 只是将正确候选程序直接交给执行器的 oracle 上界。该 run 是一次非正式、单 seed、小规模开发诊断，不是 M1 gate，不能扩展到 M2、PNO 或 test。

最后更新：2026-09-06，LOG-015 修复 K=16 在线接口并把模板决策改为证据驱动，正式 M1 gate 未运行、未生成 test。

| 项目 | 当前事实 |
|---|---|
| 方向 | CPMT 具身空间记忆；CTL 是主学习假设，用户希望面向 ML 研究 |
| 已完成 | M0 合同；首轮 CTL 开发训练；单房间视觉接口；M1 v1 已冻结；C00–C11 paired generator/图指标；candidate=3 的 paired continuous rollout、A–F causal smoke 与可学习性阶梯；固定 K=16 生成器已把 audit-only reference 与 proposer 输入/排序解耦，并完成 4 个 validation groups、80 decisions 的开发 coverage 审计。历史全套 123 tests 通过；本轮 K=16 相关测试以隔离进程通过，未重跑全套 |
| 阶段 | M1 frozen-pretest implementation；只开放 train/validation，正式 gate 未运行，不是 M2/Full CPMT |
| 最近结果 | K=16 validation 开发审计 4 paired groups、80 decisions：coverage=100%、candidate miss=0、C00–C08 各 family=100%，`reference_arguments_independent=true`；这是受控匿名检索接口闭环，`formal_gate_eligible=false`。旧 trainability 中全标签学生达到 paired 可观测上限 97.5%/可辨识 100%，仍非正式优势结论 |
| 尚缺 | 先审查 K=16 小规模诊断中 A 的高 amortization error，确认在线特征、目标与优化不存在可复现实质缺口；不以扩表征/任务寻找正结果。之后才可能重建 C00–C11 的正式 train/validation、独立视觉 observation、多 seed/trials 与 10,000 次 paired bootstrap；正式 test 仍未生成；PNO 属 M2 |
| 数据/算力 | trainability 完整 run 仅 CPU，102.054 秒、约 75.0 MB；K=16 的 80-decision coverage audit 为 CPU 2.476 秒。既往 Windows `0xC0000005`、`0x3B` 和 SSD 链路 WHEA 继续作为运行风险如实保留，但不再作为项目开发优先级或普通验证前置条件；失败时保留记录并用独立进程重试。服务器未租、云预算 AUD 0 |
| 当前决定 | D-031：M1 A=`CPMT-CTL Core`；Full CPMT 只用于 M2 的 PNO＋world graph＋executor＋CTL；协议 hash 已冻结 |
| 人工待定 | 当前实现无立即阻塞项；正式 test 解封与任何云费用仍需单独事件/授权 |
| Git 备份 | candidate=3 稳定基线以 `fa9606c` 保留在 `origin/main`；K=16 开发工作单独保存在 `origin/wip/k16-candidate-generator`。outputs、数据、论文、虚拟环境等 ignore 内容不属于 Git 备份 |

白话：M1 的考试规则已经冻结。旧容量诊断证明简单 MLP 在给足标签时能拟合可见训练关系；新的 K=16 审计又证明候选接口可在不向生成器传入隐藏事务或目标 ID 的情况下找回受控 reference。后者仍只是 C00–C08、4 个 validation groups 的匿名固定特征检索，不是独立视觉数据、不是正式 coverage gate，也没有比较 CTL 与 MLP，因而不能宣布 CTL 胜出，更不是带 PNO 的 Full CPMT。

## 当前任务清单

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
- [ ] 在不进入 M2、不动 test 的前提下，先审查 K=16 小规模诊断中 A 的高 amortization error、确认在线特征/目标/优化是否存在可复现实质缺口；只有重建 M1 的正式 C00–C11 数据与多 seed 方案后，才可能运行正式 A–F、paired bootstrap 并申请 test 解封。

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
- Run/结果（10 train + 4 validation paired groups，全标签容量设置，单 seed）：索引 head train 97.5% / validation 12.5%；共享打分器 train 97.5% / **validation 90.0%**，参数 25,188。分解为 template 90.0%、argument-given-template 100%、identifiable 92.8%、ambiguous 37.5%（构造上限 50%）。随机基线 6.25%，可观测上限 97.5%，因此首次出现方法间可比较的空间。
- 验证/对照：把那 14 维证据特征清零，validation 从 90.0% 掉到 48.1%，确认是生成的证据在起作用而非新捷径。九个模板的证据签名两两不同，且各自对应设计语义（MERGE margin=0.018、REACTIVATE dormant=0.822、RETRACT visible_empty、NOOP 三分之一带 pose/depth 故障）。
- 失败/局限：全部为单 seed 且方差可见（消融中 “both zeroed” 61.3% 高于 “evidence zeroed” 48.1%，信息论上不可能，说明噪声有数个百分点），不能作方法结论。`evidence_novel` 由生成器随传感器报告声明，尚未由每节点视角覆盖算出，是本轮证据通道里派生程度最弱的一项。参数检索仍近乎 oracle：审计新增实测字段 `reference_argument_decided_by_query` 取代原先的布尔断言。测试方面初次为 10/11，`test_m1_rollout` 取不到干净整模块运行；机器降频稳定后复跑，立刻暴露出一条被硬件损坏掩盖的真实缺陷——审计已把 `reference_arguments_independent` 布尔换成实测的 `reference_argument_decided_by_query`，但测试仍断言旧键（`KeyError`）。修正断言后该模块 15/15 通过，全套 11/11 全部一次通过。
- 环境/硬件定位：本机三天内三次内核态蓝屏（`0x3B`×2、`0x1E`，均为 `0xc0000005`），同类堆损坏在 Windows CPython 与 WSL Linux 下均出现，14 天零 WHEA。内存为单条 Samsung DDR5-5600 SODIMM，跑在 JEDEC 标称频率与 1.1V，无 XMP 可关；Windows 内存诊断标准模式通过、扩展模式在第一项 21% 处挂死无结论。改用本仓库自身负载做量化探针（`tmp/stability_probe.py`，同 seed 须给出同一 digest，可捕获不崩溃的静默损坏）：Performance 模式 12 次中 10 次失败（83%），把 Armoury Crate 切到 Silent 后频率由约 3509MHz 降至约 3133MHz（−11%），16 次中仅 1 次失败（6%），Fisher 精确检验 p≈2e-5。**内存不会因 CPU 降频而好转，故定位为处理器封装侧而非该 DIMM**，与 i9-14900HX 所属 Intel 13/14 代 Vmin shift 退化一致；微码已是 `0x12B`（只阻止继续退化，不修复已退化硅），BIOS 为 G614JIR.320 (2024-10-24)。注意 Windows 电源计划的“最大处理器状态”在本机无效（实测限到 40% 频率不变），只有 Armoury Crate 能控频。后续所有实验一律在 Silent 模式下运行，6% 残余失败率意味着 digest 校验必须保留；**LOG-014 全部数值、以及本轮在切换前产生的数值，均须在 Silent 模式下复核。**
- 结论/下一步：LOG-014 的 6.25% 不能作为 CTL 的负面证据——当时的任务两半都是查表，接口也拿不到必要信息。修复后 90% 与 97.5% 上限之间才有可比空间。下一步是机器稳定后补齐 `test_m1_rollout`、重跑多 seed A–F；仍不开放 test、不进入 PNO/M2、不产生云费用。

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
