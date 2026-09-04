# 时序图模型与多任务 loss 设计核验

状态：`design evidence / primary sources checked / not an experimental result`

## 1. 成熟模型给当前方案的边界

### Temporal Graph Networks（TGN）

TGN 把动态图表示为带时间戳的事件流，并以 message、aggregator、memory updater 和 embedding module 组织模型。这说明 event-based temporal graph memory 已是强基线，不能把“用时序 GNN 更新图”写成创新。

采用方式：实现 TGN-style L2 baseline，共享相同 evidence events 与 candidate facts。BEGR-Net 必须额外证明 event/arrival time 区分、quarantine、稀疏 typed transaction、protected controls 和 version/provenance 的作用。

来源：https://arxiv.org/abs/2006.10637

### Scene Graph Memory

Scene Graph Memory 已在部分可观测环境中使用动态图记忆并预测未见对象位置。它说明 scene graph + learned memory + partial observability 并不新；本项目必须聚焦证据冲突后的事实级、时间化、可回放修订。

来源：https://proceedings.mlr.press/v202/kurenkov23a.html

### Structured World Belief

Structured World Belief 已把对象与关系的结构化状态用于世界模型/规划。它支持“显式结构状态有用”这一基础动机，但不能直接支持本项目的 affected/control/stop 或 bitemporal transaction claim。

来源：https://proceedings.mlr.press/v139/singh21a.html

## 2. 多 loss 文献能说明什么

### Uncertainty weighting

Kendall 等用任务不确定性学习多任务 loss 权重，避免完全手工设置尺度。它适用于确实存在多个任务且似然假设合理的情况，不是“loss 越多越好”的证据。

来源：https://openaccess.thecvf.com/content_cvpr_2018/html/Kendall_Multi-Task_Learning_Using_CVPR_2018_paper.html

### GradNorm

GradNorm 用梯度大小动态平衡任务训练速率。采用前提是已经观测到共享参数上的任务失衡；它不解决标签重复、目标定义重叠或本可由硬约束保证的问题。

来源：https://proceedings.mlr.press/v80/chen18a.html

### PCGrad

PCGrad 在任务梯度冲突时投影冲突分量。它可以作为诊断后的消融，但如果 preservation、scope、stop、time 本来能由 executor 保证，先拆成 loss 再用 PCGrad 修补并不经济。

来源：https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html

## 3. 对本项目的直接结论

1. 主目标使用 factorized transaction NLL：gate，再条件化 targets/operators；
2. supporting-evidence attribution 只有在标签可靠时作为一个辅助项；
3. sparsity 只作为小正则，不能替代 necessary-update recall；
4. affected/control/stop、valid-time legality、atomic version 与 provenance completeness 先用 typed executor/hard validation；
5. task success 只用于固定下游 reader 的外部评价，不回传到通用 posterior；
6. 只有记录到多个 learned task 的梯度量级失衡或持续负 cosine，才预注册 uncertainty weighting、GradNorm 或 PCGrad 消融。

## 4. 与用户已有能力的衔接

DATA3888 报告已经展示了 hierarchical vs flat、stagewise vs end-to-end、多个 backbone、校准、空间防泄漏 split、ablation 和 negative-result 分析。当前项目应复用这些研究能力：

- hierarchical gate vs flat decoder；
- group/template split 防止变体泄漏；
- calibration 与 selective risk；
- small/medium/large capacity ablation；
- 明确记录“更大模型没有改善”的负结果。

不建议复用的是为了显示复杂度而增加许多 auxiliary heads；该报告本身也说明更大 backbone 或更多模块未必越过信息/任务上限。
