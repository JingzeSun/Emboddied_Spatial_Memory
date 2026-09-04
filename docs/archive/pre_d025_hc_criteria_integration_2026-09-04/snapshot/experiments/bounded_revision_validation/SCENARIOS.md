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

每个 family 至少有 positive、no-change control 和 counterfactual 三例，正式规模由 HC-018 与 CRITERIA 冻结。

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

