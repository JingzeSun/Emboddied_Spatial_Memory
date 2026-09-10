# 数据先行的 M1 重构与 M2 验证计划（保留 M1-v7 历史流程）

本文件沿用 D-035 批准的固定文件名，按 D-059 扩展为用户要求的完整分步计划书，并保留 M1-v7 历史流程。它是阶段顺序、当前指针、审查节点和转向条件的唯一维护处；具体方法分别进入数据/表征/实验合同，实验结果仍只进入 EXECUTE。输入是真实数据审查和逐阶段交付，输出是下一项可检查的任务。例如原始视频不能区分移动与遮挡时，先标明不可判断，而不是先写一个保证存在正确 RELINK 的生成器。本计划不等于各模块已经实现，也不是所有后续实验已经冻结。

## 从数据到论文的分步计划（D-059）

**计划日期：2026-09-11。状态：方向与分步规划已获用户授权；以下新模块、检查和实验均为 planned，除非 EXECUTE 后续提供实际实现或运行证据。当前只交付计划，不开始科学代码重构或训练。**

### 目标、阶段含义与交付终点

目标仍是 Counterfactual Projective Memory Transactions（CPMT，反事实投影记忆事务）中的 Counterfactual Transaction Learning（CTL，反事实事务学习）：检验执行候选修订后形成的事后监督，能否比直接未来损失更可靠地学习在线记忆修订。白话：输入是旧记忆和新到达的观测，输出是修订后的记忆；例如椅子换了位置，系统应更新位置且保留无关桌子的记忆。这不是预设 CTL 胜出，也不是训练一个新的视觉基础模型。

执行顺序改为：**公开数据审查 → 观测/记忆合同 → 重构 M1 → M1 小试与独立检验 → M2 自身记忆连续运行 → M3 独立来源 → 论文与复现交付**。先接触 M2 类型的数据不等于已经完成 M2。原 M1-v7/S5 的 no-go、已有数据和检查点保留；新 M1 使用新协议和新来源绑定，不把旧失败改名为通过。

| 层次 | 输入、输出与作用 | 不能混称什么 |
|---|---|---|
| 工程夹具 | 人工指定少量世界和事务，输出执行结果及手算断言；例如撤回错边应留下旧版本 | 测试执行器，不证明从视觉学会修订 |
| 重构 M1 的受控实验 | 使用审查后的观测接口；在明确的旧记忆状态和修订机会下比较监督机制，输出分层误差；例如把已观测证据误分配给两个节点，检查 MERGE 的机会及学习 | 受控造错不等于真实系统自然错误频率；不再用答案 ID 生成观测 |
| M2 自身记忆连续运行 | 冻结前端逐帧/逐次重访产生观测，模型承受自己的历史提交，输出完整轨迹；例如前次误建节点影响下次重访 | 不用每步参考世界复位；扫描间空档不冒充被观察到的连续动作 |
| M3 独立来源验证 | 冻结方法应用到未参与开发的另一来源，输出迁移表现及失败 | 不把同源场所的另一段视频叫独立外部验证 |

重构 M1 不预先固定为“真实 latent 加人工标签”或“重新造一套合成题”。先由步骤 05–10 确定真实证据能支持哪些问题。传感器观测是主要依据；额外模拟噪声、错误状态注入或 oracle 辅助条件若需要，分别登记并单独报告，不混入自然发生的表现。

最终交付包括：已审查的数据字段与 split；可逐模块阅读的实现；服务器测试和 run 回执；A–E 与 oracle 的逐例比较；M1/M2/M3 各自支持和不支持的主张；能从配置和 manifest 重建报告的 artifact。任何阶段失败，都交付该阶段的定位证据和范围结论，不以“跑完所有阶段”为成功标准。

### 你的代码审查方式

每一批科学代码先在独立分支形成一个可阅读的提交，再交你审查。允许先运行该改动必要的服务器工程测试来提供证据；**在你审过当前批次之前，不合并为新阶段科学基线、不运行依赖它的效果实验、不继续堆叠下一批科学模块。** 文档整理、只读核查和当前批次必要修复可继续。批准记录注明 commit；之后改变科学行为须重新展示差异，不能让旧批准覆盖新行为。

每批审查材料直接写在提交/PR 描述及已有合同中，不额外创建交接或状态文档，固定包含：

1. 一个具体输入例子、预期输出，以及本改动解决的问题。
2. 文件清单、入口函数、调用顺序、允许读取的字段与实际写入范围。
3. 核心实现的可读差异；源码解释“为什么”，不只把代码逐句翻译。
4. 正例、负例、歧义例；哪些是手算真值，哪些仅是模型/教师判断。
5. 必要测试的实际结果、源码/配置 hash；未运行的检查明确标 pending。
6. 与旧实现的兼容性和退回方式；未解决的限制，以及依赖步骤是什么。

科学批次尽量只改一个职责；超过约 300 行核心逻辑时优先再拆分，这是审查粒度建议，不是用大量小文件凑行数。纯注释/格式/运维修复不和损失、候选或评测改变混成一个提交。你可以指定逐函数审查；读代码不要求你自行从大日志中寻找证据。

以下 R1–R7 是正式审查节点，不要求每条成功命令后再次确认。到节点时提供完整、可审的具体交付，再等待你的审查；未完成交付前不让你批准抽象方向。

### 阶段 A：先看到数据，步骤 01–05

输入前提：服务器尚无公开数据；3RScan 是优先考察来源，未视为正式选定。输出是原始样本、数据来源表和人工审查案例。此阶段不写学习器、不比较 CTL 输赢。

| 步骤 | 具体工作 | 交付和验收 |
|---|---|---|
| 01 保存旧基线并列出待替换路径 | 登记旧源代码提交、配置及现有报告；只读列出 reference→query→候选→编码→教师的调用链，区分可复用执行基础与旧实验专用逻辑 | 旧基线可定位；不移动、删除服务器 outputs，不重写历史 source hash；形成旧/新职责对照 |
| 02 获得数据访问并登记首批清单 | 用户通过官方条款取得访问方式；助手根据实际元数据选一个官方训练场所及关联重访，先定具体 scan ID 和文件类型再下载 | manifest 记录版本、来源、用途、字节数/hash、关联关系；无法取得某文件记缺失，不自动换场所 |
| 03 检查原始 RGB-D 与坐标 | 读取图像、深度单位、相机内外参、帧序、缺帧、跨扫描变换；把深度回投再投回图像，并显示叠图 | 原始帧、深度叠图、坐标约定和异常清单；数值容差在实现前按数据精度登记，不能只看“文件可打开” |
| 04 做可由人判断的案例卡 | 先按固定均匀帧位置浏览，再在开发样本中记录重见、首次揭示、位置变化、遮挡/空位和身份歧义；每卡显示当时可见信息、后续证据和单独标注 | 每卡可追溯到 scan/frame；分别填写“能判断/不能判断/标注与画面冲突”，不把缺标注当消失，不把人工挑选案例当代表性发生率 |
| 05 审查数据是否适合问题 | 检查首场所后，按事先登记的元数据排序补看至多另外三个训练场所，不按模型效果筛选；列出每类事件证据、缺失和场所变化 | **R1：你审原始案例和字段来源。** 决定正式候选来源、受控辅助条件和不能声称的能力；若需别的来源，先给出此来源缺少什么证据，登记后另选 |

首批一个场所用于理解格式，后续少量场所用于避免只依据一个房间设计；这些数量是检查上限建议，不是正式统计样本量。已看过的全部场所进入开发清单，之后不得进入未见确认或 test。3RScan 官方提供标定 RGB-D、相机位姿、跨扫描对齐和对象对应；跨扫描对象对应属于审计信息，固定 pose 使用参考对齐时须声明该受控条件。数据获取与字段依据：[官方获取入口](https://waldjohannau.github.io/RIO/)、[官方格式](https://github.com/WaldJohannaU/3RScan)（2026-09-11 核查）。

### 阶段 B：由数据定义新 M1，步骤 06–10

输入前提：R1 审过的数据案例。输出是可执行合同草案及新实验的可回答问题。这里允许彻底改变旧 M1 的 family、观测维度、候选预算、参考标签方式和连续长度，但每一项改变要解释数据依据，不能为了保留旧代码而硬套旧结构。

| 步骤 | 具体工作 | 交付和验收 |
|---|---|---|
| 06 画清信息来源 | 对每个字段列出原始来源、时间范围、生成函数、使用方；在线观测、旧记忆、教师未来证据、审计真值分开 | 允许字段表和一帧 JSON 示例；包括 ID 哈希、真值颜色、全场景网格、未来平滑 pose、候选排序、保护 mask 等间接通道 |
| 07 定义旧 latent 与修订语义 | 确定节点表示、几何、证据归属、生命周期和版本；逐事务写 before/after，区分仅改引用、改几何、改描述向量 | 一次 BIND/RELINK/REPLACE/SPLIT/MERGE 的可读例子；新观测不默认新实体；不允许先把观测融合进旧向量再决定身份 |
| 08 定义可判断答案和评价 | 区分身份/位置语义正确、证据归属正确、历史完整、索引一致；定义未知区和多个有效候选，审计身份映射不进入在线模型 | 手工小例子能算出指标；不能仅因 active graph 相同就认定 provenance 等价，也不能因内部 ID 名称不同便算世界错 |
| 09 确定受控 M1 的题目 | 从真实观测接口抽取受控案例；旧记忆原则上由此前观测形成。必要的误合并、重复节点或错边注入只改变明确登记的状态，不造当前答案提示 | 每种错误的注入位置、操作、选样规则、可修复性与目标可辨识性；自然错误、受控造错、纯工程夹具分开 |
| 10 固定新协议边界 | 明确 split 的场所/关联扫描分组，前端选择用的数据，候选机会、公平条件、主要指标与科学问题；列出仍待测速确定的预算参数 | **R2：你审合同及旧/新 M1 对照。** 批准后才实施；旧 S5 门不追改，新 M1 正式门须在独立确认效果比较前论证和冻结，不能按小试中 CTL 的效应大小设门 |

白话：本阶段把“给模型出什么题”变成你能审查的对象。输入是一组实际观测，输出是旧记忆、允许的证据和评价规则。例如当前画面无法区分两把同款椅子，应保留歧义，不能读取跨帧真值编号给模型暗示；这不等于删除困难样本。缺少自然 SPLIT/MERGE/RETRACT 事件时，可保留明确标为受控压力测试的可执行正例，不声称它们是现实发生频率。

### 阶段 C：先实现数据与世界，步骤 11–15

每个步骤各交一个科学审查批次；优先隔离旧实验入口而非原地覆盖。新目录名暂建议 `src/cpmt/observation_memory/`，只是职责建议，R2 时依据仓库结构最终决定，不要求为了命名迁移现有 executor。

| 步骤 | 具体工作与拟议代码职责 | 验收与失败处理 |
|---|---|---|
| 11 数据适配器 | reader/observation schema 只读取批准的原始字段，校验坐标、时间和缺失；audit reader 独立 | 删除标注文件后在线适配仍能运行；schema 未知字段拒绝而非静默带入；导出可回到原始帧 |
| 12 冻结前端与缓存 | 一个先选定的固定区域提议及视觉 checkpoint 产生区域特征，保留几何和可靠性；先少量帧测速再处理已登记开发样本 | 缓存绑定权重、预处理、区域、pose/depth 来源；完整序列缓存与逐前缀结果比较。后处理若用了未来，归入特权条件或修复，不假称严格在线 |
| 13 节点表示与投影 | 实现从过去已归属证据形成的固定/轻量节点表示、按 pose 投影以及可见性处理；把数值表示写入作为版本操作的一部分 | 手算几何例子、换视角例子、无证据区域输出未知；保存/加载一致，错误绑定影响能定位到证据。拟议均值基线与投影表示分开，不能把缓存均值冒称 PNO |
| 14 执行器适配 | 审核 `executor.py` 对新几何/证据/表示的支持；必要时增加新 schema 版本，保证克隆、前置条件、原子回滚、幂等性、保护和 provenance | 候选顺序改变不污染 base；SPLIT/MERGE 的证据与表示一致；RETRACT 关闭版本；失败不半写入。旧调用默认行为及关键历史回归保留 |
| 15 确定性候选构造 | 用当前合法观测和自身旧记忆产生事务与角色参数，允许相似度和几何证据，禁止引用正确事务/目标 ID；明确预算、排序、重复和不可用槽位 | ID 重命名对应、候选置换、上游标注干预、正确/错误记忆两种覆盖检查；去重若执行了分支须披露，不假称纯静态生成 |

**R3：你审一帧如何变成观测、一个节点如何形成、每个候选怎样修改它。** 交付至少一条从原始帧到 before/after 的完整可追溯例子，以及不会修改无关节点的负例。此时还没有学习效果结论。

数值 latent 的不可变性必须覆盖实际数组/张量内容，而不只覆盖 JSON 中的引用：候选之间不能共享可写缓冲区，缓存引用须绑定内容 hash，修改一个候选不得改变旧版本或其他候选。错误绑定撤回、SPLIT/MERGE 后的表示必须按已登记的证据重分配/重计算规则形成；不能把不可逆地混过的向量保留下来，却仅因图边修好便宣称旧 latent 已恢复。

Projective Node Orbit（PNO，投影节点轨道）在此是固定/轻量表征基础：输入是世界节点和视角，输出该视角可比较的预测观测；例如同一椅子的侧面证据应与同一节点兼容。它不是要求从单次观测幻想完整背面，更不是 CTL 之外新增端到端大模型。不可见/未建模表面须保留未知，不能被“没预测到”自动当作反证。

### 阶段 D：教师、对照与独立评测，步骤 16–20

输入前提：R3 批准的观测/记忆/候选。输出是不用训练就能核查的监督计算与评测模块。

| 步骤 | 具体工作 | 验收与失败处理 |
|---|---|---|
| 16 独立评测器 | 先实现 R2 的评价例子；语义事实、证据归属、历史完整、可判断范围分别计分。评测器独立读取审计真值，不复用教师总能量当正确性 | 人工计算的正/错/等价/未知例子与输出吻合；错误事实数量、恢复分母、持续时间可逐项复算 |
| 17 执行后教师 | 所有候选从同一 base 真执行；分别记录 now/future/edit/growth/collateral/illegal。未来评价来自允许的后续观测；对应/推进规则不读取正确身份或正确事务 | 逐候选展示 post-world、六项分数和后验；至少有需要后续证据、无关未来证据、当前仍歧义三种例子。未来窗口内物体再次变化须按合同处理，不能用错误的静态假设评分 |
| 18 接入 A–E 公平对照 | 学生共享输入、候选、可用性和骨干；B 直接标签、C 直接未来辅助损失、D 当前执行监督、E 无执行未来评分、A 执行后事后监督分别实现 | 逐方法列实际读取张量、标签数量、教师目标来源、参数与总成本；C/E 不读候选 post-world 生成目标，使用同等可用未来观测和合理容量 |
| 19 端到端信息与标签审计 | 从原始文件重新生成，改变审计标注/ID、未来、候选次序和元数据；检查在线特征和候选是否依规不变。另检查训练目标是否错误惩罚多个有效候选 | 若多候选在登记评价上等价，标签集合及 CE 目标规则先修正再训练；类别对但参数错单列。只对编码后输入置零不能替代来源审计 |
| 20 完整工程链验收 | 用少量开发夹具运行缓存→候选→教师→数组→固定策略逐步执行→保存/加载→报告导出，核对三方世界 hash | **R4：你审教师分数、C/E 实现和评测器源码。** 完整服务器证据通过后才允许效果训练；测试通过只证明实现符合已审合同 |

白话：这一步检验“监督为什么认为某次修订好”。输入是同一旧世界的不同执行结果和后续观测，输出是可复算的监督分布；例如后来旧位置确实可见且为空，会削弱“原物体仍在原位”的解释。它不等于把数据集正确对象 ID 直接喂给教师，也不等于教师评分最高就是真实世界正确。

训练若允许少量人工事务标签，所有方法按同一标注预算、分组和可辨识规则使用；不把“有相同标签文件”当成监督量一定公平。E 额外 scorer 训练成本单列；A 的执行成本与 C 的辅助目标成本也列出。F 为独立审计 oracle 上界，仅用于诊断可达到的答案，不作为可部署方法；无法判定的案例不强行赋唯一参考索引。

另外登记两项便宜的诊断：只使用合法检索分数的固定最近邻规则、只使用候选槽位/顺序的规则，量化候选构造本身已经决定了多少答案；它们只作捷径诊断，不替代 A–E。若要比较某组特征的贡献，训练和评测必须在相同保留/移除条件下进行；只在推理时置零造成的性能下降不能直接解释成泄漏。候选打乱后的评价应同步重映射标签和审计索引。

### 阶段 E：小规模学习与机制诊断，步骤 21–24

输入前提：R4 通过；只能使用已经登记的开发数据。输出是一个固定小预算下的完整比较，而非正式成功结论。

| 步骤 | 具体工作 | 验收与失败处理 |
|---|---|---|
| 21 测速并冻结小试配置 | 先测特征缓存、分支执行、教师生成、学生更新、E scorer、逐步执行和导出的实际成本；据此登记数据组数、更新数、batch、horizon、K 和存储上限 | 给出预计耗时区间及依据；小试建议 seed 7/19，A–E 都接入，先通过可辨识工程样本的链路检查。具体更新数不照搬旧 300/3000；开跑前配置完整且经你审阅 |
| 22 检查学习器是否学得到 | 在预先登记的少量可辨识训练窗口上检查 loss、梯度和训练误差；给出当前信息相同却答案不同的例子作为对照 | 这是拟合诊断，不是泛化成绩。若连确定性小样本都拟合不了，定位优化/标签/输入，再修当前批次；不先扩全部模型 |
| 23 固定小试及学习曲线 | 同一分组与预登记预算运行 A–E，两 seed 全部导出；在同一次训练的固定检查点报告训练/开发曲线，不挑最好 seed | 不能把不同数据或编码的曲线拼成大小预算对照。训练下降而开发恶化才支持过拟合诊断；同时饱和、都拟合差、差距缩小分别解释 |
| 24 逐例分解失败并裁定 | 分开 candidate miss、teacher error、student selection error，以及出错后的完整/部分/无修复机会；比较正确/错误状态和自然/注入错误 | **R5：你审完整小试和失败轨迹。** 决定继续、只修一项具体机制或停止；修订形成新开发版本，不覆盖失败 run，不把改善 family 单独当整体收益 |

白话：这轮小试解决“系统能学吗，误差到底在谁那里”。输入是固定开发组和共享计算条件，输出是所有方法、所有 seed 的结果与失败；例如正确候选不存在时记候选缺失，存在却教师排错时记教师错误。这不是每轮加一批训练直到 CTL 赢，也不能用两个 seed 作正式统计保证。

风险损失、复杂历史训练、额外配对模块或更大评分器不设为必做项。只有步骤 24 的具体证据支持时再提出一个变化、数学目标、预期改善和副作用，保持 A–E 输入/预算可比较；一次不要同时换数据、表示、损失和容量。需要自身状态训练时，只在训练数据采样并保留统一生成规则，不能消费开发/确认轨迹作训练样本。

### 阶段 F：新 M1 独立检验，步骤 25–27

| 步骤 | 具体工作 | 交付和继续条件 |
|---|---|---|
| 25 冻结正式研究问题 | 依据开发阶段确定最小有意义效应、主指标/安全指标、A−C 与 A−E 主比较、候选覆盖、未知处理及允许调参预算；独立场所为统计单位 | 新配置/hash、样本量论证、固定 seed 数和预算。不能沿用旧 40/80 数值而不论证，也不能以已经观察到的 CTL 效应倒推一个容易通过的门 |
| 26 一次独立确认 | 用未参与数据审查、前端选择和算法开发的场所确认固定方案；候选与初始状态条件各方法共享 | 按场所配对并处理多重比较，不把帧数、窗口数或 learner seeds 当独立场所。预先规定失败/不确定的结束分支；确认集不用于改完继续考 |
| 27 收口重构 M1 | 给出工程完整性、候选/教师/学习误差、两主对比及预算敏感性；若保留最终 test，则在新协议中先声明其唯一使用规则 | **R6：你审科学结论及 M2 准入。** 新 M1 不支持机制时先停止扩大效果运行，交付负结果；若用户另选探索方向，明确新决定，不自动用 M2 挽救同一检验 |

步骤 25 内的训练顺序也须固定：先登记各方法允许的有限超参数/计算预算及同一开发选择准则；再仅在拟合/开发组完成该网格；随后锁定每个方法配置，在声明的完整训练部分重训并保存/加载校验；最后才执行步骤 26 的独立确认。各方法可在公平预算内有不同最优超参数，不把“强制同一个学习率”当充分公平。保存全部 trial，不选最好 seed；未完成网格或回执不一致时不得打开确认集。没有必要扩大网格时可直接冻结小试配置，但须在确认前明确该选择。

新独立确认不复用已看过的 M1-v7/S5 或本计划开发场所。严格区分“来源/样本未重叠”和“生成机制/资产未重叠”；冻结视觉模型的预训练来源也应披露已知情况，无法验证的重叠不能写成已排除。若数据规模无法支持预期统计结论，缩小主张或报告不确定，不用海量相邻帧制造窄置信区间。

在步骤 10/25 登记的数据角色必须区分：已看过的案例发现集、拟合组、开发选型组、M1 独立确认组、M2 独立确认组，以及 M3 独立来源。M1/M2 若确需在同一批未见场所做配对的受控/自然条件比较，须在任一结果揭示前同时冻结两套评价，并明确它们不是两份独立泛化证据；否则 M1 看过的确认场所不能再作为后来改动 M2 的未见测试。关联扫描和同步录制同组，不以 learner seed 制造新的数据独立性。

### 阶段 G：M2 与 M3，步骤 28–30

| 步骤 | 具体工作 | 交付和继续条件 |
|---|---|---|
| 28 M2 自身记忆完整序列 | 在批准的冻结协议下从空记忆或声明的因果 warm-up 开始；不按参考图逐步复位、不注入受控错误，完整记录所有实际失败和后续修订 | 自然连续轨迹、错误持续负担、证据污染、节点增长和完整系统成本。若使用 3RScan，明确扫描内顺序及跨扫描重访，不声称连续观察到搬运 |
| 29 必要机制与表征对照 | 在事先留出的开发部分确定有限消融，再独立验证；候选包括当前/未来教师、固定均值表示/PNO、几何/可见性信息和等预算比较 | 每项只回答一个问题。例如去掉 future 后不变，便收窄未来证据主张；均值和 PNO 的输入/候选机会可比。表征改动引起候选变化时单列覆盖贡献 |
| 30 M3 独立来源 | 先审另一来源的字段和许可，再按冻结适配原则接入；源数据不参与原方法选择，明确零调参迁移或单独受控适配 | **R7：你审 M2/M3 的完整结果与外部验证隔离。** 如需目标域监督/调参，另留未见目标域数据并报告成本，不冒称零样本迁移 |

白话：M2 检查系统连续犯错后还能不能维护世界，M3 检查换来源后是否仍成立。输入是真实顺序观测及自身旧记忆，输出是整个过程和外部表现；例如初次误绑定后，后来的视角是否修正且没有破坏桌子。这两项不等于控制相同观测的 M1，也不自动授权主动导航、动作策略、第二应用领域或更大基础模型。

### 阶段 H：论文与可复现交付，步骤 31–32

| 步骤 | 具体工作 | 完成定义 |
|---|---|---|
| 31 审核主张与证据 | 逐句对应 M1/M2/M3 的实际实验；公开旧 M1 负结果及事后改协议的时间线，区分自然证据、受控造错和特权条件 | 每个结论有对应结果路径、来源、分母和限制；不把 executor、KL 或事务标签单独当创新，不把更好表征的收益全归 CTL |
| 32 独立复算并交付 artifact | 从冻结 manifest/config 和导出逐例记录重算主表；干净服务器环境验证安装、最小样例、续跑/失败处理、保存加载和报告生成 | 论文、配置、权重/获取方式、版本、数据许可、逐例失败、运行命令与成本齐全；受限原始数据不擅自再分发。你审最终源码与报告，明确完成/未支持/未完成项 |

### 核心文件如何拆分给你审

以下为职责映射和拟议改动，具体新文件名在 R2 固定；不先制造空模块或 wrapper。

| 阅读顺序 | 现有代码/合同 | 新工作及主要审查问题 |
|---|---|---|
| 1 原始输入 | DATASETS.md、M2_DESIGN.md；现有 visual_pilot.py 仅作局部工程参考 | 数据 reader 和字段来源：是否偷偷读了实例标注、全场景 mesh 或未来处理结果？ |
| 2 旧记忆表示 | REPRESENTATION.md、executor.py | 哪些数值属于节点，哪些属于一次观测？错误绑定能否定位/修订证据，旧版本是否仍可追溯？ |
| 3 候选 | m1_rollout.py、m1_candidate_policy.py | 旧 reference→query 链不复用；正确候选和修复候选怎样出现，出现率是否依赖答案？ |
| 4 教师 | m1_rollout.py 的分支推进、visual_pilot.py 的能量接口 | 新观测评分是否实际比较执行结果；关联是否读取真值；未来有变化时如何处理？ |
| 5 学习 | m1_af_rollout.py、m1_af_method.py、dev_learning.py | 拆清编码/标签/目标/优化；C/E 是否足够强，预算和读取权限是否公平？ |
| 6 评价 | m1_metrics.py、equivalence.py | 世界语义与历史差异如何判，未知如何计分，候选索引错误是否与真实错误混在一起？ |
| 7 运行和导出 | scripts/、ops/、run_provenance.py | 是否复用成功单元、识别部分失败、绑定科学源码并准确记录退出；不能“训练 OK、验收误报未完成” |

旧 executor/equivalence 不预先全盘推翻，也不默认完全适配新数据；按已审合同逐条检查。科学算法放 src，scripts 负责正式运行，ops 只做阶段运维和检查，不再复制同一算法到多套入口。共享代码改变后跑受影响的旧合同回归；只有环境/依赖也变化或广泛风险未解决时再扩大测试范围。

### 评价口径必须先讲清

下表是待 R2/R6 细化的解释框架，不是已经冻结的新成功门。指标不得只报一个全图 exact，也不得无限添加指标挑有利项。

| 量 | 输入与输出、具体例子及边界 |
|---|---|
| 候选覆盖 | 输入当前真实候选与独立可判断答案，输出至少一个可接受修订存在的比例；例如需要新身份却没有 BIRTH/REPLACE 是缺失，不是学生错；未知答案另列 |
| 教师错误与学生错误 | 输入可用候选、审计答案、教师/学生选择，分层输出错误；例如教师正确但学生选错是学习误差，不混成执行器错误 |
| 完整/部分修复机会 | 输入当前错误记忆及可执行候选，输出能完整恢复、只能减轻、不能修复的计数；撤掉错边却补不回节点属部分修复，不等于所有多步路径不可达 |
| 记忆语义与证据正确性 | 输入独立身份映射、位置和证据归属，输出分开的错误；对象位置对但绑定了错误证据仍单列，不因图看起来相同就忽略 |
| 错误持续负担 | 输入逐时刻多余/缺失事实，累计其持续暴露；例如一条错事实持续十次决策与十条错事实一闪而过可以区分。跨扫描实际时间未知时按决策/观测次数计，不伪造小时数 |
| 无关记忆损伤与表示变化 | 输入事务前后、影响范围和独立语义检查，输出不应改变部分的损伤及表示变化；向量变化大不自动是损伤，正确融合也可能移动向量 |
| 增长和成本 | 输入节点/证据版本数量及完整执行计时，输出多余增长、总时延、存储、训练和教师成本；网络前向快不等于整条系统快 |

### 阶段交付、预算和异常处理

- 一个已确定阶段只同步一次：相应测试、数据处理、检查、训练（若该阶段允许）、导出/核验入口提前备齐。按数据→验收→下一步顺序运行，不让用户每发“下一步”都 pull 一次。尚未确定的方法不提前写成固定算法。
- 每条正式命令包含步骤 ID、输入 marker/manifest/hash 检查、读写目录、续跑方式和成功标志；大产物在 outputs，带来源的小报告在 results。开发数据样例与可视化也须有原始帧引用，不用手工截图冒充原始数据。
- 服务器目录先 `git rev-parse --show-toplevel` 获取并原样复用；用户手动运行。本机只做代码、文档、Git 和轻量标准库复算，不运行 Torch/NumPy、特征提取、训练或科学测试。
- 成功单元只读复用；中断单元保留，先核验状态再从最早缺失步骤继续。数据缺失、源码不匹配、测试失败分别报错，不用自动重训或覆盖目录解决。
- 预计不超过 30 分钟默认前台；超过 30 分钟才后台。数据访问等待、下载、前端、教师、学生和审查时间分别报告；没有测速前不承诺 GPU 型号、总费用或完成天数。
- 每个计算阶段启动前给出最大数据组数、更新数、存储和预计费用/时间范围；超过上限先报告原因及已完成单元，不自动扩预算。源码/合同变化重新绑定检查，纯文档更新不要求重跑科学计算。
- 发现答案代理或未来通道时，停止消费受影响产物，保留它们并标明影响范围；修复产生新版本和必要重算，不能改旧 manifest 让新旧产物看似一致。

### 当前唯一下一步

先交付本计划供你审查；同时可做步骤 01 的只读代码定位及准备数据访问。实际计算从步骤 02 的官方访问和小样本 manifest 开始，**当前不写新学习器、不下载全量数据、不运行训练**。拿到下载方式之后，先给你具体样本清单和阶段 A 的固定命令，再看原始数据；R1 之前不把新 M1 的架构、标签或题目固定死。

## 文件职责与优先级

| 文件 | 只负责什么 |
|---|---|
| 本文件 | 阶段顺序、分支条件、当前指针、允许调整的开发细节 |
| [`EXECUTE.md`](../../EXECUTE.md) | 已经发生的 run、失败、结果与当前看板；不再承担完整流程 |
| [`configs/m1_hard_condition_v7.json`](../../configs/m1_hard_condition_v7.json) + [`m1_scope_rebuild_plan.json`](../../configs/m1_scope_rebuild_plan.json) | 修正版本的生成合同与重建前固定规则；旧 v6 hard/overlay/post-probe registration 保留作历史来源，新组合登记待修正 probe 后接线，test 未解封 |
| [`HARD_CONDITION_EXPERIMENT.md`](HARD_CONDITION_EXPERIMENT.md) | M1 实验合同与白话解释 |
| [`docs/DECISIONS.md`](../../docs/DECISIONS.md) | 已接受的重要方法、预算或流程变更 |

冲突时，已接受的 decision 和机器合同高于本流程。流程细节可以随 train/validation 结果调整，但不能藉此绕过重新冻结或偷看 test。

## 当前指针

- **D-059 当前任务：** 用户要求先看数据、允许彻底重构 M1，并亲自把关科学代码。已交付本文件上方的 32 步计划供审查；尚未实施新科学模块或开始计算。下一步依阶段 A 处理访问和首批样本，R1 数据审查后才固定新 M1 题目，R2 后才开始逐模块实现。以下 D-058 及 v7 条目保留来源和历史边界，后续范围以 D-059 为准。

- **D-058 当前转向：** 用户明确要求直接开展 M2 公开数据到观测 latent 的接入。当前任务是核对数据可用性并准备小样本视觉/几何适配与信息来源检查，设计见 [M2_DESIGN.md](M2_DESIGN.md)。尚未确定正式数据/前端与运行配置，不启动训练。D-058 对该独立接入阶段替代下文历史“M1 成功才可进入 M2”的限制；M1 科学 no-go、S6 禁止放行及 test 封存均不变。
- 用户已确认服务器尚未下载公开数据。优先考察 3RScan 的一个训练场所及其关联重访；先落实官方数据访问，再按实际下载结构一次准备小样本阶段入口。数据源正式选择、具体场所/帧范围和冻结前端仍未落实，不凭网页猜服务器目录，不启动特征提取或训练。

- 当前原型分支：ROLE-S1/S2 及回执修复、服务器产物 Git 收尾已完成，证据仅见 EXECUTE LOG-100；已有 results/m1_d056_role_encoding_server_check.json 直接复用，不再 run/recover，也不因文档更新重新同步或重跑。D-056 工程阶段结束。
- D-057 的 ROLE-P0→P1→P2 seed 7/19→P3 及结果 Git 收尾已完成；本地导出复核见 EXECUTE LOG-102，既有运行全部复用，不再次 test/prepare/run/export。固定计划仍保存在 configs/m1_role_pilot.json，历史命令留作审计。
- D-057 保留混合结果解释与收口：可只读分析现有 C06 改善及 C08/C05 退步轨迹；不追加 seed/更新数，不启动 query 消融或新确认运行。当前没有已授权而未跑完的第五 seed 或完整预算网格。
- 当前解释统一使用“新到达的观测 latent 如何影响旧记忆”，不把“新观测”预设为“新实体”。结构/引用修订、尚未验证的 canonical 向量数值修订及额外 query 来源分别按 [实验合同的影响边界](HARD_CONDITION_EXPERIMENT.md#新观测-latent-与旧记忆的影响边界) 解释；这是既有任务澄清，不启动新实验阶段。
- D-057 仅报告固定 300 步、两个 seed 的方向性结果，不按结果增加组、延长训练或选 checkpoint；没有信号可说明小预算下未见改善，不能断言角色表示在充分训练下无效。有信号仍需另外冻结 query 依赖对照及独立确认协议，不自动扩模型或进入 M2。旧字节绑定的 LOG-097 诊断可在 b63e9a6 复核，不重写旧报告适配新 source hash；已有 AV1→AV2→AV3、S5 产物不重新生成或扫描。
- M1 协议状态：**S5 独立确认已完成并复核（EXECUTE LOG-090），工程完整但效应 CI 触发既有明确 no-go。本协议按负结果收口；S6 不放行，test 保持封存，不重新选参/调门。独立的 M2 接入由 D-058 新授权，不来自 S5 通过。S5 的结果不是 S6 test 结果，历史运行命令保留用于审计，不作为继续考试的授权。**
- 历史 S2 证据：v5 S2 的 arrays/manifest/report 已验收；1000−300 的 paired-group 95% CI 为 `[+0.008750,+0.045000]`，按预登记规则选择 1000。10-group 同预算锚点中共同 group 1 的 40−10 平均差为 `+0.005000`、仅 `1/5` seed 严格为正，未达 S3 触发条件。完整数字与 provenance 见 `EXECUTE.md` LOG-032/033。
- 已完成：同一份 40-group v4 arrays 确定性截取 10/40 groups，运行 scorer steps {60,300,1000} × seed 7。40-group 全 train 上，static preflight 对 2,552/2,552 个 executor-illegal 候选全部静态拒绝、合法误拒 0；过滤后 target-only 均匀并列期望由 0.7729 升至 0.9698，assembled oracle accuracy 由 0.7438 升至 0.9525，其 exact-ambiguity capped 读数由 0.7275 升至 0.9275。D-038 已接受把同一只读预检变成 A–E 共享 mask；旧 v4 过滤数字仍只作采纳依据，不冒充 v5 方法成绩。
- scorer 分支：40-group inner-dev 的未过滤/过滤后 teacher accuracy 在 steps 60/300/1000 分别为 0.0500/0.5688/0.5031 与 0.0625/0.7469/0.7094。1000 steps 虽将 held-out BCE 从 0.1016 降到 0.0744，候选排序却低于 300 steps；共同 group 1 在 10/40 groups、300/1000 steps 过滤后均为 0.875，也没有显示扩大到 S3 的明确数据收益。因此 300 steps 只是当前单 seed 候选，尚未固定。
- 历史 v6 分支（不作为修正版执行指令）：D-043 提交 `53539ce` 已在干净服务器运行 191 项测试，12-group train-only health 亦以完全相同的历史 digest 通过。1000-group train 随后用 16 workers 在 1001.0 秒内生成 40,000 rows，teacher agreement=`1.0`、health gate PASS，arrays digest=`e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168`。运行时报告已导出为 `results/m1_v6_d043_runtime_profile.json`：固定 300-step 实测外推原 12 格 Set Transformer/MLP 分别约 3.128/1.239 小时、峰值约 2.60/1.99 GB，合计约 4.367 小时；D-046 对同一逐方法实测路径保守加入每臂 10 条 C 附加路径后约为 3.640/1.395、合计 5.036 小时，仍只是 planning estimate，没有科学指标。D-044–D-047 已把 exact/graded 一次切换、节点安全、完整 collateral、F gate、AUC `40/80`、test 检验力规则和 H=1 teacher 主文机制对照冻结到专用 train-only overlay；当前不读取 validation/test、不直接启动完整网格。
- 成本边界：修正版 train/validation 为 1000/200 个总混合 paired groups，test N 按 D-051 一次性六格公式确定且不低于 1350，不乘 12；旧组合登记的 1350 不直接冒充修正版最终 N；原 test=200 的全 split 成本外推仅是历史估算，不能覆盖新规模。运行成本与已生成数据见 EXECUTE。完整预算网格仍按 D-046 登记，未获新结果前不扩网格；test 仅在 S6 完成入口接线、复核规模和重新冻结后生成。
- 数据量锚点判据（运行前固定）：只在 10-group 固定留出的共同 paired group 1 上，逐 seed 计算 `40 groups − 10 groups` 的 candidate-ranking accuracy。若五 seed 中至少 4 个严格为正，且五 seed 均值 `>= 0.025`（该 group 的 40 online decisions 中至少一个平均决策），才称“有明确继续增大 train diversity 的方向性信号”并进入 S3；否则 S3 不触发、进入 S4 预冻结审计。该锚点只有一个独立 group，故不报虚假的 CI、不重新选择 1000 steps、也不单独支持性能结论。
- 预登记方向：共享 mask 主要移除旧 E 会选而 A–D 已由执行信息避开的静态非法候选，因此预期 v5 的 `A_vs_E` 单步与 causal margin 相对 v3/v4 历史读数缩小，触发主对比 stop rule 的概率上升；若 margin 不缩小或仍通过门槛，才是更强证据。该方向在运行前固定，结果出来后不得把“缩小”或“不缩小”任一方向改写成预先支持 CTL。
- scorer 选择规则：共享 mask 后的 inner-dev candidate-ranking accuracy 是主选择量；同一 paired group、同一 seed 的 1000−300 先配对，再在每个 group 内对五个登记 seed 求平均，最后对 8 个 group 差值用固定 seed=260906 做 10,000 次单层 paired-group bootstrap，取 95% percentile CI。只有 CI 下界大于 0 才选 1000，否则选计算更省的 300；不得把 5×8 格子当成 40 个独立样本。总体/判别性 BCE 与 reference ranking margin 只解释目标是否失配，不按 BCE 单独选预算。若多 seed 复现“总体 BCE 改善但判别性 BCE、margin 或排序下降”，另立 decision 后才可测试 future-derived listwise loss，不得直接用全量 reference index 监督。
- BCE 分解判据：`ranking_relevant_bce` 是 loss-mismatch 的主 BCE 诊断，因为它直接筛出会改变 oracle mismatch 贡献、因而可能改变候选能量排序的位置；`target_discriminative_bce` 是次级解释量，只回答同一坐标在准入候选间是否同时出现真/假。两者不必是包含关系；发生冲突时，预算仍只按 candidate-ranking accuracy 的预登记置信区间选择，是否改 loss 以 ranking-relevant BCE、reference margin 与实际排序的多 seed 共变为主，且必须另立 decision。
- D-043/D-046 预算边界：每种架构先选 E scorer，再让 A–E 在 C weight=1 锚点上从完全相同的 12 格中以同一 reference accuracy 各自选 `(lr,updates)`；精确平手取更少 updates、再取更小 lr。随后只在 C 已冻结的计算格上复用 weight=1 并补跑 0.1/10 两条路径，以相同 group-first/五 seed 聚合选最高，精确平手优先 1、再取较小权重；不做 36 格联合搜索。10000 触顶照实接受、不扩格；共享格与 A/E 交叉格只作算力敏感性诊断。`test_access=false`、`validation_arrays_read=false`、`validation_trial_consumed=false`；不校准 gate、不跑 causal，不进入 PNO/M2 或全局 reconciliation。
- 历史 D-044–D-047 endpoint 边界（D-051 已关闭重新选择 endpoint；当前按下方总流程）：只在 Set Transformer 主臂以固定 `(lr=0.0006, updates=3000, C weight=1)` 跑 A/C/E、五 seed 和 F；所有方法固定 `(commit_probability=0, margin_threshold=0)`，不再用两折单步代理选择 shared raw-softmax gate。F 任一 semantic exact/graded、open-memory graded、open-fact AUC 或 node integrity 失败立即停止。semantic exact 的 A−C/A−E 均有至少 7 个非零 paired-group 差且 SD>0 时保留 exact；否则仅在 active graded 两对照均满足时一次切换，开关禁止读取赢家、效应方向和大小；open-memory graded 与 `open_fact_error_auc_per_100_decisions` 是固定 co-primary，也必须对两对照非退化。AUC minimum/planning 固定为 20 步持续等价的 `40/80`（8/16 个错误事实×决策步暴露）；probe 观察到的均值、效应或 SD 只能报告，不能回调该门。test N 取 selected semantic/open-memory/open-fact AUC × 两对照的 paired-SD 功效需求最大值。机制–指标矩阵另要求 C10 的相反 BIND/NOOP 被 evidence-support 通道看见、C11 指定对照被 unrelated collateral 看见；C10 单步仍按信息上限预期约 0.5，不宣称模型能预测未见未来。probe 还必须在同一 201 个完整 train/inner-dev groups 上，以完全相同候选、当前证据、外生轨迹和非 future 能量重算 H=1 teacher，主文报告 H3-vs-H1 的分布差异；它不参与 endpoint switch、test N 或成败门。validation/test 仍封存。

## 历史指标层审计处置（D-045/D-046，后续以 D-051 为准）

依据：[2026-09-07 指标层审计](../../docs/reviews/2026-09-07_metric_layer_audit.md)。该文件及后续 Claude 反馈是外部只读复核，不是 ground truth；以下事项已由 D-045/D-046 逐项裁定并完成本地接线，只有服务器 full test 成功后才算通过工程验证。

1. **污染构念对齐（已接线）**：`memory_contamination` 已降为兼容 alias；规范量改为 extra/missing open-fact error，并把额外事实拆成 new-write/stale-retention。M1 明确不声称原始 Dynamic Contamination Rate。
2. **终点与时间负担（已接线）**：terminal burden 与 AUC burden 已分开登记；正式长期负担 co-primary 是 extra+missing 的 `open_fact_error_auc_per_100_decisions`，并已纳入 test-N 功效规划。
3. **指标命名清理（已接线）**：history/post、contamination 与 unresolved 兼容 alias 已从正式 endpoint summary 排除；exact 是首选二值语义终点，graded 只作一次性同构 fallback。
4. **统计/门修正（已接线）**：空 recovery 分母返回 `None` 并报告 eligible denominator；`false_birth_growth` 使用集合差；shared gate 固定为 `(0,0)` always-attempt，不再用一步 proxy 选择 20-step gate。
5. **minimal-world-change（已裁定）**：edit/growth posterior influence 继续原样报告，不事后调权；论文只称其为注册 prior/regularizer，不称其为已验证主机制。
6. **范围边界（已裁定）**：M1 只验证 CPMT/CTL 的受控 persistent-world revision；独立 dynamic/transient memory、decay、static retention、reappearance/viewpoint consistency 留给 M2/M3。

处置结果：规范名改为 extra/missing open-fact error，并拆 new-write/stale-retention；terminal 与 AUC 并列，`open_fact_error_auc_per_100_decisions` 成为固定 co-primary 且纳入 test-N；D-046 将其 effect 门冻结为 20 步持续等价 `40/80`，并禁止按 probe 尺度回调。正式主表排除 history/post、contamination 和 unresolved 兼容别名；空 recovery 为 `null`、false-birth 用集合差；minimal-world-change 只称注册正则；M1 不声称原始 DCR 或完整 static/dynamic 双记忆。D-044 的 shared cross-fitted gate 被固定 `(0,0)` 无选择 gate supersede，且 D-046 分开 attempt、实际 commit 与 executor quarantine；C weight 改为 train/inner-dev 顺序选择，validation 只确认。完成顺序现为：**服务器 full test → 固定 endpoint probe → 再决定是否进入完整预算网格**。A1/A2/A4 的 evidence/node/collateral 覆盖修复保持，不重复返工；C10 继续按信息上限约 0.5 解释，不宣称能预测未见未来。

## 历史主张、执行与轨迹边界补正（D-047）

D-047 不改变 A/C/E、数据、候选、executor、co-primary 或通过门，只消除三种容易伤害论文可信度的过度表述。第一，claim 改为“真实执行候选世界后，以 current/随后实际观测的 future evidence 为主要评分信号”，edit/growth 只称预登记正则，不再与 current/future 并列成已验证机制。第二，online 网络只评分且不读 `post_graph`/future，D-048 进一步校正为：共享生成器和评测器仍展开候选，只有选中合法世界持久化；M2 单次执行部署路径尚未实现。第三，M1 的 event/observation/pose/revisit schedule 是 seed 固定、模型运行前预生成的外生输入，故 M1 不评测 active navigation 或 action policy。

teacher agreement=`1.0` 继续按 fixture 事实披露，M1 只声称传播软 executable hindsight distribution，不声称普遍重写 hard labels。为避免这句话沦为免责说明，endpoint probe 必须在同一 201 个完整 train/inner-dev groups 上增加 H3-vs-H1 teacher horizon contrast：只截短执行后 future trace，其余输入与能量全部固定；agreement、top-1、entropy、TV、KL、argmax change 和 reference-probability shift 总体/逐 family 报告，并进入论文主文。它是机制解释，不是重训 H=1 student、不是新方法/co-primary，也不改变 A-vs-C/E 成败规则；弱或零结果必须披露并收窄“多步 future 起作用”的叙述，不能据此调参。

## M1 后续改进候选（单一记录处，不是当前调门清单）

以下项目集中保留在本流程文件，不另建 TODO/交接文档。它们只能用于解释当前 M1、设计一个明确的新协议版本或在 M1 go 后规划 M2/M3；不得因为 endpoint probe、validation 或 test 数字“不理想”就回改 D-046、扩当前网格或重跑同一 confirmatory test。若 formal M1 no-go，仍执行既定 stop rule：报告负结果，不靠这些项目扩模型或进入 M2。

- 轨迹负担可增加 survival profile、首次错误到修复的持续时长分布和按 extra/missing/new-write/stale 分层的描述图，帮助解释 AUC 由“少量长错”还是“大量短错”产生；它们不替代 `40` 的共同绝对门，也不新增 co-primary。
- 若未来另开全新协议，可研究半程持续锚点、按 reference graph size 标准化或相对 baseline 的 AUC estimand；必须在新数据/新 hash 和任何新 probe 前重新论证，不能用当前观测尺度选择。
- C 的 36 格联合 `(lr,updates,aux)` 搜索只保留为未来资源敏感性方案；当前 M1 固定顺序搜索。若未来使用，必须给其他方法的选择机会与算力公平性单独论证，不能在当前 C 结果不佳时临时启用。
- confidence calibration、risk–coverage 与允许合法低置信 abstention 可作为部署诊断或新协议研究；当前 M1 的主效果固定 `(0,0)` always-attempt，并只把 confidence 曲线作非选择性报告。
- minimal-world-change 的 edit/growth 权重效应可在当前 M1 结论之外做预登记消融；当前权重不因 posterior influence 小而上调，也不把该项宣传成已验证主机制。
- 独立 Static Structural Memory 与 Dynamic/Transient Memory、decay、dynamic-to-static contamination、static retention、reappearance 和 viewpoint consistency 继续属于 M2/M3 planned 范围；只有 M1 go 后才能按既定顺序实现。

白话：这份候选清单解决“当前实验跑完后，哪些科学问题值得继续追、又不会反过来污染已经冻结的考试规则”。输入是当前合同已知的构念边界和将来正式结果，输出是下一项独立研究的备选设计。例如 AUC 很高时可以画错误持续时长分布解释原因，但不能把 40 改成 20 让同一结果过门。它不等于补救列表、不授权看结果调参，也不覆盖 M1 失败即停止扩模型的规则。

## 总流程

S0–S3 保留原版本开发历史；下面 S4 起按 D-051 修正版本执行。旧 v8 数据、旧预算和模型只作历史证据，不作为修正版放行依据。

```text
S0 工程上限与校准闭环（历史完成）
  ↓
S1 E/target/scorer 诊断闭环（历史完成）
  ↓
S2 scorer 优化与数据规模诊断、共享 static preflight（历史完成）
  ↓
S3 更大 train 规模交互确认（未触发，跳过）
  ↓
S4 修正版本的选参前检查与预算选择
  ├─ 修正 1000 组 train 生成与健康验收
  ├─ 固定 train 错误分支完整 20 步检查、失败现场与导出审查
  ├─ 固定 anchor probe：F integrity、固定三项终点非退化、按 D-051 机械确定 N（已完成）
  │   └─ 同时覆盖模型保存/加载→20 步→配对汇总与探针导出（已完成，可复用）
  ├─ 预算并行接线与等价检查、fit/inner-dev 同口径诊断（已完成）
  ├─ 复用 probe 工程证据；train-only 小样本只补正式登记、两架构权重兼容、
  │   评测分片合并、配对置信区间及验收报告等新增接口，不重跑完整 probe
  └─ 两臂完整原预算网格及验收（已完成）
  ↓
S5 锁定配置、全 train 重训；独立 200 组 validation 一次性确认
  ↓
S6 重新冻结、单独解封 + 一次性 formal test
  ↓
S7 M1 成功 / no-go / 不确定收口
```

### 完整选参前的放行条件

以下为已经完成的选参前放行记录。后续 S5 新接口检查仍先定位工程原因；不得删除断言、换掉失败组或改效应门以求通过。以下开发工作只用 train；不提前读取或生成 validation/test。状态证据统一见 EXECUTE，未实现事项明确保留为 planned。

| 检查 | 何时做、要交付什么 | 当前实现边界 |
|---|---|---|
| 修正 train 验收 | 其余检查之前；组数、普通/recovery 行数、family 编码、digest 与来源一致 | 已有生成及验收回执，见 LOG-077；不重生成 |
| 错误分支 20 步 | 固定 16 组、七条选择规则，检查 C11 范围外目标、MERGE 配对、K=16、immutable base、边序不变和失败现场 | 历史严格 FAIL 保留；D-053 完整矩阵和 D-054 正式策略/复用验收已完成，见 LOG-080/082；不重复。完整轨迹不保证任意错误组合都能恢复 |
| 固定 anchor probe | 错误分支检查通过后、完整网格前；修正版 F、三项 co-primary 非退化、H3/H1 诊断及六格 SD；按既定规则登记 N，同时提供共有工程环节的验收证据 | 运行、汇总、导出及报告复核已完成（LOG-086）。实际模型保存/加载、完整 20 步、配对完整性与探针汇总/导出不另起一轮重复检查。不是完整选参，也不替代正式置信区间和验收门接线 |
| 并行预算与泛化诊断 | 完整网格前；独立进程随机流/汇总等价、资源检查、同一 checkpoint 的 fit 与 inner-dev 同口径分数和差距；并行交付同时覆盖选参和 S5 全 train 重训 | 公共 worker、原网格/C 顺序权重编排、修正版登记消费及 60 模型 refit 已接线，服务器验证与预算/refit 已完成（LOG-088）。固定十组 GPU 1/4 进程对拍后，用完整 1000 组做四条两步容量检查；GPU 4 进程×CPU 1 线程。差距只作诊断，不增加选参规则 |
| 后续新增接口贯通 | 完整网格前；复用已验收 probe 证据，只补正式登记读取、两架构权重兼容、评测分片合并、配对置信区间及验收报告；同时检查复用、来源绑定和失败拒绝 | 已接线并经服务器验收（LOG-088）：使用 GPU 对拍的 refit 权重，两架构×A/C/E×seed 7；固定原 inner-dev 组号序最前四组，各保留完整两条 20 步，比较不分片串行与四进程合并的全部科学逐例记录，另做串行前向计时。直接读取 probe 的 201 组五 seed 逐例结果验证正式统计公共函数，不重跑探针轨迹；检查成绩不参与选参。正式 S5 confirmation/S6 的数据生成、一次性消费与最终解封仍不由本入口执行 |

白话：新增接口贯通检查解决“模型都训完了，才发现正式入口读不了权重或统计字段”的问题。输入是已验收 probe 产物、并发检查短训权重及预先固定的少量 train 场景，输出是共有环节的复用证据和新增接口的实际运行证据。例如用现成逐例结果检查正式配对置信区间与报告，再用少量完整 paired groups 核对新并行评测的分片合并；不为检查报告格式重跑 201 组轨迹。它不是另一个完整 probe、不是正式选参或独立泛化验证，也不保证覆盖未来所有场景；规模和诊断设置须在运行前固定，不能根据成绩挑选。

复用以实际完成并验收的产物为准：当前 probe 的完整报告已复核，后续新接口仍须实际检查，不能提前标为通过。共有代码、输入和来源绑定未变时直接引用既有证据；新增或改变的接口只补对应检查，不以“目的不同”为由重复整条训练与评测链。原放行条件保持，固定 probe 的样本量汇总不能冒充正式 S5/S6 的配对置信区间、安全门和多重比较检查。

阶段实现可在不运行服务器任务的同时准备，但实际执行必须满足前置条件；固定 probe 的结果用于按已有公式填充新登记，不用于临时改评价代码。后续 S5/S6 的公共代码、schema、配对与来源检查必须提前准备并经过上述 train-only 路径验证，最终输入、配置和 test 解封仍按阶段冻结。不能把“尚未允许运行 S6”理解为“等完整训练结束才实现 S6”。

并行训练检查的切换条件：当前服务器版本先完成 `m1_corrected_probe.sh evaluate`、`summarize`、`export`，保存并提交精确 probe 报告后，才能同步新增脚本。新 `m1_parallel_training_check.sh test/check/export` 会拒绝与活动 probe 评测同时运行；其固定十组检查不等于正式预算或 S5 已放行，完整 runner 仍须消费修正版 probe/登记和其余工程条件。

### 已准备的后续命令（同步一次，逐步执行）

旧 probe 必须先在原版本完成并导出。下表统一使用 `bash ops/m1_corrected_followon.sh <动作>`；所有命令已写入同一版本，不为下一动作另发一次代码。每个动作完成后才进入下一行；任何失败保留产物并导出，不自动重跑或越过放行条件。新源代码的完整测试只跑一次，后续入口复用同一来源的测试回执。

| 动作 | 输入前提与输出 | 运行方式 |
|---|---|---|
| `test` | 当前版本完整测试；复用同来源成功测试 | 前台 |
| `process-check` | 测试通过；固定十组 GPU 单/四进程预算与 refit 对拍 | 前台 |
| `process-export` | 对拍完成，成功或失败均可导出原精确 process-check 报告 | 前台 |
| `prepare` | probe 与 process-check 导出均完整通过；核对旧运行来源、复用权重/轨迹并消费新登记 | 前台 |
| `capacity` | prepare 通过；两架构各 scorer/A，四进程、完整 1000 组、固定两步，只作容量检查 | 前台 |
| `repair-test` | 本次迭代器修复的当前来源完整测试；旧 full-test 不冒充新来源 | 前台 |
| `repair-adopt` | 新全测通过，核验旧成功步骤与特定空评测失败；保留原目录并建立明确来源的复用回执，不重复 GPU 训练 | 前台 |
| `interfaces` | 容量检查通过；新增接口检查、独立前向计时、复用 probe 逐例统计，成功后生成 ready 回执 | 前台 |
| `export-checks` | 上述检查完成或已失败；导出 `results/m1_v7_d054_corrected_checks.json` | 前台 |
| `budget` | 所有检查通过；30 条 scorer、150 条 A–E、20 条 C 补充路径，按固定规则选择，不扩格 | 默认后台；`status` 查看进度 |
| `export-budget` | budget 完成或失败；导出 `results/m1_v7_d054_corrected_budget.json` | 前台 |
| `refit` | budget 成功、选择结果从已保存逐组指标复算一致；全 train 从头训练两架构共 60 个模型 | 按本机已完成预算路径估时，超过 30 分钟才默认后台，否则前台 |
| `export-refit` | refit 完成或失败；导出 `results/m1_v7_d054_corrected_refit.json` | 前台 |

预计超过半小时的 budget/refit 可显式加 `--foreground`；其余检查不套后台模板。导出后只允许上述精确结果文件处于未提交状态，科学代码必须干净且来源一致；无需为运行下一动作先提交一次结果。成功的计算回执直接复用，失败/中断不自动重启；导出文件不同则保留并拒绝覆盖。最终 Git 收尾仍逐一列出精确报告路径。

用户明确要求记住的训练并发交付约束：**预算选参和 S5 重训都要接入 GPU 多进程，优先采用同一张 GPU 上 4 个独立训练进程、每进程 1 个 CPU 线程；不能只完成选参加速而遗漏 S5，也不能把测速建议描述为已经实现。** 四个进程分别训练独立模型路径，例如不同 seed；不得拆分同一个模型的优化器更新，E 必须等待对应 scorer，C 权重搜索仍守原顺序。修正版等价、显存/内存和 CPU 配额检查通过后才确定实际并发，资源不足时明确报告并下调，不能硬开四进程。此配置不表示四张 GPU，也不自动适用于 CPU 候选生成/执行评测。当前已在运行的固定 probe 不因后续优化而中断、切换设备或同步代码；防过拟合规则、原预算网格和安全/效应门不变。

## 阶段大纲与转向条件

| 阶段 | 要回答的问题 | 初始执行细节 | 离开该阶段前必须有的输出 |
|---|---|---|---|
| S0 ✓ | 指标、恢复路径和 calibration 分母是否成立 | 10/4 groups、seed 7、60 updates 的 smoke | observable final active=1、恢复一步；calibration/report/recovery=40/120/8；干净 provenance |
| S1（v4/v5 ✓） | E 低是 target、能量组装、优化还是泛化问题 | 10-group train arrays 按 SHA-256 留出完整 inner-dev group；scorer=60、seed=7；不读 validation | v5 shared-mask 不变量、target/assembly 与 scorer 接线已复核；结果见 `EXECUTE.md` LOG-031 |
| S2（v4 seed 7 ✓；v5 ✓） | E 是优化不足、数据不足还是两者交互；逐关系 BCE 是否与候选排序失配 | D-038 后先以 10 groups/60 steps/seed 7 重跑 S1；再在同一 40-group v5 train arrays 上跑 steps {300,1000} × seeds {7,19,31,43,59}；已选 1000 后，补 10 groups × 1000 × 五 seed 的同预算共同-group 锚点；只用 train/inner-dev | shared-mask 不变量、v5 S1 与 300/1000 五 seed 完整；按 paired-group CI 规则已选择唯一 scorer budget=1000；锚点未满足预登记方向判据，故 S3 跳过，不据 BCE 单独改 loss |
| S3 | 40 groups 后是否仍明确受数据多样性限制 | 仅在 S2 的 10→40 同预算锚点满足预登记方向判据后，在一个更大 train-group 点上复扫 S2 的两个 scorer steps，而不是顺序固定旧最优；仍只用 train/inner-dev | 确认最优 steps 是否随数据规模改变，并判定数据曲线继续上升或已经饱和；不得同时改容量或 target |
| S4 | 修正版本的工程路径、指标登记和预算是否可放行 | 先满足上方全部选参前放行条件；D-051 固定 exact/support/AUC、原安全门和 `(0,0)` gate，以修正 train 固定 anchor 核验 F/非退化，按六格 SD 及 1350 下限机械确定 N；随后两臂按 D-043/D-046 原网格及 C 顺序权重规则选参 | 工程报告、修正 probe 与组合登记、两臂完整预算报告及来源绑定全部验收；架构不择优、不重新选择 endpoint、不扩网格，validation/test 仍封存；旧成本/结果只见 EXECUTE 历史 LOG |
| S5 | 锁定设置在足量 train/validation 上是否值得进入 test | 使用满足 C00–C11 support 的 train 和与已查看 4 groups 不重叠的新 200-group validation confirmation；所有 C weight/lr/updates 与固定 `(0,0)` gate 均已冻结；5 seeds、10% labels、完整 20-step causal 和 10,000 paired bootstrap | coverage/invariant/provenance 全通过；validation 不选择任何设置、全部 200 groups 只确认一次；没有触发明确 stop rule |
| S6 | 封存后的未见数据是否支持 CTL 主张 | 记录 protocol/code/data/hyperparameter hash，单独人工解封 test；test 不选阈值、checkpoint 或方法 | 5 seeds 完整 A–F causal 结果、逐例指标、paired CI、所有失败和完整 provenance |
| S7 | M1 是否成功且可以结束 | 严格按下方终止规则 | 唯一 pass/no-go/inconclusive 结论；更新 EXECUTE/DECISIONS/claim ledger；不再调 M1 |

## S1 诊断分支

target-only oracle（只看目标的上限）不加 penalty、不标准化，直接比较每个候选声称与真实 future 的 mismatch。它输出正确候选是否在最小集合、是否唯一最小、并列集合大小和均匀打破并列时的期望准确率。例如 3 个 RELINK 都得到最小 mismatch 时，coverage 可以是 100%，但期望准确率只有 1/3。它不是可部署的 E，也不允许靠候选顺序冒充唯一判断。

| 诊断组合 | 结论 | 后续分支 |
|---|---|---|
| target-only 高，assembled oracle 高，E train 低 | target 和组装有信息，scorer 没优化好 | 进 S2，不改 target |
| target-only 高，assembled oracle 低 | 标准化/权重/penalty 破坏目标信号 | 只在 train/inner-dev 内诊断组装；若改公式须新 decision 和重新冻结 |
| target-only 低，或最小集合长期很大 | target 缺关系或只能缩小范围 | 在 test 前重构 target，升 dataset version，重跑 S1 |
| E fitting 高、inner-dev 低 | 组间泛化问题 | 进 S3，优先数据多样性/正则化诊断 |
| relation oracle illegal rate 高 | target/penalty 偏爱不可执行声明 | 在不执行候选的 E 边界内检查声明约束；不偷用 executor illegal mask |

transaction static preflight（事务静态预检）已由 D-038 接受为 A–E 共享 online admissibility mask：它读取 immutable prior world、候选程序、在线证据和 protected IDs，输出“已能静态拒绝”或“预检通过但执行未知”。固定 K=16 槽位和失败审计仍完整，拒绝项只在训练归一化、softmax、calibration 和 commit selection 前不可选。例如候选直接触碰 protected node 会被拒绝，但需要应用操作后才暴露的坏引用仍可能通过。它不生成 post-edit world、不等于最终 executor legality；A/D/F 的执行后 illegal 能量和 `remaining_executor_illegal_candidates` 仍必须保留。

admitted-uniform random accuracy（准入集合均匀随机准确率）解决 mask 后仍把随机地板写成固定 `1/16` 的问题。输入是每一行的 16 个预检布尔值，输出是逐行 `1/有效候选数` 再求平均；例如两行分别剩 2 和 4 个候选时，随机地板是 `(1/2+1/4)/2=0.375`，不是 `1/平均候选数`。它不等于模型准确率，也不使用 reference 或 executor legality。

residual decision-impact upper bound（残余非法决策影响上界）解决只报残余候选总数却不知道最多影响多少决策的问题。输入是“预检通过但执行后非法”的行列 mask，输出是至少含一个此类候选的决策行比例；例如 100 行中有 3 行含残余非法项，则 executor illegal 通道最多改变 3% 的 teacher 决策。它是严格上界，不等于真的改变了 3%，也不为没有 post-edit world 的失败候选虚构 future 能量。

E 的 scorer 与 A–E 的 online student 使用两个独立预算：E 额外 scorer 参数/updates 单列；A–E student 架构与 12 格搜索机会完全一致，但允许按同一 reference 指标选不同 `(lr,updates)`。60→600 的非仓库 scratch probe 只作为提出二维曲线的线索，不作为选择正式设置的证据；scorer 选择只看上述可追溯 train/inner-dev 曲线。held-out BCE 早停不启用。

D-043 已把新曲线定为两架构各自的 learning rate `{0.0002,0.0006,0.002}` × `{300,1000,3000,10000}` 前缀 checkpoints × 五 seed，并改用完整 1000-group train 的固定 inner-dev。E scorer 先按 reference candidate-ranking accuracy 选择；随后 A–E 各自按同一 reference-candidate selection accuracy 选格。最高均值胜，只有精确平手才取更小 updates、再取更小 lr；10000 胜出直接接受并标 ceiling。相同网格还输出一个 A–E 共享格和 A/E 在彼此格上的交叉读数，均不反向改变正式配置。它是有限网格而非 held-out BCE early stopping；架构身份、网格上界和选择量不随中间结果扩张。

D-046 后不再有活动 validation trial 选择预算：C auxiliary weight 与 learning rate/checkpoint 都只读 train/inner-dev，commit gate 固定 `(0,0)`；所有点必须完整报告且不得扩张。新的 200-group validation 是纯 confirmation，只能在全部设置冻结后完整运行一次并报告。LOG-022 已经查看过的 4-group report 半区仍是历史开发结果，不得并入 S5 confirmation 或用于选择。

## 允许调整与必须重新冻结的边界

| 类型 | 处理方式 |
|---|---|
| 可在当前阶段调整 | 诊断输出字段、CPU/GPU 线程、worker 数和不改数据/训练轨迹的批处理方式；结果写 EXECUTE |
| 只能按已登记规则选 | learning rate/checkpoint 只从相同 12 格用 train/inner-dev 选择；C weight 只在其已选计算格上顺序比较 `{0.1,1,10}`；validation 不选择任何设置，commit gate 固定 `(0,0)`；任何扩格须新 decision |
| 必须新 decision + 新 dataset/protocol hash + 从 S1 重跑 | 启用 static-preflight 候选过滤、E target 定义、能量标准化/权重、recovery 触发/范围、K、候选生成器、H 主值、online feature 语义、主指标或效应门槛 |
| test 解封后禁止调整 | 所有会影响方法、数据、阈值、checkpoint、排除项或报告口径的内容；test 只产生最终结论 |

白话：“细节可调”解决开发中不可能一次猜对训练成本的问题。输入是当前阶段未触及 test 的诊断，输出是下一个事先记录的设置。例如 300 updates 仍上升时可按计划跑 1000；看到 test 不理想后再改权重不可以。它不等于随时移动门槛或无限加数据。

## M1 成功与结束定义

单步准确率 90%、relation oracle 高或 observable oracle=1 都不是 M1 成功。M1 只在重新冻结后的 formal test 上判定。

**成功（go）：** A–C 和 A–E 两个主对比均必须同时满足：

- D-051 固定的 exact active-world semantic correctness（`final_active_graph_correctness`）差值的 95% CI 下界 `>= +0.03`；
- graded open-memory support correctness 差值的 95% CI 下界 `>= +0.03`；
- `open_fact_error_auc_per_100_decisions` reduction 的 95% CI 下界 `>= 40.0`；
- false-birth 差值的 CI 下界 `>= -1.0 / 100`；
- collateral 差值的 CI 下界 `>= -0.5 / 100`；
- A–C/A–E 交并检验经 Holm–Bonferroni 校正后 `p <= 0.05`；
- executor invariant violation 为 0；candidate coverage@16 总体 `>=98%`、每 family `>=95%`；
- 5 个登记 seed、10,000 次 paired-group bootstrap、失败 run 和 provenance 都完整。

**明确 no-go：** 任一主对比的 CI 上界仍低于已登记的主效应门槛，或 coverage/invariant/safety 门失败且不属于 test 前已证明的独立工程故障。M1 以负结果结束，不用 PNO、第二任务或更大模型救结果，不进入 M2。

**不确定：** CI 同时覆盖“无效”和“最小有意义效应”。这不等于成功。S4 必须在 test 解封前事先选定“最多一次固定扩样”或“固定样本后以 inconclusive/no-go 收口”；未预先写明时，test 后不得自行扩样。

白话：M1 成功解决“CTL 这台修订发动机是否值得装进完整系统”的问题。输入是封存后从未用于选方法的 test sequence，输出是 A 相对 C/E 的长期当前世界语义、开放记忆支持、全过程开放事实负担和安全差值。例如 A 即使终点修对，也必须比 C/E 至少多 3 个百分点的 semantic/support 正确度并累计减少 40 个 AUC 单位（8 个错误事实×决策步暴露）才可能通过。它不等于训练准确率高、oracle 可达、只在最后一步补救或一个对照输了。

## 每阶段如何更新本流程

1. 跑之前：在“当前指针”写明阶段、本次设置和允许的分支；不得只留在对话里。
2. 跑之后：数字、失败和 provenance 只追加到 `EXECUTE.md`，本文件只移动阶段指针并记录下一分支。
3. 若只调开发细节：改本文件对应阶段；若改方法、数据语义、预算或终止规则：同时追加 `docs/DECISIONS.md` 并更新合同。
4. 只有当前阶段的必需输出齐全才能勾选并进入下一阶段。

## 最终交付清单

- 冻结 config、protocol hash、code/source-tree hash、train/validation/test manifests 与 arrays digest；
- 5 seeds 的模型/checkpoint、预算、wall-clock、峰值显存与 p95 latency；
- 逐候选能量、逐例指标、candidate/teacher/amortization/rollout error 分解；
- A–C/A–E paired CI、Holm 校正、safety、coverage、invariant 与恢复诊断；
- 完整失败 run、排除原因和 provenance；
- `EXECUTE.md` 最终 LOG、`docs/DECISIONS.md` 终止决定与 claim ledger 状态。


## D-055 S5 独立确认：一次同步后的固定命令

当前阶段已备齐；全测和 train 小预演先于 validation 生成，生成成功且健康门通过后才允许评测。所有动作统一为 `bash ops/m1_corrected_confirmation.sh <动作>`。每行成功后再执行下一行，不为切换动作要求新提交/pull。

| 动作 | 完成条件与读写范围 | 前后台 |
|---|---|---|
| `test` | 新来源完整全测，failures/errors/skipped=0；不读正式 validation/test | 前台 |
| `prepare` | 原算法来源桥接、导出指纹、登记与 60 模型全部 CPU 加载成功；不训练 | 前台 |
| `smoke` | 固定 train 第 1 组读写 digest 对拍、两架构 A/C/E seed 7 正式权重与两个 oracle 接线，320 次决策；不读取 validation | 前台 |
| `generate` | 固定 validation 4–203，共 200 组及原 family/teacher 健康门；输出新 data manifest；不评测模型 | 前台 |
| `export-data` | 导出 `results/m1_v7_d055_s5_data.json`，成功报告 `engineering_pass=true` 后继续；失败只保留诊断 | 前台 |
| `evaluate` | 先落一次性验证消费记录；50 模型×8000 决策及共享两个 oracle；成功启动仅为 `completed=false` | 默认后台 |
| `status` | 只读状态；等待 `evaluate completed=true exit=0`，不是只看入口 EXIT=0 | 前台 |
| `summarize` | 两架构所有配对/seed 支持齐全、原统计、安全门与 F 核验；不再选参数，不自动解封 test | 前台 |
| `export-confirmation` | 导出 `results/m1_v7_d055_s5_confirmation.json`；科学未过门仍如实导出，工程失败单独标记 | 前台 |

输出目录为 `/root/autodl-tmp/cpmt_outputs/m1-v7-d055-s5-<source-prefix>`。生成前全局固定 reservation 防止换来源/目录重开；各步骤退出证据、单位 hash 和失败现场保留，不能静默续算中断单位。运行中的 checkout 不同步。预计超过 30 分钟的 evaluate 可显式 `--foreground`，其余动作不套后台模板。两份报告导出后一次提交精确路径，不需要先提交 data 报告才能评测。

导出与本地复核之后按原 S5 stop rule 决定是否进入 S6 最终冻结；本阶段不含 test 入口。完整命令存在不等于允许越过前置条件，也不表示服务器全测或正式确认已完成。


## S5 事后逐步可达性分析：一次同步后的固定命令

本阶段只读取已完成的 confirmation 及其绑定 complete/result 分片。同步前在服务器当前终端运行 `git rev-parse --show-toplevel` 取得实际仓库根路径并原样使用；不猜远端目录，不在仍运行任务的 checkout 中 pull。确认处于本仓库且没有未收尾更改后，`git pull --ff-only origin main`，阶段内不为切换步骤再次更新代码。

| 步骤 ID | 命令 | 前提、读写边界和成功标志 |
|---|---|---|
| AV1 | `python ops/export_m1_s5_availability.py export` | 内置轻量前置测试先通过；固定 confirmation 哈希、全部模型/组矩阵及各单位原 marker/result 哈希和登记绑定必须一致。读取已有结果并在同一步汇总、校验、导出；输出 results/m1_v7_d055_s5_availability.json。成功为 AVAILABILITY_EXPORT_OK、exit=0；已有合格报告则 AVAILABILITY_VERIFY_OK 后直接复用。失败/中断保留 outputs/m1-s5-availability-export/<code-prefix>/ 运行证据，拒绝静默重开，不触发重新评测。 |
| AV2 | `python ops/export_m1_s5_availability.py verify` | AV1 已成功。只读导出和固定 confirmation，从保留的全部步骤复算计数、比例和时间轴指标；不读原服务器分片。AVAILABILITY_VERIFY_OK、进程退出 0 后才进入 Git 收尾。 |
| AV3 | 下方三条 Git 命令 | AV2 成功后仅提交这一份导出，不通配 results，也不提交 outputs。push 成功后本地同步同一版本，用 verify 及已有 JSON 字段分析；不为本地复核修改入口。 |

AV1 默认前台：只扫描 complete/result JSON，逐 100 分片显示进度；读盘耗时尚无全量实测，不自动套后台模板。AV2 同样前台。导出不读取 execution 大文件，不重训、不重新运行 validation，不读取 test。服务器全量未运行前，不把本地小型检查或 group 69 对拍冒称为总体归因结果。

AV3 的固定 Git 收尾：

```bash
git add -- results/m1_v7_d055_s5_availability.json
git commit -m "results: export complete S5 candidate availability"
git push origin main
```

本阶段完成后的有界分析是读取全部八格、方法/seed/当前 family/所选事务分层，并据逐例来源定位仍需完整轨迹的错误。先解释已保存事实，不据新诊断改原验收门或 S5 no-go。
