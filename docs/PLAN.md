# 空间历史驱动的世界模型研究计划

本文件是阶段、审查节点和当前指针的唯一维护处。方法见 [METHOD.md](METHOD.md)，字段见 [DATA.md](DATA.md)，证据见 [EXECUTE.md](../EXECUTE.md)，转向依据为 D-062。

## 当前目标与授权

2026-09-11 用户认可严格成对的空间历史候选，并明确“可以，开始吧，必要的时候重构整个工作区”。当前开始执行；持久三维状态和动态预测不预设为创新，CTL 不预设为新机制。旧科学 no-go、test 封存、源码和结果原路径保留。

白话：先让两个世界的近期输入相同、旧观察揭示的隐藏结构不同，再看同一控制的后果预测和动作选择。例如推杆把物块推向此前见过而当前不可见的挡板；模型应利用过去分清受阻和通过。这不是给出物块未来运动再生成图像，也不是立即建设通用机器人。

D-059 的逐职责代码审查继续有效：当前批次可实现及做必要服务器工程测试，用户审过后才进入依赖它的下一科学批次。仅执行已确定的本阶段，不提前写未确定模型/损失/预算。

## 分阶段交付

| 步骤 ID | 输入与工作 | 输出、继续条件 |
|---|---|---|
| SH-01 成对数据合同 | 已认可的候选；实现严格字段/时序/成对校验和模型输入提取，提供手工正负例 | 可读提交、具体输入输出、服务器回执；用户审查当前批次后进入 SH-02。不是物理案例 |
| SH-02 物理生成器 | 已审合同；选择并固定模拟器版本、坐标/相机、控制器/饱和、物理参数、接触语义、场景和观察路径 | 单职责模拟器实现及必要服务器测试；真实快照恢复、控制执行、渲染和重放。实现审过才生成开发审计案例 |
| SH-03 小规模物理审计 | SH-02 审查与工程通过；D-065固定16对开发世界，64条不同分支及64次独立重放，不因结果增样本 | 完整场景、快照、原始传感器、原始轨迹、失败、可视化和来源摘要。16对全部满足原物理/输入条件才通过；必要修复新版本，不覆盖 |
| SH-04 研究问题与基础对照协议 | 物理审计通过；先核查近邻/旧架构及场景信息需求，再固定划分、监督、对照、评分和预算 | 基础架构、原论文设定核验、任务适配分别交证据；D-068暂停v1实施，不以首帧可解模板承担主结论 |
| SH-05 复现并定位失败 | 已审基础对照与服务器检查；保持相同数据、信息与动作选择规则 | 逐例预测/接触/动作效果、独立场景组成对统计、成本。短历史的必然失败不算新发现；强对照成功则如实收口 |
| SH-06 决定改进机制 | SH-05 确认并复现的具体失败 | 单一机制假设、对照与预算；不预先绑定 CTL，不靠扩场景/模型追正结果 |
| SH-07 独立确认与交付 | 前阶段已审方法和冻结协议 | 未见场景确认、适当现实来源验证及论文/artifact；目前均 planned，不能视为已授权 test 解封 |

SH-03预算由D-065固定：128次4.9 s模拟执行，新产物2 GiB，按案例边界检查；预计5–10分钟前台，实际耗时待服务器记录。SH-04及以后不预设训练规模、模型架构或实验胜者。测试与计算仅在服务器；本轮D-090/091按用户授权由代理直接SSH执行。本地只做源码、文档、Git和标准库静态核查。

## 当前指针

**当前为R4-4模型接入准备，前端v2r1名义工程验收已通过。** 报告81bceed绑定01c03cf，19项检查、30项来源绑定、原16历史/144分支/320输入核验完整；16关联/两开口、144轨迹/任务读出、16选择及误标占据/自由均达到D-090登记门。公开推演754.3 s、评估66.8 s，实际物块平均误差9.59 cm、接触Brier 0.1152；16世界名义选择恰好选中真实成功动作，但全144分支仍涉及未知扫掠，formal_model_ready/eligible_for_P=false。LOG-121保留工程通过与科学缺口。

用户追加授权完成后继续SH-05接三模型、可用系统盘且必要时删除旧CPMT/CTL数据。D-091登记按实际依赖连续推进：先锁官方源码与独立环境、必要原生检查，再按职责实现完整历史/200步适配；不将24小时窗口当作56 GPU小时预算或确认集解封。DreamerV3/FloWM继续；PointWorld官方DINOv3资产缺失，用户正在询问DINOv2替代方案，DINO-WM为待定推荐，尚未把更换编码器或第三模型写成已审基线。已核系统盘约29 GiB空闲、数据盘22 GiB，尚不需删除，旧数据未动。原PLAN局部编辑保留。

已完成证据：[SH-03/v2报告](../results/spatial_history_development_audit_v2_wall_clearance.json)为12项/16对通过，原科学提交57d01aa、报告ce5b3f1，LOG-107；原v1失败保留于LOG-106。它们只供工程/输入审计，不能拆分成训练/确认。当前协议文档有新增内容，不借旧SH-03回执认证；旧产物按原代码/合同摘要复用。

### SH-04交付与继续条件

白话：先确认题目确需整合历史，再给成熟架构和已有方法公平机会。例如两个视角分别提供几何证据，需要检验单帧不足，以及公开历史能否恢复可用几何；这不是为了让检索失败而堆长视频。旧SH-03只保留原工程证据。本批复用既有隔离环境，阶段开始同步一次，下方命令顺序运行。

| 职责批次 | 固定工作与读写范围 | 输出与继续条件 |
|---|---|---|
| SH-04-R1 文献与旧架构评估（已交付） | 原文/官方源码与旧实现/结果只读核查，更新现有文献索引与方法边界 | 直接重合、真实输入/监督、可运行资产、旧模块复用边界；阅读不当作复现 |
| SH-04-R2 场景可识别性合同（工程验收及用户审查通过） | D-070/D-071的代码、完整运行与只读验收已交付，用户于34121aa后要求下一步 | 已审批次合并main至cd31dd1；固定构造证据见LOG-108，公开几何正向对照及正式连续组合仍另审 |
| SH-04-R3 公开输入及论文资产核验 | R2合同审过后，按职责交公开输入/标签隔离、原SH-03视觉读取、独立环境及官方版本锁；依D-073先审DreamerV3后果评分、PointWorld三维动力学、FloWM历史记忆的适配条件，不再默认先运行DINO-WM | 先形成输入/动作/监督/历史/读出与资产差异清单，再审具体运行职责及资源；前向、官方checkpoint重评、原训练复现分列。条件不符或资产缺失如实登记 |
| SH-04-R4 公平对照与数据/评分冻结 | 前批审过后交完整历史、RSSM、合法检索、共享地图/动力学及论文适配接口；按D-075冻结主体/探针的独立学习预算和诊断读取位置 | 信息/标签一致；历史/未来时序、接触与选择评分、误差容差、家族划分及统计固定，必要服务器检查通过；旧96对/18次不沿用 |
| SH-05 复现失败与定位 | 三条独立适配与必需强对照进入同一历史→控制后果→候选选择流程；按已审条件报告成功、失败及感知/历史/控制/动力学/读出归因 | 保留各方法原机制诊断；适配或训练不足时结论未定。简单方法足够则收口，只有定位且重复的失败才进入SH-06 |
| SH-06/07 单一机制与独立验证 | 一次只改对应失败的一处；后续在独立公开具身任务/来源核验适用范围，具体来源待审 | 不能只靠同一生成器的小参数变化支撑通用主张；不承诺会议录用，不扩第二应用领域或解封旧test |

资源落实先只读核验实际GPU显存、系统/数据盘可用量与租赁配额，再按精确文件选择权重和依赖。旧MuJoCo环境及CPMT数据保留；新依赖独立。候选论文方法的完整适配成本尚未实测，不能承诺旧6 GPU小时容纳新增比较。首次资源核验和小样例预计短任务，默认前台；具体运行预算随该职责冻结。

R2原**预算已获D-070批准**：1个工程家族、4世界、每世界1条真实历史、16条首次控制分支及16次新实例反序重放；0训练步、0新权重下载，复用旧隔离环境。新数据上限2 GiB、生成墙钟上限30分钟；实际耗时见LOG-108。必要检查单独计时，不把其短零控制夹具算入16条完整执行；预算不转借R3训练。

首个Linux运行目录`/root/autodl-tmp/spatial-history/sh04-r2-two-gate-engineering-v1`已在`history-LL`前失败并封存，先导出诊断，绝不覆盖或重跑。D-071的新目录为`/root/autodl-tmp/spatial-history/sh04-r2-two-gate-engineering-v1-lfsha1`，报告为`results/spatial_history_two_gate_engineering_v1_lfsha1.json`；check通过才允许run。每步封存退出/manifest后再启动下一步。完整物理/信息审计失败仍保存固定清单全部结果，运行异常或预算到达则停止并标清未运行项。写前字节预检及父进程墙钟/磁盘监控持续生效，含静默子进程；保留1 MiB给失败证据和manifest。终检计入生成时间。失败和无回执的中断拒绝自动重试/覆盖，已封存成功步骤按原绑定复用；独立重放不是新增样本。

工程只报告来源/物理/观察/动作信息是否成立。数值审核不等于科学代码审过；R3公共RGBD几何恢复和R4观测地图动力学正向对照缺失时，不能把工程通过升级为“完整历史足够”或启动未授权的模型效果实验。

原[baseline_protocol_v1.json](../configs/spatial_history/baseline_protocol_v1.json)保留原数值供审查，状态为requires_revision_not_executable且training_authorized=false；该旧提案没有数据/下载/训练授权。D-070只批准新双门工程批次。后续学习曲线检查不能成为无限加算力或挑最好种子的入口。

未来SH-05仍先在train/validation完成登记选参，再锁定模型/算法/数据/评分；confirmation在该阶段授权后才生成并评估，不能用其结果修方法。原50 GB数据盘中的CPMT数据与SH-03失败/通过产物均保留。新主张范围随证据决定，不预设持续3D、CTL或某个架构必胜。

SH-05按D-074保留DreamerV3、PointWorld、FloWM三条本任务适配路线；D-079已交适配/训练规格提案，实现和运行环境仍待核验。D-073核查见[文献记录](../literature/notes/spatial_world_models_2026.md#reviewed-baselines-20260912)。DINO-WM保留为有条件的视觉特征预测参照；ParticleFormer因官方实现未核得而暂不承诺复现。长历史预测器、合法历史检索、地图加简单动力学仍是必需主对照。正式比较前逐方法登记作者commit/checkpoint、原任务重评、改动、完整历史覆盖、监督与评分、训练充分性和预算；仅有论文名字不满足进入SH-05的条件。

源码审核发现的缺口已纳入[D-079三份适配合同](METHOD.md#r4-adapters)：PointWorld的历史地图/特征、控制到机器人运动及长推演；FloWM的连续相机/独立推头控制及后果目标；Dreamer的RGBD、完整历史和离线世界模型职责分离。三仓库审查commit及权重元数据已记录，均未运行。实现按依赖逐职责交付，不因难度将其中两条移出本任务；合同登记不代替科学模块审查。三系统先独立比较，之后仅针对已定位的错误审查模块组合；FloWM记忆＋PointWorld动力学是示例，不预定最终架构，不启动全排列实验。

D-075诊断实验包括E0公开几何恢复、E1编码/保留读出、E2同控制单门配对、E3全时域推演、E4成功读出与选择。方法见[METHOD](METHOD.md#history-use-diagnostic)，字段见DATA。E0使用D-078[并行活动配置](../configs/spatial_history/public_geometry_parallel_v1.json)，原D-077串行配置与D-076[数值提案](../configs/spatial_history/public_geometry_proposal_v1.json)保持原字节。E0通过只提供公开几何可读的正向参照；D-079已登记三模型原生状态读取位置和独立探针规格，不能用真值补齐缺失状态。E1–E4及主模型效果仍需各自代码/新家族/预算审过后运行，原工程四世界不用于拟合或独立确认。

SH-01审查批准已登记于9044074。SH-02科学提交e3a1d71及通过报告f6b8c58完成核验后，用户明确要求“下一步”，据上下文登记对该批次的审查通过，允许合并main并实施SH-03固定开发审计。此授权不包括SH-04训练协议或模型效果实验。

### SH-04-R4逐职责交付

白话：本阶段先把“输入什么、保留什么机制、预测什么、怎样判断失败”写到同一份可审协议。输入是已验收工程条件和三条作者源码接口，输出共同合同、具体适配和预算；例如PointWorld控制模块误差与场景点流误差分列。这不是已接好三个模型，也不能从E0回执推定新家族或新适配通过。

| 顺序 | 具体交付及依赖 | 允许继续的证据 |
|---|---|---|
| R4-0 规格提案 | 本次METHOD/DATA及protocol_r4_v1.json，D-079登记；六系统、64家族、E1–E4与有限预算 | 数值提案可供审查，尚无学习、生成、下载或确认授权 |
| R4-1 共同查询与评分（已验收并准许继续） | `r4_query.py`/`r4_scoring.py`实现公开schema、训练标签分离、区间接触、候选选择/缺失分母、家族统计；`r4_contract_check.py`只运行解析正负例及check/verify/export | 23项通过及用户继续授权见LOG-111；不是模型/物理证据 |
| R4-2 新家族生成/存储 | 固定清单、连续因素、变观察时序、无损分片、E0/物理/121帧信息门及重放 | 先审代码/数值和资源，固定train前4家族工程子批通过才继续原清单；不按结果替换样本 |
| R4-3 公共前端与控制（D-085审议稿） | v2观测覆盖检索、当前对象公开关联、静态地图、有限力近似预测及独立评估逐职责交付；细目见下方 | 每职责先定数值再交可审代码/手算例/必要服务器检查；P只获公共预测机器人路径，不获M物块轨迹或实际未来 |
| R4-4 三模型适配 | D、F、P各自可审提交，绑定作者版本，保留机制/新增模块/梯度/原生状态接口；独立环境及资产锁 | 全历史/200步、克隆/随机性/对拍/无未来输入检查；未过者留未就绪，不用弱替身替代 |
| R4-5 资源与学习放行 | 固定配方20主路径、独立探针和全部成本；完整阶段入口一次交付 | 容量和预算经具体审查后，用户服务器手动运行；小型拟合与训练充分性不合格不作机制失败归因 |
| SH-05 确认/归因 | 已锁主体/探针/评分，独立确认步骤另放行 | 三条适配和L/R/M同流程报告；简单方法成功收口，失败依E1–E4证据定位，不能自动扩模型 |

R4-0只固定规格；现已按顺序交付R4-1及R4-2，后续职责仍planned。拟议总上限56 GPU小时/64 GiB新增存储需要真实容量核验；旧50 GB数据盘不能按此假定够用，预算不足先登记不可执行，不删旧产物或静默缩科学规模。

<a id="r4-3-delivery"></a>

### R4-3逐职责交付与继续条件（D-085，proposed）

白话：将已通过的数据工程转成可审的模型输入处理。输入是原v2公共记录及已明确的方法边界，输出先为职责规格，之后才是独立实现和回执。例如检索先证明按公共覆盖取帧，再检查建图是否把未知补成自由；这不是把一次数据验收当作整个模型前端验收。

| 步骤 | 本职责输出与先决条件 | 审查/检查重点及继续条件 |
|---|---|---|
| R4-3a 公共反投影与覆盖检索（工程验收通过） | `r4_coverage.py`深度专用值函数，19项科学人工例及8项运维检查同版27项通过，报告908e370绑定26c8da8，LOG-117 | 11项来源与三份原证据已核验；按原字节复用，不重跑。不以人工选中10帧推定真实门证据恢复；下一职责数值另审 |
| R4-3b 当前对象公开关联（人工工程验收通过） | 报告bf8c05d绑定原66e4f6d，24+8=32项通过；12项来源和三份原证据核验完整，LOG-118 | 原字节复用，不重跑；自旋/瞬时速度仍未观测，人工例不认证实际16历史覆盖 |
| R4-3c 历史静态地图（D-089工程实现） | 02bce57实现逐帧动态排除、观测面片与名义地面/墙/未知及来源 | 本批full历史16次；格中心插值不是全格自由证据，完整几何包络准入尚未完成 |
| R4-3d 有限力预测与公共任务读出（D-089工程实现） | 25d0bff实现平面有限力、摩擦/接触、未知扫掠及公开开口/停稳读出；九次独立同初态 | 只保存名义诊断及未决；main_prediction=null、eligible_for_P=false，未把后向均速和零自旋当真实瞬时观测 |
| R4-3e 本批独立工程审计（流程完成，预测链路未通） | c3aaae2回传原41a9936，36项检查及320原输入/16历史/144分支审计完整 | 775c050原证据已取回核验，侧壁表面归属及可见短墙片排除两个缺口已定位；144/144仍感知未决，修订待审。LOG-119 |

a/b人工例不认证真实动力学；D-089按用户明确范围开放本组c/d与必要独立只读评估的一次工程交付。科学代码分职责可审，阶段同步一次，成功步骤只核验复用；不因本批联合交付而自动开放R4-4、训练或确认。

D-085/086/088的原预算及回执保留；本批D-089新登记36项人工检查和16/144只读工程计算，额度见下方及METHOD，不冒用旧marker或待审GPU预算。R4-4仍须另审80像素编码器适配、九候选曝光、PointWorld资产和完整不确定性边界，其余家族生成与模型效果不由工程通过自动放行。


<a id="r4-cd-server"></a>

### R4前端v2r1自主服务器工程阶段（D-090，当前步骤）

白话：输入仍是已封存的原16历史与144指令，输出修订后的名义关联/地图/轨迹/接触/选择及独立误差。先运行19项人工/隔离反例，再保存全部公开预测并取得子进程退出0，之后才读私有真值。它不新生成样本、不训练、不调控制，也不认证正式不确定性。

本轮用户已授权代理直接SSH执行，无需用户逐步复制命令。先在已核验且空闲的`/root/Emboddied_Spatial_Memory`同步review/spatial-history-baselines一次；使用原`/root/autodl-tmp/spatial-history-venv-v1/bin/python`，不安装新依赖。v2首次中断目录保留；本版stage目录为`/root/autodl-tmp/spatial-history/sh04-r4-frontend-v2r1`，失败/中断原样保留，已成功步骤只核验复用。完整命令保留复现：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_frontend_stage_v2r1.py run
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_frontend_stage_v2r1.py verify
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_frontend_stage_v2r1.py export
```

每步成功并核对退出证据后继续；run中的父进程自动检查前步退出/receipt，不绕过失败。完整运行上限7200 s、进程4 GiB、阶段加报告2 GiB、报告32 MiB，19项check上限300 s，计算窗口至2026-09-13T18:14:12Z。预计前台，可直接看进度；只有实测预计超过30分钟才转后台安排。0新生成/训练/下载/确认。工程链路验收必须同时达到16对象状态、16两门口、144完整轨迹/任务读出、16世界选择有值及误标自由/占据均0；status=passed仅表示执行完整，还必须看engineering_accepted。未知扫掠、实际误差和formal_model_ready=false仍保留。

输出为`results/spatial_history_r4_frontend_v2r1.json`，由代理取回后核验，再按原精确路径Git收尾；无需用户再手工pull/export。原服务器产物不删除/覆盖，正式模型准入不随工程通过自动开放。

### R4-c/d前端原证据回传（775c050已核验；以下保留复现命令，无需重跑）

用户要求先看服务器已有的6个未排除分量与墙面遗漏证据。入口为`ops/spatial_history/r4_frontend_evidence.py`，仅使用标准库复制原字节及核对摘要；不导入科学模块，不重跑旧check/run/export。它读取已记录的两个原目录，核验父报告d3635655…、原22项Git源码、6份阶段marker，以及16份地图/16份公开历史/16份评估XML，共54个服务器文件。输出单一`results/spatial_history_r4_frontend_evidence_v1.json`，48个原文件负载，保留原schema和压缩字节；base64仅为JSON内的无损字节编码。例如地图内近期两帧的分量支持像素、外环、高度、尺寸和拒绝原因原样回传，整段历史与地图面片来源用于后续区分未见区域和处理遗漏。这不是新的关联规则或修订后的预测；XML始终是封存后评估证据。

原文件不写入；报告上限32 MiB，原地图与公开输入压缩字节共10,582,109 bytes。实际报告14,193,917 bytes，已按775c050原负载/摘要核验，exit_code=0，归因见LOG-119。原命令前台300 s/512 MiB、0新模拟/训练/下载/分割/建图/预测；报告没有保存实际导出耗时。完全相同的已有报告只核验复用，不覆盖；不完整或不同内容拒绝并保留。首次7cffa68类型检查失败及c1658f9修复保留记录，无需再次同步或执行下方命令。判据修订仍待审。

在已核实、无运行任务的服务器checkout同步一次；不猜测或改写远端仓库路径：

```bash
git rev-parse --show-toplevel
git status --short
git pull --ff-only origin review/spatial-history-baselines
```

工作树干净且同步成功后，运行当前唯一计算步骤（只是原字节导出）：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_frontend_evidence.py
```

继续条件：`sh04-r4-frontend-evidence-v1 EXPORTED payloads=48 inputs=54 ... exit=0`，或相同内容的`REUSED`。失败保留原文件和终端错误，不启动旧run或自行改判据。成功后纯Git回传：

```bash
git add -- results/spatial_history_r4_frontend_evidence_v1.json
git commit -m "results: export sealed R4 frontend evidence"
git push origin review/spatial-history-baselines
```

### R4-c/d同版服务器阶段（D-089，36项及16/144已完成；以下保留复现命令，无需重跑）

白话：输入是本次三份科学提交、固定数值和已验收原产物，输出人工检查、封存预测与逐例误差报告。例如第一个世界关联失败仍保留其九个未决分支；这不是换场景重试或开始训练。方法/限制见[METHOD](METHOD.md#r4-map-control-engineering)，字段见[DATA](DATA.md#r4-map-control-engineering-data)。本地不运行科学函数或测试，服务器由用户前台执行。

**同步一次。** 先审本批代码，在没有运行任务的既有服务器checkout核对实际路径、当前分支及未提交内容；不根据本地路径猜服务器路径：

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --short
```

确认当前为review/spatial-history-baselines、工作树干净后同步，之后check/run/export不再pull：

```bash
git pull --ff-only origin review/spatial-history-baselines
git rev-parse HEAD
```

**SH-04-R4-cd-v1/check。** 读22项绑定来源，运行23项科学人工例及13项运维检查；旧真实报告只用于摘要绑定，不读物理outputs。新固定目录sh04-r4-cd-audit-v1/check已有时只核验，失败/中断拒绝重跑。前台、300 s、512 MiB，人工阶段额度8 MiB：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_map_control_check.py check
```

继续条件：`SH-04-R4-cd-v1 VERIFIED tests=36 exit=0`。失败则直接执行下方export回传诊断，不启动run。

**同阶段/run。** 复用同版check和原成功生成回执摘要；原目录为已记录的`/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v2`。仅读登记的320个文件，先公开预测后独立评估。运行前核可用内存至少2.5 GiB、盘至少1 GiB；总1800 s上限，进程2 GiB上限，阶段连导出1 GiB、报告32 MiB并预留失败证据1 MiB。前台显示144项公共状态及16项审计进度，失败/中断保留现场、已有run只verify：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_map_control_check.py run
```

成功标志：`SH-04-R4-cd-v1 VERIFIED histories=16 branches=144 formal_ready=False exit=0`。run已做终检，完成后直接export；只有重连核验原完成产物时才需同版verify，不执行科学函数：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_map_control_check.py verify
```

**同阶段/export。** check或run完成/失败退出后均可导出，不重跑也不覆盖不同内容的报告：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python -B ops/spatial_history/r4_map_control_check.py export
```

目标`results/spatial_history_r4_map_control_v1.json`；成功工程报告须`SH-04-R4-cd-v1 EXPORTED status=passed ... exit=0`。failed_or_incomplete也保留并回传。passed仅指本批执行和证据完整，须另读nominal_complete/readout/未决分母与误差；formal_model_ready和P准入仍false，没有准确率的科学通过门。

**纯Git收尾。** 报告写成后按精确路径提交，不提交服务器大地图/轨迹。之后本地pull只读验收；没有中间新版本同步：

```bash
git add -- results/spatial_history_r4_map_control_v1.json
git commit -m "results: export R4 joint map and control engineering audit"
git push origin review/spatial-history-baselines
```

### R4-3b固定服务器人工检查阶段（D-088，32项已验收；以下为原66e4f6d复现命令，无需重跑）

白话：输入已交付源码、已审数值与完整人工深度例，输出绑定同版代码的检查回执和小报告。例如两个圆面被错误选成一个会留下失败日志；这不读取原16历史，也不验证真实刚体状态。预计短任务，默认前台，显示逐项结果和退出；逐命令≤300 s、地址空间/峰值RSS≤512 MiB、阶段加报告≤8 MiB，真实查询/模拟/训练/下载均0。

**同步一次。** 审查当前科学职责后，在既有服务器仓库、没有运行任务的checkout核对路径和未提交内容；不安装依赖，不重跑旧阶段：

```bash
git rev-parse --show-toplevel
git status --short
```

工作树干净时同步并记录完整提交：

```bash
git pull --ff-only origin review/spatial-history-baselines
git rev-parse HEAD
```

**SH-04-R4-3b-object-v1/run。** 读取12项绑定来源及已审D-087提案，运行24项科学人工例和8项运维检查；不读旧物理outputs或借旧marker。入口核对当前源码与本次完整Git提交，绑定文件须已提交且干净。新固定目录为`/root/autodl-tmp/spatial-history/sh04-r4-3b-object-v1`，已存在仅verify，失败/中断不自动重试或覆盖：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_object_association_check.py run
```

成功标志：`SH-04-R4-3b-object-v1 VERIFIED tests=32 exit=0`。run已终检；重连只用同版verify核原证据，不重新执行科学函数或测试：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_object_association_check.py verify
```

**同阶段/export。** 完成或失败退出后导出原证据；失败只保留诊断，不启动依赖任务。不同内容的已有报告拒绝覆盖：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_object_association_check.py export
```

导出目标为`results/spatial_history_r4_object_association_v1.json`；成功需`SH-04-R4-3b-object-v1 EXPORTED status=passed ... exit=0`，`failed_or_incomplete`仍回传原诊断。报告包含测试身份、原日志/回执文本与摘要、实际时间/资源和零真实查询范围；人工例通过不表示真实对象关联或地图/控制就绪。

**纯Git收尾。** 通过或失败报告都保留，精确提交同一文件，之后本地pull核验证据：

```bash
git add -- results/spatial_history_r4_object_association_v1.json
git commit -m "results: export R4 public object association checks"
git push origin review/spatial-history-baselines
```

b的原代码/回执已核验，后续按D-089联合工程阶段执行；此处历史命令不应在修改后的METHOD/DATA上重跑，原32项也不认证新c/d。

### R4-3a固定服务器检查阶段（D-086，27项已验收；以下保留复现命令，无需重跑）

白话：输入已交付的本职责源码/固定配置和人工例，输出可复核的测试回执与小报告。例如裁剪深度误计覆盖会留下失败及原日志；这不是对原16条真实历史重新选帧，更不运行动力学。预计短任务，前台显示逐项结果和退出；单命令≤300 s，地址空间/峰值RSS≤512 MiB，阶段连报告≤8 MiB，0新模拟/训练/下载。

**同步一次。** 在已经核实的服务器仓库、没有运行任务的checkout核对并同步；本阶段只用既有隔离环境，不安装依赖。

```bash
git rev-parse --show-toplevel
git status --short
```

工作树干净时：

```bash
git pull --ff-only origin review/spatial-history-baselines
git rev-parse HEAD
```

**SH-04-R4-3a-coverage-v1/run。** 只读取绑定源码/共享配置，运行27项人工/运维检查；不依赖原v2物理目录或旧测试marker。入口自动核对11项来源的当前字节和本次Git提交，禁止未提交的绑定文件。固定写新目录`/root/autodl-tmp/spatial-history/sh04-r4-3a-coverage-v1`；已存在只verify，失败/中断不重跑或覆盖。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_coverage_check.py run
```

成功标志：`SH-04-R4-3a-coverage-v1 VERIFIED tests=27 exit=0`。run已终检；重连只需同版`verify`核原回执，不再执行选择或测试：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_coverage_check.py verify
```

**同阶段/export。** 成功或失败均导出已有证据；失败/中断只保留诊断，不启动依赖步骤。源码改变导致核验不通过会标明，不能借旧回执认证新版本。不同内容的已有报告拒绝覆盖。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_coverage_check.py export
```

完整验收需`EXPORTED status=passed`及退出0；`failed_or_incomplete`仍回传诊断。导出目标固定为`results/spatial_history_r4_coverage_v1.json`，含原始证据文本/摘要、完整测试身份及资源/范围。这一检查通过只允许下一职责审议，不执行对象/地图/模型；其实际运行预算和代码审查独立。

**纯Git收尾。** 报告成功导出后（通过或失败都保留），精确提交同一文件，不修改科学代码或重建阶段：

```bash
git add -- results/spatial_history_r4_coverage_v1.json
git commit -m "results: export R4 public coverage contract checks"
git push origin review/spatial-history-baselines
```

### R4 v2完整服务器阶段（D-084，已完成验收；以下保留复现命令，无需重跑）

白话：同一版本先核人工合同与工程接线，再生成固定四家族，最后验收/导出。输入是已审完整提交和真实租赁剩余额度，输出完整原生数据及含失败细节的小报告；例如推头碰门后整批未通过，也能直接导出原接触摘要。这不是自动扩跑64家族或训练。预计生成耗时只能参考旧批外推，默认前台；7200 s是硬上限，不是实测预计时长。

**同步一次。** 在已核实的仓库工作目录中、checkout没有运行任务时先检查；有未提交文件先保留处理。这里不重新猜测服务器仓库路径。

```bash
git rev-parse --show-toplevel
git status --short
```

工作树干净且本批代码审过后：

```bash
git pull --ff-only origin review/spatial-history-baselines
git rev-parse HEAD
```

记录打印的完整40位提交用于后续明确放行。从这一步到导出不再pull、不改绑定文件、不在中途提交报告。

**SH-04-R4-contract-v2。** 使用既有隔离环境，33项标准库人工例；只写新合同目录`/root/autodl-tmp/spatial-history/sh04-r4-contract-v2`及`results/spatial_history_r4_contract_v2.json`，不访问物理现场。已有目录只verify，不重跑；失败/中断保留。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_contract_check_v2.py run
```

继续条件：`SH-04-R4-contract-v2 VERIFIED tests=33 exit=0`。run已终检，不必重复verify；成功或失败都可以用同版导出：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_contract_check_v2.py export
```

只有`EXPORTED status=passed`才继续。失败报告仍保留原日志/回执，先回传诊断，不启动依赖步骤。单步≤300 s、512 MiB地址空间/RSS、阶段加报告≤8 MiB，0模拟/渲染/训练/下载。

**SH-04-R4-2-engineering-subset-v2/capacity。** 只读可见cgroup CPU/内存和数据盘空间，不预留资源，df不代替租赁配额：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check_v2.py capacity --workers 4
```

**同阶段/check。** 自动验证同提交v2合同回执、旧R4-1/E0报告原Git来源、v1失败报告与旧现场清单、保留空间和耗时账本，再检查新64行设计及37项测试。编译MuJoCo XML而不积分/渲染；只写新目录`/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v2`。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check_v2.py check
```

继续条件：`SH-04-R4-2-engineering-subset-v2 CHECKED tests=37 exit=0`。失败先export。新目录已存在则只核验原check；中断和失败不自动重跑，不删除现场。

**同阶段/run。** 前提：上面完整提交已经审过、两组新检查通过、4路容量通过，并且租赁后台确认用于本批的剩余新数据额度至少8 GiB。`--reviewed-code`必须逐字等于check记录的完整提交；不能用短hash、旧提交或另一次测试marker。下面两个输入由本次人工放行填写，未填写或非法值会拒绝运行；历史截图/df空闲量不能代填。

```bash
read -r -p '已审的完整40位提交: ' R4_V2_REVIEWED_CODE
read -r -p '租赁后台确认的本批剩余新数据额度 GiB: ' R4_V2_NEW_DATA_GIB
```

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check_v2.py run --workers 4 --reviewed-code "$R4_V2_REVIEWED_CODE" --available-new-data-gib "$R4_V2_NEW_DATA_GIB"
```

每个家族前台显示history/branch/write及退出，父进程约30秒显示资源进度。固定16历史/144首次/144重放；每家族原生数组/轨迹保存在execution/对应ID/data。运行连首次export≤7200 s；每家族384 MiB含1 MiB失败保留、阶段连报告8 GiB、每进程6 GiB、树30 GiB。旧批268.25082197599113 s计入8小时总生成预算，旧现场/报告保留在1 GiB共享池预留内。压缩率由本批真实核验，超限停止保留前缀，不能临时增额或少存数组。

`COMPLETED accepted=True|False exit=0`表示固定工作已完整结束，false表示工程条件失败；异常退出保留failure/未启动项。已有execution时run只核验，绝不续算或重复模拟。无论真/假，完成后均进入验收和导出，不再逐步询问。

**同阶段/verify。** 只读核验同源回执、三个渠道清单、全部36标签/72组数组每家族、原生形状/无损摘要、候选控制槽、重放与总门；不模拟。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check_v2.py verify
```

完整证据标志`VERIFIED accepted=True|False exit=0`；不完整/异常也继续导出失败证据，不重跑。类别交集全非空会让总accepted=false，即使family_gates_passed=true；任何报告都不自动开放其余60家族/学习。

**同阶段/export。** 输出固定`results/spatial_history_r4_engineering_subset_v2.json`，原始数组留数据盘。包含全部家族结果、E0计数、接触摘要、来源/manifest/退出/失败与固定预览；无需追加诊断脚本。已有相同报告核验复用，不覆盖不同报告。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check_v2.py export
```

`EXPORTED status=passed|failed|failed_or_incomplete|integrity_failed ... exit=0`是导出状态，不代表模型有效。生成前check失败也用此命令保存现场。全部计算停止、两份报告实际存在后一次Git收尾；若前一步合同就失败，仅提交实际存在的合同报告，不假造第二份：

```bash
git add -- results/spatial_history_r4_contract_v2.json results/spatial_history_r4_engineering_subset_v2.json
git commit -m "results: export R4 v2 contract and engineering subset audit"
git push origin review/spatial-history-baselines
```

本地pull后按原提交来源只读验收。失败保留，不按结果换家族/改控制/阈值；通过也只说明这四家族工程条件，不代表任何模型接入或有效。

### R4-2失败诊断（已完成，保留复用说明）

白话：这里读取已经完成的失败现场，区分“公开几何缺少可用墙顶像素”和“推头或物块实际碰到什么”。输入是原报告绑定的压缩预测和64条首次轨迹；输出仅为已有拒绝计数、接触对及首末/峰值时刻的状态。例如`gate_contact_steps=0`只排除了物块碰门，仍需检查`pusher/gate_*`接触。这不是重跑模拟、重评分或批准改变相机/门宽/控制。

步骤ID为`SH-04-R4-2/failure-diagnostics`。新入口`ops/spatial_history/r4_failure_diagnostics.py`是补齐原export未包含的只读诊断能力，不修改原入口或其来源绑定。前提是原失败报告SHA与封存目录一致；按报告清单核验每项读取的字节/SHA，核对原几何候选数和轨迹终点，结束前再次核对输入。覆盖全部4家族×16条主分支及4家族×16个E0查询，不挑成功/失败例，不再次读取重放轨迹。原重放证据沿用原报告。

`positive_steps`是同一几何体对发生正力接触的时间步数，每步多个求解接触点只计一次；`first/last/peak`保存对应实际状态，不能把首末之间所有时间都算作持续接触；`peak_point_normal_force_n`是单个接触点的峰值法向力，不是接触对总力。阈值读取原提交的`contact_force_min_n=1e-6`；几何`rejected_counts/incomplete_reasons`来自已保存预测，不重跑提取器。

本次运维上限300 s、512 MiB进程地址空间、8 MiB报告；预计短任务，前台显示逐家族进度。只写`results/spatial_history_r4_failure_diagnostics_v1.json`，原服务器目录只读；无断点续算，已存在诊断报告拒绝覆盖。中断未写出报告时可重新只读汇总；已有报告先核对完整性，不删除现场。0模拟/训练/下载。入口尚未在服务器执行，本地只做AST、输入键/路径及报告静态核查。

checkout当前无任务运行时同步一次并执行：

```bash
git pull --ff-only origin review/spatial-history-baselines
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_failure_diagnostics.py
```

继续条件是终行`SH-04-R4-2 DIAGNOSTICS EXPORTED families=4 branches=64 geometry=64 ... exit=0`；之后仅提交该新诊断报告：

```bash
git add -- results/spatial_history_r4_failure_diagnostics_v1.json
git commit -m "results: export R4 failure contact and geometry diagnostics"
git push origin review/spatial-history-baselines
```

回传后核验输入来源并定位接触；任何科学配置/代码修订需另行具体登记与审查，不自动重跑或替换首4家族。

### R4-2固定交付与服务器步骤（原版已完成，供复用核验）

白话：本阶段输入是事前固定的4个家族，输出完整物理/存储审计。比如先做不模拟的源码检查，审过后生成原清单首4家族，再核验和导出。它不是自动生成64家族的一键流水线；后续60家族没有入口。每步都使用这次同步的同一份代码，不为导出另改脚本或要求pull。

沿用已核实仓库及隔离环境。checkout空闲且`git status --short`没有输出时同步一次；有未提交内容先保留处理：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git pull --ff-only origin review/spatial-history-baselines
```

**R4-2/capacity**只读CPU/cgroup/RAM和文件系统容量，不创建阶段、不模拟；4路需要30 GiB可见可用内存加512 MiB余量。容量不够不静默降并发，可明确选择1–3路重新核容量；最多4路是本工程子批只有4家族，不改D-079后续最多12路提案。`df`不是实际租赁配额，生成时需另明报可用于本批的剩余新增数据额度。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check.py capacity --workers 4
```

**R4-2/check**允许先执行：核验旧R4-1/E0原Git报告和现有环境锁，运行22项新检查，包括小型人工轨迹、无损字节、配置和XML编译；0模拟步、0渲染、0训练、0下载。目录固定为`/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v1`，不接受自选运行目录。成功标志`SH-04-R4-2-engineering-subset-v1 CHECKED tests=22 exit=0`。已有目录只核验成功回执，失败/无回执不重试；必要时直接用本版export保留诊断。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check.py check
```

**R4-2/run**仅在用户审过代码、[METHOD首批资源](METHOD.md#r4-generation)且check成功后执行。入口必填`--reviewed-code`，值为check记录的完整40位提交；必填`--available-new-data-gib`为已核实剩余新增数据额度，至少8，不根据底层df猜测。完整调用形式为`.../bin/python ops/spatial_history/r4_generation_check.py run --workers 4 --reviewed-code <已审完整提交> --available-new-data-gib <实际额度>`；尖括号为说明位，当前不能直接粘贴执行。该显式调用记录首批工程放行，不合并main、不解封确认。耗时尚未实测，先前台显示进度及每个家族退出；7200 s是保守上限，不据上限假定实际需后台。各家族完整16首次+16反序重放及E0/信息门后，成功运行打印`COMPLETED accepted=True|False exit=0`；False是完整工程失败，不是运行异常，也不能进入学习。

**R4-2/verify**只读复查所有文件/三渠道清单、完整解压字节和回执；不是重跑物理。成功封存计算复用；缺run回执则拒绝，不补造完成。独立verify/重复export的只读运维时间另计，不重复消耗生成预算。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check.py verify
```

**R4-2/export**首次成功导出与run合计≤7200 s，使用剩余时间；报告固定为`results/spatial_history_r4_engineering_subset_v1.json`。完整成功/失败、运行中断及check失败分别导出状态；失败诊断不能升级为通过。重复导出只核验同一报告和来源，不覆盖；pending未发布不自动重试。原始大数组留服务器，先生成报告再进行精确Git收尾。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/r4_generation_check.py export
```

继续条件：4家族全工程门成立、无损存储及实际资源验收、用户代码审查。类别捷径未排除时如实标工程小试；384 MiB/家族的事前硬上限只提供完整64家族原始产物24 GiB的分配上界，不证明剩余家族都能完成，也不代替服务器租赁剩余配额。首批实际来源/输出可继续复用，但其余60家族和confirmation仍需后续明确放行；本版本不会自动启动。

### SH-04-R3/E0 并行版本固定交付与服务器命令（已完成，保留复现路径）

白话：这一阶段先检查“历史里有的信息，是否能由只读公开深度的方法恢复出来”。输入是已验收R2的四份公共历史及原R3读取器，输出是16份封存的几何预测和独立评估；例如4个worker分别处理4项独立查询，每项仍从空状态恢复自己的观察。worker是处理任务的独立子进程，不表示4个模型或4份新样本。具体输入输出和误差含义见[METHOD](METHOD.md#e0-public-geometry)。

同阶段入口已完整交付，不需为测试、验收或导出再同步代码。沿用已核实仓库及隔离环境；checkout空闲且`git status --short`无输出时同步一次，若有改动先保留处理，不覆盖：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git fetch origin
git switch review/spatial-history-baselines
git pull --ff-only origin review/spatial-history-baselines
```

**E0/capacity**：用户要求先确认如何选worker数。同步后先运行这条只读命令；它不创建阶段目录、不运行测试或恢复任务：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/public_geometry_check.py capacity
```

输出`cpu_capacity`、`available_memory_gib`、可行的`feasible_workers`、资源允许上限`maximum_feasible_workers`和起步建议`recommended_initial_workers`。起步建议至多4路；例如CPU/RAM只容纳2路就建议2，可容纳12路时仍先建议4，同时列出12的资源上限。它只核验可见资源，不是吞吐测速，不声称建议值最快；正式run会重新核验配额。

**E0/run**：先核验请求worker数对应的CPU affinity、可见cgroup配额和可用内存；不足时在创建运行目录和启动测试前拒绝，不静默降并发。核验R2/R3原Git绑定、报告、服务器回执和公共文件摘要后，先运行97项新检查，再对4世界×full/A/B/recent共16项公共查询并行派发。所有公共子进程正常退出、预测完整封存后才解析私有XML并逐项验收；测试和私有评估阶段仍串行。不会重跑原R2物理生成或R3测试。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/public_geometry_check.py run --workers 4
```

默认4路；开工前可将上条命令的数值改为1至16，例如`--workers 8`，不能在同一已启动阶段更换并发数，也不同时运行多条run。前台显示97项检查、乱序完成的16条公开恢复与16条私有评估；回执按固定查询ID排序。新目录`/root/autodl-tmp/spatial-history/sh04-r3-e0-public-geometry-parallel-v1`，报告为`results/spatial_history_public_geometry_parallel_v1.json`；原R2/R3及0b1640f串行版路径保持原样。若旧E0目录已存在，新入口停止，不能以换版本为由重复计算。成功标志`SH-04-R3-E0-public-geometry-parallel-v1 VERIFIED tests=97 queries=16 workers=4 exit=0`（workers显示实际登记数）。已有完整成功只核验复用；失败、中断或未发布临时回执不自动重试。

正式run（含测试、来源核验、恢复、评估和终检）与首次成功export合计上限1800 s，各自计入1 s文件收尾保守上界；首次export只能使用剩余时间。新阶段文件加导出报告总计≤64 MiB。每个进程的地址空间上限512 MiB，整个进程树的RSS按`(workers+1)×512 MiB`保护：4/8/16路分别为2.5/4.5/8.5 GiB；启动时还要求额外512 MiB机器可用余量，因此最低可用内存分别为3/5/9 GiB。原512 MiB整体限制明确由D-078变更，不能称全部预算不变。50 ms采样和存活进程高水位之和作保守保护，不冒称连续精确峰值；可见容器限制核验不代表不可见宿主约束或资源预留。run回执保存终检统计；export区分序列化前观测峰值和包括写入的保护上界。0模拟、0训练、0权重、0新划分，不新增依赖。

**E0/export**：run有正式回执后导出；成功需再次核验完整来源、封存预测及独立匹配，失败只导出诊断，不冒充通过或预算通过。每份实际XML文本/摘要及恢复区间、像素支持都进入审查报告，私有内容不进入恢复器。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/public_geometry_check.py export
```

继续条件为`EXPORTED status=passed|failed ... exit=0`；其中failed仅表示失败诊断已导出。正式回执/报告先写临时文件，收尾门通过后才发布；无正式回执的硬中断不能补造成功，已有`.pending.json`不得自动重试。重复导出仅核验并复用同一报告，内容不同则拒绝覆盖。必要时可独立只读核验：

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/public_geometry_check.py verify
```

verify/export自动恢复原回执登记的worker数和资源门，无需再加`--workers`；不会以默认4覆盖已登记8路。独立verify、成功复用与重复导出是可选的运维核验，不再运行恢复器；每次另受1800 s和原登记内存上限保护并显示耗时，不能隐去首次正式导出的成本。首次导出预算耗尽时保留run回执，不能重新给实验1800 s。失败诊断导出另受单次保护，仍保持失败。

完成导出后精确回传同一文件：

```bash
git add -- results/spatial_history_public_geometry_parallel_v1.json
git commit -m "results: export parallel E0 public geometry audit"
git push origin review/spatial-history-baselines
```

报告回传后先做只读证据审查。即使E0全部通过，也不自动运行三模型适配、探针或SH-05，不改变旧报告的false字段。

### SH-04-R3/public-input 历史服务器命令（已完成，保留复现路径）

本批是D-072登记的独立公开读取职责，代码位于`public_reader.py`，必要检查与实际文件审计位于`public_input_check.py`。原运行88c42b7、报告a9275e7的18项服务器检查及32次真实查询已经完成并只读核验，见LOG-109，不重跑；下列保留复现命令。原R2回执不能认证新读取器。方法及具体输入输出见METHOD/DATA。

白话：输入是已验收R2的4个公共文件，输出是只能包含历史、数值速度和目标的查询与可核对摘要。例如读LL文件、查询LR控制时，控制名称和文件路径不会传给后续方法。它不恢复门洞几何，也不代表已运行学习模型；读完输入边界并审查后，才交依赖它的下一科学职责。

阶段一次同步后按顺序运行；以下路径沿用已核实仓库，不重建环境。checkout空闲且工作树干净时：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git fetch origin
git switch review/spatial-history-baselines
git pull --ff-only origin review/spatial-history-baselines
```

**SH-04-R3/public-input/run**：父进程只读R2已验收报告、原Git来源、启动/完成/4历史回执及4个public.json；先核验原摘要，子进程运行18项新检查，然后对4世界×4控制各构造完整历史与最近2帧查询，共32次。仅返回查询摘要、字段/形状、不变性检查、耗时和峰值内存；不打开原XML、快照内容、未来数组或轨迹。读取器本身只打开显式公共文件；来源核验属于外层审计权限。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/public_input_check.py run
```

预计数分钟，前台显示测试和32次读取，失败以非零状态返回；子进程上限30分钟，新持久产物上限8 MiB，0模拟步/0权重下载/0训练步，不新增依赖。新目录为`/root/autodl-tmp/spatial-history/sh04-r3-public-input-v1`，原R2两个目录只读。成功标志`SH-04-R3-public-input-v1 VERIFIED tests=18 queries=32 exit=0`。已有成功回执只验证复用，失败或无回执的中断保留，不重新运行。独立查看验收可用同入口`verify`，不必重跑`run`。

**SH-04-R3/public-input/export**：run保存父回执后导出成功或失败证据；核验原提交绑定及新产物摘要。没有父回执的中断停止诊断，不能补造成功。不同内容的已有报告拒绝覆盖。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/public_input_check.py export
```

导出标志`SH-04-R3-public-input-v1 EXPORTED status=passed|failed ... exit=0`仅表示导出完成。纯Git回传使用同一版本的精确文件：

```bash
git add -- results/spatial_history_public_input_v1.json
git commit -m "results: export R3 public input boundary audit"
git push origin review/spatial-history-baselines
```

本节为原公开读取批次的复现路径；E0的当前交付及命令见上节。原SH-03视觉读取、论文资产/资源与独立环境锁仍依D-073的适用性审查分别交付；训练与强对照协议在R4另审，不沿用暂停v1的特征/数据/训练预算。

### SH-04-R2 历史服务器固定命令（已完成，保留复现路径）

本批已完成并按原绑定验收，无需重跑或再次check；下列仅为历史命令，不是当前R3入口。

白话：同一版本包含检查、生成、验收和导出，输入是已批准配置及原SH-03来源，输出完整成功或失败证据。例如第一个世界的某条控制没送达，仍运行其余固定分支并在最后给失败清单；程序异常则立即保存现场。这不是自动调参或训练流水线。

仓库与环境沿用已核实路径。checkout空闲、无运行任务，且`git status --short`无输出时同步；若有输出先保留并处理未提交工作，不reset或覆盖。明确切换到本批分支，不能在main上直接pull审查分支：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git fetch origin
git switch review/spatial-history-baselines
git pull --ff-only origin review/spatial-history-baselines
```

**SH-04-R2/check**：只读核验旧SH-03原提交/摘要、冻结提案与当前配置、环境及数据盘；独立验证真实EGL，执行旧公共帧测试及四个新模块的必要测试。新科学代码不借旧回执通过。本批测试身份由源码静态清单与实际unittest清单双重核对，失败/跳过均不通过；只写新目录的环境、check回执及短传感器夹具，不执行16条完整任务。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/two_gate_check.py check
```

继续条件：出现`SH-04-R2 CHECK VERIFIED tests=... renderer=... exit=0`。失败先export，不反复check重跑。已有同源成功回执只核验复用。

**SH-04-R2/run**：自动核验check成功和来源，再前台按37步完成4历史、16首次执行、16新实例反序重放及汇总。只消费本批公开/私有文件，不读旧test，不下载或训练。新阶段科学判定false与运行异常分开记录。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/two_gate_check.py run
```

通过标志：`SH-04-R2 VERIFIED unique_branches=16 replay_branches=16 exit=0`。成功完成后重复run只核验复用；完整失败、部分失败或中断不能自动重跑。单独只读验收可用同入口`verify`，不必为查询状态重跑物理。

**SH-04-R2/export**：成功或失败均用同一命令，只读核验原Git来源、manifest与退出/中断状态，导出完整诊断及原图，数组仍在数据盘。报告已存在且内容不同则拒绝覆盖。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/two_gate_check.py export
```

导出标志：`SH-04-R2 EXPORTED status=passed|failed ... exit=0`；export成功不等于实验通过。固定批次完成或停止后，按精确路径回传：

```bash
git add -- results/spatial_history_two_gate_engineering_v1_lfsha1.json
git commit -m "results: export SH-04-R2 two-gate engineering audit lfsha1"
git push origin review/spatial-history-baselines
```

本地拉取后只读核验来源、全部4×4实际成功矩阵、物理异常/可见性、121个信息检查和原图，再解释是否满足本批构造。没有完整公共几何恢复和成熟对照结果时，不进入模型有效性结论。

### SH-03/v2 历史服务器固定命令

以下仅保留原版本57d01aa的操作说明，不是当前待执行任务；METHOD/DATA已进入新提案，不能在当前checkout冒用旧绑定重跑。原成功回执已经验收，无需再次同步或导出。

白话：同一次同步提供“检查新适配→生成完整16例→核验和导出”，避免步骤切换再改入口。输入已验收SH-02报告/源码与固定登记，输出独立案例回执；例如某例完整生成但没有预期碰撞，会保留为audit_failed并继续余下固定例。这不是自动调参或训练流水线。

已核实服务器仓库`/root/Emboddied_Spatial_Memory`，环境`/root/autodl-tmp/spatial-history-venv-v1`；复用环境和EGL，无需安装或删除旧数据。当前已在review/spatial-history-development分支，checkout空闲且`git status --short`无输出时同步一次：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git pull --ff-only origin review/spatial-history-development
```

若当前分支或路径与已核实状态不同，先只读核对，不用reset；本阶段同步后不再pull。新运行目录固定`/root/autodl-tmp/spatial-history/sh03-development-v2-wall-clearance`。旧v1原始目录与报告不改；新METHOD/DATA和适配源码不借旧回执认证。

SH-03/check：检查已验收SH-02原Git绑定、原模拟器未变、v1完整失败报告及原Git来源、环境freeze和新阶段来源，然后服务器执行原8项加新增4项（共12项）。写新目录的环境/启动记录和`check/`，只读旧报告及源码；不模拟16例。成功标志`SH-03 CHECK VERIFIED tests=12 exit=0`，同版成功回执复用，失败不重跑。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/development_check.py check
```

SH-03/run：只在上述成功后运行，自动核验依赖。用新墙位置前台生成原固定16对，每例保存4条原始分支和4次反序重放；预计5–10分钟。每例完成先写退出回执/摘要，再启动下一例；新版本已有完整回执只核验复用，从最早未启动例继续，不借v1的12例通过状态。完整物理审计失败仍记录并做完固定清单；运行异常停止余下案例。启动后无回执的中断现场拒绝覆盖或自动重试，须先诊断。只写本阶段新数据盘目录，不访问旧outputs或封存test。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/development_check.py run
```

成功标志`SH-03 VERIFIED cases=16 unique_branches=64 replay_branches=64 exit=0`。否则保留全部已生成数据，导出诊断，不扩大计算；2 GiB按案例边界检查，底层df不代表租赁配额。无需重复run来查询结果，独立`verify`可只读核验。

SH-03/export：通过或已保存退出回执的失败均可导出；自动核验逐例manifest、完整状态和新代码绑定，不重模拟。导出成功只表示报告生成，审计看`status`。父进程中断没有退出回执时先诊断，不补造成功证据。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/development_check.py export
```

成功标志`SH-03 EXPORTED status=passed|failed ... exit=0`。不同内容的同名报告不覆盖；固定批次完成或停止后回传这一份报告：

```bash
git add -- results/spatial_history_development_audit_v2_wall_clearance.json
git commit -m "results: export SH-03 wall-clearance revision audit"
git push origin review/spatial-history-development
```

本地pull后只核验导出摘要、逐项失败和原PNG，不本地跑测试/模拟。通过仍只证明这16种开发设置的物理与输入条件，不能宣称模型利用了空间历史；下一科学协议须本批验收和审查后交付。

### SH-02 已验收背景（历史记录，不是当前执行指令）

依据：初次EGL环境问题已解决，实际renderer为RTX 4080 SUPER、驱动595.71.05。球形推头版的两份失败报告d087389和只读接触诊断0c4335e均已回传核验，具体失败证据见LOG-105。物块与推头约2.916 s开始接触、约4.05–4.08 s最后接触，随后物块停止，推头继续移动；对应挡板布局约5.048 s出现推头–墙接触。物块全过程y≤0.214694 m，未到墙近侧面0.575 m。这足以定位原预期的持续推动没有实现，不把机器人撞墙改记成物块撞墙。

本次单一科学改动：球形推头改为宽0.30 m、前后厚0.05 m、高0.05 m的平面推头；原质量/初始中心、速度控制、物块、墙/屏、相机、求解器和通过门保留。配置文件名沿用v1接口，内容version/model已标v2，原球形配置由原提交与失败产物复现。v2在同一固定工程对上已产生预期物块撞墙/通过对照，成对终点距离约0.292881/0.319261 m；不是对任意新场景的可靠性结论。

后续评分边界：目前goal半径0.5 m仅作为查询字段，四个终点都在该半径内，不能直接把本次“受阻/通过”当成目标成功/失败或动作选择收益。SH-04仍须事先冻结与任务相符的评分、阈值和预算；当前不据此更改工程配置或重跑。

### SH-02/v2 历史固定命令

以下仅保留复现路径。SH-03已扩充METHOD/DATA，不能在新checkout重跑这些命令来借用旧回执；旧完成任务按原版本复用，当前命令仅为上面的SH-03。

用户服务器已核实仓库为 `/root/Emboddied_Spatial_Memory`，数据盘为 `/root/autodl-tmp`。复用已验收EGL的环境 `/root/autodl-tmp/spatial-history-venv-v1`；新产物 `/root/autodl-tmp/spatial-history/sh02-engineering-v2-flat-pusher`，新报告 `results/spatial_history_physics_v2_flat_pusher.json`，默认路径已随修复更新，原失败目录/报告不覆盖。当前审查checkout无任务运行、工作树干净时同步一次：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git pull --ff-only origin review/spatial-history-physics
```

后续本阶段全部使用这次交付版本，无需步骤间pull。32项检查和全部物理/控制源码字节不因推头配置修复改写。

SH-02/setup：本机服务器环境已经安装且通过GPU EGL探测，依赖清单未变，当前可直接run，其内部会检查freeze。新服务器重建时才需要本步骤及系统EGL依赖和上下文检查：读取已提交依赖清单，用Linux Python 3.11/3.12创建隔离环境；前台显示安装输出、记录freeze和退出状态。成功且匹配的环境只核验复用，失败/中断目录拒绝重建覆盖。

```bash
python ops/spatial_history/physics_check.py setup
```

继续条件：`SH-02 ENV READY ... exit=0` 或 `SH-02 ENV VERIFIED ... exit=0`。安装失败停在当前步骤并保留日志，不启动依赖计算。

SH-02/run：自动核验已批准SH-01回执、原实现字节未变、当前源码提交干净和隔离环境，再前台启动独立Linux进程。固定1对世界、4条首次控制分支、4条反序独立重放；每分支4.9 s模拟时长、2450物理步，15帧历史。原20项回归与12项物理检查一并执行。v1实测套件11.830 s，v2需实际计时，前台逐分支报告。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/physics_check.py run
```

读边界：SH-02绑定清单、SH-01导出、隔离环境；不访问旧outputs或封存test。写边界：上述SH-02新产物目录，另由安装步骤写新环境。成功标志 `SH-02 VERIFIED tests=32 original_commit=... exit=0`；`receipt.json`保存实际时间、退出、源码/合同绑定和所有产物摘要。再次run只verify，不重做。失败或进程崩溃保留现场、返回非零并允许导出诊断；不静默换后端/场景/目录重试。

SH-02/export：成功、普通断言失败或子进程崩溃后只要父进程已写receipt均可导出。自动验证原始产物manifest，不重跑；报告包含环境/来源摘要、实际测试结果、每分支诊断、8张无损真实图像预览，以及首次分支的控制末尾位置和各接触对起止/步数/最大力。只读摘要复用已有诊断函数，省略完整逐接触段列表以控制报告大小；原trace保留。失败附日志尾部，`status=failed`不会变成物理通过。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/physics_check.py export
```

成功导出标志 `SH-02 EXPORTED status=passed|failed ... exit=0`；这个exit只表示导出完成，物理是否通过看status与报告receipt。若用户中断了父进程导致没有receipt，目录保留并需先诊断，不能用export补造运行成功。可独立使用同入口 `verify` 检查成功目录，无需重复run。

纯Git回传（只提交这份明确报告）：

```bash
git add -- results/spatial_history_physics_v2_flat_pusher.json
git commit -m "results: export SH-02 flat-pusher engineering checks"
git push origin review/spatial-history-physics
```

本地pull后只核验摘要、读失败诊断和原始PNG预览，不在本机重跑科学测试。继续条件为服务器检查通过、用户审查本批实现与画面；其后才交SH-03。若失败，先定位具体渲染/接口/物理问题，记录必要修复和新版本路径；失败样本不覆盖，不借用旧回执。训练、候选评分和大规模生成均不在本阶段。

### SH-01 已验收实现及历史命令

SH-01阅读顺序：

1. [METHOD 的当前候选与第一职责批次](METHOD.md#第一职责批次成对输入边界)和 [DATA 的字段合同](DATA.md#当前空间历史成对记录-v1d-062)。
2. [手工输入](../data/fixtures/spatial_history/manual_pair.json)：两个世界3帧，其中末2帧相同；每世界2条控制分支。2×2像素和未来坐标均手工指定。
3. [核心模块](../src/spatial_world_model/pair_contract.py)：`audit_pair → model_input`；[测试](../tests/spatial_world_model/test_pair_contract.py)验证20项合同性质。
4. [服务器入口](../ops/spatial_history/contract_check.py)：`run → verify → export` 已一次交付；不含生成/训练步骤。

已验收例子：`audit_pair` 返回 `contract_valid=true`、`early_visual_evidence_differs=true`、两个 `outcomes_differ_by_action=true`，但 `physics_and_visibility_verified=false`。同一候选的两个短历史查询完全相同；完整历史查询只因早期视觉证据不同而不同。改变私有未来标签不改变提取结果。[服务器回执](../results/spatial_history_contract_v1.json)只认证原提交的合同，不认证后续模拟器。

### SH-01 服务器固定命令

以下仅保留原提交492a7b6的运行记录/复现入口，不是当前同步指令。SH-02扩充了METHOD/DATA，原SH-01回执绑定旧文档字节；不能在新checkout上冒用旧verify认证新文档。SH-02读取不可变旧导出并重新运行原20项合同回归，使用全新来源绑定。

前提：在实际服务器仓库内、无运行中的任务使用该 checkout；先只读确认位置和工作树，不根据提示符猜路径。

```bash
pwd -P
git rev-parse --show-toplevel
git status --short
```

仅在该 checkout 空闲且工作树干净时同步一次（若已有同名本地审查分支，先检查提交，不重置它）：

```bash
git fetch origin review/spatial-history-contract
git switch --track origin/review/spatial-history-contract
git rev-parse HEAD
python --version
```

SH-01/run：Python 3.11或3.12，标准库即可；无需安装旧 Torch/NumPy 或新模拟器。预计为短检查，前台显示每项测试、结果和退出；未测速，不承诺实际时长。

```bash
python ops/spatial_history/contract_check.py run
```

成功标志：`SH-01 VERIFIED tests=20 ... exit=0`，实际测试名和计数从套件生成并写回执，不沿用旧 marker。读边界仅新模块、测试、夹具与 METHOD/DATA；写边界 `outputs/spatial-history/contract-v1/`，保存 started、日志、退出回执、输入输出和 hash。不会导入旧 CPMT、调用模拟器或读取旧 run/test。成功目录再次 run 只核验；失败或中断目录保留并拒绝静默重跑，不删除后“再试”。

SH-01/verify、export：只在 run 成功后执行；源码、合同和产物摘要须匹配。独立 verify 可用于重连，不重跑测试。export 自动包含 verify，日常无需重复调用：

```bash
python ops/spatial_history/contract_check.py export
```

导出 `results/spatial_history_contract_v1.json`，含完整服务器回执、实际测试名、源码/合同绑定、产物摘要和示例。不同已有报告拒绝覆盖；确需运行修复版本时先登记修复和新路径，再用 `--run-dir outputs/spatial-history/<明确新版本>` 及 export 的 `--report results/<明确新版本>.json` 保存新证据，不能用换目录静默重试同一失败。

继续条件：工程检查成功、用户审查 SH-01 代码与例子；其后才实现 SH-02。当前没有依赖的效果实验或下一科学模块被执行。审查批准须登记具体提交；后续改变科学语义重新审查。

## 工作区复用与历史保留

- 保留全部 `src/cpmt`、旧配置/schema/fixtures/tests/scripts/ops/results 路径与字节；新包独立，不导入旧 query、候选、教师或能量。
- 可复用来源登记、文件摘要、运行证据的工程思路；不为复用而耦合旧训练依赖。新代码用新回执，不能冒用旧 source hash。
- 第一轮没有必要搬迁旧源码或删除文件；大重构需明确解决实际依赖问题后再做。用户许可重构不等于要求清空工作区或服务器 outputs。
- ARKitScenes/ADT 已下载开发预览和 [来源清单](../data/manifests/visual_source_review.json)保留，完整接入暂缓；它们不能直接提供所需的机器人控制反事实分支。
- D-059/D-061 的32步旧计划由本计划替代为暂停状态；完整原文在 [转向前版本](https://github.com/JingzeSun/Emboddied_Spatial_Memory/blob/5f4fd115ed89876c0045d325af290d2636171e73/docs/PLAN.md)。不另建 archive/进度文件。


### R4-4资产环境阶段命令（D-091）

此版本只获取并核查源码/环境，不包含模型前向或训练。三份官方源码已锁/root/sh05-assets-v1；实际代码和环境变化后的独立接线入口另按该职责交付。当前主仓库同步一次后顺序执行，前一步exit=0才继续；失败现场保留，export读取现场不重跑。

```bash
python -B ops/spatial_history/r4_model_assets_v1.py sources
python -B ops/spatial_history/r4_model_assets_v1.py env_flowm
python -B ops/spatial_history/r4_model_assets_v1.py env_dreamer
python -B ops/spatial_history/r4_model_assets_v1.py export
```


### R4-4 D/F原生接口检查（D-091，待服务器）

资产环境回执成功且来源摘要一致后同步本职责，依次运行，预计每项小于20分钟，前台保留失败。仅人工原生模块检查，非本任务模型效果。

```bash
/root/sh05-assets-v1/flowm-env-v1/bin/python -B ops/spatial_history/r4_native_models_v1.py support_flowm
/root/sh05-assets-v1/flowm-env-v1/bin/python -B ops/spatial_history/r4_native_models_v1.py flowm
/root/sh05-assets-v1/dreamer-env-v1/bin/python -B ops/spatial_history/r4_native_models_v1.py dreamer
python -B ops/spatial_history/r4_native_models_v1.py export
```
