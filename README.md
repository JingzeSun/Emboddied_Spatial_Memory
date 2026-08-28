# Embodied Spatial Memory

研究目标：让具身智能体在新观测与旧空间信念冲突时，生成可解释、版本化、范围受控的图修订。

> 当前状态：研究合同已接受；尚未实现，尚未验证。

## 唯一入口

先读 [`EXECUTE.md`](EXECUTE.md)。它只回答：**现在做什么、产物放哪里、做到什么算通过、下一步是什么。**

之后按顺序阅读，不跳级：

1. [`docs/01_research_contract.md`](docs/01_research_contract.md)：问题、创新概念和论文边界；
2. [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md)：场景怎样拆成机器可执行 fixture；
3. [`docs/03_pilot_protocol.md`](docs/03_pilot_protocol.md)：第一版代码和无学习实验怎么做；
4. [`docs/04_training_plan.md`](docs/04_training_plan.md)：pilot 成功后训练什么；
5. [`docs/05_formal_evaluation_and_paper.md`](docs/05_formal_evaluation_and_paper.md)：正式评测、论文和复现。

Accepted 决策统一记录在 [`docs/DECISIONS.md`](docs/DECISIONS.md)。机器接口以 [`configs/mvp.yaml`](configs/mvp.yaml) 和 [`schemas/`](schemas/README.md) 为准。文献准入以 [`literature/peer_review_audit.md`](literature/peer_review_audit.md) 为准。

旧的 `docs/00–12`、旧入口和旧清单已完整归档到 [`docs/archive/pre_execution_v2_2026-08-28/`](docs/archive/pre_execution_v2_2026-08-28/README.md)，不再作为现行合同。原始技术设想和导师 notes 没有移动或覆盖。
