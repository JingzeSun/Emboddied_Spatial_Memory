# 当前推进清单

> 阶段入口：[`START_HERE.md`](START_HERE.md)
>
> 论文蓝图：[`docs/09_integrated_direction_plan.md`](docs/09_integrated_direction_plan.md)
>
> 场景合同：[`docs/12_use_case_and_fixture_contract.md`](docs/12_use_case_and_fixture_contract.md)

每项必须有“产物 + 验收”。状态只用：`[x] 已完成`、`[ ] 未完成`；计划不得写成已验证结果。

## 当前：S1/S2 概念与场景合同

- [x] 接受 Pose-Aware Structured Innovation + Affected-Subgraph Revision 主线。
- [x] 区分 graph expansion、belief revision、visibility update、association ambiguity 与 ActiveContext update。
- [x] 明确 FARM 是 novelty watch/接口/基线，不是核心创新来源。
- [x] 建立渐进式研究阶段 S0–S8 与 G1–G8 门禁。
- [x] 建立场景 WBS 和 fixture 通用字段。
- [ ] 人工确认六项 ground-truth 语义。
  - 产物：D-015 或后续决策日志。
  - 验收：identity、relation derivation、propagation、absence、stop、clarification 均无歧义。
- [ ] 写五个 P0 revision fixtures 和两个 P1 extension fixtures。
  - 产物：`tests/fixtures/` 或先放 `data/pilot_fixtures/`。
  - 验收：每项含正例、单因素反例、control、expected graph 与 falsifier。
- [ ] 完成合同一致性复核。
  - 产物：schema/config/docs link audit。
  - 验收：v1.1 字段、枚举、文档职责无冲突。

## 下一步：S3 无学习 pilot

- [ ] 建立 Python 工程、锁文件和 test/lint 命令。
- [ ] 实现五类 schema-backed typed contracts。
- [ ] 实现 immutable/versioned graph store。
- [ ] 实现 typed deterministic delta executor。
- [ ] 实现 fixture loader 与 exact/invariant evaluator。
- [ ] 实现 scope/propagation/preservation/stop/cost 指标。
- [ ] 跑 E0 schema/executor wiring。
- [ ] 跑 E1 单点 relocation/absence/occlusion。
- [ ] 跑 E2 relation cascade/irrelevant innovation。
- [ ] 形成 G3 Go/No-Go 报告。

G3 未通过时：修订概念、关系本体或 executor，不开始训练。

## G3 通过后：S4 训练

- [ ] T1 innovation classifier/calibration。
- [ ] T2 affected node/edge、operator、stop heads。
- [ ] T3 association ambiguity/quarantine。
- [ ] T4 noisy perception adapter。
- [ ] T5 multi-scenario curriculum。
- [ ] validation 上比较 deterministic/learned/hybrid。

## S5–S8 正式研究流程

- [ ] 仿真、感知噪声、长序列、真实序列分层验证。
- [ ] 接口公平时运行 FARM-style 外部基线。
- [ ] 冻结 claim-evidence map、配置、split、阈值、种子和 checkpoint。
- [ ] 正式 test 只按冻结协议运行；失败结果完整保存。
- [ ] 写论文、局限、负结果和复现说明。
- [ ] 干净环境重放关键实验。
- [ ] 发布 schema、fixtures、配置、评测器与基线。

## 每周记录

1. 本周关闭了哪个可证伪问题？
2. 哪个结果支持或反驳哪条假设？
3. 是否改变 contract/schema/split/threshold，原因是什么？
4. 是否接触 test 信息？
5. 下周最短可运行 vertical slice 是什么？
