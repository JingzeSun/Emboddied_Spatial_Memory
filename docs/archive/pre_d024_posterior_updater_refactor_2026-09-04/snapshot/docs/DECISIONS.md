# 当前研究决策日志

> 本文件只保留现行 accepted 决策和之后的新决策。完整历史、superseded 决策及原始理由见 `archive/pre_execution_v2_2026-08-28/06_decision_log.md`。
>
> 修改 accepted 决策必须追加新条目，不得静默改写旧条目。

## 现行决策摘要

| ID | 状态 | 当前约束 |
|---|---|---|
| D-001 | accepted | ObservationGraph 与长期 world belief 分离；写入必须 association |
| D-002 | accepted | VP 是观测线索，不是长期坐标 |
| D-003 | accepted | Local Chart/Place 是 MVP 稳定锚点，不学习 split/merge |
| D-004 | accepted | MVP 不以 RGB reconstruction 为目标 |
| D-007 | baseline only | normalized EMA/limited prototypes 只是低层 state baseline |
| D-008 | superseded in scope by D-017 | online spatial context revision 保留为世界信念演化中的冲突分支；四层状态分离继续有效 |
| D-009 | accepted | Related Work 事实基石必须官方核验同行评审 |
| D-010 | retained as submechanism by D-017 | Structured Innovation + Affected-Subgraph Revision 继续负责冲突证据和局部修订，不再代表完整方法 |
| D-011 | partially superseded by D-017 | typed deterministic executor 与 oracle→deterministic→learned 保留；动作条件预测和小规模主动取证纳入主线，完整导航仍延期 |
| D-012 | accepted | superseded 合同进 archive；source artifacts 不覆盖 |
| D-013 | accepted | expansion/revision/ActiveContext 分层；方向关系必须有 reference frame |
| D-014 | superseded in structure by D-015 | 渐进式思想保留，但多入口文件结构被替换 |
| D-016 | proposed | fixture 修订判题语义待人工确认；统一由 HC-001–HC-006 跟踪 |
| D-017 | accepted | 总问题升级为动作条件下的结构化世界信念扩展与修订 |
| D-018 | proposed | 世界信念扩展判题语义待人工确认；统一由 HC-007–HC-012 跟踪 |
| D-019 | accepted | DECISIONS.md 成为唯一人工确认中心；HC 条目必须映射合同、产物和日志 |
| D-020 | accepted | 每个 HC 建立同名详细判题工作表；DECISIONS.md 仍是唯一状态与最终回答入口 |
| D-021 | accepted | 将 Region-to-World Structural Binding 纳入 planned 方法桥接层；具体绑定与写入语义由 HC-014 冻结 |
| D-022 | accepted | 核心贡献聚焦“新证据如何有限、可追溯地改变世界事实”；预测、区域绑定、主动取证与 Top-K 均降为前置或下游 |
| D-023 | proposed / blocked by HC-018 | 候选训练主线为 BEGR-Net 双时间证据图后验修订；本轮仅重构合同，不等于允许先行实施 |

## 人工确认中心（唯一入口）

> 本节是项目中所有“必须由用户/研究者确认”的唯一登记处。
>
> 其他合同、代码注释、issue 或运行日志只能引用 `HC-XXX`，不得重新复制一份待确认清单。若发现新的人工决策，必须先在这里新增 HC 条目并完成映射，才能继续修改 schema、fixture、训练目标或评测协议。

### 状态与使用规则

| 状态 | 含义 |
|---|---|
| pending | 已发现问题，等待用户明确回答 |
| accepted | 用户已确认，并已追加对应 `D-XXX` 决策 |
| rejected | 用户明确拒绝推荐默认值，并已记录替代决定 |
| superseded | 后续决策替代，保留追溯 |

执行流程：

1. 新问题先创建稳定的 `HC-XXX`，填写问题、推荐默认值、影响和映射；
2. 未获得用户明确回答前保持 `pending`，不得从代码、对话语气或实验结果推断“默认同意”；
3. 用户确认后，追加新的 `D-XXX` accepted/rejected 决策，并在 HC 行写入该决策 ID；
4. 对应合同只写“blocked by / governed by HC-XXX”并链接到本节，不再复述问题；
5. schema、fixture、config 和正式运行记录必须保存相关 `decision_ids`；
6. 若接触 test 后才改变决定，必须新建 protocol version，并在决策中明确记录。

### 当前待确认总表

以下推荐值只是项目建议，当前全部仍为 `pending`，不等于已经接受。

| HC ID | 需要用户确认的问题 | 推荐默认值 | 为什么影响结论 | 对应板块 | 计划产物/日志映射 | 状态 / 决策 |
|---|---|---|---|---|---|---|
| HC-001 | 椅子从 A 到 B 时，何时保持同一 identity？ | 只有 appearance、geometry、时间与运动约束共同高置信时沿用 ID；否则保留“搬迁/新实例”多假设并 quarantine | 决定 `SUPERSEDE` 还是 `ADD`，直接影响版本链 | [01 §4.3](01_research_contract.md)、[02 R1](02_scenario_wbs.md)、[03 E5](03_pilot_protocol.md) | `belief_graph`、`context_delta`、`tests/fixtures/R1*/`、`outputs/<run>/belief_updates/` | pending / — |
| HC-002 | 哪些关系直接存储，哪些由几何或其他关系派生？ | `supports/contains/attached_to` 优先持久化；`near/above/located_in` 按谓词逐项声明 stored/derived | 决定需要显式编辑的边和 evaluator 真值 | [01 §4.3](01_research_contract.md)、[02 R2](02_scenario_wbs.md)、[03 E5](03_pilot_protocol.md) | `belief_graph relation schema`、`tests/fixtures/R2*/`、`outputs/<run>/belief_updates/` | pending / — |
| HC-003 | 一个变化可以沿哪些关系传播？ | 为每个 operator 建 relation whitelist；禁止按图可达性无差别传播 | 决定 affected truth、漏改和越界修改 | [01 §4.3](01_research_contract.md)、[02 R2/R6](02_scenario_wbs.md)、[03 E5](03_pilot_protocol.md) | `context_delta affected/control/stop`、`tests/fixtures/R2*,R6*/`、`metrics_per_sequence.jsonl` | pending / — |
| HC-004 | 什么证据足以判定 reliable absence？ | 旧址应在预期视野内、无可信遮挡、传感器可靠且多帧缺席；只让旧位置失效，去向仍为 unknown | 决定 `PRESERVE` 还是 `INVALIDATE`，避免“没看到=不存在” | [01 §4.2/§7](01_research_contract.md)、[02 R3/R4](02_scenario_wbs.md)、[03 E5](03_pilot_protocol.md) | `observation_graph visibility`、`tests/fixtures/R3*,R4*/`、`outputs/<run>/failures/` | pending / — |
| HC-005 | 多个最小修订范围都正确时怎样判分？ | 接受所有满足 target invariants、必要传播和 control preservation 的最小等价解，不伪造唯一节点集合 | 决定 scope ground truth 和停止边界指标 | [01 §4.3/§8](01_research_contract.md)、[02 §3/§9](02_scenario_wbs.md)、[03 E0/E5](03_pilot_protocol.md) | `allowed_equivalence_class`、evaluator、`aggregate_metrics.json` | pending / — |
| HC-006 | 两个候选都可能是用户目标时，何时必须澄清？ | 只有歧义会导致不同且有代价或风险的行动时询问；否则保留候选并按 ActiveContext 排序 | 决定 query 行为，但不得改变世界事实 | [01 §5/§7](01_research_contract.md)、[02 Q1](02_scenario_wbs.md)、[03 E6](03_pilot_protocol.md) | `active_context`、`tests/fixtures/Q1*/`、`outputs/<run>/action_decisions/` | pending / — |
| HC-007 | planned action、executed action 与实际 pose transition 怎样记录？ | 三者分开；planned 是意图，executed 是下发命令，pose transition 是测量/估计结果；只有模拟器状态可标 oracle | 决定 world transition 的输入和动作失败归因 | [01 §4.1/§9](01_research_contract.md)、[02 §3/W1–W4](02_scenario_wbs.md)、[03 §2](03_pilot_protocol.md) | `episode schema`、`steps/*_action.json`、`environment.json`、`run.log` | pending / — |
| HC-008 | candidate hypothesis 何时可以提升为 confirmed fact？ | pose/geometry 一致、所需区域确实可见，并达到多帧或独立证据门；具体阈值只用 validation 冻结 | 防止把“猜测走廊继续”直接写成世界事实 | [01 §4.1/§4.2](01_research_contract.md)、[02 W1/W2](02_scenario_wbs.md)、[03 E1/E4](03_pilot_protocol.md) | `hypothesis schema`、`hypothesis_transitions/`、promotion/rejection metrics | pending / — |
| HC-009 | 直行、左转、尽头、门洞/房间等候选怎样互斥或共存？ | 显式记录 `exclusive_group_id` 与 compatibility；“尽头/继续直行”可互斥，“左开口/右开口”可共存，“门洞/房间/走廊”可保留层级歧义 | 决定是否允许多假设以及 loss/evaluator 如何判分 | [01 §4.1](01_research_contract.md)、[02 W2/W4](02_scenario_wbs.md)、[03 E1/E2/E4](03_pilot_protocol.md) | `hypothesis graph`、`candidate_hypotheses`、`hypothesis_transitions/` | pending / — |
| HC-010 | 重复走廊中，什么证据足以判定新区域、loop closure 或定位不确定？ | loop 需要外观、几何与已有拓扑共同一致；new 需要 pose 连续和新 attachment；证据冲突时保留多假设，不 append/merge | 决定 false append、false merge 和回环主张 | [01 §6/§8](01_research_contract.md)、[02 W3](02_scenario_wbs.md)、[03 E2](03_pilot_protocol.md) | association fields、`tests/fixtures/W3*/`、`sequence_predictions/`、`failures/` | pending / — |
| HC-011 | 怎样区分 ego-motion 新视野、传感器矛盾和外部世界变化？ | 先用 pose/depth 重投影解释视图变化；能被 ego-motion 解释则走 reveal/visibility，可靠残差才考虑 world change，传感器不一致则 quarantine | 决定 expansion、preserve 和 revision 是否被混用 | [01 §4.2/§9](01_research_contract.md)、[02 W2/R1/R3/R4](02_scenario_wbs.md)、[03 E1/E5](03_pilot_protocol.md) | assimilation record、evidence category、`belief_updates/`、`failures/` | pending / — |
| HC-012 | 主动观察怎样平衡任务收益、信息价值、风险和成本？ | 先用 hard safety 过滤，再比较 `task_progress + λ·information_gain - μ·action_cost`；歧义不影响任务时不为好奇反复观察；权重只用 validation 冻结 | 决定 E3 是否证明主动取证而非无意义探索 | [01 §4.4/§8](01_research_contract.md)、[02 W4](02_scenario_wbs.md)、[03 E3](03_pilot_protocol.md) | action utility config、`expected_action_targets.json`、`action_decisions/`、action-cost metrics | pending / — |
| HC-013 | Pilot 的功能级硬门、多个正确答案和端到端指标怎样聚合？ | oracle module fixtures 的合同/语义硬门必须全部通过，任一禁止行为即 No-Go；多个正确答案用 acceptable set；学习阈值只在 validation 冻结；模块与端到端结果分开报告 | 防止连续流程中的下游成功掩盖上游错误，或用平均总分抵消世界污染与安全失败 | [01 §8](01_research_contract.md)、[03 §3/§5/§6](03_pilot_protocol.md)、[详细工作表](human_confirmation/HC-013.md) | evaluation config、fixture evaluator spec、`metrics_per_sequence.jsonl`、`aggregate_metrics.json`、failure taxonomy | pending / — |
| HC-014 | 当前帧中的透视/结构区域怎样绑定、拆分、合并并巩固为持久世界节点，何时允许写入长期 latent？ | 观测区域与世界节点分层；近/中/远等只作观测属性；几何、语义、实例和遮挡线索联合关联；歧义时保留多假设或 quarantine；MVP 不学习 Chart/Place split/merge | 决定扩展与修订是否拥有稳定更新单位，也决定重复节点、错误合并和 latent 污染能否被独立评价 | [01 §4.2](01_research_contract.md)、[02 W0/W1–W3/R1/R4](02_scenario_wbs.md)、[03 E1/E2/E5](03_pilot_protocol.md)、[详细工作表](human_confirmation/HC-014.md) | planned `region_world_association`、`tests/fixtures/W0_region_binding/`、`outputs/<run>/association_records/`、association/duplicate/contamination metrics | pending / — |
| HC-015 | 真实变化时刻未知时，事实有效时间怎样表达？ | 使用区间删失：分开记录最后支持、首次矛盾、首次支持、观测与写入时间；只有存在可验证来源时才写精确事件时刻 | 决定版本链是否把感知延迟冒充事件时间，也决定 temporal validity 的 ground truth 与指标 | [01 §4.3/§8](01_research_contract.md)、[03 E5](03_pilot_protocol.md)、[BRV P2](../experiments/bounded_revision_validation/README.md)、[详细工作表](human_confirmation/HC-015.md) | fact validity schema、P2 temporal fixtures、interval/provenance metrics、belief update logs | pending / — |
| HC-016 | 哪些证据条件满足后才允许提交破坏性修订？ | 按 operator 设置 identity、visibility、pose、sensor、temporal 与正/负证据前置条件；不满足时 preserve 或 quarantine；相关帧不重复计作独立证据 | 决定何时允许 INVALIDATE/RELINK/SUPERSEDE，直接控制 false revision 与漏修订的权衡 | [01 §4.2/§4.3/§8](01_research_contract.md)、[03 E5](03_pilot_protocol.md)、[BRV P1/P2](../experiments/bounded_revision_validation/README.md)、[详细工作表](human_confirmation/HC-016.md) | commit-gate schema/config、P1 evidence fixtures、commit P/R、abstention 与 hard-failure logs | pending / — |
| HC-017 | 怎样判定外部基线是否使用结构化世界模型，并保证控制变量公平？ | 不按论文自称分类；用 SA1–SA7 审计并分为 native revision、projected snapshot、unstructured control；主因果实验固定 canonical graph 与全部上游输入，只替换 updater；snapshot 只报共同指标，结构价值另做消融 | 决定比较结果能否归因于 posterior updater，避免把检测、关联、表示和修订差异混成一个数字 | [01 §8](01_research_contract.md)、[BRV baselines](../experiments/bounded_revision_validation/BASELINES.md)、[详细工作表](human_confirmation/HC-017.md) | baseline registry、adapter audit、run manifest、structure ablation、per-metric N/A mask | pending / — |
| HC-018 | 项目收窄到 posterior 后，是否允许核心实验包先于非核心预测/主动取证/区域绑定语义实施？ | 设 posterior-only 子阶段：先冻结 HC-001–005、HC-011、HC-013、HC-015–017 并用 oracle/fixed upstream 实现 evaluator、fixtures 与确定性基线；HC-006–010、HC-012、HC-014 保持 pending，且未冻结前不得修改其 schema/config 或宣称完整 A 阶段完成 | 决定当前能否真正开始最小反证实验，还是继续被已降级的前置/下游问题阻塞 | [EXECUTE A/A1](../EXECUTE.md)、[01 §2/§8](01_research_contract.md)、[BRV protocol](../experiments/bounded_revision_validation/PROTOCOL.md)、[详细工作表](human_confirmation/HC-018.md) | phase gate、run manifest decision_ids、oracle upstream config、实验状态日志 | pending / — |

详细场景、输入输出、指标解释、数字算例和判题选项统一展开在 [`docs/human_confirmation/`](human_confirmation/README.md)，每份 HC 可独立阅读；[HC 指标白话指南](human_confirmation/METRIC_GUIDE.md)仅作跨文件术语索引。这些文件不维护状态；示例数字不是已接受阈值，状态与最终回答仍只在本表记录。

| 详细工作表 | 详细工作表 | 详细工作表 |
|---|---|---|
| [HC-001 identity](human_confirmation/HC-001.md) | [HC-002 stored/derived relations](human_confirmation/HC-002.md) | [HC-003 propagation/stop](human_confirmation/HC-003.md) |
| [HC-004 reliable absence](human_confirmation/HC-004.md) | [HC-005 equivalent revisions](human_confirmation/HC-005.md) | [HC-006 clarification](human_confirmation/HC-006.md) |
| [HC-007 action/pose record](human_confirmation/HC-007.md) | [HC-008 hypothesis promotion](human_confirmation/HC-008.md) | [HC-009 compatibility](human_confirmation/HC-009.md) |
| [HC-010 new/loop/drift](human_confirmation/HC-010.md) | [HC-011 reveal/sensor/change](human_confirmation/HC-011.md) | [HC-012 active utility](human_confirmation/HC-012.md) |
| [HC-013 evaluation gates](human_confirmation/HC-013.md) | [HC-014 region-to-world binding](human_confirmation/HC-014.md) |  |
| [HC-015 temporal validity](human_confirmation/HC-015.md) | [HC-016 revision evidence gate](human_confirmation/HC-016.md) |  |
| [HC-017 baseline fairness](human_confirmation/HC-017.md) | [HC-018 posterior-only staging](human_confirmation/HC-018.md) |  |

### 对应关系的读取方式

- **对应板块**回答“这个决定改变哪一段研究合同或实验”；
- **计划产物/日志映射**回答“以后在哪里看到它被实现和实际使用”；
- 当前尚未实现的路径只是合同映射，不得被表述为已经存在的运行产物；
- 正式 run manifest 至少保存 `decision_ids: [HC-..., D-...]`，从实验数字可以反查当时采用的人工语义。

### 新人工确认条目模板

```text
### HC-XXX — 简短标题

- 状态：pending
- 需要用户确认的问题：
- 推荐默认值：
- 可选方案及代价：
- 为什么不能由模型/实现者代答：
- 对应研究合同：
- 对应场景/实验：
- 对应 schema/config/fixture：
- 对应运行日志/指标：
- 用户回答：待确认
- 接受后写入的 D-XXX：待创建
- 是否接触 test 信息：否/是（若是，必须新建 protocol version）
- 详细工作表：`human_confirmation/HC-XXX.md`
```

## D-015 — 单执行入口与五阶段合同

- 日期：2026-08-28
- 状态：accepted
- 用户确认：`docs/00–09` 信息仍然散乱，不能形成可以照着执行的思路；旧文件可归档。
- 决策：
  1. 旧 `docs/00–12`、`START_HERE.md`、`CHECKLIST.md` 和旧 README 移入 `docs/archive/pre_execution_v2_2026-08-28/`；
  2. 根目录 `EXECUTE.md` 是唯一日常执行入口，只列当前任务、产物、退出门和下一阶段；
  3. 现行研究合同固定为五个顺序文件：研究合同 → 场景 WBS → pilot → training → formal evaluation/paper；
  4. `DECISIONS.md` 独立于顺序文档，作为 append-only 决策记录；
  5. 不允许再创建平行蓝图、第二清单或第二实验合同。
- 方法影响：无；D-008、D-010、D-013 的核心研究方向不变。
- 实验影响：无；项目仍为 pre-implementation，未使用 test 信息。
- 归档来源提交：`b11c7b0`。

## D-016 — Fixture Ground-truth 语义

- 日期：待人工确认
- 状态：proposed
- 待确认项：统一登记为 HC-001–HC-006；本条不再维护第二份问题清单。
- 影响：这些决定冻结前，R1–R6 只能写设计样例，不能称为可用于监督训练的 ground truth。
- 是否接触 test 信息：否。

## D-017 — 聚焦动作条件下的结构化世界信念演化

- 日期：2026-08-28
- 状态：accepted
- 背景：后续硕士研究建议聚焦 world model。现有方案只把“新观测与旧信念冲突后的修订”作为主问题，不能覆盖机器人移动时对未见空间的预测、候选结构扩展、主动取证和连续规划。
- 决策：
  1. 项目总问题升级为 **Action-Conditioned Structural Belief Expansion and Revision**；
  2. `SceneBelief` 解释为世界模型维护的结构化 belief state；在实现层暂不改 schema 名称；
  3. 每一步先由旧 belief 与动作产生预测先验、预期可见区域和候选结构，再与新观测比较；
  4. 新证据必须走 `confirm / expand / revise / preserve / quarantine` 中明确的一条路径；
  5. 未观察空间只能进入带置信度和来源的 hypothesis set，不得直接写成已确认世界事实；
  6. Structured Innovation 与 Affected-Subgraph Revision 保留，作为冲突和真实世界变化时的局部后验修订机制；
  7. 增加离散的一步或短视界主动取证：在任务收益、信息增益和行动成本之间选择下一观察动作；
  8. 第一阶段不做视频生成式 world model，不做端到端大规模导航，不把在线加节点本身作为创新。
- 备选方案：仅把 `SceneBelief` 改名为 world model；或直接转向像素/视频生成。二者分别缺少动作预测实质或显著扩大硕士阶段范围，因此拒绝。
- 原因：该定位能保留现有 pose-aware association、版本链、关系传播和停止边界，同时把 graph expansion、结构假设和规划纳入同一条可检验闭环。
- 影响：D-008 与 D-010 从总问题降为子问题；D-011 的“导航延期”收缩为“完整导航延期”，小规模主动观察成为核心验证；`docs/01–05`、`EXECUTE.md` 和项目方法约束需要同步更新。
- 是否接触 test 信息：否。该方向调整发生在 fixture、实现和实验结果产生之前。
- 验证方式：先做 oracle/deterministic 的逐步走廊与动态修订 micro-sequences，再学习结构预测、证据吸收和动作选择；正式 test 前冻结合同。

## D-018 — 世界信念扩展的判题语义

- 日期：待人工确认
- 状态：proposed
- 待确认项：统一登记为 HC-007–HC-012；本条不再维护第二份问题清单。
- 影响：这些决定冻结前，W1–W4 只能作为设计样例，不能称为训练或评测 ground truth。
- 是否接触 test 信息：否。

## D-019 — 唯一人工确认中心与跨对话交接

- 日期：2026-08-28
- 状态：accepted
- 用户确认：所有需要人工确认的内容集中到一个文件；后续人工确认必须写入 `DECISIONS.md`，并能映射到对应研究板块和日志；需要一份可移植的新对话 Prompt。
- 决策：
  1. `docs/DECISIONS.md` 的“人工确认中心”是唯一待确认清单；
  2. 待确认问题使用稳定的 `HC-XXX`，确认后的研究决策仍使用 append-only `D-XXX`；
  3. 每个 HC 必须记录推荐默认值、替代代价、研究合同/场景映射、schema/config/fixture 映射和运行日志/指标映射；
  4. 其他文件只能引用 HC ID，不复制问题清单；
  5. 用户明确回答后才能更新 HC 状态并追加 D 决策，不从模型、代码或模糊语气推断同意；
  6. fixture metadata 和正式 run manifest 必须保存 `decision_ids`；
  7. `docs/NEW_CHAT_HANDOFF_PROMPT.md` 只作为上下文交接材料，不构成第二执行入口。
- 原因：减少多份清单漂移，使研究语义、实现和结果能双向追溯，并允许在新对话中恢复当前状态。
- 影响：扩展 D-015 的文档治理；`AGENTS.md`、`README.md`、`EXECUTE.md` 和阶段合同统一引用人工确认中心。
- 是否接触 test 信息：否。
- 验证方式：搜索现行文档不存在第二份人工确认明细；任一 HC 能定位到研究板块与计划运行产物。

## D-020 — 每个 HC 使用独立详细判题工作表

- 日期：2026-08-29
- 状态：accepted
- 用户确认：一行 HC 无法承载需要人工考虑的多种场景、输入输出和 evaluation 标准；HC-001～HC-013 都要有独立 MD 文件。
- 决策：
  1. 在 `docs/human_confirmation/` 为每个 HC 建立同名详细工作表；
  2. 工作表展开正常、边界、歧义、传感器失败和反事实场景，以及允许输出、禁止输出、指标与用户填写项；
  3. `DECISIONS.md` 继续作为唯一 HC 状态、推荐默认值、用户回答和 D 决策入口；
  4. 详细工作表不得维护第二份 pending/accepted 状态，避免漂移；
  5. 新建 HC 时必须同步创建详细工作表并从本文件回链；
  6. HC-013 登记“功能级硬门、多个正确答案和端到端指标聚合”，保持 pending，等待用户逐项确认。
- 原因：将一个抽象问题展开成可讨论、可转成 fixture 和 evaluator 的具体判题空间，同时保持决策治理单一来源。
- 影响：扩展 D-019 的信息组织方式，不改变 D-017 方法方向，也不等于接受 HC-001～HC-013 的推荐答案。
- 是否接触 test 信息：否；尚未实现或运行实验。
- 验证方式：目录存在 HC-001～HC-013 共 13 份文件；每份包含场景、输入输出/允许与禁止结果、评价和用户填写区；现行入口均回链。

## D-021 — 纳入观测区域到持久世界节点的结构绑定桥

- 日期：2026-08-29
- 状态：accepted
- 用户确认：仅依赖视觉模型从当前帧提取语义，不足以解释观测究竟应扩充或修改哪个长期空间单元；同意开始把区域级结构绑定组件补入现行方向。
- 决策：
  1. 在 `ObservationGraph` 与 `SceneBelief` 的证据吸收之间，加入 planned 的 **Structural Observation Tokenizer + Region-to-World Structural Binding**；
  2. `ObservationRegion` 是当前视角下的临时观测单元，透视远近、消失点扇区等是观测线索，不作为持久世界 identity；
  3. 持久层优先维护 world-aligned surface、portal、object，再由稳定的 Chart/Place 组织；只有完成关联且证据达到门槛的区域才可写长期 latent；
  4. 该组件是扩展、修订和 latent 写入的表示桥，不单独宣称为已经成立的第五项创新；其论文贡献地位取决于后续消融和错误分析；
  5. 先做 oracle/deterministic 区域与绑定记录，再比较固定 patch、整帧 latent、object-only 和混合结构区域；不直接训练新的大视觉模型；
  6. HC-014 负责冻结区域来源、跨帧 association、split/merge、低置信处理、写入门和评价语义；在 HC-014 accepted 前不修改 schema/config；
  7. 绑定子测试嵌入 E1、E2、E5，共用 `W0_region_binding` fixture 家族，不新增第八个端到端实验。
- 备选方案：只使用整帧视觉 latent，或把每个透视分区直接当作持久节点。前者无法给出可审计写入范围，后者会把相机运动造成的分区变化误当成世界 identity 变化。
- 原因：世界信念扩展与局部修订都要求先回答“这份新证据属于哪个已有世界单元，还是应建立新单元”；显式桥接后才能独立测量错绑、重复节点、错误合并与 latent 污染。
- 影响：扩展 D-001、D-002、D-003 和 D-017；更新 `docs/01–05`、`EXECUTE.md`、项目入口与文献综合，但不改变现有 schema/config，也不表示已经实现或验证。
- 是否接触 test 信息：否；本决定发生在实现和正式实验之前。
- 验证方式：先以人工/oracle 对应关系构造跨视角、遮挡、拆分合并、重复走廊和动态变化的 micro-sequences；再按 HC-014 的关联、重复节点、错误合并、latent 污染和控制保持指标进行消融。

## D-022 — 以世界事实的有界后验重组作为唯一母命题

- 日期：2026-08-29
- 状态：accepted
- 用户确认：项目不能以房间布局恢复、Top-K 排序、动作预测、区域绑定和图更新的简单融合来主张创新；现行文档和 E0–E6 必须共同回答“世界事实的语义状态、拓扑关系和有效时间应该怎样改变”。
- 决策：
  1. 论文唯一母命题收缩为：**新证据到来后，哪些世界事实必须改变、怎样改变、从何时生效，哪些事实必须保持，以及为什么在该边界停止**；
  2. 核心机制工作名为 **Evidence-Gated Affected-Subgraph Belief Revision**，输出 evidence path、typed operation、affected set、control set、stop boundary 与 version/provenance；
  3. 动作条件预测只负责生成 expected belief/observation，作为发现差异的前置；region-to-world binding 只负责确定证据属于谁和允许写谁；主动取证只负责补充无法判定的证据；Top-K/ActiveContext 只负责读取，均不得与核心贡献并列堆叠；
  4. 世界事实变化按三条轴组织：semantic status（unknown/candidate/confirmed/invalid/ambiguous 等）、topological relation（add/relink/propagate/stop）与 valid time/version（旧事实何时关闭、新事实何时生效、证据如何追溯）；
  5. E0–E6 不是七个平行功能：E0 建立可信判尺；E1/E2/E4 提供候选、拓扑身份和证据晋升前置；E3 主动补证；E5 直接验证有界后验修订；E6 验证读取语境不能越权写世界事实；
  6. 主要判据不是功能数量或最终任务总分，而是 necessary-update completeness、control preservation、collateral edit、stop correctness 与 version validity；
  7. “候选创新”表示尚待文献重合审计和冻结实验支持，不表示没有明确研究假设；正式论文只能把得到证据支持的部分升级为 contribution。
- 备选方案：把预测、建图、区域表示、检索和规划并列为多个贡献。该写法无法形成单一可证伪命题，也难以排除已有模块带来的性能收益，因此拒绝。
- 原因：统一母命题能让表示、预测、association、主动取证和查询各自只承担清楚的因果角色，并用同一组“必要修改与无关保持”指标判断是否真正解决问题。
- 影响：重写 `docs/01–05` 的贡献层级与 E0–E6 解释；更新 `EXECUTE.md` 和汇报 PPT 第 2 页；D-017 的 world-model 闭环保留，但贡献中心从完整闭环收缩到证据门控的有界 posterior revision。
- 是否接触 test 信息：否；尚未实现或运行正式实验。
- 验证方式：固定相同 observation/prediction/association 输入，比较不同 revision controller；逐实验报告语义状态、拓扑关系、有效时间、必要修改和 protected controls，而非只报告端到端任务成功率。

## D-023 — 双时间证据图的可训练后验修订候选主线

- 日期：2026-09-04
- 状态：proposed；执行授权仍由 HC-018 冻结。
- 背景：用户要求把项目升级到当前主要考虑的 posterior 部分，并认为只做简单规则/对象移动不足以体现可训练研究复杂度；同时要求检查多项 loss 是否反而不利。
- 候选决策：
  1. 当前候选任务收窄为乱序、多来源 evidence events 条件下的 sparse fact-graph posterior revision；
  2. 候选模型 BEGR-Net 使用 event Transformer、typed relational graph encoder 与 hierarchical transaction decoder；
  3. learned 输出为 `preserve/quarantine/commit → targets/operators/supporting evidence`；
  4. dependency closure、control/stop、valid-time legality、atomic version 和 provenance 继续由 deterministic executor 强制；
  5. 主损失收敛为 factorized transaction NLL，加可选 evidence attribution 与小 sparsity regularizer，不采用原 17 项平行 loss；
  6. 原预测、region binding、主动取证和任务读取的细粒度合同保留为后续集成，不删除或覆盖；
  7. symbolic event streams 用于训练和反证，AI2-THOR 用于可控观测，3RScan/Dyn-THOR 用于外部有效性。
- 为什么尚未 accepted：项目治理要求用户对 HC-018 的“是否允许 posterior-only 先行实施”作明确回答；“重构为主要考虑”授权了候选方案整理，但本日志不替用户自动接受具体执行门。
- 备选方案：继续完整闭环顺序；或把所有模块端到端联合训练。前者启动成本高，后者难以归因。
- 影响：已增量重构 README、EXECUTE、docs/01–05、唯一核心实验包、data/src/tests/schema 说明和文献审计；未修改现有 schema/config，未实现代码，未接触 test。
- 验证方式：B0–B7 与 L0–L5 同输入比较；双时间、typed-edge、evidence-group、hierarchical-decoder 消融；ID/OOD 拆分；若 TGN-style/flat/full-graph 对照等价则收缩 claim。

## 新决策模板

```text
## D-XXX — 标题

- 日期：YYYY-MM-DD
- 状态：proposed / accepted / superseded / rejected
- 背景：
- 决策：
- 备选方案：
- 原因：
- 影响：
- 是否接触 test 信息：
- 验证方式：
```
