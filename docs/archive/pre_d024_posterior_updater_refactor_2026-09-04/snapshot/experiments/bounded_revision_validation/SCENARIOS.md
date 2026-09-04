# 场景与指标矩阵（窄版草案）

状态：`draft / not implemented / not ground truth`

本表沿用 HC-013 的组织方法：每个场景固定上游输入，只改变一个主要因素；硬门槛先于软指标。原 P1–P3 的 19 个模板完整保留，新增 8 个 P4 双时间/多来源模板，共 27 个；`smoke=yes` 的 12 个场景仍是首轮 executor/evaluator 范围。

## P1：证据路径判别

| ID | smoke | 场景 | 唯一主要变化 | 正确路径 | 重点指标/硬门槛 |
|---|---|---|---|---|---|
| P1-S01 | yes | 同一杯子从桌 A 出现在桌 B，A 可见且为空 | 新位置正证据 + 旧位置可靠负证据 | `relocation + commit` | relocation recall；不得保留两个 current location |
| P1-S02 | yes | 桌 B 出现外观相似但实例 ID 不同的杯子 | 身份不一致 | `new_instance + commit` | new-instance precision；不得错误合并 |
| P1-S03 | yes | 原位置完全可见且为空，其他位置未知 | 只有可靠负证据 | `reliable_absence + commit` | absence precision；不得编造新位置 |
| P1-S04 | yes | 原位置被箱子遮挡 | 可见性变为 occluded | `occluded + preserve` | false-revision=0（硬门槛） |
| P1-S05 | no | 相机转向另一侧，原位置在视野外 | 可见性变为 out-of-FOV | `out_of_fov + preserve` | false-revision=0（硬门槛） |
| P1-S06 | yes | 深度与位姿冲突导致投影不一致 | 传感器/位姿质量失败 | `sensor_conflict + quarantine` | commit=0（硬门槛） |

P1 聚合报告：六类 macro-F1；逐类 precision/recall；commit precision/recall；quarantine coverage；保护类 false-revision rate。不能只报 accuracy，因为保护类通常更容易占多数。

## P2：时序事实编辑

| ID | smoke | 场景 | 固定的正确变化类型 | 必需编辑 | 重点指标/硬门槛 |
|---|---|---|---|---|---|
| P2-S01 | yes | 杯子 A→B，真实移动时刻已知 | relocation | 旧位置失效 + 新位置生效 + 双向 provenance | fact-edit P/R；时间覆盖 |
| P2-S02 | no | 门从 closed→open | state_change | `SUPERSEDE(closed, open)` | 互斥状态不得重叠 |
| P2-S03 | no | 盒子从桌面被拿起 | relation_removal | `INVALIDATE(on(box,table))` | operator accuracy；不得删除实体 |
| P2-S04 | yes | 上次在 t0，首次发现变化在 t1，真实时刻未知 | relocation | 输出删失区间，不伪造点时间 | interval legality（硬门槛） |
| P2-S05 | yes | 提交时 base graph 已被另一事务更新 | stale_base | 拒绝或重算后原子提交 | stale-write rejection=1 |
| P2-S06 | no | 两种操作序列得到相同合法当前图和历史 | equivalent_edits | 命中 acceptable set | 不用字符串 exact match 误杀 |

P2 聚合报告：acceptable-set operator accuracy；fact-edit precision/recall/F1；interval coverage/width；provenance completeness；stale-write rejection；atomic commit rate。时间真值未知的样例不得进入 point-time MAE。

## P3：依赖范围与停止条件

| ID | smoke | 场景 | 固定的主编辑 | 必需传播/停止 | 重点指标/硬门槛 |
|---|---|---|---|---|---|
| P3-S01 | yes | 小车移动，箱子仍受其支撑 | relink cart location | 更新箱子派生位置；保留无关植物 | propagation recall；control preservation=1 |
| P3-S02 | yes | 小车移动，但箱子已从车上取下 | relink cart + invalidate support | 不再传播箱子位置 | stop-edge accuracy |
| P3-S03 | no | 标签 rigidly-attached 于移动货架 | relink shelf | 标签随货架更新 | attached dependency recall |
| P3-S04 | yes | 房间包含多件物体，其中只有桌子移动 | relink table | 在 `contains(room,*)` 泛化边停止 | collateral revision=0（硬门槛） |
| P3-S05 | no | 移动对象改变 derived `near` 关系 | relink object | 只重算局部 near 候选 | scope precision + relation recall |
| P3-S06 | yes | 依赖数据中存在 A↔B 环 | relink A | 有限闭包并报告 cycle | 必须终止（硬门槛） |
| P3-S07 | no | 两个房间各发生一次独立变化 | two primary edits | 两个闭包隔离、事务结果可合并 | independent-change isolation |

P3 聚合报告：required-propagation recall；scope precision；control preservation；collateral revision rate；stop-edge accuracy；cycle termination；independent-change isolation。

## P4：双时间与多来源证据

| ID | smoke | 场景 | 唯一主要变化 | 必需决策 | 重点指标/硬门槛 |
|---|---|---|---|---|---|
| P4-S01 | no | t=12 的搬迁证据到 t=20 才收到 | arrival delay | 在 transaction t=20 修订覆盖 t=12 的 valid interval | TV1/TV4；不得把 arrival 当 change |
| P4-S02 | no | t=20 收到的帧实际拍于 t=8，旧事实在 t=10 又被支持 | stale event time | preserve/quarantine | EG4；不得 latest-arrival overwrite |
| P4-S03 | no | camera-A 与 robot-B 独立支持相反位置 | source conflict | quarantine 两分支 | ST4=0；保留双 provenance |
| P4-S04 | no | 同一扫视连续 10 帧均未见对象 | duplicate evidence | 只计 1 evidence group | 不得因帧数越过 absence gate |
| P4-S05 | no | P4-S03 后第三个独立高质量来源支持 A | independent witness | 按冻结规则 resolve 或继续 quarantine | evidence attribution；source ablation |
| P4-S06 | no | 迟到证据使历史中间区间失效，但当前状态不变 | retroactive correction | 修历史版本、不制造 current edit | version replay；current control preservation |
| P4-S07 | no | 两个合法事件几乎同时到达且共享 base version | transaction order | reject/rebase 后原子提交 | stale-write rejection；deterministic replay |
| P4-S08 | no | test 出现未见 source ID 与更长 delay | source/delay OOD | 保持校准或 abstain | LM5/LM6/LM8；unsafe commit 单列 |

P4-S01/S02、P4-S03/S05 与 P4-S04 的单组/双组版本必须组成 counterfactual pairs。P4 不用真实变化点标签时只评 interval coverage/width，不计算 point-time MAE。

## 12 个 smoke 用例

首轮只实现：

```text
P1-S01 P1-S02 P1-S03 P1-S04 P1-S06
P2-S01 P2-S04 P2-S05
P3-S01 P3-S02 P3-S04 P3-S06
```

它们覆盖：正变化、相似新实例、可靠缺失、遮挡保护、传感器冲突、已知/未知变化时间、并发版本冲突、必要传播、停止边、无关事实保护与依赖环。

smoke 只用于验证 schema、executor 和 evaluator 是否按合同工作，逐例报 pass/fail，不报告 macro-F1、置信区间或方法优越性。P1-S05 等非 smoke 类别补齐并生成平衡实例后，才计算正式分类指标。

## 配对反事实规则

每个模板扩展数据时至少生成一对只差一个字段的反事实，例如：

- `visible=true` 与 `occluded=true`；
- `identity_match=true` 与 `false`；
- `support_active=true` 与 `false`；
- `base_version=current` 与 `stale`。
- `observed_at=12, received_at=20` 与同步到达；
- 同一组 10 帧与两个位置独立采集的 2 组证据；
- typed dependency edge 存在、移除或关系类型打乱。

成对样例分别计分，并额外报告 pair consistency。这样可以检查系统是否真正使用关键证据，而不是凭对象类别或常见位置猜答案。

## 指标计算口径

设 oracle 必须修改事实集合为 `R`，系统实际修改集合为 `A`，保护控制事实集合为 `C`：

```text
required_propagation_recall = |A ∩ R| / |R|
scope_precision             = |A ∩ R| / |A|
collateral_revision_rate    = |A ∩ C| / |C|
control_preservation        = 1 - collateral_revision_rate
```

若 `A` 为空，只有在 `R` 也为空时 scope precision 才记为 1；否则记为 0。除聚合值外必须保存每个 case 的集合差异，避免平均数隐藏结构错误。

## 计分资格

- 变化检测只有在旧事实曾被可靠确认、相关区域本轮可判定且身份条件明确时才计入 commit recall。
- 不满足资格的样例进入 occlusion/out-of-FOV/conflict 保护指标，不能当成“没检测到变化”。
- oracle 上游与 estimated 上游分开报告。
- hard failure 数量始终单列；即使平均 F1 较高，也不能抵消破坏性错误。
