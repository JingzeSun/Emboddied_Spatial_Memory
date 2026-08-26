# Pose-Aware Structure-Aligned Latent Memory

面向动态室内具身环境的几何对齐、位姿感知、长期结构化视觉空间记忆研究工作区。

## 核心研究问题

> 基于几何结构和机器人姿态对齐的 latent memory，能否在视角变化、机器人转弯、动态遮挡和临时干扰下，比图像中心的 patch memory 更稳定地保持长期空间知识，同时正确响应真实的持久环境变化？

本项目不以恢复干净 RGB 或保存完整视频为目标。透视结构只组织当前观测；真正长期保存的是世界坐标中的结构、latent、拓扑、不确定性和时间状态。

## 拟议研究升级：新帧驱动的动态语境修正

项目正在评估是否把主问题从“动态条件下保护长期静态记忆”升级为：

> 根据新观测与旧空间信念之间的结构化差异，判断哪些实体、关系、事件、Chart 和 Place 应被保留、更新、重连、分裂、合并或隔离，并形成与当前位置和任务相关的新语境。

核心映射不是 `New Frame -> New Context`，而是：

```text
(Previous Scene Belief + Action/Pose + New Observation) -> Context Delta
```

该方向当前状态为 `proposed`，尚未实现或验证，也尚未替代现有实验合同。完整定义、与抗噪声的区别、候选方法和评测见 [`docs/08_dynamic_context_revision.md`](docs/08_dynamic_context_revision.md)；现有路线与新方向的冲突、优先级、技术流程、实验拆解和人工决策见 [`docs/09_integrated_direction_plan.md`](docs/09_integrated_direction_plan.md)。

当前建议把 **Pose-aware Structured Innovation + Affected-Subgraph Revision** 作为候选核心算法，把抗污染、生命周期、版本记录和 provenance 作为使核心算法成立的必要支撑，而不是并列包装为多个主创新。这个优先级只有在 D-008 接受并通过 revision pilot 后才替代当前正式合同。

## 方法主线

```text
RGB / Depth / Pose / Optical Flow
                 │
                 ├── Ego-motion compensation ──> residual dynamic evidence
                 │
                 └── Geometry + structural cues + DINO features
                                      │
                            observation-space regions
                                      │
                            frame-to-world association
                                      │
             world structural memory + local structural charts
                         ├── persistent/static slots
                         └── dynamic/transient slots
                                      │
                      navigation / query / spatial reasoning
```

## 不可丢失的设计约束

1. Observation Space 与 World Memory 必须分离。
2. Camera pose、rotation 和完整 SE(3) 对齐必须显式存在。
3. Optical flow 必须先补偿 ego-motion，才能作为动态证据。
4. 长期保存 world structural directions，而不是固定图像消失点。
5. 复杂环境使用 Local Structural Charts，并允许转弯时多 Chart overlap。
6. 当前 region 必须通过 Frame-to-World Association 关联到 persistent slot。
7. Static 与 Dynamic memory 使用带不确定性的 soft update，而不是全局硬开关。
8. 评测必须同时覆盖 viewpoint、turning、occlusion 和 persistent change。

完整原始技术设想见 [`docs/source/full_technical_vision.txt`](docs/source/full_technical_vision.txt)。

## 推荐阅读顺序

1. [`CHECKLIST.md`](CHECKLIST.md)：从研究冻结到论文写作的逐步清单。
2. [`docs/01_research_question.md`](docs/01_research_question.md)：问题、假设、范围和贡献边界。
3. [`docs/02_method_spec.md`](docs/02_method_spec.md)：表示、关联、Chart、动态判断和更新规则。
4. [`docs/03_experiment_contract.md`](docs/03_experiment_contract.md)：基线、指标、消融和成功标准。
5. [`docs/04_dataset_spec.md`](docs/04_dataset_spec.md)：反事实配对 episode 和标注要求。
6. [`docs/05_related_work_matrix.md`](docs/05_related_work_matrix.md)：已有工作与本项目的差异；同行评审证据和引用准入见 [`literature/peer_review_audit.md`](literature/peer_review_audit.md)。
7. [`docs/06_decision_log.md`](docs/06_decision_log.md)：已经接受和仍待决定的研究选择。
8. [`docs/07_long_short_term_memory_block.md`](docs/07_long_short_term_memory_block.md)：地点级长短期记忆与动态工作区。
9. [`docs/08_dynamic_context_revision.md`](docs/08_dynamic_context_revision.md)：拟议的 SceneBelief、ActiveContext 与局部语境修正方法。
10. [`docs/09_integrated_direction_plan.md`](docs/09_integrated_direction_plan.md)：方向整合、优先级、技术栈、哨兵场景、实验和待确认问题。

## 工作区结构

```text
embodied_spatial_memory/
├── docs/                 研究定义、方法、实验与数据规范
├── literature/           文献索引、同行评审审计与精读笔记
├── papers/               本地论文 PDF（不提交 Git）
├── papers_detail/        本地重点论文 PDF（不提交 Git）
├── prototype/            原型图和数据集方案
├── configs/              可复现实验配置
├── schemas/              episode 与 memory slot 数据契约
├── data/                 数据入口说明，不提交大文件
├── src/                  后续实现模块
├── scripts/              数据和实验入口脚本
├── tests/                几何、关联、更新和指标测试
└── outputs/              实验输出说明，不提交运行产物
```

## 当前阶段

当前处于 **research contract / pre-implementation** 阶段。下一决策门是确认 D-008 的主方向、MVP 图范围和 delta 语义；随后先做 revision pilot，再决定是否迁移正式 schema、配置和实验合同。

旧 MVP 的最低完成条件仍是：在同场景、同轨迹的 clean/dynamic 配对 episode 上，完整方法相对 pose-warped 和普通 EMA 基线显著降低静态记忆污染，同时不牺牲对真实持久变化的响应能力。候选 revision MVP 还必须证明：必要修改完整、无关子图保持稳定、传播范围正确，并且不是靠全图重算取得结果。
