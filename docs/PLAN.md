# VSMT-lean 从合同到论文结果的完整计划（D-224）

本文件只维护 VSMT-lean（实体生命周期版本化事务，D-224）从当前代码到论文结果的步骤链、依赖、状态、交付物和失败分支。旧 VM-00～VM-06 计划、CPMT、空间世界模型与地点层路线已随分支 `archive/pre-d224-unified-graph` 归档，本文不再列出。方法定义见 [METHOD.md](METHOD.md)，字段见 [DATA.md](DATA.md)，决策理由见 [DECISIONS.md](DECISIONS.md)，运行证据见 [EXECUTE.md](../EXECUTE.md)。本文**不自动切换研究主张**：任何会改变论文声称什么的替代路线，都必须先暂停、报告证据，再写成新决策交用户批准。

## 一、最终目标与总链路

在同一冻结公开 RGB-D 前端、同一召回规则、同一执行器和同一评价协议下，比较 VSMT-lean、TAF、ELU-P、RAC 和 LOW，回答 hindsight 监督的可逆生命周期修订能否减少陈旧实体、误删并保住被搬动物体的身份。

```text
S0 合同冻结（S0-01 → S0-06）
  ↓
S1 前端与数据小试（S1-01 → S1-02a → S1-02b → S1-05）
  ↓
S2 五臂开发表（S2-01 → S2-05）
  ↓
S3 正式数据、训练、validation 与一次性 test（S3-01 → S3-06）
  ↓
S4 论文
```

当前执行点：**S0 五份合同全部审查通过（LOG-214～LOG-219），S1-01 资产与容量授权申请材料已实现待审**（LOG-220），**D-224-S1 九项裁决已批准并落地，服务器冻结资产已只读核验通过**（LOG-221）。D-224 与 D-224-E/F/G 已批准；旧方向已归档到 `archive/pre-d224-unified-graph`，`main` 只含精简版文档。**四项已知冲突全部消解并各有回执**：Python 按两解释器分工、Vulkan 可枚举到 NVIDIA GPU、ProcTHOR-10K 定为 0.1.2（以上 LOG-221），ViT-B/14 完成一次性摘要登记（LOG-223）；基础环境缺 hydra 的阻塞已于 LOG-222 解除。S1-01 里待冻结的 null 只剩 `worker_rule.headroom_fraction`。当前开四个位（三只读/本地登记加一依赖安装），没有任何资产放置、数据生成或训练授权。**S1-01 的 worker 推导死锁已按 D-224-S1 裁决 14 解开**：占用测量移入新拆出的 S1-02a（4 worker × 1 house，4 条 episode 计入正式 50 条），S1-02b 再按算出的 worker 数补齐其余 46 个；S1-01 只保留推导规则。数据盘已由用户清理并经只读核验，22 G → 43 G 可用（LOG-224）。S1-02a 尚未获得运行授权。**2026-09-20 用户批准 D-224-X 裁决 X1～X6**（S0 合同隐患审查的六项修正）：S0-01/02/03/04/05 各追加 v2 合同、v1 字节冻结并由测试钉住摘要，S0-03 求解器与 S0-04 评价器按逐列等价重写；本会话复审修正四处后八个 lean 模块分进程共 386 项本地通过，五份 v2 已按用户批准提交推送（LOG-225）。S1-02a 开工前新增一项前置冻结：S0-02 v2 要求 seed 与 test/validation 规模在第一条 episode 前给定。**2026-09-20 用户审过 S1-01 v1 并把 `headroom_fraction` 定为 0.2**；随之发现 S0 转 v2 后 S1-01 仍指着 v1，已追加 S1-01 v2 改指 v2 并把 S1↔S0 一致性纳入跨合同测试（LOG-226）。S1-01 待冻结 null 已清零。**2026-09-20 用户审过 S1-01 v2 与五份 S0 v2**，并已实现 S1-02a 合同（LOG-227）；该合同把划分复用 S0-02 的 `assign_split`、worker 推导复用 S1-01 的 `derive_worker_count`，不另写第二套。**2026-09-20 用户冻结划分：seed=20260920、validation=50、test=100**（LOG-228）。test 与 validation 的成员、train 块起点与 S1 的开发 house 至此全部确定；`train_houses` 留到 S3-01 登记且只能下调。这三个值只登记在 S1-02a v2 一处，S0-02 v2 的值槽保持 null 并由跨合同测试钉住。S1-02a 六个授权位仍全为 false：用户已口头授权，但核对后确认**缺 runner 与 S0-02 六个路线/干预数值**，开了也跑不了，故记录授权、位不打开（LOG-229）。服务器已同步到受审提交，权威全量 **1249/1249 通过**（首次全绿）；同一次运行查出冻结摘要钉的是行尾表示而非内容，三处坏钉已修。**2026-09-20 冻结三个路线幅度**（translation 0.25／rotation 90／look 30，前两个与 `source` 网格一致并由校验器绑定），追加 S0-02 v3；仍缺 `maximum_actions`、`maximum_interventions_per_episode`、`minimum_yield` 三个数值。runner 勘定结论：驱动代码可复用 ops 的 CloudRendering 模板，但**覆盖式重访路线规划器与干预选择策略尚无可执行规范**，属设计决定而非照规格实现，故未动手写（LOG-230）。**2026-09-20 按用户要求先出设计不写实现**：R1 路线规划与 I1 干预选择提案写入 DATA 第二节，标为 proposed／待审；`max_actions` 定为 2000 但与另两个数值一并冻结。三项待裁（覆盖口径、`add` 物体来源、视点距离区间）阻塞 runner 实现（LOG-231）。**用户初裁六项后换模型重审**：发现五处会改变数据语义的漏洞（窗口无最小长度、`move` 未重访目标、可行集须按共享窗口联合算、观察须按 196 px 定义、缺空过渡）与四处工程风险；初裁大体维持，但需新增 `minimum_window_frames` 与 `p_null_window` 两个登记值，六值一起冻结后才写 runner（LOG-232）。**裁决 23／24 落地**：修订十条采纳、`minimum_window_frames`=20、`p_null_window`=0.2；版本级联改为规则才升版、摘要只钉规则、值进台账；**CloudRendering 首次真实启动成功**（5.9 s，三路帧齐），`SpawnAsset` 存在故 `add`=(b) 可冻（LOG-234）。裁决 23／24 后 R1／I1 规则已就地写入 S0-02 v3（不再开新版本），runner 已实现并真实运行：**S1-02a pilot 4 条跑完（LOG-235），S1-02b 46 条跑完但门未过**（LOG-236）：非空成品率 14/37＝0.378 ＜ 0.6，按风险表触发规模裁决；23 个失败里 21 个是执行机制（`RemoveFromScene` 挂死 7、`MoveAhead` 被挡 7、放置点 4、步数上限 3），81 个执行成功的干预全是 `add`。事后审计更发现 **87/87 个 `add` 从未进入私有真值**（`SpawnAsset` 复制件渲染但不进实例分割，LOG-237），现有非空 episode 的标签因此不可用。八项修正已写成代码、默认关闭，并在四个曾失败的 house 上 smoke 通过（4/4 成功、13/13 干预可辨）：`remove`→`DisableObject`、被挡边重规划、类型分层抽样、`add`=搬运未见真实物体、窗口内 dry-run 预筛（放一次＋视点偷看＋放回）、每容器一次放置；**2026-09-20 用户批准裁决 25～32（28 作废）并授权在新提交下重生成全部 50 条**：S0-02 v3 的 R1／I1 规则文就地修订并重钉规则摘要，runner 与选择库默认值随之改为合同规则；重生成已完成（LOG-238）：第一次（`0bfbbc2`）被编排器超时 bug 中止、整份保留为作废记录；第二次（`4bff1a8`，编排器改为心跳判卡死）50 条＝成功 32（空窗口 12、含干预 20）＋失败 18，非空成品率 S1-02b 20/36＝0.556、全 50 条 20/38＝0.526，**门 0.6 仍未过**；但 78/78 个执行的干预在扫掠二私有真值里可辨（add 27／remove 40／move 11）。**2026-09-21 用户批准裁决 33～38 并授权第三次重生成**（LOG-239）：核对扫掠二语义查出"被重访 ⇒ 有变化"是 100% 的结构捷径（20 条非空 episode 重访 44 个容器、44 个全变，10 条空窗口 episode 扫掠二 0 帧），只读重算又查出容器可见性主体封印在错误的帧上（972/1521 个容器在该帧 0 像素，可封印率 27%，U 总数 188 且偏向封闭子容器），以及 `TeleportObject` 报告成功却把物体留在 0.05～10.9 m 外、三条被记成成功的 episode 里就有（合同 `revert_failure_fails_the_house` 从未被实现）。六项裁决：**34 双生控制**（扫掠二重访被干预容器加同样多个持有已见物体的 U 内对照容器、按 RNG 交错；空窗口 episode 走同一流程只跳过执行，按同样规则失败）、**35 最佳帧封印**（只读重算：可封印 411 → 1332，U 188 → 670）、**36 move 下限**（S3-01 train 块 ≥120，源先重访 ≥60）、**37 空窗口抽签加仓库外私有盐**、**38 合格像素只数扫掠一并改写 `coverage_definition`**，规则摘要重钉 `2895f031…` → `27d5ea47…`。放回校验、连通分量内重选视点、执行期重取生成点与 Floor 排除随之落地。第三次重生成结果见下表与 LOG-239。

**S1-03 已审、已授权、生成中（2026-09-22）**：裁决 42／43 落地（`ρ_free` 登记为被 D-223 蕴含、`supported_by` 留 null、NMS 阈值按引用取代为 0.7）。开跑前修掉三处：DINOv2 预处理改为直接调用 D-218 已审提取器（原先无 ImageNet 归一化，未生成过任何 cache）、资产摘要改由 runner 对加载字节实算并对合同／登记表核验、null 登记值只拦本阶段消费的。逐帧 gzip（224 KiB/帧，全量约 8.6 GiB）、磁盘下限 abort 与 `--resume`；worker 按实测取 2（1/2/4 worker 分别 0.498/0.570/0.340 frames/s）。43 条 40,508 帧于 2026-09-22 00:03 按 `edae0b5` 启动，1 小时后因 196 像素 mask 的浮点边界 bug（逐 patch 权重求和 0.9999999999999999 < 1.0）前 5 条失败 3 条，用户批准裁决 44：停跑、旧根改名保留、`c993959` 修复（精确像素数判支持，描述子逐位不变）后于 01:57 重新启动全部 43 条，预计约 20 h（LOG-240）。

**2026-09-22 下午：S1-04 三处卡点经服务器核实属实，用户批准裁决 45～47（LOG-241）**。核实：私有面逐帧只有 x/y/z、从未保存真值整物体盒（且 S0-04 v2 的节点 P/R/F1 评价器同样要它）；召回四值 null；ReID 未训练但 `output_dimension`=128 本是 D-224-E 原话。裁决 45 取 (b)：每条 episode 在模拟器重载 house 一次读初始盒与朝向，逐帧真值盒＝初始盒＋记录平移，观测集合盒只作对照列；裁决 46：理想记忆口径认可，S1-04 出 recall_miss 曲线后一次性冻结四值；裁决 47：ReID 进 S1-04，128 维与 0.05 入台账，42 条有 cache 的开发 house 前 30 训练、后 12 选择。三份合同就地修订并重钉（S0-02/S0-03/S0-04）。cache 运行 38/43，**`train-01451` 按合同 `proposal_overflow` 失败**（87 个 ≥196 px 提案超 64 上限），S1 开发 cache 至多 42 条；另核出 cache 不存 fragment 的 mask 像素而 S0-04 的重叠标注需要它，待裁 48（见 LOG-241 第四节）。**S1-03 cache 已于 16:48 完成**：42 成 1 败、37,277 帧、399,630 色块、8.2 GB，报告导出到 `results/`（LOG-240 第五节）。裁决 45～47 的代码已按单一职责六个提交实现待审（几何核心与重载工具、诊断核心、ReID 核心、诊断 runner、S1-03 `--recover-masks`、S1-04 合同 v1），服务器全量 1432/1432 通过（LOG-241 第五节）。**同日晚用户批准裁决 48（取 (a) 只跑 SAM 的 mask 回收）并审过 S1-04 代码**：六个授权位具名打开、五个 ReID 训练值按提议冻结入台账、规则摘要重钉；服务器按顺序启动 mask 回收（后台，约 11 小时）与几何重载（LOG-242）。诊断与 ReID 训练等 mask 回收完成后运行。

## 二、状态和执行规则

**2026-09-23 当前暂停点（优先于上方历史运行状态）**：用户要求停在修正后的 S1-02，先审计空可行集与修复方向。`7c10d2c` 全 50 条为 29 成／21 败，其中 19 条空可行集＝12 条 U 为空＋7 条 U 非空但无可行干预；S1-02b 仍为 20/37，未过原门。只读归因及对既有“物理上不存在窗口”表述的纠正见 EXECUTE LOG-243。S1-03 cache 重建、S1-04 与后续训练均不推进。本轮没有改路线、窗口、阈值、抽样、规模或授权位；后续优先交付失败证据补全与路线／窗口设计提案，科学改动需先审，不按本轮事后统计截取旧窗口。

**2026-09-23 裁决 52 已落地（DECISIONS D-224-S1）**：合格物体的受体改取 `parentReceptacles` 第一个非 Floor 项、完整表写入 `provenance/object_table.json`，S0-02 规则摘要重钉 `fcd5d187…`；数据未重生成。下一步是**待裁 53**（不可观测窗口协议提案，DECISIONS 已列四个口径与只读估算），用户裁定后才改 S0-02 窗口定义、路线规划器并重生成 50 条；规模、0.6 门、move 下限与对照供给等新 pilot 数据后一起裁。 **2026-09-23 用户指示先不生成 50 条，先按 (a) 跑 8 栋做估算**（`--stage window-probe`，L=40 未冻结，产物不是 S1-02 数据；DECISIONS 待裁 53 的探针授权）。 **同日晚裁决 53 批准并落地**：窗口＝过渡最后 30 帧（DECISIONS D-224-S1 裁决 53），S0-02 就地修订重钉，生成器默认 `transition_tail`；两次探针结果记在 DECISIONS；按裁决重生成全部 50 条（S1-02a 4 栋 → S1-02b 46 栋），旧根 `lean-s1-02{a,b}-7c10d2c` 保留，生成提交须登记进 S1-03 合同后 S1-03/S1-04 重做。

**2026-09-23 裁决 53 重生成已完成并验收（LOG-243 续四）**：`5f9aa71` 全 50 条＝39 成（29 条有干预＋10 条空窗口）11 败（8 栋窗口结构性不可用＋3 栋执行期），S1-02b 非空成品率 **28/37＝0.757 过 0.6 门**，全 50 条 29/40＝0.725；move 65（源先重访 39）、对照 150 个里 93 个来自 U、`frame_write_failed` 0；报告 `results/vsmt_lean_s1_02{a,b}_report_5f9aa71.json`。**裁决 54／55 已批准取 (a)，`5f9aa71` 已登记进 S1-03 合同并重钉（`c7318cd5…`，LOG-243 续五）；下一步是 05593 生成点查因与在 39 条成功 episode 上重建 S1-03 cache**：05593 三次只读探针未复现（偶发模拟器状态，按裁决 55 (a) 不动）；cache 于 2026-09-23 15:59 CST 在 `154776d` 以 2 worker 重建到 `lean-s1-03-154776d`（39 条、44,097 帧，trial 实测 2 worker 最快），预计 9 月 24 日 08:30 CST 前后完成，完成后导出报告验收，再进 S1-04（LOG-243 续六）。旧根 `lean-s1-02{a,b}-7c10d2c` 与两个探针根保留，数据盘 19 G 可用。

**2026-09-24 S1-03 与 S1-04 已跑完，停在匹配口径门（LOG-244）**：cache `lean-s1-03-154776d` 39/39；S1-04 诊断 39/39，fragment-真值 IoU 中位 0.0004 触发第九节的匹配口径裁决，**S2 不启动**，裁决 56 (a) 的只读估算已完成（LOG-244 续：建筑结构占 65% 的行；排除后同帧并集框中位 0.368 过门），裁决 56 续（真值范围排除四类结构件、实体框改同帧并集）与裁决 58（出生半径 1.0 m）已落地（LOG-244 续二），S1 不重做，IoU 门在新口径下由估算复核（0.368）；2026-09-24 用户审过 S0 修订并授权进入 S2；**下一步：S1-05 收口（按裁决 47 的规则冻结 S1-04 已算出的描述子选择结果），然后 S2-01**，裁决 57 已冻结召回三值 k=5／k′=3／半径 3 m，第四个值 `birth_neighbourhood_radius_m` 待另裁；匹配口径本身待估算后裁定；ReID 留出按冻结规则为 30/9（选择组缺 3），选择规则结果 `reid_projection:vitb14` 待 S1-05 执行。

**2026-09-24 S1-05 已机械执行，S1 收口（LOG-245）**：按裁决 47 冻结的规则在 S1-04 报告上选定 `reid_projection:vitb14`（9 条选择 house 上中位分离度 0.236，最好的冻结描述子 ViT-B/14 为 0.143，增益 0.093 ≥ 0.05），冻结 ViT-B/14 记为论文并列报告的基线；结果记入 S0-03 `reid_adapter_head.selection_result`（新增块，规则摘要重钉 `1becb7e3…` → `37d56a90…`），常量绑定在 `lean_assignment.py`，回执 `results/vsmt_lean_s1_05_descriptor_freeze_154776d.json`。选择组按合同"跳过并计数、不顶替"只有 9 条而非 12 条（cache 39 条），登记为**待裁 59**（推荐维持）。此后不得再换描述子。**下一步 S2-01**（共同 runner 与实体记忆包装）；按 D-059 本次合同与代码改动待用户审。

**2026-09-24 S2-01 共同 runner 已实现待审（LOG-246）**：纯核心 `lean_runner.py`（实体几何为公开体积与 M_{t−1} 的纯函数、S1-05 描述子接线、固定八步的单帧流程、非法程序回滚后提交空程序并计数、ELU-P／RAC 臂状态、逐帧回执与 cache 封印门、私有侧真值表构建含 `in_scope`），合同 `lean_s2_01_runner_v1.json`（两位全 false、规则摘要首钉 `e1060695…`、唯一登记值 `entity_geometry.samples_per_axis` 为 null，登记为**待裁 60**，推荐 4），单 episode 入口 `ops/vsmt/lean_s2_01_runner.py`，测试 21 项＋跨合同 5 项。S0-04 评价器真值表放宽一处（在场但范围外的结构件可无盒，不改指标）。**下一步**：S2-02 在 S0-05 核心已含四个规则臂的 logit 与存在决定、S2-01 已把它们接进 runner 的基础上，只剩来源登记文件头与 `LLM-op` 接口；然后 S2-03 学习头与 scorer、S2-04 teacher 接线；S2-05 运行前须冻结 S0-01 五个、S0-03 两个、S0-04 五个、S0-05 九个、S2-01 一个 null 值。

**2026-09-24 S2-02 与 S2-03 已实现待审（LOG-247）**：S2-02 `lean_controls.py`——四个对照与 `LLM-op` 的 clean-room 来源登记（借了什么、改了什么、非官方实现、未抄代码，绑定 S0-05 合同的 `source` 行）、ELU-P 三个拟合量的估计式（计数退化即拒、只允许 train 且在封存之后）、`LLM-op` 接口（封存表渲染成文本、严格解析、选择转 logit 走同一求解器、只允许 validation）；S2-03 `lean_model.py`——三个代价头（LayerNorm＋两层 128 宽 GELU＋读出，合计 54,207 参数）、runner 的 scorer、登记损失（labelled／birth 进 softmax CE，gone／present 进 BCE，其余状态不进损失）、AdamW 逐帧训练与"跑满登记 epoch、取 validation 损失最低那个"的早停、AssocOnly 同架构无存在头、DAgger 两轮登记、权重摘要；候选换序 logit 跟实体走、程序不变的继续门有测试。**下一步 S2-04**（teacher 与评价器接线：从 runner 逐帧产物加私有面出标签、三分解、七项指标）；S2-05 前须冻结的 null 值不变。

**2026-09-24 S2-01～S2-03 经用户审查通过，裁决 59～63 落地（LOG-248）**：审查核对了半空间口径（D-223 材化"点在块内"为 n·p ≤ offset，runner 同式，体块与色块共用同一因果位姿）、自由空间滚动窗口 4 次观测照存读、参数数 54,207、四条来源链接与三个测试模块。批准并落地：(59) ReID 选择组维持 9 条，不改代码；(60) `entity_geometry.samples_per_axis`=4（常量绑定、台账登记、合同记 `registered_value_slots`）；(61) S2-01 校验器原要求授权位全 false 而入口要求全 true、入口永远跑不起来，改为 S1-03／S1-04 的 `activation_policy` 机制，两位仍关；(62) `fit_match_gain` 在 p_hit ≤ p_false 时拒绝；(63) 架构保持 128 宽，METHOD 与 AGENTS 的"约 4 万参数"改为 54,207；附：非法程序整帧回滚现含臂状态，合同新增布尔声称，S2-01 规则摘要重钉 `e1060695…` → `09fc1a4a…`。**下一步 S2-04**（teacher 与评价器接线）：存在标签只对 runner 的可判定行生成，`should_be_visible_min_ratio` 须先冻结；S2-05 前须核对服务器 39 份几何回执的 `objects_without_box`。S2-05 前须冻结的其余 null 值不变。

**2026-09-24 S2-04 teacher 与评价器接线已实现待审（LOG-249）**：[`lean_evaluation.py`](../src/vsmt/lean_evaluation.py)——每帧吃 runner 的一步产物与私有记录，凭回执两段封存打开私有真值，调 S0-04 的函数出目标列、存在标签、三分解、逐帧节点匹配与污染占比、假撤回、规模成本，写 S2-03 训练记录与 nuisance 行，窗口后从 S1-04 追踪器取旧/新位置算 Missing 残留率、身份连续率、恢复延迟；合同 [`lean_s2_04_evaluation_v1.json`](../configs/vsmt/lean_s2_04_evaluation_v1.json)（首钉 `40d96cf0…`，两位全 false，不登记自己的值槽）登记五条派生规则（可观察判定用臂自己的采样盒测试、旧/新位置取窗口两侧的追踪器输出、搬动的恢复起点两处任一可观察、搬动前承载实体不限状态、结构件候选一律 present）为**待裁 65**；S2-05 的运行位由哪份合同持有为**待裁 64**；入口 [`lean_s2_04_evaluate_episode.py`](../ops/vsmt/lean_s2_04_evaluate_episode.py)（runner＋teacher 同进程跑一条 episode、一个臂，位关即拒，null 值即列出拒绝）；测试 14＋跨合同 4。**下一步**：用户审 S2-04 并裁 64／65；然后 S2-05（多 episode 多臂编排、开发表）。S2-05 前须冻结 S0-01 五个、S0-03 两个、S0-04 五个、S0-05 九个 null 值，打开 S2-01／S2-04 的运行位，并核对服务器 39 份几何回执的 `objects_without_box`。

**2026-09-24 S2-04 审查通过，裁决 64／65／66 落地（LOG-250）**：裁决 64 取 (a)，S2-05 的运行位由 S2 阶段合同持有（S2-01 两位、S2-04 两位），S0 各位保持 false；裁决 65 五条派生规则全按推荐冻结；裁决 66 把 S2-05 的继续门从"不因开发差不利就改设计或删消融"改为"开发差可以促成设计修订，修订须登记为裁决、在 S3-01 冻结正式数据前完成、不读 validation/test；不选赢家、不调网格、不删消融保留"。**下一步 S2-05**：先登记开发运行的全部待冻结值（S0-01 五个、S0-03 两个、S0-04 五个、S0-05 九个、各臂网格与开发配置）并实现多 episode 多臂编排、ELU-P 拟合量计数、两轮 DAgger 训练与开发表导出；运行前打开 S2-01／S2-04 运行位并核对服务器 39 份几何回执的 `objects_without_box`。

**2026-09-24 S2-05 开发表编排已实现待审（LOG-251）**：[`lean_development.py`](../src/vsmt/lean_development.py)（校准直方图与收集器、ELU-P 拟合量计数器、开发表装配、合同校验）、合同 [`lean_s2_05_development_v1.json`](../configs/vsmt/lean_s2_05_development_v1.json)（首钉 `38314ce2…`，五趟顺序：校准→ELU-P 拟合→第 0 轮 DAgger→第 1 轮 DAgger→开发表；八个开发配置槽为 null；两位全 false）、入口 [`lean_s2_05_development.py`](../ops/vsmt/lean_s2_05_development.py)（run-pass／calibration-report／fit-elu-p／train／table，每条 episode 一个 S2-04 子进程、多 worker、按 episode_id 合并、回执续跑）；S2-04 入口新增 `--calibration`／`--elu-p-counts` 钩子；测试 7＋跨合同 3。**运行前分两批冻结**：待裁 67（跑校准趟就要的 8 个值：S0-01 dormancy 与去重四值、S0-04 dominance_min_share／delta_moved_m、S0-05 should_be_visible_min_ratio）；待裁 68（校准趟之后：各臂网格、ELU-P rollout_config、八个开发配置槽、weight_decay／seeds、nuisance 上限、reference_score_seed、S0-03 tau_r）。bootstrap_seed 与 main_gate_effect_size 留到 S3-01。**下一步**：用户审 S2-05 代码并裁 67；落值后打开 S2-01／S2-04／S2-05 运行位，核对服务器 39 份几何回执的 `objects_without_box`，跑校准趟，据其分位数提 68。

**2026-09-24 S2-05 审查通过，裁决 67 落地，六个运行位打开，校准趟开跑（LOG-252）**：八个运行必需值就地冻结（S0-01 dormancy 3、去重每 10 帧／余弦 0.9／0.25 m／IoU 0.3；S0-04 dominance 0.5、delta_moved 0.5；S0-05 should_be_visible_min_ratio 0.5），三份 S0 合同的规则摘要不变、台账登记；S2-01／S2-04／S2-05 六个位凭 activation_policy 打开（摘要重钉 `36b9fbc6…`／`f4511a34…`／`859208ee…`，位关回原钉）；服务器 39 份几何回执核对：没有任何物体缺盒；服务器全量 `1c413e0` 1584/1584。校准趟单 episode 试跑通过（`train-00702` 126 帧 54.6 s，峰值 1.25 GB，runner 每帧 0.26 s）。**校准趟停在待裁 69**：最大 episode（`train-01289`，3473 帧）试跑失败于 `truth_key_outside_geometry_table`——只读扫描 39 条 episode，28 条的私有记录含几何表没有的键：99 个 `Ceiling_room|…`（96 个曾 ≥196 像素）与 2 个 `Egg|…|EggCracked_0`；墙／房间／门／窗都在几何表里。天花板是否并入结构件、运行时生成物怎么记，是真值范围规则，登记为待裁 69。另：S2-04 入口改为流式加载（整条读入要近 20 GB），产物不变，用 `train-00702` 重跑比对。**下一步**：裁 69 后落规则、重钉 S0-04／S2-01 摘要，按最大安全 worker 数跑完 39 条校准趟，据分位数提裁决 68（网格、rollout_config、八个开发配置、weight_decay／seeds、nuisance 上限、reference_score_seed、S0-03 tau_r）。

**2026-09-24 裁决 69 落地（LOG-253）**：取 (a)——`Ceiling_room` 并入结构件清单（S0-04／S2-01／`lean_teacher.STRUCTURAL_TYPES_EXCLUDED` 五类），运行时生成物（键最后一段是"字母_数字"生成标签，如 `EggCracked_0`）记在场、范围外、无盒并计数，其它表外键仍整条失败；S2-04 的存在标签对解析到生成物的候选按结构件规则记 present。三份规则摘要重钉：S0-04 `9bf1059d…`→`7a3d661b…`、S2-01 `36b9fbc6…`→`d07f141c…`、S2-04 `f4511a34…`→`eaac36bd…`（`b4b7d80`）。至此 39 条开发 episode 都能进校准趟。**下一步**：另一会话的 11 条校准趟（`82810c0`）跑完后，在 `b4b7d80` 上重跑全部 39 条（同一提交、新根），合并直方图出 `calibration-report`，导出 `results/` 报告并提裁决 68。F1 低（试跑 0.09）不是裁决 69 要解决的事，其三个成因（单视角色块盒对整物体盒、每物体多实体而保守去重不合并、校准臂 LOW 不看外观）要等真正的开发表趟用七个臂一起诊断，属裁决 66 允许的设计修订议题。

**2026-09-24 每帧耗时被校准趟暴露，三处工程提速逐字节等价后 39 条校准趟开跑（LOG-254）**：另一会话在 `82810c0` 上的 11 条趟实测每帧 0.5～2.9 s 随实体数增长，外推 39 条要 4 小时、整条 S2-05 25～30 小时；cProfile（07270 前 120 帧）显示 `validate_memory` 每帧 9 次占 54%、`entity_geometry` 21%、纯 Python 余弦 12%。`1b89f3c`／`696fbe7`：已验证记忆对象按（id、摘要、tick、实体数）缓存不再重走；体块先按包围盒筛再做半空间判定；余弦改矩阵计算并复刻 Python 3.12 `sum()` 的补偿求和、范数保留标量路径（glibc 的 pow(x,2) 偶尔与 x*x 差一个 ULP）。服务器 worktree 上核验：00702 全程与 07270 前 120 帧的封存摘要、记忆摘要、报告、校准直方图与 `82810c0` 逐字节相同，耗时 103.7→30.3 s、245→35 s。39 条校准趟于 22:14 CST 以 10 worker 在 `lean-s2-05-696fbe7` 启动（另一会话的 3 个 worker 仍在跑）。**下一步**：趟跑完 → `calibration-report` → 导出 `results/` → 提裁决 68；同时准备节点匹配口径的只读审计（裁决 70 预告）。

**2026-09-24 节点匹配只读审计完成，提出裁决 70（LOG-255）**：`b517890` 的审计在 4 条开发 episode 上把低 F1 拆成两个各占一半的原因——一物多实体（TAF 每真值 3.5 个实体，按身份并框后 F1 0.21→0.47；裁决 67 的去重三值对照校准分位数几乎不可能满足，复核并入待裁 68）与实体框是深度表面壳、真值框是整体盒（位置对时 IoU 仍＜0.3；质心 0.5 m 口径 F1 0.41）。**待裁 70**：推荐 (a) 主指标保持 IoU 0.3、S0-04 增登质心 0.5 m 的次级节点列。校准趟 23:15 CST 时 6/39，预计 09-25 01:00～02:00 跑完；跑完后 calibration-report → 导出 → 待裁 68（含去重三值）。
**2026-09-24 裁决 70 (a) 落地（LOG-255 续，`f4f694a`）**：S0-04 新增次级节点列 `node_prf1_centroid`（同集合、同匹配器、质心距离 ≤ δ_moved 0.5 m、权重 1／(1＋距离)），S2-04 headline 与 S2-05 开发表并列报告；主列 IoU 0.3、裁决 C／V 不变；S0-04／S2-04／S2-05 摘要重钉。校准趟不重跑；后续趟在新提交上运行。服务器全量 `588fec7` **1597/1597**（含验证缓存 id 复用漏洞的修复 `0aa47cb`，LOG-254 续）。**下一步**：等校准趟跑完提裁决 68。

**2026-09-25 校准趟收尾缺陷与裁决 71（LOG-256，`cc682d7`）**：`696fbe7` 趟 5 条 1262 帧以上的 episode 在收尾崩溃、11 条"成功"回执的 nuisance 探针块为空——S2-04 入口在关闭写入流之前重读 `nuisance.jsonl.gz`（gzip 成员未完整：0 字节时读到 0 行，部分落盘时 `EOFError`）；本地用真实文件复现。修复 `cc682d7`（先关流再重读并核对行数）、服务器全量 **1600/1600**。裁决 71 (a)(a)：停趟、删 15 个部分目录、同一根 `--resume` 以 12 worker 补跑 25 条（14 条回执保留，其探针块为空、不重跑）；另一会话的旧 `82810c0` 趟按用户指示一并停掉。用户授权逐 episode 监视与工程性自行处置。**下一步**：趟跑完（预计 06:00～06:30 CST）→ `calibration-report` → 导出 `results/` → LOG-256 续 → 提裁决 68。

**2026-09-25 校准趟 39/39 跑完，提出裁决 68（LOG-256 续，`2bc05e7`）**：续跑 0 失败，合并分位数与逐 episode 报告导出到 `results/vsmt_lean_s2_05_calibration_696fbe7.json`。两条结构性读数：应可见比例 ≥0.5 的实体-帧只有 0.2%（可见体积是"深度表面之前"，实体框是表面壳）；present 候选的自由空间覆盖 p50 0.667 高于 gone 的 0.640，当前几何规则下自由空间不区分在场与消失。**待裁 68**（DECISIONS）：各臂网格、ELU-P rollout_config、八个开发配置槽、weight_decay／seeds、nuisance 上限（含 split 级判定的 scope 规则）、S0-03 两值、去重三值重定（0.8／0.5 m／0.05）、should_be_visible_min_ratio 降到 1/64 并登记几何规则修订候选、dormancy 保持 3、ELU-P 拟合量预授权。**下一步**：用户裁 68 → 一条裁决一个提交落值与重钉 → 服务器全量 → elu_p_fit → dagger_round_0 → dagger_round_1 → development_table。

**2026-09-25 裁决 68 全按推荐落地（LOG-257，`357ccdf`…`178868b`）**：五个单一职责提交把网格、rollout_config、八个开发配置槽、weight_decay／seeds、nuisance 上限（split 级 scope）、S0-03 两值、去重三值 0.8／0.5／0.05、应可见 1/64 就地冻结并绑定常量，S0-01／S0-05／S0-04 重钉，服务器全量 `178868b` **1605/1605**。run-pass 入口从此只按登记的臂与配置跑每一趟。校准趟不重跑；elu_p_fit 趟 15:01 CST 开跑（12 worker，新根 `lean-s2-05-178868b`），同一 4 条 episode 的节点审计按 LOG-255 配置重跑作前后对照。**下一步**：审计对照读数（LOG-257 续）→ fit-elu-p → 登记三个拟合量并重钉 S0-05 → dagger_round_0 → 训练 → dagger_round_1 → 训练 → development_table 六臂 → table → 导出。

| 状态 | 含义 |
|---|---|
| 已完成 | 代码和必要测试已经受审，或已有可复用的真实证据 |
| 已实现待授权 | 代码已提交并通过测试，但步骤合同中的真实执行授权位仍为 false |
| 未开始 | 依赖未满足，尚不能产生正式产物 |
| 封存 | 已确定但当前阶段禁止打开或使用 |

真实运行的授权由步骤合同里的布尔位表达并由用户在运行前审；真实运行要求 clean checkout，并逐次记录 git commit、合同摘要、输入摘要、产物摘要、worker 数与退出码、资源用量和全部失败。表格中的"完整动作"是必须完整执行的规范，不是可以挑着做的菜单。不能运行成功的 house 或 episode 必须留下失败 receipt，不得省略、替换或补样。测试夹具只证明代码行为；真实步骤只有服务器产物、摘要和退出回执齐全才算完成。

## 三、S0：合同冻结

### S0-01 实体记忆 schema 与五原子程序合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已完成、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-19 用户审过，LOG-214；v2 按 D-224-X 裁决 X6 给版本记录加 `opened_by` 并写明折叠记录归档口径，本地 47 项通过，LOG-225） |
| 输入 | METHOD 第三、四节；`cpmt.hashing` 与 `graph_ops` 的纯函数 |
| 完整动作 | 写实体记录 schema、状态机、版本链、五原子结构前条件、REPLACE 复合、帧程序原子提交与回滚、共享去重与 dormancy 规则、**实体 token 序列化 schema 与帧级稀疏残差（D-224-G）** 的机器合同；实现自足的实体记忆核心并补测试 |
| 输出 | [`lean_s0_entity_memory_v2.json`](../configs/vsmt/lean_s0_entity_memory_v2.json)（v1 字节冻结）、纯核心 [`lean_memory.py`](../src/vsmt/lean_memory.py)、合同测试 [`test_vsmt_lean_memory.py`](../tests/test_vsmt_lean_memory.py) |
| 继续门 | 五原子正反例各至少一组通过；非法程序整帧回滚且 M_{t−1} 逐字节不变；token 字段顺序由合同固定并有测试 |

### S0-02 干预数据生成合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已完成、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-19 用户审过，LOG-215；v2 按 D-224-X 裁决 X6 把前缀分配顺序改为 test→validation→train，本地 43 项通过，LOG-225） |
| 输入 | DATA 第一～四节；D-199～D-204 的不可观测窗口机制 |
| 完整动作 | 写 house 来源、哈希前缀划分、覆盖式重访路线模板、三类干预及其窗口判定、public/private/provenance 三面 schema、失败保留规则的机器合同；全部数值先登记为 null 或 proposed |
| 输出 | [`lean_s0_intervention_data_v2.json`](../configs/vsmt/lean_s0_intervention_data_v2.json)（v1 字节冻结）、只读检查核心 [`lean_intervention.py`](../src/vsmt/lean_intervention.py)、测试 [`test_vsmt_lean_intervention.py`](../tests/test_vsmt_lean_intervention.py) |
| 继续门 | 干预只在涉及容器不在视锥内的窗口执行；private 与 provenance 不进任何 reader 白名单 |

### S0-03 特征、召回与分配合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-20 通过，D-224-R；v2 按 D-224-X 裁决 X5 把字典序规范化改到等式子图上、与 v1 逐列等价，64×500 单帧 125 秒 → 0.01 秒，本地 58 项通过，LOG-225） |
| 输入 | METHOD 第五～七节 |
| 完整动作 | 写前端 cache 字段、应可见与自由空间覆盖比例、召回规则 k/k′/R_active、三个头的特征列表与顺序、代价矩阵与并列规则、封存 digest、私有扰动不变性检查的机器合同；**登记共享 ReID 适配头（D-224-E）的架构、训练数据范围与 S1-05 二选一规则** |
| 输出 | [`lean_s0_assignment_v2.json`](../configs/vsmt/lean_s0_assignment_v2.json)（v1 字节冻结）、纯核心 [`lean_assignment.py`](../src/vsmt/lean_assignment.py)、测试 [`test_vsmt_lean_assignment.py`](../tests/test_vsmt_lean_assignment.py) |
| 继续门 | 同一公开输入换 private 文件后召回顺序、特征矩阵与未训练 logits 逐字节相同 |

### S0-04 teacher、评价器与指标合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-20 通过，LOG-219；v2 按 D-224-X 落实 X1 同帧重复色块、X2 未定义 house、X5 评价器分连通块匹配、X6 生命周期版本数与真值表 `in_scope`，合同 53 条布尔声称全绑定，本地 88 项通过，LOG-225；复审修正 X1 组级记账、X2 不适用臂例外、范围外实体退出精确率分母） |
| 输入 | METHOD 第八、十一节；DATA 第六、七节 |
| 完整动作 | 写标签定义、δ_moved、七项指标、匈牙利匹配口径、bootstrap 与主门、三分解记账、nuisance probe 的机器合同 |
| 输出 | [`lean_s0_teacher_metrics_v2.json`](../configs/vsmt/lean_s0_teacher_metrics_v2.json)（v1 字节冻结）、纯核心 [`lean_teacher.py`](../src/vsmt/lean_teacher.py)、测试 [`test_vsmt_lean_teacher.py`](../tests/test_vsmt_lean_teacher.py)；只依赖 S0-03 产物的数据形状，不导入其函数 |
| 继续门 | 指标清单在任何数据生成前冻结；清单外指标不得计算或报告 |

### S0-05 对照、消融与配置网格合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-20 通过，LOG-219；v2 按 D-224-X 落实 X3 AssocOnly/HeuristicLabel 同配方重训不复用权重、X4 预登记 ELU-P `rollout_config` 与三个拟合量的估计程序，合同 73 条布尔声称全绑定，本地 44 项通过，LOG-225；复审修正 HeuristicLabel 私有依赖声称） |
| 输入 | METHOD 第九、十节；D-224-R 三项前提：规则臂门内分级代价（−余弦 / 质心距离）、每个规则臂网格含宽门或无门选项、不合格格用登记的哨兵 logit 表达 |
| 完整动作 | 写 TAF/ELU-P/RAC/LOW 的机制、参数与有限网格，VSMT-lean 训练配方与 τ_r 网格，**四组**消融（NoVersion/HandCost/HeuristicLabel/**AssocOnly**）定义，每方法 ≤12 配置规则，**必做附录臂 `LLM-op` 的 validation-only 口径**与可选臂 **`VSMT-lean-ctx`（D-224-F）** 的准入条件与单列报告规则 |
| 输出 | [`lean_s0_arms_v2.json`](../configs/vsmt/lean_s0_arms_v2.json)（v1 字节冻结）、纯核心 [`lean_arms.py`](../src/vsmt/lean_arms.py)、测试 [`test_vsmt_lean_arms.py`](../tests/test_vsmt_lean_arms.py)；规则臂只产生喂给 S0-03 求解器的 logit 与存在决定，特征按封存顺序取位置 |
| 继续门 | 每方法网格 ≤12 且预登记；规则臂无梯度 |

### S0-06 用户合同审查

| 项 | 内容 |
|---|---|
| 状态 | **v1 已通过；v2 已提交（本会话复审后用户批准，LOG-225）**（2026-09-20 用户批准 S0-01～S0-05 v1；同日 D-224-X 隐患审查后五份 v2 待用户代码审查；跨合同一致性由 `test_vsmt_lean_cross_contract.py` 机器核对，20 项通过，含五份 v1 的 sha256 钉住与 D-224-X 六项跨合同一致性） |
| 输入 | S0-01～S0-05 全部合同与测试 |
| 完整动作 | 用户逐份审查；修改只能追加新版本，不改已审字节 |
| 输出 | 审查回执；S1 授权位仍为 false |
| 继续门 | 用户批准后才可申请 S1 授权；**S1-01 资产与容量授权申请材料按用户要求留到下一次会话准备，本次不申请任何授权** |

## 四、S1：前端与数据小试

### S1-01 资产与服务器容量

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过（2026-09-20 用户代码审查）、v2 已提交待审**（LOG-220～224、226；v1 字节冻结并由跨合同测试钉住摘要；v2 只做三件事：`depends_on` 改指 S0 v2、`headroom_fraction` 冻结为 0.2、S1↔S0 一致性交给 `test_vsmt_lean_cross_contract.py` 机器核对（+9 项）。S1-01 本身 83 项、八个 lean 模块分进程共 401 项本地通过；九项资产登记完整、四项冲突全部有回执、**待冻结 null 已清零**；按 D-224-S1 开四个位，未放置任何资产、未装模拟器） |
| 输入 | D-215 冻结的 SAM 2.1 摘要；LOG-136 来源回执登记的 DINOv2、AI2-THOR、ProcTHOR 标识；ProcTHOR-10K 由 D-224-S1 定为 0.1.2 并按上游 LFS 指针登记；DINOv2 ViT-B/14 由 LOG-223 一次性登记，URL 从钉死的 dinov2 commit 源码推导并经 ViT-S/14 回执实证 |
| 完整动作 | 写资产登记、许可证登记、容量探测清单、worker 推导规则、两份回执字段与停止条件的机器合同；用户授权后才下载并核对资产摘要；探测 CPU、RAM、GPU 显存、磁盘、渲染后端；按单 worker 实测占用定最大安全 worker 数 |
| 输出 | [`lean_s1_assets_capacity_v2.json`](../configs/vsmt/lean_s1_assets_capacity_v2.json)（v1 字节冻结）、纯核心 [`lean_assets.py`](../src/vsmt/lean_assets.py)、测试 [`test_vsmt_lean_assets.py`](../tests/test_vsmt_lean_assets.py)；授权后另出资产回执与容量回执 |
| 继续门 | 登记在获取之前；标识不全的资产不可获取（当前九项全部登记完整）；摘要不符即停且不得换镜像、换版本或先用着；worker 数有实测依据并写进回执——容量读数已有，但单 worker 实测占用尚未测量，因此 worker 数仍不可算 |

### S1-02a 4-worker pilot 与占用实测

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交待审；划分已冻结**（LOG-227/228；seed=20260920、validation=50、test=100 于 2026-09-20 冻结，`train_houses` 留到 S3-01；本地 54 项只读检查通过，九个 lean 模块分进程共 464 项通过。六个授权位仍全为 false，未跑任何 episode） |
| 输入 | S0-02 v2 合同（**seed 与 test/validation 规模须先冻结**，因为 v2 把分配顺序改为 test→validation→train，train 块的起点由它们决定；裁决 X6）、S1-01 容量读数与 worker 推导规则 |
| 完整动作 | 取 train 块哈希前缀最前的 **4 个 house，4 个 worker 各跑 1 条 episode**：覆盖式重访路线、不可观测窗口干预、public/private/provenance 三面写盘；同时实测 `cpu_cores_per_worker`、`ram_gb_per_worker`、`vram_gb_per_worker`、`disk_gb_per_worker` 与 4 路并发是否安全；失败 house 保留 receipt 不替换 |
| 输出 | [`lean_s1_02a_pilot_v2.json`](../configs/vsmt/lean_s1_02a_pilot_v2.json)（v1 字节冻结）、纯核心 [`lean_pilot.py`](../src/vsmt/lean_pilot.py)、测试 [`test_vsmt_lean_pilot.py`](../tests/test_vsmt_lean_pilot.py)；授权后另出 4 条 raw、pilot 生成回执与**占用回执**（含 `concurrency_verified_at=4`、峰值 RSS/显存/磁盘、墙钟与退出码） |
| 继续门 | 四条全部有终态；占用五项齐全才允许推导 worker 数。**这 4 条是正式 S1-02 样本的一部分，计入 50，不得跑完丢弃重生成**；pilot 失败不构成"重试到好为止"的理由 |

**白话：为什么先跑 4 个。** 它解决的是"worker 数要由实测决定，可实测又必须先跑起来"这个先有鸡还是先有蛋。输入是 4 个 house 和 4 个并发 worker，输出是能不能跑通加一份占用读数。例如实测每 worker 峰值 6 GB 内存、2 GB 显存，就能算出这台机器还能开多少个。它**不等于**已经证明更大并发安全：pilot 只验证了 4 路，`concurrency_verified_at` 与算出来的 `derived_worker_count` 必须分开记；扩产后若出现不稳定，如实报告，不得事后把数字悄悄改小当没发生。

### S1-02b 扩到 50 house

| 项 | 内容 |
|---|---|
| 状态 | **重新生成已完成（2026-09-23，`7c10d2c`，LOG-242 第十节）：46 条 27 成 19 败，非空成品率 20/37＝0.541，0.6 门未过；move 只有 7 个（源先重访 6）、U 内对照 2/56；窗口验收 29/29 全部 `agrees`、79/79 条干预满足冻结规则。选择偏置已量化：成功 episode 容器数中位 41、失败 14。待规模裁决。** 裁决 50 已批准（2026-09-22）：用修好的编码器重新生成全部 50 条，mask 回收已停，旧 episode 根与 cache 根改名保留（LOG-242 第六、七节）。 起因是只读复核发现不可观测窗口 U 在正确位姿下基本不成立。 当初记录的 633 个窗口内不可见容器判定里，424 个的容器被模拟器当帧画出（中位 1,227 像素）；按裁决 49 修正位姿重算，U 降到 243 个、与渲染器一致（10 个残留、中位 67 像素），42／43 条 episode 判定改变，对照在 43／43 条上复现了当初的计算。按 S0-02 冻结的窗口规则重问 158 条已执行干预，只有 31 条（严格口径 24 条）仍成立，33 条有干预的 episode 里只有 2 条全部成立，非空成品率由 0.838 掉到 2／37＝0.054。下面的原记录是当时的结论，保留不改写。 三次运行的报告与 LOG 全部保留；首跑与第二次的服务器原始产物（`lean-s1-02b-159654f` 5.3 GB、`lean-s1-02b-4bff1a8` 6.1 GB）已于 2026-09-22 按用户授权删除，其 `results/` 报告与逐 episode 汇总仍在（LOG-240）。首跑 `159654f`：0.378、门未过且 add 真值缺失（LOG-236／237）。裁决 25～32 后在 `4bff1a8` 重生成（LOG-238）：非空成品率 0.556，门未过，78/78 个干预可辨；中间一次 `0bfbbc2` 被编排器 bug 中止。裁决 33～38 后在 `c222c51` 第三次重生成，触顶的 6 条按裁决 40 在 `a397d16` 重生成（LOG-239）：46 house 成功 40、失败 6，非空成品率 **0.838**，门 0.6 通过；move 44 个（源先重访 31）；8 worker，墙钟 186 分钟。一次 `c00db92` pilot 因发现放回漏洞被主动中止，产物保留 |
| 输入 | S1-02a 占用回执；S1-01 的 worker 推导规则与已冻结的 `headroom_fraction`＝0.2（每项可用资源打八折再除以单 worker 占用） |
| 完整动作 | 按 S1-01 公式算出最大安全 worker 数并记下瓶颈项，用该并发补齐哈希前缀其余 **46 个 house**，各生成一条 episode；失败 house 保留 receipt 不替换 |
| 输出 | 合计 50 条 raw、生成回执、干预成品率、`requested/actual` worker 数与资源用量 |
| 继续门 | 计划数＝成功数＋失败数；成品率写入回执；低于 S0-02 登记下限触发规模裁决，**不得换 house 挑好样本** |

### S1-03 共享前端 cache

| 项 | 内容 |
|---|---|
| 状态 | **等 S1-02 规模裁决（LOG-242 第十节）：重新生成的 50 条成品率 0.541 未过 0.6 门、move 只有 8 个、U 内对照 2/56，cache 规模与是否重建需先定 S1-02 的房屋数。** 裁决 50／51（2026-09-22）：旧 cache 根已导出记录后删除（数据盘 20 GB 已用、31 GB 可用）；cache 将在重新生成的 S1-02 数据上重建，并按裁决 51 在生成时直接写 mask（合同新增 `fragment_masks`，规则摘要重钉 `ee591bec…`），不再单独跑 SAM 回收。** 裁决 49（2026-09-22 晚，LOG-242 第三、四节）：`c993959` 这份 cache 的质心、AABB、表面与两个体积因 S1-02 公开位姿 pitch 符号错误全部作废，旧根改名保留、不续跑；描述子与回收的 mask 有效。重建口径已落地待跑：位姿按合同 `public_pose_correction` 在读取时翻回符号（合同重钉 `082e1c02…`），`--masks-from <旧根>` 读回收 mask 免跑 SAM，等 mask 回收结束后重建到新根 `lean-s1-03-<commit>`，开跑前 trial 实测 worker 数。** 原记录：**已完成（2026-09-22 16:48，`c993959`，2 worker，墙钟 14.5 h）：42 成 1 败（`train-01451` 按合同 `proposal_overflow` 失败，87 个 ≥196 px 提案超 64），37,277 帧、399,630 色块、8.2 GB，每帧色块峰 9～11、最大 58、无一帧贴顶；报告 [`results/vsmt_lean_s1_03_report_c993959.json`](../results/vsmt_lean_s1_03_report_c993959.json)；首次 `edae0b5` 因 196 像素边界 bug 停掉并保留（裁决 44）；cache 不存 fragment mask，回收模式 `--recover-masks` 已实现待裁 48（LOG-240 第五节、LOG-241）**；已审、已授权（合同 [`lean_s1_03_frontend_cache_v1.json`](../configs/vsmt/lean_s1_03_frontend_cache_v1.json)、纯核心 [`lean_frontend_cache.py`](../src/vsmt/lean_frontend_cache.py)、测试 45 项、runner [`lean_s1_03_cache.py`](../ops/vsmt/lean_s1_03_cache.py)）。2026-09-22 裁决 42：`ρ_free` 登记为已被 D-223 自由空间配置蕴含（隐含 1.0，三条代码依据）、`supported_by` 维持 null、五个授权位在 `activation_policy` 具名打开；裁决 43：D-215 的 box/crop NMS 阈值 1.0 → 0.7 按引用取代（D-215 字节未改，生效配置与摘要登记在 S1-03 合同），因为冻结配置在真实帧上每帧约 500 个 mask、9/9 帧超 64 上限。资产四项摘要核验一致，ViT-B/14 已按登记下载核验，`sam2` 包已从钉死仓库安装。运行见 LOG-240 |
| 输入 | S1-02b public 面、S1-01 资产；前端参数**全部按引用绑定** D-215 与 D-223（`frontend_config_sha256` = `f1fb5839…`），本阶段不新定义任何前端参数 |
| 完整动作 | 跑 F-01 reader 生成 fragment、几何、自由空间、可见体积；同时提取 ViT-S/14 与 ViT-B/14 两套描述子；写逐帧与逐 episode 封印 |
| 输出 | 43 条 cache（S1-02 成功的 3＋40 条；逐帧 `NNNN.cache.json.gz`，封印覆盖解码后的对象）、fragment 成品率、每帧 proposal 数分布（含贴着 64 上限的那一档）、每条 episode 的实测显存／内存／秒数／字节 |
| 继续门 | 任一帧 proposal 溢出即该 episode construction failure；每帧投影出的视图必须通过 S0-03 的 `validate_cache_frame`；包围盒与冻结 `extent_m` 完全一致；cache 不含任何私有派生量 |

**实现时发现的两处，已由裁决 42 解决（见 DECISIONS）；另一处由裁决 43 解决——冻结的 SAM 生成器配置关闭了 NMS，与 64 上限在真实帧上无解，两个 NMS 阈值按引用取代为 0.7。以下保留当时的记录：**

1. **`ρ_free`（自由空间可靠性门）在 METHOD 里是 null。** 它可能已被 D-223 已冻结的自由空间配置（最小深度、近轴深度、表面余量、最大轴向深度、最小纵向厚度）完全蕴含，也可能需要一个独立的门。二选一：冻结一个数，或登记「已被 D-223 配置蕴含」并说明依据。**不得在 runner 里默默取默认值**——runner 现在会因为它是 null 而直接拒绝运行。
2. **`supported_by` 的五个几何阈值从未被任何合同冻结过。** D-215、D-223 与全部 lean 合同里都没有这五个值，而实现 `materialize_public_relations` 需要它们。好在 D-224 裁决 B 把关联特征改成了纯几何的 `support_height_difference_m`，**没有任何特征读 `supported_by`**，S0-03 的校验器也明确允许它为 null。因此本阶段把字段写 null 并把五个阈值登记为待冻结；这不阻塞 S1-04、S1-05 或 S2。

**另一处实现时必须补的缺口（不是待裁，已按合同解决）：** 冻结前端的 region 记录只有点云均值 `centroid_m` 与包围盒尺寸 `extent_m`，而均值不是盒心，两者**推不出** S0-03 要的 `aabb_min_m`／`aabb_max_m`。本阶段用同一份反投影世界点直接取 min/max，并由测试钉住 `aabb_max − aabb_min` 与冻结 `extent_m` 逐字节相同，一旦上游反投影分叉即刻失败。

### S1-04 前端诊断

| 项 | 内容 |
|---|---|
| 状态 | **2026-09-22 用户审过代码并批准裁决 48：六个授权位在 `activation_policy` 具名打开，五个 ReID 训练值按提议冻结（0.07 / 20 / 512 / 0.001 / 20260922），规则摘要重钉 `29335861…`；mask 回收与几何重载已在服务器启动（LOG-242）。** 交付物：合同 [`lean_s1_04_frontend_diagnostics_v1.json`](../configs/vsmt/lean_s1_04_frontend_diagnostics_v1.json)（六个授权位全 false，五个 ReID 训练值为 null）、几何纯核心 [`lean_object_geometry.py`](../src/vsmt/lean_object_geometry.py) 与重载工具 [`lean_s1_04_object_geometry.py`](../ops/vsmt/lean_s1_04_object_geometry.py)（裁决 45）、诊断纯核心 [`lean_frontend_diagnostics.py`](../src/vsmt/lean_frontend_diagnostics.py)（裁决 46）、ReID 核心 [`lean_reid_head.py`](../src/vsmt/lean_reid_head.py)（裁决 47）、诊断 runner [`lean_s1_04_diagnostics.py`](../ops/vsmt/lean_s1_04_diagnostics.py)、S1-03 runner 的 `--recover-masks` 模式（待裁 48）；六个新测试模块共 37 项本地通过，S1-04 v1 规则摘要已钉进跨合同测试。前置：S1-03 cache 收尾（42/43，01451 溢出失败，至多 42 条）、待裁 48（fragment mask 回收）、用户审代码并冻结五个 ReID 训练值。**2026-09-22 晚 GPT Astra 审查的六项代码缺口已修（LOG-242 第二节）**：诊断 runner 按读到的字节重算每帧封印与每个 mask 的像素摘要（改描述子或改 mask 像素而保留摘要串的反例现在被拒）；30/12 留出在跑任何诊断之前按 42 条 cache 成员冻结，诊断失败只记本组缺口、不跨组补位；ReID 投影在选择 house 上同时报分离度与召回曲线（与对应冻结描述子同房对照）；训练发散登记 `training_diverged`、不写权重、不进选择规则、退出码 1；已有输出根不加 `--resume` 拒绝，`--resume` 复用成功/失败回执、只跑无回执 episode、旧阶段回执改名保留、已有权重只复用不重训；mask 回收续跑保留失败回执不重试；整条无可标注色块的 episode 记零标注、诊断未定义而非私有面损坏。**暂停（LOG-242 第三节）**：几何重载的帧 0 包含率残差中位 0.0，只读探测查明为 S1-02 runner `camera_pose` 的 pitch 符号反了（cache 里相机朝上 30°，agent 实际朝下 30°；符号改回后 34 个物体的包含率中位 1.00）；S1-03 cache 的质心、AABB、表面与两个体积都在随 yaw 变化的错误系里，描述子与 mask 不受影响。裁决 49 已落地（LOG-242 第四节）：几何工具与诊断 runner 的位姿读取与 S1-03 runner 共用同一修正入口（`lean_public_pose.py`），未登记提交拒绝；几何重载在 cache 重建前重跑一次（约 3 分钟）取修正后的残差；诊断 runner 只在新 cache 有回执之后运行；mask 回收继续跑完，产物由重建复用 |
| 输入 | S1-03 cache；S1-02 三面产物（private 在 cache 封印之后打开；本阶段是诊断，唯一的训练是裁决 47 的共享 ReID 投影头——一次训练、不属于任何臂、只在选择 house 上评分）；ProcTHOR 源与模拟器环境（裁决 45 的一次重载） |
| 完整动作 | 量冻结描述子（ViT-S/14、ViT-B/14）与共享 ReID 投影三者的跨视角分离度分布，即同物体跨视角余弦减异物体余弦；按 S0-03 召回规则算 recall_miss@k（冻结描述子在全部开发 cache 上、投影与其对应冻结描述子在 12 条选择 house 上）；应可见与自由空间覆盖比例**不在本阶段统计**——机器合同 `coverage_ratios.status=deferred_to_s2_01`，两者依赖各臂的 M_{t−1}，由 S2-01 的五臂共用在线函数计算；**统计单视角 fragment AABB 对真值整物体 AABB 的三维 IoU 分布**（BIND 用单视角 AABB 覆盖实体 AABB，而节点匹配用裁决 C 冻结的 IoU 0.3、选配置又用节点 F1；中位 IoU 不到 0.3 是已冻结的暂停门，触发匹配口径裁决，不能直接推成所有臂 F1 必然接近零——F1 还取决于 S2 的 AABB 累积与匹配实现，只能说选参分辨力有风险；D-224-X）。**裁决 45～47 追加（2026-09-22）**：(45) 真值盒来源为每条 episode 在模拟器重载一次读初始 `axisAlignedBoundingBox` 与朝向，逐帧盒＝初始盒＋私有记录平移、换到 episode 系，写按 episode 的私有 `object_geometry.json`；工具报未干预物体的位置漂移与帧 0 反投影包含率作残差；观测集合盒只作对照列。(46) recall_miss 曲线用理想记忆（每个真值物体一条实体、描述子与质心取其此前带标签 fragment 的均值）在开发 cache 上按 k、k′、半径网格报，曲线出来后一次性冻结四值。(47) ReID 投影 128 维，在开发 cache 的前 30 条 house 上用私有实例标签训练一次，只在后 12 条上量分离度 |
| 输出 | 分离度报告、recall_miss 报告、fragment-真值 IoU 报告 |
| 继续门 | 分离度低于 S0-03 登记下限触发证据层级裁决，不得就地调前端；fragment-真值中位 IoU 低于 0.3 触发匹配口径裁决，不得在 S2 就地改 AABB 累积规则 |

### S1-05 描述子选择与 S1 收口

| 项 | 内容 |
|---|---|
| 状态 | **已执行待审（2026-09-24，LOG-245）**：按裁决 47 的规则在 S1-04 报告上机械选定 `reid_projection:vitb14`（选择 house 9 条：投影中位分离度 0.236，最好的冻结描述子 ViT-B/14 为 0.143，增益 0.093 ≥ 0.05），冻结 ViT-B/14 记为并列报告基线；工具 [`lean_s1_05_select_descriptor.py`](../ops/vsmt/lean_s1_05_select_descriptor.py) 从 cache 封印重算留出、重算规则并与报告核对后写回执 [`vsmt_lean_s1_05_descriptor_freeze_154776d.json`](../results/vsmt_lean_s1_05_descriptor_freeze_154776d.json)；结果记入 S0-03 `reid_adapter_head.selection_result` 并由 `lean_assignment` 四个常量绑定；测试 [`test_vsmt_lean_s1_05_selection.py`](../tests/test_vsmt_lean_s1_05_selection.py) 10 项。选择组缺 3 条（cache 只有 39 条）按合同"跳过并计数"处理，登记待裁 59。原规则文：投影只在开发 cache 的后 12 条 house 上量分离度，中位分离度比最好的冻结描述子高 ≥0.05 余弦才入选，否则保留冻结描述子 |
| 输入 | S1-04 报告 |
| 完整动作 | 按 S0-03 登记的规则在冻结描述子与共享 ReID 投影中选一次并冻结（选择只看 12 条选择 house，训练 house 的分离度只作附注不作依据）；写 S1 收口回执 |
| 输出 | 描述子/投影冻结回执；若选中 ReID 投影，另记冻结描述子基线以供论文并列报告 |
| 继续门 | 此后不得再换描述子 |

## 五、S2：五臂开发表

### S2-01 共同 runner 与实体记忆包装

| 项 | 内容 |
|---|---|
| 状态 | **已实现并经用户审查（2026-09-24，LOG-246 实现、LOG-248 审查与修正）**：纯核心 [`lean_runner.py`](../src/vsmt/lean_runner.py)——实体几何 `entity_geometry`（M_{t−1} 每个实体包围盒上 s×s×s 均匀格心落进本帧可见体积块／自由空间块并集的比例，六半空间判定、容差 1e-9、固定顺序点积，s 为登记值）、描述子接线（只接受 `reid_projection:vitb14` 与基线 `vitb14`，权重摘要先核对）、单帧八步 `run_frame`（几何→视图→封存 A→臂 logit 与一次求解→封存 B 与放行回执→存在判定→按词表编译并原子提交→回执；非法程序回滚后提交空程序、tick 推进、计数；NoVersion 提交后删 retracted；ELU-P／RAC 臂状态随匹配更新并按存活实体修剪）、`run_episode`／`episode_summary`／`assert_identical_cache_across_arms`（继续门）、私有侧 `TruthTableBuilder`（`in_scope` 用 `in_truth_node_scope`，可观察＝私有 mask ≥196 像素一次，结构件在场范围外无盒，其它不在几何表的键整条失败）；合同 [`lean_s2_01_runner_v1.json`](../configs/vsmt/lean_s2_01_runner_v1.json)（两位全 false，`entity_geometry.samples_per_axis` null 待裁 60，摘要首钉 `e1060695…`）；入口 [`lean_s2_01_runner.py`](../ops/vsmt/lean_s2_01_runner.py)（单 episode 单臂，位关即拒，登记值 null 即列出拒绝，流式写回执）；测试 [`test_vsmt_lean_runner.py`](../tests/test_vsmt_lean_runner.py) 21 项。学习臂 logit 由 S2-03 的 scorer 提供（键须与封存行一一对应）。S0-04 `_truth_table` 放宽：在场但范围外对象可无盒。审查修正（LOG-248）：裁决 60 冻结 `samples_per_axis`=4；裁决 61 授权位改 `activation_policy` 机制；非法程序回滚含臂状态（`frame_step.arm_state` 新增布尔声称，规则摘要 `e1060695…` → `09fc1a4a…`）；测试 23 项 |
| 输入 | S0-01、S0-03 合同；S1-05 cache |
| 完整动作 | 实现 `cache 帧 + M_{t−1} → 帧程序 → M_t` 的共同 runner；共享召回、去重、dormancy、应可见判定与共同更新后审计；**`entity_geometry` 由五臂共用的确定性函数从（公开体素集，M_{t−1}）在线算出并有纯函数测试**；**非法程序回滚后对该帧提交空程序**（tick 推进、维护规则照常）并计数（D-224-X） |
| 输出 | runner、接口测试 |
| 继续门 | 五臂读取逐字节相同的 cache clone |

### S2-02 四个对照实现

| 项 | 内容 |
|---|---|
| 状态 | **已实现并经用户审查（2026-09-24，LOG-247 实现、LOG-248 审查与修正）**：S2-02的代价与存在决定在 S0-05 核心 [`lean_arms.py`](../src/vsmt/lean_arms.py)（已审）中、由 S2-01 runner 接线；本步补 [`lean_controls.py`](../src/vsmt/lean_controls.py)——`CONTROL_PROVENANCE`（TAF／ELU-P／RAC／LOW／LLM-op 各自借的机制、与来源的差别、`not_an_official_implementation`、`upstream_code_copied=False`，`contract_source` 与 S0-05 合同 `source`／`input` 行逐字绑定；TAF 与 ELU-P 有可核的 arXiv／RSS 链接，Perpetua／DSG／Mem0 以题名登记、链接在写作阶段补）、ELU-P 三个拟合量的估计式 `fit_initial_log_odds`／`fit_persistence_log_decay`／`fit_match_gain`／`fit_elu_p_quantities`（按 S0-05 v2 定义，计数为零或先验为 0/1 直接拒绝不硬钳，只允许 split=train、seals_written=True、rollout_config 全冻结；逐 episode 计数留给 S2-04/S2-05 用 teacher 身份做）、`LLM-op` 接口（`render_frame_text` 把封存 A 的候选与新建选项、阶段 B 的可判定实体按冻结顺序 4 位小数渲染成文本，`parse_llm_response` 每行一选且只能选渲染过的选项，`choices_to_logits` 选中对 0／未选对哨兵／BIRTH 选中 0 否则 −1 喂同一求解器（两色块争一实体时另一方按求解器规则退到 BIRTH），`llm_op_frame` 只允许 validation；prompt 措辞登记为 `not_in_this_stage`）；测试 [`test_vsmt_lean_controls.py`](../tests/test_vsmt_lean_controls.py) 8 项。runner 仍拒绝 LLM-op。审查修正（LOG-248，裁决 62）：`fit_match_gain` 在 p_hit ≤ p_false 时拒绝（`fit_degenerate:gain_not_positive`），否则拟合"成功"而 S2-05 第一帧才被 `elu_p_observe_matches` 拒绝 |
| 输入 | S0-05 合同；现有 `baselines.py` |
| 完整动作 | clean-room 实现 TAF、ELU-P、RAC、LOW 的代价矩阵与存在决定；文件头登记来源、差异与 not-an-official-implementation；`LLM-op` 实现接口与 validation-only 入口，不在 S2 调用 |
| 输出 | 四臂代码与分支测试 |
| 继续门 | 阈值全部来自无默认值配置 |

### S2-03 VSMT-lean 实现

| 项 | 内容 |
|---|---|
| 状态 | **已实现并经用户审查（2026-09-24，LOG-247 实现、LOG-248 审查；裁决 63 保持架构、改文档数字）**：[`lean_model.py`](../src/vsmt/lean_model.py)——`make_heads`（关联 14 维、存在 12 维、新建 4 维各一头：LayerNorm(输入)→Linear(·,128)→GELU→Linear(128,128)→GELU→Linear(128,1)，合计 54,207 参数；METHOD 原写"约 4 万"，裁决 63 保持 128 宽并把 METHOD 与 AGENTS 的数字改为 54,207）、`LeanScorer`（S2-01 的 scorer 接口，键恰为封存行，特征按冻结顺序取位置，AssocOnly 无存在头）、`frame_loss`（合同原句：逐色块在［召回列…, BIRTH 列］上 softmax 交叉熵＋逐实体存在 BCE 等权；只有 labelled／birth 目标与 gone／present 标签进损失，recall_miss／unlabelled／identity_ambiguous／duplicate_of_labelled 与身份含糊候选只计数）、`train_heads`（AdamW、逐帧 batch、登记 seed、跑满登记 epoch 后保留 validation 损失最低的 epoch＝无耐心值的早停、发散如实返回、同值同机逐位复现）、`recipe_matches_contract`（lr 1e-3／20 epoch／5 seed／2 轮 DAgger／主表第 1 轮绑定 S0-05 冻结值）、`dagger_schedule`（第 0 轮 ELU-P 预登记 rollout_config 轨迹、第 1 轮自身轨迹，两轮都报）、权重 payload 带摘要；代价矩阵、求解、编译、提交复用 S0-03／S0-01 经 runner；`NoVersion` 为 runner 开关、`AssocOnly` 为 `assoc_only=True` 重训（裁决 X3）。测试 [`test_vsmt_lean_model.py`](../tests/test_vsmt_lean_model.py) 11 项，含继续门"候选换序后每个实体的 logit 跟着实体走、最终程序不变"。标签生成与 DAgger 编排要等 S2-04 的 teacher 接线 |
| 输入 | S0-03、S0-05 合同 |
| 完整动作 | 实现三个代价头、代价矩阵、矩形分配、编译与提交；训练循环与两轮 DAgger；实现 `NoVersion` 与 `AssocOnly` 两个消融开关（同一代码路径、同一训练预算；**AssocOnly 同配方重训、去掉存在损失项，不复用 VSMT-lean 权重**，裁决 X3）；第 0 轮 DAgger 的 ELU-P 轨迹取 S0-05 v2 预登记的 `rollout_config`（裁决 X4）；不读 slot/路径/样本名 |
| 输出 | 模型代码、训练入口、单元测试 |
| 继续门 | 候选换序后每个实体的 logit 跟着实体走、最终程序不变 |

### S2-04 teacher 与评价器

| 项 | 内容 |
|---|---|
| 状态 | **已实现并经用户审查（2026-09-24，LOG-249 实现、LOG-250 审查；裁决 64 (a)、65 五条按推荐）**：[`lean_evaluation.py`](../src/vsmt/lean_evaluation.py)——`fragment_instances`（回收 mask 按定义重算摘要与封印帧逐位核对后，用 S1-04 的重叠算法出 S0-04 的实例重叠表）、`EpisodeTeacher.label_frame`（核对回执放行门与帧序→追踪器真值与 S2-01 真值表→S0-04 `association_targets`／`existence_labels`（结构件候选一律 present）／`decompose_frame`／`evaluate_frame`／`false_retract_rate`／`size_and_cost`→窗口后的旧/新位置、可观察判定、Missing 残留率、恢复标志、身份连续率→S2-03 训练记录（存在行只含可判定候选）与 nuisance 行）、`episode_report`（七项指标恰为冻结字段，`assert_report_keys` 把关；诊断另列）、`nuisance_probes`（关联行与存在行分开做）、`headline_values`；合同 [`lean_s2_04_evaluation_v1.json`](../configs/vsmt/lean_s2_04_evaluation_v1.json)（首钉 `40d96cf0…`，登记派生规则、policy 来源、主值字段，两位全 false）；入口 [`lean_s2_04_evaluate_episode.py`](../ops/vsmt/lean_s2_04_evaluate_episode.py)；测试 [`test_vsmt_lean_evaluation.py`](../tests/test_vsmt_lean_evaluation.py) 14 项（5 帧合成 episode：杯子移走、书搬动、墙始终在；TAF 残留 1/2、连续率 1/1、书恢复 0 帧、杯子未恢复，ELU-P 撤回后残留 0/2、假撤回 0/1、杯子恢复 1 帧；换私有面标签变而公开产物不变；门与帧序；合同绑定）。五条派生规则由裁决 65 冻结，运行位归属由裁决 64 定为 S2 阶段合同持有 |
| 输入 | S0-04 合同 |
| 完整动作 | 实现封存后标签器（含同帧重复色块的 `duplicate_of_labelled`，裁决 X1）、七项指标、三分解、nuisance probe、私有扰动不变性检查；评价器收到的真值表含所有可解析物体并带 `in_scope` 标志（裁决 X6）；每项指标的未定义 house 清单按 `undefined_houses` 算一次并传给全部配对比较（裁决 X2）；**存在标签只对 runner 的可判定行生成**（active／dormant 且应可见比例 ≥ S0-05 `should_be_visible_min_ratio` 的未分配实体，与部署时存在头被询问的行一致，该下限须先冻结；S2 审查，LOG-248） |
| 输出 | 评价器代码与测试 |
| 继续门 | 修改 private 不改变任何公开产物字节 |

### S2-05 50 house 开发表

| 项 | 内容 |
|---|---|
| 状态 | **编排已实现并经用户审查，校准趟进行中（2026-09-24，LOG-251 实现、LOG-252 审查与开跑）**：[`lean_development.py`](../src/vsmt/lean_development.py)——`Histogram`／`CalibrationCollector`（固定边界、可合并的直方图：同物体目标对余弦／距离／IoU、异物体余弦、新物体最高余弦、存在候选按 gone/present 的自由空间覆盖与错失次数、色块主导占比、实体应可见比例、同帧同物体色块数）、`EluPCounter`（S0-05 v2 三个拟合量的四条计数，逐帧按追踪器真值、公开可见体积、门臂分配与证据映射数）、`fit_elu_p`（求和后走 S2-02 估计式）、`development_table`（每臂每指标的 house 主值、裁决 X2 排除清单只对适用臂算、有效 house 数、均值、VSMT-lean 对每臂配对差；缺臂缺 house 即拒）、`validate_development_contract`；合同 [`lean_s2_05_development_v1.json`](../configs/vsmt/lean_s2_05_development_v1.json)（首钉 `38314ce2…`；五趟顺序、校准臂 LOW 无门、拟合臂 TAF 在 rollout theta_a 无门、第 0 轮 ELU-P 轨迹同时是 ELU-P 表行、开发训练每轮一次取首个登记 seed 且早停用 S1-04 留出、八个开发配置槽 null、继续门按裁决 66）；入口 [`lean_s2_05_development.py`](../ops/vsmt/lean_s2_05_development.py)；测试 [`test_vsmt_lean_development.py`](../tests/test_vsmt_lean_development.py) 7 项（直方图裁边合并分位数；收集器计数与封存行一致；计数器在合成 episode 上逐条手算相符、可观察间断产生在位先验计数、退化拒绝；开发表主值／排除／不适用臂／配对差、缺臂缺 house 拒绝；合同绑定与弱化拒绝）。裁决 67 已落地、六个运行位已开（LOG-252）；开发配置槽等裁决 68 |
| 输入 | S2-01～S2-04；S1 cache |
| 完整动作 | 在开发 cache 的成功子集上跑五臂（原定 50 条 house：S1-02 成功 43 条进入 S1-03，cache 成功 42 条，`train-01451` 按合同 `proposal_overflow` 失败并留在失败清单；**不补样、不重生成、不抬上限**，五臂共用同一 42 条；VSMT-lean 只做一次开发训练），**并把 `NoVersion` 与 `AssocOnly` 两个消融用同一次开发预算一起跑**，兑现风险探针的第三件事；出第一张表、逐例失败、runtime/memory、接口问题清单 |
| 输出 | 开发表，含 VSMT-lean 对 `NoVersion`、对 `AssocOnly` 的开发差 |
| 继续门 | 只用于发现工程问题与早期风险读数；**不据此选择论文赢家、不调网格、不删消融**；**开发差可以促成设计修订（裁决 66，2026-09-24）：修订须登记为裁决、在 S3-01 冻结正式数据前完成、不读 validation/test**；`HandCost`、`HeuristicLabel`、`LLM-op` 与 `VSMT-lean-ctx` 仍只在 S3 跑 |

## 六、S3：正式数据、训练、validation 与一次性 test

### S3-01 冻结正式数据与统计预算

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S1 成品率、S2 开发表 |
| 完整动作 | 冻结 train/validation/test = 300/50/100 house 的 manifest（seed 与 test/validation 规模已在 S1-02a 前冻结，此处只允许按成品率下调 train，裁决 X6）、bootstrap seed、主门效应量、停止规则；登记未定义 house 的排除规则与功效按有效 house 数计算（裁决 X2）、最强对照在 test 上逐指标后验选取的口径、回执里钉住 Python 版本（bootstrap 依赖 `random.Random`） |
| 输出 | 三个互斥 manifest、功效说明 |
| 继续门 | test manifest 此后只读一次；裁决 39 已裁（(a) m=8，见下） |

**已裁（裁决 40，2026-09-21）：`maximum_actions` 2000 → 4000，口径为范围边界，台账记 superseded；S1 只重生成触顶失败的 house，S3-01 直接按 4000 生成。**

**已裁（裁决 39，2026-09-21，取 (a) m=8）：dry-run 每个候选物体只随机测 U 里至多 8 个目的容器（`dry_run_order` 标签），回执记 `dry_run_pairs_tested`／`dry_run_pairs_total`／`feasible_set_size_estimate`；S1 的 50 条是无上限生成的，与 S3 的 F 不可直接比较。以下保留当时的论证。**

**dry-run 枚举上限（裁决 39 的论证，已按 (a) 采纳）。** 裁决 35 把 U 从 188 放大到 670 之后，dry-run 的开销是 `候选物体 × |U| × 最多 32 个点`，每个点都要真放一次再瞬移偷看一次。S1 的实测：99 个容器的 01451 单条就要一个多小时，50 条合计数小时。**300 个 house 的 S3-01 按同一口径约需 30 小时以上**，这是它必须在生成前裁掉的原因，不是可以边跑边定的工程细节。

| 口径 | 做法 | 代价 |
|---|---|---|
| **(a) 推荐：按候选物体限制目的容器数** | 每个候选物体用已派生 RNG 随机测 U 里至多 `m` 个目的容器（建议 m=8），其余不测 | 成本从 `候选 × \|U\| × 32` 降到 `候选 × 8 × 32`（01451 约 3000 对 → 320 对，降约 9 倍）；每个物体被平等探测，move 的发现不会集中损失在大 house |
| (b) 全局随机上限 K | 打乱全部 (物体, 目的容器) 对，最多测 K 对（曾建议 K=400） | 抽样仍无偏，但**大 house 的 P 最大、截断最狠，而大 house 正是 move 的主要来源**，与裁决 36 的 `train ≥120 个 move` 相抵触；不推荐 |
| (c) 不设上限 | 维持现状 | 口径最干净，S3-01 约 30 小时以上 |

两种上限都会让 `feasible_set_size` 从"这条 house 有多少可行干预"变成"测过的那部分里有多少可行"，因此回执必须同时记 `pairs_tested` 与 `pairs_total`，并报一个比值估计 `|F_true| ≈ |F_tested| × pairs_total / pairs_tested`，使被截断的数字不会被当成真值读；S1（无上限）与 S3（有上限）的 F 不可直接比较。抽样公平性不受影响：被测子集是均匀随机的，且裁决 29 先抽类型再抽三元组，`remove` 不需要 dry-run 这件事不会抬高 remove 的比例。**2026-09-21 用户批准本次 50 条按无上限跑完**，上限只影响 S3-01。

### S3-02 正式生成与 cache

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-01 manifest |
| 完整动作 | 按最大安全 worker 生成 train/validation 的 raw 与 cache；test 生成后封存不读 |
| 输出 | 正式数据、失败与资源回执 |
| 继续门 | 固定样本全部有终态；失败不替换 |

### S3-03 训练与配置选择

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-02 train；S0-05 网格 |
| 完整动作 | 先在 train 上按 S0-05 v2 登记的程序估 ELU-P 三个拟合量，并用预登记的 `rollout_config` 产生第 0 轮轨迹与 HeuristicLabel 标签（裁决 X4）；再 VSMT-lean 两轮 DAgger × 5 seed；四组消融同预算（AssocOnly 重训，裁决 X3）；规则臂各 ≤12 配置；`LLM-op` 只在 validation 上跑一次；只读 validation 选择 |
| 输出 | checkpoint、配置、训练曲线、完整失败 |
| 继续门 | 不读 test；不按单一场景临时增配 |

### S3-04 validation 后冻结

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-03 全部候选 |
| 完整动作 | 选最终 checkpoint、τ_r 与各臂配置；写冻结回执与 test 可执行代码摘要 |
| 输出 | 冻结回执 |
| 继续门 | 此后不得改算法、数据、阈值、指标或预算 |

### S3-05 test 一次性运行

| 项 | 内容 |
|---|---|
| 状态 | 封存，未打开 |
| 输入 | S3-04 冻结字节、S3-01 test manifest |
| 完整动作 | 一次性读取 test，跑五臂与四组消融、配对统计、house 级 bootstrap；`LLM-op` 不进 test |
| 输出 | 主表（含与主比较并列的 `AssocOnly` 行）、消融表、三分解、规模与成本、逐例失败 |
| 继续门 | 只跑一次；失败照实报告，不换样本、不改方法、不改指标 |

### S3-06 主张审计

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-05 不可变结果 |
| 完整动作 | 逐条检查证据是否支持第二节三项贡献；不支持的主张不写 |
| 输出 | 论文结果包与可复现实验索引 |
| 继续门 | 主门失败就报告 no-go，不通过换数据或缩减对照制造成功 |

## 七、S4：论文

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-06 结果包 |
| 完整动作 | 写作、失败分析、成本与限制 |
| 输出 | 论文稿 |
| 继续门 | 证据不支持的主张不写 |

## 八、时间与最近动作

| 阶段 | 估计 | 主要不确定项 |
|---|---|---|
| S0 | 3 天 | 用户审查往返 |
| S1 | 1 周 | SAM2 资产获取；跨视角余弦分离度；干预成品率 |
| S2 | 1 周 | RAC 投影实现；DAgger 稳定性 |
| S3 | 2 周 | 生成吞吐；统计功效 |
| S4 | 1 周 | |

估计不承诺。最近动作按顺序为：

1. 2026-09-19 用户批准 D-224 裁决 A～D，并要求把旧方向归档到分支 `archive/pre-d224-unified-graph`、在 `main` 上重写 METHOD/PLAN/DATA。已完成文档重写，未生成数据、未训练、未连接服务器。
2. 2026-09-19 用户批准 D-224-E/F/G：共享 ReID 适配头登记为 S1-05 可选前端、`VSMT-lean-ctx` 登记为可选臂、S0-01 固定实体 token schema；并确认执行顺序为先只冻结看数据前必须定的项，五臂一起在 50 house 跑通，再按三分解决定是否启用 E/F。
3. 2026-09-19 用户审过 S0-01 并采纳其中三处语义选择；同时批准把对话初期四项裁决中的前三项补进文档（`NoVersion` 与 `AssocOnly` 提前到 S2-05、新增必做消融 `AssocOnly` 并与主比较并列、`LLM-op` 收口为必做附录臂），外部基准第二张表推迟到 S2-05 后再裁。
4. 2026-09-19 用户审过 S0-02，并确认 `LLM-op` 维持必做附录臂。
5. 2026-09-19 S0-03 首版实现后经 Codex 审查退回，返工版落地（状态无关的全局召回通道、−logit 代价、字典序最小最优解、两阶段封存、合同绑定关键声称），三处语义变化登记为 D-224-S03，待用户复审。
6. 2026-09-19～20 S0-04 teacher、评价器与指标合同实现并经审核重写，待用户代码审查（LOG-217）。
7. 2026-09-20 用户批准裁决 L～Q 全部按推荐口径执行（D-224-LQ）；METHOD 第六、八、十一节与 DATA 第六、七节据此更正，合同绑定该裁决编号。
8. 2026-09-20 用户批准 D-224-R：S0-03 返工版复审通过并提交，三条规则臂约束登记为 S0-05 前提，S0-03 合同补 up_axis_index；S0-05 开始。
9. 2026-09-20 S0-05 对照、消融与配置网格合同实现，待用户代码审查（LOG-218）。
10. 2026-09-20 用户批准 D-224-SW：五项口径按推荐执行，S0-05 提交推送，S0-06 用户合同审查开始；跨合同一致性检查落为测试。
11. 2026-09-20 用户批准 S0-04 与 S0-05 通过代码审查；S0-06 用户合同审查完成，S0 全部五份合同审查通过。S1-01 资产与容量授权申请材料留到下一次会话准备，本次会话不再推进。
12. 2026-09-20 S1 开始前先做归属检查：确认 S0 合同阶段的产物恰为五份 `lean_s0_*` 合同、五个 `lean_*` 纯核心与六个 `test_vsmt_lean_*` 测试，其余 `vm04_*`／`d2xx_*`／`l1_*`／`cpmt` 属旧方向；其中 D-215、D-224 资产合同、F-01 reader 合同及其按字节绑定的七个文件是 S1 的活依赖，不得归档或改字节。随后实现 S1-01 资产与容量授权申请材料（LOG-220），待用户代码审查与六项裁决。
13. 2026-09-20 用户一次批准 D-224-S1 九项裁决并授权服务器只读核验与清理。九项全部落地（ProcTHOR-10K 定 0.1.2、ViT-B/14 本地登记待执行、两解释器分工、只读探测渲染后端、许可证留后、清理 tests/README、删 84 个孤儿字节码、切断 lean 对 cpmt.executor 的传递性 import）。服务器核验七项冻结资产标识全部一致，Vulkan 能枚举到 NVIDIA GPU，simulator-py39 已备齐 ai2thor/procthor；新发现基础环境缺 hydra 使 SAM2 无法 import。数据盘清理已只读勘定 21.9 GB，删除命令被本地安全策略拦下未执行（LOG-221）。
14. 2026-09-20 用户批准补充裁决 10～13：追认 9-19 资产放置（凭 reflog 重建时间线）、按 D-224 已有授权安装 hydra-core/omegaconf/iopath（torch 与 SAM2 工作树未变，SAM2 可 import，生成器 17 参数与登记一致）、数据盘清理由用户自己执行、estimator 5.5 GB 因 F-01 兼容适配器仍在用而保留（LOG-222）。
15. 2026-09-20 执行裁决 2：ViT-B/14 一次性摘要登记完成（URL 由钉死 dinov2 commit 源码推导并经 ViT-S/14 回执实证，346,378,731 字节 / `0b8b82f8…`，核对 768 维/patch 14/12 层/86.58M 参数后删除临时文件）。四项已知冲突至此全部拿到回执，S1-01 待冻结 null 只剩 `worker_rule.headroom_fraction`（LOG-223）。
16. 2026-09-20 用户清理数据盘（22 G → 43 G 可用，保留清单九项经只读核验全在），并批准补充裁决 14：S1-01 的 worker 死锁按方案 A 解开，占用测量移入 S1-02a（4 worker × 1 house）、S1-02b 扩到 50 house；pilot 的 4 条计入正式样本，`concurrency_verified_at` 与 `derived_worker_count` 分开记（LOG-224）。
17. 2026-09-20 用户审过 S1-01 v1、定 `headroom_fraction`＝0.2，并要求核对 S0 转 v2 是否连带影响 S1。核出三处：S1-01 `depends_on` 仍指 v1、headroom 待冻结、S1 从未进入跨合同核对。追加 S1-01 v2（v1 字节冻结并钉住摘要），跨合同测试加 9 项 S1↔S0 检查；PLAN 的 S1-02a 前置冻结与 S1-04 的 IoU 诊断在 v2 那批已同步，无需再改（LOG-226）。
18. 2026-09-20 用户审过 S1-01 v2 与五份 S0 v2，并要求写 S1-02a 合同。合同、纯核心与测试已实现待审（LOG-227）：pilot 形状固定为 4 worker × 1 house，4 条计入 50 条且禁止看过结果后重生成；占用取峰值、在完整 episode 上量、并把 `concurrency_verified_at` 与算出来的 worker 数分开记。**seed 与 test/validation 规模用户未给定，合同中保持 null，须冻结后才能跑第一条 episode。**
19. 2026-09-20 用户审过 S1-02a 并冻结划分：seed=20260920、validation=50、test=100。追加 S1-02a v2（v1 字节冻结并钉住摘要），校验器改为「三个值要么全开要么全冻」，跨合同测试加 9 项钉住「划分只在一处登记、S0-02 值槽保持 null」（LOG-228）。
17. 2026-09-20 S0 合同隐患审查后用户批准 D-224-X 裁决 X1～X6：同帧重复色块记 `duplicate_of_labelled`、未定义 house 按指标排除并计数、AssocOnly 同配方重训、预登记 ELU-P `rollout_config` 与拟合程序、求解器规范化改等式子图（64×500 单帧 125 秒 → 0.01 秒）与评价器分连通块匹配、划分顺序 test→validation→train、折叠记录归档口径、生命周期版本数、真值表 `in_scope`。五份 v2 合同追加、v1 字节冻结并钉摘要，八个 lean 模块分进程 382 项通过；本会话复审修正四处（X1 组级记账、X2 不适用臂例外、HeuristicLabel 私有依赖声称、范围外实体退出精确率分母）后 386 项通过，五份 v2 已按用户批准提交推送（LOG-225）。
20. 2026-09-22 用户担心上一段对话被记忆污染，要求直接看服务器产物判断 S1-04 的三处卡点。核实三处属实（真值盒从未保存且 S0-04 评价器同样受阻；召回四值 null；ReID 未训练但 128 维本是 D-224-E 原话），并发现 cache 运行里 01451 按合同 `proposal_overflow` 失败、cache 不存 fragment mask（待裁 48）。用户批准裁决 45～47：真值盒取模拟器重载初始盒加记录平移、观测集合盒只作对照列；理想记忆口径认可、曲线后一次冻结召回四值；ReID 进 S1-04，128 维与 0.05 入台账，30/12 留出。S0-02/S0-03/S0-04 就地修订并重钉（LOG-241）。

## 九、失败时的暂停点与待触发裁决

失败时先暂停并如实报告证据，不得在同一轮里自行选定替代路线；任何替代路线在执行前必须写成新决策并经用户批准。

| 步骤 | 失败长什么样 | 暂停点与必须触发的裁决 |
|---|---|---|
| S1-01 | 资产摘要与 D-215/LOG-136 登记值不符 | 原样停下报告，**不得**换镜像、换 tag 或先用着；是否重新冻结前端由用户裁决 |
| S1-02a | CloudRendering 虽能看到 Vulkan 与 GPU，但实际起不来或只落到 llvmpipe 软件光栅 | 触发**渲染后端裁决**：改后端等于动 S0-02 已审字节，须另开版本并经用户批准；不得默默接受软件光栅的吞吐 |
| S1-02b | 干预成品率远低于登记下限；路线无法保证重访 | 触发**规模裁决**：下调 house 数或改路线模板；不得换 house 挑好样本 |
| S1-04 | 单视角 fragment AABB 对真值整物体框的中位 IoU 低于 0.3 | 触发**匹配口径裁决**：裁决 C 冻结的 0.3 与裁决 V 的节点 F1 选参会同时失效；备选是 BIND 时按并集累积 AABB 或改用质心距离匹配，都动已审字节，须用户批准 |
| S1-04 | 两套描述子的跨视角分离度都不足 | 触发**证据层级裁决**：是否降到 L1 oracle mask。这会把主张从"可部署 RGB-D 条件下的比较"改为"感知正确前提下的机制诊断"，属改变论文声称什么，须用户批准 |
| S2-05 | VSMT-lean 在开发 house 上不优于对照 | 不构成结论；可据此提出设计修订裁决（裁决 66），否则照常进入 S3 |
| S3-02 | 成品率低于 S3-01 假设 | 按已冻结停止规则收口，用实际样本量运行，功效不足写入限制；不得事后加样本 |
| S3-03 | 训练不收敛或 DAgger 第 1 轮劣于第 0 轮 | 两轮都报告，按登记规则取主表轮次；不得因结果换轮 |
| S3-05 | 主门失败 | 如实 no-go，不换数据、不缩对照；能保留哪些贡献在 S3-06 逐条审 |
