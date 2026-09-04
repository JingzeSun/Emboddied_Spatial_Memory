# 01 研究合同：可投影、可增长、可修订的结构化视觉 latent 记忆

## 研究问题

给定连续具身观测、位姿与动作，如何把视角相关的视觉 latent 转换为世界坐标中的持久结构状态，并在每一步决定哪些 observation regions 应绑定旧节点、创建或重激活节点、扩充图结构、保持不变或修订历史？

\[
R_t=\operatorname{Tokenize}(I_t,D_t,K,T_t),
\qquad
\hat R_t=\operatorname{PredictProject}(S_{t-1},a_{t-1},T_t,K),
\]

\[
q_\theta(A_t,U_t\mid R_t,\hat R_t,S_{t-1},a_{t-1},\Sigma),
\qquad
S_t=\operatorname{Execute}(S_{t-1},A_t,U_t).
\]

### 随机变量与状态

- `R_t`：view-dependent projective structural tokens；每个 token 带 image support、latent、geometry、semantic、visibility、dynamic 与 uncertainty；
- `S_{t-1}`：world-centric memory graph，含 Place、Chart、persistent slot、transient track、事实、关系、版本和证据；
- `Rhat_t`：旧 memory 对当前视角的预期投影，包含 expected visibility 与 predicted structural latent；
- `A_t`：region-to-world binding，包括 `BIND/NEW/REACTIVATE/SPLIT/MERGE/UNRESOLVED`；
- `U_t`：统一 memory transaction，包括 node/edge birth、reinforce、state update、relink、retract、replace、preserve、quarantine，以及 scope/time/evidence；
- `Sigma`：节点、关系、坐标、生命周期和执行约束 schema。

## 中心可证伪假设

- **H1 Projective representation**：结构化 region tokens 比固定 image patches 更能在转弯、斜视与局部遮挡下保持可绑定性；
- **H2 World binding**：显式 predict-project + binding 比 IoU/nearest/EMA 降低 identity switch、false merge 与 duplicate birth；
- **H3 Controlled growth**：candidate confirmation 与 Chart attachment 能在不增加 hallucinated nodes 的条件下提高新结构覆盖；
- **H4 Dynamic persistence**：transient/persistent 分层和 visibility reasoning 同时降低静态污染与真实变化漏检；
- **H5 Unified revision**：同一 transducer 能区分 reveal、occlusion、sensor error 与 persistent change，并以局部事务保护无关状态；
- **H6 Predictive utility**：action/pose-conditioned structural prediction 改善下一视角的 visibility/attachment 与只读任务，不靠 RGB reconstruction。

任一假设若不优于对应强基线，就删除该 claim；总分提升不能替代逐机制证据。

## 候选贡献层级

1. **问题与 benchmark**：首次揭示、重访、遮挡、动态干扰和真实改变共存时的在线 world-memory growth-and-revision；
2. **表示**：view-dependent structural latent 与 world-centric versioned graph 的明确分层；
3. **方法**：predict-project → bind → transact 的统一 memory transducer；
4. **安全执行**：候选、多假设、protected scope、valid time、evidence 与原子版本；
5. **评价**：同时衡量绑定、增长、保持、修订、预测、任务与效率。

第 1 项即使神经方法失败仍可能保留 benchmark 价值；第 2–5 项必须由对照、消融和真实失败案例支持。

## 第一篇论文边界

### 核心学习对象

- structure-conditioned observation tokenization；
- projected-memory/observation matching；
- region-to-node association 与 abstention；
- candidate node/edge birth 和局部 attachment；
- memory transaction 的 scope/operator/time/evidence；
- action/pose-conditioned structural prediction。

### 固定或分阶段对象

- 第一轮使用冻结 DINO 类视觉 backbone；
- depth、intrinsics、pose 先使用 simulator/oracle 或同一冻结估计器；
- Chart/Place split/merge 先用 oracle/确定性规则，再作为扩展消融；
- navigation/planning 使用冻结 reader，不反向定义 memory truth。

### 非目标

- RGB/video reconstruction；
- 新的 detector、SLAM 或任意开放词汇本体发现；
- 完整端到端导航、社会规范规划或多机器人系统；
- 把 VP、DINO、GNN、Transformer、scene graph 或节点扩充单独称为创新。

## “world model”使用条件

若方法只做 observation fusion 和长期存储，论文使用 `persistent spatial memory`。只有 action-conditioned transition 对未来 structural latent/visibility/attachment 有独立预测评测，并用于规划或反事实，才使用 `world model` 作为核心术语。

## 成功判据

主结论不能只靠 query/navigation success。必须同时报告：association、ID switch、false merge、duplicate birth、birth/attachment、static retention、dynamic contamination、visibility state、revision transaction、protected controls、预测、效率及失败。

## 状态

D-032 已接受本研究主线与文档 supersession；全部方法、schema、数据、evaluator、训练和实验结果仍为 proposed/not implemented/not validated。
