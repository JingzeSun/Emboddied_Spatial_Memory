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

## 实现与证据

| 目录 | 职责 |
|---|---|
| `src/vsmt/lean_*.py` | D-224 纯核心：实体记忆与执行器、特征/召回/分配、前端 cache、对照臂、代价头、runner、teacher 与评价、开发表 |
| `ops/vsmt/lean_*.py` | 服务器入口：S1-02 数据生成、S1-03 cache、S1-04 诊断、S2-04 单 episode 评价、S2-05 开发表编排与导出 |
| `configs/vsmt/lean_*.json`、`tests/` | 版本化机器合同（规则摘要由跨合同测试钉住）与测试 |
| `data/`、`outputs/`、`results/` | 来源/split、服务器大产物（不进 Git）、可复算导出报告 |
| `src/cpmt/`、`src/spatial_world_model/`、`experiments/`、`schemas/`、`literature/`、`docs/source/`、`prototype/` 及 `src/vsmt/` 里的非 lean 模块 | 历史实现、原始资料与文献，保留不删 |
