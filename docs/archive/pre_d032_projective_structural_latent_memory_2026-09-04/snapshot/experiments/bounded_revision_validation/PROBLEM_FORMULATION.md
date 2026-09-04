# 问题形式化

## 在线事务

在逻辑步 `t`，输入旧信念图 `G_{t-1}` 与截至当前已到达的证据 `E_{≤t}`。证据可以迟到、乱序、重复、冲突或只覆盖部分视野。模型输出：

\[
q_\phi(\Delta G_t,M_t,\tau_t,Z_t\mid G_{t-1},E_{\le t},\Sigma).
\]

- `ΔG_t`：`KEEP / ASSERT / RETRACT / REPLACE / QUARANTINE`；
- `M_t`：进入事务可写范围的 seed affected mask；
- `τ_t`：事实有效时间或有效时间区间；
- `Z_t`：直接支持事务的证据集合；
- `Σ`：predicate registry，描述 storage、arity、value、symmetry、exclusivity、reference frame、temporal/dependency policy 与 observability。

确定性 executor 审核候选事务并原子提交得到 `G_t`。模型推断“该改什么”，executor 保证“绝不能非法改”。

## 输入图

最小异构图包含：

- `entity`：物体、房间、区域、设施；
- `fact`：重述后的时态事实，如 `at(cart_7, zone_A)`；
- `evidence`：正观测、负观测或来源消息；
- `task`：依赖事实的下游任务，只读且不能反向决定事实真假。

事实至少保存 semantic status、valid time、transaction time、source refs 和 version。证据至少保存：

```yaml
evidence_id: ev_204
source_id: robot_2
observed_at: 602.0
received_at: 968.0
visibility: 0.91
predicate: at
subject: cart_7
object: zone_B
polarity: positive
confidence: 0.88
group_id: scan_91
```

`observed_at` 说明证据描述哪个世界时刻；`received_at` 说明系统何时得到它，二者不可互换。

## 输出语义

- `KEEP(f)`：保持事实，不产生物理写操作；
- `ASSERT(f,τ,Z)`：建立有证据的新事实；
- `RETRACT(f,τ,Z)`：关闭旧事实的有效区间，不删除历史；
- `REPLACE(f_old,f_new,τ,Z)`：同一事务中的撤回与断言；
- `QUARANTINE(h,Z)`：证据不足或冲突，保存候选但不写 confirmed。

模型预测 `M_t` seed；executor 只允许修改 seed 与 typed dependency 导出的最小合法闭包。闭包之外全部是 protected controls。

若模拟器给出真实变化时刻，可以监督点或时间桶；若 3RScan 等只知道“上次仍成立、首次已改变”，则监督区间 `[t_last_support,t_first_contradiction]`，不伪造精确标签。

`Z_t` 是最小充分证据集合。直接监督 evidence-to-edit 边或集合标签；attention 只能作诊断，不能当 ground truth 归因。

## 控制变量与边界

主比较固定 detection、identity、pose、visibility、候选检索和 dependency input，只替换 updater。上游可为 oracle 或同一冻结模型，但须逐轨报告。

本论文不主张新的检测器、SLAM、完整导航、社会规范规划、开放本体发现或全图建图替代。成功必须同时包含编辑正确、影响边界正确、有效时间合法、证据可追溯、无关事实保持和依赖项正确失效。

## 输出变量的 Criteria 纵列

| 输出/层 | 本实验里具体要证明什么 | Criteria | 怎么算 | 数字例子 | 人工来源 |
|---|---|---|---|---|---|
| `ΔG_t` | 五类编辑及整个事务正确 | C1/C2 | macro-F1 + transaction exact | 五类F1平均=.76；71/100事务整体正确 | HC-002/005/013/016 |
| `M_t` | 必改不漏、无关不碰、恰好停止 | C3–C7/C15 | NUR、mask F1、CPR、CER、stop、效率 | 真8选10命中7；写12越界3，CER=25% | HC-003/005/013 |
| `τ_t` | world time 不被 arrival time污染 | C8/C9 | exact MAE或interval coverage+width | MAE=2 s；coverage=91%、width=38 s | HC-015 |
| `Z_t` | 修订能反查直接支持证据 | C10/C11 | set F1 + 删除/保留干预 | 真3选4命中2，F1=57.1% | HC-016 |
| executor | 候选非法也不能污染状态 | C13 | pre violation、rejection、post violation | pre=4%、reject=3.5%、post=0 | HC-016/013 |
| task view | 事实错误是否真的产生后果 | C14 | 错派/漏关/无关重算 | 6%/12.5%/4% | HC-003/019 |

读者在这里即可知道每个随机变量如何落到实验；完整公式仍以 `CRITERIA.md` 为准。
