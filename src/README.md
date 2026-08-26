# Source Layout

正式写代码前先冻结 `docs/02_method_spec.md` 中的坐标和数据契约。

计划模块：

```text
src/
├── perception/       DINO、depth、flow、line/plane cues
├── geometry/         SE(3)、projection、ego-motion flow
├── regions/          observation region 和 latent pooling
├── association/      region-to-slot / region-to-chart
├── memory/           slot、lifecycle、soft update、provenance
├── charts/           chart creation、overlap、topology
├── queries/          retrieval、projection、topology query
└── evaluation/       contamination、retention、consistency metrics
```

第一个实现里程碑不是训练模型，而是完成可视化的数据读取、正确的坐标重投影和 B0–B4 baseline。
