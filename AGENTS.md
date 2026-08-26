# Project Instructions

本文件约束后续在此工作区中进行的研究、代码和文档修改。

## 开始工作前

1. 阅读 `README.md`。
2. 阅读 `docs/source/full_technical_vision.txt`，不得用简化图替代其中的完整设想。
3. 阅读 `docs/02_method_spec.md` 和 `docs/03_experiment_contract.md`。
4. 检查 `docs/06_decision_log.md`，不要悄悄改变已经接受的研究决策。

## 方法约束

- 不得把系统简化成“透视切图 + DINOv2 + 数据库”。
- 明确区分 observation region、world slot 和 local structural chart。
- 不得把固定 Vanishing Point 当作世界坐标。
- 所有跨帧关联必须说明 pose/depth/geometry 的使用和坐标变换方向。
- 使用 optical flow 判断动态性时必须考虑 ego-motion compensation。
- 转弯是有效观测，不得用全局 `if turning: freeze memory` 处理。
- 静态/动态更新必须保留 confidence、visibility、pose reliability 和 provenance。
- 必须评估临时遮挡与真实持久变化，不能只展示“冻结记忆”带来的表面稳定性。

## 工程约束

- 原始 PDF、原型图和原始技术设想是 source artifacts，不覆盖、不删除。
- 大型数据、checkpoint 和运行输出不提交版本库。
- 每次正式实验保存配置、随机种子、数据版本、代码版本和完整指标。
- `src/` 中模块的输入输出应与 `schemas/` 和方法规范一致。
- 几何变换、slot 生命周期、遮挡更新和指标实现必须有测试。
- 文档以中文说明为主；公开 API、变量名和配置键使用清晰英文。

## 研究诚信

- 将“已实现”“已验证”“计划中”明确区分。
- 不把单目估计产生的深度或位姿称为 ground truth。
- 不使用测试场景调阈值。
- 对失败案例、位姿噪声和非 Manhattan 场景进行显式报告。
