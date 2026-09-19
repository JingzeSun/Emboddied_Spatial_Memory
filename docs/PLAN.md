# VSMT 从实现到论文结果的完整计划

本文件只维护 Versioned Structural Memory Transactions（VSMT，版本化结构记忆事务）从当前代码到论文结果的步骤链、依赖、状态、交付物和**失败分支**。第三至七章是理想路径，[第八章](#八失败时的暂停点与待触发裁决)为每个剩余步骤登记失败形态、暂停点与必须触发的裁决类型。本章**不自动切换研究主张**：任何会改变论文声称什么的替代路线，都必须先暂停、报告证据，再写成新决策交用户批准。决策依据写在 [DECISIONS.md](DECISIONS.md)，运行与证据写在 [EXECUTE.md](../EXECUTE.md)，方法定义写在 [METHOD.md](METHOD.md)，数据字段写在 [DATA.md](DATA.md)。历史路线和旧服务器命令不再堆在本文件；需要时从上述文件或 Git 历史查找。

## 一、最终目标与总链路

在同一冻结公开 RGB-D 前端、同一在线记忆输入、同一候选空间和同一评价协议下，比较 VSMT、TAF、ELU、WFR 和 LOW，回答类型化可执行事务、版本化状态/副作用审计以及 candidate-before-teacher 边界能否改进具身空间记忆修订。

```text
VM-00 来源与旧实现审计
  ↓
VM-01 公私输入和共同接口
  ↓
VM-02 论文机制适配器与朴素基线
  ↓
VM-03 VSMT 候选、executor 与 teacher 边界
  ↓
VM-04 新数据和共享前端
  ├─ VM-04.E  E-01 → E-02 → E-03 → E-05 → E-06 → E-08
  └─ VM-04.F  F-00 → F-01 → F-02 → F-03 → F-04 → F-05
  ↓
VM-05 开发比较、正式数据、训练与 validation
  ├─ VM-05.M  M-01 → M-02 → M-03
  └─ VM-05.P  P-01 → P-02 → P-03 → P-04
  ↓
VM-06 独立 test 与论文证据
  └─ P-05 → P-06
```

当前执行点：VM-04.E 全部完成，E-08 报告已导出并由 [LOG-206](../EXECUTE.md) 收口。D-221 最终得到2,121个成功house、55个失败house、67,872帧公开RGB-D与396维特征；E-06结构单头完成训练，但E-08显示它不适合作P08 bottleneck硬门（整体accuracy 0.7013，bottleneck recall区间0.043–0.150）。用户已批准D-223并完成F-00真实两房预检：两房均成功，分别存在2条和1条合格拓扑签名，因此拓扑继续门通过。F-01 production reader 本地实现已审；一次服务器真实预检在输入读取前停止：冻结DINO仓库/checkpoint存在且摘要正确，但冻结SAM2仓库/checkpoint和F-01精确schema的公开单episode bundle均不存在。现已按用户授权实现D-217 `public/train`首成功sample的observation 0→单帧origin-pose诊断bundle适配器，等待代码审查；没有读取真实D-217数据、下载SAM2、连接服务器、生成route/raw、加载模型或写cache，F-01执行位仍全关闭。下一步只在用户批准本实现后，另行裁决SAM2获取与一次服务器F-01真实预检；其余下游继续关闭。

## 二、状态和执行规则

| 状态 | 含义 |
|---|---|
| 已完成 | 代码和必要测试已经受审，或已有可复用的真实证据 |
| 已实现待授权 | 代码已提交并通过测试，但步骤合同中的真实执行授权位仍为 false |
| 未开始 | 依赖未满足，尚不能产生正式产物 |
| 封存 | 已确定但当前阶段禁止打开或使用 |

自 D-220 起，真实运行的授权由步骤合同里的布尔位表达并由用户在运行前审，不再要求“已审实现提交＋只改一个文件的激活提交＋父提交精确匹配”这套三重门；真实运行仍要求 clean checkout，并逐次记录 git commit、合同摘要、输入摘要、产物摘要、worker 数与退出码、资源用量和全部失败。

表格中的“动作”是必须完整执行的规范，不是可以挑着做的菜单。不能运行成功的 house、路线或槽位必须留下失败 receipt，不得省略、替换或补样。测试夹具只证明代码行为；真实步骤只有服务器产物、摘要和退出回执齐全才算完成。

## 三、VM-00～VM-03：方法和输入边界基础

### VM-00 来源与泄漏审计

| 状态 | 输入与动作 | 输出与继续条件 |
|---|---|---|
| 已完成 | 审计旧 generator、online、teacher 数据流，确认参考派生 query、未来观测和私有真值泄漏风险 | 明确禁止复用的旧输入；确定论文机制适配器只依据公开论文独立实现 |

### VM-01 公私数据与共同接口

| 状态 | 输入与动作 | 输出与继续条件 |
|---|---|---|
| 已完成 | 定义公开 ObservationPacket、先前预测记忆、公开/私有/provenance 文件边界和禁止字段 | 五种方法只能读取同一公开输入；pose/mask/entity truth、teacher、future 不进入部署输入 |

### VM-02 论文机制适配器与朴素基线

| 状态 | 输入与动作 | 输出与继续条件 |
|---|---|---|
| 已完成 | 在共同接口上实现 TAF、ELU、WFR 和 LOW，不复制上游源码和默认配置 | 四个对照与 VSMT 使用同一输入输出包装；正式阈值和预算留到 VM-05 冻结 |

### VM-03 VSMT 候选、executor 与 teacher 边界

| 状态 | 输入与动作 | 输出与继续条件 |
|---|---|---|
| 已完成 | 由当前公开观测和先前预测记忆生成并封存候选，再开放私有 teacher；候选逐一真实执行 | teacher 只能给既有候选打标签；正确候选缺失计 candidate miss；共同版本和副作用可审计 |

白话：VM-00～VM-03 解决“所有方法看什么、能改什么，以及 teacher 什么时候出现”。例如 teacher 认为 MERGE 正确，也不能临时插入一个原本没有的 MERGE 候选。它们不负责生成真实 RGB-D，也不证明 VSMT 更好。

## 四、VM-04：新数据和共享 RGB-D 前端

### VM-04 的三类数据

| 数据 | 用途 | 当前规模 | 不能支持的结论 |
|---|---|---:|---|
| Estimator RGB-D | 历史上训练、校准和一次性审计 structural estimator；D-223 后只作封存的开发证据 | 2048/128/128 house × 32 帧计划；实际见E-06/E-08回执 | 不能作为P01～P08路线raw、不能比较五种记忆方法、不能再作为production依赖 |
| 两房 P0 raw | 检查 P01/P04/P08 路线、三面文件、共享 cache 和五方法接线 | 两间固定开发 house、三条代表性路线 | 不能作为论文独立 validation 或 test |
| 正式论文 raw | 训练、选择和独立确认 VSMT 与对照 | VM-05.P 的 P-01 根据构造成品率和功效冻结 | 不能用当前两房数据代替 |

### VM-04.E：共享 Estimator 数据、训练和审计

#### E-01 冻结保留集合与 512/64/64 样本

| 项 | 内容 |
|---|---|
| 状态 | 已完成；服务器已封存 512/64/64、12 个 validation house 和私有 confirmation/audit 候选池 |
| 运行位置 | 服务器，只读完整 ProcTHOR-10K author-train source inventory |
| 输入 | 10,000-house inventory、冻结 house-level split 规则、两间 P0 house |
| 完整动作 | 对全部 house 计算 train/calibration/audit split；先保留 12 个 validation house 和私有 64-house confirmation 候选池；再在各 split 内按冻结 hash 顺序截取 512/64/64 |
| 公共输出 | development plan、12 个 validation ID、confirmation 数量与承诺摘要、512/64/64 计数 |
| 私有输出 | 全量 partition、保留清单、576 个 train/calibration source locator、64 个 audit ID seal、64 个 confirmation ID seal |
| 继续门 | 0 个观察被打开；公共文件没有 confirmation ID；所有摘要可重算 |

512/64/64 分别是 512 个训练 house、64 个校准 house 和 64 个最终 audit house，不是帧数。每个 house 后续固定取 32 帧。

本节保留 E-01 实际产出时的字段名。D-220 把 `confirmation` 这一角色改称 `test`：已封存的 64-house 候选池和承诺摘要照原样保留为历史产物，此后直接当作 test manifest 使用，不再执行隐藏 ID 与 reveal 仪式，但 test 只跑一次、且不得用于选参这两条不变。

#### E-02 服务器容量探测

| 项 | 内容 |
|---|---|
| 状态 | 已完成；1/2/4/8 worker 探测均结束，正式生成采用 8 worker |
| 运行位置 | 与正式生成相同的服务器、AI2-THOR 5.0.0、CloudRendering |
| 输入 | E-01 的正式 train 前缀 house，不使用额外测试 house |
| 完整动作 | 依次运行 1、2、4、8 worker；记录 CPU、可用 RAM、GPU 名称/总显存/空闲显存、磁盘和每组退出；成功 probe house 直接成为 E-03 正式数据 |
| 输出 | capacity receipt、每个 probe house 的成功或失败文件、实际 batch worker 数 |
| 继续门 | 至少一个 worker 安全完成；遇资源或进程失败就在该级停止；不删除失败、不换 house、不设墙钟强杀 |

E-02 不是随便跑一个 smoke。它决定 E-03 实际并发数，并把 probe 数据计入 512 个 train house，避免重复生成。

#### E-03 生成 train/calibration RGB-D

| 项 | 内容 |
|---|---|
| 状态 | 已完成；498/512 train house、61/64 calibration house 成功，17 个失败保留且未补样 |
| 运行位置 | 服务器，多 worker 数只能来自 E-02 receipt |
| 输入 | 512 个 train house、64 个 calibration house；每 house 固定 8 个相距至少 1 m 的 reachable 位置和 4 个 cardinal yaw |
| 完整动作 | 对全部 576 个 house 逐一生成或记录失败；断点重启先复验已有 NPZ、公私 receipt 和摘要，禁止仅凭文件存在就跳过 |
| 公共输出 | 计划上限 18,432 帧；实际 17,888 帧 RGB、米制 depth、相机内参和 opaque observation ID；不含 house ID、世界 pose、reachable grid、room metadata、instance/object/scenario/teacher/future |
| 私有输出 | house/source 绑定、选中世界位置、reachable 摘要、训练用 structural label 和逐 house receipt |
| 继续门 | 576 个固定 house 每个都有成功或失败终态；失败不补；64 个 audit house 仍未打开 |

E-03 会完整执行 576 个固定 house，不会为了省工程量只跑一部分。audit 的 64 个 house 此时故意不生成，这是防止开发期看到最终评估集，不是漏做；它们在 E-08 一次性打开。

#### E-04 人工语义标注（D-219 已取消）

| 项 | 内容 |
|---|---|
| 状态 | 已取消；不再是任何下游步骤的依赖 |
| 取消理由 | `room/corridor/unknown` 不定义地点身份，P08 资格只读 basin/bottleneck 概率与多视角 fragment，全库没有任何方法消费者读取 semantic 概率 |
| 历史产物 | 覆盖 17,888 帧的 A/B 双盲任务包（约 1.1 GiB）保留在服务器 `<E_STAGE_ROOT>/annotation`，不下载、不标注、不进训练 |
| 省下的成本 | 本阶段 35,776 次人工初始判断，加 E-08 原定的 4,096 次，全部不再需要 |
| 不允许 | 不得用恒定 `unknown` 冒充模型输出；不得在看到 E-08 或 test 结果后把 semantic 头补回来 |

论文相应收回“识别真实房间与走廊”的口径，只主张公开 RGB-D 推断的 basin→bottleneck→basin 及其中的匿名多视角 fragment。理由与证据见 [DECISIONS.md](DECISIONS.md) 的 D-219。

#### E-05 冻结公开特征算法并提取特征

| 项 | 内容 |
|---|---|
| 状态 | 已完成；经D-221扩展后2,121个成功house均生成32×396维feature shard，feature失败0 |
| 输入 | E-03及D-221固定RGB-D、冻结DINOv2资产和12维公开几何定义 |
| 完整动作 | 每帧提取 384 维 DINO 描述和 12 维 depth/free-space/visibility/opening/clearance/surface 几何；不得读 E-03 private 文件 |
| 输出 | 396 维 feature shard、逐帧输入摘要、模型和算法摘要 |
| 继续门 | 同一 RGB-D 重复提取字节一致；不接收 scenario ID、instance/object、teacher 或 future |

白话：E-05 把固定图像变成 Estimator 能训练的数字。例如走廊开口宽度只能由深度计算，不能查模拟器房间类型。特征本身不带标签，因此 D-219 删除 semantic 头不改变其中任何一个字节，不需要重跑。

#### E-06 训练并封存 structural Estimator

| 项 | 内容 |
|---|---|
| 状态 | 已完成；见 [LOG-205](../EXECUTE.md)。35 epoch early stop、temperature 0.84413、calibration accuracy 0.6958；D-223后仅作历史开发组件 |
| 输入 | E-05累计67,872×396特征中的train/calibration分片、house split、由可达图按冻结规则生成的basin/bottleneck/unknown标签 |
| 完整动作 | 只用 train 计算 normalization 和拟合一个 3×396 线性头；calibration 只选 checkpoint 与单个 temperature；保存逐 epoch 历史和失败 |
| 输出 | normalization、structural weights、bias、temperature、训练 receipt 和互绑摘要 |
| 继续门 | audit 未读取；真实权重和训练 receipt 经审；production reader 仍关闭 |

历史标签边界：E-06训练和E-08审计时，可达图只写train/calibration/audit标签，结构头推理只读公开RGB-D派生特征、不查grid真值。除loss、early stopping指标、checkpoint选择和temperature由两头改为单头外，AdamW、seed、epoch、batch、学习率、权重衰减、零初始化和类权重截断全部沿用D-215/D-216原值，不因结果调整。D-223后production不再运行该推理。

#### E-07 开发规模（D-221 已重新裁决为 2048/128/128）

| 项 | 内容 |
|---|---|
| 状态 | 已裁决；规则事前冻结、测量后机械触发 |
| 裁决 | **2048 train / 128 calibration / 128 audit**，仍不做 full-house 扩展 |
| 触发依据 | 现有 17,888 帧中 bottleneck 仅 856 帧（4.785%），且 559 个 house 中 394 个一帧都没有；规则的 `[300,1000)` 分支选中 2048/128/128 |
| 成本 | 增量 1,664 个 house、约 1.2 小时（实测 8 worker 下 2.6 秒/house）、约 +3.4 GiB |
| 为何不全量 | 全量约 20.6 GiB 而盘只剩 25 GiB，且 P-02 正式 raw 要用同一块盘；且读过直方图后再松动该约束属于"看完数据改标准" |

D-219 原先裁决的 512/64/64 由 D-221 取代，原因是删除 semantic 头使人工成本归零、实测速率又证明时间从来不是约束。**前缀延长不是 full-house 扩展**：选择规则是固定 hash 前缀，rank 0–511 的 house ID、rank 和 public ref 逐字节不变，现有 RGB-D 与特征全部复用，只追加 rank 512–2047；`full_house_expansion` 布尔在所有合同中继续为 false。运行时必须逐条复验这一不变性。

#### E-08 一次性 audit

| 项 | 内容 |
|---|---|
| 状态 | 已完成并封存；只跑了一次；报告已导出到[`results/vsmt_vm04_e08_structural_audit.json`](../results/vsmt_vm04_e08_structural_audit.json) |
| 输入 | 完全冻结的最终 structural Estimator、扩展后的 128-house audit seal |
| 完整动作 | 对128个固定audit house逐一生成或留失败；118个成功house形成3,776个RGB-D观察，10个失败不补。审计标签由同一冻结规则从可达图自动生成，**零人工判断**；模型输入仍只有公开RGB-D与内参；只运行预登记指标 |
| 输出 | structural NLL、accuracy、calibration、类别和 house 级区间、完整失败与资源 receipt |
| 继续门 | 结果只报告；不得因为 audit 失败而增加 house、改模型、改阈值或重新训练 |

E-08没有评价VSMT，也没有评价实体—地点关联。D-223后不再运行结构头路线门；冻结正式数据预算之前，先执行F-00，在两间开发house上只读检查原拓扑规则能否构造 basin→bottleneck→basin。若失败，按第八章暂停并触发场景设计裁决；不得自动换house或弱化规则。

### VM-04.F：生产共享前端与两房 P0 raw

#### F-00 P08拓扑可构造性预检（实现与本地测试已授权）

| 项 | 内容 |
|---|---|
| 状态 | 已完成并重新关闭；两房均成功且存在合格拓扑，公开报告见[`vsmt_vm04_f00_topology_precheck.json`](../results/vsmt_vm04_f00_topology_precheck.json)；执行门已按 D-220 撤除 activation-commit 三重门，结论与产物不受影响 |
| 输入 | 两间固定P0 house、生成器已获构造权限的`GetReachablePositions`、D-215原拓扑规则 |
| 完整动作 | 不启动production reader、不生成raw，只在两间房的可达图上计算逐位置basin/bottleneck/unknown并检查是否存在可规划的basin→bottleneck→basin路径 |
| 输出 | 两房逐类计数、候选路径存在性、固定规则/代码/输入摘要和逐house成功或失败 |
| 继续门 | 至少存在一条合格P08拓扑才继续F-01；否则暂停并触发场景设计裁决，不自动换house |

白话：F-00解决“在开发完整视觉reader之前，两间固定house里究竟有没有P08需要的拓扑”。输入只是数据生成器的可达图，输出是可否构造路线。例如某房有两个开阔区但中间没有满足原定义的瓶颈，就记失败。它不拍RGB-D、不向方法提供地图、不评价VSMT，也不保证后续fragment条件通过。

#### F-01 production reader

| 项 | 内容 |
|---|---|
| 状态 | reader本地实现已审；D-217单帧兼容适配器已实现待审；服务器前次预检因缺冻结SAM2资产和兼容公开bundle停止，真实执行位全关闭，cache为0；执行门已按 D-220 撤除 activation-commit 三重门；cache 摘要已在共享核心重构前钉住 |
| 输入 | 兼容性预检仅从D-217 `public/train`按rank取首个成功sample的observation 0并构造origin pose；reader再读冻结SAM/DINO/几何配置、公开RGB-D、内参、因果pose belief与动作摘要；**不加载E-06权重** |
| 完整动作 | 从公开RGB-D产生匿名fragment、DINO描述、surface/free-space/visibility和不含语义/结构类别概率的非网格place observation；只写一次共享cache |
| 输出 | 五种方法读取的完全相同 cache bytes 和逐帧 receipt |
| 继续门 | reader 签名没有 scenario/private/teacher/future；真实小样本逐字段审查通过 |

#### F-02 P01/P04/P08 路线构造与资格（D-220 已降为工程 smoke）

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F-00拓扑回执、F-01 reader、两间固定P0 house；可达图只由生成器读取，不进入cache |
| 完整动作 | 只构造P01、P04、P08三条代表性路线；P04使用冻结DINO top-1；P08组合F-00的basin→bottleneck→basin拓扑回执和两端稳定多视角fragment |
| 输出 | 三条 route bundle、共享 cache 证据和逐路线成功/失败 |
| 继续门 | 不换house、起点、路线或场景；不根据结果改拓扑常量或fragment的0.85/0.35；不合格照实保留 |

其余P02/P03/P05/P06/P07路线由单测或后续正式数据运行覆盖，不在两房阶段做逐路线封存仪式。这三条各自负责一件事：P01检查采集、三面raw与共享cache，P04检查冻结DINO place描述子通路，P08检查“生成器拓扑资格＋共享cache多视角fragment＋后续实体—地点链”的完整接线；结构头不再参与。

#### F-03 路线封存与单槽 smoke

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F-02 bundle、三面 raw writer |
| 完整动作 | 先封存三条路线，再只运行 P01 单槽 |
| 输出 | public RGB-D/内参、provenance 动作 journal、private pose/mask/entity state 和摘要 |
| 继续门 | 单槽文件完整、动作失败前缀保留、公私绑定可复验 |

#### F-04 两房三路线 raw

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F-03 成功、服务器容量探测和运行授权 |
| 完整动作 | 对 P01/P04/P08 完整生成；每槽接 F-01 相同 reader；失败不补 |
| 输出 | 每槽成功或失败终态、共享 cache、三面文件和批次 receipt |
| 继续门 | 所有固定槽都有终态；private evaluator 仍独立开闸；两房结果不得进入任何论文表，也不得据以选择 headline 赢家 |

#### F-05 旧网格产物退役

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | 新 cache、P04/P08 重验、12 路线重绑和只读 readiness receipt |
| 完整动作 | 显示并核对精确旧路径后删除，不使用通配符，不删除 Git 历史或复现依赖 |
| 输出 | 旧网格不再进入当前生产输入；删除清单和可恢复性说明 |

## 五、VM-05：开发比较、正式数据、训练和 validation

### VM-05.M：两房端到端开发比较

#### M-01 raw 到统一图

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F-04 raw/cache、统一类型门 |
| 完整动作 | 构造 place/entity/surface/fragment 节点、五类边、候选前类型门和 D-220 保留的三种消融 view（Typed/Flat8/NoVersion）|
| 输出 | 五方法共同 AdapterInput、初始图、逐时 packet 和复杂度基线 |
| 继续门 | 非网格 place 的 BIND/BIRTH/MERGE 全部生产接通；旧 coordinate scaffold 不进入主表 |

#### M-02 private teacher 与 evaluator

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | M-01 已封存公开候选；随后才打开 private pose/mask/entity/route truth |
| 完整动作 | 只给既有候选打标签并执行统一评价 |
| 输出 | candidate miss、teacher error、amortization error、地点/关系/挂载指标 |
| 继续门 | 修改private truth不能改变候选bytes；P08私有地点/实体参考只在路线与候选封存后评价 |

#### M-03 五方法开发比较

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | VSMT、TAF、ELU、WFR、LOW 的同 cache、同公开输入和冻结开发预算 |
| 完整动作 | 运行两房 P01/P04/P08 端到端训练/推理和逐例失败分析 |
| 输出 | 第一张五方法工程表、图膨胀、runtime、memory 和接口问题清单 |
| 继续门 | 只用于发现工程与候选问题；不得据两间 house 选择论文 headline 赢家 |

### VM-05.P：正式数据、训练和 validation

#### P-01 冻结正式数据和统计预算

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F/M 阶段构造成品率、九程序覆盖、所需最小效果和 house-level 方差 |
| 完整动作 | 事前冻结正式 train/validation/test 的 house-family 数、episode 数、seed、主指标、bootstrap 和停止规则 |
| 输出 | 三者互斥 manifest、总帧预算和功效说明 |
| 继续门 | 三个 split 按 house 互斥；主指标与停止规则在跑 test 之前冻结；不能照搬旧数据规模 |

D-220 起 test manifest 对作者可见，不再做隐藏 ID、承诺摘要和 reveal 接口；保留的实质是 test 只跑一次、且不得用于选择配置、阈值或 checkpoint。

#### P-02 生成正式 raw 和共享 cache

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-01 manifest、F-04/M-02 验收链 |
| 完整动作 | 按服务器实测最大安全 worker 生成正式 train 和 validation；test 数据生成后不读取 |
| 输出 | 多 house 正式 raw、共享 cache、公私文件、失败和资源 receipt |
| 继续门 | 固定样本全部有终态；任何失败不替换 |

#### P-03 五方法训练和有限选参

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-02 train、共同前端/候选/teacher、各方法冻结预算 |
| 完整动作 | 训练学习方法（VSMT 与 NECS 两条学习路径）；规则方法只在预登记有限配置中选择；VSMT 消融使用同预算 |
| 输出 | checkpoint、配置、训练曲线、资源和完整失败 |
| 继续门 | 不读取 test；不按单一场景临时增配 |

#### P-04 validation 后冻结

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-03 全部候选和只读 validation |
| 完整动作 | 选择最终 method config、threshold 和 checkpoint |
| 输出 | 最终冻结 receipt 和 test 可执行代码摘要 |
| 继续门 | 此后不得改算法、数据、阈值、指标或预算 |

## 六、VM-06：独立 test 与论文证据

### P-05 test 一次性运行

| 项 | 内容 |
|---|---|
| 状态 | 封存，未打开 |
| 输入 | P-04 冻结字节和 P-01 的 test manifest |
| 完整动作 | 一次性读取 test，运行五方法、配对统计和 house-level bootstrap |
| 输出 | 主指标、五个 headline 场景 macro、candidate/teacher/amortization、复杂度和逐例失败 |
| 继续门 | 只跑一次；失败照实报告，不换样本、不改方法、不改指标；被 D-220 移出必做集的臂不得在此之后补回来 |

### P-06 论文表和主张审计

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-05 不可变结果、全部失败、版本和资源证据 |
| 完整动作 | 生成主表、消融表、场景表、失败分析、成本与限制，并逐条检查证据是否支持主张 |
| 输出 | 第一篇论文结果包和可复现实验索引 |
| 继续门 | 主门失败就报告 no-go，不通过换数据或缩减强对照制造成功 |

## 七、时间与最近动作

VM-04.E 已全部完成。下表只估计**剩余**步骤；最大的不确定项是非网格 place 接线与 P08 拓扑可构造性，不再是数据规模或人工标注。

| 里程碑 | 状态 / 估计 | 主要不确定项 |
|---|---|---|
| E-01～E-03、E-05 | 已完成 | 2,121/2,176 house 成功，55 失败按合同保留 |
| E-06 structural 单头训练 | 已完成 | CPU 105 秒；calibration accuracy 0.6958 |
| E-08 一次性审计 | 已完成并封存 | accuracy 0.7013；bottleneck recall 区间 0.043–0.150 |
| D-223 文档与合同修订 | 已批准 | F-00真实预检完成且执行门重新关闭 |
| 两间 P0 house 拓扑可构造性预检 | 已完成 | 两房成功，合格签名数分别为2和1；未生成raw、未向方法暴露可达图 |
| F-01 production reader | reader已审；D-217兼容适配器本地实现候选完成；真实单episode读取待授权 | SAM2资产、真实适配字节、proposal数与cache字段须在真实小样本复核 |
| F-02 P01/P04/P08 smoke | 约 3～7 天，未授权 | 跨视角DINO区分度、P08 fragment资格 |
| M-03 第一份五方法开发表 | 约 1～2 周 | 非网格 place 接线、teacher/evaluator 和调试 |
| P-05 第一份论文级 test | 约 5～8 周 | P-01 正式规模、构造成品率、五方法训练和统计功效 |

5～8 周是剩余路径的估计，不承诺。若 F-01 或 F-02 触发[第八章](#八失败时的暂停点与待触发裁决)登记的裁决点，时间另算——那些是需要用户决策的岔路，不是可以顺手绕过的工程延迟。

最近动作按顺序为：

1. 用户代码审查D-217 public兼容适配实现；当前不得读取真实D-217目录或生成真实bundle。
2. 审查通过后，用户另行裁决是否允许获取合同已冻结但服务器缺失的SAM2官方仓库/checkpoint，并是否激活一次F-01服务器真实预检；不改变commit、YAML、checkpoint摘要或生成器参数。
3. 获批后形成一次性F-01 activation，先生成单帧诊断bundle再运行reader；真实小样本逐字段验收后停止并报告，另行决定是否进入F-02。F-01成功不自动启动F-02，诊断bundle不进入正式数据、P04/P08或论文结果。

## 八、失败时的暂停点与待触发裁决

前七章描述的是理想路径。本章登记每个剩余步骤**失败长什么样、失败时暂停在哪、需要触发哪一类新裁决**。

**本章不自动切换研究主张。** 上一版把"退到 L1 oracle 层""放弃 place 修订""把实体观测嫁接到别的场景"写成了自动备选，那是错的：这些都会实质改变论文声称什么，必须由用户裁决，而不是由某个 agent 在遇到失败时顺手选一条。本章只登记**失败形态**与**必须触发的裁决类型**，具体走哪条永远是新决策。

**两条规则。** 第一，失败时**先暂停并如实报告证据**，不得在同一轮里自行选定替代路线。第二，任何替代路线在执行前必须写成新决策并经用户批准；看到不利结果后才发明、且未经裁决就执行的退路，是移动球门。

E-08 是本章的来源：当时没有预先登记暂停点，结果一次审计失败花了整轮讨论才收敛。那次的正确做法（也是此后的模板）是——报告审计结果、诊断根因、把替代方案写成 post-audit 提案交用户审，而不是就地改规则。

### F 阶段

| 步骤 | 失败长什么样 | 暂停点与必须触发的裁决 |
|---|---|---|
| F-01 production reader | SAM 每帧 proposal 过多或过少；冻结 DINO 描述子跨视角区分度不足（同一物体两视角 cosine 低于同场景不同物体） | 暂停并报告逐帧 proposal 数分布与跨视角 cosine 分布。触发**证据层级裁决**：是否把首篇从 L2 降到 L1 oracle 层。这会把论文主张从"可部署 RGB-D 条件下的比较"改为"感知正确前提下的机制诊断"，**属于改变论文声称什么，必须用户批准** |
| F-00 P08 拓扑预检 | D-223 判据下两间 P0 house 找不到 basin→bottleneck→basin 路径 | 暂停并报告两间房的逐位置拓扑分布。触发**场景设计裁决**：重新设计实体—地点场景，或接受 P08 缺失。**不得自动换 house，也不得未经裁决就把实体观测嫁接到 P01/P03/P05**——那需要各自的数据合同与成功条件，目前都不存在 |
| F-02 P04 资格 | 冻结 DINO top-1 选出的 pair 视觉混淆强度不足 | 保留原 pair 并如实记录绝对 cosine 分数。触发**headline 组成裁决**：P04 是否降为 supporting |
| F-04 两房 raw | 路线执行中动作被拒、raw 写入不完整 | 保留失败前缀继续。两房本就只是工程 smoke，结果不进任何论文表，**无需裁决** |

### M 阶段

| 步骤 | 失败长什么样 | 暂停点与必须触发的裁决 |
|---|---|---|
| M-01 统一图接线 | 非网格 place 的 BIND/BIRTH/MERGE 候选无法从 D-214 缓存构造 | 这是当前已知的最大未接通项。暂停并报告缺口的具体几何原因。触发**核心主张裁决**：place 修订是否退出首篇。这会把创新点 1 从"统一图涵盖地点"收缩为"涵盖实体与表面"，**是首篇主张的实质改变，必须用户批准** |
| M-03 五方法开发比较 | VSMT 在两间 house 上不优于甚至劣于基线 | **不构成任何结论**，两间 house 本就不足以选 headline 赢家；照常进入正式数据，**无需裁决** |

### P 阶段

| 步骤 | 失败长什么样 | 暂停点与必须触发的裁决 |
|---|---|---|
| P-02 正式 raw | 构造成品率远低于 P-01 预算假设 | 按 P-01 已冻结的停止规则收口，用实际样本量运行，功效不足写入限制章节。**不得事后加样本，不得因样本少而改主指标** |
| P-03 selector 训练 | 不收敛，或预算内明显未充分训练 | 按已登记的 `training_sufficiency_unverified` 判据标注，照常进入 validation，同时报告 NECS 结果。不得把训练不足写成"方法失败" |
| P-05 test 主比较 | VSMT 在主指标上不优于 TAF/ELU/WFR/LOW | **如实报告 no-go**，不换数据、不缩减强对照。论文能保留哪些贡献**不能事前保证**，须在看到完整结果与误差分解后逐条审查证据是否支持主张，这正是 P-06 的职责 |
