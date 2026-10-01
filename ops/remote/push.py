#!/usr/bin/env python3
"""Copy one local file to a server path with the system scp and the dedicated key (the remote directory must exist).

白话：把一个本地文件传到服务器的指定路径（远端目录要已存在），用密钥、不用密码。正式代码应走 git 提交、服务器 fetch，
不要用它绕过版本库；它只用于临时的一次性诊断脚本或数据。

Usage:
  python ops/remote/push.py <local_file> <remote_path>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stdout.buffer.write(__doc__.encode("utf-8"))  # the console code page cannot print it
        return 2
    cfg = _ssh.settings()
    done = _ssh.run([_ssh.tool("scp"), *_ssh.common_options(cfg), "-P", cfg["port"], argv[0], f"{cfg['user']}@{cfg['host']}:{argv[1]}"])
    if done.returncode != 0:
        print(_ssh.explain_failure(done.returncode, done.stderr.decode("utf-8", "replace"), cfg), file=sys.stderr)
        return 1
    print(f"{argv[0]} -> {argv[1]} ({os.path.getsize(argv[0])} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
