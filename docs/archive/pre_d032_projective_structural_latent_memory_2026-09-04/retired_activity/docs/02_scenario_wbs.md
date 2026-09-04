# 02 单人研究 WBS 与场景工作分解

## 总原则

每个工作包只有一个问题、一个产物、一个退出门。先建立能推翻方法的判尺，再增加模型复杂度。周报 PPT 按“本周假设—证据—失败—下个判别实验”组织，不按模块数量汇报。

## 工作包

| WP | 任务 | 可交付物 | 退出门 |
|---|---|---|---|
| WP0 | 冻结人工语义 | HC 决策、metric/hard-gate version | oracle 答案不再因口头解释漂移 |
| WP1 | canonical schema/executor/evaluator | schema、unit tests、12 smoke cases | oracle 100%，故意错误均被抓住 |
| WP2 | symbolic generator | 因子化事件流、split manifest | 单因子反事实能改变正确答案 |
| WP3 | 规则与学习基线 | R0–R3、L0–L4、统一 adapter | 同输入、同预算、同 executor 可复现 |
| WP4 | ESGBU tiny/base | mask/edit/time/evidence heads | 相对强基线出现多维增益，否则 kill |
| WP5 | AI2-THOR | oracle/frozen perception、ID/OOD | 多轴 OOD 分开报告，无 test 调参 |
| WP6 | 3RScan/3DSSG | scan-to-scan transactions | 明确 zero-shot 外部有效性边界 |
| WP7 | 论文与 artifact | 表格、失败 taxonomy、复现包 | 每个 claim 有对应表/消融/反例 |

## 场景工作分解

场景不按“房间里有什么对象”分，而按造成后验困难的变量分：

1. 世界是否真的变化；
2. 证据 event time 与 arrival time；
3. 正/负证据及 visibility；
4. 来源可靠性与冲突；
5. evidence group 独立/相关；
6. dependency depth 与 protected controls；
7. 精确时间/区间时间；
8. 图规模与候选检索规模。

详细因子水平和 12 个 smoke families 见实验包 `SCENARIOS.md`。

## 单人执行优先级

优先保住：数据合同、evaluator、两三个强基线、关键消融、失败分析。延后：大模型、漂亮 demo、端到端导航、过多数据集和不影响主张的 UI。

最小可投稿证据链候选为：可复现任务 + AI2-THOR + R/L/graph 强基线 + ESGBU + OOD/消融/失败。3RScan 是提升外部有效性的优先扩展，但不能以粗糙标签拖垮主实验。

## 周报模板

```text
1. 本周只验证哪个假设？
2. 固定了哪些变量，改变了哪个变量？
3. 结果是否支持假设，effect size/CI 是多少？
4. 最重要失败案例是什么？
5. 下周哪个实验能最大幅度改变继续/停止决定？
6. 需要导师只判断哪个具体问题？
```

导师如果只评价 PPT，也应让每页对应一个可判定选择，而不是展示庞大架构让其泛泛评价。

## WBS 的 Criteria 纵列

| WP | 本阶段的“通过”是什么意思 | Criteria/门 | 数字例子 | 不通过做什么 |
|---|---|---|---|---|
| WP0 | 人工语义可生成唯一/等价oracle | HC-002–005/013/015–019有D-ID | 10个当前HC全部回答才冻结正式contract | 保持design，不训练 |
| WP1 | 判尺自身正确 | oracle=100%、C1–C15手算对拍 | 12×4=48 inputs | 修schema/evaluator |
| WP2 | 因子变化真的改变正确答案 | C1–C13 counterfactual | visibility .2→.9只改变absence答案 | 修生成器 |
| WP3 | 强下限公平可复现 | C1–C15、SA1–SA8、预算 | 10M±10%和6 GPU-hours两表 | 修adapter/预算 |
| WP4 | ESGBU有多维而非单分优势 | C2–C15 | NUR/CPR过门且time/calibration至少两类提升 | shrink/pivot |
| WP5 | 可控具身OOD成立 | AI2-THOR相关C1–C15 | 5 seeds、paired 95% CI | 只保留支持的轴 |
| WP6 | 真实外部数据不推翻主张 | C1–C7/C9/C10/C14 | 3RScan coverage与width分报 | 限定模拟器claim |
| WP7 | 每个论文claim都有表与反证 | publication gates | 一项claim至少一主表+一消融 | 删除无证据claim |
