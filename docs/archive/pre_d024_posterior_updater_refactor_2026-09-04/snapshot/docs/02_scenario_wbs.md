# 02 — WBS：把世界信念演化拆成可判分序列

> 状态：`current design work / sequences not implemented / oracle semantics not frozen`

本文把研究问题拆成机器可执行的 micro-sequences。WBS 是工作分解结构，不是场景的同义词。

## 1. 从主张到测试的分解

```text
Research Claim
  → Capability（要具备什么能力）
  → Use Case（现实中为什么需要）
  → Scenario Family（哪些因素会变化）
  → Micro-sequence（每一步输入、预测、观测和后验）
  → Counterfactual Pair（只改变一个证据）
  → Automatic Test（怎样判分）
```

每个 micro-sequence 必须能够回答：

1. 动作发生前，系统确认了什么、只是假设什么；
2. 执行动作后，系统预期会看到什么；
3. 实际新证据支持或否定了哪个解释；
4. 哪些内容应确认、扩展、修订、保持或暂缓；
5. 下一步为什么选择前进、转弯、侧看、复查或询问。

### 1.1 当前优先级

当前先完成 posterior-only 的 R1–R4/R6 与新增 T1–T4。W0–W4、R5、Q1 的细粒度全部保留，但移到后续集成层，避免预测、区域绑定、主动导航和后验修订同时成为独立变量。

首个现实叙事使用共享设施中的移动资产：推车带着容器移动、门/通道状态变化、固定相机与机器人异步上报。对象名称可替换，但研究因素必须保持为 evidence delay、source conflict、reliable absence、typed dependency 与 protected controls。

## 2. 围绕唯一母命题的 WBS

WBS 不把“预测、扩图、主动观察、动态修订、查询”当作五个并列研究方向，而是拆解同一个问题：

> 一条新证据要改变哪些世界事实的语义状态、拓扑关系和有效时间，并保护哪些 control facts？

```text
P0 evidence-gated posterior revision
├─ C0 确定证据属于哪个世界事实
│  └─ W0 结构区域：跨视角对应、拆分/合并与受控写入
├─ C1 产生可以被证据改变的先验状态
│  ├─ W1 直走廊：候选延伸 → 观察 → 确认
│  └─ W2 尽头左开口：否定直行 → 提出左侧候选
├─ C2 决定拓扑身份与是否暂缓
│  └─ W3 重复走廊：新区域 vs 回环 vs 定位不确定
├─ C3 证据不够时主动补证
│  └─ W4 主动取证：选择最能区分候选的动作
├─ C4 决定 semantic status / validity
│  ├─ R1 椅子搬迁
│  ├─ R3 可靠缺席、去向未知
│  └─ R4 遮挡控制
└─ C5 修改必要关系并保护旧知识
   ├─ R2 推车—箱子必要传播
   └─ R6 无关变化处停止

P1 不变量与下游读取
├─ R5 人长期静止仍是 actor
└─ Q1 两个木箱：ActiveContext 改排序，不改世界事实
```

旧 X1“转角扩图”被 W1/W2 拆成“先预测、后确认或撤销”的序列；旧 X2 改名为 Q1，继续作为读取边界。

### 2.1 每个场景在母命题中负责什么

| 场景 | Semantic status | Topological relation | Valid time / version | 在论文中的角色 |
|---|---|---|---|---|
| W0 | matched/new/ambiguous/quarantine | 决定证据允许写哪个 world node | 未绑定时禁止开启新版本 | association 前置 |
| W1 | forward candidate → confirmed/retained | 只增加实际观察到的走廊 attachment | 新结构从得到证据时生效 | 扩展型 posterior |
| W2 | H-forward → rejected；H-left → candidate | 直行边被否定，左侧开口成为候选 | 不把未见左走廊提前生效 | 反证型 posterior |
| W3 | new/loop/drift 多解释 | append、merge 或不提交 | 证据不足时不做不可逆版本 | 拓扑身份前置 |
| W4 | 不直接改变 fact status | 不直接改图 | 只产生新的后续证据 | 主动补证 |
| R1 | same identity；old location invalid；new location confirmed | chair 从 A relink 到 B | chair@A 关闭、chair@B 开启 | 核心 revision |
| R2 | 依赖事实按 operator 更新 | 必要后果沿许可关系传播 | 同一事件形成一致版本 | 核心 propagation |
| R3 | old location invalid；destination unknown | 不虚构新 attachment | 只关闭旧位置版本 | 核心 absence |
| R4 | occluded/out-of-FOV，仍 preserve | 不 relink、不删除 | 旧事实继续有效 | 核心反事实 control |
| R6 | 无关事实保持 | 传播在无许可边停止 | control versions 不变 | 核心 stop/control |
| R5 | actor ontology 保持 | 无关几何不变 | 静止时长不触发失效 | 不变量 |
| Q1 | 只改 read priority | world graph 零修改 | 版本逐字段不变 | 读写隔离边界 |

## 3. 序列 Fixture 结构

```text
tests/fixtures/<sequence_id>/
├─ initial_belief.json
├─ steps/
│  ├─ 000_action.json
│  ├─ 000_predicted_prior.json
│  ├─ 000_observation_graph.json
│  ├─ 000_oracle_update.json
│  └─ 000_expected_belief.json
├─ expected_action_targets.json
├─ metadata.yaml
└─ README.md
```

这只是计划目录，尚未实现。每一步至少表达：

```yaml
sequence_id: W2_wall_left_branch
step_id: 0
inputs:
  belief_ref: initial_belief.json
  planned_action: move_forward
  executed_action: move_forward
  pose_before: {}
  pose_after: {}
prediction:
  expected_visible_ids: []
  candidate_hypotheses: []
observation:
  graph_ref: 000_observation_graph.json
  region_world_association:
    observation_region_ids: []
    candidate_world_node_ids: []
    association_status: matched | new_candidate | ambiguous | quarantine
    allowed_latent_write_ids: []
oracle_assimilation:
  evidence_path: confirm | expand | revise | preserve | quarantine
  promoted_hypothesis_ids: []
  rejected_hypothesis_ids: []
  affected_node_ids: []
  control_node_ids: []
  propagation_stop_edge_ids: []
  ordered_operations: []
expected:
  belief_ref: 000_expected_belief.json
  acceptable_next_actions: []
counterfactual_group_id: CF_branch_01
falsifiers: []
provenance: {}
```

如果存在多个正确 posterior 或多个同样合理的取证动作，使用明确的 equivalence class；不能伪造唯一 ground truth。

## 4. P1 后续集成：预测与扩展序列

### W0 — Structural region-to-world binding

W0 不是第八个独立端到端实验，而是 W1–W3 和 R1/R4 共用的表示 fixture 家族。它先判断“当前视角下的一块区域属于世界里的谁”，再允许后续扩展或修订。

~~~text
t0 world: 已有 wall_left、floor_A、portal_1 等持久节点
t1 observation: 同一墙面因机器人前进由远变近，并被门框暂时切成两块
t1 association:
  - 两个临时 ObservationRegion 都指向 wall_left 的候选对应
  - 门框/开口作为 portal candidate 单独保留
  - near/far 和图像 R1/R2 编号不继承为世界 ID
t1 write:
  - 只有满足对应与可靠性门的区域可更新 wall_left latent
  - 低置信区域不写，进入 multi-hypothesis 或 quarantine
~~~

必须覆盖四类子序列：

1. 同一表面随视角移动、尺度变化和远近切换，仍绑定同一世界节点；
2. 同一世界表面在图像中被遮挡而 split，遮挡消失后 merge，不能复制持久节点；
3. 新看到的墙后区域、门洞或转角没有旧对应时，建立新节点候选并连接到已有 Chart；
4. 两块相似墙面、重复走廊或 pose 漂移无法区分时，不得用 top-1 污染任一长期 latent。

W0 的详细拆分、人工选项和指标见 [HC-014 工作表](human_confirmation/HC-014.md)。在 HC-014 accepted 前，上述字段只是合同草案，不修改 schema/config。

### W1 — Straight corridor confirmation

现实问题：走廊视觉长期相似时，机器人仍要知道自己发现的是更远的一段空间，而不是让“走廊”这个节点无限拉长或每帧创建重复节点。

```text
t0 confirmed: corridor_segment_A；前方 beyond_frontier 未观察
t0 action: move_forward
t0 prediction: H_forward = 前方可能仍可通行；状态=candidate
t1 observation: pose/depth 支持连续自由空间
t1 posterior:
  - 确认新的可观测区间或 segment attachment
  - 保留来源、相对几何和时间
  - 不把更远的未见空间一起确认为事实
t1 next: 根据目标继续前进或选择侧看
```

反例：若 t1 实际仍处于同一 pose 或观测只是重复帧，不得增加长度。

### W2 — Wall and left opening

现实问题：机器人原先倾向于认为走廊继续向前，但看到墙壁和左侧自由空间后，应改变结构假设并据此转向。

```text
t0 candidate: H_forward = 走廊继续
t0 action: move_forward
t1 observation: 前方墙；左侧深度为空
t1 posterior:
  - reject H_forward
  - propose H_left_passage
  - 只把“左侧可通行开口”写成得到支持的结构
  - 暂不把它武断标成走廊；仍可能是门洞或房间
t1 next: left-look 或 left-turn，用下一帧区分候选
```

反例：如果左侧仅是反光、深度缺失或低置信区域，正确路径应是 quarantine，而不是确认左转走廊。

### W3 — Repeated-corridor aliasing

现实问题：相似画面既可能来自新走廊段，也可能来自回到旧位置或定位漂移。

```text
输入：相似视觉 + pose/odometry/history + 已有拓扑
至少保留：
  H_new: 新 segment
  H_loop: 与旧 segment 回环
  H_pose: 定位仍不确定
输出：候选概率/置信度、各自需要的验证证据
禁止：只凭图像相似就 merge；只凭前进里程就 append
```

反事实组分别只改变：独特地标、闭环几何一致性、pose 漂移大小或连接可行性。

### W4 — Active verification

现实问题：当不同结构解释会导致不同路线时，机器人应该先获取能区分它们的证据。

```text
belief: H_left_passage 与 H_room 都可能
候选动作：
  continue_forward
  look_left
  turn_left
  reobserve
正确动作集合：
  在安全约束下，优先选择能够区分 H_left_passage/H_room
  且对当前任务有价值的动作
```

第一阶段只在离散候选动作中判分，不要求连续控制或完整导航。

## 5. P0 当前核心：真实变化与有限修订

### R1 — Chair relocation

```text
base: chair_1 located_in zone_A
action-conditioned expectation: 若 A 可见，应在 A 看到 chair_1
observation: chair_1 在 B 可靠重现，identity evidence 足够
posterior: 关闭 A 位置版本，建立 B 版本；身份和无关对象保持
counterfactual: 同类但非同一实例 → ADD，不是 SUPERSEDE
```

### R2 — Cart-box propagation

```text
base: cart_1 supports box_1；plant_1 独立
observation: cart_1/box_1 在新区域可靠出现
must update: cart 状态及 operator-specific 依赖后果
must preserve: supports 关系若仍有证据；plant_1 和无关区域
stop: 所有没有许可依赖的外出边
```

[HC-002](DECISIONS.md) 冻结前，R2 的关系存储/派生语义仍没有训练真值。

### R3 — Reliable absence, destination unknown

```text
base: chair_1 in A
observation: A 应可见、无遮挡、传感器可靠、多帧为空
posterior: 旧位置失效；当前去向 unknown
forbidden: 虚构 B；没有独立证据时标成 removed_from_scene
```

### R4 — Occlusion control

与 R3 共用旧 belief、动作和对象，只增加可信遮挡或降低可见性。正确结果必须从 `revise/INVALIDATE` 变成 `preserve + visibility_update`。

### R6 — Irrelevant change / stop

变化区域与目标子图没有人工许可的 dependency path。正确 affected set 只包含变化本身或为空，不得沿 room contains 边污染所有对象。

### 5.1 T1–T4 — 双时间与多来源证据

| ID | 只改变的因素 | 必须输出 | 禁止行为 |
|---|---|---|---|
| T1 late correction | 描述 t=12 的证据到 t=20 才收到 | 在事务时间 t=20 修订覆盖 t=12 的有效区间，保留接收日志 | 把 `received_at=20` 冒充 `changed_at=20` |
| T2 stale late arrival | t=20 收到的证据实际观测于 t=8，旧事实最后支持于 t=10 | preserve/quarantine，并指出 temporal precondition 不满足 | 因“最新收到”就覆盖 t=10 的较新事实 |
| T3 source conflict | 两个独立来源分别支持相反事实 | quarantine、保留两个来源与待验证条件 | 任取最大 confidence 直接 destructive commit |
| T4 duplicate group | 同一扫视的 10 帧都支持缺失 | 只计 1 个 evidence group | 把 10 帧当 10 个独立证人越过提交门 |

每个 T 场景至少配一个 counterfactual：T1 只把 `observed_at` 改到最新、T2 只把它改到旧事实之后、T3 只增加第三个独立证据组、T4 只把第二批帧改为新位置的独立重观测。若两个样本除该字段外仍有其他变化，则不能用于因果解释。

建议训练生成因子：

| Factor | Development values | OOD holdout |
|---|---|---|
| arrival delay | 0、1–3、4–10 steps | 11–30 steps |
| evidence groups | 1、2、3 | 4–6 |
| source reliability | 0.6、0.8、0.95 | 未见来源 ID + 0.7 |
| dependency depth | 0、1、2 | 3–5 |
| control-fact count | 0、10、50 | 100–500 |
| graph size | 20、50、100 facts | 200–1000 facts |

这些数值是数据生成范围，不是通过阈值。split 按 template family、environment 与 counterfactual group 隔离；同一模板只换对象名不能跨 train/test。

## 6. P2 不变量与读取边界

### R5 — Stationary person

只改变人的静止时长和门的遮挡程度。人的 ontology 始终是 actor；门的身份和几何不能因遮挡改变。

### Q1 — Two-box ActiveContext

```text
PersistentWorldMemory: box_A 与 box_B 都保留
SceneBelief: 两个实例和版本都保留
ActiveContext: 路线/对话可让 box_B 排名更高
decision: 有行动代价且歧义关键时询问
```

query 前后 confirmed world graph 必须相同。

## 7. 单因素反事实矩阵

| Group | 只改变 | 正确路径应改变为 |
|---|---|---|
| CF-region-bind | 同一表面跨视角 ↔ 外观相似但不同表面 | MATCH/controlled write ↔ NEW/AMBIGUOUS/no write |
| CF-region-split | 遮挡造成两块 ↔ 两个真实独立表面 | temporary split/same world node ↔ separate world nodes |
| CF-confirm | 后续观测支持 ↔ 否定候选 | confirm ↔ reject/revise |
| CF-branch | 左侧可靠自由空间 ↔ 深度缺失 | propose/verify ↔ quarantine |
| CF-loop | 几何闭环一致 ↔ 不一致 | loop hypothesis ↑ ↔ new hypothesis ↑ |
| CF-action | 侧看能区分 ↔ 不能区分 | active verify ↔ task action |
| CF-change-source | 仅 ego-motion ↔ 外部对象移动 | reveal/visibility ↔ revision |
| CF-identity | 同一 identity ↔ 新实例 | SUPERSEDE ↔ ADD |
| CF-visibility | reliably empty ↔ occluded | INVALIDATE ↔ PRESERVE |
| CF-dependency | 有许可依赖 ↔ 无依赖 | propagate ↔ stop |
| CF-dialogue | 路线/对话历史不同 | ActiveContext 改，world graph 不改 |

## 8. 人工确认门

所有待确认问题、推荐默认值及其到 W/R/Q 场景、schema、fixture 和运行日志的映射，统一维护在 [`DECISIONS.md` 的“人工确认中心”](DECISIONS.md)。每个 HC 的场景与判题选项只在 [`human_confirmation/`](human_confirmation/README.md) 的同名工作表展开，状态仍只在 `DECISIONS.md` 维护。

- W0 以及 W1–W3、R1/R4 中的区域绑定子步骤受 HC-014 约束；
- W1–W4 受 HC-007–HC-012 约束；
- R1–R6/Q1 受 HC-001–HC-006 约束，并可能同时引用 change-source 相关的 HC-011；
- T1–T4 受 HC-015 的 valid-time 语义与 HC-016 的 evidence gate 约束；
- 是否允许先实现 R/T 的 posterior-only 子阶段由 HC-018 冻结；
- 每个 fixture 的 `metadata.yaml` 必须记录采用的 `decision_ids`。

本文件不得重新维护人工确认问题清单。确认前，相关 sequence 只能用于讨论设计；数值阈值只能用 train/validation 选择，自动映射、VLM/LLM 判断和模拟器派生标签不能自动称为 ground truth。

## 9. 完成标准

- R1–R4/R6 与 T1–T4 先有完整 sequence；W0–W4、R5/Q1 的已有细节保留为后续集成；
- 每个 P0 序列有正例、单因素反例和 control；
- hypothesis 与 confirmed fact 使用不同写入路径；
- sequence 能重放 action → prior → observation → posterior → next action；
- schema 能拒绝 predicted node 直接进入 confirmed graph；
- 人不看实现也能判断正确 posterior 和允许的下一动作集合；
- 所有结果仍明确标为计划中，未实现、未验证。

通过后进入 [`03_pilot_protocol.md`](03_pilot_protocol.md)。
