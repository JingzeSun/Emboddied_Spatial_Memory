# Source Layout

当前实现服从 `docs/01_research_contract.md`、`docs/03_pilot_protocol.md`、`configs/mvp.yaml` 和 `schemas/`。

## 目标目录

```text
src/embodied_spatial_memory/
├── contracts/        schema-backed records and validation
├── events/           bitemporal evidence records, grouping and adapters
├── executor/         hard preconditions, closure, atomic versions
├── models/           Flat/Event/TGN/RGT/BEGR learned controllers
├── generation/       symbolic world/event/evidence generator
├── geometry/         SE(3), projection, frustum, ego flow
├── perception/       latent, region, object, depth, motion evidence
├── association/      observation-to-belief candidates
├── belief/           graph versions, provenance, consolidation
├── innovation/       expected observation and structured comparison
├── revision/         scope retriever, controllers, typed executor
├── context/          ActiveContext and evidence-trace queries
├── baselines/        append, EMA, lifecycle, local, full recompute
└── evaluation/       delta, propagation, preservation, query, cost
```

## 实现顺序

1. posterior event/transaction contracts gap record（相关 HC 冻结前不改 schema）；
2. versioned executor + evaluator mutation tests；
3. 12 smoke fixtures 与 B0–B7；
4. symbolic generator、group split 与 leakage audit；
5. FlatFact-MLP / Event-Transformer；
6. TGN-style / FullGraph-RGT；
7. BEGR-Net 与结构/时间消融；
8. AI2-THOR adapter；
9. 3RScan/Dyn-THOR secondary adapters；
10. geometry、prediction、association、planning 后续集成。

第一个里程碑不依赖 GPU：手写 belief + evidence events + oracle transaction 能执行、回放并被 mutation-tested evaluator 正确判分。GPU 训练接口见 `experiments/bounded_revision_validation/LEARNED_MODEL.md`。

公开 API 必须使用 typed/schema-backed 对象；任何修改必须带 base version、evidence、confidence 和 controller revision。
