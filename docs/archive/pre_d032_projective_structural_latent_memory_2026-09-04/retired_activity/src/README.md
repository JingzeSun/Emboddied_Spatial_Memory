# Source layout contract

当前尚未实现。HC-018 与核心 CRITERIA 冻结后，建议按职责建立：

```text
src/
  contracts/       # canonical dataclasses 与 schema validation
  generators/      # symbolic / AI2-THOR transaction generation
  executors/       # deterministic projection 与 atomic commit
  evaluators/      # C1–C15，无训练依赖
  baselines/       # R0–R3、L0–L4 adapters
  models/          # ESGBU encoders/heads
  data/            # loaders、split guards、collation
  training/        # train/validate，不读 test
  reporting/       # tables、CI、failure taxonomy
```

依赖方向：contracts → executor/evaluator；models 只能输出 candidate transaction，不能直接写 graph；task nodes 默认不能反向定义 fact truth。

第一实现必须是 schema + executor + evaluator，不是神经网络。任何模块完成后更新本文件的 `planned/implemented/validated` 状态。

