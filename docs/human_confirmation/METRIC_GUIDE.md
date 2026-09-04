# 指标决策速查

完整定义位于 `experiments/projective_structural_latent_memory/CRITERIA.md`。

| 族 | 回答的问题 | 主要失败 |
|---|---|---|
| B：Binding | 当前 region 属于哪个世界 node？ | identity switch、false merge、duplicate birth |
| G：Growth | 何时创建并挂接新世界结构？ | 漏建、幻觉扩张、错误 parent/topology |
| M：Memory | 长序列中静态/动态记忆是否稳定？ | 漂移、动态污染、生命周期混淆 |
| R：Revision | 世界变化后是否只改该改的？ | 错 operation/scope/time/evidence、collateral edit |
| P：Prediction | memory 能否预测下一结构观测？ | 可见性、latent correspondence、frontier 预测失败 |
| T：Task | 好记忆是否带来查询/行动收益？ | 任务无增益或归因到额外模型 |
| E：Efficiency | 在线扩张是否可部署？ | 延迟、显存或节点数无界增长 |

推荐采用顺序 gate 而非单一加权总分。尤其必须成对看：precision 与 coverage、new-node recall 与 hallucinated expansion、necessary update 与 control preservation、质量与累计计算。
