# Affected-Subgraph Revision 实验合同

> 合同版本：v1.1
> 状态：accepted for pilot；正式成功阈值尚未冻结
> 生效日期：2026-08-27
> 旧合同：`archive/pre_d008/03_experiment_contract.md`

本文件在查看正式 test 结果前冻结实验问题、条件、基线、指标和证伪规则。任何修改必须写入 `06_decision_log.md`，说明是否接触过 test 信息。

## 1. 主实验问题

Pose-Aware Affected-Subgraph Revision 是否能：

1. 正确识别新观测相对于旧 belief 的结构化创新；
2. 修改必要节点和关系；
3. 完成必要关系传播并在无关边界停止；
4. 区分 preserve、update 和 isolate；
5. 以低于 full recomputation 的编辑与计算成本维持 context query 正确率？

## 2. 实验单元

最重要的实验单元是 **same-world counterfactual history group**：

```text
same scene + same initial belief + aligned camera/action trajectory
├── unchanged_visible
├── viewpoint_or_turning_only
├── transient_occlusion
├── stationary_actor_short
├── stationary_actor_long
├── relocation_visible_destination
├── reliable_absence_unknown_destination
├── out_of_fov
├── irrelevant_innovation
└── sensor_inconsistency
```

同一 group 的所有条件必须位于同一 split。除目标变量外，初始状态、轨迹和传感器设置保持一致。

## 3. 基线

| ID | 方法 | 回答的问题 |
|---|---|---|
| B0 | Current observation only | 不使用旧 belief 的下限 |
| B1 | Append-only memory | 只增加、不修订会怎样 |
| B2 | Pose-warped global EMA | 对齐 + 全局软更新是否足够 |
| B3 | Slot lifecycle only | candidate/transient/changed 状态机是否足够 |
| B4 | Local matched-slot revision | 只改直接匹配 slot、不传播关系是否足够 |
| B5 | Full graph recomputation | 准确但昂贵的全量参照 |
| B6 | Oracle affected-subgraph + deterministic executor | 问题定义与 executor 的上限 |
| B7 | Deterministic predicted scope | 可解释规则基线 |
| B8 | Full proposed hybrid controller | 学习 scope/operator 的完整方法 |

所有基线使用相同 perception、pose/depth、association 输入和初始 belief。若某公开方法无法满足相同传感器假设，必须单独披露，不混入主公平比较。

## 4. 分阶段实验

### E0 — Oracle wiring

- 输入：oracle graph、oracle delta、oracle scope；
- 比较：expected graph vs executor output；
- 指标：operation exact match、graph state exact match、version/provenance validity；
- 目的：证明 schema、editor 和 metrics 没接错。

### E1 — Structured innovation

- 比较：feature residual、dynamic score、unstructured change classifier、structured innovation；
- 指标：category macro-F1、per-class precision/recall、ECE/Brier、visibility confusion；
- 目的：证明“新东西”被分解成可修订的证据类型。

### E2 — Affected-subgraph revision

- 比较：B2–B8；
- 指标：delta P/R、node/edge scope F1、operator accuracy、propagation completeness、collateral revision；
- 目的：证明该改哪里和何处停止。

### E3 — Stationary actor duration sweep

- 条件：moving → stationary，按停留时长、遮挡比例和位置分层；
- 指标：actor→structure error、door/background preservation、track continuity、leave recovery；
- 目的：证明 motion state 不改变 ontology。

### E4 — Relocation / absence / occlusion

- 条件：可见新位置、可靠旧址缺席、遮挡、out-of-FOV、removed-from-scene；
- 指标：relation edit accuracy、unknown calibration、false invalidation、revision latency；
- 目的：证明系统不会把“没看到”统一处理。

### E5 — Irrelevant innovation

- 在空间上或关系上无关的局部注入新物体/事件；
- 指标：control-subgraph preservation、collateral revision、query stability；
- 目的：验证 propagation stop boundary。

### E6 — Viewpoint and sensor robustness

- 条件：旋转、转弯、回访、pose/depth noise；
- 指标：false innovation、wrong global revision、association、calibration；
- 目的：排除 camera motion 或传感器误差造成的伪创新。

### E7 — Efficiency

- sweep：belief graph size、history length、affected-subgraph ratio；
- 指标：latency、峰值显存、读取/编辑节点比例、存储增长；
- 目的：验证不是隐式全图重算。

### E8 — Structured context query

- query：当前/历史位置、可见性、遮挡者、变化事件、新旧关系；
- 指标：answer accuracy、evidence trace accuracy、temporal consistency；
- 目的：验证图修订对下游语境读取有用。

## 5. 主指标定义

设 oracle 必要编辑集合为 (G)，预测编辑集合为 (P)：

```text
DeltaPrecision = |P intersection G| / |P|
DeltaRecall = |P intersection G| / |G|
CollateralRevisionRate = |changed control nodes/edges| / |control nodes/edges|
PropagationCompleteness = |required propagated edits completed| / |required propagated edits|
```

- node/edge scope F1；
- operator macro-F1；
- preservation accuracy；
- revision latency（关键证据出现到正确提交的帧数）；
- innovation calibration；
- context query accuracy；
- edited-node ratio；
- wall-clock latency、峰值显存和存储增长。

空预测必须按预注册规则计分，不能通过“什么都不改”获得虚假的高 precision/preservation。

## 6. 核心消融

1. 无 pose-aware projection；
2. 无 explicit visibility；
3. structured innovation → scalar residual；
4. 无 causal scores；
5. affected-subgraph → matched-slot-only；
6. 无 relation propagation；
7. 无 stop-boundary objective；
8. 无 preserve/control-subgraph loss；
9. factorized dynamic state → binary static/dynamic；
10. versioned operators → in-place overwrite；
11. deterministic vs GNN vs graph Transformer vs hybrid；
12. oracle association/scope vs predicted association/scope；
13. normalized EMA vs bounded prototypes（只作为低层 state update）。

## 7. 数据切分与调参

- split 单位：scene family；
- counterfactual group 不跨 split；
- 同一资产/人物轨迹模板记录 asset split；
- pilot 用于 schema/metric/debug，不报告最终 claim；
- train 用于学习参数；
- validation 用于阈值、loss 权重、模型和 prompt 选择；
- test 只在合同、阈值和 checkpoint 冻结后运行；
- 接触 test 后的任何改变都必须产生新 protocol version，不能覆盖原结果。

## 8. Pilot 通过门

在进入学习控制器前，必须满足：

1. E0 oracle executor 对微型 fixtures 达到 exact graph match；
2. B6 在必要传播上优于 B4；
3. relocation、reliable absence、occlusion 三类 oracle delta 可区分；
4. stationary actor 不改变 ontology；
5. control subgraph 在 oracle scope 下无非预期修改；
6. 所有结果可追溯到 config、dataset manifest、code revision 和 fixture。

这里不预填论文百分比。正式数值门槛只用 validation 结果冻结。

## 9. 核心 claim 的证伪

- B4 与 B6 无差异：affected-subgraph 问题可能不必要；
- B5 在准确率、成本和稳定性均不差：局部修订缺少价值；
- B8 只减少编辑量但显著漏改：scope 方法失败；
- E3/E4 不能同时做好：factorized semantics 或证据定义失败；
- E5 collateral revision 不下降：停止边界没有作用；
- E8 不随 delta 质量变化：下游任务或内部指标脱节；
- estimated pose/depth 下优势消失：方法只适用于 oracle 传感器。

## 10. 可复现性

每次正式运行保存：

```text
run_id
code_revision
contract_version
config_snapshot
dataset_manifest_hash
split_version
random_seeds
model_and_checkpoint_ids
sensor_sources
hardware_and_runtime
raw_per_episode_predictions
raw_per_episode_metrics
aggregate_metrics_and_confidence_intervals
failure_case_refs
```

失败、中断、缺失数据和不支持假设的结果都必须记录。

## 11. v1.1 场景、基线与门禁扩展

本节与 `START_HERE.md`、`12_use_case_and_fixture_contract.md` 共同构成当前 pilot 合同。旧 E0–E8 编号保留；以下内容为增量规范。

### 11.1 新增 counterfactual conditions

```text
graph_expansion_corner_reveal
same_category_discourse_shift
```

它们分别评测 graph attachment 与 ActiveContext，不并入 P0 revision 主指标，避免用扩展/检索表现替代动态修订证据。

### 11.2 新增机制型基线

| ID | 基线 | 用途 |
|---|---|---|
| B9 | FARM-style relational retrieval | 检查 relation predicate + soft top-K 是否已足够解决同类指代 |
| B10 | FARM-style fuse/merge | 检查累积融合/合并在 relocation、absence 与错误 association 下的污染 |
| B11 | Recency-only ActiveContext | 检查路线/对话因素是否优于简单最近出现 |

FARM 当前为 `novelty_watch_only`；若官方代码不能在共同输入上公平运行，B9/B10 使用机制等价实现并明确披露，不伪称复现官方结果。

### 11.3 E0–E8 的执行分层

- **S3/G3 mechanism pilot**：E0、E2 的 oracle scope、E4 的人工图版本、E5；
- **S4/G4 learnability**：E1、predicted E2、E3/E4 learned controller；
- **S5/G5 system validation**：E6、E7、真实 perception 与长序列；
- **下游扩展**：E8、graph expansion attachment、two-box ActiveContext。

### 11.4 扩展指标

graph expansion：

- graph attachment precision/recall；
- created-node/edge validity；
- false revision rate。

ActiveContext：

- referent candidate recall@K；
- referent accuracy@1；
- clarification calibration / expected action cost；
- nonselected-referent preservation；
- factor/evidence trace accuracy。

relation scope：

- stop-edge precision/recall；
- required propagation recall；
- control-subgraph preservation；
- outcome invariant accuracy（用于多种最小正确 delta）。

### 11.5 G3 Go/No-Go

进入学习阶段前，除第 8 节原条件外必须满足：

1. 每个 P0 fixture 有正例、单因素反例和 control；
2. relation derivation 与 stop truth 无未决语义，或已定义等价类评分；
3. B6 比 B4 少漏必要关系，且比 B5 少无关修改；
4. graph expansion 不触发无依据的旧事实失效；
5. two-box query 的候选排序不删除任一 world entity；
6. 失败可归因于 perception、association、innovation、scope 或 executor 中的具体模块。

若 G3 失败，回到 S1/S2，不通过增加模型容量绕过。
