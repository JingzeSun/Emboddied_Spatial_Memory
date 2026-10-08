#!/usr/bin/env python3
"""S4: static checks of the LaTeX draft that need no TeX installation.

白话：本机没有 LaTeX，这个脚本先把编译前最容易出的错查出来。输入是 ``paper/main.tex``、它 ``\\input`` 的各节与表格、
``paper/refs.bib``；输出是问题清单，没有问题时退出码 0。例如某节写了 ``\\ref{tab:gate}`` 而没有任何 ``\\label{tab:gate}``，
或者引了 ``\\cite{dsg2026}`` 而 bib 里没有这个键，都会列出来。它不等于编译通过：版面、溢出和宏包冲突只有真正编译才能发现。

Usage (repository root): python paper/tools/check_draft.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
COMMENT = re.compile(r"(?<!\\)%.*")


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
    unverified = sorted(re.findall(r"@\w+\{([^,\s]+),[^@]*?note\s*=\s*\{[^}]*VERIFY", bib, flags=re.S))
    todos = len(re.findall(r"\\todo\{", document))
    for problem in problems:
        print(f"PROBLEM {problem}")
    print(f"{len(problems)} problem(s); {len(cited)} cited keys, {len(keys)} bib entries; "
          f"{todos} \\todo marker(s); unverified bib entries: {', '.join(unverified) or 'none'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
