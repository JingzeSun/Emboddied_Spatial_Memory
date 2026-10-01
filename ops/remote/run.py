#!/usr/bin/env python3
"""Run a local bash script on the server: the system ssh with the dedicated key, the script on stdin to `bash -s`, no PTY.

白话：把本地写好的一个 .sh 文件原样交给服务器的 bash 执行，打印输出和退出码。用密钥登录、不用密码；不申请 PTY（AutoDL 的
登录欢迎界面会让 `bash -s` 永不退出）。超过 30 分钟的任务请在脚本里用 `setsid nohup ... &` 放到后台，再另开一次查日志。

Usage:
  python ops/remote/run.py <script.sh> [timeout_seconds]
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        sys.stdout.buffer.write(__doc__.encode("utf-8"))  # the console code page cannot print it
        return 2
    timeout = float(argv[1]) if len(argv) > 1 else 600.0
    with open(argv[0], "rb") as handle:
        body = handle.read().replace(b"\r\n", b"\n")  # a CRLF script would break bash
    cfg = _ssh.settings()
    command = [_ssh.tool("ssh"), *_ssh.common_options(cfg), "-p", cfg["port"], f"{cfg['user']}@{cfg['host']}", "bash -s"]
    try:
        done = _ssh.run(command, input=body, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"timed out after {timeout:.0f} s (a job started with setsid nohup keeps running on the server)", file=sys.stderr)
        return 3
    out = done.stdout.decode("utf-8", "replace")
    err = done.stderr.decode("utf-8", "replace")
    sys.stdout.buffer.write(out.encode("utf-8", "replace"))
    if done.returncode == 255:  # ssh itself failed (not the script)
        print(_ssh.explain_failure(done.returncode, err, cfg), file=sys.stderr)
        return 255
    if err.strip():
        sys.stdout.buffer.write(("\n--- stderr ---\n" + err).encode("utf-8", "replace"))
    sys.stdout.buffer.write(f"\n[exit {done.returncode}]\n".encode())
    return 0 if done.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
