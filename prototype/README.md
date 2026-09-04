# Prototype Artifacts

本目录保存原型图与数据集方案 source artifacts，不覆盖、不删除。

## Pre-D008 原型

- `intro.png`：旧研究动机、核心思想和总体流程；
- `tech_stack.png`：旧技术栈；
- `faa2063f-3b17-42a4-b69a-06bed562b498.png`：透视结构区域与 slot 的 source artifact；现行设计将图中 R1–R8 解释为临时 ObservationRegion 示例，不解释为持久 identity，具体绑定/写入判题映射到 `docs/human_confirmation/HC-014.md`；
- `d94b8f8b-74ab-4317-b876-f93e568bbbd8.png`：动态行人干扰和双记忆更新；
- `spatial_memory_dataset_plan.pdf`：旧数据、MVP、episode、指标和消融方案。

这些材料记录构思演化，目前状态为 **pre-D008 source artifacts / superseded as active contract**。内容与现行 `docs/01_research_contract.md` 或 `docs/03_pilot_protocol.md` 冲突时，以当前合同为准。

## 新架构图要求

后续图必须显示：

1. 当前世界信念：已确认结构、候选假设和版本历史；
2. 当前世界与动作怎样产生预期观测和结构候选；
3. 新观测怎样确认、否定、保留或扩充候选；
4. 主动观察怎样选择最能减少歧义且兼顾任务、风险和成本的动作；
5. 真实冲突时怎样进入 affected/control/stop 的有限修订子模块；
6. 重复走廊、回环/漂移、视野揭示、椅子搬迁和两个木箱等案例。

新图使用新文件名和版本日期，不覆盖旧图。

## 当前汇报辅助材料

- `dynamic_spatial_revision_report.pptx`：用户手改的 15 页文字与表达风格基准，不覆盖；
- `dynamic_spatial_revision_report_v0_1.pptx`：旧版汇报留存，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v0_3.pptx`：文献基础与方法蓝图初次重构版，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v0_4.pptx`：加入 FARM 现实差异例子与论文式双层方法图的上一版，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v0_5.pptx`：将方法图改为导师可顺讲的主链和六路状态解释，并移除汇报 WBS 页的上一版，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v0_6.pptx`：新增 oracle pilot、E0–E4、机制基线、指标和 Go/No-Go 的上一版，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v0_7.pptx`：将第 13–17 页和实验合同改为现实场景优先、人话解释优先的旧版，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v1_0.pptx`：升级到世界模型主线的当前汇报版；保留人话表达，覆盖预测、候选、主动取证、有限修订和 E0–E6，由 `.gitignore` 忽略；
- `dynamic_spatial_revision_report_v1_1.pptx`：从用户手改 v1.0 另存的 16 页版本；第 2 页加入机器人连续走廊探索应用场景图，v1.0 原件不覆盖；
- `dynamic_spatial_revision_report_v1_2.pptx`：从 v1.1 另存的 D-022 核心聚焦版；第 2 页改为 evidence-gated affected-subgraph revision 主链，v1.1 原件不覆盖；
- `dynamic_spatial_revision_report_v1_3.pptx`：保留 v1.1 的连续走廊场景版式；第 2 页新增墙面、门洞、地面与房间边界结构节点，并用青色安全轨迹和橙色过期轨迹说明世界事实变化怎样影响行动；
- [`assets/world_model_application_scene_v1.png`](assets/world_model_application_scene_v1.png)：v1.1 第 2 页使用的 imagegen 场景图；生成提示见同目录 `world_model_application_scene_v1.prompt.md`；
- [`assets/core_revision_slide_v1_2_preview.png`](assets/core_revision_slide_v1_2_preview.png)：v1.2 第 2 页的 1920×1080 渲染预览，用于检查版式和汇报可读性；
- [`assets/world_model_application_scene_nodes_paths_v2.png`](assets/world_model_application_scene_nodes_paths_v2.png)：v1.3 第 2 页使用的结构节点与行动轨迹场景图；同名 `.prompt.md` 保存编辑提示；
- [`assets/world_model_application_scene_nodes_paths_slide_v1_3_preview.png`](assets/world_model_application_scene_nodes_paths_slide_v1_3_preview.png)：v1.3 第 2 页的 1920×1080 渲染预览；
- [`dynamic_spatial_revision_report_speaker_guide.md`](dynamic_spatial_revision_report_speaker_guide.md)：v0.7 冲突修订主线的旧版讲稿，仅用于回看术语演化。

汇报辅助材料是现行合同的解释层，不是新的研究合同；v1.0–v1.2 与 `docs/03_pilot_protocol.md` 均先解释实验为什么做，再保留正式术语，不代表已经实现或获得结果。人工判题以 `docs/DECISIONS.md` 的 HC-001～HC-014 为唯一状态与回答入口，详细场景见 `docs/human_confirmation/`；未冻结前不能产生训练 ground truth。冲突时以 `EXECUTE.md`、`docs/01–05` 和已接受决策为准。
