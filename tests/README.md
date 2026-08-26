# Tests

测试优先覆盖论文结论依赖的确定性逻辑。

## P0 contracts/executor

1. 四个 JSON schema 的合法/非法样例；
2. node/edge ID、enum、affected/control overlap；
3. version chain、valid time、supersedes cycle；
4. 八个 typed operators 的 before/after；
5. invariant 失败进入 quarantine；
6. control subgraph byte/semantic unchanged。

## P1 micro fixtures

1. person occludes door → preserve door；
2. stationary duration 增长 → actor ontology unchanged；
3. chair visible relocation → relink/supersede；
4. reliable absence → old edge invalid + location unknown；
5. out-of-FOV/occlusion → no invalidation；
6. irrelevant innovation → stop boundary。

## P2 geometry/innovation

1. `T_world_camera` round-trip；
2. pure rotation 和 depth reprojection；
3. frustum/occlusion/out-of-FOV/reliable absence；
4. static ego-motion residual；
5. turning 不产生批量 false innovation；
6. association split/merge ambiguity。

## P3 metrics

故意构造漏改、多改、越界传播、错误 preserve、空预测和 full-graph edit，检查 delta、propagation、collateral、preservation 和 cost 分别恶化。

真实模型接入前先通过可解析合成测试，避免用 perception noise 掩盖 graph revision bug。
