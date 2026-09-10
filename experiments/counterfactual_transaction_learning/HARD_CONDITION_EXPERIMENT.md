# M1 Hard-condition Experiment

## 唯一目的

排除“CPMT 只是 direct transaction classifier 加 future loss”的替代解释。在该实验通过前，不投入完整视觉训练。

## Paired latent worlds

每对 case 在决策时拥有相同或受控等价的 prior memory 与 current regions，但隐藏世界状态不同，未来 evidence 支持不同 transaction。生成器只控制 appearance aliasing、occlusion、pose noise、real change 和 protected distractors。

## 六个方法

| ID | 方法 | 监督/上限构造执行候选 | future supervision | post-edit world |
|---|---|---:|---:|---:|
| A | CPMT-CTL Core（M1 固定解析表征） | 是 | 是 | 是 |
| B | Direct classifier | 否 | 否 | 否 |
| C | Direct + future auxiliary loss | 否 | 是 | 否 |
| D | Execute + current-only | 是 | 否 | 是 |
| E | Future scorer without execution | 否 | 是 | 否 |
| F | Oracle candidate/program | 是 | 是 | 是 |

表中“执行候选”描述各方法的监督或上限构造，不表示共享候选生成与审计 runner 的系统调用次数。当前实现的执行边界和合成参考信息见 [研究合同](../../docs/01_research_contract.md#方法角色)。

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

- A>C 且 A>E，并同时改善 semantic active-world correctness、open-memory support 与全过程 open-fact error burden：支持 CTL；
- A≈C：新 loss 解释未被排除；
- A≈E：执行器不是学习必要机制；
- F coverage 低：candidate proposer 问题，暂停 scorer 结论；
- 只改善 latent loss：不支持 persistent-memory claim。

数值 threshold、CI 和 effect size 在 test 前冻结。

命名边界：这里的 A 不是完整视觉 Full CPMT。它只包含 versioned world graph、候选真实执行、固定解析投影和 CTL；Projective Node Orbit 尚未接入。Full CPMT 这个名字保留给 M2 的“PNO＋world graph＋executor＋CTL”。


## M1-v6 pre-test lock candidate（D-043 + D-044–D-047 evaluation overlay，尚未重新冻结）

生成/训练机器合同为 [`configs/m1_hard_condition.json`](../../configs/m1_hard_condition.json)，D-044–D-047 的 train-only 评价/预算 overlay 为 [`configs/m1_endpoint_viability_probe.json`](../../configs/m1_endpoint_viability_probe.json)。D-031 冻结的 M1-v1、D-034/D-038 的 v2/v5 数值，以及被 D-040/D-041 取代的 v6/v7 本地探针只作为历史诊断保留；D-039 的 live energy/两条架构臂、D-040 的混合组规模与真实 C10/C11、D-041 的 current fixed-range 与 posterior audit，以及 D-043 的 Pre-LN 与对称逐方法预算合并为活动 v8 实现。D-045/D-046 不改已有 train arrays 的生成内容/hash，只覆盖正式报告构念、AUC 持续等价门、endpoint probe gate、C 顺序权重选择与纯 validation confirmation；D-047 同样不改 arrays，只补 claim/scope 与由 probe 重建 audit 计算的 H3-vs-H1 teacher 机制报告。D-048 以组合登记完成 probe 后评测协议升级：`configs/m1_post_probe_registration.json` 绑定原生成配置、D-047 overlay 与已完成 probe 的规范化 JSON SHA-256；评测采用登记的 exact 与 test N=1350，其余 D-044–D-047 规则继承 overlay。原 v6 配置保留为已有数组的生成来源，不再单独代表全部活动评测设置。状态仍为 `pretest_lock_candidate`；这不是 formal run，组合合同锁定 `test_access=false`，完成实现验证并另行接受重新冻结前不得生成或读取 test。

### 数据与 future

- D-048 登记 train/validation/test 的计划规模为 1000/200/1350 个**总混合 paired groups**，合计 2550，不再乘 12；原生成配置的 test=200 是 probe 前来源快照，不得作为正式 test 的执行规模。test 生成入口尚未解封，S6 须接入登记配置并重新冻结后才可运行；CLI 的 `--paired-groups` 与 manifest 都使用这一总数语义。每个 group 的 20-step causal schedule 必须覆盖 C00–C11，因此已登记正式 test 中每个 family 计划有 1350 个独立 paired-group 支持；同一 `paired_group_id + world_seed + asset_family` 不跨 split。coverage gate 的分母固定为全部 12 个 family，任何 family 缺失即失败。只排除在任何方法运行前就已确认的 schema 或生成/渲染失败；方法自身失败必须保留。
- C10 不是 BIND 的统计别名：跨 paired groups 平衡生成当前观测同分布的 transient dynamic actor/NOOP 与 persistent background change/BIND，当前帧不能泄露以后是否持续。C11 必须在正确必要 BIND 之外包含一个通过 shared preflight、executor-legal、却改动当前 evidence scope 外既有开放事实的 BIND+collateral 候选。health manifest 必须保存基于真实 reference、观测有效性和 legal collateral contrast 的 behavior fingerprint；`scenario_variant` 不参与 fingerprint，任意两个 family 指纹重复、C10 缺任一变体或 C11 缺合法 collateral 对照都直接失败。
- 主 future horizon 固定为实际已执行轨迹中**当前决策之后**的 3 个后续决策点，不能把 now 的当前步重复计入 future；H=1/5 只作报告型消融。变长 episode 只评分真实存在且 pose/visibility 有效的 future；至少有一步 future 的尾部样本保留并 mask 缺失步，零 future 样本只进 online 诊断，不训练 hindsight teacher。
- 可见正证据与“可靠可见但为空”都进入评分；遮挡和未观察区域 mask。预计算 online feature 只允许时间戳不晚于当前决策，future cache 分目录保存。
- exact ambiguity 固定为一对 online 字节相同、reference 分别为 RELINK/NOOP 的 sibling；下一步实际到达的相关可见证据构成一次有界 recovery revisit。revisit 只检查三步 lookback 内受影响子图，仍用同一 deterministic K=16，不能扩成全图异步搜索。

白话：future policy 解决“老师到底能看哪几眼”的问题。输入是机器人后来真实走过并看到的帧、位姿与可见性，输出是哪些后续证据可给离线老师评分。例如三步后回看旧桌面且明确为空，可以反对仍保留旧位置的候选；被柜门挡住则不算空。它不等于在线模型预知未来，也不等于拿计划但未执行的动作当真实证据。

### 候选、教师与六方法公平性

- A/D/F 共用 deterministic top-K，K=16；覆盖 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE，REPLACE 仍是 RETRACT+BIRTH，QUARANTINE 仍是不改 persistent world 的 wrapper。SPLIT/MERGE/RETRACT 必须有正例。
- 每个候选从同一 immutable base 克隆执行，先按 canonical memory-state equivalence 去掉纯改名重复；固定 K=16 槽位、顺序和失败审计不因预检改变。A–E 在训练归一化、online softmax 和固定 `(0,0)` commit selection 前共用 `transaction_static_preflight_v1` admissibility mask；预检拒绝项概率为 0，但不删除候选或 failure。
- static preflight 只读 immutable prior world、candidate program、截至当前的 online evidence 和 protected IDs，不读 future、candidate post-world、executor failure 或 `candidate_legal`。reference 必须通过且每行至少保留一个候选；preflight pass 只表示执行结果未知。A/D/F 真实执行后的 illegal 正无穷 mask 和六项能量记录继续保留，`remaining_executor_illegal_candidates` 每次报告。
- 执行式教师逐候选保存 now/future/edit/growth/collateral/illegal。`now` 只把候选执行后世界投影回**当前有效匿名在线传感观测**计算 mismatch，禁止以 reference post-world 为 target；其 raw 值按传感器理论范围固定缩放：appearance 除以 2、appearance+place 除以 4、可靠空观测除以 1，保存 raw/natural-range/scaled，不按同行候选 spread 做 z-score。`future` 比较 current active semantic world 与 open-memory evidence support，仍按每方法、每决策对可用 admitted 候选做 z-score，以对齐执行式结构计数和 learned relation error 的不同单位。执行式 teacher 另排除 executor-illegal，而 no-execution 方法不得借此读取 legality；closed history 只作审计。遮挡或 pose/depth 无效时 now 被 mask，所以几何故障 C09 上 now 为零是正确的中性处理，不代表六项能量在每个 family 都有信号。`collateral` 是合法事务是否改动由当前 online observation/retrieval 在执行任何候选前确定、且对同行候选相同的 evidence-relevant subgraph 之外、执行前已经存在的 open-memory 事实；候选不能用自己的操作声明扩大 scope，新建事实仍由 growth 单独计费，protected touch 仍直接 illegal。权重为 1/1/0.1/0.25/1，illegal 用正无穷 mask，temperature=0.25；train health gate 未过时不得现场调权重。
- 同一架构臂内 A–E 共用同一个 `OnlineModel` 类、输入字段、K=16 槽位、candidate mask、参数模块/形状、batch 采样规则、optimizer、batch size、split 和完全相同的 12 格学习率/更新数搜索空间；训练参数量逐位相同，既有 10% 门只作冗余保险。允许每个方法用同一 train/inner-dev reference accuracy 规则从共同网格选择自己的 `(learning rate, updates)`，监督/loss 是刻意比较的变量。C 再在已冻结计算格上复用 weight=1 并补跑 future auxiliary weight 0.1/10，三者仍只用相同 train/inner-dev 选择并完整披露；这两条 C 独有路径明确记为不对称的强基线预算。validation 不再选择任何超参。E 的额外 scorer 参数、更新、耗时和显存单列，不能藏进 student 公平性。F 是 K=16 内 oracle upper bound，不是可部署模型。
- E 在目标构造和候选评分时都不执行非参考候选：它把每个 online candidate program 分别解析为 current/future 的关系、生命周期与证据关联查询。`candidate_scoped_current_relations_v1` 的输入是 immutable prior、当前在线观测与 program 声明，输出是“动作受证据支持、必要参数命中 query、区域可靠为空”三项监督；例如观察到可靠空区域且候选 RETRACT 的 edge query 命中时，当前关系支持该候选。argument cosine `0.8`、novel best `<0.6`、split best `[0.55,0.8)`、dormant/merge best/second `>=0.8` 均在运行前冻结。scorer 继续用 BCE 拟合 current/future relation truth；候选评分时，current 使用 `sigmoid(logit)` 与 desired bit 的平均绝对误差（固定 0–1），future 才做逐决策 z-score。它不等于事务标签，也不读取 candidate post-world、executor outcome/legality/collateral 或 future；future target 才从实际 reference future 产生稠密监督。C 使用同一结构化关系目标作 direct auxiliary。评价 persistent memory 时，A–E 最终选中的单个事务仍由同一个 executor 应用。
- `current_now_comparability` 审计只在 proxy 与 executed-now 都定义的同一 online 行、同一 admitted+executor-legal 候选集合上，分别报告 reference-in-minimum、unique、uniform-tie expected 和 mean tie size；缺失行另报。exact-ambiguity siblings 的 current target、mask 与 desired 必须逐字节相同而 reference 不同，且向 online payload 注入 audit-only reference/future 字段不得改变 target。该审计不强迫 proxy 弱于 executed-now，也不把 executor legality提供给 E 的训练或在线推理。
- `teacher_posterior_term_influence` 对 now/future/edit/growth/collateral 逐项做 leave-one-out，报告完整 posterior 的 total variation、KL、argmax 改变率和 reference 概率变化，并按 family 拆分。它以 CTL 真正蒸馏的概率分布为判据，不能只因第一名没变就宣称能量项无效，也不按影响大小调权重或设 gate。edit/growth 只称 registered minimal-world-change prior/regularizer，不因当前影响小而调大，也不称为已验证主机制。
- executed-now 的逐 family 预期模式在生成前固定：C01/C02/C04/C06/C07/C08 的 leave-now-out mean total variation 预期非零，C00/C03/C05/C09/C10/C11 按机制预期为数值零。manifest 同时报告实测集合和双向偏离名单；`1e-6` 只吸收 float32 posterior 重构舍入，不是效果阈值。偏离不进 health gate，也不触发权重调整。
- S1 对 E scorer 的 current 通道，在相同 fitting/inner-dev online 行、temperature 与 `now=1` 权重下，使用和 executed teacher 相同的 leave-current-out total variation、KL、argmax 与 reference 概率指标并排报告。C 共享 current relation auxiliary target，但没有单独组装 current-energy posterior，故不报告不存在的 C posterior 消融。两侧影响无需相等，结果不用于裁剪对照、调权或设 gate。
- 五个机制切片按固定优先级互斥分配：exact ambiguity、C10 temporal underdetermination、C11 side-effect sensitive、C09 current unavailable、其余 family。每片同时写明预期行为并报告 selection/commit/active/collateral；切片由生成器机制而非实测准确率定义，只作描述，不能替代完整 mixed 20-step causal endpoint 主门。
- 20-step self-rollout 是闭环在线评测长度，不是要求模型从第 0 步预测第 20 步：每一步都从方法自己的当前图重新生成候选、读取当步新观测、作一次事务决定，只有选中合法事务的执行后世界进入下一步。当前共享候选生成器与评测器均会展开候选作检查/审计，不能称整个系统只执行一个候选；online 网络本身不读取或生成候选 `post_graph`，共享 mask 来自静态预检。训练 hindsight 只回看之后最多 H=3 个**实际已观测且 pose/visibility 有效**的步骤，且每条候选分支会先继续执行期间实际登记的后续事务，再与对应已发生观测比较，不把当前图冻结后硬拿去对比第 3 步。未观测、遮挡或无效 pose/depth 不进入 future 分母。这是训练期对“哪个当前修订与紧随其后的真实观测更一致”的回溯监督，不是部署时输入未来，也不主张对任意外生变化进行远期预测。C10 刻意属于当前不可判定的信息上限切片，单步准确率预期约 0.5、A/C/E 不预期在该行凭空获得实例级先知能力；它检验 posterior uncertainty、quarantine 与 evidence-support 后果，不单独承载 CTL 优越性，也没有被解释成“预测 20 步未来”。
- M1 的 world event、观测顺序、pose bucket 与 controlled-revisit action history 由固定 seed 在方法运行前生成，并对所有方法保持一致；它们是外生输入，不由 online memory state 或模型分数选择。例如模型可以决定是否 RELINK，但不能决定下一步去哪个 pose 获取证据。因此本实验检验固定观测流下的记忆修订，不等于 active navigation、主动消歧或 learned action policy。
- D-047 把 H=1 从“配置里保留的一行”提升为 endpoint probe 与论文主文必报的 **teacher horizon contrast（教师视野对照）**。输入是同一 201 个完整 train/inner-dev paired groups 上已经真实执行的同一批候选；H=3 与 H=1 之间只截短随后实际观测的反事实 trace，immutable base、候选顺序、当前证据、外生轨迹、now/edit/growth/collateral/illegal、权重与 temperature 全部不变。输出同时含两种 horizon 的 teacher/reference agreement、top-1 与 entropy，以及 H3-vs-H1 的 total variation、KL、argmax change 和 reference-probability shift，总体和逐 family 报告，独立单位仍是完整 paired group。例如 H=3 只改变第二至第十六名概率而第一名不变时，TV/KL 仍会留下机制证据。它只回答“多两步已观测 future 是否改变 executable teacher 的软分布”，不等于重训一个 H=1 学生、不新增方法或 co-primary，也不参与 endpoint switch、test N、超参数和 M1 pass/fail；若结果弱或为零，必须在主文披露并收窄多步 future 机制解释，不能调权重或改变 A-vs-C/E 规则。H=5 继续是次级报告型扩展，不承担这项主文义务。
- 同一份 v8 arrays 运行两条预登记架构臂：主臂 `cross_candidate_set_transformer_v1`（model dim 128、4 heads、两层 Pre-LayerNorm Set Attention Block、FFN 256、末端 LayerNorm、dropout 0）让候选在打分前相互比较；次臂是既有 hidden 64、两层 `shared_candidate_mlp_v1`。每条臂都完整运行 A–F，禁止看结果后在两架构间择优。按 D-043/D-046，两条架构各自在完整 1000-group train 的固定 inner-dev 上，以五 seed 扫描 learning rate `{0.0002,0.0006,0.002}` × scorer/student updates `{300,1000,3000,10000}`。E scorer 先按 reference candidate-ranking accuracy 选格；固定 scorer 后，A–E 在 C weight=1 锚点上各自按相同 reference-candidate selection accuracy 选择一个格，均值最高且精确平手时依次取更少 updates、更小 learning rate。每个 learning rate/seed 只训练一条到 10000 的固定轨迹并读取四个前缀；不得为任何方法扩格。C 的计算格冻结后，weight=1 结果直接复用，只在同一格为 0.1/10 各补一条路径；同一 group-first/五 seed 均值最高，精确平手优先 1、再取较小权重，不做 36 格联合搜索。正式选择之外，同一批 12 格必须报告 A–E 共享格和 A/E 交叉格结果。10000 胜出时接受并标记 grid ceiling，不得事后扩展。
- D-045/D-046 已 supersede 旧的 validation shared raw-softmax gate：endpoint probe 与后续 M1 正式主比较固定 `commit_probability=0, margin_threshold=0`，A/C/E/F 的 COMMIT 请求率为 1；实际 `commit_rate` 还要求 executor legal，请求后 executor-illegal 的比例单列为 `executor_quarantine_rate`，三者满足 attempt=commit+quarantine。静态预检照常先 mask，执行后非法仍 deterministic QUARANTINE 且不改 persistent world。它不读取 validation 成绩、不按方法概率尺度调阈值；confidence/risk-coverage 只作诊断。相对旧 smoke，移除 E 的 confidence abstention 预计给其错误施加上行压力并可能扩大 A−E，但不是保证或选择依据。
- S1/S2 的 target/scorer/student-budget 与 C weight 选择只使用 train 内按 paired-group 哈希固定留出的 inner-dev；整个 sibling 及其 recovery row 同进同出。它不消耗 validation trial，也不能用于最终效果报告。新的 200-group validation 在全部设置冻结后只作一次纯 confirmation，历史 calibration bit 被忽略。LOG-022 已查看过的 4-group validation report 只保留为历史开发结果，不再冒充 S5 的首次确认。

白话：C auxiliary-weight 顺序搜索解决“要加强 direct-future 主基线，又不想让它获得 36 格联合择优空间”的问题。输入先是 C 与 A/E 共同的 12 格 weight=1 训练结果，输出一个冻结的 C learning rate/updates；再输入这个固定计算格上 `{0.1,1,10}` 的三组结果，输出一个 C weight。例如 C 先选中 `0.0006/3000`，就只在该格补跑 0.1 和 10，不回头试别的 learning rate。它不等于联合网格、不使用 validation，也不使 C 与其他方法的搜索完全对称；额外两条路径会单列成本。

白话：pure validation confirmation（纯验证确认集）解决“validation 既当泛化检查、又只替一个基线选权重”的角色混淆。输入是 train/inner-dev 已经冻结的所有模型设置和新的 200 个 validation groups，输出是只报告一次的完整泛化结果。例如 validation 发现 C 的另一权重可能更好，也不能重训或换权重。它不是 inner-dev、不是 test，也不是失败后继续调参的反馈集。

白话：公平协议解决“CPMT 是否只是比对照多拿了答案、模型或搜索机会”的问题。输入是同一批 online 信息、同一候选语言、同一架构臂和完全相同的 12 格预算，输出是 A–F 可比的预测、运行成本与失败。例如 A 和 E 可以各自选不同步数，但都不能多试一个 learning rate 或换一套网络；E 也不能先执行 16 个候选再偷看哪些合法。它不等于让监督机制相同——监督正是实验要改变的变量，也不等于把 F 的 oracle 成绩当实际系统成绩。

白话：cross-candidate Set Transformer（候选间集合 Transformer）解决“候选共同竞争却彼此看不见”的问题。输入是当前世界上下文和同一行 K=16 候选，输出是经过候选间注意力比较的 16 个分数；例如两个 RELINK 只差目标位置时，可以直接比较相对证据。它不等于生成新候选、不改变 executor，也不让 online inference 读取 future。

白话：candidate-scoped current target（候选范围当前目标）解决 no-execution 对照缺少真实 now 信号的问题。输入是当前证据和候选声明，输出是候选声称的关系与当前观测是否一致；例如候选说杯子在桌上、可靠观测却显示桌面为空，就记 mismatch。它不执行候选、不读取 candidate post-world，也不等于 future target。

白话：行为指纹解决“把普通 BIND 改名成 C10/C11 也能通过覆盖门”的问题。输入是实际 reference 行为、当前观测状态和候选执行后的 legal/collateral 事实，输出是每个 family 可比较的机制摘要与重复列表；例如 C11 只有真的出现合法但连带改错无关记忆的候选才算覆盖。它不把 family 标签喂给模型，也不证明模型已经学会该机制。

白话：同分母 now 审计解决“executed-now 缺失的行在一边算错、另一边算并列命中”的问题。输入是两条 now 通道共同可算的行和同一批审计候选，输出是覆盖、唯一性与均匀打破并列的期望准确率；例如 C09 几何无效时记 unavailable，不塞进任一方的胜负。它只是离线公平性审计，不是新的训练损失，也不会把合法性答案交给 no-execution 模型。

白话：current fixed-range（当前项固定自然量程）解决“候选几乎全并列时，小误差被 z-score 吹大”的问题。输入是当前投影原始 mismatch 与该传感比较的理论最大范围，输出是 0–1 的 now；例如 appearance 误差 0.1 除以自然范围 2 得 0.05。它不删除 now、不靠观察同行候选决定缩放，也不改 future 的单位对齐。

白话：posterior influence（后验影响）审计解决“第一名不变是否就等于能量项没用”的问题。输入是完整教师概率与去掉某一项后的概率，输出是 total variation、KL、argmax 和 reference 概率变化；例如正确候选仍排第一但概率从 0.4 升到 0.6，CTL 的软监督已经改变。它不等于新损失、不调权重，也不设置通过门槛。

白话：now family 预期模式解决“本该有 current 区分力的 family 在大 run 中悄悄退化”的问题。输入是每个 family 的完整与 leave-now-out posterior，输出是预期/实测零非零及偏离名单；例如 C07 变零会被点名，而 C11 为零符合预期。它不要求所有 family 都激活，也不是效果门。

白话：E/teacher 同尺 current 审计解决“相同权重不一定产生相同实际影响”的问题。输入是同一批 online 行及两侧各自的完整/去 current posterior，输出是并排的 TV、KL、赢家变化和 reference 概率变化；例如 E 影响比执行式 now 大或小都原样记录。它不强迫数值相等、不削弱基线，也不把 C 的辅助损失误称为候选 posterior。

白话：机制切片解决“既要解释 C09/C10/C11 的特定预期，又不能看完准确率才挑 family”的问题。输入是生成器事先登记的 family/ambiguity，输出是五个互斥描述性分组及 selection/commit/active/collateral 指标；例如 C10 因构造上当前不可判定而入组，不因模型碰巧得 0.5 才入组。它不把 family 标签喂给模型、不替代混合 20-step 主指标，也不用于事后择优。

白话：共享 online admissibility mask 解决“一个候选在不改世界前就已违反版本、前置条件或 protected state，却只让执行式方法提前排除”的不公平。输入是当前记忆、事务文本、当前证据和 protected IDs，输出是在原 K=16 槽位上的允许/拒绝值；例如 BIND 明写要碰 protected node 时，A–E 都把它的 softmax 概率设为 0。它不等于执行候选、不产生 post-edit world、不保证通过项合法，也不删除 executor 的 illegal、failure 或 provenance。

白话：train/inner-dev（训练内开发留出）解决“需要调优化，但又不该提前消费 validation report”的问题。输入是原 train paired groups，输出是一组拟合 group 和一组只做 target/scorer 选择的留出 group；例如一对相同 online 输入、不同 future 的 siblings 必须一起被留出。它不是 test、不是正式 validation 成绩，也不允许把 inner-dev 调到最好后宣称方法已经泛化。

白话：对称有限预算网格解决“复杂模型或某种监督只是没训练够”和“看到结果后无限加点”两个相反风险。输入是两种固定架构、五个 seed、三个 learning rate 和四个更新前缀，输出是每个架构的 E scorer 格以及 A–E 各自一个 student 格；例如 A 选 10000、E 选 1000 是同一 12 格中的对称调优，报告还会给出共享格和彼此预算下的 A/E 结果。它不等于 early stopping、不选择架构、不追加网格，也不使用 validation/test。

白话：Pre-LayerNorm（预归一化残差）解决注意力主臂可能因归一化位置而比 MLP 更难优化的问题。输入和输出仍是相同的 16 个候选表示，只把 LayerNorm 放到 attention/FFN 之前并在末端统一归一化；例如先规范候选 token 再比较，比较结果通过残差加回。它不增加模型可见信息、不改变 A–E 监督，也不保证主臂性能必然提高。

白话：预算不确定性诊断解决“最高格只比第二名高一点是否由少数序列造成”的问题。输入是选中格与确定性第二名在同一批完整 paired groups 上、先跨五 seed 平均的差值，输出是固定 10,000 次 bootstrap 的 95% 区间。它只解释选择稳定性，不改变最高均值与精确平手规则，也不是正式 A−C/A−E 效应检验。

白话：student-to-own-teacher agreement（学生复现自身教师第一名的一致率）解决“模型没学会”和“教师本身选错”难以区分的问题。输入是每种方法已固定的 teacher posterior 和 inner-dev 在线学生分数，输出是两边第一名是否相同；例如 E 教师选 BIND、E 学生选 NOOP 就记为 amortization error。D-043 后它只作诊断，不选择预算；它不把 future/teacher 提供给部署模型，也不是最终 causal 成绩。

白话：structured relation-target oracle（结构化关系目标上限）解决“E 没学好，究竟是目标没有信息，还是 scorer 没学会”的问题。输入是每个候选从程序文本提出的关系查询、真实 reference future 给出的查询真假和 E 可用的声明成本，输出是在完美知道这些关系真假时的候选排序准确率。例如，若 RELINK 声称“杯子未来在水槽”且真实 future 支持它，oracle 给该查询零不一致；错误位置得到不一致。它不执行 candidate post-world、不是可部署模型、不是 F 的 transaction oracle，也不能作为 E 的正式成绩。

白话：target-only oracle（仅目标诊断上限）进一步把目标和能量组装拆开。输入仍是上述关系真假，但输出只按原始 masked mismatch 找到全部并列最小候选，并报告 reference 是否在其中、是否唯一、并列大小和均匀打破并列时的期望准确率。例如三个 RELINK 同分时记作三选一，而不是让数组里的第一个候选冒充正确。它不加 penalty、不标准化、不用 executor 合法性筛选，也不是新的 baseline。E scorer fit diagnostic（E 评分器拟合诊断）则分别在 train、validation calibration 和 report 上输出监督 masked BCE、关系二分类准确率和最终 teacher 候选准确率；它解决“训练没拟合”与“跨世界没泛化”的区分，不改变 E 的训练或推理。

白话：判别性/排序相关 BCE 诊断（planned）解决“总体 BCE 下降是否只来自对所有候选都一样的容易关系”。输入是 scorer relation logits、真实 reference future、relation/预检 mask 和候选声明，输出是 future truth 在候选间不同的位置、oracle mismatch 在候选间不同的位置各自的 BCE，以及 reference 对最佳错误候选的 probability/log-probability margin。例如只有正确 RELINK 支持新位置的坐标会进入判别性分母。它只用于 train/inner-dev 解释，不改变当前 pointwise BCE、不使用 reference index 训练，也不等于排序 loss 已被采纳或验证。

白话：exact-ambiguity capped diagnostic（精确歧义封顶诊断）把 relation oracle 在不可辨 sibling 上因读取真实 future 得到的成绩替换为成对最高 50%，其余 identifiable 行保持原 oracle 读数；它提醒读者 80.83% 的 future-reading oracle 不是部署目标，但不是 E 的严格理论上限。initial-step invalid rate（初始步非法选择率）只看尚未被自身错误污染的第 0 步，全轨迹 invalid rate 则保留错误复合后的失控程度；两者并报能区分“策略一开始就乱选”和“早期错误导致后续候选越来越不适用”，但都不把合法性喂回模型。

### 指标、统计与 go/no-go

- 主标签比例为 10%；0/1/10/100% 全部报告。正式优化种子固定为 7/19/31/43/59。
- co-primary 定义为：semantic active-world correctness（当前开放的语义世界与 reference 一致）、graded open-memory support correctness（同一批开放记录连同 `evidence_refs` 的支持结构正确）与 `open_fact_error_auc_per_100_decisions`（二十步内额外开放边和缺失开放边的累计状态负担之和）。D-044 先以固定 train-only anchor 检查二值 active endpoint 是否对 A−C/A−E 都有分辨率；只在其退化且同构的 active graded endpoint 对两者均非退化时一次性切换，不能按赢家或效应方向挑指标。open-memory 与 open-fact AUC 分支固定，不随结果切换。false-birth growth、node-state error 与 collateral violation 是安全量；history exactness 只作 retained provenance 诊断。
- 旧 `memory_contamination` 的规范名是 `extra_open_fact_error`，即预测开放边事实集合中 reference 没有的项；相反方向叫 `missing_open_fact_error`。每步 extra 再拆为本步 pre-decision world 不存在的 `new_incorrect_open_fact_write` 和已存在但仍保留的 `retained_stale_open_fact`。例如本步把椅子写到错房间是 new write，下一步没撤销同一错边是 stale retention；两者每步相加严格等于 extra。它们不等于原始愿景中动态目标覆盖 static slot 的 Dynamic Contamination Rate（DCR）；M1 没有独立 dynamic/transient memory 与 decay，DCR、static retention、reappearance 和 viewpoint consistency 仍明确 planned for M2/M3。
- terminal normalized burden（归一化终点负担）按 `100×第20步错误状态数/20` 报告，AUC burden（Area Under the Curve，时间曲线下面积负担）按 `100×二十步逐步错误状态数之和/20` 报告。公式的白话作用是：terminal 只看最后还剩多少，AUC 会惩罚错误存活过的每一步，因此最后修好不会追溯抹掉前十九步。两者都不是“100 次决策中发生了多少次错误事件”的事件率。
- graded active-world correctness（渐进 active-world 正确度，当前为已实现的预备分支）对 exact endpoint 使用的相同开放节点/边语义记录计算多重集 Jaccard，即重复次数也计入的交集大小除以并集大小。输入是预测与 reference 的终点 active world，输出在 0–1 之间；例如只把一个 node lifecycle 改错时不会像 exact 一样直接只给 0，而会按整图记录中仍正确的比例给分。它满足 `graded=1` 当且仅当 exact=1，不是 edge-only contamination、不是 history exactness，也尚未在 D-044 探针前成为正式主指标。
- graded open-memory correctness（渐进开放记忆正确度）在开放 node/edge records 中保留 `evidence_refs` 后做同样的多重集 Jaccard，并单列 evidence attachment symmetric difference。例如 C10 的错误 BIND 没改 node lifecycle 或空间边、却把瞬时观察挂到长期节点上，active graded 仍为 1，但 open-memory graded 会下降。它不把 closed versions/provenance 当当前错误，也不声称 evidence 附着等于空间拓扑变化。
- 节点安全量 `active_node_state_error_per_100` 常驻统计 active node 记录的多重集对称差，非劣 margin 为 `1.0/100 decisions`；一个已有节点属性改错算一条正确记录缺失加一条错误记录多出。`false_birth_growth` 使用预测开放 entity ID 减 reference 开放 entity ID 的集合差，错删与错建不能用净基数互相抵消，并另报 missing open entities。既有 v8 train arrays 中的 `excess_nodes` 只为复用不可变训练输入保留，是 pre-D-045 净基数兼容字段，禁止进入正式 safety；正式 causal report 从图状态重算集合差。collateral 同时拆出 protected 与 unrelated 分量，主安全计数取两者逐步并集，避免同一步重复计数。输入是当前 active nodes、protected IDs 和候选执行前确定的 evidence scope，输出是节点语义错误、假出生及两类连带修改；它不把新事实 growth、closed provenance 或 illegal candidate 混作同一安全错误。
- recovery 条件比例始终与 eligible denominator 同报；分母为空时 JSON 值为 `null`，有 eligible 序列但成功数为零时才是 `0.0`。例如 F 从未犯 active error 时 arbitrary-first-error recovery 没有可评价样本，不能显示成“恢复率 0”。它不删除 out-of-scope 错误，也不把没有恢复机会的正确序列当失败。
- 正式 endpoint summary 只用规范正向名称；`post_graph_correct*`/`memory_contamination*`/`missing_open_facts*` 仅留在兼容明细，`unresolved_active_error` 只留作旧消费者 alias，不进入论文主表。这样输入仍是同一原始逐步状态，输出不会把 `history_exact` 误读为当前 post world，也不会把 exact 与其反极性重复算作两个发现。
- primary contrasts 只有 A–C 和 A–E。每个 20-step endpoint 都横跨同一套 mixed registered schedule，因此 endpoint bootstrap 只有一个明示的 stratum；以 `paired_group_id` 为不可拆分单位做 10,000 次 paired bootstrap、95% CI。两项主对比用 Holm–Bonferroni 控制 family-wise alpha=0.05；逐步 family 结果另报，但不冒充 endpoint 分层。
- 每个主对比都必须同时达到：最终由 D-044 train-only 开关选定的 exact 或 graded semantic correctness 绝对提高至少 3 percentage points；graded open-memory correctness 绝对提高至少 3 percentage points；`open_fact_error_auc_per_100_decisions` 绝对减少至少 40，且校正后 95% CI 排除各自最小效应边界。AUC 40 是 D-046 声明的 20 步持续等价门，对应平均减少 8 个错误开放事实×决策步暴露，不是从 terminal 做单位转换；它刻意要求改善贯穿轨迹，不能只靠末步修复。false-birth 与 node-state error 每 100 决策非劣 margin 均为 1，collateral margin=0.5；executor invariant violation 必须为 0。test paired groups 不再未经功效检查固定为 200：以 201 个 inner-dev groups 的三类 co-primary paired SD，正确度用 H0≤0.03/规划真效应 0.06，open-fact AUC 用 H0≤40/规划真效应 80，均取单侧 α=0.025、power=0.80，前瞻取三 endpoint × 两主对照所需最大值，至少 200 且向上取整到 10；探针观察到的 AUC 尺度或 SD 不得回调 40/80，确定 test N 后才生成 test。
- candidate coverage@16 必须总体至少 98%、每 family 至少 95%；未通过时暂停 scorer/CTL 结论并归为 candidate miss。结果分别报告 candidate miss、teacher error、amortization error、rollout error。
- A 对 C 或 E 的 CI 若排除了上述最小有意义收益，则停止扩模型，不进入 M2；不得靠 PNO、更大数据或第二任务找正结果。

白话：最小有意义效应解决“统计上有一点差，但实际是否值得”的问题。输入是同一 paired group 上 A 与对照的逐例差，输出是平均差和不确定范围。例如 A 的 semantic/support 各高 3 个百分点且每 100 决策累计 open-fact 状态暴露少 2，才算达到预先认定的机制收益；只把 latent loss 降低不算。它不等于要求每个样本都赢，也不等于把三类 co-primary 揉成一个可以互相抵消的总分。

白话：终点检验力规划解决“test 只有一次，却事先没检查 200 groups 能不能分辨全部 co-primary 登记效应”的问题。输入是固定 anchor 在 201 个 train inner-dev groups 上 semantic、support、open-fact AUC 的 A−C/A−E paired SD，输出是 formal test 应生成的最大 group 数；例如累计负担波动最大就由它决定 test N，而不是只替正确度供电。它不用 inner-dev 的效应正负判定 CTL 成败、不读取 test，也不改变 Holm 与 bootstrap 的正式规则。

白话：机制–指标覆盖矩阵解决“场景写进生成器了，但所有正式渐进量都看不见它”的问题。输入是 C00–C11 每个 reference row 的非 reference、预检通过且 executor-legal 候选，输出是 active、open-memory、evidence、节点/边和 collateral 哪些通道会变化。例如 C10 的相反 BIND/NOOP 必须由 open-memory/evidence 看见，C11 的指定连带 BIND 必须由 unrelated collateral 看见。它不要求把真正等价的每个程序硬判错，也不把 illegal 候选当部署成绩。

白话：safety 非劣门槛解决“主指标变好是否靠制造更多错误节点或误改旁边对象”的问题。输入是 false-birth、collateral 和 invariant 计数，输出是是否仍在允许差值内。例如正确率提高但每 100 次多建 3 个假对象会失败。它不是额外奖励项，安全失败不能被平均准确率盖住。

白话：有界恢复指标解决“后来看到反证时，系统能否把当前记忆修回来”。输入是歧义点落入**另一个 sibling reference 所代表的那条已构造错误状态**、下一次相关可见证据和固定 K=16 候选；输出分成 designed-pivot recovery-within-3、触发率、恢复耗时，以及另报的 arbitrary-first-error recovery。比如先在 RELINK/NOOP 二选一处走错，下一步看清杯子位置后关闭错边再 RELINK；原歧义步仍算错，history 也仍记录旧版本。若模型选了其余 14 个候选或更早已把世界改坏，该次错误会进入 out-of-scope 计数，不混入设计恢复分母。`delayed_contradiction_revisit` 只由生成器供评测定位且不进入 feature values，所以这里验证的是“给定这次预设重访后能否改正”，不是学习触发检测、retroactive credit、删除 provenance，也不是 Khronos 式全局慢路径。

### 计算边界

轻量静态/单元检查可在本地运行；用户已提示本机 CPU 负载可能诱发内存损坏，因此数据生成、完整测试、训练和 causal rollout 优先在 AutoDL 的干净 Git 提交上执行。仓库不设置固定单-run wall-clock 上限，只要求保存实际耗时、内存/显存、磁盘和失败；云实例由操作者手动启停并设置定时关机，仓库只记录该控制方式，不自行启动或续费实例。新宿主机发生 BugCheck 时仍停止长 run。

白话：计算边界解决“在哪台机器安全地跑”。输入是本地稳定性记录、服务器 wall-clock/显存和干净提交哈希，输出是本地只做轻检查、AutoDL 承担重任务。例如服务器 `git pull` 到指定提交后生成 arrays，再把 output 汇总拉回本地分析。它不等于允许脚本自行购买资源，也不等于服务器跑完就自动解封 test。

## D-048 probe 后登记与证据范围

白话：组合登记解决“已有训练数据的生成指纹不能改，但正式评测必须记住探针选定的终点和规模”的问题。输入是原 v6 生成合同、D-047 overlay 和已导出的固定 train-only probe，输出是绑定三者哈希的评测计划。例如旧 train arrays 仍按原协议 hash 验收，而新计划的 test groups 必须是 1350。它不是重新生成数据、不是以当前均值选指标，也不授权读取 test。`scripts/validate_m1_protocol.py` 校验组合登记；预算 runner 在读取 train arrays 前同样校验，报告同时保存来源协议 hash 和登记 hash。正式生成/评测入口未来必须消费该计划，不能只读来源 v6 配置。

登记固定 semantic=`final_active_graph_correctness`、support=`final_graded_open_memory_correctness`、burden=`open_fact_error_auc_per_100_decisions`，两个主对比均须满足 0.03/0.03/40；其余安全门、Holm/paired bootstrap、C 顺序预算与纯 validation confirmation 继承既有合同。不得因为当前 anchor 的累计负担较小而降低 40/80、换分母或改数据后继续复用本次登记。

TV（Total Variation，总变差距离）输入删项/截短视野前后的两组候选概率，输出分布差异；例如概率只在次优候选间移动，TV 仍可非零。它不等于贡献百分比或学生长期收益。H3-vs-H1 报告只检验多看两步对教师分布的影响，不检验 H=1 学生，也不能从它推出 teacher 纠正错误参考标签。数值结果只记 EXECUTE。

D-048 登记的 `execution_boundary` 明确覆盖旧 overlay 的 `naming_and_scope.online_model_execution_boundary`：候选生成和评测均展开全部候选，只有选中合法世界持久化。旧 overlay 字符串只为来源指纹保留，不能继续作为当前系统单次执行的依据。

## S5 固定配置训练与权重产物（D-049，等待服务器实现验证）

预算搜索完成后，以 [S5 training plan](../../configs/m1_s5_training_plan.json) 固定两臂各方法的 lr/updates、C weight、E scorer 配置和五 seeds。训练使用完整的 1000-group train 与原有 10% transaction label mask；原 201 inner-dev 在配置选定后纳入重训，之后不能充当独立验证。新 200-group validation 仍与历史已查看组隔离，只在模型设置冻结后作一次完整确认，不反向选 lr、权重或 checkpoint；test 仍封存。A–E 在同一架构内的输入、网络结构、数据与标签 mask 一致，更新数按已登记的逐方法选择执行；不得回退成统一 300/1000-step smoke 配置。

白话：这一步输入已选出的训练配方和完整 train，输出能在下一阶段直接加载的网络。例如 Transformer A 使用 0.0006/3000，C 使用 0.0006/10000 和 aux=1；MLP C 使用 0.002/10000 和 aux=10。它不是另一轮调参，不把训练分数当验证结果，不保证先前约 94% 的 inner-dev 数字在重训或连续评测中不变。

`run_m1_s5_train.py` 只训练/保存 50 个在线 student 和 10 个 E scorer，使用 CUDA、8 threads、两臂顺序执行；F 无需训练。每个模型原子保存 state_dict、模型构造参数、config、trace、模型 hash 与完整来源；成功产物按 plan/data/source/device 等绑定复用，未完成产物保留并要求先复核。E 的 train 教师分布同 checkpoint 保存，不通过独立 validation 产生或选择它；在线推理输入边界保持不变。单模型完成后才形成可复用产物，这不是中途 optimizer 状态续训。

白话：一个模型目录回答“训练的是哪套设置、权重是否完整、能否继续用”。输入训练完成的网络，输出模型文件及验收元数据；例如机器重连时已经完整保存的 A/seed7 不再训练。它不代表该模型科学上优于基线；当前训练记录不含正式 p95 或世界指标，这些留待独立连续评测。新实现须经服务器全测后运行，当前不授权 test、不改变原最小效应门，也不表示完整 S5/S6 evaluator 已接线。

## D-050：S5 保存模型独立确认接口（已实现，待服务器完整验证）

活动接线由 `configs/m1_s5_confirmation_plan.json` 固定。输入是 D-049 已验收的 60 个模型清单及既有生成/评测合同，输出先是新数据清单，再是两臂 20-step continuous confirmation 报告；两阶段由唯一 ops 入口分别交付。它不改变 M1 唯一主张，不意味着 S5 或 M1 已通过。

历史 validation 0–3 全部排除；新 validation 4–203 共 200 组，各含两条 20 步 sibling。原 validation namespace 与种子规则不变，不把新组号与 train 中同一整数编号视为同一世界。所有组一次进入确认，不再切 calibration/report，不用验证结果选择配置或换样本。例如旧第 3 组曾用于 scorer 诊断，不能因改了代码就称它从未看过；新第 4 组的两个 sibling 必须一起保留。这是数据隔离，不是采样优化。

生成阶段沿用既有候选/executor/编码器，以 16 workers 各自从路径读取合同、写完整配对组的 `audits.json.gz`、`learning.npz`、`summary.json`、`complete.json`。这些文件分别存完整参考审计（含六项能量及 future 分支）、诊断数组、健康/覆盖计数和指纹。输入是固定组号，输出是能复核的数据分片；例如第 4 组完成后重连只核对已有 hash。失败组保留并阻止进入评测，不得被别组替换。它不是并行评测或训练样本重生成。

评测阶段加载原 50 个 student，固定 CPU/1 thread 串行；F full-reference oracle 和单独的信息上限 oracle 各一次。每个模型的 200 组共 400 条完整轨迹、8000 次在线决策；每步采用上一步实际留下的世界。学习数组末尾没有 future 的在线行不会出现在单步教师诊断里，故该诊断行数可少于 8000；完整 causal 路径仍覆盖每条全部 20 步。它不表示遗漏主评测步骤，也不把诊断当独立模型选择机会。

`teacher_forced` 是固定正确参考历史的单步诊断，输入是相同参考历史下的当前在线向量，输出候选不可用率、教师与参考的不一致、student 与教师的分歧等；例如正确候选存在而 student 偏离教师，可定位学习/输入问题。它不证明教师总正确，不代替自有错误历史上的 rollout。生成的候选覆盖与执行教师健康逐 C00–C11 报告，当前预检、完整执行和最终选择边界沿用 D-047/D-048。

`audit_sink` 是选择后的可选审计回调：输入是已选定并持久化的世界和候选执行记录，输出压缩逐步 online 输入、程序失败、base/post hashes、候选概率和实际序列/sibling 标识。它不参与打分、不把 future/post-world 传给网络。参考 hindsight 能量保存在生成审计；分叉世界的回调记录不是重新形成训练教师。每个持久世界重新检查 invariant，失败保留并停止；正常候选的静态或执行拒绝仍作为已预期的非法候选记录，不能冒充持久世界损坏。

统计按原配对组单位汇总两 sibling 与五 seed，10000 次重采样；原 exact、open-memory、open-fact AUC 三项指标及 0.03/0.03/40 效应门、两主对照 Holm 校正和安全门不变。`s5_confirmation_report.json` 保存两个架构的逐方法逐 seed 指标与配对统计，供既定 S5 stop rule 复核；测试解封始终为 false，不自动启动 S6。

完整模型评测单元成功后写指纹并原子发布；中断单元保留 `.incomplete` 和失败原因，拒绝自动重试。`validation_trial.json` 在读取确认数据前记录模型、数据、方案、新评测源码与运行环境的绑定；数据目录另以排他创建的 `confirmation_consumption.json` 绑定唯一评测输出位置，换目录不能另开一次确认。评测不改写生成分片，只新增这一控制记录。输入是一次冻结考试，输出是可追溯的消费记录；例如第 12 个模型失败时，前 11 个结果不因重连丢失，也不能换参数重跑。它不是新的确认机会或可任意覆盖的临时缓存。训练源码保留原 hash，新评测源码另记，避免为了新增 evaluator 重训模型。

成本每模型单独记录 wall_seconds、CPU/1-thread 条件和 forward p95，不对多个 p95 求平均；该 p95 只覆盖网络与相关张量/概率处理，不是候选生成到执行结束的系统延迟。CPU 评测的 allocated VRAM 为 0，不能用它取代 CUDA 训练成本或声称整机无其他进程竞争。全部原始单元与失败留在服务器，最终 JSON 由仓库 exporter 带原始 training/evaluation/export provenance 导回。


### D-051 选参前的 train 错误分支工程检查

检查解决正确参考轨迹之外的记忆状态可能让候选构造中止的问题。输入为已验收 v7/v9 train 数据和 D-051 固定的 16 组、七种规则，输出为 224 条 20-step 轨迹的完整性结果及失败现场。例如连续 MERGE 后仍须能构造下一步候选；它不等于 CTL 学习效果验证，也不保证穷尽全部可达状态。

接口为 `run_m1_train_branch_preflight.py`，固定计划由 `m1_branch_preflight.fixed_plan()` 记录进产物。生成标记、协议、分片 SHA-256、生成提交和检查提交分别核验；生成生产模块不能发生未经审查的变化。重建 16 组 audit 的编码必须与已验收分片一致。`complete_branch_matrix` 表示组×sibling×规则无缺漏或重复；`preferred_template_unavailable` 表示偏好模板静态不可用、明确采用 NOOP 的次数；`minimum_c11_unrelated_candidates` 表示轨迹 C11 时最少范围外可用目标数。这些是工程诊断，不用于选模型或修改效应门。

选择器只接收候选 index/template/static_preflight_pass；legal/post_graph、reference、future 和教师分数不传给选择器。executor-illegal 保留世界的原行为不变；构造异常、K=16 坍缩或 invariant 失败保存当前图/event/已完成步数并停止该组，不吞错、不换样本。其他固定组继续留存结果；完整矩阵全部完成且无工程错误才能 PASS。

状态：生成已验收，检查器与轻量测试从隔离工程分支纳入，真实服务器检查尚未运行。按 D-052 使用同一版本的 `ops/m1_train_preflight.sh check` 与 `export`；导出成功仅说明报告被核验并写出，工程门以 `report.gate.pass` 为准。已有完成尝试复用，失败现场随导出保留，不自动重跑。未触碰 validation/test，未改变主终点、效应、安全 margin、N 或选参规则。


### 对象耗尽时的候选可用性（D-053，experimental；正式接入仍 planned）

参考数据仍使用原严格生成合同，K=16 去重与 C11 合法连带对照不能缺失。LOG-078 的失败发生在连续错误合并后的自有记忆，因此另提供显式诊断模式，区分“网络的 16 个输入槽位”和“当前真正构造出的事务”。`slot_status=unavailable` 表示该格没有可执行程序，`unavailable_reason` 记录配对不足、C11 无目标、SPLIT 无证据或 canonical 重复；它的共享准入值恒为 false，`post_graph=null`、`execution_attempted=false`。兼容记录中的 `legal=false` 只用于拒绝选择，不应统计为执行器实际尝试后的非法事务。所有真正存在的候选仍从同一 base 克隆并执行。

白话：输入是模型当前记忆和当前查询，输出是固定长度的真实候选/不可用槽位。例如连续合并后仅剩一对对象，就保留这一对，把缺失的第二对明确标出来，机器人仍能选 NOOP 或其他可用动作。它不等于添加一个空操作、隐藏 C11 样本、补充对象或读参考答案；当前只验证程序是否能完整运行，不能据此声称模型会恢复正确记忆。

默认 `generate_fixed_candidates` 和 `materialize_rollout_step` 均保留 `allow_unavailable=False`。新诊断入口只复用固定 16 组已保存的 train 审计，先核对 640 个普通参考步骤与 32 个恢复步骤，再运行全部 4480 次压力决策；逐步保存不可用原因及 C11 无目标暴露。未知异常仍失败，不丢弃分支或改变组集。该 gate 与旧严格 gate 分别记录，`formal_budget_authorized=false`；正式启用、覆盖与安全指标口径尚须登记和验证。


### 正式 self-rollout 的共享候选可用性（D-054，已采纳）

D-054 采用 `configs/m1_candidate_availability_policy.json` 作为独立评测策略，覆盖上一节“正式采用仍 planned”的状态。参考数据仍使用严格 v7/v9 生成来源，真实事务执行边界不变；固定 16 个网络输入位置允许部分位置为不可用记录。只有显式登记此策略的评测配置才能启用，旧登记和保存模型不能自动切换。实际候选按原共享生成、执行和去重流程处理，所有方法的选择 mask 相同。

新增逐步诊断位于 choice.candidate_availability，汇总在序列和 aggregate 的 candidate_availability 中，原主要指标不改。`unavailable_slot_count` 与 `executor_illegal_candidate_count` 分别表示没有事务和执行拒绝，避免把空槽算成执行器失败。`exact_reference_reachable` 只检查当前候选的语义 exact 可达性，排除不可用/静态拒绝/执行失败项；在动作选定和持久化之后才读取评测参考，不能反向提供在线选择信息。原 reference-index 选择诊断仍按原名记录，不能把它解释成任意错误历史下的真实恢复能力。

白话：输入是本步候选执行记录和独立评测参考，输出是哪里出了问题。例如程序仍能跑满 20 步，但第 15 步没有任何可选世界能把前面误合并的椅子分回来，就记录这一事实；它不等于单独归罪于生成器，也不代表成功恢复。C11 另报目标存在率与指定合法连带候选可用率，无目标时仍保留原时间步、组和全部主要指标分母；零 C11 分母用 null，不用零或一伪装成绩。诊断计算不纳入网络前向延迟定义，实际总耗时仍包含这部分审计。

train 复用必须经 `configs/m1_train_reuse_policy.json` 核对原验收指纹、全部 1002 个文件和已审查源码差异。参考生成默认严格路径及训练编码保持，旧 generation provenance 不改写，生成版本与评测版本分别记载。保存 16 组的行为一致性是支持证据，不能写成已完成全量重新生成对拍。正式 fixed probe、S5/S6 的后续组合登记必须绑定新策略，test 仍封存。


### 修正版固定 anchor 与组合登记的实现（D-051/D-054）

`run_m1_corrected_probe.py` 消费已验收的修正版 train，先核对固定 201 个 inner-dev 组的重建数组与 F 上限，再训练固定参数的 A/C/E 五 seed；模型落盘后从同一公共 causal evaluator 评测完整 20 步。固定运行条件是 CPU、一个 torch/BLAS 线程；审计重建最多四个独立进程，评测按 method/seed 顺序执行。学习目标、split、模型容量、gate 和效应门均沿用已登记规则。

`cpmt-m1-corrected-post-probe-registration-v1` 解决旧组合登记写死 1350 且仍连接旧数据的问题。输入是完整 train probe 的六格 paired SD、D-051 规则和数据/代码/策略来源，输出是新的封存登记。例如公式给出 1280 时仍取 1350，给出 1401 时向上取 1410；固定 exact 或其他必需终点不可用时没有登记，也不切到 graded。它不等于 test 解封、自动批准完整选参或宣布方法有效；后续消费入口必须显式校验这一新 schema 与来源，不能把它塞进旧 v6 校验器。完整矩阵先核对每个方法/seed/sibling，再按原组内均值和样本标准差计算，避免缺 seed 或重复行改变有效样本数。

固定 anchor 的拟合/inner-dev 差距只解释已固定模型的拟合情况，无参数选择作用；本阶段权重保存/加载集成 fixture 的模型未训练，不替代完整选参前已要求的真实短训、配对统计与正式报告导出小预演。运行结果仅记 EXECUTE，未完成的服务器验证不视为方法证据。


### 预算与重训共用的多进程路径（工程实现，GPU 验证 pending）

`m1_training_jobs.py` 将一条模型训练路径作为独立进程任务。输入是固定 train 数组、架构/seed/学习率/checkpoints 和必要的已完成 scorer，输出是逐 checkpoint 权重、概率、训练 trace、逐组指标及可核验完成记录。例如四个进程共享一张 GPU，各自训练不同 seed 的完整模型，而不是四个进程分担同一模型的更新。CPU 线程限制为每进程一条；调度线程只管理子进程，不共享模型或随机状态。

同一实现支持 budget 和 refit 两种人口划分：前者按原 hash 留出完整 train groups，后者使用全部输入 train。fit/inner-dev 采用相同的普通行 reference-ranking accuracy 定义，并另报逐组均值和差距；refit 不保留“独立 inner-dev”说法。此差距不改变参数选择规则，也不等于独立泛化成绩。正式 1000 组、全部原网格、C 顺序权重搜索以及 60 模型重训的登记消费已由 `m1_corrected_training_plan.py` 和 `run_m1_corrected_followon.py` 接线，服务器验证 pending。worker 只接受固定工程检查或经过 ready 回执、固定配方和来源校验的 train-only 任务；不能直接增加学习率、步数、seed 或读取 validation/test。

GPU 对拍固定使用原 train groups 0..9（原 hash 分为 9 fit/1 inner-dev）、两架构、seeds 7/19、scorer+A–E、lr=0.0006、steps 10/30、C weight=1。两种人口模式各跑单进程和四进程，核对精确 tensor 数值、教师/概率、checkpoint 分数与 trace；torch.save 容器字节不是比较对象，容差不在结果出现后放宽。例如调度次序不同但同 seed 的权重与预测一致才通过；任何差异保留诊断并暂停，而非修改样本或选择更好结果。它不验证学习收益、不完成原网格选参，也不证明 1000 组的四进程显存峰值已经满足。

检查期间不与当前 corrected probe 的 CPU 评测并行，以免将共享算力下的延迟误报为独占测量。小样本资源/速度报告只能描述已记录的运行条件；正式训练并发选择和完整规模资源检查仍按 D-051 与用户明确要求处理。所有来源、完成/失败日志和 exported report 保留，test 不访问，validation 不读取。

完整规模容量检查固定使用 1000 组 train、两架构各一条 scorer/A、seed 7、lr=0.0006、两步更新，四进程同时运行完整 refit 人口并记录采样资源和每进程分配峰值。输入仍是已验收数组，输出只用于决定四进程能否保持显存/内存余量。例如小样本对拍通过但完整数组放不进四份 worker 时，在正式网格前停止。它不重新选择超参，也不保证后续整个长任务不会发生资源故障；不得把两步分数写成方法成绩。

`m1_paired_evaluation.py` 是磁盘分片评测公共路径：输入保存权重及完整 paired group 文件路径，worker 自行读取两条轨迹，每条连续执行 20 步；输出逐组真实执行审计、逐例指标和按组号合并的结果。例如同一场景的两个 pivot sibling 始终在一个任务里，不将第 10 步后半段交给另一 worker。前向 p95 不从 worker 分位数拼接；关闭评测进程池后，读取实际在线输入作单进程前向重放，并核对选择不变。此计时只覆盖网络与概率计算，不是完整系统耗时，也不声称机器全局独占。

新增接口检查只使用并发对拍已经保存的两架构 A/C/E、seed 7、30-step refit 权重和原固定 inner-dev 组号最前四组；不为该检查额外训练。逐例完整记录要求不分片串行与四 worker 合并精确一致。正式统计公共函数另读取已有 probe 的 201 组、五 seed 结果，检查配对覆盖后复用原 10000 次 bootstrap、安全门及 Holm 计算；其 train-only 输出不参与选参、不判断 M1 方法成败。正式 S5/S6 的消费 reservation、数据入口及解封仍需独立冻结；公共数值函数已接入不等于这些正式运行已获放行。


### D-055 修正版 S5 确认的当前实现（服务器验证 pending）

机器计划为 [`m1_s5_confirmation_v7.json`](../../configs/m1_s5_confirmation_v7.json)，实施入口为 `ops/m1_corrected_confirmation.sh`。它消费 LOG-088 已验收的两臂预算和 60 模型 refit，固定 validation 4–203、两 sibling、20 步；数据、候选、能量、在线边界及统计公共算法逐文件保持 `4c89e59`，不使用旧 v6 S5 登记冒充新来源。原 S5 科学门和 S6 单独解封规则保持。

白话：新增数据写入与来源核验解决“模型存在，但下一阶段可能读错分片或权重”的问题；输入是固定分片编号、绑定 hash 和现成模型，输出是完整配对轨迹和原统计报告。例如两个 sibling 必须一起交给 CPU worker，前置配对检查和后续执行可反复读取同一绑定分片；不能把一次性迭代器耗尽后产生的空结果当作模型成绩。它不改感知表征、训练目标或评价口径。

前置固定 train 第 1 组的新写入必须与既有 probe 审计重编码 digest 一致；两架构 A/C/E、seed 7 的正式权重及两个 oracle 使用这一组检查新接线，共 320 次决策，不训练模型、不访问 validation/test。这是新增接口小预演，不是重复固定 probe 或证明所有未见分支可靠。通过后才生成固定 200 validation groups。生成健康门同时要求原各 family 覆盖和 teacher agreement，失败保留原组，不替换样本。

评测 50 个学生共 400000 次连续决策，另有两个共享 oracle 共 16000 次。四 worker 按 paired group 分片，模型间按固定顺序；每模型的单步 reference-history 错误分解与完整 self-rollout 同时报告。无竞争的阶段内串行重放报告每模型网络前向 p95：输入是已保存在线向量和静态 mask，输出是前向时间分布及选择一致性；例如其 p95=2 ms 只描述网络与概率计算，不包含候选执行和磁盘 I/O，也不保证服务器其他任务未争用 CPU。

生成前固定全局数据目录 reservation，首次模型读取 validation 前落下消费标记；同一绑定可核验复用成功产物，失败和 partial 不自动恢复。输出逐例指标与汇总须保留 candidate miss、teacher error 和 student/teacher disagreement 的区别，并注明 `validation_trial_consumed=true`、`model_selection_performed=false`、`formal_test_release=false`。最终 S5 报告不自动放行 test，统计不通过也应正常导出负结果；工程失败与科学不通过分别报告。

### S5 事后恢复分层（只读描述，不修改正式指标）

`ops/analyze_m1_s5_recovery.py` 解决把“出现错误”和“具有已登记恢复机会”使用同一分母的问题。输入是固定 SHA-256 的 S5 confirmation 全部逐序列指标；输出是每架构/方法、每 seed 和每 paired-group/seed 的计数、比例及负担分层。例如某序列首次全图出错后一直没恢复，会计入 `first_error_never_recovered`，但不会仅凭此认定修复候选缺失。它不重跑模型、executor 或 teacher，也不更改原统计和成败规则。

`bounded_pivot_wrong` 原样汇总 `designed_bounded_pivot_error`：在预设歧义步出错，且保存世界 hash 属于该 paired group 预先覆盖的另一个参考 pivot 世界。`bounded_revisit_triggered` 和 `bounded_recovered` 分别汇总该范围内的可见重访触发与重访后全图恢复；`bounded_not_recovered` 是范围内错误数减恢复数。输入是既有布尔字段，输出是已登记窄范围的条件恢复比例 `bounded_recovery_fraction`，零分母返回 null。例如只有位置选错且世界命中预先覆盖状态才进入该分母；同时遗留身份错误可能不在其中。它不等于所有位置错误、所有可修复错误或重新检查实际候选后的完整覆盖率；`pivot_wrong_outside_registered_scope` 也不表示没有修复候选。

`never_wrong`、`first_error_recovered`、`first_error_never_recovered` 将全部序列按首次全图错误后是否曾恢复划分；`ever_wrong` 是后两类之和，`first_error_recovered_within_3` 复用原三步窗口，`recovered_then_final_wrong` 单列恢复后终点再次出错，`first_step_wrong` 仅统计第一个决策后出错。输入是原首错、恢复时长及终点字段，输出是完整计数和首错步直方图（-1 表示无错）。例如第 3 步错、第 4 步修好、第 10 步再错至终点，属于曾恢复且终点再次出错；它不是始终未恢复，也不能证明所有中间局部事实都修好。

`burden_sum_by_sequence_stratum` 将每条完整序列的既有 open-fact burden 按上述互斥类别求和；`first_step_wrong_sequences` 是另列的交叉子集，不与前三类再次相加。输入是原全过程负担，输出是各类序列承载的负担总量；例如首步错误序列后来又错一次，这两次均进入该序列的总负担，它不等于首步错误本身的因果贡献。`mean_burden` 仍除以所有序列。分母包含同一 200 paired groups 的两 sibling 和五 seed，不冒称 2000 个独立场景；不对方法各自不同的错误子集作因果恢复率比较或新增显著性检验。全体错误后逐步候选覆盖和错误分支 teacher 排名需另读已保存逐步轨迹，本汇总不补推这些缺失字段。


### D-056：已有参数角色分离原型（独立开发；效果未验证）

本节只约束原型工程阶段，不修改上文已冻结的 S5 方法或替换其结论。用户在 LOG-097 后授权继续实现；正式方法有效性、开发训练预算和新确认数据仍为 planned。代码为 `src/cpmt/m1_role_encoding.py`，原 `online_feature_vector` 与所有旧入口默认行为保持；新适配器显式传递 `feature_encoder` 给训练数组构建和每步自身状态 rollout。原型训练/rollout 适配器只接受非空 train audits，配置必须 `formal_run=false`、`test_access=false`；不加载旧权重冒充新编码模型。

白话：参数角色分离解决“参数混在一起后，网络不知道哪个 ID 是关系源、哪个是目的地”的表示问题。输入是原来已有的候选操作参数及 node/edge/place 三条 query，输出是在原 33 维候选块后追加的角色匹配信息。例如把 ADD_EDGE 中对象 source 和地点 target 分开编码；它不新增视觉信息、不读取参考索引或未来，也不等于已经证明这类信息丢失造成了 LOG-095 的 69 次错误。

固定角色来自结构化参数字段，不解析 ID 中的 family、物体名字或事件编号：

| 英文角色 | 中文含义与取值规则 |
|---|---|
| `edge_argument` | 顶层 edge_id 指向的边；沿用旧规则去掉 @ 版本后缀 |
| `node_argument` | 顶层 node_id / node_version_id 指向的节点；沿用旧版本后缀归一化 |
| `edge_source` | 嵌套 edge.source，例如位置边中的物体 |
| `edge_target` | 嵌套 edge.target，例如位置边中的地点 |
| `node_record` | 嵌套 node.node_id，例如待建立或打开新版本的节点 |

各角色内部去重排序，对三条原 query 分别保留 max/mean，再加参数数目除以 6，合计每角色 7 维、追加 35 维；空角色全零。所有角色 ID 的并集必须严格等于旧 `candidate_argument_ids` 集合。不同角色可出现同一个 ID，角色计数不是全局不重复计数。原世界上下文和原候选 33 维逐位保留，事务日志计数、closed edges、生命周期不改，`merge_queries` 不进入新特征。

| 编码 ID | 每候选宽度 | 职责 |
|---|---:|---|
| `pooled_v1` | 33 | 原编码兼容锚点 |
| `pooled_padded_v1` | 68 | 原编码追加 35 个零，作为同宽度对照 |
| `argument_roles_v1` | 68 | 原编码追加 35 个角色特征 |

白话：同宽度对照解决“收益是否仅来自输入维度和模型参数量增加”的一部分混淆。输入为同一原候选描述，输出为补零的 68 维描述；例如两个 68 维模型可以使用完全相同的随机初始化和总参数量。它不保证两者的有效容量、梯度或训练难度相同，因为补零列没有输入信号；不将参数数目相同夸大为排除了所有容量影响。

若把原输入记为 X、追加角色特征记为 Z，在允许忽略 Z 的理想预测器集合中，最优风险满足 `R*(X,Z) <= R*(X)`。白话：新增特征保留了“仍按原输入作答”的可能性，不能据此保证固定网络、有限数据或梯度训练一定改善。测试以把追加输入列的权重置零验证模型能忽略角色特征，但不训练或选择这种权重。

历史 ROLE-P1/P2 入口 `python ops/m1_role_encoding_preflight.py [--verify]` 保留，用于复核本机九项专项检查记录 `results/m1_d056_role_encoding_preflight.json`。用户在 2026-09-11 明确本机 CPU 有问题后，该成功记录不再认证本原型，Windows/WSL 都不继续重试；必须执行以下独立服务器验收。

当前机械顺序：ROLE-S1 执行 `python ops/m1_role_encoding_server_check.py run`，ROLE-S2 执行同一入口的 `verify`。run 仅允许独立 Linux 服务器，拒绝本机 Windows/WSL；实际项目根由 `git rev-parse --show-toplevel` 确认，输入源码须已经提交且无未提交改动。先运行 9 项角色专项，再运行 30 项既有 A–F 回归，前项 exit=0 且成功测试数匹配才进入后项。专项输入是一组 train 夹具；旧回归自行生成少量 train/validation 单元夹具，不读取原 S5 或封存 test。40 步固定分数模型只检验动态接线，不输出角色方法成绩；既有单元测试中的小训练调用也不属于正式模型训练或 checkpoint 选择。

输出为独立的 `results/m1_d056_role_encoding_server_check.json`，成功标志为 `ROLE_SERVER_CHECK_OK tests=39 exit=0`，后续 verify 成功为 `ROLE_SERVER_CHECK_VERIFIED tests=39 exit=0`。报告包含全部相关源码/测试和两份配置的 hash、实际服务器根路径、Git 提交、Python/NumPy/Torch、系统/hostname、两组完整 unittest 回执与退出状态。verify 可在本地只读核验服务器报告，不执行测试。它不复用本机九项成功记录。运行前写 attempt，每组计算结束后先写日志和 exit 回执，再启动下一组；现场在 `outputs/m1-role-encoding-server-check/<binding>/`。成功报告同绑定直接复用，失败或不完整尝试保留并拒绝自动重开；不删除本机或服务器失败证据。

全部 39 项通过后自动写报告，后续只需 verify 和精确提交这一个服务器产物，不为步骤切换更新版本。服务器实际通过之前，当前状态仍是原型实现完成、验收待完成；通过也不等于角色编码有效或允许直接启动未冻结的新训练协议。

下一科学阶段仍须先冻结：复用哪些合格 train 产物、拟合与 inner-dev paired-group 划分、A–E 及强制主对照的预算、同 seed/初始化与停止步数、query 依赖诊断和未参与本轮分析的新确认来源。本阶段不现场指定胜出方向或新科学效应阈值；C10 证据支持、全体错误负担及候选可达性仍要分别观察，不能只报 C06/C08。新增角色可能强化既有 query 捷径、过拟合角色稀疏性或增加优化难度；原候选生成器本身的 query 依赖没有被消除。merge_queries 配对分、历史计数删除、自身状态重采样和风险损失均不并入本原型。

### S5 全体逐步候选可达性导出（只读诊断，服务器全量待执行）

入口为 `ops/export_m1_s5_availability.py export|verify`，只使用 Python 标准库。`export` 先执行本入口的轻量前置测试，再读取固定 SHA-256 的 S5 confirmation，从报告原样取得全部 50 模型、10000 个 paired-group 分片路径；逐一核验 complete.json 的原始字节哈希、result.json 的登记哈希、科学登记/来源绑定、模型与组号绑定、两 sibling 的原逐例指标、20 步时间轴和持久状态链。输入是已完成评测的保存结果，输出是 results/m1_v7_d055_s5_availability.json。例如第 5 步保存的合法可选候选没有完整正确世界，则直接保留该判断；它不是重新生成候选、执行模型或重算图相等性。原 audit 与 execution 文件的来源由已核验绑定引用，本入口不重新读取其字节，不冒称全量原始候选世界已经再次审计。

导出保留全部逐步 choice 的步骤、当前 family/歧义类型、选中模板和索引、原参考索引及其匹配标志、实际提交/合法性/静态预检/隔离、重访、active_correct_after 与完整 candidate_availability。每模型的 400 条序列以 gzip+base64 JSON 无损封装这些保留字段，记录解压字节数和 SHA-256；每单位另保存原路径、marker/result 哈希及参考 audit 来源，每序列保存经核验的状态链摘要。输入是原保存字段，输出可在本地重新拆分和统计的数据，例如保留所有成功步与失败步而非只导出挑中的错误。它不是完整原 result 的字节备份：概率向量和逐步图哈希不复制进本报告，原文件保持在服务器。code_binding 只对导出器及测试代码统一 LF 行尾后求哈希以兼容 Windows/Linux；数据和报告仍按原始字节校验。

`decision_cells` 是八格计数：`prior_correct/prior_wrong` 表示上一决策后的世界相对上一时刻参考是否正确，首步按登记的正确初始世界处理；`reachable/unreachable` 表示本步保存的可选合法候选中是否有完整正确世界；`correct/wrong` 是本步实际持久世界相对本步参考的正确性。它解决把“上一步就有错误”“本步无完整选项”“本步有选项却选错”混为一谈的问题。输入为相邻步正确性和本步保存的可达性，输出为互斥且覆盖所有步骤的格子；例如 `prior_wrong_unreachable_wrong` 是上一步已错、本步无完整正确候选、执行后仍错，不能归成模型面对完整修复选项却失败。参考目标可能随时间变化，`prior_wrong_reachable_correct` 只表示有候选时观察到全图恢复，不证明该操作主动修复了所有原错误。没有完整正确候选也不排除局部修改、分步修复或其他未走过的路径。

`post_error_complete_option_fraction` 用上一刻已错的全部决策作分母，统计本步存在完整正确候选的比例；`observed_recovery_given_complete_option_fraction` 只在上一刻已错且本步存在完整候选的决策中统计恢复比例；零分母均为 null。例如三个错误后决策中两个有完整候选、其中一个恢复，两项分别为 2/3 和 1/2；它们不等于全体步骤的 candidate coverage 或 CTL 的因果纠错优势。各方法进入错误分支和修复机会的分母不同，仅描述原轨迹，不做新的成败检验，不改正式分母，也不把 sibling/seed 当成独立场景。

`by_current_family` 和 `by_selected_template` 将八格按本步场景类型、实际选中事务分层；输入是当前步标签，输出是全部类别的计数，例如在 BIRTH 步发现以前身份错误仍无完整候选，会按当前 BIRTH 步记录，而不是把原错误原因归成 BIRTH。`sequence_counts` 记录至少一次出现对应现象的序列数量：with_prior_error_and_no_complete_option、with_prior_error_and_complete_option、with_reachable_selection_error；这些“曾出现”类别可以重叠，不能相加充当总序列数。模型、seed、配对组和 sibling 均保留，不按事后效果筛选。teacher_error_assessed=false：可达却选错能确认在线选择错误，但仅凭这些字段不能进一步区分 teacher error 与 amortization error，不能用参考轨迹教师正确率补推错误分支。

`verify` 在不访问服务器原目录的条件下，校验同一 confirmation、代码绑定、全部 payload 哈希和序列矩阵，从逐步字段复算时间轴指标、每模型及每架构/方法八格计数和比例。它解决导出损坏、漏组或汇总不一致的问题；输入是封装报告与原 confirmation，输出是 AVAILABILITY_VERIFY_OK。例如少一条 sibling 或有人只改汇总分子，都不能通过。它不等于再次执行或验证候选图，原始字段的真实性依赖 export 时核验的 marker/result 来源。

写入采用独占 partial 文件，完成检查后以不覆盖已有目标的方式安装。导出运行证据在 outputs/m1-s5-availability-export/<code-binding-prefix>/：attempt.json、progress.jsonl、complete.json 或 failure.json；这些不进 Git。每 100 个分片显示进度，完整导出内部复核成功后才写报告及 exit_code=0 完成证据。已存在且通过 verify 的导出直接复用，不重新扫描原分片；不完整尝试或 partial 保留并拒绝自动重开，先检查失败原因，不删除或替换原评测产物。本入口未实现任意多步反事实搜索，也不放行 S6/test。
