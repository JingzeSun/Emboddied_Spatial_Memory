# BEGR-Net：可训练的双时间证据图后验修订器

状态：**模型合同草案；尚未实现、尚未训练、尚无结果。** 本文件属于唯一核心实验包，不创建第二套研究蓝图。语义规则仍由 `docs/DECISIONS.md` 中的 HC 条目治理。

## 1. 为什么训练，但不靠堆复杂度

当前需要学习的不是“识别一把椅子”，而是一个条件分布：给定旧世界事实、乱序到达且可能互相矛盾的证据、事实依赖和当前版本，预测这次事务应当保持、暂缓还是提交；若提交，选择哪些事实和哪种 typed operation。

工作名：**Bi-temporal Evidence-Gated Graph Revision Network（BEGR-Net）**。

复杂度放在三个真正困难的位置：

1. event time、arrival/transaction time 与事实 valid time 分离；
2. 证据、事实和 typed dependency 的结构化联合推断；
3. 稀疏事务、拒绝提交、证据归因和可回放历史。

视觉 backbone、检测、身份关联和动作规划在主因果实验中固定。模型若只在更强视觉前端下获益，不能归因给后验修订。

## 2. 输入和输出

一个训练样本是一次 revision opportunity，而不是单帧：

```text
X_t = (
  candidate fact subgraph G_t,
  recent evidence events E_<=t,
  typed dependency edges D,
  base version v_t,
  optional task read-only context q_t
)

Y_t = (
  gate,
  target facts,
  typed operations,
  supporting evidence ids
)
```

每条 evidence event 至少包含：

```yaml
evidence_id: ev_204
entity_hypotheses: [cart_2]
predicate: located_in
value: loading_zone_b
polarity: positive | negative
observed_at: 120.0       # 事件/观测时间
received_at: 128.4       # 系统收到证据的事务时间
source_id: camera_west
evidence_group_id: sweep_17
coverage: 0.94
confidence: 0.87
identity_confidence: 0.96
```

`observed_at` 早不等于证据应被忽略：它可能迟到并纠正历史；`received_at` 新也不等于它描述的世界状态更新。输出的事实 `valid_interval` 由已接受的时间语义和 deterministic executor 生成，不能把 arrival time 当真实变化时刻。

### 2.1 图的节点和边

采用 reified fact graph，避免把所有信息塞进对象 embedding：

- entity nodes：对象、surface、portal、Chart/Place；
- fact nodes：`predicate(subject, object/value)` 及 status、valid interval、version；
- evidence nodes：观测、来源、时间、正负性、coverage 与 evidence group；
- dependency edges：`supports`、`contradicts`、`derived_from`、`moves_with`、`invalidates_if`、`protected_by`；
- optional task node：只用于下游 readout，默认不得影响事实写入。

主实验由 deterministic retriever 给出候选子图；否则“检索是否找到事实”和“修订是否正确”会混成一个误差。

## 3. 模型结构

```text
evidence events
  → time/source/polarity encoder
  → causal event Transformer
                         ↘
candidate fact graph → typed relational graph encoder
                         ↓
                 evidence–fact cross attention
                         ↓
        hierarchical transaction decoder
        ├─ gate: preserve / quarantine / commit
        ├─ targets + operator | commit
        └─ supporting evidence attribution
                         ↓
              deterministic executor
        ├─ dependency closure + stop boundary
        ├─ hard preconditions and atomicity
        ├─ valid interval + recorded_at
        └─ version/provenance commit
```

### 3.1 Evidence encoder

- 同时编码 `observed_at`、`received_at` 和二者差值；
- 同一 `evidence_group_id` 的相邻帧先聚合，防止十帧被当成十个独立证人；
- source embedding 只能学习来源条件，不得访问 test 来源统计；
- event Transformer 使用 observed-time causal mask 加显式 late-arrival flag；乱序证据实验另做无 mask/arrival-order 消融。

### 3.2 Relational graph encoder

首选 2–3 层小型 typed relational Transformer/HGT-style encoder。关系类型拥有独立参数或低秩基；节点初始特征由事实类型、语义状态、时间区间、置信度和版本年龄构成。

它不是因为名字叫 GNN 就自动“结构化”。是否结构化仍按 `BASELINES.md` 的 SA1–SA7 审计：持久实体、显式事实、typed relation、旧状态条件更新、可追踪 mutation 和 canonical export 缺一不可。

### 3.3 分层事务解码器

第一层先预测：

```text
preserve   证据不要求写正式事实
quarantine 证据相关但不足或冲突，需要保留分支
commit     满足门槛，可以提交事务
```

只有 `commit` 才激活 target/operator 解码：`ADD / INVALIDATE / RELINK / SUPERSEDE / REINFORCE`。这比直接把所有状态与操作做成一个平面分类更符合问题条件结构，也允许与 flat decoder 做严格消融。

模型提出直接 targets 和 operators；dependent affected facts、protected controls、stop edges、合法时间区间和 version chain 由 typed contract 与 executor 推导/验证。学习模型不得绕过 executor 直接改图。

## 4. 主损失：一个结构化似然，不是十七项拼盘

默认主目标：

```text
L = L_revision_nll + lambda_ev L_evidence + lambda_sp R_sparse

L_revision_nll =
  - log p(gate | X)
  - 1[gate=commit] log p(targets, operators | gate, X)
```

其中 target 与 operator 可用自回归 set decoder，或在固定 candidate set 上用带 STOP token 的排列不变集合似然。它们是同一个事务联合概率的因子分解，不是若干互相抢梯度的独立任务。

- `L_evidence`：可选辅助项，只在 supporting evidence 标签可靠时监督 evidence attribution；
- `R_sparse`：小权重的多余 target 惩罚，只抑制无必要写入，不能替代 recall；
- 建议 validation 搜索而非人工拍定：`lambda_ev ∈ {0, 0.1, 0.3, 1.0}`，`lambda_sp ∈ {0, 1e-4, 1e-3, 1e-2}`；最终值与选择依据写入 run manifest。

### 4.1 不再各自训练成 loss 的内容

| 原候选项 | 当前处理 | 原因 |
|---|---|---|
| state 与 operator 两套 loss | 合并进 joint revision NLL | 最终状态和操作高度重复，双重监督容易重复计权 |
| affected/control/stop | typed dependency closure + evaluator | 有精确规则时先做硬结构；另训三个 head 会允许互相矛盾 |
| valid time/version | executor 生成并做 hard validation | 真实变化时刻多为 interval-censored，不应假装精确点回归 |
| preservation/constraint | write mask、precondition、atomic transaction | 这是安全合同，不应靠有限 penalty“尽量做到” |
| task success/action cost | 固定下游 reader 的评测指标 | 不让特定导航/任务偏好污染通用 posterior |
| calibration | validation temperature scaling + ECE/Brier | 先验证概率质量，只有明确失准再加 calibration objective |

如果后续确实学习多个共享 encoder 的任务，先记录每个 loss 的梯度范数和两两 cosine；只有观测到持续冲突，才把 uncertainty weighting、GradNorm 或 PCGrad 作为预注册消融，不作为默认方法卖点。

## 5. 容量档位与训练顺序

| Variant | 结构 | 目的 |
|---|---|---|
| S | `d=128`，2 event layers，2 graph layers，4 heads | 单卡/快速反证；默认首跑 |
| M | `d=256`，3+3 layers，8 heads | 主模型候选 |
| L | `d=384`，4+4 layers，8 heads | 只做容量控制；若 M 无饱和证据不启用 |

参数量必须由实际代码打印，不在设计阶段虚报。训练顺序：

1. evaluator/oracle 先对 12 个 smoke fixtures 达到 100% 合同硬门；
2. 256 个生成样本 tiny-set overfit，训练 transaction exact match 目标 ≥98%，否则先查标签或实现；
3. symbolic generator 产生训练流，先跑 flat MLP、event Transformer 和 deterministic strong-local；
4. 再加入 typed graph encoder；
5. validation 选择 checkpoint、温度与 commit 阈值；
6. 冻结后一次性跑 ID test、组合 OOD 和真实数据 secondary track。

建议首轮开发规模为 30k train / 5k validation / 5k ID test transactions，另留 5k OOD；这只是预算起点，不是统计充分性结论。split 必须按场景 family、环境和 counterfactual group 分组，不能把同一模板换对象名后分到 train/test 两边。

## 6. 必做学习基线与消融

在 `BASELINES.md` 的确定性 B0–B7 之外，至少加入：

- L0 FlatFact-MLP：相同事实特征，无时间序列、无图边；
- L1 Event-Transformer：相同事件历史，无图邻接；
- L2 TGN-style memory：通用动态图事件更新；
- L3 FullGraph-RGT：typed graph encoder，但每次预测整图新快照；
- L4 BEGR-Net：分层门控、稀疏事务、deterministic executor；
- L5 BEGR-FlatDecoder：与 L4 同参数预算，把 gate/operator 展平，检验分层条件结构本身。

所有 learned methods 共享 candidate facts、event encoder 输入字段、train/validation/test split、参数预算档位和调参预算。不同模型不能用不同的 oracle 信息。

最小消融：去 event time、去 arrival time、打乱 source、去 typed edge、去 evidence group、去 quarantine、去 sparse regularizer、去 provenance read-in、移除 hierarchical decoder。

## 7. 先于正式训练的反证检查

| Check | 若失败意味着什么 |
|---|---|
| label-prior baseline 已接近主模型 | 数据生成器太容易或标签泄漏 |
| 时间戳打乱不掉分 | “双时间”没有被任务真正需要 |
| typed edge 打乱不掉 dependency-depth OOD | 图结构没有贡献 |
| flat decoder 与分层 decoder 等价 | 不应宣称分层事务建模有效 |
| TGN-style 与 BEGR 在 UP/CP/ST/TV 等价 | 方法新意需收缩到协议/审计层 |
| 训练高、模板族 OOD 低 | 模型记住模板而非修订规律 |
| confidence 上升但 unsafe commit 不降 | 校准或 abstention 设计无效 |

这些结果不是“模型垃圾”，而是早期研究结论。它们必须在扩 backbone 或接真实感知之前出现。

## 8. 单人实现边界

第一篇/第一个完整实验只训练 posterior updater。使用已有视觉特征或 oracle facts，不训练检测器、SLAM、region tokenizer、world prediction、active planner 和 posterior updater 的端到端组合。待核心反证实验成立后，再选择一个最有价值的上游噪声源接入。

成熟度来自：冻结语义、反事实数据、强基线、概率校准、OOD 拆分、事务回放和失败分析；不来自 loss 数量或 backbone 大小。
