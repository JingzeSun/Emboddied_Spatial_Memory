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


## Frozen pre-test protocol v1（D-031 accepted，test 尚未生成）

机器可读合同为 [`configs/m1_hard_condition.json`](../../configs/m1_hard_condition.json)。D-031 已将状态冻结为 `frozen_pretest`，但这不是已经产生论文结果的 formal run；配置中的 `test_access=false` 仍由校验器强制检查。生成器、指标和泄漏测试实现通过前不得生成或读取 test。

### 数据与 future

- C00–C11 每个 family 计划生成 1000/200/200 个 train/validation/test paired groups；同一 `paired_group_id + world_seed + asset_family` 不跨 split，每个 family 的 test support 不低于 200。只排除在任何方法运行前就已确认的 schema 或生成/渲染失败；方法自身失败必须保留。
- 主 future horizon 固定为实际已执行轨迹的 3 个后续决策点，H=1/5 只作报告型消融。变长 episode 只评分真实存在且 pose/visibility 有效的 future；至少有一步 future 的尾部样本保留并 mask 缺失步，零 future 样本只进 online 诊断，不训练 hindsight teacher。
- 可见正证据与“可靠可见但为空”都进入评分；遮挡和未观察区域 mask。预计算 online feature 只允许时间戳不晚于当前决策，future cache 分目录保存。

白话：future policy 解决“老师到底能看哪几眼”的问题。输入是机器人后来真实走过并看到的帧、位姿与可见性，输出是哪些后续证据可给离线老师评分。例如三步后回看旧桌面且明确为空，可以反对仍保留旧位置的候选；被柜门挡住则不算空。它不等于在线模型预知未来，也不等于拿计划但未执行的动作当真实证据。

### 候选、教师与六方法公平性

- A/D/F 共用 deterministic top-K，K=16；覆盖 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE，REPLACE 仍是 RETRACT+BIRTH，QUARANTINE 仍是不改 persistent world 的 wrapper。SPLIT/MERGE/RETRACT 必须有正例。
- 每个候选从同一 immutable base 克隆执行，先按 canonical memory-state equivalence 去掉纯改名重复；非法候选不消失，保留 failure 后以正无穷 mask。
- 教师逐候选保存 now/future/edit/growth/collateral/illegal。v1 权重固定为 1/1/0.1/0.25/10，illegal 用正无穷 mask，temperature=0.25；这些值沿用人工审阅过的单房间接口尺度，不能看正式 test 后重调。
- A–E 共用 online encoder、输入字段、学生更新数和 split，训练参数量差异不超过 10%；每方法最多 6 次 validation trial。C 的 future auxiliary weight 可在 {0.1,1,10} 内独立选。E 的额外 scorer 参数、更新、耗时和显存单列，不能藏进共同预算。F 是 K=16 内 oracle upper bound，不是可部署模型。
- B/C/E 在学习/打分时不执行全部反事实分支；但评价 persistent memory 时，所有方法选中的最终事务都由同一个 executor 应用，再算 post-graph 指标。

白话：公平协议解决“CPMT 是否只是比对照多拿了答案或算力”的问题。输入是同一批 online 信息、同一候选语言和可核对的训练预算，输出是 A–F 可比的预测、运行成本与失败。例如 C 可以认真调 future loss 权重，但不能读 post-edit world；E 可多用一个结果预测器，但这部分参数和时间必须明报。它不等于强迫网络结构一模一样，也不等于把 F 的 oracle 成绩当实际系统成绩。

### 指标、统计与 go/no-go

- 主标签比例为 10%；0/1/10/100% 全部报告。正式优化种子固定为 7/19/31/43/59。
- 主指标定义为：post-graph correctness（执行所选事务后，完整决策相关图与 reference/equivalence set 一致的比例）；memory contamination（20 个 self-rollout 决策后，每 100 次决策仍开放的错误事实数）；false-birth growth（同一时点每 100 次决策多出的 open entity 数）；collateral violation（每 100 次决策对 protected/无关状态的修改数）。
- primary contrasts 只有 A–C 和 A–E。按 `paired_group_id`、family 分层做 10,000 次 paired bootstrap，95% CI；两项主对比用 Holm–Bonferroni 控制 family-wise alpha=0.05。
- 每个主对比都必须同时达到：graph correctness 绝对提高至少 3 percentage points；contamination 每 100 决策绝对减少至少 2，且校正后 95% CI 排除零。false-birth 每 100 决策非劣 margin=1，collateral margin=0.5；executor invariant violation 必须为 0。
- candidate coverage@16 必须总体至少 98%、每 family 至少 95%；未通过时暂停 scorer/CTL 结论并归为 candidate miss。结果分别报告 candidate miss、teacher error、amortization error、rollout error。
- A 对 C 或 E 的 CI 若排除了上述最小有意义收益，则停止扩模型，不进入 M2；不得靠 PNO、更大数据或第二任务找正结果。

白话：最小有意义效应解决“统计上有一点差，但实际是否值得”的问题。输入是同一 paired group 上 A 与对照的逐例差，输出是平均差和不确定范围。例如 A 正确率高 3 个百分点且长期每 100 次少 2 个错误事实，才算达到预先认定的机制收益；只把 latent loss 降低不算。它不等于要求每个样本都赢，也不等于把四个指标揉成一个可以互相抵消的总分。

白话：safety 非劣门槛解决“主指标变好是否靠制造更多错误节点或误改旁边对象”的问题。输入是 false-birth、collateral 和 invariant 计数，输出是是否仍在允许差值内。例如正确率提高但每 100 次多建 3 个假对象会失败。它不是额外奖励项，安全失败不能被平均准确率盖住。

### 计算边界

先在本地做 generator/metric/unit validation，单个正式 run 上限 2 小时；发现新的宿主机 BugCheck 立即停止长 run。当前云预算授权为 AUD 0，不租服务器。是否需要云卡只依据实现后的实测峰值和稳定性另行决定。

白话：计算边界解决“什么时候真的需要租卡”。输入是本地实测 wall-clock、peak VRAM、缓存体积和稳定性，输出是继续本地或另行申请云预算；例如小型 M1 若低于 8 GiB 且两小时内完成，就不因显卡型号先租服务器。它不等于承诺 4070 Laptop 足够后续 M2，也不授权任何付费资源。
