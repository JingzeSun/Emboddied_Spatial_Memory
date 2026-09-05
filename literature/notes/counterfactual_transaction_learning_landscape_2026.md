# CPMT / CTL Novelty Landscape — updated 2026-09-05

状态：内部 novelty audit。同行评审状态按链接类型分别标注；preprint 只用于风险预警。

## 已被占据的部件

| 部件 | 代表工作 | 对本项目的约束 |
|---|---|---|
| frozen visual latent 的 action-conditioned prediction | [DINO-WM, ICML 2025](https://proceedings.mlr.press/v267/zhou25t.html) | future latent prediction 不能单独作为创新 |
| 生成式预测写回 persistent 3D map | [Learning 3D Persistent Embodied World Models, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/970f59b22f4c72aec75174aae63c7459-Abstract-Conference.html) | persistent future consistency 已有强先例 |
| 3D-aware association/reactivation | [SuperMap, RSS 2026](https://www.roboticsproceedings.org/rss22/p052.html) | appearance/disappearance、relocalization 不能作为唯一贡献 |
| 4D persistent reconstruction 与 object permanence | [4D Primitive-Mâché, CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Mazur_4D_Primitive-Mache_Glueing_Primitives_for_Persistent_4D_Scene_Reconstruction_CVPR_2026_paper.html) | persistent reconstruction/object permanence 已有正式强先例 |
| 经典 data association、多假设与延迟决策 | [Lazy Data Association](https://robots.stanford.edu/papers/Haehnel03c.html), [Probabilistic Data Association](https://arxiv.org/abs/1909.11213), [Multiple Hypothesis Semantic Mapping](https://arxiv.org/abs/2012.04423) | top-K、MHT、回溯本身不是新 |
| predictive state / 用未来可预测性定义状态 | [Predictive State Representations, NeurIPS 2001](https://proceedings.neurips.cc/paper_files/paper/2001/hash/1e4d36177d71bbb3558e43af9577d70e-Abstract.html) | “未来预测决定好状态”是已有思想 |
| active hypothesis testing | [NeurIPS 2017](https://proceedings.neurips.cc/paper/2017/hash/9f44e956e3a2b7b5598c625fcc802c36-Abstract.html) | 主动消歧不能无审计地并入主 claim |

## 2026 novelty watch（不作已验证事实基石）

- [HGR](https://arxiv.org/abs/2604.04108)：hierarchical graph revision；
- [Move First, Commit Later](https://arxiv.org/abs/2607.17103)：行动后再承诺的近邻表述；
- [SG-AMP](https://arxiv.org/abs/2609.01579)：scene-graph active memory/planning 的极新风险。

截至本次审计，这三项按 preprint novelty watch 处理；投稿前必须重新核验正式 venue 和最新版本。

## 仍可检验的窄缝

没有证据支持声称上述单一组件首次出现。当前可守的组合机制是：

> 对同一持久图版本施加 typed memory-state transactions，真实执行每个候选，再用 action-conditioned future projective evidence 比较执行后世界，并将 hindsight selection 蒸馏成无未来在线 updater。

这个窄缝是否足够，不靠措辞判断，只靠 CPMT 的 A vs C/E hard-condition experiment。若 direct classifier + future loss 达到同等效果，CTL 窄缝在实证上关闭。

## Related Work 组织

1. latent world prediction；
2. persistent embodied/3D memory；
3. data association and multiple hypotheses；
4. versioned graph revision；
5. 本项目差异：post-edit executable counterfactual transactions + future ranking + online distillation。

不得写“prior work cannot revise memory”；只能逐项写它是否执行 typed candidate programs、是否评价 post-edit world、是否保留版本/rollback、是否在线无未来。
