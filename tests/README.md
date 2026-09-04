# 测试契约

当前状态：未实现。

测试至少覆盖：schema 正反例、transaction 原子性、非法交易拒绝、版本/时间一致性、控制项保持、S00–S11 fixtures、指标手算对照、确定性重放以及 oracle 字段不进入线上输入。

正式 test split 不能用于调阈值、选 prompt、选 checkpoint 或筛方法。开发期只使用 fixtures、train 与 validation。

