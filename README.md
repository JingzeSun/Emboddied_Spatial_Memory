# VSMT-lean: Versioned Entity-Lifecycle Memory Transactions（精简版）

> **English summary.** VSMT-lean studies how an embodied agent should *revise* an object-level memory while it revisits a house with RGB-D observations. Every frame, one joint assignment over the current anonymous fragments and the recalled memory entities yields a legal program of five atomic operations — **NOOP, BIND, BIRTH, RETRACT, REACTIVATE** — which is executed on an immutable previous version and committed as a new, traceable version. RETRACT only closes a version and REACTIVATE restores the same identity, so revisions are reversible. REPLACE is a composite (RETRACT + BIRTH). **MERGE exists only as a deterministic de-duplication rule shared identically by all compared methods; it is not a learned operation. SPLIT and RELINK, place/topology revision and relation edges are out of scope for the first paper.** The model is a frozen public frontend (simulator instance segmentation exposing mask geometry only for the main table, SAM 2.1 as a robustness appendix; RGB-D geometry; frozen DINOv2 descriptors with a shared ReID projection), three small MLP cost heads (54,207 parameters in total) and one rectangular Hungarian assignment per frame, trained with hindsight labels from private instance ground truth under a candidate-before-teacher information boundary. Status: contracts, data generation, frontend caches, runner, teacher and evaluator are implemented and server-tested; the development table is being run; **no validation or test result exists yet, so no performance claim is made.** *(Update 2026-10-08, the sentence above is kept as history: the one test run (S3-05) is done and the claim audit (S3-06, ruling 113) fixes what may be claimed — on the simulator instance-segmentation front end the lifecycle operations leave fewer stale entities and re-attach more relocated objects than the same-recipe association-only ablation; with SAM 2.1 only the stale-entity part holds; the original gate against the strongest rule-based control is not met. See docs/METHOD.md section 2 and EXECUTE.md LOG-306/LOG-307.)*

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

## 当前状态（2026-10-08）

S0～S3-05 已完成：S3-05 在冻结回执下把 test 读了一次（LOG-306）。主门固定顺序第一步（模拟器实例分割，Missing 残留率与身份连续率）与第二步（SAM 2.1 残留率）成立，第三步（SAM 2.1 身份连续率）未通过；对最强规则臂的原主门未满足。论文能说什么、不能说什么按裁决 113 定（METHOD 第二节“S3-05 之后的主张范围”，逐句措辞见 EXECUTE LOG-307）。进行中：S3-06 只读复算（待用户审代码）、S3-07 外部验证（3RScan，实例分割列）。计划中：S3-05R 公开发布、S4 论文。下面 2026-09-25 的状态表保留作历史。

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

再跑一次 `all` 就从停下的地方续跑：完成的作业保留（之后若代码有改动，只有 ELU-P 拟合值的登记文件与文档例外，否则拒绝，除非 `ACCEPT_CODE_CHANGE=1` 并记进作业状态）；上次中断时还在跑的作业，残留输出先挪到 `$RUN_ROOT/interrupted/` 留存再重跑；审计保留已完成的配置；是否采用已有校准趟的选择写进运行根，之后每次续跑沿用（在任何校准或采用作业跑过之前可以改，之后再给不同的选择会被拒绝）；失败或门未过的作业不会自己重跑，续跑时驱动会先停在它前面，修好或裁决后用 `RETRY_FAILED=1` 才重跑（残留输出先挪到 `$RUN_ROOT/failed/`）；同一个运行根同时只能有一个驱动（文件锁 `$RUN_ROOT/.lock`）。作业图与各子命令写在 [`ops/vsmt/s3_03_manifest.py`](ops/vsmt/s3_03_manifest.py)，派发规则在 [`ops/vsmt/s3_03_jobs.py`](ops/vsmt/s3_03_jobs.py)。

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
| 训练 | 第 0 轮三个臂（种子 7，总验证损失选点）→ 第 1 轮轨迹（VSMT-lean 与 HeuristicLabel τ_r 0.5，AssocOnly 无配置）→ 第 1 轮每臂 5 个种子（VSMT-lean 与 HeuristicLabel 分组选点）；前 240 个 house 训练、后 60 个选点（104-1 1a）；线程数在第 0 轮期间按 20＋5 个 house 实测 1～4 线程选定，整趟固定；优化器走 AdamW 的多张量路径（与登记路径逐位相同：测试套件钉住，训练等价探针在真实记录上再核）；崩溃或内存不足的训练同输入同种子自动重跑一次；发散记为结果，不换种子 |
| 审计 | validation 上 208 组：规则臂 TAF 12、ELU-P 12、RAC 12、LOW 5、HandCost 12（ELU-P 等拟合），学习臂 VSMT-lean、NoVersion、HeuristicLabel 各 10 档 τ_r × 5 种子，AssocOnly × 5 种子；每个作业是一条 episode 上同一臂同一组头的至多 3 个（规则臂）或 5 个（学习臂）配置，cache 每个作业只核验一次，只算指标；作业不可抢占，所以单个作业压在约半小时以内，免得长的低优先级作业挡住关键路径 |
| 探针 | 审计等价（一条 train episode 上完整审计与只算指标逐项相同）先于全部审计，训练等价（登记的列表式路径与本次运行的流式＋多张量路径逐位相同）先于第 0 轮训练，不过即停；最后在一条 validation episode 上重跑一个审计核对确定性 |
| 读数 | 合并完整性；每套前端的选参读数（逐指标排除清单、house 均值、种子均值、缺的种子注明、AssocOnly 参照值）；只报告：89-3 ① 状态覆盖、两套校准趟的网格位置（101 (1)(a) 读法）、标签构成 |
| export → verify | 导出 `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_03_*_<tag>.json`；verify 要求所有作业结束、所有门通过、S0-05 登记的拟合值与本次运行的值逐位相等 |

**拟合值的登记（裁决 104-1 1b，不停机）**：运行用的是运行内的拟合值；登记提交把 S0-05 里两套开发集拟合值就地换成本次的值（旧值进台账 `SUPERSEDED_VALUES`），只改 `ops/vsmt/s3_03_manifest.py` 里 `REGISTRATION_FILES` 列出的文件，运行期间在本地做、运行结束后再拉到服务器（运行中的 checkout 不 pull）。拉之前 verify 会报 `elu_p_values_not_registered` 并以 3 退出——这是预期，不重跑任何作业；拉到登记提交后再跑一次 `all`：完成的作业全部保留，verify 通过。

**停点**：check 不过；拟合被拒或值不有限；第 0 轮门（G4 有不一致，或 nuisance 优势超过 0.05——先只读拆解再提裁决，不放宽线）；审计等价、训练等价或确定性探针不同；任何作业的工程失败（训练除外：先自动重跑一次）。停下时在跑的作业会跑完，新作业不再派发。

**输出**：运行根 `$AUTODL/vsmt_private/s3-03-run`（`inputs.json`、`workers.json`、`pool.json`、`jobs/` 逐作业状态与实测内存，每套前端的 `calibration/`、`fit/`、`round0/`、`round1/`、`training/`、`audit/`、`merged/`、`gates/`、`selection_readings.json`、`coverage.json`）；日志 `$AUTODL/vsmt_outputs/run_logs/s3-03-<tag>/`（每个作业一个）；导出拉回 `results/` 提交：输入核对、worker 依据、线程实测与选择、两套前端的拟合与校准、门与探针、训练回执摘要（含逐 epoch 分项损失）、选参读数、状态覆盖、网格位置、作业汇总、运行清单与 verify。

外壳的退出码：verify 通过为 0，否则是停下那一步的退出码（状态 JSON `$AUTODL/vsmt_outputs/exports/s3_03_<tag>.status.json` 写明是哪一步）。

**怎样核对复现**：同一提交与同一 TRAIN_THREADS 下训练权重逐位可复现（裁决 96），审计是确定的（确定性探针）；别人复现后把自己的运行清单与 `results/vsmt_lean_s3_03_manifest_<tag>.json` 逐项比较，选参读数逐项比较 `vsmt_lean_s3_03_readings_<front>_<tag>.json`。

## 怎样复现 S3-04（validation 后冻结，裁决 106）

白话：S3-04 回答“每套前端每个臂拿哪个配置去考 test，考 test 那天跑哪份代码、用哪些权重”。输入是 S3-03 跑完的运行根（只读）与导出；输出是一份冻结回执：每个臂的唯一配置、test 上每条 episode 要跑的 25 个运行（5 个规则臂各 1 个配置、4 个学习臂各 5 个种子）、S3-05 要算的统计、test 当天会运行的每个代码文件（`src/`、`ops/`、`configs/`）与权重文件的指纹。例如实例分割前端 VSMT-lean 的 10 个 τ_r 里，先划掉 validation Missing 残留率不低于 AssocOnly 的，再取节点 F1 最高的。它不读 test、不训练、不算主门；回执提交并推送、用户确认之后，S3-05 才解封 test（106-5）。

**前提**：S3-03 已在登记提交上收尾核验通过（`vsmt_lean_s3_03_verify_<tag>.json` 无问题）；冻结提交里已有 S3-05 的入口 `ops/vsmt/s3_05_test.sh`（106-1 (a)：冻结覆盖 S3-05 要执行的代码，入口不在就不写回执）；在 B1 上建冻结提交的干净 detached worktree。

```bash
git -C /root/Emboddied_Spatial_Memory worktree add --detach /root/autodl-tmp/vsmt_worktrees/s3-04-<commit> <commit>
cd /root/autodl-tmp/vsmt_worktrees/s3-04-<commit>
bash ops/vsmt/s3_04_freeze.sh all
bash ops/vsmt/s3_04_freeze.sh status
```

约 30～60 分钟，前台即可；再跑一次 `all` 保留本提交上已通过的步骤；换提交就在新的输出根里全部重做。没有兜底关机。导出要拉回后在另一个 checkout 里提交（在冻结 worktree 里提交会换提交，等于开始新的冻结）。解封前若只修了 `ops/` 的运维缺陷要重冻结，设 `PREVIOUS_RECEIPT=<旧的 freeze_receipt.json>`：新选择与旧回执逐位相同才写回执（106-4 (a)）。

| 步骤 | 做什么 | 通过线（不过即停，不写回执） |
|---|---|---|
| suite | 全量测试 | 全部通过 |
| check | G1：S3-03 verify 无问题、导出等于其清单、30 份第 1 轮权重文件等于训练回执、S0-05 登记值等于运行值；G5：四个 test 根的封存标记仍为 sealed、摘要等于 S3-02 导出的封印（只读标记文件） | 全部相等 |
| select（两套前端） | G2：用冻结代码从合并审计重算选参读数，与 S3-03 的逐值比较；G3：身份连续率、检索成功率的事件数在全部运行里只有一个值；按 102-4 选配置；定 test 运行清单与探针 episode | 逐值相等；只有一个值 |
| probe（两套前端） | G4：每个选中运行（学习臂 5 个种子）在帧数最少、且有身份事件的 2 条 validation episode 上重跑（约 100 次小审计，按 cgroup 取最大安全并行数，单线程环境与 S3-03 的作业池相同） | 与 S3-03 的审计逐位相同（墙钟、提交号、头路径除外） |
| receipt | 冻结回执与导出 | 以上全过、S3-05 入口存在、worktree 干净 |
| verify | 回执摘要、代码与冻结文件对照回执、导出摘要；写运行清单 | 无问题 |

只报告、后果事先写定（106-3）：约束不可满足的臂（结论边界按 102-1／102-4）、缺种子（涉及它的主门在 S3-05 记不可判）、选中点落在网格端点（网格不改，102-6）、validation 事件数。

**输出**：输出根 `$AUTODL/vsmt_private/s3-04-<commit>`（各步 JSON、`freeze_receipt.json`、`<前端>/probe/`）；导出 `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_04_{freeze,check,selection_<前端>,probe_<前端>,manifest,verify}_<commit>.json`。**下一步（106-5）**：拉回导出、提交到 `results/` 并推送 `main` 与 `s1-02a-runner`，等用户确认后 S3-05 才解封 test。冻结后 `src/`、`configs/` 不再改；解封前若只需修 `ops/` 的运维缺陷，修好后整趟重跑 S3-04，选择必须与旧回执逐位相同（106-4）。

## 怎样复现 S3-05（test 一次性运行，裁决 107）

白话：S3-05 回答“冻结好的每个臂在 test 上考多少分、主门过没过”。输入是 S3-04 冻结回执钉住的代码、配置与权重，以及只读一次的 test；输出是两套前端的主表、VSMT-lean 对每个消融与规则臂的比较、主门固定顺序三步的判定、节点 F1 的差值与 90% 区间、三分解、规模与成本与逐例失败。例如回执提交之后 `src/` 里有一个文件变了，check 就停下，test 保持封存。它只跑一次，不调任何东西。

**前提**：S3-04 回执已拉回、提交到 `results/` 并推送（106-5），用户确认并给出放行口令（回执摘要前 12 位）；在 B1 上建一个 detached worktree，它的 `src/`、`ops/`、`configs/` 与冻结提交相同、`results/` 里有回执。

```bash
cd /root/autodl-tmp/vsmt_worktrees/s3-05-<commit>
setsid nohup env S3_05_GO=<回执摘要前 12 位> RECEIPT=/root/autodl-tmp/vsmt_private/s3-04-<冻结提交>/freeze_receipt.json bash ops/vsmt/s3_05_test.sh all > /root/autodl-tmp/vsmt_outputs/run_logs/s3-05.log 2>&1 < /dev/null &
bash ops/vsmt/s3_05_test.sh status
```

| 步骤 | 做什么 |
|---|---|
| suite | 全量测试 |
| check | `verify_freeze` 对照回执（代码、权重、ELU-P 登记值、test 清单）；回执已提交在 `results/`；放行口令等于回执摘要前 12 位 |
| unseal | S3-02 封印摘要等于回执所记；逐 episode 重算四个 test 根并与封印逐项相等，才把它们打开为第 1 次读取，每个根旁写读取记录 `TEST_READ.json`（续跑是同一次读取；S3-03／S3-04 的入口照旧拒读）；再定每套前端可用的 test episode |
| run | 作业池：每个作业是一条 test episode 上回执里的一个运行（node audit 只算指标，`--manifest-split test --test-receipt`，入口再核对配置是回执冻结的那个）；崩溃同输入自动重跑一次，仍失败记为数据失败、照记、整趟继续；运行中不打印、不导出任何指标 |
| merge → stats | 全部作业结束后，每个运行合并一份，再一次性按 107-4 算统计（`lean_s3_05`） |
| export | `$AUTODL/vsmt_outputs/exports/vsmt_lean_s3_05_*_<commit>.json` 与运行清单 |

**工作机（107-3）**：解封之后才可能复制 test——`remote_hosts.py setup --run-root $AUTODL/vsmt_private/s3-05-run --kinds test`（B1→w4；w4 准入后可用 `--relay-from w4 --relay-key <w4 上能登录 w1 的密钥>` 接力到 w1，密钥放到 w4 上须用户同意），代码 worktree 同步到冻结提交；`admit --kinds test --reference-run-root $AUTODL/vsmt_private/s3-03-run`：在工作机上按封印逐文件核对 test（结果记进读取记录），并在冻结提交上重跑 S3-03 的 validation 审计逐位比对（不读 test）。作业池每 30 秒读 `<运行根>/hosts/`。

## 怎样发布与下载 S3 产物（S3-05R，裁决 110）

白话：S3 的产物分四层发到 Hugging Face，每层可单独下载：T0 结果与权重（`Jsun0632/vsmt-lean`，模型仓库）、T1 评估输入（validation 与 test 的原始 episode、几何、两套 cache，`Jsun0632/vsmt-lean-s3-eval`）、T2 训练与审计记录（S3-03、S3-05 运行根，`Jsun0632/vsmt-lean-s3-records`）、T3 训练输入（train 的同四类，`Jsun0632/vsmt-lean-s3-train`）。每条 episode 目录是一个确定性 tar（成员按路径排序、时间 0、属主 0/0、权限 644/755），清单 `MANIFEST.json` 记每一项的 sha256、字节数、恢复路径和目录树摘要（与 S3-02 test 封印同一算法）；上传前 test 每条对封印、cache 每条对 S3-02 导出，不一致就不上传。下载的人解包后重算树摘要即可逐字节核对；恢复路径与 B1 相同（`/root/autodl-tmp` 下），仓库脚本不用改路径。它不改任何结果，也不是新实验。

发布（B1，先 `hf auth login`；脚本自己 `source /etc/network_turbo`；中断后同一命令续传）：

```bash
setsid nohup bash ops/vsmt/hf_release.sh T0 T1 > /root/autodl-tmp/vsmt_outputs/run_logs/hf-release.log 2>&1 < /dev/null &
```

每层依次：发布测试 → `plan` → `run`（打包、核对、按批上传，默认每批 20 GiB）→ `verify`（远端大小与 sha256 对清单，清单与仓库 revision 导出为 `vsmt_lean_hf_release_<层>_<提交>.json`）。先以 private 发布；逐文件核对并核实 ProcTHOR-10K、AI2-THOR 渲染图的再分发许可后才转 public。

下载并恢复（任一机器）：

```bash
python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-eval --repo-type dataset --revision <论文写明的提交> --select validation/instance_cache/ --dest /root/autodl-tmp
```

## 怎样跑 LLM-op（附录臂，裁决 105）

白话：LLM-op 回答审稿人必问的“零训练的大模型直接做记忆修订够不够”。输入是与其他臂逐字节相同的封存特征表（转成带表头的表格文本）和两段登记的指令，模型是 DeepSeek `deepseek-flash`（2026-10-04 实际为 V4.1-Flash）默认推理模式；输出是两套前端各 1 条 validation episode（裁决 108；原为 15 条）的闭环指标（与其他臂同一个 node audit、同一套指标）、全部调用存档与一份导出。每帧问两次：先关联（每个色块选一个召回实体或 BIRTH），求解后再判存在（每个可判定实体 RETRACT 或 NOOP）。它不训练、不选参、不进主表、不读 test；它独立于 S3-03 的作业池，可以在另一台机器上和 S3-03 同时跑。

**前提**：合同 [`configs/vsmt/lean_s3_03_llm_op_v1.json`](configs/vsmt/lean_s3_03_llm_op_v1.json) 的两个运行位（`pilot_run`、`validation_run`）在用户审过代码后由一个提交打开，之前试点与正式运行都会拒绝；S3-03 的 check 已写出 `inputs.json`（validation 两套前端都已完成）；新机器（不需要 GPU；建议 ≥16 核、≥64 GB 内存、数据盘 ≥50 GB）上用户自己写好密钥文件 `/root/.config/vsmt/deepseek.env`（一行 `DEEPSEEK_API_KEY=...`，权限 600）。

```bash
# S3-02 主机（只读；在审过的提交上新建干净的 detached worktree）
bash ops/vsmt/llm_op.sh plan                         # 抽 1 条 validation episode 与试点 episode，写 plan.json 与 transfer.txt
# 已有按 15 条写的计划时（裁决 108 之前）：SUPERSEDE_PLAN=1 bash ops/vsmt/llm_op.sh plan，旧计划改名为 plan.superseded.<sha12>.json 保留
SSH_KEY=<新机器认可的私钥> bash ops/vsmt/llm_op.sh transfer <新机器地址> <端口>   # 按原绝对路径拷过去（15 条时约 8 GB，已在的文件 rsync 跳过）
# 新机器（同一提交的干净 checkout）
bash ops/vsmt/llm_op.sh test                         # 全量测试
bash ops/vsmt/llm_op.sh check                        # 逐条重算 cache 封印、核对回执／几何表／两个 ReID 头，读密钥、查 API
bash ops/vsmt/llm_op.sh pilot                        # 两套前端各 200 帧 train 试点；遇到决定点以退出码 3 停下汇报（存档里有的调用回放、不重复付费）
nohup bash ops/vsmt/llm_op.sh run > /root/autodl-tmp/vsmt_outputs/run_logs/llm-op.log 2>&1 &
bash ops/vsmt/llm_op.sh status                       # 进度、费用、STOP 原因；要停就 bash ops/vsmt/llm_op.sh stop
bash ops/vsmt/llm_op.sh replay-check                 # 每套前端只用存档回放最短的一条，须与正式运行逐字节相同（在 export 之前）
bash ops/vsmt/llm_op.sh export                       # results/vsmt_lean_llm_op_<commit>.json
```

| 步骤 | 做什么 | 停点 |
|---|---|---|
| plan | 按 sha256(“vsmt-lean-llm-op-105-2\|” + episode ID) 升序取两套前端都可用的第 1 条 validation episode（裁决 108；原 105-2 取前 15 条）；试点取同一顺序里 train 上第一条至少 200 帧的；记下各封印摘要、每帧行数（本前端 S3-03 第 0 轮 ELU-P 回执的均值）与要拷的路径（试点只拷公开面和生成回执） | 计划只写一次（`SUPERSEDE_PLAN=1` 只替换条数不同、盐串与抽签顺序相同、正式运行未开始的旧计划，旧计划改名保留）；S3-03 的输入记有问题，或仍是 provisional（除非 `ALLOW_PROVISIONAL=1`，记进计划） |
| check | 抽中的与试点的 cache 逐帧重算封印并等于计划；原始回执与几何表摘要；两个 ReID 头是 S0-03 按来源钉住的；密钥能读、API 列出 `deepseek-flash`；按内存与核数定并行数 | 任一项不符 |
| pilot | 两套前端各在试点 episode 前 200 帧上真调 API，只跑公开阶段、不读私有、不算指标；统计 token、耗时、无效回答与回退、返回的模型名；按每行价钱 × 满帧行数（登记值与试点自己的取大者）× 计划帧数推算，全部按峰时价（最坏情况）再加试点本身的花费；登记模型名 | 推算超过 30 美元（裁决 108；原 150）；某类调用试点里没问过、没法定价；某类回退率超过 2%；两套前端返回的模型名不同（用户决定后 `ACCEPT_PILOT=1`，记进运行记录） |
| run | 2 个作业（2 套前端 × 1 条）并行跑 node audit 的 LLM-op 正式审计（metrics-only、validation）；存档里有的调用一律回放，存档中间缺调用即拒绝；中断后再跑一次 `run` 从存档续跑 | 账本（含试点）到 30 美元不再开新作业（已开跑的中断后仍可续跑）；到 40 美元写 STOP（裁决 108；原 150／200），所有进程在下一次调用前停下（每个进程调用前自己也核账，驱动不在也成立）；模型名改变或致命 4xx 写 STOP；驱动被杀或出错也写 STOP；工程失败不再派发新作业 |
| replay-check | 每套前端只用存档回放最短的一条 episode（一次 API 也不调），轨迹摘要与指标须与正式运行逐字节相同，记进 `replay/check.json` | 不同即退出码 3 |
| export | 逐 episode 指标与合并、每套前端的调用统计（回退率超过 2% 标“格式不可靠”）、费用、模型名、试点报告、回放核对与运行记录 | 有 episode 没跑完；没有通过的回放核对 |

**输出**：运行根 `$AUTODL/vsmt_private/llm-op-run`（`plan.json`、`transfer.txt`、`check.json`、`pilot/`、`model.json`、`archive/<前端>/<episode>.jsonl` 与它的 `.ledger.json`、`audit/<前端>/<episode>/LLM-op/node_audit.json`、`run.json`、`logs/`、可能的 `STOP`）；导出拉回 `results/` 提交。外壳的退出码：0 完成；2 拒绝（合同位未开、缺前一步、计划或代码变了）；3 决定点（推算超上限、STOP、没跑完）；其他为失败（看 `logs/`）。

**怎样核对复现**：托管 API 的回答不能逐字节重现，所以复现靠存档：`replay-check` 只读存档、一次 API 都不调，同一代码在同一台机器上轨迹摘要与指标须与正式运行逐字节相同；它要在 `export` 之前跑（export 往 `results/` 写文件后 checkout 不再干净，回放的审计会拒绝）。论文写“DeepSeek V4.1-Flash（API，访问日期）”，模型名以每次回答返回的为准；账本只覆盖这个运行根里的存档，实际账单以 DeepSeek 控制台为准（节假日的非峰时价账本不计，只会高估）。

## 论文结果与复现索引（S3-06，裁决 113-5）

白话：这一节回答“论文里每一个数从哪个文件来、用哪条命令、在哪个提交上算出来”。输入是 `results/` 里已提交的各阶段导出，输出是下面这张“表／图 → 文件与字段 → 命令与提交”的索引，以及同一张索引的机器可读版本 `results/vsmt_lean_s3_06_paper_index_<tag>.json`（每个文件都重算 sha256，并与列出它的阶段 manifest 比对）。例如审稿人想核主表某一格，就按索引找到 `vsmt_lean_s3_05_statistics_8d58475.json` 的 `fronts.instance.main_table`，再用下面的复算命令从合并审计重算一遍。它不新增实验，也不替代上面各阶段的“怎样复现”。主张的写法见 METHOD 第二节“S3-05 之后的主张范围”。

| 论文位置 | 内容 | 结果文件（`results/`）与字段 | 命令与提交 |
|---|---|---|---|
| 表 1／表 2 | 主表（实例分割／SAM 2.1）：9 个臂 × 节点 F1 两列、残留率、假撤回率两列、身份连续率、检索成功率、恢复延迟（附未恢复数）、污染 AUC，逐列有效 house 数 | `vsmt_lean_s3_05_statistics_8d58475.json` → `fronts.<前端>.main_table`、`exclusion_lists`；事件与分母计数在 `vsmt_lean_s3_06_reanalysis_<tag>.json` → `d4_counts`：与主表均值同一批 house 的在 `per_arm_kept_houses`，全部可用 episode 的绝对数（例如未恢复物体数，多数落在被排除的 house 上）在 `per_arm_all_houses` | S3-05（运行 `8d58475`，冻结 `dea8c20`，回执 `4fd08d4f…`）；复算见下 |
| 表 3 | 主门固定顺序三步与原主门（只报告） | `fixed_sequence`、`fronts.<前端>.primary_gate`、`fronts.<前端>.original_gate` | S3-05 |
| 表 4 | NoVersion、HandCost、HeuristicLabel、AssocOnly 对 VSMT-lean，逐指标的差值、双侧 90% 区间、单侧下界与 82-1（描述性） | `fronts.<前端>.comparisons`；AssocOnly 的全部指标在 `d2_assoc_only`，双侧区间在 `d3_intervals` | S3-05 ＋ 复算 |
| 表 5 | TAF、ELU-P、RAC、LOW 对 VSMT-lean 的逐指标取舍（描述性） | `fronts.<前端>.comparisons`、`d3_intervals` | 同上 |
| 表 6 | 三分解（每个臂按自己的决策数算占比，不跨臂排名） | `fronts.<前端>.decomposition_totals`、`d6_decomposition` | 同上 |
| 表 7 | 规模与成本（每帧运行时间只作量级） | `fronts.<前端>.size_and_cost_episode_means`、`d7_size_and_cost` | 同上 |
| 表 8 | 外部验证（3RScan validation，只有实例分割列：108 条 episode 合成 46 个场景，实例图由标注网格渲染，代理真值，冻结配置，只报告、不进主门；SAM 2.1 列按冻结前端不可算，110 条里只有 3 条可用） | `vsmt_lean_s3_07_statistics_aa94373.json` → `fronts.instance.main_table`、`comparisons`（含双侧 90% 区间）、`exclusion_lists`、`cache_data_failures`、`fronts_missing`、`not_applicable`；逐 episode 在 `vsmt_lean_s3_07_merged_instance_aa94373.json` | `FRONTS=instance bash ops/vsmt/s3_07_external.sh audit`（B1＋w4＋w5，运行 `aa94373`，冻结 `dea8c20`；代码在分支 `s3-07-impl`，尚未并入 main） |
| 图 2／图 3 | 残留率与节点 F1 的取舍；主门两项的逐 house 配对差 | 主表；`d5_per_house` | 画图脚本 planned |
| 附录 | 选参与网格端点；选参曲线与训练回执（逐 epoch 分项损失）；数据清单与失败原因；功效与零效应校准；LLM-op（n＝1） | `vsmt_lean_s3_04_selection_{instance,sam2}_dea8c20.json`；`vsmt_lean_s3_03_{readings,trainings}_{instance,sam2}_10f7013.json`；`vsmt_lean_s3_02_*_3f6ef1d.json`；`vsmt_lean_s3_01_planning_6c57903.json`；`vsmt_lean_llm_op_dea8c20.json` | 见上面各阶段的“怎样复现”与 LLM-op 一节 |

**怎样复算（L0：只用已提交的 `results/`，纯 CPU，不读 test 根，不连服务器）**：在一个 `src/`、`ops/`、`configs/` 与输入文件都没有未提交改动、输入都受 git 跟踪、`src/` 与 `configs/` 与冻结提交 `dea8c20` 相同的提交上，于仓库根目录运行

```bash
python ops/vsmt/s3_06_reanalysis.py run --workers 8
```

脚本先用冻结的 `lean_s3_05` 函数从两份合并审计逐值复现 `vsmt_lean_s3_05_statistics_8d58475.json`（`receipt_sha256`、`written_utc` 除外），不相等就以退出码 3 停下、只写差异所在的字段；相等才继续算 D2～D8，写出 `results/vsmt_lean_s3_06_reanalysis_<tag>.json` 与 `results/vsmt_lean_s3_06_paper_index_<tag>.json`（tag 是运行时的提交）。只需重写索引（例如后来的阶段补了导出）时，用 `python ops/vsmt/s3_06_reanalysis.py index --reanalysis-tag <已提交复算的 tag>`：不重算任何统计，只把索引列出的每个文件重算 sha256、与阶段 manifest 比对，写 `vsmt_lean_s3_06_paper_index_<当前提交>.json`。同一提交的输出已存在时拒绝覆盖，确要重写须加 `--replace`。退出码：0 完成；2 拒绝（代码或输入有未提交改动、输入不受 git 跟踪、输入缺失或与 manifest 不符、`src/` 或 `configs/` 与冻结提交不同、输出已存在）；3 复算不等；4 已写出、但某项一致性核对报了问题；1 意外错误（有 traceback）。D2～D8 都是看过 test 之后算的描述性读数，不作门、不做多重比较校正；D3、D5 的数是“优势”（正数对 VSMT-lean 有利，越低越好的指标已翻转符号）。本机 CPU 不稳，若运行崩溃或复算不等，改在无卡服务器上用同一命令重跑，不在本机反复重试。

| 输入（只读） | 输出 |
|---|---|
| `vsmt_lean_s3_05_*_8d58475.json`（七个，按 S3-05 manifest 逐个核对 sha256，读统计、输入与两份合并审计）、`vsmt_lean_s3_04_{freeze,manifest}_dea8c20.json`（回执按 S3-04 manifest 核对） | D1 复算核对、D2 VSMT-lean 对 AssocOnly 的全部指标、D3 双侧 90% 区间、D4 事件与分母计数、D5 逐 house 配对差、D6 三分解占比、D7 规模与成本、D8 一致性核对；论文索引 |

复现层级（与裁决 110 的 Hugging Face 四层对应）：L0 只用 `results/` 重算表 1～7 与图 2～3 用到的统计（上面这条命令；附录各表直接取各阶段已提交的导出，表 8 等 S3-07）；L1 用 test／validation 的原始 episode、几何、两套 cache 与权重重跑审计（HF T1；复现入口与读取记录的写法在 S3-05R 另定）；L2 用训练记录重训（HF T2）；L3 从 ProcTHOR-10K 起全部重跑（HF T3）。确定性边界：同一提交与同一 `TRAIN_THREADS` 的权重逐位相同（裁决 96，只在 Intel AVX-512＋MKL 上验证）；审计是确定的（S3-04 探针逐位一致）；生成器结构可复现、字节不保证（LOG-303）；SAM 2.1 cache 预期确定但未逐字节验证；LLM-op 靠调用存档回放逐字节一致。

## 实现与证据

| 目录 | 职责 |
|---|---|
| `src/vsmt/lean_*.py` | D-224 纯核心：实体记忆与执行器、特征/召回/分配、前端 cache、对照臂、代价头、runner、teacher 与评价、开发表 |
| `ops/vsmt/lean_*.py` | 服务器入口：S1-02 数据生成、S1-03 cache、S1-04 诊断、S2-04 单 episode 评价、S2-05 开发表编排与导出 |
| `configs/vsmt/lean_*.json`、`tests/` | 版本化机器合同（规则摘要由跨合同测试钉住）与测试 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物（不进 Git）、可复算导出报告 |
| `src/cpmt/`、`src/spatial_world_model/`、`experiments/`、`schemas/`、`literature/`、`docs/source/`、`prototype/` 及 `src/vsmt/` 里的非 lean 模块 | 历史实现、原始资料与文献，保留不删 |
