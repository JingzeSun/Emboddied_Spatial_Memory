# 当前研究决策日志

> 本文件记录重要研究/预算/流程决策及其历史状态，不是日常实验日志。普通进度、对话和导师反馈只写 [EXECUTE.md](../EXECUTE.md)。较早原始理由见 `archive/pre_execution_v2_2026-08-28/06_decision_log.md`。
>
> 修改 accepted 决策必须追加新条目，不得静默改写旧条目。

## 现行决策摘要

| ID | 状态 | 当前约束 |
|---|---|---|
| D-001 | accepted | ObservationGraph 与长期 world belief 分离；写入必须 association |
| D-002 | accepted | VP 是观测线索，不是长期坐标 |
| D-003 | historical scope; see D-018/D-021 | 早期 MVP 稳定锚点；其“不学习 split/merge”不是后续 CPMT 的现行范围约束 |
| D-004 | accepted | MVP 不以 RGB reconstruction 为目标 |
| D-007 | baseline only | normalized EMA/limited prototypes 只是低层 state baseline |
| D-008 | accepted | 主问题是 online spatial context revision；四层状态分离 |
| D-009 | accepted | Related Work 事实基石必须官方核验同行评审 |
| D-010 | superseded by D-017 | Structured Innovation + Affected-Subgraph Revision 保留历史，不再是活动主方法 |
| D-011 | accepted | typed deterministic executor；oracle→deterministic→learned；导航延期 |
| D-012 | accepted | superseded 合同进 archive；source artifacts 不覆盖 |
| D-013 | accepted | expansion/revision/ActiveContext 分层；方向关系必须有 reference frame |
| D-014 | superseded in structure by D-015 | 渐进式思想保留，但多入口文件结构被替换 |
| D-016 | superseded in structure by D-017 | 未决语义迁入 HC-001/002/003/006，不再作为单一六项合同 |
| D-017 | superseded in scope by D-018 | executable transaction 核心保留；命名、层级和流程由 D-018 收敛 |
| D-018 | accepted | Embodied-first CPMT；CTL 为唯一学习机制；M0–M3 范围锁 |
| D-019 | accepted | identity lifecycle 与 version closure 分离；冻结 BIND/REACTIVATE 前置条件 |
| D-020 | accepted | candidate 显式确认、确定性 dormant 维护；所有方法必须附中文白话说明 |
| D-021 | accepted | SPLIT 新建对称后继；MERGE 保留最早 confirmed canonical ID |
| D-022 | accepted | RETRACT 默认撤回 fact version；REPLACE 不删除旧对象身份 |
| D-023 | accepted | QUARANTINE 保存低权重、可检索、可重激活的暂定认知 |
| D-024 | accepted | graph-equivalence 的 anchored/exchangeable 旧身份与新身份严格双射 |
| D-025 | accepted | 等价只消除表示差异；未来投影相似不合并可能不同的世界状态 |
| D-026 | accepted | 保留即时在线判断；新观测到来后可修订，不提前读取下一帧 |
| D-027 | accepted development only | 授权本地 CTL 开发训练；暂定配置不等于正式 M1 冻结 |
| D-028 | proposed | 公开数据/单房间投影试点与云资源建议，未正式采纳 |
| D-029 | superseded by D-032 | EXECUTE 为唯一追加实验记录，不按对话新建或复制进度页 |
| D-032 | accepted | EXECUTE 只为实验结果、架构变化或需保留的失败 run 追加 LOG；普通对话不逐轮记录 |
| D-030 | accepted by D-031 | M1 v1 数值合同获接受；命名由 D-031 澄清后冻结 |
| D-031 | accepted | M1 A 改称 CPMT-CTL Core；Full CPMT 保留给接入 PNO 的完整系统；test 继续封存 |
| D-033 | accepted | 云支出改为操作者控制，协议记录而不再以 `==0` 拦截；本地优先与 bugcheck 停止规则不变 |
| D-034 | accepted | M1-v2 使用有界补偿恢复、结构化 E、active-world 主指标和共享 commit 校准 |
| D-035 | accepted | `M1_V2_CLOSEOUT_FLOW.md` 是 M1-v2 唯一阶段流程文件 |
| D-036 | accepted | S1/S2 只用 train/inner-dev，不再消费 validation report |
| D-037 | accepted | S2 先审计只读 static preflight；启用前必须另立 decision |
| D-038 | accepted | static preflight 成为 A–E 共享 online admissibility mask；保留 executor illegal 能量与完整候选审计 |
| D-039 | accepted as amended | live energy、两条候选架构臂和完整重跑；规模/机制/now 细节由 D-040/D-041 修订 |
| D-040 | accepted | 1000/200/200 个总混合 groups；C10/C11 必须有真实行为机制与指纹 gate |
| D-041 | accepted | current 固定自然量程、软后验逐项影响审计和五个预登记机制切片 |
| D-042 | accepted; optimization details superseded by D-043 | v8 双架构 train/inner-dev 有限预算框架保留；具体网络归一化、网格和逐方法选择由 D-043 更新 |
| D-043 | accepted | A–E 严格共用架构与 12 格搜索空间、各自按同一 reference 指标选预算；Pre-LN 主臂、共享/交叉预算读数与触顶纪律预登记 |
| D-044 | accepted | test 前以固定 train-only anchor 一次判定 exact endpoint 是否退化；必要时切到同构 multiset-Jaccard，并把 open-memory/evidence、节点与完整 collateral 纳入覆盖、安全和检验力定样 |
| D-045 | accepted; AUC effect values superseded by D-046 | 正名并分解 open-fact error；terminal/AUC 并报；固定无选择 gate、recovery 空分母和 false-birth 集合差 |
| D-046 | accepted | AUC `40/80` 持续等价门、C train/inner-dev 顺序权重选择、纯 validation confirmation 与三种提交率 |
| D-047 | accepted | 收紧 claim 与 online/executor/外生轨迹边界；H3-vs-H1 teacher 对照为主文必报机制证据但不进入成败门 |

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
- 必须决定：
  1. identity continuation；
  2. relation storage/derivation；
  3. operator-specific propagation；
  4. reliable absence evidence；
  5. stop equivalence/scoring；
  6. clarification action cost。
- 影响：这些决定冻结前，R1–R6 只能写设计样例，不能称为可用于监督训练的 ground truth。
- 是否接触 test 信息：否。

## D-017 — Counterfactual Transaction Learning 主线切换

- 日期：2026-09-04
- 状态：accepted
- 用户确认：将当前版本先作为垃圾/历史分支推送 Git，然后按“反事实事务学习 + projective/equivariant structural node latent + versioned deterministic executor”重构整个项目，并把硬条件作为真实实验验证。
- 背景：D-010 的 affected-subgraph revision 容易被评价为新的 loss 或局部 graph updater；持久 3D memory、latent prediction、scene-graph update 和多假设关联均已有强先例。需要把可被证伪的机制差异落在“候选编辑真实执行后，由未来结构证据评价执行后世界”。
- 决策：
  1. main 的唯一活动方法改为 Counterfactual Transaction Learning（CTT）；
  2. 顶层事务空间固定为 NOOP/BIND/BIRTH/SPLIT/MERGE/RELINK/RETRACT；
  3. 候选事务必须从同一旧图版本克隆并由 deterministic executor 真实执行；
  4. hindsight teacher 评价 post-edit world 的 action-conditioned future projective consistency；
  5. online updater 在推理时禁止读取未来，仅从 hindsight 结果蒸馏；
  6. Projective/Equivariant Structural Node Latent 是 representation foundation，不单独作为主创新；
  7. active disambiguation 延期，不与第一阶段同时实现；
  8. direct classifier + auxiliary future loss 是硬性主基线；若 full CTT 无法优于它，主方法 claim 失败。
- 被取代内容：D-010 不再是活动核心方法；D-016 的未决 ground-truth 问题迁入 HC-001/002/003/006。D-001、D-002、D-004、D-009、D-011 的 observation/world 分离、VP 边界、无 RGB reconstruction、文献核验和 deterministic executor 纪律继续有效。D-003 的稳定 Chart/Place 仅约束表示锚点，不禁止 entity/surface transaction 的 SPLIT/MERGE。
- 归档：旧工作树已提交并推送至 branch archive/pslm-pre-ctt-20260904，commit eba4339；原始 source artifacts 未删除。
- 影响：活动 schema、配置、实验合同、WBS、训练和评估全部切换到 CTT；任何旧 PPT/文档若冲突，只作为 provenance。
- 是否接触 test 信息：否；目前没有 CTT test 结果。
- 验证方式：先完成 P0/P1 contract fixtures，再运行 P2 hard-condition paired experiment；Gate A 失败时停止 CTT 顶级方法 claim。

## D-018 — CPMT 北极星与首篇范围收敛

- 日期：2026-09-05
- 状态：accepted
- 用户确认：北极星“机器人从未来多视角证据中学习应该保留、绑定、创建、重激活、重连还是撤回世界记忆；训练时执行候选事务，在线时不看未来”符合真正想做的方向。
- 背景：D-017 后的讨论一度把 CTL 泛化为跨领域 structured-state learning，增加第二任务、理论和多套 benchmark；这偏离原始 embodied/projective spatial memory 动机并使单人项目失控。
- 决策：
  1. 完整方法命名为 Counterfactual Projective Memory Transactions（CPMT）；
  2. Counterfactual Transaction Learning（CTL）是 CPMT 内唯一主学习创新；
  3. Projective Node Orbit 是具身表征基础，Versioned Deterministic Executor 是执行基础，不预先单列为主创新；
  4. transaction 使用 intent/template 两级语言：PRESERVE/NOOP，ASSOCIATE/BIND|REACTIVATE，EXPAND/BIRTH，REVISE/RELINK|RETRACT|SPLIT|MERGE；
  5. REPLACE 是 RETRACT+BIRTH 复合程序；QUARANTINE 是不修改 persistent world 的 deterministic commit wrapper；
  6. energy 明确拆为 now、future、edit、growth、collateral、illegal，并形成 temperature hindsight posterior；
  7. online \(q_\theta\) 使用当前/历史 state、regions 和 actions，不访问 future；
  8. 流程从 P0–P7 收敛为 M0 executor、M1 hard-condition、M2 embodied visual online、M3 one external/paper；
  9. 首篇排除 active disambiguation、第二应用领域、learned candidate generator、端到端 backbone 和导航。
- 硬性主对照：Full CPMT vs direct+future-loss；Full CPMT vs future-scorer-without-execution。
- 影响：D-017 的 executable counterfactual 核心继续有效，但 CTT 不再作为完整系统名；旧阶段编号和扁平事务枚举被取代。活动 contract version 升为 cpmt-0.2。
- 是否接触 test 信息：否；项目仍无 CPMT 实验结果。
- 验证方式：M1 未通过时停止 CPMT learning claim，不通过新增模块挽救。

## D-019 — Identity lifecycle 与版本关闭分离

- 日期：2026-09-05
- 状态：accepted
- 用户确认：接受 candidate、confirmed、dormant、retracted、alias 五态规则及对应 BIND/REACTIVATE 约束。
- 决策：
  1. identity lifecycle 固定为 candidate、confirmed、dormant、retracted、alias；
  2. node/edge version 是否关闭只由 valid_to 表示，不再使用 lifecycle=closed；
  3. BIND 仅可指向 candidate/confirmed，REACTIVATE 仅可指向 dormant；
  4. retracted identity 不可直接 REACTIVATE；若原撤回事务错误，必须显式回滚；
  5. executor 不按观察次数隐式把 candidate 升为 confirmed，状态升级必须出现在 program 中；
  6. 每个 identity 可有多个历史 version record，以 node_version_id 区分；同一时刻至多一个 open version。
- 备选方案：沿用 closed lifecycle；或把 dormant 作为派生缓存状态。两者都会混淆身份状态与版本结束，拒绝。
- 影响：world graph schema 增加 node_version_id/edge_version_id；C00–C03 executor 与 fixtures 按上述规则实现。confirmed→dormant 的触发机制仍留在 HC-001。
- 是否接触 test 信息：否；当前只有合同设计。
- 验证方式：BIND/REACTIVATE 正反例、wrong-lifecycle、历史版本保留和 atomic rollback 单元测试。

## D-020 — Candidate 确认、Dormant 维护与白话说明

- 日期：2026-09-05
- 状态：accepted
- 用户确认：接受 candidate→confirmed 与 confirmed→dormant 的推荐规则，并要求当前及后续全部概念和方法附带白话说明。
- 决策：
  1. BIRTH 只创建 candidate；
  2. 至少获得第二条独立视角支持后，BIND program 才可显式 SET_LIFECYCLE(candidate→confirmed)；
  3. executor 不自动确认；M0 先检查两个不同 evidence IDs，视角独立性的数值阈值留到 M2 validation 冻结；
  4. confirmed→dormant 是不参与 CTL 竞争的确定性维护，不代表对象消失，不删除 identity、latent、evidence 或历史；
  5. 连续 K 步未观测时可进入 dormant，K 只能由 train/validation 选择；
  6. 任何新术语、公式、模块或实验必须同时给出中文白话解释，并标明实现/验证状态。
- 影响：增加 candidate promotion 正反例、versioned dormancy maintenance 与项目白话词典；不增加新的学习型事务。
- 是否接触 test 信息：否；K 和视角阈值尚未选择。
- 验证方式：重复 evidence 不得确认 candidate；独立 evidence 的显式 BIND 可确认；dormancy 不丢历史且可由 REACTIVATE 恢复。

## D-021 — SPLIT/MERGE 身份与证据继承

- 日期：2026-09-05
- 状态：accepted
- 用户确认：接受 SPLIT 关闭错误混合身份并创建新后继，以及 MERGE 保留最早 confirmed ID 的不对称规则。
- 决策：
  1. SPLIT 将旧 conflated node 标为 retracted 并关闭版本，不物理删除；
  2. SPLIT 创建至少两个新 successor IDs，默认 lifecycle=candidate，且 predecessor_ids 指向旧 node_version_id；
  3. 旧 evidence 与本次 program evidence 必须在 successors 间恰好分配一次；不得丢失或重复；
  4. successor latent_refs 必须彼此分离，且不得直接继承旧 conflated aggregate latent；
  5. MERGE 至少需要一个 confirmed source；canonical ID 按最早 valid_from、再按 node_id 字典序确定；
  6. MERGE 关闭全部 source versions，打开 canonical 新版本；其他 IDs 打开 alias 版本并指向 canonical；
  7. canonical 新版本保留全部 source/program evidence 和 source latents；历史版本、provenance 与 alias 均保留。
- 白话：SPLIT 是把一个混错的档案作废后重建两个新档案；MERGE 是把同一个人的重复档案归到最早的正式档案名下。
- 影响：实现 C04/C05 fixtures 与 executor；Projective Node Orbit 尚未实现，因此 latent 继承目前只检查引用集合，不声称已学会 canonical latent。
- 是否接触 test 信息：否；fixtures 仍为 human_draft。
- 验证方式：证据 partition、canonical deterministic tie-break、alias、历史版本和 atomic rejection 测试。

## D-022 — RETRACT/REPLACE 与可靠否定证据

- 日期：2026-09-05
- 状态：accepted
- 用户确认：接受 RETRACT 默认作用于世界事实而非对象身份，以及可见、可靠、重复的否定证据条件。
- 决策：
  1. 普通 absence 只 RETRACT fact/edge version，例如关闭 chair-A located_at old-place；
  2. 对象 identity 保留；没有已知位置时可继续 confirmed，之后由非学习型维护进入 dormant；
  3. node-level RETRACT 仅用于已证实的误建、幻觉或错误身份，不由普通 visible-empty 触发；
  4. REPLACE 严格编译为 RETRACT(old fact)+BIRTH(new identity)+ADD(new fact)，不物理删除旧对象；
  5. edge RETRACT 至少需要两条 online visible_empty evidence，来自不同 time/view key，且 pose/depth 有效、reliability 达到预设门槛；
  6. 两条否定证据之间若出现支持原 fact 的正面 observation，则证据链失效；
  7. M0 使用 reliability=1 的 oracle evidence；M2 数值阈值只由 train/validation 冻结。
- 白话：没在旧位置看见椅子，只能说明“椅子仍在旧位置”这句话过期，不能说明椅子从世界上消失。
- 影响：实现 C06 RELINK-vs-REPLACE、C07 RETRACT-vs-occlusion；node-level RETRACT 保持显式未实现。
- 是否接触 test 信息：否；fixtures 为 human_draft，未用未来或 test 选规则。
- 验证方式：可见空场景合法撤回事实；遮挡、坏 pose/depth、低可靠度、重复同一视角或中间正面观测必须拒绝。

## D-023 — QUARANTINE 保存可检索的暂定认知

- 日期：2026-09-05
- 状态：accepted
- 用户确认：看不清的证据仍应形成低权重粗略认知，并允许以后与新证据关联；不能因暂时无法提交事务而丢弃。
- 决策：
  1. “看不清”定义为多个合法事务解释仍无法可靠区分，不等同于图像模糊；
  2. 当 top posterior 未达到 commit probability，或 top-1/top-2 margin 小于门槛时，确定性 wrapper 选择 QUARANTINE；
  3. QUARANTINE 不修改 persistent world，而是写入独立 pending memory；
  4. pending record 保存原始 evidence、粗略 latent/spatial/semantic retrieval keys、低权重支持和候选假设历史；
  5. 只有 relevant 且 can_disambiguate 的观察机会才累计 K；没有重新观察相关区域时不计时；
  6. 达到 K 次有效机会仍未跨过 commit gate 时，active_pending 转为 archived_unresolved；不删除、不宣称事实为假；
  7. active_pending 与 archived_unresolved 都可被后续证据检索；新相关证据可重新激活 archived record；
  8. 正式 transaction 消费 pending evidence 时必须显式引用其 evidence IDs，并记录 consumed_by_transaction；
  9. 完全重复的 time/view 证据保留审计记录但不增加独立支持；更一般的相关性权重留到 M2 validation；
  10. commit probability、margin 与 K 均只能在 train/validation 冻结，不使用 test 选择。
- 白话：模糊印象先写进可搜索的草稿记忆，影响很小但不消失；以后再看到相关东西时可以重新对照。多次真正有机会看清却仍无法决定，只把它移入低优先级档案，不改正式世界。
- 影响：新增 pending-memory schema 与 deterministic quarantine manager；QUARANTINE 仍不是可学习 world transaction，不扩大 CTL 主创新。
- 是否接触 test 信息：否；数值门槛尚未选择，C08–C11 仍为 human_draft。
- 验证方式：world hash 不变、无关帧不累计 K、归档记录可检索/重激活、重复视角不增加支持、正式事务消费时 evidence/provenance 完整。

## D-024 — Graph-equivalence 身份对应规则

- 日期：2026-09-05
- 状态：accepted
- 用户确认：接受修订后的第 2 条和第 3 条；旧身份不再一律要求字符串 ID 相同，新身份双射严格但允许不同视角 latent 存在投影容差。
- 决策：
  1. 被比较 programs 必须从同一 immutable base world version 合法执行；
  2. 旧身份按 anchored 与显式 exchangeable 分开：anchored/unlisted IDs 固定，只有 fixture/policy 明确声明且整体对称的集合允许内部一一置换；
  3. 暂时分不清、但未来可能区分的旧身份不是 graph-equivalent，而是 epistemic ambiguity，保留多假设或 QUARANTINE；
  4. 相对共同 base 新创建、无外部 identity anchor 的 local IDs 允许 alpha-renaming，但必须建立覆盖全部新身份的严格双射；
  5. 新身份不能映射到旧身份，不允许多对一或一对多；外部锚定的新 ID 必须固定；
  6. 同一映射必须在整个结果中全局一致；不能在不同关系、时间或引用中改变对应对象；
  7. 双射结构是严格离散合同；不同视角 raw latent 不要求相等，未来由 pose/visibility-conditioned Projective Node Orbit 在 validation 冻结的容差内判断；
  8. M0 只实现 identity-correspondence validator，不声称已实现跨视角 latent equivalence。
- 白话：旧档案如果有身份锚点就不能换人；完全对称且明确声明的旧档案可以交换编号。新档案叫什么不重要，但建了几个、谁对应谁必须严格，而且新档案不能冒充旧档案。正面和侧面看起来可以不同，但以后必须由同一个世界身份解释。
- 影响：新增 equivalence policy schema 与 identity mapping validator；完整 graph field canonicalization 等第 4 条后再实现。
- 是否接触 test 信息：否；Projective 容差尚未选择，不能使用 test 调整。
- 验证方式：固定旧 ID 不可交换、显式 exchangeable 集合内可置换、新 ID 改名可接受、新旧互换及非双射必须拒绝。

## D-025 — Conservative canonical memory-state equality

- 日期：2026-09-05
- 状态：accepted
- 用户确认：graph-equivalence 不是要求世界跨时间保持相同，也不能妨碍后续扩张或修订；接受将它限定为同一 base、同一决策时刻下候选执行结果的保守规范化比较。
- 决策：
  1. equivalence 只用于消除候选程序的新 local ID 命名、审计编号和无意义序列化顺序差异，以避免任意单标签监督、重复候选和 executor 非确定性；
  2. 它只横向比较从同一 immutable base 分叉得到的 post-edit states，不比较 (S_t) 与 (S_{t+1})，不限制新证据到来后的 BIRTH/RELINK/RETRACT 等版本化修改；
  3. D-024 身份映射后，lifecycle、node/edge version history、事实与关系、evidence/latent refs 归属、protected state 和 pending state 必须一致；
  4. 新 local identity/edge 名称、transaction/operation ID、graph hash、transaction log 名称和列表排列可从比较视图中规范化，但原始记录仍为审计保留；
  5. 同一节点内部的不同视角 raw latents 可以数值不同；但同一次候选分叉中 evidence/latent refs 的节点归属必须一致；
  6. finite-horizon projective similarity 永远不定义 graph equivalence，只进入 CTL 的 (D_{future}) 候选能量；
  7. 只要差异可能影响未来 BIND/BIRTH/RELINK/RETRACT，就保留为不同候选假设；不确定时使用 posterior/QUARANTINE，不以 equivalence 提前合并。
- 白话：这里只合并“同一本档案换了编号或排版”的情况，不合并“现在看起来一样、以后可能不同”的两种世界解释。世界下一时刻仍然可以照常扩张和修订。
- 对 D-024 的澄清：Projective Node Orbit 可以解释一个节点内部的跨视角 latent 差异，但 projective tolerance 不用于宣布两个候选世界相同。
- 影响：实现 canonical memory-state equality；HC-001 关闭。M1 的 future scorer 继续独立评分每个非等价候选。
- 是否接触 test 信息：否；规则由状态充分性与未来可修订性确定，未根据 test 结果调节。
- 验证方式：改名/重排/审计 ID 差异可接受；lifecycle、evidence、latent assignment、protected 或 pending 差异必须拒绝；声明 exchangeable 只允许身份配对，不能掩盖状态差异；future projection 不得出现在 equivalence policy 中。

## D-026 — 保留即时在线判断

- 日期：2026-09-05
- 状态：accepted
- 用户确认：“可以，保留当前的及时判断吧”。
- 决策：主设置保留即时判断。时刻 t 的在线模型只使用截至 t 已获得的记忆、观测和历史动作，不预先输入真实 t+1 图像，也不统一等待下一帧再提交 t 的决定。
- 后续更新：t+1 观测真正到来后，可以形成新的判断并按现有版本机制修订记忆；不能将这次修订计作 t 时刻已经正确。即时判断仍允许 D-023 的 QUARANTINE，不要求证据不足时强行提交世界事务。
- 训练边界：未来观测可以形成 hindsight teacher 监督，不能进入在线学生在 t 时刻的输入；延迟一帧对照暂不加入当前实验范围。
- 白话：现在先根据已经看见的东西判断；拿不准就保存暂定认知。下一眼看清以后再改档案，但不把后来的理解冒充成当时已经知道。
- 影响：明确 D-018 的在线时间边界；HC-003 部分确认。实际/计划 future pose 的来源、horizon、mask 与 episode 尾部策略仍未由本条确认。
- 是否接触 test 信息：否。
- 实现/验证状态：本次仅同步决策、说明与配置；在线模型和输入防泄漏检查尚未实现，不新增方法效果结论。

## D-027 — 启动 CUDA 上的 CTL 受控开发学习实验

- 日期：2026-09-05
- 状态：accepted（开发执行授权；数值配置 provisional）
- 用户授权：“CUDA里面有4070LAPTOP，然后现在开始CTL学习实验吧”。
- 决策：在现有 executor 之上实现并运行 BIND/BIRTH/RELINK 的合成空间学习闭环；加入 direct classifier、direct+future loss、future scorer without execution；只用 train/validation，不运行正式 test。
- 开发假设：解析三位置投影、实际合成相机序列、H=3、约 25% 组标签、三个随机种子；这些是低成本工程默认值，不替代 HC-003/005/006/007/008 的正式人工冻结。
- 影响：解除 EXECUTE 中“只做 M0、不训练”的旧阶段限制，仅允许 M1-development；不得据开发结果宣布正式 M1 go/no-go、完整 CPMT 有效或 PNO 已实现。正式 M1 失败停止主 claim 的规则不变。
- 公平性限制：CTL 教师有已知解析投影；无执行对照需学习结果预测且有额外参数/更新，不能把两者差异直接解释为执行机制的独立收益。
- 白话：先让小网络真的开始学，并诚实比较；这次相当于实验台联调，不是论文成绩单。
- 是否接触 test 信息：否；开发入口拒绝 test。
- 验证方式：既有合同测试、输入防泄漏、配对不可辨识检查、真实 CUDA 训练及完整运行审计。详见实验目录 DEVELOPMENT.md 和后续结果记录。

## D-028 — 公开具身数据试点与算力审计建议

- 日期：2026-09-05
- 状态：proposed（讨论已记录；数据选型、试点执行范围与云预算尚未确认）
- 用户意向：认为当前任务可能过于简单，希望利用公开数据，并表示可以租服务器；随后要求将任务进度沉淀到文件以便新开对话。
- 已知证据：D-027 中直接分类达到当前配对数据的信息上限，CTL 无相对优势；这不能推出扩大数据一定有效，也不是正式 M1 判决。
- 建议：ProcTHOR＋AI2-THOR 作为受控主环境候选，3RScan 作为现实重访验证候选；先审计少量开发场景，不同时搭建多个模拟平台。
- 建议交付：版本/许可/字段核对、连续样本可视化、在线与审计信息隔离、候选世界投影接口、渲染/缓存/训练资源测量。5–10 个房屋为未冻结建议。
- 算力边界：本地 4070 Laptop 约 8 GiB 已验证 CUDA；单卡 24 GB、32–64 GB RAM Linux 是未实测的云规格建议，不是购买授权、价格或容量保证。未租服务器、未下载公开大数据、未开始公开场景训练。
- 方法边界：仍须对齐教师评分与评价、匹配对照知识条件；公开数据不自动提供 CTL 事务样本或实现 PNO。数据可行性准备不绕过正式 M1 gate，也不修改 stop rule。
- 白话：先借公开房间做几道真正贴近空间记忆的题，确认数据能用且知道成本，再决定投入；不是靠租更大 GPU 证明创新。
- 是否接触 test 信息：否；仅检索公开介绍/接口，未读取 test 样本。来源与限制见活动实验 DATASETS.md。
- 影响：仅记录候选方案和交接，不改变已有 accepted 方法决策；下一次需研究者确认试点范围及任何云支出。

### D-028 后续讨论补充 — 单房间数据与投影闭环

- 日期：2026-09-05；仍为 proposed，不修改 D-028 的确认状态。
- 用户追问四项未实现工作如何排序，并要求保存助手解释；本次请求仅授权文档沉淀。
- 细化建议：先一个公开训练场景中的房间，制作重见/首次发现/移动后三类连续案例；验证接口后再决定是否扩至原提案 5–10 房屋。
- 顺序：最小数据与固定几何投影接口 → 教师评分审计 → 冻结并执行正式 M1 → 有支持后做 PNO/视觉整合与长期记忆验证。
- 边界：最小投影器不是完整 PNO；真值与在线记忆隔离；不通过视觉复杂度掩盖教师目标或基线知识不公平；不跳过 M1 stop rule。
- 下一次交付建议：三类可视化案例、候选世界/教师评分、未解决问题及实测算力。用户决定场景和偏好是否符合研究意图。
- 当前执行状态：未开始公开数据采集/投影实现/新训练，未租服务器；只补充交接记录。
- 白话：先能看懂真实题目、检查老师如何评价几个世界，再投入模型学习；不是四项工程一起开工。

## D-029 — 单一追加式实验记录与文档职责收敛

- 日期：2026-09-05；状态：accepted。
- 用户要求：审计现有工作区，不要每个新对话加文件；在一个实验记录文件上持续追加并追踪进度。
- 决策：复用 EXECUTE.md 为唯一“当前看板＋事件历史”；不新建 RUNS/STATUS/TODO 等第二入口。普通实验、讨论、失败排查、导师反馈都追加这里。
- 文件职责：README 保持稳定介绍；旧长交接缩为固定链接；人工确认首页仅作索引；详细方法合同/数据规格和白话词典只在内容实质改变时更新，不跟着每个对话同步进度。
- 决策日志：保留既有 D 条目和原始理由，重要接受/修改/否决才新增 D；普通聊天不再编号成研究决策。D-028 仍 proposed，本条不批准试点或云支出。
- 历史与工程：不删 source artifacts/归档/既有报告/运行产物。真实 run 仍单独保存配置、指标、失败、代码快照和权重；用户确需对外独立报告时允许导出并在实验记录登记。
- 与旧规则关系：收紧 D-015 的单入口要求，替代多处同步交接/实时状态以及每周默认新建报告的流程；不改变 CPMT 方法、M0–M3 阶段门或研究 stop rule。
- 审计澄清：D-003 的旧 split/merge 范围按 D-018/D-021 理解；这是索引历史澄清，不新增方法选择。修正合同中“尚未实现训练/仅 M0”的过期表述。
- 验证：活动 Markdown 链接、文件总数、受保护代码/来源/输出及其他项目文档哈希；详细结果在 EXECUTE 的 LOG-004。没有重新训练或接触 test。
- 白话：以后只翻同一本实验本子；每次记做了什么、证据在哪、失败在哪、下一步是什么，不再到几个页面拼进度。

## D-030 — 正式 M1 v1 的 pre-test lock candidate

- 日期：2026-09-06
- 状态：proposed；用户已接受单房间三画面与 BIND/BIRTH/RELINK 语义并要求开始下一步，但尚未逐项确认本条数值，因此不得写成 accepted/frozen。
- 背景：LOG-005 已证明单房间 RGB/depth/pose、候选真实执行和 hindsight 教师接口可工作，但 D-027 只有四方法、饱和三位置数据和单步指标，不能完成正式 M1 go/no-go。下一步必须先固定能排除 direct+future loss 与 no-execution 解释的合同，而不是扩到 PNO/M2 或租服务器。
- 候选决策：
  1. 固定 A–F 六方法；A–E 共享 online encoder、输入、split 和学生更新预算，C 独立合理调参，E 的额外 scorer 资源明报，F 仅为 K 内 oracle upper bound；
  2. A/D/F 共用 deterministic K=16；覆盖八种原子事务，REPLACE/QUARANTINE 保持既有语义；非法候选保留 failure 并在 posterior 前 mask；
  3. future 来自实际已执行轨迹，主 H=3、报告 H=1/5；按有效 pose/visibility mask，online 与 future cache 物理隔离；
  4. 教师能量权重拟固定 now/future/edit/growth/collateral=1/1/0.1/0.25/10，illegal 为正无穷 mask，temperature=0.25；
  5. C00–C11 每 family 拟使用 1000/200/200 train/validation/test paired groups，联合 group key 不跨 split，每 family test support≥200；正式 test 仍不生成/不读取；
  6. 主设置为 10% transaction labels，另报 0/1/10/100%；五个 formal seeds=7/19/31/43/59；
  7. A 对 C/E 均须 graph correctness 绝对 +3 percentage points，且 20-step contamination 每 100 决策减少 2，校正后 95% CI 排除零；false-birth/collateral 每 100 决策非劣 margin 为 1/0.5，invariant violation=0；
  8. candidate coverage@16 总体≥98%、每 family≥95%；paired stratified bootstrap 10,000 次，A–C/A–E 用 Holm–Bonferroni；
  9. 本地优先，单 run 2 小时上限；新 BugCheck 停止长 run；云预算当前授权 AUD 0。
- 白话：这份候选把“什么结果才值得继续”提前写死。输入是同一组空间记忆题和六种方法，输出是带单位、置信区间和安全门槛的 go/no-go。例如只提高分类准确率、却没有减少连续记忆污染，仍判失败。它不等于 M1 已冻结、test 已运行或 CTL 已有效。
- 备选方案：等 formal validation 后再选 horizon/能量/门槛；拒绝，因为选择空间过大且容易把验证集反馈混入核心机制。也可现在扩大视觉/PNO；拒绝，因为会绕过 M1 stop rule。
- 原因：数值来自既有合同、D-027 开发尺度与已人工审阅的 LOG-005 教师接口，不来自封存 test；优先用绝对、可解释的图错误单位，避免 composite score 掩盖 safety。
- 影响：新增机器可读配置与校验器；开发 harness 接入 D/F，但旧四方法 run 不回写。只有用户接受且 generator/metric/leakage validation 通过后，才能将状态改为 frozen_pretest、记录哈希并考虑生成 test。
- 是否接触 test 信息：否；`test_access=false`，未生成正式 M1 test。
- 验证方式：协议负例测试、A–F 接线测试、配置 canonical SHA256；后续仍需完成 C00–C11 paired generator、20-step metrics、统计实现和 full dry-run。

## D-031 — M1 Core 与 Full CPMT 命名边界及 v1 冻结

- 日期：2026-09-06
- 状态：accepted。
- 用户确认：“可以，你修改完了命名然后启动下一步。”此前用户已审阅 D-030 的 M1 v1 数值和关于 world node/Projective Node Orbit 尚未实现的澄清。
- 决策：
  1. 接受 D-030 的 M1 v1 future、split、A–F、公平预算、指标、门槛和本地优先设置；机器配置状态改为 `frozen_pretest`；
  2. M1 的 A 正式命名为 `CPMT-CTL Core` / `cpmt_ctl_core`，表示在固定解析表征上检验 executed post-world hindsight supervision；
  3. `Full CPMT` 只指同时包含 Projective Node Orbit、versioned world graph、deterministic executor 与 CTL 的完整 M2 系统；
  4. 当前 world graph 节点/版本/证据结构已实现，但 canonical world latent、真实 observation-region transport 和 PNO 尚未实现，不得用 M1 名称造成已完成的印象；
  5. 冻结不等于解封 test：下一步只实现并验证 C00–C11 train/validation paired generator、20-step metrics、bootstrap 和 leakage audit；通过后另记 test manifest/hash 与解封事件。
- 白话：最终研究方向仍是包含世界节点跨视角表征的 Full CPMT；现在只是先考 CTL 这台“档案修改发动机”。输入是固定解析 world-node 表征，输出是事务学习是否胜过 C/E；它不是完整视觉系统。只有发动机通过 M1，才把 PNO 这套“同一世界节点在不同视角下长什么样”的表征接上。
- 原因：避免把已经实现的 graph/executor/玩具投影与尚未实现的 PNO 混在同一个 Full 名称下，也避免 M1 失败后仍靠表征扩张寻找正结果。
- 影响：活动 M1 配置、方法 ID、表格、测试和 manifest 模板统一重命名；历史 D-027/旧输出名称保留为当时事实。D-030 从 proposed 转为 accepted by D-031。
- 是否接触 test 信息：否；formal M1 test 未生成，配置仍 `test_access=false`。
- 验证方式：全库活动文档命名搜索、A–F smoke、配置负例和全套单元测试。冻结配置 canonical SHA256 为 `fa09da245047cbe0399cac49049357173700301565dcab53b452da4682c00287`，文件 SHA256 为 `d793770f1cbe6afb0f364c50135c9824fbd105010daa2514d5590617c2d5f244`。

## D-032 — EXECUTE 事件日志的记录粒度

- 日期：2026-09-06
- 状态：accepted。
- 用户确认：只有产出实验结果或发生架构代码变更时才写入 EXECUTE 的历史 LOG；普通对话不必逐轮记录。
- 决策：EXECUTE 继续作为唯一的当前看板和实验/架构事件日志，但不再为普通讨论、状态问答或没有形成结果的日常调试追加 LOG。产生可复查的实验结果、架构实质变化，或有必要保留失败产物的 run 时，才追加一条事件记录；不为同一事项另建 STATUS、TODO、周报或对话交接文件。
- 白话：这条规则解决“日志被每轮聊天淹没”的问题。输入是一次工作事件，输出是“只更新看板”或“追加一条 LOG”的选择；例如修改候选生成架构并跑出 80 个 validation 决策，应追加 LOG，而只是解释 F oracle 的含义不需要。它不等于丢弃机器 run 失败、不等于删除历史记录，也不改变正式实验必须保存完整 manifest 的要求。
- 原因：让 EXECUTE 保留真正影响复现和下一步判断的证据，同时避免把对话流水账当研究产物。
- 影响：D-029 关于“唯一入口、不按对话建文件”的部分继续有效；其中要求普通讨论一律追加 EXECUTE 的粒度被本条取代。AGENTS 与 EXECUTE 文件职责同步更新。
- 是否接触 test 信息：否。
- 验证方式：后续记录审查；本次 LOG-013 因同时包含候选架构变化与 validation 开发审计结果，符合追加条件。

## D-033 — 云支出改为操作者控制

- 日期：2026-09-06
- 状态：accepted。
- 用户确认：“不用加那个限制了，我就算用也是用 AUTODL 在那里开启那里的实例跑的，我还有定时关闭的习惯。”
- 背景：D-030 设 `cloud_spend_authorized_aud = 0`，且 `validate_m1_protocol` 以 `== 0` 强制校验。由于几乎所有生成与训练入口都先调用该校验，任何非零额度会让整条流程直接抛异常，因此该字段实际不是预算记录而是一道全局开关。用户的实际用法是在 AutoDL 手动开实例、按量计费并设定时关机，成本已由人工控制。
- 决策：
  1. 移除 `cloud_spend_authorized_aud == 0` 的硬性拦截；协议改为**记录**授权而非据此阻断；
  2. `cloud_spend_authorized_aud` 允许为 `null`（操作者控制、未设上限）或非负数值；
  3. 新增必填字段 `cloud_spend_control`，以文字说明成本由谁、以何种方式控制，防止该段退化成无意义的占位；
  4. `policy` 改为 `operator_controlled_cloud_instances`。
- 备选方案：把额度改为某个具体数字并保留上限校验；拒绝，因为真实成本发生在 AutoDL 控制台而非本仓库，仓库里的数字无法约束实际支出，只会制造已受控的假象。
- 原因：这道闸门原本用于防止自动化流程在无人确认时产生费用；在手动开实例加定时关机的工作流下该风险不存在，而闸门的副作用是阻断全部流程。
- 影响：`configs/m1_hard_condition.json` 的 `resources` 段与 `src/cpmt/m1_protocol.py` 的校验同步更新，protocol sha256 随之改变。**`formal_run_wall_time_limit_hours = 2` 与 `stop_on_new_host_bugcheck = true` 两条不变**；后者在本机三天三次内核态 bugcheck 后仍然适用，长 run 应在硬件判定稳定后进行（见 LOG-015 环境/硬件定位）。
- 是否接触 test 信息：否；`test_access` 仍为 false，未生成 test。
- 验证方式：`load_and_validate` 通过；`cloud_spend_authorized_aud` 为负数或 `cloud_spend_control` 缺失时均被拒绝；全套 11 个测试模块通过。

## D-034 — M1-v2 的可达上限、局部恢复与强 no-execution 对照

- 日期：2026-09-06
- 状态：accepted。
- 用户确认：“可以，很好，按照你的来”“可以，现在开始你的下一步”。用户随后要求解释为何 Khronos 式全局慢路径仍留在 M2，并接受 M1 只前移最小局部恢复、M2 再做全局 reconciliation 的边界。
- 背景：M1-v1 的 train/validation 报告为 `formal_run=false` 且 test 始终封存。诊断发现：(a) history-exact final 会把已经由版本事务修正的 active world 永久判错；(b) exact ambiguity 后没有有意构造的再观察与补偿事务，无法测量 D-026 已允许的后续更新；(c) E 只在带标签的参考候选 descriptor 上回归未来，部署评分的其余候选是零监督输入；(d) sibling 1 的 counterfactual future 曾按 primary policy 前进却与 contrast reference 比较；(e) commit gate 使用未校准的 smoke 数值；(f)结果导出只记录 export 时的 HEAD，不能证明生成与训练代码版本。
- 决策：
  1. M1-v1 作为诊断性历史结果保留，不覆盖、不重新解释为通过。活动协议升级为 `m1-hard-condition-v2`、新 dataset/runner schema，并在重新冻结前保持 `pretest_lock_candidate`；test 继续不生成、不读取。
  2. 正式模型改动前先运行 observable-information oracle：可辨步骤使用 audit oracle，exact ambiguity 的两个 sibling 强制采用同一个确定性选择，禁止独立随机数造成两个 sibling 同时猜对。它输出当前候选/提交/rollout 下的在线可达上限，不是部署方法。
  3. validation 按 `paired_group_id` 的固定哈希拆成 calibration/report 两半；只在 calibration 半区从预登记网格选择一组 A–E 共用的 commit/quarantine 参数，report 半区只汇报，test 不选择任何设置。commit rate 是一等诊断，不替代 active correctness、contamination 与 safety 指标。
  4. 将“固定范围的在线补偿事务”前移到 M1-v2：exact ambiguity 固定为可恢复的 `RELINK`/`NOOP`，随后实际到达的相关可见证据触发确定性 revisit；仅在固定 lookback 和受影响子图中用同一 K=16 generator 产生补偿候选，并继续通过 versioned executor 关闭错误版本、保留 provenance。A–E 获得相同的触发和候选机会。全图、跨多对象、异步全局 reconciliation 仍属于 M2，不用它掩盖 M1 的监督比较。
  5. 后续修订不回填先前正确性。逐步即时 correctness 保留原时间语义；另报最终 active semantic graph、最终 open-memory support、完整 history exactness、recovery-within-k、time-to-recovery、unresolved quarantine 和 contamination AUC。旧 `post_graph_correctness` 只保留为 history-exact compatibility alias，不再单独代表部署终态。
  6. E 的边界固定为目标构造和候选评分都不执行非参考候选。E 解析 online candidate program 提出的关系查询，并从实际 reference future trajectory 构造所有 K=16 查询的稠密标签；目标构造不得读取这些候选的 `post_graph`，scorer 也不得复用执行得到的 illegal/collateral penalty，只能使用声明成本与程序文本可判定的 protected-touch。C 使用同一结构化 future-relation target 作为 direct auxiliary loss。A 的区别仍是每个候选从 immutable base 真实执行后形成 hindsight posterior；部署时 E 最终选中的单个事务仍按统一 application rule 交给共享 executor 执行，这不等于在评分时展开所有候选世界。
  7. 每次生成、训练和导出分别记录 HEAD、branch、dirty 状态、diff hash、source-tree hash、protocol hash 与 arrays digest。导出时 HEAD 只命名为 `export_commit`，不得冒充数字生成 commit；正式可复现实验必须使用已提交、干净的树。
  8. M1-v2 不引入 PNO、learned candidate generator、active disambiguation、第二领域或全局慢路径；M1-v2 未通过 hard condition 前仍不得进入 M2。
- 白话：这次改动解决“模型当时猜错以后有没有机会改档案，以及 E 是否真是一个没有执行候选的强未来基线”。输入是同一组 20 步空间记忆、固定候选和后来真正到达的观察；输出既有当时是否判断正确，也有之后是否通过新事务把当前世界修回来。例如遮挡时把苹果错连到桌面，下一步看清苹果仍在水槽，系统可以关闭错误位置版本并重新连回水槽，但遮挡时那一步仍记为错。它不等于提前看未来、不等于删除错误 provenance，也不等于在 M1 中加入 Khronos 式全局优化。
- 与旧决策关系：保留 D-026 的即时在线边界；仅对 D-031 的活动 v1 冻结和 EXECUTE 看板中“所有回溯均留到 M2+”作有界替代。D-031 与 M1-v1 数值仍是历史事实，全局慢路径仍按 D-018 的 M1→M2 顺序执行。
- 是否接触 test 信息：否；`test_access=false`，没有生成或读取 M1 test，也不据 test 修改门槛。
- 验证方式：协议负例、E 目标来源扫描、exact paired oracle、分支一致性、唯一补偿 RELINK、active/history 分离、calibration/report group 隔离、provenance round-trip 和全套 train/validation 单元测试；完成 observable upper bound 与 calibration smoke 后才可申请重新冻结。

## D-035 — 独立的 M1-v2 收口流程与记录职责分离

- 日期：2026-09-06
- 状态：accepted。
- 用户确认：“EXECUTE.md 只是试验记录，不是整体的流程……完全可以另起一个流程文件。”
- 背景：`EXECUTE.md` 能追溯“发生了什么”，但不适合快速回答“下一步是什么、什么时候转向或结束”。只靠对话记忆保留分支条件不可审计，也会在新对话中丢失。
- 决策：新建 `experiments/counterfactual_transaction_learning/M1_V2_CLOSEOUT_FLOW.md` 作为 M1-v2 唯一收口流程，只维护阶段顺序、当前指针、诊断分支、可调整项、重新冻结边界和 M1 终止条件。`EXECUTE.md` 继续作为唯一实验/失败/架构结果日志，只保留指向流程的当前阶段链接，不复制流程正文。
- 更新规则：run 前把当前阶段和设置写入流程；run 后数字和失败写 `EXECUTE.md`，流程只移动指针。只调开发细节时更新流程；改方法、数据语义、预算、流程门或终止规则时仍须追加 decision 并同步合同。
- 备选方案：继续只用 `EXECUTE.md` 或新建每日 TODO。前者已证明难以导航；后者会重新制造多个进度入口。因此只允许这一个阶段流程，不为每轮对话生成新计划文件。
- 影响：这是文档职责与执行可见性的变更，不改 CPMT/CTL 方法、A–F、训练预算、门槛、test seal 或 M1→M2 边界。
- 是否接触 test 信息：否；`test_access=false`。
- 验证方式：检查流程、EXECUTE、活动配置和 D-034 的链接/职责不冲突；后续新对话应先读流程当前指针，再读 EXECUTE 最新 LOG。

## D-036 — S1/S2 使用 train/inner-dev，停止消费 validation report

- 日期：2026-09-06。
- 状态：accepted。
- 背景：LOG-022 与最初 S1 runner 已读取 validation report 半区的 relation oracle，并据此决定继续优化 scorer；这与 D-034 的 `report_partition_selects_nothing` 及流程中“S5 才报告一次”冲突。另一方面，scorer 最优步数可能随 train group 数变化，若先在小数据选 steps、再固定到大数据，会把优化与数据效应混在一起；仓库此前也没有真正的 train/inner-dev 接线。
- 决策：S1/S2 的 target、assembly 和 E scorer 选择改用 train 内确定性 SHA-256 留出的一组完整 paired groups，约占 1/5；siblings 及 recovery rows 同进同出。专用 runner 只读 train arrays，不训练 online student、不校准 gate、不跑 causal。scorer steps 与 train groups 做二维扫描；若进入更大规模，仍复扫两个 steps 点。A–E student updates 继续相同，E scorer 额外预算单列。
- validation 处理：已经查看的 4-group validation report 保留为历史开发结果，但不再用于选择方法、checkpoint 或 S5 go/no-go。S5 必须在 S4 预先登记一个与其不重叠的新 validation confirmation group range；calibration 仍只选共享 commit gate，新的 report 半区只汇报一次。正式 test 继续封存。
- 早停边界：held-out relation BCE early stopping 仍为 proposed；除非在 S4 前固定监控集合、最大 steps、评估间隔、patience、最小改善和 checkpoint tie-break，并同步机器 config，否则不得启用。当前先使用有限固定 steps 网格。
- trial 预算：train/inner-dev scorer 曲线不计入 `max_validation_trials_per_method=6`，但所有点都记录。validation 预算保守分配为：历史 smoke 1 次、共享 student updates 最多 2 个新点、C auxiliary weight 最多 3 个登记点。
- 影响：这是 pretest 的数据选择与流程修正，不改 A–F、E 的 no-execution 边界、目标、能量、门槛、candidate K、recovery 或 test。活动 config 暂不改，以便在 S1 只读复用已有 arrays；S4 重新冻结时必须把最终 inner-dev/confirmation 规则写入机器 config，并产生新 protocol hash。
- 是否接触 test 信息：否；没有生成或读取 test。
- 验证方式：inner-dev group 完整性单测、专用 runner source scan、干净提交上的全测；S1 报告必须明确 `validation_arrays_read=false`、`validation_report_partition_accessed=false` 和 `validation_trial_consumed=false`。

## D-037 — S2 先审计只读静态预检，并补齐 60-step 同源锚点

- 日期：2026-09-06。
- 状态：accepted。
- 用户确认：在看到“全 train oracle、静态合法性上界与 60-step 锚点应先于旧 S2 命令”的逐项审查后，用户回复“可以，开始吧”。
- 背景：LOG-026 的 oracle 只统计 1 个 inner-dev paired group/40 个 online rows，不能稳定描述固定 relation target 与 assembly；外部 scratch probe 又提示 raw mismatch 的并列集合常被 executor 判定的非法候选撑大，但其 94.4% 数字直接使用了 `candidate_legal`，只能作为禁止部署的上界。原 S2 只扫 scorer steps {300,1000}，缺少同一份 40-group arrays 上的 60-step 锚点。另经当前 HEAD 核查，主 runner 已有独立 `--scorer-steps`，无需重复修复。
- 决策：
  1. 将 transaction static preflight（事务静态预检）实现为 executor 真正应用 operation 前的只读检查：输入仅为 immutable `prior_world`、candidate program、online evidence 与 protected IDs；输出只允许“已静态拒绝”或“预检通过但执行结果未知”。它检查 graph/header/base-version/duplicate transaction、template-level precondition 和 protected touch，不生成 `post_graph`，也不把“通过”声称为合法。
  2. S2 生成数组同时保存 static-preflight pass/failure 与最终 executor failure；`candidate_legal` 只作为事后审计标签，比较非法召回、合法误拒、剩余非法、effective K、template/failure 分解，以及 relation 最小集合中非法成员的查询数与声明 penalty。当前不得把任何 legality mask 输入 A–E、改变候选选择或改写 teacher。
  3. target-only 与 assembled relation oracle 在全部 selected train online rows 上报告 aggregate 和逐 paired-group 结果；scorer 的泛化指标仍严格分 fitting/inner-dev。inner-dev oracle 只作同范围参照，不再用单 group 数字描述固定 target 的总体质量。
  4. S2 固定为同一份 40-group train arrays 的完整 2×3：train groups {10,40} × scorer steps {60,300,1000}，seed 7。60 是连接 S1 的锚点而非新增可选超参数；train/inner-dev scorer 曲线仍不消耗 validation trial。
- 白话：静态预检解决“一个候选不改世界就已经能看出不合规，却仍被 E 当成便宜答案”的问题。输入是当前版本图、事务文本和此刻可见证据，输出是“现在就能拒绝”或“还不能判断”；例如 BIND 要修改受保护节点可立即拒绝，而 RELINK 指向不存在节点可能先通过、直到真正执行 ADD_EDGE 才失败。它不等于执行候选、不产生候选后世界、不等于 executor 的最终 `candidate_legal`，本轮也不把过滤后的数字冒充 E 成绩。
- 后续边界：若干净 S2 报告证明静态预检有高非法召回、零/近零合法误拒且过滤上界显著改善，是否把它变成 A–E 共享 online admissibility mask 必须另立新 decision、更新方法合同和 protocol hash，并从 S1 重跑；D-037 本身不授权启用。
- 影响：新增只读 executor API、generation audit 字段、全-train/逐 group 诊断与两个 60-step 训练点；不改 A–F、relation target、energy、loss、K、candidate generator、commit gate、recovery、主指标或成功门槛。
- 是否接触 test 信息：否；`test_access=false`，不生成或读取 test，也不读取 validation/report。
- 验证方式：静态预检不改变 base 的单测；protected 冲突应静态拒绝；至少一个 operation-time 失败应“预检通过、执行失败”，证明 pass 不是 legality；生成数组中合法候选不得被静态拒绝；过滤诊断只接收 static-preflight flag；干净提交上全测后才运行 S2。

## D-038 — A–E 共享启用事务静态预检 online admissibility mask

- 日期：2026-09-07。
- 状态：accepted。
- 用户确认：在核对 LOG-028 六点结果、外部复核意见和实现边界后，用户回复“可以，开始执行，接受”。
- 背景：D-037 的 train-only 审计在 40-group、1,600 个 online decisions、25,600 个候选槽上，对 2,552 个 executor-illegal 候选实现静态拒绝召回 1.0、precision 1.0、合法误拒 0、reference pass 1.0。事后过滤使 assembled relation oracle 从 0.7438 升至 0.9525，说明 E 的旧比较被大量只看当前 world/program 就能排除的候选削弱。历史开发 causal 中 A/B/C/D 的非法选择率为 0，而 E 很高，因此该改变主要增强强制主对照 E、缩小而不是放大 A 的优势。
- 决策：
  1. `transaction_static_preflight_v1` 成为 A–E 共用的 online admissibility mask。它只读取 immutable prior world、candidate program、截至当前的 online evidence 和 protected IDs；不得读取 future、candidate post-world、executor failure 或 `candidate_legal`。
  2. 固定 K=16 的槽位、顺序、程序、preflight failure、executor failure、post-world/provenance 审计全部保留，不删除或重排候选。预检拒绝项在 A–E 的训练归一化、online softmax、共享 calibration 与 commit selection 前不可选；reference 必须通过，任何一行不得全部拒绝。
  3. executor 仍从同一 immutable base 真实尝试候选，并分别记录 now、future、edit、growth、collateral 和 illegal。A/D/F 的执行后 illegal 正无穷 mask 不删除；preflight pass 只表示“静态检查尚未拒绝”，不声称执行合法。
  4. `remaining_executor_illegal_candidates`、合法误拒、reference pass、effective K 与 template/failure 分解成为每次 run 的常驻审计。若 residual 非零，必须区分 candidate-generator 缺陷与只能执行后发现的失败，不得把 executor truth 偷喂给 B/C/E。
  5. E 的现有逐关系 masked binary cross-entropy（BCE）训练目标本 decision 不改。S1/S2 只增加判别性/非判别性 BCE 和 reference ranking margin 诊断；若多 seed 复现“总体 BCE 改善而排序变差”，另立 decision 后才能引入候选级排序目标。
- 白话：共享 online admissibility mask 解决“候选不改世界就已经能看出违反版本、前置条件或 protected state，却仍让某个方法为它分配概率”的不公平。输入是当前记忆、事务文本、此刻证据和受保护 ID，输出是保留原 K=16 槽位的允许/拒绝布尔值；例如 BIND 明写要修改 protected node 时，A–E 都在 softmax 前拒绝它。它不等于执行候选、不产生 post-edit world、不保证通过项合法，也不删除失败记录或 provenance。
- 白话：判别性 BCE 诊断解决“总体逐关系损失下降，是否只是学好了对所有候选都一样的容易位置”。输入是 scorer 的 relation logits、真实 reference future、relation mask 和共享预检 mask，输出是能区分候选的位置与其余位置各自的 BCE，以及正确候选相对最佳错误候选的 probability/log-probability margin；例如只有正确 RELINK 支持新位置的坐标属于判别性位置。它只是 planned train/inner-dev 诊断，不改变 loss、不读取 validation/test，也不等于候选级排序方法已经有效。
- 协议影响：dataset version 升为 `m1-paired-latent-worlds-v5-shared-static-preflight`，机器 config 加入 D-038 和 mask 语义并产生新 protocol hash；旧 v4 arrays/report 只保留历史证据，不能冒充新方法结果。保持 target、energy weights、K、candidate generator、recovery、主指标、门槛和 formal seeds 不变。
- 是否接触 test 信息：否；`test_access=false`，本 decision 不生成或读取 validation/test，不训练 student、不校准 gate、不跑 causal。
- 验证方式：protocol validator 锁定 A–E 共享方法集合、pass 语义、reference/all-rejected/illegal-retention 条件；单测验证 mask 后拒绝项概率为 0、reference 通过、K=16 审计仍完整、causal 不会选择静态拒绝项、executor illegal 仍独立；随后在干净服务器提交上全测，重新生成 train arrays 并从 S1 重跑。

## D-039 — M1-v3 合同一致性修复、候选交互架构与全量重跑

- 日期：2026-09-07。
- 状态：accepted。
- 用户确认：用户明确表示“不怕重跑”，要求加入成熟模型重跑；在审阅外部复核对 per-family、C09–C11、now/collateral、E 对称目标、架构对照和成本的意见后回复“可以，开始吧”，并进一步要求删除单次正式运行 2 小时的仓库限制。
- 背景：S4 只读盘点证明活动合同写的是**每个 family**分别生成 train/validation/test=`1000/200/200` paired groups，但现有 CLI 把 `--paired-groups` 当混合总数，连续 rollout 也只实现 C00–C08；coverage gate 又只遍历已出现 family，导致 C09–C11 缺失时仍可能静默通过。这两项是实现偏离既有合同的 conformance bug，不是为了结果而扩大任务。另有两个能量项虽已真实计算，却在当前 fixture 结构下恒为零：`now` 只检查是否有 evidence ref，`collateral` 只检查 protected mutation，而后者已先被 executor 判非法。现有共享候选 MLP 已是逐候选置换等变模型，但没有候选间信息通路；因此“加入成熟模型”的实质是加入 cross-candidate attention，而不是用任意更大网络替换 CTL。
- 决策：
  1. 活动协议升级为 `m1-hard-condition-v3`，dataset 升为 `m1-paired-latent-worlds-v6-conformant-live-energy`，状态保持 `pretest_lock_candidate`。旧 v5 arrays、1000-step 选择和全部报告只保留为历史诊断，不能带入 v6 成绩或预算选择；S1/S2 必须在 v6 上重跑。
  2. `groups_per_family` 是唯一规模语义：train/validation/test 各为 `12×1000=12,000`、`12×200=2,400`、`12×200=2,400` paired groups。生成器必须逐 family 接收/报告计数，连续 20-step rollout 必须实现 C00–C11；coverage gate 的分母固定为配置中的全部 12 个 family，任何 family 缺失即失败。C09–C11 与 CLI 修复按 conformance bug 处理。
  3. `now` 改为候选执行后世界对**当前**有效在线观测的投影 mismatch；无效 pose/depth、遮挡和未观察位置不入分母，因此专门承载几何故障的 C09 上 now 可以按设计为零，不能宣称每个 family 的六项能量都同时有判别信号。`future` 从当前决策之后的下一步开始取 H=3，不能再把当前步重复算入 future。now/future 都按“每方法、每决策、该方法可用的 shared-preflight admitted 候选”分别做 z-score；执行式 teacher 另排除 executor-illegal，no-execution 方法不得借此读取 legality。raw 和 scaled 值同时保存；候选间 spread 为零时 scaled 为零但 raw 仍报告。
  4. protected touch 继续是 executor-illegal，不降级成软惩罚。`collateral` 改为：合法事务是否修改了由当前 online observation/retrieval 在执行任何候选前确定的 evidence-relevant subgraph 之外、且在候选执行前已经存在的 open-memory 事实，取二值 0/1；该 scope 对同一行所有候选相同，不能由候选自己的操作声明把误改目标纳入“相关”从而自我豁免。新建事实仍由 growth 单独计费，避免正确 BIRTH 同一变化被 growth 与 collateral 重复惩罚。逐 family 报非零率与分布。teacher 权重预登记为 now/future/edit/growth/collateral=`1/1/0.1/0.25/1`，illegal 仍为正无穷 mask，temperature=`0.25`。旧 collateral=`10` 从未乘过活信号，不能直接迁移为已验证权重。
  5. teacher health gate 在训练前固定为 reference agreement 总体至少 `0.95`、每 family 至少 `0.90`，并检查非退化 NOOP/事务分布、now/collateral 激活率和 A 的 `10× active semantic + 1× open-memory` 主比较及 `1×/1×` 报告型消融。未过时停止，不得现场调权重；只能把问题归为 fixture/energy mismatch，另立 pre-test decision。
  6. E 与 C 新增 `candidate_scoped_current_relations_v1`。它只从 immutable prior world、当前在线观测和 candidate program 声明形成三项 now 查询：候选动作是否受当前证据支持、其必要参数是否命中当前 query、当前区域是否可靠为空；严禁读取 candidate post-world、executor outcome/legality 或 future。证据分区阈值随协议冻结为 argument cosine `0.8`、novel entity best `<0.6`、split best `[0.55,0.8)`、dormant/merge best/merge second `>=0.8`。E 仍可用既有 candidate-scoped future 目标，但候选评分阶段不执行候选；最终选中的单个事务仍由共享 executor 应用。
  7. 同一份 v6 arrays 预登记两条架构臂：主臂 `cross_candidate_set_transformer_v1` 使用两层 Set Attention Block、model dim 128、4 heads、FFN 256 和共享逐候选输出头；次臂保留 hidden 64、两层的 `shared_candidate_mlp_v1`。每条架构臂都完整运行 A–F，同一臂内 A–E 共享 online encoder/student updates 且参数量差不超过 10%；Set Transformer 是唯一正式 go/no-go 主臂，MLP 是容量稳健性诊断，禁止看结果后在两架构间择优。
  8. scorer/student 的旧 1000-step 选择作废。实现与健康检查通过后，在 train/inner-dev 内为两条架构分别预登记有限预算网格和唯一选择规则，再进入 S5；validation report/test 不参与预算或架构选择。主对比仍只有 A–C、A–E，完整 A–F 和原 effect/safety/CI 门槛不变。
  9. S4 v5 成本参考为：40 groups 生成 42.5 秒、合并数组 11,977,314 bytes、保留分片 12,262,560 bytes；按旧结构线性外推，三 split 共 16,800 groups、705,600 rows、11,289,600 candidate slots、合并数组约 4.685 GiB、含分片约 9.482 GiB、生成约 4.958 小时。这只是 v5 参考，不冒充 v6/Set Transformer benchmark；v6 实现后先跑小规模 train-only 实测再启动正式规模。
  10. 废止 D-030 和 D-033 中的 `formal_run_wall_time_limit_hours=2`。仓库不再设置固定单-run 时长上限，只强制记录 wall-clock、显存/内存、磁盘和失败；云实例继续由操作者手动启停/定时关机，`stop_on_new_host_bugcheck=true` 保留。该变更不解封 test，也不授权脚本购买或续费资源。
- 白话：cross-candidate attention（候选间注意力）解决“16 个候选在同一个 softmax 里竞争，却彼此看不见”的问题。输入是同一时刻的世界上下文和 16 个候选描述，输出是每个候选经过相互比较后的分数。例如两个 RELINK 只差目标位置时，模型可以直接比较它们与其余候选的相对证据。它不等于 learned candidate generator、不改变 K=16，也不把未来或执行结果喂给在线模型。
- 白话：candidate-scoped current target（候选范围当前目标）解决 E 的 now 仍是残缺代理所造成的不公平。输入是当前能看到的证据和候选自己声明的关系，输出是“该声明与当前观测是否一致”的监督。例如候选声称杯子在桌上、当前可靠观测显示桌面为空，就产生 mismatch。它不执行候选、不查看候选后世界，也不等于 future target。
- 白话：同尺度能量解决“一个 10.0 权重乘到从未非零的量，激活后可能突然压倒 future”的问题。输入是每个候选的原始 now/future mismatch，输出是同一决策内可比较的标准化数和完整 raw 审计。例如所有合法候选的 now 完全相同时，它们的 scaled now 都是 0，不凭空改变排序。它不等于把六项揉成不可解释的总分；六项仍分别保存。
- 备选方案：只跑 Set Transformer、用跨版本 v5-MLP 作对照；拒绝，因为数据和能量同时改变，无法归因。也拒绝保持 collateral=10 后看结果再调，以及沿用旧 1000 steps；两者都把未验证权重或过期预算带进新协议。
- 影响：这是 conformance 修复与预先接受的方法/架构变化的组合；protocol/dataset hash 必须改变，生成器、energy、C/E target、模型、runner、报告和测试全部需实现后从 S1 重跑。它不改变 CPMT/CTL 唯一主张、M1→M2 stop rule、K=16、executor、candidate language、formal seeds、主指标或 test seal。
- 是否接触 test 信息：否；`test_access=false`，成本盘点只读既有 train arrays，没有生成或读取 validation/test。
- 验证方式：protocol 负例先锁住 12-family 分母、对称 now target、live energy、两架构臂和无固定 wall-time cap；随后实现单测验证 C00–C11 皆可产生连续正例、now/collateral 可非零且 protected touch 仍非法、E target 无 post-world 来源、candidate permutation equivariance、A–E 参数量门槛。干净服务器全测与小规模 v6 train-only cost/health benchmark 通过后，才登记并运行新的 S1/S2。

## D-040 — 混合组规模、C10/C11 行为机制与同分母 now 审计

- 日期：2026-09-07。
- 状态：accepted；取代 D-039 的 per-family 乘 12 规模解释、v6 数据版本和仅按 family 名称计数即可通过的实现。
- 用户确认：用户审阅外部逐代码复核后明确回复“可以”，并要求一定修改 C10/C11、审计指标和规模合同。
- 背景：D-039 实现后的本地 12-group 探针揭示三点。(a) 一条 paired group 本身是覆盖 C00–C11 的混合 20-step schedule，故把 `1000/200/200` 再乘 12 没有独立 family-group 含义；真正约束是每个 family 至少获得 200 个独立 test group 支持。(b) C10/C11 只是把普通 BIND 事件重命名，候选和观测生成均不读取对应机制，计数 gate 会把克隆当作覆盖。(c) 首轮比较把不可用的 executed-now 行算作失败、却把 proxy 的同一行算作全候选并列成功，产生 `0.8509 vs 1.0` 的假性强弱差；进一步检查还发现 executed `now` 实际以 reference post-world 为 target，而不是当前传感观测。
- 决策：
  1. 活动协议升为 `m1-hard-condition-v4`，dataset 升为 `m1-paired-latent-worlds-v7-semantic-family-mechanisms`。正式规模固定为 train/validation/test=`1000/200/200` 个**总混合 paired groups**，三 split 合计 1400，不乘 family 数。每个 group 的 causal schedule 必须含全部 12 个 family；manifest 同时报 causal 独立 group support 与因末步无 future 而可能略少的 learning-row group support。test 的每-family 独立 group support 仍至少 200。
  2. C10 必须实现两种平衡行为：暂态 dynamic actor 对应 NOOP，持久 background change 对应 BIND；两者使用相同的当前观测分布，差别只能由之后是否持续形成。C11 必须出现正确必要 BIND 与一个 shared-preflight admitted、executor-legal、确实修改证据范围外既有开放事实的 BIND+collateral 候选；reference 的 collateral=0，对照的 collateral=1。M0 中触碰 protected state 的 corruption 仍作为 illegal 语义测试，但不能冒充 live collateral。
  3. family gate 不再信任标签本身。每次 health run 保存由实际 reference template、观测有效性模式和 legal collateral contrast 形成的行为 fingerprint；要求 C10 同时出现 NOOP/BIND、C11 每行出现 legal collateral contrast，且 12 个 family 的行为 fingerprint 不重复。`scenario_variant` 只作 provenance，不参与 fingerprint，防止再次靠改名通过。
  4. executed `now` 只比较候选后世界与当前有效匿名传感观测，不得读取 reference post-world。可见对象按匿名 appearance、必要时按位置一致性评价；可靠空观测按仍开放的匿名 edge match 评价；无效 pose/depth 或遮挡继续缺失。SPLIT successor 的观测 latent 与 component 对齐，MERGE 的两个 query 都进入 candidate-independent evidence scope，避免正确组合事务被错误记为 now/collateral。
  5. 新增 `current_now_comparability` 常驻审计：proxy 与 executed-now 只在两者均定义的同一行、同一 admitted+legal candidate 集合上分别报告 reference-in-minimum、unique、uniform-tie expected 和 mean tie size，并逐 family 拆分；缺失行单独计数。exact-ambiguity sibling 的 current target/mask/desired 必须完全一致且 reference 不同。该审计不规定“proxy 不得强于 executed now”，因为人为压低强基线会使 A–E 比较失真；它约束的是同分母、无 audit-only reference/future 输入和歧义对不可区分。
  6. 首轮 v6 实测 12 groups/8 workers 为 24.7 秒、合并 arrays 3.96 MB；按旧 16,800 groups 约 9.6 小时/5.5 GB 合并 arrays，而本 decision 的 1400 总混合 groups 线性参考约 48 分钟/0.46 GB。它们是计划参考，不是固定时限；v7 仍先在服务器重新实测后才能登记正式 S1/S2 预算。
- 白话：行为 fingerprint（行为指纹）解决“只把 C01 改名 C10/C11 就通过十二类覆盖”的问题。输入是实际执行后的 reference 类型、传感状态和候选的 legal/collateral 事实，输出是每个 family 的机制摘要及重复检测。例如 C11 必须真的有一个合法但误改无关记忆的候选；它不等于用 family 名称做 one-hot，也不证明模型已经学会避开该候选。
- 白话：同分母 now 审计解决“缺失值在两种方法里被不同计分”的问题。输入是同一批可计算行和共同候选集合，输出是两条 now 通道各自的最小集合覆盖与并列准确率。例如 C09 没有合法几何时只计为 unavailable，不在 A 一侧算错、E 一侧算全并列命中。它不等于限制强基线必须输给 CTL，也不把 executor legality交给在线 E。
- 备选方案：保留 12× 规模；拒绝，因为混合 schedule 已在每个 group 覆盖全部 family，只增加约 12 倍成本而不增加 family 下限。把 C10/C11 仅作统计标签或把 protected illegal 当 collateral；拒绝，因为两者都不能检验登记机制。用 `proxy<=executed` 作硬门；拒绝，因为这是按主方法能力裁剪对照。
- 影响：D-039 的 Set Transformer/MLP 两架构、A–F、能量权重、formal seeds、主门槛和无固定 wall-time cap 保持；scale、family mechanism、now target source、manifest、协议/data hash 全部改变，旧 v6 arrays 不得用于 v7 训练或成绩。
- 是否接触 test 信息：否；只使用 train/validation 生成接口的本地小规模实现探针，未生成或读取正式 test。
- 验证方式：协议负例锁住总混合规模、C10/C11 机制和 now target source；rollout 测试要求 12 个非重复行为指纹、C10 NOOP/BIND 双变体、C11 legal collateral 对照；数组测试要求同分母 now 指标、缺失计数、exact-ambiguity identity 和 audit-only reference/future mutation invariance。随后在干净服务器提交上全测，再单独跑 12-group v7 train-only health/cost benchmark。

## D-041 — current-now 固定自然量程、软后验影响审计与机制切片

- 日期：2026-09-07。
- 状态：accepted；取代 D-039/D-040 中 now 与 future 共用逐决策 z-score 的条款，保留其余规模、family mechanism、架构和主门槛。
- 用户确认：用户审阅退化 z-score、固定量程与“now 是否惰性”的两轮复核后回复“可以”，接受按 CTL 实际蒸馏的完整 posterior 而非只看 argmax 来判定能量项是否参与监督。
- 背景：v7 train-only 探针显示，一行中多数候选的 `now_raw` 几乎完全相同时，逐行 z-score 会把一个很小的绝对偏差放大为数个标准差，并在 C04 抵消本来正确的 future 排序。固定自然量程消除了这类放大；虽然 leave-now-out 前后的 argmax 可以完全相同，完整 teacher posterior 仍发生系统变化。CTL 的主损失是对该软 posterior 的 KL 蒸馏，因此“第一名没变”不能推出“now 没有作用”。把 now 改成 audit-only 还会留下 C/E 独有的 current target，造成新的方法不对称。
- 决策：
  1. 活动协议升为 `m1-hard-condition-v5`，dataset 升为 `m1-paired-latent-worlds-v8-fixed-range-current-energy`，状态保持 `pretest_lock_candidate`。v7 arrays、训练预算和报告只保留为发现数值问题的诊断证据，不进入 v8 训练或成绩；S1/S2 仍须重新选择两架构预算。
  2. executed `now` 不再按同行候选标准差归一化。可见匿名 appearance mismatch 的自然范围为 0–2，appearance 加 place 的联合 mismatch 为 0–4，可靠空观测的 edge mismatch 为 0–1；各自除以 2/4/1 后进入能量，保存 raw、natural range 与 scaled 值。无效/遮挡观测仍为 unavailable 并贡献中性 0，executor-illegal 仍由独立正无穷 mask 排除。`future` 继续逐方法、逐决策 z-score，因为执行式结构计数与 learned relation error 的原始单位不同。
  3. C/E 的 current relation 推理能量使用 `sigmoid(logit)` 与 desired bit 的平均绝对误差，天然落在 0–1；逐关系 binary cross-entropy（BCE，二元交叉熵）仍是 scorer 的训练损失，不用 BCE 的无界数值直接充当 current 能量，也不再对 current error 做同行 z-score。A/D/F 与 C/E 继续使用同一个 `now=1` 权重，不能按某一方法的能力事后裁剪。
  4. 每次 arrays 生成常驻 leave-one-term-out posterior influence audit：对 now、future、edit、growth、collateral 逐项移除后，比较完整 teacher posterior 与消融 posterior 的 total variation（总变差距离）、`KL(full||ablated)`、argmax 改变率、reference 概率变化，并报告 total variation 的 mean/median/p95/max 与超过 0.001/0.01/0.05/0.1 的比例；总体与逐 family 同报。argmax 只是其中一个诊断，不能单独宣告某项活跃或惰性；该 audit 不设效果门、不用于调权重。
  5. 预登记五个互斥机制切片，按固定优先级分配：`exact_online_ambiguity`（生成器标记的歧义 pivot）、`temporal_underdetermination`（C10）、`execution_side_effect_sensitive`（C11）、`current_sensor_unavailable`（C09）和其余 `other_registered_mechanisms`。切片只由生成机制定义，禁止按实测 proxy/model accuracy 设阈值。每片描述性报告 selection accuracy、commit rate、已提交项正确率、决策后 active correctness 与 selected collateral；完整 mixed 20-step causal endpoint 仍是唯一 primary go/no-go 分母。
  6. 预期行为随切片冻结：exact ambiguity 的同输入 sibling references 不同，成对在线单步上限为 0.5 且错误不能追溯抹去；C10 的 transient-NOOP/persistent-BIND 当前观测同分布，在线单步准确率预期约 0.5，主要看 teacher 是否由 future 解析及 causal endpoint；C11 每行应有 admitted+legal collateral contrast；C09 的 executed-now 按构造 unavailable，null now influence 是机制确认而非待补成绩；其余 family 不做事后挑选。
  7. train health gate 新增固定量程审计：所有可用 executed-now scaled 值须在 0–1，且必须与 `raw/natural_range` 一致。posterior influence 的大小只报告不设通过阈值，避免又根据预跑数调出一个“必须有作用”的权重。原 teacher agreement、12-family fingerprint、C10/C11 与 exact-ambiguity 门保持不变。
  8. 冻结 executed-now 的逐 family 预期激活模式：C01/C02/C04/C06/C07/C08 的 leave-now-out mean total variation 预期非零，C00/C03/C05/C09/C10/C11 按生成机制预期为数值零。生成 manifest 必须报告实测非零/零 family 及双向偏离名单；`1e-6` 仅用于吸收保存为 float32 posterior 后约 `1e-8` 量级的重构舍入，不是效果阈值。模式偏离只报警，不进 health gate、不触发调权重。
  9. S1 对 E 的 no-execution current scorer 使用与 executed teacher 相同的 leave-current-out posterior influence 指标、temperature、`now=1` 权重和同一批 fitting/inner-dev online 行，并排报告 total variation、KL、argmax 与 reference 概率变化。C 共享同一 current relation target 作为 auxiliary，但其部署选择没有单独组装 current-energy posterior，因此不虚构 C 的 posterior 消融量。两侧影响不同可以如实保留，不据此裁剪强基线、调权重或设通过门。
- 白话：固定自然量程解决“大家几乎打平时，一点点差异被标准差除法吹成巨大惩罚”的问题。输入是候选后世界对当前传感观测的原始误差，输出是按传感器理论范围缩到 0–1 的 now；例如 appearance 原始误差 0.10 除以 2 后就是 0.05，不会因另外 15 个候选恰好同分而变成 3 个标准差。它不等于删除 now、不等于调大 now 权重，也不改变 future 的跨方法单位对齐。
- 白话：软后验影响审计解决“只看第一名，误以为第二到第十六名的概率变化不参与 CTL”的问题。输入是完整 teacher posterior 和逐项去掉某个能量后的 posterior，输出是两份概率分布的距离、第一名是否改变及正确候选概率变化；例如第一名都还是 SPLIT，但其概率从 0.35 变成 0.60，CTL 收到的蒸馏监督已经明显不同。它只是解释能量项，不等于新增训练损失、显著性检验或权重选择器。
- 白话：机制切片解决“总体平均掩盖某种构造的预期行为，同时又避免看完结果才挑有利 family”的问题。输入是生成器事先写入的 family/ambiguity 机制，输出是五组固定诊断；例如 C10 只因它被定义为当前时刻不可判定而进入 temporal slice，不因某个模型恰好只得 0.5 才进入。它不等于把 family one-hot 喂给模型、不替代 20-step 主指标，也不允许某片的好结果补偿主门失败。
- 白话：now 激活模式审计解决“某个本应有 current 区分力的 family 在正式规模上静默退化为零”的问题。输入是逐 family 的完整 teacher posterior 与去掉 now 后的 posterior，输出是预期零/非零和实测零/非零的偏离名单；例如 C07 若从非零变为数值零会被点名，而 C11 为零会被记为符合构造。它不等于要求每个 family 的 now 都有用，也不是新的成功门或显著性阈值。
- 白话：同尺 current 影响审计解决“权重都写 1.0，却不知道执行式 now 与无执行 scorer current 实际推动 posterior 多大”的问题。输入是同一批 online 行、相同 temperature 和两种方法各自的完整/去 current posterior，输出是并排的 total variation、KL、赢家变化和 reference 概率变化；例如 E 的 mean TV 是 A 的两倍也会原样报告。它不等于把两者强行校成相等、削弱 E，或把只含 auxiliary target 的 C 假装成另一个 E。
- 备选方案：把 now 设为 M1 audit-only 并推迟到 M2；拒绝，因为固定量程后 now 对软 posterior 仍有可测影响，而且只删执行式 now 会让 C/E 独占 current 通道，连 C/E 一起删除又无必要削弱已登记的当前＋未来假设。用 clipping、MAD 或人为 std floor；拒绝，因为仍依赖同行候选分布并引入新的经验阈值。把 posterior influence 设硬门；拒绝，因为它会诱导按预跑数据调权重制造信号。
- 影响：更新 energy assembly、C/E scorer inference、arrays/manifest、生成健康门、A–F 报告、协议/data/report schema、测试与 S4 流程；补充逐 family now 预期偏离和 S1 E-current 同尺 posterior 报告；不改 raw current mismatch、future 语义、能量权重、temperature、A–F、K=16、C10/C11、正式规模、两架构、主指标或 test seal。
- 是否接触 test 信息：否；只读取本地 train-only v7 探针及重新生成的小规模 train/validation 接口验证数据，未生成或解封正式 test。
- 验证方式：协议负例分别锁住 current fixed range、future z-score、bounded probability current energy、posterior audit 和非主机制切片；单测验证 `raw/range==scaled`、scaled∈[0,1]、关系 current energy 不 z-score、posterior 重构/逐项消融、五切片全覆盖；随后在干净服务器提交上跑 full test，再单独跑 12-group v8 train-only health/cost benchmark，成功后才登记新 S1/S2。

## D-042 — v8 双架构 train/inner-dev 有限预算选择

- 日期：2026-09-07。
- 状态：accepted；落实 D-039/D-041 要求的 v8 重新选预算，旧 v5/v7 的 1000-step 结论仍不迁移。
- 用户确认：服务器 175 项测试和 12-group v8 health 均通过并完成本地复核后，用户回复“OK开始下一步”，授权进入预算登记与实现。
- 背景：Set Transformer 主臂加入候选间交互，MLP 次臂容量较小；同时 v8 改了 current energy、C10/C11 和训练目标接线。因此旧协议上只为 E scorer 选出的 1000 updates 既不能代表新 scorer，也没有回答 A–E student 应训练多久。若先看 validation 再决定训练步数，会消耗确认分区并把 S5 变成调参。
- 决策：
  1. 两条架构臂分别选择自己的 scorer budget 和 student budget，但架构身份不由结果选择：`cross_candidate_set_transformer_v1` 始终是 go/no-go 主臂，`shared_candidate_mlp_v1` 始终是容量稳健性次臂。
  2. 预算选择只读完整的 1000 个 v8 train mixed paired groups。继续用 `sha256(rollout-pair:train:{group_index:06d}) mod 5 == 0` 留出完整 inner-dev group；siblings 与 recovery rows 同进同出。validation/test 均不生成、不读取、不消费 trial。
  3. 两种架构都登记 scorer/student checkpoints `{300,1000,3000}`、五个 seed `{7,19,31,43,59}`、learning rate `0.002` 和 batch size `64`。每个 seed 只训练一条到 3000 updates 的固定随机轨迹，在三个前缀处评估；这与分别以相同 seed 从头训练到 300/1000/3000 的参数状态相同，同时避免重复前缀计算。
  4. E scorer 先选。主选择量是 shared-preflight 后 inner-dev online 行的 reference candidate-ranking accuracy；先在每个完整 paired group 内计算，再让 seed 和 group 等权平均。登记点中均值最高者胜；仅当浮点结果精确相同时选择 updates 更少者。BCE、margin 和 current posterior influence 继续解释，不参与选择。
  5. scorer 固定后再选该架构唯一的 shared student updates。A–E 均进入选择，每个方法与其固定 teacher 比较 inner-dev online argmax；方法先等权，再让 seed 与完整 group 等权。均值最高者胜，精确平手选较少 updates。A/B/C 使用 executed hindsight teacher 作评估目标、D 使用 current-only teacher、E 使用刚选定的 no-execution scorer teacher；这量的是各自监督被 amortize 的程度，不是 A 相对 C/E 的主效果，也不允许针对 A 单独选预算。
  6. C 在本轮 student-budget 选择中使用预登记 `auxiliary_weight=1.0` 锚点并与 A–E 共用 updates。validation 后续只允许在原 `{0.1,1,10}` 中选择 C auxiliary weight 以及一组 A–E 共享 commit rule；它不能回头重选 scorer/student updates。
  7. runner 必须报告逐 architecture/seed/method/checkpoint/paired-group 选择量、BCE/KL/reference accuracy、训练 trace、wall-clock、设备和参数量。A–E student 参数量在同一架构内必须一致并满足既有 10% 门；E 的额外 scorer 参数仍单列。
- 白话：有限预算网格解决“模型没学会究竟是方法差，还是只训练得不够”的问题。输入是 1000 个 train groups、两种固定架构和三个事先写死的更新点，输出是每种架构各一个 scorer 步数与一个 A–E 共用 student 步数。例如 Set Transformer 可能选 3000、MLP 可能选 1000，但仍分别完整跑 A–F，不能因 MLP 分数好就把它换成主模型。它不是正式 validation/test 成绩，也不是无限搜索超参数。
- 白话：前缀 checkpoint 路径解决重复训练成本。输入是同一 seed、相同初始化与批次随机序列，输出是训练到第 300、1000、3000 步时的三个状态；例如第 300 步状态就是单独“训练 300 步”会得到的状态，后续评估不会改变随机批次。它不等于 early stopping、不按中途结果改变最大步数，也不让三个点共享不同 seed。
- 白话：teacher-argmax student 选择量解决“共同 student 预算不能只按 A 是否赢来挑”的问题。输入是 A–E 各自已经固定的监督 posterior 与学生在线输出，输出是学生第一名是否复现其 teacher 第一名；例如 E 的 scorer teacher 选 BIND 而 E student 选 NOOP 就记一次 amortization error。它不把 teacher 或 future 喂给 online inference，也不等于最终 reference accuracy、causal 效果或 CTL 优势。
- 备选：沿用旧 1000 steps，被拒绝，因为架构、能量和数据协议均已改变；在 validation 上选 checkpoint，被拒绝，因为会把确认集用于训练开发；为 A/C/E 分别选 student steps，被拒绝，因为会破坏共同更新预算并制造方法特定优化优势；把三个点独立重训，被拒绝，因为固定 seed 下重复了完全相同的前缀计算。
- 影响：活动 protocol 名称和 dataset version 保持 v5/v8，但机器配置 hash 因预算合同加入而更新；旧 12-group health arrays 只保留为机制健康证据，正式 1000-group train arrays 必须按新 protocol hash 重生成。新增 train-only budget runner 和 checkpoint 审计回调；S5 validation 只保留 C weight 与 shared commit rule 的选择权。
- 是否接触 test 信息：否；本 decision 只依据已入库的 train-only health 报告与既有合同，不生成或读取 validation/test。
- 验证方式：协议负例锁住 1000 train groups、两架构、五 seed、两个 `{300,1000,3000}` 网格、选择量、平手规则和 validation/test=false；单测验证 checkpoint 回调落在真实训练前缀且平手选较小预算。随后在干净服务器提交上跑完整测试，再生成唯一 1000-group v8 train arrays，依次运行 Set Transformer 与 MLP 的预算报告。

## D-043 — 严格架构控制下的对称逐方法优化

- 日期：2026-09-07。
- 状态：accepted；取代 D-042 的 Post-LN、单一 learning rate、3000-step 上界和 A–E 共享 student updates，保留其 train-only、双架构不择优和固定前缀训练框架。
- 用户确认：用户明确要求“A–E 架构方面控制变量，可以 STEP 不一样选最优”，并接受同一搜索空间内逐方法选择、共享预算和交叉预算同时报告。
- 背景：主臂有 341,732 个 student 参数，次臂有 26,148 个，但 D-042 把 MLP 时代的 `learning_rate=0.002` 同时固定给 Post-LN Set Transformer，且 3000 是没有触顶处理的上界。强制 A–E 共用一个 updates 点也会让不同监督目标的可拟合难度混入方法效果；反过来，若各方法用不同指标或不同网格调优，又会破坏控制变量。
- 决策：
  1. 活动协议升为 `m1-hard-condition-v6`，dataset 仍为 `m1-paired-latent-worlds-v8-fixed-range-current-energy`。本 decision 不改生成语义、A–F 定义、energy、K=16、split 或 test seal。
  2. `cross_candidate_set_transformer_v1` 改为标准 Pre-LayerNorm 残差块，并在最后一个 attention block 后增加一次 LayerNorm；MLP 次臂不改。两层、model dim 128、4 heads、FFN 256、dropout 0、Adam、batch 64 均保持；不同时加入 warmup、scheduler、gradient clipping 或新 optimizer。
  3. 每条架构臂的 scorer 和 A–E student 共用同一有限网格：learning rate `{0.0002,0.0006,0.002}` × checkpoints `{300,1000,3000,10000}` × seeds `{7,19,31,43,59}`。每个 learning rate/seed 只训练到 10000，一次记录四个真实前缀；五个方法必须恰好拥有相同 12 格，禁止为任何方法扩格。
  4. 同一架构臂内 A–E 使用同一个 `OnlineModel` 类、完全相同的输入、K=16 槽位、candidate mask、参数模块与形状、batch 采样规则、optimizer、batch size 和 12 格搜索空间。所有方法都分配 relation head，只有 C 的 loss 使用其梯度。允许变化的独立变量是监督/loss；E 的额外 outcome scorer 参数和计算继续单列。
  5. E scorer 先在 train 固定 inner-dev 上按 online reference-candidate ranking accuracy 选择自己的 `(learning rate, steps)`。scorer 固定后，A–E 各自在完全相同的 12 格中，按同一批 inner-dev online rows 的 reference-candidate selection accuracy 选择自己的 `(learning rate, steps)`；先在每个完整 paired group 内对五 seed 等权平均，再对 group 等权。最高均值胜；精确平手依次选择更少 updates、更小 learning rate。
  6. 逐方法最优格定义后续正式训练配置。同时从已经计算的相同网格预登记两种算力敏感性读数：一是按 A–E、seed、完整 group 等权选择一个共享格并在该格重报 A−C/A−E；二是在 A 选中的格比较 A/E、并在 E 选中的格比较 A/E。它们只作诊断，不反向选择正式配置，不增加训练格。
  7. scorer、每个方法和共享格的报告都保存“选中格减确定性第二名”的 paired-group bootstrap 95% CI：先对 seed 等权，完整 paired group 为唯一重采样单位，10,000 次，seed=`260907`。CI 只显示选择噪声，不把精确平手改成“统计平手”，也不改变确定性选择。
  8. 若任一 scorer/student/shared 选择落在 10000，上限结果照实接受并标记 `budget_grid_ceiling_reached=true`；禁止看到触顶后追加新点。每个方法另报自己最优格相对固定共享锚点 `(0.0006,3000)` 的差值。
  9. 主/次架构身份仍不可按结果交换：Set Transformer 是正式 go/no-go 主臂，MLP 是容量稳健性次臂，两臂均完整跑 A–F。C 的 budget run 暂用 `auxiliary_weight=1.0`；后续 validation 仍只在已登记 `{0.1,1,10}` 中选 C weight 与共享 commit rule，不得重选本 decision 的 learning rate 或 steps。
  10. 服务器完整测试通过后，先单独重生成 12-group v8 health 并要求 arrays digest 逐位等于 `e924f96d4cf28179df010766e4275244cbb78cb9f9425ed514093bdbca3958c3`。protocol/manifest hash 预期改变，arrays digest 不应改变；不相等即视为训练合同意外耦合数据生成，先调查而不启动 1000-group arrays。
- 白话：Pre-LayerNorm（预归一化残差）解决较大注意力模型在当前固定 optimizer 下可能比 MLP 更难优化的问题。输入仍是同一行 16 个候选 token，输出仍是 16 个候选分数；例如 attention 前先归一化候选表示，再把比较结果加回残差，最后统一归一化。它不增加候选、未来信息或新监督，也不保证 Set Transformer 一定胜过 MLP。
- 白话：对称逐方法调优解决“某个监督目标只是因为共同步数不合适而没学会”的问题。输入是 A–E 完全相同的 12 个 `(learning rate, steps)` 格和同一 train/inner-dev reference 指标，输出是每个方法自己的一个最优格；例如 A 可选 10000、E 可选 1000，但两者都只能从同样 12 格中选择。它不等于给 A 更多试验机会、不允许换架构，也不读取 validation/test。
- 白话：共享与交叉预算读数解决“A 只是多训练才赢”的质疑。输入是不额外训练、已经存在的 12 格结果，输出是所有方法同格比较，以及 A/E 在彼此所选格上的比较；例如即使 A 自选 10000、E 自选 1000，报告仍会显示 A 和 E 在 1000 那一格谁更好。它不替代逐方法正式选择，也不允许看完结果再增加格子。
- 白话：paired-group bootstrap（配对组自助法）解决最优格与第二名差距可能只是少数序列波动的问题。输入是两格在同一批完整 causal groups 上、先跨 seed 平均后的差值，输出是 10,000 次按 group 重采样得到的 95% 区间；例如区间跨 0 只说明选择优势不稳定。它不改变“最高均值＋精确平手规则”，也不是最终 A−C/A−E 效应检验。
- 备选：继续使用单一 `0.002` 与 Post-LN，被拒绝，因为它把未经本架构验证的优化设置固定在主臂；强制 A–E 共用 updates，被取代，因为各 teacher 的可拟合难度不同；按各自 teacher fidelity 逐方法选格，被拒绝，因为五个方法会优化不同选择量；看到 10000 胜出后扩网格，被禁止，因为是结果后调参。
- 影响：更新 Set Transformer 架构、预算 runner、机器合同、测试和 S4 流程。架构变化要求追加 `EXECUTE.md` LOG，但在服务器预算结果产生前不宣称性能提升。旧 D-042 full-test handoff 作废；旧 v8 health 只可在新提交重生成且 arrays digest 相同后继承机制结论。
- 是否接触 test 信息：否；设计只基于 train-only health、代码审计和预登记优化风险，validation/test 未读取。
- 验证方式：本地轻量测试锁住 Pre-LN、最终 LayerNorm、三学习率、四 checkpoints、逐方法相同 12 格、双预算读数、确定性第二名、paired bootstrap 和触顶策略；服务器先跑完整测试，再单独做 12-group digest invariance，之后才允许生成 1000-group train arrays。

## D-044 — semantic/support 终点可用性、机制覆盖与 test 检验力预登记

- 日期：2026-09-08。
- 状态：accepted；只授权 train-only 可用性探针和常驻评测补全，尚未选择 exact/graded 分支、尚未解封 validation/test。
- 用户确认：用户要求在拉取服务器 D-043 运行时报告后，客观判断并“正式接受并实现评价协议变更”；此前已明确接受把 endpoint 非退化、检验力、节点盲区与 F oracle 纳入预登记。
- 背景：D-043 服务器剖析已通过，Set Transformer/MLP 完整登记网格保守线性投影分别为 `3.128/1.239` 小时，合计 `4.367` 小时，因而先做固定 anchor 探针不会造成不可接受的额外计算。旧 3-group smoke 中 A–E 的 `final_active_graph_correctness` 全为零，但它只能提示风险，不能触发换指标；该量是 20 步结束时 active node+edge semantic state 的整图精确相等，不是逐步正确率连乘，后续事务可以恢复。另一方面，`memory_contamination` 与 `missing_open_facts` 都只覆盖开放边，无法看见非 protected 节点的 lifecycle/canonical/latent 错误；active state 又有意不含 `evidence_refs`，因此 C10 的错误 BIND/NOOP 可保持 active semantic world 与边计数完全相同。现有 protected collateral 能看完整受保护记录，却没有把已计算的证据范围外 unrelated mutation 纳入 causal 主安全聚合，导致 C11 的专门对照也可能不触发旧主安全数。
- 决策：
  1. **不立即换主指标。** 使用已经生成的唯一 1000-group v8 train arrays，在主架构 `cross_candidate_set_transformer_v1` 上只跑 A/C/E 和无需训练的 F。固定 seeds=`{7,19,31,43,59}`、learning rate=`0.0006`、student updates=`3000`、E scorer=`0.0006/3000`、C auxiliary weight=`1.0`；799 个 fitting groups 与 201 个 inner-dev groups 由既有 SHA-256 规则确定。不得搜索 checkpoint、learning rate、方法或指标，不读取 validation/test。
  2. causal commit gate 在 201 个 inner-dev groups 内做预登记的两折 cross-fit：paired group 以 `sha256(paired_group_id + ':endpoint-probe-fold')` 前 8 字节模 2 分折，每折只使用另一折按既有 lexicographic 规则校准 A/C/E 与五 seed 共用的 gate；本折只评估。另报 `(commit_probability=0, margin=0)` always-commit 诊断，但它不能触发指标切换。这样输入是 train-only 概率，输出是对每个 group 没用自身结果校准过的 causal endpoint；它不等于 validation 校准或新增可调 gate。
  3. exact semantic endpoint 仍为 `final_active_graph_correctness`。预备 fallback 为**多重集 Jaccard active-world correctness**：把 `_active_graph_state` 同一组开放节点记录 `(node_id,node_type,lifecycle,canonical_id,latent_refs)` 与开放边记录 `(source,target,relation,frame)` 合并成保留重复次数的多重集，取交集计数/并集计数。它在 `[0,1]` 内且 `graded=1` 当且仅当 exact=1，所以只是同一 active-world 构念的渐进松弛，不是换成 edge-only contamination；不同 `edge_id` 但语义相同的重复开放边不会被普通 set 静默折叠。
  4. 另把 `final_graded_open_memory_correctness` 固定为 A−C/A−E 都必须通过的 co-primary support endpoint。它对 `_open_memory_state` 的同一开放 node/edge records（包含 `evidence_refs`）计算多重集 Jaccard，阈值独立登记为 `0.03`；同时单报 evidence attachment 对称差。白话说，semantic active world 回答“当前世界结构对不对”，open-memory support 回答“这些开放记录挂接的观察证据对不对”；C10 错误 BIND 只污染后者，不能再被 active 指标吞掉。它不把 closed provenance 算当前错误，也不把 evidence 支持与几何边污染混成一个解释。
  5. F 是硬 integrity gate：每一个 inner-dev group 必须 semantic exact=1、active graded=1、open-memory graded=1 且 node error=0；任一失败就中止，不允许切指标或启动完整预算网格。A−C/A−E 先在每个完整 paired group 内对两个 siblings 和五 seed 等权平均。某 endpoint 对一个对照“非退化”要求 paired-group 差的样本标准差大于 0，且绝对非零 group 数至少 `ceil(0.03×201)=7`；`1e-12` 以下按数值零处理。open-memory support 对两对照也必须非退化，否则停止，不用 semantic 分支掩盖 evidence 盲区。
  6. semantic endpoint 的一次性切换规则只看**可观测性**，不看 A 是否赢、效应正负或大小：若 exact 对 A−C、A−E 均非退化，保留 exact；否则仅当 active graded 对两者均非退化时，全局一次切到 active graded；若 graded 仍退化，停止并另立 decision，不继续搜索第三个 semantic 指标。graded 的有意义效应独立登记为绝对 `0.03`，含义是相对 active-record overlap 提高三个百分点，不冒充从二值率继承了同一物理单位。
  7. 检验力按与正式门一致的 H0 `effect≤0.03` 规划，而非错误地按 H0 `effect≤0`。对最终选中的 semantic endpoint 与固定 open-memory support endpoint，固定规划真效应 `0.06`、每个主对照单侧 `alpha=0.025`、power=`0.80`，以探针 paired-group SD 代入 `ceil((((1.959964+0.841621)×SD)/(0.06−0.03))²)`；至少 200、向上取整到 10，并取两个 endpoint × A−C/A−E 的最大值。无预设上限，test 只在样本数登记后生成；这不是用 inner-dev 效应判断胜负，而只用方差避免一次性 test 天生欠功效。
  8. 无论是否切换，常驻报告 semantic exact/graded、open-memory exact/graded、active/open node/edge 多重集对称差、evidence attachment 对称差、参考记录数和 union 规模。新增 `active_node_state_error_per_100` 安全非劣 margin=`1.0/100 decisions`；修改一个节点记录算“一条正确记录缺失＋一条错误记录多出”共 2，新增/删除算 1。白话说，它防止方法边数没错却把对象 lifecycle 或 canonical 身份改坏；输入是终点 active node records，输出是错误记录数，它不替代主效果，也不把 retained history 当当前世界。
  9. collateral 主安全量修正为每步 `protected state mutation OR committed evidence-scope-external mutation` 的并集，并分别报告 protected/unrelated 两个分量；原 margin=`0.5/100 decisions` 不变。白话说，受保护对象被碰坏和证据范围外的无关图被连带修改，两种都算连带伤害；输入是每步 base→post 状态及 evidence scope，输出是两个原因和不重复计数的并集，它不把合法的新事实 growth 或 executor illegal 混进来。
  10. 新增 C00–C11 机制–指标覆盖矩阵：对每个 reference row 枚举所有非 reference、shared-preflight admitted 且 executor-legal 的候选，逐 family 报 active、open-memory、evidence、边/节点与 collateral 哪条渐进通道能看到差异。所有 family 至少要有一个非参考候选被渐进通道识别；C10 的指定相反 BIND/NOOP 每行必须由 open-memory+evidence 识别，C11 的 `bind-with-collateral` 每行必须由 unrelated collateral 识别，否则在 endpoint probe/预算网格前停止。它不要求把语义等价的每个程序都硬判错，也不把 executor illegal 当可部署指标。
  11. recovery 同时报 `designed_recovery_rate_within_window` 与 `any_first_error_recovery_rate_within_window`、各自 eligible 数与恢复时间。另报最终参考 active/open-memory record 数分布，防止 graded 比例受图规模变化而被误读。
  12. M1 v8 health 中 teacher/reference argmax agreement=`1.0` 必须如实披露，同时报告 teacher top-1 均值/中位数、低于 0.60 的比例与 posterior entropy，并保留 H=1 消融。一般 CPMT 合同仍允许 teacher 与 reference 分歧；本 fixture 的高 agreement 是 teacher health/conformance 事实，M1 在此主要检验软 executable hindsight distribution 的传播，而不宣称所有决策都由 teacher 改写标签。
  13. D-041 对 C10 “teacher resolution/causal endpoint 具有信息量”的旧表述在本条下被精确收窄：C10 的当前输入按构造完全同分布，任何合法在线方法的实例级单步上限都约为 0.5；hindsight teacher 能在训练时辨认哪个已发生未来与候选一致，但 student 部署时不可能从相同当前输入预知该实例。因此 C10 只检查软后验的不确定性、QUARANTINE/提交行为和 evidence-support 后果，不单独支持 A 优于 C/E，也不宣称预测 20 步未来。
- 白话：endpoint viability probe（终点可用性探针）解决“正式 test 只有一次，但原来的整图全对指标可能所有方法都得零”的问题。输入是固定模型设置、201 个从 train 留出的完整 group 和未训练的 F oracle，输出只有三种机械结果：保留 exact、一次切到同构 graded、或停止；例如 A/C/E 的 exact 全零但 graded 有组间差时按已写死规则切换。它不按谁赢挑指标、不调模型、不看 validation/test，也不是正式方法成绩。
- 备选：直接因旧 smoke 全零而换主指标，被拒绝，因为旧样本小且协议/模型过时；用 contamination+missing 作 fallback，被拒绝，因为二者只看边并遗漏节点身份状态；用普通 set Jaccard，被拒绝，因为会折叠重复语义边；若 exact 方差大就换 graded，被拒绝，正确处理是保留 exact 并前瞻增加 test groups；把 201 个 group 直接称为 200，被拒绝，实际 hash 分割是 799/201。
- 影响：新增专用机器预登记 `configs/m1_endpoint_viability_probe.json`；补 active-world graded/node/edge、open-memory graded/evidence、完整 collateral 分解、机制–指标覆盖矩阵、endpoint decision helper、测试与 S4 流程。活动 `m1_hard_condition.json` 暂不修改，从而已有 v6/v8 1000-group arrays 可作为探针输入；探针选定 semantic 分支和 test 数量后再一次性升级正式 protocol、同步 co-primary/safety/go rule 并按新 protocol manifest 重验/重生成，不把条件分支提前伪装成已选结论。
- 是否接触 test 信息：否；D-044 的依据只有代码审计、旧 train-only smoke、v8 train arrays/health 和 planning-only runtime profile。validation/test 未读取，test 尚未生成。
- 验证方式：单测锁住 node-only 错误可见、重复 edge 多重性、`graded=1⇔exact=1`、protected/unrelated collateral 分量与并集、F gate、group-first 聚合、非退化开关和功效公式；干净服务器 full test 后才运行固定探针。报告导出并接受分支后，才允许进入 D-043 完整预算网格。

## D-045 — M1 指标构念、全过程负担与无选择 gate 对齐

- 日期：2026-09-08。
- 状态：accepted；阻断 endpoint probe/完整预算网格的指标语义修订已冻结，尚未运行服务器 full test、endpoint probe、validation 或 test。
- 用户确认：用户要求把 `docs/reviews/2026-09-07_metric_layer_audit.md` 的 C1/C7 作为正式 M1 前阻断项，并在新对话“开始这个项目的下一步”；随后再次确认当前审核必须落实其列出的 C1–C7、B1/B4 与 B2/B3，而不是推翻 D-044。
- 背景：D-044 已让节点、evidence 与 unrelated collateral 错误可见，但旧 `memory_contamination` 只是预测开放边集合减 reference 开放边集合；它既不能说明错误是本步写入还是旧事实未撤销，也把 `100×终点错误数/20` 命名得像 100 次决策的事件率。最初愿景的 Dynamic Contamination Rate（DCR，动态污染率）专指动态目标错误覆盖 static memory slots；M1-v8 没有独立 transient memory、decay 或 dynamic-to-static slot overwrite，因此不能用当前开放边量宣称已验证原始 DCR。旧 `post_graph_correct` 又等于 retained `history_exact`，`unresolved_active_error` 则只是 `1-final_active_graph_correctness`，继续并列进正式主表会制造构念和极性误读。审计还确认空 recovery 分母被写成 0、false-birth 用净基数会抵消、共享原始 softmax gate 在 A/C/E 不同监督尺度间未必公平，而且用单步代理选 gate 与 20-step endpoint 不同尺。
- 决策：
  1. 现有边集合差的规范名改为 `extra_open_fact_error`（预测中多出的开放边事实）与 `missing_open_fact_error`（reference 中应有但预测缺失的开放边事实）。旧 `memory_contamination`/`missing_open_facts` 只保留机器兼容 alias；正式主表、论文表和新解释不得使用旧名。`post_graph_correct*` 只作为 `history_exact*` 兼容 alias，`unresolved_active_error` 只作为 active exact 的反极性兼容 alias，三者均从正式 endpoint summary 排除。exact semantic 是非退化时的首选二值终点，graded semantic 仍只是 D-044 预登记的一次性同构 fallback；两者可同时报告但角色必须标明。
  2. 每步额外开放边再拆为 `new_incorrect_open_fact_write` 与 `retained_stale_open_fact`：前者是 post 中错误且在该方法本步 pre-decision world 不存在的事实，后者是 post 中错误且已存在于该 pre-decision world 的事实；两者之和严格等于该步 `extra_open_fact_error`。例如本步把杯子写到错误房间计 new write，下一步继续保留同一错边计 stale retention。该分解描述“本次决策新引入还是沿用”，不追溯一个错误在更早哪一步首次产生，也不把 NOOP 的陈旧状态说成主动写入。
  3. 每个方向同时登记 terminal normalized burden（归一化终点负担）与 AUC burden（Area Under the Curve，时间曲线下面积负担）。`terminal_*_per_100_decisions = 100×第20步状态错误数/20`；它只回答最后剩多少，不叫事件率。`*_auc_per_100_decisions = 100×二十步状态错误数之和/20`；白话说，它把错误在轨迹中存活的每一步都计入，因此前 19 步一直错、最后一步修好仍留下负担，而不是被终点清零。
  4. M1 的固定长期负担 co-primary 改为 `open_fact_error_auc_per_100_decisions = extra AUC + missing AUC`，两方向必须另报且不能互相抵消；最小有意义改善沿用 `2.0/100 decisions`，功效规划真效应登记为 `4.0`。它解决“只看多出的边会把漏更新藏掉”；输入是每步预测/reference 开放边集合，输出是累计额外与缺失暴露之和，例如错误旧边保留 10 步并同时漏掉新边会两边各自累计。它不等于原始动态 actor 覆盖 static slot 的 DCR，也不把节点/evidence 错误揉进边负担；semantic 与 open-memory support 两个 co-primary 继续承担那些构念。
  5. endpoint probe 的 test-N 取 selected semantic、固定 graded open-memory support、固定 `open_fact_error_auc_per_100_decisions` 三类 co-primary × A−C/A−E 的 paired-SD 功效需求最大值。正确度仍按 H0≤0.03、规划真效应 0.06；边负担按 H0≤2、规划真效应 4；二者都用单侧 alpha=0.025、power=0.80、至少 200、向上取整到 10。co-primary 必须全部通过属于 intersection-union gate，不因增加必须同时通过的 endpoint 放宽显著性。
  6. `false_birth_growth` 改为预测开放 entity ID 集合减 reference 开放 entity ID 集合的大小，并另报 missing open entities；禁止用两个集合总数的净差。这样错删一个真实实体同时错建一个假实体时仍记一项 false birth 和一项 missing，而不是 0。terminal false-birth 保持安全门，AUC 与 missing 作为常驻解释量。
  7. 任一 conditional recovery 分母为空时，rate 与 conditional mean time 输出 JSON `null`，并始终报告 eligible denominator；0 只表示有 eligible 样本且成功数为零。旧报告中的 0 保留为历史快照，不回写。白话说，`null` 回答“没有可评价案例”，0 回答“有案例但全失败”；输入是 eligible 序列集合，输出是分母与条件比例，例如 F 从未出错时 recovery rate 是 `null` 而不是 0。它不改变错误步或 out-of-scope 计数。
  8. D-044 的两折 shared raw-softmax gate 被本条 supersede。M1 endpoint probe 与后续正式主比较固定使用同一无选择 gate：`commit_probability=0`、`margin_threshold=0`，A/C/E/F 都尝试提交 argmax；shared preflight 仍先拒绝静态非法候选，剩余 executor-illegal 选择仍由 deterministic QUARANTINE 原子回退且不写 persistent world。confidence/risk-coverage 可报告但不能选 endpoint、阈值或主效果。白话说，fixed always-attempt gate 解决“不同监督训练出的概率尺度不同，却用一个绝对阈值决定谁可以行动”和“用单步成绩调 20 步系统”的混淆；输入只有每法 argmax 与共同合法边界，输出是一次执行尝试或非法回退，例如 E 低置信但合法的 NOOP 仍按模型选择执行。它不声称概率已校准、不让方法各自挑有利阈值，也不取消 executor 对非法程序的 QUARANTINE。旧非正式 smoke 曾选中同一 `(0,0)` 且暴露提交率差异，只作为风险证据，不是当前 v8 性能或调参依据。
  9. edit/growth 的小 posterior influence 继续如实报告，不为“制造机制作用”改权重。论文只称 minimal-world-change 为 registered prior/regularizer（预登记先验/正则项），不得称为已验证主机制。它解决的是并列候选中偏好更小改动；输入是候选 edit/growth cost，输出是教师能量中的轻量偏置，例如两候选 future 一样时偏向少建节点者。它不等于本实验已证明该项带来收益，也不替代 executable hindsight。
  10. M1 的结论边界固定为 controlled embodied persistent-world revision。独立 Static Structural Memory/Dynamic or Transient Memory、decay、static retention、dynamic actor contamination、reappearance 与 viewpoint consistency 仍是 M2/M3 planned；M1 的开放图指标不得宣称验证完整初始愿景。
- 机器合同与版本：`configs/m1_endpoint_viability_probe.json` 升为 v2，作为 v6/v8 不可变 train arrays 上的 D-044/D-045 evaluation overlay；输出 schema 升为 `m1-endpoint-viability-report-v2`，一般 A–F causal report 升为 v6、逐 seed causal payload 升为 v5。活动 `m1_hard_condition.json` 暂不改 hash，因为 D-044 已冻结只在 probe 选定 semantic 分支与 test N 后一次性升级正式 protocol；这不允许旧 hard-config 中的旧指标文字覆盖本 overlay。existing train arrays digest `e8a890...b168` 仍只作为同一数据内容输入，指标从可重建 audit/causal state 重新计算。旧数组字段 `excess_nodes` 为 pre-D-045 净基数诊断，只为字节级复用保留，禁止作为正式 false-birth safety；正式 `false_birth_growth` 始终由预测开放 entity ID 减 reference ID 的集合差重新计算。
- 备选方案：拒绝只改名字而继续用终点量过 long-horizon 门；拒绝只把 extra AUC 设主门而让 missing 被语义遮蔽；拒绝为了保留低置信 QUARANTINE 再从当前 inner-dev 搜索方法特定阈值，因为会在 endpoint probe 内新增大规模选择并混入概率校准能力；拒绝沿用 shared raw-softmax 绝对阈值，因为监督机制本来不同、概率尺度没有预先校准。
- 影响：D-044 的可见性修复、F integrity、exact/graded 一次切换、C10/C11 机制覆盖与节点/collateral 安全门保持；D-045 只补构念、时间口径、分母、false-birth、gate 和正式报告语义。正式 protocol 升级时必须同步 go rule、功效结果、report schema 与 compatibility alias 表；M1→M2 stop rule、候选、executor、架构和训练预算不变。
- 是否接触 test 信息：否。只读取外部审计、原始愿景、活动合同、历史已导出的非正式 smoke 与 train-only v8 health/runtime 证据；未生成或读取 validation/test，未训练 anchor，未观察 endpoint probe 结果。
- 验证方式：单测锁定 extra/missing、新写入/stale 的逐步恒等关系，终点/AUC 差异、false-birth 不抵消、空 recovery=`null`、compatibility alias 排除、三类 co-primary 功效与无选择 gate；Python compile、JSON/schema、shell syntax 与 `git diff --check` 本地通过后，先在干净服务器只跑 full test。full test 成功后才把唯一服务器入口改写为固定 train-only endpoint probe，仍不启动完整预算网格。

## D-046 — M1 AUC 持续等价门与纯 validation confirmation

- 日期：2026-09-08。
- 状态：accepted；在读取 endpoint probe、validation 或 test 结果前冻结，supersede D-045 §4/§5 的 AUC `2/4` 门，并把 D-043/D-045 遗留的 validation 选择职责移回 train/inner-dev。
- 用户确认：用户接受 terminal 与 AUC 是不同 estimand、`2×20` 只有在声明“效应贯穿 20 步”时才有含义，并明确要求把更严门与样本量、全程持续理由、probe 不得回调阈值、C 顺序扫描及三种提交率写入正式 decision 后执行。
- 背景：D-045 正确把 `open_fact_error_auc_per_100_decisions` 登记为 long-horizon co-primary，却把终点错误负担的最小/规划效应 `2/4` 原样沿用到 AUC。terminal=`100×第20步错误事实数/20`，AUC=`100×二十步错误事实数之和/20`；二者不是同一统计对象，因而不能只凭相同的 `/100 decisions` 字样共用数值门。用 AUC `2/4` 时功效公式的 planning-minus-null 只有 2，配对 SD 为 20/30/50/80 会分别要求 790/1770/4910/12560 groups，说明该门把“很短的累计暴露变化”误当成长期有意义效应。旧 smoke 又是 extra-only、旧 gate、旧协议，只能提示 AUC 数量级，不能选阈值。与此同时，固定 `(0,0)` gate 已取消 validation gate 搜索；若 C auxiliary weight 仍留在 validation，200-group validation 就只服务一个基线的三选一，无法保持纯确认职责。
- 决策：
  1. `open_fact_error_auc_per_100_decisions` 的最小有意义绝对改善固定为 `40.0`，功效规划真效应固定为 `80.0`。这叫 **20-decision persistent-equivalent effect（20 步持续等价效应）**，是声明的建模假设，不是从 terminal 做单位转换。因 AUC=`5×错误事实-决策步暴露总数`，40 对应每个 paired group 平均减少 8 个错误开放事实×决策步暴露，80 对应减少 16 个。例如相对基线少保留一条错边 8 步达到最小门；只在最后一步把终点修好但此前没有累计减少 8 个暴露，不能靠 terminal 合格替代 AUC 合格。它不表示每个错误必须恰好持续 20 步，也不把 AUC 解释成错误事件发生率。
  2. 选择“全 20 步持续等价”而不是半程锚点，是为了让 long-horizon 门专门拒绝晚期补救：一个方法可以终点正确，却因前段长期保留错边而未达到 AUC 40；三类 co-primary 使用 intersection-union gate 时整体应失败。这解决“后来修好是否能抹掉早先污染”的研究问题，输入是完整 20-step 逐步状态，输出是不可被终点追溯清零的累计收益；它不等于另加终点惩罚，也不允许 semantic/open-memory 的优势抵消 AUC 失败。
  3. semantic 与 open-memory 的 null/planning 仍为 `0.03/0.06`，AUC 为 `40/80`，三者都保持 planning-to-null=`2×`。H0 是 effect≤minimum，因此把 AUC minimum 从 2 提到 40 会使科学通过门更严；功效分母从 2 增到 40、所需 N 随 `(SD/(planning−minimum))²` 降低，是按 AUC 自身构念定门后的数学推论，不是选阈值的动机。功效仍取三类 co-primary×A−C/A−E 最大值、至少 200、向上取整到 10、无预设上限。
  4. endpoint probe 无论观察到什么 AUC 均值、效应或 SD，都不得改 `40/80`。若可达尺度远低于 40，报告应冻结该尺度与功效结果，并把它解释为“CTL 在本 M1 设计中未达到预登记的持续效应量级”；不得以“尺度不匹配”为由重调门、换相对百分比或再跑一版 probe。probe 只决定 exact/graded semantic 的机械分支与 test N，不决定 AUC 阈值。
  5. C 的 `direct_future_auxiliary_weight∈{0.1,1,10}` 改到 train/inner-dev 做**顺序有限搜索**。第一阶段所有 A–E 仍在 weight=1 锚点上使用完全相同的 3 learning rates×4 update prefixes=12 格，以相同 complete groups、五 seeds、reference candidate-ranking accuracy、均值最高与“更少 updates、再更小 lr”的平手规则选各自计算格。第二阶段只固定 C 已选的 lr/updates，复用 weight=1 结果并为 0.1、10 各补一条同 seed 训练路径；三权重仍按相同 group-first、seed-averaged accuracy 选最高，精确平手优先锚点 1，再取较小登记权重。两阶段各自报告全部格、确定性 runner-up 与 paired-group bootstrap 不确定性，不做 36 格联合搜索、不扩权重或回头重选 C 的 lr/updates。
  6. 顺序搜索让 C 比其他方法每 seed 多两条已登记路径，但不会冒充完全对称搜索；公平性来自共同的 12 格计算预算、相同 train/inner-dev 行/seed/指标/聚合，以及把 C 独有 loss-weight 自由度和成本完整披露。按 D-043 已保存的 300-step 实测，保守假定两条额外路径都跑到 10000 updates 时，Set Transformer/MLP 约额外 `0.513/0.157` 小时，两臂总投影由 `4.367` 增至约 `5.036` 小时；真实增量随 C 已选 updates 下降。这是旧 profile 的规划外推，不是新实测 runtime，也不改变 operator 对云资源的控制。
  7. validation 改为纯 confirmation：所有 train/inner-dev 选择冻结后，新的 200 个登记 validation groups 只完整运行一次并报告，不选择 C weight、commit gate、lr、updates、checkpoint、method 或 endpoint。旧 arrays 即使保留历史 calibration bit，正式 validation runner 也忽略该分区；LOG-022 已查看的 4-group smoke 仍只是历史开发结果，不计入新的 confirmation。validation 输入是冻结模型与 200 groups，输出是一次泛化确认及完整失败；它不是 inner-dev、不是 test，也不能在失败后用于调参。
  8. 固定 `(0,0)` gate 下分别报告 `commit_attempt_rate`、实际 `commit_rate` 与 `executor_quarantine_rate`。前者是模型请求执行 argmax 的比例并固定为 1；实际 commit 还要求 executor legal；请求后因 executor-illegal 原子回退的比例单列为 quarantine，满足 `attempt=commit+quarantine`。相对旧 smoke，移除 confidence abstention 预计会给 E 的错误施加向上压力并可能扩大 A−E，但这只是预登记方向性风险，不是保证结果、gate 理由或成功条件。
- 备选方案：拒绝继续使用 AUC `2/4`，因为它没有 long-horizon 构念依据；拒绝从 probe 的实测 SD 或可达效应反推阈值，因为会把预登记变成事后调门；拒绝相对 baseline AUC 百分比，因为零/近零 baseline 不稳定且 A−C/A−E 会失去共同绝对门；拒绝 `lr×updates×weight` 36 格联合搜索，因为它给 C 更大的联合择优空间与选择噪声；拒绝继续用 validation 三选一，因为当前仍可在未读 validation 前完成同一有限选择。
- 机器合同与版本：`configs/m1_endpoint_viability_probe.json` 升为 v3，继续覆盖不变的 v6/v8 source protocol 与 train arrays digest；endpoint report 升为 v3，通用 A–F report 升为 v7，train/inner-dev budget report 升为 v3，runtime profile 升为 v2。活动 `m1_hard_condition.json` 暂不改 hash，以继续字节级复用既有 1000-group train arrays；它内部被 supersede 的 validation/gate 旧字段不能覆盖 D-046 overlay，等 probe 冻结 semantic 分支与 test N 后再一次性升级总协议。
- 影响：D-045 的指标名称、extra/missing、新写入/stale、false-birth、recovery null、固定 gate 与范围声明保持；只 supersede AUC 效应门/功效值和 validation 选择职责。当前 endpoint probe 与完整预算网格继续阻断，先在干净服务器对 D-044–D-046 全部实现跑 full test。full test 成功后才改写唯一入口运行固定 train-only endpoint probe；若其通过，再运行含 C 顺序权重搜索的两臂预算网格。
- 是否接触 test 信息：否。D-046 只使用代码/量纲审计、已登记公式、历史非正式 smoke 的尺度提醒和 D-043 planning-only runtime profile；未运行或读取 endpoint probe、validation/test，test 尚未生成。
- 验证方式：schema validator 锁住 `40/80`、8/16 暴露、不得按 probe 回调、顺序选择与纯 confirmation；功效单测锁住最低 200/向上取整；预算 helper 单测锁住 group-first 聚合、锚点平手与两条附加路径；causal 单测锁住 attempt/commit/quarantine 恒等关系。完成 Python compile、JSON 解析、shell syntax、定向测试与 diff 检查后，唯一服务器入口只运行全仓库测试，不生成数据、不训练、不读 validation/test。

## D-047 — M1 claim 边界与 H=1 主文 teacher 机制对照

- 日期：2026-09-08。
- 状态：accepted；在读取 endpoint probe、validation 或 test 结果前冻结，不改变 D-044–D-046 的方法、数据、候选、能量、co-primary、阈值或成败门。
- 用户确认：用户询问遗留的 teacher agreement、claim、online execution 与外生轨迹问题是否被遗漏，并授权在确认对论文有益时补正。
- 背景：M1-v8 health 的 `teacher_reference_agreement=1.0` 已按 D-044 披露为“软 executable hindsight distribution 的传播”，但 H=1 仍只是配置中的 `reported_ablations`/`retain_horizon_1_ablation`，没有固定比较量和主文职责；这会使“并非只传标签”的解释显得只靠免责措辞。研究合同的英文 claim 又继续把 `current and future projective consistency` 与 `minimal-world-change prior` 连在同一句中，容易把后者误读成与 future 同等级且已经验证的机制。另有两处系统边界需要拆开：online 网络评分时不展开候选 `post_graph`，但部署系统仍用共享 executor 应用最终选中的事务；M1 pose/trajectory 是生成器事先固定的外生观测流，不是机器人根据记忆主动选择的导航策略。
- 决策：
  1. 唯一 claim 改为：hindsight posterior 来自真实执行候选 world transactions；在 M1 中，执行条件下的当前证据和随后实际观测到的 future evidence 是主要评分信号，minimal-world-change 的 edit/growth cost 只称预登记正则，不称已验证主机制。中文主假设同步使用 persistent-world error burden，不再用 M1 的开放边代理泛称原始 Dynamic Contamination Rate。
  2. 论文和合同必须区分网络与系统：online network 只读截至当前的 world/observation/candidate program 并输出分数，不读 future 或候选 `post_graph`，也不在网络内展开全部候选；CPMT system 随后用所有方法共享的 deterministic executor 只执行最终选中的一个事务，再计算记忆指标。它既不等于硬编码 online updater，也不等于部署时没有真实 memory mutation。
  3. M1 的 world event、observation order、pose bucket 与 controlled-revisit action history 由固定 seed 在方法运行前预生成，并在所有方法间共享；它们不依赖 learned memory state 或模型分数。因此 M1 只检验外生观测流下的 online persistent-memory revision，不声称 active navigation、主动消歧或 action-policy learning。
  4. endpoint probe 在同一 201 个完整 train/inner-dev paired groups 上必报 H3-vs-H1 **teacher horizon contrast（教师视野对照）**。每个候选仍从同一 immutable base 真实执行，H=1 只把之后实际登记且有效的 counterfactual trace 从最多三步截为下一步；candidate program/order、current evidence、外生 event/pose schedule、now/edit/growth/collateral/illegal、energy weights 和 temperature 全部固定。online learning rows 中最后一个零-future step 与 recovery-only rows 排除。
  5. 两个 horizon 分别报告 teacher/reference argmax agreement、top-1 probability mean/median/fraction<0.60、posterior/uniform entropy；H3-vs-H1 报 total variation mean/median/p95/max、argmax change、`KL(H3||H1)` 与 H3−H1 reference probability，总体和逐 family 同报，完整 paired group 是独立单位。该结果必须进入论文主文而非只放 supplement。
  6. H=1 是 teacher-level 机制诊断，不重训一个 H=1 student、不新增第七方法、co-primary、显著性门或 multiplicity family，也不参与 exact/graded switch、test N、超参数、validation/test 选择或 M1 pass/fail。若差异弱或为零，必须披露并收窄“多步 future context materially changes supervision”的机制叙述；不得调能量、隐藏结果或修改 A-vs-C/E 主比较。H=5 保留为次级报告扩展，不承担本条主文义务。
- 白话：teacher horizon contrast 解决“老师第一名始终等于参考标签时，future 到底有没有改变监督”这一问题。输入是同一批已经执行的候选世界，H=3 看后面最多三次有效观测，H=1 只看下一次；输出是两份完整候选概率分布之间的 TV/KL、第一名变化和正确候选概率变化。例如第一名都还是 RELINK，但其概率从 0.35 变成 0.65，说明多步 future 改变了蒸馏信号。它不保证老师改写 hard label、不证明 A 已优于 C/E，也不新增一个必须“做出正结果”的门。
- 论文影响：该补正减少过度主张并把潜在弱点前置为可审计证据，整体有利于可信度。可能出现的代价是 H3-vs-H1 为零时机制叙述必须变窄，但这是真实边界；把它留到结果后再决定是否报告，对论文风险更大。
- 机器合同与版本：`configs/m1_endpoint_viability_probe.json` 升为 v4，endpoint report 升为 v4；新增可从重建的 train rollout audits 计算 H3-vs-H1 分布诊断的代码与单测。活动 `m1_hard_condition.json` 和既有 1000-group train arrays 内容/hash 不变；H=1 只在 train-only endpoint probe 重建 audit 时计算，不消费 validation/test，也不改变训练输入。
- 是否接触 test 信息：否。未运行 endpoint probe，未读取 validation/test，test 尚未生成；本条只使用既有代码合同、train-only teacher health 事实和用户提供的只读审计意见。
- 验证方式：validator 锁住 H=1 只改变 future horizon、201 complete groups、主文职责、固定输入、报告量和 no-gate/no-retune 边界；单测验证重算不修改 audit、排除零-future/recovery rows并输出有限分布指标；文档测试拒绝旧 claim，并要求 online/system 与外生轨迹说明存在。随后在干净服务器运行 D-044–D-047 full test，通过后才实现/运行唯一 endpoint probe 入口。

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

## D-048：probe 后组合登记与执行/信息边界修正

- 状态：accepted（2026-09-08）；依据用户授权处理已拉取的 D-047 结果。机械登记依据为 D-044–D-047 已冻结规则，数值及核查结果只记 EXECUTE LOG-052/053。
- 采用 `configs/m1_post_probe_registration.json` 绑定不变的 v6 生成来源、v4 probe overlay 与导出 probe，登记 exact、test 1350 groups、原 0.03/0.03/40 最小效应与 0.06/0.06/80 规划效应，test access=false。这明确替代 D-046/047“probe 后升级总协议”的单文件实现方式：组合合同是活动评测真值，旧来源 hash 继续验收现有数组；禁止用旧 test=200 直接生成正式 test。其余 overlay 安全/选择规则不变，S6 仍需单独重新冻结并实现消费登记的正式入口。
- 白话：输入是已完成 probe 和原冻结规则，输出是可由机器核对的评测登记；例如 exact 未退化就保留 exact，而非因谁赢改指标。它不是重新跑 probe，不授权 test，也不表示方法已过关。预算 runner 在读取 train 前验证登记并写入报告，来源协议与登记各保留独立 hash。
- 修正系统边界：当前生成器和评测器都执行候选；前者检查 canonical duplicate，成功返回恰为原 16 个的固定排列，否则报错。保留这一检查与全部历史数据；仅选中合法世界进入持续记忆。不声称已实现单次执行部署，也不将 forward latency 当系统延迟。M2 独立部署路径及无执行候选生成的等价性仍 planned。
- 披露 M1 合成器参考信息：A 的后续参考事务/结构观测与 C/E 的参考轨迹目标不等于真实传感器；当前不支持无标注视觉主张。分布 TV 不等于贡献比例或学生收益。发现影响在线选择的 future/post-world/reference 信息才修复并重验受影响结果；没有这类证据时不重构或重跑整个 M1。
- 因登记校验接入科学 runner、增加边界测试，下一唯一服务器阶段是全套验证；验证后再进入原预算网格，不混入训练、导出或 Git 发布。现有 probe/数组保留；不会靠改门槛、量程或加 M2 模型挽救 M1。

## D-049：S5 已选预算实体化、全 train 重训与可复用模型产物

- 状态：accepted（2026-09-09）；用户在了解预算训练与独立确认的区别后明确要求“给我指令开始做”。只落实 D-043/D-046/D-048 的后续训练，不改变方法、候选、能量、成功门、架构身份或搜索预算。具体科学结果见 EXECUTE LOG-059。
- 以 `configs/m1_s5_training_plan.json` 绑定两份已验收预算导出 SHA-256、逐方法选中 lr/updates、C 权重及各臂 E scorer 配置；机器验证 selected 必须与已固定报告完全一致。主架构 Set Transformer、次架构 MLP 都保留，五 seeds 7/19/31/43/59，不新增网格或根据最终成绩择优。
- 正式训练采用已登记的完整 1000 paired-group train：预算选择结束后，将其内部 201 组重新纳入训练，与另外 799 组合并。所有方法共享相同已有数组、原 transaction-labelled mask 与 10% 标签来源，不重新采样标签，不增加任何 validation/test 数据。重训后不再把 201 inner-dev 称为独立泛化数据；S5 新 200-group confirmation 仍只运行一次且不选参数。该全 train 拟合选择在访问 confirmation 前固定，不能因结果好坏退回 799 组。
- 白话：selected-budget refit（按选定配置重新拟合）解决“搜索已经选出了训练方法，但没有留下可直接用的权重”。输入是完整 train 数组与固定配置，输出是可加载的网络权重；例如 A 按登记的 3000 updates 重训一次，C 按其 10000 updates 与选定辅助权重重训一次。它不是重新搜索，不保证重训准确率等于原 inner-dev 数字，也不是在验证集上训练。
- 两臂顺序运行 CUDA、各 8 个 torch threads，不实施新分片/吞吐 benchmark。每臂五个 outcome scorer 和 25 个 A–E student，共 60 个独立模型产物；F 是确定性 oracle，无需学习权重。现有训练函数和目标公式保持原样；E scorer 的旧 API 第二个名为 validation 的数据参数明确使用同一 train 对象，只为生成 train 教师分布，不读取独立验证数据。
- 每个 `(architecture,seed,method)` 分别落盘 CPU state_dict、重建参数、固定 config、完整 trace、模型 hash、训练/数据/登记/code 来源及成本。E scorer 另保存其同一 train 上的教师分布，以免接续 E student 时重复训练 scorer。模型目录完成后原子发布并经同一加载函数核对；重运行只复用绑定和 hash 均一致的产物。单个模型中途失败保留 incomplete 目录及错误，不自动覆盖或重训；它不是逐 optimizer step 的断点恢复。
- 白话：可复用模型产物解决“终端重连后不知道哪个模型已经完成”。输入是一个模型的权重及其来源记录，输出是一个可校验的完整模型目录；例如 30 个模型已完成时，它们会被跳过，剩下的尚未开始模型才需要训练。它不允许换配置后继续复用旧权重，也不隐藏失败记录。
- `run_m1_s5_train.py` 仅承担 train-only 模型训练/保存，状态为 S5 preparation，`formal_run=false`、`validation_arrays_read=false`、`test_access=false`、`causal_complete=false`。S5 的数据生成/一次性确认和 S6 test 解封仍是独立后续阶段；本条不声称完整 S5 evaluator 已实现，不将训练完成称为 M1 通过。
- 因新增训练/存储代码和方案登记，先通过新的服务器完整测试，成功 marker 绑定 plan 与 src/scripts/configs/tests hash；旧 221 项 marker 继续作为历史事实但不能验收新代码。当前 ops 版本只承载该全测阶段，不预埋训练/导出/push。本地只做静态和纯元数据检查，含模型加载及完整套件在 AutoDL 上运行。

## D-050：固定 S5 独立确认范围、保存模型消费与连续评测接线

- 状态：accepted（2026-09-09）；用户在 D-049 训练报告本地复核通过后授权“可以，开始吧”。落实既有纯 confirmation，不改变 A–E、主次架构、已选权重、gate、三项主要指标、效应门或 test N。新代码的服务器验证仍 pending；不是实验成功。
- `configs/m1_s5_confirmation_plan.json` 绑定已验收训练导出、训练方案、原生成合同、probe overlay 和组合登记。补齐 D-036/LOG-025 要求的历史隔离：排除旧 validation 编号 0–3，新范围固定为 4–203（含端点），共 200 个完整 paired groups，保持原 validation seed namespace。此登记发生在首次生成或读取这批新确认数据之前，不能因数据健康或方法结果失败替换组、移动编号或增加组数。
- 白话：独立确认集范围解决“过去看过的例子混入新考试”。输入是历史用过的组号和原生成器，输出是冻结的 200 个新组号；例如旧组 3 被排除，新组 4 保留两条配对轨迹。它不是按模型分数挑样本，也不是新的任务或 test 解封。
- 新 `run_m1_s5_confirmation.py` 提供 generation/evaluation 两个独立命令模式，仍只能经当时版本的唯一 ops 入口交付。生成沿用现有 deterministic generator 和编码器，以既有 16-worker 路径参数/分片模式为模板，每个 worker 自己写一个完整 paired-group 的审计 gzip、学习数组和指纹；parent 按组号记录清单。重任务仍在 AutoDL，本地不跑 full suite、模型或 rollout；不添加 1/4/8-worker benchmark，不实施轨迹评测分片并行。
- 评测固定 CPU、1 个 torch thread、两臂/方法/seed 串行，直接读取原 50 个 student；10 个 scorer 只核对已保存产物完整性，不重训或重新形成 E 教师。F full-reference oracle 只跑一次并作原完整性检查，其结果跨两臂共享，不伪装为独立 seed；observable information oracle 单独跑一次作信息上限诊断，不能代替 F 或主对照。主架构仍 Set Transformer，MLP 是次架构，不按结果择优。
- 白话：保存模型的连续确认解决“单步分数看不出错误记忆是否积累”。输入是固定权重、当前观测和模型上一步留下的记忆，输出是完整 20 步选择与世界指标；例如第 6 步绑错后，第 7 步从这个错误世界继续。它不重置到正确历史，不训练模型，也不做未来 20 步的一次性答案预测。新范围每模型 400 条轨迹、8000 次决策，50 student 共 400000 次在线决策；两种 oracle 各另有 8000 次。
- 主要统计复用现有 `_paired_causal_statistics`：先在组内合并两 sibling 和五 seed，再做固定 seed=260906、10000 次 paired-group bootstrap。保留 exact/open-memory/AUC 的最小效应 0.03/0.03/40、三项 intersection-union 与两主对照 Holm 校正，以及 false-birth/collateral/active-node 安全非劣门。S5 输出完整结果后按既定 stop rule 复核；不自动解封 S6、不重选 endpoint 或训练设置。
- 额外固定参考历史的单步诊断只读学习数组中非 recovery 行，记录候选不可用、执行教师与参考的不一致、student 与教师的分歧及 template/argument 误差；它不能替代完整 8000 次自有记忆连续决策，也不把“student 与教师不同”一概称为错，因为教师本身可能错误。validation 不再切 calibration/report 子集，所有组保留一次确认职责。
- 白话：逐步审计记录解决“只知道最后错了却无法回查哪一步”。输入是选择已经结束后的候选执行记录，输出是压缩的逐步 online payload、候选合法性/失败、base/post hashes、选择概率及实际 sibling/sequence 标识；例如可以看到错误候选怎样进入后续记忆。它只在选择后记录，不进入网络输入或修改选择。参考历史下的六项候选能量和 future 分支保存在生成审计中，不冒称在模型分叉世界重新计算了 hindsight teacher。新增 callback 默认关闭；原候选生成、执行、网络和指标公式不改。
- 数据分片及每个完整 `(architecture,method,seed)` 评测单元原子完成并保存内容 hash。成功单元只能在模型/data/plan/evaluation-code 绑定一致时复用；partial 与失败记录保留、拒绝自动重算。validation trial 在首次打开新数据前落盘，即使随后失败也保留已消费事实；数据目录另写唯一 `confirmation_consumption.json`，绑定实际评测输出目录，防止换目录重开。生成数组及审计不改写，评测仅在数据目录新增这一控制记录。评测 binding 同时记录 PyTorch/NumPy/Python、机器与 hostname，防止不知情地混用运行环境。该记录不等于 optimizer 恢复，也不允许换配置重复考试。
- 成本逐模型报告 CPU wall_seconds 与实际 forward p95；保留原作用域“网络及相关张量/概率操作”，不平均各 seed 的 p95，不当作完整系统延迟。评测 CPU 的 peak_vram=0，训练 CUDA 显存另见原训练报告；串行/1-thread 是明确测量条件，不承诺操作系统不存在其他租户负载或把它称为独占硬件 benchmark。
- 因新增科学 runner、配置和只记录的 callback，下一唯一服务器阶段先运行完整测试（预计 250=234+16），成功 marker 绑定新方案及 source/tests hash。此 ops 版本不预埋数据生成、评测或导出；全测通过后按规则逐阶段改写入口。原 60 个已验收模型仍复用，不因新评测 source hash 变化重训。

## D-051：范围错误后的统一重建、重跑前统计规则与有界并行测量

- 状态：accepted（2026-09-09，实施分阶段 pending）。用户明确接受重训，要求优先论文可信度、检查选参并行提速并控制过拟合。依据是 LOG-067/069 的实现与影响证据，未看修正后数据或模型结果；本条 supersede D-049/050 对旧 60 个模型作为后续正式模型的复用安排，保留全部历史产物。机器计划为 `configs/m1_scope_rebuild_plan.json`；它不授权 test、不把旧 registration 的硬编码 1350 静默改成新结果。
- 修复定义：固定与生产一致的 node/edge/place/merge 查询检索集合，以不可变初始集合判断每条 open edge 是否相交，一次性纳入该边及两端点；不把扩展所得节点继续用于判定后续边。要求对边记录排列不变、候选无关、只读当前信息、ranks=3。这是恢复既有一跳意图的最小修复，不宣称数学上不存在其他可定义的范围函数；禁止仅把顺序敏感循环改名为多跳，不改成传递闭包，不删 C11 空候选断言，不添加补救对象。生产函数的变更单独 commit；测试、机器合同精确定义、dataset version/hash 与登记接线另行可审查，必须在生成修正数据之前完成，不能只等最终 test 时补文档。
- 重建范围：新输出目录中重建同一 seed namespace 的 1000 train groups，重新运行固定 train-only anchor probe、完整原预算网格、选定配置的 60 模型 refit，再生成同一登记范围的 200 validation groups。旧 59 个完整及 17 个 incomplete validation 目录、旧 arrays、模型、probe/预算/训练导出均不移动删除、不混入修正版。scope 同时影响候选、教师与安全指标，旧分数不冒充修正版结果。独立确认和 test 尚未做，不能把尚未运行的下游计成重复成本。
- 为什么重训：输入候选与软监督已实测改变，且 collateral 的操作性定义参与已登记安全非劣门 0.5/100，故正式数据、训练和评测须统一。单独改变指标只会必然要求重评，不是任何项目都逻辑上必须重训；本项目重训依据是这三项共同影响。保留相同网络、executor、方法、能量权重和全部效应门，不因旧结果偏弱加新正则、增强或模型。完整重跑原预算是这次 bug 修复的版本一致性处理，不是看 confirmation 不好后追加搜索。
- endpoint 在修正 probe 前固定：仍用 exact `final_active_graph_correctness`，support 与 open-fact AUC 不变；保留原完整 F integrity 和原各 co-primary/contrast 非退化条件。F 失败或任一所需指标退化均停止审查，不切 graded、不把零 SD 宣称为高检验力。原 exact/graded 的一次选择不重新开放。保留 0.03/0.03/40 最小效应、0.06/0.06/80 planning effects、两个主对照、多重比较与安全/invariant 门。
- 样本量在修正 probe 前固定规则：一次性使用同一固定 train-only anchor 的六个 co-primary×contrast paired-group SD，沿用原 z 值、planning−null 差及向上取整到 10 的公式，最终 N=`max(1350, 六格新需求最大值)`。禁止用观测到的均值差、validation/test 或新赢家回调效应门、endpoint、N；新 N 在进入模型 confirmation 前完成机器登记，之后不再估一次。若资源不足就暂停，不降低 N 或门槛。1350 若大于新公式需求，只称“保留历史下限的保守规划”，不保证真实 power 一定更高。
- 白话：带下限的样本量重估解决“修复后方差可能变了，但不能看结果随意增减考试规模”。输入是修正 train probe 的组间差异标准差，输出是最终组数；例如新公式要求 1200 就仍用 1350，要求 1500 就用 1500。它不是 test 中途加样本，也不是“任何预注册都只能上调”的通用定理。这里采用的规则需透明披露为 bug 修复后的预先计划变更；时间戳并不自动消除所有偏差。新 helper 尚未接入旧登记 validator，后续接线必须验证来源、六格完整性与失败条件。
- 控制模型及选参过拟合：paired group（含两个 sibling、全部步和 recovery）不可跨划分；预算仍为固定 799 fit / 201 inner-dev，五个登记 seed 等权且先按组聚合。保留三 lr×四 checkpoint、C 的两阶段权重选择和原平手规则，不扩网格、不选幸运 seed、不按结果选主架构。runner 后续增加同口径的 fit/inner-dev checkpoint 诊断及差距，作用仅为诊断；不能按差距新增阈值选模型。inner-dev 最优成绩存在选择偏差，selected-vs-runner-up CI 不是独立方法显著性证据。全 1000 组 refit 后不再把原 201 组当独立泛化评测；S5 只确认一次、不调 lr/steps/权重/gate，按原 stop rule 处理，不因结果不利重开搜索。
- 白话：选参过拟合指反复试模型后，把碰巧适合选参集的配置选中。输入是多个候选配置在同一开发集的分数，输出是可能偏乐观的最优分数；例如训练准确率和 inner-dev 都高，也不能保证新房间可靠。固定搜索范围与独立 confirmation/test 控制这个风险，不能保证没有过拟合；同源合成 test 也不等于真实视觉泛化。后续真实场景证据仍按 M2/M3 与 M1 stop rule 执行。
- 并行以独立训练路径为单元：使用新 Python 子进程隔离模型、optimizer 与随机数状态，不用多个 Python 训练线程共享 `torch.manual_seed`；不拆一个模型的梯度/updates，不使用多卡 DDP，不增加 batch size 或删 steps。现有每条 lr 路径训练至最大步数、读取四个 prefix checkpoint 的复用保留。scorer 完整五 seed 汇总选择后才启动依赖它的 E student；C 的计算格选择完成后才补权重路径，parent 按固定任务键汇总，完成顺序不决定选参。
- 本轮先用原 train 数组运行已有 `--runtime-profile-only` 的固定 300-step scorer+A–E 短任务，比对 `(processes, threads)=(1,8),(1,1),(2,1),(4,1)`；每配置同样四个任务（两次 Transformer、两次 MLP），只导出耗时/资源，不导出科学分数、不选超参数。读取 cgroup/affinity 的 CPU 容量、可用主存与 GPU 余量，保守预算不满足则预先跳过配置。调度候选取距最快耗时 5% 内进程最少、再线程最少者；这是性能初选，不是完整预算 ETA。完整预算路径分片尚未实现，后续须验证固定随机流/输出与汇总等价并复核新数组资源，不能把本次测速称为已验证的数值等价。评测延迟另用串行条件测，不用并发抢资源时的数值充当部署延迟。
- 论文解释：旧/新分布差异说明硬标签不含完整教师分布，不直接证明软监督改善学生或 CTL 有效；候选同时改变还形成混淆。新旧结果一致或不同都必须完整披露，但不保证能够发表；正式 A–C/E 的长期优势、效应门、安全和机制证据仍是核心。相同超参只说明此次修复下的选择一致，不泛称超参全局不敏感。
- 是否接触 test：否；本条使用原 train 诊断及公开方法资料，未生成修正数据、运行修正 probe、读取模型 validation 指标或 test。方法依据：[Cawley & Talbot 2010，模型选择过拟合](https://www.jmlr.org/papers/v11/cawley10a.html)、[COS 预注册与变更披露](https://www.cos.io/initiatives/prereg)、[PyTorch 多进程与 CPU 过量分配](https://docs.pytorch.org/docs/stable/notes/multiprocessing.html)。这些资料不替代本项目的机器边界检查。
- 实施定位（2026-09-09）：生产一跳改动单独提交 `31f0e0f`；修正生成合同独立保存为 `configs/m1_hard_condition_v7.json`，protocol=v7、dataset=v9、规范化 SHA-256=`adc6badc93dcca11904e12cb93396d26c3a4e728ccf438ce9a3a4f442f93901f`，由 rebuild plan 绑定。它与旧合同的语义差异仅为两个版本标识及新增精确 scope 定义；其余数据、seed、模型、预算与门保持原值。v6 只读历史验证保留，新 rollout 生成要求 v7/v9；审计来源必须匹配新编码/执行路径，已有 shard/output 不覆盖。生成基合同中的 test=200 仍只表示原基础规模，不能用于正式 test；D-051 的至少 1350 与一次性六格规则须由后续新组合登记消费。当前阶段只有完整回归测试，尚无修正数据、probe、预算或模型；这些后续结果不得绑定到旧登记或旧成功 marker。

- 选参前工程门补充（2026-09-09，用户接受，修正 train 尚未生成）：1000 组 train 生成及健康验收后、固定 probe/昂贵预算前，检查固定 train 组 `[0,66,133,199,266,333,399,466,532,599,666,732,799,865,932,999]`，每组两条 sibling、每条 20 步。七种规则为 NOOP、优先 MERGE/RETRACT/RELINK/SPLIT/BIRTH、固定哈希随机选择（seed=260909），共 224 条轨迹、4480 次决策。选择只读静态预检、模板和位置，不读执行结果、参考、教师分数或 future；优先模板不可用则选择 NOOP 并记录次数。这些是工程压力规则，不是新 A–F 方法。
- 白话：输入是固定 train 场景和选择规则，输出是完整性结果及失败现场，用来提前发现记忆被错误修改后下一步可能崩溃。例如连续合并后仍须能生成候选；有限轨迹不保证每步都选错，也不证明全部可达状态安全。构造异常、K=16 坍缩、base 改写、图 invariant、C11 范围外目标或 MERGE 配对检查失败均暂停预算，不吞错、不换组。已构造候选的 executor-illegal 沿用原 QUARANTINE，保留世界并记录，不单凭它判工程失败。
- 只重建这 16 组审计，重新编码须与已验收 train 分片 digest 一致；不重建全部 train、不查看 validation/test。检查代码先放隔离分支，当前生成结束后再合入，以免运行中源码漂移。分别记录生成和检查来源，确认生产模块未变；旧全测不冒充新增检查代码的测试证据。
- 不改 D-051 的 exact/support/AUC、安全 margin、N 或选参规则，不按压力结果扩模型、扩网格或恢复 M2。工程 PASS 不等于 CTL 通过。检查使用 CPU 子进程、每进程一线程，按 30 分钟规则交付；并行预算完整接线和 fit/inner-dev 同口径差距诊断仍待后续实现。

- 选参前交付范围补充（2026-09-09，用户再次要求优先检查）：除固定错误分支检查和原定 probe 外，将并行预算接线、fit/inner-dev 同口径诊断及后续实际公共路径的小样本贯通作为完整网格的前置工程条件。贯通只用运行前固定的 train 子集与短训诊断权重，覆盖保存/加载、完整 20 步、paired-group 汇总、统计和导出；不另写简化评测器冒充正式路径，不读取 validation/test，不用诊断成绩选择配置。该路径仍 planned；明确先实现和验证，再开始昂贵选参，不能等完整模型训练后才补评测接线。具体顺序只维护在 M1_V2_CLOSEOUT_FLOW.md；方法、网格、效应门、N 规则及 test 解封权限不变。

## D-052：阶段内一次同步、固定分步命令

- 日期：2026-09-09；状态：accepted。用户明确取消唯一入口和逐步反复 pull，要求提前准备一个阶段的脚本，再按部就班交付指令。
- 决定：同一已确定阶段的功能入口一次准备、检查、提交并推送，阶段开始同步一次，之后运行固定命令。可用多个 ops 脚本、阶段子命令或直接调用正式 runner，不再每步改写唯一入口，允许提前实现后续步骤。当前运行任务不迁移、不重启，历史脚本和记录保留。
- 白话：输入是阶段协议和依赖，输出是同步一次后可依序执行的短命令，解决每一步都要改入口再 pull 的摩擦。例如检查、选参、导出脚本提前备齐，但缺少合格预算产物便不能导出。它不是无条件串行运行全部工作，也不授权临时改方法或解封 test。
- 边界：各步自动核验输入、成功标记及冻结登记，保存输出和退出证据，复用成功任务，失败保留并停止依赖步骤。新科学决定、必要修复或新能力仍可能需要新提交和再次同步；运行中的 checkout 不 pull，不为步骤切换重训或重测。
- 影响：替代 AGENTS 中唯一活动服务器入口、每版只承载一个功能、不得预写后续步骤和逐步改写/推送的运维限制。历史 D-049/D-050/D-051 的对应交付措辞保留为当时安排，不继续约束新交付。科学方法、数据、效应门、样本量、安全、test 封存、30 分钟分界及精确路径 Git 收尾不变。本次只改工作规则和流程说明，不增加实验 LOG，不改当前生成脚本或科学源码。


## D-053：对象耗尽后的显式不可用槽位诊断（尚未采纳为正式评测规则）

- 日期：2026-09-09；状态：accepted 仅指有界工程诊断的实现和执行，正式候选/评测语义仍 proposed。用户要求继续定位并在长训练前处理 LOG-078 的失败。不得把诊断 PASS 当原严格工程门 PASS 或直接开始预算。
- 设计：新增显式 `allow_unavailable=True` 诊断模式；原参考生成、教师生成、模型评测和 CLI 默认仍严格，C11/MERGE/K 断言不删除。诊断保持 16 个输入槽位、原模板布局和 seed 排列，正常构造出的事务照旧在同一 immutable base 上真实执行。无法构造的槽位用 `slot_status=unavailable` 与原因表示，所有方法共用的准入值为 false，不产生 post-world，`execution_attempted=false`；它不冒充合法 NOOP，也不冒充 executor 已经运行后失败。
- 白话：显式不可用槽位解决“只剩两个对象时，固定长度网络仍需要 16 格输入，但不能虚构第二对合并”的问题。输入是当前世界和当前查询，输出是原位置上的真实事务或不可用记录。例如一个 MERGE 仍可尝试，第二个 MERGE 槽位标明缺少不同配对，其余动作继续竞争。它不是新事务类型、不增加对象、不恢复正确答案，也不保证剩余候选里一定有正确修复。
- 诊断处理范围预先固定为：不足两对 MERGE、C11 范围外目标为空、SPLIT 源没有可分配证据、canonical 等价候选去重后留下空槽。前两项来自真实失败，后两项来自相同耗尽路径的代码检查。canonical 重复的原程序保留审计，但不可用槽位不会再次执行它。既有生成器已使用执行后 canonical 等价去重；本诊断不读取未来、reference 或模型分数来选择不可用槽位，不把重复检查称为纯静态预检。未知 schema/索引/图错误继续抛出并记录，不用 broad except 全部改成不可用。
- C11 的参考场景合法 collateral 对照和 family coverage 仍必须成立。错误累积图上的 C11 无目标在诊断中逐步记录，不移除该组或时刻，也不把该情况宣传成安全改善。正式接入前仍须明确 unavailable、executor-illegal、candidate miss 与 C11 stress availability 的独立报告口径；本次不修改正式 collateral 分母或成功门。
- 有界执行：读取已导出的固定失败报告及其 hash 绑定的 16 组 reference_audits.json.gz，不生成新 train/validation/test。每组先对 40 个普通参考步骤、2 个恢复步骤比较默认严格模式与诊断模式的程序、证据，并与保存程序/执行记录比对；仅验证这 16 组，不能声称覆盖全部 1000 组。随后同一 16×2×7×20 矩阵按原七种规则完整检查，各分支失败保留现场后继续检查其他固定分支，任何失败均使总 gate=false，不挑换组。
- 新模式只在显式诊断 runner 使用。参考严格模式的旧错误应继续复现，正常状态不应改候选；旧 arrays、模型和失败报告均保留。是否需要重新生成数据须依据最终正式修复及来源兼容性决定，不能因本次局部快照成功直接承诺复用全部 train。原 N/效应门/模型/预算/选参规则不变，正式 test 仍封存。
- 运维交付同一版本的 `ops/m1_candidate_availability.sh test|check|export`：先服务器完整测试，再复用审计跑 CPU 最多 4 worker 的诊断，最后导出。全部前台，源码与测试/ops/hash 绑定，失败/中断不自动重启，成功或已完成失败可验收导出；原检查目录和报告不覆盖。正式模式接入、组合登记、预算并行和后续路径贯通仍是后续工作。


## D-054：正式评测采用共享不可用槽位，保留严格生成与原科学门

- 日期：2026-09-09；状态：accepted（用户在 LOG-080 报告复核后要求继续正式接入）。依据 D-053 的 299 项测试、640+32 保存参考步骤一致及 4480 次压力决策完成；新正式评测接线的服务器验证仍 pending。本条正式采用候选可用性规则，替代 D-053 中“正式采用仍 proposed”的状态；不覆盖旧严格诊断 FAIL，不授权完整预算或 test。
- 机器策略独立保存在 `configs/m1_candidate_availability_policy.json`，policy_id=`shared_explicit_candidate_slots_v1`。生成协议 v7/v9 保留为已有 train 的来源；新的 self-rollout 评测必须显式携带此完整策略并写入结果/后续组合登记。缺失策略的历史调用继续严格，错误/漂移策略拒绝。S5 配置只允许从 evaluation plan 注入，不能由保存模型配置私自启用；旧 v6 post-probe registration 不冒充新登记，修正固定 probe 和最终样本量接线仍按 D-051 后续落实。
- 语义：网络保持 16 个固定位置、原候选布局与 seed 排列。实际存在的事务继续从同一 immutable base 克隆并真实执行；缺失位置以不可用记录表示、准入值为 false、没有 post-world，不调用 executor。所有 A–F 共用同一候选生成与准入边界；canonical 去重仍由共享生成器执行审计后完成，不宣称该部分是纯静态预检。NOOP 仍是真实且唯一的保留动作，不能用多个合法 NOOP 填空。未知构造异常继续失败，不能概括吞错。
- 参考生成、教师构造和学习数组编码继续严格：在参考状态必须具有原 16 个去重候选、合法 C11 对照及原正例/coverage 条件。对象耗尽后的不可用槽位只改变原先无法返回完整列表的 self-rollout 状态；不补对象、不修改观测、不重写 reference、不换组。coverage@16 的既有参考生成健康门不改；另报告自有历史上是否存在能达到当前参考语义状态的可选合法候选，不用这个新诊断另设通过门。
- 分开记录：`unavailable_slot_count` 是没有可执行事务的位置数；`executor_illegal_candidate_count` 只计实际尝试后拒绝的真实事务，不把不可用槽位算进去；`exact_reference_reachable` 是选定动作后才用参考图审计当前可选合法候选的语义可达性。白话：输入是本步已经构造/执行的候选和评测参考，输出是失败来自候选缺失还是学生选择的诊断。例如所有可选世界都仍缺少已误删的对象，就记“本步参考语义不可达”；它不等于证明候选生成器独自造成错误，因为以前错误动作也可能是原因；更不读参考替模型选动作。它不等于完整证据记忆正确性或教师普遍纠错。
- C11 分别报告当前范围外目标是否存在、指定合法连带对照是否实际可用。`c11_events` 分母保留所有 C11 事件；无目标、不可执行对照均单列，没有 C11 的汇总返回 null 并保留零分母。原 20 步、paired group、安全 collateral/false-birth/invariant 与三项终点分母、阈值及通过规则全部不变；既不删除无目标时刻，也不把条件可用性比率替换原安全量。空槽位不被选中，所以不会自动产生“模型执行成功”或“更安全”的成绩。
- train 复用采用 `configs/m1_train_reuse_policy.json` 来源桥接：固定原生成提交 `ee1af48eb9d6337e0f22a23b34c1042d00cf715b`、原 generation.ok.json hash、原 arrays digest、两份失败/诊断证据及逐文件已审查源码差异。生成器/encoder 以外的依赖不得新增未审查改变；m1_af_rollout 的训练/编码定义与原生成版本比较 AST，仅允许 causal evaluator 和其新诊断 import 不同。m1_rollout 默认严格路径差异经审查后按精确规范化文件 hash 锁定；这不是仅凭 16 组数值一致就假设任意源码兼容。
- 白话：来源桥接解决“数据没有变，但新增评测代码使全局源码指纹变化”的问题。输入是原验收 marker、1002 个文件指纹、原生成提交和经过审查的精确改动，输出是可追溯的复用记录。例如保留原 train.npz 的来源，另记新评测版本；它不是给旧数据改生成日期、不等于全 1000 组重新生成并逐值对拍，也不能用于未经审查的候选或监督变更。若任何原分片/hash/编码定义或已批准源码差异不符，则停止并审查，不覆盖 marker 或自动重建。
- 当前服务器阶段一次性交付 `ops/m1_candidate_policy.sh test|reuse|export`：前台完整测试含实际 causal evaluator 的一组固定 train 集成测试，再只读校验 1000 个分片和合并数组/manifest（1002 文件），输出独立复用报告。测试中的固定小型 train fixture 不是重新生成 1000 组；不运行上次已经成功的 224 条诊断、不训练模型，不读取正式 validation/test。失败保留并可导出，成功不授权预算；固定 probe、并行网格接线、真实保存/加载/统计小预演仍须按流程完成。


## D-055：修正版 S5 独立确认绑定及整阶段交付

- 状态：accepted，用户在修正版选参/60 模型 refit 报告复核后授权准备 S5（2026-09-10）。本条落实 D-050/D-051/D-054 已固定的确认方法与运行边界，不重新选择方法、参数、效应门、endpoint 或 N。
- 新机器计划 `configs/m1_s5_confirmation_v7.json` 钉住 LOG-088 的 checks/budget/refit 三份导出 SHA-256、修正训练来源及组合登记。历史 v6 S5 合同和失败数据保持原样。新数据仍为原 validation seed namespace 的编号 4–203，排除 0–3，共 200 paired groups、每组两条 20 步。不因健康门、F 或模型结果失败换组、追加样本或重新生成另一批验证数据。
- 来源复用：新阶段逐文件核验 `4c89e59` 中既有 src/scripts/configs 未改变，新增阶段文件单独由当前完整测试覆盖。先核验并 CPU 加载全部 60 个已保存模型，不重训评分器或学生。50 个 A–E student（两架构×五方法×五 seed）各跑 8000 次连续决策；共享 F 和 observable-information oracle 各跑一次，分别保存其 8000 次轨迹，后者只作信息上限诊断。架构主次保持，不根据 validation 选择赢家。
- 新接口只补固定 train 第 1 组的小预演：新分片写入/读取与已验收 probe 审计重新编码 digest 对拍；两架构 A/C/E、seed 7 的现成正式权重共 240 次决策，两个 oracle 共 80 次决策。小预演不重训、不重做原固定 probe/预算/四进程等价检查；结果不参与科学参数选择。它检查新增写入、oracle 接线及正式权重消费，不保证未见的 200 组不会触发其他工程错误。
- 生成最多 16 CPU worker，按实际 cgroup CPU/内存余量下调；评测复用已验收的 paired-group 四 CPU worker、各一个 Torch/BLAS thread，两个 sibling 保持同一任务、20 步状态串行传递。模型之间按固定顺序执行。每模型关闭评测进程池后，用同一已保存在线输入独立串行重放网络前向，并核验 argmax 与原选择一致；不平均 worker p95、不称为系统总延迟或机器全局独占测速。记录模型评测/重放 wall-clock、CPU 条件和 peak_vram=0。
- 统计复用已验收的 `registered_statistics`，沿用原 10000 次 paired-group bootstrap、五 seed 组内合并、安全非劣门与主比较 Holm 校正；不增加指标成败门。单步 reference-history 诊断沿用原 teacher_forced/selection_error_decomposition，排除 recovery，分别报告候选不可用、teacher/reference 不一致、student/teacher 分歧和 template/argument；这些不是独立于 validation 的调参数据，也不替代完整 self-rollout。
- 防止换目录重开：生成前在 outputs 根的固定 `m1-v7-d055-s5-validation-reservation.json` 写入当前来源、计划及唯一输出；评测在打开 validation arrays/audits 前另写 `confirmation_consumption.json` 和 trial 回执，绑定数据 manifest、已选模型、代码及 Python/NumPy/Torch/platform/hostname。不同绑定拒绝运行；partial/失败原地保留，不自动重试或覆盖。成功单元仅按原绑定复用。这是一次确认的消费约束，不是 checkpoint/optimizer 断点恢复。
- 阶段完整交付 `ops/m1_corrected_confirmation.sh test|prepare|smoke|generate|export-data|evaluate|status|summarize|export-confirmation`，同步一次后顺序执行。全测、准备、小预演、生成和汇总默认前台；完整评测预计超过 30 分钟，默认后台并明确 `completed=false`。忙锁返回非零且说明动作未执行，避免将 launch 的 EXIT=0 当成训练/导出完成。已完成模型/数据/逐例轨迹的详细产物保留服务器，导出使用不同职责的 data/confirmation 两个精确 results 路径。
- 完成后仅报告 S5 确认及既有检查结果，交由原 stop rule 复核；不自动生成 test、调整 N=1350 或放行 S6。本阶段未在本地生成/读取正式 validation/test；服务器全测、小预演及确认均 pending。
- 白话：本次绑定解决“旧模型已经训练完成，新验证入口怎样可信地接上”的问题。输入是验收过的模型、冻结参数和固定 200 组范围，输出为一次独立连续验证的逐例记录、配对统计及来源。例如先把第 1 组 train 用新读写接口走通，再一次性评测 4–203 的 validation；不能看到 C 不好就改权重再考。它不等于重新选参、M1 已成功或 test 已解封。

## D-056：已有参数角色分离的独立原型工程阶段

- 状态：accepted，仅限原型实现与工程验证。用户明确允许依据 M1 结果优化 CTL 架构，并在 LOG-097 后授权继续（2026-09-10）；这不把尚未运行的角色编码实验登记为有效方法，也不重新放行 S5/S6。
- 新模块 `m1_role_encoding` 保留旧上下文及 33 维候选块，按五类结构化参数角色对原三条 query 追加 35 维匹配信息。固定 `pooled_v1`、`pooled_padded_v1`、`argument_roles_v1` 三个模式：旧编码兼容锚点、同宽度补零对照、角色版本。新增特征所用 ID 集合必须与旧提取器一致，不引入 merge_queries，不删历史计数，不修改候选、执行器、teacher、标签、六项能量、mask、损失或 A–E 方法定义。
- 在原数组构建及因果 rollout 函数增加显式可选编码回调，默认仍使用原 encoder；新适配器把同一模式用于训练行和每步自身状态输入，校验模型/配置维度并限 train audits。候选维度不同的新模型不能直接复用原 checkpoint；未来保存模型须绑定编码模式，两个 68 维模式不能仅凭维度识别。
- 本阶段只生成一个 train paired group 的工程夹具，检验旧字段逐位保持、非 x 数组完全相等、角色提取、候选置换、输入边界、同宽度模型参数与初始化相等以及 40 步动态接线。两个架构的小模型只前向，不执行优化器；固定分数模型的 rollout 只作工程断言，不估计方法效果。入口及可复用成功/失败证据见 HARD_CONDITION_EXPERIMENT.md 的 D-056 小节。
- 2026-09-11 用户补充本机 CPU 有问题，授权转服务器检查并继续采用由用户运行命令的方式。停止在本机重试；本机九项成功记录只作历史证据，不认证当前版本。新增 ROLE-S1/S2 服务器入口重新运行这九项以及原二十八项 A–F 回归（旧测试自行生成少量 train/validation 夹具，不读取 S5/test 数据），独立记录服务器源码、环境、日志和退出状态。服务器两组检查均通过前，不启动新训练。本条属于同一原型工程阶段的验收环境修正，不是新科学方法或预算变化。
- 计数修正：初版入口把二十八项误写为三十项，服务器实际成功后被错误拒收。按源码中显式 unittest 方法清单修正为 9+28=37，并核验日志中逐个测试名称。增加只读 recover，严格复用已完成且科学代码/测试源码不变的旧服务器回执；不增加、删除或跳过任何科学测试，不改统计验收标准，不自动重跑。新报告分别绑定当时执行代码与修正版验收入口，保留旧 failure.json，不能把真实测试失败或其他失败原因当作计数问题修复。
- 科学开发训练的数据、预算和新确认规则仍 pending，不在本阶段重训、选参、读取已有 S5 作新方法确认或解封 test。旧 S5 no-go 与历史报告保持；修改了共享科学模块后，不沿用旧 source hash/test marker 认证新版本。旧字节绑定的只读诊断报告应在原提交复核，不为了让历史 verify 通过而重写旧报告。
- 白话：这项决定解决“优化方向已有线索，但怎样把一个改动独立、可比较地接入现有系统”的问题。输入是原在线信息与候选参数，输出是可切换的角色原型及补零对照。例如比较同为 68 维的角色版和补零版，可以控制总参数数目；它不等于证明角色版更好，更不等于旧 M1 已通过。理论上可忽略新增特征，实际训练仍可能过拟合或放大 query 捷径。

## D-057：角色编码的固定小预算开发试验

- 日期：2026-09-11；状态：accepted，用户在 D-056 的服务器工程验收后明确提出“可以先小规模看一下效果”。授权限以下有界开发试验，不重开旧 S5、不解封 test、不扩模型进入 M2。工程验收与角色方法有效性仍分别判断。
- 固定 configs/m1_role_pilot.json：旧 0–999 训练编号之外的 train 1000–1019 共 20 paired groups，沿用原哈希取模划分，12 组拟合、8 组 inner-dev；两 sibling 和恢复训练行不跨集合。拟合 480 行、留出 320 行，另在全部 16 条留出轨迹上各做完整 20 步自身状态评测。新样本保持原生成合同和 label mask，不改为全部有标签，不按健康门或模型表现换组。
- 三种编码 × A/CTL、C/direct future loss、E/future scorer without execution × seed 7/19，共 18 个学生、6 个 E scorer。全部使用原主架构 128 维两层四头，固定 student/scorer 各 300 步、lr=0.0006、batch=64、aux/distill weight=1、gate=(0,0)，CPU 单线程；无选参、无最佳 checkpoint、无旧模型权重复用。E 的额外 scorer 成本单列。同宽度补零与角色版是主编码对照，参数数目、初始化及批次随机序列匹配；33 维原版只作兼容锚点，初始化消耗的随机数不同，不称三路逐参数/批次均相同。
- 实验目标是观察固定短预算下的改善信号，未设新的正式科学通过门。逐 seed、逐 paired group 全部导出角色减补零，以及每种编码 A−C/A−E 的描述差值；正确性越高越好，错误事实累计负担越低越好。不把两个 seed 当新增独立组，不报小样本显著性，不挑好看的 family 或 seed。C06/C08 的新身份混淆及条件分母、全图/完整证据记忆、累计错误事实、C10 索引分歧、候选可达性均报告。
- 共享模块只为 run_af_method 增加可选 causal_evaluator，默认路径不变；role adapter 仍同时约束训练和动态在线编码。正式损失/teacher/候选/executor/六项能量/label/mask 不复制、不修改。新捕获回调沿用原数组构建器实际发出的行，一次计算监督并生成三路 x，机械断言所有非 x 字段一致。
- 当前阶段全部入口一次交付：服务器新入口专项检查、两 worker 生成、两 seed 分块训练评测、导出/核验。旧 37 项不因阶段切换重跑；旧回执仅绑定历史工程证据，新入口由新专项检查覆盖。每组/每模型独立 marker、manifest 和 digest；仅复用完整成功单元，partial 不静默重训、不覆盖。模型在 rollout 前保存并严格加载验证；完整执行分支和失败保留 outputs，导出结果及其来源到 results。
- 白话：这项试验解决“代码能运行之后，值得不值得继续研究这个改动”的问题。输入是同一批新程序化场景和固定小预算，输出是角色版、补零版及原版在真实连续修改世界中的差异。例如角色版 C06 错误下降，但 C10 证据支持错误增加，必须一起解释；它不等于充分训练的最终比较，也不能证明模型学会了视觉身份推理。短训欠拟合、小样本零/少事件、角色稀疏过拟合及强化既有 query 捷径都可能影响读数。
- 本轮不加入 merge_queries，不删历史计数，不加风险损失或自身状态重采样。无信号不能断言角色特征普遍无效，有信号也不自动授权扩大运行。任何正式有效性主张仍需单独冻结不参与本轮诊断/开发的确认数据与 query 依赖对照；当前尚未设计或运行该确认。

## D-058：保留 M1 负结果，转入独立的 M2 公开观测接入

- 日期：2026-09-11；状态：accepted 仅指用户明确提出“直接到 M2，先把公开数据集转成……LATENT 结构”所授权的阶段转向与接入工作；具体数据源、前端、样本规模和正式比较配置仍 proposed/planned。本条明确替代旧流程中对本接入阶段的“M1 成功后才可进入 M2”限制，不把 S5 no-go 改成通过，不重开 S5/S6，不解封 M1 test，也不把 D-057 小试验当放行证据。
- 原因：用户希望直接检查新到达的真实观测如何影响旧记忆，并要求解决 reference 参数派生查询的答案代理问题。“合成数据训练足够久必然使方法趋同”不作为已成立的科学依据；转真实数据也不预设 CTL 会获胜。论文须披露这是看到 M1 结果后作出的新研究阶段选择，旧协议失败照实保留。
- 接口原则：复用事务/执行合同和监督比较职责，重新建立视觉观测、学生旧记忆、教师未来证据、审计真值的来源边界，不强制复用旧输入维度或权重。不添加 M1 的 merge_queries 配对分；M2 的检索和候选均从允许的视觉/几何证据形成，不把真实数据标注 ID 编成查询。合法视觉配对相似度不是禁止项，但不得以正确目标或候选构造名次作身份线索。
- 教师同样需要适配：未来真实观测用于评价独立执行后的候选世界，不直接重放正确后续事务或读取真值身份来伪装未标注视觉监督。固定/轻量 PNO、数值 latent 更新和完整视觉 rollout 仍待实现；不得把特征缓存称为这些模块已经完成。
- 当前边界：先做公开训练部分的小样本可追溯接入、前缀/标注干预检查和候选/修复机会诊断；源数据与计算均在服务器处理。先确认数据可用性，再一次准备该阶段固定命令。不启动未冻结的训练网格，不更换样本寻找正结果；实际训练前另行落实共享前端、A–E 公平条件、split、预算和评价合同。
- 数据来源允许优先考察公开实采具身序列，替代旧设计把模拟器作为 M2 主来源的唯一默认。3RScan 与 Aria Digital Twin 的适用性和局限见 DATASETS.md，尚未选定正式数据。后续 M3 的独立来源及隔离规则仍须明确；同一场所、同源扫描或参与开发的数据不得再次冒充外部未见验证。
- 白话：这项决定解决“程序化接口的答案线索可能妨碍检验真实记忆修订，下一步怎样换到可观察证据”的问题。输入是当前公开观测及过去记忆，输出是与审计答案分开的 latent/候选接入。例如椅子移动后应由当前外观和几何支持 RELINK，而不是读取它的真值 ID。这不等于否定 M1 的工程价值，也不等于用 M2 的潜在好结果挽救原 M1 结论。方案细节复用 M2_DESIGN.md；本条无新实验结果，不追加 LOG。

## D-059：数据先行、可彻底重构 M1，由用户审查科学代码

- 日期：2026-09-11；状态：accepted 指用户授权“先看数据，再根据数据看 M1”、可以彻底重构 M1，并要求完整分步计划和亲自把关代码。具体 32 步安排、模块合同、样本与预算仍按计划审查，不因本条自动变为已实现或已冻结。
- 替代 D-058 仅做 M2 接入的范围限制：可以依据真实数据重新定义 M1 的观测、旧记忆、候选、教师、标签和评价合同，不要求兼容原编码维度、family、K、权重或旧检查点。新协议保留 CPMT/CTL 唯一科学问题、执行/在线边界、C/E 强对照及首篇任务范围。旧 M1/S5 no-go、历史源码和运行产物不覆盖，旧 test 不解封。
- 顺序：公开数据审查→新观测/记忆合同→重构 M1→小试及独立检验→M2 自身记忆连续运行→M3 独立来源→论文/artifact。工程夹具、真实观测上的受控错误、自然发生的连续错误分层；不能拿真实数据集的真值 ID 重新构造答案 query，也不能以“合成数据长训必然趋同”为已经证实的重构理由。
- 用户把关：科学代码先形成职责明确的可读提交及具体输入/输出、必要测试和未解决问题，再交用户审查；批准前不合并为新科学基线或消费其效果，不堆叠后续科学模块。允许在同批次运行必要服务器工程检查供审阅，修复后的科学行为再展示。完整计划中的 R1–R7 集中审数据、合同、世界/候选、教师/对照、小试、独立检验及视觉/外部结论，不把每个成功命令都变成审批。
- 计划书复用 M1_V2_CLOSEOUT_FLOW.md，扩展其职责并保留原 v7 历史流程；它仍是唯一阶段计划和当前指针，不另建平行 roadmap。M2_DESIGN、DATASETS、REPRESENTATION 和 HARD_CONDITION_EXPERIMENT 继续分别维护方法细节；新协议实施时显式分开历史与新合同，不能静默改写旧规则。本轮只交付计划，没有科学代码或实验结果，不追加 LOG。
- 白话：这项决定解决“模型已经训练完，用户才发现题目和输入设错”的问题。输入是你能看到的真实帧、逐模块源码及运行证据，输出是经审查后再推进的研究链。例如先审查节点是不是从过去观测形成，再审候选是否读取答案，最后才审训练结果。这不等于承诺彻底重写每个已有函数，也不等于你批准计划后所有将来的方法变更都无需审查。


## D-060：重组文件并删除重复文档体系

- 日期：2026-09-11；状态：accepted，用户明确要求“彻底重组，不要只是添加，该删的就删”。本次为职责和导航整理，不改变科学算法、旧门槛或运行产物。
- 活动文档归并为 docs/PLAN.md、docs/METHOD.md、docs/DATA.md；README 为唯一导航，EXECUTE 合并主张证据表并移除过时任务清单，DECISIONS 保留决定历史。替代 D-035/D-059 对旧流程文件名和旧词典/确认表索引的固定要求，仍只有一份阶段计划。
- 从工作树删除 70 个被合并、重复或过时的文件，包括两套 docs/archive 副本、十张确认表及索引、停用周报模板/早期说明、编号文档和细分实验说明。没有把它们复制进新 archive；原文固定在 c24ced2f4a5513f5a8944b98139857cfc27909ff。保留独立指标复核原文、旧 M1/开发合同及结果快照。
- 保护源码、脚本、配置、测试、schema、fixtures、导出结果及原始资料；连科学源码目录内 README 字节也保留，避免破坏已绑定运行来源。重写删除文档的引用时，历史 LOG/decision 指向原提交，活动说明指向归并后的合同；不改历史事件内容。
- 白话：输入是重复且互相冲突的文件体系，输出是按计划/方法/数据/结果/决定分工的少量入口。例如原来查事务须翻研究合同、词典和实验目录，现在集中到 METHOD；这不是把所有旧文件搬进另一个目录，也不等于重构科学代码。
- 同轮用户提醒保留 M2 的慢速修订；核对 D-034 及原 M2_DESIGN 的全局 reconciliation 后，将其明确保留在 METHOD，并把 PLAN 步骤 29 拆为合同、实现、版本检查、公平效果比较四个子步骤。区分离线事后监督、在线快提交与在线慢补偿；此处恢复并明确原计划范围，不表示慢路径已实现，不新增科学结果 LOG。
- 整理核验：工作树版本化文件由 397 减至 330，Markdown 由 105 减至 42；32 个主步骤和 7 个审查节点保留。314 个受保护文件逐字节 hash 相同；历史 LOG 正文除链接目标外一致，本地 Markdown 文件链接无失效。这里只做标准库/Git 文档核查，没有运行科学测试、训练或服务器任务。

## D-061：恢复环境结构扩充与对象修订的共同范围

- 日期：2026-09-11；状态：accepted 的范围澄清，具体结构 schema、候选与实验仍 planned。用户明确“我要的不仅是对象”，要求新看到的走廊转角及相连区域通过结构 latent 纳入旧记忆。核对原始 full_technical_vision.txt 第十一节，这属于原有具身空间记忆目标，不是新加第二领域。
- 纠正前次仅优先看 Bonn 箱子变化的选源建议：首批数据审查须同时检查环境结构重见、可见范围扩展、连接新区域及对象变化。优先核查 ADT 公寓连续活动与 ARKitScenes 墙/地面扫描，具体片段待看数据，不预设任一来源已满足跨走廊序列。Bonn 保留为对象/遮挡补充；正式来源和实验 split 尚未冻结。
- 世界节点不局限于可数对象；结构表示及显式相对几何/连接须与观测证据、可见/未知范围和版本关联。新区域纳入可以是旧结构已观测范围增长，也可以是建立相连局部结构，不强制合成同一平面或一个向量。现有事务语言能否完整表达按步骤 07–10 审查，不能将 object 重命名为 corridor 冒充已实现。
- M2 慢路径须包含误接、重复或误合并结构的补偿审查，仍只使用截至修订时刻已到达证据。可靠 pose/depth 下的确定性几何累计作为必要基础对照；单纯地图变大不证明 CTL 优势，唯一主张仍为执行后事后监督相对 C/E 的可靠修订收益。固定前端/候选、不可变执行、在线未来边界及用户代码审查规则不变；不新增动作策略或导航任务。
- 白话：输入旧走廊记忆与转弯时连续看到的新墙面/地板，输出保留原结构并纳入新片段及有证据连接的世界。例如原区域 A 与新区域 B 经转角相连，旧 A 离开画面也要保留。这不是只跟踪箱子，也不是把完整真值地图直接编码给模型。本次仅修正文档与审查要求，没有科学源码改动、运行结果或新增 LOG。


## D-062：转向空间历史条件下的动作后果预测，先审合同再复现失败

- 日期：2026-09-11；状态：accepted 的研究目标与开始授权。用户明确认可：近期观测相同而早期历史揭示的遮挡区结构不同时，检验同一机器人控制的不同视野外交互后果及动作选择；随后明确“可以，开始吧，必要的时候重构整个工作区”。
- 当前候选取代 D-059/D-061 的活动研究路线；旧记忆修订合同、科学 no-go、结果、原始资料及 test 封存保留。暂缓原实采完整接入，已下载画面和来源记录不删除。旧32步计划在转向前提交5f4fd115ed89876c0045d325af290d2636171e73可查，唯一当前计划改写在PLAN。
- 新研究不预先绑定 Counterfactual Transaction Learning（CTL，反事实事务学习）或任何三维表示，也不把持久记忆加动力学自动称作创新。允许固定机器人控制候选的后果评价和动作选择，替代旧“不得加入动作策略”对这一小范围的限制；不新增主动探索策略、开放世界、复杂操作、语言接口或高质量视频生成。
- 已核查原文的 PERSIST/Mem-World/PointWorld 等条件与重合在 METHOD；这不是代码复现、失败证据或排他的新颖性结论。强制与真正获得早期证据的长历史预测器、历史检索及地图加简单动力学比较；若这些足以解决问题，应如实收口。
- 当前第一职责批次为成对数据接口审计和模型输入提取；不堆叠模拟器、表示、动力学、规划或训练代码。严格区分控制指令、机器人计划运动和物体实际未来运动；手工夹具永不称为物理案例。下一批再固定真实模拟器/控制器和接触规则。
- D-059 的可读科学提交、具体例子、必要服务器测试、用户审过后才合并基线/运行依赖效果实验继续有效。工作区可按实际需要重构，当前无需移动旧源码；不把开始授权解释为自动批准未审科学模块、未来训练预算或旧test解封。
- 本轮新的方法/数据合同在审查分支交付；训练/确认划分、数据规模与预算均未冻结。旧六项能量和事务操作只约束旧协议，不强加给新世界模型，但信息边界、真实候选执行、完整失败保存和来源追溯保留。
- 白话：输入是这个具体研究候选及现有项目，输出是先查数据合法性、再真正模拟、再找强对照失败的单一路线。例如旧墙面应影响相同推法的后果，但只有短历史模型猜错不能证明需要新机制。它不等于清空项目、立即重训或承诺新方法会胜出。

- D-062 批次批准补充：SH-01 原科学提交492a7b6及服务器20项通过报告1e00352已核验；用户随后“继续”，登记本批审查通过并快进合并main，允许实现SH-02模拟器与必要工程测试。后续代码审查、开发数据生成和效果实验仍分阶段进行。

## D-063：SH-02固定模拟器、有限力控制和单对工程重放

- 日期：2026-09-11；状态：工程实现提案，服务器测试与本批科学代码审查pending。依D-062的开始授权及SH-01验收后“继续”，交付单一模拟器职责，不将本条写成已批准的训练合同。
- 固定MuJoCo 3.3.7、NumPy 2.2.6和EGL渲染，环境独立放已确认数据盘；精确场景与控制参数在configs/spatial_history，方法解释在METHOD，原始字段在DATA。保护旧约25 GB的cpmt_outputs、Git位置和旧依赖，不删除或迁移。
- 工程预算仅一对固定世界、每世界两候选、每候选一次首次执行与一次独立反序重放，共8条4.9 s分支；无随机搜索、参数扫描或模型。32项工程检查包含原20项合同回归。该对不是SH-03开发数据，也不冻结后续训练数量或统计门槛。
- 真实速度伺服与有限执行器力取代任何直接赋值物块后果的实现；所有候选恢复完整积分快照并执行。原始RGB/深度独立渲染，分割像素仅做遮挡审计；历史和未来真值严格区分。手工fixture保留且永不升级为物理证据。
- 固定工程门覆盖近期输入完全相同、早期墙可见、接触期间目标不可见、重放一致、实际接触差异及非布局初态相同。失败保存并导出，不按结果丢弃或自动扩场景；首次服务器结果只能判断实现是否满足这些具体工程条件，不能判断新颖性、模型有效或现实泛化。
- 白话：输入两个只在遮挡墙位置上不同的场景和相同机器人控制，输出真实物理轨迹及可以复查的画面。例如验证“左推是否在某个世界撞墙”，先确保这个问题本身被正确生成；这不等于已经训练世界模型，或宣称它会胜过长历史/地图方法。旧no-go与test封存不变。

## D-064：依据已记录的侧向脱离修复SH-02推头几何

- 日期：2026-09-11；状态：审查分支工程修复提案，配置已实现，服务器验证与本批审查pending；不合并科学基线或启动依赖效果实验。依据为已回传的contact_diagnostic_v1及LOG-105。
- 诊断显示物块确实与球形推头发生接触，但在约4.05–4.08 s最后接触后停在墙前；推头随后继续前进，在对应布局约5.048 s撞墙。机器人撞墙不冒充物块目标接触，原两项失败保留。
- 唯一物理参数改动为推头从半径0.035 m球体换为半尺寸(0.15,0.025,0.025) m盒体：宽面接触尝试解决侧向滑脱。质量0.5 kg、初态、两候选速度/时长、物块/墙/遮挡屏、求解器、渲染和所有通过阈值保留；配置version/model改标v2，原32项测试源码不改。尺寸为约两倍物块直径的单次机械设计选择，不做搜索或扫描，成效仍未知。
- 预算仍一对世界、四条首次执行及四条独立重放。新默认目录sh02-engineering-v2-flat-pusher、新报告spatial_history_physics_v2_flat_pusher.json；同一现有环境，原球头失败目录和三份报告保留。常规export加入已有轨迹的接触过程摘要，避免再次失败只能看到终点；此读取不重新模拟。
- 白话：输入相同的机器人速度指令，换一个接触面更宽的实体推头，观察物块能否被持续推到原来的墙前。例如仍要求物块真实撞墙并在碰撞时不可见；这不是让物块按给定轨迹移动、降低通过门或证明世界模型有效。若仍失败，根据新版本完整轨迹诊断，不自动扩大场景或训练。
- 后续验证登记：e3a1d71在服务器通过同一32项工程检查，f6b8c58的报告及预览已核验（LOG-105）；D-064的固定夹具工程条件已满足。本批代码审查及后续开发数据协议仍待完成，测试通过不自动批准合并、扩大数据或模型训练。
- 批次批准补充：验收报告已呈现后，用户明确要求“下一步”；据上下文登记SH-02科学提交e3a1d71及其验收批次审查通过，合并main，开始SH-03固定开发审计。新批次范围与预算另行固定，不将本句解释为模型训练授权。

## D-065：固定SH-03开发审计组合、完整失败与计算预算

- 日期：2026-09-11；状态：依用户“下一步”实现当前工程审计批次，服务器检查/生成待运行，尚未批准为后续学习实验基线。SH-02验收批次已快进合并main；新代码在review/spatial-history-development审查分支。
- 事前固定16对开发场景：墙y四值×共同起点x两值×历史采样数两值，全部组合、顺序及字段见登记JSON和METHOD/DATA。选择这些有限变化是为检查原夹具附近的条件是否成立，不依据尚未运行的结果选参；不扩大任务、接触机制、控制器、goal或通过阈值。
- 将原PLAN“最多64条分支”的提案明确冻结为64条不同控制分支，加64条独立反序重放，总128次实际执行；重放不作为额外样本。每次模拟4.9 s。依据SH-02全流程12.680253 s，预算预计5–10分钟前台，实际耗时逐例记录；新产物2 GiB预算按案例边界检查，超过则停止依赖计算并保留数据。旧25 GB数据不删除，复用现有环境，不安装学习库。
- 固定16例全部满足原物理/输入条件才算审计通过。完整生成的失败仍做完其他登记案例，运行异常立即停后续；拒绝补样、覆盖、换目录静默重试与成功子集报告。仅有sealed回执的完整案例可复用，从最早未启动案例继续；中断案例先诊断。此阶段不宣称模型效果、动作收益或独立泛化。
- 一次交付check/run/verify/export；新8项检查验证适配边界和拒绝条件，旧32项与旧物理实现保持原字节、旧报告按原Git来源认证。新METHOD/DATA与新源码另行绑定，不借旧回执认证新批次。后续SH-04训练、公平对照与评分仍待具体冻结及审查。
- 白话：输入原已通过的模拟器和16种预定设置，输出“哪些条件仍成立、哪些具体失败”的完整表。例如挡板变近后碰撞可能重新可见，应留下这个失败再解释；这不是调整场景直到全通过，更不是承诺空间记忆方法有效。

## D-066：依据SH-03墙角擦碰证据作单次横向间隙修订

- 日期：2026-09-11；状态：用户在收到v1完整失败诊断后要求“继续”，授权当前受控工程修订及必要服务器验证；未合并学习实验基线或启动SH-04。原v1的12通过/4失败与全部产物保留，不重写D-065结果。
- 依据LOG-106的4例真实物块–墙角接触，唯一场景改动是左右世界的墙中心横坐标从±0.31 m移至±0.33 m，尺寸不变、内侧边由±0.02 m变为±0.04 m。原首次擦碰位姿的平面几何净距据此增加到约18.09–18.50 mm；该计算不预测新动力学，不能保证应有碰撞和遮挡仍成立。数值为基于已见开发失败的一次设计选择，不做间隙参数扫描，不称为独立确认。
- 同一改动用于原16组固定设置；所有控制/时长、物块、推头、屏、相机、墙y、共同起点、历史长度、goal与13项通过规则保留。新代码不把6–8步短碰撞忽略，不改变真值标签或仅筛掉4例。原模拟器、SH-02配置及32项测试字节保留，开发判定assess不改；新增4项适配/拒绝回归与原8项一并执行。
- 本次预算为新16对、64条首次分支与64次独立反序重放（128次4.9 s执行），新增产物2 GiB按案例边界检查。按v1逐例合计192.38 s，仍预计5–10分钟前台；实际时间记录。新目录sh03-development-v2-wall-clearance、新报告spatial_history_development_audit_v2_wall_clearance.json，复用环境。v1成功例也因几何变化重新执行，不借用旧回执。
- check/run/verify/export整批同步一次交付；新check验证v1失败来源及原实现，并形成12项新测试回执。完整生成的审计失败继续固定清单，运行异常停止后续；失败/中断不覆盖、不自动换目录重试、不继续扩间隙。方法有效性、训练预算、动作收益与强对照比较仍未验证。
- 白话：输入已经证明会擦角的原场景，把墙整体向侧面移2 cm，再问相同动作的碰撞模式能否恢复。例如右推应通过的那一条必须真正在物理执行中无墙接触，同时左推仍需碰到墙。这不是修一个记录错误，因为旧接触是真实的；它是保留旧失败的受控场景修订。
- 批次批准补充：57d01aa及ce5b3f1的12项/16对验收证据呈现后，用户明确“可以，下一步”；登记SH-03/v2本批审查通过，允许合并main并准备SH-04基础对照协议。该授权不自动批准尚未交付的训练代码或确认集解封。

## D-067：SH-04视觉强对照小试提案，先检验输入再训练

- 日期：2026-09-11；状态：具体协议提案，未实现、尚未冻结为可执行训练基线。用户认可SH-03后“可以，下一步”授权交付此协议；SH-03验收批次及批准登记e901beb已合并main。新提案分支review/spatial-history-baselines，机器参数为baseline_protocol_v1.json；当前training_authorized=false，不下载权重、不生成新数据或训练。
- 首轮坚持真实RGB/深度及标定输入，拟冻结DINOv2 ViT-S/14的patch特征，保留早期揭示帧。S/L/R共享预测器和监督，加入观测地图＋准静态动力学与观测地图＋重建物理两种主对照，以及单列真值诊断。由于首帧已揭示墙，首帧检索是必要强对照；不以短历史必然失败支持新机制。
- 未来遮挡图像不是隐藏物块状态的充分标签，采用49步实际位置/接触监督；明确这是DINO编码器的任务适配，不是原DINO-WM实验复现。动作评分固定终点到原目标中心距离及真实regret，原半径命中率不作主指标；不增加碰撞惩罚来放大优势。METHOD给出损失、判门和停止条件，DATA给出权限和家族划分。
- 现有16对仅供工程/输入审计，不拆成训练和独立测试。新小试拟48物理设置家族、每家族2种历史，共96对；32/8/8家族分别训练/选参/最后确认，确认在方法锁定及该阶段授权后才生成。固定模板与两种动作不变，只称参数插值小试，不把家族重命名或固定设计当跨模板随机泛化。
- 学习预算提案：S/L/R各2学习率×3种子、每次1500更新，共最多18次；每次20分钟、总训练6 GPU小时双上限，新环境/权重6 GiB＋数据/特征/结果6 GiB，峰值显存≤12 GiB且≤实际设备容量80%。先量实际设备显存和吞吐，不能仅凭租赁“32 GB”假定硬件容量；若不能完成固定预算则暂停修订协议，不自动缩历史/只训练弱对照。
- 阶段顺序：先交公开输入/编码审计实现并审查（复用旧16对、0训练步），后交新split/数据生成，再逐职责交公平预测器/地图/评分与必要检查；各自确定的阶段一次同步交完整命令，不为转下一步补wrapper。当前外部权重摘要、完整依赖锁、地图拟合/接触算子及模型mask实现尚待该职责交付核验，不能声称整个训练已冻结或立即运行。
- 白话：输入合规视觉与机器人指令，先让现成的长历史、检索和地图方法公平回答同一问题；如果它们已够用，就如实结束这个候选的“需要新记忆机制”主张。这不是为了训练而训练，也不是将小试通过包装成通用世界模型。

## D-068：先收紧研究问题，分列架构对照、论文复现和任务适配

- 日期：2026-09-11；状态：用户认可现在收紧小实验，并要求先核查相关论文、评判旧CTL/CPMT、给建议和落地步骤。接受复审方向；具体新场景、架构、数据量、指标阈值和训练预算仍proposed，未授权模型训练或旧test解封。
- SH-03的15/25帧仅1.4/2.4秒且首帧揭示是验收硬条件；左右类别与固定动作可表达全部碰撞类别，但是否达到连续轨迹精度尚未实测。已通过16对保留为工程/输入检查，不否定其物理证据。原v1的96对插值数据、18次训练及接触Brier单门不足以支撑新主张，JSON改requires_revision_not_executable并保留原参数供审查，不继续其生成/训练计划。
- 定向核查补充FloWM、DreamerV3、PropNet/GNS及机器人世界模型，并更新PERSIST/Mem-World版本。持续3D、视野外动态、历史检索和交互传播各有直接先例；未发现精确相同配对评估不等于证明新颖性。文献事实放literature，方法/架构复审放METHOD，唯一当前步骤放PLAN。
- 旧候选事务网络不当成视觉历史模型；图事务执行不当成机器人动力学；完整PNO与数值latent纠错仍未实现。复用来源、不可变分支、失败与输入隔离；不移植reference派生query、参考事务推进或为了保留CTL而制造修订任务。旧no-go和原始资料不变。
- 新主场景先审核分散空间证据、单帧歧义、变化的证据时刻及几何—控制未见组合。保留完整历史、普通循环状态、合法检索与共享地图动力学；成功允许否证新机制需要，失败先排除感知、监督、训练和评分原因。事件检出/误报与位置/真实动作损失分列，具体阈值事前另审。
- 基础架构比较、官方checkpoint重评/原训练复现、迁移适配三类证据分别记录。输入RGBD/相机、状态标签或动作接口改动必须显式登记，不能把自建相似网络叫原论文复现。数据/权重可见不等于服务器已能运行；旧6 GPU小时预算不能默认为新增对照足够，先测量再冻结。
- 白话：输入用户对首帧捷径和架构证据的质疑、旧源码与当前论文，输出暂停旧提案并重新审查题目和比较条件。例如两个视角的信息是否确实要组合，应在训练前给出可核查实例。这不是立即重构所有科学代码或通过提高数字门槛追求严谨；本轮仅文献、计划与非执行提案更新，没有新实验LOG。
- R2授权边界补充：用户明确“可以，继续，然后进行到具体场景涉及到关于判定的事情让我拍板，但你一定要跟我解释清楚”。据此继续准备具体可审建议，场景取舍、任务成败、数值容差和运行预算保持待选；METHOD的双门四世界草案不登记为用户已接受，也不触发生成/训练。

## D-069：认可双门场景与真实送达目标，继续具体工程判定审查

- 日期：2026-09-11；状态：在a134b1a草案和“是否采用双门场景，并以实际通过两门、到达目标区为主判定”的具体问题之后，用户明确“可以，继续”。据此记录场景方向及任务含义已接受，允许准备具体工程协议，不再重复询问方向许可。
- 数值提案为两门中心y=0.60/2.20 m、洞宽0.38 m/中心x=±0.12 m；相机固定正俯视局部扫描，历史12 s/121帧；四套共同20 s速度控制；目标矩形50×40 cm、末1 s整块容纳且线速度≤2 cm/s、边界容差1 mm。采用有限视场而非实体屏遮挡，以及全部数值/预算，均在本轮清楚解释并待用户选择，尚未冻结执行。
- 工程继续门分开来源、物理、观测、可完成性与动作信息：不预定只有对角控制成功，四世界各至少一成功候选；每个固定单历史帧＋共同近期的信息regret建议≥0.25。这是有限世界中的信息缺失检查，不是模型提升25个百分点的目标，不约束已读完整历史的合法检索器。
- 预算建议1个工程家族、16条首次分支＋16次独立反序重放、新产物2 GiB及生成30分钟；不下载权重、不训练，不自动扩样/扫参。参数文件明确not_executable和未授权生成，旧科学源码、场景、测试和回执保留；新场景需独立接口及新验证。
- 白话：输入用户已选的任务，把路线图细化为真实控制、尺寸和可核验的送达规则。例如擦墙但在20秒内稳定送达仍成功；运动指令执行偏差导致滑脱就记录失败。它不是批准未审科学代码或把手算净空当物理结果；当前没有新实验LOG。

## D-070：冻结双门工程协议，交付一次同步的检查、执行与导出

- 日期：2026-09-11；状态：用户对3c5755e数值提案表示“其他我都很满意”，在听取固定单帧信息损失的解释后明确“可以，我接受这个，继续吧”。据此批准全部本批观察、控制、任务/工程判定和预算；不再请求相同判定许可。
- 冻结`configs/spatial_history/two_gate_engineering_v1.json`，原proposal字节保留。新文件只更新版本/授权/来源元数据，全部几何、时间、像素、任务、信息与预算数值原样复制；用原proposal SHA256绑定。仅工程生成获准，训练仍为false。
- 实现新四世界公开合同、真实物理记录与评分/信息审计；旧模块不改。首批一条相机路径/每世界121帧、四个20 s候选，共16首次分支及16次新实例反序重放。逐步封存回执后继续，完整工程判定失败仍保留固定清单，运行异常、2 GiB或30分钟生成预算到达则停止且可导出。
- 本批必要服务器测试与物理工程检查属于已批准范围；全部入口一次交付、同步一次，逐步核验前提后运行。仍不把新代码自动合并为科学基线，不进入依赖效果实验；R3公共几何恢复、R4强对照/学习预算和确认封存另行满足条件。
- 白话：输入用户已看懂并接受的数值表，输出可审代码、完整真实分支和成功/失败证据。例如某个非同名动作送达也算成功，物理穿透超限则另列工程失败；不会按预期矩阵改答案。这不是已经验证双门能够通过或已有模型失效证据。

## D-071：修正物理参考XML的跨平台字节摘要，保留首次失败现场

- 日期：2026-09-12；状态：Linux首次运行在`history-LL`读取物理参考前失败，未执行物理步、传感器、训练或后续分支。用户已报告完整终端输出；旧运行目录和失败回执保留，只允许导出诊断。
- 原因：D-070提案在Windows工作树中以含CRLF的`physics_v1.xml`计算SHA-256；服务器从Git Linux checkout读取同一blob的LF字节，二者行尾不同而XML语义、Git blob和所有物理数值相同。该错误不支持修改场景、阈值、控制、预算或研究主张。
- 决定：活动配置版本后缀改为`lfsha1`，只把`physics_reference_sha256`换成固定Git blob摘要；原proposal字节、原摘要和D-070全部科学值保留。运维入口同时固定原proposal/其Git提交、原工作树摘要、LF blob摘要及当前checkout字节；check提前失败，不能再等到第一个物理子任务。新目录和报告名均加`lfsha1`，避免覆盖首次失败。
- 白话：输入同一份XML在不同系统中的字节表示，输出可在服务器验证的来源摘要。例如Windows把每行末尾写成两个字节而Linux写成一个，文件内容对MuJoCo相同但哈希不同；这不是场景被换了，也不是重跑或放宽物理规则。

## D-072：R2审查后，先交R3公开文件读取边界

- 日期：2026-09-12。用户在34121aa完整只读验收交付后要求“下一步”；按既有逐职责审查流程登记R2通过，已审代码与结果合并main，事实见LOG-108。新R3模块仍在审查分支，不借旧74项服务器回执认证。
- 首个职责限定为真实`public.json`读取边界，沿用原四世界公开合同、控制与goal，不增加科学机制或判定阈值。必要服务器检查后只读已验收的四公共文件，4世界×4控制×完整/近期两种输入共32次，全部保留；不读原始未来轨迹、快照内容或私有几何，不重模拟或建立新划分。
- 执行沿用现有Python解释器但仅导入标准库和已审合同，0新依赖/0权重下载/0训练步/0新模拟步。运维保护登记为子进程最长1800 s、新持久审计产物8 MiB、公共文件单次读取32 MiB；这是既定合同必要工程检查的保护上限，不是新训练预算或样本扩展。预计短任务、前台运行；run/verify/export一次交付，原失败/成功目录只读，新目录失败或中断不覆盖、不自动重跑。
- 公开几何恢复的具体算法、恢复量及误差判定仍planned，须单独给用户审查；论文资产/资源核验、原SH-03视觉读取及独立环境按现有R3计划随后交付。本批不下载论文权重，也不把读取成功称为官方架构前向、原任务重评或模型有效。
- 白话：输入已通过工程验收的四份公共记录，输出后续方法可以合法消费的查询和来源摘要；例如修改旁边的未来结果文件不应改变查询，非法字段即使位于没选的帧也应报错。这不是用文件夹名称告诉方法应该走哪条路，更不是证明完整历史已能恢复双门几何。

## D-073：按同行评审与任务适用性重审论文候选，取消默认先运行DINO-WM

- 日期：2026-09-12。用户指出DINO-WM的画面预测目标，并要求核查已评审且仍具代表性、能够配套当前案例的方法。核查依据为正式出版/会议目录、指定正文版本与作者公开资产；详细来源保存在现有文献记录，不将作者自称接收、搜索未命中或代码入口存在分别冒充正式接收、没有代码或已复现。
- 调整候选审查优先级：DreamerV3的历史状态与奖励后果，PointWorld的三维点流与机器人路径假设，FloWM的结构历史状态与自运动条件。DINO-WM保留为有条件的视觉特征预测对照；ParticleFormer的正式CoRL身份已核实，但官方实现/权重未核得，暂不承诺复现。此为文献筛选与适配提案，不是冻结模型名单、代码版本、数据划分、监督、预算或新架构。
- SH-05仍必须包含长历史预测器、合法历史检索、地图加简单动力学。先审输出目标是否可识别后果、历史是否提供足够信息、控制是否被偷换为实际运动，以及原设定是否能正确重评；公平适配并充分训练后才检验可复现失败。强对照成功应收口，未收敛/输入不匹配/监督缺失不能被写成新的长期记忆缺口。
- 白话：输入论文的实际接口和本实验合法信息，输出可以如何比较、哪些条件尚缺的清单。例如预测空地画面正确但未输出门后箱子的位置，不能直接算论文失败；给它后果标签和读出头后再比较，必须说明改动。这不证明任何模型已经失败或新机制有必要。
- 本次仅更新文献与计划/方法说明；R3公开读取器的原运行88c42b7及导出结果a9275e7继续按原绑定审计，文档更新不产生新服务器回执、不要求重跑。结果尚未在本次文献核查中完成只读验收；不提前更新LOG-109为通过。
- 用户随后授权“可以，开始审核吧”；源码接口审查补充：以三个完整作者commit只读核验后，DreamerV3进入第一份适配合同设计，PointWorld暂限共享观测地图动力学候选，FloWM暂限原任务记忆参照。后两者不能直接接收本任务的充分历史与独立有限力控制；修改接口/监督后须明确属于适配。审查记录及未决项见现有文献笔记/METHOD，执行指针见PLAN，不开始训练、下载权重或新划分。R3报告现已完成独立只读核验并补入LOG-109；它只认证原公开读取工程，不认证论文方法或新科学模块审查通过。

## D-074：三个论文方法均适配，独立路线与模块组合分开比较

- 日期：2026-09-12。用户询问三个模型解决哪些模块、能否组合，并明确“我还是想这三个每个都适配”。据此覆盖D-073末段仅先推进Dreamer而将另两项限定为参照的处置，保留DreamerV3、FloWM、PointWorld三条本任务适配目标；已发现的接口缺口变为待解决工作项，不据难度排除路线。
- 功能分为观测编码、历史状态、动态推演、后果读出/评分。Dreamer与FloWM均跨多个功能，不把Dreamer误当成可通用的奖励头或把FloWM说成只有静态记忆。PointWorld需要公共历史前端及合法控制适配。三条均先形成可独立比较的适配系统，再考虑固定一侧的模块替换；不将模型间隐状态假定为可直接互换。
- 白话：输入同一历史、控制与目标，三个系统各自输出后果；例如都要利用曾分别看见的两门判断推物能否通过。组合时可让FloWM保留历史，再经明确场景转换交PointWorld推演，但转换需要自己的来源、监督和误差记录。这不是三个权重串起来就完成复现，也不是组合本身已经有创新。
- 下一批为共同接口及三份具体适配合同，按依赖逐职责交付；原任务核验、任务适配、混合系统分别命名。保持长历史、合法检索和地图加简单动力学主对照。用户确定适配范围，不等于已经批准未定训练预算/划分或未审科学代码；本次无训练、权重下载、模拟及新效果结果，不新建实验LOG。

- 用户进一步澄清：允许三个模型分别比较，只要处在同一体现项目研究问题的整体流程，更关注各自何时失效及迈向通用能力的实际障碍。D-074据此补充为统一历史—控制后果—候选选择的任务和证据链，保留原机制差异与独立诊断；组合只由定位后的错误驱动，不预选最终拼装架构。具体判读见METHOD“同一研究流程中的独立比较与失效条件”；本补充不新增模型结果、训练/划分授权或实验LOG。

## D-075：将历史信息、推演与错误动作连接为可审诊断实验

- 日期：2026-09-12；状态：proposed。用户要求把已有流程做成能回答“信息在哪里丢失、在哪里没有被利用、为什么最终造成错误动作”的实验。本批交付METHOD的E0–E4设计和DATA诊断字段，不实施模型、探针或新几何算法。
- 固定设计方向：公开几何正向检查；冻结主体的编码/跨时状态读出；四条只改一门的完整真实历史配对；全控制时域的推演检查；成功读出与候选选择分查。配对重用原16条分支，不新增物理样本、不把相关边或时间步当独立统计单元。三个适配及必需强对照进入同一流程，条件性模块替换另按兼容接口登记。
- 白话：输入同一历史—控制链上的合法状态和独立实际后果，输出每一步能支持的错误解释。例如决策状态可读出远门而预测仍错误，只能先定位为“可读信息未转化为正确后果”，还要分查推演与读出；这不是用探针失败证明信息完全消失，也不是凭状态可视化宣布新机制成立。
- 连续几何探针和冻结成功诊断读出是额外诊断学习，必须与主体训练、主排名及特权评估分开；当前四世界不得用于拟合或选参。读出容量、训练家族/划分、样本与优化上限、各误差容差、模型资源和统计方案仍未冻结。原R2/R3工程回执只认证原职责，不认证这些新诊断；不得以本提案启动训练、下载权重或新模拟。
- 本轮仅文档/源码及标准库静态核对；DATA同步纠正“零深度被拒绝”的过强说明，沿用实际帧合同的有限非负深度及零值无效约定，不改科学源码、配置或历史报告。无新运行事实，不追加EXECUTE实验LOG。后续实现按D-059逐职责审查，阶段命令与资源一次交付，不预定改进机制或最终模块组合。

## D-076：E0采用公开俯视深度的顶面边界包络，先交具体算法与数值提案

- 日期：2026-09-12；状态：proposed。用户在D-075交付后要求继续，本批将首个E0职责具体化；提案为`configs/spatial_history/public_geometry_proposal_v1.json`，实现、数值运行及预算尚未批准，不冒用原R2/R3回执。
- 源码核对表明R2相机固定垂直俯视，应恢复水平顶面的开口轮廓。算法从全部公开深度自行分面，以同面左右片段夹着更远有效深度提出开口，利用相邻像素射线足迹形成三边区间，跨历史仅融合相容候选。门高/数量/位置、红色特征、私有mask、正确A/B下标和动作答案不进入完整历史恢复；未知区域不补自由空间，不将顶面向下外推为已观测完整墙。
- 白话：输入原RGBD/位姿，输出“这一段像素支持门边位于这段坐标内”；例如用墙顶与地面的深度跳变夹住内边，不能直接拿地面点的位置当墙边。这是当前理想俯视设置的几何正向检查，不是学习模型、通用建图、真实接触可预测性或创新主张。
- 数值提案包括1e−4 m平面容差、双侧2像素/2行支撑、像素足迹区间、25 mm最大坐标区间宽和12.5 mm中点误差门；具体算法与公开/私有参数分工见METHOD/DATA。原4世界各full/A/B/recent共16项、500次帧消费，全部复用旧观察；评估才允许从原manifest绑定XML获取真值并核对候选数量。不能把完整提案连同evaluation_only传给提取器。
- 拟议只读阶段为纯标准库、前台≤1800 s、新产物≤64 MiB、峰值RSS≤512 MiB；0模拟、0训练、0权重、0新划分。失败保留且不按结果改阈值；一次交付同阶段检查/run/verify/export后再运行，不为导出另改代码。当前仅提案及静态检查，无新实验事实，不新增LOG。

## D-077：接受E0具体提案，交付独立恢复、评估与整阶段工程入口

- 日期：2026-09-12。用户在公开读取结果/论文接口审查及D-076具体数值提案e64afa6交付后再次要求“继续”；据此实施E0并交付必要服务器检查和只读工程运行。原提案JSON及其Git字节不改，另建`public_geometry_v1.json`登记本次授权，逐值保留source、sensor、extractor、evaluation、budget及claims；training_authorized仍false。提案摘要按固定Git blob的LF字节核对，不重新使用Windows工作树CRLF摘要。
- 科学职责拆分为公开恢复器`public_geometry.py`及独立评估器`public_geometry_audit.py`，分别带解析正负例检查；`ops/spatial_history/public_geometry_check.py`只管理来源、顺序、资源、回执和导出，复用原R3读取器，不复制恢复算法。白话：输入原公共历史，先留下“只看观察得到哪些边”的不可覆盖预测，再让另一职责看实际XML评分；例如近期空预测可以合格，完整历史漏一扇门不合格。它不是将真值补给恢复器，也不是三个模型的成功/失败实验。
- 本批59项必要服务器检查与16个原历史查询一次交付。500是恢复器收到的输入帧总数；原读取器每次仍完整校验文件，来源/终检也只读复核，不能把500写成文件读取次数。全部16份预测及来源摘要封存后才解析私有XML；恢复进程不接完整配置、世界/门标签、A/B语义或目标数量。进程职责分离不是操作系统权限沙箱。
- 不放宽D-076资源：正式run及首次成功export合计≤1800 s，各含1 s文件收尾保守上界；阶段及报告合计≤64 MiB、阶段存活进程树合计RSS≤512 MiB。来源核验、测试、恢复、评估和最终验收均在计时内；首次导出只使用剩余时间。内存采用50 ms采样、存活进程高水位之和及附加地址空间限制，区分观测值与执行上界。回执/报告先写pending，收尾门通过才发布；失败/中断保留，不能复用待发布文件冒充成功。独立verify/重复导出属于可选只读运维核验，单次资源保护及终端统计另列；失败诊断导出不能升级为预算通过。
- 本地仅源码、AST、JSON/Git静态核查，不导入/执行新模块或测试，不运行MuJoCo/NumPy/Torch。实际服务器检查、几何恢复及资源结果仍pending，见LOG-110。新代码只在审查分支交付，未成为已审科学基线，未合并main；本次接受具体工程提案不批准E1–E4学习、三模型适配效果、权重下载、新划分或未定预算。旧CPMT、旧no-go/test及原R2/R3产物保持原样。

## D-078：按用户要求提供E0多worker并行，独立登记运维内存额度

- 日期：2026-09-12。用户指出旧M1/S5能够worker并行，要求E0也支持，并明确旧E0运行尚未启动。原串行入口是实现选择，不是研究协议不能并行；旧S5的4路评估、最多16路生成见`m1_s5_confirmation_v7.json`及`run_m1_corrected_confirmation.py`。本批仅借用独立任务/产物和固定顺序汇总原则，不导入旧CPMT算法或借旧检查回执通过。
- 默认4个worker，`run --workers N`接受1–16；只并行16项公共查询，测试和私有评估串行，全部公共子进程正常退出及预测封存后才能评估。白话：输入是固定清单中的独立合法历史，每个worker输出自己的几何预测；例如四项同时完成、回执仍按查询ID排列。它不是新增四个模型或四份独立物理样本，不保证获得四倍加速。
- `public_geometry.py`、`public_geometry_audit.py`及其科学检查保持原字节；公共参数、恢复/评估门、4世界×4模式、500个提取器输入帧和1800 s/64 MiB上限不变。新`public_geometry_parallel_v1.json`绑定0b1640f的串行配置与原提案，逐值核验允许的运维差异。原提案、串行配置、入口Git版本及原路径保留；新版本不冒用原回执，旧目录已存在时禁止自动另跑。
- 内存额度明确变更：父进程及各worker地址空间分别≤512 MiB，存活进程树合计RSS上限为`(N+1)×512 MiB`。默认4路2.5 GiB，8路4.5 GiB，最多16路8.5 GiB；配置的8.5 GiB是最高允许值，实际门按N登记。启动前要求CPU affinity/可见cgroup配额至少N、主机与cgroup可用内存的最小值至少该门加512 MiB余量，不静默降低N。预检只覆盖可见约束，不假称资源已预留或不可见宿主限制已测得；不扩大样本、训练或时间预算。
- 运维职责为独立进程调度与Linux资源核验；跨进程锁将磁盘预算检查与写入绑定，乱序完成按固定ID汇总。失败停止派发并清理所有活动进程组；已启动PID、未启动ID和缺退出回执ID分开保存，不把清理失败伪装成未运行。SIGINT/SIGTERM/超时/内存中断保留现场；pending未通过收尾门不发布。失败导致的残缺JSON以字节摘要和有限原文前缀导出诊断，不改写原文件。
- 用户进一步要求先确定worker数量，补充只读`capacity`入口；列出可见CPU/RAM约束下1–16路的可行范围及至多4路的起步建议，不创建阶段、不跑测试或恢复，不以资源可行上限冒充最快配置。正式run仍按所选数量重新核验。
- 本批97项必要服务器检查，包括小型标准库1路/4路结果一致和跨进程磁盘锁检查；它们不额外读取真实R2进行多布局试跑。本地仅源码、AST、JSON/Git静态核查，未运行模块或测试。实际并行速度、内存、完整恢复与几何验收仍待服务器；补充原LOG-110，不创建新的模型实验记录。整阶段一次提交交付及同步，verify/export复用登记worker数；没有合并main、训练、下载权重或解封旧test。

## D-079：开启R4，固定共同接口、三模型适配和公平比较的可审v1规格

- 日期：2026-09-12。用户在E0结果审查a516395之后明确“开启下一步：SH-04-R4共同接口、三份模型适配合同及公平对照/数据/评分冻结”，并在切换会话模型后要求继续。本次落实该阶段的具体协议，新增`protocol_r4_v1.json`，状态`frozen_for_review_not_executable`；没有把开启阶段解释为批准尚未交付的科学代码或本次首次提出的资源数值。新版本的生成/训练/下载/确认授权字段均false；既有通过报告和原字节保持原样。
- 共同输入为公开121帧RGBD/位姿/本体、一条200段世界速度控制、目标及所有系统相同的固定物性。输出为200步位置/区间接触和原整段成功概率，四候选从同状态独立推演；真值门、对象mask、实际未来机器人运动和审计编号不能进入输入。白话：同一旧门证据最终是否改变正确的动作后果，在一个外层流程比较；例如位置可读但成功分数错误会继续检查读出，不把不同论文的原任务指标拼成结论。
- 三份适配分别保留DreamerV3的RSSM、FloWM空间更新/动态通道和PointWorld点流预测。新增深度、连续相机、操纵控制、历史场景、机器人预测及长chunk续接逐项写明；作者commit沿用已审锚点。D/F拟从头学习，P拟微调small-droid并冻结DINOv3，外部预训练条件不相同，报告完整系统表现而非宣称单一架构因果效应。DINO资产摘要/权限、checkpoint配置与环境兼容性仍未核验；不下载或用随机替身冒名比较。L长历史、R观测覆盖检索、M地图加有限力简单动力学为强制主对照；暂无混合系统、主动策略或新机制。
- 新64家族的连续几何/控制和观察顺序/时序独立预登记，六种split按家族分开：32/8/8模型训练/验证/确认，8/4/4探针训练/验证/确认；共1024首次及1024独立重放，不把旧R2或重放充训练/独立样本。固定train前4家族工程子批复用到全清单；任一构造门失败保留且停止依赖学习，不剔除重抽。二元门侧别是否仍决定动作须由开发实际矩阵检查，连续采样本身不证明排除捷径。确认在全部主体/探针/评分锁定后单独放行，旧test保持封存。
- 主指标按家族汇总实际选择regret；缺预测/真值保留完整注册分母与代价上下界。位置、接触稀疏正例、首接触、全段成功和E1–E4分别报告；冻结探针用独立家族训练并核验历史/未来状态域，不以probe失败直接判无信息。三seed、全部小样本家族及描述性配对区间完整保留，不把重复帧/动作/seed当独立样本，不因短历史必然失败启动SH-06。
- 数值预算首次具体提出：20条主学习路径最多40 GPU小时，含小型拟合、60探针、15打乱负对照、资产检查和推理导出合计最多56 GPU小时；新数据/特征32 GiB、环境/权重12 GiB、模型状态/报告20 GiB，总64 GiB。生成墙钟8小时、其他CPU工程/评分4小时；单GPU学习，显存门24 GiB、CPU存活树32 GiB，生成4路起步/最多12路。数值是待审上限，当前资源/费用可行性未验证，旧50 GB盘不推定够用。到顶未收敛记充分性未核验，不自动增加配方/种子/预算或删除原数据。
- 本次仅文档与非执行JSON协议的静态一致性审查，未新建数据清单、代码模块、运行目录或实验LOG；不合并main。后续按PLAN的共同评分、生成器、公共前端/控制、三条适配各自交可审代码和必要服务器检查；用户审过本职责后才依赖实现/运行，不在未审科学模块上堆叠效果实验。

## D-080：R4-1共同查询与评分器独立交付，限定为工程值合同

- 日期：2026-09-12。用户在D-079后要求继续，随后要求不拖延小任务；据此交付R4-1的最小独立代码审查批次：`r4_query.py`验证公开历史、控制、目标和D-071共同物性并产生不含文件/ID/真值的列式查询，`r4_scoring.py`独立读取预测和评估标签、计算位置/接触/成功/选择与家族统计。两者均只依赖标准库及既有字段验证器，不读文件、不调用模拟器、不导入模型框架。
- 白话：输入是一条已经由外层合法读取的历史、一条候选控制，输出是每个方法都能消费的公开查询；评分输入是该方法自己的预测和独立真值，输出是候选选择代价与错误拆分。例如四条候选同分时，每条以1/4概率参与期望代价；一条预测缺失时不把其余三条重新归一化、也不假装世界已经完成。这不是让评分器知道门的答案，更不是已经跑了Dreamer、FloWM、PointWorld或三项主对照。
- R4-1的`labels_from_trajectory`只把已保存的10001行物理轨迹投影到200个预登记控制区间；其调用者负责来源绑定，函数不认证物理或可见性。`score_world`要求四个候选真值均物理/可见性合格才给主regret；否则保留注册候选数、错误原因及保守代价界。汇总以家族为唯一统计单位，seed/world/候选/时间步不增加独立样本数；缺登记家族使主均值和配对区间保持未完成。
- 新`r4_contract_check_v1.json`和`r4_contract_check.py`只允许服务器执行两份手工正负例测试，资源上限300 s、8 MiB阶段产物及512 MiB父进程峰值；阶段目录固定为`/root/autodl-tmp/spatial-history/sh04-r4-contract-v1`，已存在时只verify，绝不覆盖重跑。检查、run、verify和export均登记0新模拟步、0训练步、0权重下载，并把物理、可见性、公开几何、模型实验和长期记忆主张固定为false。当前尚无服务器回执或新EXECUTE日志。
- 本地只做AST/JSON/Git静态检查，不运行新模块、单元测试、MuJoCo、NumPy或Torch。R4-1代码仍在审查分支，用户审过并取得同一提交的服务器回执后才允许R4-2新家族生成；D-079的64家族、56 GPU小时和64 GiB数值不因本工程检查获得额外运行授权。旧CPMT、旧R2/R3报告与失败目录均未改动。

## D-081：R4-2固定家族及无损工程子批实现，生成与资源仍待审

- 日期：2026-09-12。用户在R4-1只读验收`e57015f`后明确继续R4-2。当前授权用于交付独立可审代码及必要服务器检查；不解释成批准尚未看过的物理代码、新资源细分、模型/确认。64家族、split、数值范围、控制独立性、观察时序、信息/物理/E0门均照D-079，不根据结果修改。
- 白话：输入固定设计规则，输出64行事前清单及仅能运行首4家族的入口。例如`r4-39`使用自己独立的近/远门宽和2.8/6.8秒停留，四世界共享控制；固定工程ID为`r4-39/r4-47/r4-25/r4-03`。清单是静态配置，不是生成了64家族观察，更不是确认数据解封。
- 新模块职责为设计、逐门物理/评分适配、无损字节存储、家族编排及运维。旧源码/配置/结果保持原字节；旧门事件评分仅改逐门中心/宽度索引，新的source绑定独立认证。运行前按原Git blob复核R4-1/E0报告，不重跑旧任务；22项新服务器检查只编译XML及处理人工数值/字节，0模拟步、0渲染。
- 首批资源细分为**待审提案**：4家族16历史、64首次+64重放；check≤300 s，run+首次export≤7200 s且计入原生成8小时，首批目录/报告≤8 GiB。每家族384 MiB含1 MiB失败余量，64家族原始产物最多24 GiB，另留8 GiB公共特征/阶段元数据，仍在原32 GiB数据总额内。上限不足时保留失败，不按结果替换、删精度/原轨迹或扩大额度。每进程6 GiB地址空间、存活树30 GiB、另512 MiB可用余量；本子批默认4路/可选1–4。后续模型、环境、权重和总56 GPU小时/64 GiB无新增授权。
- 直接无损行流保存RGB、扩宽后原值不变的深度、积分/索引及全部接触/事件，历史逐帧追加可恢复前缀，原始/压缩摘要分列。公开观察、训练标签和私有审计各自manifest；恢复器只收原公开字段，16项E0输出先封存后读实际XML评估。函数/文件隔离不冒称OS权限隔离。失败/中断保留，不用合法gzip尾补造完整数组；完整成功步骤只验证复用。
- 同版本交齐capacity/check/run/verify/export。check可以先跑；run只有用户审过当前代码与资源、明报实际新增数据可用额度并以`--reviewed-code`指向同一check的完整提交才放行，生成false的基础配置不会自动授权。仅允许固定4个train家族，无其余60家族或确认入口；首批false工程门仍执行本家族登记剩余分支，异常/预算/中断才停止派发。
- 本地仅物化静态64行配置、源码/AST/JSON/Git核查；未导入执行新科学模块、未运行测试/模拟/模型。服务器实际通过数、生成耗时、压缩率及家族是否可用均pending；实现事实见LOG-112，不把设计当结果，也不推进R4-3。


## D-082：R4-2失败后的观察与九候选修订规格提案（未批准实施）

- 日期：2026-09-12；状态：proposed。用户在`84d3046`的完整失败诊断交付后要求“下一步”，本轮据此交付具体修订规格供审查，不将其解释为已批准尚未见过的九候选科学合同或新模拟。唯一数值源为`configs/spatial_history/r4_repair_proposal_v2.json`，实施/生成/训练/下载/确认均false；方法和字段分别在METHOD/DATA，当前指针在PLAN，不新建实验LOG。
- 白话：输入原首4家族失败的实际接触与几何证据，输出目前是相机、门位、控制及预算的可审提案。例如几何带组合让一个家族的较左门在中间位置，另一个家族在左位置，候选仍按实际数值顺序登记；这不是通过随机打乱标签排除捷径，也不是已证明新数据有效。
- 不推荐仅收紧原四条控制以追求恢复对角矩阵：它可能留下原已登记的类别到控制固定对应。提案改为三横向参考位置的3×3九候选；各门独立用几何hash选其中两带，叠加连续微扰。世界符号只是较左/较右带，不能固定指向同一控制索引。原单帧信息门和类别最优集交集仍用真实结果裁决；交集仍全非空则仅工程结果，不继续其余生成或模型。排除这一特定捷径不证明排除所有模板解法，不能靠扩大难度追求模型失败。
- 具体变化包括原生80像素/42度相机与起终点/未来y=−0.20 m；门共同横移微扰±0.005 m、每侧独立±0.01 m、门宽[0.38,0.40] m；控制缩放[0.95,1.05]并对近/远计划端点分别定义，远段发两计划端点之差。仍保持各几何键与控制键独立、无实际未来状态输入、有限力及20 s控制。缩窄部分范围、改为三位置带及增加候选均是基于开发证据的数据分布修订，不包装成只修代码。静态19 mm名义推头端点余量不能替代物块保持接触、真实轨迹和渲染验证。
- 不改原v1配置、源码、数据、旧评分或no-go；同64个ID与划分保留，但v2须新dataset/query/prediction/score版本、设计/传感器与代码摘要，不混用v1/v2为独立样本。现有D/F/P及L/R/M原64像素/4候选接口和训练曝光不能直接沿用，新合同后另审适配；不改模型名单、损失或学习预算，不下载权重。
- 拟议仅一次首4家族新版本工程批次，16历史、144主分支、144重放；候选增加使分支为原2.25倍，80像素使每家族原始数组静态估计1,405,018,944 bytes。保持首批7200 s/8 GiB、每家族384 MiB、4路/每进程6 GiB/树30 GiB硬门；全部生成总8小时包含旧run+首次export已耗268.250822 s，预算不重置。原24 GiB家族+8 GiB共享池总32 GiB内，从共享池先预留1 GiB给v1失败，剩余特征/元数据共用至多7 GiB。压缩足够、租赁剩余额度及后续模型成本未验证；失败保留且不自动调整/扩跑。
- 交付顺序：先审本提案，再交80像素/9候选公共值合同及评分人工例，用户审过后交新设计、真实物理/观察与无损存储及完整工程入口。整阶段完成审查后服务器同步一次，运行新检查；数量按实现实际清点，不冒用旧22项/23项回执。明确放行只涉及首4家族，不含其余60或确认。当前仅JSON、源码阅读及轻量标准库静态算例，无新服务器测试、渲染、模拟、训练或结果。


## D-083：接受D-082规格，先交v2公共查询与九候选评分职责

- 日期：2026-09-12。用户在`ad2e9e1`具体数值提案后明确“可以，继续”，据此登记D-082规格认可并开展首个独立科学职责。原提案JSON保持原字节/提案标记，新`r4_contract_check_v2.json`以原Git SHA绑定认可的规格并限定零模拟检查范围；不将实现授权扩大为首批实际生成、其余60、确认或训练。
- 白话：输入公共历史、数值控制以及独立预测/真值，输出版本合法的模型特征及九候选评分。例如9条同分且仅一条成功时失败代价8/9，缺一条时仍有9个注册位且主选择未定；这不是生成器、真实物理标签或模型有效性证据。
- 新`r4_query_v2.py`校验80像素和D-082固定标定，显式区分源/查询/预测版本，并在输出模型特征前剥离版本元数据；9条查询对照外层事前登记的数值控制检查顺序与共享历史，但不代替外层manifest来源认证。新`r4_scoring_v2.py`增加标签版本与6400像素范围，保留原200段/10001行接触投影、指标和家族统计，仅将候选槽位改为9，不将四世界数量也改成9。
- 旧source/config/test/ops字节保留；新科学职责按查询、评分两份可读提交交付，公共人工例供新检查复用。必要服务器检查清单33项（查询15、评分15、运维3）；本地只做AST、依赖路径、原逻辑逐函数对照和JSON静态核查，不导入新科学模块或运行测试。
- 运维入口预写run/verify/export，固定新目录sh04-r4-contract-v2；最多300 s、512 MiB地址空间/RSS、8 MiB阶段加报告。零模拟/渲染/训练/下载，失败保留，旧目录或不同报告拒绝覆盖，失败/中断可导出原证据。检查配置许可仅为标准库人工合同检查，不能放行物理生成或冒用旧22/23项marker。
- 按D-082已经说明的阶段顺序，本轮先交本合同审查；审过后再开发v2生成/存储及整阶段入口，完成后服务器同步一次。当前不要求用户提前pull或分次同步，33项真实测试结果仍pending；新生成依赖的工程放行另核明确提交、完整检查与资源，不在未审合同上堆叠后续科学代码。

## D-084：接受v2合同交付，实施固定设计、生成/存储与完整服务器阶段

- 日期：2026-09-13。用户在`8450180`的D-083交付后明确“继续”，据此推进下一职责；不重复请求已批准的D-082数值规格。原提案、v1源码/测试/配置/入口/失败报告保持原字节；D-083值合同也不改动。
- 白话：输入固定64行规则、原物理常量与已审v2值合同，输出首4家族完整原生历史、36首次/36反序重放每家族及审计。例如即使第一个分支失败，其余登记候选仍执行和保存；不是按结果筛样本，也不是模型实验。
- 分开世界LL/LR/RL/RR与候选c00…c22。私有配置按原base模板摘要和index精确派生，公开数据只含匿名数值槽；新设计、公共记录/信息审计、物理/存储编排和运维分别形成可审职责提交，不合并main。原轨迹评分、历史采集和rollout方法体保持，真实配置改为已登记80像素/42度/三带独立门/九控制；无损存储直接复用原实现。
- 新报告直接保留全部主分支接触对摘要及全部E0拒绝/候选/未闭合/冲突计数，口径同LOG-113，不更改训练接触标签或任务成功规则。总accepted同时要求家族门和类别捷径门；类别最优槽交集全非空则停止依赖工作，不能靠各家族通过继续扩跑。
- D-082预算不变：仅一次16历史/144首次/144重放；7200 s/8 GiB阶段、384 MiB每家族、4路/每进程6 GiB/树30 GiB，旧268.25082197599113 s和1 GiB旧现场保留计入总账。剩余60、确认、训练、下载均无入口。实际新数据配额仍由人工放行显式填写，不能由df或旧截图猜测。
- 整阶段入口一次备齐：D-083的33项合同run/export，新生成capacity/check/run/verify/export，生成check有37项（设计11、公共/信息5、存储8、物理/编排7、运维6）。前提逐步自动核验，失败保留/可导出，不重试/覆盖；check只编译XML和运行人工测试，0积分/渲染。整批审过后服务器同步一次，旧/新报告最后一起精确Git收尾。
- 本地只进行轻量标准库AST/符号表/JSON/设计物化/源差异/依赖/Git核查，没有运行这些测试或科学模块；实际压缩、时间/资源、物理/信息/E0及类别捷径均待服务器证据。当前交付可审实现和短命令，不把静态核查写成通过回执。

## D-085：R4-3公共前端与控制职责、输入及未知边界审议

- 日期：2026-09-13；状态：proposed，文档审议，未实施。用户确认69a8c92的v2本批工程和合同证据通过、无需重跑，并明确要求开始审议R4-3。此授权覆盖本轮具体规格审议，不把首次提出的拟合/地图/接触规则写成已审算法或可运行数值合同。
- 白话：输入已验收v2公共历史、数值控制和共同物性，输出各模块该读什么、该产出什么、哪里必须保留未知。例如PointWorld只得到公开近似控制器自己预测的推头运动，不能得到实际机器人路径或M的物块后果。这不是已有模型结果，也不新增学习/生成/下载授权。
- METHOD细化R覆盖选择、近期对象估计、全历史静态地图、有限力预测、M公开任务读出及独立评估的责任；DATA登记派生值/状态/来源及误差字段；PLAN是实施依赖和当前指针的唯一位置。原protocol_r4_v1、v2源代码/配置/报告保持原字节，当前输入明确使用80像素/九候选，旧64像素/四候选模型规格不直接执行。
- R保留D-079的近期2帧加8次公开表面覆盖贪心，细化固定世界原点、负坐标floor、单帧去重、全零新增、前缀和来源规则，不用E0/对象mask/控制/目标重排选帧。M/P使用完整合法历史而非R的10帧；公共观测可以共享，L/R/D/F不额外接入M状态。
- 地图明确区分真实表面/射线自由证据、未知与共同外形假设；E0前缘不是完整碰撞地图，已知厚高不授予私有侧墙或未观测墙端。对象支持/速度从公开像素估计，歧义不按初始坐标或真值选择。拟合、动态排除、自由覆盖、接触几何及不确定性判定的科学数值尚待各职责实施前审议；不按四家族结果默认调阈值。
- P正式条件只消费M以同一公开初态和单条指令预先生成的predicted机器人路径；planned只供诊断，actual_future只供独立评估。M物块轨迹/成功不流入P，P的chunk不反向修改M；共享路径包含M对物块反作用的近似，误差须单列。M/P未决保留完整分母，不以真值、计划路径或概率0.5补齐。
- M整段成功用公开恢复几何和自身轨迹判断；真实轨迹评分函数需要私有family config/world_name，只留评估端，不作为M读出。碰撞不自动等于任务失败，推头碰门不混入物块接触标签。评估必须在公共输出封存后读取原实际运动/几何，既有工程报告只绑定原7a2005c字节，不认证这次文档或未来前端。
- 下一最小实现职责为R4-3a公共反投影/覆盖检索，随后逐职责审查对象、地图、控制和工程评估，不在未审模块上叠后续科学代码。本次无科学实现、测试/模型运行、新数据/下载或EXECUTE实验LOG；原PLAN局部编辑保留，不合并main。后续检查/实际只读评估须分别给出完整阶段入口、固定清单、预算和同版回执，不要求重跑已验收生成。
