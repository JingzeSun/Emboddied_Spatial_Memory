# 基线与结构化准入协议

状态：**草案；待 HC-017 人工确认。**

## 1. 为什么不能只看论文是否自称“结构化世界模型”

“structured”“scene graph”“memory”只是作者用语，不能作为控制变量。主实验不按论文标签
分组，而是把所有可执行方法接到同一份 canonical fact graph 上，固定上游输入，只替换
posterior updater。这样才能把差异归因给后验修正规则，而不是检测器、跟踪器、VLM 或地图质量。

外部方法另做能力覆盖审计，不与主因果比较混在一起。

## 2. 结构化准入标准（SA1–SA7）

一个方法只有同时满足 SA1–SA6，才标记为 `native_structured_revision`；SA7 是主实验的额外要求。

| ID | 判定问题 | 通过例 | 不通过例 |
|---|---|---|---|
| SA1 Persistent entities | 跨时间是否有可追踪实体，而不是每帧独立框？ | `mug_7` 在 t1、t2 保持同一 ID | t1/t2 各自只有 `mug` 检测框 |
| SA2 Explicit facts | 状态能否导出为离散事实或带类型属性？ | `on(mug_7, table_2)`、`open(drawer_1)=true` | 只有不可解释的整图 embedding |
| SA3 Typed relations | 是否显式区分关系语义与参数？ | `inside`、`on`、`attached_to` | 只有无类型相似度边 |
| SA4 Prior-conditioned update | 新状态是否由旧状态和新证据共同产生？ | updater 输入 `B_t` 与 `O_t` | 每轮从最新帧重建全图，不读旧状态 |
| SA5 Selective mutation | 能否指出哪些旧事实被保留、撤销或替换？ | 输出 `retract f3; add f8` | 只输出一张新快照且无法对齐事实 |
| SA6 Canonical export | 是否能无歧义映射到统一 schema，并通过适配器测试？ | 同一事实两次导出完全一致 | 映射依赖人工猜测或随机生成 |
| SA7 Fixed upstream | 比较时能否使用完全相同的 `B_t/O_t/I_t/V_t/Q_t/D`？ | 所有 updater 读取同一 fixture | 基线必须换自己的检测/关联结果 |

数字例：某外部方法满足 SA1、SA2、SA3、SA4、SA6，但只重建快照，不能给出事实级变更，
因此 SA5 失败。它应标为 `projected_structured_snapshot`，可比较最终图 F1，却不能被当作
“选择性后验修正”基线来比较操作精度、停止正确率或版本历史。

## 3. 三层标签

| 标签 | 含义 | 可比较指标 |
|---|---|---|
| `native_structured_revision` | 原生持久实体、显式事实/关系、读取旧状态并输出可追踪修正 | 全部指标 |
| `projected_structured_snapshot` | 可把前后快照确定性投影到 canonical graph，但没有原生操作/历史语义 | 最终节点/边/事实指标、任务指标；操作与版本指标记 N/A |
| `unstructured_or_per_frame_control` | 只有文本、embedding 或逐帧输出，无法可靠恢复持久事实 | 仅作为表示消融或任务控制，不作同类方法结论 |

不得把 N/A 记为 0，也不得因为某方法无法输出 provenance 就宣称其 provenance 得分低。

## 4. 主实验 updater 基线

所有下列方法读取同一 canonical input：

| ID | 基线 | 唯一变化点 | 预期暴露的问题 |
|---|---|---|---|
| B0 | `no_update` | 永不改旧信念 | 漏掉真实变化 |
| B1 | `append_only` | 新事实只追加，不撤销冲突旧事实 | 冲突并存、版本污染 |
| B2 | `latest_overwrite` | 最新观测覆盖相关槽位 | 遮挡即删除、证据不足也提交 |
| B3 | `matched_node_local` | 只改直接匹配实体属性和入射边 | 漏掉非局部依赖传播 |
| B4 | `incident_edge_recompute` | 重算变化实体的全部入射边 | 比 B3 强，但仍不追踪类型化跨实体依赖 |
| B5 | `full_graph_recompute` | 每次对整图重算 | 可能正确但副作用和成本高 |
| B6 | `bounded_revision` | 证据门控 + affected/control/stop + 版本事务 | 候选方法 |
| B7 | `oracle_revision` | 使用真值变化类型和作用域 | 给出协议上界并检查评测器 |

### 4.1 学习型基线

确定性基线先回答“规则是否已经足够”；学习型基线再回答“优势来自时间建模、图结构、稀疏事务还是参数量”。

| ID | 方法 | 保留/移除的结构 | 主要控制问题 |
|---|---|---|---|
| L0 | `FlatFact-MLP` | 相同 candidate fact features；无 history、无 graph edges | 静态特征是否已足够 |
| L1 | `Event-Transformer` | 有 evidence sequence 与双时间；无 graph adjacency | 时序是否足够，图是否必要 |
| L2 | `TGN-style` | 通用 event-based node memory/message/update | 通用动态图模型是否已解决问题 |
| L3 | `FullGraph-RGT` | typed graph encoder；每次预测完整新快照 | 稀疏 transaction 是否必要 |
| L4 | `BEGR-Net` | 双时间、typed graph、hierarchical gate、稀疏事务、executor | 候选方法 |
| L5 | `BEGR-FlatDecoder` | 与 L4 同 encoder/预算；展平 gate/operator | 分层条件解码是否必要 |

TGN-style 实现应遵循公开的 event/message/memory/update 组件，而不是只借名字；若直接使用第三方库，保存版本、配置和偏差说明。所有 L0–L5 使用同一 candidate set、split、参数容量档位、训练 epoch 上限、early stopping 和 hyperparameter trial 数。

模型不因使用 graph neural network 就自动通过 SA1–SA7。例如 L3 有 typed graph encoder，却只输出不可追踪快照时，SA5 仍失败；它只能比较最终事实/边指标，不能把 operation/provenance 的 N/A 当低分。

## 5. 外部论文如何纳入

1. 先填写 SA1–SA7，并为每项保存论文页码、代码位置或导出样例。
2. 有代码且能固定上游：接 canonical adapter，进入主实验。
3. 有代码但只能输出快照：进入 snapshot track，只报共同指标。
4. 无代码或不可复现：只做 feature matrix，不制造数值结果。
5. DSG（2026-09-01 预印本）当前按 `projected_structured_snapshot / novelty_watch` 审计；若其代码或
   补充材料后来公开并满足 SA5、SA7，再升级标签。标签是可复核事实，不是价值判断。

## 6. 适配器保真度

- smoke fixtures 的实体、事实、关系映射必须 `100%` 通过人工金标后，才可运行正式比较。
- 任何丢失的关系类型、时间字段或实体 ID 都要列入 `adapter_loss`。
- 若 120 个输入事实中只正确导出 117 个，保真度为 `117/120=97.5%`，未达硬门槛；不能把后续
  差异归因给 updater。

## 7. “结构本身”的控制实验

主实验回答“相同结构下哪种 updater 更好”。结构价值另开消融，逐项只去掉一个能力：

- A0：完整结构化 posterior；
- A1：扁平事实表（保留相同事实，不提供图邻接）；
- A2：去掉依赖类型，只保留无类型边；
- A3：去掉 control set；
- A4：去掉版本和 provenance；
- A5：只保留观测事实，去掉 derived facts。
- A6：去掉 `observed_at`，只保留 arrival order；
- A7：去掉 `received_at`，假设证据同步；
- A8：打乱 typed dependency edge；
- A9：把同一 `evidence_group_id` 的帧误当独立证据；
- A10：去掉 quarantine，只能 preserve/commit。

若 A0 对 B3/B4 有优势但对 A1 没优势，不能声称“图结构有效”；优势可能只来自修正规则。

同理，若 L4 相对 L1 的优势在 A8 后不下降，不能声称 typed graph 产生作用；若 L4 相对 L2 只改善最终 F1、不改善 UP/CP/ST/TV，则不能声称解决了有界可追溯修订。
