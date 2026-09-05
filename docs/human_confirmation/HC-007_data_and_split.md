# HC-007 Data, Split, Test Release

- 状态：M1 controlled split 已由 D-031 冻结；M3 数据选择仍 pending
- 最早激活：M3；当前 deferred
- 建议默认：paired_group_id + world_seed + asset_family 联合 group split；冻结 manifest hash 后封存 test；选择两个 OOD axes。

需确认 simulator、轨迹生成器、train/validation/test 比例、OOD 范围、排除规则、外部数据许可和 test 解封人。任何重生成都使用新 dataset_version。

M1 v1 冻结选择（D-030/D-031）：使用 `controlled_embodied_spatial_worlds_v1`；C00–C11 每 family 1000/200/200 个 train/validation/test paired groups；联合 group key 不跨 split；只排除方法运行前的 schema/generator/render failure；方法失败保留；任何重生成使用新 dataset version/hash。test 只有在实现验证通过后才生成/解封。M3 的 simulator/现实数据许可、两个 OOD axes 与解封责任人仍未由本项决定。

研究者选择：M1 v1 已确认；M3 选项继续 deferred。

日期 / 理由 / 影响：____
