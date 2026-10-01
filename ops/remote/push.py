#!/usr/bin/env python3
"""Copy one local file to a server path over SFTP (the remote directory must exist).

白话：把一个本地文件传到服务器的指定路径（远端目录要已存在）。正式代码应走 git 提交、服务器 fetch，不要用它绕过版本库；
它只用于临时的一次性诊断脚本或数据。

Usage:
  python ops/remote/push.py <local_file> <remote_path>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _connect import connect  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stdout.buffer.write(__doc__.encode("utf-8"))  # the console code page cannot print it
        return 2
    client = connect()
    try:
        sftp = client.open_sftp()
        sftp.put(argv[0], argv[1])
        print(f"{argv[0]} -> {argv[1]} ({os.path.getsize(argv[0])} bytes)")
        sftp.close()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
