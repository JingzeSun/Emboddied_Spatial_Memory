# Project Instructions

本文件约束该项目后续研究、代码和文档修改。

## 开始工作前

1. 阅读根目录 `README.md`；
2. 阅读 `docs/09_integrated_direction_plan.md`，它是当前最高层研究蓝图；
3. 阅读 `docs/source/full_technical_vision.txt`，不得丢失其中 observation/world、pose、Chart 和转弯约束；
4. 阅读当前 `docs/02_method_spec.md` 与 `docs/03_experiment_contract.md`；
5. 检查 `docs/06_decision_log.md`，不得悄悄改变 accepted 决策；
6. `docs/archive/` 只作追溯，不得误用为现行合同。

## 当前方法约束

- 核心方法是 Pose-Aware Structured Innovation + Affected-Subgraph Revision；
- 必须区分 ObservationGraph、SceneBelief、ActiveContext 与 PersistentWorldMemory；
- 新证据必须输出 typed ContextDelta、affected/control set 和 propagation stop boundary；
- 不得把系统简化成 dynamic gate、soft EMA、对象槽状态机或“DINO + database”；
- 不得把 selective reading/attention 冒充 selective revision；
- typed graph edit 由确定性版本化 executor 执行，不允许无约束 LLM 直接改图；
- 静止时长不能改变 actor ontology；
- occluded、out-of-FOV、reliably absent、unknown location 和 removed-from-scene 必须区分；
- unknown 不得被写成虚构新位置；
- Chart/Place 是 MVP 稳定底座，暂不学习 split/merge。

## 几何与感知约束

- camera pose 使用 `T_world_camera`，所有公式和代码明确变换方向；
- optical flow 必须先考虑 ego-motion compensation；
- Vanishing Point 是观测线索，不是长期世界坐标；
- 转弯是有效证据，不使用全局 freeze；
- 所有 observation-to-belief association 说明 pose/depth/geometry、置信度和歧义；
- 单目/估计 pose、depth、flow 不得称为 ground truth。

## 工程约束

- `src/` 接口与 current schemas、方法和实验合同一致；
- 第一实现里程碑是 deterministic oracle vertical slice，不先训练大模型；
- schema、executor、version invariants、geometry、visibility 和 metrics 必须有测试；
- 正式实验保存 config、contract、seed、data/split hash、code/model IDs、raw outputs 和失败；
- 大型数据、checkpoint、PDF 和运行输出不提交 Git；
- 文件和脚本不写死本机绝对数据路径；
- 文档中文为主，公开 API、变量、config/schema 字段使用清晰英文。

## Source Artifacts 与归档

- 原始提示、导师 notes、PDF、原型图和 `docs/source/full_technical_vision.txt` 不覆盖、不删除；
- superseded 合同移入带 provenance 的 `docs/archive/`；
- archive 只读；恢复旧实验应从对应 Git commit 建分支；
- 修改已接受方向时先更新决策日志，再同步受影响合同。

## 研究诚信

- 明确区分已接受、已实现、已验证和计划中；
- simulator world state 可称 oracle，自动 VLM/LLM 映射不能自动称 ground truth；
- test 不用于阈值、prompt、baseline、checkpoint 或模型选择；
- 不用“什么都不改”获得虚假 preservation；
- 同时报告漏改、多改、传播越界、失败、缺失数据和反例；
- Related Work 的事实主干只使用经官方来源核验的同行评审工作；
- preprint/submission 只作 novelty watch，除非状态重新核验。
