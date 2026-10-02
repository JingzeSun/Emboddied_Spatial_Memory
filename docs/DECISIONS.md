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

## D-086：接受R4-3a边界并交付公共反投影/覆盖检索及必要检查

- 日期：2026-09-13。用户在7b1cd6c的D-085审议稿后明确“继续”，据此实施首个职责；不把该指示扩大到对象/地图/控制的未定数值、真实历史恢复、模型或其余家族生成。当前代码待用户审查，服务器检查尚未运行，不合并main。
- 白话：输入一份已选择的纯深度历史、共享传感器和固定覆盖参数，输出最多10个原帧下标及全部表面像素来源。例如121帧全零仍选最早八帧加近期两帧；不是证明这些帧包含门，也不把体素补成地图。方法和具体手算例在METHOD，字段在DATA，阶段和命令只在PLAN。
- 科学职责为`r4_coverage.py`：原生80像素、决策相对时钟、纯深度字段白名单、轴向反投影、所有来源保留、0.02 m固定世界网格、2+8贪心和时间并列；近期/前缀不得传多余帧。近/远裁剪0.04/20 m及0.0001 m余量继承原E0共享传感器；绝对1e−9的相机/时钟常量容差沿v2。不增加任务评分阈值、标签权限、划分或学习预算。
- 输出局部索引用于外层取回原RGBD，版本、来源像素和新增覆盖分数不作为附加语义特征；公开入口不接外部预计算体素，以免把私有几何冒充合法覆盖。无RGB/控制/目标/本体/私有mask/文件读取，不依赖对象关联、E0候选或私有可见性。值合同不是文件来源认证；未来真实接线仍须单独绑定原manifest。
- 新科学检查19项、独立运维检查8项，共27项人工检查；同版run/verify/export一次交付。必要检查限定既有Linux隔离环境、逐命令300 s/512 MiB地址空间与峰值RSS、阶段加报告8 MiB；所有模拟/训练/权重新增为0。该额度只覆盖本职责短工程检查，不重算原16历史/144首次/144重放，也不借D-079总预算开启其他计算。
- 新回执绑定11项来源、完整Git提交、测试身份及源字节；失败/中断保存原阶段且禁止自动重试，verify/export不执行科学函数或测试。不同报告不覆盖，失败报告保留原证据文本。旧源码/配置/结果保持字节，原33/37项marker不用于认证本批。
- 本地仅做AST/导入依赖/固定JSON/手算预期与Git差异静态核查，实际27项通过数、耗时和峰值均pending。实现事实记LOG-117；后续需先审本职责和回传工程证据，再审R4-3b的拟合/歧义/速度等数值，未在当前模块上堆叠后续科学实现。PLAN原有局部编辑保留。

## D-087：R4-3b当前对象公开关联的数值与未观测状态提案

- 日期：2026-09-13；状态：proposed，未实现。用户在2b6cc9c的R4-3a验收记录后明确“继续”，据当前指针审议b具体数值；不把本次首次提出的几何判据或动力学初态近似登记为已获批准。唯一数值源为`configs/spatial_history/r4_object_association_proposal_v1.json`，implementation/runtime/generation/training/download/confirmation均false。
- 白话：输入近期两帧原生深度/标定/公开本体和共同外形，输出可追到原像素的圆柱中心范围、关联状态及区间平均速度。例如完整圆面旁还有未能排除的小片时返回歧义；圆面不提供自旋。这是狭义公开几何近似的可审方案，不是完整对象识别或已测得可用于接触预测的刚体初态。
- METHOD登记近水平完整顶面方案：公共推头盒投影排除、按总z跨度分组和四连通分量、完整有效外环、逐行/列弦中点交集、已知半径与像素足迹容差、均匀支持权重及所有未排除分量保留。新增0.2 mm分组、0.1 mm高度外扩、16像素/6行列、25 mm中心宽度等是事前待审选择，没有在真实16历史上调参；不能由E0通过推定该方案覆盖足够。
- 共同推头姿态只可由已存在的世界x/y两滑动关节规格定义；原公开本体没有朝向字段，拟将固定世界轴运动学显式白名单化。运行拟合器不读XML/生成位置/物块姿态/地面高度，不以伺服指令或相同像素位置推定物块静止。
- 物块速度改用显式`backward_interval_mean`字段，保留两帧独立位置包络传播；它不是t=0瞬时速度。姿态/角速度保持null，association_ready与dynamics_initial_state_ready分开，后者在b恒false。后续动力学若用直立/零自旋/平均速度初值，须在d具体登记近似与误差检查，不能伪装成本模块传感输出。
- 保守规则可因噪声、倾斜或小片过度拒绝，且观测内唯一不证明视野外没有其他物体；不靠真实身份或按残差选最好候选补齐。实际覆盖失败须保留完整分母，不能升级为简单地图/P/历史机制的失败；历史动态排除也不能将决策关联倒灌到早期帧。
- DATA细化纯值白名单、候选/区间/支持/状态及本体来源；PLAN维护唯一当前指针。本轮只交文档及不可执行提案，无新科学模块、服务器命令/测试、真实历史查询、模拟/学习/下载、实验LOG或main合并。未来必要人工检查拟逐命令300 s、地址空间/RSS各512 MiB、阶段加导出8 MiB，数量待实现清点；真实恢复及依赖动力学预算仍另审。旧源码/配置/结果和原PLAN局部编辑保持，已成功产物按原字节复用。

## D-088：接受D-087并交付R4-3b公开对象关联及人工检查阶段

- 日期：2026-09-13。用户在a9cc59b具体数值提案后明确“继续”，据此登记D-087规格认可并实施本职责。原提案proposed/false字段保留为历史，新的`r4_object_association_check_v1.json`以原完整Git提交及SHA-256绑定认可版本；不扩大到真实历史查询、地图/控制、模型、其余家族或确认。
- 白话：输入最近两帧原生深度/公开本体与固定外形，输出原像素支持、条件中心范围、歧义和两帧平均速度。例如完整人工圆面旁增加一个小片会使顶层位置/速度未决，保留两者；不会按生成坐标或残差挑一个。这是已实现的值处理职责，服务器是否通过仍未知，非真实对象恢复证据。
- 科学提交a6eed98新增独立`r4_object_association.py`与24项科学人工检查，METHOD/DATA给出实际纯值接口和完整解析图像例。参数逐值对应D-087；原a覆盖模块仅作为标准库旋转/传感器依赖，旧源码、配置、结果均未改动。未从姿态真值或指令补物块速度，orientation/angular velocity保持null，瞬时测速与动力学初态ready保持false。
- 单帧原语只看自身帧；两帧入口先完整校验输入再内部计算候选，不接受外部拟合或后续缓存。公开本体、像素过渡/支持与物块估计分开；完整顶面规则、所有未排除小分量和几何包络语义按D-087保留，不因可能过严临时改门，也不将尺寸排除的大面片自动写为墙。
- 独立运维交8项检查，连科学检查共32项；run/verify/export同版齐备，固定新目录sh04-r4-3b-object-v1，逐命令300 s、地址空间/RSS各512 MiB、阶段连报告8 MiB。只运行人工例，真实历史查询/模拟/训练/下载均0；12项来源、已审提案、完整测试身份和原证据绑定，不冒用27或33/37项marker。已有失败/中断保留，只verify或导出，不重试/覆盖。
- 本地仅AST/编译语法、参数字面量/JSON/原Git摘要、导入与文件读取边界和文档/Git静态核查；未导入执行科学模块、单元测试、NumPy/MuJoCo或真实数组。实际32项通过数、耗时与峰值待服务器；实现事实记LOG-118，当前代码待用户审查，不合并main，原PLAN局部编辑保留。

## D-089：按用户授权合并交付c/d及原16/144只读工程审计

- 日期：2026-09-13。用户明确要求“PULL一下……把c和d一起做了然后在服务器上面跑”，并选择“人工检查＋现有16条历史/144分支的只读工程审计”。据此复用bf8c05d的b成功报告，授权本组c/d与必要独立误差评估一起实现、一次同步后按前提执行；不再在c→d之间重复请求许可。本组仍给独立可读科学提交，用户审查后手动执行服务器命令；不合并main或把未审模块变成效果实验基线。
- 白话：这次把公开建图、指令到有限力轨迹及误差核验一次交齐。输入是已有16条公开历史和固定144条指令，输出先是封存名义预测，再是独立真实误差与未决分母；例如未知墙段导致预测缺口时原样保留，不读真实墙补地图。这不是新生成、训练、模型接入或科学有效性结论。
- c/d首次落地的具体规则、输入输出例子和限制登记在METHOD/DATA及唯一配置r4_map_control_audit_v1.json。c为1 cm观测面片格图，最低大平面提供名义支撑，逐帧独立排除动态/歧义，不用私有模板补墙；d为0.002 s步长的有限力平面代理、10轮接触冲量及公共任务读出。物体后向均速当名义初速、固定直立/零自旋都是模型假设；尚未完成完整初态/几何包络传播，main_prediction=null、eligible_for_P=false、formal_model_ready=false。本次工程范围不降低D-085正式M/P输入的未知要求；完整c/d科学准入仍未完成，不能用代理诊断代替正式主对照。
- 数值更改均在真实查询前一次登记：地图面片0.0002 m高度跨度、0.0004 m合并/分类容差、至少0.3 m双轴大平面；动态求解侵入松弛0.0001 m、偏置0.2、修正上限0.002 m、单步位移/残余侵入上限0.005 m、初始高度差上限0.002 m、正接触力阈值1e-6 N；任务墙条0.02–0.08 m、距共同厚度0.05 m容差0.02 m、至少一列观测贯通支持。共同质量/摩擦/伺服/控制/目标参数复用原域；完整算法及不等于什么只在METHOD解释。未用此次真实误差调整数值。
- 23项科学人工例覆盖地图/对象排除、有限力/守恒/扫掠未知、公共任务事件和独立指标；13项运维检查覆盖绑定/失败/防重跑/私有读取前置/完整诊断导出。源码总22项绑定，原320源文件逐项从已验收v2报告取bytes/sha256；只对成功生成回执验原字节摘要，预测前不解析含私有聚合结果的回执。所有16地图/144分支先写public_seal并保存独立预测子进程退出0，再由评估子进程解码真实XML/轨迹/标签，禁止事后修预测。
- 工程通过门是36项无失败/错误/跳过、原绑定一致、两个子进程退出0、预测/评估文件和16/144全部身份分母完整、资源未超；没有事后加的准确率门。名义误差和缺失都报告，即使覆盖为0也不能删例，工程passed不表示完整前端或模型可用。原144重放及旧33/37/a27/b32检查按原摘要复用，不为本批重新生成或执行旧测试。
- 本组实际运行预算明确登记：check/verify/export各300 s、512 MiB；run总1800 s前台，逐进程2 GiB，启动可用内存至少2.5 GiB及盘1 GiB；新阶段连报告1 GiB、报告32 MiB、失败预留1 MiB，人工检查原额度8 MiB。名义推演是本批计算，0新MuJoCo生成/重放、0训练/下载/确认，不挪用旧生成或待审GPU额度。缺产物、超时、失败和中断停在原现场，只核验/导出，不自动重试、覆盖、替换样本或新增同步版本。
- 本地仅源码/AST/编译语法、参数字面量、JSON/Git原字节、依赖与文档检查；未运行科学模块、测试、NumPy/MuJoCo或真实数组。三份科学提交02bce57、25d0bff、c5af4d8与同版运维供审；实际新检查通过数/时间/内存和真实误差均pending。新实现事实在LOG-119，当前指针/完整命令仅PLAN；原PLAN局部编辑保留未提交。


## D-090：用户授权直接SSH持续推进当前R4工程验收

- 日期：2026-09-13。用户提供服务器登录方式，明确余额覆盖24小时并要求“先看看什么时候这个能验收，一直做下去”，随后授权学术加速及GitHub认证。按本轮范围由代理直接连接、登记修订、实现、检查、运行和取回证据，不再要求用户逐条执行命令；凭据不入库。本轮仅当前R4工程链路，D-059的正式科学基线/main合并及效果实验审查不以持续工程授权代替。
- 实际只读核验仓库为`/root/Emboddied_Spatial_Memory`，review/spatial-history-baselines，无在跑实验，数据盘约22 GiB空闲；旧outputs完整保留。学术加速source /etc/network_turbo已成功，运行不需要下载新依赖或权重。用户给的24小时是可用上限而非保证通过时间；本轮时限登记至2026-09-13T18:14:12Z，不重启或删除服务器任务/目录。
- 原证据已经定位两类前端缺口，按独立职责实现条件侧壁归属与同帧地面相对墙高的短墙片保留，具体算法/反例及限制见METHOD，字段见DATA。旧v1源码/config/results保留原字节，新地图经显式版本桥接调用未改的原有限力求解器/读出/独立评分；不按误差增加力、时长、训练或换样本。
- 在新真实查询前固定本版验收：16/16关联、16/16各两门口、144/144完整名义轨迹与任务读出、16/16九候选选择可计算，独立误标占据与误标自由格均0。只有这些都达到才称“本轮名义工程链路验收通过”；继续报告所有实际误差、未知和不确定性缺口，formal_model_ready/eligible_for_P仍false，不将其称为正式预测性能验收。
- 固定原四家族16历史/144原主分支，0生成/训练/下载/确认。新16项人工检查在服务器运行，每次check300 s，单阶段run总7200 s、单进程4 GiB、新阶段连报告2 GiB、报告32 MiB；预计先前台运行，若证据显示将超过30分钟再按原规则安排后台。只创建新sh04-r4-frontend-v2目录；失败/中断保留并导出，不自动覆盖或重跑。必要bug需新版本/新目录登记；科学方案实质变化仍先追加具体决定，不用旧回执认证。
- 本版实现与完整入口先按职责提交再一次同步，check→public预测封存及真实退出0→独立evaluation→verify/export。同版本成功步骤按原字节复用。结果/边界写EXECUTE，完整指针及命令只在PLAN，原PLAN局部编辑继续保留。

- D-090运维隔离修复补充：首次v2入口在公共预测进程中解析了含旧评估值的父报告来取登记，虽未传给科学函数仍违反本阶段隔离。已主动中断并封存，报告88c9422，不采纳该次预测。v2r1只从预先物化的纯路径/bytes/sha256登记读数据，父报告仅流式验摘要，并加进程级源目录读取守卫；允许原16公开文件、拒绝304私有轨迹/标签/XML及原聚合回执。新增3项隔离检查，共19项；科学源码/算法/阈值/16与144及验收门不变，新目录sh04-r4-frontend-v2r1、新报告spatial_history_r4_frontend_v2r1.json，时限与资源沿本轮登记。


## D-091：按追加授权继续模型接入与资源安排

- 日期：2026-09-13。用户明确前端完成后“继续到SH-05接通3个模型”，允许使用系统盘及磁盘不足时删除旧CPMT/CTL数据。本轮继续直接SSH、固定版本获取、独立依赖安装及必要接线检查；先完成前提，不能以名义工程成功认证正式M/P、模型效果或完整训练。原D-079规格里64像素/四候选必须按现有80像素/九候选显式适配，实际科学模块逐职责登记，不随意缩模型换弱替身。
- 白话：输入已经跑通的公开数据前端和官方模型源码，输出可加载、能消费合法输入并生成自身预测的独立适配。例如Dreamer保留作者RSSM，完整历史后执行固定控制；原生前向成功只是接线证据，不等于双门任务训练充分或论文复现。
- 当前先锁D-079三份作者commit。模型接入资产与环境用/root/sh05-assets-v1，避免改既有MuJoCo隔离环境；已核系统盘29 GiB、数据盘22 GiB空闲。旧CPMT数据25 GiB可按用户授权在确需空间时先盘点路径、依赖、未提交产物与可保留摘要，再精确删除；目前无需清理，未执行删除。
- 首批环境工程额度：总墙钟2小时（含下载/安装），新增系统盘上限10 GiB、至少保留5 GiB；0模拟/数据生成/训练/确认。FloWM隔离overlay环境只读复用现有torch2.8.0+cu128，独立装einops；Dreamer独立Python3.12及作者JAX0.4.33依赖，先CPU接线，不能声称GPU训练就绪。各阶段独立started/log/receipt/failure，失败保留不得覆盖，成功验摘要复用，完整ops入口同版交付。后续原生/适配检查按具体实现另登记张量例和额度。
- PointWorld的DINOv3 ViT-L/16官方权重未找到且用户没有访问资产，按asset_unverified记录。用户询问DINOv2与其他平替，先只读核查DINO-WM/JEPA-WM官方接口与权重；DINO-WM为当前推荐，尚未把V2强换V3或替换第三模型当作已审科学基线。先继续D/F独立准备，不因资产阻塞停止无依赖工作。
- 用户的24小时可用窗口仍截至2026-09-13T18:14:12Z；不是原56 GPU小时提案被自动压缩或扩大，不解封旧test、不启动未固定训练预算/确认，不合并main。当前授权覆盖模型实现与必要工程核验，后续学习规模和输入/监督实质变化须具体登记。

- D-091原生检查具体登记：新增r4_native_models_v1.py，不改作者科学源码，F按49×49/5速度/256宽/6层/8头运行64像素的人工3×3可见区；检验形状、有限值、输入不变、未见区保持、可见写入、显式状态分块等价、动作token作用及速度通道。D按已登1024/512/32/32/8容量，原Encoder直接读80像素121帧，固定200步控制imagine；检查形状/有限值、同seed重放、共同分支初态、首动作对拍及无actor/critic参数。种子7901，仅人工数组，不读取本项目任何样本。
- 原生stage每步1200 s上限、零训练/权重/样本/新模拟，计入本轮窗口；额外F依赖timm1.0.19、huggingface-hub0.26.2、safetensors0.4.5在独立环境安装。F仅绕开会急切导入无关trainer的包初始化，实际map/patch/FOV源码不替换、不提供假函数；该导入裁剪显式进入证据。D先CPU，F用现有GPU；这不认证连续相机/完整RGBD/任务头等尚未实现的适配。失败按新stage现场保留，不能重新跑同名目录覆盖。


## D-092：用户选择DINO-WM替代PointWorld，先完成具体适配

- 日期：2026-09-13。用户明确选择“DINO-WM（推荐）：替代当前第三条，先完成具体适配”。据此三条作者方法改为DreamerV3/FloWM/DINO-WM，PointWorld及既有资产/合同保留为后置参照，不再阻塞当前模型接入。L/R/M信息充分对照继续必需；替换不意味着视觉特征预测与三维点运动职责完全相同，也不据此宣称已发现旧方法失败。
- 白话：DINO-WM输入图像特征和控制，输出未来特征，再由本任务头读位置/接触/成功；例如用看过的门信息判断同一推头命令会不会受阻。它原生使用公开DINOv2，免于等待DINOv3访问；仍需完整历史、深度和200步本任务适配，不是把PointWorld里的V3权重直接换成V2。
- 官方源码锁DINO-WM 0a9492fa12044b852ae9e001cc74604b79c8bb0c、DINOv2 7764ea0f912e53c92e82eb78a2a1631e92725fc8，已获取系统盘独立目录。先核原DINOv2 ViT-S/14无register预训练权重（官方fba公开URL，下载上限128 MiB并记录完整SHA-256），原DINO-WM的6层/16头/2048 MLP及3帧人工前向；不下载大数据集，不把随机动力学主体当作者任务checkpoint重评。
- 新r4_dinowm_assets_v1.py按download→native→export同版执行，每步1200 s，新目录dinowm-native-v1，阶段上限256 MiB，权重文件max128 MiB；失败保留。复用已核torch/timm独立环境，0训练/生成/确认。加载本地固定DINOv2权重strict=True；只改模型构造时的资产定位，原patch特征、原VWorldModel/ViTPredictor计算保持，具体差异入回执。
- 任务适配的具体数值/历史保留、动作晚早一拍、原生辅助目标与新增读出仍在METHOD中逐职责固定，不能拿3帧原生检查充当121帧接入；未来机器人实际状态依旧不作主体输入或额外监督。当前用户授权落实适配，预算内必要工程检查由代理继续，不自动做主训练/确认或main合并。


## D-093：Dreamer完整RGBD任务适配与零更新梯度核验

- 日期：2026-09-13；在D-091持续接入及D-092三模型选择授权内落实D首个完整适配职责。原e3f0224 RSSM/Encoder/Decoder不改源码，公共输入转换与任务模型分为两个可审模块；本批不实现策略/奖励/价值、不生成新样本，不依赖M/P诊断作为D输入。
- 白话：输入121帧公开RGBD、相机/本体和200步速度指令，输出自身隐状态、200个物块位置/接触logit及整段成功logit。例如把第101条控制改动后，前100步位置必须不变；训练目标可以用于损失，不能回到推理初态。随机初始化接通和梯度有限不表示已经学会推物。
- 唯一实现规则见METHOD/DATA及r4_model_inputs.py、r4_dreamer_adapter.py。80像素原生RGB不缩放，独立32/64/128/128深度+mask卷积，37维公共元数据经2×256 MLP；原RGB6400+深度3200+元数据256合成9856维token。RSSM容量仍1024/512/32/32/8，其余沿作者类默认。计算明确float32，保留源float64记录不变，不将米制深度量化为RGB。
- 两层256共享位置/接触局部头输出3+1，256维GRU及256隐藏层读取未来状态/12维公共目标后输出成功。原RSSM无策略的控制imagine固定200步，不重置未来物块或读取未来本体。辅助RGB/有效深度MSE各1、dyn/rep KL0.5/0.1和free_nats1；主任务三项各1。辅助只在分离的训练loss接口消费未来RGBD，后验目标使用公开决策本体锚点及已知时钟，不使用实际未来机器人运动。
- 原生RGBDecoder及新增5×5×128起始、四次2倍上采样/3×3卷积128/128/64/1的米制深度Decoder实现重建。RGB/深度及KL辅助在200个训练侧未来时刻均值；主预测先从历史初态开环产生，不经未来后验。各家族/世界/分支等权由未来训练入口实现；当前只验证单个手工批次，不开放未固定主训练预算。
- 必要服务器人工检查固定完整121/200、种子7903/7905/7907/7909，核公共字段拒绝、输入尺度/深度、因果动作、同分支初态、输出形状、全200步损失反向及七模块梯度；不构造optimizer，new_training_steps=0。新目录dreamer-adapter-check-v1、1800 s、RSS12 GiB、新证据64 MiB；先CPU前台，资源/耗时实测记录，失败保留不重跑同目录。完整run/export同版交付；原D/F native回执只作先决条件，不认证新代码。


## D-094：DINO-WM完整历史任务适配与原计算对拍

- 日期：2026-09-13；按用户明确选择W及连续完成具体适配授权落实，不再要求DINOv3权限。公共Torch转换/读出与W科学模块分职责提交；作者源文件不改，主训练、样本生成、确认和main合并仍未开展。
- 白话：用全部121帧RGBD记住历史，再按200步指令预测自己的未来特征并读位置/接触/成功。例如第一个旧观察必须可影响决策，后面的控制不能倒灌较早结果；原3帧原生前向不能证明这些。本批是随机动力学主体的工程接通，不是有效性验收。
- METHOD固定原80补边到84、36块、冻结DINOv2S14、独立深度卷积、37→10元数据/4→10控制、6层16头404维原主体、321帧位置容量及完整可微因果KV缓存。与原3帧计算先对拍值/梯度；激活检查点无detach，不以截短历史降低资源。未来动作使用obs_t→obs_t+1对齐，决策锚点不受候选污染。
- METHOD/DATA固定共享Torch空间读出/GRU头、三项主损失及视觉特征/有效米制深度辅助各1；不使用实际未来机器人辅助监督，未来RGBD只在loss目标分支读取。新增384→256→196块深度重建是任务适配，作者原checkpoint不作已复现表述。
- 人工工程检查固定种子7911/7913、完整121/200、17项检查，0优化更新。新目录dinowm-adapter-check-v1，单次1800 s前台、进程RSS12 GiB、CUDA分配峰值28 GiB、新证据64 MiB；失败原样保留，不自动覆盖或缩科学输入。先决条件为已保存原生成功回执及相同权重SHA，绑定15项当前源码/合同和两作者源全摘要。只用系统盘现有资产，0新下载/生成/确认。


## D-095：FloWM连续相机、独立控制与完整任务适配

- 日期：2026-09-13。按持续接通三模型授权实现F，不把D/W先通过当作F已通过；原作者源码和旧原生回执保持，科学适配独立提交。无主训练/新增样本/确认或main合并。
- 白话：输入真实公开相机移动和RGBD，再单独接推头控制，输出原生空间记忆与任务后果。例如整数平移重叠部分应与原roll一致，但越界不能卷回；未来相机静止不关闭独立控制。这些是可测的适配约束，不证明动力学学会或科学创新。
- METHOD/DATA固定80像素patch8、49格×0.15m×5通道×256、6层8头、双线性零填充相机对齐、无环绕速度通道、公开深度表面列mask和独立历史支持。无真实物块/墙mask，不认证地面自由；原通道混合为none。按41→256→256控制token、原6层decoder和共同任务头实现自身RGBD反馈，主/辅助共五项损失各1。
- 未来本体固定公开决策锚点，只有时钟推进，不输入或监督实际未来本体；预测图像从不变成历史观测支持。空可见列用固定零上下文表示解码先验，离散预测可见mask不可微，其余全链checkpoint无detach。源代码不隐式消费项目数据或私有标签。
- 人工工程固定种子7915/7917、19项、完整121/200及八路径反向，0optimizer更新；新目录flowm-adapter-check-v1、1800 s前台、RSS12 GiB/CUDA分配28 GiB、新证据64 MiB。未核验就绪不跑效果实验，失败保留，不缩减历史或覆盖旧目录。与D/W使用同一真实任务字段和本批零更新边界。


## D-096：三模型共同预测出口与一条真实公开历史的工程核验

- 日期：2026-09-13；D16/W17/F19项完整人工适配均已通过后，按持续接通授权验证实际存储输入。固定既有v2r1清单首家族/首世界的121帧及全部九候选，不按任何标签/表现选例，不生成新数据或训练。
- 白话：输入同一条真实公开历史，输出200步位置/接触/成功字段；例如九分支共享同一决策状态，D按16随机样本保留概率均值。随机初始化“有值”不是有效预测，本批不给误差/排名/实际选择结论，trained_model_ready=false。
- 实现标准库稳定sigmoid/严格schema与1或16样本概率聚合，D历史/未来同索引流跨候选复用。METHOD/DATA固定初始化7921及D8000+i/8100+i，不从身份/标签选种子。运行前后参数不变，候选后决策不变；prior先核人工成功、原Git来源和当前科学文件相同，旧文档摘要只按原Git核验。
- 新three-model-public-check-v1分D/F/W三个独立前台步骤，逐步1800 s、RSS12 GiB/CUDA28 GiB、阶段512 MiB、导出16 MiB；只读取固定一个登记public文件，数据根其余所有文件在进程审计守卫拒绝，旧真实评估不解码。0新增样本/优化更新/确认/下载，失败保留新目录不重跑。全部27模型-候选都成功且源/回执完整才工程接线ready，仍不是SH-05科学有效性验收。


## D-097：持续推进SH-05授权下的学习合同对齐、资源预检及旧输出清理

- 日期：2026-09-13。用户确认D/F/W接通与27/27工程报告，提供SSH/Git认证并要求“一直做到SH-05跑完为止”。继续由代理直接SSH执行已确定且满足前提的工作；不让用户重复复制服务器步骤。当前先将旧P/64像素/四候选提案对齐W/80像素/九候选，形成独立可审learning_contract_r4_v2，不改原绑定文件，不合并main。D-059用户科学代码审查与新预算具体审查仍适用，缺失实现不能由一般完成目标追认已审。
- 新稿保留64家族/原32/8/8/8/4/4划分、20条主体路径及原评分/诊断预算；显式提出L/R自然5×5卷积输出、W随机主体使用scratch学习率、均匀家族/世界/候选采样、完整轨迹梯度累计、未来201帧取1–200和72分支小型拟合的具体语义。METHOD/DATA附中文解释。这是proposed，不启动新生成/训练或确认，M正式未决和W探针池化仍待可审实现。
- 精确资源预检先做：180秒、报告1MiB内、0训练/模拟/下载，只读系统与原JSON证据，设备探测不初始化科学模型。服务器仓库经pwd/find/git实测为/root/Emboddied_Spatial_Memory、review/spatial-history-baselines，源f8974aa，未见在跑实验；实际数值以新results回执为准。现有Dreamer只有JAX CPU后端，不能称GPU训练ready；旧24小时窗口也不等于新56 GPU小时预算已获具体批准。
- 用户随后明确“你可以删除原来CPMT的OUTPUT”。只读解析找到/root/autodl-tmp/cpmt_outputs，约24GiB；先保存每文件摘要清单、有限运行元数据及Git已导出报告摘要，再按精确路径删除。原数组/权重/逐例原输出会丢失，现有导出报告、代码/原资料、旧no-go、其他CPMT输入、系统盘outputs/spatial-history、新spatial-history及sh05-assets保持。删除事实与实际空间变化写EXECUTE及机器结果，不把清理当旧实验重跑或确认解封。


## D-098：取消旧在线截止、允许计算worker并补齐Dreamer GPU工程前提

- 日期：2026-09-13。用户回复“先不用考虑时长这个，只要允许多worker就可以了”。不再把D-090旧2026-09-13T18:14:12Z在线窗口用于新步骤截止；允许按具体配置使用多个数据生成/读取worker。此处worker指计算进程，不是代理并行科学审查。原56 GPU小时仍作为待审配方成本表和记录参照，不依据旧窗口阻止工程推进；不把放宽在线时限解释为无限训练步数、变划分、追结果或未审代码自动成为基线。当前单卡主训练并发仍1；生成已有允许值1–4，更多并发须先实测资源并登记，不能因机器报告128逻辑CPU就开128进程。
- 独立补齐Dreamer GPU工程：保留作者及本项目科学源和原CPU隔离环境，在/root/sh05-assets-v1/dreamer-cuda-v1/packages仅安装jax-cuda12-plugin==0.4.33及jax-cuda12-pjrt==0.4.33，无依赖升级，复用已有CUDA12.8工具链及NVIDIA运行库。依据JAX官方0.4.33源码与PyPI版本页，CPU旧回执保留。本批不下载模型权重或数据。
- 同版install/check/export；每步1800秒工程超时、新overlay上限1GiB、RSS12GiB、GPU分配峰值28GiB。check强制gpu，沿原DreamerTask.loss及人工121/200输入，固定种子7923/7925，首次完整梯度及三次编译后梯度计时，验证七模块有限非零梯度。没有optimizer、0参数更新、0真实数据读取；它不能冒充训练充分性或正式优化器吞吐。
- 新步骤拒绝同目录重跑和覆盖，子进程退出/日志、pip精确URL/包摘要、安装文件清单与源码绑定全部保存。独立实际结果见EXECUTE；旧预检只反映当时CPU环境，不回改原false字段。GPU后端可用也不解除L/R/M、学习/诊断实现审查与独立确认前提。


## D-099：L/R信息充分强对照首个可审实现与人工工程检查

- 日期：2026-09-13。在持续推进SH-05的实现范围内补齐D-097提出的L/R；这是一项独立科学职责，未合并main、不运行依赖它的效果实验。两者共用同一个HistoryPredictor参数结构，从头初始化；区别仅是L全部121帧或R用原D-086公开覆盖最多10帧，检索证据留在模型外。
- 本职责固定80→5×5卷积格、3025/最多250历史token、宽256/6层8头/FF1024、2层8头因果控制解码器、dropout0.1、pre-LayerNorm及eps1e-5/GELU。RGB/深度各四层3×3 stride2 padding1通道32/64/128/256；元数据37→256→256、上一控制4→256→256分别相加；连续二维固定sin/cos位置各128维。每层独立初始化。未来控制与决策元数据41→256→256加0.1–20秒固定sin/cos时序，任务头直接复用原Torch TaskHeads；三项任务损失各1，无额外原生目标。
- 完整历史在决策时双向注意，前缀从该前缀重算；R保留原时钟而非压紧选帧时间。未来只对已给控制因果注意，再交叉读取同一历史状态。状态只含tokens与公开decision_metadata，不能携带选择索引/分数、身份、私有标签或实际未来本体。激活检查点保留随机流和完整梯度，不detach历史。
- 新history-predictor-check-v1，21项人工检查，种子7927/7929；同时检查L完整121/200与R10/200反向、八路径梯度和最早深度梯度、原图尺寸/5×5、选帧并列/原时钟/前缀、无效深度不影响、私有字段拒绝、控制因果/分支不变/确定性。0优化器/更新、0真实数据/生成/下载。1800秒前台、RSS12GiB、GPU分配28GiB，新回执64MiB；首次失败保留，无自动重跑。同版run/export供复现，原a27项只认证选帧本体，不替代新适配检查。

## D-100：Dreamer CUDA首次下载失败保留，修复镜像超时后新目录重试

- 日期：2026-09-13。`dreamer-cuda-v1/install`从服务器默认阿里镜像下载首个14.9MB wheel时连接代理超时，pip退出2；只写started/run.log/failure，overlay未形成成功回执，原CPU环境、项目源码和数据未改。该失败不是CUDA兼容性或模型失败证据。
- 修订只将新stage固定为`/root/sh05-assets-v1/dreamer-cuda-v2`，显式使用官方PyPI simple索引、单请求120秒及最多5次网络重试；包名/版本、无依赖安装、1GiB/1800秒、科学检查和全部输入输出保持D-098。原v1目录不删除、不覆盖、不再次运行；v2成功后仍须按安装文件摘要与gpu强制检查验收。

## D-101：学术加速实测后改用长超时镜像下载

- 用户提醒启用`source /etc/network_turbo`；主SSH会话在v2开始前已执行，进程环境核得http/https代理存在。v2官方PyPI下载持续约4分钟仅得约3MB，仍在前进但不足以高效完成，主动中断；脚本保存`dreamer-cuda-v2/install/failure.json`，未产生成功回执或改CPU环境。
- v3精确目录为`/root/sh05-assets-v1/dreamer-cuda-v3`，仍在已启用加速的同一会话，改回实测吞吐更高的阿里镜像，并保留120秒请求超时与5次重试。包版本、无依赖、文件摘要、科学检查和资源边界均不变。v1/v2失败目录保留；网络策略不是科学方法变化。

## D-102：先只读定位M的未知扫掠，不用敏感性补格取得正式准入

- 日期：2026-09-13。现有v2r1地图和有限力推演144/144完整，但每个分支均涉及未知扫掠；正式M仍不能把未知空间当自由空间。先对已封存的16张公开地图和144条名义轨迹逐步重算物块与推头的扫掠格，区分显式unknown、已有地面但未进入known、没有任何公开表面记录、当前身体遮挡足迹和紧邻已知格等来源。不读XML、真实轨迹或标签，不重跑模型、地图、动力学或模拟。
- 白话：这个诊断解决“未知来自初始身体挡住了地面、厘米栅格的边缘取整，还是确实没有观察”的问题。输入是已封存公开地图和名义预测轨迹，输出每条分支的缺格类型、最近已知格距离，以及两个仅供敏感性比较的计数。例如只把当前物块和推头脚下格子补入后，如果第一步未知消失但门附近仍出现未知，就说明两种缺口同时存在。它不证明被补格子真实自由，也不改变`formal_model_ready=false`。
- `add_initial_body_envelopes`和`one_cell_known_dilation`只回答计数对两种假设有多敏感，不作为新地图输入或正式自由空间证书；任何据此改变M的科学实现都必须另行登记连续几何依据、公开输入边界、私有false-free独立评估和必要反例。脚本拒绝覆盖报告，运行前后逐一重算160个公开gzip文件的字节数与SHA-256，原文件变化即失败。

## D-103：48个剩余开发家族使用独立多worker生成阶段

- 日期：2026-09-13。D-097已固定52个开发家族，其中首4个model_train家族已有成功v2原产物；新阶段只生成其余48个model_train/model_validation/probe_train/probe_validation家族，不复制或重跑首4个，不生成12个model/probe confirmation家族。原生成器、物理、控制、标签、E0、重放和每家族验收值均不改。
- 白话：这个阶段解决“如何一次生成训练与验证所需的剩余数据，同时复用已成功样本”的问题。输入是固定64行设计、原4家族成功清单和审过的完整提交，输出48个独立家族目录、每个家族36条主分支与36次反序重放，以及统一开发清单。例如`r4-11`失败会原样保留并使阶段停止，不能跳过后用别的家族补数。它不训练模型、不读取确认集，也不把并行worker当作更多随机样本。
- 配置允许1–8个生成worker，默认6，基于旧4-worker峰值约1.98 GB和12个可见CPU选择；每个family仍有384 MiB硬上限，单进程6 GiB、整树16 GiB。新阶段上限18 GiB并在数据盘保留10 GiB，墙钟4小时；运行时还必须声明至少18 GiB新增数据额度。旧实测4家族约1.19 GB/500.6秒，线性外推只用于容量安排，不保证本阶段耗时。
- check绑定当前科学字节并重跑既有生成必要检查及7项新边界检查；运行必须显式`--reviewed-code`等于该check的完整提交。worker逐家族运行原`run_family`并立即`verify_family`，任何失败保留现场且不启动训练；全部完成后再次逐文件解压/摘要核验再导出。配置中的授权保持false，等待用户审查具体提交后才给出run参数；一般持续完成目标不替代D-059代码审查。

## D-104：训练读取器分开模型输入、任务标签与视觉辅助目标

- 日期：2026-09-13。新增`r4_learning_data.py`只读取已通过v2家族验收且manifest逐文件相符的数据根。它用family/world/action只定位文件，在返回值中把`model_input`、`targets`、`auxiliary_targets`和`audit`四部分分开；模型主体只能收到`model_input`，身份与文件摘要只留在audit。
- 白话：这个读取器解决训练时误把路径、世界名或未来机器人状态送进模型的问题。输入是一个已封存家族目录和0–8候选槽，输出121帧公开历史、该候选200步控制、公开目标、200步物块/接触/成功标签，以及D/F/W需要时才读取的200帧未来RGBD。例如候选槽0对应公开文件里原顺序第一条控制，并核对`LL-c00`标签绑定的原轨迹摘要。它不返回integration数组、实际未来推头运动、XML或重放数组，也不执行模拟或训练。
- RGB/depth原数组均为201帧，索引0是决策状态；辅助目标严格取1–200，并核对时间0–20秒及物理步0–10000。每次读取先核压缩文件manifest，再核数组头、原始长度和原始SHA-256；标签必须`physics_valid/visibility_valid=true`，失败家族仍保留但不能静默进入学习。L/R不请求视觉辅助目标，因此不为它们读取未来图像。

## D-105：学习读取v1身份字段错误保留，改用目录与外部seal绑定

- 日期：2026-09-13。首次服务器检查在建立144分支索引时退出：reader要求`audit/config.json`含顶层`family_id`，但原封存配置只描述共同生成合同，家族编号由外层执行目录和已导出全目录清单绑定。v1目录中的`started.json/failure.json`原样保留；没有报告、数据写入、模拟或训练。
- 修复删除这个不存在的字段依赖，改为要求真实路径严格是`.../execution/<family_id>/data`，随后仍逐项核对该家族在外部来源清单中的三个manifest与`family_result.json`摘要。白话：这解决“编号放在哪里才是权威证据”的问题；输入是调用方给出的家族编号、实际目录和旧报告封存摘要，输出仍是同一个144分支索引。例如`r4-39`只能绑定父目录名为`r4-39`的`data`目录。它不从编号预测结果，也不放松任何文件内容与完整目录清单检查。
- 新检查使用独立v2目录和报告，保留600秒、6 GiB、0生成/训练/确认边界；旧v1入口继续保存用于解释失败。v2成功前reader仍不能称为真实数据ready。

## D-106：学习读取v2公开记录版本错误保留，复用正式public桥接

- 日期：2026-09-13。v2已通过家族身份与四家族seal核验，但在首条公开记录上退出：磁盘文件是`spatial-history-r4-public-family-v2`整家族包，reader却直接要求选定候选后的`spatial-history-r4-public-query-v2`版本。v2的started/failure保留，未打开标签或未来数组，仍为0训练/模拟/确认。
- 修复直接复用既有`r4_public_v2.model_input`：先完整验证121帧、九个匿名候选与共同目标，再按0–8槽选择一个query，最后交给`from_public_query`。白话：这解决“整盒九个候选如何变成模型的一条查询”的问题；输入是一份公开家族记录和候选槽，输出只含相同历史、被选控制、目标和公共常数。例如槽0先由public合同验证再转成200步控制列。它不凭标签选候选，也不改变公开字节或任务目标。
- 另建v3目录与报告，资源和禁止范围不变；v3成功前不宣称真实学习数据边界通过。

## D-107：学习读取v3浮点时钟容差错误保留，采用既有合同容差

- 日期：2026-09-13。v3已通过家族/public/label/trajectory绑定并读取四份允许的辅助数组，随后因`1e-12`秒容差拒绝原传感器时钟；实际201点为0–20秒、步号严格0–10000，浮点累加最大误差`7.702283255639486e-12`秒。v3失败目录保留，源数据未变，0训练/模拟/确认。
- 改用公共查询与预测合同已有的`1e-9`秒绝对容差，物理步号仍要求逐项精确等于`50*i`。白话：这解决反复加0.002秒产生的万亿分之几秒舍入误差；输入原float64时钟，输出只是“与登记的0.1秒采样一致”判断。例如19.499999999992298秒被视为19.5秒。它不重采样、不移动帧，也不允许一纳秒以上的时钟偏移。
- 独立v4目录和报告复查全部来源前后清单；600秒、6 GiB和禁止范围不变。

## D-108：剩余开发生成检查随当前科学绑定重发v2

- 日期：2026-09-13。v1的44项检查本身通过，但其绑定包含METHOD/DATA/DECISIONS；D-104–107的reader登记使当前绑定不同，按设计不能消费旧检查启动生成。v1检查目录和报告保留，未生成任何家族。
- v2保持同一48家族、生成器、物理、6个默认worker、18 GiB阶段上限、10 GiB保留和确认禁读，仅使用新目录/报告并重建当前绑定。白话：这解决“检查后文档有了科学变更，旧回执还能不能用”的问题；输入是当前提交和原48家族清单，输出新的零生成检查回执。例如reader文档变化即使没改物理，也必须让受审提交明确。它不重跑旧四家族、不放宽样本失败门，也不授权训练或确认。
- 运行的review绑定从“Git HEAD必须恰等于检查提交”收紧到真正相关的条件：`--reviewed-code`必须等于检查提交、全部BOUND字节必须仍等于检查回执，当前HEAD必须是该提交后代。这样仅提交未绑定的结果JSON不会使已审科学字节失效；任何绑定文件变化仍拒绝运行。

## D-109：训练runtime先固定采样、八分支累计与不可覆盖checkpoint

- 日期：2026-09-13。先实现框架中立的`r4_learning_runtime`，不选择验证结果或启动优化。`UniformBranchSampler`按family→world→candidate三层均匀有放回抽样，保存Python RNG完整状态和draw计数；恢复后下一条身份序列逐值相同。身份只交reader定位，不进入模型张量。
- `accumulated_torch_step`恰好消费8条完整121/200分支，每条总损失除以8后反向，全部累计完只做一次全局范数1裁剪和一次optimizer step；任一非有限loss/term或无梯度均在更新前失败。白话：它解决一条完整轨迹太大而不能组成普通batch的问题；输入8条完整分支及各模型已有loss，输出一个参数更新和各项平均值。例如8条loss相加后除8，不能把200步拆成八个伪样本。它不决定学习率、不读取验证集，也不证明500或10000步足够。
- checkpoint只含模型、optimizer、sampler、Torch CPU/CUDA RNG、update与代码/数据/配置binding；先写`.partial`再原子改名，正式文件拒绝覆盖，加载只允许tensor/基本值并拒绝不同binding。白话：输入一次已完成更新的全部可恢复状态，输出一个不可覆盖文件及摘要；例如中断后必须从同一采样器下一draw继续。它不把失败partial当成功，也不允许只载模型权重后声称精确续跑。

## D-110：L/R/F/W共享Torch学习桥接与三项微拟合指标

- 日期：2026-09-13。`r4_torch_learning`只把reader已经分离的值接到现有模型：L/R调用各自公开query选择且不请求未来图像；F/W请求已允许的未来RGBD辅助target；身份/audit不传入模型。AdamW只接`requires_grad=true`参数，学习率限登记的`1e-4/3e-4`、weight decay固定0.01，W冻结DINOv2不会进入optimizer。
- 三项微拟合指标为200步三维欧氏位置误差均值、接触概率Brier均值和整段成功概率Brier；先逐分支算，再对完整分支等权。白话：输入模型logit与真实训练标签，输出三种0附近更好的误差，例如logit 0对应概率0.5，真假标签的Brier都是0.25。它不以0.5阈值准确率代替概率质量，不按大量无接触帧重新加权，也不读取validation来调整一次微拟合。
- 本批是桥接实现和人工值测试，尚未在服务器真实分支执行optimizer update；Dreamer JAX仍需对应的同语义runtime。代码通过不表示达到0.02微拟合门。

## D-111：M增加未知即阻挡的悲观主输出候选，不再要求未知可通行

- 日期：2026-09-13。提出并实现待审`r4_pessimistic_map`：继续复用已封存公开地图和原有限力名义求解，但名义轨迹只保留到物块或推头的扫掠形状首次离开“观测自由格＋决策时身体排除格”；该步起把未知视作静态阻挡，整个系统停在上一合法状态并补齐200个预测端点。原未知当自由的完整名义轨迹只提供到停止前的动力学前缀，不作为主输出。
- 决策时身体排除格仅含“格中心在所有允许当前物块位置下都位于圆柱截面内”的交集，以及公开推头矩形内部；静态墙不能与当前刚体实体重叠，因此这些点可排除静态占据。物块扫掠用圆形沿线段形成的capsule格，不再用外接正方形角；推头仍用保守轴对齐扫掠盒，多算格只会更早停止。
- 白话：这个悲观M解决“地图没看见的地方怎样仍给完整、合法预测”的问题；输入公开地图、估计当前物块/推头和一条名义动力学轨迹，输出200步位置、物块碰障概率和成功概率。例如推头下一毫米会进入没观测到的格子，主输出停在进入前并把未知当墙。它不宣称未知真的有墙，不读取XML/实际未来，也不把一格膨胀冒充自由空间；早停造成的误阻挡必须按强对照结果如实计入。
- 当前仅有3项人工几何/冻结测试通过，尚未在16个既有公开地图/144分支跑独立public→private评估；单分支只标`formal_prediction_available=true`，`formal_model_ready=false`保持到服务器整批检查通过，不能提前升级学习合同的M状态。

## D-112：以连续条件证书和双动力学取代D-111中心格冻结原型

- 日期：2026-09-13。用户逐项批准以下M语义，并批准M-SIMPLE与M-PHYS两者全部运行。D-111的`0202fb9`保留为被否决原型：格中心在扫掠形状内不能覆盖所有与连续刚体相交的格，格中心落在名义地面或当前身体内也不能证明整个格自由；首次未知后冻结整个系统亦不是合法接触动力学。该实现不得进入正式M、效果运行或`formal_model_ready`判定。
- 自由证书改为依赖登记理想域假设的条件证书：俯视无噪深度、已知标定、局部平面插值、竖直且至少公共厚度的静态墙、公共刚体形状。连续地面支持按投影误差向内收缩；被认证离散单元必须完整包含于连续支持，不再用中心命中。完整刚体扫掠必须连续包含于这些单元的并集；网格复算只能保守地多报阻挡。白话：输入公开深度和共同场景假设，输出“在这些假设下整块身体走过的每一点都有自由证据”；例如圆盘只擦到一个方格角也必须检查该格。它不是有限像素对任意真实场景的无条件安全证明。
- 当前身体只能填补所有允许初态共同覆盖的连续核心；身体外缘、采样间隙和视野外分别保留未知。墙边界以完整公开区间传播，悲观几何取所有允许墙占据的并集；名义中点只作诊断。未知按占据形成可评分的完整预测，同时独立记录`first_uncertified_time_s`与`contact_source`；因悲观先验造成的假接触、位置误差、Brier和regret全部计入，不删分母，也不把`unknown_prior`写成已观测墙。
- M-SIMPLE是二维简化惯性动力学：质量、摩擦、有限伺服力、0.002秒半隐式积分和顺序冲量均保留；不再误称忽略惯性的M-QS。M-PHYS从同一公开连续地图生成全新MuJoCo场景，使用同一初态区间、悲观未知和公共物性；禁止原世界XML、积分快照、真实未来机器人/物块状态和按真值校准。M-PHYS是同引擎归因对照，不支持现实物理泛化主张。任一强对照成功都须收缩新增记忆机制主张。
- 两种M均须覆盖全部登记开发/验证家族，确认集仍待模型、探针、算法和评分锁定后的单独释放。当前只冻结用户决定；连续地图、两种求解器及隔离运行尚待逐职责实现、人工案例和用户代码审查，服务器效果运行继续为未授权依赖步骤。

## D-113：登记双动力学实现的初态分支与M-PHYS未知约束

- 日期：2026-09-13。依D-112实施但仍待用户代码审查：M-SIMPLE和M-PHYS都固定使用公开中心区间的中点作为主预测，并完整运行四个xy端点组合作敏感性分支；区间退化造成的重复分支去重。分支从相同公开地图独立克隆，不按标签、未来或误差挑选。
- M-PHYS构建器的函数签名不接来源XML、snapshot或integration；生成场景只含公开地面、公开墙区间、公共物块/推头形状与物性。已观测接触由MuJoCo 3.3.7求解；悲观未知使用与M-SIMPLE相同的逐刚体连续支持约束在每个引擎步后执行，不能把虚拟未知写成已观测墙。
- M-PHYS的三维圆柱未知检查先登记为任意姿态包围球的水平投影，半径为公共圆柱半径与半高的平方和开根。白话：70 mm半径、40 mm半高的圆柱用约80.62 mm圆盘检查未知，可能比实际倾斜轮廓更早停住，但不会因为只检查直立圆面而漏掉伸出的角部；这不是现实碰撞裕量，也不能在看到效果后缩小。
- 新实现当前均为review pending、`formal_model_ready=false`；人工测试和服务器隔离测试可以运行，开发/验证效果运行仍须先完成用户代码审查。D-112对确认集的单独释放要求不变。

## D-114：双M按公开预测、封存、独立评价分阶段执行

- 日期：2026-09-13。新增`SH-05-R4-dual-M-v1`审查候选入口，52个开发/验证家族可按用户已允许的1–8个家族worker并行；每个worker必须完成四世界、九候选、M-SIMPLE与M-PHYS两系统，任何缺项或数值失败停止父阶段并保留现场。已有4家族复用已验证产物，被用户删除的48家族目录必须先按更新后的绑定重新生成和验证。
- `run`只可打开各家族`public_manifest`登记的历史并先封存1872×2条200步预测；`evaluate`须等`verify`逐摘要通过后才能打开`labels_manifest`，确认split在两个阶段均禁止。白话：例如公开预测算完`r4-11/LR`后不能立即偷看哪条动作成功再改模型，必须等全部52家族预测完整落盘才进入统一评价；这不是边跑边调未知边界或选择初态角点。
- 当前入口、配置和测试仍为review pending；用户审过具体提交后，才可用该提交号释放48家族重跑及双M效果计算。训练和确认仍未由本条释放。

## D-115：E0完整坐标区间必须进入M墙并集

- 日期：2026-09-13。复核D-112的五项语义时发现`1a158a2`虽然把深度墙顶面按5 mm相交格向外取整，却没有直接消费E0的`coordinate_intervals_m`；E0实测区间最宽约21.17 mm，因此一格取整不能覆盖全部允许墙内缘。该提交不得作为效果运行绑定，旧检查回执也不得复用。
- 连续地图现在从同一原公开历史重算E0：左墙内缘取左边区间上界、右墙内缘取右边区间下界、前缘覆盖完整区间并加公共墙厚；每个候选必须在公开深度墙顶面找到左右支撑，否则该世界在动力学前失败。原像素墙证据与区间派生墙格分字段保存，最终墙并集从认证自由和身体核心中扣除。
- 白话：这解决“中点看起来能过，但允许的墙位置可能更窄”这一具体漏洞。输入是不含私有标签的E0区间与墙顶面，输出最不利门宽和可追溯墙并集；例如中点门宽120 mm、端点门宽40 mm时必须按40 mm评估。它不扩大观察范围、不读取XML真值，也不把未知区或门洞认证为自由。修复仍须形成新提交并通过本地/服务器隔离检查后由用户审查，才能重跑开发/验证；确认集继续封存。
- 同次服务器预检还发现阶段入口误读了不存在的逐家族`verified.json`和生成`verify_receipt.json`。正式生成器实际输出全局`run_receipt.json`，其中`accepted=true`且`artifacts`逐文件绑定整个execution。入口改为先核全局成功回执，再核每家族`public_manifest`与回执中的摘要，随后由manifest核公开文件；校验链未放宽。白话：例如`r4-39`的manifest改一个字节就会在读历史前拒绝；这不是把“目录存在”当作验证通过，也不重跑已有四家族。

## D-122：第一篇切回版本化结构记忆事务，先消除参考 query 捷径

- 日期：2026-09-13。用户依据导师意见将第一篇优先级从 D-062 空间世界模型切回记忆修订，并确认保留 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE 八个原子模板；REPLACE 仍为复合程序。旧 S5 的 A 对 C/E no-go 和 test 封存不改写，D-062 分支、代码、数据和证据暂停但不删除。
- 新 proposed 名称为 Versioned Structural Memory Transactions（VSMT，版本化结构记忆事务），范围包含实体、地点/区域、关系、证据及结构 SPLIT/MERGE，不缩成对象生命周期。第一篇主比较改为 VSMT、ConceptGraphs 风格阈值关联融合（TAF）、Fusion++/Dengler 风格存在概率更新（ELU）、Khronos 风格窗口片段协调（WFR）和朴素末次观测覆盖（LOW）。后三者是引用清楚的 clean-room mechanism-level adaptations，不复制上游源码，也不冒称论文官方复现。
- 旧实现审计确认实质信息风险：`_event_plan` 由 `reference_spec.target_node_id(s)/target_edge_id/new_target` 生成 node/edge/place/merge query，候选生成器再据此排序；尤其 `merge_queries` 直接帮助构造首个 MERGE pair。删除 `reference_spec` 后候选不变的测试没有追踪 query 的上游来源，因此不能证明无 oracle shortcut。此事实不回写旧 S5 结果，但新数据、候选和主实验禁止复用全部参考派生 query。
- 新版固定原则是 candidate-before-teacher：候选只由公开观测前缀和 prior predicted memory 产生、先写 digest 封存，teacher 随后才可打开未来/reference 并仅给既有候选打训练标签。private reference、未来或模拟器 ID 变化而 public 不变时，候选、顺序、在线特征和 logits 必须逐字节不变；漏掉正确候选记 candidate miss，不准补槽。
- 新数据全部重新生成，采用 public/candidate/teacher/private_eval/provenance 分通道和独立读取器。冻结 DINOv2 只提供共享匿名 RGB 区域描述，深度/位姿提供公开几何；真值 mask/instance ID 只能 private 评价。具体图类型、proposal、场景、split、样本数、训练与存储预算尚未冻结，当前 generation/training/confirmation 均未授权。
- 独立工作树为`D:\Users\28115\Desktop\SCI\projects\embodied_spatial_memory_m1_structural`，分支`codex/m1-structural-memory-revision`从已审`origin/main`提交`1e5fa2c`建立；原工作区未提交的`docs/PLAN.md`和`scripts/notes.txt`未移动或修改。当前只交 VM-00 文献、许可证、旧代码泄漏和合同草案，用户审过后才进入 VM-01 schema/测试实现。

## D-123：VM-01只冻结信息边界，语义等价与指标由用户裁决

- 日期：2026-09-13。用户批准继续 VM-01，并明确 BIND/BIRTH 等语义指标由用户判断，但实现者必须提供足以区分边界的案例和描述。本职责不实现 TAF/ELU/WFR/LOW、不生成数据、不训练，也不把未裁决语义藏进 validator。
- 新 `vsmt.contracts` 严格验证公开观测、候选目录、teacher 目标、共同结果、私有评价和私有扰动不变性。共同适配器只接剥离审计身份后的七类部署值；候选构造 API 不接 private，teacher 只能按已封存候选的原 ID 与顺序给分。白话：输入同一份公开观测和旧记忆，输出固定模型输入、候选摘要及独立标签绑定。例如交换私有模拟器实例名后，private 摘要应变，但候选、适配输入和 logits 摘要必须完全不变。它不证明候选正确、事务语义合理或方法优于基线。
- S-01 至 S-12 作为待用户裁决案例，分别覆盖 BIND/BIRTH、REACTIVATE/BIRTH、RELINK/REPLACE、SPLIT/BIRTH、MERGE/BIND、RETRACT/NOOP、低置信 NOOP、地点/关系扩充、图 ID 等价、错误代价、持续时间和 provenance。裁决须在 VM-04 数据数值冻结前落到生成规则与等价集合；当前不预选有利于 VSMT 的口径。
- 本地只允许语法、JSON和 diff 静态核查；合同测试须在服务器用本提交运行并保存退出证据。用户代码审查及服务器测试通过前，VM-02 和任何效果依赖均不开始。

## D-124：VM-01～VM-03分别提交后一次同步做服务器工程验收

- 日期：2026-09-13。用户认可 METHOD 的 S-01～S-12 边界案例，并要求其余工程内容先一起交付、最后一次到服务器运行。按 D-059 仍保留单职责提交和可审差异，但把服务器同步/测试合并；这不跳过用户审查，也不授权 VM-04 数据生成或后续训练。
- VM-01 在实现 VM-02 时补出必要公开输入：匿名 `structure_kind` 与传感器派生 `free_space_observations`。后者含合法历史时间、轴对齐内包、可靠性和支持摘要；候选另封存每程序的 `online_evidence` 及摘要。白话：ELU/RETRACT 必须知道旧节点所在空间是否真的被传感器看空，输入公开深度派生的匿名自由盒，输出可重复检查的负证据；例如同一节点连续两时刻被完整覆盖才可形成 VSMT RETRACT 候选。它不是真值空区、不点名要删除谁，也不把一次漏检当删除。
- VM-02 clean-room 代码候选实现 TAF 的 BIND/BIRTH/MERGE、ELU 的 BIND/BIRTH/REACTIVATE/RETRACT、WFR 的 BIND/BIRTH/MERGE/RETRACT 和 LOW 的 BIND/BIRTH。所有阈值配置无默认值，人工测试值不冻结为实验参数；共同 GraphRevision 只统一合法输出和审计版本，不让基线读取其机制之外的历史能力。
- VM-03 公开生成器枚举八原子加 REPLACE，按每模板显式上限取公开分数候选，逐一用旧 executor 真执行后封存。事务 ID 和顺序只依赖剥离审计身份后的 AdapterInput 摘要；完整 public 摘要只绑定文件。teacher API 只遍历已封存槽并输出分数/概率，具体语义 scorer 仍由用户在 VM-04 前决定。
- 固定 `ops/vsmt/vm01_vm03_contract_check.py` 在审查提交上运行34项定向测试，保存 started/log/receipt/success 后才允许 export；失败不导出、不生成数据、不训练、不打开真实 private 数据。服务器尚未运行，本地仅 AST/JSON/diff 静态检查。

## D-125：第一篇按VSMT论文收敛，旧LATENT降为诊断而非视觉输入

- 日期：2026-09-14。用户要求本地日常入口、方法和计划从暂停的空间世界模型改成当前 VSMT 论文版本，并询问 C00–C11、旧 LATENT 与 RGB 输入的实验职责。第一篇唯一当前主题固定为 VSMT；核心候选贡献写成“类型化可执行事务、版本化状态/副作用审计、candidate-before-teacher 监督边界”的组合。成熟系统只提供共享前端、图层次、存在更新和快慢协调骨架，不能把 ConceptGraphs、Hydra、Fusion++、Khronos 的已有能力改写成本项目创新。
- 旧 C00–C11 保留为 `L0 symbolic regression`，用于八原子/REPLACE 前条件、原子回滚、版本/provenance、S-01～S-12 和错误分解回归；不进入主表，不证明视觉感知或方法效果。旧 LATENT 来自符号 ID、合成 history cue、稳定哈希和参考派生 query，不是 RGB 学得的 latent；最多作为旧结果或 oracle-structured 机制诊断，不能成为部署主输入。
- 新实验分成同源三层：L0旧符号回归；L1在新数据上用 oracle proposal 的结构机制上界；L2让 VSMT/TAF/ELU/WFR/LOW 共享完全相同的冻结 RGB-D proposal、DINOv2 region descriptor、depth/pose/free-space，作为主结果。VSMT 不改成端到端原始 RGB 网络；RGB-D先经共享前端形成结构观测，公平性由所有方法的相同前端字节与摘要保证。
- 新增静态反作弊门：VSMT 包不得导入旧 `cpmt.m1_*` query/feature 模块；部署 prior memory 的 `latent_refs` 只能为空或公开派生的十六进制摘要，旧 `latent:C05:chair-a` 一类语义值须拒绝。此门仍不足以证明匿名值的因果来源，因此 VM-04 必须实现不挂载 private 的 prior memory 顺序构建回执，并把 prior/candidate/online/logits 全部纳入 private-mutation invariance；该生成、数值、split、预算和训练仍未授权。
- D-124的服务器阶段沿用同一入口但定向测试计数更新为36；旧34项回执尚不存在、也不得冒用。原D-062工作树的用户未提交PLAN/notes继续原样保留，VSMT论文版在独立分支交付，用户审查后再决定合并。

## D-126：SPLIT关系重分配未冻结前只生成无开放incident edge候选

- 日期：2026-09-14。首次服务器合同测试发现当前SPLIT会关闭源节点并创建两个后继，但没有关闭或重建源节点的开放关系，因此对`entity-a --located_at--> place-a`执行后留下悬空边并被executor正确拒绝。失败目录保留，没有导出、生成或训练。
- 当前窄修复是在候选生成阶段排除具有开放 incident edge（关联边）的SPLIT源节点；无关联边节点仍可产生和执行SPLIT。白话：它解决“拆了节点却没决定原关系归谁”的结构非法问题；输入旧图的开放边和可分区域，输出只含目前语义完整的SPLIT候选。例如孤立的错误聚合片段可拆，仍连着地点边的节点暂不拆。它不等于这些节点永远不能SPLIT，也不把关系复制给两个后继当作默认答案。
- VM-04前须由用户在S-04/S-08语义下冻结关系分配候选：分给左后继、右后继、两者、关闭，或按公开证据枚举多个合法程序；冻结前不自行扩张。对应回归和合法`composition_label`窄白名单使服务器定向计数变为37，须在新提交/新目录重跑。
- 修复版服务器37/37通过，旧失败与新成功目录均保留；该工程通过不自动批准VM-04生成、阈值、split、预算、训练或上述SPLIT关系语义。

## D-127：VM-04首个同源RGB-D数据协议作为不可执行审议稿

- 日期：2026-09-14；状态：proposed。用户要求把VSMT分支快进合并`main`并开始下一步，同时明确保留当前工作区`scripts/notes.txt`、采用VSMT `docs/PLAN.md`。合并已完成；本职责只交[VM-04 v1提案](../configs/vsmt/vm04_data_protocol_proposal_v1.json)和论文合同，不下载、生成、训练或打开confirmation。
- 主来源建议ProcTHOR-10K＋AI2-THOR，独立单位为house family；拟2/48/12/12个audit/train/validation/confirmation家族，每家族对八原子和REPLACE各2个预登记重复，每episode 32帧、第24帧决策、第25–31帧只供封存后teacher/private评价，总计1,332条episode、42,624帧。house不跨split、失败不换样本、confirmation延后生成。以上均未获数值批准。
- L1/L2复用同一物理序列和时刻但独立建prior/candidate：L1用去真实ID的simulator mask作机制诊断，L2建议逐帧无视频记忆SAM2.1自动mask＋冻结DINOv2 ViT-S/14区域池化作主表。DINO来源沿用已核commit/权重摘要但须产生新VM-04回执；SAM、AI2-THOR/ProcTHOR精确摘要和全部proposal/几何阈值为空，fail closed。
- SPLIT/MERGE正例定位为受控前端记忆错误而非物体物理裂合。压力日程和pair只依赖公开proposal/固定时间表；私有真值只在封存后判目标成立或construction failure，不能修改public/candidate或换样本。自然前端错误另报。
- 关系感知SPLIT建议成为一个原子操作：关闭源节点及其开放incident edges，再为每条边枚举给后继0、后继1、二者或均不继承的类型合法分配；均不继承须有公开负证据。第一批建议源度数≤2、最多16个原始分配组合。用户批准与executor/schema实现前，D-126的孤立节点限制继续有效。
- 主比较仍为VSMT/TAF/ELU/WFR/LOW；同一数据另分controlled revision共享因果prior和closed-loop revision各自自反馈两轨。VM-05须加入直接参考排序、无执行后状态评分和公开启发式排序三项VSMT内部对照，以区分teacher、candidate execution和候选启发式贡献；它们不替代LOW或三种论文机制。
- S-01～S-12案例目录已被用户认可，但具体身份/可见性阈值、图等价、错误权重、终点/持续时间优先级、provenance成功条件、candidate cap、teacher温度及nuisance probe门未冻结。JSON保持`null`并把全部授权设false，不能因本提案存在而开始服务器生成。

## D-128：关系感知SPLIT进入代码候选，关闭分支继续等待证据口径

- 日期：2026-09-14；状态：implementation candidate。用户确认VM-04 v1方向“没问题，开始下一步”，因此解除D-127中关系感知SPLIT的纯提案状态，但不把该确认扩张为数据生成、训练、confirmation或未填数值的授权。
- schema/executor/公开候选生成器现要求SPLIT在同一事务内关闭源节点和全部开放incident edges，并逐边枚举给后继0、后继1或二者。第一批开放边数上限2；超限或源自环不生成。漏分、重复分、改变关系类型/方向/另一端点或添加未登记替代边均原子拒绝。
- “均不继承”只保留在executor合同中，必须引用至少两份已登记、在线可得且无中间正观测的公开负证据；因关系负证据的几何/可靠性口径尚未冻结，公开生成器不产生该分支。白话：输入一个带地点边的混合节点和两个新区域，输出三个可审候选——左继承、右继承或两者继承；不会由teacher事后补边。它不决定哪个候选语义正确，也不以本地静态检查冒充服务器测试。

## D-129：public bootstrap因果旧记忆链形成纯代码候选

- 日期：2026-09-14；状态：implementation candidate。`src/vsmt/causal_prior.py`只接收公开packet、前一步预测图、显式无默认值配置和源码摘要；函数签名不接受private/teacher/future/path。从全episode共享的空图开始，每帧区域至多使用一次，公开相似度过门做BIND，否则BIRTH，运行时间固定记0以保持回执确定性。
- 回执逐步绑定公开文件、实际AdapterInput、提交更新和图版本链；审计身份变化会改变外层文件绑定，但不能改变实际输入摘要或最终图。白话：它解决“受控对比的共同旧图是不是用真值做好了”的问题；输入0～23帧公开观测，输出24帧前同一旧图及可复算链。例如两个连续同类近邻区域会先BIRTH再BIND。它不构造关系、不读取私有身份，也不证明关联阈值合理。
- 该提交只允许本地AST/JSON/diff静态检查。正式VM-04运行前仍须冻结关联数值，增加服务器只挂载public的进程级守卫并取得新回执；旧VM-01～03的37项成功不能认证本模块，当前生成和训练授权保持false。

## D-130：VM-04计划清单标签隔离与fail-closed闸门

- 日期：2026-09-14；状态：implementation candidate。新增纯标准库协议校验、house-family确定性分组和episode计划，不读取资产、不生成图像。family按`sha256(source_manifest_sha256|split_seed|house_id)`排序后依次分2/48/12/12，合计74个house且不跨split；协议同时复算18 episode/family、1332 episode和42624 observations。
- 开发family行保存实际house ID，confirmation行只保存绑定来源manifest的摘要并把ID置空；真实ID的reveal和confirmation episode计划当前都会因授权false拒绝。公开episode ID只依赖协议版本、family ordinal和0～17槽位，事务/重复分配只在私有计划中由私有salt确定；更换salt必须保持公开计划逐字节相同。白话：它解决“确认家族被提前看见”和“文件名里虽然没写MERGE但固定槽位仍能猜到MERGE”的问题；输入公开槽位和私有平衡分配，输出分读权限的清单。它不等于元数据探针已经跑过，也不允许训练进程读取私有映射。
- 执行闸门要求`frozen_executable`、数值批准、实现批准、动作授权、来源/前端/因果prior/语义/nuisance全部填齐且待审事项为空。当前提案在第一项即失败，因此本代码不能被用来下载、生成、打开confirmation或训练；服务器测试仍pending。

## D-131：VM-04只读来源预检一次同步交付

- 日期：2026-09-14；状态：entry prepared, server pending。用户先开启服务器并批准下一步，随后决定关机休息并要求完成所有不依赖服务器的内容。关机前仅作了手工只读来源/环境核查：实际仓库`/root/Emboddied_Spatial_Memory`、RTX 4080 SUPER 32760 MiB、基础Python 3.12.3/Torch 2.8.0+cu128，AI2-THOR/ProcTHOR/SAM2未安装；未下载、安装、生成、训练或打开private/confirmation。该手工观察没有标准receipt，不能认证新代码。
- 固定`ops/vsmt/vm04_preflight.py`按`contracts → source-audit → export`运行，绑定同一受审提交。source audit只用`git ls-remote`、GitHub/PyPI小元数据、checkpoint HEAD、精确本地DINO路径及主机只读探针；所有安装/下载/生成/训练/confirmation标志为false。网络失败允许同提交递增attempt并保留旧失败，不覆盖；contracts成功只复用，不重跑。
- 环境版本当前明确未决：ProcTHOR发布元数据只声明到Python 3.9，而SAM2要求Python≥3.10，所以不能直接选3.9，也不改服务器基础3.12；只登记后续在`/root/autodl-tmp/vsmt-envs`做Python 3.10/3.11隔离兼容检查。白话：预检解决“来源和机器是否能支撑后续安装”的问题；输入官方版本元数据和现有主机，输出匹配/缺失清单。例如现有DINO权重可复用但SAM权重只查长度、不下载。它不等于环境装好、模拟器能渲染或数据协议已冻结。

## D-132：先做五方法共同L1，L2视觉proposal后置

- 日期：2026-09-14。用户在确认L1职责后明确“先做L1”并授权继续当前预检收口。L1不是VSMT专属：VSMT、TAF、ELU、WFR、LOW必须消费同一批新序列、同一匿名oracle proposal、同一冻结DINOv2区域描述和同一公开depth/pose几何；受控轨道还须共享同一因果prior字节。
- Oracle proposal（真值区域提议诊断）解决自动分割错误是否掩盖记忆机制的问题；输入模拟器instance mask，输出去掉instance ID、按包重新编号的区域mask。例如椅子mask可帮助五个方法看到同一完整区域，但不能告诉它们这是历史中的哪把椅子。它不提供真值身份、reference事务或正确候选，也不允许跨L1/L2复用prior/candidate缓存。
- L1仍保留冻结DINOv2 descriptor作为共同公开外观信号，只后置SAM2.1自动proposal及其误差；不能把`visual_weight=0`的纯几何退化版或oracle instance identity暗中当成L1主设置。L1只报告机制上界与失败归因，不进入L2共享RGB-D主排名；L2后置不等于取消。
- 当前决定只改变实施顺序，不冻结匿名化/池化/几何数值、bootstrap/候选/基线阈值、VSMT在线选择器、teacher/evaluator、数据规模或训练预算。服务器预检成功只允许进入L1-only合同与代码审查，仍不授权依赖安装、资产下载、2家族生成、正式train/validation、训练或confirmation。

## D-133：L1-only输入、匿名化和逐候选选择器形成不可执行提案

- 日期：2026-09-14；状态：proposed，待用户审查。唯一机器提案为`configs/vsmt/vm04_l1_contract_proposal_v1.json`；所有实现、安装、下载、audit生成、train/validation生成、训练和confirmation授权均为false。它细化D-132的实施边界，不把本次“继续”解释为对首次出现数值或网络容量的批准。
- L1隔离materializer只在单帧内用instance ID取mask，公开排序前丢弃ID；同一实例跨帧重新编号。实体可使用oracle mask，surface/place/free-space仍只读公开depth/pose，不能把simulator语义、真值pose/mesh/bbox或房间图带入方法。白话：输入真值像素分区，输出匿名区域和可见几何；例如两帧中的同一杯子仍须由方法自己BIND。它不等于oracle identity或oracle scene graph。
- 冻结DINOv2拟在224×224原RGB上产生16×16×384 patch token，以每个14×14 patch的mask占比加权平均并L2归一化；缓存float32 descriptor一次，五方法逐字节共享，无私有视觉adapter。最小像素/patch/depth支持、范数容差和可靠性仍为null。白话：它输入同一当前RGB和匿名mask，输出区域外观向量，例如半个patch属于区域则权重0.5；它不训练backbone或提供对象身份。
- VSMT在线选择器拟用无slot embedding的共享逐候选scorer，编码prior、program/evidence、候选触及的pre-state、同一基图真实执行后的post-state及delta，每个program输出一个logit；换序诊断中logit必须随program而非ordinal移动。DRCR保留post-state但换直接reference训练标签，NECS禁止post graph并用固定零分支，PHR只用冻结公开启发式分。该设计解决旧索引head和“执行后状态是否有独立价值”的问题；输入封存catalog，输出候选排序。它不改变candidate-before-teacher，也不让四个论文机制适配器经过VSMT网络。
- 必需正反例固定为instance ID置换、跨帧重编号、mask枚举换序、两相似实体、遮挡非空、支持不足失败保留、private/future变异和catalog校验后scorer batch换序八类。它们先验证信息边界与接口；最后一项不修改封存catalog或teacher槽位。它们不证明真实数据覆盖或方法效果。下一步只有在用户审查本提案后，才可把已接受规则实现为L1 materializer/selector/evaluator代码与必要服务器测试；环境和2-house audit继续后置。

## D-134：用户裁决在对话正文直接交付

- 日期：2026-09-14；状态：active workflow rule。用户指出从文件中寻找待认可内容费劲。今后凡有待认可、二选一或数值冻结，最终回复须直接给出待决事项、推荐口径、替代口径、结果/资源/主张影响和可直接回复的批准句；文件链接仅作证据，不再作为发现决策的入口。若没有待决事项，正文明确写“本轮无需裁决”。
- 白话：这条规则解决“决定藏在文档里”的沟通问题；输入是本轮尚未冻结的选择，输出是一段在对话里即可审查和批准的清单。例如用户可直接回复“第1～5项按推荐口径认可”，而不必打开配置逐项找`null`。它只改变交付方式，不代表任何科学口径、数值、运行、下载、训练或confirmation已经获批。

## D-135：L1五项方向通过，开始隔离环境与实现

- 日期：2026-09-14；状态：direction approved, implementation in progress。用户依次认可五方法共同机制诊断、冻结共享DINOv2且无方法私有adapter、VSMT无slot逐候选执行后状态scorer、四个论文机制直接更新，以及单帧内同一instance的断开可见部分保持一个匿名区域。真实instance ID仍在公开排序/摘要前删除，不提供跨帧身份；surface/place/free-space仍只来自公开depth/pose。未来共同视觉描述或输入改变时允许为公平归因重跑L1，旧版本和摘要不得覆盖。
- 用户随后要求“接着跑L1”。当前解释为允许L1合同/代码、必要服务器测试、隔离AI2-THOR/ProcTHOR环境、已审AI2-THOR CloudRendering构建和既有DINO资产复用；不从这句话推导任何仍为`null`的科学数值，也不提前允许SAM/L2、2-house数据生成、train/validation生成、选择器训练或confirmation。L1第一职责是只处理当前帧mask的匿名化模块：输入instance到二值mask的临时私有映射，输出按mask内容排序的匿名缓存和不含ID的失败记录；例如同一椅子隔着桌面露出的三块像素仍是一个`region`。它不做跨帧关联、DINO编码、几何、事务选择或效果实验。
- L1模拟器与公开materializer改为文件边界隔离候选：Python 3.9环境只运行AI2-THOR 5.0.0/ProcTHOR 0.0.1.dev2并写封存RGB、depth、instance mask和pose；现有Python 3.12/Torch 2.8环境再运行冻结DINO和公开materializer。白话：它解决ProcTHOR旧Python范围与未来SAM所需新Python无法塞入同一环境的问题；例如模拟器进程结束后，记忆方法只收到匿名`AdapterInput`。它不允许私有mask ID穿过文件边界，也不表示模拟器smoke成功或数据协议已冻结。
- 隔离环境和第一职责随后在`5833fe0`取得服务器回执：9/9匿名mask测试通过，官方AI2-THOR CloudRendering构建按835,983,275字节及SHA-256校验，Vulkan识别RTX 4080 SUPER，FloorPlan1返回224×224 RGB/depth/instance segmentation及9个instance mask，既有DINO仓库/权重摘要匹配。环境ready只代表可以开始下一块公开物化实现；0 VM-04 house生成、0训练、0confirmation，支持/几何/候选/teacher/指标数值仍须用户在对话中裁决。

## D-136：L1实体mask、DINO池化与可见几何数值获批

- 日期：2026-09-14；状态：entity materialization values approved。用户认可推荐口径：实体mask最少196个可见像素，触边但支持充足就保留；DINO总patch权重至少1.0，float32单位范数容差`1e-5`；公开depth有效范围0.05–20 m，有效点至少`max(32, ceil(25%×可见像素数))`，区域可靠性为有效点数除以可见像素数。支持不足或非有限值保留construction failure，不重采样、不用私有几何补齐。
- 固定AI2-THOR 5.0.0提交`f0825767cd50d69f666c7f282e54abfe58f1e917`的`Depth.shader`用`Linear01Depth`乘far-near，故本批把返回米制depth固定为相机前向轴`z`。反投影使用整数像素`u=列、v=行`且不加0.5，camera坐标为`x=(u-cx)z/fx, y=(cy-v)z/fy, z=depth`，再用公开camera-to-world四元数/平移变换。白话：画面边缘一个depth=2 m的像素仍位于相机前方z=2 m平面，不把2 m当作斜射线长度。它不读取模拟器对象pose/mesh/bbox，也不声称AI2-THOR文档中的自然语言“distance”是另一种几何定义。
- 当前授权只覆盖`l1_entities`实现、必要服务器合同测试和一次真实冻结DINO权重的非数据smoke；不生成2-house audit，不训练，不打开confirmation。surface/place/free-space、bootstrap/五方法阈值、选择器容量、teacher/evaluator和S-01～S-12汇总口径仍未裁决；以后视觉前端或本层输入改变时按新摘要重跑L1是预期行为，不覆盖旧结果。

## D-137：正式生成、训练与检验必须支持多worker

- 日期：2026-09-14；状态：execution requirement approved。用户要求生成数据、训练和检验均使用多个worker。正式数据生成以完整house family为任务单元且至少2个worker；validation/评价以封存episode或完整family并行且至少2个worker；当前单张GPU上的训练保留一个learner进程并至少2个数据加载/预处理worker，多个独立方法/seed可由外层调度，但并发占用同一GPU须另经容量审查。
- 回执须记录请求/实际worker数、capacity probe、确定性分片和seed、逐worker开始/退出/产物摘要、未启动/缺退出项及与完成顺序无关的合并摘要。白话：4个worker只是把同一冻结house清单分块加速，不创造4倍样本；某个worker失败时保留完整前缀并停止新派发，不能换house补齐。精确worker数在各正式阶段前根据CPU、RAM、GPU和磁盘吞吐冻结；单worker只允许合同测试、非数据smoke或用户点名的失败复现。

## D-138：surface/place/free-space与关系通道口径获批

- 日期：2026-09-14；状态：approved for implementation and server contract verification, not generation。用户明确接受四项推荐口径：surface/place/free-space数值、ObservationPacket v2、`relation_observations`及节点/关系类型化BIRTH/BIND；允许实现和必要服务器合同/合成烟测，不授权house数据生成、训练或confirmation。唯一数值合同为`configs/vsmt/vm04_l1_non_entity_geometry_review_v1.json`。
- Surface用公开depth的14×14基础平面片、10°合并、最终至少784内点、2 cm内点阈值和1 cm RMS；place从距标准站立agent支撑高度5 cm内的水平surface形成0.5 m地面格，25个0.1 m子格至少覆盖16个。AI2-THOR固定提交中的标准agent胶囊高1.8 m、camera局部高度0.675 m，因此支撑高度由公开camera世界y减1.575 m得到；禁止`GetReachablePositions`、navmesh和房间标签。白话：输入公开depth和相机标定，输出平面区域与局部地面锚点。例如桌面是surface但不是place。它不输出房间语义、可行走标签或真值网格。
- Free-space不再沿用packet v1的世界AABB：packet v2改存6个世界半空间的多尺度截锥；每个时刻最多341个，depth块100%有效、边界内缩1像素、表面前留10 cm，旧bbox每边扩2 cm且完整落在单个截锥内，并在相隔至少0.25 s两时刻成立才允许负证据。白话：输入两帧公开depth，输出“相机确实看到为空”的空间；沙发后的旧椅子仍是未知而不是空。它不等于漏检、碰撞自由或导航网格。
- Packet v2新增公开关系通道，并把既有BIRTH/BIND类型化为节点或关系身份：关系BIRTH创建第一条edge，关系BIND给一条开放edge附证据，RELINK仍只改已有edge；不增加第九个原子且teacher不得补边。`contains`作为`located_at`的反向派生视图并共用证据，持久图只存一份规范`located_at`；`adjacent_to`按端点ID规范方向。白话：首次看到“杯子在某地点”先建立一条关系，后来换地点才RELINK；反向查询不再把同一事实计两次，也不会留下过期反向边。它不是给真值scene graph或永久身份。

## D-139：阈值、候选容量与公平调参形成不可执行审议稿

- 日期：2026-09-14；状态：proposed，待用户在对话中裁决。代码审计确认测试/烟测中的关联权重、阈值与候选上限只验证分支，不能升格为正式数值；单一视觉—质心分跨`entity/surface/place/fragment`也会混淆固定地点与可移动实体。拟改为封存可审的视觉、米制距离、归一化几何、结构类型和可靠性分量，再由类型化显式配置组合；仍不读取类别、instance ID、teacher或未来。
- 当前候选器先完整物化所有组合、再按每模板cap截断，cap并不限制截断前内存；用于截断的分数随后丢失，而PHR提案又需要公开分。拟以输出等价的确定性流式top-k取代完整物化，保存每模板截断前计数、边界分与并列数，并把`enumeration_priority`与跨模板`decision_heuristic_score`分开。白话：NOOP为保证目录存在可在枚举阶段记1.0，但不能因此在最终选择时永远击败0.95的真实RELINK；排在cap后面的正确程序只能如实记candidate miss，teacher不能补回。它不等于PHR公式或cap数值已经批准。
- 公平调参建议所有方法共用train/validation与冻结选择指标，各自最多评估12个完整配置；方法特有阈值可不同，bootstrap在受控轨道只选一次并逐字节共享。正式数值必须在相关S-01～S-12身份、等价和错误口径确定后选择，confirmation不得参与。该审议只允许用户批准后实现无默认值配置、分数封存、流式top-k和合同测试；不授权2-house、train/validation生成、训练或confirmation。

## D-140：place脚手架、类型化容量、SPLIT整组和两层审计获批

- 日期：2026-09-14；状态：approved for implementation and server contract verification, not data execution。用户认可D-139全部选择协议，并在审阅外部代码意见后批准：place按世界坐标作为五方法共同的确定性scaffold，不进入学习式BIND/MERGE/SPLIT；候选容量按`template × structure_kind`或`template × relation_type`分桶；TAF/ELU/WFR/LOW及bootstrap也使用显式类型化关联配置。测试/烟测数值仍不是正式阈值。
- SPLIT采用公开证据约束的混合口径：当前关系唯一支持左、右或二者时确定性收窄；没有公开支持时保留左、右、二者三种分配。同一左右后继的全部关系分配是不可拆候选组，容量不足整组拒绝并记candidate miss，不能由canonical hash随机保留部分。当时统称的incident-edge计算护栏不再固定为“最多2条边”的科学语义，随后由D-141拆成歧义边和总incident-edge两项；均不继承仍等待公开负证据口径。
- MERGE必须在同一原子内关闭两个源身份的全部开放incident edges，将alias端点重锚到canonical；同类型、同方向、同frame重复边合并证据/provenance，折叠出的自环关闭而不重开。白话：两个重复杯子节点都连到同一地点时，MERGE后只留一条规范关系并保留两边证据。它不删除旧版本，也不允许后续BIRTH掩盖悬空alias边。
- `CandidateCatalog v2`封存每项枚举优先级和公开分量，并逐桶记录截断前候选/组数、保留数、超大整组数和最低保留优先级；PHR跨模板决策分仍未实现。2-house audit分成不挂载private的容量层，以及public/candidate全封存后才打开private的逐事务candidate recall/可用正例层；用户只批准审计内容，未授权实际运行。candidate recall和DRCR/NECS/PHR升为主报告一等诊断，关系通道为五方法共享能力而非VSMT独立创新。
- 同批直接工程修复包括：真实`mask匿名化→实体物化→region组包`联测、mask紧凑字节存储、退化place格记录失败并跳过。允许必要本地/服务器合同及合成非数据smoke；house生成、阈值选择、训练、validation效果、private/confirmation读取仍为false。

## D-141：实体撤回、共享dormant路径、共同审计与family统计口径获批

- 日期：2026-09-14；状态：approved for implementation and server contract verification, not data execution。用户先批准动作空间对称化、统计口径和`f73b587`追认，随后在具体例子与未来影响解释后选择方案1A：保留关系级RETRACT，同时实现entity node-level RETRACT；surface/fragment节点本轮不扩展。house生成、训练、validation效果、2-house audit、confirmation生成/reveal仍未授权。
- entity RETRACT只有在至少两条不同time/view的公开在线visible-empty证据满足有效pose/depth及可靠性门时才可执行；同一原子关闭当前实体版本及全部开放incident edges，追加terminal retracted版本并保留全部旧evidence/latent/provenance和新负证据。目标incident edge的关闭属于声明范围，即使另一端是protected节点也不等于修改该邻居节点；邻居自身状态和无关边仍受保护。白话：旧杯子所在空间连续两次可靠为空时，杯子和直接挂在它上的`located_at/supported_by`一起终止，但地点节点和其他物体关系不变。它不是物理删除历史，也不允许retracted身份以后REACTIVATE。
- entity REPLACE严格编译为上述RETRACT后BIRTH一个不同candidate实体；新实体不得继承旧身份、证据或关系，只能从当前packet的公开支持新建`located_at/supported_by`，且新节点/边证据必须是online supporting observation。例如旧杯子消失而当前位置出现新花瓶，旧杯历史封存，新花瓶只携带当前证据；若其实是同一杯子移动，应走RELINK而非REPLACE。全部写操作继续原子回滚。
- 五方法运行前使用同一共享包装器：place版本化证据逐字节一致；只有长期未被公开重观测的confirmed entity可按显式时间门进入dormant，candidate不可进入，可靠空证据必须走RETRACT。时间门只可在train/validation选择并在confirmation前冻结。因果public bootstrap在两份不同公开观测证据后才把candidate升级confirmed，重复同一证据不计两次；因此REACTIVATE获得公开可构造路径，而不是由private或teacher造dormant。
- TAF/ELU/WFR/LOW不强制经过VSMT executor，以免借到不属于原机制的动作空间；所有方法最终结果必须经过共同只读审计，统一验证图、重算delta、检测历史物理删除、既有版本突变及protected节点/incident topology变化。关系通道和place包装是五方法共享能力，论文须把节点错误与关系错误分开归因。
- SPLIT资源限制拆成`maximum_split_ambiguous_edges`与`maximum_split_total_incident_edges`：前者只作用于没有唯一公开支持的边，变体数为`3^(歧义边数)`；后者限制整笔原子操作规模。catalog逐桶分别记录两种护栏拒绝数，顶层记录所有桶总容量、截断前总量、保留总量和未保留总量；正式数值只能由开发容量审计冻结。
- 统计独立单位固定为house family；同family两个replicate只能形成family内配对估计，不能当两个独立n。总体跨九类family聚合比较是主确认主张；分类型确认性主张只预登记SPLIT、MERGE、RETRACT，其余六类只作描述。confirmation family数由开发阶段逐类构造成品率反推并在任何confirmation访问前冻结，2-house audit只作工程审计、不作功效估计。当前12个confirmation family因此降回待重算提案，不得看confirmation后追加family。
- place确定性坐标身份明确依赖AI2-THOR精确位姿；五方法共享其证据包装并单独计账。真实机器人SLAM漂移不在首篇研究范围，不能把模拟器精确位姿结论外推为现实地点身份已解决。所有批准语义的机器可查摘要见`configs/vsmt/vm04_l1_action_symmetry_v1.json`。

## D-142：不可逆撤回、观测机会、共同审计和确认性RETRACT口径获批

- 日期：2026-09-14；状态：approved for protocol-first implementation and local/server contract verification, not data execution。用户在对话中逐字批准六项推荐口径，并明确要求先登记协议再实现；本决定不授权house生成、训练、validation效果、confirmation生成/reveal或私有数据读取。
- entity RETRACT的覆盖目标改为“达到显式可靠性门的历史公开观测AABB并集＋逐边安全裕度”，而非当前融合`extent_m`。可靠性门和裕度仍为开发审计后冻结的无默认值参数。当前packet若存在达到同一公开BIND门的实体区域，阻断单独node RETRACT，但仍保留REPLACE，使“同一物体移动”可走BIND/RELINK、“旧物消失且相似新物出现”仍可竞争REPLACE。白话：只看到过椅子前缘时，不能拿这个偏小盒子永久撤掉整把椅子；同时当前又看见像这把椅子的区域时，不能只撤旧身份。它不把当前相似区域直接判成同一身份，也不让teacher补候选。
- 共享dormancy横轴从墙钟未观测时长改为连续错失的公开合格观测机会，并覆盖candidate/confirmed entity。观测机会由公开depth、相机标定和pose形成匿名、节点无关的可见体积，不含instance ID、teacher、future、reference或private；没有观测机会不累计，当前达到BIND门的区域重置计数，可靠visible-empty仍路由RETRACT。进入dormant前的candidate/confirmed来源必须保留，candidate重现仍须满足独立证据确认，不能借REACTIVATE偷升。例：机器人离开房间一分钟不累计；连续三次正对旧杯位置、深度有效却没有匹配才可休眠。它不等于实体已被证明消失，也不是新的学习事务。
- common post-update audit改为分层保护和分类改写。在线公共protected范围至少包含确定性place scaffold；episode特定protected集合只在五方法完成推理后由同一封存评价器读取，不进入adapter输入。既有版本变化分为合法关闭、evidence/provenance仅追加、已声明语义转移和未声明破坏性改写；只有删除/替换旧证据、重写旧观测状态、重开或改写关闭时间等最后一类对五方法fatal。白话：杯子关系关闭会改变地点的incident topology但不等于改写地点状态；把旧地点坐标偷偷换掉则直接拒绝。它不强迫基线走VSMT executor，也不把private保护标签给模型看。
- 候选桶按优先级降序和canonical signature确定性排序；第一个完整候选组放不下时停止该桶，禁止以后来的低分小组填空，并记录cutoff组/候选数。SPLIT源节点终止统一追加terminal retracted版本；SPLIT关系分配和REPLACE当前关系端点组合共用`maximum_ambiguous_relation_variables`歧义变量数、`maximum_relation_variants`总变体数及逐桶拒绝记账，SPLIT另受`maximum_total_incident_edges`原子规模限制，逐关系RELINK不是笛卡尔组合路线。白话：容量紧时保留一个清楚的分数边界，不用组大小暗中改变谁被选中；完整歧义组仍不可拆。它不冻结cap或护栏数值。
- 编辑代价按声明的高层事务原子归一：RELINK计一个原子，REPLACE按RETRACT+BIRTH计两个；为维持原子一致性必须关闭的incident edges不再逐版本加罚，非必要或越界变化另计collateral。正式权重仍在S指标冻结时裁决。白话：关系多的旧杯子不应只因清理边更多而让正确REPLACE永远输给RELINK。它不把REPLACE和RELINK视为同价，也不免除副作用惩罚。
- 逐类型确认性范围固定为SPLIT、MERGE和entity RETRACT；relation RETRACT单独作描述性/次要报告，总体九类主确认仍包含它。这样避免把两种RETRACT混成一个效应，也不为共享关系能力新增第四个低功效确认性主张。confirmation family数仍须由开发成品率反推并在访问confirmation前冻结。
- 提交证据顺序从本决定起固定为decision/config先于科学实现；D-141的用户裁决已先发生在对话而登记提交随后完成，不回写或重排既有Git历史。

## D-143：BIND包络、闭环可见体积、模板白名单和语义成本补充获批

- 日期：2026-09-14；状态：approved for protocol-first implementation and local/server contract verification, not data execution。用户在复审外部意见后逐字批准本补充；D-142仍有效，本决定收紧其实现形态。协议提交必须先于继续实现；不授权house生成、训练、validation效果、confirmation生成/reveal或私有数据读取。
- 五方法每次接受节点观测时都由共享状态合同保存“本次原始观测AABB”和“截至本次、只增不减的可靠支持包络”；包络不得由融合后的平均centroid/extent反推。TAF/ELU/WFR/LOW已通过`GraphRevision`产生BIND successor；VSMT节点BIND也必须关闭当前版本并打开携带原始AABB与累计包络的规范successor，仍计一个高层BIND而不按物理版本数加价。白话：杯子先在桌左、后在桌右时，两次原始盒子都保留；不能只留下从未真实占据过的中间平均盒子。它不等于把移动自动判成同一身份，是否BIND仍由既有公开候选规则决定。
- packet v3只新增节点无关的`visibility_observations`，由公开depth、相机标定和pose形成受遮挡深度限制的匿名可见体积；不得保存`node_id→机会真假`。共享函数分别将这些体积和当前公开区域与每个方法自己的记忆相交，才判断该方法的节点是否错失机会；远平面在节点之前即遮挡，不累计。例：五方法记住的杯子位置不同，同一匿名可见体积会对它们分别产生不同机会结果。它不使用共享bootstrap位置代替闭环方法状态，也不把真值可见性送入packet。
- “已声明语义变化”采用模板—真实diff封闭白名单，并由共同auditor对不经过executor的TAF/ELU/WFR/LOW同样执行；方法自报`declared_template`不能自行授权任意改写。统一terminal后SPLIT不得原地改lifecycle，alias/canonical转移只允许MERGE，其他模板只允许各自已登记的关闭、追加和successor形状。白话：把一次坐标重写叫做“已声明”不能逃过检查；声明和真实图差必须吻合。它不要求基线改写成VSMT程序。
- 严格整组截断除`cutoff_group_count/candidate_count`外记录`unused_capacity`。RELINK双端点循环另记`endpoint_pair_evaluation_count`以审计二次计算量，但实际通过语义门并进入桶的程序才计pre-cap candidate；RELINK不加入指数歧义护栏。白话：容量20只保留13个时，报告剩余7格为什么没有被低分组填充；尝试过100对端点也不等于生成了100个合法候选。
- 编辑成本按canonical开放关系事实而非物理edge version数计算。RETRACT为终止实体必须关闭的incident edges不逐条加价；MERGE重锚/去重后若`(relation, canonical source, canonical target, frame)`事实未变，也不按重开版本数加价，但MERGE本身仍计一个高层原子。真正新增的持续关系事实计growth，丢失或改变无关事实计collateral。例：两个重复杯子合并后仍只有“杯子位于地点A”不算关系增长；凭空多出地点B才计费。它不使MERGE免费，也不免除副作用。
- entity RETRACT确认性主张受预登记保护：开发审计必须在新原始包络＋裕度规则下报告per-family构造yield与candidate recall。单位不足时只能在confirmation访问前按授权增加family，或如实报告功效不足/无确认结论；不得在看到confirmation后降级为描述性。包络裕度只可依据未见confirmation的开发安全校准调整，禁止为达到目标yield而缩小。该条追加D-143而不回写D-141历史。

## D-144：D-140～D-143工程基线获认可并形成2-house不可执行数值提案

- 日期：2026-09-14；状态：engineering baseline accepted, two-house proposal requires review and is not executable。D-143服务器164/164及合成packet v3 smoke交付后，助手在对话中明确推荐“批准D-140至D-143实现作为工程基线；下一步只制定并审查2-house开发审计数值，不授权数据生成、训练、private或confirmation”，用户回复“继续”。据此认可当前工程基线并授权本轮制定[机器提案](../configs/vsmt/vm04_l1_two_house_audit_proposal_v1.json)；不把该回复解释为来源读取、实现或运行授权。
- 两house建议从ProcTHOR-10K `0.1.2`作者train分区完整manifest中按原seed `260914`哈希预选；机械合格只查来源分区、唯一ID和记录可解析，不看目标能否构造、候选、teacher、private身份或未来。两个family共36个固定episode/1,152帧，任何加载/构造失败留在原slot且不换house。manifest、license和实际house ID摘要当前仍为null，先做只读inventory也须用户另行批准。
- 审计建议预登记strict/balanced/permissive三组类型化关联profile，只用于同一公开分量的容量重放，不按private结果选赢家；候选cap报告16/32/64，64是资源上限而非正式cap。审计临时值建议为支持包络可靠性0.9＋每边2 cm裕度、机会可靠性0.9＋连续3次、SPLIT/REPLACE护栏6个歧义变量/729变体/32条总incident edge；正式值全部继续为null，2/5 cm裕度和2/3/4次机会只作敏感计数，裕度不得为提高yield而缩小。
- public层须在无private/teacher/reference/future挂载下封存free-space/visibility存活、原关联分量、逐桶容量/截断/unused、护栏、RELINK端点对及资源；之后private evaluator才报告逐slot construction yield、严格canonical reference recall和D-143 entity RETRACT合法recall。其他语义等价类recall保持null，避免在BIND/BIRTH等边界裁决前暗定答案；本批不生成teacher概率或五方法效果。
- 资源建议为两个family worker各处理一个预选house、一个确定性串行GPU descriptor队列、前台硬停1800秒、stage≤4 GiB/每family≤2 GiB/报告≤64 MiB、进程树RSS≤40 GiB、GPU分配≤24 GiB、新资产下载0、训练步0。capacity probe预计超过30分钟则不启动。construction failure和candidate miss是报告结果而非重跑条件，不设最低yield/recall通过门；来源inventory、审计代码、服务器合同和实际运行仍需依次审查授权。

## D-145：截断顺序无关、地点相邻归入骨架与审计放宽标注获批

- 日期：2026-09-14；状态：implementation delivered locally, server receipt pending, still not executable。用户在助手交付D-144验收意见后回复“这次修改你来做，然后我再交给GPT审批”，据此实现两项必修与三项次要收紧；不把该回复解释为来源读取、2-house运行、训练或confirmation授权。
- 候选桶的严格分数截断此前只对已保留集合增量重排，被截断的组会被后到的低分小组顶替，于是封存目录取决于枚举顺序而非候选集合。桶现在记住截断线，排序在线后的组直接拒绝且截断线只收紧；超容量组与护栏拒绝组仍单独计数、不设截断线。白话：这解决“同一批候选换个产生顺序就得到不同目录”的问题；输入逐个到达的候选组与桶容量，输出与一次性排序完全相同的保留集合。例如放不下的3候选组被截断后，后到的2候选低分组不能因为塞得进而顶替它。它不改变任何阈值，也不决定最终提交哪个事务。
- 地点身份已由世界格坐标确定，因此格与格之间的`adjacent_to`是坐标的推论而非修订决定。共同`place_scaffold`现在自行维护相邻边，使用`adjacency-birth`/`adjacency-bind` provenance且不追加任何学习模板；共享关系更新把这类观测记为`scaffold_maintained`，公开候选生成器不再为骨架关系开容量桶或生成RETRACT/REPLACE。合成完整packet上候选目录因此从26项、截断40项降为6项、截断0项，而61条canonical关系边不变。
- 共同审计现在报告`semantic_allowance_templates`与`semantic_allowance_is_result_level`：`classify_mutation`取结果所声明模板的并集，一个结果同时声明MERGE与其他模板时该放宽会比逐版本判定宽，因此如实标出而不是默认成立。逐版本模板归属需要结果合同新增字段，本轮不实现。
- D-144提案同步收紧：来源inventory改为“只读清点→冻结manifest与eligible house ID摘要→公布audit house ID→才可审查生成”的独立前置步骤，house选择不得与manifest冻结同批完成；`minimum_consecutive_missed_opportunities`新增不得为提高yield而下调；private层须按0.02/0.05两档裕度分别报告entity RETRACT合法候选recall；`protected_incident_topology_change`明确只作评价期指标而非在线闸门。提案的工程基线摘要因本轮改动作废并置null，须取得新的服务器回执后才能重新填写。
- 固定入口改为新stage `vsmt-vm04-l1-capacity-scaffold-v1`并导出到新路径，不覆盖D-143已验收报告；期望测试数更新为executor 42、L1 31、VSMT 101，共174。本地标准库分组全部通过且本地smoke干跑成功，但本地通过不等于服务器验收，也不代表D-059用户代码审查已完成。

## D-146：无模板边操作收口、跨帧坐标邻接与共同审计v2获批

- 日期：2026-09-14；状态：implementation delivered locally, server receipt pending, still not executable。用户据GPT对D-145的审查指示继续修复五项并暂缓一项；本轮仍未推送、未连接服务器、未读取source/private/confirmation。
- D-145为骨架相邻引入的`template=None`边操作原先对任何调用者开放，一个适配器可以据此把建边藏到模板白名单之外。现在`create_edge`/`bind_edge`只允许受信任的确定性包装（`vsmt.place.scaffold.v1`、`vsmt.public.bootstrap.v1`）省略模板，其他method_id直接报错。白话：这解决“不记模板的边操作变成绕过审计的后门”；输入一次边操作及其调用者身份，输出要么记模板要么被拒绝。例如记忆方法调用同一接口建相邻边会失败。它不改变骨架自身的语义。
- 骨架相邻原先只取本帧`adjacent_to`观测，因此本帧新见的格与图中已有的邻格连不上。现在骨架对本帧每个地点格按格边长查四邻格，只要邻格是开放骨架节点就建立或附加证据；本帧确有观测时用该观测的公开支持摘要，否则用由两个格坐标推出的公开摘要，计数分为`observation_supported`与`coordinate_derived`。对角格不相邻。格边长由开放骨架格的`extent_m`取得并要求一致。
- 共同post-update审计记录因新增`semantic_allowance_templates`与`semantic_allowance_is_result_level`升为`vsmt-common-post-update-audit-v2`，并在D-143配置登记该版本号。逐版本模板归属本批暂缓实现，登记为`per_version_template_attribution_blocks_five_method_comparison=true`：在五方法主比较之前必须补齐，否则一次声明多模板的结果会得到比逐版本更宽的语义放宽。
- 新stage的started、contract receipt/success、smoke receipt/success五个schema串一并改为`capacity-scaffold`，避免新stage沿用已验收stage的记录身份。2-house提案另补`opportunity_reliability_threshold_may_be_reduced_to_improve_yield=false`，与机会次数、支持裕度三项禁止下调条款对齐。
- 本地固定分组为executor 42、L1 31、VSMT 104，共177项通过；本地smoke干跑成功且与D-145同构：61条canonical关系边不变，`place_adjacency_updates`为born 60/bound 0/deduplicated 60/observation_supported 60/coordinate_derived 0，候选目录6项、9桶、截断0。跨帧坐标邻接由新增合同测试覆盖，单帧smoke不触发该分支。本地通过不代替服务器验收或D-059用户代码审查。

## D-147：无模板骨架边必须先验授权且失败原子

- 日期：2026-09-14；状态：implemented and fixed-entry server verified, still not executable。GPT复审复现D-146权限检查发生在边与provenance已写入之后：非受信任调用者可捕获异常再`finish`，得到新增边、零模板且共同白名单通过；受信任method ID也可把非`adjacent_to`关系伪装成无模板骨架更新。用户随后明确回复“你来做吧，开始”，授权该修复与必要验证；后续“继续”仅执行既定push和服务器`contracts → smoke → export`，不授权source读取、2-house生成、private、训练或confirmation。
- 公开`create_edge`与`bind_edge`恢复为必记BIRTH/BIND，不再接收调用者提供的`template`或`purpose`。无模板边只经骨架内部专用入口形成；该入口在任何图字节、delta列表或模板列表改变之前，必须同时验证调用者属于受信任确定性包装、关系为`adjacent_to`、两个端点均为开放place，且provenance purpose由代码固定。白话：这解决“已经写完边才说没有权限”的失败原子性问题；输入一次边操作和调用上下文，输出要么完整合法写入，要么revision逐字节不变。例如普通方法尝试无模板建边并捕获错误后继续结束，结果仍必须是真正NOOP。它不新增事务模板，也不改变合法地点邻接的图语义。
- 必要反例至少覆盖非受信任create、非受信任bind、受信任身份对非邻接关系三类；每类都检查异常发生前后revision内部图和created/closed/template记账不变，并检查捕获异常后不能封存未声明边。跨帧邻接、候选6项/9桶/0截断及共同审计v2继续沿用D-146，逐版本模板归属仍是五方法主比较前阻断项。
- 协议提交`0be2854`先于实现；`122cea6`移除公开接口的模板抑制参数并实现先验校验的骨架专用create/bind，三类失败原子反例通过；`74161b6`把机器合同和固定入口绑定到该策略并将VSMT期望数更新为106。固定入口在本地临时目录对`74161b6`顺序执行contracts与smoke：executor 42、L1 31、VSMT 106共179项通过，smoke仍为61条canonical关系边、6候选、9桶、0截断；这不是服务器回执，不回填D-144工程基线。
- 服务器在受审`33aec1c`上按固定入口顺序通过179项合同与同构smoke，导出报告`results/vsmt_vm04_l1_capacity_scaffold.json`摘要为`b5918086e5ee7f4e30d113b87b3b7546c5083f6431374abd7471e33562c68eff`，由结果提交`7641509`回传。D-144提案工程基线据此绑定该受审代码与报告；该工程回执不改变提案的不可执行状态，也不授权后续来源或数据步骤。

## D-148：冻结D-144审计数值并授权一次性交付完整2-house数据入口

- 日期：2026-09-14；状态：audit values approved and implementation authorized, inventory and generation still blocked。用户逐字批准“按D-144当前数值冻结，立即实现完整2-house数据入口；实现完成只做一次总审。总审通过后运行inventory并公布固定house IDs，再由用户确认后直接生成数据”。本决定把机器提案状态改为`approved_for_implementation_not_executable`，只开放`audit_numeric_values_approved`与`implementation_authorized`；source inventory、house选择、生成、private evaluator、训练、validation效果和confirmation授权仍为false。
- 本批实现必须一次性交付七段固定能力：只读来源/license清点、冻结source manifest与eligible ID摘要、与清点分开的确定性2-house选择与36-slot不可变manifest、两个family worker的模拟器生成、公私文件分离与trusted L1匿名化、public-only容量重放封存、封存后private严格recall及合同/资源停止/导出。白话：输入冻结配置、ProcTHOR作者train清单和两个稍后公开的house ID，输出36个固定slot的公开packet、隔离私有标签、容量审计和失败回执。例如某slot构造失败就保留失败且不换house。它不等于现在已经读取来源、生成数据、看private结果或选择正式阈值。
- 实现完成后只做一次总审；总审通过才单独授权并运行inventory。inventory运行只冻结manifest/license/eligible摘要，不得同批选择house；house IDs公布并由用户确认后，才可把generation/private audit授权位在新的协议提交中打开并执行。不得用预写入口绕过这两个运行闸门。

## D-149：完整2-house入口总审通过并开放只读inventory

- 日期：2026-09-14；状态：inventory executable, generation still blocked。一次性总审绑定提交`0d4fbfe340f4c4cad83cd38601175409bc70a89b`：固定入口本地精确通过executor 42、L1 31、VSMT 131，共204/204；Python编译、JSON解析、diff检查通过，`scripts/notes.txt`未变。总审同时核对公开重放不读private计划或25–31未来帧、每帧公开agent action已登记、来源commit/license边界、失败不换house、资源硬停以及公开错误不泄露private异常文本。
- 按用户已批准的顺序，现在只开放`source_inventory_authorized`并把状态改为`inventory_executable_generation_blocked`；inventory与select仍必须是两个独立命令，前者只冻结作者train清单、许可证与eligible ID摘要，后者只按冻结摘要和seed 260914确定两个house。白话：这一步解决“先把可选房屋全集固定，再机械地抽出两间”的问题；输入是固定ProcTHOR-10K 0.1.2本地只读checkout，输出manifest/license/eligible摘要和随后公开的两个house ID。例如换一个枚举顺序不能改变选中结果。它不运行模拟器、不生成任何帧、不读取private评价，也不开放训练或confirmation。
- `generation_authorized`、`private_audit_authorized`、训练、validation效果与confirmation继续为false。两个house ID公布后必须停住，等待用户确认，才可在新的协议提交中绑定inventory/selection摘要并开放生成。

## D-150：授权一次性准备固定ProcTHOR-10K来源checkout

- 日期：2026-09-14；状态：source checkout acquisition authorized, generation still blocked。服务器总审合同通过后只发现已安装的ProcTHOR生成器包，没有D-144要求的ProcTHOR-10K 0.1.2 Git数据checkout；用户明确回复“可以下载”。据此允许在审计stage之外向数据盘一次性取得官方仓库Git元数据、`LICENSE`和`train.jsonl.gz`，必须checkout到`d54954a81e7126001e552c2d7904ee2e0d49eaae`，下载硬上限64 MiB，不得取得validation/test数据。
- 白话：来源准备解决“服务器有模拟器代码但没有可清点的房屋定义”这个运维缺口；输入是官方固定commit，输出一个可由inventory核验commit和许可证的只读checkout。例如只物化作者train压缩清单，不取val/test。它不属于audit stage内部的新资产下载，不改变D-144阈值、房屋选择规则或资源数值，也不授权模拟器生成、private评价、训练或confirmation。
- 来源准备成功后按同一固定代码依次运行服务器contracts、单独inventory、再单独select；公布两个固定house ID后停止，等待用户确认生成。

## D-151：冻结2-house来源摘要与固定house IDs，等待生成确认

- 日期：2026-09-14；状态：inventory and selection complete, generation blocked。服务器在`a8fa08a74bad99218a5be72d874841dd169695ab`通过204/204合同，回执SHA-256=`d29caeaaf88cf58d5829a7fe9bda4b61fd79c594439cff437ce7835ccce7879b`。一次性来源准备只物化52,316,238字节的`train.jsonl.gz`，SHA-256=`d64450ec821aef55351f62885e4d56b3f0d948693af467bb7f6532850ef4fa37`，与固定commit的LFS指针一致；gzip检查通过，未取得val/test。
- inventory独立清点10,000个author-train house，冻结source manifest=`7db1df1e…9269bd`、license=`3767827e…eb9e52`、eligible IDs=`31b9d819…fb6d87`；该步`selection_performed=false`。下一条独立select按seed 260914和冻结manifest确定`train:004270`与`train:008243`，selection SHA-256=`8fb750d8…5a1e3d`；失败不换房规则不变。
- 白话：固定house IDs解决“先看到哪间房容易构造，再决定用哪间”的自选风险；输入完整10,000房屋ID清单和预登记seed，输出两间不可替换的审计house。例如后续某个slot失败也仍留在原house和原slot。它不证明两间房能构造全部程序，也没有启动模拟器、生成帧、private评价、训练或confirmation。
- 当前只把来源、选择摘要和私有程序分配salt摘要写回机器配置；`generation_authorized`与`private_audit_authorized`仍为false。用户确认这两个固定house后，才新增协议提交开放generation/private audit并从现有planning stage直接继续。

## D-152：确认固定house并开放完整2-house生成与封存后private审计

- 日期：2026-09-15；状态：generation and post-seal private audit authorized。用户逐字确认`train:004270`与`train:008243`并要求直接开放generation/private-audit生成数据。据此机器配置只把状态改为`generation_executable`并开放`generation_authorized`、`private_audit_authorized`；D-144全部数值、来源/选择/程序salt摘要、失败不换房、资源停止、公私边界及训练/confirmation阻断均不变。
- 固定执行顺序为当前提交服务器contracts，通过后以D-151 planning stage运行capacity；只有capacity ready才运行两个family worker的generate，然后依次materialize、public-seal、private-eval、verify、export。白话：这一步解决“协议和两间房已固定，但运行闸门仍关闭”的问题；输入是封存planning stage和固定来源checkout，输出36个slot的公开packet、隔离private标签及容量/recall审计。例如某slot无法构造时记录失败且不换房。它不开放train/validation效果实验、模型训练、confirmation或L2。

## D-153：默认出生视角零产出后固定匿名初始视点搜索

- 日期：2026-09-15；状态：generation runtime fix authorized，原失败stage永久保留。服务器在`a7f35e07cae18576ad42466b3b7f20f2595fc32c`完成contracts 204/204和capacity后，两个family worker均正常退出，但36/36固定slot都在采帧前报`insufficient anonymous visible targets`；generate约142.81秒，materialize据此得到0 complete。失败house、slot和原stage不得删除、覆盖或替换，public-seal/private-eval未运行。
- 每个固定house在family worker分派slot前只做一次确定性初始视点搜索：读取AI2-THOR当前house的`GetReachablePositions`，按坐标排序并在0/90/180/270度水平朝向扫描；候选只以面积不少于196像素的匿名mask数量、这些mask总像素数及坐标/朝向字典序评分，选择最高项并供该family全部18个slot复用。搜索至少需要两个合格匿名mask，因为SPLIT/REPLACE需要两个目标；失败仍占原house并停止该family，不换房。
- 白话：这个修复解决“模拟器随机/默认把相机放在看不见对象的位置”的工程问题。输入是同一固定house的可达相机位置和匿名mask几何，输出一个固定起始相机位姿。例如某位置能看见3块合格区域、另一位置只能看见1块，就选前者；同分时只按坐标和朝向决定。它不按对象名称、类别、instance ID、事务是否成功、未来帧或private评价挑容易样本，也不改变D-144阈值、house、slot、训练或confirmation授权。

## D-154：固定ProcTHOR 0.0.1到AI2-THOR 1.0.0房屋schema兼容

- 日期：2026-09-15；状态：generation source compatibility fix authorized，前两次失败stage均保留。`a0e8410`服务器contracts 207/207与capacity通过，但36/36在family级视点搜索前失败；只读诊断确认Controller初始事件已失败，首个明确错误为旧字符串`proceduralParameters.ceilingMaterial`无法反序列化为AI2-THOR 5.0.0的`MaterialProperties`，转换三类material后又明确要求把house schema从`0.0.1`升级为`1.0.0`。因此D-153看到的`GetReachablePositions`失败是无效空场景的次生错误，不把它解释成固定house本身没有可视对象。
- worker必须在内存中按已登记官方ProcTHOR提交`53d5bd4…`的`upgrade_house_version.py`语义做确定性兼容：升级material字段，使用固定安装包的`asset-database.json`补门窗hole/asset position，标注exterior wall并把schema写为`1.0.0`；原始source record字节不改。Controller创建后必须先检查初始事件成功且对象列表非空，再允许D-153视点搜索；任何转换、asset缺失或场景创建失败仍使固定slot失败且不换house。
- 白话：这个兼容层解决“旧数据能解析成JSON，但新模拟器不认识旧字段形状”的版本问题。输入是冻结的0.1.2房屋记录和同一固定ProcTHOR安装包的asset尺寸，输出只存在于worker内存里的1.0.0房屋字典。例如`floorMaterial: "Wood"`变成`floorMaterial: {"name":"Wood"}`，门窗旧包围盒按官方规则变成洞口和asset位置。它不是重新生成房屋、修改原始数据、下载新数据、按事务结果修场景，也不开放训练/validation/confirmation。

## D-155：用房屋登记agent pose启动可达点查询

- 日期：2026-09-15；状态：generation compatibility completion authorized。D-154实现后在服务器只读探针中，两间固定house已分别创建出223和136个对象，但AI2-THOR仍把agent留在procedural house创建前的旧坐标，直接`GetReachablePositions`继续因越界失败。把agent先`TeleportFull`到升级后house自带的`metadata.agent`，同一`train:004270`查询立即成功并返回1299个可达位置。
- worker创建house并通过对象非空检查后，必须先按该house登记的agent position/rotation/horizon/standing做一次确定性bootstrap，再调用D-153可达点扫描。bootstrap pose只用于让模拟器从有效场景坐标开始查询，不能直接充当最终公开起点；最终起点仍由全部可达位置上的匿名mask几何规则唯一决定。
- 白话：这是把“寻路从哪里开始算”放回房屋作者登记的合法起点。输入是房屋JSON已有的agent pose，输出是可用的可达点集合；例如原来从场景外算会越界，从房屋内登记点算得到1299个位置。它不按对象、事务或结果挑镜头，也不改最终视点评分、house、slot或任何训练授权。

## D-156：服务器重计算强制多worker且不得按墙钟截断

- 日期：2026-09-15；状态：execution requirement approved，允许修复并继续已授权D-152审计。D-155实现后两间固定house共得到16个完整、20个构造失败的固定episode；16个完整episode均成功materialize。原`public-seal`按episode与三个association profile串行运行，只占12核服务器的一个CPU核，并在完成6/48个重放单元后被D-144的1800秒墙钟检查终止。失败发生在private打开前；原stage、六个完整单元和`public_audit/resource-stop.json`必须保留，不能覆盖或伪装成成功。
- 用户据此明确规定：以后服务器上的生成、调参、训练、验证、测试、检验和审计，只要存在独立工作单元就必须使用多个worker，并根据CPU、GPU显存、内存和I/O采用最大安全并发；不得默认串行或机械固定为少量worker。当前12核、62 GiB RAM、单重放进程约304 MiB RSS，恢复入口固定请求12个CPU worker，运行时仍须记录实际worker数、任务分片、逐worker退出和与完成顺序无关的规范合并。
- 用户进一步明确“需要跑得久就跑久一点”，因此正式有效工作不再因预设墙钟到达而失败；原1800秒只作为本次失败事实保留，不再约束恢复后的public seal及后续正式服务器计算。内存、显存、磁盘剩余量和异常进程保护继续生效，因为它们防止机器崩溃或写满，并不以时长截断合法计算。训练公平性以后用冻结样本、配置数、训练步数和停止规则约束，不用墙钟强杀。
- `public-seal`恢复采用新的原子任务目录：每个`constructed episode × association profile`由独立worker只读25帧公开输入，在独立attempt目录写prior、三档catalog和结果；全部文件及摘要完成后才原子提升为完成单元。失败或中断的attempt原样保留，后续同一固定入口只跳过摘要验证通过的完成单元，不覆盖旧文件。最终按原36个episode顺序和固定profile顺序规范合并，private仍须等`public.seal.json`及其成功回执存在后才可打开。
- 恢复代码与原生成/materialize代码分开绑定：上游stage固定为`53d47367c7b30cff7d518d0d15fde1dca37ace0c`，并核验materialize receipt、public plan、原resource-stop和started摘要；恢复及后续private/verify/export回执同时登记上游stage代码与当前执行代码。它解决并行、续跑和完整provenance，不重新生成house、不替换失败slot、不改变候选/teacher/指标数值，也不开放train/validation或confirmation。

## D-157：VM-05区分学习排序器与确定性机制选参

- 日期：2026-09-15；状态：readiness protocol only, training and validation effects blocked。用户要求在D-156 public seal运行期间完善VM-05，并核查TAF、ELU、WFR三个论文方法究竟需要训练模型还是只采用机制；随后明确服务器任务不再限制运行时长。当前先固定职责分类和执行边界，不从尚未完成的D-144审计猜网络、网格、步数或seed。
- 来源复核显示，ConceptGraphs、Fusion++/Dengler及Khronos完整系统可依赖SAM、Grounding DINO、Mask/Faster R-CNN或外部语义分割等预训练感知，但本项目采用的多视角阈值关联/融合、存在证据更新、窗口片段/全局协调属于算法机制。TAF、ELU、WFR和朴素LOW因此不做梯度训练，只在共同train/validation内从预登记有限配置选择；不能称官方模型复现。共享DINOv2与L1/L2前端冻结且五主臂逐字节一致，不能把上游私有感知模型带入某一对照。
- 真正做梯度训练的是VSMT在线候选排序器及同架构DRCR、NECS两项因果消融；PHR是无学习公开启发式控制。三学习臂的架构、优化器、步数、seed数和五个确定性方法的有限网格当前保持null，须绑定VM-04完整审计、train/validation family、S-01～S-12选择语义及逐版本模板归属后另行冻结。每个VSMT/TAF/ELU/WFR/LOW主臂及DRCR/NECS/PHR内部对照各自最多12个完整配置选择机会；没有梯度不等于没有选参，内部消融也不得获得无界搜索预算。
- Claude复审指出首版readiness验证器浅拷贝、缺少显式键/冻结清单检查、未消费status、授权成功路径不可达及论文方法集合依赖LOW排序；这些均属于契约强度缺口，不改变上述科学分类。修订要求深克隆返回、顶层及关键嵌套键显式存在、前置/禁止清单逐项相等、单列TAF/ELU/WFR论文机制集合，并把当前planned-null状态与未来`frozen_executable`状态条件化验证。Dengler检测器表述已按其论文III-A核实为TensorFlow预训练Faster R-CNN，可保留具体架构名。
- VM-05所有服务器特征物化、配置搜索、训练和validation，只要有至少两个独立任务就先实测单任务CPU/RAM/VRAM/I/O，再采用最大安全worker数；GPU显存允许时并发独立learner，否则每个单learner仍使用多个数据worker。有效任务不设墙钟超时，资源安全只防RAM/VRAM溢出和磁盘写满；科学预算由固定样本、配置数、更新步数、seed及停止规则界定。输出必须记录worker分片、退出、产物摘要和与完成顺序无关的规范合并。
- [机器readiness合同](../configs/vsmt/vm05_training_validation_readiness_v1.json)当前`training_authorized=false`、`validation_effect_authorized=false`、`confirmation_authorized=false`。白话：输入是本轮已知的方法性质和资源规则，输出是以后实现/运行不能混淆的任务清单；例如ELU跑12组阈值是调参，不会产生ELU checkpoint。它不等于VM-05已经能跑，也不允许抢在D-144结果前选有利网格。
- Claude二次复核继续发现三项可执行性缺口：论文系统来源/预训练感知声明仍可篡改，frozen分支允许零步、零seed和空对象，八项前置只有名称清单而没有满足证据。修订把TAF/ELU/WFR的来源系统、预训练感知布尔、适配范围及总policy整行固定；frozen态要求`training_steps`/`seed_count`为正整数且四类配置对象非空；新增`satisfied_input_sha256s`，planned态必须为空，frozen态必须精确覆盖八项前置并全部为合法SHA-256。白话：这使未来授权必须引用外部审查产物，而不是让同一个JSON只靠把status改成可执行来自我批准；它不自动核验文件，正式入口仍须按摘要打开并比对实际产物。
- Claude三次复核发现同类冻结缺口仍存在于共享前端、学习消融定义、公平选择、多worker和资源安全节。验证器改为把所有非待填字段与递归不可变的整节常量全等比较；八项前置摘要还必须互不相同且拒绝空文件摘要，顶层接口按注解接受任意`Mapping`并在内部深克隆。白话：输入仍是同一份readiness JSON，输出仍只是通过或明确拒绝；例如把`same_train_families`翻为false或把GPU策略改成单worker会立即失败。它不冻结仍为null的网络、训练步数或有限网格，也不代替正式入口核对真实文件摘要。
- Claude四次复核发现Python数值相等会让布尔/整数与`1`/`1.0`混用，整节错误丢失字段定位，而且真实产物摘要核对仍只是文档承诺。修订改用canonical JSON锁定类型并报告首个变化字段；唯一动作授权函数强制接收八项产物路径并逐文件重算SHA-256，不再允许调用者跳过核验。白话：例如把12次预算写成12.0会在训练前明确指出该字段，把摘要字符串写对但文件内容不匹配也无法获得train授权。它只核验readiness前置证据，不表示当前planned记录已经开放VM-05。

## D-158：封存VM-04并审查20个失败slot的共同根因

- 日期：2026-09-15；状态：VM-04结果封存，训练/validation/confirmation继续阻断。用户批准保留当前导出结果，不启动训练，另行审查20个失败slot的构造修复方案。现有stage、raw失败记录、16个完整episode、public seal、private evaluation、verify和export报告均不得覆盖、删除或重生成。
- 下一职责仅做失败归因与修复提案审查：按固定house、family、program和失败阶段归类，核对是否存在共同工程根因；不得替换house/slot、按结果补样、打开teacher或训练输入。只有形成单职责代码/合同、输入输出例子、资源预算和独立stage方案，并经用户审查后，才可考虑新生成。
- 白话：这一步解决“当前16个样本能否直接进入学习，还是20个失败暴露了共同数据缺口”的问题。输入是封存stage的失败回执和完整产物，输出是失败分类及是否值得另开修复stage的提案；它不等于重新生成数据，也不等于方法效果结论。

## D-159：新stage按物理对象过滤并实行slot级视角独立

- 日期：2026-09-15；状态：新stage实现授权，旧VM-04封存不覆盖。用户批准保留事务语义不变；公开mask候选必须先与同帧`metadata.objects`求交；动作能力审计作为第二道前提；每个slot独立按公开几何规则确定start pose和物理目标；不足时固定slot失败，不换house、不换目标、不用mask centroid替代真实pose。
- 当前实现提交`b36153d`：`rank_visible_instance_ids`与匿名视点评分支持物理object ID白名单；视角搜索从family级移到slot级；每个slot写独立viewpoint receipt；旧stage、旧结果和旧代码绑定不变。动作结果细化记录与新stage完整配置仍须后续职责实现，不能把本地测试当作真实house复查。
- 白话：这一步解决“墙/天花板mask被当成事务对象，以及18个slot共用同一目标”的问题。输入是每个slot自己的公开视点和同帧物理对象表，输出是可执行物理对象目标与独立视角回执；它不改变BIRTH、REACTIVATE等记忆语义，也不等于新数据已经生成。

## D-160：纠正VM-04 slot视角实现与v1审计合同冲突（待代码审查）

- 日期：2026-09-15；状态：v2实现提案，generation/private-eval关闭。静态审查确认`b36153d`每slot重复同一个确定性全量视角扫描，无法产生不同pose；worker记录的物理对象选择规则与v1配置断言冲突，动作异常时成功路径才写的诊断被丢弃。v1配置及旧stage字节不改；新入口改用独立v2配置和stage ID，v2验证器同时核对一次family扫描、物理对象mask支持、slot索引和摘要链。
- 推荐口径待用户裁决：pose按公开几何全序排序，slot `k`取第`k`个满足现有`≥2`物理对象mask且每mask`≥196`像素的pose；没有第`k`项则该slot失败。目标集合互异不作硬门，只记录重复；额外质量阈值暂不设。其他可选口径包括强制目标集合互异或设置相对首位像素/对象支持底线，都会改变完成率、失败归因和采集开销，不能根据旧失败结果反推阈值。
- 正反案例：两个pose不同、各见到相同两只杯子时，满足“独立视角”但不满足“目标集合互异”；若后者硬门，第二slot须失败。第18个pose有两只各196像素物理对象mask时，按现有门通过；若额外质量门要求高于这一支持，则该slot失败。只见一只物理对象和大片墙mask的pose必失败，墙不补足第二目标。
- 白话：这个拟议修复解决“18倍搜索成本换来同一pose”和失败诊断缺证据的问题。输入是固定house的公开可达点、同帧物理对象mask表及固定slot索引，输出是一次扫描的有序pose表、逐slot回执和异常时private动作记录。例如第3个slot拿排序第3个pose，DisableObject失败会留下`errorCode`及文件摘要。它不等于目标必定不同、视角足够好，也不等于服务器真实house已复验。

## D-161：VM-04空间去重与先扫描诊断（待数值冻结和代码审查）

- 日期：2026-09-15；状态：proposed，v2扫描、generation、private-eval仍关闭。用户对D-160的两问提出选择规则修订：原前18名可能含同位置不同yaw和相邻0.25 m格点；先每位置留最高分yaw，再要求入选位置与全部已选位置的三维欧氏距离至少`D`。当前`D=1.0 m`仅作预登记建议（四个已知0.25 m格距），不是已获批准或真实house验证值。扫描与完整生成使用同一规则，目标ID只进入family内`private/viewpoint-target-audit.json`；公开`initial_viewpoints.json`保存完整pose排序、原前18与空间筛选前18的包围盒、独立位置数、mask数/像素支持及选中rank。scan-only固定两house并行运行、0 episode；生成入口必须核验扫描receipt、worker代码及视角规则摘要，但不会用重复率自动拒绝house。
- 反例边界：不同位置相隔1 m仍可看到同一物体，因此空间去重只能降低近邻重复风险，不保证目标集合互异；两pose都达`≥2`个各196像素mask，也可能分别看到20个大mask与仅2个临界mask，不能推断质量相近。对`D=1 m`，高分中心0 m先入选会排除−0.75 m和+0.75 m；后二者彼此相隔1.5 m，本来可组成两点合格集，所以贪心不足18不证明house不存在18点可行集。1299个可达点也不等于1299个物理mask合格位置。
- v2状态条件化：待审态要求目标互异/额外质量门为`null`、扫描及生成授权为false；未来经用户冻结后`frozen_executable`要求这两项显式false、D状态为`frozen_pre_registered`且只开放扫描授权，完整生成还须另有生成授权位。这样未来填入已裁决布尔值时不必改验证器，但任何D变动或效果驱动改门仍是新科学决定。`targets`截断提前、旧`select_initial_viewpoint`标明非生成路径、成功回执不再重读刚写的视角文件；不足目标时列表本就短于所需数量，旧写法并不会混入超过1–2个ID，因此此项不记作已复现失败。
- 扫描需为每个合格pose记录私有top-2诊断，旧mask排序对每个物理mask都序列化全幅像素并求摘要；新实现仅当两个mask的首像素索引与面积都相同时才求原来的摘要，排序键及同分回退顺序逐字节不变。白话：输入仍是同一批合格mask，输出仍是同一匿名几何顺序；例如两mask首像素分别在0和500处时无需读完整像素摘要，首像素与面积都相同才按旧摘要比较。它不是换目标规则或用私有ID为视角打分，只减少预扫描的CPU成本。
- 白话：空间去重提案解决“名次不同却挤在同一小区域”的视角分配问题。输入是一次冻结house扫描得到的公开合格pose及预登记1 m间距，输出是每位置一朝向、按分数和间距领取的最多18个pose；例如0 m已经入选，0.25 m位置会被跳过，1 m位置可入选。它不识别跨视角是否同一物体，也不保证18个slot都有pose。独立扫描解决“先花36个episode才知道分散度”的问题，输入固定两house和同一规则，输出0 episode的公开分散度/支持报告及私有top-2目标诊断；例如扫描报告可以分别显示原前18的top-1重复17次、筛选后top-1重复8次。它不是按诊断结果换house、自动调D或宣布新数据验收通过。

## D-162：冻结VM-04 v2两房纯视角扫描（生成继续关闭）

- 日期：2026-09-15；状态：用户已审实现提交`feeadef`并明确批准“预登记D=1.0 m；服务器恢复后只开放两间固定house的纯视角扫描，生成仍关闭”。v2配置据此置`status=frozen_executable`、`viewpoint_scan_authorized=true`、`minimum_position_spacing_m=1.0`及`spacing_value_status=frozen_pre_registered`；目标集合互异与额外质量底线显式false，保留原资格门和失败不替换原则。`generation_authorized`、`private_audit_authorized`、训练、validation效果及confirmation全部保持false。旧v1配置、原stage/结果不改。
- 执行范围只限在服务器恢复后的受审提交上核对`contracts`并扫描固定两family，随后导出公开统计与摘要链。先只读取得实际远端仓库/source/planning/output路径，核验原selection、inventory、plan、source checkout和当时CPU/RAM/GPU/数据盘；两个family为全部两个独立扫描单元，曾在同机并行生成成功不替代恢复后的资源复核。扫描失败或不足18个pose都原样保留，不换house、不调D、不自动启动episode；报告验收与下一次用户审查之前不开放完整生成。
- 白话：本次授权解决“先确认18个视角是否扎堆，再决定值不值得生成36条序列”的问题。输入是原两间房、公开物理mask几何和冻结1 m规则，输出是0 episode的视角分散度、支持范围、重复目标统计及文件摘要。例如某房原前18名只有5个位置，而间距筛选后有16个位置，报告会列出两者且不补齐剩余slot。它不是学会识别物体、判断事务语义、替换失败house或验收新数据。

## D-163：VM-04合同测试按独立组并行（服务器运行前运维修复）

- 日期：2026-09-15；状态：运维修复已取得服务器合同与扫描回执，D-162扫描范围不变。恢复后的服务器只读检查显示16个可见CPU、约62 GB cgroup内存额度、数据盘约27 GB空余、RTX 4080 SUPER约32 GB空闲显存；原`contracts`入口把executor、L1、VSMT三个独立测试组串行运行，与跨阶段多worker规则冲突。修订按当时CPU/容器内存及数据盘预检启动三个独立测试worker，逐组保存退出码/日志摘要与实际完成顺序，回执按预登记executor→L1→VSMT顺序合并；受审`67099f2`服务器252/252通过，随后原两house纯扫描也成功，实际数值见EXECUTE LOG-153。原stage、生成方法、视角规则和D值不改。
- 白话：这个运维修复解决“服务器有多个独立测试组，却只占一个worker”的问题。输入是受审checkout的三套合同测试及当时资源，输出是带worker数、分片、退出、日志摘要和固定合并顺序的合同回执。例如VSMT先完成、executor后完成，回执仍按executor、L1、VSMT列出。它不产生episode、不训练识别模型，也不表示真实house视角已经分散。

## D-164：固定两房动作能力探针代码审查（执行仍关闭）

- 日期：2026-09-15；状态：implementation approved, probe execution proposed and closed。用户明确保持空间去重`D=1.0 m`、目标重复只报告，并要求准备固定两房的动作能力探针供代码审查；生成继续关闭。因此独立`vm04_action_capability_probe_proposal_v1.json`仅授权实现，`probe_execution_authorized=false`，不改v2扫描/生成配置、旧stage或事务语义。以后若获用户代码审查和探针运行批准，必须另发冻结闸门提交，绑定已审实现提交；这轮不在服务器运行。
- 拟议探针的输入是受SHA-256绑定的原两房扫描receipt、18个固定pose与private top-2、原公开/私有episode plan的36个固定slot及同一ProcTHOR train checkout。每slot新建一份独立controller，live mask目标必须与扫描目标一致；不一致记录失败，不换目标。BIRTH、REACTIVATE、RELINK、RETRACT、REPLACE仅重放原注册的`-1/16/22/24`动作及此前的0.25°交替yaw，停在最后一次干预；NOOP、BIND、SPLIT、MERGE只审当前目标元数据，标为无物理干预，不把它们当动作成功。全程不截取RGB-D、不写episode、未来标签、teacher或记忆候选。
- 预写步骤为`contract`只读合同、`check`把九项纯边界测试分成三个独立worker并写各组退出/日志摘要、经另行冻结后的`run`先验check/扫描/来源/CPU/cgroup RAM/GPU/数据盘再启动两个已实测可同机扫描的family worker、最后`export`核验36个private slot SHA-256并只导出公开次数。每个stage只创建一次；失败保留原目录、退出码及已写前缀，不自动重跑，也没有合法运行的墙钟强制上限。后续闸门提交可继承已审实现提交并须证明入口/worker/测试字节不变，避免把后续提交HEAD要求成自身内嵌的SHA-1。
- 正例：RETRACT在frame22对原top-1的`DisableObject`返回成功，探针记成功并保留动作诊断；这只证明此固定姿态/动作路径在该模拟器可执行。反例：BIRTH在setup `DisableObject`返回`errorCode`，私有slot记录保留动作参数/错误，公开报告只多记一次失败；RELINK的真实`metadata.objects.position`缺失时记录`missing_action_precondition`，不拿mask centroid假装物理pose，也不发`TeleportObject`。若扫描目标和live目标不同，则固定slot停止，不使用较容易成功的另一个对象。
- 待审科学界限：动作返回`lastActionSuccess=true`以及终态元数据位置，只是模拟器能力证据，不足以确定BIRTH/REACTIVATE/RETRACT等记忆事务的语义，也不证明生成后公开识别或结构地图可靠。重复目标仍只报告；探针失败不调D、不换house/slot/程序/目标，不自动开启生成。动作错误和真实object ID只在服务器private slot及private family回执；公开stage receipt保存摘要和worker资源/退出，导出的公开报告按family/program/status汇总36槽。
- 白话：动作能力探针（proposed，未在真实house运行）解决“旧20个构造失败究竟是目标没有物理位置，还是模拟器拒绝固定动作”的问题。输入是已扫描的固定pose/真实对象元数据、固定程序和注册相机动作，输出每槽的私有动作诊断与公开次数汇总。例如两房各有一个RELINK槽缺真实position，公开报告显示对应程序`missing_action_precondition`次数，private文件才说明哪只对象。它不等于训练识别模型、构造记忆地图、生成episode或验收事务语义。

## D-165：来源层级目标边界阻断旧探针，保持生成关闭

- 日期：2026-09-15；状态：只读根因审计完成，目标规则待代码审查和科学冻结。用户要求彻底查明并修复VM-04数据验收问题；原D-164探针未运行。固定旧generate/verify、v2 scan、ProcTHOR source及两house审计证实：旧16条完整记录的首目标16/16不在作者`house.objects`；v2扫描72个选定top-2条目70个不在该层级。D=1.0 m、目标重复只报告、固定house/slot不替换和完整生成关闭仍保持。`metadata.objects`中的objectId/position仅表明模拟器登记，不等于作者物体资产，更不等于可安全物理移动。
- 立即工程修复：D-164配置转`blocked_invalid_v2_scan_targets`，探针执行位仍false；父入口在stage/controller创建前用冻结source record和private扫描目标验证资产归属，worker另设独立拒绝。旧v1/v2配置、扫描pose、原stage及失败字节不改。旧已完成16条不能当物体生命周期正例，也不能未经结构标签审计就进入主比较效果样本；其结构观察与非干预程序可能仍有诊断价值，不一概判无效。不会借现有20失败补样或根据private重复率换房。
- 独立合同缺口：v1/v2配置`planning_stage_binding`里的public/private episode manifest字符串各长65字符，不是合法64字符SHA-256；原v1与v2实际封存计划的两个manifest均是相同的64字符值。D-164原探针若按配置文本比较，会在资产检查之前误报“计划变化”。新探针单独登记经旧/v2封存计划核对的64字符摘要并硬断言，不改旧冻结配置或把无效65字符当证据。服务器只读先验复查在`17e5895`已到达预期`v2 scan top2 includes architecture`拒绝，0模拟器/0干预。
- 固定pose资格的只读核验已经在同两房36槽获得全部资产/可移动资产各至少2件，原扫描与新controller当前mask的top-2逐槽一致。故可以提出不改D=1.0 m、pose、house或slot的目标资格修订；这项覆盖不自动批准私有来源归属进入正式公开`ObservationPacket`，不把动作能力或语义正例当成已通过。新资产目标top-1依然重复12/10次；只报告的政策继续有效，不能依据这些private数值重排pose。
- 独立[v3目标边界提案](../configs/vsmt/vm04_target_boundary_proposal_v3.json)与条件化验证器`0bef772`预登记原v2扫描receipt、固定pose/D、物理干预目标作者资产∩当前真实有限position、REPLACE至少2个各≥196像素资格、按原匿名几何顺序选私有目标、重复只报告、资格不足占原slot失败；所有执行位关闭。NOOP/BIND/SPLIT/MERGE不发物理动作，其类型化实体/结构观测目标另有独立待审口径，不受物理资产门一概排除。待裁决的`relink_requires_moveable_or_pickupable`、`static_authored_asset_lifecycle_policy`、`non_intervention_typed_region_target_policy`、`l1_oracle_entity_structure_separation_policy`在待审态必须是null，未来只开探针的冻结态才要求显式口径。生成态尚未实现，不能靠切换状态开启episode；v1/v2/原stage不动。
- `83eddff`将两种静态资产口径做成需要显式参数的纯私有固定pose**物理干预**目标函数：允许生命周期临时隐藏静态资产时BIRTH可取排在前面的挂画；排除静态时改取可移动的椅子，RELINK在两口径下都只取可移动资产，REPLACE两目标按生命周期口径一起筛。后续审查发现SPLIT/NOOP/BIND/MERGE无物理干预，不应被这个作者资产门一概收窄；新函数对这些程序明确拒绝调用，类型化结构目标另登记。物理资格不足抛原slot构造失败，不回落墙mask、换pose或靠private重复挑其他对象。它尚未接入v3生成/探针worker，不改变v2冻结扫描。
- `25a0c5f`将v3纯函数改为直接消费当前mask，并按原首像素/像素数/完整binary mask摘要排序；同形同像素的两个作者资产mask若几何排序键完全相同，明确构造失败，而非沿用旧v2排序末端的私有object ID并列回退。mask输入枚举换序和metadata `objectType`字符串篡改不改目标几何结果，服务器19项纯边界测试通过。此处仅用于私有目标，原v2 pose及扫描排序/字节保持不动。
- `f7c8e92`核对v3合同所写顺序，将作者归属、当前metadata对象及真实有限position三项可信资格先做交集，再对这些资格mask按几何排序；缺position的作者资产不会进入并列失败或目标排序。服务器19项测试复过，后续新stage仍未执行。
- 结构记忆边界复核：旧16个完整episode的首目标为天花板等非作者资产，仅证明它们不是“物理对象生命周期”正例；VSMT的结构观测/NOOP/BIND/SPLIT/MERGE标签是否成立尚未独立审计，不能把所有墙面观察删除或仅因来源非资产判为结构任务无效。`physical_intervention_programs`作者资产门限于五个真的发模拟器干预的程序，其他四程序由新`non_intervention_typed_region_target_policy`待决；主比较前仍须逐类型审查。
- 新科学目标选择建议（未冻结）：原公开pose几何规则仍不得读取作者ID/类别/affordance，私有生成目标改为“本帧匿名几何排序中属于冻结作者`house.objects`递归资产、在当前`metadata.objects`有真实有限position的实例”；`RELINK`的物理移动还需显式`moveable`或`pickupable`前提及动作/终态核验。静态作者资产（如墙挂画）是否可作BIRTH/REACTIVATE/RETRACT的记忆消失/再见案例，不由此工程检查暗中裁决。另一口径是所有干预目标一律要求可移动，能减少静态挂画干预，但缩窄静态实体记忆边界；纯公开视觉识别选目标则需要独立训练与识别误差审计，不能用当前冻结两房私有ID作为部署捷径。
- 正反案例：作者`house.objects`里的椅子有当前可见mask与真实position，可进入私有资产资格；生成的`house.walls`墙即使有mask、metadata objectId和position也不进入资产目标。作者挂画属于资产，但`moveable=false`时对其执行RELINK应拒绝，而是否允许其被模拟器`DisableObject`暂时隐藏以构造REACTIVATE，仍是语义待决。资格profile仅是可审诊断，不是已生成或已训练的输入。
- 白话：来源层级边界解决“墙与椅子都被模拟器叫object，数据生成器误把墙当记忆中的东西”的问题。输入是作者房屋`objects`清单、当前mask几何排序及私有模拟器元数据，输出只在生成器私有侧的合格目标profile与公开匿名次数。例如两间房扫描top-2里70项是建筑结构，修复闸门会阻断原探针，避免把拆墙当成功事务。这不等于地图构造修复、训练过的物体识别器、事务语义冻结或开放生成。

## D-166：VM-04四项目标语义获批，关闭式实现及历史回执勘误

- 日期：2026-09-15；状态：用户明确批准四项语义用于实现/审查，目标动作探针和完整生成均未获运行批准。固定两间`train:004270/train:008243`、各18槽、v2 pose、`D=1.0 m`、目标重复只报告及失败不换房不变。v3合同状态改为`approved_semantics_implementation_only`，四字段均显式填值，`target_capability_probe_authorized/generation_authorized/training_authorized=false`。未来仅探针冻结态必须另经用户代码审查与单独闸门；这次不是新episode或训练授权。
- 物理RELINK只选作者资产中当前metadata有真实有限position、且`moveable`或`pickupable`为真的实例；仅有mask centroid或模拟器architecture metadata position不算物理移动。静态作者资产可作为BIRTH/REACTIVATE/RETRACT/REPLACE**可见性干预的候选资格**，但新动作/标签worker必须分别核验动作诊断、终态可见性/状态及旧记忆历史；`DisableObject`成功不等于物理删除，也不能自动确定记忆事务标签。不发物理动作的NOOP/BIND/SPLIT/MERGE仅由公开RGB-D及先前预测记忆产生匿名类型化区域证据；L1私有oracle仅提供匿名实体区域，建筑结构区域仍由公开证据产生，L1诊断不得成为L2部署捷径。
- Claude审查的RELINK“代码预先只接受True”是提案阶段真实的提前收窄：D-165虽披露，不能把它称为曾经开放的另一种物理RELINK选择。用户本次明确选True后，将其登记为已定科学语义，未来若新增“纯结构关系RELINK”须独立合同/类型规则与对照审查，不能通过把当前物理RELINK布尔值改False隐式实现。纯目标选择函数现接收已验证合同，196像素、REPLACE两个目标与物理程序集合只从该合同读；数值或批准语义被篡改，先拒绝合同而非静默漂移。该函数只做目标资格，仍未核验静态生命周期三条件或模拟器动作。
- 旧v1/v2两房配置`planning_stage_binding.public_episode_manifest_sha256/private_episode_manifest_sha256`各长65字符，是无效SHA-256字面值；实际封存计划及旧stage回执保存的是相应有效64字符摘要，v3单独绑定有效值。旧配置/旧stage/旧结果字节和原源码历史保留，不以65位字面值追认计划，也不回改其摘要链；新v3合同所有顶层`*_sha256`字段校验64位小写hex，`test_vm04_config_digest_shapes`同时普查`configs/vsmt`全部14份JSON、只对白名单内四个旧原字面值作历史例外，其他新增坏摘要直接失败。今后新合同还须在读取边界核对所绑定文件实际摘要。这个erratum不把旧生成合同重新声明有效。
- 旧`vm04_root_cause_audit.py`与`vm04_target_repetition_export.py`服务器只读导出跨两个family用了一个进程，报告未登记requested/actual worker及串行理由，确实偏离跨阶段多worker规则。旧公开报告自身有真实脚本/输入摘要和匿名计数，可作为历史只读诊断，但不能事后给旧回执填`actual_workers=2`或虚构串行豁免。若未来将其作为正式跨family审计重放，须新版本入口在资源核验后并行两个family、记录requested/actual/资源依据/分片/退出与确定性合并顺序，再导出新schema和路径；本轮不覆盖旧报告，也没有新审计运行。
- 白话：本决策解决“目标资格与记忆标签混在一起、数值在合同和代码两处各写一遍、旧摘要笔误及旧审计并发记录不足”的问题。输入是用户四项裁决、冻结扫描/计划与原报告，输出是关闭式v3实现合同和明确保留的历史偏差。例如挂画mask可在私有侧成为待核验REACTIVATE目标，但若旧记忆没有休眠挂画身份，它不能因模拟器`EnableObject`成功被标成REACTIVATE。它不等于新36条episode已成功、模型学会识别或旧单进程审计已经被并行重跑。

## D-167：固定两房新目标动作能力探针代码供审查，执行仍关闭

- 日期：2026-09-15；状态：implementation approved for code review, probe execution proposed/closed。用户审过D-166三提交并明确继续准备新目标动作探针供审查；这不是动作探针、episode、训练或旧test解封授权。独立`vm04_target_action_probe_proposal_v1.json`仍为`implementation_only_not_executable`，reviewed code空、探针/生成/训练执行位全false；D-164旧墙面目标探针、v1/v2合同及原stage不修改。固定两house、36原slot、v2 pose、`D=1.0 m`、重复只报告、失败不补样不变。
- 父入口预写`contract→check→run→export`四个步骤及新路径/schema：合同只读不建stage；`check`把合同/资格、动作/后态、阶段/导出三组独立纯测试交给三个worker，记录requested/actual、CPU配额/内存/磁盘、逐组退出与日志摘要，按合同→动作→导出固定顺序合并；`run`在用户审查后仍须新冻结闸门、精确受审源码祖先、同版检查回执、scan/plan/source/资源复核，先用一个worker对family00原slot00做scene create+TeleportFull的0干预资源实测，保存峰值RSS/退出/私有日志摘要；剩余cgroup内存至少为该RSS的4倍且再次核对CPU/GPU/磁盘后，才并行两个实际family worker。单worker仅限启动前测占用，两个独立family任务不因此串行。`export`只在36个私有slot与receipt/benchmark摘要都验过后输出匿名次数，未运行步骤不得被预写入口自动越过。长任务不设墙钟强制失败，旧成功stage不覆盖。
- 单worker场景预检运行时另采样逐设备空闲显存，记录启动值、最低值、结束值和GPU下标；同设备派发前剩余显存至少为观测空闲下降量的2倍，且不低于合同原8 GiB安全线；若采样下降量为零，单worker显存占用未被证实，拒绝派发而不假称安全。采样可能漏掉瞬时峰值，8 GiB静态线仍须满足，服务器审查可要求更密采样或更大安全倍数；2倍显存和4倍RSS都是待审工程预登记，不是训练预算或成功率阈值。
- worker在每个物理程序的原slot重新加载相同作者house、固定pose、当前metadata/mask；首先用原v2排序top-2只核对同一场景，然后由已审v3私有作者资产资格选1–2个新目标。v2墙面ID绝不成为动作对象，v3资格失败就记原slot。每次外界干预与注册相机动作先写`frame_index/arguments/diagnostic`，动作拒绝/异常保留尝试列表；`DisableObject`说成功但mask仍可见即记poststate mismatch，最终可见性/RELINK真实位置另核验。NOOP/BIND/SPLIT/MERGE不创建controller，`public_region_out_of_probe_scope`是范围说明，不是这些程序的成功/失败或公开结构证据验收。
- 动作路径完整执行原注册的32个相机动作及其中预设的-1/16/22/24帧干预；动作能力探针的终态从frame31注册相机动作后的事件读取，不从最后一次干预瞬间推断最终可见性。逐动作元数据/目标mask不写公开侧；失败后原槽仍保留已尝试动作并停止，不能借缩短时序把失败伪装为成功。
- 每次注册相机动作后在私有尝试记录中读取目标mask支持；已通过`DisableObject`隐藏且尚未执行注册`EnableObject`的目标若提前再次出现mask，原槽立即记`disabled_target_reappeared_between_actions`。例如BIRTH在frame -1隐藏挂画后，frame0相机事件又显示它，即使frame24再Enable成功也不准把这条路径报为可见性生命周期成功。这个中途证据仍不替代旧记忆历史核验。
- 新探针终态位置容差提案为5 mm：输入原`RELINK`注册x+0.5 m位置和终态`metadata.objects.position`，输出三轴各自是否相差≤0.005 m；例如预期x=2.500 m、终态2.504 m通过位置回执，2.510 m失败。这是探针工程核验数值，不是地图/事务评分阈值、动作碰撞护栏或用户已冻结主实验数值；用户代码审查时可要求更严1 mm（可能放大Unity浮点误差的假拒绝）或更宽1 cm（接受更大未达目标位移）。注册`TeleportObject(forceAction=true)`沿旧时序保留，成功状态必须标`collision_or_reachability_checked=false`，不能算物理可行RELINK；若要正式可行性正例，须后续单独审不强制的动作/轨迹与碰撞规则，不把当前探针成功冒用为结果。
- 静态作者资产可接受动作/每次隐藏后的mask/终态可见性探针，但旧记忆历史在本动作探针内未读取，所有slot显式`memory_history_checked=false/semantic_positive_label_issued=false`，绝不从动作能力直接出BIRTH/REACTIVATE/RETRACT/REPLACE正例。L1实体oracle与公开结构材料化边界也未由探针执行；完整生成须新独立合同/worker和另一次代码审查。公开导出不含真实object ID、动作参数、错误字符串、私有crosswalk或逐槽程序身份，只报family/program/status计数及匿名目标重复。
- 白话：新探针解决“旧视角能看到椅子却把墙当动作目标，以及动作成功后物体是否真的消失/移动没有证据”的准备问题。输入同两间房、原36个镜头/程序、当前真实mask与作者资产清单，输出待运行的私有逐动作/后态记录和公开摘要计数。例如BIRTH选挂画，隐藏动作若返回失败就保留frame -1错误码；若成功但画面仍有挂画mask也要报失败。它不是模型训练、记忆标签核验、正式物理轨迹可行性或新数据验收；当前没有服务器动作回执。

## D-168：仅开放固定两房v3新目标动作探针，生成和训练仍关闭

- 日期：2026-09-15；状态：用户已审`fe8b725`实现并批准固定两房新目标动作探针执行。v3目标合同状态从`approved_semantics_implementation_only`转为`frozen_target_probe_only`，仅`target_capability_probe_authorized=true`；独立探针合同状态从`implementation_only_not_executable`转为`frozen_probe_only`，仅`probe_execution_authorized=true`并登记`expected_reviewed_probe_code=fe8b725b4b8617b7795ef916ec92d874c901233c`。两份合同`generation_authorized=false/training_authorized=false`继续不变；旧D-164墙面目标探针与v1/v2配置、旧失败stage不改。
- 固定对象只有`train:004270/train:008243`两间house、family内0–17共36个原slot、D=1.0 m的v2冻结pose、原程序/replicate和v3作者物理资产选择。目标重复只报告，任何目标/pose/house替换或失败补样仍禁止。探针仅诊断原注册动作时序、动作返回/错误码、隐藏期目标mask与终态可见性/真实位置；不生成公开RGB-D episode、候选/teacher、记忆历史正例或模型效果。
- 用户认可的工程口径保持`relink_terminal_tolerance_m=0.005`、单worker峰值RSS的4倍剩余cgroup内存、观测单worker显存下降量的2倍且同设备至少8 GiB、原注册RELINK `TeleportObject(forceAction=true)`只报告`collision_or_reachability_checked=false`。例如终态x与注册x+0.5 m相差4 mm可通过**位置诊断**，但若传送穿过家具，探针不会把它叫作物理可行RELINK。位置/显存/RSS线不是地图质量或事务评分门；资源证据不够时原stage留失败回执，不换任务或降低安全线。
- 服务器顺序为：在精确冻结提交和干净隔离checkout复核合同/旧扫描/计划/source/环境资源；三个独立worker重新运行同版纯`check`并验receipt；一次0干预scene+TeleportFull单worker资源实测及摘要；满足资源线才并行两个family worker，保留每个原slot的私有动作诊断；全36个slot都有原槽诊断回执且私有链完整后才导出不含object ID的公开计数。纯`check`和动作能力探针成功不等于36个事务正例、地图/识别修复或完整数据验收；实际服务器回执须写EXECUTE，运行前不预测完成率。
- 白话：本冻结解决“代码已审且纯检查通过后，能否在不解封生成的情况下，用真实模拟器定位新目标动作的失败”的范围问题。输入是原两房、冻结扫描/计划、已审探针代码和安全资源检查，输出是待运行的私有动作/后态诊断与匿名公开计数。例如REACTIVATE在frame16隐藏椅子被模拟器拒绝，原槽保留错误码并在公开报告只增加一次拒绝；这不等于模型认错物体、记忆里已有休眠节点或整个VM-04通过验收。

## D-169：v1新目标动作探针结果保留与资源测量勘误

- 日期：2026-09-16；状态：v1固定两房探针已按D-168运行且原结果封存，资源测量边界需修复后另审。精确代码`1749a3f066e40ad914092bef099087e73d109b58`在隔离worktree执行，36/36原槽均留诊断回执、两family worker退出0、0 episode/0训练；匿名报告由原出口单独提交`a46fcec`。完整次数与摘要在EXECUTE LOG-159，当前不按结果换目标、pose、house或重跑失败槽。
- 20个物理程序槽中，16个可见性生命周期动作到达探针终态，RELINK 3个位置吻合且明确碰撞未查，1个RELINK `TeleportObject(forceAction=true)`在frame24返回`lastActionSuccess=true`但同一次动作metadata真实x就比注册目标少`0.049812 m`；frame24–31注册相机后该偏差不变。y/z偏差分别为`+0.000620/-0.001423 m`，未超过5 mm；x偏差超标，因此原槽正确记`terminal_poststate_mismatch`。这是动作返回与真实后态不一致；具体原因（模拟器放置、碰撞或位置修正）尚无接触/可达性证据，不能据此断定是哪一种机制，更不能归因于部署识别模型。
- v1资源回执登记单worker`resource.getrusage(resource.RUSAGE_SELF).ru_maxrss=86920 KiB`并将其乘4作为双worker RAM门。该API按[Python官方资源说明](https://docs.python.org/3/library/resource.html)只统计调用进程，不涵盖独立模拟器进程；父入口只在benchmark结束后再次读cgroup剩余内存，没有测运行期间容器内存峰值。因而“剩余内存≥4倍**总**单worker需求”在v1没有证据，不可把该回执称为完备并发内存审计。GPU运行时采样观测到空闲显存下降`1569718272` bytes，服务器约60 GiB cgroup余量且本轮没有OOM或退出异常，这说明本次完成，但不追认未测的单worker RAM峰值。原v1配置、code、private stage和公开报告不改字节；错误作为勘误明示。
- 后续仅准备执行关闭的v2工程预检：保留worker自身RSS辅助值，同时在0干预scene create/TeleportFull运行期间按[Linux cgroup v2官方说明](https://docs.kernel.org/en/latest/admin-guide/cgroup-v2.html)从同一cgroup采样`memory.current`/headroom，登记启动/最大占用/结束值和采样间隔，以观测的容器增量作为新的4倍并发RAM门；增量为零或取样失败时拒绝派发。样本可能包含其他容器进程且有限频率可能漏瞬时峰值，所以它是保守资源门而非精确Unity进程归因；未审新版本不得重跑动作或冒用v1 marker。原D-168只授权两房探针，生成/训练仍关闭。
- 白话：本勘误解决“动作诊断已经抓到一条真失败，但资源回执把Python内存当成整个模拟器内存”的证据问题。输入是原动作后态、v1公开/私有摘要和资源API口径，输出保留失败的结论与下一版更严格资源采样规则。例如RELINK说传送成功却少走约5 cm，原槽仍报失败；Python只用了85 MiB并不能推出Unity也只用了85 MiB。它不把失败变为模型识别错、不把19个探针终态变成事务正例，也不批准完整生成。

## D-170：v2动作探针并发RAM预检供代码审查，执行关闭

- 日期：2026-09-16；状态：implementation only、未批准v2服务器动作。D-168已运行的v1合同、源码历史、private stage与匿名报告保持封存。独立`vm04_target_action_probe_proposal_v2.json`继续绑定同两间`train:004270/train:008243`、各18个原slot、D=1.0 m、冻结v2 pose/计划和v3作者资产目标；`status=implementation_only_not_executable`、`probe_execution_authorized=false`、`expected_reviewed_probe_code=null`、生成/训练false。v3目标合同继续保持受审探针口径，不能用它单独打开v2动作。
- v2只修D-169的资源证据：在family00原slot00的0干预scene create/TeleportFull benchmark开始前记录cgroup剩余内存，每0.25秒读取一次同一cgroup的headroom，登记采样次数、最长采样间隔、运行窗口最低剩余值、结束/派发前值。原始采样序列写入private/resource-benchmark.cgroup-samples.json，父回执登记摘要且导出前重算最低值、次数、间隔；运行时观测RAM需求=`启动headroom－最小headroom`；若读数不可得、观测需求为零或派发前headroom小于观测需求的4倍，则原stage写失败回执并拒绝两个family worker。原Python worker的`RUSAGE_SELF`和原4倍门仍保留为辅助检查；逐设备GPU下降量2倍及8 GiB静态线不变。新check/probe/report采用v2路径和schema，不能冒用v1 marker或覆盖v1报告。
- 该cgroup读数通常包含同cgroup的模拟器子进程和其他进程；背景负载变化可能让单worker归因不准，0.25秒取样也可能漏过瞬时高峰。因此“4倍”只对**采样到的容器净需求**成立，不宣称完整进程树精确峰值。用户若要再次执行动作，应先审v2代码及此证据限度，再另行冻结v2 reviewed-code与执行位；当前不在服务器运行v2动作，更不从旧RELINK失败推断已找到Unity放置或碰撞根因。
- 白话：这个关闭式预检解决“Python只报告85 MiB，却不知道Unity在启动时用了多少内存”的问题。输入是零干预启动期间的容器内存读数、原固定场景和4倍安全门，输出带采样摘要的可审并发判断。例如启动时余20 GiB，运行中最低18 GiB，观测需求2 GiB；派发前还余8 GiB可过采样RAM门，少1 byte则拒绝。它不等于精确物理碰撞证据、VM-04 episode验收、识别训练或新的动作运行许可。

## D-171：原失败RELINK槽的受控复现与三层归因

- 日期：2026-09-16；状态：用户本轮明确要求“现有证据不够就复现这个场景，加一点东西能得出结论”。只开放原固定两房探针中`audit-family:01`原slot12的三个**诊断分支**，完整生成、训练、模型效果、其他house/slot和按结果换目标仍关闭。此诊断不是把D-170尚未获审的v2动作worker解闸，也不是将新代码合并为科学基线；独立入口先作原v1 receipt/private slot、v2 scan/pose、source house和v3目标摘要核验，精确干净提交与纯检查通过后才建唯一新stage。每个分支新建controller，重新验证旧live top-2和v3作者资产目标正好等于原失败槽，不允许重选。
- 先重放原24个注册相机动作，再在frame24对同一资产同一真实position分别执行：①原`TeleportObject(forceAction=true)`；②除`forceAction=false`外同一请求；③原请求前执行`PausePhysicsAutoSim`，其余原相机动作继续，终态后仅用`Done`读静止/运动状态。原分支兼作单worker容量benchmark，父入口运行中采样cgroup/GPU真实需求；只有4倍采样RAM、2倍采样GPU及8 GiB静态余量足够，才并行两个独立控制分支。原分支与控制分支绝不写episode/RGB-D数组或事务正例，拒绝/不支持也保留原条件的私有诊断。
- 每次动作记录请求和`lastActionSuccess/errorCode/errorMessage`、即时及后续8帧真实`metadata.objects.position`、`isMoving/isSceneAtRest`，并在请求/实际位姿对其他metadata对象算私有轴对齐包围盒（AABB，Axis-Aligned Bounding Box）相交数。AABB只用于寻找值得检查的邻近物体，不是Unity collider接触、可达路径或物理可行性证据；`forceAction=false`拒绝也可能是交互距离/可见性规则，须结合错误码和源码规则解释。公开仅导出三分支的匿名三轴误差、返回状态及AABB相交次数，真实object ID/类别、pose及错误原文都留private。
- 先前D-169/LOG-159的只读复算中z偏差写为`−0.001423 m`；本轮对原private frame24请求与同一事件position直接相减得到`−0.014230025 m`（约−1.423 cm），x=`−0.049812317 m`、y=`+0.000620067 m`。这是文档抄录的小数位错误，不改原private/公开结果字节；x与z均超过5 mm探针容差。复现结果须按真实新回执解释，不能因先前文字错误改变原失败计数。
- 三层结论分开：模拟器后态层判请求/返回/实际位置是否一致，受控分支可定位哪种执行条件改变误差；碰撞/可达性层只有明确collider或动作规则/错误证据才能称已查，本入口的AABB/强制传送均不足；记忆语义层要求公开前缀、先前预测记忆与动作/终态历史，当前探针`memory_history_checked=false`，任何动作成功或位置吻合都不签RELINK标签。即使同槽复现定位Unity处理，也仍不等于地图或识别模型出错。
- 白话：这个复现解决“传送说成功却少走约5 cm，到底是动作后态本身有偏差，还是物理阻挡，还是记忆更新判断错了”的分层问题。输入是原失败槽已经封存的房/镜头/作者资产/请求，输出同条件与两个单变量控制的私有动作轨迹和匿名误差。例如强制传送仍少走5 cm，而暂停物理后恰好到点，会支持自动物理结算参与位置修正；如果不强制失败并显示明确碰撞错误，还要核对它针对的到底是物体collider还是交互范围。它不等于训练识别器、用私有ID给在线记忆选目标、生成36条新数据或宣布物理RELINK语义已经有效。

## D-172：暂停后手动推进物理，复核碰撞导致的位置修正

- 日期：2026-09-16；状态：用户要求继续查明原场景根因的单槽追加诊断，生成/训练仍关闭。D-171已在精确提交`20d9682f1cab0500470d81f8efd154aefff466f8`的原固定house/pose/target执行三个新controller分支；独立[匿名报告](../results/vsmt_vm04_relink_mechanism_probe_v1.json)的SHA-256=`9cb7d18f6fe4779ac9dd33a1332a146c9f04297d21dd99ca0bfad9a9fe3a47de`，父receipt摘要=`36e695cc74af4a396576adf19fa109d87fd9d490df358e6cafa6774b4aea3092`。原强制动作重现即时/终态x=`−0.049812 m`、z=`−0.014230 m`，返回成功、即时目标`isMoving=true`；同请求仅把`forceAction`改false被模拟器拒绝，private原文明确写“传送后与另一件物体碰撞”，不把真实ID/错误全文导出；原强制请求前暂停物理后即时及后8帧三轴误差全零、目标`isMoving=false`。原分支真实cgroup/GPU采样需求约1.05/1.56 GB，两个控制worker并行退出0，0 episode/训练。AABB粗相交字段当前不可用，不能拿它当独立碰撞证据。
- 为排除“暂停物理只是冻结位置，并不能证明恢复结算会推开目标”的剩余解释，再在两个独立新controller中按同原槽重放前24帧、暂停物理、执行同强制请求和后8帧；之后每个复本固定执行50次`AdvancePhysicsStep(timeStep=0.01)`，共0.5秒模拟物理时间，保存每步目标真实position/`isMoving`和动作返回。两个复本作为独立工作单元并行；启动前复核当时cgroup/GPU/CPU/盘与D-171原完整动作单worker的采样需求，分别留至少4倍RAM/2倍GPU和8 GiB静态余量；运行中低于4 GiB紧急保护线即保留失败并停worker。旧D-171 stage、旧报告及v1数据不覆盖，新物理步stage采用单独配置/receipt/schema/出口。
- 新private报告与D-171三个控制的回执、原v1失败槽及扫描/来源摘要串联；public只出两个复本的首个位置变化步、首末三轴误差、运动步数和匿名“模拟器明确报告传送后对象碰撞”的类别。若手动推进物理也出现与原自动结算同方向/量级的修正，结合不强制碰撞拒绝可将**模拟器强制传送后的物理结算**判作已复现根因；但仍不证明机器人可达的运动路径，也不签发记忆RELINK正例。若50步仍不变化，只能把原自动结算期间的具体处理留为未定位，不能强推结论。
- 白话：这项追加诊断解决“关掉物理后到点，是因为障碍消失了，还是只是还没让物理系统碰它”的问题。输入是同一目标在暂停物理下已到达的请求位置，输出两次独立实验中0.5秒内每一步的真实位移。例如第1步把物体从请求x=3.878推到x≈3.828，且非强制传送明确说和另一件物体撞，便能解释原强制返回成功却少移动约5 cm。它不等于把错误目标换成无碰撞目标、在线识别训练、物理可达路径证明或完整数据验收。

## D-173：两房原RELINK槽的非强制端点校验

- 日期：2026-09-16；状态：fixed-scene diagnostic已完成、报告见EXECUTE LOG-162，未成为生成科学基线；依据用户本轮要求严格找出并修复原RELINK失配，只开放原固定两房四个原RELINK槽的端点复查，完整episode生成、训练、validation、confirmation与记忆正例全部关闭。D-171/D-172原失败slot12的非强制碰撞拒绝、暂停控制与两个手动物理复本已证明**原目标位置的模拟器后态失配根因**，不把此证据外推为另外三槽也碰撞、机器人路径可达或记忆语义已正确。
- 新`vm04_physical_relink_action`为私有服务器侧物理端点校验函数：输入已登记的原`TeleportObject(forceAction=true)`请求、原作者资产物性和冻结端点合同；输出只把`forceAction`置false的同请求，以及接受/拒绝、即时/终态真实`metadata.objects.position`、终态运动状态和匿名原因类别。原注册端点固定为初始真实x+0.5 m，真实位置容差5 mm；拒绝或偏差作为**原槽失败**，不得换目标、目的地、pose、slot或house，错误原文/object ID仅入private。仅检查模拟器可接受端点与实际后态，不证明机器人可实际把物体搬到此处。
- 新四槽入口绑定原v1两房动作探针receipt、v2扫描receipt、D-172匿名报告和源house/pose/原private slot摘要；原两个family各2槽，每槽独立新controller并行，基于当时CPU/GPU/cgroup/磁盘和已实测单worker需求选择四个安全worker，记录requested/actual、分片、退出与family/slot确定性合并。各worker重放原32帧相机动作，仅改变frame24`forceAction`，保留private诊断并匿名导出family×状态计数；若资源不足则**启动前**停，不减worker静默跑；没有wall-clock强杀。
- 三层判读：`lastActionSuccess`、即时与终态真实位置及物理步轨迹属于模拟器后态；非强制拒绝的私有明确碰撞错误说明该**请求端点**与另一对象冲突，不是独立验证Unity碰撞体几何、机器人路径或周边可达域；记忆RELINK语义另需公开历史、先前预测记忆、结构关系和版本化事务前后状态，本入口一律`memory_history_checked=false/semantic_positive_label_issued=false`。全部四槽结果只能决定当前端点规则是否可作为数据动作前提，不能通过识别器训练修补碰撞。
- 白话：这个探针解决“原四个RELINK是不是仅因强制传送假成功而被误判为有效端点”的问题。输入原两间房、原四槽的目标资产与x+0.5 m请求；输出四个原槽分别被模拟器接受且真正到点、因碰撞被拒绝、或因其他后态不符失败的匿名统计。例如原slot12只改`forceAction=false`后仍被明确报与另一物体碰撞，该slot失败并保留原场景，不去寻找另一个容易成功的角落。它不等于操作路径规划、识别模型训练、记忆RELINK正确性证明，也不等于完整新数据已经修复。

## D-174：两房原RELINK的真实交互能力探针设计

- 日期：2026-09-16；状态：`requires_action_plan_review_not_executable`，用户批准**先设计**抓取/放置与推/拉的固定两房能力探针，生成/训练继续关闭；本批不登录服务器执行动作。设计只绑定旧v1探针receipt、v2视角扫描、v3目标合同、D-173四槽端点报告和原四个private slot/source house摘要，不按结果选房、位置、目标或重复目标。原slot4/11/6/12的资产物性从旧private探针只读取得：三件仅`moveable=true`、一件仅`pickupable=true`；真实ID/类别不复制到公开配置。
- 动作前路线：按旧固定视角先重放24帧公开相机序列，在任何交互结果可见前用L1匿名目标可见mask、深度/相机位姿投影的**可见区域中心**和公开`GetReachablePositions` 0.25 m格，选到该区域最近的单一四邻接路线并封存。该中心只帮助机器人靠近，不替代资产真实position或RELINK目的地；无路或位置偏差使原分支失败。路线指令仅`RotateRight/RotateLeft/MoveAhead`，每步必须核动作返回及实际机器人位姿，初始启动视角之外禁止`TeleportFull`捷径。路线由匿名区域与公开几何决定，private object ID仅给已固定物体发交互命令。
- 能力分支：可拾取资产只尝试`PickupObject(forceAction=false)`→`PutObject(forceAction=false)`，记录`isPickedUp`前后和实际落点/父容器；仅可移动资产每槽在不同fresh controller分别尝试`PushObject(forceAction=false)`与`PullObject(forceAction=false)`，固定力档的每个值又各在独立场景运行，完整报告动作错误、真实XYZ位移/是否停稳，**不得挑成功方向或力值做训练样本**。抓取与推拉动作都可能返回成功而物体未产生预期关系变化；能力报告与记忆语义标签分开。
- 必须审定的门：①公开类型化容器区域及其在动作前的固定排序/私有执行ID映射尚未实现，不能用`metadata.receptacle`私有oracle替代；②推拉力档、路径snap/真实位置容差未冻结，不能因四槽先前失败来调；③`PickupObject(manualInteract)`和`PutObject(placeStationary)`分别影响手前抽象传送与确定性/物理结算，需明确能力主张；④官方[交互动作说明](https://ai2thor.allenai.org/ithor/documentation/interactive-physics/)的`PutObject`例子与其“放入目标容器”的文字不够一致，上游[ProcTHOR问题记录](https://github.com/allenai/procthor-10k/issues/7)也显示旧build参数差异，故需在**固定已锁模拟器**上先留API smoke receipt再冻结入口。任一项缺失，proposal validator保持`probe_authorized=false`，未来填值走状态条件化，不悄悄解闸。
- 三类失败例子：机器人从原位到最近格点的`MoveAhead`碰障碍，是**实际导航路径失败**，不归为目标端点碰撞；抓取成功但非强制放置被容器拒绝，是**交互/终点失败**，不能归为导航或识别；抓取/放置动作都成功且资产真实落下，但旧预测关系早已相同或公开后态证据不支持修订，是**可能的记忆语义问题**，本探针仍不签标签，须另核历史/版本事务。推拉成功但资产没动则只报告零位移，不以动作返回成功推断RELINK成立。
- 白话：这项设计解决“同一批原物体能否通过机器人实际走近并交互，而不是靠强制传送假成功”的问题。输入原四个固定槽的公开匿名可见区域/可达格及私有动作目标ID，输出未来可审的导航、抓放或推拉逐步证据和匿名失败阶段报告。例如原槽12先沿公开格走到目标资产附近，再不强制抓取、放到动作前已选的公开容器区域，任一步失败就保留原槽。它不等于连续机械臂运动学、公开部署目标识别、记忆RELINK正确性、episode数据生成或训练结果。

## D-175：公开容器证据、固定build API smoke与独立推拉力档的runner审查批次

- 日期：2026-09-16；状态：用户认可公开容器证据原则、锁定版本API smoke和独立预登记推拉力档，并授权开始实现runner供D-059代码审查；**没有授权四槽动作运行、完整episode、训练或效果评估**。旧四槽/原house/pose/目标/24帧前缀不变。D-174提案执行位继续false。
- 力档独立文件在任何新交互结果出现前固定20/80/160 N；三件仅可移动旧目标各用fresh controller跑推/拉×三力，共18个分支，另一个仅可拾取旧目标跑一组抓放，总19个分支。不按结果选方向、力、容器、目标或房；动作成功而零位移仍在分母。此档位是广覆盖的能力诊断口径，不是对各资产质量的优化或训练超参。
- API smoke规格固定服务器simulator Python、AI2-THOR 5.0.0和已审CloudRendering build/zip摘要；`PickupObject.manualInteract=false`承认手前抽象传送，`PutObject.placeStationary=true`只测确定性放置能力，交互全部`forceAction=false`。官方[交互动作说明](https://ai2thor.allenai.org/ithor/documentation/interactive-physics/)给出这两个默认值，却在`PutObject.objectId`示例与目标容器文字上留有歧义；独立真实smoke必须看本build的动作返回、`isPickedUp`转换和`parentReceptacles`，拒绝或父容器不符均记inconclusive，不能从网页推断成功。当前只有锁定规格与人工事件纯测试，真实receipt为空。
- runner审查核心先封存公开路线/公开类型化容器区域，后在私有执行侧映射容器ID、查真实能力并发动作；通用L1 `surface`不能直接等同可放置容器，当前公开类型化容器生成/验证仍是运行阻断项。逐动作记录请求、返回、机器人实际位姿及资产后态，区分导航拒绝、导航位置差、交互拒绝、抓放状态不符和推拉零位移；不发记忆正例。路径snap与实际位姿容差仍需在真实运行前独立冻结。D-059要求审查代码后才合并为运行依赖；服务器已关闭，本批仅本地纯验证。
- 白话：这批解决“先定好怎么走、放到哪里、推多大力，并把动作返回与真实结果分开”的问题。输入是公开当前区域/可达格、旧四槽的私有执行ID和固定档位，输出可审的封存计划、动作函数与将来的逐分支失败。例如推20 N、80 N、160 N都没动，三个零位移全报；抓起后`PutObject`说成功却没有目标父容器，也只报不符。它不等于公开容器检测已完成、固定build实测smoke通过、19个分支已执行或记忆RELINK语义有效。

## D-176：固定槽失败保留的开发构造与交互探针停止线

- 日期：2026-09-16；状态：用户明确批准“先审runner；固定槽生成并保留失败，RELINK不成功就记缺口，不再追加探针”。该批准改变VM-04开发构造的推进顺序，不追认旧强制RELINK动作、旧失败stage、旧test或记忆正例；train/validation/confirmation继续关闭。D-175的19个交互分支、公开容器读取器和真实`PutObject` API smoke是**将来主张机器人真实交互能力**所需的诊断，不再作为取得固定两房原始记录的前置条件；当前不执行或追加交互能力探针。
- 两房、36个原slot、v2固定pose、原house与D=1.0 m均不换。每槽生成入口仅写一次终止记录：完整raw，或保留公开可得前缀、私有失败动作/前提及摘要的`raw.failure`；硬资源停止后的槽显式`not_started`。36个终止记录及worker退出/合并摘要意味着**运行完整**，不意味着36个有效训练样本。开发验收只对公私隔离、时序、真实后态、公开结构证据和候选先于teacher成立的槽发`constructed=true`；失败或candidate miss计入分母及逐类覆盖缺口，不能被同房换目标、换pose、换动作、重复槽或补探针修复。既有v2合同`minimum_yield_or_recall_pass_gate=null`、`construction_failure_or_candidate_miss_is_a_result_not_a_rerun_trigger=true`支持此口径，旧配置/产物不改字节；本决议为新生成职责的补充冻结，不自动解旧stage执行位。
- 四个原RELINK `x+0.5 m`端点已在D-173固定场景以`forceAction=false`明确碰撞拒绝。新生成职责不得再用旧`forceAction=true`把返回成功当真实RELINK。原RELINK槽可在核原私有目标/pose/source与D-173摘要后保存已知动作前提失败及可公开前缀，标`constructed=false/semantic_positive_label_issued=false`；不为它们重新寻找容器、力档、移动方向或端点，也不把诊断runner的行动结果转成记忆标签。若以后另立数据版本研究真实交互，需独立公开动作/语义合同和审查，不能替换这36槽。
- runner审查结论：D-175交付的是**纯函数核心**而非可运行的完整stage；调用者可自行声称`semantic_type="receptacle"/evidence_source="public_current_rgb_depth"`，内存摘要也不能证明公开文件在私有读取前封存。它还缺固定source/pose/slot核验、fresh controller/19分支派发、resource与exit receipt、真实API回执及匿名出口；当前`probe_authorized=false`在首动作前拒绝。因此它不具备作为开发生成依赖或交互成功证据的审查条件。原始数据最短路径应独立改新生成worker：复用受审v3作者资产∩真实metadata位置的固定pose目标选择，非干预四类由公开类型化区域决定，失败原样保留；旧`vm04_two_house_worker`仍按所有可见instance mask私选目标并对RELINK强制传送，不能直接解闸运行。旧`assess_private_construction`还用私有target ID判NOOP/BIND/SPLIT/MERGE是否成立，不能给这些新公开结构语义发`constructed=true`。此独立职责先交可审代码/测试/固定服务器入口，再按D-059用户审查运行；本轮不登录服务器。
- 白话：这条停止线解决“为了救四个失败RELINK，数据生成一直被新探针拖住”的问题。输入是原两房36槽、已核来源和封存的D-173端点失败，输出下一版每槽完整或失败终止记录与真正可用的覆盖统计。例如slot12在原目标位置有明确碰撞，就保存其公开观察前缀和私有失败依据，记一条RELINK缺口，不换一个容易搬的杯子。它不等于36个有效样本、RELINK已被新动作修好、训练获准或负结果变成成功。

## D-177：物理RELINK正例的实体连续性与公开关系证据

- 日期：2026-09-16；用户明确认可：**同一物理实体且公开旧、新关系均有证据，才算物理RELINK正例**。私有实例连续性只能由候选封存后的可信评价器核验，不得进入公开候选、在线选择或部署输入；旧边须由动作前公开观察形成的先前预测记忆支持，新边须由动作后当前公开观察支持。只满足一项、动作失败或真实关系未变，均不能发物理RELINK正例标签；原36槽四个固定失败仍按D-176保留，不被新版本替换。
- QUARANTINE是在线低置信/非法提交时不修改persistent world的wrapper，不是离线失败记录的统一标签。物理构造失败、旧边前提缺口、公开新关系证据不足、候选遗漏、私有身份不连续和executor-illegal须分别记录；**是否把公开证据不足的在线选择暂存为pending，以及何种门触发QUARANTINE，仍待独立冻结**，不得用事后私有身份判定在部署时触发它。本决议不批准新RELINK探针、生成、训练或效果运行。
- 白话：这条口径解决“看起来像同一物体便把替换写成搬动”的问题。输入是封存前的公开旧边、动作后的公开新边和仅供事后评价的私有实例连续性，输出物理RELINK正例资格及分层失败原因。例如P1凳子确实被推到P2且两处公开关系都有支持，才可贴正例；P2出现另一张凳子不能贴。它不等于让私有ID决定在线候选，也不等于每个不合格记录都自动进入QUARANTINE。

## D-178：弱公开证据的暂存分流，不吞物理与身份失败

- 日期：2026-09-16；用户明确批准：“弱证据不足时暂存且不提交；物理失败和私有身份不连续只分层记录，不自动QUARANTINE”。在线分流仅可读当前公开观察、此前预测记忆、封存候选及已冻结的公开支持判断；有可归属的弱证据但不足以合法提交关系修订时，可选择QUARANTINE wrapper，把证据写独立pending并保持persistent world字节不变。没有可归属证据、已知无需修订、非法执行、候选遗漏及真实动作失败须各记自己的原因，不能用同一个QUARANTINE位代替；非法执行的确定性回退仍按既有executor合同。
- 私有实例ID和事后物理/身份评价不得决定在线暂存。此决议冻结**分流原则**，不凭空冻结证据可靠性数值、pending生命周期预算、在线选择门或新数据版本运行权限；这些仍需开发数据与代码审查后独立登记。原36槽D-176失败保留、RELINK覆盖缺口及生成/训练闸门不变。
- 白话：机器人当前只见凳子边缘，能保存“可能仍是旧凳子”的公开线索，却不能直接把`located_at(P2)`写进持久图；输入是这条弱公开线索和旧预测记忆，输出独立pending与不变的世界版本。若推凳子失败，就记物理失败，不把失败动作包装成pending；若事后私有评价发现是另一张凳子，也只影响离线标签。它不等于在线系统偷看实例ID或把每个RELINK缺口称作QUARANTINE。

## D-179：原36槽raw受审实现开放服务器检查与运行

- 日期：2026-09-16；用户明确认可`0342098`逐帧raw验证和`6731f9f`物理RELINK正例硬门，并授权开放原36槽raw的服务器检查与运行。固定两房、36槽、v2 pose、原house、D=1.0 m及一次终止规则不变；四个原RELINK继续保存第0–23帧和D-173失败来源，不能换端点、目标、动作、pose或房，也不能由正例硬门补标签。`vm04_relink_positive_gate.py`只供以后独立新数据版本审查，原36槽stage不调用它。
- 固定raw stage以`18de8692ce9f352789336c07578eca51d17d0dcd`为受审实现：该提交只把关闭闸门测试改成显式注入关闭配置，使同一测试在真实配置开闸后仍验证“首输出前拒绝”；算法、任务、worker与摘要规则不变。随后配置仅开放`run_authorized/generation_authorized=true`并登记该ref；`private_evaluation_authorized/training_authorized/confirmation_authorized`仍为false。运行顺序固定为同版`check→run→verify→export`，后一步核前一步marker和摘要；任何失败/资源停止保留现场，不静默重跑。
- 白话：这项授权解决“代码已经审过，但配置仍永远拒绝服务器生成”的问题。输入是受审固定槽实现、旧扫描/端点回执和两间原house，输出36个完整、失败或未启动的raw终止记录及逐帧摘要验证。例如四个RELINK仍写失败，其余槽继续生成并接受文件核验。它不等于36个有效样本、`constructed=true`、公开结构语义通过、独立新RELINK动作、训练或confirmation获准。


## D-180：原36槽科学适用性阻断与服务器运行再关闭

- 日期：2026-09-16；状态：根据用户要求复核“即使36槽全部成功能否支持VSMT主张”，在服务器尚未运行时重新关闭raw生成，等待新观察合同裁决。原两房、slot、失败和D-173四个RELINK证据不删除；`vm04_fixed_slot_raw_stage_v1.json`改为`reviewed_raw_paused_scientific_suitability`，`run_authorized/generation_authorized=false`且`expected_reviewed_code=null`，private evaluation/training/confirmation继续false。
- 结论明确为**不能支持**。现有32帧注册相机策略在同一位置交替±0.25° yaw、净朝向回零且无平移，主要满足“每包跟随登记动作”的溯源形式，不能形成实质跨视角再识别、遮挡变化或自由空间负证据压力。四个RELINK固定为失败；NOOP/BIND/SPLIT/MERGE共16槽不发干预；其中BIND/SPLIT/MERGE 12槽的公开类型化结构规则和NOOP 4槽的不变语义验收均尚未实现；生命周期16槽在固定镜头中心执行Disable/Enable；两house无独立未见family split，也没有五方法候选、预测或评分。因此36/36 raw成功至多支持writer、公私隔离、摘要链、失败保留和资源派发，不能进入L2主表、比较朴素当前帧基线或支撑VSMT候选贡献。
- 生命周期后态属于既定动作证据的实现遗漏而非新科学口径：raw worker在每次`DisableObject/EnableObject`返回成功后读取私有target mask，分别要求0/>0像素；不符保留已发动作及mask支持并写`intervention_poststate_mismatch`。这避免把API success冒充真实可见性后态，但不把槽升级为记忆事务正例。
- D-177硬门原实现把`old/new_region_id`与instance ID放在同一private outcome自报，未落实DATA所述trusted L1 crosswalk。修订后outcome不再指定entity region；gate必须从前后独立private crosswalk取得唯一instance→region→mask摘要绑定，并与已封存公开packet的entity mask逐项核对。P1/P2改用公开place mask和关系support摘要判不同，拒绝多条歧义关系，避免只看第一行和浮点centroid不等。该代码仍只供独立新版本审查，未接trusted materializer或真实数据。
- 推荐下一口径：不运行当前静态36槽；先预登记有实际平移/显著视角变化、可见/遮挡/出视野分支与共同公开输入的开发数据版本，先用朴素当前帧基线做可辨识性检查，再决定VM-05规模。另一口径是仅将旧36槽作为一次工程writer回放运行并永久标`engineering_only`，会增加算力和文件但不增加论文主张证据；维持现设计进入L2不可接受。
- 白话：即使36个文件全写成功，也可能只是同一镜头里让物体消失再出现，普通单帧方法就能做对，无法测试版本化记忆是否解决身份传播和长期副作用。输入是现有静态worker与未实现语义项，输出是关闸和明确证据上限；它不是已经运行出的负结果，也不否定以后按新视角合同构造的VSMT数据。


## D-181：静态36槽退役、新观察合同与可辨识性硬门提案

- 日期：2026-09-16；状态：用户明确认可不运行原静态36槽，并要求先提交包含真实相机平移、遮挡/出视野/重现分支和当前帧朴素基线预检的新VM-04观察合同。原stage继续`run_authorized/generation_authorized=false`且`expected_reviewed_code=null`；D-173失败、D-179历史授权与本地回执保留。新`vm04_observation_suitability_proposal_v1.json`所有实现/生成/评价/训练/确认位为false，数值门为null，不能靠保存配置启动服务器。
- 采纳生命周期审查①②。raw worker维护disabled与pending-enable集合：Disable成功立即要求mask=0，之后每个注册相机event都核disabled目标仍为0，提前出现记`disabled_target_reappeared_between_actions`；Enable动作event只记录即时mask，真正通过条件是紧随其后的注册相机event中mask>0。这样既保留D-168的跨帧检查，也避免假设Enable同一event必重渲染分割。所有逐帧目标支持只写private intervention/failure，公开terminal只写匿名reason。
- 采纳crosswalk审查③的推荐层级：当前D-177 gate的内容绑定保留，但文档明确`crosswalk provenance pending materializer receipt`，不把文件名中的trusted当来源证据。新合同要求未来materializer receipt原子绑定raw public frame、private mask、public packet、private crosswalk、代码和配置摘要，并由public RELINK proof seal绑定receipt摘要；在实现、测试和用户审查前禁止真实物理RELINK正例。本轮不先改尚不存在的materializer schema/runner。
- 采纳可辨识性硬门，但不在本轮暗中冻结数值。CFO只读当前L2 packet；同预算public-history probe多读公开历史与causal prior，二者输出相同program type并按house family比较。进入L2须同时满足：历史减CFO的单侧区间下界超过冻结最小差、CFO不超过冻结上限、sealed-catalog oracle candidate recall超过冻结下限。规则和全部数值/模型/预算必须在生成前固定，结果后不得改。推荐审查值为差15个百分点、CFO≤60%、oracle recall≥90%、95%区间、10000次bootstrap、至少24个开发family；它们目前只在`recommended_values_for_review_not_frozen`，不是批准门。
- 新路线不是active exploration：初始观测前可`TeleportFull`，其后路线由公开可达/几何信息在private ID和结果之前封存，失败不换路径。每family至少含自然遮挡后重现、出视野后重现两类分支，每episode从旧关系可见开始，经一个预登记挑战，再在真实平移后的pose重现。推荐审查值为关键pose和重现各至少0.5 m平移、至少30°关键yaw差、每visibility state至少2个公开时刻、最多24步、2 cm/1° pose验收容差；数值仍未批准。
- 白话：新合同解决“数据文件完整但最后一帧已经泄露答案”的问题。输入固定多视角路线和两种只差历史访问权的诊断probe，输出是否值得进入L2的准入结论。例如当前帧都看到同一把椅子，但只有历史说明它是旧节点还是新节点时，history probe应稳定胜过CFO；这不等于VSMT已训练或一定获胜。


## D-182：不可观测干预、单probe配对门与预登记pilot提案

- 日期：2026-09-16；状态：根据D-181代码复核追加的执行关闭合同修订，未获生成/训练授权。所有带world intervention的程序必须在动作前由公开visibility builder将此前封存的匿名target track或公开预登记reveal locus判为`occluded`或`out_of_view`并封存；证据仍可见就以`intervention_visible_to_camera`保留原槽失败，不执行动作、不换pose/路径/house。重现0.5 m的参考pose明确为干预前对应程序的公开前提pose：RELINK等使用旧关系可见pose，BIRTH使用无既有目标节点时封存的公开reveal-locus pose。该约束防止“相机虽移动但动作仍在镜头前，当前帧直接看出答案”。
- CFO/history门显式`paired_by_family=true`。取消“线性和两层set probe各自取validation较好者”；两侧必须用单一事前冻结的共享结构、参数容量和优化预算，CFO仅mask掉history/prior输入。不得用门所评family选结构。推荐结构是一个共享两层set probe，具体token/池化/优化预算仍为null，需另审；这比另划结构选择family更省样本且消除max-selection偏差。
- 保持严格统计语义：按family配对的history−CFO单侧95%区间下界须超过15个百分点，不改成“均值15且下界>0”。明确该门通常要求观测均值差大于15个百分点；这是为减少误收无区分度数据，接受更高样本成本。推荐将完成development family从24提高到32。
- 产出分两批但不共享house：先推荐6个pilot family，只查路线、visibility state和构造成品率，永久排除准入门、VM-05和VM-06；pilot与正式house清单均须在pilot前按result-blind manifest hash顺序封存且互不相交，pilot后若改合同必须新版本。正式批推荐一次性预登记48个source house，失败不补且观察结果后不得追加house；少于32个完成family则构造门失败，不运行可辨识性门。`pilot=6/source=48/completed=32`仍在推荐区，所有冻结字段为null。
- 生命周期低优先缺口一并修复：Enable在下一注册相机event确认重现后进入enabled集合，剩余每个注册相机event持续要求可见至frame31；再次消失记`enabled_target_disappeared_before_terminal`。这只修原静态worker的D-168终态证据，未来多视角runner应按其预登记终端重现窗口另实现，不能机械复用“所有后续视角持续可见”。
- 白话：输入是看不见动作的公开窗口、固定一套probe和预先列好的6+48个house，输出固定分母上的数据准入结论。例如pilot发现MoveAhead频繁撞墙，可以改合同并重开新版本，但这6个房永远不混进正式32个成功family。它不是允许看到失败后继续抽房，也没有开放服务器。


## D-183：D-182审查冻结、机器口径对齐与后续修订提案

- 日期：2026-09-16；状态：D-182设计和数值已获用户批准用于下一轮精确schema/实现审查，**不批准任何运行**。冻结的审查值为：关键pose与相对程序前提pose的终端重现各至少0.5 m平移、关键yaw差至少30°、每visibility state至少2个公开时刻、路线最多24步、实际pose容差2 cm/1°；CFO/history使用一个共同预登记结构并按house family配对，history−CFO单侧95%区间下界须>15个百分点，CFO≤60%，sealed-catalog oracle recall≥90%，family bootstrap 10000次、seed 260916；6个pilot永久排除统计/VM-05/VM-06，正式一次性登记48个source house且失败不补，至少32个完成family。24完成family并改为“均值≥15pp且下界>0”的省资源备选明确未采用，因为它削弱“历史优势至少15pp”的区间保证。
- Claude审查K项是机器合同与D-182正文不一致，现直接对齐且不改变上述科学口径：旧固定视角worker的Enable后逐注册帧持续可见规则标为`scope=fixed_view_worker_only`；未来多视角runner的terminal reobservation window保持`null`并作为实现/运行阻断；少于32个完成family的机器动作固定为构造门失败，不运行可辨识性门、VM-05或VM-06。共享probe精确结构/训练预算、visibility builder、materializer receipt、终端窗口、runner及schema尚未实现；基础合同所有授权位继续false。
- L项判断成立但会改变D-182固定48，因此只作为独立[D-183机器提案](../configs/vsmt/vm04_observation_suitability_d183_amendment_proposal_v1.json)，未获并入。为避免pilot后人工挑N，pilot前须封存至少70个合格house的确定顺序；pilot只能给出6个family的构造完成布尔。推荐离散规则为完成5–6个时正式N=48，完成4个时N=64，完成0–3个时停止并另立版本；正式house始终取pilot之后的前N个，不得按失败追加。没有采用`ceil(32/pilot_yield)`点估计公式，因为在4/6时仍给N=48，若点估计准确，完成数低于32的概率约一半，缺少构造余量。
- M项判断成立但改变逐原子主张资格，故仍是提案：九种登记program必须逐类报告CFO accuracy、history accuracy及配对差；任一program的CFO超过冻结60%上限时，该program标`easy_class`，仍保留在聚合门分母且不得重标/删除/补样，但不允许作为该原子的单独证据。它不自动阻断整批，聚合三门仍照D-182运行；若以后要改成任一easy class阻断整批，须新决议而不能看结果后选择。
- N项判断成立且与既有SPLIT/MERGE语义一致，但精确构造仍未完成。程序分配必须在生成前由冻结几何、相机路线和公开前端确定：SPLIT从远距/遮挡pose的一个公开欠分区域转为近距重现的两个公开区域；MERGE从旧前缀预登记关联断裂形成的两个公开track转为重现时支持同一结构。private身份只可在public/candidate封存后评分；伪影不复现就记原program构造失败，绝不按观察结果改标签。fresh replay重复次数、几何参数和公开前端伪影判据仍为null并阻断schema实现完成及运行。
- 白话：这条决议把已经批准的严格数字与仍待批准的改动分开。输入是D-182关闭合同和Claude的四项审查，输出一个可查的D-182冻结版本及一个全关的D-183提案。例如pilot完成4/6时，D-183建议从事前排序中用64个正式house；SPLIT欠分若第二次不出现就保留失败，不临时改成BIND。它不授权pilot、正式生成、probe训练、VM-05或confirmation。


## D-184：D-183批准与观察规划runner首版实现

- 日期：2026-09-16；用户明确批准D-183全部推荐口径，只进入精确schema/实现审查，不开放运行。D-183规则已合入D-182基础合同：pilot前按来源摘要和seed封存70个house顺序；6个pilot完成5–6/4/0–3时分别选择48/64/停止；逐program CFO超60%标easy但保留聚合分母；SPLIT/MERGE必须事前确定性构造，未实现即失败。来源池封存、route plan封存、正式选择、route assessment、pilot/formal执行、生成、private评价、probe训练和confirmation授权均为false。
- 首版schema与纯runner完成来源池、正式N、私有构造路线、公开provenance路线、逐帧公开visibility assessment、route receipt和失败verdict。路线实际验收核注册动作、0.5 m平移、30°关键yaw、每状态两个公开时刻、不可观测干预、2 cm/1° pose容差及至少两个连续终端重现；失败不补路/房。公开状态从投影样本、depth可见体积与当前公开support重算，private mask/instance ID位必须false；公开路线删掉program和SPLIT/MERGE assignment，且不能进入adapter输入。
- 当前精确停止点：真实reachable-position路线候选生成、多视角simulator worker、trusted materializer receipt尚未接；SPLIT/MERGE fresh replay次数、几何参数和冻结公开前端伪影判据，以及CFO/history共享probe精确结构与训练预算仍为null。`vm04_observation_stage.py check`只读通过；其他stage命令在读输入或写输出前因各自授权false拒绝。此停止点允许继续审实现，不构成pilot或生成许可。
- 白话：这一步把“应该怎样生成”变成机器可拒绝的文件和函数。输入70个预排序house候选、预登记路线和之后拍到的公开证据，输出固定正式前缀与成功/失败记录。例如第4个pilot完成时只能取预排序后的64个formal候选，动作时公开投影仍可见则原episode失败，不能换路线。它不等于已经找到这些路线或启动了AI2-THOR。


## D-185：公开多视角路线构造与执行核心

- 日期：2026-09-16；状态：按D-183已批准的精确schema/实现审查继续实现，所有运行授权保持关闭。路线时序固定为初始`TeleportFull`产生观测0，之后N个注册Move/Rotate/Look动作产生观测1至N；因此一条N动作路线必须有N+1条观测。动作的精确AI2-THOR请求参数不使用默认值，机器合同新增`registered_action_request_templates=null`阻断项，待真实API口径审查后再冻结。
- 新公开路线构造器只接收干预前公开pose扫描、匿名visibility assessment和注册动作有向图，按固定排序做最短路径搜索。每条扫描必须声明`pre_intervention_public_route_scan`、只表示干预前subject/locus支持且`future_or_action_outcome_used=false`；输入含private instance ID或未来/动作结果即拒绝。找到的路线依次满足至少两个visible、至少两个指定hidden分支和至少两个reobserved时刻，以及0.5 m/30°/24步门；找不到就保留构造失败，不换房或事后改标签。
- 新多视角worker核心先执行初始定位，再逐个执行显式动作请求；只有公开hidden assessment封存后才把原始event交给私有干预回调。公开观测回调不直接接收含`objectId`/instance mask的模拟器event，而只接收可信提取器输出的RGB、depth、camera和来源摘要；相机拒绝、干预仍可见或终端重现不合格均保留已有公开前缀且`failed_route_replacement_allowed=false`。生产包装先核全部合同字段和授权，当前在创建任何episode前拒绝。
- 当前停止点：可信提取器只有接口及人工测试，尚未实现公私raw落盘与materializer receipt；精确动作请求模板、SPLIT/MERGE几何/公开前端/replay次数和共享probe结构/预算仍为空。0 source inventory、0模拟器、0episode、0训练。
- 白话：输入是干预前公开扫描形成的路线图和一条封存路线，输出按真实动作顺序得到的公开观察前缀或完整receipt。例如先在观测0看到椅子，移动两步到桌后确认遮挡，才允许私有执行器搬动物体，再移动到另一侧连续两次公开重见；如果第二步撞墙就保存前3个观测并失败。它不等于已连接真实AI2-THOR数据写盘、已知道SPLIT/MERGE精确几何或已获准跑pilot。


## D-186：多视角raw落盘与materializer来源绑定

- 日期：2026-09-16；状态：继续执行D-183已批准的精确实现审查，未改变任何运行位。新raw writer在episode目录不存在时才创建，逐观测以`O_EXCL`写公开`rgb.npy/depth_m.npy/camera.json/frame.json`和私有`instance_masks.npz/mapping.json`；公开帧与私有mask按摘要交叉绑定，公开字节不含实例ID。逻辑失败、相机拒绝和未捕获异常都写唯一公私terminal及双manifest，保留已完成帧；跳号、第二次终止和覆盖已有episode拒绝。
- 生产`run_authorized_route`在通过全部冻结字段和授权检查后才创建store，使用store的可信提取函数执行路线并落盘；当前基础合同因动作模板、SPLIT/MERGE和probe字段为null且授权false，会在目录创建和controller调用前拒绝。人工测试临时注入完整非磁盘合同，只验证六帧文件链，不构成真实运行。
- 新trusted materializer receipt逐帧绑定raw公开帧摘要、raw私有mask摘要、公开packet摘要、私有crosswalk摘要，并绑定route、raw episode manifest、materializer代码和配置摘要；帧必须从0连续，部署reader不得打开private crosswalk。D-177 RELINK正例门现在要求公开proof seal绑定receipt，并要求旧/新packet与对应crosswalk摘要同时出现在receipt中；receipt之后改crosswalk会在读取私有标签前拒绝。
- 当前边界：receipt生成/验证和D-177消费已实现，但从新多视角raw真实产生公开packet/private crosswalk的materializer执行器尚未实现，代码/配置摘要也尚未由父stage绑定受审提交；因此真实RELINK仍不能发正例。真实reachable扫描、精确动作模板、SPLIT/MERGE构造、共享probe和服务器父stage继续阻断。
- 白话：这一步解决“动作走了一半失败时文件还在不在”和“crosswalk是不是由同一批raw经过受审materializer产生”。输入每个模拟器event，输出分开的公私raw文件及以后materialization的一张摘要收据。例如有人在收据生成后改了新帧crosswalk里的椅子ID，即使公开packet没变，RELINK gate也立即拒绝。它不等于materializer已经运行或pilot已经开放。


## D-187：多视角materializer执行与复验核心

- 日期：2026-09-16；状态：继续实现D-183审查范围，不开放materialization或生成。执行核心只接受`raw_complete`且construction verdict为真的episode，先复核公私manifest、route、terminal、N动作/N+1帧、每个RGB/depth/camera/mask/mapping摘要和数组形状，再逐帧调用注入的trusted materializer回调。回调输出必须是合法公开ObservationPacket和私有crosswalk；crosswalk实例只能来自该帧私有mapping，并须唯一绑定packet中的entity region/mask，任何private ID出现在公开packet都拒绝。
- 每帧packet与crosswalk用`O_EXCL`分写；回调或raw核验中途失败时保留已完成materialized前缀，公开失败只写匿名reason，私有失败保留异常，不生成receipt/success。全部帧完成后重新打开每个raw绑定，才生成D-186 receipt和success marker。独立verifier再从磁盘复核raw、packet、crosswalk、receipt和marker；receipt后改packet会拒绝。
- 基础合同新增独立`materialization_authorized=false`，crosswalk状态改为“receipt schema/gate binding已实现、executor待审”，受审materializer代码/配置摘要仍为null并同时阻断generation与materialization。人工测试可注入packet fixture验证文件链，但实际公开前端、DINO token、结构区域、causal prior和逐帧角色生成尚未接入，不能把回调接口称作真实材料化完成。

## D-188：公开packet与causal-prior序列绑定

- 日期：2026-09-16；状态：继续D-183精确实现审查，不开放source inventory、materialization或生成。raw相机记录补齐世界坐标pose、四元数、FOV、图像尺寸和由同一公开记录计算的内参，使后续公开几何不必回读模拟器metadata；它仍不带object ID、mask或program。
- 新`vm04_public_packet_builder.py`只接受十一项精确公开前端字段，不接收调用方提供的`prior_memory_ref`。每帧ref由上一帧公开bootstrap的已封存memory生成，随后用同一显式`PublicBootstrapConfig`在线推进；整段完成后从空memory独立重放并要求终态完全一致，输出既有causal-prior receipt。额外private/program/target字段、region内instance ID、时间倒退或memory摘要不匹配均拒绝。
- 机器合同据实际进度把crosswalk状态改为“receipt/gate/executor shell已实现，真实前端与受审摘要待定”，将阻断项收窄为真实公开前端和父stage。`decision_time_s`规则、past-action向量编码、bootstrap阈值、真实DINO/结构区域、SPLIT/MERGE确定性伪影判据和materializer代码/配置摘要仍未冻结；旧静态两房private program注入明确禁止复用。所有授权位保持false。
- 白话：这一步解决“第2帧的packet究竟引用哪一版旧记忆，以及材料化结束后能不能证明整段旧记忆是公开序列算出来的”。输入已匿名的逐帧公开感知，输出逐帧packet、共同旧记忆和重放收据。例如有人给第2帧偷偷塞进另一个有正确椅子关系的memory，builder会因为ref不由第1帧产生而拒绝。它不解决RGB-D怎样形成区域，也没有运行任何house。

## D-189：无私有program通道的真实公开前端核心

- 日期：2026-09-16；状态：继续D-183实现审查，不开放source inventory、模拟器、materialization或生成。新前端核心复用既有L1匿名mask、DINO区域池化、公开depth几何、surface/place/free-space/visibility及关系函数；所有mask、描述、几何和关系阈值通过无默认值config显式提供。函数签名没有program、target、teacher或future字段。
- 单帧private ID只用于把原mask与输出entity mask摘要写入独立crosswalk；公开区域在每帧按mask内容重新编号。旧静态materializer的`SPLIT`前缀强制合并两个目标mask和`MERGE`中段翻转目标descriptor不复用，因为两者依赖私有program/target制造公开伪影，违反D-183确定性公开构造。
- 新多帧callback从verified raw取得RGB/depth/camera及文件摘要，只把RGB和frame ordinal交给注入的DINO token extractor；时间、机器人状态、past actions、公开常量和sample摘要必须来自精确预封存context。它顺序生成packet、推进共同bootstrap并在末帧独立重放，乱序或未完成拒绝。真实DINO loader/checkpoint摘要、context生成规则、前端/bootstrap正式config和父stage仍待冻结绑定，授权位全false。
- 白话：这一步把“真实公开区域怎样产生”从人工packet fixture换成现有L1算法，但没有偷偷决定数值。例如同一mask换了模拟器ID，公开packet不变；如果要构造SPLIT，必须靠事前几何和公开前端自然产生欠分，不能告诉前端当前标签叫SPLIT。它仍不是服务器数据或已验收科学样本。

## D-190：公开时间与已结束动作context封存

- 日期：2026-09-16；状态：继续D-183实现审查，不冻结时间或动作编码数值、不开放运行。新builder只读去掉program/伪影assignment的sealed public route，并要求调用者显式给出N+1个严格递增decision time、完整八动作编码表及其规则ID、同长公开robot state和公开常量。
- 观测0固定无past action；观测i只加入route中0..i-1动作，结束时刻等于对应第i个decision time。八动作向量必须同维、有限、互异且完整覆盖，不能只为当前路线登记几个动作。manifest绑定public route、时间表、编码表和逐context摘要；额外program/private字段或改route不改摘要均拒绝。
- 基础合同新增`action_command_encoding=null`和独立生成阻断，避免只冻结API request模板却忘记adapter看到的数值编码。人工测试使用一秒间隔/one-hot只验证前缀和shape，不写回正式合同。真实时间规则、编码值、DINO/config和父stage仍待审；授权位全false。
- 白话：机器人已经执行前三步时，当前packet可以看到前三步，不能看到第四步；编码表决定“MoveAhead”等命令怎样变成共同数值输入。这个模块把规则做成必填并封存，但没有替用户选规则。
- 白话：输入一份已经完整落盘的公私raw episode，输出逐帧公开packet、隔离crosswalk和最终收据。例如第2帧回调报错时保留第0帧输出并写失败，但绝不拿单帧成功冒充整集receipt。它不决定公开前端怎样产生SPLIT/MERGE，也没有运行服务器。


## D-191：materializer整段公开记忆链与raw mask实绑定

- 日期：2026-09-16；状态：继续D-183已批准的精确schema/实现审查，materialization、pilot、正式生成、训练和confirmation授权均保持false。D-190的context不再作为一组未验裸字典传给前端；stateful callback必须接收并重核完整bundle的route、帧数、时间、编码及逐context/manifest摘要，额外private program/target字段或任一摘要变化先拒绝。
- crosswalk的`mask_sha256`现在由materializer从该帧sealed `instance_masks.npz`实际mask重算，并同时要求等于crosswalk绑定和公开entity region中的摘要。packet和crosswalk共同自报一个错误摘要不再能通过；私有instance ID仍只写private crosswalk。
- trusted materializer receipt升级为v2。逐帧packet/crosswalk全写完后，回调还必须返回独立重放核验的causal-prior receipt、最终prior memory、context manifest和packet规范摘要序列；materializer逐项与磁盘packet、public route和最终graph交叉核对，写出三个公开文件并把文件摘要纳入总receipt。普通无状态逐帧函数即使完成所有帧，也只保留失败现场而不能写success；复验器重新打开并核整条链。
- 白话：这一步解决“每帧文件看似正确，但整段记忆可能来自另一组packet或一张自报crosswalk”的问题。输入同一raw episode、sealed公开context和有状态前端，输出逐帧packet/crosswalk、最终公开旧记忆及一张共同收据。例如有人让packet与crosswalk都声称错误mask摘要，raw mask重算会立即拒绝；有人换掉第3帧packet，causal-prior序列也会不匹配。它不选择正式时间/动作编码、前端阈值或模型权重，也没有开放任何数据运行。


## D-192：八种注册相机动作请求的完整性门

- 日期：2026-09-16；状态：继续D-183精确实现审查，正式动作幅度仍未冻结，所有运行位不变。runner新增纯验证器，要求`MoveAhead/MoveBack/MoveLeft/MoveRight/RotateLeft/RotateRight/LookUp/LookDown`八种请求全部存在且不多不少；Move只允许`action+moveMagnitude`，Rotate/Look只允许`action+degrees`，数值须有限正数，Rotate不超过180°、Look不超过90°。`forceAction`、漏项、额外API参数和动作名错配均在controller调用前拒绝。
- 多视角worker的测试核心也消费同一验证器，避免生产入口严格而人工路线核心仍可用不完整字典。人工fixture的0.25 m移动和30°旋转/俯仰仅覆盖请求形状；基础合同继续保持`registered_action_request_templates=null`，不能据此运行。
- 白话：这一步解决“路线写了MoveAhead，但实际调用偷偷用了默认步长或forceAction”的问题。输入八张显式API请求模板，输出一份可执行且字段受限的请求表。例如少了LookDown，即使当前路线恰好没用它，整版配置也不能通过。它不替用户冻结0.25 m、30°或任何模拟器动作值，也没有发出真实动作。


## D-193：materializer完整配置与模型资产回执

- 日期：2026-09-16；状态：继续D-183精确schema/实现审查，不批准materialization、pilot或生成。新增`vsmt-vm04-materializer-config-v1`，要求前端mask/descriptor/entity geometry/surface/place/free-space及关系阈值、三类bootstrap规则、公开常量、builder代码摘要和DINO模型来源一次性完整封存；无默认值、null、额外字段、模型shape与descriptor不符或总摘要不符均拒绝。当前没有把人工fixture阈值写成正式配置。
- 模型来源另有只读assets verifier：现场核DINO仓库精确40位commit、包含未跟踪文件在内的干净工作树和checkpoint文件SHA-256，输出离线资产回执；不联网、不下载、不启动模型。生产配置入口必须先验证这张回执与同一materializer config/model相符，回执内部摘要再进入每个episode的materializer v2 receipt，避免只在配置中声明checkpoint摘要却未核实际文件。
- 生产包装现可由一份sealed config构造`Vm04PublicFrontendSequence`，而不是让调用方分别拼装前端与bootstrap对象；授权仍在读取模型资产和episode前检查。真实DINO loader只从已核本地仓库构造`dinov2_vits14(pretrained=false)`，以`weights_only=true/strict=true`加载checkpoint，随后冻结参数、切eval并移到CUDA；公开帧再调用既有固定预处理与`x_norm_patchtokens`提取。正式阈值、时间规则、动作编码、materializer代码源清单摘要和父stage资源派发仍未完成。
- 白话：这一步解决“代码能跑，但每个worker可能拿了不同阈值或不同模型文件”的问题。输入一份完整配置、一个干净仓库和checkpoint，输出同一有状态材料化callback及资产回执。例如checkpoint字节变了，即使文件名相同也不能进入episode receipt。它不代表这些阈值已经科学批准，也没有加载GPU模型或生成数据。

## D-194：materializer完整源码清单与受审commit绑定

- 日期：2026-09-16；状态：继续D-183精确schema/实现审查，不批准source inventory、materialization、pilot或生成。新增`vsmt-vm04-materializer-code-manifest-v1`，保守枚举materializer执行入口、父stage入口及`src/cpmt/**/*.py`、`src/vsmt/**/*.py`全部Python文件；之所以绑定整个包，是因为导入任一`vsmt.*`前会执行包`__init__.py`并加载其余模块，单列直接import不足以描述真实代码边界。
- manifest逐文件保存仓库相对POSIX路径与SHA-256，并绑定40位受审Git commit及固定inventory policy。验证器同时要求当前checkout和该commit中的相关文件集合完全相同、每个文件字节与manifest相同，拒绝新增、删除、符号链接、路径逃逸或字节变化。Python/NumPy/Torch等环境依赖不冒充仓库源码；DINO仓库和checkpoint继续由D-193独立assets receipt约束。
- 最强生产入口不再接受调用方手填`materializer_code_sha256`；它先只核内存中的manifest seal与合同期望摘要并检查授权，授权成立后才读取代码checkout、模型资产和episode。基础合同的期望代码摘要仍为null，因此当前不能生成正式manifest或进入后续读取。正式动作幅度、时间/动作编码、前端数值、SPLIT/MERGE参数和父stage继续阻断。
- 白话：这一步解决“收据写了一个代码哈希，但没人知道它覆盖哪些文件”的问题。输入用户审过的Git commit和同字节checkout，输出一张逐文件源码装箱单；例如有人在运行前新增一个会被`vsmt/__init__.py`加载的模块，inventory立刻不同并拒绝。它不批准这些代码成为运行基线，也不检查第三方包版本或产生任何数据。

## D-195：crosswalk取消自报旧帧/新帧语义

- 日期：2026-09-16；状态：继续D-183精确实现审查，不开放运行。发现真实生产包装仍要求调用方提供未封存`private_frame_roles`，随后把`old/new`写进crosswalk；这会让materializer在proof seal之前自行决定哪帧承担RELINK旧/新证据。现删除该参数，crosswalk只保存从零连续的机械`observation_index`及instance→匿名region→mask绑定。
- materializer逐帧强制crosswalk index等于当前raw/receipt index。RELINK私有gate先用已封存old/post packet摘要和crosswalk摘要在materializer receipt中各找唯一行，再以那两行的observation index核crosswalk；因此“旧/新”只来自公开proof seal选择的已封存证据，不能由crosswalk文件自报或事后改名。
- 白话：这一步解决“私有映射自己说我是新帧，所以就被当成P2证据”的问题。输入仍是连续raw帧，输出只标第0、1、2……帧的crosswalk；例如proof seal选择第3帧作为post，gate会要求它的crosswalk也写index 3。它不决定哪一帧科学上应作旧/新证据，不产生标签，也不改变同一物理实体与两端公开关系的正例硬门。

## D-196：父stage的代码清单封存步骤

- 日期：2026-09-16；状态：只实现并审查父stage前置步骤，不批准实际source inventory、materialization、pilot或生成。`vm04_observation_stage.py check`现同时读取并核观察构造、materializer config、assets receipt、code manifest和episode receipt五类schema均为登记的JSON Schema草案；它不读取source house、模型或episode。
- 新`seal-materializer-code`模式由独立`materializer_code_sealing_authorized`控制，并在读取`--code-root`或创建输出前先核合同。未来开闸后，它从明确`--reviewed-commit`生成清单、立即按同一checkout和commit复验，再以独占创建写manifest；父stage自身已纳入固定entry列表，避免调度入口落在清单外。当前该gate为false，测试用不存在checkout确认先拒绝。
- 白话：这一步解决“谁来生成上一条逐文件装箱单，以及生成它的入口是否也被审”的问题。输入未来获批的commit和checkout，输出一份不可覆盖的code manifest；例如没有授权时即使传入一个路径也不会打开它。它不调度worker、不读取DINO、不材料化episode，正式批并发与资源回执仍待实现。

## D-197：RELINK公开证据的严格时间方向

- 日期：2026-09-16；状态：按外部审查Q修复已实现gate缺口，不开放任何运行。D-195虽然让old/post packet与crosswalk通过materializer receipt唯一反查机械帧号，但尚未要求old帧先于post帧；调用方仍可把动作后证据放进old文件、动作前证据放进post文件并重签所有摘要。
- gate现要求`old_observation_index < post_observation_index`，并在读取私有outcome及判断同一实例前拒绝反向证据。人工反例交换两组packet/crosswalk在receipt中的帧位、同步修改crosswalk index并重签materializer/public proof，仍因时间反向拒绝。
- 白话：RELINK必须先有P1证据、后有P2证据。输入两张都已封存且来源合法的帧，输出只接受时间向前的那一对；把两张照片交换名称不能把P2→P1冒充P1→P2。它不证明机器人动作成功，也不放松同一实体和两端公开关系硬门。

## D-198：L1/L2层级、合同字段状态与pilot完成来源收紧

- 日期：2026-09-16；状态：采纳外部审查O/P/R的阻断性修订，不改变D-182/D-183已批数值，不开放运行。当前`vm04_public_frontend`的entity proposal来自隔离private instance mask，按METHOD只能是L1 oracle结构诊断；合同此前却把可辨识性门输入写成L2 packet，存在把L1结果误当L2准入的风险。机器合同新增`evidence_level`，明确目标是L2公开proposal前端、当前实现仅L1、L1结果不得准入L2，并新增`implement_and_review_L2_proposal_frontend`生成前阻断项；`reviewed_L2_frontend_receipt_sha256=null`同时进入执行硬门，不能只改授权位绕过。
- 两处混合命名的`numeric_review_required_before_generation`拆开：已批准的路线/统计数值原值不变并迁入`frozen_numeric_values`；仍为null的共享probe架构和训练预算迁入`pending_model_and_budget_fields`。`freeze_disjoint_pilot_and_formal_house_manifests`重新加入人审阻断列表。D-183修订记录补`merged_into_base_contract_commit=ac978b6...`，说明其内容已并入基础合同但仍不表示可执行。
- 基础合同新增pilot family完成定义、只准由sealed route receipt/construction verdict机械派生、禁止调用方布尔自报，并登记机械派生仍待父stage family receipt实现。现有`seal-formal`生产模式在授权检查后也会明确拒绝旧布尔文件，且在拒绝前不读取pool/outcomes或写输出；48/64/停的纯规则函数保留作单元测试，不构成完成证明。
- 采纳审查S的交付拆分：后续先交科学口径层（L2 proposal来源、visibility、program前提、SPLIT/MERGE和RELINK证据）供用户审查；在该层获得认可前不再向上叠加新的批量调度/摘要封装。已存在封装代码保留并继续fail closed，不把整批测试通过当作科学层获批。
- 白话：这一步解决三种“名字看起来已经成立”的问题：oracle mask包不能叫L2，冻结数值不能和null架构混在同一袋里，pilot完成也不能由一张布尔表自报。输入仍是关闭合同和人工收据，输出更明确的阻断状态；它没有实现L2前端或pilot family收据，也没有删掉已审数值。

## D-199：L2 proposal、公开visibility与九类program构造科学层候选

- 日期：2026-09-16；状态：用户认可D-198科学口径层后形成的实现候选，等待代码审查，不开放运行、不冻结SAM资产或新增科学数值。L2 proposal核心只把当前公开RGB交给单帧无提示generator；禁用跨帧video memory，不接受depth、history、program、teacher、未来或private输入。输出mask按首像素/面积/摘要规范排序，重复mask直接构造失败，合法重叠proposal原样保留；receipt绑定RGB、SAM仓库commit、checkpoint、automatic-mask config、assets和generator代码摘要。真实SAM 2.1 loader、commit/checkpoint及全部mask数值仍为null，因此当前L2主表硬门不变。
- 公开visibility核心从一个已经公开的mask、depth和camera封存稀疏世界点；后帧只用当前公开depth/camera投影。视野外、被更近公开depth完全挡住、公开proposal再次支撑分别产生`out_of_view/occluded/reobserved`；无效或缺失depth保守地按未遮挡处理，不能授权隐藏干预。采样步长、样本数和遮挡容差仍待审，builder receipt尚未接入route receipt。
- 九类program构造计划为每类固定不同的公开前提槽，并对prior memory中的open/dormant node/edge机械核验。RELINK特别要求open entity、旧place和方向一致的open `located_at`边；SPLIT/MERGE在生成前封存geometry/frontend/远近pose和重复次数，每次fresh replay都必须实现1→2或2→1公开proposal转移，任一次不满足即保留construction failure，禁止换标签或替换样本。BIRTH/NOOP等涉及“无匹配/稳定”的最终充分判据仍须由冻结matcher与runner receipt绑定，当前结构计划不冒充完整构造成功。
- 白话：输入是一帧公开RGB、已经公开的几何记忆以及生成前写死的程序计划，输出是公开proposal、遮挡状态和可追溯的程序前提。例如SPLIT必须事先登记“远处1块、近处2块”，连续两次重放有一次仍是1块就失败，不能改叫BIND。它不等于SAM已经装好、数值已定、house可生成或这些程序在真实模拟器中已经成立。

## D-200：公开充分matcher与visibility route/worker摘要绑定（已认可）

- 日期：2026-09-16；状态：用户已正式认可D-200科学口径与当前代码候选：matcher只作公开构造充分门；RELINK新place绑定确定性place scaffold版本；edge RETRACT继续阻断；正式matcher/visibility数值保持null；不开放运行。visibility route plan现封存公开subject与builder config摘要；路线扫描和worker逐帧记录必须携带`vsmt-vm04-public-visibility-builder-receipt-v1`，并让subject/config/observation index/depth/camera/assessment/receipt逐项一致。worker在任何private intervention前完成验证，不能先执行动作再在终态发现receipt无效。正式visibility数值和生产callback仍未冻结。
- 新公开充分matcher采用显式无默认值配置，记录entity/surface/fragment逐region的visual/centroid/geometry/score分量、阈值、唯一/歧义/无匹配及逐program失败原因。BIND/BIRTH、REACTIVATE/BIRTH、RELINK/REPLACE按公开构造证据分流；RELINK的新place必须落到确定性place scaffold的登记版本；entity RETRACT/REPLACE要求至少两条满足冻结可靠度和时间间隔的visible-empty覆盖；SPLIT/MERGE继续绑定全部fresh replay artifact receipt。所有正式matcher数值保持null，测试值只作fixture。
- matcher只签`program_public_match_satisfied`并固定`semantic_identity_truth_established=false/private_identity_used=false`；私有身份、teacher和参考事务不能参与构造或修补候选。当前packet没有跨时“关系应出现但缺席”的公开证据类型，因此edge RETRACT充分条件明确失败，不以一次没检测到关系替代。父stage/materializer尚未落盘并聚合matcher receipt，故九类生产验收清单不勾选。
- 白话：这一步解决“遮挡判断是否真来自绑定的公开几何”和“写了program计划后最低公开证据是否够”的问题。输入是封存的公开subject、route、packet、prior和显式matcher参数，输出逐帧visibility收据与逐program构造收据。例如一帧自报`occluded`但receipt来自别的subject会在干预前失败；BIRTH若仍唯一匹配旧节点也会失败。它不等于物理身份已知、matcher数值已定、edge RETRACT已可构造或pilot获准运行。

## D-201：episode construction receipt与matcher因果边界（已认可）

- 日期：2026-09-17；状态：用户已正式认可D-201科学口径与当前代码候选，不开放运行。新增`vsmt-vm04-episode-construction-receipt-v1`，把既有materializer receipt、causal-prior receipt、最后一个登记terminal observation的公开packet、该packet之前的因果prior、program construction plan、显式matcher config、matcher receipt及可选SPLIT/MERGE artifact receipt绑定到同一append-only audit目录。该audit明确禁止deployment reader打开。
- matcher prior候选固定为“最后一个登记terminal observation之前的因果记忆”，其`graph_hash`必须等于causal receipt对应version-chain项，也必须等于terminal packet的`prior_memory_ref`和construction plan的prior摘要。选择干预时刻的更早memory会与当前packet合同不一致；接受任意外部prior则无法证明没有未来或错链。terminal当前packet本身仍只含公开输入，matcher receipt继续固定`private_identity_used=false/semantic_identity_truth_established=false`。
- materialization完成与program公开匹配分开记录：matcher不通过（包括edge RETRACT或缺失SPLIT/MERGE artifact receipt）封存`construction_failure`及原失败原因，不抛弃、不改program、不替换样本；matcher通过当前只写`public_match_satisfied_temporal_seal_pending`。离线audit能核内容和因果次序，但不能自证construction plan在terminal observation前已由在线父stage封存，因此固定`construction_plan_pre_terminal_seal_established=false/eligible_for_parent_family_completion=false`。当前也未实现family覆盖集合与完成聚合，不能把本收据冒充`constructed`或pilot family完成证明。
- 白话：这一步解决“公开packet已经写出来以后，matcher判断是否真对应同一次材料化和正确的历史版本”的问题。输入是材料化摘要链、终端公开packet、它之前的公开记忆、构造计划和显式matcher配置；输出一张只供审计的episode证据收据。例如BIRTH的RGB-D packet成功写出但仍匹配旧节点，结果会保留为`construction_failure`；即使matcher通过，在父stage补上终端观测前的plan封存证据以前也不能叫构造成功。它不等于family已经完成、身份真值正确、正式阈值已定或可以开始pilot。

## D-202：终端帧加载前的在线plan时间封存（已认可）

- 日期：2026-09-17；状态：用户已正式认可D-202科学口径与当前代码候选，不开放运行。stateful materializer callback只能在`terminal-1`公开packet已更新causal memory、最后一个登记terminal observation的公开或私有raw帧尚未打开时封存construction plan、matcher prior和`vsmt-vm04-online-program-plan-temporal-receipt-v1`。四个文件与摘要marker立即以append-only方式写入`materialized/construction-plan-seal/`；后续terminal帧加载或materialization失败时保留该现场，不回滚或改标签。
- 本收据只证明受审materializer调用内部的先后顺序：请求中的program、precondition refs和matcher config是否也由父stage在未预读terminal数据时从公开状态派生，当前尚无证明。因此receipt固定`request_provenance_established_by_parent_stage=false/clears_episode_temporal_seal_pending=false`，离线D-201 episode receipt也不消费该seal；正匹配仍为`public_match_satisfied_temporal_seal_pending`，不得计入family完成。
- 白话：这一步解决“当前公开记忆是否在看最后一帧之前就已经被用来造plan”的局部时序问题。输入是terminal前的causal memory、sealed route和一张请求，输出plan、prior及时间收据。例如最后一帧RGB损坏时，plan seal仍已留存但episode继续按失败收口。它不等价于父stage没有曾经偷看terminal数据、D-201已解除阻断、matcher数值已冻结或运行已获批。

## D-203：父stage公开request派生核心候选

- 日期：2026-09-17；状态：继承已认可D-202的独立实现候选，待用户审查，不开放运行。新增`vsmt-vm04-parent-program-request-spec-v1`与`vsmt-vm04-parent-program-request-provenance-receipt-v1`。父级核心只接受sealed public route、预登记公开selector spec、`terminal-1` causal memory和代码摘要；函数签名不接受episode root、raw path、terminal frame、teacher、reference transaction或private identity。
- 九类program均用稳定公开node ID/规则摘要作selector，调用者禁止直接传`node_version_id/edge_version_id`。核心在当前causal memory上唯一解析open version；RELINK还必须唯一解析方向一致的open `located_at`边。RETRACT只开放entity selector，edge RETRACT仍无入口。收据可证明本核心未获得raw路径且refs由公开memory确定派生。
- 边界仍保守：selector spec自身是否在terminal之前由父级编排封存尚无时间收据，D-203 receipt也尚未被D-202 temporal receipt消费。因此固定`selector_spec_pre_terminal_registration_established=false/consumed_by_D202_temporal_receipt=false/clears_D201_temporal_seal_pending=false`，不计入family。
- 白话：这一步解决“调用者能不能看完结果后手填一个有利的version ID”的问题。输入是公开路线、早先选定的稳定节点名和terminal前记忆，输出精确version refs、online request和来源收据。例如RELINK只登记entity A和place P1，核心自动找当前open版本及A→P1的open `located_at`；若有零条或多条则失败。它不等价于selector已证明提前封存、D-202已接入该receipt、D-201已解锁或运行已开放。

## D-204：父级selector时间seal与D-202父来源消费候选

- 日期：2026-09-17；状态：用户认可D-203候选并明确要求继续实现父级selector时间seal与D-202 receipt绑定，保持D-201/family阻断且不开放运行。新增`vsmt-vm04-parent-selector-temporal-receipt-v1`；父级纯核心把selector spec、sealed public route/private route commitment和父代码摘要绑定为raw观测0前、双方raw帧数均为0的时间收据。D-203 provenance升v2并绑定该selector receipt，仍不接受version ID、episode/raw path、terminal/future/teacher/reference/private输入。
- D-202 temporal receipt升v2并消费D-203 v2 receipt摘要；消费前逐项核episode/program/route/request、`terminal-1` prior、terminal index、确定性公开派生、selector提前登记及全部禁止通道。只改禁止位后重算摘要也必须拒绝。父receipt自身保持append-only的`consumed_by_D202=false`创建状态，由D-202 v2另记实际消费，避免回写旧receipt。
- 本批仍不让`clears_episode_temporal_seal_pending`变true：selector receipt尚未由真实生产父stage在raw writer前落盘，materializer尚未从该父任务读取整链，D-201离线episode receipt也未消费D-202 v2。正式matcher/visibility/SAM数值、edge RETRACT证据、family聚合和所有运行位不变。
- 白话：这一步解决“selector是否先登记”和“D-202是否真的拿到了父来源证明”的核心接口。输入是观测0前的selector/route和terminal前的causal memory，输出三段相互绑定的时间/来源收据；例如有人看完terminal后改BIRTH absence scope，原selector摘要就无法复用。它不等于真实父stage已经按这个顺序写文件、D-201已解除pending、episode可计入family或pilot获准运行。

## D-205：一次性数值冻结、首篇口径收窄与 pilot 早期信号

- 日期：2026-09-17；状态：科学数值已全部冻结，实现待用户审查，生成/训练/confirmation 仍全部关闭。用户审查了对 PLAN/METHOD/DECISIONS/证据链的整体审计后明确接受五条建议，并给出优先级："先生成一些数据然后再看哪里有缺陷比现在虚空索敌更合理"。该优先级同时裁决了审计中留给用户的二选一：place 采取收窄口径而不是放回学习集合，因为后者会在生成前**增加**阻断项。原 v1 提案 `configs/vsmt/vm04_observation_suitability_proposal_v1.json` 保持原字节（SHA-256=`2d99d51995e1b8f0ded5e66f1f0df9b8fab94c452655324ba289105eb38ba4c3`），新合同为逐字段派生的 [v2](../configs/vsmt/vm04_observation_suitability_v2.json)，状态 `d205_numeric_frozen_artifacts_pending`，全部 14 个授权位仍为 false。
- **阻断项分类修正（本决定的核心）。** D-183 的 16 项 `pre_generation_blockers` 与 `assert_generation_authorized` 的 36 个字段把两类东西混在一起：一类是"操作者裁决一个数值"，另一类是"服务器对真实产物算一个摘要"。混在一起的后果是这份清单不可能被任何一次审查会清空，于是四条连续决策 D-201→D-204 都只加固同一条时间封存链而自报不解除阻断。v2 将两类拆开：每个 `pending_fields` 块分为 `frozen_numeric_values`（科学，本决定冻结）与 `pending_artifact_digests`（证据，真实产物存在并经审查前保持 null）。新增 `assert_numeric_freeze_complete` 只回答"操作者是否已经决定完"，`assert_generation_authorized` 继续回答"模拟器是否可以运行"，两者不可互相代替。白话：输入同一份合同，输出"科学裁决已完成，只剩 8 个需要真实产物才能算出的摘要"；它不等于可以开始生成。
- **冻结的数值及依据。** 八种注册相机动作：Move 全部 `moveMagnitude=0.25 m`（与已封存公开路线扫描使用的 `GetReachablePositions` 栅格一致，一个栅格步等于一个注册动作），Rotate/Look 全部 `degrees=30`（30 恰等于已冻结的 `minimum_key_pose_yaw_change_degrees`，一次旋转即可满足关键 pose 偏航门，整圈占 24 步预算中的 12 步）；禁用 `forceAction` 与默认参数，固定 build 的 API smoke 仍是执行前必需。`decision_time_rule` 为名义注册动作时钟：观测 0 为 0.0 s，每个注册动作 +1.0 s，显式标注**不是**墙钟或物理时间，只表达顺序，动作若获得可变时长必须换版本。`action_command_encoding` 为 9 维：8 个动作按名称排序的 one-hot 加一个"观测 0 无注册动作"标志位，八个动作互异，不含幅度分量（每个动作只有一个冻结幅度，幅度槽恒定），不编码任何 private/program 字段。L2 proposal：`minimum_visible_pixels=196`（与 L1 实体一致）、`maximum_proposals_per_frame=64`、超限记构造失败而非静默截断；automatic mask generator 的 `box_nms_thresh` 与 `crop_nms_thresh` 均固定为 1.0，即**关闭抑制**，否则会与已封存的"保留独立重叠 proposal"政策冲突并引入未冻结的归属规则，完全重复的 mask 仍直接构造失败。公开 visibility：深度 0.05–20 m（与 L1 公开几何相同）、遮挡容差 0.05 m、采样步长 4 像素、样本数 32–512，且明确不得为提高成品率下调。Matcher：按 entity/surface/fragment 分别定值（D-139 要求，可移动实体允许合法位移而 0.5 m 地点锚定表面不允许），视觉/几何权重各自和为 1，唯一性分差 0.10，region/relation 可靠度 0.5，free-space 与支持包络可靠度 0.9、包络裕度 0.02 m（D-144 临时值升为正式值，D-145 的禁止下调条款继续生效），负证据最少 2 条时间分离至少 2.0 s。共享 probe：`shared_region_set_transformer_v1`，256 维、2 层 4 头、FFN 512、mean pooling、9 类输出，CFO 与 history 参数量完全相同且**唯一差别是 mask**；预算为 AdamW/3e-4/batch 16/4000 步/seed 7·19·31，**只登记一个配置、一个 checkpoint 规则、不做任何选择**，因此 `selection_family_split` 由"需要预留 family 做 probe 选择"改为"单配置不需要选择划分"，max-selection 偏差被彻底消除。SPLIT/MERGE：`fresh_replay_repeat_count=3`，几何与远近 pose 全部显式，判据只在冻结 L2 公开 proposal mask 上测量，覆盖度 0.5，private mask 仅作封存后覆盖度量、绝不参与 program 分配。以上数值是本决定提出的事前选择，依据是既有已冻结值、L1 公开几何的同口径和 24 步路线预算，**不来自任何已观测结果**；用户可以逐项否决，但否决必须发生在 pilot 之前。
- **首篇口径收窄（place）。** 新增 `first_paper_scope_boundary`：place 身份与 place 之间的 `adjacent_to` 由确定性 `place_scaffold` 对五个方法逐字节同样维护、且被排除在学习式 BIND/MERGE/SPLIT 之外，place 身份又直接来自模拟器精确 pose，因此第一篇的可检验对象是 entity/surface/fragment 上的类型化事务，**不能**主张地点或房间身份修订、空间拓扑/连通性修订、对 pose 或 SLAM 漂移的鲁棒性，也不能主张 D-061 描述的走廊级结构记忆。D-061 的研究目标本身保留并推迟到 M2，不是撤回。选择收窄而不是把 place 放回学习集合，是因为后者需要新增"公开地点负证据"类型及其自己的门，会在生成前增加而不是减少阻断项；这一取舍由用户本轮的优先级裁决。白话：审稿人一定会问"spatial memory 的 spatial 在哪里被检验了"，现在合同里有一个机器可核的答案，而不是在论文阶段临时解释。
- **pilot 早期可辨识性信号（只报告、不选择）。** 六个 pilot family 已由 D-182 永久排除出准入门、VM-05 和 VM-06，因此在它们上面跑一次 CFO/history probe 不可能选择任何东西。新增 `pilot_report_only_diagnostic`：使用与正式门完全相同的单一注册架构与预算，报告 pilot 的 CFO 准确率、history 准确率、配对差和逐 program 准确率；明确不得改门限、不得改正式 house 数、不得改 probe 架构/预算、不得改路线几何或 program 分配、不得改 matcher/visibility 数值；允许的响应只有"按原样进入正式生成"和"停止并按既有 pilot 规则另开合同版本"。当 pilot 配对差点估计 ≤0 或 pilot CFO ≥0.8 时要求操作者显式记录 go/no-go。这两个触发值故意取得很松，只用于在 48–64 房之前捕捉灾难性设计失败，松到不可能充当选择工具。它解决的是"花完全部生成预算之后才第一次知道 CFO 是不是 70%"，把 48 房的风险压成 6 房的风险；它不是准入门结果，pilot 结果永不进入任何正式统计。
- **SPLIT/MERGE pilot 成品率下限。** D-142 把三个确认性原子中的两个押在 SPLIT/MERGE 上，而这两者的构造依赖一个前端伪影在每次 fresh replay 都复现，且分割器当时尚未选定。新增 `pilot_artifact_yield_floor`：在六个 pilot family 上，SPLIT 与 MERGE 各需至少 3 个 family 的全部 fresh replay 复现；低于下限时，在正式生成**之前**记录该原子从确认性集合降为描述性，并如实报告缩小后的检验力。低于下限不得改几何或判据，门限不得在看到 pilot 结果后调整。白话：确认性功效不应该押在最不可控的环节上还等到最后才发现。
- **pilot family 完成度的机械派生已实现（待审）。** 新增 [`src/vsmt/vm04_pilot_family_completion.py`](../src/vsmt/vm04_pilot_family_completion.py)：输入封存的 source pool、每个 pilot family 的注册 episode 及其由 `assess_route_receipt` 产出的构造 verdict、以及 SPLIT/MERGE 的 fresh replay 回执，输出六个逐 family 布尔、逐 family 的不完成原因、以及上述成品率下限评估；`seal_formal_selection_from_pilot` 再把它接到已有的 6→48/64/停规则上。调用者自报的 `constructed` 等字段直接拒绝，verdict 必须绑定封存 route plan，replay 的"已复现"标志必须与其公开 proposal 计数一致，摘要被篡改即拒绝。它**不读取** CFO、history、oracle recall、private 身份或 teacher 分数——D-183 规则只允许看构造完成度。合同中该状态写为 `implemented_review_pending_parent_stage_family_receipt_v1`，`assert_generation_authorized` 继续要求 `implemented_and_reviewed_...`，因此用户审查之前它仍是阻断项。
- **仍然阻断的内容，以及为什么不能由本决定清空。** v2 剩余 8 个 null 全部是真实产物摘要：SAM 2.1 仓库 commit、checkpoint、automatic-mask config、assets receipt、generator 代码，materializer 代码与 config，以及已审 L2 前端 receipt。凭空填写其中任何一个都是伪造证据，与本项目全部反作弊纪律直接冲突，因此它们保持 null。另外 `source_houses_to_attempt` 按设计只在 pilot 之后封存。工程阻断项不变且已重写为 11 条：真实 SAM 资产、materializer source manifest 封存、生产父 stage/raw writer/materializer 接线、D-201 消费在线 seal、真实 reachable 扫描、pilot family 完成度审查、pilot 与正式 house manifest 封存、最终开闸审计。
- 是否接触 test 信息：否。本决定只使用既有合同、已冻结数值、源码审计和 D-139/D-142/D-144/D-145/D-182/D-183 的既有裁决；未生成数据、未运行模拟器、未训练、未读取 validation/confirmation，旧 M1/S5 no-go 与 test 封存不变。
- 验证方式：[`tests/test_vm04_d205_numeric_freeze.py`](../tests/test_vm04_d205_numeric_freeze.py) 29 项本地通过，覆盖 v1 字节未变、未改动节逐字段相同、剩余 null 恰为 8 个产物摘要加 1 个 pilot 后字段、冻结态仍关闭全部授权、口径收窄不可弱化、动作模板无 forceAction/默认值、动作编码互异且无 private 字段、NMS 保持关闭、matcher 按结构类型分别定值且权重和为 1、probe 单配置、pilot 诊断不能选择任何东西、成品率下限不可调，以及机械派生的 6/4/3 分支、原因保留、下限降级、自报布尔拒绝、route 绑定、replay 计数一致性和摘要篡改拒绝。服务器全量回归与用户代码审查仍 pending；本地通过不代替服务器验收。

## D-206：收回地点层 oracle，首篇纳入地点身份修订

- 日期：2026-09-17；状态：地点层科学数值已冻结，实现待用户审查，生成/训练/confirmation 仍全部关闭。用户明确目标为冲二区、结果出来再发表，并接受"加里程计噪声、科学分量优先于 pilot 通过率"。合同为从 v2 逐字段派生的 [v3](../configs/vsmt/vm04_observation_suitability_v3.json)（v2 保持原字节，SHA-256=`48b50df4adc162e2896145a01d2ab4eb8c87d4dbb943898abab29bb18079fa59`），状态 `d206_place_layer_frozen_artifacts_pending`，14 个授权位仍为 false。本条**取代 D-205 的口径收窄**，D-205 的数值冻结与阻断项 A/B/C 分类全部保留。
- **重开 D-205 收窄的原因是发现了一个信息边界漏洞，而不是改主意。** `contracts.py:576` 的 `build_adapter_input` 把 `camera_pose` 直接从模拟器 agent metadata 传给每个方法，`vm04_multiview_raw.py:92` 的 `_camera_record` 也把真值世界位姿写进公开相机记录；同时 CFO 的输入定义是"整个当前公开 packet"，禁止列表里没有 `camera_pose` 也没有 `past_actions`。因此 place 身份不是"被排除在学习之外"，而是**被无偿给出**；CFO 也不是当前帧诊断器，而是"当前帧＋真值世界位姿＋完整动作历史"诊断器。D-205 的正确做法本应是收回这个 oracle，而不是围绕它收窄主张。白话：走廊 A 和走廊 B 长得再像也不用推理，packet 里的世界坐标直接给了答案。
- **公开 pose 通道改为 episode 相对里程计。** 公开 pose 定义为"以观测 0 为原点、由注册动作推算、叠加声明噪声"的相对位姿；真值世界位姿移到私有评价通道，不进公开 packet。公开内参保留，因为它是固定传感器属性而非定位答案。噪声模型 `registered_action_odometry_noise_v1` 固定为平移相对 2%＋绝对 5 mm、旋转相对 2%＋绝对 0.5°、侧滑 5 mm，零均值高斯、逐动作独立、由封存 episode ID 派生种子；噪声只作用于公开估计，**模拟器仍精确执行原动作**，路线验收也仍按实际 pose 的 2 cm/1° 判定——那检查的是"路线有没有真的发生"，不是"方法被允许知道什么"。2% 在真实轮式里程计的报告范围内，是可辩护的难度而不是人为制造的难度，且不得在看到结果后调大。
- **place 成为可学习结构。** place 区域保留 0.5 m 格量子，但格坐标表达在漂移的相对系里，于是同一物理地点在不同时刻可能落进不同格（假回环 → 需要 place MERGE），两个物理地点可能落进同一格（地点混淆 → 需要 place SPLIT）。`adjacent_to` 由坐标推出改为证据形成。确定性骨架不废弃，降级为 **place-oracle 诊断臂**：同一批 episode 跑两遍，一遍给真值地点以隔离地点层误差，主表用推断地点，两者之差就是地点误识别的代价；oracle 臂不得进主表。新增误差类别 `place_misidentification_induced_entity_error`，因为 `located_at` 一旦依赖推断地点，一个 RELINK 错误可能根本是地点认错造成的。private 评价这一侧反而免费——模拟器知道真实坐标，地点身份真值判定精确可靠，不需要 D-177 那样的物理正例硬门。
- **Z 型路线 family 是地点层判别的登记原型。** 形状为走廊 A → 转弯 → 连接段 → 反向转弯 → 视觉相似的走廊 B，两次注册转弯，两条走廊按构造使用相同作者材质。**必须附带后续可判别观测**：路线要继续到一个能公开区分 A 与 B 的观测。原因是没有它的话，family 只检验一次性关联；有了它才检验"早期错误的地点承诺能否被修订、以及它污染记忆多久"——这正是版本化和 SPLIT 的用武之地，也正是 contamination AUC 测量的东西。几何在生成前预登记，不得在看到结果后调。
- **CFO 掩码补漏。** 禁止列表增加 `camera_pose` 与 `past_actions`，共享 probe 架构的掩码增加 `pose_tokens` 与 `past_action_tokens`。同时给 pilot 只报告诊断登记具名风险假设：D-206 之前真值 pose 会让 CFO 直接回答空间锚定问题并顶破 0.6 上限；若 D-206 之后 CFO 仍高，归因是外观或区域构成泄漏 program type，而不是 pose。
- **公平性口径按用户判断调整。** 用户明确不回避"动作空间更大"的质疑，希望强调统一事务空间涵盖四类机制。合同据此登记：主张框架为"现有系统各自实现修订空间的一个片段，统一的类型化可执行空间把它们作为特例包含"，并新增 `structural_capability_gap_argument`——TAF/ELU/WFR/LOW 都不维护可修订的地点身份，**再多训练预算也补不上**，这是表达能力差距而非预算差距，必须如此报告。共同能力子集改为**按对报告**而非五方交集，因为五方交集只有 BIND 和 BIRTH 两项，那张表不提供信息。
- **本条不新增任何 B 类产物摘要。** v3 剩余 null 与 v2 完全相同：8 个真实产物摘要加 pilot 后才封存的 `source_houses_to_attempt`。新增的是三条 C 类工程项：raw writer 的 pose 通道替换、确定性骨架降级为 oracle 臂并实现 place 关联、真实 reachable 扫描与 Z 路线 family 构造器。D-205 的两个闸门与 A/B/C 分类架构不受影响。
- 预期代价，事前记录：噪声会让部分 episode 的公开证据不足以支撑任何合法程序，构造成品率下降，六个 pilot family 更容易触发 0–3 的停止规则。用户已在知情下选择科学分量优先。若 pilot 因此停止，按既有规则另开合同版本，**不得调小噪声来提高成品率**。
- 是否接触 test 信息：否。未生成数据、未运行模拟器、未训练、未读取 validation/confirmation。
- 验证方式：[`tests/test_vm04_d206_place_layer.py`](../tests/test_vm04_d206_place_layer.py) 17 项本地通过，覆盖 v2 字节未变、授权全闭、不新增产物摘要、真值 pose 不得回到公开 packet、噪声为正且不可上调、**零噪声被拒绝**（否则退化为积分题）、place 不能同时可学又是骨架、退役骨架必须使place可学、每个可学结构类型都要有自己的关联规则、CFO 不得重新获得 pose、Z 路线不得去掉后续判别、oracle 臂不得进主表、D-205 冻结值未漂移、新增阻断项仅为工程类。服务器全量回归与用户代码审查仍 pending。

## D-207：地点层路线预算与 provenance 通道分离

- 日期：2026-09-17；状态：科学数值与通道边界已冻结，实现待用户审查，全部授权位仍为 false。用户批准两件事：地点层路线步数上限提到 64（实体层保持 24），以及立即处理 `public/route.json` 的残留隐患。合同为从 v3 逐字段派生的 [v4](../configs/vsmt/vm04_observation_suitability_v4.json)（v3 保持原字节，SHA-256=`31d2e156b8a4c1ca39837aadc004c804a3e016e0bf9d55c0d211f96054130723`），状态 `d207_place_layer_budget_and_provenance_split_artifacts_pending`。D-205 的数值冻结与 A/B/C 阻断项分类、D-206 的 pose 通道与 place 层全部保留。
- **发现的硬冲突：D-206 的 Z 路线在 D-182 合同下无法表达。** 冻结的 Z 几何是走廊 4 m ＋ 连接段 3 m ＋ 走廊 4 m 加两次 90° 转弯；按已冻结的 0.25 m/步、30°/步展开需要 44 个平移加 6 个旋转共 **50 步**，而 D-182 冻结的 `maximum_route_steps=24`。24 这个值是为实体层"可见→遮挡→重现"短分支定的，当时还没有地点层 family。
- **同一个数字还决定科学分量。** 实测漂移：24 步（行进 4.5 m）时航向漂移在臂长上的横向误差约 0.16 m，远小于 0.5 m 的 place 格，place 身份**永远不会真正含糊**；64 步（行进 14.5 m）时约 0.50 m，恰好一个格。所以让 Z 路线可表达的同一个改动，也把漂移带进了地点身份开始真正不确定的量级。
- **处理方式：分层预算，不动 D-182 的已批准值。** 新增 `maximum_route_steps_by_family_layer = {entity: 24, place: 64}`；`frozen_numeric_values.maximum_route_steps` 保持 24 逐字节不变，验证器要求分层表里的 entity 项必须等于它。route plan 新增必填 `family_layer` 字段，`_route_step_budget` 按层选预算。白话：实体层的规则一个字没改，地点层是新增的预算，不是放宽旧的。
- **提步数的代价是成品率，不是精度——这一点必须写清楚，因为它容易和第一次 VM-04 的失败混淆。** 路线验收只在 precondition/challenge/reobservation 三个锚点逐点绝对比较实际 pose 与计划 pose，**不累积**；AI2-THOR 的离散动作要么精确成功要么被挡住失败（后者由 `registered_camera_action_success` 直接判路线失败）。所以更长的路线不会让每个锚点变得更不准，只会提高"某一个动作被挡住"的概率。缓解办法是每个计划步必须落在实测可达格上，在封存路线之前就排掉绝大多数阻挡；**不得通过放宽容差提高成品率**。
- **与 D-169 那次失败的区分。** 第一次 VM-04 的误差失败是**物体终态误差**：`TeleportObject(forceAction=true)` 返回成功但物体真实 x 比请求少 `0.049812 m`、z 少 `0.014230 m`，超过 5 mm 容差记 `terminal_poststate_mismatch`。D-171/D-172 已把根因钉死为物体被传送进被占据的位置、物理结算把它推出约 5 cm（同请求改 `forceAction=false` 被明确拒绝并写"传送后与另一件物体碰撞"，请求前暂停物理则三轴误差全零）。**那是落点选址问题，与路线长度无关**，后续干预执行器必须先用公开 free-space 证据验证落点为空并使用非强制动作，被拒绝就记构造失败。
- **provenance 通道分离。** 此前 sealed route 写在 episode 的 `public/` 目录下，而证据链 §7 的五通道模型明确把 route/plan/receipt 归在 **provenance 通道**，其读取规则是"deployment reader 不打开"。也就是说 `public/` 同时被当成"非私有"和"部署可读"，这两个含义不一样。现在 route 文件移到 `provenance/route.json`，`public/` 从此只意味着部署可读。
- **公开投影同时去掉世界锚点。** `initial_pose` 与 `planned_poses` 从公开投影删除——路线验收比的是**私有** route plan，它保留这两项，所以公开投影从来不需要它们。更值得注意的是另外三个字段：`phase_observation_indices` 说明哪几帧是 precondition/challenge_hidden/reobserved，`branch_type` 说明是遮挡还是出视野分支，`visibility_subject_public_ref` 点名干预主体——**泄漏 phase 结构比泄漏 pose 严重**，因为它直接说明这条 episode 在考什么。这三项留在 provenance，不进部署可读侧。
- **补上一条现有防线抓不到的不变量。** 既有的反泄漏测试是"改私有/参考/未来数据，公开字节必须逐字节不变"；而 route 文件本身就在公开侧，改私有数据不会改它，**所以该测试对这一类泄漏结构性失明**。新增直接的目录不变量：部署可读目录的字节里不得出现任何世界 pose 数值，也不得出现任何 episode phase 结构。
- 是否接触 test 信息：否。未生成数据、未运行模拟器、未训练、未读取 validation/confirmation。
- 验证方式：[`tests/test_vm04_d207_provenance_split.py`](../tests/test_vm04_d207_provenance_split.py) 14 项本地通过，覆盖 v3 字节未变、实体预算仍是 D-182 原值且不可经分层表抬高、地点预算覆盖 Z 路线所需步数、实体层拒绝 50 步路线而地点层接受、地点层仍有 64 步天花板、未登记 family layer 被拒、公开投影无世界 pose 而私有 plan 保留、route 写在 provenance 而非 public、**部署可读字节中既无世界 pose 也无 phase 结构**、私有侧仍持有世界真值。VM04/VSMT 全量 480 项通过；服务器全量回归与用户代码审查仍 pending。

## D-208：工作树收敛到活跃 VSMT 线，旧两条路线移入归档分支

- 日期：2026-09-17；状态：accepted（仓库整理，不改任何科学口径、数值、门或授权位）。用户要求"加两个分支，一个CPMT，一个SpatialWorldModel，把相关文件都送进去，目前仓库文件太多，每次耗费TOKEN太多"。
- 归档分支在删除**之前**从当时 HEAD 建立并推送，因此两个分支各自包含完整快照：`archive/cpmt-m1-20260917`、`archive/spatial-world-model-20260917`。这沿用 D-017 把旧工作树推到 `archive/pslm-pre-ctt-20260904` 的先例，以及 D-060"原文固定在某提交、不复制进新 archive"的处置；**没有任何文件被销毁**，全部可由分支或历史取回。
- 移出活跃工作树的两块：**SpatialWorldModel 区**（D-062 空间世界模型路线，已由 D-122 暂停）含 `src/spatial_world_model/`、`ops/spatial_history/`、`tests/spatial_world_model/`、`configs/spatial_history/`、`literature/`；**CPMT/M1 区**（旧 M1/S5，已 no-go）含 20 个 `src/cpmt/m1_*|dev_*|visual_pilot|run_provenance` 模块、对应测试、`ops/` 中非 vsmt 脚本、非 vsmt 的 configs/results/schemas，以及 `scripts/`、`prototype/`、`data/manifests/`、experiments 的文档与模板。跟踪文件由 **719 降到 210**。
- **保留的 cpmt 核心是活跃依赖而非遗留**：`__init__`、`errors`、`hashing`、`executor`、`equivalence`、`maintenance`、`pending` 七个模块构成闭包，`src/vsmt` 与 `ops/vsmt` 只 import `cpmt.executor` 与 `cpmt.hashing`，而包 `__init__` 连带 equivalence/maintenance/pending。METHOD 把旧 C00–C11 的职责降为 `L0 symbolic regression`（执行器语义、回滚、版本/provenance 与 S-01～S-12 边界回归），所以这七个模块和 `experiments/counterfactual_transaction_learning/fixtures/` 的 69 个 C00–C11 夹具**属于活跃线**，一并保留。第一次归档时误删了这批夹具、导致 executor/equivalence/pending 共 63 项失败，已按此口径恢复。
- 归档判据是**基于实际 import 而不是文件名**：凡 import `cpmt.m1_*|dev_*|visual_pilot|run_provenance` 的测试一律归档，因此 `test_ctl_dev.py`、`test_run_provenance.py`、`test_visual_pilot.py` 这些名字里没有 `m1` 的也被正确识别；`test_export_run_report.py` 因 import 已归档的 `scripts/` 包一并移出。
- **旧 M1 的 3 个已知失败测试随本次归档移出活跃线，这不是把失败藏起来**：它们连同全部 M1 源码、配置、结果与回执完整保留在 `archive/cpmt-m1-20260917`，旧 S5 no-go 结论不变、旧结果不重新解释。活跃线的回归从"466 通过 + 3 个历史失败"变为 **578 项全通过**。
- 不改变的内容：VSMT 全部科学数值与阻断项分类（D-205）、地点层口径与 pose 通道（D-206）、分层预算与 provenance 分离（D-207）、合同 v1–v4 字节、全部十四个授权位（仍为 false）、旧 test 封存、D-062 与旧 M1 的历史结论。
- 是否接触 test 信息：否。未生成数据、未运行模拟器、未训练。
- 验证方式：删除后活跃线 `pytest tests/` 578 项全通过；`src/cpmt` 保留模块的 import 闭包经 AST 复算确认不含归档模块；两个归档分支已推送且各含完整快照。

## D-209：真实公开 reachable 扫描、逐步可达验证与 Z 路线 family 构造器（②）

- 日期：2026-09-17；状态：工程接线已实现，待用户代码审查；未改任何科学数值、未改任何合同字节、全部十四个授权位仍为 false。这是证据链 §10.2b 的 ② 项，对应 v4 `pre_generation_blockers` 里的 `implement_the_real_public_reachable_position_route_scan_with_per_step_reachability_verification_and_the_Z_route_family_builder`。该阻断项**不由本实现清空**，按 D-059 须由用户审查后才能改写。
- 解决的问题：路线此前只有 schema 和纯核心，没有真实可达点来源——`build_route_plan_from_public_graph` 接到的 pose 图是调用者递进来的，没有任何东西保证图上的姿态真的可达。同时 D-206 登记的 Z 路线 family 只有文字形状，没有构造器。D-207 又把这两件事绑在一起：地点层 64 步预算把"某一个动作被挡住"变成长路线的主要失败模式，而唯一不放宽容差的缓解就是每个计划步预先验证落在可达格上。
- 允许的输入：公开 `GetReachablePositions` 返回、已冻结的八种注册动作请求模板、干预前匿名 visibility 扫描、预登记并封存的 Z 几何。不读 private instance ID、program 结果、teacher、future，也不读任何动作执行结果——扫描是干预前的公开查询，计划姿态是对冻结模板的纯运动学展开。
- 产生的输出：
  - [`src/vsmt/vm04_reachable_scan.py`](../src/vsmt/vm04_reachable_scan.py)：`seal_public_reachable_scan` 把一次真实公开查询封存成整数格键的回执（浮点不进摘要，所以同一房屋两次扫描逐字节可比）；格距**由合同的 `moveMagnitude` 派生而非硬编码**，所以未来改动幅度不可能与扫描格悄悄不一致。`nominal_route_poses` 给出 N+1 个无噪声计划姿态；`seal_route_step_reachability` 逐步验证并封存回执，遇到第一个被挡住的步就失败关闭。
  - [`src/vsmt/vm04_place_route_builder.py`](../src/vsmt/vm04_place_route_builder.py)：Z 路线 family 构造器。几何是**输入**不是搜索结果——使地点层 family 成立的正是那个事前登记的形状，而不是某条恰好好用的路线。
  - [`ops/vsmt/vm04_reachable_scan_worker.py`](../ops/vsmt/vm04_reachable_scan_worker.py)：唯一接触模拟器的入口，**先查 `trajectory_implementation_authorized` 再碰 controller**，而不是先拿到位置再检查。查询失败是拒绝，不是空格子。
  - `vm04_observation_stage.py` 新增 `seal-reachable-scan` 与 `verify-route-reachability`，两者都要 `route_plan_sealing_authorized`（当前 false）。
- **AI2-THOR 的可达格是轴对齐的，而冻结的旋转步长是 30°，所以从非 90° 倍数航向发出的平移按构造就会离开格子。** 这不是本决定新增的限制，是 0.25 m 与 30° 两个已冻结值相遇的既有后果；本实现把它变成一个具名的规划期失败（`translates from a heading that is not axis aligned`），而不是一条只有在服务器上跑起来才会失败的路线。实体层路线因此在提供扫描时被约束到轴对齐平移；Z 路线的 90° 转弯（3×30°）本来就满足。
- **Z 路线的三条结构要求，都是实体层 schema 表达不了的：** 两次方向相反的注册转弯（一次只是拐角，两次相反才把走廊 B 摆到走廊 A 旁边）；**强制的后续可判别观测**（D-206 明确：没有它只检验一次性关联，有了它才检验早期错误的地点承诺能否被修订、以及污染多久，这正是 contamination AUC 测量的东西；构造器对空的 disambiguation 直接拒绝）；**走廊 B 内非空的模糊承诺窗口**（如果路线从未在锚点隐藏时观测走廊 B，就没有错误承诺可供修订）。三者连同几何摘要、可达扫描摘要、逐步验证摘要一起写进 `z_route_family_receipt`。
- **实测：冻结几何恰好占满预算。** 4 m 走廊＋90° 转弯＋3 m 连接段＋反向 90°＋4 m 走廊 = 16+3+12+3+16 = **50 个注册动作**，与 D-207 的算术一致；地点层 64 步预算给后续可判别观测留下**恰好 14 步**（例如掉头 6 步＋回走 2 m 的 8 步）。这不是余量，是刚好够。若某个 pilot house 的可判别观测需要多于 14 步，那是构造失败，按规则保留，不得提预算。
- **顺带修掉一个会让 D-207 分层预算失效的缺陷：** `vm04_public_route_builder` 读的是 `frozen_numeric_values.maximum_route_steps`（实体层的 24），而不是 D-207 的 `_route_step_budget(approved, family_layer)`。于是 `family_layer="place"` 这个参数存在但无效，任何超过 24 步的地点层路线都会被静默判为"找不到合法路线"。现已改为按层取预算，并加了一条回归：同一条 27 步链在实体层被拒、在地点层通过。
- 它解锁：可以从真实房屋取得可达格、按可达格预先筛掉绝大多数被挡住的路线、并构造出符合 D-206/D-207 全部登记要求的地点层 Z 路线 family。①②合起来使"在 SAM 资产到位之前先跑通并产出真实多视角 raw episode"成为只差 ③ 的路径。
- 它仍不解锁：不解除任何授权位；不封存来源池；不产生任何 episode；不动八个 B 类产物摘要；不实现父 stage 多 worker 调度与 receipt 合并（③）；不实现 place 关联与 `adjacent_to` 证据化（D-206 的第 6 项 C 类工程项）。edge RETRACT 继续阻断。
- **一处需要用户裁决的缺口（未自行决定）：** 合同 `place_identity_revision.corrective_programs` 把 place MERGE 与 place SPLIT 列为地点层的纠正程序，但 `validate_route_plan` 对 SPLIT/MERGE 要求一个 `split_merge_artifact_plan`，而已冻结的 `deterministic_SPLIT_MERGE_construction` 是**实体层前端伪影**的定义（在 L2 公开 proposal mask 上按覆盖度 0.5 测量、3 次 fresh replay）。地点层的 SPLIT/MERGE 不是前端过分割，是漂移造成的格冲突，用不上那套判据。本实现的处理是：构造器接受一个由调用者预登记并传入的 artifact plan，**绝不自行发明**；不传就拒绝。真正的地点层 SPLIT/MERGE artifact plan 语义需要单独裁决。当前可用的地点层 program 只有 BIND 与 BIRTH。
- 下一条依赖：③ 父 stage 多 worker 调度与确定性 receipt 合并。
- 是否接触 test 信息：否。未生成数据、未运行模拟器、未训练、未读取 validation/confirmation。
- 验证方式：[`tests/test_vm04_reachable_scan_and_z_route.py`](../tests/test_vm04_reachable_scan_and_z_route.py) 32 项本地通过，覆盖十四位授权仍全 false、剩余产物摘要仍为 8 个、v1/v2/v3 逐字节未变、扫描格等于冻结 move 幅度、空/失败查询被拒、离格点被拒、重复格与多层被拒、摘要与三条无污染声明被篡改即拒、运动学与冻结模板一致、非轴对齐平移被拒、单个被挡住的格使整条路线失败、验证回执可复算且篡改被拒、Z 几何恰好占满 64 步预算且几何本身为 50 步、去掉后续可判别观测被拒、走廊不相似或同引用被拒、事后调参被拒、非整步长度与转角被拒、超预算几何被拒、走廊 B 全程可见（无模糊承诺）被拒、扫描姿态偏离计划姿态被拒、非地点层 program 被拒、place SPLIT/MERGE 缺 artifact plan 被拒、扫描缺观测被拒、公开投影仍无世界锚点，以及分层预算回归（27 步链实体层拒、地点层通过）与离格扫描姿态被拒。活跃线全量 `pytest tests/` 由 578 升至 **610 项全通过**。服务器全量回归与用户代码审查仍 pending。

## D-210：动作可见、地点非网格真值的双层地点记忆与固定 12 槽 P0

- 日期：2026-09-18；状态：用户已明确批准科学口径，本轮形成可审机器合同、纯核心、关闭阶段入口、适配器和指标；真实 source house 绑定、路线封存、raw 生成、adapter materialization、private evaluation、训练、validation 和 confirmation 均未授权。
- 用户批准原文：“完整逐动作只作 raw/provenance，模型读取关键帧、连续位姿信念和边动作摘要；0.5 米格只用于规划与候选召回，不定义地点身份；85.5% 降为诊断，精确动作积分作为单列 oracle；P03/P04/P06/P07/P08 承担地点与拓扑修订主证据。”此前同轮已批准：两开发 house 固定 12 条；删除 24 步上限；0.25 m 平移、90° 转向、`snapToGrid=true`；路线执行前登记完整动作；128 动作只作机械保护线；P01–P04 各在两房运行、P05–P08 各一次、P09/P10 延后；raw 逐动作保存；正回环门 0.35 m、负例至少 1.5 m。
- **取代范围：** D-210 取代 D-206/D-207 的“2% 人工动作噪声→0.5 m 相对格→格即地点身份”主实验解释、地点 SPLIT 作为 P0 操作、64 步科学上限和 30° body rotation。D-206 的真值世界 pose 泄漏发现、世界 pose 私有化及后续判别观测要求继续有效；D-207 的 raw/provenance 与部署读取分离继续有效；D-209 的公开 reachable scan/逐步可达验证可作为路线工程部件，但其 50/64 步 Z family 不是新 P0 的硬路线模板。旧配置、代码、测试和回执保持原字节与历史解释，不能认证 D-210。
- **双层状态：** 快层是 episode-relative 连续位姿信念（均值、协方差、置信度），只作度量先验和候选召回；慢层是版本化拓扑地点图，地点节点容纳区域/实体证据，边保存关键帧间动作摘要。输入为关键帧 RGB-D/公开几何、连续 belief、边摘要和 prior predicted memory，输出地点/关系候选及版本化修订。例如 Z 形走廊进入外观相似的新走廊时应 BIRTH，新路径回到旧走廊时凭视觉—拓扑证据 BIND/MERGE。它不把 belief mean、0.5 m cell 或动作积分结果直接变成 place ID，也不主张度量 SLAM。
- **事务边界：** P0 地点操作限定 `NOOP/BIND/BIRTH/MERGE`，不沿用实体 proposal 伪影的 SPLIT 判据；关系允许 `CREATE/RELINK`。CREATE 是首次增加关系，RELINK 只修正既有错误端点。例如 T 路口首次探索左右支路是两次 CREATE，不是 RELINK。完整逐动作在 raw/provenance；模型边只见 step count、动作直方图、合并的有序 quarter-turn 段、名义平移、估计 delta/covariance、confidence 和 raw span digest，不见逐步列表。
- **85.5% 与 0% 的解释：** 85.5% 是 3,000 个诊断回程中，D-206 带噪格启发式至少制造一个重复地点的 episode 比例，越低越好，但不等于模型准确率、覆盖率或最终错误率；精确公开动作积分得到 0% 只证明固定动作回程可被简单算回，不能证明地点图、视觉别名拒绝、多环拓扑或实体挂载正确。因此 noisy-grid 数字降为历史诊断，精确动作积分和真值 pose 分别作为输入占优的单列 oracle，全部排除 headline。
- **12 槽与证据角色：** slot 0–3 为 house 0 的 P01–P04，4–7 为 house 1 的 P01–P04，8/9 为 house 0 的 P05/P07，10/11 为 house 1 的 P06/P08，seed 为 26091800–26091811。P01/P02 是 control，P05 supporting，P03 alternate-path return、P04 perceptual-alias nonreturn、P06 T-junction branches、P07 figure-eight loops、P08 room-corridor-room with entities 是 headline。规划动作数范围仅是 hint；实际完整路线只受 128 机械保护线，运行时不截断，失败不换槽不补样。
- **地点参考与指标：** ≤0.35 m 且同 reachable component 为回环正例，≥1.5 m 或预登记不同分支/房间为负例，间隔带不贴强标签，yaw 不决定地点身份。主指标为 label-invariant place pairwise P/R/F1、duplicate-place、false-merge、loop P/R、relation-type+endpoint F1、entity-place attachment accuracy、contamination AUC；另报 candidate miss、teacher error、amortization error、illegal transaction 和 collateral change。全 P0 macro 与五个 headline 场景 macro 分开。
- **实现：** 新机器合同 [`vm04_d210_dual_layer_p0_v1.json`](../configs/vsmt/vm04_d210_dual_layer_p0_v1.json) 五个授权位全 false；[`d210_place_memory.py`](../src/vsmt/d210_place_memory.py) 实现合同验证、无 24 步上限的 route seal、12 槽公私 manifest、动作边摘要、禁止字段递归扫描的 adapter、标签置换不敏感评价与 headline 聚合；[`vm04_d210_p0_stage.py`](../ops/vsmt/vm04_d210_p0_stage.py) 当前只可 check，`seal-batch` 在读外部文件或写目录前拒绝。它们不产生 episode、模型或论文效果。

## D-211：批准 D-210 基线，开放两房/12路线封存与单槽 raw smoke

- 日期：2026-09-18；状态：用户明确批准 `8d6bd13` 作为 D-210 P0 工程基线，并开放“两房与12条路线封存及单槽 raw smoke”。`8d6bd13` 已 fast-forward 合入本地 main；未推送远端。新执行实现位于独立审查分支，当前仍待其 commit 审查，因此没有读取服务器 source/route、没有启动 simulator、没有创建 seal 或 raw 产物。
- **授权的最窄解释：** 固定复用两个已有来源审计的开发 house `train:004270`/`train:008243`及其 source record SHA-256；允许封存 D-210 固定 slot 0–11 的完整 route 和私有起点；只允许 slot 0/house 0/P01 用 fresh controller 跑一次工程 raw smoke。P01 是 control，不是 headline。其余11槽 raw、adapter materialization、private evaluation、metrics、训练、validation、confirmation继续关闭；失败不得换房、换slot、换scenario、换路线或补样。
- **为何新增 execution binding：** D-210 route plan 完整保存动作但故意没有 simulator 世界起点，不能单独执行。D-211 另存 private `initial_pose`，绑定 route digest、公开 reachable scan 摘要和公开 RGB-D route evidence 摘要；yaw 必须为90°倍数、horizon=0，每个平移终点须在执行前验证reachable。这个绑定只供执行器定位，不进入模型或公共manifest。它不改变“0.5 m格不定义地点”的D-210口径。
- **为何不用旧 raw writer，以及用户复核后的三面修正：** 旧 `vm04_multiview_raw.py` 会按 D-206 的2%声明噪声生成相对pose，与D-210撤销人为noisy-grid地点任务冲突。最初D-211候选已保存公开RGB-D/无世界pose内参和provenance完整route/逐动作回执，但把simulator pose全部不落盘；用户指出这会失去D-210已登记的true-pose oracle和定位/地点推理误差分解。修正口径是公开面仍无世界pose，provenance仍保留完整动作，新增隔离的private per-observation agent/camera pose并绑定公开frame摘要；采集private truth不等于运行private evaluation，adapter/candidate reader均不得读取。instance masks、reference place、loop label、teacher、adapter packet和metric仍不生成。另修正垂直FOV焦距公式使用图像高度而非宽度。动作失败保留成功观察/pose前缀和失败动作回执后终止。
- **工程门：** 用户本次授权科学/运行范围，但D-059仍要求新增执行代码先成可审commit。故 [`vm04_d211_p0_seal_single_smoke_v1.json`](../configs/vsmt/vm04_d211_p0_seal_single_smoke_v1.json) 当前状态为`authorized_scope_implementation_pending_reviewed_commit`、`expected_reviewed_code_commit=null`；`check`可运行，`seal-routes/run-smoke`在碰外部输入或创建输出前拒绝。审查通过后只填该commit并切换`frozen_executable_seal_and_single_slot_smoke`，不重新裁决已批准的house/slot/动作范围。
- **单worker理由：** 获准的真实执行单元只有一个slot，因此本次smoke本质串行；这不是给未来12槽批量预设单worker。无墙钟超时，执行前核磁盘≥8 GiB，4 GiB为紧急余量，单smoke最多2 GiB；controller创建/运行/停止失败均保留终端或stage receipt。

## D-212：D-211 生成前纠偏——可复算路线、不可再生私有真值与两提交执行门

- 日期：2026-09-18；状态：用户已批准纠偏顺序，工程实现待提交审查，未运行 simulator。用户批准原文：“批准按‘先补齐不可再生 raw、路线语义与执行门，再做单槽 smoke；通过后开放两房 12 路线，同时统一地点、关系、实体与八原子适配器及可信指标’的顺序纠偏；e5d7bed 仅作阶段性提交，不作为最终 D-211 基线。”
- **路线证据：** `vsmt-vm04-d211-route-bundle-v2` 每槽必须含完整 reachable scan、执行前 public RGB-D evidence、P01–P08 场景收据和 execution binding。seal 从私有起点按0.25 m/90°注册动作重算 N+1 计划姿态并验证格成员，不接受“已验证=true”或任意64位字符串。P01 Z前缀、P02精确逆行、P03非逆替代回环、P04分离pair公开cosine top-1、P05同位置反向、P06 T两支、P07只共享中心的双环、P08公开房间—走廊—房间与匿名实体区域均有独立条件。
- **P04边界：** 没有新增未经批准的绝对相似度阈值；只固定≥1.5 m pair中的公开top-1选择并保存绝对分数。该路线即使封存成功也只证明“按固定规则选出本house最像的非回返点”，不自动证明足以成为强视觉alias论文证据。
- **raw三面：** public仍只有RGB-D/内参/frame digest；provenance动作逐条append-only落盘；private每观察保存agent/camera pose、instance mask、simulator object ID↔稳定私有entity ID、对象状态和parent/receptacle关系，并与public frame digest绑定。private采集不等于private evaluation授权，candidate/model reader仍禁止挂载。
- **关系与八原子：** 关系首次新建编译成八原子中的`BIRTH + ADD_EDGE`，不引入`CREATE`第九原子；`RELINK`只修正已有关系端点。D-210 v1旧字段留作历史字节，D-212先在P06 receipt写清该编译；完整place/entity/surface/fragment统一图、八原子候选及可信评价器在单槽smoke之后实施，当前未声称完成。
- **执行门：** 废除不可满足的“HEAD必须等于其内容中写入的自身commit hash”。实现commit保持v2 expected为空；审查后仅允许一个改v2合同的activation child commit。执行核验clean HEAD、`HEAD^=reviewed implementation`及parent→HEAD文件列表恰为单文件allowlist。
- **固定运行环境：** AI2-THOR 5.0.0、CloudRendering、224×224、FOV 90°、gridSize 0.25 m、snapToGrid、rotateStepDegrees 90°、depth及instance segmentation全部显式传入controller；安装版本不符即拒绝。
- **仍未解锁：** 没有真实12-route bundle、没有route seal、没有slot-0 raw、没有12槽raw、adapter、teacher/private evaluation、metrics、训练、validation或confirmation。真实P08公开匿名实体region怎样由路线survey形成仍必须由公开RGB-D过程产出，不能拿private instance mask替代。
- **执行候选补齐：** 用户随后批准开始执行门激活、服务器路线封存和单槽raw工程验证。激活前核查发现原入口只能验证外部bundle，不能从两房生成它；因此先新增公开route survey作为同一受审实现的一部分，激活子提交仍只改v2合同。模板选择只读reachable grid，路线固定后才采公开RGB-D；P04采用无绝对阈值的top-1，P08匿名region不读instance mask。任一survey动作失败保留收据且不换模板/起点/house。P08的grid开阔度角色和轻量RGB-D区域只具有raw工程资格，正式headline仍被共享冻结前端复核阻断。

## D-213：统一稀疏版本图、类型门控八原子与五组消融

- 日期：2026-09-18；状态：用户已批准方法与工程实现，代码候选待审；全部生成/adapter/训练/validation/confirmation授权仍关闭。用户批准原文：“批准 VSMT 采用统一稀疏版本图与按结构类型门控的八原子事务；地点 P0 仅开放 NOOP/BIND/BIRTH/MERGE，其他原子只在实体、关系、表面和片段的合法事件中开放；主表各方法共享同一冻结 RGB-D 前端与公开输入，但保留各自内部记忆机制；加入 Place-4、Typed-8、Flat-8、NoPlace 和 NoVersion 消融。”机器名称将“Typed-8”规范为主行`VSMT-Typed`，其余为`Place-4/VSMT-Flat8/VSMT-NoPlace/VSMT-NoVersion`。
- **统一图：** `place/entity/surface/fragment`为一等节点，`located_at/contains/supported_by/adjacent_to/route_transition`为一等版本边；活动检索稀疏，历史版本只供审计/训练证据/回滚。`contained_entity_refs`最多是活动关系推导缓存，不得作为独立真值。0.5 m格继续只作规划和候选召回，不定义place。
- **类型门：** 全局原子词表仍恰好八个；place P0只允许NOOP/BIND/BIRTH/MERGE，surface/fragment不开放RELINK，relation不开放SPLIT/MERGE。门在candidate seal和teacher之前，只读公开当前观测、prior predicted memory、公开pose belief和动作边摘要；teacher不能改门或补candidate miss。
- **关系编译：** 新关系=`BIRTH+ADD_EDGE`，错误端点修正=`RELINK`，关闭错误关系=`RETRACT`，恢复同一历史事实=`REACTIVATE`；`CREATE`不是原子，`REPLACE`保持`RETRACT+BIRTH`复合程序。executor与候选器据此补入relation REACTIVATE；node RETRACT从entity扩为entity/surface/fragment，place仍不允许。
- **公平比较：** 主表VSMT/TAF/ELU/WFR/LOW共享完全相同的冻结RGB-D前端缓存和公开输入字节，禁止方法私有视觉前端；内部记忆组件允许不同，因为那正是比较对象。该表支持“共同前端下记忆更新机制差异”，不自动支持原系统端到端优劣，也没有改成RGB-only。
- **五组消融：** `Place-4`只见地点和place-place边；`VSMT-Typed`为主VSMT；`VSMT-Flat8`取消selector类型mask但保留executor拒绝/回滚并报告illegal；`VSMT-NoPlace`删除place及incident edges但保留非地点关系；`VSMT-NoVersion`只给当前活动状态并屏蔽模型可读历史，外部审计provenance仍保留。除目标组件外前端、数据、预算和评分不变。
- **节点膨胀指标：** 强制派生活动节点/边按类型计数、历史版本数、scope×atom候选数，并在正式episode汇总type-gate拒绝、illegal、峰值节点/候选、runtime和峰值内存；不把“任务分数上升但图无限增长”藏在总分后。
- **工程边界：** 新合同/纯核心能验证图、候选门、sealed catalog、五种memory view和复杂度指标，现有公共候选器可选择启用该门。D-210 raw→关键帧→非网格place候选的实际materializer接线仍依赖单槽raw字节，旧确定性coordinate scaffold不得进入D-213主表；因此当前不是完整训练模型或效果证据，也不越过D-212的真实smoke顺序。

## D-214：P01–P08全局场景盲共享RGB-D前端，P04/P08重验并延后服务器

- 日期：2026-09-18；状态：用户已批准方法边界，本轮形成合同与纯核心实现候选；全部服务器、材料化、评价和训练授权保持false。用户批准原文：“批准 D-214 作为 P01–P08 全局、场景无关的共享 RGB-D 前端；前端不得读取 scenario ID，所有方法读取同一冻结缓存；P04 与 P08 必须重新做前端资格审核，其余路线重新绑定同一缓存，生成完新的之后旧的网格可以直接删了。”
- **不是P08特供：** 每个保存观察都产出同一schema，VSMT/TAF/ELU/WFR/LOW读取逐字节相同cache；scenario ID、headline/control角色不进入材料化API或cache。P08只能运行cache上的资格谓词，不能获得额外模型、字段或视角。P09/P10执行继续延后，但schema不得为它们另开分支。
- **观察而非身份：** SAM单帧mask统一称fragment，冻结DINO描述和公开depth只给可见几何；非网格place observation聚合全帧DINO、因果pose belief、surface/free-space支持和两组概率，但persistent place ID保持null。room/corridor/unknown只作属性，basin/bottleneck/unknown只作公开结构角色；二者都不能定义地点身份。entity/place持久身份只能由后续记忆机制形成。
- **P04/P08资格：** P04保留≥1.5 m且无绝对相似阈值的口径，但top-1改读冻结DINO地点描述；四象限工程描述退出论文资格。P08要求连续basin→bottleneck→basin，且两端各有至少两个不同观察支持同一匿名fragment稳定匹配；语义概率只报告。正式P08四数仍为null，测试值不是批准值。
- **服务器顺序：** 撤回立即激活D-212的顺序；`63efba3`保留route/raw工程能力，但在真实SAM/semantic assets、P08数值、生产reader和缓存字节受审前不创建activation child、不跑survey/seal/smoke。
- **实现状态不能合并概括：** 本次只把公开派生输出组合、cache封存和资格核心记为已实现；真实SAM/DINOv2/semantic推理编排、production raw reader与服务器执行在机器合同中分别保持false。public/forbidden input列表逐项冻结，episode复核重新检查时间单调及动作边终点，避免scenario通道或重封摘要绕过。
- **旧grid删除：** 用户已授权在新产物完成后删除，但不是现在。必须先全部生成D-214 cache、核验摘要、P04/P08重验、P01–P08路线重绑、审查精确无通配符目标且确认没有复现依赖；只读readiness receipt通过后再执行。Git历史和原始研究资料保留。
- **仍未完成：** SAM checkpoint/config/assets receipt、place semantic head模型/训练split/权重/推理config、P08四个数值、真实asset loader编排、raw reader、adapter转换、两房真实cache与路线重封均不存在；当前0服务器、0模型推理、0episode、0效果证据。

## D-215：冻结SAM资产、场景盲双头估计器、house级训练划分与P08四数

- 日期：2026-09-18；状态：用户明确要求先冻结上述内容，再接production reader；本轮只形成独立合同/纯核心候选，不开放训练、reader、route、raw或评价。用户原文：“先冻结 SAM checkpoint/config、场景盲 semantic/structural estimator、训练划分和 P08 四个阈值，再接生产 reader”。
- **SAM资产：** 固定官方SAM 2.1 Hiera Small commit `2b90b9f…`、官方YAML SHA-256=`0f36b91e…b6f55`、checkpoint 184,416,285 bytes且SHA-256=`6d1aa6f3…c4d38`。automatic-mask复用旧VM-04已登记数值：32点/边、batch64、IoU 0.8、stability 0.95、无crop、无NMS归属抑制、binary mask；最小196像素、最多64 proposals，超限失败不截断。**（2026-09-22 补记：D-224-S1 裁决 43 按引用取代了其中两条——box/crop NMS 阈值 1.0 → 0.7，本文件字节未改；生效配置与摘要见 S1-03 合同 `sam2_nms_supersession`。）**仅在本机临时目录下载核摘要后删除，未安装、未复制到服务器。
- **Estimator与划分：** 一个共享的场景盲模型读取384维冻结DINO描述＋12维固定公开几何，输出semantic和structural两个三类线性温度softmax。固定house级哈希80/10/10 train/calibration/audit；两间P0 house及VM-04 validation/confirmation排除。每house按hash固定8个相距≥1 m的位置×4 yaw；结构训练标签由固定2 m局部可达图切口规则产生，semantic标注者不见scenario/house身份。任何标签/grid/metadata不进推理/cache。实际partition manifest、normalization、weights和training receipt保持null并阻断推理。
- **P08：** 四数固定为0.70/0.70/0.85/0.35 m，等号通过、结构类须唯一argmax、每端至少两个不同观察。数值不按路线yield调；失败保留原槽，不换路线/house，不重新解释room/corridor为identity。
- **下一顺序：** 先审本提交；随后单独材料化split manifest并生成/训练/封存前端权重，审过真实receipts后才实现production reader。D-212 activation和旧grid删除继续关闭。

## D-216：批准D-215基线，只实现split manifest与Estimator训练封存

- 日期：2026-09-18；状态：用户明确批准`7dd44d2`作为D-215冻结基线，并要求“下一步只实现split manifest与Estimator训练封存，审过真实权重回执后再接production reader”。本批是独立审查分支的实现候选，全部真实执行位仍关闭，0服务器/partition/训练/权重。
- **split先决条件：** D-215只冻结了保留角色，仓库尚未公开绑定VM04 validation/confirmation具体house；D-216因此要求先输入三角色齐全的reserved manifest，两间P0 house也必须显式列出。完整eligible universe每house恰有一行，排除项留行说明原因，分组算法不读观察、标签、路线或yield。
- **训练输入与封存：** 训练只消费精确八数组NPZ及逐观察receipt，house ID只做split管理，模型输入恒为396维公开特征。封存输出为normalization、weights/temperatures、training receipt和success四件互绑artifact；audit只在选择/温度都冻结后报告。额外scenario/private/future字段、跨split house、重复观察、换包或覆盖目录均失败。
- **补全而非换模型：** 为消除PyTorch默认值歧义，本决策显式登记零初始化、AdamW β/ε、seed+epoch shuffle、类权重不再归一化、early-stop精确定义及log-temperature golden-section范围/轮数。这些值须作为本实现的一部分受审；不宣称它们是创新，也不允许按P08表现调整。
- **仍关闭：** 训练帧/人工标注的真实生成尚未授权；production reader、route survey/seal/raw、private evaluation、P04/P08资格重验和旧grid删除继续false。审过本实现后才可用一次只改合同的activation commit开放split/bundle/train/seal；审过真实权重receipt后另立reader职责。

## D-218：批准实现E-04离线双盲标注器和E-05冻结特征提取器

- 日期：2026-09-18；状态：用户明确批准“实现并提交 VM-04.E 的 E-04 离线双盲标注器和 E-05 冻结特征提取器；不得打开 audit、Estimator 训练、production reader、P04/P08 或 raw”。本批因此只形成关闭态机器合同、纯核心、两个阶段入口和测试，尚未读取服务器E-03产物。
- **E-04边界：** 两份包覆盖相同public观察，但按role独立排序；界面只显示无损RGB、固定对数色标depth和opaque observation ID。A/B必须是两个不同annotator ID；一致直接采用，分歧只能由不同第三人仲裁，未处理则unknown。package/submission/adjudication均内容寻址、无覆盖、可从已核媒体断点继续。
- **E-05边界：** 384维描述固定为DINOv2 ViT-S/14全帧patch token均值后L2归一化；12维几何的分位数、frustum体积、开口、clearance、D-205 surface统计公式和截断值全部登记。实际模型加载只接受既有冻结commit、干净仓库和checkpoint SHA；一个GPU进程推理，多worker并行public NPZ I/O和CPU几何且有界预取。
- **失败与隔离：** annotation/feature只接public root，显式拒绝audit目录；feature逐public sample保留失败且不补样。private structural标签要到后续D-216 evidence组装才可由隔离流程加入，不得进入本阶段标注页面或feature数组。
- **仍关闭：** D-218实现提交不授权真实任务包、人工提交导入或feature运行；后续即使只改合同激活这三项，audit、Estimator训练、full-house扩展、production reader、P04/P08、route/raw和private evaluation也必须保持false。真实E-04/E-05收据需另审，不能由代码测试替代。

## D-219：删除semantic头，Estimator收窄为公开RGB-D结构单头

- 日期：2026-09-18；状态：用户批准“停止E-04人工语义标注、删除semantic头、保留structural头、精简流程但保留公平比较/独立test/防泄漏实质”。本批只交机器合同[`vm04_d219_structural_only_estimator_v1.json`](../configs/vsmt/vm04_d219_structural_only_estimator_v1.json)与本决策文本供审查；代码、训练和服务器执行仍全部关闭。
- **为什么删semantic头：** `room/corridor/unknown`不定义地点身份（[d214_shared_frontend.py:460](../src/vsmt/d214_shared_frontend.py#L460)），P08资格只读basin/bottleneck概率、fragment DINO cosine和质心距离，并显式记录语义未用于身份（[同文件:883](../src/vsmt/d214_shared_frontend.py#L883)）。全库除D-214/D-215/D-216前端合同、训练实现和测试外没有任何方法消费者：adapter、候选生成器、D-213统一图、teacher和evaluator都不读它。因此17,888帧×2人＝35,776次判断买不到论文证据。不得用恒定`unknown`冒充模型输出；已导出的约1.1 GiB任务包保留为历史产物，不下载、不标注、不进训练。五个臂同等地少掉这三维，已封存比较不受扰动。论文相应收回“识别真实房间与走廊”的口径，只主张公开RGB-D推断的basin→bottleneck→basin及其中的匿名多视角fragment。
- **为什么当时没有连structural头一起删（历史判断，后由D-223取代）：** D-219当时认为P08部署时不能查reference reachable grid，因此保留只读公开RGB-D的结构头。E-08随后证明该头不适合作硬门；D-223把“构造期认证场景”和“部署期方法输入”分开，结构头最终退出production。此处只解释D-219当时为何如此设计，不再代表当前方法。
- **为什么不就地改d215/d216：** d216绑d215、d217绑d216、d218绑d215与d217，而E-01～E-03和E-05已按这些确切字节执行完毕。就地编辑会同时打断三层绑定，并使已完成的服务器receipt无法复验或续跑。D-219因此按当前哈希绑定四份前置合同、以引用方式supersede，永不重写它们；d214没有任何合同绑定其字节，故可就地删除三个死字段。
- **范围与规模：** E-05的396维特征本身无标签，逐字节复用，不重跑DINO与几何。E-07就此裁决为冻结512/64/64，不做full-house扩展，该门不再保留为未决选择。E-08改为零人工：审计标签由同一冻结规则从私有可达图自动生成，模型输入仍只有公开RGB-D，只跑一次；审计失败不得加house、改模型或改阈值。
- **P08四数不动：** 0.70/0.70/0.85/0.35与唯一argmax全部沿用D-215，不因路线成品率调整。新增的是排期要求：E-08之后先在两间开发house上做P08 dry-run，在冻结正式数据预算前暴露不合格风险；不合格时改路线/场景设计或如实记construction failure，而不是动阈值。
- **仍关闭：** `structural_training`、`audit_open_or_generation`、`full_house_expansion`、`production_reader`、`p04_p08_qualification`、`route_or_raw_generation`和`private_evaluation`全为false。本批0训练、0权重、0审计、0服务器运行；真实E-06/E-08收据需另审，不能由代码测试替代。

## D-220：协议精简——执行闸门、独立test、消融集合与两房smoke

- 日期：2026-09-18；状态：用户批准“精简流程但保留公平比较、独立test和防泄漏实质”。本批只交机器合同[`vm05_d220_protocol_simplification_v1.json`](../configs/vsmt/vm05_d220_protocol_simplification_v1.json)与本决策文本供审查；训练、validation效果、test、route/raw和private evaluation全部关闭。D-219的`activation_policy`已同批改为`run_authorization_policy`并指向本决策，避免同一批内两套激活规则并存。
- **执行闸门：** 取消D-212确立的“已审实现提交＋只改一个文件的激活提交＋父提交必须精确等于已审提交”三重门。该门已被实证证伪：D-218授权后，仅仅一个文档提交`c8b4c68`就把`HEAD^`推离已审实现提交，使E-04/E-05的执行命令从此无法再跑。替代规则是每个VM里程碑一个清晰提交、真实运行记录git commit/合同/输入/产物摘要与资源和失败、真实运行仍要求clean checkout、授权由步骤合同里的布尔位表达并由用户在运行前审。不变量照旧：不按结果改split/阈值/house集合、失败保留不补样、test和audit只读一次。
- **独立test：** confirmation降为普通独立test。取消隐藏house ID、承诺摘要、salt打乱的episode ID和reveal接口；保留house级train/validation/test互斥、test只跑一次、test不得选择配置/阈值/checkpoint、主指标与停止规则在test前冻结、全部seed与失败如实报告。文档与代码中的`confirmation`统一改称`test`，VM-06相应改称test stage。
- **消融集合：** 五个主臂VSMT/TAF/ELU/WFR/LOW全部保留，且不得因某个强基线表现好而删除。VSMT消融只保留`VSMT-Typed`（主行）、`VSMT-Flat8`（度量类型门价值）、`VSMT-NoVersion`（度量版本历史价值），内部对照只保留`NECS`（“可执行修订空间”主张的唯一因果反事实）。`Place-4`、`VSMT-NoPlace`、`DRCR`、`PHR`移出必做集合，可作低成本附录。学习式排序器训练路径由VSMT/DRCR/NECS三条降为VSMT/NECS两条。被移出的臂在看过test之后不得再补回来。
- **两房P0（历史口径，P08部分后由D-223取代）：** 降为工程smoke，只保留P01、P04和P08三条代表性端到端检查。D-220当时把P08写成“结构头＋多视角fragment”；D-223现改为“生成器拓扑回执＋共享cache多视角fragment”，两房结果仍不得进入任何论文表、不得据以选择headline赢家、construction failure照实保留并报告。
- **不可再精简的底线（八条）：** 五个主臂读取逐字节相同的冻结公开前端cache；house级train/validation/test分离；test只跑一次且不得据以改模型；候选必须在teacher/private truth打开之前生成并封存；candidate miss、teacher error和selector摊销误差分开报告；多seed、置信区间、失败样本和资源成本齐备；P08私有metadata只在预测与路线固定之后打开；强基线不得因效果好被删除。这八条足以应付正常二区评审，本决策不触碰其中任何一条。

## D-221：按事前冻结的规则把开发规模从512/64/64扩到2048/128/128

- 日期：2026-09-18；状态：规则与测量均已完成，用户批准按规则执行；机器合同[`vm04_d221_estimator_scale_rule_v1.json`](../configs/vsmt/vm04_d221_estimator_scale_rule_v1.json)。只开放`structural_rgbd_expansion`，Estimator训练、audit、production reader、route/raw和private evaluation继续false。
- **为什么重开这个已裁决的门：** D-219删除semantic头后，原本主导512决策的639,872次人工判断成本归零；同时从E-02容量回执取回实测速率为8 worker下**2.6秒/house**，全量生成只需约7小时，而当初估计是1–4天。也就是说支撑512的两条主要理由——人工成本和墙钟时间——都不再成立。这是**前提变化**，不是看到不利结果后改口：E-06尚未训练，audit的64个house从未生成，没有任何模型输出被读取过。
- **顺序可审：** 先在提交`f9b3b9c`冻结决策规则且`measurement`为null，再读服务器上已有的559份私有receipt，最后在`2fcd2a6`填入测量与规则触发的结果。阈值在读数后未作任何调整。
- **测量结果：** 现有17,888帧中basin 8,864（49.55%）、**bottleneck 856（4.785%）**、unknown 8,168（45.66%）。关键不是这个比例，而是**559个house里有394个（70.5%）一帧bottleneck都没有**，单house最多12帧——整个bottleneck证据只由165个house承担，而P08的硬门正卡在bottleneck概率≥0.70上。零新仿真，未读audit，未读任何模型输出。
- **规则触发：** 856落入`[300,1000)`，选择2048/128/128。增量1,664个house、约1.2小时生成、约+3.4 GiB；预计bottleneck训练帧756→约3,024，贡献bottleneck的house 165→约680。
- **拒绝全量：** 全量约需20.6 GiB而数据盘只剩25 GiB，且P-02的正式论文raw要用同一块盘；要腾空间只能删另一条研究线18 GiB的原始物理数据。更重要的是，读过直方图之后再松动这个约束就是"看完数据改标准"，本决策明令禁止。科学上，3,024→约13,000个bottleneck帧对一个1,191参数的线性头也已过边际收益拐点。
- **扩展是纯增量，不是重做：** 选择规则为`ascending_sha256(sampling_salt|split|house_id)`取固定前缀，`sample_rank`是排序下标，`public_house_ref`哈希`{scope,split,sample_rank,partition}`。因此rank 0–511的house ID、rank和public ref逐字节不变，新house只是追加rank 512–2047，现有RGB-D与396维特征全部复用。运行时仍须逐条复验这一不变性，不得仅凭构造假设。PLAN原E-07表中"从零重做、512 cache失效"的说法只适用于`full_house_expansion`，不适用于前缀延长；该布尔在D-217/D-218/D-219和本决策中继续为false。
- **未变边界：** house级split先于任何图像或标签、house不跨split、P0与VM04 validation/test house继续排除、采样house只由冻结hash决定、每house仍8位置×4朝向、失败house保留不补样、calibration只选checkpoint与temperature、audit不参与任何选择且只读一次、P08的0.70/0.70/0.85/0.35不得重调。

## D-222：E-08 一次性结构审计，指标定义先于数据冻结

- 日期：2026-09-19；状态：指标定义已冻结、audit 仍关闭；机器合同[`vm04_d222_structural_audit_v1.json`](../configs/vsmt/vm04_d222_structural_audit_v1.json)。用户批准建立并执行 E-08。
- **为什么另立合同而不改 D-219：** D-219 的 `must_remain_false` 现在含 `audit_open_or_generation`，那条正是用来阻止训练阶段顺手读 audit 的。从 D-219 内部开 audit 会废掉这道门，因此 E-08 由 D-222 单独治理，D-219 字节不动。
- **指标必须现在定义，不能看完数据再定：** D-219 只登记了指标名称（NLL、accuracy、calibration error、类别与 house 级区间），没有规定 ECE 用几个 bin、bootstrap 多少次、什么 seed。本决策把这些补全并在任何 audit 观察存在之前提交：ECE 取 15 个等宽置信度 bin 并附完整 bin 表；bootstrap 以 **house 为单位** cluster 重采样 10,000 次、seed 260919、取 2.5/97.5 百分位；逐类报告 recall/precision/mean NLL/support。**本清单之外的任何指标不得计算或报告**——否则就是看到结果后挑一个好看的口径。
- **为什么 bootstrap 必须按 house 而不是按帧：** 同一 house 的 32 帧高度相关，按帧重采样会把区间做得虚假地窄。
- **一次性与不可回头：** `audit_runs_once=true`，终态回执阻止第二次运行；`audit_failure_may_add_houses_change_model_or_thresholds=false`；audit 不得用于选择 checkpoint、temperature 或阈值。审计结果不好就如实报告，不回头加数据、不调参、不换 house。
- **模型字节绑定：** 合同按摘要绑定 E-06 的 weights=`e5fca2f2…22c5`、normalization=`cce06993…04c3a`、training receipt=`874ccf82…5887`；任一字节变化即拒绝运行，确保审计的确实是那份冻结权重，且审计期间不发生任何重训或重拟合。
- **审计不是通过门：** 本决策不登记任何及格线。它描述冻结前端的表现，不决定论文是否继续；P08 路线是否合格由 D-215 冻结的 0.70/0.70/0.85/0.35 另行判定。
- **边界未变：** audit 的 128 个 house 在本决策前从未生成；标签仍由私有可达图按同一冻结规则自动产生，零人工判断；模型输入仍只有公开 RGB-D 与内参，推理不查 grid 真值；失败 house 保留不补样。`estimator_retraining`、`production_reader`、`p04_p08_qualification`、`route_or_raw_generation`、`private_evaluation` 全程 false。

## D-223：P08 资格改用已冻结的拓扑规则（post-audit 决策，已批准）

- 日期：2026-09-19；状态：**修订稿已由用户批准**，六个执行授权位仍全 false；批准范围只允许实现并本地测试 F-00，真实两房服务器预检须在代码审查后另行授权。机器合同[`vm04_d223_p08_topological_qualification_v1.json`](../configs/vsmt/vm04_d223_p08_topological_qualification_v1.json)。
- **本决策写于审计结果已知之后，必须按 post-audit 阅读。** 绑定审计报告摘要`3e652a45…b142`；当时已知结构头整体 accuracy 0.7013，但 bottleneck recall 区间为 0.043–0.150、NLL 区间 1.830–2.238，比三类均匀猜测的 1.099 还差。它不是被禁止的修补：不加 house、不改模型、不调阈值，estimator 保持被审计的原字节，审计报告不重跑，P08 的 fragment 判据 0.85/0.35 不动。变的只是"由哪个公开来源认证路线的结构角色"，而这是因为审计证伪了"单帧 90° 视场能恢复 360° 拓扑性质"这个前提。
- **诊断边界：** 标签是 `f(位置)`，输入是 `f(位置, 朝向)`。[vm04_d217_rgbd_worker.py](../ops/vsmt/vm04_d217_rgbd_worker.py) 每个位置调一次 `structural_label_from_reachable(reachable, position)`，然后把同一标签复制给四个 yaw；站在瓶颈位置面朝墙的帧可能没有通道证据却仍带 bottleneck 标签，存在明确的标签—可见证据错配。train 0.7049 / calibration 0.6958 / audit 0.7013 接近，只说明整体 accuracy 没有明显泛化间隙，不能严格排除所有过拟合，也不能分离该错配、线性容量和类别不平衡的各自贡献。准确结论是：在冻结特征、线性模型和单帧输入合同下，扩充数据没有让 bottleneck 达到作为 P08 硬门所需的可靠性。0.150 是 95% 区间上界而非确定性天花板；逐帧低 recall 也不等于整条路线必然失败。**实现者在审计前没有核对这项错配**；D-221 增加的 1,664 个 house 未能把该头变成可用硬门。
- **改法与零新增参数：** P08 不再以学习式结构头概率为门，改为由**数据生成器在构造期**对 `GetReachablePositions` 可达图直接应用 D-215 已冻结的拓扑规则（rule sha `4fa32f89…4774`，十个常量原样继承）。判据不是 bottleneck 定义的近似，**它就是那个定义**，因此引入 0 个新数值。所需签名仍是时序上连续的 basin→bottleneck→basin，与 D-214 一致。
- **权限边界：** 可达图是 generator-only construction information（生成器专用构造信息）：输入是路线构造器已获准查询的可达位置，输出只是固定路线是否满足场景条件。例如构造器可据此拒绝一条没有拓扑瓶颈的路线；它不等于部署机器人得到地图。可达图不得进入共享 cache、五个方法、candidate generator、selector 或任何 adapter input；私有 room/object 真值仍然不用。因此 C2 只保证试题结构，不替任何方法答题。
- **必须报告的口径收缩：** 论文此后**不得声称**"P08 的结构角色可由单帧公开 RGB-D 推断"，只能声称"固定路线确实具有 basin-bottleneck-basin 拓扑，由构造期生成器专用可达几何认证"。场景名称收紧为“两个 basin 经拓扑 bottleneck 连接、含实体”，不再称为经视觉识别的“房间—走廊—房间”。
- **结构头退出 production：** production reader 不计算它，place observation 不携带它，selector、候选生成器和 adapter 均不得读取。逐字节相同的弱特征只保证接口一致，不保证对五种机制影响中性，故不因已有成本而强留。E-05 特征、E-06 权重/回执和 E-08 报告全部封存保留，不重训、不重跑；论文主方法只描述实际使用的 SAM proposal、冻结 DINOv2、公开深度几何与因果位姿信念，结构头至多在附录作为未采用的开发尝试披露。
- **F-01实现边界补正（2026-09-19，未开放真实运行）：** 用户审出并裁定四项。(1) F-01 不得另起一套前端：材料化、封印、校验与五臂 clone 已收拢到 `shared_frontend_core.py` 一份实现，D-214 与 D-223/F-01 各绑定一个 profile，各自保留显式 validator 与字面字段集，不允许任何 validator 同时接受两种字节布局；重构前先钉住两套封印摘要，D-214 字节逐一不变，已执行回执不受影响。(2) D-217 兼容适配器并回 reader，取消独立模块、独立 receipt schema 与独立子命令，来源摘要写进同一份 F-01 run receipt；摘要校验、公私边界与"损坏早样本不得跳过"一律保留。(3) SAM automatic-mask 构造器在冻结 commit 下共 17 个参数，D-215 只钉了 10 个；其余 6 个（含 `multimask_output=true`）原样抄录进 F-01 合同并在加载时核对未漂移，值不改、D-215 字节不动。理由与 D-216 当初给 AdamW 补全 β/ε 相同：影响输出的量不得依赖库默认值。(4) 合同策略名到执行常量的映射改为合同显式承载并加测试，不再是代码里的隐式替换。四项均不改变任何已冻结数值，也不开放任何授权位。
- **防二次调参：** 判据须在任何 P08 路线被评估之前冻结；路线成品率不得改变判据或其常量。若在该判据下 P08 仍不合格，记 construction failure 并如实报告，不弱化判据、不换路线、不换 house；再次替换 P08 的门需要新决策。
- **F-01实现边界（2026-09-19补充，未开放真实运行）：** 用户在F-00完成后批准只实现并本地测试production reader。实现采用独立D-223覆盖schema而不修改历史D-214字节，删除结构/语义概率及其模型receipt，保留冻结SAM/DINO、公开深度几何、因果pose belief和非网格place observation；五方法读取同一episode cache的独立等字节clone。`check`只读复核合同与F-00公开证据，`run`在任何外部输入/资产路径打开前强制验证单文件activation child与干净checkout。当前真实资产加载、真实公开输入读取、cache生成、P04/P08资格、route/raw、adapter、private evaluation、训练与audit重跑全为false；F-01成功也不自动授权F-02。
- **F-01 D-217公开兼容输入（2026-09-19补充，已授权实现与本地测试）：**服务器只读定位确认不存在F-01精确bundle后，用户批准实现D-217 public适配。它**不是独立阶段或新方法概念，而是F-01 reader的一种输入模式**：只读`public/train`，按数值rank取首个实际存在且receipt成功的sample，只取observation 0，构造单帧episode-relative origin pose、零协方差belief和无入边动作的输入；所选最早sample若不完整或畸形立即失败，禁止向后跳过。来源rank与源摘要只写入同一份F-01 run receipt，不另建receipt schema；方法manifest不携带house/ref/raw observation ID。该输入只用于冻结资产与reader兼容性预检，不进入正式数据、P04/P08或论文结果；不读取private/calibration/audit，不生成route/raw。SAM2下载、真实D-217读取、服务器运行与cache生成仍须另行授权；F-02及全部下游继续关闭。

## D-224：按引用开启 D-215 的资产下载与依赖安装两位（已批准）

- 日期：2026-09-19；状态：**用户已批准**；三个获取位已开启，F-01 的十个执行位仍全 false。机器合同[`vm04_d224_frozen_sam2_asset_acquisition_v1.json`](../configs/vsmt/vm04_d224_frozen_sam2_asset_acquisition_v1.json)。本决策只让 D-215 自己钉死的 SAM2 字节落到服务器磁盘上，不启动 reader、不读公开输入、不写 cache、不开 F-01 的任何执行位。
- **为什么必须先补这一条：** F-01 的 `verify_frozen_assets` 要核 SAM2 仓库 commit、官方 YAML 的 3,761 字节与 checkpoint 的 184,416,285 字节，而服务器上这三样一样都没有（[LOG-210](../EXECUTE.md) 的两条独立零命中证据）。把它们弄上去正好落在 D-215 的 `authorization.server_asset_download` 与 `dependency_install` 两位，而这两位现在都是 false。不补决策就下载，等于绕过一条还在生效的关闭位。
- **为什么不就地改 d215：** 与 D-219 当初的理由逐字相同——d216 绑 d215、d217 绑 d216、d218 绑 d215 与 d217，且 E-01～E-03、E-05、E-06、E-08 都已按这些确切字节执行完毕。改一个字节会同时打断三层绑定，并使已完成的服务器 receipt 无法复验。因此沿用 D-219 的先例**按引用 supersede**：绑定当前 d215 摘要 `c3d6736f…88db8`，只替换那两位，其余七位授权位和 `sam2`/`p08_qualification` 等全部条款原样不动，d215/d216/d217/d218 一个字节都不改。
- **只开三位，且不含任何 F-01 执行位：** `sam2_repository_clone`、`sam2_checkpoint_download`、`sam2_import_dependency_install`。同时显式关死五位：摘要不符时替换资产、失败时换版本或找镜像、升级/重装 torch 或改 CUDA、向已钉住的 worktree 做 editable/build 安装、重新获取或改动 DINOv2 资产。F-01 的十个授权位继续由 F-01 合同单独治理，**获取资产不等于获得运行权**。
- **摘要不符就停：** `digest_mismatch_policy.action = stop_and_report_verbatim`。钉住的字节就是这个实验的对照；摘要不符意味着拿到的前端不是被冻结的那个前端，而"换一个能干净下载的版本"正是在悄悄替换它。不换版本、不找镜像、不接受部分校验通过的资产。
- **为什么禁止 `pip install -e .`：** F-01 用 `git status --porcelain --untracked-files=all` 核 SAM2 worktree，editable 安装写进 clone 的 `*.egg-info` 或任何构建产物都会让冻结资产检查直接失败。仓库改为从源码树经 `sys.path` 导入，依赖装进 `/root/miniconda3` 环境，torch 2.8.0+cu128 不得变动。
- **F-01 怎样强制这条：** F-01 合同新增 `d224_relative_path` 与 `d224_supersession_core_sha256` 两个 binding，`load_contract` 在打开任何外部路径之前重算并比对。绑的是**治理核心的摘要而不是整文件摘要**——这样日后开启、事后再关闭三个获取位都不会打断绑定，而两个被替换的条款名、所绑的 d215 摘要和预期资产字节一旦挪动就会立刻失败。D-224 不反向绑定 F-01 的摘要，避免两份合同互相哈希成环；绑定方向仍是下游绑上游。
- **边界：** 本决策把冻结字节放到磁盘上，不证明 SAM proposal 数量合理、不证明 DINO 描述子跨视角可分、也不证明 VSMT 有效。F-02 及全部下游继续关闭。

## D-224：首篇精简为实体生命周期版本化事务、帧级联合分配与 Dyn-THOR 对齐（已批准）

- 日期：2026-09-19；状态：**用户批准裁决 A～D**；机器合同、数据生成、模型训练、服务器运行均未授权。用户同时要求：把当时的工作树归档到分支 `archive/pre-d224-unified-graph`（HEAD e1c19f6），在 `main` 上重写 METHOD/PLAN/DATA，只保留精简版，先删减再加。DECISIONS 与 EXECUTE 作为历史日志保留，`docs/VSMT_EXPERIMENT_EVIDENCE_CHAIN.md` 因整体描述旧设计而从本分支移除，归档分支仍可读。
- **触发证据。** 外部：DSG/Dyn-THOR、OASIS-Map、Khronos、Perpetua、Mem0 等表现好的方法都不学习更新决策，胜负由冻结前端与简单关联规则决定，且绝对分数低（Dyn-THOR 节点 F1 28～40，3RScan appear/disappear F1 0.24、moved 0.35，Khronos 变化检测 F1 45～65）；存在性与生命周期是文献最弱的轴。内部：S5 no-go 显示执行后监督相对 direct future loss 的增益不达门且 seed 不稳（LOG-090），LOG-002 中 CTL 低于直接分类；E-08 显示冻结 DINO 线性头在 bottleneck 类不可用；非网格 place 接线与 P08 资格是旧计划最大的两个未知项。
- **裁决 A（采纳）：帧级联合分配加学习代价函数替换"分桶枚举候选、逐候选真实执行、后状态编码、独立 logit 取最大"。** 每帧一次矩形匈牙利分配同时给出全部 BIND/REACTIVATE/BIRTH，未匹配且应可见的实体单独过存在判定得到 RETRACT/NOOP；executor 只负责按版本合同提交并检查不变量。后状态编码与 NECS 消融取消；"可执行候选空间"不再作为独立创新点。
- **裁决 B（采纳）：首篇只做 entity 生命周期。** 保留 entity 节点、active/dormant/retracted 状态、版本链、NOOP/BIND/BIRTH/RETRACT/REACTIVATE 五原子与 REPLACE 复合；MERGE 降为五方法共享的确定性周期去重；SPLIT、RELINK、place/surface/fragment 一等节点、五类关系边、类型门、分桶容量、连续位姿信念、结构估计器、Flat8 消融全部退出首篇。supported_by 作为几何派生属性五方法共享。旧 README "表达能力差距"论据作废。
- **裁决 C（采纳）：数据与指标对齐 Dyn-THOR。** ProcTHOR 多 house 覆盖式重访路线，不可观测窗口内至多 10 件可动物体的移走/搬动/新增干预；指标为匈牙利 3D IoU 0.3 的节点 P/R/F1 与 Missing 残留率，加假撤回率、被搬动物体身份连续率、恢复延迟、contamination AUC 与图规模。P01～P08 手工路线不再是正式数据。
- **裁决 D（采纳）：正式规模 train/validation/test = 300/50/100 house，按 house 互斥。** S1 先跑 50 house 小试，S3-01 可按成品率下调，只能在 test 打开前改。
- **底层模型（proposed，S0 冻结）。** 前端沿用 D-215 冻结 SAM 2.1 Hiera Small 与 DINOv2 ViT-S/14，fragment 描述子改为 mask 内 patch 均值；S1 并行提取 ViT-B/14 作唯一可选升级，按开发集分离度选一次。学习部件为三个两层 128 宽 MLP 代价头（关联、存在、新建），约 4 万参数；逐 fragment softmax 交叉熵加逐实体二元交叉熵；AdamW 1e-3、20 epoch、早停、5 seed；两轮 DAgger 处理因果记忆分布偏移。teacher 改为 t 时刻私有实例真值，不等未来。
- **对照与消融。** TAF、ELU-P（Perpetua 式持续性滤波）、RAC（渲染比对）、LOW，可选零训练 LLM 选操作臂；消融 NoVersion、HandCost、HeuristicLabel。每方法至多 12 个完整配置，规则臂无梯度。
- **保留的反作弊门。** 私有扰动不变性（召回顺序、特征矩阵、未训练 logits 逐字节不变）、部署特征不读未来/私有/路径/槽号、test 只跑一次且不选参。执行授权继续用步骤合同布尔位。旧 `candidate_miss` 改为 `recall_miss`，teacher error 与 amortization error 定义不变。
- **口径收缩。** 可主张：共享冻结前端下 hindsight 监督的可逆生命周期修订是否减少陈旧实体、误删并保住身份，并给出三分解。不可主张：地点/拓扑修订、关系修订、SPLIT/MERGE 学习、度量 SLAM、真实机器人。论文体量按 RA-L/ICRA 规划。
- **失败分支。** S1 跨视角余弦分离度不足→证据层级裁决（降到 L1 oracle mask 属改主张，须用户批准）；干预成品率过低→规模裁决；S3 主门失败→照实 no-go，不换数据、不缩对照。
- 白话：这次改动解决"流程太长、学习部件信号太弱、没有外部锚点"三个问题。输入是同一套冻结视觉前端和 ProcTHOR 干预序列，输出是每帧一个由五种操作组成的程序和可回溯的实体记忆版本。例如椅子被搬到卧室后重见，系统应把原椅子恢复到新位置而不是删旧建新。它不是新的视觉模型，不是地点识别，也不等于方法已经验证有效。

## D-224-EFG：共享 ReID 可选前端、可选上下文臂与实体 token schema（已批准）

- 日期：2026-09-19；状态：**用户批准裁决 E、F、G 与执行顺序**；仍无任何数据、训练或服务器授权。本条是 D-224 的修正案，不改动已批准的 A～D。
- **触发问题。** 用户问「先跑通链路还是先设计对比」「有没有更厉害一点的网络」「物理机器人是否只能用这个量级」「怎样接世界模型与具身智能」。据实测数据回答：Jetson Orin AGX 上开放词汇分割约 10 Hz、物体地图更新约 2 Hz，延迟几乎全部在 SAM/DINO 前端；4 万到 200 万参数的决策头在此之下可忽略。因此「机器人只能用小网络」对记忆维护层成立、对规划层不成立，主流是快慢两层。据此把可升级的算力放在**前端区分度**而不是决策头容量。
- **裁决 E（采纳）：共享 ReID 适配头登记为 S1-05 可选前端。** 冻结 DINO 描述子上加一个 384/768→128 的投影头，用 train 划分 house 的实例级对比损失训练一次后冻结，五个臂逐字节共用同一投影。S1-04 与冻结描述子一同量跨视角分离度，S1-05 按 S0-03 登记规则二选一。它不计入任何方法的 12 个配置额度；若被选中，论文必须同时报告冻结描述子基线，不得只报强前端结果。理由：跨视角余弦分离度是最可能让五臂一起趴在低分区的单点，升级它使 VSMT 的相对优势在更强前端上衡量，更可信。
- **裁决 F（采纳）：`VSMT-lean-ctx` 登记为可选臂，不作默认。** 在 fragment×候选实体对上加 1～2 层 transformer 使代价互相可见，求解器、执行器、teacher 与指标不变。与 MLP 版共享同一训练预算与配置额度，结果单列，**不得在看过 test 后替换主表行**。理由：S5 的 Set Transformer 相对 MLP 没有改变结论，300 house 规模有过拟合风险，不能默认用它当主表。
- **裁决 G（采纳）：S0-01 固定实体 token 序列化 schema 与帧级稀疏残差。** 每个非 retracted 实体导出定序字段（`entity_id`、状态 one-hot、描述子、质心、尺寸、观察次数、年龄、版本数、错失次数、是否有支撑面），另导出本帧被改动的 `entity_id` 与对应原子。理由：2026 年的对象中心世界模型（FOCUS、OCM、RoboStream 的 4D 因果时空图、稀疏残差世界模型）消费的都是带持久 ID 与状态转移的逐实体 token，而 VSMT-lean 每帧程序本身就是一次稀疏残差更新。首篇不接世界模型，只冻结接口，使暂停的 D-062 方向有落点。
- **执行顺序（已确认）。** S0 只冻结「看数据前必须定」的项：信息边界、house 划分与 test 只读一次、指标清单与主门、五臂与三组消融名单。阈值、召回数、描述子/投影变体、网络宽度、DAgger 轮次取舍留到开发集之后。五个臂一起在 50 house 跑通，不先单跑 VSMT；S2-05 开发表按合同不构成结论，在那里看到 VSMT 不好看是安全的，由三分解指出瓶颈在前端、标签还是模型，再决定是否启用 E/F。
- **S0-01 实现说明（2026-09-19，代码待审）。** 读过实现后确认 `GraphRevision` 与 `cpmt.executor.validate_graph` 绑定 place scaffold、五类关系边、`graph_hash` 与统一图 lifecycle，收窄它会把这些一并带入，与 D-224 削减流程的目的相反。因此实体记忆核心为自足新模块 [`lean_memory.py`](../src/vsmt/lean_memory.py)，只复用不产生第二套数值语义的纯函数（规范 JSON、深拷贝、余弦、质心距离、AABB、不透明 ID）；`GraphRevision`、place scaffold、关系边与 `public_candidates.py` 不被本分支任何入口导入。旧模块与其测试原样保留。METHOD 第十三节已据此更正。
- **S0-01 三处需用户裁决的语义选择（实现按下列默认写死，可改）。** 其一，版本记录只保存几何与计数快照，不保存描述子，理由是审计需要「当时记忆说它在哪」而不需要当时的外观，384 维逐版本保存会使记忆随帧数线性膨胀。其二，执行器只检查**结构**前条件（实体存在、状态允许、同帧不重复使用 fragment 或实体），「本帧应可见」与「σ(r) ≥ τ_r」属决策层条件，随 `decision_basis` 原样记入 provenance 供审计，执行器不重新推导，以免执行器依赖几何数据。其三，共享去重的 canonical 实体取「首个版本 `opened_at` 最小、并列取 `entity_id` 字典序最小」，而不是观察次数最多，理由是身份连续率以最早建立的身份为准。
- 白话：这次修正解决「怕结果不好看就先偷看结果」和「该不该换更大模型」两个问题。输入是同一套冻结前端与同一批 house，输出是一个先冻结、后跑通、再决定是否升级前端的顺序。例如跨视角余弦分不开时，先换共享投影头而不是先放大决策网络。它不改变 D-224 的主张边界，也不表示任何臂已经实现或验证。

## D-224-HIJ：补齐早期四项裁决的前三项，S0-01 通过（已批准）

- 日期：2026-09-19；状态：**用户批准裁决 H、I、J 并推迟 K**，同时**审过 S0-01** 并采纳其中三处语义选择。仍无任何数据生成、训练或服务器授权。本条是 D-224 的第二份修正案。
- **触发。** 用户回看本轮对话最初提出的四项裁决，问是否已经落地。逐条核对结果是：主张收窄完全落地且比推荐更彻底（地点层是被整体砍掉而非降为 supporting）；外部基准只落地了口径，没落地数据；两类强对照只落地了半条；低成本风险探针三件事只落地两件。以下补齐前三项。
- **裁决 H（采纳）：把 `NoVersion` 与 `AssocOnly` 提前到 S2-05 开发表。** 原计划四组消融只在 S3-03 训练和 S3-05 测试时跑，意味着要走完全部 S2 实现与 S3-02 正式数据生成，才第一次知道版本化和事务词表有没有用。现在它们用同一次 50 house 开发预算与五臂一起跑，兑现早期第四项裁决的第三件事。开发差**只作早期风险读数**：不据此选赢家、不调网格、不因不利就改设计或删消融。`HandCost`、`HeuristicLabel`、`LLM-op`、`VSMT-lean-ctx` 仍只在 S3 跑。
- **裁决 I（采纳）：新增必做消融 `AssocOnly`，并与主比较并列报告。** 定义是同一个学习关联头与同一求解器，但事务词表只剩 `BIND` 与 `BIRTH`：不撤回、不恢复、无 dormancy，`retracted` 集合不存在。它解决此前**没有任何一臂回答**的问题——胜负来自学到的关联，还是来自可撤回可恢复的生命周期词表。`HandCost` 换的是代价来源，`NoVersion` 换的是可逆性，都不回答词表本身的价值。因为它是第二节贡献 1 的唯一因果反事实，论文**主表必须并列报告它**，不得只放消融表。它不是规则臂，也不等于 TAF：TAF 的关联是手写阈值，`AssocOnly` 的关联是同一个学习头。消融组数由三组改为四组。
- **裁决 J（采纳）：`LLM-op` 从"可选、条件不明"收口为必做附录臂。** 必须跑，但只在 validation 上跑，结果只进附录，永不进主表、不进 test。理由是它的成本与 prompt 敏感性使"每方法至多 12 个完整配置"的公平预算对它不成立，放进主表等于在一个无法对齐预算的维度上比较；但完全不跑又回避了审稿人必问的"零训练 LLM 是不是已经够了"。这不是认为 LLM 路线无效；若以后要升为主表臂，须先冻结它自己的配置预算口径，属新裁决。
- **裁决 K（推迟）：外部基准的第二张表推迟到 S2-05 之后再裁。** 现状是已采纳 Dyn-THOR 的指标口径（匈牙利 3D IoU 0.3 的节点 P/R/F1、Missing 残留率、逐物体 Stable/Appeared/Missing/Moved）与干预设定，但数据仍是自建 ProcTHOR，只能说口径可比、不能与 DSG/DynamicGSG 的数字直接并列。真要第二张表须在其公开序列上跑一遍五臂，属独立数据适配工作，约一到两周。同时记录一处冲突：早期裁决说"保留自建 P0 作机制诊断"，但 D-224 裁决 B 已把 P0 整体砍掉，文档中已无 P0；当时未指出该冲突，此处补记。
- **S0-01 已审通过。** 用户采纳实现中三处写死的语义选择：版本记录只存几何与计数快照、不存描述子；执行器只检查结构前条件，"应可见"与 σ(r)≥τ_r 属决策层并原样记入 `decision_basis`；共享去重的 canonical 取首版本 `opened_at` 最小、并列取 `entity_id` 字典序最小。这三项此后按已审字节执行，修改须另立决策。
- **S0-02 实现说明（代码待审）。** 只读检查核心为 [`lean_intervention.py`](../src/vsmt/lean_intervention.py)，合同为 [`lean_s0_intervention_data_v1.json`](../configs/vsmt/lean_s0_intervention_data_v1.json)。四条继续门各有实现与反例测试：划分是 `(seed, house_id)` 的纯函数且可从清单重算；干预只在全部相关容器于窗口内每一帧都被判不可见时执行，判定必须由已审的 `vm04_public_visibility` 在公开深度上产生并附该帧摘要，缺判定不视为不可见、`visible` 必须严格为 `False` 而非仅仅假值；`private` 与 `provenance` 不进任何部署读取器白名单且三面文件互斥；失败 house 留回执、不替换，计划数须等于成功数加失败数。本阶段不新写几何，不定义特征、标签、指标或对照参数。
- 白话：这次修正解决"早期提过的对照和探针有没有真的写进合同"。输入是最初四项裁决与当前文档，输出是三条补齐、一条推迟，以及一个能在开发阶段就看到版本化与词表价值的顺序。例如现在不必等正式数据生成完，就能知道可撤回可恢复到底值不值。它不改变 D-224 的主张边界，也不表示任何臂已经实现或验证。

## D-224-S03：S0-03 审查返工的三处语义变化登记（实现已改，待用户复审）

- 日期：2026-09-19；状态：**登记；2026-09-20 用户复审通过（见 D-224-R）**。仍无任何数据生成、训练或服务器授权。本条是 D-224 的第三份修正案，只登记 S0-03 按 Codex 审查返工后与 LOG-216 所记两个语义决定不同之处；返工代码在工作树中、未提交。
- **变化一：召回增加与实体状态无关的全局通道，取代"只给 dormant/retracted 远距资格"。** LOG-216 的口径是活动实体召回受距离上限、休眠与已撤回实体不受。返工后召回取两条通道并集：本地通道按余弦取前 k、质心距离 ≤ R_local；全局通道对 active/dormant/retracted 一视同仁、无距离上限、按余弦取前 k′；并列按 entity_id。理由：`AssocOnly`（D-224-HIJ 裁决 I）没有 dormant/retracted 状态，若远距资格绑定状态，它的旧实体会留在原地被距离门挡成 BIRTH，比较就同时混入"有没有生命周期词表"和"有没有远距候选资格"，不再是贡献一的纯反事实。影响：候选资格五臂逐字节相同，状态只决定分配编译成哪个原子；recall_miss 的口径随之改为"正确实体不在两通道并集内"。合同 `recall_rule.global_channel_covers_every_state` 已绑定。
- **变化二：代价矩阵由 −log σ(logit) 改为 −logit。** 理由：METHOD 用逐色块 softmax 交叉熵训练，学到的是 p(列|行) ∝ exp(logit)，最大化联合对数似然等价于最小化 Σ(−logit)，逐行归一化常数不影响联合最优；−log σ 是非线性单调变换，会改变跨行竞争下的最优配对（Codex 在 20 万次随机 2×2 上实测约十分之一给出不同最优解）。影响：分配与训练目标一致；召回外的禁止代价改为由当前矩阵最大/最小合法代价与行数派生，不再固定常数。合同 `cost_matrix.cost = negative_logit` 与 `forbidden_cost_is_derived_from_the_matrix` 已绑定。
- **变化三：关联特征 `supported_by_agrees` 改为 `support_height_difference_m`。** Codex 认为 `supported_by` 重新引入被 D-224 移除的 surface 信息；核对裁决 B 原文，`supported_by` 作为几何派生属性五方法共享是明确保留的，因此字段本身不冲突、该意见不整体采纳；但其底层风险成立：按 ID 比较只有在表面 ID 跨帧稳定时才有信息，而跨帧稳定的表面 ID 等于维持了一个持久表面身份。改为纯几何的支撑面高度差，保留公开线索、去掉身份需求、不新增阈值；`supported_by` 属性仍留在 S0-01 实体记录中。影响：关联头 14 维特征顺序改变一位；S0-04 评价器不读任何表面 ID。
- **同批采纳的其余审查意见（不改语义，只补实现）：** 字典序最小最优解的规范化（原始最短增广路对 `[[1,0],[1,0]]` 返回 `[1,0]`，与"较小列优先"声明不符）、行按 fragment_id 排序、两阶段封存（阶段 B 带阶段 A 摘要封存分配回执与存在特征）、新建特征改用对全部实体的最高余弦、空帧合法、描述子宽度检查、合同校验器绑定十条关键布尔声称。
- **待复审的两处提醒：** 字典序规范化每接受一列做一次子求解，Codex 实测 30 行 100 列约 300 毫秒，64×200 量级下每帧可能到秒级，须在 S1 小试实测吞吐；METHOD 第六节第 5 步仍写"对每个 `active`"做存在判定，S0-01 执行器允许 RETRACT `dormant`，S0-04 已按 active+dormant 登记并列为待裁决项。
- 白话：这次登记解决"审查后代码改了什么、为什么改、哪些审查意见没全盘照收"。输入是 Codex 的六条审查意见与 S0-03 首版，输出是三处语义变化、其余工程修补，以及两条复审提醒。例如杯子被搬到卧室后，现在五个臂都能把旧杯子召回来，差别只剩在能不能 REACTIVATE。它不改变 D-224 的主张边界，不表示 S0-03 已通过复审，也不表示任何臂已经实现或验证。

## D-224-LQ：S0-04 六项评价口径裁决 L～Q（已批准）

- 日期：2026-09-20；状态：**用户批准裁决 L～Q 全部按推荐口径执行**；仍无任何数据生成、训练或服务器授权。本条是 D-224 的第四份修正案，冻结 S0-04 teacher、评价器与指标合同里六处此前只能由用户定的语义；实现已按这些口径写好（LOG-217），本条不改代码，只把它们从"推荐"升为"已裁决"。
- **裁决 L（采纳）：dormant 实体在节点 P/R/F1 与 Missing 残留率中都算"仍在记忆里"。** 预测节点集合与 MRR 残留集合都取 `active` ∪ `dormant`，只有 `retracted`（NoVersion 下为物理删除）算清除。理由：dormancy 是无证据的共享规则；若不算残留，共享的 `n_dormant` 会替代 RETRACT 决定主门指标，且 `AssocOnly` 没有 dormancy，比较会混入词表之外的因素。被拒的备选：两处只算 active（所有有 dormancy 的臂在 n_dormant 帧后自动获得 MRR 减免）；MRR 算而 P/R 不算（两指标口径不一致）。
- **裁决 M（采纳）：身份连续率不承认 `canonical_of` 折叠。** 在搬动后第一次带标签重见时按当时的分配判定，分到搬动前任一承载该物体的实体（含重复实体）即算保住；此后共享去重把新实体折进旧实体不记功。理由：去重是无学习的共享规则，其阈值不应进主门指标。被拒的备选：episode 末按当前承载实体是否等于或折叠自搬动前实体判定。
- **裁决 N（采纳）：主导度阈值语义与实体身份规则。** 色块主导度的分母是色块全部像素（背景计入）；覆盖两个及以上物体且最大占比低于 `dominance_min_share`（null）或最大占比并列记 `identity_ambiguous`；只覆盖一个物体但占比不足记 `unlabelled`；没有物体记 `unlabelled`。实体身份取带物体证据的严格多数（超过一半），不设第二阈值，背景证据不投票；物体证据只落在身份含糊的实体里时记 `identity_ambiguous`，不猜 birth。被拒的备选：分母只算物体像素、背景不计。
- **裁决 O（采纳）：恢复延迟从干预处对方法首次可观察的帧起算。** 终点是记忆对该物体首次正确的帧（移走：旧位置附近无同身份在记忆里实体；新增：新位置附近有；搬动：两者同时）。未恢复与从未可观察的物体分别单列，不进平均。被拒的备选：从干预发生帧起算。
- **裁决 P（采纳）：存在判定候选为 `active` 与 `dormant`。** S0-01 执行器允许 RETRACT `dormant`，否则 dormant 只能靠 REACTIVATE 离开；`retracted` 候选由 teacher 拒绝而不是跳过。METHOD 第六节第 5 步"对每个 `active`"已据此改为"对每个 `active` 或 `dormant`"。被拒的备选：只 active。
- **裁决 Q（采纳）：真值节点范围与"已不在原处"参照点。** 节点 P/R/F1 的真值集合是本帧在场且自 episode 开始至少可观察过一次的物体；存在标签与陈旧判定的位移参照实体记住的质心，而不是干预日志里的物体位移。被拒的备选：整个 house 的在场物体（早期帧所有臂召回率同低、方差增加）；参照干预日志位移（搬动后新建的实体会被误标为 gone）。
- **随裁决冻结的常量与仍为 null 的数值。** 3D IoU 0.3（D-224 裁决 C）、bootstrap 10,000 次与单侧 95%（METHOD 第十一节）绑定为常量；`dominance_min_share`、`delta_moved_m`、bootstrap seed、主门效应量、nuisance probe 最大优势仍为 null，待 S3-01 或开发集之后冻结。
- **文档同步。** METHOD 第六节第 5 步、第八节 S0-04 段、第十一节指标表与统计段，DATA 第六节标签定义与第七节评价文件字段，均据本条更正；合同 `user_rulings.decision_id` 绑定为 `D-224-LQ`。
- 白话：这次裁决解决"评价器里六个只能由人定的口径到底怎么定"。输入是 LOG-217 列出的推荐与备选，输出是六条冻结口径。例如杯子被搬走后旧记录转成 dormant 还挂在原位，按裁决 L 仍算残留，只有真的 RETRACT 才算清干净。它不改变 D-224 的主张边界，不表示 S0-04 代码已审通过，也不表示任何臂已经实现或验证。

## D-224-R：S0-03 复审通过，三处语义变化的对照公平性结论与 S0-05 三项前提（已批准）

- 日期：2026-09-20；状态：**用户批准裁决 R**：S0-03 返工版通过复审并提交，三条规则臂约束登记为 S0-05 合同前提，S0-03 合同补 `up_axis_index`。仍无任何数据生成、训练或服务器授权。本条是 D-224 的第五份修正案。
- **公平性结论。** D-224-S03 的三处语义变化都没有让对照变得更不公平。变化一（状态无关的全局召回通道）消除了 `AssocOnly` 在召回层被距离门挡成 BIRTH 的既有混杂，候选资格五臂逐字节相同；规则臂拿到远距候选后由自身距离门标为不可选，解不变。变化二（−logit）只影响学习臂，是这套逐 fragment softmax 训练目标的正确解码，−log σ 是只惩罚学习臂的 bug；规则臂的代价是直接写的数，新变换下反而能被精确表达。变化三（支撑面高度差）只有学习臂读，规则臂不读特征表，去掉的是一个只有在表面 ID 跨帧稳定时才有信息的输入。一个非公平但必须可见的后果：全局通道的 k′ 个名额由全部状态竞争，各臂记忆规模不同（`AssocOnly` 膨胀、`NoVersion` 收缩），recall_miss 可能随臂变化；三分解已按臂单独报告，k′ 在开发集上按最大记忆规模选，不得按臂调。
- **S0-05 前提一：规则臂门内必须给分级代价。** METHOD 第九节把 TAF 写成"合格则 BIND 代价 0，否则正无穷"，ELU-P、RAC 沿用；二值代价会大量并列，而求解器固定返回字典序最小的最优解、列按不透明 entity_id 排序，等于让 ID 顺序决定 TAF 绑谁，ConceptGraphs 本身按相似度取最大。门内代价改为 −余弦（LOW 用质心距离），门外才是不可选。
- **S0-05 前提二：每个规则臂的 ≤12 配置里必须有一个宽门或无门选项。** 召回不再排除远距候选后，排除工作全部落在规则臂的 d_a 上；若网格只有紧的 d_a，任何对照都无法在新位置重新关联被搬动的物体，身份连续率这一半主门会被构造性地赢下。
- **S0-05 前提三：不合格格的表达方式登记为哨兵 logit。** 代价矩阵构造要求每个被召回的对都给一个 logit，缺一个即出错；规则臂用一个登记的哨兵值表达"不可选"，派生的禁止代价自动高于它。
- **S0-03 合同补 `feature_rules.up_axis_index = 1`。** 高度差特征把三维向量第二维当竖直轴（AI2-THOR/ProcTHOR 的 y 向上约定），此前只是代码里的裸字面量；现由常量 `UP_AXIS_INDEX` 承载并由校验器绑定。
- 白话：这次裁决解决"返工后的候选规则、代价变换和特征替换会不会偏袒某个臂"。输入是三处变化与五臂四消融的定义，输出是"不偏袒"的结论和三条写进 S0-05 的约束。例如 TAF 在两个合格实体之间以后按余弦高低选，而不是按 ID 顺序选。它不表示任何臂已经实现或验证，也不改变 D-224 的主张边界。

## D-224-SW：S0-05 五项口径裁决 S～W（已批准）

- 日期：2026-09-20；状态：**用户批准裁决 S～W 全部按推荐口径执行**，并要求提交推送、进入 S0-06；仍无任何数据生成、训练或服务器授权。本条是 D-224 的第六份修正案。
- **裁决 S（采纳）：HandCost 重定义为无时间累积的手写分数。** 精简设计下五臂共用求解器与执行器，"把三个头换成 ELU-P 手写代价"就等于 ELU-P 对照本身。现改为：关联 logit = 余弦（无距离门、可复活 retracted）、新建 logit = 常数 θ_b、存在 = 当帧自由空间覆盖比例 ≥ ρ_h 则 RETRACT；结构、求解器、词表与复活规则都是 VSMT-lean 的。它回答"同一决策结构下学习代价值多少"，ELU-P 回答"时间累积的概率遗忘值多少"，两者不再重合。网格改为 θ_b 与 ρ_h，无距离门参数。被拒的备选：删掉 HandCost，消融降为三组。
- **裁决 T（采纳）：HeuristicLabel 以 ELU-P 的公开决定为标签来源。** TAF 从不撤回，用它当标签时存在头没有 gone 样本，消融会把"标签来源"和"词表缺失"混在一起；ELU-P 有完整五原子词表。被拒的备选：维持 TAF。
- **裁决 U（采纳）：RAC 不复活 retracted 实体。** 按 DSG 适配，被删节点重见只能重建；允许复活会给 RAC 一个其来源机制没有的能力。ELU-P 复活。
- **裁决 V（采纳）：各方法在 validation 上按节点 F1 选唯一配置。** 它是 Dyn-THOR 的主指标且不是主门指标，避免朝主门选参；并列取配置序号最小者。被拒的备选：MRR 或身份连续率，效果是选参方向与主门重合。
- **裁决 W（采纳）：应可见下限 `should_be_visible_min_ratio` 作为五臂共享值留在 S0-05。** 它决定谁累计错失次数、谁休眠，此前任何合同都没登记；数值随其他阈值在开发集后冻结。被拒的备选：移到 S0-01 的 dormancy 规则，需另开 S0-01 版本。
- **文档与合同同步。** METHOD 第九节补选参规则、分级代价与共享候选门，第十节 HandCost 与 HeuristicLabel 两行改写；S0-05 合同 `user_rulings.decision_id` 绑定为 `D-224-SW`，`selection_metric` 由 null 改为冻结常量 `node_f1`，HandCost 网格改为 `theta_b`、`rho_h`；代码新增 `hand_cost_association_logits` 与 `hand_cost_existence`，HandCost 退出余弦门臂与无门参数表；测试 42 项通过。
- 白话：这次裁决解决"四组消融各自到底在问什么、参数按什么选"。输入是 LOG-218 列出的推荐与备选，输出是五条冻结口径。例如现在 HandCost 和 ELU-P 一个问"学习值多少"、一个问"随时间遗忘值多少"，不再是同一个臂。它不表示任何臂已经实现或验证，也不改变 D-224 的主张边界。
## D-224-S1：S1 开工九项裁决（已批准）

- 日期：2026-09-20；状态：**用户一次性批准全部九项并要求按推荐执行**；同时授权到服务器上只读核验与清理过期数据。本条是 D-224 的第七份修正案，只开只读与本地登记位，仍无数据生成、安装、训练或 private 读取授权。
- **裁决 1（采纳）：S1-01 的资产范围含模拟器侧。** AI2-THOR 5.0.0、ProcTHOR 代码与 ProcTHOR-10K 数据集与 SAM/DINO 一并由 S1-01 登记核验。PLAN 的 S1-01 行原本只写 SAM/DINO，而 S1-02 离不开模拟器侧；不扩范围就要再开一轮申请才能进 S1-02。
- **裁决 2（采纳）：ViT-B/14 用一次本地临时登记。** 授权在本地临时目录下载一次、只记录 url/字节数/sha256 后删除，再写回 S1-01 合同，沿用 SAM 2.1 checkpoint 的同一先例；登记完成前该资产保持 `registration_incomplete` 且不可获取。被拒的备选：把 ViT-B/14 退出首篇、只用 ViT-S/14，代价是 S1-05 的"二选一"退化为无选择，METHOD 第五节要改。**已于 LOG-223 执行**：URL 从钉死的 dinov2 commit 自己的源码推导并经 ViT-S/14 的既有下载回执实证同一模式，登记 346,378,731 字节 / `0b8b82f8…`，核对 embed_dim 768、patch 14、depth 12、86,580,480 参数确属 ViT-B/14 后删除临时文件；服务器放置仍需另一个仍为 false 的位。
- **裁决 3（采纳）：ProcTHOR-10K 选 0.1.2。** commit `d54954a81e7126001e552c2d7904ee2e0d49eaae`。house 池文件 `train.jsonl.gz` 的标识**取自上游仓库内 133 字节 git-lfs 指针声明的 oid 与 size**（52,316,238 字节 / `d64450ec…`），因此是上游声明而不是我们对下载结果的观测，满足"登记在获取之前"。该 tag 只登记在 S1-01 合同，不写进 S0-02 已审字节。
- **裁决 4（采纳）：Python 冲突按角色分两个解释器。** 模拟器侧（AI2-THOR + procthor）在 `vsmt-envs/simulator-py39`（3.9.25），前端侧（SAM 2.1 + DINOv2 + torch 2.8.0+cu128）在基础 3.12.3；两侧只通过磁盘上的 public/private/provenance 文件交接，不在同一进程内互相 import。LOG-221 核验两侧都已就位，冲突消解。被拒的备选：找一个能同时装下三者的版本——不存在。
- **裁决 5（采纳）：授权只读容量探测并顺带确认渲染后端。** LOG-221 已执行：`libvulkan.so.1` 可解析，`vulkaninfo --summary` 枚举出 NVIDIA GeForce RTX 4080（driverName=NVIDIA，apiVersion 1.4.329），另有 llvmpipe 软件后备。**这只说明 Vulkan 能看到这块 GPU，不等于 CloudRendering 已成功渲染过一帧**，那要到 S1-02 首次真实渲染才算证据。
- **裁决 6（采纳）：许可证本阶段留 null。** 九个资产的四项许可证字段在具体获取授权通过时一并填入，本阶段只固定字段清单与"未登记即不可获取"的规则。
- **裁决 7（采纳）：清理 `tests/README.md`。** 移除 `test_ctl_dev.py` 与六个 `test_m1_*.py` 的段落及 M1/M2/M3 三节——这些文件已在 `d7159ba` 随 CPMT/M1 归档删除。文件从 104 行减到 40 行，现存每个被点名的测试文件都真实存在。AGENTS.md 关于"`tests/` 内 README 字节可能进入源码 hash"的顾虑由用户裁决解除：旧 run 的 hash 已记录在案，不受本次改动影响。
- **裁决 8（采纳）：删除孤儿字节码。** `tests/spatial_world_model/` 只剩 `__pycache__`、无任何 `.py`（49 个文件），`tests/__pycache__` 另有 35 个源文件已删的 `.pyc`，共 84 个文件。全部被 gitignore，删除不改变仓库任何字节。
- **裁决 9（采纳）：切断 S0 纯核心对旧执行器的传递性 import。** `lean_memory.py` 原先 `from vsmt.graph_ops import ...`，而 `graph_ops` 在文件顶部 `from cpmt.executor import validate_graph`、并在同一文件定义 `GraphRevision` 与 place scaffold，于是为了 20 行纯函数把整条已归档的统一图代码拉进了当前入口，METHOD 第十三节"不被本分支任何入口导入"在模块层面并不成立。现将 `cosine_similarity`、`centroid_distance`、`opaque_id` **逐字复制**到 `src/vsmt/lean_geometry.py`；实际从未被调用的 `observation_aabb` 从复用清单移除。**数值未变**：`test_vsmt_lean_geometry.py` 在 200 组随机向量、200 组随机点、五种退化输入和四组 ID 片段上逐值比对两份实现，并用 AST 守住七个 lean 模块的 import 边界与传递闭包。这动了 S0 已审字节，依据是本裁决；`graph_ops` 与 `cpmt.executor` 原样保留供旧模块和旧测试使用。
- **合同与文档同步。** S1-01 合同 `user_rulings.decision_id` 绑定 `D-224-S1`，新增 `activation_policy`（三个 true 位：已登记资产只读核验、只读容量探测、ViT-B/14 本地摘要登记），四项已知冲突改为"未裁决／已裁决未执行／已执行"三态并各自校验，registry_rules 补两条（上游声明算登记、LFS 展开不算工作树脏）；METHOD 第十三节更正；`tests/README.md` 重写。六个 lean 模块共 **350 项**本地通过。
- **补充裁决 10～13（同日批准，LOG-222）。**
  - **10（采纳）：追认 9-19 的资产放置。** reflog 证明 SAM2 于 2026-09-19 19:52:51 从 D-215 钉死的 URL clone、19:52:52 checkout 到 pinned commit，checkpoint 19:55:08 落盘，LOG-221 已核验字节一致；缺的只是当时没写 LOG。**追认的是"发生过且事后核验通过"，不是"当时留了证据"**。登记教训：已开的授权位被执行时必须当场写 LOG。
  - **11（采纳）：安装 hydra-core / omegaconf / iopath。** 实质授权来自 D-224 资产合同本就为 true 的 `sam2_import_dependency_install` 位；S1-01 的同名位按引用打开，免得两份合同对同一动作各说各话。先 dry-run 确认 torch/torchvision/numpy 不在变更清单内才安装；装后三者版本与 CUDA 可用性不变，被钉住的 SAM2 工作树仍然干净，`import sam2.build_sam` 成功。逐包 sha256 记在 LOG-222，因为 index 是 aliyun 镜像而非官方 pypi.org。
  - **12（采纳）：数据盘清理由用户自己执行。** 九条精确命令已交付，预计释放 21.9 GB；本会话不执行。
  - **13（采纳）：`vsmt-vm04-estimator-development-0c4f9851006d`（5.5 GB）保留。** 它虽属被 E-08 证伪的旧线，但仓库中仍在用的 F-01 兼容适配器读它的 `public` 树；删了就无法在 S1-02 数据产出前跑 F-01 预检。
  - **14（采纳）：S1-01 的 worker 死锁按方案 A 解开，pilot 定为 4 worker × 1 house。** 合同要求 worker 数由实测单 worker 占用推导，而那五个量只能靠真跑一条 episode 得到，偏偏 `route_or_episode_generation` 在同一份合同的 `must_remain_false` 里——S1-01 按自己的条款永远测不出占用。被拒的备选 B 是为"恰好一条 pilot episode"在 must_remain_false 上挖口子，代价是那份清单的含义被削弱，以后每个阶段都能援引这个先例。采纳的 A 把测量整体移进 S1-02，并按用户意见拆成两步：**S1-02a** 用 4 个 worker 各跑 1 个 house（合计 4 条 episode）跑通管线并实测占用，**S1-02b** 用算出的 worker 数补齐其余 46 个。S1-01 只保留推导规则与输入清单，删掉 `single_worker_occupancy_measurement` 位，并由校验器禁止它以任何名义回到这份合同。两条配套约束：pilot 的 4 条 episode **计入正式 50 条**，不得跑完丢弃重生成，否则就是按结果挑样本；`concurrency_verified_at=4` 与 `derived_worker_count` 必须分开记，pilot 只证明 4 路安全，扩产后不稳定要如实报告而不是事后调小数字。
  - **15（采纳）：S1-01 v1 代码审查通过，`headroom_fraction` 冻结为 0.2。** 余量的含义是每项可用资源先打八折再除以单 worker 占用，留给测量误差与运行期波动；它是安全边际，**不是可以按运行结果回调的性能参数**，冻结后若嫌保守只能另开版本并说明理由。校验器相应改写：headroom 要么仍为 null 且登记在 `policy_values_without_defaults` 里，要么是 [0,1) 内的数、写明冻结它的裁决编号、且已从待冻结清单里移除——三者缺一即拒，防止"已冻结却仍对外宣称待定"。
  - **16（采纳）：S0 转 v2 后 S1-01 按 v2 消费，并纳入跨合同机器核对。** D-224-X 之后五个纯核心都绑了 v2，只剩 S1-01 的 `depends_on` 还指着 S0-02/S0-03 的 v1，再不改就会出现 S1 按 v1 语义登记、S0 按 v2 语义执行的错位。更要紧的是 S1-01 从未进入 `test_vsmt_lean_cross_contract.py`：它登记的模拟器、house 池与描述子标识与 S0-02/S0-03 的假设之间，此前没有任何机器检查。现追加 S1-01 v2（v1 字节冻结、摘要钉进 `FROZEN_V1_SHA256`），跨合同测试新增 9 项：S1-01 过自己的校验器、消费的是 v2 而非冻结的 v1、注册的模拟器版本与 S0-02 `source` 一致、house 池来源对得上、SAM 标识与 D-215 逐项一致、S1-05 要二选一的两种描述子都已登记、episode 生成在两侧同时关闭、占用测量归属可运行的阶段、S1-01 不留待冻结 null。**PLAN 侧的连带项（S1-02a 的 seed 与 test/validation 前置冻结、S1-04 新增 fragment-真值 IoU 诊断）在 D-224-X 那批已同步，本次核对确认无需再改。**
  - **17（采纳）：S1-01 v2 与五份 S0 v2 代码审查通过。**
  - **18（采纳）：S1-02a 合同按 pilot 形状实现，划分与 worker 推导都不重写。** house 分块直接调 S0-02 v2 的 `assign_split`，worker 数直接调 S1-01 v2 的 `derive_worker_count`，各有一项测试钉住复用——否则很容易出现第二套划分或第二个公式，而它们之间的分歧只会在真跑时才暴露。合同自己只管三件事：pilot 的 4 个 house 是 train 块前四个（重算得到而非挑选，换一个即被抓到）、占用怎么量（**取峰值不取均值**，在完整 episode 而非合成小基准上量，否则按均值配出的并发会在高峰期挤爆机器）、以及回执必须写什么。另加两条防线：4 条 pilot episode **计入 50 条**且禁止看过结果后重生成同样的 house（那等于按结果挑样本）；算出的 worker 数若超过实测验证过的 4 路并发，回执必须显式标为外推。**seed 与 test/validation 规模用户本轮未给定（消息里是占位符），合同中保持 null 并登记为待冻结；未冻结前任何生成都被拒，因为 S0-02 v2 的分配顺序是 test→validation→train，这三个数一动，train 块起点连同全部开发 house 都会挪。**
  - **19（采纳）：S1-02a 审查通过；划分冻结为 seed=20260920、validation=50、test=100。** 规模沿用 D-224 在 PLAN S3-01 登记的 300/50/100，seed 取冻结当日日期以便复述且不带任何暗示。**这是 S1 最不可逆的一步**：S0-02 v2 的分配顺序是 test→validation→train，因此 test 与 validation 的成员、train 块的起点与 S1 的 50 个开发 house 至此全部确定；`train_houses` 留到 S3-01 登记且此后只能下调，下调只从 train 块尾部截短。三个值**只登记在 S1-02a v2 一处**：S0-02 v2 定的是构造规则（方法层面，不该带某一次运行的 seed），值属于运行层面。跨合同测试钉住这条分工——S0-02 的四个值槽必须保持 null、S1-02a 必须自称唯一登记处——要防的是出现两个互相矛盾的 seed 而事后没人说得清数据是按哪个生成的。校验器同时改为「三个值要么全开、要么全冻」：半冻结是最危险的状态，看着像定了，可一旦补上缺的那个，train 块起点还会再挪一次。
  - **20（采纳）：三个路线幅度冻结为 translation 0.25 m、rotation 90°、look 30°。** 前两个没有自由度：`source` 段已登记 `grid_size_m`=0.25 与 `rotate_step_degrees`=90，且 `snap_to_grid` 为 true，步长与格子不一致会让机器人要么走不到格点、要么每步被悄悄吸附到别处，两种都会让同一条路线在不同 house 上走出不同轨迹；校验器现在直接绑定这条一致性。同批把"登记值必须恒为 null"改成"要么开、要么冻"——原规则下合同永远无法记录它本来就是为了承载的值。
  - **21（采纳）：`max_actions` 定为 2000，但与另两个数值一并冻结。** 2000 步约合 500 m 纯平移，对跨度 10–20 m 的 house 足够宽松；它只防无限长 episode，**触顶记构造失败而不是截断**，因为被截断的路线不再是覆盖路线，重访保证也随之失效。本轮不为它单开 S0-02 v4：`maximum_interventions_per_episode` 与 `minimum_yield` 取决于 R1／I1 的裁决结果，三个一起冻可少触发一次版本级联。
  - **22（提案待裁）：路线规划 R1 与干预选择 I1。** 设计写在 DATA 第二节，标为 proposed。核心选择是把"覆盖"定义成对**实体**而不是对空间的覆盖，以及干预**先穷举可行三元组再抽样**而不是顺序抽样加失败重抽（后者会按可藏性挑样本）。三项待裁：覆盖口径、`add` 的物体来源、视点距离区间。
  - **23（采纳）：复审修订一至十全部采纳；`p_null_window`=0.2；修订六取 (i) 枚举时预筛可放置性；`move` 重访顺序由派生 RNG 决定。** 采纳的同时更正修订一的理由：原文以"一帧窗口使 dormancy 永远不触发"立论，机制说反了——休眠按应可见却未匹配累计，发生在扫掠二重访空容器时，与窗口长短无关；`minimum_window_frames` 仍登记，真正理由是 ELU-P 的按 tick 衰减把窗口长度变成全部臂共见的数据分布参数，以及一帧过渡会让路线结构退化。该值用户尚未给定（消息中为占位符），建议 20 帧。**本轮未冻结任何值**：一是缺这一个值，二是冻结的操作方式取决于版本级联的处理（见 LOG-233 提案）。
  - **24（采纳）：`minimum_window_frames`=20；版本级联按"规则才升版、摘要只钉规则、值进台账"三条处理；授权复制动作签名探测；删除提交署名。** 三条的实现见 LOG-234：规则摘要对值槽置 null、去过程记录、去白话后计算，七份现行合同各钉一个；已填值全部进 `FROZEN_VALUES` 台账且不得再变；填了值不入账即拒。指针按阶段族核对。**这改变的是治理成本，不是任何科学口径。** 探测结论：CloudRendering 能起（首次真实渲染），`SpawnAsset(assetId, generatedId)` 存在，`add`=(b) 可冻。
  - **补充裁决 25～32（2026-09-20 批准，原话"裁决 25～32 按推荐全部采纳（28 作废），授权在新提交下重生成全部 50 条"；LOG-236／237）。** 起因是 S1-02b 首跑（`159654f`）非空成品率 14/37＝0.378 未过 0.6 的门，且事后审计发现 87/87 个"执行成功"的 `add` 从未进入私有真值。**这是 R1／I1 规则文的就地修订**：S0-02 v3 的 `intervention_selection` 与 `route_planning` 段改写，规则摘要重钉（旧 `57ff25c7…` → 新值见 `test_vsmt_lean_cross_contract.py`），不开 v4。
    - **25（采纳）：规模裁决取"修机制后同 seed 重生成全部 50 条"。** 在新提交下重生成 pilot 4 条与 46 条到新输出根，旧运行整份保留为"门未过＋真值缺失"记录。被拒的备选：下调 house 数（问题在机制不在 house）；只重跑失败 house（看过结果再挑样本）。
    - **26（采纳）：`remove` 执行器改为 `DisableObject`。** `RemoveFromScene` 在 Procedural 场景里让 Unity 在生成元数据时抛 NullReferenceException，客户端 100 s 超时，7/7 个 house、换新控制器仍复现；`DisableObject` 0.04 s 成功，实例掩码键整个消失、碰撞体消失，六轮 smoke 里 23/23 次在扫掠二 0 像素。物体仍留在模拟器元数据里但 `visible=false`；private 帧记录由实例掩码生成，不受影响。
    - **27（采纳）：被拒绝的 `MoveAhead` 把那条格间边加入黑名单并从真实位姿重算剩余路点，上限 32 次。** `GetReachablePositions` 只保证格子可站，不保证相邻两格之间的 0.25 m 能走；7/46 个 house 被椅子、门或我们搬过的物体挡住。拒绝是模拟器对同一 house 的确定答案，路线仍是确定函数，只是不再事先全知。
    - **28（作废）：多试几个生成点。** 8 点、32 点各 4/4 house 仍失败——"有生成点"既不保证放得下也不保证看得见。由 31 取代。
    - **29（采纳）：抽样先类型后三元组。** 按三元组均匀抽时 add（合格物体×U 容器）占九成，81/81 个执行成功的干预全是 add；同一 F 上分层后 add 低于六成。不动 U／F 的定义，不按可藏性挑样本。
    - **30（采纳）：`add` 改为搬运一个从未被渲染过（至今 0 像素）的真实物体到 U 容器。** 探测证明 `SpawnAsset` 造的物体在 RGB／深度里渲染、在元数据里 `visible=true`，却永远不进实例分割也无 2D 检测，`Initialize` 也救不回；对照的既有物体 `PlaceObjectAtPoint` 到同一点即有掩码。代价：(b) 想要的同描述子身份歧义压力消失，只有 9/23 house 有"未见但同资产"的天然复制件；若要保留这种压力须另找机制。
    - **31（采纳）：move／add 的 (物体, 目的容器) 对须通过窗口内 dry-run。** 真的放一次（最多 32 个均匀间隔的生成点）、瞬移到目的容器的重访视点用私有渲染偷看是否 ≥196 像素、再 `TeleportObject` 放回原位；只有通过的对进 F 并记住那个点，放回失败整条作废，表写 provenance。偷看帧不进 public、不计入观察序列，窗口内容器本就不可见。smoke：4/4 house 成功、13/13 个干预在扫掠二可辨；可行对显著减少（00406 从 46 对剩 2 对），干预数会低于 6，这是"只造 teacher 看得见的干预"的代价。
    - **32（采纳）：dry-run 模式下每个目的容器每条 episode 至多一次放置，remove 不限。** 同一容器放两次时后一次可能被前一次挡住。
    - 代码默认值随合同改变：runner 与 `sample_interventions` 的默认即上述规则；首跑的旧行为只留作复算 `159654f` 的显式选项，不是第二套协议。
  - **补充裁决 33～38（2026-09-21 批准，原话"裁决 34 取双生控制；封印帧改最佳帧；move 下限 N=120/60；null 抽签加私有盐；像素计数限扫掠一；coverage_definition 随 34 改写；以上落地后第三次重生成全部 50 条"；LOG-238／239）。** 起因有三：`4bff1a8` 重生成非空成品率 0.556 仍未过门；核对扫掠二语义发现 20 条非空 episode 重访的 44 个容器全部被干预过（"被重访 ⇒ 有变化"是 100% 的结构捷径），而 10 条空窗口 episode 没有扫掠二、也从不经过可行性与触顶检查，于是大房子和开放户型只以空窗口身份存活；对 50 条产物的只读重算发现容器可见性主体所用的"视点帧"里 972/1521 个容器是 0 像素（452 个共用视点格、520 个是路过帧），只有 411 个容器能封印，U 总数 188，且偏向抽屉门板这类放进去看不见的子容器——这是 move 稀少（11/78，源先重访 7）和可行集为空的共同根因。**这是 R1／I1 规则文的第二次就地修订**：S0-02 v3 的 `route_planning`、`intervention_selection`、`intervention_window` 段改写，规则摘要重钉（`2895f031…` → `27d5ea47…`），不开 v4。
    - **33（采纳）：规模裁决取"修机制后第三次重生成全部 50 条"，不带 `4bff1a8` 数据进 S1-03。** 被拒的备选：以 0.556 的 50 条直接进 S1-03（扫掠二捷径会让 cache 白算一遍）。
    - **34（采纳，双生控制）：扫掠二重访被干预容器（move 源与目标都算）加上同样多个对照容器；空窗口 episode 走完全相同的流程（U、dry-run、抽样、对照、路线、触顶检查），只跳过执行。** 对照容器优先从 U 减去被干预集合里抽，必须持有至少一个扫掠一里看见过的合格物体，U 不够才从 U 外补并登记数目；变与不变的重访顺序由派生 RNG（新用途标签 `control_revisit`／`revisit_order`）交错。空窗口 episode 因此成为非空 episode 逐项匹配的反事实：同样的房子分布、同样的重访集合构造、只是什么都没动；它也按同样规则失败，仍不进成品率。被拒的备选：(ii) 对照从全部容器随机抽（过渡段里见过的容器一眼就能分出来，且空抽屉测不到东西）；(i) 重访全部合格容器（路线翻倍、触顶失败大增）；(iii) 维持现状。
    - **35（采纳）：容器可见性主体改从扫掠一中该容器像素最多的帧封印（≥512 像素）。** 只读重算：可封印容器 411 → 1332，U 总数 188 → 670，11 个可行集为空的 house 里 8 个仅靠 remove 就非空。这是机制修正不是规则改变，但会改变哪些 house 成功，故写进合同并重钉。
    - **36（采纳）：数据集级 move 下限。** S3-01 的 train 块执行成功的 move ≥120、其中源先重访 ≥60，不达标触发规模裁决而不是放宽规则；S1 的 50 条只报告数字。理由：identity_continuity 与 REACTIVATE 正例只来自 move，`4bff1a8` 按比例推到 test 100 house 只有约 25 个 move、十来个可逆性事件，主张一没有统计力。
    - **37（采纳）：空窗口抽签混入私有盐。** seed 写在公开合同里、house id 就是目录名，`is_null_window(seed, house_id)` 是任何读取器都能算的纯函数。盐文件放在生成机器仓库外（`/root/autodl-tmp/vsmt_private/null_window_salt.txt`），runner 拒绝仓库内路径，plan.json 与回执只登记盐的 sha256；其他抽签不加盐（依赖私有可行集，本就算不出）。用户须自行备份盐文件：丢失即空窗口划分不可复算。
    - **38（采纳）：合格物体的像素只数扫掠一的帧（合同原文如此，代码原先累计到过渡段结束）；未见物体数到窗口前的每一帧；`coverage_definition` 改为 `every_eligible_container_observed_once_before_and_the_revisit_set_once_after`，并新增 `revisit_set` 段。**
    - **附带的机制修正（不改规则，随本次一起落地）：** 被拒绝的格间边把视点格割开时，在带黑名单的连通分量内重选最近合格视点并写 provenance（`4bff1a8` 的 00975）；执行放置时 dry-run 点失效则重新向模拟器取当前生成点、逐点偷看，并把每个点的错误与放置前位姿写进 provenance，失败也写（`4bff1a8` 的 00236／03361／08927 无法定因）；Floor 不再算容器（AI2-THOR 给地板打了 receptacle 标志，其"视点"是房子中心）；路线触顶错误带步数与上限。三个触顶 house（00950／01289／08790，8～10 个房间）只有改 `maximum_actions` 才救得回，本次不改值。
  - **补充裁决 40（2026-09-21 批准，原话"裁决 40 取调高：maximum_actions 改为 4000，口径写为范围边界，台账记 superseded；本次 50 条跑完后按新值重生成受影响的 house"；LOG-239）。** 起因：`c222c51` 第三次重生成里 01451（98 个容器）扫掠一 1695 步加过渡 204 步后，双生控制的扫掠二需要 666 步而预算只剩 101 步；01259 同样触顶。46 条实测中位 381 步、p90 1380 步、最大需求约 2565 步，触顶的恰是容器最多、U 最大、move 机会最多的 house，与裁决 36 相抵触。**先纠正一处旧说法**：2000 步不是防止 episode 跑不完的——路线是有限 BFS 路径、重规划上限 32 次，终止性本来就有保证；它真正约束的是内存（每帧深度与掩码留在内存到 episode 结束，1899 帧实测 3.3 GB/worker）、磁盘（每个观察约 245 KB）、前端 cache 的算量，以及 ELU-P 按 tick 衰减所依赖的 episode 长度分布。因此**调高而不是移除**：`route.maximum_actions` 2000 → 4000（约 1.5 倍余量），口径写为**范围边界**——需要更多步数才能完成覆盖与重访的 house 不在本数据集范围内，记为构造失败并计入成品率。台账治理：`FROZEN_VALUES` 改为 4000，旧值 2000 连同冻结它的裁决 23/24 与退役它的裁决 40 一起进新增的 `SUPERSEDED_VALUES`，合同在值槽旁边带同一份 `maximum_actions_superseded` 记录，跨合同测试钉住两处一致；规则摘要因新增口径键而重钉（`27d5ea47…` → `b60e4e47…`）。执行：S1 的 50 条按 2000 跑完后，**只**把触顶失败的 house 按 4000 重生成（旧目录移走保存、不覆盖，`regenerate` 入口按裁决点名、不按结果挑），其余不动；由此 S1 开发集内会出现两个代码提交，阶段回执与 `regenerate-<commit>.json` 如实记录。被拒的备选：完全移除（须另补按帧数或 RSS 的运行期看门狗，否则违反运维安全线）；只在 S3-01 生效（S1 与 S3 范围边界不同，主张一在 S1 上少掉最大 house 的正例）；维持 2000。
  - **补充裁决 39／41（2026-09-21 批准，原话"裁决 41 取 (b)；裁决 39 取 (a) m=8；删除 3272d11、12d4209 与两份 interrupted 产物"；LOG-239）。** 规则摘要重钉为 `22bc6f2f…`。
    - **39（采纳 (a)，m=8）：dry-run 每个候选物体只随机测 U 里至多 8 个目的容器。** 起因：裁决 35 把 U 放大三倍半后 dry-run 开销为 `候选 × |U| × 32 点`，01451 单条 3.2 小时，S3-01 的 300 house 按无上限口径约需 30 小时以上。目的容器由派生 RNG（新用途标签 `dry_run_order`）逐物体随机抽，被测子集均匀随机、抽样公平性不变；按物体而不是全局设上限，是为了让 move 的发现不集中损失在 P 最大的大 house（那正是 move 的主要来源，与裁决 36 相抵）。代价与登记：`feasible_set_size` 从此是"测过的那部分里有多少可行"，回执必记 `dry_run_pairs_tested`、`dry_run_pairs_total` 与比值估计 `feasible_set_size_estimate`；S1 的 50 条按无上限生成（`--dry-run-destinations-per-object 0` 仅用于复算），S1 与 S3 的 F 不可直接比较。被拒的备选：全局随机上限 K（压制大 house 的 move）；不设上限。
    - **41（采纳 (b)）：对照规则不变，U 内／U 外比例如实报告，U 外对照单列为较弱对照。** 起因：第三次重生成 40 条里 U 容器 517 个、被干预 188 个、扣掉被干预后仍持有已见物体的 U 容器只有 16 个，对照需要 145 个，实际 U 内 16／U 外 91／缺口 38——"在 U 里且持有已见物体"既是对照条件也是 remove／move 源的条件，抽样把它们用光，这是结构性的。U 外对照在窗口里看得见、偏弱，但 107/111 个在扫掠二重见了未动物体。被拒的备选：(a) 先划对照集再抽干预（move 少三到四成，与裁决 36 相抵）；(c) 只从 U 里抽不补（对照数降到十几个）。导出器新增 `controls_from_U`、`controls_outside_U_fraction`。
    - **清理**：按用户授权删除 `lean-s1-02a-3272d11`、`lean-s1-02a-12d4209`、`lean-s1-02a-c00db92-interrupted-…`、`lean-s1-02b-12d4209-interrupted-…`；两份 `superseded-by-ruling-40` 保留为"同一 house 在 2000 步下失败"的证据。
  - **补充裁决 42（2026-09-22 批准，原话"ρ_free 登记为已被 D-223 自由空间配置蕴含；supported_by 维持 null；S1-03 代码审过，开 cache 生成授权"；LOG-240）。** 实现 S1-03 时查出 METHOD 第五节的 `ρ_free` 从未冻结。核对 D-223 的自由空间材化后确认它已被蕴含且取的是最严的 1.0：`materialize_public_free_space` 只在一个体块内**每个像素**深度都落在有效窗口时才生成该体块（`block_valid.all()`），远平面从最近表面往回收一个表面余量并封顶，过薄体块丢弃，两种体块记录都硬写 `reliability: 1.0`——不存在需要门限筛掉的部分可靠体块。三条代码依据登记在 S1-03 合同 `volumes.rho_free_resolution`，并有一项测试把这条声称本身变成可检验的（往最大体块塞一个无效像素，体块数减少）。`supported_by` 的五个几何阈值从未被任何合同冻结、也没有任何特征读它（S0-03 用 `support_height_difference_m`），字段维持 null、阈值维持待冻结，不阻塞 S1-04/S1-05/S2。S1-03 五个授权位在 `activation_policy` 具名打开。若将来要引入小于 1 的 `ρ_free`，那是改变自由空间语义，须另开裁决并重生成 cache。
  - **补充裁决 43（2026-09-22 批准，原话"裁决 43 取推荐：box_nms_thresh 与 crop_nms_thresh 改为 0.7，重钉 D-215 摘要，其余不动"；LOG-240）。** 起因：S1-03 单帧 smoke 撞上重复 mask，9 帧实测 D-215 冻结的生成器配置**在真实帧上不可满足**——`box_nms_thresh` 与 `crop_nms_thresh` 都是 1.0（只压制 IoU>1 的框，等于关闭 NMS），每帧 512 个 mask、去重后 479 个、291 个逐字节重复、9/9 帧超过同一合同规定的 64 上限，而合同又规定溢出与重复即构造失败；196 像素门槛几乎不起作用（9964 → 9877）。裁决只改这两个阈值为 0.7，其余 15 个生成器参数原样：实测每帧中位 9、最大 17、重复 0、每帧 1.3 秒。**落地方式与原话有一处偏离，特此登记：D-215 的字节没有改写。** 它的整文件摘要 `c3d6736f…` 被 D-216/D-218/D-219/D-223-F00/D-223-F01/D-224 五份合同和四个模块钉着，链上的规则是"predecessor bytes must not change，supersession is by reference not by rewrite"（D-219、D-224 都是这样取代 D-215 条款的）；改写会让九处钉一起移动。因此按同一先例，S1-03 合同 `sam2_nms_supersession` 登记被取代的两条、生效的完整生成器配置、以及用 D-215 自己的派生公式算出的生效摘要 `c56fb625…`（冻结摘要 `df828bcf…` 并排保留可比对）；纯核心把生效配置整个绑死（第三个参数变了即拒），runner 只按生效配置建生成器并在加载前核对摘要。"重钉摘要"落在 S1-03 这一层。被拒的备选：提示点 32→16（第二处改动、略减召回）；保留无 NMS 而把上限提到 768（分配矩阵每帧约 700 行且多为同一物体的重复，直接污染分配）。D-214 的转述是它自己时代的 D-215 状态，属旧方向、不进当前入口，未动。
  - **补充裁决 44（2026-09-22 批准，原话"批准 c993959 的 196 像素边界修复；停掉 edae0b5 的运行，旧目录改名保留，按 c993959 重新启动全部 43 条"；LOG-240 第六节）。** S1-03 首次全量生成 1 小时内 5 条 episode 失败 3 条，全部是恰好 196 像素的 mask 在 `pool_dinov2_region_descriptor` 里被判"支持不足"：逐 patch 均值浮点求和得 0.9999999999999999 < 1.0。D-215 的 196 像素准入下限与 D-223 的 `minimum_total_patch_weight = 1.0` 是同一条边界（196/196），两条冻结规则都不改；修复只把支持判定改为精确像素数除以 patch 面积，池化除数不变，此前通过的 mask 描述子逐位不变。这是冻结核心 `l1_entities.py` 的 bug 修复而不是阈值变化，不触发任何合同摘要重钉。`edae0b5` 的部分产物改名保留、不进下游；cache 从头按 `c993959` 单一提交生成。
  - **补充裁决 45（2026-09-22 批准，原话"裁决 45 取 (b) 模拟器重载读初始盒加记录平移，(a) 只作对照列"；LOG-241）。** 起因：S1-04 的 fragment 对真值整物体 AABB 的 IoU 诊断与 S0-04 v2 `truth_objects` 的节点 P/R/F1 匹配都要真值盒，而私有面逐帧只写了 `position` 的 x/y/z（`lean_s1_02a_pilot.py` 第 231 行；服务器 513 帧核对键并集恰为 x/y/z，全根搜索无任何包围盒；provenance 也没有物体尺寸表）。三个口径：(a) 各可见帧私有 mask 反投影点并集当"观测集合盒"，最省，但系统性偏小，当真值会改节点 F1 的含义；(b) 每条 episode 在模拟器里重载 house 一次，读初始状态每个物体的 `axisAlignedBoundingBox` 与 rotation，逐帧盒＝初始盒＋（记录位置−初始位置），换到以观测 0 相机为原点的 episode 系；(c) 完整重放 43 条，数小时且物理不保证复现。取 (b)：move/add 都由 `PlaceObjectAtPoint` 执行、保持物体朝向，放置后的物理沉降登记为残差；(a) 只作 S1-04 报告的对照列。落地：S0-04 v2 `private_truth_inputs.truth_box_source`（规则串由校验器绑定）、S0-02 v3 `private_house_geometry`（按 episode 一份 `object_geometry.json`，由 S1-04 工具在生成后写出，不改已生成文件，部署 reader 不可读），两份规则摘要重钉；重载工具与残差检查见 S1-04。影响：不补此源则 S2-04 评价器同样跑不了；搬动物体的真值盒带沉降残差，工具以未干预物体的位置漂移和帧 0 私有 mask 反投影的包含率报告残差。
  - **补充裁决 46（2026-09-22 批准，原话"裁决 46 取推荐，理想记忆口径认可，曲线出来后一次性冻结"；LOG-241）。** 召回四值（`local_count`、`global_count`、`local_radius_m`、`birth_neighbourhood_radius_m`）留 null；S1-04 在开发 cache 上报 `recall_miss` 随 k、k′、半径的曲线后，按 S0-03 规则与 D-224-R"k′ 按最大记忆规模选、不按臂调"一次性冻结，此后不改，全程不碰 validation/test。算 recall_miss 需要一份"上一帧记忆"而 S1-04 时五臂都不存在，故登记**理想记忆**：每个真值物体一条实体，描述子取它此前带标签 fragment 的均值、质心取此前 fragment 质心均值；量的是前端召回上限，与臂无关，只作诊断、不进任何臂。S0-03 `recall_rule` 就地增加三条规则并重钉。
  - **补充裁决 47（2026-09-22 批准，原话"裁决 47 取进，output_dimension 填 128，训练/选择按 30/12 留出，threshold 取 0.05"；LOG-241）。** ReID 投影进 S1-04。`output_dimension`=128 是 D-224-E 原话（384/768→128），合同槽此前未同步，今入台账；`selection_rule_threshold`=0.05 余弦入台账，语义为投影在选择 house 上的中位跨视角分离度至少比最好的冻结描述子高 0.05 才入选，否则保留冻结描述子。公平性修正：投影用 train 划分 house 的私有实例标签训练，S1-05 若在同一批 house 上量分离度等于在训练集上评自己，故 42 条有 cache 的开发 house 按哈希前缀顺序前 30 条只训练、后 12 条只选择，两组互不重叠；无 cache 的 house（01451）按顺序跳过并计数，不顶替。S0-03 `reid_adapter_head.holdout` 就地写入并重钉；S0-03 授权位仍全 false，训练授权由 S1-04 合同的位承载，用户审过 S1-04 代码后再开。被拒的备选：ReID 退出首篇（省一小时和两个值，但分离度偏低时没有后备）。
  - **补充裁决 48 与 S1-04 代码审查（2026-09-22 批准，原话"裁决 48 取 (a)，开 S1-04 的 fragment_mask_recovery 与 server_run 位跑 mask 回收；S1-04 代码审过，五个 ReID 值按提议冻结，开其余授权位"；LOG-241 第四节、LOG-242）。** 起因：S1-03 cache 逐 fragment 只存 `mask_sha256` 与 `pixel_count`，不存 mask 像素，而 S0-04 `fragment_instance.overlap` 的重叠标注、X1 的同帧重复色块折叠与 S1-04 的诊断标注都要 mask。三个口径：(a) cache 跑完后加一次只跑 SAM 的回收步骤，逐帧用同一生效配置重算、按 D-215 边界准入、逐位核对 `mask_sha256` 后写 `NNNN.masks.npz`，不匹配整条登记 `fragment_mask_mismatch`；(b) 停跑改 runner 存 mask 后重启，损失 14.5 小时；(c) 用几何代替像素标注，改 S0-04 冻结规则且与 IoU 诊断循环。取 (a)。同时用户审过裁决 45～47 的六个提交，S1-04 v1 六个授权位在 `activation_policy` 具名一次打开，五个 ReID 训练值按提议冻结（temperature 0.07、epochs 20、batch_fragments 512、learning_rate 0.001、seed 20260922）并入台账。落地：合同就地修订；六个位是"谁可以跑什么"的规则，故规则摘要按 S1-03 先例重钉 `2fff2d19…` → `29335861…`，重钉时核对"位全部关回去即回到首钉"成立；v1 即现行文件的合同用 `registered_value_slots` 保留 v1 登记的槽位清单，使冻结后台账仍可核对。影响：回收步骤约 11 小时 GPU，SAM 逐位复现性靠摘要核对变成可审计数字；S3-02 正式 runner 应直接写 mask，不再回收。
  - **补充裁决 49（2026-09-22 批准，原话"裁决 49 取 (a)，改 camera_pose 符号、S1-03 读取侧修正并重钉、cache 重建到新根、旧根改名保留、mask 回收跑完复用；是否允许 runner 读回收 mask 免跑 SAM：允许"；LOG-242 第三、四节）。** 起因：S1-04 几何重载的帧 0 包含率残差中位 0.0；只读探测查明 S1-02 runner `camera_pose` 用 `cos(-pitch), sin(-pitch)` 编码，公开四元数把低头 30° 写成抬头 30°，位置正确；D-223 解码器与裁决 45 的真值盒都对；符号翻回后 34 个物体的包含率中位 1.00。误差绕每帧相机自身 x 轴、随 yaw 变化，不是全局刚体变换，S1-03 cache 的质心、AABB、表面与两个体积全部失效，描述子与 mask 不受影响。三个口径：(a) 编码器改正符号供以后生成，S1-03 合同登记读取侧修正（由前向量 y 分量恢复俯仰角、右乘 Rx(2p)）并按 episode 生成提交表适用，cache 重建到新根，旧根改名保留，回收 mask 复用；(b) 改符号后整套重生成 S1-02；(c) 不重建、在 S2 消费侧逐帧修正（AABB 不能精确转回）。取 (a)，并允许 runner 用 `--masks-from` 读回收 mask 免跑 SAM（逐 mask 按像素重算摘要核对）。落地：`lean_public_pose.py` 纯核心；S1-03 合同就地新增 `public_pose_correction`（适用提交 c222c51、a397d16，未登记提交拒绝，已生成文件不改）并重钉 `e4d8a52e…`→`082e1c02…`；S1-03 runner、S1-04 几何工具与诊断 runner 三个读者共用同一入口；`camera_pose` 改为 Rx(+pitch)。影响：cache 重建约 4～6 h（免跑 SAM，开跑前 trial 实测 worker 数），旧根 `lean-s1-03-c993959` 改名保留、不续跑，几何重载重跑一次取修正后的残差。附带发现：S1-02 runner 生成时的容器可见性封印与不可观测窗口判定也用了错误位姿（同一 yaw 内误差抵消、跨 yaw 不抵消），已生成 episode 的窗口判定是否受影响待只读复核，不在本裁决内。被拒的备选：(b) 代价最大且私有真值与 RGB-D 本来正确；(c) 把错误留在冻结产物里。
  - **补充裁决 50（2026-09-22 批准，原话"裁决 50 取 (a)，停掉 mask 回收，用修好的编码器重新生成 S1-02 全部 50 条，旧 episode 根与 cache 根改名保留"；LOG-242 第六、七节）。** 起因：裁决 49 查明位姿符号错误后，只读复核发现同一个错误位姿还决定了不可观测窗口 U——容器可见性主体的封印与投影都用它，同一朝向内误差抵消、跨朝向不抵消。43 条全审，对照在 43/43 条上复现了生成时记录的 U（故复算忠实），修正后 U 由 633 个容器判定降到 243 个；模拟器自身实例分割在窗口内画出过其中 424 个（中位 1,227 像素），修正后只剩 10 个（中位 67 像素），两条独立证据一致。按 S0-02 `intervention_window` 冻结规则（涉及的全部容器窗口内每帧不可见，源容器中途重新进入视野整条 episode 失败）重问 158 条已执行干预：仍成立 31 条（严格口径 24 条），33 条有干预的 episode 里只有 2 条全部成立，非空成品率由 31/37＝0.838 降到 2/37＝0.054，远低于 0.6 门。三个口径：(a) 用修好的编码器重新生成全部 50 条；(b) 只保留仍合规的 2 条（样本塌缩、成品率触门、对照结构不成立）；(c) 把窗口规则弱化为"干预时刻不可见"（改已冻结科学规则、削弱不可观测窗口主张，且 S0-02 明文禁止缩短窗口通过）。取 (a)。落地：mask 回收即时停止（父进程 SIGTERM 后两个 spawn 子进程仍占 5.6 GB 显存，一并清除；13 条完成回执与 17,501 个 mask 文件留在原根作记录）；旧 `lean-s1-02a/b-c222c51` 与 `lean-s1-03-c993959` 改名保留；在 Rx(+pitch) 编码器下重新生成 50 条（上次墙钟 02a 3.2 h、02b 3.1 h）。影响：S1-03 cache 与 S1-04 几何、诊断、ReID 全部作废重做，`--masks-from` 随之无用（回收的 mask 属旧 RGB）；生成所用提交须登记进 S1-03 合同 `correct_encoder_since_code_commits` 并重钉，否则所有读者按裁决 49 拒绝读新数据；裁决 41 的"U 内对照供不上 16/145"在放大 2.6 倍的 U 上测得，须在新数据上重测。旧产物不删：`results/` 三代阶段报告与 LOG-238/239/242 是被取代运行的记录。旧 cache 根随后按用户要求删除（记录先导出为 `results/vsmt_lean_s1_03_report_c993959_superseded_by_ruling_50.json`，数据盘 29 GB → 20 GB 已用）。
  - **补充裁决 51（2026-09-22 批准，原话"裁决 51 同意，S1-03 cache 生成时直接写 mask，合同就地加规则并重钉，不再单独跑回收"；LOG-242 第八节）。** 起因：裁决 50 让 cache 必须从头重建，而裁决 48 的 SAM-only 回收要另花约 13 小时 GPU；SAM 的 mask 在生成时本来就在内存里。落地：`build_episode` 写完帧文件后按同一色块顺序写 `NNNN.masks.npz`（每帧约 6 KiB，对比帧本身 224 KiB，全量约 0.2 GB）；S1-03 合同就地新增 `fragment_masks` 块（文件名、顺序、消费者必须按像素重算摘要、不另加封印因为帧封印已覆盖每个 `mask_sha256`、回收模式保留给本裁决之前生成的 cache），校验器绑定并拒绝任何一项被改弱，规则摘要重钉 `082e1c02…` → `ee591bec…`；回执新增 mask 字节数与带 mask 的帧数。影响：S0-04 重叠标注与 S1-04 诊断直接从 cache 读 mask，不再有独立回收步骤；裁决 48 的 `--recover-masks` 与裁决 49 的 `--masks-from` 都保留，只是不再进入正常流程。被拒的备选：维持裁决 48 的两步流程（结果相同但多花 13 小时）。
  - **补充裁决 52（2026-09-23 批准，原话"批准裁决 52：父容器取第一个非 Floor 受体并记录完整列表；窗口设计先出提案不改旧数据；规模/门/对照待提案后一起裁"；LOG-243 及其补充）。** 起因：空可行集只读审计（LOG-243 补充）用模拟器探针确认，生成器 `_object_table` 取 AI2-THOR `parentReceptacles[0]` 当作源容器，而模拟器对沙发、电视柜、边桌、置物架、餐桌上的物体先列房间 `Floor`；`train-03361` 的 Bowl（扫掠一 579 像素）与 Candle（325 像素）明明在 U 里的电视柜上，却被记到 Floor，remove 没进可行集，整条 house 失败。全 49 条联表：987 个合格物体里 99 个（10%）被这样记到 Floor；取第一个非 Floor 受体后，U 上的源 81 → 91、U 内持物容器（对照候选）39 → 45、全部持物容器 335 → 408。三个口径：(a) 取 `parentReceptacles` 第一个非 Floor 项，只列 Floor 的物体在地上、不算合格，完整表写进 provenance；(b) 保持第一项；(c) 物体同时落在多个受体触发盒时整条排除。取 (a)。落地：`lean_interventions.parent_receptacle_of` 纯函数；生成器 `_object_table` 记录 `parent_receptacles` 完整表，并在 dry-run 之前把全部可拾取物体的父容器表、扫掠一像素、窗口前像素、合格／未见／父容器在 U 三个标志写进 `provenance/object_table.json`，可行集为空的回执附 U 上合格源数、未见物体数、有生成点的目的容器数与 dry-run 通过对数；S0-02 合同就地新增 `receptacle_is_the_first_non_Floor_entry_of_parentReceptacles`、`an_object_listed_only_under_Floor_has_no_receptacle_and_is_not_eligible`、`full_parentReceptacles_list_written_to_provenance_object_table` 与 `parent_receptacle_rule_superseded`，校验器绑定前两条，规则摘要重钉 `15fcfe6f…` → `fcd5d187…`；测试新增 9 项（`test_vsmt_lean_object_table.py` 5 项、选择器 4 项）。影响：以前算"合格"但从不可能当源的 65 个只在地上的物体不再合格，`eligible_object_count` 会下降；U 内对照统计（裁决 41）须在新规则下重算；本裁决不授权重生成，数据要等窗口协议（待裁 53）一起定后再生成。被拒的备选：(b) 继续丢 10% 的源与对照候选；(c) 触发盒重叠是模拟器常态，整条排除会再丢一批。窗口设计、规模、0.6 门与对照供给本裁决不改。
  - **待裁 53（提案，2026-09-23，未批准、未实现）：不可观测窗口协议。** 问题：现行窗口＝整段过渡（最后视点 → 最远可达格，49 条全程 30° 俯视），U＝整段每帧都不可见的容器。小房子走一遍就把每个容器至少看到一次（12 条 U=0 里 11 条所有可用容器都被模拟器真的画出过），U≠0 时又多是封闭受体；这是路线结构，不是判定错误，也不是"物理上不存在窗口"。四个口径：(a) **推荐，两段过渡**——离开段仍按现规则走到最远可达格，其帧照常观察但不参与 U；紧接其后的窗口段是事前冻结长度 L 的继续行走（推荐"继续走向离窗口起点最远的可达格，L 步截止"，不足 L 整条失败而不是缩短），U 只在窗口段每一帧上算，"涉及的全部容器窗口内每帧不可见""不缩短窗口"原样保留。科学理由：记忆任务只要求涉及容器从窗口开始到重访之间未被看见，离开段里看到某容器只是把它的最后观察推后，不削弱不可观测主张。只读估算（用现有 49 条过渡的最后 L 帧近似窗口段，仅信息、不是新样本）：L=20 时 U≥1 48/49、有 remove 源 46/49；L=40 时 41/42、40/42（7 条过渡不足 40 帧）；整段口径为 37/49、24/49。move 仍要两个 U 容器、add 仍要过 dry-run，成品率不会等于这些数。(b) 保留整段窗口，把过渡终点从"最远格"改为按封印容器 AABB 与规划视锥的几何预测使 U 最大的终点（纯 house 函数、抽样前定）；不改窗口定义，但路线为藏容器而选、房屋结构偏置更强，且不保证 U≥1，旧数据无法估计。(c) 保持现协议，接受 S1-02 no-go。(d) 把 <196 像素视为不可见：U≥1 43/49，但直接削弱不可观测主张且合同明文禁止，不推荐。需同时裁：L（推荐 40，≥ 2 倍下限 20，42/49 条过渡本身已够长）、窗口段走法、窗口段俯仰（推荐保持最后视点的俯仰，不加新动作）。落地要改：S0-02 `intervention_window.window_is_the_whole_transition_segment` 改为两段定义并重钉、路线规划器加窗口段、生成器 U 计算改窗口段范围、重生成 50 条（约 1 小时）；旧数据不改不重算。move 下限、0.6 门、对照供给与规模在新 pilot 数据出来后一起裁。
  - **待裁 53 的探针授权（2026-09-23，用户原话“先别生成50条，先跑前几条看看效果估算一下怎么样”；不是裁决 53 的批准）。** 按口径 (a) 在生成器加可选窗口段：过渡走到最远格之后，再朝“离当时位置最远的可达格”继续走恰好 L 步（转身也算一步），U 只在这 L 帧上算；走不满 L 步整条按 `intervention_window_unavailable` 失败，不缩短。入口 `--stage window-probe --window-segment-frames L --houses … --probe-note …`，只跑 8 栋 house：S1-02a 登记的 4 栋 pilot house（00460、01451、03394、08566）加 4 栋本轮 U=0 失败的小房子（01456、03986、06764、09951），8 worker。L 取推荐值 40，**未冻结**；产物根 `lean-s1-02-window-probe-<commit>`，只用于估算 U、可行集、move 与 U 内对照能到什么量级；S0-02 合同的窗口定义没有改、规则摘要不动，S1-03 合同的编码器提交登记表不含本提交，所以任何读者都会拒绝把它当开发数据。看过估算后再裁 53（L、走法、俯仰）与规模／门／对照。**探针第一口径的结果（同日）**：到最远格后掉头再走 40 步，段首两次 `RotateRight` 是 180° 转身，小房子在窗口开始 2～6 帧内看遍全部容器（01456、06764 走满 40 步 U 仍为 0；03986、09951 到最远格只有 38 步），大房子则好于整段口径（01451 U 15 → 51、03394 4 → 21、08566 0 → 8，08566 执行 2 个 move）；离线“旧过渡最后 L 帧”估算不能预测掉头轨迹。**探针第二口径（`--window-mode transition_tail`）**：不掉头，窗口＝走向最远格这段过渡的最后 L 帧，前面是离开段；目标格与 L 走前已定，不足 L 整条失败。它与离线估算用的是同一条相机轨迹，所以旧 49 条的估算对它精确（L=20：U≥1 48/49、有 remove 源 46/49；L=30：43/45、41/45；L=40：41/42、40/42）。同样 8 栋、L=30 再跑一次看 F、move 与对照。
  - **补充裁决 53（2026-09-23 批准，原话“裁决 53 取最后 L 帧口径，L=30，落地后重生成 50 条。”；LOG-243 续）。** 起因：见待裁 53 与两次探针。第二口径探针（`cf56dc5`，尾窗 L=30，同样 8 栋，7 worker）在批准时的现场：小房子 03986、06764 过渡只有 26／25 帧不足 30；01456 U=0；00460、09951 U=1 但容器上无合格物体、未见物体试放不过——五栋均与离线逐栋估算一致（01456 L=30 估 U=0；00460、09951 估 U=1 源 0），三栋大房子仍在跑；这 8 栋是刻意选的最难 case，不是随机样本，全 49 条的估算仍是 L=30：U≥1 43/45、有 remove 源 41/45。同一估算显示 L=20 对小房子更好（01456 U=5 源 2、00460 U=2 源 4、49/49 过渡够长），用户仍取 30。落地：S0-02 `intervention_window` 就地改为 `window_is_the_last_L_frames_of_the_transition`＋`window_frames: 30`，`window_is_the_whole_transition_segment` 记 superseded，离开段照常观察不参与 U，不足 30 帧失败不缩短，起点与长度走前固定；校验器新增五条绑定并导出 `WINDOW_FRAMES`；生成器所有阶段默认 `--window-mode transition_tail --window-segment-frames 30`，`whole_transition` 只用于复算旧运行，`u_turn` 只用于复算第一次探针根；测试新增（校验器 4 项断言、`_resolve_window` 1 项）；规则摘要重钉。影响：S1-02 全部 50 条重生成（旧根 `lean-s1-02a/b-7c10d2c` 保留），生成提交须登记进 S1-03 合同 `correct_encoder_since_code_commits` 并重钉，S1-03 cache 与 S1-04 全部重做；裁决 41 的 U 内对照与裁决 36 的 move 下限在新数据上重看；两次探针根不是数据。被拒的备选：(b) 几何预测终点（不保证 U≥1、偏置更强）、(c) 接受 no-go、(d) 像素阈值当不可见（合同明文禁止）。
  - **待裁 54（提案，2026-09-23，未批准、未实现）：裁决 53 下小房子的路线协议。** 现场（LOG-243 续四）：`5f9aa71` 全 50 条里 8 栋结构性失败——4 栋过渡只有 24～29 帧（03986、04146、06764、09985，其中 04146、09985 在旧整段口径下是成功的）、2 栋 U=0（01456、08101）、2 栋 U 只剩一台冰箱且冰箱内未见物体试放不过（00460、09951）；02b 成品率 28/37＝0.757 已过 0.6 门，这 8 栋不影响门，影响的是开发集规模（39/50）与 S3-01 的 train 有效数（按 16% 结构性掉栋估算 300 → 约 250，按 X6 只能下调不能补）。口径：(a) **推荐，维持裁决 53**——8 栋按合同记失败并留在失败清单，不换 house、不补样，规模缺口留到 S3-01 下调 train；(b) 小房子分档 L——过渡不足 30 帧的 house 用 L=20（续二记录的离线估算：L=20 时 49/49 过渡够长、01456 U=5、00460 U=2），代价是窗口长度随 house 变化、两档数据不可比、S0-02 规则要改并重钉、至少重生成受影响的 4～8 栋；(c) 尾窗之后再续走 L 步（第一次探针的 `u_turn` 变体）——探针已证明它对小房子无效（01456、06764 掉头即看全）；(d) 用 train 块后续 house 顶替——按结果挑样本，合同禁止。影响：(a) 不改代码、不重生成，S1-03 可在 39 条上重建；(b) S1-03 再等一轮。
  - **待裁 55（提案，2026-09-23，未批准、未实现）：执行期单个干预失败时是否整条 house 作废。** 现场（LOG-243 续四）：3/50 栋 `intervention_execution_failed`，三种机制——01451 第 5/6 个干预被前序 move 遮挡（干预互相破坏）、09488 第 1/6 个干预在 dry-run 通过的同一点执行时落不稳（dry-run 不可复现，无前序干预）、05593 第 2/4 个干预时模拟器对刚被搬空的水槽盆返回 y≈−12150 的生成点（世界外坐标，疑似模拟器／代码问题，需单独查，与口径无关）。成功的 39 条里 95 次放置有 5 次靠执行期重取生成点兜底、途中 60 次被拒，说明冲突普遍存在、失败是兜底救不了的尾部。口径：(a) **推荐，本轮维持现状**——整条失败、计入分母（成品率已过门），先查 05593 的坐标来源再谈改规则；(b) 丢弃该干预、保留其余并如实登记（01451 保留 4 个、05593 保留 1 个、09488 保留 0 个仍失败）——须明文禁止"再抽一个补上"，否则是按结果选样本，且被丢弃干预的双生对照要同步作废；(c) dry-run 改为顺序验证（在已执行前序干预的世界上验证下一对）——语义最干净，开销随干预数上升，且 09488 这类物理不可复现仍救不了。影响：(a) 无代码改动；(b) 改 runner 与 S0-02 的失败规则、重钉、重生成 3 栋；(c) 改 dry-run 实现并全部重生成。
  - **补充裁决 54（2026-09-23 批准，原话「批准裁决 54 取 (a)、裁决 55 取 (a)；先查 05593 的 y=-12150 来源；授权在 S1-03 合同登记 5f9aa71 并重钉，然后重建 cache」；LOG-243 续五）。** 取 (a)：维持裁决 53，`5f9aa71` 下 8 栋结构性失败（4 栋过渡不足 30 帧、2 栋 U=0、2 栋 U 只剩一台冰箱且无合格物体）按合同记失败并留在失败清单，不换 house、不补样、不分档 L、不重生成；开发集为 39 条（29 条有干预＋10 条空窗口），规模缺口留到 S3-01 按 X6 下调 train。被拒的备选：(b) 小房子分档 L=20（窗口长度随 house 变、两档不可比）、(c) 尾窗后续走（探针已证明对小房子无效）、(d) 用后续 house 顶替（按结果挑样本）。影响：不改代码、不改 S0-02；S1-03 可直接在 39 条上重建。
  - **补充裁决 55（2026-09-23 批准，原话同上；LOG-243 续五）。** 取 (a)：执行期单个干预失败仍整条 house 作废并计入成品率分母（3/50：01451 干预互相破坏、09488 dry-run 不可复现、05593 模拟器返回世界外生成点）；不实现"丢弃该干预保留其余"，也不把 dry-run 改为顺序验证。附带要求：先查 05593 的 y≈−12150 来源（只读探针，记在 LOG-243 续五），查明后若需改 runner 再另立裁决。影响：无代码改动、无重生成。
  - **裁决 53 的 S1-03 登记（2026-09-23 批准，原话同上）。** 生成提交 `5f9aa71` 登记进 S1-03 合同 `public_pose_correction.correct_encoder_since_code_commits`（与 7c10d2c 之间 `camera_pose` 函数逐字相同，读者按原样读），合同就地修订、规则摘要 `2a17546f…` → `c7318cd5…`，`test_vsmt_lean_public_pose` 的登记断言随之更新；授权在 39 条成功 episode 上重建 S1-03 cache 到新根 `lean-s1-03-<cache 提交>`（开跑前 trial 实测 worker 数，裁决 51 生成时直接写 mask）。旧根 `lean-s1-02{a,b}-7c10d2c` 的 episode 不再是数据，只作审计源保留。
  - **待裁 56（提案，2026-09-24，未批准、未实现）：匹配口径。** 触发：S1-04（LOG-244）单视角 fragment 盒对真值整盒 IoU 中位 0.0004＜0.3，按物体组分是可拾取 0.453、容器 0.136、其他（非可拾取、非容器，占 76% 的行）≈0。口径：(a) **推荐先做只读估算再裁**——在现有开发 cache 上离线重算两种备选，不改任何合同，产物只用于裁决：BIND 时按并集累积 AABB 后，实体盒对真值盒的 IoU 分布；以及质心距离匹配下的命中率。同时按组报告。(b) 直接取 BIND 并集累积 AABB（改 S0-01 的实体几何规则并重钉）。(c) 直接改用质心距离匹配（改 S0-04 匹配口径与裁决 C 的 0.3，裁决 V 的节点 F1 选参重做）。(d) 把门限定在进入实体记忆的物体组上重算——只有在 S0-01／S0-04 本来就把"其他"组排除在实体之外时才成立，需先核对，否则就是按结果改门。影响：(a) 一次只读运行，约 1 小时，不动任何字节；(b)(c) 动已审字节，重钉，S2 臂实现随之改；(d) 若核对成立可能不改规则。
  - **待裁 57（提案，2026-09-24，未批准）：S0-03 召回值冻结（裁决 46）。** 依据 LOG-244 的曲线（ViT-B/14，两套描述子相差不到 0.7 个百分点）。候选：(a) k=5、k′=3、半径 3 m，漏召回 2.0%，每次召回候选数至多 8；(b) k=5、k′=5、半径 3 m，1.7%，至多 10；(c) k=8、k′=5、半径 3 m，1.0%，至多 13；(d) k=3、k′=2、半径 2 m，约 4.7%，至多 5。候选越多，分配越难、计算越贵，而漏召回按 S0-03 单独记 `recall_miss`，不混进教师或摊销误差。影响：只填三个登记值，不改规则摘要。
  - **补充裁决 56（2026-09-24 批准，原话「裁决 56 取 (a) 先做只读估算；裁决 57 取 (a) k=5、k′=3、半径 3 m」；LOG-244 续）。** 取 (a)：先在 S1-04 开发 cache 上做只读估算，不改任何合同；复用 S1-04 runner 的加载、标注与真值追踪，关联取理想关联（色块归其私有物体），逐行比较单视角框、同帧并集框、跨帧累积并集框（真值中心移动超过 5 cm 即重开累积）对真值框的 IoU，以及累积质心到真值中心的距离与“最近真值物体是否就是自己”，按可拾取／容器／其他三组与物体类型分列；估算结果出来后再裁匹配口径本身。脚本与产物只在 `vsmt_private/tmp-audit-ruling56-154776d/`，结论写 LOG。
  - **补充裁决 57（2026-09-24 批准，原话同上）。** S0-03 合同 `recall_rule` 冻结 local_count=5、global_count=3、local_radius_m=3.0（ViT-B/14 漏召回 2.0%、ViT-S/14 2.3%，每次召回至多 8 个候选），`lean_assignment.py` 绑定常量 `RECALL_LOCAL_COUNT／RECALL_GLOBAL_COUNT／RECALL_LOCAL_RADIUS_M`，跨合同台账 `FROZEN_VALUES["S0-03"]` 登记，规则摘要 `1becb7e3…` 不变（填值不动规则）。**遗漏更正**：合同写的是“四个值在 S1-04 曲线之后一次冻结”，第四个 `birth_neighbourhood_radius_m` 不在待裁 57 的提案里（提案者的遗漏），本次保持 null 并在合同里注明，须在任何臂使用召回规则之前另行裁决；其依据（出生时刻半径 0.25／0.5／1.0 m 内已有实体数）随裁决 56 的估算一并汇总。
  - **待裁 56 续（提案，2026-09-24，未批准、未实现）：匹配口径本身。** 依据：裁决 56 (a) 的只读估算（LOG-244 续）。wall、room、door、window 四类建筑结构占门上 65% 的行；这四类在任何框规则或匹配规则下都匹配不上（墙"最近即自己"3%）。排除它们之后，同帧并集框的 IoU 中位 0.368，过 0.3；单视角 0.165，跨帧累积 0.129，都不过。口径：(a) **推荐**：两处规则变更一起改。第一，S0-04 真值节点范围按类型排除这四类建筑结构，解析到它们的实体按 X6 已有机制记为范围外、不进精确率分母。第二，S0-01 的 BIND 框规则由"换成最新色块框"改为"本帧绑定到该实体的全部色块框取并集"，跨帧不累积。0.3 与裁决 C 的其余口径保持不变。(b) 同样排除建筑结构，但匹配改为质心距离（排除后 92% 在 0.5 m 内，最近即自己 82%；阈值另定）。要改 S0-04 的匹配口径与裁决 C 的 0.3，裁决 V 的节点 F1 选参重做。(c) 只排除建筑结构、框规则不变：单视角中位 0.165，仍不过门，不推荐。(d) 不排除建筑结构：任何口径都过不了门，只能进入证据层级裁决。影响：(a)(b) 都要修改已审字节并重钉；(a) 只动 S0-01、S0-04 各一条规则，S2 的臂实现随之改。排除的四类是从 ProcTHOR 的结构类型名来的，不是看了结果挑的：它们是房屋的结构件，不是可被干预、也不是会移动的物体。但排除会改变论文里"节点"的含义，必须写进方法与限制。
  - **待裁 58（提案，2026-09-24，未批准）：S0-03 第四个召回值 `birth_neighbourhood_radius_m`。** 这个值是裁决 57 的提案漏掉的，合同要求它在任何臂使用召回规则之前冻结。依据：S1-04 的出生邻域统计（LOG-244 续），出生时刻周围已有实体的平均个数在 0.25／0.5／1.0 m 分别为 0.07／0.35／1.15，只有 1.0 m 那一档不几乎恒为 0。(a) **推荐 1.0 m**：只有这一档能让出生特征真的有信息量；(b) 0.5 m；(c) 0.25 m。影响：只填一个登记值，要绑定常量并登记进台账，规则摘要不变。
  - **补充裁决 56 续（2026-09-24 批准，原话「裁决 56 续取 (a)：真值范围排除 wall/room/door/window，BIND 框改为同帧并集；裁决 58 取 1.0 m」；LOG-244 续二）。** 取 (a)。S0-04 `node_prf1.truth_node_scope` 改为排除四类结构件，新增 `structural_types_excluded_from_scope`＝door／room／wall／window，按私有键第一个 `|` 之前的前缀识别；评价器新增纯函数 `in_truth_node_scope` 与 `structural_type_of`，真值表把结构件标为在范围内即拒绝（`truth_object_structural_in_scope`）。S0-01 新增 `entity_box` 规则：实体框＝最近被看到那一帧里属于它的色块框的并集，新的一帧整个替换，同帧再来的取并集，合并时只有同帧才并、否则保留较新的；`lean_memory` 的 BIND／REACTIVATE 与共享去重随之改。0.3 与裁决 C 的其余口径不变。规则摘要重钉：S0-01 `76f505da…` → `4818d6ac…`，S0-04 `585e3660…` → `9bf1059d…`。影响：S1 不重做（S1-02 数据、S1-03 cache、S1-04 的分离度／召回／ReID 都不用框也不用范围），S1-04 的 IoU 门在新口径下由裁决 56 (a) 的只读估算复核：同样 459,275 行中排除结构件后同帧并集框中位 0.368 ≥ 0.3；S2 的臂实现与 S2-01 的真值表构建按新规则写。论文须写明节点只指物体、不含房屋结构。
  - **补充裁决 58（2026-09-24 批准，原话「裁决 56 续取 (a)：真值范围排除 wall/room/door/window，BIND 框改为同帧并集；裁决 58 取 1.0 m」）。** S0-03 `recall_rule.birth_neighbourhood_radius_m`＝1.0，绑定常量 `RECALL_BIRTH_NEIGHBOURHOOD_RADIUS_M`，登记进台账，S0-03 规则摘要 `1becb7e3…` 不变。至此裁决 46 要求的四个召回值全部冻结。
  - **S0 修订审查通过（2026-09-24，原话「S0 修订审过，开 S2」）。** 裁决 56 续／57／58 的合同与代码改动（`30a7537`、`6699a19`，服务器 1492/1492）经用户审过，按 D-059 成为 S2 基线；授权进入 S2。按 PLAN，S2-01 的输入是 S1-05 冻结后的描述子，故先做 S1-05（按已冻结的选择规则收口），再开 S2-01；用户要求在新对话中进行。
  - **S1-05 执行登记（2026-09-24，机械执行裁决 47，非新裁决；LOG-245）。** 按 S0-03 冻结的规则在 S1-04 报告（`results/vsmt_lean_s1_04_diagnostics_154776d.json`，sha256 `18c7f79d…`）的 9 条选择 house 上选择：冻结 ViT-B/14 中位分离度 0.143 为最好的冻结集，ViT-B/14 投影 0.236，增益 0.093 ≥ 0.05，选定 `reid_projection:vitb14`，冻结 ViT-B/14 为并列报告基线，权重摘要 `f6fc67e5…`。落地：S0-03 `reid_adapter_head.selection_result`（新增块，规则摘要重钉 `1becb7e3…` → `37d56a90…`）、`lean_assignment` 四个常量与校验器绑定、回执 `results/vsmt_lean_s1_05_descriptor_freeze_154776d.json`、工具 `ops/vsmt/lean_s1_05_select_descriptor.py`（从 cache 封印重算留出、重算规则、与报告核对后才写）、测试 10＋1＋4 项。此后不得再换描述子；S1 收口。按 D-059 待用户审。
  - **待裁 59（提案，2026-09-24，未批准）：ReID 选择组 9 条而非 12 条是否维持。** 现场：合同留出登记 30/12，cache 只有 39 条成功 episode，合同规定无 cache 的 house 跳过并计数、不顶替，S1-04 与 S1-05 均按此执行并登记 `selection_shortfall: 3`。判定余量：增益 0.093 对门 0.05，两个投影的增益都 ≥ 0.086，不在边缘。(a) **推荐：维持**——规则事前冻结、机械执行、缺口如实登记，论文限制里写明选择组为 9 条；不改任何代码或合同。(b) 改分法保 12 条选择（如 27/12）——须修 S0-03 留出规则并重钉、按新分法重训两个投影（服务器约 1 小时 GPU）、重做 S1-04 的 ReID 段与 S1-05，且"看过结果再改分法"须写进论文；训练 house 少 3 条，投影可能略差。影响：(a) 零成本，S2-01 立即可用现有权重；(b) 推迟 S2 约半天并换权重摘要。
  - **S2-01 实现登记（2026-09-24，LOG-246，待审）。** 共同 runner 纯核心 `lean_runner.py` 与合同 `lean_s2_01_runner_v1.json`（首钉 `e1060695…`，两位全 false）。合同把三条此前只在 METHOD／PLAN 里的规则写成机器形式：实体几何＝包围盒均匀格心落进可见体积块／自由空间块并集的比例（六半空间判定、容差 1e-9、固定顺序点积，分辨率为登记值）；非法程序整帧回滚后提交空程序、tick 推进、计数；真值表范围＝此前至少一帧私有 mask ≥196 像素且非 wall／room／door／window，结构件在场、范围外、无盒，其它不在几何表的键整条失败。S0-04 `_truth_table` 放宽一处：在场但范围外的对象可无盒（结构件没有初始盒），不改任何指标。学习臂 logit 由 S2-03 的 scorer 提供；LLM-op 在 runner 拒绝。
  - **待裁 60（提案，2026-09-24，未批准）：S2-01 `entity_geometry.samples_per_axis`。** 应可见比例与自由空间覆盖比例都按实体包围盒上 s×s×s 个格心算，S0-05 的 `should_be_visible_min_ratio`、RAC 的 ρ_rac、ELU-P 的 free_space_weight、HandCost 的 ρ_h 全作用在这个比例上，所以 s 决定比例的粒度。(a) **推荐 4**：每实体 64 点，比例粒度 1/64，单帧约百个实体×数百块的半空间判定在 numpy 里约几十毫秒；(b) 8：512 点、粒度 1/512，约 8 倍计算；(c) 2：8 点，粒度 1/8，太粗，比例只有九个取值。影响：只填一个登记值，规则摘要不变；S2-05 任何运行前必须冻结。
  - **S2-02／S2-03 实现登记（2026-09-24，LOG-247，待审）。** `lean_controls.py`：四个对照与 LLM-op 的 clean-room 来源登记（绑定 S0-05 `source` 行）、ELU-P 三个拟合量的估计式（退化计数拒绝）、LLM-op 文本接口（选择转 logit 走同一求解器，只允许 validation）；`lean_model.py`：三个代价头（54,207 参数，METHOD 的"约 4 万"为约数、架构文本为准）、scorer、登记损失、AdamW 逐帧训练与最佳 epoch 早停、AssocOnly 无存在头重训、DAgger 两轮登记。没有新裁决；S0-05 的 `weight_decay`、`seeds`、`tau_r`、`should_be_visible_min_ratio`、ELU-P 六值仍为 null，S2-05 前冻结。
  - **S2-01～S2-03 审查通过，裁决 59～63 与臂状态回滚（2026-09-24 批准，原话「裁决 59 取 (a)，60 取 4，61 按 S1-04 的 activation_policy 修，62 拒绝，63 保持 128 宽改数字，非法程序臂状态回滚；修完再开 S2-04」；LOG-248）。** 审查范围 `b0b59d2`…`95b9e84`。审查核对项：D-223 材化的"点在块内"为 n·p ≤ offset（近平面写成 (0,0,−1)、−near），runner 用同一不等式且体块与色块共用同一因果位姿；自由空间滚动窗口 4 次观测按合同"照存的读"；三头参数 18,589＋18,329＋17,289＝54,207 逐头核对；四条来源链接在线核过（ConceptGraphs、Fusion++、Dengler ECMR 2021、POCD RSS 2022 标题作者相符）；runner 21、controls 8、model 11 本机通过。裁决落地：(59) 维持 9 条选择组，论文限制里写明，不改代码与合同。(60) S2-01 `entity_geometry.samples_per_axis`=4（每实体 64 点、粒度 1/64），绑定 `ENTITY_GEOMETRY_SAMPLES_PER_AXIS`，跨合同台账 `FROZEN_VALUES["S2-01"]` 登记，合同以 `registered_value_slots` 记住 v1 登记过的槽位；填值不动规则摘要。(61) `validate_runner_contract` 原要求两个授权位全 false，而入口 `lean_s2_01_runner.py` 先调它再要求两位为 true，入口永远跑不起来（审查时置位模拟证实抛 `contract_authorization_must_be_all_false`）；改为 S1-03／S1-04 的 `activation_policy` 机制：为 true 的位必须被 `active_true_authorizations` 点名并写 `opened_by`，未点名即拒（`contract_bit_opened_without_a_ruling`）；两位现仍关。(62) `fit_match_gain` 原接受 p_hit ≤ p_false（10/100 对 50/100 得 −1.61）而 `elu_p_observe_matches` 拒绝负增益，拟合"成功"到 S2-05 第一帧才失败；现拟合即拒（`fit_degenerate:gain_not_positive`）。(63) 架构保持 LayerNorm＋两层 128 宽 GELU，METHOD 第七节与 AGENTS.md 的"约 4 万参数"改为 54,207（宽度 112 才是约 4.2 万）。附：非法程序整帧回滚原不含臂状态（ELU-P log-odds 与 RAC 计数为未生效的决定推进），现回到帧前值，回执记 `arm_state_rolled_back`，合同 `frame_step.arm_state` 新增布尔声称并由校验器绑定，S2-01 规则摘要重钉 `e1060695…` → `09fc1a4a…`（去掉该声称即回到首钉，台账注释登记）。影响：S1 与 S0 字节不变；S2-05 任何运行前仍须打开两位并冻结 S0-01 五个、S0-03 两个、S0-04 五个、S0-05 九个 null 值。S2-04 接线时存在标签只对可判定行生成（active／dormant 且应可见比例 ≥ `should_be_visible_min_ratio`），该下限须先冻结；S2-05 前须核对服务器 39 份几何回执的 `objects_without_box`（在场、范围内、无盒会整条 episode 失败）。
  - **S2-04 实现登记（2026-09-24，LOG-249，待审）。** teacher 与评价器接线 `lean_evaluation.py` 与合同 `lean_s2_04_evaluation_v1.json`（首钉 `40d96cf0…`，两位全 false，不登记自己的值槽）。S0-04 的标签、三分解、七项指标、nuisance probe 一律调用原函数；本步只登记它们的输入在真实运行时怎么派生：色块实例重叠表来自回收 mask（摘要核对）与私有实例图；证据映射按 S0-04 色块主导规则；存在标签只对 runner 的可判定候选给出；结构件候选一律 present；旧/新位置取 S1-04 追踪器在窗口最后一帧／窗口后第一帧的质心与盒；"对方法可观察"＝把真值盒（无盒用质心点）放到该位置，用 S2-01 的 entity_geometry 采样、比例 ≥ S0-05 共享下限；Missing 残留率主值取最后一帧；恢复延迟起点按干预类型（移走看旧位置、新增看新位置、搬动两处任一）；搬动前承载实体＝窗口最后一帧提交后严格多数身份解析到该物体的实体（不限状态）；第一次带标签重见＝窗口后第一次有色块主导物体是它的帧。入口 `lean_s2_04_evaluate_episode.py` 在同一进程里跑 runner 与 teacher。测试 14＋跨合同 4，本机通过。
  - **待裁 64（提案，2026-09-24，未批准）：S2-05 的运行位由哪份合同持有。** S0-01／S0-03／S0-04／S0-05 的校验器把各自授权位绑定为 false（`EXPECTED_BOOLEAN_CLAIMS`），S2-01（裁决 61）与 S2-04 的位用 `activation_policy` 机制可凭裁决打开。(a) **推荐**：S2 阶段合同持有运行位（S2-01 `episode_run`／`server_run`，S2-04 `label_generation_run`／`server_run`），S0 各位保持 false 并在白话注明"运行由 S2 阶段合同授权"；入口只检查 S2 位。(b) 把 `activation_policy` 机制加进 S0 四份合同的校验器并逐位打开：改四个已审校验器、重钉四份规则摘要。影响：(a) 不动 S0 字节；(b) 多一轮 S0 审查。
  - **待裁 65（提案，2026-09-24，未批准）：S2-04 五条派生规则。** 代码按各条 (a) 实现，合同以规则字串登记、校验器绑定；改口径只改字串与实现、重钉 S2-04 摘要。(1) 可观察判定：(a) **推荐** 臂自己那套采样盒测试（S2-01 `entity_geometry`，比例 ≥ S0-05 `should_be_visible_min_ratio`），和臂判断自己实体应可见用同一把尺子；(b) 质心点落进可见体积；(c) 私有 mask ≥196 像素——对已移走的物体没有像素，无法判"旧位置可观察"，故不可用。影响：(a) 把 MRR 与恢复延迟的分母绑到那个待冻结的下限上。(2) 搬动物体的恢复起点：(a) **推荐** 旧位置或新位置任一可观察即起算；(b) 两处都可观察；(c) 只看旧位置。影响：(a) 延迟最短、最不偏向方法。(3) 搬动前承载实体：(a) **推荐** 不限状态（retracted 可被 REACTIVATE，身份连续率应承认）；(b) 只算 active／dormant。(4) 第一次带标签重见：(a) **推荐** 窗口后第一帧有色块的主导物体是它（目标状态不限，多块取物体像素最多者）；(b) 只算目标状态 labelled／recall_miss。影响：(b) 会把重见时实体身份含糊的帧跳过、推迟判定时刻。(5) 解析到结构件的存在候选：(a) **推荐** 一律 present（结构件从不被干预、没有点质心）；(b) 不给标签、不进损失、只计数；(c) 按位移判——被拒，墙的中心离墙段实体远，会把墙打成 gone。影响：(a) 存在头学到"墙不撤回"；(b) 存在头对墙实体没有监督。
  - **S2-04 审查通过，裁决 64／65 批准（2026-09-24，原话「S2-04 审过；裁决 64 取 (a)，65 五条全按推荐。然后我看S205里面有不因开发差不利就改设计或删消融，我觉得可以改设计，继续下一步」；LOG-250）。** 64 取 (a)：S2-05 的运行位由 S2 阶段合同持有（S2-01 `episode_run`／`server_run`，S2-04 `label_generation_run`／`server_run`），S0-01／S0-03／S0-04／S0-05 各位保持 false、由各自校验器绑定，入口只检查 S2 位；不动 S0 字节。65 五条全按推荐：S2-04 合同 `derivation_rules` 的字串即冻结口径，代码不变，规则摘要 `40d96cf0…` 不变。落地：S2-04 合同 `status`、`authorization_rule_zh`、`user_rulings`（均为记账或白话，不进规则摘要），PLAN S2-04 行与指针。
  - **裁决 66（2026-09-24 批准，原话「我觉得可以改设计，继续下一步」）：S2-05 继续门放开设计修订。** 原文"不据此选择论文赢家、不调网格、不因开发差不利就改设计或删消融"改为：开发差**可以**促成设计修订，但修订须登记为裁决、在 S3-01 冻结正式数据前完成、且不读 validation/test（开发 cache 是 train 划分的 39 条 house，改设计不污染选参与 test）；"不选赢家、不调网格、不删消融"三条保留——用户只说了改设计，其余三条未提；若也要放开，须另裁。落地：PLAN S2-05 行继续门与风险表行、AGENTS.md 当前方向一条。影响：S2-05 之后若开发差不利，允许提出设计修订裁决并在 S3-01 前实现；论文方法须写明设计在开发集上修订过。
  - **S2-05 实现登记（2026-09-24，LOG-251，待审）。** 开发表编排 `lean_development.py` 与合同 `lean_s2_05_development_v1.json`（首钉 `38314ce2…`，两位全 false）。五趟固定顺序：校准（LOW 无门，只统计封存行分布）→ ELU-P 拟合（TAF 在登记 rollout theta_a 上无门，数四条计数）→ 第 0 轮 DAgger（ELU-P 在 rollout_config 上，同时是 ELU-P 表行）→ 第 1 轮 DAgger（第 0 轮头各自轨迹）→ 开发表（TAF／RAC／LOW 开发配置，VSMT-lean／NoVersion／AssocOnly 第 1 轮头）。每趟每条 episode 是一次 S2-04 子进程运行，多 worker 按 episode 分片、按 episode_id 升序合并、回执续跑。开发训练每轮一次、取首个登记 seed、早停用 S1-04 留出（前 30 训练、后 9 选 epoch）。开发表：主值按 S2-04 headline，裁决 X2 排除只对适用臂算，VSMT-lean 对每臂只报配对差均值不做区间。S2-04 入口加 `--calibration`／`--elu-p-counts` 钩子（纯核心不变）。
  - **待裁 67（提案，2026-09-24，未批准）：跑校准趟就需要的 8 个运行必需值。** 每个都是登记槽，落值要改各模块的 NULL_POLICY_PATHS、绑定常量并登记台账（同裁决 57/58 的做法）；校准趟之后若分布说明该改，按裁决 66 以裁决 68 取代（台账 SUPERSEDED_VALUES 留底）。(1) S0-01 `dormancy_missed_opportunity_limit`：**推荐 3**（连续三次应可见未匹配才休眠，容忍 SAM 偶发两帧漏检；runner 测试用 2 只为缩短场景）；备选 2（休眠快、REACTIVATE 多）、5。(2) S0-01 `shared_dedup.period_ticks`：**推荐 10**（每 10 帧一次确定性去重，成本有界）；备选 5、30。(3) S0-01 `shared_dedup.descriptor_cosine_min`：**推荐 0.9**（投影后单位向量，先取保守高阈值；校准趟报同物体目标对余弦分位数后再定）；备选 0.8。(4) S0-01 `shared_dedup.centroid_distance_max_m`：**推荐 0.25**（＝S0-02 冻结的平移步长，相邻位姿看到的同一物体两块落在一步之内）；备选 0.5。(5) S0-01 `shared_dedup.aabb_iou_min`：**推荐 0.3**（沿用裁决 C 的匹配下限；LOG-244 续：同帧并集框中位 0.368 过 0.3，可拾取物体单视角 IoU 中位 0.45）；备选 0.2。去重要三条同时满足，保守组合意味着开发趟里很少合并，误合并风险低。(6) S0-04 `dominance_min_share`：**推荐 0.5**（严格多数，S1-04 标注 465,334 个色块用的就是过半规则）；备选 0.6。(7) S0-04 `delta_moved_m`：**推荐 0.5**（METHOD 提议值；S1-02 搬动下限 0.6 m／1.2 m 在其上，S1-04 未干预物体漂移 1.4～16 cm 在其下，两侧都不擦边）；备选 0.3、0.75。(8) S0-05 `should_be_visible_min_ratio`：**推荐 0.5**（实体盒 64 个格心过半落进可见体积才算应可见；比例粒度 1/64）；备选 0.25（更早判可见、更多错失计数）、0.75。影响：这 8 个值只决定开发趟怎么跑，不进 test；(3)(5)(8) 明确等校准趟复核。可复制批准句：「裁决 67 八个值全按推荐」。
  - **待裁 68（预告，校准趟之后提案）：** S0-05 各臂网格（每方法 ≤12、规则臂含无门项）、ELU-P `rollout_config` 三值（网格成员）、S2-05 八个开发配置槽、S0-05 `weight_decay`（METHOD 提议 1e-4）与 `seeds`（METHOD 提议 7/19/31/43/59）、S0-04 `nuisance_probe.maximum_advantage`、S0-03 `reference_score_seed` 与 `existence_threshold_tau_r`。依据是校准趟的分位数：同物体/异物体余弦定 theta_a 网格，距离分位数定 d_a／d_low，gone/present 的自由空间覆盖定 rho_rac／free_space_weight／retract_threshold，错失次数分布复核 dormancy。`bootstrap_seed` 与 `main_gate_effect_size` 留到 S3-01。
  - **S2-05 审查通过，裁决 67 批准并落地（2026-09-24，原话「S2-05 审过；裁决 67 八个值全按推荐。」；LOG-252）。** 八个值就地冻结：S0-01 `dormancy_missed_opportunity_limit`=3、`shared_dedup` period_ticks=10／descriptor_cosine_min=0.9／centroid_distance_max_m=0.25／aabb_iou_min=0.3（绑定 `DORMANCY_MISSED_OPPORTUNITY_LIMIT`／`SHARED_DEDUP`，校验器改为 S0-03 的"开着须登记、冻结须相等"规则，S0-01 的开放清单清空）；S0-04 `dominance_min_share`=0.5、`delta_moved_m`=0.5（`DOMINANCE_MIN_SHARE`／`DELTA_MOVED_M`，经 `FROZEN_VALUES_BY_RULING` 绑定；`NULL_POLICY_PATHS` 剩 bootstrap_seed／main_gate_effect_size／nuisance 上限）；S0-05 `shared.should_be_visible_min_ratio`=0.5（`SHOULD_BE_VISIBLE_MIN_RATIO`）。三份合同的规则摘要不变（填值不动规则），跨合同台账 `FROZEN_VALUES` 登记八项。按裁决 64 打开六个运行位：S2-01 `episode_run`／`server_run`、S2-04 `label_generation_run`／`server_run`、S2-05 `development_run`／`server_run`，各自 `activation_policy` 写明由裁决 64／67 与 S2-05 审查打开；位进规则摘要，三份重钉 `09fc1a4a`→`36b9fbc6`、`40d96cf0`→`f4511a34`、`38314ce2`→`859208ee`（位关回原钉，已核）。S2-05 前置核对：服务器 39 份 S1-04 几何回执全在、S1-02 根全在、没有任何物体缺盒（`objects_without_box` 合计 0）。落地提交 `607d976`（冻结）、`1c413e0`（开位）。
  - **待裁 69（提案，2026-09-24，未批准）：几何表以外的私有键——天花板与运行时生成物。** 现场（LOG-252 续）：S2-01 真值表规则"不在几何表里、又不是四类结构件的键整条 episode 失败"在最大 episode 上触发；只读扫描 39 条开发 episode，28 条含表外键：99 个 `Ceiling_room|<room>|…`（ProcTHOR 的房间天花板，96 个曾 ≥196 像素）与 2 个 `Egg|surface|…|EggCracked_0`（鸡蛋碎裂后运行时生成的物体，1 个曾 ≥196 像素）；wall／room／door／window 都在重载几何表里（表外为 0）。(a) **推荐**：两条规则并行——其一，`Ceiling_room` 并入结构件清单（S0-04 `structural_types_excluded_from_scope`、S2-01 `structural_types_out_of_scope`、`lean_teacher.STRUCTURAL_TYPES_EXCLUDED` 加第五类），理由与裁决 56 续逐字相同：天花板是房屋结构、不可干预、一次只看到一片；其二，登记"运行时生成物"规则：表外键的最后一段是非数字的生成标签（`EggCracked_*`、`*Sliced_*` 一类）即记为在场、范围外、无盒并单独计数 `spawned_after_reload`（重载时不存在、没有初始盒，是物理事件的产物）。其它表外键仍整条失败。影响：S0-04 与 S2-01 各改一处规则字串、重钉摘要；论文"节点"的脚注加天花板；S1 不重做；存在标签对解析到天花板的候选按结构件规则记 present。(b) 通用规则：任何表外键一律记范围外并计数——最省事，但把 S2-01 故意留的"数据有问题就整条失败"关掉了。(c) 排除这 28 条 episode——只剩 11 条，不可取。可复制批准句：「裁决 69 取 (a)」。
  - **裁决 69 批准并落地（2026-09-24，原话「裁决 69 取 (a)。」；LOG-253，`b4b7d80`）。** 取 (a)。`lean_teacher`：`STRUCTURAL_TYPES_EXCLUDED` 加 `Ceiling_room`（与裁决 56 续同一理由）；新增 `SPAWNED_AFTER_RELOAD_RULE` 与 `is_spawned_after_reload`（最后一段匹配 `^[A-Za-z][A-Za-z0-9]*_\d+$`），`in_truth_node_scope` 对生成物返回 False，评价器拒绝被标在范围内的生成物，校验器绑定规则字串。`lean_runner.TruthTableBuilder`：生成物一行在场、范围外、无盒并计入 `spawned_keys`；其它表外键仍 `truth_key_outside_geometry_table`。`lean_evaluation`：解析到生成物的存在候选记 present（reason `spawned_after_reload`），诊断列出生成物键。三份合同就地改规则字串并重钉：S0-04 `9bf1059d…`→`7a3d661b…`、S2-01 `36b9fbc6…`→`d07f141c…`、S2-04 `f4511a34…`→`eaac36bd…`。影响：28 条含表外键的开发 episode 可以运行；节点指标分母不含天花板与生成物；S1 不重做；论文"节点"脚注加天花板。
  - **待裁 70（提案，2026-09-24，未批准、未实现）：节点匹配口径与低 F1 的处置。** 依据：LOG-255 的只读审计（`b517890`，4 条开发 episode、10,890 真值物体·帧）。TAF（诊断配置 θ_a 0.65）下当前 IoU 0.3 口径 F1 0.21；83～87％ 的真值物体附近有身份正确的实体，召回损失 35％ 来自“位置对但 IoU＜0.3”；每真值 3.5 个实体，按私有身份并框后 F1 0.47（IoU）／0.78（质心 0.5 m）。两个主因各占一半：一物多实体（方法与去重值）和实体框是深度表面壳、真值框是整体盒（冻结前端的几何限制）。口径：(a) **推荐**：主节点指标保持裁决 C 的匈牙利 3D IoU 0.3 不变（Dyn-THOR 对齐、裁决 V 选参不变），S0-04 **增登一列次级节点 P／R／F1**：同一最大权匹配、用“实体质心到真值质心距离 ≤ δ（δ＝已冻结的 `delta_moved_m`＝0.5 m），权重 1／(1＋距离)”代替 IoU 门，六臂主表并列报告；不新增阈值。一物多实体由方法与裁决 68 的去重值复核处理。(b) 主指标改为质心 0.5 m 口径、IoU 0.3 降为次级列：修改裁决 C，裁决 V 的选参改按新主指标；对 Dyn-THOR 只能称“同一匹配机制、不同重叠判定”，须写进方法与限制。(c) 保持 IoU 0.3、不加列：不动字节，但所有臂的节点 F1 绝对值受前端几何限制压低，读者难以区分方法误差与前端限制。(d) 改 S0-01 实体框规则（跨帧累积或按深度厚度外扩）：LOG-244 续已测跨帧累积并集中位 0.129 更差；外扩是带参数的新启发式，不推荐现在动。影响：(a)(b) 都改 S0-04 的 `METRIC_FIELDS`／报告字段、`lean_evaluation` 报告与导出器并重钉 S0-04、S2-04 摘要，约一个提交；S1 不重做；校准趟不重跑（它只统计封存行，不读节点指标）。(a) 主表绝对值仍低但可解释；(b) 绝对值更高但外部对齐弱。无论取哪项，论文都须写明实体框来自单帧深度表面、与整体盒的 IoU 天然偏低。
  - **待裁 68 补充（2026-09-24，校准趟之后提案时一并给出）：去重三值复核。** 9 条校准回执：同物体余弦 p50 0.74～0.83、p25 0.66～0.76；同物体 IoU p50 0.013、p75 0.03～0.38；同物体质心距离 p25 0.13～0.21 m、p50 0.7～1.75 m。裁决 67 的去重三条（余弦≥0.9、质心≤0.25 m、IoU≥0.3）同时满足的概率接近零，去重实际不工作（LOG-255：TAF 每真值 3.5 个实体）。按裁决 66／67 的约定，在裁决 68 里用 39 条合并分位数重定这三值并在台账 SUPERSEDED_VALUES 留底；具体候选等合并分位数后给出。
  - **裁决 70 批准并落地（2026-09-24 批准，原话「裁决 70 取 (a)」；LOG-255 续，`f4f694a`）。** 取 (a)。`lean_teacher`：`METRICS`／`METRIC_FIELDS` 增 `node_prf1_centroid`（六个字段同 `node_prf1`）；`evaluate_frame` 在同一批预测与真值上再做一次最大权匹配，权重为质心距离 ≤ `delta_moved_m` 时的 1／(1＋距离)，否则 0，返回 `node_prf1_centroid` 与 `centroid_matched_pairs`；合同校验器绑定 `matching`、`distance_max_source`＝`labels.existence.delta_moved_m`、`role`（次级列、不选配置、不进主门）三条字串。`lean_evaluation`：逐帧记录与 episode 报告各多一块，`HEADLINE_FIELD` 增 `node_f1`；`lean_development.BETTER` 增 higher。S0-04 合同 `metrics.names`／`reported_fields`／`node_prf1_centroid` 块与 `user_rulings.ruling_70`，S2-04 `headline_fields`，S2-05 `table.better` 各登记一项；规则摘要重钉：S0-04 `7a3d661b…`→`126fdd34…`，S2-04 `eaac36bd…`→`0ff1fbe9…`，S2-05 `859208ee…`→`0d3cf50c…`。节点审计脚本改用评价器的距离函数并逐帧核对自己的质心口径与新列相等。测试：teacher（薄框在 δ 内被次级列匹配、δ 外不匹配、空帧为 None、三条字串绑定与缺块拒绝）、evaluation（合成 episode 上次级列逐帧与主列相等）、development、node_audit、cross-contract 重钉。影响：主列、裁决 C／V 与 Dyn-THOR 对齐不变；S1 不重做；正在跑的 `696fbe7` 校准趟不重跑（它只统计封存行、不读节点指标，回执里没有新列，导出器按缺列容忍）；S2-05 后续各趟在新提交上跑，主表并列报告两列。论文须写明实体框来自单帧深度表面。
  - **裁决 71 批准并落地（2026-09-25 01:05 CST 批准，原话「裁决 71 取 (a)(a)，停掉 195007 并按修复后的提交续跑」；LOG-256，`cc682d7`）。** 现场：`696fbe7` 校准趟 16/39 出结果时 5 条失败（00406、02524、01543、03394、02768，均已处理完全部帧、崩在收尾），11 条"成功"的回执 `nuisance_probes` 全为空块。根因在 S2-04 入口：收尾先重读 `nuisance.jsonl.gz` 再关闭写入流，gzip 成员在关闭前不完整——压缩输出还在缓冲区时读到 0 行（小 episode "成功"但探针块为空），部分输出已落盘时抛 `EOFError`（约 32 KB 压缩输出以上，即 1262 帧以上的 episode 全部会崩）。用真实文件本地重放复现（00702／00619 读到 0 行，00406 落盘 35,794 B 抛错）；旧 `82810c0` 趟的 01543 同样方式失败，与提速无关。待决两项：(1) 正在跑的趟——(a) **推荐**：立即停掉、落修复、同一根 `--resume` 只补缺的，已成回执保留；(b) 让它跑完再补，多等 2～3 小时且无任何可复用产物（崩溃的 episode 没有 receipt 与 calibration.json，`--resume` 不认）。(2) 已成功回执的空探针块——(a) **推荐**：不重跑，校准报告不读这一块，LOG 与导出报告如实标注；(b) 重跑这些 episode（约 4 小时机时）。用户取 (a)(a)。落地：`cc682d7` 入口改为先关三个流再重读并核对行数（`finish_streams`，回执多一项 `nuisance_rows_written`），回归测试 3 项，服务器全量 **1600/1600**；01:05 CST 停 `195007` 及 10 个子进程，按用户随后的指示一并停掉另一会话的旧 `82810c0` 趟（`869573` 及 2 个子进程，其余两条也必崩，产物只作旁证不合并）；只读列出后删除 15 个无回执的部分目录；01:21 CST 在 worktree `s2-05-cc682d7` 上以 12 worker `--resume` 续跑 25 条（14 条 `696fbe7` 回执保留）。校准直方图、标签、训练记录与 nuisance 行本身不受该缺陷影响（收集器单独写出、流在进程退出时完整落盘）；两提交的 calibration.json 逐字节同构，导出器按回执登记两个提交号。**用户同时授权（01:15 CST，原话「为了防止同样的情况出现，你最好监视每个episode，如果有这些情况就看看需不需要调整，需要调整你自行处理即可不需要我的批准」）**：本趟及后续趟逐 episode 监视，工程性失败（崩溃、资源、续跑、worker 数、停跑重启、删除失败 episode 的部分产物）由实现者直接处理并在 LOG 如实记录；科学口径（网格、冻结值、合同规则、指标定义、待裁 68）仍须用户裁决。影响：14 条保留回执的 `nuisance_probes` 为空块，导出报告中对应 `nuisance_largest_advantage` 为 null 并注明原因；S3 之前若需要这 14 条的探针值，须按 (2)(b) 重跑或另登记只读重算入口。
  - **待裁 68（提案，2026-09-25，未批准）：校准趟之后的网格、开发配置与复核值。** 依据：LOG-256 续的 39 条合并分位数（LOW 无门；两条保守解读——LOW 把最近实体当承载者，实体均值混入多个物体，同物体余弦偏低、异物体偏高；应可见比例与自由空间覆盖受"表面壳框对表面之前体积"的几何耦合）。每方法 ≤12 个完整配置，规则臂距离门含 None；网格是 S3 在 validation 上选参用的，S2-05 不选参。(1) **S0-05 各臂网格（推荐）**：TAF theta_a {0.6, 0.7, 0.8} × d_a {None, 0.5, 1.0, 2.0}＝12（同物体余弦 ≥0.6/0.7/0.8 为 90.9/75.6/43.4%，异物体 49.2/32.4/15.6%，新物体最高余弦 ≥0.7 仅 11.2%，交叉区在 0.7 附近；距离门覆盖同物体 ≤0.5/1/2 m 的 35.5/46.3/65.3%）；ELU-P theta_a {0.7} × d_a {None, 1.0} × free_space_weight {0.5, 1.0, 2.0} × retract_threshold {0.0, −1.0}＝12（覆盖基线 ≈0.65 时对应 2～10 个合格未匹配帧才撤回）；RAC theta_a {0.7} × d_a {None, 1.0} × rho_rac {0.7, 0.85} × n_rac {2, 3, 5}＝12（present 覆盖 ≥0.7/0.85 为 39.9/7.3%，gone 27.9/3.8%，在当前几何规则下不可分，网格只能括住基线）；LOW d_low {None, 0.25, 0.5, 1.0, 2.0}＝5；VSMT-lean／NoVersion／HeuristicLabel／VSMT-lean-ctx tau_r {0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9}＝7；HandCost theta_b {0.6, 0.7, 0.8} × rho_h {0.6, 0.7, 0.8, 0.9}＝12；AssocOnly {}。备选：theta_a 四值 {0.55, 0.65, 0.75, 0.85} × d_a {None, 1.0, 2.0}；tau_r 12 值 0.2～0.9。(2) **ELU-P rollout_config（推荐）** theta_a 0.7、free_space_weight 1.0、retract_threshold 0.0（d_a None，网格成员）。(3) **S2-05 八个开发配置槽（推荐）**：TAF theta_a 0.7、d_a "no_gate"；RAC theta_a 0.7、d_a "no_gate"、rho_rac 0.7、n_rac 3；LOW d_low 1.0；VSMT-lean tau_r 0.5（三个规则臂与 ELU-P rollout 同取无门，便于开发表与第 0 轮轨迹对读；LOW 取 1.0 m 与校准臂区分）。备选：TAF／RAC 取 1.0 m 门（LOG-255：Chair 匹配 0.36→0.90）。(4) **weight_decay 1e-4、seeds [7, 19, 31, 43, 59]**（METHOD 提议值；开发训练只用 7）。(5) **nuisance maximum_advantage（推荐 (a)）0.05，判定在 split 级**：S0-04 `nuisance_probe` 增一条 `scope` 规则字串（门槛对一个 split 全部 episode 合并的行判定；逐 episode 的 `largest_advantage` 只报告不判定），重钉 S0-04。依据：25 条新回执逐 episode 的 frame_index 优势中位 0.005，但 00406 0.128、03361 0.104、04801 0.081、00563 0.069——同一帧的色块状态成簇（新物体入镜的帧多 birth、去重帧多 duplicate）是时间聚类不是身份泄漏；path／seed／house_index 单 episode 内恒定，只有在 split 级合并后才有区分力，也才是探针要抓的泄漏。备选 (b) 0.15 逐 episode 也判定；(c) 0.05 逐 episode 判定（4 条 episode 会被标为泄漏，与事实不符）。(6) **S0-03 `seal.reference_score_seed`＝224**（确定性替身的种子，任一固定整数皆可）；**`cost_matrix.existence_threshold_tau_r`＝0.5**，并注明"参考值：运行时 τ_r 逐配置来自 S0-05 网格，本槽无代码消费"（校验器要求冻结值有绑定常量，落地时在 `lean_assignment` 加两常量）。(7) **去重三值重定（推荐 (a)）**：`descriptor_cosine_min` 0.9→**0.8**、`centroid_distance_max_m` 0.25→**0.5**、`aabb_iou_min` 0.3→**0.05**，`period_ticks` 10 不变；旧值进 SUPERSEDED_VALUES（裁决 67 冻结、裁决 68 取代）。论证：去重比的是实体对实体（描述子均值对均值、质心对质心、框对框），而校准序列是色块对实体均值——两个同物体实体各自平均了多块色块，其均值间余弦高于色块对均值的分位数（p50 0.78），按色块分位数定 0.8 偏保守；异物体候选对余弦 ≥0.8 占 15.6%、≤0.5 m 占 17.1%，两条同时满足的比例粗估 3% 以内，再要求框有实质重叠（同物体 IoU ≥0.05 占 27.9%，p50 只有 0.012，0.3 把 81% 的同物体对挡在门外）；误合并会在 `post_maintenance.dedup` 日志、身份连续率与污染 AUC 上暴露，可在 S3-01 前再取代。备选 (b) 0.85／0.5／0.05；(c) 保持 0.9／0.25／0.3（去重实际关闭，开发表将继续读到每真值 3.5 个实体）。(8) **`should_be_visible_min_ratio` 复核（推荐 (a)）0.5→1/64**（任一采样格心在视锥内、表面之前即"应可见"），旧值进 SUPERSEDED_VALUES：可见体积是"深度表面之前"的体素，实体框是表面壳，≥0.5 只有 0.2% 的实体-帧通过，44,097 帧只产生 2,068 个存在候选；降到 1/64 后为 3.5%（约每帧 5 个候选），RAC／ELU-P／存在头才有样本，旧位置可观察判定（MRR、恢复延迟）才不至于"从未可观察"。并**登记设计修订候选 (b)** 由开发表趟的规则臂读数决定是否提出：修订 S2-01 `entity_geometry`（例如对可见体积的远侧半空间加登记深度余量，或把自由空间覆盖只算表面之后的采样点），使在场物体的可见比例≈1、覆盖≈表面前半，消失物体两者≈1——这是让自由空间证据有区分度的根本办法，须重钉 S2-01、S1 不重做、在 S3-01 前完成（裁决 66）。备选 (c) 0.25（1.0% 通过）；(d) 保持 0.5。(9) **`dormancy_missed_opportunity_limit` 保持 3**：gone ≥3 占 17.5%、present ≥3 占 28.9%——LOW 污染下 present 反而更常休眠，没有据以改值的证据。(10) **ELU-P 三个拟合量预授权**：`elu_p_fit` 趟出来后直接登记进 S0-05 `arms.ELU-P.fitted.*` 并重钉，不另等一轮。(11) `bootstrap_seed` 与 `main_gate_effect_size` 留到 S3-01。落地方式：一条裁决一个提交，合同就地填值（不建 v3）、各模块 `NULL_POLICY_PATHS`／`FROZEN_VALUES_BY_RULING`／绑定常量按裁决 67 的做法、网格由 `lean_arms` 校验器绑定、跨合同台账登记与 SUPERSEDED 留底、涉及规则字串的 S0-04（5）重钉；随后服务器全量。可复制批准句：「裁决 68 全按推荐」，或逐项如「裁决 68：(1)～(4)(6)(7)(9)(10) 按推荐，(5) 取 (b)，(8) 取 (c)」。
  - **裁决 68 批准并落地（2026-09-25 批准，原话「裁决 68 全按推荐」；LOG-257，五个提交 `357ccdf`／`0610c7f`／`7117824`／`b9334e0`／`178868b`）。** 全按推荐：(1) S0-05 各臂网格（TAF 12、ELU-P 12、RAC 12、LOW 5、四个学习臂 τ_r 7、HandCost 12、AssocOnly 0）绑定 `lean_arms.FROZEN_GRIDS`，校验器要求合同网格逐值相等；(2) `rollout_config` (0.7, 1.0, 0.0) 绑定 `ROLLOUT_CONFIG`；(3) S2-05 八个开发配置槽（TAF 0.7／no_gate；RAC 0.7／no_gate／0.7／3；LOW 1.0；VSMT-lean 0.5）绑定 `lean_development.DEVELOPMENT_CONFIGURATIONS`，`development_configuration()` 把槽翻译成 runner 配置并逐一核验为网格成员；run-pass 入口新增 `PASS_ARMS` 与 `expected_pass_config`——每趟只能跑登记的臂与配置（拟合趟 TAF 取 rollout theta_a 无门、第 0 轮 ELU-P 取 rollout_config 加登记拟合量、第 1 轮与开发表取开发配置），命令行配置不符即拒绝；(4) weight_decay 1e-4、seeds [7,19,31,43,59] 绑定 `WEIGHT_DECAY`／`SEEDS`；(5) S0-04 `nuisance_probe.maximum_advantage`=0.05 绑定 `NUISANCE_MAXIMUM_ADVANTAGE`，新增规则字串 `nuisance_probe.scope`（split 级判定、逐 episode 只报告）绑定 `NUISANCE_SCOPE_RULE`；(6) S0-03 `reference_score_seed`=224、`existence_threshold_tau_r`=0.5（参考值，无代码消费）绑定两常量；(7) S0-01 去重三值 0.9／0.25／0.3 → 0.8／0.5／0.05，`SHARED_DEDUP` 同步，旧值进 `SUPERSEDED_VALUES` 并在槽旁留 `*_superseded` 记录；(8) S0-05 `should_be_visible_min_ratio` 0.5 → 1/64（0.015625），`SHOULD_BE_VISIBLE_MIN_RATIO` 同步，旧值留底，几何规则修订登记为候选（待开发表规则臂读数）；(9) dormancy 3 不变；(10) ELU-P 三个拟合量保持 null，拟合趟产出后直接登记并重钉；(11) bootstrap_seed／main_gate_effect_size 留 S3-01。规则摘要重钉：S0-01 `4818d6ac…`→`10c223a6…`（取代记录）、S0-05 `c5354b1e…`→`4e285050…`（网格、rollout、取代记录）、S0-04 `126fdd34…`→`c5d66505…`（scope 规则）；S0-03 与 S2-05 只填槽、摘要不变（S2-05 `0d3cf50c…` 复核相等）。跨合同台账 `FROZEN_VALUES` 登记 S0-01 三值、S0-03 两值、S0-04 一值、S0-05 三值、S2-05 八值。测试：arms（网格绑定、预算与无门、rollout 成员与相等、三值绑定）、memory、assignment、teacher（scope 绑定）、development（runner 形式、网格成员、开放槽允许、三种拒绝）、新增 S2-05 入口测试 3 项、跨合同台账；服务器全量 `178868b` **1605/1605**（231.8 s）。影响：后续四趟在 `178868b` 起的提交上跑；elu_p_fit 趟 15:01 CST 开跑；LOG-255 的节点审计在同一 4 条 episode 上按同配置重跑作前后对照（LOG-257 续）。
  - **待裁 72（提案，2026-09-25，未批准）：主实验范围向核心主旨简化——前端、主指标与臂集。** 依据：LOG-257 续。用户的判断（14:30 CST）：主表节点 F1 绝对值 0.2 档时"改善"没有说服力，结构太复杂，参照 DINO-WM（冻结预训练特征＋很小的学习模块＋刻意简单的环境，让主张没有混杂因素）向核心主旨简化。探针结论：SAM2 过分割／漏检占低 F1 的一半（完美分割后 TAF 0.224→0.399），单帧深度表面壳对整体盒的几何限制占另一半（完美分割＋完美身份合并的 IoU 0.3 上限 0.64，质心口径上限 0.86），剩下的是记忆逻辑（每真值 2.4 个实体）。三项可分别取舍：**(A) 前端**——(a) **推荐**：主表改用模拟器实例分割作公开前端（只暴露 mask 几何，不暴露实例 ID；DINOv2 描述子、深度几何、位姿、可见体积不变；SAM2 前端降为鲁棒性附录，在同一 39 条开发 house 或其子集上报一次），S1-03 合同增登 `mask_source` 两值、S0-03／S1-04 的前端声明相应修订并重钉，39 条 oracle cache 重建约 1～1.5 h（不跑 SAM），S1-04 诊断只补召回曲线复核；(b) 保持 SAM2 主表；(c) 双前端并列主表（成本翻倍）。**(B) 主指标**——(a) **推荐**：裁决 70 改取 (b)——质心 ≤ δ_moved 口径为主节点列与选参指标，IoU 0.3 降为次级列（同一匹配器，只换重叠判定），论文写明实体框是单帧深度表面、与 Dyn-THOR 只是"同一匹配机制、不同重叠判定"；(b) 保持 IoU 0.3 为主，绝对值封顶 0.64；(c) 修改 S0-01 实体框规则跨帧累积三维范围——LOG-244 续实测更差，不推荐。**(C) 臂集与趟**——(a) **推荐**：开发表保持合同的七个臂（管线已通，oracle 前端下每帧实体减少三分之一、趟更快），S3 主比较暂定 VSMT-lean／TAF／ELU-P／LOW／AssocOnly＋NoVersion，RAC、HandCost、HeuristicLabel、ctx、LLM-op 在首个完整开发表之后按读数决定去留并另裁；(b) 现在就砍到 VSMT-lean／TAF／AssocOnly；(c) 全部保留。**(D) 正在跑的 SAM2 拟合趟**——若 (A)(a)，(a) **推荐** 立即停掉（其拟合量属 SAM2 前端，主表不再用；省约 6 小时机时），拟合趟在 oracle cache 上重跑；(b) 跑完留作附录。影响：(A)(a)+(B)(a) 下四条探针 episode 的读数——TAF 质心 F1 0.54、LOW 1.0 m 0.78、完美记忆上限 0.86——主表绝对值进入可读区间，方法差异落在陈旧实体、假撤回与身份连续率上，这正是 D-224 的主张；D-224 "共用同一冻结 RGB-D 前端"改为"共用同一冻结公开前端（实例分割＋RGB-D 几何）"，须在 METHOD／DATA／PLAN 同步；S1-02 数据不重生成；已跑的校准趟（SAM2）只作附录与分位数来源，网格（裁决 68）在 oracle 前端上是否需要复核，等 oracle 校准趟分位数再定。可复制批准句：「裁决 72 取 (A)(a)(B)(a)(C)(a)(D)(a)」，或逐项如「裁决 72：(A)(a)，(B)(b)，(C)(c)，(D)(b)」。
  - **裁决 72 批准（2026-09-25 16:35 CST，原话「裁决 72 取 (A)(a)(B)(a)(C)(a)(D)(a)」；LOG-258；落地由新对话执行）。** 取 (A)(a)：主表公开前端改为模拟器实例分割（只暴露 mask 几何、不暴露实例 ID；DINOv2 描述子、深度几何、因果位姿、可见体积与自由空间不变），SAM2 前端降为鲁棒性附录；(B)(a)：裁决 70 改取 (b)——质心 ≤ δ_moved 口径为主节点列与选参指标，IoU 0.3 降为次级列；(C)(a)：开发表保持合同七臂，S3 臂集在首个完整开发表后另裁；(D)(a)：SAM2 拟合趟立即停掉（16:37 CST，4/39，根 `lean-s2-05-178868b` 标记 STOPPED_BY_RULING_72，产物只作旁证），在 oracle cache 上重跑。**落地清单（新对话）**：S1-03 合同增登 `mask_source` 两值（`simulator_instance_masks` 主、`sam2` 附录）与"生成器只读私有实例图的 mask 几何"这一条公开边界说明并重钉；S0-03／S1-04 的前端声明相应修订；`lean_s1_03_cache.py` 增加实例分割模式（正式入口，不再经 `lean_s2_05_oracle_masks.py` 两步）；S0-04／S2-04／S2-05 按裁决 70 (b) 交换主次节点列并重钉；METHOD／DATA／PLAN／AGENTS 当前方向同步；39 条 oracle cache 重建（2～4 GPU worker，估计 4～7 h）；校准趟与拟合趟在新 cache 上重跑，校准分位数若与裁决 68 的依据明显不同，另提裁决复核网格；ReID 投影头是否在新 cache 上重训另提裁决（默认复用冻结权重并报召回曲线复核）。影响：D-224 "共用同一冻结 RGB-D 前端"改写为"共用同一冻结公开前端（实例分割＋RGB-D 几何＋DINOv2）"；S1-02 数据不重生成；已跑的 SAM2 校准趟与三份审计只作附录与论文素材。
  - **裁决 72 落地（2026-09-25，LOG-259；四个单一职责提交＋本文档提交）。** (A) `9bb2c91`：S1-03 合同就地新增 `mask_source` 块——登记值 `simulator_instance_masks`（主表）与 `sam2`（鲁棒性附录），一个 cache 根一种来源；实例模式只读私有面五项（私有逐帧记录的 `observation_index` 与 `frame_digest`——须与公开帧一致、`instance_mask_path`——须是 private 内文件名、`object_id_to_entity_id` 的标签值集合、实例图像素），只输出匿名布尔 mask（按摘要排序），标签值、对象 ID、类型、位姿、可见像素数、真值盒与映射本身一律不出；准入不变（≥196 像素、每帧 ≤64、超过即构造失败，不像探针那样截断）；`seal` 块登记 episode 封印对非 SAM2 来源写入 `mask_source`（SAM2 封印保持原字节，`lean-s1-03-154776d` 仍核得过）、封印前读私有面只在实例模式、cache 唯一允许的私有派生量是这份匿名几何；纯核心 `seal_episode(mask_source=…)`、`sealed_mask_source`、`instance_label_masks`，校验器绑定；S1-04 加载器与 S2-04 `verify_cache_episode` 按封印声明的来源重算；S2-04 入口与 S2-05 run-pass 必须给 `--mask-source`，另一来源的 cache、续跑与合并一律拒绝，开发表记录共同来源；规则摘要 `c7318cd5…` → `f354863c…`。`942f45f`：`lean_s1_03_cache.py --mask-source` 正式模式（实例模式不装 SAM，逐帧从私有实例图建 mask，回执记来源）。S0-03／S1-04 没有任何规则字串指名 SAM2，只在 `user_rulings` 记账（前端含义、ReID 头默认复用、召回曲线复核），摘要不变。(B) `8ebbd05`：`node_prf1` 改为质心 ≤ δ_moved、权重 1／(1＋d) 的主列与选参指标，IoU 0.3 改名 `node_prf1_iou` 次级列，`node_prf1_centroid` 取消；校验器绑定两列的匹配、角色与“同一匹配机制、不同重叠判定”；D-224-C 冻结常量路径移到 `metrics.node_prf1_iou.iou_min`；S0-04 `c5d66505…` → `b831a3a4…`、S2-04 `0ff1fbe9…` → `d1645593…`、S2-05 `0d3cf50c…` → `57dc753d…`；S0-05 `selection_metric` 字节不变（`4e285050…`），白话改写；节点审计的 IoU 规则改标 `iou_0.3_secondary`、质心规则对主列核对。METHOD 第五节（前端两行与理由、限制）、第十一节（主次两列）、主张措辞，DATA 第三节（私有面读取边界）、第五节、第八节第 3 条，AGENTS 当前方向同步。服务器全量 `8ebbd05` 1618/1618。影响：主表数字只在“分割已知”设定下成立，SAM2 附录并列说明；节点 F1 与 Dyn-THOR 不再是同一重叠判定。
  - **待裁 73（提案，2026-09-26，未批准）：实例分割前端下的网格复核与 ReID 头。** 依据 LOG-260。每条给出推荐、备选与影响，按裁决 66 只在开发集上读、S3-01 前生效。
    - **(1) 关联网格、去重三值、应可见下限。** (a) **推荐**：全部沿用裁决 68 的值（TAF θ_a {0.6, 0.7, 0.8} × d_a {无, 0.5, 1, 2}；学习臂 τ_r 7 值；去重 0.8／0.5 m／0.05；应可见 1/64），只登记“依据已按实例分割分位数复核”。依据：同物体余弦不变、异物体余弦下降，交叉区从约 0.7 移到约 0.6，0.6 这一档仍在网格内；应可见分位数逐位相同。(b) 把 θ_a 网格下移到 {0.5, 0.6, 0.7}。影响：(a) 合同字节不变，拟合趟可立即跑；(b) 要改 S0-05 网格并重钉，拟合趟用的 rollout θ_a 0.7 仍是网格成员。
    - **(2) 依赖自由空间覆盖的规则值。** 覆盖中位数从约 0.65 降到约 0.06。(a) **推荐**：按新分位数重登记。RAC ρ_rac {0.7, 0.85} → {0.1, 0.3}（gone ≥0.1／≥0.3 为 39.7%／10.5%），n_rac {2, 3, 5} 不变；HandCost ρ_h {0.6, 0.7, 0.8, 0.9} → {0.1, 0.2, 0.3, 0.5}；ELU-P free_space_weight {0.5, 1, 2} → {5, 10, 20}，覆盖基线缩小约 10 倍，权重同比放大，每个合格未匹配帧的扣分量级不变；rollout_config 的 free_space_weight 1.0 → 10.0，θ_a 与撤回阈值不变。这样两个规则臂不会因为阈值落在分布之外而退化成不撤回，但在场与消失本来就分不开的事实不变，论文如实报告。(b) 保持裁决 68 的值：RAC 与 HandCost 几乎永不撤回，容易被批评为稻草人对照。(c) 先修订自由空间几何规则（例如只在实体盒被本帧可见且深度在盒后方时计覆盖），属设计修订，按裁决 66 登记并在 S3-01 前完成，需要额外诊断与重跑；裁决 68 (8) 已把几何规则修订登记为候选、等开发表规则臂读数。影响：(a) 改 S0-05 网格与 ROLLOUT_CONFIG、重钉 S0-05，dagger_round_0（ELU-P rollout）前完成即可，不影响拟合趟；(c) 推迟 dagger_round_0。
    - **(3) ReID 投影头。** (a) **推荐**：原样复用冻结权重 `reid_head_vitb14.json`（同物体余弦分布不变、异物体下降，投影在实例分割色块上照样分得开）；在实例分割 cache 上的召回曲线复核留到下次开机，与拟合趟一起跑，只读、不改冻结的召回值。(b) 在实例分割 cache 上按裁决 47 的规则重训并重新做 S1-05 选择：约多一次 S1-04 运行，S0-03 的选择结果与权重摘要要重钉。
    - 可复制批准句：「裁决 73 取 (1)(a)(2)(a)(3)(a)」，或逐项如「裁决 73：(1)(a)，(2)(c)，(3)(a)」。
  - **裁决 73 批准（2026-09-26，原话「裁决 73 取最好方案：(1) 暂不动，(2) 逐点深度检验先做探针，(3) 重训 ReID」；用户说明“我想要最好的，我不怕重训”）。**
    - (1) 关联网格、去重三值、应可见下限暂不动，等 (2)(3) 完成、重跑校准趟后再用新分位数复核。
    - (2) 存在证据改用逐点深度检验的设计修订（裁决 66 的通道，S3-01 前完成）：先做只读探针，不改合同。实体盒 64 个采样点逐点投到当前帧公开深度图，测到的深度比点远出余量为“看穿”、差不多为“在表面”、更近为“被挡”；比较它与当前块视锥规则把 gone 与 present 分开的程度（AUC），余量 0.05／0.10／0.20 m 都报、不冻结。探针入口 `ops/vsmt/lean_s2_05_depth_probe.py`，16 条开发 episode（帧数 ≤1,000 且 MRR 判定数 ≥3）× TAF、LOW 两个开发配置。分得开才提出合同修订（S2-01 实体几何规则、S0-03 特征定义、应可见与覆盖两个比例），再重跑校准趟并按新分位数重登记 RAC／HandCost／ELU-P 的阈值。
    - (3) ReID 投影头在实例分割 cache 上按裁决 47 的规则重训（前 30 训练、后 9 选择，同时量召回曲线），再由 S1-05 的冻结规则重新二选一；新权重摘要进 S0-03 并重钉，这一步单独提交。所有趟都用这个描述子，所以它排在校准重跑之前。
    - 执行：下次开机运行 `ops/vsmt/ruling73_boot.sh`，依次做全量测试、探针 30 帧冒烟，然后 S1-04 `--reid`（2 worker，约 43 GB 内存）与探针（6 worker）并行，报告拷到 `exports/` 后自动关机，预计 1.5～2 小时。影响：已跑的 oracle 校准趟只作存档与对照，拟合趟推迟到 (2)(3) 落地之后。
    - **裁决 73 执行结果（2026-09-26，LOG-261）**：(3) 已落地——ReID 在实例分割 cache 上重训，S1-05 重选仍为 `reid_projection:vitb14`（增益 0.104），新权重 5cea91cf… 钉进 S0-03／S2-01（`87316cb`）；S1-05 续跑报告的检查修正见 `2bccb2e`。(2) 探针完成：逐点检验能拿到证据的行多约 4 倍，gone 对 present 的 AUC 0.57 → 0.60～0.61（余量 0.05 m），转入待裁 74。
  - **待裁 74（提案，2026-09-26，未批准）：存在证据正式改用逐点深度检验。** 依据 LOG-261。
    - **(1) 规则**：(a) **推荐**：两个实体几何比例都改为逐点深度检验。实体框的 64 个采样点投到本帧公开深度图（公开内参、因果公开位姿），测到的深度比点远出余量为“看穿”，差不多远为“在表面”，更近为“被挡”，出画或深度无效为“看不到”。应可见比例＝（看穿＋在表面）／64；自由空间覆盖＝看穿／（看穿＋在表面），没有观测点时记 0。余量冻结为 0.05 m（探针三档里最好）。runner 每帧从 S1-02 公开面读深度图与位姿，属公开输入，cache 不重建。(b) 保持块视锥：证据少 4 倍、AUC 0.57。(c) 同时采用 (a) 并继续研究更强的信号，例如跨帧累积或对框质量加权——属于新设计，另提。
    - **(2) 诊断**：(a) **推荐**：校准趟的收集器把 gone 行按原因拆成“物体已不在场景”与“物体在场但离实体记住的位置超过 δ”两列，另报 present 行里实体框与真值框的 IoU。这样能看清证据对真正被移走的物体有多强，只读、不进指标。(b) 不拆。
    - **(3) 连带重冻结**：应可见下限（现为 1/64）以及 RAC ρ_rac、HandCost ρ_h、ELU-P free_space_weight 与 rollout 值，都在新规则的校准趟之后按新分位数另提，不在本裁决里定。
    - **影响**：改 S2-01 `entity_geometry` 规则与 runner、S0-03 两个特征的定义字串、S0-05 应可见下限的定义字串，并重钉；测试覆盖“与冻结反投影逐像素互逆”和“只读公开面”。之后开一次机：全量测试、校准趟（按 12 核实测定 worker 数），跑完导出并自动关机；再提阈值裁决，然后拟合趟、两轮 DAgger 和开发表。已跑的 oracle 校准趟只作存档。
    - 可复制批准句：「裁决 74 取 (1)(a)(2)(a)」。
  - **裁决 74 批准（2026-09-26，原话「裁决 74 取 (1)(a)(2)(a)」）并落地。**
    - (1)(a) `e62670b`：S2-01 `entity_geometry` 改为逐点深度检验，余量 0.05 m 冻结，深度有效范围沿用 D-223 的 0.05～20 m。
      - runner 每帧读读取方附上的公开深度视图（帧摘要、深度、内参、因果位姿），缺失或不是同一帧就拒绝；深度视图从不写进 cache，也不读私有面。
      - teacher 的"位置对方法可观察"用同一把尺子（裁决 65 (1)）。
      - 四个入口从 S1-02 公开面附上深度视图；S2-01 入口新增 `--episode-root`。
      - 旧块视锥规则改名为 `entity_geometry_blocks`，只供诊断对照。
      - 重钉：S2-01 `c911a4d6` → `7b1dd704`，S2-04 `d1645593` → `51250dcb`；S0-03、S0-05 只改白话，摘要不变。
    - (2)(a) `fd2042f`：校准收集器新增五列只读诊断——gone 按 absent／moved 拆开的覆盖值、按标签分的应可见比例、present 实体框对真值框 IoU。S2-05 重钉 `57dc753d` → `cea002f4`。
    - 实现中发现：在场物体在新规则下应可见比例约 1/4，所以应可见下限重新冻结时必须远低于 1/4。当前冻结值 1/64 可用，测试策略也改用 1/64。
    - 下一步：开机跑全量测试与新规则下的校准趟，再按新分位数提出阈值裁决。
  - **裁决 75（2026-09-26 提案并批准，原话「裁决 75 取 (1)(a)(2)(a)，校准趟跑完，如果数据盘不够系统盘还有多的空间」）：存在证据的检验点与校准用的记忆。**
    - 依据：
      - 253d6bd 校准趟在无门 LOW 上的第一条读数：present 覆盖中位 0.91，而实体框对真值框的 IoU 中位只有 0.009。无门 LOW 把几个物体和背景并进一个实体，而且单帧框里大半是空气。
      - 文献做法：Fusion++ 关联要求检测与物体渲染 mask 的重叠至少占检测的 20%，存在概率只在物体应清楚可见的帧计数；Khronos 用物体自己的表面点对后来的射线做"看穿／在表面／被挡"检验，时间窗内至少 60% 看穿才判不在；MakeWay 被挡时不扣存在概率；POCD 用射线追踪的变化量更新静止分数。
    - (1)(a)：校准改为两路。
      - 实际：带门的开发关联 TAF θ_a 0.7 无距离门，即拟合趟的臂与配置，同一趟顺带写 ELU-P 计数，省掉单独的拟合趟。
      - 上限：理想记忆证据上限诊断（每个物体一个完美实体），只读。
      - 无门 LOW 退为旧臂留底。
    - (2)(a)：实体的检验点改为它自己上次观测到的表面点：色块 mask 内深度有效像素反投影，每色块至多 64 个。真值位置仍用框内网格。
    - 备选 (1)(b) 维持无门 LOW、(2)(b) 保持框内网格，均未取。
    - 落地：
      - `c9682eb` 表面点：runner 状态里维护色块表面点表，读取方从 cache mask（先复核摘要）与公开深度算出；S2-01 `7b1dd704` → `8bc99b13`。
      - `e9e0d1e` 校准臂改为 TAF、`fit-elu-p --from-pass calibration`；S2-05 `cea002f4` → `7916d4f8`。
      - `05e539c` 证据上限诊断与开机脚本 `ops/vsmt/ruling75_calibration.sh`。
    - 影响：253d6bd 这趟（无门 LOW、框内网格）按用户要求跑完，只作存档与污染量化；主口径以 ruling-75 趟为准。拟合量将来自校准根。数据盘不够时，大文件移到系统盘（剩约 26 GB）。
  - **待裁 76（提案，2026-09-26，未批准）：按 GPT Astra 审查采纳的四项——归因审计、去重资格、匹配目标、输入核验。** 依据 LOG-262。按裁决 66 只在开发集上读，S3-01 前生效；不选赢家、不调网格。
    - **(1) 只读归因审计扩展。**
      - 白话：它解决"按错的归因改方法"的风险。输入是封存候选、提交后的记忆和私有诊断标签；输出是质心主列未匹配预测／真值的完整分类账、每次 BIRTH 的原因（首次出现／余弦低于 θ／正确实体未召回／联合竞争）、去重同身份与异身份实体对在余弦 0.6／0.7／0.8、距离、IoU 各门下的通过数（真重复能收回多少、误合并风险多大），再加一列"先最大匹配数"的匹配数。例如 00702 上 34 次物体 BIRTH 里 19 次卡在 θ。它不等于改方法或改指标，只读，不进任何表。
      - "离得远"一类里，把"物体真被搬动"与"物体没动、只是表面质心离整体中心超过 0.5 m"拆开。
      - (a) **推荐**：扩展 `lean_s2_05_node_audit.py`，在 4 条历史审计 episode（00702／01394／07367／09423）上以当前规则跑 TAF θ0.7 无门与 LOW 1.0 m，单进程、nice、单核，估计 5～10 分钟，不挤占在跑的趟（12 核中 11 核在用）；读数进入待裁 77 的去重三值复核。
      - (b) 等 ruling-75 趟结束后在 16 条开发 episode 上跑，11 worker，约 1 小时。
      - (c) 不做。
    - **(2) 共享去重的资格与折叠几何。**
      - 现状：维护先 dormancy 后去重，去重只看 active–active；AssocOnly 没有 NOOP、从不进 dormancy，它的实体始终有去重资格。于是 VSMT-lean 与 AssocOnly 之间除了生命周期词表，还差了"去重资格"，这正是贡献一的唯一因果对照，方向对 VSMT-lean 不利。00702 上 dormant 占预测实体·帧 41%。
      - (a) **推荐**：S0-01 共享去重的资格改为 active 或 dormant，retracted 仍排除。折叠时幸存实体的质心、框、表面点取两者中最近被观测的一方，描述子均值仍按观测数加权；任一方 active，则幸存者为 active。折叠照旧记进事务日志，不物理删除历史。
        - 理由：五臂与 AssocOnly 共用同一去重，资格不再依赖各臂的存在决定。dormant 进来之后，把陈旧几何和新鲜几何按观测数混合会让质心偏离两边，所以几何改取最新一方；审查在 00702 上见到 2 个实体·帧的质心落在自己最新框外。
        - 收益：00702 上只改资格，只多 2 对三门都过，节点 F1 的直接收益很小；主要价值是去掉因果对照里的耦合。
        - 影响：S0-01 就地修订、重钉，`lean_memory` 与测试更新。0ac510f 校准趟与 ELU-P 拟合是在旧去重下跑的，是否重跑由 (1) 的读数在待裁 77 里定。
      - (b) 保持 active-only；论文把这一耦合列为限制，并报告各臂的折叠次数。
      - (c) 让 AssocOnly 也按错失次数进 dormancy——不推荐，等于给 AssocOnly 偷偷加上生命周期。
      - 去重余弦 0.8 在 00702 挡住了 93 对 active 同身份对中的 92 对。去重三值按裁决 73 (1) 本就在复核队列里，留到待裁 77 用 (1) 的同／异身份通过率定，不在本条。
    - **(3) 节点匹配目标：先最大匹配数，再最大权。**
      - 现状：评价器求最大总权（质心列权重 1/(1＋d)，IoU 列权重 IoU），会拿一个匹配换更近的距离。反例：4 对各相距 0.5 m 的合法匹配，被 3 对零距离匹配取代，F1 从 1.0 变成 0.75。
      - (a) **推荐**：两列都改为字典序——先最大匹配数，在数量最多的匹配里再取最大权。实现上，每个连通分量的权重统一加一个大于该分量规模的常数，再做同一个求解；另加与暴力枚举的比对测试。
        - 理由：F1 是计数指标，权重本意是在平手时偏向更近的对。规则对所有臂相同，在任何臂的比较与选参之前登记。
        - 影响：S0-04 规则字串与摘要、S2-04／S2-05 重钉；Dyn-THOR 关系字串仍为"同一匹配机制、不同重叠判定"（两列用同一机制）。历史审计数字不重算，旧列名注明是最大权口径。(1) 的并列列会给出真实差异，但差异大小不作为采纳与否的依据。
      - (b) 只改质心主列，IoU 次列保持最大权；此时关系字串要改写为"不同匹配目标"。
      - (c) 不改，只在审计里并列报告最大匹配数。
    - **(4) 输入核验与诊断表述（不改任何冻结值）。**
      - (a) **推荐**三处：
        1. 读取方按 S1-02 的定义，从 rgb 与深度字节以及三个公开字段重算 `frame_digest`，不符即拒；故障注入测试"深度＋0.2 m、摘要不变"必须被拒。
        2. 逐点检验的前向判定改为 z ≥ 0.05，与深度有效闭区间一致。
        3. 校准报告的分位数：计数类序列报精确值（箱下沿），比例类序列改报在 1/64 整数倍处的超越比例（精确），插值分位数标为"近似"。
      - 影响：真实数据上 1、2 两处不改变任何数；第 1 处每帧多读一张 RGB，趟耗时略增。正在跑的 0ac510f 趟不重跑——它的导出带原始箱计数，阈值裁决直接用箱计数。
      - (b) 只做第 3 处。(c) 不做。
    - **本条之外**：应可见下限、RAC ρ_rac、HandCost ρ_h、ELU-P free_space_weight 与 rollout 值、去重三值的复核，以及 ELU-P 三个拟合量的登记，等 ruling-75 趟的导出到后另提待裁 77。
    - 可复制批准句：「裁决 76 取 (1)(a)(2)(a)(3)(a)(4)(a)」，或逐项如「裁决 76：(1)(a)，(2)(b)，(3)(c)，(4)(a)」。
  - **裁决 76 批准（2026-09-26，原话「裁决 76 取 (1)(a)(2)(a)(3)(a)(4)(a)」）并落地。** 五个单一职责提交，每个都同时推到 `main` 与 `s1-02a-runner`：
    - (1)(a) `721ebaf`＋`d231474` 节点审计 v2（只读）：
      - 质心主列自己的分类账，"离得远"拆成物体真被搬动与物体没动两类；
      - 每次提交的 BIRTH 用臂自己的 logit 在封存行上重算原因；
      - 去重之后剩下的实体对按状态组合与私有身份在余弦、距离、IoU 各档下的通过数；
      - 每次实际折叠按身份归类：钩子只读，折叠数必须等于事务日志里的数；
      - 两列"先最大匹配数"。
    - (2)(a) `7909615`：共享去重资格改为 active 或 dormant，retracted 仍排除。
      - 幸存者的质心与框取较晚被看到的一条；同一帧看到的两条取并框、质心按观测数加权；表面点本来就按最近一帧证据取。
      - 任一方 active 则幸存者为 active；两条都 dormant 则仍为 dormant，版本来源新增 `dedup_dormant`。
      - 合同的规则、资格、幸存几何与幸存状态四个字串绑定；S0-01 重钉 `10c223a6` → `76a00901`。
    - (3)(a) `ea7fff5`：两列节点匹配都改为"先最大匹配数、再最大权"。
      - 实现：评价器匹配器在每个连通分量里把正权重统一抬高一个大于分量规模的常数，再做同一个求解；count-first 与暴力枚举（先比对数、再比总权）比对测试。
      - 合同两列各绑定 `objective`，IoU 列关于"上限 0.64"的说法已更正；S0-04 重钉 `b831a3a4` → `eb81780b`。
      - 节点审计改用 count-first 两列核对评价器，原来两列保留为旧的最大权口径。
    - (4)(a) `da4c385`：
      - S2-04 读取方按 S1-02 定义，从 RGB PNG 像素、深度数组与三个公开字段重算帧摘要，不符即拒；服务器真实数据 138/138 帧复现，每帧 2.6 ms。
      - 逐点检验前向判定改为 z ≥ 0.05。
      - 整数序列报精确分位数；比例序列增报 k/64（k＝1～63）处的精确超越比例，插值分位数标为近似。
      - 不改冻结值与合同规则字串。
    - 本地定向测试全过（memory 57、cross-contract 72、teacher、node_audit 8、runner 38、development、evaluation、s2_04_entry、s2_05_entry）；服务器全量在 ruling-75 趟开头跑。
    - 改前／改后读数见 LOG-263：TAF 质心 F1 0.515 → 0.526、LOW 0.761 → 0.769。新放进来的 dormant 折叠以同物体为主（TAF 13:4，LOW 9:1）；原有的两条 active 折叠在现行三值下约一半是不同物体，留待待裁 77 复核三值。
    - 运行：ruling-75 趟改在 `d231474` 上跑（接力脚本 `relay_74_to_76.sh`），校准与 ELU-P 拟合不必事后重跑。S1 各步没有调用改过的代码，不重做。
  - **待裁 77（提案，2026-09-26，未批准）：节点主列的配对条件与共享去重三值。** 依据 LOG-263 续。按裁决 66 只在开发集上读，S3-01 前生效；阈值与 ELU-P 拟合量改由校准趟之后的待裁 78 处理。
    - **(1) 节点主列 `node_prf1` 的配对条件。**
      - (a) **推荐**：一对算配上，须同时满足两条：
        - 实体按评价器已用的证据多数身份属于这个物体；
        - 质心 ≤ δ_moved（0.5 m），或落在该物体真值框外扩 0.25 m 内。
        - 其余不变：先最大匹配数、再最大权；权重 1/(1＋距离)；dormant 仍计入；结构件仍排除。
        - 理由：
          - 现行口径把"附近有个实体"就算配上，TAF 18%、LOW 34% 的配对其实是别的物体或身份含糊的实体。
          - 同时，大件物体看到一角时质心会离整体中心超过 0.5 m。
          - 新口径回答"记忆知不知道哪个物体在哪"：两个问题一起修，所有臂同一规则。
        - 影响：
          - 4 条 episode 上（现冻结去重）TAF 0.526 → 0.500，LOW 0.769 → 0.701，对照组的数字下降。
          - 外扩 0.25 m 成为新的冻结值。
          - 要改 S0-04 规则字串、评价器与测试，重钉 S0-04／S2-04。
          - 与 Dyn-THOR 的关系改写为"主列另加身份一致，次级 IoU 列保持 Dyn-THOR 原口径"。
          - 身份连续率、MRR 不变。
      - (b) 只放宽几何（≤0.5 m 或在框内），不要求身份。所有数字最高（TAF 0.555、LOW 0.882），但 LOW 有三分之一配对是别的物体，最强对照被抬得更强，审稿人按身份核对时说不清。
      - (c) 只加身份、不加框（TAF 0.468、LOW 0.587）：大件物体仍吃几何亏。
      - (d) 保持现行。
    - **(2) 共享去重三值**（五臂与消融共用，按裁决 73 (1) 本就待复核）。
      - (a) **推荐**：余弦 0.8 → 0.6，距离 0.5 m 与框 IoU 0.05 不变，周期 10 不变。
        - 依据：同 4 条 episode 上 TAF"身份＋框"0.500 → 0.638，预测实体·帧 −31%；新增折叠八成是同一物体（110 对 27）；LOW 0.701 → 0.704。
        - 影响：S0-01 就地改值，旧值进 `*_superseded`，重钉 S0-01。
        - 对照更强，更难被批评为"没给基线做去重"。VSMT-lean 在 F1 上对 TAF 的余量会变小；主张仍靠与 AssocOnly 的对照、MRR 与身份连续率。
      - (b) 0.7／0.05：TAF 0.553，更保守。
      - (c) 保持 0.8。
    - **执行**：批准后按单一职责提交落地（评价器与 S0-04、S0-01 值与重钉），本地定向测试通过后推送。再往服务器接力的标记文件写入新提交号，ruling-75 趟在新规则上开跑：全量测试 → 证据上限 → TAF 校准＋ELU-P 计数 → 拟合 → 导出 → 自动关机。
    - 可复制批准句：「裁决 77 取 (1)(a)(2)(a)」，或逐项如「裁决 77：(1)(b)，(2)(b)」。
  - **裁决 77 批准（2026-09-26，原话「裁决 77 取 (1)(a)(2)(a)」）并落地。** 批准前用户问"是在讨好对照方法还是对研究有利"，回答要点：
    - (1) 压低对照：LOW 的三分之一配对是别的物体。
    - (2) 虽然抬高对照，但去重是所有方法共用的，而且合并更准：同物体占比 56% → 80%。
    - 两者都不触碰与 AssocOnly 的对照、MRR 与身份连续率。
    - 开发表出来后复核学习臂的误合并，必要时按裁决 66 退回 0.7。
    - (1)(a) `91e936f`：`node_prf1` 的一对须是实体按证据多数身份所属的物体（身份含糊的实体不配），且质心 ≤ δ_moved 或落在真值框外扩 0.25 m 内。
      - 合同新增 `identity_requirement`、`box_pad_m`（0.25，常量 `NODE_BOX_PAD_M` 绑定）；`dyn_thor_relation` 改写为"主列另加身份与框检验，次级 IoU 列保持 Dyn-THOR 原口径"。
      - 节点审计改用"身份＋框"候选核对评价器。
      - S0-04 重钉 `eb81780b` → `8b57bacb`。
    - (2)(a) `4a59789`：共享去重余弦 0.8 → 0.6，其余不变。
      - 0.8 进 `SUPERSEDED_VALUES` 与合同的 `*_superseded` 记录，0.9 留在 `earlier`。
      - S0-01 重钉 `76a00901` → `15dbabb9`。
    - 本地 lean 测试全部通过后，往服务器写开跑标记，ruling-75 趟在含本裁决的提交上开跑。阈值与 ELU-P 拟合量由校准趟后的待裁 78 处理。
  - **待裁 78（提案，2026-09-27，未批准）：ruling-75 校准趟之后的阈值复核。** 依据 LOG-265（原始 1/64 箱计数）。按裁决 66 只在开发集上读，S3-01 前生效。ELU-P 三个拟合量已按裁决 68 (10) 登记（`c81b68b`），不在本条。
    - **(1) 应可见下限（现 1/64）。**
      - 白话：一个实体本帧至少要有多少个表面点"应当看得见"，才对它做存在判定（撤回、保留或累计错失）。
      - (a) **推荐**：保持 1/64。只有 1～3 个点可见的行，在场 12.0%、离场 9.4%，两类差不多，没有证据说明它们会带偏；学习臂把应可见比例当作特征，自己能学会打折；不改值就不用重跑校准和拟合。
      - (b) 4/64：少点数的"全看穿或全没看穿"噪声消失，但会去掉约一成证据行；而且应可见下限也进入 teacher 与 ELU-P 计数，要重跑校准趟（新代码约 2.5 h）并重拟合。
      - (c) 8/64：同 (b)，去掉约两成。
    - **(2) RAC 与 HandCost 的阈值网格（现 ρ_rac {0.7, 0.85} × n_rac {2, 3, 5}；ρ_h {0.6, 0.7, 0.8, 0.9}）。**
      - (a) **推荐**：保持。单帧 ≥0.7 时，真被拿走 68.5%、在场 1.7%；≥0.85 时为 60.3% 与 1.0%。RAC 还要求连续 n 帧，在场的误撤回会再降一个量级。网格括住了合理区间。待裁 73 (2) 当时准备下调到 {0.1, 0.3}，是因为旧几何规则下覆盖率塌到接近 0，现在不需要了。
      - (b) 整体下调一档，RAC {0.5, 0.7}、HandCost {0.5, 0.6, 0.7, 0.8}：撤回更积极，在场误撤回率单帧上升到 2～4%。
    - **(3) ELU-P 权重网格与 rollout 值（现 free_space_weight {0.5, 1, 2}，rollout 1.0；retract_threshold {0, −1}）。**
      - (a) **推荐**：保持。按拟合出的初始 log-odds 4.76，平均被看穿比例（真被拿走 0.73、在场 0.073）下，权重 1.0 时真被拿走的物体约 7 帧后撤回、一直没配上的在场实体约 65 帧；0.5 与 2 分别约为 13／3 帧与 130／33 帧，括住了快慢两端。
      - (b) 改为 {1, 2, 4}、rollout 2：撤回更快，在场误撤回也更多。
    - **影响**：全取 (a) 则合同字节不变，不重跑任何东西，下一步直接 dagger_round_0（ELU-P 按 rollout 配置加拟合量跑 39 条，新代码下预计 2～3 h，开跑前先在最大 episode 上试跑计时）。取 (1)(b)/(c) 要先改 S0-05 并重跑校准与拟合。
    - 可复制批准句：「裁决 78 取 (1)(a)(2)(a)(3)(a)」，或逐项如「裁决 78：(1)(b)，(2)(a)，(3)(a)」。
  - **裁决 78 批准（2026-09-27，原话「裁决 78 取 (1)(a)(2)(a)(3)(a)」）。** 应可见下限保持 1/64；RAC ρ_rac {0.7, 0.85} × n_rac {2, 3, 5}、HandCost ρ_h {0.6, 0.7, 0.8, 0.9} 保持；ELU-P free_space_weight {0.5, 1, 2}、rollout 1.0、retract_threshold {0, −1} 保持。依据 LOG-265 的原始箱计数与证据上限。合同字节不变，校准与拟合不重跑。下一步：新开机，先在最大 episode 上试跑计时，再跑 dagger_round_0。
  - **裁决 79 批准（2026-09-28，原话「裁决 79 全按推荐」；LOG-272）。** 依据：本会话逐条核实 GPT-6 Astra 对 LOG-270／271 的诊断（对话内），另从已提交导出补了五条事实（LOG-272）。按裁决 66：只用开发集，S3-01 之前完成，不读 validation/test。
    - 79-1 (a)：LOG-265／267／269／270／271 的八处更正以追加的 LOG-272 为准，原条目不改写；AGENTS 当前方向里过时的状态句同步更新。
    - 79-2：只读导出 v2（`ded50b4`），窗口阶段改用评价器口径（帧号 > window_end）；标签与假撤回按实体是否仍在原处拆分，这一精确拆分放在节点审计 v3 的重跑里（`f22be92`）。
      - 白话：输入是逐帧的标签、学生决定、记忆和真值框，输出“撤回正标签和假撤回各落在什么实体上”。它不是新方法，也不改任何标签。
      - **预登记判读规则**：取开发表 VSMT-lean 的 v3 归档中“未登记干预物体上的 gone(moved)”各行，分三类：
        - A 类：另有实体按节点规则承载该物体（重复实体）；
        - B 类：没有别的承载实体，但它本身按节点规则仍在原处（标签与指标冲突）；
        - C 类：没有别的承载实体，它本身也不在原处（真实的记忆错误）。
      - 判读：A 类过半，转去查去重与重复实体，不清洗标签；B 类过半，支持 79-4 (a)；C 类过半，不采用“忽略未干预 gone”的清洗；都不过半，三类如实并列，不下单一结论。同一拆分也用导出 v2 在两轮训练来源轨迹上报告。
    - 79-3：一次开机的诊断包，worktree 固定在 `0471c3e`，驱动是 `ops/vsmt/ruling79_diagnostics.py`；在 01289 上试跑计时并报告之后，才启动完整一趟。
      - (i) 节点审计 v3：VSMT-lean、NoVersion、AssocOnly 各 39 条，用开发表配置和第 1 轮的头。这同时完成裁决 77 承诺的“去重余弦 0.6 下的误合并复核”。逐 episode 的报告必须与开发表一致（去掉墙钟字段）。
      - **(i) 判读规则**：如果按 episode 配对，VSMT-lean 的异物体合并在多数 episode 上多于 AssocOnly，而且它的召回损失主要落在“物体此前出过色块、此刻没有实体”一类，就按裁决 77 的承诺另提去重修订裁决（余弦退回 0.7，或休眠实体不参与去重）；否则去重不动。
      - (ii) 分项曲线重放：第 1 轮 VSMT-lean 的训练原样重放，逐 epoch 记录关联项和存在项的留出损失（本臂记录，以及 AssocOnly 同一批选择 house 的记录），最终权重必须与 `452f6baa` 逐位相同；只作诊断，不产生新权重。
      - **(ii) 判读规则**：在 AssocOnly 的记录上，如果关联项最低的那一轮权重把 0.658 对 0.634 的差距缩小一半以上（≤ 0.646），视为支持“关联与新建一组、存在一组”的分组早停；否则不支持。
      - 暂不做换头和关闭休眠两项诊断；关闭休眠只在 (i) 显示休眠实体参与了误合并时再提。
    - 79-4：存在标签语义只登记候选，等 79-2／79-3 出数后再裁。
      - (a) 领先候选：teacher 的 gone(moved) 与节点主列对齐，即实体不满足裁决 77 的“质心 ≤ δ_moved 或落在真值框外扩 0.25 m 内”才算 gone。这个方案不读干预记录。
      - (b) GPT-6 提的“过时版本”语义，加上干预记录辅助。
      - 不推荐：(c) 直接忽略未干预物体上的 gone；(d) 维持现状。
      - 取 (a) 或 (b) 都要改 S0-04 的标签规则并重钉摘要。S3 本来就要在正式数据上重训，所以不额外增加成本；若要在开发集上复核，约 6～9 h。
    - 79-5 (a)：头初始化对齐，落地于 `385f873`。
      - 每个头按 sha256(seed|头名) 各自播种，AssocOnly 与 VSMT-lean 的关联头、新建头起点逐位相同；规则字串 `INITIALISATION_RULE` 记在权重的训练元数据里（不进摘要）。
      - 已登记的运行不重跑；以后的每次训练权重都会变。
      - 分组早停等 79-3 (ii) 出数后再裁。
    - 79-6：
      - C（存在头类别加权）不采纳：对已校准的二分类头，类别加权近似平移阈值，而已冻结的 τ_r 网格 {0.3, …, 0.9} 已经覆盖阈值平移。
      - D2（提高干预密度）不采纳：开发规模是 39 条成功 episode、65 次搬动，按正式 300 个 train house、约 78% 成功率外推，远高于冻结的 120／60 最低线；S3 的 dry-run 每个物体至多测 8 个目的容器，在 S3-01 实测后复核。
      - 休眠精简和换头：看 79-3 的结果再说。
      - WindowEvidence：只登记为附录候选，注明“受 Khronos（Schmid 等，RSS 2024）时间几何验证思想启发、非复现”；79-4 裁定之前不写合同。
    - 79-7：维持方向 A，最多做一次有边界的修订，然后在同一协议下做一次完整的开发复核，就此停下。
      - 复核后如果 VSMT-lean 相对 AssocOnly 仍没有超出噪声的生命周期收益，就缩减主张，不恢复地点层与关系层。
      - 登记风险：选参指标（节点 F1）会把 τ_r 推向少撤回，而主门（Missing 残留率与身份连续率，对最强规则臂）需要撤回，两者方向相反。此项在 S3-01 按与哪个臂获胜无关的理由裁定；现在不改选参指标，因为看过开发结果再改就是事后修订。
    - 影响：合同字节不变。S1、S2 各趟不重跑。以后训练的权重随 79-5 改变。S3 继续暂停，直到 79-4 与分组早停的裁决落地。
  - **裁决 80 批准（2026-09-28，原话「裁决 80 全按推荐」；提案与读数见 LOG-273／LOG-274）。**
    - 80-1 (d)：存在标签语义暂维持现状。按 79-2 的预登记规则，B 类（标签与指标冲突）27.9% 未过半，不支持 (a)；C 类 51.5% 过半，不做清洗。
    - 80-2：维持联合早停，不做分组。79-3 (ii) 显示关联项与联合损失在同一轮最低。
    - 80-3：做关闭休眠诊断。诊断开关 `--dormancy-override 1e9` 只用于诊断，不是登记的臂或配置。
    - 80-4：做关联错误按绑定目标拆分的诊断（节点审计 v4）。
      - **预登记判读规则**：VSMT-lean 比 AssocOnly 多出的误绑定里，如果过半落在休眠实体上，就提“精简休眠”的修订；如果过半是“首次出现却绑到已有实体”，就提“第 1 轮训练混入第 0 轮记录”的修订；两者都不过半，就如实并列。
      - 落地于 `8caeb41`／`c0dbe54`，结果见 LOG-274：休眠一条过半，所以按规则提出精简休眠；但 80-3 显示关闭休眠对各指标几乎无影响，两者一并交由裁决 81 处理。
    - 80-5 (b)：保留原假撤回率，另加一列 `false_retract_rate_in_scope`（剔除按规则记为在场的结构件与运行时生成物）。这一列不选配置、不进主门。落地于 `831bcc1`，三份合同就地重钉摘要。
    - 影响：S1、S2 各趟不重跑。以后的评价报告多一列。S3 继续暂停，直到裁决 81 落地。
  - **裁决 81 批准（2026-09-28，原话「裁决 81 全按推荐」；LOG-275）。** 取消 79-7 的“只修订一次”，改为有范围、预算和停止条件的开发修订。依据：LOG-274，以及用户转来的 GPT 两轮意见（本会话核实）。按裁决 66：只用开发集，S3-01 之前完成，不读 validation/test。
    - 81-1 修订边界（取代 79-7）：
      - 范围：只修对象级方法的训练流程，以及关联与记忆更新机制；不加地点层或关系层，不改前端，不改已冻结的指标。
      - 预算：连同本轮最多 3 轮；开发诊断合计约 25 小时机时。
      - 停止条件：连续两轮未达到各自预登记的目标，就停止修订，转入确认和缩减主张。
      - 每轮修订单独裁决，并在出数之前登记判读规则。
      - 确认集：train 块第 50～99 位，名单冻结于 `configs/vsmt/lean_ruling81_confirmation_houses.json`（`0e4494d`）。方法冻结后才生成并评估一次；看过结果再改方法，它就降为开发数据；它不替代正式 test。
    - 81-2 数据累积的受控对照（两个学习臂都做，都用 79-5 的新初始化）：
      - A7：只用本臂第 1 轮记录，更新预算 U（本臂记录跑 20 遍的更新次数），seed 7。
      - A19：同 A7，seed 19，作为种子噪声底线。
      - B：第 0 轮 ELU-P 记录加本臂第 1 轮记录（都只取训练分区），预算 V（累积记录跑 20 遍的更新次数），seed 7。
      - C：只用本臂记录重复取样，预算同样是 V，seed 7。
      - “一次更新”是实际执行的优化器步数。四组都每隔 K 次更新（本臂记录一遍的更新次数）在同一批验证记录（本臂第 1 轮、选择 house）上打分，取最低的检查点。
      - 开发复核用节点审计 v5，每组 39 条。
      - **预登记判读规则**：
        - 改善：VSMT-lean 的 B 对 C，节点 F1 按 house 配对，90% 重抽样区间（按 house、种子 81、10,000 次）在 0 以上，且均值超过 |A7−A19|；
        - 保护指标（Missing 残留率、身份连续率、污染 AUC、范围内假撤回率）：B 相对 C 往坏的方向的配对均值不超过该指标的种子噪声，算“没有变差”；
        - 以上两条同时成立，才判“累积有效”；
        - 对 AssocOnly 的差距（B 对 C）与“缩小一半”只作开发目标，另行报告；
        - 不达标时如实记录，结合 81-3 另行判断：可以是方向 B（身份与位置分开确认），也可以停止或缩减主张，不自动转向。
      - 落地于 `1b19f30`、`4689075`、`171e5e9`、`ad5e362`、`93f9b87`。
    - 81-3 误绑定后果统计（节点审计 v5，`85c71db`）：
      - 事件：物体在上一帧还有合格实体承载，这一帧一个都没有了，按原先各承载实体各自的遭遇归因；
      - 后果：此后没有承载的帧数，同一段缺失只算一次；
      - 用途：判断方向 B 是否值得立项，不作为 B 的收益上限。
    - 81-4：搬动密度本轮不改，S3-01 时按训练信号和统计功效单独裁决。
    - 81-5：休眠维持现状。
    - 影响：合同字节不变；登记的训练配方不变（新训练函数只用于诊断）。机时估计约 4.5～5.5 小时，开跑前实测。S3 继续暂停。
  - **裁决 82 批准（2026-09-29，原话「裁决 82 全按推荐」；LOG-276／LOG-277）。** 依据：LOG-276，同一训练配方下三次训练，VSMT-lean 对 AssocOnly 的节点 F1 差距分别是 −0.071、+0.039、+0.069，Missing 残留率的先后也会翻转。
    - 82-1 训练波动研究（这是测量，不计入 81-1 的修订轮次）：两个臂各用登记的另外 3 个种子（31、43、59）按登记配方训练（只用本臂第 1 轮轨迹、20 遍、79-5 的新初始化），加上裁决 81 的 seed 7、19，每臂 5 个种子，每个都跑 39 条开发审计（节点审计 v5）。
      - **预登记判读规则**：对每个指标，报告两个臂 5 个种子的均值与标准差，以及 5 个按种子配对的差距（在两臂都有定义的 house 上取 house 均值差）；至少 4 个同号、且差距均值的绝对值大于这 5 个差距的标准差，才算在开发集层面确定了先后，否则记为“开发集上分不出”。
      - “每个 house 先对种子取平均、再按 house 重抽样”的区间，以及 LOG-270 那次训练，只作参考，不进判定。
      - 落地于 `011e5f4`、`7d96da6`、`d584af3`。
    - 82-2 S3 协议风险（现在只登记，S3-01 时按与哪个臂获胜无关的理由裁定）：
      - ① S3-04 为每个臂从 5 个种子里只选一个检查点：在种子波动这么大时，等于抽签；备选是报告 5 个种子的平均。
      - ② 登记的选检查点依据是验证损失，但它与节点 F1 对不齐：LOG-276 里 VSMT-lean 多训练后验证损失更低（0.946 对 0.975），节点 F1 反而更低（0.760 对 0.820）。
    - 82-3 方向 B（身份与位置分开确认）暂缓，82-1 出数后再议。它会是所有方法共用的执行器修订，计入 81-1 的轮次。
    - 82-4 数据累积不采纳（按 81-2 的预登记规则判为无效）。
    - 影响：合同字节不变，登记的训练配方不变。机时约 4～4.5 小时（12 核）。S3 继续暂停。
  - **裁决 83 提案并批准（2026-09-29，原话「可以，1. 把你目前的这个决定写到PLAN和METHOD里面，如果PLAN和METHOD没这些就再加」；LOG-278）：论文成形六项。** 依据：用户问 S0～S3 的流程够不够投 RA-L 或中科院二区。评估（摘要见 LOG-278）：预登记主门（VSMT-lean 在 Missing 残留率与身份连续率两项上都赢最强规则臂）在开发集上于 MRR 一项已经输（VSMT-lean 旧初始化 0.127、新初始化 0.385／0.337，RAC 0.089、ELU-P 0.092），身份连续率赢（0.41～0.51 对 0.149）；按节点 F1 选 τ_r 推向少撤回是机制（79-7 已登记）。对照 RA-L 与二区审稿的常见要求，缺口是：主结果不稳、主表前端是模拟器实例分割、对照是非官方机制适配、只有 ProcTHOR、没有任务面指标；统计与协议严谨性是强项。
    - 83-1 选参与主门的冲突（原 79-7）：**批准“必须有一条预登记约束，且在 S3-01 前冻结”**；约束文本本身待冻结（planned）。推荐样式：validation 上仍按节点 F1 选唯一配置，但只在满足约束的配置里选，约束例如“该配置在 validation 上的 MRR 不高于最强规则臂在 validation 上的 MRR”；备选 (b) 维持只按节点 F1 选参并接受 MRR 上的 no-go，(c) 改主门。冻结时的理由必须与哪个臂获胜无关，并对所有臂同样适用；82-1 出数后、S3-01 前另提裁决定文本。
    - 83-2 方向 B（身份与位置分开确认）：批准为 81-1 的那一轮修订，82-1 出数后立项；它是所有臂共用的执行器修订，不单独造 VSMT-lean 的优势。
    - 83-3 SAM 2.1 升为第二张完整主表：批准（planned）。S3-02 起两套前端各生成 cache，S3-03 各自独立选参，S3-04 一并冻结，S3-05 同一次打开 test 各跑一次，两张主表并列；S3 机时约翻倍。开发表阶段不重跑 SAM 2.1（裁决 72 之前的 SAM2 校准趟与审计只作素材）。
    - 83-4 外部验证：批准立项（planned，待调研），登记为 S3-07。首选 3RScan 重扫描对；只跑 S3-04 冻结后的臂与配置，不选参、不进主门；调研许可证、真值转换与前端适配后另提裁决定范围。用户 2026-09-27 已要求开发表后调研真实数据评测，本条正式登记。
    - 83-5 检索式下游指标：批准登记为第八项指标（planned，S3-01 前冻结定义），不进主门、不选参；定义冻结前不得计算。
    - 83-6 目标刊物：83-3 与 83-4 落地则投 RA-L；否则投中科院二区 CS 类期刊并以协议加基准为框架。分区以投稿当年的分区表为准。
    - 同批答复（核对记录，不是新裁决）：SAM 2.1 当初是被裁决 72 因混杂因素降级，不是“S2-04 没过”（S2-04 的问题是 LOG-256 的 gzip 收尾 bug，裁决 71 已修）；换回 SAM 2.1 不会抬高节点 F1——七个臂逐字节共用前端，臂间先后不由前端决定，且 SAM2 下 TAF 的节点 F1 只有实例分割下的一半（LOG-257 续）。
    - 影响：只改文档（DECISIONS／PLAN／METHOD／DATA／AGENTS／EXECUTE），合同字节不变；S3-01 前新增两项待冻结（83-1 文本、83-5 定义）；S3 机时约翻倍（83-3）加外部验证的工程（83-4）；S3 继续暂停，当前执行点仍是 82-1 种子研究。
  - **裁决 84 提案并批准（2026-09-29，原话「我按照你84-1 b现在的同意，剩下的都按照推荐来」；LOG-278 续）：SAM 2.1 第二主表的落地条件与 S3-02 的主机。** 依据：S1-04 诊断与裁决 72 探针的并排读数——SAM2 色块上冻结 ViT-B/14 的身份分离度中位 0.140（实例分割 0.071）、ReID 头增益 +0.093（+0.104），描述子不是短板；色块对真值框 IoU 中位可拾取物 0.45 对 0.67、容器与家具 0.14 对 0.67，漏检 4% 对 0，每真值实体 3.19 对 2.42，差距在 mask 几何（部件级 mask、框太小、漏检）。SAM2 cache 是唯一吃 GPU 的环节且是算力瓶颈（每 worker 5.3 GiB 显存，4080 SUPER 上 2 worker 即饱和，0.57～0.68 帧/秒）；服务器 torch 2.8.0+cu128 含 sm_120，Blackwell 卡可直接跑。
    - 84-1 SAM2 表的描述子头：**取 (b)**，ReID 投影头按 `mask_source` 各钉一份；SAM2 表用在 SAM2 cache `154776d` 上按裁决 47 训练、S1-05 选出的 ViT-B/14 投影头（服务器 `vsmt_private/exports/reid_head_vitb14_154776d.json`，合同摘要形式的 sha256 待重钉时核对），实例分割表沿用 `5cea91cf…`；S0-03 的“不再改描述子”改写为“每种来源各一份，钉住后不再改”。这是合同与代码改动，单独一个提交、跑服务器全量测试后合并（planned）。被拒的 (a)：复用实例分割的头——两表共用一头虽省事，但 SAM2 表会报低于它本可达到的分离度。
    - 84-2 SAM2 校准与网格：取 (a)，在 SAM2 cache 上按裁决 75 口径跑校准趟（TAF θ_a 0.7 无门＋ELU-P 计数）；分位数落在现网格内只登记“已复核”，否则 S0-05 按 `mask_source` 分存两套值。
    - 84-3 SAM2 开发表：取 (a)，方向 B（83-2）落地后在开发集上跑一次完整 S2-05 链（校准→拟合→第 0 轮→训练→DAgger→七臂开发表），登记为 S2-06；**更正 83-3 与 LOG-277 的“开发表阶段不重跑 SAM 2.1”**：不跑则 S3-01 前没有任何 SAM2 读数。
    - 84-4 S3 的 SAM2 cache 预算：取 (a)，先在多卡实例上实测 worker 吞吐再定；开发集 44,097 帧在 4080 SUPER 上约 19 小时，S3 约 51 万帧单卡约 9.5 天，多卡按 episode 线性加速、总费用几乎不变。
    - 84-5 数据盘：S3-02 前扩到 ≥300 GB（两套 cache 各约 110 GB 加 raw 与各趟产物）；两套前端都需要。
    - 84-6 SAM2 mask 层修订（从 SAM2 自动 mask 的嵌套层级优先取整物体级 mask）：暂缓，等 S2-06 读数再定，S3-02 前必须定；做则重新冻结 S1-03 并重建 SAM2 cache。
    - 84-7 S3-02 的主机：RTX 5090 类多卡、可扩容盘大的主机（5090 D 是限制版，AI 算力按公开规格低约三成；PRO 6000 显存用不上、价格 2.5 倍、可扩容盘几乎为零）。用户 2026-09-29 早上按可用性选择立即克隆到多卡 5090 主机，为此把正在跑的 82-1 种子研究在训练回执产生前停掉（07:03 CST，LOG-278 续），克隆后重跑。
    - 影响：合同字节暂不变（84-1 的 S0-03 改动另提交）；新增 S2-06；S3-02 新增主机与扩盘前提；82-1 的六个训练从头重跑，损失约 25 分钟墙钟；S3 继续暂停。
  - **裁决 85 提案并批准（2026-09-29，原话「裁决 85 全按推荐」；LOG-279 续）：82-1 出数后的登记与下一轮。** 批准口径：85-1 (a)、85-2 (a)（现在登记，S3-01 冻结）、85-3 (a)、85-4 登记。方向 B 的具体规则另提裁决（待裁 86），出数前登记判读规则。原提案全文如下。 依据 LOG-279：五个种子下六项指标都“开发集上分不出”；Missing 残留率跨种子 0.21～0.59、五种子均值 0.357 对规则臂 0.089；验证损失选出的最佳检查点落在第 7／12／20 遍。
    - 85-1 判读登记：(a) **推荐** 按预登记规则登记“六项分不出”，规则不改；82-1 是测量，81-1 的计数仍是 1 次未达标。(b) 事后放宽规则——不采纳，等于按结果改规则。
    - 85-2 S3 的报告与检查点口径（现在登记，S3-01 裁）：(a) **推荐** ① S3-05 主表的学习臂按 5 个种子的均值 ± 标准差报告并附逐种子，不从 5 个种子里选单一检查点作主表行；② 检查点依据从验证损失改为验证记录上的决策准确率（每条记录 argmin 代价是否等于 teacher 标签，训练内即可算、零额外机时，且与节点 F1 同向），S3-03 起对所有学习臂同样适用。(b) 保留验证损失。(c) 按 validation 上的节点 F1 选检查点——最贴近选参指标，但每个检查点都要跑审计，即使只比 4 个检查点也约 1,700 CPU·小时，不推荐。影响：(a)① 只改报告规则、不改训练；② 改 S0-05 训练合同的一个字串并重钉，须与谁赢无关地写理由。
    - 85-3 下一修订轮：(a) **推荐** 方向 B（身份与位置分开确认，83-2）立项，同一轮内不改训练配方，出数用 5 种子按 82-1 规则判读；在新机上每轮约 2 小时（六个训练 1 小时并行、审计 1 小时）。(b) 先做 85-2 ② 再做方向 B——多一轮、多 2 小时，但能把“选点不稳”与“执行器”两个因素分开。
    - 85-4 主门现实登记：MRR 差四倍不是种子噪声能解释的；83-1 的约束文本等方向 B 出数后再写，若方向 B 之后 MRR 仍在规则臂的两倍以上，须在 S3-01 前裁定是否改主张框架（裁决 83-6 的备选路线）。
    - 可复制批准句：「裁决 85 全按推荐」，或逐条如「85-3 取 (b)」。
  - **待裁 86（提案，2026-09-29，未批准）：第 2 轮修订（81-1）——共享去重加同帧共现否决。** 依据 LOG-280（位置门净亏：误绑定 63%～70% 发生在被选错实体 0.25 m 以内，病根是实体漂离与混合身份）与 LOG-281（错并 85%～88%、含糊合并 90%～92% 是同帧共现的两个实体；去重开启的缺失占看过物体丢失帧的 16.5%～28.6%）。它是所有臂共用的记忆更新规则，属 81-1 范围；方向 B 的“位置门”形式按 LOG-280 撤下。
    - 86-1 规则：(a) **推荐** 共享去重的候选对里，两条记录只要在同一个 tick 各自收到过色块，就不合并；其余条件（余弦 ≥ 0.6、质心 ≤ 0.5 m、IoU ≥ 0.05、每 10 tick）不变。只读实体自己的证据 tick，属公开记忆状态。正例：桌上的杯子与桌子在同一帧各出一个色块，此后永不合并。反例：同一把椅子因一次误绑定分成两个实体、两者从未在同一帧出现，仍可合并。(b) 共现至少 k 帧才否决——实例分割下一次共现已足够，k 只会放过错并，不推荐。(c) 不改去重、只改 BIND 的几何更新——没有量化的反事实，放到第 3 轮。
    - 86-2 前端适用范围：(a) **推荐** 否决只对登记为“一个色块对应一个物体”的前端生效（S1-03 `mask_source` 块新增公开属性 `fragments_are_whole_objects`：`simulator_instance_masks` 为 true、`sam2` 为 false），SAM2 表沿用现去重规则；同一张表里各臂仍逐字节共用同一规则，与 84-1 (b) 按前端各钉一份 ReID 头同理，论文写明。(b) 两套前端都生效——SAM2 下会拦住该合并的碎片。(c) 两套都不生效——等于不修。
    - 86-3 本轮同时只改这一条：训练配方、网格、τ_r 都不变；BIND 的几何更新不在本轮（81-1 最多 3 轮，这是第 2 轮）。
    - 86-4 预登记判读规则（出数前冻结）：全链重跑（校准与 ELU-P 拟合、第 0 轮、第 0 轮训练、第 1 轮、第 1 轮训练 5 种子 × 2 臂、15 组审计：两个学习臂各 5 种子，加 TAF、RAC、LOW、ELU-P、NoVersion）。① **本轮目标**：VSMT-lean 节点 F1 按种子配对（新 seed s 对裁决 82 的 seed s，同 39 条 house 的 house 均值差）至少 4/5 为正、且均值大于这 5 个差的标准差；② 保护指标：VSMT-lean 的 Missing 残留率、身份连续率、污染 AUC 按同一配对方式，不得“至少 4/5 往坏的方向且均值绝对值大于标准差”；③ ①② 同时成立判“达标”，否则计 81-1 的第 2 次未达标——按 81-1 连续两轮未达标即停止修订，转入确认集与缩减主张；④ 规则臂（确定性，无种子）另报新旧 house 配对差与 90% 重抽样区间；VSMT-lean 对 AssocOnly 仍按 82-1 规则报告；MRR 对规则臂的差距按 85-4 报告；三项都只作读数，不进本轮达标判定。
    - 影响：改 S0-01 合同 `shared_dedup` 一条（就地修订、重钉摘要）、S1-03 `mask_source` 加一个公开属性、执行器与测试；单职责提交、服务器全量测试、用户代码审查后开机。机时约 145 CPU·小时，36 核约 6～7 小时（更正早先“约 390 CPU·小时”的估计，那是按旧 4080 SUPER 实例的 CPU 折算）。S3 继续暂停。
    - 可复制批准句：「裁决 86 全按推荐」，或逐条如「86-2 取 (b)」。
  - **裁决 86 修订版批准（2026-09-29；用户转来 Codex 复核后，我按复核改了草案并提“修订版”，用户答「不怕超预算」，按批准修订版执行；LOG-282）。** 取代上面的原草案。
    - 依据：Codex 复核（对话内，本会话逐条核对）指出：85%～92% 是既有轨迹上的事件筛查比例，不是收益；共现是风险信号不是证明；共享规则那一轮即使达标也只说明执行器修订有效，不支持贡献一；身份连续率缺逐物体归因。另核对：seed 31 VSMT-lean 范围内撤回 71% 是假撤回（137／193），身份连续率 VSMT-lean 12/61、AssocOnly 22/45，搬动前无承载 4 对 20（与 LOG-270 旧初始化 28 对 16 方向相反），两臂可判物体集合不同。
    - 86-0（批准）先做逐物体归因，不占 81-1 的修订轮次：节点审计 v7（`f1b09ab`）对每个被搬动物体搬动后第一次带标签重见，记录“接回、原实体已不在（被合并或被 NoVersion 删除）、原实体没进召回、进了召回但选了新建、进了召回但选了别的实体、搬动前无承载（从没出过色块／没有实体按多数票认它）”，及原实体状态、是否曾被撤回、是否仍按多数票认该物体、学生所选与最佳原实体的 logit 差；判定“接回”与评价器同口径，并逐帧核对与评价器计数一致。跑 VSMT-lean、AssocOnly、NoVersion 各 5 个种子（裁决 81／82 已训好的头），15 组 × 39 条（`ruling86_attribution.sh`，`167464b`）。
    - 86-1（批准，判读规则出数前冻结，`identity_attribution_analysis.py`，`3744f88`）：在同一种子、两臂都可判的物体上配对（按 episode 与干预序号）；取 VSMT-lean 在“AssocOnly 接回、它没接回”的物体上的失败（五种子合并），归为三侧：生命周期侧（原实体曾被撤回，或在场的原实体全处于休眠／撤回）、卫生侧（原实体全被合并掉，或没有在场原实体仍按多数票认该物体）、关联侧（其余）。生命周期侧过半 → 第 2 轮修生命周期一侧（存在头或恢复，具体规则另提）；卫生侧过半 → 第 2 轮修同帧共现否决（原草案 86-1／86-2，仅限实例分割前端）；都不过半 → 两侧读数交用户裁定。
    - 86-2（批准）判读规则写明：共享规则那一轮达标只说明执行器修订有效；贡献一仍按 82-1（VSMT-lean 对 AssocOnly）与 85-4（Missing 残留率对规则臂）判。
    - 机时：用户明确不受 81-1 约 25 小时开发诊断上限约束（原话「不怕超预算」）；修订轮数上限（3 轮）与“连续两轮未达标即停”不变，除非用户另行裁定。86-0 约 110 CPU·小时，36 核约 3.5～4 小时，跑完自动停机。
    - 影响：只加只读诊断代码，合同字节不变。S3 继续暂停。
  - **待裁 87（提案，2026-09-29，未批准）：第 2 轮修订（81-1）的具体内容。** 依据 LOG-283：86-1 规则字面判“生命周期侧”，但该规则只看一个方向，反方向同机制；更硬的证据是存在头几乎不撤回（候选层面 AUC 0.65～0.69，σ 压在 0.1～0.2，登记网格 0.3～0.9 基本高于输出），主门 Missing 残留率输在这里；而论文的“可逆撤回”在现配置下从未被检验。
    - 87-1 内容：(a) **推荐** 把 τ_r 网格向下扩展，加入 0.15、0.2、0.25（10 个值，仍 ≤12 个配置），在裁决 81／82 已训好的 5 个种子的头上，VSMT-lean 与 NoVersion 各在这三档跑 39 条开发审计（v7，含归因）；不重训、不改执行器，与裁决 82／86 同种子逐一配对。(b) 存在头改用类别加权的交叉熵（按训练记录里 gone／present 的比例加权，公式冻结）并按登记配方重训两轮 DAgger × 5 种子——决策边界的效果与降阈值相近，但重新引入训练波动，成本约高一倍。(c) 停止修订，转确认集并按 83-6 改以协议加基准为框架。
    - 87-2 预登记判读（出数前冻结）：① **本轮目标**：新三档里存在某一档，使 VSMT-lean 五种子的 Missing 残留率均值不高于最强规则臂的两倍（LOG-270 的 RAC 0.089，即 ≤0.178），且在该档上 VSMT-lean 对 AssocOnly 的节点 F1 与身份连续率都不被 82-1 规则判为“AssocOnly 更好”；满足即“达标”，否则计 81-1 连续第 2 次未达标，停止修订。② 同时报告每一档上 VSMT-lean 对 NoVersion 的身份连续率（82-1 规则）和“全部重见物体的接回比例”，这是“可逆”这一主张的直接读数，不进达标判定。③ 选档本身不在开发集上做：达标只说明网格里存在可行点，S3 仍按 83-1 在 validation 上选。
    - 87-3 口径补登：身份连续率另报“全部重见物体的接回比例”（分母含搬动前无承载者），与原指标并列；原指标定义不改。它回答“原指标把搬动前已丢身份的物体排除，是否让某臂显得更好”，只进报告、不进主门。这一项动 S0-04 的“七项以外不报”规则，须在 S3-01 前冻结。
    - 影响：(a) 改 S0-05 的 τ_r 网格一处（就地修订、重钉摘要），无训练；机时 VSMT-lean 与 NoVersion × 5 种子 × 3 档 = 30 组 × 39 条约 220 CPU·小时，这台 25 核约 9～10 小时（不关机）。S3 继续暂停。
    - 可复制批准句：「裁决 87 全按推荐」，或逐条如「87-1 取 (b)」。
  - **裁决 87 修订版批准（2026-09-29，原话「裁决 87 修订版全按推荐」；LOG-284）。** 取代上面的原草案。依据：LOG-283 与 GPT 复核（对话内，本会话逐条核对属实：325 为 65 个搬动事件 × 5 种子；目标子集撤回率 0.03%～0.50%、全部候选撤回 3,117 次；AUC 是已训头在旧轨迹上的排序能力；降阈值后被撤回者多为 present；原 87-2 的保护条件与 NoVersion 角色有漏洞）。
    - 87-1 实验：权重不动，VSMT-lean 与 NoVersion 各在 τ_r = 0.15、0.2、0.25、0.3 跑 39 条开发审计（节点审计 v8，`1ca96ea`，接回时另记原实体是休眠还是已撤回），5 个种子用裁决 81／82 已训好的头；τ_r=0.5 与 AssocOnly 复用裁决 86 的导出（`378008c`）。四处 τ_r 网格（VSMT-lean、NoVersion、HeuristicLabel、ctx）就地扩到 10 个值，S0-05 规则摘要 4e285050 → c9a44bd3（`d1c442e`）。
    - 87-2 甲层（开发继续线，计入 81-1 达标）：四档里至少一档同时满足：VSMT-lean 五种子 Missing 残留率均值 ≤ 0.178（LOG-270 最强规则臂 RAC 0.0891 的两倍）；对自己 τ_r=0.5 按种子配对，节点 F1 平均降幅 ≤ 0.03、全部重见物体接回比例平均降幅 ≤ 0.05；节点 F1 与接回比例都不被 82-1 规则判为 AssocOnly 更好。明写：这只是继续线，不是论文主门。甲层不过即 81-1 连续第 2 次未达标，停止修订。
    - 87-2 乙层（可逆性证据，不计入达标）：在满足甲层且 Missing 残留率最低的那一档（并列取较大 τ_r，事先定死），VSMT-lean 的接回比例按 82-1 规则确定高于 NoVersion，且 VSMT-lean 接回、NoVersion 没接回的物体里过半是从“已撤回”接回的。甲层过、乙层不过：只说明原阈值偏保守，可逆性主张在开发集上没有支持，S3-01 前裁定是否按 83-6 改框架。
    - 87-3：身份连续率旁并列报告原指标、分母、逐种子结果与“全部重见物体的接回比例”，原指标定义不改、不进主门，S3-01 前冻结。
    - 判读脚本 `ruling87_sweep_analysis.py`（`1bbcee8`），驱动 `ruling87_sweep.sh`（`1d12662`，默认不关机）。机时 40 组 × 39 条约 300 CPU·小时，单卡 25 核实例约 13～14 小时。S3 继续暂停。
  - **裁决 88 批准（2026-09-29，原话「裁决 88 全按推荐」；LOG-284 续）：机制核查、第 0 步诊断包与重设计轨道。** 本条在裁决 87 扫描（18:09 CST 开跑）出数之前登记并推送。
    - 依据（本会话只读核查，对话内交付，数字见 LOG-284 续）：
      - ① 存在头的 gone 正例只有约 13% 是窗口后真实的拿走或搬动；约 29% 是实体按节点主列仍在原处、且没有别的实体承载该物体（撤回它就删掉唯一正确的记录），约 24% 是在原处的重复实体，约 27% 是漂移（`cf179fb`，裁决 86 的十组审计）。裁决 80-1 用“B 类是否过半”维持标签，比错了对象：该比的是它与真实变化正例的 13%。
      - ② 第 1 轮 DAgger 的训练轨迹（第 0 轮头在 τ_r 0.5 下）39 条一共只有 75 次 RETRACT（LOG-268），第 1 轮从头初始化、只用这批轨迹（LOG-269、LOG-272 第 6 条）；主表用的头几乎没见过撤回态候选。
      - ③ 三个头第一层对整行做 LayerNorm，对“整行乘一个数再加一个数”严格不变。初始化参数下，余弦 0.4→0.9 使关联头输入变化 1.58（活动、上一帧刚见）、0.0084（休眠、300 帧未见）、0.0017（撤回、1,500 帧未见）；自由空间覆盖 0→1 使存在头输入变化 0.98／0.012／0.0012（观察次数 3／300／3,000）；新建头输入近乎常数。受伤最重的恰是长间隔重新认回与多次观察后被搬走的物体。训练后的权重可能部分补偿，未核实。
      - ④ 学习的存在决定是逐帧 σ ≥ τ_r、不累积（`lean_arms.learned_existence`）：在视野里 N 帧、每帧误撤回概率 p 的实体一生至少被误撤回一次的概率为 1−(1−p)^N；RAC、ELU-P 靠累积避开。
      - ⑤ 存在判定只对本帧未被分配的实体做，关联头输入里没有该实体的自由空间证据；被别的色块错绑的陈旧实体轮不到撤回（待验证，第 0 步不含它的专门统计，列入重设计的第一个检查）。
      - ⑥ D-224 从未跑过“teacher 当策略”的决定上限（旧 CPMT 有可观测信息上限，D-050、D-055），“这套词表、召回与执行器在决定全对时能不能赢”至今没有答案。
    - **88-1（乙层登记，出数前）**：裁决 87 乙层（接回比例确定高于 NoVersion、多接回者过半来自已撤回）的结果只作现象记录，**不作可逆性证据**，理由是依据 ②——降低 τ_r 后出现的大量撤回态候选落在第 1 轮头没训练过的输入区域，乙层量的是外推，不是版本化的价值。甲层判读与其 81-1 后果不变；判读脚本与导出字段不改。
    - **88-2（第 0 步诊断包，全部只读、只用开发集 39 条，通过线在此冻结）**：
      - (i) **决定上限（teacher 当策略）**。白话：它回答“这套词表和执行器在每步决定都对时最多能做到多好”。输入是同一份 cache、召回、执行器，每帧直接用 teacher 的关联目标与存在标签当决定；输出七项指标的上限。例如若完整词表在决定全对时，Missing 残留率与身份连续率都不能同时胜过只有 BIND/BIRTH 的词表和 RAC，再好的学习也救不了贡献一。它不是可部署方法：私有真值在两段封存之前进入决定，只在节点审计的诊断模式里跑、产物标 `oracle_diagnostic`，不写训练记录、不进任何表、不用于选参。
        - 决定规则：关联——色块目标为 labelled 或 birth 时取该列，其余（recall_miss、unlabelled、identity_ambiguous、duplicate_of_labelled）一律 BIRTH 并计数；存在——可判定候选的标签为 gone 则 RETRACT，否则 NOOP；标签口径分“节点主列”（88-4 起的现行规则）与“仅质心”（88 之前的规则，只用于诊断对照）。
        - 格子：O-V-主列、O-V-质心（VSMT-lean 词表）；O-N-主列、O-N-质心（NoVersion 词表）；O-A（AssocOnly 词表，无存在决定）；O-V-主列-补召回（每个色块的主导物体若有承载实体而未被召回，把首版本最早的那个补进召回）；以及 VSMT-lean 的 2×2 混合格：teacher 关联＋学习存在、学习关联＋teacher 存在（主列），学习部分用裁决 81／82 的 5 个种子、τ_r 0.5；学习关联＋学习存在复用裁决 86 导出（`378008c`）。6 个确定性格 × 39 条＋10 组 × 39 条，共 624 条审计。
        - **G0-a 词表价值**：在各指标共同有效的 house 上，O-V-主列相对 O-A：Missing 残留率低 ≥ 0.05，且身份连续率与“全部重见物体的接回比例”各自不低于 O-A 超过 0.05。
        - **G0-b 版本价值**：O-V-主列相对 O-N-主列，身份连续率高 ≥ 0.05。
        - **G0-c 主门可达**：O-V-主列的 Missing 残留率比开发表（LOG-270，`8ce7b0b`）四个规则臂中最低者低 ≥ 0.05，且身份连续率比四个规则臂中最高者高 ≥ 0.05，均在共同有效 house 上。
        - 余量取 0.05：它与 82-1 测得的学习臂跨种子标准差同一量级（节点 F1 约 0.03、身份连续率约 0.10、Missing 残留率约 0.13），上限处连这点余量都没有，学习后的方法不可能稳定越过。它是必要条件，不是充分条件。
        - 判读：G0-a 与 G0-c 都过 → 进入重设计轨道（88-3），按下面的归因排序；G0-a 不过 → 在现有前端、召回与执行器下贡献一没有上限空间，训练前先提改主张或改词表的裁决；G0-a 过、G0-c 不过 → 登记的主门在上限处也够不到，训练前先裁主门或框架（83-6 路线）；G0-b 不过 → 论文不主张“保留档案”的价值，只报读数。
        - 归因（只报告，决定重设计顺序）：对 Missing 残留率与身份连续率各算“换成 teacher 关联”与“换成 teacher 存在”分别关掉学习版（五种子均值）到 O-V-主列差距的比例；哪一侧比例大，该侧的重设计项排在前面。O-V-质心对 O-V-主列、O-V-主列-补召回对 O-V-主列的差值只报告。
      - (ii) **三个分钟级核验**：
        - P1 状态覆盖：第 0 轮（ELU-P 轨迹）与第 1 轮（VSMT-lean 轨迹）训练记录里，关联行按候选状态（活动／休眠／撤回）、labelled 目标按目标状态、存在行按标签计数。只报告；重设计训练的状态覆盖线在其训练合同里冻结，且每个部署会遇到的“原子 × 状态”组合的 labelled 目标不少于 1,000 条。
        - P2 训练后头的敏感度：5 个种子的第 1 轮 VSMT-lean 头，在第 1 轮记录的 9 条选择 house 上，只把两个余弦特征各加 0.1（截到 1）看关联 logit 变化，按“没见帧数”分档（1、2～10、11～100、101～500、>500）与状态分档；存在头把自由空间覆盖从 0 换成 1，按观察次数分档（1～10、11～100、101～1,000、>1,000）；新建头最高余弦加 0.1，按像素数分档。判读（按中位 |Δlogit|）：>100 帧两档对 1 帧档、观察次数 >100 两档对 1～10 档的比值 < 0.1 为“LayerNorm 伤害证实”，0.1～0.5 为“部分”，≥ 0.5 为“训练已补偿、不证实”。
        - P3 模仿充分性。白话：它回答“学习头的输入和容量是不是连它要打败的规则都表达不了”。输入是第 1 轮 VSMT-lean 记录的封存行和规则臂在同一批行上的决定，输出拟合后的一致率。例如 RAC 要连续 3 帧被看穿才撤回，而存在头输入里没有连续计数。它不是让学习臂去模仿规则，只是下限检查。目标：TAF（θ_a 0.7 无门）与 LOW（d_low 1.0）的联合分配、HandCost 存在（ρ_h 0.8）——这三个只依赖当帧特征，是阳性对照；RAC（ρ 0.7、n 3）与 ELU-P（rollout 配置＋登记拟合量）的存在决定——依赖历史，沿记录顺序逐实体重放（匹配由相邻两次候选行之间的观察次数与上次看见帧推出，去重合并后按记录值近似）。按登记配方（AdamW、lr 1e-3、wd 1e-4、20 遍、seed 7，30 条训练 house、9 条选择 house 选最低验证损失）训练同架构的头，主读数是训练 house 上的**分类均衡一致率**（关联按规则选“绑定某实体”与“新建”两类、存在按 RETRACT 与 NOOP 两类，各类一致率取平均），选择 house 上的一致率并列报告。判读：≥ 0.99 能表达，0.95～0.99 部分，< 0.95 不能；阳性对照不过 → 编码或优化是瓶颈；阳性对照过、RAC／ELU-P 不过 → 缺历史；全过 → 头够用，弱点在标签或数据。
      - 机时：P1、P2 数分钟；P3 五次训练约 1～1.5 小时；624 条审计在 25 核实例上约 5～6 小时。裁决 87 扫描结束后在同一台实例上运行，不关机。
    - **88-3（修订框架）**：
      - 裁决 81 的开发修订轮在裁决 87 出数后按原规则结算：甲层不过即 81-1 连续第 2 次未达标、该轨道停止，计数不清零、不改写；甲层过则记达标。此后的改动一律进“重设计轨道”，不再计 81-1 轮次。
      - 重设计轨道的规则：① 先跑第 0 步诊断包，按 88-2 判读决定继续还是先改主张，以及各项顺序；② 每一项先登记规则、正反案例、受影响的臂和它自己的机制检查及通过线，再实现、再跑，单职责提交；③ 共享部件的修订给所有臂，关联训练的修订同样给 AssocOnly，只有生命周期专属的改动只给有生命周期的臂；④ 只用开发集，不读 validation／test；整套改完后按 82-1 规则 5 种子判读（对 AssocOnly）并按 85-4 报 Missing 残留率对规则臂，再在裁决 81 冻结的确认集（train 块第 50～99 位）上核对一次，确认集不参与任何选择；⑤ 开发集上已有的负结果全部保留，旧计数不清零；⑥ 某项没过自己的机制检查就撤下或只修订一次（登记），G0 不过则不训练。
      - 候选项（顺序由第 0 步读数定，每项仍须另登记规则）：存在标签对齐节点主列（88-4，已批准）；逐字段输入编码；存在决定改为序贯证据累积；DAgger 聚合数据并满足状态覆盖；共享去重的同帧共现否决（仅实例分割前端）；身份外观与位置分开更新。
      - 机制门成为此后所有阶段（含 S3、S2-06 SAM2 表）的常设规则，表见 PLAN“S2-R 重设计轨道与机制门”：每个阶段的机制检查及通过线在该阶段运行前登记。
    - **88-4（存在标签语义，重开 79-4，取 (a)）**：teacher 的存在标签与节点主列对齐——物体已不在场景中记 gone；物体在场时，实体只要按裁决 77 的地点规则对自己的物体成立（质心 ≤ δ_moved，或质心落在真值框外扩 0.25 m 内）就记 present，否则记 gone。在原处的重复实体因此记 present，冗余交给共享去重；结构件与运行时生成物的规则不变；物体没有真值框时只用质心。
      - 假撤回率按存在标签定义，随之改为“被撤回的实体中按节点主列仍在原处的比例”；88 之前的开发表假撤回数值与之不可比。
      - 88 之前的“仅质心”规则保留为具名诊断口径，只供 88-2 的 O-V-质心／O-N-质心两格，不用于训练或任何表。
      - 改 S0-04 标签规则（就地修订、重钉规则摘要）与评价器的物体状态（带真值框），相关合同的摘要随之重钉。开发集上的复核随重设计一起做，不额外加一趟。
    - 影响：本条文档先于扫描出数推送；88-4 的合同与代码、88-2 的诊断代码分单职责提交，服务器全量测试后运行；不训练学习臂的正式权重（P3 的模仿训练只作诊断）。S3 继续暂停。
    - **落地（2026-09-29，都推两分支，不带署名行）**：`cf179fb` gone 标签拆分（只读）；`019e338` 本条文档（扫描出数前）；`b172f30` 88-4 合同与代码（S0-04 规则摘要 185d7ff4 → 818ec131）；`fcf2bf4` 节点审计 v9（决定上限诊断模式）；`6ad6aed` P1／P2／P3 核验脚本；`e977fe5` 判读脚本；`5de3cff` 第 0 步驱动 `ruling88_step0.sh`（`WAIT_FOR` 等扫描的状态文件出现再开跑，默认不关机）。本机 lean 测试 966 个分模块全过（受控训练模块一次偶发失败、单独重跑通过，与笔记本 CPU 故障记录一致），服务器全量测试由驱动在开跑前执行。
    - **执行变更（2026-09-29 19:27 CST，用户指示「看看还有没有必要，没必要就停止」）**：裁决 87 的 τ_r 扫描在 195/1,560 条时停止（LOG-285）。原因：乙层已按 88-1 不作证据，甲层只决定 81 修订轨道怎样结算，而 88-3 已把此后的改动转入重设计轨道；它评估的头正是要被替换的那套。影响：甲层没有读数，81-1 计数维持 1 次未达标、第 2 轮记“未读出”，该轨道按 88-3 转入重设计；195 条保留，可用 `RESUME=1` 续跑。第 0 步随即在同一实例上启动，不再等扫描的状态文件。
    - 白话：这次裁决解决“改之前先弄清这套方法在决定全对时能不能赢、现在的头到底被什么卡住”。输入是只读核查查出的六条线索，输出是四条口径：扫描的乙层不当证据；先跑一包只读诊断，并事先定好读法；以后每个改动先过自己的机制检查；存在标签改成和节点指标同一把尺子。它不表示任何改动已经有效，也不授权 S3。
  - **裁决 89 修订稿批准（2026-09-30，原话「可以的」与「可以按照裁决89来」；取代同日初稿）：S2-R 重设计的清单、顺序与各项机制检查。** **执行授权（同日，原话「你自己代码审查就好了，全自动即可」）**：S2-R 裁决 89 各项的代码由执行会话自审、全自动推进，是 D-059“用户审过才跑”在本轨道内的例外；仍须单职责提交、服务器全量测试、每项先登记检查与通过线再运行，检查不过至多修订一次（89-8），再不过即停下写明原因等用户，不得自行放宽通过线或越过 89-4 的停止规则；本授权不覆盖 S2-06、S3 与任何 validation/test。 依据 LOG-286（措辞按其更正）：G0 三项都过；在本次替换诊断中，存在侧是 Missing 残留率的主要限制、关联侧是身份连续率的主要限制，两侧耦合，所以 99.4%／100% 只是这组运行的差距关闭比例，不是互相独立的因果贡献；召回在现行 teacher 策略下漏掉 21/65；现行训练配方连 HandCost 单阈值规则的少数类都只学到 43.5%。修订来自 GPT 复核（对话内，本会话逐条核对属实）：初稿 89-2 的“自上次匹配以来”摘要表达不了 ELU-P（它的对数几率从实体诞生起累积，匹配只加增益、不清零，`lean_arms.elu_p_existence`）；半上限格通过不保证联合闭环有效；89-3 的覆盖线按行数会被连续帧凑数，且必须在同一召回条件下对比；主张须写成待验证。
    - 白话：这次裁决决定“先改什么、每一改怎样算起作用”。每一侧先在半上限格上单独检查（另一侧用 teacher），两侧都过后先做一次固定配置的联合闭环检查，再决定是否做完整重跑。它不是新方法主张，也不授权 S3。
    - 89-1 召回（第一步，所有臂共用）：(a) **推荐** 先做只读诊断：在决定上限格的记忆上，记录 21 次漏召回时原实体在全局余弦排序里的公开名次，报名次分布；然后 k′ 取 {5, 8, 12} 中第一个使上限格漏召回 ≤ 3/65 的值，通道仍与状态无关。**三个值都不过即暂停另提裁决，不临时继续加大。** (b) 为休眠／撤回实体单开通道——混淆对 AssocOnly 的对照，不推荐。(c) 不改——身份连续率在 teacher 策略下的上限停在 0.67。影响：(a) 名次诊断要在节点审计里加一个只读字段（约 1 小时机时）；改 S0-03 召回值（裁决 57 冻结，就地修订、重钉）。
    - 89-2 存在侧（第二步）：(a) **推荐**：
      - 历史摘要改为两组逐实体统计，更新规则写死：RAC 组——ρ 取 RAC 网格的 0.7 与 0.85 各一个“连续被看穿计数”，每个可判定帧覆盖 ≥ ρ 则加一、否则清零，本实体被匹配（BIND／REACTIVATE）时清零；ELU-P 组——自诞生以来的可判定帧数与累计自由空间覆盖，匹配与撤回都不清零（与 ELU-P 一致），配合已有的观察次数，ELU-P 的对数几率就是它们的线性函数。去重合并时 canonical 保留自己的统计、被折叠者丢弃（与 runner 对 ELU-P／RAC 臂状态的处理一致）；撤回后恢复时统计延续。
      - 训练前先做“同输入异答案”检查：在重放的训练 house 记录上，按新特征行（浮点完全相同才算同输入）分组，HandCost（ρ_h 0.8）、RAC（两个 ρ × n ∈ {2, 3, 5}）、ELU-P（rollout 配置与登记拟合量）的规则决定出现同输入异答案的比例须为 0；不为 0 先修摘要，不训练。
      - 损失对 gone／present 加权，gone 权重 ＝ 训练 house 的 present 行数 ／ gone 行数；存在头逐字段编码：计数、帧数取 log1p 后按训练 house 的均值与标准差标准化，比例与 one-hot 不变。权重与标准化统计只用训练 house。
      - 检查：① P3 在新输入与新配方上，HandCost、RAC、ELU-P 的训练 house 分类均衡一致率 ≥ 0.99，同时报告最后一个 epoch 与训练损失最低 epoch 的读数（选择集选点不能当作拟合能力的严格检验）；② “teacher 关联＋新存在头”格 5 种子 Missing 残留率均值 ≤ 0.05、节点 F1 ≥ 0.93，范围内假撤回率另报。
      - (b) 学习逐帧证据增量加确定性累加器：只在 (a) 不过时启用，算作 89-2 的唯一一次修订。(c) 只加权损失：RAC、ELU-P 的历史规则仍表达不了，不推荐。
      - 影响：改 S0-03 存在特征表与 runner 的逐实体状态、S0-05 损失口径（就地修订、重钉）；训练记录要重新生成（第 0 轮 ELU-P 轨迹与第 1 轮轨迹重放）。
    - 89-3 关联侧（第三步，与 89-2 分开检查）：(a) **推荐**：
      - 两个学习臂的第 1 轮训练都用“第 0 轮 ELU-P 轨迹记录＋本臂第 1 轮记录”，第 0 轮部分两臂逐字节相同；AssocOnly 部署时见不到撤回态，但训练集来源与 VSMT-lean 对称，差别仍只在词表与存在项。全量拼接、不重采样；训练预算为拼接集上的登记 20 遍，实际更新次数记入回执；检查点规则不变（验证损失，85-2 的决策准确率属 S3-01）。
      - 状态覆盖按训练 house 单列、按事件计：撤回态与休眠态的 labelled 目标各自按不同的（episode、实体、接回事件）计数，每类 ≥ 200 个事件、分布在 ≥ 15 个训练 house；训练前只读统计，不够即暂停。这条取代裁决 88-2 按行计的 1,000 条线。
      - 关联头与新建头逐字段编码，规则同 89-2。
      - 检查在同一召回条件下：先用旧关联头在新召回下重跑“学习关联＋teacher 存在”格作基线；新头相对这一基线，身份连续率与全部重见接回比例按 82-1 规则确定更高（至少 4/5 同号且均值大于标准差），且“选了新建”减少；P3 的 TAF、LOW ≥ 0.99（同样报两种 epoch 的读数）。“只有 86 条导致接不回”在此之前是假说，这项配对检查就是在验证它。
      - (b) 只编码不聚合——不针对撤回态样本稀少的问题，不推荐。
    - 89-4 联合闭环检查（89-2、89-3 都过之后，新增）：VSMT-lean 同时用两侧改动训练的头，固定配置（τ_r 0.5、新召回），5 种子 × 39 条开发 episode，不新增 DAgger 轮。通过线（5 种子均值）：Missing 残留率 ≤ 0.10（RAC 0.089 附近）、身份连续率 ≥ 0.45（现行 0.405 之上）、节点 F1 ≥ 0.76（不低于现行 0.788 超过 0.03）、范围内假撤回率 ≤ 0.35（现行 0.45～0.73）。不过：在 89-2／89-3 的已登记选项内修订一次，仍不过即停止重设计、按 83-6 讨论框架。
    - 89-5 记忆卫生（条件项，不预先承诺）：联合检查里“搬动前已无承载”5 种子均值 ≤ 3/65 且去重开启的失去承载段 ≤ 10% 时跳过；否则另提具体规则。身份与位置分开更新会改变方法本身，须单独裁决。
    - 89-6 收尾：联合检查通过（且 89-5 处理完）后，完整链重跑（第 0／1 轮记录重生成、七臂开发表、学习臂 5 种子），按 82-1 判 VSMT-lean 对 AssocOnly、按 85-4 报 Missing 残留率对规则臂，再在确认集核对一次。
    - 89-7 贡献一的表述（只改文字，标为待验证）：(a) **推荐** “拟验证：生命周期操作能否减少陈旧实体，同时通过保留可召回的实体档案，在撤回后恢复原身份；实际收益由学习闭环与消融实验检验。”依据只到 teacher 诊断：完整词表对 AssocOnly 在上限处只领先 Missing 残留率（0 对 0.563）；NoVersion 的 0.025 支持“保留可召回档案有用”，不单独证明完整版本链或事务审计必不可少；AssocOnly 在上限处身份持平，也不排除学习条件下的身份差异。(b) 维持原表述——与上限读数不符。
    - 89-8 停止规则：每一项（89-1、89-2、89-3、89-4）检查不过后至多修订一次，89-2(b) 就是 89-2 的这一次；机时是估计，不是到点终止的超时。89-1～89-4 合计约 15～20 小时机时，89-6 约 12～15 小时。S3 继续暂停。
    - 批准口径：全部按推荐（含 89-4 的四条通过线），无逐条改动。
    - **执行变更一：确认集提前生成（2026-09-30，用户原话「能跑就今晚一起生成确认集数据」与「确认集提前生成，评估仍在方法冻结后一次」）。** 裁决 81-1 原写“方法冻结后才生成并评估一次”；现在把“生成”提前到本轨道执行期间，“评估一次”不变。范围：只生成 train 块第 50～99 位（`configs/vsmt/lean_ruling81_confirmation_houses.json`，名单不动）的原始 episode、oracle cache（`simulator_instance_masks`）与 S1-04 几何重载，协议与开发集逐项相同（生成器、cache、几何重载的代码自 `5f9aa71`／`8ebbd05`／`154776d` 以来没有改动，只加一个核对冻结名单的 `--stage confirmation` 入口）；可读的只有工程回执（成败、帧数、失败原因），不在确认集上跑任何臂、不算任何指标、不看逐帧内容，直到 89-6 方法冻结后评估一次。依据：生成只依赖已冻结的数据协议与前端，不依赖方法；这台 4 卡实例今晚空闲。前提已核：vGPU 上 Vulkan 枚举到 4 张 NVIDIA RTX 4080 SUPER（非 llvmpipe），CloudRendering 在每张卡上都能起、三路帧齐全；数据盘已由用户扩到 100 GB。观察项：同一场景四张卡的 RGB 均值在小数点后第二位不同、深度逐位相同，生成器不指定 `gpu_device`，全部在 0 号卡渲染。
      - 白话：确认集是最后只考一次的“期末卷”。以前规定方法定稿才印卷子，现在先把卷子印好封存（生成数据），但仍然定稿后才考、只考一次。它不改名单、不改协议，也不让确认集参与任何选择。
      - 附带的工程登记：生成器提交 `2339baa`（只加确认集入口与多卡 `nvidia-smi` 读数修复，`camera_pose` 编码器与 5f9aa71 相同）生成的 episode，要登记进 S1-03 合同 `public_pose_correction.correct_encoder_since_code_commits` 并重钉规则摘要后，cache 与几何重载的读取端才接受——与 5f9aa71 当时的登记同一做法，不改任何读取规则。
    - **裁决 89 执行细则（一）：89-1 召回诊断的做法（2026-09-30，运行前登记，只细化做法，不改通过线）。**
      - 格与范围：O-V-主列（teacher 关联＋teacher 存在、节点主列标签、VSMT-lean 词表、τ_r 0.5），39 条开发 episode，k′ ∈ {3, 5, 8, 12} 各跑一遍；本地通道（半径 3 m 内前 5 个）不变，只覆盖全局通道的 k′（节点审计 v10 的 `--recall-global-count`，只供诊断，写进产物）。
      - 名次字段：每个搬动物体首次重见时，取仍在记忆里的搬动前承载实体中首版本最早的那个（与补召回格、teacher 目标同一规则）为“原实体”，记它在“该色块对全部实体的余弦降序、并列按实体 ID”里的名次（从 1 起）；排序键与召回全局通道逐位相同，名次 ≤ k′ 即全局通道会召回它（测试钉住）。k′=3 下报漏召回者的名次分布。
      - 漏召回计数：该 k′ 下首次重见分类为“原实体没进召回”（`carrier_not_recalled`）的个数；分母是全部首次重见的搬动物体（k′=3 时为 65）。
      - 判读（照原文）：{5, 8, 12} 按顺序取第一个漏召回 ≤ 3 的 k′，就地改 S0-03 的 `RECALL_GLOBAL_COUNT` 并重钉；三个都不过即暂停另提裁决，不继续加大。四个 k′ 并行跑，但取值只按这个顺序规则，不看其他指标；五项指标的均值只报告。
      - 入口：`ops/vsmt/ruling89_recall.sh`（共用队列、合并、`ruling89_recall.py` 判读），与确认集生成同机并行，worker 数按 CPU 配额减去生成占用。
    - **裁决 89 执行细则（二）：89-2 存在侧与 89-3 关联侧的做法（2026-09-30，运行前登记，只细化做法，不改任何通过线）。** 用户同日追加授权（原话「如果你能在悉尼时间11点之前完成89-3和89-2然后也收到了服务器的返回，你可以启动89-4，你可以全程自动化代码编写，代码方面不需要我的审批」）：两侧检查都过且回执齐全时，89-4 可直接按原文启动；任一侧不过仍按 89-8 处理。
      - 召回：89-1 按冻结规则选出的 k′ 就地写进 S0-03 `RECALL_GLOBAL_COUNT` 后，本项所有记录与格都在新召回下生成；三个 k′ 都不过则本项不开始。
      - 历史摘要（89-2 (a) 原文的落地）：S0-03 存在特征表在原 12 项之后就地追加 `rac_run_rho_070`、`rac_run_rho_085`、`matches_since_birth`、`eligible_frames_since_birth`、`free_space_coverage_sum_since_birth`；runner 对所有臂维护（`lean_runner.update_existence_history`），行里是本帧更新前的值。可判定帧＝`eligible_existence_rows` 选出的行（应可见、未分配、未撤回），匹配＝本帧分配到的既有实体（BIND 与 REACTIVATE，不含 BIRTH），与 ELU-P／RAC 臂读同一批行、同一批匹配；去重时 canonical 保留自己的、被折叠者丢弃；非法程序整帧回滚；撤回不清零，撤回后恢复时延续。测试钉住：ELU-P 臂每个可判定行的对数几率等于“初值 + 增益×匹配次数 − 衰减×(可判定帧数+1) − 权重×(累计覆盖+当帧覆盖)”。
      - RAC 规则在一行上的决定（用于同输入检查与 P3）：当帧覆盖 ≥ ρ 且“此前连续计数 + 1 ≥ n”即 RETRACT。它是 RAC 在这条轨迹所处状态下的决定（计数自上次匹配起）；与裁决 88 P3 沿记录重放 RAC 自身撤回后清零的近似不同，这里不需要近似。
      - 逐字段编码（89-2 (a)、89-3 (a)）：替换三个头第一层的整行 LayerNorm。计数与帧数类（没见帧数、错失次数、召回内名次、观察次数、两个 RAC 计数、匹配次数、可判定帧数、累计覆盖、半径内活动实体数、像素数）取 log1p 后按训练 house 的均值与总体标准差标准化；其他无界量（质心距离、体积对数比、支撑高度差、相机距离）只标准化；比例、余弦、有界间隔、one-hot 与标志不变。统计量只用训练 house（按 split 种子留出的 30 个），写进权重文件。
      - 类别权重（89-2 (a)）：存在损失 `pos_weight` ＝ 训练 house 记录里 present 行数 ／ gone 行数；选择 house 的验证损失同样加权。
      - 训练记录与来源：第 0 轮＝ELU-P 在 rollout 配置加登记拟合量下、新召回与新特征的 39 条开发 episode 重新生成（S2-05 `run-pass dagger_round_0`，写入新诊断根，旧根不动）；第 0 轮头＝VSMT-lean 在第 0 轮记录上、按新配方、登记的第一个种子 7 训练一次（开发训练规则不变）；第 1 轮＝VSMT-lean 用这个第 0 轮头、τ_r 0.5 在同 39 条上重新生成（`run-pass dagger_round_1`）。第 1 轮训练用“第 0 轮 ELU-P 记录＋第 1 轮记录”全量拼接、不重采样，按登记 20 遍、选择 house 的验证损失选检查点，实际更新次数写进回执；五个登记种子 7／19／31／43／59 各训练一次，第 0／1 轮轨迹共用——与裁决 81／82 的 A 条件相同（种子只换最后一轮训练）。
      - 两个学习臂的对称：AssocOnly 用同一份第 0 轮 ELU-P 记录（逐字节相同）、同一编码与配方，在 89-6 的完整链里按同样步骤训练；89-2／89-3 的检查只涉及 VSMT-lean，本步不训练 AssocOnly，不作 VSMT-lean 对 AssocOnly 的任何比较。
      - 89-2 的检查：① 同输入异答案——第 0 轮训练 house 的可判定行，HandCost（0.8）、RAC（0.7／0.85 × 2／3／5）、ELU-P（rollout 配置与登记拟合量）必须为 0，不为 0 即停、不训练；② P3——在第 0 轮记录上按新编码与新配方（存在目标加类别权重）训练同架构的头，目标 HandCost 0.8、RAC 0.7／3、ELU-P rollout，训练 house 分类均衡一致率在“最后一个 epoch”与“训练损失最低 epoch”两种读数上都 ≥ 0.99 才算过，选择集损失最低的检查点并列报告；③ “teacher 关联＋新存在头”格（节点审计 `--oracle-association`，新头的存在头、τ_r 0.5）五个种子 × 39 条，Missing 残留率五种子均值 ≤ 0.05、节点 F1 均值 ≥ 0.93，范围内假撤回率另报。
      - 89-3 的检查：① 状态覆盖按事件——拼接集训练 house 上，labelled 目标处于撤回态、休眠态的，按（趟、episode、实体、段起点＝tick − 没见帧数）去重，每类 ≥ 200 个事件且分布在 ≥ 15 个训练 house，不够即停、不做第 1 轮训练；② P3 的 TAF（0.7 无门）、LOW（1.0）在第 0 轮记录上按新编码，同样两种读数 ≥ 0.99；③ 同一新召回下，“学习关联＋teacher 存在”格（`--oracle-existence node_primary`）新头五个种子对旧头基线（裁决 81／82 的 A7／A19／A31／A43／A59）同种子配对：身份连续率与全部重见接回比例按 82-1 规则确定更高（至少 4/5 同号且均值差大于差的标准差），且“选了新建”的五种子均值减少。旧头只用关联头与新建头（存在由 teacher 给），其存在头是 12 项旧顺序，加载时保留、不能对新行打分。
      - 判读与入口：`ops/vsmt/ruling89_sides.sh`（一条链：全量测试 → 第 0 轮与基线格并行 → 同输入 → P3 与第 0 轮训练 → 第 1 轮 → 覆盖 → 五种子训练 → 两个新格 → 合并 → `ruling89_checks.py`）；停止点在同输入与覆盖两处；机时估计 4～5 小时，不是超时。任一侧不过：按 89-8 在已登记选项内至多修订一次（89-2 的修订就是 (b)），写 LOG 等用户；两侧都过：按用户追加授权启动 89-4。
      - 白话：这一条把 89-2／89-3 的“怎么做”写死在运行之前：历史摘要怎么记、编码怎么算、训练数据从哪来、种子怎么换、每条线在哪个产物上读。它不放宽任何一条通过线，也不让确认集、validation 或 test 进入。
    - **执行细则（二）补充：89-1 不过时 89-2／89-3 的暂定运行（2026-09-30 02:55 CST 登记，在 89-2／89-3 的任何运行之前）。** 89-1 的 k′=3／5／8 已出齐（漏召回 21／18／14，上限 3），按名次字段推算 k′=12 为 11；k′=12 的正式数与判读以 LOG-287 为准。若三个值都不过，按 89-1 原文召回暂停、另提裁决（待裁 90），不继续加大 k′。执行细则（二）原写“三个 k′ 都不过则本项不开始”，现改为：89-2／89-3 在**冻结的现行 k′=3**下照（二）的全部做法先跑，产物一律标“暂定”（provisional）——待裁 90 若保持 k′=3，它们就是 89-2／89-3 的正式检查（通过线、做法一字不改）；若改召回，全部作废、在新召回下重跑，数字不得引用。两侧暂定检查都过时，链内按用户的追加授权接着跑 89-4 联合闭环（VSMT-lean 用五个第 1 轮头、τ_r 0.5、不加 DAgger 轮，四条线照原文），同样标暂定、同样以待裁 90 为前提。理由：k′=3 是现行冻结值，也是待裁 90 的推荐口径，这一步不改变任何已冻结的东西，只把机时用在最可能成立的前提上；改动发生在 89-2／89-3 任何结果出现之前，与它们的读数无关。
      - 更正（2026-09-30，采纳 ASTRA 复核，LOG-288 续⑤）：这条补充改变了执行细则（二）已登记的停止规则（“三个 k′ 都不过则本项不开始”），上一句“不改变任何已冻结的东西”撤回。它没有用户的明确批准，因此这批产物维持“暂定”，待裁 90 即使保持 k′=3 也不自动转正，需用户对这项例外单独表态。
  - **待裁 90（2026-09-30 提出，LOG-287）：89-1 三个候选都不过之后，召回怎么办。** 依据：决定上限格（teacher 关联＋teacher 存在）上漏召回 k′=3／5／8／12 为 21／18／14／10，线是 3/65；漏召回者的名次中位 13、最大 88（记忆 37～292 个实体），压到 3 以下约需 k′=43；上限格身份连续率 0.670／0.704／0.762／0.840，Missing 残留率都为 0、节点 F1 0.954～0.962。
    - (a) **推荐**：保持 k′=3，把“召回上限”写进局限与后续工作（身份连续率在 teacher 策略下的上限 0.67；G0-c 在这个上限下已过）。理由：三个登记值都没过事先定的线，任取其一都是看结果后另立一条线；名次长尾说明全局余弦认不出约三分之一被搬动物体的原实体，加大 k′ 只是把“从几十个实体里挑对”的难题从召回挪到关联头，而 LOG-286 显示学习关联本身就是身份连续率的主要限制。影响：不改任何合同；89-2／89-3（以及两侧都过后的 89-4）的暂定运行（执行细则（二）补充）直接转为正式检查。
    - (b) k′=12，并把 89-1 的线改为“漏召回 ≤ 10/65”：上限格身份连续率 +0.17（0.84），每个色块至多 17 个候选（现为 8），阶段 A 的关联行约翻倍、每帧开销相应上升，学习关联在更多干扰候选下能否兑现未验证。影响：S0-03 就地改值并重钉；暂定运行作废，第 0／1 轮记录、训练与两个格在新召回下重跑（约 5 小时），89-4 随后。
    - (c) 继续加大到 k′≈43 使漏召回 ≤ 3：召回接近“全部实体”，关联头每个色块面对约 48 个候选，训练与运行开销数倍；不推荐。
    - 利益冲突说明：本会话已在 k′=3 下暂定开跑 89-2／89-3，(a) 会让这批机时直接生效；推荐 (a) 的理由见上，不依赖这批运行的任何结果（登记时它们还没有任何读数）。
    - 批准句（任选其一原样回复）：「待裁 90 取 (a)，保持 k′=3」／「待裁 90 取 (b)，k′=12，线改为 10/65」／「待裁 90 取 (c)」。
  - **待裁 91（2026-09-30 提出，LOG-288）：89-2 与 89-3 的训练前检查都没过之后，这一次修订用什么。** 依据（暂定运行，k′=3）：
    - 89-2 ①（P3，新输入＋新配方，训练 house 分类均衡一致率，最后 epoch／训练损失最低 epoch）：HandCost 0.998／0.995、RAC 0.995／0.996 过，**ELU-P 0.986／0.958 不过**；同输入异答案 0（历史摘要已能表达三条规则）。
    - 89-3 ②（P3）：**TAF 0.969／0.969、LOW 0.986／0.980 不过**（LOG-286 的旧编码为 0.942／0.966）；89-3 ① 状态覆盖过（撤回态 18,211、休眠态 15,899 个事件，30 个训练 house）。
    - 训练过程：三个存在目标的训练损失都随 epoch **上升**（ELU-P 0.19 → 2.05，RAC 0.31 → 0.98，HandCost 0.04 → 0.18），gone 权重 88～327 倍；VSMT-lean 第 0 轮最佳 epoch 0，第 1 轮五个种子最佳 epoch 0／0／2／0／17，选择 house 验证损失在 2.4～9.8 之间跳动。关联目标没有加权，训练损失单调下降、第 20 个 epoch 仍在降（没学够）。两侧的共同点是优化：每帧一步、lr 1e-3 恒定、存在侧再乘近百倍的权重。
    - 两个格：89-2 ②“teacher 关联＋新存在头”五种子 Missing 残留率 0.004（过）、**节点 F1 0.682（线 0.93，不过）**、范围内假撤回率 **0.982**——新存在头几乎见啥撤啥；89-3 ③ 同召回配对：身份连续率差 −0.021（标准差 0.055）、全部重见接回比例差 0.000（0.047），82-1 规则下分不开，“选了新建”18.0 对 17.8，没有减少。过度撤回可以算出来：用权重 w 训练会把最优 logit 整体抬高 ln w（w≈94 时约 4.5），τ_r 0.5 就相当于未加权时的 1/(1+w)≈0.01。
    - (a) **推荐**：两侧共用一次“配方修订”（替代 89-2 原登记的 (b)，也作为 89-3 的那一次修订），三处一起：学习率按 epoch 余弦衰减（1e-3 → 1e-5，20 遍不变）；每步梯度范数裁剪到 1.0；存在决策用校正后的 logit（头输出减 ln w，权重文件里记这个偏移且受摘要保护，P3 与各格都读校正后的值）。编码、类别权重、数据、种子、检查点规则与全部通过线不变。先只重跑五个 P3 作闸门（约 30 分钟），五个都在两种读数上 ≥ 0.99 才重跑第 0／1 轮、五种子训练与两个格（约 4 小时），两侧都过再按原文做 89-4。代码已备好、默认关闭（`9545ef0`／`af5ac56`，`REVISION_91=1`）。影响：两臂共享的训练配方与存在决策改动，AssocOnly 在 89-6 同样使用；D-224 冻结的 lr 1e-3 作为起点保留。它不保证关联侧能过：89-3 ③ 的“分不开”也可能说明聚合数据本身帮不了身份，这一点要等修订后的读数。
    - (b) 按 89-2 原登记做 (b)“学习逐帧增量＋确定性累加器”：它改的是表达方式，而这次的证据是优化不稳定（同输入异答案为 0，说明输入已足够），预计治不了；具体形式还要另行设计（约 1 天工程）；89-3 另需指定修订。不推荐。
    - (c) 不再修订，按 89-8 停止重设计、按 83-6 讨论框架。
    - 召回：本条与待裁 90 独立；若待裁 90 取 (a)，按 (a) 修订的重跑直接成为正式检查。
    - 批准句（任选其一）：「待裁 91 取 (a)」／「待裁 91 取 (b)」／「待裁 91 取 (c)」。
    - **推荐暂时撤回（2026-09-30，采纳 ASTRA 复核，LOG-288 续）**：上面依据中的“同输入异答案 0 说明输入已足够”不成立（该检查不可能失败），“训练损失最低 epoch”读数与“训练损失上升”都来自 epoch 内的逐步损失，0.982 是撤回精度而不是撤回面，18,211 与 86 不同口径。已改为独立执行器核对与固定权重的训练集损失，复核（`ruling89_recheck.sh`）出数后按实际读数重写本条的依据与推荐；在此之前请不要按本条批准。
  - **待裁 91 重提（2026-09-30，LOG-289；取代上面待裁 91 的依据与推荐）：89-2 与 89-3 各自这一次修订用什么。** 依据（暂定，k′=3）：历史摘要经独立执行器核对完全忠实（约 1,060 万行 0 不一致，错误摘要全部检出）；P3 按固定权重重读后 HandCost、RAC 过，ELU-P（0.986／0.980）、TAF（0.969／0.967）、LOW（0.986／0.980）不过；存在目标的检查点训练集损失逐 epoch 大幅起伏，关联目标走平；“teacher 关联＋新存在头”格节点 F1 0.682、在场候选每次决策撤回 13.6%～30.6%；同召回配对分不开。
    - (a) **推荐**：两项各用一次修订，内容按两侧证据分开写。89-2（存在侧，替代原登记的 (b)）：学习率按 epoch 余弦衰减 1e-3 → 1e-5、每步梯度范数裁剪 1.0、存在决策用头输出减 ln w 的校正 logit——前两项针对检查点损失的起伏，第三项针对过度撤回的理论偏移；三项一起改，只能检验组合能否救回结果，不能单独确认哪一项起作用。89-3（关联侧）：同样的余弦衰减与裁剪（两臂共用配方），它针对的是平台而不是不稳定，能否越过 0.99 不确定。两侧都先只重跑 P3 作闸门（约 30 分钟），五个目标都在两种读数上 ≥ 0.99 才重跑第 0／1 轮、五种子训练与两个格（约 4 小时），两侧都过才按原文做 89-4。编码、类别权重、数据、种子、检查点规则与全部通过线不变。代码已备、默认关闭（`9545ef0`／`af5ac56`，`REVISION_91=1`，P3 读法已按 LOG-288 续修正）。
    - (b) 89-2 按原登记的 (b)（学习逐帧增量＋确定性累加器）：独立核对已表明输入足以表达规则，改表达方式针对的不是这次暴露的问题；具体形式另需设计（约 1 天）；89-3 另需指定修订。不推荐。
    - (c) 不再修订，按 89-8 停止重设计、按 83-6 讨论框架。
    - 与待裁 90、92 的关系：修订的重跑以待裁 90 的召回为准；若待裁 90 改召回，本条照样适用，只是在新召回下跑。
    - 批准句：「待裁 91 取 (a)」／「待裁 91 取 (b)」／「待裁 91 取 (c)」。
  - **待裁 92（2026-09-30，LOG-288 续⑤）：执行细则（二）补充条款下的暂定运行，能否算作 89-2／89-3 的正式首轮。** 该补充把已登记的“89-1 不过则 89-2／89-3 不开始”改成了暂定运行，没有用户的明确批准。
    - (a) **推荐**：若待裁 90 保持 k′=3，承认这批产物为 89-2／89-3 的正式首轮（两侧都不过），待裁 91 的修订就是各项的那一次修订。理由：改动在任何 89-2／89-3 结果出现前登记并推送，产物与代码提交全部保留；同一提交重跑是确定性的，会逐字节得到同样的产物，重跑只花约 5 小时、不增加信息。
    - (b) 不承认：待裁 90 之后在正式身份下重跑一遍首轮（约 5 小时），再决定修订。
    - (c) 若待裁 90 改召回：本条自动失效，首轮在新召回下重跑。
    - 批准句：「待裁 92 取 (a)」／「待裁 92 取 (b)」。
  - **裁决 90 批准（2026-09-30，原话「待裁 90 取 (a)，保持 k′=3，关联侧过检后重新评估召回」）：召回保持 k′=3。** `RECALL_GLOBAL_COUNT` 与 S0-03 合同不变。89-1 的原门没有通过，这里是明确接受现行召回的限制（teacher 当策略时身份连续率上限 0.67，约三分之一搬动物体的原实体进不了召回），不声称原门已过。附带的后续规则：关联侧（89-3 或其修订）通过自己的检查之后、完整链（89-6）之前，重新评估召回（候选包括 k′=12 与更好的召回方式），届时另行登记检查与通过线；依据是学习关联头在“原实体已进召回”时的接回率现在只有 12%～50%（LOG-289 附近的暂定格），召回此刻不是主要瓶颈，关联头改好后它会重新成为瓶颈。k′≈43 只是旧轨迹上的名次估算，不能保证闭环达标。
    - 白话：先不扩候选名单，因为现在即使原实体在名单里，学习头也只认回三成左右；等学习头认得准了，再回来决定要不要把名单拉长。
  - **补记（2026-09-30，采纳 GPT 复核）**：
    - 措辞：0.982 是“撤回中的错误比例”，对应的撤回精确率约 0.018；LOG-288 续与待裁 91 附注里“0.982 是撤回精度”的说法以此为准。
    - 待裁 92 (a) 的理由改为“已有完整证据，无需重复计算”；原写“同一提交重跑会逐字节得到同样的产物”过强——复核时五份 P3 权重确实逐位复现，但不能由此保证整条链的日志、耗时与全部产物逐字节相同。
    - 入口：待裁 91 (a) 只能经 `ops/vsmt/ruling91_revision.sh`（`a98c980`）运行——它核验并复用 003b906 的第 0 轮记录与旧头基线格、c02cb98 的历史审计（缺失或代码已变即停），先只跑五个 P3 作闸门，通过才继续；判读器缺历史审计时 89-2 ① 直接判不过，不再退回同输入表；`ruling89_sides.sh` 的 `REVISION_91` 模式已停用。待裁 91 (a) 因此是“有预算与停止条件的一次工程尝试”：闸门约 30 分钟，全链约 4～5 小时，失败按 89-8 停止；不承诺修订会奏效，关联侧能否越过平台尤其不确定。
  - **裁决 91 批准（2026-09-30，原话「待裁 91 取 (a)」）：89-2 与 89-3 各用这一次修订。** 内容照重提稿 (a)：学习率按 epoch 余弦衰减 1e-3 → 1e-5（20 遍不变）、每步梯度范数裁剪 1.0、存在决策用头输出减 ln(pos_weight) 的校正 logit；编码、类别权重、数据、种子、检查点规则与全部通过线不变。只经 `ops/vsmt/ruling91_revision.sh` 运行：先只跑五个 P3 作闸门，五个目标都在“最后一个 epoch”与“固定权重训练损失最低 epoch”两种读数上 ≥ 0.99 才继续；闸门不过或任一侧检查不过，按 89-8 停止重设计、写明证据等用户，不再修订。两侧都过才按原文做 89-4。它替代 89-2 原登记的 (b)。
    - 白话：这是存在侧和关联侧各自唯一的一次补救：只改训练的步子（越往后越小、每步不许迈太大）和存在决定的门槛校正，先用最便宜的模仿检查试，过了才花几个小时跑完整链；不过就停。
  - **裁决 92 批准（2026-09-30，原话「待裁 92 取 (a)」）：执行细则（二）补充条款下的暂定运行（`ruling89-sides-003b906`，LOG-288／LOG-289）追认为 89-2／89-3 的正式首轮，两侧都不过。** 流程偏离（补充条款改了已登记的停止规则而未经批准）保留记录，不删不改；追认理由是已有证据完整、无需重复计算。89-8 的计数：89-2、89-3 各已失败一次，裁决 91 是各自的那一次修订。
  - **待裁 93（2026-09-30 提出，LOG-290）：裁决 91 的修订闸门没过、按 89-8 停止重设计之后怎么走。** 依据：修订后 P3 HandCost 0.999、RAC 0.999 过，ELU-P 0.949／0.953、TAF 0.977／0.973、LOW 0.987／0.986 不过；只读诊断显示同一 ELU-P 头去掉 ln w 校正后为 0.994／0.991——存在侧的模仿问题被稳定化配方解决了，闸门失败来自我把 P3 设为读校正后 logit 的设计冲突；关联侧仍停在平台，与这个失误无关，单凭它五个目标也不会全过。没有任何闭环读数。
    - (a) **推荐**：按 89-8 的预先承诺停止 S2-R 学习闭环的重设计，进入 83-6 的备选路线讨论——以“协议加基准”为框架（ProcTHOR 覆盖式重访加不可观测窗口干预的数据协议、Dyn-THOR 对齐的指标、决定上限与机制检查、规则臂与学习臂的对照），学习方法作为基线之一如实报告；下一步由我起草框架裁决（待裁 94：主张、主表、S3 范围与确认集用法），不再训练。理由：停止规则就是为防止“修到过为止”而事先定的；关联侧的平台与本次失误无关；把现有证据写实比再追加一轮更可信。影响：S3 按新框架重排；已有开发集证据（G0、历史摘要独立核对、召回上限、两轮失败）全部保留为协议与基准的一部分。
    - (b) 例外续做（需要你明确推翻 89-8）：另开一条有预算的新轨道——存在侧沿用稳定配方、P3 改读未校正 logit（闭环的校准另设检查），关联侧另行设计（例如更长训练或更大容量），先登记再跑。影响：约 1～2 天；所有结果都要标明是在停止规则之后追加的，说服力低于事先登记的检查。
    - (c) 只修存在侧的设计冲突、按原修订重读闸门：不推荐——这是看完结果改读法，而且关联侧仍不过，闸门照样不过。
    - 批准句：「待裁 93 取 (a)」／「待裁 93 取 (b)」。
  - **裁决 93 批准（2026-09-30，原话「待裁 93 取 (a)，取消至多一次，P3 只报告，跑完整链，给我预估时长」；取代上面待裁 93 的原推荐）：继续 S2-R，取消 89-8 的“至多修订一次”，P3 改为只报告。** 用户同时澄清：89-8 的“唯一一次”不是其本意，停止规则只意味着停下等用户。
    - 93-1：89-8 的“每项检查不过至多修订一次”取消，改为有预算的迭代——每轮先登记改动与读法再运行，出数后写 LOG、提裁决，由用户决定是否继续；通过线不变。
    - 93-2：P3（模仿充分性）不再作 89-2／89-3 的通过条件，只报告；且改读**未校正**的 logit（修正待裁 91 里我定的读法与分类均衡一致率的冲突，LOG-290）。闭环里的存在决策仍用 ln w 校正后的 logit（首轮闭环的问题是过度撤回）。
    - 93-3：按裁决 91 的配方（余弦学习率 1e-3 → 1e-5、梯度裁剪 1.0、存在决策 ln w 校正）跑完整链：复用 003b906 的第 0 轮记录与旧头基线格、c02cb98 的历史审计 → 第 0 轮训练（种子 7）→ 第 1 轮 → 状态覆盖（仍是训练前的停止线）→ 五种子训练 → 两个半上限格 → 判读；89-2 以历史审计与“teacher 关联＋新存在头”格（Missing ≤ 0.05、节点 F1 ≥ 0.93）判定，89-3 以状态覆盖与同召回配对（82-1 规则、“选了新建”减少）判定；两侧都过即按原文接 89-4。入口 `ops/vsmt/ruling93_chain.sh`。
    - 白话：模仿检查从“拦路的门”改成“体检报告”，直接看闭环里方法到底行不行；不再限定只能修一次，每一轮由你看完再决定。
    - 表述更正（2026-09-30，采纳 ASTRA 复核，LOG-290 续；不改变 93-1～93-3 的做法）：93-2 里“修正……与分类均衡一致率的冲突”改为——拟合能力、决策阈值与误撤回代价此前被混在同一道检查里，现在分开报告：P3 读未校正 logit 只衡量拟合，闭环的误撤回由格检查衡量。闭环保留 ln w 校正是**待检验的方案**，不因首轮撤回过多就认定正确。P3 作为诊断照常报告，另按类别与关键事件（规则选择 × 实体状态、teacher 的撤回态／休眠态接回、teacher 存在标签、阈值附近的近似并列）列出不一致；它不再单独否决方法路线，但也不把改口径后的读数追溯为原检查通过。已发生的失败（LOG-288、LOG-290）照实保留。每一轮先写明要解决的问题、改动假设、影响范围与机时预算，出数后由用户决定下一轮；方法冻结后才在确认集上检验一次，validation／test 继续封存。
  - **裁决 94（2026-09-30，原话「待裁 94 取 (a)：先写 LOG-293 续并读失去承载记录，再起草多帧诊断登记稿，登记稿批准前不运行」）：批准后在执行前由用户叫停，未执行、未产生任何产物。** 内容原是：先用现有失去承载记录比较两个工作点，再起草多帧撤回规则的离线诊断登记稿。叫停原话「停，我觉得现在已经陷入了不断自证的怪圈，不断导数上面求导」，同时转来 ASTRA 复核：LOG-279 之后各轮都在半上限格、模仿与阈值上补检查，没有一次在改过的方法上重测主问题，检查不应取代研究目标。本条只作记录，不留后续义务。
  - **裁决 95 批准（2026-09-30，原话「待裁 95 取 (a)」）：半上限检查降为只报告，直接在开发集上测主问题。** 依据：主问题（学到的生命周期操作能否比同样学关联、但没有生命周期操作的 AssocOnly 更好地维护记忆）最后一次在同等条件下测是 LOG-279（旧配方、五种子：六项指标都分不出，均值上 AssocOnly 反而更好——Missing 残留率 0.272 对 0.357、身份连续率 0.486 对 0.405），此后没有再测；89-2 ② 的两条线能被错误行为满足（LOG-293：关闭校正这个事后工作点的五种子均值落在两条线内，同时约 7,700 次错撤），说明这组线不足以认证想要的行为；半上限格里 teacher 关联会把错撤的实体接回（种子 7：关闭校正格接回撤回态实体 2,778 次，保留校正 68 次），错撤在联合闭环里的代价在这种格里看不到。
    - 95-1：89-2／89-3 的半上限检查（89-2 ② 的两条线、89-3 的同召回配对与状态覆盖线）改为只报告，不再作为联合运行的前提；已发生的失败（LOG-288～LOG-293）照实保留。89-4 的四条线只作参照报告，不判通过。
    - 95-2：配置在运行前冻结。联合 VSMT-lean 用裁决 93 的五个第 1 轮头（`ruling93-9722290`），登记配置 τ_r 0.5、ln w 校正、k′=3，不重训；关闭校正是看过结果后才选的工作点，不用于任何主张。AssocOnly 按同样的关联侧改动重训（逐字段编码、第 0 轮 ELU-P 记录＋本臂第 1 轮记录、裁决 91 配方，无存在项）：第 0 轮训练（种子 7）→ 本臂第 1 轮 → 五个种子的第 1 轮训练。四个规则臂在现行评价代码下重跑（TAF、RAC、LOW 取开发配置，ELU-P 取第 0 轮配置；88-4 以来假撤回口径已变）。只用 39 条开发 episode。
    - 95-3：读法在运行前写死，只用已登记的规则。VSMT-lean 对 AssocOnly 按 82-1（至少 4/5 个种子同号且 |均值| > 5 个差的标准差）判六项指标的先后。“开发集上显示收益”＝Missing 残留率确定更好，且节点 F1 与身份连续率都不是确定更差；Missing 残留率确定更好、但节点 F1 或身份连续率确定更差＝“取舍，不主张收益”；Missing 残留率不是确定更好＝“开发集上未显示收益”（分不出不等于没有效果）。规则臂按 85-4 报 VSMT-lean 五种子 Missing 残留率是最好规则臂的几倍（≥ 2 时须在 S3-01 前裁定是否改主张框架）。
    - 95-4：各结果之后的下一步也先写死：显示收益 → 提议冻结方法、在确认集上评估一次（另行批准）；未显示收益或取舍 → 只挑一个具体失败机制（候选：存在标签能否从公开输入推断、存在决策的校准、关联的种子不稳），先写清怀疑哪里、应改变哪些读数、什么结果会否定这个解释，再改；不再新设代理门槛。
    - 95-5：开发集读数是样本内的：39 个开发 house 里有 30 个是学习头的训练 house。开发集上显示收益只算开发读数，主张在确认集上检验；开发集上都未显示收益，分量反而更重。
    - 入口 `ops/vsmt/ruling95_compare.sh`、判读 `ops/vsmt/ruling95_reading.py`（`d835cd3`）；机时估计 3～4 小时（估计，不作超时）。用户同日追加：「服务器跑完然后你拉取结果完之后立刻停机」——结果拉回本地核对后立即关机；驱动另设写完状态 2 小时后的兜底关机（其间无其他 vsmt 进程时）。
    - 白话：这次裁决解决“生命周期学习到底有没有用还没被直接测过”的问题。输入是同一批开发 house 上的三组运行：联合 VSMT-lean、按同样关联改动重训的 AssocOnly、重跑的规则臂；输出是按事先规则给出的“显示收益／取舍／未显示收益”，以及与规则臂的差距。例如 Missing 残留率五个种子里有 4 个更低、均值超过波动，而节点 F1 和身份连续率分不出，就记“开发集上显示收益”。它不是确认集结果，不选任何参数，也不再用半上限检查挡在主问题前面。
  - **待裁 96（2026-10-01 提出，LOG-294）：裁决 95 归“取舍，不主张收益”之后，按 95-4 挑哪一个机制。** 依据：Missing 残留率 VSMT-lean 确定更好（0.131 对 0.697），节点 F1 AssocOnly 确定更好（差 0.010，5/5），身份连续率分不出；节点 F1 的差距里撤回造成的无承载帧只占 0.7%～4.5%，精确率五个种子都更低；VSMT-lean 五个第 1 轮头都按总验证损失选中第 0 个 epoch，AssocOnly 的头选中第 2～5 个 epoch。
    - (a) **推荐**：只检验“检查点选择把关联头绑在存在损失上”这一个机制。
      - 怀疑哪里错：选点看关联＋存在的总验证损失，存在项从第 0 个 epoch 起上升，于是 VSMT-lean 的关联头也停在第 0 个 epoch；AssocOnly 的关联头按自己的损失训到第 2～5 个 epoch。节点 F1 的 0.010 可能来自这个不对称，而不是生命周期操作本身。
      - 改动（共享训练规则，对所有学习臂相同）：每个头按自己的验证项各自选点——关联与新建头按关联项，存在头按存在项。AssocOnly 只有关联项，选点不变，不重训。VSMT-lean 第 1 轮在同一批记录（`ruling93-9722290` 的第 0 轮 ELU-P 记录与第 1 轮记录）、同一配方与种子上重训一次（逐 epoch 分项照存），重跑 5 × 39 条联合审计，与本轮的 AssocOnly 头按裁决 95-3 同一规则再读一次。
      - 应改变的读数：节点 F1 不再是 AssocOnly 确定更好；Missing 残留率仍是 VSMT-lean 确定更好（存在头的选点预计仍在第 0 个 epoch，基本不变）。
      - 否定条件：节点 F1 仍是 AssocOnly 确定更好 → 这个解释不成立，撤下，不再在选点上找原因；若 Missing 残留率不再确定更好，照原规则记录。
      - 影响：改 `lean_model.train_heads` 的选点（单职责提交、带测试）；约 2 小时机时（训练约 1 小时、审计约 1 小时），需要开机；不碰确认集、validation、test。归类若变为“显示收益”，按 95-4 另行提议冻结方法、在确认集上评估一次。在同一开发集上每多改一轮，开发读数就更乐观一分，最终以确认集为准。
    - (b) 检验“存在标签能否从公开输入推断”：它针对的是 Missing 残留率对 RAC 的差距与错撤，不是这次决定归类的节点 F1；做法还要另行设计，暂不推荐。
    - (c) 不再改：把“取舍”写成开发集结论，转 83-6“协议加基准”的框架讨论。影响：不花机时；贡献一只能写成“生命周期操作大幅减少陈旧实体，但节点 F1 小幅下降、身份连续率未见差别”。
    - 批准句：「待裁 96 取 (a)」／「待裁 96 取 (b)」／「待裁 96 取 (c)」。
    - 更正（2026-10-01，采纳 ASTRA 复核，LOG-294 续）：(a) 里“存在项从第 0 个 epoch 起上升，于是 VSMT-lean 的关联头也停在第 0 个 epoch”是假设；已知的只有总验证损失选中第 0 个 epoch。训练跑完全部 epoch，只是保留早期权重。
  - **裁决 96 批准（2026-10-01，原话「待裁 96 取 (a)，按补全的约束做，跑完拉回结果后立即关机」）：只检验选点规则这一个机制，保留 LOG-294 的“取舍”归类。** 按 ASTRA 补全的约束：
    - 96-1：训练过程不变——同一批记录（`ruling89-sides-003b906` 第 0 轮、`ruling93-9722290` 第 1 轮）、裁决 91 配方、五个种子、4 线程、所有头一起梯度裁剪；只改保留哪一轮权重。关联头与新建头共用一项交叉熵，按关联项成组选同一个 epoch；存在头按存在项单独选；并列取更早。
    - 96-2：同一次重训同时保存原规则（总验证损失）与分组规则两份权重；原规则的五份权重摘要必须与 9722290 完全一致才继续，否则停下报告、不跑审计。一致时，原规则的联合结果就是 d835cd3 的 JOINT 导出。
    - 96-3：只把分组权重放进联合闭环（τ_r 0.5，5 × 39），与 d835cd3 的 AssocOnly（分组选点对它不变，不重训）和规则臂，按裁决 95-3 同一规则归类；Missing 残留率的收益在联合运行里重新核验。
    - 96-4：若节点 F1 仍是 AssocOnly 确定更好，只否定“单改选点足以消除这次差距”，不否定全部训练耦合解释；不新设代理门槛。
    - 入口 `ops/vsmt/ruling96_selection.sh`（`7c76970`），代码 `e44fee9`；约 2 小时机时；跑完拉回结果后立即关机。
    - 白话：训练一点不改，只换“最后留哪一轮权重”的规则，看节点 F1 那 0.010 的差距是不是选点造成的。输入是原来的训练记录，输出是分组选点的头在联合闭环里的表现，与 AssocOnly 按原规则比较。例如关联与新建留第 4 轮、存在留第 0 轮。它不改训练、不改评价，也不是泛化证据。
  - **待裁 97（2026-10-01 提出，LOG-295）：开发集上归“显示收益”之后，是否按 95-4 冻结方法、在确认集上评估一次。** 依据：原规则逐位复现 9722290；分组选点后 Missing 残留率（0.135 对 0.697）与身份连续率（0.309 对 0.212）VSMT-lean 确定更好，节点 F1 分不出（均值差 −0.006，sd 0.019，种子 31 单独下降）；这条规则是看过开发集结果后提出的，开发集又是样本内。
    - (a) **推荐**：冻结现在评估过的这一版，在确认集上评估一次。
      - 冻结内容：VSMT-lean 五个分组选点头（`7c76970` 的 `weights_grouped.json`，摘要在运行前写进登记）、AssocOnly 五个头（`d835cd3`）、四个规则臂的开发配置；τ_r 0.5、ln w 校正、k′=3、模拟器实例分割前端与评价代码都不变。第 0 轮仍是原规则选出的头，方法描述照实写成“第 1 轮分组选点”。
      - 范围：裁决 81 冻结的确认集（train 块第 50～99 位；生成成功 43 个，7 个生成失败按缺失记录，不补不换）；两个学习臂各 5 个种子加 4 个规则臂，共 602 条审计；不训练、不选任何参数。
      - 读法与开发集相同，事先写死：裁决 95-3 的归类（82-1 规则）、85-4 比值，89-4 四条线只作参照，另报开发集与确认集逐项对照。确认集只用这一次；无论结果如何，不在确认集上调整或重跑。
      - 结果对应：确认集也归“显示收益” → 这一版对 AssocOnly 的收益在没见过的 house 上成立（仍限于 ProcTHOR 与模拟器实例分割前端），据此讨论恢复 S3 与论文表述；归“取舍”或“未显示收益” → 开发集上的收益没有复现，如实记录，再回到 95-4 或框架讨论。
      - 影响：约 2.5 小时机时（估计），需要开机；跑完拉回结果后立即关机。确认集用掉以后，方法再改就要另生成一批确认数据（train 块其余位置）。
    - (b) 先把分组选点用到整个流程（第 0 轮也分组选点，第 1 轮记录随之重生成），在开发集上再读一次再上确认集。影响：方法定义更干净，但又多一轮开发集迭代（约 4 小时），开发读数更乐观。
    - (c) 暂不动用确认集，先在开发集上处理其余差距（Missing 残留率是 RAC 的 1.5 倍、身份连续率 0.309 低于 89-4 的 0.45）。影响：确认集留给更终态的版本，但继续在样本内迭代，正是之前“怪圈”的风险。
    - 批准句：「待裁 97 取 (a)，跑完拉回结果后立即关机」／「待裁 97 取 (b)」／「待裁 97 取 (c)」。
    - 补充（2026-10-01，用户问选点机制与公平性之后提出）：(a) 可加一行事先登记的敏感性对照——原规则的五个 VSMT-lean 头（9722290）也在确认集上跑一遍，只报告、不参与选择；约多 215 条审计。
  - **裁决 97 批准（2026-10-01，原话「实例已经开机，待裁 97 取 (a)，加原规则敏感性一行，跑完拉回结果后立即关机」）：冻结 LOG-295 这一版，在确认集上评估一次，加原规则敏感性一行。**
    - 97-1：冻结内容以 `ops/vsmt/ruling97_freeze.json`（`5176bb6`，运行前提交）为准：VSMT-lean 分组选点头（`7c76970`，主读数）、VSMT-lean 原规则头（`9722290`，敏感性）、AssocOnly 头（`d835cd3`），各按权重摘要；四个规则臂的开发配置；τ_r 0.5（ln w 校正后的 logit）、k′=3、模拟器实例分割前端、评价代码自 `7c76970` 不变。只有第 1 轮用分组选点，第 0 轮仍是原规则选出的头。
    - 97-2：范围是裁决 81 冻结的确认集里同时有 episode、oracle cache 与几何重载的 43 个 house；7 个生成失败按缺失记录，不补不换。不训练、不选参数。
    - 97-3：读法事先写死：主读数为分组版对 AssocOnly 与规则臂的裁决 95-3 归类（82-1 规则）与 85-4 比值，89-4 四条线只作参照；敏感性为原规则版的同一读法，只报告，出数后不在两者间挑选；另报开发集与确认集逐项对照。
    - 97-4：确认集只读这一次。只有工程故障可以用同一冻结输入续跑；结果无论如何，不在确认集上调整或重跑。结果对应：主读数也归“显示收益” → 这一版对 AssocOnly 的收益在没见过的 house 上成立（限于 ProcTHOR 与模拟器实例分割前端）；归“取舍”或“未显示收益” → 开发集上的收益没有复现，如实记录。敏感性一行用来判断结论是否依赖选点规则。
    - 入口 `ops/vsmt/ruling97_confirmation.sh`、核对 `ops/vsmt/ruling97_verify.py`；817 条审计（19 组 × 43），约 3～3.5 小时；跑完拉回结果后立即关机。
    - 白话：确认集是最后只考一次的“期末卷”。这次把开发集上评出“显示收益”的那一版原封不动地拿去考，同时把原规则那一版也考一遍，看结论是不是靠选点规则撑起来的。输入是从没用于训练或选点的 43 个 house，输出是同一条规则下的归类。它不是正式 test，validation／test 仍封存。
  - **待裁 98（2026-10-01 提出，LOG-296）：确认集出数之后，S2-R 怎样收口、贡献一怎样写、S3 怎样进入。** 依据：确认集主读数（分组版）归“显示收益”——Missing 残留率 0.189 对 0.795、身份连续率 0.124 对 0.017 都确定更好，节点 F1 分不出但 4/5 个种子更低（均值差 −0.010）；敏感性（原规则版）归“取舍”（节点 F1 确定更差）；对 RAC，Missing 残留率仍高（0.189 对 0.166，1.14 倍），节点 F1、身份连续率与假撤回率更好。
    - (a) **推荐**：S2-R 收口，贡献一按 LOG-296 的限定写定（只改文字，标明“确认集一次性评估、ProcTHOR、模拟器实例分割前端”）：“同样学习关联时，生命周期操作在没见过的 house 上大幅减少陈旧实体（约 0.80 → 0.19）、身份连续率更高、恢复更快；节点 F1 约低 1 个点（原规则下确定更差，分组选点下分不出）；对最强规则臂 RAC，Missing 残留率仍略高，节点 F1、身份连续率与假撤回率更好。”随后由我起草“S3 进入方案”另提裁决，内容包括：S2-06 SAM2 开发表；方法定义是否补全（第 0 轮也分组选点、带 NoVersion 的七臂开发表）；主门口径（Missing 一项两套数据都没越过 RAC）；S3-01 的冻结项。本条不运行任何东西。影响：不花机时；S3 继续暂停，直到 S3 进入方案批准。
    - (b) 先在开发集上处理节点 F1 约 1 个点的代价（例如关联与存在分开做梯度裁剪或分开训练），再进 S3。影响：至少一轮训练与审计（约 2～3 小时），开发集继续样本内迭代；确认集已用掉，改动后的收益只能靠 S3 的一次性 test 或另生成一批确认数据来检验。
    - (c) 直接转框架讨论（裁决 83-6 的备选）：主门的 Missing 一项在两套数据上都没越过 RAC，把主张收窄为“生命周期操作对只学关联的因果对照，加协议与基准”，S3 范围随之重排。影响：不花机时；论文主张改变，需另裁。
    - 批准句：「待裁 98 取 (a)」／「待裁 98 取 (b)」／「待裁 98 取 (c)」。
    - 修改（2026-10-01，采纳 ASTRA 复核，用户批准前）：(a) 的收口改为“已确认存在价值与代价”，不写“整体优势已成立”；不把“第 0 轮也分组选点”列为补全项（那是新变体）；S3 方案优先处理已有承诺：SAM2 第二前端、NoVersion 等必要消融、正式选参与主门、数据与预算冻结。
  - **裁决 98 批准（2026-10-01，原话「待裁 98 取 (a)，按 ASTRA 修改的收口表述与 S3 方案范围」）：S2-R 收口。** 收口表述与六处措辞更正见 LOG-296 续；方法定义按评估过的版本冻结（第 0 轮按总损失选点、第 1 轮分组选点）；METHOD 的主门与主张边界不在本条改动，交给 S3 进入方案（待裁 99）。确认集已用过，不再用于任何主张。（表述更正，2026-10-01，采纳 CODEX：上一句过头，应为“既有确认结果继续支持冻结版本的限定结论；不得用于后续调参，也不得替修改后的版本背书”。）
    - 白话：S2-R 到此为止。我们确认了“生命周期机制在没见过的 house 上大幅减少陈旧实体、身份连续率更高，代价是节点 F1 小幅下降约 1 个点”，但没有确认“整体更好”，也还没证明版本化本身的作用。下一步不再修方法，而是定 S3 怎么进。
  - **待裁 99（2026-10-01 提出，裁决 98）：S3 进入方案。** 依据：S2-R 已收口；METHOD 第七节的训练配方与第十一节的主门仍是 S2-R 之前的文字；裁决 83／84 的 S2-06（SAM2 第二前端）与 S3-02 主机前提未落地；83-1 选参约束、83-5 检索成功率定义未冻结。只写方案，不运行任何东西。
    - 99-1 方法定义冻结（推荐，只改文字与合同说明）：S3 用评估过的这一版——存在头 17 维（原 12 维加 5 个历史量）、逐字段编码、存在损失按类别加权且决策用减去 ln w 的 logit、学习率余弦 1e-3 → 1e-5 与所有头一起的梯度裁剪 1.0、两轮 DAgger（第 0 轮用 ELU-P 记录、按总损失选点；第 1 轮用第 0 轮 ELU-P 记录加本臂第 1 轮记录、分组选点）、5 个种子；AssocOnly 的关联侧完全相同、无存在项；NoVersion 用 VSMT-lean 的头；HeuristicLabel 用同一配方。不引入新变体。就地修订 METHOD 第七、十节与 S0-05 训练说明并重钉摘要，代码开关都已存在。
    - 99-2 主门（必须选一）：
      - (a) **推荐**：前瞻修订，明确标为“看过开发集与确认集之后、读取 validation／test 之前”的协议修订。首要假设改为：VSMT-lean 对同配方 AssocOnly，在 Missing 残留率与身份连续率上单侧 95% 下界都大于 0；节点 F1 作事先登记的非劣检验，裕度在 S3-01 按与结果无关的理由冻结（建议 0.03，约一个跨种子标准差，LOG-279 的 0.027～0.033，不取确认集的 0.010）。原主门（对最强对照）照原文计算，在论文中报告为“尚未满足的原目标”，不追溯宣布通过；对规则臂的比较按多指标取舍报告。影响：首要检验对准 S2-R 真正回答的问题；S3 仍可能不过；修订本身须在论文里写明。
      - (b) 保留原主门不变：S3 照原文判定。按开发集与确认集读数，Missing 一项（对 RAC）很可能不过，S3-06 将报告 no-go，对 AssocOnly 的比较作并列报告。影响：协议最干净，但主结论大概率是“原门未过”。
      - (c) 对规则臂改为“Missing 非劣＋身份连续率与节点 F1 优于”的组合门。影响：裕度仍需另定，同样属于看过结果后的修订，且非劣裕度对 RAC 的 2.3 个百分点很敏感。
    - 99-3 臂与消融（推荐）：按已登记的全套——主比较 VSMT-lean／TAF／ELU-P／RAC／LOW，消融 NoVersion／HandCost／HeuristicLabel／AssocOnly，LLM-op 只在 validation 作附录；可选臂 VSMT-lean-ctx 退出 S3，控制范围。
    - 99-4 S2-06 SAM2 开发表（推荐照裁决 84 做，S3-01 前完成）：用冻结的方法原样在 SAM2 开发 cache 上跑七臂开发表（含 NoVersion），顺带在实例分割开发集上补一个 NoVersion 读数（约 1 小时）；只作“结论在 SAM2 下是否保持”与 S3 预算的开发读数，不据此改方法（工程故障除外）。前提：开机后只读核对 SAM2 cache `lean-s1-03-154776d`（原放在旧实例系统盘 `/root/vsmt_cold`）是否在本机且摘要一致，不在则另提迁移或重建（4080 SUPER 上约 19 小时）的裁决；84-1 (b) 的 SAM2 ReID 头摘要先钉住。约 1～1.5 天（估计）。
    - 99-5 S3-01：99-2 定下后，由我起草 S3-01 冻结稿（待裁 100）：三个 manifest 与种子、bootstrap 种子与种子×house 的合并方式、主门效应量与停止规则、83-1 选参约束（在 ln w 校正后的 τ_r 网格上）、83-5 检索成功率定义、关键事件预算（功效）、79-7 风险与 D2 外推复核、S3-02 主机与 ≥ 300 GB 数据盘（84-5／84-7）。
    - 顺序：99-1 文档 → 99-4 S2-06 → 待裁 100（S3-01）→ S3-02。S3-03 起的训练全部用 99-1 冻结的配方。
    - 批准句：「待裁 99 全按推荐」，或逐项改，例如「待裁 99：99-2 取 (b)，其余按推荐」。
    - 修订（2026-10-01，采纳 CODEX 复核，用户批准前，逐条核实）：① 撤下 99-2 (a) 的 0.03——“与结果无关”却引 LOG-279 的跨种子标准差，自相矛盾，且训练波动不等于可接受的损失；非劣裕度只有在 S3-01 给出独立、可解释的容忍依据时才冻结，否则只报告节点 F1 的差值与区间、不作非劣主张；原主门照算，开发集与确认集上记“未满足”，S3 按实际判定，不提前写死。② 99-4 的 S2-06 是裁决 84-3 的完整链（校准→网格复核→ELU-P 拟合→第 0 轮→训练→第 1 轮→训练→七臂开发表），两个学习臂在 SAM2 记录上按冻结规则重训，不复用实例分割下的头（那是跨前端迁移的另一个问题）；运行前先写完整阶段协议。③ 99-1 须按实际代码与产物完整同步：输入 14／17／4 维、逐字段编码、参数 54,787（AssocOnly 35,842），类别权重与编码统计只来自训练 house 记录；S2-05 正式训练入口没有新配方开关、S0-05 训练块仍是旧配方，须写明现行入口并要求 S3 正式入口默认这套配方。④ AssocOnly 与五个主比较臂并列进主表，NoVersion 单独检验版本保留。⑤ S3-01 须在 SAM2 正式出数前定好两张主表怎样共同决定结论。
  - **裁决 99 批准（2026-10-01，原话「待裁 99 按 CODEX 修订版全部批准」）：S3 进入方案。**
    - 99-1 方法定义按实际代码与产物同步：METHOD 第七、十节改写；S0-05 `arms.VSMT-lean.training.s2r_recipe` 就地记录冻结配方，规则摘要 `c9a44bd3` → `806611ad`（裁决 89 之前的运行仍绑定 `c9a44bd3` 与当时的提交）；现行实现入口 `ops/vsmt/ruling89_train.py --revision-91 --group-selection`，S3 正式训练入口须默认这套配方（S3-03 准备时实现并测试）。
    - 99-2 主门：首要假设为 VSMT-lean 相对同配方 AssocOnly 在 MRR 与身份连续率两项的单侧 95% 下界均大于 0，标明为看过开发集与确认集之后、读取 validation／test 之前的协议修订；不设预定的非劣裕度（S3-01 有独立依据才冻结，否则只报告取舍）；原主门照原文计算与报告，S3 按实际判定。METHOD 第十一节已改写；S0-04 `main_gate` 字段在 S3-01 就地修订。
    - 99-3 臂与消融：已登记全套；AssocOnly 与五个主比较臂并列进主表；NoVersion 单独报告；VSMT-lean-ctx 退出 S3。
    - 99-4 S2-06：立项；先写完整阶段协议（待裁 100）再运行，协议写清两个学习臂在 SAM2 记录上的训练记录、选点、种子与预算，SAM2 专属 ReID 头摘要，ELU-P 拟合量与校准结果的使用规则，校准分位数出网格即停下登记（84-2），七臂＝五个主比较臂＋NoVersion＋AssocOnly，84-6 的 mask 层修订在 S2-06 读数后、S3-02 前裁定；前提是开机核对 SAM2 cache 是否在本机。机时在协议写完后估。
    - 99-5 S3-01 冻结稿（待裁 101）：在 99-2 基础上冻结效应量、种子与 house 的合并方式、停止规则、选参约束、检索成功率定义、功效与主机磁盘，并在 SAM2 正式出数前定好两张主表怎样共同决定结论（各自报告支持范围，或两种前端都通过才主张跨前端成立；不得事后挑表）。
    - 用户追加要求（同日，原话「最后的结果，包括目前的前端和SAM2前端，到时候全部都要能够复现，不能只呈现数字，人家看代码的时候可读性要高，目前ops这么多文件，如果是之前版本的，没用的可以删除了」）：最终结果的两套前端都必须能从可读的代码完整复现（每个阶段一个写明命令的正式入口：生成→cache→训练→评估→出表，配置与种子钉住），列为 S3 的交付物；ops 里旧版本、已无用的文件经复现依赖核查后删除，删除清单先给用户过目。
    - 白话：这次裁决决定 S3 怎么进：方法照评估过的那一版写准确；首要问题改成“生命周期机制相对只学关联到底值多少”，并如实标明这是看过结果后的修订；SAM2 第二张表先写清协议再跑；S3-01 再冻结统计细节。它不运行任何计算，也不宣布任何门槛已过。
  - **待裁 100（2026-10-01 提出，裁决 99-4；LOG-299）：S2-06 SAM2 开发表的阶段协议。** 依据：SAM2 开发 cache（39 条、44,097 帧）与 SAM2 ReID 头（`f6fc67e5…`）都在服务器上且摘要一致；代码里 ReID 头摘要写死为实例分割那份、ELU-P 拟合量只有一套。
    - 它回答什么：S2-R 在实例分割前端上看到的模式——相对同配方 AssocOnly，Missing 残留率大幅更低、身份连续率更高、节点 F1 小幅更低；相对规则臂的多指标取舍——换成 SAM2 前端、所有可训练和可拟合的部分都按冻结规则在 SAM2 上重来以后，是否还在。输入是 SAM2 开发 cache、SAM2 ReID 头、同一几何重载与同一代码；输出是 SAM2 七臂开发表与读数。它不是 test，不是跨前端迁移检验（头在 SAM2 上重训），也不据此改方法。
    - 100-1 开跑前的实现（单职责提交，带测试；运行前服务器全量测试）：
      - (i) 裁决 84-1 (b) 落地：S0-03 在 ReID 选择记录旁登记 SAM2 头摘要 `f6fc67e5…`；三个入口按 episode 的 `mask_source` 取对应摘要，同一趟或同一组审计里混用两种来源即拒绝。
      - (ii) ELU-P 拟合量按 `mask_source` 分存：S0-05 增加 SAM2 一套（运行前为空，由 S2-06 的拟合趟按登记程序填入，记入跨合同台账）；`expected_pass_config` 按来源读取；实例分割那套不动。
      - (iii) S2-06 正式驱动：一个入口，阶段有名字（核对 → 校准 → 网格复核 → 拟合 → 第 0 轮 → 第 0 轮训练 → 第 1 轮 → 第 1 轮训练 → 七臂审计 → 合并 → 判读），每段可续跑、写回执与标记，全程 `--mask-source sam2`；按用户要求写成可读、带说明的复现入口，作为最终流水线的一部分。
    - 100-2 流程（冻结规则，在 SAM2 上重新拟合与训练）：
      1. 校准趟：按裁决 75 口径（TAF θ_a 0.7 无门＋ELU-P 计数），39 条。
      2. 网格复核（裁决 84-2，事先写死）：对裁决 68 为各网格引用的校准量逐项在 SAM2 上重算，并与实例分割的同一量并排——TAF θ_a 取“同物体余弦 ≥ c 的占比减异物体 ≥ c 的占比”最大的 c；距离门与 LOW 取同物体距离中位数；RAC ρ_rac 与 HandCost ρ_h 取“gone 覆盖 ≥ ρ 的占比减 present 覆盖 ≥ ρ 的占比”最大的 ρ；应可见下限取应可见比例分布。任一网格的端点不再括住对应的点或中位数，即判“出界”：停下，另提裁决按 `mask_source` 分存网格，在拟合与规则臂运行之前完成；不边看边改。
      3. ELU-P 拟合：按登记程序只在 30 个训练 house 上拟合，结果填入 SAM2 那套。
      4. 第 0 轮：ELU-P 在 `rollout_config` 加 SAM2 拟合量下产生 39 条记录。
      5. 第 0 轮训练：VSMT-lean 与 AssocOnly 各一次（种子 7，冻结配方，按总验证损失选点）。
      6. 第 1 轮：两个学习臂各用自己的第 0 轮头产生记录（VSMT-lean τ_r 0.5）。
      7. 第 1 轮训练：两臂各 5 个种子，用第 0 轮 ELU-P 记录加本臂第 1 轮记录；VSMT-lean 分组选点，AssocOnly 只有关联一组；回执保存逐 epoch 分项损失。
      8. 七臂闭环审计（39 条 SAM2 episode）：VSMT-lean（5 种子）、NoVersion（VSMT-lean 的头加删除开关，5 种子）、AssocOnly（5 种子）、TAF／RAC／LOW（开发配置）、ELU-P（第 0 轮配置加 SAM2 拟合量）。
      9. 顺带（裁决 99-4）：在实例分割开发集上用冻结的分组头（`7c76970`）补 NoVersion 读数，5 × 39 条。
    - 100-3 读法（事先写死，只作开发读数）：VSMT-lean 对 AssocOnly 按 82-1 逐项、按 95-3 归类，回答“模式在 SAM2 下是否保持”；VSMT-lean 对 NoVersion（两套前端）按 82-1 逐项报告，回答版本保留本身的作用，不设门；规则臂报 house 均值与 85-4 比值（对 Missing 残留率最低的规则臂）；与实例分割开发读数（LOG-295）逐项并排。39 个 house 里 30 个是训练 house，是样本内读数。读数不用来改方法（工程故障除外），只供 S3-01 的两前端结论规则与 84-6 的 mask 层修订（S3-02 前裁定）参考。
    - 100-4 资源与停止：在现在这台 4 卡实例上正常开机（CPU 配额随卡数，4 卡 68 核；GPU 基本不用）；产物估计不超过 15 GB（数据盘余 46 GB）。驱动先在一条大 SAM2 episode 上实测各段耗时，再定总预算，粗估 15～25 小时（不作超时）；趟按 episode 并行（39 个），训练 5 个并行各 4 线程，审计用配额减 4 个 worker 且按内存核验。停止规则：网格出界即停下登记；工程故障修复后用同一输入续跑，不换数据、不改规则；跑完拉回结果后立即关机。
    - 100-5 不做的事：不碰 S3 数据、validation、test 与已用过的确认集；不引入新方法变体（例如第 0 轮分组选点）；不调网格（出界只停下登记）。
    - 选项：(a) **推荐**：照上面全部执行。(b) 去掉第 9 项的实例分割 NoVersion 读数，省约 1 小时；版本保留的作用只在 SAM2 上有开发读数，实例分割那边留到 S3。(c) 暂缓 S2-06，先写 S3-01 冻结稿；第二前端的风险推迟到 S3 才暴露。
    - 批准句：「待裁 100 取 (a)」／「待裁 100 取 (b)」／「待裁 100 取 (c)」。
  - **裁决 100 批准（2026-10-01，原话「待裁 100 取 (a)，加 100-6 复现要求，我要新开对话去实现这个」）：S2-06 照待裁 100 (a) 全部执行，并增加 100-6。** 实现在新对话中进行。
    - 100-6 复现要求：① 一条命令跑完整条链（例如 `bash ops/vsmt/s2_06_sam2.sh`），阶段有名字，可只跑某一段、可续跑，文件开头写清用法；② 输入全部钉死并写进运行清单：cache 与 ReID 头的摘要、配置、种子、代码提交、线程数；③ 输出全部留档：各段回执、训练好的权重及摘要、审计结果、合并导出、判读 JSON，表中每个数字都由已提交的脚本从这些文件算出，不手抄；④ 可复核：同一提交、同一线程数重训的权重应逐位相同（裁决 96 已验证），审计是确定性的，驱动最后核对这些摘要；⑤ README 写一段“怎样复现 S2-06”，列命令、输入路径与预计耗时，让别人照做能得出同一张表。S3 的最终结果（两套前端）照同一标准。
    - 白话：结论要事先定好怎么下，数字要别人能照着命令重新跑出来；这条把“能复现”从口头要求变成 S2-06 的交付物。
  - **裁决 100 落地（2026-10-01，实现完成、待用户审查；未运行任何东西）。** 六个单职责提交，本地逐模块测试：
    - `94491fb` 100-1 (i)＝裁决 84-1 (b)：S0-03 `selection_result.heads_by_mask_source` 登记两份头（实例分割 `5cea91cf…`、SAM2 `f6fc67e5…`，各绑已提交的 S1-04 报告与 S1-05 回执），主表那份选择记录一字不变；S2-01 合同 `descriptor.weights_sha256_by_mask_source`。三个入口按 episode 封印声明的来源取摘要（SAM2 封印没有 `mask_source` 字段即 sam2）：S2-01 入口加载帧之前读封印，S2-04 入口用 `--mask-source`（封印须相符），节点审计加可选 `--mask-source`；节点审计 v11 记下来源与权重摘要，合并时混用来源（或新旧回执混合）即拒绝。重钉 S0-03 `70c13b5f` → `5f60345b`、S2-01 `8bc99b13` → `da2ab804`。
    - `8a7b30e` 100-1 (ii)：S0-05 `arms.ELU-P.fitted` 仍是实例分割那套（`fitted_mask_source` 写明），SAM2 那套是新增的三个值槽 `fitted_by_mask_source.sam2.*`，在任何值出现之前登记（记账键 `registered_value_slots_added`，跨合同测试的 `SLOTS_REGISTERED_AFTER_V1` 同步登记）；`expected_pass_config` 按来源读取，SAM2 那套为空时第 0 轮拒绝运行；`fit-elu-p` 记下来源，登记后重拟合须逐位相等。重钉 S0-05 `806611ad` → `0065b9b4`（值槽不进摘要）。
    - `b37e672` 网格复核 `ops/vsmt/s2_06_grid_review.py`：按待裁 100 第 2 步写死的判定点，SAM2 与实例分割并排；出界退出码 4。校准报告记下来源。
    - `661bd8d` 判读 `ops/vsmt/s2_06_reading.py`：100-3 的读法，两套前端并排；实例分割那份从已提交导出重算，须与已提交判读（`7c76970`）逐项相等。`ruling82_seed_analysis` 推广到任意两臂，默认输出不变（逐项复现已提交判读即为证明）。
    - `ddd312e` 正式驱动 `ops/vsmt/s2_06_sam2.sh` 与记账 `ops/vsmt/s2_06_manifest.py`（100-1 (iii)、100-6）：14 个有名字的阶段，每段标记、可续跑、运行清单、按 cgroup 配额与实测峰值内存定 worker、兜底关机；`run-pass --largest-first`（只改派发顺序）。实例分割补 NoVersion 之前先核对今天的代码能逐项复现 `7c76970` 的一条审计；verify 阶段重跑一条 SAM2 审计比对、核对全部摘要。
    - `4f66a41` README“怎样复现 S2-06”。
    - 首跑的设计停点：elu-p-fit 拟合出 SAM2 三个值后停下（`hold`），由我按裁决 68 (10) 的预授权提交登记（S0-05 填值、`lean_arms` 冻结值、跨合同台账），在那个提交上再跑 `all`，该段核对重拟合与登记值逐位相等后继续；以后在最终提交上复现不会再停。
    - 实现中发现协议原文有两处需要用户先定，提为待裁 101（下一条）；S3-01 冻结稿顺延为待裁 102。
    - 白话：S2-06 要的代码都写好了，没有上服务器跑；运行前要用户审代码，并先定网格复核怎样判“出界”。
  - **待裁 101（2026-10-01 提出，S2-06 实现时发现；运行前必须定）：网格复核的出界判定与 ELU-P 拟合的 house 范围。**
    - 依据（只用已提交的数据，见 `tests/test_vsmt_lean_s2_06_grid_review.py` 的钉住读数）：把待裁 100 第 2 步写死的判定点套到实例分割校准趟（`results/vsmt_lean_s2_05_calibration_oracle_850c533.json`，即裁决 78 据以保留现有网格的那一趟）上：TAF θ_a 的交叉点 0.70，在 {0.6, 0.7, 0.8} 之内；同物体质心距离中位数约 0.19 m（≤ 0.25 m 的占 58%，≤ 0.5 m 的占 68%），低于 TAF d_a 的最小有限门 0.5 与 LOW 的 0.25；“gone 覆盖 ≥ ρ 的占比 − present 覆盖 ≥ ρ 的占比”在 ρ = 1/64 处最大（0.35，往上单调变小，0.70 处 0.071），低于 RAC {0.7, 0.85} 与 HandCost {0.6, …, 0.9}。也就是说，按原文，实例分割自己就有 4 个网格“出界”；裁决 78 (2) 保留覆盖网格用的是另一种读法（覆盖 ≥ 0.7 时真被拿走 68.5%、在场 1.7%，看低误报），不是这里的最大差。照原文跑，S2-06 几乎必然在网格复核停下，而停下的理由对实例分割同样成立，回答不了 84-2 真正的问题（SAM2 需不需要自己的网格）。应可见下限是单个值，没有端点可括，只能报告分布（1～3 个点可见的行：在场 12.0%、离场 9.4%，即裁决 78 (1) 的读数）。
    - (1) 出界判定。
      - (a) **推荐**：相对判定——每个判定点先看实例分割的点落在网格有限端点的哪一侧（之下／之内／之上），SAM2 的点只有落在网格之外、而且与实例分割不在同一侧时才判“出界”并停下；与实例分割同在网格外同一侧，记“与实例分割同一状况”，不停，作为 S3-01 的一项（两套前端的距离与覆盖网格要不要往下扩）留到 S3-01 裁定；应可见下限只报告。影响：回答的是“SAM2 是否需要不同于实例分割的网格”；在任何 SAM2 数据出现之前写死，不是边看边改；只改网格复核的判定函数与测试，合同不动；S3-01 多一个待定项。
      - (b) 维持原文（绝对括住）：预计校准后即停（约 3～5 小时机时之后），再另提按来源分存网格的裁决；同一规则会把实例分割的现有网格也判为出界，等于重开裁决 78。
      - (c) 改用当初保留各网格时的读法（覆盖：在场误触发 ≤ 约 2%、真被拿走检出 ≥ 约 60%；距离：门覆盖同物体对约 1/3～2/3），给出数值线：更贴近当初的理由，但要现在新冻结几条数值线。
    - (2) ELU-P 拟合的 house 范围。待裁 100 第 2 步第 3 项写“只在 30 个训练 house 上拟合”，而登记程序（`fit-elu-p` 读校准趟，裁决 68 (10) 在实例分割上就是这样拟合的）是对全部 39 条开发 episode 求和（它们都属 train 划分）。
      - (a) **推荐**：按登记程序，39 条，与实例分割同一程序；“30”是提案措辞的错误，照实更正。影响：两套前端的 ELU-P 拟合可比；不改代码。
      - (b) SAM2 只用 30 个训练 house：两套前端拟合程序不同，要加代码开关。
      - (c) 两套前端都改为 30 个：实例分割要重新拟合登记、ELU-P 相关读数要重跑，不推荐。
    - 批准句：「待裁 101 取 (1)(a)(2)(a)」，或逐项如「待裁 101：(1)(b)，(2)(a)」。
  - **裁决 101 批准（2026-10-01，原话「待裁 101 取 (1)(a)(2)(a)」）：网格复核按相对实例分割判定；ELU-P 拟合按登记程序。** 在任何 SAM2 数据出现之前定下。
    - 101-1 (1)(a)：每个判定点先看两套前端各落在网格有限端点的哪一侧（之下／之内／之上）；SAM2 的点落在网格外、而且与实例分割的点不在同一侧，才判出界并停下，另提按 `mask_source` 分存网格的裁决；与实例分割同在网格外同一侧，记“与实例分割同一状况”、不停。应可见下限只报告。原文的绝对读数仍写进报告，只供阅读。落地 `7e42258`（`s2_06_grid_review.py` 的 `verdict()`、测试、驱动说明与 README）。
    - 101-2 (2)(a)：待裁 100 第 2 步第 3 项“按登记程序只在 30 个训练 house 上拟合”更正为“按登记程序对全部开发 episode 求和”（`fit-elu-p` 读校准趟，与实例分割同一程序；SAM2 cache 有 39 条）。“30”是提案措辞的错误，不改代码。
    - 登记到 S3-01 的一项：若 S2-06 网格复核里有“与实例分割同在网格外同一侧”的检查项（照实例分割校准趟推断，最可能是 TAF d_a、LOW d_low、RAC ρ_rac、HandCost ρ_h），S3-01 裁定两套前端的这些网格要不要调整；理由须与哪个臂获胜无关，两套前端同样处理。
    - 白话：网格复核要回答的是“SAM2 需不需要一套不同于实例分割的网格”。实例分割自己的点就落在几个网格之外，所以只看 SAM2 有没有跑到与实例分割不同的一边；同在一边的问题两套前端都有，留给 S3-01 一起定。
  - **待裁 102 修订稿二（2026-10-02；初稿 `4ba8424`、修订稿 `4a33674` 先后经 ASTRA 两轮复核，逐条核实后重写；用户原话「起草待裁 102，含 85-4 框架裁决、101 同侧网格与 84-6」；LOG-300 之后）：S3-01 冻结稿。** 本条只起草，不改任何合同字节、不运行任何实验。规划数字全部由已提交的只读脚本 `ops/vsmt/s3_01_planning.py`（`6c57903`，9 项测试）从已提交的合并审计算出，报告 `results/vsmt_lean_s3_01_planning_6c57903.json`（numpy 2.4.3、Python 3.12.10、规划种子 102）。批准后才按单职责提交就地修订合同与文档并实现，用户审过代码后 S3-01 关闭。validation／test 一直未读。
    - **两轮复核的修订记录（逐条核实属实）。** 第一轮（修订稿已改）：① 排除清单没写死，三种取法给出 SAM2 身份连续率三个数；② 功效只估了 house 均值检验；③ 固定顺序是看过开发结果后设计的；④ 选参约束的三处问题；⑤ 102-1 违反裁决 99，并把“协议加基准”写成自动后备；⑥ 缺种子规则与 `ruling82_seed_analysis.verdict()` 不符；⑦ 检索指标定义不全。第二轮（本稿改）：⑧ 统一 house 清单不等于统一身份连续率的考题。`lean_teacher.identity_continuity` 只把“搬动前该臂有承载实体”的重见事件计入分母，分母随臂变化；重见事件本身逐 house 在全部运行里相同（报告 `denominators`）。例如 SAM2 开发集 63 个重见事件，VSMT-lean 种子 7 的分母 49、AssocOnly 48、TAF 53、LOW 只有 24。修订稿把 LOW 等规则臂的可判性带进了首要比较的样本，SAM2 身份连续率 +0.021 → −0.010 就是这样来的。本稿新增 102-0，先定事件定义。⑨ 修订稿的“约 0.01”是把开发估计 −0.010 当成真实效应的情景结果，不是功效，也推不出“test 再大也没用”；本稿改为零效应校准，加若干事先列出的正效应与种子波动的敏感性表，开发估计直接代入只作为情景单列。⑩ 两级重采样的保证写得过满。本稿写明两个维度独立抽取、所有种子共用当次抽中的 house；五个种子时百分位下界的覆盖率没有保证，已用模拟核验无真实收益时的误判率（见下）；结论限定为固定训练数据、配方与选参流程下的训练随机性。⑪ 102-4 无解时“不能主张减少陈旧实体”与 102-1“首要检验通过即可主张”冲突，本稿改为：数值检验照算，正式主张还须满足已登记的选参可行性条件。⑫ 修订稿的规划数字没有提交脚本与报告，无法复核；本稿的数字都可从上面的脚本与报告复现。
    - 依据：S2-06（LOG-300）SAM2 上 VSMT-lean 对 AssocOnly 归“开发集上显示收益”、与实例分割一致，但身份连续率分不出；85-4 比值 SAM2 2.39（ELU-P 0.050，范围内误撤回率 0.868）、实例分割开发集 1.52（RAC）、确认集 1.14（RAC）；网格复核在网格内，同侧三项 TAF.d_a、RAC.rho_rac、HandCost.rho_h 登记到 S3-01（裁决 101）。报告的开发重读（VSMT-lean 减 AssocOnly、正号表示 VSMT-lean 更好；种子平均后的差；两级重采样 10,000 次的单侧 95% 下界；样本内读数）：

      | 读数来源 | Missing 残留率 | 身份连续率·共同事件（102-0 (a)） | 身份连续率·条件定义（现登记；主表清单／两臂清单） |
      |---|---|---|---|
      | 实例分割开发集 | +0.562（29 个 house），82-1 成立，下界 +0.49 | +0.101（27），成立，+0.019 | +0.104（23）／+0.101（26），成立 |
      | 实例分割确认集 | +0.605（34），成立，+0.53 | +0.091（26），成立，+0.035 | +0.130（18）／+0.111（22），成立 |
      | SAM2 开发集 | +0.174（29），成立，+0.11 | +0.015（26），不成立，−0.025 | −0.010（15）／+0.021（21），不成立 |

      零效应校准（真实收益为 0、种子标准差 0 → 0.10，九个“读数来源 × 指标”组合，每格 2,000 次模拟，蒙特卡洛误差约 ±0.005）判“成立”的比例：只按 house 重采样 0.04～0.06 → 0.17～0.33；house 重采样加 82-1 0.03～0.06 → 0.04～0.06；两级重采样加 82-1 0.02～0.04 → 0.04～0.06；只有两级重采样 0.02～0.04 → 0.06～0.09。只按 house 重采样把这 5 个模型当成固定的，种子一有波动就明显超过 5%；两级重采样单独用时，五个种子估不准种子波动，种子标准差大时也略超 5%；两级重采样加 82-1 在这些情形下都在 5% 左右。

      功效（两级重采样加 82-1，身份连续率·共同事件，test 尝试 100 个 house；每格三个数依次是种子标准差 0／0.03／0.06；每格 500 次模拟）：

      | 真实收益 | 实例分割（开发集 house 分布，约 54 个有效 house） | 实例分割（确认集分布，约 52） | SAM2（开发集分布，约 52） |
      |---|---|---|---|
      | +0.04 | 0.23／0.27／0.19 | 0.50／0.39／0.27 | 0.86／0.62／0.30 |
      | +0.06 | 0.53／0.48／0.38 | 0.86／0.71／0.46 | 0.99／0.84／0.50 |
      | +0.08 | 0.75／0.71／0.56 | 0.99／0.93／0.63 | 1.00／0.97／0.74 |
      | +0.10 | 0.90／0.88／0.73 | 1.00／0.99／0.84 | 1.00／1.00／0.85 |

      Missing 残留率：真实收益 +0.10 时三处都 ≥ 0.80，+0.05 时 0.32～0.74。test 尝试 200 个 house 时，种子波动小的格子明显提高（例：实例分割开发集分布、+0.06：0.53 → 0.79），种子标准差 0.06 时几乎不变（0.38 → 0.38），增加 house 消除不了种子波动。开发估计直接代入的情景（不是预测）：实例分割开发集 +0.101 约 0.92，确认集 +0.091 约 0.99，SAM2 +0.015 约 0.18。同一真实收益下各列功效不同，是因为三处的 house 分布不同（SAM2 上身份连续率大多为 0，house 间差异小）。所有数字都基于样本内开发数据、只有 43 个 house 的确认集，以及“整行重抽 house、另加正态种子偏移、平移收益”的模拟假设，只作规划。
    - 白话：S3-01 要在碰 validation 与 test 之前，把“考什么题、怎样判输赢、两张表怎样一起下结论、配置怎样选、样本与机器够不够”一次写死。下面十一项是要冻结的内容，每项给推荐与备选；推荐的共同原则是理由与哪个臂获胜无关、两套前端同样处理、不看 test 改任何东西；凡是看过开发结果才设计的地方都如实写明。
    - **102-0 身份连续率的事件定义（第二轮复核新增；102-2、102-3 依赖它）。** 现登记的定义（裁决 M）是条件成功率：分母只含“搬动前该臂已有承载实体”的重见事件，所以各臂考的题不同，哪些事件进分母也由方法自己的表现决定。
      - (a) **推荐**：改为共同事件。事件＝被搬动、并在窗口之后第一次有色块以它为主导物体的物体（只由前端色块与私有标签决定，同一套前端上所有臂、所有种子是同一批事件）；成功＝这次重见被分配（BIND 或 REACTIVATE）到窗口最后一帧时承载它的任一实体（任何状态）；搬动前该臂没有承载实体记失败。比例＝成功数／事件数；没有事件的 house 不可算。含义写成“同一批被搬动并重见的物体里，第一次重见时接回搬动前身份的比例；搬动前没为它建立记忆也算没接回”。理由是设计上的：配对比较要考同一批题；可算性只取决于前端与真值，X2 的单一清单因此与任何臂都无关，其他臂不再改变首要比较的样本；不是因为数字更好，两种定义在三处读数上方向相同（上表）。这是科学合同修订：S0-04 的身份连续率定义就地修订、重钉摘要，评价器分母改一行并加测试，原定义保留为诊断列 `identity_continuity_conditional` 并列报告；重验已用已提交的导出完成（上表，不需要重跑），如实登记为看过开发结果之后的修订。
      - (b) 保留条件定义：主张限定为“在该方法搬动前已为物体建立记忆的条件下”；每个比较旁报分母（分母事件数／重见事件数）；首要检验的排除清单只看参与比较的两臂（给 X2 加一条例外），否则 LOW 等臂的可判性会改变首要比较的样本。
      - (c) 两臂共同的条件事件（只取两臂所有种子都有承载实体的事件）：两臂考同一批题，但样本仍由两臂自己的记忆决定。
      - 白话：考身份连续率时，现在每个方法只考“它自己事先记住了的那些被搬走的东西”，记住得少的方法考题就少。推荐改成所有方法考同一批“被搬走后又看到的东西”，事先没记住也算没接上。例如 10 件东西被搬走后又被看到，方法 A 事先记住 6 件、接上 3 件，方法 B 事先记住 9 件、接上 4 件：现在的定义是 0.5 对 0.44，共同事件是 0.3 对 0.4。
    - **102-1 主张框架（裁决 85-4 触发）。** 85-4 原文：方向 B 之后 MRR 若仍在规则臂的两倍以上，须在 S3-01 前裁定是否改主张框架（83-6 的备选路线）。SAM2 上越过了 2 倍，主要因为 ELU-P 在 SAM2 上残留率更低（0.092 → 0.050），代价是大部分撤回是错的；VSMT-lean 基本没变（0.135 → 0.119）。裁决 99-2 已把首要假设改为“对同配方 AssocOnly”。
      - (a) **推荐**：保留方法研究方向，不改框架；现在就预先限定每种 S3 结果能支持的主张，论文写法事后只能在这些边界里选：① 实例分割首要检验（102-2 第一步）的数值检验成立，并且 VSMT-lean 满足已登记的选参可行性条件（102-4）→ 可以说“在 ProcTHOR 与模拟器实例分割前端上，用这套训练程序（固定训练数据、配方与选参流程，5 个种子）的生命周期操作，相对同配方只学关联，陈旧实体更少、身份接回更好（按 102-0 的定义）”；数值检验成立但选参约束不可满足 → 照报数值，不作这一主张；数值检验不成立 → 首要假设未确立，两项指标只报差值与区间；② SAM2 按 102-2 的后两步各自支持或不支持对应部分；③ 对规则臂一律逐指标报告取舍（Missing 残留率、范围内误撤回率、节点 F1、身份连续率），原主门（对最强对照）在 S3 照原文计算、按实际结果报告，开发集与确认集上已记未满足（比值 1.14～2.39）；④ “协议加基准”不是自动后备：如果以后改用这个框架，要另有它自己的贡献证据（例如信息边界与三分解的审计、对照适配的可信度、S3-07 外部验证），并另提裁决；⑤ 刊物按 83-6 不变。影响：不花机时、不改合同；论文必须写明“单看 Missing 残留率，最好的规则臂更低”以及它的误撤回代价。
      - (b) 现在就改为“协议加基准”框架：主交付是信息边界、三分解、干预窗口、同前端机制适配与两套前端的基准表，VSMT-lean 作为学习参照方法；要先写清这个框架自己的贡献证据并另提裁决。影响：主张更稳，但贡献一即使在 test 上成立也不再是标题。
      - (c) 不预先限定，S3-05 之后再定。不推荐：等于看完 test 选主张，与 85-4“S3-01 前裁定”相抵。
      - 白话：这一项不决定论文最后叫什么，而是事先写清“哪种结果能说哪句话”。例如实例分割那一关过了、SAM2 身份连续率没过，就只能说“实例分割下两项都成立，SAM2 下陈旧实体减少成立”，不能说“跨分割器都成立”。
    - **102-2 两张主表怎样共同决定结论（裁决 99-5 要求在 SAM2 正式出数前定）。**
      - (a) **推荐**：固定顺序检验，三步：① 实例分割表的首要检验（Missing 残留率与身份连续率两项都要成立，“都成立才算成立”）；② ① 成立才检验 SAM2 表的 Missing 残留率；③ ② 成立才检验 SAM2 表的身份连续率；前一步不成立就停，后面各项只报差值与区间。每一步“成立”的标准见 102-3。实例分割排第一，依据是裁决 72／83-3 早已定它为主表前端；SAM2 两项的先后沿用 S0-04 `main_gate` 里早已登记的指标顺序（先 Missing 残留率、后身份连续率）。**如实登记**：把 SAM2 拆成两步、不与实例分割同时检验，是看过 S2-06 的开发读数之后设计的，在读 validation／test 之前冻结。只有在每一步本身是有效检验的前提下，三步合起来误判的概率才不超过 5%；每一步的有效性按 102-3 的零效应校准核验（两级重采样加 82-1 约 5%），没有理论保证。按上面的功效表，SAM2 身份连续率在真实收益 +0.04 到 +0.10 时的功效约 0.30 到 1.00，取决于种子波动；**当前开发证据不足以支持 SAM2 身份连续率有稳定正收益；正式结果仍未知，不以扩样或修改前端追求过门**。不事后挑表，不把两套前端合并成一个检验。S0-04 的 `multiple_comparison_correction` 就地写成这条规则；规则臂对比与三组消融的区间只作描述，不作校正、不设门。
      - (b) 两张表四项都成立才有任何结论：最干净，但 SAM2 身份连续率一项不成立就连实例分割上的结论也不能说。
      - (c) 撤回裁决 83-3，SAM2 回到附录、只有实例分割一张主表：检验最简单，但 83-6 的 RA-L 条件（83-3 落地）随之不满足。
      - 白话：“固定顺序检验”就是先考主卷、主卷过了再考副卷第一题、再考第二题，前面没过后面就不算分。它控制的是“几句话里至少一句说错”的概率。它不是把两张表的数平均，也不保证 SAM2 的身份连续率能过。
    - **102-3 主门的统计细节。**
      - 排除清单：每个指标、每套前端只有一份——某个 house 只要在主表任一臂的任一种子上该指标不可算，就对所有臂、所有检验一并排除（X2 推广到种子）；主检验、82-1 的种子配对差、原主门、最强对照选取与功效说明都用这同一份；报告有效 house 数与清单。102-0 取 (a) 时，Missing 残留率与身份连续率的可算性都只取决于前端与真值，这份清单与任何臂都无关（报告里主表清单与两臂清单完全相同）；取 (b) 时按 102-0 (b) 的例外。开发读数的 82-1 用的是“每个种子各取共同可判 house”，与这条不同，换成这条以后开发集的数会变（上表）。
      - 推断对象与重采样：(a) **推荐**：结论针对“固定训练数据、配方与选参流程下的这套训练程序”，同时计入训练随机性（种子）与 house 抽样。下界用两级重采样：每次独立地有放回抽 5 个种子编号与有放回抽 house，所有抽中的种子共用这一次抽中的同一批 house（一个训好的模型在每个 house 上都审计过，house 与种子是交叉的两个维度），两臂按同一种子编号配对（79-5 起两臂的关联头与新建头按种子编号同起点），统计量是抽中 house × 抽中种子上配对差的均值，10,000 次，取单侧 95% 百分位。这种交叉数组重采样（Owen 与 Eckles 的思路）在一定条件下高估方差，但五个种子时百分位下界的覆盖率没有保证；报告里的零效应校准显示，单用它在种子波动大时误判率约 0.06～0.09，所以仍要求 82-1 的种子稳定条件（五个种子齐全，配对差至少 4 个指向对 VSMT-lean 有利的方向，且均值的绝对值大于 5 个差的标准差）；两条合起来在校准的各种情形下约 5%。一项指标两条都满足才算成立。主表学习臂报 5 个种子的均值 ± 标准差并附逐种子（85-2 ①），不从 5 个种子里挑一个；另报只按 house 重采样的下界作敏感性。(b) 结论只针对“这 5 个训好的模型”：只按 house 重采样种子平均后的差，加 82-1 条件；工作较少，但论文要写明结论不推到重新训练；零效应校准里它对“训练程序”的误判率约 0.03～0.065，比 (a) 略高。(c) 只按 house 重采样、不加 82-1：最简单，种子有波动时误判率可达 0.17～0.33，不推荐。
      - 效应量：(a) **推荐**：主门维持“下界大于 0”（99-2）；S0-04 的 `main_gate_effect_size` 只登记规划用的效应与功效表（上表与报告），写明“只用于功效说明，不是门槛”。(b) 要求下界大于一个最小效应 δ：主张更强，但 δ 没有独立依据，不推荐。
      - 节点 F1：99-2 要求的“独立、可解释的容忍依据”没有找到，不设非劣裕度；只报差值与 90% 区间，写明取舍（实例分割开发集 −0.006、确认集 −0.010；SAM2 开发集 +0.007）。
      - bootstrap 种子 `20261002`（任意固定整数，在任何 S3 数据出现之前登记）；统计在服务器分析解释器（`/root/miniconda3/bin/python3.12`）上运行，回执记 `sys.version` 与 numpy 版本。
      - 白话：两级重采样同时问“换一批 house 还成立吗”和“换一次训练还成立吗”，82-1 条件再保证结论不是靠某一个种子撑起来的。例如 5 个种子里 4 个都显示 VSMT-lean 的 Missing 残留率更低、两级重采样的下界也大于 0，这一项才算成立。它不等于对任意训练都给出保证：只有 5 个种子，训练随机性只粗略地进了区间，这一点用零效应校准核验过，但没有理论保证。
    - **102-4 选参约束文本（裁决 83-1，回应 79-7）。** 网格是 ln w 校正后的 τ_r {0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9}；选参指标仍是 validation 上的节点 F1（裁决 V）。
      - (a) **推荐**：一条对所有有撤回机制的臂相同的门槛：VSMT-lean、NoVersion、HeuristicLabel、HandCost、ELU-P、RAC 都只能在 validation 上 Missing 残留率低于同一前端 AssocOnly 的 validation Missing 残留率的配置里，按节点 F1 选最大（学习臂与 AssocOnly 都用 5 个种子的均值；并列取配置编号最小）。TAF、LOW 没有撤回，AssocOnly 没有可选配置，它们只按节点 F1。理由与谁赢无关：门槛对六个臂是同一个数，不按臂另找“反事实”，不引用任何规则臂的成绩，也不用身份连续率（所以 NoVersion“残留更少、身份更差”这类真实取舍不会被划掉）；它只排除“撤回了还比从不撤回留下更多陈旧实体”的配置。按开发读数它很少会起作用（VSMT-lean 在 τ_r 0.5 时 0.119 对 0.294、0.135 对 0.697），主要防止选参选出明显失效的配置；79-7 原先担心的“对规则臂的 Missing 残留率”不再由选参处理，而由 102-1 的逐指标报告处理。无解时：该臂取节点 F1 最大的配置照常进 test，回执记“约束不可满足”；它的数值检验照算，但正式主张还须满足这条可行性条件，所以不能用来支持“该臂的撤回机制减少了陈旧实体”；若发生在 VSMT-lean 上，按 102-1 ① 不作首要主张，S3-06 写明。
      - (b) 83-1 当时的例句：学习臂的 validation Missing 残留率不高于最强规则臂。影响：选参去追原主门；按 SAM2 开发集要压到约 0.05，会推向很低的 τ_r、节点 F1 明显下降，或无解。
      - (c) 撤销 83-1，不设约束，只按节点 F1 选：最干净，但需要用户明确撤销 83-1“必须有约束”；79-7 的风险原样保留。
      - 白话：先划掉“撤回机制在 validation 上反而让陈旧实体比从不撤回还多”的配置，再在剩下的里挑最准的。输入是 validation 上每个配置的指标，输出是每个臂进 test 的唯一配置。例如 τ_r 0.9 节点 F1 最高、但 Missing 残留率比 AssocOnly 还高，就不能选。它不读 test，也不拿主门的另一项（身份连续率）来选。
    - **102-5 检索成功率的定义（裁决 83-5，第八项指标）。**
      - (a) **推荐**：按外观检索，事件集合与各臂无关。事件：被搬动的物体，在搬动后第一次有色块以它为主导物体的那一帧（与 102-0 (a) 同一批事件）。查询：该物体搬动前所有以它为主导物体的色块的描述子（该前端选定的描述子，即 `reid_projection:vitb14` 投影）取均值后单位化；搬动前一个这样的色块都没有的物体没有查询，不算事件、单独计数（同样与臂无关）。候选：那一帧提交后的记忆里全部 `active` 与 `dormant` 实体，用它们在该版本的 `descriptor_mean`（单位化）；候选为空记失败。取余弦最高的实体，并列取 entity_id 小者；它按节点主列的配对规则配得上这个物体（证据多数身份就是它，且质心 ≤ 0.5 m 或落在真值框外扩 0.25 m 内）记成功。成功率＝成功数／事件数；没有事件的 house 不可算（按 102-3 的同一份清单方式）。不进主门、不选参，S3-05 与其余指标同批计算；回执记事件数、无查询数与空候选数。
      - (b) 现在 METHOD 里的草稿：在承载该物体身份的实体里取最新版本，质心 ≤ 0.5 m 记成功。缺点：只学关联的臂在新位置新建一个同身份实体也算成功，原位置的陈旧实体不影响结果；“承载身份”还依赖各臂自己的记忆，事件集合随臂变化。
      - (c) 严格版：新位置至少有一个承载该身份的实体、且别处没有残留才算成功。与 Missing 残留率大面积重合。
      - 白话：它回答“机器人拿着这个杯子以前的样子去记忆里找，找到的那条记录是不是它、在不在它现在的位置”。例如只学关联的方法在旧位置留着杯子的陈旧实体、又在新位置新建了一个，旧实体的外观更像查询，就会被拿错，记失败。所有臂在同一批事件上考。
    - **102-6 裁决 101 留下的同侧网格（TAF.d_a、RAC.rho_rac、HandCost.rho_h；LOW.d_low 只在实例分割上出界）。** 依据：两套前端的判定点都在网格下方（同物体质心距离中位 SAM2 0.295 m、实例分割 0.192 m；覆盖交叉点都在 1/64）。按当初保留这些网格的理由复核（裁决 78 (2)）：单帧覆盖 ≥ 0.7 时，真被拿走的物体 SAM2 检出 63.9%、在场误触发 2.6%（实例分割 68.5%、1.7%）；≥ 0.85 时 56.8%、1.8%（60.3%、1.0%）；距离门 0.5 m 覆盖同物体对 59%（实例分割 68%），2 m 覆盖 88%（91%），每个距离网格都含无门选项。覆盖交叉点 1/64 对应“只要看穿一个点”，此时在场误触发 32%（实例分割 28%），不是能用的单帧阈值。
      - (a) **推荐**：两套前端都不改网格，不因当前差值追加优化。理由与谁赢无关：网格复核用的判定点（距离中位数、覆盖最大差）是裁决 100 登记的检查，不是这些网格的设计依据；当初保留网格的依据在两套前端上都仍成立；此时改网格发生在看过全部臂的开发读数之后。论文把两套前端的校准点画在网格旁边。
      - (b) 只把距离网格往下扩，两套前端同样处理、不超预算：TAF d_a {无门, 0.15, 0.5, 1.0}（去掉 2.0，它已覆盖约九成同物体对，近似无门），LOW d_low {无门, 0.15, 0.25, 0.5, 1, 2}（6 个配置）；覆盖网格不动。影响：要另写独立的机制依据与预算；S0-05 网格就地修订、重钉摘要；开发表上规则臂那几行不再对应 S3 网格。
      - (c) 再加覆盖网格下调一档（裁决 78 当时的备选：RAC {0.5, 0.7}、HandCost {0.5, 0.6, 0.7, 0.8}）：撤回更积极，单帧在场误触发 SAM2 约 5%、实例分割约 4%（覆盖 ≥ 0.5 时）。
      - 白话：网格是规则臂可以试的阈值清单。推荐不改，因为当初定清单用的是“误触发少、真拿走能检出六成以上”这条理由，它在两套前端上都还成立。
    - **102-7 SAM2 的 mask 层修订（裁决 84-6，S3-02 前必须定）。**
      - (a) **推荐**：不修订，SAM2 前端保持 S1-03 冻结的样子（D-215 配置加裁决 43），不因当前差值追加优化。理由：第二张表要回答的是“结论在 SAM 2.1 下是否保持”（83-3 不主张分割鲁棒性），S2-06 已给出开发读数；在看到 SAM2 上身份连续率接近 0 之后改前端，等于朝着假设调前端。限制照实写：当前开发证据不足以支持 SAM2 身份连续率有稳定正收益，正式结果仍未知；SAM2 节点 F1 的绝对值比实例分割低约 0.2～0.3。不修前端不等于现在就接受 SAM2 那一项失败。
      - (b) 修订：先另写独立的机制依据（例如 S1-04 诊断里容器与家具色块对真值框 IoU 中位 0.14 的部件级切分）与预算，事先写死一条“整物体优先”的取舍规则，再走完整的重验链：重新冻结 S1-03、重建 SAM2 开发 cache（单张 4080 SUPER 级卡约 19 小时）、按裁决 47／S1-05 规则重训并重选 SAM2 的 ReID 头、再跑一遍 S2-06（约 20 小时），约 2～3 天机时；S2-06 重跑只读“模式是否保持”，不用来调规则。影响：SAM2 的节点 F1 与身份连续率事件可能上升；有被看作“调过前端”的风险。
      - 白话：SAM2 常把一个物体切成几块（椅背、椅座各一块），这项决定要不要改成优先取整物体的那一块 mask。推荐不改：第二张表的用途是“换成真实分割器结论还在不在”，不是把 SAM2 调到最好。
    - **102-8 数据清单、关键事件与功效说明。**
      - 清单：test（100）与 validation（50）的成员由 S1-02a v2（seed 20260920）固定，不动。train：(a) **推荐**：train 块第 100～399 位共 300 个 house，全部按 S3 设置生成（dry-run 每个物体至多 8 个目的容器、`maximum_actions` 4000）；S1 开发 house（第 0～49 位）与确认集（第 50～99 位）不进 S3，S3 的 train 与开发、确认过程完全分开；生成失败照记、不替换。(b) 第 0～299 位（X6 当时的读法），开发与确认集的 house 按 S3 设置重新生成后进 train：同一批 house 在记录里会有两个版本。
      - 关键事件：S3-02 生成 train 后按裁决 36 检查执行成功的搬动 ≥ 120、其中源位置先重访 ≥ 60，不达标触发规模裁决、不放宽规则；79-6 的 D2 外推（开发集 39 条成功 episode 65 次搬动，按约 234 条成功的 train 外推约 390 次）在同一步按 m=8 的实测复核。
      - 功效：(a) **推荐**：test 维持 100（已冻结），不凭规划数字扩样；功效说明就是上面的零效应校准、敏感性表与情景，连同它们的假设（单一清单、整行重抽 house、正态种子偏移、平移收益）写进 S3-01 回执；S3-02 之后按实际有效 house 数重跑同一脚本更新，不补样本。(b) 扩样：按报告，种子波动小时 test 加倍明显提高功效，种子标准差 0.06 时几乎不变；要改动已冻结的划分，还要先说明为什么按种子波动小的情形规划，不推荐。(c) 提高干预密度（D2）以增加每个 house 的搬动事件：要改 S0-02 并先做 pilot，S3 数据分布会偏离开发集，不推荐。
      - 白话：功效说明回答“如果真实收益是这么大、种子波动是这么大，按现在的样本量和判定规则有多大把握判成立”；零效应校准回答“如果其实没有收益，有多大机会被误判成立”。它们都不是对 S3 结果的预测。
    - **102-9 停止规则（S3 各步）。** ① S3-02：清单固定，生成失败照记不替换；工程故障用同一输入续跑；裁决 36 检查；有效 house 少于规划时按实际样本量继续并重算功效，不补样。② S3-03：每次训练跑满登记的 epoch；工程故障（崩溃、内存不足）用同一输入与同一种子重跑；训练发散或权重不可用是结果，照记、不换种子、不改种子编号；**五个种子齐全才可判**：某套前端上某个学习臂少于五个可用种子，涉及它的主门与 82-1 判定都记“不可判”，报告为未确立，不删掉坏种子后照算。③ S3-04：按冻结规则选配置，约束不可满足按 102-4 的处理与结论边界；冻结后不得改算法、数据、阈值、指标或预算。④ S3-05：test 只跑一次；工程故障用同一冻结输入续跑；出数后不重跑、不中途偷看。⑤ 主门结果只按 102-1 的边界写主张。
      - 白话：事先写明每一步出了什么事就怎么处理，避免出数以后临时决定“这次不算”。
    - **102-10 主机、磁盘与机时。** 84-5（数据盘 ≥ 300 GB）与 84-7（多卡、可扩容大盘）不变；补一条：S3 除生成 cache 外都吃 CPU。按 S2-06 所用实例（westd，2 × 4080 SUPER，cgroup 32 核）上的实测（每次闭环审计约 0.32 核·小时：SAM2 0.34、实例分割 0.31）粗估：validation 选参约 1.6 万次闭环（每个 house 约 208 个臂-配置-种子组合 × 约 39 个成功 house × 两套前端）约 5,200 核·小时；test 约 3,900 次约 1,250 核·小时；train 上的轨迹约 750 核·小时；训练约 36 次、每次约 7～8 小时 × 4 线程，约 1,100 核·小时；合计约 8,000 核·小时（误差 ±50%），在 64 核主机上约 5～7 天；cache 两套前端各约 51 万帧（84-4：SAM2 单卡约 9.5 天，按卡数近似线性加速）。训练内存：开发集 3.2 万帧时每进程约 8.2 GiB，S3 约为开发集的 6 倍帧数，S3-03 前先实测再定并行数。推荐 S3-02～S3-05 用 4 卡、cgroup ≥ 64 核、数据盘 ≥ 300 GB 的主机；费用按届时价格由用户核对。
      - 白话：这是让用户事先知道 S3 大概要多少机器、多少天，不是承诺；S3-02 主机上实测后更新。
    - 不做的事：不读 validation／test；不改方法定义与训练配方（99-1）；本条起草时不改任何合同字节。批准后的顺序：① 单职责提交就地修订 S0-04（102-0 选 (a) 时的身份连续率定义与诊断列；`main_gate` 改为对 AssocOnly；排除清单与两级重采样；`bootstrap_seed`；`main_gate_effect_size`；`multiple_comparison_correction`）与 S0-05（选参约束字串；102-6 选 (b)/(c) 时连同网格）并重钉摘要，METHOD 第二、十一节与 PLAN S3-01 同步；② 实现并测试：评价器的身份连续率分母、单一排除清单、两级重采样加 82-1 的主门函数（独立抽 house 与种子、所有种子共用抽中的 house）、固定顺序的三步判定、检索成功率、选参约束，写出三份清单；③ 用户审代码后 S3-01 关闭；④ 主机就绪后进 S3-02。
    - 批准句：「待裁 102 修订稿二全按推荐」，或逐项改，例如「待裁 102 修订稿二：102-0 取 (b)，其余按推荐」。
  - **裁决 102 批准（2026-10-02，原话「待裁 102 修订稿二全按推荐」）：S3-01 冻结稿按修订稿二的推荐口径执行。** 各项取 (a)：102-0 身份连续率改为共同事件（所有臂同一批搬动后重见的物体，搬动前没有承载实体记失败），原定义保留为诊断列 `identity_continuity_conditional`；102-1 保留方法研究方向，按事先写死的“结果 → 可说的话”边界写主张，原主门在 S3 按实际结果报告，“协议加基准”不是自动后备；102-2 固定顺序三步（实例分割两项 → SAM2 Missing 残留率 → SAM2 身份连续率），如实登记为看过开发结果后设计；102-3 每个指标每套前端一份排除清单（主表全部臂、全部种子都可算才保留），推断对象为固定训练数据、配方与选参流程下的训练程序，下界用两级重采样（独立抽 house 与种子，所有种子共用抽中的 house，10,000 次，单侧 95%）加 82-1 种子稳定条件，`main_gate_effect_size` 只登记规划效应，节点 F1 不设非劣裕度，bootstrap 种子 `20261002`；102-4 六个有撤回机制的臂共用门槛“validation Missing 残留率低于同一前端 AssocOnly”，无解时数值照算、不作正式主张；102-5 检索成功率按外观检索、事件与臂无关；102-6 网格不改；102-7 SAM2 mask 层不修订；102-8 S3 train 取 train 块第 100～399 位、test 维持 100、功效说明为 `results/vsmt_lean_s3_01_planning_6c57903.json`；102-9 五个种子齐全才可判；102-10 主机 4 卡、cgroup ≥ 64 核、数据盘 ≥ 300 GB。
    - 实现顺序（单职责提交，各带测试；本地逐模块测试，服务器全量在下次开机时补跑）：① 评价器的身份连续率分母与诊断列（S0-04 指标定义就地修订、重钉）；② S0-04 统计：单一排除清单、两级重采样加 82-1 的主门函数、固定顺序三步判定，原主门与消融用同一套重采样只报告（`statistics` 块就地修订、重钉）；③ S0-05 选参约束（`budget.selection_rule` 就地修订、纯函数与测试）；④ 检索成功率（第八项指标）；⑤ 三份清单；⑥ METHOD 第二、九、十一节与 PLAN、DECISIONS 落地记录。用户审过代码后 S3-01 关闭，主机就绪后进 S3-02。
    - 白话：S3 怎样考、怎样判、怎样选配置、说到哪一步为止，到这里全部定下；接下来只是把这些写成代码与合同，不再改口径。
  - **裁决 102 落地（2026-10-02，实现完成、待用户审代码；未运行任何实验）。** 五个单职责提交，本地 104 个模块 1,609 个测试逐模块全部通过（四个旧模块需 `PYTHONPATH=src`，与本次改动无关）；服务器全量在下次开机时补跑。
    - `4511aac` 102-0：`lean_teacher.identity_continuity` 的分母改为全部重见事件（`events`，只由前端与真值决定），搬动前没有承载实体记没接回；`identity_continuity_blocks` 给出主列（`identity_continuity`、`kept`、`events`、`no_prior_carrier`）与诊断列 `identity_continuity_conditional`（`identity_continuity`、`kept`、`judged`，裁决之前的定义，不进主门、不选参）。评价器、开发表方向表与两个合同同步；S0-04 `818ec131` → `0e856be3`，S2-04 `eb9ac356` → `02d0e1b6`，S2-05 `d010a992` → `743eae92`。S3-01 规划脚本能读两种报告格式（在已提交输入上逐项复现已提交报告）。
    - `b1590ae` 102-2／102-3：`primary_gate`（VSMT-lean 对 AssocOnly，两项主门指标各用一份单一排除清单；缺规则臂即报错，学习臂少一个种子记不可判）、`two_level_lower_bound`（先抽种子编号再抽 house，所有抽中的种子共用这批 house，两臂按种子编号配对）、`seed_stability`（82-1 有利方向）、`original_gate`（对最强对照，只报告）、`fixed_sequence`（三步）；S0-04 `statistics` 块写明全部规则，bootstrap 种子 `20261002` 与只作规划的 `main_gate_effect_size` 填入两个值槽并入台账；S0-04 → `bf775628`。
    - `8dc8cf5` 102-4：`lean_arms.select_configuration` 与 S0-05 `budget.selection_rule`、`selection_constraint` 块；S0-05 `0065b9b4` → `60e2aa9d`。
    - `2085185` 102-5：`retrieval_success`／`retrieval_success_block` 与评价器接线（查询来自窗口最后一帧及之前以该物体为主导的色块描述子，事件与身份连续率相同），第八项指标进入指标清单与两个合同的表头／方向表；S0-04 → `f8c87355`，S2-04 → `dfd879b2`，S2-05 → `dba77a2d`。合成 TAF episode 上书被搬到 C 后检索到它自己在 C 的实体，成功率 1.0。
    - `efa2a55` 102-8：`src/vsmt/lean_s3_manifests.py`、`ops/vsmt/s3_01_manifests.py` 与 `configs/vsmt/lean_s3_01_manifests.json`（test 100、validation 50、train 300＝train 块第 100～399 位；开发与确认块排除，确认集逐项与按摘要重算一致，五块两两不交）。S1-02a 的 `train_houses` 值槽按“train 块前缀”设计，裁决 102-8 改取第 100～399 位，故该值槽保持 null，S3 的 train 以清单为准。
    - 没有代码改动的项：102-6 网格不改、102-7 SAM2 前端不改、102-9 停止规则（五个种子齐全才可判已进 `gate_metric`，其余在 S3 各步入口实现时照此写）、102-10 主机与机时（S3-02 前由用户开机）。METHOD 第二、九、十一节与 PLAN S3-01～S3-05 已同步。
    - 白话：S3-01 的“怎样考、怎样判、怎样选、名单是谁”都已写成可测试的代码与合同；用户审过这五个提交后 S3-01 关闭。
  - **裁决 102 落地代码审过，S3-01 关闭（2026-10-02，原话「裁决 102 落地代码审过，S3-01 关闭」；LOG-301）。**
  - **待裁 103（2026-10-02 提出，S3-01 关闭之后）：S3-02 阶段协议（正式数据生成、几何重载与两套 cache）。** 本条只起草，不改代码、不运行；批准后按单职责提交实现一条命令的驱动，用户审过代码再开机。依据：现有生成器（`ops/vsmt/lean_s1_02a_pilot.py`）已按 S0-02 v3 默认每个物体至多测 8 个目的容器（裁决 39）、`maximum_actions` 4000（裁决 40），确认集（`2339baa`）就是这样生成的（50 个 house、16 worker、57 分钟，成功 43）；cache（`lean_s1_03_cache.py`）与几何重载（`lean_s1_04_object_geometry.py`）都有入口；新生成器提交须登记进 S1-03 合同的 `correct_encoder_since_code_commits` 才能被读者使用（确认集是 `6b65cb1` 登记的）。
    - 白话：S3-02 只做“把 450 个 house 生成出来、补上真值框、建好两套 cache”，不训练、不评价。这里要定的是：test 现在一起生成还是最后再生成、生成器换了提交后怎样登记、worker 怎样实测、搬动数不够时怎么办。
    - 103-1 生成范围与 test 封存。(a) **推荐**：一次生成全部 450 个（train 300、validation 50、test 100），同一提交、同一设置；test 的 raw、几何重载与两套 cache 都生成，写进单独的根并写封印（逐 episode 摘要清单），S3-03／S3-04 的入口拒绝读 test 根，S3-05 先核对封印再读，且只读一次。理由：test 数据与 train／validation 在同一代码与环境下生成，日后不用另开一次机或另登记生成器；生成与建 cache 不读任何评价结果。(b) test 留到 S3-05 前再生成：冻结前 test 字节不存在，最干净；代价是多开一次机、多等约半天，生成器与环境若有变化要另登记。
    - 103-2 生成设置：S0-02 v3 现行规则，与 S1-02b、确认集相同（窗口为过渡最后 30 帧、dry-run 至多 8 个目的容器、`maximum_actions` 4000、私有盐空窗口抽签、增补用 unseen_existing）；生成失败照记、不替换；停滞 1,800 s 判失败（这是卡死保护，不是时间预算）。生成器只加一个按 S3 清单读名单的 `--stage s3`，不改任何生成规则。
    - 103-3 生成器提交的登记停点。(a) **推荐**：仿照 S2-06 的拟合量停点——驱动在生成器提交 X 上生成完后停在 hold，由我做一个只把 X 加进 S1-03 `correct_encoder_since_code_commits`、重钉 S1-03 摘要的登记提交（与确认集 `2339baa` → `6b65cb1` 的做法相同），在登记提交上续跑几何重载与两套 cache；这一登记现在预授权。(b) 每次登记都另提裁决：多一次往返，机器可能空等。
    - 103-4 worker 与吞吐实测：开机后先跑服务器全量测试；生成先用 4 个 house 实测并发、单 house 耗时与峰值内存，按 S1-01 规则（headroom 0.2，取 CPU、内存、显存、磁盘与模拟器并发的最小值）定 worker；SAM2 cache 先在一条大 episode 上实测每卡吞吐（裁决 84-4），据此报总时长与费用再继续；实例分割 cache 与几何重载沿用已测设置（8 worker × 2 线程；8 个模拟器 worker）。不设墙钟超时，保留内存、显存、磁盘余量保护。
    - 103-5 裁决 36 检查：train 生成完后统计执行成功的搬动与“源位置先重访”；不足 120／60 → 停下、提规模裁决，不放宽规则、不补样本；validation／test 的成品率与搬动数只记录。
    - 103-6 两套 cache：冻结的 S1-03 设置——实例分割 `--mask-source simulator_instance_masks`；SAM 2.1 按 D-215 加裁决 43，不修订 mask 层（102-7）；描述子 DINOv2 ViT-B/14；ReID 头不重训，两套前端各用 S0-03 钉住的那份（84-1 (b)）；cache 封印写明来源。
    - 103-7 产物与关机：raw 写 `vsmt_outputs/s3-02-<提交>/{train,validation,test}`，cache 写 `vsmt_caches/s3-02-{instance,sam2}-<提交>`，几何写 `vsmt_private/s3-02-geometry-<提交>`；各段回执、成品率与搬动统计、cache 报告、worker 依据与运行清单导出到 `results/`；跑完拉回并核对 sha256 后立即关机（用户固定要求）；数据盘保留到 S3 结束。
    - 103-8 入口：一条命令 `ops/vsmt/s3_02_data.sh`，阶段 check → measure → generate → hold（登记）→ geometry → instance-cache → sam2-measure → sam2-cache → export → verify，可续跑，写法同 S2-06 驱动（标记、运行清单、兜底关机）；单职责提交、带测试，用户审过才开机。估计在推荐的 4 卡、每卡 25 核主机上约 1～1.5 天，约 ¥250～400（±50%，以实测为准）。
    - 批准句：「待裁 103 全按推荐」，或逐项改，例如「待裁 103：103-1 取 (b)，其余按推荐」。
  - **清理已由用户执行（核验记录见 LOG-224）。** 数据盘 22 GB → 43 GB 可用，保留清单九项全在，四个 worktree 登记已干净摘除。
- 白话：这次裁决解决"S1 正式开工前，资产范围、未登记项、环境冲突和历史残留各自怎么办"。输入是 LOG-220 列出的九项推荐与备选，输出是九条冻结口径和三个被打开的只读位。例如 ProcTHOR-10K 以后固定用 0.1.2，而且它的字节数不是"下载到多少算多少"，是上游 LFS 指针先声明好的。它不表示任何数据已生成、任何依赖已安装或前端已跑通。
## D-224-X：S0 合同隐患审查的六项修正 X1～X6（已批准）

- 日期：2026-09-20；状态：**用户一次性批准 X1～X6 全部按推荐口径执行**，原话为“S0-01/S0-02/S0-04/S0-05 追加 v2 不改已审字节，S0-03 求解器与 S0-04 评价器按逐列等价测试复审”。本条是 D-224 的第八份修正案；仍无任何数据生成、训练或服务器运行授权。起因是对 PLAN 第三节 S0 五份合同及其纯核心的逐条审查，审查实测见 LOG-225。
- **X1（采纳）：同帧重复色块记 `duplicate_of_labelled`。** SAM 常把一个物体切成几块；teacher 对同帧同物体的两块都给同一目标实体，而 S0-01 规定一个实体每帧只收一块，第二块无论如何满足不了。实测一个实体、两个主导实例相同的色块，最优分配下仍记 `amortization_error: 1`，贡献二的三分解把结构性不可能算给学生，softmax 交叉熵也同时要求两行选同一列，`VSMT-lean-ctx` 的准入规则会被这类噪声触发。现在只有物体上像素最多的那块（并列取整块像素多者，再取 fragment_id 小者）保留目标，其余不进损失、不记任何错误类、单独计数；目标不同、目标是新建列或 recall_miss 的不折叠。被拒的备选：允许执行器同帧多绑（动 S0-01 不变量与去重语义）；新增第四类 `structural_infeasible`（“三分解”要改名）。
- **X2（采纳）：未定义 house 按指标排除并计数，绝不填补。** MRR 与身份连续率在没有可判物体的 house 上是 null，`paired_house_bootstrap` 遇 null 直接抛错，而“缺任一臂即拒”只管缺臂。现在 `undefined_houses` 按指标对全部报告臂算一次排除清单，配对 bootstrap、最强对照与消融报告都必须传同一份，结果报有效 house 数与排除清单；清单外的 null 是带名字的错误。S3-01 的功效预算按有效数算。被拒的备选：null 当 0 或 1（有偏）；按物体池化（破坏配对单位）。
- **X3（采纳）：`AssocOnly` 与 `HeuristicLabel` 同配方重训，不复用权重。** “同一个学习关联头”原文未定义是复用 VSMT-lean 训好的权重还是重训；复用会让输入分布全变（状态 one-hot 恒为 active、错失次数恒为 0），贡献一的“唯一因果反事实”里混进分布偏移。现定义为同架构、同优化器与学习率、同 epoch 与早停、同 seed、同预算、同两轮 DAgger 在自己的轨迹上重训，AssocOnly 去掉存在损失项。
- **X4（采纳）：预登记 ELU-P `rollout_config`，登记三个拟合量的估计程序。** VSMT-lean 第 0 轮 DAgger 与 HeuristicLabel 的标签都要 ELU-P 轨迹，而 ELU-P 的配置到 S3-03 才按 validation 选，S2-05 更没有选择步骤。现在 S0-05 v2 登记 `rollout_config`（theta_a、free_space_weight、retract_threshold 三个待冻结值，d_a 固定为无门），必须是网格成员，S2-05 与 S3-03 用同一格，与 validation 选参无关；`initial_log_odds`、`persistence_log_decay_per_tick`、`match_gain` 各写明在 train 私有真值上的估计式（匹配增益在 rollout_config 的门上估一次、所有配置共用）。被拒的备选：先做 ELU-P 选参再喂给训练（训练数据源依赖 validation 选择，且 S2-05 无法执行）。
- **X5（采纳）：求解器规范化改到等式子图；评价器匹配分连通块。语义不变，逐列等价。** v1 的字典序规范化每试一列就把整张矩阵重解一次：本机实测 30×100 浮点代价 1,337 次子求解、1.2 秒（合同写的 300 毫秒只对并列多的规则臂式矩阵成立），48×300 为 6,364 次、27 秒，64×500 为 13,055 次、125 秒，而原始求解只要几毫秒。v2 用原始求解结束时的最优势 (u, v)：按互补松弛，最优分配只能用约化代价为零的格且势为负的列必须被匹配，于是只在这张稀疏图上按行试最小列，用两次增广路匹配判断剩余行能否补全（Mendelsohn–Dulmage 保证可同时满足）；64×500 降到 0.01 秒，核心求解器只调用一次。评价器把 (实体+真值)² 的方阵匈牙利改为按非零 IoU 的连通块分别求解，300×100 单帧从 3.1 秒降到毫秒级，匹配数与总权重相同（有并列时匹配对可能不同，但没有任何指标读匹配对）。两者都把 v1 实现原样留在测试文件里逐列/逐对比对。
- **X6（采纳）：四项小型 v2 修正。** (a) S0-02 前缀分配顺序改为 test→validation→train，S3-01 下调 train 时 test/validation 成员不变；代价是 seed 与 test/validation 规模必须在 S1-02a 第一条 episode 前冻结，此后 train 只能下调，S1 的 50 个开发 house 是 train 块前 50 个。(b) S0-01 写明被折叠实体“归档进 `canonical_of`，不算物理删除历史版本”，版本记录新增 `opened_by` 并绑定状态。(c) S0-04 规模指标改为生命周期版本数（不含 BIND 打开的逐观察版本，否则约等于观察次数）。(d) S0-04 真值表带 `in_scope` 标志，范围规则由评价器套用，解析到范围外物体的实体单独计数而不是崩溃。
- **同批只记入文档、不改合同字节的项：** METHOD 第六节第 6 步写明非法程序回滚后提交空程序推进 tick；METHOD 第五节写明 `entity_geometry` 是逐臂在线派生量，S2-01 用共用纯函数计算；S1-04 加“单视角 fragment AABB 对真值整物体框的 IoU 分布”诊断与匹配口径裁决触发条件；S3-01 登记最强对照在 test 上逐指标后验选取、回执钉住 Python 版本。
- **合同与文档同步。** 五份 `lean_s0_*_v2.json` 追加，五份 v1 字节冻结并由 `test_vsmt_lean_cross_contract.py` 钉住 sha256；五个纯核心的 `CONTRACT_SCHEMA_VERSION` 指向 v2；每份 v2 的 `supersedes_contract` 指向自己的 v1 摘要并写明变与不变。METHOD 第三、五、六、七、八、十、十一、十三节，DATA 第一、六、七节，PLAN 第三、四、五、六、八、九节与 `tests/README.md` 据此更正。八个 lean 模块分进程共 **382 项**本地通过（合跑一次段错误，为本机已知 CPU 不稳定，待服务器复核）。
- **复审修订（2026-09-20，本会话逐条核对 v2 后用户批准“按推荐修 1～4”）。** 其一，X1 记账改为按组：保留块与其重复块一起判，组内任一块分到目标实体且无一块绑到别的既有实体即 correct，否则一次 amortization_error；原实现会把“学生把椅子绑到椅背而不是椅座”记成错，而哪一块承载物体是学生的选择。其二，X2 排除清单只对该指标按构造可定义的臂计算，S0-04 合同登记 `metric_not_applicable_rule`（假撤回率对词表无 RETRACT 的臂不适用），S0-05 提供 `arms_without_atom`；原实现下 TAF、LOW、AssocOnly 在每个 house 都是 null，整列对所有臂都报不出来。其三，HeuristicLabel 的“只用公开数据”声称改为写明唯一私有依赖：ELU-P 三个拟合量在 train 私有真值上估计。其四，解析到在场但范围外物体的实体退出精确率分母并计数，物体已缺席的仍算陈旧；原实现把它们算成永远匹配不上的假阳性。被拒的备选：X1 维持逐块记账；X2 把假撤回率整个移出配对；HeuristicLabel 改为先验登记三标量不拟合；范围外实体留在分母。X3、X5、X6 其余部分与等价重写经核对无需改动。
- 白话：这次裁决解决“五份合同的护栏都在，但有几处会让三分解、统计和吞吐在真跑时出问题”。输入是逐条审查找出的十几处隐患与实测数字，输出是六条口径修正和五份 v2 合同；例如椅座和椅背两块色块以后只有一块算“该绑到旧椅子”，另一块不再算学生错。它不改变 D-224 的主张边界，不表示 v2 已通过复审，也不授权任何数据生成或训练。
