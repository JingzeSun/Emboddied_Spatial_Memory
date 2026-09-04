# v0.7 动态空间语境修订汇报讲稿（旧方向）

> 用途：帮助第一次汇报时解释 PPT 术语、场景 WBS 和实验路线。
>
> 状态：`pre-D017 presentation aid / superseded`。本文件只用于回看旧版术语演化，不再代表当前世界模型主线；现行边界以 `EXECUTE.md`、`docs/01–05` 和 `docs/DECISIONS.md` 为准。

## 1. 先背这一段 30 秒主线

现有工作已经能在线建对象图、跟踪动态对象、选择性读取记忆，也能通过空间关系找同类实例。但当一条可靠新证据和旧世界信念冲突时，仍需要明确回答：旧图到底改什么、哪些关系必须跟着变、哪些无关事实不能动、传播到哪里停止，以及旧版本怎样保留。我的设想是把新旧差异先分型，再生成受影响范围受控的 typed delta，最后由确定性的版本化执行器改图。

如果导师只问“你的创新是什么”，先说：

> 不是再造一种空间记忆，而是研究一条受控的 world-belief write path：typed edit、necessary propagation、stop boundary 和 version provenance 的联合预测与评测。

## 2. 名词怎么回答

回答顺序固定为：**它回答什么问题 → 举什么场景 → 怎样判错**。

| 名词 | 人话定义 | 场景 | 怎样判错 |
|---|---|---|---|
| Pose / geometry | 把相机里看到的位置换算成同一个世界坐标 | 转身后仍能判断是不是先前那把椅子 | 投影位置明显不一致或 reference frame 不明 |
| Dynamic state | 对象当前状态与过去是否不同 | 椅子 A→B、门 closed→open | 把遮挡误写成移动，或漏掉可靠变化 |
| Typed edit | 修改动作必须有固定语义，不用“更新一下”这种自由文本 | ADD、SUPERSEDE、INVALIDATE、PRESERVE、RELINK | executor 接受非法参数或不同动作语义混用 |
| Structured Innovation | 将“预期应该看到什么”和“实际看到什么”的差异分型 | 新对象、搬迁、可靠缺席、遮挡、身份歧义 | R3 可靠空缺与 R4 遮挡输出同一种类型 |
| Affected scope | 这次变化必须修改的节点和边集合 | 推车移动时处理位置及依赖关系 | 必要边漏改，scope recall 下降 |
| Control set | 与本次变化无关、必须保持的节点和边 | 椅子搬迁时台灯、植物不变 | 无关图被修改，collateral revision 上升 |
| Propagation | 状态变化沿有依据的依赖关系产生必要后果 | 推车支撑箱子，推车移动可能影响箱子的位置关系 | local-slot 只改推车，漏掉箱子后果 |
| Stop boundary | 没有依据继续传播时必须停止的边 | 不能沿 room contains 改写全屋对象 | full-graph 式越界修改无关节点 |
| Version chain | 保存事实何时成立、何时失效、被什么替换 | chair@A 在 t1 关闭，chair@B 在 t1 开启 | 历史被原地覆盖、出现环或时间区间冲突 |
| Provenance | 每次修改引用产生它的观测、pose、置信度和代码版本 | 可以追问“为什么认为椅子搬了” | 结果无法回到证据帧或运行配置 |
| Oracle | 初步实验中由人工提供正确中间答案 | 人工给正确 identity、visibility、scope | 不代表最终模型拥有这些真值 |
| Vertical slice | 从输入合同到执行、判分的最小完整链路 | 一个 R1 fixture 能被完整重放 | 只有单个模块，没有端到端可判分输出 |

## 3. 四个状态容器

### ObservationGraph：这一刻看到了什么

只放当前帧或短窗口的 pose-aligned evidence。没看到某物只说明当前证据缺失，不自动说明世界里不存在。

### SceneBelief：现在相信世界是什么样

保存当前世界假设、置信度与版本。可靠搬迁会改变这里；遮挡通常只改 visibility，不直接关闭旧位置。

### ActiveContext：这次任务优先考虑什么

只改变候选排序或是否需要澄清，不修改世界事实。两个木箱场景中，右转后看到的 box_B 可以排序更高，但 box_A 不能因此被删除。

### PersistentWorldMemory：长期保留什么

保存巩固事实和历史版本，使系统能回答“现在在哪里”和“以前在哪里”。

一句区分：

> 当前帧证据进 ObservationGraph；可靠世界变化进 SceneBelief；任务偏好进 ActiveContext；稳定历史归档进 PersistentWorldMemory。

## 4. WBS 到底做什么

WBS 是 Work Breakdown Structure，即把一个无法直接实验的大概念拆成可交付的小任务。在这里，一个小任务叫 fixture。

你现在对每个场景人工完成六件事：

1. `base_belief.json`：画变化发生前的旧世界图；
2. `observation_graph.json`：写当前观察到的证据、pose 与 visibility；
3. `oracle_delta.json`：人工圈出 affected、control、stop，并写 typed operations；
4. `expected_belief.json`：画执行后正确的新世界图和版本；
5. `metadata.yaml`：记录场景 ID、唯一变量、claim 和反证条件；
6. `README.md`：解释为什么这是正确答案，以及哪个结果会推翻假设。

随后再复制一个场景，只改一个因素作为 counterfactual。例如 R3 与 R4 的旧图完全相同，只把“旧址可靠可见且为空”换成“旧址被遮挡”，正确操作就必须从 `INVALIDATE` 变为 `PRESERVE`。

当前阶段不做：采大规模视频、训练网络、接 detector、跑导航。先让人工标准答案无歧义。

## 5. R1 椅子搬迁完整口头讲法

1. 旧图 v0 中，`chair_1 located_in zone_A`；另放 `table_1` 与 `plant_1` 当无关对照。
2. 新帧通过 pose 对齐后，在 zone_B 看到与 `chair_1` 高置信匹配的椅子；zone_A 也可靠可见且为空。
3. 这不是首次发现新对象，而是同一对象的 relocation，因此属于 `belief_revision`。
4. `oracle_delta` 关闭 `chair_1@A` 的有效区间，开启 `chair_1@B`，保留 identity。
5. table、plant 和无关关系必须完全不变；传播在无依赖边停止。
6. 新图 v1 表示椅子当前在 B，但仍能追溯过去在 A。
7. 反事实只改 identity：如果 B 中是另一把椅子 `chair_2`，正确操作变成 ADD，而不是关闭 `chair_1@A`。

这个 fixture 同时测四件事：目标修改是否正确、版本是否正确、必要操作是否漏掉、无关事实是否被误改。

## 6. 六个 P0 与两个边界场景各测什么

| 场景 | 唯一变量 | 真正检验 |
|---|---|---|
| R1 椅子搬迁 | identity continuation | ADD 还是 SUPERSEDE；版本链 |
| R2 推车—箱子 | dependency edge | 必要关系传播与停止 |
| R3 可靠缺席 | reliable visibility | 旧位置失效、新位置 unknown |
| R4 遮挡对照 | occluder | PRESERVE 与 visibility update |
| R5 人长期站立 | stationary duration | motion state 不改变 actor ontology |
| R6 无关变化 | relevance/dependency path | control preservation 与 stop |
| X1 转弯见新区域 | never observed | graph expansion 与 attachment，不冒充 revision |
| X2 两个木箱 | route/dialogue context | ActiveContext 排序/澄清，不污染 world belief |

## 7. Oracle pilot 怎么解释

Oracle pilot 不是“使用一个很强的模型”，而是暂时由研究者提供正确中间变量。它的目的，是先验证问题与执行机制是否成立。

```text
人工给正确 pose / visibility / identity / delta / scope
  → deterministic executor
  → expected graph
  → evaluator 判分
```

若 oracle delta 都无法得到正确版本，说明 schema、operator 或场景定义有问题；这时训练网络只会把机制错误藏起来。

## 8. 常见追问短答案

### 这不就是抗噪声吗？

抗噪只决定信不信。我们还要决定信了以后改哪个事实、哪些关系跟着变、哪些事实必须保持、在哪里停止。

### Affected scope 不就是 attention 吗？

attention 是读取权重；affected scope 是写权限。attention 高不代表有权修改世界事实，修改必须经过 typed executor。

### FARM 已经能通过关系找对象，你还有什么？

FARM 主要解决 query-time relational retrieval。我们的 P0 问题是新证据反证旧 belief 后怎样执行版本化局部修订。FARM 可作为对象记忆与 X2 检索接口，不是 P0 的同一任务。

### 为什么需要 control set？

只看“该改的改对了”会允许全图重算。control set 用来证明方法没有顺手改坏无关世界事实。

### WBS 写完就证明创新成立了吗？

没有。WBS 只证明概念能变成无歧义测试。方法成立至少还要通过 executor、oracle pilot、学习模型验证和冻结正式测试。

### 你现在做到哪一步？

研究合同和文献边界已整理；fixture、executor 和实验尚未实现，因此只能说 `we formulate / propose to evaluate`。

## 9. 汇报时避免的说法

- 不说“我们的方法已经有效”；改说“计划检验的机制是……”；
- 不说“首次做动态记忆”；改说“现有动态记忆未显式联合评测……”；
- 不说“attention 选中哪里就改哪里”；改说“attention 只可作特征，写操作受 typed contract 约束”；
- 不把 FARM 的预印本结果说成同行评审共识；
- 不把 oracle 输入说成模型能力或 ground truth 感知。
