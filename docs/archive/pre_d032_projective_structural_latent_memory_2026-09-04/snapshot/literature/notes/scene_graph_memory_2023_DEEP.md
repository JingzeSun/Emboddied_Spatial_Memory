# Scene Graph Memory 精读：动态位置预测不等于旧图修订

> 论文：**Modeling Dynamic Environments with Scene Graph Memory**
> venue：ICML 2023，PMLR 202:17976–17993
> 同行评审状态：`verified_peer_reviewed / foundation`
> 精读日期：2026-08-28
> 官方来源：[PMLR](https://proceedings.mlr.press/v202/kurenkov23a.html)

## 一句话结论

SGM 把“根据不完整历史预测对象现在可能在哪里”形式化为部分可观测动态图上的 link prediction；它证明动态空间先验与历史适应本身不是空白，但没有规定新证据反证旧事实时应执行什么 typed delta、传播到哪些关系、在哪里停止。

## 问题与输入输出

论文考虑会随时间移动、出现或消失对象的家庭场景。智能体只能观察当前选择区域的一部分节点和边，需要预测 query object 与哪个 furniture node 相连，再据此搜索目标。

```text
partial observations O0...Ot
  → Scene Graph Memory
  → Node Edge Predictor
  → P(query edge exists)
  → object-search action
```

SGM 累积曾观测到的 node/edge，并为其保存最近观测时间、观测次数、变化次数、历史成立频率等特征。NEP 用节点、边编码与 self-attention 比较目标节点的候选边。

## 实验结构

- Dynamic House Simulator 用 room–furniture–object 概率图生成不同家庭及对象移动规律；
- 主要预测对象与家具的关系，并在 iGridson 中评估对象搜索；
- observation 可漏掉对象，以模拟 partial observability；
- 论文比较 myopic、Bayesian、图网络与 NEP 变体，并报告 link prediction 与搜索效率。

## 优点

1. 问题定义清楚：动态图、节点可变、部分可观测、只预测任务相关边；
2. 把通用先验与环境特定历史结合，而不是只用静态共现；
3. 数据生成可以控制对象变化规律，适合构造单因素反事实；
4. 表示显式保留时间与变化统计，便于分析模型依据。

## 局限与适用边界

- 主实验集中于 symbolic graph 和半真实 2D iGridson；感知、关联与真实 3D 导航被抽象；
- iGridson 中对象主要在固定家具集合间移动，物理关系与可见性证据较简化；
- 输出是 query edge 概率，不是事务化世界编辑；
- 没有 affected/control set、operator-specific propagation、stop edge 或 supersedes/version invariant；
- 预测正确位置不能证明无关旧事实没有被误改。

## 对本项目可借鉴的内容

1. 把 R1–R6 写成部分可观测动态关系图，而不是只做视频变化分类；
2. 用单因素环境生成控制 `identity / visibility / dependency / relevance / history`；
3. 保留 link-level 指标，但增加 `required propagation recall`、`control preservation` 与 `collateral revision`；
4. SGM/NEP 可作为“预测对象位置”的邻近基线，不能替代 revision executor 基线。

## 与当前项目的最小差异

```text
SGM: history → where is the object likely to be?
Ours: belief + current evidence → which old facts must change, remain, or stop propagating?
```

前者优化目标是 query prediction；后者需要输出可执行、可追溯且范围受控的 ContextDelta。

## Evidence pointers

- Sec. 3：partial-observable temporal link prediction；
- Sec. 4.1：Dynamic House Simulator；
- Sec. 4.2–4.3：SGM 与 NEP；
- Sec. 6：link prediction / object-search 实验；
- Appendix E.3：作者明确说明真实 3D perception/navigation 尚属扩展方向。
