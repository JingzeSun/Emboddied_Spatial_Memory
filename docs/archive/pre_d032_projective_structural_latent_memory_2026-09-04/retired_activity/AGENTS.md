# Project Instructions

本文件只约束 `embodied_spatial_memory`。当前活动主线由 D-024 重构为证据感知的稀疏图后验修订，并由 D-025 固定 Human Confirmation 与 Criterion 的信息结构；旧完整闭环设计只从 archive 追溯。

## 开始工作前

1. 读工作区根 `README.md`；
2. 读本项目 `README.md`、`EXECUTE.md` 和 `docs/DECISIONS.md`；
3. 按阶段读 `docs/01–05`；
4. 实验细节只以 `experiments/bounded_revision_validation/` 为活动合同；
5. `docs/archive/` 只作 provenance，不作现行要求。

## 文档治理

- `EXECUTE.md` 是唯一日常入口；活动顺序合同只有 `docs/01–05`；
- 任何时刻只允许一个活动实验合同，不维护平行蓝图；
- accepted 决策变化先追加 `docs/DECISIONS.md`，不得改写历史决策；
- 用户明确授权文档重构时，允许原位 supersession，但必须先做逐文件快照、验证清单、写迁移说明，并保持 source artifacts 不动；
- 文档重构授权不自动等于接受尚未回答的实验执行 HC；
- 待人工问题只在 `DECISIONS.md` 的确认中心登记；细节由同名 `docs/human_confirmation/HC-XXX.md` 展开；
- 用户回答后追加 `D-XXX`，run manifest 与 fixture 保存实际 `decision_ids`；
- 原始提示、导师 notes、PDF、原型图、人工标注源和 `docs/source/full_technical_vision.txt` 不覆盖、不删除。

## 当前研究合同

学习目标为：

\[
q_\phi(\Delta G_t,M_t,\tau_t,Z_t\mid G_{t-1},E_{\le t},\Sigma).
\]

- `ΔG_t`：`KEEP/ASSERT/RETRACT/REPLACE/QUARANTINE`；
- `M_t`：受影响 seed mask；
- `τ_t`：事实有效时间点或区间；
- `Z_t`：直接支持本次修订的证据集合；
- `E_≤t`：含来源、event time、arrival time、visibility、confidence 和 group 的事件流。
- `Σ`：机器可读 predicate schema；主模型使用共享 schema encoder/编辑头，registered-but-unseen predicate 只作次级泛化。

主实验固定 perception、identity、pose、visibility、candidate retrieval 和 dependency input，只替换 updater。event/arrival 双时间、来源冲突、负证据充分性、typed dependency 与 protected facts 是受控因素。

任务、导航、动作预测、区域绑定、Top-K 和主动取证不是当前论文的并列贡献。若后续接入，只能作为上游固定输入或下游只读评估。

## 模型与执行器边界

- ESGBU 可学习时序证据编码、异构图传播、affected mask、编辑、时间与证据集合；
- 主 loss 与 `ΔG/M/τ/Z` 一一对应；state/preserve/constraint/task 默认作为评估，不堆叠重复 loss；
- deterministic executor 强制互斥、最小依赖闭包、protected facts、valid-time legality、atomic version 和 provenance；
- task 节点默认不能向 fact truth 反向传递；
- 不允许 LLM 或神经网络绕过 executor 直接写 confirmed graph；
- occluded、out-of-FOV、reliably absent、unknown location 和 removed 必须区分；unknown 不得虚构新位置。

## 实验约束

- `experiments/bounded_revision_validation/CRITERIA.md` 是统一判据定义；实验设计文件还必须在对应对象旁竖列写出适用 Criterion、局部含义、计算口径和数值例子；
- `docs/human_confirmation/` 活动区只保留当前后验修订版本仍需治理的确认项；旧确认项只从带日期归档追溯；
- 第一个可信里程碑是 evaluator + 经人工复核的 smoke fixtures，不等于方法验证；具体先后仍受 HC-018 管理；
- baselines 顺序：time/rule → Bayes/gate → MLP/GRU/Transformer → TGN/FullGraph-HGT → ESGBU → oracle；
- 主表共享 prior graph、events、candidate facts、dependency input 和 executor；native-system 比较单列；
- 参数匹配与 wall-clock 匹配都报告，不以更大 backbone 替代消融；
- symbolic、AI2-THOR、3RScan/3DSSG 分轨报告；AI2-THOR 的 simulator state 可称 oracle，自动映射不能自动称 ground truth；
- train/validation/test 严格隔离，test 不用于阈值、loss、提示、baseline 或 checkpoint 选择；
- 正式 run 保存配置、seed、data/split/contract hash、code/model ID、环境、原始/投影后预测、完整指标和失败；
- 大数据、权重、checkpoint 和运行输出不提交 Git。

## 研究诚信

- 明确区分 proposed、accepted、implemented、validated；
- 同时报漏改、多改、越界传播、错误证据、时间误差、投影拒绝和反例；
- 与成熟方法重合时收缩 claim，不用“结构化”“世界模型”自称代替审计；
- 论文只主张实验支持到的贡献梯级，不因目标期刊强而夸大结果。
