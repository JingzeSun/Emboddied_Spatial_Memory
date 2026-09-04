# 当前执行页

> 这是项目唯一的日常执行入口。
>
> 当前阶段：`A — 围绕双时间 evidence-gated posterior revision 重新冻结可判分合同`
>
> 当前状态：`in progress / no implementation / no experimental evidence`

## 现在先做什么

完成 A1–A3。当前设计与文档优先 posterior-only；是否允许它先于完整闭环进入实现，仍由 HC-018 冻结。完成前不搭视频生成式大模型、不接端到端视觉/导航、不写论文结果。

本阶段所有工作只服务一个退出问题：对于每条新证据，人能否明确判断世界事实的 semantic status、topology 和 valid time 应怎样变化，哪些 control facts 必须保持，以及传播在哪里停止。

### A1：人工冻结 posterior 核心语义，再处理集成语义

唯一清单、推荐默认值和板块/产物/日志映射见 [`docs/DECISIONS.md` 的“人工确认中心”](docs/DECISIONS.md)。

- posterior 核心：HC-001–005、HC-011、HC-013、HC-015–017；
- 后续集成：HC-006–010、HC-012、HC-014；
- HC-018：是否允许 posterior-only 子阶段先进入实现；确认前仍不得静默改变现有 A 阶段退出门。

详细场景和判题选项见 [`docs/human_confirmation/`](docs/human_confirmation/README.md)。本文件不复制问题内容。产物是：每个 HC 条目都有用户明确回答、对应的 accepted/rejected `D-XXX`，并能转成 sequence fixture 字段或判分规则。

### A2：先写双时间 posterior micro-sequences

严格按 [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md) 写：

```text
P0 posterior-only core
├─ R1 chair relocation
├─ R2 cart-box relation cascade
├─ R3 reliable absence, destination unknown
├─ R4 occlusion control
├─ R6 irrelevant change / stop
├─ T1 late evidence corrects a historical interval
├─ T2 newer arrival carries older event time
├─ T3 conflicting independent sources → quarantine
└─ T4 duplicate frames remain one evidence group

P1 later integration
├─ W0 region binding
├─ W1–W4 prediction, expansion and active verification
├─ R5 stationary person remains actor
└─ Q1 two boxes / ActiveContext
```

每个 sequence 必须包含：`base belief + action + predicted prior/hypotheses + observation regions + region/world association + allowed latent writes + semantic transition + topology edit + valid-from/valid-to + affected/control/stop + expected belief + next-action target + counterfactual`。

产物：`tests/fixtures/<fixture_id>/`。验收：人不看实现也能判断输出是否正确；无未决语义。

### A3：做合同连通检查

检查 sequence 字段能否落入现有 schema，明确需要新增但尚未实现的字段：

- `schemas/episode.schema.json`；
- `schemas/observation_graph.schema.json`；
- `schemas/belief_graph.schema.json`；
- `schemas/context_delta.schema.json`；
- `schemas/active_context.schema.json`。

至少还要表达 `action`、`predicted_prior`、`hypothesis status`、`observation evidence`、planned `region_world_association`、`allowed_latent_writes` 和 `next_action target`。不允许为了通过检查把 predicted node 混进 confirmed graph，也不允许在 HC-014 冻结前直接修改 schema/config。

posterior-only planned contract 还要表达 `observed_at`、`received_at`、`evidence_group_id`、`source_id`、正/负证据、candidate fact subgraph、base version、gate、typed operation 和 supporting evidence。先记录 v1.2 schema gap；相关 HC 冻结前不直接修改现有 schema/config。

合同连通检查的中心不是“字段都能装下”，而是从任一 posterior 数字都能反查：改了什么语义状态、哪条拓扑关系、何时生效、为什么传播、在哪里停止、哪些 control facts 被保护。

产物：合同检查记录。验收：合法样例均可表达，非法 version/ID/operator/reference frame 有明确拒绝规则。

## A 阶段退出门

只有同时满足以下条件才进入 B：

- HC-001–HC-013 全部已有用户回答和对应 `D-XXX`；D-016/D-018 不再处于 proposed；
- HC-014 当前仍是 pending；只有用户逐项回答、形成新的 accepted/rejected `D-XXX` 后，区域绑定语义才算冻结并允许退出 A；
- HC-015–HC-017 已有人工作表但仍为 pending；有效时间、commit gate 与基线公平性未冻结前，不得形成正式 benchmark contract；
- HC-018 尚未确认；若接受 posterior-only 子阶段，只表示可先做 oracle/fixed-upstream 核心 pilot，不表示完整 A 阶段完成；
- W0 已覆盖同表面跨视角、遮挡 split/merge、新区域候选、相似表面歧义和长期 latent 写入控制；
- W1–W4 与 R1–R4/R6 全部有正例、单因素反例和 control；
- R5/Q1 明确标为不变量或读取边界，不冒充核心 world-model 证据；
- predicted、confirmed、rejected 和 unknown 不混用；
- 新区域、loop closure 与定位不确定使用不同路径；
- `unknown/absent/occluded/out_of_fov/removed` 不混用；
- hypothesis expansion、confirmed graph expansion、belief revision、ActiveContext 使用不同写入路径；
- E0–E6 均已注明它是核心 revision 的判尺、前置、补证、直接验证还是读写边界；不能再作为七个平行创新叙述；
- 所有计划仍明确标注为“未实现/未验证”。

## 接下来做什么

若 HC-018 接受，执行较窄的候选通道：

```text
A-P posterior-only 合同冻结
  ↓
B-P event adapter + versioned executor + evaluator
  ↓
C-P deterministic/oracle pilot + symbolic generator
  ↓
D-P 训练 BEGR-Net，对比 flat/event/TGN/full-graph learned baselines
  ↓
E-P AI2-THOR、3RScan/Dyn-THOR 外部有效性与冻结测试
```

若 HC-018 不接受，则保留下面的完整闭环顺序。

```text
A 世界模型合同冻结
  ↓ pass
B 实现 schema + hypothesis/versioned executor + evaluator
  ↓ pass
C 运行 oracle predictive-belief pilot
  ↓ prediction/assimilation/revision mechanism survives falsification
D 分阶段训练 hypothesis/assimilation/scope/action
  ↓ validation success
E 感知接入、正式测试、论文和复现
```

每阶段的具体合同：

- A：[`docs/01_research_contract.md`](docs/01_research_contract.md) 与 [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md)；
- B/C：[`docs/03_pilot_protocol.md`](docs/03_pilot_protocol.md)；
- D：[`docs/04_training_plan.md`](docs/04_training_plan.md)；
- E：[`docs/05_formal_evaluation_and_paper.md`](docs/05_formal_evaluation_and_paper.md)。

## 禁止跳级

- oracle executor 不能 exact match：修合同/执行器，不训练；
- oracle hypothesis lifecycle 不能稳定区分候选与事实：停止训练结构预测；
- oracle region binding 不能稳定区分同一表面、不同表面和歧义：不训练 tokenizer/binder，先收缩或删除该表示层；
- repeated corridor 不能区分新扩展与 loop closure：收缩拓扑预测主张；
- oracle affected scope 不优于 local-slot：重审关系传播是否必要；
- oracle scope 不优于 full-graph 的无关保持/成本：收缩局部修订主张；
- event time 打乱后不掉分：收缩“双时间”主张；
- typed edge 打乱后在 dependency-depth OOD 不掉分：收缩“结构依赖”主张；
- TGN-style / flat Event-Transformer 与 BEGR-Net 在冻结指标上等价：不继续堆 backbone，收缩方法 claim；
- validation 失败：不看 test 调参；
- 正式 test 后改协议：建立新 protocol version，保留旧结果。

## 每次工作结束只更新三处

1. 本页的“当前阶段/当前任务”；
2. `docs/DECISIONS.md` 中新的人工确认 HC 条目或真正改变合同的 D 决策；
3. 对应阶段文档中的验收状态。

不要再新建平行蓝图、人工确认清单、个人清单或第二套实验合同。
