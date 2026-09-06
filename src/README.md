# CPMT Source Layout

定位：代码模块与实现接口说明；最近运行结果和下一步只记录在 [EXECUTE.md](../EXECUTE.md)，不在此复制实验进度。

## 单房间视觉接口审计

`cpmt/visual_pilot.py` 实现固定几何投影、深度反投影、同源候选执行、六项能量记录和 online 边界检查。白话说，固定几何投影解决“改完记忆后，从某个相机位置应该在哪里看见物体”的问题：输入是执行后的世界图、位置坐标、相机位姿和视场角，输出是归一化图像坐标与深度；例如 `RELINK` 把杯子从旧台面连到新台面后，投影点应跟新台面观测对齐。它不是 Projective Node Orbit（PNO），不生成 RGB，也不学习深度、位姿或遮挡。

同源候选执行审计解决“教师到底在比较事务名称，还是比较事务真的造成的世界”的问题：输入是同一个不可变 base、`NOOP/BIND/BIRTH/RELINK` 程序、当前观测和离线后续观测，输出是每个真实执行分支以及 `now/future/edit/growth/collateral/illegal` 六项能量和教师概率；例如物体移动后，旧地点重访为空且新地点重访可见时，正确的 `RELINK` 应优于留下旧位置的 `BIND`。它不是正式 M1 结果，也不等于 CTL 已学会选择这些事务。

online 边界检查解决“在线学生是否偷看未来或模拟器对象编号”的问题：输入是准备交给在线侧的嵌套 JSON，输出是通过或显式拒绝；例如出现 `future_views`、`teacher_score` 或 `target_object_id` 会失败。它不证明所有可能的信息侧信道都已消除，正式 run 仍需冻结字段 allowlist 并做独立泄漏审计。

~~~text
src/
  cpmt/
    errors.py        显式合同与拒绝类型
    equivalence.py   身份对应与保守 canonical memory-state equality
    hashing.py       canonical graph hash
    executor.py      immutable clone、primitive、invariant、atomic reject
    maintenance.py   非学习型 confirmed→dormant 版本维护
    pending.py       QUARANTINE gate、弱证据暂存、归档/检索/消费
    dev_data.py      合成配对场景、真实候选执行、解析投影和 hindsight 教师
    dev_learning.py  无未来在线编码器与置换等变候选打分头、未来辅助头、无执行结果评分器及训练/评估
    m1_protocol.py   正式 M1 pre-test 配置完整性、泄漏边界与 A–F 语义校验
    m1_data.py       C00–C11 train/validation 配对生成、候选执行与 online/audit 隔离
    m1_rollout.py    程序化空间图、连续 20-decision 执行与预测状态回放
    m1_af_rollout.py A–F 共用在线特征、训练适配与 causal self-rollout 评估
    m1_af_method.py A–F 单方法训练、评估与结果打包
    m1_trainability.py 全标签容量、数据/步数阶梯与三段误差诊断
    m1_metrics.py    分项图错误、真实顺序 rollout 接口与 paired bootstrap
~~~

`m1_protocol.py` 解决“正式评测前是否把关键条件填完整且没有悄悄改弱”的问题：输入是 `configs/m1_hard_condition.json`，输出是通过或明确拒绝；例如打开 `test_access`、删掉 E、把 future 改为计划动作或把 bootstrap 拆散 paired group 都会失败。它不是实验 runner，不生成 test，也不能证明门槛合理或方法有效。

`m1_data.py` 解决“十二类事务场景能否被一致地变成成组、可重放的数据接口”的问题：输入是冻结配置和 C00–C11 human-draft 语义 fixture，输出是重新命名的 prior world、同源候选、真实执行分支、匿名 current cues，以及物理分离的 online/audit records。例如 C07 的一对 sibling 共用旧图和候选，一边由可靠 visible-empty 支持 RETRACT，另一边由遮挡条件支持 NOOP。它目前只改变 ID、asset signature、history cue、pose 和 visibility，world topology 仍停留在 fixture archetype，因此是 generator interface validation，不是正式多样化数据或 test ground truth。

其中的 fixed structural projector 解决“教师不要直接拿 candidate graph 对答案图”的问题：输入是执行后的 graph、future pose bucket 和 visibility mask，输出是固定哈希投影形成的结构 observation；reference world 只负责生成未来 observation，其他候选经同一投影后计算误差。例如 RELINK 和 BIRTH 留下的节点/边不同，会在未来结构 observation 上产生差异。它不是 PNO、RGB 特征或 learned dynamics，也不证明这种玩具表征足以支持 Full CPMT。

`m1_rollout.py` 解决“20 个独立 case 不能冒充在线记忆连续运行”以及“候选不能由 reference 标签或参数临时拼出来”的问题：输入是当前 versioned world、当前证据、固定种子、train/validation split 和不含身份字符串的匿名 16 维 observation query，输出是 20-decision 世界链，以及每步固定 16 个、真实执行、canonical state 去重后的事务候选；paired mode 还在每组放入一个“当前完全相同、合法 reference 不同”的 ambiguity pivot。完整隐藏事务只存在 audit-only `reference_spec`，候选生成器用匿名 query 在当前 world 检索 node/edge/place，再按固定槽位枚举 NOOP/BIND/BIRTH/REACTIVATE/RELINK/RETRACT/SPLIT/MERGE 与复合 REPLACE；删除 `reference_spec` 不改变候选。它不读取 future、不使用 learned proposer，也不是 Projective Node Orbit（PNO）或正式规模数据。在线观测由执行中的世界生成：每个节点有固定外观描述符，观测是该描述符加噪声，并附带 `visibility`/`pose_valid`/`depth_valid`/`reliability` 与七项记忆比对量；正确模板因此可由证据推出，而不再由 `scenario_family` 标签直接给出——该标签已移出 online、只留 audit。歧义点改用遮挡实现，因为遮挡不是“事实为假”的证据，两个 sibling 的 online 输入天然逐字节相同。当前外观与检索特征仍是受控、非学习的 SHA-256 固定向量，仅用于验证接口，不能冒充真实视觉 proposal 或正式独立 coverage；`evidence_novel` 由生成器随传感器报告声明，尚未由每节点视角覆盖算出。

`m1_af_rollout.py` 解决“六种方法不能只在单步数组上比较，必须用各自改出来的长期记忆继续”的问题：输入是 paired rollout 的 online records、仅训练期可见的 hindsight targets 和 A–F smoke 配置，输出是 A–E 同结构学生、E 的额外 outcome scorer、单步 teacher-forced 指标以及 20-step causal graph 指标。例如某学生第 6 步选择错误事务后，第 7 步 online feature 和 K=16 候选由它自己的错误图重新生成，而不是使用保存的 reference base。在线向量分成世界上下文与每候选描述块，候选块含模板/意图/代价/操作计数与候选参数对 proposal query 的对齐度，因此同模板的多个候选不再编码成同一串数字。它不把 future 喂给 `forward`，不等于固定的 Projective Node Orbit（PNO）表征，也不是五 seeds、bootstrap 的正式 gate；数值只记录在 `EXECUTE.md`，不能冒充正式 gate。

`m1_af_method.py` 解决“一个 A–F 方法的原生进程异常不能丢掉其余已完成方法，也不能把半成品混进比较”的问题：输入是同一 train/validation arrays、同一 seed、paired-group 数与更新步数，以及一个固定方法 ID；输出是该方法的一份完整 teacher-forced、causal rollout、误差分解和参数量结果。比如 A 已结束而 C 在 causal replay 中退出时，恢复流程只会重跑 C，A 的 `complete.json` 仍可复用。它不是把 A–F 拆开调参，不是从多个成功 attempt 中挑最好的一次，也不是新的学习方法；所有方法仍使用同一冻结点，只有完成的六项才能聚合。

`m1_trainability.py` 解决“低准确率到底是网络根本学不会，还是数据/训练不足”的问题：输入是 paired arrays、全标签容量设置或不同 paired-group/更新步数组合，输出是可观测准确率上限、按 family 的 candidate coverage、teacher error、student-to-teacher amortization error 和 causal graph 指标。例如 exact ambiguous pair 的两个样本 online vector 相同而答案相反，所以确定性学生的总体上限是 97.5%、歧义点上限是 50%。K=16 的非正式开发阶梯已经重跑，结果只在 `EXECUTE.md`；旧 candidate=3 数值仍不得和它混报。它不是调正式 test、不是修改冻结 gate，也不把容量通过写成 CTL 已胜出。

性能说明：`hashing.clone_json` 按精确类型分派而非 isinstance 链，`executor.validate_graph` 以一次索引取代按 id 重复扫描的 O(n²) 检查，`m1_data._state_tokens` 对未变化的 node/edge 视图缓存其规范序列化。三者都保持输出逐字节不变（已用 paired rollout 的 SHA-256 对照验证），合计约 1.27× 加速；生成阶段的并行见 `scripts/generate_m1_parallel.py`。

能量与目标表征说明：协议声明六个能量项，当前 `now` 仍弱，`collateral` 又因 protected 检查与 illegal mask 高度冗余；生成 summary 会在 `energy_term_variation` 如实报告每项的非零比例与不同取值数，不能把六个字段写成六个都有效的信号。M1-v2 的 C/E 不再以 `hashed_tokens` 或 `world_latent` 回归作为主要未来目标，而是预测候选所声明的具体未来关系；旧向量仍留作兼容审计和表征对照，不参与结构化 E 的候选评分。

`m1_metrics.py` 解决“当前世界是否正确、证据档案是否一致和历史是否无错不能混成一个 accuracy”的问题：输入是预测/参考/base graphs 或真实连续状态序列，输出分别包含 active semantic correctness、open-memory support correctness、history exactness、contamination、missing fact、false birth、collateral、recovery 及保持 paired group 的 bootstrap CI。例如错误 RELINK 的旧边版本被关闭、正确位置重新打开后，active 可恢复为 1，但 history 仍为 0，且原错误步不会被回填。它不物理删除 provenance，也不把后来修正说成当时已正确；rollout 接口仍要求恰好 20 个有序状态。

`m1_af_rollout.py` 的候选作用域未来关系目标解决“E 只在正确候选上训练，却要给全部 16 个候选排序”的问题：输入是截至当前的 online 特征、每个候选程序声明的操作和实际后来到达的 reference future，输出是每个候选在三个未来时刻上的关系真假标签与 mask。例如 RELINK 候选提出“杯子位于水槽”，目标只查询真实未来是否存在该关系，不执行这个候选。它不是 post-world embedding、不是 transaction label，也不允许借用 executor 给出的 illegal/collateral；E 最终选中的单个事务仍须交给共享 executor 执行。

同模块的有界恢复与 observable-information oracle 解决“错误是否有在线改正机会，以及可观察信息下最多能做到多少”的问题：输入是 exact ambiguity 后真正到达的一次相关可见证据和原固定 K=16 proposer，输出是补偿候选、active/history 分离结果与恢复耗时；例如遮挡时选错位置，下一步看清后以新 RELINK 关闭错边并打开正确边。oracle 在不可辨 sibling 上强制做同一个确定性选择，不能靠两次独立猜测抬高上限。它不是可部署模型、不是提前读取未来，也不是 Khronos 式全图异步 reconciliation。

当前 executor 实现 C00–C11 所需的 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE 和 COMPOSITE:REPLACE。pending manager 实现 D-023 的低置信度 gate、低权重证据、有效观察机会、可检索归档、重新激活与带 provenance 的消费。它仍是确定性支持机制，不是 CTL 模型。

事实级 RETRACT 需要两条满足 D-022 的可靠空观测；REPLACE 必须按 RETRACT→BIRTH→ADD_EDGE 执行并保留旧对象身份。节点级 RETRACT 尚未实现，会被显式拒绝。

开发模块白话：dev_data 把“旧物体还在、出现新物体、原物体移动”变成竞争世界并评分；dev_learning 用这些结果教小网络，只用已经获得的信息做决定。旧开发 harness 与新的 paired causal smoke 都已接 A–F，其中 D 删除 future 教师项，F 是候选预算内 oracle；这些开发结果只记录在 [EXECUTE.md](../EXECUTE.md)，不等于正式 M1 比较。输入输出、损失、局限详见 [开发合同](../experiments/counterfactual_transaction_learning/DEVELOPMENT.md)。解析三位置投影不是 PNO；三个候选的 smoke 不是完整 CPMT。executor 仍无梯度且不依赖 learned scorer。
