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
- 日常进度只有 EXECUTE.md：顶部当前看板可更新，历史按工作/实验事件追加；新对话也读取并续写同一文件。
- 不按每个对话创建交接、STATUS、TODO、周报或结果 Markdown；不把同一进度复制到 README、人工确认首页或词典。
- README 是稳定介绍，NEW_CHAT_HANDOFF_PROMPT 是固定跳转，human_confirmation 是表单索引；它们不再维护实时状态。
- 普通实验/调试/讨论/导师反馈只写 EXECUTE.md。实际改变重要方法、预算或流程才追加 DECISIONS，并按需修改对应合同；不要给每轮聊天分配 D 编号。
- 新代码、测试、机器 run 产物仍按工程需要保存；配置/权重/逐例指标不塞进 Markdown。只有新内容确实无法归入既有职责，或用户明确要求独立交付时才新建文档。
- 历史结果和旧周报保留为当时快照，不继续追写；不得把历史“下一步”覆盖当前看板。详细方法合同/文献仍按需阅读，非并行路线图。管理规则以 D-029 为准。
