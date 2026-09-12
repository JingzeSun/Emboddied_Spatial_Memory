# 数据与观测合同

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
