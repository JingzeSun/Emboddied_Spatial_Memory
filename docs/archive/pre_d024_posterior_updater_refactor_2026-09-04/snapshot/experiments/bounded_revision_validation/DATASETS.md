# 数据集与环境适配计划

状态：**候选方案；尚未下载、尚未跑通。** 数据集只提供场景和观测，不自动等于本项目需要的
revision ground truth。所有派生标注必须记录来源和生成规则。

## 0. Symbolic event streams：训练主轨与机制反证

AI2-THOR/3RScan 的原始规模和标注都不直接提供足量 transaction labels。第一训练轨由确定性 world-event simulator 生成 reified fact graph、typed dependency、evidence event 与合法 revision：

~~~text
world events
  → delayed/noisy observations from multiple sources
  → observed_at / received_at / source_id / evidence_group_id
  → gold preserve/quarantine/commit + targets/operators
  → executor-derived affected/control/stop + valid interval/version
~~~

生成器独立采样 object/relation 名称、事件顺序、arrival delay、source reliability、coverage、dependency depth、control size 与 graph size。每个样本保存随机 seed、generator version、factor values 和 decision IDs。

建议起始规模：30k train、5k validation、5k ID test、5k OOD transactions。train/validation/test 按 template family、environment seed 与 counterfactual group 分组；test 的 OOD 组合在训练前写入 manifest，不用其结果改生成器。

symbolic track 只能证明机制在合同世界里可学习，不能证明真实视觉适用。因此它必须由 AI2-THOR 的可控观测和 3RScan/Dyn-THOR 的外部有效性轨道补充。

## 1. AI2-THOR / Rearrangement：可控动态与反事实实验床

官方 Rearrangement 任务会在两个阶段之间随机改变 1–5 个对象的位置、朝向或 openness，
并提供第一视角 RGB、深度和 perfect egomotion，适合生成可重复的 posterior 冲突。

建议用途：

- 精确控制对象移动、容器开闭、遮挡、重观测位置和变化时刻；
- 生成 R1 移位、R3 可靠缺失但去向未知、R4 遮挡、R6 稳定/停止；
- 用 metadata 构造实体 ID、pose、`parentReceptacles`、`receptacleObjectIds` 等真值；
- 用 action log 得到物理变化时刻，校验 HC-015 的 censored interval。

关键限制：metadata 的 `visible=false` 同时受视野、距离和遮挡影响，绝不能直接作为可靠负证据。
R2“推车移动导致隐藏箱子关系传播”需要自定义 scripted scene 或等价容器/承载关系。

首个最小切片：4 个房间 × 5 个 seed × 6 个 posterior 模板 = 120 cases；先只跑 oracle perception、
oracle identity、oracle dependency，验证 revision evaluator。

官方入口：

- Rearrangement：https://ai2thor.allenai.org/rearrangement/
- Object metadata：https://ai2thor.allenai.org/ithor/documentation/environment-state/
- Object types/relations：https://ai2thor.allenai.org/ithor/documentation/objects/object-types/

## 2. 3RScan + 3DSSG：真实重扫场景的外部效度

3RScan 含 478 个变化室内环境、1482 次重建/快照，提供 RGB-D、相机位姿、跨序列全局对齐、
固定实例 ID 和对象变换标注。3DSSG 在其上提供对象节点与空间关系，可用来生成跨扫描事实差分。

建议用途：

- 测试真实传感噪声、长期重扫、对象重定位和关系变化；
- 用固定实例 ID 检查身份保持；
- 用 3DSSG 的 `objects.json` / `relationships.json` 生成 snapshot gold；
- 作为 AI2-THOR 规则是否能迁移到真实数据的 secondary track。

关键限制：扫描间通常只知道“上次仍成立、这次已变化”，并不知道真实物理变化瞬间；因此默认
gold 是 `(last_supported_at, first_contradicted_at]`，不能伪造精确 `changed_at`。数据也不天然提供
本项目的 evidence group、control set、typed operation 和 dependency closure，必须人工或规则派生并抽检。

最小切片建议：先选 10 个 reference/rescan 组，每组 3–5 个明确对象变化；逐例人工确认实体对齐、
必要关系、控制事实和可见性，再扩展。不同数据集不合并成一个总平均分。

官方入口：

- 3RScan：https://github.com/WaldJohannaU/3RScan
- ICCV 2019 论文：https://openaccess.thecvf.com/content_ICCV_2019/html/Wald_RIO_3D_Object_Instance_Re-Localization_in_Changing_Indoor_Environments_ICCV_2019_paper.html
- 3DSSG：https://3dssg.github.io/

## 3. Dyn-THOR / DSG：直接重叠审计集

2026-09-01 的 DSG 预印本提出面向变化室内环境的动态 3D 场景图，使用 Dyn-THOR（20 个
序列、3326 个关键帧、每序列最多 10 个移动对象）评测 Stable/Appeared/Missing 节点和空间关系。

它适合作为“动态节点/边快照质量”的直接相关基线或数据来源，但当前公开论文主要评估 node/edge
matching；本项目仍需另加 operation log、affected/control、证据来源、有效时间和版本事务标注。

入口：https://arxiv.org/abs/2609.00619

## 4. 数据轨道不要混成一项

| Track | 上游 | 回答的问题 |
|---|---|---|
| T0 Hand-authored fixtures | 全 oracle | 规则、事务和 evaluator 是否正确 |
| T1 Symbolic event streams | oracle facts + controlled evidence noise | BEGR-Net 是否学到双时间/依赖修订规律 |
| T2 AI2-THOR scripted | oracle observation/identity | 后验算法在精确可控变化下是否成立 |
| T3 AI2-THOR noisy | 注入检测/关联/可见性噪声 | 对上游错误是否稳健 |
| T4 3RScan+3DSSG curated | 真实扫描 + 人工抽检 gold | 能否迁移到真实长期变化 |
| T5 Dyn-THOR compatible | 按 DSG 共同输出评测 | 与动态场景图工作重叠部分表现如何 |

不得用 T2–T5 的测试场景来决定 T0/T1 的规则、生成因子或阈值。
