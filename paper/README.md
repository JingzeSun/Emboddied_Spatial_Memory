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

## 改版（2026-10-08 第二轮，EXECUTE LOG-313；上面的状态、文件表与说明是第一轮的记录，保留不改）

白话：这一轮回答“对本项目一无所知的审稿人能不能读懂，稿件合不合 RA-L 的规定”。输入是第一轮稿、一位模拟审稿人（做过物体级建图与 SLAM、不熟悉本项目）的逐节意见和 RA-L 的投稿规定；输出是 8 页内自足的正文、匿名与正式两版 PDF、新的图与表。例如原来的两张逐指标区间表和 3RScan 表合成了一张取舍矩阵图（图 4），附录全部并入正文或删去。它不是新实验，不改任何数，只改写作与排版。

- RA-L 规定（用户 2026-10-08 在 ieee-ras.org 的 RA-L Information for Authors 页面核实）：6 页加至多 2 页付费页，图、表、参考文献与附录全部计入；附录这类文字或图表不能作为 8 页之外的补充材料（补充材料只收视频、数据集、代码与说明文件）；图表都要编号并在正文引用；审稿双盲。所以稿件不再有附录，`build.sh` 把页数超过 8 当作失败。
- 两版一个开关：`main.tex` 顶部 `\finalversionfalse` 是匿名初投稿版（默认；作者栏写 Anonymous Authors，脚注说明作者信息因双盲审稿隐去，GitHub 与 Hugging Face 链接写成 “link withheld for review”），改成 `\finalversiontrue` 是正式版（作者 Jingze Sun、The University of Sydney、jingzesun498@gmail.com 与全部链接）。`bash paper/tools/build.sh` 同时编出 `paper/build/vsmt_review.pdf` 与 `vsmt_final.pdf`，每版核对页数不超过 8、0 处溢出、0 个未定义或不稳定引用，匿名版另用 pdftotext 查不含作者名、单位、邮箱与个人仓库名；任一项不过退出码为 1。
- 原附录的去向：区间表（旧附录 A 的两张）与 3RScan 表 → 图 4 取舍矩阵三格；主门表 → 图 3 点图（带区间与逐种子差）；逐 house 图删去，计数写在结果节 V-A；选参表 → 协议节 IV-C 的文字；三分解与规模表 → 结果节 V-E 的文字；LLM-op 一段与附表 → 结果节一句加表 III（DECISIONS“D-224-S4”登记）；复现一节 → 结论节 “Reproducibility” 段。全表留在已提交的导出与根目录 README 的论文索引里。
- 打 Overleaf 包：`python paper/tools/pack_overleaf.py` 写出 `paper/build/vsmt_overleaf.zip`（`main.tex`、`refs.bib`、`sections/*.tex`、`tables/*.tex`、`figures/*.pdf`、`figures/*.tex`），在 Overleaf 用 New Project → Upload Project 上传；Overleaf 上默认编匿名版。

| 文件（第二轮） | 内容 |
|---|---|
| `figures/overview.tex` | 图 1（第 1 页）：杯子在看不见时被挪走，三种记忆各自会怎样，以及 MRR、IdC 数的是什么；TikZ 手绘，不含数据 |
| `figures/method.tex` | 图 2：单帧流程（封存 A、B，教师只在训练时用）与实体状态（地图＝active＋dormant，retracted 离开地图但可召回）；不含数据，只有参数数 54,787 |
| `figures/gate.pdf` | 图 3：主门固定顺序三步与原主门的点图（`make_figures.py`；数取自 S3-05 `primary_gate`／`original_gate` 与 S3-06 `d3_intervals`，脚本核对区间左端等于检验用的单侧下界） |
| `figures/comparisons.pdf` | 图 4：VSMT-lean 对其余八个臂、七项指标的优势矩阵，三格（ProcTHOR 实例分割、ProcTHOR SAM 2.1、3RScan 实例分割），按双侧 90% 区间着色（S3-06 `d3_intervals`、S3-07 `comparisons`） |
| `tables/main.tex` | 表 II：test 主表，列按“回答哪个问题”分组，主指标表头加粗 |
| `tables/llm_op.tex` | 表 III：LLM-op 与其他九个臂在同一条 validation episode 上的节点 F1（附百分位）与假撤回率（S4 E1 导出） |
| `sections/method.tex` 里的表 I | 九个臂一行一臂（手写，不含数据） |
| `tools/check_draft.py` | 新增：禁用词与等价说法、速度与下游任务说法、ELU-P“代价”句式；摘要三句与两条限定；方法／协议节三项披露；每张图表有标签且在正文被引用；LLM-op 小表在正文且表注写明四项 |
| `tools/pack_overleaf.py` | 打 Overleaf 包 |

删去：`sections/supplement.tex`、`tables/{ablations,rule_arms,external,gate,selection,decomposition,size}.tex`、`figures/{tradeoff,per_house}.pdf`（都可从 Git 历史取回）。

与根目录 README“论文结果与复现索引”的编号对应（那张索引与 `results/vsmt_lean_s3_06_paper_index_154043e.json` 仍按第一轮编号，不改）：表 II＝索引表 1、表 2；图 3＝索引表 3；图 4(a)(b)＝索引表 4、表 5；图 4(c)＝索引表 8；结果节 V-E 的三分解与规模＝索引表 6、表 7；协议节 IV-C 的选参＝索引“附录”行的 S3-04 选参导出；表 III＝索引“附录”行的 LLM-op（另加 `results/vsmt_lean_s4_llm_op_context_2b50a12.json`）；索引的图 2（取舍散点）不再出现，图 3（逐 house）的计数写在 V-A。
