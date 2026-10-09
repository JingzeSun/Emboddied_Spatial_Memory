"""List what each reproduction level needs and what this machine is missing (reports only; never downloads or writes).

    python reproduce/check_env.py [--level L0|L1|L2|L3|full|plugin|all] [--data-root PATH] [--deep]

Levels (docs/REPRODUCE.md, section 1):

- ``L0``     recompute every statistic, table and figure from ``results/`` (CPU, no download);
- ``L1``     re-run the evaluation audits from Hugging Face T0 (weights) and T1 (validation and test inputs);
- ``L2``     inspect training and audit records (T2);
- ``L3``     retrain from the released training inputs (T3);
- ``full``   regenerate everything from ProcTHOR-10K (simulator, GPUs, front-end assets, the private salt);
- ``plugin`` run the memory on your own RGB-D stream (docs/PLUGIN.md).

``--data-root`` is the directory given as ``--dest`` to ``ops/vsmt/hf_fetch.py`` (default ``$AUTODL`` or
``/root/autodl-tmp``); ``--deep`` also recomputes the SHA-256 and tree digest of every restored item.  Each line reads
``OK``, ``MISSING`` (required by the level) or ``NOTE`` (optional or informational), with a fix.  The exit code is 0
only when every required item of the requested levels is present.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FREEZE_COMMIT, PAPER_TAG, REPO_ROOT, S3_05_RUN_COMMIT, git, load_json  # noqa: E402

LEVELS = ("L0", "L1", "L2", "L3", "full", "plugin")
RELEASE_MANIFESTS = {layer: REPO_ROOT / "results" / f"vsmt_lean_hf_release_{layer}_2d179b9.json"
                     for layer in ("T0", "T1", "T2", "T3")}
HF_REVISIONS = {"T0": ("Jsun0632/vsmt-lean", "model", "0b2ce7f8bb5de862fd500f10b23e55ba4eebf372"),
                "T1": ("Jsun0632/vsmt-lean-s3-eval", "dataset", "1bb81d27554d3795439172c418dc1416bff0c56e"),
                "T2": ("Jsun0632/vsmt-lean-s3-records", "dataset", "1d45b57add4a89f4586a4b128a0cc7d1a81721c8"),
                "T3": ("Jsun0632/vsmt-lean-s3-train", "dataset", "d0396685929460b65496883b6007df5f6f23c0c9")}
INSTANCE_REID = "vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json"
INSTANCE_REID_SHA256 = "27bf6a10767f68c3b7aef6e76f91e48c9bea8de6750cfb8620e16e0c388217e0"
ASSET_KEYS = {"sam2_repository": None, "sam2_checkpoint": "sam2_checkpoint", "dinov2_repository": None,
              "dinov2_vits14_checkpoint": "dinov2_vit_s14_checkpoint", "dinov2_vitb14_checkpoint": "dinov2_vit_b14_checkpoint"}
PROCTHOR_SHA256 = "d64450ec821aef55351f62885e4d56b3f0d948693af467bb7f6532850ef4fa37"


@dataclass
class Row:
    level: str
    item: str
    ok: bool
    detail: str = ""
    fix: str = ""
    required: bool = True


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(level: str, name: str, *, required: bool = True, want: str | None = None, fix: str | None = None) -> Row:
    try:
        version = getattr(importlib.import_module(name), "__version__", "present")
    except Exception as exc:  # noqa: BLE001 - any import failure means the package is unusable here
        return Row(level, f"python package {name}", False, type(exc).__name__, fix or f"uv pip install {name}", required)
    if want and version != want:
        return Row(level, f"python package {name}", True, f"{version} (the committed figures were written with {want})",
                   f"uv pip install {name}=={want}", required)
    return Row(level, f"python package {name}", True, str(version))


def command(level: str, name: str, *, required: bool, fix: str) -> Row:
    path = shutil.which(name)
    return Row(level, f"command {name}", bool(path), path or "not on PATH", "" if path else fix, required)


def restored(item: dict, root: Path) -> bool:
    """A file of the manifest's size, or a directory with the manifest's file count (``--deep`` checks the digests)."""

    target = root / item["restore_path"]
    if item["kind"] != "tar":
        return target.is_file() and target.stat().st_size == item["bytes"]
    return target.is_dir() and sum(len(files) for _, _, files in os.walk(target)) == item["tree"]["files"]


def layer_rows(level: str, layer: str, root: Path, prefixes: tuple[str, ...], deep: bool, *, required: bool = True) -> list[Row]:
    """Whether the items of one Hugging Face layer under ``prefixes`` are restored under ``root``."""

    manifest = load_json(RELEASE_MANIFESTS[layer])
    rows = [item for item in manifest["items"] if item["path_in_repo"].startswith(prefixes)]
    missing = [item for item in rows if not restored(item, root)]
    repo, kind, revision = HF_REVISIONS[layer]
    select = " ".join(p for p in prefixes if p)
    fix = f"python ops/vsmt/hf_fetch.py --repo {repo} --repo-type {kind} --revision {revision} --dest {root}" +         (f" --select {select}" if select else "")
    detail = f"{len(rows) - len(missing)} of {len(rows)} items restored, {sum(i['bytes'] for i in rows) / 2**30:.1f} GiB in all"
    out = [Row(level, f"{layer} {select or '(whole layer)'}", not missing, detail, fix if missing else "", required)]
    if deep and not missing:
        sys.path.insert(0, str(REPO_ROOT / "ops" / "vsmt"))
        import lean_hf_release as hf

        bad = [item["path_in_repo"] for item in rows if hf.verify_restored(item, root / item["restore_path"])]
        out.append(Row(level, f"{layer} digests", not bad, f"{len(bad)} differ" + (f": {bad[:3]}" if bad else ""),
                       "delete the differing items and fetch them again" if bad else "", required))
    return out


def pinned_salt_sha256() -> str:
    """The salt digest this clone's generator accepts (``S3_SALT_SHA256``; an outside rerun re-pins it)."""

    text = (REPO_ROOT / "ops" / "vsmt" / "lean_s1_02a_pilot.py").read_text(encoding="utf-8")
    return re.search(r'^S3_SALT_SHA256 = "([0-9a-f]{64})"', text, re.MULTILINE).group(1)


def pinned_reid_sha256(mask_source: str) -> str:
    """The ReID-head payload digest this clone pins for a mask source (``lean_assignment``, as the drivers check)."""

    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))
    from vsmt import lean_assignment

    return lean_assignment.reid_weights_sha256_for(mask_source)


def check(levels: set[str], root: Path, deep: bool) -> list[Row]:
    rows: list[Row] = []
    python_ok = sys.version_info[:2] in ((3, 11), (3, 12))
    rows.append(Row("all", "Python 3.11 or 3.12", python_ok, platform.python_version(), "install Python 3.12 (uv python install 3.12)"))
    rows.append(command("all", "git", required=True, fix="install git"))
    if levels & {"L0", "L1", "L2", "L3", "full"}:
        tag = git("rev-parse", "--verify", "--quiet", f"{PAPER_TAG}^{{commit}}", check=False)
        rows.append(Row("L0", f"tag {PAPER_TAG}", bool(tag), tag[:12] or "absent", "git fetch --tags origin"))
        if tag:
            same = not git("diff", "--name-only", FREEZE_COMMIT, tag, "--", "src", "configs", check=False)
            rows.append(Row("L0", f"src/ and configs/ at {PAPER_TAG} equal the freeze {FREEZE_COMMIT[:7]}", same,
                            "" if same else "differ", "fetch the published tag"))
    if "L0" in levels:
        rows += [package("L0", "numpy"), package("L0", "torch"),
                 package("L0", "matplotlib", want="3.10.8", fix="uv pip install matplotlib==3.10.8")]
        for name in ("vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_06_reanalysis_cd3ee83.json",
                     "vsmt_lean_s3_04_freeze_dea8c20.json"):
            rows.append(Row("L0", f"results/{name}", (REPO_ROOT / "results" / name).exists(), "", "git checkout paper-v1 -- results"))
        tex = shutil.which("latexmk") or shutil.which("pdflatex")
        rows.append(Row("L0", "TeX (only for building the PDF)", bool(tex), tex or "not on PATH",
                        "" if tex else "install TeX Live or MiKTeX", required=False))
    if "L1" in levels:
        rows.append(package("L1", "huggingface_hub"))
        run_commit = git("rev-parse", "--verify", "--quiet", f"{S3_05_RUN_COMMIT}^{{commit}}", check=False)
        rows.append(Row("L1", f"S3-05 run commit {S3_05_RUN_COMMIT} in this clone", bool(run_commit), "",
                        "git fetch origin (a full, not shallow, clone)"))
        rows += layer_rows("L1", "T0", root, ("weights/", "reid/", "s3-04-dea8c20/"), deep)
        rows += layer_rows("L1", "T1", root, ("validation/",), deep)
        rows += layer_rows("L1", "T1", root, ("test/",), deep, required=False)
        instance = root / INSTANCE_REID
        present = instance.exists() and sha256(instance) == INSTANCE_REID_SHA256
        rows.append(Row("L1", "instance-mask ReID head (5cea91cf...)", present, "" if present else
                        "not released on Hugging Face", "" if present else
                        "the instance-mask table cannot be re-run from the release; SAM 2.1 can", required=False))
    if "L2" in levels:
        rows += layer_rows("L2", "T2", root, ("",), deep)
        rows.append(Row("L2", "T2 restored apart from T0", False, "T2 restores whole S3-03 run roots, inside which T0 "
                        "restores the round-1 weights; give T2 its own --dest", required=False))
    if "L3" in levels:
        rows += layer_rows("L3", "T3", root, ("",), deep)
        rows += layer_rows("L3", "T1", root, ("validation/",), deep)
        rows += layer_rows("L3", "T0", root, ("exports/", "reid/"), deep)
        rows.append(Row("L3", "stage drivers accept the released data", False,
                        "S3-03 check requires sealed test markers; the released test roots are marked opened (read in S3-05)",
                        "regenerate S3-02 yourself (level full), or see docs/REPRODUCE.md section 1", required=False))
    if "full" in levels:
        autodl = root  # --data-root, which defaults to $AUTODL as in the drivers
        linux = platform.system() == "Linux"
        rows.append(Row("full", "Linux", linux, platform.system(), "use a Linux server"))
        literal = Path("/root/autodl-tmp")
        rows.append(Row("full", "/root/autodl-tmp exists (the generator's disk check and the receipts use this path)",
                        linux and literal.is_dir(), "" if linux else "not checked off Linux",
                        "create it, or make it a link to your data disk ($AUTODL)"))
        rows.append(command("full", "nvidia-smi", required=True, fix="a host with NVIDIA GPUs and drivers"))
        gpus = 0
        if shutil.which("nvidia-smi"):
            listing = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout
            gpus = sum(1 for line in listing.splitlines() if line.startswith("GPU "))
        rows.append(Row("full", "NVIDIA GPUs (the paper used 4 x RTX 5090)", gpus >= 1, f"{gpus} found",
                        "generation and geometry (simulator with Vulkan), the caches and the S1-04 diagnostics need GPUs"))
        main_py = Path(os.environ.get("PY", "/root/miniconda3/bin/python3.12"))
        probe = ("import torch, numpy, sam2, hydra; "
                 "print(torch.__version__, numpy.__version__, 'cuda' if torch.cuda.is_available() else 'no-cuda')")
        result = subprocess.run([str(main_py), "-c", probe], capture_output=True, text=True) if main_py.exists() else None
        output = result.stdout.strip() if result and result.returncode == 0 else ""
        rows.append(Row("full", "main interpreter $PY: torch with CUDA, numpy, sam2, hydra", output.endswith(" cuda"),
                        output or str(main_py),
                        "Python 3.12 with this repository's environment, a CUDA build of torch, hydra-core, omegaconf, "
                        "iopath and sam2 installed from the pinned clone (the paper used torch 2.8.0+cu128, numpy 2.3.2)"))
        sim = Path(os.environ.get("SIM_PY", str(autodl / "vsmt-envs/simulator-py39/bin/python")))
        sim_probe = "import ai2thor, procthor; print(ai2thor.__version__)"
        sim_result = subprocess.run([str(sim), "-c", sim_probe], capture_output=True, text=True) if sim.exists() else None
        sim_version = sim_result.stdout.strip() if sim_result and sim_result.returncode == 0 else ""
        rows.append(Row("full", "simulator interpreter $SIM_PY: ai2thor 5.0.0 and procthor", sim_version == "5.0.0",
                        sim_version or str(sim), "a Python 3.9 environment with ai2thor==5.0.0, procthor at 53d5bd4c, "
                        "pillow and psutil (CloudRendering needs Vulkan)"))
        source = Path(os.environ.get("SOURCE", str(autodl / "vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz")))
        rows.append(Row("full", "ProcTHOR-10K 0.1.2 train.jsonl.gz ($SOURCE)", source.exists() and sha256(source) == PROCTHOR_SHA256,
                        str(source), "train.jsonl.gz from the Git LFS repository github.com/allenai/procthor-10k at "
                        "d54954a8 (52,316,238 bytes)"))
        salt = Path(os.environ.get("SALT_FILE", str(autodl / "vsmt_private/null_window_salt.txt")))
        pinned = pinned_salt_sha256()
        # the generator's rule (_read_private_salt): the SHA-256 of the file's stripped UTF-8 text
        salt_ok = salt.exists() and hashlib.sha256(salt.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest() == pinned
        rows.append(Row("full", "salt matching the generator's S3_SALT_SHA256 ($SALT_FILE)", salt_ok,
                        f"pinned {pinned[:12]}" + ("" if salt.exists() else "; file missing"),
                        "the paper's salt (ruling 37) is not released: write your own and re-pin S3_SALT_SHA256 "
                        "(docs/REPRODUCE.md section 11, outside rerun)"))
        assets = Path(os.environ.get("ASSETS_JSON", str(autodl / "vsmt_private/s103_assets.json")))
        problems: list[str] = []
        if assets.exists():
            listed = json.loads(assets.read_text(encoding="utf-8"))
            registry = {row["asset_id"]: row for row in load_json(REPO_ROOT / "configs/vsmt/lean_s1_assets_capacity_v2.json")["asset_registry"]}
            for key, asset_id in ASSET_KEYS.items():
                if key not in listed or not Path(listed[key]).exists():
                    problems.append(f"{key} missing")
                elif deep and asset_id and sha256(Path(listed[key])) != registry[asset_id]["sha256"]:
                    problems.append(f"{key} digest differs")
        else:
            problems.append("file missing")
        rows.append(Row("full", "front-end assets list ($ASSETS_JSON)", not problems, "; ".join(problems) or
                        ("all five present" + (", digests equal the registry" if deep else " (--deep checks digests)")),
                        "a JSON object mapping sam2_repository, sam2_checkpoint, dinov2_repository, "
                        "dinov2_vits14_checkpoint and dinov2_vitb14_checkpoint to paths (docs/REPRODUCE.md section 11)"))
        for name, variable, relative, source_name, fix in (
                ("SAM 2.1 ReID head", "SAM2_REID", "vsmt_private/exports/reid_head_vitb14_154776d.json", "sam2",
                 "released in T0 (reid/); or your own S1-04 head, re-pinned (docs/REPRODUCE.md section 11)"),
                ("instance-mask ReID head", "INSTANCE_REID", INSTANCE_REID, "simulator_instance_masks",
                 "not released: train it in S1-04 and re-pin it (docs/REPRODUCE.md section 11, outside rerun)")):
            head = Path(os.environ.get(variable, str(autodl / relative)))
            expected = pinned_reid_sha256(source_name)
            try:
                actual = json.loads(head.read_text(encoding="utf-8")).get("sha256") if head.is_file() else None
            except (OSError, ValueError):
                actual = None
            rows.append(Row("full", f"{name} (${variable}) with the pinned payload digest", actual == expected,
                            f"pinned {expected[:12]}; " + (f"found {str(actual)[:12]}" if head.is_file() else f"missing: {head}"),
                            fix))
        disk = shutil.disk_usage(autodl if autodl.exists() else REPO_ROOT).free / 1e9
        rows.append(Row("full", "free disk >= 410 GB (S3-02 alone projected 346.5 GB)", disk >= 410, f"{disk:.0f} GB free",
                        "a larger data disk (the paper's host had 470 GB)"))
        rows.append(command("full", "flock", required=True, fix="util-linux (S3-03 locks its run root)"))
    if "plugin" in levels:
        rows += [package("plugin", "numpy"), package("plugin", "torch"), package("plugin", "huggingface_hub"),
                 package("plugin", "PIL", fix="uv pip install pillow"),
                 package("plugin", "sam2", required=False, fix="pip install git+https://github.com/facebookresearch/sam2@2b90b9f5 "
                                                                "(only to generate masks with SAM 2.1)")]
        cache = Path(os.environ.get("VSMT_MEMORY_CACHE") or Path.home() / ".cache" / "vsmt_memory")
        rows.append(Row("plugin", "weights cache ($VSMT_MEMORY_CACHE)", True, f"{cache} "
                        f"({'present' if cache.exists() else 'created on first use; about 450 MB'})", required=False))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--level", choices=(*LEVELS, "all"), default="L0")
    parser.add_argument("--data-root", type=Path, default=Path(os.environ.get("AUTODL", "/root/autodl-tmp")))
    parser.add_argument("--deep", action="store_true", help="recompute the digests of every restored Hugging Face item")
    args = parser.parse_args(argv)
    levels = set(LEVELS) if args.level == "all" else {args.level}
    print(f"checking the interpreter running this script: {sys.executable} (Python {platform.python_version()})")
    rows = check(levels, args.data_root, args.deep)
    width = max(len(row.item) for row in rows)
    for level in ("all", *LEVELS):
        group = [row for row in rows if row.level == level]
        if not group:
            continue
        print(f"\n[{level}]")
        for row in group:
            status = "OK     " if row.ok else ("MISSING" if row.required else "NOTE   ")
            print(f"  {status} {row.item:{width}s}  {row.detail}")
            if row.fix and not row.ok:
                print(f"          {'':{width}s}  -> {row.fix}")
    missing = [row for row in rows if row.required and not row.ok]
    print(f"\n{'ready' if not missing else 'not ready'} for {args.level}: {len(missing)} required item(s) missing")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
