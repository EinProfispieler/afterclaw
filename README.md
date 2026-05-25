# AfterClaw [![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/X0M21ZSG35)

AfterClaw is a self-hosted control center for home/NAS server workflows.
It unifies directory link generation, HTTP transfer, qBittorrent/DDNS operations, and web terminal access in one UI.

Website: [https://www.afterclaw.xyz](https://www.afterclaw.xyz)  
Language: English | [简体中文](#简体中文)

## New UI Screenshots

### Dashboard (Light)
![AfterClaw Dashboard Light](docs/screenshots/ui-dashboard-light.png)

### Dashboard (Dark)
![AfterClaw Dashboard Dark](docs/screenshots/ui-dashboard-dark.png)

### HTTPD Workspace
![AfterClaw HTTPD](docs/screenshots/ui-httpd.png)

### ShareClip
![AfterClaw ShareClip](docs/screenshots/ui-shareclip.png)

### Web Terminal
![AfterClaw Web Terminal](docs/screenshots/ui-web-terminal.png)

### Services Overview
![AfterClaw Services](docs/screenshots/ui-attachment-1.png)

### Docker Recommendations
![AfterClaw Docker Recommendations](docs/screenshots/ui-attachment-2.png)

## What Problem It Solves

Most home server workflows break down into many separate scripts and panels:

- one tool for upload
- another for service status
- another for DDNS
- another for terminal access

AfterClaw collapses these into one operational surface so setup, migration, and troubleshooting stay consistent.

## Main Use Case

If your media stack uses netdisk-backed playback (for example POPCorn / VidHub):

1. normalize media filenames
2. stream-upload large files with resume
3. monitor throughput and service state centrally

This is the core loop AfterClaw is designed for.

## Core Modules

- Dashboard: system health, transfer activity, service status
- Directory Service: browse `STORAGE_ROOT`, generate file links
- HTTP Transfer: large-file stream upload with resume
- Service Controls: qBittorrent, DDNS, HTTP module controls
- Docker: container inventory, image pull, install form, and safe start/stop/remove controls
- Web Terminal: remote maintenance + key file management
- ShareClip: lightweight clipboard-style sharing

## Architecture

- Frontend: embedded web dashboard
- Runtime: Python app (`python3 -m fcc` / `python3 app.py`)
- Worker modules: transfer, DDNS, process-network metrics, terminal
- Optional automation: Ko-fi webhook + member email flow

## Quick Start

```bash
WEB_PORT=1288 \
STORAGE_ROOT=/srv/Storage \
PUBLIC_HOST=example.com:1288 \
PUBLIC_SCHEME=http \
python3 -m fcc
```

Compatibility entry:

```bash
python3 app.py
```

## Installation

Recommended:

```bash
curl -fsSL https://raw.githubusercontent.com/EinProfispieler/afterclaw/main/install.sh | sudo bash
```

Installer behavior by platform:

- Linux: installs Python runtime + `requirements.txt` + `smartmontools`
- macOS: installs Python if needed, installs `requirements.txt`, attempts `smartmontools` via Homebrew
- Windows (`install.ps1`): creates venv, installs `requirements.txt`, attempts `smartmontools` via winget

Uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/EinProfispieler/afterclaw/main/install.sh | sudo bash -s -- --uninstall
```

Update (pull latest from GitHub and re-run installer):

```bash
curl -fsSL https://raw.githubusercontent.com/EinProfispieler/afterclaw/main/install.sh | sudo bash -s -- --update
```

Platform scripts:

- `scripts/install_ubuntu.sh`
- `scripts/install_mint.sh`
- `scripts/install_macos.sh`
- `scripts/install_windows.ps1`
- `scripts/setup_torrent_docker.sh` (provisions Docker torrent clients with isolated runtime data root)

Docker safety note:

- Do not place client runtime/config/session data under monitored content roots (for example `/srv/Storage/...`).
- Recommended runtime data root: `/var/lib/afterclaw/torrents`
- Recommended downloads root (content): `/srv/Storage/BT`

Windows (PowerShell as Administrator):

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Windows uninstall (PowerShell as Administrator):

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
```

Windows update (PowerShell as Administrator):

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Update
```

Windows doctor (PowerShell as Administrator):

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Doctor
```

## Configuration

Minimum runtime variables:

- `WEB_PORT`
- `STORAGE_ROOT`
- `PUBLIC_HOST`
- `PUBLIC_SCHEME`

Most operational settings are managed in the in-app `Config` page.

## Ko-fi / Member Automation (Optional)

Current deployment supports:

- Ko-fi webhook ingest
- event persistence
- automatic email notifications (Resend)

Recommended endpoint:

- `https://ddns.afterclaw.xyz/webhooks/kofi`

## Build and CI

Workflow: `.github/workflows/installers.yml`

- Trigger: `push`, `workflow_dispatch`
- Targets: Linux, macOS, Windows
- Output: installer artifacts

## Roadmap

- member activation (one-time code + password setup)
- subscription validity + grace-period automation
- self-service DDNS prefix management with yearly change limits

## Versioning

- Stable (`main`): SemVer tags (`MAJOR.MINOR.PATCH`)
- Nightly (`nightly`): PEP 440 dev tags (`MAJOR.MINOR.NEXT_PATCH.devYYYYMMDD`)
- `.dev0` is reserved for local bootstrap and not for stable release

---

## 简体中文

AfterClaw 是面向家庭 / NAS 场景的自托管中控台。  
它把目录链接生成、HTTP 传输、qBittorrent/DDNS 控制和 Web 终端收敛到一个统一入口。

### 解决的问题

家庭服务器常见问题不是“功能不够”，而是“工具太散”：上传、监控、DDNS、终端各在不同面板里，迁移和排障成本高。  
AfterClaw 的目标就是把这些运维动作集中到一个界面。

### 典型流程

1. 规范电影/剧集命名
2. 流式上传大文件（支持续传）
3. 在一个看板里监控速率与服务状态

### 核心模块

- Dashboard（系统/传输/服务状态）
- Directory Service（浏览 `STORAGE_ROOT`、生成链接）
- HTTP Transfer（大文件流式上传）
- Service Controls（qBittorrent / DDNS / HTTP）
- Web Terminal（远程维护 + 密钥管理）
- ShareClip（轻量分享）

### 安装 / 卸载 / 更新

推荐安装：

```bash
curl -fsSL https://raw.githubusercontent.com/EinProfispieler/afterclaw/main/install.sh | sudo bash
```

卸载（仅移除服务，不删除程序与数据目录）：

```bash
curl -fsSL https://raw.githubusercontent.com/EinProfispieler/afterclaw/main/install.sh | sudo bash -s -- --uninstall
```

更新（从 GitHub 拉取最新版并执行安装）：

```bash
curl -fsSL https://raw.githubusercontent.com/EinProfispieler/afterclaw/main/install.sh | sudo bash -s -- --update
```

Windows（管理员 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Windows 卸载（管理员 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
```

Windows 更新（管理员 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Update
```

Windows 自检（管理员 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Doctor
```
