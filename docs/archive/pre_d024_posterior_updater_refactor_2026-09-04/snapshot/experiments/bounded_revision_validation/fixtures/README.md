# Fixtures

状态：`contract prepared / no fixture implemented`

权威场景编号与 smoke 范围见 [../SCENARIOS.md](../SCENARIOS.md)，完整运行顺序见
[../PROTOCOL.md](../PROTOCOL.md)，字段示例见 [../templates/](../templates/)。本目录后续只保存小型、
可人工复核的确定性输入与 gold contract，不保存正式 test 结果、大型数据或模型输出。

## 首批 12 个 smoke fixture 的要求

每个案例至少保存：

- 初始 belief/version、固定 observation/identity/visibility/pose/sensor 输入；
- `observed_at`、`received_at`、source、evidence group、polarity 与 coverage；
- 唯一改变的变量与配对反事实；
- gold change type、acceptable operations、affected set、control set、stop boundary；
- forbidden operations、valid-time 约束与 provenance 要求；
- 人工复核者、依赖 HC/D IDs、是否接触 test（首批必须为否）。

先让 `oracle_revision` 对 12/12 全部 hard gates 通过，再故意注入 overwrite、漏传播、越界传播、
非法半提交等错误，验证 evaluator 会失败。不能只验证正确实现。

P4 双时间模板先保持 non-smoke，待 12 个 executor/evaluator smoke 通过后再加入。learned training transactions 不放入本目录；这里只保存小型 regression fixtures 与其人工可读 gold。

在 HC-001–005、HC-011、HC-013、HC-015–018 的相关选择确认前，不生成冻结 fixture；HC-018 若未
接受，仍遵守现有完整 A 阶段门。未确认前可以写 `draft_not_gold` 样例，但不能称为 ground truth。
