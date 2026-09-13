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

## D-122 第一篇共同流水线候选（2026-09-13）

本轮目标不再是证明八个事务名称逐个新颖，而是选择经论文验证、能在同一公开输入和记忆状态上独立适配的更新机制。这里的“机制适配”指按论文描述重写最小算法并清楚列差异，不是下载作者代码后改名，也不是宣称复现原论文数值。

| 独立适配 | 主要来源 | 采用的机制 | 不采用/不声称 |
|---|---|---|---|
| TAF：阈值关联与融合 | [ConceptGraphs, ICRA 2024](https://arxiv.org/abs/2309.16650) | posed RGB-D 区域的几何/视觉相似度、匹配后增量融合、未匹配新建、周期性重复合并 | 不复制官方 MIT 代码，不运行语言 caption/LLM 图关系，不称官方复现 |
| ELU：存在概率更新 | [Fusion++, 3DV 2018](https://arxiv.org/abs/1808.08378)；[Dengler et al., ECMR 2021](https://arxiv.org/abs/2011.06895)；[POCD, RSS 2022](https://www.roboticsproceedings.org/rss18/p013.html) | 存在置信、可靠正/负观测、错误关联修正及半静态变化证据 | 不复现 TSDF/完整 SLAM，不把一次未检出当作消失 |
| WFR：窗口化片段协调 | [Khronos, RSS 2024](https://www.roboticsproceedings.org/rss20/p081.html) | active window、fragment hypotheses、较慢的全局 association/reconciliation、presence/absence | 不复制 BSD-3 ROS/C++，不称完整 metric-semantic SLAM 或作者 baseline |

补充强近邻为 [SuperMap, RSS 2026](https://www.roboticsproceedings.org/rss22/p052.html)，其 3D-aware association/reactivation、existence/label confidence 和 outdated-content pruning 会限制 BIND/REACTIVATE/RETRACT 的新颖性；当前用作 related-work 与 ELU/WFR 设计压力，不另加第四个高度重叠适配器。[Long-Term Online Multi-Session Graph-Based SPLAM](https://arxiv.org/abs/2301.00050) 的 Working Memory/Long-Term Memory 转移和重取回是 REACTIVATE 的经典系统近邻，但主要解决在线资源管理，不适合作为本轮结构纠错主基线。

### clean-room 与许可证边界

- ConceptGraphs 官方仓库为 MIT，Khronos 为 BSD-3-Clause，Hydra 为 BSD-2-Clause；许可证允许有条件复用，但本轮仍不复制源码，避免将工程依赖和机制比较混在一起。
- 每个适配器文件头记录论文链接、机制摘要、与原方法的缺失项及 `independent mechanism-level adaptation; not official implementation; no upstream source copied`。
- 不沿用上游类名、函数结构、注释、默认阈值和测试样例；阈值只在共同 train/validation 冻结。论文公式若使用，在 METHOD 重新推导、标引用并说明变量映射。
- 若后续确需官方代码重评，单列作者仓库 commit、license notice、原数据/权重和未修改结果；官方复现与本项目适配不得合并为同一个结果臂。

### 旧 query 风险结论

当前 `m1_rollout._event_plan` 先读取 reference transaction 的目标节点、边和地点，再生成 node/edge/place/merge query；候选生成器虽然不直接读 `reference_spec`，但读取已经携带目标身份信息的 query。`merge_queries` 又专门将两个目标排序成首个 MERGE pair。因此现有“删掉 reference_spec 后候选不变”只检查最后一跳，不能认证端到端无 teacher/oracle shortcut。D-122 新数据须移除这些字段，query 只能从当前公开区域/片段与 prior predicted memory 重新计算。
