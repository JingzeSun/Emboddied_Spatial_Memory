# VSMT 从实现到论文结果的完整计划

本文件只维护 Versioned Structural Memory Transactions（VSMT，版本化结构记忆事务）从当前代码到论文结果的步骤链、依赖、状态和交付物。决策依据写在 [DECISIONS.md](DECISIONS.md)，运行与证据写在 [EXECUTE.md](../EXECUTE.md)，方法定义写在 [METHOD.md](METHOD.md)，数据字段写在 [DATA.md](DATA.md)。历史路线和旧服务器命令不再堆在本文件；需要时从上述文件或 Git 历史查找。

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
  ├─ VM-04.E  E-01 → E-02 → E-03 ─┬→ E-04 ─┐
  │                                └→ E-05 ─┴→ E-06 → E-07 → E-08
  └─ VM-04.F  F-01 → F-02 → F-03 → F-04 → F-05
  ↓
VM-05 开发比较、正式数据、训练与 validation
  ├─ VM-05.M  M-01 → M-02 → M-03
  └─ VM-05.P  P-01 → P-02 → P-03 → P-04
  ↓
VM-06 独立 confirmation 与论文证据
  └─ P-05 → P-06
```

当前执行点：VM-04.E 的 E-01～E-03 已在服务器完成。激活提交为 `0c4f9851006dbb996864c9af82d60ff4b28c09b2`；E-02 实测选择 8 worker；E-03 的 576 个固定 house 全部取得终态，559 个成功、17 个失败且未替换，共生成并逐文件复验 17,888 帧公开 RGB-D。64-house audit 仍封存，E-04 以后均未获执行授权。

## 二、状态和执行规则

| 状态 | 含义 |
|---|---|
| 已完成 | 代码和必要测试已经受审，或已有可复用的真实证据 |
| 已实现待激活 | 代码已提交并通过测试，但真实服务器执行位仍关闭 |
| 未开始 | 依赖未满足，尚不能产生正式产物 |
| 封存 | 已确定但当前阶段禁止打开或使用 |

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
| Estimator RGB-D | 训练、校准和一次性审计共享前端的 semantic/structural estimator | 开发口径 512/64/64 house × 32 帧，共 20,480 帧 | 不能作为 P01～P08 路线 raw，也不能比较五种记忆方法 |
| 两房 P0 raw | 检查 P01～P08 路线、三面文件、共享 cache 和五方法接线 | 两间固定开发 house、12 个槽 | 不能作为论文独立 validation 或 confirmation |
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

#### E-04 制作语义标注包并完成人工双盲标注

| 项 | 内容 |
|---|---|
| 状态 | 未开始；标注工具和正式目录尚未实现 |
| 运行位置 | 标注包由服务器从 E-03 public RGB-D 导出；人工在本地离线浏览器界面完成 |
| 输入 | E-03 成功的 train/calibration 公共帧；标注者不得看到 house、scenario、route、世界 pose 或私有结构标签 |
| 完整动作 | 两名不同标注者分别对每帧选择 `room`、`corridor` 或 `unknown`；两人不看彼此结果；分歧进入独立仲裁；每次判断绑定 annotator、observation、label 和任务包摘要 |
| 输出 | 盲化任务包、annotator-A JSONL、annotator-B JSONL、分歧表、仲裁 JSONL 和逐观察 semantic receipt |
| 数量 | 若 E-03 的 18,432 帧全部成功，需要 36,864 次独立初始判断；失败 house 不产生伪造帧，也不补 house |
| 继续门 | 所有成功帧都有两个独立判断和最终标签；未解决分歧只能标为 `unknown`；不能覆盖旧判断 |

E-04 确实需要人工。当前还没有可以开始点击的正式页面，所以现在不要手改 JSON。E-03 完成后先实现并审查离线标注器；计划入口为 `ops/vsmt/vm04_estimator_annotation_stage.py`，计划产物位于 `<E_STAGE_ROOT>/annotation/`，浏览器只显示盲化图片和 opaque observation ID。你可以担任一名标注者，但第二名必须是另一位独立人员；同一个人标两遍不算双盲。

#### E-05 冻结公开特征算法并提取特征

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | E-03 固定 RGB-D、冻结 DINOv2 资产和 12 维公开几何定义 |
| 完整动作 | 每帧提取 384 维 DINO 描述和 12 维 depth/free-space/visibility/opening/clearance/surface 几何；不得读 E-03 private 文件 |
| 输出 | 396 维 feature shard、逐帧输入摘要、模型和算法摘要 |
| 继续门 | 同一 RGB-D 重复提取字节一致；不接收 scenario ID、instance/object、teacher 或 future |

白话：E-05 把固定图像变成 Estimator 能训练的数字。例如走廊开口宽度只能由深度计算，不能查模拟器房间类型。它不直接决定这是房间还是走廊。

#### E-06 训练并封存 Estimator

| 项 | 内容 |
|---|---|
| 状态 | 训练/封存核心已实现；等待 E-04、E-05 真实输入 |
| 输入 | E-04 semantic receipt、E-05 396 维特征、E-01 split |
| 完整动作 | 只用 train 计算 normalization 和拟合两个 3×396 线性头；calibration 只选 checkpoint 与 temperature；保存逐 epoch 历史和失败 |
| 输出 | normalization、semantic/structural weights、bias、temperature、训练 receipt 和互绑摘要 |
| 继续门 | audit 未读取；真实权重和训练 receipt 经审；production reader 仍关闭 |

#### E-07 一次性选择开发规模或全量扩展

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | E-03～E-06 的 train/calibration 成品率、标注成本、校准诊断和工程失败；禁止读取 audit |
| 选择 A | 冻结 512 版，最快进入 E-08 和两房 raw，统计覆盖较小 |
| 选择 B | 在打开 audit 前扩展全部允许 house；所有 RGB-D、标注、特征、normalization、weights、temperature 从零重做，512 cache 失效 |
| 继续门 | 只能选择一次，并在 audit、production reader、P04/P08 资格和任何正式 raw 之前登记 |

#### E-08 一次性 audit

| 项 | 内容 |
|---|---|
| 状态 | 封存，未打开 |
| 输入 | E-07 后完全冻结的最终 Estimator、E-01 私有 64-house audit seal |
| 完整动作 | 首次生成 2,048 个 audit RGB-D 观察；使用与 E-04 相同的双人盲标和仲裁规则产生 4,096 次初始判断；只运行预登记指标 |
| 输出 | NLL、accuracy、calibration、类别和 house 级区间、完整失败与资源 receipt |
| 继续门 | 结果只报告；不得因为 audit 失败而增加 house、改模型、改阈值或重新训练 |

audit 不是 E-04。E-04 是 train/calibration 的人工标签，可用于训练和发现问题；E-08 是模型冻结后的独立最终前端评估，只能看一次，不能用于修模型。

### VM-04.F：生产共享前端与两房 P0 raw

#### F-01 production reader

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | E-06 真实权重、E-08 audit 报告、冻结 SAM/DINO/几何配置 |
| 完整动作 | 从公开 RGB-D 产生匿名 fragment、DINO 描述、surface/free-space/visibility、semantic/structural 概率和非网格 place observation；只写一次共享 cache |
| 输出 | 五种方法读取的完全相同 cache bytes 和逐帧 receipt |
| 继续门 | reader 签名没有 scenario/private/teacher/future；真实小样本逐字段审查通过 |

#### F-02 P01～P08 路线调查与资格

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F-01 reader、两间固定 P0 house、公开 reachable grid |
| 完整动作 | 构造并固定 12 条路线；P04 使用冻结 DINO top-1；P08 要求 basin→bottleneck→basin 和两端稳定多视角 fragment |
| 输出 | 12-route bundle、共享 cache 证据和逐路线成功/失败 |
| 继续门 | 不换 house、起点、路线或场景；不根据结果调 0.70/0.85/0.35；不合格照实保留 |

#### F-03 路线封存与 slot-0 smoke

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F-02 bundle、三面 raw writer |
| 完整动作 | 先封存全部 12 路线，再只运行 slot-0/P01 |
| 输出 | public RGB-D/内参、provenance 动作 journal、private pose/mask/entity state 和摘要 |
| 继续门 | 单槽文件完整、动作失败前缀保留、公私绑定可复验 |

#### F-04 两房 12 槽 raw

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F-03 成功、服务器容量探测和运行授权 |
| 完整动作 | 对固定 12 槽完整生成；每槽接 F-01 相同 reader；失败不补 |
| 输出 | 12 个成功或失败终态、共享 cache、三面文件和批次 receipt |
| 继续门 | 所有固定槽都有终态；private evaluator 仍独立开闸 |

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
| 完整动作 | 构造 place/entity/surface/fragment 节点、五类边、候选前类型门和五种消融 view |
| 输出 | 五方法共同 AdapterInput、初始图、逐时 packet 和复杂度基线 |
| 继续门 | 非网格 place 的 BIND/BIRTH/MERGE 全部生产接通；旧 coordinate scaffold 不进入主表 |

#### M-02 private teacher 与 evaluator

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | M-01 已封存公开候选；随后才打开 private pose/mask/entity/route truth |
| 完整动作 | 只给既有候选打标签并执行统一评价 |
| 输出 | candidate miss、teacher error、amortization error、地点/关系/挂载指标 |
| 继续门 | 修改 private truth 不能改变候选 bytes；P08 私有房间/实体只在路线封存后评价 |

#### M-03 五方法开发比较

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | VSMT、TAF、ELU、WFR、LOW 的同 cache、同公开输入和冻结开发预算 |
| 完整动作 | 运行两房 12 槽端到端训练/推理和逐例失败分析 |
| 输出 | 第一张五方法工程表、图膨胀、runtime、memory 和接口问题清单 |
| 继续门 | 只用于发现工程与候选问题；不得据两间 house 选择论文 headline 赢家 |

### VM-05.P：正式数据、训练和 validation

#### P-01 冻结正式数据和统计预算

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | F/M 阶段构造成品率、九程序覆盖、所需最小效果和 house-level 方差 |
| 完整动作 | 事前冻结正式 train/validation/confirmation house-family 数、episode 数、seed、主指标、bootstrap 和停止规则 |
| 输出 | 三者互斥 manifest、总帧预算和功效说明 |
| 继续门 | confirmation ID 仍不可见；不能照搬旧数据规模 |

#### P-02 生成正式 raw 和共享 cache

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-01 manifest、F-04/M-02 验收链 |
| 完整动作 | 按服务器实测最大安全 worker 生成正式 train 和 validation；confirmation 只保存承诺，不打开 |
| 输出 | 多 house 正式 raw、共享 cache、公私文件、失败和资源 receipt |
| 继续门 | 固定样本全部有终态；任何失败不替换 |

#### P-03 五方法训练和有限选参

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-02 train、共同前端/候选/teacher、各方法冻结预算 |
| 完整动作 | 训练学习方法；规则方法只在预登记有限配置中选择；VSMT 消融使用同预算 |
| 输出 | checkpoint、配置、训练曲线、资源和完整失败 |
| 继续门 | 不读取 confirmation；不按单一场景临时增配 |

#### P-04 validation 后冻结

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-03 全部候选和只读 validation |
| 完整动作 | 选择最终 method config、threshold 和 checkpoint |
| 输出 | 最终冻结 receipt 和 confirmation 可执行代码摘要 |
| 继续门 | 此后不得改算法、数据、阈值、指标或预算 |

## 六、VM-06：独立 confirmation 与论文证据

### P-05 confirmation 一次性运行

| 项 | 内容 |
|---|---|
| 状态 | 封存，未打开 |
| 输入 | P-04 冻结字节和 P-01 私有 confirmation manifest |
| 完整动作 | 一次性生成/读取 confirmation，运行五方法、配对统计和 house-level bootstrap |
| 输出 | 主指标、五个 headline 场景 macro、candidate/teacher/amortization、复杂度和逐例失败 |
| 继续门 | 失败照实报告，不换样本、不改方法、不改指标 |

### P-06 论文表和主张审计

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | P-05 不可变结果、全部失败、版本和资源证据 |
| 完整动作 | 生成主表、消融表、场景表、失败分析、成本与限制，并逐条检查证据是否支持主张 |
| 输出 | 第一篇论文结果包和可复现实验索引 |
| 继续门 | 主门失败就报告 no-go，不通过换数据或缩减强对照制造成功 |

## 七、时间与最近动作

| 里程碑 | 从当前起的现实估计 | 主要不确定项 |
|---|---:|---|
| E-03 train/calibration RGB-D 完成 | 已完成 | 559/576 house 成功，17 个失败按合同保留 |
| E-08 最终 Estimator audit 完成 | 约 7～14 个工作日 | 36,864 次 E-04 人工判断、E-05 特征实现 |
| F-04 两房 P0 raw 完成 | 约 10～18 个工作日 | 标注进度、production reader、P04/P08 资格 |
| M-03 第一份五方法开发表 | 约 4～7 周 | 非网格 place 接线、teacher/evaluator 和调试 |
| P-05 第一份论文级 confirmation | 约 12～20 周 | P-01 正式规模、构造成品率、五方法训练和统计功效 |

最近动作按顺序为：

1. 审查并实现 E-04 离线盲化标注器；它只读取 E-03 public RGB-D，不允许标注者看到 house、scenario、route、世界 pose 或私有结构标签。
2. 同一实现批次完成 E-05 冻结 DINOv2＋12 维公开几何特征提取器；不得读取 E-03 private 文件。
3. 工程审查通过后导出两份独立人工标注任务包，并以多 worker 提取 17,888 帧特征。
4. 两名独立标注者完成 E-04，分歧经仲裁；E-05 字节复验通过后才能进入 E-06 真实 Estimator 训练。
5. audit、production reader、P04/P08 资格和正式 raw 在 E-07 最终规模选择前继续关闭。
