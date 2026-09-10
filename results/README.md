# Results

这里放可提交的运行报告和明确选取的分析导出，用于把服务器结果带回仓库。历史导出保留原始字节，不能因为有更新的报告就改写或删除仍被合同哈希引用的文件。

与 [`outputs/`](../outputs/README.md) 的分工：

| 目录 | 内容 | 进 Git |
|---|---|---|
| `outputs/` | 生成的数组、audit、逐序列记录、模型权重 | ✗ |
| `results/` | 汇总报告、逐例指标、manifest 和有界案例导出；大小依阶段而异 | ✓ |

生成方式：

~~~bash
python scripts/export_run_report.py --out-dir outputs/<run> --name <run>
git add -- results/<run>.json
git commit -m "results: <run>"
git push origin main
~~~

每份报告自带 provenance——git commit、工作区是否 dirty、协议 sha256、dataset version、Python/NumPy/PyTorch 版本、主机名与 CPU 核数——所以两份报告能否放在一起比较是可以查证的，不靠记忆。

三条规矩：

- **不放全量 arrays/权重。** 逐例指标可能达到数十 MB；体积不能单独决定是否有价值。少量完整案例可无损压缩封装到 JSON，必须保留原文件 hash、选择依据和解码方式，不能代替全量审计归档。
- **运行性质必须如实。** 以对应 schema、登记和消费回执区分工程检查、S5 validation 与 S6 test；S5 结果可触发其已登记 stop rule，不能称为 S6 test 结果。历史 schema 的 `formal_run` 字段不能代替这些判断。
- **`causal_complete=false` 的报告不能用来支持"减少长期记忆污染"的主张**——那需要跑满 20-step causal self-rollout，单步准确率不是替代品。

## 覆盖关系与保留边界

“包含前一步报告”与“包含前一步全部产物”不同。白话说，输入是各阶段导出及其路径/hash，输出是可以核验的依赖关系；例如最终报告记录权重 SHA 并不包含权重文件，不能用它恢复模型。

- D-054 `corrected_refit` 的 `reports` 完整包含 `corrected_budget` 的报告内容，后者包含 `corrected_checks`；但 D-055 配置分别锁定这三个文件的精确路径和 SHA。原文件继续保留以支持历史核验；不能直接换成压缩 JSON、删除内部字段或删掉前两份。
- D-055 `s5_confirmation` 包含各模型逐例指标、统计量及执行分片路径/hash；不包含全量 `execution.jsonl.gz`、训练权重或 validation 原始审计。`s5_data` 独立保留数据 manifest/健康验收；它也不包含实际 arrays 和全量审计。
- 服务器的 `complete.json` 对整个完成单元的文件清单和字节 hash 作绑定。只删除单元里的一个“重复” result/日志也可能让核验失败。需要节省服务器磁盘时，按完整单元归档到另一存储位置并验证内容 hash、解压及路径恢复方案，再决定是否移除服务器副本；不能只剩摘要。
- 旧实现结果、失败现场、原始轨迹和 provenance 是历史证据。未被最新报告引用不是删除依据；选出的八条案例也不能取代全部 S5 轨迹。
- 新阶段导出应使用“本阶段独有数据 + 上游路径/hash”的结构，避免递归嵌套上游正文。这里是后续格式约束，不把已冻结的旧导出冒充已经迁移。若将来迁移历史存储，必须保留原字节可恢复性与依赖解析，另作明确迁移，不修改科学结果。

服务器只读目录盘点入口为 `python ops/inventory_m1_storage.py`，输出 `results/m1_storage_inventory.json`。它从报告确定实际产物根目录，列出大小和引用，不读取大文件内容、不重跑计算、不删除任何文件；盘点结果本身不是删除清单。
