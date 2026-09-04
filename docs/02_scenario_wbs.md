# 02 单人研究 WBS 与场景工作分解

## 总原则

每个工作包只回答一个可推翻的问题。先证明状态和判尺成立，再证明学习必要，再证明完整方法优于强构建/融合基线。前端提升、记忆机制提升和下游策略提升必须分开归因。

## 工作包

| WP | 唯一问题 | 主要产物 | 退出门 |
|---|---|---|---|
| WP0 | 人工语义是否唯一 | HC-020～034、metric/hard-gate version | 两人能独立得到等价 oracle |
| WP1 | transaction/evaluator 是否可信 | schema、executor、12 smoke sequences、corruptions | oracle全收、错误全拒绝 |
| WP2 | projective binding 是否有问题 | deterministic tokenizer/projector/associator | 固定patch/IoU在预期场景失败 |
| WP3 | graph growth 是否可评 | candidate/birth/attachment generator | 新结构覆盖与错误birth可同时计算 |
| WP4 | learned binding/growth 是否必要 | patch/warp/slot/window/graph 强基线 | 学习显著超过最强规则而非前端差异 |
| WP5 | revision 子模块是否增益 | safe transaction updater 与 full recompute 对照 | 必改、保护、时间、证据同时成立 |
| WP6 | action-conditioned prediction 是否增益 | structural latent/visibility predictor | 改善预测及至少一个只读任务 |
| WP7 | simulator ID/OOD 是否成立 | AI2-THOR/Habitat 多轴实验 | 多 seed、paired CI、无 test 调参 |
| WP8 | 外部/真实有效性 | 重扫或真实机器人序列 | 公开标签局限和真实失败 |
| WP9 | 论文与 artifact | 表格、失败 taxonomy、复现包 | 每个 claim 有表、消融和反证 |

## 场景因子

场景按机制变量而不是对象名字划分：

1. camera rotation / translation / pose noise；
2. surface/object/portal region 粒度和 split/merge；
3. overlap 与 reappearance gap；
4. known place / new place / perceptual aliasing；
5. new structure coverage 与 attachment depth；
6. occluded / out-of-FOV / reliable absence；
7. transient actor / stationary actor / relocated object；
8. event time / arrival time / delayed evidence；
9. graph size、history length 与 active scope；
10. action-conditioned next-view visibility 与 frontier。

精确 S00–S11 families 见实验包 `SCENARIOS.md`。

## 单人执行优先级

优先保住：冻结前端、可回放数据合同、binding/growth oracle、evaluator、四类强机制基线、关键消融和失败分析。延后：大型 VLM、漂亮 demo、全局 learned Chart split/merge、多任务策略和开放世界语义发现。

## 周报模板

```text
1. 本周只验证 H1–H6 中哪一个？
2. 固定了哪些输入和前端？
3. 改变了哪个 representation/update mechanism？
4. binding、growth、retention、revision 中哪项改善或恶化？
5. 最重要反例是什么？
6. 下周哪个判别实验最可能推翻当前选择？
7. 哪个 HC 必须由研究者决定？
```

## WBS 与指标组

| WP | 直接指标组 | 数字式检查 | 不通过动作 |
|---|---|---|---|
| WP1 | B/G/M/R 全部接口 | 12 oracle + 每例4个单因素 corruption | 修 schema/evaluator，不训练 |
| WP2 | B1–B5、P1 | 纯旋转不应产生 duplicate birth | 修 projector/association |
| WP3 | G1–G4、M1 | 新走廊覆盖提高且 false birth 不升 | 收缩 growth ontology |
| WP4 | B/G/M/E | 学习相对最佳规则有预注册效应 | pivot 为 benchmark/system |
| WP5 | R1–R6 | revision 提升且 protected 不退化 | ESGBU 子模块降级/删除 |
| WP6 | P1–P3、T1 | 预测提高但 memory truth 不下降 | 不使用 world-model claim |
| WP7 | 全指标适用项 | 至少5 seeds、OOD轴分报 | 删除不支持的 claim |
| WP8 | 外部数据支持项 | 自动映射项明确记 weak/oracle/N/A | 限定模拟器结论 |
