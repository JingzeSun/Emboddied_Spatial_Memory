# Embodied Spatial Memory：证据感知的稀疏图后验修订

当前唯一问题：在部分可观测、对象与关系会变化的室内环境中，面对异步、迟到、冲突和不充分的具身证据，学习怎样只修改必要世界事实及依赖关系，保留无关事实，并记录有效时间和证据来源。

\[
q_\phi(\Delta G_t,M_t,\tau_t,Z_t\mid G_{t-1},E_{\le t},\Sigma)
\]

方法工作名：**Evidence-Aware Sparse Graph Belief Updater（ESGBU）**。

## 现在真正研究什么

- `ΔG_t`：`KEEP / ASSERT / RETRACT / REPLACE / QUARANTINE` 编辑程序；
- `M_t`：需要修订的最小 affected seed 与依赖闭包；
- `τ_t`：世界事实何时真正改变，不等于消息何时到达；
- `Z_t`：哪些证据直接支持这次修订；
- 硬 executor：保护无关事实、互斥约束、依赖一致性、原子版本和 provenance。

`Σ` 是机器可读 predicate registry。模型采用 schema encoder、小型时序证据编码器、异构图编码器、稀疏 mask、分层编辑解码器、时间头与证据归因头；共享编辑头不能把核心谓词写死为专属分类器。主 loss 只有与四个预测变量对应的四项；state、preserve、constraint 和 task 默认作为派生评估。

## 创新不是什么

不是“识别椅子”“用 GNN 更新场景图”或“完整导航”。已有 SceneGraphFusion、Continuous Scene Representations、Scene Graph Memory、DiffVSGG 和 Embodied VideoAgent 已覆盖多种增量图或持久记忆更新。

候选差异必须由这组联合反例支撑：event/arrival 双时间、可见率条件下的负证据、多来源冲突与相关证据分组、显式最小编辑、protected controls、有效时间区间、直接 evidence set 和下游错误代价。任一项消融无效，就收缩对应 claim。

## 唯一执行入口

先读 [`EXECUTE.md`](EXECUTE.md)，再按顺序读：

1. [`docs/01_research_contract.md`](docs/01_research_contract.md)
2. [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md)
3. [`docs/03_pilot_protocol.md`](docs/03_pilot_protocol.md)
4. [`docs/04_training_plan.md`](docs/04_training_plan.md)
5. [`docs/05_formal_evaluation_and_paper.md`](docs/05_formal_evaluation_and_paper.md)

全部实验细节位于唯一活动包 [`experiments/bounded_revision_validation/`](experiments/bounded_revision_validation/README.md)，其中 `CRITERIA.md` 逐项解释指标和数字例子，`BASELINES.md` 给出结构化审计办法。

## 三条阅读路线

| 你的目的 | 从哪里开始 | 接着读什么 | 读完应能回答 |
|---|---|---|---|
| 了解项目 | 本 README | `docs/01_research_contract.md` → 实验包 `PROBLEM_FORMULATION.md` | 研究问题、变量、创新边界是什么 |
| 了解模型 | 实验包 `LEARNED_MODEL.md` | `LOSS.md` → `PROBLEM_FORMULATION.md` | 哪些部分学习、哪些约束硬执行、每项 loss 监督什么 |
| 了解实验设计 | 实验包 `README.md` | `SCENARIOS.md` → `BASELINES.md` → `CRITERIA.md` | 比什么、每行为什么测、怎么算 |
| 真正开始做 | `EXECUTE.md` | `docs/03_pilot_protocol.md` → 实验包 `PROTOCOL.md` → `human_confirmation/HC-018.md` | 当前第一步、产物、退出门是什么 |

Human Confirmation 当前只保留十个 posterior 直接项；入口为 [`docs/human_confirmation/README.md`](docs/human_confirmation/README.md)。每份工作表已内嵌 criterion、含义、计算、数字例子和需要填写的决定。

## 现在从哪里开始

当前不要一次性决定全部十个 Human Confirmation。第一件事是打开 [`HC-018`](docs/human_confirmation/HC-018.md)，决定先做哪一种早期验证。

当前建议选择 **A：先制作 12 个 hand-authored smoke cases**，暂不直接从 AI2-THOR 开始。这 12 个案例不是用来证明方法优越，而是尽早检查：

- `KEEP / RETRACT / REPLACE / QUARANTINE` 是否具有可重复标注的区别；
- affected seed、依赖闭包和 protected facts 是否存在明确答案；
- event time、arrival time、有效时间区间和 evidence set 是否可评估；
- 简单规则、序列模型、全图模型与稀疏修订模型之间是否可能形成可观察差距。

接受 HC-018 后，再按以下顺序冻结其余人工决断：

1. `HC-002～HC-005`：存储事实、派生事实、依赖传播、负证据与等价编辑；
2. `HC-015～HC-016`：有效时间标注和 `COMMIT / QUARANTINE` 边界；
3. `HC-013`：主指标、硬门槛、分子、分母和数值阈值；
4. `HC-017`：结构化基线资格与公平比较；
5. `HC-019`：下游错误任务的代价矩阵。

## 从 12 个案例到正式实验

| 阶段 | 要做什么 | 主要产物 | 进入下一阶段前必须确认 |
|---|---|---|---|
| 1. 语义冻结 | 回答 HC-018，并冻结案例需要的事实、依赖、证据和时间语义 | 已接受的 D-XXX 决策 | 两个人在同一案例上能得到一致标签 |
| 2. Smoke fixtures | 按 `case_contract.example.yaml` 制作 12 个最小反例 | 12 个经人工复核的案例 | 每个案例都有 prior、events、oracle state、等价编辑、affected set、time、evidence set |
| 3. 评估基础设施 | 实现 schema validator、deterministic executor 和 evaluator | 可复现的指标与失败报告 | 手工可计算结果与 evaluator 输出一致 |
| 4. 简单基线 | 运行 arrival-time、event-time、Bayes 和手写 gate | 第一张规则基线表 | 场景确实暴露迟到、负证据、冲突和越界传播错误 |
| 5. 学习基线 | 训练 MLP、GRU、Transformer、TGN/FullGraph-HGT | 参数匹配和速度匹配结果 | ESGBU 的比较对象不是故意做弱的 |
| 6. ESGBU 与消融 | 训练完整模型并去掉 mask、source、time、dependency、executor 等组件 | 主表、消融、校准和失败案例 | 优势同时出现在正确编辑、少改无关事实、冲突校准和泛化上 |
| 7. AI2-THOR | 自动生成可控变化、遮挡、异步与冲突事件 | 训练/验证/测试划分和跨场景结果 | 测试集未参与阈值、提示、loss 或模型选择 |
| 8. 3RScan/3DSSG | 做真实重扫数据上的外部测试 | 单列外部有效性结果 | 不把自动映射或时间区间伪装成精确 ground truth |
| 9. 发表判断 | 对照 `PUBLICATION_GATES.md` 审查机制证据与反例 | 继续、收缩 claim 或淘汰方法的决定 | 论文主张不超过实验真正支持的范围 |

日常执行以 [`EXECUTE.md`](EXECUTE.md) 为唯一入口；上表用于理解全流程，不替代各阶段的正式退出门。

## 数据轨

- [AI2-THOR Rearrangement](https://ai2thor.allenai.org/rearrangement/)：主要可控具身轨，用于 scripted changes、遮挡、视角和精确 simulator event time；
- [3RScan](https://github.com/WaldJohannaU/3RScan) + 3DSSG：真实室内多次重扫的外部有效性轨，通常只支持变化时间区间；
- symbolic generator：evaluator、快速学习和多轴反证，不替代具身实验。

三轨分别报告，不混成一个总平均分。当前均未下载、实现或运行。

## 应用切口

首选叙事是共享室内设施中的移动资产与安全状态记忆，例如仓库、实验室或医院后台的推车、容器、门和通道。论文价值在于避免迟到消息覆盖新状态、弱负证据误撤回、冲突强行提交和无关任务重算，不在于对象类别本身。

## 当前状态与发表目标

- 文档与实验设计：已按 D-024/D-025 重构；
- evaluator、数据、代码、训练和结果：均未实现/未验证；
- HC-018：D-026～D-030 已完整接受；T0a CPU-first且40小时为硬上限，后续学习训练默认使用已验证的 RTX 4070 Laptop CUDA；
- HC-002/Q02.1：D-031 已接受 schema-conditioned predicate registry；核心 stored/derived 名单仍待 Q02.2。
- 质量目标：先按 RA-L 级完整度设计；只有出现真实/外部泛化和足够机制证据后再考虑 T-RO/IJRR 扩展。

“SCI”“国内 A 类”和“强国际 venue”不是同一概念。国内 A 类必须以后按目标学校/学院的最新版目录核对。

重构前的 56 文件快照位于 [`docs/archive/pre_d024_posterior_updater_refactor_2026-09-04/`](docs/archive/pre_d024_posterior_updater_refactor_2026-09-04/README.md)。原始 PDF、原型、`docs/source/`、完整文献和更早档案均保持原位。
