# 01 CPMT 研究合同

定位：已确认的研究问题与拟验证假设，不维护实现进度；当前实现、实验结果与未完成项统一见 [实验记录](../EXECUTE.md)。

## 研究问题

在部分可观测、视角持续改变且世界可能真实变化的环境中，机器人如何从序列本身学习：当前结构证据应当绑定已有节点、扩张世界，还是修订既有事实，同时避免视角、遮挡和位姿误差污染长期记忆？

## 唯一主假设

与直接预测 transaction label 或增加 future auxiliary loss 相比，先在同一旧图的版本副本上执行竞争性 transaction programs，再以执行后世界对当前证据及随后实际观测的投影不一致为主要依据，并仅以 edit/growth 等最小改动代价作为预登记正则，能够产生更可靠的 hindsight supervision；由此蒸馏的 online updater 能减少长期 persistent-world error burden。这里要检验的是“真实展开候选世界后形成的监督是否更可靠”，不是把 current、future 与 minimal-world-change 三项并列宣称为已经验证的创新机制。

## 方法角色

范围修复后的重建受 D-051 和 [`m1_scope_rebuild_plan.json`](../configs/m1_scope_rebuild_plan.json) 约束：current evidence scope 由原当前查询的固定检索集合做一次 open-edge 扩展，对边记录排列不变，不递归使用扩展结果。生产函数与版本边界已实现，服务器完整验证 pending。它同时用于 C11 候选、collateral 教师能量和安全指标；修正数据的生成合同为 [`m1_hard_condition_v7.json`](../configs/m1_hard_condition_v7.json)，dataset=v9。旧 `m1_hard_condition.json`、probe overlay、post-probe registration 和模型方案仅保留其历史绑定，不能授权修正版本的正式确认。

白话：这条约束明确“当前观测涉及哪些已有记忆”。输入是当前图与检索到的节点/边，输出是一跳涉及的标识集合；例如检索到 A、存在 A–B 和 B–C 时，可以纳入 B，但不能仅因 B 刚被纳入又把 C 加进来。它不改变候选预算、学习目标权重或安全门，不是主动获取新观测；修复正确性不等于 CTL 方法有效。

新连续序列审计的 `source_binding` 保存 protocol、protocol_sha256、dataset_version 和 scope_schema；数组编码、horizon 对照与连续执行在使用前检查绑定。白话：版本绑定解决“旧候选和新规则不知不觉混用”的问题；输入是审计的来源标记和所用合同，输出是允许读取或明确拒绝。例如旧 v8 审计没有新一跳定义标记，就不能由新编码器重新标成 v9；历史报告仍可独立读取。它不是重新跑实验的成功证据，也不是修改旧数据的许可。

修正后的 fixed train probe 保留 exact、support、AUC 与原安全门，F 或非退化检查失败时停止，不重选 endpoint。test 组数仅在进入 confirmation 前按原六格 SD 公式重估一次并取至少 1350；不按观测效应或 validation/test 结果调整。预算重跑保持原网格和完整 paired-group 隔离，inner-dev 最优值不作无偏泛化成绩；只有完整独立确认与 test 才能支持对应范围内的最终性能结论。执行顺序、阶段证据与具体限制分别见唯一流程、EXECUTE 和 D-051。

- CPMT：完整具身空间记忆系统；
- CTL：从 future-conditioned transaction posterior 蒸馏 online transaction policy 的核心学习机制；
- Projective Node Orbit：使同一世界节点解释多视角 observation latents 的表征基础；
- Versioned Deterministic Executor：使候选解释成为真实 graph interventions 的执行基础。

主创新只归于 CTL 的 executable counterfactual supervision。表征与 executor 是否构成额外贡献，必须由独立消融决定，不能预先宣称。

M1 的 online 网络只读取截至当前的世界、观测和候选程序并输出候选分数，不读取 future 或候选 `post_graph`。当前 M1 是审计型评测 runner：固定候选生成器先执行全部候选，以规范化执行后状态检查重复；原始集合固定 16 个，去重后不足 16 个就报错，成功返回时没有删减候选。评测器随后展开全部候选，网络以共享静态预检 mask 选择，只有选中的合法结果进入持续记忆。因此当前实现不能声称“整个在线系统只执行一次”，也不能把 `p95_forward_latency_ms` 当系统总延迟。该计时仅覆盖网络前向及相关张量/概率处理，不含候选生成、分支审计或完整提交成本。

白话：审计型评测解决“选完以后世界怎样变化、其他候选是否可执行”的核查问题；输入是当前记忆、候选与当步证据，输出是各分支记录和一个进入下一步的选中世界。例如网络选择 BIND 时，其他 15 个分支仍留下审计记录，却不写进持久记忆。它不等于未来泄漏，也不等于已实现的单次执行部署路径。M2 的独立部署路径仍为 planned：固定候选生成、静态预检、网络选择、仅执行选中事务；必须先明确无执行生成器的重复处理/失败语义并验证候选、mask 与选中结果等价，不直接删掉 M1 检查。

M1 的 world events、观测顺序、pose buckets 与 controlled-revisit action history 都是由固定 seed 预生成的外生输入，不由模型根据当前记忆状态选择。例如某一步换到哪个 pose 在该方法开始决策前已经确定；模型只能决定如何修订记忆，不能决定去哪里看。该设置检验外生观测流下的 online memory revision，不等于 active navigation、主动消歧或 action-policy learning。

### 教师可以不同意参考标签

白话：教师不是答案本身，是一个**打分器**。它把每个候选真的执行一遍，再看"执行完的世界，和后来实际观测到的世界像不像"，同时对"改动越大越不划算"扣分。所以当两个候选对未来预测得**几乎一样好**时，便宜的那个会赢——哪怕它不是我们标注的参考答案。

这是设计意图，不是缺陷。能量函数写的就是"未来一致性 + 最小改动代价"，把后半句去掉才是错的。

paired sibling 的反事实 rollout 必须沿该 sibling 实际登记的 primary/contrast policy 前进。hindsight 的视野跨过 ambiguity pivot 时，参考候选继续执行该分支的真实后续事务，故其 `future_raw` 必须为 0；若代码把 contrast sibling 偷换回 primary policy，产生的非零误差是分支实现错误，不是合理的 teacher disagreement。即使参考轨迹正确，其他候选仍可能在有限观察下得到相同 future 分数，此时 edit/growth 等最小改动先验可以让教师与事务标签不同意。

因此：

- 教师与参考标签的一致率**记录为 `teacher_reference_agreement`**，不作为断言拦截；生成器不会因为教师不同意而失败。
- 该比率若显著下降，属于需要解释的实验事实（可能是候选等效、能量权重或数据问题）；但必须先验证参考候选的分支 trace 为零误差，不能把 policy 错配包装成教师性质。
- 报告 A 的表现时必须一并报告该比率、reference future error 与 disagreement 分解，不能只报学生准确率。

## 拟议 claim

> CPMT learns online persistent-memory revision by distilling a hindsight posterior built from genuinely executed candidate world transactions. In M1, execution-conditioned current evidence and subsequently observed future evidence provide the principal scoring signal, while minimal-world-change costs remain registered regularizers rather than a separately validated mechanism.

这里的 counterfactual 是对内部 memory state 的干预，不是物理世界因果效应。

## 事务范围

主要意图：

- PRESERVE：NOOP；
- ASSOCIATE：BIND / REACTIVATE；
- EXPAND：BIRTH；
- REVISE：RELINK / RETRACT / SPLIT / MERGE。

REPLACE 是 RETRACT+BIRTH 的复合程序。QUARANTINE 是低置信度 wrapper，不属于 world mutation。

## 首篇边界

固定 DINO-family backbone、depth、pose、region proposals 和 deterministic candidate generator。禁止把 active disambiguation、第二任务领域、learned proposer、端到端视觉训练或导航同时并入。

## 成功条件

1. M1 的 CPMT-CTL Core 在预注册 paired cases 上优于 direct+future-loss 与 no-execution future scorer；
2. 改善落在 post-execution graph correctness 和 long-horizon contamination；
3. growth、collateral edit、protected violation 和 illegal program 不恶化；
4. candidate miss、hindsight teacher error、online amortization error 分开报告；
5. SPLIT/MERGE/RETRACT 有正例并由同一 executor 处理；
6. teacher 优势能部分保留到 online self-rollout。

## 失败解释

- Full≈direct+future：核心机制失败，不能称 CPMT 学习贡献；
- Full≈no-execution：真实执行候选不是必要条件；
- 只有 Node Orbit 有效：降级为 representation work；
- 只有 oracle/executor 有效：降级为 deterministic memory system；
- candidate coverage 低：先修候选，不评价 scorer；
- 只有单步准确率改善：不能声称 persistent memory 改善。

## 证据顺序

M0 executor fixtures → M1 hard-condition → M2 embodied visual self-rollout → M3 one external/real validation。

任何阶段均区分 planned、implemented、validated、failed。数值 gate 在正式 test 前冻结。

## M1 合成证据与 M2 传感器证据的边界

M1 的 A 教师通过登记的后续 primary/contrast 参考事务推进每个候选分支，并与参考图构造的结构观测比较；C/E 的当前关系目标来自候选声明和当前观测，future 关系目标来自同一参考后续轨迹，目标构造不执行候选 post-world。共同的合成参考信息来源应披露；候选分支执行及监督构造方式正是被比较的区别。参考身份、完整参考图及正确后续事务属于合成器特权信息，不是原始传感器读数。

白话：这条边界解决“实验有标准答案，真实视频却没有答案接口”的迁移问题；输入是当前合成器向各方法提供的信息清单，输出是 M2 必须替换的教师证据接口。例如后来从另一侧看到椅子，M2 应凭区域、深度、位姿及可见性验证身份假设，不能从正确 BIND 标签读出答案。它不等于已发现 A 独占未来数据，也不证明现有教师能直接用于无标注视觉训练。M2 必须分别登记传感器证据、训练特权信息和仅评测真值；任何在线选择使用 future、reference index 或候选执行后正确性时，都必须修复并重新验证受影响实验。
