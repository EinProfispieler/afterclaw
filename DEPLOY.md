# 文件中控台部署说明

## 1. 新服务器部署（Ubuntu/Debian）

1. 上传发布包并解压：

```bash
tar -xzf storage-http-control-*.tar.gz
cd storage-http-control-*
```

1. 按需修改环境变量（可选）：

```bash
cp .env.example .env.local
```

编辑 `.env.local`，重点改这几个：

- `STORAGE_ROOT`（你的数据目录）
- `PUBLIC_HOST`（你的 DDNS 或公网 IP:端口）
- `QBT_SERVICE`、`DDNS_SERVICE`（你的 systemd 服务名）
- `QBT_API_URL`、`QBT_API_USERNAME`、`QBT_API_PASSWORD`（可选：显示 qBittorrent 上下行/做种统计）
- `SHARECLIP_STORAGE_ROOT`（可选：ShareClip 剪贴数据目录；不设则默认 `APP_ROOT/shareclip/storage`）

ShareClip 已内置在 `1288` 同一进程，**无需再监听 8888**。若机器上仍有旧的 `shareclip.service` 独占 8888，可在确认迁移完成后执行：`sudo systemctl disable --now shareclip.service`

1. 安装并启动：

```bash
set -a
source .env.local
set +a
sudo -E bash install.sh
```

1. 验证：

```bash
systemctl status storage-http-link-web --no-pager
curl -I "http://127.0.0.1:${WEB_PORT:-1288}/"
curl -I "http://127.0.0.1:${WEB_PORT:-1288}/?id=pub"
```

## 2. 常用维护

- 重启服务：`sudo systemctl restart storage-http-link-web`
- 查看日志：`journalctl -u storage-http-link-web -f`
- 关闭开机自启：`sudo systemctl disable storage-http-link-web`

## 3. 迁移到下一台服务器

重复「打包 -> 上传 -> 解压 -> install.sh」流程即可，核心是保留：

- `app.py`
- `shareclip/`（内置 ShareClip 源码）
- `install.sh`
- `.env.example`（或你自己的 `.env.local`）
