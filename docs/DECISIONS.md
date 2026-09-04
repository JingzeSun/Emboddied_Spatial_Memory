# 当前研究决策日志

> 本文件只保留 D-032 后的活动摘要和之后的新决策。D-001～D-031 的完整原文及当时 HC 状态保存在 `archive/pre_d032_projective_structural_latent_memory_2026-09-04/snapshot/docs/DECISIONS.md`。新决策继续 append-only；不得静默改写 accepted 条目。

## 现行决策摘要

| ID | 当前状态 | 对新主线仍有效的约束 |
|---|---|---|
| D-001 | retained | Observation 与长期 world memory 分离；写入必须先 association |
| D-002 | retained | VP 是观测线索，不是长期坐标 |
| D-003 | retained | Local Chart/Place 是稳定锚点；learned split/merge 不是首个 MVP 默认 |
| D-004 | retained | 不以 RGB reconstruction 为主目标 |
| D-009 | retained | Related Work 基石必须由正式论文/官方来源核验 |
| D-012 | retained | superseded 合同进入 archive；source artifacts 不覆盖 |
| D-015 | retained | README/EXECUTE/docs01–05/单一实验包的信息架构 |
| D-019 | retained | DECISIONS 是唯一人工确认状态中心 |
| D-024～D-031 | superseded in active scope | posterior-only ESGBU 与 predicate 泛化只从 D-032 archive 追溯；双时间、scope、time、evidence、executor 可作 revision 子机制 |
| D-030 hardware fact | retained as environment evidence only | RTX 4070 Laptop CUDA 曾验证可用；不自动冻结新训练预算 |
| D-032 | accepted | Projective Structural Latent Memory 成为唯一活动主线 |

## 人工确认中心

推荐项不是 accepted。用户回答后追加 D-XXX，并在下表写入决策 ID；schema、fixture、config 和正式 run 保存实际 `decision_ids`。

| HC | 必须决定什么 | 推荐默认值 | 直接影响 | 状态/决策 |
|---|---|---|---|---|
| HC-020 | 第一批验证路线与规模 | 先12条 hand-authored sequences，再 simulator | oracle/evaluator 起点 | pending / — |
| HC-021 | 输入与 oracle 来源 | RGB-D+intrinsics+pose+action/time；先 simulator oracle | 可归因边界 | pending / — |
| HC-022 | structural tokenizer 单元 | hybrid surface/object/portal/occlusion regions；VP仅cue | H1 与 region oracle | pending / — |
| HC-023 | world memory 层次 | Place→Chart→slot/track→versioned facts | node ontology | pending / — |
| HC-024 | binding 与 identity 等价 | set-valued oracle，允许 split/merge 多解 | B1–B5 | pending / — |
| HC-025 | node birth/reactivation | candidate 多帧确认；单帧高危写 quarantine | G1/G2 | pending / — |
| HC-026 | Chart/Place attachment | MVP固定split/merge，学习局部attachment | G2–G4 | pending / — |
| HC-027 | lifecycle/visibility | transient/persistent 与 motion/static 解耦 | M1–M3 | pending / — |
| HC-028 | latent state/update | bounded prototypes + uncertainty + evidence refs | latent drift/污染 | pending / — |
| HC-029 | revision transaction | scoped CREATE/UPDATE/RELINK/RETRACT/REPLACE/PRESERVE/QUARANTINE | R1–R3 | pending / — |
| HC-030 | time/provenance/quarantine | event/arrival/valid time分离；破坏性写入须证据 | R4–R6 | pending / — |
| HC-031 | 主指标与 hard gates | binding/growth/protection先过门，再看task | 全评价 | pending / — |
| HC-032 | baseline/预算公平 | 同前端；参数和wall-clock两张表；native system单列 | 因果归因 | pending / — |
| HC-033 | 数据与 split | episode/template/place 不跨split；test晚解封 | 泛化可信度 | pending / — |
| HC-034 | 下游任务 | temporal query主任务，轻量导航/规划次级 | T1 | pending / — |

详细工作表位于 `docs/human_confirmation/`，指标总字典位于活动实验包 `CRITERIA.md`。

## D-032 — Projective Structural Latent Memory 主线 supersession

- 日期：2026-09-04
- 状态：accepted（研究主线与文档重构）
- 用户确认：当前 posterior-only ESGBU 看起来主要是更新 loss，要求回到 archive 中以 DINO-WM 启发的透视/结构 latent、持久节点、实时空间扩充与环境认知修订设想；允许重构整个项目并把当前方案归档，同时保持现有细粒度。
- 决策：
  1. 唯一活动问题改为把 view-dependent structural latent 转换为 world-centric persistent memory，并统一处理 binding、birth、graph expansion、dynamic isolation 与 revision；
  2. 方法采用 `Tokenize → PredictProject → Bind → Transact → Execute` 闭环；工作名 PSLM；
  3. 表示至少区分 World/Place、Local Chart、persistent slot/transient track、projective observation region 和 visual latent；
  4. action-conditioned prediction 只面向 structural latent、visibility 和 attachment/frontier，不以 RGB reconstruction 为主目标；
  5. 原 ESGBU 的 `Delta G/M/tau/Z`、双时间、证据集合、protected controls 和 executor 保留为 `U_t` 的 revision 子分支；schema-conditioned predicate 泛化不再是主贡献；
  6. 第一篇核心聚焦 region-to-world binding、controlled node birth/local attachment、dynamic persistence 与 versioned revision；完整导航、开放本体和 learned global Chart split/merge延期；
  7. 当前活动文件、实验包、HC、schema/config 与文献索引先做72文件快照，再原位 supersede；旧实验不与新合同拼接；
  8. `docs/source/`、PDF、原型、脚本、outputs 和更早 archive 原位保留。
- 被取代范围：D-024/D-025 的活动方法与信息结构；D-026～D-031 的数据规模、阈值、谓词泛化与训练合同只解释旧主线，不自动迁移。
- 保留范围：D-001～004 的 observation/world、VP、Chart 和 no-RGB 原则；研究诚信、test 隔离、正式 run 记录和 source preservation。
- 是否接触 test：否；仅检查文档、archive 和公开文献，没有生成或查看正式 test。
- 实现/验证状态：未实现、未验证。
- 迁移位置：`archive/pre_d032_projective_structural_latent_memory_2026-09-04/`。

## 新决策模板

```text
## D-XXX — 标题
- 日期：YYYY-MM-DD
- 状态：proposed / accepted / superseded / rejected
- 用户回答或新证据：
- 决策：
- 备选方案：
- 原因：
- 方法/实验影响：
- 是否接触 test：
- 验证方式：
```
