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

## 实现与实验

- candidates、executor、projection、hindsight、online 必须可替换并分别记录误差。
- executor 无梯度、deterministic、versioned，检查 precondition、protected state、invariant、provenance、idempotency 和 atomic rollback。
- 正式 run 保存 config、seed、data/code hash、front-end IDs、future-use policy、逐候选能量、逐例指标和完整失败。
- paired group 不跨 split；不用 test 调阈值、选 prompt、筛方法或选 checkpoint。
- 结果必须区分 candidate miss、teacher error 和 amortization error。

## 服务器终端命令交付规则（跨对话强制）

- `ops/run_next_server_step.sh` 是唯一活动的服务器执行入口。凡下一阶段需要用户在服务器运行命令，Codex 必须先把该阶段写入这个脚本，完成本地静态检查后单独 commit/push；交付给用户时原则上只给“同步仓库”和 `bash ops/run_next_server_step.sh` 两个短功能块，不再在对话里粘贴脚本正文。只有首次安装该入口或脚本自身无法启动时，才临时给最小修复命令。
- 这个入口每个版本只承载一个当前功能阶段，并显式写出 `CPMT_SERVER_STEP_ID`、输入前提、只读/写入边界、已有产物的续跑策略和唯一成功标志。不得在同一版本中预埋尚未满足前置条件的训练、导出或 push；阶段完成后直接在下一提交中改写同一文件，历史由 Git 保存，不复制出 `next_step_v2.sh`、临时 handoff 或状态脚本。
- 入口固定放在 `ops/`，不放入 provenance 默认覆盖的 `src/`、`scripts/`、`configs/`，避免仅更新运维指令就改变科学源码哈希。它可以调用仓库正式 runner，但不得复制或改写实验算法；正式 runner、config 或合同变化仍按原有测试、decision 与重新冻结规则处理。
- 给用户的服务器命令按功能块拆分：环境/版本核对、测试、数据生成、训练、结果导出、Git 提交必须是不同代码块；不得把从测试到 push 的完整流水线塞进一个超长粘贴块。一个功能块内部可以合并同质、短小、可重试的操作，例如同一规模的多个 scorer 点或统一导出六份 JSON。
- 重任务各自落盘并返回终端后再进入下一块。已经成功且有 manifest/digest/exit 证据的测试、数据生成或训练不得因终端重连而默认重跑；先检查已有产物，再从最早缺失阶段续跑。
- 不在用户的交互式父 shell 中设置 `set -e`；如功能块确需 fail-fast，只能放进 `bash -c` 子 shell，使失败返回当前终端而不是关闭窗口。每个重任务块应显示或保存退出状态，下一块写清继续条件。
- Shell 变量不得使用 Bash/系统特殊名称，例如 `GROUPS`、`SECONDS`、`RANDOM`、`PWD`、`HOME`；使用任务专名，例如 `TRAIN_GROUPS`、`SCORER_STEPS`、`CPMT_RUN_DIR`。生成命令前检查变量是否为预期值。
- 远端仓库路径和拼写不得根据提示符、网页文件树或本地目录猜测。首次连接或重建后，用 `pwd -P`、`find ... -name .git` 或 `git rev-parse --show-toplevel` 取得机器实际路径，并原样复用；本仓库远端名称中的 `Emboddied` 拼写不得擅自更正。
- 用户要求“一条条”时，每个代码块只承担一个清晰目的；用户允许“按功能块合并”时，也只合并当前阶段，不把后续未满足前置条件的阶段一起执行。代码块前用一句话给出输入前提，块后说明唯一成功标志。
- `outputs/` 是服务器大产物且默认不进 Git；需要本地分析时，先用仓库 exporter 生成带 manifest/provenance 的 `results/*.json`，再单独 commit/push，用户本地 pull 后读取。不得把“没有 exported report”误说成“没有生成 arrays”。
- 删除、移动或重建服务器目录前，先只读解析并显示精确目标；未经用户明确要求不删除。用户已明确要求删除时也要避开通配符和猜测路径，并说明未提交的 `outputs` 是否会丢失。

白话：这些规则解决“一个长命令中间失败后窗口消失、路径猜错、昂贵步骤重复跑”和聊天复制时引号损坏的问题。输入是当前已确认的仓库版本与上一功能块产物，输出是 Git 中可审查、可单独验证和续跑的唯一脚本；例如 40-group arrays 已有 digest 时，脚本只验收或训练当前 scorer 点，不再从 unittest 开始。用户只需先同步仓库再运行固定入口。它不等于一键跑完整流水线、不等于实时状态文档，也不改变实验方法、统计协议或 test 封存。

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
