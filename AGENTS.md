# Project Instructions

## 唯一方向

- 完整方法是 Counterfactual Projective Memory Transactions（CPMT）。
- 核心学习机制是 Counterfactual Transaction Learning（CTL）。
- 研究对象始终是 embodied spatial memory；首篇不泛化到第二任务领域。
- Projective Node Orbit 是固定/轻量表征基础；Versioned Deterministic Executor 是必要执行基础。
- 唯一主张是：post-edit executable hindsight supervision 能否学习比 direct future loss 更可靠的在线世界记忆修订。

## 首篇范围

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

## 不可降级的硬条件

- 所有候选从同一 immutable base version 克隆并真实执行。
- 能量必须分别记录 now、future、edit、growth、collateral 和 illegal。
- hindsight posterior 由执行后世界形成；online inference 不得读取未来。
- direct+future-loss 与 future-scorer-without-execution 是强制主对照。
- SPLIT/MERGE/RETRACT 必须有可执行正例，但可作为组合压力测试而非三个平行研究方向。
- RETRACT 关闭版本，不物理删除 provenance。
- QUARANTINE 不修改 persistent world。

## 唯一执行顺序

1. M0：contracts、executor、oracle fixtures；
2. M1：hard-condition go/no-go；
3. M2：固定感知前端的 visual online/self-rollout；
4. M3：一个 external/现实来源、论文与 artifact。

M1 失败时停止扩模型，不通过增加表征或任务寻找正结果。

2026-09-11 用户明确转向的例外见 docs/DECISIONS.md D-058：保留 M1 no-go 与 test 封存，允许独立开展 M2 公开观测接入；不把接入或新阶段结果当作旧 M1 通过。具体训练仍须先固定新阶段的方法、数据与预算，不授权按结果扩模型。

## 实现与实验

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

## 文件保护与决策

- docs/source/full_technical_vision.txt、prototype 原始图/PDF、notes.txt 和论文 PDF 是 source artifacts，不覆盖、不删除。
- 历史 PPT/脚本只作 provenance；冲突时以 README、EXECUTE 和活动实验合同为准。
- 未实现内容只能标 planned；fixture/unit test 通过不等于方法有效。
- accepted 方法变化必须追加 docs/DECISIONS.md。
- 实验/架构结果只记在 EXECUTE.md：顶部当前看板可更新；只有产生实验结果、架构代码实质变化或需要保留的失败 run 时才追加历史 LOG。M1-v2 的阶段顺序、当前指针、转向和终止条件只维护在 experiments/counterfactual_transaction_learning/M1_V2_CLOSEOUT_FLOW.md，它不复制实验结果。新对话先读流程当前指针，再读 EXECUTE 看板与最新 LOG。
- 不按每个对话创建交接、STATUS、TODO、周报或结果 Markdown；M1_V2_CLOSEOUT_FLOW.md 是 D-035 明示批准的唯一阶段流程例外。不把同一进度复制到 README、人工确认首页或词典。
- README 是稳定介绍，NEW_CHAT_HANDOFF_PROMPT 是固定跳转，human_confirmation 是表单索引；它们不再维护实时状态。
- 普通讨论、状态问答和未形成结果的日常调试不要求追加 LOG，也不另建进度文件；若产生实验结果、架构变化或需保留的失败 run，只写 EXECUTE.md。实际改变重要方法、预算或流程才追加 DECISIONS，并按需修改对应合同；不要给每轮聊天分配 D 编号。
- 新代码、测试、机器 run 产物仍按工程需要保存；配置/权重/逐例指标不塞进 Markdown。只有新内容确实无法归入既有职责，或用户明确要求独立交付时才新建文档。
- 历史结果和旧周报保留为当时快照，不继续追写；不得把历史“下一步”覆盖当前看板。详细方法合同/文献仍按需阅读，非并行路线图。管理规则以 D-029 为准。
