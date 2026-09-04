# 动态场景图验证实验的成熟做法：面向有界信念修订的阅读笔记

状态：`literature note / not an accepted project decision`

目的：只提炼可用于 `bounded_revision_validation` 的实验设计模式，不把相关工作的任务或指标直接当作本项目 ground truth。

## 1. Khronos：把不同能力和输入质量拆开测

Khronos 在模拟公寓、模拟办公室和真实机器人序列上分别验证长期时空感知，并把背景重建、静态物体、短期动态和长期变化分开评价。它还分别使用 ground-truth 与估计位姿、ground-truth 与开放集语义输入，以隔离前端质量对后续模块的影响。

对本项目可采用的模式：

- 首轮固定 oracle 身份、可见性和位姿，只评价修订逻辑。
- 核心通过后，再一次加入一种估计误差。
- 时间变化既评价是否检测正确，也评价出现/消失时间；真实时刻不可见时，用最后支持与首次观测之间的区间表达不确定性。

不直接照搬之处：Khronos 的对象级 precision/recall/F1 不能评价“无关事实是否被保留”“依赖传播是否越界”和“证据能否追溯”。本项目必须补 scope/control/provenance 指标。

来源：[Khronos, RSS 2024](https://www.roboticsproceedings.org/rss20/p081.html)；[论文 PDF](https://roboticsproceedings.org/rss20/p081.pdf)。

## 2. Scene Graph Memory：每个研究问题使用自己的任务指标

Scene Graph Memory 没有用一个总分概括所有能力，而是设置相对似然预测、对象位置预测和序列式对象搜索三个任务；搜索任务直接以找到目标前的动作数评价，并使用 Random、Frequentist、Priors、Myopic、Bayesian、Oracle 等不同能力层级的基线。论文还在未见环境上测试，并通过模块消融解释提升来自哪里。

对本项目可采用的模式：

- P1、P2、P3 分别用分类、事实编辑和范围控制指标，不做跨任务平均。
- 简单规则基线与 oracle 上界都保留；oracle 用于评测器校验，不包装成可部署方法。
- 模板冻结后才生成未见对象、布局与关系组合的 test 实例。

不直接照搬之处：该工作的下游对象搜索指标适合证明记忆有任务价值，但不能代替修订正确性；应放在核心门槛之后。

来源：[Scene Graph Memory, ICML 2023（PMLR）](https://proceedings.mlr.press/v202/kurenkov23a.html)。

## 3. SuperMap：静态质量、动态一致性和下游任务分层报告

SuperMap 将研究问题拆成语义地图质量、时空一致性、具身推理和在线导航。动态实验在真实环境中主动添加与移除对象，并分别报告对象检测和变化检测；其分析还指出，若系统一开始就漏检对象，某些“变化召回”可能看起来虚高。

对本项目可采用的模式：

- 变化指标必须先定义 eligibility：旧对象此前确实被确认，且本轮相关区域可判定。
- 保护类场景与真正变化场景分开计分，避免把前端漏检奖励成变化成功。
- 核心结构正确性、运行开销和下游导航分层报告。

不直接照搬之处：仅用 change recall 不能区分遮挡保护、错误实体合并和依赖越界，因此 P1 必须有 commit precision，P3 必须有 control preservation。

来源：[SuperMap, RSS 2026](https://www.roboticsproceedings.org/rss22/p052.html)；[论文 HTML](https://arxiv.org/html/2608.22896v1)。

## 4. 本项目因此采用的最小验证结构

| 成熟论文常用做法 | 本项目对应实现 |
|---|---|
| 按研究问题拆任务 | P1 证据路径、P2 时序编辑、P3 依赖范围 |
| oracle 与 estimated 输入分开 | 首轮 oracle；通过后逐项加噪声 |
| 每类能力有专属指标 | macro-F1、fact-edit F1、scope/control 指标分别报告 |
| 简单基线 + oracle 上界 | append、overwrite、local、full recompute、oracle delta |
| 消融与反事实 | visibility、identity、support、base version 成对改变 |
| 静态、动态、下游分层 | 核心修订先过门槛，下游任务后置 |

这组设计是从论文的验证结构推导出的项目选择，不是论文原结论。数值阈值、样本量和 HC-015/016 的语义仍需本项目单独确认。

