# 项目推进清单

说明：每个阶段都包含“做什么、产物、验收”。不要因为后续模型更有趣而跳过前面的数据和基线合同。

## P0 — 工作区与研究资产（已完成）

- [x] 归档完整原始技术设想。
  - 做什么：把附件原文原样保存到 `docs/source/full_technical_vision.txt`。
  - 产物：可追溯的 source artifact。
  - 验收：源文件与工作区副本 SHA-256 一致。

- [x] 建立 README、项目规则和文档索引。
  - 做什么：说明研究问题、不可简化模块、阅读顺序和目录职责。
  - 产物：`README.md`、`AGENTS.md`、`docs/00_index.md`。
  - 验收：新成员能在十分钟内理解“observation 不是 memory”。

- [x] 建立研究、方法、实验和数据规范。
  - 做什么：把概念图转成坐标、slot、Chart、关联、更新、指标和数据契约。
  - 产物：`docs/01`–`04`。
  - 验收：核心模块都有输入、输出或待决定项，不只是一张流程图。

- [x] 建立文献索引和工程目录骨架。
  - 做什么：登记已有 PDF，创建 notes、config、schema、src、tests、outputs 等入口。
  - 产物：`literature/`、`configs/`、`schemas/` 及各目录 README。
  - 验收：原始 PDF 和图片未删除、未移动、未覆盖。

- [ ] 创建第一次版本控制提交。
  - 做什么：检查文件后创建 initial research-workspace commit。
  - 产物：可回退的基线版本。
  - 验收：工作树干净，提交不包含数据、模型权重或临时输出。

## P1 — 冻结论文问题（开始编码前）

- [ ] 确定论文主任务。
  - 做什么：在 `structure_query` 和 `lightweight_navigation` 中选择一个下游任务；memory robustness 保持主任务。
  - 产物：更新 D-006 和 `configs/mvp.yaml`。
  - 验收：一句话能说明主任务、输入、输出和成功指标。

- [ ] 确定方法名称和贡献声明。
  - 做什么：选择临时 acronym，写出不含“first”或无法验证表述的三条贡献。
  - 产物：更新 `README.md` 和 `docs/01_research_question.md`。
  - 验收：每条贡献都对应至少一个实验或消融。

- [ ] 完成 SpatialMem、AstraNav-Memory 和 MTU3D 精读。
  - 做什么：使用 `literature/notes/TEMPLATE.md` 回答表示、关联、更新、动态性和评测问题。
  - 产物：至少三份结构化 notes。
  - 验收：能明确说明本项目相对每篇工作的新增机制和必须比较的基线。

- [ ] 识别 `papers/p013.pdf`。
  - 做什么：人工打开并补全 title、authors、venue、URL 和 topic。
  - 产物：更新 `literature/library.csv`。
  - 验收：不存在 unknown/anonymous PDF 条目。

- [ ] 冻结坐标与传感器假设。
  - 做什么：确定 pose/depth 的训练、validation、test 来源，以及是否报告 oracle/estimated 两套结果。
  - 产物：更新 D-008、配置和 dataset spec。
  - 验收：任何 frame-to-world 公式都可由单元测试验证。

- [ ] 决定 slot latent state。
  - 做什么：先用 normalized EMA 做 baseline，再选择 bounded prototypes 或 mean/covariance 作为正式候选。
  - 产物：更新 D-007。
  - 验收：说明存储量、更新公式、重现检索和冲突处理。

## P2 — 数据可行性与 Pilot

- [ ] 核对候选数据集。
  - 做什么：逐个登记许可证、大小、RGB/depth/pose、动态 actor、scene mesh、任务协议和下载方式。
  - 产物：`docs/dataset_candidates.md`。
  - 验收：确定 controlled synthetic、public benchmark、real dynamic 三种角色的数据源。

- [ ] 实现 episode manifest 生成器。
  - 做什么：生成符合 `schemas/episode.schema.json` 的 manifest，不复制大型数据。
  - 产物：`scripts/prepare_data.*` 和 manifest 示例。
  - 验收：同一 counterfactual group 的轨迹、初始状态和 scene identity 一致。

- [ ] 实现 episode validator。
  - 做什么：检查 schema、文件存在、timestamp、pose matrix、intrinsics、split 泄漏和事件标签。
  - 产物：`scripts/validate_episode.*` 与测试。
  - 验收：故意构造的错误 episode 均能产生清晰失败信息。

- [ ] 构建首批 20 个 paired episodes。
  - 做什么：覆盖直走、原地转弯、边走边转、行人遮挡和真实持久变化。
  - 产物：pilot manifest、可视化和手工核验记录。
  - 验收：每个 persistent ID、visibility 和 change event 均经过人工抽检。

- [ ] 建立 split v0.1。
  - 做什么：按 scene family 划分 pilot/train/validation/test，并固定随机种子。
  - 产物：带 hash 的 split manifest。
  - 验收：counterfactual group 和同建筑录制不跨 split。

## P3 — 几何与弱基线

- [ ] 建立 Python 环境。
  - 做什么：根据 GPU/CUDA 决定 Python、PyTorch 和依赖版本，生成锁文件。
  - 产物：`pyproject.toml`/lockfile 或 `environment.yml`，以及安装说明。
  - 验收：全新环境可运行 schema test 和一个 RGB-D episode。

- [ ] 实现 geometry primitives。
  - 做什么：实现 SE(3)、backprojection、reprojection、pure-rotation homography 和视锥判断。
  - 产物：`src/geometry/`。
  - 验收：合成点和简单平面 round-trip 误差在数值容差内。

- [ ] 实现 ego-motion flow。
  - 做什么：根据 depth/pose/K 预测静态 flow，与 observed flow 形成 residual。
  - 产物：模块、可视化和单元测试。
  - 验收：静态合成场景 residual 接近零；动态体区域明显增大。

- [ ] 实现 DINO feature extraction/cache。
  - 做什么：冻结 backbone，记录模型标识、预处理、patch stride 和输出维度。
  - 产物：`src/perception/` 和 `scripts/extract_features.*`。
  - 验收：重复运行结果一致，cache 与数据 manifest 绑定。

- [ ] 实现 B0–B4。
  - 做什么：current frame、fixed patch、single-VP、pose-warped、world-slot EMA。
  - 产物：统一 baseline 接口和配置。
  - 验收：所有基线使用相同输入、数据切分和指标实现。

- [ ] 验证指标敏感性。
  - 做什么：人为制造 slot 覆盖、重复新建、漏更新和错误退休。
  - 产物：metric unit tests。
  - 验收：每类错误至少有一个指标按预期恶化。

## P4 — 完整方法 MVP

- [ ] 实现结构 observation regions。
  - 做什么：融合 line/plane/VP/depth cues，生成 polygon/mask、near/middle/far 和 latent pooling。
  - 产物：`src/regions/` 和逐帧可视化。
  - 验收：转弯时 region 可改变，但不直接改变 world slot ID。

- [ ] 实现 frame-to-world association。
  - 做什么：融合 geometry、reprojection、latent、semantic 和 temporal score，支持 split/merge。
  - 产物：`src/association/`。
  - 验收：遮挡重现和跨视角 IDF1 优于 nearest-image-patch 基线。

- [ ] 实现 world slot 与 provenance。
  - 做什么：按 schema 创建、更新、查询 slot，保存每次证据和 update weight。
  - 产物：`src/memory/`。
  - 验收：任何异常 slot 状态都可追溯到 episode/frame/region。

- [ ] 实现 dynamic evidence fusion。
  - 做什么：组合 residual flow、semantic/instance、depth occlusion 和 history。
  - 产物：可解释 baseline 与 learned candidate（可选）。
  - 验收：stationary pedestrian 不因 residual≈0 被直接写入 static memory。

- [ ] 实现 lifecycle 和 persistent change。
  - 做什么：完成 candidate/transient/persistent/changed/retired 转移与确认延迟。
  - 产物：状态机、配置和测试。
  - 验收：行人经过保持门 slot；椅子永久移动最终更新而不是永久冻结。

- [ ] 实现 Local Structural Charts。
  - 做什么：创建 Chart、region soft assignment、multi-Chart overlap 和 topology edge。
  - 产物：`src/charts/` 和 Chart graph 可视化。
  - 验收：转弯序列中 A/B overlap 连续，且相对关系可回溯到共同观测。

- [ ] 实现 soft update。
  - 做什么：使用 association、visibility、dynamic、pose 和 measurement confidence 计算 update weight。
  - 产物：更新模块和权重日志。
  - 验收：完全遮挡时不覆盖静态 slot；可靠重现时允许更新。

## P5 — 正式实验

- [ ] 冻结 experiment contract v1.0。
  - 做什么：确定阈值、指标实现、噪声等级、随机种子、正式数据规模和成功门槛。
  - 产物：带版本号的合同与配置。
  - 验收：之后的修改全部记录且不使用 test 调参。

- [ ] 跑主基线和完整方法。
  - 做什么：按 scene seed 运行 B0–B6，保存 per-episode 原始结果。
  - 产物：标准 `outputs/<run_id>/`。
  - 验收：任一汇总数字可追溯到配置和 episode。

- [ ] 跑核心消融。
  - 做什么：依次移除 structure、pose、ego compensation、lifecycle、Chart overlap 和 soft update。
  - 产物：消融表和置信区间。
  - 验收：每项声称的贡献都有独立证据。

- [ ] 跑鲁棒性和效率实验。
  - 做什么：pose/depth noise、非 Manhattan 场景、长时序、内存、时延和显存。
  - 产物：鲁棒性曲线、效率表和失败案例。
  - 验收：不仅报告 oracle sensor 结果。

- [ ] 接入强基线。
  - 做什么：至少覆盖 image-centric memory、3D anchor memory、semantic-geometric map。
  - 产物：复现说明和公平性表格。
  - 验收：统一输入和传感器假设；无法统一时明确披露。

- [ ] 运行一个下游任务。
  - 做什么：固定 memory 后接 structure query 或轻量导航消费者。
  - 产物：次指标结果。
  - 验收：证明更稳定的 memory 带来可测任务收益，而不是只优化内部相似度。

## P6 — 论文与发布

- [ ] 冻结论文故事线。
  - 做什么：围绕 viewpoint alignment、contamination resistance、persistent change 三个问题组织，不按模块流水账写作。
  - 产物：一页 paper outline。
  - 验收：每个 section 对应研究问题或实验结论。

- [ ] 生成完整架构图。
  - 做什么：保留 pose、SE(3)、ego compensation、world directions、Charts、association、双记忆和 soft update。
  - 产物：可编辑源文件和导出图。
  - 验收：不退化成“透视切图 + DINO + database”。

- [ ] 整理定量和定性结果。
  - 做什么：主表、消融、鲁棒性、效率、turning/occlusion/true-change 可视化。
  - 产物：可由脚本生成的 figures/tables。
  - 验收：所有图表标注 run ID 和生成命令。

- [ ] 整理失败案例与限制。
  - 做什么：报告 pose drift、depth failure、stationary actor、相似结构、非 Manhattan 和错误 Chart。
  - 产物：limitations 和 failure appendix。
  - 验收：说明方法何时失败以及未来修复方向。

- [ ] 发布前审计。
  - 做什么：检查许可证、隐私、数据来源、模型权重、随机种子、README、安装和复现命令。
  - 产物：release checklist、license、citation 和匿名版本。
  - 验收：新环境能复现至少一条主结果和一张主图。

## 每周最小节奏

每周结束前回答并记录：

1. 本周关闭了哪个可验证问题？
2. 新结果支持还是反驳哪个假设？
3. 最大的不确定性是什么？
4. 下周最小可交付物是什么？
5. 是否改变了数据、指标或实验合同？若改变，为什么？
