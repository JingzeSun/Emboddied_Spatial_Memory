#!/usr/bin/env python3
"""S4: static checks of the LaTeX draft that need no TeX installation.

白话：编译之前先把最容易出的错查出来。输入是 ``paper/main.tex``、它 ``\\input`` 的各节、表格与 TikZ 图、``paper/refs.bib``；
输出是问题清单，没有问题时退出码 0。查四类：
1. 结构：``\\input`` 的文件存在、``\\ref`` 都有 ``\\label``、``\\cite`` 键都在 bib、花括号配平、标签不重复；
2. RA-L 规定：每张图和表都有编号标签，并且在正文（图表环境之外）至少被引用一次；
3. 裁决 113 与 S4 写作要求的措辞：不得出现 robust、outperform、state of the art、non-inferior、等价说法（comparable、
   on par、equivalent、no difference 等）、速度与下游任务的说法；含 ELU-P 的句子不得把它的低残留写成“代价”；
4. 必须出现的句子：摘要里的三句（SAM 2.1 身份连续率没有提高、ELU-P 残留率更低而撤回的多是仍在原处的物体、节点 F1 只报差值）
   和实例分割主张旁的两条限定（分割近乎理想、推断对象是 5 个种子的训练程序）；方法或协议节里的三项披露（主门修订的时点、
   固定检验顺序的设计时点、身份连续率按共同事件定义）；LLM-op 小表在正文里，表题或表注写明 validation、每前端 1 条、描述性、
   无显著性检验。
例如某节写了 ``\\ref{tab:gate}`` 而没有 ``\\label{tab:gate}``，或摘要里删掉了 “does not improve” 那一句，都会列出来。
它不等于编译通过：版面、页数与溢出由 ``build.sh`` 检查；措辞是否在裁决 113 的边界内仍要逐句复核，这里只拦明显的违规。

Usage (repository root): python paper/tools/check_draft.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
COMMENT = re.compile(r"(?<!\\)%.*")
#: (pattern, why) -- forbidden anywhere in the compiled text (ruling 113; S4 writing rules of 2026-10-08)
FORBIDDEN = (
    (r"\brobust", "ruling 113: no 'robust'"),
    (r"outperform", "ruling 113: no 'outperform(s)'"),
    (r"state[- ]of[- ]the[- ]art", "ruling 113: no 'state of the art'"),
    (r"non-?inferior", "no non-inferiority wording (no margin was registered)"),
    (r"across segmenters", "ruling 113: no 'across segmenters'"),
    (r"\bcomparable\b|\bon par\b|\bequivalen|\bno difference\b|\bindistinguishable\b|\bas good as\b",
     "no equivalence wording (no equivalence test)"),
    (r"\bfaster\b|\bspeed|\befficien|real-time|\bruntime advantage", "no speed or efficiency claim"),
    (r"\bdownstream\b", "no downstream-task claim"),
)
#: phrases that, in a sentence naming ELU-P, would make its lower residual rate a causal 'cost' (LOG-307 A3)
ELU_P_COST = r"at (?:a|the) (?:small |large )?(?:cost|price|expense)|in exchange for|\bpays? for\b|\btrades? off\b"
#: (pattern, what) that must appear in the abstract (ruling 113-1 (a))
ABSTRACT_REQUIRED = (
    (r"identity continuity does not improve", "SAM 2.1: identity continuity does not improve"),
    (r"still in place", "with instance masks ELU-P leaves fewer stale entities, while what it retracts is still in place"),
    (r"Node F1\b.{0,120}?differs from", "node F1 reported as a difference only"),
    (r"almost perfectly|near-ideal", "next to the instance-mask claim: the segmentation is near-ideal"),
    (r"training procedure", "next to the instance-mask claim: the target of inference is the training procedure"),
    (r"five seeds", "next to the instance-mask claim: five seeds"),
)
#: (pattern, what) that must appear in the method or protocol sections (ruling 113-1 (a): disclosure)
DISCLOSURE_REQUIRED = (
    (r"primary hypothesis was revised", "when the primary hypothesis (gate) was revised"),
    (r"fixed order was designed", "when the fixed testing order was designed"),
    (r"same events for every arm", "identity continuity defined over common events"),
)
#: (pattern, what) that must appear in the LLM-op table's title or note (S4 writing rule of 2026-10-08)
LLM_OP_CAPTION_REQUIRED = (
    (r"[Vv]alidation", "validation"),
    (r"one episode per front end", "one episode per front end"),
    (r"[Dd]escriptive", "descriptive"),
    (r"no significance test", "no significance test"),
)


def strip_comments(text: str) -> str:
    return "\n".join(COMMENT.sub("", line) for line in text.splitlines())


def collect(path: Path, problems: list[str], seen: set[Path]) -> str:
    """The text of ``path`` with every ``\\input`` expanded, recording missing inputs."""

    seen.add(path)
    text = strip_comments(path.read_text(encoding="utf-8"))
    parts = []
    position = 0
    for match in re.finditer(r"\\input\{([^}]+)\}", text):
        parts.append(text[position:match.start()])
        target = PAPER / (match.group(1) if match.group(1).endswith(".tex") else match.group(1) + ".tex")
        if not target.exists():
            problems.append(f"{path.relative_to(PAPER)}: \\input{{{match.group(1)}}} does not exist")
        elif target in seen:
            problems.append(f"{path.relative_to(PAPER)}: \\input{{{match.group(1)}}} is included twice")
        else:
            parts.append(collect(target, problems, seen))
        position = match.end()
    parts.append(text[position:])
    return "".join(parts)


def brace_problems(text: str) -> list[str]:
    depth = 0
    for index, char in enumerate(text):
        if char == "{" and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif char == "}" and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth < 0:
                return [f"unbalanced '}}' near: {text[max(0, index - 60):index + 1]!r}"]
    return [] if depth == 0 else [f"{depth} unclosed '{{' in the expanded document"]


def plain(text: str) -> str:
    """Rough prose for phrase checks: drop math, unwrap \\arm{...}/\\op{...}/\\emph{...}, collapse white space."""

    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\(?:arm|op|emph|textbf|textit|mbox)\{([^}]*)\}", r"\1", text)
    text = text.replace("~", " ").replace("--", "-")
    return re.sub(r"\s+", " ", text)


def section(document: str, start: str, end: str | None) -> str:
    begin = document.find(start)
    if begin < 0:
        return ""
    finish = document.find(end, begin) if end else -1
    return document[begin:finish if finish > 0 else len(document)]


def float_problems(document: str) -> list[str]:
    """RA-L: every figure and table is numbered (has a label) and is referred to in the text outside the floats."""

    problems = []
    floats = list(re.finditer(r"\\begin\{(figure\*?|table\*?)\}(.*?)\\end\{\1\}", document, flags=re.S))
    outside = document
    for match in reversed(floats):
        outside = outside[:match.start()] + outside[match.end():]
    for match in floats:
        labels = re.findall(r"\\label\{([^}]+)\}", match.group(2))
        if not labels:
            problems.append(f"a {match.group(1)} has no \\label (every figure and table must be numbered and cited)")
        for label in labels:
            if not re.search(r"\\ref\{" + re.escape(label) + r"\}", outside):
                problems.append(f"{label} is never referred to in the text (outside figures and tables)")
    return problems


def wording_problems(document: str) -> list[str]:
    problems = []
    prose = plain(document)
    for pattern, why in FORBIDDEN:
        for match in re.finditer(pattern, prose, flags=re.I):
            problems.append(f"forbidden wording ({why}): ...{prose[max(0, match.start() - 50):match.end() + 30]}...")
    for sentence in re.split(r"(?<=[.;])\s", prose):
        if "ELU-P" in sentence and re.search(ELU_P_COST, sentence, flags=re.I):
            problems.append(f"ELU-P's lower residual rate written as a cost: {sentence[:160]}")
    abstract = plain(section(document, r"\begin{abstract}", r"\end{abstract}"))
    problems += [f"abstract lacks: {what}" for pattern, what in ABSTRACT_REQUIRED if not re.search(pattern, abstract)]
    method = plain(section(document, r"\section{Method}", r"\section{Results}"))
    problems += [f"method/protocol sections lack the disclosure: {what}" for pattern, what in DISCLOSURE_REQUIRED
                 if not re.search(pattern, method)]
    llm_op = [match.group(0) for match in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", document, flags=re.S)
              if r"\label{tab:llm_op}" in match.group(0)]
    if not llm_op:
        problems.append("the LLM-op table (tab:llm_op) is missing from the main text")
    else:
        text = plain(llm_op[0])
        problems += [f"LLM-op table title or note lacks: {what}" for pattern, what in LLM_OP_CAPTION_REQUIRED
                     if not re.search(pattern, text)]
    return problems


def main() -> int:
    problems: list[str] = []
    document = collect(PAPER / "main.tex", problems, set())
    problems += brace_problems(document)
    labels = re.findall(r"\\label\{([^}]+)\}", document)
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    problems += [f"label defined more than once: {label}" for label in duplicates]
    for reference in sorted(set(re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", document)) - set(labels)):
        problems.append(f"\\ref{{{reference}}} has no \\label")
    bib = (PAPER / "refs.bib").read_text(encoding="utf-8") if (PAPER / "refs.bib").exists() else ""
    keys = set(re.findall(r"@\w+\{([^,\s]+),", bib))
    cited = {key.strip() for group in re.findall(r"\\cite\{([^}]+)\}", document) for key in group.split(",")}
    problems += [f"\\cite{{{key}}} is not in refs.bib" for key in sorted(cited - keys)]
    problems += float_problems(document)
    problems += wording_problems(document)
    unverified = sorted(re.findall(r"@\w+\{([^,\s]+),[^@]*?note\s*=\s*\{[^}]*VERIFY", bib, flags=re.S))
    todos = len(re.findall(r"\\todo\{", document))
    for problem in problems:
        print(f"PROBLEM {problem}")
    print(f"{len(problems)} problem(s); {len(cited)} cited keys, {len(keys)} bib entries; "
          f"{todos} \\todo marker(s); unverified bib entries: {', '.join(unverified) or 'none'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
