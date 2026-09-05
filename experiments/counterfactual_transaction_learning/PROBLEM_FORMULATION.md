# CPMT / CTL Problem Formulation

## 状态

方法合同已确认；参数化、实现和有效性尚未验证。

## 变量

- \(O_t\)：当前传感器观测；
- \(R_t=\phi(O_t,T_t)\)：当前 structural-region latents；
- \(S_{t-1}\)：versioned persistent world memory；
- \(a_{<t}\)：决定时刻之前的动作历史；
- \(\mathcal C_t\)：由固定 proposer 生成的 candidate transaction programs。

## 执行候选世界

\[
S_t^{(u)}=\operatorname{Execute}(\operatorname{Clone}(S_{t-1}),u),
\qquad u\in\mathcal C_t.
\]

非法 program 在预测前被 executor 拒绝。所有合法候选从完全相同的 base version 开始。

## Counterfactual energy

\[
\begin{aligned}
E(u)=&
\lambda_nD_{\mathrm{now}}\!\left(\Pi(S_t^{(u)},T_t),R_t\right)\\
&+\lambda_fD_{\mathrm{future}}\!\left(
\operatorname{PredictProject}(S_t^{(u)},a_{t:t+H-1},T_{t+1:t+H}),
R_{t+1:t+H}\right)\\
&+\beta C_{\mathrm{edit}}(u)
+\gamma C_{\mathrm{growth}}(u)
+\eta C_{\mathrm{collateral}}(u)
+I_{\mathrm{illegal}}(u).
\end{aligned}
\]

- now：执行后世界对当前可见结构的解释误差；
- future：同一执行后世界对后续可见结构的预测误差；
- edit：关闭或改变既有事实的复杂度；
- growth：新建 node/edge，单独抑制 node explosion；
- collateral：修改非必要或 protected context；
- illegal：违反 precondition/invariant 时为无穷大。

所有 discrepancy 使用 visibility mask，区分 visible-empty、occluded、out-of-view 和 unknown。

## Hindsight posterior

\[
p^*(u\mid R_{t:t+H},S_{t-1},a)
=
\frac{\mathbf 1[u\ \mathrm{legal}]\exp[-E(u)/\tau]}
{\sum_{v\in\mathcal C_t}\mathbf 1[v\ \mathrm{legal}]\exp[-E(v)/\tau]}.
\]

若多个 programs 产生语义等价 graph，概率在 equivalence set 上聚合，不强迫唯一字符串 target。

## Online amortization

\[
q_\theta(u\mid S_{t-1},R_{\le t},a_{<t})
\]

拟合 hindsight posterior，但其数据接口物理排除 future observations/poses、oracle programs 和 hidden simulator state。

## 可证伪性

CTL 只有在 post-edit execution 同时改善 program selection、graph correctness 和 self-rollout contamination 时成立。未来监督本身有用但不足以证明 CTL；必须通过 direct+future-loss 与 no-execution scorer 排除替代解释。
