# 评价 CRITERIA 与人工冻结项

本文件把“怎么计算”与“什么数算过关”分开。公式可实现；阈值、等价答案和代价偏好必须由人冻结。以下阈值均是讨论起点，不是已接受结论。

## 1. 编辑是否正确

### C1 Edit macro-F1

含义：分别计算 `KEEP/ASSERT/RETRACT/REPLACE/QUARANTINE` 的 F1 再平均，避免大量 KEEP 掩盖少数编辑失败。

例：五类 F1 为 `0.98, 0.80, 0.70, 0.60, 0.72`，macro-F1 为 `(0.98+0.80+0.70+0.60+0.72)/5=0.76`。同时报告 micro-F1，但不作为唯一主指标。

### C2 Transaction exact match

含义：一个事务的操作、目标、时间和证据集合是否整体正确。允许的等价程序由 HC-013 冻结。

例：100 个事务中 71 个完全等价，exact match=`71%`；即使 fact-level F1 是 `0.92`，也说明组合事务仍有问题。

## 2. 必要修改与无关保护

### C3 Necessary-update recall（NUR）

含义：oracle 必须修改的事实中，方法改对了多少。漏改会留下陈旧世界状态。

例：oracle 要改 20 个事实，方法正确覆盖 18 个，NUR=`18/20=90%`。

### C4 Affected-set precision / recall / F1

含义：`M_t` 是否找到真正受影响范围。precision 低表示圈太大，recall 低表示漏掉依赖。

例：oracle affected 有 8 个，模型选 10 个，其中 7 个正确：precision=`7/10=70%`，recall=`7/8=87.5%`，F1=`77.8%`。

### C5 Control preservation rate（CPR）

含义：明确标为 protected controls 的无关事实有多少保持逐字段不变。

例：200 个 control facts 中 199 个保持，CPR=`99.5%`。一个被误改也必须列出，而不是只报四舍五入的 `1.00`。

### C6 Collateral edit rate（CER）

含义：实际写操作中，有多少落在 oracle affected closure 之外。

例：模型写了 12 个事实，其中 3 个越界，CER=`3/12=25%`。若模型完全不写，CER 虽为 0，但 NUR 也会暴露失败。

### C7 Stop-boundary exactness

含义：依赖传播是否恰好在应停止处停止。建议同时报告 boundary edge F1 与 transaction-level exact match。

例：10 个事务中 8 个边界完全正确；余下两例多传播 1 层，exact=`80%`，平均 excess depth=`0.2`。

## 3. 时间与证据

### C8 Exact valid-time MAE

含义：有精确事件标签时，预测有效时间与真实变化时刻的平均绝对误差。

例：三例误差 `1, 3, 2` 秒，MAE=`2 s`。不得用 received_at 作为真值。

### C9 Interval coverage 与 width

含义：只有区间标签时，预测区间是否覆盖真实允许区间，以及区间是否过宽。只追求 coverage 会输出无限宽区间。

例：真实变化在 `[100,140]`，预测 90% 区间为 `[105,135]`，它未覆盖整个标注区间；若评价点真值不可得，则报告与允许区间的 overlap/coverage 规则。100 例覆盖 91 例，coverage=`91%`，平均 width=`38 s`。

### C10 Evidence-set F1

含义：模型引用的证据是否属于直接支持集合。

例：oracle `{e2,e5,e8}`，模型 `{e2,e5,e9,e10}`，precision=`2/4=50%`，recall=`2/3=66.7%`，F1=`57.1%`。

### C11 Evidence sufficiency / redundancy

含义：只保留模型选中证据时决策是否仍成立；逐条移除时是否包含大量无用证据。这是 intervention-style 诊断，不等于真正因果证明。

例：删除未选证据后 commit 概率从 `0.86` 到 `0.82`，仍过门；移除选中的 e5 后降到 `0.41`。若 6 条被选证据中只有 2 条有此作用，redundancy=`4/6=66.7%`。

## 4. 校准、合法性与任务后果

### C12 Commit calibration

含义：模型说 80% 可提交的事务，是否约 80% 真能正确提交。报告 ECE、Brier 和 reliability diagram。

例：置信度 0.8–0.9 的 100 例平均预测 `0.84`，实际正确 `0.72`，该 bin calibration gap=`0.12`。

### C13 Constraint violation / projection rejection

含义：投影前候选有多少违反互斥、provenance、valid-time 或 dependency；投影后必须为 0，同时报告多少候选被拒绝。

例：1000 个候选中 40 个非法，pre-violation=`4%`；executor 拒绝 35、修复 5，post-violation 必须=`0`，rejection=`3.5%`。不能只报投影后 0 而隐藏模型质量。

### C14 Downstream task errors

含义：世界事实错误带来的 wrong dispatch、missed invalidation 与 collateral recompute 分开报告。

例：100 个应启动任务中错启 6 个，wrong dispatch=`6%`；40 个应失效任务中漏关 5 个，missed invalidation=`12.5%`；200 个无关任务重算 8 个，collateral recompute=`4%`。

若必须合成 cost，候选权重可为 `错启=5、漏关=10、无关重算=1`。上述额外成本=`6×5+5×10+8×1=88`。权重体现应用风险，必须人工确认，主表仍保留分项。

### C15 Efficiency

含义：稀疏更新是否真的少写、少算，而不是只换一个名字。报告 edited-fact fraction、visited edges、p50/p95 latency、峰值显存。

例：2000 个 facts 中写 12 个，edited fraction=`0.6%`；访问 420/18000 条边=`2.33%`；p95 latency=`47 ms`。同时报告 FullGraph-HGT 的对应数字。

## 5. 候选硬门（待 HC-013 冻结）

| 门 | 起始候选 | 为什么 |
|---|---:|---|
| evaluator oracle | 100% | 判尺自己不能错 |
| NUR | ≥95% | 稀疏不能靠漏改换效率 |
| CPR | ≥99.5% | 保护无关事实是核心主张 |
| post-projection violations | 0 | 硬结构不能破例 |
| transaction exact | ≥80% | 防止单项分数高但事务组合错 |
| ECE | ≤0.05 或显著优于 strongest baseline | 绝对/相对门二选一待定 |
| OOD relative drop | ≤20% 且优于 strongest baseline | 防止只记住训练延迟分布 |
| p95 latency | 按目标硬件冻结 | 研究主张先不假装部署需求 |

这些不是论文保证。pilot 若显示标签上限达不到，应先修标签或公开缩小门，而不是看 test 后改门。

### T0a 适用性分层（D-029 已接受）

- C1–C10、C13、C14：有对应标签和定义分母时必须计算并保存 raw counts；
- C1：五类未齐时完整 macro-F1 记 N/A，但仍保存已覆盖类别的 TP/FP/FN；
- C11/C12：T0a 没有可运行概率模型或足够 cohort 时记 N/A；
- C14：三项原始任务错误必报，合成 cost 在 HC-019 前记 N/A；
- C15：只验证 edited-fact、visited-edge、latency/memory 字段能记录，不设置性能门；
- 所有 N/A 必须有原因并排除出聚合分母，不能当作0分或100%。

## 6. 需要你人工决定什么

你不需要手工计算每个指标，也不需要一开始标几万条数据；代码负责计算。你需要冻结的是评价语义：

| 关联 HC | 你要决定的内容 | 推荐起点 | 数字例子 |
|---|---|---|---|
| HC-013 | 主指标与硬门是否采用上表 | NUR/CPR/transaction exact 为主；edit F1 为辅 | NUR 95%、CPR 99.5%、exact 80% |
| HC-013 | 多个正确编辑程序是否等价 | 最终状态、最小写集、时间和证据均等价即可 | `REPLACE` 与同事务 `RETRACT+ASSERT` 可等价 |
| HC-015 | 精确时间容差与区间评分 | 模拟器 ±1 step；重扫用区间 | 20 Hz 模拟器即 ±0.05 s |
| HC-016 | 何时必须 QUARANTINE | 高可信冲突且无一方占优时 | 0.86 vs 0.84 不硬选；0.95 vs 0.40 可提交 |
| HC-004 | 负证据“充分可见”的语义 | 由覆盖率字段定义，数值阈值在 validation 学/选 | visibility 0.2 不撤回，0.9 才进入候选 |
| HC-017 | baseline 的同预算口径 | 同参数档 + 同 wall-clock 两张表 | 均 10M±10%；另均训练 6 GPU-hours |
| HC-018 | 先 T0 还是先 AI2-THOR | 推荐先 12 个 T0，再生成数据 | 判尺先跑 12×(1 oracle+3 corruptions)=48 例；adapter 齐全后再做 12×11=132 次接口 smoke |
| HC-019 | task cost 是否需要合成 | 先只报三项，不合成 | 若合成，5/10/1 权重必须说明行业理由 |

HC 工作表只承载选项；最终答案仍追加到 `docs/DECISIONS.md`，并进入 run manifest 的 `decision_ids`。
