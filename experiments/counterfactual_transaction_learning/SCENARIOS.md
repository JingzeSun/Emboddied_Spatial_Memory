# CPMT Scenario Contract

## 十二个最小 case

| Case | 竞争解释 | 核心失败 |
|---|---|---|
| C00 | NOOP vs RELINK/BIRTH | ego-motion 被写成 world change |
| C01 | BIND vs BIRTH | reappearance 与新实例 |
| C02 | BIRTH vs BIND | first reveal 与 revisit |
| C03 | BIND vs REACTIVATE | active 与 dormant identity |
| C04 | SPLIT vs NOOP | conflated node |
| C05 | MERGE vs separate IDs | duplicate revisit |
| C06 | RELINK vs REPLACE | relocation 与 replacement |
| C07 | RETRACT vs occlusion | reliable absence |
| C08 | RELINK vs temporary block | topology change |
| C09 | NOOP vs edit | pose/depth fault |
| C10 | NOOP/BIND vs edit | dynamic actor contamination |
| C11 | any vs collateral edit | protected context |

每个 case 必须有 positive、confounder、control、candidate coverage 和 protected distractor。C04/C05 是 SPLIT/MERGE 组合压力测试，不各自扩成大数据分支。

## Split

paired_group_id、world_seed、asset family 和同源轨迹整体 group split。test 前冻结 OOD axes；不允许相同 scene 轻微变体跨 split。

## Ground truth

M0 使用人工可审计规则和显式 simulator state。现实数据无法唯一判断时使用 equivalence/ambiguous，不强制单标签。模型或 VLM 评价不是真值。
