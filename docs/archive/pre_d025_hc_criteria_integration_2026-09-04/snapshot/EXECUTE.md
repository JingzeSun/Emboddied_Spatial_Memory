# EXECUTE：当前唯一执行入口

## 当前状态

阶段：**P0，后验任务与判尺冻结**。

已完成：D-024 文档重构；旧活动合同与实验包 56 文件快照；新问题、模型、loss、数据、基线、场景、criteria、协议和反证设计。

未完成：HC-018 执行顺序；关键 CRITERIA 冻结；schema/executor/evaluator；任何数据下载、训练或验证。

## 现在只做什么

1. 人工回答 HC-018：推荐选“先 12 个 hand-authored oracle smoke cases，通过 deterministic gate 后再做 symbolic/AI2-THOR”；
2. 按 [`CRITERIA.md`](experiments/bounded_revision_validation/CRITERIA.md) 冻结 HC-004/005/013/015/016/017/019 涉及的负证据、等价事务、时间容差、QUARANTINE、baseline 预算和任务代价；
3. 决策落盘后，才实现 canonical transaction schema、executor 和 evaluator；
4. evaluator 自测通过后，按 R0→R3→L0→L4→M0 顺序推进。

## P0 产物

- accepted decision IDs；
- 12 个 case contracts（或用户选择的 AI2-THOR-first 合同）；
- metric version 与 hard-gate version；
- canonical input/output schema 草案；
- test access policy。

## P0 退出门

- 所有会改变 oracle 答案的语义已有 decision ID；
- 允许/禁止编辑、affected/protected、valid time、evidence set 与 task delta 可由人判定；
- 没有把 test 用于阈值或方案选择；
- 下一阶段只有一个可执行合同。

## 当前禁止

- 在 HC-018 未决时把训练写成已授权启动；
- 为了“复杂”先训练大 VLM 或完整导航；
- 用七项以上重复 loss 掩盖输出定义不清；
- 只比 edit F1，不报保护、时间、证据、校准和任务后果；
- 把旧 archive 或原型当作活动合同；
- 宣称“已验证”“可投某刊”或“国内 A 类”而没有结果/认定表。

## 当前详细合同

唯一实验包：[`experiments/bounded_revision_validation/README.md`](experiments/bounded_revision_validation/README.md)。

跨对话时使用 [`docs/NEW_CHAT_HANDOFF_PROMPT.md`](docs/NEW_CHAT_HANDOFF_PROMPT.md)，但它不替代本文件。
