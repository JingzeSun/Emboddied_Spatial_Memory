# 01 — 研究合同：双时间证据图的有界后验修订

> 状态：`accepted direction / contract refreeze in progress / not implemented / not validated`

本文只回答五件事：世界模型在本项目中指什么、核心问题是什么、各状态放在哪里、论文能主张什么、什么结果会反驳它。

## 1. 研究问题

完整系统边界仍是：在部分可观测且会发生长期变化的环境中，具身智能体怎样预测、吸收证据、维护世界信念并支持行动。但当前候选论文问题进一步收窄为：

> **当来自机器人、固定相机或日志的证据按不同延迟到达，并与已有时序事实冲突时，系统如何只提交必要的事实/依赖修订，保留无关知识，同时给出有效时间、事务时间和证据来源？**

### 1.1 唯一母命题

完整闭环服务于一个核心科学问题，不把多个现成模块并列包装成创新：

> **新证据到来后，哪些世界事实必须改变、应该怎样改变、从何时开始有效；哪些旧事实必须保持；修改为什么在这里停止？**

这里“改变世界事实”至少包含三条轴：

| 变化轴 | 要回答什么 | 例子 |
|---|---|---|
| Semantic status | 事实现在处于什么语义状态 | unknown → candidate → confirmed；visible → occluded；old location → invalid |
| Topological relation | 节点和关系怎样增加、重连、传播与停止 | 新走廊 attachment；椅子 relink；推车变化传播到箱子但不传播到花盆 |
| Valid time / version | 旧事实何时关闭，新事实何时生效，历史怎样追溯 | chair@A 在 t 关闭；chair@B 从 t+1 生效；两者共享 identity 与证据链 |

每次更新还必须显式给出 protected/control facts：它们是同一事件中**不得改变**的旧知识。核心目标不是“融合更多信息”，而是同时做到必要修改完整、无关事实保持。

把一步写清楚：

```text
旧世界信念 B_t + 已执行/候选动作 a_t
  ↓
预测先验 B^-_{t+1}
  ├─ 预期会看见什么
  └─ 未见空间的多个候选结构 H_{t+1}
  +
新观测 O_{t+1}
  ↓
证据吸收：确认 / 扩展 / 修订 / 保持 / 暂缓
  ↓
后验世界信念 B_{t+1} + 版本与证据
  ↓
下一步主动取证或任务动作 a_{t+1}
```

这里的世界不是随着机器人行走才“生成”的；变化的是智能体对世界的认识。未观察到的走廊可以被预测，但在得到证据前只能是 hypothesis，不能冒充已确认事实。

### 1.2 当前首篇工作的独立变量

主实验固定 perception、identity、visibility、pose、candidate retrieval 与 initial graph，只替换 posterior updater。真正变化的因素是：

- evidence 是否正/负、独立/重复、同步/迟到、相容/冲突；
- graph 是否包含 typed dependency；
- updater 是 no-op、overwrite、local、full-graph、通用动态图模型，还是 evidence-gated sparse transaction；
- executor 是否强制原子版本、时间区间与 provenance。

因此“椅子从 A 移到 B”只是最小单元测试；主要难度来自同一事件在延迟、多来源、遮挡、依赖级联和历史纠错下应产生不同后验，而不是对象类别识别。

## 2. 什么才算接入 world model

本项目中的最小 world-model 闭环必须同时具有：

1. **持久状态**：保存跨帧的对象、局部结构、拓扑、关系、不确定性和历史版本；
2. **动作条件预测**：根据 `B_t` 与 `a_t` 预测下一 belief prior 或 expected observation；
3. **证据吸收**：新观测到来后得到 posterior，而不是只追加观测；
4. **行动用途**：posterior 能用于下一步主动观察、短视界规划或任务读取。

以下能力单独存在时不构成本项目创新：

- 走一步增加一个地图节点；
- 用深度检测可通行区域；
- frontier exploration；
- 根据当前帧直接决定左转或右转；
- 只预测下一帧像素或 latent；
- 只做对象检索、soft ranking 或 top-K。

## 3. 已知覆盖与待验证缺口

现有工作已经覆盖在线 metric/topological mapping、主动探索、对象中心 world model、部分可观测 belief state、动态对象记忆、关系检索和选择性读取。正式事实主干必须以 `literature/peer_review_audit.md` 的同行评审核验为准。

本项目暂时把以下内容当作**待验证的研究缺口**，不能在系统性文献审计完成前写成“首次提出”：

1. 未见空间的候选结构怎样与 confirmed world facts 分开；
2. 重复视觉中怎样保留“新区域、回环、定位漂移”多个解释；
3. 怎样区分机器人移动带来的信息揭示与外部世界真实变化；
4. 候选被证据确认或否定后，怎样有限、可追溯地改变旧 belief；
5. 怎样选择动作主动验证会影响后续决策的结构歧义。

项目的重点不是其中任一基础模块，而是它们在同一条结构化 belief evolution 闭环中的可判分组合。

更严格地说，当前贡献中心不是“组合本身”，而是闭环中的 **posterior write/revision controller**。各模块的角色固定为：

| 模块 | 只负责什么 | 是否作为核心创新 |
|---|---|---|
| layout/region/视觉模型 | 提供当前观测单元与证据 | 否，前置感知 |
| action-conditioned prediction | 给出 expected belief/observation，用于发现差异 | 否，前置先验 |
| region-to-world binding | 判断证据属于谁、允许写谁 | 否，必要桥接；消融成立后才可能成为辅助贡献 |
| active verification | 证据不足时选择下一眼 | 辅助机制 |
| Top-K / ActiveContext | 决定当前任务优先读取谁 | 否，下游读取边界 |
| evidence-gated affected revision | 决定改什么、怎样传播、何时生效、哪里停止、保护什么 | **唯一核心贡献假设** |

### 3.1 “创新假设”不等于“项目没有创新”

研究启动时只能先提出一个明确、可反驳的 novelty hypothesis，不能在文献审计和实验之前宣布“已证明创新”。当前状态是：

- **已经明确**：不同于布局恢复、Top-K、动作预测或普通融合的研究对象与输出合同；
- **尚待核验**：是否已有论文实现同样的 semantic/topology/time + affected/control/stop + version 组合；
- **尚待证明**：固定相同前端后，该 controller 是否比 local-slot、full-graph、overwrite 等基线少漏改和越界修改。

只有同时满足“没有实质等价先例”和“冻结实验支持核心机制”后，创新假设才升级为论文 contribution。若发现完全等价的先例，或实验无改善，就必须收缩/更换 claim；这表示研究假设被证伪，而不是现在没有研究问题。

## 4. 核心方法

完整系统工作名称：

**Action-Conditioned Structural Belief Expansion and Revision**

中文：**动作条件下的结构化世界信念扩展与修订**。

核心机制工作名称：

**Evidence-Gated Affected-Subgraph Belief Revision**

中文：**新证据门控的受影响子图信念修订**。

```text
SceneBelief B_t + action a_t + pose/history
                  ↓
      Structural Transition & Reveal Prediction
                  ↓
 expected visible region + candidate hypothesis graph
                  ↓
        ObservationGraph O_{t+1}
                  ↓
 Structural Observation Bridge
 ├─ camera-relative regions / objects / surfaces
 ├─ region-to-world association hypotheses
 └─ allowed persistent-latent write targets
                  ↓
   Pose-aware alignment + evidence comparison
                  ↓
 Structured Belief Assimilation
 ├─ confirm hypothesis
 ├─ expand confirmed graph
 ├─ revise contradicted belief
 ├─ update visibility only
 └─ quarantine ambiguity
                  ↓
 affected seed → allowed propagation → stop boundary
                  ↓
 typed, versioned posterior update
                  ↓
 SceneBelief B_{t+1}
                  ↓
 task utility + information value + action cost
                  ↓
next observation/action
```

### 4.0 贡献层级

上图不是八个并列创新，而是一条因果链：

~~~text
预测、观测区域、association
  = 给 revision controller 的输入

evidence path + typed operation
+ affected/control/stop
+ versioned apply
  = 论文需要证明的核心机制

主动观察、Top-K、导航
  = 检查 posterior 是否有用、是否越权的下游
~~~

### 4.0.1 候选可训练实现：BEGR-Net

候选实现为 **Bi-temporal Evidence-Gated Graph Revision Network**：

1. event Transformer 编码 evidence 的 `observed_at`、`received_at`、来源、正负性和 evidence group；
2. typed relational graph encoder 编码 entity、reified fact 与 dependency；
3. hierarchical decoder 先预测 `preserve / quarantine / commit`，仅在 commit 时选择 target 与 typed operator；
4. deterministic executor 计算 dependency closure、control/stop、valid interval、atomic version 与 provenance。

模型学习“该不该提交、直接改谁、用什么操作、依据哪条证据”；确定规则负责“合法事务怎样执行”。这使错误能归因给证据判断、目标选择或执行合同，而不是由一个黑盒整图重写器共同承担。

默认训练目标是一个 factorized transaction NLL，加可选 evidence attribution 与小权重 sparsity regularizer；不把 preservation、constraint、time、task success 分别做成十多个 loss。完整接口和基线见 [BEGR-Net 合同](../experiments/bounded_revision_validation/LEARNED_MODEL.md)。

### 4.1 Structural Prediction

输入：

- 当前 confirmed belief；
- 当前 hypothesis set；
- 计划或已执行动作；
- pose、几何、可见区域和历史。

输出：

- 动作后预期可见的已知结构；
- 直行、左转、右转、尽头、门洞/房间等候选结构；
- 每个候选的置信度、来源和互斥/兼容关系；
- 不能判断时的显式 unknown。

预测不会直接修改 confirmed graph。

### 4.2 Structured Belief Assimilation

在判断 confirm/expand/revise 之前，系统先回答一个更基础的问题：**当前帧中的这块证据属于哪个已有世界单元，还是只能成为新节点候选？**

~~~text
RGB-D / pose / visual features
  → Structural Observation Tokenizer
  → 临时 ObservationRegion
  → Region-to-World Structural Binding
  → matched world node / new-node candidate / multi-hypothesis / quarantine
  → 允许写入的 world node 与 latent 范围
  → Structured Belief Assimilation
~~~

这里严格分两层：

- **观测层**：区域随当前视角产生；透视近/中/远、消失点扇区、图像左右只作线索，不是长期 identity；
- **世界层**：持久节点优先是 world-aligned surface、portal、object，再由稳定的 Chart/Place 组织；
- **写入门**：未完成 association 的区域不得直接平均进长期 latent；低置信结果保留多假设或 quarantine。

第一版使用人工/oracle 区域与确定性绑定规则，不训练新的大视觉模型。区域来源、跨帧 split/merge、巩固和长期写入语义由 [HC-014](DECISIONS.md) 冻结；其接受前不修改 schema/config。该桥目前是 planned representation substrate，不是已验证的独立贡献。

新观测与预测先验比较后必须进入一条明确路径：

| 路径 | 人话 | 写入位置 |
|---|---|---|
| confirm | 新证据支持某个候选 | candidate → confirmed 或增强证据 |
| expand | 发现此前没有候选的新结构 | 新 candidate；满足确认规则后再写 confirmed graph |
| revise | 可靠证据反驳已有事实 | versioned affected-subgraph revision |
| preserve | 只是遮挡、出视野或证据不足 | 保持 world fact，只更新 visibility/uncertainty |
| quarantine | 身份、回环或结构解释有歧义 | 保留多个假设，不贪心提交 top-1 |

`Structured Innovation` 现在是 evidence comparison 的一个子模块，重点处理预测与观测的有类型差异，而不是整个方法的总称。

### 4.3 Affected-Subgraph Revision

只有进入 `revise` 路径时，才需要回答：

- 哪些节点和关系必须改变；
- 哪些依赖后果必须传播；
- 哪些无关事实必须保持；
- 传播在什么关系前停止；
- 旧版本怎样关闭、被什么证据取代。

executor 只执行合法 typed delta，不允许 LLM 用自由文本直接改世界图。

一次合格的 posterior revision 必须同时返回：

| 输出 | 作用 |
|---|---|
| evidence path | 这是 confirm、expand、revise、preserve 还是 quarantine |
| typed operation | semantic status、relation 或 validity 应执行什么变化 |
| affected set | 为满足新证据必须改变的节点和边 |
| control set | 与事件无关、必须保持的事实 |
| propagation + stop | 哪些必要后果继续传播，在哪条边前停止 |
| version/provenance | 旧事实何时失效，新事实何时生效，依据哪条观测 |

### 4.4 Active Evidence Acquisition

第一阶段只研究离散的一步或短视界动作，例如：

- 前进；
- 左看/左转；
- 右看/右转；
- 原地复查；
- 向候选目标移动。

动作分数至少区分：

- 对任务是否有帮助；
- 能否区分关键假设；
- 行动和碰撞风险；
- 是否只是重复观察已经确定的内容。

完整端到端导航不属于第一阶段。

## 5. 状态容器

| 状态 | 保存什么 | 不能做什么 |
|---|---|---|
| ObservationGraph | 当前帧、camera-relative 几何、可见性，以及临时 object/surface/region 证据 | 充当长期事实或给透视分区持久 identity |
| RegionWorldAssociationRecord（planned） | 观测区域与世界节点的候选对应、split/merge、可靠性和允许写入目标 | 在歧义未解除时直接污染长期 latent |
| SceneBelief | 当前结构化 belief state：confirmed graph、hypothesis set、uncertainty、当前版本 | 把预测候选静默写成事实 |
| ActiveContext | 当前目标、路线、对话需要读取的候选和动作评分 | 删除未选对象或修改 world truth |
| PersistentWorldMemory | 已经确认并巩固的长期对象、结构、拓扑和版本历史 | 接收未经验证的 top-1 猜测 |

`SceneBelief` 是本项目的 world-model state。为避免无意义改名，当前 schema 仍使用既有名称；实现时必须在内部区分：

```text
SceneBelief
├─ ConfirmedGraph
├─ HypothesisSet
└─ VersionHistory / Provenance
```

## 6. 一个核心贡献与支撑能力

下表不再表示六个平行创新。它们共同为“有界 posterior revision”提供前置、核心或边界证据。

| 概念 | 在母命题中的作用 | 主要错误 |
|---|---|---|
| 动作条件预测 | 前置：产生“原本应该怎样”的比较基准 | 只根据当前帧反应 |
| 结构假设 | 前置：让未证实内容拥有可改变的候选状态 | 把想象写成事实 |
| 假设确认/撤销 | 核心之一：改变 semantic status 与 valid time | 永久追加错误节点 |
| 视野揭示与世界变化分离 | 核心之一：决定 preserve 还是 revise | 转个弯就认为世界变了 |
| 受影响关系修订 | **核心主体**：必要修改、传播、停止和 control preservation | 漏改或整图污染 |
| 主动取证 | 辅助：当前证据不足时补充决定 revision 所需的证据 | 无目的地扩大覆盖率 |

表征底座：把当前视角下的临时结构区域绑定到持久 world nodes，为扩展、修订和 latent 写入提供可审计单位；主要错误是把固定 patch/透视扇区当成世界节点，或让整帧特征无边界地平均进旧记忆。

## 7. 论文范围

### 当前 P0：posterior-only 核心

- 乱序/迟到证据下的 valid-time 与 transaction-time 分离；
- reliable absence、遮挡、来源冲突与 duplicate evidence group；
- relocation、unknown destination 与 typed dependency cascade；
- `preserve / quarantine / commit` 分层事务；
- necessary update、control preservation、stop boundary、版本回放和 provenance；
- symbolic event streams → AI2-THOR controlled change → 3RScan/Dyn-THOR secondary tracks。

下面的预测、绑定、主动取证和任务读取保留为完整系统集成边界，不再与当前训练主张并列。

### P1-A：预测与信念扩展

- 跨视角结构区域到持久 surface/portal/object 的关联与受控 latent 写入；
- 直走廊候选的提出、观察和确认；
- 墙壁否定直行、左侧开口产生新候选；
- 重复走廊中的 new-segment / loop-closure / localization ambiguity；
- predicted、confirmed、rejected、unknown 的严格分离；
- 一步主动取证动作。

### P1-B：感知接入后的真实变化与有限修订

- relocation；
- reliable absence 与 unknown destination；
- occlusion/out-of-FOV preservation；
- operator-specific relation propagation；
- irrelevant change 与 stop boundary；
- versioned deterministic execution。

### P2：边界与下游

- 人长期静止但 actor ontology 不变；
- 同类对象在路线/对话中的 ActiveContext 排序；
- 更长视界规划和真实机器人接入；
- FARM-style mapper/retrieval interface。

### 暂不做

- 视频生成式 foundation world model；
- 完整像素重建；
- 端到端大规模导航策略；
- learned Chart/Place split/merge；
- 跨人的生物身份 re-ID；
- 无约束 LLM 图编辑；
- 以更大 backbone 代替机制验证。

## 8. 可检验主张

主 claim 只有一个：

> 在相同 candidate graph 与 evidence events 输入下，显式建模 event/arrival time、证据门和稀疏 typed transaction 的 controller，比局部匹配、全图重算、无版本覆盖与通用动态图更新器更完整地完成必要修改，并更少破坏无关旧事实。

其余 claim 是前置可行性、辅助价值或系统边界；任何一项可以降级，而不应被包装成“多项创新”。

| Claim | 必须比较 | 支持证据 | 直接反证 |
|---|---|---|---|
| world-aligned region binding 提供更稳定的更新单位 | fixed patch / full-frame latent / object-only | association P/R、duplicate nodes、false merge、latent contamination、control preservation | 与简单表示无差异，或 split/merge 错误反而污染更多 |
| 候选/事实分离减少错误扩图 | greedy append / top-1 commit | false expansion 与恢复能力 | 与贪心提交无差异 |
| 动作条件假设能表达结构不确定性 | observed-only map | hypothesis recall、calibration | 候选不含真实结构或不可校准 |
| 主动取证能更快消除关键歧义 | reactive/frontier-only | 决策步数、信息收益、任务成功 | 动作更多且不提高正确性 |
| ego-motion reveal 可与 world change 分离 | frame-difference/scalar residual | 类型准确率和反事实稳定性 | 转弯持续触发错误修订 |
| affected revision 完成必要后果并保护无关事实 | local-slot / full graph | propagation recall、control preservation | 漏改或无关修改无改善 |
| 版本链使确认和撤销可追溯 | in-place overwrite | provenance/version validity | 历史不可恢复或语义混淆 |

任何失败 claim 都必须删除、降级或重新定义；不能只换模型继续保留原结论。

## 9. 几何与语义不变量

- pose 使用 `T_world_camera`，planned action、executed action 和实际 pose transition 分开记录；
- camera motion、信息揭示和 world change 分开；
- Vanishing Point 是观测线索，不是长期坐标；
- ObservationRegion 是临时观测单元；near/mid/far 或 R1–R8 编号不得跨帧充当世界 identity；
- 长期 latent 只能写入已关联的 world node；不确定对应关系必须保留候选或 quarantine；
- Chart/Place 是稳定检索与传播边界，第一阶段不学习 split/merge；
- 方向关系必须带 reference frame；camera-relative left/right 默认不持久化；
- 重复外观不能自动等于同一地点，也不能自动等于新地点；
- `unknown` 和 candidate hypothesis 不得变成虚构 confirmed location；
- 静止时长不改变 actor ontology。

## 10. 当前状态与下一步

- 已接受：D-017 的世界模型聚焦方向；
- 已接受：D-022 将核心贡献收缩为世界事实的语义状态、拓扑关系与有效时间的有界后验重组；
- 候选训练主线：BEGR-Net 与双时间 event-stream benchmark；尚未接受为 contribution，尚未训练；
- 待人工冻结：[人工确认中心](DECISIONS.md) 的 posterior 核心 HC-001–005、HC-011、HC-013、HC-015–018；其他 HC 保留给后续集成；详细判题工作表见 [`human_confirmation/`](human_confirmation/README.md)；
- 未实现：schema、hypothesis store、predictor、executor、planner；
- 未验证：本文所有 capability 和 novelty claim。

下一步只读 [`02_scenario_wbs.md`](02_scenario_wbs.md)。
