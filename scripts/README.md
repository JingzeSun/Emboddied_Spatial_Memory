# Scripts

现有 dynamic_memory_prior_work PPT 脚本是历史 provenance，内容对应 D-017 之前的方法，保留但不再作为活动合同。不得仅改标题就把旧图当 CPMT。

## 单房间视觉试点入口

`run_visual_pilot.py` 在 Linux/WSL2 中启动 AI2-THOR，先采集换视角重见、首次发现和移动后重访三类画面，再调用项目 executor 从同一 base 真实执行候选。输入是公开 iTHOR 场景名、分辨率、Linux 盘上的 Unity build 缓存和输出目录；输出包含 `frames/`、每例严格分离的 `online.json`/`audit.json`、逐候选六项能量、教师概率、失败栈和 run manifest。一个具体例子是：旧冰箱视角不再出现已搬走的小物体，而新视角仍出现，离线审计据此比较 `RELINK` 与 `BIRTH`。它只是 M1-development 的数据/几何/教师接口审计，不是正式 M1、完整视觉闭环或 PNO 训练。

为减少 WSL 从 NTFS 直接执行大文件的风险，`--build-cache` 默认是 Linux 文件系统中的 `~/.cache/cpmt-ai2thor`，脚本会拒绝 `/mnt/...` 缓存。典型命令：

~~~bash
.venv-wsl/bin/python scripts/run_visual_pilot.py --dry-run
.venv-wsl/bin/python scripts/run_visual_pilot.py --smoke-only --width 320 --height 240
.venv-wsl/bin/python scripts/run_visual_pilot.py --scene FloorPlan1
~~~

白话说，`--dry-run` 只核对依赖和显卡，不启动 Unity；`--smoke-only` 只保存一帧来查渲染兼容；不带二者才运行三案例。三者都不代表方法有效，只有最后一种会产生候选世界/教师审计，而且它仍不能替代后续冻结的正式对照实验。

## CPMT 计划入口

~~~text
scripts/
  validate_contracts.*
  audit_split_leakage.*
  run_executor_fixtures.*
  generate_paired_worlds.*
  export_online_view.*
  run_hard_condition.*
  run_representation_pilot.*
  run_training.*
  run_self_rollout.*
  aggregate_metrics.*
  build_weekly_packet.*
~~~

每个入口必须支持 help、显式 config、dry-run（写数据时）、非零失败码和 run_manifest。禁止写死机器绝对路径。

run_ctl_dev.py 用于 D-027 授权的 train/validation 开发训练，支持 --help、--config、--dry-run、独立输出目录与失败 manifest。白话：在小世界里联调学习过程，不是正式论文评测。规格见 [开发合同](../experiments/counterfactual_transaction_learning/DEVELOPMENT.md)，运行记录只写 [EXECUTE.md](../EXECUTE.md)。正式 M1 须协议冻结，M2 须 M1 go。上方计划中的周报导出仅在用户要求独立报告时使用，不默认按周或对话生成文件。

`validate_m1_protocol.py` 读取正式 M1 的 pre-test lock candidate，检查六方法、paired split、future 来源、K=16、六项能量、统计门槛、test 封存和零云预算授权，并输出 canonical SHA256。例如有人把 A–E 改成五方法或允许 test 选 checkpoint，脚本应非零失败。它只验证合同自洽，不运行训练、不创建数据，也不把 candidate 自动升级为 frozen。

`generate_m1_pairs.py` 只开放 `train` 和 `validation`，把 C00–C11 语义原型扩成 paired online/audit JSONL，并保存配置/协议/源代码哈希、逐候选执行结果、教师能量和完整 failure。输入是冻结配置、split 与可选每类组数，输出写入 `outputs/m1_data/<run_id>/`；例如 `--split validation --groups-per-family 4` 生成每类四对 sibling。它没有 `test` 选项，当前 topology 多样性仍只是 fixture archetype，所以不能把 smoke 输出称作正式数据集或 coverage gate 结果。

`generate_m1_rollouts.py` 只开放 `train` 和 `validation`，生成真正按前一步 post-graph 继续的 20-decision 程序化世界链。输入是冻结配置、split 和 paired group 数，输出写入 `outputs/m1_rollout/<run_id>/`，包括逐步 online JSONL、整条 audit sequence、配置、摘要和标准 manifest；例如 `--split validation --paired-groups 4` 会生成 4 对 sibling、共 160 个有序决策。白话说，它检查“模型第 4 步改错记忆后，第 5 步是否真的拿错后的记忆继续”，并为每步使用固定、reference-blind 的 K=16 候选；若错误世界使后续 audit reference 已不合法，就记录 counterfactual failure 并保持当前错误世界，而不是偷偷重置。它不是 PNO/视觉数据，也不运行训练或 test。单条 20-step 开发诊断已通过；正式规模 paired rollout 仍未运行。

该入口现在默认使用 `--paired-groups`：每组两条 sequence 共享初始世界、资产、事件计划和 ambiguity pivot 的 online payload，但 pivot 的 audit-only reference 分别指向 primary/contrast；`--sequences` 只保留未配对的接口诊断模式。输入不变，输出额外记录 paired group、sibling 和 pivot；例如 `--paired-groups 4` 产生 8 条 sequence、160 个决策。它不表示整条分叉后的两个世界仍应逐帧 online 相同，也不等于正式规模 K=16 数据已经生成。

`audit_m1_candidates.py` 是 K=16 的训练前 coverage 专用入口。输入是当前 world、train/validation split 和 paired-group 数，输出是逐决策 reference canonical match、总体与逐 family coverage、非法 reference、去重数和 gate 状态；它不构造 future trace、不训练 A–F，也没有 test 选项。例如隐藏 reference 为 RETRACT 时，生成器只从匿名 observation query 检索当前 edge 并先枚举全部 16 个候选，审计端再独立执行 audit-only RETRACT reference 并匹配 post-world；匹配不到就明确记为 candidate miss，不能算成 CTL/scorer 错误。summary 分开写 `coverage_thresholds_met` 与 `formal_gate_eligible`：受控 validation 审计即使达到数值门槛，只要还不是 C00–C11 正式规模和独立/视觉 observation，`coverage_gate_pass` 仍为 false。具体运行结果只记录在 EXECUTE。

`run_m1_af_rollout.py` 使用 `configs/m1_af_smoke.json` 把 A–F 接到 paired continuous rollout。输入是冻结 hard config、明确标为 nonformal 的 smoke config 和 train/validation 数据，输出包括共享且随 K 自动定维的 online tensors、99 维训练期 future targets、A–E 权重、E 的额外 scorer、逐方法 teacher-forced/causal 指标、完整失败和标准 manifest。例如 A 单步选错后，runner 会从 A 自己的 post graph 构造下一个 K=16 候选集。它不访问 test、不自动调阈值，也不是五 seeds/10,000 bootstrap 的正式实验；动态 K=16 接线尚未完成运行验证。

`run_m1_trainability.py` 使用 `configs/m1_trainability_ladder.json` 做可学习性审计。输入是相同 train/validation paired 数据、全标签容量曲线和 4→10 group、60→1000 step 的受控点，输出是容量上限差、A–F 指标、candidate/teacher/amortization 误差分解、资源和完整重试记录。K=16 的非正式开发结果仅记录在 `EXECUTE.md`；旧 candidate=3 数值不能与之混报。它明确 `formal_run=false`、`test_access=false`，不是 checkpoint 选择或正式结论。

`generate_m1_trainability_shard.py`、`run_m1_trainability_point.py` 和 `run_m1_trainability_method.py` 是上述 runner 的隔离 worker：前者每次只生成一个完整 paired group，中者运行一个容量阶梯点，后者把同一 optimization point 的 A–F 各自在独立进程中训练和 causal replay；只有六个方法结果齐全且 A–E 参数量一致时才聚合。失败 attempt 原样保留，后续 attempt 不复用半成品。父 runner 可用显式 `--resume-output` 恢复中断 run，但只承认带 `complete.json` 的完整 shard/point，并要求相关科学源码与全部配置不变；跨 Windows/WSL worktree 时只额外允许可证明的 CRLF/LF 字节转换。runner 自身可以只改变恢复机制并记录前后 commit。例如 A、B 已完成而 C 进程退出时，恢复会复用 A/B 并只重试 C。它解决“偶发进程退出后不要抹掉完整结果”的问题，输入仍是同 seed、同数据和同训练预算，输出仍是一次完整 A–F point；它不等于拆开调参、跳过失败方法、替换样本或选择最佳 attempt。

## 项目内 Python 环境

`pyproject.toml` 与生成的 `uv.lock` 固定当前合同测试、CTL 开发代码和单房间视觉试点的 Python 依赖。输入是依赖声明，输出是项目内 `.venv` 和可复现的精确版本锁；例如换机器后运行 `uv sync --extra visual-pilot` 可恢复同一组包。它不固定 AI2-THOR 下载的 Unity build、场景数据或 GPU 驱动，这些仍须写入每次 run manifest，也不代表视觉方法已经验证。
