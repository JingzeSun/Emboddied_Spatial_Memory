# Fixtures

这里保存可提交版本库的小型、人工可审计 case；不保存大型图像、视频、模型权重或运行输出。

每个 case 至少包含：

- `case.yaml`：场景、输入版本、oracle 与控制项。
- `observation.json`：region tokens 或其小型替代数据。
- `memory_before.json`：执行前世界记忆。
- `oracle_transaction.json`：预期交易。
- `memory_after.json`：预期执行后记忆。
- corruption 变体及预期失败类别。

Fixtures 只用于开发 evaluator 与单元测试，不进入正式 test 主表。

