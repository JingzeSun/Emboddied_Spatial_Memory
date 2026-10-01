# ops/remote：从 Windows 笔记本连 AutoDL 服务器（密钥登录）

白话：Claude／Codex 会话不能用密码登录服务器（会话的安全规则不允许输入密码去认证，即使密码是用户给的）。所以这里用**一把专用密钥**：本机生成一次，公钥由用户在服务器上加进 `authorized_keys` 一次，之后任何会话都能直接连。三个脚本都调用系统自带的 `ssh`／`scp`：`run.py` 把本地的一个 `.sh` 交给服务器执行，`pull.py` 把服务器文件取到本地，`push.py` 把本地文件传上去。它们不读、不存任何密码，也不是实验代码。

## 一次性准备

1. 本机生成专用密钥（不设口令，只给这台服务器用；已有的 `~/.ssh/id_ed25519` 不动）：

   ```bash
   ssh-keygen -t ed25519 -N "" -C autodl-vsmt -f ~/.ssh/autodl_vsmt_ed25519
   ```

2. 用户在 AutoDL 控制台打开实例的网页终端（JupyterLab → Terminal），执行一次（把 `<公钥内容>` 换成 `~/.ssh/autodl_vsmt_ed25519.pub` 的那一整行）：

   ```bash
   mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '<公钥内容>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
   ```

   克隆出的新实例会带上这个文件；换成全新实例时再加一次。

## 每次使用

主机和端口以 AutoDL 控制台当前显示为准（实例重启后端口可能变）。在 Git Bash 里必须先设两个 MSYS 变量，否则 `/root/...` 这样的远端路径会被改写成本地路径：

```bash
export MSYS_NO_PATHCONV=1 MSYS2_ENV_CONV_EXCL='*'
export VSMT_SSH_HOST=connect.westb.seetacloud.com VSMT_SSH_PORT=36425
PY=C:/Users/28115/AppData/Local/Programs/Python/Python312/python.exe   # 任何 Python 3 都行，不需要额外的包
$PY ops/remote/run.py my_step.sh 600                       # 执行本地脚本 my_step.sh，超时 600 秒
$PY ops/remote/pull.py results /root/autodl-tmp/vsmt_outputs/exports/xxx.json   # 取文件到 results/
$PY ops/remote/push.py tmp_probe.py /root/autodl-tmp/vsmt_private/tmp_probe.py  # 传一个临时文件
```

密钥不在默认位置时设 `VSMT_SSH_KEY=<私钥路径>`。若 ssh 报私钥权限过宽（UNPROTECTED PRIVATE KEY FILE），再收紧它的权限（这台机器上 Git 自带的 ssh 目前不报）。服务器主机指纹记在 `~/.ssh/autodl_vsmt_known_hosts`（首次连接自动记录）。

## 注意

- 不申请 PTY：AutoDL 登录会弹欢迎界面，申请 PTY 后 `bash -s` 永不退出。`run.py` 不加 `-t`。
- `BatchMode=yes`：密钥不被接受时直接报错并提示去加公钥，不会停下来问密码。
- 预计超过 30 分钟的任务，在脚本里用 `(setsid nohup bash xxx.sh > log 2>&1 < /dev/null &)` 放后台，另开一次 `run.py` 查日志；不要在同一次连接里等。
- 实例关机时连不上（报“cannot reach”）；重启后端口可能变。
- 服务器上 `git fetch`、`pip` 之前先 `source /etc/network_turbo`。
- 正式代码走 git 提交、服务器 fetch 并新建 detached worktree；`push.py` 只用于临时诊断，不绕过版本库。
- 例子：`run.py` 读 `my_step.sh`，里面写 `date; df -h /root/autodl-tmp`，输出服务器时间和磁盘余量，最后一行 `[exit 0]`。它不等于一个能交互的终端。
