# PSLM 模型合同

工作名：**Projective Structural Latent Memory（PSLM）**。模型核心可称 **Projective Structural Memory Transducer**；投稿前检查名称冲突。

## 1. Projective Structural Tokenizer

输入 frozen DINO 类 patch features、depth、pose uncertainty、surface/plane、instance、portal、occlusion 与结构方向线索。输出可变数量 region tokens。

首选 hybrid region，不硬编码八块透视网格：

- surface/plane 支撑墙、地面和无显著物体的结构；
- object/instance 支撑可移动实体；
- portal/opening 支撑拓扑连接；
- occlusion boundary 支撑 visibility；
- VP/dominant direction 作为弱 cue，帮助走廊和转弯，不成为 world ID。

必要消融：fixed ViT patches、VP-only、object-only、geometry-only、hybrid。

## 2. Predict-project Module

解析 geometry projector 将 world nodes 投影到当前视图；轻量 temporal/graph module 预测：

- expected visible/occluded/out-of-FOV；
- projected region support 与 uncertainty；
- view-conditioned structural latent distribution；
- action 后下一 Chart/portal/frontier candidate。

只预测结构 latent/visibility，不训练 RGB decoder。无 action 数据时只能称 pose-conditioned projection，不能声称完整世界动力学。

## 3. World Memory Encoder

对 Place、Chart、slot/track、relation、version/evidence 构建异构图。局部 active graph 由 frustum、Chart/Place 和空间索引检索；历史版本只读，不能被普通 message passing 覆盖。

task 节点只接收 memory 信息，默认不向 world truth 反传。

## 4. Association Head

对 observed/projected token 对输出兼容分数，并提供 dustbin/abstention。特征至少包含：

- 3D geometry 与 projected overlap；
- latent distribution/prototype distance；
- semantics/structural role；
- visibility、dynamic 与 lifecycle compatibility；
- pose/measurement uncertainty；
- Chart/topology context 与时间历史。

decoder 输出 set-valued `BIND/NEW/REACTIVATE/SPLIT/MERGE/UNRESOLVED`，而不是默认一对一。

## 5. Birth and Attachment Head

对 `NEW` evidence 预测：

- candidate node type；
- geometry/latent initialization；
- supporting observations；
- parent Chart/Place 与 attachment edges；
- confirmation probability；
- 是否与旧 retired node reactivation 竞争。

多帧确认与 executor 控制 candidate→confirmed。单帧高置信也必须由 HC-025 允许才可直接提交。

## 6. Growth/Revision Transaction Decoder

先预测 gate，再条件化输出 scope、operations、valid time 和 evidence set。graph expansion 与 belief revision 共用 transaction 接口，但分开计分：

- expansion 创建此前未知的 node/edge/Chart attachment；
- revision 关闭、替换或重连已有版本；
- preserve 记录遮挡/出视野原因但不覆盖长期 latent；
- quarantine 保存冲突候选和原始证据。

## 7. Latent State

默认候选为 bounded prototype set + uncertainty，而不是无限存帧或单 EMA：

```text
latent_state = {
  prototypes: up_to_K,
  weights,
  dispersion,
  view/geometry tags,
  supporting_evidence_ids,
  last_reinforced_at
}
```

K、替换策略与是否保存 covariance 由 HC-028 冻结。mean/EMA、mean+covariance、evidence bank 是必要基线。

## 8. Executor 与状态提交

模型只输出 candidate association/transaction。executor 负责 ID、lineage、版本、坐标、生命周期、protected scope、atomic commit 与 provenance。模型原始错误率、拒绝率和执行后状态必须同时报告。

## 9. 规模配置

| 配置 | hidden/layers | active nodes/regions | 参数目标 | 用途 |
|---|---|---:|---:|---|
| tiny | 128 / 2+2 | 128 / 32 | 约4M–8M | smoke/pilot |
| base | 256 / 4+3 | 256 / 64 | 约12M–25M | 正式比较候选 |

与 learned matcher、recent-N graph model 和 full-memory graph model 做参数、step 与 wall-clock 匹配。报告 backbone 参数但不把冻结参数混入 trainable matching。

## 10. 实现顺序

1. schema、oracle lineage、executor、evaluator；
2. deterministic tokenizer/projector/association；
3. patch/warp/slot/window/full-recompute baselines；
4. learned association + abstention；
5. candidate birth + attachment；
6. lifecycle + revision transaction；
7. predict-project；
8. online rollout、simulator OOD、external sequence。
