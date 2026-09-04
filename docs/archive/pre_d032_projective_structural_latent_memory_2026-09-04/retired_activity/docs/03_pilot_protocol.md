# 03 Pilot：尽早知道方法是不是垃圾

## 先决选择

D-026～D-030 已完整冻结 HC-018/Q01：第一批先走 hand-authored oracle smoke；T0a 为12个语义案例/48个输入、严格100%判尺门和适用性criteria；通过后 T0b 扩为总计36个语义案例/144个输入，再做 symbolic/AI2-THOR。T0a 采用CPU-first和40小时硬上限，约24小时仍未接近严格门时提前汇报；后续学习训练使用已验证的 RTX 4070 Laptop CUDA。现在先冻结 HC-002 等 oracle 语义，不把训练写成已授权启动。

## Pilot A：判尺自测

对 S00–S11，每例构造 oracle output 和至少三种故意错误：漏改、越界修改、错误时间/证据。evaluator 必须给 oracle 全通过，并把错误归到正确类别。这一步不比较模型性能，只回答“以后分数值得信吗”。

## Pilot B：规则必要性检查

在 development symbolic data 上比较 R0 last-arrival、R1 last-event、R2 Bayes 和 R3 evidence gate。

若 R3 在 delay/conflict/visibility/dependency 的完整因子网格上已近 oracle，则学习模型没有必要；可以把工作转成 benchmark 或 executor 论文，而不是继续堆网络。

## Pilot C：最小学习检查

只训练 L0 FlatFact-MLP、L1 GRU、L2 Event-Transformer、L4 FullGraph-HGT 和 M0 ESGBU-tiny。先固定 1 个 debug seed，管线正确后用 3–5 个 seeds。

进入完整 AI2-THOR 的候选门：

- 学习方法显著优于 R3，证明任务确实需要学习；
- M0 不仅 edit F1 高，还在 NUR/CPR、time/calibration 中至少两类优于 L2/L4；
- 优势在未见 delay 或 conflict validation split 上仍存在；
- executor 的共享收益没有解释全部差距。

## Kill / pivot 条件

- Event-Transformer 与 ESGBU 等价：删掉“图结构必要”主张；
- FullGraph-HGT 与 ESGBU 等价：删掉“稀疏 mask 提升准确性”主张，只保留有证据的效率结论；
- 共享 executor 后差距消失：方法贡献转向结构执行器；
- edit F1 提升但 CPR/task 不改善：不宣称世界状态维护更安全；
- attribution 干预不忠实：降级为辅助诊断；
- 多 seed 方差大于方法差：先修数据/优化，不上正式 test。

## Pilot 输出

- 一张方法 × 指标表；
- 一张 delay/conflict/visibility 曲线；
- 一张投影前后合法性表；
- 10 个最有信息量的失败案例；
- 明确的 continue / shrink / pivot 决定和对应 D-ID。

完整协议见实验包 `PROTOCOL.md` 与 `NOVELTY_AND_FALSIFIERS.md`。

## Pilot 就地 Criteria 纵列

| Pilot | 关键 Criteria | 白话含义 | 数字例子 | 决策 |
|---|---|---|---|---|
| A 判尺 | oracle gate、C1–C15可算 | 先确认尺子会抓错 | 12例×4输出=48，oracle必须100% | 否则禁止训练 |
| B 规则 | C1–C7/C12/C13 | 判断学习是否必要 | R3在各轴近oracle则不堆网络 | benchmark/executor pivot |
| C 学习 | C2/C3/C5/C8–C13/C15 | 判断图、稀疏、双时间是否真有用 | edit高但CPR<99.5%仍No-Go | continue/shrink/pivot |
| AI2-THOR前门 | OOD + 5 seeds + CI | 防止单seed/单分布偶然 | delay/conflict分别报告paired 95% CI | 过门才正式生成test |

详细计算仍见 `CRITERIA.md`，但做当前 Pilot 时不需要离开本表才能理解判定目的。
