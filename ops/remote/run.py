#!/usr/bin/env python3
"""Run a local bash script on the server: the script goes to `bash -s` on stdin, no PTY; prints stdout, stderr and the exit code.

白话：把本地写好的一个 .sh 文件原样交给服务器的 bash 执行，打印输出和退出码。不申请 PTY（AutoDL 的登录欢迎界面会让
`bash -s` 永不退出）。超过 30 分钟的任务请在脚本里用 `setsid nohup ... &` 放到后台，再另开一次查日志。

Usage:
  python ops/remote/run.py <script.sh> [timeout_seconds]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _connect import connect  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        sys.stdout.buffer.write(__doc__.encode("utf-8"))  # the console code page cannot print it
        return 2
    timeout = float(argv[1]) if len(argv) > 1 else 600.0
    with open(argv[0], "rb") as handle:
        body = handle.read().replace(b"\r\n", b"\n")  # a CRLF script would break bash
    client = connect()
    try:
        stdin, stdout, stderr = client.exec_command("bash -s", timeout=timeout)
        stdin.write(body)
        stdin.channel.shutdown_write()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
    finally:
        client.close()
    sys.stdout.buffer.write(out.encode("utf-8", "replace"))
    if err.strip():
        sys.stdout.buffer.write(("\n--- stderr ---\n" + err).encode("utf-8", "replace"))
    sys.stdout.buffer.write(f"\n[exit {code}]\n".encode())
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
