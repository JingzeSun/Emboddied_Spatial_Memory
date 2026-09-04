# 场景族与控制变量

## 因子设计

每个实验只改变计划中的因子，其他输入固定或分层随机化。

| 因子 | 初始水平 | 要排除的混淆 |
|---|---|---|
| evidence delay | 0 / 30 / 300 / 900 s | 不与 source reliability 同时只升不降 |
| arrival disorder | 0 / 25% / 50% | 与 event time 分开记录 |
| visibility | 0.2 / 0.6 / 0.9 | negative evidence 不能只看 detected=false |
| source reliability | 0.55 / 0.8 / 0.95 | 训练/测试来源 ID 解耦 |
| conflict rate | 0 / 0.25 / 0.5 | 保持实际 change rate 相同 |
| change rate | 0.05 / 0.2 / 0.5 | 保留 no-change controls |
| dependency depth | 0 / 1 / 3 / 5 | 图规模单独控制 |
| graph facts | 25 / 100 / 500 / 2000 | 候选检索召回固定 |
| evidence grouping | independent / correlated | 防止重复帧被当独立票数 |

具体水平是 pilot 候选，不是已冻结 CRITERIA。

## 12 个最小 smoke families

| ID | 唯一主要变化 | 正确行为 | 专门抓什么 bug |
|---|---|---|---|
| S00 | 强正证据给出新位置 | REPLACE 旧位置 | 基本事务 |
| S01 | 迟到证据描述更旧位置 | KEEP 当前事实 | last-arrival-wins |
| S02 | 低可见率未检测 | KEEP/QUARANTINE | 缺失即撤回 |
| S03 | 高覆盖可靠负证据 | RETRACT，位置变 unknown | 虚构新位置 |
| S04 | 两个高可信来源冲突 | QUARANTINE | 强行二选一 |
| S05 | 十帧同组弱证据 | 不当十个独立证据 | 重复计票 |
| S06 | 两个独立弱来源累积 | 达门后提交 | 不能累积证据 |
| S07 | 前提变化有两级依赖 | 只改最小闭包 | 漏传播 |
| S08 | 相似但无依赖的控制事实 | 完全保持 | collateral edit |
| S09 | 真实变化只知区间 | 输出合法区间 | arrival=valid time |
| S10 | 同一事件重复到达 | 幂等 | 重复写版本 |
| S11 | 某事实只影响一个任务 | 只失效相关任务 | 全图/全任务重算 |

D-027 固定两阶段：T0a 先为每个 family 做1个代表案例，并各配3个 deliberate corruptions，共12个语义案例/48个评价器输入；判尺稳定后，T0b 扩为每个 family 的 positive、no-change control 和 counterfactual，总计36个语义案例/144个评价器输入。corruption 是破坏 oracle output，不能与三种语义案例混称。

## AI2-THOR 场景模板

- movable asset：推车/容器从 A 移至 B，机器人看到全部或部分过程；
- occlusion：物体被柜门、家具或视角遮挡，形成不充分负证据；
- asynchronous fleet：两个虚拟机器人按不同延迟上传；
- state relation：门/柜开关影响通行或任务依赖；
- stale replay：旧帧或旧消息在新状态后到达；
- correlated burst：同一轨迹连续帧共享 group ID。

同一物理 episode 可以派生多个接收队列，但 train/test 不可共享底层 episode。

## 3RScan 场景模板

- object moved / removed / added；
- support 或邻接关系改变；
- 房间整体不变但局部事实变化；
- 扫描覆盖差异造成“疑似变化”；
- 多处变化但只有局部任务依赖。

对覆盖不足无法判定的案例标 `indeterminate`，不强塞进 RETRACT 标签。

## 每个 smoke family 的 Criteria 纵列

| Family | 本场景主要判什么 | Primary Criteria | 数字例子/预期失败 | 关联 HC |
|---|---|---|---|---|
| S00 basic replace | 基本编辑事务整体正确 | C1/C2/C8/C10 | 状态对但时间/证据错，C2仍=0 | 002/005/015/016 |
| S01 stale arrival | 晚到旧证据不覆盖新事实 | C1/C2/C5/C8 | event=602、当前事实从720成立、arrival=968，应KEEP | 015/016 |
| S02 weak negative | 不充分缺失不能撤回 | C1/C5/C12 | visibility=.2时RETRACT记FP | 004/016 |
| S03 reliable absence | 可靠缺失应关闭旧址但不造新址 | C1/C3/C8/C10 | 20例应撤回只改18，NUR=90% | 004/015/016 |
| S04 source conflict | 高可信冲突应隔离 | C1/C2/C12/C13 | .86 vs .84强行选边，transaction失败 | 016 |
| S05 correlated burst | 同组十帧不能当十票 | C10/C11/C12 | 6条选证据仅2条必要，冗余66.7% | 004/016 |
| S06 independent accumulation | 独立弱证据可累积 | C1/C10/C11/C12 | 两来源各.70是否过门只由validation | 016 |
| S07 dependency closure | 必要依赖不能漏 | C3/C4/C7/C14 | 真8选10命中7，mask F1=77.8% | 003/013 |
| S08 protected control | 相似但无依赖事实不变 | C5/C6 | 200 controls误改1，CPR=99.5% | 003/013 |
| S09 interval time | 真实变化只有区间 | C2/C9 | coverage=91%且width=38s，二者一起报 | 015 |
| S10 duplicate arrival | 重复事件幂等 | C2/C5/C13 | 同evidence重复到达不得新增version | 005/016 |
| S11 task boundary | 只失效相关任务 | C7/C14/C15 | 应失效40漏5=12.5%；无关200重算8=4% | 003/019 |

每个 family 的 positive/control/counterfactual 共用同一 Primary Criteria；如果新增因子改变评分语义，必须先回到对应 HC，而不是在代码里临时解释。
