# Test contract

这里的 software tests 与论文 test split 不同。软件测试可以随时运行；论文 test 数据在合同冻结前不得查看。

计划测试：

- schema：合法/非法 evidence、graph、transaction、case、run manifest；
- bitemporal：迟到旧消息不能覆盖新有效区间；
- executor：互斥、闭包、protected facts、atomic version、幂等；
- evidence：写操作缺 provenance 必须拒绝；
- negative evidence：occluded/out-of-FOV/reliably absent 分流；
- metrics：C1–C15 用手算 fixture 对拍；
- split guard：场景、实体组合和 generator seed 不跨 split；
- baseline adapter：同一输入、canonical output、共享 executor；
- regression：所有 S00–S11 失败类型保留。

oracle evaluator 必须 100%，但这只证明判尺实现与人工合同一致，不证明模型正确。

