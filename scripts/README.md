# Scripts

## 当前汇报脚本

当前研究设想汇报 PPT 保留一个入口、一个构建器和一个现行内容文件。脚本名沿用早期 prior-work 命名以避免新增第二套入口。v1.0 已切换到 D-017 的世界模型主线：同行评审文献基础、动作条件预测与候选信念循环、主动取证、有限修订，以及首轮 oracle 机制验证；不包含正式训练和实验结果。

```text
scripts/
├── run_dynamic_memory_prior_work_ppt.ps1
├── build_dynamic_memory_prior_work_ppt.ps1
├── dynamic_world_model_ppt_content.json       # 当前 v1.0
├── dynamic_memory_prior_work_ppt_content.json # v0.7 复现源
├── run_insert_application_scene_slide.ps1     # 从用户手改 v1.0 生成 v1.1
├── insert_application_scene_slide.ps1         # 插入应用场景图并顺延页码
├── run_replace_core_innovation_slide.ps1      # 从 v1.1 生成核心聚焦 v1.2
└── replace_core_innovation_slide.ps1          # 替换第 2 页，不覆盖 v1.1
```

当前内容以 D-017、D-018 和 D-019 为准；旧 JSON 仅用于复现冲突修订主线的 v0.7，不再代表当前论文方向。

运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_dynamic_memory_prior_work_ppt.ps1
```

默认生成 `prototype/dynamic_spatial_revision_report_v1_0.pptx`。v1.0 保持用户手改稿的 15 页节奏和人话表达，把旧版“动态冲突修订”降为世界模型中的一个子模块，并加入重复走廊、候选事实、回环/漂移歧义、主动观察和 E0–E6。v0.1–v0.7 作为旧版汇报留存，已删除的 v0.2 不恢复。PPTX 是本地生成产物并由 `.gitignore` 忽略；可复现源是 JSON 与 PowerShell 构建器。

若要保留用户手改 v1.0 的全部措辞，并在第 2 页插入应用场景图，运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_insert_application_scene_slide.ps1
```

默认读取 v1.0 与 `prototype/assets/world_model_application_scene_v1.png`，生成 16 页的 `prototype/dynamic_spatial_revision_report_v1_1.pptx`；不覆盖 v1.0，后续正文页码自动顺延。

若要把第 2 页从泛化应用场景改为 D-022 的单一核心创新图，运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_replace_core_innovation_slide.ps1
```

默认读取 v1.1，生成 `prototype/dynamic_spatial_revision_report_v1_2.pptx`，不覆盖 v1.1。第 2 页明确画出：旧世界 + 新证据 → evidence path / typed edit / affected-control-stop / versioned apply → semantic、topology、valid time 三轴 posterior；房间布局、动作预测、区域绑定、主动补证和 Top-K 均标为前置或下游。

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
