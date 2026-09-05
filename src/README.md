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
    dev_learning.py  无未来在线 MLP、未来辅助头、无执行结果评分器及训练/评估
    m1_protocol.py   正式 M1 pre-test 配置完整性、泄漏边界与 A–F 语义校验
    m1_data.py       C00–C11 train/validation 配对生成、候选执行与 online/audit 隔离
    m1_rollout.py    程序化空间图、连续 20-decision 执行与预测状态回放
    m1_af_rollout.py A–F 共用在线特征、训练适配与 causal self-rollout 评估
    m1_trainability.py 全标签容量、数据/步数阶梯与三段误差诊断
    m1_metrics.py    分项图错误、真实顺序 rollout 接口与 paired bootstrap
~~~

`m1_protocol.py` 解决“正式评测前是否把关键条件填完整且没有悄悄改弱”的问题：输入是 `configs/m1_hard_condition.json`，输出是通过或明确拒绝；例如打开 `test_access`、删掉 E、把 future 改为计划动作或把 bootstrap 拆散 paired group 都会失败。它不是实验 runner，不生成 test，也不能证明门槛合理或方法有效。

`m1_data.py` 解决“十二类事务场景能否被一致地变成成组、可重放的数据接口”的问题：输入是冻结配置和 C00–C11 human-draft 语义 fixture，输出是重新命名的 prior world、同源候选、真实执行分支、匿名 current cues，以及物理分离的 online/audit records。例如 C07 的一对 sibling 共用旧图和候选，一边由可靠 visible-empty 支持 RETRACT，另一边由遮挡条件支持 NOOP。它目前只改变 ID、asset signature、history cue、pose 和 visibility，world topology 仍停留在 fixture archetype，因此是 generator interface validation，不是正式多样化数据或 test ground truth。

其中的 fixed structural projector 解决“教师不要直接拿 candidate graph 对答案图”的问题：输入是执行后的 graph、future pose bucket 和 visibility mask，输出是固定哈希投影形成的结构 observation；reference world 只负责生成未来 observation，其他候选经同一投影后计算误差。例如 RELINK 和 BIRTH 留下的节点/边不同，会在未来结构 observation 上产生差异。它不是 PNO、RGB 特征或 learned dynamics，也不证明这种玩具表征足以支持 Full CPMT。

`m1_rollout.py` 解决“20 个独立 case 不能冒充在线记忆连续运行”的问题：输入是冻结配置、train/validation split 和 sequence/group 数，输出是带不同 place/surface/object 数、空间关系与随机事件顺序的 20-decision 世界链、逐步同源候选、执行后图和分离的 online/audit records；paired mode 还在每组放入一个“当前完全相同、合法 reference 不同”的 ambiguity pivot。例如第 4 步错误选择 NOOP 而漏掉一次 RELINK 后，第 5 步候选会从这个错误后的预测图重新生成，错误位置事实可一直留到第 20 步并被 contamination 指标捕获。它不是把保存好的 reference base 强行喂回模型，也不是 Projective Node Orbit（PNO）、视觉轨迹或正式 K=16 数据；当前状态明确为 paired rollout interface validation。

`m1_af_rollout.py` 解决“六种方法不能只在单步数组上比较，必须用各自改出来的长期记忆继续”的问题：输入是 paired rollout 的 online records、仅训练期可见的 hindsight targets 和 A–F smoke 配置，输出是 A–E 同结构学生、E 的额外 outcome scorer、单步 teacher-forced 指标以及 20-step causal graph 指标。例如某学生第 6 步选择错误事务后，第 7 步 online feature 和候选由它自己的错误图重新生成，而不是使用保存的 reference base。它不把 future 喂给 `forward`，不等于固定的 Projective Node Orbit（PNO）表征，也不是正式 K=16、五 seeds、bootstrap gate；当前只是 candidate=3 的 CPU 接线验证。

`m1_trainability.py` 解决“低准确率到底是网络根本学不会，还是数据/训练不足”的问题：输入是相同的 candidate=3 paired arrays、全标签容量设置或不同 paired-group/更新步数组合，输出是可观测准确率上限、teacher error、student-to-teacher amortization error 和 causal graph 指标。例如 exact ambiguous pair 的两个样本 online vector 相同而答案相反，所以确定性学生的总体上限是 97.5%、歧义点上限是 50%；全标签测试应比较这个上限，不能假定 100%。它不是调正式 test、不是修改冻结 gate，也不把容量通过写成 CTL 已胜出。

`m1_metrics.py` 解决“图错误和统计比较不能只剩一个 accuracy”的问题：输入是预测/参考/base graphs 或真实连续的状态序列，输出分别为 post-graph correctness、错误开放事实、缺失事实、false birth、collateral、invalid，以及保持 paired group 的分层 bootstrap CI。例如预测多建一个带错误位置边的对象，会同时记一个 false birth 和一个 contamination，不能互相抵消。rollout 接口要求恰好 20 个有顺序的状态，拒绝把 20 个独立样本冒充 self-rollout；`m1_af_rollout.py` 已在非正式 smoke 中用该接口评估 A–F，但正式 paired bootstrap/gate 仍未运行。

当前 executor 实现 C00–C11 所需的 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE 和 COMPOSITE:REPLACE。pending manager 实现 D-023 的低置信度 gate、低权重证据、有效观察机会、可检索归档、重新激活与带 provenance 的消费。它仍是确定性支持机制，不是 CTL 模型。

事实级 RETRACT 需要两条满足 D-022 的可靠空观测；REPLACE 必须按 RETRACT→BIRTH→ADD_EDGE 执行并保留旧对象身份。节点级 RETRACT 尚未实现，会被显式拒绝。

开发模块白话：dev_data 把“旧物体还在、出现新物体、原物体移动”变成竞争世界并评分；dev_learning 用这些结果教小网络，只用已经获得的信息做决定。旧开发 harness 与新的 paired causal smoke 都已接 A–F，其中 D 删除 future 教师项，F 是候选预算内 oracle；这些开发结果只记录在 [EXECUTE.md](../EXECUTE.md)，不等于正式 M1 比较。输入输出、损失、局限详见 [开发合同](../experiments/counterfactual_transaction_learning/DEVELOPMENT.md)。解析三位置投影不是 PNO；三个候选的 smoke 不是完整 CPMT。executor 仍无梯度且不依赖 learned scorer。
