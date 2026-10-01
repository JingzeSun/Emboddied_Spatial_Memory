# ops/remote：从 Windows 笔记本连 AutoDL 服务器

白话：这台 Windows 笔记本上的 `ssh` 只能交互式输入密码，Claude／Codex 的命令行里没法输；系统也没有 `sshpass`、`plink`，服务器不接受密钥登录。这里的三个脚本用 Python 的 paramiko 库按密码连接：`run.py` 把本地的一个 `.sh` 交给服务器执行，`pull.py` 把服务器文件取到本地，`push.py` 把本地文件传上去。它们不含密码，也不是实验代码，只是连接工具。

## 一次性准备（每台机器一次）

用**系统 Python**（项目的 `.venv` 没有 pip）把 paramiko 装到一个目录：

```bash
C:/Users/28115/AppData/Local/Programs/Python/Python312/python.exe -m pip install --target C:/Users/28115/vsmt_pylib paramiko
```

## 每次使用

先设环境变量（Git Bash 下两条 MSYS 变量必须有，否则路径样的字符串和以 `/` 开头的密码会被改写）：

```bash
export MSYS_NO_PATHCONV=1 MSYS2_ENV_CONV_EXCL='*'
export VSMT_PYLIB=C:/Users/28115/vsmt_pylib
export VSMT_SSH_HOST=connect.westb.seetacloud.com VSMT_SSH_PORT=36425   # 以 AutoDL 控制台当前显示为准
export VSMT_PW='<服务器密码>'                                         # 只放环境变量，不写进任何文件、提交或记忆
```

然后用系统 Python 运行：

```bash
PY=C:/Users/28115/AppData/Local/Programs/Python/Python312/python.exe
$PY ops/remote/run.py my_step.sh 600                       # 执行本地脚本 my_step.sh，超时 600 秒
$PY ops/remote/pull.py results /root/autodl-tmp/vsmt_outputs/exports/xxx.json   # 取文件到 results/
$PY ops/remote/push.py tmp_probe.py /root/autodl-tmp/vsmt_private/tmp_probe.py  # 传一个临时文件
```

## 注意

- 不申请 PTY：AutoDL 登录会弹欢迎界面，申请 PTY 后 `bash -s` 永不退出。`run.py` 已经这样做。
- 预计超过 30 分钟的任务，在脚本里用 `(setsid nohup bash xxx.sh > log 2>&1 < /dev/null &)` 放后台，另开一次 `run.py` 查日志；不要在同一次连接里等。
- 实例关机时连不上；重启后端口可能变，以控制台为准。
- 服务器上 `git fetch`、`pip` 之前先 `source /etc/network_turbo`。
- 正式代码走 git 提交、服务器 fetch 并新建 detached worktree；`push.py` 只用于临时诊断，不绕过版本库。
- 例子：`run.py` 读 `my_step.sh`，里面写 `date; df -h /root/autodl-tmp`，输出服务器时间和磁盘余量，最后一行 `[exit 0]`。它不等于一个能交互的终端。
