#!/usr/bin/env python3
"""Copy server files into a local directory over SFTP and print each file's sha256 prefix and size.

白话：把服务器上的若干文件取到本地目录（常用于把 exports 里的结果取到 results/），并打印摘要前缀与大小，方便和服务器端核对。

Usage:
  python ops/remote/pull.py <local_dir> <remote_path> [<remote_path> ...]
"""

from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _connect import connect  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stdout.buffer.write(__doc__.encode("utf-8"))  # the console code page cannot print it
        return 2
    local_dir = argv[0]
    os.makedirs(local_dir, exist_ok=True)
    client = connect()
    try:
        sftp = client.open_sftp()
        for remote in argv[1:]:
            local = os.path.join(local_dir, os.path.basename(remote))
            sftp.get(remote, local)
            with open(local, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            print(digest[:16], os.path.getsize(local), local)
        sftp.close()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
