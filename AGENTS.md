# Project Instructions

## 当前方向（D-122，优先于下面各历史方向）

- 用户于 2026-09-13 根据导师意见，将第一篇优先级切回结构记忆修订；旧 S5 no-go 保留，不把原 A 对 C 的不足改写为成功。
- 当前 proposed 方法名为 Versioned Structural Memory Transactions（VSMT，版本化结构记忆事务）；处理节点、关系、证据、生命周期和结构扩充，不限定为对象生命周期。
- 保留 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE 八个原子模板；REPLACE 仍是 RETRACT+BIRTH 复合程序。事务单独出现不主张首次提出。
- 第一篇主比较改为：VSMT、可在同一公开输入/状态/输出接口上独立实现的论文机制适配器，以及一个朴素基线。旧 A/C/E 仅可在新合同内作为训练机制消融，不能继续承担唯一主张。
- 论文机制适配只参考公开论文的机制并明确引用、差异与非官方复现身份；不复制上游源码、类名、默认配置或文字。若以后运行官方代码，须作为独立复现路线登记许可证、commit、原设定与任务适配。
- 旧 `proposal_observation.node_query/edge_query/place_query/merge_queries` 存在由 `reference_spec` 参数派生的参考身份捷径风险，新数据和主实验禁止复用。所有部署 query 必须由公开当前观测和先前预测记忆在线计算。
- 候选集必须在 teacher、未来、reference transaction 和私有真值可见之前生成并封存；teacher 只可给既有候选打训练标签，不得插入、删除、排序或修补候选。正确候选缺失按 candidate miss 计入。
- 新数据必须重新生成，物理/视觉公开输入与私有监督分文件、分读取器；模拟器 instance ID、真值 mask、参考事务、未来观测及实际未来状态不得进入部署输入或候选生成。
- 当前只批准文献与旧实现审计、方法/数据/反作弊合同和独立分支；具体数据划分、生成预算、模型预算、确认集与效果运行仍须在用户代码审查前后分别冻结。
- D-059 的单职责科学提交、用户代码审查和服务器规则继续有效；旧代码、结果、原始资料、D-062 空间世界模型分支及复现路径保留。

## 上一方向（D-062，暂停但保留）

- 用户于 2026-09-11 明确授权从记忆修订转向空间世界模型，并开始执行；必要时可重构工作区，但保留旧代码、结果、原始资料和复现路径。
- 当前候选：近期观测相同而早期历史揭示的遮挡区结构不同时，能否预测同一机器人控制指令的不同视野外交互后果，并改善固定候选动作的选择。
- 先检验既有方法的可复现失败，不预设持久三维状态、动态预测或二者组合是创新，不预先绑定 CTL。
- 本轮允许固定候选控制序列的后果比较；不开展主动探索策略、开放世界、复杂操作、语言接口或高质量视频生成。
- 数据/模型主对照必须包含长历史预测器、历史检索和地图加简单动力学。只胜过没有足够信息的短历史模型，不足以支持新机制。
- 区分机器人控制指令、根据机器人运动学计算的计划运动、执行后实际运动、物体未来变换；后两项不得伪装成可部署的动作输入。
- 第一批是独立成对数据合同与输入边界，具体定义见 METHOD/DATA；手工夹具不是模拟器、物理正确性或模型失败的证据。
- D-059 的单职责科学提交、用户代码审查、服务器运行规则继续有效；本次开始授权不等于批准未审模块成为基线。新训练/测试划分、训练预算和机制仍须先具体登记。
- 新旧实验协议分别适用：旧 test 继续封存，旧 no-go 不改写；新模块不必实现旧事务操作/六项能量，也不能用旧测试回执认证新代码。

## 历史 CPMT 方向（仅用于旧代码和旧运行审计）

- 完整方法是 Counterfactual Projective Memory Transactions（CPMT）。
- 核心学习机制是 Counterfactual Transaction Learning（CTL）。
- 研究对象始终是 embodied spatial memory；首篇不泛化到第二任务领域。
- Projective Node Orbit 是固定/轻量表征基础；Versioned Deterministic Executor 是必要执行基础。
- 唯一主张是：post-edit executable hindsight supervision 能否学习比 direct future loss 更可靠的在线世界记忆修订。

## 历史 CPMT 首篇范围

允许：

- 固定 backbone、depth、pose 和 region proposals；
- NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE；
- REPLACE 作为 RETRACT+BIRTH 复合程序；
- deterministic QUARANTINE 作为低置信度 wrapper；
- M0–M3 的受控、具身和一个 external/现实验证。

禁止擅自加入：

- active disambiguation/action policy；
- 第二个非具身应用领域；
- learned candidate generator；
- 端到端 foundation backbone；
- 大规模导航或语言任务；
- 把 executor、KL loss 或 transaction labels 单独称为创新。

## 旧 CPMT 运行不可降级的硬条件

- 所有候选从同一 immutable base version 克隆并真实执行。
- 能量必须分别记录 now、future、edit、growth、collateral 和 illegal。
- hindsight posterior 由执行后世界形成；online inference 不得读取未来。
- direct+future-loss 与 future-scorer-without-execution 是强制主对照。
- SPLIT/MERGE/RETRACT 必须有可执行正例，但可作为组合压力测试而非三个平行研究方向。
- RETRACT 关闭版本，不物理删除 provenance。
- QUARANTINE 不修改 persistent world。

## 旧 CPMT 执行顺序（当前指针已由 D-062 替代）

1. M0：contracts、executor、oracle fixtures；
2. M1：hard-condition go/no-go；
3. M2：固定感知前端的 visual online/self-rollout；
4. M3：一个 external/现实来源、论文与 artifact。

M1 失败时停止扩模型，不通过增加表征或任务寻找正结果。

2026-09-11 用户明确转向的例外见 docs/DECISIONS.md D-058：保留 M1 no-go 与 test 封存，允许独立开展 M2 公开观测接入；不把接入或新阶段结果当作旧 M1 通过。具体训练仍须先固定新阶段的方法、数据与预算，不授权按结果扩模型。

D-059 进一步授权先审真实数据，再彻底重构新协议 M1；完整计划及当前指针仅维护在 docs/PLAN.md。用户明确要求把关代码：科学改动按单一职责交付可读提交、输入输出例子和必要服务器测试，用户审过后才合并为新科学基线或运行依赖的效果实验，不在未审模块上堆叠后续科学代码。旧 M1 负结果及产物保留；当前计划交付不等于后续科学合同/预算自动冻结。

## 旧 CPMT 实现与实验

- candidates、executor、projection、hindsight、online 必须可替换并分别记录误差。
- executor 无梯度、deterministic、versioned，检查 precondition、protected state、invariant、provenance、idempotency 和 atomic rollback。
- 正式 run 保存 config、seed、data/code hash、front-end IDs、future-use policy、逐候选能量、逐例指标和完整失败。
- paired group 不跨 split；不用 test 调阈值、选 prompt、筛方法或选 checkpoint。
- 结果必须区分 candidate miss、teacher error 和 amortization error。

## 服务器终端命令交付规则（跨对话强制）

- 默认“一阶段一次交付、同步一次、按步骤运行”。阶段的方法与输入契约确定后，提前准备所需测试、生成、检查、训练、评估、验收和导出入口，完成适当检查并 commit/push；用户阶段开始时同步一次，之后运行已有命令，不为切换步骤反复改脚本或要求 pull。一个阶段是已确定的一组有序工作，不要求提前实现整个 M1 或未确定的下一里程碑。
- 不再强制 `ops/run_next_server_step.sh` 为唯一入口，也不再限制每个版本只能包含一个功能步骤。允许稳定的 `ops/<stage>/` 下按功能命名的多个脚本，或阶段脚本的命名子命令；简单任务可直接调用正式 runner，不为形式增加 wrapper。既有入口保留兼容和历史用途，不强制迁移或重启正在运行的任务。
- 可以提前写好后续步骤，但不能执行尚未满足条件的步骤。每步明确步骤 ID、输入前提、读写边界、续跑策略、输出路径和成功标志，运行前自动核验依赖的 marker、manifest、digest 和登记。已冻结的机械规则可自动消费前步结果；新科学决定或尚未授权的 test 解封仍须暂停，不能用预写脚本绕过。
- 按顺序交付短命令和继续条件。环境/版本核对、测试、生成、检查、训练、评估、导出及 Git 收尾按功能分块，不粘贴脚本正文或从测试到 push 的超长命令。用户要求“一条条”时只发当前一步，后续仍使用已交付的同一版本，不为发下一条命令新增提交。
- 只有必须修复的 bug、科学代码/配置/合同变化或确需新增能力时，才更新版本并再次同步；运行中的 checkout 不 pull。运维脚本放 `ops/`，不复制实验算法；正式 runner、config 或合同变化仍按原有测试、decision 与重新冻结规则处理，不能冒用旧测试 marker。
- 已成功且有 manifest/digest/exit 证据的任务复用，不因重连、步骤切换或文档更新默认重跑。先核验产物，从最早缺失步骤继续；失败/中断保留现场，禁止静默重跑、覆盖或替换样本。每项计算完成并保存退出证据后才启动依赖步骤，不要求每次成功后再询问是否继续。
- 纯 Git 收尾直接给精确 `git add -- results/file.json ...`、`git commit -m ...`、`git push origin main` 三条命令；不为提交产物另改脚本、另建 handoff 或制造仅承载提交命令的提交。多个同批已验收报告逐一列出路径，不通配整个 `results/`。
- 前台/后台按预计耗时决定，不按任务类型套用：检查、测试、测速、数据生成、训练等预计不超过 30 分钟的任务默认前台运行，直接显示进度、结果和退出状态，可同时保存日志；只有预计超过 30 分钟的任务才默认后台运行。耗时未知时不自动套用后台模板；用户明确指定时遵从用户。不要让短任务必须靠另查日志或重复运行入口才能看到结果；本规则不要求中断或重启已经运行的后台任务。
- 不在用户的交互式父 shell 中设置 `set -e`；如功能块确需 fail-fast，只能放进 `bash -c` 子 shell，使失败返回当前终端而不是关闭窗口。每个重任务块应显示或保存退出状态，下一块写清继续条件。
- Shell 变量不得使用 Bash/系统特殊名称，例如 `GROUPS`、`SECONDS`、`RANDOM`、`PWD`、`HOME`；使用任务专名，例如 `TRAIN_GROUPS`、`SCORER_STEPS`、`CPMT_RUN_DIR`。生成命令前检查变量是否为预期值。
- 远端仓库路径和拼写不得根据提示符、网页文件树或本地目录猜测。首次连接或重建后，用 `pwd -P`、`find ... -name .git` 或 `git rev-parse --show-toplevel` 取得机器实际路径，并原样复用；本仓库远端名称中的 `Emboddied` 拼写不得擅自更正。
- `outputs/` 是服务器大产物且默认不进 Git；需要本地分析时，先用仓库 exporter 生成带 manifest/provenance 的 `results/*.json`，再按纯 Git 收尾例外直接给精确路径的 add/commit/push，用户本地 pull 后读取。不得把“没有 exported report”误说成“没有生成 arrays”。
- 删除、移动或重建服务器目录前，先只读解析并显示精确目标；未经用户明确要求不删除。用户已明确要求删除时也要避开通配符和猜测路径，并说明未提交的 `outputs` 是否会丢失。

白话：按阶段交付解决每一步都要改入口、提交、pull 的操作摩擦。输入是已确定的阶段协议、代码和产物依赖，输出是同步一次后可按顺序运行、核验和复用的固定命令。例如先检查，再选参，最后导出，后一步自动核验前一步成功。它不是忽略失败的一键流水线，也不改变实验方法、统计协议、test 封存或当前运行任务。

## 白话说明硬规则

- 每个新概念、方法、模块、损失项、指标和实验，在首次出现处必须附一段中文白话说明。
- 白话说明至少回答：解决什么问题、输入是什么、输出是什么、一个具体例子、它不等于什么。
- 公式后必须用一句不依赖公式的中文说明其作用；缩写首次出现必须同时给出全称和白话含义。
- schema/code 中使用英文标识，但对应 README 或合同必须给出中文解释。
- 若概念尚未实现或验证，白话说明也必须明确标记 proposed/planned，不得用叙述造成已经成立的印象。

## Codex 模型与思考深度建议

- 每次任务、职责批次或服务器步骤交付的最终回复，末尾单独写一行：`下一任务建议：<模型> / <思考深度> — <一句理由>`。按下一项工作的科学风险、语义不确定性和可验证程度选择，不按代码行数或任务名称机械决定；若没有确定的下一任务，明确写“暂无”。该建议只帮助用户切换模型，不表示下一阶段已经获得运行、训练、下载、确认或合并授权。
- GPT-6 Astra High 默认用于研究问题、输入/标签边界、对照公平性、失败归因、跨METHOD/DATA/PLAN的复杂科学开发与审查。代码很短但可能改变研究结论时仍用这一档。
- GPT-6 Astra Ultra 留给协议最终冻结、昂贵实验启动前审计、证据能否支持主张的关键复核，以及用户明确要求多条独立证据线或代理并行审查的任务；不把Ultra当作日常小修默认档。
- GPT-5.6 Sol High 用于按照已审规格实现边界清楚的模块、补必要测试、一般故障定位和服务器工程检查；一旦发现会改变数据、输入、标签、评分、阈值、划分或预算，停止自行修改并建议切回Astra High审议。
- GPT-5.6 Sol Medium 用于路径、日志、命令、Git收尾和已定位的低风险小修。Sol Ultra只在方案已经明确、任务确实可拆成多个独立实现/只读检查且用户允许并行时作为可选项，不为追求“更严谨”默认启用。
- 推荐使用当前Codex界面实际可选的精确模型名和思考深度；若所列档位不可用，说明可用的最近替代，不虚构已切换成功。科学审议与工程执行可分两轮：Astra High确定/审查语义，Sol High落实冻结规则，必要时再由Astra High核对实现没有改变科学含义。

## 文件职责与保护

- 日常入口仅 README；工作规则在本文件；完整计划、阶段和当前指针只在 docs/PLAN.md；方法和中文术语解释只在 docs/METHOD.md；数据来源/字段只在 docs/DATA.md。
- 实验结果、架构实质变化、需保留失败及主张证据只写 EXECUTE.md，顶部看板可更新。重要方法/预算/流程变化追加 docs/DECISIONS.md；普通讨论不逐轮创建 LOG 或 decision。
- 新对话先读 docs/PLAN.md 当前指针，再读 EXECUTE 看板和最新 LOG。不再创建单独 handoff、STATUS、TODO、周报、确认表或词典；用户需要独立对外交付时例外。
- D-060 按用户明确要求重组并删除重复文档；旧细分合同、确认表、模板和两套方案副本在 c24ced2 Git 历史可查，不重新建 archive 副本。仍存在的旧 M1 合同/结果快照及历史代码说明只代表当时版本，不覆盖新计划。
- docs/source/full_technical_vision.txt、prototype 原始图/PDF、notes.txt、论文 PDF 和原始资料不覆盖或删除；文献笔记保留。科学源码、schema、配置、fixtures、run 结果和服务器 outputs 的清理必须先检查复现依赖。
- 已完成运行按原 code/data/config hash 复用；新代码不能冒用旧回执。源码 hash 可能包含 src/scripts/tests 目录内 README，不能因整理文档而随意改这些字节。
- 新科学代码逐职责形成可审提交、具体输入输出和必要服务器测试，用户审过后再合并为新科学基线或运行依赖效果实验；测试通过不等于方法有效。
- 未实现内容标 planned；数据、权重和逐例机器结果按工程职责保存，不塞进 Markdown，也不为每个对话新增进度文件。
