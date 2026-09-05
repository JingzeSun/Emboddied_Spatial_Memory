# CTL: Core Learning Experiment inside CPMT

定位：CTL 方法与实验规格索引，不维护第二份进度；当前结果、未完成项和下一步统一见 [EXECUTE.md](../../EXECUTE.md)。

按需读 [开发合同](DEVELOPMENT.md) 和 [首轮结果快照](DEVELOPMENT_RESULTS.md)。开发实验的解析投影不等于 Projective Node Orbit，也不能当作正式 M1；新实验结果追加 EXECUTE，不自动新建结果 Markdown。

CPMT 是完整 embodied spatial memory 方法；本目录只验证其中唯一主创新 CTL：

> 从同一旧世界版本执行多个 transaction programs，以当前和未来 projective evidence 形成 hindsight posterior，再训练不读取未来的 online updater。

## 只回答三个问题

1. post-edit execution 是否比 direct future loss 提供额外信息；
2. future-conditioned teacher 是否能减少 transaction labels；
3. online student 是否能在 self-rollout 中保留收益。

## 阅读顺序

1. PROBLEM_FORMULATION.md；
2. TRANSACTION_SEMANTICS.md；
3. COUNTERFACTUAL_EXECUTION.md；
4. REPRESENTATION.md；
5. HARD_CONDITION_EXPERIMENT.md；
6. SCENARIOS.md、BASELINES.md、CRITERIA.md；
7. DATASETS.md、TRAINING.md、PROTOCOL.md、PUBLICATION_GATES.md。

这些细粒度文件是同一实验的支持材料，不是平行工作流。日常任务只由根目录 EXECUTE.md 指定。

## 四关

- M0：transaction language + deterministic executor；
- M1：hard-condition go/no-go；
- M2：embodied visual online/self-rollout；
- M3：一个 external/现实来源和论文 artifact。

阶段推进须满足对应门槛，不能根据旧报告的“下一步”自动进入后续训练；实际阶段由唯一实验记录的看板说明。
