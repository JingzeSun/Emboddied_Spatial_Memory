# Affected-Subgraph Revision 推进清单

> 当前蓝图：`docs/09_integrated_direction_plan.md`
> 实验合同：`docs/03_experiment_contract.md`
> 旧清单：`docs/archive/pre_d008/CHECKLIST.md`

每项必须有“产物 + 验收”。不得因为模型训练更显眼而跳过 contract、oracle、executor 和 metrics。

## P0 — 方向与合同迁移

- [x] 接受 D-008/D-010。
  - 产物：决策日志、当前蓝图。
  - 验收：项目不再同时存在两个现行主问题。

- [x] 归档 pre-D008 合同。
  - 产物：`docs/archive/pre_d008/`。
  - 验收：旧文件明确 superseded，source artifacts 未动。

- [x] 重建现行 01–09 合同。
  - 产物：研究、方法、实验、数据、Related Work、记忆边界与算法规范。
  - 验收：所有文件以 affected-subgraph revision 为主线。

- [x] 更新配置与 schema。
  - 产物：`configs/mvp.yaml`、四个 current schemas。
  - 验收：JSON 可解析，配置与合同枚举一致。

- [x] 更新论文与文献综合。
  - 产物：`docs/11_paper_blueprint.md`、current cross-paper synthesis、PPT content。
  - 验收：不再把抗污染、双记忆或动态对象槽当主创新。

## P1 — Deterministic Vertical Slice

- [ ] 建立 Python 工程。
  - 做什么：创建 package、lockfile、test/lint 命令。
  - 产物：`pyproject.toml` 或等价环境文件。
  - 验收：新环境一条命令运行 tests。

- [ ] 实现 schema-backed contracts。
  - 做什么：BeliefGraph、ObservationGraph、ContextDelta typed records 与 JSON validation。
  - 产物：`src/.../contracts/`。
  - 验收：合法样例 round-trip；非法 version、ID、enum 被拒绝。

- [ ] 实现版本化图执行器。
  - 做什么：八个 typed operators、copy-on-write/transaction、invariants、quarantine。
  - 产物：`src/.../revision/executor.*`。
  - 验收：before/after/version/provenance exact match。

- [ ] 建立四类 micro fixtures。
  - 做什么：人遮挡门、长期静止的人、椅子可见搬迁、旧址可靠缺席。
  - 产物：`tests/fixtures/`。
  - 验收：preserve/update/isolate 均有正例与反例。

- [ ] 实现 revision metrics。
  - 做什么：delta P/R、scope F1、propagation、preservation、collateral、cost。
  - 产物：`src/.../evaluation/` 与单元测试。
  - 验收：故意漏改、多改、越界、空预测时相应指标恶化。

- [ ] 跑 E0。
  - 产物：oracle wiring 报告。
  - 验收：micro fixtures exact graph match；控制子图无变化。

## P2 — Geometry 与 Observation

- [ ] 实现 SE(3)、projection、frustum 和 visibility。
  - 验收：合成点/平面 round-trip；occluded/out-of-FOV/reliably-absent 可分。

- [ ] 实现 ObservationGraph builder。
  - 做什么：连接 RGB/depth/pose、region/object、latent、motion、visibility evidence。
  - 验收：每个字段有 source/confidence，不把估计值称 ground truth。

- [ ] 实现 expected-observation projection。
  - 验收：只读取当前 frustum/Chart 候选，不扫描完整历史。

- [ ] 实现 gated association。
  - 验收：输出候选、歧义和 unmatched，不只输出一个 ID。

## P3 — Structured Innovation

- [ ] 实现 deterministic innovation。
  - 验收：八类 innovation 在 micro/simulator fixtures 可触发。

- [ ] 冻结 reliably-absent 证据政策。
  - 做什么：人工定义证据类别，数值阈值只用 validation。
  - 验收：unknown 不被写成 removal 或虚构位置。

- [ ] 跑 E1。
  - 验收：相同输入下与 feature residual/dynamic score 公平比较。

## P4 — Affected Subgraph

- [ ] 实现 deterministic seed/propagate/stop。
  - 验收：operator-specific relation propagation 可视化。

- [ ] 实现 B1–B7。
  - 验收：共享输入、初始 belief、数据和指标。

- [ ] 跑 E2/E5。
  - 验收：oracle scope 优于 local slot；deterministic scope 有明确上限/失败。

- [ ] 实现 graph-size/history-length sweep。
  - 验收：能够识别隐式 full recomputation。

## P5 — Simulator 与 Learned Controller

- [ ] 选择 controlled synthetic 数据源。
  - 验收：许可证、pose/depth、visibility、world state 和编程接口已核验。

- [ ] 实现 state diff → ContextDelta mapper。
  - 验收：映射有 revision ID、人工抽检和歧义记录。

- [ ] 建 D1/D2 pilot。
  - 验收：counterfactual group 不跨 split，所有 oracle 可重放。

- [ ] 实现 GNN/graph Transformer controller。
  - 验收：输出 node/edge scope、stop、operator、confidence。

- [ ] 跑 E3/E4/E6。
  - 验收：stationary actor、relocation/absence/occlusion 和 sensor noise 分层报告。

## P6 — Query、正式合同与实验

- [ ] 实现 structured context query。
  - 验收：答案包含 belief version 与 evidence trace。

- [ ] 冻结正式数据规模、阈值和成功门槛。
  - 产物：experiment contract v1.1 或 v2.0、split hash。
  - 验收：未查看 test 结果。

- [ ] 跑 E0–E8、主基线和消融。
  - 验收：保存 per-episode raw outputs、置信区间、失败和缺失数据。

- [ ] 复核 novelty-watch 状态。
  - 验收：Related Work 没有把预印本写成同行评审共识。

## P7 — 论文

- [ ] 生成主架构图。
  - 验收：同时显示 projection、innovation、affected/control/stop、delta 和 revised belief。

- [ ] 生成四张主表。
  - 验收：claim—metric—baseline—ablation 一一对应。

- [ ] 冻结 contributions。
  - 验收：任何失败的 claim 被删除或降级。

- [ ] 写失败与限制。
  - 验收：报告 pose/depth、ontology、annotation、open-world unknown、Chart/Place deferred。

- [ ] 发布前复现审计。
  - 验收：新环境能重放至少一个完整 revision run 和对应图表。

## 每周记录

1. 本周关闭了哪个可证伪问题？
2. 哪个结果支持或反驳哪个假设？
3. 是否改变 contract/schema/split/threshold？
4. 是否接触 test 信息？
5. 下周最短可运行 vertical slice 是什么？
