# VSMT: Versioned Structural Memory Transactions

当前第一篇论文唯一主题是 **Versioned Structural Memory Transactions（VSMT，版本化结构记忆事务）**：机器人持续接收 RGB-D 观测时，不只向地图追加特征，而是从公开证据提出 NOOP、BIND、BIRTH、REACTIVATE、RELINK、RETRACT、SPLIT、MERGE 八种原子修订，先在同一不可变旧版本上真实执行候选，再选择并提交一个可追溯的新记忆版本。REPLACE 是 RETRACT+BIRTH 复合程序，不算第九个原子。当前为 proposed 方法；工程合同已实现，效果尚未验证。

白话：它解决“新看到的东西应该并入旧记忆、新建、恢复、改关系、撤回、拆开还是合并”的问题。输入是截止当前时刻的 RGB-D 派生匿名区域、公开几何/自由空间和系统自己此前形成的结构记忆，输出是一个合法事务程序及新版本。例如两个旧节点后来被公开多视角证据证明是同一结构，系统可执行 MERGE，同时保留两个旧版本和证据来源。它不等于普通对象跟踪，不限定节点必须是对象，也不把 DINOv2、场景图、确定性执行器或八个动作名字单独当作创新。

## 论文收敛口径

论文的核心候选创新是：**把长期具身记忆更新建模为有类型、可执行、版本化且可审计的结构事务选择，并用严格的 candidate-before-teacher 边界学习选择，而不是让未来监督参与候选构造。** 成熟架构只作为骨架和对照来源：ConceptGraphs 风格前端负责 RGB-D 区域关联，Fusion++ 风格分数负责存在更新，Khronos 风格快窗口/慢协调负责片段修订，Hydra 风格分层图允许实体、地点、表面和关系共存；VSMT 的论文主张必须由同输入实验支持，不能由架构描述自行成立。

第一篇主实验计划比较 `VSMT / TAF / ELU / WFR / LOW`。所有方法共享固定 RGB-D 前端及同一 `ObservationPacket → MemoryUpdateResult` 流水线；旧 C00–C11 只保留为执行器语义与反作弊回归，不进入主结果。旧 LATENT 是合成结构 token/哈希查询，不是视觉 latent；它只能作为 `oracle_structured` 诊断，不能替代新的 RGB-D 主实验。具体分层见 [docs/METHOD.md](docs/METHOD.md) 与 [docs/DATA.md](docs/DATA.md)。

## 五个日常入口

| 你要看什么 | 唯一位置 |
|---|---|
| 下一步、阶段计划和代码审查节点 | [docs/PLAN.md](docs/PLAN.md) |
| 当前方法候选、对照及旧方法合同 | [docs/METHOD.md](docs/METHOD.md) |
| 数据来源、字段、split 和适配检查 | [docs/DATA.md](docs/DATA.md) |
| 已发生的实验、失败、结果与主张状态 | [EXECUTE.md](EXECUTE.md) |
| 方法、预算与工作规则的变更理由 | [docs/DECISIONS.md](docs/DECISIONS.md) |

新对话先读 [AGENTS.md](AGENTS.md)、PLAN 的当前指针，再读 EXECUTE 看板和最新 LOG。不再另建导航页、词典、确认表、周报模板或平行计划；新内容归入以上职责。

## 实现与证据

| 目录 | 职责 |
|---|---|
| `src/vsmt/` | 当前 VSMT 公私合同、共同图包装、论文机制适配器和公开候选/teacher 边界 |
| `ops/vsmt/` | 当前 VSMT 服务器工程检查；尚无数据生成或训练入口 |
| `src/spatial_world_model/` | 暂停的 D-062 空间世界模型实现，保留复现，不是当前入口 |
| `src/cpmt/`、`schemas/` | 保留的旧科学实现和机器接口 |
| `tests/`、`configs/` | 合同/回归检查、版本化科学配置 |
| `scripts/`、`ops/` | 正式运行和服务器运维；历史入口不自动是当前命令 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物、可复算导出 |
| `experiments/counterfactual_transaction_learning/` | 旧 M1/开发合同、结果快照和 fixtures，保留复现路径 |
| `literature/`、`docs/source/`、`prototype/` | 文献、原始资料及原型来源 |

旧源码、配置和 run 报告保留原路径。已被合并的细分文档、重复确认表和两套旧方案副本从工作树删除，原文可在[重组前提交](https://github.com/JingzeSun/Emboddied_Spatial_Memory/tree/c24ced2f4a5513f5a8944b98139857cfc27909ff)查看，不在新目录再复制一套。

VSMT VM-01～VM-03 已完成服务器合同验收并合并 `main`；VM-04旧[L1结构报告](results/vsmt_vm04_l1_structures.json)绑定130/130合同与合成packet。D-140随后把place改为五方法共同的确定性坐标scaffold，候选改为类型化有界分桶并封存容量审计，补齐SPLIT整组分配、MERGE关系重锚、实体主链联测和退化格失败记录；这些新字节目前只有本地139项合同通过，尚待服务器回执，不能借旧报告认证。当前仍不生成house、不打开confirmation、不训练；正式阈值、候选cap、选择器、teacher/evaluator及S-01～S-12数值口径尚待冻结。旧CPMT的S5 no-go、旧test封存、D-062世界模型代码与全部复现路径保留。
