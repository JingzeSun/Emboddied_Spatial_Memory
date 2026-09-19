# VSMT-lean 数据与观测合同（D-224）

本文件只定义 VSMT-lean 的数据来源、划分、生成规则、三种读取面、字段、标签与评价文件。旧 VM-04 各版数据协议、D-210 地点路线、SH/R4 物理数据合同已随分支 `archive/pre-d224-unified-graph` 归档。全部内容为 **proposed**：未生成任何 episode，未下载任何新资产；数值凡写"null"者在 S0 登记规则、在 S1/S3 按规则选择。

## 一、来源与划分

来源是 ProcTHOR-10K 作者 `train` 分区的 house，经 AI2-THOR 5.0.0 CloudRendering 渲染。它解决"手工路线太少、没有外部锚点"的问题；输入是作者分区的完整 house 清单，输出是按 house 互斥的三个 manifest。例如某个 house 落入 test 后，它的任何帧不得出现在 train 或 validation。它不复用旧 12 槽路线，不使用 3RScan 或真实数据。

| 项 | 规则 |
|---|---|
| 划分 | 对 house ID 与登记 seed 的哈希取前缀排序；前 300 个入 train、随后 50 个入 validation、再 100 个入 test（proposed，S3-01 可按成品率下调） |
| 小试 | S1 只取 train 前缀前 50 个 house |
| 互斥 | 按 house；同一 house 只生成一条 episode |
| 失败 | 生成失败的 house 保留 receipt，不替换、不补样 |

## 二、路线与干预生成

**覆盖式重访路线** 解决"干预后的物体必须有机会被重新看见"的问题。输入是 house 的可达位置（生成器专用构造信息，不进入任何方法），输出是执行前登记的完整动作序列。例如路线先经过客厅、厨房，中途在卧室停留，再返回客厅与厨房。它不给方法暴露可达图，不保证每个物体都被看见。

| 项 | 规则 |
|---|---|
| 动作 | 平移 0.25 m、转身 90°、俯仰 30°；`snapToGrid=true`、`forceAction=false`、`gridSize=0.25`、`rotateStepDegrees=90` |
| 渲染 | 224×224、垂直 FOV 90°、depth 与 instance segmentation 开启 |
| 路线 | 覆盖式行走，保证每个受干预容器在干预后至少重访一次；动作总数上限 `L_max`（null）为机械保护线，执行中不截断 |
| 关键帧 | 每个保存的公开观察都是关键帧（沿用 `every_saved_public_observation`） |

**不可观测窗口干预** 解决"记忆必须在看不见时被世界改变"的问题。输入是当前视锥与已登记的可动物体，输出是干预日志。例如机器人在卧室时，客厅的杯子被移走、椅子被搬到厨房。它只在涉及容器不在当前视锥内时执行，判定沿用 D-199～D-204 的公开可见性机制；它不在视野内瞬移物体。

| 项 | 规则 |
|---|---|
| 数量 | 每 episode 至多 10 件可动物体（proposed） |
| 类型 | `remove`：移出场景；`move`：搬到同 house 另一可用容器；`add`：从该 house 自有物体池新增到可用容器 |
| 窗口 | 涉及的源/目标容器均不在当前视锥内；窗口起止帧写入 provenance |
| 失败 | 干预执行失败保留前缀，整条 episode 记 construction failure，不换物体、不换 house |

## 三、三种读取面

| 面 | 内容 | 谁可读 |
|---|---|---|
| `public` | 逐帧 RGB `uint8[224,224,3]`、米制 depth `float32[224,224]`、内参、以观测 0 为原点的因果相对位姿、关键帧间动作摘要、frame digest | 前端 reader、五个方法、候选/特征计算 |
| `private` | 逐帧 instance-mask stack、模拟器对象 ID 到稳定私有实体 ID 的映射、逐对象位置/旋转/可见性、干预日志、由此派生的逐帧"已不在原处"标签与 fragment 主导实例 ID | 只有封存后的 teacher 与评价器 |
| `provenance` | append-only 动作与干预 journal、单调时钟、setup 记录 | 只有审计 |

白话：public 是机器人自己能拿到的东西，private 是只有上帝视角才知道的答案，provenance 是操作流水。任何 candidate/model reader 不得挂载 private 与 provenance；违反即整批失败。

## 四、位姿与动作摘要

公开位姿是以观测 0 为原点、由已注册动作推算的因果相对位姿；真值世界位姿只进 private。关键帧间动作摘要记录两帧之间已完成动作的步数、动作直方图与名义位移，不记录逐步动作列表。它解决"逐动作太长而模型输入膨胀"的问题；它不是里程计创新，也不把未来动作回灌。

## 五、共享 cache 字段

| 字段 | 内容 |
|---|---|
| `fragments[]` | `fragment_id`（packet-local 匿名）、mask 像素数、深度有效率、三维点数、质心、AABB、描述子（ViT-S/14 384 维；S1 另存 ViT-B/14 768 维，S1-05 后只保留选中的一套） |
| `free_space` | 可靠深度射线穿过的体素集合与可靠性门 |
| `visibility` | 视锥内、深度表面之前的体素集合 |
| `surfaces[]` | 几何派生的水平支撑面 ID 与范围，供共享 `supported_by` 规则 |
| `frame_seal`、`episode_seal` | 逐帧与逐 episode 封印摘要 |

五个方法读取同一 cache 的等字节 clone；cache 不含 house ID、场景名、对象 ID 或任何 private 派生量。

## 六、标签与封存文件

| 文件 | 内容 | 生成时刻 |
|---|---|---|
| `recall_seal.json` | 每帧每个 fragment 的召回实体列表与顺序、BIRTH 列、digest | private 打开前 |
| `feature_matrix.npz` | 关联头、存在头、新建头的特征矩阵与列顺序、digest | private 打开前 |
| `labels.npz` | 逐 fragment 目标列（哪个实体或 BIRTH）、逐实体"已不在"标签、`recall_miss` 标记 | 封存后 |

标签定义（D-224-LQ 裁决 N、P、Q）：fragment 的主导实例按实例 mask 重叠占比判定，分母是 fragment 全部像素；主导实例等于实体证据的严格多数实例为关联正例；实体对应实例已被 `remove`、或其当前质心离实体记住的质心超过 `δ_moved`（proposed 0.5 m，合同内为 null）为"已不在"正例，只对 `active` 与 `dormant` 候选给出；正确实体不在召回集合记 `recall_miss`。修改任何 private 文件而保持 public 不变时，`recall_seal` 与 `feature_matrix` 逐字节不变。

## 七、评价文件

| 粒度 | 内容 |
|---|---|
| 逐帧 | 真值物体表（本帧在场且自 episode 开始至少可观察过一次的物体，含框与质心；裁决 Q）、仍在记忆里（`active` 或 `dormant`；裁决 L）的实体框、最大权匹配（3D IoU 0.3）、每个真值物体的 Stable/Appeared/Missing/Moved 状态、已移走/搬动物体的原位置与原位置是否已对方法可观察、MRR 分子分母、污染占比 |
| 逐实体 | 是否假撤回、身份是否连续（搬动前承载实体列表与首次带标签重见的分配；裁决 M）、恢复延迟（自干预处首次可观察帧起；裁决 O） |
| 逐 episode | contamination AUC、活动实体数、历史版本数、每帧运行时间、峰值内存、三分解计数 |
| 逐 house | 上述量的聚合，供配对 bootstrap |

## 八、强制泄漏检查

1. 部署 reader 白名单只含 `public` 与 cache；`private`、`provenance`、house ID、场景名不进入任何方法值。
2. `recall_seal` 与 `feature_matrix` 的 digest 在 `labels.npz` 生成前写入；teacher 只读 digest 指向的文件。
3. 私有扰动检查：换 instance map、干预日志或对象 ID 后，公开产物与未训练 logits 逐字节不变。
4. nuisance probe：只用路径、seed、帧号、house 序号不得预测任何标签。
5. test manifest 生成后封存，S3-05 只读一次。

## 九、状态

当前没有生成任何 episode、cache、标签或评价文件；SAM 2.1 与 DINOv2 ViT-B/14 资产尚未下载；所有数值待 S0 登记。
