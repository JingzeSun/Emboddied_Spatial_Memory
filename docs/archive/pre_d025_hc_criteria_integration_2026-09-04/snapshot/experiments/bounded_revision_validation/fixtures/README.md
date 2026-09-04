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

每个 `case.yaml` 遵循 `templates/case_contract.example.yaml`，并保存 `decision_ids`。每个 family 至少有：

- positive：真正需要更新；
- no-change control：看起来相似但应保持；
- counterfactual：只改一个因子后正确答案改变。

## 人工工作量

你需要人工复核每个 oracle 事务，而不是手算所有指标。初始建议 12 个 family 各 3 例，共 36 例；若先做最小 smoke，可先每族 1 例共 12 例。每例复核：

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
- oracle evaluator 100%；
- 每个 baseline 至少有预期成功和预期失败；
- 任一 case 的人工歧义已通过 HC/decision 解决；
- test split 尚未生成或保持封存。

