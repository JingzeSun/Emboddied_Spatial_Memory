# Scripts

## 当前汇报脚本

当前研究设想汇报 PPT 保留一个入口、一个构建器和一个现行内容文件。脚本名沿用早期 prior-work 命名以避免新增第二套入口。v0.3 只聚焦两部分：精简后的同行评审文献基础，以及完整的方法定义、真实 WBS 和实验覆盖审计；具体场景与训练课程暂不展开。

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

默认生成 `prototype/dynamic_spatial_revision_report_v0_3.pptx`。v0.1 作为旧版汇报留存；已删除的 v0.2 不恢复。PPTX 是本地生成产物并由 `.gitignore` 忽略；可复现源是 JSON 与 PowerShell 构建器。

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
