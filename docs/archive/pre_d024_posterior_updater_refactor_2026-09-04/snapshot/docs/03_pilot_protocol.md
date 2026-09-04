# 03 — 第一轮验证：先反证双时间 posterior revision

> 状态：`planned / implementation not started / thresholds not frozen`

本文是第一版代码和无学习实验的唯一合同。它先用人话说明每个实验为什么存在，再在括号中保留代码和论文需要的名称。

## 1. 这轮实验到底为了什么

机器人走在一条视觉重复的走廊里。它可以猜测“前方可能还是走廊”，但不能因为猜了就把未见空间写成事实。继续前进后：

- 如果深度和位姿支持前方确实延伸，就确认刚刚的候选；
- 如果看到墙壁和左侧开口，就撤销“继续直行”，提出“左侧可通行”的新候选；
- 如果画面和旧位置很像，就同时考虑新区域、回环和定位漂移；
- 如果几种解释会导致不同路线，就先选择能区分它们的观察动作。

另一个场景中，机器人原来记得“椅子在 A”，后来椅子被搬到 B。它还要：

- 关闭失效的 A 位置；
- 保留同一把椅子的 identity；
- 修改真正受影响的关系；
- 不改坏远处无关的桌子和花盆；
- 保存为什么改、何时改以及旧版本。

所以第一轮验证四个连续问题：

1. **预测与扩展**：未见空间能否先作为假设，再被支持、撤销或继续保留；
2. **主动取证**：有多个解释时，能否选择真正帮助任务和消除歧义的下一动作；
3. **确认与修订**：证据何时足以把候选写成事实，真实变化后又能否只改必要部分；
4. **读写隔离**：任务语境能否改变“先处理谁”，同时不改变“世界里有什么”。

第一轮把视觉识别、位姿和正确解释直接给系统，只检查 belief evolution 本身。这里的 **oracle** 是“研究者提供当前暂不测试的答案”，不是模型能力，也不是实验结果。

> 如果 oracle 条件下候选和事实都会混淆，或者明确的修订仍执行错误，就不能通过换 detector、VLM、LLM 或更大模型掩盖问题。

### 1.1 当前候选最小垂直切片

当前不同时跑七个学习模块。posterior-only pilot 固定 perception、identity、visibility、pose、candidate retrieval 和 dependency graph，只实现：

~~~text
event adapter
  → preserve / quarantine / commit gate
  → typed direct edit
  → deterministic dependency closure
  → valid-time + transaction-time versioned executor
  → operation/history/evidence evaluator
~~~

实验顺序沿用唯一核心包的 P1–P4：先判是否允许改，再判直接事务改什么，继而判依赖传播到哪里停止，最后判迟到/冲突证据属于哪个时间和来源。串联前每个模块都使用 oracle upstream；这样失败能被定位，不会由端到端总分掩盖。

## 2. 每一步给系统什么、系统返回什么

| 环节 | 人话 | 正式名称 |
|---|---|---|
| 旧世界 | 已确认结构、候选结构、对象关系和历史版本 | SceneBelief `B_t` |
| 动作 | 打算做什么、实际做了什么、最后移动到哪里 | planned/executed action + pose transition |
| 动作后预测 | 预计会看见哪些旧结构，未见区域有哪些可能 | predicted prior / hypothesis set |
| 当前现场 | 这一刻真正观察到的节点、边、深度和可见性 | ObservationGraph `O_{t+1}` |
| 对应世界 | 当前帧每块临时区域属于哪个旧节点、是否是新候选、能否写长期记忆 | RegionWorldAssociationRecord（planned） |
| 证据处理 | 哪个候选被支持或否定，差异来自视角还是世界变化 | belief assimilation |
| 修改意图 | 确认、扩展、修订、保持或暂缓；改谁、在哪里停 | typed posterior update |
| 新世界 | 更新后的事实、候选、版本和证据来源 | posterior SceneBelief `B_{t+1}` |
| 下一动作 | 为任务前进，或先观察以消除关键歧义 | active evidence action |

第一版不接真实 detector、DINO、真实 RGB-D 或连续控制。动作只来自一个很小的离散集合。

## 3. 完整闭环 E0–E6 的保留角色

E0–E6 的细粒度全部保留，但当前优先级不是七项并行：E0 的 evaluator/执行链和 E5 的 bounded revision 是 P0；E1/E2/E4 是以后替换 oracle prior/identity 的前置；E3 是补证；E6 是只读边界。

七个实验不是七项并列创新。它们围绕同一个核心输出逐层追问：

~~~text
世界事实的 semantic status 应怎样变化？
拓扑节点/关系应怎样 add、relink、propagate 或 stop？
旧事实何时失效，新事实何时生效？
哪些 control facts 必须保持？
~~~

| 实验 | 在母命题中验证什么 | 性质 |
|---|---|---|
| E0 | typed operation、版本和 evaluator 能否准确执行/判分，否则“改对了”没有可信定义 | 判尺前置 |
| E1 | 新证据怎样把预测从 candidate 改为 confirmed/rejected，并只扩展实际可见拓扑 | 状态与拓扑前置 |
| E2 | 相似观测应 append 新节点、merge 旧节点，还是保持 ambiguous，避免错误拓扑永久化 | 拓扑身份前置 |
| E3 | 当前证据不足以决定 revision 时，能否主动取得真正区分候选的证据 | 补证机制 |
| E4 | 多少、什么类型的证据允许 candidate 在某一时刻成为 fact，或被关闭/拒绝 | 状态与有效时间前置 |
| E5 | 已确认事实被反驳后，是否完整修改 semantic/topology/time，同时传播必要后果并保护 control facts | **核心机制直接验证** |
| E6 | prompt/任务优先级只能改变读取，不能越权改变任何 world fact 或版本 | 写入边界反证 |

七个实验共用同一种写法。每个 fixture 都必须保存：

```text
初始世界 B_t
+ planned / executed action / pose transition
+ 动作后的预测候选
+ 当前观测与证据可靠性
+ 临时结构区域及其 world-node 对应候选
+ 哪些区域允许写入哪些长期 latent
+ 系统应走的状态路径
+ 期望的新世界 B_t+1
+ 下一动作目标
+ 只改变一个条件的反事实
+ decision_ids
```

人工写出的期望结果在对应 HC 冻结前只是设计答案，不能称为训练或评测 ground truth；posterior-only 直接相关项为 HC-001–005、HC-011、HC-013、HC-015–018。

### E0 — 先检查实验工具和执行链是否可信

**与母命题的关系：判尺前置。** E0 不证明创新，只保证语义状态、关系和版本变化能够被准确执行、回放和判错。

**初始准备**

1. 人工写一份旧世界，明确哪些是 confirmed fact、哪些是 candidate、哪些是历史版本；
2. 人工给出这一步的正确候选变化、正确 typed update 和正确的新世界；
3. 本实验不让系统预测，也不让系统自己判断身份、可见性或修改范围。

**执行过程**

1. contract validator 检查 ID、版本、reference frame、action 和证据引用是否合法；
2. deterministic executor 按人工答案执行候选提出/否定/晋升或 confirmed graph 修订；
3. evaluator 比较实际输出与人工期望的新世界；
4. 再故意制造 candidate 混入 confirmed、错误版本引用、半提交和无关事实被修改等错误，检查 evaluator 是否能发现。

**正确时应该看到**

- 合法输入产生完全一致的 posterior，或落入预先声明的最小等价解集合；
- 旧版本仍可查询，新版本能回到动作和观测证据；
- 任一操作非法时整组拒绝，不留下半改状态；
- 人工植入的每一种错误都会让对应指标恶化。

**失败说明**

- 合法答案执行错误：schema、executor 或版本不变量有问题；
- 错误答案仍被判为正确：evaluator 或等价解定义有问题；
- E0 未通过时禁止训练，因为后续数字没有可信的“尺子”。

**计划产物**

- contract validation report；
- executor/evaluator unit tests；
- 所有 W/R/Q fixture 的 oracle replay；
- 记录实际判题语义的 `decision_ids`。

E0 只证明实验与执行工具可用，不证明系统拥有预测、理解或规划能力。

### E1 — 行动后的结构预测能否被新证据纠正

**与母命题的关系：建立可被修改的 prior。** 它验证 candidate/confirmed/rejected 的 semantic transition，以及新拓扑只能在实际证据覆盖范围内生效。

**初始世界**

- ConfirmedGraph 只确认机器人位于走廊 C1；
- C1 前方尚未观察，不能写成走廊、墙壁或房间；
- 机器人计划向前移动一步。

**预测阶段**

1. 系统根据 C1 的局部结构和 planned action 提出候选 H-forward：“前方可能继续”；
2. 候选必须写入 HypothesisSet，记录来源、置信度、待验证区域和互斥组；
3. ConfirmedGraph 此时保持不变。

**观测与吸收阶段**

1. 记录实际下发动作和 pose transition，不能把 planned action 当成实际位移；
2. 基准场景提供“正前方是墙、左侧有可靠自由空间”的 oracle depth/pose evidence；
3. oracle 先把当前帧切成临时 wall/floor/opening regions，并给出它们到已有 world nodes 的正确对应；
4. 系统必须把随机器人靠近而尺度变化的同一墙/地面继续绑定到旧节点；新开口没有旧对应时只产生 new-node candidate；
5. 系统将已绑定观测投影到当前世界坐标，与 H-forward 的预期可见区域比较；
6. 正前方墙壁反驳 H-forward，因此该候选应被 REJECT；
7. 左侧自由空间只足以提出 H-left-open，不足以直接断言它一定是走廊；
8. 只有允许写入的节点更新 latent；已确认的 C1 和其他无关结构不变。

**单因素反事实**

- 只把观测改为“前方连续自由空间且位姿一致”；
- H-forward 可以得到支持，但只能确认实际观测覆盖的区间；
- 更远的未观察空间继续保持 candidate 或 unknown，不能生成无限走廊。

**正确时应该看到**

- 预测先成为候选，而不是事实；
- 反证能否定直行候选，新证据能提出左侧候选；
- 支持证据只能确认已经看见的范围；
- 新一帧不会机械创建重复走廊节点。
- 同一表面由远变近、被门框暂时切开时，不会因此复制世界节点或交叉污染 latent。

**失败说明**

- 预测后立刻扩充 ConfirmedGraph：候选与事实边界失效；
- 看见墙壁仍保留直行候选：证据吸收或 rejection 失效；
- 左侧一点自由空间直接变成完整走廊：过度确认；
- 每走一步复制相同节点：这只是 greedy append，不是世界模型。
- 把透视近/远分区直接当永久 ID，或把未关联区域平均进整张记忆：region-to-world binding 失效。

本实验对应 W0/W1/W2，受 HC-007、HC-008、HC-009、HC-011 和 HC-014 约束。

### E2 — 相似画面下能否区分新区域、回环和定位漂移

**与母命题的关系：冻结拓扑身份之前先保留歧义。** append、merge 和 quarantine 会产生完全不同且可能不可逆的旧世界组织。

**共同初始条件**

- 机器人进入一段外观高度重复的走廊；
- 当前画面在三组序列中尽量保持相似；
- 系统已经保存若干历史 Place、拓扑连接和 pose uncertainty。

**三组单因素序列**

1. **新区域**：pose transition 连续，当前区域与旧地标不完全一致，并出现从 C1 指向新区域的合理 attachment；
2. **回到旧地点**：当前外观、几何和已有拓扑共同支持某个历史 Place，闭环后连接关系也一致；
3. **定位漂移**：odometry 与视觉/深度互相冲突，新区域、旧地点和 pose error 都能解释当前观测。

**执行过程**

1. 系统先保留当前 ObservationRegion 到多个历史 world nodes 的对应候选，不用单一图像相似度直接写 latent；
2. 系统分别计算“new segment”“loop closure”“pose uncertainty”的证据；
3. 证据充分时选择对应路径；证据不足时同时保留多个候选；
4. 在没有满足回环条件前，不允许 merge 到旧地点或更新其 latent；
5. 在 pose 明显不可靠时，不允许直接 append 新节点；
6. 每个候选记录支持证据、反证、所需下一观察和版本状态。

**正确时应该看到**

- 新区域被连接为候选或确认的新 segment；
- 真正回访时复用历史 Place，不重复建图；
- 定位漂移场景保持歧义或 quarantine，不做不可逆 append/merge。

**反事实**

- 只替换一个历史地标或一项 pose consistency evidence；
- 输出应从 new 倾向变成 loop，或从确定判断退回多假设；
- 其他对象、关系和历史版本保持不变。

**失败说明**

- 画面相似就 merge：容易把新走廊吞进旧地图；
- 走一步就 append：回环时不断制造重复节点；
- pose 冲突仍强制二选一：定位错误会变成永久拓扑错误。

本实验对应 W0/W3，受 HC-009、HC-010 和 HC-014 约束。

### E3 — 机器人能否主动选择最有价值的下一眼

**与母命题的关系：为 revision 补证。** 它不直接修改世界，而是在现有证据无法决定 semantic/topology transition 时选择下一条证据。

**初始世界**

- E2 留下至少两个仍然合理的候选，例如“左侧是走廊”和“左侧只是门洞”；
- 候选会导致不同后续路线，因此歧义与当前任务相关；
- 可选动作限制为一个很小的离散集合，例如左看、前进、回看旧地标和停止。

**每个动作提供的信息**

- 预计能支持或否定哪些候选；
- 对当前任务进度有什么帮助；
- 移动或转向成本是多少；
- 是否存在碰撞、越界或不可恢复风险。

**执行过程**

1. hard safety gate 先拒绝风险不可接受的动作；
2. 对剩余动作分别计算任务收益、预期信息价值和行动成本；
3. 选择一个能以合理成本区分关键候选的动作；
4. 执行动作并接收新观测；
5. 检查候选不确定性是否确实下降，以及任务是否被无意义探索拖延。

**单因素反事实**

- 保持世界与候选不变，只交换“左看”和“回看”能够获得的证据；
- 正确动作也应随之改变；
- 再把歧义改成“不影响当前任务”，系统应继续任务，而不是为了好奇反复观察。

**正确时应该看到**

- 选择的动作能区分当前最关键的候选；
- 高信息但高风险的动作被 safety gate 拒绝；
- 已经确定路线时不重复复查；
- action decision 明确记录“想验证哪组候选”，不修改世界事实。

**失败说明**

- 永远选择最近 frontier：没有利用当前信念歧义；
- 永远选择最便宜动作：可能长期无法消除关键错误解释；
- 只追求信息量而忽略风险和任务：形成无意义探索；
- 选择动作时直接改图：ActiveContext/planning 污染 SceneBelief。

本实验对应 W4，受 HC-012 约束；权重和允许动作集合只能用 validation 冻结。

### E4 — 候选需要多少证据才能成为世界事实

**与母命题的关系：决定事实何时生效。** 它验证 candidate 的晋升、保留和拒绝门，以及相应版本的开启/关闭时刻。

**共同初始条件**

- ConfirmedGraph 只包含已经确认的走廊 C1；
- HypothesisSet 包含“左侧可能存在可通行结构”；
- 候选记录来源、待验证条件、支持证据、反证和互斥组。

**弱证据序列**

1. 第一次观测只看到一小块左侧自由空间；
2. 该证据也可能由门缝、凹槽、深度噪声或 pose error 解释；
3. 系统可以增强候选，但必须 RETAIN 在 HypothesisSet；
4. ConfirmedGraph 不发生结构扩充。

**连续支持序列**

1. 机器人从不同位置再次观察左侧区域；
2. pose、geometry 和可见区域相互一致；
3. 转向后观测到连续、可连接的可通行结构；
4. 候选逐步累积相互独立的支持；
5. 只有满足 HC-008 冻结的晋升规则后，executor 才执行 PROMOTE/ADD；
6. 新事实保留其候选来源和全部确认依据。

**反证序列**

1. 保持最初候选不变，后续提供“左侧其实是封闭凹槽”的可靠证据；
2. 候选应被 REJECT，并记录被哪条证据否定；
3. 已确认的 C1 不受影响。

**正确时应该看到**

- 弱证据只保留候选；
- 充分且一致的证据能在合理时间内完成晋升；
- 可靠反证能够撤销候选；
- PROMOTE 只确认被证据覆盖的结构，不补全未见空间。

**失败说明**

- 一次模糊观测就确认：误扩图风险过高；
- 多次独立证据后仍永不确认：世界模型无法形成可用的稳定认识；
- 反证后候选仍长期存活：错误假设不能恢复；
- 只保存最终事实而丢失候选历史：无法解释为什么确认。

本实验受 HC-008 和 HC-009 约束。具体证据数量、独立性和阈值尚未冻结，只能在 validation 上确定。

### E5 — 世界真的变化时能否只修订必要部分

**与母命题的关系：核心机制的直接实验。** E5 同时检查 semantic status、topological relation、valid time/version、necessary propagation、stop boundary 和 control preservation。

E5 是旧“动态冲突修订”方向在当前世界模型中的核心位置。它分两组检查：先判断是否真的发生变化，再判断变化后应传播到哪里。

**共同初始世界**

- chair_1 位于 A；
- table_1、plant_1 和另一区域作为无关对照；
- 另一个子场景中 cart_1 supports box_1；
- 所有事实都带有效版本和来源。

**E5-A：同一旧世界，只替换现场解释**

1. **搬迁到 B**：在 B 可靠重识别到 chair_1，A 也清楚可见且为空。正确处理是关闭 chair_1@A，建立 chair_1@B，并保留 identity 和旧版本；
2. **可靠缺席、去向未知**：A 清楚可见且多帧为空，但没有在其他位置看到 chair_1。正确处理是让旧位置失效，新位置保持 unknown，不能编造 B；
3. **人物遮挡**：A 被可信 occluder 挡住。正确处理是更新 visibility，继续 PRESERVE chair_1@A。

三组都先检查观测区域绑定：遮挡产生的临时 split 不能制造新世界表面；搬迁对象区域只有通过 identity/geometry association 后才能写 chair_1；歧义区域不得更新 chair_1 或邻近墙面的长期 latent。

三组只替换 visibility/identity evidence，旧世界和其他对象完全相同。

**E5-B：必要传播和停止边界**

1. 旧世界记录 cart_1 supports box_1，plant_1 与二者没有依赖关系；
2. 新现场确认推车和箱子一起移动；
3. 系统先确定推车的 primary edit；
4. 只沿 HC-003 允许的关系传播 operator-specific 后果；
5. 箱子需要更新的位置或支撑关系必须完整；
6. 传播到无依赖边时停止，plant_1、table_1 和其他区域保持不变；
7. 整组 typed update 原子提交，保存修改理由和旧版本。

**正确时应该看到**

- 搬迁、可靠缺席和遮挡走三条不同路径；
- unknown 不被写成虚构位置；
- 推车—箱子的必要后果没有遗漏；
- 无关对象、无关关系和历史版本没有被污染；
- affected、control 和 stop 都能回到明确证据与 operator。

**单因素反事实**

- 把 B 中对象 identity 改成另一把椅子，正确操作应从 SUPERSEDE 变成 ADD；
- 删除 cart_1 supports box_1，箱子不再必须随推车传播；
- 为 plant_1 增加真实依赖边后，它才可能进入 affected set。

**失败说明**

- 把“没看到”统一当成消失：visibility 与 world change 混用；
- 搬迁后同时保留 A/B 为当前位置：旧事实未关闭；
- 只改推车不改箱子：必要传播漏改；
- 修改花盆或整张图：停止边界和 control preservation 失败；
- 任一步失败后留下半提交版本：事务与版本链失败。

本实验对应 W0/R1–R4/R6，受 HC-001–HC-005、HC-011 和 HC-014 约束。

### E6 — 当前任务可以改变先找谁，但不能改变世界里有什么

**与母命题的关系：读写隔离的反证边界。** 如果 Top-K 或 prompt 能改世界事实，说明 revision controller 没有独占写入权限。

**初始序列**

1. 机器人直行时看到木箱 box_A，并把它与当时的 Place 和关系证据写入世界；
2. 用户随后要求向右转；
3. 机器人右转后看到另一个同类实例 box_B；
4. 两个木箱都已经满足各自的确认条件，并拥有独立 identity 和位置历史。

**查询阶段**

1. 用户只说“找木箱”；
2. ActiveContext 根据近期路线、对话和任务代价，可以把 box_B 排在 box_A 前面；
3. 系统优先返回或前往 box_B，但不能删除、覆盖或合并 box_A；
4. 若用户改为“找刚才直走时看到的木箱”，排序应切换到 box_A；
5. 若两个候选会导致代价或风险明显不同且用户意图无法判断，则按 HC-006 触发澄清。

**单因素反事实**

- 保持世界图不变，只替换 prompt、路线历史或当前任务；
- 允许候选排序和是否澄清发生变化；
- ConfirmedGraph、两个实例的 identity、位置和版本必须逐字段保持不变。

**正确时应该看到**

- 两个木箱始终存在于持久世界；
- query 结果会随 ActiveContext 改变；
- 用户补充信息后能够重新找到 box_A；
- 澄清只发生在歧义会造成有代价或风险的不同动作时；
- action/query 日志与 belief update 日志明确分离。

**失败说明**

- top-1 查询后删除 box_A：检索结果污染世界事实；
- 因为两个实例同类而合并 identity：association 失败；
- prompt 改变导致对象位置或版本变化：ActiveContext 越权写入；
- 任何歧义都询问：系统不可用；从不询问：可能执行高代价错误动作。

本实验对应 Q1，受 HC-006 约束。FARM 风格关系排序可作为 read/query baseline，但不能替代世界信念写入实验。

### 跨实验边界检查（P1，不作为第八个实验）

- R5：同一个人无论静止多久仍是 actor；静止、遮挡和驻留时长只能改变状态，不能把人改成固定结构；
- predicted hypothesis 不能出现在 ConfirmedGraph；
- planned action、ActiveContext 和 query ranking 不能直接修改世界事实；
- occluded、out-of-FOV、reliably absent、unknown 和 removed-from-scene 不能混用；
- 任意实验中没有被证据或依赖路径触及的 control facts 必须逐字段保持。

这些不变量附加到 E0–E6 的相关 fixture 中，用来发现状态容器污染，不单独作为 world-model 创新或第八组性能实验。

### 七个实验怎样连接

| 实验 | 使用的场景 | 接收什么 | 对核心 posterior 的贡献 |
|---|---|---|---|
| E0 | 全部 W/R/Q 的最小 oracle 样例 | 人工 prior、update、posterior | 给 semantic/topology/time 变化建立可信判尺 |
| E1 | W1/W2 | 旧走廊 + 动作 | 产生和纠正 candidate status 与有限 topology expansion |
| E2 | W3 | 相似画面 + 历史拓扑/pose evidence | 决定 append/merge/ambiguous 的拓扑身份 |
| E3 | W4 | 当前候选 + 离散动作后果 | 获取足以决定 posterior transition 的下一证据 |
| E4 | W1/W2 的多步证据版本 | 一个候选 + 连续支持或反证 | 冻结 fact promotion/rejection 与版本生效时刻 |
| E5 | R1–R4/R6 | 已确认旧事实 + 冲突证据 | 直接产生 affected/control/stop + typed versioned revision |
| E6 | Q1 | 同一世界 + 不同 prompt/近期语境 | 证明 read priority 对 world posterior 必须是 zero-delta |

推荐运行依赖不是简单地“堆七个功能”：

```text
E0 工具可信
  ├─ E1 产生和纠正结构候选
  │    ├─ E2 在拓扑解释之间保留歧义
  │    │    └─ E3 主动选择下一条证据
  │    └─ E4 决定候选何时成为事实
  ├─ E5 对已经确认但被反驳的事实做局部修订
  └─ E6 验证任务读取不会越权改写世界
```

E0–E4 为核心 revision 提供可信判尺、可修改先验、拓扑身份和充分证据；E5 是核心机制的直接验证；E6 是写入权限的边界反证。论文不能把七项分别包装成七个创新。

### 3.1 P0 的四级早停验证

| Level | 输入 | 比较 | 早停条件 |
|---|---|---|---|
| V0 evaluator mutation test | 12 smoke fixtures | oracle 与故意错误操作 | evaluator 不能 100% 接受 oracle 或不能击败注入错误 |
| V1 deterministic falsifier | oracle event/fact graph | B0–B7 | incident-edge/local 已与 bounded 在 UP/CP/ST/TV 等价 |
| V2 learnability sanity | symbolic event streams | label prior、flat MLP、Event-Transformer | 256 样本不能 overfit，或模板泄漏 baseline 已饱和 |
| V3 structure/time value | held-out template/OOD | TGN-style、FullGraph-RGT、BEGR-Net | 时间/typed-edge 打乱不掉分，或强 learned baseline 等价 |

只有 V0–V3 都留下待解释差异，才接 AI2-THOR noisy perception；3RScan/Dyn-THOR 只作外部有效性，不参与阈值选择。

## 4. 为什么要和这些简单办法比较

| 对照 | 它怎么做 | 它暴露的问题 | 代码/论文名称 |
|---|---|---|---|
| 固定图像 patch | 每个网格块独立积累特征 | 视角变化时是否错绑或复制节点 | Fixed patch memory |
| 整帧只存一个 latent | 所有区域共同写入一个状态 | 局部变化是否污染无关表面 | Full-frame latent / global EMA |
| 只建对象 slot | 墙、地面、开口不作为更新单位 | 无显著物体的走廊能否扩展 | Object-only slots |
| oracle 结构区域与对应 | 人工给区域及 world-node 绑定 | 表征桥的可达上限 | Oracle region binding |
| 只记录看见的内容 | 不预测未见空间 | 结构先验是否有额外价值 | Observed-only |
| 走一步就加节点 | 不保留候选，直接提交 | 是否产生假走廊和重复节点 | Greedy append |
| 永远采用最可能解释 | 不保留第二候选 | 回环/定位歧义后能否恢复 | Top-1 commit |
| 只按最近 frontier 走 | 只追求覆盖，不考虑关键假设 | 主动取证是否改善决策 | Frontier-only |
| 只改眼前对象 | 不传播关系后果 | 是否漏改推车上的箱子 | Local matched-slot |
| 整张记忆慢慢平均 | 用平滑吸收新观测 | 抗噪能否表达明确世界变化 | Pose-warped global EMA |
| 每次整图重做 | 所有节点关系全部重算 | 是否出现无关修改和高成本 | Full-graph recomputation |
| 人工给出正确范围和动作 | 检查机制上限 | 合同和执行器最多能做到什么 | Oracle |

在线拓扑建图、frontier 或 FARM 风格检索若用于正式比较，必须保证输入、地图粒度和任务接口公平；不能用名称相似代替实验可比性。

## 5. 怎么判断结果好不好

### 5.1 当前帧有没有绑错世界节点

人话检查：

- 同一墙面从远处走近后，是否仍更新同一世界节点；
- 遮挡把一块墙切成两块时，有没有错误复制节点；
- 新门洞是否成为新候选，而不是覆盖旧墙或整张记忆；
- 对应不清时，系统是否先不写长期 latent。

论文指标：association precision/recall、duplicate-node rate、false merge、split/merge recovery、latent contamination、control-node preservation、abstention quality。

### 5.2 猜测有没有冒充事实

人话检查：

- 未观察的走廊是否仍是 candidate；
- 得到证据后能否正确确认或撤销；
- 错误候选是否能恢复，而不是永久污染地图。

论文指标：candidate/confirmed state accuracy、promotion/rejection accuracy、false expansion rate、hypothesis calibration、recovery rate。

### 5.3 地图扩展和回环有没有搞混

人话检查：

- 新走廊段是否正确连接；
- 回到旧位置时有没有重复建图；
- 证据不足时有没有保留多种解释。

论文指标：topology accuracy/graph edit distance、false append、false merge、loop-closure decision、abstention quality。

### 5.4 真实变化有没有改对

人话检查：

- 椅子新旧位置是否正确；
- 箱子随推车变化的必要后果是否齐全；
- 花盆、遮挡后的门和其他无关事实是否不变。

论文指标：target invariant accuracy、required propagation recall、control preservation、collateral revision rate、stop-edge accuracy。

### 5.5 为什么改、为什么走这一步能否追溯

人话检查：

- 候选从哪里来；
- 哪条观测确认或否定了它；
- 旧事实何时关闭；
- 下一动作是在推进任务还是验证哪一组假设。

论文指标：version/provenance validity、transaction integrity、decision explanation coverage。

### 5.6 主动观察是否值得

人话检查：

- 是否用更少步骤排除关键错误解释；
- 是否避免无意义侧看；
- 是否在风险和收益之间做出允许范围内的选择。

论文指标：steps-to-correct-belief、information gain、task success、action cost、collision/risk violations。

### 5.7 任务排序有没有污染持久世界

人话检查：

- prompt 或近期路线改变时，优先木箱是否会正确切换；
- 未被优先选择的实例是否仍保留；
- query 前后 ConfirmedGraph 和版本链是否逐字段相同；
- 应该澄清时是否询问，不需要澄清时是否直接行动。

论文指标：ranking responsiveness、world-belief zero-delta rate、instance preservation、clarification precision/recall、query/action cost。

## 6. Go / No-Go 门

| 想证明的事 | 至少必须看到 | 看不到时怎么办 |
|---|---|---|
| 合同能执行 | E0 全部满足 posterior 与版本不变量 | 修 schema/executor/evaluator，不训练 |
| 观测能稳定绑定世界单元 | E1/E2/E5 的同表面跨视角、遮挡 split/merge 和新区域 case 比 fixed-patch/global-latent 少重复、错绑与污染 | 保留视觉 encoder，但取消结构区域贡献主张，回到更简单表示 |
| 动作预测可被证据纠正 | E1 能拒绝直行、提出左侧候选，并只确认实际可见范围 | 停止结构预测训练，先重写 candidate/confirmed 边界 |
| 重复走廊可管理 | E2 比 greedy/top-1 少 false append/merge，证据不足时能保留多假设 | 收缩 topology/loop claim |
| 主动取证有价值 | E3 比 frontier-only 更低代价地消除任务相关歧义，且不违反安全约束 | 降级为被动 world belief update |
| 候选晋升可校准 | E4 的弱证据保留、充分证据晋升、可靠反证拒绝三者同时成立 | 不训练 promotion head，先冻结或重写证据门 |
| 真实变化修订有价值 | E5 区分搬迁/缺席/遮挡，必要后果不漏且无关修改更少 | 删除或收缩传播、局部修订和 change claim |
| 任务语境不污染世界 | E6 排序可变但两个实例与版本逐字段保持 | 重写 ActiveContext/read-write 隔离，不做查询集成 |

不使用一个漂亮的平均总分绕过任一核心失败。

## 7. 实现顺序

posterior-only 候选顺序（受 HC-018 约束）：

1. 冻结 R1–R4/R6、T1–T4 的输入、acceptable outputs 与 hard failures；
2. 实现 canonical event/fact adapter、事务回放和 evaluator mutation tests；
3. 实现 B0–B7 deterministic baselines，先尝试推翻 bounded claim；
4. 实现 symbolic event generator，并做 group split、hash 与 leakage audit；
5. 实现 L0/L1，再实现 TGN-style、FullGraph-RGT 和 BEGR-Net；
6. validation 冻结温度、commit threshold、checkpoint 与 loss weight；
7. 正式跑 ID/OOD test，最后接 AI2-THOR 与真实重扫数据。

下面既有的完整闭环顺序保留为后续集成合同。

| 顺序 | 人话任务 | 计划代码产物 | 通过条件 |
|---|---|---|---|
| B0 | 建立可复现 Python 环境 | pyproject/lock/test command | 干净环境可运行 |
| B1 | 检查序列输入是否合法 | `contracts/` | 非法 action/version/reference 明确拒绝 |
| B2 | 分开保存事实、候选和历史 | `belief/` | candidate 不进入 confirmed；版本无环 |
| B3 | 表达临时区域、对应候选与允许写入目标 | `observation/`、`association/` | oracle W0 能重放；歧义时不写长期 latent |
| B4 | 实现有限的候选生命周期 | `hypothesis/` | propose/promote/reject 可回放 |
| B5 | 实现确定性 typed update | `revision/` | oracle update 产生正确 posterior |
| B6 | 重放 W/R/Q 序列 | `tests/fixtures/` | 每一步结果可自动检查 |
| B7 | 分开统计绑定、扩图、回环、修订和污染 | `evaluation/` | 人工错误使对应指标恶化 |
| B8 | 用规则产生候选、吸收证据和选择动作 | `prediction/`、`planning/` | 可运行、可解释、可消融 |
| B9 | 保存配置、结果和失败 | runner/manifest | 任一数字可追溯 |

依赖顺序：B0 → B1 → B2/B3/B4 → B5 → B6/B7 → B8 → B9。

计划目录：

```text
src/embodied_spatial_memory/
├─ contracts/
├─ belief/
├─ observation/
├─ association/
├─ hypothesis/
├─ prediction/
├─ assimilation/
├─ revision/
├─ planning/
├─ context/
├─ baselines/
└─ evaluation/
```

## 8. 系统允许的有限状态操作

### HypothesisSet

| 操作 | 人话 |
|---|---|
| PROPOSE | 新建带来源、置信度和待验证条件的候选 |
| PROMOTE | 证据满足规则后，把候选提升为 confirmed fact |
| REJECT | 证据否定候选，保留被否定原因和版本 |
| RETAIN | 证据不足，继续保留一个或多个候选 |

### ConfirmedGraph

| 操作 | 人话 |
|---|---|
| REINFORCE | 新证据再次确认旧事实 |
| ADD | 新增已经满足确认条件的对象或关系 |
| UPDATE_STATE | 更新运动、可见性等状态 |
| RELINK | 从旧连接迁移到有证据的新连接 |
| INVALIDATE | 让被可靠反驳的旧事实失效 |
| SUPERSEDE | 用新版本取代旧版本并保留历史 |
| PRESERVE | 明确保留旧事实 |
| QUARANTINE | 身份或证据不清时暂不提交 |

整组操作任一项非法时整组拒绝，不能只提交一半。

## 9. 每次运行必须保存

```text
outputs/<run_id>/
├─ config.yaml
├─ environment.json
├─ dataset_manifest.json
├─ sequence_predictions/
├─ association_records/
├─ hypothesis_transitions/
├─ belief_updates/
├─ action_decisions/
├─ metrics_per_sequence.jsonl
├─ aggregate_metrics.json
├─ failures/
└─ run.log
```

正式运行还必须保存随机种子、数据版本、split hash、代码版本和模型标识。

## 10. 通过后怎样逐层增加难度

“增加难度”优先增加证据延迟、来源冲突、dependency depth、graph size 和上游噪声；不优先增加 loss 数量或同时训练更多模块。

```text
人工给出 prior、evidence path、posterior 和 next action
  ↓
规则系统自己产生候选并吸收证据
  ↓
学习结构预测与 hypothesis calibration
  ↓
学习 association、revision scope 和 stop
  ↓
学习离散主动取证
  ↓
最后接入真实 pose、depth、detector 和较长规划
```

每次只移除一类 oracle，失败后才能知道问题出在预测、定位、证据吸收、修订还是动作选择。

## 11. 真正运行前必须由研究者确认

唯一清单和完整映射见 [`DECISIONS.md` 的“人工确认中心”](DECISIONS.md)，当前为 HC-001–HC-018；详细场景与判题选项见 [`human_confirmation/`](human_confirmation/README.md)。

本文件不复制问题内容。确认前，micro-sequence 只能用于讨论设计，不能称为训练 ground truth；运行 manifest 必须记录实际采用的 HC/D decision IDs。

## 12. 研究诚信边界

- Pilot 只检查机制，不作为最终论文数字；
- 当前全部能力仍是未实现、未验证；
- 模拟器 world state 可以称 oracle，但自动映射或模型评审不能自动称 ground truth；
- 不使用 test 调阈值、动作权重、提示、baseline 或 checkpoint；
- false append、false merge、漏改、多改、风险动作和反例必须保存并报告。

通过本协议后，才进入 [`04_training_plan.md`](04_training_plan.md)。
