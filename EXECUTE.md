# EXECUTE：当前唯一执行入口

## 当前状态

阶段：**P0，Projective Structural Latent Memory 的状态、oracle 与判尺冻结**。

已完成：D-032 接受主线 supersession；旧 ESGBU 活动文件完成 72 文件快照并退役；新入口、合同和实验包正在按同一主线重建。

未完成：HC-020～HC-034；v0.1 schema 冻结、executor/evaluator；任何数据生成、模型实现、训练或验证。

## 当前活动队列

| ID | 状态 | 决策/工作 | 完成标志 |
|---|---|---|---|
| Q00 | DONE | D-032 主线与归档 | 旧方案可恢复，新主线唯一 |
| Q01 | WAITING_USER | HC-020 第一批 smoke 路线 | 冻结12个序列还是 simulator-first |
| Q02 | BLOCKED | HC-021 输入与 oracle 来源 | RGB/depth/pose/action/时间字段唯一 |
| Q03 | BLOCKED | HC-022 structural tokenizer | region 定义、VP角色和等价分区可判 |
| Q04 | BLOCKED | HC-023 memory hierarchy | Chart/Place/slot/track 的存储边界唯一 |
| Q05 | BLOCKED | HC-024 binding identity | BIND/NEW/REACTIVATE/SPLIT/MERGE 真值可复核 |
| Q06 | BLOCKED | HC-025 birth/confirmation | candidate 何时成为 persistent node 可复核 |
| Q07 | BLOCKED | HC-026 Chart attachment | 新节点/新区域怎样连接旧 world graph 可复核 |
| Q08 | BLOCKED | HC-027 lifecycle/visibility | transient、occluded、absent、removed 不混淆 |
| Q09 | BLOCKED | HC-028 latent state/update | prototype、distribution、evidence bank 与写入规则冻结 |
| Q10 | BLOCKED | HC-029 revision transaction | 旧 ESGBU 子模块的 operator/scope/stop 冻结 |
| Q11 | BLOCKED | HC-030 time/provenance/quarantine | 破坏性提交和历史版本语义冻结 |
| Q12 | BLOCKED | HC-031 metrics/gates | B/G/M/R/P/T/E 指标与硬门冻结 |
| Q13 | BLOCKED | HC-032 baseline fairness | 同前端、同预算和 native-system 边界冻结 |
| Q14 | BLOCKED | HC-033 datasets/splits | 场景、轨迹、房间与模板不泄漏 |
| Q15 | BLOCKED | HC-034 downstream task | query、navigation 或 planning 的只读评估冻结 |
| I01 | PLANNED | schema + deterministic executor | transaction 可原子执行和完整回放 |
| I02 | PLANNED | evaluator + deliberate corruptions | oracle 全收、故意错误全拒绝 |
| E01 | PLANNED | deterministic baselines | 验证任务不被简单几何/规则解决 |
| E02 | PLANNED | learned binding/growth pilot | 学习超过强规则且不是只靠前端 |
| E03 | PLANNED | full PSLM + ablations | project/bind/grow/revise 各自有证据 |
| E04 | PLANNED | simulator ID/OOD | 多轴 OOD 与长期增长稳定 |
| E05 | PLANNED | external/real sequence | 外部有效性与真实失败边界 |

## P0 必须冻结的对象

- `ObservationRegion` 与 region equivalence；
- persistent node identity、Chart/Place attachment 与 split/merge；
- candidate/confirmed/transient/retired 生命周期；
- `A_t` association 与 `U_t` transaction oracle；
- projection、visibility、time、evidence 和 protected controls；
- metric version、test access policy 和 baseline adapters。

## P0 退出门

- 人能对同一短序列独立得到一致的 binding、birth、attachment 与 revision 标签；
- oracle 事务可被 executor 100% 接受；
- 单因素 deliberate corruption 均被 evaluator 拒绝并命中预期错误码；
- 固定 patch、pose-warp、slot fusion 和 full recomputation 至少各暴露一个预期失败；
- 未查看正式 test，下一阶段只有一个可执行合同。

## 当前禁止

- 把 DINO、VP、3D node、scene graph 或在线扩图本身写成创新；
- 在 binding/birth oracle 未冻结前直接训练大模型；
- 用导航成功率替代 memory identity、growth 和 revision 指标；
- 把预测但未观测的 latent 直接写成 confirmed fact；
- 把旧 `bounded_revision_validation` archive 与新实验包混用；
- 宣称已实现、已验证或可投某刊。

如果现在只做一件事：打开 [`HC-020`](docs/human_confirmation/HC-020.md)，冻结第一批可执行验证路线。
