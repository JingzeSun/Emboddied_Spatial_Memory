# P1–P4 双时间后验修订实验协议

状态：`draft protocol / not implemented / not validated`

本协议只把 HC-013 的 E5 展开为可独立证伪的 posterior-only 实验。它不替代 `docs/03_pilot_protocol.md`，也不改变尚未确认的 HC 语义。

## 1. 唯一问题

给定同一份旧世界信念、同一份新证据和同一份关系契约，修订控制器能否：

1. 只在证据足以支持时修改正式事实；
2. 生成语义、拓扑和有效时间均合法的 typed edit；
3. 补齐必要依赖后果；
4. 在无许可依赖处停止；
5. 完整保留 control facts、旧版本和证据来源。

## 2. 固定输入与被测输出

### 2.1 Canonical 输入

```text
B_t                 旧 SceneBelief/confirmed fact versions
O_t                 已结构化的新 observation facts
E_t                 evidence events: polarity/source/group/coverage
observed_at         证据描述世界的事件/观测时间
received_at         系统收到证据的事务时间
I_t                 oracle 或 estimated identity association
V_t                 visibility/occlusion/out-of-FOV/reliability
Q_t                 pose 与 sensor quality
D                   stored/derived relation 与 dependency contract
base_version        本次事务所基于的图版本
```

首轮 P1–P4 使用 oracle `I_t/V_t/Q_t`。任何 estimated 输入必须另开 track，不能混入 oracle 主结果。

### 2.2 Canonical 输出

```text
evidence_path       preserve | quarantine | commit
change_type         relocation | reliable_absence | occluded |
                    out_of_fov | sensor_conflict | new_instance | ...
ordered_operations  ADD | INVALIDATE | RELINK | SUPERSEDE |
                    PRESERVE | QUARANTINE
direct_targets      learned controller 选择的直接事实目标
supporting_evidence 支持/阻止本次提交的 evidence IDs
affected_set        为满足证据和约束必须接触的事实
control_set         本次明确不得改变的事实
stop_boundary       传播被阻止的边及原因
posterior_version   原子提交后的新版本，或明确拒绝
validity            有效时间/删失区间
provenance          observation、规则、旧版本和操作的双向引用
```

`direct_targets/supporting_evidence` 由 learned controller 输出；`affected_set/control_set/stop_boundary/validity/posterior_version` 默认由 typed contract 与 executor 推导/验证。若某个消融让模型直接预测后者，必须单列，不能与 hard-executor 主方法混报。

## 3. 三个功能级实验

### P1 — 是否允许修改正式图

**固定**：旧图、identity、visibility、pose/sensor quality。

**只测**：从证据到 `change_type + preserve/quarantine/commit` 的判别。

**关键控制变量**：每组反事实只改变一个字段，例如 `occluded=false→true`，其余旧图、对象、时间和观测内容不变。

**硬失败**：遮挡或 out-of-FOV 导致失效；identity 冲突仍合并；sensor conflict 仍 commit；可靠负证据长期被当作安全 abstention。

### P2 — 决定具体怎么改、何时生效

**固定**：oracle change type、旧版本、证据、base version。

**只测**：typed operations、validity、provenance 和 transaction atomicity。

**关键控制变量**：已知事件时刻与未知事件时刻分开；current base 与 stale base 成对；唯一合法 edit 与多个等价 edit 分开。

**硬失败**：无来源精确事件时间；互斥事实有效期重叠；旧历史被物理覆盖；stale write 部分提交；等价合法答案被字符串 exact-match 误杀。

### P3 — 决定传播到哪里、在哪里停

**固定**：oracle 主编辑、relation contract、dependency graph、control set。

**只测**：required propagation、scope、control、stop 和 cycle termination。

**关键控制变量**：`support_active=true/false`、`stored/derived`、许可/非许可 dependency、单/双独立变化成对。

**硬失败**：漏掉必要后果；修改 control；沿 `room contains all objects` 泛化传播；依赖环不终止；两个独立变化被虚假路径连接。

### P4 — 决定迟到/冲突证据属于哪个时间和来源

**固定**：相同 fact graph、identity、visibility、source reliability contract 与 candidate set。

**只测**：event time、arrival/transaction time、evidence group 和 source conflict 是否产生正确 gate/历史修订。

**关键控制变量**：同步/迟到、late-but-valid/stale、同组多帧/独立重观测、两源冲突/第三源补证成对。

**硬失败**：用 arrival time 冒充 change time；旧 event 覆盖更新事实；相关帧被重复计票；冲突来源直接 destructive commit；迟到纠错破坏 current control facts。

## 4. 控制变量设计

主实验固定 representation，只改变 updater：

```text
同一 canonical structured graph
+ 同一 evidence events 与双时间字段
+ 同一 relation/dependency contract
+ 同一 candidate facts 与 base version
+ 同一 evaluator
                    ↓
只替换 revision controller
```

这组比较回答“收益是不是来自 bounded revision controller”。

另设结构消融，固定事实内容和观察，逐项删除结构字段：

1. 去掉 stored/derived 标记；
2. 去掉 dependency type/whitelist；
3. 去掉 control set；
4. 去掉 valid-time/version；
5. 把 typed graph 展平成无依赖的 fact list。

这组比较回答“哪些结构信息产生收益”。两组不能混为一个总表，否则无法判断提升来自图表示还是更新器。

## 5. 基线运行矩阵

| Baseline | 相同 canonical graph | 使用历史状态 | 主要预期失败 |
|---|---:|---:|---|
| `no_update` | 是 | 是 | 必要修改 recall=0 |
| `append_only` | 是 | 是 | 互斥旧事实仍 current |
| `latest_overwrite` | 是 | 是 | 历史/provenance 丢失 |
| `matched_node_local` | 是 | 是 | 漏掉依赖后果 |
| `incident_edge_recompute` | 是 | 是 | 可能过改所有邻边，是强简单基线 |
| `full_graph_recompute` | 是 | 可选 | 当前图可对，但 collateral/version pollution 高 |
| `bounded_revision` | 是 | 是 | 被测方法 |
| `oracle_delta` | 是 | 是 | 只校验 evaluator，不是可部署基线 |

学习型矩阵在相同输入上增加 `FlatFact-MLP`、`Event-Transformer`、`TGN-style`、`FullGraph-RGT`、`BEGR-FlatDecoder` 与 `BEGR-Net`。它们共享容量档位、trial budget、early stopping 和 calibration protocol；详细审计见 [BASELINES.md](BASELINES.md)。

外部论文方法必须先经过 [BASELINES.md](BASELINES.md) 的结构化准入和 adapter audit，不能直接把论文自报数字放进该表。

## 6. 数据规模和 split

### 6.1 Smoke

- 12 个确定性案例；
- 逐例 pass/fail；
- oracle 必须命中 acceptable output；
- 不计算可宣称性能优越性的 F1 或置信区间。

### 6.2 Template-complete dev

- 完成 P1 6、P2 6、P3 7 与 P4 8，共 27 个模板；
- 每个模板先有至少一个正例和一个单因素反事实；
- 只在 dev 调整数值阈值、规则优先级和 adapter。

### 6.3 Generated validation/test

- 模板冻结后替换对象、布局、时间间隔、无关 facts 和 dependency depth；
- 27 个模板的小实例只用于 evaluator/dev regression；learned track 由 symbolic generator 起步生成 30k train / 5k validation / 5k ID test，另留 5k OOD transactions；
- split 以模板变体族/环境为单位，不能把同一模板仅换对象名后分到 train 与 test；
- counterfactual pair 必须整体落在同一 split；OOD 预留未见 delay、source、dependency depth 与 graph size；
- test 只在 protocol、阈值、baseline 和输出字段冻结后运行一次。

## 7. 分阶段加入非 oracle 误差

| Track | 唯一新增误差 | 其他仍固定 | 用途 |
|---|---|---|---|
| T0 | 无 | 全 oracle | 修订逻辑能否成立 |
| T1 | identity | visibility/pose/sensor oracle | 身份误差敏感性 |
| T2 | visibility/occlusion | identity/pose oracle | 负证据门控敏感性 |
| T3 | pose | identity/visibility oracle | reveal/change 混淆 |
| T4 | detector/sensor | identity/pose oracle | 观测噪声敏感性 |
| T5 | 联合 estimated front-end | 无 | 端到端外部有效性 |

不得从 T5 的失败直接断言 posterior controller 失败；必须报告最早失败模块。也不得用 T5 的偶然任务成功覆盖 T0–T4 的硬失败。

## 8. 输出和复现记录

每次运行至少保存：

- protocol/config/decision IDs；
- code revision、dataset/version/split hash、seed；
- baseline/adapter ID；
- 每 case 的 eligibility、acceptable outputs、actual output 和逐字段 diff；
- required/control/stop 集合；
- hard failures 与 failure type；
- per-case metrics、aggregate metrics 和置信区间；
- raw observation/evidence references；
- model architecture、parameter count、loss weights、optimizer/scheduler、checkpoint 与 calibration temperature；
- 每个 hyperparameter trial 的预算和 validation 选择依据；
- estimated/oracle 标志；
- 缺失、不适用和被排除样例及理由。

示例见 [templates/](templates/)。正式输出仍写到项目 `outputs/`，大型数据和运行结果不提交版本库。

## 9. 退出门

### Gate 0 — 执行授权

- HC-018 若接受 posterior-only 子阶段：只在 HC-018 列出的直接相关 HC 冻结后开始 oracle/fixed-upstream pilot；
- HC-018 若未接受：继续遵守 `EXECUTE.md` 的完整 A 阶段退出门；
- 无论哪条路径，都不得把 posterior pilot 写成完整世界模型已实现或 A 阶段已完成。

### Gate A — 尺子可信

- oracle expected output 全部被 evaluator 接受；
- 人工植入漏改、越界修改、版本污染和无来源时间均能被检测；
- 非法事务原子拒绝。

### Gate B — 核心机制有增量价值

- 相对 `matched_node_local` 提高必要传播 recall；
- 相对 `full_graph_recompute` 提高 control preservation、scope precision 或减少 touched facts；
- 相对 `latest_overwrite` 保留合法时间和 provenance；
- 不得靠大规模 quarantine 获得高 commit precision。
- BEGR-Net 还必须与最强 Event-Transformer/TGN-style/FullGraph-RGT 比较；只赢规则弱基线不足以支持 learned claim。

### Gate C — 结构增量不是命名效果

- 所有主方法共享 canonical structured input；
- structure ablation 单独报告；
- adapter fidelity 达到 HC-017 冻结门槛；
- 同时报告 final snapshot 和 revision-history 指标。
- event-time、arrival-time、typed-edge、evidence-group 与 hierarchical-decoder 消融分别报告；
- 时间或边打乱不掉分时，对应 claim 自动降级。

### Gate D — 外部有效性

- AI2-THOR oracle track 通过后才运行 estimated track；
- 3RScan/3DSSG 按环境分割，未知事件时刻不计算 point-time MAE；
- 外部数据失败按 perception、association、revision、adapter 分解。

具体数值过线标准由 HC-013 在 validation 上冻结；本文件中的示例数值均不是已接受阈值。
