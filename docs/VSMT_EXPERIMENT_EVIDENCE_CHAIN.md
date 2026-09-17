# VSMT 实验构造与论文证据链

> 本文件是面向代码审查和论文写作的**解释性总图**，回答“实验怎样造、每个部件证明什么、证据怎样组合”。它不替代规范文件：阶段与授权以 [PLAN.md](PLAN.md) 为准，方法定义以 [METHOD.md](METHOD.md) 为准，字段与读取权限以 [DATA.md](DATA.md) 为准，历史裁决以 [DECISIONS.md](DECISIONS.md) 为准，实际运行证据以 [EXECUTE.md](../EXECUTE.md) 为准。若本文与机器合同冲突，以已审机器合同和后续裁决为准。

## 1. 一页结论

第一篇论文要检验的不是“能否把 RGB-D 写成图”，而是：当机器人在多视角历史中遇到实体重现、消失、关系变化和前端过分割/欠分割时，能否用 **Versioned Structural Memory Transactions（VSMT，版本化结构记忆事务）**，比共享同一公开输入的机制适配器和朴素基线更可靠地修改长期结构记忆。

VSMT 的核心候选贡献是三个部分的组合：

1. **类型化可执行事务**：不是直接输出一张新图，而是从 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE 八个原子模板中构造程序；REPLACE 是 RETRACT+BIRTH 复合程序。每个候选必须从同一旧版本真实执行，非法候选不能偷偷提交。
2. **版本化状态与副作用审计**：旧节点、旧边和证据不物理删除；每次更新保存前后版本、声明变化、非目标副作用、失败和来源。
3. **candidate-before-teacher（候选先于教师）边界**：候选目录必须在 future、reference transaction、private identity 和 teacher 可见前封存。teacher 只能给既有候选评分，不能补候选、改顺序或替换失败样本。

论文效果主张只有在下面整条链同时成立时才有资格检验：

```text
公开来源与固定划分
  → 有历史压力的多视角路线
  → 公私分离的真实 RGB-D raw
  → 五方法共享的 L2 公开前端
  → terminal 前形成的 causal memory 与 program request
  → 不可观测窗口中的真实干预
  → 公开构造充分门与失败保留
  → teacher 前封存并真实执行的候选目录
  → 独立 private 语义评价
  → CFO/history 可辨识性门
  → 同输入、同预算的五方法比较
  → validation 后锁定，再做 confirmation
```

任何一段缺失，都只能缩小结论范围，不能由后续步骤“补证明”。例如，executor 测试全过只能证明事务机械语义，不证明 L2 数据需要历史；CFO/history 门通过只能证明数据有历史信息，不证明 VSMT 优于 TAF、ELU、WFR 或 LOW。

### 1.1 首篇口径边界（D-206，取代 D-205 的收窄）

D-205 曾把首篇收窄为"不主张地点身份修订"。随后发现那个收窄建立在一个信息边界漏洞之上：`build_adapter_input` 把**模拟器真值世界 `camera_pose`** 直接发给每个方法，`_camera_record` 也把它写进公开相机记录，而 CFO 的禁止列表里既没有 `camera_pose` 也没有 `past_actions`。所以地点身份不是"被排除在学习之外"，是**被无偿给出**；CFO 也不是当前帧诊断器。D-206 的处理是**收回这个 oracle**，而不是围绕它收窄主张。

| 第一篇可以主张 | 第一篇不能主张 |
|---|---|
| 四类结构（entity/surface/fragment/**place**）上的类型化可执行事务选择 | 度量 SLAM 或全局位姿图优化 |
| 版本化状态与副作用的可审计性 | 超出声明里程计模型之外的传感噪声鲁棒性 |
| candidate-before-teacher 监督边界 | 真实机器人/真实传感器泛化 |
| **地点身份修订，含假回环的纠正** | 主动探索或主动寻找回环 |
| 统一事务空间把四类已有机制作为特例包含 | |

公开 pose 改为"以观测 0 为原点、由注册动作推算、叠加 2% 声明噪声"的相对位姿；真值世界位姿只进私有评价通道。place 保留 0.5 m 格量子，但格坐标表达在漂移的相对系里——于是同一物理地点可能落进不同格（假回环，需 place MERGE），两个物理地点可能落进同一格（混淆，需 place SPLIT）。**这两种失效模式在 D-205 的定义下根本不可能发生**，因为格坐标是精确的纯函数。

这条边界写在机器合同 `first_paper_scope_boundary` / `public_pose_channel` / `place_identity_revision` 里并由验证器拒绝弱化：真值 pose 不得回到公开 packet，噪声不得调小到零（否则退化为里程计积分题），place 不得同时"可学"又"是骨架"。

**为什么这是二区而不是三区的论据：** TAF/ELU/WFR/LOW 都不维护可修订的地点身份，再多训练预算也补不上——这是表达能力差距，不是预算差距。合同里登记为 `structural_capability_gap_argument`。

## 2. 状态词怎样读

本文统一使用以下状态，避免“代码存在”被误读成“科学主张成立”。

| 状态 | 含义 |
|---|---|
| 已认可 | 用户已接受科学口径或边界；不自动代表代码、数值或运行已批准 |
| 已实现候选 | 有代码和局部测试，可进入审查；不自动成为正式生成依赖 |
| 已审工程基线 | 代码/合同已按当时职责验收；只能证明对应工程边界 |
| 待冻结 | 仍有数值、资产、预算或语义选择为 `null` |
| 阻断 | 条件未满足时必须失败关闭，不能生成、训练或计入 family |
| 运行后判断 | 必须依靠真实 pilot、开发、validation 或 confirmation 结果，文档和单测不能预先证明 |

截至 D-212，旧 D-205～D-209 路线只作历史实现背景；当前活动方向是 D-210 双层地点记忆及 D-212 生成前纠偏。真实 route survey、seal、raw、adapter、private evaluation、训练和 confirmation 均未运行。D-210 固定“连续位姿信念只作候选先验，版本化拓扑地点图负责身份，0.5 m格不定义地点”；D-212 又要求12条路线的reachable/视觉/场景语义可复算，并补齐private instance/entity truth。旧 v4 的30°/64步/noisy-grid口径不得认证新批次。

[PLAN.md](PLAN.md) 是当前指针唯一维护处；本文件只解释主张—证据链。若本文件后续历史段落仍提到固定place scaffold、D-207活动合同或旧VM-04阻断，应按D-210/D-212和PLAN当前指针理解，不得反向覆盖新决定。

## 3. 论文主张拆成哪些可检验证据

### 3.1 主张 C1：VSMT 是结构事务选择，而不是普通图覆盖

所需证据：八个原子和 REPLACE 的显式前提、确定性 executor、同一 immutable base version 上的逐候选执行、非法分支和原子回滚、版本/provenance 保留，以及节点、关系、地点和 SPLIT/MERGE 的真实覆盖。

具体例子：旧记忆把两个视觉片段错误地保存成两个实体。MERGE 候选必须引用这两个旧实体版本，执行后关闭旧版本并生成合并后的新版本，同时留下来源和副作用记录。

它不等于：用了场景图、保存了图哈希、给动作起了 MERGE 名字，或在事后标签中把某例称为 MERGE。

### 3.2 主张 C2：版本化执行减少非法更新和非目标污染

所需证据：每个候选的 precondition、protected state、声明 delta、实际 delta、非法原因、回滚、版本链和共同 post-update audit；评价时还要报告当前正确性、长期 contamination、false birth、missing facts 和 collateral change。

具体例子：RELINK 只应关闭旧 `entity→place` 关系并建立新关系。如果同时改写了无关地点坐标，即使目标边正确，也必须记为未声明副作用或非法更新。

它不等于：输出文件可复现，或一次更新后的图看起来合理。版本化只提供可审计机制，真正减少错误仍要由比较实验验证。

### 3.3 主张 C3：学习信号不参与候选构造

所需证据：公开 observation 和 causal prior 先产生并封存候选；候选摘要、顺序、在线特征和 logits 对 private ID、reference 和 future 的改动保持不变；teacher 只在封存后打开并给已有候选评分；正确程序缺失时记录 candidate miss。

具体例子：交换两件物体的 simulator instance ID 后，private crosswalk 可以变化，但公开 packet、program request、候选集合和在线 logits 必须逐字节不变。

它不等于：函数签名里没有名为 `teacher` 的参数。还必须证明调用时序、文件来源和父 stage 没有预读 terminal/private 数据。

### 3.4 主张 C4：L2 数据确实需要历史，而不是终帧即可猜出答案

所需证据：真实平移和显著视角变化、自然遮挡/出视野后重现、只在公开不可观测窗口执行干预，以及同架构同预算的 Current-Frame-Only（CFO，当前帧诊断器）与 public-history probe 对比。

已认可的准入门是：按 house family 配对，history−CFO 的单侧 95% 区间下界大于 15 个百分点，CFO 不高于 60%，sealed-catalog oracle recall 至少 90%，bootstrap 10,000 次、seed 260916，且至少 32 个完成 family。九类 program 逐类报告；CFO 超过 60% 的类型保留在总体分母但标为 `easy_class`，不能单独支撑该原子主张。

它不等于：VSMT 已经优于基线。这个门只证明数据具有历史辨识压力且候选目录基本可解。

### 3.5 主张 C5：VSMT 相对共同接口基线有效

所需证据：VSMT、TAF、ELU、WFR、LOW 使用逐字节相同的 L2 `ObservationPacket`、相同 split、公开信息权限和公平预算；在 validation 完成方法选择后锁定，并在未用于选择的 confirmation family 上比较共同指标。

五个主臂的职责是：

| 方法 | 要回答的问题 | 不能据此声称什么 |
|---|---|---|
| VSMT | 类型化候选、真实执行、版本审计和 candidate-before-teacher 学习的组合是否有效 | 单独某个 executor、DINO 或事务名是创新 |
| TAF | ConceptGraphs 风格阈值关联/融合是否已足够 | 官方 ConceptGraphs 复现 |
| ELU | Fusion++/Dengler 风格存在与生命周期更新是否已足够 | 与上游训练和默认配置完全等价 |
| WFR | Khronos 风格窗口片段协调是否已足够 | 官方 Khronos 结果 |
| LOW | 只按末次观测覆盖的朴素规则能达到什么水平 | 它是 history probe 或 oracle 下界 |

它不等于：在 L1 oracle mask 上胜出即可支持主表。L1 只回答“感知近似正确时，结构机制是否工作”；论文主结果必须来自 L2 公开 proposal。

## 4. 实验单位和数据划分

### 4.1 五级单位

| 单位 | 定义 | 为什么需要 |
|---|---|---|
| source house | 一个 ProcTHOR/AI2-THOR 房屋来源 | 防止同一房屋跨 split 泄漏 |
| family | 同一 house、共享构造规则和配对分支的独立统计单位 | bootstrap 和完成数按 family，不把帧数冒充样本量 |
| branch | 自然遮挡后重现或出视野后重现 | 证明不是单一路线偶然现象 |
| episode | 一个预登记 program 在一条实际路线中的完整记录 | 形成 raw、packet、plan、候选、teacher 和评价链 |
| observation | 观测 0 及每个注册动作后的 RGB-D/pose | N 个动作必须对应 N+1 个观测，禁止跳帧补写 |

SPLIT/MERGE 还有 fresh replay：同一事前计划必须在每次独立重建场景时重复实现固定 1→2 或 2→1 proposal 转移。任何一次失败都保留 construction failure，不能换 program 或换样本。

### 4.2 来源顺序、pilot 和正式 family

pilot 前先按 result-blind manifest hash 和固定 seed 封存至少 70 个合格 house 的确定顺序。前 6 个是独立 pilot，只诊断路线、visibility 和构造成品率，永久排除 CFO/history 门、VM-05、VM-06 和论文效果统计。

只看 6 个 pilot 的 family 构造完成布尔：

| pilot 完成数 | 后续动作 |
|---|---|
| 5–6 | 从已封存顺序取后续 48 个正式 house |
| 4 | 从已封存顺序取后续 64 个正式 house |
| 0–3 | 停止，另立协议版本 |

正式 house 失败不补样；少于 32 个完成 family 时，构造门失败，不运行可辨识性门、VM-05 或 VM-06。这样做解决“看到哪些房容易成功后再挑样本”的选择偏差。它不保证 48 或 64 个都成功，也不允许根据模型准确率调整 N。

## 5. 一条 episode 怎样被构造

### 阶段 A：事前封存来源、路线和 program 意图

输入是已封存的 house 顺序、公开 reachable 信息、注册动作模板、program 类型、稳定 public selector、visibility subject，以及必要时的 SPLIT/MERGE artifact plan。输出是不可按结果修改的 route/program 计划和摘要。

例子：为 RELINK 只登记公开 entity A、旧 place P1、期望的新 place scaffold P2 和固定路线；调用者不能直接填写当前 `node_version_id` 或从 terminal 帧选择最有利的版本。

它不等于：该 program 已构造成功。此时只固定“准备检验什么”。

对应论文作用：阻止事后贴标签和按结果换路线，为 C3、C4 提供事前性证据。

当前状态：route/schema 核心已有实现候选；**真实 reachable scan 与逐步可达验证、Z 路线 family 构造器已由 D-209 实现（待审）**，动作幅度/decision time/action encoding 已由 D-205 冻结；selector 的 terminal 前父级时间封存仍待接生产父 stage。

### 阶段 B：按真实相机动作写 raw

观测 0 前允许一次初始 `TeleportFull`；之后只能执行预登记 Move/Rotate/Look。每一步用实际 camera pose 验收，而不是相信动作命令。公开 raw 只写 RGB、depth、camera 和 frame 元数据；私有 raw 单独写 instance masks 和 mapping。每侧都有唯一 terminal 和 manifest，中断保留已写前缀，禁止覆盖重跑。

例子：MoveAhead 请求 0.25 m，但实际只移动 0.18 m；receipt 必须记录实际 pose，并按 2 cm/1° 容差判断路线是否成立，不能把命令值当真实移动。

它不等于：公开 packet 已产生，也不等于 private mask 可以作为 L2 proposal。

对应论文作用：提供真实具身观测和不可抵赖的公私来源，为 C3、C4、C5 提供底层数据边界。

当前状态：raw writer、manifest 和失败保留外壳已有关闭实现；真实父 stage 和服务器资源派发尚未完成。

### 阶段 C：形成 L1 或 L2 匿名 proposal

L1 使用隔离的 simulator instance mask，再去除真实 ID，只作 oracle proposal 机制诊断。L2 主实验的 proposal generator 只能接收**当前单帧公开 RGB**；禁止提示、跨帧 video memory、depth、program、history、teacher、future 和 private identity。重叠 proposal 保留，完全重复 mask 直接失败，避免暗中引入未冻结 NMS/归属规则。

例子：两张 SAM mask 部分重叠但不相同，两者都进入公开候选；若位图完全相同则 construction failure，而不是静默删除一个。

它不等于：SAM 已安装或 checkpoint/阈值已冻结。当前真实 SAM loader、仓库 commit、权重摘要和 automatic-mask 数值仍缺失。

对应论文作用：L1 隔离感知误差；L2 保证五方法真正从公开视觉出发，为 C5 的公平主比较提供共同入口。

### 阶段 D：从公开 RGB-D 形成 `ObservationPacket`

共享前端给每个匿名 region 计算冻结 descriptor、公开 depth/因果pose-belief几何、surface/fragment/entity/free-space/visibility 和关系观测。D-210之后，0.5 m格只作规划与候选召回，place 必须成为与 entity/surface/fragment 共存的可版本化一等节点；`located_at`、`contains`、`supported_by`、`adjacent_to` 和路线转移是显式边。公开 packet 不含 instance ID、类别真值、reference program、世界真值pose或 future。

例子：一个椅子区域通过 depth 反投影得到可见质心和 extent，并向当前地点候选提供 `located_at` 支持；地点是否沿用旧节点由视觉—拓扑证据与事务决定，而不是由所在格直接决定。extent 只是当前可见部分，不能用真值 bbox 补齐。

它不等于：region 已跨帧获得真实身份。跨帧身份仍由各方法从公开描述、几何和旧记忆推断。

对应论文作用：把共同感知输入固定为可审计字节，隔离“前端不同”对 C5 的混淆。

当前状态：L1 materializer、context、packet/prior receipt 外壳已有实现候选；正式 DINO/SAM 资产、数值和真实 L2 接线待冻结。

### 阶段 E：只用过去公开 packet 形成 causal memory

从空图开始按观测顺序推进公开 bootstrap；每一步只允许读取当前及此前 packet，保存 version chain。terminal program matcher 使用“最后一个登记 terminal observation 之前”的 causal memory，不能任意传入更早或事后重算的便利 prior。

例子：terminal 是观测 12，则 program request 和 matcher prior 必须对应处理完观测 11 后的图；其 graph hash 要同时匹配 causal receipt、terminal packet 的 `prior_memory_ref` 和 construction plan。

它不等于：bootstrap 是最终 VSMT 模型，也不证明旧记忆正确。它只给所有后续构造提供同一因果旧状态。

对应论文作用：保证 C3 的候选输入来自合法历史，也让 C1/C2 的前后版本有明确起点。

### 阶段 F：在 terminal raw 加载前封存 selector、request、plan 和 prior

terminal−1 memory 更新完成后、terminal 公开/私有 raw 尚未加载时，父 stage 必须已经封存 selector spec；随后核心只能从 sealed public route、该 selector 和 terminal−1 causal memory 确定派生当前 open version refs，再封存 online request、construction plan、matcher prior 和时间 receipt。

例子：RELINK selector 只登记 entity A 和旧 place P1。核心必须从 terminal−1 memory 唯一解析 A、P1 及方向一致的 open `located_at`；零条或多条都失败，调用者不能手填一个恰好有利的 edge version。

它不等于：D-204 已经解除时间阻断。D-204 证明纯核心可把提前 selector receipt、D-203 provenance 和 D-202 receipt 串起来；真实生产父 stage 尚未按此顺序落盘，D-201 也尚未消费该链。

对应论文作用：这是 C3 最关键的调用时序证据，防止“函数内部没读答案，但调用者看完答案再选 refs”。

当前状态：D-202 和 D-203 已认可，D-204 纯核心候选已实现；尚未接生产 parent stage/raw writer/materializer，也未升级D-201，故仍为 `temporal_seal_pending`。

### 阶段 G：只在公开不可观测窗口执行 world intervention

visibility builder 从先前公开 mask/depth/pose 封存稀疏世界点，后续只用当前公开 depth/camera 判断 `visible`、`occluded`、`out_of_view` 或 `reobserved`。只有 `occluded/out_of_view` 才允许隐藏干预；缺失或无效 depth 不能证明遮挡。private mask 只能在公开判定封存后用于评价。

例子：目标世界点仍投影在画面内，但所有有效采样都被更近公开 depth 挡住，可判 `occluded`；若对应 depth 无效，则不能借缺测授权搬动物体。

它不等于：对象真实不可见身份已经由 private truth 证明，也不允许 Disable 造成的消失冒充自然遮挡。

对应论文作用：避免 terminal 图像直接暴露干预过程，为 C4 的历史必要性提供因果机会。

当前状态：公开 visibility 核心、route/worker receipt 绑定已有候选；正式采样步长、样本数、遮挡容差和 production callback 仍待冻结/接入。

### 阶段 H：加载 terminal 观测并执行公开构造充分门

terminal 公开 packet 形成后，public matcher 用显式配置比较 region 与 terminal−1 causal memory，只签 `program_public_match_satisfied`。它明确固定 `private_identity_used=false` 和 `semantic_identity_truth_established=false`：这是构造充分门，不是身份真值 oracle。

例子：BIRTH 的 terminal region 若仍唯一匹配某个旧节点，就记 construction failure；即使 private truth 后来说明它是新物体，也不能回头修改公开构造或补候选。

它不等于：program 的最终语义标签正确。private evaluator 仍需在候选封存后独立判断。

对应论文作用：保证九类样本在公共接口上有明确、可重复的最低条件，为 C1、C3、C5 建立一致任务定义。

当前状态：matcher 核心和 D-201 episode audit 已认可；D-204 已在纯核心中消费 D-202/D-203 时间链，但生产文件接线、D-201 在线seal消费、正式 matcher 数值和 family 聚合仍阻断。

### 阶段 I：封存候选并从同一旧版本真实执行

VSMT candidate generator 只读公开 terminal packet 和同一 causal prior，枚举受容量约束的程序；每个合法候选从同一 immutable base version 克隆并由 deterministic executor 真执行，保存 post-state、delta、非法原因和摘要。候选目录封存后不得增删、重排或修补。

例子：正确 RELINK 因公开候选生成器未提出而缺失，应记 candidate miss；teacher 不能把 reference RELINK 插入目录。

它不等于：候选覆盖率已达标，或 learned selector 已经训练。sealed-catalog oracle recall 会在数据生成后检查“正确答案是否存在于既有目录”。

对应论文作用：直接支撑 C1 和 C3，并把错误分成 candidate miss、teacher error 和 amortization error。

### 阶段 J：封存后才打开 teacher 和 private evaluator

teacher 可以读取已登记 future/reference/private evaluation，但只能给候选目录中的 program 评分。private evaluator 独立检查物理身份、实际后态和事务语义，不向部署 reader 暴露。物理失败、公开前提失败、candidate miss、executor 失败和 teacher 失败分层保存。

例子：同一把椅子真实从 P1 到 P2，公开前后也有关系证据，但 catalog 没有 RELINK：private 记录身份连续和后态，公开统计记 candidate miss，不能改标 BIRTH 或补 RELINK。

它不等于：teacher 评分必然正确。teacher 自身要有审计和误差统计，也不能用 private 结论指导在线 QUARANTINE。

对应论文作用：完成 C3 的监督边界，并为 C5 提供不污染在线输入的训练/评价目标。

### 阶段 K：先做数据准入，再做五方法效果实验

开发数据先过三类门：构造完成、sealed-catalog oracle recall、CFO/history 可辨识性。通过后才进入 VM-05，冻结五方法阈值、架构、训练/选择预算、seed、停止规则和共同指标；validation 只做已登记选择。所有选择锁定后再生成/打开 VM-06 confirmation。

例子：history probe 明显优于 CFO，但 sealed catalog recall 只有 70%，说明任务需要历史却常缺正确候选；该版本不能进入方法比较，更不能把后续 VSMT 失败归咎于 selector 学习。

它不等于：三个数据门通过就是论文正结果。只有 confirmation 上的预登记方法比较才能支持 C5。

## 6. 九类 program 怎样构造

下表描述的是**公开构造充分条件**。private identity 和后态只能在候选封存后判断语义真值；公开条件通过与真实身份正确是两个不同层次。

| Program | 要修什么 | terminal−1 旧记忆前提 | terminal 公开充分条件 | 主要失败含义 |
|---|---|---|---|---|
| NOOP | 当前无需结构修改 | 绑定稳定 prior 摘要 | 可靠 current regions 都唯一匹配 active memory，且不要求非 NOOP 处理 | 有 unmatched、ambiguous 或匹配 dormant 节点 |
| BIND | 当前 region 归入开放节点 | 预登记 open node | 目标 region 唯一匹配该 active node | 未匹配、歧义或匹配到别的节点 |
| BIRTH | 新建此前不存在的结构 | 预登记公开 reveal locus 和 absence scope | 目标 region 对旧记忆为 unmatched | 仍唯一/歧义匹配旧节点 |
| REACTIVATE | 恢复 dormant 节点 | 预登记 dormant node | 目标 region 唯一匹配该 dormant version | 匹配不到或生命周期不对 |
| RELINK | 同一实体改到新 place | open entity、旧 place、方向一致的 open `located_at` | entity 唯一匹配，且当前公开关系唯一落到不同的确定性新 place scaffold | 旧边不存在/歧义、新地点关系不唯一或仍是旧地点 |
| RETRACT | 关闭不再存在的开放实体 | 预登记 open entity | 至少两条时间分离的可靠 visible-empty 覆盖，且当前无 region 仍匹配它 | 负证据不足、仍有正匹配；edge RETRACT 当前直接阻断 |
| SPLIT | 一个欠分旧节点拆为两个 | 预登记 undersegmented entity 和 artifact plan | 每次 fresh replay 都实现远处 1 proposal→近处 2 proposals | 任一次未实现就保留 construction failure |
| MERGE | 两个误分旧节点合为一个 | 两个不同 open entity 和 artifact plan | 每次 fresh replay 都实现远处 2 proposals→近处 1 proposal | 任一次未实现就保留 construction failure |
| REPLACE | 旧实体撤回并在同一事件中新建 | open old entity、旧证据、新 reveal locus | 旧实体满足 RETRACT 负证据，同时新 region 对旧记忆 unmatched | 任一半不成立；它始终是 RETRACT+BIRTH 复合程序 |

### 6.1 为什么 matcher 只叫“充分门”

公开 matcher 解决的是“根据部署时可见证据，这个 program 至少有资格被构造吗”。它不能证明 BIND 的两个区域在物理世界真是同一物体，也不能证明 BIRTH 真是首次存在。这样分层是为了避免用 simulator ID 让构造变容易，同时仍能在封存后用 private truth 评估公开判断是否正确。

### 6.2 为什么 edge RETRACT 继续阻断

当前 packet 能表示实体所在空间的多次 visible-empty 证据，因此可以保守支持 entity RETRACT；但尚不能表示“某条关系在本应出现的跨时观测中持续缺席”的公开负证据。一次没检测到关系可能只是 proposal、深度或关系提取失败，不能证明边应关闭。故 edge RETRACT 没有生产入口，也不得用 entity 规则替代。

### 6.3 为什么 SPLIT/MERGE 必须事前登记并重复

SPLIT/MERGE 的表面现象很容易由 SAM 随机抖动产生。如果看完结果后把 1→2 叫 SPLIT、2→1 叫 MERGE，就会把偶然前端噪声包装成结构任务。因此必须先固定几何、前端版本、远/近 pose、重复次数和 program；每次 fresh replay 都达到固定转移才算公开构造满足。

## 7. 公共数据、私有数据和五类产物怎样隔离

| 通道 | 主要内容 | 谁可以读 | 论文作用 |
|---|---|---|---|
| public observation | RGB-D、camera、匿名 regions、descriptor、几何、关系、free-space、visibility | 所有部署方法、CFO/history probes | 共同输入与公平比较 |
| candidate | 封存的 programs、执行前后摘要、在线特征/logits | VSMT 选择器和审计器；teacher 只能引用 | C1/C3 的候选边界 |
| teacher | 对既有候选的训练分数/分布 | 训练侧，不进入部署输入 | hindsight supervision |
| private evaluation | instance identity、真值 mask、真实干预后态、语义判定 | 封存后 evaluator | 评价公开决定，不构造候选 |
| provenance | raw/materializer/route/plan/receipt/code/config/assets 摘要及失败 | 审计工具；deployment reader 不打开 | 证明时序和来源，不作为模型特征 |

**D-207 的目录语义修正：** sealed route 此前写在 episode 的 `public/` 下，与上表矛盾——`public/` 同时被当成"非私有"和"部署可读"。现在 route 移到 `provenance/route.json`，公开投影另去掉 `initial_pose`/`planned_poses`（验收比的是私有 plan）。留在 provenance 的 `phase_observation_indices`/`branch_type`/`visibility_subject_public_ref` 比 pose 更敏感——它们直接说明这条 episode 在考什么。既有反泄漏测试对这一类失明（route 本就在公开侧，改私有数据不会改它），因此另立目录不变量：部署可读字节中不得出现世界 pose 数值或 episode phase 结构。

关键不变性是：只改变 private identity、reference 或 future，而保持 public 相同，prior、selector request、candidate catalog、候选顺序和在线 logits 必须不变。private 标签允许变化，因为它正是独立评价内容。

## 8. L0、L1、L2 各自回答什么

| 层级 | 输入 | 能回答 | 不能回答 |
|---|---|---|---|
| L0 symbolic regression | 旧 C00–C11 符号图和人工结构事件 | executor、前提、回滚、版本、provenance 是否机械正确 | 视觉感知、真实具身构造、方法效果 |
| L1 oracle proposal | 新 RGB-D 序列，但 entity mask 来自隔离 private instance mask 并匿名化 | 假设 proposal 正确时，结构机制和数据链能否工作 | 从公开视觉出发的主表性能 |
| L2 public proposal | 当前公开 RGB 生成 proposal，公开 depth/pose 形成几何，五方法共享同字节 packet | 完整部署边界上的历史需求和方法比较 | 开放世界、主动探索、端到端 foundation model |

L0 和 L1 失败会定位机制问题；L2 失败可能来自 proposal、关联、候选、teacher 或选择器，因此必须分层报告，不能把所有错误合成一个 accuracy。

## 9. 证据怎样组合成论文结论

### 9.1 先组合“实验有效性”

```text
来源/划分事前封存
  AND 真实多视角与不可观测干预
  AND L2 公共前端同字节共享
  AND program 公开构造充分
  AND private 语义评价独立
  AND 失败不补样、不改标签
= 数据版本有资格进入可辨识性检查
```

缺任一项，只能报告工程或构造诊断。例如 route 合格但 SAM proposal 来自 private mask，只能算 L1。

### 9.2 再组合“学习问题有效性”

```text
数据版本有效
  AND history−CFO 严格门通过
  AND CFO 上限通过
  AND sealed-catalog oracle recall 通过
  AND 至少 32 个完成 family
= 有资格问“哪种记忆更新方法更好”
```

history 门失败说明终帧已经泄露答案或历史无辨识力；oracle recall 失败说明候选生成器常常不给正确答案。两者都不能靠增加 VSMT 网络容量修复。

### 9.3 最后组合“VSMT 方法主张”

```text
学习问题有效
  AND 五方法同输入/同 split/公平预算
  AND validation 选择规则事前冻结
  AND confirmation 未参与选择
  AND 共同主指标和副作用指标满足预登记统计门
  AND candidate/teacher/amortization error 分层可解释
= 才能支持 VSMT 相对方法主张
```

即使 VSMT 总体获胜，某个 `easy_class` program 也不能单独用作对应原子证据；即使某个原子明显获胜，也不能自动推广到开放世界、主动探索或第二任务领域。

### 9.4 三类失败分别意味着什么

| 失败层 | 典型现象 | 应得结论 | 不允许的修复 |
|---|---|---|---|
| 构造失败 | 路线不成立、visibility 不足、SPLIT 重放不稳定 | 当前固定规则下样本未构成 | 换房、换标签、删失败、看结果调路线 |
| 候选失败 | private reference 正确但 sealed catalog 无正确 program | candidate miss | teacher 补候选或扩大该例 cap |
| 学习失败 | 正确候选存在，teacher 可区分，但在线 selector 选错 | amortization/selection error | 把错误归咎于数据缺答案 |

teacher 本身给错分时另记 teacher error；executor 拒绝 reference 时另记语义或执行合同错误。

## 10. 当前实现地图（D-212纠偏后的解释）

### 10.1 已有并保留的底座

- VM-01：公私数据、共同 `ObservationPacket → MemoryUpdateResult` 接口和反泄漏合同。
- VM-02：TAF、ELU、WFR、LOW 的 clean-room 机制适配器工程基线。
- VM-03：公开九类 program 候选、同 base 执行、candidate seal 和封存后 teacher 边界。
- VM-04 外壳：多视角 raw writer、materializer/causal-prior/context receipts、失败保留、公开 proposal/visibility 核心、program matcher、episode audit、terminal 前 plan seal 和父级 request 派生核心。

这些内容证明“接口和拒绝规则可以实现”，不证明真实 house 数据已经生成或 VSMT 有效。

### 10.2 当前真正阻断 pilot 的缺口

D-205 把这张清单按性质分成三类。**混在一起是此前它无法被任何一次审查清空的原因**：科学裁决可以一次开会定完，产物摘要必须等真实产物存在，工程接线要写代码。

**A. 科学数值裁决 —— 已由 D-205 全部冻结。**

- ~~八种 camera action 的真实请求参数~~（Move 0.25 m，Rotate/Look 30°，禁用 `forceAction` 与默认值；固定 build 的 API smoke 仍是执行前必需）
- ~~`decision_time_s` 规则与 past-action encoding~~（名义注册动作时钟 1.0 s/动作；9 维 one-hot 加观测 0 标志位）
- ~~L2 proposal 数值与 automatic-mask 配置~~（196 像素、每帧至多 64 个、NMS 关闭以保留重叠 proposal）
- ~~公开 visibility 数值~~（0.05–20 m、遮挡容差 0.05 m、步长 4、样本 32–512）
- ~~matcher 正式数值~~（按 entity/surface/fragment 分别定值，分差 0.10，包络裕度 0.02 m，负证据 ≥2 条且间隔 ≥2.0 s）
- ~~SPLIT/MERGE 几何、前端伪影判据、fresh replay 次数~~（3 次，判据只在冻结 L2 公开 proposal 上测量）
- ~~CFO/history 共用 probe 架构与训练预算~~（单一注册配置，无任何选择，因此不需要预留选择 family）

**B. 真实产物摘要 —— 只能由真实产物产生，凭空填写即伪造证据。**

1. SAM 2.1 仓库 commit 与 checkpoint SHA-256。
2. automatic-mask config、assets receipt 与 generator 代码摘要。
3. materializer 代码与 config 摘要（须先封存 source manifest）。
4. 已审 L2 前端 receipt 摘要。

**C. 工程接线 —— D-206 新增两项，其余范围不变。**

5. **（D-206 新增）** 把 raw writer 的公开相机记录从真值世界 pose 换成 episode 相对的带噪里程计，真值位姿改写私有评价通道。
6. **（D-206 新增）** 把确定性 place 骨架降级为 oracle 诊断臂，并实现基于证据的 place 关联与 `adjacent_to`。
7. 把 D-204 纯核心接入生产父 stage/raw writer/materializer，并升级 D-201 离线 episode receipt 消费在线 seal。
8. 把 production visibility、materializer、intervention、RELINK、candidate/teacher 接入同一真实 episode 纵向链。
9. ~~实现真实 reachable scan 与 **Z 路线 family 构造器**~~（D-209 已实现待审：真实 `GetReachablePositions` 封存、逐步可达验证、Z family 构造器；阻断项按 D-059 待用户审查后才可勾掉）；父 stage 多 worker、确定性合并、失败恢复、verify/export 仍缺。
10. 用户审查 pilot family 完成度的机械派生（已实现，见 §10.3）。
11. 封存互不相交的 pilot 与正式 house manifest，完成最终开闸审计。

D-206 **不新增任何 B 类产物摘要**——剩余 null 与 D-205 完全相同。

edge RETRACT 继续作为明确覆盖缺口阻断，不应在没有新公开关系负证据类型时被“顺手实现”。

### 10.2b 下一步的两项工程接线（②③）

科学裁决已由 D-205～D-207 全部冻结，剩下的 C 类阻断项收敛成两项：

**② 真实公开 reachable 扫描与路线构造 —— D-209 已实现，待用户审查。** 解决"路线目前只有 schema 和纯核心，没有真实可达点来源"的问题。输入是已冻结的八种注册动作模板、公开可达格和干预前匿名 visibility 扫描；输出是真实扫描回执与两类 family 的封存路线。例如一条地点层 Z 路线要走完 4 m 走廊、转 90°、走 3 m 连接段、反向转 90°、再走 4 m 走廊，约 50 个注册动作，落在 D-207 的地点层 64 步预算内。**每个计划步必须预先验证落在可达格上**——这是长路线的成品率护栏，因为路线验收是逐锚点绝对比较、不累积，长路线的真实风险是某一个动作被挡住而整条失败，而不是精度下降。它不等于主动探索：路线由干预前的公开信息预登记，找不到合法路线就记构造失败，不换房、不换目标。

**③ 父 stage 多 worker 调度与 receipt 合并。** 解决"单 episode 的 writer/materializer 外壳都在，但没有东西按 family 把它们跑起来"的问题。输入是 ② 的路线、已实现的 raw writer/materializer/matcher 外壳和 D-205 的 pilot 完成度机械派生；输出是逐 family 的并发执行与确定性合并回执。先单 worker 实测 CPU/RAM/VRAM/IO，再按最大安全并发派发；记录 requested/actual worker、分片、退出与资源依据，合并顺序与完成顺序无关。逐 episode 的 `complete/failure/not_started` 全数保留。它不等于开闸：失败保留、不补样、不覆盖、不静默重跑的规则不变。

**②③ 都不解除任何授权位。** 完成后剩余阻断项只有 8 个真实产物摘要与用户对 pilot 完成度派生的代码审查。

### 10.3 当前细粒度指针

D-206 之后，最近的因果链是：

```text
D-201→D-204 时间封存链（纯核心可复算，仍 temporal_seal_pending）
  └─ D-205：科学数值一次性冻结，阻断项按性质分为 A/B/C 三类
       └─ D-206：收回地点层 oracle，place 变为可学习
            ├─ A 科学裁决：已完成（含 pose 通道、噪声模型、place matcher、Z 路线）
            ├─ pilot family 完成度机械派生：已实现，待用户审查
            ├─ D-207：地点层 64 步预算、route 移入 provenance
            └─ D-209：真实 reachable scan ＋ 逐步可达验证 ＋ Z 路线 family 构造器（②，已实现待审）
                 └─ 当前下一步（按对生成数据的贡献排序）：
                      ③ 生产父 stage 多 worker 调度与 receipt 合并 ← 下一条
                      ④ 取得真实 SAM 资产并冻结 B 类 4 组摘要（L2 与 SPLIT/MERGE 需要）
                      ⑤ 封存 70-house 顺序，开闸跑 6 个 pilot family
                 （① raw writer 换 pose 通道已完成；②③ 完成后 ①②③ 合起来可在 SAM 之前产出真实 raw）
```

①②③ 不需要 SAM：路线、visibility、干预、raw 写盘都只依赖公开 RGB-D 与几何。因此**可以在 SAM 资产到位之前先跑通并产出真实多视角 raw episode**，作为工程可行性运行（显式不是科学样本），这是目前"尽快看到真实数据"的最短路径。

科学裁决完成不等于可以运行：`assert_numeric_freeze_complete` 只回答“操作者是否已经决定完”，`assert_generation_authorized` 继续要求 B 类摘要、pilot 派生的用户审查和授权位，两者不可互相代替。pilot 跑完后，`pilot_report_only_diagnostic` 会在正式生成前给出一次只报告、不可用于任何选择的 CFO/history 早期信号。

## 11. 后续每轮怎样更新这份记录

为了继续细粒度推进但不让文档重新变乱，每一轮只更新四处：

1. 在本节“当前细粒度指针”替换当前叶节点，不无限追加旧状态。
2. 在对应阶段的“当前状态”改一行，说明新证据解锁了什么。
3. 在“当前真正阻断 pilot 的缺口”勾掉或改写一个具体阻断项。
4. 在下面的功能索引新增一行 D-编号；完整历史仍只追加到 DECISIONS。

每个新 decision 的说明必须用固定句式：

```text
解决的问题：……
允许的输入：……
产生的输出：……
它解锁：……
它仍不解锁：……
下一条依赖：……
```

这样 chronological decision 保留完整法律式记录，而本文始终保持一条可读的实验逻辑。

## 12. Decision 功能索引

| 功能组 | 主要 decisions | 在证据链中的位置 |
|---|---|---|
| 论文方向与信息边界 | D-122～D-125 | 定义 C1～C5、主比较、candidate-before-teacher 和 L0/L1/L2 |
| 事务/关系/结构机制 | D-126～D-143 | SPLIT/MERGE、causal prior、place scaffold、关系、审计和候选容量 |
| 旧两房工程批与停止线 | D-144～D-180 | 证明 writer/动作探针可工作，同时证明原36槽不足以支持论文主张 |
| 新多视角科学合同 | D-181～D-183 | 真实视角、不可观测干预、CFO/history、pilot/formal 规则 |
| raw/materializer/route 外壳 | D-184～D-198 | 文件、receipt、context、公开输入来源和 L1/L2 边界 |
| L2 proposal/visibility/program | D-199 | 单帧公开 proposal、公开 visibility、九类必要前提 |
| 公开构造充分门 | D-200 | matcher、route/worker visibility receipt、edge RETRACT 阻断 |
| episode 因果内容审计 | D-201 | terminal packet、terminal−1 prior、matcher 和 materializer 的同 episode 绑定 |
| materializer 内部时间顺序 | D-202 | terminal raw 加载前封存 plan/prior，但父 request 来源仍 pending |
| 父级 request 公开派生 | D-203 | 禁止手填 version ID，从公开 selector 和 causal memory 唯一解析 refs |
| selector与父来源时间链 | D-204（实现候选） | selector提前seal，并把D-203 v2 provenance接入D-202 v2；生产接线和D-201消费仍缺 |
| 数值冻结与首篇口径 | D-205 | 科学裁决一次性冻结、阻断项按性质分 A/B/C、place 收窄、pilot 只报告诊断与 SPLIT/MERGE 成品率下限、family 完成度机械派生 |
| 地点层 oracle 收回 | D-206 | 公开 pose 改相对带噪里程计、place 变可学习、Z 路线 family、CFO 掩码补漏、oracle 诊断臂 |
| 分层预算与通道分离 | D-207 | 地点层 64 步/实体层 24 步、route 移入 provenance、公开投影去世界锚点、目录不变量 |
| 真实可达扫描与地点层路线 | D-209 | 真实 `GetReachablePositions` 封存、逐步可达验证作为长路线成品率护栏、Z 路线 family 构造器与强制后续可判别观测 |

## 13. 为什么新版 VM-04 比第一次复杂

第一次 VM-04 的两房 36 固定槽主要验证 writer、公私分文件、摘要、失败保留和资源派发；它使用近静止视角，部分结构依赖 private instance mask，四个 RELINK 预登记失败，也没有独立 house split 和五方法效果链。它可以快速回答“工程文件能不能写出来”，不能回答“历史是否必要、候选是否无泄漏、VSMT 是否优于共同输入基线”。

新版 VM-04 同时承担三种职责：真实具身数据、反信息泄漏证明、论文可辨识性准入。复杂度主要来自把这三件事都变成可机器核验的边界，而不是单纯多写几个样本。细粒度继续保留，但每个 receipt 都必须落回本文件的一条主张链；若一个新 receipt 既不改变输入权限、不排除替代解释，也不解锁下一实验阶段，就不应继续单独扩张。
