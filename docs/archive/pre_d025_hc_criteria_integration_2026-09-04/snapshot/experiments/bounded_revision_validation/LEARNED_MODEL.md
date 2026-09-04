# ESGBU 模型合同

工作名：**Evidence-Aware Sparse Graph Belief Updater（ESGBU）**。投稿前需检索名称冲突。

## 1. 模块边界

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

