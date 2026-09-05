# 2026-09-04 Initialization Packet

> 历史状态：本包已由 2026-09-05 CPMT scope-freeze packet 取代。

- 当前阶段：P0
- 状态：方法/合同已重构；实现与验证未开始

## 本周唯一命题

CTT 只有在候选事务被真实执行、并按执行后世界的未来结构一致性排序时，才可能区别于 direct classifier + future loss。

## 已固定

- 七类候选 family 的提案；
- deterministic/versioned/rollback executor 的职责；
- online inference 禁止未来证据；
- A vs C/E 为 primary hard-condition contrast；
- 旧方法已归档到 archive/pslm-pre-ctt-20260904，commit eba4339。

## 尚无结果

没有 executor、fixture ground truth、训练 run 或性能数字。本周工作不能称为实验验证。

## 当前最大风险

事务语义若不能为 SPLIT/MERGE/RETRACT 构造自然正例，CTT 会退化为带复杂命名的 BIND/BIRTH 分类器。

## 下一项证伪工作

先手工完成 C00–C11 paired fixtures；若无法在相同 current evidence 下构造至少三个必须依赖 future 才可区分的自然 case，则暂停模型设计，重审命题。

## 需要研究者/导师决定

优先确认 HC-001（事务语义）与 HC-002（首批 fixture）。推荐默认写在对应文件中；确认前不生成 ground truth。
