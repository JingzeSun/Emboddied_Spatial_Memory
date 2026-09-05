# 02 CPMT 场景与四阶段 WBS

定位：场景矩阵与阶段职责，不是当前进度表；执行状态和下一步统一见 [实验记录](../EXECUTE.md)。下文 M0 的“不训练”仅描述该阶段，不否定已完成的开发训练。

## 最小场景矩阵

| ID | 主要竞争事务 | 当前歧义 | 未来判据 |
|---|---|---|---|
| C00 | NOOP vs RELINK/BIRTH | 纯视角变化还是世界变化 | 后续重投影与旧世界一致 |
| C01 | BIND vs BIRTH | 相似实例重现还是新实例 | 后续共现/互斥 |
| C02 | BIRTH vs BIND | 首次揭示还是旧结构 | 多视角形成独立支持 |
| C03 | BIND vs REACTIVATE | 当前活跃身份还是历史身份恢复 | lifecycle 与后续轨迹 |
| C04 | SPLIT vs NOOP | 一个旧节点是否混合两个实体 | 两组 evidence 独立出现 |
| C05 | MERGE vs separate IDs | 重访副本还是真实同类实例 | 后续共同/独立轨迹 |
| C06 | RELINK vs REPLACE | 同一身份移动还是被新实体替代 | identity continuity |
| C07 | RETRACT vs occlusion | 旧事实失效还是暂时不可见 | reliable visible-empty |
| C08 | RELINK vs temporary block | 拓扑改变还是临时阻挡 | 后续通行证据 |
| C09 | NOOP vs edit | pose/depth fault 还是世界变化 | 位姿恢复后的一致性 |
| C10 | NOOP/BIND vs static edit | 动态 actor 是否污染背景 | actor 离开后的背景 |
| C11 | any vs collateral edit | 无关图是否被连带修改 | protected subgraph 不变 |

每个 case 有 positive、confounder、control 和 protected distractor。同一 paired_group 不跨 split。

## M0：Language + Executor

- 冻结 intent/template/primitives/lifecycle；
- 写 C00–C11 draft fixtures 和非法 corruption；
- 实现 clone、execute、rollback、hash、provenance；
- 只证明事务真实可执行，不训练、不声称有效。

## M1：Hard-condition

- 使用可控 latent simulator；
- 比较 CPMT-CTL Core、direct classifier、direct+future loss、execute/current-only、future/no-execution、oracle；
- primary contrast 为 Core vs direct+future、Core vs no-execution；
- 失败立即停止主 claim。

## M2：Embodied visual online

- 固定 backbone、depth、pose、regions 和 candidate generator；
- 接入固定/轻量 Projective Node Orbit；此时包含世界节点跨视角表征的系统才称 Full CPMT；
- 验证 turning、revisit、reveal、relocation、absence、occlusion；
- 报 teacher、online、self-rollout 和标签效率；
- SPLIT/MERGE 是同一机制的组合压力测试。

## M3：External + paper

- 只选择一个 external rescan 或小规模现实来源；
- 运行 formal seeds、OOD、runtime 和 artifact replay；
- 按 claim–evidence ledger 决定投稿措辞。

## 范围锁

主动消歧、第二应用、learned proposer、端到端视觉训练和导航不属于 M0–M3。任何新增必须先证明现有 gate 无法回答主问题。
