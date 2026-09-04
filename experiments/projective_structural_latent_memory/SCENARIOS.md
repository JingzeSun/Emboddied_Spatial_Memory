# 最小场景族

状态：计划中。场景 ID 固定，具体资产和阈值待 HC-020、HC-031、HC-033。

每个场景必须包含：初始世界、动作序列、逐帧观测、oracle region-to-node 绑定、oracle transaction、至少四类 corruption，以及预期保持不变的控制项。

| ID | 场景 | 核心 oracle | 主要指标 |
|---|---|---|---|
| S00 | 原地旋转看到同一面墙 | `BIND` 到同一 surface node；不得重复创建 | B1, B4, M1 |
| S01 | 平移与大视角变化后重见对象 | `BIND/REACTIVATE` 原 node | B1, B2, B5, P2 |
| S02 | 转角时两个 Chart 短暂重叠 | region 分别绑定，跨 Chart 关系保持 | B3, G2, G3 |
| S03 | 推进后首次看到新走廊 | `NEW + CREATE + ATTACH` 到正确 frontier | G1–G4, P3 |
| S04 | 外观相同但无重叠的另一走廊 | 创建新 node，不因语义相似误绑定 | B3, B4, G1 |
| S05 | 局部遮挡后恢复 | `PRESERVE`，恢复后回原 node | B5, M1, M3 |
| S06 | 行人短暂遮挡门 | 行人为 transient track；门保持 occluded | M2, M3, R3 |
| S07 | 行人短暂停留在墙前 | 不得把其融合成 wall/surface | B3, M2, R6 |
| S08 | 椅子被移动到新位置 | 同一实体 identity，`RELINK/REPLACE` 空间事实 | R1–R5 |
| S09 | 可靠缺失但新位置未知 | 撤回旧位置，不捏造新位置 | R1, R2, R3, R6 |
| S10 | 单一表面在观测中 split/merge | 多 region 仍可指向同一 world node | B1, B3, R3 |
| S11 | 位姿瞬时故障 | `QUARANTINE/UNRESOLVED`，不得大规模 birth | B4, G4, R6 |

## Corruption 族

每个 case 从下列类别选择至少四种，且 corruption 参数写入 manifest：

- 视觉：模糊、光照、纹理重复、局部遮挡、proposal split/merge。
- 几何：深度缺失、深度噪声、内参扰动、位姿漂移或跳变。
- 时间：掉帧、乱序、长时间离开视野、突然出现/消失。
- 动态：可移动物体换位、行人穿行、门开合。
- 语义：同类实例、错误标签、未知类别。

## Oracle 边界

- `observation region` 与 `world node` 必须独立编号。
- “同一世界节点”的判定规则由 HC-024 冻结。
- `NEW` 只表示无可绑定的现有节点；是否立即 `CREATE` 由 HC-025 冻结。
- 位姿/深度是否作为线上输入由 HC-021 冻结；oracle 可持有更强信息，但不得泄漏给模型。

## 最小通过逻辑

场景通过不是“最终图看起来合理”，而是：

1. 绑定或拒识正确；
2. transaction 与 oracle 一致；
3. 控制项未被修改；
4. 执行前后约束可审计；
5. 结果能由保存的输入与版本确定性重放。

