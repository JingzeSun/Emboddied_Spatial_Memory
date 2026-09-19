# CPMT Test Plan

定位：测试覆盖与待补测试规格；最近实际执行数量、是否通过及失败记录只写 [EXECUTE.md](../EXECUTE.md)。测试代码存在不等于本次已运行，也不等于方法有效。

test_vsmt_lean_memory.py 是 D-224 / S0-01 的合同测试：检查实体记忆的字段、状态机与版本链合法性，五个原子（NOOP/BIND/BIRTH/RETRACT/REACTIVATE）各有正例与反例，REPLACE 展开为 RETRACT+BIRTH 且两半都须合法，非法程序整帧回滚且调用者手里的旧记忆逐字节不变，共享 dormancy 与共享去重是确定性的且数值必须显式传入，实体 token 字段顺序与机器合同一致且不含私有或场景标识，帧级稀疏残差只列改动过的实体。白话：输入是手写的小记忆和帧程序，输出是通过或拒绝；例如 REACTIVATE 一个仍然活动的实体必须被拒绝且整帧不生效。它只证明机械语义正确，不证明 VSMT-lean 有效、数据已生成或任何数值已冻结。

test_vsmt_lean_intervention.py 是 D-224 / S0-02 的只读检查测试：检查 house 划分是 (seed, house_id) 的纯函数且三份互斥、清单被篡改即拒；路线只能使用八个登记动作且观察数等于动作数加一；三类干预的端点规则、每 episode 上限、同一物体不得被干预两次、窗口不得越界；干预窗口内每个相关容器每一帧都必须被判为不可见，判定缺失、缺少深度帧摘要或只是「假值」而非严格 False 都拒绝；三面文件互斥且部署读取器不得挂载 private 或 provenance；公开帧记录任何层级不得出现 house/scene/object/instance 等标识；失败 house 必须留回执且不得替换，计划数必须等于成功数加失败数。白话：输入是手写的划分、路线、干预计划与可见性判定，输出是通过或拒绝；例如源容器在窗口中间重新可见，整条 episode 必须失败而不是缩短窗口。它不生成数据、不调用模拟器、不读取 RGB-D，也不证明干预在科学上可构造。

test_vsmt_lean_assignment.py 是 D-224 / S0-03 的合同测试：检查冻结前端一帧的字段与几何合法性；活动实体召回受距离上限约束而休眠与已撤回实体不受约束；召回顺序不随记忆列表排列变化；三张特征表的字段顺序与元数一致；存在特征确实依赖分配结果，因此必须在求解之后计算；自写矩形匈牙利在 40 个随机矩阵上与暴力枚举的最优值一致、重复调用结果不变、行多于列或参差矩阵被拒；召回之外的组合拿到有限但极大的代价，两个色块不能共用一个实体，一个色块不能占用别的色块的新建列；只改私有数据时召回顺序、特征矩阵、封存摘要与参考分数必须逐字节相同，任何一项被改都会被抓到。白话：输入是手写的一帧、一份旧记忆和三个头的 logit，输出是通过或拒绝以及一次分配；例如两个色块都最像同一个旧实体时，只有一个能拿到它。它不训练模型、不读取私有数据，也不证明这些特征有用。

test_vsmt_lean_teacher.py 是 D-224 / S0-04 的合同测试：检查私有数据只能凭同时写明两段封存摘要的放行回执打开，链条断裂或指向另一帧就不发回执，且源码不 import 方法求解器、不打开文件；实体身份按带物体证据的严格多数解析，并列判为含糊而不是猜，背景证据不投票；色块主导物体按实例重叠表判定，没有物体记 unlabelled、覆盖两个物体且占比不足或并列记 identity_ambiguous、单物体占比不足记 unlabelled；色块目标列各有正例（被召回的匹配实体、匹配实体不在召回内记 recall miss、记忆里没有该物体记 birth、物体证据困在含糊实体里记 identity_ambiguous 而不猜 birth、重复实体折向首版本最早者、只有重复者被召回时以它为目标、retracted 实体可作目标），且 teacher 不改不重排召回；存在标签区分物体缺席、被搬动与被遮挡，dormant 候选可判、retracted 候选拒绝而不跳过；三分解把每个决定恰好归入一类且五类之和等于决定数，分配与标签、决定与候选集合不对应即拒；评价器自己的最大权匹配在随机小矩阵上与暴力枚举一致，dormant 实体按推荐口径算作预测节点与残留，执行器写入不同表面 ID 后各指标逐字节相同；节点 P/R/F1、Missing 残留率（未可观察者单列）、假撤回率、身份连续率（承认搬动前任一承载实体、不承认新建）、三类干预的记忆正确判定、从首次可观察帧起算的恢复延迟（未恢复与从未可观察分别单列）、梯形积分的污染面积、规模与成本各有手算例；报告出现清单外指标或字段被拒；house 级配对 bootstrap 同 seed 结果相同、方向语义正确、某 house 缺臂即拒，最强对照逐指标按方向选取，消融只报不设门；nuisance probe 四字段对三种标签全跑并能抓出泄漏的帧号字段；合同的 41 条布尔声称逐条翻转、缺失或新增均被拒，多一项指标或字段、改动 IoU 0.3 / bootstrap 10,000 / 95% 常量、改动状态集合、提前填五个待冻结数值均被拒。白话：输入是手写的记忆、召回、分配和私有真值，输出是标签、计数与指标；例如旧杯子实体在召回里而学生把色块分到新建列，记 amortization error。它不生成数据，不证明指标有区分度，也不证明任何数值合适。

test_ctl_dev.py 检查真实候选分叉不改 base、在线字段拒绝未来/真值、相同输入的不同未来、历史可消歧、分组不交叉、不读取 test、数据可复现、能量一致、参数真实更新和未来不影响在线 forward。白话：检查模型有没有偷偷看答案、代码有没有真的训练，不用单元测试宣称研究假设成立。概念解释见 [开发合同](../experiments/counterfactual_transaction_learning/DEVELOPMENT.md)。

test_m1_protocol.py 检查 pre-test 配置能生成稳定指纹，并对开启 test、删除 A–F 方法、用计划动作冒充真实 future、拆散 paired bootstrap 给出反例。输入是正式配置候选，输出是通过或拒绝；它不是统计功效验证，也不代表 test 已生成或 M1 已通过。

test_m1_data.py 检查十二 family、八原子事务正例、同一 immutable base、非法分支保留、reference top-1、ambiguous sibling 在线输入相同、可辨 sibling 只差合法历史 cue、train/validation group 与 asset 隔离，以及 test 入口不存在。它还要求 future 是固定投影 observation，不是 reference graph hash。测试通过只表示生成接口守约，不表示 archetype 已有足够多样性或正式 ground truth 已获验证。

test_m1_metrics.py 用手算小例检查 graph correctness、contamination、missing fact、false birth、collateral/invalid 分开计数，20-step rollout 拒绝错误长度，并验证 bootstrap 不拆 paired group、效果方向和 Holm 校正。它不是统计显著性结果，也没有运行 A–F 模型。

test_m1_rollout.py 检查程序化世界确实形成 20 个首尾相接的 graph versions、事件顺序和空间关系随 seed 变化、八种原子事务与 REPLACE 都有可执行正例、固定 K=16 不读取 reference 字段、canonical 去重、非法 protected 分支完整保留、H=3 尾部按 3/2/1 遮罩，以及 train/validation/test 边界。白话说，输入是一条生成序列和候选选择，输出是每一步真实执行后的预测图；删掉完整 `reference_spec`、改变 audit family 后候选列表必须不变，匿名 proposal observation 也不能含对象/边身份字符串，oracle 选择则必须精确重放 reference。关键三项测试在开发中曾各自以独立进程通过；最终实际执行状态与中断只记录在 EXECUTE。这仍不证明模型会选择正确候选、正式 M1 有效或全部测试在同一进程通过。

同一文件还检查 paired continuous siblings：pivot 之前和当步的 online payload 必须逐字节相同，reference program/post-world/future trace 必须不同，分叉后两个 oracle 必须各自重放到自己的正确终态。它解决的是相同当前信息存在多种合法 latent future 的数据条件，不等于整条 episode 都不可辨识，也不等于模型能超过信息上限。

test_m1_af_rollout.py 检查 A–F 的共享 online encoder 拒绝 audit 字段、future 存储变化不影响 online vector、10% 标签按完整 paired group 提供、非法候选在教师前被 mask、A–E 学生参数量一致，以及 F 在 causal replay 中得到零污染的正确终态。白话说，输入是小型 train/validation paired sequences，输出是六方法训练和回放结果；它防止把 future 偷塞进在线推理或让某个学生多拿参数。两步训练 smoke 只证明代码接线，不是方法比较结果。

test_m1_trainability.py 检查诊断配置不能打开 test/冒充 formal、数组子集不拆 paired siblings、reference coverage 与 candidate miss 分开记录、exact ambiguity 的可观测上限为 97.5%，以及全标签容量点使用真实学生而不是 oracle。`test_m1_rollout.py` 另要求 offset shard 与一次性生成的同一 group 字节级等价。白话说，输入是已有 paired train 数据和诊断步数，输出是“模型能否学到可见信息上限”的审计；它不等于验证泛化、正式统计显著性或 CTL 优势。

## M0 Contracts + executor

- [部分] cpmt-0.2 graph/program draft 正反例；
- [部分] intent/template/primitive compatibility；
- [完成] BIND vs REACTIVATE lifecycle；
- [完成] SPLIT evidence partition 与 MERGE deterministic canonical；
- [完成] 事实级 RETRACT 的双重可靠空观测、遮挡/低可靠度/无效几何/中断证据反例；
- [完成] REPLACE=RETRACT+BIRTH order，且旧 identity 不被附带撤回；
- [完成] NOOP world hash 不变；
- [完成] QUARANTINE 不改 world、弱证据保留、重复视角不重复加权；
- [完成] 只有有效观察机会累计 K，归档后仍可检索和重激活；
- [完成] pending consumption 必须保留全部 evidence 与 transaction provenance；
- [完成] anchored/unlisted 旧身份固定、显式 exchangeable 集合内置换、新 local identity 严格双射；
- [完成] 新身份不得映射到旧身份，外部锚定的新身份不得改名；
- [完成] 映射后的 lifecycle、版本、事实、证据/latent 归属、protected 与 pending 状态必须一致；
- [完成] 新 ID、审计编号与无意义排列可规范化；有限未来投影相似不得定义等价；
- [部分] wrong version、multiple open version 被拒绝；dangling edge/duplicate ID 待扩展；
- [完成] protected IDs、atomic rollback、provenance、重复 transaction 显式拒绝；
- [完成] RELINK 必须真正改变 relation target；同 target 的版本空转被显式拒绝；
- online record 不含 future/oracle/test-only fields；
- paired group split 不相交。

## M1 Mechanism

- candidates 从同一 base version；
- energy 保存 now/future/edit/growth/collateral/illegal；
- total 与分项/权重一致；
- illegal candidates 在 posterior 前 mask；
- current-identical pairs 在 future 上可分；
- A–F 使用同一 split/front-end/预算；
- 六方法开发 harness 接线完整，D 使用无 future 的执行教师，F 明确为 oracle upper bound；
- candidate、teacher、amortization error 分开。

## M2 Online

### M1-development 单房间视觉接口

- 固定针孔投影与 depth+pose 反投影互逆微型例；
- 换视角重见、首次发现、移动后重访分别选择 BIND/BIRTH/RELINK；
- 四候选共享一个 immutable base，合法分支有 post hash，非法分支保留失败；
- 每个分支都记录 now/future/edit/growth/collateral/illegal；
- online 嵌套 JSON 拒绝 future、teacher、oracle 和 simulator object ID。

白话：这些测试检查“真实画面进来前后，事务执行和数据隔离的管道有没有接反”。输入是小型几何、相机和匿名区域，输出是候选分支、六项能量及泄漏拒绝；例如物体搬到新位置后，RELINK 应投影到新视角，旧视角不应再预测它。它不是 RGB 识别准确率、PNO 训练或正式 M1 效果证明。

- Projective Node Orbit 的 reprojection/equivariance/visibility；
- teacher-forced 与 self-rollout 隔离；
- 0/1/10/100% labels；
- contamination、growth、invariant survival；
- seed 可重复、失败 run 不丢。

## M3 Formal

- paired bootstrap 与手算微型例一致；
- test seal；
- external manifest/license；
- artifact cold-start。

fixture/unit test 通过只证明合同实现，不证明 CTL 有效。

M1-v2 新增反例覆盖：E 的 scorer penalty 不得含 executor 产生的百万非法惩罚；paired sibling 必须沿各自真实 primary/contrast future 前进；错误 RELINK 的下一次相关可见观察必须出现唯一可执行补偿；active world 恢复后 history 仍保持不一致；commit 网格必须含 K=16 未校准 softmax 可达到的阈值，且 report groups 不参与选择；observable oracle 对不可辨 sibling 必须共用同一决策；target-only 诊断必须保留并列集合而不是依赖首索引，E 的 masked BCE 与候选排序必须分开报告，relation oracle 的合法性只能事后审计并拆成合法/非法 wrong-template，causal 汇总必须保留未受 rollout 漂移影响的 initial-step invalid rate。输入是小型受控 graph/arrays，输出是通过或明确失败；这些反例不是模型效果、恢复率或正式统计结论。

S1/S2 还检查 train/inner-dev 的哈希分区不拆任何 paired sibling 或 recovery rows，专用 scorer runner 不读取 validation/test、不训练 online student、不校准 gate。白话说，它输入完整 train arrays，输出互斥的拟合集和开发留出集；通过只证明没有数据串组，不证明选出的 scorer 能在 validation 或 causal rollout 上工作。

运行：

```powershell
python -m unittest discover -s tests -v
```
