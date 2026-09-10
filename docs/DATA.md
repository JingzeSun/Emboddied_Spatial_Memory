# 数据与观测合同

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
- **ARKitScenes**：[官方下载说明](https://github.com/apple/ARKitScenes/blob/main/DATA.md)允许按 video_id 和文件类型下载，官方脚本使用公开 Apple URL；示例训练视频 47333462 的相机轨迹 URL 未认证 HEAD 返回 200。未下载图像、深度或标注。按照[当前仓库许可](https://github.com/apple/ARKitScenes/blob/main/LICENSE)核查使用条件，不沿用第三方旧许可证描述。
- **ADT**：[官方获取说明](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/dataset_download)给出邮箱注册并取得下载链接 JSON 的方式，也有[样例教程](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset)和公开序列预览。说明页未列出导师申请流程，但本轮未完成注册，不把它说成已获完整下载权限。[深度格式说明](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset/data_format)明确深度来自真值系统；使用这部分只能声明为特权深度受控条件，或另用冻结估计深度。
- **BEHAVE**：[官方数据页与条款](https://virtualhumans.mpi-inf.mpg.de/behave/license.html)公开列出下载链接及非商业科学研究条件，单批文件较大，本轮未下载；[官方概览](https://virtualhumans.mpi-inf.mpg.de/behave/)说明其四台 Kinect 采集与对象注册。获取方便并不消除视角与任务限制。

以上是候选来源的用途判断。Bonn 若用于初看，序列名只能帮助预选“检查哪类变化”，不能映射成模型输入或正确事务标签；实际发生了什么要看画面。没有已核查官方 train/test 分组的来源先只作开发样例，同场所及关联记录按组隔离，不能随机拆帧伪造独立检验。下载前登记具体清单；旧基线 manifest 保留其当时访问快照，不追改为新来源。

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
