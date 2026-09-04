# 实现边界

当前状态：未实现。

计划模块按数据流组织：

1. `tokenize`：从观测产生 projective structural latent regions。
2. `predict_project`：从既有世界记忆和动作预测当前可见结构。
3. `bind`：输出 BIND/NEW/REACTIVATE/SPLIT/MERGE/UNRESOLVED。
4. `transact`：产生带 target、scope、valid time、evidence 的交易。
5. `execute`：确定性检查硬约束并修改版本化 memory。
6. `evaluate`：B/G/M/R/P/T/E 指标及 corruption 诊断。

实现前先完成相关 Human Confirmation。不能把临时代码、手工规则结果或模型评审称为已验证方法。

