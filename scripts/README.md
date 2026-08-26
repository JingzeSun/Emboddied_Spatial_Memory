# Scripts

## 当前汇报脚本

动态记忆 prior-work PPT 保留一个入口、一个构建器和一个现行内容文件：

```text
scripts/
├── run_dynamic_memory_prior_work_ppt.ps1
├── build_dynamic_memory_prior_work_ppt.ps1
└── dynamic_memory_prior_work_ppt_content.json
```

内容已更新为 D-008 accepted 的论文方向；旧 JSON 位于 `docs/archive/pre_d008/presentation/`。

运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_dynamic_memory_prior_work_ppt.ps1
```

`notes.txt` 是导师建议的 source artifact，不得覆盖或删除。

## 实施脚本顺序

```text
scripts/
├── validate_contracts.*
├── run_oracle_fixtures.*
├── prepare_revision_data.*
├── validate_episode.*
├── map_oracle_delta.*
├── run_baseline.*
├── run_experiment.*
└── aggregate_metrics.*
```

每个脚本支持 `--help`、显式 config、非零失败退出码；数据写入脚本支持 dry-run。禁止写死本机绝对数据路径。
