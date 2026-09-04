# Embodied Spatial Memory：Projective Structural Latent Memory

当前唯一问题：机器人如何把随相机视角不断变化的视觉 latent observation，转化为世界坐标中长期存在、可以在线扩充并在真实变化时安全修订的结构化空间记忆？

方法工作名：**Projective Structural Latent Memory（PSLM）**。投稿前必须检索名称冲突。

## 与 DINO-WM 的关系

DINO-WM 证明预训练 DINO patch features 可以作为动作条件预测和规划的 latent state，而不必重建 RGB。本项目不把“使用 DINO”当创新，而研究它没有直接解决的长期状态问题：

- observation-space patch 随视角移动，world node 应保持身份；
- 新视角既可能重见旧结构，也可能首次揭示新区域；
- 遮挡和出视野不应删除旧世界；真实搬迁又必须修订旧状态；
- 记忆必须受控增长，能回答节点为何创建、绑定、保持或修改。

一句话边界：**DINO-WM 预测未来 observation latent；PSLM 维护可投影、可增长、可修订的 world-centric structural latent state。**

## 核心闭环

```text
RGB / Depth / Pose / Action / Time
              ↓
Frozen visual features + geometry/structure cues
              ↓
Projective Structural Tokenizer
              ↓ R_t: view-dependent region tokens
Persistent World Memory S_(t-1)
              ↓ pose/action-conditioned predict-project
Expected Observation Rhat_t
              ↓ compare and bind
Association A_t
  BIND / NEW / REACTIVATE / SPLIT / MERGE / UNRESOLVED
              ↓
Memory Transaction U_t
  CREATE / REINFORCE / UPDATE / RELINK / RETRACT /
  REPLACE / PRESERVE / QUARANTINE
              ↓ deterministic executor
Expanded or revised World Memory S_t
```

形式化为：

\[
q_\theta(A_t,U_t\mid R_t,\hat R_t,S_{t-1},a_{t-1},\Sigma),
\qquad
S_t=\operatorname{Execute}(S_{t-1},A_t,U_t).
\]

## 表示层次

1. `World / Place graph`：全局连通关系、route history 与坐标；
2. `Local Structural Chart`：局部一致的走廊、房间、转角、portal 与 dominant directions；
3. `Persistent Slot / Transient Track`：surface、object、portal、occupancy 及生命周期；
4. `Projective Observation Region`：当前视图中的 surface/object/portal/occlusion region；
5. `Visual Latent Tokens`：DINO 类 patch features 在 region 内的分布或 bounded prototypes。

透视只负责组织当前 observation。Vanishing point、near/mid/far 与图像 polygon 不得成为长期 world ID。

## 真正候选创新

- **Predict-project**：旧世界记忆在给定位姿/动作下产生预期结构 latent 与 visibility，而不是每帧重建后丢弃；
- **Projective binding**：显式预测 observation region 到 persistent node 的绑定、复活、多解与拒绝；
- **Controlled graph growth**：未解释但跨帧一致的结构通过 candidate → confirmed 创建并附着到 Chart/Place；
- **Unified growth and revision**：同一 transducer 区分首次揭示、视角变化、遮挡、动态实体与真实世界改变；
- **Auditable transaction**：节点出生、关系扩充和后验修订均带 scope、valid time、evidence 和版本。

它不是什么：首次使用 DINO、首次使用 VP、首次建立 scene graph、首次在线增加节点、首次做动态地图，或靠更多 loss 获得创新。

## 唯一执行入口

先读 [`EXECUTE.md`](EXECUTE.md)，再按顺序读：

1. [`docs/01_research_contract.md`](docs/01_research_contract.md)
2. [`docs/02_scenario_wbs.md`](docs/02_scenario_wbs.md)
3. [`docs/03_pilot_protocol.md`](docs/03_pilot_protocol.md)
4. [`docs/04_training_plan.md`](docs/04_training_plan.md)
5. [`docs/05_formal_evaluation_and_paper.md`](docs/05_formal_evaluation_and_paper.md)

全部实验细节位于唯一活动包 [`experiments/projective_structural_latent_memory/`](experiments/projective_structural_latent_memory/README.md)。指标总字典为其中的 `CRITERIA.md`；机器接口见 `schemas/`。

## 第一篇论文的边界

主贡献限定为：结构 token、predict-project、region-to-world binding、candidate node birth、局部 graph expansion 与版本化 revision。第一轮固定 detector/depth/pose；完整导航、任意开放词汇、学习型全局 Chart split/merge、视频生成和多机器人协作不作为并列贡献。

action-conditioned prediction属于核心表示检查，但第一阶段只预测结构 latent、visibility 与 attachment candidate；导航/规划只作冻结 reader 的下游验证。

## 数据与证据轨

- hand-authored/symbolic：验证 schema、binding/growth/revision oracle 和反事实；
- AI2-THOR/Habitat：可控转弯、遮挡、首次揭示、搬迁与动作条件预测；
- 3RScan/ScanNet 类重扫：真实跨视角与场景变化外部测试；
- real robot：只有形成稳定模拟结果后再作为强期刊扩展。

不同轨分别报告，不拼接总平均分。

## 当前状态

- D-032：已接受新主线与文档 supersession；
- 当前 ESGBU posterior-only 活动方案：已完整归档到 [`pre_d032_projective_structural_latent_memory_2026-09-04`](docs/archive/pre_d032_projective_structural_latent_memory_2026-09-04/README.md)；
- schema：已有 v0.1 草案但尚未由 HC 冻结；模型、数据、executor/evaluator、训练和结果均未实现或未验证；
- 当前下一步：HC-020，冻结第一批可执行的 projective binding/growth/revision smoke 路线；
- 质量目标：先形成强机器人/具身论文证据；若要冲击通用 ML/AI 顶刊，必须证明跨 schema/跨环境的通用学习机制，而不只是系统集成。
