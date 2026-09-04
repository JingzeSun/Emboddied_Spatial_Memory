# 03 Pilot：先证明“世界节点怎样出生和延续”可被判定

## 先决状态

D-032 只接受新主线，不自动把 D-026～D-031 的 posterior-only 数据规模、谓词泛化或通过门迁移为新合同。第一批规模与判尺由 HC-020/031 重新冻结；在此之前只允许写设计样例。

## Pilot A：12 条 hand-authored projective sequences

推荐先为 S00–S11 各制作一条 4–12 帧的最小序列。每条包含：

- RGB/latent placeholder、depth/pose/intrinsics 与时间；
- observation regions 及 image/3D support；
- prior memory graph 与 projected expected regions；
- oracle association edges；
- node/edge birth、attachment、visibility/lifecycle 与 revision transaction；
- protected nodes、valid time、evidence refs；
- 至少四个单因素错误：wrong bind、false birth/merge、wrong lifecycle、wrong revision/scope。

这一步只验证语义与 evaluator，不证明方法有效。

## Pilot B：确定性下限

固定 oracle regions/depth/pose，比较：

1. image-patch nearest memory；
2. pose-warped latent nearest neighbor；
3. IoU + appearance slot fusion；
4. lifecycle rules；
5. recent-N full recomputation；
6. oracle association/update。

若几何/规则在全部转弯、重现、birth、遮挡、搬迁和 pose-noise 因子上已接近 oracle，学习机制没有必要；应转为 benchmark/system，而不是增加网络。

## Pilot C：最小学习检查

只训练 tiny 配置：

- learned matcher；
- matcher + abstention/birth；
- matcher + birth + local graph context；
- full PSLM-tiny；
- 去 predict-project、去 structure、去 revision 的关键消融。

进入大规模 simulator 的候选门：

- learned matcher 在 aliasing/partial overlap 上超过最强规则；
- controlled birth 同时提高 new-node recall 并降低 duplicate/false birth；
- complete model 在 binding、growth、retention/revision 至少三个维度优于 recent-N/full recomputation；
- action-conditioned head 改善预测指标；否则删除 world-model 表述；
- executor 没有解释全部收益。

## Kill / pivot 条件

- fixed patch 与 structural regions 等价：删除 perspective/structure token claim；
- pose-warp + IoU 与 learned binding 等价：binding 降为工程模块；
- recent-N recomputation 与 persistent memory 等价且成本可接受：长期 transducer claim 失败；
- birth recall 提高但 duplicate/false merge 激增：controlled growth 失败；
- 静态保持来自永久冻结、真实搬迁无法更新：dynamic persistence 失败；
- prediction head 不改善未来结构或下游：不用 world-model claim；
- full pipeline 只提高导航而 memory 指标不升：不能归因于记忆正确性。

## Pilot 输出

- 方法 × B/G/M/R/P/E 指标表；
- angle/overlap/occlusion/pose-noise 四张曲线；
- node lineage 与 transaction 的可视化回放；
- 至少 12 个信息量最大的失败案例；
- continue / shrink / pivot 决策及 D-ID。
