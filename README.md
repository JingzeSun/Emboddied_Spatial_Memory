# VSMT-lean: Versioned Structural Memory Transactions（精简版）

当前第一篇论文唯一主题是 **VSMT-lean（实体生命周期版本化事务，D-224，2026-09-19 批准）**：机器人持续接收 RGB-D 观测并重访时，对象级记忆里的每个实体应当保持、绑定新证据、新建、撤回还是恢复，由一次帧级联合分配给出 NOOP、BIND、BIRTH、RETRACT、REACTIVATE 组成的程序，在同一不可变旧版本上提交为可追溯的新版本。REPLACE 是 RETRACT+BIRTH 复合程序；MERGE 降为五方法共享的确定性去重；SPLIT、RELINK 与地点/关系修订不进入首篇。当前为 proposed 方法；机器合同、数据与训练均未开始。

白话：它解决"原来那把椅子现在看不见，是被挡住、走出视野、检测漏了，还是真的被搬走"的判断。输入是截至当前帧的 RGB-D 派生匿名 fragment、公开几何/自由空间/可见体积和系统自己此前预测的实体记忆，输出是本帧一个合法程序及新记忆版本。例如杯子原位置连续被可靠自由空间覆盖、另一张桌面出现高相似 fragment，程序应把旧杯子恢复到新位置而不是删旧建新。它不等于普通对象跟踪的别名，不训练视觉前端，也不把 executor、DINOv2 或五个操作名字单独当作创新。

## 论文收敛口径

核心候选贡献是：**用私有实例真值做 hindsight 监督、以可逆版本记录对象级记忆的生命周期修订，并在共享冻结 RGB-D 前端下用 recall miss / teacher error / amortization error 分解说明胜负来自哪里。** 底层模型是冻结 SAM 2.1 加 DINOv2 描述子、三个约 4 万参数的 MLP 代价头和一次匈牙利分配，不是 VLM 或图网络。

主实验比较 `VSMT-lean / TAF / ELU-P / RAC / LOW`，可选零训练 LLM 选操作臂；消融 `NoVersion / HandCost / HeuristicLabel`。数据为 ProcTHOR 多 house 覆盖式重访加不可观测窗口干预，指标对齐 Dyn-THOR 的节点 P/R/F1 与 Missing 残留率，另报假撤回率、身份连续率、恢复延迟。

## 分支说明

`main` 只含精简版文档；旧 CPMT、空间世界模型、地点双层记忆、统一四类图、八原子枚举与结构估计器的全部文档、代码说明与证据链保留在分支 `archive/pre-d224-unified-graph`（HEAD e1c19f6）。旧源码文件仍在本分支树中，只作历史与复用来源，不进入任何当前入口。

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
| `src/vsmt/` | 执行器、合同、前端 reader、可见性、规则对照；D-224 后新增的 lean 模块按 S0～S2 交付 |
| `ops/vsmt/` | 服务器工程入口；当前无 lean 入口 |
| `tests/`、`configs/` | 合同/回归检查、版本化科学配置；lean 合同以 `configs/vsmt/lean_*` 命名 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物、可复算导出 |
| `src/cpmt/`、`src/spatial_world_model/`、`experiments/`、`schemas/`、`literature/`、`docs/source/`、`prototype/` | 历史实现、原始资料与文献，保留不删 |
