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
