# CRITERIA：判定规则、指标释义与数字例子

状态：**定义草案；阈值尚未接受。** HC-013 决定总体评测口径，HC-015/016/017 决定时间、
提交门和结构化基线口径。本文把“指标是什么”与“多少算通过”分开，防止先看测试结果再定标准。

## 0. 共用记号

- `G*`：该案例必须执行的 gold operations。
- `P`：系统实际提交的 operations。
- `A*`：gold affected facts，允许被写入的最小闭包。
- `C*`：gold control facts，明确必须保持不变的事实。
- `Dep*`：由直接变化触发、必须传播的 gold dependency updates。
- `H`：系统触碰过的全部旧事实，包括最终又改回去的事实。
- 一次“提交”以 transaction 为单位；同一 transaction 的局部操作不能拆开算多个独立成功。

## 1. 案例进入评测前的完整性标准（DC）

| ID | 含义 | 数字例子 |
|---|---|---|
| DC1 Gold completeness | 所有必要操作、允许作用域、控制事实均已标注 | 应撤销 2 条、增加 3 条，共 5 个 gold op；漏标 1 条则案例退回，不计分 |
| DC2 Input determinism | 固定输入多次序列化一致 | 同一 fixture 连跑 5 次 hash 全相同；4/5 相同不算通过 |
| DC3 Identity validity | 每个引用实体都存在且时间上合法 | 20 个引用 ID 中 20 个可解析为 100%；19/20=95% 不通过 |
| DC4 Dependency closure | gold 已列出直接变化的必要依赖闭包 | cart 移动后 box 与 room 两条关系都要更新；只标 1/2 不完整 |
| DC5 Control separation | control 与 affected 不重叠，且确实无关 | `|A* ∩ C*|=0`；若 1 条重叠，修正标注后才能运行 |

## 2. 提交前证据标准（EG，待 HC-016）

这些是规则，不是模型分数。每次 destructive operation 必须给出机器可检查的 preconditions。

| ID | 意思 | 可接受例 | 不可接受例 |
|---|---|---|---|
| EG1 Identity support | 有证据说明观测对象就是被修改实体 | ID 后验 0.97 且跨视角匹配一致 | 只因同类别就覆盖 `mug_7` |
| EG2 Positive support | `add/replace` 的新事实被正证据支持 | 3D 几何与接触检测都支持 `on(mug,desk)` | VLM 猜测但无可定位观测 |
| EG3 Reliable negative support | `retract` 不能把“没看见”直接当“不存在” | 目标位置被完整重观测 2 次且可见性模型均预测应可见 | 物体被柜门挡住而 `visible=false` |
| EG4 Temporal order | 证据时间不早于被推翻事实的最后支持时间 | 旧事实最后支持 t=10，新冲突首见 t=14 | 用 t=8 的帧撤销 t=10 的事实 |
| EG5 Dependency witness | 每个传播写入都有显式依赖路径 | `cart moved -> supported box pose invalid` | 因同一房间就更新所有物体 |
| EG6 Conflict handling | 高质量证据互相冲突时隔离而非强行提交 | 两路传感器一正一反，状态转 `quarantined` | 任取最新一条覆盖 |

建议起始规则（仍需人工接受）：一条高质量、完整覆盖的独立重观测，或至少两个独立 evidence
groups 支持缺失，才允许破坏性撤销；相邻视频帧属于同一 evidence group，不能虚增票数。

数字例：帧 101–110 来自同一次静止相机扫视，即使有 10 帧，都只算 1 组；另一个位置在帧
205–210 完成独立重观测后才达到 2 组。

## 3. 操作正确性（OP）

| ID | 公式/含义 | 数字例子 |
|---|---|---|
| OP1 Operation precision | `|P ∩ G*| / |P|`：提交的操作中多少是必要且类型正确 | 提交 35 个，32 个正确：`32/35=91.4%` |
| OP2 Operation recall | `|P ∩ G*| / |G*|`：必要操作完成多少 | gold 40 个，完成 32 个：`32/40=80%` |
| OP3 Change-type accuracy | 变化类型（stable/moved/appeared/missing/unknown）是否正确 | 20 例判对 17 例：`85%` |
| OP4 Atomic validity | transaction 是否全有或全无、无非法半提交 | 50 次事务中 1 次只撤销未增加：`49/50=98%`，且触发硬失败 |

操作必须比较实体、predicate、旧值、新值与有效时间语义；只比较字符串相似度不算命中。

## 4. 必要更新与依赖传播（UP）

| ID | 公式/含义 | 数字例子 |
|---|---|---|
| UP1 Necessary fact recall | 必须改变的事实有多少达到正确最终状态 | 应改 12 条，正确改 11 条：`91.7%` |
| UP2 Dependency propagation recall | `Dep*` 中多少被正确更新 | cart 移动要求 10 条依赖更新，完成 9 条：`90%` |
| UP3 Affected-scope precision | 被触碰事实中多少属于 `A*` | 触碰 11 条，其中 9 条在允许闭包：`9/11=81.8%` |
| UP4 Minimality excess | `|H \ A*| / max(1,|A*|)`：多碰了多少无关事实 | `|A*|=10`，多碰 2 条：`20%`，越低越好 |

`H` 采用操作日志而非最终快照计算，因此“先误删、再补回”仍算 collateral touch。

## 5. 无关事实保留（CP）

| ID | 公式/含义 | 数字例子 |
|---|---|---|
| CP1 Control preservation | control 中最终未变且历史未被触碰的比例 | 50 条 control，48 条完全保留：`48/50=96%` |
| CP2 Collateral edit rate | `|H ∩ C*| / |C*|` | 50 条 control 误触 2 条：`4%`，越低越好 |
| CP3 Stable-case exact match | gold 为 stop 时，整份 belief/version 是否完全不变 | 30 个 stable case 中 29 个零写入：`96.7%` |

核心主张要求 CP1 高且 CP2 低；只看最终图 F1 会漏掉中途误写和版本污染。

## 6. Stop、拒绝与提交质量（ST）

| ID | 公式/含义 | 数字例子 |
|---|---|---|
| ST1 Stop precision | 系统说 stop 的案例中，多少确实无需更新 | stop 25 次，23 次正确：`92%` |
| ST2 Stop recall | 确实无需更新的案例中，多少成功 stop | 30 个稳定/证据不足案例，stop 23 个：`76.7%` |
| ST3 Commit precision | 发生 commit 的事务中，多少全部合法 | commit 35 次，32 次合法：`91.4%` |
| ST4 Unsafe commit rate | 应 quarantine/stop 却执行破坏性写入的比例 | 20 个证据不足案例误写 1 个：`5%`，并按硬门处理 |

“总是什么也不改”会有高 stop precision 或 control preservation，但 UP1/OP2 很低；必须联合报告。

## 7. 时间与版本（TV，待 HC-015）

| ID | 含义 | 数字例子 |
|---|---|---|
| TV1 Valid-time coverage | 真值变化时间是否落入系统区间 | 最后支持 t=10、首次冲突 t=14，输出 `(10,14]`；真值 t=12，coverage=1 |
| TV2 Interval width | 时间区间宽度，越窄越有信息，但不能牺牲 coverage | `(10,14]` 宽度 4 秒；`(0,14]` 宽度 14 秒 |
| TV3 Observation-time error | 若任务提供真值且系统输出可比点估计，点估计误差 | 估计 12.8、真值 12.0，绝对误差 0.8 秒 |
| TV4 Transaction-time validity | `recorded_at >= observed_at` 且版本单调 | 100 个版本全部单调为 100%；出现回退 1 次即硬失败 |
| TV5 Version-chain validity | parent、base、commit/reject 状态是否形成合法链 | 40 次事务中 40 条可回放；缺 1 个 parent 为 97.5%，硬失败 |
| TV6 Provenance completeness | 每个提交事实是否有证据源、时间和规则/模型版本 | 60 个写入中 57 个字段齐全：`95%` |

没有物理变化真值时不计算 TV3，也不能把 `first_observed_at` 当作真实 `changed_at`。

## 8. 最终状态与任务效用（FS）

| ID | 含义 | 数字例子 |
|---|---|---|
| FS1 Fact F1 | 最终 canonical facts 的 micro/macro F1 | P=0.90、R=0.80，则 F1=`84.7%` |
| FS2 Node/edge F1 | 与场景图论文共同可比的节点和关系质量 | edge TP=80, FP=20, FN=40，F1=`72.7%` |
| FS3 Query accuracy | 用更新后的世界模型回答查询是否正确 | 100 个位置/关系查询答对 86 个：`86%` |
| FS4 Downstream success | 固定策略读取 posterior 后的任务成功率 | 50 个取放任务成功 38 个：`76%` |

FS 指标允许与 snapshot 方法比较，但不能单独证明 bounded revision、provenance 或版本正确。

## 9. 效率（EF）

| ID | 含义 | 数字例子 |
|---|---|---|
| EF1 Latency | 每次 revision 端到端时间，报 p50/p95 | p50=42 ms，p95=110 ms |
| EF2 Touched-fact count | 一次更新读取或写入的事实数 | bounded 12 条，full graph 800 条 |
| EF3 History growth | 每 100 次观测新增版本/字节 | 100 次观测新增 18 版本、240 KB |

效率只在相同硬件、缓存、输入规模和批处理设置下比较。

### 9.1 学习模型指标（LM）

这些指标评价概率模型，不能替代 OP/UP/CP/ST/TV 的世界事实合同。

| ID | 意思 | 具体数字例子 |
|---|---|---|
| LM1 Gate macro-F1 | preserve、quarantine、commit 三类各算 F1 再平均，防止多数 preserve 掩盖少数类 | 三类 F1 分别 0.96、0.60、0.84，macro-F1=`(0.96+0.60+0.84)/3=0.80`，不能只报 92% accuracy |
| LM2 Transaction exact match | gate、target set、operator set 和事务合法性全部正确才命中 | 100 个事务中 78 个全对，即 78%；其中 10 个只错时间区间也全部算错 |
| LM3 Negative log-likelihood | 真类概率越高越好；对过度自信错误惩罚大 | 真类概率 0.8，单例 NLL=`-ln(0.8)=0.223`；若错误地只给真类 0.01，NLL=4.605 |
| LM4 Multiclass Brier | 概率离 one-hot 真值的平方误差，越低越好 | 预测 `[0.8,0.1,0.1]`，第一类为真；按三类平均为 `(0.2²+0.1²+0.1²)/3=0.02` |
| LM5 ECE | 置信度与实际正确率的分箱差距 | 100 个置信度约 0.8 的样本只对 65 个，该箱 gap=15 个百分点；各箱加权得总 ECE |
| LM6 Selective risk | 系统只提交高置信事务时，剩余 commit 的错误率 | 全提交 100 次错 12 次，risk=12%；只提交 70 次错 2 次，coverage=70%、risk=2.86% |
| LM7 Counterfactual pair consistency | 单因素反事实的两例是否都响应正确 | 50 对中 46 对两边都对，pair consistency=92%；不能把 96/100 单例正确冒充 96% 配对一致 |
| LM8 OOD retention | OOD 指标保留 ID 表现的程度 | ID transaction EM=80%，OOD=60%，retention=`60/80=75%`；同时必须报绝对下降 20 点 |

### 9.2 候选 learned Go/No-Go（尚未接受）

用于尽早判断是否值得扩大训练，而不是论文最终门槛：

1. tiny-set：256 个样本训练 transaction EM ≥98%；否则优先排查实现/标签；
2. label-prior 与随机/打乱输入不得接近主模型，否则检查泄漏或数据过易；
3. BEGR-Net 在 validation 上相对最强 learned baseline，UP1 下降不超过 1 个百分点，同时 CP2 或 ST4 至少一项有预注册的实质改善；
4. typed-edge ablation 在 dependency-depth OOD 无下降，则删除“结构依赖带来泛化”的 claim；
5. 双时间消融在 late/stale cases 无下降，则删除“bi-temporal 建模必要”的 claim；
6. 所有硬失败必须逐例报告；是否要求 0 次由 HC-013 冻结。

上面的 98%、1 个百分点等是**候选工程门**，不是从测试结果倒推的论文阈值。正式阈值需在接触 test 前由 HC-013/017 冻结。

### 9.3 哪些必须由研究者人工决定

| HC | 人工决定的不是“模型参数”，而是什么 | 一个数字例子 |
|---|---|---|
| HC-001 | 0.92 identity posterior 是否足以把新观测当同一实体，还是保留两假设 | 阈值设 0.95 时 0.92 必须 quarantine；设 0.90 时可进入 commit precondition |
| HC-002/003 | 哪些 relation 是 stored/derived，哪种 operator 可传播几跳/到哪类边停止 | `moves_with` 最多传播 2 跳；碰到 `near` 立即 stop |
| HC-004/016 | 几组怎样的负证据才算 reliable absence/允许 destructive write | 10 个相邻帧同属 1 group；规则要求 2 个独立 groups 时仍不能 invalidate |
| HC-005 | 多个最小事务怎样算同样正确 | 两套合法 target set 大小分别 3 和 4；若都满足 invariants，可放入 acceptable set，而非强迫 exact match 到其中一个 |
| HC-011 | 哪些 residual 先解释为 ego-motion、sensor conflict 或 world change | pose 重投影残差 3 cm 在容差 5 cm 内时走 reveal，不触发 revision |
| HC-013 | 哪些是 100% 硬门、哪些用均值/置信区间、何时 No-Go | 100 个中 1 次 occlusion deletion：即使平均准确率 99%，仍可规定为 No-Go |
| HC-015 | 真实变化时刻未知时输出点还是区间 | last support=10、first contradiction=14，则输出 `(10,14]`，而非猜 12 |
| HC-017 | 哪些外部方法是 native structured baseline、哪些只能比快照 | adapter 120 条事实映射对 117 条=97.5%；若门为 100%，不得进入 updater 因果主表 |
| HC-018 | 是否允许先实现上述 posterior-only 通道 | 接受后可先做 P1–P4；拒绝则仍需先冻结 W0–W4 等完整闭环语义 |

模型宽度、学习率和 loss weight 由 validation protocol 选择，不需要研究者凭感觉逐项决定；语义、禁止行为、gold equivalence 与 baseline 准入必须人工冻结。

## 10. 硬失败与 No-Go

以下任一项发生，不能被平均分掩盖：

- 遮挡或单次 `visible=false` 直接导致存在性删除；
- 目的地未知时编造新位置；
- 必要依赖关系漏更；
- 写入 gold control fact；
- 事务出现非法半提交或版本链不可回放；
- 提交事实缺失证据来源；
- 使用 test split 调阈值、选提示或筛方法。

示例：99 个案例完全正确，1 个案例因遮挡删除物体。平均准确率可能是 99%，但仍触发
“occlusion deletion”硬失败；必须单列失败案例，不得宣称通过安全门。

## 11. 阈值该怎么定

阈值不是指标定义。推荐顺序：

1. HC-013 先接受硬门（推荐 oracle fixtures 上 100%）；
2. 在 training/development 构造实现，不看 test；
3. validation 上冻结 commit/stop 阈值，并报告灵敏度曲线；
4. test 只跑冻结版本；
5. 同时报绝对值、置信区间、逐场景结果和配对差值，不只报单一均值。

候选的演示性成功条件（**不是已接受阈值**）：B6 相对最强 B3/B4/B5，在 UP1 不下降超过
1 个百分点的前提下，CP2 绝对下降至少 10 个百分点，且全部硬门为 0 次失败。最终数值须由
HC-013/017 明确接受后才能写入 frozen config。
