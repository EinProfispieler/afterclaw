# AfterClaw

AfterClaw 是一个面向家庭与小团队自托管场景的文件中控平台。  
它把目录服务、HTTP 传输、下载观察、服务控制、DDNS 与实用工具整合到同一个控制台，目标是“低门槛部署、可持续维护、可跨机器迁移”。

## 为什么开发 AfterClaw

- 很多 NAS/轻服务器环境里，功能分散在多个页面，排障和维护成本高。
- 纯脚本方案可用，但新成员接手难、可观测性差。
- 我们需要一个既能稳定运行、又方便持续迭代和开源协作的统一入口。

AfterClaw 的设计重点是：

- 单一入口管理核心能力
- 面向真实运维场景的状态与操作反馈
- 对 GitHub 自动化友好（测试、构建、发布）

## 功能总览

- 目录服务：浏览 `STORAGE_ROOT` 并生成文件 HTTP 链接
- 传输监控：查看实时传输速度、连接与任务列表
- 服务控制：在 Web 控制台管理 qBittorrent、DDNS、HTTP 服务
- 配置中心：统一配置模块开关、主题、来源池等
- 跨平台部署：支持 Linux / macOS / Windows 安装入口

## 快速启动（源码运行）

```bash
WEB_PORT=1288 \
STORAGE_ROOT=/srv/Storage \
PUBLIC_HOST=home.rxotc.cn:1288 \
PUBLIC_SCHEME=http \
python3 -m fcc
```

兼容入口：

```bash
python3 app.py
```

## 安装

Linux / macOS:

```bash
sudo bash install.sh
```

Windows（管理员 PowerShell）:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

或：

```bat
install.cmd
```

## 环境变量

- `WEB_PORT`：端口，默认 `1288`
- `STORAGE_ROOT`：文件根目录，默认 `/srv/Storage`
- `PUBLIC_HOST`：外链域名（可带端口）
- `PUBLIC_SCHEME`：`http` / `https`
- `DOWNLOADS_ENABLED`：是否允许公网传输（`1`/`0`）
- `QBT_SERVICE`：qBittorrent 服务名
- `QBT_API_URL`：qBittorrent WebUI 地址
- `QBT_API_USERNAME` / `QBT_API_PASSWORD`：qBittorrent 认证信息（可选）
- `DDNS_SERVICE`：DDNS 服务名
- `SHARECLIP_STORAGE_ROOT`：内置剪贴数据目录

## GitHub 自动化

仓库已提供 GitHub Actions：

- `.github/workflows/test.yml`：每次 push / PR 自动测试
- `.github/workflows/installers.yml`：每次 push 自动构建三平台安装包 artifact
- `.github/workflows/release.yml`：打 tag 自动生成 Release 包

推送新代码后，在 Actions 页面可直接下载各平台构建产物。

## 部署与迁移

- 生产部署说明：`DEPLOY.md`
- 变更记录：`CHANGELOG.md`
- 贡献说明：`CONTRIBUTING.md`
