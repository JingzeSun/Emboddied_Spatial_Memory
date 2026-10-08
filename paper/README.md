# 论文稿（S4，RA-L 格式草稿）

这里是 VSMT-lean 首篇论文的 LaTeX 稿。它解决“论文里每句话、每个数从哪来”的问题：主张只按 `docs/METHOD.md` 第二节“S3-05 之后的主张范围”（裁决 113）写，逐句措辞取自 `EXECUTE.md` 的 LOG-307（A2、A4）、LOG-308 与 LOG-309；表格全部由脚本从 `results/` 里已提交的导出排出，不手抄数字。输入是已提交的导出；输出是 `main.tex` 及其各节、`tables/*.tex`、`figures/*.pdf`。例如主表 VSMT-lean 的节点 F1 来自 `results/vsmt_lean_s3_05_statistics_8d58475.json` 的 `fronts.instance.main_table.node_prf1`。它不是新实验，不改任何 test 数字，也不替代 README 的“论文结果与复现索引”。

状态：**草稿**。本机 MiKTeX 编译通过（0 处溢出）。按用户选的压页方案 (a)，正文加参考文献正好 8 页（RA-L 6＋2 页上限），附录从第 9 页起，投稿时移到补充材料；两张逐指标区间表与逐 house 图在附录 A。`\todo{}` 与 `\verifyref{}` 标出的地方在投稿前必须处理。

上传 Overleaf：把 `main.tex`、`refs.bib`、`sections/`、`tables/`、`figures/`（`*.pdf` 与 `method.tex`）打成 zip，在 Overleaf 用 New Project → Upload Project 新建项目。表与图以本仓库的脚本输出为准，不在 Overleaf 里改。

| 文件 | 内容 |
|---|---|
| `main.tex` | IEEEtran journal 类，按节 `\input` |
| `sections/*.tex` | 摘要、引言、相关工作、方法、实验协议、结果、局限、结论、附录 |
| `tables/*.tex` | 由 `tools/make_tables.py` 生成，**不要手改** |
| `figures/*.pdf` | 由 `tools/make_figures.py` 生成（取舍散点、逐 house 配对差） |
| `figures/method.tex` | 图 1 方法示意，TikZ 手绘（据 `docs/METHOD.md` 第三～八节，不含数据），随正文一起编译 |
| `tools/make_tables.py` | 从 `results/` 排表（S3-05 统计、S3-06 复算、S3-07 外部验证、S3-04 冻结回执、S4 E1 导出） |
| `tools/make_figures.py` | 从 `results/` 画取舍散点与逐 house 配对差；`--png` 另出预览图（不提交） |
| `tools/check_draft.py` | 不需要 LaTeX 的静态核对：`\input` 文件存在、`\ref` 都有 `\label`、`\cite` 键都在 `refs.bib`、花括号配平 |
| `tools/build.sh` | pdflatex＋bibtex＋两遍 pdflatex，输出到 `paper/build/`（不进版本库），报溢出与未定义引用 |
| `refs.bib` | 参考文献；每条下面写了核对来源，`note` 里写 VERIFY 的条目未核实 |

重新生成表与图并核对（仓库根目录）：

```bash
python paper/tools/make_tables.py
```

```bash
python paper/tools/make_figures.py
```

```bash
python paper/tools/check_draft.py
```

编译（MiKTeX 或 TeX Live；本机 MiKTeX 装在用户目录，脚本会自己找到）：

```bash
bash paper/tools/build.sh
```
