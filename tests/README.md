# CPMT Test Plan

定位：测试覆盖与待补测试规格；最近实际执行数量、是否通过及失败记录只写 [EXECUTE.md](../EXECUTE.md)。测试代码存在不等于本次已运行，也不等于方法有效。

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
