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

