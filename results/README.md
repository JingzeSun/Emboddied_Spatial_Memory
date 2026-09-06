# Results

这里放**可提交的小型运行报告**，用于把在别处（例如租用的服务器）跑出的数字带回仓库分析。

与 [`outputs/`](../outputs/README.md) 的分工：

| 目录 | 内容 | 进 Git |
|---|---|---|
| `outputs/` | 生成的数组、audit、逐序列记录、模型权重 | ✗ |
| `results/` | 汇总后的 JSON 报告与 manifest（KB 量级） | ✓ |

生成方式：

~~~bash
python scripts/export_run_report.py --out-dir outputs/<run> --name <run>
git add results && git commit -m "results: <run>" && git push
~~~

每份报告自带 provenance——git commit、工作区是否 dirty、协议 sha256、dataset version、Python/NumPy/PyTorch 版本、主机名与 CPU 核数——所以两份报告能否放在一起比较是可以查证的，不靠记忆。

三条规矩：

- **只放报告，不放数组。** 单个文件超过几百 KB 就说明放错了东西。
- **`formal_run` 字段必须如实。** 这里的报告默认是非正式运行，不构成 M1 go/no-go。
- **`causal_complete=false` 的报告不能用来支持"减少长期记忆污染"的主张**——那需要跑满 20-step causal self-rollout，单步准确率不是替代品。
