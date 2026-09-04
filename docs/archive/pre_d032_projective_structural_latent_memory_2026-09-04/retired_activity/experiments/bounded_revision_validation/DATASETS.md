# 数据集与生成合同

三条数据轨分工明确，不合并成单一平均分。

## T0：Hand-authored transaction fixtures

用途：验证 schema、executor、metrics 和每个 baseline 是否按预期失败。D-026/D-027 已固定先做12个代表性语义案例并各配3个 deliberate corruptions，共48个评价器输入；判尺稳定后扩为总计36个 positive/control/counterfactual 语义案例及144个评价器输入。每例包含旧图、事件流、oracle transaction、affected/protected 集、valid-time label、evidence set 和 task delta。

它不是训练规模数据，也不能证明泛化。D-028 要求 T0a 达到 oracle `12/12`、corruption rejection `36/36`、primary failure code hit `36/36` 和漏计 `0/48`；D-029 要求 C1–C10/C13/C14 适用时必算、C15只验接口、C11/C12明确N/A。

## T1：Symbolic event-stream generator

用途：控制延迟、乱序、来源可靠性、负证据可见率、冲突、依赖深度和图规模；做快速训练、消融和反事实检查。

候选初始预算：30k train / 5k validation / 5k ID-test / 每个 OOD 轴 5k。该数字未冻结，必须在 test 生成前由 validation pilot 确定。

生成器保存 scenario seed、factor vector、generator version、oracle state trajectory 和所有拒绝样本。train/validation/test 不共享场景 seed、房间模板或实体组合。

D-031 增加次级 registered-but-unseen predicate split：训练与测试均获得机器可读 `Σ`，但测试 predicate identity 不进入训练；主模型不能为其新增专属输出头。该结果与 unseen room、delay、conflict、graph size 分列报告。任意自然语言开放谓词不在本数据合同内。

## T2：AI2-THOR 可控具身轨

定位：主要可控具身 benchmark，而不是文档里的装饰性例子。

利用 Rearrangement/可交互室内场景脚本化移动物体、开关门柜、遮挡和机器人视点，保存 simulator state、RGB-D/pose、visibility、event time 与接收队列。`visible=false` 不自动等于 reliably absent；负证据充分性由覆盖率与可见性标签决定。

划分至少包括：

- unseen rooms；
- unseen object compositions；
- unseen delay distribution；
- unseen conflict/source reliability；
- unseen change frequency；
- unseen dependency depth。

主 updater 比较优先使用 oracle/frozen perception 两轨：oracle 轨回答 posterior 能力，frozen 轨回答对现实上游噪声的敏感性。

## T3：3RScan + 3DSSG 外部有效性轨

定位：真实室内环境多次重扫、固定实例和关系变化的外部测试。它通常只能提供两次扫描之间的变化区间，不能当作精确物理事件时间。

需要构造 scan-to-scan transaction：旧图、后续观测/图、实例匹配、关系变化、有效时间区间和可验证 evidence refs。缺少来源可靠性与消息延迟时，只评估可支持的子问题，不合成虚假“真实传感器延迟”。

3RScan/3DSSG 不用于调主阈值；若需要域适配，另立 validation scenes 并明确报告 zero-shot 与 adapted 两组。

## 统一样本字段

```yaml
case_id: ai2thor_floorplan1_ep004_t18
track: ai2thor_oracle
prior_graph_ref: graph_v17.json
events_ref: events_to_t18.jsonl
candidate_facts_ref: candidates_t18.json
oracle:
  edit_program_ref: edits_t18.json
  affected_facts: [f_cart_at_A, f_task_retrieve_A]
  protected_facts: [f_door2_open]
  valid_time: {kind: exact, value: 602.0}
  evidence_ids: [ev_203, ev_204]
factor_vector:
  delay_seconds: 366
  visibility: 0.91
  conflict_rate: 0.25
decision_ids: [D-024, D-025, D-026, D-027]
```

## 数据治理

- 保存原始下载来源、版本、许可、校验和与预处理命令；
- 大型数据不提交 Git；Git 只留 manifest、生成脚本和小 fixture；
- simulator state 可称 oracle，自动映射或人工弱标签不能自动称 ground truth；
- test 在 CRITERIA、阈值、提示、baseline 和 checkpoint 选择冻结后才解封。

参考入口：[AI2-THOR Rearrangement](https://ai2thor.allenai.org/rearrangement/)，[3RScan 官方仓库](https://github.com/WaldJohannaU/3RScan)。

## 数据轨验收 Criteria 纵列

| Track | 必须提供的 oracle/label | 就地 Criteria 含义 | 数字例子 | 不支持时怎么办 |
|---|---|---|---|---|
| T0 hand fixtures | 全部 `ΔG/M/τ/Z`、controls、task delta | 先验证C1–C15计算与错误分类 | 12例×(1 oracle+3 corruptions)=48 evaluator inputs | 不能训练，只修合同/判尺 |
| T1 symbolic | 完整state trajectory和因子向量 | 做C1–C15、单因素曲线和反事实 | delay取0/30/300/900秒；每OOD轴候选5k | 规则已近oracle则收缩学习主张 |
| T2 AI2-THOR oracle | simulator state、event time、visibility、receive queue | C1–C8/C10–C15 的可控具身证据 | event=602、arrival=968；C8按602评分 | oracle与frozen perception分轨 |
| T2 frozen perception | 同一episode的固定感知输出 | 测上游噪声敏感性，不重选candidate | candidate recall=.92须各方法共享 | 单独报上游失败，不归咎updater |
| T3 3RScan/3DSSG | scan-to-scan对象/关系变化和时间区间 | C1–C7/C9/C10/C14；不伪造delay | 100例coverage=91%、平均width=38s | 无来源/arrival标签的criterion记N/A |

`N/A` 不是0分；它表示数据轨无法支持该 claim。跨轨总平均禁止使用。
