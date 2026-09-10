# Embodied Spatial Memory

研究 **Counterfactual Projective Memory Transactions（CPMT，反事实投影记忆事务）**，核心机制是 **Counterfactual Transaction Learning（CTL，反事实事务学习）**。

机器人收到新的观测 latent 后，判断应怎样影响旧世界记忆：绑定旧对象、建立新身份、修改关系或暂存证据。训练时把竞争解释执行到同一旧世界的不同副本，用后续实际观测形成监督；在线只看截至当前的信息。例如椅子移动后改位置且保留无关桌子的记忆。“新观测”不预设“新物体”，执行器可用也不代表 CTL 比直接未来损失有效。

## 五个日常入口

| 你要看什么 | 唯一位置 |
|---|---|
| 下一步、32 步计划和代码审查节点 | [docs/PLAN.md](docs/PLAN.md) |
| 方法、术语、事务、教师、对照与评价 | [docs/METHOD.md](docs/METHOD.md) |
| 数据来源、字段、split 和适配检查 | [docs/DATA.md](docs/DATA.md) |
| 已发生的实验、失败、结果与主张状态 | [EXECUTE.md](EXECUTE.md) |
| 方法、预算与工作规则的变更理由 | [docs/DECISIONS.md](docs/DECISIONS.md) |

新对话先读 [AGENTS.md](AGENTS.md)、PLAN 的当前指针，再读 EXECUTE 看板和最新 LOG。不再另建导航页、词典、确认表、周报模板或平行计划；新内容归入以上职责。

## 实现与证据

| 目录 | 职责 |
|---|---|
| `src/cpmt/`、`schemas/` | 科学实现和机器接口 |
| `tests/`、`configs/` | 合同/回归检查、版本化科学配置 |
| `scripts/`、`ops/` | 正式运行和服务器运维；历史入口不自动是当前命令 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物、可复算导出 |
| `experiments/counterfactual_transaction_learning/` | 旧 M1/开发合同、结果快照和 fixtures，保留复现路径 |
| `literature/`、`docs/source/`、`prototype/` | 文献、原始资料及原型来源 |

旧源码、配置和 run 报告保留原路径。已被合并的细分文档、重复确认表和两套旧方案副本从工作树删除，原文可在[重组前提交](https://github.com/JingzeSun/Emboddied_Spatial_Memory/tree/c24ced2f4a5513f5a8944b98139857cfc27909ff)查看，不在新目录再复制一套。

首篇固定视觉前端和确定性候选器，聚焦具身记忆；不加主动策略、第二领域或端到端基础模型。方法有效性必须比较直接未来损失与无执行未来评分，开发样本不改称未见 test，负结果保留。科学边界见 METHOD，逐步执行见 PLAN。
