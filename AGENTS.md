# Project Instructions

本文件约束该项目后续研究、代码和文档修改。

## 开始工作前

1. 阅读根目录 `README.md`；
2. 阅读 `EXECUTE.md`，确认当前阶段、任务和退出门；
3. 只阅读当前任务对应的阶段文件：
   - A：`docs/01_research_contract.md`、`docs/02_scenario_wbs.md`；
   - B/C：`docs/03_pilot_protocol.md`；
   - D：`docs/04_training_plan.md`；
   - E：`docs/05_formal_evaluation_and_paper.md`；
4. 阅读 `docs/DECISIONS.md`，不得静默改变 accepted 决策；
5. 涉及方法/几何时阅读 `docs/source/full_technical_vision.txt`；
6. `docs/archive/` 只作追溯，不得误用为现行合同。

## 文档治理

- `EXECUTE.md` 是唯一日常入口；
- 现行顺序合同只有 `docs/01–05`；
- 不新建平行蓝图、第二清单或第二实验合同；
- accepted 决策变化必须先追加 `docs/DECISIONS.md`；
- superseded 合同进入带 provenance 的 archive；
- 原始提示、导师 notes、PDF、原型图和 `docs/source/full_technical_vision.txt` 不覆盖、不删除。

## 当前方法约束

- 核心方法是 Pose-Aware Structured Innovation + Affected-Subgraph Revision；
- 必须区分 ObservationGraph、SceneBelief、ActiveContext 与 PersistentWorldMemory；
- 必须区分 graph expansion、belief revision、visibility update 和 association ambiguity；
- 新证据输出 typed ContextDelta、affected/control set 和 propagation stop boundary；
- selective reading/attention 不等于 selective revision；
- typed edit 由确定性版本化 executor 执行，不允许无约束 LLM 直接改图；
- 静止时长不能改变 actor ontology；
- occluded、out-of-FOV、reliably absent、unknown location 和 removed-from-scene 必须区分；
- unknown 不得写成虚构新位置；
- Chart/Place 是 MVP 稳定底座，暂不学习 split/merge。

## 几何与关系约束

- camera pose 使用 `T_world_camera`，所有变换明确方向；
- optical flow 先考虑 ego-motion compensation；
- Vanishing Point 是观测线索，不是长期坐标；
- 转弯是有效证据，不使用全局 freeze；
- association 说明 pose/depth/geometry、置信度和歧义；
- 方向关系带 reference frame；camera-relative left/right 默认不持久化；
- 单目/估计 pose、depth、flow 不称为 ground truth。

## 工程与实验约束

- `src/` 与 `configs/mvp.yaml`、`schemas/`、`docs/03_pilot_protocol.md` 一致；
- 第一里程碑是 deterministic oracle vertical slice，不先训练大模型；
- schema、executor、version invariants、geometry、visibility 和 metrics 必须有测试；
- 正式运行保存 config、contract、seed、data/split hash、code/model IDs、raw outputs 和失败；
- 大型数据、checkpoint、PDF 和运行输出不提交 Git；
- 文件和脚本不写死本机绝对数据路径。

## 研究诚信

- 明确区分 accepted、implemented、validated 和 planned；
- simulator world state 可称 oracle，自动映射/模型评审不能自动称 ground truth；
- test 不用于阈值、prompt、baseline、checkpoint 或模型选择；
- 同时报告漏改、多改、传播越界、失败、缺失数据和反例；
- Related Work 主干只用官方核验的同行评审工作；preprint/submission 只作 novelty watch。
