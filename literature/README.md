# 文献工作流

`library.csv` 是唯一机器文献索引；PDF 文件名不是知识管理系统。同行评审准入见 [`peer_review_audit.md`](peer_review_audit.md)。

## 两条独立状态

- 阅读状态：inbox / skimmed / reading / noted / deep_read / implemented / excluded；
- 同行评审状态：verified_peer_reviewed / preprint_only / submitted_not_accepted / submission_or_preprint / preprint_or_venue_unverified。

`noted` 不代表已同行评审；`verified_peer_reviewed` 也不代表已精读。

## Related Work 用途

- `foundation`：已核验且直接相关，可支撑事实主干；
- `adjacent`：已核验但侧重邻近任务/表示；
- `novelty_watch_only`：只做查重、baseline 和 claim 收缩；
- `excluded`：离题。

没有官方 proceedings、出版社或正式接收页证据，不得升级为 foundation/adjacent。

## 当前精读问题

每篇论文除 memory coordinate、association、update、dynamic handling、data、metrics 外，还必须回答：

1. 是否生成 structured innovation？
2. 更新单位和 affected scope 是什么？
3. 是否有 relation propagation？
4. propagation 在哪里停止？
5. 是否保留 history/provenance？
6. 是否评测 necessary update 和 unrelated preservation？
7. 是否隐式全图重算？
8. 相对本项目的最小机制差异是什么？

## 添加与更新

1. 合法获得的 PDF 放 `papers/` 或 `papers_detail/`，这些目录不进 Git；
2. 更新 `library.csv` 的官方 URL、状态和用途；
3. 使用 `notes/TEMPLATE.md` 新建结构化笔记；
4. 更新 `notes/00_cross_paper_synthesis.md`、`peer_review_audit.md` 与 `docs/01_research_contract.md` 的创新边界；
5. 投稿前重新审计 novelty-watch 状态。

作者主页、项目页和社交媒体 venue 声明只能作线索，不能单独作为同行评审证据。
