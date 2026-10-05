"""Remote CPU hosts for the S3 pools (user 2026-10-04): the commands remote-run builds, the hosts a pool may use, and one job
run end to end through stand-ins for ssh and rsync (on Linux; the host is this machine, so pushes and pulls are no-ops).

Pinned here: pushes and pulls keep the absolute path (rsync --relative); a job's own outputs are pushed with --delete where the
coordinator has them and removed on the host where it has not, never outside the run root; the remote line runs in the same
directory with the job's thread variables and records its group; the exit is the job's own when its receipt came back and 75
(transport) otherwise; only admitted hosts of this stage that are neither paused nor suspended are loaded; a suspension writes
its marker.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import remote_hosts as remote  # noqa: E402
import s3_03_jobs as pool  # noqa: E402


def host(**extra) -> remote.Host:
    payload = {"name": "w1", "address": "connect.example", "port": 12345, "budget_cores": 30, "budget_gib": 52.0,
               "kinds": ["audit", "train1"], "key": "/k"}
    payload.update(extra)
    return remote.Host(payload)


class CommandTests(unittest.TestCase):
    def test_pushes_and_pulls_keep_the_absolute_path(self) -> None:
        argv = remote.push_argv(host(), "/root/autodl-tmp/run/instance/round0")
        self.assertEqual(argv[:3], ["rsync", "-a", "--relative"])
        self.assertEqual(argv[-2:], ["/root/autodl-tmp/run/instance/round0", "root@connect.example:/"])
        self.assertIn("-p 12345", argv[argv.index("-e") + 1])
        self.assertIn("BatchMode=yes", argv[argv.index("-e") + 1])
        self.assertIn("--delete", remote.push_argv(host(), "/a/b", delete=True))
        self.assertNotIn("--delete", remote.push_argv(host(), "/a/b"))
        self.assertEqual(remote.pull_argv(host(), "/a/b")[-2:], ["root@connect.example:/a/b", "/"])
        with self.assertRaises(remote.RemoteError):
            remote.push_argv(host(), "relative/path")

    def test_the_remote_line(self) -> None:
        line = remote.remote_job_command(["python", "x.py", "--config", '{"a": 1}'], cwd="/w t", env={"OMP_NUM_THREADS": "1"},
                                         pidfile="/r/j.rss.json.pid")
        self.assertTrue(line.startswith("cd '/w t' && echo $$ > /r/j.rss.json.pid && exec env OMP_NUM_THREADS=1 python x.py"))
        self.assertIn("'{\"a\": 1}'", line)
        stale = remote.stop_stale_command("/r/j.pid", "/r/j.rss.json")
        self.assertIn("grep -qF -- /r/j.rss.json", stale)  # only the group whose leader runs this job is stopped

    def test_owned_outputs_are_made_equal_and_never_removed_outside_the_run_root(self) -> None:
        present = {"/run/instance/audit/TAF-c00/e1"}
        push, removed = remote.owned_paths_plan(["/run/instance/audit/TAF-c00/e1", "/run/instance/audit/TAF-c01/e1"], run_root="/run",
                                                exists=lambda path: path in present)
        self.assertEqual((push, removed), (["/run/instance/audit/TAF-c00/e1"], ["/run/instance/audit/TAF-c01/e1"]))
        with self.assertRaises(remote.RemoteError):
            remote.owned_paths_plan(["/root/autodl-tmp/vsmt_caches/x"], run_root="/run")
        with self.assertRaises(remote.RemoteError):
            remote.owned_paths_plan(["/runner/x"], run_root="/run")

    def test_the_exit(self) -> None:
        self.assertEqual(remote.exit_from({"exit": 0}, 0), 0)
        self.assertEqual(remote.exit_from({"exit": 3}, 3), 3)
        self.assertEqual(remote.exit_from({"exit": -9}, 255), -9)  # the job's own end, even if the connection then dropped
        self.assertEqual(remote.exit_from(None, 0), remote.TRANSPORT_EXIT)
        self.assertEqual(remote.exit_from(None, 255), remote.TRANSPORT_EXIT)
        self.assertEqual(remote.TRANSPORT_EXIT, pool.TRANSPORT_EXIT)


class HostFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name: str, **extra) -> None:
        payload = {"stage": remote.STAGE, "name": name, "address": "a", "port": 1, "budget_cores": 4, "budget_gib": 8.0,
                   "kinds": ["audit"], "admitted": True}
        payload.update(extra)
        remote.write_json(self.tmp / "hosts" / f"{name}.json", payload)

    def test_only_admitted_hosts_that_are_neither_paused_nor_suspended(self) -> None:
        self.assertEqual(remote.load_hosts(self.tmp), [])
        self.write("ok")
        self.write("refused", admitted=False)
        self.write("paused", paused=True)
        self.write("other", stage="something.else")
        self.write("down")
        remote.suspend(self.tmp, "down", "transport failure in x")
        (self.tmp / "hosts" / "broken.json").write_text("{", encoding="utf-8")
        self.assertEqual([h.name for h in remote.load_hosts(self.tmp)], ["ok"])
        marker = json.loads((self.tmp / "hosts" / "down.suspended").read_text(encoding="utf-8"))
        self.assertEqual(marker["reason"], "transport failure in x")
        (self.tmp / "hosts" / "down.suspended").unlink()
        self.assertEqual([h.name for h in remote.load_hosts(self.tmp)], ["down", "ok"])


SSH_SHIM = """
import subprocess, sys
sys.exit(subprocess.run(["bash", "-c", sys.argv[-1]]).returncode)
"""
DOWN_SHIM = """
import sys
sys.exit(255)
"""
RSYNC_SHIM = """
import sys
sys.exit(0)
"""


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "remote-run end to end needs a POSIX shell")
class RemoteRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.run_root = self.tmp / "run"
        for name, body in (("ssh.py", SSH_SHIM), ("down.py", DOWN_SHIM), ("rsync.py", RSYNC_SHIM)):
            (self.tmp / name).write_text(body, encoding="utf-8")
        remote.write_json(self.run_root / "hosts" / "w1.json", {"stage": remote.STAGE, "name": "w1", "address": "localhost", "port": 22,
                                                               "budget_cores": 2, "budget_gib": 4.0, "kinds": ["audit"], "admitted": True})
        self.saved = {k: os.environ.get(k) for k in ("VSMT_REMOTE_SSH", "VSMT_REMOTE_RSYNC")}
        os.environ["VSMT_REMOTE_RSYNC"] = f"{sys.executable} {self.tmp / 'rsync.py'}"

    def tearDown(self) -> None:
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_job(self, code: int, *, ssh: str = "ssh.py") -> int:
        os.environ["VSMT_REMOTE_SSH"] = f"{sys.executable} {self.tmp / ssh}"
        rss = self.run_root / "jobs" / "j.rss.json"
        out = self.run_root / "instance" / "audit" / "TAF-c00" / "e1"
        job = [sys.executable, "-c", f"import os, sys; os.makedirs({str(out)!r}, exist_ok=True); sys.exit({code})"]
        wrapped = [sys.executable, str(PROJECT_ROOT / "ops" / "vsmt" / "s3_03_jobs.py"), "run-measured", "--out", str(rss), "--", *job]
        return remote.main(["remote-run", "--run-root", str(self.run_root), "--host", "w1", "--rss", str(rss), "--pull", str(out),
                            "--env", "OMP_NUM_THREADS=1", "--cwd", str(PROJECT_ROOT), "--", *wrapped])

    def test_the_job_runs_and_ends_with_its_own_exit_and_host(self) -> None:
        self.assertEqual(self.run_job(0), 0)
        receipt = json.loads((self.run_root / "jobs" / "j.rss.json").read_text(encoding="utf-8"))
        self.assertEqual((receipt["exit"], receipt["host"]), (0, "w1"))
        self.assertEqual(self.run_job(3), 3)

    def test_an_unreachable_host_is_a_transport_failure(self) -> None:
        self.assertEqual(self.run_job(0, ssh="down.py"), remote.TRANSPORT_EXIT)


if __name__ == "__main__":
    unittest.main()
