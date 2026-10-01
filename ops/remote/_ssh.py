"""Shared settings for the ops/remote helpers: the system ssh / scp with a dedicated key, never a password.

白话：用系统自带的 ssh／scp 和一把专用密钥连 AutoDL，不输入、不读取任何密码（会话的安全规则不允许用密码登录，即使是用户
给的密码）。主机、端口、用户、密钥路径都从环境变量读，有默认值；BatchMode=yes 保证密钥不对时直接报错，而不是停下来问密码。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

HOME_SSH = Path.home() / ".ssh"
DEFAULT_KEY = HOME_SSH / "autodl_vsmt_ed25519"
KNOWN_HOSTS = HOME_SSH / "autodl_vsmt_known_hosts"


def settings() -> dict[str, str]:
    key = Path(os.environ.get("VSMT_SSH_KEY", str(DEFAULT_KEY)))
    if not key.exists():
        raise SystemExit(f"no key at {key}: create one with  ssh-keygen -t ed25519 -N \"\" -f {key}  and append {key}.pub to "
                         "/root/.ssh/authorized_keys on the instance (AutoDL web terminal), or set VSMT_SSH_KEY")
    return {"host": os.environ.get("VSMT_SSH_HOST", "connect.westb.seetacloud.com"),
            "port": os.environ.get("VSMT_SSH_PORT", "36425"),
            "user": os.environ.get("VSMT_SSH_USER", "root"), "key": str(key)}


def common_options(cfg: dict[str, str]) -> list[str]:
    return ["-i", cfg["key"], "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"UserKnownHostsFile={KNOWN_HOSTS}", "-o", "ConnectTimeout=60", "-o", "ServerAliveInterval=30"]


def tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise SystemExit(f"{name} not found on PATH (Git Bash's /usr/bin or Windows OpenSSH)")
    return found


def explain_failure(code: int, stderr: str, cfg: dict[str, str]) -> str:
    text = stderr.strip().splitlines()[-1] if stderr.strip() else ""
    if "Permission denied" in stderr:
        return f"key refused on {cfg['host']}:{cfg['port']} ({text}) -- append {cfg['key']}.pub to /root/.ssh/authorized_keys on the instance"
    if "Connection refused" in stderr or "timed out" in stderr or "Could not resolve" in stderr or "Connection closed" in stderr:
        return (f"cannot reach {cfg['host']}:{cfg['port']} ({text}) -- the instance may be powered off, or its port changed after a "
                "restart (take it from the AutoDL console and set VSMT_SSH_PORT)")
    return f"ssh exit {code}: {text}"


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, **kwargs)
