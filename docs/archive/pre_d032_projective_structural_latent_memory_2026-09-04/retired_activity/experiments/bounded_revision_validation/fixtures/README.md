# Smoke fixtures

本目录只保存可提交 Git 的小型手写事务。正式生成数据和模型输出不放这里。

## 目录格式

```text
fixtures/
  S00_basic_replace/
    case.yaml
    prior_graph.json
    events.jsonl
    oracle_transaction.json
  ...
  S11_task_boundary/
```

每个 `case.yaml` 遵循 `templates/case_contract.example.yaml`，并保存 `decision_ids`。D-027 固定先后顺序：T0a 每个 family 先有1个代表案例；T0b 再扩为：

- positive：真正需要更新；
- no-change control：看起来相似但应保持；
- counterfactual：只改一个因子后正确答案改变。

## 人工工作量

你需要人工复核每个 oracle 事务，而不是手算所有指标。T0a 为12个 family 各1例，每例配3个单因素 deliberate corruptions，即12个语义案例/48个评价器输入；T0b 复用其中语义相符的12例并通常新增24例，形成36个语义案例，每例仍配3个 corruptions，即144个评价器输入。每例复核：

1. 哪些事实必须改；
2. 哪些事实必须保持；
3. 允许哪些等价编辑程序；
4. 有效时间是点还是区间；
5. 哪些 evidence 是直接支持；
6. 哪些依赖任务应失效；
7. 禁止输出及理由。

作者和 reviewer 字段不可由同一自动流程同时填充。单人研究时，可先由自己标注，至少隔一天盲复核；关键歧义样本带到导师/同行处二次确认并保留分歧。

## 进入训练前的门

- schema 全部通过；
- oracle evaluator `12/12` 全接受；
- deliberate corruptions `36/36` 全拒绝，并且 `36/36` 包含预期 primary failure code；
- 48个输入无 crash、silent skip、漏计或把 N/A 当0分；
- 每个 baseline 至少有预期成功和预期失败；
- 任一 case 的人工歧义已通过 HC/decision 解决；
- test split 尚未生成或保持封存。

## 每个 case 必带的 Criteria 纵列

`case.yaml` 的 `evaluation_contract` 不能只写 C-ID；每一项同时写 `local_meaning / calculation / numerator_example / denominator_example / expected_example / governed_by`。

| 例 | local meaning | calculation | 数字示例 | HC |
|---|---|---|---|---|
| S01/C2 | 旧消息不得覆盖新事实 | exact transaction | 1/1=100% | HC-005 |
| S01/C5 | 两个controls都不变 | unchanged/all | 2/2=100% | HC-003 |
| S01/C13 | stale overwrite必须被拒 | post violation | 0/1=0% | HC-016 |

这样打开单个 case 就能知道为什么测、如何计数和由谁冻结，不必再跳到总字典猜语义。
