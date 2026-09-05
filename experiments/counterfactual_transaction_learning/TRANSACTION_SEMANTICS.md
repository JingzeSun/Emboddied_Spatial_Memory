# CPMT Transaction Language

状态：**北极星层级已确认；M0 用 fixtures 冻结边界**。

## 两级语义

每个 program 使用一个 intent 和一个 executable template：

| Intent | Template | 世界解释 |
|---|---|---|
| PRESERVE | NOOP | 当前证据不足以改变 persistent world |
| ASSOCIATE | BIND | evidence 属于当前活跃节点 |
| ASSOCIATE | REACTIVATE | evidence 属于 dormant historical node |
| EXPAND | BIRTH | 旧节点均不能解释，需要新 identity |
| REVISE | RELINK | identity 不变，位置/拓扑/所有关系改变 |
| REVISE | RETRACT | 可靠证据使既有事实/edge version 失效；普通空观测不撤回 identity |
| REVISE | SPLIT | 一个旧节点混合了多个实体/表面 |
| REVISE | MERGE | 多个节点是同一实体的重复表示 |
| REVISE | COMPOSITE:REPLACE | RETRACT(old) 后 BIRTH(new) |

NEW/CREATE 在论文和代码中统一为 BIRTH。REPLACE 不新增原子操作。

## QUARANTINE

QUARANTINE 是 commit wrapper，不是 world transaction：

- 不修改 persistent world graph；
- 把 evidence 写入独立、可检索的 pending memory；
- 不与 NOOP 混为同一个评估标签；
- top probability 或 top-1/top-2 margin 未跨过固定门槛时触发；
- evidence 保留粗略 latent、空间、语义、可靠度和假设历史；
- 只有 relevant 且 can_disambiguate 的观察机会才累计 K；
- K 次仍未解决时转为 archived_unresolved，不删除；
- active/archived 都可被未来证据检索，正式事务消费时必须引用原 evidence；
- 门槛与 K 只由 train/validation 冻结，不学习 action policy。

白话说，模糊印象进入低置信度“草稿记忆”，不会提前改正式世界。机器人真正回看相关区域才算一次机会；多次仍看不清只降低检索优先级，未来看到相似东西仍能把它找回来。

M0 中 evidence 的 decision weight 使用 reliability 乘以独立性权重。相同 time/view 的重复证据保留审计记录，但独立性权重为零；更一般的视角相关性和 Projective latent 相似度留到 M2 学习与 validation。

## 身份生命周期与版本

身份状态与记录版本分开：

- candidate：新 identity，尚未确认；
- confirmed：已确认 identity；
- dormant：暂不活跃但可由 REACTIVATE 恢复；
- retracted：已被可靠证据否定，不可直接恢复；
- alias：MERGE 后指向 canonical identity。

valid_to 只表示某一 node/edge version 是否结束，不是 lifecycle。BIND 只接受 candidate/confirmed；REACTIVATE 只接受 dormant。candidate→confirmed 必须由 program 显式执行，executor 不按计数自动升级。以上由 D-019 冻结。

白话说，BIRTH 只是给一个疑似新物体建立“候选档案”，不会见一次就认定它是真实新身份。后续 BIND 带来第二条独立视角证据时，program 可以明确把它升级为 confirmed。长期没见到 confirmed 节点时，确定性维护规则可以把它放入 dormant；这只是退出活跃匹配池，不代表对象消失。以上由 D-020 冻结。

## SPLIT/MERGE 身份继承

SPLIT 将错误混合多个对象的旧 node 标为 retracted 并关闭，创建至少两个 candidate successors。旧 evidence 与本次 program evidence 必须在 successors 间恰好分配一次；successor latent_refs 彼此分离且不直接继承旧 aggregate latent。

MERGE 从 confirmed sources 中按最早 valid_from、再按 node_id 字典序选 canonical。全部 source versions 关闭后，canonical 打开聚合 evidence/latent 的新版本，其他 IDs 打开只指向 canonical 的 alias 版本。

白话说，SPLIT 是“旧档案本身混错了，所以作废后建两个新档案”；MERGE 是“同一个对象被建了重复档案，所以保留最早的正式 ID，其他改成别名”。当前只验证引用集合和版本语义，尚未实现 Projective Node Orbit 的 latent 学习。

## 事实级 RETRACT、REPLACE 与可靠缺席

D-022 将普通环境变化与“身份从来就是错的”分开：

- 普通 visible-empty 只能关闭被否定的 fact/edge version，例如“椅子 A 位于左侧”，不能删除或 retracted “椅子 A”这个 identity；
- node-level RETRACT 只留给未来可证明为虚构、幻觉或错误身份的情况，当前 executor 不实现；
- REPLACE 严格编译为关闭旧事实、BIRTH 新 candidate identity、再添加新事实；
- REPLACE 保留旧 identity 及其历史，不能偷偷等价成 RELINK，也不能顺手撤回旧 identity。

白话说，机器人连续确认“左边已经没有椅子”，只能得出“椅子 A 不再位于左边”，不能得出“椅子 A 从世界上从未存在”。如果右边出现的是另一把椅子，就保留旧椅子档案、关闭旧位置记录，再给新椅子建候选档案。

M0 的 reliable absence 必须同时满足：

1. 至少两条 online `visible_empty` 反证；
2. 两条证据具有不同的 `(time_index, viewpoint_id)`；
3. pose 与 depth 均有效；
4. reliability 不低于阈值；
5. 两条反证之间没有支持同一旧事实的正观测。

M0 oracle evidence 的 reliability 固定为 1；M2 的实际阈值只能在 validation 上选择，不能用 test 调参。

白话说，一次没看到可能只是漏检；遮挡更不能证明东西消失。只有从两个独立观察机会都清楚看见“那里是空的”，而且中间没有重新看到对象，才允许关闭那条旧事实。

## Primitive operations

- ASSERT_PRECONDITION
- CREATE_NODE
- OPEN_NODE_VERSION
- CLOSE_NODE_VERSION
- ADD_EDGE
- CLOSE_EDGE_VERSION
- ATTACH_EVIDENCE
- MOVE_EVIDENCE
- SET_CANONICAL_ALIAS
- SET_LIFECYCLE
- RECORD_PROVENANCE

不允许物理 DELETE。

## Template invariants

- NOOP：persistent world hash 不变；
- BIND：target lifecycle 必须 candidate/confirmed，不创建 identity；
- REACTIVATE：target 必须 dormant，关闭旧 version 并打开可追溯的 confirmed version；
- BIRTH：必须 CREATE_NODE，初始为 candidate；
- RELINK：保持 identity，关闭旧 edge version 后打开新 edge；
- RETRACT：引用满足 D-022 的 reliable negative evidence，只关闭对应 fact/edge version；
- SPLIT：旧 node retracted/closed；新 candidate successors 引用 predecessor，evidence exact-once partition；
- MERGE：最早 confirmed ID 保留为 canonical，来源节点新版本变为 aliases；
- REPLACE：有序执行 RETRACT→BIRTH→ADD_EDGE，保留旧 identity，两个身份不得偷换成 RELINK。

同一 transaction_id 重放必须幂等或显式拒绝。

## Conservative canonical memory-state equality

D-024 已冻结并实现身份对应层：anchored/unlisted 旧身份固定，显式 exchangeable 旧身份只能在声明集合内一一置换；共同 base 后的新 local identity 可 alpha-renaming，但必须严格双射，且不得映射到旧身份。

D-025 只把新 ID 名称、审计编号和无意义排列视为可忽略表示差异。身份映射后的节点状态、事实关系、版本历史、evidence/latent refs 归属、protected 与 pending state 必须一致。有限未来预测相似不定义等价；它只参与 `D_future` 候选评分。若某项差异可能改变未来事务，两套状态就继续作为竞争假设。

白话说，我们只把“同一本档案换了编号或排列顺序”合并，不把“现在看起来一样、以后可能不同的两本档案”合并。世界从 (t) 到 (t+1) 仍然可以正常扩张和修订。

当前 C00–C11 与 63 个单元测试只证明以上合同能够被确定执行、暂存、进行保守状态比较或原子拒绝，不证明 CTL 已经学会选择正确事务。
