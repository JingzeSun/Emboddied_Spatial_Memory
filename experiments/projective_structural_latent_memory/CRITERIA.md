# 评价指标与统计口径

状态：计划中，阈值待 HC-031 冻结。本文只定义指标，不声称已有结果。

## 1. 评价单位

- `observation region`：单帧结构区域，不等同于世界实体。
- `world node`：跨视角持续存在的世界记忆节点。
- `transaction`：对世界记忆的最小受控修改。
- `episode`：一段连续动作、观测和世界状态变化。
- `case`：带 oracle 与 corruption 的可复现实验单元。

所有微平均与宏平均都要报告；重复区域多的长序列不得支配总分。置信区间按 episode bootstrap 计算，随机种子随 run manifest 保存。

## 2. 绑定指标 B

| ID | 指标 | 定义 |
|---|---|---|
| B1 | Association P/R/F1 | 非 `NEW/UNRESOLVED` region 与 oracle world node 的匹配准确性 |
| B2 | Identity-switch rate | 一个 oracle node 在时间上被错误切换到另一预测 node 的次数 / 可比较转移数 |
| B3 | False-merge rate | 不同 oracle nodes 被合成一个预测 node 的比例 |
| B4 | Duplicate-birth rate | 已存在可绑定 node 时仍创建重复 node 的比例 |
| B5 | Reappearance consistency | 遮挡、离开视野后重现时回到原 node 的比例 |

`UNRESOLVED` 不直接计为误匹配，但单独报告 coverage-risk 曲线，防止靠全部拒识获得虚高精度。

## 3. 生长指标 G

| ID | 指标 | 定义 |
|---|---|---|
| G1 | Node-birth P/R/F1 | oracle 新世界区域首次出现时，`NEW + CREATE` 的检测质量 |
| G2 | Attachment exact match | 新节点的 parent Chart/Place、边类型与局部关系全部正确的比例 |
| G3 | Structural consistency | 创建后无非法 parent、互斥边或局部拓扑冲突的比例 |
| G4 | Coverage / hallucinated expansion | 已观测世界覆盖率与无证据扩张率成对报告 |

## 4. 记忆稳定性指标 M

| ID | 指标 | 定义 |
|---|---|---|
| M1 | Static retention / drift | 静态 node 在长时序中的保留率及 latent/geometry 漂移 |
| M2 | Dynamic contamination | 动态、短暂观测写入静态世界层的错误比例 |
| M3 | Lifecycle / visibility F1 | visible、occluded、out-of-view、inactive、retired 状态的分类质量 |

## 5. 修订指标 R

| ID | 指标 | 定义 |
|---|---|---|
| R1 | Transaction exact match | operation、target、scope、valid time 和 evidence 均正确 |
| R2 | Necessary-update recall | oracle 必须更新的事实中被正确处理的比例 |
| R3 | Control preservation / collateral edit | 控制项保持率与不相关事实被改动率成对报告 |
| R4 | Valid-time accuracy | 时点误差或时间区间 IoU，按任务类型报告 |
| R5 | Evidence/intervention score | evidence set 匹配度及干预后操作变化是否符合 oracle |
| R6 | Constraint pre/reject/post | 执行前约束满足率、非法交易拒绝率、执行后约束满足率 |

## 6. 预测投影指标 P

| ID | 指标 | 定义 |
|---|---|---|
| P1 | Expected-visibility score | 动作与位姿条件下，哪些 node 应进入视野的预测质量 |
| P2 | Projective-latent correspondence | 预测结构 latent 与真实 region 的检索/匹配质量 |
| P3 | Attachment/frontier prediction | 下一观测应连接到何处、是否越过已知 frontier 的准确性 |

如果移除 `PredictProject` 不损害 B/G/R 或 P 指标，则不能把系统称为 world model；只能称为带投影先验的结构记忆。

## 7. 下游与效率指标

| ID | 指标 | 定义 |
|---|---|---|
| T1 | Task score | 时间限定结构查询、目标重定位或导航任务的成功率/路径效率 |
| E1 | Runtime footprint | 单步延迟、峰值显存、活跃节点数、每米/每分钟增长率 |

## 8. 统计与报告要求

1. teacher-forced association 与 full rollout 分开报告。
2. seen scene、unseen layout、unseen appearance、dynamic shift 分桶报告。
3. 所有阈值只在 validation 上确定；test 只运行冻结版本。
4. 每个主要表至少报告均值、95% CI、种子数和失败 episode 数。
5. 不能用渲染器内部状态作为线上输入；若用于 oracle，必须明确标为 oracle-only。
6. 失败案例至少覆盖 false merge、duplicate birth、dynamic contamination、pose glitch 和 collateral edit。

## 9. 待确认

- 数值门槛、主指标与最小效果量：HC-031。
- 数据与 split：HC-033。
- 下游任务：HC-034。

