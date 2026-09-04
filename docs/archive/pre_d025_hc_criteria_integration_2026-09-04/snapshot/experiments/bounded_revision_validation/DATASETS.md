# 数据集与生成合同

三条数据轨分工明确，不合并成单一平均分。

## T0：Hand-authored transaction fixtures

用途：验证 schema、executor、metrics 和每个 baseline 是否按预期失败。初始 12 例，每例包含旧图、事件流、oracle transaction、affected/protected 集、valid-time label、evidence set 和 task delta。

它不是训练规模数据，也不能证明泛化。是否从 T0 开始仍由 HC-018 决断。

## T1：Symbolic event-stream generator

用途：控制延迟、乱序、来源可靠性、负证据可见率、冲突、依赖深度和图规模；做快速训练、消融和反事实检查。

候选初始预算：30k train / 5k validation / 5k ID-test / 每个 OOD 轴 5k。该数字未冻结，必须在 test 生成前由 validation pilot 确定。

生成器保存 scenario seed、factor vector、generator version、oracle state trajectory 和所有拒绝样本。train/validation/test 不共享场景 seed、房间模板或实体组合。

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
decision_ids: [D-024]
```

## 数据治理

- 保存原始下载来源、版本、许可、校验和与预处理命令；
- 大型数据不提交 Git；Git 只留 manifest、生成脚本和小 fixture；
- simulator state 可称 oracle，自动映射或人工弱标签不能自动称 ground truth；
- test 在 CRITERIA、阈值、提示、baseline 和 checkpoint 选择冻结后才解封。

参考入口：[AI2-THOR Rearrangement](https://ai2thor.allenai.org/rearrangement/)，[3RScan 官方仓库](https://github.com/WaldJohannaU/3RScan)。

