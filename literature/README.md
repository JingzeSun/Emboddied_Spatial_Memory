# 文献工作流

`library.csv` 是唯一文献索引；PDF 文件名不是知识管理系统。

同行评审状态和正式引用边界见 [`peer_review_audit.md`](peer_review_audit.md)。论文写作时不得只看 `venue` 字符串，必须同时检查 `peer_review_status`、`venue_verification_url` 和 `related_work_usage`。

## 添加论文

1. 把合法获得的 PDF 放入 `papers/`；重点论文可继续保留在 `papers_detail/`，暂不移动历史文件。
2. 在 `library.csv` 中登记 title、year、venue、topic、URL 和 local path，并从官方 proceedings、出版社页面或正式 OpenReview 接收页核实 `peer_review_status` 和 `venue_verification_url`。
3. 从 `notes/TEMPLATE.md` 复制一份笔记，文件名使用稳定短名，例如 `spatialmem_2026.md`。
4. 填写 memory coordinate、association、update、dynamic handling、data、metrics 和与本项目差异。
5. 更新 `docs/05_related_work_matrix.md`。

本地 PDF 目录被 `.gitignore` 排除。Git 只同步索引、笔记与合法公开链接，不同步论文 PDF。

## 阅读状态

- `inbox`：已收集，未筛选；
- `skimmed`：已读摘要、方法图和实验表；
- `reading`：正在精读；
- `noted`：已有结构化笔记；
- `implemented`：已复现或接入；
- `deep_read`：已完成面向本项目的深读；
- `excluded`：与主线无关，并在笔记中说明原因。

不要依赖 `papers_detail` 目录名推断论文已经精读；只有存在笔记并填完核心问题才算 `noted`。

阅读状态和同行评审状态是两条独立维度：`noted` 不等于已同行评审，`verified_peer_reviewed` 也不等于已精读。

## 同行评审状态

- `verified_peer_reviewed`：已从官方 proceedings、出版社或正式接收页核验；
- `preprint_only`：目前只找到预印本；
- `submitted_not_accepted`：官方页面仍显示投稿，未显示接收；
- `submission_or_preprint`：存在投稿或预印本，但没有正式接收证据；
- `preprint_or_venue_unverified`：有 venue 声明，但本轮没有在官方来源完成核验。

## Related Work 用途

- `foundation`：直接相关且同行评审已核验，可支撑核心论述；
- `adjacent`：同行评审已核验，可用于邻近路线、数据或强基线；
- `novelty_watch_only`：只做创新性预警，不作为已验证事实的基石；
- `excluded`：离题或不进入主线。

没有官方证据时不得填 `foundation` 或 `adjacent`。作者主页、项目主页和社交媒体中的 venue 声明只能作为待核线索。

## 写作前检查

1. Related Work 主干是否只依赖 `foundation` 与 `adjacent`；
2. 预印本是否明确写成 preprint/submission，而非“已有研究已经证明”；
3. venue 声明是否有官方 URL；
4. 是否记录与本项目最小差异、反例和未覆盖条件；
5. 是否在投稿前重新审计 `novelty_watch_only` 条目的状态。
