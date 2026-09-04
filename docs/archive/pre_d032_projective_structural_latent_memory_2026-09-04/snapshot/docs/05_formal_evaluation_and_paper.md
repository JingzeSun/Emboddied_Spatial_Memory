# 05 正式评价、论文证据与投稿路线

## 正式表格

### Table 1：Updater-isolation 主结果

R0–R3、L0–L4、M0 和 O0；报告 edit macro-F1、transaction exact、NUR、CPR、CER、time、evidence F1、ECE、task errors、p95 latency。统一输入和 executor，投影前后分列。

### Table 2：多轴 OOD

unseen room、object composition、delay、conflict/source、change rate、dependency depth 分列；不只给一个 hard split 平均值。

### Table 3：结构与方法消融

flat vs typed graph、full write vs sparse mask、双时间、visibility、source、grouping、time head、evidence head、executor、可选 task loss。

### Table 4：外部有效性

3RScan/3DSSG zero-shot 和可选 adapted 分开；只报真实数据支持的 relation/object change、interval time 和 preservation。

### Figure 1–3

- 方法图：evidence events → heterogeneous graph → mask/edit/time/evidence → executor；
- calibration/robustness：随 delay/conflict/visibility 的曲线；
- qualitative transaction：正确最小修改和失败案例各一例。

## 统计与报告

- 至少 5 个正式 seeds，逐场景 paired bootstrap 95% CI；
- 报 effect size，不用“有显著性”替代实际差异；
- OOD 和多消融说明多重比较策略；
- 缺失、崩溃、投影拒绝、无合法事务和反例都计数；
- test 只在合同、阈值、baseline 和 checkpoint 规则冻结后运行。

## 论文结构

1. 问题：旧世界状态面对异步不可靠证据；
2. 相关工作：动态图/场景图/持久记忆已做什么，缺哪组事务语义；
3. benchmark：双时间事件、最小编辑、有效时间、证据集合和任务依赖；
4. 方法：ESGBU 与 deterministic projection；
5. 实验：规则→时序→图→稀疏方法→oracle；
6. 反证与限制：哪些假设不成立、真实数据缺哪些标签；
7. 结论：只写被表格支持的 claim。

## 投稿质量路线

- RA-L：官方定位是简洁、显著创新的机器人理论或应用结果，常规篇幅 6 页、最多 8 页，适合作为“一个清楚的新任务 + 紧凑方法 + 完整实验”的质量标尺。[官方作者信息](https://www.ieee-ras.org/publications/ra-l/ra-l-information-for-authors/)
- RSS：强国际机器人会议，论文主张需在正文自包含；会议路线不等于 SCI 期刊路线。[官方 CFP](https://roboticsconference.org/information/cfp/)
- T-RO：官方强调对机器人领域的重要推进，适合在 RA-L 级证据上增加真实长序列、跨域、机制或保证后再考虑。[官方介绍](https://www.ieee-ras.org/publications/t-ro/) 与 [作者信息](https://www.ieee-ras.org/publications/t-ro/t-ro-information-for-authors/)

具体 venue 要等结果形状再选：若主要贡献是 benchmark + 紧凑模型，优先短而聚焦；若有真实系统和大规模机制证据，再扩展期刊。不得先选刊再伪装贡献。

## 国内 A 类与博士申请

SCI 是索引，不是统一等级；“A 类”取决于目标学校/学院/项目采用的最新版目录，可能与 CCF 或期刊分区不一致。用户需要提供目标认定表，仓库才能建立 venue matrix。

面向强博士申请，优先形成可复现的第一作者主线、公开 benchmark/code、诚实失败分析和能被推荐信具体描述的独立研究能力。刊名重要，但不能替代这些证据，也不保证录取。

## 投稿前硬门

- evaluator 与数据泄漏审计通过；
- strongest baselines 和容量/时间预算公平；
- 主效果覆盖准确、保护、时间/校准与任务后果，而非单指标；
- AI2-THOR ID/OOD 完整；
- 至少一个外部或真实证据轨，或明确把 claim 限定在模拟器；
- 失败案例、局限、代码/配置/manifest 可复现；
- 每项 contribution 与一张表或一个消融一一对应。

