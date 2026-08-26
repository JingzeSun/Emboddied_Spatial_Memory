# Prototype Artifacts

本目录保存原型图与数据集方案 source artifacts，不覆盖、不删除。

## Pre-D008 原型

- `intro.png`：旧研究动机、核心思想和总体流程；
- `tech_stack.png`：旧技术栈；
- `faa2063f-3b17-42a4-b69a-06bed562b498.png`：透视结构区域与 slot 示例；
- `d94b8f8b-74ab-4317-b876-f93e568bbbd8.png`：动态行人干扰和双记忆更新；
- `spatial_memory_dataset_plan.pdf`：旧数据、MVP、episode、指标和消融方案。

这些材料记录构思演化，目前状态为 **pre-D008 source artifacts / superseded as active contract**。内容与现行 `docs/09_integrated_direction_plan.md` 冲突时，以 current blueprint 和实验合同为准。

## 新架构图要求

后续图必须显示：

1. ObservationGraph 与 projected old belief；
2. pose-aware structured innovation；
3. affected/control subgraph 与 propagation stop boundary；
4. typed ContextDelta 和 versioned executor；
5. SceneBelief、ActiveContext、PersistentWorldMemory；
6. stationary person 与 chair relocation/absence 两类案例。

新图使用新文件名和版本日期，不覆盖旧图。
