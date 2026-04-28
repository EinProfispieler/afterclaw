# 文件中控台（1288 单端口）

用于统一管理你的文件目录服务、下载监控和服务控制，目标是“换服务器也能直接迁移”。

## 功能总览

- 目录服务：浏览 `STORAGE_ROOT`（默认 `/srv/Storage`），一键生成当前目录所有文件的 HTTP 链接
- 下载服务：`/http-files/*` 支持大文件流式传输和 `Range` 断点续传
- 中控页面：查看系统状态、实时外网下载速度、当前活跃传输
- 服务控制：在页面里控制 `qBittorrent-nox`、DDNS、本服务的开关和重启
- **ShareClip**：源码在 `shareclip/`，与主程序**同一进程、同一端口 1288**，无需再开 8888；剪贴数据在 `SHARECLIP_STORAGE_ROOT`（默认 `APP_ROOT/shareclip/storage`）。页面右上角可切换**浅色 / 深色**主题（含内嵌 ShareClip）
- 安全策略：主页和受控 API 仅局域网可访问，`/http-files/*` 可按开关对外提供下载

## 快速启动（不装服务）

```bash
WEB_PORT=1288 \
STORAGE_ROOT=/srv/Storage \
PUBLIC_HOST=home.rxotc.cn:1288 \
PUBLIC_SCHEME=http \
SHARECLIP_STORAGE_ROOT=/opt/storage-http-link-web/shareclip/storage \
python3 -m fcc
```

兼容入口仍可用：

```bash
python3 app.py
```

## 推荐安装（systemd）

```bash
sudo bash install.sh
```

`install.sh` 现已按平台分发到：

- `scripts/install_ubuntu.sh`
- `scripts/install_mint.sh`
- `scripts/install_macos.sh`

兼容旧入口：

```bash
sudo bash install_on_130.sh
```

默认服务名：`storage-http-link-web`

## 环境变量

- `WEB_PORT`：端口，默认 `1288`
- `STORAGE_ROOT`：文件根目录，默认 `/srv/Storage`
- `PUBLIC_HOST`：生成外链使用的域名（可带端口）
- `PUBLIC_SCHEME`：`http` / `https`
- `DOWNLOADS_ENABLED`：是否允许外网下载（`1`/`0`）
- `QBT_SERVICE`：qBittorrent 的 systemd 服务名
- `QBT_API_URL`：qBittorrent WebUI 地址（默认 `http://127.0.0.1:8080`）
- `QBT_API_USERNAME` / `QBT_API_PASSWORD`：qBittorrent WebUI 账号密码（可选；用于展示上/下行与做种统计）
- `DDNS_SERVICE`：DDNS 的 systemd 服务名
- `SHARECLIP_STORAGE_ROOT`：ShareClip 数据目录（各 ID 的剪贴与图片）；默认 `APP_ROOT/shareclip/storage`

## 打包到 iCloud（迁移用）

在项目目录执行：

```bash
bash package_to_icloud.sh
```

会生成：

- 本地包：`dist/storage-http-control-时间戳.tar.gz`
- 自动复制：`/Users/你的用户名/Library/Mobile Documents/com~apple~CloudDocs/你的目录/`

可通过环境变量覆盖 iCloud 目录：

```bash
ICLOUD_DIR="/Users/你的用户名/Library/Mobile Documents/com~apple~CloudDocs/你的目录" bash package_to_icloud.sh
```

## 换新服务器部署

完整步骤见 `DEPLOY.md`。
