# 04 CTL 训练计划

定位：正式训练方案；完整视觉训练须 M1 支持继续，M1 正式比较须协议冻结。D-027 已授权的开发训练不在此禁止范围；当前进度见 [实验记录](../EXECUTE.md)。

## 固定模块

首篇固定 observation encoder、depth、pose、region proposals、candidate generator 和 deterministic executor。这样训练变量只剩：

1. 轻量 PredictProject/future scorer；
2. online transaction model \(q_\theta\)。

不得同时训练 backbone、candidate proposer 或 active policy。

## 训练顺序

### T0：Oracle execution

执行人工 programs，验证 schemas、world diffs、能量分项和 metrics。没有 learning claim。

### T1：Hindsight posterior

对每个候选执行后世界计算 now/future/edit/growth/collateral/illegal，形成 \(p^*(u)\)。所有权重和 temperature 只在 validation 冻结。

### T2：Online amortization

\[
\mathcal L_{\mathrm{CTL}}
=
\operatorname{KL}\!\left(
\operatorname{stopgrad}(p^*)\Vert
q_\theta(u\mid S_{t-1},R_{\le t},a_{<t})
\right).
\]

若有多个等价 programs，使用 equivalence-set likelihood。该 KL 是实现手段；创新来自 target 的 executable post-edit construction。

### T3：Self-rollout

online model 使用自己的 committed graph 继续预测。teacher-forced 与 self-rollout 分开报告，不混合。

## 标签效率

在相同 split 上比较 0%、1%、10%、100% transaction labels。0% 设置仍使用固定 transaction language、future observations 和 executor，因此称 transaction-label-free，不称完全无监督。

## 误差分解

- candidate miss：正确 equivalence set 不在 top-K；
- teacher error：正确候选存在但 \(p^*\) 排错；
- amortization error：teacher 正确但 \(q_\theta\) 排错；
- rollout error：单步正确但历史污染导致后续失败。

## 复现

每个 run 记录 code/data/config hash、seed、front-end IDs、future-use policy、energy components、label fraction、teacher/student mode、逐例结果和全部失败。
