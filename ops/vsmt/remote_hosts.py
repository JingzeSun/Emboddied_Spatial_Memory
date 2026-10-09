#!/usr/bin/env python3
"""Remote CPU hosts for the S3 job pools (user 2026-10-04: S3-03 and the CPU-only stages after it on several rented hosts).

Most of the remaining S3-03 work is validation audits (one core per audit job, independent of each other), several days on a
32-core CPU host. This module lets the same job pool hand some jobs to other CPU hosts, while the jobs' states, logs and
results stay recorded once, on the coordinator (the host running the driver):

  * ``setup``: copies from the coordinator, at the same absolute paths, what a worker needs: the same Python environment, the
    same code worktree, the validation raw data / geometry / both caches, the ReID heads and, only if trainings are allowed,
    the round-0 records they read.
  * ``admit``: the admission check; only when everything passes is ``admitted: true`` written to
    ``<run root>/hosts/<name>.json``: reachable with rsync present; identical Python / torch / numpy versions; identical
    sha256 of every code file and every static input; a few audits the coordinator has finished rerun on the worker and
    bit-identical to the coordinator's (except volatile fields such as times; the same comparison as the ruling-104-2
    determinism probe); with trainings allowed, also the weight digest of one short training.
  * ``remote-run``: every job the pool sends to a worker is run by this small process on the coordinator: it first makes the
    job's output location on the worker equal to the coordinator's (pushed if the coordinator has it, deleted on the worker
    otherwise), pushes the small inputs the job needs (training heads, records), runs the same command on the worker over ssh
    (inside the same run-measured wrapper), pulls a training's outputs (epoch checkpoints included) back at intervals, pulls
    the outputs and the memory receipt back when the job ends, and exits with the job's own exit code; on a connection or
    transfer failure it exits 75, and the pool requeues the job and suspends the host (``hosts/<name>.suspended``).

S3-05 (ruling 107-3): the job kind ``test`` can only appear after S3-05 has unsealed test -- its static inputs (the four test
roots and the S3-02 seal) are in the ``inputs.json`` written after unsealing, so ``setup --kinds test`` has nothing to copy
before; at admission the digests are recomputed file by file on the worker against the seal (``verify_seal``; the markers
must have been opened by this receipt) and recorded in the test read record (``record_copy``); the admission audits use
finished validation audits of the S3-03 run root (``--reference-run-root``), compared bit for bit at the frozen commit,
without reading test.

Inputs: the coordinator's run root and the worker's address / port. Outputs: ``hosts/<name>.json`` (admission record and
budget) and the results each remote job pulls back. Example: once a 32-core worker is admitted, audits that do not fit on
the coordinator go to it, each result returns to its original path on the coordinator, and merges and readings are
unchanged. It changes no job's command, inputs or scientific scope, only the host a job runs on; admission has checked that
the worker's results are bit-identical to the coordinator's. Key: a dedicated key on the coordinator (default
``/root/.ssh/vsmt_workers_ed25519``, overridable by ``VSMT_WORKER_KEY``) whose public key is in the worker's
``authorized_keys``; never a password (BatchMode).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for _item in (ROOT / "src", HERE.parent):
    if str(_item) not in sys.path:
        sys.path.insert(0, str(_item))
STAGE = "vsmt.lean.remote_hosts.v1"
HOSTS_DIR = "hosts"
TRANSPORT_EXIT = 75  # EX_TEMPFAIL: the job never ran to an end that could be read back; the pool requeues it
DEFAULT_KEY = "/root/.ssh/vsmt_workers_ed25519"
KNOWN_HOSTS = "/root/.ssh/vsmt_workers_known_hosts"
#: A remote host keeps this much back from its cgroup, as the coordinator does (ruling 104-3).
RESERVE_CORES = 2
RESERVE_GIB = 8.0
#: The free disk a remote host must have before a job starts there.
MIN_REMOTE_FREE_GIB = 10.0
#: How often a running job's outputs are pulled back (the trainings' epoch-end checkpoints).
PULL_EVERY_SECONDS = 600.0
RSYNC_RETRIES = 3


class RemoteError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RemoteError(code)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# the hosts a pool may use
# --------------------------------------------------------------------------

class Host:
    """One admitted remote host as the pool sees it: where it is, what it may run, and its budget."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.name = str(payload["name"])
        self.address = str(payload["address"])
        self.port = int(payload["port"])
        self.user = str(payload.get("user") or "root")
        self.key = str(payload.get("key") or DEFAULT_KEY)
        self.cores = int(payload["budget_cores"])
        self.gib = float(payload["budget_gib"])
        self.kinds = tuple(payload.get("kinds") or ())

    def __repr__(self) -> str:
        return f"Host({self.name}, {self.address}:{self.port}, {self.cores} cores, {self.gib} GiB, {list(self.kinds)})"


def hosts_dir(run_root: Path) -> Path:
    return Path(run_root) / HOSTS_DIR


def suspended_marker(run_root: Path, name: str) -> Path:
    return hosts_dir(run_root) / f"{name}.suspended"


def load_hosts(run_root: Path) -> list[Host]:
    """The admitted hosts that are neither paused (``"paused": true``) nor suspended (a ``<name>.suspended`` marker)."""

    out = []
    folder = hosts_dir(run_root)
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            payload = load_json(path)
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict) or payload.get("stage") != STAGE or not payload.get("admitted") or payload.get("paused"):
            continue
        if suspended_marker(run_root, str(payload.get("name"))).exists():
            continue
        out.append(Host(payload))
    return out


def suspend(run_root: Path, name: str, reason: str) -> None:
    write_json(suspended_marker(run_root, name), {"name": name, "reason": reason, "at_utc": utc_now(),
                                                  "resume": "remove this file once the host is reachable again"})


# --------------------------------------------------------------------------
# ssh and rsync
# --------------------------------------------------------------------------

def ssh_command() -> list[str]:
    return shlex.split(os.environ.get("VSMT_REMOTE_SSH", "ssh"))


def rsync_command() -> list[str]:
    return shlex.split(os.environ.get("VSMT_REMOTE_RSYNC", "rsync"))


def ssh_options(host: Host) -> list[str]:
    return ["-i", host.key, "-p", str(host.port), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={KNOWN_HOSTS}", "-o", "ConnectTimeout=30",
            "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=8"]


def ssh_argv(host: Host, command: str) -> list[str]:
    return [*ssh_command(), *ssh_options(host), f"{host.user}@{host.address}", command]


def rsync_shell(host: Host) -> str:
    return shlex.join([*ssh_command(), *ssh_options(host)])


def push_argv(host: Host, path: str, *, delete: bool = False) -> list[str]:
    """Copy ``path`` (a file or a directory, absolute) to the same absolute path on the host."""

    _require(os.path.isabs(path), f"push_path_not_absolute:{path}")
    return [*rsync_command(), "-a", "--relative", *(["--delete"] if delete else []), "-e", rsync_shell(host), path,
            f"{host.user}@{host.address}:/"]


def relay_argv(relay: Host, target: Host, path: str, *, key: str) -> list[str]:
    """Ruling 107-3: copy ``path`` from a relay host (which already holds it, at the same absolute path) to the target host.

    The rsync runs on the relay with ``key`` there, a key the target accepts (placed on the relay by the operator, with the
    user's consent); hosts in one region copy far faster to each other than from the coordinator's gateway."""

    _require(os.path.isabs(path), f"relay_path_not_absolute:{path}")
    inner = shlex.join(["ssh", "-i", key, "-p", str(target.port), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                        "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=30"])
    command = shlex.join(["rsync", "-a", "--relative", "-e", inner, path, f"{target.user}@{target.address}:/"])
    return ssh_argv(relay, command)


def pull_argv(host: Host, path: str) -> list[str]:
    """Copy ``path`` from the host back to the same absolute path here."""

    _require(os.path.isabs(path), f"pull_path_not_absolute:{path}")
    return [*rsync_command(), "-a", "--relative", "-e", rsync_shell(host), f"{host.user}@{host.address}:{path}", "/"]


def remote_job_command(argv: Sequence[str], *, cwd: str, env: Mapping[str, str], pidfile: str) -> str:
    """The shell line the host runs: in the same working directory, with the job's thread variables, recording its group."""

    settings = [f"{key}={value}" for key, value in sorted(env.items())]
    return (f"cd {shlex.quote(cwd)} && echo $$ > {shlex.quote(pidfile)} && "
            f"exec env {' '.join(shlex.quote(item) for item in settings)} {shlex.join(list(argv))}")


def stop_stale_command(pidfile: str, marker: str) -> str:
    """Stop an earlier run of the same job on the host (after a lost connection): only the group whose leader names ``marker``."""

    q = shlex.quote
    return (f"if [ -f {q(pidfile)} ]; then P=$(cat {q(pidfile)}); "
            f"if ps -o args= -p \"$P\" 2>/dev/null | grep -qF -- {q(marker)}; then kill -TERM -- -\"$P\" 2>/dev/null; sleep 2; "
            f"kill -KILL -- -\"$P\" 2>/dev/null; fi; rm -f {q(pidfile)}; fi")


def owned_paths_plan(pulls: Sequence[str], *, run_root: str, exists=os.path.exists) -> tuple[list[str], list[str]]:
    """Before a job runs remotely its own outputs there are made equal to the coordinator's: pushed (with --delete) where they
    exist here, removed there where they do not (a stale receipt or a half-written audit of an earlier attempt).  Only paths
    inside the run root are ever removed."""

    root = run_root.rstrip("/") + "/"
    push, remove = [], []
    for path in pulls:
        _require(path.startswith(root), f"owned_path_outside_the_run_root:{path}")
        (push if exists(path) else remove).append(path)
    return push, remove


def exit_from(rss: Mapping[str, Any] | None, ssh_exit: int) -> int:
    """The job's own exit (as run-measured recorded it) when its receipt came back, otherwise a transport failure."""

    if rss is not None and isinstance(rss.get("exit"), int):
        return int(rss["exit"])
    return TRANSPORT_EXIT


def _run(argv: Sequence[str], *, retries: int = 1, capture: bool = True) -> subprocess.CompletedProcess:
    last = None
    for attempt in range(max(1, retries)):
        last = subprocess.run(list(argv), capture_output=capture, text=True)
        if last.returncode == 0:
            return last
        time.sleep(min(30, 5 * (attempt + 1)))
    return last


@contextlib.contextmanager
def host_lock(run_root: Path, name: str) -> Iterator[None]:
    """One push at a time per host: several trainings dispatched together push the same record roots."""

    path = hosts_dir(run_root) / f"{name}.push.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        try:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX)
        except ImportError:  # not on Linux (tests on Windows): no lock
            pass
        yield


def host_by_name(run_root: Path, name: str) -> Host:
    path = hosts_dir(run_root) / f"{name}.json"
    _require(path.exists(), f"host_unknown:{name}")
    return Host(load_json(path))


# --------------------------------------------------------------------------
# remote-run: one job on a host
# --------------------------------------------------------------------------

def cmd_remote_run(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    host = host_by_name(run_root, args.host)
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    _require(bool(command), "remote_run_needs_a_command")
    env = dict(item.split("=", 1) for item in args.env or [])
    rss = str(Path(args.rss).resolve())
    pidfile = rss + ".pid"
    pulls = [str(Path(p)) for p in args.pull or []]

    def say(text: str) -> None:
        print(f"[remote-run {host.name}] {text}", flush=True)

    def transport(text: str) -> int:
        say(f"transport failure: {text}")
        return TRANSPORT_EXIT

    owned_push, owned_remove = owned_paths_plan(pulls, run_root=str(run_root))
    prepare = [stop_stale_command(pidfile, rss), f"mkdir -p {shlex.quote(str(Path(rss).parent))}", f"rm -f {shlex.quote(rss)}"]
    prepare += [f"rm -rf -- {shlex.quote(path)}" for path in owned_remove]
    prepare.append(f"df -Pk {shlex.quote(str(run_root))} | tail -1 | awk '{{print $4}}'")
    done = _run(ssh_argv(host, " ; ".join(prepare)), retries=RSYNC_RETRIES)
    if done.returncode != 0:
        return transport(f"prepare exit {done.returncode}: {(done.stderr or '').strip()[-300:]}")
    try:
        free_gib = int((done.stdout or "").strip().splitlines()[-1]) / 2 ** 20
    except (ValueError, IndexError):
        return transport(f"cannot read the free disk: {done.stdout!r}")
    if free_gib < MIN_REMOTE_FREE_GIB:
        return transport(f"{round(free_gib, 1)} GiB free on the host (< {MIN_REMOTE_FREE_GIB})")
    with host_lock(run_root, host.name):
        for path in [p for p in args.push or [] if os.path.exists(p)]:
            done = _run(push_argv(host, path), retries=RSYNC_RETRIES)
            if done.returncode != 0:
                return transport(f"push {path}: exit {done.returncode} {(done.stderr or '').strip()[-300:]}")
        for path in owned_push:
            done = _run(push_argv(host, path, delete=True), retries=RSYNC_RETRIES)
            if done.returncode != 0:
                return transport(f"push {path}: exit {done.returncode} {(done.stderr or '').strip()[-300:]}")

    def pull_all() -> bool:
        ok = True
        for path in pulls:
            done = _run(pull_argv(host, path), retries=RSYNC_RETRIES)
            # 23: the path does not exist there (e.g. a job that wrote nothing); anything else is a failure
            if done.returncode not in (0, 23):
                ok = False
                say(f"pull {path}: exit {done.returncode} {(done.stderr or '').strip()[-200:]}")
        return ok

    say(f"start: {shlex.join(command)[:300]}")
    process = subprocess.Popen(ssh_argv(host, remote_job_command(command, cwd=args.cwd, env=env, pidfile=pidfile)))
    stopping = threading.Event()

    def on_term(signum, frame):  # the pool was stopped: stop the job on the host, bring back what it finished, then end
        stopping.set()
        subprocess.run(ssh_argv(host, stop_stale_command(pidfile, rss)), capture_output=True, timeout=60)
        process.terminate()
        try:  # finished audit configurations and the last training checkpoint are whole files (written by rename)
            for path in pulls:
                subprocess.run(pull_argv(host, path), capture_output=True, timeout=300)
        except Exception:
            pass
        sys.exit(128 + signum)

    signal.signal(signal.SIGTERM, on_term)
    last_pull = time.time()
    while process.poll() is None:
        time.sleep(5)
        if args.pull_every and time.time() - last_pull >= float(args.pull_every) and pulls:
            pull_all()  # a failure here is not fatal: the final pull decides
            last_pull = time.time()
    ssh_exit = process.returncode
    outputs_ok = pull_all()
    rss_back = _run(pull_argv(host, rss), retries=RSYNC_RETRIES)
    payload = None
    if rss_back.returncode == 0 and os.path.exists(rss):
        try:
            payload = load_json(Path(rss))
        except ValueError:
            payload = None
    if payload is not None:  # the receipt records where the job ran
        payload["host"] = host.name
        write_json(Path(rss), payload)
    _run(ssh_argv(host, f"rm -f {shlex.quote(pidfile)}"))
    code = exit_from(payload, ssh_exit)
    if code == TRANSPORT_EXIT:
        return transport(f"no receipt back (ssh exit {ssh_exit})")
    if not outputs_ok:
        return transport("the outputs did not come back")
    say(f"end: exit {code}")
    return code


# --------------------------------------------------------------------------
# setup and admission (run on the coordinator)
# --------------------------------------------------------------------------

def static_paths(run_root: Path, *, kinds: Sequence[str]) -> list[str]:
    """What every job a host may run reads and no job pushes: the environment and the validation inputs (the code is checked
    file by file on its own, ``code_files``)."""

    inputs = load_json(Path(run_root) / "inputs.json")
    roots = inputs["roots"]
    fronts = list(inputs.get("fronts") or roots["cache"].keys())
    paths = [str(Path(sys.executable).resolve().parents[1])]  # the python prefix (…/miniconda3)
    if "audit" in kinds:
        paths += [roots["raw"]["validation"], roots["geometry"]["validation"]]
        paths += [roots["cache"][front]["validation"] for front in fronts]
    if "test" in kinds:  # ruling 107-3: S3-05's run root after unsealing -- the opened test roots, the seal and the freeze receipt
        _require("test" in roots["raw"] and "seal" in inputs, "test_kind_needs_the_s3_05_inputs_after_unsealing")
        paths += [roots["raw"]["test"], roots["geometry"]["test"], *(roots["cache"][front]["test"] for front in fronts)]
        paths += [inputs["seal"]["file"], inputs["receipt"]["path"]]
        # the admission reruns S3-03's validation audits there: the reference run's validation inputs come along
        reference = load_json(Path(inputs["s3_03_run_root"]) / "inputs.json")["roots"]
        paths += [reference["raw"]["validation"], reference["geometry"]["validation"]]
        paths += [reference["cache"][front]["validation"] for front in fronts]
    paths += [str(inputs["reid"][front]["file"]) for front in fronts]
    if any(kind.startswith("train") for kind in kinds):
        paths += [str(Path(run_root) / front / "round0") for front in fronts]
    return sorted(set(paths))


#: ruling 107-3: files beside an opened test root that change after opening (the read record logs every copy, a marker or record
#: may leave a .tmp behind): never compared -- the seal check on the host covers the test bytes themselves
UNCOMPARED_NAMES = ("TEST_READ.json", "TEST_SEALED.json")


def skipped(path: str) -> bool:
    """Byte code written on import differs in what exists, not in what runs: never compared; nor the test roots' bookkeeping."""

    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return "/__pycache__/" in path or path.endswith((".pyc", ".tmp")) or name in UNCOMPARED_NAMES


def digest_tree(paths: Sequence[str]) -> dict[str, list[Any]]:
    """Every file under each path: size and sha256."""

    out: dict[str, list[Any]] = {}
    for top in paths:
        top_path = Path(top)
        files = [top_path] if top_path.is_file() else sorted(p for p in top_path.rglob("*") if p.is_file() and not skipped(str(p)))
        for path in files:
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                for block in iter(lambda: handle.read(1 << 22), b""):
                    digest.update(block)
            out[str(path)] = [path.stat().st_size, digest.hexdigest()]
    return out


def git_common_dir() -> str:
    found = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--git-common-dir"], capture_output=True, text=True, check=True).stdout.strip()
    return str((ROOT / found).resolve()) if not os.path.isabs(found) else found


def git_head(cwd: Path = ROOT) -> str:
    return subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def code_files() -> list[str]:
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
    return [str(ROOT / name) for name in listed if (ROOT / name).is_file()]


FACTS = """
import json, os, platform, shutil, sys
facts = {"python": sys.version.split()[0], "executable": sys.executable}
for name in ("torch", "numpy", "scipy"):
    try:
        facts[name] = __import__(name).__version__
    except Exception as exc:
        facts[name] = "missing:" + type(exc).__name__
try:
    facts["torch_threads_default"] = __import__("torch").get_num_threads()
except Exception:
    pass
model = ""
try:
    model = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
except Exception:
    pass
facts["cpu_model"] = model
def read(path):
    try:
        return open(path).read().strip()
    except OSError:
        return None
cpu = read("/sys/fs/cgroup/cpu.max")
facts["cpu_quota"] = (int(cpu.split()[0]) // int(cpu.split()[1])) if cpu and cpu.split()[0] != "max" else os.cpu_count()
memory = read("/sys/fs/cgroup/memory.max")
facts["memory_bytes"] = int(memory) if memory and memory != "max" else None
facts["rsync"] = shutil.which("rsync")
print(json.dumps(facts))
"""


def facts_here() -> dict[str, Any]:
    done = subprocess.run([sys.executable, "-c", FACTS], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def remote_python(host: Host, code: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"
    return subprocess.run(ssh_argv(host, command), capture_output=True, text=True, input=stdin)


DIGEST_REMOTE = """
import hashlib, json, sys
from pathlib import Path
out = {}
for top in json.load(sys.stdin):
    p = Path(top)
    files = [p] if p.is_file() else (sorted(q for q in p.rglob("*") if q.is_file() and "/__pycache__/" not in str(q)
                                            and not str(q).endswith((".pyc", ".tmp"))
                                            and q.name not in ("TEST_READ.json", "TEST_SEALED.json")) if p.exists() else [])
    for f in files:
        d = hashlib.sha256()
        with open(f, "rb") as h:
            for b in iter(lambda: h.read(1 << 22), b""):
                d.update(b)
        out[str(f)] = [f.stat().st_size, d.hexdigest()]
print(json.dumps(out))
"""

DIGEST_FILES_REMOTE = """
import hashlib, json, os, sys
out = {}
for f in json.load(sys.stdin):
    if os.path.isfile(f):
        out[f] = hashlib.sha256(open(f, "rb").read()).hexdigest()
print(json.dumps(out))
"""


def cmd_setup(args: argparse.Namespace) -> int:
    """Copy the environment, the code and the static inputs to the host, each to the same absolute path."""

    run_root = Path(args.run_root)
    kinds = [k for k in args.kinds.split(",") if k]
    host = Host({"name": args.name, "address": args.address, "port": args.port, "key": args.key, "budget_cores": 1,
                 "budget_gib": 1.0, "kinds": kinds})
    # and this worktree with the repository it belongs to, so that `git rev-parse HEAD` (the receipts' code commit) works there
    paths = [*static_paths(run_root, kinds=kinds), git_common_dir(), str(ROOT)]
    relay = host_by_name(run_root, args.relay_from) if args.relay_from else None
    print(f"[setup {args.name}] {len(paths)} paths to {args.address}:{args.port}"
          + (f" relayed from {relay.name}" if relay else ""), flush=True)
    for path in paths:
        started = time.time()
        argv = relay_argv(relay, host, path, key=args.relay_key) if relay else push_argv(host, path)
        done = _run(argv, retries=RSYNC_RETRIES, capture=False)
        print(f"[setup {args.name}] {path}: exit {done.returncode}, {round(time.time() - started)} s", flush=True)
        if done.returncode != 0:
            return 1
    print(f"[setup {args.name}] done; next: admit", flush=True)
    return 0


def local_static_manifest(run_root: Path, paths: Sequence[str]) -> dict[str, list[Any]]:
    """The coordinator's digests of the static inputs (computed once per set of paths and kept)."""

    key = hashlib.sha256(json.dumps(sorted(paths)).encode("utf-8")).hexdigest()[:16]
    cached = hosts_dir(run_root) / f"static_manifest_{key}.json"
    if cached.exists():
        return load_json(cached)["files"]
    files = digest_tree(paths)
    write_json(cached, {"paths": sorted(paths), "files": files, "written_utc": utc_now()})
    return files


def admission_audits(run_root: Path, per_front: int, *, scratch_root: Path | None = None) -> list[tuple[str, str, list[str], Path]]:
    """Finished rule-arm audits to run again on the host: (front, episode, argv with a scratch output root, original audit).

    ``run_root`` is the S3-03 run whose validation audits are the reference; the scratch outputs go under ``scratch_root`` (the
    admitting run's root; S3-05 admits against S3-03's audits without writing into S3-03's root, ruling 107-3)."""

    sys.path.insert(0, str(HERE.parent))
    import lean_s2_05_node_audit as audit
    import s3_03_manifest as manifest

    ctx = manifest.load_context(run_root)
    scratch_base = Path(scratch_root) if scratch_root is not None else Path(run_root)
    chosen = []
    for front in ctx.fronts:
        frames = ctx.frames(front, "validation")
        configs = list(enumerate(manifest.audit_configs("TAF")))
        found = []
        for episode in sorted(frames, key=frames.get):
            for index, config in configs:
                original = ctx.group_root(front, "TAF", index, None) / episode / "TAF" / audit.AUDIT_FILE_NAME
                if original.exists():
                    found.append((episode, index, config, original))
                    break
            if len(found) >= per_front:
                break
        for episode, index, config, original in found:
            scratch = scratch_base / HOSTS_DIR / "admission" / front / episode
            argv = ctx.audit(front, episode, "TAF", None, [(index, config)])
            argv[argv.index("--configs") + 1] = json.dumps([{"config": config, "output_root": str(scratch)}])
            chosen.append((front, episode, argv, original))
    return chosen


def cmd_admit(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    kinds = [k for k in args.kinds.split(",") if k]
    probe = Host({"name": args.name, "address": args.address, "port": args.port, "key": args.key, "budget_cores": 1,
                  "budget_gib": 1.0, "kinds": kinds})
    checks: dict[str, Any] = {}
    problems: list[str] = []

    def note(name: str, ok: bool, detail: Any) -> None:
        checks[name] = {"ok": bool(ok), "detail": detail}
        print(f"[admit {args.name}] {name}: {'ok' if ok else 'FAILED'} {json.dumps(detail)[:300]}", flush=True)
        if not ok:
            problems.append(name)

    done = remote_python(probe, FACTS)
    if done.returncode != 0:
        note("reachable", False, (done.stderr or "").strip()[-300:])
        return finish_admission(run_root, args, kinds, checks, problems, None)
    remote = json.loads(done.stdout)
    local = facts_here()
    note("reachable", True, {"cpu_model": remote.get("cpu_model")})
    note("rsync", bool(remote.get("rsync")), remote.get("rsync"))
    same = {k: [local.get(k), remote.get(k)] for k in ("python", "executable", "torch", "numpy", "scipy")}
    note("versions", all(a == b for a, b in same.values()), same)
    files = code_files()
    done = remote_python(probe, DIGEST_FILES_REMOTE, stdin=json.dumps(files))
    there = json.loads(done.stdout) if done.returncode == 0 else {}
    here = {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
    differing = sorted(f for f in files if here[f] != there.get(f))
    head = git_head()
    done = subprocess.run(ssh_argv(probe, f"git -C {shlex.quote(str(ROOT))} rev-parse HEAD"), capture_output=True, text=True)
    note("code", not differing and done.stdout.strip() == head,
         {"files": len(files), "differing": differing[:10], "head": [head, done.stdout.strip()]})
    paths = static_paths(run_root, kinds=kinds)
    here_static = local_static_manifest(run_root, paths)
    done = remote_python(probe, DIGEST_REMOTE, stdin=json.dumps(paths))
    there_static = json.loads(done.stdout) if done.returncode == 0 else {}
    missing = sorted(set(here_static) - set(there_static))
    differing = sorted(f for f in here_static if f in there_static and there_static[f] != here_static[f])
    note("static_inputs", not missing and not differing,
         {"files": len(here_static), "missing": missing[:10], "differing": differing[:10]})
    if "test" in kinds and not problems:  # ruling 107-3: the copied test roots equal the seal there, recorded in the read record
        from vsmt import lean_test_seal

        inputs = load_json(run_root / "inputs.json")
        seal = {k: v for k, v in load_json(Path(inputs["seal"]["file"])).items() if k != "seal_sha256"}
        code = (f"import json, sys; sys.path.insert(0, {str(ROOT / 'src')!r}); from vsmt import lean_test_seal as ts; "
                f"seal = json.load(open({inputs['seal']['file']!r})); seal = {{k: v for k, v in seal.items() if k != 'seal_sha256'}}; "
                f"print(json.dumps(ts.verify_seal(seal, opened_by={inputs['receipt_sha256']!r})))")
        done = remote_python(probe, code)
        found = json.loads(done.stdout) if done.returncode == 0 else [f"verify_failed_to_run:{(done.stderr or '').strip()[-200:]}"]
        entry = lean_test_seal.record_copy(seal, host=args.name, problems=found)
        note("test_copy_matches_the_seal", not found, entry)
    if ("audit" in kinds or "test" in kinds) and not problems:
        import lean_s2_05_node_audit as audit

        rows = []
        if "test" in kinds:  # S3-05 admits against the S3-03 run its inputs name (ruling 107-3); a different one is refused
            named = load_json(run_root / "inputs.json")["s3_03_run_root"]
            _require(not args.reference_run_root or str(Path(args.reference_run_root).resolve()) == str(Path(named).resolve()),
                     "reference_run_root_differs_from_the_s3_05_inputs")
            reference = Path(named)
        else:
            reference = Path(args.reference_run_root) if args.reference_run_root else run_root
        for front, episode, argv, original in admission_audits(reference, args.audits_per_front, scratch_root=run_root):
            scratch = json.loads(argv[argv.index("--configs") + 1])[0]["output_root"]
            command = remote_job_command(argv, cwd=str(ROOT), env={"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                                                                      "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"},
                                         pidfile=f"/tmp/vsmt_admission_{front}_{episode}.pid")
            ran = subprocess.run(ssh_argv(probe, f"rm -rf {shlex.quote(scratch)} ; " + command), capture_output=True, text=True)
            back = _run(pull_argv(probe, scratch), retries=RSYNC_RETRIES)
            rerun = Path(scratch) / episode / "TAF" / audit.AUDIT_FILE_NAME
            identical = (ran.returncode == 0 and back.returncode == 0 and rerun.exists()
                         and audit.comparable_metrics(load_json(original)) == audit.comparable_metrics(load_json(rerun)))
            rows.append({"front": front, "episode": episode, "exit": ran.returncode, "identical": identical})
        note("audit_determinism", bool(rows) and all(r["identical"] for r in rows), rows)
    if any(k.startswith("train") for k in kinds) and not problems:
        rows = []
        inputs = load_json(run_root / "inputs.json")
        for front in list(inputs.get("fronts") or ["instance", "sam2"]):
            out = run_root / HOSTS_DIR / "admission" / f"train_probe_{front}.json"
            argv = [sys.executable, str(HERE.parent / "s3_03_train.py"), "probe", "--source",
                    f"{run_root / front / 'round0'}:ELU-P:teacher", "--arm", "VSMT-lean", "--round", "0", "--houses",
                    str(args.train_houses), "--epochs", "1", "--threads", "1", "--foreach"]
            env = {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}
            here_run = subprocess.run([*argv, "--out", str(out)], capture_output=True, text=True, cwd=str(ROOT), env={**os.environ, **env})
            remote_out = str(out) + ".remote"
            ran = subprocess.run(ssh_argv(probe, remote_job_command([*argv, "--out", remote_out], cwd=str(ROOT), env=env,
                                                                    pidfile=f"/tmp/vsmt_admission_train_{front}.pid")),
                                 capture_output=True, text=True)
            back = _run(pull_argv(probe, remote_out), retries=RSYNC_RETRIES)
            ok = here_run.returncode == 0 and ran.returncode == 0 and back.returncode == 0
            same = ok and load_json(out)["weights_sha256"] == load_json(Path(remote_out))["weights_sha256"]
            rows.append({"front": front, "identical": bool(same), "exits": [here_run.returncode, ran.returncode, back.returncode]})
        note("training_determinism", all(r["identical"] for r in rows), rows)
    return finish_admission(run_root, args, kinds, checks, problems, remote)


def finish_admission(run_root: Path, args: argparse.Namespace, kinds: list[str], checks: Mapping[str, Any], problems: list[str],
                     remote: Mapping[str, Any] | None) -> int:
    cores = int(args.cores) if args.cores else int((remote or {}).get("cpu_quota") or 0) - RESERVE_CORES
    gib = float(args.gib) if args.gib else ((remote or {}).get("memory_bytes") or 0) / 2 ** 30 - RESERVE_GIB
    payload = {"stage": STAGE, "name": args.name, "address": args.address, "port": int(args.port), "user": "root", "key": args.key,
               "kinds": kinds, "budget_cores": max(0, cores), "budget_gib": round(max(0.0, gib), 1),
               "reserve": {"cores": RESERVE_CORES, "gib": RESERVE_GIB}, "facts": remote, "checks": checks,
               "admitted": not problems and cores > 0 and gib > 0, "problems": problems, "code_root": str(ROOT),
               "admitted_utc": utc_now()}
    write_json(hosts_dir(run_root) / f"{args.name}.json", payload)
    marker = suspended_marker(run_root, args.name)
    if payload["admitted"] and marker.exists():
        marker.unlink()
    print(f"[admit {args.name}] admitted={payload['admitted']} cores={payload['budget_cores']} gib={payload['budget_gib']} "
          f"kinds={kinds} problems={problems}", flush=True)
    return 0 if payload["admitted"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("remote-run")
    run.add_argument("--run-root", required=True)
    run.add_argument("--host", required=True)
    run.add_argument("--rss", required=True)
    run.add_argument("--cwd", default=str(ROOT))
    run.add_argument("--push", action="append")
    run.add_argument("--pull", action="append")
    run.add_argument("--pull-every", type=float, default=0.0)
    run.add_argument("--env", action="append")
    run.add_argument("command", nargs=argparse.REMAINDER)
    for name in ("setup", "admit"):
        command = sub.add_parser(name)
        command.add_argument("--run-root", required=True)
        command.add_argument("--name", required=True)
        command.add_argument("--address", required=True)
        command.add_argument("--port", required=True, type=int)
        command.add_argument("--key", default=os.environ.get("VSMT_WORKER_KEY", DEFAULT_KEY))
        command.add_argument("--kinds", default="audit,train1")
        if name == "setup":
            command.add_argument("--relay-from", default=None,
                                 help="ruling 107-3: an admitted host of this run root that already holds every path copies them to the "
                                      "new host (B1 -> w4, then w4 -> w1); default: copy from this coordinator")
            command.add_argument("--relay-key", default=DEFAULT_KEY, help="the key on the relay host that the new host accepts")
        if name == "admit":
            command.add_argument("--cores", type=int)
            command.add_argument("--gib", type=float)
            command.add_argument("--audits-per-front", type=int, default=2)
            command.add_argument("--train-houses", type=int, default=6)
            command.add_argument("--reference-run-root", default=None,
                                 help="the S3-03 run whose finished validation audits are rerun on the host (default: --run-root); "
                                      "S3-05 admits with S3-03's run root here (ruling 107-3)")
    args = parser.parse_args(argv)
    try:
        return {"remote-run": cmd_remote_run, "setup": cmd_setup, "admit": cmd_admit}[args.action](args)
    except RemoteError as exc:
        print(f"[remote_hosts] refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
