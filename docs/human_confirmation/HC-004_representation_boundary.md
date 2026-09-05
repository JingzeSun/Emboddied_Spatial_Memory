# HC-004 Representation Boundary

- 状态：pending
- 最早激活：M2；当前 deferred
- 建议默认：冻结 DINO-family backbone；只训练 region pooling/transport 与轻量 projection；depth/pose 作为带噪输入而非 oracle。

需决定 backbone、depth source、pose source、Local Chart 定义、mixed-chart transition、latent dimension 与允许训练的层。任何改变都要同时更新 no-projective-latent 消融。

研究者选择：____

日期 / 理由 / 影响：____
