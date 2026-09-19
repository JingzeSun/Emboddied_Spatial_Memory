# VSMT-lean 方法合同（D-224）

> 本文件只定义当前首篇方法：**Versioned Structural Memory Transactions 的精简版（VSMT-lean，实体生命周期版本化事务）**。旧 CPMT、空间世界模型（D-062）、地点双层记忆（D-210）、统一四类图（D-213）、八原子候选枚举与结构估计器（D-214～D-223）的方法文本已随分支 `archive/pre-d224-unified-graph` 归档，本文不复述；需要时从该分支或 Git 历史读取。本文全部小节均为 **proposed**：机器合同未写、数据未生成、模型未训练、效果未验证。数值凡写"proposed"者均待 S0 合同冻结，凡写"null"者由后续步骤按登记规则选择。

## 一、问题定义

VSMT-lean 解决的问题是：机器人在多视角历史中重访时，对象级记忆里的每个实体应当**保持、绑定新证据、新建、撤回还是恢复**。输入是截至当前帧 t 的公开观测 O_t（冻结前端产生的匿名 fragment、公开几何、自由空间与可见体积、因果相对位姿、动作摘要）和系统自己此前预测的记忆 M_{t−1}；输出是本帧一个由 NOOP/BIND/BIRTH/RETRACT/REACTIVATE 组成的合法程序 Π_t、新记忆版本 M_t = exec(M_{t−1}, Π_t) 和证据归属。

白话：它回答"原来那把椅子现在看不见，是被挡住、走出视野、检测漏了，还是真的被搬走"，以及"眼前这个东西是旧的、新的，还是以前撤回过的又回来了"。例如杯子原位置连续三帧被可靠自由空间覆盖，而另一张桌面出现一个高相似 fragment，本帧程序应当是把旧杯子 REACTIVATE 到新位置，而不是 RETRACT 加 BIRTH。它不是地点或拓扑修订，不学习 SPLIT/RELINK，不训练视觉前端，也不把 executor、DINOv2 或五个操作名字单独当作创新。

形式化地，记忆 M_t 是实体记录的集合；程序 Π_t 是逐 fragment 操作与逐实体存在决定的集合；exec 是确定性、可回滚、保留历史版本的执行器。一句话：exec 只负责"按规则改档案并留底"，Π_t 才是要学的东西。

## 二、论文定位与核心候选贡献

首篇的核心候选贡献是下面三部分的组合，任一部分单独都不构成主张：

1. **hindsight 监督的可逆生命周期修订。** 用私有实例真值给封存后的关联/存在决定打标签，训练一个小代价函数；RETRACT 只关闭版本，REACTIVATE 可恢复同一身份。它解决"陈旧实体留在记忆里"与"误删后身份丢失"两个对立错误；输入同一公开特征，输出可逆的版本化修订。例如物体被搬到另一房间后重见，记忆保持原 ID 而不是新建。它不等于把标签换成动词，也不等于保存历史字节。
2. **候选先于教师的信息边界与三分解。** 召回集合、特征矩阵与分配输入在任何私有文件打开前算完并封存；teacher 只能给既有行列打标签。错误分成 recall miss（正确实体不在召回集合）、teacher error（标签本身错）、amortization error（学生与标签不一致）。它解决"赢了不知道赢在哪、输了不知道输在哪"的问题。它不等于函数签名里没有 private 参数。
3. **同前端下与关联、持续性、渲染比对三类机制的对照。** VSMT-lean、TAF、ELU-P、RAC、LOW 读取逐字节相同的冻结前端 cache，指标对齐 Dyn-THOR。它解决"优势是否只是前端差异"的问题。它不等于官方复现这些系统。

可以主张：在共享冻结 RGB-D 前端下，hindsight 监督的可逆生命周期修订是否减少陈旧实体、误删并保住身份，并给出三分解。不能主张：地点或拓扑修订、关系修订、SPLIT/MERGE 学习、度量 SLAM、传感噪声鲁棒性、真实机器人泛化。论文体量按 RA-L/ICRA 规划。

## 三、记忆表示

**实体记录（entity record）** 是记忆的唯一节点类型。它解决"一个物体在记忆里应当留下哪些可审计信息"的问题；输入是历次 BIND/BIRTH/REACTIVATE 附上的 fragment 证据，输出是可查询的当前状态和可回溯的版本链。例如一把椅子的记录里有 12 次观察的描述子均值、最新 AABB、上次看见的帧号、连续三次"应可见却没看见"的计数和两条已关闭的旧版本。它不是 place，不是 surface，不含语义类别。

| 字段 | 含义 | 由谁写 |
|---|---|---|
| `entity_id` | 匿名稳定 ID，BIRTH 时分配，MERGE 去重时保留 canonical | executor |
| `state` | `active` / `dormant` / `retracted` | executor |
| `versions[]` | 每个版本含 `version_id`、`predecessor`、`opened_at`、`closed_at`、`closing_transaction` | executor |
| `descriptor_mean`、`descriptor_count`、`best_view_descriptor` | DINO 描述子的运行均值、次数，以及像素最多一次观察的单视角描述子 | BIND/BIRTH/REACTIVATE |
| `centroid`、`aabb` | episode-relative 坐标下的质心与轴对齐包围盒，BIND 时按证据更新并记录位移 | BIND/BIRTH/REACTIVATE |
| `observation_count`、`last_seen_t` | 观察次数与上次观察帧号 | BIND/BIRTH/REACTIVATE |
| `missed_opportunity_count` | 连续"应可见却未匹配"次数；任一次匹配清零 | 共享 dormancy 规则 |
| `evidence[]` | `(frame_digest, fragment_id)` 列表 | BIND/BIRTH/REACTIVATE |
| `supported_by` | 几何派生的支撑面 ID 或 null；五方法共享同一确定性规则。它是 D-224 裁决 B 明确保留的几何派生属性，但**不进入关联特征**：按 ID 比较只有在表面 ID 跨帧稳定时才有信息，而跨帧稳定的表面 ID 等于维持一个持久表面身份，那正是首篇移除的能力。关联头改用纯几何的支撑面高度差 | 共享几何规则 |
| `provenance` | 创建/关闭该版本的事务 ID 与决策时刻 | executor |

**状态机。** `active` ⇄ `dormant` 由五方法共享的确定性 dormancy 规则决定：连续错失的应可见次数达到 `n_dormant`（null）转 dormant，任一次匹配转回 active。`active`/`dormant` → `retracted` 只由 RETRACT 触发；`dormant`/`retracted` → `active` 只由 REACTIVATE 触发。BIND 只能落到 `active` 实体。NoVersion 消融把 `retracted` 改为物理删除。白话：dormant 是"很久没看见但没有证据说它不在"，retracted 是"有证据说它不在原处"；两者都不删档案。

**共享去重（MERGE）。** 每 `m_dedup`（null）帧对活动实体做一次确定性去重：余弦 ≥ `θ_m` 且质心距离 ≤ `d_m` 且 AABB IoU ≥ `i_m`（三者 null）的一对合并为一条记录，关闭两个旧版本、保留 canonical ID 与全部证据。五方法逐字节相同地执行同一规则，参数只在 S1 开发集上选一次。它解决前端过分割产生的重复实体；它不是学习决定，也不进入任何方法的差异。

**实体 token（entity token，D-224-G）。** 它解决“这份记忆怎样被下游世界模型或规划器消费”的问题。输入是当前记忆，输出是每个非 retracted 实体一行的定序字段：`entity_id`、状态 one-hot、描述子、质心、尺寸、观察次数、年龄、版本数、错失次数、是否有支撑面。另有帧级稀疏残差：本帧哪些 `entity_id` 被哪个原子改动。例如对象中心世界模型可以只对改动过的 token 做状态转移预测，而不重算整张图。它不是首篇的实验对象，本篇只保证 schema 与字段顺序冻结、逐帧可导出；世界模型接入是后续工作。

**执行器不变量。** 每个原子有前条件；程序整体从同一不可变 M_{t−1} 克隆执行，任一原子失败整帧回滚；历史版本不物理删除；同一帧内一个 fragment 至多落到一个实体；版本号单调；provenance 必须齐全。执行器复用 [`graph_ops.py`](../src/vsmt/graph_ops.py) 与 [`contracts.py`](../src/vsmt/contracts.py) 的实体子集，不新写第二套。

## 四、五个原子与帧程序

| 原子 | 前条件 | 作用 | 谁决定 | 例子 | 不等于 |
|---|---|---|---|---|---|
| `NOOP` | 目标实体本帧应可见且未匹配 | 保持该实体状态，`missed_opportunity_count` 加一 | 存在头 σ(r) < τ_r | 杯子被橱柜门挡住，不撤回 | 忽略该实体 |
| `BIND` | 目标实体 `active` | 追加证据、更新描述子/几何、记录位移 | 分配 f→active e | 同一把椅子换个角度再看见 | 语义标签匹配 |
| `BIRTH` | fragment 未分配给任何实体 | 新建实体与首个版本 | 分配 f→自己的 BIRTH 列 | 第一次看见新放的杯子 | 每个 mask 都是新实体 |
| `RETRACT` | 目标实体应可见、未匹配，且 σ(r) ≥ τ_r | 关闭当前版本，状态改 `retracted`，证据保留 | 存在头 | 原位置连续被可靠深度射线穿过 | 物理删除 |
| `REACTIVATE` | 目标实体 `dormant` 或 `retracted` | 打开新版本、状态改 `active`、更新几何并保留旧 ID | 分配 f→dormant/retracted e | 搬到卧室的椅子被重新看见 | 新建一个像它的实体 |

`REPLACE` 仍是同一帧内对同一位置先 RETRACT 旧实体再 BIRTH 新实体的复合程序，只有两半各自合法才允许，不计作第六原子。**帧程序** Π_t 是本帧全部原子的集合，一次原子提交；本帧没有 fragment 也没有应可见实体时程序为空。白话：五个动词分别对应"先放着、认出来了、新东西、确实没了、又回来了"，每帧把所有该做的决定一起做，而不是一步只做一件。

## 五、共享冻结前端

前端由 D-215 冻结的资产与确定性几何组成，五个方法读取同一份 cache 的等字节 clone；本项目不训练其中任何部件。

| 部件 | 规格 | 输出 |
|---|---|---|
| Proposal | SAM 2.1 Hiera Small automatic mask，D-215 登记的 17 个参数原样；每帧 ≥196 像素、≤64 个 proposal，第 65 个即整帧 construction failure | 匿名 `fragment` mask |
| 描述子 | DINOv2 ViT-S/14（无 registers，384 维）mask 内 patch token 均值、L2 归一化；S1 同时提取 ViT-B/14（768 维）作为唯一可选升级，只按开发集分离度选一次并在 S3 前冻结；DINOv3 因许可证未核对不作默认 | 逐 fragment 向量 |
| 几何 | depth＋内参＋因果 episode-relative 位姿 → fragment 三维点、质心、AABB、像素数、深度有效率 | 逐 fragment 几何 |
| 自由空间 | 可靠深度射线穿过的体素集合，可靠性门 `ρ_free`（null） | 逐帧体积 |
| 可见体积 | 视锥内、深度表面之前的体素集合 | 逐帧体积 |
| 应可见判定 | 实体 AABB 体素落入可见体积的比例 ≥ `v_min`（null）即"本帧应可见"；自由空间覆盖比例＝AABB 体素被可靠射线穿过的比例 | 逐实体两个比例 |

**共享 ReID 适配头（shared ReID adapter head，D-224-E，可选前端）。** 它解决“冻结 DINO 的余弦在跨视角同物体与同场景异物体之间分不开”这一最可能压低整张表的瓶颈。输入是冻结描述子（384 或 768 维），输出是一个 128 维 L2 归一化投影；参数由 train 划分 house 的实例级对比损失训练一次后冻结，**五个臂逐字节共用同一投影**，因此它不是 VSMT-lean 的私有优势。例如同一把椅子的正面与侧面在投影后余弦升高，而同房间另一把椅子下降。它在 S1-04 与原始冻结描述子一同量分离度，由 S1-05 按已登记规则二选一并冻结；它不产生 fragment，不做身份判定，其对比标签虽与主 teacher 同源但只在 train house 上使用，也不计入任何方法的 12 个配置额度。若被选中，论文必须同时报告冻结描述子基线，不得只报强前端结果。

白话：前端只回答"眼前有哪些匿名色块、它们在哪、哪些空间确实是空的、哪些空间本帧看得清"，不回答"这是不是上次那把椅子"。它复用 [`d223_f01_production_reader.py`](../src/vsmt/d223_f01_production_reader.py) 与 [`shared_frontend_core.py`](../src/vsmt/shared_frontend_core.py)，去掉 place observation 字段。

## 六、帧级联合分配

**帧级联合分配（frame-level joint assignment）** 解决旧设计"分桶枚举候选、逐个真实执行、独立打分取最大"带来的候选遗漏、容量截断和一步一原子的问题。输入是当前帧 fragment 集合 F、按余弦召回的候选实体和每个 fragment 一个 BIRTH 虚拟列；输出是一个矩形分配加逐实体存在决定，编译为一个帧程序。例如三个 fragment、两个近邻实体时，分配器可同时判定 f1→e1 BIND、f2→BIRTH、f3→e2(retracted) REACTIVATE。它不是 SPLIT/MERGE 求解器，不允许一个 fragment 绑两个实体，也不读取任何私有身份。

步骤：

1. **召回（两条通道取并集）。** 对每个 fragment f：本地通道按描述子余弦取前 `k` 个质心距离 ≤ `R_local`（null）的实体；全局通道**对 active/dormant/retracted 一视同仁**、不设距离上限、按余弦取前 `k′`（null）个。两者去重合并，并列按 `entity_id`。召回集合、顺序及其 digest 在此封存。全局通道不分状态，是因为 `AssocOnly` 根本没有 dormant/retracted 状态：若只给这两种状态远距资格，它的旧实体会留在原地被距离门挡成 BIRTH，比较就同时混入了「有没有生命周期词表」和「有没有远距候选资格」，而 D-224-HIJ 要的是前者的纯反事实。候选资格因此与状态无关且五臂共享；状态只决定分配编译成哪个原子。
2. **代价矩阵。** 行为按 `fragment_id` 排序的 F；列为召回的实体并集加 |F| 个 BIRTH 虚拟列。`C[f,e] = −a(f,e)`，`C[f,birth_f] = −b(f)`。取 logit 的相反数而不是 `−log σ(·)`：softmax 训练学到的是 `p(列|行) ∝ exp(logit)`，最大化联合对数似然等价于最小化 `Σ(−logit)`，归一化常数是每行常量不影响联合最优；`−log σ` 是非线性单调变换，会改变跨行竞争下的最优配对，实测约十分之一的随机二乘二case给出不同答案。召回之外的组合用由当前矩阵最大/最小合法代价和行数算出的禁止代价，保证任何含禁止格的分配严格更贵；固定写一个大常数不安全，因为极端 logit 能产生同样大的合法代价。
3. **矩形分配。** 自写求解器取最小总代价，并把结果规范化为**字典序最小的那个最优解**；行序按 `fragment_id` 而非 SAM 返回顺序，因此交换本帧色块顺序不会换掉并列结果。
4. **编译。** f→active e 记 BIND；f→dormant/retracted e 记 REACTIVATE；f→birth 记 BIRTH。
5. **存在决定。** 对每个 `active` 且本帧应可见、且未被分配的实体 e：σ(r(e)) ≥ `τ_r`（null，属 VSMT-lean 的 ≤12 配置之一）记 RETRACT，否则记 NOOP 并累计错失次数。
6. **提交。** 执行器在 M_{t−1} 的克隆上原子执行全部原子，失败整帧回滚并记 `illegal_program`；随后共享 dormancy 规则与共享去重按登记周期运行。

白话：这一步把"谁是谁、谁是新的、谁没了"变成一次分配求解，学习部件只提供每格的代价；对手方法用手写阈值填同一张表，因此差别只在代价怎么来。

**封存为什么分两阶段。** 阶段 A 在任何模型运行前、任何私有文件打开前封存召回集合与关联/新建特征。阶段 B 在求解之后封存分配回执与存在特征，因为存在头有一项是「最相似色块是否仍未被分配」，求解之前没有定义。只封存阶段 A 会让三分之一的模型输入落在不变性保证之外，「三张特征表逐字节不变」这句话就不成立。两份摘要都写完，teacher 才可以打开 private；训练时喂给存在特征的分配必须来自当前策略或登记的规则臂，**绝不能用 teacher 的分配**，否则学生在训练时看到的是它自己在部署时拿不到的东西。

## 七、学习代价头

**学习代价头（learned cost heads）** 是 VSMT-lean 中唯一训练的部件。它解决"多条公开线索怎样合成一个关联或存在判断"的问题；输入是下表的逐对/逐项公开特征，输出三个标量 logit。例如被橱柜门挡住的杯子可见比例为零、自由空间覆盖也为零，存在头应给出低"已不在"概率；同一位置被可靠深度射线穿过时才升高。它不是端到端视觉网络，不产生 fragment，不看未来。

| 头 | 输入特征（全部由公开 cache 与 M_{t−1} 计算） | 输出 |
|---|---|---|
| 关联头 a(f,e) | 与 `descriptor_mean` 的余弦；与 `best_view_descriptor` 的余弦；质心距离；AABB 三维 IoU；尺寸对数比；`t − last_seen_t`；`missed_opportunity_count`；状态 one-hot；e 在 f 的召回中的余弦名次；次优余弦差；是否互为最佳；支撑面高度差 | 关联 logit |
| 存在头 r(e) | 应可见比例；自由空间覆盖比例；相机到质心距离与视角余弦；`missed_opportunity_count`；`observation_count`；`t − last_seen_t`；与当前任一 fragment 的最高余弦及该 fragment 是否仍未匹配；状态 one-hot | "已不在原处" logit |
| 新建头 b(f) | 对任一实体的最高余弦；1 m 内活动实体数；fragment 像素数；深度有效率 | 新建 logit |

架构：每个头为输入 LayerNorm 加两层 128 宽 GELU MLP，输出一维；三个头合计约 4 万参数。损失：逐 fragment 对 `[召回列…, BIRTH 列]` 的 softmax 交叉熵，加逐实体存在的二元交叉熵，两项等权。训练配方（proposed）：AdamW，lr 1e-3，weight decay 1e-4，batch 按帧组织，20 epoch，按 validation loss 早停，seed 7/19/31/43/59。因果记忆的分布偏移用两轮 DAgger 处理：第 0 轮用 ELU-P 产生的记忆序列训练，第 1 轮用第 0 轮模型自己产生的记忆再训练；两轮都登记，主表用第 1 轮。它不接受 slot、路径、样本名或 house ID 作为输入。

白话：模型是"冻结视觉特征＋几十 KB 的小打分器＋一次匈牙利分配"，不是 VLM，也不是图网络。这样选是因为训练决策点只有十万量级，对手全是零训练方法，任何大模型的收益都无法与前端区分开。

## 八、实例真值 teacher 与信息边界

**实例真值 teacher（instance-truth teacher）** 解决旧设计要等未来观测才能打分、且大半语义无法事前确定的问题。输入是封存后的召回集合与特征矩阵，以及 t 时刻私有实例真值；输出是逐 fragment 的目标列和逐实体的"已不在"标签。例如 fragment 的主导实例 ID 与实体 provenance 的多数实例 ID 相同即 BIND 正例；实体对应实例已被移走或位移超过 `δ_moved`（proposed 0.5 m）即"已不在"正例。它不生成候选，不改召回集合，不进入部署推理。

必须同时满足的门，任一失败即停止：

1. 部署可见输入只含决策时刻及之前的公开 RGB-D 派生量、因果位姿、动作摘要和 M_{t−1}；house ID、模拟器对象 ID、真值 mask、干预日志不进入模型值。
2. 召回集合、特征矩阵与 BIRTH 列在任何 private 文件打开前算完并写 digest；teacher 只读该 digest 指向的固定行列。
3. 修改任意 private 文件而保持 public 字节不变时，召回顺序、特征矩阵与未训练模型 logits 逐字节不变。
4. 评估进程在 private 不可见时完成全部预测；评价器随后按预测 digest 独立打开标签。
5. 正确实体不在召回集合记 `recall_miss`；标签错记 `teacher_error`；学生与标签不一致记 `amortization_error`。
6. 只用路径、seed、帧号、house 序号的 nuisance probe 不得预测任何标签。

## 九、对照

四个对照与 VSMT-lean 共用同一冻结前端、同一召回规则、同一共享去重与 dormancy 规则、同一执行器和同一评价器；差别只在代价矩阵与存在决定怎么来。所有规则臂无梯度，只在预登记的有限网格中选择，每方法至多 12 个完整配置，VSMT-lean 亦同。

| 臂 | 机制来源 | 代价与存在决定 | 不能据此声称 |
|---|---|---|---|
| `TAF` | ConceptGraphs 式阈值关联与融合 | 余弦 ≥ θ_a 且距离 ≤ d_a 则 BIND 代价 0 否则 +∞；BIRTH 代价常数；不撤回 | 官方 ConceptGraphs |
| `ELU-P` | Fusion++ 存在 log-odds 加 Perpetua 式持续性滤波 | 关联同 TAF；存在 log-odds 按可靠自由空间覆盖递减、按匹配递增，涌现/持续率只在 train 上拟合；过门即 RETRACT，再匹配即 REACTIVATE | 与上游完整系统等价 |
| `RAC` | DSG 式 render-and-compare | 关联同 TAF；把实体 AABB/点投影到当前深度图，观测深度大于记忆表面超过 `margin` 的像素比例 ≥ `ρ_rac` 记一次负证据，连续 `n_rac` 次 RETRACT | 官方 DSG 或 Gaussian 渲染 |
| `LOW` | 末次观测覆盖 | 最近质心距离 ≤ d_low 即覆盖属性，否则 BIRTH；不撤回、不恢复 | 有意削弱的对照 |
| `LLM-op`（必做附录臂） | Mem0 式零训练操作选择 | 把同一特征表转成文本，让冻结 LLM 逐行选 BIND/BIRTH/REACTIVATE/RETRACT/NOOP | 不得进主表；附录结果不能当作主比较 |

白话：TAF 回答"像就并、不像就新建"够不够；ELU-P 回答"按概率慢慢忘"够不够；RAC 回答"把记忆画出来和现在比"够不够；LOW 回答最简单的覆盖能到哪。它们各自的阈值只能在 S3 的 train/validation 上选，不抄论文在别的数据集上的数值。

**`LLM-op` 的身份已收口（D-224-HIJ）。** 它从“可选、条件不明”改为**必做的附录臂**：必须跑，但只在 validation 上跑，结果只进附录，永不进主表。它解决“零训练 LLM 是不是已经够了”这个审稿人必问的问题；输入是与五臂逐字节相同的特征表转成的文本，输出是逐行操作选择。例如同一帧里 LLM 可能对一个被遮挡实体直接选 RETRACT，而主表方法选 NOOP。放在附录而不是主表的理由是它的成本与 prompt 敏感性使得“每方法至多 12 个完整配置”的公平预算无法对它成立，把它放进主表等于在一个无法对齐预算的维度上比较。它不是被削弱的对照，也不表示本项目认为 LLM 路线无效；若以后要把它升为主表臂，需要先冻结它自己的配置预算口径，属新裁决。

## 十、消融

| 名称 | 精确定义 | 回答的问题 |
|---|---|---|
| `NoVersion` | RETRACT 改为物理删除，被删实体不再存在于记忆中因此也无从召回，再出现只能 BIRTH；召回规则、代价头与训练不变 | 可逆版本对被搬动物体身份连续率值多少 |
| `HandCost` | 把三个代价头替换为 ELU-P 的手写代价，分配求解器与执行器不变 | 学习代价相对手写代价的贡献 |
| `HeuristicLabel` | 用 TAF 在公开数据上的决定当标签训练同一网络 | 私有实例真值相对公开启发式标签的贡献 |
| `AssocOnly` | 同一个学习关联头与同一求解器，但事务词表只剩 `BIND` 与 `BIRTH`：不撤回、不恢复、无 dormancy，`retracted` 集合不存在 | 生命周期词表本身值多少，而不是学到的关联值多少 |

四组消融共享同一前端、数据、召回规则、训练预算与评价；被移出的消融在看过 test 之后不得补回。

**`AssocOnly` 是主张 1 的直接反面（D-224-HIJ，必做）。** 它解决“胜负到底来自学到的关联，还是来自可撤回可恢复的生命周期词表”这个此前没有任何一臂回答的问题。输入与 VSMT-lean 逐字节相同，输出只有 BIND 与 BIRTH 两种操作；`HandCost` 换的是代价来源、`NoVersion` 换的是可逆性，都不回答词表本身的价值。例如一个被搬走的杯子，VSMT-lean 可以 RETRACT 后在别处 REACTIVATE，而 `AssocOnly` 只能留着旧实体并在新位置 BIRTH，于是同时产生一个陈旧实体和一个重复实体。因为它是第二节贡献 1 的唯一因果反事实，**论文主表必须与主比较并列报告它**，不得只放在消融表里。它不是一个规则臂，也不等于 TAF：TAF 的关联是手写阈值，`AssocOnly` 的关联是同一个学习头。

**`VSMT-lean-ctx`（D-224-F，可选臂，不作默认）。** 它解决“每个候选对独立打分，看不见 f1 已经占了 e1、所以 f2 不该再要 e1 这类联合约束”的问题。输入是同一帧全部 fragment×候选实体对的特征，经 1～2 层 transformer 相互注意后再输出同样三个标量；求解器、执行器、teacher 与指标完全不变。例如两个外观相近的 fragment 同时匹配同一个旧实体时，上下文层可以把其中一个推向 BIRTH。它登记为可选臂而非主表：S5 的经验是 Set Transformer 相对 MLP 没有改变结论，而 300 house 的规模有过拟合风险。主表始终以 MLP 版为准；ctx 版与 MLP 版共享同一训练预算与配置额度，其结果单列报告，且不得在看过 test 后替换主表行。

## 十一、指标与统计

| 指标 | 定义 | 对齐 |
|---|---|---|
| 节点 precision / recall / F1 | 每帧按匈牙利与 3D IoU 0.3 把预测活动实体框匹配到真值当前活动物体框 | Dyn-THOR |
| Missing 残留率 MRR | 真值已不在原处的物体中仍以 `active` 留在记忆里的比例 | Dyn-THOR |
| 假撤回率 | 被 RETRACT 的实体中真值仍在原处的比例 | 自家 |
| 身份连续率 | 被搬动物体重见后记忆 ID 与搬动前相同的比例 | 自家 |
| 恢复延迟 | 干预对方法首次可见到记忆状态正确所经过的帧数 | 自家 |
| contamination AUC | 一次错误决定在后续帧持续的面积 | 沿用 |
| 规模与成本 | 活动实体数、历史版本数、每帧运行时间、峰值内存 | 沿用 |

统计以 house 为配对单位，bootstrap 10,000 次、seed 在 S3-01 登记；主门为 VSMT-lean 相对最强对照在 MRR 与身份连续率两项的单侧 95% 下界均大于 0，效应量在 S3-01 冻结。所有指标分项报告，不合成单一总分；test 只跑一次，跑后不得改指标、阈值、数据或对照。

## 十二、口径边界

| 可以主张 | 不能主张 |
|---|---|
| 共享冻结前端下，hindsight 监督的可逆生命周期修订是否减少陈旧实体、误删并保住身份 | 地点/拓扑修订、关系修订 |
| recall miss / teacher error / amortization error 三分解 | SPLIT/MERGE 学习 |
| 与关联、持续性、渲染比对三类机制在 Dyn-THOR 对齐指标上的比较 | 度量 SLAM、传感噪声鲁棒性、真实机器人泛化 |

## 十三、代码复用与归档地图

| 用途 | 复用来源 | 处理 |
|---|---|---|
| 执行器、版本链、不变量 | 新模块 `src/vsmt/lean_memory.py`；只复用纯函数 `cpmt.hashing.canonical_json/clone_json` 与 `graph_ops.cosine_similarity/centroid_distance/observation_aabb/opaque_id` | 见下方说明 |
| 冻结前端 reader | `src/vsmt/d223_f01_production_reader.py`、`src/vsmt/shared_frontend_core.py` | 去掉 place observation |
| 可见体积、错失机会、共同审计 | `src/vsmt/vm04_public_visibility.py`、SharedMemoryWrapper、CommonPostUpdateAudit | 沿用 |
| 不可观测窗口干预与路线 | `src/vsmt/vm04_program_construction.py`、`src/vsmt/vm04_observation_runner.py` 及 D-199～D-204 机制 | 改为随机干预生成器 |
| 规则对照 | `src/vsmt/baselines.py` | 补 ELU-P 与 RAC |
| 地点、统一图、八原子枚举、结构估计器 | `d210_*`、`d211_*`、`d212_*`、`d213_*`、`d214_*`～`d219_*`、`public_candidates.py` | 留在树中不删，标历史；不进入本分支任何入口 |

**为什么执行器另写一份核心而不是收窄 `GraphRevision`。** 读过实现后确认：`GraphRevision` 与 `cpmt.executor.validate_graph` 绑定了 place scaffold、五类关系边、`graph_hash` 与统一图 lifecycle，收窄它等于把这些一起带进来，与 D-224 削减流程的目的相反。因此实体记忆核心是一个自足的新模块，**只复用不会产生第二套数值语义的纯函数**：规范 JSON 与深拷贝、余弦、质心距离、AABB、不透明 ID。`GraphRevision`、place scaffold、关系边与旧 `public_candidates.py` 不被本分支任何入口导入。它不等于旧执行器被删除，旧模块与其测试原样保留。

**求解器已在 S0-03 登记为自写，不新增依赖。** scipy 不在本项目依赖里，而且并列必须由我们自己定：一个矩形分配通常有多个最优解，返回哪一个不能取决于字典顺序、浮点噪声或库版本。实现是带势的最短增广路方法，复杂度 `O(行^2 × 列)`，并列一律取较小列号；因为每个 fragment 都有自己的 BIRTH 列，列数永远不少于行数。测试用 40 个随机矩阵与暴力枚举的最优值逐一比对。它不比 scipy 更快，只保证同一矩阵永远给出同一组列号。
