# 文献工作流

> D-062/D-068：当前研究转向空间历史条件的动作后果预测，CTL不预设为核心机制。优先读[空间世界模型定向核查](notes/spatial_world_models_2026.md)。旧CPMT/CTL与记忆笔记保留作历史和相邻工作；当前方法见[方法合同](../docs/METHOD.md)，当前步骤只在[计划](../docs/PLAN.md)。

`library.csv` 是唯一机器文献索引；PDF 文件名不是知识管理系统。同行评审准入见 [`peer_review_audit.md`](peer_review_audit.md)。

## 两条独立状态

- 阅读状态：inbox / skimmed / reading / noted / deep_read / implemented / excluded；
- 同行评审状态：verified_peer_reviewed / preprint_only / submitted_not_accepted / submission_or_preprint / preprint_or_venue_unverified。

`noted` 不代表已同行评审；`verified_peer_reviewed` 也不代表已精读。

## Related Work 用途

- `foundation`：已核验且直接相关，可支撑事实主干；
- `adjacent`：已核验但侧重邻近任务/表示；
- `novelty_watch_only`：只做查重、baseline 和 claim 收缩；
- `excluded`：离题。

没有官方 proceedings、出版社或正式接收页证据，不得升级为 foundation/adjacent。

## 当前精读问题

每篇世界模型论文除状态坐标、更新、数据与指标外，还必须回答：

1. 输入的是机器人控制、假定实现的机器人轨迹，还是物体已知未来变换？
2. 实际能看到哪些历史、深度、位姿、分割或真值初始状态？
3. 监督是未来视觉、几何状态、接触、奖励还是额外教师？
4. 历史是窗口、循环状态、检索还是持续空间表示？证据何时丢失？
5. 视野外动态是实际碰撞、给定运动，还是生成一致性？
6. 是否评估后果准确性、动作选择以及相同近期观察的配对归因？
7. 代码、数据、权重、许可及运行预算分别核验到什么程度？
8. 已有架构、原设定复现和本任务迁移分别有什么证据？

白话：输入论文及实现证据，输出可比较的真实条件。例如“输入末端目标预测物块位姿”和“输入物块变换渲染”必须分开；它不是根据标题给论文贴标签。未执行的复现标planned，论文作者报告与本项目结果分开。

## 添加与更新

1. 合法获得的 PDF 放 `papers/` 或 `papers_detail/`，这些目录不进 Git；
2. 更新 `library.csv` 的官方 URL、状态和用途；
3. 优先更新对应笔记；新增方向级核查可用一个合并笔记，不为每轮讨论批量建模板；
4. 更新 `peer_review_audit.md` 的核验范围和 `docs/METHOD.md` 的当前方法边界；旧综合保留历史用途，不重建已删除合同；
5. 投稿前重新审计 novelty-watch 状态。

作者主页、项目页和社交媒体 venue 声明只能作线索，不能单独作为同行评审证据。
