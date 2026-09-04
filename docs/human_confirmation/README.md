# Human Confirmation 索引

这些文件是研究设计的人工冻结点，不是普通待办。按顺序处理；上游决策变化时，下游必须重新审查并在 `docs/DECISIONS.md` 记录影响。

| ID | 主题 | 状态 |
|---|---|---|
| HC-020 | 第一批验证路线 | WAITING_USER |
| HC-021 | 线上输入与 oracle | BLOCKED |
| HC-022 | structural tokenizer | BLOCKED |
| HC-023 | memory hierarchy | BLOCKED |
| HC-024 | binding identity | BLOCKED |
| HC-025 | birth/confirmation | BLOCKED |
| HC-026 | Chart/Place attachment | BLOCKED |
| HC-027 | lifecycle/visibility | BLOCKED |
| HC-028 | latent state/update | BLOCKED |
| HC-029 | revision transaction | BLOCKED |
| HC-030 | time/provenance/quarantine | BLOCKED |
| HC-031 | metrics/gates | BLOCKED |
| HC-032 | baseline fairness | BLOCKED |
| HC-033 | datasets/splits | BLOCKED |
| HC-034 | downstream task | BLOCKED |

当前只需先处理 [HC-020](HC-020.md)。每个文件都给出建议项、替代项、风险、接受测试和 YAML 填写区。确认后需要同步更新 EXECUTE、配置与决策日志；未确认项继续标记 planned/pending。

指标释义见 [METRIC_GUIDE](METRIC_GUIDE.md)。

