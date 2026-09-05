# CPMT Run Protocol

## M0

schema validate → oracle fixture → corruption test → deterministic replay → HC-001 freeze。

## M1

freeze paired split、candidate K、energy weights、A–F budgets 和 primary thresholds；运行 hard-condition；先检查 coverage/invariants，再看 A vs C/E。

## M2

冻结感知前端；分别运行 hindsight teacher、online teacher-forced 和 online self-rollout；加入 label-fraction 与 Projective Node Orbit 消融。

## M3

冻结 release commit 后只选择一个 external/现实来源；运行 formal seeds、OOD、runtime 和 artifact cold-start。

## 每个 run

保存 manifest、config/environment、逐候选 transaction、sandbox graph hash、now/future/edit/growth/collateral/illegal、graph diff、逐例指标和 failures。

test 后发现实现 bug 时，旧批次标 invalidated；修复进入决策日志，A–F 整套重跑，不能只重跑 CPMT。
