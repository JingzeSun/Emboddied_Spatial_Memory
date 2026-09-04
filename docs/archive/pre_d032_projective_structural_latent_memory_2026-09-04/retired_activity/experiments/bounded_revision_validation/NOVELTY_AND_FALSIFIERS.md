# 创新边界与反证

## 1. “维护场景图”本身不新

SceneGraphFusion 已做增量 3D 场景图预测；Continuous Scene Representations 在线更新关系表示；Scene Graph Memory 从部分可观测动态图预测关系；DiffVSGG 把在线视频图生成写成迭代更新；Embodied VideoAgent 维护持久具身记忆。因此不能把“用 GNN/Transformer 更新图”写成创新。

9 月 1 日提到的 DSG 工作也应按同一原则审计：先补齐准确题名、版本、代码和任务定义，再逐项填 SA1–SA8。它若已经做 affected-subgraph revision，就不能回避，必须比较其是否同时处理 arrival/event 双时间、负证据充分性、显式编辑程序、protected controls、有效时间区间和直接证据集合。

## 2. 候选剩余贡献

当前可检验的组合是：

1. 乱序 evidence 的 event/arrival 双时间；
2. visibility-conditioned negative evidence；
3. 显式 `KEEP/ASSERT/RETRACT/REPLACE/QUARANTINE`；
4. 学习 seed affected mask，并由硬 typed closure 限定写边界；
5. valid-time 点/区间预测；
6. 直接监督 supporting evidence set，而非 attention 展示；
7. 同时衡量 necessary edits、protected facts 与任务后果。
8. 使用 predicate schema 条件化共享 updater，并把 registered-but-unseen predicate 作为次级、可删除的泛化主张。

贡献强度必须由消融证明，不是因为列表长就成立。

## 3. 场景创新在哪里

不是“椅子被识别”或“对象移动”本身，而是这些反例：

- 新收到的证据实际上比当前事实更旧；
- 没看见对象，但覆盖不足，不能撤回；
- 多个相关帧不能假装多个独立来源；
- 两个可信来源冲突，只能隔离；
- 旧位置应撤回但新位置未知；
- 一处变化只应失效两个依赖项，不能重写整图；
- 真实数据只给出变化区间，不能伪造精确时刻。

若成熟 DSG 已同时覆盖这组输入、输出和指标，本项目必须转为 benchmark/replication 或寻找更窄的新假设。

## 4. 反证表

| 观察结果 | 推翻什么 | 下一步 |
|---|---|---|
| R3 规则与学习模型等价 | “需要学习证据门” | 收缩为 benchmark/系统论文或增加真实噪声 |
| Event-Transformer 与 ESGBU 等价 | “显式图依赖必要” | 删除图创新主张 |
| FullGraph-HGT 与 ESGBU 准确率、保护和成本等价 | “稀疏 mask 带来方法优势” | 只保留效率工程结论 |
| 共享 executor 后各方法差距消失 | “神经 updater 有贡献” | 把贡献归于结构执行器并重写论文 |
| 去掉双时间不下降 | “迟到/乱序是核心难点” | 审查生成器或删除双时间主张 |
| attribution F1 高但删除证据不影响输出 | “证据归因可信” | 降级为相关性展示 |
| AI2-THOR 有效、3RScan 崩溃 | “跨域现实价值” | 只主张模拟器内能力 |
| edit F1 提升但 wrong dispatch/CPR 不改善 | “后验更新有下游价值” | 不写应用收益 |
| mask 更小但 NUR 明显下降 | “最小必要更新” | 判为失败，不以效率掩盖漏改 |
| held-out predicate 与 ID-only/schema-ablated 对照等价 | “schema 带来谓词泛化” | 删除次级泛化claim，保留场景/动态泛化结果 |

## 5. 最小论文主张梯子

- C0：提出可复现的异步证据图修订任务与判尺；
- C1：ESGBU 在同预算结构基线上改善稀疏、校准、时间与保护；
- C2：AI2-THOR 多轴 OOD 仍成立；
- C3：3RScan/真实长序列外部有效且减少任务错误。
- C4：registered-but-unseen predicate 上共享 schema updater 仍成立；该层失败不回填修改前三级 test。

只有实验支持到哪一级，论文就写到哪一级。

参考：[Scene Graph Memory](https://proceedings.mlr.press/v202/kurenkov23a.html)、[Continuous Scene Representations](https://openaccess.thecvf.com/content/CVPR2022/papers/Gadre_Continuous_Scene_Representations_for_Embodied_AI_CVPR_2022_paper.pdf)、[SceneGraphFusion](https://openaccess.thecvf.com/content/CVPR2021/papers/Wu_SceneGraphFusion_Incremental_3D_Scene_Graph_Prediction_From_RGB-D_Sequences_CVPR_2021_paper.pdf)、[DiffVSGG](https://openaccess.thecvf.com/content/CVPR2025/papers/Chen_DiffVsgg_Diffusion-Driven_Online_Video_Scene_Graph_Generation_CVPR_2025_paper.pdf)、[Embodied VideoAgent](https://openaccess.thecvf.com/content/ICCV2025/html/Fan_Embodied_VideoAgent_Persistent_Memory_from_Egocentric_Videos_and_Embodied_Sensors_ICCV_2025_paper.html)。

## 候选创新的 Criteria 纵列

| Hypothesis | 必须由哪些 Criteria 支持 | 最小对照 | 数字式证据例 | 不成立时删什么 |
|---|---|---|---|---|
| H1 双时间 | C2/C8/C12 | L2双时间 vs 去observed/received任一项 | exact 84→73%、time MAE恶化且CI不重叠 | 删除双时间创新claim |
| H2 负证据/来源 | C1/C3/C5/C10–C13 | 去visibility/source/grouping | weak-negative误撤由2%升12% | 删除evidence-aware对应部分 |
| H3 稀疏边界 | C3–C7/C15 | M0 vs FullGraph-HGT，同图同预算 | NUR均96%，CPR 99.7 vs98.8，p95 47 vs91ms | 若只快则只写效率，不写准确性 |
| H4 时间/归因 | C8–C12 | 去time/evidence head | evidence F1升但删除干预无变化 | attribution降级为展示 |
| H5 schema泛化（次级） | held-out split上的适用C1–C15 | schema vs ID-only vs fields removed | ID exact=.84、held-out=.78且显著优于ID-only=.61 | 无优势即删除predicate泛化claim |
| downstream value | C14且C3/C5/C12不降 | oracle task reader读取各方法state | wrong dispatch 9→5%，CPR不降 | 删除应用收益claim |

这里的数字只展示何种“联合证据”才足以支撑 claim，不是预先保证的效果量。
