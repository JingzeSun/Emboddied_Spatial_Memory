# 当前研究决策日志

> 本文件只保留现行 accepted 决策和之后的新决策。完整历史、superseded 决策及原始理由见 `archive/pre_execution_v2_2026-08-28/06_decision_log.md`。
>
> 修改 accepted 决策必须追加新条目，不得静默改写旧条目。

## 现行决策摘要

| ID | 状态 | 当前约束 |
|---|---|---|
| D-001 | accepted | ObservationGraph 与长期 world belief 分离；写入必须 association |
| D-002 | accepted | VP 是观测线索，不是长期坐标 |
| D-003 | accepted | Local Chart/Place 是 MVP 稳定锚点，不学习 split/merge |
| D-004 | accepted | MVP 不以 RGB reconstruction 为目标 |
| D-007 | baseline only | normalized EMA/limited prototypes 只是低层 state baseline |
| D-008 | accepted | 主问题是 online spatial context revision；四层状态分离 |
| D-009 | accepted | Related Work 事实基石必须官方核验同行评审 |
| D-010 | accepted | 核心方法为 Structured Innovation + Affected-Subgraph Revision |
| D-011 | accepted | typed deterministic executor；oracle→deterministic→learned；导航延期 |
| D-012 | accepted | superseded 合同进 archive；source artifacts 不覆盖 |
| D-013 | accepted | expansion/revision/ActiveContext 分层；方向关系必须有 reference frame |
| D-014 | superseded in structure by D-015 | 渐进式思想保留，但多入口文件结构被替换 |

## D-015 — 单执行入口与五阶段合同

- 日期：2026-08-28
- 状态：accepted
- 用户确认：`docs/00–09` 信息仍然散乱，不能形成可以照着执行的思路；旧文件可归档。
- 决策：
  1. 旧 `docs/00–12`、`START_HERE.md`、`CHECKLIST.md` 和旧 README 移入 `docs/archive/pre_execution_v2_2026-08-28/`；
  2. 根目录 `EXECUTE.md` 是唯一日常执行入口，只列当前任务、产物、退出门和下一阶段；
  3. 现行研究合同固定为五个顺序文件：研究合同 → 场景 WBS → pilot → training → formal evaluation/paper；
  4. `DECISIONS.md` 独立于顺序文档，作为 append-only 决策记录；
  5. 不允许再创建平行蓝图、第二清单或第二实验合同。
- 方法影响：无；D-008、D-010、D-013 的核心研究方向不变。
- 实验影响：无；项目仍为 pre-implementation，未使用 test 信息。
- 归档来源提交：`b11c7b0`。

## D-016 — Fixture Ground-truth 语义

- 日期：待人工确认
- 状态：proposed
- 必须决定：
  1. identity continuation；
  2. relation storage/derivation；
  3. operator-specific propagation；
  4. reliable absence evidence；
  5. stop equivalence/scoring；
  6. clarification action cost。
- 影响：这些决定冻结前，R1–R6 只能写设计样例，不能称为可用于监督训练的 ground truth。
- 是否接触 test 信息：否。

## 新决策模板

```text
## D-XXX — 标题

- 日期：YYYY-MM-DD
- 状态：proposed / accepted / superseded / rejected
- 背景：
- 决策：
- 备选方案：
- 原因：
- 影响：
- 是否接触 test 信息：
- 验证方式：
```
