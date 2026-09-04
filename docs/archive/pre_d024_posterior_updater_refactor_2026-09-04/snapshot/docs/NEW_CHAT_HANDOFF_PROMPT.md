# 新对话可移植交接 Prompt

> 本文件只用于恢复上下文，不是执行入口、研究合同或人工确认清单。进入新对话后仍先读 `EXECUTE.md`。

```text
请继续处理项目：
D:\Users\28115\Desktop\SCI\projects\embodied_spatial_memory

开始前按顺序阅读：
1. 根目录 README.md 和项目 AGENTS.md；
2. EXECUTE.md，确认当前阶段和退出门；
3. 当前任务对应的 docs/01–05；
4. docs/DECISIONS.md；
5. 若涉及人工判题，读取 docs/human_confirmation/README.md 和对应 HC-XXX.md。

当前研究方向：
Action-Conditioned Structural Belief Expansion and Revision。
核心循环是：
旧世界信念 + 动作
→ 结构候选与预期观测
→ 新证据中的临时结构区域
→ region-to-world association 与受控 latent 写入
→ 确认 / 扩展 / 修订 / 保持 / 暂缓
→ 新版本世界信念
→ 主动取证或任务动作。

当前状态：
- D-017 世界模型方向已接受；
- D-019 唯一人工确认中心已接受；
- D-020 每个 HC 使用独立详细工作表已接受；
- D-021 将 Structural Observation Bridge 纳入 planned 方法已接受；
- D-022 已把唯一核心贡献假设收缩为 evidence-gated affected-subgraph posterior revision：新证据怎样改变 semantic status、topology 和 valid time，同时保护 control facts；预测、区域绑定、主动取证和 Top-K 分别只是前置、补证或下游；
- D-023 是 proposed 的 BEGR-Net 双时间 learned posterior 主线，不是 accepted；HC-018 仍决定是否允许 posterior-only 先行；
- HC-001～HC-018 仍为 pending，不得推断用户已经接受推荐值；posterior-only 直接相关项为 HC-001–005、HC-011、HC-013、HC-015–018，HC-014 保留给后续 region binding 集成；
- schema、executor、fixture 和实验尚未实现、尚未验证；
- 任何数值阈值只能用 validation 冻结，不得使用 test。

人工确认治理：
- docs/DECISIONS.md 是唯一状态和最终回答入口；
- docs/human_confirmation/HC-001.md～HC-014.md 是详细场景与判题工作表；
- 用户明确回答后才追加 D-XXX 并更新 HC；
- fixture/run manifest 必须保存 decision_ids。

请先用 git status 和只读检查确认工作区已有修改，不覆盖用户改动。
不要使用 docs/archive/ 作为现行合同。
不要把 planned 写成 implemented/validated。
请从 EXECUTE.md 当前任务继续，不另建平行蓝图、第二清单或第二实验合同。
```
