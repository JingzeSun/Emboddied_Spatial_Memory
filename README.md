# Embodied Spatial Memory

当前唯一研究方向是 **Counterfactual Projective Memory Transactions（CPMT）**。它仍然是一个具身空间记忆项目；其中的核心学习机制叫 **Counterfactual Transaction Learning（CTL）**。

## 北极星

> 机器人从未来多视角证据中学习：当前结构观测应该保留、绑定、创建、重激活、重连还是撤回世界记忆；训练时真实执行候选事务并比较修改后的世界，在线时使用不看未来的摊销模型完成决策。

本项目不扩张为脱离具身场景的通用 structured-state learning，也不退回到只增加 future loss 的 PSLM。

## 白话入口

一句话说，机器人维护一个带版本的内部世界；看到新东西时，它把“还是旧对象、出现新对象、旧对象移动或旧事实失效”等解释分别执行到世界副本，再用后续观测学习哪种修改最合理。

所有当前术语、公式、事务和实验的中文解释见 [CPMT 白话方法词典](docs/PLAIN_LANGUAGE_GLOSSARY.md)。以后新增概念必须在首次出现处同时写白话说明，并同步该词典。

## 方法核心

对候选 transaction program \(u\)，从同一旧世界版本分叉执行：

\[
S_t^{(u)}=\operatorname{Execute}\!\left(\operatorname{Clone}(S_{t-1}),u\right).
\]

执行后世界的能量为：

\[
\begin{aligned}
E(u)=&
\lambda_nD_{\mathrm{now}}\!\left(\Pi(S_t^{(u)},T_t),R_t\right)
+\lambda_fD_{\mathrm{future}}\!\left(
\operatorname{PredictProject}(S_t^{(u)},a_{t:t+H-1},T_{t+1:t+H}),
R_{t+1:t+H}\right)\\
&+\beta C_{\mathrm{edit}}(u)
+\gamma C_{\mathrm{growth}}(u)
+\eta C_{\mathrm{collateral}}(u)
+I_{\mathrm{illegal}}(u).
\end{aligned}
\]

由此得到训练期 hindsight posterior：

\[
p^*(u)=
\frac{\mathbf 1[u\ \mathrm{legal}]\exp[-E(u)/\tau]}
{\sum_{v\in\mathcal C_t}\mathbf 1[v\ \mathrm{legal}]\exp[-E(v)/\tau]}.
\]

在线模型：

\[
q_\theta(u\mid S_{t-1},R_{\le t},a_{<t})\approx p^*(u)
\]

在推理时禁止读取未来。创新不在 KL 或某一项 loss，而在 teacher target 来自多个候选世界的**真实、版本化执行结果**。

D-026 保留即时判断：t 时刻只使用截至 t 已获得的信息；下一帧真正到来后可以更新判断并修订记忆，不能把后来的修订计作先前已经正确。证据不足时仍可 QUARANTINE；当前不加入固定延迟一帧的设置。白话说，现在按已经看见的判断，下一眼看清后再改，原先的判断和时间仍然保留。

## Projective Node Orbit

世界节点不是 observation features 的 EMA，而是 canonical world latent \(m_j\) 在具身视角变换下形成的轨道：

\[
z_{t,i}\approx\Pi(T_t,m_j),\qquad
\mathcal O(m_j)=\{\Pi(T,m_j)\mid T\in\mathcal T_{\mathrm{reachable}}\}.
\]

首篇固定视觉 backbone、depth、pose 和 region proposals。Projective Node Orbit 是 CPMT 的表征基础，不单独包装成第一主创新。

## 事务层级

- PRESERVE：NOOP；
- ASSOCIATE：BIND，或对 dormant node 执行 REACTIVATE；
- EXPAND：BIRTH；
- REVISE：RELINK、RETRACT、SPLIT、MERGE；
- REPLACE：RETRACT + BIRTH 的复合程序；
- QUARANTINE：低置信度 commit wrapper，只暂存 evidence，不修改 persistent world。

这些是竞争性世界解释，不是独立分类头。所有程序最终编译为 deterministic primitives，再由 versioned executor 检查 precondition、provenance、protected state、rollback 和 graph invariants。

## 论文硬条件

若 full CPMT 无法优于以下两项，主创新判定失败：

1. direct transaction classifier + future auxiliary loss；
2. future scorer without post-edit execution。

首篇只回答：**执行候选世界后形成的未来监督，是否比不执行的 future loss 更能学习长期记忆修订。**

## 四个里程碑

| 阶段 | 唯一问题 |
|---|---|
| M0 | 事务语义和 executor 是否确定、合法、可回滚 |
| M1 | hard-condition 中 CPMT 是否优于新 loss 与无执行 scorer |
| M2 | 固定感知前端下，online CTL 是否减少具身长期记忆污染 |
| M3 | 结论能否在一个 external/现实来源复现并形成论文 |

主动消歧、第二应用领域、learned candidate generator、端到端 backbone 和大规模导航均不属于首篇。

## 当前进度与实验记录

只维护 [EXECUTE.md](EXECUTE.md)：顶部看当前阶段/下一步，下面按事件追加配置、run、结果、失败与人工事项。本 README 只介绍研究设想，不代表所有模块都已实现或有效。

新开对话继续读写同一记录，不新建交接/进度/周报文件；旧结果报告作为当时快照保留，不能覆盖最新看板。旧 PSLM 备份 archive/pslm-pre-ctt-20260904 / eba4339 仅为历史。

## 从哪里开始

新对话可使用 [固定提示](docs/NEW_CHAT_HANDOFF_PROMPT.md)，它只跳转到实验记录，不再复制状态。

1. [实验记录与看板](EXECUTE.md)：唯一日常入口；
2. [研究合同](docs/01_research_contract.md)：claim 与失败条件；
3. [CTL experiment](experiments/counterfactual_transaction_learning/README.md)：CPMT 的核心学习实验；
4. [人工确认表单索引](docs/human_confirmation/README.md)：需要时查看，不是第二进度页；
5. [claim–evidence ledger](docs/CLAIM_EVIDENCE_LEDGER.md)；
6. [decision log](docs/DECISIONS.md)。

## 科研诚信

- proposed、implemented、validated、failed 不得混用；
- test 不用于调阈值、选模型或重写主指标；
- future evidence 只进入 hindsight training/evaluation；
- advisor 或模型评价不是 ground truth；
- 失败案例、空结果、运行错误和不支持假设的结果全部保存。
