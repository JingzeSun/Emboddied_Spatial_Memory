# Source Layout

当前实现服从 `docs/09_integrated_direction_plan.md`、`docs/02_method_spec.md` 和 `schemas/`。

## 目标目录

```text
src/embodied_spatial_memory/
├── contracts/        schema-backed records and validation
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

1. contracts；
2. versioned executor；
3. micro fixtures；
4. metrics；
5. geometry/projection；
6. structured innovation；
7. deterministic scope；
8. simulator mapper；
9. learned controller；
10. context query。

第一个里程碑不依赖 GPU：手写 belief + observation + oracle delta 能执行并得到 exact graph match。详细工作包见 `docs/10_implementation_roadmap.md`。

公开 API 必须使用 typed/schema-backed 对象；任何修改必须带 base version、evidence、confidence 和 controller revision。
