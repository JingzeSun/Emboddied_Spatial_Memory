# CPMT 白话方法词典

状态：**方法解释文档；不代表对应模块均已实现或验证**。

这份文件是所有技术合同的中文入口。以后新增概念时，必须先在首次出现处写白话说明，再补充到这里。

## 一句话方法

机器人维护的不是“见过哪些图片”，而是一个带版本的内部世界。每次看到新东西，它提出几种竞争性的世界解释，分别在同一个旧世界的副本上真实执行，再用后续观测判断哪种修改最合理。训练期从这种比较中学习；部署时不看未来。

## 四个核心部分

| 名称 | 白话作用 | 当前状态 |
|---|---|---|
| CPMT | 整套“观察世界—尝试修改—比较结果—在线提交”的具身记忆方法 | 合同已定义，部分实现 |
| Projective Node Orbit | 判断不同视角下的观测能否由同一个世界对象解释 | proposed，未实现 |
| Versioned Deterministic Executor | 把候选修改确定地执行到世界副本，并保留历史或原子拒绝 | C00–C11 M0 slice 已实现 |
| Pending Memory Manager | 保存不够提交的低权重粗略认知，并支持归档、检索、重激活和消费 | D-023 M0 slice 已实现 |
| CTL | 用未来证据形成训练目标，让在线模型学习选择事务 | 小型合成开发版已训练；完整效果未验证 |

## Projective Node Orbit

### 它解决什么

同一把椅子从正面、侧面、远处或遮挡后看起来差别很大。直接平均这些 feature，可能得到一个任何真实视角都不像的模糊向量。Projective Node Orbit 允许同一个世界身份在不同视角下拥有不同但可预测的 observation latent。

### 输入和输出

- 输入：canonical world latent \(m_j\)、机器人/相机位姿 \(T_t\) 和可见性信息；
- 输出：该节点在当前视角下应该呈现的结构 latent \(\Pi(T_t,m_j)\)；
- 比较对象：实际观测区域 latent \(z_{t,i}\)。

公式：

\[
z_{t,i}\approx\Pi(T_t,m_j)
\]

白话说，同一个世界节点应该能根据机器人当前视角“变换成”与实际观测相符的 latent。

### 例子

机器人绕到椅子侧面，如果投影后的旧椅子 latent 仍能解释当前观测，就优先 BIND；如果相机运动解释不了椅子位置变化，才考虑 RELINK、BIRTH 或 REPLACE。

### 它不是什么

- Orbit 不是机器人行走轨迹；
- 不是保存更多图片或简单多 prototype；
- 第一篇不要求生成 RGB；
- 它是表征基础，不单独作为 CTL 的主学习创新。

## Observation region、world node 与 canonical latent

- observation region：当前帧中一次局部观测，例如一个 mask、框或 patch 集合。白话说，它是“机器人这一次看到了什么”。
- world node：长期世界中的身份记录，例如“椅子 A”。白话说，它是“机器人认为世界里持续存在什么”。
- canonical latent：不绑定某一个具体视角的世界表征。白话说，它是椅子 A 的内部底稿，而不是某一张椅子照片。

Observation 和 world 必须分开。一次 observation 可以绑定旧节点、创建新节点，也可能因不确定而暂存；不能未经事务直接写成世界事实。

## 事务层级

事务是长期记忆允许使用的受约束修改语言。

| Intent | Template | 白话解释 |
|---|---|---|
| PRESERVE | NOOP | 当前证据不足以改变长期世界 |
| ASSOCIATE | BIND | 当前观测属于 candidate/confirmed 旧节点 |
| ASSOCIATE | REACTIVATE | 当前观测属于 dormant 历史节点 |
| EXPAND | BIRTH | 旧节点都解释不了，建立 candidate 新身份 |
| REVISE | RELINK | 身份不变，但位置、拓扑或关系改变 |
| REVISE | RETRACT | 可靠证据否定一个旧事实/关系版本；普通空观测不否定对象身份 |
| REVISE | SPLIT | 一个旧节点错误混合了多个真实身份 |
| REVISE | MERGE | 多个旧节点其实是同一个真实身份 |

这些不是八个互不相关的分类头，而是对当前世界发生了什么的竞争性解释。

### REPLACE

\[
\mathrm{REPLACE}=\mathrm{RETRACT(old)}+\mathrm{BIRTH(new)}
\]

白话说，原位置的旧椅子离开后换成了另一把椅子：保留旧椅子的身份档案，先关闭“旧椅子仍在原位置”这条事实，再创建新身份并记录新位置。它不同于 RELINK；RELINK 表示还是同一把椅子。

### 事实级 RETRACT 与 reliable absence

当前 ordinary RETRACT 的对象是 fact/edge version，不是 object identity。node-level RETRACT 只适用于未来有可靠证据证明某个身份本身是幻觉或错误建档的情况，目前没有实现。

要关闭“椅子 A 位于左侧”这条事实，至少需要两条 online `visible_empty` 证据。它们必须来自不同的时间—视角组合，pose/depth 有效，可靠度达到阈值，而且两条空观测之间不能又看到椅子支持原事实。遮挡、视野外、单次漏检、低可靠观测都不够。

白话说，“没看见”不等于“不存在”。只有机器人至少两次确实看清原位置是空的，才允许把旧位置记录截止；椅子 A 的身份和历史仍然保留。

### QUARANTINE

QUARANTINE 是提交策略，不是世界事务。这里的“看不清”指多个合法事务解释仍无法可靠区分，不单指图像模糊。当最高 posterior 未达到 commit probability，或第一名与第二名的 margin 太小时，evidence 进入独立 pending memory，不修改 persistent world。

pending record 保存原始 evidence、粗略 latent、可用的空间键、语义提示、低权重支持和候选假设历史。低质量证据仍可与后续观察关联；同一 time/view 的重复证据保留，但不重复增加独立支持。

K 不是普通帧 TTL。只有机器人确实再次观察相关区域，而且这一视角理论上能够区分候选解释时，才算一次 relevant opportunity。K 次仍未解决时，记录从 active_pending 变为 archived_unresolved；它仍然可检索，新证据可以把它重新激活。正式事务使用这些证据时，必须把 evidence IDs 和 consumed_by_transaction 写入审计记录。

白话说，机器人选择“先记在可搜索的草稿箱里，暂时别改正式档案”。多次真正回看仍无法决定，只把便签放入低优先级归档，不撕掉。NOOP 表示确信无需改世界；QUARANTINE 表示现在还不敢决定。

### SPLIT 与 MERGE 为什么不对称

SPLIT 面对的是一个本身就错误的混合身份，所以关闭并 retracted 旧 node，再建立两个或更多 candidate successors。原 evidence 和本次 evidence 必须在 successors 间恰好出现一次；不能丢、不能重复。旧 aggregate latent 已经混合，不能直接复制给任何一个 successor。

MERGE 面对的是同一身份的重复档案，其中通常存在可保留的稳定 ID。因此从 confirmed sources 中保留最早建立的 ID；建立时间相同时按 node_id 排序。其他 IDs 变成 alias，历史版本不删除，全部 evidence 和 latent 引用汇入 canonical 新版本。

白话说，SPLIT 是“旧档案内容混错，重新建档”；MERGE 是“多个档案重复，归到最早的正式档案”。当前实现只验证版本和引用集合，不表示已经学会怎样生成正确 latent。

## Identity lifecycle

| 状态 | 白话解释 |
|---|---|
| candidate | 新建但尚未充分确认的身份 |
| confirmed | 已经获得足够支持的身份 |
| dormant | 暂时退出活跃匹配池、但允许重激活的身份 |
| retracted | 已被可靠证据否定，不能直接复活的身份 |
| alias | MERGE 后保留、指向 canonical identity 的旧 ID |

valid_to 表示某个版本何时结束，不是 lifecycle。一个 identity 可以有多个历史版本，但同一时刻至多有一个 open version。

BIRTH 只产生 candidate。后续 BIND 带来至少第二条独立 evidence 后，program 才可显式升级为 confirmed。confirmed 长时间未被观察时，可以由非学习型维护规则转为 dormant；它仍保留身份、latent、evidence 和历史。

## Candidate program 与 primitive

- candidate program：一次完整的世界解释，例如“把当前观测绑定到椅子 A”；
- primitive：executor 真正执行的小操作，例如创建节点、关闭版本、增加边、附加 evidence。

白话说，candidate program 像数据库事务，primitive 像事务里的逐条命令。论文比较的是完整事务执行后的世界，不是单独给某个 primitive 打标签。

## Versioned Deterministic Executor

### 输入和输出

- 输入：immutable base world、一个 candidate program、protected IDs；
- 输出：合法的新世界版本，或者明确的拒绝原因；
- 相同输入必须产生相同输出。

### 必须保证

- 所有候选从同一个旧版本复制；
- 失败时不留下半个修改；
- 不物理删除旧版本；
- 每次修改都记录 provenance；
- 受保护节点不得被附带修改；
- graph hash 能发现内容被偷偷改变；
- 重复 transaction 必须幂等或明确拒绝。

白话说，它是一台严格的“世界修改模拟器”。它本身不负责猜哪个候选正确，只保证每种假设真的被执行并且可以审计。

## Counterfactual Transaction Learning

### 训练期

每个候选事务 \(u\) 都在同一个旧世界副本上执行，得到：

\[
S_t^{(u)}=\operatorname{Execute}(\operatorname{Clone}(S_{t-1}),u)
\]

白话说，系统分别假设“这是旧物体”“这是新物体”“旧物体移动了”，看看每种假设会把内部世界变成什么样。

然后按执行后世界的当前解释能力、未来解释能力和修改代价计算能量：

\[
E(u)=D_{\mathrm{now}}+D_{\mathrm{future}}
+C_{\mathrm{edit}}+C_{\mathrm{growth}}
+C_{\mathrm{collateral}}+I_{\mathrm{illegal}}
\]

白话说，既要解释现在和未来，也要避免乱改旧事实、乱建节点、伤及无关内容或执行非法操作。

能量越低，候选在 hindsight posterior \(p^*(u)\) 中概率越高。这个 posterior 是训练目标，不是人工事务标签的简单替代名称。

### 部署期

在线模型 \(q_\theta\) 只读取当前世界、历史/当前观测和过去动作，不能读取未来。

白话说，训练时老师可以用未来检查答案，真正运行时学生必须在当下做决定。

## 六个能量分项

| 分项 | 白话含义 |
|---|---|
| now | 修改后的世界能否解释当前观测 |
| future | 修改后的世界能否解释后续视角 |
| edit | 是否无必要地改动已有事实 |
| growth | 是否无必要地创建新节点 |
| collateral | 是否破坏了与当前问题无关的正确内容 |
| illegal | 是否违反前置条件、版本或图约束 |

不能只保存 total；每一项都要单独记录，才能知道方法失败在感知、候选、执行还是权衡。

## Hindsight teacher 与 online model

- hindsight teacher：训练时执行候选并查看未来，形成 \(p^*(u)\)；
- online model：部署时不看未来，学习逼近 teacher 的选择。

白话说，teacher 是“事后复盘者”，online model 是“现场决策者”。如果 online 输入意外包含未来信息，实验无效。

## Oracle、candidate coverage 与 equivalence

- oracle program：人工规则或 simulator hidden state 给出的可执行正确事务，仅用于检查机制上限；
- candidate coverage：正确解释是否出现在候选集合里；
- oracle equivalence：多个执行顺序不同的程序可能得到语义等价的世界，不能强迫只有一个字符串标签正确。

白话说，如果正确答案根本没进入候选集合，不能把责任算到 teacher 或在线模型上。

### Graph-equivalence 的身份对应层

当前已实现的第一层只回答“左右两个执行结果里的身份怎样一一对上”。有锚点或未被声明为可交换的旧身份必须保持不变；只有策略明确声明、整体对称的旧身份集合才允许内部换名。共同 base 之后新建、且没有外部锚点的 local identity 可以改名，但必须是一对一、覆盖全部新身份的严格双射；新身份绝不能映射成旧身份。

白话说，旧档案不能随便换人，新档案叫什么可以不同，但左右两边必须能逐个配对，不能少一个、多一个或把新人冒充老人。这里的“严格”约束的是身份配对，不要求同一节点内部的正面和侧面观测产生完全相同的 raw latent。

### Canonical memory-state equality

D-025 将 graph-equivalence 收紧为“同一时刻的规范化记忆状态相等”。它只消除新 local ID 名称、transaction/operation 等审计编号和列表排列差异；映射后的 lifecycle、版本历史、事实/关系、证据和 latent 引用归属、protected state 与 pending memory 必须一致。任何可能影响后续 BIND、BIRTH、RELINK 或 RETRACT 的差异都不能合并。

白话说，这不是要求世界永远不变，而是判断从同一个旧世界分叉出来的两种程序写法，在当前时刻是否真的留下了同一本档案。下一帧到来后，这本档案仍然可以继续扩张或修订。未来几帧看起来相似只能影响候选的 `D_future` 分数，不能用来宣布两个内部世界相同。

同一节点可以保存数值不同的多视角 latent；但是比较同一次候选分叉时，两边把哪些 evidence/latent refs 分给了哪个节点必须一致。Projective Node Orbit 的数值容差不属于 graph-equivalence。

## Hard-condition experiment

核心对照是：

- CPMT-CTL Core：M1 在固定解析表征上执行候选世界，再用未来评分；
- direct classifier + future loss：直接预测事务，future 只是辅助 loss；
- future scorer without execution：看未来，但不真正修改和比较世界。

白话说，这个实验要排除“只是多加一个 future loss”和“只是在候选上打分”两种解释。CPMT-CTL Core 如果不能优于它们，就停止主创新 claim，不继续用 PNO 扩成 Full CPMT。Full CPMT 特指后续同时包含 Projective Node Orbit、world graph、executor 和 CTL 的完整系统，不等于当前解析投影版本。

## 关键错误与指标

- candidate miss：正确事务不在候选中；
- teacher error：正确事务存在，但 hindsight teacher 排错；
- amortization error：teacher 排对，但 online model 没学会；
- memory contamination：错误观测或错误关系进入长期世界；
- false-birth growth：同一对象被反复创建成多个节点；
- collateral violation：修一个局部问题时破坏了无关正确内容。

白话说，最终不能只报一个 accuracy；必须说明错误发生在“没提出正确答案”“复盘判断错”还是“在线模型没学会”。

## 实现与证据的边界

本词典解释概念，不重复维护当前实现/测试数/待定事项。它们统一在 [实验记录](../EXECUTE.md)。确定性规则可执行、小型网络可训练、完整方法有效，是三种不同证据，不得相互替代。

## 首轮学习开发术语

MLP 是小型多层感知机，输入已经获得的世界/历史/当前特征，输出三种事务概率；例如根据旧位置空了来判断物体移动。它是实际训练的网络，不是大视觉模型。

解析教师用已知玩具世界投影比较候选结果与未来；学生只看截至当前的信息。不可辨识配对表示两个案例全部在线输入一样、未来却不同，例如被遮住的旧位置其实有或没有原物体；这种题不能凭学习神奇答对，未来教师也不能打破在线信息上限。

开发实验是检查数据、训练、评估是否能连起来的小规模试运行，不是正式论文测试。四种对照、CE/KL/MSE 损失、NLL/Brier、提交率、单次事实错误、数据和算力指标均在 [开发合同](../experiments/counterfactual_transaction_learning/DEVELOPMENT.md) 附输入输出、例子与局限；[首轮结果](../experiments/counterfactual_transaction_learning/DEVELOPMENT_RESULTS.md) 记录实际表现。新增方法的完整白话说明以该合同为补充，不把玩具投影当成 PNO。
