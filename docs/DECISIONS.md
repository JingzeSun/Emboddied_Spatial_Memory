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
