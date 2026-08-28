# Prototype Artifacts

本目录保存原型图与数据集方案 source artifacts，不覆盖、不删除。

## Pre-D008 原型

- `intro.png`：旧研究动机、核心思想和总体流程；
- `tech_stack.png`：旧技术栈；
- `faa2063f-3b17-42a4-b69a-06bed562b498.png`：透视结构区域与 slot 示例；
- `d94b8f8b-74ab-4317-b876-f93e568bbbd8.png`：动态行人干扰和双记忆更新；
- `spatial_memory_dataset_plan.pdf`：旧数据、MVP、episode、指标和消融方案。

这些材料记录构思演化，目前状态为 **pre-D008 source artifacts / superseded as active contract**。内容与现行 `docs/01_research_contract.md` 或 `docs/03_pilot_protocol.md` 冲突时，以当前合同为准。

## 新架构图要求

后续图必须显示：

1. ObservationGraph 与 projected old belief；
2. pose-aware structured innovation；
3. affected/control subgraph 与 propagation stop boundary；
4. typed ContextDelta 和 versioned executor；
5. SceneBelief、ActiveContext、PersistentWorldMemory；
6. stationary person 与 chair relocation/absence 两类案例。

新图使用新文件名和版本日期，不覆盖旧图。

## 当前汇报辅助材料

- `dynamic_spatial_revision_report_v0_1.pptx`：旧版汇报留存，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v0_3.pptx`：文献基础与方法蓝图初次重构版，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v0_4.pptx`：加入 FARM 现实差异例子与论文式双层方法图的当前版，由 `.gitignore` 忽略；
- [`dynamic_spatial_revision_report_speaker_guide.md`](dynamic_spatial_revision_report_speaker_guide.md)：术语、人话定义、WBS 执行动作、R1 示例和导师追问口头回答。

汇报辅助材料是现行合同的解释层，不是新的研究合同；当前版中的实验覆盖重排仍是建议稿，确认后才能回写 `docs/03_pilot_protocol.md`。冲突时以 `EXECUTE.md` 与 `docs/01–05` 为准。
