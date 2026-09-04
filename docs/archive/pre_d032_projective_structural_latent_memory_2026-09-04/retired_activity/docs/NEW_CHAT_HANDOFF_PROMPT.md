# 新对话交接 Prompt

请先读本项目 `AGENTS.md`、`README.md`、`EXECUTE.md`、`docs/DECISIONS.md`，然后只按 `docs/01–05` 和 `experiments/bounded_revision_validation/` 工作。

当前活动问题是：

\[
q_\phi(\Delta G_t,M_t,\tau_t,Z_t\mid G_{t-1},E_{\le t})
\]

即在异步、迟到、部分可见和冲突具身证据下，学习稀疏编辑程序、affected mask、有效时间和直接 evidence set，由 deterministic executor 保护无关事实和结构一致性。方法工作名 ESGBU。

状态：D-024/D-025 已固定主线与信息架构；D-026～D-030 已完成 HC-018/Q01；D-031 已接受 HC-002/Q02.1 的开放 predicate registry、schema-conditioned 共享 updater 与次级 held-out registered-predicate 泛化，不做任意自然语言谓词。已验证 RTX 4070 Laptop 可被 PyTorch CUDA 使用；T0a 仍CPU-first，训练再用GPU。没有代码、数据、训练或验证。当前只等待 HC-002/Q02.2 核心 stored/derived 名单。

不要把旧完整闭环、导航、region binding、Top-K、动作预测或主动取证重新并列成贡献。不要堆七项以上重复 loss。任何实现先过 evaluator，任何 test 只在规则冻结后打开。
