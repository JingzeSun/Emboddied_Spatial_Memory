# Scripts

## 当前可复现脚本

动态记忆 prior-work PPT 只保留一个入口、一个构建器和一个内容文件：

```text
scripts/
├── run_dynamic_memory_prior_work_ppt.ps1
├── build_dynamic_memory_prior_work_ppt.ps1
└── dynamic_memory_prior_work_ppt_content.json
```

从项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_dynamic_memory_prior_work_ppt.ps1
```

入口以 UTF-8 读取构建器，并通过 `$PSScriptRoot` 解析项目内路径，不依赖本机绝对路径。旧的 `v2/v3/v4/debug/final*` 包装器已合并并删除。

`notes.txt` 是导师建议的 source artifact，不是可执行脚本，不得覆盖或删除。

## 后续实验脚本约定

后续脚本按动作命名并保持单一职责：

```text
scripts/
├── prepare_data.*
├── validate_episode.*
├── extract_features.*
├── run_baseline.*
├── run_experiment.*
└── aggregate_metrics.*
```

每个脚本应支持 `--help`、显式配置路径、dry-run（涉及数据写入时）和非零失败退出码。禁止在脚本中写死本机绝对数据路径。
