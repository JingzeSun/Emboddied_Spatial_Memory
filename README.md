# Embodied Spatial World Models

当前研究候选：**利用早期空间历史，预测相同机器人控制指令在不同遮挡结构下的后果，并检验是否改善动作选择。** 2026-09-11 用户授权开始（D-062）；方法尚未验证，不预先绑定旧项目的 CTL，也不把持久三维状态本身称为创新。

白话：输入过去看见的环境、当前传感器信息和拟执行的控制，输出未来物块轨迹与接触后果。例如机器人先看过挡板位置，挡板离开视野后，相同推法在两个场景里可能分别受阻与通过。这不是输入物体已知位移再生成画面，也不是已经实现了通用智能体。

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
| `src/spatial_world_model/` | 新空间历史合同与物理适配器；与旧科学模块独立 |
| `src/cpmt/`、`schemas/` | 保留的旧科学实现和机器接口 |
| `tests/`、`configs/` | 合同/回归检查、版本化科学配置 |
| `scripts/`、`ops/` | 正式运行和服务器运维；历史入口不自动是当前命令 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物、可复算导出 |
| `experiments/counterfactual_transaction_learning/` | 旧 M1/开发合同、结果快照和 fixtures，保留复现路径 |
| `literature/`、`docs/source/`、`prototype/` | 文献、原始资料及原型来源 |

旧源码、配置和 run 报告保留原路径。已被合并的细分文档、重复确认表和两套旧方案副本从工作树删除，原文可在[重组前提交](https://github.com/JingzeSun/Emboddied_Spatial_Memory/tree/c24ced2f4a5513f5a8944b98139857cfc27909ff)查看，不在新目录再复制一套。

按阶段审查成对数据合同、真实模拟器生成和重放，再比较长历史与地图加简单动力学；当前指针及阶段命令见 PLAN。暂不开展模型训练、主动探索、开放世界、复杂操作或视频生成。旧 CPMT 代码、科学 no-go、结果与 test 封存状态保留。
