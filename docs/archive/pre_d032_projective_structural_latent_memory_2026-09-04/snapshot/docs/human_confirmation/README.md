# 当前 Human Confirmation

本目录只保留与 ESGBU 后验修订直接相关的十个工作表。状态和最终答案只记录在 `docs/DECISIONS.md`；本目录负责把选择、场景、criteria、公式和数字例子展开。

## 推荐阅读顺序

| 顺序 | HC | 先决定什么 | 为什么先看 |
|---:|---|---|---|
| 1 | [HC-018](HC-018.md) | hand-authored smoke 或 AI2-THOR-first | 决定第一批实际工作 |
| 2 | [HC-002](HC-002.md) | stored/derived facts | 决定什么才是可编辑对象 |
| 3 | [HC-003](HC-003.md) | dependency closure/stop | 决定 `M_t` 真值 |
| 4 | [HC-004](HC-004.md) | reliable negative evidence | 决定何时能撤回 |
| 5 | [HC-005](HC-005.md) | 等价编辑程序 | 决定 evaluator 接受什么 |
| 6 | [HC-015](HC-015.md) | valid-time 点/区间 | 决定 `τ_t` 标签和评分 |
| 7 | [HC-016](HC-016.md) | commit/quarantine | 决定破坏性写入门 |
| 8 | [HC-013](HC-013.md) | C1–C15 主次与 hard gates | 决定什么结果算继续 |
| 9 | [HC-017](HC-017.md) | 结构化基线与预算公平 | 决定比较是否可信 |
| 10 | [HC-019](HC-019.md) | task cost 是否合成 | 决定应用评价写法 |

若只想立刻开始，先回答 HC-018；若要冻结第一版 evaluator，再完成 HC-002/003/004/005/015/016/013。

## 每份工作表统一结构

1. 当前必须由人决定的问题；
2. 已固定、不再讨论的不变量；
3. 可选方案及代价；
4. `criterion｜在本 HC 中是什么意思｜怎么算/判定｜数字例子｜需要填什么` 纵向表；
5. 正常、边界、反事实与禁止结果；
6. 用户填写区与落盘位置。

`experiments/bounded_revision_validation/CRITERIA.md` 是 C1–C15 唯一总字典。工作表中的解释是就地摘录，不能另改公式或状态。

## 已归档而非删除

HC-001/006–012/014 属于旧完整闭环的身份、澄清、动作、结构扩展、定位、主动取证与区域绑定问题，已从活动目录移除。D-025 前版本保存在 `docs/archive/pre_d025_hc_criteria_integration_2026-09-04/`；它们不再阻塞 posterior-only 项目。

