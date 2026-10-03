# VSMT-lean: Versioned Entity-Lifecycle Memory Transactions（精简版）

> **English summary.** VSMT-lean studies how an embodied agent should *revise* an object-level memory while it revisits a house with RGB-D observations. Every frame, one joint assignment over the current anonymous fragments and the recalled memory entities yields a legal program of five atomic operations — **NOOP, BIND, BIRTH, RETRACT, REACTIVATE** — which is executed on an immutable previous version and committed as a new, traceable version. RETRACT only closes a version and REACTIVATE restores the same identity, so revisions are reversible. REPLACE is a composite (RETRACT + BIRTH). **MERGE exists only as a deterministic de-duplication rule shared identically by all compared methods; it is not a learned operation. SPLIT and RELINK, place/topology revision and relation edges are out of scope for the first paper.** The model is a frozen public frontend (simulator instance segmentation exposing mask geometry only for the main table, SAM 2.1 as a robustness appendix; RGB-D geometry; frozen DINOv2 descriptors with a shared ReID projection), three small MLP cost heads (54,207 parameters in total) and one rectangular Hungarian assignment per frame, trained with hindsight labels from private instance ground truth under a candidate-before-teacher information boundary. Status: contracts, data generation, frontend caches, runner, teacher and evaluator are implemented and server-tested; the development table is being run; **no validation or test result exists yet, so no performance claim is made.**

当前第一篇论文唯一主题是 **VSMT-lean（实体生命周期版本化事务，D-224，2026-09-19 批准）**：机器人持续接收 RGB-D 观测并重访时，对象级记忆里的每个实体应当保持、绑定新证据、新建、撤回还是恢复。每帧由一次帧级联合分配给出一个合法程序，在同一不可变旧版本上执行并提交为可追溯的新版本。

白话：它解决"原来那把椅子现在看不见，是被挡住、走出视野、检测漏了，还是真的被搬走"的判断。输入是截至当前帧的匿名色块（fragment）、公开几何、自由空间与可见体积，以及系统自己此前预测的实体记忆；输出是本帧一个合法程序和新记忆版本。例如杯子原位置连续被可靠自由空间覆盖、另一张桌面出现高相似色块，程序应把旧杯子 REACTIVATE 到新位置，而不是删旧建新。它不等于普通对象跟踪的别名，不训练视觉前端，也不把执行器、DINOv2 或五个操作名字单独当作创新。

## 操作词表（首篇）

| 操作 | 含义 | 首篇地位 |
|---|---|---|
| NOOP | 实体本帧不变 | 学习决定 |
| BIND | 把本帧色块作为新证据绑到已有实体 | 学习决定 |
| BIRTH | 为色块新建实体 | 学习决定 |
| RETRACT | 关闭实体的当前版本（不物理删除历史） | 学习决定 |
| REACTIVATE | 恢复已撤回或休眠实体的同一身份 | 学习决定 |
| REPLACE | RETRACT＋BIRTH 的复合程序 | 不是独立原子 |
| MERGE | 五个方法逐字节相同执行的确定性去重（余弦、质心距离、框重叠同时满足才合并） | 共享规则，不是学习操作，不进入方法差异 |
| SPLIT、RELINK、地点/拓扑修订、关系边 | — | **不进入首篇** |

休眠（dormant）是共享的确定性规则：连续应可见却没匹配达到登记次数的实体转为 dormant，档案不删。

## 模型与前端

- **冻结公开前端（裁决 72，2026-09-25）**：主表的色块来自模拟器实例分割，只暴露 mask 几何，不暴露标签、对象 ID、位姿或真值盒；跨帧是不是同一实体仍由方法判断。SAM 2.1 自动分割前端作为鲁棒性附录。两种前端共用同一 DINOv2 描述子（经五个方法共享的 ReID 线性投影）、同一深度几何、自由空间与可见体积。
- **学习部分**：三个 MLP 代价头（关联、新建、存在，合计 54,207 参数）加每帧一次矩形匈牙利分配。它不是 VLM，也不是图网络。
- **监督与信息边界**：召回集合与特征矩阵在任何私有文件打开之前封存；teacher 只用 t 时刻私有实例真值给已封存的候选打标签，不插入、删除或重排候选。错误分成 recall miss（正确实体没被召回）、teacher error（标签含糊）、amortization error（标签明确而学生选错）三类，分开记账。

## 对照、消融与指标

- **主比较**：VSMT-lean、TAF、ELU-P、RAC、LOW。四个对照是按公开论文机制在同一接口上独立实现的适配器，不是官方复现。
- **消融**：NoVersion、HandCost、HeuristicLabel、AssocOnly。其中 AssocOnly 使用同一学习关联头，但词表只剩 BIND 与 BIRTH，是核心贡献唯一的因果反事实，主表必须并列报告。LLM-op 是只在 validation 上跑的附录臂。
- **数据**：ProcTHOR-10K 多 house 覆盖式重访，加不可观测窗口内的物体移走、新增与搬动干预。划分已冻结：validation 50 栋、test 100 栋，训练规模在 S3-01 登记。
- **指标**：
  - 节点 P/R/F1 的主列是质心 ≤ δ_moved（0.5 m）的最大权匹配，也是选参指标；IoU 0.3 为次级列，与 Dyn-THOR 是同一匹配机制、不同重叠判定。
  - Missing 残留率、身份连续率是主门指标。
  - 另报假撤回率、恢复延迟、contamination AUC、规模与成本。
  - test 只跑一次。

## 当前状态（2026-09-25）

| 已实现并通过服务器测试 | 进行中 | 计划中 |
|---|---|---|
| S0 五份机器合同；S1 数据生成（开发用 50 栋，39 栋成功）、SAM2 与实例分割两份前端 cache、前端诊断与 ReID 投影；S2 runner、teacher、评价器与开发表编排 | S2-05 开发表：实例分割 cache 上的校准趟 | ELU-P 拟合、两轮 DAgger 训练、开发表；S3 正式数据、训练、validation 选参与一次性 test；论文 |

尚无 validation 或 test 结果，**不作任何性能主张**。完整进度与失败记录见 EXECUTE。

## 分支说明

GitHub 默认分支 `main` 可能落后，当前工作推送在 `s1-02a-runner` 分支。旧 CPMT、空间世界模型、地点双层记忆、统一四类图、八原子枚举与结构估计器的全部文档、代码说明与证据链保留在分支 `archive/pre-d224-unified-graph`（HEAD e1c19f6）；那里的八原子方案（含 SPLIT、RELINK、MERGE 学习）已被 D-224 取代。旧源码文件仍在本分支树中，只作历史与复用来源，不进入任何当前入口。

## 阅读入口

| 你要看什么 | 唯一位置 |
|---|---|
| 下一步、阶段计划和代码审查节点 | [docs/PLAN.md](docs/PLAN.md) |
| 方法、模型、对照、消融与指标 | [docs/METHOD.md](docs/METHOD.md) |
| 数据来源、划分、干预、字段与泄漏检查 | [docs/DATA.md](docs/DATA.md) |
| 已发生的实验、失败、结果与主张状态 | [EXECUTE.md](EXECUTE.md) |
| 方法、预算与工作规则的变更理由 | [docs/DECISIONS.md](docs/DECISIONS.md) |

新对话先读 [AGENTS.md](AGENTS.md)、PLAN 的当前指针，再读 EXECUTE 看板和最新 LOG。不再另建导航页、词典、确认表、周报模板或平行计划。

## 怎样复现 S2-06（SAM 2.1 开发表，裁决 100-6）

白话：S2-06 回答“S2-R 在实例分割前端上看到的模式（相对同配方 AssocOnly，陈旧实体大幅减少、身份连续率更高、节点 F1 小幅下降），换成 SAM 2.1 分割、所有可训练与可拟合的部分都在 SAM2 上按冻结规则重来以后，还在不在”。输入是 SAM2 开发 cache、SAM2 ReID 头、同一几何重载与同一份代码；输出是 SAM2 七臂开发表与按事先写死的规则给出的读数，并排放着实例分割的同一读数。例如 SAM2 上 Missing 残留率 5/5 个种子更低、节点 F1 分不出，就归“开发集上显示收益”。它不是 test，不是跨前端迁移检验（头在 SAM2 上重训），也不用来改方法。

**一条命令**（服务器，在审过的提交上新建干净的 detached worktree；不需要 GPU）：

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s2-06-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s2-06-<commit>
nohup bash ops/vsmt/s2_06_sam2.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s2-06-<commit>.log 2>&1 &
bash ops/vsmt/s2_06_sam2.sh status
```

再跑一次 `all` 就从停下的地方续跑：完成的阶段保留；阶段完成之后若代码有改动（只有登记 SAM2 拟合量与文档的改动例外），该阶段拒绝续用。各阶段、读写与停点写在 [`ops/vsmt/s2_06_sam2.sh`](ops/vsmt/s2_06_sam2.sh) 开头。

| 输入（`AUTODL=/root/autodl-tmp`） | 默认路径 | 运行前核对（check 阶段） |
|---|---|---|
| SAM2 开发 cache | `$AUTODL/vsmt_caches/lean-s1-03-154776d`（39 条 episode，44,097 帧） | 每条封印的 mask 来源是 sam2 |
| 实例分割开发 cache | `$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05` | 同一批 39 条，来源是实例分割 |
| 几何重载、S1-02 episode | `$AUTODL/vsmt_private/lean-s1-04-geometry-154776d`、`$AUTODL/vsmt_outputs/lean-s1-02{a,b}-5f9aa71` | 每条都有 |
| SAM2 ReID 头 | `$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json` | 摘要 `f6fc67e5…`（S0-03 按来源钉住） |
| 实例分割 ReID 头 | `$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json` | 摘要 `5cea91cf…` |
| 实例分割分组头（补 NoVersion 用） | `$AUTODL/vsmt_private/ruling96-7c76970/training/round1/VSMT-lean/A{7,19,31,43,59}/weights_grouped.json` | 摘要等于 `ops/vsmt/ruling97_freeze.json` |
| 并排读的实例分割读数 | `results/vsmt_lean_ruling96_*_7c76970.json`、`results/vsmt_lean_ruling95_*_d835cd3.json`、`results/vsmt_lean_s2_05_calibration_oracle_850c533.json` | 摘要等于已提交判读登记的输入 |

| 阶段 | 做什么 | 预计耗时（粗估，以 pilot 实测为准） |
|---|---|---|
| check | 全量测试；全部输入写进运行清单 | 约 10 分钟 |
| pilot | 最大一条 SAM2 episode：校准作业（保留为校准趟的一部分）与一条只计时的 TAF 审计 | 1.5～2.5 小时 |
| calibration → grid-review → elu-p-fit | 裁决 75 的校准趟；裁决 100-2 第 2 步的网格复核（按裁决 101 (1)(a) 相对实例分割判定，出界即停）；ELU-P 拟合（对全部开发 episode 求和，裁决 101 (2)(a)；首跑时停下等登记提交） | 1.5～2.5 小时 |
| round0 → train0 → round1 → train1 | 第 0 轮 ELU-P 记录；两个学习臂种子 7；各自第 1 轮记录；两臂各 5 个种子（VSMT-lean 分组选点） | 5～7 小时 |
| audits → instance-noversion | SAM2 上 19 组 × 39 条审计；实例分割上补 NoVersion 5 × 39 条（先核对今天的代码能逐项复现 7c76970 的一条审计） | 7～10 小时 |
| merge → reading → verify | 合并、按裁决 100-3 判读、确定性探针与全部摘要核对、写最终运行清单 | 约 30 分钟 |

**停点**：网格复核出界时驱动写 `stopped` 标记并停下，等用户另提按 `mask_source` 分存网格的裁决——裁决 101 (1)(a)：只有 SAM2 的判定点落在网格外、而且与实例分割的点不在同一侧才算出界，同在网格外同一侧的项列给 S3-01、不停；首跑到 elu-p-fit 时写 `hold` 标记——SAM2 的三个拟合量要先就地登记进 S0-05（裁决 68 (10) 预授权，一个提交），在那个提交上再跑 `all`，该阶段核对重拟合结果与登记值逐位相等后继续。以后任何人在最终提交上跑 `all` 都不会再停在这里。

**输出**：`$AUTODL/vsmt_outputs/exports/vsmt_lean_s2_06_*_<tag>.json`（tag 是第一次 check 时的提交），拉回 `results/` 提交：输入核对、pilot、校准、网格复核、拟合、各趟导出、12 份训练回执（含逐 epoch 分项损失）、24 份合并审计、判读、运行清单与 verify 报告。表里每个数字都由 [`ops/vsmt/s2_06_reading.py`](ops/vsmt/s2_06_reading.py) 从合并审计算出，判读会先从已提交的导出重算实例分割那份并与已提交判读逐项核对。权重按工作区规则不进 Git，留在服务器 `$RUN_ROOT/training/`，摘要在运行清单里。

**怎样核对复现**：同一提交、同一 `TRAIN_THREADS`（默认 4）重训的权重逐位相同（裁决 96 已验证），审计是确定性的；verify 阶段重跑一条审计比对、核对每份权重与回执的摘要，`REPRO_TRAINING=1` 时另重训第 0 轮 AssocOnly 比对摘要。别人复现后，把自己的运行清单与 `results/vsmt_lean_s2_06_manifest_<tag>.json` 里的权重摘要和导出摘要逐项比较即可。

## 怎样复现 S3-02（正式数据，裁决 103）

白话：S3-02 回答“正式实验的数据从哪来”。输入是 ProcTHOR-10K 0.1.2 源文件、S1 用过的私有盐、冻结的前端资产与已审代码；它按已提交的三份清单（train 300、validation 50、test 100，裁决 102-8）生成原始 episode，补几何重载，建实例分割与 SAM 2.1 两套 cache，输出三个划分各自的根与回执。test 写进单独的根并封存：S3-05 之前，任何读数据的入口（训练、选参、审计）遇到 test 根都会拒绝。例如 train 生成完若执行成功的搬动不足 120 次，驱动停下等规模裁决，而不是放宽规则或补样本。它不训练、不评价，test 只算摘要与计数。

**一条命令**（服务器，4 卡；数据盘可用空间不少于 check 段推算的约 340 GB；在审过的提交上新建干净的 detached worktree）：

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s3-02-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s3-02-<commit>
nohup bash ops/vsmt/s3_02_data.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-02-<commit>.log 2>&1 &
bash ops/vsmt/s3_02_data.sh status
```

再跑一次 `all` 就从停下的地方续跑：完成的阶段保留；阶段完成之后若代码有改动（只有登记生成器提交的三个文件与文档例外），该阶段拒绝续用。各阶段、读写与停点写在 [`ops/vsmt/s3_02_data.sh`](ops/vsmt/s3_02_data.sh) 开头。

| 输入（`AUTODL=/root/autodl-tmp`） | 默认路径 | 运行前核对（check 阶段） |
|---|---|---|
| ProcTHOR-10K 0.1.2 源文件 | `$AUTODL/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz` | 摘要与字节数等于 S1-01 登记值（`d64450ec…`，52,316,238 字节） |
| 私有盐（裁决 37） | `$AUTODL/vsmt_private/null_window_salt.txt` | 在仓库外，摘要等于 S1 各次生成用过的那份（`8f4eae85…`） |
| 前端资产 | `$AUTODL/vsmt_private/s103_assets.json` | SAM 2.1 与 DINOv2 按 S1-03 合同与 S1-01 登记逐字节核对 |
| 两份 ReID 头（S3-03 起使用） | `$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json`、`$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json` | 摘要等于 S0-03 按来源钉住的值 |
| 模拟器解释器 | `$AUTODL/vsmt-envs/simulator-py39/bin/python` | 能导入 ai2thor |

| 阶段 | 做什么 | 预计耗时（粗估，以实测为准） |
|---|---|---|
| check | 全量测试；全部输入、显卡、cgroup 配额与内存、数据盘可用空间写进运行清单（磁盘按全部产物推算、减去本次已写入，所以 hold 之后在登记提交上重跑时只要求剩下的部分） | 约 15 分钟 |
| measure | train 前 4 个 house、4 路并发，实测单 worker 占用（measure 根，不算 S3 数据） | 约 25 分钟 |
| generate | 用实测字节数重算磁盘；450 个 house 一个进程池（S1-01 规则推导 worker 数，模拟器并发上限按确认集的 16 路外推）；裁决 36 检查 | 约 8～9 小时 |
| hold | 首跑停在这里：生成器提交要登记进 S1-03 位姿登记表（裁决 103-3 预授权的登记提交），在那个提交上再跑 `all` | — |
| geometry | 三个划分的几何重载，8 个模拟器 worker | 约 15 分钟 |
| instance-cache | 实例分割 cache，每个 worker 2 线程，按 cgroup 配额与内存定 worker 数，所有卡，大 episode 先派发 | 约 2 小时 |
| sam2-measure | 一张卡上 1～4 个 worker 试跑，取吞吐最高的每卡 worker 数，打印总时长估计后继续；某一档里有 episode 因数据本身失败（如色块超上限）照样算数并列出，因显存不足等其他原因失败的档不算，全都不算才停 | 约 15 分钟 |
| sam2-cache | SAM 2.1 cache，每卡最佳 worker 数 × 卡数 | 约 20～40 小时 |
| export → verify | 导出（train、validation 逐 house；test 只有计数）、封存 test、核对各划分一致与封印、写最终运行清单 | 约 30 分钟 |

**停点**：train 搬动不足 120 次或源先重访不足 60 次时 generate 写 `stopped` 并停下，等规模裁决（裁决 36）；首跑到 hold 时写 `hold` 并停下，生成器提交登记后续跑；若生成器提交的 camera_pose 编码与已登记的不同，hold 写 `stopped`，这种提交不能这样登记。cache 某条 episode 若因数据本身的原因失败（如 SAM2 色块超上限），照记、不算该段失败；若因别的原因失败，该段失败并停下等检查，不重跑、不替换。

**输出**：原始 episode `$AUTODL/vsmt_outputs/s3-02-<tag>/{measure,train,validation,test}`，几何 `$AUTODL/vsmt_private/s3-02-geometry-<tag>/<划分>`，cache `$AUTODL/vsmt_caches/s3-02-{instance,sam2}-<tag>/<划分>`（tag 是第一次 check 时的提交）；导出 `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_02_*_<tag>.json` 拉回 `results/` 提交：输入核对、测量、生成计划、train 与 validation 的逐 house 报告、几何与两套 cache 的报告、test 的计数汇总与封印、worker 依据、裁决 36 检查、登记记录、SAM2 试跑、运行清单与 verify。

**正式运行之前的测速**（`ops/vsmt/s3_02_bench.sh`，一张 RTX 5090，只读开发集，不是正式阶段）：在干净的 detached worktree 上运行 `nohup bash ops/vsmt/s3_02_bench.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-02-bench-<commit>.log 2>&1 &`，全部输出写在 `/root/autodl-tmp/vsmt_bench/<tag>`，导出为 `vsmt_lean_s3_02_bench_*_<tag>.json`。七段：check（全量测试、显卡与 torch、输入）→ compat（生成器在这台机器上跑 4 个 house 的占用测量）→ sam2-scaling（每卡 1～4 个 SAM2 worker 做同一批工作）→ caches（两套 cache 依次与同时跑）→ audit-profile（闭环审计的 cProfile 剖析）→ train-device（训练记录的内存构成与 CPU／GPU 各一个 epoch）→ collect。粗估共约 3 小时，写盘约 6 GB。

**怎样核对复现**：同一提交下，生成器对同一个 house 的输出是确定的——verify 把测量用的 4 个 house 与 train 里同名的 4 个逐字节比较并记进运行清单；cache 对同一条 episode 预期是确定的（同型号显卡；这一点没有逐字节验证过）。别人复现后，把自己的运行清单与 `results/vsmt_lean_s3_02_manifest_<tag>.json` 逐项比较；test 的封印摘要在 `results/vsmt_lean_s3_02_test_seal_<tag>.json`，S3-05 读 test 之前先核对它。

## 怎样复现 S3-03（训练与选参读数，裁决 104）

白话：S3-03 回答“正式实验里每个臂拿什么权重、每个配置在 validation 上读数多少”。输入是 S3-02 的 train／validation 数据（test 根封存，只读它们的封存标记文件）、冻结的方法（裁决 99-1 的配方）、网格与选参规则；输出是两套前端各自的 ELU-P 拟合量、第 0／1 轮轨迹与 HeuristicLabel 标签、36 次训练（每次都记逐 epoch 的 train／validation 分项损失）、208 组 × 约 42 条 validation 闭环审计（只算指标），以及给 S3-04 的选参读数。整趟是一个依赖驱动的作业池：作业的输入一齐就派发，关键路径（拟合、轨迹、训练）优先，规则臂审计用剩下的核。例如 VSMT-lean 第 0 轮训练一结束，它的第 1 轮轨迹就开始，不等另外两个臂。它不选配置（S3-04 做）、不读 test、不改方法与网格。

**一条命令**（服务器，只用 CPU；S3-02 已完成、它的导出在 `$AUTODL/vsmt_outputs/exports`；在审过的提交上新建干净的 detached worktree）：

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s3-03-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s3-03-<commit>
nohup bash ops/vsmt/s3_03_train_select.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-03-<commit>.log 2>&1 &
bash ops/vsmt/s3_03_train_select.sh status
```

再跑一次 `all` 就从停下的地方续跑：完成的作业保留（之后若代码有改动，只有 ELU-P 拟合值的登记文件与文档例外，否则拒绝，除非 `ACCEPT_CODE_CHANGE=1` 并记进作业状态）；上次中断时还在跑的作业，残留输出先挪到 `$RUN_ROOT/interrupted/` 留存再重跑；审计保留已完成的配置；失败或门未过的作业不会自己重跑，修好或裁决后用 `RETRY_FAILED=1`（残留输出先挪到 `$RUN_ROOT/failed/`）。作业图与各子命令写在 [`ops/vsmt/s3_03_manifest.py`](ops/vsmt/s3_03_manifest.py)，派发规则在 [`ops/vsmt/s3_03_jobs.py`](ops/vsmt/s3_03_jobs.py)。

| 输入（`AUTODL=/root/autodl-tmp`） | 默认路径 | 运行前核对（check） |
|---|---|---|
| S3-02 的数据 | 原始 episode `$AUTODL/vsmt_outputs/s3-02-3f6ef1d/{train,validation}`、几何 `$AUTODL/vsmt_private/s3-02-geometry-3f6ef1d/<划分>`、cache `$AUTODL/vsmt_caches/s3-02-{instance,sam2}-3f6ef1d/<划分>` | S3-02 运行清单无问题；它记的每个导出文件摘要相符；逐 house 的原始回执、逐 episode 的 cache 封印与几何回执都等于导出所记；计数等于运行清单 |
| S3-02 的 test 封印 | `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_02_test_seal_3f6ef1d.json` | 四个 test 根各有 `TEST_SEALED.json`，状态 sealed、摘要等于这份封印（只读这四个标记文件） |
| 两份 ReID 头 | `$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json`（SAM2）、`$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json`（实例分割） | 摘要等于 S0-03 按来源钉住的值 |
| 可选：已有的校准趟（S3 预拟合） | `ADOPT_CALIBRATION_INSTANCE=<pass root>` | 每条 episode 的回执、配置与来源相符，并在本提交上重跑最小一条、两份产物逐字节相同才采用 |

| 部分 | 做什么 |
|---|---|
| check | 全量测试；上表的核对；每套前端可用的 train／validation episode（清单内、原始、几何表、cache 都在）写进 `$RUN_ROOT/inputs.json` |
| 校准趟 → 拟合 | TAF θ_a 0.7 无门，带直方图与 ELU-P 计数；S3 train 全部可用 episode 上拟合三个量，写成运行内的值（裁决 104-1 1b）；拟合被拒（退化）即停 |
| 第 0 轮 → 门 | ELU-P 在 rollout_config 加本前端拟合量下的轨迹，同时写 teacher 记录与 HeuristicLabel 记录；门：HeuristicLabel 的决定函数在 ELU-P 自己的轨迹上与臂的决定逐行相同（G4）、整条 split 的 nuisance 探针最大优势 ≤ 0.05；不过即停在训练之前 |
| 训练 | 第 0 轮三个臂（种子 7，总验证损失选点）→ 第 1 轮轨迹（VSMT-lean 与 HeuristicLabel τ_r 0.5，AssocOnly 无配置）→ 第 1 轮每臂 5 个种子（VSMT-lean 与 HeuristicLabel 分组选点）；前 240 个 house 训练、后 60 个选点（104-1 1a）；线程数在第 0 轮期间按 20＋5 个 house 实测 1～4 线程选定，整趟固定；崩溃或内存不足的训练同输入同种子自动重跑一次；发散记为结果，不换种子 |
| 审计 | validation 上 208 组：规则臂 TAF 12、ELU-P 12、RAC 12、LOW 5、HandCost 12（ELU-P 等拟合），学习臂 VSMT-lean、NoVersion、HeuristicLabel 各 10 档 τ_r × 5 种子，AssocOnly × 5 种子；每个作业是一条 episode 上同一臂同一组头的全部配置（cache 只核验一次），只算指标 |
| 探针 | 审计等价（一条 train episode 上完整审计与只算指标逐项相同）、训练等价（列表式与流式入口逐位相同）与正式作业同时跑，不过即停；最后在一条 validation episode 上重跑一个审计核对确定性 |
| 读数 | 合并完整性；每套前端的选参读数（逐指标排除清单、house 均值、种子均值、缺的种子注明、AssocOnly 参照值）；只报告：89-3 ① 状态覆盖、两套校准趟的网格位置（101 (1)(a) 读法）、标签构成 |
| export → verify | 导出 `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_03_*_<tag>.json`；verify 要求所有作业结束、所有门通过、S0-05 登记的拟合值与本次运行的值逐位相等 |

**拟合值的登记（裁决 104-1 1b，不停机）**：运行用的是运行内的拟合值；登记提交把 S0-05 里两套开发集拟合值就地换成本次的值（旧值进台账 `SUPERSEDED_VALUES`），只改 `ops/vsmt/s3_03_manifest.py` 里 `REGISTRATION_FILES` 列出的文件，运行期间在本地做、运行结束后再拉到服务器（运行中的 checkout 不 pull）。拉之前 verify 会报 `elu_p_values_not_registered` 并以 3 退出——这是预期，不重跑任何作业；拉到登记提交后再跑一次 `all`：完成的作业全部保留，verify 通过。

**停点**：check 不过；拟合被拒或值不有限；第 0 轮门（G4 有不一致，或 nuisance 优势超过 0.05——先只读拆解再提裁决，不放宽线）；审计等价、训练等价或确定性探针不同；任何作业的工程失败（训练除外：先自动重跑一次）。停下时在跑的作业会跑完，新作业不再派发。

**输出**：运行根 `$AUTODL/vsmt_private/s3-03-run`（`inputs.json`、`workers.json`、`pool.json`、`jobs/` 逐作业状态与实测内存，每套前端的 `calibration/`、`fit/`、`round0/`、`round1/`、`training/`、`audit/`、`merged/`、`gates/`、`selection_readings.json`、`coverage.json`）；日志 `$AUTODL/vsmt_outputs/run_logs/s3-03-<tag>/`（每个作业一个）；导出拉回 `results/` 提交：输入核对、worker 依据、线程实测与选择、两套前端的拟合与校准、门与探针、训练回执摘要（含逐 epoch 分项损失）、选参读数、状态覆盖、网格位置、作业汇总、运行清单与 verify。

**怎样核对复现**：同一提交与同一 TRAIN_THREADS 下训练权重逐位可复现（裁决 96），审计是确定的（确定性探针）；别人复现后把自己的运行清单与 `results/vsmt_lean_s3_03_manifest_<tag>.json` 逐项比较，选参读数逐项比较 `vsmt_lean_s3_03_readings_<front>_<tag>.json`。

## 实现与证据

| 目录 | 职责 |
|---|---|
| `src/vsmt/lean_*.py` | D-224 纯核心：实体记忆与执行器、特征/召回/分配、前端 cache、对照臂、代价头、runner、teacher 与评价、开发表 |
| `ops/vsmt/lean_*.py` | 服务器入口：S1-02 数据生成、S1-03 cache、S1-04 诊断、S2-04 单 episode 评价、S2-05 开发表编排与导出 |
| `configs/vsmt/lean_*.json`、`tests/` | 版本化机器合同（规则摘要由跨合同测试钉住）与测试 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物（不进 Git）、可复算导出报告 |
| `src/cpmt/`、`src/spatial_world_model/`、`experiments/`、`schemas/`、`literature/`、`docs/source/`、`prototype/` 及 `src/vsmt/` 里的非 lean 模块 | 历史实现、原始资料与文献，保留不删 |
