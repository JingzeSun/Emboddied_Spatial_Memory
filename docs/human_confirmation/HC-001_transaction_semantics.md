# HC-001 Transaction Semantics

- 状态：confirmed
- 当前阶段：M0
- 已确认：PRESERVE/ASSOCIATE/EXPAND/REVISE 两级层级；REACTIVATE 模板；REPLACE=RETRACT+BIRTH；QUARANTINE 不修改 world，并保留可检索的暂定认知。

## 已确认切片：身份生命周期（2026-09-05）

- identity lifecycle 固定为 candidate、confirmed、dormant、retracted、alias；
- 版本关闭只由 valid_to 表示，不使用 lifecycle=closed；
- BIND 只能指向 candidate/confirmed；
- REACTIVATE 只能指向 dormant；
- retracted 不可直接 REACTIVATE；重现时使用 BIRTH/REPLACE，错误撤回则显式回滚原事务；
- executor 不隐式把 candidate 升为 confirmed，升级必须由 program 显式请求。

该切片由研究者确认并记录为 D-019。HC-001 的其余条目仍需后续 fixtures 决定，因此整个 HC 尚未关闭。

## 已确认切片：确认与休眠（2026-09-05）

- BIRTH 只产生 candidate；
- candidate 至少有两条不同 evidence IDs 后，BIND 才可显式升级为 confirmed；
- 两条 evidence 是否构成独立视角由 observation pose/view metadata 判断，数值阈值在 M2 validation 冻结；
- confirmed→dormant 是确定性维护，不参与 CTL 候选竞争；
- 连续 K 步未观察可触发 dormant，K 不使用 test 选择；
- dormant 只退出活跃匹配池，不删除 identity、latent、evidence 和历史。

该切片由研究者确认并记录为 D-020。

## 已确认切片：SPLIT/MERGE（2026-09-05）

- SPLIT 关闭并 retracted 旧 conflated identity，创建至少两个 candidate successors；
- 旧 evidence 与本次 program evidence 在 successors 间恰好分配一次；
- successors 不直接继承旧 aggregate latent，只引用各自 evidence 产生的 latent；
- MERGE 保留最早 valid_from 的 confirmed ID；并列时按 node_id 字典序；
- 其他 source IDs 变为 alias，全部历史、evidence、latent 和 provenance 保留。

白话：拆分时旧档案本身不可信，所以重建；合并时已有稳定档案可复用，所以保留最早的正式 ID。该切片记录为 D-021。

## 已确认切片：RETRACT/REPLACE（2026-09-05）

- absence 默认关闭 fact/edge version，不 retract 对象 identity；
- node-level RETRACT 只用于证实的误建、幻觉或错误身份；
- REPLACE=RETRACT(old fact)+BIRTH(new identity)+ADD(new fact)；
- reliable absence 至少需要两条不同 time/view key 的 online visible_empty；
- pose/depth 必须有效，reliability 达到预设门槛，期间不得有支持旧 fact 的正面 observation；
- M0 只用 reliability=1 oracle evidence，M2 数值阈值由 validation 冻结。

白话：看不见旧位置上的椅子，只撤回“椅子在这里”，不删除“椅子 A”这个身份。该切片记录为 D-022。

## 已确认切片：QUARANTINE（2026-09-05）

- “看不清”指事务解释无法可靠区分，不等于单纯画面模糊；
- top probability 或 top-1/top-2 margin 未跨过 validation 门槛时进入 QUARANTINE；
- evidence 进入独立 pending memory，不修改 persistent world；
- pending 保存低权重粗略 latent、空间、语义与候选假设，可与未来观测关联；
- K 只统计 relevant 且能消歧的观察机会，普通帧或没有回看不计数；
- K 次后仍未解决只转为 archived_unresolved，不删除；
- archived record 仍可检索和重新激活；
- 正式事务消费 pending 时必须引用原 evidence 并记录来源。

白话：看不清的信息是一张低置信度便签，不是正式世界事实，也不是垃圾。该切片记录为 D-023。

## 已确认切片：Graph-equivalence 身份对应（2026-09-05）

- 旧身份分 anchored 与显式 exchangeable；未声明为 exchangeable 的旧 ID 默认固定；
- 暂时无法区分但未来可能区分属于 ambiguity，不直接合并为 equivalence；
- 无外部锚点的新 local identity IDs 允许改名，但必须严格一一双射；
- 新身份不能映射旧身份，不允许多对一或一对多；
- 双射映射全局一致；不同视角 raw latent 可不同，但必须由后续 Projective Node Orbit 判定相容。

白话：档案编号可以任意，但档案里的“过去是谁”不能偷换；视角差异由投影解释，不能靠放松一一对应掩盖。该切片记录为 D-024。

## 已确认切片：Canonical memory-state equality（2026-09-05）

- equivalence 只横向比较从同一 immutable base 分叉得到的当前 post-edit states，不比较前后时刻，不阻止后续扩张或修订；
- 新 local ID、审计编号和无意义排列可以规范化，原始记录仍然保留；
- identity mapping 后的 lifecycle、版本历史、事实/关系、evidence/latent refs 归属、protected 与 pending state 必须一致；
- 任何可能影响后续事务的差异都不能被 equivalence 合并；
- future projection similarity 不定义 equivalence，只进入 CTL 的 `D_future`；
- 有限观测下仍可能分歧的世界保留为多假设，必要时 QUARANTINE。

白话：这里只把“同一本档案换了编号或排列方式”当作相同；不会把“现在看起来一样、以后可能不同”的两本档案提前合并。该切片记录为 D-025。

## 推荐默认

- dormant node 可 REACTIVATE；retracted node 不可直接 REACTIVATE（已确认）；
- RETRACT 至少需要可见区域中的重复 negative evidence；
- SPLIT/MERGE 不丢 evidence，旧 IDs 保留 predecessor/alias；
- posterior margin 不足时 QUARANTINE，不自动 NOOP（已确认）；
- pending evidence 达到 K 次有效机会后转为可检索归档，不删除、不修改 world history（已确认）。

## 完成方式

C00–C11 和 corruption variants 已给出唯一规则或显式 equivalence set：

- 研究者确认日期：2026-09-05
- 例外与理由：Projective Node Orbit 的数值容差只用于候选评分，不用于状态合并。
- fixture/version：C00–C11 human_draft / cpmt-0.2；合同已确认，尚不是方法效果 ground truth。
