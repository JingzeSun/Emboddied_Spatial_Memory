# 创新命题与证伪条件

状态：研究假设，不是已验证贡献。

## 1. 拥挤的已有组件

以下单项均不能独立构成主创新：冻结视觉 latent、透视/消失点结构、pose/depth 投影、object/region graph、persistent slot、EMA 更新、open-vocabulary map、dynamic scene graph、action-conditioned latent prediction、置信度门控或版本化事实。

因此论文不能写成“把 DINO feature 放进节点并更新”。真正需要验证的组合命题是：

> 将世界记忆主动投影为预期结构观测，在 observation-region 与 persistent world-node 之间进行可拒识、可一对多/多对一的绑定，并把 node birth、局部 attachment 与带证据/时间/作用域的 revision 统一为可执行 transaction；该闭环在长序列中同时提高身份稳定、受控扩张和环境变化后的正确修订。

## 2. 贡献阶梯

| Level | 必要证据 | 允许主张 |
|---|---|---|
| N0 | schema + fixtures | 可执行研究合同 |
| N1 | 胜过图像/规则基线 | 结构记忆原型有效 |
| N2 | 学习模块胜过公平规则与 pair matcher | 学习式绑定/transaction 有必要 |
| N3 | project-bind-transact 各模块有独立增益 | 方法级组合创新 |
| N4 | 多场景、长 rollout、真实回放与下游收益 | 强机器人/视觉贡献 |
| N5 | 跨环境/本体泛化或一般性理论，并胜强外部系统 | 顶级 ML/AI 期刊候选 |

项目当前处于 N0 前：合同已重写，但 evaluator、实现和结果都未完成。

## 3. 核心 falsifier

| 假设 | 证伪结果 | 后续降格 |
|---|---|---|
| H1 结构 tokenizer 比普通 patch 更适合世界绑定 | 换成 patch 后 B/G 不下降 | tokenizer 仅工程选择 |
| H2 `PredictProject` 提供 world-model 信息 | 去掉后 B/G/R/P 不下降 | 不再称 world model |
| H3 persistent nodes 优于短窗融合 | L2 在长序列同等或更好 | 长期记忆主张失败 |
| H4 learned association 必要 | R2/R4 与 M0 相当 | 使用规则系统并缩小贡献 |
| H5 unified transaction 有益 | 独立 heads 或直接覆写同等且更稳 | transaction 贡献失败 |
| H6 delayed birth 控制扩张 | G4 改善但 G1 recall 严重崩溃 | 重新定义 birth policy |
| H7 revision 不破坏无关事实 | R3 collateral edit 不优于旧 ESGBU | 统一循环未带来控制性 |
| H8 memory 带来行动价值 | T1 无收益 | 只能主张表示/地图质量 |

## 4. 最危险的替代解释

- 收益来自更强 backbone 或更高分辨率，而非世界记忆。
- pose/depth 几乎直接解出匹配，learned model 只拟合阈值。
- 数据生成器泄漏 node ID、坐标或渲染器状态。
- `UNRESOLVED` 过多导致精度虚高、coverage 极低。
- 每次新建 node 规避 false merge，造成无界增长。
- offline full recomputation 被包装成 online memory。
- 下游任务直接读取 oracle 字段或参与写入，形成评测泄漏。

## 5. 与近邻工作的边界

- 相对 DINO-WM：关注长期、显式、可修订的世界节点；但必须证明 action-conditioned 预测确实有独立作用。
- 相对 3D feature fusion / ODIN / ConceptFusion：主张不是开放词汇特征，而是 region-to-world binding 与受控 birth/revision。
- 相对 Hydra / Khronos / SuperMap：主张不是“又一个场景图”，而是从投影结构 latent 到可执行 transaction 的学习闭环。

若公开工作已完整覆盖该闭环，应修改命题并在决策日志记录，而不是通过改名维持新颖性。

