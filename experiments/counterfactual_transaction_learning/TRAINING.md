# CTL Training

## Hindsight teacher

对合法候选保存 now、future、edit、growth、collateral、illegal 和 total energy，以 temperature softmax 形成 \(p^*(u)\)。temperature、weights、horizon 和 K 只在 validation 选择。

## Online student

\[
\mathcal L_{\mathrm{CTL}}
=
\operatorname{KL}(\operatorname{stopgrad}(p^*)\Vert q_\theta(u\mid S_{t-1},R_{\le t},a_{<t})).
\]

student 预测 intent、template、arguments 和 primitive program。输出必须通过 transaction schema/executor；invalid program 的 raw rate 与 deterministic fallback 分别报告。

## Fixed scope

candidate proposer、executor、backbone、depth、pose 和 regions 固定。只训练轻量 future scorer/projector 与 online student。

## Evaluation modes

- hindsight teacher；
- online teacher-forced graph；
- online self-rollout graph；
- transaction labels 0/1/10/100%。

scheduled sampling 若使用，必须作为额外变体，不能混入主方法。
