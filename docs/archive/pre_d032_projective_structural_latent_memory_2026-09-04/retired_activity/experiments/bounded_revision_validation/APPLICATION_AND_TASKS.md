# 应用切口与下游任务

## 主应用叙事

选择“共享室内设施中的移动资产与安全状态记忆”：仓库、实验室或医院后台区域中，推车、容器、门、通道状态会被人和机器人改变，多来源异步上报。

贡献不是识别椅子，而是回答：一条迟到或不充分的负证据是否足以关闭旧位置；冲突证据是否应隔离；一次移动应使哪些库存/巡检/安全任务失效；哪些无关资产必须完全保持。

这个切口满足：对象变化频繁、错误更新有成本、有效时间和 provenance 有实际意义，同时单人可用模拟器与公开重扫数据开展。

## 任务节点的角色

任务节点只用于测量事实错误的后果。例如：

```text
fact F1: at(cart_7, zone_A)
fact F2: blocks(cart_7, exit_2)
task T1: retrieve(cart_7, zone_A) depends_on F1
task T2: inspect(exit_2) depends_on F2
```

若只改变 F1，则 T1 失效，T2 不应重算。任务图用于评估错误派发与无关重算，不默认反向监督事实真假。

## 不作为主任务的送货超人叙事

“为避免前方拥堵是否超过行人”还需要意图预测、社会规范、轨迹规划和博弈，已超出 posterior updater。可在未来把更新后的结构化状态提供给 planner，但本论文不主张解决超车决策。

## 下游指标

- wrong-dispatch rate：因错误事实启动了不该启动的任务；
- missed-invalidation rate：前提已失效却未关闭任务；
- collateral-recompute rate：无关任务被重算的比例；
- task-cost regret：相对 oracle state 的额外代价，仅作为次级指标。

## C14 在应用实验中的纵列

| 指标 | 这个应用里是什么意思 | 计算 | 数字例子 | 人工决定 |
|---|---|---|---|---|
| wrong dispatch | 因旧/错事实派出不该执行的取货或巡检 | 错启/派发机会 | 6/100=6% | 分母与可逆任务范围，见HC-019 |
| missed invalidation | 事实失效但任务仍confirmed | 漏关/应失效 | 5/40=12.5% | 哪些depends_on是硬前提，见HC-003 |
| collateral recompute | 无关事实被污染导致多余重算 | 无关重算/无关任务 | 8/200=4% | 重算边界，见HC-019 |
| regret | 相对oracle state的额外行动成本 | predicted-oracle | 150-120=30 | 单位与应用语义 |
| optional composite | 行业权重合成 | `5W+10M+1R` | 6/5/8次→88 | 是否使用和权重，见HC-019 |

主表始终保留前三项，不能只显示 composite 88。
