# 当前研究决策日志

> 本文件只保留现行 accepted 决策和之后的新决策。完整历史、superseded 决策及原始理由见 `archive/pre_execution_v2_2026-08-28/06_decision_log.md`。
>
> 修改 accepted 决策必须追加新条目，不得静默改写旧条目。

## 现行决策摘要

| ID | 状态 | 当前约束 |
|---|---|---|
| D-001 | accepted | ObservationGraph 与长期 world belief 分离；写入必须 association |
| D-002 | accepted | VP 是观测线索，不是长期坐标 |
| D-003 | accepted | Local Chart/Place 是 MVP 稳定锚点，不学习 split/merge |
| D-004 | accepted | MVP 不以 RGB reconstruction 为目标 |
| D-007 | baseline only | normalized EMA/limited prototypes 只是低层 state baseline |
| D-008 | superseded in scope by D-017 | online spatial context revision 保留为世界信念演化中的冲突分支；四层状态分离继续有效 |
| D-009 | accepted | Related Work 事实基石必须官方核验同行评审 |
| D-010 | retained as submechanism by D-017 | Structured Innovation + Affected-Subgraph Revision 继续负责冲突证据和局部修订，不再代表完整方法 |
| D-011 | partially superseded by D-017 | typed deterministic executor 与 oracle→deterministic→learned 保留；动作条件预测和小规模主动取证纳入主线，完整导航仍延期 |
| D-012 | accepted | superseded 合同进 archive；source artifacts 不覆盖 |
| D-013 | accepted | expansion/revision/ActiveContext 分层；方向关系必须有 reference frame |
| D-014 | superseded in structure by D-015 | 渐进式思想保留，但多入口文件结构被替换 |
| D-016 | proposed | fixture 修订判题语义待人工确认；统一由 HC-001–HC-006 跟踪 |
| D-017 | accepted | 总问题升级为动作条件下的结构化世界信念扩展与修订 |
| D-018 | proposed | 世界信念扩展判题语义待人工确认；统一由 HC-007–HC-012 跟踪 |
| D-019 | accepted | DECISIONS.md 成为唯一人工确认中心；HC 条目必须映射合同、产物和日志 |
| D-020 | accepted | 每个 HC 建立同名详细判题工作表；DECISIONS.md 仍是唯一状态与最终回答入口 |
| D-021 | accepted | 将 Region-to-World Structural Binding 纳入 planned 方法桥接层；具体绑定与写入语义由 HC-014 冻结 |
| D-022 | accepted | 核心贡献聚焦“新证据如何有限、可追溯地改变世界事实”；预测、区域绑定、主动取证与 Top-K 均降为前置或下游 |
| D-023 | superseded by D-024 | BEGR-Net 候选被更清楚的 `ΔG/M/τ/Z` 与 ESGBU 文档主线替代 |
| D-024 | accepted（文档 supersession） | 活动仓库改为证据感知稀疏图后验修订；旧版逐文件归档；实验启动顺序仍由 HC-018 冻结 |
| D-025 | accepted（HC/criteria 信息架构） | 现行 HC 只留 posterior 直接项；C1–C15 的含义、计算和例子嵌入实验设计列，`CRITERIA.md` 保留为总字典 |
| D-026 | accepted（HC-018/Q01.1） | 第一批验证采用方案 A：先构造 hand-authored oracle smoke cases，再接 symbolic/AI2-THOR；首批做12还是36仍待 Q01.2 |
| D-027 | accepted（HC-018/Q01.2） | 两阶段案例规模：先12个代表案例及36个故意错误，再扩为总计36个语义案例及108个故意错误 |
| D-028 | accepted（HC-018/Q01.3） | T0a 使用严格判尺门：12/12 oracle 全接受、36/36 deliberate corruptions 全拒绝且命中预期主错误码 |
| D-029 | accepted（HC-018/Q01.4） | T0a criteria 按适用性分层：C1–C10/C13/C14按标签必算，C15只验接口，C11/C12与C14合成成本记N/A |
| D-030 | accepted（HC-018/Q01.5） | 采用精益40小时硬上限并优先加速；T0a CPU-first，学习训练使用已验证可用的 RTX 4070 Laptop CUDA |
| D-031 | accepted（HC-002/Q02.1） | 采用最小核心谓词＋开放 predicate registry＋schema-conditioned 共享 updater；held-out registered predicates 只作次级泛化，不做任意自然语言谓词 |

## 人工确认中心（唯一入口）

> 本节是项目中所有“必须由用户/研究者确认”的唯一登记处。
>
> 其他合同、代码注释、issue 或运行日志只能引用 `HC-XXX`，不得重新复制一份待确认清单。若发现新的人工决策，必须先在这里新增 HC 条目并完成映射，才能继续修改 schema、fixture、训练目标或评测协议。

### 状态与使用规则

| 状态 | 含义 |
|---|---|
| pending | 已发现问题，等待用户明确回答 |
| accepted | 用户已确认，并已追加对应 `D-XXX` 决策 |
| rejected | 用户明确拒绝推荐默认值，并已记录替代决定 |
| superseded | 后续决策替代，保留追溯 |

执行流程：

1. 新问题先创建稳定的 `HC-XXX`，填写问题、推荐默认值、影响和映射；
2. 未获得用户明确回答前保持 `pending`，不得从代码、对话语气或实验结果推断“默认同意”；
3. 用户确认后，追加新的 `D-XXX` accepted/rejected 决策，并在 HC 行写入该决策 ID；
4. 对应合同只写“blocked by / governed by HC-XXX”并链接到本节，不再复述问题；
5. schema、fixture、config 和正式运行记录必须保存相关 `decision_ids`；
6. 若接触 test 后才改变决定，必须新建 protocol version，并在决策中明确记录。

### 当前待确认总表

以下推荐值只是项目建议，`pending` 不等于已经接受。D-025 后，当前且唯一的 HC 集合是 HC-002/003/004/005/013/015/016/017/018/019；其他旧 HC 只在 D-025 前快照追溯，不再阻塞 posterior-only 当前版本。当前指标公式以 `experiments/bounded_revision_validation/CRITERIA.md` 为准。

| HC ID | 当前必须由你决定什么 | 推荐默认值 | 就地评价含义与数字例子 | 详细工作表 | 状态 / 决策 |
|---|---|---|---|---|---|
| HC-002 | 哪些谓词是可编辑 stored facts，哪些只是 derived views？ | MVP 存 `at/contains/supports/blocks/open`；`near/left_of` 默认派生并带 reference frame | 若 oracle 只要求改 `at(cart,B)`，重算出的 `near(cart,door)`不计独立 edit；对应 C1/C3/C5 | [HC-002](human_confirmation/HC-002.md) | pending / D-031 已接受schema-conditioned registry；Q02.2具体名单未决 |
| HC-003 | 事实变化沿哪些 typed dependency 传播并在哪里停止？ | 每种 operator 使用 relation whitelist；只取最小闭包 | oracle 必改8个、预测覆盖7个且多写3个：NUR=87.5%，CER=30%；对应 C3–C7/C14 | [HC-003](human_confirmation/HC-003.md) | pending / — |
| HC-004 | 什么负证据足以 RETRACT，什么情况只能 KEEP/QUARANTINE？ | 结合 coverage、visibility、遮挡、来源可靠性和独立重复证据 | visibility=0.2 不撤回；0.9 且可靠覆盖才进入撤回候选；对应 C1/C3/C5/C12 | [HC-004](human_confirmation/HC-004.md) | pending / — |
| HC-005 | 多个最小编辑程序何时算等价正确？ | 最终状态、最小写集、时间、证据和版本一致即可 | 同事务 `REPLACE` 与 `RETRACT+ASSERT` 可等价；事务100例中71例整体等价，C2=71% | [HC-005](human_confirmation/HC-005.md) | pending / — |
| HC-013 | 哪些指标是主指标，什么数字构成 pilot gate？ | NUR≥95%、CPR≥99.5%、transaction exact≥80%、投影后非法率=0 作为待冻结起点 | 200 controls 误改1个，CPR=99.5%；20个必要事实改对18个，NUR=90%，不通过候选门 | [HC-013](human_confirmation/HC-013.md) | pending / — |
| HC-015 | 精确/区间 valid time 怎样评分？ | 模拟器±1 step；重扫数据用 interval coverage+width | 20 Hz 的±1 step=±0.05 s；100例覆盖91例、平均宽38 s，分别报91%/38 s | [HC-015](human_confirmation/HC-015.md) | pending / — |
| HC-016 | 什么置信与冲突状态允许 COMMIT，何时必须 QUARANTINE？ | 先校准再按 operator 冻结门；高可信近似冲突必须隔离 | 0.86 vs 0.84 不硬选；0.95 vs 0.40 可候选提交；0.8–0.9 bin预测0.84、实际0.72，gap=0.12 | [HC-016](human_confirmation/HC-016.md) | pending / — |
| HC-017 | 结构化基线怎样准入，算力怎样公平？ | SA1–SA3 为最低结构化条件；同时做参数与 wall-clock 匹配 | 10M±10%参数一张表；每法6 GPU-hours再一张表；对应 C1–C15 和效率 C15 | [HC-017](human_confirmation/HC-017.md) | pending / — |
| HC-018 | 第一批数据先做 hand-authored smoke 还是 AI2-THOR？ | 先12个 hand cases，再扩36个，之后接 simulator | 第一阶段12×(1 oracle+3 corruptions)=48；第二阶段总计36×4=144个评价器输入 | [HC-018](human_confirmation/HC-018.md) | accepted / D-026～D-030 |
| HC-019 | 任务错误是否合成单一 cost？ | 主表分报错派、漏关、无关重算；暂不合成 | 若权重5/10/1，错派6、漏关5、重算8，cost=88；对应 C14 | [HC-019](human_confirmation/HC-019.md) | pending / — |

详细场景、输入输出、指标解释、数字算例和判题选项统一展开在 [`docs/human_confirmation/`](human_confirmation/README.md)，每份 HC 可独立阅读；[HC 指标白话指南](human_confirmation/METRIC_GUIDE.md)仅作跨文件术语索引。这些文件不维护状态；示例数字不是已接受阈值，状态与最终回答仍只在本表记录。

| 当前工作表 | 决策主题 | 直接指标 |
|---|---|---|
| [HC-002](human_confirmation/HC-002.md) | stored/derived facts | C1/C2/C3/C5 |
| [HC-003](human_confirmation/HC-003.md) | dependency closure/stop | C3–C7/C14/C15 |
| [HC-004](human_confirmation/HC-004.md) | reliable negative evidence | C1/C3/C5/C12/C13 |
| [HC-005](human_confirmation/HC-005.md) | equivalent minimal programs | C1/C2/C4–C7 |
| [HC-013](human_confirmation/HC-013.md) | primary metrics and gates | C1–C15 |
| [HC-015](human_confirmation/HC-015.md) | valid-time point/interval | C8/C9 |
| [HC-016](human_confirmation/HC-016.md) | commit/quarantine policy | C1/C2/C12/C13 |
| [HC-017](human_confirmation/HC-017.md) | structured baseline fairness | C1–C15 |
| [HC-018](human_confirmation/HC-018.md) | first executable data | evaluator gate + C1–C15 readiness |
| [HC-019](human_confirmation/HC-019.md) | downstream task cost | C14 |

### 对应关系的读取方式

- **对应板块**回答“这个决定改变哪一段研究合同或实验”；
- **计划产物/日志映射**回答“以后在哪里看到它被实现和实际使用”；
- 当前尚未实现的路径只是合同映射，不得被表述为已经存在的运行产物；
- 正式 run manifest 至少保存 `decision_ids: [HC-..., D-...]`，从实验数字可以反查当时采用的人工语义。

### 新人工确认条目模板

```text
### HC-XXX — 简短标题

- 状态：pending
- 需要用户确认的问题：
- 推荐默认值：
- 可选方案及代价：
- 为什么不能由模型/实现者代答：
- 对应研究合同：
- 对应场景/实验：
- 对应 schema/config/fixture：
- 对应运行日志/指标：
- 用户回答：待确认
- 接受后写入的 D-XXX：待创建
- 是否接触 test 信息：否/是（若是，必须新建 protocol version）
- 详细工作表：`human_confirmation/HC-XXX.md`
```

## D-015 — 单执行入口与五阶段合同

- 日期：2026-08-28
- 状态：accepted
- 用户确认：`docs/00–09` 信息仍然散乱，不能形成可以照着执行的思路；旧文件可归档。
- 决策：
  1. 旧 `docs/00–12`、`START_HERE.md`、`CHECKLIST.md` 和旧 README 移入 `docs/archive/pre_execution_v2_2026-08-28/`；
  2. 根目录 `EXECUTE.md` 是唯一日常执行入口，只列当前任务、产物、退出门和下一阶段；
  3. 现行研究合同固定为五个顺序文件：研究合同 → 场景 WBS → pilot → training → formal evaluation/paper；
  4. `DECISIONS.md` 独立于顺序文档，作为 append-only 决策记录；
  5. 不允许再创建平行蓝图、第二清单或第二实验合同。
- 方法影响：无；D-008、D-010、D-013 的核心研究方向不变。
- 实验影响：无；项目仍为 pre-implementation，未使用 test 信息。
- 归档来源提交：`b11c7b0`。

## D-016 — Fixture Ground-truth 语义

- 日期：待人工确认
- 状态：proposed
- 待确认项：统一登记为 HC-001–HC-006；本条不再维护第二份问题清单。
- 影响：这些决定冻结前，R1–R6 只能写设计样例，不能称为可用于监督训练的 ground truth。
- 是否接触 test 信息：否。

## D-017 — 聚焦动作条件下的结构化世界信念演化

- 日期：2026-08-28
- 状态：accepted
- 背景：后续硕士研究建议聚焦 world model。现有方案只把“新观测与旧信念冲突后的修订”作为主问题，不能覆盖机器人移动时对未见空间的预测、候选结构扩展、主动取证和连续规划。
- 决策：
  1. 项目总问题升级为 **Action-Conditioned Structural Belief Expansion and Revision**；
  2. `SceneBelief` 解释为世界模型维护的结构化 belief state；在实现层暂不改 schema 名称；
  3. 每一步先由旧 belief 与动作产生预测先验、预期可见区域和候选结构，再与新观测比较；
  4. 新证据必须走 `confirm / expand / revise / preserve / quarantine` 中明确的一条路径；
  5. 未观察空间只能进入带置信度和来源的 hypothesis set，不得直接写成已确认世界事实；
  6. Structured Innovation 与 Affected-Subgraph Revision 保留，作为冲突和真实世界变化时的局部后验修订机制；
  7. 增加离散的一步或短视界主动取证：在任务收益、信息增益和行动成本之间选择下一观察动作；
  8. 第一阶段不做视频生成式 world model，不做端到端大规模导航，不把在线加节点本身作为创新。
- 备选方案：仅把 `SceneBelief` 改名为 world model；或直接转向像素/视频生成。二者分别缺少动作预测实质或显著扩大硕士阶段范围，因此拒绝。
- 原因：该定位能保留现有 pose-aware association、版本链、关系传播和停止边界，同时把 graph expansion、结构假设和规划纳入同一条可检验闭环。
- 影响：D-008 与 D-010 从总问题降为子问题；D-011 的“导航延期”收缩为“完整导航延期”，小规模主动观察成为核心验证；`docs/01–05`、`EXECUTE.md` 和项目方法约束需要同步更新。
- 是否接触 test 信息：否。该方向调整发生在 fixture、实现和实验结果产生之前。
- 验证方式：先做 oracle/deterministic 的逐步走廊与动态修订 micro-sequences，再学习结构预测、证据吸收和动作选择；正式 test 前冻结合同。

## D-018 — 世界信念扩展的判题语义

- 日期：待人工确认
- 状态：proposed
- 待确认项：统一登记为 HC-007–HC-012；本条不再维护第二份问题清单。
- 影响：这些决定冻结前，W1–W4 只能作为设计样例，不能称为训练或评测 ground truth。
- 是否接触 test 信息：否。

## D-019 — 唯一人工确认中心与跨对话交接

- 日期：2026-08-28
- 状态：accepted
- 用户确认：所有需要人工确认的内容集中到一个文件；后续人工确认必须写入 `DECISIONS.md`，并能映射到对应研究板块和日志；需要一份可移植的新对话 Prompt。
- 决策：
  1. `docs/DECISIONS.md` 的“人工确认中心”是唯一待确认清单；
  2. 待确认问题使用稳定的 `HC-XXX`，确认后的研究决策仍使用 append-only `D-XXX`；
  3. 每个 HC 必须记录推荐默认值、替代代价、研究合同/场景映射、schema/config/fixture 映射和运行日志/指标映射；
  4. 其他文件只能引用 HC ID，不复制问题清单；
  5. 用户明确回答后才能更新 HC 状态并追加 D 决策，不从模型、代码或模糊语气推断同意；
  6. fixture metadata 和正式 run manifest 必须保存 `decision_ids`；
  7. `docs/NEW_CHAT_HANDOFF_PROMPT.md` 只作为上下文交接材料，不构成第二执行入口。
- 原因：减少多份清单漂移，使研究语义、实现和结果能双向追溯，并允许在新对话中恢复当前状态。
- 影响：扩展 D-015 的文档治理；`AGENTS.md`、`README.md`、`EXECUTE.md` 和阶段合同统一引用人工确认中心。
- 是否接触 test 信息：否。
- 验证方式：搜索现行文档不存在第二份人工确认明细；任一 HC 能定位到研究板块与计划运行产物。

## D-020 — 每个 HC 使用独立详细判题工作表

- 日期：2026-08-29
- 状态：accepted
- 用户确认：一行 HC 无法承载需要人工考虑的多种场景、输入输出和 evaluation 标准；HC-001～HC-013 都要有独立 MD 文件。
- 决策：
  1. 在 `docs/human_confirmation/` 为每个 HC 建立同名详细工作表；
  2. 工作表展开正常、边界、歧义、传感器失败和反事实场景，以及允许输出、禁止输出、指标与用户填写项；
  3. `DECISIONS.md` 继续作为唯一 HC 状态、推荐默认值、用户回答和 D 决策入口；
  4. 详细工作表不得维护第二份 pending/accepted 状态，避免漂移；
  5. 新建 HC 时必须同步创建详细工作表并从本文件回链；
  6. HC-013 登记“功能级硬门、多个正确答案和端到端指标聚合”，保持 pending，等待用户逐项确认。
- 原因：将一个抽象问题展开成可讨论、可转成 fixture 和 evaluator 的具体判题空间，同时保持决策治理单一来源。
- 影响：扩展 D-019 的信息组织方式，不改变 D-017 方法方向，也不等于接受 HC-001～HC-013 的推荐答案。
- 是否接触 test 信息：否；尚未实现或运行实验。
- 验证方式：目录存在 HC-001～HC-013 共 13 份文件；每份包含场景、输入输出/允许与禁止结果、评价和用户填写区；现行入口均回链。

## D-021 — 纳入观测区域到持久世界节点的结构绑定桥

- 日期：2026-08-29
- 状态：accepted
- 用户确认：仅依赖视觉模型从当前帧提取语义，不足以解释观测究竟应扩充或修改哪个长期空间单元；同意开始把区域级结构绑定组件补入现行方向。
- 决策：
  1. 在 `ObservationGraph` 与 `SceneBelief` 的证据吸收之间，加入 planned 的 **Structural Observation Tokenizer + Region-to-World Structural Binding**；
  2. `ObservationRegion` 是当前视角下的临时观测单元，透视远近、消失点扇区等是观测线索，不作为持久世界 identity；
  3. 持久层优先维护 world-aligned surface、portal、object，再由稳定的 Chart/Place 组织；只有完成关联且证据达到门槛的区域才可写长期 latent；
  4. 该组件是扩展、修订和 latent 写入的表示桥，不单独宣称为已经成立的第五项创新；其论文贡献地位取决于后续消融和错误分析；
  5. 先做 oracle/deterministic 区域与绑定记录，再比较固定 patch、整帧 latent、object-only 和混合结构区域；不直接训练新的大视觉模型；
  6. HC-014 负责冻结区域来源、跨帧 association、split/merge、低置信处理、写入门和评价语义；在 HC-014 accepted 前不修改 schema/config；
  7. 绑定子测试嵌入 E1、E2、E5，共用 `W0_region_binding` fixture 家族，不新增第八个端到端实验。
- 备选方案：只使用整帧视觉 latent，或把每个透视分区直接当作持久节点。前者无法给出可审计写入范围，后者会把相机运动造成的分区变化误当成世界 identity 变化。
- 原因：世界信念扩展与局部修订都要求先回答“这份新证据属于哪个已有世界单元，还是应建立新单元”；显式桥接后才能独立测量错绑、重复节点、错误合并与 latent 污染。
- 影响：扩展 D-001、D-002、D-003 和 D-017；更新 `docs/01–05`、`EXECUTE.md`、项目入口与文献综合，但不改变现有 schema/config，也不表示已经实现或验证。
- 是否接触 test 信息：否；本决定发生在实现和正式实验之前。
- 验证方式：先以人工/oracle 对应关系构造跨视角、遮挡、拆分合并、重复走廊和动态变化的 micro-sequences；再按 HC-014 的关联、重复节点、错误合并、latent 污染和控制保持指标进行消融。

## D-022 — 以世界事实的有界后验重组作为唯一母命题

- 日期：2026-08-29
- 状态：accepted
- 用户确认：项目不能以房间布局恢复、Top-K 排序、动作预测、区域绑定和图更新的简单融合来主张创新；现行文档和 E0–E6 必须共同回答“世界事实的语义状态、拓扑关系和有效时间应该怎样改变”。
- 决策：
  1. 论文唯一母命题收缩为：**新证据到来后，哪些世界事实必须改变、怎样改变、从何时生效，哪些事实必须保持，以及为什么在该边界停止**；
  2. 核心机制工作名为 **Evidence-Gated Affected-Subgraph Belief Revision**，输出 evidence path、typed operation、affected set、control set、stop boundary 与 version/provenance；
  3. 动作条件预测只负责生成 expected belief/observation，作为发现差异的前置；region-to-world binding 只负责确定证据属于谁和允许写谁；主动取证只负责补充无法判定的证据；Top-K/ActiveContext 只负责读取，均不得与核心贡献并列堆叠；
  4. 世界事实变化按三条轴组织：semantic status（unknown/candidate/confirmed/invalid/ambiguous 等）、topological relation（add/relink/propagate/stop）与 valid time/version（旧事实何时关闭、新事实何时生效、证据如何追溯）；
  5. E0–E6 不是七个平行功能：E0 建立可信判尺；E1/E2/E4 提供候选、拓扑身份和证据晋升前置；E3 主动补证；E5 直接验证有界后验修订；E6 验证读取语境不能越权写世界事实；
  6. 主要判据不是功能数量或最终任务总分，而是 necessary-update completeness、control preservation、collateral edit、stop correctness 与 version validity；
  7. “候选创新”表示尚待文献重合审计和冻结实验支持，不表示没有明确研究假设；正式论文只能把得到证据支持的部分升级为 contribution。
- 备选方案：把预测、建图、区域表示、检索和规划并列为多个贡献。该写法无法形成单一可证伪命题，也难以排除已有模块带来的性能收益，因此拒绝。
- 原因：统一母命题能让表示、预测、association、主动取证和查询各自只承担清楚的因果角色，并用同一组“必要修改与无关保持”指标判断是否真正解决问题。
- 影响：重写 `docs/01–05` 的贡献层级与 E0–E6 解释；更新 `EXECUTE.md` 和汇报 PPT 第 2 页；D-017 的 world-model 闭环保留，但贡献中心从完整闭环收缩到证据门控的有界 posterior revision。
- 是否接触 test 信息：否；尚未实现或运行正式实验。
- 验证方式：固定相同 observation/prediction/association 输入，比较不同 revision controller；逐实验报告语义状态、拓扑关系、有效时间、必要修改和 protected controls，而非只报告端到端任务成功率。

## D-023 — 双时间证据图的可训练后验修订候选主线

- 日期：2026-09-04
- 状态：proposed；执行授权仍由 HC-018 冻结。
- 背景：用户要求把项目升级到当前主要考虑的 posterior 部分，并认为只做简单规则/对象移动不足以体现可训练研究复杂度；同时要求检查多项 loss 是否反而不利。
- 候选决策：
  1. 当前候选任务收窄为乱序、多来源 evidence events 条件下的 sparse fact-graph posterior revision；
  2. 候选模型 BEGR-Net 使用 event Transformer、typed relational graph encoder 与 hierarchical transaction decoder；
  3. learned 输出为 `preserve/quarantine/commit → targets/operators/supporting evidence`；
  4. dependency closure、control/stop、valid-time legality、atomic version 和 provenance 继续由 deterministic executor 强制；
  5. 主损失收敛为 factorized transaction NLL，加可选 evidence attribution 与小 sparsity regularizer，不采用原 17 项平行 loss；
  6. 原预测、region binding、主动取证和任务读取的细粒度合同保留为后续集成，不删除或覆盖；
  7. symbolic event streams 用于训练和反证，AI2-THOR 用于可控观测，3RScan/Dyn-THOR 用于外部有效性。
- 为什么尚未 accepted：项目治理要求用户对 HC-018 的“是否允许 posterior-only 先行实施”作明确回答；“重构为主要考虑”授权了候选方案整理，但本日志不替用户自动接受具体执行门。
- 备选方案：继续完整闭环顺序；或把所有模块端到端联合训练。前者启动成本高，后者难以归因。
- 影响：已增量重构 README、EXECUTE、docs/01–05、唯一核心实验包、data/src/tests/schema 说明和文献审计；未修改现有 schema/config，未实现代码，未接触 test。
- 验证方式：B0–B7 与 L0–L5 同输入比较；双时间、typed-edge、evidence-group、hierarchical-decoder 消融；ID/OOD 拆分；若 TGN-style/flat/full-graph 对照等价则收缩 claim。

## D-024 — 证据感知稀疏图后验修订的文档 supersession

- 日期：2026-09-04
- 状态：accepted（仅限仓库与研究方案重构）；不自动接受 HC-018 的具体执行顺序。
- 用户确认：允许按当前方法重构 `embodied_spatial_memory`；旧的大杂烩内容按原文件粒度进入 archive；若规则阻止有快照的覆盖式文档重构，则升级该治理规则；目标质量面向强国际论文。
- 决策：
  1. 当前活动方案改写为 `q_phi(Delta G_t, M_t, tau_t, Z_t | G_{t-1}, E_{<=t})`，分别表示编辑程序、受影响掩码、有效时间和直接证据集合；
  2. 方法工作名为 **Evidence-Aware Sparse Graph Belief Updater（ESGBU）**；时序证据编码、异构图传播、稀疏编辑和证据归因属于候选学习模块，硬结构合法性由 executor 强制；
  3. 损失收敛为与四个预测变量对应的四项主目标；state、preserve、constraint 和 task 先作为派生评估，避免重复监督；
  4. 旧活动合同、接口、HC 和 `bounded_revision_validation` 已逐文件快照到 `docs/archive/pre_d024_posterior_updater_refactor_2026-09-04/`；新合同在原路径 supersede，source artifacts 不动；
  5. symbolic、AI2-THOR、3RScan/3DSSG 分别承担单元验证、可控具身实验和真实重扫外部有效性，不混为一个总平均分；
  6. 预测、区域绑定、主动取证、导航与 Top-K 暂不作为本轮论文贡献，历史细节只在 archive 中追溯。
- 未决执行门：HC-018 仍需明确选择“先做 12 个 hand-authored oracle smoke cases，还是先生成 AI2-THOR 数据”；在此之前允许完善设计、接口和模板，不宣称已授权开始正式训练。
- 备选方案：继续在完整闭环上堆叠模块；只做手写规则；或维持七项以上并列 soft loss。三者分别有归因困难、研究上限有限和重复监督的问题。
- 原因：固定上游后，才能用控制变量把效果归因到双时间、稀疏边界、来源证据和结构投影；归档后原位重写避免旧大杂烩继续污染活动入口。
- 影响：D-023 的具体候选模型被本方案 supersede；`README/EXECUTE/docs/01–05` 与活动实验包将原位重写；尚未实现、训练或验证。
- 是否接触 test 信息：否；没有正式 test 数据、阈值或模型选择。
- 验证方式：设计审计检查只有一个活动实验合同且 archive 可恢复；执行顺序待 HC-018 后再冻结。

## D-025 — 收缩 Human Confirmation 并把 criteria 嵌入实验设计

- 日期：2026-09-04
- 状态：accepted（信息架构与文档重构）。
- 用户确认：Human Confirmation 保持当前细粒度，但活动目录只留下当前 ESGBU 版本有关的内容；CRITERIA 的解释不仅独立存在，还要以纵向表格列进入实验设计和需要人工决断的 HC；完成后明确项目阅读入口、流程入口和起步步骤。
- 决策：
  1. 活动 HC 保留 HC-002/003/004/005/013/015/016/017/018/019，分别覆盖事实/关系存储、依赖闭包、负证据、等价事务、总评价、有效时间、提交门、基线公平、首批数据和任务代价；
  2. HC-001/006–012/014 从活动目录移除，原文件保存在 `archive/pre_d025_hc_criteria_integration_2026-09-04/`；它们不再阻塞 posterior-only 当前版本；
  3. `CRITERIA.md` 继续作为 C1–C15 的唯一公式和术语字典；场景、数据、基线、协议、消融、case template 与每个现行 HC 都增加“criterion / 本处含义 / 计算或判定 / 数字例子 / 人工选择”列；
  4. 嵌入列可以摘录解释，但不得产生第二套公式、阈值或状态；如有冲突，以 `CRITERIA.md` 和 `DECISIONS.md` 为准；
  5. 项目阅读顺序固定为 README → 01研究合同 → 实验包README/PROBLEM → CRITERIA；执行顺序固定为 EXECUTE → 03 pilot → PROTOCOL → 当前 HC。
- 原因：只引用独立指标字典会造成场景、基线和阶段设计来回跳转；保留全部旧 HC 又会让非核心闭环问题继续看似阻塞当前主线。
- 影响：建立 D-025 前 39 文件快照；重写 Human Confirmation 入口与十个现行工作表；移除九个非当前 HC 的活动副本；实验设计文件加入 criteria 纵列；不改变任何尚未回答的 HC 状态。
- 是否接触 test 信息：否；仍未实现、训练或查看正式 test。
- 验证方式：活动 HC 文件集合与决策表完全一致；实验设计每个关键行能就地读到判据含义和数字例子；本地链接、JSON/YAML 可用范围和旧文件归档均检查。

## D-026 — 第一批验证采用 hand-authored oracle smoke 路线

- 日期：2026-09-04
- 状态：accepted（HC-018/Q01.1；HC-018 其余子项仍 pending）。
- 用户确认：接受方案 A，由实验对接人按已展示的完整案例精细度制作第一批人工 oracle cases；用户负责不可替代的世界语义判断，不负责填写 schema、指标公式或测试代码。
- 决策：
  1. 第一批验证先使用 hand-authored structured cases，不从 AI2-THOR-first 开始；
  2. 每个 case 覆盖一个主要困难，并包含 prior graph、按到达顺序的 evidence、source/observed/received/visibility/confidence、oracle edit、affected/protected facts、valid time、direct evidence set、task delta 和 forbidden outputs；
  3. 每个 oracle case 派生至少三个单因素 deliberate corruptions，用来检查评价器能否识别操作、边界、时间或证据错误；
  4. 人工案例只用于冻结语义和自测判尺，不称为模型验证、正式 benchmark test 或具身泛化证据；
  5. symbolic 与 AI2-THOR 在该判尺通过后接入，3RScan/3DSSG 仍只作后续外部有效性轨。
- 尚未决定：Q01.2 首批规模选12还是直接36；oracle/corruption 的硬通过门；第一阶段 required/not-applicable criteria；时间与资源上限。
- 备选方案：AI2-THOR-first 和最小并行方案不作为第一批路线；若后续新证据要求改变顺序，必须追加新决策。
- 原因：先把 updater 的双时间、负证据、冲突、最小闭包、protected facts、有效时间、证据归因和任务边界转成可人工核验的判题单元，降低 simulator adapter、visibility 和 evaluator 错误相互混淆的风险。
- 影响：解除“hand-authored 还是 AI2-THOR-first”的路线阻塞，队首移动到 Q01.2；在规模和后续 oracle 语义冻结前，仍不启动正式训练或生成正式 test。
- 是否接触 test 信息：否；打样只使用 development 语义，没有生成、查看或选择正式 test。
- 验证方式：检查活动队列只把 Q01.2 标为 WAITING_USER；所有新 case/run 模板引用 D-026；首批案例必须可追溯到最终接受的 HC/D IDs。

## D-027 — 先做12个代表案例，再扩为36个语义案例

- 日期：2026-09-04
- 状态：accepted（HC-018/Q01.2；HC-018 通过门等子项仍 pending）。
- 用户确认：先做截图一所示的12个小案例，每个案例增加3个故意错误形成48个 evaluator inputs；完成后再做截图二所示的 positive/no-change control/counterfactual 扩展。
- 决策：
  1. 阶段 T0a 对 S00–S11 每类制作1个代表性 oracle case，共12个语义案例；
  2. 每个 oracle case 配3个单因素 deliberate corruptions，因此 T0a 为 `12×(1+3)=48` 个评价器输入；
  3. T0a 判尺稳定后进入 T0b，把每个 family 扩为 positive、no-change control、counterfactual 三种语义案例，总计36个；
  4. T0b 的36个包含并复用 T0a 中语义相符的12个，通常新增24个，而不是在已有12个之外再造36个重复案例；
  5. T0b 每个语义案例仍配3个单因素 deliberate corruptions，总计 `36×(1+3)=144` 个评价器输入；
  6. deliberate corruption 是对一个 oracle output 的单轴破坏，不与 positive/control/counterfactual 三类语义案例混称。
- 尚未决定：Q01.3 是要求12/12 oracle 与36/36 corruptions 全部正确分类，还是允许非关键失败；后续还需决定第一阶段 required criteria 和资源上限。
- 原因：T0a 用较低返工成本先验证语义与判尺；T0b 再用成对控制和反事实排除方法只记住表面模式，同时保留第一阶段投资。
- 影响：首批案例规模不再未决；允许按12→总计36的顺序规划 fixture，但在 Q01.3 和相关语义 HC 冻结前仍只可生成 draft，不称 ground truth 或正式 benchmark。
- 是否接触 test 信息：否；两阶段均属于 development fixture 设计。
- 验证方式：manifest 分别报告 `semantic_cases=12, evaluator_inputs=48` 与 `semantic_cases=36, evaluator_inputs=144`；禁止把两阶段误报为48个不同语义案例。

## D-028 — T0a 采用严格 evaluator 通过门

- 日期：2026-09-04
- 状态：accepted（HC-018/Q01.3；HC-018 criteria/资源子项仍 pending）。
- 用户确认：选择方案 A，人工可验证的小案例上不允许评价器带错进入下一阶段。
- 决策：
  1. T0a 的12个 oracle outputs 必须 `12/12` 被 evaluator 接受；
  2. 36个单因素 deliberate corruptions 必须 `36/36` 被拒绝；
  3. 每个 corruption 的报告必须包含预注册的 primary failure code；允许同时报告由该错误引起的其他连带错误，但不能漏掉主错误；
  4. 任何 crash、silent skip、未计入分母、错误地把 N/A 当0分或成功，都视为未通过；
  5. 任一失败先分类为 case ambiguity、schema omission、evaluator defect 或 corruption-not-isolated，修复后完整重跑48个输入；
  6. 无法机械消解的世界语义重新作为单项人工决策退回，不通过降低门槛掩盖。
- 备选方案：允许11/12 oracle或34/36 corruption；或只要求事务接受/拒绝正确、放宽错误分类。两者均未采用。
- 原因：该阶段评价的是确定性判尺而非含噪模型；若小型人工 oracle 上不能100%工作，后续模型百分比没有可信解释。
- 影响：Q01 队首移动到 Q01.4（第一阶段 required/not-applicable criteria）；T0a 未过严格门不得扩展 T0b、运行性能基线或启动训练。
- 是否接触 test 信息：否；通过门只作用于 development fixtures。
- 验证方式：保存 `oracle_accepted=12/12`、`corruptions_rejected=36/36`、`primary_failure_code_hit=36/36` 和 `unaccounted_inputs=0/48` 的原始计数及逐例日志。

## D-029 — T0a criteria 按适用性分层

- 日期：2026-09-04
- 状态：accepted（HC-018/Q01.4；HC-018 资源子项仍 pending）。
- 用户确认：选择方案 A；能由12个 hand-authored cases 客观计算的 criterion 必须计算，需要模型概率、证据干预或足够样本量的项目明确记 N/A，不强造数字。
- 决策：
  1. T0a 对有对应标签和非零定义分母的案例必须计算 C1–C10、C13 和 C14 原始分项；
  2. C1 保存每类 TP/FP/FN 与已覆盖类别；若五种 edit classes 未全部出现，完整 five-class macro-F1 记 N/A，不用“只平均出现类别”冒充完整值；
  3. C3/C6 等遇到无必要编辑或无写操作的零分母案例，保存 raw counts 并记 N/A，不记0分或100%；
  4. C8 只在 exact-time label 且有时间预测时计算，C9 只在 interval label 时计算；每个 N/A 必须保存机器可读原因且排除出聚合分母；
  5. C11 evidence intervention 与 C12 commit calibration 在 T0a 无可运行概率模型/足够 cohort 时记 N/A；
  6. C14 先必须报告 wrong dispatch、missed invalidation、collateral recompute 三项 raw counts/rates，合成 cost 在 HC-019 前记 N/A；
  7. C15 在 T0a 只要求 edited-fact、visited-edge、latency/memory 字段能记录，不设置效率性能门，也不据此主张高效；
  8. 该分层只治理 T0a 判尺自测，不替代 HC-013 对正式主指标、阈值和 publication gates 的后续决定。
- 备选方案：强制 C1–C15 全部产出数字；或只实现 C2/C5/C13。前者会制造无意义指标，后者会延迟暴露依赖、时间和证据 evaluator 错误，均未采用。
- 原因：区分“评价接口可验证”和“已有足够数据产生有意义统计”，避免把 N/A 当零分或用微型样本伪装校准/效率结论。
- 影响：run/case contract 增加 applicability 与 N/A reason；Q01 队首移动到 Q01.5 资源上限；正式主指标与 hard gates 继续由 HC-013 冻结。
- 是否接触 test 信息：否；criteria 分层在生成正式 test 前确定。
- 验证方式：12个案例汇总必须列出每个 C-ID 的 `required_when_applicable/interface_only/not_applicable` 状态、raw numerator/denominator、N/A reason 和聚合排除记录。

## D-030 — 精益资源上限与 CPU/GPU 分工

- 日期：2026-09-04
- 状态：accepted（完成 HC-018/Q01）。
- 用户确认：选择精益方案 A，但要求尽量加快；允许使用已安装的 CUDA，设备为 RTX 4070 Laptop。
- 环境实测：`NVIDIA GeForce RTX 4070 Laptop GPU`，显存8188 MiB，驱动581.42；Python 3.12.10；PyTorch 2.11.0+cu126；`torch.cuda.is_available()=True`；PyTorch CUDA runtime 12.6。`nvcc` 未在 PATH，但当前 PyTorch 运行与训练不依赖本机 nvcc。
- 决策：
  1. T0a 保留40个专注工程小时的硬上限，但这是停止线而不是计划耗时；优先自动生成 corruption、复用 schema 和参数化测试，并在累计约24小时仍未接近严格门时提前汇报；
  2. T0a 的48个小型结构化输入默认使用 CPU；JSON/YAML 校验、分支规则、图事务和单元测试不为“使用显卡”而迁移到 GPU；
  3. 若 T0a 出现可批处理张量瓶颈，只有端到端微基准显示实际加速后才切 CUDA，不以单算子理论速度判断；
  4. 后续 GRU/Transformer/HGT/ESGBU 训练默认使用 `cuda:0`，8 GB 显存通过小模型、mixed precision、梯度累积和逐方法训练控制；
  5. T0a 不下载外部数据、不启动训练、不制作额外界面；Git 内小 fixture 目标小于1 GB，用户人工复核预算约2–3小时；
  6. 达到40小时仍未通过 D-028 时停止，不降低严格门；报告 case ambiguity/schema/executor/evaluator 各自耗时和阻塞，再由用户决定继续或缩范围。
- 备选方案：为T0a强制GPU化；或把预算扩大到80小时。前者对48个小对象可能因启动与传输开销更慢，后者会推迟学习必要性验证，均未采用。
- 原因：GPU应投入矩阵计算密集的学习阶段；T0a 的主要瓶颈是语义、数据契约和确定性分支正确性。加速来自缩小范围、代码生成与自动回归，而不是设备标签。
- 影响：HC-018/Q01 完成，队首转为 HC-002/Q02；无需安装完整 CUDA toolkit 即可开始后续 PyTorch 训练，但正式训练前仍需保存环境锁和显存基准。
- 是否接触 test 信息：否；硬件检查与 development 计划未生成或查看 test。
- 验证方式：T0a 工时/失败分类写入执行日志；训练前再次记录 `nvidia-smi`、PyTorch/CUDA版本、device name 和最小 CUDA tensor smoke test。

## D-031 — Schema-conditioned predicate 泛化作为次级机制

- 日期：2026-09-04
- 状态：accepted（HC-002/Q02.1；具体 stored/derived 名单仍 pending）。
- 用户确认：选择方案 B，希望模型具有可测量的泛化能力并以强 AI/机器人 venue 为质量目标，但不把项目重新扩成任意自然语言开放世界。
- 决策：
  1. 核心任务仍是乱序、不完整、冲突证据下的稀疏、时态、可追溯 belief revision；predicate 泛化是共享更新机制和次级实验，不替代 `Delta G/M/tau/Z` 母命题；
  2. 模型条件扩展为 `q_phi(Delta G_t,M_t,tau_t,Z_t | G_{t-1},E_{<=t},Sigma)`，其中 `Sigma` 是 predicate registry/schema；
  3. registry 至少描述 storage policy、arity、value type、symmetry、mutual exclusion、reference frame、temporal policy、dependency policy 与 observability；精确枚举由 Q02.2/Q02后续子项冻结；
  4. updater 使用共享 schema encoder 与共享编辑头，不以每个 predicate 专属分类头作为主方法；predicate-ID-only 保留为消融；
  5. 主要泛化仍是 unseen room/entity composition/delay/conflict/graph size/dependency depth；registered-but-unseen predicate 作为次级 held-out split，结果单列；
  6. 不主张任意自然语言谓词、开放词汇本体发现或 VLM grounding；新增谓词必须先提供机器可读 schema；
  7. 若 held-out predicate 不优于 ID-only/structure-agnostic 对照，则删除 predicate-generalization claim，不据此否定核心后验修订结果。
- 备选方案：固定闭集谓词只做场景泛化；或直接做任意自然语言开放谓词。前者研究上限较低，后者引入语言 grounding 与 ontology alignment，均未采用为当前方案。
- 原因：泛化应来自共享的修订算法和结构条件，而不是把更多关系名塞进训练集合；次级定位允许该机制被独立反证。
- 影响：研究合同、模型和数据 split 增加 `Sigma` 与 held-out registered-predicate 轴；Q02 队首移动到 Q02.2 核心 stored/derived 名单；不改变 Q01 的 T0a 路线和资源门。
- 是否接触 test 信息：否；held-out 规则在生成测试数据前定义。
- 验证方式：同一模型权重在不改输出头的情况下运行 held-out registered predicates；报告各 C1–C15 适用指标、相对 ID drop 和 ID-only/schema-ablated 对照。

## 新决策模板

```text
## D-XXX — 标题

- 日期：YYYY-MM-DD
- 状态：proposed / accepted / superseded / rejected
- 背景：
- 决策：
- 备选方案：
- 原因：
- 影响：
- 是否接触 test 信息：
- 验证方式：
```
