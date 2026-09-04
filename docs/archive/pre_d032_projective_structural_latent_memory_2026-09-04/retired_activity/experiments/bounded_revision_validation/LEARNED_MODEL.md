# ESGBU 模型合同

工作名：**Evidence-Aware Sparse Graph Belief Updater（ESGBU）**。投稿前需检索名称冲突。

## 1. 模块边界

### 1.0 Predicate Schema Encoder

每个候选事实先读取 predicate registry `Σ`，编码 storage policy、arity、value type、symmetry、mutual exclusion、reference frame、temporal/dependency policy 与 observability。该向量与 fact/evidence 表示共同输入共享编辑头；主模型不为每个 predicate 建专属输出分类器，也不依赖任意自然语言语义。predicate-ID-only 与移除 schema fields 是必要消融。

### 1.1 Temporal Evidence Encoder

对候选事实的相关历史编码 event time、arrival time、delay、source、visibility、confidence、polarity 和 evidence group。默认 2–4 层 Transformer；GRU 和无序 pooling 是必要对照。

它要学习：低可见率负观测是否充分、迟到证据描述的是旧状态还是当前状态、多个弱证据是否独立、不同来源在不同条件下是否可靠。

### 1.2 Heterogeneous Graph Encoder

节点为 entity/fact/evidence/task，边为 subject/object、supports/contradicts、depends_on、mutually_exclusive 与 temporal adjacency。候选为 HGT 或 relational graph attention，推荐 3–4 层、hidden 128–256。

任务节点只能接收事实信息。默认阻断 task-to-fact message，防止任务成本改变世界真值。

### 1.3 Affected Mask Head

对每个候选事实预测 `p(M_i=1)`。标注同时区分：

- `direct_seed`：新证据直接涉及；
- `dependency_required`：因 typed dependency 必须联动；
- `protected_control`：相似但不应改变。

推理时模型给 seed，executor 求最小合法闭包。阈值和 mask budget 只在 validation 冻结。

### 1.4 Hierarchical Edit Decoder

先预测 `KEEP / QUARANTINE / COMMIT`；commit 时再预测 `ASSERT / RETRACT / REPLACE`、目标、替代事实、时间与证据集合。层级化用于缓解大量 no-op 与少量具体编辑之间的失衡。

### 1.5 Valid-Time Head

精确事件时间数据输出时间桶或连续分布；只有重扫区间的数据输出区间概率。模型可以预测“不确定区间”，不能用 arrival time 伪装 event time。

### 1.6 Evidence Attribution Head

预测 evidence-to-transaction 多标签集合。报告集合 precision/recall/F1、充分性与冗余度。attention map 不作为归因标签。

## 2. 确定性结构投影

模型输出必须经过同一个 executor：

```text
同一对象不能同时位于互斥位置；
写操作必须引用可达证据；
affected closure 外的 protected facts 不可修改；
依赖前提失效后不能继续 confirmed；
旧证据不能覆盖已经确认的较新有效区间；
证据不足只能 KEEP 或 QUARANTINE；
事务原子提交并产生 version/provenance；
投影拒绝必须记录原始候选与 rejection_reason。
```

硬投影不是给 ESGBU 独享的后处理优势；updater-isolation 主表中所有可产生 canonical transaction 的方法均经过同一 executor，并另报投影前后结果。

## 3. 规模配置

| 配置 | hidden/layers | 参数目标 | 用途 |
|---|---|---:|---|
| tiny | 128 / 2+2 | 约 3M–6M | smoke 与单卡调试 |
| base | 256 / 4+3 | 约 10M–20M | 正式比较上限 |

ESGBU 与 full-graph 对照至少做参数匹配和 wall-clock 匹配两组。参数量、FLOPs、训练时长、显存、单事务延迟全部报告。

## 4. 实现顺序

1. canonical schema、oracle transaction、executor、evaluator；
2. Last-time/Bayes/rule baselines；
3. FlatFact-MLP、GRU、Event-Transformer；
4. TGN-style 与 FullGraph-HGT；
5. ESGBU mask + edit；
6. time 与 attribution heads；
7. AI2-THOR ID/OOD；
8. 3RScan/3DSSG 外部测试。

在 1–4 未建立可信下限前，不增加 VLM、端到端视觉或更大 backbone。

## 模块验收 Criteria 纵列

| 模块 | 它不是为了什么 | 它必须改善什么 | Criteria | 数字判例 |
|---|---|---|---|---|
| Schema encoder | 不是扩大谓词清单冒充泛化 | registered-but-unseen predicate 的修订与保护 | 各适用C1–C15，按held-out split单列 | ID内exact=.84、held-out=.78；若ID-only也=.78则schema claim失败 |
| Temporal encoder | 不是只记最后到达消息 | stale/乱序下 edit 与校准 | C1/C2/C12 | 去掉双时间后 transaction exact 从84%降到73%才支持 H1 |
| Heterogeneous graph encoder | 不是因为 GNN 名字高级 | typed dependency 的召回与停止 | C3/C4/C7 | oracle8个依赖，命中7，NUR=87.5%仍不够 |
| Affected mask | 不是把 mask 做得越小越好 | 在NUR达门时提高CPR/降低CER | C3–C6/C15 | mask缩50%但NUR从97%降88%判失败 |
| Edit decoder | 不是只提高KEEP准确率 | 五类操作与事务整体正确 | C1/C2 | macro=.76而micro=.95时，以macro暴露长尾 |
| Time head | 不是预测received_at | exact/interval valid time | C8/C9 | AI2-THOR MAE=2s；3RScan覆盖91%宽38s |
| Evidence head | 不是attention截图 | 集合正确且具干预充分性 | C10/C11 | evidence F1高但删除后输出不变，归因主张失败 |
| Hard projection | 不是掩盖模型非法率 | post非法0且公开pre/reject | C13 | pre4%、post0；不能只报0 |
| Read-only task nodes | 不是用任务偏好改写真值 | 降低错误后果且事实指标不降 | C14 + C3/C5/C12 | cost降但CPR 99.6→98.2%，不能称整体改善 |
