# 当前文档索引

项目唯一阶段入口是根目录 [`../START_HERE.md`](../START_HERE.md)。它规定 S0–S8、G1–G8 和阅读顺序；本目录文件只展开某一研究阶段。

| 文件 | 当前职责 | 状态 |
|---|---|---|
| `01_research_question.md` | 主问题、假设、贡献、非目标、证伪 | accepted contract |
| `02_method_spec.md` | 状态表示、projection、innovation、scope、operator、接口 | accepted contract |
| `03_experiment_contract.md` | E0–E8、基线、指标、消融、test 规则 | accepted for pilot |
| `04_dataset_spec.md` | counterfactual history、oracle graph/delta、人工审计 | accepted for pilot |
| `05_related_work_matrix.md` | 当前论文定位、引用准入和 claim 禁区 | current |
| `06_decision_log.md` | accepted/superseded/rejected 决策与原因 | append-only log |
| `07_long_short_term_memory_block.md` | Observation/Belief/Context/Memory 边界 | accepted contract |
| `08_dynamic_context_revision.md` | StructuredInnovation、scope、stop、executor invariants | accepted contract |
| `09_integrated_direction_plan.md` | 最高层论文蓝图、优先级和证据链 | current blueprint |
| `10_implementation_roadmap.md` | 工程依赖和最短 vertical slice | current |
| `11_paper_blueprint.md` | 论文故事、图表、章节和 claim-evidence map | current |
| `12_use_case_and_fixture_contract.md` | 场景 WBS、counterfactual 与机器 fixture 合同 | accepted for pilot design |

当前任务入口：根目录 `CHECKLIST.md`。机器合同：`configs/mvp.yaml` 与 `schemas/`。文献准入：`literature/peer_review_audit.md`。

旧合同统一位于 `archive/pre_d008/`，状态为 superseded，只作追溯。原始设想位于 `source/`，是不可覆盖的 source artifact。

若文件发生冲突，优先级为：accepted decision log → `START_HERE` 阶段治理 → `09` blueprint → `12` fixture contract → `03` experiment contract → 对应分解规范 → README/清单。任何改变 accepted 决策的修改必须先更新 `06_decision_log.md`。
