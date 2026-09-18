# 数据与观测合同

## D-210 地点 P0 数据合同（已批准，实现待审，生成关闭）

D-210 为地点/拓扑主实验建立独立于旧 VM-04 v1–v4 的数据版本。它解决旧合同一边把完整固定动作保存在可见 packet、一边用人为带噪格制造地点错误的冲突；输入是两个开发 house 的公开可达扫描、执行前封存的 12 条完整路线及真实逐步 RGB-D，输出 raw/provenance、部署适配输入和候选封存后才可读的 private evaluation。具体例子是 56 步 8 字路线：raw 保存 57 个观察和 56 个动作回执，模型只在关键帧接收连续位姿信念与若干边摘要。它不复用旧 24/64 步上限，不把 0.5 m 格、路线 phase 或 source house ID 当模型特征，也不表示当前已经生成任何 episode。

活动机器合同为 [`vm04_d210_dual_layer_p0_v1.json`](../configs/vsmt/vm04_d210_dual_layer_p0_v1.json)，纯核心为 [`d210_place_memory.py`](../src/vsmt/d210_place_memory.py)，关闭的阶段入口为 [`vm04_d210_p0_stage.py`](../ops/vsmt/vm04_d210_p0_stage.py)。当前五个授权位全为 false：source house 绑定、route plan 封存、raw 生成、adapter materialization 和 private evaluation 均未开放；`check` 可读合同，`seal-batch` 会在读取外部 house/route 文件和创建输出目录之前拒绝。

### 固定 12 槽与路线记录

槽 0–3 是 house slot 0 的 P01–P04，槽 4–7 是 house slot 1 的 P01–P04，槽 8/9 是 house slot 0 的 P05/P07，槽 10/11 是 house slot 1 的 P06/P08；seed 固定为 26091800–26091811。P09/P10 不进入 P0。每条 `vsmt-vm04-d210-p0-route-plan-v1` 必须在执行前包含：固定 slot/house slot/scenario/seed，完整有序 `actions`，每步显式 API request，`planned_action_count`、N+1 `observation_count`、关键帧 observation indices、公开构造来源声明和 SHA-256。平移请求只可为 0.25 m，RotateLeft/Right 只可为 90°，LookUp/Down 为 30°；`snapToGrid=true`、`forceAction=false`。

场景 `planning_action_count_hint` 只帮助路线搜索排序，不能拒绝一条结构条件成立的更长路线。没有 24 或 64 动作的科学上限；1–128 个动作均可封存，129 个在执行前因机械保护线拒绝，运行中不得截断。白话：128 防止坏规划器无限写动作，不表示 127 步比 129 步更有科学意义。例如 P01 的提示上沿是 32，但一条合法的 56 步 P01 仍必须被接受。它不授权为了塞进 128 而删掉回环或后续判别段。

`public/manifest.json` 只列 opaque `episode_id`、slot、scenario、route digest、动作/观察/关键帧数；不含 source house ID。`private/manifest.json` 才绑定 house slot、真实 source house ID 与 route digest。完整 `provenance/routes/slot_XX.json` 不属于部署目录；动作失败时保存已经完成的 raw 前缀和终止失败，禁止改 scenario、换 house 或补一个成功样本。

### 三种读取面

| 读取面 | 必须保存/可读 | 明确禁止 |
|---|---|---|
| raw / provenance | 观测 0；每个完成动作后的 RGB-D、动作请求/回执、成功或终止失败；完整 route；代码/配置/资源/worker 摘要 | 不直接作为模型输入；不得因失败覆盖、截断或补样 |
| deployable adapter | 当前 RGB-D 关键帧摘要、公开视觉几何/区域/关系、连续位姿信念、入边动作摘要、prior predicted memory、公共常数 | 完整逐动作序列、past actions、世界/模拟器 pose、grid place ID、private reference、future、teacher、route phase、instance/object ID |
| private evaluator | 模拟器连续 pose、reference place region/可达分量、回环 pair、真实关系端点、实体—地点挂载 | 候选生成前读取；排序、插入、删除或修补候选；进入任一模型值 |

白话：三种读取面解决“完整保存以便复现”和“不能把答案喂给模型”不是一回事。输入同一 episode 字节，raw reader 可重放第 17 个 RotateRight，adapter reader只能看到它所在关键帧边的压缩摘要，evaluator 在候选摘要封存后才看到该帧是否真回到旧地点。它不靠删 raw 来防泄漏，也不允许 adapter 通过文件路径间接打开 provenance。

### 关键帧、连续位姿信念与边动作摘要

`vsmt-d210-public-keyframe-v1` 只含 observation index、RGB/depth/公开视觉几何摘要、排序去重的公开 entity refs 和自身摘要。`vsmt-d210-continuous-pose-belief-v1` 含同一 observation index、以 observation 0 为原点的 episode-relative frame、`mean_x_y_z_yaw`、四维协方差对角、公开 source ID，以及强制为 false 的 `is_world_pose/defines_place_identity`。位姿信念是估计分布，不得从 simulator metadata 复制真值；正式 belief estimator 的代码/资产与误差校准仍须在 raw 运行前另审。

`vsmt-d210-transition-action-summary-v1` 连接两个关键帧，字段固定为起止 observation index、step count、八动作 histogram、有序且相邻同向合并的 90° quarter-turn 段、名义平移总长、估计 `delta x/z/yaw` 均值、三维协方差对角、置信度、对应 raw action span 摘要及自身摘要。它不含 `actions` 数组，`contains_per_step_action_sequence=false`、`may_directly_assign_place_identity=false`。例如 8 次 MoveAhead＋1 次 RotateLeft＋4 次 MoveAhead 输出 12 次平移、1 个 left quarter-turn 和 3 m 名义路程；它不告诉模型终点是 `place_7`。

唯一部署包 `vsmt-d210-place-adapter-packet-v1` 精确接收 `decision_time_s,current_keyframe,pose_belief,incoming_transition_action_summary,region_observations,relation_observations,prior_memory_ref,public_constants`。observation 0 的 incoming summary 必须为 null；其他关键帧的 summary 终点必须等于当前 observation index。prior 必须以 graph version 和整图摘要绑定。递归字段扫描拒绝禁止通道，即使它们藏在 region 或 prior 的嵌套对象里也失败关闭。

### 私有地点参考与指标文件

私有地点参考不保存“0.5 m cell = place”。同地点正例需连续位置误差≤0.35 m 且属于同一 reachable component；负例需距离≥1.5 m，或在路线封存前已登记为不同支路/房间；中间距离带不产生强制同异标签，yaw 不参与地点同一性。0.5 m grid 只能出现在 route planner/candidate retrieval 的公共常数与回执中，不能作为参考 place ID 或 adapter 的 node label。

每个 `vsmt-d210-place-episode-metrics-v1` 接收模型 place membership、回环 pair 判断、关系类型与端点、实体挂载、逐关键帧污染比例和五类错误分解；reference 在预测封存后打开。place pairwise 指标对任意节点改名不敏感；拓扑端点和实体挂载在评价器内部先按 observation overlap 对齐预测/参考节点名再计分。输出 pairwise P/R/F1、duplicate place、false merge、loop P/R、edge endpoint F1、entity attachment accuracy、contamination AUC 和 `candidate_miss/teacher_error/amortization_error/illegal_transaction/collateral_change`。

聚合文件分别保存 `all_p0_macro` 与 `headline_macro`；后者只含 P03/P04/P06/P07/P08，P01/P02 控制和 P05 支持场景不混入。精确动作积分、真值 pose 及历史 85.5% noisy-grid duplicate episode rate 都有独立诊断文件，不得拥有 `headline_eligible=true`，也不得进入 macro。85.5% 的单位固定为“3,000 个诊断回程中至少发生一次重复地点的 episode 比例”，不是错误率字段的通用定义、不是覆盖率，更不是模型分数。

### D-213 统一图、类型门与消融读取视图（已批准，纯核心待审）

[`vm04_d213_unified_typed_graph_v1.json`](../configs/vsmt/vm04_d213_unified_typed_graph_v1.json) 固定统一图节点/边类型、按作用域事务白名单、共同前端和五组消融。候选器在 seal 前把每项显式绑定为 `global/place/entity/surface/fragment/relation:<type>` 作用域；类型门只读公开当前观测、prior predicted memory、pose belief 和 transition action summary，输出候选计数及门审计摘要。teacher/private/future 不在函数参数中，封存后审计只验证而不编辑 catalog。白话：它先检查“地点能不能做 RETRACT”再让候选进入考场，答案文件只能给已经入场的候选评分；它不根据正确答案把被拒候选重新放回来。

`vsmt-d213-ablation-memory-view-v1` 是模型实际可见的记忆投影：`Place-4`只含place与place-place边，`VSMT-NoPlace`删除place及incident edges但保留如`entity→surface supported_by`，`VSMT-NoVersion`只含活动记录并移除version ID、有效期、predecessor、provenance与transaction log；`VSMT-Typed/VSMT-Flat8`保留统一版本图，区别只在selector类型mask。每个view绑定source graph digest和自身digest。它不删除raw/provenance里的审计历史，也不允许不同消融读取不同RGB-D缓存。

`vsmt-d213-graph-complexity-v1`从图和sealed catalog字节派生活动节点/边按类型计数、历史版本数及scope×atom候选数；正式episode还须由runner记录type-gate拒绝、illegal transaction、peak active nodes、peak candidates、runtime和peak memory。`contained_entity_refs`若出现，validator要求它精确等于活动`located_at/contains`边推导的排序实体集合。它不接受模型自报图规模，也不把缓存当真值。当前尚无真实episode文件；D-210 raw到非网格place候选的materializer接线仍关闭。

### D-214共享RGB-D缓存与资格回执

`vsmt-vm04-d214-shared-rgbd-frame-cache-v1`逐保存观察包含：observation/time、RGB/depth/calibration摘要、连续pose belief、可选入边动作摘要、packet-local匿名fragment、surface、单个非网格place observation、滚动free-space、当前visibility、SAM/semantic/config receipt摘要及整帧摘要。place observation含全帧DINO描述、belief均值/协方差、surface/free-space支持、`basin/bottleneck/unknown`和`room/corridor/unknown`归一概率；`persistent_place_id=null`、`identity_assigned=false`、`metric_grid_identity_used=false`、`semantic_class_defines_identity=false`。白话：输入当前公开画面和估计，输出一份谁都能读但谁都不能改的结构证据；例如`room=0.7`只表示当前语义估计，不会生成`place:kitchen`。它不含raw路径、mask像素、instance/object ID、场景名或private crosswalk。

`vsmt-vm04-d214-shared-rgbd-episode-cache-v1`按0开始连续封存frame，绑定DINO/SAM/semantic资产receipt和单一config摘要；`identical_method_cache_views`给VSMT/TAF/ELU/WFR/LOW独立clone并核canonical摘要完全相同。输入是同一episode的有序frame cache，输出五份等字节视图；它不允许方法私有前端或按P08附加字段。当前测试用显式概率和fixture token只验证代码边界，正式模型资产尚未产生，因此没有真实cache文件。

合同的`implementation_boundary`显式登记：公开派生输出组合与cache核心已实现，SAM/DINOv2/semantic真实推理编排、production raw reader和服务器执行均未实现。白话：测试可以证明同一组已验证mask/token/概率会被无泄漏地封成共同cache，但还不能把服务器上的原始RGB-D直接变成正式cache；这不是用`implemented=true`概括一半完成的前端。

P04回执保存所选两帧、公开名义距离、DINO cosine和“未用绝对阈值/未用旧四象限描述子”布尔；P08回执保存两段连续basin观察、其中连续bottleneck段、两端各一对跨帧稳定fragment及显式资格配置。room/corridor概率不进入P08 identity gate，private metadata只在seal后评价。四个P08数值在合同中仍为null，测试值不是冻结值。

`vsmt-vm04-d214-legacy-grid-retirement-readiness-v1`只在新cache全部生成、摘要验证、P04/P08重验、全路线重绑、有精确无通配符目标且无复现依赖时置`ready_for_user_requested_deletion=true`；`deletion_performed`始终false。它是删除前证据，不执行删除。

### D-215前端冻结资产、划分和训练后回执

[`vm04_d215_frontend_freeze_v1.json`](../configs/vsmt/vm04_d215_frontend_freeze_v1.json)保存SAM仓库/官方YAML/checkpoint字节与SHA-256、automatic-mask和proposal boundary摘要、双线性head的精确feature顺序/训练预算、house级split规则及P08四数。`asset_receipt_sha256`只覆盖实际核过的SAM来源和配置；`split_rule_sha256`覆盖决定性划分算法；`inference_config_sha256`覆盖架构、公开输入、训练/校准规则和标签隔离。输入是结果前合同，输出三类可复算摘要；它不把尚未生成的weights或partition manifest伪写成receipt。

`actual_partition_manifest_receipt_sha256`、`normalization_receipt_sha256`、`weights_sha256`和`training_receipt_sha256`当前必须为null。后续训练阶段须先按源manifest完整列出house→split并封存，再按位置hash、1 m最小间距、每house 8位置×4 yaw生成32帧，拟合train-only标准化和两个线性头，用calibration split选最低总NLL checkpoint并各拟合一个正温度；audit split只作冻结后诊断。任一P0/validation/confirmation house混入、frame级随机拆分、按P08 yield选checkpoint或改阈值均失败。白话：合同已经决定“谁能进哪一组、看哪些帧和怎样选模型”，但还没有声称模型训练完成；production reader仍不能读取一组零权重fixture冒充正式概率。

### D-216 split、训练包与真实权重回执

`vsmt-vm04-d216-reserved-house-manifest-v1`含排序的`rows[{house_id,roles}]`、按角色计数及自身receipt。角色词表恰为`P0_route_and_raw_development/VM04_validation/VM04_confirmation`，两间P0 house必须显式出现，三种角色必须在split前全部绑定。`vsmt-vm04-d216-house-split-manifest-v1`再绑定source inventory、D-215 split-rule和reserved receipt；10,000行逐一保存`house_id/split/hash_bucket/exclusion_roles/planned_observations`，excluded行不删除。输入是来源与保留角色，输出不可变partition；例如validation house仍在总行数内但`planned_observations=0`。它不含RGB-D、标签、路线或产率。

训练NPZ分片只允许八个数组：`features[N,396] float32`、`semantic_labels[N] uint8`、`structural_labels[N] uint8`、`house_ids/observation_ids`及`public_observation_sha256/semantic_annotation_receipt_sha256/structural_label_receipt_sha256`三个定长字符串向量。`house_ids`只用于检查整house split，拟合张量只有`features`；额外`scenario_id`等字段不是“忽略”，而是整片拒绝。`vsmt-vm04-d216-training-evidence-index-v1`逐观察保存两名盲标注者标签、仲裁/未决状态及D-215结构规则标签的内容寻址子receipt；bundle seal逐行核标签值和三个摘要，未决semantic分歧只能写`unknown`。`vsmt-vm04-d216-estimator-training-bundle-v1`保存每个分片相对路径、文件SHA-256、split、行/house/类别计数和各receipt向量摘要，并要求train/calibration/audit齐全、观察ID全局不重复。白话：evidence index证明标签摘要指向什么，bundle像封条防止训练时把另一个NPZ悄悄换进来；二者都不把标注或reference grid复制到推理cache。

真实训练目录拟生成`normalization.json`、`weights.json`、`training_receipt.json`、`success.json`及`stage_receipt.json`。normalization含396项train均值/标准差；weights含两个3×396矩阵、bias和temperature但不含house/观察/路径；training receipt含代码commit、partition/bundle/artifact摘要、seed、torch/device、epoch历史、best epoch、类权重及三split冻结指标；success只汇总互相绑定的receipt且固定`real_weight_receipt_reviewed=false/production_reader_authorized=false`。当前这些都尚未真实生成；测试fixture输出不得写回D-215的null字段或供production reader使用。

### D-211/D-212 执行封装与 raw smoke 文件（纠偏实现待审，真实文件未生成）

[`vm04_d211_p0_seal_single_smoke_v2.json`](../configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json) 将两间开发 house 固定为 `train:004270`/`train:008243`，分别绑定 source record 摘要 `79a1…026f`/`cdbd…bea7`。v1 和 `e5d7bed` 只保留阶段历史，不是最终生成基线。来源证据仍是既有只读 root-cause 报告，报告本身记录 0 episode、0 intervention；D-212 不把它们改叫 confirmation，也不因路线或 smoke 失败换房。

`survey-routes` 生成目录包含 `route-bundle.json` 与 `survey.receipt.json`。前者是 `vsmt-vm04-d211-route-bundle-v2`，恰好含按 slot 0–11 排序的 12 行；每行包含 `route_plan`、完整 `reachable_scan`、执行前 `public_route_evidence`、`scenario_receipt` 及 `execution_binding`。后者保存算法摘要、请求/实际worker数、CPU/RAM/GPU/磁盘依据、固定合并顺序、每槽完成动作数和失败摘要；失败时 bundle 不产生，receipt 保留且同目录不得覆盖。reachable scan 保存 `GetReachablePositions` 的规范整数格键，seal 时从私有起点重算 N+1 名义姿态并逐个检查可达；public evidence 为选定 survey 观察保存 RGB/depth/calibration 摘要、非零 place descriptor、公开 room/corridor/unknown 角色和匿名 `region:*` 实体区域引用；scenario receipt 对 P01–P08 分别重算 Z形、精确逆行、替代回环、top-1视觉别名、同地反向、T分支、8字双环及房间—走廊—房间条件。白话：route plan 说“怎么走”，scan 证明“计划步都落在可达格”，公开 evidence 证明“路线为什么从画面上被选中”，scenario receipt 证明“它确实是哪一种挑战”。它不包含模型地点答案，也不能用布尔自报或假摘要替代内容。

以下D-212规则仅描述被D-214取代的工程survey收据，不再允许直接获得路线资格：P04 曾从名义间隔至少 1.5 m 的 pair 中用四象限工程descriptor取top-1；P08 曾要求两个room-like anchor各有匿名`region:*`且中间登记为corridor。D-214生效后，P04必须改用冻结DINO place descriptor重验，P08必须改用basin→bottleneck→basin和多视角稳定fragment重验；旧字段只可追溯，不能冒充完整L2前端输出或headline资格。

本轮旧survey不保存instance mask/object ID，也不把`instance_masks`属性传给纯构造器；四象限小描述子和匿名区域现在只作历史工程诊断。P08的room-like/corridor-like来自公开reachable-grid局部开阔度，D-214明确禁止它继续充当资格条件；未经新cache复核不得给该槽`headline_eligible=true`。

`seal-routes` 生成：

- `public/manifest.json`：12 个 opaque episode、scenario、route/action/frame/keyframe计数，无 house ID或起点；
- `private/manifest.json`：episode 到固定 source house 的绑定；
- `provenance/routes/slot_00.json`～`slot_11.json`：完整逐动作 route；
- `provenance/route-evidence/slot_XX.json`：执行前公开 RGB-D 路线证据；
- `private/reachable-scans/slot_XX.json` 与 `private/scenario-receipts/slot_XX.json`：可达格及场景语义收据；
- `private/route-bindings.json`：12 个起点及 route-evidence 摘要；
- `private/route-evidence-index.json` 与 `route-seal.receipt.json`：逐槽证据文件摘要、`simulator_started=false/episodes_generated=0`。

`run-smoke` 只能读取 slot 0/P01，并把同一次 event 拆成三种不可互读的文件面。`public/raw/frame_NNNN/{rgb.npy,depth_m.npy,sensor-calibration.json,frame.json}` 保存 RGB-D、垂直FOV和由图像高度计算的 `fx=fy`，不含世界pose或identity。`provenance/action-journal/attempt_NNNN.json` 在每次动作后立即落盘完整公开请求、success、错误摘要、attempt ordinal 和 monotonic timestamp，最终 `action-receipts.json` 只是聚合索引。`private/raw/frame_NNNN/` 立即写 `simulator-pose.json`、`instance-masks.npz`、`entity-state.json` 和绑定三者与 public frame 的 `frame.json`；stable private entity ID 由 source record digest 与 simulator object ID 单向摘要得到，mapping 和原 simulator ID 只留 private。实体状态含 position/rotation、visible、interactable、pickupable/moveable、picked-up/moving 及 parent/receptacle 私有关系。白话：公开面供模型看，provenance回答“怎么走”，private回答“实际在哪、画面里是哪一个实体以及关系怎样”；private 同批采集不等于模型可读，也不等于已经运行 teacher/evaluator。

成功条件仍为 N 动作、N+1 公开观察、N+1 private pose 和 N+1 private scene frame；动作 k 失败时保留此前成功前缀和失败动作 journal，不写失败动作后的观察，不继续、不换路线。硬进程死亡可能来不及写 terminal aggregate，但已经 fsync 的逐动作/逐帧 journal 仍是可审现场，不得静默覆盖后重跑。

当前 v2 overlay 的 `expected_reviewed_implementation_commit=null`，所以实际 `seal-routes`/`run-smoke` 仍先拒绝。待实现提交经用户审查后，只做一个单文件 activation commit：写入受审实现 parent hash 并切换 executable 状态；运行入口要求 clean `HEAD`、`HEAD^` 等于受审实现且两提交间只改 v2 合同。该两提交门替代不可实现的“提交内容包含自身 hash”。

## 当前：VSMT 新数据边界（D-122/D-123，VM-01代码候选，尚未生成）

新版数据解决旧合成 query 由参考事务参数派生、无法支撑无泄漏视觉实验的问题。输入源拟为受控具身 RGB-D 序列、公开相机/机器人位姿和已发生动作；输出分成不可互读的 `public`、`candidate`、`teacher`、`private_eval` 与 `provenance` 五类产物。例如一次 MERGE 样本的 `public` 只保存两个当前区域的 RGB-D/匿名特征及 prior memory，`candidate` 由这些公开值枚举可能 pair，真实 pair 只在 `private_eval`。它不复用旧 S5 query/data，也不把人工事务夹具当作视觉或物理结果。

旧 C00–C11 不迁移为新版样本：其 `case_family`、语义化 node/evidence/`latent_refs`、人工 `oracle_equivalence` 和预写候选仍保留在原目录，只供 `L0 symbolic regression`。新 `L1 oracle_structured` 与 `L2 shared RGB-D` 必须从同一批重新生成的序列形成，二者只在 proposal 来源上不同；场景、时间切分、旧记忆构建和 private 标签相同。白话：这解决“用旧符号样本冒充视觉实验”以及“oracle 与 RGB 条件换了数据”的问题。输入同一真实或模拟序列，输出一份真值 proposal 诊断视图和一份冻结视觉前端主视图；例如同一个椅子分裂事件在 L1 用私有 mask 只查机制上限，L2 用公共 proposal 进入主表。它不允许把 L1 的候选或旧记忆缓存给 L2。

### 五类产物与读取权限

| 通道 | 当前合同内容 | 禁止与用途 |
|---|---|---|
| `public` | 截至决策时刻的 RGB-D、时间、相机/机器人位姿、已执行动作、冻结 proposal/descriptor 结果、公开传感器状态，以及从更早 public 顺序构建的 prior memory 摘要 | 所有方法唯一在线输入；禁止未来帧、真实未来运动、场景答案名、reference、instance ID、真值 mask |
| `candidate` | 由 `public + prior predicted memory` 生成的规范事务程序、静态 preflight、顺序、catalog digest 和来源字段 digest | teacher 打开前封存；禁止因正确候选缺失而补槽或重排 |
| `teacher` | 固定候选上的训练后验/排序、六项能量或新版登记能量、teacher 版本与 candidate digest | 仅训练标签；validation 只用于登记选择，confirmation/test 推理不可读 |
| `private_eval` | 参考结构版本、事务等价集合、模拟器 instance/关系真值、未来观测、实际未来状态及错误归因 | 只由独立评价器打开；不得构造 query、proposal、candidate 或模型输入 |
| `provenance` | 原始文件摘要、生成器/前端/模型版本、seed、split group、失败与退出回执 | 用于复现和审计；路径、seed、split 编号不进入模型值 |

白话：`candidate` 封存解决 teacher 先知道答案再帮模型准备选项的问题。输入是尚未打开任何私有文件的公开记录，输出一份带摘要的候选清单；例如只找到一个合理 MERGE pair 就只记录这一个，正确 pair 缺失时后面记 candidate miss。它不保证候选覆盖率为 100%，也不允许 teacher 在训练时补齐。

### `ObservationPacket` 与 `MemoryUpdateResult`

`ObservationPacket` 是共同在线输入包，VM-01 packet v3精确字段为：`schema_version, sample_id_hash, decision_time_s, rgbd_refs, camera_pose, robot_state, past_actions, region_observations, free_space_observations, visibility_observations, relation_observations, prior_memory_ref, public_constants`。`sample_id_hash`、`rgbd_refs` 和 `prior_memory_ref` 只作外层对齐/摘要绑定，`build_adapter_input` 会删除它们；适配器实际得到决策时间、相机位姿、机器人状态、已结束动作、匿名区域、传感器派生自由空间、匿名可见体积、匿名关系、已校验 prior memory 和公共常数。`region_observations` 当前含包内顺序号、匿名 `structure_kind`、mask 摘要、descriptor、质心、包围尺寸、可靠性和冻结 proposal 来源，不含永久身份或原图路径。`free_space_observations` 是由公开深度射线保守内包得到的六半空间截锥，含包内顺序号、合法历史 `time_s`、六个世界半空间、可靠性和支持摘要；至少两个不同历史时刻的覆盖证据才能组成 executor 可接受的 RETRACT/REPLACE 负证据链。`visibility_observations`同样只保存节点无关的六半空间体积，并把远平面限制在公开深度表面，遮挡后的空间不算观测机会；共享函数必须再与各方法自己的记忆包络相交。例如旧节点包络在连续两帧都完整落入高可靠自由空间时，ELU 才得到负观测候选；相机虽朝向柜后杯子，但深度远平面先撞到柜门时不累计杯子的错失机会。它们不是真值空区或逐节点可见性答案、不提供被删对象 ID，具体深度到截锥的数值规则仍须 VM-04 前冻结。

L1第一道隔离缓存`vsmt-l1-anonymous-mask-cache-v1`保存图像高宽、按内容排序的匿名区域和匿名拒绝记录。区域含包内`region_id`、固定`entity`结构类型、mask摘要、行优先0/1像素、可见像素数和是否触边；实体最少196个像素，触边区域满足该支持数就保留。拒绝项只含mask摘要、支持数、触边标志和固定原因。输入instance ID既不进入公开字段，也不参与公开排序或缓存摘要，只形成访问受限的映射摘要。例如把模拟器ID从`Cup|7`换成`opaque-b`而mask不变，公开缓存必须逐字节相同，私有映射摘要应改变。它还不是`ObservationPacket`：DINO描述、公开几何和可靠性完成并通过阈值后才能组包。

L1实体描述缓存把匿名mask投到16×16个DINOv2 ViT-S/14 patch token，每块权重为196个像素中落入mask的比例，总权重至少1.0；加权均值L2归一化后以384维float32保存，单位范数容差`1e-5`。公开几何缓存只接同帧米制轴向depth、`fx/fy/cx/cy`和camera-to-world的`position_m/quaternion_xyzw`，深度有效范围0.05–20 m，有效点门为`max(32, ceil(25%×visible_pixel_count))`，可靠性为有效点比例。输出只含可见点质心、可见轴对齐extent、支持计数和摘要。例如196像素中98个深度有效时通过且可靠性0.5；它不保存DINO的CLS token、不把深度当欧氏射线长度，也不包含真值姿态、mesh、完整bbox或instance ID。

正式多worker回执必须保存请求/实际worker数、容量探测、每个worker的确定性任务清单与seed、开始/退出、产物摘要、未启动/缺退出项及规范合并摘要。生成worker的最小不可拆单位是完整house family；validation公开预测按episode或family分片，但private evaluator只能在全部公开预测封存后运行。当前单GPU训练保持一个learner并至少两个数据worker，不能把多个进程争抢同一GPU包装成更充分训练。例如某worker处理family 03失败时保留其他已完成family并停止新派发，不由family 04顶替。它不改变split、样本权重或统计独立单位；精确worker数仍须运行前容量核验。

`causal_prior_receipt`（因果旧记忆回执，planned）解决 prior memory 虽然字段合法、其值却可能由 simulator instance ID 或 reference transaction 预先构造的问题。输入只读 public 序列、初始空图或公开初始化和冻结更新器版本，输出每步输入摘要、提交事务摘要、图版本链及最终图摘要；构建进程不得挂载 `teacher/private_eval`。例如把私有椅子 ID 从 7 改成 19 而 public 字节不变时，最终 prior memory 必须逐字节不变。它不等于把私有 ID 哈希后就成为公开值，也不允许用 reference graph 初始化历史。

VM-01 当前代码已拒绝旧式语义 `latent_refs`：可部署旧记忆的该字段只能为空或形如 `latent:<16–64位十六进制摘要>`，并有测试禁止 `src/vsmt/` 导入旧 `cpmt.m1_*` query/feature 模块。这是必要的静态门，不是充分的因果证明；VM-04 生成器仍须实现上面的无私有挂载回执与 private mutation 检查。

`CausalPriorReceipt`（因果旧记忆回执）代码候选的字段为：builder身份/版本/源码摘要、显式配置摘要、初始图摘要、按时间排列的公开包摘要、实际适配输入摘要、每步提交更新摘要、完整版本链、最终旧图摘要、包数和回执摘要。它解决 prior memory 是否可能由答案预填的问题；输入按时间排列且 `prior_memory_ref` 连续匹配的公开包，输出可逐步复算的封存链。例如第0帧BIRTH、第1帧公开相似度过门后BIND，链中会有初始图及两个后图摘要。它不保存private真值、不证明阈值正确，也不把包/文件摘要交给模型；schema见 `schemas/vsmt_causal_prior_receipt.schema.json`，当前只完成本地AST/JSON静态检查。

VM-04清单拆成三层：`FamilySplitManifest`保存audit/train/validation的实际ProcTHOR house ID，但confirmation行只保存承诺摘要及空ID；真实confirmation ID只能由另一个同时检查confirmation授权的reveal接口恢复。`PublicEpisodePlan`只保存与事务标签无关的opaque episode ID、family、split、槽位、32帧数和决策索引；`PrivateEpisodePlan`才保存episode到九种程序及重复号的映射和私有assignment salt。它解决确认家族提前暴露以及训练文件名/槽号泄漏事务类别；输入合格house列表和协议，输出互相摘要绑定但读取权限分离的清单。例如换salt后公开18个episode槽完全不变，私有九程序各2次的排列会变。它不隐藏开发split本身，也不代替后续只用元数据的nuisance probe；confirmation真实ID和episode计划在授权前均不可创建，schema见 `schemas/vsmt_vm04_manifests.schema.json`。

白话：新增自由空间证据解决“没检测到”无法区分遮挡与可靠为空的问题。输入只能是当前公开 RGB-D 和相机标定，输出不指向任何旧节点的匿名自由盒；例如桌面前方射线直到墙面之间的一块空间可标 `free:0000`。它不等于模拟器碰撞几何、真值 mask 或“对象已消失”标签；每个适配器仍需用相同公开几何自行判断旧节点是否被覆盖。共同适配器因此看到八类部署值，TAF、ELU、WFR、LOW 与 VSMT 完全一致。

`MemoryUpdateResult` 是共同预测输出，VM-01 精确字段为：`schema_version, method_id, pre_memory_sha256, post_memory, post_memory_sha256, normalized_delta, confidence, runtime_ms, diagnostics`。`normalized_delta` 只记录声明模板以及创建/关闭的节点版本和边版本 ID；当前验证结构合法和摘要绑定，不判定它在语义上应叫 BIND 还是 BIRTH。它解决直接改图方法与事务选择方法难以同一评价的问题；输入任一方法的内部更新结果，输出规范化的新记忆和变化记录；例如 LOW 覆盖旧节点属性可在后续适配规范中映射为 BIND-like delta。它不声称原论文使用了本项目事务术语，也不把结构合法等同语义正确。

VM-02 的共同节点观测状态键为 `vsmt_observation_state`，当前包含 `descriptor, centroid_m, extent_m, reliability, last_seen_s, observation_count`；ELU 可另存 `existence_log_odds`，WFR 可另存 `fragment_observations, absent_reconciliations`。它解决各适配器如何从同一图读取自己的最小状态；输入匿名区域观测，输出只依赖公开前缀的当前节点统计。例如 TAF 对 descriptor/centroid 做按既有观测数与当前可靠性的确定性融合。它不含永久真值身份、reference 标签或未来，并不把 ELU/WFR 私有字段提供给其他方法作为额外特征；正式初始化及字段迁移仍须随 VM-04 数据合同冻结。

`CandidateCatalog v2`（候选目录v2）解决teacher是否改过选择空间，以及容量到底截掉了什么。输入只能是已验证`ObservationPacket + prior_memory`、公开来源指针、候选程序及程序引用的`online_evidence`，输出带逐程序/证据摘要、`enumeration`、`capacity_audit`和顶层`capacity_summary`的包内匿名顺序`candidate:0000...`。`enumeration`保存`bucket_id`、枚举优先级和公开分量；容量桶保存template、结构类型或关系类型、容量、截断前候选/整组数、保留数、超大整组数、歧义边/总incident-edge护栏拒绝数及最低保留优先级，顶层汇总全部桶总容量和总截断量。例如SPLIT同一左右后继的三种关系分配必须整组保留或整组拒绝，不能按hash只留一个。它不接收private参数、不保存PHR决策分，也不证明某个候选正确。`TeacherTargets`（教师目标）输入已封存目录和等长分数/概率，输出按完全相同ID与顺序绑定的标签；正确MERGE漏掉时不能新增槽或替换证据。

`PrivateEvaluation`（私有评价记录）由独立入口加载，当前只绑定参考记忆、候选事务等价组、未来观测摘要、模拟器身份映射和语义案例 ID；实际未来数组的数值字段留到 VM-04 前另行冻结。它解决答案文件怎样与公开样本对齐而不进入模型的问题；例如交换两个模拟器实例名会改变 `private_sha256`，但不得改变公开包或候选。它不构造 proposal/query/candidate，也不是当前已经生成的数据。

### 新生成内容与结构范围

新数据至少需要八个原子模板的可执行正例及容易混淆的合法反例，并包含对象之外的结构变化：地点/区域 BIRTH、实体—地点 RELINK、关系 RETRACT、观测碎片 SPLIT/MERGE 和 dormant 结构 REACTIVATE。物理世界变化、感知片段错误与记忆初始错误必须分别标源；例如同一把椅子真实移动导致 RELINK，与两次检测形成重复节点后需要 MERGE，不能共用一个含糊标签。具体场景数、每类比例、轨迹、图类型和随机预算尚未冻结。

正式视觉输入计划共享一个冻结、与结果无关的 proposal/descriptor 前端。DINOv2 只从 `public.rgb` 产生区域描述；深度和位姿产生公开几何。VSMT、TAF、ELU、WFR、LOW 必须消费同一前端字节和缓存摘要，不能让 VSMT 用 RGB-D 而对照用旧 LATENT，也不能让对照读取更干净的真值结构。L1允许隔离materializer用模拟器instance segmentation提出匿名mask，但这只消除实体proposal误差，结果必须标 `oracle_structured_diagnostic_only`且不得进入主表；L2仍禁止instance segmentation作为正式proposal。

### VM-04 新数据协议 v1（D-127，proposed、不可执行）

[唯一数值提案](../configs/vsmt/vm04_data_protocol_proposal_v1.json)先把“什么是一条样本、L1/L2怎样同源、八原子怎样产生、什么仍未决定”写成机器可查合同。它解决讨论停留在“以后重生成数据”而无法审查的问题；输入拟固定的 ProcTHOR 房屋、AI2-THOR RGB-D 回放和公开前端，输出 32 个顺序观测、一个登记决策、七个仅供 teacher/private 评价的后续观测及完整来源回执。例如第 0–15 帧建立旧记忆，第 16–23 帧发生遮挡或环境变化，第 24 帧只凭公开前缀提出并选择事务，第 25–31 帧才由封存后的 teacher 判断候选后状态。它不是已经批准的数据配置，也没有授权下载、生成、训练或 confirmation。

首选来源是 ProcTHOR-10K＋AI2-THOR：前者提供程序生成房屋，后者提供可交互场景、相机动作及 RGB/可选 depth/instance segmentation 接口。只读预检已核AI2-THOR 5.0.0 tag、ProcTHOR代码/数据tag及PyPI发布存在，但wheel/source精确安装摘要、house manifest、许可证快照和服务器headless运行仍未固定，因此入口继续拒绝执行。实例 mask 和 simulator object ID 只给 L1隔离materializer/private；L2 不能挂载它们。相机在观测 0 之前可用 `TeleportFull` 做初始放置，之后每个 packet 对应一个已成功的登记 agent action；机器人实际执行过的操作进入 `past_actions`，外界搬动物体只留 private provenance。它不把实际未来运动或物体变换伪装成动作输入。

统计独立单位已固定为`house_family`，不能随机拆帧，也不能把同family的两个episode重复当成两个独立样本。总体主确认主张先在family内聚合九类程序的配对差，再跨family比较；分类型确认性主张只预登记SPLIT、MERGE、RETRACT，其余NOOP/BIND/BIRTH/REACTIVATE/RELINK/REPLACE只作描述性报告。confirmation family数不再把当前12当成已冻结答案，而由开发数据的逐类型构造成品率反推并在打开confirmation前锁死；2-house audit只查工程容量，不作功效估计。白话：某一house里两个SPLIT重复都成功，只增加该family内估计稳定性，不把统计n从1变2；输入开发成品率和预登记主张，输出冻结的confirmation family预算。例如SPLIT每family只有一半能构造时，不能仍拿12个family并把失败样本从分母删掉。它不允许看confirmation结果后加family，也不要求九个类型都各自显著。

当前数值清单中的2个audit、48个train、12个validation、12个confirmation仍是待重算提案：按源manifest＋固定seed＋house ID的SHA-256顺序选取；每家族对八个原子与REPLACE各做2个预登记重复，即18条episode。若暂按该提案，总量为74家族、1,332条episode、42,624帧，confirmation的216条episode继续延后生成。失败family/episode记录失败且不按结果换样本。它不保证这些数量足以支持上述分类型主张，最终confirmation family数须按D-141规则更新后再冻结。

D-144新增的[2-house audit机器提案](../configs/vsmt/vm04_l1_two_house_audit_proposal_v1.json)不修改上述正式split提案，只定义独立开发审计字段。来源层须先保存ProcTHOR-10K `0.1.2`作者train分区清单摘要、许可证快照摘要、机械合格ID列表摘要和哈希选出的两个实际audit house ID；这些字段在D-151已冻结。公开计划固定2 family×18 slot、共36 episode/1,152帧，私有事务salt只保存承诺摘要；任一来源解析、加载或episode构造失败都占原slot且不替换。白话：输入完整未筛效果的来源清单，输出可复算的两house承诺；例如某house启动失败仍留在manifest。它不是先看可用正例再选house，也不生成confirmation身份。

D-153的生成器初始视点只在每个固定house开始时搜索一次：`GetReachablePositions`给出当前场景可达相机坐标，生成器扫描四个水平朝向，以匿名mask合格数量、总像素支持和位姿字典序确定唯一位姿，再让该family全部slot复用。输入不含对象类别、instance ID排序、reference事务、未来或构造结果；输出位姿随公开相机文件封存，私有ID仍只用于既定干预和crosswalk。例如重命名全部instance ID而mask像素不变，所选位姿必须不变。它不是按每种事务分别找最容易成功的镜头，也不允许失败后换house。

D-160的[独立v2审计合同](../configs/vsmt/vm04_l1_two_house_audit_proposal_v2.json)为planned、generation关闭；原D-153/v1只解释旧stage。v2仍在每family扫描一次，但先与同帧`metadata.objects`求交，只数物理对象mask，再按合格mask数、像素和位姿排出全部候选；slot `k`取第`k`项并写`initial_viewpoint.receipt.json`，有序表写family级`initial_viewpoints.json`。初始门仍是至少2个各196像素的物理对象mask，额外质量门和目标集合互异均待裁决。例如两个pose各见同一两只物体仍是两个独立pose；若第18项不存在，固定第18 slot失败。它不保证干预可执行、目标集合不同或高排名以外的视角质量，且不允许按程序/未来/失败回执改排序。`intervention-capability-audit.json`与异常时`intervention-attempts.json`仅在private目录，公开raw回执只保存摘要；输入是实际干预动作事件，输出是保留`lastActionSuccess/errorMessage/errorCode`的可核对失败证据，例如DisableObject返回错误码时无需重跑即可审查。它不把私有object ID交给方法进程，也不是事务语义结果。

D-161修订上述v2 slot分配为planned空间去重：完整有序候选仍封存在`initial_viewpoints.json`，但每个可达位置只保留最高排名yaw，然后顺序选与所有已选pose三维距离至少`D=1.0 m`的最多18项；该D是待用户冻结的预登记提案。文件新增`selected_pose_rank_indices`，slot `k`领取第`k`个入选项而非原始排序第`k`项，并记录原前18与去重前18的独立位置数、坐标包围盒、物理mask数量/像素的最小最大值。白话：输入公开合格视角排序和固定距离，输出分散的视角索引及可见支持摘要，例如排名第1、2项是同位置不同yaw，后者被跳过。它不等于跨视角目标已去重、入选视角质量相等或贪心一定找到18个可行位置；无第18项仍占原slot失败。

预生成`viewpoint-scan`只让两个固定family worker执行该视角扫描，0帧episode、0干预；公开family文件不含object ID，`execution/<family>/private/viewpoint-target-audit.json`才保存原前18和空间去重前18的top-2真实目标ID。总`scan.receipt.json`分别输出top-1和top-2重复次数、包围盒、mask支持及两个worker的退出/摘要；top-1对应大多数单目标程序，top-2只对应需要两个目标的程序，扫描不读取程序分配来改视角。`viewpoint-scan-export`产生可回传的`results/vsmt_vm04_viewpoint_scan_v1.json`并核对来源摘要。白话：输入已封存的source house、episode计划和v2规则，输出能先判断位置是否扎堆及目标重复率的审计报告，例如公开报告显示去重后18个位置的top-1重复8次，原始ID仍只在private文件。它不是生成36个episode、不根据结果替换house，也不自动决定是否开放完整生成；未来`generate`先核验扫描receipt、同一规则与worker代码字节。

D-162已把上述`D=1.0 m`从planned数值冻结为本次纯扫描规则：v2 `status=frozen_executable`只表示已审扫描可执行，`viewpoint_scan_authorized=true`，而`generation_authorized/private_audit_authorized/training_authorized/validation_effect_authorized/confirmation_authorized`均为false。目标集合互异和额外质量底线显式为false，不能拿private top-2结果筛掉house或调间距。白话：输入还是原两间固定house与公开mask几何，输出仅为带摘要的视角报告；例如筛选后某family只得到15个pose，就照实报告15，剩余3个slot不会在扫描时被补样。这不是完成数据生成或证明18个目标已经分散。

D-164动作能力探针字段（proposed、代码待审、执行关闭）：独立[提案配置](../configs/vsmt/vm04_action_capability_probe_proposal_v1.json)只绑定现有扫描报告/receipt、两house、1 m和原program plan，不给v2 `generation_authorized`开闸。`execution/<family>/private/slot_XX.json`每个固定slot保存`scan_target_instance_ids/live_target_instance_ids`、程序、重复号、真实元数据能力、`frame_index/arguments/diagnostic`逐动作记录、注册agent动作数量、终态目标元数据及失败类别；`private/worker.receipt.json`逐slot保存private文件摘要，worker日志也在private下。公开`check.receipt.json`先保存三个独立测试worker（共九项）的requested/actual、固定合并顺序、各组退出与日志SHA-256；`probe.receipt.json`只存check摘要、两个private worker回执SHA-256、扫描摘要、requested/actual worker与退出/资源证据；导出`results/vsmt_vm04_action_capability_probe_v1.json`按family/program/status计数，不给slot程序对应关系、instance ID、动作参数或模拟器错误文字。白话：这些字段解决“DisableObject失败却只留一个笼统异常”的证据缺口；输入是固定pose的真实对象和AI2-THOR动作事件，输出私有逐动作诊断与公开汇总，例如私有文件写出RELINK对象没有`position`，公开报告只加一次`missing_action_precondition`。它不成为`ObservationPacket`或在线候选输入，不保存RGB-D episode、teacher或训练标签；动作成功也不证明记忆事务语义正确。

D-154在加载后、创建Controller前对冻结source record做内存schema兼容：源`metadata.schema=0.0.1`按官方ProcTHOR `53d5bd4…`升级语义转换material、门窗洞口/asset位置、exterior wall和schema字段；门窗asset尺寸只读固定`procthor==0.0.1.dev2`安装包的`asset-database.json`。输出字典须确定且不能回写`train.jsonl.gz`；Controller初始事件失败或对象为空时不得继续当作可用场景。白话：输入同一原始房屋和固定asset表，输出模拟器5.0.0能识别的等价字段布局；它不改变房间、对象、材质选择或相机样本，也不从private结果修房。

D-155在house创建成功后先把agent放到升级后记录自带的`metadata.agent` pose，再查询可达位置；该pose只作查询bootstrap，不能绕过D-153的匿名几何最终选择。输入字段是position/rotation/horizon/standing，输出是一次成功的生成前TeleportFull和可达点集合。例如首房从旧场景坐标查询会越界，从登记pose查询返回1299点。它不进入32帧序列、不作为模型额外输入，也不按对象或事务调整。

D-148实现把这些字段落成三个互相摘要绑定但权限不同的文件层。`inventory`要求本地ProcTHOR-10K git checkout的HEAD精确等于登记release commit，只读该checkout内显式的author-train JSON/JSONL（含gzip）和license文件，输出公开manifest/eligible摘要及隔离的source locator；`select`必须在另一次命令中从该已封存manifest按seed `260914`计算两个house，并生成36个公开opaque slot和私有程序salt；`generate`才按family启动两个Python 3.9模拟器worker。输入是预先存在且版本正确的本地`train.jsonl.gz`、许可证和冻结配置，输出可复算的house IDs、公开计划与私有计划。例如即使JSON行没有显式house ID，也按冻结文件顺序赋稳定`train:000123`，随后选择仍只依赖manifest、seed和该ID。它不下载来源、不接受checkout外license、不在inventory时选择house，也不让公开计划出现程序名或source house ID。

原始生成每个frame先执行按replicate反相的预登记±0.25°左右旋转，再把RGB/depth/camera及累计`past_actions`写入`public`，把instance masks、simulator object状态和外界干预记录写入`private`；因此每个packet都跟在一个成功且已登记的agent action之后，物体的外界干预仍不会伪装成机器人动作。trusted L1 materializer临时同时读取二者后，只把匿名region/surface/place/relation/free-space/visibility写回公开目录，真实ID到匿名region的crosswalk继续单独留在私有目录。public replay只验证并打开公开episode plan、匿名frame、公开prior/catalog和无标签process顺序，不能打开private plan或crosswalk；其seal完成后private evaluator才可读取crosswalk并产生严格recall。白话：输入同一帧的公开图像和临时私有mask，输出一份方法可读的匿名packet及一份方法不可读的对照表；例如公开packet只看见`region:...`和已经完成的微小相机旋转，评价器稍后才知道它对应哪个模拟器对象。它不把oracle ID当作跨帧跟踪，也不把未来25–31帧送进第24帧候选生成。

两层产物继续分读权限：可信L1 materializer可临时读取当前帧instance mask但只能输出匿名packet和私有映射承诺；public capacity进程只挂载匿名packet与三组审计profile，输出各尺度free-space/visibility存活、原关联分量、逐桶pre-cap/retained/truncated/cutoff/unused、护栏拒绝、RELINK端点对次数及资源峰值；public seal后独立private evaluator才输出逐slot construction yield、严格canonical reference recall和D-143 entity RETRACT合法candidate recall。BIND/BIRTH、REACTIVATE/BIRTH、RELINK/REPLACE及SPLIT/MERGE的等价类recall保持`null`，因为这些语义边界尚未裁决。它不读取teacher打分、不运行五方法预测，也不把严格reference miss自动解释为方法失败。

同一物理序列形成两个完全隔离的 proposal 视图：L1 把真值 instance mask 去除真实 ID 后生成匿名区域，用来查机制上限；L2 拟用逐帧、无视频记忆的 SAM 2.1 Hiera-S 自动 mask，再用冻结 DINOv2 ViT-S/14 无 register 的 patch token 做区域池化。DINOv2沿用已核官方 commit `7764ea0f912e53c92e82eb78a2a1631e92725fc8`及权重 SHA-256 `b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9`，但旧回执只证明资产来源，不认证 VM-04 前端。SAM commit/checkpoint、自动 mask 参数以及 depth→surface/place/free-space 的全部门限仍为空并阻止运行。白话：逐帧 SAM 只把当前图像切成匿名区域，输入单张公开 RGB，输出 masks；不用其视频 memory 是为了避免共享前端先替 WFR/VSMT 做长期关联。它不输出永久身份，也不等于 SAM 的 region 就是真实对象。

八原子和 REPLACE 的数据来源分开登记，防止把物理变化、观察变化和旧记忆错误混成一个标签：

| 程序 | 拟议可观察构造与边界 | 不等于什么 |
|---|---|---|
| NOOP | 无受支持的持久变化，或遮挡/低可靠使证据不足 | 不是把难例删出分母 |
| BIND | 同一 entity、surface 或 place 的公开重观测 | 不是 descriptor 过阈就自动拥有真值身份 |
| BIRTH | 首次公开揭示的新 entity 或可持续 place | 不只限对象，也不是每个 mask 都建点 |
| REACTIVATE | dormant 结构再次出现，且旧址没有可同时存在的可靠证据 | 不是所有“消失后出现”都复用旧 ID |
| RELINK | 同一结构的 `located_at/supported_by` 等关系发生变化 | 不是把另一实体替换旧实体 |
| RETRACT | 两个不同历史时刻的公开可靠自由空间覆盖旧实体或旧关系 | 不是一次漏检就删除 |
| SPLIT | public-only 前端在旧前缀把相邻/重叠区域欠分成一个记忆节点，当前恢复为两个区域 | 不是现实物体裂开，也不由真值指定欠分 pair |
| MERGE | public-only 关联在旧前缀按预登记时间窗断开而形成重复节点，当前公开证据支持同一结构 | 不是现实物体融合，也不允许 `merge_queries` 给答案 pair |
| REPLACE | 旧结构可靠为空，同时当前出现身份冲突的新结构；执行为 RETRACT+BIRTH | 不是第九个原子 |

`controlled_frontend_stress`（受控前端压力事件）专门产生可复验的 SPLIT/MERGE 旧记忆错误。输入只能是已经公开的 proposals、固定时间窗和公开几何，输出所有方法在同一 evidence level 内共同看到的欠分或关联断开。例如固定前缀内把两个公开相邻 mask 合成一条 proposal，之后恢复原 proposal，可能形成 SPLIT 需求。私有真值只能在 public/candidate 封存后把它判作“目标成立”或“construction_failure”，不能反向挑 pair、改候选或重采样。它不冒充自然检测错误；自然错误须另列结果。

SPLIT关系语义已按D-140/D-141批准：原子事务关闭源节点及全部开放incident edges，再逐边按当前公开支持收窄为左、右或二者；没有公开支持的歧义边才保留这三种合法分配，所以组合数为`3^(歧义边数)`。同一后继pair的组合整组保留或整组拒绝；歧义边数上限与总incident-edge操作上限分别审计并在开发阶段冻结。“均不继承”只有达到另行冻结的公开关系负证据时才可生成。白话：旧节点有两条边，其中`located_at`公开唯一支持两个后继、`supported_by`当前没有证据时，只需枚举后者的三种分配；输入旧边、两个匿名后继和当前公开关系，输出完整原子程序。它不增加第九个事务，不让hash或teacher决定被截掉的分支，也不把“最多2条边”当科学语义。

同一数据拟报告两条轨道。`controlled_revision`（受控单次修订）让五个方法在同一 L1 或 L2 内拿到逐字节相同、由 public-only bootstrap 顺序构建并封存的 prior memory，用来隔离修订机制；`closed_loop_revision`（闭环连续修订）让每个方法从空图开始提交自己的历史，用同一序列报告错误持续和恢复。前者输入共享旧记忆、输出一次可比更新，例如同一错误合并图交给 VSMT/TAF/ELU/WFR/LOW；后者输入相同观测流、输出各自版本链。前者不证明长期稳定，后者也不能因为各方法旧图不同而伪装成单步同条件比较。

主臂仍为 VSMT/TAF/ELU/WFR/LOW；VM-05还须有三项 VSMT 内部对照：同在线架构但不用执行后 teacher 的 direct reference ranker、看候选语法/旧图但不看候选执行后状态的 no-execution scorer、完全不学习的 public heuristic ranker。L1 oracle proposal 和 sealed-catalog oracle choice 只作上界。白话：这些内部对照解决“收益到底来自未来 teacher、真实执行后的候选状态，还是候选本身已经很好猜”；它们输入同一 catalog，输出候选排序。例如 no-execution scorer 若与 VSMT 同样好，不能把收益归因于执行后比较。它们不是新增论文机制主臂，也不能替代 LOW 朴素基线。

当前真正阻塞VM-04的不是服务器是否开启；L1匿名mask、DINO池化、实体/表面/地点/free-space及关系结构值已批准并有旧工程回执，类型化配置、place scaffold、候选分桶、SPLIT整组、MERGE关系规范化、entity RETRACT/REPLACE、共享dormant路径和共同更新后审计已获实现授权但须新服务器回执。D-142/D-143把packet再扩为公开匿名`visibility_observations`：它由depth、相机标定和pose生成节点无关且受遮挡深度限制的可见体积，不得含逐节点机会结果、node ID、instance ID、事务标签、teacher、future、reference或private；共享函数必须使用各方法自己的闭环记忆判断机会。没有机会不累计，可靠visible-empty仍单独进入RETRACT证据。仍未冻结的是public bootstrap及各方法正式关联数值、候选cap、历史包络可靠性门/裕度、错失机会次数/可靠性门、SPLIT与REPLACE组合护栏、teacher temperature、PHR公式、在线选择器容量、关系“均不继承”的公开负证据、S-01～S-12的数值/图等价细节和nuisance probe门；L2另有SAM资产与mask参数。统计独立单位、总体主张与SPLIT/MERGE/entity RETRACT分类型确认范围已冻结，relation RETRACT只作描述性次要报告；entity RETRACT开发审计必须在新包络规则下报告yield与candidate recall，confirmation family数须由开发成品率反推。2-house只读容量审计仍未获运行授权，train/validation、训练和confirmation继续fail closed；48/12开发划分、32帧、每程序2重复、16 GiB和8小时也仍是提案而非批准值。

### VM-04 L1-only 输入输出提案（D-132/D-133，proposed、不可执行）

[L1-only合同提案](../configs/vsmt/vm04_l1_contract_proposal_v1.json)解决五方法能否先在“实体区域已切对、身份仍未知”的条件下比较。隔离materializer输入当前帧RGB、公开depth/pose/calibration及私有instance masks/IDs，输出匿名mask缓存、冻结DINOv2描述、公开可见几何、`ObservationPacket`和来源回执；方法进程仍只收到既有`AdapterInput`。例如私有ID为`Mug|3`只可帮助取出本帧mask，公开排序前必须删除，输出只能是`region:0000`及mask摘要。它不返回mask数组、RGB路径、类别名或跨帧oracle ID给记忆方法，也不是L2部署输入。

| L1区域类型 | materializer可读来源 | 方法可见输出 | 明确禁止 |
|---|---|---|---|
| `entity` | 单帧instance mask＋当前RGB-D/pose | 匿名ordinal、mask摘要、384维DINO描述、可见点质心/extent、可靠性 | instance ID、类别名、真值姿态/mesh/bbox、跨帧链接 |
| `surface` | 公开depth/pose/calibration | 匿名几何区域及同字段 | simulator surface/room语义或碰撞mesh |
| `place` | 公开depth/pose/calibration | 0.5 m世界格及按坐标确定的共同scaffold版本，只作关系端点/几何锚 | house/room名称、私有导航图、reference地点、学习式BIND/MERGE/SPLIT |
| `fragment` | 预登记的匿名区域变换 | 匿名片段及变换摘要 | 按reference程序挑片段或用真实身份合并 |

白话：实体oracle mask只移除“检测器有没有把像素分对”的误差；输入仍是一帧可见像素，输出仍没有历史身份。例如同一杯子下一帧再次出现时会得到新的包内ordinal，TAF/ELU/WFR/VSMT必须自己依据描述、位置和旧记忆决定BIND还是BIRTH。它不允许把模拟器ID哈希后塞进descriptor，也不把完整物体几何补给方法。

place坐标身份的确定性以AI2-THOR提供的精确相机位姿为前提：五方法共享包装器把同一世界格的版本化观测证据逐字节相同地附着，并在S指标中与实体/关系分开计账。输入公开depth、精确pose和固定格原点，输出可复用坐标锚；例如两帧都覆盖格`(2,-1)`时只更新该格版本，不让选择器决定是否BIND。它不声称真实机器人存在SLAM漂移时地点身份仍然确定；首篇明确把SLAM不确定性排除在研究范围，研究对象限定为实体与关系修订。

VM-04的目标来源诊断新增仅供可信私有生成器使用的`author_asset_ids`：从冻结ProcTHOR源house的`objects`及递归`children`取ID，并与`walls/doors/windows/rooms`分开；再用当前`metadata.objects.position`核验真实有限位置，另列`moveable/pickupable`能力。输入私有房屋来源、当前私有mask ID与simulator metadata，输出私有`authored_asset`/`movable_asset`资格profile及公开匿名计数。例如墙在`metadata.objects`中有ID和position仍不属于作者物体；挂画属于作者物体但可能不可移动。它不进入公开packet/descriptor/候选，不把私有ID哈希成模型特征；D-166仅批准新目标资格语义的实现，尚未批准新生成worker或episode运行。旧v2 scan的72个top-2条目仅2个作者资产，不能把原`metadata.objects`交集解释成非建筑对象过滤；[根因审计](../results/vsmt_vm04_root_cause_audit_v1.json)、[同pose资格审计](../results/vsmt_vm04_target_visibility_audit_v1.json)和[匿名重复审计](../results/vsmt_vm04_target_repetition_audit_v1.json)各有来源/私有文件摘要链。服务器private profile保留36槽逐pose ID，三个公开报告只存匿名计数。

[v3目标边界合同](../configs/vsmt/vm04_target_boundary_proposal_v3.json)是D-166已批准语义、D-168仅固定两房目标能力探针获准的合同，字段白话含义如下：`status=frozen_target_probe_only`只表示已审目标资格可用于新目标探针，生成及训练仍关闭；`pose_source/private_asset_membership_may_affect_pose`规定仍用v2固定相机位姿且私有资产不得挑镜头；`physical_intervention_programs/trusted_private_target_boundary/private_target_rank`规定仅五个物理干预程序在私有侧以作者资产∩当前真实metadata position沿原匿名几何次序选目标；`minimum_qualified_visible_assets_for_replace/minimum_mask_pixels`为REPLACE至少2件/每件196像素；`asset_visibility_shortage_policy`记原slot失败，不回绕/换房；`target_repeat_policy`只计重复。四个已批准字段分别要求物理RELINK选可移动/可拾取资产、静态作者资产可见性生命周期以后必须核验动作/终态/记忆历史、非干预程序只读公开类型化区域证据、L1 oracle仅给匿名实体区域而建筑结构由公开证据生成；`source_public_episode_manifest_sha256/source_private_episode_manifest_sha256`登记原封存计划的有效64位摘要，不使用旧v1/v2配置的65位笔误。输入固定两house/扫描/来源和用户裁决，输出关闭式实现规则；例如墙+挂画+椅子同框时墙不进RELINK物理目标、却能以公开证据进入结构观察。它不是私有ID进入部署packet、不是静态生命周期已验收，也不是已开放新数据生成。

[v3私有物理干预目标纯函数](../src/vsmt/vm04_target_selection_v3.py)只消费五个发物理动作程序的`program/instance_masks/current_metadata_objects/authored_ids`及已验证的关闭式v3 `contract`，从合同读资格/程序/像素/REPLACE数量，输出1–2个待核验私有ID，资格不足抛异常占原slot；同几何mask并列亦明确失败，不按私有ID排先后。NOOP/BIND/SPLIT/MERGE调用它会被拒绝，不能靠物理资产门删掉合法结构观察。它并未写入任何公开packet、DINO descriptor或候选。输入mask ID属于可信模拟器/生成器过程，在线方法进程不得调用此函数。例如墙在原几何首位、挂画第二、可移动椅子第三，BIRTH可把挂画列为待核验的可见性干预目标，物理RELINK跳过挂画取椅子。它不是由公开视觉模型识别出的类、不核验静态生命周期动作/终态/记忆历史，也不是已接入生成worker。

D-170关闭式[v2动作探针合同](../configs/vsmt/vm04_target_action_probe_proposal_v2.json)新增`minimum_memory_headroom_to_sampled_cgroup_demand_ratio_for_two_workers=4.0`与`resource_benchmark_sample_interval_seconds=0.25`，并保持`probe_execution_authorized=false/expected_reviewed_probe_code=null`。未来私有`probe.receipt.json/resource_evidence`的`pre_benchmark_cgroup_memory_headroom_bytes/benchmark_min_cgroup_memory_headroom_bytes/post_benchmark_cgroup_memory_headroom_bytes`记录同cgroup读数；`benchmark_observed_cgroup_demand_bytes/benchmark_cgroup_sample_count/benchmark_cgroup_sample_window_seconds/benchmark_maximum_cgroup_sample_gap_seconds`记录采样需求及分辨率，`post_benchmark_resource_evidence`再登记派发前真实余量。输入只有服务器资源与零干预启动，不向`ObservationPacket`或public区域输入增添资源字段；原始采样序列将来单独保存在private/resource-benchmark.cgroup-samples.json并登记SHA-256，export会反算最低值、次数与最长采样间隔；输出将来只作为私有回执与匿名报告的资源证据。例如20 GiB启动、最低18 GiB，观测需求2 GiB，派发前8 GiB满足4倍门；未取到读数或需求为零拒绝派发。它不是已运行的v2 stage、Unity精确独立峰值、原v1资源安全追认或新episode授权。

D-171原失败RELINK槽的受控复现入口`ops/vsmt/vm04_relink_mechanism_probe.py`只读原v1 private/slot_12.json及其worker/父receipt摘要、旧v2扫描的原slot12 pose/top-2、冻结作者source house；三个新private/<mode>.json各保存同一目标真实ID、原请求、动作返回/错误、逐帧真实位置及请求/实际位姿的AABB相交对象，private/resource-samples.json登记并发前真实cgroup/GPU采样，所有产物由新mechanism.receipt.json登记摘要。独立export只生成`results/vsmt_vm04_relink_mechanism_probe_v1.json`的匿名三轴误差与AABB相交次数，`private_ids_exported=false`。例如请求x=1.5而实际x=1.45，public只报x误差−0.05 m，不给目标object ID、类别、世界位置或错误原文。它不把AABB相交当碰撞真值，不给ObservationPacket加私有字段，也不读记忆历史或签RELINK正例；当前仅代码/合同已写，真实复现结果须看EXECUTE回执。

D-172`vm04_relink_physics_step_probe_v1.json`只绑定D-171父receipt、匿名报告及原v1探针/扫描摘要，固定family01原slot12同一目标；两个private/replica_00/01.json分别保存暂停强制动作和50个`AdvancePhysicsStep(timeStep=0.01)`后的真实position/isMoving、动作返回及目标ID，父physics.receipt.json登记worker/日志/资源/轨迹摘要。独立public出口只导出首个偏移步、首末三轴差及匿名碰撞拒绝类别，不含原错误字符串、对象ID、世界坐标或记忆标签。例如第0步x偏差−0.049 m，公开报告只给差值，不能据此给模型一个跨帧真实身份。它不修改D-171旧stage/报告、不换失败槽，不给完整episode或物理可达路径验收；真实复本结果待EXECUTE。

[D-167新目标动作探针配置](../configs/vsmt/vm04_target_action_probe_proposal_v1.json)是实现可审、执行关闭的新合同，绑定v3文件SHA-256及v2 scan receipt/report、原两房36槽plan有效manifest摘要。`status=implementation_only_not_executable/probe_execution_authorized=false/expected_reviewed_probe_code=null`使父入口与worker都不能发模拟器干预；`target_source`规定先比对v2旧top-2与live旧top-2确认相同pose/场景，再由私有v3作者资产规则选新的物理目标；`relink_terminal_tolerance_m=0.005`只在探针里比较真实metadata终态和注册x+0.5 m位置，`relink_force_action_semantic_policy`明确碰撞/可达性未查；`static_lifecycle_memory_history_policy`明确探针不读取记忆历史、不签发事务正例。输入是冻结扫描/计划及将来隔离动作事件，输出尚待服务器执行的`execution/<family>/private/slot_XX.json`和摘要绑定的private worker/probe receipts，公开导出只保留family/program/status次数、作者资产目标匿名top-1/目标集合重复次数、requested/actual worker及退出/资源依据。例如REACTIVATE在frame16隐藏挂画时模拟器返回错误码，私有slot保留注册相机动作和此次干预的`arguments/diagnostic/target_poststate`，公开只加一条`intervention_rejected`；它不把object ID、action参数、错误文字或oracle mask放进部署packet，不生成RGB-D episode/teacher/训练标签。当前只有代码与本地纯测试，没有新私有slot或公开报告。

资源预检私有文件`private/resource-benchmark.json`只登记固定family00/slot00的场景创建与传送诊断、单worker峰值RSS、0干预和退出状态；父`probe.receipt.json`登记它的SHA-256、私有日志SHA-256、逐GPU启动/采样最低/结束空闲显存、观测峰值需求与两family派发前的4倍RSS/2倍显存安全核验。例如采样到GPU空闲显存从12 GiB降至8 GiB，需求按4 GiB估算，结束后须在同设备达到至少8 GiB空闲才允许派发。这份资源回执没有真实object ID，不证明动作或记忆标签；目前文件仅属未来输出计划，未在服务器生成。

每条未来private `slot_XX.json`的`actions`同时保存32个注册相机动作的诊断和`target_poststate`；已注册Disable但未注册Enable时若目标mask提前重现，写`disabled_target_reappeared_between_actions`，终态从frame31事件读取。例如隐藏挂画后frame0重现，private留下原槽相机事件的196像素mask支持，public只计一次状态，不导出真实ID或逐帧mask。当前这些仍是输出字段设计，没有生成文件。

D-168活动合同仅对固定两房动作探针开放：v3目标边界的`status=frozen_target_probe_only/target_capability_probe_authorized=true`及D-167探针的`status=frozen_probe_only/probe_execution_authorized=true`相互绑定；探针额外登记用户审过的实现commit `fe8b725b4b8617b7795ef916ec92d874c901233c`和活动v3文件SHA-256=`7d11335be9a8b85cc26dd1c2058c36f71c93d9db0cef4f33fdda2ec7cfa6dbac`。两份配置的`generation_authorized=false/training_authorized=false`未变。输入仍是原扫描/计划/house和真实当前动作事件，输出待运行的private逐槽动作诊断及只含匿名计数的公开探针报告。例如原槽干预失败保留动作错误码于private，公开只增加一次相应失败状态；它不等于新RGB-D episode或记忆正例，两房真实动作产物已按LOG-159封存，0新episode。

匿名区域规范顺序为`structure_kind → row-major首个真像素 → 可见像素数 → binary mask SHA-256`，之后才赋`region:0000...`；mask摘要只覆盖`[height,width,row-major 0/1值]`的canonical JSON。输入mask枚举顺序任意，输出顺序和字节必须相同。例如一把椅子在画面左缘仍有220像素时保留，只有150像素时按支持不足拒绝。它不按instance ID、对象类别、文件路径或reference排序，也不把触边可见部分补成完整物体。

DINO输入固定为224×224当前RGB；uint8除255后按均值`[0.485,0.456,0.406]`、标准差`[0.229,0.224,0.225]`归一化，不裁剪、不增强。ViT-S/14产生16×16×384 patch token；每个token权重等于对应14×14块中mask像素比例，按权重求均值并L2归一化为384维float32。区域总patch权重至少1.0，落盘float32向量的单位范数误差不超过`1e-5`，否则保留失败且不重采样。输入同一RGB和匿名mask，输出一次缓存、五方法逐字节共享的descriptor。例如半个patch权重0.5，单独不能通过。它不使用CLS/register token、不训练DINO，也没有方法私有视觉adapter。

实体几何用mask内0.05–20 m有效公开depth逐像素反投影到世界坐标，AI2-THOR深度按相机轴向`z`解释；质心为可见点逐坐标均值，extent为可见点逐轴最大减最小。有效点至少`max(32, ceil(25%×可见像素数))`，可靠性为有效点数除以可见像素数。输入公开depth、内参与camera pose，输出可见几何。例如杯子底部被桌沿挡住时，extent可以偏小并由可靠性反映，而不能读取真值bbox修正。它不等于对象完整尺寸。

D-138已批准把旧`free_space_observations`的`minimum_m/maximum_m`轴对齐盒替换为packet v2的6个世界半空间截锥，并新增必需的`relation_observations`。关系记录精确含包内`relation_id`、两个包内region ID、`relation`、`reliability`和公开支持摘要；端点类型固定为entity→place的`located_at`、place→entity的`contains`、entity→surface的`supported_by`及place→place的`adjacent_to`，只能从当前公开几何形成并在teacher前封存。`contains`与反向`located_at`共用支持摘要；消费端规范为一条持久`located_at`，不把同一事实算两次。place region还必须先由共同`place_scaffold`按世界格坐标建立/更新开放节点，随后五方法和VSMT候选只把它当关系端点；place之间的`adjacent_to`同样由该骨架按格坐标维护（含跨帧邻格），共享关系更新把这类观测记为`scaffold_maintained`而不建边，候选生成器也不为它开容量桶。它解决旧schema无法表达第一条关系及地砖候选淹没实体的问题；输入匿名region和公开几何，输出匿名关系证据与确定性地点锚。它不提供永久实体ID、参考边或正确事务；旧130项回执不认证这次新实现。

L1 materialization receipt（L1物化回执）分公开与私有两份：公开回执绑定materializer/config、RGB/depth/pose、匿名mask、descriptor、geometry、`ObservationPacket`及DINO源码/权重摘要；私有审计回执另存原instance mask集合、ID映射和公开回执摘要。输入同一次物化，输出两条不可互读的来源链；例如只置换instance ID时公开回执必须不变，私有映射摘要可以变化。它不把private摘要、路径、类别或future/reference摘要带入公开回执或方法输入。

VSMT选择器新增的计划产物为`online_candidate_features`和`candidate_logits`。前者逐候选绑定catalog、prior、候选触及的执行前子图、同一基图真实执行后的子图及normalized delta；后者由共享逐候选打分器输出一项有限标量。candidate ordinal、列表位置、路径和样本ID均禁止成为数值特征；并列拟按canonical program SHA-256处理。输入一个封存catalog，输出与每个program身份绑定的logit，例如候选换序后logit只随program移动。它不允许teacher改catalog，也不使TAF/ELU/WFR/LOW经过VSMT网络；网络宽度、层数、参数量和训练预算仍为`null`。

必需正反例在实现前固定为：

| 案例 | 输入改动 | 必须输出；它不等于什么 |
|---|---|---|
| L1-01 ID置换 | 只换全部simulator instance ID | 匿名区域、descriptor、geometry、prior、catalog、在线特征/logit逐字节相同；private mapping摘要可变，不要求private标签相同 |
| L1-02 跨帧重现 | 同一私有实例下一帧再见 | 新包内ordinal，由方法自己关联；不允许oracle直接BIND |
| L1-03 mask枚举换序 | 私有读取器交换实例返回顺序 | 规范公开顺序完全相同；不以输入数组位置代替身份 |
| L1-04 两相似实体 | 两把同类近似外观椅子同时可见 | 两匿名区域并保留歧义；不输出类别或正确pair |
| L1-05 遮挡 | 旧实体当前无mask但射线被遮挡 | 不生成可靠空证据/RETRACT；“没mask”不等于不存在 |
| L1-06 支持不足 | mask太小或有效depth不足 | 保存frontend/construction failure且不补样；不读真值bbox补齐 |
| L1-07 private/future变异 | public不变，只改reference/future | prior、catalog、顺序、在线特征及未训练logit不变；不要求teacher标签不变 |
| L1-08 候选batch换序 | catalog校验后只改变scorer的候选batch顺序，不修改封存catalog | logit跟program SHA、最终选择不变；不允许slot head，也不伪造可被teacher接受的重排catalog |

这些案例解决匿名化、输入因果性和逐候选打分是否真的成立；输入是人工小例或同public的私有变体，输出字节不变或明确失败。例如L1-05必须等两份公开自由空间覆盖才可提出RETRACT。它们不证明真实2-house序列能产生全部事务，也不代替后续效果实验。

### 强制泄漏检查字段

每个样本须保存但不向模型返回：`public_digest`、`candidate_digest`、`private_digest`、`candidate_generated_before_private_open`、`query_derivation_fields`、`instance_id_permutation_digest`、`private_mutation_invariance`、`prediction_without_private_access` 和 `nuisance_probe_group`。其中 `query_derivation_fields` 逐个列出 node/edge/place/pair query 所依赖的 public 字段摘要；出现 `reference_spec`、未来、真值 identity 或 private 路径即拒绝。

白话：private mutation invariance（私有改动不变性）解决“答案是否已经绕路写进公开输入”的问题。输入两份 public 完全相同但 reference、未来或模拟器 ID 被置换的审计副本，输出候选和在线特征是否逐字节相同。例如交换两个真值对象编号后 MERGE 候选顺序必须不变。它不要求最终评价标签相同，也不证明视觉信息本身没有合理线索。

### 划分与重新生成状态

旧 train/validation/test、旧 S5 arrays、旧 query 和旧 candidate catalog 均不得作为新版效果数据。可复用的是 executor、事务 schema、旧失败案例设计经验及 Git 中的历史结果。新 split 必须以物理/资产家族成组，train/validation/confirmation 不共享场景模板实例、材质身份或初始记忆错误实例；confirmation 在前端、候选、阈值、模型、预算和评分冻结后才生成。当前 `generation_authorized=false`、`training_authorized=false`、`confirmation_authorized=false`，等待具体数值合同和用户代码审查。

## 当前：空间历史四世界工程记录（D-062/D-070）

### SH-04-R2 四世界家族字段（已实现，服务器验证pending）

双门候选与判定含义见[METHOD](METHOD.md#sh04-r2-two-gate)。D-070已批准观察、控制、任务/工程判定及本批预算；D-071仅修复物理参考XML的跨平台字节摘要。新合同版本为`spatial-history-two-gate-public-v1`，旧`spatial-history-pair-v1`仍严格表示两世界、两候选。首个Linux运行在进入`history-LL`前发现摘要不符并停止，不以旧32项测试或SH-03回执认证；没有训练/确认划分。

白话：输入同一场景家族中四种门洞组合的真实记录，输出合法模型查询及独立的审计/监督通道。例如完整历史可以含两门的旧图，但模型拿不到“左左”标签、门洞真值坐标或执行后的轨迹；这不是把真实未来改名为latent或控制输入。

| 通道/字段职责 | 内容与用途 | 权限与待定项 |
|---|---|---|
| `history` | 全部真实RGB/有限非负深度、相机内外参、时间、机器人本体、已发生控制；本版无单独有效mask，0沿用旧帧合同的无效深度约定 | 主输入；64×64、0.1 s采样。模型按所比较的历史规则消费，不能共享含额外历史的缓存统计 |
| `controls / goal` | 四世界共用的数值速度—时长序列和共同目标定义 | 主输入；四条200段/20 s控制及目标已冻结；计划控制不等于执行后的机器人或物块运动 |
| `family_id / world_id / action_id` | 分组、去重和关联真实结果；左左等名称只供审查 | 私有元数据，不作为特征；同一物理家族的四世界、四动作及历史变体不得跨split |
| `frame_information[].equivalence_groups` | 按指定单视图＋共同近期的完整公开输入形成不可区分组 | 仅审计；保存按全部公开字段比较的分组及信息代价，不能向主模型提供答案分组 |
| `layout_truth / initial_state / snapshots` | 两门实际几何、完整决策初态、重放积分状态 | 仅审计及单列特权诊断；主地图必须由公共传感器形成 |
| `future_object_state / contacts / actual_robot_state` | 真执行物块位置/速度、接触对象/力/时间和实际机器人响应 | 物块/接触可作已登记训练监督及评估；实际机器人运动仅诊断，不能作计划控制替身 |
| `visibility / geometry_recovery_audit` | 每历史/未来采样及实际接触步的可见性；观测几何与真值之差 | 仅审计/定位错误；不得作为选帧标签、语义mask或模型特征 |
| `task_outcomes / costs` | 用户选定任务规则下从真实轨迹导出的到达结果与代价 | 只用于已登记监督/评估；不能按路线名称指定成功，不先假定通过矩阵 |
| `manifest / receipts / failures` | 全部首次分支及新实例重放、来源摘要、退出证据和完整失败 | 私有来源审计；无结果明确未运行，不自动补样或覆写 |

首个四世界家族已获准执行16条不同控制分支、另16次独立重放。四世界各自独立记录同一条12 s相机路径、121帧历史；A/B分别取从0计的第25/65帧，共同近期为第119/120帧，全部历史帧的单视图检查从同一合法记录截取，不额外模拟、不合成路径。每条分支为200段0.1 s控制、20 s真实执行。数据角色仅为已见工程开发；未来训练/验证/确认的家族数和划分另审，不使用当前公开设计做独立确认。

[冻结配置JSON](../configs/spatial_history/two_gate_engineering_v1.json)由新入口消费，`numeric_protocol_approved/generation_authorized=true`，`training_authorized=false`，`approval_decision=D-071`。`proposal_source/proposal_sha256`追溯原[数值提案](../configs/spatial_history/two_gate_engineering_proposal_v1.json)及提交3c5755e；除明确批准元数据和一个跨平台字节摘要外逐值一致。原提案的`physics_reference_sha256`为Windows工作树的CRLF字节摘要；活动配置固定改用同一Git blob的LF字节摘要，入口同时要求这两个固定值，不能借此改变任何物理值。白话：输入已接受的参数表，输出明确的执行来源；例如20 s不会因某条动作卡住而自动延长，配置本身不是运行成功回执。

| 配置字段/真值职责 | 中文定义与单位 | 权限和例子 |
|---|---|---|
| `geometry` | 门、侧壁、物块、推头和固定动力学；长度米、质量kg、力N、速度m/s | 生成器输入，不整体给模型；两门真实坐标私有，已声明的公共机器人/物块常数可公平共享 |
| `observation.camera_segments` | 相对历史起点的秒与相机y端点；`camera_segment_interpolation`为连续路径规则 | 相机实际位姿与真实时刻可见；预设A/B语义编号和真值分割不作为特征 |
| `controls.phase_duration_s / phase_vx_mps / phase_vy_mps / phase_vz_mps` | 对齐的10段时长与四候选速度表；每段按0.1 s展开 | 模型只消费所查询候选展开后的数值，不给LL等类别或名义物块终点 |
| `task_success / engineering_audit / budget_proposal` | 任务几何与停稳规则、来源/视野外/信息检查和运行预算 | 用于记录、监督、评分或执行边界；任务公开定义与实际真值结果分开，预算不是已发生耗时 |
| `object_axis_world / object_linear_velocity_mps` | 每物理步圆柱轴的世界单位向量及三维线速度m/s；完整旋转另在积分状态内 | 任务评估用轴方向求完整投影、速度判断停稳；主输入不读；未来训练标签须R4另登记 |
| `gate_events` | 真实相邻步、穿面插值时刻/横坐标、尝试号、回退失效、同次整个物块过线步及顺序 | 仅评估/审计；不拼接不同尝试，不把机器人计划过门时间当真实事件；具体不等式见METHOD |
| `object_position_m / object_axis_world / contacts` | 每步真实投影边界、目标停留/速度、所有涉及动态物体的原始接触距离（未按力筛选）和相邻步平移 | 仅评估/诊断，失败原样保留；1 mm目标边界容差、5 mm穿透/单步平移工程上限是不同条件 |

时间约定：相机表的0–12 s是稳定后采集窗口；公开帧`time_s=0.5+0.1×帧下标`，保留实际模拟时钟（允许1e−9 s浮点差）。未来文件使用相对决策的0–20 s：下标0是恢复初态，其后才是未来；任务停稳窗口为相对19–20 s。不得把数组第一行初态标成未来。全部控制分支从该世界同一完整积分状态恢复，独立重放单独保存。

白话：公开记录与真值文件分开，解决“加载整份场景时把答案顺手送进模型”的问题。输入`public.json`和所查询的控制名称，`model_input`只返回`history / controls / goal`；例如查询LR也只得到数值速度，返回值没有世界编号或LR类别。R3首批已交付实际读取器`public_reader.load_query`，服务器验证待运行；它是输入API边界，尚不等于训练进程/操作系统权限隔离。

**R3/public-input字段边界（D-072，已实现、待服务器验证）。** `public_path / expected_sha256 / expected_bytes / action_name / history_indices`为调用参数，前3项来自外层核验后的文件路径与manifest；后2项是查询控制及可选历史下标。读取器不自动寻找标签或旁边文件；先核验同一份原始字节，再拒绝重复JSON键、非有限常量和违反原公开合同的字段，最后按原`model_input`选历史。允许单文件至多32 MiB仅为内存/读取保护，不改变121帧协议；已验收4文件各约14.9 MB。

输入例（实际文件尚待服务器加载）：`steps/history-LL/data/public.json`，字节数`14904397`，SHA-256=`669b3afaed576fdc0219dd8a94364a469618b06aabc0da8d56de6d2e20675c90`，查询`action_name="LR"`、`history_indices=[25,65,119,120]`。合同输出为4个原始64×64 RGBD帧、200段`duration_s / ee_velocity_mps`数值控制、原公开goal；顶层严格为`history / controls / goal`。它不返回LL世界、LR名称、来源路径、摘要、下标、门洞真值、执行后机器人运动或未来物块状态。该例说明接口形状，不是本地实际读入的运行结果。

`public_audit.json`及导出报告的`queries[]`是私有审计记录：`world / action / mode`只用于回指检查项，`query_sha256 / history_sha256 / controls_sha256 / goal_sha256`按带末尾LF、排序键、UTF-8、2空格缩进的JSON计算；这些审计字段不进入读取器返回值。`public_inputs`保存R2四文件的原路径、字节数和原始字节SHA，不把规范序列化摘要混同文件SHA。报告保留`geometry_recovery_run=false / model_experiment_run=false / new_training_steps=0`；不保存一套复制的公共图像或新标签。

| 实际文件/键 | 形状、来源与语义 | 可见范围 |
|---|---|---|
| `steps/history-W/data/public.json` | 仅`schema_version / history / actions / goal`；actions是四条共同数值控制，history有121帧 | 公开记录；路径中的W不可作特征。`model_input`返回所选历史/单条控制/目标，不返回选择下标 |
| 历史帧 | `time_s,width,height,rgb,depth_m,camera_position_m,camera_xyzw,intrinsics,ee_position_m,ee_velocity_mps,previous_velocity_mps`；RGB扁平12288整数、深度4096米值；其余沿用旧帧坐标约定 | 公开；所有历史末端指令为零，相机/本体是真实读数，不读未来 |
| `world.xml / snapshot.json / history.json / observation_evidence.json` | 实际XML、完整积分状态及其XML SHA/状态枚举、原历史、121份按geom计数的分割可见性和观察不改状态标志 | 私有审计；history.json是公开帧的原始副本，但未来加载器只取public.json |
| `steps/primary-W-A/data/trace_raw.jsonl` | 含初态10001行，每行`step_index,time_s,object_position_m,object_axis_world,object_linear_velocity_mps,pusher_position_m,actuator_force_n,contacts,object_visible_pixels` | 原始真值；contacts保留全部接触，每项为`geoms / distance_m / normal_force_n`；未采分割的步可见性为null |
| `trajectory.jsonl / visibility.jsonl` | 前者补齐所有规定审计步的可见性；后者保存这些步的实际`step_index / counts`，原trace不覆盖 | 私有审计；由保存的真实状态恢复渲染，不补执行或合成mask |
| `integration.npy / end_snapshot.json` | 10001×实际完整状态宽度的float64，以及最终完整状态 | 私有恢复/重放；包含真实物块旋转和机器人响应，不能作模型控制输入 |
| `rgb.npy / depth.npy` | 分别201×64×64×3 uint8、201×64×64 float32；初态加200个控制末时刻 | 决策初态加未来真实传感器；后200帧仅供后续已登记监督/评估，本批不训练 |
| `sensor_times.npy / sensor_step_indices.npy` | 各201项，相对决策时刻与原物理步下标，float64/int64 | 传感器与轨迹对齐审计，不用绝对历史时间冒充未来 |
| `rollout.json / result.json` | 分支状态/控制摘要、文件摘要、实际评分；`gate_events`含穿面两步、插值时刻、尝试/取消/完成状态；物理检查极值及首次失败步 | 私有结果；raw_task_success为几何判定，physics无效时task_success为null |
| 历史PNG、`final_ego.png / private_overview.png` | 历史首/A/B/近期、末帧原RGB；另有固定高位审查相机图 | 前两类是公开像素的展示副本；overview只作`review_only_not_model_input`，不进传感器数组 |
| `check/`、各步`receipt.json`、根`started.json / environment.json / completion.json` | 测试身份/退出状态、来源、环境、manifest、耗时/字节和终检记录；seed=null，无随机采样 | 私有来源；未运行、完整失败和中断分开，不为中断补造通过 |

物理异常保留`failure.json`的有效状态前缀/已写trace行数，必要时保存`failed_current_state.f64`及未落盘批次`pending_actual_samples.jsonl`。预分配数组的未写部分不能当有效轨迹。导出JSON嵌入回执、逐分支评分、121帧信息损失/等价组、历史可见性、失败日志尾及选定原PNG；完整原始数组仍留数据盘，逐文件摘要进入报告。

### E0开口前缘恢复字段（D-078并行工程，服务器尚未生成）

白话：本合同把恢复器自己的判断与评估答案分开。输入为原公开帧及共同相机规格，输出坐标区间和支持这些区间的像素；例如每个开口有左右内边及前缘三条边，评估端再检查实际门边是否落入区间。这不是给恢复器两个真值门让它微调坐标，也不是完整三维地图。方法见[METHOD](METHOD.md#e0-public-geometry)，活动配置为[public_geometry_parallel_v1.json](../configs/spatial_history/public_geometry_parallel_v1.json)；它保持科学数值，另登记并发运维。下面是实现字段定义，当前没有这批服务器结果。

| 实现字段 | 形状/含义 | 权限 |
|---|---|---|
| `public_sensor_spec / extractor` | 共同轴向深度、裁剪和姿态条件；平面/边界/融合数值 | 提取器只接这两个白名单子对象及合法history，不能接含评估部分的完整配置；0.04/20 m来自原共同参考XML及固定extent，不读各世界XML |
| `schema_version / history_frames` | `public-openings-v1`及本次实际传给提取器的帧数 | 公共恢复输出顶层还含`candidates / conflicts / incomplete_observations / rejected_counts`，严格六个字段；无世界/门类别 |
| `candidates[].coordinate_intervals_m` | `3×2`米区间，顺序为左内边x、右内边x、前缘y；每项为`[lower,upper]` | 从公开深度计算；候选数可为0或更多，不按真值固定为2 |
| `candidates[].coordinates_m / plane_height_interval_m` | 三条坐标的区间中点，以及被观测顶面的世界z区间 | 中点不表示亚像素真值；与D-075的`gate_opening_front_m`对应要经评估匹配，输出本身不附近/远标签 |
| `candidates[].support[]` | 严格含`local_frame_index / pixel_pair / boundary_kind / raw_interval_m / plane_height_interval_m`；像素对为`[[u_surface,v_surface],[u_farther,v_farther]]`，边类型为`x_left / x_right / y_front` | 局部下标相对于传入history；原始下标映射由外层保存。每条支持保留融合前坐标与顶面区间，不用私有实例分割 |
| `incomplete_observations[]` | `local_frame_index / row_span / plane_height_interval_m / reason`；行范围`[first_v,last_v]`，原因包括无效/较近间隙、连续行或二维面片不足、缺前缘及边区间不相容 | 缺边保持未知。局部视野自然造成的未闭合观察可与成功候选并存，不单独作为整批失败 |
| `rejected_counts` | 九项非负整数计数，详见下文 | 记录无效深度和候选提取拒绝，不用于筛选世界或补几何 |
| `conflicts[]` | `reason="empty_common_intersection" / members`；members保留该重叠连通组全部原候选与支持 | 公共证据自身的冲突；不可用平均消除，独立验收必须检查 |
| `started.json.jobs[]` | `id / world / mode / indices / expected_candidates / public_path / expected_sha256 / expected_bytes`；mode为`full / view_a / view_b / recent` | 外层清单与来源审计，世界、模式、下标和预期数量不输入`recover_openings`；public worker只把选后合法history及两个公共参数对象交给它 |
| `predictions/query-NN.json` | `prediction / prediction_sha256 / public_file_sha256 / history_sha256 / history_frames` | prediction为上方六字段恢复输出；其余绑定原公共文件及实际切片，均由外层生成。保存全部16项，不只保留通过项 |
| `public_seal.json` | `public_complete=true / predictions`；后者为16个预测文件名到`bytes / sha256`的映射 | 所有预测完成后封存，私有XML解析前后都复核；不把内容规范摘要与整个预测文件字节摘要混为一谈 |
| `evaluation.json.private_xml_evidence` | 每世界保存`relative_path / bytes / sha256 / xml_text / targets`；targets每项含`coordinates_m / plane_height_m / gate_index` | 仅独立评估可见。XML为原manifest绑定的实际UTF-8文本，摘要与字节数对应原文件；可在本地只读复算，不按世界名称填答案 |
| `evaluation.json.rows[].assessment` | `accepted / checks / failed_checks / registered_count_matches / targets / matches / pair_diagnostics / eligible_target_indices`以及候选、目标、冲突、未闭合和匹配数 | 全候选与全目标唯一匹配；`pair_diagnostics`保留逐配对坐标/高度包含和中点误差，`matches`另含区间宽度；匹配数超过1时最多保存2表示已证非唯一，不挑最佳子集 |
| `audit.json / receipt.json / worker/*.json / exits/*.json` | 汇总输入帧数/查询数/近期一致/坐标验收，逐子进程完成与退出状态，来源/输入不变性、错误、manifest及资源记录 | 读取工程、运算完成、几何门与失败可分别追查；缺失阶段不能补造通过，不修改原R2/R3报告 |
| 导出报告的`receipt / receipt_sha256 / artifacts_json / export_resources` | 实际回执及其字节摘要、阶段JSON产物内嵌、首次导出资源记录；失败时可附`tests_log_tail` | 报告仍是私有工程审计。`public_geometry_recovery_verified`仅能随新批次成功验收成立；完整地图、物理预测与模型实验声明保持false |

`rejected_counts`的九个键为`zero_depth_pixels`（0深度像素）、`clipped_depth_pixels`（近/远裁剪范围像素）、`insufficient_side_run_pairs`（双侧连续像素不足）、`invalid_gap_pairs`（间隙含无效深度）、`nonfarther_gap_pairs`（间隙未全部更远）、`insufficient_row_groups`（连续行不足或行配对竞争）、`insufficient_side_patch_groups`（二维面片不足）、`missing_front_groups`（前缘见证不足）、`incompatible_boundary_groups`（行内融合或双侧前缘区间不相容）。这些是提取过程计数，不是物理失败标签。

规范JSON摘要使用排序键、UTF-8、2空格缩进、末尾LF；`public_file_sha256`和封存manifest则绑定相应文件的实际字节。`started.json.jobs[].indices=null`表示完整历史，其余保存原始下标；提取器的`support.local_frame_index`只需通过该清单映射，不能从恢复输出倒填近/远门标记。所有16份预测封存之后，评估子进程才解析原XML；公共请求文件不含XML、预期门数或评估配置。RGB不变性仅由新手工解析服务器检查提供，不额外运行真实查询。

`started.json.execution/resources`记录实际worker数、每进程512 MiB地址空间门、树RSS门、CPU/cgroup/RAM预检；`receipt.json`另记录`launched_children / not_started_ids / missing_exit_ids`。白话：例如4路只说明四个公共查询可同时处理，输出仍是原16项封存预测；不能把并发PID当作新样本。首轮run/export共同使用1800 s，阶段与报告总字节≤64 MiB；预检只覆盖可见约束，不表示资源已预留或得到连续精确峰值。

正式回执与首份导出均先写pending文件：阶段内`receipt.pending.json`及报告旁`spatial_history_public_geometry_parallel_v1.pending.json`。写完并通过时间/内存收尾门后才重命名发布；pending表示未完成发布，不是可复用的成功回执或报告。失败/中断不覆盖原现场，不能把pending中的临时成功字段当作正式验收。

原公共文件、XML及报告均只读；新产物为稀疏候选、像素支持、封存/评估及资源证据，不复制完整RGBD或另存密集点云。固定16查询向恢复器传入`4×(121+1+1+2)=500`帧，这是提取器输入计数，不是新样本。公共worker输出按固定查询ID排序，跨进程写入以`.write.lock`保护预算和写入。入口目录为`/root/autodl-tmp/spatial-history/sh04-r3-e0-public-geometry-parallel-v1`，导出路径为`results/spatial_history_public_geometry_parallel_v1.json`；登记路径不表示服务器目录或报告已经生成。

### 历史利用诊断的记录字段（D-075，proposed，尚无schema实现或产物）

白话：这些字段把同一案例的输入、内部诊断和实际后果连接起来，供评估端定位错误。输入是合法查询产生的状态/预测及独立真值文件，输出可回指来源的诊断行；例如某条控制预测成功但实际受阻，可以追到对应的历史状态和接触区间。它不扩展现有`public.json`或`load_query`，也不允许把诊断标签返回主模型。实验和指标定义见[METHOD的E0–E4](METHOD.md#history-use-diagnostic)。

| 拟议字段 | 形状、单位、含义 | 边界 |
|---|---|---|
| `audit_key / model_revision / adapter_revision / checkpoint_sha256 / seed / history_mode` | 关联家族、世界、控制、代码、权重及full/recent条件 | 外层私有审计，编号/摘要不作为网络特征；无checkpoint时明确未运行 |
| `history_cut_index / input_prefix_sha256 / state_ref / state_schema` | 原始前缀末帧、实际消费的公开前缀摘要、状态产物引用和结构版本 | 状态仅由相应前缀形成；引用由诊断进程读取，不将文件路径作为主模型或探针特征 |
| `gate_opening_front_m` | `2×3`米值，每门为`[x_left,x_right,y_front]`；左右为两侧墙的开口内边，前缘为较小世界y的墙面；沿y由近到远排序 | 分别保存公开观测估计、探针预测和私有评估目标，三通道不混淆；前缘不是原任务的门中心穿越面 |
| `observed_support / geometry_unknown / geometry_error_m` | 恢复器的观测来源、未知区域及评估误差；探针目标另有评估侧的证据已出现标记 | 恢复器来源只能由公开帧形成；私有可见性只在评估侧核对，不作为选帧或对象mask输入 |
| `probe_revision / probe_training_family_digest / probe_target / probe_prediction` | 冻结读出的来源、拟合家族登记、独立目标及预测 | 探针训练不能使用本工程家族或确认家族；目标不回流主体，标签打乱负对照另存版本 |
| `prediction_times_s / object_position_m / obstacle_contact_probability` | 相对决策时刻`0.1,0.2,…,20.0`，分别200项、`200×3`米值和200个区间接触概率 | 主预测输出；初态不混入200个未来值，不得从真实轨迹填补缺项 |
| `rollout_state_ref / rollout_time_s / diagnostic_geometry` | 原生预测状态在相对`0,5,10,15,20` s的引用和几何读出 | 0为决策初态，其余只能由控制推演；兼容的原生中间状态读取需适配合同明确，不能填入未来观察 |
| `task_success_probability / diagnostic_success_probability / selection_probabilities` | 主整段成功概率、冻结诊断读出的概率及四候选选择概率 | 主结果和诊断结果分列；并列最优均匀分配仅用于计算期望代价，不假称实际随机执行 |
| `paired_worlds / changed_gate / prediction_difference / actual_difference / pair_position_error_m` | 四条单门配对边、被改变的门、同控制的预测/真实差及配对位置误差 | 仅评估端重组原分支，不成为新独立样本；模型不读取配对编号或哪扇门改变 |
| `actual_task_success / expected_actual_cost / selection_regret / evidence_flags / unresolved_reasons` | 原任务标签、选择的期望实际代价、相对最优候选的代价差及归因证据 | 缺失/物理无效/推理失败分别计数；未完成诊断记未核验，不强行归因 |

预测接触按控制间隔定义：第k项表示相对时间`(0.1×(k−1),0.1×k]`内至少一次物块—门/侧壁正力接触的概率，k为1至200。评估标签读取原物理步`50×(k−1)+1`至`50×k`，沿用原距离≤0、法向力>1e−6 N及物块与`gate_ / side_`的对象规则；不计推头/地面接触，不用控制末一个瞬时接触代替整个区间。初始步0单列，不归入未来。区间概率不自动定义“全程至少一次接触”的概率，后者若使用须另行登记汇总方式。

整段成功仍使用原`assessment.task_success`。物理无效时该值为null，不把`raw_task_success`偷换成有效主标签；可见性合格性、物理有效性和任务成功分别报告。任一候选标签缺失/为null或预测不合格时，该世界的`expected_actual_cost / selection_regret`为null并注明原因；不对余下候选重归一化，汇总同时报告可计算数与完整登记数。私有完整姿态/速度/门事件可以解释错误，却不能通过来源关联进入主模型。诊断行只引用经manifest绑定的原始轨迹，不修改原产物；模型状态、逐步预测等大文件在未来获准的服务器新目录，小报告由阶段入口导出，当前未创建运行目录。

深度说明的静态纠正：上方原“正深度、无效拒绝”表述强于实际代码。`pair_contract.frame`及调用它的双门合同接受有限非负值，0已在旧帧合同中定义为无效；本次仅修正文档。公开几何恢复应由`depth_m>0`派生有效性，不把0投影成真实表面。没有修改读取器、原schema或旧报告，也没有据此声称原实际RGBD含有零值。

<a id="r4-data"></a>

### SH-04-R4接口与新家族登记（D-079冻结；R4-1值合同代码待审，尚未生成）

白话：本节把过去观察、模型预测、训练标签和评估真值分开存。输入为预登记的新物理家族，输出可以按来源重放的公开查询、独立标签和预测报告；例如四世界的同一条数值控制共享候选语义，但模型只看控制数值。旧工程家族不变成训练或确认样本；本节也不是已经实现的新数据加载器。

| 接口字段 | 形状/单位及定义 | 读取者 |
|---|---|---|
| `history.rgb / depth_m / depth_valid` | `[121,64,64,3]` uint8、`[121,64,64]`原始米值及由深度>0派生的bool；前缀/近期变体按实际帧数 | 模型；原始精度保留，float32张量转换单列 |
| `history.time_s / camera_position_m / camera_xyzw / intrinsics` | `[T] / [T,3] / [T,4] / [T,4]`；时间−12至0 s，位姿和像素中心沿用原合同 | 模型；不含未来相机实测 |
| `history.ee_position_m / ee_velocity_mps / previous_velocity_mps` | 各`[T,3]`；当前本体和上一控制 | 模型；不是未来执行轨迹 |
| `controls.ee_velocity_mps / duration_s` | `[200,3] / [200]`；每段0.1 s，z控制为0 | 单候选预测调用；四候选排序由外层维护 |
| `goal / domain_spec` | 原整段停稳/按序过门定义及共同固定物性；目标区域可随全局平移同步变换 | 模型；不附实例门参数 |
| `prediction.object_position_m / obstacle_contact_probability / task_success_probability` | `[200,3] / [200] / scalar`，有限值，概率在[0,1] | 评分器；缺项/非有限/越界为推理失败 |
| `prediction.native_state_refs / native_point_flows / sample_index` | 原生状态/点流的摘要引用及随机样本号；状态shape和轴单位另由各适配manifest登记 | 独立诊断；路径/ID不得作为特征 |
| `labels.object_pose / interval_contact / task_success / future_rgbd` | 训练侧完整物块姿态、200段接触、整段成功及未来原RGBD | 仅获准的训练损失或独立评估；不与public放同一读取对象 |
| `audit.actual_robot_trajectory / xml / geometry / visibility / family_spec` | 完整原始执行、实例门几何、逐采样可见性及生成参数 | 评估/来源审计；几何探针训练只读自己split的门目标 |
| `manifest.contract_sha256 / source_commit / adapter_commit / split_digest / asset_digests` | 固定协议、源码、适配、分组及真实下载资产摘要 | 外层先核验；全部预测封存后才连接确认真值 |

新公共外层版本为`spatial-history-r4-query-v1`，其当前R4-1值合同实现只接收调用者已选出的full/recent/prefix公开帧，不读取文件、标签或模型状态；原R2 public文件与读取器保留原版本。R4只是显式的张量/权限适配，不能给旧严格校验器添加绕过模式。区间接触仍按本页D-075物理步范围计算；初始状态不混入200个未来末点。公开robot几何点由固定外形和计划/预测位姿产生，来源字段只允许`planned`或`predicted`，任何`actual_future`输入直接拒绝。R4-1的手工值只用于解析和评分边界检查，不是新家族、真实训练标签或物理结果。

**家族与划分。** 首批固定64个新家族：model_train 32、model_validation 8、model_confirmation 8、probe_train 8、probe_validation 4、probe_confirmation 4。每家族4世界、每世界4控制，共256历史、1024首次分支，另1024次独立反序重放；重放不增加样本。工程R2、SH-03、旧CPMT和旧v1均不参与任何split。确认家族属于本次未来小试确认，不是旧封存test，也不是SH-07外部确认。

64个内部索引i=0…63，按UTF-8字符串`sh04-r4-v1:split:i`的SHA-256升序分配以上六个连续区段，碰撞以i升序打破；i用无前导零十进制。所有同源世界、控制、顺序变体、未来chunk、特征缓存及增广继承家族split。参数去重比较去除共同x平移后的完整几何、控制和观察时序；若存在重复/等价家族则整份清单拒绝，不能重抽某项。不发布确认参数/像素预览给开发者；生成规则公开，但学习/选参进程不读取family_spec或任何确认文件。

**独立连续因素。** 对每个字段k取`sh04-r4-v1:param:i:k`的SHA-256前8字节大端无符号值，除以`2^64−1`得到u，线性映射到JSON登记范围。两门位置分别在[0.56,0.64]、[2.16,2.24] m；近/远门各有独立中心偏置[−0.02,0.02] m、左右半间距[0.10,0.16] m和净宽[0.34,0.42] m。同家族四世界使用这两个位置的笛卡尔组合，只改变相应门洞；全局x平移在[−0.12,0.12] m，同步施加于所有场景、相机、初始机器人/物块及目标。除此之外物性、厚度/高度、任务规则、20 s/200步及0.002 s物理步沿用D-071，不能由世界类型推导成功标签。

四控制在同家族仍完全相同：D-071四段横向路线共用两个独立缩放，前5个phase的vx乘`control_near_scale`∈[0.8,1.2]，后5个phase的vx乘`control_far_scale`∈[0.8,1.2]；vy、vz、phase时长不变。缩放的hash键与几何键独立，不读取实例门坐标。这样同一侧别在不同家族可有不同间隙和控制偏差，但“侧别不足以选对”仍须检查实际矩阵，不能仅由连续采样宣称成立。

**观察时序。** 每家族独立取近门先见或远门先见（hash值最低位）；两停留中心时间分别为2.5+δ1、6.5+δ2 s，δ1/δ2从{−0.3,0,0.3}独立hash模3选取。第一/第二停留各1 s，位置固定为y=0.6/2.2 m或反序，起点及11至12 s固定y=−0.1；区间之间用D-071三次smoothstep逐物理步移动。相机位置不追随真实门y，路径在四世界间一致。图像/时间/本体是真实记录；A/B和停留编号只给诊断。E1前缀检查点为每次停留中心、末端、末端后0.9 s，以及10.1/12 s去重升序；当前原R2仍用D-075原下标，不回写旧记录。

**先审构造再学习。** 未来生成器先固化64行清单/配置摘要，仅运行固定model_train排序前4家族的工程子批（不是额外4家族）。子批通过后，逐职责审过的同版本可继续剩余非确认家族；成功子批复用。每家族必须核验物理、近期精确一致、全部121个单视图等价组、不可见关键交互、实际任务矩阵及独立重放；E0正向恢复也须按新记录核验，沿用登记精度。信息门沿用D-070每世界至少一成功、最小固定单视图regret≥0.25；不要求对角矩阵。若任何家族不合格，保留已运行事实并停止依赖学习，不删除该家族、补样或条件筛选后训练。

开发侧还必须报告只读二元门侧别的模板参照是否已足够：按D-071四种数值路线的固定顺序关联候选，对每种二元侧别将全部已生成开发家族的真实最优候选索引集合求交；若四种侧别的交集均非空，说明每种侧别仍能固定选一条路线，登记`categorical_shortcut_unexcluded`。侧别仅为这个特权审计参照的输入，不提供给主模型。即使各家族最优集合不完全相同，只要存在共同最佳路线也不能声称排除了类别捷径。本批此时只能作接口小试，不能推进以跨几何整合失败为依据的SH-06；不据此剔除家族，新场景修订须新版本，不挪用本批确认来定范围。

**保存与封存。** 原RGB uint8、深度/积分float64、采样索引、每物理步接触/任务事件、XML、起始快照、失败及退出全部保存；仅允许无损压缩和同源字节按摘要去重，不按预算删掉原始轨迹/未来RGBD或减少重放。公开、训练标签、审计三通道独立manifest。model_confirmation 8家族及probe_confirmation 4家族在主体配方/全部seed checkpoint、探针配方/权重和评分代码分别锁定后，经确认步骤放行才生成；若其构造门失败，报告该预定分母中的无效项，不能利用它调生成器或模型并继续称独立确认。

模型产物与上述原始物理证据不同：所有逐样本200步位置/接触/成功、选择、诊断读出、错误和来源都落盘；每个原生状态/完整点流保存精确shape/轴/摘要与`checkpoint+public_query+random_stream+prefix_or_chunk`可再生引用。每系统/seed固定选各split排序首家族的首世界、首控制、sample0，额外落盘完整原生状态/点流供审查，不按失败挑样本。其他状态是`materialized=false`，不得宣称已存完整数组；诊断运行当时消费真实内存状态并保存读出。再生必须先核验环境/确定性及原摘要，失败记不可复现；再生计算另计入既定预算，不覆盖主预测或伪造原运行回执。此规则避免把全量49×49×5×256地图和点流缓存误估为小报告，也不修改原物理产物保留要求。

<a id="r4-public-front-control-data"></a>

#### R4-3公共派生值与控制来源（D-085，proposed，尚无schema/产物）

本节基于v2原生80×80/九候选，不更改旧v1字段或v2查询/预测校验器；下面是待实现的内部值和外层审计记录，不宣称已有文件。方法与中文概念解释见[METHOD](METHOD.md#r4-public-front-control)。

白话：这些记录解决“同一个坐标究竟来自观察、假设还是预测”。输入合法公共值，输出带来源的派生值和独立失败状态；例如公开前缘加共同半厚度得到门中心，必须能追到前缘像素和所用常量。这不是给模型添加世界ID、审计路径或真值标签。

| 拟议对象/字段 | 值与读取边界 |
|---|---|
| `frame_surfaces.voxel_keys / source_pixels` | 每帧去重的三维整数覆盖键，0.02 m、固定世界原点；每个来源为所给历史内局部帧下标及原生行列。坐标来自深度；来源只用于取原帧/像素和审计 |
| `retrieval.selected_local_indices / selected_time_s / marginal_new_voxels` | 最多10个不重复下标及原时间；另存贪心选择顺序和每次新增数，最终编码按时间顺序。全零新增按原规则保留；近期/前缀不读取所给历史之外的像素 |
| `public_objects.status / candidates / position_m / support_weights` | 从近期公开像素拟合的物块候选、中心、支持及不确定性；推头当前位置/速度来自公开本体。D-087以显式`interval_mean_velocity_mps`细化原拟议velocity字段，避免混淆瞬时速度；未决时不发布单一有效物块，子schema见下方待审提案 |
| `observed_map.surfaces / free_evidence / unknown / conflicts` | 保留原生表面和射线/足迹证据、未覆盖与矛盾；动态/歧义点有独立状态。不能将未命中体素自动标free，不能以P降采样点替代全部几何 |
| `collision_geometry.primitives / coordinate_intervals_m / assumption_refs` | 由观测及共同形状/厚高形成的名义碰撞体、区间和明确结构假设；所有体都须有公开支持。不可包含来自实例XML的墙端或两门模板补全 |
| `point_scene.points_m / appearance_sources / object_support / validity` | P拟议0.01 m融合后至多4096点及原RGB来源；保留关联权重和缺失状态。此阶段没有DINO特征或未来真值点；外观来源不能改挂最近帧 |
| `robot_motion.kind` | `command / planned / predicted / actual_future`是互斥来源。实际控制接口只接数值command；P正式机器人条件只接受已绑定公共预测器产生的predicted |
| `robot_prediction.position_m / velocity_mps` | 推头t=0和0.1…20 s，共`[201,3]`；t=0来自公开本体。内部0.002 s轨迹`[10001,3]`用于控制/接触检查，不从实际10001行拷贝 |
| `robot_prediction.robot_points_m / status / valid_prefix_steps` | P条件拟为`[201,512,3]`，固定外形点身份加自身预测位姿，机器人点采样规则后续冻结。路径状态与M任务读出状态分开；失败可留前缀供诊断，不能拿前缀填满200步正式预测 |
| `map_rollout.object_state / contacts / task_events` | 仅M任务读出及独立评估读取；不进入P动作输入。状态自由度、碰撞/摩擦数值schema尚待控制职责冻结 |
| `result.status / reason / first_unresolved_time_s / prediction` | 最终任务结果外层状态拟分`ok / perception_unresolved / map_unresolved / control_unresolved / task_readout_unresolved / numerical_failure`；仅ok携带完整v2 prediction，其余prediction=null且保留失败前缀。进入既有评分前映射为无效候选，九个注册位及原代价界不变；M任务读出失败不自动使有效机器人路径或P任务预测失效 |
| 外层`provenance` | 原始公共manifest/查询摘要、具体代码/参数/假设版本、原生像素到派生几何的映射和封存摘要。函数可消费公开局部索引，ID/路径/hash/split/世界类型不进模型特征 |

数值张量与来源旁表分开。M/P可消费公开几何的有效/未知状态，因为它是观察派生信息；不能消费独立评估的真值匹配、指定A/B/停留帧号、私有mask、实际接触或成功矩阵。R不消费M/P的关联或碰撞输出。前端纯值函数无文件读取权限；外层来源验证可核验manifest，但不能借此把私有config作为科学函数参数。这里仍是函数/进程数据边界，不声称已经建立操作系统隔离。

**拟议误差字段（连续诊断，无新通过阈值）。** `robot_position_error_m`在200个未来末点分别计算预测与实际的三维欧氏距离，保存逐点、均值及终点；`robot_velocity_error_mps`同样逐末点对比速度；planned和predicted分别标明，不能拿计划误差冒充控制模型误差。`object_initial_position_error_m / object_initial_velocity_error_mps`仅在公共估计封存后对比决策真值；未决估计不记零误差。`unresolved_count / registered_count`按完整登记候选及原因计数，另存首次未决时刻，不作条件成功率。

白话：这些误差用于区分“开始就没认对物块”与“推头后来预测错了”。例如物块初始误差很小、推头受阻后位置误差变大，支持继续检查控制近似；这不是单凭相关性确定原因，也不是新增达标门。地图与点支持的误差必须在具体几何schema冻结后另定匹配和分母，本次不虚构一个统一地图准确率。

本轮只登记字段/权限，没有新源数据、缓存、预测、manifest或测试回执。原v2两份通过报告仍按7a2005c源码/文档摘要复用；新文档和未来R4-3代码不能冒用原33/37项回执认证。

<a id="r4-coverage-data"></a>

#### R4-3a实际值接口与工程回执（D-086，代码待审，无服务器产物）

白话：这个值接口让“能选哪几帧”和“原图像保存在何处”分开。输入仅已批准切片的原生深度与相机数值，输出本地帧下标和全部像素证据；例如recent输出下标0/1，外层负责映射回原119/120。这不是把0/1当世界类别，也没有改变原始RGBD储存。

| 实现对象/字段 | 严格定义 |
|---|---|
| `history.schema_version / frames` | `spatial-history-r4-depth-history-v1`；frames为所给切片的列表，不收完整query。模式/cut是函数关键字元数据，不在数值帧内 |
| `frames[].time_s / width / height / depth_m` | 原决策相对时间、整数80/80及行优先6400个原深度；不允许附RGB/depth_valid/控制/目标/本体/mask/ID。有效与裁剪在模块内从原深度派生 |
| `frames[].camera_position_m / camera_xyzw / intrinsics` | 米制3值、xyzw四元数4值及fx/fy/cx/cy四值；相机约束沿v2，不增加实例几何 |
| `public_sensor_spec` | 只准depth_kind=`camera_axis_distance_m`、pixel_centers=`integer_u_v`、near_depth_m=0.04、far_depth_m=20、clip_margin_m=0.0001；其他E0字段不传入 |
| `selection_parameters` | 仅voxel_m=0.02、recent_keep=2、additional_frames=8、origin_m=[0,0,0]，所有值严格锁定 |
| 反投影结果`schema_version / frames` | `spatial-history-r4-surface-coverage-v1`；每帧local_index/time_s、voxel_keys `[V,3]`整数、source_pixels为同序V个不定长`[row,column]`列表，以及valid_pixels/zero_depth_pixels/clipped_depth_pixels，三计数和为6400 |
| 选择结果`schema_version` | `spatial-history-r4-coverage-selection-v1`；没有task prediction，不送入v2后果评分器 |
| `selected_local_indices / selected_time_s` | 按时间排序的唯一选择，最多10帧；原始时间不重新归零；外层取回原RGBD，只把原合法观察送编码器 |
| `selection_trace / selected_union_voxels / frame_surfaces` | trace逐次记录local_index、role=`recent/greedy`、new_voxels；并集覆盖数只描述已选表面格；frame_surfaces嵌入全部所给帧的反投影证据，不是地图、模型token或真值覆盖率 |

外层适配必须先按已审v2读取器选择full/recent/prefix，再显式提取上表字段并将源0.5…12.5 s转为−12…0 s。当前纯值函数不读服务器公共文件、不认证调用者拷贝来源；未来真实接线仍需原公共manifest/切片/像素摘要绑定。投影/选帧版本字符串、来源索引和边际分数留在调度/审计，不能作为新增模型语义特征；R原本可见的观察时间保留。

独立服务器产物目录由PLAN固定，拟含started.json、tests.log及receipt.json；receipt绑定11项源码/配置/文档及原Git完整提交、27项测试身份/数量/失败/跳过/预期失败、时间/峰值RSS、实际阶段总字节和两个证据摘要。失败或中断保留已有文件，尽可能写failure.json；存在目录只verify，不自动续跑，缺退出不造成功。导出到`results/spatial_history_r4_coverage_v1.json`，嵌入原证据文本/字节数/SHA及原receipt摘要；不同报告拒绝覆盖，失败导出可保留截断JSON原文。

回执明确新模拟/训练/权重字节均0，真实历史检索、几何恢复、地图、物理预测、模型和长期记忆主张均false。run的必要人工例与独立运维检查只认证本职责；旧v2的33/37项通过不能代替27项新回执。verify/export不调用科学函数或重新运行测试；计时上限是每条命令300 s，不伪称整个后续R4-3的总预算。

<a id="r4-object-association-data"></a>

#### R4-3b公开对象值接口提案（D-087，proposed，无实现/产物）

方法、数值含义与手算例见[METHOD](METHOD.md#r4-object-association)，数值源为[r4_object_association_proposal_v1.json](../configs/spatial_history/r4_object_association_proposal_v1.json)。以下是新纯值接口提案，不改变原v2公共记录/查询/预测schema，不向记录文件增加私有mask或对象初态。提案的版本、decision、授权和预算字段由外层审查/运维读取，科学函数只接列明白名单，不能把整个提案JSON当科学参数。

白话：这些字段让“看到了什么”和“以后动力学想假定什么”能分开核查。输入两帧公开传感值，输出顶面支持、中心范围与区间平均速度；例如速度中点为0也会保留非零宽度区间，自旋仍为空。这不是测得完整刚体状态，也不是给M/P新增真值输入。

| 拟议字段/接口 | 值、状态及权限 |
|---|---|
| `object_history.schema_version / frames` | 新`spatial-history-r4-object-history-v1`，只收原119/120两帧；不是a的history额外附字段后直接通过a入口 |
| `frames[].time_s / width / height / depth_m / camera_position_m / camera_xyzw / intrinsics` | 与D-086同数值定义和合法近期切片；保持原−0.1/0时间与行优先6400深度，不接受RGB/depth_valid/previous_velocity/mask/控制/目标/ID |
| `frames[].ee_position_m / ee_velocity_mps` | 公开本体三维位置/速度；有限数、非布尔。用于推头几何排除与原值输出，不作为物块初速度或静止依据 |
| `public_sensor_spec / common_shape_spec / association_parameters` | 传感器白名单同a；外形仅半径、半高、推头半尺寸和固定世界轴运动学常量；参数只取提案segmentation/fit的数值和规则，逐值锁定，不能传实例XML/质量/目标/私有配置 |
| 单帧原语`frame_candidates` | 仅接一帧合法数值与三份白名单；输出原相对时间、所有高度分量、推头mask及拒绝原因。外层两个单帧结果须由正式两帧入口内部计算，不能把外部预计算候选伪装成公开恢复 |
| 结果`schema_version / status / reasons` | 拟为`spatial-history-r4-object-association-v1`；`status=association_ready / perception_unresolved`。格式/非有限/非法字段等输入违约抛合同错误；合法但缺支持/遮挡/歧义返回未决及原因，不抛成读取异常 |
| `frame_results[].components` | 每项包括局部`component_index`、`classification=accepted_candidate / incompatible_extent / unexcluded_component`、`reasons`、行优先`support_pixels`、外环及轮廓来源、顶面区间、delta和各门观测值。索引按最小行列再最小z排序，只是审计身份 |
| `frame_results[].association_ready / selected_component_index` | 恰有一个完整候选且没有其他未排除分量才为true并给索引；否则false/null。排除大分量只证明不符合该圆柱大小，不认证为静态墙 |
| `frame_results[].position_m / position_intervals_m` | 单帧唯一关联时的名义中心`[3]`及区间`[3,2]`，否则null；每候选的诊断拟合可独立保留。x/y为弦中点区间交集，z为顶面区间减共同半高 |
| 顶层`position_m / position_intervals_m` | 两帧整体association_ready时引用末帧唯一结果，否则null；单帧成功但整体未决仅保留在frame_results中，不能顶层伪装完整状态 |
| `support_weights / interval_kind / assumption_refs` | 支持权重在每个通过候选内按其像素数等分；区间类型`conditional_raster_geometry_envelope_not_statistical_confidence`；假设显列直立圆柱代理、完整圆形轮廓及像素过渡范围，不产生真值mask/校准概率 |
| `velocity_time_interval_s / interval_mean_velocity_mps / interval_mean_velocity_intervals_mps` | 原两帧时间、三维中点差/dt及`[3,2]`端点最坏组合；整体未决时速度及区间null，原输入时间仍可留诊断。不发布未注明来源的通用`velocity_mps`物块字段 |
| `velocity_kind / instantaneous_velocity_observed` | 固定`backward_interval_mean / false`；没有“误差低于任务静止门”的自动通过条件，不把相同估计等同于实际静止 |
| `orientation_xyzw / angular_velocity_radps / dynamics_initial_state_ready` | 恒null/null/false；近水平表面门没有测出零倾角或自旋。动力学须用自己的已审初始化近似，不能由此补真实姿态或零角速度 |
| `robot_state.position_m / velocity_mps / source` | 原末帧公开本体值，source=`public_proprioception`；与物块估计分开，不读取未来本体。即使物块未决也可保留合法本体值 |
| 外层`provenance` | 原公共manifest/切片/像素、白名单和参数摘要、代码/假设版本及封存输出摘要；路径/hash/原世界/配对/split不入数值特征。值检查不代替真实来源认证 |

`reasons`拟至少区分`pusher_projection_unresolved / insufficient_support / incomplete_outline / center_interval_empty / center_interval_too_wide / radius_mismatch / no_accepted_candidate / multiple_accepted_candidates / unexcluded_support / missing_frame_estimate`；允许同分量多个原因，顺序按方法检查顺序固定。frame_results保留所有分量，无“取最好一个”或默默截断候选上限；输入固定80×80已给计算规模上界。非法两帧数量/时序属于合同错误，合法帧没有可用几何属于perception_unresolved。

后续独立评估先封存本模块输出再接真值。原拟议`object_initial_velocity_error_mps`必须标明比较的是“后向区间均值作为决策初速度代理”的误差，不能叫瞬时测速精度；另报`object_interval_mean_velocity_error_mps`时须对比原轨迹同一时间区间的中心位移/dt。两者无新增通过门，实际评估仍另审。相同原像素造成的相关误差未建模，不能擅自缩区间；未决项保留登记分母，不能记零误差。

本提案未建测试/运行/导出schema，也未产生服务器结果。拟议人工检查预算、零真实查询和零模拟限制见数值源；实现时须另绑定明确Git来源/检查清单与新回执，不能消费R4-3a的27项marker当b通过。此前证据按原字节复用；本轮METHOD/DATA新增文字不冒用原摘要认证。

<a id="r4-object-association-implementation-data"></a>

#### R4-3b实际值接口与工程回执（D-088，代码待审，无服务器产物）

本次实现D-087字段提案；上述历史提案JSON保持原字节，新的check配置绑定用户认可的原提案提交/摘要。具体算法、完整人工例和限制见[METHOD](METHOD.md#r4-object-association-implementation)，阶段入口仅在PLAN。不修改原v2记录/标签/查询格式。

白话：实际接口保存“这个估计是从哪些原像素算来、在哪一步不能继续”。例如中点范围没有交集时，候选保留空交集诊断而顶层位置为空；推头本体仍可独立保留。它不是失败时用真值补完整状态，也不是已有真实查询的产物。

- 实际函数为`associate_objects`及仅收单帧的`frame_candidates`。前者严格接`object_history.schema_version=spatial-history-r4-object-history-v1`及两帧列表，帧字段沿D-087白名单；后者需外层`source_index`整数0…120验证相对时钟，只读取给定帧。原图像的公共manifest/切片来源仍由后续接线认证，局部索引不是模型类别特征。
- `common_shape`只含四个已列外形/固定轴字段，`association_parameters`恰为segmentation和fit字典；布尔选项不能用数值0/1冒充，像素计数不能用等值float替代。结果版本、status及null规则与D-087相同，未测自由度不补值；顶层`robot_state`和对象位置、帧内位置各自拥有数组副本。
- `frame_results[].pusher_mask_pixels`保存行优先保守排除像素；投影未决时为null、components为空并有原因。每个component实际含`component_index / classification / reasons / support_pixels / outer_ring_pixels / top_height_interval_m / radial_tolerance_m / observed_axis_extent_m / position_m / position_intervals_m / support_weights / contour_transitions / radius_checks / interval_kind / assumption_refs`。支持数量和行列跨度可从完整像素表重算，未截断；图外外环像素保留其整数坐标用于解释裁剪。
- `contour_transitions[]`含`world_axis`（0=x、1=y）、两个前景/背景`pixels`及`coordinate_interval_m`；`radius_checks`含`max_foreground_radius_m / min_outer_ring_radius_m / plane_axis_extent_m`。相应步骤未执行时诊断为null/空列表；被拒候选的`position_intervals_m`可包含下界大于上界的空交集诊断，不能送入下游当有效区间。只有classification通过且该帧唯一的候选才填该帧位置；两帧都成立才填顶层位置/速度。
- `velocity_time_interval_s / interval_mean_velocity_mps / interval_mean_velocity_intervals_mps / velocity_kind`保留实际正时间差及独立端点传播；整体未决时速度null，原时间和逐帧诊断保留。`instantaneous_velocity_observed / dynamics_initial_state_ready`恒false，`orientation_xyzw / angular_velocity_radps`恒null；这与公开本体`robot_state.velocity_mps`测量字段不同。
- 新工程报告为`results/spatial_history_r4_object_association_v1.json`，kind=`r4_object_association_artificial_engineering_check`；receipt绑定12项来源、完整Git、32项实际测试身份/数量、失败/错误/跳过/预期失败/意外成功、elapsed_s、peak_rss_bytes和stage_bytes。started.json/tests.log/receipt.json的原文本、字节和SHA-256嵌入报告，failure.json若存在同样保留；不同报告不覆盖、已有失败/中断不重跑。verify/export不调用关联器或执行测试。
- receipt额外锁定`real_history_queries=0`以及新模拟/训练步/权重字节0；六项claims包括真实对象关联、公开几何、完整地图、物理预测、模型和长期记忆，全部false。逐命令300 s/512 MiB、阶段加报告8 MiB同D-087人工额度；旧27项和33/37项回执只供原职责复用，不认证b。

当前没有真实对象数组、关联缓存或服务器回执，不新增独立误差通过门。科学源码和检查只能证明所给人工值按合同处理，不能证明这些严格支持门在16条真实历史上足够；实际误差审计必须另绑定原产物并保留全部未决分母。

#### R4 v2设计与生成产物字段（D-084，服务器产物尚未生成）

白话：这些字段把“按哪个配置生成、哪个控制产生哪个标签”连起来。输入固定设计和真实记录，输出独立公共、标签、审计渠道；例如public第9槽对应私有c22及其首次轨迹，不能把文件名当模型输入。下面是已实现保存规则，不是已有结果或已通过的测试。

| 产物/字段 | 含义与读取边界 |
|---|---|
| `r4_family_design_v2.json` | version=sh04-r4-family-design-v2，64行parameters、band_pairs、camera、split/rank和去横移规范摘要；固定engineering_family_ids，确认行只有事前设计 |
| 私有`config.registration` | index与D-071完整base_template供精确派生校验，配置version=sh04-r4-family-v2；运行不靠模板赋予许可 |
| `public/W.json.gz` | schema_version=spatial-history-r4-public-family-v2，121条真实80×80 history、匿名九槽actions列表、共同goal；目录名W是编排元数据 |
| `model_input` | 验证完整公共记录后，按candidate_index及history_mode/history_cut_index选择一槽/合法历史，输出D-083源查询；选择器不进入模型特征 |
| `labels/W-cXY.json.gz` | 36份首次分支v2标签及trajectory大小/SHA绑定，任务/物理/可见性状态与实际评分一致；重放不增加监督 |
| `audit/W/primary-cXY`及`replay-cXY` | 原生数组、10001行轨迹、201传感帧、快照/实际接触/完成或失败标记；控制摘要和全部实际字节用于重放比较 |
| `family_result.json` | schema_version=sh04-r4-family-result-v2，4历史/36首次/36重放、36分支、72组数组摘要、成功矩阵和失败门；缺槽或完成回执不符均拒绝 |
| `branches[].contacts` | trace_rows、initial/terminal，以及positive_contact_pairs中的geoms、positive_steps、first/last/peak、peak_point_normal_force_n；同一步多点计一次，峰值为单点力，首末区间不表示连续接触 |
| `geometry.rows[]` | 原assessment加公开预测rejected_counts、candidate_count、incomplete_count、conflict_count；16查询/家族全部保留，零候选/零拒绝计数不推定通过 |
| 总报告`family_gates_passed/accepted/categorical_shortcut` | 区分家族门与类别捷径门，交集按固定数值槽0…8计算；交集全非空则总accepted=false；无效物理矩阵只作原始诊断 |
| `generation_ledger/export_resources/remaining_storage` | v1耗时、v1+v2耗时上界、1 GiB旧现场保留及7 GiB新共享池；不完整报告总生成耗时为null，不伪造预算核验 |

生成检查依赖同提交D-083成功回执、旧报告原Git来源与v1现场清单；全部代码、配置及依赖进入新来源绑定，不复用旧22项marker。新目录存在时只核验，不续算/覆盖/换样本。生成检查37项尚未运行，实际压缩和物理/E0/信息结果未定。

#### R4-2修订提案字段（D-082历史登记，实施补充见D-083/D-084）

**D-083补充：** D-082规格已获用户认可；本批只实现v2公共查询、预测、标签及评分值边界，物理数据与生成器仍未实现，原提案JSON不改。新入口与范围在独立`r4_contract_check_v2.json`登记，原字段表中未来物理产物仍为planned。

| 已实现v2值边界 | 实际字段与限制 |
|---|---|
| `r4_query_v2.from_public_query`输入 | `schema_version=spatial-history-r4-public-query-v2`＋history/controls/goal，history为已经按full/recent/prefix选择的原生80×80帧列表，controls为200条数值指令；拒绝旧无版本/64像素对象 |
| 列式查询输出 | `schema_version=spatial-history-r4-query-v2`＋history/controls/goal/domain_spec；history保留原RGB/深度/相机/本体值并增加depth_valid，相对时钟−12–0 s；不接实际未来状态 |
| `model_features`输出 | 先校验版本，再复制history/controls/goal/domain_spec；版本字段不进入特征，修改返回值不修改源对象 |
| `validate_candidate_queries` | 九查询＋外部事前登记的九条列式控制，逐位核对、拒绝重复，历史/目标/物性共用；此函数本身不提供文件/manifest认证或控制生成 |
| 预测、标签 | 预测`schema_version=spatial-history-r4-prediction-v2`；标签`schema_version=spatial-history-r4-labels-v2`。200步字段与v1语义相同，标签可见像素上限6400，所有原始物理行也检查上限；源版本不符拒绝 |
| 世界评分与汇总 | `schema_version=spatial-history-r4-scoring-v2`，世界固定9个注册位，缺失仍保留原错误/代价界；四世界、种子及家族层级不变，注册外/重复世界和跨方法真值变化拒绝 |
| 检查与报告（尚未运行） | `ops/spatial_history/r4_contract_check_v2.py`绑定19项来源及33项测试身份；新目录`/root/autodl-tmp/spatial-history/sh04-r4-contract-v2`，新报告`results/spatial_history_r4_contract_v2.json`。报告包含started/receipt/tests.log原文与摘要、完整人工查询/预测/标签和并列/缺失评分；失败/中断导出不填造通过或人工评分 |

白话：版本字段解决旧格式被误送入新接口的问题，输入合法值后输出验证结果或纯数值特征。例如给v1预测补一张旧64像素图并不能变成新查询；当前检查仍不能鉴定一张合成80像素图是否真正由模拟器渲染，这要靠后续来源绑定与生成审计。所有本批例子都明确标为人工合同例，不作为数据或模型结果。

白话：本节防止把新分辨率/九候选数据误当成旧四候选数据。输入是[修订数值提案](../configs/spatial_history/r4_repair_proposal_v2.json)，输出目前只有待实现的字段和版本边界。例如旧查询的64×64和4候选不能换个版本字符串就成为80×80和9候选；必须由新合同校验实际原生观察与全部控制。这不是已有新数据、通过测试或模型接入。

| 字段/产物 | 拟议值及读取边界 |
|---|---|
| 提案`status/*_authorized` | `proposed_not_executable`；实施/生成/训练/下载/确认均false。本JSON不是可运行的protocol或family config |
| `identity` | 64个ID与32/8/8/8/4/4划分保持，另登记dataset_version=v2；同ID的v1/v2不可作为独立样本或混用拟合，v1失败保留 |
| `geometry.band_pairs_in_order/pair_hash_keys` | 几何专用hash选择左右/左中/中右之一，实际枚举顺序为左中、左右、中右；近/远分别独立选择。带、侧微扰及实际XML只在设计/审计，不进公开查询 |
| `controls.candidate_keys` | c00…c22为固定3×3控制枚举，仅编排/私有标签使用；公开查询接数值控制，不暴露索引、世界符号或家族ID。实际四世界共享全部9条控制 |
| 公开`history/controls/goal/domain_spec` | 新`spatial-history-r4-query-v2`拟保留字段职责；121×80×80原生RGBD、最近2帧、每候选200段/20 s，物性和目标不变。内参/位姿必须来自实际新相机；不得上采样旧数组冒充原生80像素 |
| 预测/评分版本 | 新版本必须明确9个注册候选；并列、缺失、区间标签与逐家族统计按METHOD的v2提案校验。不能用v1测试marker认证或让旧4候选API静默接受9候选 |
| 私有原始数组 | 每家族4历史、36主分支、36重放。RGB为201×80×80×3 uint8；深度201×80×80 float64容器保留原float32值；状态/轨迹仍10001步含初态。时间/索引、源/解压字节摘要、全部原接触和无损分片职责保留 |
| 训练标签 | 每家族36份首次分支标签，重放不重复计入监督；共64家族的2304主分支仍按原家族划分，不能把候选增长当作独立家族增加 |
| 新目录及来源 | 拟议`/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v2`尚未创建；新code/config/design/sensor/query/score摘要及真实新检查回执齐全后才有执行条件；原v1目录只读保留 |
| 资源及停止字段 | 仅拟议首4家族144首次+144重放一次；原始数组约1,405,018,944 bytes/家族，不等于压缩后磁盘占用。每家族384 MiB及总预算是硬停止条件，压缩足够与实际配额尚未验证 |

该提案读取了首4个model_train家族的开发失败来修订分布；这段适应过程须随未来报告保留。确认家族仍只有既有静态ID/划分，没有确认观察或标签；新提案不解封确认，也不把三位置带设置当作通用连续几何泛化的证据。

#### R4-2实现字段（D-081，代码待审；物理数据未生成）

白话：以下文件将固定输入和实际证据连接起来。输入是64行事前设计中允许执行的4行，输出三份渠道清单、逐家族判定和整批回执。例如`public/r4`概念上只含过去帧，实际路径为`execution/r4-39/data/public/LL.json.gz`；该路径和LL标记留在外层，不返回模型。它不是把场景配置或未来物块状态写入公开查询，也不表示当前服务器已有这些文件。

| 文件/字段 | 内容及读取边界 |
|---|---|
| `configs/spatial_history/r4_family_design_v1.json` | 已物化的64行静态配置，`index/family_id/split/split_rank`仅编排；`parameters`为D-079连续值，`camera`含路径/语义观察下标/诊断前缀；`normalized_design_sha256`核验去平移后不重复。不是实际物理数据manifest |
| `design.json / started.json / check_receipt.json` | 服务器核验静态清单后保存原规范值、代码/Git来源、既有R4-1/E0报告、环境锁与22项检查的真实身份和退出；缺检查回执拒绝run |
| `execution/release.json` | 用户审过的完整code commit、明报剩余新增数据配额、采用的首批资源和worker数。只放行固定4家族；不能用`df`可见容量替代租赁额度 |
| `data/public/W.json.gz` | 沿用公开记录的`schema_version/history/actions/goal`；解压后经原公共校验和R4-1查询转换。121×64×64原RGB/米制深度、真实相机/本体、4条200段控制及共同目标；没有家族/门参数/未来运动 |
| `data/audit/W/history_prefix.jsonl.gz` | 每次实际捕获立即追加`frame_index/observation/visibility/snapshot`；私有前缀审计，中断后已写原始帧保留。完整时与公开帧相同源，不是新增历史样本 |
| `data/audit/W/world.xml / snapshot.json / observation.json` | 实际独立几何、完整决策快照、121帧原分割计数和观察不改状态检查；首/近/远/近期PNG同目录。history失败另存`history_failure.json`及实际快照 |
| `data/audit/W/primary-A/`与`replay-A/` | 原始trace、补足可见性的trajectory、visibility、实际末快照、原RGB展示与私有全景图、rollout评分/文件摘要；前者与后者各16份。每次完整阵列按原字节/接触/任务事件比较，不把重放作独立样本 |
| `*.npy.gz` | **R4专用行流，不是标准NPY**：gzip内第一行JSON为`version=r4-array-v1/shape/dtype`，随后连续C-order小端原数组行。integration是10001×完整状态宽度float64；RGB是201×64×64×3 uint8；depth是201×64×64 float64；time/index分别201项float64/int64。原生float32深度无损扩宽，禁止将此说成原传感器提供64位精度 |
| `array_storage.*.raw_bytes/raw_sha256` | 每份数组解压后的实际长度/原始字节摘要、shape/dtype；同时保留压缩文件bytes/sha256。CRC（Cyclic Redundancy Check，循环冗余校验）验证压缩流损坏，SHA验证来源；两者都不证明物理正确性 |
| `data/labels/W-A.json.gz` | 独立`labels`为R4-1的200步位置/区间接触/可见像素/整段成功/有效性，另绑定实际trajectory文件摘要。只提供首次执行的16条监督，重放不重复训练标签 |
| `data/audit/geometry/` | 4世界×4模式的无损公共恢复输出、`public_seal.json`及私有`evaluation.json`；由新实际帧重算，不用旧E0通过填充新结果 |
| `public_manifest.json / labels_manifest.json / audit_manifest.json` | 各自仅列对应渠道的相对文件名、字节数、文件SHA；渠道隔离由读取接口实现，文件夹不代表操作系统访问权限 |
| `data/audit/family_result.json` | 全部分支原assessment、重放差异、121帧信息分组、观察/E0检查及失败、原/压缩存储字节；`accepted`是工程门，不是模型有效性 |
| `complete.json / history_complete.json` | 同步函数完成与已保存原文件的绑定标志；没有启动一个新进程，不冒充每个分支都有独立OS退出回执 |
| 家族`launched.json / exit.json / run.log`、`processes.json` | 真正的家族子进程PID、退出、未启动/缺退出、取消及资源；每家族内部顺序执行，其他家族最多4路并行。失败停止新派发，已获完整成功回执的计算不自动重跑 |
| `summary.json / run_receipt.json / run_receipt.pending.json` | 全4家族结果与类别捷径/资源预留、完整来源/manifest和退出；pending未通过收尾门不得当成功。首批通过仍不授权其余60家族或确认 |

固定阶段目录`/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v1`，小报告`results/spatial_history_r4_engineering_subset_v1.json`。报告保留静态清单、来源、全部家族判定与渠道manifest、进程退出及失败日志尾；完整图像、积分和轨迹在服务器。没有导出完整数组不等于没有生成数组。已存在失败/中断目录只允许只读检查和诊断导出，不覆盖、补造成功或自动另起同批。所有候选、原始接触、失败行及无效分母保留，不依据结果替换样本。

### SH-04 新小试数据与模型权限（proposed，尚未生成）

**D-068：本节v1数据量、划分和采集路径进入待修订状态，不能据此生成80对或确认16对。** 旧SH-03仅保留作工程/公开输入审计。新主场景先证明单帧证据不足、跨视角历史可区分、左右类别不决定全部后果；几何—控制组合和证据时序需重新登记。新数据字段/样本数/预算均未冻结，不因本次文献核查生成新数据。方法依据见METHOD，唯一执行顺序见PLAN。

白话：现有16对都已看过并用于场景修订，不能拆出“未见测试”。新小试输入固定场景参数登记，输出分别用于训练、选参和最后确认的完整家族。例如同一墙距离/起点的13帧与23帧历史必须同组，两世界及两动作也不能跨组；这不是把同一轨迹的帧随机打散后声称泛化。

拟固定48个新物理设置家族，每个家族两种历史长度，合计96对、384条不同控制分支，另做384次独立重放。家族i=0…47，wall_y_m=0.522+0.0036×i（范围0.522–0.6912 m）；start_x_m由UTF-8字符串`sh04-pilot-v1:{i}`的SHA256前8字节按big-endian无符号整数u映射为−0.02+0.04×u/(2^64−1)。i用无前导零十进制。此规则只生成物理输入参数，不生成答案，也不根据模拟是否通过重新抽样。运行前服务器导出完整48行清单与摘要，固定其浮点表示；当前不生成场景或探看确认结果。

i mod 6为0/1/2/3的32家族归train、4的8家族归validation、5的8家族归confirmation；每家族同时包含history_arc_samples=13和23。先生成train＋validation共80对；confirmation的16对在全部算法、权重、超参、评分和数据manifest锁定并获得该阶段运行授权后才生成/评估。确认失败不补样、不剔除，也不能因其结果回改已锁方法。若训练/选参80对中有不满足物理合同的例，保留并停止进入训练，先处理数据协议，不换为“好样本”。

这里家族是同一具体物理初态/布局参数的所有相关分支和观察版本；SH-03原16对及其v1/v2仍整体作为已见工程家族，全部排除训练与确认，不给旧case换编号复用。同一物理模板在新各组共用，因此仅称“模板内参数插值小试”；参数表是固定设计，不视为48个独立随机现实场景，8个确认家族不支撑总体泛化置信区间。

首轮仍使用v2墙横坐标、固定物块/机器人/屏、两候选控制和64×64渲染；不同时扩动作分布、纹理、物体形状或开放世界。原`pair_contract.py`仅支持development，不修改其旧语义：后续适配器应使用新外层split manifest管理角色，旧内部成对记录保留作机械审计，不能把旧development字段冒充新的隔离检查。新的跨split家族/数值初态摘要去重、公开输入提取器和确认封存均须实现测试后才可运行；当前还不存在这些能力。

| 数据通道 | 主模型/部署读取 | 监督、审计与例子 |
|---|---|---|
| 历史RGB/深度、相机、本体、过去指令 | 允许；按S/L/R窗口先截取再编码；M方法读完整历史 | 例如从首帧深度反投影墙表面，不输入墙的真实坐标 |
| 未来拟执行控制、共同goal | 允许；动作输入只用速度/持续时间 | decoder只用对应预测时刻之前的控制前缀，不读真实末端未来运动 |
| 未来物块xyz和接触0/1 | 不允许 | train用于损失，validation仅选参，confirmation仅最终评分 |
| 墙坐标、完整XML/快照、实例分割、可见像素 | 不允许 | 物理审计或单列真值诊断；像素派生地图不等于直接读取这些字段 |
| 家族/世界/候选编号、split、路径、hash | 不编码进特征 | 加载器/审计保留来源，模型接口剥离；候选由实际控制数值区分 |

时间统一为相对决策时刻，历史≤0、预测为0.1…4.9 s，padding附显式有效mask；不把不同历史长度的绝对模拟时间误当未来对齐。所有公开图像/深度的缩放参数、有效mask和像素中心坐标须绑定来源；未来真值改变不应改变公开特征。公共输入与标签分文件/接口保存，预测进程不直接打开原paired JSON；当前旧model_input只可供离线提取审计，不能称为已完成在线隔离。

第一个可执行批次拟只读已验收SH-03/v2的16对，验证公开提取、DINO特征与原图对应、成对近期特征相同，并用固定1近邻检查首帧左右布局信息。邻居按另外三个wall_y组的首帧归一化展平patch特征欧氏距离选，留一wall_y组验证，标签只在独立诊断端读取；目标准确率≥0.95，近期成对特征必须相同。这个门仅排除编码/读取明显失效，不证明连续墙位置可恢复、未来可预测或模型有效；不据此训练DINO或宣称独立确认。若失败保留结果，先诊断，不静默更换编码器。

新产物预算6 GiB覆盖公开图像、必要原始轨迹、特征缓存、checkpoint及小报告，另6 GiB覆盖新环境和权重；按各阶段真实大小核验，不能把底层df容量当租赁剩余额度。以SH-03每对约33 MiB作粗估，96对原始记录约3.1 GiB，实际可能变化；重复RGB历史/特征应按内容摘要去重复用，不重渲染原16对、不删除旧25 GB CPMT结果。未来encoder权重和逐例特征放数据盘，不入Git。

### SH-03 数据登记与读写边界（实现待服务器验证）

v2补充（服务器验证pending）：当前登记为`configs/spatial_history/development_audit_v2_wall_clearance.json`，增加`wall_center_abs_x_m=0.33`（米，墙中心横坐标绝对值）和`prior_development_audit_sha256`（已核验v1失败报告的audit摘要）。白话：输入旧失败来源和唯一新墙位置，输出可追溯的新场景XML；例如实际墙位置为−0.33/+0.33 m，但这一真值参数不作为模型特征。它不是候选动作、物块未来变换或可调搜索范围。

当前新目录为`/root/autodl-tmp/spatial-history/sh03-development-v2-wall-clearance`，新报告为`results/spatial_history_development_audit_v2_wall_clearance.json`；旧v1目录/报告及登记文件保留。新12项检查、全部16例、64条首次分支及64次独立重放产生新绑定，预算仍为新增2 GiB、按案例边界检查。case_id/family_id/split和原16行参数相同，用版本、实际配置/XML与回执区分；两版本不是32个独立场景，不拼接成训练/确认划分。check先核对原SH-02通过报告和v1失败报告的摘要/原Git来源，旧通过状态不用于替代v2验收。以下路径和8项计数描述原v1结构；v2沿用内部文件结构，check中改为12项。

白话：新增登记表解决“到底生成了哪些案例、失败是否被换掉”的问题。输入固定16行参数，输出每行对应的原始数据和审计记录。例如sh03-00失败时，其轨迹和失败项仍可导出；这不是训练集筛选，也不会把场景参数作为模型特征。

登记文件为`configs/spatial_history/development_audit_v1.json`，字段`wall_y_m/start_x_m/history_arc_samples`分别表示挡板中心纵坐标、物块与推杆共同横向起点、历史绕行采样数；单位米/米/帧。`unique_branches=64`是不同控制分支，`replay_branches=64`是独立一致性复核次数；`output_budget_bytes=2147483648`为新产物预算，按案例边界检查，单个正在运行案例可能使预算越界，越界后拒绝启动下一例并判批次失败。它不是服务器租赁配额；系统df的底层空闲容量不能替代用户数据盘50 GB额度。

默认目录`/root/autodl-tmp/spatial-history/sh03-development-v1`中，顶层`started.json/environment.json`固定代码、登记表和环境；`check/`存新8项检查与回执。每个`sh03-XX/`有独立启动、日志、退出回执和完整文件摘要；`data/input_config.json/input_model.xml`是实际输入，`data/raw/`保留原SH-02生成器产生的世界XML、完整快照、原始像素/深度、逐物理步轨迹、反序重放及PNG，`data/pair.json`只规范化顶层pair_id/family_id/split，原始pair仍单独保留，`data/audit.json`记录13项检查与失败列表。

规范记录统一`family_id=sh03-fixed-factorial-development`、`split=development`。原生成器的code/config摘要保留，新适配器、登记表和当前合同另由SH-03回执绑定；不把旧生成器的固定工程编号当作16个不同编号。模型仍只能经`model_input`读取过去RGB/深度、相机与机器人历史、拟执行速度和目标；登记参数、编号、XML、分割可见像素、完整快照和实际未来轨迹不得进主模型输入。未来物块位置/接触只作后续监督或评估，其余真值只做审计或单列特权诊断，SH-03本身不训练。

`results/spatial_history_development_audit_v1.json`包含批次规范摘要、来源/环境、新测试、16例逐项状态、各例文件manifest、8张原PNG预览及首次分支接触过程摘要；失败保留日志尾部，未运行明确标not_run。完整数组仍在服务器；没有把数组嵌入小报告不等于没有生成。已封存回执的案例只核验复用；有启动但无退出回执的中断现场须先诊断，不覆盖或自动重跑。

第一批只接收 `development`（开发）记录，不创建训练/确认/test 划分。JSON 中保存小样本的解码后像素与数值；这是可读的审计交换格式，不承诺后续训练直接用 JSON 存大数据。首个文件 `data/fixtures/spatial_history/manual_pair.json` 是人工指定接口例子，2×2 像素无物理含义，`simulator=not_run`、来源 hash 的全零值是占位；服务器回执会另记该文件真实摘要。不能把它计入16–32对物理案例，也不能把示例中的后果称为发现。

白话：这个合同解决“模型不知不觉看见答案或两组近期输入不同”的问题。输入两个世界的完整审计记录，输出结构诊断与只含过去传感器信息、拟执行控制和共同目标的查询。例如未来物块位置只在 `branches.future`，提取后不出现在模型输入里；这不等于证明传感器记录真实或模型已懂遮挡。

| 字段 | 定义/单位 | 模型权限 |
|---|---|---|
| `schema_version` | 固定 `spatial-history-pair-v1`，严格拒绝未知/缺失字段 | 仅审计 |
| `pair_id / family_id / split` | 成对记录编号、关联场景家族、仅 `development` | 仅审计；编号不作特征 |
| `provenance` | `kind` 为手工夹具或模拟导出；`simulator` 名称/版本、非负整数 `seed`、`code_sha256/config_sha256` | 仅审计；hash 声明需后续产物核验 |
| `recent_frames` | 两个世界末尾完全相同的帧数；必须另有早期帧 | 仅加载器截取短历史，不返回模型 |
| `control_kind` | 固定 `ee_velocity_world_mps`：世界坐标机器人末端速度，非物块位移 | 运行合同常量 |
| `goal` | `center_m` 三维位置、正的 `radius_m`，两世界/两动作共用 | 可用；当前只是查询条件，未实现评分器 |
| `actions` | 恰好两个不同候选；每个候选为 `{duration_s, ee_velocity_mps}` 序列，三维速度的 z 为0，时长为正且候选时间网格相同 | 仅返回所查询候选的数值；不返回候选编号 |
| `worlds[].history` | 严格递增时间的真实过去帧；两世界长度/采样时间/相机/机器人信息一致，只有早期视觉可不同 | 全历史或末尾近期片段 |
| 帧 `rgb / depth_m / width / height` | 按行展开 RGB，0–255整数，长度宽×高×3；深度为米，长度宽×高，0表示无效，禁止负数/非有限数 | 可用；模拟器后续不得将实例标签混入像素 |
| 帧 `camera_position_m / camera_xyzw / intrinsics` | 相机到世界的平移与单位四元数；内参 `[fx,fy,cx,cy]` 以像素计；相机局部 +x 向右、+y 向下、+z 向前，世界 +z 向上 | 可用；首轮理想定位必须明确声明 |
| 帧 `time_s / ee_position_m / ee_velocity_mps / previous_velocity_mps` | 从片段开始的时间；当前末端位置/速度及到该帧为止前一间隔的已施加指令；首帧前指令为声明的初始条件 | 可用；不是未来实际运动 |
| `initial_state` | 决策时刻物块和末端的位置/速度，两世界相同，末端状态与末帧一致 | 特权审计；不输入物块真值位置 |
| `hidden_obstacles` | 遮挡区障碍的轴对齐盒，`[min_x,min_y,min_z,max_x,max_y,max_z]`，单位米 | 特权审计；可独立用作上限诊断，不进主输入 |
| `branches` | 与两个候选按索引一一对应；`base_snapshot_sha256` 在同一世界内必须相同，跨世界允许不同 | 特权审计；仅核验声明，不证明已真实克隆 |
| `branches[].future` | 每段控制结束时的 `time_s / object_position_m / contact`；SH-02具体接触定义见METHOD，每0.1 s间隔内任一物理步物块与墙/屏有正力接触 | 只作监督/评估，不包括地板支撑或机器人接触 |

未知字段、非有限数、布尔值冒充数值、时间错位、缺分支、重复候选或不同近期输入均报 `ValueError`。`audit_dataset` 拒绝重复 pair_id；当前未支持多 split，因此不宣称已经完成未来训练/确认划分审计。

模型输入唯一允许的顶层字段是 `history / controls / goal`，所有数据深拷贝。`model_input` 是离线审计/提取函数，它为校验配对会读取审计记录；在线模型只消费提取结果，不能直接加载原 paired JSON。未来部署读取器仍 planned。与旧 query 生成的区别是这个模块不生成观察、不根据答案生成特征；但上游来源真实性仍需模拟器审计。

物理来源在SH-02固定为MuJoCo 3.3.7；生成代码已实现，实际产物仍待服务器运行。手工验证器不承担物理认证，独立工程套件检查下面的来源记录。

### SH-02 原始物理记录（实现，实际生成 pending）

白话：这一层解决“JSON里的真值究竟是否由同一初态真实执行得到”的问题，输入场景XML、固定控制和相机路径，输出原始图像、快照和逐步轨迹。例如可以加载原XML与决策快照重新执行左推，并比较全部物理结果和传感器；这不是训练集或模型可直接打开的公共输入文件。

| 产物/字段 | 内容与访问边界 |
|---|---|
| `config.json / world-N.xml` | 完整配置与两个实际场景，保存控制器、物理和渲染参数；仅来源审计。seed=0是固定夹具标识，本版无随机数生成 |
| `world-N-snapshot.json` | `xml_sha256 / state_spec / state`；完整积分状态，浮点JSON往返保留双精度值。snapshot摘要采用模块的规范JSON序列化，与文件内容一致；仅审计/重放 |
| `world-N-record.json / pair.json` | 每世界独立产生的历史与原合同双世界记录；含RGB/depth解码后值、公开本体/相机信息及私有初态/布局/未来。公共模型只接收旧 `model_input` 提取的 `history/controls/goal` |
| `*-trace.json` | `base_snapshot_sha256 / future / trace / end_snapshot`；trace每0.002 s保存time、qpos/qvel、物块位置与倾角、实际末端位置/速度、命令、执行器力、接触对象/距离/法向力、障碍接触时可见计数。全部特权，不进模型；用于监督、重放和诊断 |
| `*-sensors.npz` | 每0.1 s未来真实传感器数组：`rgb[49,64,64,3]` uint8、`depth_m[49,64,64]` float32；仅未来监督/评估。保存原始数值，不是视频生成结果，当前训练未实施 |
| `*-replay-trace.json / *-replay-sensors.npz / *-replay.json` | 新模型/数据从磁盘快照按反序重放的完整结果和期望/实际摘要；不同结果也原样保留，不只存equal布尔值 |
| `evidence.json` | 历史物块/推杆/墙/屏可见像素计数、观测不变性、非布局初态一致性、重放一致性、每分支接触/遮挡/高度/倾角/力摘要；均仅工程审计 |
| `*-early.png / *-recent.png / *-final.png` | 两世界早期/近期及四分支最终真实RGB预览；没有后处理增强。报告内嵌无损PNG用于本地查看，不冒充完整原始图像/轨迹下载 |
| `started.json / environment.json / tests.log / tests-result.json / receipt.json` | 启动来源、环境、实际测试输出/计数、子进程退出码与完整文件摘要清单。子进程异常或崩溃保留已写产物，不能宣称未写完的轨迹完整；失败报告仍可导出 |

`pair.provenance.code_sha256` 是物理适配器实际文件字节摘要，`config_sha256` 是适配器规范序列化的 `{config,xml模板字符串}` 摘要；完整模块/测试/文档/依赖与旧验收前提另由SH-02 receipt绑定。文件总manifest为实际磁盘字节摘要；原始数组一致性另按数组内存值摘要核验，避免压缩容器时间字段干扰。

深度为相机轴向距离，远裁剪处可记录约20 m的背景深度；不把背景冒充实测表面。相机/深度/机器人本体为理想模拟传感器，不能称真实噪声条件；实例身份、物块真值、隐藏墙几何和未来实际机器人运动均是私有数据。主对照可用的历史像素/深度/位姿信息必须一致，地图上限如使用真值另列。

本批只有一对固定工程世界及独立重放，不创建训练/确认/test文件。记录失败时同样保留完整已生成样本；后续扩至开发审计须先审查本模块，不能仅因工程检查通过自动扩大数据或训练。

SH-02失败轨迹只读诊断（已实现并导出v1证据）：`ops/spatial_history/contact_diagnose.py`读取已经保存的四条首次分支，核验原报告/receipt、原Git提交字节及全部已登记产物摘要，再输出 `results/spatial_history_contact_diagnostic_v1.json`。它解决原报告只有终点、无法判断推杆何时接触或离开物块的问题；例如输入一条2450步轨迹，输出49段控制末尾的实际机器人/物块位置及每段连续推杆接触的起止和相邻状态。这不是重新模拟、推断未记录接触或改变接触阈值，也不向模型开放这些特权数据。

诊断字段 `control_endpoints` 是每段控制结束的已有轨迹行；`object_pusher_episodes` 是原正力接触记录中连续出现object–pusher的时间段，保存first/last/previous/next、物理步数及最大法向力，短暂断开如实分段；`contact_pairs` 按接触对象对统计出现步数（同一步多个接触点只计一次）、最大法向力与首次/末次状态；`object_axis_ranges_m` 是整条原轨迹各坐标最小/最大值。最小中心距离是两物体中心的三维距离，不是几何表面间隙。报告同时绑定原报告、原receipt、原trace、诊断源码及本文摘要；仅保存衍生小报告，不写回失败目录。更新后的DATA不能由旧physics回执认证；诊断明确对照原提交读取旧来源，新说明独立绑定。

v2常规物理导出新增 `contact_process_by_branch`：用首次分支trace路径作键，保存其SHA256、每段控制末尾实际状态、每种接触对的起止/步数/最大力、物块全程各坐标范围与 `object_pusher_episode_count`（连续推杆接触段数）。它解决再次失败还需单独同步诊断代码的问题；输入已绑定原trace，输出可直接定位接触丢失的摘要，例如推杆继续走而物块已停。省略完整接触段列表，保留原trace可复算；不重跑物理、不改变标签或向模型开放真值。配置文件名保留physics_v1接口名，但version/model已标v2-flat-pusher，原球头配置只能通过原提交或对应run中的XML复现，不能冒用当前配置。

## 历史来源与字段（D-059/D-061 已暂停的接入研究）

以下 ARKitScenes/ADT 已有画面筛查保留，暂不继续其完整接入；这些数据不能自动替代机器人控制与成对重放。后续若复用仍按各自来源与用途限制，旧测试封存不变。

本文件只维护来源、字段、split 和适配验收；执行步骤及当前指针见 [PLAN.md](PLAN.md)，方法见 [METHOD.md](METHOD.md)，实际结果见 [EXECUTE.md](../EXECUTE.md)。新适配仍为 planned，候选来源不是已经冻结的数据。

## 数据类型

1. 工程夹具：少量人工可审计世界，用于执行/接口检查，不估计真实事件发生率。
2. 重构 M1：按 D-059 先审真实观测接口，再确定受控记忆和错误条件；旧程序化 paired worlds 仅作历史来源，不强制新协议继续使用同一生成器。
3. M2/M3：实采或明确声明的模拟具身序列及独立外部来源；正式来源尚未冻结，同源开发样本不能冒充未见验证。

不增加第二个非具身应用领域。

## 旧 M1 字段与实采适配边界

world_seed、paired_group_id、split、observations、poses、actions、visibility、prior world、candidate programs、oracle equivalence、future evidence、protected IDs、generator version。

上列是原程序化/模拟器合同字段。D-058 的实采适配须改用真实 scene/sequence/frame 标识和采集来源；没有 world_seed、动作日志或唯一参考事务时显式标为不适用/不可用，不虚构对应字段。旧记忆与候选由在线系统形成，不从标注完整图转换得到。新字段设计见 METHOD.md。

online export 物理删除 future、oracle 和 hidden state。

## Split

paired group、world seed、asset family 和同源轨迹不跨 split。validation 选择 horizon/K/weights/checkpoint；test 在 freeze commit 后一次性正式运行。

现实数据无法唯一判断 transaction 时保留 ambiguity（不确定性）/多假设，不把模型判断当 ground truth。只有满足 D-025 保守状态相等条件才使用 equivalence；不能因暂时分不清或未来投影相似而合并不同世界。

## 来源候选

以下来源按数据所能支持的证据比较，尚未冻结正式组合。模拟器建议源于 D-028；实采优先考察与信息边界按 D-058/D-059。查看开发数据后再确定具体版本、规模和预算，不由本页预设。

**结构与对象共同筛查（D-061）：** 观测必须覆盖环境结构逐渐纳入的机会，不能只按可移动对象及身份标注丰富度排序。输入连续移动相机帧和姿态，输出可人工审查的“旧结构重见、已知结构范围扩大、转角/门口揭示相连新区域、对象变化”案例；例如转角前后共有一段墙/地面时，应能检查新片段怎样接入旧记忆。这不是要求数据集已经提供我们的结构 latent 或事务答案；这些由模型与独立审计协议分别形成。

ARKitScenes 的[采集协议第 3.1 节](https://arxiv.org/html/2111.08897v3)明确采集天花板、地板、墙面及家具，但多数 scene 是单个房间，采集期间尝试保持环境静止。因此它可支持静态环境中随着相机移动而扩充已知结构；不能据此保证连续“直走廊→拐角→另一段走廊”或跨房间轨迹。ADT 的[官方概览](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset)描述了含客厅、厨房、餐厅、卧室的公寓和连续佩戴式活动，是跨区域结构案例的优先核查候选；两个空间及特权深度的限制仍在。两者均不是机器人本体采集，先用于移动相机离线回放；指定的走廊片段、结构连接真值与遮挡覆盖尚未逐帧确认。

首批样本必须保留旧/新结构共同可见的时间段，不能将独立房间扫描随意拼成自然连续轨迹，不能用全场景重建先初始化记忆。Bonn 箱子序列只作对象变化/遮挡补充候选，不能单独满足结构增长的数据审查。

### 模拟辅助候选：ProcTHOR＋AI2-THOR

白话：ProcTHOR 提供公开的室内房屋场景，AI2-THOR 让相机/机器人在里面移动和观察；输入场景与动作，输出观测和环境记录。例如绕到椅子背面、离开后重访，检查该绑定旧节点还是修改位置。它不是下载即用的 CTL 事务训练集。

- ProcTHOR 提供程序生成的可交互房屋；[官方介绍](https://procthor.allenai.org/) 与 [ProcTHOR-10K 仓库](https://github.com/allenai/procthor-10k)。
- AI2-THOR 提供 RGB、深度、分割及 agent/object 元数据；[观测和状态接口](https://ai2thor.allenai.org/ithor/documentation/environment-state/)。对象操作需按具体版本验证，不能假定所有资产都能自由移动/创建。
- 拟覆盖：换视角重见、首次揭示、物体移动、遮挡但未消失、重访修订；首次看见不等于物理上刚创建。
- 尚缺：版本锁定、许可核查、轨迹与变化事件生成、样本筛选、身份对照审计、数据导出、候选世界的视觉特征投影。
- 输入边界：GT 实例 ID、不可见对象位置、完整场景图和未来只能进入独立审计/允许的离线监督；在线 memory 必须来自截至当前的观测。即使先用分割轮廓，也要移除跨帧对象编号/固定颜色暗含的身份答案。

### 实采接入候选：3RScan

白话：同一真实房间在不同状态下被重复扫描，输入不同扫描中的 RGB-D 和相机位姿，评估旧对象对应和变化。例如重访后原物体换了位置，旧记忆是否得到正确修订；它不是完整记录搬运过程的连续机器人动作数据。

- 官方提供标定 RGB-D、相机位姿、跨扫描对齐、实例对应及变化对象信息；[官方仓库](https://github.com/WaldJohannaU/3RScan)、[项目与获取入口](https://waldjohannau.github.io/RIO/)。
- 适合候选用途：跨重访身份与位置修订的现实验证；不假定它覆盖所有 CTL 事务或有完整动作日志。
- 获取流程、数据许可和实际字段覆盖尚需核查；代码仓库的许可不自动等同于数据许可。
- 跨扫描对齐/实例对应属于需要声明的参考信息；若固定 pose 条件使用参考对齐，必须对所有方法一致开放并明确 oracle 条件，不把完整重建泄漏进在线旧世界。
- 不能从缺少标注直接推断对象消失；歧义/漏标/无法建立的事务应保留并报告。

## 在线、教师与审计字段

以下为设计字段，不是已经实现的导出 schema。在线、教师与审计数据使用独立文件与读取接口，在线接口只接受明确列出的字段；同一文件里删掉一个 reference_spec 不足以排除上游派生泄漏。

| 通道 | 拟议字段及来源 | 边界 |
|---|---|---|
| 当前观测缓存 | frame_id、timestamp、region_local_id、appearance、region_support、depth、camera_pose、calibration、source_manifest | 区域编号只在当前帧内寻址；特征来自冻结前端。深度/位姿分别注明 sensor、estimated 或 privileged；缺失显式标明，不用对象真值补齐 |
| 在线旧记忆 | memory_node_id、version、evidence_refs、geometry、lifecycle、descriptor_refs | 仅从此前已提交版本和当时可用观测形成；不从全序列重建或真值图初始化 |
| 离线教师证据 | future_observations、visibility、时间窗及分支推进规则 | 只在训练时用于比较真实执行后的候选世界；不照搬 M1 的正确后续事务重放，推进/对应规则须另行固定且不读取正确身份 |
| 独立标注/审计 | instance_id、对象真值轨迹、跨扫描对应、参考标签 | 默认只供审计和评价；如用于有标签训练须另列标签量与 A–E 公平边界，不能作为在线检索输入 |

白话：上述分离把“机器人当时看到了什么”和“研究者后来知道答案是什么”分开。输入是一帧观测及元数据，输出是在线可用字段与独立审计记录。例如同一把椅子的跨帧真值 ID 可用于评价是否认对，却不进入 appearance；这不是删除所有真值，也不声称数据集提供的 pose/depth 天然满足在线条件。


## 数据适配验收规格

### 公开实采接入的来源比较（proposed；延续 D-058/D-059）

| 来源 | 可用于什么 | 必须处理的限制 |
|---|---|---|
| 3RScan | 已有提案中的标定 RGB-D、位姿及同场所变化后的重访，优先考察身份/位置修订的小样本接口 | 跨扫描有采集空档，不能虚构连续搬运轨迹；实例对应/对象变换只供独立审计。跨扫描参考对齐若用作固定 pose 条件须明示特权来源，不从完整重建初始化在线旧记忆 |
| Aria Digital Twin（ADT，Aria 数字孪生数据集） | 实采眼镜视频中的动态活动，用于连续观测和对象变化的候选来源 | 官方同时提供实采与合成图像，以及真值派生深度、设备/对象轨迹；它们不能混称传感器输入。只有两个场所且动态对象共享，不足以仅靠随机序列切分声称广泛的未见场景/对象泛化 |
| Bonn RGB-D Dynamic（波恩动态彩色深度序列） | 实采移动/放置/移走箱子等连续序列；输入彩色深度帧及相机位姿，先输出可审查的变化案例，例如箱子移走后旧位置不应继续占据 | 官方列出相机位姿与静态环境点云真值，未列出完整对象身份轨迹标注；正式身份/证据归属评价需另做独立标注。短序列和少量环境不能代表长期、多场所泛化，也不预设所有变化都能唯一判断 |
| ARKitScenes（移动设备室内彩色深度扫描） | iPad 实采 RGB-D、相机轨迹、标定和家具框；输入多视角扫描，检查旧节点在绕行后能否重识别 | 多次采集不等于物体确实发生变化，不保证有跨扫描身份/变化标签；适合观测与几何适配候选，不能单独替代动态修订证据。激光扫描高质量深度、完整 mesh 与全场景框须和移动设备观测分开 |
| BEHAVE（人与物体交互数据） | 多台 RGB-D 相机记录搬动等交互，并提供人/物体注册与相机位姿；可提供真实物体变化的辅助案例 | 外部多相机视角与具身移动相机不同；不把它直接当完整 M2 主来源，不把人体姿态/接触任务扩为第二研究领域 |

白话：这项比较解决“公开数据哪部分真正提供新观测、哪部分其实是答案”的选源问题。输入是官方字段说明，输出是接入候选及来源限制。例如 3RScan 的 RGB-D 可形成当前观测，跨扫描对象 ID 用来检查记忆是否认对；它不是已经选定或下载的数据，也不保证任何来源覆盖全部事务。依据：[3RScan 官方字段](https://github.com/WaldJohannaU/3RScan)、[ADT 官方概览](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset)、[ADT 文件及真值格式](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset/data_format)（2026-09-11 查阅）。具体观测/记忆/教师/审计接口及干预检查见 [METHOD.md](METHOD.md)。

访问与用途核查（2026-09-11，来源筛查，不是正式数据冻结）：

- **3RScan**：[官方入口](https://waldjohannau.github.io/RIO/)要求 Terms of Use 表单；用户没有表单要求的机构/导师信息，不能把申请成功当现有条件。官方 [FAQ](https://github.com/WaldJohannaU/3RScan/blob/master/FAQ.md)进一步说明仓库 split 列表仅列 reference scans；旧清单的 385 个 ID 应理解为该训练 reference 列表，关联 rescans 仍需元数据，不能靠 ID 前缀猜测。
- **Bonn**：[官方页面](https://www.ipb.uni-bonn.de/data/rgbd-dynamic-dataset/index.html)有直接分序列下载，不需填写机构/导师表单。移动遮挡箱子、放置非遮挡箱子、移走非遮挡箱子三个官方 ZIP 的未认证 HEAD 均返回 200，Content-Length 分别为 320845314、400775291、271656752 字节。对第一个 ZIP 仅读取 217106 字节目录元数据：590 个 RGB PNG、589 个 depth PNG，以及 rgb.txt、depth.txt、groundtruth.txt；这不证明时间对齐或数值质量，未读取图像/深度载荷、未取得完整文件 SHA256。页面要求研究引用，未见独立数据许可证文本；正式使用/再分发范围仍需记录清楚，不能套用 TUM 的许可。
- **ARKitScenes**：[官方下载说明](https://github.com/apple/ARKitScenes/blob/main/DATA.md)允许按 video_id 和文件类型下载，官方脚本使用公开 Apple URL；示例训练视频 47333462 的相机轨迹 URL 未认证 HEAD 返回 200。后续首批画面核查已读取该视频的 12 张 RGB 原帧，未读取深度或标注，详见下节。按照[当前仓库许可](https://github.com/apple/ARKitScenes/blob/main/LICENSE)核查使用条件，不沿用第三方旧许可证描述。
- **ADT**：[官方获取说明](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/dataset_download)给出邮箱注册并取得下载链接 JSON 的方式，也有[样例教程](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset)和公开序列预览。说明页未列出导师申请流程，但本轮未完成注册，不把它说成已获完整下载权限。[深度格式说明](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset/data_format)明确深度来自真值系统；使用这部分只能声明为特权深度受控条件，或另用冻结估计深度。
- **BEHAVE**：[官方数据页与条款](https://virtualhumans.mpi-inf.mpg.de/behave/license.html)公开列出下载链接及非商业科学研究条件，单批文件较大，本轮未下载；[官方概览](https://virtualhumans.mpi-inf.mpg.de/behave/)说明其四台 Kinect 采集与对象注册。获取方便并不消除视角与任务限制。

以上是候选来源的用途判断。Bonn 若用于初看，序列名只能帮助预选“检查哪类变化”，不能映射成模型输入或正确事务标签；实际发生了什么要看画面。没有已核查官方 train/test 分组的来源先只作开发样例，同场所及关联记录按组隔离，不能随机拆帧伪造独立检验。下载前登记具体清单；旧基线 manifest 保留其当时访问快照，不追改为新来源。

### 首批画面核查（开发预览）

白话：这次核查用实际画面判断来源是否值得进入连续视频与几何检查。输入是官方 RGB 帧或预览缩略图，输出是带原图引用的定性案例。例如门框、墙地面与对象共同出现，可以列为结构接入候选；这不等于已验证跨门运动、三维连接或对象真值身份，更不等于 M1/M2 方法有效。

来源、选择过程、32 张图像的摘要及 6 个案例记录在 [visual_source_review.json](../data/manifests/visual_source_review.json)。图像与内嵌原图的审查页保存在本地 `outputs/data-source-review/index.html`，不随 Git 分发。判断由助手逐图检查形成，用户复核仍待完成；ADT 缩略图没有已核实的时间戳，不能按编号伪造连续轨迹。

| 样本 | 实际可见内容与候选用途 | 尚未建立的证据 |
|---|---|---|
| ARKitScenes 47333462 | 从 3611 张 RGB 中按时间顺序均匀取 12 张，跨度 60.143 秒；可见地面、床、门框、墙角、窗与家具的不同视角，开头与结尾重见外观一致的地面印刷物。适合结构逐步揭示、对象重识别及两者共同保留 | 未确认连续跨房间或走廊拐角，不证明物体实际移动；未核深度、标定和位姿一致性 |
| ADT Apartment_release_clean_seq137_M1292 | 全部 10 张官方缩略图；厨房、客厅、餐区、楼梯与门口共同出现，另有手持物体和盘子。适合公共区域结构锚点与对象操作的联合考察 | 多区域同时可见不等于相机已经连续穿门；不能由缩略图恢复完整操作次序 |
| ADT Apartment_release_decoration_seq137_M1292 | 全部 10 张官方缩略图；公共区域与较小区域内视角，以及外观相似相框在支撑面、近处手持、桌面和搁板上的状态。优先考察门口连接及对象搬放 | 需连续 RGB 确认实际路径、共同锚点、时间次序与对象身份；尚未确认指定的走廊转角 |

ARKit 样本取自官方示例，选择早于看图；官方划分元数据确认其为 Training、visit_id=467138。只读取划分元数据及该训练视频帧，未读取验证/测试图像。ADT 第二段是在第一段不足以确认穿门后，按同后缀、不同活动选择的探索样本，不是随机代表性抽样。两段 ADT 同属一个公寓；这些已看场所及关联记录只作开发，不能再作为未见场所确认。共享物体的跨场所分组仍需核查。

ADT 预览通过官方公开资源接口获得，未完成完整原始 VRS 的注册/下载；公开预览可访问不等于所有数据权限已取得。ARKit 仅用 HTTP Range 读取 ZIP 目录及所选 PNG，校验各帧长度、CRC32 和 SHA256；ADT 校验官方 SHA1 与本地 SHA256。没有完整 ZIP 摘要，也没有本地视频解码、特征提取或科学测试。

**额外输入审查项：动捕标记。** [ADT 论文第 3.2–3.3 节](https://arxiv.org/html/2306.06362v2)说明物体及墙面使用运动捕捉标记，且标记出现在 Aria 图像中。它们可能为身份匹配提供额外线索，影响大小尚未量化；需在真实前端输入中核查，不能直接宣布存在答案泄漏，也不能默认实拍数据就没有捷径。真值派生深度仍按前述特权条件隔离。后续是否采用屏蔽或对照须先审查具体标记覆盖，不能改图后冒称原始观测。

上述案例用于挑选后续审查材料，不生成正确事务标签。结构误接、重复片段合并和对象错误修复继续纳入 M2 慢修订合同；这些是待实现/验证目标，并非已从缩略图观察到的系统修复结果。

### 共同检查

本节规定接口应满足什么，不维护当前任务顺序、规模或完成状态；这些只在 [PLAN.md](PLAN.md)。

1. 可追溯：许可、数据/模拟器版本、场景/资产列表、时间、相机参数和实际动作齐全，失败显式记录。
2. 可观察：支持重见、首次揭示、移动后重访的连续样本；呈现画面、位姿、当时记忆、候选和独立参考，不把首次发现等同于物理新建。
3. 无泄漏：online 与 audit 物理隔离，检查实例 ID/颜色、不可见对象、未来、完整重建，以及同源轨迹/资产跨 split 泄漏。
4. 可投影：候选 post-world＋固定几何/位姿输出可见性、位置和可比较观测。白话：能检查“这样改以后从另一个视角会看见什么”；不等于完整 PNO 或生成未来 RGB，不能用三位置换位替代真实 3D 投影。
5. 可审计教师：真实执行候选、记录所有能量分项/概率，覆盖遮挡、冗余编辑和信息不足；不只查排名第一。
6. 可计费：测渲染吞吐、固定前端特征提取耗时、峰值显存、缓存体积及训练耗时，不把硬件建议当实测保证。
7. 可比较：公开训练部分用于开发，test 不触碰；正式比较前冻结标签/知识/计算公平条件、split、评分/评价与差异门槛。
8. 可解释限制：不可辨识案例单独分析；复杂数据不保证 CTL 胜出；数据适配不能代替正式 M1 gate，不能把准备工作写成 M2 或长期效果已验证。

来源候选和接口合同的实质变化才更新本文件；实验结果进入 EXECUTE，阶段顺序和下一步只维护 PLAN，不按对话扩写另一份进度清单。

<a id="r4-map-control-engineering-data"></a>

### R4-3c/d联合工程值与产物（D-089）

白话：这些字段把“观测到了什么”和“作了什么近似”分开。输入来自原v2公共记录，输出名义地图及带原因的状态；例如unknown_cells中的格子即使有历史地面记录也不算名义自由。这不是私有XML转成模型输入，也不是新的训练标签或正式P场景点接口。

`spatial-history-r4-map-history-v1`只含schema_version和frames。每帧严格白名单为time_s、width、height、depth_m、camera_position_m、camera_xyzw、intrinsics、ee_position_m、ee_velocity_mps；深度80×80原值不重采样，时间相对决策点为−12..0 s。RGB、previous_velocity、goal、controls及世界/家族名不传地图函数。运行适配器先验证完整公共记录，再按白名单取值；选择器和文件名只留运维层。

`spatial-history-r4-observed-map-v1`输出status、cell_m、ground、surface_cells、floor_cells、nominal_free_cells、occupied_cells、unknown_cells、conflict_cells、obstacle_rectangles_xy_m、frame_audit、current_object、certified_free_volume=false及assumptions。xy格为整数二元组，矩形为[x0,x1,y0,y1]米；ground含height_interval_m与source_witnesses。每表面含cell_xy、role、height_m、first_source/last_source=[局部帧索引,row,col]、quad_observations；frame_audit显式对应source_index与time_s，记录分量分类数及原原因。地面缺失用null；未知格不丢弃，空列表不解释为整个世界自由。current_object沿用b完整值合同，未观测姿态/自旋仍null。

`spatial-history-r4-control-proxy-v1`以kind=predicted区分控制指令、运动学planned与真实actual。status为perception_unresolved、ground_unresolved、robot_kinematics_unresolved、initial_height_unresolved、numerical_failure或nominal_complete。trajectory为null/保留前缀/完整10001行；行含step_index、time_s、object_position_m、object_velocity_mps、robot_position_m、robot_velocity_mps、servo_force_n及三类接触布尔值。robot_path只含201端点的time_s、robot_position_m、robot_velocity_mps，数值失败时可能为前缀；不夹带物体结果、门事件或标签。

initialization记录public_object_position_m、position_intervals_m、backward_mean_velocity_mps、velocity_intervals_mps、model_object_height_m、model_vertical_velocity_mps、model_spin_radps及assumption。后两项0是平面模型假设，原b姿态/自旋仍未观测。first_unknown_step、unknown_sweep_steps、numerical_failure_step和最大位移/侵入记录缺口；uncertainty_status固定initial_state_and_geometry_envelope_not_certified，main_prediction=null、eligible_for_P=false。本批不构造P的4096点场景或特征，也不生成可部署动作标签。

公共任务读出返回status、openings、events、nominal_success、nominal_object_contact_intervals和formal_prediction=null。openings含观测x_bounds_m、plane_y_m、source_rectangles、observed_through_columns与coordinate_uncertainty_certified=false；events含gate_index（公开开口按y排序的局部序号，非私有ID）、cross_time_s、cross_x_m、status和completion_time_s。未决时nominal_success=null，不能当false填入选择。完整名义读出另给settled_containment、settled_speed和ordered_gate_passage；工程诊断布尔值不是正式成功概率。

#### 只读审计字段与原证据关系

白话：封存清单解决“这些误差究竟对的是哪份输入和哪版预测”的核验问题。输入是固定文件的字节摘要和运行输出，输出public_seal、子进程退出凭据及audit_receipt。例如改动一字节预测文件后，verify应拒绝原回执；这不是用哈希替代代码审查或误差评估。

运行配置`configs/spatial_history/r4_map_control_audit_v1.json`含23+13测试入口、固定数值、资源边界、320项源文件的bytes/sha256、原生成提交/成功回执和两份旧报告摘要。原公共/审计文件目录取自已交付v2运行入口：`/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v2`。新目录`/root/autodl-tmp/spatial-history/sh04-r4-cd-audit-v1`只新增check/、public/{family}/{world}/map.json.gz及九分支.json.gz、evaluation/{family}-{world}.json.gz、summary.json、原日志和各回执。原目录只读，不修改或复制大数组。正式summary保留原家族/世界/动作ID仅作审计索引，不能反传科学输入。

public_seal保存22项源码binding、完整commit、160个公开输出文件记录、16源公共记录摘要、逐世界/分支状态、16/144分母和private_truth_read=false；它必须在全部预测完成后写入。predict_exit须为0并绑定seal，evaluation才可读私有XML/trajectory/labels。原labels.trajectory必须等于登记的真实轨迹压缩文件记录；评估不接触integration_state，不重新运行MuJoCo。

summary.worlds保留16条，每条含map、association_status、frame_audit、九branches和selection。branch.object_association含几何位置误差、条件区间包含标志、后向均速作初速误差和未观测声明。branch还含proxy_status/readout_status、actual_success/nominal_success、compared_future_steps、逐点object_position_error_m/robot_position_error_m/robot_interval_mean_velocity_error_mps、初始化代理误差、unknown/数值失败位置及接触诊断。缺失值用null；部分前缀有可比端点但不能冒充完整200步。机器人瞬时速度参考固定not_present_in_original_trajectory，误差null。

summary另含proxy_status_counts、nominal_complete_count、nominal_task_readout_count、source_truth_files及public_seal摘要；formal_prediction_count和eligible_for_P_count固定0，formal_model_ready=false。map.full_world_wall_cell_recall用完整私有静态墙格分母；它不伪称只在公共可见范围评价。selection只有名义并列候选、期望真实失败代价与真实最优代价，正式regret保持null。

audit_receipt绑定全部阶段文件、源码、summary、两阶段真实退出0、总时间和资源。CLI verify只核原文件/登记/摘要/分母，不导入执行科学模块。export生成`results/spatial_history_r4_map_control_v1.json`，包含完整summary、public_seal、阶段文件清单、原始回执/检查日志文本及运行日志尾；大地图/轨迹留服务器。失败/中断也可导出原证据，status=failed_or_incomplete；已有报告仅在字节完全相同时复用。导出退出0只说明报告写成，需单独看status。科学/模型六项claims与formal_model_ready始终false。


## D-090：R4前端v2字段增量

白话：输入仍是已经封存的同一16条公开历史与144条指令，输出保留原像素与状态，并补充条件表面归属。例如某个单像素有唯一父顶面时，输出父分量编号及高度/半径见证；它不是新的语义真值标签，也不扩大模型输入的私有权限。

`r4_object_surfaces`接原object-history-v1纯深度值合同；输出schema_version=spatial-history-r4-object-surfaces-v2。原components字段不删：attached_side_support另有original_classification、possible_parent_count及ownership；ownership含parent_component_index、points（pixel、height_m、radial_interval_m）、radial_tolerance_m、conditional_same_cylinder=true及identity_certified=false。原reasons记录分量为何不是独立顶面，顶层/帧reasons按仍未决分量计算。surface_ownership_certified、瞬时速度及初态就绪仍false，姿态和角速度仍null。输入不接受RGB、XML、真实坐标、未来轨迹或标签。

地图schema_version改为spatial-history-r4-observed-map-v2，历史输入版本及已有格/面片字段保持；frame_audit新增attached_side_components和wall_height_resolved_components。静态高度判断只用同帧最低大平面及共同墙高，不读取后帧或私有墙名。控制适配输出spatial-history-r4-control-proxy-map-v2及source_map_version，原trajectory/robot_path/未决/未知扫掠字段语义保持。

阶段配置`r4_frontend_stage_v2.json`登记固定families/worlds/actions、原报告SHA、源路径、新输出路径、16项人工检查、deadline和资源。新check/public/evaluation各有started/receipt及失败时failure，父进程另保存check_exit/predict_exit/evaluate_exit。public全部输出封存并有predict_exit=0后才打开私有XML/轨迹/标签；原320输入逐文件校验。evaluation/summary记录acceptance_required、acceptance_observed、engineering_accepted以及原全量逐例误差；formal_model_ready仍false。公开地图和轨迹留服务器，独立export写`results/spatial_history_r4_frontend_v2.json`并绑定配置、源码、原输入/输出清单及原始回执。status=passed仍只表示执行完整，需另看engineering_accepted；两者都不表示正式模型通过。

D-090 v2r1运维修复：配置新增source_code_files、public_registration（16项）和truth_registration（304项），每项只含原path→bytes/sha256，没有真实状态或标签值。新入口r4_frontend_stage_v2r1.py仅流式核父报告摘要，不解析其JSON；公开子进程对原数据目录安装只允许16公开文件的读取守卫，私有读只在公开子进程退出后独立评估。新增3项隔离反例，共19项。旧v2中断报告/目录保留，新目录与报告用v2r1后缀；科学schema与算法仍为v2。


### R4-4资产环境审计字段（D-091）

`ops/spatial_history/r4_model_assets_v1.py`读取/root/sh05-assets-v1下已锁作者源码及独立环境，不读本项目公共/私有样本。`audit-v1/<step>/started.json`记录入口摘要与时钟，`run.log`保存完整命令输出，`receipt.json`含来源或解释器/版本、日志bytes/sha256及退出/耗时，失败保留failure.json。exporter将逐阶段证据文本及摘要导出results/spatial_history_r4_model_assets_v1.json；author_forward_passed和adapted_models_ready为空明确表示尚无接通结果。白话：例如pip成功只填环境回执，不填模型成功；这些是资产工程字段，不是模型可消费的语义输入或效果标签。


原生入口r4_native_models_v1.py的native-audit-v1目录将输入形状、参数数/名称、实际检查名、dependencies、source_module、CPU/RSS或CUDA峰值与日志/started摘要写入receipt。导出spatial_history_r4_native_models_v1.json核对每个成功回执的日志和started字节后列complete_stages；adapted_models_ready仍为空。独立进程读取守卫拒绝/root/autodl-tmp/spatial-history下全部项目数据，人工原生检查不接触训练/验证/确认标签。


D-092的DINO-WM资产目录为/root/sh05-assets-v1/dinowm-native-v1，download保存官方URL与权重bytes/sha256，native先核下载回执及权重再严格加载。逐阶段started保存两份官方源码全文件摘要、脚本和时钟，receipt含人工输入/输出形状、实际检查、参数量、GPU/RSS峰值、退出及耗时。导出results/spatial_history_r4_dinowm_native_v1.json不内嵌权重；adapted_models_ready为空，明确区别原生工程与任务接通。白话：例如权重严格加载通过仍不表示预测器已在双门数据训练。


### D完整任务适配值与工程证据（D-093）

r4_model_inputs.prepare返回history/controls/goal三份纯值；RGB与depth仍保存原80×80展平列表。D.tensorize生成[1,H,80,80,3] uint8 RGB、[1,H,80,80,1] float32深度/bool有效性、[1,H,37]元数据、[1,H,4]上一控制及reset，未来[1,200,4]控制和[1,12]目标。H为合法完整/近期/前缀长度，模式只在外层校验不作模型特征。

D.predict输出decision、observed、future、task；observed含tokens/deter/stoch/logit，future含原生prior，task为object_position_m[1,200,3]、contact_logit[1,200]、success_logit[1]与success_state[1,256]。概率只在外层用sigmoid转换，未训练值不写入正式结果表。训练loss单独接受精确三项labels（position_m/contact/success）及future_images（rgb/depth_m/depth_valid），不接受未来本体字段。白话：位置标签可以惩罚预测，但不能被误放到历史或控制里。

r4_dreamer_adapter_check_v1.py只读源码及人工fixtures，进程守卫拒绝所有spatial-history项目数据。started绑定源字节/提交，receipt记录16项具体检查、实际参数shape/count、七模块梯度范数、人工loss各项、输出摘要和资源；zero optimizer/new_training_steps=0。导出spatial_history_r4_dreamer_adapter_v1.json内嵌证据JSON及摘要，不伪造模型checkpoint或实际任务预测；首次失败保持原目录。


### W完整任务适配值与工程证据（D-094）

Torch公共tensorize沿用D-093严格查询，只将RGB转[1,H,3,80,80]、深度/mask转[1,H,1,80,80]，其余H×37/H×4/200×4/12语义相同。W.observe返回encoded_history[1,H,36,394]、H-1帧各6层的prefix_cache、末观测last_observation、index和零动作decision[1,36,404]。imagine只读取该公开状态/controls/goal，返回future[1,200,36,394]、task及last_cache_frames。缓存tuple追加新张量，不就地修改旧分支；depth_valid是原传感器有效性，不是墙/对象真值。

白话：例如121帧状态可以克隆给九候选，每条保持完全相同历史；第101步控制不会改变前100步预测。训练侧labels和future_images集合与D完全相同、无真实未来本体；辅助未来编码仅形成停止梯度目标，不进入预测缓存。图像padding及缓存是新适配字段，不能拿7项原生检查认证。

r4_dinowm_adapter_check_v1.py在新/root/sh05-assets-v1/dinowm-adapter-check-v1写started/source/weight绑定与receipt或failure；只用人工fixture，守卫禁止全部项目数据。17项包含稠密/缓存值及梯度对拍、完整历史、早历史依赖、因果/分支不可变、全200步反向和七路径梯度、DINO冻结。证据记录参数数/shape、实际CUDA/RSS、耗时、loss和输出摘要，new_training_steps=0、optimizer_constructed=false。导出spatial_history_r4_dinowm_adapter_v1.json，不产生真实模型结果或checkpoint。


### F完整适配值与工程证据（D-095）

F沿D-094 Torch公开张量接口；observe可传上块公开state继续，返回map[1,5,49,49,256]、observed_support[1,1,49,49,1]、camera_xy[1,2]、metadata[1,37]、image[1,5,80,80]和history_frames。image为RGB三通道/米制深度/有效mask；support表示历史观测曾支持该列的插值程度，不是碰撞占据概率。历史state不含未来控制或标签。

白话：例如分57+64帧接入应与一次121帧产生同图；未来解码得到的像素能做模型反馈，不能增加observed_support。imagine返回200×256未来池化、200×4×80×80预测RGBD、共同task及五个时间的完整地图引用；loss精确接收与D/W相同三项labels和三项future_images，目标不得进入主输入。

r4_flowm_adapter_check_v1.py固定新flowm-adapter-check-v1目录，14项本地来源与原作者来源receipt绑定，19项人工检查涵盖整数/半格平移、零环绕、5通道推进、未知支持、空视图、完整分块等价、控制因果/分支与全200步反向八路径。receipt保存参数/梯度/资源/人工loss与输出摘要，失败写failure并保留。export生成spatial_history_r4_flowm_adapter_v1.json，0优化更新/0真实查询/0新权重。


### 三模型真实公开接口证据（D-096）

r4_three_model_public_check_v1.py读取既有r4_frontend_stage_v2r1配置的families[0]/worlds[0]公开文件及原登记bytes/sha256；该选择只基于清单顺序。读取守卫在解码前安装，拒绝spatial-history下其他所有文件，包含私有trajectory/labels及聚合报告；有实际拒绝open反例。算法只得到严格public query及9份缩放控制，文件名/家族/世界不进入模型。

白话：例如同一份原始LL公开观察交给D/F/W，原144主分支和私有标签均不改动。新three-model-public-check-v1下D/F/W分别保存started绑定、c00..c22的samples/prediction、receipt或failure；D每候选16samples，F/W每候选1。receipt含公开源摘要、9候选/121帧/200步、参数与决策摘要、计时/峰值、0训练/0私有读取；未来目标从未打开。export内嵌所有JSON及原字节摘要至spatial_history_r4_three_model_public_v1.json，engineering_ready与trained_model_ready明确分开。


### R4-5学习数据与资源预检证据（D-097，proposed）

[learning_contract_r4_v2.json](../configs/spatial_history/learning_contract_r4_v2.json)直接引用原r4_family_design_v2，不另随机划分。32/8/8/8/4/4家族顺序和64个身份保持；每家族4世界9候选，共256历史、2304首次分支及2304独立重放。开发侧52家族，已有4家族按原manifest/digest/exit复用，余48待新生成入口；确认侧12家族仍只保留设计，模型/探针/评分锁定与单独放行前不生成观测。旧CPMT test继续封存。

白话：这些计数解决“候选由四条变九条后仍按旧规模计数据”的错误。输入固定家族清单，输出开发、确认及复用分母；例如一家的36条控制不是36个独立场景家族。这里是计划计数，不是2304条新分支已经生成。

r4_learning_preflight_v1.py只读取Git、已导出的工程JSON、家族设计、磁盘统计和JAX/Torch设备列表，不打开数据文件、初始化模型或跑训练。输出results/spatial_history_r4_learning_preflight_v1.json，含源文件bytes/SHA256、原33项内嵌证据校验、精确服务器根目录、各文件系统可用字节、设备信息、剩余旧窗口、固定预算缺口和未满足条件。audit_completed/exit_code=0仅表示预检执行完成；training_executable与confirmation_executable仍为false。成功报告拒绝重写；故障先保留终端证据，再登记修复，不借旧marker认证。

白话：资源预检输入机器实际容量和拟议额度，输出哪些前提还缺。例如Dreamer只能列出CpuDevice时，不能因为另两模型能用GPU就声称三模型训练环境均就绪。这不是GPU训练测速，前向/反向工程总耗时也不能直接当每个优化步成本。


D-098的results/spatial_history_r4_dreamer_cuda_v1.json保存独立install/check内嵌JSON及SHA256，pip_report为实际依赖下载来源，package_files为overlay普通文件摘要（nvidia目录链接仅复用已有库）。check结果包含jax/backend/devices、121/200、参数总数、七组gradient_l2、首次编译加反向秒数和三次热态反向秒数、GPU内存统计及RSS；new_training_steps=0、optimizer_throughput_measured=false。白话：报告区分安装成功、完整反向成功和真实学习，原CPU报告不能被此新回执覆盖。

D-100只改变运行stage为`dreamer-cuda-v2`及下载端点/超时重试；最终报告文件名和schema不变，内嵌新v2成功证据。首次v1失败仍在服务器资产目录，不混入成功报告。白话：下载失败只说明当时镜像没有及时返回完整wheel，不等于相同wheel内容或CUDA检查被替换。

D-101最终成功证据若产生，来自`dreamer-cuda-v3`；v1镜像超时和v2主动中断均不混入成功报告，服务器原目录保留各自日志/failure。白话：三个目录区分三次网络现场，只有带receipt且文件摘要完整的v3才可供GPU检查消费。


D-099的prepare_query返回history/controls/goal及独立selection_evidence，只有前三项是模型输入；公开查询严格校验后才允许R选帧，证据里的local_indices/voxel来源仅供审计。L历史tokens为[1,3025,256]，R至多[1,250,256]；decision_metadata为[1,37]，不保留其他语义字段。未来future_features为[1,200,256]，task沿共同位置/接触/成功输出。白话：例如R的第九个选中观察仍对应原119时刻，不能把选帧后的序号当作真实时间。

history-predictor-check-v1保存started原代码/合同绑定、receipt或failure，导出results/spatial_history_r4_history_predictor_v1.json；21项人工检查、L/R各自完整反向时间/三项损失/八路径梯度、总参数和实际CUDA/RSS峰值都记录。new_training_steps=0/optimizer_constructed=false；不是已拟合checkpoint或真实家族结果。


### R4学习分支读取值（D-104）

`spatial-history-r4-learning-branch-v1`的返回顶层为`schema_version/model_input/targets/auxiliary_targets/audit`。`model_input`严格是r4-query-v2的history/controls/goal/domain_spec；`targets`含prediction_times_s[200]、object_position_m[200,3]、interval_contact[200]和task_success布尔值。`auxiliary_targets`为null或future_rgb[200,80,80,3] uint8、future_depth_m[200,80,80] float64及future_depth_valid同形布尔数组；进入模型适配器时再显式转float32，不改服务器原数组。

`audit`含family_id/world/action/action_slot和public/label文件摘要，只供采样、日志及复现，不是模型张量。`actual_future_robot_motion_returned=false`、`integration_state_returned=false`是读取边界记录；它们不能被下游改写为特征。branch_index中的`seals`含三个原manifest及family_result，属于父训练进程的来源证明，不随微批次传入模型。

D-105补充：原`audit/config.json`没有家族实例编号；reader以已解析的`.../execution/<family_id>/data`父目录名和外部来源报告中的家族路径共同绑定身份，再核三个manifest、family_result和完整文件清单。目录名只是审计索引，不进入`model_input`。

D-106补充：磁盘`public/<world>.json.gz`是含九候选的`public-family-v2`，必须先经`r4_public_v2.model_input(public, action_slot)`验证并选槽，所得`public-query-v2`才进入共同查询转换。两个schema不能直接等同。

D-107补充：`sensor_times.npy.gz`由0.002秒物理步累加产生，按公共时钟合同以`1e-9`秒绝对容差核0.1秒采样；`sensor_step_indices`仍精确核对0、50、…、10000。原数组不重写。

D-108新增开发生成v2目录`/root/autodl-tmp/spatial-history/sh05-r4-development-generation-v2`；其48家族内容schema与v1提案相同，检查和最终报告路径独立。v1的零生成检查证据不冒充v2运行回执。

### R4学习runtime状态（D-109）

`UniformBranchSampler.state_dict`字段为schema_version、固定family_ids/seed、已发出draws及Python random完整状态；它属于训练恢复审计，不进入模型。Torch checkpoint字段固定为schema_version、update、model、optimizer、sampler、torch_rng_state、cuda_rng_state和binding；binding至少由代码、数据清单、配置摘要组成，具体runner必须补齐。`.partial`不是成功checkpoint，正式路径不可覆盖。

白话：这些字段解决训练中断后是否从完全相同位置继续的问题；输入是一次完整更新后的模型和所有随机/优化状态，输出可核摘要的单个恢复文件。例如只保留model而丢掉AdamW动量或下一采样位置，不能称精确续跑。它不保存模型输入中的family/world/action，也不代替逐例预测与验证指标。

D-110的共同逐分支metric记录`position_error_m/contact_brier/success_brier`三个有限浮点；聚合只对完整分支逐项算术平均。训练loss term仍按模型分别记录，不能混称共同metric。Torch optimizer state不含冻结参数；W的DINOv2权重仍由外部资产摘要绑定。

### M悲观输出值（D-111）

`spatial-history-r4-pessimistic-map-v1`返回共同`prediction`、补齐后的proxy、task、audit及布尔边界。audit含`stop_step/object_denied/pusher_denied/denied_cell_count/decision_body_free_cells`；stop_step为null表示全轨迹始终在允许格内。共同prediction仍是200个0.1秒端点、200个0/1物块碰障概率和一个0/1成功概率。

白话：这些字段记录M为何停止；输入是每个0.002秒扫掠所需格，输出首次不能由公开证据允许的步及完整预测。例如只有推头扫到未知时`pusher_denied=true`，不能伪装成已观测墙的物块碰撞。它不存私有墙坐标或真实标签，private评估结果必须在独立进程另存。

### M连续条件证书与双动力学字段（D-112，planned）

D-111的`spatial-history-r4-pessimistic-map-v1`不再是正式输入schema。新连续地图分别保存`observed_floor_support_rectangles_xy_m`、`observed_wall_interval_rectangles_xy_m`、`decision_body_core_cells`及按来源分类的未知；栅格缓存只能是连续证据的保守派生物，不能从旧格中心结果反推连续区域。`opening_boundary_intervals`保存E0的三条原区间，`wall_interval_propagation`逐候选保存左右墙外包矩形与传播规则，`wall_interval_derived_cells / wall_interval_witnesses`保存由区间扩张新增的相交格及候选/侧别；原`wall_cell_witnesses`仍只指向深度帧、行、列。白话：输入公开深度墙面与同一历史恢复的门边区间，输出可追到像素或E0候选的保守墙并集；例如左墙内缘可能在−100到−20 mm时按−20 mm挡住。它不把区间中点当真值，也不把新增墙格写成地面自由证据。

每个M结果共同含`system=M-SIMPLE|M-PHYS`、200步共同prediction、`certificate`、`contact_provenance`和数值审计。`certificate`至少含`assumption_conditioned / complete_sweep_contained / first_uncertified_step / first_uncertified_time_s / body / region_kind`；`contact_provenance`逐接触标明`observed_wall_interval / body_occlusion_unknown / sampling_gap_unknown / outside_observed_region / object_pusher`。未知先验产生的碰撞是模型输出，不能放进观测事实字段。

`M-PHYS.generated_scene`含`builder / source / xml_sha256 / wall_geometries / source_xml_used / saved_integration_state_used / xml`；每个`wall_geometries`元素含生成geom名、公开墙区间矩形和固定来源。`numerical_audit`含失败步、最大单步平移、最大接触侵入、最大物块倾角及MuJoCo/NumPy版本；`certificate`另给`object_projection / object_projection_radius_m`。白话：这些字段让审查者可从同一公开地图重建实际送入引擎的场景，并看见80.62 mm保守投影是否造成提前阻挡；它不保存或变相编码原世界XML、私有门编号和真实未来状态。

`SH-05-R4-dual-M-v1/public/<family>/<world>/map.json.gz`保存一次公共连续地图及本次重算的E0区间传播结果，`<action>.json.gz`保存严格的`family_id / split / world / action / M-SIMPLE / M-PHYS / private_truth_read=false`；家族`manifest.json`逐文件记录字节数和SHA-256。公开任务读出的`coordinate_uncertainty_certified=true`只表示门宽已取公开区间最不利端点，仍受登记理想传感器假设约束。独立`evaluation/<family>.json.gz`才包含同一世界九候选对标签的评分，`summary.json`只汇总52家族、208世界、1872分支的完整性、家族平均regret、逐分支位置/接触/成功误差和条件证书数量。白话：公开阶段即使知道路径里的`LR`字符串也只把它当已登记本地槽位，不把私有布局坐标送给模型；评价阶段在所有预测落盘后才打开标签。它不把文件名当视觉特征，也不因某一候选失败缩小分母。

`spatial-history-r4-m-simple-v1`（implemented, review pending）顶层含`system=M-SIMPLE / status / prediction / trajectory / certificate / contact_provenance / numerical_audit / initialization / initial_sensitivity / formal_model_ready=false`。`trajectory`为t=0加10000个2 ms步；共同`prediction`只抽取200个0.1 s末点，接触概率是该区间内是否有物块–已观测墙或物块–悲观未知接触的确定0/1值。`initial_sensitivity`固定含中点及去重后的四个xy角点；每项保存初始位置、完成状态、200步预测、名义成功、接触来源和数值审计，不保存实际未来。`contact_provenance`把连续相同来源压成`first_step / last_step / step_count / body / source / detail`区间，其中未知detail含代表格及未覆盖面积，墙detail含公开矩形序号。白话：输入同一公开地图和五个登记初态，输出一条中点主预测与四条不挑结果的边界敏感性；例如只有高x角点擦墙时会在该分支出现墙接触，但主预测不因此改选它。它不是从五条里挑最接近真值的一条，也不是概率校准后的随机样本。

连续几何审计另存`dependency_versions.shapely/geos`及`outer_circle_radial_excess_m`。固定32段/象限时外包半径因子为`1.000301272041302`，再加`numeric_guard_m=1e-6`；自由地面格则必须完全落入已向内收缩的观测面片。二者方向相反，避免同一个多边形近似同时被当作自由外包和扫掠内包。

白话：这些字段解决“预测撞墙”和“真的看见墙”被混写的问题。输入同一公开地图和控制，输出两种动力学的完整预测及每次阻挡的证据来源；例如M-PHYS在0.4秒撞到`body_occlusion_unknown`，表示它按悲观先验预测那里有障碍，不表示传感器观察到墙。它不读取私有XML、实际接触或未来机器人运动，独立评估只能在两种公开预测都封存后追加误差。

白话：例如一条分支可同时给出“看过什么和要执行什么”以及“实际物块后来到哪里”，但前者放model_input、后者只放训练target。未来RGBD只帮助D/F/W重建自身状态，不包含推头真实未来位姿。这不是把标签变成部署输入，也不允许从audit身份查表预测。
### VM-04两房四槽RELINK端点诊断产物（D-173）

新版本只读取原v1两房动作探针private四个RELINK槽、v2匿名视角扫描的对应私有top-2、两份固定house JSON、D-172碰撞归因匿名报告及各receipt/摘要；源文件字节不修改。每槽独立新controller在`private/<family>/slot_NN.json`保存原请求、只把`forceAction`改false的请求、模拟器错误原文、目标真实position即时与后8帧终态，以及是否碰撞拒绝/真实到点/仍运动。公开`results/vsmt_vm04_relink_endpoint_two_house_probe_v1.json`只保存family×状态计数、worker/资源/来源摘要和`private_ids_exported=false`；错误原文、真实object ID、类别、pose与house细节不得进入公开报告或部署输入。`episodes_generated=0/training_steps=0/memory_history_checked=false/semantic_positive_labels_issued=0`是边界字段。

白话：解决“看四个原RELINK动作能否按真实端点成立，却不能把物体私有身份泄漏到研究公开数据”的问题。输入是四个旧槽的封存请求和house，输出是四份仅私有的详细诊断及一份匿名状态表。例如某family两槽一槽碰撞拒绝、一槽真实到点，公开只出现两个状态各1，物体名字和碰撞对象仅留private。它不是36条新episode、训练标签、机器人可达路径证明或记忆关系前后核验。
### VM-04真实交互能力探针提案字段（D-174，未执行）

`configs/vsmt/vm04_relink_interaction_probe_proposal_v1.json`只登记原两房/四槽的来源receipt和报告SHA-256、固定视角/目标/相机前缀、匿名区域+公开可达格路线来源、不强制`PickupObject/PutObject/PushObject/PullObject`及public/private边界；`probe_authorized/generation_authorized/training_authorized=false`。`receptacle_target_source`、公开类型化容器读取器验证摘要、锁定模拟器`PutObject` API smoke摘要、私有动作runner摘要、推拉固定力档、抓取`manualInteract`、放置`placeStationary`和机器人位置容差均为null，验证器在待审态强制保持null。纯路线计划仅有公开路径点和匿名区域中心，不含object ID、真实asset pose、私有容器ID、动作结果或记忆标签。

拟议future private branch文件逐步登记原slot/分支/力档、请求和实际机器人位姿、资产实际position/`isMoving/isPickedUp`、父容器、`lastActionSuccess/errorMessage/errorCode`及完整失败；public exporter只汇总family×模式×失败阶段×力档计数、来源摘要、requested/actual workers及资源/退出，`private_ids_exported=false`。任何结果不得按成功方向、力值、容器、房或目标替换原槽；零位移也在分母。每个分支fresh controller，独立工作单元数在力档冻结后由原能力模式确定，实际并发由开机时安全资源测量决定。本提案未产生future branch文件、episode或训练数组。

白话：例如原两房四槽里三件仅可移动资产会分成各自推/拉测试，一件可拾取资产会分成抓/放测试；私有文件保存每次动作的真实细节，公开文件只说每类失败多少。这样能判断“机器人没走到、互动被拒绝、东西没动、关系没变”哪层缺证据。它不是现在已经做完的物理互动实验，也不是公开模型能凭私有身份选目标的接口。

D-175新增两个独立预登记文件：`vm04_relink_force_prereg_v1.json`固定三件可移动目标×推/拉×20/80/160 N共18个fresh-scene分支，另一个抓放分支；`vm04_relink_put_api_smoke_v1.json`固定simulator Python、AI2-THOR 5.0.0、CloudRendering build/zip摘要、`manualInteract=false/placeStationary=true/forceAction=false`，但真实`PutObject`参数与父容器语义回执为null。`vm04_relink_interaction_runner.py`生成的公开封存计划只含区域ID、public mask摘要、public类型来源、路线和digest；私有branch含目标/映射容器ID、动作请求/错误、实际位姿、目标位置/运动/拾取/父容器及失败。公开类型化容器输入必须来自当前公开RGB-D，单纯`surface`与私有`metadata.receptacle`均不能签发容器候选；现阶段该前端读取器未完成，不能运行四槽动作。原v1 proposal的执行档/真实smoke receipt等字段仍null，闸门false，不把预登记规格伪装成真实回执。

白话：预登记力档解决“看到某个力成功后才换试验力”的问题；输入是旧四槽能力分流，输出19个固定分支。例如80 N推没有位移，仍保留这次失败和80 N档，不去挑160 N结果冒充同一次成功。版本API smoke解决“网页示例中的`PutObject.objectId`到底在本build指向谁”的问题；输入锁定环境和一个独立抓放场景，输出将来的私有动作与父容器证据。两者都不是新数据生成、已验证容器感知或记忆RELINK标签。

D-176新生成职责沿用v2的固定两房36槽及`run_complete_requires`，每槽一次写`raw.receipt.json`、`raw.failure.json`或资源停后的`raw.not_started.json`；失败文件保留已生成public帧/动作前缀摘要、原slot/pose/source与私有拒绝或已核前提摘要，机器报告按family×program统计attempted/constructed/failed/not_started/candidate miss，并单列原四RELINK的覆盖缺口。`constructed=false`不删掉public前缀，不替换失败槽，也不作为teacher或训练正例。原v2文件和旧结果不改；新worker/配置/manifest与摘要仍须作为下一代码职责单独审查。

固定槽原始任务与文件（D-176，代码交审、未在服务器生成）解决原worker把建筑实例当干预目标、失败后难以核对固定槽的问题。输入是原v2公私36槽计划、两房作者house及固定pose、D-173四槽私有碰撞回执；输出先是`task-root/public/task-manifest.json`的36个匿名family/slot/episode行和`task-root/private/task-manifest.json`所绑定的36份`private/audit-family_00/slot_00.json`等私有任务，再由单槽worker写独立episode。例如原family00 slot04属于RELINK，私有任务封存其原目标ID与已验失败摘要，worker只写24帧前缀及`raw.failure.json`。公开任务manifest没有program、source locator、目标ID或私有任务摘要；这不等于训练部署输入、语义正例或换槽重试。

一个完整槽的可审文件形状为`episode/public/frame_0000…0031/{rgb.npy,depth.npy,camera.json}`、`episode/private/frame_0000…0031/{instance_masks.npz,mapping.json}`、`episode/private/intervention.json`和`episode/raw.receipt.json`。`camera.json`只保存公开相机pose/标定、时间、历史机器人命令、RGB/depth文件SHA；`mapping.json`隔离保存mask顺序与实例ID、目标ID、物体后态和干预动作。生命周期干预保留即时私有target mask，但只有`DisableObject`即时要求0像素；此后每个注册相机event继续要求disabled目标为0，提前重现记`disabled_target_reappeared_between_actions`。`EnableObject`即时mask只作诊断，是否重现改在紧随其后的注册相机event要求大于0，避免模拟器尚未重渲染造成假失败。`raw.receipt.json`绑定family/slot/episode、任务/固定pose/来源摘要、32帧公私文件摘要，写`raw_complete=true,constructed=false,construction_assessment_pending=true`。这只是raw落盘完整，不等于结构事务有效。失败槽保留已经写出的同形帧前缀，另写`episode/private/construction-failure.json`含私有ID、拒绝诊断和动作前缀，`episode/raw.failure.json`只保存匿名reason、任务/pose/来源摘要、公开前缀相机与私有mapping摘要和私有失败文件摘要；原四RELINK槽设置`relink_coverage_gap=true`。失败或资源停机未启动槽的逐槽父回执已写供审查但未运行，不能把worker的单槽终止冒充36槽stage完成。

父stage代码已按`check/run/verify/export`完成用户审查并由D-179开放raw批次（未在服务器执行）。`check.receipt.json`绑定两组独立纯测试与代码摘要；`run`先使用第一个原槽实际写raw同时采样RAM/GPU/磁盘/进程树占用，再按当前可见CPU和采样单worker需求选择最大安全并发（注册上限4），逐槽保存私有launch/log/exit和终止文件；硬资源停机后剩余原槽写`raw.not_started.json`，进程意外退出保留公开相机前缀摘要并写`raw.failure.json`。父`run.receipt.json`绑定36槽固定合并顺序、请求/实际worker、分片、退出、资源采样和`stop_reason`；匿名`results/*.json`出口只报family×program×complete/failure/not_started计数与RELINK缺口，不导出ID。例如第一个槽完整、四个RELINK失败、其余因磁盘保护未启动时报告分别保留这些状态，而不能说“36个有效样本”。这不等于真实服务器资源支持4并发或评价语义已验收；D-180在服务器运行前将`run_authorized/generation_authorized`重新置为false；当前实现即使完整落盘也只可作工程文件证据，服务器尚未运行。

启动第一个场景之前，父入口还从D-135隔离模拟器Python读取实际`python/ai2thor/procthor`版本并逐项对照已绑定环境合同（3.9.25/5.0.0/0.0.1.dev2），差异先拒绝生成，父回执保存核对值。这解决“同一源码在换过模拟器的环境中生成却冒用旧端点证据”的问题；输入是已登记虚拟环境与合同，输出实际版本核验，例如AI2-THOR变5.1.0会在首scene前停止。它不是另做`PutObject` API smoke、验证Unity collider或发记忆RELINK正例。

四个RELINK槽的`raw.failure.json`明确写`reason=prior_D173_fixed_endpoint_collision`、`relink_collision_observed_this_run=false`与原D-173端点receipt摘要；新父报告写`new_relink_collision_actions_executed=0/memory_history_checked=false`。这把“此前固定端点已被真实模拟器拒绝”和“本轮raw只留下前缀”分开：输入是原四槽已验回执及本轮第0–23帧，输出一个有来源的覆盖缺口。例如family00 slot04在本轮第24帧前退出，不能把失败字符串冒充新一次碰撞复现；也不等于找到机器人可执行的新RELINK路径或验证前后记忆关系。

这里的版本号来自不同文件职责：`vm04_two_house_worker.py`是原两房raw **v2**写入器（名字未带v2）；视角扫描配置/receipt **v2**固定了两个family的18个pose；`vm04_target_selection_v3.py`与目标合同 **v3**只规定作者资产资格；新`vm04_fixed_slot_raw_stage_v1.json`里的**v1**是本次独立固定槽stage的schema起始号，不是退回原两房v1 worker。白话：它解决“看到v1/v2/v3就误以为三个worker轮流覆盖同一批数据”的混淆；输入是旧写入器、扫描回执和新目标规则，输出各自明确职责及新文件来源。例如新raw帧沿用旧v2的npy/camera布局，却由v3筛物理目标。这不等于旧v2样本已经有效，也不要求旧目录重写成v3。

白话：输入是同一个冻结槽和它实际走到的最后一步；输出是可复核的成功或失败记录。例如前24帧已经拍到，但第24帧规定动作端点被碰撞拒绝，public保存已拍帧，private保存拒绝依据，报告说该槽失败。它不是把拍过前缀说成完整32帧episode，也不是隐去四个RELINK失败后宣称类别齐全。

固定槽raw新增只读逐帧完整性步骤`verify`（代码交审，服务器未运行）：完整槽的`frame_receipts`和worker失败槽的`public_prefix_frame_receipts`都绑定每帧公开camera及私有mapping摘要；camera再绑定RGB/depth，mapping再绑定mask和对应公开camera。进程崩溃槽只列实际已存在的相机/私有mapping前缀摘要，不把部分私有写入当完整raw；`not_started`必须没有公私帧。36槽独立哈希任务按运行时可见CPU、cgroup余量、磁盘余量与1 MiB流式读块/每worker 64 MiB保守内存档选择最大安全只读并发，保存requested/actual、规范槽序、逐槽验帧数及私有失败诊断摘要。成功`verify.receipt.json/verify.success.json`绑定`run.receipt.json`；匿名`export`必须核验该marker并按当前资源再并行复核36槽字节，才写`raw_file_digests_verified=true/raw_verify_receipt_sha256`。例如有人改了失败前缀`instance_masks.npz`，mapping的SHA链会拒绝导出且失败现场不覆盖。它不是公开类型化结构语义验收、`constructed=true`、teacher标签或服务器数据生成授权。

### VM-04独立RELINK新数据版本的拟议公私文件（proposed，未批准运行）

D-177只冻结`private/relation-verdict.json`未来发**物理RELINK正例**的两项必要条件：同一物理实例，以及公开旧、新关系各自有证据。它不冻结这个新版本的文件schema、在线QUARANTINE门或生成授权；离线各类失败继续分别计数。白话：私有评价确认P1和P2是同一凳子、公开两时点也支持两条关系，才可标正例；输入是封存后的公私证据，输出正例资格。它不让私有ID进入`public/candidate-seal.json`，也不把失败槽统一改名为QUARANTINE。

D-177正例条件已实现为独立[私有评价硬门](../ops/vsmt/vm04_relink_positive_gate.py)供代码审查：先核`old-observation-packet.json/prior-memory.json/post-observation-packet.json`及`relink-proof.seal.success.json`摘要，再打开`private/outcome.json`和前后两份trusted L1 `private-region-crosswalk`。outcome不再自报entity region；gate必须由crosswalk中唯一的instance→region→mask摘要链反查公开entity mask。只有该绑定成立、前后instance ID相同、prior有公开旧`located_at`证据、post有公开新`located_at`证据、P1/P2的公开place mask与关系支持不同、不强制动作已核且真实关系稳定变化全真，才写`physical_relink_positive=true`。输出只给布尔、失败原因和公私文件摘要，不导出ID；不同实例、crosswalk错绑或任一公开关系缺证据输出false且不产生QUARANTINE。当前仅人工公私文件测试6/6，未接trusted materializer或真实stage、未签任何真实正例。白话：它解决“文档说必须同一物体和两端公开证据，但未来评价器可能漏查一项”的问题；输入封存公开证据和事后私有后态，输出正例布尔与缺项，例如同一凳子但P2公开关系缺失就拒绝。它不等于公开模型读取私有ID、候选/teacher评价、在线暂存门或真实数据已通过。

若另立版本，`public/action-plan.json`应在动作前封存匿名目标区域、公开旧`located_at(P1)`关系、目标格`P2`、机器人路线、全部固定分支/方向/力档及公开证据摘要；`private/action-map.json`才保存模拟器实例ID、实际动作参数与容器映射。每个fresh分支的`private/action-outcome.json`保留机器人逐步真实位姿、动作返回、目标物实际位移/拾取/父容器/稳定终态、完整失败和退出；`public/post-action-packet`仅由执行后的当前RGB-D与此前预测记忆生成匿名实体/地点/关系证据，不读取该私有后态。`public/candidate-seal.json`在任何teacher、private评价或未来观测打开前保存候选及摘要，`private/relation-verdict.json`此后才记录同一实例连续性、旧边前提、P1→P2物理关系、公开支持、候选是否遗漏、executor旧边关闭/新边建立/身份保留及逐层失败原因。公开汇总只报family×分支×物理/记忆状态与candidate miss，不暴露ID、真值位置或失败文字；原36槽及四个固定RELINK失败文件保持原样。

白话：这些拟议文件解决“动作真的可执行”和“记忆关系真的改对”被一个成功位混淆的问题。输入是先登记的公开目标和动作、后来实际拍到的当前画面；输出是公开候选封存、隔离的私有物理/关系判定及完整失败。例如同一椅子从P1推到P2，但候选集没有合法RELINK，公开汇总记candidate miss，私有文件记录同一实例和真实终态；若旧记忆没有P1边则记事务前提缺口。它不等于已取得机器人路径证据、用私有ID生成候选、teacher补候选，或用新成功替换原碰撞槽。


D-180科学适用性审查把原36槽限定为暂停的工程批。每个episode的注册相机命令只在同一pose交替±0.25° yaw，偶数步回到原朝向且无平移；因此32帧不能提供有意义的跨视角再识别、遮挡转移或自由空间负证据压力。再叠加四个RELINK必败、16个非干预槽中，BIND/SPLIT/MERGE 12槽尚无公开类型化结构规则，NOOP 4槽也无不变语义验收、两house无独立family split，即使所有可写槽都raw成功，也不能用来估计五臂L2差异或支持VSMT主张。输入是现有worker/合同静态字节，输出是`generation_authorized=false`和明确的证据上限；它不删除旧设计，也不把尚未生成的数据写成负实验结果。


D-181发起、D-182冻结审查数值的[观察适用性合同](../configs/vsmt/vm04_observation_suitability_proposal_v1.json)继续执行关闭。初始相机可在观测0前`TeleportFull`，此后只能执行预登记的Move/Rotate/Look动作并按真实camera pose验收；同一family必须有自然遮挡后重现与出视野后重现两种分支，每条episode在真实平移后的pose重新看到目标。公开`visible/occluded/out_of_view/reobserved`只由当前RGB-D、depth、pose和标定形成，private mask只能在公开封存后评分；Disable造成的消失不准冒充自然遮挡。审查冻结值为关键与重现pose各至少0.5 m平移、关键yaw至少30°、每状态至少2个公开时刻、最多24步及2 cm/1°实际pose容差。白话：输入一条事前固定的相机路线，输出多视角公开包和真实pose回执，例如从P1看见椅子、移动到桌后遮挡、再移动0.5 m从P2看见它；它不是模型主动找路，也不保证事务标签成立。多视角终端重现窗口仍为null，所以这些数值获准进入schema审查并不等于runner可执行。

同一合同把L2可辨识性升为硬准入门。Current-Frame-Only probe（CFO，当前帧单独诊断器）只读当前L2公开packet并预测登记program type；同架构/优化预算的public-history probe额外读取封存公开历史和causal prior。二者按house family汇总，历史probe减CFO的单侧95%区间下界必须超过15个百分点，CFO不得超过60%；另以candidate封存后才打开private reference的sealed-catalog oracle recall检查候选可解性且须至少90%，family bootstrap固定10000次、seed 260916，至少32个完成family才运行门。输入是开发family公开包，输出`L2_admitted`或`engineering_or_easy_slice_only`；它不等于LOW记忆更新基线，也不证明VSMT胜过任何方法。CFO/history只准共用一个事前冻结结构，CFO把history/prior输入mask掉，不得在门所用family上分别挑表现较好的结构；精确结构和共同训练预算仍为null，未审实现不得生成。24-family且“均值≥15个百分点、下界>0”的省资源备选未获采用，因为它削弱了“历史优势至少15个百分点”的区间保证。

D-177 crosswalk当前只验证instance→region→公开mask内容绑定，真实来源仍待trusted L1 materializer receipt。D-181要求该receipt同时绑定raw public frame、private mask、public packet、private crosswalk及materializer代码/配置摘要，并让public RELINK proof seal再绑定receipt摘要；实现和测试完成前，真实物理RELINK不得发正例。白话：这解决“crosswalk内容看起来一致，但不知道是谁在什么时候写的”；输入同一次materialization的公私文件，输出一张不可替换的摘要链。它不是让部署模型读取private crosswalk，当前仍标planned。


D-182补充观察合同的不可观测干预和产出计划。凡有world intervention的程序，动作前公开visibility builder必须基于当前RGB-D/pose及此前封存的匿名target track或公开预登记reveal locus，把干预对象所在证据判为`occluded`或`out_of_view`并封存；若仍`visible/reobserved`，原槽记`intervention_visible_to_camera`，不执行动作、不换路线。重现平移固定相对“干预前对应程序的公开前提pose”计算，不能挑任意更远pose凑0.5 m。输入是事前路线和公开visibility状态，输出动作许可或匿名失败；它不使用private mask决定何时动作，private只在封存后评分。

D-182批准先登记6个独立pilot family，只诊断路线、visibility builder和构造成品率；pilot和48个正式house清单都在pilot前按result-blind manifest hash顺序封存且互不相交；pilot永久排除可辨识性门、VM-05训练/validation及VM-06 confirmation。正式失败不补，少于32个完成family即构造门失败。D-183另行[提议](../configs/vsmt/vm04_observation_suitability_d183_amendment_proposal_v1.json)只预封存不少于70个house的固定顺序，并让6-family pilot完成数机械决定正式前缀长度：5–6个完成取48，4个完成取64，0–3个停止；不得看probe或oracle结果决定N。白话：pilot是提前发现“路线总撞墙”的工程试跑，不是先看6个结果再挑容易的房；D-182当前输入固定6+48个不同house，D-183若获批只允许把正式固定前缀扩到64，不自动授权任何运行。

D-183已批准九个program逐类报告CFO正确率、history正确率和配对差；某类CFO超过60%时，该类仍留在总体分母，但标`easy_class`且不得单独支撑该原子主张。SPLIT/MERGE程序分配须在生成前由确定性几何、相机路线和冻结公开前端封存：SPLIT要求远/遮挡pose形成一个公开欠分区域、近距重现形成两个；MERGE要求旧前缀预登记关联断裂形成两个公开track、重现时公开证据支持同一结构。伪影未按冻结判据重复出现就记construction failure，不能事后改program。精确几何参数、公开前端伪影判据和pilot重复次数仍为null并阻断运行。

新[观察构造schema](../schemas/vsmt_vm04_observation_construction.schema.json)登记六类机器记录：70-house来源池、pilot后正式前缀、私有构造路线、去掉program/伪影assignment的公开provenance路线、逐帧公开route receipt及construction verdict。公开visibility assessment只含匿名subject ref、公开投影样本数、由depth可见体积判为未遮挡的样本数、当前公开support摘要和四态结果；`private_mask_or_instance_id_used=false`固定。投影为0是`out_of_view`，投影大于0但未遮挡样本为0是`occluded`，终端窗口有当前公开support才是`reobserved`，其余保守记`visible`并禁止隐藏干预。白话：机器人动作前不能自己写“看不见”；输入公开相机几何、depth和匿名轨迹位置，输出带摘要的状态。例如目标位置仍投进画面但所有采样点都被更近深度挡住才算遮挡。它不读取模拟器mask/ID，也不把构造路线文件交给adapter当额外输入。

D-185路线扫描最初记录`pose_id/pose/visibility_assessment/public_evidence_sha256/scan_phase/support_role/future_or_action_outcome_used`七项；D-200再加入`visibility_builder_receipt`，且`public_evidence_sha256`必须等于该receipt摘要。后三个来源边界项仍分别固定为`pre_intervention_public_route_scan`、`pre_intervention_public_subject_or_locus_not_post_action_confirmation`和`false`。执行侧的可信公开帧接口只输出`rgb/depth_m/camera/source_frame_sha256/private_fields_removed=true`，公开capture再据此生成visibility assessment和公开证据摘要；模拟器metadata、objects、instance masks及干预回执不经过该接口。route receipt含观测0和每个注册动作后的观测，N个动作须有N+1项。白话：输入同一个模拟器event，可信边界把公开图像与私有对象表分开，输出给公开侧的只有相机能拍到的数据；例如event内部即使有`objectId`，公开visibility函数也拿不到。它不等于materializer receipt已经落盘，当前精确动作请求和正式数值仍待冻结。

D-186新增[raw文件schema](../schemas/vsmt_vm04_multiview_raw.schema.json)和[materializer receipt schema](../schemas/vsmt_vm04_materializer_receipt.schema.json)。每帧公开目录含`rgb.npy/depth_m.npy/camera.json/frame.json`，私有目录含`instance_masks.npz/mapping.json`；episode末尾两侧各有唯一`raw.terminal.json`和`raw.manifest.json`。私有manifest摘要作为`raw_episode_manifest_sha256`进入materializer receipt；receipt的每行必须同时记录连续`observation_index`、raw公开帧、raw私有mask、公开packet和私有crosswalk摘要，并绑定materializer代码/配置。公开RELINK proof seal再绑定receipt文件摘要。白话：这张receipt像逐帧装箱单，证明哪个packet与哪个crosswalk来自哪份raw；它只含摘要而不公开ID，也不能替代尚未实现的新多视角materializer执行器。

D-187 materializer输出固定在`episode/materialized/public/frame_XXXX.json`与`episode/materialized/private/frame_XXXX.json`；完整批次才另写公开`materializer.receipt.json/materializer.success.json`。中途失败改写为公私各一份`materializer.failure.json`，公开文件只含匿名reason、已完成帧数和禁止替换，私有文件才保存异常类型/文字；不得同时出现success receipt。复验器重新读取原raw和全部输出，逐项核receipt摘要。白话：输入第0至N帧raw，输出同序packet/crosswalk或一个保留前缀的失败目录；它不是允许失败后删目录重跑，当前回调仍是人工fixture而非真实前端。

D-188公开前端行只允许`sample_id_hash/decision_time_s/rgbd_refs/camera_pose/robot_state/past_actions/region_observations/relation_observations/free_space_observations/visibility_observations/public_constants`十一项；`schema_version`和`prior_memory_ref`由packet builder补入。builder逐帧先验收公开schema，再用共同bootstrap推进memory，最后调用独立causal-prior replay签收据。白话：输入一排已经匿名化的公开感知结果，输出与当时旧记忆逐帧绑定的数据包；例如材料化进程不能把私有`SPLIT`标签或椅子objectId塞进前端行，也不能自己写一个方便的旧图摘要。它不生成匿名区域、动作时间或阈值，这三项仍是运行阻断。

D-189公开前端的输入分成两侧：公开侧为sealed raw RGB/depth摘要、当前depth数组、camera pose/calibration、冻结DINO patch token及显式公开context；隔离私有侧仅为当前帧instance mask栈和同序ID。输出公开前端行、当前free-space内部状态、匿名拒绝诊断及单独private crosswalk。mask/ID枚举顺序或ID文字变化不得改变公开行；小mask拒绝只公开像素/摘要/reason。白话：可信材料化器可以知道哪个mask属于哪个私有实例以便写审计映射，但记忆链只看到`region:0000`等匿名区域；它不提供跨帧oracle身份。当前阈值均须显式构造且尚未冻结，真实模型权重和父stage仍未绑定。

D-190 context manifest记录`public_route_sha256/observation_count/decision_time_rule_id/decision_times_sha256/action_encoding_id/action_command_vectors_sha256/ordered_context_sha256s`，并固定未使用private program/target/teacher/future。sample ID只由public route摘要、观测序号和decision time产生；past actions来自public route前缀及显式编码表。白话：它解决材料化器是否可能把尚未执行的动作塞入当前packet；输入路线和冻结时间/编码，输出每帧可复核的上下文。它不把construction-only整条route直接交给adapter，也不说明当前人工一秒间隔/one-hot fixture已批准。

D-191将公开材料化终态固定为`materialized/public/prior-memory.json`、`causal-prior.receipt.json`和`public-frame-context.manifest.json`，三者的文件SHA-256与逐帧raw/packet/crosswalk一起进入`vsmt-vm04-trusted-materializer-receipt-v2`。causal receipt内部的规范packet摘要序列必须等于磁盘全部公开packet按观测序号重算的序列；context manifest必须绑定同一`public_route_sha256`和相同观测数；prior memory须通过graph hash核验并等于causal receipt的终态。crosswalk的每个instance→region mask摘要另由该帧raw私有mask内容重算，不接受packet/crosswalk两边一致但与raw不同的自报摘要。白话：输入是一段已封存raw及其公开context，输出一套能证明“这些packet确实产生了这份旧记忆”的公开文件；它不是允许部署reader读取private crosswalk，也不表示尚为空的正式时间、动作编码、阈值和模型摘要已经冻结。

D-192注册相机请求表必须精确覆盖八种公开路线动作。Move行只含`action/moveMagnitude`，Rotate与Look行只含`action/degrees`；所有幅度显式、有限且为正，任何`forceAction`或额外字段拒绝。白话：输入是路线动作名，输出是不依赖AI2-THOR默认参数的实际请求；例如正式合同即使当前没有LookDown路线，也必须先登记LookDown模板。它不代表人工测试的0.25 m与30°已经成为正式值。

D-193新增`vsmt-vm04-materializer-config-v1`与`vsmt-vm04-materializer-assets-receipt-v1`。前者完整保存公开前端、bootstrap、模型声明、公开常量、builder摘要和自身摘要；后者保存同一config摘要、model ID、DINO repository commit、干净工作树标志、checkpoint摘要、无需网络标志及自身摘要。episode的materializer v2 receipt新增`materializer_assets_receipt_sha256`，生产入口必须先核assets receipt与config一致。真实loader固定本地`dinov2_vits14`、`pretrained=false`、checkpoint `weights_only=true/strict=true`、冻结参数/eval/CUDA及`x_norm_patchtokens`，不接受模型别名。白话：输入正式数值和服务器已有模型字节，输出“这次材料化到底用了哪套参数与哪份模型”的摘要链；它不把服务器绝对路径写进公开数据，也不把当前测试数值升级为正式配置。

D-194新增`vsmt-vm04-materializer-code-manifest-v1`。字段为`reviewed_git_commit/source_inventory_policy/sources/manifest_sha256`；每个source只含仓库相对`path`与实际文件`sha256`。固定inventory覆盖materializer与父stage两个入口及`src/cpmt`、`src/vsmt`下全部Python源码，运行前同时核当前checkout和受审commit的文件集合与字节。manifest自身摘要才可填入合同的`expected_materializer_code_sha256`和episode receipt的`materializer_code_sha256`，调用方不能单独报一个哈希。白话：输入受审commit，输出其真实运行源码的逐文件清单；例如同名文件改一字节、漏一个包模块或多出一个新模块都会拒绝。它不包含模型checkpoint、第三方环境或正式科学参数，这些分别由assets/config/未来environment receipt约束；当前合同期望摘要仍为null。

D-195把`vsmt-vm04-private-region-crosswalk-v1`的顶层字段收窄为`schema_version/observation_index/bindings`，删除调用方可写的`frame_role`。`observation_index`必须与raw manifest、materializer receipt同一连续帧号相等；RELINK proof seal用old/post公开packet摘要选择证据，私有gate再从receipt唯一反查对应crosswalk和帧号。白话：crosswalk只说“我是第3帧”，不能说“我是新关系帧”；输入哪帧属于old/post由先封存的公开proof决定。它不把observation index当实体身份，也不允许事后选择有利帧替换proof。

D-197补充RELINK证据对的机器约束：materializer receipt中由old packet+crosswalk摘要唯一命中的`observation_index`必须严格小于post packet+crosswalk命中的index。相等、反向或多行命中都在读取private outcome前拒绝。白话：旧关系文件必须真来自更早帧，新关系文件必须真来自更晚帧；它不依赖文件名自报时间。

D-198将观察合同的数值状态拆为`observation_trajectory.frozen_numeric_values`和`l2_identifiability_admission_gate.frozen_numeric_values`，两者只保存已由D-182批准的数值；仍待冻结的`CFO_and_public_history_probe_architecture/shared_probe_training_budget`单列在`pending_model_and_budget_fields`且保持null。可辨识性门新增`evidence_level`：当前前端为`L1_oracle_entity_masks_plus_public_geometry`，目标主张层为`L2_public_proposal_frontend`，L1结果不得开放L2主表；`reviewed_L2_frontend_receipt_sha256`当前为null并由生成入口硬检查。白话：同一RGB-D序列可以以后生成L1/L2两种proposal视图，但当前只有oracle mask视图，不能换个packet名字冒充公开检测。

D-199新增三个只供审查的科学层记录。`vsmt-vm04-l2-proposal-receipt-v1`绑定当前公开RGB文件/像素、SAM仓库commit、checkpoint、automatic-mask配置、assets、generator代码及有序mask摘要，不含crosswalk；`vsmt-vm04-public-visibility-subject-v1`绑定先前公开packet、mask/depth/camera和公开世界采样点，后帧builder receipt绑定当前depth/camera与assessment；`vsmt-vm04-public-program-construction-plan-v1`绑定prior memory和各program所需node/edge/locus/artifact引用。SPLIT/MERGE另有artifact plan/receipt，逐replay保存远近public packet摘要、region ID集合和转移证据。白话：这些文件让“proposal从哪里来、为什么说被挡住、为什么这一槽叫RELINK”都可复算；它们不保存私有实例ID，也不代表真实loader、数值或runner已获批。

D-200把visibility builder receipt正式嵌入每条route observation：route plan同时封存`visibility_subject_seal_sha256/visibility_builder_config_sha256`，每帧必须使subject、config、observation index、当前depth、camera、assessment和receipt摘要一致，`public_evidence_sha256`必须等于该builder receipt摘要；worker在任何private intervention前先验这些绑定。公开route provenance保留subject/config摘要，但仍禁止作为adapter额外输入。白话：输入当前公开帧和先前封存subject，输出一条可追到真实公开depth/camera的遮挡判断；例如把第3帧`occluded` assessment配上第2帧receipt会在动作前失败。它不开放controller、模型资产或运行。

同一修订新增`vsmt-vm04-public-program-matcher-receipt-v1`及[机器schema](../schemas/vsmt_vm04_program_matcher.schema.json)。program plan新增`matcher_config_sha256`；receipt绑定plan、prior、当前packet、route plan/receipt/verdict、全量region匹配分量、终端support选中的region、负证据数、RELINK新place关系和可选SPLIT/MERGE artifact receipt。输出固定`private_identity_used=false/semantic_identity_truth_established=false/posthoc_relabel_or_replacement_used=false`。白话：输入封存的公开证据，输出“本槽最低公开构造条件是否满足”；例如BIRTH region对所有同类型旧节点都低于冻结门才可通过。它不等于参考事务正确，也不允许teacher修补候选。当前matcher全部正式数值仍为null，edge RETRACT因packet尚无跨时关系缺席证据明确失败。

D-201新增`materialized/construction-audit/`及`vsmt-vm04-episode-construction-receipt-v1`。目录保存规范化construction plan、matcher config、terminal packet之前的matcher prior、program matcher receipt及可选artifact receipt；episode receipt再逐文件绑定这些字节和既有materializer/causal/terminal packet文件。目录固定`deployment_reader_may_open_construction_audit=false`，没有private instance ID、teacher或参考事务，但program名和构造判据属于审计元数据，不能作为部署模型额外输入。离线目录还固定`construction_plan_pre_terminal_seal_established=false/eligible_for_parent_family_completion=false`，matcher通过只写时间封存待补状态。白话：输入同一次材料化留下的公开证据文件，输出一张可重放的公开匹配/失败证明；例如篡改prior、终端packet或matcher receipt任一文件都会验收失败。它不等于这些文件可喂给adapter、plan时间顺序已经在线证明或整个family完整。

D-202新增`materialized/construction-plan-seal/`。目录在打开最后登记terminal raw帧前立即写入`online-plan-request.json`、`program-construction-plan.json`、`matcher-prior-memory.json`、`online-plan-temporal.receipt.json`和绑定四个文件摘要的`online-plan-temporal.sealed.json`。收据固定terminal public/private帧、未来、teacher、参考事务和私有身份均未在seal前被该materializer调用打开，同时固定`request_provenance_established_by_parent_stage=false/clears_episode_temporal_seal_pending=false`。输入是当前公开memory、route和request，输出是一个在线时序失败现场；例如terminal RGB验证失败时，seal目录保留而materializer receipt不会出现。它不等价于request的父stage来源已证明、离线audit已消费该收据或episode/family已构造完成。

D-203候选新增`vsmt-vm04-parent-program-request-spec-v1`和`vsmt-vm04-parent-program-request-provenance-receipt-v1`。spec绑定public route/private route commitment、family/program、terminal index、matcher config和逐program selector；selector只保存稳定public node ID、public locus/place ref或规则/artifact摘要，禁止调用者提供version ID。receipt绑定spec、public route、`terminal-1` prior、派生的online request和父核心代码摘要，并固定无episode/raw path参数、无terminal/future/teacher/reference/private输入。例如RELINK spec只存entity A、place P1和public P2 ref，receipt中的A/P1 version与A→P1 edge version必须由prior唯一复算。当前receipt另固定`selector_spec_pre_terminal_registration_established=false/consumed_by_D202_temporal_receipt=false/clears_D201_temporal_seal_pending=false`；它不等价于spec已有提前时间证明、已落盘到D-202 seal目录或可供adapter读取。

D-204候选新增`vsmt-vm04-parent-selector-temporal-receipt-v1`、`vsmt-vm04-parent-program-request-provenance-receipt-v2`和`vsmt-vm04-online-program-plan-temporal-receipt-v2`。selector receipt绑定spec、public route/private route commitment和父代码摘要，并固定在raw observation 0前、双方raw帧数均为0；父provenance v2再绑定该receipt和`terminal-1` prior派生request；D-202 v2只保存父provenance摘要并标`parent_request_provenance_consumed_by_D202=true`。输入链中任一program、route、prior、terminal index或禁止通道不一致即拒绝。例如把`teacher_reference_or_private_identity_used`改成true后即使重算receipt摘要，D-202也不能消费。当前真实episode目录尚未规定这些父文件的生产落点，D-201 episode receipt也仍只认识旧pending状态；这些字段不供deployment reader读取，也不等于family完成。

同一修订把pilot完成固定为“该family全部预登记route、visibility状态及所需SPLIT/MERGE伪影均不替换通过”，来源只能是sealed route receipts与construction verdicts机械派生；调用方布尔禁止。父stage family receipt尚未实现，所以`seal-formal`当前即使开闸也拒绝旧布尔输入。白话：48/64/停的输入必须由六套完整施工收据计算，而不是人工写五个true；这不改变离散N规则。

D-196在观察父stage登记独立`materializer_code_sealing_authorized`和`seal-materializer-code`输出。输出文件就是D-194 manifest，采用独占创建；输入路径和commit不写入其他状态文件。当前授权为false，所以不存在真实输出摘要。白话：父stage以后负责把审过的commit变成正式源码清单；现在只证明未授权时它不会读取传入checkout或写文件，不等于已经做过服务器source inventory。
