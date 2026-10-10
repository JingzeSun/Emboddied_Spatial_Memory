#!/usr/bin/env python3
"""S4: static checks of the LaTeX draft that need no TeX installation.

Reads ``paper/main.tex``, the sections, tables and TikZ figures it inputs, and ``paper/refs.bib``; prints the problems
found and exits with 0 when there are none. Five groups of checks:
1. Structure: every ``\\input`` file exists, every ``\\ref`` has a ``\\label``, every ``\\cite`` key is in the
   bibliography, braces balance, labels are unique.
2. RA-L rules: every figure and table carries a label and is referenced at least once in the running text (outside
   the float environments).
3. Wording required by ruling 113 and the S4 writing rules: no "robust", "outperform", "state of the art",
   "non-inferior", no equivalence phrases ("comparable", "on par", "equivalent", "no difference", ...), no speed or
   downstream-task claims, and no sentence presenting ELU-P's lower residual rate as a "cost".
4. Required sentences: the three abstract statements (SAM 2.1 identity continuity does not improve; ELU-P's lower
   residual rate comes with retractions of objects still in place; node F1 as a difference only) and the two
   qualifiers next to the instance-mask claim (near-ideal segmentation; the inference target is the training
   procedure with five seeds); the three disclosures in the method or protocol sections (timing of the gate revision,
   design timing of the fixed testing order, identity continuity over common events); the LLM-op table in the main
   text, with a caption or note stating validation, one episode per front end, descriptive, no significance test.
5. Generative-AI disclosure (IEEE policy; user approval of 2026-10-10): ``main.tex`` inputs the acknowledgment inside
   ``\\iffinalversion`` and the acknowledgment states the use of generative AI.
Passing these checks is not a successful build: layout, page count and overfull boxes are checked by ``build.sh``,
and whether the wording stays within ruling 113 still needs a sentence-by-sentence review; this script only catches
clear violations.

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
#: the acknowledgment carrying the generative-AI disclosure, printed in the final version only
ACKNOWLEDGMENT_INPUT = r"\iffinalversion\input{sections/acknowledgment}\fi"
AI_DISCLOSURE = "Generative AI use"


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


def ai_disclosure_problems() -> list[str]:
    """The generative-AI disclosure exists and only the final version prints it (the review version is anonymous)."""

    problems = []
    if ACKNOWLEDGMENT_INPUT not in strip_comments((PAPER / "main.tex").read_text(encoding="utf-8")):
        problems.append(f"main.tex lacks {ACKNOWLEDGMENT_INPUT} (generative-AI disclosure, final version only)")
    acknowledgment = PAPER / "sections" / "acknowledgment.tex"
    if not acknowledgment.exists() or AI_DISCLOSURE not in strip_comments(acknowledgment.read_text(encoding="utf-8")):
        problems.append(f"sections/acknowledgment.tex lacks the generative-AI disclosure ('{AI_DISCLOSURE}')")
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
    problems += ai_disclosure_problems()
    unverified = sorted(re.findall(r"@\w+\{([^,\s]+),[^@]*?note\s*=\s*\{[^}]*VERIFY", bib, flags=re.S))
    todos = len(re.findall(r"\\todo\{", document))
    for problem in problems:
        print(f"PROBLEM {problem}")
    print(f"{len(problems)} problem(s); {len(cited)} cited keys, {len(keys)} bib entries; "
          f"{todos} \\todo marker(s); unverified bib entries: {', '.join(unverified) or 'none'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
