# VSMT-lean: Versioned Entity-Lifecycle Memory Transactions（精简版）

> **English summary.** VSMT-lean studies how an embodied agent should *revise* an object-level memory while it revisits a house with RGB-D observations. Every frame, one joint assignment over the current anonymous fragments and the recalled memory entities yields a legal program of five atomic operations — **NOOP, BIND, BIRTH, RETRACT, REACTIVATE** — which is executed on an immutable previous version and committed as a new, traceable version. RETRACT only closes a version and REACTIVATE restores the same identity, so revisions are reversible. REPLACE is a composite (RETRACT + BIRTH). **MERGE exists only as a deterministic de-duplication rule shared identically by all compared methods; it is not a learned operation. SPLIT and RELINK, place/topology revision and relation edges are out of scope for the first paper.** The model is a frozen public frontend (simulator instance segmentation exposing mask geometry only for the main table, SAM 2.1 as a robustness appendix; RGB-D geometry; frozen DINOv2 descriptors with a shared ReID projection), three small MLP cost heads (54,207 parameters in total) and one rectangular Hungarian assignment per frame, trained with hindsight labels from private instance ground truth under a candidate-before-teacher information boundary. Status: contracts, data generation, frontend caches, runner, teacher and evaluator are implemented and server-tested; the development table is being run; **no validation or test result exists yet, so no performance claim is made.**

当前第一篇论文唯一主题是 **VSMT-lean（实体生命周期版本化事务，D-224，2026-09-19 批准）**：机器人持续接收 RGB-D 观测并重访时，对象级记忆里的每个实体应当保持、绑定新证据、新建、撤回还是恢复。每帧由一次帧级联合分配给出一个合法程序，在同一不可变旧版本上执行并提交为可追溯的新版本。

白话：它解决"原来那把椅子现在看不见，是被挡住、走出视野、检测漏了，还是真的被搬走"的判断。输入是截至当前帧的匿名色块（fragment）、公开几何、自由空间与可见体积，以及系统自己此前预测的实体记忆；输出是本帧一个合法程序和新记忆版本。例如杯子原位置连续被可靠自由空间覆盖、另一张桌面出现高相似色块，程序应把旧杯子 REACTIVATE 到新位置，而不是删旧建新。它不等于普通对象跟踪的别名，不训练视觉前端，也不把执行器、DINOv2 或五个操作名字单独当作创新。

## 操作词表（首篇）

| 操作 | 含义 | 首篇地位 |
|---|---|---|
| NOOP | 实体本帧不变 | 学习决定 |
| BIND | 把本帧色块作为新证据绑到已有实体 | 学习决定 |
| BIRTH | 为色块新建实体 | 学习决定 |
| RETRACT | 关闭实体的当前版本（不物理删除历史） | 学习决定 |
| REACTIVATE | 恢复已撤回或休眠实体的同一身份 | 学习决定 |
| REPLACE | RETRACT＋BIRTH 的复合程序 | 不是独立原子 |
| MERGE | 五个方法逐字节相同执行的确定性去重（余弦、质心距离、框重叠同时满足才合并） | 共享规则，不是学习操作，不进入方法差异 |
| SPLIT、RELINK、地点/拓扑修订、关系边 | — | **不进入首篇** |

休眠（dormant）是共享的确定性规则：连续应可见却没匹配达到登记次数的实体转为 dormant，档案不删。

## 模型与前端

- **冻结公开前端（裁决 72，2026-09-25）**：主表的色块来自模拟器实例分割，只暴露 mask 几何，不暴露标签、对象 ID、位姿或真值盒；跨帧是不是同一实体仍由方法判断。SAM 2.1 自动分割前端作为鲁棒性附录。两种前端共用同一 DINOv2 描述子（经五个方法共享的 ReID 线性投影）、同一深度几何、自由空间与可见体积。
- **学习部分**：三个 MLP 代价头（关联、新建、存在，合计 54,207 参数）加每帧一次矩形匈牙利分配。它不是 VLM，也不是图网络。
- **监督与信息边界**：召回集合与特征矩阵在任何私有文件打开之前封存；teacher 只用 t 时刻私有实例真值给已封存的候选打标签，不插入、删除或重排候选。错误分成 recall miss（正确实体没被召回）、teacher error（标签含糊）、amortization error（标签明确而学生选错）三类，分开记账。

## 对照、消融与指标

- **主比较**：VSMT-lean、TAF、ELU-P、RAC、LOW。四个对照是按公开论文机制在同一接口上独立实现的适配器，不是官方复现。
- **消融**：NoVersion、HandCost、HeuristicLabel、AssocOnly。其中 AssocOnly 使用同一学习关联头，但词表只剩 BIND 与 BIRTH，是核心贡献唯一的因果反事实，主表必须并列报告。LLM-op 是只在 validation 上跑的附录臂。
- **数据**：ProcTHOR-10K 多 house 覆盖式重访，加不可观测窗口内的物体移走、新增与搬动干预。划分已冻结：validation 50 栋、test 100 栋，训练规模在 S3-01 登记。
- **指标**：
  - 节点 P/R/F1 的主列是质心 ≤ δ_moved（0.5 m）的最大权匹配，也是选参指标；IoU 0.3 为次级列，与 Dyn-THOR 是同一匹配机制、不同重叠判定。
  - Missing 残留率、身份连续率是主门指标。
  - 另报假撤回率、恢复延迟、contamination AUC、规模与成本。
  - test 只跑一次。

## 当前状态（2026-09-25）

| 已实现并通过服务器测试 | 进行中 | 计划中 |
|---|---|---|
| S0 五份机器合同；S1 数据生成（开发用 50 栋，39 栋成功）、SAM2 与实例分割两份前端 cache、前端诊断与 ReID 投影；S2 runner、teacher、评价器与开发表编排 | S2-05 开发表：实例分割 cache 上的校准趟 | ELU-P 拟合、两轮 DAgger 训练、开发表；S3 正式数据、训练、validation 选参与一次性 test；论文 |

尚无 validation 或 test 结果，**不作任何性能主张**。完整进度与失败记录见 EXECUTE。

## 分支说明

GitHub 默认分支 `main` 可能落后，当前工作推送在 `s1-02a-runner` 分支。旧 CPMT、空间世界模型、地点双层记忆、统一四类图、八原子枚举与结构估计器的全部文档、代码说明与证据链保留在分支 `archive/pre-d224-unified-graph`（HEAD e1c19f6）；那里的八原子方案（含 SPLIT、RELINK、MERGE 学习）已被 D-224 取代。旧源码文件仍在本分支树中，只作历史与复用来源，不进入任何当前入口。

## 阅读入口

| 你要看什么 | 唯一位置 |
|---|---|
| 下一步、阶段计划和代码审查节点 | [docs/PLAN.md](docs/PLAN.md) |
| 方法、模型、对照、消融与指标 | [docs/METHOD.md](docs/METHOD.md) |
| 数据来源、划分、干预、字段与泄漏检查 | [docs/DATA.md](docs/DATA.md) |
| 已发生的实验、失败、结果与主张状态 | [EXECUTE.md](EXECUTE.md) |
| 方法、预算与工作规则的变更理由 | [docs/DECISIONS.md](docs/DECISIONS.md) |

新对话先读 [AGENTS.md](AGENTS.md)、PLAN 的当前指针，再读 EXECUTE 看板和最新 LOG。不再另建导航页、词典、确认表、周报模板或平行计划。

## 实现与证据

| 目录 | 职责 |
|---|---|
| `src/vsmt/lean_*.py` | D-224 纯核心：实体记忆与执行器、特征/召回/分配、前端 cache、对照臂、代价头、runner、teacher 与评价、开发表 |
| `ops/vsmt/lean_*.py` | 服务器入口：S1-02 数据生成、S1-03 cache、S1-04 诊断、S2-04 单 episode 评价、S2-05 开发表编排与导出 |
| `configs/vsmt/lean_*.json`、`tests/` | 版本化机器合同（规则摘要由跨合同测试钉住）与测试 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物（不进 Git）、可复算导出报告 |
| `src/cpmt/`、`src/spatial_world_model/`、`experiments/`、`schemas/`、`literature/`、`docs/source/`、`prototype/` 及 `src/vsmt/` 里的非 lean 模块 | 历史实现、原始资料与文献，保留不删 |
