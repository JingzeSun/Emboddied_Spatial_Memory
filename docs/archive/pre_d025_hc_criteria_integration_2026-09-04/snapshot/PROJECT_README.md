# Embodied Spatial Memory：证据感知的稀疏图后验修订

当前唯一问题：在部分可观测、对象与关系会变化的室内环境中，面对异步、迟到、冲突和不充分的具身证据，学习怎样只修改必要世界事实及依赖关系，保留无关事实，并记录有效时间和证据来源。

\[
q_\phi(\Delta G_t,M_t,\tau_t,Z_t\mid G_{t-1},E_{\le t})
\]

方法工作名：**Evidence-Aware Sparse Graph Belief Updater（ESGBU）**。

## 现在真正研究什么

- `ΔG_t`：`KEEP / ASSERT / RETRACT / REPLACE / QUARANTINE` 编辑程序；
- `M_t`：需要修订的最小 affected seed 与依赖闭包；
- `τ_t`：世界事实何时真正改变，不等于消息何时到达；
- `Z_t`：哪些证据直接支持这次修订；
- 硬 executor：保护无关事实、互斥约束、依赖一致性、原子版本和 provenance。

模型采用小型时序证据编码器、异构图编码器、稀疏 mask、分层编辑解码器、时间头与证据归因头。主 loss 只有与四个预测变量对应的四项；state、preserve、constraint 和 task 默认作为派生评估，避免七八项 loss 重复监督。

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

## 数据轨

- [AI2-THOR Rearrangement](https://ai2thor.allenai.org/rearrangement/)：主要可控具身轨，用于 scripted changes、遮挡、视角和精确 simulator event time；
- [3RScan](https://github.com/WaldJohannaU/3RScan) + 3DSSG：真实室内多次重扫的外部有效性轨，通常只支持变化时间区间；
- symbolic generator：evaluator、快速学习和多轴反证，不替代具身实验。

三轨分别报告，不混成一个总平均分。当前均未下载、实现或运行。

## 应用切口

首选叙事是共享室内设施中的移动资产与安全状态记忆，例如仓库、实验室或医院后台的推车、容器、门和通道。论文价值在于避免迟到消息覆盖新状态、弱负证据误撤回、冲突强行提交和无关任务重算，不在于对象类别本身。

## 当前状态与发表目标

- 文档与实验设计：已按 D-024 重构；
- evaluator、数据、代码、训练和结果：均未实现/未验证；
- HC-018：仍需决定先做 12 个 hand-authored smoke cases，还是先生成 AI2-THOR；
- 质量目标：先按 RA-L 级完整度设计；只有出现真实/外部泛化和足够机制证据后再考虑 T-RO/IJRR 扩展。

“SCI”“国内 A 类”和“强国际 venue”不是同一概念。国内 A 类必须以后按目标学校/学院的最新版目录核对。

重构前的 56 文件快照位于 [`docs/archive/pre_d024_posterior_updater_refactor_2026-09-04/`](docs/archive/pre_d024_posterior_updater_refactor_2026-09-04/README.md)。原始 PDF、原型、`docs/source/`、完整文献和更早档案均保持原位。

