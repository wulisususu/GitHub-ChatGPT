# GitHub-ChatGPT

用本机代理为 Linux 服务器安装**仓库级** GitHub Actions Self-hosted Runner。

它解决首次接入慢和步骤分散的问题：本机通过代理下载正确的 Runner 包、校验 SHA-256、使用 SSH/SFTP 上传到服务器、安装为 systemd 服务，并删除本地临时包和远端安装包。再次运行时，若该仓库 Runner 已存在，不会下载或重装。

## 需要提供给智能体的信息

- 这个仓库地址：`https://github.com/wulisususu/GitHub-ChatGPT`
- 要托管的 GitHub 仓库地址
- 服务器地址、SSH 端口、用户名，以及 SSH 密码或密钥
- 一个只在执行时提供的 GitHub PAT

PAT 需要有目标仓库的 Actions Runner 管理权限，才能通过 GitHub API 自动生成短期 Runner 注册令牌。无需再在网页手动点击“新建自托管运行器”。PAT、SSH 密码和短期注册令牌均不写入仓库或服务器配置文件。

## 本机执行

Python 3.9+ 和 Paramiko 是唯一的本机依赖：

```powershell
python -m pip install paramiko
$env:GITHUB_TOKEN = '仅在当前终端设置的PAT'
python .\deploy_runner.py `
  --repository https://github.com/wulisususu/Android-Suspect-Interrogation `
  --host 124.223.176.99 `
  --port 600 `
  --user youyeetoo
```

默认本机 HTTP 代理是 `http://127.0.0.1:7897`。如不使用代理，追加 `--proxy ""`。若服务器通过密码登录，可追加 `--password`；若 sudo 密码不同，追加 `--sudo-password`。省略密码时，脚本使用本机 SSH 密钥或 SSH Agent。

可用 `--label rk3588` 追加设备标签。GitHub 会自动添加 `self-hosted`、`linux` 和对应架构（例如 `ARM64`）标签；工具另加 `managed-by-github-chatgpt` 标签。

## Runner 包如何选择

脚本会通过 SSH 读取 `uname -m`：

- `aarch64` / `arm64` → Linux ARM64 Runner
- `x86_64` / `amd64` → Linux x64 Runner

版本不是写死的。每次首次安装会从 GitHub Actions Runner 的最新正式发行版接口取得正确包名与 SHA-256 摘要；摘要不提供或校验失败时会中止，不会安装未验证的包。

## 验证

```powershell
python .\tests\test_deploy_runner.py -v
```

Runner 成功后，可在目标仓库的“设置 → 操作 → 运行器”看到在线状态。工作流可使用：

```yaml
runs-on: [self-hosted, linux, ARM64]
```

按需增加设备标签，例如：

```yaml
runs-on: [self-hosted, linux, ARM64, rk3588]
```
