# 有界信念修订核心验证（后验收窄版）

状态：**已完成实验设计细化；尚未实现、尚未运行、尚无验证结果。**

这是 D-022 后验修正主张的唯一核心实验包。入口文件：

- [`PROTOCOL.md`](PROTOCOL.md)：固定输入、控制变量、分阶段运行与硬门；
- [`SCENARIOS.md`](SCENARIOS.md)：原 19 个模板、8 个双时间模板与 12-case smoke 子集；
- [`BASELINES.md`](BASELINES.md)：基线、结构化准入 SA1–SA7、表示消融；
- [`CRITERIA.md`](CRITERIA.md)：每项规则/指标的含义、公式和数字例子；
- [`DATASETS.md`](DATASETS.md)：AI2-THOR、3RScan+3DSSG、Dyn-THOR 的用途与限制；
- [`LEARNED_MODEL.md`](LEARNED_MODEL.md)：BEGR-Net、精简 loss、学习型基线、训练顺序与反证检查；
- [`NOVELTY_AND_FALSIFIERS.md`](NOVELTY_AND_FALSIFIERS.md)：与 DSG 的边界及会推翻主张的结果；
- [`templates/`](templates/)：案例合同与运行清单示例；
- [`fixtures/`](fixtures/)：确定性测试夹具的制作要求。

状态：`draft operational package / not implemented / no evidence`

本目录只验证 D-022 的核心机制：新观测与既有时序场景图冲突时，系统能否选择正确的证据处理路径、生成合法的时序事实编辑，并把传播限制在必要依赖范围内。

它不是新的实验总蓝图，也不替代 `docs/01-05`、`EXECUTE.md` 或 HC-013。当前只用于把 HC-013 的 E5 拆成一个人可以依次完成的小型验证包。

## 本轮边界

本轮允许训练 posterior updater，但不训练端到端世界模型，不把检测、跟踪、SLAM 和开放词汇识别误差混入核心机制结论，也不同时验证导航收益、长期预测或真实机器人部署。它们只能在核心机制过门后作为外部有效性实验加入。

## 三个先验验证实验

这里的“先验”指正式系统开发前的可证伪小实验，不是先训练概率先验模型。

| 实验 | 唯一问题 | 固定上游输入 | 主指标 | 硬失败示例 |
|---|---|---|---|---|
| P1 证据路径判别 | 是否应该修改正式图 | oracle 旧图、身份、可见性、位姿与传感器质量 | 六类 macro-F1、逐类 P/R、commit P/R、false-revision rate | 遮挡触发失效；身份不确定却合并；冲突证据直接提交 |
| P2 时序事实编辑 | 具体改什么、何时有效、凭什么改 | oracle 变化类型、旧事实版本、证据与 base version | acceptable-set operator accuracy、fact-edit P/R/F1、interval、provenance、atomicity | 伪造事件时刻；有效期非法重叠；缺来源；接受 stale write |
| P3 依赖范围与停止 | 影响传播到哪里、在哪里停 | oracle 主编辑、关系契约、依赖图与保护控制集 | propagation recall、scope precision、control preservation、stop accuracy | 漏必要依赖；改 control；越过停止边；循环不终止 |

P1 的标签为 `relocation / reliable_absence / occluded / out_of_fov / sensor_conflict / new_instance`，并输出 `preserve / quarantine / commit`。P2 使用 `ADD / INVALIDATE / RELINK / SUPERSEDE / PRESERVE / QUARANTINE` 等 typed operations。P3 评价 affected-subgraph closure，而不是整图相似度。

## 实验顺序

```text
P1 是否允许改
        ↓ 固定为 oracle 变化类型
P2 生成合法事实编辑
        ↓ 固定为 oracle 主编辑
P3 传播到必要依赖并停止
        ↓
三模块串联回放
        ↓
逐项加入 identity / visibility / pose / sensor 噪声
```

每一步都固定正确的上游输入。这样 P3 失败时不能把责任推给 P1。三项分别通过后才做串联；串联总分不替代模块结果。

## 学习阶段：从规则判尺到 BEGR-Net

P1–P4 不只是确定性 demo，而是 learned revision 的分解判尺：

1. 12 smoke fixtures 验证 evaluator 与 hard contract；
2. B0–B7 deterministic baselines 尽早检查强局部规则是否已经足够；
3. symbolic generator 生成带 `observed_at/received_at/source/group` 的训练事务；
4. 先跑 FlatFact-MLP、Event-Transformer，再跑 TGN-style 与 FullGraph-RGT；
5. 最后跑 BEGR-Net，并做 hierarchical decoder、typed edge、双时间和 evidence-group 消融；
6. 冻结 validation 决策后才运行 ID/OOD test 和外部数据轨道。

模型不是直接学习一张“新场景图”，而是学习 `gate → targets/operators → supporting evidence`；依赖闭包、control/stop、时间区间、原子版本和 provenance 由 executor 强制。

## 对照方法

同一批场景运行 `append_only`、`latest_overwrite`、`matched_node_local`、`full_graph_recompute` 和 `bounded_revision`。`oracle_delta` 只用于评测器自检和上界，不算可部署基线。学习型对照加入 FlatFact-MLP、Event-Transformer、TGN-style、FullGraph-RGT 与 flat-decoder ablation。所有方法必须共享初始图、观测序列、candidate facts、split 和评分器。

## 一个人可完成的规模

1. 先实现场景矩阵中标记为 smoke 的 12 个确定性用例，并让 oracle 全通过。
2. 再补齐原 19 个手工场景模板，并增加 8 个双时间/多来源模板；允许等价编辑时保存 `acceptable_outputs`。
3. 模板冻结后再替换对象、布局、时间间隔与无关事实。190 个实例只用于 evaluator/dev regression，不足以训练模型；学习数据由 symbolic generator 起步生成 30k/5k/5k train/validation/ID-test transactions，另留 5k OOD，并依据方差、失败分布和功效分析调整。
4. dev 可调阈值；test 不调阈值、不改提示、不筛方法。
5. P1–P4 功能门分别通过后，才进行串联与逐项噪声压力测试。

## 每个用例的最小记录

```yaml
case_id: P1-S01
experiment: P1
split: smoke | dev | test
decision_ids: [D-022, HC-013, HC-015, HC-016]
initial_graph: {}
observation: {}
oracle_upstream: {}
eligibility: {}
expected:
  acceptable_outputs: []
  required_updates: []
  protected_controls: []
  stop_edges: []
hard_gate_results: {}
actual:
  output: {}
  graph_diff: {}
metrics: {}
provenance: {}
failure_type: null
```

HC-015 至 HC-018 尚未确认，因此未知变化时间、commit gate、基线准入和 posterior-only 执行授权目前都只是候选语义；本轮文档重构不等于接受这些推荐值，确认前不得冻结为正式 benchmark contract 或静默跳过现有阶段门。

## 开始实现前的门槛

- 要求 HC-001 至 HC-005、HC-011、HC-013 从 pending 变为用户明确回答并产生对应 D 决策。
- 要求 HC-015、HC-016、HC-017 从 pending 变为用户明确回答并产生对应 D 决策。
- 要求 HC-018 明确授权 posterior-only 子阶段；若未授权，则先满足 `EXECUTE.md` 的完整 A 阶段门。
- stored/derived 关系和停止边已写成机器可判定契约。
- 12 个 smoke 用例及其 expected delta 已人工复核。
- 评分器能让 oracle 全通过，并能故意击败至少一个错误实现。

详细场景与指标见 [SCENARIOS.md](SCENARIOS.md)。成熟论文的验证结构审计见 [literature note](../../literature/notes/bounded_revision_validation_patterns_2026.md)。
