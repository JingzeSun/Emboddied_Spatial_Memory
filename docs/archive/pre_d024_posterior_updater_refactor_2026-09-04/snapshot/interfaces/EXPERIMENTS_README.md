# 实验目录

本目录只保存可复现的实验设计、固定输入、运行配置和结果索引，不替代
`docs/01_research_contract.md`、`docs/02_scenario_wbs.md` 或决策日志。

当前唯一核心实验包是 [`bounded_revision_validation/`](bounded_revision_validation/README.md)：
在相同的结构化先验、观测、预测和关联输入下，只改变后验修正策略，验证
Evidence-Gated Affected-Subgraph Belief Revision 是否能做到“该改的改、无关的不改、
证据与时间可追溯”。

当前状态：**实验协议已细化；尚未实现、尚未运行、尚无验证结果。**

核心包现已包含 [BEGR-Net 训练合同](bounded_revision_validation/LEARNED_MODEL.md)、B0–B7/L0–L5 基线、27 个场景模板、双时间 symbolic data track 和 learned calibration/OOD 指标。它们仍是候选设计，不表示模型已训练或 HC-018 已接受。

## 目录规则

- `templates/`：人工可读的配置模板；冻结后复制到每次运行目录。
- `fixtures/`：小型确定性样例；不得把自动估计冒充 ground truth。
- 正式运行须保存数据版本、代码版本、配置、随机种子、模型标识、逐案例输出和失败信息。
- 大型数据、checkpoint、模型权重和运行输出不提交版本库。
- 阈值只能在 validation split 上选择，test split 只运行一次，不得反向调参。
