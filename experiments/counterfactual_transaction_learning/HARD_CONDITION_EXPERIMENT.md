# M1 Hard-condition Experiment

## 唯一目的

排除“CPMT 只是 direct transaction classifier 加 future loss”的替代解释。在该实验通过前，不投入完整视觉训练。

## Paired latent worlds

每对 case 在决策时拥有相同或受控等价的 prior memory 与 current regions，但隐藏世界状态不同，未来 evidence 支持不同 transaction。生成器只控制 appearance aliasing、occlusion、pose noise、real change 和 protected distractors。

## 六个方法

| ID | 方法 | 执行候选 | future supervision | post-edit world |
|---|---|---:|---:|---:|
| A | CPMT-CTL Core（M1 固定解析表征） | 是 | 是 | 是 |
| B | Direct classifier | 否 | 否 | 否 |
| C | Direct + future auxiliary loss | 否 | 是 | 否 |
| D | Execute + current-only | 是 | 否 | 是 |
| E | Future scorer without execution | 否 | 是 | 否 |
| F | Oracle candidate/program | 是 | 是 | 是 |

## 公平性

- A–E 相同 front-end、split、可见字段、优化步数和合理参数预算；
- A/D 相同 candidate K；
- B/C/E 输出相同 intent/template/argument space；
- C 获得独立合理调参；
- F 只作为 coverage/teacher upper bound；
- 报 wall-clock、显存、失败 run。

## Primary contrasts

- A vs C：执行后世界是否超越 future auxiliary supervision；
- A vs E：真实 graph intervention 是否必要。

D 诊断 future evidence；F 分解 candidate coverage 与 scorer error。

## 固定判定

- A>C 且 A>E，并改善 graph correctness/contamination：支持 CTL；
- A≈C：新 loss 解释未被排除；
- A≈E：执行器不是学习必要机制；
- F coverage 低：candidate proposer 问题，暂停 scorer 结论；
- 只改善 latent loss：不支持 persistent-memory claim。

数值 threshold、CI 和 effect size 在 test 前冻结。

命名边界：这里的 A 不是完整视觉 Full CPMT。它只包含 versioned world graph、候选真实执行、固定解析投影和 CTL；Projective Node Orbit 尚未接入。Full CPMT 这个名字保留给 M2 的“PNO＋world graph＋executor＋CTL”。


## M1-v3 pre-test lock candidate（D-039 accepted，尚未重新冻结）

机器可读合同为 [`configs/m1_hard_condition.json`](../../configs/m1_hard_condition.json)。D-031 冻结的 M1-v1、D-034/D-038 的 v2/v5 数值只作为历史诊断保留；D-039 接受 conformance 修复、live energy 与两条架构臂后，活动状态仍为 `pretest_lock_candidate`。这不是 formal run，配置中的 `test_access=false` 仍由校验器强制检查；完成实现验证并另行接受重新冻结前，不得生成或读取 test。

### 数据与 future

- C00–C11 **每个 family**分别生成 1000/200/200 个 train/validation/test paired groups，即三个 split 总计 12,000/2,400/2,400 groups；CLI 不再把该值解释为混合总数。同一 `paired_group_id + world_seed + asset_family` 不跨 split，每个 family 的 test support 不低于 200。连续 rollout 必须实现配置里的全部 12 个 family，coverage gate 对缺失 family 直接失败。只排除在任何方法运行前就已确认的 schema 或生成/渲染失败；方法自身失败必须保留。
- 主 future horizon 固定为实际已执行轨迹中**当前决策之后**的 3 个后续决策点，不能把 now 的当前步重复计入 future；H=1/5 只作报告型消融。变长 episode 只评分真实存在且 pose/visibility 有效的 future；至少有一步 future 的尾部样本保留并 mask 缺失步，零 future 样本只进 online 诊断，不训练 hindsight teacher。
- 可见正证据与“可靠可见但为空”都进入评分；遮挡和未观察区域 mask。预计算 online feature 只允许时间戳不晚于当前决策，future cache 分目录保存。
- exact ambiguity 固定为一对 online 字节相同、reference 分别为 RELINK/NOOP 的 sibling；下一步实际到达的相关可见证据构成一次有界 recovery revisit。revisit 只检查三步 lookback 内受影响子图，仍用同一 deterministic K=16，不能扩成全图异步搜索。

白话：future policy 解决“老师到底能看哪几眼”的问题。输入是机器人后来真实走过并看到的帧、位姿与可见性，输出是哪些后续证据可给离线老师评分。例如三步后回看旧桌面且明确为空，可以反对仍保留旧位置的候选；被柜门挡住则不算空。它不等于在线模型预知未来，也不等于拿计划但未执行的动作当真实证据。

### 候选、教师与六方法公平性

- A/D/F 共用 deterministic top-K，K=16；覆盖 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE，REPLACE 仍是 RETRACT+BIRTH，QUARANTINE 仍是不改 persistent world 的 wrapper。SPLIT/MERGE/RETRACT 必须有正例。
- 每个候选从同一 immutable base 克隆执行，先按 canonical memory-state equivalence 去掉纯改名重复；固定 K=16 槽位、顺序和失败审计不因预检改变。A–E 在训练归一化、online softmax、共享 calibration 和 commit selection 前共用 `transaction_static_preflight_v1` admissibility mask；预检拒绝项概率为 0，但不删除候选或 failure。
- static preflight 只读 immutable prior world、candidate program、截至当前的 online evidence 和 protected IDs，不读 future、candidate post-world、executor failure 或 `candidate_legal`。reference 必须通过且每行至少保留一个候选；preflight pass 只表示执行结果未知。A/D/F 真实执行后的 illegal 正无穷 mask 和六项能量记录继续保留，`remaining_executor_illegal_candidates` 每次报告。
- 执行式教师逐候选保存 now/future/edit/growth/collateral/illegal。`now` 是候选执行后世界对当前有效在线观测的投影 mismatch，`future` 比较 current active semantic world 与 open-memory evidence support；两者按每方法、每决策在该方法可用的 admitted 候选上分别做 z-score，执行式 teacher 另排除 executor-illegal，而 no-execution 方法不得借此读取 legality；raw/scaled 同时保存，closed history 只作审计。`collateral` 是合法事务是否改动 candidate 声明 evidence-affected subgraph 之外的 open-memory 事实；protected touch 仍直接 illegal。权重为 1/1/0.1/0.25/1，illegal 用正无穷 mask，temperature=0.25；train health gate 未过时不得现场调权重。
- A–E 共用 online encoder、输入字段、学生更新数和 split，训练参数量差异不超过 10%；每方法最多 6 次 validation trial。C 的 future auxiliary weight 可在 {0.1,1,10} 内独立选。E 的额外 scorer 参数、更新、耗时和显存单列，不能藏进共同预算。F 是 K=16 内 oracle upper bound，不是可部署模型。
- E 在目标构造和候选评分时都不执行非参考候选：它把每个 online candidate program 分别解析为 current/future 的关系、生命周期与证据关联查询；current target 只能读取 immutable prior、当前在线观测与 program 声明，future target 才从实际 reference future 产生稠密监督。两者都不得读取 candidate post-world 或复用 executor 给出的 outcome/legality/collateral。C 使用同一结构化关系目标作 direct auxiliary。评价 persistent memory 时，A–E 最终选中的单个事务仍由同一个 executor 应用。
- 同一份 v6 arrays 运行两条预登记架构臂：主臂 `cross_candidate_set_transformer_v1`（model dim 128、4 heads、两层 Set Attention Block、FFN 256）让候选在打分前相互比较；次臂是既有 hidden 64、两层 `shared_candidate_mlp_v1`。每条臂都完整运行 A–F，同一臂内 A–E 共享 encoder/student updates 并满足 10% 参数量门槛；禁止看结果后在两架构间择优。v5 的 1000 scorer steps 对 v6 两架构均失效，须重新用 train/inner-dev 选择 scorer/student 预算。
- validation paired groups 按 `paired_group_id` 的固定 SHA-256 奇偶拆成 calibration/report。只在 calibration 半区的 online rows 从登记网格选一组 A–E 共用的 commit probability/margin；report 半区只汇报，不能选阈值。counterfactual recovery training rows 只用于学习，不参与 gate calibration 或 report 分母。
- S1/S2 的 target/scorer 选择只使用 train 内按 paired-group 哈希固定留出的 inner-dev；整个 sibling 及其 recovery row 同进同出。它不消耗 validation trial，也不能用于最终效果报告。LOG-022 已查看过的 4-group validation report 只保留为历史开发结果，不再冒充 S5 的首次确认；S5 必须在 S4 登记后使用与它不重叠的新 validation confirmation groups。

白话：公平协议解决“CPMT 是否只是比对照多拿了答案或算力”的问题。输入是同一批 online 信息、同一候选语言和可核对的训练预算，输出是 A–F 可比的预测、运行成本与失败。例如 E 可以预测“RELINK 声称的新位置未来是否成立”，但不能先执行 16 个候选再偷看哪些合法；最终决定落地时仍和其他方法一样调用 executor。它不等于强迫网络结构一模一样，也不等于把 F 的 oracle 成绩当实际系统成绩。

白话：cross-candidate Set Transformer（候选间集合 Transformer）解决“候选共同竞争却彼此看不见”的问题。输入是当前世界上下文和同一行 K=16 候选，输出是经过候选间注意力比较的 16 个分数；例如两个 RELINK 只差目标位置时，可以直接比较相对证据。它不等于生成新候选、不改变 executor，也不让 online inference 读取 future。

白话：candidate-scoped current target（候选范围当前目标）解决 no-execution 对照缺少真实 now 信号的问题。输入是当前证据和候选声明，输出是候选声称的关系与当前观测是否一致；例如候选说杯子在桌上、可靠观测却显示桌面为空，就记 mismatch。它不执行候选、不读取 candidate post-world，也不等于 future target。

白话：共享 online admissibility mask 解决“一个候选在不改世界前就已违反版本、前置条件或 protected state，却只让执行式方法提前排除”的不公平。输入是当前记忆、事务文本、当前证据和 protected IDs，输出是在原 K=16 槽位上的允许/拒绝值；例如 BIND 明写要碰 protected node 时，A–E 都把它的 softmax 概率设为 0。它不等于执行候选、不产生 post-edit world、不保证通过项合法，也不删除 executor 的 illegal、failure 或 provenance。

白话：train/inner-dev（训练内开发留出）解决“需要调优化，但又不该提前消费 validation report”的问题。输入是原 train paired groups，输出是一组拟合 group 和一组只做 target/scorer 选择的留出 group；例如一对相同 online 输入、不同 future 的 siblings 必须一起被留出。它不是 test、不是正式 validation 成绩，也不允许把 inner-dev 调到最好后宣称方法已经泛化。

白话：structured relation-target oracle（结构化关系目标上限）解决“E 没学好，究竟是目标没有信息，还是 scorer 没学会”的问题。输入是每个候选从程序文本提出的关系查询、真实 reference future 给出的查询真假和 E 可用的声明成本，输出是在完美知道这些关系真假时的候选排序准确率。例如，若 RELINK 声称“杯子未来在水槽”且真实 future 支持它，oracle 给该查询零不一致；错误位置得到不一致。它不执行 candidate post-world、不是可部署模型、不是 F 的 transaction oracle，也不能作为 E 的正式成绩。

白话：target-only oracle（仅目标诊断上限）进一步把目标和能量组装拆开。输入仍是上述关系真假，但输出只按原始 masked mismatch 找到全部并列最小候选，并报告 reference 是否在其中、是否唯一、并列大小和均匀打破并列时的期望准确率。例如三个 RELINK 同分时记作三选一，而不是让数组里的第一个候选冒充正确。它不加 penalty、不标准化、不用 executor 合法性筛选，也不是新的 baseline。E scorer fit diagnostic（E 评分器拟合诊断）则分别在 train、validation calibration 和 report 上输出监督 masked BCE、关系二分类准确率和最终 teacher 候选准确率；它解决“训练没拟合”与“跨世界没泛化”的区分，不改变 E 的训练或推理。

白话：判别性/排序相关 BCE 诊断（planned）解决“总体 BCE 下降是否只来自对所有候选都一样的容易关系”。输入是 scorer relation logits、真实 reference future、relation/预检 mask 和候选声明，输出是 future truth 在候选间不同的位置、oracle mismatch 在候选间不同的位置各自的 BCE，以及 reference 对最佳错误候选的 probability/log-probability margin。例如只有正确 RELINK 支持新位置的坐标会进入判别性分母。它只用于 train/inner-dev 解释，不改变当前 pointwise BCE、不使用 reference index 训练，也不等于排序 loss 已被采纳或验证。

白话：exact-ambiguity capped diagnostic（精确歧义封顶诊断）把 relation oracle 在不可辨 sibling 上因读取真实 future 得到的成绩替换为成对最高 50%，其余 identifiable 行保持原 oracle 读数；它提醒读者 80.83% 的 future-reading oracle 不是部署目标，但不是 E 的严格理论上限。initial-step invalid rate（初始步非法选择率）只看尚未被自身错误污染的第 0 步，全轨迹 invalid rate 则保留错误复合后的失控程度；两者并报能区分“策略一开始就乱选”和“早期错误导致后续候选越来越不适用”，但都不把合法性喂回模型。

### 指标、统计与 go/no-go

- 主标签比例为 10%；0/1/10/100% 全部报告。正式优化种子固定为 7/19/31/43/59。
- 主指标定义为：active-graph correctness（执行所选事务后，当前开放的语义世界与 reference 一致，不因已关闭的旧错永久判零）；memory contamination（20 个 self-rollout 决策后，每 100 次决策仍开放的错误事实数）；false-birth growth（同一时点每 100 次决策多出的 open entity 数）；collateral violation（每 100 次决策对 protected/无关状态的修改数）。open-memory support correctness、完整 history exactness、contamination AUC、recovery-within-3、time-to-recovery 与 unresolved error 同时报告；history 不是主部署终态。
- primary contrasts 只有 A–C 和 A–E。每个 20-step endpoint 都横跨同一套 mixed registered schedule，因此 endpoint bootstrap 只有一个明示的 stratum；以 `paired_group_id` 为不可拆分单位做 10,000 次 paired bootstrap、95% CI。两项主对比用 Holm–Bonferroni 控制 family-wise alpha=0.05；逐步 family 结果另报，但不冒充 endpoint 分层。
- 每个主对比都必须同时达到：graph correctness 绝对提高至少 3 percentage points；contamination 每 100 决策绝对减少至少 2，且校正后 95% CI 排除零。false-birth 每 100 决策非劣 margin=1，collateral margin=0.5；executor invariant violation 必须为 0。
- candidate coverage@16 必须总体至少 98%、每 family 至少 95%；未通过时暂停 scorer/CTL 结论并归为 candidate miss。结果分别报告 candidate miss、teacher error、amortization error、rollout error。
- A 对 C 或 E 的 CI 若排除了上述最小有意义收益，则停止扩模型，不进入 M2；不得靠 PNO、更大数据或第二任务找正结果。

白话：最小有意义效应解决“统计上有一点差，但实际是否值得”的问题。输入是同一 paired group 上 A 与对照的逐例差，输出是平均差和不确定范围。例如 A 正确率高 3 个百分点且长期每 100 次少 2 个错误事实，才算达到预先认定的机制收益；只把 latent loss 降低不算。它不等于要求每个样本都赢，也不等于把四个指标揉成一个可以互相抵消的总分。

白话：safety 非劣门槛解决“主指标变好是否靠制造更多错误节点或误改旁边对象”的问题。输入是 false-birth、collateral 和 invariant 计数，输出是是否仍在允许差值内。例如正确率提高但每 100 次多建 3 个假对象会失败。它不是额外奖励项，安全失败不能被平均准确率盖住。

白话：有界恢复指标解决“后来看到反证时，系统能否把当前记忆修回来”。输入是歧义点落入**另一个 sibling reference 所代表的那条已构造错误状态**、下一次相关可见证据和固定 K=16 候选；输出分成 designed-pivot recovery-within-3、触发率、恢复耗时，以及另报的 arbitrary-first-error recovery。比如先在 RELINK/NOOP 二选一处走错，下一步看清杯子位置后关闭错边再 RELINK；原歧义步仍算错，history 也仍记录旧版本。若模型选了其余 14 个候选或更早已把世界改坏，该次错误会进入 out-of-scope 计数，不混入设计恢复分母。`delayed_contradiction_revisit` 只由生成器供评测定位且不进入 feature values，所以这里验证的是“给定这次预设重访后能否改正”，不是学习触发检测、retroactive credit、删除 provenance，也不是 Khronos 式全局慢路径。

### 计算边界

轻量静态/单元检查可在本地运行；用户已提示本机 CPU 负载可能诱发内存损坏，因此数据生成、完整测试、训练和 causal rollout 优先在 AutoDL 的干净 Git 提交上执行。仓库不设置固定单-run wall-clock 上限，只要求保存实际耗时、内存/显存、磁盘和失败；云实例由操作者手动启停并设置定时关机，仓库只记录该控制方式，不自行启动或续费实例。新宿主机发生 BugCheck 时仍停止长 run。

白话：计算边界解决“在哪台机器安全地跑”。输入是本地稳定性记录、服务器 wall-clock/显存和干净提交哈希，输出是本地只做轻检查、AutoDL 承担重任务。例如服务器 `git pull` 到指定提交后生成 arrays，再把 output 汇总拉回本地分析。它不等于允许脚本自行购买资源，也不等于服务器跑完就自动解封 test。
