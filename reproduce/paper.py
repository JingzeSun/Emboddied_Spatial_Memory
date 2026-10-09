"""Reproduce the paper's test results from the committed exports (level L0; CPU only, no download, no test data).

    python reproduce/paper.py [--workers N] [--keep-worktree] [--build-pdf]

Steps, all in a clean worktree of the tag ``paper-v1`` (the state that produced the paper) that the script creates in the
system's temporary directory with ``git worktree add`` and removes afterwards (``--keep-worktree`` keeps it); your
checkout's files are not modified:

1. ``ops/vsmt/s3_06_reanalysis.py run`` recomputes the S3-05 test statistics from the two merged test audits with the
   frozen functions and stops unless they equal the committed ``vsmt_lean_s3_05_statistics_8d58475.json`` value for
   value (D1); it then recomputes the descriptive readings D2-D8;
2. the recomputed D1-D8 are compared field by field with the committed ``vsmt_lean_s3_06_reanalysis_cd3ee83.json``;
3. ``paper/tools/make_tables.py`` and ``make_figures.py`` regenerate Tables II and III and Figures 3 and 4 from the
   committed exports, and the outputs are compared byte for byte with the committed files;
4. optionally (``--build-pdf``, needs TeX) ``paper/tools/build.sh`` builds both PDF versions.

It prints the rows of Table II (Missing residual rate and identity continuity of AssocOnly and VSMT-lean, the one-sided
95% lower bound and the fixed-order step) and writes a report to ``outputs/reproduce/`` that lists every compared field and
file with its SHA-256.  Exit codes: 0 everything
reproduced; 3 a difference (listed); 2 a precondition is missing; 1 an unexpected error.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PAPER_TAG, Refusal, git, load_json, resolve, worktree, write_report  # noqa: E402

STATISTICS = "results/vsmt_lean_s3_05_statistics_8d58475.json"
COMMITTED_REANALYSIS = "results/vsmt_lean_s3_06_reanalysis_cd3ee83.json"
#: Fields of a reanalysis export that describe the run, not the readings; ``inputs`` is compared separately.
RUN_FIELDS = ("code_commit", "started_utc", "written_utc", "environment", "workers", "timing_s", "inputs")
TABLES, FIGURES = "paper/tables", "paper/figures"
#: The matplotlib version that wrote the committed figure PDFs; other versions write other bytes.
FIGURE_MATPLOTLIB = "3.10.8"
FRONTS = (("instance", "simulator_instance_masks", "Simulator instance masks"), ("sam2", "sam2", "SAM 2.1 masks"))
METRICS = (("missing_residual_rate", "MRR (lower is better)"), ("identity_continuity", "IdC"))


def run(step: str, argv: list[str], cwd: Path) -> dict[str, Any]:
    print(f"[paper] {step}: {' '.join(argv[1:])}", flush=True)
    started = time.time()
    result = subprocess.run(argv, cwd=str(cwd), env={**os.environ, "PYTHONUTF8": "1"})
    return {"step": step, "exit": result.returncode, "seconds": round(time.time() - started, 1)}


def compare_reanalysis(recomputed: dict[str, Any], committed: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Fields whose readings differ, and the inputs the tag holds beyond those of the committed run (later exports)."""

    keys = sorted((set(recomputed) | set(committed)) - set(RUN_FIELDS))
    differing = [key for key in keys if recomputed.get(key) != committed.get(key)]
    mine, theirs = recomputed.get("inputs") or {}, committed.get("inputs") or {}
    differing += [f"inputs:{name}" for name in sorted(theirs) if mine.get(name) != theirs[name]]
    return differing, sorted(set(mine) - set(theirs))


def versions() -> dict[str, str | None]:
    """Versions of the packages the recomputation uses."""

    out: dict[str, str | None] = {}
    for name in ("numpy", "torch", "matplotlib"):
        try:
            out[name] = __import__(name).__version__
        except ImportError:
            out[name] = None
    return out


def table_ii(statistics: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows of Table II, from the statistics export that step 1 reproduced value for value."""

    steps = statistics["fixed_sequence"]["steps"]
    rows = []
    for front, source, label in FRONTS:
        block = statistics["fronts"][front]
        for metric, name in METRICS:
            gate = block["primary_gate"]["metrics"][metric]
            number = next(i + 1 for i, s in enumerate(steps) if s["front_end"] == source and metric in s["metrics"])
            step = steps[number - 1]
            rows.append({"front_end": label, "metric": name,
                         "AssocOnly": block["main_table"][metric]["AssocOnly"]["mean"],
                         "VSMT-lean": block["main_table"][metric]["VSMT-lean"]["mean"],
                         "lower_bound": gate["lower_bound_two_level"],
                         "fixed_order_step": f"{number}: " + ("holds" if step["passed"] else "does not hold")})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1),
                        help="processes for the reanalysis bootstrap (default: min(8, CPU count))")
    parser.add_argument("--keep-worktree", action="store_true", help="leave the temporary worktree for inspection")
    parser.add_argument("--build-pdf", action="store_true", help="also build the paper (needs MiKTeX or TeX Live)")
    args = parser.parse_args(argv)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report: dict[str, Any] = {"level": "L0", "tag": PAPER_TAG, "started_utc": started, "python": sys.version.split()[0],
                              "versions": versions(), "steps": [], "differences": [],
                              "hash_note": "SHA-256 of text files is taken over the bytes the scripts write (LF line endings, "
                                           "as stored in git); a Windows checkout with core.autocrlf has CRLF copies"}
    try:
        commit = resolve(PAPER_TAG)
        report["commit"] = commit
        try:
            import matplotlib
        except ImportError as exc:
            raise Refusal(f"matplotlib is needed for the figures: uv pip install matplotlib=={FIGURE_MATPLOTLIB}") from exc
        with worktree(PAPER_TAG, keep=args.keep_worktree) as tree:
            print(f"[paper] worktree of {PAPER_TAG} ({commit[:12]}) at {tree}", flush=True)
            step = run("reanalysis", [sys.executable, "ops/vsmt/s3_06_reanalysis.py", "run", "--workers",
                                      str(args.workers)], tree)
            report["steps"].append(step)
            if step["exit"] != 0:
                report["differences"].append(f"s3_06_reanalysis exited with {step['exit']} (3: the test statistics "
                                             "do not recompute; 2: refused)")
            else:
                recomputed = load_json(tree / f"results/vsmt_lean_s3_06_reanalysis_{commit[:7]}.json")
                differing, extra = compare_reanalysis(recomputed, load_json(tree / COMMITTED_REANALYSIS))
                report["reanalysis_fields_differing"] = differing
                report["reanalysis_inputs_added_after_the_committed_run"] = extra
                report["compared_reanalysis_fields"] = sorted(set(recomputed) - set(RUN_FIELDS))
                committed_inputs = load_json(tree / COMMITTED_REANALYSIS).get("inputs") or {}
                report["compared_reanalysis_inputs"] = {name: (recomputed.get("inputs") or {}).get(name)
                                                        for name in sorted(committed_inputs)}
                report["differences"] += [f"reanalysis field differs from {COMMITTED_REANALYSIS}: {k}" for k in differing]
            for script in ("make_tables.py", "make_figures.py"):
                step = run(script, [sys.executable, f"paper/tools/{script}"], tree)
                report["steps"].append(step)
                if step["exit"] != 0:
                    report["differences"].append(f"{script} exited with {step['exit']}")
            changed = git("diff", "--name-only", "--", TABLES, FIGURES, cwd=tree).splitlines()  # line endings normalised
            report["matplotlib"] = matplotlib.__version__
            report["regenerated_files_differing"] = changed
            report["compared_regenerated_files"] = {
                str(path.relative_to(tree)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                for folder, suffix in ((TABLES, ".tex"), (FIGURES, ".pdf")) for path in sorted((tree / folder).glob(f"*{suffix}"))}
            for name in changed:
                if name.startswith(FIGURES) and matplotlib.__version__ != FIGURE_MATPLOTLIB:
                    report.setdefault("notes", []).append(
                        f"{name} differs in bytes: written with matplotlib {matplotlib.__version__}, the committed figures "
                        f"with {FIGURE_MATPLOTLIB} (uv pip install matplotlib=={FIGURE_MATPLOTLIB} to compare bytes)")
                else:
                    report["differences"].append(f"regenerated file differs from the committed one: {name}")
            if args.build_pdf:
                step = run("build.sh", ["bash", "paper/tools/build.sh"], tree)
                report["steps"].append(step)
                if step["exit"] != 0:
                    report["differences"].append(f"build.sh exited with {step['exit']}")
            report["table_ii"] = table_ii(load_json(tree / STATISTICS))
    except Refusal as exc:
        print(f"[paper] refused: {exc}", file=sys.stderr)
        return 2
    report["written_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path = write_report(f"l0_{PAPER_TAG}_{started.replace(':', '')}.json", report)

    print("\nTable II (test split, read once; means over five seeds):")
    print(f"{'Front end':26s} {'Metric':22s} {'AssocOnly':>9s} {'VSMT-lean':>9s} {'Lower bound':>11s}  Fixed-order step")
    for row in report.get("table_ii", []):
        print(f"{row['front_end']:26s} {row['metric']:22s} {row['AssocOnly']:9.3f} {row['VSMT-lean']:9.3f} "
              f"{row['lower_bound']:11.3f}  {row['fixed_order_step']}")
    for note in report.get("notes", []):
        print(f"note: {note}")
    if report["differences"]:
        print("\nNOT reproduced:\n  " + "\n  ".join(report["differences"]), file=sys.stderr)
        print(f"report: {path}")
        return 3
    figures = "(figure bytes not compared, see the note)" if report.get("notes") else "byte for byte"
    print("\nReproduced: test statistics recomputed value for value (D1), readings D2-D8 equal the committed export, "
          f"tables and figures regenerated {figures}.\nreport: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
