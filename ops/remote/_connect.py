"""Shared SSH connection for the ops/remote helpers (paramiko, password from the environment, no PTY).

白话：这台 Windows 笔记本的 ssh 只能交互式输密码，所以用 paramiko 连 AutoDL。主机、端口、用户从环境变量读，密码只从
VSMT_PW 读——不写进任何文件。paramiko 不在项目的 .venv 里：用系统 Python 装到一个目录，再用 VSMT_PYLIB 指过来。
"""

from __future__ import annotations

import os
import sys


def connect():
    pylib = os.environ.get("VSMT_PYLIB")
    if pylib and pylib not in sys.path:
        sys.path.insert(0, pylib)
    try:
        import paramiko
    except ImportError as exc:  # pragma: no cover - environment problem, explained to the caller
        raise SystemExit("paramiko not found: install it with the system Python "
                         "(python -m pip install --target <dir> paramiko) and set VSMT_PYLIB=<dir>") from exc
    password = os.environ.get("VSMT_PW")
    if not password:
        raise SystemExit("set VSMT_PW (the server password; never write it into a file)")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    host = os.environ.get("VSMT_SSH_HOST", "connect.westb.seetacloud.com")
    port = int(os.environ.get("VSMT_SSH_PORT", "36425"))
    try:
        client.connect(host, port=port, username=os.environ.get("VSMT_SSH_USER", "root"), password=password,
                       look_for_keys=False, allow_agent=False, timeout=60, banner_timeout=60, auth_timeout=60)
    except paramiko.AuthenticationException as exc:
        raise SystemExit(f"authentication failed on {host}:{port} (check VSMT_PW)") from exc
    except (OSError, paramiko.SSHException) as exc:
        raise SystemExit(f"cannot reach {host}:{port}: {exc} -- the instance may be powered off, or its port changed after a restart "
                         "(take it from the AutoDL console and set VSMT_SSH_PORT)") from exc
    return client
