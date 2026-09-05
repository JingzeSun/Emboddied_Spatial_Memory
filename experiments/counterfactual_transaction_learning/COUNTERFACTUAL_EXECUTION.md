# Versioned Counterfactual Execution

## Clone

所有 candidates 从同一 immutable base_graph_version 分叉。clone 可以 copy-on-write，但 transaction log、result version 和 graph hash 必须独立。

## Execute

executor 按序运行 primitives，并在 sandbox commit 前检查：

1. base version 和 preconditions；
2. node/edge references；
3. intent/template compatibility；
4. lifecycle、identity、temporal interval；
5. protected IDs 与 collateral scope；
6. provenance、idempotency；
7. failure 的 atomic rollback。

executor deterministic、无梯度、不读取未来。同一 graph、program、config 必须产生相同 result hash。

## Project

对每个合法 \(S_t^{(u)}\)：

1. 用 \(T_t\) 重投影得到当前结构预测，计算 \(D_{\mathrm{now}}\)；
2. 用相同动作、future poses 和 horizon 预测未来结构，计算 \(D_{\mathrm{future}}\)；
3. 按 world diff 计算 edit、growth、collateral；
4. 保存每项原始 numerator、mask 和权重。

visible-empty、occluded、out-of-view 和 unknown 必须分开。非法候选不进入 softmax。

## Rank and distill

energy 归一化形成 \(p^*(u)\)。online \(q_\theta\) 只接收截止 t 的信息，并对 intent、template、arguments 和完整 program 分别评价。

## Online commit

- 选择合法最高 posterior program；
- top probability 或 top-1/top-2 margin 未跨过 validation 门槛时进入 deterministic QUARANTINE；
- QUARANTINE 只写 pending memory，保存低权重 evidence 与粗略检索键，不修改 world；
- 只有真正能消歧的相关观察机会才累计 K；达到 K 后只归档，仍可检索与重激活；
- 正式事务消费 pending record 时必须引用全部 pending evidence；
- commit 后生成新 world version；
- 原 base graph 与未选 sandbox branches 不被修改。

白话说，在线模型不是“看不清就忘掉”，而是先把模糊印象放入可搜索草稿。以后看见相似结构时可以重新关联；只有跨过提交门槛后才改正式世界。
