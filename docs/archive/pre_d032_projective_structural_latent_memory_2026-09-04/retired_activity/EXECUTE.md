# EXECUTE：当前唯一执行入口

## 当前状态

阶段：**P0，后验任务与判尺冻结**。

已完成：D-024/D-025 主线与信息架构；D-026～D-030 已冻结 HC-018/Q01；D-031 已接受 Q02.1 的 schema-conditioned predicate registry 与次级 held-out predicate 泛化。

未完成：Q02.2 核心 stored/derived predicate 名单；其余关键语义；schema/executor/evaluator；任何数据下载、训练或验证。

## 实验对接协议

- 用户负责不可替代的研究判断：选择研究语义、风险偏好、评价门槛和资源上限；
- 实验对接人负责把每个答案追加为 D-XXX，更新合同/schema/fixture/config，实现并验证对应工作；
- 每次只退回一个会阻塞下一步的决策，附推荐项、替代项、数字例子和影响；
- 未得到回答的问题保持 `WAITING_USER`，不能把推荐项伪装成 accepted；
- 实现结果若反驳原设想，先报告反例，再把是否修改研究合同作为新的单项决策退回。

## 活动待办清单

状态含义：`DONE` 已完成；`WAITING_USER` 正等待用户决定；`BLOCKED` 被前项阻塞；`PLANNED` 已定义但尚未授权启动。

| ID | 状态 | 决策/工作 | 用户负责 | 实验对接人负责 | 完成标志 |
|---|---|---|---|---|---|
| Q01 | DONE | HC-018 第一批数据与判尺门 | D-026～D-030 已接受 | 已固定路线、规模、严格门、criteria与资源策略 | 第一批数据合同唯一且明确 |
| Q02 | WAITING_USER | HC-002 stored/derived facts | D-031 已接受开放registry与schema-conditioned updater；现决定核心 stored/derived 名单 | 更新 graph schema、标签说明和案例模板 | 任一 predicate 的编辑权限可判定 |
| Q03 | BLOCKED | HC-003 dependency closure | 决定依赖边类型、传播与停止规则 | 实现 closure oracle 和越界传播测试 | `M_t` 与 protected set 可重复计算 |
| Q04 | BLOCKED | HC-004 reliable negative evidence | 决定可见率、连续未检出和来源条件 | 实现 negative-evidence gate 与边界案例 | `absence/unknown/occluded` 不混淆 |
| Q05 | BLOCKED | HC-005 equivalent edits | 决定哪些事务序列语义等价 | 实现 canonicalization 和 set-valued oracle | 合理替代表达不被误判为错 |
| Q06 | BLOCKED | HC-015 valid time | 决定点标签、区间标签和容差 | 实现 event/arrival/valid-time evaluator | 迟到证据不会改写真实变化时间 |
| Q07 | BLOCKED | HC-016 commit/quarantine | 决定证据不足时的写入边界 | 实现 hard projection、拒绝原因和日志 | 破坏性编辑均通过提交门 |
| Q08 | BLOCKED | HC-013 C1–C15 | 决定主指标、hard gates 与继续阈值 | 固化 metric version、分子/分母和报告表 | 结果是否继续不靠临时解释 |
| Q09 | BLOCKED | HC-017 baseline fairness | 决定结构化资格与预算公平口径 | 完成 SA1–SA8 审计、adapter 和预算表 | 每个基线的输入/输出/结构能力可核查 |
| Q10 | BLOCKED | HC-019 task cost | 决定漏派、误派、迟派等错误代价 | 实现只读 task evaluator 和敏感性分析 | 下游价值不反向污染事实真值 |
| I01 | PLANNED | 第一批 smoke fixtures | 只复核争议 oracle | 制作、互审并保存 12/36 个 case contracts | oracle 100% 通过，故意错误被抓住 |
| I02 | PLANNED | Schema 与 deterministic executor | 无，除非出现新语义冲突 | 实现 validator、transaction executor、provenance | 原子写入、约束和失败日志有测试 |
| I03 | PLANNED | Evaluator 与 corruption tests | 审核无法机械判定的边界例 | 实现 C1–C15、raw counts、bootstrap 和校准 | 手算与程序结果一致 |
| E01 | PLANNED | 规则与统计基线 | 只决定发现的新公平性争议 | 运行 R0–R3，保存 manifest 和失败案例 | 确认任务不是被简单规则轻易解决 |
| E02 | PLANNED | 学习基线 | 只决定资源上限变化 | 训练 L0–L4，做参数/速度双匹配 | 比较对象足够强且可复现 |
| E03 | PLANNED | ESGBU 与消融 | 决定证据不支持时是否收缩 claim | 训练 M0、做消融、泛化、校准和反例分析 | 优势来自目标机制而非参数量 |
| E04 | PLANNED | AI2-THOR 轨 | 只确认下载/算力等新增资源 | 生成受控事件流并做跨场景测试 | 模拟器轨与 symbolic 轨分列报告 |
| E05 | PLANNED | 3RScan/3DSSG 外部轨 | 只确认许可/资源等新增约束 | 适配真实重扫并报告标签局限 | 不把区间或自动映射称为精确真值 |
| P01 | PLANNED | 发表判定 | 选择投稿梯级与风险偏好 | 对照 publication gates 组织结果和失败 | claim 不超过证据，目标目录另行核验 |

当前队首只有 `Q02.2`。Q01 已完整结束；Q02.1 已接受，其余项目不会越过核心谓词名单擅自启动。

## P0 产物

- accepted decision IDs；
- 12 个 case contracts（或用户选择的 AI2-THOR-first 合同）；
- metric version 与 hard-gate version；
- canonical input/output schema 草案；
- test access policy。

## P0 退出门

- 所有会改变 oracle 答案的语义已有 decision ID；
- 允许/禁止编辑、affected/protected、valid time、evidence set 与 task delta 可由人判定；
- 没有把 test 用于阈值或方案选择；
- 下一阶段只有一个可执行合同。

## 当前禁止

- 在 HC-018 规模、通过门和所需语义未冻结时把训练写成已授权启动；
- 为了“复杂”先训练大 VLM 或完整导航；
- 用七项以上重复 loss 掩盖输出定义不清；
- 只比 edit F1，不报保护、时间、证据、校准和任务后果；
- 把旧 archive 或原型当作活动合同；
- 宣称“已验证”“可投某刊”或“国内 A 类”而没有结果/认定表。

## 当前详细合同

唯一实验包：[`experiments/bounded_revision_validation/README.md`](experiments/bounded_revision_validation/README.md)。

如果今天只做一件事：回答 HC-002/Q02.2，冻结第一批可直接编辑的 stored predicates 与只能重算的 derived predicates。

跨对话时使用 [`docs/NEW_CHAT_HANDOFF_PROMPT.md`](docs/NEW_CHAT_HANDOFF_PROMPT.md)，但它不替代本文件。
