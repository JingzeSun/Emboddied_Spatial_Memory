# 顶级论文的增量创新对照

## 结论

顶会/顶刊论文通常不是每个组件都从零开始。DINO-WM 依赖预训练视觉特征和已有 world-model/planning 范式；persistent embodied world models 组合生成模型与 3D map；scene-graph memory 也建立在图表示、partial observability 和预测之上。它们能成立的关键不是“与所有前作零重合”，而是：

1. 把一个以前没有被清楚解决的 failure mode 定义为可测问题；
2. 给出与该问题匹配、无法轻易被弱化为已有 baseline 的机制；
3. 用强对比排除最合理的替代解释；
4. 在足够现实的设置中证明收益和边界。

## 对 CPMT / CTL 的客观标准

CPMT 与 prior work 重合很大：DINO latent、future prediction、persistent memory、graph edits、MHT、versioning 都不是新。重合本身不判死刑；CTL 必须证明 post-edit executable supervision 不可被普通 future loss 替代。

要达到同等级的“可辨认贡献”，论文必须让下面这条因果链在实验中不可替代：

transaction proposal → sandbox execution → post-edit future evaluation → hindsight target → no-future online commit

因此最关键的不是增加更多模块，而是 A vs C/E：

- C 保留相同标签和 future supervision，拿掉 post-edit execution；
- E 保留 future scorer，拿掉执行后 world；
- 若 A 不能稳定超过二者，审稿人说“只是换 loss/训练标签”是正确评价。

## 风险评级

| 风险 | 当前判断 |
|---|---|
| 概念完全被占 | 尚无证据；但没有系统综述能保证不存在 |
| 组件重合 | 极高 |
| 组合式叙事被判工程拼接 | 高 |
| 通过 hard-condition 后形成方法贡献 | 中等，有条件 |
| 单人直接完成全视觉+真机+顶刊 | 低，应按 M0–M3 严格过门 |

## 投稿前强制再审计

在实验冻结与投稿前各做一次检索，核对 2026–2027 新作、官方 acceptance、开源实现和最新 baseline。新论文出现时优先收缩 claim 和增加必要基线，不事后改变 test 指标。
