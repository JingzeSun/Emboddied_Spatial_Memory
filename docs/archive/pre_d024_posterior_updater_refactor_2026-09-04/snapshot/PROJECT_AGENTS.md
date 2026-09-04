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
- `docs/DECISIONS.md` 的“人工确认中心”是所有待用户确认问题的唯一清单；
- `docs/human_confirmation/HC-XXX.md` 是对应 HC 的唯一详细判题工作表，只展开场景、输入输出和评价选项，不维护第二份状态或最终答案；
- 任何新的人工确认问题必须先创建稳定的 `HC-XXX`，记录推荐默认值、备选代价，以及到研究板块、schema/config/fixture 和运行日志的映射；
- 新建 HC 时必须同时创建对应详细工作表，并从 `DECISIONS.md` 回链；
- 其他文件只能引用 `HC-XXX`，不得复制或维护第二份人工确认问题；
- 用户明确回答后必须追加对应 `D-XXX`，再更新 HC 状态；不得从代码、模型输出或模糊对话推断用户已经同意；
- fixture metadata、正式 run manifest 和结果日志必须保存实际采用的 `decision_ids`，使结果能反查人工语义；
- superseded 合同进入带 provenance 的 archive；
- 原始提示、导师 notes、PDF、原型图和 `docs/source/full_technical_vision.txt` 不覆盖、不删除。

`docs/NEW_CHAT_HANDOFF_PROMPT.md` 只用于跨对话传递上下文，不是第二执行入口，也不能覆盖 `EXECUTE.md`、`DECISIONS.md` 或阶段合同。

## 当前方法约束

- 完整系统是 Action-Conditioned Structural Belief Expansion and Revision；唯一核心贡献假设是 Evidence-Gated Affected-Subgraph Belief Revision；
- D-023 是 proposed 的 posterior-first 训练候选：BEGR-Net 只学习双时间 evidence 下的 gate、direct targets/operators 与 evidence attribution；HC-018 未接受前不得把候选顺序写成已授权实施；
- 当前候选主实验固定 perception/identity/visibility/pose/candidate retrieval，只替换 updater；event/arrival time、source/group 与 typed dependency 是主要受控因素；
- dependency closure、control/stop、valid-time legality、atomic version 和 provenance completeness 优先由 deterministic executor 强制，不拆成大量软 loss；
- 所有模块和实验必须回到同一母命题：世界事实的 semantic status、topological relation 与 valid time 应怎样改变，哪些 control facts 必须保持；
- action prediction、layout/region perception、region-to-world association 是前置输入；active verification 是补证；Top-K/ActiveContext 是下游读取，不得并列包装成多个创新；
- Pose-Aware Structured Innovation + Affected-Subgraph Revision 保留为冲突与真实世界变化时的子机制；
- 必须区分 ObservationGraph、SceneBelief、ActiveContext 与 PersistentWorldMemory；
- planned 的 Structural Observation Bridge 位于 ObservationGraph 与 Structured Belief Assimilation 之间，负责临时 ObservationRegion 到持久 world nodes 的 association 与 latent 写入门；
- ObservationRegion、透视近/中/远和图像分区编号只属于观测层，不得跨帧充当持久 identity；
- 持久 latent 只能写入已关联且达到证据门的 world node；歧义对应必须保留多假设或 quarantine；
- SceneBelief 是结构化 world-model belief state；其中 predicted hypothesis 与 confirmed fact 必须逻辑隔离；
- 必须区分 hypothesis creation/confirmation/rejection、confirmed graph expansion、belief revision、visibility update 和 association ambiguity；
- 未观察空间只能作为有来源和置信度的候选假设，不得直接写成确认事实；
- 必须区分 ego-motion 导致的信息揭示、定位/loop-closure 歧义和外部世界变化；
- 所有新证据先输出 typed assimilation record；只有 revision 路径额外输出 typed ContextDelta、affected/control set 和 propagation stop boundary；
- selective reading/attention 不等于 selective revision；
- 核心 revision 输出至少包含 evidence path、typed operation、affected/control set、propagation stop 与 version/provenance；
- hypothesis lifecycle 与 confirmed-graph typed edit 均由确定性版本化 executor 执行，不允许无约束 LLM 直接改图；
- 静止时长不能改变 actor ontology；
- occluded、out-of-FOV、reliably absent、unknown location 和 removed-from-scene 必须区分；
- unknown 不得写成虚构新位置；
- Chart/Place 是 MVP 稳定底座，暂不学习 split/merge。
- 区域来源、跨帧 split/merge、world-node association 与 latent write gate 受 HC-014 治理；HC-014 accepted 前不得据此修改 schema/config。

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
- 候选 posterior-first 第一里程碑是 deterministic executor/evaluator + 12 smoke fixtures；若 HC-018 未接受，仍遵守 `EXECUTE.md` 的完整 A 阶段门；
- learned 顺序必须先跑 FlatFact-MLP、Event-Transformer、TGN-style、FullGraph-RGT，再跑 BEGR-Net；不以更大 backbone 替代结构/time 消融；
- 第一个动作模块只做离散的一步或短视界主动取证，不直接做端到端完整导航；
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
