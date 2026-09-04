# Project Instructions

本文件只约束 `embodied_spatial_memory`。D-032 后唯一活动主线是 **Projective Structural Latent Memory（PSLM，工作名）**：把视角相关的结构化视觉 latent 绑定到世界坐标中的持久节点，并用同一在线 transducer 处理绑定、节点出生、图扩充、动态隔离和版本化修订。

## 开始工作前

1. 读工作区根 `README.md`；
2. 读本项目 `README.md`、`EXECUTE.md` 和 `docs/DECISIONS.md`；
3. 按阶段读 `docs/01–05`；
4. 实验细节只以 `experiments/projective_structural_latent_memory/` 为活动合同；
5. `docs/archive/` 只作 provenance，不作现行要求。

## 文档治理

- `EXECUTE.md` 是唯一日常入口；活动顺序合同只有 `docs/01–05`；
- 任何时刻只允许一个活动实验合同，不从 archive 拼接平行蓝图；
- accepted 决策变化先追加 `docs/DECISIONS.md`，不得静默改写历史；
- 用户明确授权文档重构时，先做逐文件快照、迁移说明和验证清单；
- source artifacts、PDF、原型、人工标注来源和 `docs/source/full_technical_vision.txt` 不覆盖、不删除；
- 待人工问题只在 `DECISIONS.md` 的确认中心登记，细节由同名 `docs/human_confirmation/HC-XXX.md` 展开。

## 当前研究合同

每步输入为 RGB、depth、intrinsics、pose、时间、可选动作与冻结感知证据。系统先把 DINO 类 patch features 与表面、portal、对象、遮挡和透视线索组织为临时 `ObservationRegion`，再从持久世界记忆投影预期结构，最后学习：

\[
q_\theta(A_t,U_t\mid R_t,\hat R_t,S_{t-1},a_{t-1},\Sigma),
\qquad
S_t=\operatorname{Execute}(S_{t-1},A_t,U_t).
\]

- `R_t`：当前视角的 projective structural latent tokens；
- `\hat R_t`：由旧世界记忆、pose 与可选动作预测/投影的预期观测；
- `A_t`：`BIND / NEW / REACTIVATE / SPLIT / MERGE / UNRESOLVED` association；
- `U_t`：节点/边创建、强化、重连、失效、替换、隔离及其 scope/time/evidence；
- `S_t`：含 Local Chart、Place、persistent slot、transient track、关系、版本和 provenance 的世界状态；
- `Σ`：节点、关系、生命周期和执行约束 schema。

原 ESGBU 的 `Delta G/M/tau/Z` 只属于 `U_t` 的 revision 分支，不再代表完整方法。透视只组织 observation，不作为长期坐标；世界节点必须 pose-aware、geometry-aligned、versioned。

## 模型与执行器边界

- 冻结视觉/深度/pose 前端用于第一轮归因；结构 tokenizer、projective matching、binding、birth/revision controller 是候选学习对象；
- DINO latent 是表示底座，不是创新声明；VP、结构线和 near/mid/far 是可消融的观测线索，不是固定世界网格；
- action-conditioned predict-project 只预测结构 latent、visibility 与候选 frontier，不生成 RGB；
- deterministic executor 强制 ID 唯一、坐标系合法、版本无环、protected scope、原子提交和 provenance；
- 不允许模型绕过 executor 直接覆盖 confirmed world state；
- `occluded / out_of_fov / reliably_absent / unknown / removed` 必须区分。

## 实验约束

- 主比较固定 RGB/depth/pose 与基础感知，先隔离 memory transducer；强前端替换另作二因素实验；
- baseline 必须覆盖 image-patch memory、pose-warped feature map、object-slot memory、recent-window 3D fusion、hierarchical graph construction、full recomputation 与 oracle；
- 主表同时测 binding、错误 birth/merge、graph attachment、长期保持、动态污染、revision、预测、任务和效率；
- symbolic/hand-authored、AI2-THOR/Habitat、3RScan/ScanNet 类重扫、真实机器人分轨报告；自动映射不自动称 ground truth；
- train/validation/test 严格隔离；正式 run 保存配置、seed、数据/合同/code/model ID、原始输出、投影后输出、完整指标和失败；
- 大型数据、权重、checkpoint 和运行输出不提交 Git。

## 研究诚信

- 明确区分 proposed、accepted、implemented、validated；
- 不把 DINO/VP/节点/场景图/在线扩图等成熟组件单独宣称为创新；
- 不用导航成功率掩盖 identity switch、duplicate birth、false merge、latent contamination 或 collateral revision；
- 与 DINO-WM、ConceptFusion、ODIN、Hydra、Khronos、SuperMap 等工作重合时收缩 claim；
- 论文只主张实验支持到的贡献梯级。
